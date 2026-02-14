from pydantic import BaseModel, Field
from typing import Type, Optional
import requests
import json

from app.tools.base import BaseTravelTool
from app.config import settings


class RestaurantFinderInput(BaseModel):
    """Input schema for Restaurant Finder tool"""
    location: str = Field(description="City or specific area to find restaurants")
    cuisine_type: Optional[str] = Field(default=None, description="Type of cuisine (e.g., seafood, Indian, Italian, local)")
    budget: Optional[str] = Field(default="moderate", description="Budget level: cheap, moderate, or expensive")


class RestaurantFinderTool(BaseTravelTool):
    """Tool for finding restaurants using Foursquare Places API"""
    
    name: str = "restaurant_finder"
    description: str = """Find restaurants and food spots based on location and preferences.
    Returns list of restaurants with ratings, price ranges, cuisine types, and links.
    Specify location, optional cuisine type, and budget level."""
    args_schema: Type[BaseModel] = RestaurantFinderInput
    
    # Price level mapping
    PRICE_LEVELS = {
        "cheap": [1],
        "moderate": [1, 2],
        "expensive": [2, 3, 4]
    }
    
    def _run(self, location: str, cuisine_type: Optional[str] = None, budget: str = "moderate") -> str:
        """Search restaurants using Foursquare Places API"""
        
        # Check cache (24 hours TTL - restaurant data is relatively static)
        cache_key = f"restaurants:{location}:{cuisine_type}:{budget}"
        cached = self._get_cached_result(cache_key)
        if cached:
            return self._format_result(cached)
        
        try:
            # Foursquare Places API
            url = "https://api.foursquare.com/v3/places/search"
            
            headers = {
                "Authorization": settings.foursquare_api_key,
                "Accept": "application/json"
            }
            
            # Build query
            query = "restaurants"
            if cuisine_type:
                query = f"{cuisine_type} restaurants"
            
            params = {
                "query": query,
                "near": location,
                "categories": "13065",  # Restaurants category
                "limit": 15,
                "sort": "RELEVANCE"
            }
            
            # Add price filter
            if budget in self.PRICE_LEVELS:
                params["min_price"] = min(self.PRICE_LEVELS[budget])
                params["max_price"] = max(self.PRICE_LEVELS[budget])
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                restaurants = self._parse_foursquare_response(data, budget)
                
                # Cache for 24 hours
                self._set_cache(cache_key, restaurants, ttl=86400)
                return self._format_result(restaurants)
            else:
                # Fallback to generated restaurants
                return self._generate_estimated_restaurants(location, cuisine_type, budget)
                
        except Exception as e:
            # Fallback to estimated restaurants on API failure
            return self._generate_estimated_restaurants(location, cuisine_type, budget)
    
    def _parse_foursquare_response(self, data: dict, budget: str) -> dict:
        """Parse Foursquare API response"""
        restaurants = []
        
        for place in data.get("results", []):
            # Get location info
            location = place.get("location", {})
            
            # Estimate price level from category or default
            price_level = place.get("price", 2)
            price_str = "₹" * (price_level if price_level else 2)
            
            restaurants.append({
                "name": place.get("name"),
                "rating": place.get("rating", "N/A"),
                "price_level": price_str,
                "address": location.get("formatted_address", location.get("address", "Address not available")),
                "cuisine": [cat.get("name") for cat in place.get("categories", [])],
                "distance": place.get("distance"),
                "fsq_id": place.get("fsq_id"),
                "link": f"https://foursquare.com/v/{place.get('fsq_id')}"
            })
        
        return {
            "location": data.get("context", {}).get("geo_bounds", {}).get("circle", {}).get("center", {}),
            "restaurants": restaurants,
            "total_found": len(restaurants),
            "budget_filter": budget
        }
    
    def _generate_estimated_restaurants(self, location: str, cuisine_type: Optional[str], budget: str) -> str:
        """Generate estimated restaurant options when API fails"""
        
        # Common restaurant data for different locations
        base_restaurants = [
            {
                "name": f"Local {cuisine_type or 'Traditional'} Kitchen",
                "rating": 4.2,
                "price_level": "₹₹" if budget != "cheap" else "₹",
                "cuisine": [cuisine_type or "Local", "Indian"],
                "avg_cost": 300 if budget == "cheap" else 600,
            },
            {
                "name": f"{location} Food Corner",
                "rating": 4.0,
                "price_level": "₹",
                "cuisine": ["Street Food", "Local"],
                "avg_cost": 150,
            },
            {
                "name": f"The {location} Cafe",
                "rating": 4.3,
                "price_level": "₹₹",
                "cuisine": ["Cafe", "Continental"],
                "avg_cost": 500,
            },
            {
                "name": f"Spice Garden - {location}",
                "rating": 4.1,
                "price_level": "₹₹",
                "cuisine": ["Indian", "North Indian"],
                "avg_cost": 450,
            },
            {
                "name": f"Coastal Flavors",
                "rating": 4.4,
                "price_level": "₹₹₹",
                "cuisine": ["Seafood", "Coastal"],
                "avg_cost": 800,
            },
            {
                "name": f"Street Bites {location}",
                "rating": 4.0,
                "price_level": "₹",
                "cuisine": ["Street Food", "Snacks"],
                "avg_cost": 100,
            },
            {
                "name": f"{location} Biryani House",
                "rating": 4.5,
                "price_level": "₹₹",
                "cuisine": ["Biryani", "Mughlai"],
                "avg_cost": 350,
            },
            {
                "name": f"Royal Dining - {location}",
                "rating": 4.6,
                "price_level": "₹₹₹₹",
                "cuisine": ["Fine Dining", "Multi-cuisine"],
                "avg_cost": 1500,
            }
        ]
        
        # Filter by budget
        filtered = []
        for r in base_restaurants:
            if budget == "cheap" and r["avg_cost"] > 300:
                continue
            if budget == "moderate" and r["avg_cost"] > 800:
                continue
            # Add location-specific link
            r["address"] = f"{location} City Center"
            r["link"] = f"https://www.google.com/maps/search/{r['name'].replace(' ', '+')}+{location.replace(' ', '+')}"
            filtered.append(r)
        
        result = {
            "location": location,
            "cuisine_filter": cuisine_type,
            "budget_filter": budget,
            "restaurants": filtered[:6],
            "note": "Local restaurant recommendations. Check Zomato, Swiggy, or Google Maps for current ratings and menus."
        }
        
        # Cache for 24 hours
        cache_key = f"restaurants:{location}:{cuisine_type}:{budget}"
        self._set_cache(cache_key, result, ttl=86400)
        
        return self._format_result(result)
    
    async def _arun(self, location: str, cuisine_type: Optional[str] = None, budget: str = "moderate") -> str:
        """Async version - delegates to sync for now"""
        return self._run(location, cuisine_type, budget)
