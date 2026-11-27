"""Browser-gate, arrival, layout, and layer integration tests."""

import itertools
import json
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from interact_support import publish

from leaf.base.findings import Finding, Rejected
from leaf.base.leases import lock_is_held
from leaf.base.state import EVENTS_FILE
from leaf.pages import page_snapshot
from leaf.pages.render_gate import command as render_gate_command
from leaf.pages.render_gate import readings as render_gate_readings
from leaf.pages.render_gate import version as render_gate_model
from leaf.pages.render_gate.command import (
    PIN_VARIABLE,
    BrowserCheck,
    WidgetQuality,
    desktop_viewport,
    user_engine,
)
from leaf.pages.validation.command import check_page
from leaf.serving import user_views
from leaf.source import render_checks
from leaf.source.structure import SourceDocument
from model.test_user_views import report


def test_swept_faults_are_reported_by_element_and_by_unbroken_run():
    """The sweep names a fault per element and per unbroken run of widths, with its
    reading at the run's narrowest. Here a spill clears between 1520px and 640px and
    returns below, so it is two runs. A clipped control is read the same way, and the
    desktop's second sample, as the page loaded, joins it: a control clipped in either
    sample of a width is clipped at that width. A squeezed table is advice wherever
    the sweep finds it. Two drawings that share a name are told apart by their place."""
    widths = sorted(render_gate_readings.SWEEP_WIDTHS, reverse=True)

    def at(width, loaded=False):
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
                    ("#mid", 520 <= width <= 560),
                    ("#loaded", loaded),
                )
                if clipped
            ],
            "covered": [],
            "labels": {"threshold_px": 10, "drawings": drawings},
            "broken": [
                {
                    "code": "broken-name",
                    "at": "<table id=n>",
                    "place": {"id": "n", "steps": []},
                    "count": 1,
                    "names": ["x-awaits"],
                }
            ]
            if width >= 1200
            else [],
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
    swept = render_gate_readings.swept_faults(
        [(1280, at(1280, loaded=True)), *readings]
    )
    assert [(f.code, f.at, f.widths) for f in swept] == [
        ("past-column", "<pre>", (1560, 1600)),
        ("clipped-control", "<button id=loaded>", (1280, 1280)),
        ("past-column", "<pre>", (360, 600)),
        ("clipped-control", "<button id=mid>", (520, 560)),
        ("clipped-control", "<button id=narrow>", (360, 440)),
    ]
    spill, _, _, _, clipped = swept
    assert clipped.severity == "error"
    assert clipped.values["lost"] == 360
    assert spill.values["past"] == 1560
    assert str(spill) == (
        "at 1560–1600px wide, <pre> is set 1560px past the column, out in the margin"
        '; to give it more room, mark it data-width="wide" or "available" rather than sizing it past the column, or scroll it sideways in a box of its own with overflow-x: auto and class="lf-scroll"'
    )
    squeezed = render_gate_readings.squeezed_advice(readings)
    assert [(f.code, f.at, f.widths, f.severity) for f in squeezed] == [
        ("broken-name", "<table id=n>", (1200, 1920), "advice"),
        ("squeezed-table", "<table id=u>", (520, 560), "advice"),
        ("squeezed-table", "<table id=t>", (360, 400), "advice"),
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
        widths=(360, 400),
    )
    assert str(finding) == (
        "at 360–400px wide, <div id=wide> is set 74px past the column, out in the margin"
        '; to give it more room, mark it data-width="wide" or "available" rather than sizing it past the column, or scroll it sideways in a box of its own with overflow-x: auto and class="lf-scroll"'
    )
    assert json.loads(json.dumps(finding.json())) == {
        "code": "past-column",
        "severity": "advice",
        "at": "<div id=wide>",
        "widths": [360, 400],
        "values": {"place": "#wide", "past": 74},
        "text": str(finding),
    }
    assert Finding.loads(finding.json()) == finding
    # Equal records are one finding, so they dedupe as their words did.
    assert len({finding, finding.but(values={})}) == 1
    with pytest.raises(ValueError):
        Finding("no-such-code")
    # A refusing code's words end with the guarantee its declaration names: input
    # a check refuses, or a page the browser's check fails. Only such a code refuses.
    upgrades = Finding("missing-upgrades", values={"tags": ["lf-x"]})
    assert (upgrades.severity, str(upgrades)) == (
        "error",
        "upgraded widgets did not define their elements: <lf-x> (fails the check so"
        " that the user sees the page's widgets and scripts work as written)",
    )
    assert upgrades.said == "upgraded widgets did not define their elements: <lf-x>"
    duplicate = Finding("duplicate-ids", values={"ids": ["a"]})
    assert str(duplicate).endswith(
        "(refused so that each id names one element for comments and commands to reach)"
    )
    with pytest.raises(ValueError):
        Rejected([finding])


