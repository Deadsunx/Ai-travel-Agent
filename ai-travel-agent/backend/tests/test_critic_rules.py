"""The critic's rules, and the guarantees the loop rests on."""

from app.agents.graph.nodes.critic import (
    MAX_REVISIONS_CEILING,
    parse_llm_issues,
    revision_budget,
)
from app.agents.graph.rules import (
    cap_ratio_for_overrun,
    check_budget,
    check_data_quality,
    check_day_coverage,
    check_duplicate_meals,
    evaluate,
)


def _budget(total, limit):
    return {"total_with_buffer": total, "budget_limit": limit,
            "within_budget": total <= limit, "subtotal": round(total / 1.1)}


def _state(**overrides):
    state = {
        "params": {"destination": "Goa", "days": 3, "travelers": 2, "budget_limit": 30000},
        "budget": _budget(30000, 30000),
        "choices": {"hotel": {"kind": "hotel", "item": {"name": "Inn", "price_per_night": 4000}}},
        "itinerary": {"days": [
            {"day": d, "morning": [{}, {}], "afternoon": [{}], "evening": [{}]}
            for d in (1, 2, 3)
        ]},
        "meal_plan": [
            {"lunch": {"name": "A"}, "dinner": {"name": "B"}},
            {"lunch": {"name": "C"}, "dinner": {"name": "D"}},
            {"lunch": {"name": "E"}, "dinner": {"name": "F"}},
        ],
        "restaurants": {"restaurants": [{"name": n} for n in "ABCDEF"]},
        "specialist_issues": [],
    }
    state.update(overrides)
    return state


# ---- budget -----------------------------------------------------------


def test_a_plan_within_budget_raises_nothing():
    issues, requests = check_budget(_state())
    assert issues == [] and requests == []


def test_over_budget_is_a_blocker_with_a_specific_cut():
    state = _state(budget=_budget(39000, 30000))
    issues, requests = check_budget(state)

    assert issues[0]["severity"] == "blocker"
    assert "30% over" in issues[0]["message"]
    assert requests[0]["name"] == "cheaper_hotels"
    # 9000 over, 3 nights, buffer-adjusted: about 2727 off a 4000 room.
    assert 0.31 <= requests[0]["args"]["ratio"] <= 0.33 or requests[0]["args"]["ratio"] == 0.4


def test_a_small_overrun_asks_only_for_a_cheaper_room():
    state = _state(budget=_budget(31000, 30000))
    _, requests = check_budget(state)

    assert [r["name"] for r in requests] == ["cheaper_hotels"]
    assert requests[0]["args"]["ratio"] > 0.9    # a small trim is enough


def test_a_severe_overrun_also_cuts_activities():
    state = _state(budget=_budget(60000, 30000))
    _, requests = check_budget(state)

    assert [r["name"] for r in requests] == ["cheaper_hotels", "drop_paid_activities"]


def test_cap_ratio_is_none_when_there_is_nothing_to_fix():
    assert cap_ratio_for_overrun(_budget(20000, 30000), 3, 4000) is None
    assert cap_ratio_for_overrun(_budget(40000, 0), 3, 4000) is None


def test_no_budget_limit_means_no_budget_rule():
    state = _state(budget=_budget(90000, 0))
    assert check_budget(state) == ([], [])


# ---- coverage and coherence -------------------------------------------


def test_a_thin_day_is_reported_with_the_day_number():
    state = _state(itinerary={"days": [
        {"day": 1, "morning": [{}, {}], "afternoon": [{}], "evening": [{}]},
        {"day": 2, "morning": [{}], "afternoon": [], "evening": []},
    ]})
    issues, requests = check_day_coverage(state)

    assert issues[0]["severity"] == "warning"
    assert "Day 2" in issues[0]["message"]
    assert requests[0]["name"] == "rebalance_days"


