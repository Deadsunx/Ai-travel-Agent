# Multi-Agent Travel Orchestrator — v2 Specification

**Status:** M0–M5 landed and verified end to end. Open follow-up: the golden
set still lacks a case with a *closable* budget gap, so the revision loop is
proven by construction and by trace rather than by the eval (see §9).
**Branch:** `feat/multi-agent-orchestrator`
**Baseline:** the deterministic pipeline in `backend/app/agents/travel_agent.py` (v1)

---

## 1. Why v2

v1 is a **fixed pipeline**: extract params → fetch flights/hotels/restaurants/attractions in
parallel → compute budget → build an itinerary skeleton → stream one synthesis call.
It is fast and reliable, but it has no judgment:

| v1 limitation | Observable symptom |
|---|---|
| No selection logic — the LLM sees every result | Picks a ₹40 000 flight for a ₹30 000 trip and hopes prose covers it |
| Budget is computed *after* choices are locked | `budget.remaining` can be negative and nothing reacts |
| No feedback loop | A bad plan is streamed to the user as-is |
| No per-decision provenance | "Why this hotel?" is unanswerable |
| Single synthesis prompt does all reasoning | Quality tracks model size; small local models degrade badly |

v2 keeps the fast path and adds **specialist agents that make defensible choices** and a
**critic that can reject the plan and force a bounded replan**.

### Non-goals

- Not replacing the tools, mock fallback, Redis cache, DB, or SSE transport — all reused.
- Not free-form agent-to-agent chatter. Replan actions are a **closed enum** (§5.3) so
  `qwen3:8b` stays reliable.
- Not removing v1. It stays as the `pipeline` planner and as the eval baseline.

---

## 2. Architecture

```
                    ┌──────────┐
   user message ───▶│  intake  │  param extraction + intent routing (reuse v1)
                    └────┬─────┘
                         │ intent=chat ──────────────────────────┐
                         │ intent=plan_trip                      │
                    ┌────▼───────┐                               │
              ┌────▶│ supervisor │  sets constraints per specialist
              │     └────┬───────┘                               │
              │          │ fan-out (parallel)                    │
              │   ┌──────┼──────────────┬─────────────┐          │
              │   ▼      ▼              ▼             │          │
              │ flight  hotel         local           │          │
              │ agent   agent         agent           │          │
              │   │      │              │             │          │
              │   └──────┴──────┬───────┘             │          │
              │           ┌─────▼──────┐                         │
              │           │   budget   │  deterministic          │
              │           └─────┬──────┘                         │
              │           ┌─────▼──────┐                         │
              │           │ itinerary  │  grounded skeleton      │
              │           └─────┬──────┘                         │
              │           ┌─────▼──────┐                         │
              │           │   critic   │  rules + LLM            │
              │           └─────┬──────┘                         │
              │      REVISE     │  PASS                          │
              └─────────────────┤                                │
                          ┌─────▼──────┐                         │
                          │ synthesis  │◀────────────────────────┘
                          └─────┬──────┘
                                ▼  streaming tokens → SSE
```

**Framework:** LangGraph (`langgraph>=0.2`) — chosen over hand-rolled async because it gives
parallel fan-out, conditional edges, and a typed state object for free, and because
`astream_events` maps cleanly onto the SSE contract you already have.

**Model routing** (reuses `get_llm()` in `travel_agent.py:72`):

| Node | Model | Rationale |
|---|---|---|
| intake | `ollama_native.complete_without_thinking` | already ~20× faster, keep it |
| specialists | same local model, `temperature=0` | short structured picks |
| critic | `settings.critic_model` (default = main model) | can be pointed at Gemini for quality runs |
| synthesis | main model, streaming | unchanged from v1 |

---

## 3. State

New file `backend/app/agents/graph/state.py`:

