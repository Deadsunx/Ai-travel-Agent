"""Unit tests for the <think>-block streaming filter."""

from app.agents.streaming import ThinkFilter, strip_think


def _run_chunks(chunks):
    f = ThinkFilter()
    out = "".join(f.feed(c) for c in chunks)
    return out + f.flush()


def test_strip_think_removes_block():
    assert strip_think("<think>reasoning here</think>Hello world") == "Hello world"


def test_strip_think_no_block():
    assert strip_think("Just an answer") == "Just an answer"


def test_filter_passthrough():
    assert _run_chunks(["Hello ", "world"]) == "Hello world"


def test_filter_removes_whole_block_in_one_chunk():
    assert _run_chunks(["<think>secret</think>Answer"]) == "Answer"


def test_filter_tag_split_across_chunks():
    # "<think>" split as "<th" + "ink>", "</think>" split as "</thi" + "nk>"
    assert _run_chunks(["<th", "ink>hidden</thi", "nk>Visible"]) == "Visible"


def test_filter_text_before_and_after_block():
    assert _run_chunks(["Before<think>x", "y</think>After"]) == "BeforeAfter"


def test_filter_unclosed_think_suppressed():
    # An unterminated think block should never leak.
    assert _run_chunks(["<think>never closed..."]) == ""


def test_filter_angle_bracket_not_a_tag():
    assert _run_chunks(["a < b and c > d"]) == "a < b and c > d"


def test_filter_multiple_blocks():
    assert _run_chunks(["<think>a</think>1<think>b</think>2"]) == "12"
