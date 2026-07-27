"""Revision actions are pure functions — no model, no network, no graph."""

from app.agents.graph.actions import (
    apply_actions,
    describe,
    needs_refetch,
    request,
)
from app.agents.graph.nodes.supervisor import initial_constraints

BASE_PARAMS = {
    "destination": "Goa",
    "days": 4,
    "travelers": 2,
    "budget_limit": 40000.0,
    "start_date": "2099-03-01",
    "end_date": "2099-03-05",
}


def _state(**overrides):
    state = {
        "params": dict(BASE_PARAMS),
        "constraints": initial_constraints(BASE_PARAMS),
        "hotels": {"hotels": [{"name": "Inn", "price_per_night": 4000}]},
        "requests": [],
    }
    state.update(overrides)
    return state


def test_initial_constraints_split_the_budget():
    constraints = initial_constraints(BASE_PARAMS)
    # 35% of 40000 over 4 days
    assert constraints["hotel_nightly_cap"] == 3500
    assert constraints["food_budget"] == 8000
    assert constraints["activity_budget"] == 6000
    assert constraints["flight_tier"] == "cheapest"


def test_initial_constraints_without_a_budget():
    constraints = initial_constraints({"days": 3, "budget_limit": 0})
    assert constraints["hotel_nightly_cap"] is None
    assert constraints["flight_tier"] == "balanced"


def test_cheaper_hotels_tightens_the_cap():
    state = _state(requests=[request("cheaper_hotels", ratio=0.75)])
    delta, applied = apply_actions(state)

    assert delta["constraints"]["hotel_nightly_cap"] == 2625   # 3500 * 0.75
    assert applied == ["cheaper_hotels(ratio=0.75)"]
    assert not needs_refetch(applied)


def test_cheaper_hotels_never_cuts_below_the_cheapest_room():
    """A cap under every room wastes a round proving what is already known."""
    state = _state(
        hotels={"hotels": [{"name": "Inn", "price_per_night": 2500},
                           {"name": "Lodge", "price_per_night": 3000}]},
        requests=[request("cheaper_hotels", ratio=0.4)],
    )
    delta, _ = apply_actions(state)

    assert delta["constraints"]["hotel_nightly_cap"] == 2500    # not 3500 * 0.4


def test_cheaper_hotels_never_loosens_the_cap():
    """When nothing is affordable already, the cap is left where it is."""
    state = _state(
        hotels={"hotels": [{"name": "Pricey", "price_per_night": 9000}]},
        requests=[request("cheaper_hotels", ratio=0.75)],
    )
    delta, _ = apply_actions(state)

    assert delta["constraints"]["hotel_nightly_cap"] == 2625    # 3500 * 0.75


def test_cheaper_hotels_anchors_on_found_prices_when_uncapped():
    state = _state(constraints={"hotel_nightly_cap": None})
    state["requests"] = [request("cheaper_hotels", ratio=0.5)]
    delta, _ = apply_actions(state)

    assert delta["constraints"]["hotel_nightly_cap"] == 2000   # 4000 * 0.5


def test_shorten_stay_rewrites_the_trip_and_forces_a_refetch():
    state = _state(requests=[request("shorten_stay", days=1)])
    delta, applied = apply_actions(state)

    assert delta["params"]["days"] == 3
    assert delta["params"]["end_date"] == "2099-03-04"
    assert needs_refetch(applied)


def test_shorten_stay_never_goes_below_one_day():
    state = _state(requests=[request("shorten_stay", days=9)])
    delta, _ = apply_actions(state)
    assert delta["params"]["days"] == 1


def test_actions_compose_in_order():
    state = _state(requests=[
        request("cheaper_hotels", ratio=0.5),
        request("swap_flight", tier="cheapest"),
        request("drop_paid_activities", count=3),
    ])
    delta, applied = apply_actions(state)

    assert delta["constraints"]["hotel_nightly_cap"] == 1750
    assert delta["constraints"]["flight_tier"] == "cheapest"
    assert delta["constraints"]["max_paid_activities"] == 5    # 4 days * 2 - 3
    assert len(applied) == 3


def test_unknown_and_malformed_requests_are_skipped():
    state = _state(requests=[
        request("delete_everything"),
        request("cheaper_hotels", nonexistent_arg=1),
        request("rebalance_days"),
    ])
    delta, applied = apply_actions(state)

    assert applied == ["rebalance_days()"]
    assert delta["constraints"]["rebalance_days"] is True


def test_widen_hotel_search_clears_the_cap():
    state = _state(requests=[request("widen_hotel_search")])
    delta, _ = apply_actions(state)
    assert delta["constraints"]["hotel_nightly_cap"] is None


def test_describe_is_stable_for_the_ui():
    assert describe(request("swap_flight", tier="fastest")) == "swap_flight(tier=fastest)"
    assert describe(request("rebalance_days")) == "rebalance_days()"
