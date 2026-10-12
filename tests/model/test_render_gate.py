"""Browser-gate, arrival, layout, and layer integration tests."""

import json

import pytest
from leaf.render_gate import readings as render_gate_readings
from leaf.render_gate import version as render_gate_model
from leaf.render_gate.command import BrowserCheck
from leaf.render_gate.findings import Finding


def test_swept_faults_are_reported_by_element_and_by_unbroken_run():
    """The sweep names a fault per element and per unbroken run of widths, with its
    reading at the run's narrowest. Here a spill clears between 1520px and 640px and
    returns below; the run taking in the 540px viewport is that viewport's to report,
    and the wide run is still the sweep's. A squeezed table is advice wherever the
    sweep finds it, a run across the 540px viewport included, since no fixed viewport
    reads it. Two drawings that share a name are told apart by their place."""
    widths = sorted({*render_gate_readings.SWEEP_WIDTHS, 540}, reverse=True)

    def at(width):
        spill = 1560 <= width <= 1600 or width <= 600
        drawings = [
            {"at": "<svg> in <figure id=f>", "place": place, "labels": n, "drawn": d}
            | {"set": 11, "words": words}
            for place, n, d, words in ((">0", 1, 8.8, "mild"), (">1", 3, 5, "worst"))
            if width <= 800
        ]
        return {
            "overflow": 0,
            "misplaced": [
                {"code": "past-column", "at": "<pre>", "place": "#x>0", "past": width}
            ]
            if spill
            else [],
            "scrollbars": [],
            "labels": {"threshold_px": 10, "drawings": drawings},
            "squeezed": [
                {
                    "code": "squeezed-table",
                    "at": f"<table id={place[1:]}>",
                    "place": place,
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
    fixed = [{"width": 1200}, {"width": 540}]

    [spill] = render_gate_readings.swept_overflow(readings, fixed)
    assert (spill.code, spill.at, spill.widths) == (
        "past-column",
        "<pre>",
        (1560, 1600),
    )
    assert spill.values["past"] == 1560
    assert str(spill) == (
        "at 1560–1600px wide, <pre> is set 1560px past the column, out in the margin"
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
        " (at 540x720)"
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
    # A wait that never ended carries what the console said, as findings of its own.
    console = [
        Finding("failed-load", values={"status": 401, "url": "http://page/"}),
        Finding("console-warning", values={"text": "slow"}),
    ]
    stalled = Finding(
        "never-reached",
        values={
            "arrival": "an authored main",
            "requesting": ["/page.css"],
            "console": [entry.json(text=False) for entry in console],
        },
        scheme="light",
    )
    assert str(stalled) == (
        "[light] pre-upgrade proof failed: the document never reached an authored"
        " main; still requesting /page.css — 401 http://page/\nwarning: slow"
    )


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
        "unreserved-height",
        "<lf-x id=a>",
        {"drawn": 20, "reserved": None},
        severity="advice",
    )

    def attempt(failures=(), notices=(), complete=True, advice=()):
        reading = render_gate_model.RenderReading([*failures, *advice], [], [])
        return reading, list(notices), complete

    def policy(*attempts):
        left = list(attempts)
        monkeypatch.setattr(
            render_gate_model,
            "_render_version_attempt",
            lambda browser, url, served_timeout_ms=None: left.pop(0),
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
