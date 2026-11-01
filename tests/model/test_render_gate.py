"""Browser-gate, arrival, layout, and layer integration tests."""

import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from leaf import render_checks as render_checks_model
from leaf import user_views
from leaf.findings import Finding
from leaf.render_gate import readings as render_gate_readings
from leaf.render_gate import version as render_gate_model
from leaf.render_gate.command import PIN_VARIABLE, BrowserCheck, desktop_viewport
from model.test_user_views import report


@pytest.mark.parametrize("failure", [None, "body", "finish"])
def test_probe_observation_finishes_and_disposes_native_handle(monkeypatch, failure):
    """A failed check or native reading still disconnects and releases its observation."""
    calls = []
    finding = {"code": "passive-layout-shift"}

    def finish(_expression):
        calls.append("finish")
        if failure == "finish":
            raise RuntimeError("finish failed")
        return [finding]

    handle = SimpleNamespace(evaluate=finish, dispose=lambda: calls.append("dispose"))
    page = SimpleNamespace(evaluate_handle=lambda *_args: handle)
    monkeypatch.setattr(render_checks_model, "_load_probes", lambda *_args: None)
    error = (
        pytest.raises(RuntimeError, match=f"{failure} failed")
        if failure
        else nullcontext()
    )
    with error:
        with render_checks_model.observe_probe(page, "passiveLayoutShifts") as records:
            assert records == []
            if failure == "body":
                raise RuntimeError("body failed")
    assert calls == ["finish", "dispose"]
    assert records == ([] if failure == "finish" else [finding])


def test_swept_faults_are_reported_by_element_and_by_unbroken_run():
    """The sweep names a fault per element and per unbroken run of widths, with its
    reading at the run's narrowest. Here a spill clears between 1520px and 640px and
    returns below, so it is two runs. A clipped control is read the same way, and the
    phone widths' second sample, at the phone's height, joins it: a control clipped
    in either sample of a width is clipped at that width. One clipped in both is one
    run; one clipped only at the desktop height, or only at the phone's, is a run of
    its own. A squeezed table is advice wherever the sweep finds it. Two drawings that
    share a name are told apart by their place."""
    widths = sorted({*render_gate_readings.SWEEP_WIDTHS, 540}, reverse=True)

    def at(width, short=False):
        spill = 1560 <= width <= 1600 or width <= 600
        drawings = [
            {
                "at": "<svg> in <figure id=f>",
                "place": {"id": "f", "steps": [{"child": place}]},
                "labels": n,
                "drawn": d,
            }
            | {"set": 11, "words": words}
            for place, n, d, words in ((0, 1, 8.8, "mild"), (1, 3, 5, "worst"))
            if width <= 800
        ]
        return {
            "overflow": 0,
            "misplaced": [
                {
                    "code": "past-column",
                    "at": "<pre>",
                    "place": {"id": "x", "steps": [{"child": 0}]},
                    "past": width,
                }
            ]
            if spill
            else [],
            "scrollbars": [],
            "contained": [],
            "clipped": [
                {"code": "clipped-control", "at": f"<button id={place[1:]}>"}
                | {
                    "place": {"id": place[1:], "steps": []},
                    "control": "pick",
                    "id": place[1:],
                    "lost": width,
                }
                | {"by": "<div id=row>"}
                for place, clipped in (
                    ("#narrow", width <= 440),
                    ("#tall", 520 <= width <= 560 and not short),
                    ("#short", 400 <= width <= 480 and short),
                )
                if clipped
            ],
            "covered": [],
            "labels": {"threshold_px": 10, "drawings": drawings},
            "squeezed": [
                {
                    "code": "squeezed-table",
                    "at": f"<table id={place[1:]}>",
                    "place": {"id": place[1:], "steps": []},
                    "scrolls": width,
                    "columns": [{"heading": None, "width": 80, "wraps": True}],
                }
                for place, squeezed in (
                    ("#t", width <= 400),
                    ("#u", 520 <= width <= 560),
                )
                if squeezed
            ],
        }

    readings = [(width, at(width)) for width in widths]
    short = [(width, at(width, short=True)) for width in widths if width <= 540]
    swept = render_gate_readings.swept_faults([*readings, *short])
    assert [(f.code, f.at, f.widths) for f in swept] == [
        ("past-column", "<pre>", (1560, 1600)),
        ("past-column", "<pre>", (360, 600)),
        ("clipped-control", "<button id=tall>", (520, 560)),
        ("clipped-control", "<button id=short>", (400, 480)),
        ("clipped-control", "<button id=narrow>", (360, 440)),
    ]
    spill, _, _, _, clipped = swept
    assert clipped.severity == "error"
    assert clipped.values["lost"] == 360
    assert spill.values["past"] == 1560
    assert str(spill) == (
        "at 1560–1600px wide, <pre> is set 1560px past the column, out in the margin"
        '; to give it more room, mark it data-width="wide" or "available" rather than sizing it past the column'
    )
    squeezed = render_gate_readings.squeezed_table_advice(readings)
    assert [(f.at, f.widths, f.values["scrolls"], f.severity) for f in squeezed] == [
        ("<table id=u>", (520, 560), 520, "advice"),
        ("<table id=t>", (360, 400), 360, "advice"),
    ]
    advice = render_gate_readings.shrunk_label_advice(readings)
    assert [
        (f.at, f.widths, f.values["labels"], f.values["words"], f.values["drawn"])
        for f in advice
    ] == [
        ("<svg> in <figure id=f>", (360, 800), 1, "mild", 8.8),
        ("<svg> in <figure id=f>", (360, 800), 3, "worst", 5),
    ], advice
    assert {f.values["width"] for f in advice} == {360}


