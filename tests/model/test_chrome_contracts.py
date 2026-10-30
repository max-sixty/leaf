"""Everyday browser contracts for shared chrome."""

import json
import time

import pytest
from browser.test_chrome_contracts import _ProblemPage
from render_harness import (
    Traffic,
    _until,
    clean_browser,
    consume_browser_errors,
    watched,
)

from leaf.findings import Finding
from leaf.render_checks import SERVED_TIMEOUT_MS


def said(text):
    """A console error saying `text`, as the browser fixture records one."""
    return Finding("console-error", values={"text": text, "url": ""})


def test_browser_health_rejects_an_unconsumed_problem():
    """A forgotten per-test assertion cannot turn a browser fault green."""

    with (
        pytest.raises(
            AssertionError, match="https://leaf.test/example: unexpected browser fault"
        ),
        clean_browser(),
    ):
        watched(_ProblemPage()).append(said("unexpected browser fault"))


def test_consuming_browser_problems_accounts_for_every_entry():
    """Naming one expected fault cannot consume an unrelated one."""

    with clean_browser():
        page = _ProblemPage()
        watched(page).extend([said("expected fault"), said("unrelated fault")])
        with pytest.raises(AssertionError, match="unrelated fault"):
            consume_browser_errors(page, "expected fault")


def test_a_traffic_wait_stops_when_repaints_outlive_its_deadline(monkeypatch):
    """A page that repaints its ledger forever cannot keep a false fact alive forever."""

    class BusyPage:
        reads = 0

        def evaluate(self, _script):
            self.reads += 1
            return json.dumps(
                {"sends": self.reads, "acked": 0, "asked": 0, "heard": 0, "pending": []}
            )

        def wait_for_function(self, *_args, **_kwargs):
            raise AssertionError("the expired wait listened for another paint")

    page = BusyPage()
    monkeypatch.setattr(page, "lf_traffic", Traffic(page), raising=False)
    expired = SERVED_TIMEOUT_MS / 1000 + 1
    times = iter((0, expired, expired, expired))
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    with pytest.raises(AssertionError, match="never reached a false fact"):
        _until(page, lambda _traffic: False, "reached a false fact")
