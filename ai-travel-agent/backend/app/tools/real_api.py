"""Real API implementations for travel planning tools"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)



# Validates key and returns it. Returns None if invalid.
def _get_key(env_var_name):
    key = os.getenv(env_var_name)
    if not key or key.strip() == "" or "your_" in key.lower():
        return None
    return key

# Simple airport code mapper
def _get_airport_code(city_name: str) -> str:
    city_map = {
        "delhi": "DEL",
        "new delhi": "DEL",
        "mumbai": "BOM",
        "bombay": "BOM",
        "bangalore": "BLR",
        "bengaluru": "BLR",
        "goa": "GOI",
        "chennai": "MAA",
        "madras": "MAA",
        "kolkata": "CCU",
        "calcutta": "CCU",
        "hyderabad": "HYD",
        "pune": "PNQ",
        "ahmedabad": "AMD",
        "jaipur": "JAI",
        "kochi": "COK",
        "cochin": "COK",
        "kerala": "COK"
    }
    cleaned = city_name.lower().strip()
    return city_map.get(cleaned, city_name.upper()[:3]) # Fallback to first 3 chars


def search_flights_serpapi(origin: str, destination: str, date: str = None, return_date: str = None, passengers: int = 1) -> dict:
    """
    Search for real flights using SerpAPI Google Flights
    Returns flights data or mock data with error reason
    """
    try:
        import requests
        
        serpapi_key = _get_key("SERPAPI_KEY")
        if not serpapi_key:
            return get_mock_flights(origin, destination, date, passengers, reason="API Key Missing")
        
        # Format date
        # Format and validate date
        current_date = datetime.now().strftime("%Y-%m-%d")
        if not date or date < current_date:
            date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            logger.warning(f"Auto-corrected past/missing date to: {date}")
        
        # Get airport codes
        origin_code = _get_airport_code(origin)
        dest_code = _get_airport_code(destination)
        
        params = {
            "engine": "google_flights",
            "departure_id": origin_code,
            "arrival_id": dest_code,
            "outbound_date": date,
            "adults": passengers,
            "currency": "INR",
            "hl": "en",
            "api_key": serpapi_key
        }
        
        if return_date:
            params["return_date"] = return_date
            params["type"] = 1 # Force Round Trip
        else:
            # If no return date, force One-way to avoid 400 error
            params["type"] = 2
        
        try:
            with open("/app/debug_params.txt", "w") as f:
                f.write(f"PARAMS: {json.dumps(params)}\n")
        except:
            pass
            
        logger.info(f"Calling SerpAPI with params: {json.dumps(params)}")
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"SerpAPI Error {response.status_code}: {response.text}")
            # If 400 error, return mock data instead of crashing
            return get_mock_flights(origin, destination, date, passengers, reason=f"API Error {response.status_code}: {response.json().get('error', 'Invalid Parameters')}")
            
        data = response.json()
        
        # Parse results
        flights = []
        flight_list = data.get("best_flights", []) or data.get("other_flights", [])
        
        if not flight_list:
            logger.warning(f"SerpAPI successful but no flights found. Keys in data: {data.keys()}")
            return get_mock_flights(origin, destination, date, passengers, reason="No Flights Found")
        
        for flight_data in flight_list[:5]:
            try:
                flight_info = flight_data.get("flights", [{}])[0]
                total_duration = flight_data.get("total_duration", 0)
                
                # Check for booking token or link
                # Google Flights usually doesn't give a direct deep link in the basic API, 
                # but we can construct a search URL
                google_flights_link = f"https://www.google.com/travel/flights?q=flights+from+{origin_code}+to+{dest_code}+on+{date}"
                if return_date:
                    google_flights_link += f"+returning+on+{return_date}"
                
                # Make it a clickable generic link if specific deep link fails (which it often does in basic tiers)
                booking_link = google_flights_link
                
                flights.append({
                    "airline": flight_info.get("airline", "Unknown"),
                    "flight_number": flight_info.get("flight_number", "N/A"),
                    "departure": flight_info.get("departure_airport", {}).get("time", "N/A"),
                    "arrival": flight_info.get("arrival_airport", {}).get("time", "N/A"),
                    "duration": f"{total_duration // 60}h {total_duration % 60}m" if total_duration else "N/A",
                    "price": flight_data.get("price", 0),
                    "currency": "INR",
                    "class": "Economy",
                    "booking_link": booking_link
                })
            except Exception:
                continue
        
        if not flights:
            return get_mock_flights(origin, destination, date, passengers, reason="Parse Error")
        
        return {
            "origin": origin,
            "destination": destination,
            "date": date,
            "return_date": return_date,
            "passengers": passengers,
            "flights": flights,
            "source": "SerpAPI - Real Data"
        }
        
    except Exception as e:
        logger.error(f"SerpAPI error: {e}")
        return get_mock_flights(origin, destination, date, passengers, reason=f"API Error: {str(e)}")


def get_mock_flights(origin: str, destination: str, date: str = None, passengers: int = 1, reason: str = "API not configured") -> dict:
    """Fallback mock flight data"""
    # ... (mock data implementation)
    flights = [
        {
            "airline": "IndiGo (Demo)",
            "flight_number": "6E-2001",
            "departure": "06:00",
            "arrival": "08:15",
            "duration": "2h 15m",
            "price": 4500,
            "currency": "INR",
            "class": "Economy",
            "booking_link": f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}+on+{date}"
        },
        {
            "airline": "Air India (Demo)",
            "flight_number": "AI-101",
            "departure": "09:30",
            "arrival": "11:45",
            "duration": "2h 15m",
            "price": 5200,
            "currency": "INR",
            "class": "Economy",
            "booking_link": f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}+on+{date}"
        }
    ]
    
    return {
        "origin": origin,
        "destination": destination,
        "date": date or "Flexible dates",
        "passengers": passengers,
        "flights": flights,
        "source": f"Mock Data ({reason})"
    }


def search_hotels_rapidapi(city: str, check_in: str = None, check_out: str = None, guests: int = 2) -> dict:
    """Search for real hotels using RapidAPI Booking.com"""
    try:
        import requests
        
        rapidapi_key = _get_key("RAPIDAPI_KEY")
        if not rapidapi_key:
            return get_mock_hotels(city, check_in, check_out, guests, reason="API Key Missing")
        
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
        }
        
        # Format dates
        if not check_in:
            check_in = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        if not check_out:
            check_out = (datetime.now() + timedelta(days=16)).strftime("%Y-%m-%d")
        
        # 1. Search for destination ID
        search_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchDestination"
        
        # Improve city search: prioritize "City, India" to avoid "Goa" -> "Genoa" mixups
        search_queries = []
        
        # 1. Try "City, India" first (Strongest match for this context)
        if "india" not in city.lower():
            search_queries.append(f"{city}, India")
            
        # 2. Try original query
        search_queries.append(city)
        
        # 3. Try stripping extra details if comma exists
        if "," in city:
            search_queries.append(city.split(",")[0].strip())
            
        dest_data = None
        for query in search_queries:
            logger.info(f"Searching for hotels in: {query}")
            try:
                dest_response = requests.get(search_url, headers=headers, params={"query": query}, timeout=10)
                if dest_response.status_code == 200:
                    data = dest_response.json()
                    if data and data.get("data"):
                        # Verify it's actually India if we asked for India
                        # (Basic check, though API usually respects the query)
                        dest_data = data
                        break
            except:
                continue
        
        if not dest_data or not dest_data.get("data"):
            return get_mock_hotels(city, check_in, check_out, guests, reason="City Not Found")
            
        dest_id = dest_data["data"][0]["dest_id"]
        search_type = dest_data["data"][0]["search_type"]
        
        # 2. Search hotels
        hotels_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels"
        hotel_params = {
            "dest_id": dest_id,
            "search_type": search_type,
            "arrival_date": check_in,
            "departure_date": check_out,
            "adults": guests,
            "room_qty": 1,
            "page_number": 1,
            "units": "metric",
            "temperature_unit": "c",
            "languagecode": "en-us",
            "currency_code": "INR"
        }
        
        hotels_response = requests.get(hotels_url, headers=headers, params=hotel_params, timeout=15)
        hotels_response.raise_for_status()
        data = hotels_response.json()
        
        hotels = []
        if not data.get("data") or not data["data"].get("hotels"):
             return get_mock_hotels(city, check_in, check_out, guests, reason="No Hotels Found")
             
        # LOG RAW HOTEL DATA FOR DEBUGGING
        if len(data["data"]["hotels"]) > 0:
            logger.info(f"FIRST HOTEL RAW DATA: {json.dumps(data['data']['hotels'][0])}")

        for hotel in data["data"]["hotels"][:5]:
            try:
                property_data = hotel.get("property", {})
                
                # Check different fields for booking link
                # Sometimes it's in a different place or constructed
                booking_link = "https://www.booking.com"
                
                hotels.append({
                    "name": property_data.get("name", "Unknown Hotel"),
                    "rating": property_data.get("reviewScore", 0),
                    "price_per_night": int(property_data.get("priceBreakdown", {}).get("grossPrice", {}).get("value", 0)),
                    "currency": property_data.get("priceBreakdown", {}).get("grossPrice", {}).get("currency", "INR"),
                    "location": city,
                    "amenities": [],
                    "booking_link": booking_link
                })
            except Exception:
                continue
        
        if not hotels:
            return get_mock_hotels(city, check_in, check_out, guests, reason="Parse Error")
        
        return {
            "city": city,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "hotels": hotels,
            "source": "RapidAPI Booking.com - Real Data"
        }
        
    except Exception as e:
        logger.error(f"RapidAPI hotel search error: {e}")
        return get_mock_hotels(city, check_in, check_out, guests, reason=f"API Error: {str(e)}")


def get_mock_hotels(city: str, check_in: str = None, check_out: str = None, guests: int = 2, reason: str = "API not configured") -> dict:
    """Fallback mock hotel data"""
    hotels = [
        {
            "name": f"Grand Hotel {city} (Demo)",
            "rating": 4.5,
            "price_per_night": 3500,
            "currency": "INR",
            "location": f"{city} City Center",
            "amenities": ["Free WiFi", "Pool", "Gym", "Restaurant"],
            "booking_link": "#"
        },
        {
            "name": f"Comfort Inn {city} (Demo)",
            "rating": 4.0,
            "price_per_night": 2500,
            "currency": "INR",
            "location": f"{city} Downtown",
            "amenities": ["Free WiFi", "Breakfast", "AC"],
            "booking_link": "#"
        }
    ]
    
    return {
        "city": city,
        "check_in": check_in or "Flexible dates",
        "check_out": check_out or "Flexible dates",
        "guests": guests,
        "hotels": hotels,
        "source": f"Mock Data ({reason})"
    }


def search_restaurants_foursquare(location: str, cuisine: str = None, budget: str = "moderate") -> dict:
    """Search for real restaurants using Foursquare Places API"""
    try:
        import requests
        
        foursquare_key = _get_key("FOURSQUARE_API_KEY")
        if not foursquare_key:
            return get_mock_restaurants(location, cuisine, budget, reason="API Key Missing")
        
        url = "https://api.foursquare.com/v3/places/search"
        headers = {
            "Accept": "application/json",
            "Authorization": foursquare_key
        }
        
        params = {
            "near": location,
            "categories": "13065",  # Restaurant category
            "limit": 10
        }
        
        if cuisine and cuisine.lower() != "any":
            params["query"] = cuisine
        
        logger.info(f"Searching for restaurants in: {location}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        restaurants = []
        for place in data.get("results", [])[:8]:
            try:
                # Convert rating from 10-scale to 5-scale
                rating = place.get("rating", 0) / 2 if "rating" in place else 4.0
                
                restaurants.append({
                    "name": place.get("name", "Unknown Restaurant"),
                    "cuisine": place.get("categories", [{}])[0].get("name", "Restaurant") if place.get("categories") else "Restaurant",
                    "rating": round(rating, 1),
                    "price_level": 2,
                    "address": place.get("location", {}).get("address", ""),
                    "popular_dishes": []
                })
            except Exception:
                continue
        
        if not restaurants:
            return get_mock_restaurants(location, cuisine, budget, reason="No Restaurants Found")
        
        return {
            "location": location,
            "cuisine": cuisine or "all",
            "budget": budget,
            "restaurants": restaurants,
            "source": "Foursquare - Real Data"
        }
        
    except Exception as e:
        logger.error(f"Foursquare restaurant search error: {e}")
        return get_mock_restaurants(location, cuisine, budget, reason=f"API Error: {str(e)}")


def get_mock_restaurants(location: str, cuisine: str = None, budget: str = "moderate", reason: str = "API not configured") -> dict:
    """Fallback mock restaurant data"""
    restaurants = [
        {
            "name": f"The Spice Route {location} (Demo)",
            "cuisine": cuisine or "Indian",
            "rating": 4.5,
            "price_level": 2,
            "address": f"{location} Main Street",
            "popular_dishes": ["Butter Chicken", "Biryani"]
        },
        {
            "name": f"Coastal Kitchen {location} (Demo)",
            "cuisine": "Seafood",
            "rating": 4.3,
            "price_level": 3,
            "address": f"{location} Beach Road",
            "popular_dishes": ["Fish Curry", "Prawns"]
        }
    ]
    
    return {
        "location": location,
        "cuisine": cuisine or "all",
        "budget": budget,
        "restaurants": restaurants,
        "source": f"Mock Data ({reason})"
    }
