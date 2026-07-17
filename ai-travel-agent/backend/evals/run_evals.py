"""Golden-query eval harness for the travel planning pipeline.

Runs each query in evals/golden_queries.json through TravelPlanningAgent and
scores the result with programmatic checks (no LLM judge needed):

  - pipeline succeeded and produced a non-trivial Markdown answer
  - all data sections present for plan requests (flights/hotels/restaurants/
    budget/itinerary)
  - extracted days / travelers / budget_limit match expectations
  - trip dates are in the future
  - budget math is internally consistent (subtotal + buffer = total)
  - estimated (mock) data is disclosed to the user when present

Requires the stack to be reachable (Ollama + Redis), e.g.:

    docker compose exec backend python -m evals.run_evals
    docker compose exec backend python -m evals.run_evals --only goa_budget_trip

Run it before/after every prompt or model change and compare pass rates.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.travel_agent import TravelPlanningAgent  # noqa: E402

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_queries.json")
PLAN_SECTIONS = ("flights", "hotels", "restaurants", "budget", "itinerary")


def _check(checks: list, name: str, ok: bool, detail: str = ""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


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


async def run_case(case: dict, session_id: str, model: str) -> dict:
    agent = TravelPlanningAgent(session_id=session_id, model_name=model)
    started = time.time()
    result = await agent.plan_trip(case["query"])
    latency = time.time() - started
    checks = score_result(case, result)
    return {"case": case["id"], "latency_s": round(latency, 1), "checks": checks,
            "passed": all(c["ok"] for c in checks)}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Override model name")
    parser.add_argument("--only", default=None, help="Run a single case id")
    args = parser.parse_args()

    with open(GOLDEN_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]

    from app.config import settings
    model = args.model or settings.model_name

    # Sessions: refinement cases reuse the session of their prerequisite case.
    run_id = uuid.uuid4().hex[:8]
    sessions = {}
    reports = []
    for case in cases:
        prior = case.get("requires_prior")
        if prior and prior not in sessions:
            print(f"SKIP {case['id']} (requires {prior}, not run)")
            continue
        session_id = sessions[prior] if prior else f"eval_{run_id}_{case['id']}"
        sessions[case["id"]] = session_id

        print(f"RUN  {case['id']}: {case['query']!r}")
        report = await run_case(case, session_id, model)
        reports.append(report)
        status = "PASS" if report["passed"] else "FAIL"
        print(f"{status} {case['id']} ({report['latency_s']}s)")
        for c in report["checks"]:
            if not c["ok"]:
                print(f"     ✗ {c['name']} {c['detail']}")

    total = len(reports)
    passed = sum(r["passed"] for r in reports)
    all_checks = [c for r in reports for c in r["checks"]]
    checks_passed = sum(c["ok"] for c in all_checks)
    print("\n===== SUMMARY =====")
    print(f"model: {model}")
    print(f"cases: {passed}/{total} passed")
    print(f"checks: {checks_passed}/{len(all_checks)} passed")
    avg = sum(r["latency_s"] for r in reports) / total if total else 0
    print(f"avg latency: {avg:.1f}s")

    out_path = os.path.join(os.path.dirname(GOLDEN_PATH), f"report_{run_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"model": model, "reports": reports}, f, indent=2)
    print(f"report saved: {out_path}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
