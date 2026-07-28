"""Unit tests for the OpenStreetMap places lookup.

Network calls are stubbed — these check parsing, ranking and fallback logic,
not OSM's uptime.
"""

import json
from unittest.mock import patch

import pytest

from app.tools import places_api
from app.tools.places_api import (
    _address,
    _bbox,
    _format_cuisine,
    _rank,
    search_attractions_osm,
    search_restaurants_osm,
)


# ---------------- pure helpers ----------------

def test_bbox_is_south_west_north_east():
    # Overpass expects S,W,N,E — a transposed box silently returns nothing.
    south, west, north, east = _bbox(15.5, 73.8).split(",")
    assert float(south) < float(north)
    assert float(west) < float(east)
    assert float(south) == pytest.approx(15.25, abs=0.01)
    assert float(east) == pytest.approx(74.05, abs=0.01)


def test_format_cuisine_takes_first_and_titles():
    assert _format_cuisine("indian;seafood") == "Indian"
    assert _format_cuisine("fine_dining") == "Fine Dining"
    assert _format_cuisine(None) == "Restaurant"
    assert _format_cuisine("") == "Restaurant"


def test_address_joins_available_parts():
    assert _address({"addr:street": "Beach Rd", "addr:city": "Panaji"}) == "Beach Rd, Panaji"
    assert _address({}) == ""


def test_rank_prefers_richly_tagged_places():
    sparse = {"tags": {"name": "Unknown Dhaba"}}
    rich = {"tags": {"name": "Real Place", "cuisine": "indian", "website": "x", "phone": "y"}}
    assert _rank([sparse, rich])[0] is rich


# ---------------- restaurants ----------------

GOA_ELEMENTS = [
    {"tags": {"name": "Punjabi Dhaba"}},
    {"tags": {"name": "Mayonna Creek Side", "cuisine": "regional;seafood",
              "website": "http://x", "addr:street": "Creek Rd"}},
]


def test_restaurants_parsed_and_marked_real():
    with patch.object(places_api, "geocode_place", return_value={"lat": 15.5, "lon": 73.8, "area_id": None}), \
         patch.object(places_api, "_run_overpass", return_value=GOA_ELEMENTS):
        result = search_restaurants_osm("Goa")

    assert result["source"] == "OpenStreetMap - Real Data"
    names = [r["name"] for r in result["restaurants"]]
    assert "Punjabi Dhaba" in names
    # Best-described place ranks first.
    assert result["restaurants"][0]["name"] == "Mayonna Creek Side"
    assert result["restaurants"][0]["cuisine"] == "Regional"


def test_restaurants_never_invent_ratings():
    with patch.object(places_api, "geocode_place", return_value={"lat": 15.5, "lon": 73.8, "area_id": None}), \
         patch.object(places_api, "_run_overpass", return_value=GOA_ELEMENTS):
        result = search_restaurants_osm("Goa")

    # OSM has no ratings; reporting a fake one would undermine the live/est split.
    assert all(r["rating"] == 0 for r in result["restaurants"])
    assert all(r["price_level"] is None for r in result["restaurants"])


def test_restaurants_skip_unnamed_places():
    with patch.object(places_api, "geocode_place", return_value={"lat": 15.5, "lon": 73.8, "area_id": None}), \
         patch.object(places_api, "_run_overpass", return_value=[{"tags": {"cuisine": "indian"}}]):
        assert search_restaurants_osm("Goa") is None


def test_cuisine_filter_retries_without_filter_when_empty():
    calls = []

    def fake_overpass(query):
        calls.append(query)
        return [] if "cuisine" in query else GOA_ELEMENTS

    with patch.object(places_api, "geocode_place", return_value={"lat": 15.5, "lon": 73.8, "area_id": None}), \
         patch.object(places_api, "_run_overpass", side_effect=fake_overpass):
        result = search_restaurants_osm("Goa", cuisine="Ethiopian")

    # A cuisine nobody serves locally should still return the local restaurants.
    assert any("cuisine" not in q for q in calls), "should retry without the cuisine filter"
    assert result is not None
    assert result["restaurants"]


