from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import asyncio

from app.agents.catalog import available_models, default_model, is_available
from app.agents.travel_agent import create_planner
from app.config import settings
from app.services.redis_service import redis_service
from app.services.db_service import save_chat_message
from app.models.schemas import ChatRequest

router = APIRouter()

# In-memory cancellation flags keyed by session id.
_cancel_events: dict[str, asyncio.Event] = {}


def client_key(request: Request, chat_request: ChatRequest) -> str:
    """Who to rate limit.

    Prefers the client IP: a session id is generated in the browser, so
    limiting on it only asks an abusive client to press refresh. Render and
    Vercel both sit behind proxies, so the first hop of X-Forwarded-For is
    the real client.
    """
    if chat_request.user_id:
        return f"user:{chat_request.user_id}"

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"

    client = request.client
    return f"ip:{client.host}" if client else f"session:{chat_request.session_id}"


def resolve_model(requested: Optional[str]) -> str:
    """The model to run, or a 400 explaining why the requested one cannot.

    Without this, asking a cloud deployment for a local model means waiting
    out a connection timeout to an Ollama that was never there.
    """
    if not requested:
        return default_model()

    if is_available(requested):
        return requested

    runnable = [m["label"] for m in available_models() if m["available"]]
    detail = next(
        (m["reason"] for m in available_models() if m["value"] == requested),
        "That model is not available on this server.",
    )
    raise HTTPException(
        status_code=400,
        detail=f"{detail} Available here: {', '.join(runnable) or 'none'}.",
    )


@router.post("/")
async def chat(request: ChatRequest, http_request: Request):
    """
    Main chat endpoint with streaming response
    """

    # Rate limiting
    limit = settings.rate_limit_per_hour
    if not redis_service.check_rate_limit(client_key(http_request, request), max_requests=limit):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. You can make {limit} requests per hour. Please try again later."
        )

    model = resolve_model(request.model)

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
async def chat_sync(request: ChatRequest, http_request: Request):
    """
    Non-streaming chat endpoint - returns complete response
    """

    # Rate limiting
    limit = settings.rate_limit_per_hour
    if not redis_service.check_rate_limit(client_key(http_request, request), max_requests=limit):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )

    model = resolve_model(request.model)

    try:
        # Initialize planner ("pipeline" or "graph"; see create_planner)
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
