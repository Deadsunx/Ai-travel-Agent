"""Trip-parameter resolution: fill sane defaults for dates, duration, travelers.

Kept free of LangChain imports so it is unit-testable with minimal dependencies.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

MAX_TRIP_DAYS = 14
DEFAULT_TRIP_DAYS = 3
DEFAULT_START_OFFSET_DAYS = 14


def resolve_trip_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in sane future dates/duration; clamp to MAX_TRIP_DAYS.

    Mutates and returns `params` with guaranteed keys:
    start_date, end_date (YYYY-MM-DD, future), days (1..MAX_TRIP_DAYS),
    travelers (>=1), budget_limit (float, 0 = unspecified).
    """
    today = datetime.now().date()

    def _parse(value):
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    start = _parse(params.get("start_date"))
    end = _parse(params.get("end_date"))
    try:
        days = int(params.get("days") or 0)
    except (ValueError, TypeError):
        days = 0

    if start is None or start <= today:
        start = today + timedelta(days=DEFAULT_START_OFFSET_DAYS)
    if end is not None and end > start:
        days = days or (end - start).days
    days = min(max(days, 1), MAX_TRIP_DAYS) if days else DEFAULT_TRIP_DAYS
    end = start + timedelta(days=days)

    try:
        travelers = max(int(params.get("travelers") or 1), 1)
    except (ValueError, TypeError):
        travelers = 1

    try:
        budget_limit = float(params.get("budget_limit") or 0)
    except (ValueError, TypeError):
        budget_limit = 0

    params.update({
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "days": days,
        "travelers": travelers,
        "budget_limit": budget_limit,
    })
    return params
