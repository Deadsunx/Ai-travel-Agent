"""
Quick test script to verify API keys work outside Docker
Run: python test_apis.py
"""
import os
import requests

# API Keys from Api keys.txt
SERPAPI_KEY = "4b4e24b49ece365a747e4cda5266bf979c3e064cc797f95ef5eea4b96a06725f"
RAPIDAPI_KEY = "f835b12849mshf59582ed5050485p1e9607jsn2d171fa63d8c"
FOURSQUARE_API_KEY = "fsq3Qv5cR9wAeNEAnAmtSU0oPy83Q5XxXunGNd5crlL0vjo="

def test_serpapi():
    """Test SerpAPI Google Flights"""
    print("Testing SerpAPI...")
    try:
        url = "https://serpapi.com/search"
        params = {
            "engine": "google_flights",
            "departure_id": "DEL",
            "arrival_id": "GOI",
            "outbound_date": "2026-03-01",
            "currency": "INR",
            "hl": "en",
            "api_key": SERPAPI_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            print("✅ SerpAPI works! (Status code: 200)")
            return True
        else:
            print(f"❌ SerpAPI failed: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ SerpAPI error: {e}")
        return False

def test_rapidapi():
    """Test RapidAPI Booking.com"""
    print("\nTesting RapidAPI (Booking.com)...")
    try:
        url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
        }
        params = {
            "dest_id": "-2092174",  # Goa
            "search_type": "CITY",
            "arrival_date": "2026-03-01",
            "departure_date": "2026-03-05",
            "adults": "2",
            "room_qty": "1",
            "page_number": "1",
            "units": "metric",
            "temperature_unit": "c",
            "languagecode": "en-us",
            "currency_code": "INR"
        }
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            print("✅ RapidAPI works! (Status code: 200)")
            return True
        else:
            print(f"❌ RapidAPI failed: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ RapidAPI error: {e}")
        return False

def test_foursquare():
    """Test Foursquare Places API"""
    print("\nTesting Foursquare...")
    try:
        url = "https://api.foursquare.com/v3/places/search"
        headers = {
            "Authorization": FOURSQUARE_API_KEY,
            "Accept": "application/json"
        }
        params = {
            "near": "Goa,India",
            "categories": "13065",  # Restaurants
            "limit": 5
        }
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            print("✅ Foursquare works! (Status code: 200)")
            return True
        else:
            print(f"❌ Foursquare failed: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Foursquare error: {e}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("API Keys Test")
    print("="*50)
    
    serp_ok = test_serpapi()
    rapid_ok = test_rapidapi()
    four_ok = test_foursquare()
    
    print("\n" + "="*50)
    print("RESULTS:")
    print(f"SerpAPI: {'✅ Working' if serp_ok else '❌ Failed'}")
    print(f"RapidAPI: {'✅ Working' if rapid_ok else '❌ Failed'}")
    print(f"Foursquare: {'✅ Working' if four_ok else '❌ Failed'}")
    print("="*50)