def test_page_check_json_names_only_the_gates_that_read_the_page():
    """Failing page code ends the check before the render gate reads anything, so
    `--json` says the render check was asked for and did not run. A gate whose browser
    could not read the page, as one that crashed, ran no more than one no browser ran,
    and its finding fails nothing."""
    failed = Finding("page-report", values={"text": "leaf: <lf-x> failed"})
    gates = ["page code", "render check"]
    check = BrowserCheck(gates, "Chrome", page_code=[failed]).json()
    assert (check["asked"], check["ran"]) == (gates, ["page code"])
    crashed = Finding("browser-error", values={"error": "Target closed"})
    stopped = Finding("server-stopped", values={"error": "Timeout 30000ms"})
    unread = BrowserCheck(
        gates,
        "Chrome",
        page_code=[],
        render=render_gate_model.RenderReading([stopped], []),
    )
    assert (unread.ran, unread.status) == (["page code"], 0)
    assert BrowserCheck(["page code"], "Chrome", page_code=[crashed]).ran == []
    # A thread the page can't open is the page's own failure, read once the browser
    # has read the rest, so it fails the render check rather than leaving it unread.
    undrawn = Finding("thread-not-drawn", values={"thread": "t1", "error": "no card"})
    reading = render_gate_model.RenderReading([undrawn], [])
    drawn = BrowserCheck(gates, "Chrome", page_code=[], render=reading)
    assert (drawn.ran, drawn.status) == (gates, 1)
    # No browser at all reads the same way, and says what went unchecked for it.
    missing = Finding("no-browser", values={"error": "no browser launched: none"})
    assert missing.unread and missing.said.startswith("no browser launched: none; ")
    assert missing.said.endswith(
        "; the browser checks did not run, so a failure only they would find shows"
        " when a browser first draws the page"
    )
    # So with the widget quality gate, where a crash once failed the package check.
    quality = WidgetQuality(1, "Chrome", findings=(crashed,))
    assert (quality.status, quality.json()["ran"]) == (0, [])


def test_a_render_check_takes_no_screens_of_a_page_that_never_got_ready(
    page_dir, monkeypatch
):
    """A screen is taken of a ready page. Where the render reading reports that the
    page never got ready, opening the page for a screen would wait out the same
    deadline again, so `page check --render` reports the finding and opens no screens.
    A reading of a ready page gets them."""
    stuck = Finding("not-ready", values={"stage": "arrived", "error": "never landed"})
    readings = [
        render_gate_model.RenderReading([], []),
        render_gate_model.RenderReading([stuck], []),
    ]
    asked = []

    def screens(*args):
        asked.append(args)
        return page_dir, []

    monkeypatch.setattr(
        render_gate_command, "run_in_browser", lambda read, engine: (read(None), "none")
    )
    monkeypatch.setattr(
        render_gate_command, "render_version", lambda *args, **kwargs: readings.pop(0)
    )
    monkeypatch.setattr(render_gate_command, "save_screens", screens)

    ready, _ = check_page(page_dir, render=True)
    assert (len(asked), ready["status"]) == (1, 0), ready
    assert "screens" in ready["browser"], ready

    unready, _ = check_page(page_dir, render=True)
    assert len(asked) == 1, asked
    assert [f["code"] for f in unready["findings"] if f["severity"] == "error"] == [
        "not-ready"
    ]
    assert "screens" not in unready["browser"], unready


def test_a_render_checks_capture_holds_the_page_lease_only_to_read_the_log(
    page_dir, monkeypatch
):
    """Every gesture waits for the page's append lease, so the capture a render check
    serves holds the lease only while it reads the log and what is read with it. It
    executes the candidate before it takes the lease and each stored revision after
    it releases the lease."""
    publish(page_dir)
    held = []
    execute = page_snapshot.executing

    def executing(artifact):
        held.append(lock_is_held(page_dir / EVENTS_FILE))
        return execute(artifact)

    monkeypatch.setattr(page_snapshot, "executing", executing)
    candidate = SourceDocument((page_dir / "index.html").read_text())
    page_snapshot.capture_page_snapshot(page_dir, candidate, 2, url="/")
    # The candidate, then revision 1.
    assert held == [False, False]


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


