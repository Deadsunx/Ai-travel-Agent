from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.services.db_service import save_itinerary, get_itinerary_by_id
from app.models.schemas import SaveItineraryRequest, SaveItineraryResponse

router = APIRouter()


@router.post("/save", response_model=SaveItineraryResponse)
async def save_user_itinerary(request: SaveItineraryRequest):
    """
    Save generated itinerary to database
    """
    try:
        itinerary_id = save_itinerary(
            session_id=request.session_id,
            user_id=int(request.user_id) if request.user_id else None,
            itinerary_data=request.itinerary_data
        )
        
        return SaveItineraryResponse(
            success=True,
            itinerary_id=itinerary_id,
            message="Itinerary saved successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{itinerary_id}")
async def get_itinerary(itinerary_id: int):
    """
    Retrieve saved itinerary by ID
    """
    itinerary = get_itinerary_by_id(itinerary_id)
    
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    return itinerary
