from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from app.config import settings
from app.api.routes import chat, itinerary, health, manual_plan, models
from app.models.database import Base
from app.services.db_service import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup: Create database tables
    try:
        init_db()
        print("✅ Database tables created/verified")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
    
    yield
    
    # Shutdown: Cleanup
    print("🔴 Shutting down AI Travel Agent...")


app = FastAPI(
    title="AI Travel Agent API",
    description="""
    🌍 AI-powered travel planning with real-time data
    
    ## Features
    - Chat with AI agent to plan trips
    - Manual planning form (no AI required)
    - Real-time flight and hotel prices
    - Restaurant recommendations
    - Budget-conscious itinerary generation
    - Streaming responses for real-time feedback
    
    ## Endpoints
    - **POST /api/chat/** - Main chat endpoint (streaming)
    - **POST /api/chat/sync** - Chat endpoint (non-streaming)
    - **GET /api/chat/history/{session_id}** - Get conversation history
    - **POST /api/manual-plan** - Generate itinerary from form (no AI)
    - **POST /api/itinerary/save** - Save generated itinerary
    - **GET /api/itinerary/{id}** - Get saved itinerary
    - **GET /health** - Health check
    """,
    version="1.0.0",
    lifespan=lifespan
)


# CORS Configuration - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    # Local development origins are always allowed; deployed frontends are
    # added through ALLOWED_ORIGINS (comma-separated), because a hosted
    # frontend lives on a domain this file cannot know.
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(models.router, prefix="/api/models", tags=["Models"])
app.include_router(itinerary.router, prefix="/api/itinerary", tags=["Itinerary"])
app.include_router(manual_plan.router, prefix="/api", tags=["Manual Planning"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "🌍 Welcome to AI Travel Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "chat": "/api/chat/",
            "itinerary": "/api/itinerary/",
            "health": "/health/"
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler — log details server-side, return a generic message."""
    import logging
    logging.getLogger("app").exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "Something went wrong. Please try again."
        }
    )


# Main package init
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