def test_the_render_check_draws_in_the_engine_of_the_last_reported_browser(
    tmp_path, monkeypatch
):
    """`page check` draws in Firefox where the browser that reported last is a Firefox,
    so a break only Firefox draws reaches the author, and in Chromium for any other
    reader, before any report, and when the caller pins the check. Firefox on iOS is a
    WebKit and names itself otherwise."""
    monkeypatch.delenv(PIN_VARIABLE)
    now = datetime(2026, 11, 16, tzinfo=UTC)
    monkeypatch.setattr(user_views, "_now", lambda: now)
    assert user_engine(tmp_path) == "chromium"

    agents = {
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:160.0) Gecko/20100101"
        " Firefox/160.0": "firefox",
        "Mozilla/5.0 (Android 14; Mobile; rv:160.0) Gecko/160.0 Firefox/160.0": "firefox",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15"
        " (KHTML, like Gecko) FxiOS/146.0 Mobile/15E148 Safari/605.1.15": "chromium",
        report()["identity"]["browser"]["user_agent"]: "chromium",
    }
    for sequence, (agent, engine) in enumerate(agents.items(), start=1):
        view = report(sequence=sequence)
        view["identity"]["browser"]["user_agent"] = agent
        user_views.observe_user_view(tmp_path, view)
        assert user_engine(tmp_path) == engine, agent
    view = report(sequence=len(agents) + 1)
    view["identity"]["browser"]["user_agent"] = next(iter(agents))
    user_views.observe_user_view(tmp_path, view)
    # An agent's own browser opening the page later, such as a headless Chromium a
    # script drives, is not the reader's, and leaves the check where the reader is.
    now += timedelta(minutes=1)
    driven = report(session="b" * 32)
    driven["identity"]["browser"]["webdriver"] = True
    driven["viewport"] = {"width": 1280, "height": 720}
    user_views.observe_user_view(tmp_path, driven)
    assert user_engine(tmp_path) == "firefox"
    assert desktop_viewport(tmp_path).json()["width"] == 900
    monkeypatch.setenv(PIN_VARIABLE, "fixed")
    assert user_engine(tmp_path) == "chromium"


def test_a_handover_whose_arrivals_only_swing_ends_at_its_bound():
    """A page whose arrivals left swing between two counts at every reading, as they
    do where each arrival makes way for the next, never progresses, so its readiness
    wait ends at its bound however fast the readings come."""

    class SwingingPage:
        readings = itertools.cycle((["arrived", 2], ["arrived", 3]))

        def wait_for_function(self, expression, *, arg, timeout, polling="raf"):
            reading = (
                "arrived"
                if expression == render_checks.OUTSTANDING
                else next(self.readings)
            )
            return SimpleNamespace(json_value=lambda: reading)

    # The bound this wait is expected to run out: the readings come as fast as the
    # wait asks, so its length doesn't change the case.
    expected_stall_ms = 50
    with pytest.raises(render_checks.PageNotReady) as unready:
        render_checks.wait_until_ready(SwingingPage(), timeout_ms=expected_stall_ms)
    assert unready.value.stage == "arrived"


def test_a_handover_that_replaces_the_document_waits_on_in_the_new_one():
    """A page may replace its document on the way to ready, as a revision that cannot
    be patched in does, between the standing the old document answered and the read
    of that answer. The wait goes on in the new document rather than failing."""
    from playwright.sync_api import Error as PlaywrightError

    class ReplacingPage:
        readings = iter(("replaced", "ready"))

        def wait_for_function(self, expression, *, arg, timeout, polling="raf"):
            reading = next(self.readings)

            def json_value():
                if reading == "replaced":
                    raise PlaywrightError(
                        "JSHandle.json_value: Execution context was destroyed, "
                        "most likely because of a navigation"
                    )
                return reading

            return SimpleNamespace(json_value=json_value)

    page = ReplacingPage()
    render_checks.wait_until_ready(page)
    assert next(page.readings, None) is None


