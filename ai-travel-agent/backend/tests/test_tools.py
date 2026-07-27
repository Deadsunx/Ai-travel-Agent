"""Unit tests for tool helpers and pure tool logic.

These import app.tools, which touches Redis at import time; the Redis client
degrades gracefully when no server is reachable, so no service is required.
"""

import json

from app.tools import (
    _extract_json_payload,
    _normalize_date,
    _norm_key_part,
    budget_calculator,
    itinerary_builder,
)


# ---------------- _extract_json_payload ----------------

def test_extract_plain_json():
    assert _extract_json_payload('{"city": "Goa"}') == {"city": "Goa"}


def test_extract_markdown_fenced_json():
    assert _extract_json_payload('```json\n{"city": "Goa"}\n```') == {"city": "Goa"}


def test_extract_json_with_surrounding_text():
    raw = 'Here you go: {"city": "Goa", "days": 3} hope that helps'
    assert _extract_json_payload(raw) == {"city": "Goa", "days": 3}


def test_extract_python_literal():
    assert _extract_json_payload("{'city': 'Goa'}") == {"city": "Goa"}


def test_extract_garbage_returns_none():
    assert _extract_json_payload("not json at all") is None
    assert _extract_json_payload("") is None


# ---------------- _normalize_date ----------------

def test_normalize_iso_date():
    assert _normalize_date("2026-08-01") == "2026-08-01"


def test_normalize_dmy_date():
    assert _normalize_date("01/08/2026") == "2026-08-01"


def test_normalize_none():
    assert _normalize_date(None) is None


# ---------------- _norm_key_part ----------------

def test_cache_key_normalization():
    assert _norm_key_part(" Goa ") == _norm_key_part("goa") == "goa"
    assert _norm_key_part("New Delhi") == "new_delhi"


# ---------------- budget_calculator ----------------

def test_budget_uses_real_prices():
    result = json.loads(budget_calculator(
        destination="Goa", days=3, travelers=2,
        flight_cost=5000, hotel_cost_per_night=3000,
    ))
    b = result["breakdown"]
    assert b["flights"] == 10000            # 5000 x 2 travelers
    assert b["accommodation"] == 9000       # 3000 x 3 nights
    # subtotal + 10% buffer
    assert result["total_with_buffer"] == result["subtotal"] + b["buffer_10_percent"]
    assert b["buffer_10_percent"] == round(result["subtotal"] * 0.10)


def test_budget_within_limit_flag():
    over = json.loads(budget_calculator(
        destination="Goa", days=3, budget_limit=1000, flight_cost=5000,
    ))
    assert over["within_budget"] is False

    under = json.loads(budget_calculator(
        destination="Goa", days=2, budget_limit=1000000,
    ))
    assert under["within_budget"] is True


def test_budget_no_limit_defaults_ok():
    result = json.loads(budget_calculator(destination="Goa"))
    assert result["within_budget"] is True
    assert result["budget_limit"] == 0


# ---------------- itinerary_builder ----------------

def test_itinerary_day_count():
    result = json.loads(itinerary_builder(destination="Goa", days=4))
    assert len(result["days"]) == 4


def test_itinerary_grounded_in_real_restaurants():
    result = json.loads(itinerary_builder(
        destination="Goa", days=2,
        restaurants=["Thalassa", "Gunpowder", "Fisherman's Wharf", "Vinayak"],
    ))
    text = json.dumps(result)
    assert "Thalassa" in text
    assert "Gunpowder" in text
    # No generic placeholders when real names were provided
    assert "local restaurant" not in text


def test_itinerary_fallback_without_data():
    result = json.loads(itinerary_builder(destination="Goa", days=1))
    text = json.dumps(result)
    assert "famous landmark #" not in text  # old placeholder style is gone


def test_activity_cost_defaults_to_two_a_day():
    """The per-activity rate must reproduce the original per-day figure."""
    import json
    from app.tools import budget_calculator

    budget = json.loads(budget_calculator(destination="Goa", days=3, travelers=1))
    assert budget["breakdown"]["activities"] == 3600      # 1200 x 3 days


def test_cutting_activities_lowers_the_total():
    """drop_paid_activities must move the number it claims to move."""
    import json
    from app.tools import budget_calculator

    full = json.loads(budget_calculator(destination="Goa", days=3, travelers=1))
    cut = json.loads(budget_calculator(destination="Goa", days=3, travelers=1,
                                       paid_activities=2))

    assert cut["breakdown"]["activities"] == 1200         # 2 x 600
    assert cut["total_with_buffer"] < full["total_with_buffer"]
