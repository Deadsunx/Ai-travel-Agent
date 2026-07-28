"""Specialist nodes: one per data domain, run as a parallel fan-out.

Each node fetches its section with the existing tools (sync functions moved
off the event loop with `asyncio.to_thread`, exactly as the v1 pipeline does)
and then *chooses*: a fare, a stay, which places belong to which day. The
choice and its one-line reason travel in the state, so the budget can be
costed from what was actually picked and the UI can show why.

The picking itself lives in `graph/selection.py` as pure functions — this
module is the I/O and reporting shell around them.
"""

from typing import Any, Callable, Dict, List
import asyncio
import logging

from app.agents.data import is_mock, safe_load, section_count
from app.agents.graph.runtime import emit, status
from app.agents.graph.selection import (
    Selection,
    assign_meals,
    cluster_by_area,
    select_flight,
    select_hotel,
)
from app.agents.graph.state import PlanState
from app.tools import (
    attraction_finder,
    flight_search,
    hotel_search,
    restaurant_finder,
)

logger = logging.getLogger(__name__)

DEFAULT_ORIGIN = "Delhi"

LABELS = {
    "flights": "✈️ Flights",
    "hotels": "🏨 Hotels",
    "restaurants": "🍽️ Restaurants",
    "attractions": "📍 Sights",
}

#: Which specialist owns which section, for the timeline UI.
OWNERS = {
    "flights": "flight",
    "hotels": "hotel",
    "restaurants": "local",
    "attractions": "local",
}


async def _fetch(
    section: str,
    tool: Callable[..., str],
    config: Dict[str, Any],
    **kwargs: Any,
) -> Any:
    """Run one tool and report what came back.

    A failing tool yields None for its section rather than failing the run —
    the mock fallback already covers missing keys, and a partial plan beats
    no plan.
    """
    try:
        data = safe_load(await asyncio.to_thread(tool, **kwargs))
    except Exception as e:
        logger.warning("%s failed: %s", section, e)
        data = None

    count = section_count(data, section)
    note = " (estimated)" if is_mock(data) else ""
    await status(config, f"{LABELS[section]}: found {count} options{note}")
    return data


async def _report(config: Dict[str, Any], section: str, data: Any,
                  selection: Selection = None) -> None:
    """Announce a specialist's result, with its choice when it made one."""
    event: Dict[str, Any] = {
        "type": "agent_result",
        "agent": OWNERS[section],
        "section": section,
        "count": section_count(data, section),
        "source": (data or {}).get("source", "") if isinstance(data, dict) else "",
    }
    if selection and selection.item:
        event["choice"] = {
            "name": selection.item.get("name") or selection.item.get("airline") or "",
            "rationale": selection.rationale,
        }
    await emit(config, event)


def _items(data: Any, key: str) -> List[Dict[str, Any]]:
    return (data or {}).get(key) or [] if isinstance(data, dict) else []


async def flight_agent(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Trade fare against flying time on the tier the supervisor set."""
    params = state["params"]
    data = await _fetch(
        "flights", flight_search, config,
        origin=str(params.get("origin") or DEFAULT_ORIGIN),
        destination=str(params["destination"]),
        date=params["start_date"],
        return_date=params["end_date"],
        passengers=params["travelers"],
    )

    selection = select_flight(
        _items(data, "flights"),
        (state.get("constraints") or {}).get("flight_tier", "balanced"),
    )
    await _report(config, "flights", data, selection)

    update: Dict[str, Any] = {"flights": data}
    choice = selection.as_choice()
    if choice:
        update["choices"] = {"flight": choice}
    return update


async def hotel_agent(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Best-rated stay inside the nightly cap; flag it when none fits."""
    params = state["params"]
    data = await _fetch(
        "hotels", hotel_search, config,
        city=str(params["destination"]),
        check_in=params["start_date"],
        check_out=params["end_date"],
        guests=params["travelers"],
    )

    selection = select_hotel(
        _items(data, "hotels"),
        (state.get("constraints") or {}).get("hotel_nightly_cap"),
    )
    await _report(config, "hotels", data, selection)

    update: Dict[str, Any] = {"hotels": data}
    choice = selection.as_choice()
    if choice:
        update["choices"] = {"hotel": choice}
    # Always written, never omitted: a key left out of a node's update keeps
    # its previous value, so a revision that fixes the problem would other-
    # wise leave the old complaint standing.
    update["specialist_issues"] = [selection.issue] if selection.issue else []
    return update


async def restaurant_agent(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Find eateries and lay out a distinct lunch and dinner for each day."""
    params = state["params"]
    data = await _fetch(
        "restaurants", restaurant_finder, config,
        city=str(params["destination"]),
        cuisine=params.get("cuisine"),
        budget="medium",
        # Two meals a day, so ask for what the trip needs rather than
        # accepting the default eight and repeating from day five.
        limit=params["days"] * 2,
    )

    meals = assign_meals(_items(data, "restaurants"), params["days"])
    await _report(config, "restaurants", data)
    return {"restaurants": data, "meal_plan": meals}


async def attraction_agent(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Find sights and group them so a day's stops are near each other."""
    params = state["params"]
    data = await _fetch(
        "attractions", attraction_finder, config,
        city=str(params["destination"]),
    )

    clusters = cluster_by_area(
        _items(data, "attractions"), params["days"],
        # Set by the rebalance_days revision action: spread the sights so
        # every day gets one, at some cost to how tightly each day clusters.
        even=bool((state.get("constraints") or {}).get("rebalance_days")),
    )
    await _report(config, "attractions", data)
    return {"attractions": data, "sight_clusters": clusters}


#: Node name -> callable, wired as a parallel fan-out in build.py.
SPECIALISTS = {
    "flight_agent": flight_agent,
    "hotel_agent": hotel_agent,
    "restaurant_agent": restaurant_agent,
    "attraction_agent": attraction_agent,
}
