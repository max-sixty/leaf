"""Browser-gate, arrival, layout, and layer integration tests."""

import re

from leaf.render_gate import readings as render_gate_readings
from leaf.render_gate import version as render_gate_model


def test_swept_faults_are_reported_by_element_and_by_unbroken_run():
    """The sweep names a fault per element and per unbroken run of widths, with its
    reading at the run's narrowest. Here a spill clears between 1520px and 640px and
    returns below; the run taking in the 540px viewport is that viewport's to report,
    and the wide run is still the sweep's. A table that fits at both fixed viewports and
    scrolls squeezed only on a phone narrower than 540px is the sweep's advice, and one
    squeezed across 540px is that viewport's failure. Two drawings that share a name
    are told apart by their place."""
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
                {
                    "at": "<pre>",
                    "place": "#x>0",
                    "kind": "column",
                    "text": f"<pre> spills at {width}px",
                }
            ]
            if spill
            else [],
            "scrollbars": [],
            "labels": {"threshold_px": 10, "drawings": drawings},
            "squeezed": [
                {"place": place, "text": f"<table id={place[1:]}> scrolls at {width}px"}
                for place, squeezed in (
                    ("#t", width <= 400),
                    ("#u", 520 <= width <= 560),
                )
                if squeezed
            ],
        }

    readings = [(width, at(width)) for width in widths]
    fixed = [{"width": 1200}, {"width": 540}]

    assert render_gate_readings.swept_overflow(readings, fixed) == [
        "at 1560–1600px wide, <pre> spills at 1560px"
    ]
    assert render_gate_readings.squeezed_table_advice(readings, fixed) == [
        "at 360–400px wide, <table id=t> scrolls at 360px"
    ]
    advice = render_gate_readings.shrunk_label_advice(readings)
    shown = r"at 360–800px wide <svg> in <figure id=f> draws labels below 10px, "
    smallest = r"(\d) at 360px, the smallest \('(\w+)'\) at ([\d.]+)px from the 11px"
    assert [re.match(shown + smallest, line).groups() for line in advice] == [
        ("1", "mild", "8.8"),
        ("3", "worst", "5"),
    ], advice


def test_a_resize_notice_is_pardoned_only_by_a_complete_clean_confirmation(monkeypatch):
    """The retry policy over whole attempts (`render_version`): a notice is ignored
    only when a later complete attempt is clean, ordinary failures from both attempts
    stand once each, and an incomplete confirmation pardons nothing. Advice is the
    first attempt's. What an attempt hears is the browser's half, read by
    `test_a_recurring_resize_notice_fails_the_render_gate`."""
    notice = "[light] window error: ResizeObserver loop completed"
    error = "[light] console: ordinary error from first attempt"

    def attempt(failures=(), notices=(), complete=True, advice=()):
        reading = render_gate_model.RenderReading(list(failures), list(advice), [], [])
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

    # A notice once, under load, and a clean confirmation: nothing to report.
    transient = policy(attempt(notices=[notice], advice=["first"]), attempt())
    assert (transient.failures, transient.advice) == ([], ["first"])
    # The confirmation pardons the notice and nothing else, and says it once.
    assert policy(
        attempt([error], [notice]), attempt([error, "[dark] console: later"])
    ).failures == [error, "[dark] console: later"]
    # On every rendering, which is a layout feedback loop.
    assert policy(attempt(notices=[notice]), attempt(notices=[notice])).failures == [
        f"{notice} (recurred on the confirming render attempt)"
    ]
    # A confirmation that did not finish cannot say the notice was transient.
    assert policy(
        attempt([error], [notice]), attempt(["probe failed"], complete=False)
    ).failures == [
        error,
        "probe failed",
        f"{notice} (the confirming render attempt did not complete)",
    ]
    # Nor can an attempt that did not finish ask for one.
    assert policy(attempt([error], [notice], complete=False)).failures == [
        error,
        notice,
    ]