def test_overpass_fails_over_to_next_mirror():
    from app.tools.places_api import _run_overpass

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"elements": GOA_ELEMENTS}

    attempts = []

    def fake_post(url, **kwargs):
        attempts.append(url)
        if len(attempts) == 1:
            raise RuntimeError("504 Gateway Timeout")
        return Response()

    with patch.object(places_api.requests, "post", side_effect=fake_post):
        elements = _run_overpass("[out:json];node;out;")

    assert len(attempts) == 2, "should try the next mirror after a failure"
    assert elements == GOA_ELEMENTS


def test_prefers_bounding_box_for_speed():
    """The box around the centre is bounded work and answers in seconds, so it
    is tried before the whole-area query even when an area is available."""
    queries = []

    def fake_overpass(query):
        queries.append(query)
        return GOA_ELEMENTS

    goa = {"lat": 15.36, "lon": 74.03, "area_id": 3607790883}
    with patch.object(places_api, "geocode_place", return_value=goa), \
         patch.object(places_api, "_run_overpass", side_effect=fake_overpass):
        result = search_restaurants_osm("Goa")

    assert len(queries) == 1, "the bounding box should succeed on its own"
    assert "area(" not in queries[0], "bbox is tried first"
    assert result["source"] == "OpenStreetMap - Real Data"


def test_falls_back_to_indexed_area_when_box_is_empty():
    queries = []

    def fake_overpass(query):
        queries.append(query)
        return GOA_ELEMENTS if "area(" in query else []

    goa = {"lat": 15.36, "lon": 74.03, "area_id": 3607790883}
    with patch.object(places_api, "geocode_place", return_value=goa), \
         patch.object(places_api, "_run_overpass", side_effect=fake_overpass):
        result = search_restaurants_osm("Goa")

    assert len(queries) == 2, "should fall back to the whole-area query"
    assert "area(3607790883)" in queries[1]
    assert result is not None


def test_area_id_derivation():
    from app.tools.places_api import _area_id

    # Overpass offsets: relations by 3.6e9, closed ways by 2.4e9; nodes have
    # no area at all.
    assert _area_id("relation", 7790883) == 3607790883
    assert _area_id("way", 12345) == 2400012345
    assert _area_id("node", 999) is None


def test_unknown_city_returns_none():
    with patch.object(places_api, "geocode_place", return_value=None):
        assert search_restaurants_osm("Nowheresville") is None


def test_overpass_failure_returns_none_for_fallback():
    with patch.object(places_api, "geocode_place", return_value={"lat": 15.5, "lon": 73.8, "area_id": None}), \
         patch.object(places_api, "_run_overpass", side_effect=RuntimeError("503")):
        assert search_restaurants_osm("Goa") is None


# ---------------- attractions ----------------

def test_attractions_dedupe_by_name():
    elements = [
        {"tags": {"name": "Museum of Goa", "tourism": "museum", "website": "x"}},
        {"tags": {"name": "museum of goa", "tourism": "museum"}},
        {"tags": {"name": "Miramar Beach", "natural": "beach"}},
    ]
    with patch.object(places_api, "geocode_place", return_value={"lat": 15.5, "lon": 73.8, "area_id": None}), \
         patch.object(places_api, "_run_overpass", return_value=elements):
        result = search_attractions_osm("Goa")

    names = [a["name"] for a in result["attractions"]]
    assert len(names) == 2
    assert result["attractions"][0]["kind"] == "museum"


def test_attractions_respect_limit():
    elements = [{"tags": {"name": f"Sight {i}", "tourism": "attraction"}} for i in range(40)]
    with patch.object(places_api, "geocode_place", return_value={"lat": 15.5, "lon": 73.8, "area_id": None}), \
         patch.object(places_api, "_run_overpass", return_value=elements):
        result = search_attractions_osm("Goa", limit=5)

    assert len(result["attractions"]) == 5


# ---------------- tool wiring ----------------

def test_attraction_finder_falls_back_to_mock():
    from app.tools import attraction_finder

    with patch.object(places_api, "geocode_place", return_value=None):
        payload = json.loads(attraction_finder("Atlantis"))

    assert payload["source"].startswith("Mock Data")
    assert payload["attractions"]
