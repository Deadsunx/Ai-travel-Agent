"""Multi-agent travel planner (v2).

The v1 pipeline in `app.agents.travel_agent` runs a fixed sequence; this
package runs the same work as a LangGraph state machine so specialists can
make and explain choices, and a critic can send a plan back for a bounded
revision round.

Selected with PLANNER=graph or ChatRequest.planner="graph"; see
`app.agents.travel_agent.create_planner`.
"""

from app.agents.graph.build import GraphPlanner, build_graph

__all__ = ["GraphPlanner", "build_graph"]