```python
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
import operator

class Choice(TypedDict):
    """One specialist decision, with its reasoning, for the trace UI."""
    kind: Literal["flight", "hotel", "restaurant", "attraction"]
    item: Dict[str, Any]        # the raw option that was selected
    rationale: str              # one sentence, shown in the UI
    alternatives: List[Dict]    # runners-up, for "show other options"

class Issue(TypedDict):
    severity: Literal["blocker", "warning", "note"]
    category: Literal["budget", "coverage", "feasibility", "data_quality", "coherence"]
    message: str
    action: Optional[str]       # a RevisionAction name, see actions.py

class PlanState(TypedDict, total=False):
    # --- inputs
    session_id: str
    model_name: str
    user_query: str
    history_text: str

    # --- intake
    params: Dict[str, Any]              # output of resolve_trip_params()
    intent: Literal["plan_trip", "chat"]

    # --- supervisor directives (rewritten each revision)
    constraints: Dict[str, Any]         # {"hotel_nightly_cap": 4000, "flight_tier": "cheapest", ...}

    # --- specialist raw data (same keys as v1 `collected`, for compatibility)
    flights: Optional[Dict]
    hotels: Optional[Dict]
    restaurants: Optional[Dict]
    attractions: Optional[Dict]
    budget: Optional[Dict]
    itinerary: Optional[Dict]
    trip_params: Dict[str, Any]

    # --- v2 additions
    choices: Annotated[List[Choice], operator.add]
    issues: List[Issue]
    revision: int
    max_revisions: int
    applied_actions: Annotated[List[str], operator.add]
    verdict: Literal["pass", "revise", "give_up"]
```

> The keys `flights / hotels / restaurants / attractions / budget / itinerary / search_results /
> trip_params` are deliberately identical to v1's `collected` dict so
> `get_synthesis_prompt()`, `ItineraryDisplay.tsx`, and the DB schema need **zero** changes.

---

## 4. Nodes

### 4.1 `intake`
Straight lift of `TravelPlanningAgent._extract_params` (`travel_agent.py:128`). Sets
`params`, `intent`. Conditional edge: `intent == "chat"` → jump to `synthesis` with the
stored-plan chat prompt (v1 behaviour preserved exactly).

### 4.2 `supervisor`
**Revision 0: fully deterministic** (no LLM call — protects latency):

```python
budget = params["budget_limit"]
days   = params["days"]
constraints = {
    "flight_tier":       "cheapest" if budget else "balanced",
    "hotel_nightly_cap": (budget * 0.35 / days) if budget else None,
    "activity_budget":   (budget * 0.15) if budget else None,
    "food_budget":       (budget * 0.20) if budget else None,
    "interests":         params.get("interests") or [],
}
```

**Revision ≥ 1:** applies the `RevisionAction`s the critic asked for (§5.3) to the previous
constraints. Still no free-form LLM planning — the action enum *is* the plan language.

Emits `agent_start` events for the specialists it is about to dispatch.

### 4.3 Specialists (parallel branch)

All three wrap the existing sync tools in `asyncio.to_thread`, exactly as v1 does
(`travel_agent.py:187`). What's new is the **selection step** after the fetch.

**`flight_agent`** — `flight_search(...)` → score each option:
`score = normalized_price * w_price + normalized_duration * w_time`, with `w_price=0.7`
under a budget constraint, `0.4` otherwise. Emits a `Choice` with a rationale like
*"IndiGo ₹4 812 — cheapest non-stop; the ₹4 200 option adds a 6 h layover."*

**`hotel_agent`** — `hotel_search(...)` → filter to `price_per_night <= hotel_nightly_cap`,
then rank by `rating`. If the filter empties the list, do **not** silently widen: keep the
cheapest and raise a `data_quality`/`budget` issue so the critic sees it.

**`local_agent`** — `restaurant_finder` + `attraction_finder` (both already OSM-backed via
`places_api.py`), then **geographic clustering**: group by lat/lon into `days` clusters
(simple k-means or grid buckets — `search_attractions_osm` already returns coordinates), so
day N's morning and afternoon are not 40 km apart. Enforces no restaurant repeats across days.

### 4.4 `budget`
Unchanged call to `budget_calculator` (`tools/__init__.py:218`), but fed the **chosen**
flight/hotel prices from `state["choices"]` instead of `min()` over everything
(v1 `_cheapest`, `travel_agent.py:221`). This is what makes the budget number honest.

