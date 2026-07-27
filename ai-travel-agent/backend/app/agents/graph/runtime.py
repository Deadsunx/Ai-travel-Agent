"""Per-run wiring handed to the nodes through the LangGraph config.

Nodes need two things that do not belong in the graph state: somewhere to
push progress events as they happen (the state is only visible between
supersteps, which would defeat streaming), and the v1 agent instance whose
history/Redis/token-streaming helpers both planners share.

Both travel through `config["configurable"]`, which LangGraph passes to every
node untouched.
"""

from dataclasses import dataclass
from typing import Any, Dict
import asyncio

RUNTIME_KEY = "planner_runtime"


@dataclass
class Runtime:
    """Everything a node needs that is not planning state."""

    agent: Any                 # TravelPlanningAgent — the shared helper surface
    events: asyncio.Queue
    max_revisions: int


def runtime_of(config: Dict[str, Any]) -> Runtime:
    return config["configurable"][RUNTIME_KEY]


def config_for(runtime: Runtime, recursion_limit: int = 50) -> Dict[str, Any]:
    return {
        "configurable": {RUNTIME_KEY: runtime},
        "recursion_limit": recursion_limit,
    }


async def emit(config: Dict[str, Any], event: Dict[str, Any]) -> None:
    """Push one SSE event toward the client."""
    await runtime_of(config).events.put(event)


async def status(config: Dict[str, Any], message: str) -> None:
    """Push a v1-compatible status line."""
    await emit(config, {"type": "status", "message": message})
