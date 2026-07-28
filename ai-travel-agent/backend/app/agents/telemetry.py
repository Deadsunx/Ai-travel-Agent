"""Recording planning runs.

Both planners call `record_run` at the same point — just before the result
reaches the client — so a row exists for every plan either of them
produced, and the comparison between them is a query rather than a
screenshot.

Writing is best-effort and off the event loop: telemetry may never slow a
request down, and may never fail one.
"""

from typing import Any, Dict, Optional
import asyncio
import logging
import time
import uuid

from app.config import settings

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    return uuid.uuid4().hex


async def record_run(
    planner: str,
    session_id: str,
    model_name: str,
    collected: Optional[Dict[str, Any]],
    started: float,
    succeeded: bool = True,
    verdict: Optional[str] = None,
    run_id: Optional[str] = None,
) -> None:
    """Persist one planning run. `started` is a time.perf_counter() reading."""
    if not settings.record_plan_runs:
        return

    from app.services.db_service import save_plan_run

    try:
        await asyncio.to_thread(
            save_plan_run,
            run_id=run_id or new_run_id(),
            session_id=session_id,
            planner=planner,
            model_name=model_name,
            collected=collected,
            latency_ms=int((time.perf_counter() - started) * 1000),
            succeeded=succeeded,
            verdict=verdict,
        )
    except Exception as e:
        logger.warning("Could not record plan run: %s", e)