def test_a_finding_is_a_record_its_words_and_json_are_rendered_from():
    """A finding's fields are what a reader takes; its words and its JSON are both
    rendered from them, and where it was read stands around the words."""
    finding = Finding(
        "past-column",
        "<div id=wide>",
        {"place": "#wide", "past": 74},
        scheme="dark",
        viewports=("540x720",),
    )
    assert str(finding) == (
        "[dark] <div id=wide> is set 74px past the column, out in the margin"
        '; to give it more room, mark it data-width="wide" or "available" rather than sizing it past the column (at 540x720)'
    )
    assert json.loads(json.dumps(finding.json())) == {
        "code": "past-column",
        "severity": "error",
        "at": "<div id=wide>",
        "scheme": "dark",
        "viewports": ["540x720"],
        "values": {"place": "#wide", "past": 74},
        "text": str(finding),
    }
    assert Finding.loads(finding.json()) == finding
    # Equal records are one finding, so they dedupe as their words did.
    assert len({finding, finding.but(values={})}) == 1
    with pytest.raises(ValueError):
        Finding("no-such-code")


def test_page_check_json_names_only_the_gates_that_read_the_page():
    """Failing page code ends the check before the render gate reads anything, so
    `--json` says the render check was asked for and did not run."""
    failed = Finding("page-report", values={"text": "leaf: <lf-x> failed"})
    check = BrowserCheck(
        ["page code", "render check"], "Chrome", page_code=[failed]
    ).json()
    assert (check["asked"], check["ran"]) == (
        ["page code", "render check"],
        ["page code"],
    )


def test_the_render_check_reads_the_desktop_in_the_last_reported_window(
    tmp_path, monkeypatch
):
    """`page check --render` reads its desktop at the window of the browser that
    reported last, while the page keeps that report, and at the fixed laptop window
    before any report or when the caller pins it."""
    monkeypatch.delenv(PIN_VARIABLE)
    now = datetime(2026, 10, 22, tzinfo=UTC)
    monkeypatch.setattr(user_views, "_now", lambda: now)

    def read():
        return desktop_viewport(tmp_path).json()

    unviewed = read()
    assert (unviewed["width"], unviewed["height"]) == (1280, 720)
    assert unviewed["from"].startswith("fixed, since no browser")

    laptop, wide = report(session="a" * 32), report(session="b" * 32)
    wide["viewport"] = {"width": 1728, "height": 999}
    user_views.observe_user_view(tmp_path, laptop)
    now += timedelta(minutes=5)
    user_views.observe_user_view(tmp_path, wide)
    assert read() == {"width": 1728, "height": 999, "from": "the user's window"}

    # A day on, the page no longer keeps either report.
    now += timedelta(days=1, seconds=1)
    assert read()["from"].startswith("fixed, since no browser")
    now -= timedelta(days=1, seconds=1)

    monkeypatch.setenv(PIN_VARIABLE, "fixed")
    assert read() == {
        "width": 1280,
        "height": 720,
        "from": f"fixed, pinned by {PIN_VARIABLE}",
    }
    monkeypatch.setenv(PIN_VARIABLE, "1728x999")
    with pytest.raises(ValueError, match="takes only 'fixed'"):
        read()


