"""The critic's deterministic rules.

Pure functions over a finished plan: state in, issues and revision requests
out. No model, no I/O — which is why the revision loop still works when a
local 8B returns malformed JSON, and why every rule can be tested by
constructing a plan rather than by running one.

Each rule that can be *fixed* pairs its issue with a request from the closed
action vocabulary in `actions.py`. Rules that only describe a problem
(too much estimated data) raise an issue with no request, and the plan is
delivered with the problem stated.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.agents.data import is_mock
from app.agents.graph.actions import request
from app.agents.graph.state import SECTIONS, Issue, PlanState

#: Over budget by more than this is treated as needing more than a cheaper
#: room — activities come out too.
SEVERE_OVERRUN = 1.3

#: How far the nightly cap may be cut in one round. Below the floor the
#: hotel search would return nothing useful, so activities are cut as well.
MIN_CAP_RATIO = 0.4
MAX_CAP_RATIO = 0.95

#: Estimated data in at least this many of the four sections is worth saying.
MOCK_SECTIONS_WORTH_NOTING = 2

SLOTS = ("morning", "afternoon", "evening")


def _issue(severity: str, category: str, message: str,
           action: Optional[str] = None) -> Issue:
    return {"severity": severity, "category": category,
            "message": message, "action": action}


def _money(value: float) -> str:
    return f"₹{round(value):,}"


def cap_ratio_for_overrun(budget: Dict[str, Any], nights: int,
                          hotel_nightly: float) -> Optional[float]:
    """How far the nightly cap must fall to close the gap, as a ratio.

    Asking for a specific reduction beats a blind "make it cheaper": the
    next round either lands inside the budget or proves it cannot.
    """
    total = float(budget.get("total_with_buffer") or 0)
    limit = float(budget.get("budget_limit") or 0)
    if not limit or total <= limit or not hotel_nightly or nights < 1:
        return None

    # The buffer is 10% of the subtotal, so a rupee cut from the room saves
    # about 1.1 rupees off the total.
    per_night_cut = (total - limit) / (nights * 1.1)
    return round(max((hotel_nightly - per_night_cut) / hotel_nightly, 0), 3)


def _meal_names(state: PlanState) -> List[str]:
    """Restaurants the local desk scheduled, in day order."""
    names = []
    for day in state.get("meal_plan") or []:
        for slot in ("lunch", "dinner"):
            place = (day or {}).get(slot) or {}
            if place.get("name"):
                names.append(place["name"])
    return names


# ----------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------


def check_budget(state: PlanState) -> Tuple[List[Issue], List[Dict[str, Any]]]:
    """The plan must cost no more than the traveller said they had."""
    budget = state.get("budget") or {}
    limit = float(budget.get("budget_limit") or 0)
    total = float(budget.get("total_with_buffer") or 0)
    if not limit or total <= limit:
        return [], []

    overrun = total / limit
    message = (f"Plan costs {_money(total)} against a {_money(limit)} budget "
               f"({round((overrun - 1) * 100)}% over)")

    nights = max(int((state.get("params") or {}).get("days") or 1), 1)
    hotel = ((state.get("choices") or {}).get("hotel") or {}).get("item") or {}
    try:
        nightly = float(hotel.get("price_per_night") or 0)
    except (TypeError, ValueError):
        nightly = 0

    requests: List[Dict[str, Any]] = []
    ratio = cap_ratio_for_overrun(budget, nights, nightly)

    if ratio is not None and ratio >= MIN_CAP_RATIO:
        requests.append(request("cheaper_hotels", ratio=min(ratio, MAX_CAP_RATIO)))
    elif nightly:
        # No room is cheap enough on its own; take what the room can give
        # and cut paid activities for the rest.
        requests.append(request("cheaper_hotels", ratio=MIN_CAP_RATIO))

    if overrun >= SEVERE_OVERRUN or (ratio is not None and ratio < MIN_CAP_RATIO):
        requests.append(request("drop_paid_activities", count=2))

    return [_issue("blocker", "budget", message,
                   requests[0]["name"] if requests else None)], requests


def check_day_coverage(state: PlanState) -> Tuple[List[Issue], List[Dict[str, Any]]]:
    """No day should be filled with placeholders while others have real places.

    Counting rows in the day plan cannot detect this: the itinerary template
    always emits the same number of slots and pads the ones it has no real
    place for. What matters is how the *found* sights were distributed, so
    that is what this reads.
    """
    clusters = state.get("sight_clusters")
    if not clusters:
        return [], []

    empty = [index + 1 for index, day in enumerate(clusters) if not day]
    if not empty:
        return [], []

    found = sum(len(day) for day in clusters)
    listed = ", ".join(str(d) for d in empty)

    if found < len(clusters):
        # Fewer sights than days: no redistribution can cover them all.
        return [_issue("note", "data_quality",
                       f"Only {found} sights found for {len(clusters)} days, so "
                       f"day {listed} falls back to generic suggestions")], []

    return (
        [_issue("warning", "coverage",
                f"Day {listed} has no real sight while other days have several",
                "rebalance_days")],
        [request("rebalance_days")],
    )


def check_duplicate_meals(state: PlanState) -> Tuple[List[Issue], List[Dict[str, Any]]]:
    """The same restaurant twice in one trip reads as a broken plan.

    When it happens because the search only found a handful of places, no
    rearrangement can fix it — that is reported as a data problem instead,
    so the loop does not burn a revision round on something unfixable.
    """
    names = _meal_names(state)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if not duplicates:
        return [], []

    available = len({r.get("name") for r in
                     ((state.get("restaurants") or {}).get("restaurants") or [])
                     if r.get("name")})
    listed = ", ".join(duplicates[:3]) + ("…" if len(duplicates) > 3 else "")

    if available < len(names):
        return [_issue("note", "data_quality",
                       f"Only {available} restaurants found for {len(names)} meals, "
                       f"so some repeat ({listed})")], []

    return (
        [_issue("warning", "coherence", f"Restaurant repeated across days: {listed}",
                "rebalance_days")],
        [request("rebalance_days")],
    )


def check_data_quality(state: PlanState) -> Tuple[List[Issue], List[Dict[str, Any]]]:
    """Say plainly when much of the plan rests on estimates."""
    estimated = [section for section in SECTIONS if is_mock(state.get(section))]
    if len(estimated) < MOCK_SECTIONS_WORTH_NOTING:
        return [], []

    return [_issue("note", "data_quality",
                   f"{', '.join(estimated)} are estimated, not live prices")], []


#: Order matters only for presentation; every rule runs.
RULES = (check_budget, check_day_coverage, check_duplicate_meals, check_data_quality)


def evaluate(state: PlanState) -> Tuple[List[Issue], List[Dict[str, Any]]]:
    """Run every rule plus whatever the specialists already raised."""
    issues: List[Issue] = list(state.get("specialist_issues") or [])
    requests: List[Dict[str, Any]] = []

    for rule in RULES:
        rule_issues, rule_requests = rule(state)
        issues.extend(rule_issues)
        requests.extend(rule_requests)

    # A specialist that could not honour its constraint says how to relax it.
    for issue in state.get("specialist_issues") or []:
        if issue.get("action") and not any(r["name"] == issue["action"] for r in requests):
            requests.append(request(issue["action"]))

    return issues, _resolve(requests)


def _resolve(requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One request per action, with contradictions removed.

    `widen_hotel_search` and `cheaper_hotels` pull the nightly cap in
    opposite directions: a plan that is over budget *and* found no room
    under the cap would otherwise widen, overrun, cheapen, find nothing,
    and widen again. Being over budget wins — there is no point relaxing a
    cap the total cannot afford anyway.
    """
    seen = set()
    unique = []
    for req in requests:
        if req["name"] in seen:
            continue
        seen.add(req["name"])
        unique.append(req)

    if "cheaper_hotels" in seen:
        unique = [r for r in unique if r["name"] != "widen_hotel_search"]
    return unique