def test_repeats_with_enough_restaurants_are_a_fixable_warning():
    state = _state(meal_plan=[
        {"lunch": {"name": "A"}, "dinner": {"name": "B"}},
        {"lunch": {"name": "A"}, "dinner": {"name": "C"}},
    ])
    issues, requests = check_duplicate_meals(state)

    assert issues[0]["severity"] == "warning"
    assert issues[0]["category"] == "coherence"
    assert requests[0]["name"] == "rebalance_days"


def test_repeats_from_a_thin_search_are_a_data_note_not_a_revision():
    """Rearranging two restaurants across six meals fixes nothing."""
    state = _state(
        meal_plan=[
            {"lunch": {"name": "A"}, "dinner": {"name": "B"}},
            {"lunch": {"name": "A"}, "dinner": {"name": "B"}},
            {"lunch": {"name": "A"}, "dinner": {"name": "B"}},
        ],
        restaurants={"restaurants": [{"name": "A"}, {"name": "B"}]},
    )
    issues, requests = check_duplicate_meals(state)

    assert issues[0]["severity"] == "note"
    assert issues[0]["category"] == "data_quality"
    assert requests == [], "no revision can invent restaurants"


def test_estimated_data_is_noted_once_it_dominates():
    state = _state(
        flights={"source": "Mock Data (API not configured)"},
        hotels={"source": "Mock Data (API not configured)"},
    )
    issues, _ = check_data_quality(state)
    assert issues[0]["severity"] == "note"


def test_one_estimated_section_is_not_worth_a_note():
    state = _state(flights={"source": "Mock Data (API not configured)"})
    assert check_data_quality(state) == ([], [])


# ---- the whole pass ---------------------------------------------------


def test_contradictory_requests_are_resolved_in_favour_of_the_budget():
    """Widening a cap the total cannot afford would loop forever."""
    state = _state(
        budget=_budget(45000, 30000),
        specialist_issues=[{"severity": "blocker", "category": "budget",
                            "message": "no room under cap", "action": "widen_hotel_search"}],
    )
    _, requests = evaluate(state)
    names = [r["name"] for r in requests]

    assert "cheaper_hotels" in names
    assert "widen_hotel_search" not in names


def test_each_action_is_requested_at_most_once():
    state = _state(
        budget=_budget(45000, 30000),
        itinerary={"days": [{"day": 1, "morning": [], "afternoon": [], "evening": []}]},
        meal_plan=[{"lunch": {"name": "A"}, "dinner": {"name": "A"}}],
    )
    _, requests = evaluate(state)
    names = [r["name"] for r in requests]

    assert len(names) == len(set(names))


def test_a_sound_plan_produces_no_requests():
    issues, requests = evaluate(_state())
    assert requests == []
    assert [i for i in issues if i["severity"] == "blocker"] == []


# ---- guarantees -------------------------------------------------------


def test_the_revision_budget_is_capped():
    assert revision_budget(99) == MAX_REVISIONS_CEILING
    assert revision_budget(-4) == 0


def test_advisory_issues_can_never_block():
    raw = '{"issues": [{"category": "feasibility", "severity": "blocker", "message": "far apart"}]}'
    issues = parse_llm_issues(raw)

    assert len(issues) == 1
    assert issues[0]["severity"] == "warning", "the advisory pass must not drive the loop"
    assert issues[0]["action"] is None


def test_advisory_garbage_is_survivable():
    for raw in ("", "not json at all", '{"issues": "nonsense"}', '{"wrong": []}'):
        assert parse_llm_issues(raw) == []


def test_advisory_issues_are_capped_and_categorised():
    raw = ('{"issues": [' + ",".join(
        '{"category": "invented", "message": "m%d"}' % i for i in range(6)) + ']}')
    issues = parse_llm_issues(raw)

    assert len(issues) == 3
    assert all(i["category"] == "coherence" for i in issues)


def test_advisory_thinking_blocks_are_stripped():
    raw = '<think>let me see</think>{"issues": [{"category": "coverage", "message": "thin day 2"}]}'
    assert parse_llm_issues(raw)[0]["message"] == "thin day 2"
