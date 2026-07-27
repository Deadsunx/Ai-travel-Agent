"""Composition nodes: turn what the specialists chose into a budget and a
day-by-day skeleton.

Both are deterministic — the numbers a user is shown must be reproducible,
so no model touches them. The join point of the specialist fan-out is
`budget_node`: LangGraph runs it once all four specialists have reported.
"""

from typing import Any, Dict, List, Optional
import asyncio

from app.agents.data import cheapest, safe_load
from app.agents.graph.state import PlanState
from app.tools import budget_calculator, itinerary_builder


def chosen(state: PlanState, kind: str) -> Optional[Dict[str, Any]]:
    """The option a specialist picked, if it picked one."""
    return ((state.get("choices") or {}).get(kind) or {}).get("item")


def _price(item: Optional[Dict[str, Any]], key: str) -> float:
    try:
        value = float((item or {}).get(key, 0))
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _names(section: Any, list_key: str) -> list:
    """Names of the places in a tool result, for grounding the itinerary."""
    return [
        item.get("name")
        for item in ((section or {}).get(list_key) or [])
        if isinstance(item, dict) and item.get("name")
    ]


async def budget_node(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Cost the trip from the options that were actually chosen.

    v1 costed the cheapest flight and the cheapest hotel on the page, which
    is why its totals could describe a trip nobody was being offered. The
    cheapest price is still the fallback for when a specialist found nothing
    to choose from.
    """
    params = state["params"]

    flight_cost = (_price(chosen(state, "flight"), "price")
                   or cheapest(state.get("flights"), "flights", "price"))
    hotel_cost = (_price(chosen(state, "hotel"), "price_per_night")
                  or cheapest(state.get("hotels"), "hotels", "price_per_night"))

    budget = safe_load(await asyncio.to_thread(
        budget_calculator,
        destination=str(params["destination"]),
        days=params["days"],
        travelers=params["travelers"],
        budget_limit=params["budget_limit"],
        flight_cost=flight_cost,
        hotel_cost_per_night=hotel_cost,
        # None keeps the default of two a day; a revision that cut
        # activities passes the reduced count and the total falls with it.
        paid_activities=(state.get("constraints") or {}).get("max_paid_activities"),
    ))
    return {"budget": budget}


def daily_places(state: PlanState) -> List[Dict[str, Any]]:
    """Per-day places from the local desk: its meal pairs and sight clusters."""
    days = max(int(state["params"].get("days") or 1), 1)
    meals = state.get("meal_plan") or []
    clusters = state.get("sight_clusters") or []

    plan = []
    for day in range(days):
        meal = meals[day] if day < len(meals) else {}
        sights = clusters[day] if day < len(clusters) else []
        plan.append({
            "lunch": (meal.get("lunch") or {}).get("name"),
            "dinner": (meal.get("dinner") or {}).get("name"),
            "sights": [s.get("name") for s in sights if s.get("name")],
        })
    return plan


async def itinerary_node(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Day-by-day skeleton, each day built from one area's sights and its own
    pair of restaurants."""
    params = state["params"]

    itinerary = safe_load(await asyncio.to_thread(
        itinerary_builder,
        destination=str(params["destination"]),
        days=params["days"],
        interests=params.get("interests"),
        restaurants=_names(state.get("restaurants"), "restaurants"),
        attractions=_names(state.get("attractions"), "attractions"),
        daily_places=daily_places(state),
    ))
    return {"itinerary": itinerary}
