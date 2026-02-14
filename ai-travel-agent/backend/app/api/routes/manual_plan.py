"""
Manual planning API route - Generate itineraries without AI agent
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ManualPlanRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: str
    passengers: int = 1
    budget: float
    preferences: str = "any"
    trip_style: str = "relaxed"


@router.post("/manual-plan")
async def create_manual_plan(request: ManualPlanRequest):
    """
    Generate trip itinerary from manual form input
    Bypasses AI agent and directly calls tools
    """
    try:
        from app.tools import (
            flight_search, 
            hotel_search, 
            restaurant_finder, 
            budget_calculator,
            itinerary_builder
        )
        
        logger.info(f"Manual planning: {request.origin} -> {request.destination}")
        
        # 1. Search flights
        flights_data = json.loads(flight_search(
            origin=request.origin,
            destination=request.destination,
            date=request.departure_date,
            return_date=request.return_date,
            passengers=request.passengers
        ))
        
        # 2. Search hotels
        hotels_data = json.loads(hotel_search(
            city=request.destination,
            check_in=request.departure_date,
            check_out=request.return_date,
            guests=request.passengers
        ))
        
        # 3. Find restaurants
        restaurants_data = json.loads(restaurant_finder(
            city=request.destination,
            cuisine=request.preferences if request.preferences != "any" else None,
            budget="moderate"
        ))
        
        # 4. Calculate trip duration
        dep_date = datetime.strptime(request.departure_date, "%Y-%m-%d")
        ret_date = datetime.strptime(request.return_date, "%Y-%m-%d")
        num_days = (ret_date - dep_date).days
        
        if num_days < 1:
            raise HTTPException(status_code=400, detail="Return date must be after departure date")
        
        # 5. Build itinerary
        itinerary_data = json.loads(itinerary_builder(
            destination=request.destination,
            days=num_days,
            interests=request.trip_style
        ))
        
        # 6. Calculate budget breakdown (use correct parameters)
        try:
            budget_data = json.loads(budget_calculator(
                destination=request.destination,
                days=num_days,
                travelers=request.passengers,
                budget_level="medium"  # Can map from request.budget if needed
            ))
        except Exception as e:
            logger.warning(f"Budget calculator error: {e}")
            # Provide simple budget breakdown if calculator fails
            budget_data = {
                "total_budget": request.budget,
                "estimated_cost": 0,
                "breakdown": {},
                "currency": "INR"
            }
        
        # Format response for frontend (match AI chat response structure)
        return {
            "success": True,
            "mode": "manual",
            "collected_data": {
                "flights": flights_data,  # Includes source field
                "hotels": hotels_data,    # Includes source field
                "restaurants": restaurants_data,  # Includes source field
                "itinerary": itinerary_data,
                "budget": budget_data
            },
            "destination": request.destination,
            "duration_days": num_days,
            "message": f"✅ Your {num_days}-day trip to {request.destination} is ready!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual planning error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating itinerary: {str(e)}")
