"""Critic node: decide whether the assembled plan is good enough to send.

Rules first, model second. The deterministic pass in `graph/rules.py`
catches budget overrun, thin days, repeated restaurants and estimated data,
and it is the only thing that can drive a revision. The LLM pass runs
afterwards and is strictly advisory: it can add an observation a reader
would notice, but it cannot request an action and its issues are clamped
below blocker severity.

That split is what makes the loop survive a small local model. If the
critic model returns nothing usable, the plan is still checked, still
revised when it must be, and still terminates.
"""

from typing import Any, Dict, List, Tuple
import asyncio
import logging

from app.agents.graph.prompts import get_critic_prompt
from app.agents.graph.rules import evaluate as evaluate_rules
from app.agents.graph.runtime import emit, runtime_of
from app.agents.graph.state import Issue, PlanState
from app.agents.streaming import strip_think
from app.config import settings
from app.tools import _extract_json_payload

logger = logging.getLogger(__name__)

#: Upper bound on revisions regardless of configuration — a user request must
#: terminate even if MAX_REVISIONS is set to something silly.
MAX_REVISIONS_CEILING = 3

#: The advisory pass may not raise a blocker, so it can never drive the loop.
LLM_MAX_SEVERITY = "warning"
LLM_MAX_ISSUES = 3
LLM_CATEGORIES = ("feasibility", "coherence", "coverage")

#: Seconds for the critic call; it is optional, so it fails fast.
CRITIC_TIMEOUT = 45


def revision_budget(max_revisions: int) -> int:
    """How many revisions this run may actually spend."""
    return min(max(int(max_revisions or 0), 0), MAX_REVISIONS_CEILING)


def parse_llm_issues(raw: str) -> List[Issue]:
    """Read the advisory pass's reply, keeping only well-formed issues."""
    payload = _extract_json_payload(strip_think(raw or "")) or {}
    if not isinstance(payload, dict):
        return []

    issues: List[Issue] = []
    for item in (payload.get("issues") or [])[:LLM_MAX_ISSUES]:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "").strip()
        if not message:
            continue
        category = str(item.get("category") or "coherence")
        issues.append({
            "severity": LLM_MAX_SEVERITY,
            "category": category if category in LLM_CATEGORIES else "coherence",
            "message": message[:300],
            "action": None,
        })
    return issues


async def _advisory_issues(state: PlanState, config: Dict[str, Any],
                           found: List[Issue]) -> List[Issue]:
    """Ask the model for what the rules cannot see. Never fatal."""
    agent = runtime_of(config).agent
    prompt = get_critic_prompt(state, found)

    try:
        response = await asyncio.wait_for(
            agent.llm.ainvoke(prompt), timeout=CRITIC_TIMEOUT
        )
        raw = response.content if hasattr(response, "content") else str(response)
        return parse_llm_issues(raw)
    except Exception as e:
        logger.info("Advisory critic unavailable (%s); rules stand alone", e)
        return []


async def critic(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Score the plan and decide pass / revise / give_up."""
    issues, requests = evaluate_rules(state)

    if settings.critic_advisory_pass:
        issues = issues + await _advisory_issues(state, config, issues)

    blockers = [i for i in issues if i.get("severity") == "blocker"]
    revision = state.get("revision", 0)
    budget = revision_budget(state.get("max_revisions", 0))

    if not blockers:
        verdict = "pass"
    elif revision < budget and requests:
        verdict = "revise"
    else:
        # Out of revisions, or nothing left to try: deliver the best plan we
        # have and say plainly what is wrong with it.
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
        "requests": requests if verdict == "revise" else [],
    }
    if verdict == "revise":
        update["revision"] = revision + 1
    return update


def route_after_critic(state: PlanState) -> str:
    """Loop back for another round, or write the answer."""
    return "supervisor" if state.get("verdict") == "revise" else "synthesis"
