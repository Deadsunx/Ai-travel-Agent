"""Typed state for the multi-agent planner graph.

The data keys (flights / hotels / restaurants / attractions / budget /
itinerary / search_results / trip_params) deliberately match the v1
pipeline's `collected` dict, so the synthesis prompt, the frontend and the
database schema are unchanged by v2. `to_collected()` is the single place
that projects graph state back onto that shape.

Kept free of LangGraph and LangChain imports so it is unit-testable with
minimal dependencies.
"""

from typing import Any, Dict, List, Literal, Optional
# typing_extensions, not typing: on Python < 3.12 pydantic cannot build a
# schema from typing.TypedDict, which breaks graph introspection (and so the
# diagram export) even though execution works.
from typing_extensions import Annotated, TypedDict
import operator

Intent = Literal["plan_trip", "chat"]
Verdict = Literal["pass", "revise", "give_up"]
Severity = Literal["blocker", "warning", "note"]
Category = Literal["budget", "coverage", "feasibility", "data_quality", "coherence"]

#: Sections fetched by the specialist nodes, in event-label order.
SECTIONS = ("flights", "hotels", "restaurants", "attractions")

#: Keys of the v1 `collected_data` payload, in v1's insertion order.
COLLECTED_KEYS = (
    "flights", "hotels", "restaurants", "attractions",
    "budget", "itinerary", "search_results", "trip_params",
)


class Choice(TypedDict, total=False):
    """One specialist decision, kept with its reasoning for the trace UI."""
    kind: Literal["flight", "hotel", "restaurant", "attraction"]
    item: Dict[str, Any]          # the option that was selected
    rationale: str                # one sentence, shown next to the choice
    alternatives: List[Dict[str, Any]]   # runners-up, for "show other options"


class Issue(TypedDict, total=False):
    """A problem the critic found with the current plan."""
    severity: Severity
    category: Category
    message: str
    action: Optional[str]         # a RevisionAction name, see actions.py


def merge_choices(left: Optional[Dict[str, Choice]],
                  right: Optional[Dict[str, Choice]]) -> Dict[str, Choice]:
    """Reducer for `choices`: later picks replace earlier ones for the same kind.

    Keyed by kind rather than appended to a list because a revision round
    re-runs the specialists — with an append reducer the second round's
    choices would pile on top of the first round's instead of replacing them.
    """
    return {**(left or {}), **(right or {})}


class PlanState(TypedDict, total=False):
    """Shared state threaded through every node.

    Only `choices` and `applied_actions` are written by concurrently running
    nodes, so only they need a reducer; every other key is written by exactly
    one node per superstep.
    """

    # --- inputs
    session_id: str
    model_name: str
    user_query: str

    # --- intake
    params: Dict[str, Any]        # resolve_trip_params() output
    intent: Intent

    # --- supervisor directives, rewritten on each revision
    constraints: Dict[str, Any]

    # --- specialist output (v1-compatible keys)
    flights: Optional[Dict[str, Any]]
    hotels: Optional[Dict[str, Any]]
    restaurants: Optional[Dict[str, Any]]
    attractions: Optional[Dict[str, Any]]
    budget: Optional[Dict[str, Any]]
    itinerary: Optional[Dict[str, Any]]
    search_results: List[Any]
    trip_params: Dict[str, Any]

    # --- local desk layout (per day)
    meal_plan: List[Dict[str, Any]]          # [{lunch, dinner}] for each day
    sight_clusters: List[List[Dict[str, Any]]]   # sights grouped by area

    # --- v2 decision trail
    choices: Annotated[Dict[str, Choice], merge_choices]
    specialist_issues: List[Issue]   # raised while selecting, judged by the critic
    issues: List[Issue]
    requests: List[Dict[str, Any]]   # revision requests, see actions.request()
    applied_actions: Annotated[List[str], operator.add]
    revision: int
    max_revisions: int
    verdict: Verdict

    # --- synthesis output
    final_text: str
    collected_data: Dict[str, Any]


def empty_collected(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The v1 `collected` skeleton, with every section unset."""
    collected: Dict[str, Any] = {key: None for key in COLLECTED_KEYS}
    collected["search_results"] = []
    collected["trip_params"] = params if params is not None else {}
    return collected


def to_collected(state: PlanState) -> Dict[str, Any]:
    """Project graph state onto the v1 `collected_data` payload.

    Extra v2 keys (choices, issues) are added only when non-empty, so a plan
    produced without any specialist decisions is byte-identical to v1's.
    """
    collected = empty_collected(state.get("params") or {})
    for key in COLLECTED_KEYS:
        if key in ("search_results", "trip_params"):
            continue
        collected[key] = state.get(key)
    collected["search_results"] = state.get("search_results") or []

    if state.get("choices"):
        # Keyed by kind in the state; a list is what the UI and the DB want.
        collected["choices"] = list(state["choices"].values())
    if state.get("issues"):
        collected["issues"] = state["issues"]
    if state.get("revision"):
        collected["revisions"] = state["revision"]
    return collected


def initial_state(
    session_id: str,
    model_name: str,
    user_query: str,
    max_revisions: int,
) -> PlanState:
    """Fresh state for one planning run."""
    return {
        "session_id": session_id,
        "model_name": model_name,
        "user_query": user_query,
        "params": {},
        "constraints": {},
        "search_results": [],
        "choices": {},
        "specialist_issues": [],
        "issues": [],
        "requests": [],
        "applied_actions": [],
        "revision": 0,
        "max_revisions": max_revisions,
        "verdict": "pass",
    }
