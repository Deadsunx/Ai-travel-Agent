"""The wiring itself: a mis-drawn edge is the failure mode that unit tests
of individual nodes cannot catch."""

from app.agents.graph.build import build_graph
from app.agents.graph.nodes.specialists import SPECIALISTS

SPECIALIST_NAMES = set(SPECIALISTS)


def _edges():
    return {(e.source, e.target) for e in build_graph().get_graph().edges}


def test_every_node_is_wired():
    nodes = {n for n in build_graph().get_graph().nodes if not n.startswith("__")}
    assert nodes == {
        "intake", "supervisor", "compose_budget", "compose_itinerary",
        "critic", "synthesis",
    } | SPECIALIST_NAMES


def test_intake_can_skip_planning():
    edges = _edges()
    assert ("intake", "supervisor") in edges
    assert ("intake", "synthesis") in edges


def test_specialists_fan_out_and_join_on_the_budget():
    edges = _edges()
    for name in SPECIALIST_NAMES:
        assert ("supervisor", name) in edges, f"{name} never dispatched"
        assert (name, "compose_budget") in edges, f"{name} never joined"


def test_the_revision_loop_closes():
    edges = _edges()
    assert ("compose_itinerary", "critic") in edges
    assert ("critic", "supervisor") in edges, "critic cannot request a revision"
    assert ("critic", "synthesis") in edges, "critic cannot pass a plan"


def test_the_graph_is_reused_not_recompiled():
    assert build_graph() is build_graph()
