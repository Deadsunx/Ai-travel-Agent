"""How a specialist picks one option — and how it says why.

Every function here is pure: options in, a `Selection` out. No model, no
network, no graph state. That is deliberate — the judgment v2 adds over v1
lives in code that can be tested exhaustively, not in a prompt whose output
changes with the weather.

A `Selection` carries the runner-up options too, so the UI can offer "show
the other three" and the critic can swap the choice on a revision round
without re-running the search.
"""

from typing import Any, Dict, List, Optional, Tuple
import re

from app.agents.graph.state import Choice, Issue

#: Weight on price when scoring flights; the remainder goes to duration.
FLIGHT_PRICE_WEIGHT = {"cheapest": 0.85, "balanced": 0.55, "fastest": 0.2}

#: Runner-up options kept alongside a choice.
ALTERNATIVES_KEPT = 3


def _money(value: float) -> str:
    return f"₹{round(value):,}"


def _number(item: Dict[str, Any], key: str) -> Optional[float]:
    try:
        value = float(item.get(key))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _duration_minutes(flight: Dict[str, Any]) -> Optional[int]:
    """Minutes in the air, from an explicit duration or the clock times."""
    raw = str(flight.get("duration") or "")
    hours = re.search(r"(\d+)\s*h", raw)
    minutes = re.search(r"(\d+)\s*m", raw)
    if hours or minutes:
        return int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0)

    def _clock(value: Any) -> Optional[int]:
        match = re.search(r"(\d{1,2}):(\d{2})", str(value or ""))
        if not match:
            return None
        return int(match.group(1)) * 60 + int(match.group(2))

    start, end = _clock(flight.get("departure_time")), _clock(flight.get("arrival_time"))
    if start is None or end is None:
        return None
    return (end - start) % (24 * 60)


def _normalize(values: List[Optional[float]]) -> List[float]:
    """Scale to 0..1, where 0 is best. Missing values score as middling (0.5)
    so an option is neither rewarded nor punished for incomplete data."""
    present = [v for v in values if v is not None]
    if not present:
        return [0.5] * len(values)
    low, high = min(present), max(present)
    if high == low:
        return [0.0 if v is not None else 0.5 for v in values]
    return [0.5 if v is None else (v - low) / (high - low) for v in values]


class Selection:
    """One chosen option, its reason, and the runners-up."""

    def __init__(self, kind: str, item: Optional[Dict[str, Any]], rationale: str,
                 alternatives: Optional[List[Dict[str, Any]]] = None,
                 issue: Optional[Issue] = None):
        self.kind = kind
        self.item = item
        self.rationale = rationale
        self.alternatives = alternatives or []
        self.issue = issue

    def as_choice(self) -> Optional[Choice]:
        if not self.item:
            return None
        return {
            "kind": self.kind,
            "item": self.item,
            "rationale": self.rationale,
            "alternatives": self.alternatives[:ALTERNATIVES_KEPT],
        }


# ----------------------------------------------------------------------
# Flights
# ----------------------------------------------------------------------


def select_flight(flights: List[Dict[str, Any]], tier: str = "balanced") -> Selection:
    """Trade price against time on the tier the supervisor asked for."""
    options = [f for f in flights or [] if isinstance(f, dict)]
    if not options:
        return Selection("flight", None, "no fares came back")

    weight = FLIGHT_PRICE_WEIGHT.get(tier, FLIGHT_PRICE_WEIGHT["balanced"])
    prices = [_number(f, "price") for f in options]
    durations = [_duration_minutes(f) for f in options]

    price_scores = _normalize(prices)
    duration_scores = _normalize([float(d) if d is not None else None for d in durations])
    scored = sorted(
        zip(options, prices, durations,
            (weight * p + (1 - weight) * d for p, d in zip(price_scores, duration_scores))),
        key=lambda row: row[3],
    )

    chosen, price, duration, _ = scored[0]
    cheapest_price = min((p for p in prices if p is not None), default=None)

    if price is None:
        rationale = f"{chosen.get('airline', 'this fare')} — the only option with a usable time"
    elif cheapest_price is not None and price <= cheapest_price:
        rationale = f"{chosen.get('airline', 'Fare')} at {_money(price)} — cheapest of {len(options)}"
    else:
        gap = price - cheapest_price
        faster = ""
        cheapest_duration = next(
            (d for o, p, d, _ in scored if p == cheapest_price and d is not None), None
        )
        if duration is not None and cheapest_duration is not None and cheapest_duration > duration:
            faster = f", but {cheapest_duration - duration} min shorter"
        rationale = (f"{chosen.get('airline', 'Fare')} at {_money(price)} — "
                     f"{_money(gap)} over the cheapest{faster}")

    return Selection("flight", chosen, rationale, [row[0] for row in scored[1:]])


# ----------------------------------------------------------------------
# Hotels
# ----------------------------------------------------------------------


