"""Revision actions — the closed vocabulary the critic may ask for.

A critic that can emit free-form instructions turns replanning into another
prompt-engineering problem, and small local models handle it badly. Instead
the critic picks from the operators below; each is a pure function
`(state, constraints, **args) -> delta`, so the whole revision loop is
testable without a model in the loop.

A delta may carry two sections:
  "constraints" — merged into the supervisor's constraints for the next round
  "params"      — merged into the trip parameters (only `shorten_stay` needs
                  this, and it is the one action that forces a refetch)
"""

from typing import Any, Callable, Dict, List, Tuple

from app.agents.data import cheapest
from app.agents.graph.state import PlanState

#: Actions that change the search itself; everything else re-filters data
#: that is already cached, which is what keeps a revision round cheap.
REFETCHING_ACTIONS = ("shorten_stay",)


def request(name: str, **args: Any) -> Dict[str, Any]:
    """Build one revision request. `args` must match the action's signature."""
    return {"name": name, "args": args}


def describe(req: Dict[str, Any]) -> str:
    """Display form, e.g. cheaper_hotels(ratio=0.75)."""
    args = ", ".join(f"{k}={v}" for k, v in (req.get("args") or {}).items())
    return f"{req['name']}({args})"


# ----------------------------------------------------------------------
# Operators
# ----------------------------------------------------------------------


def cheaper_hotels(state: PlanState, constraints: Dict[str, Any],
                   ratio: float = 0.75) -> Dict[str, Any]:
    """Tighten the nightly cap, then re-filter the cached hotel results."""
    cap = constraints.get("hotel_nightly_cap")
    if not cap:
        # No cap yet (no budget given): anchor on what the search actually found.
        cap = cheapest(state.get("hotels"), "hotels", "price_per_night")
    if not cap:
        return {}
    return {"constraints": {"hotel_nightly_cap": max(round(cap * ratio), 1)}}


def drop_paid_activities(state: PlanState, constraints: Dict[str, Any],
                         count: int = 2) -> Dict[str, Any]:
    """Cap how many paid activities the itinerary may schedule."""
    current = constraints.get("max_paid_activities")
    days = max(int((state.get("params") or {}).get("days") or 1), 1)
    ceiling = current if current is not None else days * 2
    return {"constraints": {"max_paid_activities": max(ceiling - count, 0)}}


def swap_flight(state: PlanState, constraints: Dict[str, Any],
                tier: str = "cheapest") -> Dict[str, Any]:
    """Re-select from the cached flight results on a different tier."""
    if tier not in ("cheapest", "balanced", "fastest"):
        tier = "cheapest"
    return {"constraints": {"flight_tier": tier}}


def shorten_stay(state: PlanState, constraints: Dict[str, Any],
                 days: int = 1) -> Dict[str, Any]:
    """Drop `days` from the trip. The only action that forces a refetch."""
    from datetime import datetime, timedelta

    params = dict(state.get("params") or {})
    current = int(params.get("days") or 1)
    new_days = max(current - max(days, 1), 1)
    if new_days == current:
        return {}

    params["days"] = new_days
    try:
        start = datetime.strptime(str(params["start_date"]), "%Y-%m-%d")
        params["end_date"] = (start + timedelta(days=new_days)).strftime("%Y-%m-%d")
    except (ValueError, KeyError, TypeError):
        pass
    return {"params": params}


def rebalance_days(state: PlanState, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Re-cluster the itinerary only — no API calls, no price changes."""
    return {"constraints": {"rebalance_days": True}}


def widen_hotel_search(state: PlanState, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Lift the nightly cap after it filtered every hotel away."""
    return {"constraints": {"hotel_nightly_cap": None}}


ActionFn = Callable[..., Dict[str, Any]]

REGISTRY: Dict[str, ActionFn] = {
    "cheaper_hotels": cheaper_hotels,
    "drop_paid_activities": drop_paid_activities,
    "swap_flight": swap_flight,
    "shorten_stay": shorten_stay,
    "rebalance_days": rebalance_days,
    "widen_hotel_search": widen_hotel_search,
}


def apply_actions(state: PlanState) -> Tuple[Dict[str, Any], List[str]]:
    """Fold the critic's requests into the next round's constraints/params.

    Unknown action names are skipped rather than raised: a malformed critic
    response must not take down a user's request.

    Returns (delta, applied) where delta has "constraints" (always) and
    "params" (only when an action changed the trip itself).
    """
    constraints: Dict[str, Any] = dict(state.get("constraints") or {})
    params: Dict[str, Any] = {}
    applied: List[str] = []

    for req in state.get("requests") or []:
        action = REGISTRY.get(req.get("name", ""))
        if action is None:
            continue
        try:
            delta = action(state, constraints, **(req.get("args") or {}))
        except TypeError:
            # Bad arguments from the critic — skip this one operator.
            continue
        if not delta:
            continue
        constraints.update(delta.get("constraints") or {})
        params.update(delta.get("params") or {})
        applied.append(describe(req))

    result: Dict[str, Any] = {"constraints": constraints}
    if params:
        result["params"] = params
    return result, applied


def needs_refetch(applied: List[str]) -> bool:
    """True when a revision changed the search, not just the filtering."""
    return any(name.split("(")[0] in REFETCHING_ACTIONS for name in applied)
