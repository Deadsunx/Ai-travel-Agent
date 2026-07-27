"""Where the two planners still agree, and where they deliberately do not.

Both are run over the same stubbed tools and the same stubbed LLM. Through
M1 they matched exactly. From M2 the graph *chooses* rather than reporting
everything, so the contract shrinks to what must never drift — the shape of
`collected_data`, the status lines, and the chat path — while the budget is
now expected to differ, and is asserted to.

Only the four search tools are stubbed — budget_calculator and
itinerary_builder are pure, so the real ones run and prove the composition
steps agree too.
"""

import json

import pytest

from app.agents import travel_agent as v1
from app.agents.graph.build import GraphPlanner
from app.agents.graph.nodes import specialists as specialist_nodes

FLIGHTS = {
    "flights": [
        {"airline": "IndiGo", "price": 4800, "departure_time": "06:10",
         "arrival_time": "07:45", "booking_link": "https://example.test/f1"},
        {"airline": "Akasa", "price": 6100, "departure_time": "11:00",
         "arrival_time": "12:35", "booking_link": "https://example.test/f2"},
    ],
    "source": "Google Flights (SerpAPI)",
}

HOTELS = {
    "hotels": [
        {"name": "Beach Retreat", "price_per_night": 3200, "rating": 4.3},
        {"name": "Palm Grove Inn", "price_per_night": 5400, "rating": 4.6},
        # Cheapest and worst — what v1 costs the whole trip on.
        {"name": "Hostel Bay", "price_per_night": 2400, "rating": 3.0},
    ],
    "source": "Booking.com (RapidAPI)",
}

RESTAURANTS = {
    "restaurants": [
        {"name": "Fisherman's Wharf", "cuisine": "Seafood"},
        {"name": "Gunpowder", "cuisine": "South Indian"},
        {"name": "Thalassa", "cuisine": "Greek"},
        {"name": "Bhatti Village", "cuisine": "Goan"},
    ],
    "source": "OpenStreetMap - Real Data",
}

ATTRACTIONS = {
    "attractions": [
        {"name": "Aguada Fort", "kind": "historic"},
        {"name": "Basilica of Bom Jesus", "kind": "attraction"},
        {"name": "Dudhsagar Falls", "kind": "attraction"},
    ],
    "source": "OpenStreetMap - Real Data",
}

PLAN_PARAMS = {
    "intent": "plan_trip",
    "destination": "Goa",
    "origin": "Mumbai",
    "start_date": "2099-01-15",
    "end_date": "2099-01-18",
    "days": 3,
    "travelers": 2,
    "budget_limit": 30000.0,
    "interests": "beaches, food",
    "cuisine": "seafood",
}

CHAT_PARAMS = {
    "intent": "chat",
    "destination": None,
    "origin": None,
    "start_date": "2099-01-15",
    "end_date": "2099-01-18",
    "days": 3,
    "travelers": 1,
    "budget_limit": 0.0,
    "interests": None,
    "cuisine": None,
}

ANSWER = "### Trip Summary\nThree days in Goa, within budget.\n### Booking Links\n- flights"


def _tool(payload):
    def call(**kwargs):
        return json.dumps(payload)
    return call


@pytest.fixture
def stub_planners(monkeypatch):
    """Stub the network tools and the LLM for both planners at once.

    Returns the list the synthesis prompts are recorded into.
    """
    tools = {
        "flight_search": _tool(FLIGHTS),
        "hotel_search": _tool(HOTELS),
        "restaurant_finder": _tool(RESTAURANTS),
        "attraction_finder": _tool(ATTRACTIONS),
    }
    for module in (v1, specialist_nodes):
        for name, stub in tools.items():
            monkeypatch.setattr(module, name, stub)

    prompts = []
    params = {"value": PLAN_PARAMS}

    async def fake_extract(self, user_query):
        return dict(params["value"])

    async def fake_stream(self, prompt):
        prompts.append(prompt)
        yield {"type": "token", "content": ANSWER[:20]}
        yield {"type": "token", "content": ANSWER[20:]}
        yield {"type": "text", "content": ANSWER}

    monkeypatch.setattr(v1.TravelPlanningAgent, "extract_params", fake_extract)
    monkeypatch.setattr(v1.TravelPlanningAgent, "stream_llm", fake_stream)
    # Redis-backed helpers: no store in a unit test.
    monkeypatch.setattr(v1.TravelPlanningAgent, "history_text", lambda self: "")
    monkeypatch.setattr(v1.TravelPlanningAgent, "load_stored_plan", lambda self: None)
    monkeypatch.setattr(v1.TravelPlanningAgent, "store_plan", lambda self, data: None)
    monkeypatch.setattr(
        v1.TravelPlanningAgent, "save_conversation", lambda self, q, a: None
    )
    # ChatOpenAI would try to read a base URL/key at construction.
    monkeypatch.setattr(v1, "get_llm", lambda model_name=None: object())

    return {"prompts": prompts, "params": params}


async def _collect_events(planner, query):
    events = []
    async for event in planner.plan_trip_events(query):
        events.append(event)
    return events