def select_hotel(hotels: List[Dict[str, Any]], nightly_cap: Optional[float] = None) -> Selection:
    """Best-rated stay that respects the cap.

    When the cap excludes everything the search found, the cheapest option is
    kept but an issue is raised — quietly ignoring the budget is exactly the
    v1 behaviour v2 exists to fix.
    """
    options = [h for h in hotels or [] if isinstance(h, dict)]
    if not options:
        return Selection("hotel", None, "no stays came back")

    def rank(hotel: Dict[str, Any]) -> Tuple[float, float]:
        rating = _number(hotel, "rating") or 0
        price = _number(hotel, "price_per_night") or float("inf")
        return (-rating, price)

    if nightly_cap:
        affordable = [
            h for h in options
            if (_number(h, "price_per_night") or 0) <= nightly_cap
        ]
    else:
        affordable = list(options)

    if nightly_cap and not affordable:
        cheapest = min(options, key=lambda h: _number(h, "price_per_night") or float("inf"))
        price = _number(cheapest, "price_per_night")
        issue: Issue = {
            "severity": "blocker",
            "category": "budget",
            "message": (f"No stay under {_money(nightly_cap)} a night; cheapest found is "
                        f"{_money(price or 0)}"),
            "action": "widen_hotel_search",
        }
        return Selection(
            "hotel", cheapest,
            f"{cheapest.get('name', 'Stay')} at {_money(price or 0)} — over the "
            f"{_money(nightly_cap)} cap, but the cheapest available",
            [h for h in options if h is not cheapest],
            issue,
        )

    ordered = sorted(affordable, key=rank)
    chosen = ordered[0]
    price = _number(chosen, "price_per_night") or 0
    rating = _number(chosen, "rating")

    if nightly_cap:
        rationale = (f"{chosen.get('name', 'Stay')} at {_money(price)} — "
                     f"{'best rated' if rating else 'cheapest'} of {len(affordable)} under the "
                     f"{_money(nightly_cap)} cap")
    else:
        rationale = (f"{chosen.get('name', 'Stay')} at {_money(price)}"
                     + (f", rated {rating}" if rating else ""))

    return Selection("hotel", chosen, rationale, ordered[1:])


# ----------------------------------------------------------------------
# Local: clustering and meal assignment
# ----------------------------------------------------------------------


def _coords(place: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    lat, lon = place.get("lat"), place.get("lon")
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def cluster_by_area(places: List[Dict[str, Any]], days: int,
                    even: bool = False) -> List[List[Dict[str, Any]]]:
    """Group places into `days` buckets.

    Sorting along whichever axis the places actually spread over, then
    chunking, is not k-means — but for the eight to ten POIs a city search
    returns it produces the same "don't cross town twice before lunch"
    result, deterministically and without a dependency.

    Chunking optimises coherence at the cost of coverage: with six sights
    over four days it fills the first three and leaves the fourth empty.
    `even=True` deals round-robin instead, trading some of that coherence
    for a real place on every day — the trade the `rebalance_days` revision
    action exists to make.

    Places without coordinates keep their original order and are dealt out
    round-robin regardless, which is exactly the v1 behaviour.
    """
    days = max(int(days or 1), 1)
    located = [p for p in places or [] if _coords(p)]
    unlocated = [p for p in places or [] if not _coords(p)]

    buckets: List[List[Dict[str, Any]]] = [[] for _ in range(days)]

    if located:
        lats = [_coords(p)[0] for p in located]
        lons = [_coords(p)[1] for p in located]
        spread_lat = max(lats) - min(lats)
        spread_lon = max(lons) - min(lons)
        axis = 0 if spread_lat >= spread_lon else 1
        ordered = sorted(located, key=lambda p: _coords(p)[axis])

        if even:
            # Still ordered by area, but every day is served before any day
            # gets a second stop.
            for index, place in enumerate(ordered):
                buckets[index % days].append(place)
        else:
            # Deal contiguous runs so neighbouring places land on the same day.
            per_day = max(1, round(len(ordered) / days))
            for index, place in enumerate(ordered):
                buckets[min(index // per_day, days - 1)].append(place)

    for index, place in enumerate(unlocated):
        buckets[index % days].append(place)

    return buckets


def assign_meals(restaurants: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    """Two distinct restaurants per day, never repeating until supply runs out.

    v1 rotated with `index % len(list)`, which repeats a restaurant every
    other day on a week-long trip. Here each day takes the next unused pair,
    and only once every option has been used does the rotation begin again.
    """
    days = max(int(days or 1), 1)
    pool = [r for r in restaurants or [] if isinstance(r, dict) and r.get("name")]
    if not pool:
        return [{"lunch": None, "dinner": None} for _ in range(days)]

    plan = []
    cursor = 0
    for _ in range(days):
        lunch = pool[cursor % len(pool)]
        dinner = pool[(cursor + 1) % len(pool)] if len(pool) > 1 else None
        plan.append({"lunch": lunch, "dinner": dinner})
        cursor += 2
    return plan
