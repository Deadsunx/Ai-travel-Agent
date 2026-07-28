"""Manual planning route — same data pipeline as the chat agent, no LLM.

Takes an explicit form instead of a sentence, then runs the identical tool
sequence so both paths produce the same shape of plan (including the
provenance markers the UI stamps onto each section).
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_TRIP_DAYS = 30


class ManualPlanRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: str
    passengers: int = 1
    budget: float
    preferences: str = "any"
    trip_style: str = "relaxed"


def _safe_load(raw: Optional[str]) -> Optional[Dict]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _cheapest(section: Optional[Dict], list_key: str, price_key: str) -> float:
    prices = []
    for item in (section or {}).get(list_key) or []:
        try:
            value = float(item.get(price_key, 0))
            if value > 0:
                prices.append(value)
        except (ValueError, TypeError):
            continue
    return min(prices) if prices else 0


@router.post("/manual-plan")
async def create_manual_plan(request: ManualPlanRequest):
    """Generate a trip plan from form input, bypassing the AI agent."""
    try:
        from app.tools import (
            flight_search,
            hotel_search,
            restaurant_finder,
            attraction_finder,
            budget_calculator,
            itinerary_builder,
        )

        try:
            departure = datetime.strptime(request.departure_date, "%Y-%m-%d")
            arrival_back = datetime.strptime(request.return_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Dates must be in YYYY-MM-DD format")

        num_days = (arrival_back - departure).days
        if num_days < 1:
            raise HTTPException(status_code=400, detail="Return date must be after the departure date")
        if num_days > MAX_TRIP_DAYS:
            raise HTTPException(status_code=400, detail=f"Trips are limited to {MAX_TRIP_DAYS} days")

        travelers = max(1, request.passengers)
        cuisine = request.preferences if request.preferences != "any" else None

        logger.info("Manual plan: %s -> %s, %s days", request.origin, request.destination, num_days)

        # Independent lookups run together, as in the chat pipeline.
        flights_raw, hotels_raw, restaurants_raw, attractions_raw = await asyncio.gather(
            asyncio.to_thread(
                flight_search,
                origin=request.origin,
                destination=request.destination,
                date=request.departure_date,
                return_date=request.return_date,
                passengers=travelers,
            ),
            asyncio.to_thread(
                hotel_search,
                city=request.destination,
                check_in=request.departure_date,
                check_out=request.return_date,
                guests=travelers,
            ),
            asyncio.to_thread(
                restaurant_finder,
                city=request.destination,
                cuisine=cuisine,
                budget="medium",
            ),
            asyncio.to_thread(attraction_finder, city=request.destination),
        )

        flights_data = _safe_load(flights_raw)
        hotels_data = _safe_load(hotels_raw)
        restaurants_data = _safe_load(restaurants_raw)
        attractions_data = _safe_load(attractions_raw)

        # Price the trip against the real fares found and the stated limit —
        # both were previously collected and then ignored.
        budget_data = _safe_load(await asyncio.to_thread(
            budget_calculator,
            destination=request.destination,
            days=num_days,
            travelers=travelers,
            budget_limit=request.budget,
            flight_cost=_cheapest(flights_data, "flights", "price"),
            hotel_cost_per_night=_cheapest(hotels_data, "hotels", "price_per_night"),
        ))

        itinerary_data = _safe_load(await asyncio.to_thread(
            itinerary_builder,
            destination=request.destination,
            days=num_days,
            interests=request.trip_style,
            restaurants=[r.get("name") for r in (restaurants_data or {}).get("restaurants", [])],
            attractions=[a.get("name") for a in (attractions_data or {}).get("attractions", [])],
        ))

        return {
            "success": True,
            "mode": "manual",
            "collected_data": {
                "flights": flights_data,
                "hotels": hotels_data,
                "restaurants": restaurants_data,
                "attractions": attractions_data,
                "itinerary": itinerary_data,
                "budget": budget_data,
                "trip_params": {
                    "origin": request.origin,
                    "destination": request.destination,
                    "start_date": request.departure_date,
                    "end_date": request.return_date,
                    "days": num_days,
                    "travelers": travelers,
                    "budget_limit": request.budget,
                },
            },
            "destination": request.destination,
            "duration_days": num_days,
            "message": f"Your {num_days}-day trip to {request.destination} is ready.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Manual planning error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not build the plan. Please try again.")
