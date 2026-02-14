from pydantic import BaseModel, Field
from typing import Type, Optional, List
import json
from datetime import datetime, timedelta

from app.tools.base import BaseTravelTool


class ItineraryBuilderInput(BaseModel):
    """Input schema for Itinerary Builder tool"""
    destination: str = Field(description="Travel destination")
    duration_days: int = Field(description="Number of days for the trip")
    start_date: str = Field(description="Trip start date in YYYY-MM-DD format")
    flights: str = Field(description="Selected flight details as JSON string")
    hotels: str = Field(description="Selected hotel details as JSON string")
    restaurants: str = Field(description="Recommended restaurants as JSON string")
    preferences: str = Field(description="User preferences (e.g., food-focused, adventure, relaxation)")
    budget: float = Field(description="Total budget for the trip in INR")


class ItineraryBuilderTool(BaseTravelTool):
    """Tool for building structured day-by-day itineraries"""
    
    name: str = "itinerary_builder"
    description: str = """Build a structured day-by-day itinerary from collected travel information.
    Takes flights, hotels, restaurants, and preferences to create a complete trip plan.
    Returns detailed daily schedule with activities, times, costs, and booking links."""
    args_schema: Type[BaseModel] = ItineraryBuilderInput
    
    # Destination-specific attractions database
    ATTRACTIONS = {
        "goa": [
            {"name": "Baga Beach", "type": "beach", "duration": "3-4 hours", "cost": 0},
            {"name": "Aguada Fort", "type": "historical", "duration": "2 hours", "cost": 50},
            {"name": "Dudhsagar Falls", "type": "nature", "duration": "Full day", "cost": 500},
            {"name": "Old Goa Churches", "type": "historical", "duration": "3 hours", "cost": 0},
            {"name": "Anjuna Flea Market", "type": "shopping", "duration": "2-3 hours", "cost": 0},
            {"name": "Calangute Beach", "type": "beach", "duration": "3-4 hours", "cost": 0},
            {"name": "Chapora Fort", "type": "historical", "duration": "1.5 hours", "cost": 0},
            {"name": "Spice Plantation Tour", "type": "nature", "duration": "3 hours", "cost": 400},
            {"name": "Casino Cruise", "type": "entertainment", "duration": "4 hours", "cost": 2000},
            {"name": "Water Sports at Candolim", "type": "adventure", "duration": "2-3 hours", "cost": 800}
        ],
        "mumbai": [
            {"name": "Gateway of India", "type": "historical", "duration": "1-2 hours", "cost": 0},
            {"name": "Marine Drive", "type": "sightseeing", "duration": "2 hours", "cost": 0},
            {"name": "Elephanta Caves", "type": "historical", "duration": "4 hours", "cost": 250},
            {"name": "Siddhivinayak Temple", "type": "religious", "duration": "2 hours", "cost": 0},
            {"name": "Juhu Beach", "type": "beach", "duration": "2-3 hours", "cost": 0},
            {"name": "Chhatrapati Shivaji Terminus", "type": "historical", "duration": "1 hour", "cost": 0},
            {"name": "Colaba Causeway", "type": "shopping", "duration": "3 hours", "cost": 0},
            {"name": "Haji Ali Dargah", "type": "religious", "duration": "1.5 hours", "cost": 0}
        ],
        "default": [
            {"name": "City Center Tour", "type": "sightseeing", "duration": "3 hours", "cost": 200},
            {"name": "Local Market Visit", "type": "shopping", "duration": "2 hours", "cost": 0},
            {"name": "Historical Monument", "type": "historical", "duration": "2 hours", "cost": 100},
            {"name": "Nature Walk/Park", "type": "nature", "duration": "2 hours", "cost": 50},
            {"name": "Local Temple/Shrine", "type": "religious", "duration": "1 hour", "cost": 0}
        ]
    }
    
    def _run(
        self,
        destination: str,
        duration_days: int,
        start_date: str,
        flights: str,
        hotels: str,
        restaurants: str,
        preferences: str,
        budget: float
    ) -> str:
        """Build comprehensive day-by-day itinerary"""
        
        try:
            # Parse JSON inputs
            flights_data = self._parse_json_input(flights)
            hotels_data = self._parse_json_input(hotels)
            restaurants_data = self._parse_json_input(restaurants)
            
            # Extract list data
            flight_list = flights_data.get("flights", []) if isinstance(flights_data, dict) else flights_data
            hotel_list = hotels_data.get("hotels", []) if isinstance(hotels_data, dict) else hotels_data
            restaurant_list = restaurants_data.get("restaurants", []) if isinstance(restaurants_data, dict) else restaurants_data
            
            # Calculate dates
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
            except:
                start = datetime.now() + timedelta(days=7)
            
            # Get attractions for destination
            dest_lower = destination.lower()
            attractions = self.ATTRACTIONS.get(dest_lower, self.ATTRACTIONS["default"])
            
            # Build itinerary
            itinerary = {
                "destination": destination,
                "duration_days": duration_days,
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": (start + timedelta(days=duration_days - 1)).strftime("%Y-%m-%d"),
                "preferences": preferences,
                "budget": budget,
                "summary": {
                    "flight": flight_list[0] if flight_list else {"note": "Book flights separately"},
                    "accommodation": hotel_list[0] if hotel_list else {"note": "Book hotel separately"}
                },
                "daily_plan": [],
                "booking_links": self._generate_booking_links(destination, flight_list, hotel_list)
            }
            
            # Build day-by-day plan
            for day in range(1, duration_days + 1):
                current_date = start + timedelta(days=day - 1)
                
                day_plan = self._build_day_plan(
                    day=day,
                    date=current_date,
                    duration=duration_days,
                    attractions=attractions,
                    restaurants=restaurant_list,
                    preferences=preferences,
                    destination=destination
                )
                
                itinerary["daily_plan"].append(day_plan)
            
            # Calculate total estimated cost
            total_cost = self._calculate_total_cost(
                flights=flight_list,
                hotels=hotel_list,
                daily_plans=itinerary["daily_plan"]
            )
            itinerary["total_estimated_cost"] = total_cost
            itinerary["budget_status"] = "Within Budget ✅" if total_cost <= budget else "Over Budget ⚠️"
            
            return self._format_result(itinerary)
            
        except Exception as e:
            return self._format_error(f"Itinerary building failed: {str(e)}")
    
    def _parse_json_input(self, data: str) -> dict:
        """Safely parse JSON input"""
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"items": data}
        try:
            return json.loads(data)
        except:
            return {}
    
    def _build_day_plan(
        self,
        day: int,
        date: datetime,
        duration: int,
        attractions: list,
        restaurants: list,
        preferences: str,
        destination: str
    ) -> dict:
        """Build plan for a single day"""
        
        pref_lower = preferences.lower()
        is_food_focused = "food" in pref_lower
        is_adventure = "adventure" in pref_lower
        is_relaxation = "relax" in pref_lower
        
        # Select attractions based on day and preferences
        attraction_idx = (day - 1) * 2
        day_attractions = attractions[attraction_idx:attraction_idx + 2] if attraction_idx < len(attractions) else attractions[:2]
        
        # Get restaurants for the day
        restaurant_idx = (day - 1) * 3
        day_restaurants = restaurants[restaurant_idx:restaurant_idx + 3] if restaurant_idx < len(restaurants) else restaurants[:3]
        
        day_plan = {
            "day": day,
            "date": date.strftime("%Y-%m-%d"),
            "day_name": date.strftime("%A"),
            "theme": self._get_day_theme(day, duration, preferences),
            "morning": [],
            "afternoon": [],
            "evening": [],
            "meals": {},
            "estimated_cost": 0
        }
        
        daily_cost = 0
        
        # Morning activities
        if day == 1:
            # Arrival day
            day_plan["morning"].append({
                "time": "Check-in",
                "activity": "Arrive and check into hotel",
                "location": "Hotel",
                "duration": "1-2 hours",
                "cost": 0,
                "notes": "Rest and freshen up after journey"
            })
        else:
            # Breakfast
            breakfast_spot = day_restaurants[0] if day_restaurants else {"name": "Hotel Restaurant"}
            day_plan["morning"].append({
                "time": "08:00 AM",
                "activity": "Breakfast",
                "location": breakfast_spot.get("name", "Local Cafe"),
                "duration": "1 hour",
                "cost": 300,
                "link": breakfast_spot.get("link")
            })
            daily_cost += 300
            day_plan["meals"]["breakfast"] = breakfast_spot
            
            # Morning attraction
            if day_attractions:
                attr = day_attractions[0]
                day_plan["morning"].append({
                    "time": "10:00 AM",
                    "activity": f"Visit {attr['name']}",
                    "location": attr["name"],
                    "duration": attr["duration"],
                    "cost": attr["cost"],
                    "type": attr["type"]
                })
                daily_cost += attr["cost"]
        
        # Afternoon activities
        # Lunch
        lunch_spot = day_restaurants[1] if len(day_restaurants) > 1 else {"name": "Local Restaurant"}
        day_plan["afternoon"].append({
            "time": "01:00 PM",
            "activity": "Lunch",
            "location": lunch_spot.get("name", "Local Restaurant"),
            "duration": "1.5 hours",
            "cost": 500 if is_food_focused else 400,
            "link": lunch_spot.get("link")
        })
        daily_cost += 500 if is_food_focused else 400
        day_plan["meals"]["lunch"] = lunch_spot
        
        # Afternoon exploration
        if is_relaxation:
            day_plan["afternoon"].append({
                "time": "03:00 PM",
                "activity": "Leisure time / Beach relaxation" if "beach" in destination.lower() or "goa" in destination.lower() else "Leisure time / Spa",
                "location": "Beach/Hotel",
                "duration": "3 hours",
                "cost": 0
            })
        elif len(day_attractions) > 1:
            attr = day_attractions[1]
            day_plan["afternoon"].append({
                "time": "03:00 PM",
                "activity": f"Explore {attr['name']}",
                "location": attr["name"],
                "duration": attr["duration"],
                "cost": attr["cost"],
                "type": attr["type"]
            })
            daily_cost += attr["cost"]
        
        # Evening activities
        day_plan["evening"].append({
            "time": "06:00 PM",
            "activity": "Sunset viewing / Evening walk",
            "location": f"{destination} waterfront/viewpoint",
            "duration": "1.5 hours",
            "cost": 0
        })
        
        # Dinner
        dinner_spot = day_restaurants[2] if len(day_restaurants) > 2 else {"name": "Popular Local Restaurant"}
        day_plan["evening"].append({
            "time": "08:00 PM",
            "activity": "Dinner",
            "location": dinner_spot.get("name", "Local Restaurant"),
            "duration": "2 hours",
            "cost": 800 if is_food_focused else 600,
            "link": dinner_spot.get("link"),
            "notes": "Try local specialties" if is_food_focused else None
        })
        daily_cost += 800 if is_food_focused else 600
        day_plan["meals"]["dinner"] = dinner_spot
        
        # Last day - departure
        if day == duration:
            day_plan["evening"].append({
                "time": "Late Evening",
                "activity": "Check-out and departure",
                "location": "Hotel/Airport",
                "duration": "2-3 hours",
                "cost": 0,
                "notes": "Allow buffer time for travel to airport/station"
            })
        
        day_plan["estimated_cost"] = daily_cost
        
        return day_plan
    
    def _get_day_theme(self, day: int, duration: int, preferences: str) -> str:
        """Get theme for the day"""
        if day == 1:
            return "Arrival & Orientation"
        if day == duration:
            return "Final Exploration & Departure"
        
        pref_lower = preferences.lower()
        if "food" in pref_lower:
            themes = ["Culinary Discovery", "Local Food Trail", "Seafood & Sunset", "Street Food Adventure"]
        elif "adventure" in pref_lower:
            themes = ["Adventure Day", "Outdoor Exploration", "Active Discovery", "Thrill & Excitement"]
        elif "relax" in pref_lower:
            themes = ["Beach & Relaxation", "Spa & Wellness", "Leisure Day", "Peaceful Retreat"]
        else:
            themes = ["Cultural Exploration", "Heritage & History", "Nature & Sightseeing", "Local Experience"]
        
        return themes[(day - 2) % len(themes)]
    
    def _calculate_total_cost(self, flights: list, hotels: list, daily_plans: list) -> float:
        """Calculate total estimated trip cost"""
        total = 0
        
        # Flight cost
        if flights:
            flight = flights[0]
            total += float(flight.get("price", 0))
        
        # Hotel cost
        if hotels:
            hotel = hotels[0]
            nights = len(daily_plans)
            price_per_night = float(hotel.get("price_per_night", hotel.get("total_price", 0)))
            if price_per_night > 0:
                total += price_per_night * nights
        
        # Daily expenses
        for day in daily_plans:
            total += day.get("estimated_cost", 0)
        
        return round(total, 2)
    
    def _generate_booking_links(self, destination: str, flights: list, hotels: list) -> dict:
        """Generate helpful booking links"""
        dest_encoded = destination.replace(" ", "+")
        
        return {
            "flights": {
                "skyscanner": f"https://www.skyscanner.co.in/transport/flights-to/{dest_encoded}",
                "makemytrip": f"https://www.makemytrip.com/flights/",
                "goibibo": "https://www.goibibo.com/flights/"
            },
            "hotels": {
                "booking": f"https://www.booking.com/searchresults.html?ss={dest_encoded}",
                "makemytrip": f"https://www.makemytrip.com/hotels/",
                "oyo": f"https://www.oyorooms.com/search?location={dest_encoded}"
            },
            "activities": {
                "tripadvisor": f"https://www.tripadvisor.in/Search?q={dest_encoded}",
                "viator": f"https://www.viator.com/searchResults/all?text={dest_encoded}"
            },
            "food": {
                "zomato": f"https://www.zomato.com/{destination.lower().replace(' ', '-')}/restaurants",
                "swiggy": "https://www.swiggy.com/"
            }
        }
    
    async def _arun(
        self,
        destination: str,
        duration_days: int,
        start_date: str,
        flights: str,
        hotels: str,
        restaurants: str,
        preferences: str,
        budget: float
    ) -> str:
        """Async version - delegates to sync"""
        return self._run(destination, duration_days, start_date, flights, hotels, restaurants, preferences, budget)
