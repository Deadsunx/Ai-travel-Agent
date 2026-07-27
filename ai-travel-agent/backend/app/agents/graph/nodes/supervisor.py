"""Supervisor node: turn the trip budget into per-specialist constraints.

Revision 0 is deliberately deterministic — no LLM call, so v2 pays nothing
in latency for the extra structure. From revision 1 on, the critic's
requested actions (see `graph/actions.py`) are applied to the previous
constraints; the action enum is the whole planning language, which is what
keeps small local models reliable.

The constraints computed here are consumed by the specialists from M2
onward; at M1 they are emitted for the trace but do not change any search,
so the graph reproduces v1 exactly.
"""

from typing import Any, Dict

from app.agents.graph.runtime import emit
from app.agents.graph.state import PlanState

# Share of the total budget each category may claim when a limit was given.
HOTEL_SHARE = 0.35
FOOD_SHARE = 0.20
ACTIVITY_SHARE = 0.15


def initial_constraints(params: Dict[str, Any]) -> Dict[str, Any]:
    """Budget-derived caps for the specialists. Pure function, unit-tested."""
    budget = float(params.get("budget_limit") or 0)
    days = max(int(params.get("days") or 1), 1)

    return {
        "flight_tier": "cheapest" if budget else "balanced",
        "hotel_nightly_cap": round(budget * HOTEL_SHARE / days) if budget else None,
        "food_budget": round(budget * FOOD_SHARE) if budget else None,
        "activity_budget": round(budget * ACTIVITY_SHARE) if budget else None,
        "interests": params.get("interests") or "",
    }


async def supervisor(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Set constraints for this round and announce the dispatch."""
    from app.agents.graph.actions import apply_actions

    revision = state.get("revision", 0)
    update: Dict[str, Any] = {}

    if revision == 0:
        constraints = initial_constraints(state["params"])
        applied: list = []
    else:
        delta, applied = apply_actions(state)
        constraints = delta["constraints"]
        if delta.get("params"):
            # shorten_stay is the only action that rewrites the trip itself.
            params = {**state["params"], **delta["params"]}
            update["params"] = params
            update["trip_params"] = params
        await emit(config, {
            "type": "revision",
            "round": revision,
            "actions": applied,
        })

    for agent_name in ("flight", "hotel", "local"):
        await emit(config, {
            "type": "agent_start",
            "agent": agent_name,
            "constraints": constraints,
        })

    update["constraints"] = constraints
    update["applied_actions"] = applied
    return update
