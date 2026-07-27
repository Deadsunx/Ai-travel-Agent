"""Intake node: extract trip parameters and route plan vs chat."""

from typing import Any, Dict

from app.agents.graph.runtime import runtime_of, status
from app.agents.graph.state import PlanState


async def intake(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """One structured-output call for the trip parameters.

    Delegates to the v1 agent so both planners extract identically; the only
    thing added here is the plan/chat routing decision, which v1 makes inline.
    """
    agent = runtime_of(config).agent

    await status(config, "🔍 Understanding your travel request...")
    params = await agent.extract_params(state["user_query"])

    plans = params.get("intent") == "plan_trip" and bool(params.get("destination"))
    if plans:
        await status(
            config,
            f"🌍 Planning {params['days']} days in {params['destination']} — "
            "searching live data...",
        )

    return {
        "params": params,
        "trip_params": params,
        "intent": "plan_trip" if plans else "chat",
    }


def route_intake(state: PlanState) -> str:
    """Chat and refinement turns skip the whole planning graph, as in v1."""
    return "supervisor" if state.get("intent") == "plan_trip" else "synthesis"