def test_a_resize_notice_is_pardoned_only_by_a_complete_clean_confirmation(monkeypatch):
    """The retry policy over whole attempts (`render_version`): a notice is ignored
    only when a later complete attempt is clean, ordinary failures from both attempts
    stand once each, and an incomplete confirmation pardons nothing. Advice is the
    first attempt's. What an attempt hears is the browser's half, read by
    `test_a_recurring_resize_notice_fails_the_render_gate`."""
    notice = Finding(
        "resize-loop", values={"text": "ResizeObserver loop completed"}, scheme="light"
    )
    error = Finding("console-error", values={"text": "first attempt"}, scheme="light")
    later = Finding("console-error", values={"text": "later"}, scheme="dark")
    failed = Finding("probe-failed", values={"error": "probe failed"}, scheme="light")
    first = Finding(
        "grows-with-content",
        "<lf-x id=a>",
        {"layout": "column", "box": "div", "height": 20},
        severity="advice",
    )

    def attempt(failures=(), notices=(), complete=True, advice=()):
        reading = render_gate_model.RenderReading([*failures, *advice], [])
        return reading, list(notices), complete

    def policy(*attempts):
        left = list(attempts)
        monkeypatch.setattr(
            render_gate_model,
            "_render_version_attempt",
            lambda browser, url, desktop, served_timeout_ms=None, implementations=None, declaration_sources=None: (
                left.pop(0)
            ),
        )
        reading = render_gate_model.render_version(None, "http://page")
        assert not left, f"{len(left)} attempts were never made"
        return reading

    def confirmed(how):
        return notice.but(values={"confirmation": how})

    # A notice once, under load, and a clean confirmation: nothing to report.
    transient = policy(attempt(notices=[notice], advice=[first]), attempt())
    assert (transient.failures, transient.advice) == ([], [first])
    # The confirmation pardons the notice and nothing else, and says it once.
    assert policy(attempt([error], [notice]), attempt([error, later])).failures == [
        error,
        later,
    ]
    # On every rendering, which is a layout feedback loop.
    recurring = policy(attempt(notices=[notice]), attempt(notices=[notice])).failures
    assert recurring == [confirmed("recurred")]
    assert str(recurring[0]) == (
        "[light] console: window error: ResizeObserver loop completed"
        " (recurred on the confirming render attempt)"
    )
    # A confirmation that did not finish cannot say the notice was transient.
    assert policy(
        attempt([error], [notice]), attempt([failed], complete=False)
    ).failures == [error, failed, confirmed("incomplete")]
    # Nor can an attempt that did not finish ask for one.
    assert policy(attempt([error], [notice], complete=False)).failures == [
        error,
        notice,
    ]


def test_output_contract_failures_refuse_page_and_package_checks():
    from leaf.data_contracts import output_findings
    from leaf.render_gate.command import WidgetQuality
    from leaf.render_gate.version import RenderReading

    registry = {
        "$data": {
            "contracts": {
                "counts": {
                    "schema": {
                        "type": "object",
                        "properties": {"count": {"type": "integer"}},
                        "required": ["count"],
                    }
                }
            }
        }
    }
    readings = [
        {
            "tag": "lf-counter",
            "id": "count",
            "output": "total",
            "contract": "counts",
            "value": value,
        }
        for value in ({"count": 2}, {"count": "wrong"})
    ]
    found = output_findings(
        readings,
        registry,
        {
            "lf-counter": {"owner": "layer", "path": "/widgets/lf-counter.js"},
        },
    )
    assert len(found) == 1
    assert str(found[0]) == (
        "<lf-counter id=count> (package producer): output 'total' value is invalid "
        "for contract 'counts' at $.count: 'wrong' is not of type 'integer'"
    )
    assert BrowserCheck(["render check"], render=RenderReading(found, [])).status == 1
    assert WidgetQuality(1, findings=tuple(found)).status == 1
