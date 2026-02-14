"""Simple tool implementations with LangChain compatibility"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Callable
import json
import requests
from langchain.tools import Tool

from app.services.redis_service import redis_service
from app.config import settings


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
    cache_key = f"google_search:{query}:{num_results}"
    
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
    
    cache_key = f"flights:{origin}:{destination}:{date}:{return_date}:{passengers}"
    
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
    
    cache_key = f"hotels:{city}:{check_in}:{check_out}:{guests}"
    
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
    
    cache_key = f"restaurants:{city}:{cuisine}:{budget}"
    
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
    
    result = {
        "city": city,
        "cuisine_filter": cuisine or "All",
        "budget": budget,
        "restaurants": restaurants
    }
    
    _set_cache(cache_key, result, ttl=1800)
    return json.dumps(result, ensure_ascii=False)


def budget_calculator(destination: str, days: int = 3, travelers: int = 2, budget_level: str = "medium") -> str:
    """Calculate estimated trip budget"""
    
    # Budget multipliers
    multipliers = {
        "budget": 0.6,
        "medium": 1.0,
        "luxury": 2.5
    }
    mult = multipliers.get(budget_level, 1.0)
    
    # Base daily costs (INR)
    base_costs = {
        "accommodation": 3000,
        "food": 1500,
        "transport": 800,
        "activities": 1200,
        "miscellaneous": 500
    }
    
    daily_costs = {k: int(v * mult) for k, v in base_costs.items()}
    daily_total = sum(daily_costs.values())
    
    result = {
        "destination": destination,
        "duration_days": days,
        "travelers": travelers,
        "budget_level": budget_level,
        "daily_breakdown": daily_costs,
        "daily_total_per_person": daily_total,
        "total_per_person": daily_total * days,
        "total_for_group": daily_total * days * travelers,
        "currency": "INR",
        "tips": [
            "Book flights 2-3 weeks in advance for best prices",
            "Consider staying in hostels or Airbnb for budget travel",
            "Use local transport like metro and buses",
            "Try street food for authentic and cheap meals"
        ]
    }
    
    return json.dumps(result, ensure_ascii=False)


def itinerary_builder(destination: str, days: int = 3, interests: str = None) -> str:
    """Build a day-by-day itinerary"""
    
    itinerary = {
        "destination": destination,
        "duration": f"{days} days",
        "interests": interests or "General sightseeing",
        "days": []
    }
    
    for day in range(1, days + 1):
        day_plan = {
            "day": day,
            "theme": f"Explore {destination} - Day {day}",
            "morning": [
                {"time": "08:00", "activity": "Breakfast at hotel"},
                {"time": "09:00", "activity": f"Visit famous landmark #{day}"},
                {"time": "11:00", "activity": "Local market exploration"}
            ],
            "afternoon": [
                {"time": "12:30", "activity": "Lunch at local restaurant"},
                {"time": "14:00", "activity": f"Cultural experience #{day}"},
                {"time": "16:00", "activity": "Shopping / Leisure time"}
            ],
            "evening": [
                {"time": "18:00", "activity": "Sunset viewpoint"},
                {"time": "19:30", "activity": "Dinner"},
                {"time": "21:00", "activity": "Night walk / Entertainment"}
            ],
            "estimated_cost": 3000 + (day * 500)
        }
        itinerary["days"].append(day_plan)
    
    return json.dumps(itinerary, ensure_ascii=False)


def get_all_tools():
    """Return list of all available LangChain-compatible tools"""
    
    # Wrapper functions that accept a single string input
    def _google_search_wrapper(query: str) -> str:
        return google_search(query=query)
    
    def _flight_search_wrapper(input_str: str) -> str:
        try:
            params = json.loads(input_str) if input_str.strip().startswith("{") else {"origin": "Delhi", "destination": input_str}
            return flight_search(**params)
        except:
            return flight_search(origin="Delhi", destination=input_str)
    
    def _hotel_search_wrapper(input_str: str) -> str:
        try:
            params = json.loads(input_str) if input_str.strip().startswith("{") else {"city": input_str}
            return hotel_search(**params)
        except:
            return hotel_search(city=input_str)
    
    def _restaurant_finder_wrapper(input_str: str) -> str:
        try:
            params = json.loads(input_str) if input_str.strip().startswith("{") else {"city": input_str}
            return restaurant_finder(**params)
        except:
            return restaurant_finder(city=input_str)
    
    def _budget_calculator_wrapper(input_str: str) -> str:
        try:
            params = json.loads(input_str) if input_str.strip().startswith("{") else {"destination": input_str}
            return budget_calculator(**params)
        except:
            return budget_calculator(destination=input_str)
    
    def _itinerary_builder_wrapper(input_str: str) -> str:
        try:
            params = json.loads(input_str) if input_str.strip().startswith("{") else {"destination": input_str}
            return itinerary_builder(**params)
        except:
            return itinerary_builder(destination=input_str)
    
    return [
        Tool.from_function(
            func=_google_search_wrapper,
            name="google_search",
            description="Search the web for travel information. Input: search query string."
        ),
        Tool.from_function(
            func=_flight_search_wrapper,
            name="flight_search",
            description="Search for flights. Input: JSON with origin, destination, date."
        ),
        Tool.from_function(
            func=_hotel_search_wrapper,
            name="hotel_search",
            description="Search for hotels. Input: JSON with city, check_in, check_out."
        ),
        Tool.from_function(
            func=_restaurant_finder_wrapper,
            name="restaurant_finder",
            description="Find restaurants. Input: JSON with city, cuisine, budget."
        ),
        Tool.from_function(
            func=_budget_calculator_wrapper,
            name="budget_calculator",
            description="Calculate trip budget. Input: JSON with destination, days, travelers."
        ),
        Tool.from_function(
            func=_itinerary_builder_wrapper,
            name="itinerary_builder",
            description="Build day-by-day itinerary. Input: JSON with destination, days."
        )
    ]
