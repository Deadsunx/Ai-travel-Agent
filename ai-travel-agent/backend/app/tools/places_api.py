"""Places lookup via OpenStreetMap (Nominatim + Overpass).

Foursquare's v3 API was deprecated on 2026-05-15 and now returns 410 Gone, so
restaurants and attractions come from OpenStreetMap instead: no API key, no
quota, worldwide coverage.

Two calls are involved:
  1. Nominatim resolves a place name to coordinates (cached 30 days — city
     coordinates do not move).
  2. Overpass returns named POIs inside a bounding box around that point.

OSM carries no ratings or price levels, so none are reported. Inventing them
would defeat the point of the live/estimated distinction the app is built on.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# The main Overpass instance returns 504 on larger boxes at busy times, so
# fail over to public mirrors before giving up.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

# Both services require a descriptive User-Agent; bare clients get 406/429.
USER_AGENT = "AI-Travel-Agent/1.0 (PBL project; contact via repository)"

# Fallback box half-width (~27 km) used only when a place has no OSM area to
# query — a bare point result. Wider boxes were tried and are far too slow:
# Overpass answers an area query for all of Goa in seconds, but times out on
# the equivalent bounding box.
BBOX_HALF_DEGREES = 0.25

GEOCODE_TTL = 60 * 60 * 24 * 30
NOMINATIM_TIMEOUT = 10
# Kept tight on purpose: a trip plan that waits a minute for restaurant names
# is worse than one that falls back to estimates and says so.
OVERPASS_TIMEOUT = 18

# Tags that suggest a place is real and worth showing, used to rank results
# in the absence of ratings.
QUALITY_TAGS = ("cuisine", "website", "phone", "opening_hours", "wikidata", "addr:street")


def _clean(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _area_id(osm_type: str, osm_id: int) -> Optional[int]:
    """Overpass area id for an OSM object, or None if it has no area.

    Overpass keeps a dedicated area index built from relations and closed ways;
    querying it is dramatically faster than scanning a bounding box.
    """
    if osm_type == "relation":
        return 3600000000 + osm_id
    if osm_type == "way":
        return 2400000000 + osm_id
    return None


def geocode_place(place: str) -> Optional[Dict[str, Any]]:
    """Resolve a place name to {lat, lon, area_id}. Cached; None if not found."""
    key = f"geocode:v2:{place.strip().lower()}"
    cached = redis_service.get_cached(key)
    if cached and "lat" in cached:
        return cached

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": place, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=NOMINATIM_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            logger.warning("Nominatim found no match for %r", place)
            return None

        top = results[0]
        location = {
            "lat": float(top["lat"]),
            "lon": float(top["lon"]),
            "area_id": _area_id(top.get("osm_type", ""), int(top.get("osm_id", 0))),
        }
        redis_service.set_cache(key, location, ttl=GEOCODE_TTL)
        return location
    except Exception as e:
        logger.warning("Geocoding failed for %r: %s", place, e)
        return None


def _bbox(lat: float, lon: float, half: float = BBOX_HALF_DEGREES) -> str:
    """Overpass bounding box string: south,west,north,east."""
    return (
        f"{lat - half:.4f},{lon - half:.4f},"
        f"{lat + half:.4f},{lon + half:.4f}"
    )


def _scopes(location: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Query scopes to try, in order. Each is (prelude, filter) spliced into a
    query.

    The box around the centre goes first because it is bounded work and
    answers in seconds — which covers city destinations, the common case. The
    whole-area query is the fallback for regions like "Goa" or "Kerala", whose
    centre lands away from the POIs; it is correct but can take tens of
    seconds, so results are cached hard.
    """
    scopes: List[Tuple[str, str]] = [("", f"({_bbox(location['lat'], location['lon'])})")]
    if location.get("area_id"):
        scopes.append((f"area({location['area_id']})->.searchArea;", "(area.searchArea)"))
    return scopes


def _run_overpass(query: str) -> List[Dict[str, Any]]:
    """Run a query, trying each mirror until one answers."""
    last_error: Optional[Exception] = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=OVERPASS_TIMEOUT,
            )
            response.raise_for_status()
            return response.json().get("elements", [])
        except Exception as e:
            last_error = e
            logger.info("Overpass mirror %s unavailable (%s); trying next", endpoint, e)

    raise last_error if last_error else RuntimeError("No Overpass endpoint available")


