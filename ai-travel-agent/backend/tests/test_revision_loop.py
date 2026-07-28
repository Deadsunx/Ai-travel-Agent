"""The revision loop, end to end, with no model in the way.

A plan that breaks the budget must come back cheaper, and a plan that
cannot be fixed must still terminate. Both are properties of the whole
graph, not of any one node, so they are exercised through the planner.
"""

import json

import pytest

from app.agents import travel_agent as v1
from app.agents.graph.build import GraphPlanner
from app.agents.graph.nodes import specialists as specialist_nodes

# One cheap room and one expensive one. Under a 30,000 budget over 3 days
# the cap starts at 3,500, so the 3,400 room is chosen and the trip lands
# over budget; only a tightened cap reaches the 1,200 room.
HOTELS = {
    "hotels": [
        {"name": "Sea View", "price_per_night": 3400, "rating": 4.8},
        {"name": "Lane House", "price_per_night": 1200, "rating": 3.9},
    ],
    "source": "Booking.com (RapidAPI)",
}

# Cheap enough that the room is what decides whether the trip fits: the
# fixed costs (food, transport, activities) already take ₹16,500 of the
# ₹30,000, and the fare takes ₹4,000 of what is left.
FLIGHTS = {
    "flights": [{"airline": "IndiGo", "price": 2000,
                 "departure_time": "06:10", "arrival_time": "07:45"}],
    "source": "Google Flights (SerpAPI)",
}

RESTAURANTS = {
    "restaurants": [{"name": f"R{i}"} for i in range(8)],
    "source": "OpenStreetMap - Real Data",
}

ATTRACTIONS = {
    "attractions": [{"name": f"S{i}", "lat": 15.4 + i * 0.01, "lon": 73.8}
                    for i in range(6)],
    "source": "OpenStreetMap - Real Data",
}

PARAMS = {
    "intent": "plan_trip",
    "destination": "Goa",
    "origin": "Mumbai",
    "start_date": "2099-01-15",
    "end_date": "2099-01-18",
    "days": 3,
    "travelers": 2,
    "budget_limit": 30000.0,
    "interests": "beaches",
    "cuisine": None,
}

ANSWER = "### Trip Summary\nThree days in Goa.\n### Budget Breakdown\nWithin budget."


def _tool(payload):
    def call(**kwargs):
        return json.dumps(payload)
    return call


@pytest.fixture
def stubbed(monkeypatch):
    for name, payload in (("flight_search", FLIGHTS), ("hotel_search", HOTELS),
                          ("restaurant_finder", RESTAURANTS),
                          ("attraction_finder", ATTRACTIONS)):
        monkeypatch.setattr(specialist_nodes, name, _tool(payload))

    prompts = []

    async def fake_extract(self, user_query):
        return dict(PARAMS)

    async def fake_stream(self, prompt):
        prompts.append(prompt)
        yield {"type": "token", "content": ANSWER}
        yield {"type": "text", "content": ANSWER}

    monkeypatch.setattr(v1.TravelPlanningAgent, "extract_params", fake_extract)
    monkeypatch.setattr(v1.TravelPlanningAgent, "stream_llm", fake_stream)
    monkeypatch.setattr(v1.TravelPlanningAgent, "history_text", lambda self: "")
    monkeypatch.setattr(v1.TravelPlanningAgent, "load_stored_plan", lambda self: None)
    monkeypatch.setattr(v1.TravelPlanningAgent, "store_plan", lambda self, data: None)
    monkeypatch.setattr(v1.TravelPlanningAgent, "save_conversation", lambda self, q, a: None)
    monkeypatch.setattr(v1, "get_llm", lambda model_name=None: object())
    return prompts


async def _run(session, max_revisions=1):
    from app.config import settings

    original = settings.max_revisions
    settings.max_revisions = max_revisions
    try:
        events = []
        async for event in GraphPlanner(session, "test-model").plan_trip_events(
            "Plan 3 days in Goa from Mumbai under 30000"
        ):
            events.append(event)
        return events
    finally:
        settings.max_revisions = original


def _result(events):
    return next(e["data"] for e in events if e["type"] == "result")


def _critiques(events):
    return [e for e in events if e["type"] == "critique"]


@pytest.mark.asyncio
async def test_an_over_budget_plan_is_sent_back_and_comes_back_cheaper(stubbed):
    events = await _run("loop-revise", max_revisions=1)

    verdicts = [c["verdict"] for c in _critiques(events)]
    assert verdicts == ["revise", "pass"], f"expected one round trip, got {verdicts}"

    revisions = [e for e in events if e["type"] == "revision"]
    assert revisions and revisions[0]["round"] == 1
    assert any("cheaper_hotels" in action for action in revisions[0]["actions"])

    collected = _result(events)["collected_data"]
    assert collected["budget"]["within_budget"] is True
    # The second round reached the room the first round's cap excluded.
    hotel = next(c for c in collected["choices"] if c["kind"] == "hotel")
    assert hotel["item"]["name"] == "Lane House"
    assert collected["revisions"] == 1


@pytest.mark.asyncio
async def test_the_answer_is_written_from_the_revised_plan(stubbed):
    await _run("loop-prompt", max_revisions=1)

    # One synthesis prompt only: revisions must not stream two answers.
    assert len(stubbed) == 1

    # Both rooms appear in the prompt as search results; what matters is
    # which one the recorded choice and the costing settled on.
    assert '"rationale": "Lane House' in stubbed[0]
    assert '"accommodation": 3600' in stubbed[0]      # 1200 x 3 nights


@pytest.mark.asyncio
async def test_no_revision_budget_means_the_problem_is_stated_not_fixed(stubbed):
    events = await _run("loop-giveup", max_revisions=0)

    assert [c["verdict"] for c in _critiques(events)] == ["give_up"]
    collected = _result(events)["collected_data"]
    assert collected["budget"]["within_budget"] is False
    # The unresolved problem reaches the writer rather than being dropped.
    assert any(i["severity"] == "blocker" for i in collected["issues"])


@pytest.mark.asyncio
async def test_the_loop_terminates_even_when_nothing_helps(monkeypatch, stubbed):
    """Every room is unaffordable, so no cap ever satisfies the budget."""
    monkeypatch.setattr(specialist_nodes, "hotel_search", _tool({
        "hotels": [{"name": "Only Option", "price_per_night": 40000, "rating": 4.0}],
        "source": "Booking.com (RapidAPI)",
    }))

    events = await _run("loop-hopeless", max_revisions=3)

    verdicts = [c["verdict"] for c in _critiques(events)]
    assert verdicts[-1] == "give_up"
    assert len(verdicts) <= 4, "must stop at the revision ceiling"
    assert _result(events)["success"] is True