### 4.5 `itinerary`
`itinerary_builder` fed the clustered, de-duplicated names from `local_agent`.

### 4.6 `critic`

Two passes, deterministic first — cheap, and it means the loop still works if the LLM
returns garbage JSON.

**Pass A — rules (pure Python, no LLM):**

| Rule | Severity | Suggested action |
|---|---|---|
| `budget.total > budget.budget_limit * 1.0` | blocker | `cheaper_hotels` |
| `budget.total > limit * 1.3` | blocker | `cheaper_hotels` + `drop_paid_activities` |
| any day with `< 3` activities | warning | `rebalance_days` |
| duplicate restaurant across days | warning | `rebalance_days` |
| `≥ 2` of 4 sections are `source.startswith("Mock")` | note | none (annotate confidence) |
| flight dates ≠ `params.start_date/end_date` | blocker | `swap_flight` |
| chosen hotel nights ≠ `days - 1` | warning | none |

**Pass B — LLM critic** (structured output, one call, `temperature=0`): geographic
feasibility, interest coverage vs `params["interests"]`, pacing, and internal contradictions.
Prompt gets the compacted plan (choices + itinerary + budget), **not** the raw API dumps.

Verdict: `revise` if any blocker and `revision < max_revisions`; else `pass`
(warnings are passed through to synthesis so the prose can hedge honestly).

