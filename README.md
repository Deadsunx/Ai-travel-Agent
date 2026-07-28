# AI Travel Agent

Ask for a trip in a sentence and get a costed, day-by-day itinerary back — with
real flight, hotel and place data, and a budget the plan is actually held to.

Next.js 14 frontend, FastAPI backend, PostgreSQL and Redis, all under Docker
Compose. The planning itself can run two different ways, and both are kept in
the repo so the comparison between them is checkable.

- [PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md) — the full tour
- [WORKFLOW_DIAGRAMS.md](WORKFLOW_DIAGRAMS.md) — Mermaid diagrams of both flows
- [MULTI_AGENT_SPEC.md](MULTI_AGENT_SPEC.md) — the graph planner's design

## Two planners, and why both are still here

| Planner | What it does |
| --- | --- |
| `graph` (default) | A LangGraph state machine. A supervisor turns the budget into hard constraints; three specialist desks — flights, stays, places — run in parallel and each explains its pick; a critic checks the assembled plan against those constraints and can send it back for one bounded revision round with a specific instruction. |
| `pipeline` | Extract parameters, fetch every source in parallel, cost the trip, write the answer. One pass, no selection, no critic. |

The graph is the default because it wins the golden-query comparison **15/16
against 13/16** — it fixes both duplicate-restaurant failures and keeps a plan
inside its budget. It costs roughly **17% more latency**, and `PLANNER=pipeline`
buys that back.

The pipeline is not retired. It is the control: without it there is no way to
show the graph is earning its extra complexity, and "the multi-agent version is
better" is an assertion rather than a measurement. Either can be selected per
request via `"planner"` in the chat payload, so the two answer the same query:

```bash
docker compose exec backend python -m evals.run_evals --compare
```

## How it got here

The first version was a LangChain ReAct agent — the model chose tools in a loop.
It worked, and it was untestable: the same query took different paths on
different runs, so a regression was indistinguishable from the model having a
different idea that day.

That became a deterministic pipeline: pull the parameters out of the request
first, then fetch everything in parallel and cost it. Predictable, and cheap to
put tests and an eval harness around — which is what made the next step
measurable rather than a matter of taste.

The graph planner then reintroduced genuine agency, but in a shape that can be
held to account: named nodes, explicit state, and a critic whose objections are
rules that can be unit-tested. The pipeline stayed as the baseline it is
measured against.

## Request trace

A chat request on the default planner:

```
POST /api/chat
  intake       normalise the request into trip parameters
  supervisor   derive hard constraints from the budget
  specialists  flights · stays · places, in parallel, each justifying its pick
  compose      assemble a candidate day-by-day plan
  critic       check the plan against the constraints
               └─ fails? one bounded revision round with a specific instruction
  synthesis    stream the written answer back over SSE
```

Every run is recorded, so the two planners can be compared on real traffic
rather than on impressions. Streaming responses can be cancelled mid-flight.

## Data sources, and the fallback layer

| Tool | Source | Needs a key |
| --- | --- | --- |
| Flights | SerpAPI (Google Flights) | yes |
| Hotels | RapidAPI (Booking.com) | yes |
| Places | OpenStreetMap (Overpass) | no |
| General search | Google Search | yes |

Every one of them has a mock fallback, and that is a deliberate design choice
rather than a convenience. Three of the four sources are rate-limited free
tiers: a demo that dies on a 429 in front of an audience is worse than one that
degrades. So a missing key or a rate-limit response falls back to realistic
estimated data **and says which source is estimated and why**, rather than
silently presenting a guess as a live price.

It also means the whole stack runs with no keys at all, which is what lets the
test suite be fully offline.

## Tests

```bash
cd ai-travel-agent/backend
pip install -r requirements-dev.txt
pytest -q
```

129 tests, no network, no services required — they run in CI on every push and
pull request. They cover the critic's rules, the revision loop, graph
construction and state, node selection, telemetry, and a parity test asserting
both planners satisfy the same interface identically.

The eval harness scores end-to-end runs against golden queries without an LLM
judge, including adversarial cases: an impossible budget, a 14-day trip, and
deliberately conflicting interests.

## Stack

- **Frontend** — Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui
- **Backend** — FastAPI, Python 3.11
- **Orchestration** — LangGraph for the `graph` planner
- **Models** — local Ollama (Qwen3, Gemma), or Google Gemini
- **Storage** — PostgreSQL for itineraries and sessions, Redis for caching and
  rate limiting
- **Infrastructure** — Docker Compose

## Running it

Prerequisites: Docker and Docker Compose. Ollama on the host or a Gemini key.
SerpAPI and RapidAPI keys are optional — without them those sources use their
mock fallback.

```bash
cd ai-travel-agent
cp .env.example .env      # then fill in whichever keys you have
docker-compose up --build
```

The app comes up at `http://localhost:3000`.

## Layout

```text
ai-travel-agent/
├── frontend/                 Next.js app
├── backend/
│   ├── app/agents/graph/     the LangGraph planner — nodes, state, rules
│   ├── app/agents/           the pipeline planner, streaming, telemetry
│   ├── app/tools/            external API clients and their fallbacks
│   ├── tests/                offline test suite
│   └── evals/                golden queries and the comparison harness
├── scripts/                  setup utilities
└── docker-compose.yml
```

## On AI assistance

Parts of this were written with AI assistance, including some of the code and
an earlier draft of these docs. What I decided myself: that the ReAct loop had
to go because it could not be tested, that the pipeline should survive as the
control rather than be deleted once the graph beat it, and that the critic's
objections belong in testable rules instead of a prompt. The eval numbers above
are the ones the harness prints — including the cases where the graph does not
win.
