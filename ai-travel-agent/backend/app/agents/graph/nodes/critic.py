"""Critic node: decide whether the assembled plan is good enough to send.

The design is rules-first, model-second (M3): a deterministic pass catches
budget overrun, thin days, duplicate restaurants and date mismatches, and
only then does an LLM pass judge feasibility and pacing. That ordering is
what makes the loop survive a small local model returning malformed JSON —
the rules alone are enough to drive a revision.

At M1 the rule set is empty, so every plan passes and the graph produces
exactly what the v1 pipeline produces.
"""

from typing import Any, Dict, List, Tuple

from app.agents.graph.runtime import emit
from app.agents.graph.state import Issue, PlanState

#: Upper bound on revisions regardless of configuration — a user request must
#: terminate even if MAX_REVISIONS is set to something silly.
MAX_REVISIONS_CEILING = 3


def revision_budget(max_revisions: int) -> int:
    """How many revisions this run may actually spend."""
    return min(max(int(max_revisions or 0), 0), MAX_REVISIONS_CEILING)


def evaluate(state: PlanState) -> Tuple[List[Issue], List[Dict[str, Any]]]:
    """Deterministic plan checks. Returns (issues, revision requests).

    For now this only forwards what the specialists raised while choosing —
    a hotel that broke the nightly cap, say. Those come with no revision
    request yet, so a blocker ends as `give_up`: the plan is delivered with
    the problem stated rather than hidden, which is the honest M2 answer.
    The whole-plan rules (budget total, thin days, duplicate restaurants)
    and the requests that fix them arrive with M3.
    """
    return list(state.get("specialist_issues") or []), []


async def critic(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Score the plan and decide pass / revise / give_up."""
    issues, requests = evaluate(state)

    blockers = [i for i in issues if i.get("severity") == "blocker"]
    revision = state.get("revision", 0)
    budget = revision_budget(state.get("max_revisions", 0))

    if not blockers:
        verdict = "pass"
    elif revision < budget and requests:
        verdict = "revise"
    else:
        # Out of revisions: deliver the best plan we have and say so plainly.
        verdict = "give_up"

    await emit(config, {
        "type": "critique",
        "verdict": verdict,
        "issues": issues,
        "revision": revision,
    })

    update: Dict[str, Any] = {
        "verdict": verdict,
        "issues": issues,
        "requests": requests,
    }
    if verdict == "revise":
        update["revision"] = revision + 1
    return update


def route_after_critic(state: PlanState) -> str:
    """Loop back for another round, or write the answer."""
    return "supervisor" if state.get("verdict") == "revise" else "synthesis"
