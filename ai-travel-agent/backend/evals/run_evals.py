"""Golden-query eval harness for the travel planners.

Runs each query in evals/golden_queries.json through a planner and scores the
result with programmatic checks (no LLM judge needed):

  - planner succeeded and produced a non-trivial Markdown answer
  - all data sections present for plan requests (flights/hotels/restaurants/
    budget/itinerary)
  - extracted days / travelers / budget_limit match expectations
  - trip dates are in the future
  - budget math is internally consistent (subtotal + buffer = total)
  - estimated (mock) data is disclosed to the user when present
  - plan quality: budget respected or explicitly disclosed, days not thin,
    no restaurant repeated across days

The last group is what separates the v1 pipeline from the v2 multi-agent
graph, so the harness can run both and compare:

    docker compose exec backend python -m evals.run_evals
    docker compose exec backend python -m evals.run_evals --planner graph
    docker compose exec backend python -m evals.run_evals --compare
    docker compose exec backend python -m evals.run_evals --only goa_budget_trip

Requires the stack to be reachable (Ollama + Redis).
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.travel_agent import create_planner  # noqa: E402

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_queries.json")
PLAN_SECTIONS = ("flights", "hotels", "restaurants", "budget", "itinerary")
SLOTS = ("morning", "afternoon", "evening")

#: Generic stand-ins itinerary_builder uses when it has no real place; they
#: may legitimately repeat, so they are excluded from the duplicate check.
PLACEHOLDER_PLACES = ("a well-rated local restaurant", "a popular dinner spot")

OVER_BUDGET_PHRASES = ("exceed", "over budget", "over your budget", "above your budget",
                       "more than your budget", "not fit", "doesn't fit", "does not fit",
                       "tight", "reduce", "cut")


def _check(checks: list, name: str, ok: bool, detail: str = ""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _meal_places(itinerary: dict) -> list:
    """Restaurant names the itinerary scheduled, in day order."""
    places = []
    for day in (itinerary or {}).get("days") or []:
        for slot in SLOTS:
            for activity in day.get(slot) or []:
                match = re.match(r"(?:Lunch|Dinner) at (.+)", str(activity.get("activity", "")))
                if match:
                    places.append(match.group(1).strip())
    return places


def _activity_counts(itinerary: dict) -> list:
    """Number of scheduled activities per day."""
    return [
        sum(len(day.get(slot) or []) for slot in SLOTS)
        for day in (itinerary or {}).get("days") or []
    ]


def score_result(case: dict, result: dict) -> list:
    checks = []
    response = result.get("response") or ""
    collected = result.get("collected_data") or {}
    params = collected.get("trip_params") or {}

    _check(checks, "success", result.get("success") is True)
    _check(checks, "response_nontrivial", len(response) >= 100,
           f"len={len(response)}")

    if case.get("expect_plan"):
        for section in PLAN_SECTIONS:
            _check(checks, f"has_{section}", bool(collected.get(section)))

        _check(checks, "markdown_sections", "###" in response)

        if case.get("expect_days"):
            _check(checks, "days_extracted", params.get("days") == case["expect_days"],
                   f"got {params.get('days')}, want {case['expect_days']}")
        if case.get("expect_max_days"):
            _check(checks, "days_clamped",
                   (params.get("days") or 0) <= case["expect_max_days"],
                   f"got {params.get('days')}, max {case['expect_max_days']}")
        if case.get("expect_travelers"):
            _check(checks, "travelers_extracted",
                   params.get("travelers") == case["expect_travelers"],
                   f"got {params.get('travelers')}")
        if case.get("expect_budget_limit"):
            _check(checks, "budget_limit_extracted",
                   params.get("budget_limit") == case["expect_budget_limit"],
                   f"got {params.get('budget_limit')}")

        # Dates must always be in the future
        start = str(params.get("start_date") or "")
        _check(checks, "future_dates", start > time.strftime("%Y-%m-%d"),
               f"start_date={start}")

        # Budget math consistency
        budget = collected.get("budget") or {}
        if budget:
            subtotal = budget.get("subtotal", 0)
            buffer_amt = (budget.get("breakdown") or {}).get("buffer_10_percent", 0)
            total = budget.get("total_with_buffer", 0)
            _check(checks, "budget_math", abs((subtotal + buffer_amt) - total) <= 1,
                   f"{subtotal}+{buffer_amt} vs {total}")

        # --- plan quality -------------------------------------------------
        if case.get("expect_budget_respected") and budget:
            _check(checks, "budget_respected", budget.get("within_budget") is True,
                   f"total {budget.get('total_with_buffer')} vs limit {budget.get('budget_limit')}")

        if case.get("expect_min_revisions"):
            want = case["expect_min_revisions"]
            got = collected.get("revisions", 0)
            _check(checks, "plan_was_revised", got >= want,
                   f"{got} revision(s), wanted at least {want}")

        if case.get("expect_budget_disclosure") and budget:
            # An impossible budget is fine; silently ignoring it is not.
            if budget.get("within_budget") is False:
                said = any(p in response.lower() for p in OVER_BUDGET_PHRASES)
                _check(checks, "over_budget_disclosed", said,
                       "answer never says the trip is over budget")

        if case.get("expect_min_activities_per_day"):
            want = case["expect_min_activities_per_day"]
            counts = _activity_counts(collected.get("itinerary") or {})
            thin = [i + 1 for i, c in enumerate(counts) if c < want]
            _check(checks, "days_not_thin", bool(counts) and not thin,
                   f"days below {want} activities: {thin}")

        if case.get("expect_no_duplicate_restaurants"):
            places = [p for p in _meal_places(collected.get("itinerary") or {})
                      if p not in PLACEHOLDER_PLACES]
            duplicates = sorted({p for p in places if places.count(p) > 1})
            _check(checks, "no_duplicate_restaurants", not duplicates,
                   f"repeated: {duplicates}")

        # Mock data must be disclosed
        has_mock = any(
            str((collected.get(s) or {}).get("source", "")).startswith("Mock")
            for s in ("flights", "hotels", "restaurants")
        )
        if has_mock:
            disclosed = any(w in response.lower() for w in ("estimat", "demo", "mock", "approximate"))
            _check(checks, "mock_disclosed", disclosed)
    else:
        # Chat/refinement path: should NOT have re-run a full plan for greetings
        _check(checks, "no_hallucinated_prices",
               "₹" not in response or bool(collected.get("budget")),
               "prices shown without any collected data")

    return checks


async def run_case(case: dict, session_id: str, model: str, planner: str) -> dict:
    agent = create_planner(session_id=session_id, model_name=model, planner=planner)
    started = time.time()
    result = await agent.plan_trip(case["query"])
    latency = time.time() - started
    checks = score_result(case, result)
    collected = result.get("collected_data") or {}
    budget = collected.get("budget") or {}

    return {
        "case": case["id"],
        "planner": planner,
        "latency_s": round(latency, 1),
        "checks": checks,
        "passed": all(c["ok"] for c in checks),
        # Metrics the summary aggregates, kept separate from pass/fail.
        "over_budget": bool(budget) and budget.get("within_budget") is False,
        "had_budget_limit": bool(budget.get("budget_limit")),
        "revisions": collected.get("revisions", 0),
    }


async def run_suite(cases: list, model: str, planner: str, run_id: str) -> list:
    """Run every case against one planner. Sessions are per case, except
    refinement cases which reuse the session of their prerequisite."""
    sessions = {}
    reports = []

    for case in cases:
        # Some assertions only mean anything for a planner that has the
        # capability — a case about revising a plan cannot fairly be run
        # against a planner that never chooses, and so never revises.
        only = case.get("only_planner")
        if only and only != planner:
            print(f"SKIP {case['id']} (only applies to the {only} planner)")
            continue

        prior = case.get("requires_prior")
        if prior and prior not in sessions:
            print(f"SKIP {case['id']} (requires {prior}, not run)")
            continue
        session_id = sessions[prior] if prior else f"eval_{run_id}_{planner}_{case['id']}"
        sessions[case["id"]] = session_id

        print(f"RUN  [{planner}] {case['id']}: {case['query']!r}")
        report = await run_case(case, session_id, model, planner)
        reports.append(report)
        status = "PASS" if report["passed"] else "FAIL"
        print(f"{status} {case['id']} ({report['latency_s']}s)")
        for check in report["checks"]:
            if not check["ok"]:
                print(f"     ✗ {check['name']} {check['detail']}")

    return reports


def summarize(reports: list) -> dict:
    total = len(reports)
    all_checks = [c for r in reports for c in r["checks"]]
    latencies = sorted(r["latency_s"] for r in reports)
    with_limit = [r for r in reports if r["had_budget_limit"]]

    return {
        "cases": total,
        "passed": sum(r["passed"] for r in reports),
        "checks": len(all_checks),
        "checks_passed": sum(c["ok"] for c in all_checks),
        "budget_violations": sum(r["over_budget"] for r in with_limit),
        "budget_cases": len(with_limit),
        "p50_latency": latencies[len(latencies) // 2] if latencies else 0,
        "avg_revisions": round(sum(r["revisions"] for r in reports) / total, 1) if total else 0,
    }


def print_summary(planner: str, model: str, summary: dict):
    print("\n===== SUMMARY =====")
    print(f"planner: {planner}   model: {model}")
    print(f"cases: {summary['passed']}/{summary['cases']} passed")
    print(f"checks: {summary['checks_passed']}/{summary['checks']} passed")
    print(f"budget violations: {summary['budget_violations']}/{summary['budget_cases']}")
    print(f"p50 latency: {summary['p50_latency']}s")


def print_comparison(summaries: dict):
    """The v1-vs-v2 table: the point of building the graph planner."""
    names = list(summaries)
    width = 12

    def row(label, values):
        print(label.ljust(24) + "".join(str(v).rjust(width) for v in values))

    print("\n===== COMPARISON =====")
    row("", names)
    row("pass rate", [f"{s['passed']}/{s['cases']}" for s in summaries.values()])
    row("checks passed", [f"{s['checks_passed']}/{s['checks']}" for s in summaries.values()])
    row("budget violations", [f"{s['budget_violations']}/{s['budget_cases']}"
                              for s in summaries.values()])
    row("p50 latency", [f"{s['p50_latency']}s" for s in summaries.values()])
    row("avg revisions", [s["avg_revisions"] for s in summaries.values()])
    print("\nnote: planners run in sequence and share the Redis tool cache, so the"
          "\n      later one searches warm. Compare latency across separate runs.")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Override model name")
    parser.add_argument("--only", default=None, help="Run a single case id")
    parser.add_argument("--planner", default=None, choices=["pipeline", "graph"],
                        help="Planner to evaluate (default: the PLANNER setting)")
    parser.add_argument("--compare", action="store_true",
                        help="Run both planners and print a comparison table")
    args = parser.parse_args()

    with open(GOLDEN_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]

    from app.config import settings
    model = args.model or settings.model_name
    planners = ["pipeline", "graph"] if args.compare else [args.planner or settings.planner]

    run_id = uuid.uuid4().hex[:8]
    all_reports = {}
    summaries = {}
    for planner in planners:
        reports = await run_suite(cases, model, planner, run_id)
        all_reports[planner] = reports
        summaries[planner] = summarize(reports)
        print_summary(planner, model, summaries[planner])

    if len(planners) > 1:
        print_comparison(summaries)

    out_path = os.path.join(os.path.dirname(GOLDEN_PATH), f"report_{run_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"model": model, "summaries": summaries, "reports": all_reports},
                  f, indent=2)
    print(f"\nreport saved: {out_path}")

    everything_passed = all(s["passed"] == s["cases"] for s in summaries.values())
    sys.exit(0 if everything_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
