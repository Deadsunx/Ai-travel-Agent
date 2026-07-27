from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import asyncio

from app.agents.travel_agent import create_planner
from app.services.redis_service import redis_service
from app.services.db_service import save_chat_message
from app.models.schemas import ChatRequest

router = APIRouter()

# In-memory cancellation flags keyed by session id.
_cancel_events: dict[str, asyncio.Event] = {}


@router.post("/")
async def chat(request: ChatRequest):
    """
    Main chat endpoint with streaming response
    """
    
    # Rate limiting
    user_id = request.user_id or request.session_id
    if not redis_service.check_rate_limit(user_id, max_requests=20):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. You can make 20 requests per hour. Please try again later."
        )
    
    try:
        # Stream response — events come straight from the agent pipeline:
        # real per-tool progress and real LLM tokens (no post-hoc re-chunking).
        async def generate():
            cancel_event = _cancel_events.setdefault(request.session_id, asyncio.Event())
            cancel_event.clear()

            def sse(payload: dict) -> str:
                return f"data: {json.dumps(payload)}\n\n"

            try:
                # Initialize planner ("pipeline" or "graph"; see create_planner)
                model = request.model or "qwen3:8b"
                agent = create_planner(
                    session_id=request.session_id,
                    model_name=model,
                    planner=request.planner,
                )

                async for event in agent.plan_trip_events(request.message):
                    if cancel_event.is_set():
                        yield sse({'type': 'cancelled', 'message': 'Generation stopped by user.'})
                        return

                    if event["type"] == "result":
                        result = event["data"]
                        if result.get("success"):
                            yield sse(event)
                            # Save to database
                            try:
                                save_chat_message(
                                    session_id=request.session_id,
                                    user_message=request.message,
                                    agent_response=result
                                )
                            except Exception as e:
                                print(f"Error saving chat: {e}")
                        else:
                            yield sse({'type': 'error', 'message': result.get('error', 'Unknown error occurred')})
                    else:
                        yield sse(event)

            except Exception as e:
                yield sse({'type': 'error', 'message': f"Error: {str(e)}"})
            finally:
                _cancel_events.pop(request.session_id, None)
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{session_id}")
async def cancel_chat(session_id: str):
    """Cancel an in-progress chat generation for a session."""
    cancel_event = _cancel_events.setdefault(session_id, asyncio.Event())
    cancel_event.set()
    return {"success": True, "message": "Cancellation requested"}


@router.post("/sync")
async def chat_sync(request: ChatRequest):
    """
    Non-streaming chat endpoint - returns complete response
    """
    
    # Rate limiting
    user_id = request.user_id or request.session_id
    if not redis_service.check_rate_limit(user_id, max_requests=20):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    
    try:
        # Initialize planner ("pipeline" or "graph"; see create_planner)
        model = request.model or "qwen3:8b"
        agent = create_planner(
            session_id=request.session_id,
            model_name=model,
            planner=request.planner,
        )

        # Execute agent
        result = await agent.plan_trip(request.message)
        
        # Save to database
        try:
            save_chat_message(
                session_id=request.session_id,
                user_message=request.message,
                agent_response=result
            )
        except Exception as e:
            print(f"Error saving chat: {e}")
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get conversation history for a session"""
    messages = redis_service.get_session(session_id)
    
    if not messages:
        return {"session_id": session_id, "messages": []}
    
    return {"session_id": session_id, "messages": messages}


@router.delete("/history/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear conversation history for a session"""
    redis_service.delete(f"session:{session_id}")
    return {"success": True, "message": "Chat history cleared"}
