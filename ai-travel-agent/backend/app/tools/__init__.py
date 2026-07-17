"""Simple tool implementations with LangChain compatibility"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Callable
import json
import ast
from datetime import datetime
import requests

from app.services.redis_service import redis_service
from app.config import settings


def _extract_json_payload(input_str: str) -> Optional[dict]:
    """Best-effort parse of model-produced tool input."""
    if not input_str:
        return None

    text = input_str.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    for candidate in (text, text[text.find("{"):text.rfind("}") + 1] if "{" in text and "}" in text else ""):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        try:
            data = ast.literal_eval(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


def _normalize_date(raw_date: Any) -> Optional[str]:
    if raw_date is None:
        return None
    if not isinstance(raw_date, str):
        return None
    value = raw_date.strip()
    if not value:
        return None

    known_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y"]
    for fmt in known_formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _norm_key_part(value: Any) -> str:
    """Normalize a cache-key component so 'Goa', ' goa ' and 'GOA' share one entry."""
    return str(value).strip().lower().replace(" ", "_")


def _get_cached(cache_key: str) -> Optional[dict]:
    """Check Redis cache"""
    return redis_service.get_cached(cache_key)


def _set_cache(cache_key: str, data: Any, ttl: int = 3600) -> bool:
    """Store in Redis cache"""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            data = {"result": data}
    return redis_service.set_cache(cache_key, data, ttl)


def google_search(query: str, num_results: int = 5) -> str:
    """Search the web using SerpAPI"""
    num_results = min(max(1, num_results), 10)
    cache_key = f"google_search:{_norm_key_part(query)}:{num_results}"
    
    cached = _get_cached(cache_key)
    if cached:
        return json.dumps(cached)
    
    try:
        params = {
            "q": query,
            "api_key": settings.serpapi_key,
            "num": num_results,
            "engine": "google"
        }
        
        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for result in data.get("organic_results", [])[:num_results]:
            results.append({
                "title": result.get("title"),
                "link": result.get("link"),
                "snippet": result.get("snippet")
            })
        
        _set_cache(cache_key, results, ttl=3600)
        return json.dumps(results, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"error": str(e)})



def flight_search(origin: str, destination: str, date: str = None, return_date: str = None, passengers: int = 1) -> str:
    """Search for real flights using SerpAPI"""
    from .real_api import search_flights_serpapi, get_mock_flights
    
    cache_key = f"flights:{_norm_key_part(origin)}:{_norm_key_part(destination)}:{date}:{return_date}:{passengers}"
    
    # Check cache first
    cached = _get_cached(cache_key)
    if cached:
        return json.dumps(cached)
    
    # Try real API first
    result = search_flights_serpapi(origin, destination, date, return_date, passengers)
    
    # Fallback to mock data if API fails
    if not result:
        result = get_mock_flights(origin, destination, date, passengers)
    
    # Cache the result
    _set_cache(cache_key, result, ttl=1800)
    return json.dumps(result, ensure_ascii=False)


def hotel_search(city: str, check_in: str = None, check_out: str = None, guests: int = 2) -> str:
    """Search for hotels using RapidAPI (with fallback to mock data)"""
    from .real_api import search_hotels_rapidapi, get_mock_hotels
    
    cache_key = f"hotels:{_norm_key_part(city)}:{check_in}:{check_out}:{guests}"
    
    # Check cache first
    cached = _get_cached(cache_key)
    if cached:
        return json.dumps(cached)
    
    # Try real API first
    result = search_hotels_rapidapi(city, check_in, check_out, guests)
    
    # Fallback to mock data if API fails
    if not result:
        result = get_mock_hotels(city, check_in, check_out, guests)
    
    # Cache the result
    _set_cache(cache_key, result, ttl=1800)
    return json.dumps(result, ensure_ascii=False)


def restaurant_finder(city: str, cuisine: str = None, budget: str = "medium") -> str:
    """Find restaurants using Foursquare (with fallback to mock data)"""
    from .real_api import search_restaurants_foursquare, get_mock_restaurants
    
    cache_key = f"restaurants:{_norm_key_part(city)}:{_norm_key_part(cuisine)}:{_norm_key_part(budget)}"
    
    # Check cache first
    cached = _get_cached(cache_key)
    if cached:
        return json.dumps(cached)
    
    # Try real API first
    result = search_restaurants_foursquare(city, cuisine, budget)
    
    # Fallback to mock data if API fails
    if not result:
        result = get_mock_restaurants(city, cuisine, budget)
    
    # Cache the result
    _set_cache(cache_key, result, ttl=3600)
    return json.dumps(result, ensure_ascii=False)


def budget_calculator(
    destination: str,
    days: int = 3,
    travelers: int = 1,
    budget_level: str = "medium",
    budget_limit: float = 0,
    flight_cost: float = 0,
    hotel_cost_per_night: float = 0,
) -> str:
    """Calculate estimated trip budget using real prices when available."""

    # Budget multipliers for estimated categories
    multipliers = {
        "budget": 0.6,
        "medium": 1.0,
        "luxury": 2.5,
    }
    mult = multipliers.get(budget_level, 1.0)

    # --- Flights ---
    flights_total = float(flight_cost) * travelers if flight_cost else 0

    # --- Accommodation ---
    if hotel_cost_per_night and float(hotel_cost_per_night) > 0:
        accommodation_total = float(hotel_cost_per_night) * days
    else:
        accommodation_total = int(3000 * mult) * days  # estimate per night

    # --- Food (estimated) ---
    food_daily = int(1500 * mult)
    food_total = food_daily * days * travelers

    # --- Transport (local, estimated) ---
    transport_daily = int(800 * mult)
    transport_total = transport_daily * days

    # --- Activities (estimated) ---
    activities_daily = int(1200 * mult)
    activities_total = activities_daily * days

    # --- Miscellaneous (estimated) ---
    misc_daily = int(500 * mult)
    misc_total = misc_daily * days

    subtotal = (
        flights_total
        + accommodation_total
        + food_total
        + transport_total
        + activities_total
        + misc_total
    )

    # 10% emergency buffer
    buffer_amount = round(subtotal * 0.10)
    total_with_buffer = subtotal + buffer_amount

    # Budget comparison
    budget_limit = float(budget_limit) if budget_limit else 0
    within_budget = total_with_buffer <= budget_limit if budget_limit > 0 else True
    remaining = budget_limit - total_with_buffer if budget_limit > 0 else 0
    percentage_used = round((total_with_buffer / budget_limit) * 100, 1) if budget_limit > 0 else 0

    # Recommendations
    recommendations = []
    if budget_limit > 0:
        if not within_budget:
            recommendations.append("⚠️ Budget exceeded! Consider these options:")
            if flights_total > accommodation_total:
                recommendations.append("- Look for budget airlines or alternative dates")
                recommendations.append("- Consider train travel for nearby destinations")
            else:
                recommendations.append("- Consider hostels, Airbnb, or budget hotels")
                recommendations.append("- Look for stays slightly outside the main area")
            recommendations.append("- Cut activities/dining to essentials")
        elif percentage_used > 85:
            recommendations.append("💡 Budget is tight — keep a buffer for emergencies")
        elif percentage_used < 60:
            recommendations.append("✅ You have room in your budget for upgrades or premium experiences")
        else:
            recommendations.append("✅ Budget looks good! Trip is well-planned within limits")
    else:
        recommendations.append("💡 No budget limit specified — showing estimated costs")

    recommendations += [
        "Book flights 2-3 weeks in advance for best prices",
        "Try street food for authentic and cheap meals",
    ]

    result = {
        "destination": destination,
        "duration_days": days,
        "travelers": travelers,
        "budget_level": budget_level,
        "breakdown": {
            "flights": round(flights_total),
            "accommodation": round(accommodation_total),
            "food": round(food_total),
            "activities": round(activities_total),
            "transport": round(transport_total),
            "miscellaneous": round(misc_total),
            "buffer_10_percent": round(buffer_amount),
        },
        "subtotal": round(subtotal),
        "total_with_buffer": round(total_with_buffer),
        "budget_limit": round(budget_limit),
        "remaining_budget": round(remaining),
        "within_budget": within_budget,
        "percentage_used": percentage_used,
        "currency": "INR",
        "recommendations": recommendations,
    }

    return json.dumps(result, ensure_ascii=False)


def itinerary_builder(
    destination: str,
    days: int = 3,
    interests: str = None,
    restaurants: Optional[list] = None,
    attractions: Optional[list] = None,
) -> str:
    """Build a day-by-day itinerary, grounded in real places when provided.

    `restaurants` and `attractions` are optional lists of names (strings) from
    earlier tool results; they are rotated across the days so each slot
    references a real place instead of a generic placeholder.
    """
    restaurants = [r for r in (restaurants or []) if r]
    attractions = [a for a in (attractions or []) if a]

    def _pick(items: list, index: int, fallback: str) -> str:
        if not items:
            return fallback
        return items[index % len(items)]

    itinerary = {
        "destination": destination,
        "duration": f"{days} days",
        "interests": interests or "General sightseeing",
        "days": []
    }

    for day in range(1, days + 1):
        lunch_place = _pick(restaurants, (day - 1) * 2, "a well-rated local restaurant")
        dinner_place = _pick(restaurants, (day - 1) * 2 + 1, "a popular dinner spot")
        morning_sight = _pick(attractions, (day - 1) * 2, f"{destination}'s top sights")
        afternoon_sight = _pick(attractions, (day - 1) * 2 + 1, "a local cultural experience")

        day_plan = {
            "day": day,
            "theme": f"Explore {destination} - Day {day}",
            "morning": [
                {"time": "08:00", "activity": "Breakfast at hotel"},
                {"time": "09:00", "activity": f"Visit {morning_sight}"},
                {"time": "11:00", "activity": "Local market exploration"}
            ],
            "afternoon": [
                {"time": "12:30", "activity": f"Lunch at {lunch_place}"},
                {"time": "14:00", "activity": f"Explore {afternoon_sight}"},
                {"time": "16:00", "activity": "Shopping / Leisure time"}
            ],
            "evening": [
                {"time": "18:00", "activity": "Sunset viewpoint"},
                {"time": "19:30", "activity": f"Dinner at {dinner_place}"},
                {"time": "21:00", "activity": "Night walk / Entertainment"}
            ],
            "estimated_cost": 3000 + (day * 500)
        }
        itinerary["days"].append(day_plan)

    return json.dumps(itinerary, ensure_ascii=False)