def _statuses(events):
    return {e["message"] for e in events if e["type"] == "status"}


def _result(events):
    results = [e["data"] for e in events if e["type"] == "result"]
    assert len(results) == 1, "exactly one result event expected"
    return results[0]


def _tokens(events):
    return "".join(e["content"] for e in events if e["type"] == "token")


@pytest.mark.asyncio
async def test_both_planners_speak_the_same_data_shape(stub_planners):
    """The contract the frontend and the database depend on."""
    query = "Plan a 3-day trip to Goa from Mumbai under 30000 rupees"

    pipeline_events = await _collect_events(
        v1.TravelPlanningAgent("parity-pipeline", "test-model"), query
    )
    graph_events = await _collect_events(
        GraphPlanner("parity-graph", "test-model"), query
    )

    pipeline, graph = _result(pipeline_events), _result(graph_events)
    assert pipeline["success"] is True
    assert graph["success"] is True
    assert graph["response"] == pipeline["response"] == ANSWER

    # Every v1 key is still present and still populated; the graph may add
    # its own (choices, issues) but may never drop one.
    for key, value in pipeline["collected_data"].items():
        assert key in graph["collected_data"], f"graph dropped {key}"
        assert bool(graph["collected_data"][key]) == bool(value), f"{key} emptiness differs"

    # Same progress lines, same streamed text.
    assert _statuses(graph_events) == _statuses(pipeline_events)
    assert _tokens(graph_events) == _tokens(pipeline_events)


@pytest.mark.asyncio
async def test_graph_records_why_it_chose(stub_planners):
    events = await _collect_events(
        GraphPlanner("graph-choices", "test-model"),
        "Plan a 3-day trip to Goa from Mumbai under 30000 rupees",
    )
    choices = {c["kind"]: c for c in _result(events)["collected_data"]["choices"]}

    assert set(choices) == {"flight", "hotel"}
    # Budget 30000 over 3 days puts the nightly cap at 3500, so the 5400
    # room is out and the better-rated 3200 beats the 2400 hostel.
    assert choices["hotel"]["item"]["name"] == "Beach Retreat"
    assert "₹3,500 cap" in choices["hotel"]["rationale"]
    assert choices["flight"]["item"]["airline"] == "IndiGo"
    assert choices["hotel"]["alternatives"], "runners-up kept for a later swap"


@pytest.mark.asyncio
async def test_chat_turn_skips_planning_in_both(stub_planners):
    stub_planners["params"]["value"] = CHAT_PARAMS

    pipeline_events = await _collect_events(
        v1.TravelPlanningAgent("parity-pipeline-chat", "test-model"), "hello"
    )
    graph_events = await _collect_events(
        GraphPlanner("parity-graph-chat", "test-model"), "hello"
    )

    pipeline, graph = _result(pipeline_events), _result(graph_events)
    assert graph["response"] == pipeline["response"]
    # No search ran, so every data section is empty in both.
    for section in ("flights", "hotels", "restaurants", "budget", "itinerary"):
        assert not pipeline["collected_data"].get(section)
        assert not graph["collected_data"].get(section)

    pipeline_prompt, graph_prompt = stub_planners["prompts"]
    assert graph_prompt == pipeline_prompt


@pytest.mark.asyncio
async def test_graph_reports_each_specialist(stub_planners):
    events = await _collect_events(
        GraphPlanner("graph-trace", "test-model"),
        "Plan a 3-day trip to Goa from Mumbai under 30000 rupees",
    )

    started = {e["agent"] for e in events if e["type"] == "agent_start"}
    assert started == {"flight", "hotel", "local"}

    sections = {e["section"] for e in events if e["type"] == "agent_result"}
    assert sections == {"flights", "hotels", "restaurants", "attractions"}

    critiques = [e for e in events if e["type"] == "critique"]
    assert [c["verdict"] for c in critiques] == ["pass"], "M1 critic has no rules yet"


@pytest.mark.asyncio
async def test_budget_follows_the_chosen_hotel_not_the_cheapest(stub_planners):
    """The point of M2: the total describes the trip being offered.

    v1 costs the ₹2,400 hostel nobody was shown; v2 costs the ₹3,200 room it
    actually chose.
    """
    query = "Plan a 3-day trip to Goa from Mumbai under 30000 rupees"

    pipeline_events = await _collect_events(
        v1.TravelPlanningAgent("budget-pipeline", "test-model"), query
    )
    graph_events = await _collect_events(
        GraphPlanner("budget-graph", "test-model"), query
    )

    pipeline_budget = _result(pipeline_events)["collected_data"]["budget"]
    graph_budget = _result(graph_events)["collected_data"]["budget"]

    assert pipeline_budget["breakdown"]["accommodation"] == 7200    # 2400 x 3
    assert graph_budget["breakdown"]["accommodation"] == 9600       # 3200 x 3
    # Both cost the same fare: under a budget the tier is "cheapest" anyway.
    assert graph_budget["breakdown"]["flights"] == pipeline_budget["breakdown"]["flights"]
