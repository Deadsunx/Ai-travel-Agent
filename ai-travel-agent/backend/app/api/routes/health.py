from fastapi import APIRouter
from datetime import datetime

from app.services.redis_service import redis_service
from app.services.db_service import check_db_connection
from app.models.schemas import HealthCheckResponse

router = APIRouter()


@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint to verify all services are running
    """
    # Check database connection
    db_status = "connected" if check_db_connection() else "disconnected"
    
    # Check Redis connection
    redis_status = "connected" if redis_service.is_connected() else "disconnected"
    
    # Overall status
    overall_status = "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"
    
    return HealthCheckResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.utcnow()
    )


@router.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"message": "pong", "timestamp": datetime.utcnow().isoformat()}
