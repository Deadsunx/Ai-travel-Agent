"""Prompts used inside the graph planner.

Only the critic needs one: every other decision in the graph is made by
code. The prompt is deliberately narrow — the model is asked to notice
things rules cannot (a museum and a beach 40 km apart on the same morning,
a plan that ignores what the traveller asked for), not to plan anything.
"""

import json
from typing import Any, Dict, List

#: The critic sees a compacted plan, never the raw API payloads: the whole
#: point of a second opinion is lost if it is spent reading JSON.
MAX_PLAN_CHARS = 4000


def compact_plan(state: Dict[str, Any]) -> str:
    """The plan as the critic should see it: decisions, days, money."""
    choices = {
        kind: {"item": (choice.get("item") or {}).get("name")
                       or (choice.get("item") or {}).get("airline"),
               "why": choice.get("rationale")}
        for kind, choice in (state.get("choices") or {}).items()
    }

    budget = state.get("budget") or {}
    days = []
    for day in (state.get("itinerary") or {}).get("days") or []:
        days.append({
            "day": day.get("day"),
            "morning": [a.get("activity") for a in day.get("morning") or []],
            "afternoon": [a.get("activity") for a in day.get("afternoon") or []],
            "evening": [a.get("activity") for a in day.get("evening") or []],
        })

    plan = {
        "trip": {
            "destination": (state.get("params") or {}).get("destination"),
            "days": (state.get("params") or {}).get("days"),
            "travelers": (state.get("params") or {}).get("travelers"),
            "interests": (state.get("params") or {}).get("interests"),
        },
        "chosen": choices,
        "cost": {
            "total": budget.get("total_with_buffer"),
            "limit": budget.get("budget_limit"),
            "within_budget": budget.get("within_budget"),
        },
        "itinerary": days,
    }
    return json.dumps(plan, ensure_ascii=False, default=str)[:MAX_PLAN_CHARS]


def get_critic_prompt(state: Dict[str, Any], found: List[Dict[str, Any]]) -> str:
    """Ask for the problems arithmetic cannot see."""
    already = "\n".join(f"- {issue['message']}" for issue in found) or "(none)"

    return f"""You are reviewing a travel plan before it is sent to the traveller.

Report only problems a reader would notice. Budget arithmetic, empty days and
repeated restaurants have already been checked — do not repeat them.

Look for:
- stops scheduled on the same day that are far apart
- a plan that ignores what the traveller asked for
- pacing that is unrealistic (too much in one day, nothing on another)
- anything internally contradictory

Output ONLY a JSON object, no markdown:

{{"issues": [{{"category": "feasibility"|"coherence"|"coverage",
              "message": "one sentence, specific"}}]}}

Report nothing rather than inventing a problem: {{"issues": []}} is a good
answer for a sound plan. Maximum three issues.

Already reported:
{already}

Plan:
{compact_plan(state)}

JSON:"""