def test_a_resize_notice_fails_only_when_a_complete_confirmation_repeats_it(
    monkeypatch,
):
    """The retry policy over whole attempts (`render_version`): a notice fails the
    check only when a later complete attempt repeats it and is ignored when that
    attempt is clean, ordinary failures from both attempts stand once each, and a
    notice no complete attempt settles is dropped for what stopped that attempt.
    Advice is the first attempt's. What an attempt hears is the browser's half, read by
    `test_a_recurring_resize_notice_fails_the_render_gate`."""
    notice = Finding("resize-loop", values={"text": "ResizeObserver loop completed"})
    error = Finding("console-error", values={"text": "first attempt"})
    later = Finding("console-error", values={"text": "later"})
    failed = Finding("page-exception", values={"text": "confirming attempt"})
    first = Finding(
        "grows-with-content",
        "<lf-x id=a>",
        {"layout": "column", "box": "div", "height": 20},
    )

    def attempt(failures=(), notices=(), complete=True, advice=()):
        reading = render_gate_model.RenderReading([*failures, *advice], [], complete)
        return reading, list(notices)

    def policy(*attempts):
        left = list(attempts)
        monkeypatch.setattr(
            render_gate_model,
            "_render_version_attempt",
            lambda browser, url, desktop, served_timeout_ms=None, implementations=None, declaration_sources=None, page_code=None: (
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
    assert recurring[0].said == (
        "window error: ResizeObserver loop completed"
        " (recurred on the confirming render attempt)"
    )
    # A confirmation that did not finish settles nothing: what stopped it stands, a
    # crash leaving the page unread and the page's own failure failing it, each once.
    crashed = Finding("browser-error", values={"error": "Target closed"})
    unread = policy(attempt([error], [notice]), attempt([crashed], complete=False))
    assert unread.findings == [error, crashed]
    assert policy(
        attempt([error], [notice]), attempt([failed], complete=False)
    ).findings == [error, failed]
    # The reading is still the first attempt's, which read the page through.
    assert unread.complete
    # Nor can an attempt that did not finish ask for one, and its reading says the
    # page was never read through.
    stopped = policy(attempt([error], [notice], complete=False))
    assert (stopped.findings, stopped.complete) == ([error], False)


def test_output_contract_failures_refuse_page_and_package_checks():
    from leaf.pages.render_gate.version import RenderReading
    from leaf.source.data_contracts import output_findings

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
    assert found[0].said == (
        "<lf-counter id=count> (package producer): output 'total' value is invalid "
        "for contract 'counts' at $.count: 'wrong' is not of type 'integer'"
    )
    assert BrowserCheck(["render check"], render=RenderReading(found, [])).status == 1
    assert WidgetQuality(1, findings=tuple(found)).status == 1


def test_a_failed_request_names_the_document_that_made_it_without_its_marks():
    """A failed request names the frame's document as the user sees it, read as the
    failure arrives: neither the bootstrap's marks, which a failure can reach the
    check ahead of, nor a document the frame navigated to before collection."""
    from leaf.pages.render_gate.page_code import _failed_requests

    frame = SimpleNamespace(url="http://leaf.test/v1.html?view=a&t=key&_leaf-recovered")
    handlers = {}
    page = SimpleNamespace(
        on=lambda event, handler: handlers.setdefault(event, handler)
    )
    failures = _failed_requests(page)

    request = SimpleNamespace(
        frame=frame,
        failure="net::ERR_FAILED",
        resource_type="script",
        url="http://leaf.test/page/helper.js",
    )
    handlers["requestfailed"](request)
    frame.url = "http://leaf.test/b.html"
    # The frame has moved on to another document; a later failure names that one.
    handlers["response"](SimpleNamespace(status=404, request=request))

    assert [failure.values["frame"] for failure in failures] == [
        "http://leaf.test/v1.html?view=a",
        "http://leaf.test/b.html",
    ]


def test_a_marked_address_reads_as_the_address_the_bootstrap_leaves():
    """The bootstrap rewrites the address with `URLSearchParams`, so a failure that
    arrives before the rewrite names the same address as one that arrives after."""
    from leaf.pages.render_gate.page_code import frame_address

    marked = "http://leaf.test/v1.html?q=~*%20+a!%27()%C3%A9&t=key&_leaf-recovered#f"
    rewritten = "http://leaf.test/v1.html?q=%7E*++a%21%27%28%29%C3%A9#f"
    assert frame_address(marked) == rewritten
    assert frame_address(rewritten) == rewritten


def test_a_marked_address_keeps_an_empty_fragment():
    from leaf.pages.render_gate.page_code import frame_address

    rewritten = "http://leaf.test/v1.html?q=%7E*#"
    assert frame_address("http://leaf.test/v1.html?q=~*&t=key#") == rewritten
    assert frame_address(rewritten) == rewritten
    assert (
        frame_address("http://leaf.test/v1.html?t=key#") == "http://leaf.test/v1.html#"
    )


def test_the_address_marks_are_the_ones_the_bootstrap_takes_off():
    from leaf.base.schema import ASSETS

    bootstrap = (ASSETS / "runtime" / "bootstrap.js").read_text()
    marks = re.search(r"const marks = \[([^\]]*)\]", bootstrap)
    assert marks, "bootstrap.js no longer lists its marks as `const marks = [...]`"
    assert set(json.loads(f"[{marks.group(1)}]")) == render_checks.ADDRESS_MARKS


@pytest.mark.parametrize("code", ["clipped-content", "past-column"])
def test_a_box_a_module_built_is_told_to_scroll_by_its_package(code):
    """The page's own box scrolls sideways with the page's `lf-scroll` class; a box a
    module built (`built`) can't take the page's markup, so its finding names the
    module's mark and the package's CSS instead."""
    values = {"across": 900, "down": 0, "past": 900}
    page = str(Finding(code, "<div id=own>", values))
    built = str(Finding(code, "<div> in <lf-stages id=s>", values | {"built": True}))
    assert 'class="lf-scroll"' in page and "data-lf-scroll" not in page
    assert 'class="lf-scroll"' not in built
    assert "data-lf-scroll" in built and "package's CSS" in built
