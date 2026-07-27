"""Graph wiring and the planner that drives it.

    intake ─┬─(chat)───────────────────────────────────────▶ synthesis ─▶ END
            └─(plan)─▶ supervisor ─┬─▶ flight_agent ─────┐
                          ▲        ├─▶ hotel_agent ──────┤   compose_budget
                          │        ├─▶ restaurant_agent ─┼─▶       ▼
                          │        └─▶ attraction_agent ─┘   compose_itinerary
                          │                                         │
                          └────────(revise)───────── critic ◀───────┘
                                                       │
                                                  (pass)▼
                                                   synthesis

`GraphPlanner` exposes the same interface as `TravelPlanningAgent`
(plan_trip_events / plan_trip / sync_plan_trip) so the API routes and the
eval harness treat the two planners interchangeably.
"""

from functools import lru_cache
from typing import Any, AsyncIterator, Dict
import asyncio
import logging
import time

from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.agents.graph.nodes.compose import budget_node, itinerary_node
from app.agents.graph.nodes.critic import critic, route_after_critic
from app.agents.graph.nodes.intake import intake, route_intake
from app.agents.graph.nodes.specialists import SPECIALISTS
from app.agents.graph.nodes.supervisor import supervisor
from app.agents.graph.nodes.synthesis import synthesis
from app.agents.graph.runtime import Runtime, config_for
from app.agents.graph.state import PlanState, empty_collected, initial_state
from app.agents.telemetry import record_run
from app.agents.travel_agent import TravelPlanningAgent

logger = logging.getLogger(__name__)

#: Supersteps allowed per run. A revision round costs about nine, and the
#: critic caps revisions at 3, so this only ever fires on a wiring bug.
RECURSION_LIMIT = 60

MIN_USEFUL_ANSWER_CHARS = 20


@lru_cache(maxsize=1)
def build_graph():
    """Compile the planner graph once; it holds no per-request state."""
    graph = StateGraph(PlanState)

    graph.add_node("intake", intake)
    graph.add_node("supervisor", supervisor)
    for name, node in SPECIALISTS.items():
        graph.add_node(name, node)
    # Node names may not collide with state keys, hence the compose_ prefix.
    graph.add_node("compose_budget", budget_node)
    graph.add_node("compose_itinerary", itinerary_node)
    graph.add_node("critic", critic)
    graph.add_node("synthesis", synthesis)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges(
        "intake", route_intake,
        {"supervisor": "supervisor", "synthesis": "synthesis"},
    )

    # Fan out to the specialists, then join on the budget node: LangGraph
    # runs it once every incoming branch has reported.
    for name in SPECIALISTS:
        graph.add_edge("supervisor", name)
        graph.add_edge(name, "compose_budget")

    graph.add_edge("compose_budget", "compose_itinerary")
    graph.add_edge("compose_itinerary", "critic")
    graph.add_conditional_edges(
        "critic", route_after_critic,
        {"supervisor": "supervisor", "synthesis": "synthesis"},
    )
    graph.add_edge("synthesis", END)

    return graph.compile()


class GraphPlanner:
    """Multi-agent planner: specialists choose, a critic checks, then answer."""

    def __init__(self, session_id: str, model_name: str = settings.model_name):
        self.session_id = session_id
        self.model_name = model_name
        # The v1 agent is kept as the shared helper surface: conversation
        # history, plan persistence and token streaming have one
        # implementation, used by both planners.
        self.agent = TravelPlanningAgent(session_id, model_name)

    async def plan_trip_events(self, user_query: str) -> AsyncIterator[Dict[str, Any]]:
        """Run the graph, forwarding node events as they happen.

        Nodes push to a queue rather than returning events, because graph
        state is only visible between supersteps — waiting for that would
        turn streaming into batching.
        """
        started = time.perf_counter()
        events: asyncio.Queue = asyncio.Queue()
        runtime = Runtime(
            agent=self.agent,
            events=events,
            max_revisions=settings.max_revisions,
        )
        outcome: Dict[str, Any] = {}
        done = object()

        async def run() -> None:
            try:
                outcome["state"] = await build_graph().ainvoke(
                    initial_state(
                        self.session_id, self.model_name, user_query,
                        settings.max_revisions,
                    ),
                    config_for(runtime, recursion_limit=RECURSION_LIMIT),
                )
            except Exception as e:               # noqa: BLE001 — reported to the user
                outcome["error"] = e
            finally:
                await events.put(done)

        task = asyncio.create_task(run())
        try:
            while True:
                event = await events.get()
                if event is done:
                    break
                yield event
        finally:
            if not task.done():
                task.cancel()

        error = outcome.get("error")
        if error is not None:
            logger.error("Graph planner error", exc_info=error)
            yield {
                "type": "result",
                "data": {
                    "success": False,
                    "error": str(error),
                    "response": f"I encountered an error while processing your request: {error}. "
                                "Please try again or rephrase your request.",
                    "session_id": self.session_id,
                },
            }
            return

        state = outcome.get("state") or {}
        final_text = state.get("final_text") or ""
        if len(final_text) < MIN_USEFUL_ANSWER_CHARS:
            final_text = ("I processed your request but couldn't generate a complete response. "
                          "Please try again or provide more details.")

        collected = state.get("collected_data") or empty_collected()
        if state.get("intent") == "plan_trip":
            self.agent.store_plan(collected)
            await record_run("graph", self.session_id, self.model_name, collected,
                             started, verdict=state.get("verdict"))
        self.agent.save_conversation(user_query, final_text)

        yield {
            "type": "result",
            "data": {
                "success": True,
                "response": final_text,
                "collected_data": collected,
                "session_id": self.session_id,
            },
        }

    async def plan_trip(self, user_query: str) -> Dict[str, Any]:
        """Non-streaming entry point; same return shape as the pipeline."""
        result: Dict[str, Any] = {
            "success": False,
            "response": "No response generated.",
            "session_id": self.session_id,
        }
        async for event in self.plan_trip_events(user_query):
            if event["type"] == "result":
                result = event["data"]
        return result

    def sync_plan_trip(self, user_query: str) -> Dict[str, Any]:
        """Synchronous wrapper around plan_trip."""
        try:
            return asyncio.run(self.plan_trip(user_query))
        except RuntimeError:
            # Already inside an event loop — run in a worker thread.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.plan_trip(user_query)).result()
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"Error: {e}",
                "session_id": self.session_id,
            }
