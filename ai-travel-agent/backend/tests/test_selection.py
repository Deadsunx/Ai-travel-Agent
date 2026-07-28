"""Selection is where v2's judgment lives, so it is tested exhaustively and
without a model."""

from app.agents.graph.selection import (
    assign_meals,
    cluster_by_area,
    select_flight,
    select_hotel,
)

FLIGHTS = [
    {"airline": "IndiGo", "price": 4800, "departure_time": "06:10", "arrival_time": "07:45"},
    {"airline": "Akasa", "price": 4200, "departure_time": "11:00", "arrival_time": "17:30"},
    {"airline": "Vistara", "price": 7100, "departure_time": "09:00", "arrival_time": "10:25"},
]

HOTELS = [
    {"name": "Palm Grove", "price_per_night": 5400, "rating": 4.6},
    {"name": "Beach Retreat", "price_per_night": 3200, "rating": 4.3},
    {"name": "Budget Stay", "price_per_night": 1800, "rating": 3.1},
]


def test_cheapest_tier_takes_the_lowest_fare():
    selection = select_flight(FLIGHTS, "cheapest")
    assert selection.item["airline"] == "Akasa"
    assert "cheapest of 3" in selection.rationale


def test_fastest_tier_pays_for_time():
    selection = select_flight(FLIGHTS, "fastest")
    assert selection.item["airline"] in ("Vistara", "IndiGo")
    # 6.5 hours in the air is never the fastest option here.
    assert selection.item["airline"] != "Akasa"


def test_balanced_explains_what_the_extra_money_buys():
    selection = select_flight(FLIGHTS, "balanced")
    if selection.item["airline"] != "Akasa":
        assert "over the cheapest" in selection.rationale
        assert "shorter" in selection.rationale


def test_alternatives_are_kept_for_a_later_swap():
    selection = select_flight(FLIGHTS, "cheapest")
    assert len(selection.alternatives) == 2
    assert selection.as_choice()["alternatives"] == selection.alternatives


def test_no_fares_is_not_a_crash():
    selection = select_flight([], "cheapest")
    assert selection.item is None
    assert selection.as_choice() is None


def test_hotel_respects_the_cap_and_prefers_rating():
    selection = select_hotel(HOTELS, nightly_cap=3500)
    assert selection.item["name"] == "Beach Retreat"    # 4.3 beats 3.1, both under cap
    assert selection.issue is None
    assert "₹3,500 cap" in selection.rationale


def test_hotel_without_a_cap_takes_the_best_rated():
    selection = select_hotel(HOTELS)
    assert selection.item["name"] == "Palm Grove"
    assert selection.issue is None


def test_impossible_cap_keeps_the_cheapest_and_raises_a_blocker():
    selection = select_hotel(HOTELS, nightly_cap=900)

    assert selection.item["name"] == "Budget Stay"
    assert selection.issue["severity"] == "blocker"
    assert selection.issue["action"] == "widen_hotel_search"
    assert "over the ₹900 cap" in selection.rationale


def test_clusters_keep_nearby_sights_on_the_same_day():
    places = [
        {"name": "North A", "lat": 15.60, "lon": 73.75},
        {"name": "North B", "lat": 15.61, "lon": 73.76},
        {"name": "South A", "lat": 15.20, "lon": 73.90},
        {"name": "South B", "lat": 15.21, "lon": 73.91},
    ]
    day_one, day_two = cluster_by_area(places, days=2)

    assert {p["name"] for p in day_one} == {"South A", "South B"}
    assert {p["name"] for p in day_two} == {"North A", "North B"}


def test_places_without_coordinates_fall_back_to_round_robin():
    places = [{"name": f"Sight {i}"} for i in range(4)]
    buckets = cluster_by_area(places, days=2)

    assert [p["name"] for p in buckets[0]] == ["Sight 0", "Sight 2"]
    assert [p["name"] for p in buckets[1]] == ["Sight 1", "Sight 3"]


def test_chunking_can_leave_a_late_day_empty():
    """The coherence/coverage trade rebalance_days exists to make."""
    places = [{"name": f"S{i}", "lat": 15 + i * 0.05, "lon": 73.5} for i in range(6)]
    buckets = cluster_by_area(places, days=4)

    assert buckets[3] == [], "contiguous chunking fills the early days first"


def test_even_spreads_a_sight_onto_every_day():
    places = [{"name": f"S{i}", "lat": 15 + i * 0.05, "lon": 73.5} for i in range(6)]
    buckets = cluster_by_area(places, days=4, even=True)

    assert all(bucket for bucket in buckets), "every day gets a real sight"
    assert sum(len(b) for b in buckets) == 6


def test_every_place_lands_on_exactly_one_day():
    places = [{"name": f"S{i}", "lat": 15 + i * 0.1, "lon": 73.5} for i in range(9)]
    buckets = cluster_by_area(places, days=4)

    assigned = [p["name"] for bucket in buckets for p in bucket]
    assert sorted(assigned) == sorted(p["name"] for p in places)
    assert len(buckets) == 4


def test_meals_do_not_repeat_while_restaurants_remain():
    pool = [{"name": f"R{i}"} for i in range(8)]
    plan = assign_meals(pool, days=4)

    picked = [meal[slot]["name"] for meal in plan for slot in ("lunch", "dinner")]
    assert len(set(picked)) == 8, "every day should get two unused restaurants"


def test_meals_reuse_only_once_the_pool_is_exhausted():
    pool = [{"name": "Solo"}, {"name": "Duo"}]
    plan = assign_meals(pool, days=3)

    assert plan[0]["lunch"]["name"] == "Solo"
    assert plan[0]["dinner"]["name"] == "Duo"
    assert plan[1]["lunch"]["name"] == "Solo"   # pool exhausted after day one


def test_no_restaurants_yields_empty_slots():
    plan = assign_meals([], days=2)
    assert plan == [{"lunch": None, "dinner": None}, {"lunch": None, "dinner": None}]
