"""State projection: the graph must keep speaking v1's data shape."""

from app.agents.graph.nodes.critic import revision_budget
from app.agents.graph.state import (
    COLLECTED_KEYS,
    empty_collected,
    initial_state,
    to_collected,
)


def test_empty_collected_has_exactly_the_v1_keys():
    collected = empty_collected()
    assert tuple(collected) == COLLECTED_KEYS
    assert collected["search_results"] == []
    assert collected["trip_params"] == {}


def test_to_collected_carries_every_section():
    state = {
        "params": {"destination": "Goa", "days": 3},
        "flights": {"flights": [{"price": 4800}]},
        "hotels": {"hotels": []},
        "restaurants": {"restaurants": []},
        "attractions": {"attractions": []},
        "budget": {"total_with_buffer": 25000},
        "itinerary": {"days": []},
    }
    collected = to_collected(state)

    assert collected["flights"] == state["flights"]
    assert collected["budget"] == state["budget"]
    assert collected["trip_params"] == state["params"]


def test_to_collected_omits_v2_keys_until_they_are_used():
    """A plan with no decisions or revisions is byte-identical to v1's."""
    state = {"params": {"destination": "Goa"}, "choices": {}, "issues": [], "revision": 0}
    assert tuple(to_collected(state)) == COLLECTED_KEYS


def test_to_collected_adds_the_decision_trail_once_present():
    state = {
        "params": {},
        # Keyed by kind in the state, a list once projected for the UI.
        "choices": {"hotel": {"kind": "hotel", "item": {}, "rationale": "cheapest under cap"}},
        "issues": [{"severity": "warning", "category": "budget", "message": "tight"}],
        "revision": 1,
    }
    collected = to_collected(state)

    assert collected["choices"][0]["rationale"] == "cheapest under cap"
    assert collected["issues"][0]["severity"] == "warning"
    assert collected["revisions"] == 1


def test_initial_state_starts_a_clean_run():
    state = initial_state("s1", "qwen3:8b", "plan a trip", max_revisions=2)
    assert state["revision"] == 0
    assert state["max_revisions"] == 2
    assert state["choices"] == {}
    assert state["issues"] == state["requests"] == []


def test_revision_budget_is_capped_regardless_of_configuration():
    assert revision_budget(0) == 0
    assert revision_budget(2) == 2
    assert revision_budget(99) == 3
