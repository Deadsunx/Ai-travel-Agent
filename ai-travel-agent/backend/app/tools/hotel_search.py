from pydantic import BaseModel, Field
from typing import Type, Optional
import requests
import json

from app.tools.base import BaseTravelTool
from app.config import settings


class HotelSearchInput(BaseModel):
    """Input schema for Hotel Search tool"""
    destination: str = Field(description="City or location to search hotels")
    check_in: str = Field(description="Check-in date in YYYY-MM-DD format")
    check_out: str = Field(description="Check-out date in YYYY-MM-DD format")
    max_price: Optional[float] = Field(default=None, description="Maximum price per night in INR")


class HotelSearchTool(BaseTravelTool):
    """Tool for searching hotels and accommodations"""
    
    name: str = "hotel_search"
    description: str = """Search for hotels and accommodations with current prices.
    Returns list of hotels with prices, ratings, amenities, and booking links.
    Specify the destination city, check-in and check-out dates."""
    args_schema: Type[BaseModel] = HotelSearchInput
    
    def _run(self, destination: str, check_in: str, check_out: str, max_price: Optional[float] = None) -> str:
        """Search hotels using Booking.com RapidAPI"""
        
        # Check cache (1 hour TTL)
        cache_key = f"hotels:{destination}:{check_in}:{check_out}:{max_price}"
        cached = self._get_cached_result(cache_key)
        if cached:
            return self._format_result(cached)
        
        try:
            # First, get destination ID
            dest_id = self._get_destination_id(destination)
            
            if dest_id:
                # Use Booking.com RapidAPI
                url = "https://booking-com.p.rapidapi.com/v1/hotels/search"
                
                headers = {
                    "X-RapidAPI-Key": settings.rapidapi_key,
                    "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
                }
                
                params = {
                    "dest_id": dest_id,
                    "dest_type": "city",
                    "checkin_date": check_in,
                    "checkout_date": check_out,
                    "adults_number": 2,
                    "order_by": "popularity",
                    "filter_by_currency": "INR",
                    "room_number": 1,
                    "units": "metric",
                    "locale": "en-gb"
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    hotels = self._parse_booking_response(data, max_price)
                    
                    # Cache for 1 hour
                    self._set_cache(cache_key, hotels, ttl=3600)
                    return self._format_result(hotels)
            
            # Fallback to generated hotels
            return self._generate_estimated_hotels(destination, check_in, check_out, max_price)
                
        except Exception as e:
            # Fallback to estimated hotels on API failure
            return self._generate_estimated_hotels(destination, check_in, check_out, max_price)
    
    def _get_destination_id(self, destination: str) -> Optional[str]:
        """Get Booking.com destination ID"""
        try:
            url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
            
            headers = {
                "X-RapidAPI-Key": settings.rapidapi_key,
                "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
            }
            
            params = {"name": destination, "locale": "en-gb"}
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0].get("dest_id")
        except:
            pass
        return None
    
    def _parse_booking_response(self, data: dict, max_price: Optional[float]) -> dict:
        """Parse Booking.com API response"""
        hotels = []
        
        for hotel in data.get("result", [])[:10]:
            price = hotel.get("min_total_price", hotel.get("price_breakdown", {}).get("gross_price", 0))
            
            # Filter by max price if specified
            if max_price and price > max_price:
                continue
            
            hotels.append({
                "name": hotel.get("hotel_name"),
                "price_per_night": round(price, 2),
                "total_price": round(price, 2),
                "currency": hotel.get("currency_code", "INR"),
                "rating": hotel.get("review_score"),
                "review_count": hotel.get("review_nr"),
                "address": hotel.get("address"),
                "distance_from_center": hotel.get("distance_to_cc"),
                "amenities": self._extract_amenities(hotel),
                "image": hotel.get("max_photo_url"),
                "booking_link": hotel.get("url", f"https://www.booking.com/hotel/{hotel.get('hotel_id')}.html")
            })
        
        return {
            "destination": data.get("result", [{}])[0].get("city") if data.get("result") else "Unknown",
            "hotels": hotels[:8],
            "total_found": len(hotels)
        }
    
    def _extract_amenities(self, hotel: dict) -> list:
        """Extract hotel amenities"""
        amenities = []
        
        if hotel.get("has_free_parking"):
            amenities.append("Free Parking")
        if hotel.get("is_free_cancellable"):
            amenities.append("Free Cancellation")
        if hotel.get("has_swimming_pool"):
            amenities.append("Swimming Pool")
        
        # Add from hotel facilities if available
        for facility in hotel.get("hotel_facilities", "").split(",")[:5]:
            if facility.strip():
                amenities.append(facility.strip())
        
        return amenities[:6]
    
    def _generate_estimated_hotels(self, destination: str, check_in: str, check_out: str, max_price: Optional[float]) -> str:
        """Generate estimated hotel options when API fails"""
        
        # Calculate nights
        from datetime import datetime
        try:
            d1 = datetime.strptime(check_in, "%Y-%m-%d")
            d2 = datetime.strptime(check_out, "%Y-%m-%d")
            nights = (d2 - d1).days
        except:
            nights = 1
        
        base_prices = [1500, 2500, 4000, 6000, 8000]
        hotel_types = ["Budget Hotel", "Standard Hotel", "Business Hotel", "Premium Hotel", "Luxury Hotel"]
        
        hotels = []
        for i, (hotel_type, base_price) in enumerate(zip(hotel_types, base_prices)):
            if max_price and base_price > max_price:
                continue
                
            hotels.append({
                "name": f"{destination} {hotel_type}",
                "price_per_night": base_price,
                "total_price": base_price * nights,
                "currency": "INR",
                "rating": 3.5 + (i * 0.3),
                "address": f"Central {destination}",
                "amenities": ["WiFi", "AC", "TV", "Room Service"][:2+i],
                "booking_link": f"https://www.booking.com/searchresults.html?ss={destination.replace(' ', '+')}"
            })
        
        result = {
            "destination": destination,
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "hotels": hotels,
            "note": "Estimated prices. Check Booking.com, MakeMyTrip, or Goibibo for current availability and exact prices."
        }
        
        # Cache for 1 hour
        cache_key = f"hotels:{destination}:{check_in}:{check_out}:{max_price}"
        self._set_cache(cache_key, result, ttl=3600)
        
        return self._format_result(result)
    
    async def _arun(self, destination: str, check_in: str, check_out: str, max_price: Optional[float] = None) -> str:
        """Async version - delegates to sync for now"""
        return self._run(destination, check_in, check_out, max_price)
