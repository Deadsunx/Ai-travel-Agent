"""Telemetry may never slow a request down, and may never fail one."""

import time

import pytest

from app.agents import telemetry
from app.config import settings


@pytest.fixture
def recording():
    """Re-enable recording for these tests only (conftest disables it)."""
    original = settings.record_plan_runs
    settings.record_plan_runs = True
    yield
    settings.record_plan_runs = original


@pytest.mark.asyncio
async def test_nothing_is_written_when_recording_is_off():
    calls = []
    import app.services.db_service as db_service
    original = db_service.save_plan_run
    db_service.save_plan_run = lambda **kwargs: calls.append(kwargs)
    try:
        await telemetry.record_run("graph", "s1", "m", {}, time.perf_counter())
    finally:
        db_service.save_plan_run = original

    assert calls == []


@pytest.mark.asyncio
async def test_a_run_is_recorded_with_its_latency(recording, monkeypatch):
    calls = []
    import app.services.db_service as db_service
    monkeypatch.setattr(db_service, "save_plan_run", lambda **kw: calls.append(kw) or True)

    started = time.perf_counter() - 1.5
    await telemetry.record_run(
        "graph", "session-1", "qwen3:8b",
        {"budget": {"total_with_buffer": 25000}}, started, verdict="pass",
    )

    assert len(calls) == 1
    assert calls[0]["planner"] == "graph"
    assert calls[0]["verdict"] == "pass"
    assert calls[0]["latency_ms"] >= 1500


@pytest.mark.asyncio
async def test_a_failing_database_does_not_reach_the_caller(recording, monkeypatch):
    import app.services.db_service as db_service

    def explode(**kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(db_service, "save_plan_run", explode)

    # The point of the test is that this returns rather than raising.
    await telemetry.record_run("pipeline", "s", "m", {}, time.perf_counter())


@pytest.mark.asyncio
async def test_run_ids_are_unique():
    assert telemetry.new_run_id() != telemetry.new_run_id()
