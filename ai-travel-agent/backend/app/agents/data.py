"""Helpers for reading tool payloads.

Shared by the v1 pipeline (`travel_agent.py`) and the v2 graph
(`graph/nodes/`) so both coerce tool JSON and pick prices identically — a
budget computed by one planner is directly comparable to the other's.

Kept free of LangChain imports so it is unit-testable with minimal
dependencies.
"""

import json
from typing import Any, Dict, Optional


def safe_load(raw: Optional[str]) -> Optional[Dict]:
    """Parse a tool's JSON string payload; None on anything unparseable."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def cheapest(section: Optional[Dict], list_key: str, price_key: str) -> float:
    """Lowest positive price in a tool result section; 0 when there is none."""
    items = (section or {}).get(list_key) or []
    prices = []
    for item in items:
        try:
            price = float(item.get(price_key, 0))
            if price > 0:
                prices.append(price)
        except (ValueError, TypeError, AttributeError):
            continue
    return min(prices) if prices else 0


def section_count(section: Optional[Dict], list_key: str) -> int:
    """Number of options in a tool result section."""
    if not isinstance(section, dict):
        return 0
    return len(section.get(list_key) or [])


def is_mock(section: Optional[Any]) -> bool:
    """True when a tool result came from the mock fallback rather than an API."""
    return (
        isinstance(section, dict)
        and str(section.get("source", "")).startswith("Mock")
    )