### 4.7 `synthesis`
Reuses `_stream_llm` (`travel_agent.py:291`) and `ThinkFilter` untouched. The prompt gains
two blocks: the `Choice` rationales, and any surviving warnings ("say plainly that the plan
is 8% over budget"). Extend `get_synthesis_prompt()` with optional `choices` / `issues` args
so the v1 call site keeps working.

---

## 5. The revision loop

### 5.1 Bound
`max_revisions = settings.max_revisions` (default **1** for local models, 2 for Gemini).
Hard cap 3. On exhaustion: `verdict = "give_up"`, plan is delivered with an explicit
"couldn't fit your budget, here's the closest" framing — never an infinite loop, never a
silent failure.

### 5.2 Cache reuse — the thing that makes replans affordable
Tool results are already Redis-cached by `_get_cached/_set_cache` (`tools/__init__.py:71`).
A replan with a *tighter cap* re-filters the **same cached result set** rather than re-hitting
SerpAPI. Only actions that change the query itself (`swap_flight` with new dates,
`shorten_stay`) trigger a real refetch. Budget a replan at ~2–4 s, not 20 s.

### 5.3 `RevisionAction` enum — `graph/actions.py`

```python
cheaper_hotels(cap_ratio: float)      # tighten hotel_nightly_cap by ratio, re-filter cache
drop_paid_activities(n: int)          # replace n costliest activities with free ones
swap_flight(tier: Literal[...])       # re-select from cached flights on a different tier
shorten_stay(days: int)               # reduce trip length, refetch (expensive — last resort)
rebalance_days()                      # re-cluster itinerary only, no API calls
widen_hotel_search()                  # only when hotel filter returned empty
```

Each is a pure function `(PlanState, args) -> constraints_delta`. Unit-testable without any
model. **This is the core of the project** — the intelligence lives in bounded, testable
operators, not in prompt strings.

---

## 6. Streaming contract

Additive only. Existing types (`status`, `token`, `result`, `error`, `cancelled`) keep their
exact shape, so an un-updated frontend still works.

```jsonc
{"type": "agent_start",  "agent": "hotel",  "constraints": {"nightly_cap": 4000}}
{"type": "agent_result", "agent": "hotel",  "count": 8, "source": "Booking.com",
                         "choice": {"name": "...", "rationale": "..."}}
{"type": "critique",     "verdict": "revise", "issues": [{"severity":"blocker", ...}]}
{"type": "revision",     "round": 1, "actions": ["cheaper_hotels(0.75)"]}
```

`chat.py` (`api/routes/chat.py:36`) changes only in which planner it instantiates; the
`async for event in ...` loop and SSE framing are untouched.

---

## 7. Persistence & observability

New table (Alembic-less, same pattern as `models/database.py`):

```sql
CREATE TABLE plan_runs (
  id            SERIAL PRIMARY KEY,
  run_id        UUID UNIQUE NOT NULL,
  session_id    VARCHAR(64) NOT NULL,
  planner       VARCHAR(16) NOT NULL,      -- 'pipeline' | 'graph'
  model_name    VARCHAR(64) NOT NULL,
  params        JSONB,
  choices       JSONB,
  issues        JSONB,
  revisions     INT DEFAULT 0,
  verdict       VARCHAR(16),
  latency_ms    INT,
  tool_calls    INT,
  created_at    TIMESTAMP DEFAULT NOW()
);
```

This single table is what turns "I built a multi-agent system" into "here is the measured
effect of the critic loop." It also seeds project idea #6 (eval platform) later.

---

## 8. Frontend changes

| File | Change |
|---|---|
| `lib/types.ts` | add `AgentEvent`, `Critique`, `Choice` types |
| `components/agents/AgentTimeline.tsx` | **new** — one lane per specialist, live status, critic verdict badge, revision rounds as a vertical thread |
| `components/agents/ChoiceCard.tsx` | **new** — chosen option + rationale + "show 3 alternatives" |
| `components/chat/ChatInterface.tsx` | handle new event types; `default:` case ignores unknown types (forward compatible) |
| `components/ui/SourceLedger.tsx` | reuse as-is for provenance |
| `components/itinerary/BudgetBreakdown.tsx` | add an "over budget → revised" delta badge |

The timeline is the demo. A reviewer watching three lanes fill in parallel, a red critic
badge, and the hotel lane re-running with a tighter cap *sees* the architecture.

---

## 9. Evals — how v2 is proven better

Extend `backend/evals/golden_queries.json` with assertions the current suite can't express:

```jsonc
{
  "id": "goa_tight_budget",
  "query": "Plan a 3-day trip to Goa from Mumbai under 15000 rupees",
  "expect_plan": true,
  "expect_budget_respected": true,        // NEW: budget.total <= budget_limit
  "expect_min_activities_per_day": 3,     // NEW
  "expect_no_duplicate_restaurants": true // NEW
}
```

Add ~8 adversarial cases: impossibly tight budget, 14-day trip, conflicting interests,
unknown destination, past dates, single traveler + luxury tier.

`run_evals.py` gains `--planner {pipeline,graph}` and `--compare`, printing:

```
                        pipeline    graph
pass rate                 71%        94%
budget violations          6/17       1/17
avg revisions              n/a       0.8
p50 latency               11.2s     14.6s
```

**That table is the deliverable.** Design the harness so it can produce it before you build
the critic — otherwise you'll be tempted to skip it.

---

## 10. Files

**New** (✅ = already on the branch)
```
backend/app/agents/data.py                 ✅ safe_load/cheapest/is_mock, shared by both planners
backend/app/agents/graph/__init__.py       ✅
backend/app/agents/graph/state.py          ✅ PlanState, Choice, Issue, to_collected()
backend/app/agents/graph/runtime.py        ✅ Runtime + emit(), passed via LangGraph config
backend/app/agents/graph/actions.py        ✅ revision operators + apply_actions()
backend/app/agents/graph/selection.py      ✅ how a specialist picks, and says why
backend/app/agents/graph/build.py          ✅ wiring, compile(), GraphPlanner driver
backend/app/agents/graph/nodes/intake.py       ✅
backend/app/agents/graph/nodes/supervisor.py   ✅
backend/app/agents/graph/nodes/specialists.py  ✅ fetch only until M2
backend/app/agents/graph/nodes/compose.py      ✅ budget + itinerary nodes
backend/app/agents/graph/nodes/critic.py       ✅ shape final, rules empty until M3
backend/app/agents/graph/nodes/synthesis.py    ✅
backend/app/agents/graph/prompts.py        # critic + specialist prompts (M3)
backend/tests/test_actions.py              ✅
backend/tests/test_graph_state.py          ✅
backend/tests/test_graph_build.py          ✅ topology guard
backend/tests/test_graph_parity.py         ✅ shape contract + the M2 divergence
backend/tests/test_selection.py            ✅
backend/tests/test_critic_rules.py         # M3
frontend/components/agents/AgentTimeline.tsx   # M4
frontend/components/agents/ChoiceCard.tsx      # M4
```

Node names carry a `compose_` prefix (`compose_budget`, `compose_itinerary`)
because LangGraph forbids a node name that collides with a state key.

**Modified**
```
backend/app/agents/travel_agent.py    # unchanged logic + create_planner(name) factory
backend/app/agents/prompts.py         # get_synthesis_prompt(..., choices=None, issues=None)
backend/app/api/routes/chat.py        # planner selection from request/env
backend/app/models/schemas.py         # ChatRequest.planner, plan_runs schemas
backend/app/models/database.py        # plan_runs table
backend/app/config.py                 # PLANNER, MAX_REVISIONS, CRITIC_MODEL
backend/requirements.txt              # langgraph
backend/evals/golden_queries.json     # new assertions + adversarial cases
backend/evals/run_evals.py            # --planner, --compare
frontend/lib/types.ts
frontend/components/chat/ChatInterface.tsx
README.md, PROJECT_WALKTHROUGH.md     ✅ rewritten around the two planners
```

---

## 11. Milestones

| # | Deliverable | Done when | Est. |
|---|---|---|---|
| **M0** ✅ | Scaffolding + planner flag | `PLANNER=graph` routes to a stub that returns v1's answer; `PLANNER=pipeline` is default and untouched | 0.5 d |
| **M1** ✅ | Graph parity | LangGraph reproduces v1 end-to-end; `test_graph_parity.py` shows identical `collected` keys; eval pass rate ≥ pipeline | 2 d |
| **M2** ✅ | Specialists with judgment | flight/hotel/local emit `Choice` + rationale; budget uses chosen prices; clustering removes duplicates | 2 d |
| **M3** ✅ | Critic + revision loop | rule critic + LLM critic; ≥1 golden case demonstrably goes blocker → revise → pass; `max_revisions` respected | 2 d |
| **M4** ✅ | Timeline UI + `plan_runs` | live agent lanes, critic badge, revision thread; every run persisted | 1.5 d |
| **M5** ✅ | Eval comparison + docs | `--compare` table produced; READMEs corrected; walkthrough updated with the v1→v2 story | 1 d |

The harness half of M5 was pulled forward and is already on the branch
(`--planner`, `--compare`, and the plan-quality assertions), so every later
milestone can be measured the day it lands instead of at the end.

**~9 days part-time.** M0–M1 are the risky part; if M1 doesn't reach parity, stop and
diagnose rather than piling the critic on top of a broken graph.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| `qwen3:8b` returns malformed critic JSON | Rule critic runs first and is sufficient alone; LLM critic gets one retry then is skipped (logged as `data_quality` note) |
| Latency doubles from replans | `max_revisions=1` default; Redis cache re-filter instead of refetch (§5.2); p50 budget of v1 + 40% enforced as an eval assertion |
| Scope creep into RAG / booking / auth | Explicitly out of scope; they are separate project ideas |
| Parallel branches race on shared state | Only `choices` / `applied_actions` are concurrently written, both via `operator.add` reducers; everything else is written by exactly one node |
| Losing a working demo mid-refactor | v1 stays the default planner until M3's evals pass; `feat/` branch, `main` always demoable |

---

## 13. What this project teaches (PBL framing)

- Graph-based agent orchestration and typed shared state (LangGraph)
- Parallel fan-out/fan-in with bounded latency
- **Self-critique loops with termination guarantees** — the genuinely hard part
- Constraint propagation: a budget that actually constrains, instead of decorating
- Agent observability: decision traces, per-run metrics, provenance in the UI
- Empirical evaluation of an AI system: an A/B harness against your own prior architecture
