from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import asyncio

from app.agents.travel_agent import TravelPlanningAgent
from app.services.redis_service import redis_service
from app.services.db_service import save_chat_message
from app.models.schemas import ChatRequest

router = APIRouter()


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
        # Stream response
        async def generate():
            try:
                # Send initial status
                yield f"data: {json.dumps({'type': 'status', 'message': '🔍 Analyzing your travel request...'})}\n\n"
                await asyncio.sleep(0.3)
                
                # Initialize agent
                model = request.model or "qwen3:8b"
                agent = TravelPlanningAgent(session_id=request.session_id, model_name=model)
                
                yield f"data: {json.dumps({'type': 'status', 'message': '🤖 AI Agent activated, planning your trip...'})}\n\n"
                await asyncio.sleep(0.3)
                
                # Execute agent
                result = await agent.plan_trip(request.message)
                
                if result.get("success"):
                    # Stream progress updates
                    yield f"data: {json.dumps({'type': 'status', 'message': '✅ Itinerary generated successfully!'})}\n\n"
                    await asyncio.sleep(0.2)
                    
                    # Stream the response text word-by-word for perceived speed
                    response_text = result.get("response", "")
                    if response_text:
                        words = response_text.split()
                        chunk_size = 3  # Send 3 words at a time
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i + chunk_size])
                            yield f"data: {json.dumps({'type': 'token', 'content': chunk + ' '})}\n\n"
                            await asyncio.sleep(0.02)  # Small delay between chunks
                    
                    # Send final structured result (flights, hotels, etc.)
                    yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
                    
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
                    yield f"data: {json.dumps({'type': 'error', 'message': result.get('error', 'Unknown error occurred')})}\n\n"
                    
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        
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
        # Initialize agent
        model = request.model or "qwen3:8b"
        agent = TravelPlanningAgent(session_id=request.session_id, model_name=model)
        
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
