"""The served row's thread counts, held to the cases the panel's are."""

import json
from pathlib import Path

import pytest

from leaf.served_state.thread import thread_counts

CASES = json.loads((Path(__file__).parents[1] / "thread_count_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_rows_count_threads_as_the_panel_does(case):
    """`tests/runtime/thread-counts.test.mjs` reads the same cases against the
    runtime's `threadCounts`, so Claude Code's band and the page's Leaf panel show
    the same numbers."""
    assert thread_counts(case["threads"]) == case["counts"]
