"""Unit tests for trip-parameter resolution."""

from datetime import datetime, timedelta

from app.agents.params import (
    resolve_trip_params,
    MAX_TRIP_DAYS,
    DEFAULT_TRIP_DAYS,
    DEFAULT_START_OFFSET_DAYS,
)

TODAY = datetime.now().date()


def test_defaults_when_nothing_given():
    p = resolve_trip_params({})
    assert p["days"] == DEFAULT_TRIP_DAYS
    assert p["travelers"] == 1
    assert p["budget_limit"] == 0
    start = datetime.strptime(p["start_date"], "%Y-%m-%d").date()
    assert start == TODAY + timedelta(days=DEFAULT_START_OFFSET_DAYS)


def test_past_date_moved_to_future():
    p = resolve_trip_params({"start_date": "2020-01-01"})
    start = datetime.strptime(p["start_date"], "%Y-%m-%d").date()
    assert start > TODAY


def test_days_inferred_from_date_range():
    start = TODAY + timedelta(days=30)
    end = start + timedelta(days=5)
    p = resolve_trip_params({
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
    })
    assert p["days"] == 5
    assert p["end_date"] == end.strftime("%Y-%m-%d")


def test_days_clamped_to_max():
    p = resolve_trip_params({"days": 60})
    assert p["days"] == MAX_TRIP_DAYS


def test_garbage_values_fall_back():
    p = resolve_trip_params({
        "days": "a week",
        "travelers": "two",
        "budget_limit": "cheap",
        "start_date": "next month",
    })
    assert p["days"] == DEFAULT_TRIP_DAYS
    assert p["travelers"] == 1
    assert p["budget_limit"] == 0


def test_budget_string_number():
    p = resolve_trip_params({"budget_limit": "30000"})
    assert p["budget_limit"] == 30000.0