def _rank(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order by how completely a POI is described — the best proxy OSM offers
    for notability, since there are no ratings."""
    def score(element: Dict[str, Any]) -> int:
        tags = element.get("tags", {})
        return sum(1 for tag in QUALITY_TAGS if tags.get(tag))

    return sorted(elements, key=score, reverse=True)


def _format_cuisine(raw: Optional[str]) -> str:
    """OSM cuisine tags look like 'indian;seafood' or 'fine_dining'."""
    if not raw:
        return "Restaurant"
    first = raw.split(";")[0]
    return re.sub(r"[_-]+", " ", first).strip().title() or "Restaurant"


def _address(tags: Dict[str, Any]) -> str:
    parts = [tags.get("addr:street"), tags.get("addr:suburb"), tags.get("addr:city")]
    return ", ".join(p for p in parts if p)


def search_restaurants_osm(location: str, cuisine: str = None, budget: str = "moderate", limit: int = 8) -> Optional[Dict]:
    """Restaurants in `location`. Returns None so callers can fall back."""
    place = geocode_place(location)
    if not place:
        return None

    cuisine_filter = ""
    if cuisine and cuisine.lower() not in ("any", "all", "none"):
        # Case-insensitive substring match against the cuisine tag.
        safe = re.sub(r'["\\\]]', "", cuisine)[:40]
        cuisine_filter = f'["cuisine"~"{safe}",i]'

    elements: List[Dict[str, Any]] = []
    for prelude, scope in _scopes(place):
        query = (
            f'[out:json][timeout:25];{prelude}'
            f'node["amenity"="restaurant"]["name"]{cuisine_filter}{scope};'
            f'out body {limit * 3};'
        )
        try:
            elements = _run_overpass(query)
        except Exception as e:
            logger.warning("Overpass restaurant search failed for %r: %s", location, e)
            continue
        if elements:
            break

    # A cuisine filter that matches nothing is worse than no filter.
    if not elements and cuisine_filter:
        return search_restaurants_osm(location, cuisine=None, budget=budget, limit=limit)

    restaurants = []
    for element in _rank(elements)[:limit]:
        tags = element.get("tags", {})
        name = _clean(tags.get("name"))
        if not name:
            continue
        restaurants.append({
            "name": name,
            "cuisine": _format_cuisine(tags.get("cuisine")),
            "address": _address(tags),
            "website": _clean(tags.get("website")),
            # Carried through so a planner can group a day's stops by area.
            "lat": element.get("lat"),
            "lon": element.get("lon"),
            # OSM has no ratings or price levels — report nothing rather than
            # inventing a number.
            "rating": 0,
            "price_level": None,
            "popular_dishes": [],
        })

    if not restaurants:
        return None

    return {
        "location": location,
        "cuisine": cuisine or "all",
        "budget": budget,
        "restaurants": restaurants,
        "source": "OpenStreetMap - Real Data",
    }


def search_attractions_osm(location: str, limit: int = 10) -> Optional[Dict]:
    """Sights worth building a day around: attractions, museums, viewpoints,
    monuments, beaches and places of worship."""
    place = geocode_place(location)
    if not place:
        return None

    elements: List[Dict[str, Any]] = []
    for prelude, scope in _scopes(place):
        query = (
            f'[out:json][timeout:25];{prelude}'
            # Nodes only: resolving way geometry costs far more than it adds,
            # and named POI nodes already cover the sights worth visiting.
            f'('
            f'node["tourism"~"attraction|museum|viewpoint"]["name"]{scope};'
            f'node["historic"~"monument|fort|castle"]["name"]{scope};'
            f'node["natural"="beach"]["name"]{scope};'
            f');'
            f'out body {limit * 3};'
        )
        try:
            elements = _run_overpass(query)
        except Exception as e:
            logger.warning("Overpass attraction search failed for %r: %s", location, e)
            continue
        if elements:
            break

    attractions = []
    seen = set()
    for element in _rank(elements):
        tags = element.get("tags", {})
        name = _clean(tags.get("name"))
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        attractions.append({
            "name": name,
            "kind": tags.get("tourism") or tags.get("historic") or tags.get("natural") or "sight",
            # Carried through so a planner can group a day's stops by area.
            "lat": element.get("lat"),
            "lon": element.get("lon"),
        })
        if len(attractions) >= limit:
            break

    if not attractions:
        return None

    return {
        "location": location,
        "attractions": attractions,
        "source": "OpenStreetMap - Real Data",
    }


def get_mock_attractions(location: str, reason: str = "Lookup unavailable") -> Dict:
    """Generic stand-ins, clearly marked."""
    return {
        "location": location,
        "attractions": [
            {"name": f"{location} old quarter", "kind": "attraction"},
            {"name": f"{location} central market", "kind": "attraction"},
            {"name": f"{location} waterfront", "kind": "viewpoint"},
        ],
        "source": f"Mock Data ({reason})",
    }
