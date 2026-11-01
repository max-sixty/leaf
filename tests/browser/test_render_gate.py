"""Browser-gate, arrival, layout, and layer integration tests."""

import itertools
import json
import re
import threading
from contextlib import contextmanager
from html import escape
from urllib.parse import urlsplit

import pytest
import tinycss2
from browser_sources import browser_function
from click.testing import CliRunner
from interact_support import (
    COMMAND_HUB_PACKAGE,
    STATED_TIMEOUT,
    add_test_widget,
    running_http_server,
)
from known_widget_findings import KNOWN, PACKAGES
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    CHANGE_SHAPES_PAGE,
    PANEL_PAGE,
    SHORT_SUGGESTION,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    CODE_CONTROL_PAGE,
    CODE_FAULT_PAGE,
    CUSTOM_WIDGET_PAGE,
    HIDDEN_SCROLLERS,
    IDENTIFIERS_IN_CODE_PAGE,
    NOTE_BESIDE_A_CHANGE,
    RESIZE_LOOP_EVENT,
    SHOT_SRC,
    SHOTS,
    WIDE_TABLE_PAGE,
    apply_restore_case,
    arrival_findings,
    motions,
    moved_at,
    page_at_rest,
    toggle_queue,
    user_view_restore_cases,
)
from render_cases_navigation import (
    CODE_PAGE,
    call_diff,
    call_node,
)
from render_cases_widgets import (
    GENERIC_VISUAL_LAYER,
    PART_DIAGRAM_PAGE,
    prefixed_visual_layer,
    visual_widgets,
)
from render_harness import (
    CORPUS_SOURCES,
    EXAMPLE_PACKAGES,
    LONG_PAGE,
    OPEN_THREAD_COUNT,
    ROOT,
    TOKEN,
    _traffic,
    _until,
    at_rest,
    compare_with,
    confirming_resize_notices,
    consume_browser_errors,
    leaf_page,
    left_alone,
    live_counts,
    open_page,
    open_threads,
    pane_scroll_behavior,
    panel_control,
    panel_menu,
    plant_quiet_word,
    primed,
    reader_state,
    reported_browser_errors,
    resized,
    root_overflow,
    scroll_followers,
    scroll_settled,
    scroll_writes,
    stamp_page,
    state_changes,
    still_page,
    take_browser_errors,
    wait_for_revision,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import layer as layer_model
from leaf import leases as leases_model
from leaf import render_checks as render_checks_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf.findings import Finding
from leaf.registry.contract import is_element_name
from leaf.render_checks import rendered, wait_until_ready
from leaf.render_gate import readings as render_gate_readings
from leaf.render_gate import scheme as render_gate_scheme
from leaf.render_gate import version as render_gate_model
from leaf.render_gate.widget_quality import own_tags
from leaf.validation import composition as validation_model

pytestmark = pytest.mark.shifts_unsurveyed

# The deadline of a wait these tests expect to expire, on a page held or refused on
# purpose: long enough for the page to reach the stall on a busy runner, and well short
# of the suite's hang bound, which would hold each of them for 30 s.
EXPECTED_STALL_MS = 5_000

BOUNDED_WORKSPACE_PAGE = leaf_page(
    "bounded workspace gate",
    """
  <header><h1>Queue</h1></header>
  <div id="gate-split">
    <lf-pane id="gate-list" label="Items"><div><p>First</p><div style="height:900px"></div><p>Last</p></div></lf-pane>
    <lf-pane id="gate-detail" label="Detail"><div><p>Subject</p><div style="height:900px"></div><button>Finish</button></div></lf-pane>
  </div>
  <footer>End of queue</footer>
""",
    head="<style>#gate-split { display: grid; grid-template-columns: 1fr 1fr; "
    "}</style>",
    layout="workspace",
)


def test_the_render_gate_reports_a_compact_spill(browser, serve):
    source = leaf_page(
        "Compact spill",
        "<h1>Compact route</h1>"
        '<p id="compact-overflow">This row spills only from compact viewports.</p>',
        head="<style>@media(max-width:600px){#compact-overflow{width:700px}}</style>",
    )
    reading = render_gate_model.render_version(browser, serve(source, packages=()))
    overflow = [
        finding for finding in reading.failures if finding.code == "page-scrolls"
    ]
    assert [(f.widths, f.scheme, f.viewports) for f in overflow] == [
        ((360, 600), None, ())
    ], reading.failures


def test_startup_shift_evidence_serializes_as_advice(browser, serve, monkeypatch):
    """Platform entries survive the real JS probe and report boundary as advice.

    Supply deterministic PerformanceObserver readings rather than depending on
    whether the compositor happened to paint before a particular module loaded.
    """
    probe = render_gate_scheme.evaluate_probe

    def with_shifts(page, name, *args, **kwargs):
        if name == "startupLayoutShifts":
            page.evaluate("""() => {
                const driver = globalThis.__leafRenderDriver;
                globalThis.__leafRenderDriver = {
                    ...driver,
                    startupLayoutShifts: () => [
                        {startTime: 0, value: .1, sources: []},
                        {startTime: 500, value: .2, sources: [{
                            node: document.querySelector('#shifted'),
                            before: {x: 0, y: 10, width: 100, height: 20},
                            after: {x: 0, y: 60, width: 100, height: 20},
                        }]},
                        {startTime: 2000, value: .15, sources: []},
                    ],
                };
            }""")
        return probe(page, name, *args, **kwargs)

    monkeypatch.setattr(render_gate_scheme, "evaluate_probe", with_shifts)
    findings, _, completed = render_gate_scheme._render_scheme(
        browser,
        serve(leaf_page("Shift evidence", '<p id="shifted">Reading.</p>'), packages=()),
        "light",
        {"width": 1200, "height": 900},
        3_000,
        [],
    )
    assert completed
    shifts = [
        finding.json() for finding in findings if finding.code == "startup-layout-shift"
    ]
    assert len(shifts) == 1
    shift = shifts[0]
    assert shift["severity"] == "advice"
    assert shift["values"]["cls"] == pytest.approx(0.3)
    assert "startup CLS 0.3000" in shift["text"]
    movement = shift["values"]["entries"][1]["sources"][0]
    assert movement["node"] == "<p id=shifted>"
    assert (movement["before"]["y"], movement["after"]["y"]) == (10, 60)


def _panel(name: str) -> str:
    return f'<section class="panel" id="{name}"><h2>{name}</h2><p>Words.</p></section>'


def test_the_render_gate_fails_a_page_that_scrolls_sideways_only_between_viewports(
    browser, serve
):
    """A body beside its track, and a row that spills only from 600 to 900px: both fixed
    viewports read the page clean, and only the sweep between them sees it. A control
    row that loses its scrollbar track room only between them is the same reading for
    the overlay bar. Below both, a decision in a card of fixed height, whose prose
    grows at 440px and narrower (a margin stands in for its wrapping) until it pushes
    the decision's controls under the card's clip: a press nobody can reach, which only
    the sweep's narrowest widths see. A card as tall as the window holds its decision
    below 600px of plan, so a window 720px tall clips it and one 900px tall does not:
    read at a user's 900px-tall desktop window, only the phone render's sweep, at its
    own height, sees it. A card whose rule for the
    dark scheme pushes its decision under the clip is clipped only in the two dark
    renders, which each read the geometry once."""
    source = leaf_page(
        "mid-width overflow",
        f"""
<h1>Mid-width spill</h1>
<div id="tracks">
  <div id="body">{_panel("plan")}{_panel("steps")}</div>
  <div id="rail">{_panel("checks")}{_panel("log")}</div>
</div>
<p id="mid-spill">{"A line that wraps at both viewports and runs on unbroken between them. " * 4}</p>
<div id="strip"><button>Summary</button><button>Release scope</button>
<button>Owner handoff</button></div>
<div id="card"><lf-ask id="go-decision"><h2>Ship it?</h2>
<p>The release passed its checks.</p><lf-options id="go" choose>
<lf-option id="go-yes"><strong>Yes</strong></lf-option>
</lf-options></lf-ask></div>
<div id="short"><div id="plan-body"></div><lf-ask id="hold-decision"><h2>Hold it?</h2>
<lf-options id="hold" choose><lf-option id="hold-yes"><strong>Yes</strong></lf-option>
</lf-options></lf-ask></div>
<div id="dusk"><lf-ask id="dusk-decision"><h2>Wait?</h2>
<p>The canary is still running.</p><lf-options id="wait" choose>
<lf-option id="wait-yes"><strong>Yes</strong></lf-option>
</lf-options></lf-ask></div>
""",
        head="""<style>
#tracks { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-4); }
@media (min-width: 600px) and (max-width: 900px) { #mid-spill { white-space: nowrap; } }
#strip { display: flex; width: 240px; overflow: auto; padding: 0 0 15px; border: 0; }
#strip button { flex: 0 0 180px; height: 40px; margin: 0; }
@media (min-width: 600px) and (max-width: 900px) { #strip { padding-bottom: 0; } }
#card { height: 400px; overflow: hidden; }
@media (max-width: 440px) { #card p { margin-bottom: 400px; } }
#short { height: 100vh; overflow: hidden; }
#plan-body { height: 600px; }
#dusk { height: 400px; overflow: hidden; }
@media (prefers-color-scheme: dark) { #dusk p { margin-bottom: 400px; } }
</style>""",
    )

    reading = render_gate_model.render_version(
        browser,
        serve(source, packages=("default",)),
        desktop={"width": 1280, "height": 900},
    )

    clipped = [f for f in reading.failures if f.code == "clipped-control"]
    assert clipped, reading.failures
    assert {(f.values["by"], f.widths) for f in clipped} == {
        ("<div id=card>", (360, 440)),
        ("<div id=short>", (360, 540)),
        ("<div id=dusk>", (1280, 1280)),
        ("<div id=dusk>", (540, 540)),
    }, clipped
    # Each card that loses its controls loses the prose above them too, at the same
    # widths: the content reading names the card, with what would show the rest.
    cut = {(f.at, f.widths) for f in reading.failures if f.code == "clipped-content"}
    assert cut == {(f.values["by"], f.widths) for f in clipped}, reading.failures
    assert {(f.code, f.at, f.widths) for f in reading.failures} - {
        (f.code, f.at, f.widths) for f in clipped
    } - {("clipped-content", *box) for box in cut} == {
        ("page-scrolls", "", (600, 880)),
    }, reading.failures
    # A strip that leaves no room for an overlay scrollbar is advice: the bar covers its
    # last line only under the pointer, and the room is the author's to choose.
    [strip] = reading.advice
    assert (strip.code, strip.at, strip.widths) == (
        "scrollbar-clearance",
        "<div id=strip>",
        (600, 880),
    ), reading.advice
    assert strip.values["clear"] == 0, strip


# Four drawings in the idiom. The first is drawn wider than the column holds, so the fit
# takes its 11px labels to under half. The second is fitted by the same fraction, and its
# 28px labels survive it. The third keeps its natural size, with the theme's 9px step
# glyph on it. The fourth is fitted like the first, but none of its words is drawn: one
# label sits in <defs>, and the other's only run is a tspan out of the layout.
DRAWN_LABELS_PAGE = leaf_page(
    "drawn labels",
    """
<h1>Rollout</h1>
<figure id="squeezed">
  <svg class="drawing" viewBox="0 0 1600 120" role="img" aria-label="Rollout stages">
    <text x="20" y="40">canary</text>
    <text x="560" y="40">region</text>
    <text x="1100" y="40">global</text>
  </svg>
</figure>
<figure id="large">
  <svg class="drawing" viewBox="0 0 1600 120" role="img" aria-label="Rollout headline">
    <text x="20" y="60" font-size="28">canary</text>
    <text x="1100" y="60" font-size="28">global</text>
  </svg>
</figure>
<figure id="natural">
  <svg class="drawing" width="200" viewBox="0 0 200 40" role="img" aria-label="Step one">
    <circle class="mark" cx="20" cy="20" r="7" />
    <text class="glyph" x="20" y="20">1</text>
    <text class="small" x="40" y="24">note</text>
  </svg>
</figure>
<figure id="undrawn">
  <svg class="drawing" viewBox="0 0 1600 120" role="img" aria-label="Rollout key">
    <defs><text x="20" y="40">draft</text></defs>
    <rect class="mark" x="20" y="60" width="200" height="40" />
    <text x="20" y="40"><tspan display="none">paused</tspan></text>
  </svg>
</figure>
""",
)


def test_user_view_checks_read_current_geometry_without_changing_the_page(
    browser, serve
):
    """A passive reading exposes layout and measured checks at the actual width.

    The same drawing's labels shrink further on a narrower window; large labels are
    clean at desktop and cross the stated threshold on mobile. A closed disclosure's
    arrangement is no part of the view, so the reading leaves it out. Reading leaves
    the DOM, focus, selection, and scroll position intact.
    """
    source = DRAWN_LABELS_PAGE.replace(
        "<h1>Rollout</h1>",
        '<h1>Rollout</h1><div id="arrangement" style="display:flex; gap:16px">'
        "<p>Canary</p><p>Global</p></div>"
        '<details><summary>Later</summary><div style="display:flex; gap:16px">'
        "<p>Europe</p><p>Asia</p></div></details>",
    )
    page = open_page(browser, serve(source, packages=()))

    def read():
        return page.evaluate(
            """async () => {
              const {readViewChecks} = await import('/checks/view.js');
              const before = {
                html: document.documentElement.outerHTML,
                focus: document.activeElement,
                selection: getSelection().toString(),
                scroll: [document.scrollingElement.scrollLeft,
                         document.scrollingElement.scrollTop],
              };
              const observer = new MutationObserver(() => {});
              observer.observe(document, {subtree:true, childList:true,
                                          attributes:true, characterData:true});
              const reading = readViewChecks([]);
              const mutations = observer.takeRecords().length;
              observer.disconnect();
              return {reading, unchanged:
                mutations === 0 &&
                before.html === document.documentElement.outerHTML &&
                before.focus === document.activeElement &&
                before.selection === getSelection().toString() &&
                before.scroll[0] === document.scrollingElement.scrollLeft &&
                before.scroll[1] === document.scrollingElement.scrollTop};
            }"""
        )

    desktop = read()
    page.set_viewport_size({"width": 600, "height": 900})
    rendered(page)
    narrow = read()

    assert desktop["unchanged"] and narrow["unchanged"]
    for result in (desktop, narrow):
        reading = result["reading"]
        (arrangement,) = reading["layout"]["arrangement"]
        assert arrangement["at"] == "<div id=arrangement>"
        assert arrangement["rows"] == "2"
        assert page.locator(arrangement["path"]).get_attribute("id") == "arrangement"
        assert reading["checks"]["horizontal_overflow_px"] == 0
        assert reading["checks"]["overflowing_regions"] == []
        assert reading["checks"]["shrunk_labels"]["threshold_px"] == 10
    (drawing,) = desktop["reading"]["checks"]["shrunk_labels"]["drawings"]
    assert drawing["at"] == "<svg> in <figure id=squeezed>"
    assert drawing["labels"] == 3
    small = narrow["reading"]["checks"]["shrunk_labels"]["drawings"]
    assert {drawing["at"] for drawing in small} == {
        "<svg> in <figure id=squeezed>",
        "<svg> in <figure id=large>",
    }
    assert small[0]["drawn"] < drawing["drawn"]


# A widget whose module draws a 120px box, where its authored markup holds nothing.
@pytest.mark.parametrize("resource", ["module", "theme"])
def test_an_unanswered_startup_resource_fails_the_render_gate(browser, serve, resource):
    """A missing response fails navigation rather than admitting an unread page."""
    holding = []

    def configure(page):
        page.set_default_timeout(EXPECTED_STALL_MS)

        def hold(route):
            if holding:
                route.continue_()
            else:
                holding.append(route)

        page.route("**/runtime/*.js" if resource == "module" else "**/theme.css", hold)

    failures, _, completed = render_gate_scheme._render_scheme(
        primed(browser.unwatched, configure),
        serve(
            leaf_page("Unanswered resource", "<h1>Waiting for a resource</h1>"),
            packages=(),
        ),
        "light",
        {"width": 1200, "height": 900},
        EXPECTED_STALL_MS,
        [],
    )
    assert holding, "the positive control held no resource"
    assert completed is False
    assert [failure.code for failure in failures] == ["no-runtime"]


@pytest.fixture
def dropped_entry_server(serve):
    """Keep the dropped request's server alive until the browser fixture closes it."""
    served = serve(leaf_page("dropped entry", "<h1>Dropped</h1>"), packages=())
    asked = threading.Event()
    release = threading.Event()

    class Drops(http_model.PageEndpoint):
        """Answers everything but the Leaf entry, which it accepts and drops."""

        def _get(self):
            if self.path.endswith("/leaf.js"):
                asked.set()
                release.wait()
                return None
            return super()._get()

    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0),
        http_model.page_endpoint(serve.page_dir, TOKEN, endpoint=Drops),
    )
    dropped = (
        urlsplit(served)
        ._replace(netloc=f"127.0.0.1:{httpd.server_address[1]}")
        .geturl()
    )
    with running_http_server(httpd):
        try:
            yield dropped, asked
        finally:
            release.set()


@pytest.fixture
def dropped_entry_page(dropped_entry_server, browser):
    """Make the browser fixture's context cleanup precede server teardown."""
    return browser.unwatched.new_page()


def test_an_unanswered_entry_fails_the_render_gate(
    dropped_entry_server, dropped_entry_page
):
    dropped, asked = dropped_entry_server
    page = dropped_entry_page
    page.set_default_timeout(EXPECTED_STALL_MS)

    class ExistingPage:
        def new_page(self, **options):
            return page

    failures, _, completed = render_gate_scheme._render_scheme(
        ExistingPage(),
        dropped,
        "light",
        {"width": 1200, "height": 900},
        EXPECTED_STALL_MS,
        [],
    )
    assert asked.is_set(), "the browser never requested the held entry"
    assert completed is False
    assert [failure.code for failure in failures] == ["no-runtime"]


def test_browser_like_console_words_remain_console_diagnostics(browser):
    """An authored message cannot establish an HTTP failure by imitating Chrome."""
    page = browser.new_page()
    text = (
        "Failed to load resource: the server responded with a status of 404 (Not Found)"
    )
    page.evaluate("text => console.error(text)", text)
    [problem] = reported_browser_errors(page, text)
    assert problem.code == "console-error"
    assert problem.values == {"text": text, "url": ""}
    assert str(problem) == text
    page.evaluate(
        "console.error('ordinary failure')\n//# sourceURL=http://page/author.js"
    )
    [problem] = reported_browser_errors(page, "ordinary failure")
    assert problem.values == {
        "text": "ordinary failure",
        "url": "http://page/author.js",
    }
    assert str(problem) == "ordinary failure — http://page/author.js"


def test_a_refused_document_reports_its_status_with_the_gate_failure(browser, serve):
    served = serve(leaf_page("Refused", "<h1>Refused</h1>"), packages=())
    refused = served.split("?")[0] + "?t=not-the-page-key"
    controlled = primed(
        browser.unwatched, lambda page: page.set_default_timeout(EXPECTED_STALL_MS)
    )
    failures, _, completed = render_gate_scheme._render_scheme(
        controlled,
        refused,
        "light",
        {"width": 1200, "height": 900},
        EXPECTED_STALL_MS,
        [],
    )
    assert completed is False
    [failure] = failures
    assert (failure.code, failure.scheme) == ("probe-failed", "light")
    assert {
        "code": "console-error",
        "severity": "error",
        "values": {
            "text": "Failed to load resource: the server responded with a status of 401 (Unauthorized)",
            "url": refused,
        },
    } in failure.values["console"], failure

    assert "401 (Unauthorized)" in str(failure)


RECURSIVE_ROWS_PAGE = leaf_page(
    "recursive rows",
    """
  <div id="rows">
    <lf-pane id="upper" label="Upper"><div><p>Upper body</p><div style="height:600px"></div></div><footer style="height:120px">Tall actions</footer></lf-pane>
    <div id="lower">
      <lf-pane id="lower-left" label="Lower left"><div><p>Left body</p></div></lf-pane>
      <lf-pane id="lower-right" label="Lower right"><div><p>Right body</p></div></lf-pane>
    </div>
  </div>
""",
    head="""<style>
#rows { display: grid; gap: var(--sp-4); }
#lower { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-4); }
</style>""",
    layout="workspace",
)


def test_recursive_rows_share_the_window_and_keep_pane_furniture_in_view(
    browser, serve
):
    """Rows in a full-height workspace's body split its height, and a pane's footer stays
    inside its row while the body above it scrolls. A window too short for the
    workspace hands the scroll to the page, where each pane takes its full height."""
    page = open_page(browser, serve(RECURSIVE_ROWS_PAGE))
    resized(page, 1200, 700)
    upper = page.locator("#upper")
    pane_scroll_behavior(page, upper, "bounded")
    boxes = page.evaluate(
        """() => {
          const box = selector => document.querySelector(selector).getBoundingClientRect();
          return {upper: box('#upper'), lower: box('#lower'),
                  footer: box('#upper > footer'), workspace: box('main')};
        }"""
    )
    assert boxes["lower"]["top"] >= boxes["upper"]["bottom"] - 1, boxes
    assert boxes["footer"]["bottom"] <= boxes["upper"]["bottom"] + 1, boxes
    assert boxes["workspace"]["bottom"] <= 700, boxes
    assert abs(boxes["upper"]["height"] - boxes["lower"]["height"]) <= 1, boxes

    resized(page, 1200, 420)
    pane_scroll_behavior(page, upper, "flow")
    flow = page.evaluate(
        """() => {
          const box = selector => document.querySelector(selector).getBoundingClientRect();
          return {upper: box('#upper'), lower: box('#lower')};
        }"""
    )
    assert flow["lower"]["top"] >= flow["upper"]["bottom"] - 1, flow
    assert flow["upper"]["height"] > 720, flow


def test_readiness_reopens_on_widget_preparation_and_retires_removed_work(
    browser, serve
):
    """Current widget preparation holds readiness; a removed owner's work retires.

    The pure coordinator tests cover ticket supersession. This browser case protects
    its integration with captured widgets, native removal, and the readiness facade.
    """
    readiness = "() => document.querySelector('script[data-lf-entry]').lfReadiness()"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Current readiness",
                '<lf-suggestion id="readiness"><lf-new>A proposed change.</lf-new></lf-suggestion>',
            )
        ),
    )
    assert page.evaluate(readiness) is None
    page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfWidgetApi();
          window.probeOlderSettled = false;
          const work = new Promise(resolve => { window.releaseProbeOlder = resolve; });
          window.probeOlder = work.then(() => { probeOlderSettled = true; });
          widgetController(document.getElementById('readiness')).present(work);
        }"""
    )
    assert page.locator("body").get_attribute("data-lf-presented") == "1"
    assert page.evaluate(readiness) == "presented"
    page.locator("#readiness").evaluate("node => node.remove()")
    wait_until_ready(page)
    assert page.evaluate("() => probeOlderSettled") is False
    page.evaluate("() => releaseProbeOlder()")
    page.evaluate("() => probeOlder")
    assert page.evaluate(readiness) != "presented"


def test_an_async_reading_probe_is_refused_instead_of_awaited(browser, serve):
    """Every shipped probe publishes a synchronous reading or readiness fact."""
    facade = (render_checks_model.PROBE_ROOT / "index.js").read_text()

    def hold_probe(page):
        page.route(
            "**/checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body=facade.replace('from "./', 'from "/checks/')
                + "\nconst held = [];\n"
                + "export const invalidPaints = () =>"
                + " new Promise((settle) => held.push(settle));\n",
            ),
        )

    failures = render_gate_model.render_version(
        primed(browser, hold_probe), serve(LONG_PAGE), served_timeout_ms=3000
    ).failures

    assert failures
    assert all(
        "probe invalidPaints must be synchronous" in failure.values["error"]
        for failure in failures
    ), f"an async reading has to name itself, and this came back as {failures}"


def test_a_devtools_issue_inside_nested_cross_origin_frames_is_unplaced(browser):
    """A same-origin inner frame cannot lend access through its outer boundary."""
    context = browser.new_context()
    context.route(
        "http://issue-top.local/**",
        lambda route: route.fulfill(
            body='<iframe src="http://issue-other.local/frame"></iframe>',
            content_type="text/html",
        ),
    )
    context.route(
        "http://issue-other.local/**",
        lambda route: route.fulfill(
            body="<iframe srcdoc='<img alt=\"An issue node\">'></iframe>",
            content_type="text/html",
        ),
    )
    page = context.new_page()
    page.goto("http://issue-top.local/")
    node = page.frame_locator("iframe").frame_locator("iframe").locator("img")
    expect(node).to_have_count(1)
    assert (
        node.evaluate(f"node => ({render_gate_readings._ISSUE_NODE}).call(node)")
        is None
    )


def test_a_rendering_turn_is_polled_from_the_driver(browser, serve):
    """A stopped compositor cannot strand the gate inside page.evaluate."""

    def stop_presenting_frames(page):
        # Runs after the driver's own init script, so it replaces what that installed.
        page.add_init_script(
            "globalThis.__leafRenderDriver = Object.freeze({"
            "...globalThis.__leafRenderDriver, framePresented: () => false });"
        )

    failures = render_gate_model.render_version(
        primed(browser, stop_presenting_frames),
        serve(LONG_PAGE),
        served_timeout_ms=3000,
    ).failures

    assert failures
    assert all(
        "no rendering update arrived within 3000ms" in f.values["error"]
        for f in failures
    ), failures


def test_a_rendering_turn_ends_after_its_intersection_observer_deliveries(
    browser, serve
):
    """A reader waiting on a rendering turn sees what that turn's IntersectionObserver
    callbacks did, such as a Copy control leaving layout once a resize and a scroll
    put its code block more than a screen away. Chrome runs those callbacks in a task
    after one the animation frame queues, so a turn marked from that task let
    `rendered` read the page before those callbacks ran."""
    page = open_page(browser, serve(LONG_PAGE))
    rendered(page)
    marked_first = page.evaluate(
        """() => new Promise(resolve => {
          const driver = globalThis.__leafRenderDriver;
          const turn = driver.requestFrame();
          const observer = new IntersectionObserver(() => {
            observer.disconnect();
            resolve(driver.framePresented(turn));
          });
          observer.observe(document.body);
        })"""
    )
    assert marked_first is False


def test_a_reload_mid_flight_never_wedges_round_trip(browser, serve, monkeypatch):
    """A navigation ends a trip the browser reports for neither kind, and the ledger
    must not carry it into the next document or every later wait there runs its
    timeout out.

    Accept-all is how a real sweep gets here: it answers its obligations one awaited
    trip at a time, so a reload after the press lands mid-cascade and kills an
    /api/event POST that then produces no `response` and no `requestfailed`.
    The held answer puts the navigation on that exact edge. The ledger is the
    document's, so what can still go wrong is the new
    document's own first trip: the same press again has to be counted there, and the
    attempt it puts in the outbox has to leave it with an outcome."""
    url = serve(CHANGE_SHAPES_PAGE)
    # The interrupted request is absent from the new document's console: the navigation
    # clears the old document and its in-flight trip together.
    page = open_page(browser, url)
    answer_ready = threading.Event()
    release_answer = threading.Event()
    reload_committed = threading.Event()
    document_path = urlsplit(url).path
    native_json = http_model.PageEndpoint._json

    def hold_first_event_answer(endpoint, *args, **kwargs):
        if (
            endpoint.method == "POST"
            and endpoint.path == "/api/event"
            and not answer_ready.is_set()
        ):
            answer_ready.set()
            release_answer.wait()
        return native_json(endpoint, *args, **kwargs)

    def release_after_reload(frame):
        if (
            answer_ready.is_set()
            and frame == page.main_frame
            and urlsplit(frame.url).path == document_path
        ):
            reload_committed.set()
            release_answer.set()

    monkeypatch.setattr(http_model.PageEndpoint, "_json", hold_first_event_answer)
    page.on("framenavigated", release_after_reload)
    try:
        panel_control(page, "blanket:accept").click()
        assert answer_ready.wait(STATED_TIMEOUT), (
            "the first event reached no server answer"
        )
        page.goto(url, wait_until="load")
        assert reload_committed.is_set(), "the replacement document did not commit"
        wait_until_ready(page)
    finally:
        release_answer.set()
    # The first trip of the new document's own cascade, which is the whole of what a
    # ledger carried across the navigation can get wrong. Waiting the answer-all out
    # instead ties this reading to how many obligations the page happens to carry.
    #
    # The trip is over when that first attempt leaves `pending`, which is the outbox's
    # own list of attempts with no outcome — a failed post keeps its attempt there and
    # retries it, so an attempt that has left came back. Neither neighbouring fact says
    # that: `acked` is counted in a `finally` around the fetch, so a post that throws
    # counts one and is retried anyway, and an empty `pending` is the momentary gap
    # between the cascade's trips, which paint-to-paint sampling steps over. One
    # attempt leaving is bounded by one trip and stays true once it holds.
    sends = _traffic(page).sends
    panel_control(page, "blanket:accept").click()
    first = []

    def first_trip_home(reading):
        # Latched on the first reading that carries the press's send. `pending` is in
        # the outbox's serial order, so its head is the earliest attempt still without
        # an outcome; a head already gone by then is a trip already home.
        if not first and reading.sends > sends:
            first.append(reading.pending[0] if reading.pending else None)
        return bool(first) and first[0] not in reading.pending

    # The wait is the assertion: it names the reading it gave up on, and no fact read
    # behind it could fail once it has returned.
    _until(page, first_trip_home, "heard back the new document's first answer")


def test_arrival_reading_reports_a_deterministic_transition(browser, serve):
    url = serve(
        leaf_page(
            "arrival transition",
            '<h1 id="title">Arrival transition</h1>'
            '<p id="arrival" style="transition: color 60s linear !important">'
            "At rest.</p>",
            head="<style>#arrival.lf-arrived { color: rgb(72, 48, 24); }</style>",
        )
    )

    def start_transition(page):
        page.add_init_script(
            """addEventListener("DOMContentLoaded", () => {
              const target = document.querySelector("#arrival");
              getComputedStyle(target).color;
              requestAnimationFrame(() => target.classList.add("lf-arrived"));
            }, { once: true });"""
        )

    arrival = arrival_findings(primed(browser.unwatched, start_transition), url)
    assert (
        "[first visit] color transitioned on p#arrival before presentation" in arrival
    )


def test_shadow_stage_withholds_package_transitions_until_presentation(
    browser, serve, tmp_path
):
    """The shared shadow stage suppresses a package transition during arrival."""
    theme = tmp_path / "transition-theme"
    theme.mkdir()
    (theme / "widget-shadow.css").write_text(
        ":host(lf-diff) details { transition: color 60s linear; }\n"
    )
    page = browser.new_page()
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(
        serve(PANEL_PAGE, packages=(*EXAMPLE_PACKAGES, "./transition-theme")),
        wait_until="load",
    )
    render_checks_model.wait_for_probe(page, "upgraded")
    assert held, "the state read completed before the shadow guard was observed"
    assert page.locator("body").get_attribute("data-lf-presented") is None
    assert (
        page.evaluate(
            """() => getComputedStyle(document.querySelector("#how-patch")
                  .shadowRoot.querySelector("details")).transitionProperty"""
        )
        == "none"
    )

    held.pop().continue_()
    page.unroute("**/api/state*")
    wait_until_ready(page)
    assert (
        page.evaluate(
            """() => getComputedStyle(document.querySelector("#how-patch")
                  .shadowRoot.querySelector("details")).transitionProperty"""
        )
        == "color"
    )


def test_page_navigation_classifies_only_its_resize_notices(browser, serve):
    first_load_only = (
        """addEventListener('DOMContentLoaded', () => {
      const seen = Number(sessionStorage.getItem('lf-test-resize-loads') || 0);
      sessionStorage.setItem('lf-test-resize-loads', String(seen + 1));
      if (seen === 0) """
        + RESIZE_LOOP_EVENT
        + """
    });"""
    )
    page = open_page(browser, serve(LONG_PAGE), init_script=first_load_only)

    page.evaluate(RESIZE_LOOP_EVENT)
    errors = take_browser_errors(page)
    assert [(e.code, e.values) for e in errors] == [
        (
            "resize-loop",
            {"text": "ResizeObserver loop completed with undelivered notifications."},
        )
    ], "a notice after the classified navigation was hidden too"


def test_page_navigation_reports_a_recurring_resize_notice(browser, serve):
    every_load = (
        "addEventListener('DOMContentLoaded', () => {" + RESIZE_LOOP_EVENT + "});"
    )
    page = open_page(browser, serve(LONG_PAGE), init_script=every_load)

    errors = take_browser_errors(page)
    assert [(e.code, e.values.get("confirmation")) for e in errors] == [
        ("resize-loop", "recurred")
    ]


def test_the_render_gate_refuses_visual_inventories_it_cannot_trust(
    browser, serve, tmp_path, monkeypatch
):
    """A provider registers its inventory and declares which generated ids it admits."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
    callout = json.loads((tmp_path / ".leaf" / "registry.json").read_text())[
        "lf-callout"
    ]
    callout["properties"]["parts"] = {"type": "string", "minLength": 1}
    callout["x-visual"] = {"parts": "parts"}
    prefixed = prefixed_visual_layer("out", "inn")["lf-test-visual"]
    layer = {
        **GENERIC_VISUAL_LAYER,
        "lf-test-visual-prefixed": {
            **prefixed,
            "x-example": '<lf-test-visual-prefixed id="example"></lf-test-visual-prefixed>',
        },
        "lf-callout": callout,
    }
    widgets = visual_widgets() | visual_widgets(tag="lf-test-visual-prefixed")
    markup = CUSTOM_WIDGET_PAGE.replace(
        "</main>",
        """<lf-test-visual-prefixed id="prefixed"></lf-test-visual-prefixed>
</main>""",
    )
    failures = render_gate_model.render_version(
        browser.unwatched,
        serve(markup, layer_registry=layer, layer_widgets=widgets),
    ).failures

    def problems(tag):
        return [
            (f.scheme, f.at, problem)
            for f in failures
            if f.code == "visual-parts" and f.at.startswith(f"<{tag} ")
            for problem in f.values["problems"]
        ]

    assert {problem["kind"] for _, _, problem in problems("lf-callout")} == {
        "unregistered"
    }, failures
    assert problems("lf-test-visual-prefixed") == [
        (
            scheme,
            "<lf-test-visual-prefixed id=prefixed>",
            {"kind": "unadmitted-parts", "parts": ["html"]},
        )
        for scheme in ("light", "dark")
    ]


def test_replay_findings_keep_the_throw_site(browser, serve):
    """A direct complete-state replay retains the package's original exception."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    page.evaluate("""async () => {
      const {validationWidgetStates} = await window.__lfCheckApi();
      const widget = validationWidgetStates().find(s => s.widget?.redraw).widget;
      window.restoreReplay = () => { delete widget.render; };
      widget.render = function replayProjection() { throw new TypeError('replay rejected'); };
    }""")
    try:
        findings = render_checks_model.evaluate_probe(page, "relativeReplays")
    finally:
        page.evaluate("restoreReplay()")
    [finding] = findings
    assert finding["code"] == "render-threw", finding
    assert 'File "' not in finding["error"], finding
    assert "TypeError: replay rejected" in finding["error"]
    assert "replayProjection" in finding["error"]


def test_the_render_gate_refuses_duplicate_diagram_identities(browser, serve):
    """Two named boxes cannot share the same stable comment identity."""
    page = PART_DIAGRAM_PAGE.replace(
        "</lf-diagram>",
        """</lf-diagram>
<lf-diagram id="model" parts="all"><pre>
classDiagram
  namespace Job {
    class Job
  }
</pre></lf-diagram>""",
        1,
    )
    failures = render_gate_model.render_version(browser.unwatched, serve(page)).failures
    assert [(f.scheme, f.code, f.at) for f in failures] == [
        (scheme, "console-error", "") for scheme in ("light", "dark")
    ], failures
    assert all(
        'leaf: <lf-diagram id="model"> failed:' in f.values["text"]
        and "Job" in f.values["text"]
        for f in failures
    ), failures


def test_diagrams_preserve_late_state_labels_and_sequence_titles(browser, serve):
    """Both sources used to draw successfully while silently dropping their words."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "diagram semantics",
                """
<h1 id="title">Diagram semantics</h1>
<lf-diagram id="life" parts="all"><pre>
stateDiagram-v2
  [*] --&gt; A
  A --&gt; B
  state "Preparing order" as A
  state A {
    Fetch --&gt; Build
  }
</pre></lf-diagram>
<lf-diagram id="exchange" parts="all"><pre>
sequenceDiagram
  title Order handshake
  loop Retry
    User-&gt;&gt;Server: Submit order
  end
  Note right of Server: Checks order
</pre></lf-diagram>
<lf-diagram id="relationships" parts="all"><pre>
erDiagram
  RUNNER ||--o{ JOB : runs
</pre></lf-diagram>
<lf-diagram id="identities" parts="all"><pre>
flowchart TD
  123[Start] --&gt; Ω[Done]
</pre></lf-diagram>
""",
            )
        ),
    )
    expect(page.locator("#life svg")).to_contain_text("Preparing order")
    expect(page.locator("#exchange svg")).to_contain_text("Order handshake")
    assert set(page.locator("#life").evaluate("e => [...e.visualParts.keys()]")) == {
        "node:A",
        "node:B",
        "node:Fetch",
        "node:Build",
    }
    assert page.locator("#exchange").evaluate("e => [...e.visualParts.keys()]") == [
        "node:User",
        "node:Server",
    ]

    svg = page.locator("#exchange svg").element_handle()
    for scheme in ("dark", "light"):
        page.emulate_media(color_scheme=scheme)
        paint = page.locator("#exchange svg").evaluate("""svg => {
          const paper = getComputedStyle(document.body).backgroundColor;
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 1;
          const ctx = canvas.getContext('2d', {willReadFrequently: true});
          const luminance = color => {
            ctx.fillStyle = color;
            ctx.fillRect(0, 0, 1, 1);
            return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3)
              .map(c => c / 255)
              .map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
              .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
          };
          return [...document.querySelectorAll('#exchange svg text, #exchange svg tspan, #relationships svg text, #relationships svg tspan')]
            .filter(e => !e.children.length && e.textContent.trim())
            .map(e => {
              const fill = getComputedStyle(e).fill;
              const background = luminance(paper);
              const text = luminance(fill);
              const contrast = (Math.max(background, text) + 0.05)
                / (Math.min(background, text) + 0.05);
              return {text: e.textContent, fill, contrast};
            });
        }""")
        assert {p["text"] for p in paint} >= {
            "User",
            "Server",
            "[Retry]",
            "Checks order",
            "runs",
        }, paint
        assert all(p["contrast"] >= 4.5 for p in paint), (scheme, paint)
        assert svg.evaluate("e => e === document.querySelector('#exchange svg')")

    assert page.locator("#identities").evaluate("e => [...e.visualParts.keys()]") == [
        "node:123",
        "node:%CE%A9",
    ]


DIAGRAM_FAMILIES = {
    "pie": 'pie title Pets\n  "Dogs" : 386\n  "Cats" : 85',
    "gantt": "gantt\n  dateFormat YYYY-MM-DD\n  tickInterval 2day\n  section Build\n  Draft :a1, 2026-01-01, 3d\n  Review :after a1, 2d",
    # A box whose id is several words can never be a part, and still has to draw.
    "mindmap": "mindmap\n  root((Leaf))\n    Big idea\n    Threads",
    "er-quoted-name": 'erDiagram\n  "Line Item" ||--o{ ORDER : in',
    "timeline": "timeline\n  2025 : Draft\n  2026 : Ship",
    "journey": "journey\n  title Review\n  section Read\n    Open page: 5: User",
    "quadrant": "quadrantChart\n  x-axis Low --&gt; High\n  y-axis Low --&gt; High\n  A: [0.3, 0.6]",
    "git-graph": "gitGraph\n  commit\n  branch fix\n  commit\n  checkout main\n  merge fix",
    "architecture": "architecture-beta\n  service api(server)[API]\n  service db(database)[DB]\n  api:R --&gt; L:db",
    "radar": "radar-beta\n  axis a, b, c\n  curve one{1, 2, 3}",
}


def _author_lying_callout(tmp_path):
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
    module = tmp_path / ".leaf" / "widgets" / "lf-callout.js"
    module.write_text(
        'import { once } from "/runtime/widget-api.js";\n'
        "customElements.define(\n"
        '  "lf-callout",\n'
        "  class extends HTMLElement {\n"
        "    connectedCallback() {\n"
        "      if (!once(this)) return;\n"
        '      this.textContent = "Entirely different words.";\n'
        "    }\n"
        "  },\n"
        ");\n"
    )


@pytest.mark.parametrize(
    ("failed_stage", "expects_projection"),
    [
        ("pageSettled", True),
        ("arrived", True),
        ("presented", False),
        ("log", False),
        ("state", False),
    ],
)
def test_only_a_final_settling_failure_keeps_projection_findings(
    browser, serve, tmp_path, monkeypatch, failed_stage, expects_projection
):
    monkeypatch.chdir(tmp_path)
    _author_lying_callout(tmp_path)
    if failed_stage == "pageSettled":
        probe = render_gate_scheme.wait_for_probe

        def moving(page, name, *args, **kwargs):
            if name == "pageSettled":
                raise PlaywrightTimeout("held moving")
            return probe(page, name, *args, **kwargs)

        monkeypatch.setattr(render_gate_scheme, "wait_for_probe", moving)
    else:

        def unready(*_args, **_kwargs):
            raise render_checks_model.PageNotReady(failed_stage, f"held {failed_stage}")

        monkeypatch.setattr(render_gate_scheme, "wait_until_ready", unready)

    failures, _notices, completed = render_gate_scheme._render_scheme(
        browser,
        serve(CUSTOM_WIDGET_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf")),
        "light",
        {"width": 1200, "height": 900},
        3_000,
        [],
    )

    assert completed is True
    codes = {failure.code for failure in failures}
    assert ("verbatim" in codes) is expects_projection
    assert ("never-settled" in codes) is (failed_stage == "pageSettled")


def test_a_transition_on_a_hidden_control_leaves_the_page_settled(
    firefox_browser, serve
):
    """A scheme switch starts the colour transitions of controls inside a closed
    disclosure too. Firefox never runs them while the disclosure stays closed, and they
    move no box, so the page settles; reading them as motion held `leaf-dev probe
    --browser firefox` on live-progress until its 120 s limit."""
    page = open_page(
        firefox_browser,
        serve(
            leaf_page(
                "a transition in a closed disclosure",
                "<h1>Settles</h1><details><summary>More</summary>"
                '<input id="hidden-field" style="transition: color 150ms; '
                'color: var(--ink)"></details>',
            )
        ),
    )
    page.emulate_media(color_scheme="dark")
    assert page.evaluate(
        "() => document.getElementById('hidden-field').getAnimations().length"
    )
    render_checks_model.wait_for_probe(page, "pageSettled")


def test_the_state_wait_follows_a_source_rewritten_under_it(browser, serve):
    """Any process may rewrite a source, so the answer the gate took can name a
    reading the page has already moved past. A reading is a digest with no order;
    the page presenting an answer the server took later has caught up."""
    url = serve(
        leaf_page(
            "moving source",
            '<h1>Notes</h1><lf-text-document id="notes" source="notes">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "notes", "First.\n")
    page = open_page(browser, url)
    held = render_gate_scheme.served(page, url, "/api/state").json()
    data_model.cmd_data_set(serve.page_dir, "notes", "Second.\n")
    expect(page.locator("#notes code")).to_have_text("Second.\n")
    expect(page.locator("body")).not_to_have_attribute(
        "data-lf-reading", held["reading"]
    )
    wait_until_ready(page, held)


def test_a_pane_compares_its_words_without_its_opaque_children_rendered_data(
    browser, serve
):
    source = leaf_page(
        "Patch reading",
        '<lf-pane id="files" label="Files"><header>Changed files</header>'
        '<lf-file-tree id="tree" for="patch"></lf-file-tree></lf-pane>'
        '<lf-pane id="code" label="Code"><header>Patch</header>'
        '<div><svg id="drawing" viewBox="0 0 240 40"><text x="0" y="24">'
        "UNCHANGED DRAWING</text></svg>"
        '<lf-diff id="patch" view="file"><pre>'
        "diff --git a/config.txt b/config.txt\n"
        "--- a/config.txt\n+++ b/config.txt\n@@ -1 +1 @@\n-old\n+new\n"
        "</pre></lf-diff></div><footer>Tests not run</footer></lf-pane>",
    )
    page = open_page(browser, live_url(serve(source, packages=("diff", "file-tree"))))
    # The pane's prose, without its opaque children's rendered data, owns the inline
    # explanation of a revision.
    stamp_page(
        serve.page_dir,
        source.replace(">Patch</header>", ">xxx  </header>").replace(
            ">Tests not run</footer>", ">  yyy</footer>"
        ),
        "Approve patch",
    )
    wait_for_revision(page, 2)
    compare_with(page, 1)
    change = page.locator('[data-lf-margin-for="code"] [data-lf-kinds~="change"]')
    change.click()
    expect(page.locator("#code .lf-version-inline-deletion del")).to_have_text(
        "Patch Tests not run"
    )
    assert page.evaluate(
        "() => [...CSS.highlights.get('lf-version-insert') ?? []].map(range => range.toString())"
    ) == ["xxx  ", "  yyy"]
    expect(page.locator("#patch .lf-version-inline-deletion")).to_have_count(0)
    change.click()
    expect(page.locator("#code > header")).to_have_text("xxx")


def test_the_state_wait_follows_a_source_back_to_the_version_the_page_shows(
    browser, serve
):
    """A source can move away and back between the gate's read and the page's. The page
    never sees the version the gate holds, and the reading it does see changes nothing
    it shows, yet it is a reading the server took later, so the page has caught up."""
    url = serve(
        leaf_page(
            "returning source",
            '<h1>Notes</h1><lf-text-document id="notes" source="notes">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "notes", "First.\n")
    page = open_page(browser, url)
    reads = []
    page.route("**/api/state*", lambda route: reads.append(route))
    data_model.cmd_data_set(serve.page_dir, "notes", "Second.\n")
    held = render_gate_scheme.served(page, url, "/api/state").json()
    data_model.cmd_data_set(serve.page_dir, "notes", "First.\n")
    for read in reads:
        read.continue_()
    page.unroute("**/api/state*")
    wait_until_ready(page, held)
    expect(page.locator("#notes code")).to_have_text("First.\n")


def test_the_state_wait_covers_a_status_that_moves_neither_log_nor_data(browser, serve):
    """A declared status and a live watcher are part of what the server holds and of
    what the page shows, though neither appends to the log or rewrites a source. A page
    caught up with the answer that carries them already shows them, with no retry left
    to the reader."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url)
    declared = CliRunner().invoke(cli_model.cli, ["page", "open", str(serve.page_dir)])
    assert declared.exit_code == 0, declared.output
    claim = service_model.page_claim(serve.page_dir)
    lease_path = leases_model.waiter_lease_path(
        serve.page_dir, claim["id"] if claim else None
    )
    assert lease_path is not None
    lease = leases_model.take_wait_lease(lease_path)
    try:
        held = render_gate_scheme.served(page, url, "/api/state").json()
        wait_until_ready(page, held, through="state")
        # The leaf names the agent's status.
        assert "Ready" in page.locator(".lf-fp-leaf").get_attribute("aria-label")
    finally:
        leases_model.release_lease(lease)


def test_the_render_gate_holds_project_widgets_to_their_declarations(
    browser, serve, tmp_path, monkeypatch, declared_reading_package
):
    """Bug-backs for the module contracts the gate enforces, one project widget each,
    on one page, beside the DevTools issues the page owns.

    `lf-callout` declares x-verbatim while its module renders other words in the
    body's stead (quotes would strand on words the screen no longer shows).
    `author-card` is the clean control beside it: a page script's own custom element
    with a shadow root it attached itself, which the gate accepts, since the passage
    reading leaves an undeclared root's words alone and reads its host by its light
    children, as the file does.

    `lf-dusk` replaces its words in the dark scheme only, so the verbatim check runs in
    each color scheme and reports it once, there.

    `lf-stager` breaks the other thing a declaration promises: that the words arrive.
    The word pass stops at a shadow boundary on purpose — which widgets the page holds
    is the document's question — so an element a module stages into its own tree keeps
    its declarations and gets no pass, and the failure is silence: no error, no missing
    box. It stages a declared lf-reading whose declaration names an x-says word, and
    the gate is asked for it. A staged element rather than a module that wipes its own
    body after the pass has run, which is the same failure by a route that races the
    module's own render, and a bug-back that has to win a race is a bug-back that
    reports the machine.

    `lf-veil` is the host case of that failure: its declarations are on the element that
    stages the tree, so the pass finds it and writes into a light DOM the shadow root
    hides. It is the half a reading of the markup cannot see. `textContent` returns a
    hidden light-DOM span and `querySelector` finds it, so a check written against the
    markup passes on a page whose user is never handed the word. Asking `says()` for
    the words is what tells the two apart — the layer's own reading enters a declared
    root in the host's stead."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    _author_lying_callout(tmp_path)
    for tag in ("lf-dusk", "lf-stager", "lf-veil"):
        add_test_widget(package, tag, upgrade=True)
    registry_path = package / "registry.json"
    declarations = json.loads(registry_path.read_text())
    for tag in ("lf-stager", "lf-veil"):
        # Each module shows a tree of its own rather than the body, and declares it.
        declarations[tag].pop("x-verbatim")
        declarations[tag]["x-shadow"] = True
    veil = declarations["lf-veil"]
    veil["properties"]["label"] = {"type": "string"}
    veil["x-says"] = {"label": "before"}
    registry_path.write_text(json.dumps(declarations, indent=2))
    modules = {
        "lf-dusk": (
            "  connectedCallback() {\n"
            "    if (!once(this)) return;\n"
            '    if (matchMedia("(prefers-color-scheme: dark)").matches)\n'
            '      this.textContent = "Dark replacement.";\n'
            "  }\n"
        ),
        "lf-stager": (
            "  connectedCallback() {\n"
            "    if (!once(this)) return;\n"
            '    const staged = document.createElement("lf-reading");\n'
            '    staged.id = "staged-reading";\n'
            '    staged.setAttribute("label", "09:00");\n'
            '    staged.textContent = "The feeder stopped.";\n'
            "    shadowStage(this, [staged]);\n"
            "  }\n"
        ),
        "lf-veil": (
            "  connectedCallback() {\n"
            "    if (!once(this)) return;\n"
            '    const stage = document.createElement("p");\n'
            '    stage.textContent = "The feeder stopped overnight.";\n'
            "    shadowStage(this, [stage]);\n"
            "  }\n"
        ),
    }
    for tag, body in modules.items():
        (package / "widgets" / f"{tag}.js").write_text(
            'import { once, shadowStage } from "/runtime/widget-api.js";\n'
            f'customElements.define("{tag}", class extends HTMLElement {{\n'
            + body
            + "});\n"
        )
    # A lazy image that holds no room is reported only in DevTools' Issues panel. The
    # page owns an image it authors in a form-associated control's light DOM, and a
    # frame it embeds, whose issue is placed at the frame. The same image in the
    # control's shadow tree is the control's implementation, even inside a frame, so
    # the page is not refused for it.
    src = SHOT_SRC["before"]
    control = f"""<script type="module">
customElements.define("field-host", class extends HTMLElement {{
  static formAssociated = true;
  constructor() {{
    super();
    this.attachShadow({{ mode: "open" }}).innerHTML =
      '<slot></slot><img src="{src}" alt="" loading="lazy">';
  }}
}});
</script></head>"""
    shadow_frame = escape(
        "<head>" + control + "<body><field-host></field-host></body>", quote=True
    )
    # Its root shows words of its own, slots one light child and leaves another out.
    author_card = """<script type="module">
customElements.define("author-card", class extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML =
      '<h3>Shown by the root</h3><p><slot name="lead"></slot></p>';
  }
});
</script>"""
    source = (
        CUSTOM_WIDGET_PAGE.replace("</head>", author_card + control)
        .replace(
            '<h1 id="title">Project vocabulary</h1>',
            f"""<h1 id="title">Project vocabulary</h1>
<img id="unsized" src="{src}" alt="A panel" loading="lazy">
<img id="sized" src="{src}" alt="A panel" loading="lazy" width="600" height="300">
<field-host id="host"><img id="authored" src="{src}" alt="" loading="lazy"></field-host>
<iframe id="frame" title="A frame" srcdoc='<img src="{src}" alt="" loading="lazy">'>
</iframe>
<iframe id="shadow-frame" title="A control’s shadow tree" srcdoc="{shadow_frame}"></iframe>""",
        )
        .replace(
            "</main>",
            '<lf-dusk id="dusk-note"><strong>Heads up</strong> Read in both schemes.'
            "</lf-dusk>\n"
            '<lf-stager id="staged-note"><strong>Heads up</strong> Staged.</lf-stager>\n'
            '<lf-veil id="veiled-note" label="Escalated">'
            "<strong>Heads up</strong> Clipped words.</lf-veil>\n"
            '<author-card id="author-card"><span slot="lead">Slotted lead.</span>'
            "Unslotted source.</author-card>\n</main>",
        )
    )

    reading = render_gate_model.render_version(
        browser,
        serve(
            source,
            packages=(*EXAMPLE_PACKAGES, "./.leaf"),
            media={src: SHOTS["before"]},
        ),
    )
    failures = reading.failures

    def reported(code, at=""):
        return [f for f in failures if f.code == code and at in f.at]

    assert reported("verbatim", "custom-note"), failures
    assert not [f for f in failures if "author-card" in f.at + str(f)], failures
    dusk = reported("verbatim", "dusk-note")
    assert [f.scheme for f in dusk] == ["dark"], failures
    assert {f.values["value"] for f in reported("silent-word")} >= {
        "09:00",
        "Escalated",
    }, failures
    # Delivery serves media under the revision, so the issue names that URL.
    issues = [f for f in reading.advice if f.code == "devtools-issue"]
    # Chromium may emit the same issue for a frame more than once. The gate's
    # contract is which owned source nodes receive it, not CDP's event count.
    assert {(f.scheme, f.at, f.values["issue"]) for f in issues} == {
        (scheme, where, "LazyLoadImageIssue")
        for scheme in ("light", "dark")
        for where in ("<img id=unsized>", "<img id=authored>", "<iframe id=frame>")
    }, failures
    assert all(
        [key for key, _ in f.values["details"]] == ["url"]
        and dict(f.values["details"])["url"].endswith(src)
        for f in issues
    ), issues


def _author_stateful_verbatim_widget(tmp_path):
    """A stateful widget whose corrupt state rewrites prose it does not own: its own
    paragraph, or, inside the preserving `lf-shell` wrapper, the wrapper's."""
    add_test_widget(tmp_path / ".leaf", "lf-stateful", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    stateful = declarations["lf-stateful"]
    stateful["properties"].update(
        {
            "user": {"type": "string"},
            "agent": {"type": "string"},
            "restated": {"type": "boolean"},
            "overruled": {"type": "boolean"},
        }
    )
    stateful["x-state"] = {
        "change": {
            "unit": "widget",
            "record": {"kind": "value", "attr": "user"},
        },
        "status": {
            "writer": "agent",
            "unit": "widget",
            "record": {"kind": "value", "attr": "agent"},
        },
    }
    declarations["lf-shell"] = {
        "description": "A preserving wrapper around a stateful child.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": True,
        "x-verbatim": True,
        "x-example": '<lf-shell id="shell-example">Example</lf-shell>',
    }
    registry_path.write_text(json.dumps(declarations, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-shell.js").write_text(
        'import { once } from "/runtime/widget-api.js";\n'
        'customElements.define("lf-shell", class extends HTMLElement {\n'
        "  connectedCallback() { once(this); }\n"
        "});\n"
    )
    (tmp_path / ".leaf" / "widgets" / "lf-stateful.js").write_text(
        'import { LeafElement, keepsText } from "/runtime/widget-api.js";\n'
        'customElements.define("lf-stateful", class extends LeafElement {\n'
        "  render() {\n"
        "    const { state } = this;\n"
        '    if (state.change.value === "corrupt" || state.status.value === "corrupt")\n'
        '      keepsText(this.closest("lf-shell")?.querySelector(":scope > p")'
        ' ?? this.querySelector("p"), "State replaced unrelated prose.");\n'
        "  }\n"
        "});\n"
    )


# The page's longest scroller, the one its reader spends the scroll in.
READING_SCROLLER = (
    "[document.scrollingElement, ...document.querySelectorAll('*')]"
    ".filter((el) => el === document.scrollingElement ||"
    " /auto|scroll/.test(getComputedStyle(el).overflowY))"
    ".sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight))[0]"
)
# Eight small steps down and back, from a third of the way in.
SCROLL_PASS = (30,) * 8 + (-30,) * 8


def unread_syntax(page):
    """Code tokens the page paints too faint to read, in each colour scheme."""
    unread = []
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        # The scheme's colours land through transitions; read where they end.
        page.evaluate(
            "() => document.getAnimations().forEach("
            "(a) => a instanceof CSSTransition && a.finish())"
        )
        unread += [
            Finding.read(u, scheme=scheme)
            for u in render_checks_model.evaluate_probe(page, "unreadSyntax")
        ]
    return unread


def scroll_findings(page):
    """Scrolling a page writes to its DOM only where the scroll changed a state: which
    section is current, which row a key reaches. Nothing is rewritten with the value it
    already held (the browser fixture fails that on any page), and nothing is placed
    from scroll events, since what follows the scroll is laid out by the browser, which
    carries it with the scroll itself.

    Every write costs Chrome a repaint of the whole document while a highlight holds a
    range, which every page with a quoted comment does, so a write on every scroll event
    makes the scroll judder. The pass runs twice and the second is read: the first is
    where the pass's own arrivals happen, such as a margin row laid out as it comes
    into view. A page too short for the pass has nothing to read."""
    reach = page.evaluate(
        f"() => {{ const s = {READING_SCROLLER}; return s.scrollHeight - s.clientHeight; }}"
    )
    # From a third of the way in, the pass must reach its depth before the page ends.
    if reach < 1.5 * sum(step for step in SCROLL_PASS if step > 0):
        return []
    page.evaluate(
        f"reach => {{ {READING_SCROLLER}.scrollTop = Math.round(reach / 3); }}", reach
    )
    rendered(page)
    scroll_writes(page, SCROLL_PASS, READING_SCROLLER)
    return scroll_followers(
        scroll_writes(page, SCROLL_PASS, READING_SCROLLER), len(SCROLL_PASS)
    )


def rest_findings(page):
    """A page nobody touches writes nothing, asks for no frame, moves no focus, and runs
    no animation without end, in its own document or any it frames. Its clock still
    ticks, to read the server and age what it shows, and a tick that changed nothing
    writes nothing. A loop that keeps the page awake costs the reader's battery for as
    long as the tab stays open, and with a quoted comment on the page each write repaints
    the whole document.

    The reader has asked for reduced motion, which is when a page owes stillness: one who
    allows motion may be shown a page's own film playing itself (rust-sort's)."""
    return at_rest(page)


@pytest.mark.parametrize("work", [1, 10])
def test_rest_runs_its_timer_callbacks_before_reading(browser, serve, work):
    """A delayed passive write is observed with ten times the callback's CPU work."""
    page = still_page(browser, serve(leaf_page("Rest clock", "<p>Reading</p>")))
    page.evaluate(
        """work => {
            Object.defineProperty(window, 'lfRest', {
                configurable: true,
                set(rest) {
                    Object.defineProperty(window, 'lfRest', {
                        value: rest, writable: true, configurable: true
                    });
                    setTimeout(() => {
                        let total = 0;
                        for (let i = 0; i < 500000 * work; i++) total += Math.sqrt(i);
                        window.restWork = total;
                        document.body.setAttribute('data-late', 'yes');
                    }, 4000);
                }
            });
        }""",
        work,
    )
    assert any("data-late" in finding for finding in at_rest(page))


def test_rest_waits_for_contained_arrival_before_arming(browser, serve):
    source = leaf_page(
        "Contained arrival",
        '<lf-sample id="sample"><template id="content" data-sample>'
        "<p>Example</p></template></lf-sample>",
    )
    page = still_page(browser, serve(source))
    child = page.frames[1]
    wait_until_ready(child)
    child.evaluate(
        """async () => {
            const {afterPresentation} = await window.__lfWidgetApi();
            const entry = document.querySelector('script[data-lf-entry]');
            afterPresentation(() => new Promise(resolve => {
                entry.releaseArrival = () => {
                    document.body.setAttribute('data-arrived', 'yes');
                    resolve();
                };
            }));
        }"""
    )

    page.clock.run_for(1100)
    assert (
        child.evaluate(
            "() => document.querySelector('script[data-lf-entry]').lfReadiness(null)"
        )
        == "arrived"
    )
    child.evaluate(
        """() => {
            const entry = document.querySelector('script[data-lf-entry]');
            const readiness = entry.lfReadiness;
            entry.lfReadiness = (...args) => {
                entry.lfReadiness = readiness;
                queueMicrotask(entry.releaseArrival);
                return readiness(...args);
            };
        }"""
    )
    assert at_rest(page) == []
    assert child.locator("body").get_attribute("data-arrived") == "yes"


def test_reader_state_observes_behavior_without_freezing_the_dom(browser, serve):
    """The round-trip oracle detects user loss and permits equivalent markup."""
    page = browser.new_page()
    page.set_content(
        '<main><h1>Reading</h1><label>Draft <input value="kept words"></label>'
        "<button>Continue</button><button>Continue</button>"
        "<div id=scroll>Scrollable words</div>"
        "<div id=editable contenteditable=true>Editable words</div>"
        "<div hidden>Cached content</div></main>"
    )
    field = page.get_by_role("textbox", name="Draft")
    field.focus()
    field.evaluate("node => node.setSelectionRange(2, 5, 'backward')")
    first = reader_state(page)

    # Implementation-only state and an anonymous wrapper have no user effect.
    page.locator("main").evaluate(
        "node => { node.dataset.internalEpoch = 'next'; "
        "node.querySelector('h1').innerHTML = '<span>Reading</span>'; }"
    )
    assert reader_state(page) == first

    # Property state is invisible to raw HTML; selection and focus are independent
    # of accessibility. Rendered boxes catch layout without reading CSS spellings.
    for change, restore in (
        ("node.value = 'lost words'", "node.value = 'kept words'"),
        ("node.setSelectionRange(0, 0)", "node.setSelectionRange(2, 5, 'backward')"),
        ("node.disabled = true", "node.disabled = false"),
    ):
        field.evaluate(f"node => {{ {change}; }}")
        assert reader_state(page) != first, change
        field.evaluate(f"node => {{ {restore}; }}")
        field.focus()
        field.evaluate("node => node.setSelectionRange(2, 5, 'backward')")
        assert reader_state(page) == first

    button = page.get_by_role("button", name="Continue").first
    button.evaluate("node => node.tabIndex = -1")
    assert reader_state(page) != first, "losing a Tab route must be observable"
    button.evaluate("node => node.removeAttribute('tabindex')")
    assert reader_state(page) == first
    scroll = page.locator("#scroll")
    for tab_index in (-1, 0):
        scroll.evaluate("(node, value) => node.tabIndex = value", tab_index)
        assert reader_state(page) != first, "a stale scroll stop must be observable"
        scroll.evaluate("node => node.removeAttribute('tabindex')")
        assert reader_state(page) == first

    editable = page.locator("#editable")
    editable.evaluate("node => node.removeAttribute('contenteditable')")
    assert reader_state(page) != first, "losing an editing route must be observable"
    editable.evaluate("node => node.setAttribute('contenteditable', 'true')")
    assert reader_state(page) == first

    button.focus()
    assert reader_state(page) != first, "focus loss must be observable"
    on_button = reader_state(page)
    page.get_by_role("button", name="Continue").last.focus()
    assert reader_state(page) != on_button, "same-name controls have different focus"
    field.focus()
    field.evaluate("node => node.setSelectionRange(2, 5, 'backward')")
    page.locator("main").evaluate("node => node.style.paddingLeft = '20px'")
    assert reader_state(page) != first, "layout history must be observable"

    # A labeled native editable can omit its words from accessibility's reading.
    # Its text and native Selection still matter, independently of focus.
    page.set_content(
        '<button>Continue</button><div contenteditable role="textbox" '
        'aria-label="Editable draft">kept words</div>'
    )
    editable = page.get_by_role("textbox", name="Editable draft")
    button = page.get_by_role("button", name="Continue")
    button.focus()
    page.evaluate("() => getSelection().removeAllRanges()")
    before = reader_state(page)
    editable.evaluate("node => node.textContent = 'lost words'")
    assert reader_state(page) != before, "editable source loss alone must be observable"
    editable.evaluate("node => node.textContent = 'kept words'")
    assert reader_state(page) == before
    editable.evaluate("node => node.innerHTML = '<span>kept words</span>'")
    assert reader_state(page) == before, "an editable wrapper has no user effect"

    select_words = (
        "(node, [anchor, focus]) => { const text = node.querySelector('span').firstChild; "
        "getSelection().setBaseAndExtent(text, anchor, text, focus); }"
    )
    editable.evaluate(select_words, [5, 2])
    before = reader_state(page)
    editable.evaluate(select_words, [0, 0])
    assert reader_state(page) != before, "editable selection loss must be observable"
    editable.evaluate(select_words, [5, 2])
    assert reader_state(page) == before
    editable.evaluate("node => node.innerHTML = '<span><span>kept words</span></span>'")
    editable.evaluate(
        "node => { const text = node.querySelector('span span').firstChild; "
        "getSelection().setBaseAndExtent(text, 5, text, 2); }"
    )
    assert reader_state(page) == before, (
        "selection coordinates must survive equivalent wrappers"
    )

    for text_offset, element_offset in ((0, 0), (10, 1)):
        editable.evaluate(
            "(node, offset) => getSelection().collapse(node.querySelector('span span').firstChild, offset)",
            text_offset,
        )
        text_endpoint = reader_state(page)
        editable.evaluate(
            "(node, offset) => getSelection().collapse(node, offset)", element_offset
        )
        assert reader_state(page) == text_endpoint, (
            "equivalent element and text endpoints must have the same caret reading"
        )
    editable.evaluate(
        "node => { const text = node.querySelector('span span').firstChild; "
        "getSelection().setBaseAndExtent(text, 5, text, 2); }"
    )

    button.focus()
    assert page.evaluate("() => getSelection().toString()") == "pt "
    before = reader_state(page)
    editable.evaluate(
        "node => { const text = node.querySelector('span span').firstChild; "
        "text.data = 'lost words'; getSelection().setBaseAndExtent(text, 5, text, 2); }"
    )
    button.focus()
    assert reader_state(page) != before, (
        "an unfocused editable source loss must be observable"
    )
    editable.evaluate(
        "node => { const text = node.querySelector('span span').firstChild; "
        "text.data = 'kept words'; getSelection().setBaseAndExtent(text, 5, text, 2); }"
    )
    button.focus()
    assert reader_state(page) == before
    page.evaluate("() => getSelection().collapseToStart()")
    button.focus()
    assert reader_state(page) != before, (
        "an unfocused editable caret loss must be observable"
    )

    page.set_content(
        '<div contenteditable role="textbox" aria-label="Multiline draft">'
        "first<br>second</div>"
    )
    editable = page.get_by_role("textbox", name="Multiline draft")
    editable.focus()
    editable.evaluate("node => getSelection().collapse(node, 1)")
    before = reader_state(page)
    editable.evaluate("node => getSelection().collapse(node, 2)")
    assert reader_state(page) != before, (
        "a caret crossing an explicit break must be observable"
    )
    after = reader_state(page)
    editable.evaluate(
        "node => { node.innerHTML = '<span>first</span><br><span>second</span>'; "
        "getSelection().collapse(node, 2); }"
    )
    assert reader_state(page) == after, (
        "linebreak offsets must permit equivalent wrappers"
    )
    editable.evaluate("node => getSelection().collapse(node, 1)")
    assert reader_state(page) == before

    editable.evaluate("node => node.innerHTML = 'first<br><br><br>second'")
    editable.evaluate("node => getSelection().collapse(node, 2)")
    before = reader_state(page)
    editable.evaluate("node => getSelection().collapse(node, 3)")
    assert reader_state(page) != before, (
        "a caret crossing an empty line must be observable"
    )

    page.set_content(
        '<div contenteditable role="textbox" aria-label="Multiline draft">'
        "<div>first</div><div>second</div></div>"
    )
    editable = page.get_by_role("textbox", name="Multiline draft")
    editable.focus()
    editable.evaluate("node => getSelection().collapse(node.firstChild.firstChild, 5)")
    before = reader_state(page)
    editable.evaluate("node => getSelection().collapse(node.lastChild.firstChild, 0)")
    assert reader_state(page) != before, (
        "a caret crossing a block line must be observable"
    )
    after = reader_state(page)
    editable.evaluate(
        "node => { node.firstChild.innerHTML = '<span>first</span>'; "
        "node.lastChild.innerHTML = '<span>second</span>'; "
        "getSelection().collapse(node.lastChild.firstChild.firstChild, 0); }"
    )
    assert reader_state(page) == after, "caret geometry must permit equivalent wrappers"
    editable.evaluate(
        "node => getSelection().collapse(node.firstChild.firstChild.firstChild, 5)"
    )
    assert reader_state(page) == before

    # A real closed-root editor exposes its source through its public field API,
    # even while focus is elsewhere and accessibility only reports the host.
    page.goto(
        serve(
            leaf_page(
                "Reader state",
                '<button>Continue</button><leaf-text aria-label="Draft" '
                'style="display:block;width:400px;height:70px"></leaf-text>',
            )
        )
    )
    wait_until_ready(page)
    draft = page.locator('leaf-text[aria-label="Draft"]')
    draft.evaluate(
        "field => { field.value = 'kept words'; field.setSelectionRange(2, 5, 'backward'); }"
    )
    page.get_by_role("button", name="Continue", exact=True).focus()

    # This arm probes the field reading. The served Leaf page may finish placing
    # unrelated chrome while these property-only changes are made, and the panel's own
    # field is read too, unchanged throughout, so it is set aside.
    def fields():
        return [line for line in reader_state(page) if line.startswith("field: ")]

    panel = [line for line in fields() if '"kept words"' not in line]

    def draft_reading():
        return [line for line in fields() if line not in panel]

    before = draft_reading()
    assert len(before) == 1
    draft.evaluate(
        "field => { field.value = 'lost words'; field.setSelectionRange(2, 5, 'backward'); }"
    )
    assert draft_reading() != before, "an unfocused draft loss must be observable"
    draft.evaluate(
        "field => { field.value = 'kept words'; field.setSelectionRange(2, 5, 'backward'); }"
    )
    assert draft_reading() == before
    draft.evaluate("field => field.setSelectionRange(0, 0)")
    assert draft_reading() != before, "an unfocused caret loss must be observable"
    draft.evaluate("field => field.setSelectionRange(2, 5, 'backward')")
    assert draft_reading() == before


# Each surface a page-level key opens, by the keys that open it from the page, and the
# control that shows the page has one to open: a page with no thread has no card, and a
# page with no other page live has no All pages. Escape unwinds any of them to the
# page (keyboard/AGENTS.md); the ones Go-to opens take the most presses. A new surface
# joins by its keys.
#


def has_open_thread(page):
    """Whether the page has a thread to open: its reading holds an open thread."""
    return bool(page.evaluate(OPEN_THREAD_COUNT))


def other_pages(page):
    """Whether the leaf's menu offers All pages, which it does only while other pages
    are live; the menu is put away again."""
    offered = panel_menu(page, "navigate").locator('.lf-fp-item[data-row="leaves"]')
    count = offered.count()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-floating-panel")).not_to_have_attribute("data-menu", "")
    return count > 0


# Where the focus stands in a thread, by the runtime's own selectors
# (thread/selectors.js): "reply" in that thread's reply field, "card" elsewhere in it,
# or null outside every thread or where the user sees none of the focused node. Seeing
# it takes both what the browser draws, which `checkVisibility` reads through every
# ancestor's display, visibility and opacity, and where it is drawn, which `seenRect`
# (geometry.js) holds to the viewport, every clip and the chrome, as
# anchor-resolution.js composes the two for a passage.
IN_THREAD = """async () => {
  const {THREAD, SAY_BOX} = await window.__lfCheckApi();
  const {focused} = await window.__lfWidgetApi();
  const {closestAcross} = await window.__lfCheckApi();
  const {seenRect} = await window.__lfCheckApi();
  const at = focused();
  const thread = at && closestAcross(at, THREAD);
  const drawn = at?.checkVisibility({opacityProperty: true, visibilityProperty: true});
  if (!thread || !drawn || !seenRect(at, new Map())) return null;
  return [...thread.querySelectorAll(SAY_BOX)].includes(at) ? 'reply' : 'card';
}"""
SURFACES = {
    "composer": (["c"], None),
    "target picker": (["s"], None),
    "page search": (["/"], None),
    "go-to": (["g"], None),
    "thread card": (["t"], has_open_thread),
    "threads view": (["g", "Shift+t"], None),
    "on me view": (["g", "Shift+m"], None),
    "all pages view": (["g", "Shift+l"], other_pages),
    "page map": (["g", "Shift+p"], None),
    "versions menu": (["g", "Shift+v"], None),
    "draw mode": (["w"], None),
    "design mode": (["l"], None),
    "command reference": (["?"], None),
}
# A surface whose keys change the page even where it fails to open, as `t` announces
# its walk, is open only where this reading finds it.
SHOWN = {"thread card": lambda page: page.evaluate(IN_THREAD) is not None}
UNWIND = 3
# Round trips after the first, which may build what the surface keeps for next time:
# three, so a count that climbs on each of them is a leak rather than a late build. With
# two, CI read the feature gallery's command reference at 53,317, 53,352 and 53,353
# nodes, a build finishing, as a leak.
AGAIN = 3


def surface_findings(page):
    """Opening a surface from the page and closing it again returns the page the first
    round trip left, and holds no more than it did. The first trip may build what the
    surface keeps for next time and leave what it changed on purpose, such as threads
    read or the last announcement; a later trip that leaves more is leaving something
    behind, and a count of nodes or listeners that climbs on every trip is a leak.
    Later trips preserve accessible content, control values, focus, caret, and layout.
    DOM nodes and listeners, including invisible markers and detached cached nodes,
    are measured separately for accumulation.

    Each surface the page offers must open, so a key that stopped opening one fails
    here rather than passing for having left nothing behind. The keys start from the
    page, where a page's own script may have left the focus inside a sample.

    Nothing happens between one trip's close and the next trip's keys, so the reading
    a trip closes on is the next trip's starting point; only a surface's first trip
    reads whether it opened."""
    # Whether the page offers each surface, read before the round trips start.
    offered = {
        surface: not door
        or (door(page) if callable(door) else page.locator(door).first.is_visible())
        for surface, (_, door) in SURFACES.items()
    }
    left_alone(page)

    def press(keys):
        for key in keys:
            page.keyboard.press(key)
            rendered(page)

    def unwind():
        for _ in range(UNWIND):
            page.keyboard.press("Escape")
            rendered(page)
        return reader_state(page)

    def settled_state(reading):
        # The live region retains the last spoken command. A panel can mark a
        # message read after Go-to announces its routes, so its next announcement
        # correctly has different words even though the closed page is unchanged.
        # The announcement is still part of the opening check above.
        stable = reading.copy()
        for line in page.locator(".lf-live").aria_snapshot(boxes=True).splitlines():
            if line in stable:
                stable.remove(line)
        return stable

    findings = []
    left = reader_state(page)
    for surface, (keys, _) in SURFACES.items():
        if not offered[surface]:
            continue
        press(keys)
        opened = reader_state(page) != left and SHOWN.get(surface, lambda _: True)(page)
        first = settled_state(left := unwind())
        if not opened:
            findings.append(f"{'+'.join(keys)} opened no {surface}")
            continue
        trips = [live_counts(page)]
        for _ in range(AGAIN):
            press(keys)
            left = unwind()
            trips.append(live_counts(page))
            if changes := state_changes(first, settled_state(left)):
                findings.append(
                    f"the {surface} closed again leaving\n" + "\n".join(changes[:12])
                )
                break
        for what in trips[0]:
            held = [trip[what] for trip in trips]
            if len(trips) == AGAIN + 1 and all(
                later > earlier for earlier, later in itertools.pairwise(held)
            ):
                findings.append(
                    f"the {surface} leaks {what}: {held} after each round trip"
                )
    return findings


# From the widest window the corpus is read at down to a phone's, crossing every
# breakpoint between them; a state that outlives its width is still there at the next
# step back.
RESIZE_PATH = (*range(1200, 439, -160), 440)


def resize_findings(page, path):
    """What a page says at a width depends on the width, not on the widths it passed
    through: a page taken through a resize and back says at each width on the way back
    what it said there on the way out, including accessible controls and their layout,
    after asking the document and every reading region to scroll to their start.
    Resize continuity can move each region's viewpoint independently; this journey
    resets those inputs after the resize has rendered and compares their actual
    positions too, since native scroll snapping can settle away from zero.
    Both ends are tried: a state written on the way down and one written on the
    way up are cleared by different widths, so each journey runs on a page opened at
    the end it starts from.

    Unlike a scroll, a resize lays the whole page out again and repaints it, so what it
    writes at each step costs nothing beside that; a write that restates what stood is
    failed wherever it happens (`write_watch.js`)."""
    assert page.viewport_size["width"] == path[0]

    def at_width(width):
        resized(page, width, 900)
        rendered(page)
        page.evaluate(
            """async () => {
            const {readingRegions} = await window.__lfCheckApi();
            const boxes = new Set([document.scrollingElement, ...readingRegions().map(region => region.body)]);
            for (const box of boxes) box.scrollTo({left: 0, top: 0, behavior: 'instant'});
        }"""
        )
        rendered(page)
        positions = page.evaluate(
            """async () => {
            const {readingRegions} = await window.__lfCheckApi();
            const position = box => [box.scrollLeft, box.scrollTop];
            return Object.fromEntries([
                ['$page', position(document.scrollingElement)],
                ...readingRegions().map(region => [region.id, position(region.body)]),
            ]);
        }"""
        )
        return [
            *reader_state(page),
            "scroll positions: " + json.dumps(positions, sort_keys=True),
        ]

    left_alone(page)
    # A sample can hold its child's growth while the reader sees the frame. Resizing
    # interrupts that reading and releases the held height; take the baseline after
    # that first release, so the return trip compares settled layouts at each width.
    resized(page, path[-1], 900)
    resized(page, path[0], 900)
    said = {width: at_width(width) for width in path}
    for width in path[-2::-1]:
        if changes := state_changes(said[width], at_width(width)):
            # Hand the page on at the width it opened at, as a whole journey does.
            resized(page, path[0], 900)
            return [
                f"opened at {path[0]}px, taken to {path[-1]}px and back to {width}px:\n"
                + "\n".join(changes[:12])
            ]
    return []


def untouched_resize_findings(page):
    """A page opened at its widest and scrolled by no one still shows its place, the
    words at its landing edge (reading-place.js), once the window narrows to a phone's:
    continuity keeps the page's own place, and a region the narrowing carries into the
    page, as a sidebar's track or a pane stacking under the one before, holds no place
    of the reader's to take the page to (version.js, `placeFor`). Read on a page of its
    own, since every other journey scrolls the page it reads."""
    assert page.viewport_size["width"] == RESIZE_PATH[0]
    rendered(page)
    landmark = page.evaluate_handle(
        "async () => { const api = await window.__lfCheckApi();"
        " return api.placeNode(api.capturePlace()); }"
    )
    if not landmark.evaluate("node => Boolean(node)"):
        return []
    resized(page, RESIZE_PATH[-1], 900)
    rendered(page)
    shown = landmark.evaluate(
        """node => {
        const range = document.createRange();
        range.selectNode(node);
        const {top, bottom} = range.getBoundingClientRect();
        return bottom > 0 && top < innerHeight;
    }"""
    )
    if shown:
        return []
    said = landmark.evaluate("node => node.textContent.trim().slice(0, 60)")
    scrolled = page.evaluate("() => document.scrollingElement.scrollTop")
    return [
        (
            f"opened at {RESIZE_PATH[0]}px and scrolled by no one, narrowed to "
            f"{RESIZE_PATH[-1]}px: the page scrolled to {scrolled}px, away from its "
            f"place ({said})"
        )
    ]


# The words in the field holding the focus, found through the shadow trees on the way
# to it, or null where the focus is on no field; and each field's words that the page
# draws, found the same way.
FOCUSED_WORDS = """() => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  if (!at?.matches('textarea, input, [contenteditable], leaf-text')) return null;
  return at.value ?? at.textContent;
}"""
SHOWN_WORDS = """() => {
  const found = [];
  const walk = (root) => {
    for (const node of root.querySelectorAll('*')) {
      if (node.matches('textarea, input, [contenteditable], leaf-text')
          && node.checkVisibility({ visibilityProperty: true }))
        found.push(node.value ?? node.textContent);
      if (node.shadowRoot) walk(node.shadowRoot);
    }
  };
  walk(document);
  return found;
}"""
# Every scroller the page holds sent to one end on both axes, remembering where each
# stood, or put back there.
SCROLL_ALL_TO = """(end) => {
  const scrolls = (el) => el === document.scrollingElement
    || /auto|scroll/.test(getComputedStyle(el).overflow);
  const scrollers = [document.scrollingElement, ...document.querySelectorAll('*')]
    .filter((el) => scrolls(el) && (el.scrollHeight > el.clientHeight + 1
      || el.scrollWidth > el.clientWidth + 1));
  window.__lfScrolledFrom = scrollers.map((el) => [el, el.scrollTop, el.scrollLeft]);
  for (const el of scrollers) {
    el.scrollTop = end === 'start' ? 0 : el.scrollHeight;
    el.scrollLeft = end === 'start' ? 0 : el.scrollWidth;
  }
}"""
SCROLL_ALL_BACK = """() => {
  for (const [el, top, left] of window.__lfScrolledFrom) {
    el.scrollTop = top;
    el.scrollLeft = left;
  }
}"""


def into_the_page(page):
    """Tab to a page control where `c` names its item rather than edits its text."""
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate("""async () => {
            const {focused} = await window.__lfWidgetApi();
            const {takesLetters} = await window.__lfCheckApi();
            const {closestAcross} = await window.__lfCheckApi();
            const at = focused();
            return Boolean(at && closestAcross(at, 'main') && !takesLetters(at));
        }"""):
            return True
    return False


# Every box the user types into from the keyboard, by how they reach it: a comment on
# the item they stand at, the page's own comment, and a thread card's reply where the
# page has a thread to open. Each route takes the user from the page to where the
# box's keys apply and returns them, or nothing where the page offers no such box. A
# new box joins by its route.
TYPED_BOXES = {
    "comment on an item": lambda page: into_the_page(page) and ["c"],
    "comment on the page": lambda page: ["c"],
    "thread card reply": lambda page: has_open_thread(page) and ["t", "c"],
}
# A box another box's keys could reach instead, as `c` outside a thread opens the page's
# comment, is reached only where this reading finds the focus in it.
IN_BOX = {"thread card reply": lambda page: page.evaluate(IN_THREAD) == "reply"}


def typed_box_findings(page):
    """A box the user is typing in is still there, holding their words and the focus,
    after every scroller on the page has been sent to either end and back: scrolling is
    reading, and what the user wrote waits for them. The browser fixture fails a box
    that went away on the way even where it came back (`words_watch.js`).

    The boxes share one page. A user abandons each one before the next, deleting its
    words with keys and closing it with Escape, so it leaves no draft behind: a page
    comment's draft would otherwise come back in the next box `c` opens."""
    findings = []
    for box, route in TYPED_BOXES.items():
        left_alone(page)
        keys = route(page)
        if not keys:
            continue
        for key in keys:
            page.keyboard.press(key)
            rendered(page)
        if page.evaluate(FOCUSED_WORDS) is None or not IN_BOX.get(box, lambda _: True)(
            page
        ):
            findings.append(f"{'+'.join(keys)} put the user in no {box} to type in")
            continue
        words = f"Words for the {box}"
        page.keyboard.type(words)
        for end in ("end", "start"):
            page.evaluate(SCROLL_ALL_TO, end)
            scroll_settled(page)
            rendered(page)
            page.evaluate(SCROLL_ALL_BACK)
            scroll_settled(page)
            rendered(page)
            if words not in page.evaluate(SHOWN_WORDS):
                findings.append(f"the {box} scrolled to the {end} and back is gone")
            elif page.evaluate(FOCUSED_WORDS) != words:
                findings.append(
                    f"the {box} scrolled to the {end} and back lost the focus"
                )
            if findings:
                # Where the words went is unknown, so no later box starts clean.
                return findings
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        assert page.evaluate(FOCUSED_WORDS) == "", f"the {box} kept its words"
        for _ in range(UNWIND):
            page.keyboard.press("Escape")
            rendered(page)
    return findings


# Each bundled widget's package, which answers for it in `KNOWN`, by tag.
WIDGET_PACKAGES = {
    tag: package.name for package in PACKAGES for tag in own_tags(package)
}


def unshown_key_findings(page, source):
    """Each command in a widget that declares context keys the page never shows
    (`shows-context-keys`, widget_quality.py), in the page and each Leaf document it
    frames. A worked example shows one state of its widget, and a command a widget
    declares only in another, such as a multiple-choice obligation's Done, goes unseen
    there; the corpus holds those states. Widgets and `KNOWN` are read as for
    `held_scroller_findings`."""
    local = source.with_suffix(".page")
    tags = sorted({*WIDGET_PACKAGES, *(own_tags(local) if local.is_dir() else ())})
    findings = []
    for frame in page.frames:
        if not frame.evaluate(
            "() => !!document.querySelector('script[data-lf-entry]')"
        ):
            continue
        where = "" if frame == page.main_frame else f" in {urlsplit(frame.url).path}"
        findings += [
            f"<{command['tag']} id={command['id']!r}> {command['command']} declares "
            f"context keys and no bindingBadge{where}"
            for command in render_checks_model.evaluate_probe(
                frame, "unshownContextKeys", tags
            )
            if (command["tag"], "shows-context-keys")
            not in KNOWN.get(WIDGET_PACKAGES.get(command["tag"]), set())
        ]
    return findings


def held_scroller_findings(page, source):
    """Each box in a widget that holds its own height and scrolls inside it
    (`grows-with-content`, widget_quality.py), in the page and each Leaf document it
    frames. `package check --render` reads a widget's worked example, which carries no
    data, so a box that holds its height only once rows arrive goes unseen there; the
    corpus gives the widgets their data. A widget is one a bundled package or the page's
    own package declares, and a finding `KNOWN` lists for the widget's package is that
    defect, wherever it stands. A box the page or a Layout bounds on purpose declares
    `--lf-holds-height: 1`, as a workspace's panes do. `heldScrollers` writes the page,
    so it reads a page nothing reads again."""
    local = source.with_suffix(".page")
    tags = sorted({*WIDGET_PACKAGES, *(own_tags(local) if local.is_dir() else ())})
    findings = []
    for frame in page.frames:
        if not frame.evaluate(
            "() => !!document.querySelector('script[data-lf-entry]')"
        ):
            continue
        where = "" if frame == page.main_frame else f" in {urlsplit(frame.url).path}"
        findings += [
            f"<{box['tag']} id={box['id']!r}> {box['at']} holds {box['height']}px and "
            f"scrolls inside it{where}"
            for box in render_checks_model.evaluate_probe(frame, "heldScrollers", tags)
            if (box["tag"], "grows-with-content")
            not in KNOWN.get(WIDGET_PACKAGES.get(box["tag"]), set())
        ]
    return findings


def test_working_prose_density_yields_to_component_spacing(browser, serve):
    """Density supplies prose defaults without defeating a component's own rhythm."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Working prose and component rhythm",
                """<style>@layer lf-base {
.component-line { margin: 0; }
.component-cell { padding: 3px; }
}</style>
<section class="density-working">
  <p>First paragraph.</p>
  <h2 id="prose-heading">Ordinary heading</h2>
  <p id="prose-paragraph">Ordinary paragraph.</p>
  <div style="display:grid;gap:8px">
    <h2 class="component-line">Component title</h2>
    <h3 class="component-line">Component subject</h3>
    <h4 class="component-line">Component detail</h4>
    <p class="component-line">Component status</p>
    <ul class="component-line"><li class="component-line">Component item</li></ul>
    <table><tr><th class="component-cell">Label</th>
      <td class="component-cell">Value</td></tr></table>
  </div>
  <p>Last paragraph.</p>
</section>""",
            )
        ),
    )
    reading = page.evaluate(
        """() => {
          const margin = node => {
            const s = getComputedStyle(node);
            return [parseFloat(s.marginBlockStart), parseFloat(s.marginBlockEnd)];
          };
          return {
            heading: margin(document.querySelector('#prose-heading')),
            paragraph: margin(document.querySelector('#prose-paragraph')),
            components: [...document.querySelectorAll('.component-line')].map(margin),
            cells: [...document.querySelectorAll('.component-cell')]
              .map(node => getComputedStyle(node).paddingBlock),
          };
        }"""
    )
    assert reading["heading"] == [18, 6], reading
    assert reading["paragraph"] == [6, 6], reading
    assert all(margin == [0, 0] for margin in reading["components"]), reading
    assert reading["cells"] == ["3px", "3px"], reading


def test_frame_edges_pass_through_whatever_stands_at_them(browser, serve):
    """A frame trims the margin at its edge through every first or last child: a bare
    section, a boxless one, and a padded grid section alike, with nothing declared on
    them. A padded box away from any frame's edge, and from the column's own items, keeps
    its heading's margin inside its inset, and the reading says to declare that box's
    frame."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Frame edges",
                """<div id="frame" style="padding:24px;--lf-block-frame:1">
  <section id="first">
    <h2 id="opening">Opening</h2>
    <p>First section.</p>
  </section>
  <section id="middle"><h2 id="middle-heading">Middle</h2></section>
  <section id="last">
    <p id="closing">Closing.</p>
  </section>
</div>
<div id="grid-frame" style="padding:24px;--lf-block-frame:1">
  <section style="display:grid;padding:12px">
    <h2 id="grid-heading">Grid item</h2>
  </section>
</div>
<div id="contents-frame" style="padding:24px;--lf-block-frame:1">
  <section style="display:contents">
    <h2 id="contents-heading">Boxless section</h2>
  </section>
</div>
<p>Between the frames.</p>
<div>
  <p>Prose before the padded box.</p>
  <div id="padded" style="padding:12px;border:1px solid">
    <h2 id="padded-heading">Padded, undeclared</h2>
  </div>
</div>
<p>After the padded box.</p>""",
            )
        ),
    )
    margins = page.evaluate(
        """() => Object.fromEntries(
          ['opening', 'middle-heading', 'closing', 'grid-heading', 'contents-heading',
           'padded-heading'].map(id => {
            const s = getComputedStyle(document.getElementById(id));
            return [id, [parseFloat(s.marginBlockStart), parseFloat(s.marginBlockEnd)]];
          }))"""
    )
    assert margins["opening"][0] == 0
    assert margins["middle-heading"][0] > 0
    assert margins["closing"][1] == 0
    assert margins["grid-heading"][0] == 0
    assert margins["contents-heading"][0] == 0
    assert margins["padded-heading"][0] > 0
    trapped = render_checks_model.evaluate_probe(page, "trappedMargins")
    assert not [
        f for f in trapped if f["id"] in {"frame", "grid-frame", "contents-frame"}
    ], trapped
    assert any(
        f["id"] == "padded" and f["child"] == "h2" and not f["frameDeclared"]
        for f in trapped
    ), trapped
    page.locator("#padded").evaluate(
        "el => el.style.setProperty('--lf-block-frame', '1')"
    )
    assert not [
        f
        for f in render_checks_model.evaluate_probe(page, "trappedMargins")
        if f["id"] == "padded"
    ]


def test_a_column_item_opening_with_a_heading_starts_at_the_heading(browser, serve):
    """A grid item keeps its first child's margin inside its box, so a section in the
    reading column would begin a heading's gap above its heading, and the focus ring,
    margin entry and landing Leaf places by that box would stand in the gap. The item
    takes the heading's gap instead: its box starts at the heading, which stands as far
    below the block above as the gap says. An eyebrow over the heading follows the same
    edge. A callout opening with a heading keeps its own margin, and an item opening with
    prose keeps its child's margin, so neither one's text moves."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Column items",
                """<p>Before.</p>
<section id="h2-led"><h2>Heading</h2><p>Body.</p></section>
<section id="h3-led"><h3>Subheading</h3><p>Body.</p></section>
<section id="eyebrow-led"><p class="eyebrow">Eyebrow</p><h2>Heading</h2></section>
<div class="callout" id="framed"><h2>Callout</h2><p>Body.</p></div>
<section id="prose-led"><p>Prose first.</p></section>""",
            )
        ),
    )
    items = page.evaluate(
        """() => Object.fromEntries(
          ['h2-led', 'h3-led', 'eyebrow-led', 'framed', 'prose-led'].map(id => {
            const item = document.getElementById(id);
            const box = item.getBoundingClientRect();
            const first = item.firstElementChild.getBoundingClientRect();
            const above = item.previousElementSibling.getBoundingClientRect();
            return [id, {
              band: first.top - box.top,
              gap: first.top - above.bottom,
              margin: parseFloat(getComputedStyle(item).marginBlockStart),
            }];
          }))"""
    )
    tokens = page.evaluate(
        """() => ['--h2-start', '--h3-start', '--callout-margin-block'].map(name =>
          parseFloat(getComputedStyle(document.querySelector('main'))
            .getPropertyValue(name)))"""
    )
    page.close()

    h2_start, h3_start, callout_margin = tokens
    for led in ("h2-led", "h3-led", "eyebrow-led"):
        assert items[led]["band"] == pytest.approx(0, abs=0.5), (led, items)
    assert items["h2-led"]["gap"] == pytest.approx(h2_start, abs=0.5), items
    assert items["h3-led"]["gap"] == pytest.approx(h3_start, abs=0.5), items
    assert items["eyebrow-led"]["gap"] == pytest.approx(h2_start, abs=0.5), items
    assert items["framed"]["margin"] == pytest.approx(callout_margin, abs=0.5), items
    assert items["prose-led"]["band"] > 0, items


def test_the_page_edge_is_no_frame(browser, serve):
    """A page with no Layout keeps the browser's margin on its body, and the live root
    scrolls, so the root holds that margin in. The root draws no frame, its edge
    being the window's. Shell padding is viewport spacing, including Leaf's panel
    clearance; a border makes the shell an actual frame whose edges can be read."""
    page = open_page(
        browser, serve(leaf_page("No Layout", "<p>Plain prose.</p>", layout=None))
    )
    margin = page.evaluate("() => getComputedStyle(document.body).marginTop")
    trapped = render_checks_model.evaluate_probe(page, "trappedMargins")
    page.evaluate("() => document.documentElement.style.padding = '12px'")
    padded = render_checks_model.evaluate_probe(page, "trappedMargins")
    page.evaluate("() => document.documentElement.style.border = '1px solid'")
    framed = render_checks_model.evaluate_probe(page, "trappedMargins")
    page.close()

    assert margin == "8px", "the body lost the browser's margin, so this tests nothing"
    assert trapped == [], trapped
    assert padded == [], padded
    assert [f["at"] for f in framed] == ["<html>", "<html>"], framed


def test_a_row_at_a_frame_edge_holds_the_trim_by_declaring_it(browser, serve, subtests):
    """A row holds its edge whether it declares the frame or receives its edge from
    outside. The advice names the actual split, and its documented declaration stops
    that trim. An unframed row's deliberate item margins remain the author's choice.
    The advice names each row by its id, so every case stands on one page."""
    cases = [
        (display, frame)
        for display in ("flex", "grid")
        for frame in ("1", "trim", "propagated")
    ]

    def rows(display, frame):
        name = f"{display}-{frame}"
        row = f"""<div id="row-{name}" style="display:{display};grid-template-columns:1fr 1fr;
      gap:12px;padding:24px;--lf-block-frame:{"0" if frame == "propagated" else frame}">
  <p id="left-{name}">Left.</p><p id="right-{name}">Right.</p>
</div>"""
        if frame == "propagated":
            row = f'<div style="--lf-block-frame:1">{row}</div>'
        return f"{row}<p>Following text keeps the rows apart.</p>"

    deliberate = "".join(
        f"""<div id="deliberate-{display}" style="display:{display};grid-template-columns:1fr 1fr">
  <p style="margin-block-start:0">One deliberately higher item.</p>
  <p style="margin-block-start:13px">One lower item.</p>
</div>"""
        for display in ("flex", "grid")
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Split rows",
                "<h1>Rows</h1>"
                + "".join(rows(display, frame) for display, frame in cases)
                + deliberate
                + "<p>Following text keeps the rows away from the page frame's edges.</p>",
            )
        ),
    )

    def tops(name):
        return page.evaluate(
            """name => ['left', 'right'].map(side => Math.round(
              document.getElementById(`${side}-${name}`).getBoundingClientRect().top))""",
            name,
        )

    def split(identity):
        return [
            f
            for f in render_checks_model.evaluate_probe(page, "splitEdges")
            if f["id"] == identity
        ]

    assert not split("deliberate-flex") and not split("deliberate-grid")
    for display, frame in cases:
        with subtests.test(display=display, frame=frame):
            name = f"{display}-{frame}"
            left, right = tops(name)
            assert left != right
            assert any(f["edge"] == "above" for f in split(f"row-{name}"))
            page.locator(f"#row-{name}").evaluate(
                "el => el.style.setProperty('--lf-holds-edge', '1')"
            )
            left, right = tops(name)
            assert left == right
            assert not split(f"row-{name}")


def test_every_idiom_in_the_catalog_stands_in_a_corpus_source(browser):
    """The sweep above is the corpus's own gate, and an idiom no source holds never
    reaches it: the shape passes every test it has, because it has none. It is the
    floor test_every_widget_in_the_vocabulary_stands_in_a_corpus_source is for widgets, and
    the reason it is here rather than beside that one is that an idiom is declared as a
    selector, which only a layout engine can answer.

    Asked of the authored markup and not of the upgraded page, so an idiom stands
    because an example writes it rather than because a widget's own rendering happens
    to match — a `<table>` a module builds demonstrates nothing about the shape an
    author is being pointed at. The corpus is left out for the same reason it is left
    out of the widget floor: generated from the others, it can only repeat them.

    Every key is put to the engine, so a key that is not a selector fails here too.
    `pre > code.language-*` was one for as long as nothing asked — readable, matching
    nothing, and the only member of the catalog with no way to be checked."""
    registry = validation_model.incoming_registry(
        [
            schema_model.ASSETS,
            schema_model.DEFAULT_PACKAGE,
            COMMAND_HUB_PACKAGE,
        ]
    )
    idioms = [
        key for key in registry if not key.startswith("$") and not is_element_name(key)
    ]
    assert idioms, "no idioms read — an empty catalog demonstrates itself"
    page = browser.new_page()
    held, invalid = set(), set()
    for example in CORPUS_SOURCES:
        page.set_content(example.read_text(), wait_until="domcontentloaded")
        answer = page.evaluate(
            """(selectors) => {
                const held = [], bad = [];
                for (const s of selectors) {
                    try { if (document.querySelector(s)) held.push(s); }
                    catch { bad.push(s); }
                }
                return {held, bad};
            }""",
            idioms,
        )
        held |= set(answer["held"])
        invalid |= set(answer["bad"])
    # The sources carry the page's own module entry, which resolves against nothing
    # on the blank document this asks its selector questions of. Consumed here rather
    # than avoided: what this page is for is the engine, not the load.
    consume_browser_errors(page, "Failed to resolve module specifier")
    page.close()

    assert not invalid, f"not selectors, so nothing can ask for them: {sorted(invalid)}"
    assert not set(idioms) - held, (
        f"no example holds {', '.join(sorted(set(idioms) - held))}"
        " — see examples/AGENTS.md"
    )


# Computed values, so a shorthand in one sheet and its longhands in the other read as
# one answer, and a var() and the length it resolves to are the same reading.
ORDER_SENSITIVE = (
    "display",
    "visibility",
    "position",
    "zIndex",
    "width",
    "height",
    "minWidth",
    "minHeight",
    "color",
    "backgroundColor",
    "borderTopColor",
    "borderTopWidth",
    "borderTopStyle",
    "borderTopLeftRadius",
    "boxShadow",
    "outlineColor",
    "outlineWidth",
    "fontFamily",
    "fontSize",
    "fontWeight",
    "lineHeight",
    "letterSpacing",
    "textAlign",
    "paddingTop",
    "paddingLeft",
    "opacity",
    "cursor",
    "resize",
)

COMPUTED_FACES = """([properties]) => {
    const faces = {};
    const counted = new Map();
    for (const element of document.querySelectorAll('body *')) {
        // getAttribute, because an SVG element's className is an SVGAnimatedString and
        // every one of them would key as the same element.
        const stem =
            element.tagName.toLowerCase() + '.' + (element.getAttribute('class') ?? '');
        const nth = (counted.get(stem) ?? 0) + 1;
        counted.set(stem, nth);
        const computed = getComputedStyle(element);
        faces[stem + '#' + nth] = properties.map((name) => computed[name]);
    }
    return faces;
}"""

RELOCATE_ADOPTED = """async () => {
    const rules = document.adoptedStyleSheets.flatMap((sheet) => [...sheet.cssRules]);
    // The page states its layer order in the first rule it loads (layer.py,
    // CASCADE_LAYERS). A copy standing first has to state it again, or the first layer
    // its own rules name becomes the lowest.
    const order = [...document.styleSheets].map((sheet) => sheet.cssRules[0])
        .find((rule) => rule instanceof CSSLayerStatementRule);
    const style = document.createElement('style');
    style.textContent = [order, ...rules].map((rule) => rule.cssText).join('\\n');
    // A copy: adoptedStyleSheets is a live array, so the assignment below would empty
    // the saved reference along with it.
    window.__lfAdopted = {sheets: [...document.adoptedStyleSheets], style};
    document.head.prepend(style);
    document.adoptedStyleSheets = [];
    await new Promise((settled) =>
        requestAnimationFrame(() => requestAnimationFrame(settled)));
    return {adopted: rules.length, linked: (style.sheet?.cssRules.length ?? 1) - 1};
}"""

RESTORE_ADOPTED = """async () => {
    const {sheets, style} = window.__lfAdopted;
    style.remove();
    document.adoptedStyleSheets = sheets;
    await new Promise((settled) =>
        requestAnimationFrame(() => requestAnimationFrame(settled)));
    return document.adoptedStyleSheets.length;
}"""


# The layer's own list of aims, read from the rule that floors them rather than copied
# here: a control joins the floor by joining that selector list, and the sweep below has
# to follow it there. The rule states both floors; a control that hangs a reach leaves
# the block floor to it, and one a flex or grid container could squeeze states it as
# padding.
AIM_FLOOR_RULE = (
    "min-width: var(--aim-floor); min-height: var(--lf-face-floor, var(--aim-floor));"
)


def aim_selectors():
    sheet = layer_model.stylesheet(
        schema_model.ASSETS / "shadow.css", schema_model.ASSETS
    )
    rules = [
        rule
        for rule in tinycss2.parse_stylesheet(
            sheet, skip_comments=True, skip_whitespace=True
        )
        if rule.type == "qualified-rule"
        and " ".join(tinycss2.serialize(rule.content).split()) == AIM_FLOOR_RULE
    ]
    assert len(rules) == 1, f"{len(rules)} rules in shadow.css state the aim floor"
    return " ".join(tinycss2.serialize(rules[0].prelude).split())


AIM_BOXES = browser_function("aims.js", "flooredAims")


# Everything an injected control still draws once the medium has taken the press away.
# `cursor` first, the hand being the plainest promise a page makes; the rest is the dress
# a control wears — a chip ground, a pill's corner, a border, a link's underline, a
# summary's marker. Colour is not read: a chip that is red is saying something, and what a
# control says is the other half of this bargain rather than this half. Every box
# inherits a list style, but only a list item, as a summary is, draws its marker.
PRINTED_OFFERS = """() => [...document.querySelectorAll('[data-lf-offer]')]
  .filter(n => n.checkVisibility() && n.getBoundingClientRect().width > 0)
  .map(n => {
    const s = getComputedStyle(n);
    return {
      what: (n.className || n.tagName).toString().trim().split(/\\s+/)[0],
      said: n.hasAttribute('data-lf-said'),
      pressable: [
        s.cursor === 'pointer' && 'a pointer hand',
        s.backgroundColor !== 'rgba(0, 0, 0, 0)' && 'a filled ground',
        parseFloat(s.borderTopLeftRadius) > 0 && 'a rounded corner',
        parseFloat(s.borderTopWidth) > 0 && 'a border',
        s.textDecorationLine.includes('underline') && 'an underline',
        s.display === 'list-item' && s.listStyleType !== 'none' && 'a marker',
      ].filter(Boolean),
    };
  })"""

# Each disclosure and whether the sheet shows its authored content. Injected controls
# may sit beside that content for keyboard order, but are intentionally absent on paper.
DISCLOSURES = """() => [...document.querySelectorAll('details')]
  .filter(d => !d.closest('.lf-chrome'))
  .map(d => ({
    open: d.open,
    displayed: d.checkVisibility(),
    summary: (d.querySelector('summary')?.textContent || '').trim().slice(0, 40),
    // What a disclosure holds is its content, a widget's generated words included,
    // and not the runtime's apparatus, which paper drops. An authored output
    // placeholder that is explicitly hidden has no paper reading.
    shown: [...d.children].filter(c =>
      !c.matches('summary, script, style, template, .lf-ui') && !c.hidden)
      .every(c => c.checkVisibility()),
  }))"""


def adopted_sheet_findings(page):
    """The runtime's sheets are adopted, so they cascade after base.css and after every
    package theme concatenated onto it. That position is an accident of how they are
    delivered, and a rule that wins by it beats the page's own rule at equal specificity
    — a default outranking the thing it is a default for. Nothing catches that, because
    no test and no browser gate can read a rule that never applied: .lf-ui's face stated
    there drew .lf-ref at 14px ink where its own rule asked for 11.5px muted, and
    .lf-margin-more's ink never reached the `…` it was written for.

    So the same rules are served from a stylesheet standing first in the head instead.
    Specificity does not change, so every computed value that moves was decided by sheet
    order alone. Zero of them is the contract: what the runtime lays over the page has
    to beat page and widget alike, and it must do that on its selectors rather than on
    where it is delivered. The chrome's guard (styles/chrome-guard.css) is the one rule
    built to win by delivery: it weighs one class and rolls back a page rule of that
    weight by standing after it.

    Layer order is the one other thing the move could reverse. A module sheet adopted
    first names `lf-base` before chrome.css names `lf-reset`, so the copy opens with the
    statement the page's first sheet makes (`@layer lf-reset, lf-base, lf-layouts`). An
    anonymous layer base.css opens meets nothing here: every rule in it asks for a body
    without `data-lf-presented` or `data-lf-upgraded`, and open_page has waited for both.

    A tie shows only where both rules meet one element, so this reads the corpus."""
    page.evaluate("() => document.getAnimations().forEach((one) => one.pause())")
    adopted = page.evaluate(COMPUTED_FACES, [list(ORDER_SENSITIVE)])
    rules = page.evaluate(RELOCATE_ADOPTED)
    assert rules["adopted"] and rules["adopted"] == rules["linked"], (
        f"{rules['adopted']} adopted rules became {rules['linked']} linked ones,"
        " so the comparison below is between a page and itself"
    )
    linked = page.evaluate(COMPUTED_FACES, [list(ORDER_SENSITIVE)])
    # Put the sheets back. The corpus is still going about its business — the
    # gallery builds a replay frame, a pulse reaches its next step — and those
    # values move whatever this test does to the cascade. A value the sheet's
    # position decided comes back when the position does; one the page moved by
    # itself stays where it went.
    assert page.evaluate(RESTORE_ADOPTED), "the sheets were not put back"
    restored = page.evaluate(COMPUTED_FACES, [list(ORDER_SENSITIVE)])

    assert len(adopted) > 1000, f"only {len(adopted)} elements read from the corpus"
    decided = []
    for key in adopted.keys() & linked.keys() & restored.keys():
        moved = [
            f"{ORDER_SENSITIVE[at]} {was} -> {now}"
            for at, (was, now, back) in enumerate(
                zip(adopted[key], linked[key], restored[key], strict=True)
            )
            if was != now and back == was
        ]
        if moved:
            decided.append(f"{key}: {', '.join(moved)}")
    if not decided:
        return []
    return [
        f"{len(decided)} of {len(adopted)} elements are drawn by the adopted sheet's"
        " position rather than by its selectors:\n" + "\n".join(sorted(decided)[:20])
    ]


def short_aim_findings(page):
    """One floor, and it has to reach the page as well as the chrome.

    The rule naming Leaf's aims used to stand inside chrome.css's `@scope`, so it floored
    the controls in the runtime's own chrome and nothing else: under a finger, 41 of this
    page's 73 buttons and all 21 of its margin entries stood below 44px while the six
    inside the chrome were correct. Stated in shadow.css it reaches the document, the
    chrome, and the declared widget trees alike.

    Reach is only half of it. The floor is one rule at each control's own weight, so any
    rule that states a minimum of its own for one of these outranks it — and a package's
    38px button or the chrome's 28px step is shorter than a finger. Those fold the floor
    in with max(), and this sweep is what says they did: it reads the layer's selector
    list, then measures every visible control, with any reach it hangs past its box,
    under an emulated finger."""
    return _short_aims(page, every_tab=False)


def short_aim_findings_in_every_tab(page):
    """The same floor, read as every tab opens it, wherever the page is sized.

    A page's own CSS can shrink a control under a narrow window's rules, and a tab's
    content stands in the layout only while that tab is open, so a reading of the first
    tab at desktop width never met the three examples whose controls fell below the
    floor at 390px. Each tab, and each tab inside it, is opened once, and what that
    shows, its panel and the chrome, is read; the rest of the page was read before the
    first tab opened."""
    return _short_aims(page, every_tab=True)


NEXT_TAB = """(opened) => {
  // The last unopened tab in document order, so the tabs a tab opens, which stand
  // after it, are all opened before the strip they hang from goes on to its next tab.
  const tab = [...document.querySelectorAll('[role="tab"]')].findLast(
    (tab) =>
      !tab.closest('.lf-chrome') &&
      !tab.closest('[hidden]') &&
      tab.checkVisibility() &&
      !opened.includes(tab.getAttribute('aria-controls')),
  );
  return tab?.getAttribute('aria-controls') ?? null;
}"""


# Press the tab that opens a panel, or a sibling of it in its strip (`away`). Pressed by
# script: a strip that runs past a phone's width leaves tabs outside the window, and
# what is under test is the content the tab opens, not the strip's reach.
OPEN_TAB = """([id, away]) => {
  const tab = [...document.querySelectorAll('[role="tab"]')].find(
    (tab) => tab.getAttribute('aria-controls') === id,
  );
  const siblings = [...tab.parentElement.closest('.lf-tabstrip').querySelectorAll('[role="tab"]')];
  (away ? siblings.find((other) => other !== tab) : tab).click();
}"""


def _short_aims(page, *, every_tab):
    short, seen = {}, 0
    selectors = aim_selectors()

    def read(roots, where):
        nonlocal seen
        measured = roots.evaluate_all(AIM_BOXES, selectors)
        assert measured["floor"] == 44, f"a finger asked for {measured['floor']}px"
        seen += measured["seen"]
        for found in measured["short"]:
            short.setdefault(found, []).append(where)

    with under_a_finger(page):
        read(page.locator(":root"), "first")
        opened = []
        while every_tab and (tab := page.evaluate(NEXT_TAB, opened)):
            opened.append(tab)

            def opening(tab=tab, away=False):
                page.evaluate(OPEN_TAB, [tab, away])
                rendered(page)

            def reopening(tab=tab):
                # Away to a sibling and back, which opens the tab afresh; what the
                # sibling's own opening raised is set aside with it.
                opening(tab, away=True)
                page.lf_resize_notices.clear()
                opening(tab)

            # Opening a tab hands the browser a block of new layout, and under load it
            # may say once that a ResizeObserver delivery was deferred.
            confirming_resize_notices(page, opening, reopening)
            # What the opening shows: the panel, and the chrome the runtime draws for
            # it, such as the margin's entries for what the panel holds.
            read(page.locator(f'[id="{tab}"], body > .lf-chrome'), tab)
    assert seen > 30, f"only {seen} aims stood on the corpus"
    if not short:
        return []
    return [
        f"{len(short)} aims are smaller than 44px under a finger, of {seen} read:\n"
        + "\n".join(
            f"{found} (open on {', '.join(dict.fromkeys(tabs[:3]))})"
            for found, tabs in sorted(short.items())
        )
    ]


@contextmanager
def under_a_finger(page):
    """Show the page to a coarse pointer, as the aim floor's own rules read it."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
    try:
        assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
            "the touch emulation never reached Leaf's coarse-pointer rules"
        )
        yield
    finally:
        cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": False})
        cdp.detach()


def pressable_paper_findings(page):
    """Nothing on a sheet is interactive, so nothing on it should look as though it is.

    Injected controls go on paper, which the layer has always done — but the ones whose
    label is the page speaking stay, because their words are the page's only statement of
    what they say, and twenty of the corpus's 236 came through still dressed as controls:
    the command hub's counts as filled pills with a pointer hand, its worktree heads with
    a disclosure marker, a decision's links underlined. The words are what data-lf-said
    keeps; the shape was never part of that bargain.

    A shut disclosure is the same fault from the other side — the words are in the
    document, nothing on the sheet says so, and there is no press to open it with. The
    layer already prints a settled group's cards and an inactive tab's panel open;
    <details> was the one way of putting content behind a gesture that was missed. Six of
    them printed as stubs, one holding 3270px of an exact source.

    Both readings are taken on screen first, and that half is what makes the print half
    mean anything: a corpus whose controls were bare and whose disclosures were open
    everywhere would pass the assertions below while proving nothing about the medium.
    """
    page.locator('[role="tab"][aria-controls="corpus-command-hub"]').click()
    expect(page.locator("#corpus-command-hub")).to_be_visible()
    on_screen = page.evaluate(PRINTED_OFFERS)
    assert sum(1 for offer in on_screen if offer["pressable"]) > 20, (
        f"the page draws almost nothing as pressable on screen, so paper taking it away "
        f"is not something this can see: {on_screen}"
    )
    shut = [d for d in page.evaluate(DISCLOSURES) if not d["open"]]
    assert len(shut) >= 3, f"the corpus has no shut disclosures to print: {shut}"
    assert not any(d["displayed"] and d["shown"] for d in shut), (
        f"the page shows what its shut disclosures hold before the medium changes: {shut}"
    )

    page.emulate_media(media="print")
    printed = page.evaluate(PRINTED_OFFERS)
    # A disclosure omitted from paper altogether, such as a draft's edit history,
    # is not a visible summary concealing content from a reader of the sheet.
    on_paper = [
        d for d in page.evaluate(DISCLOSURES) if d["displayed"] and not d["open"]
    ]
    page.emulate_media(media="screen")
    assert len(printed) >= 10, (
        f"paper kept {len(printed)} injected controls, which is too few for the "
        f"assertion below to be about the ones that speak"
    )
    assert on_paper, "no shut disclosure printed, so none was read on paper"
    dressed = [
        f"{offer['what']} still draws {', '.join(offer['pressable'])}"
        for offer in printed
        if offer["pressable"]
    ]
    findings = []
    if dressed:
        findings.append(
            f"{len(dressed)} of the {len(printed)} controls paper kept still promise "
            "a press nothing on a sheet can answer:\n  " + "\n  ".join(dressed)
        )
    if stubs := [d for d in on_paper if not d["shown"]]:
        findings.append(
            "a shut disclosure printed as a summary and a stub, with no press on the "
            f"sheet to open it: {stubs}"
        )
    return findings


# From a box's last line of text to the inside of its lower border, and whether the box
# scrolls sideways at all, since one that fits has no bar to clear.
TEXT_CLEAR_OF_BAR = """(box) => {
    const walk = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
    let last = -Infinity;
    for (let node; (node = walk.nextNode());) {
        if (!node.data.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const r of range.getClientRects()) last = Math.max(last, r.bottom);
    }
    const s = getComputedStyle(box);
    return { scrolls: box.scrollWidth > box.clientWidth,
             clear: Math.round(box.getBoundingClientRect().bottom
                               - parseFloat(s.borderBottomWidth) - last) };
}"""


def test_a_box_of_text_that_scrolls_leaves_its_last_line_clear_of_the_bar(
    browser, serve
):
    """macOS draws an overlay scrollbar over a scroller's own block end and widens it to
    a 15px track under the pointer, so a thread's code block, 8px of padding under its
    last line, lost half that line to the bar the moment the user reached for it. A code
    block or table that scrolls sideways keeps 15px clear under its last line, and the
    room costs it none of its width: a block child dropped the code block's inline-end
    padding from what it scrolls, enough to stop a block that overflowed by less than
    that and loop. One that fits keeps the same clearance, so becoming scrollable
    never moves the following content a frame after layout."""
    url = serve(WIDE_TABLE_PAGE)
    wide = "word " * 60
    root = panel_comment(
        serve.page_dir,
        f"A wide block:\n\n```\n{wide}\n{wide}\n```\n\nAnd one that fits:\n\n"
        "```\nshort\n```",
        {"section": "p"},
        author="agent",
    )
    page = open_page(browser, url)
    open_panel_thread(page, root)
    measured = page.evaluate(
        """() => {
        const read = """
        + TEXT_CLEAR_OF_BAR
        + """;
        const [wide, fits] = document.querySelectorAll(
          '.lf-fp-view[data-view="thread"] .lf-msg-body pre');
        const reading = { table: read(document.querySelector('#sessions')),
                          wide: read(wide), fits: read(fits),
                          fitsPad: parseFloat(getComputedStyle(fits).paddingBottom),
                          width: wide.scrollWidth };
        const bare = document.createElement('style');
        bare.textContent = 'pre::after { display: none !important }';
        document.head.append(bare);
        reading.bareWidth = wide.scrollWidth;
        bare.remove();
        return reading;
    }"""
    )
    for name in ("table", "wide"):
        assert measured[name]["scrolls"], f"the {name} fits, so it proves nothing"
        assert measured[name]["clear"] >= 15, measured
    assert not measured["fits"]["scrolls"], measured
    assert measured["width"] == measured["bareWidth"], measured
    assert (
        measured["fitsPad"] + 8 <= measured["fits"]["clear"] <= measured["fitsPad"] + 11
    ), measured


def test_horizontal_scrollbar_clearance_does_not_change_after_layout(
    browser, serve, subtests
):
    """The track's clearance is already present when a box gains horizontal overflow.

    A scroll-state query added it on the next frame, shifting the following control
    after both the first layout and the layout caused by a resize.
    """
    words = "0123456789" * 6
    boxes = {
        "code": f"<pre>{words}</pre>",
        "table": f"<table><tr><td>{words}</td></tr></table>",
        "widget": f'<div style="overflow:auto hidden;white-space:pre">{words}</div>',
    }
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Stable scrollbar clearance",
                "".join(
                    f'<section id="{name}" style="width:1000px">{box}'
                    "<button>Following control</button></section>"
                    for name, box in boxes.items()
                ),
            )
        ),
    )
    page.locator("#widget > div").evaluate(
        "element => element.classList.add('lf-text-scroller')"
    )
    for name in boxes:
        with subtests.test(box=name):
            readings = page.locator(f"#{name}").evaluate("""async section => {
              const box=section.firstElementChild, following=section.lastElementChild;
              const read=()=>({height:box.getBoundingClientRect().height,
                following:following.getBoundingClientRect().top,
                scrolls:box.scrollWidth>box.clientWidth});
              const readings=[read()];
              section.style.width='200px';
              readings.push(read());
              for(let i=0;i<3;i++) {
                await new Promise(requestAnimationFrame);
                readings.push(read());
              }
              return readings;
            }""")
            assert not readings[0]["scrolls"], readings
            assert all(reading["scrolls"] for reading in readings[1:]), readings
            assert all(
                reading["height"] == readings[0]["height"]
                and reading["following"] == readings[0]["following"]
                for reading in readings
            ), readings


@pytest.mark.parametrize(
    ("browser_fixture", "track"),
    [("browser", 0), ("scrollbar_browser", 15), ("scrollbar_browser", 20)],
)
def test_a_diagrams_reserved_box_includes_its_scrollbar_clearance(
    request, serve, browser_fixture, track
):
    """The diagram fits standard tracks; a wider native track grows without clipping.

    An ample authored reservation is stable through startup on either platform's
    font metrics. Removing it exposes the natural drawing and native track sizes;
    the overlay and classic track share the drawing's own blank bottom padding.
    """
    source = (ROOT / "examples" / "security-boundary.html").read_text()
    # The example draws its five-step chain top-down so it fits a phone; drawn
    # left-to-right it runs past a 678px viewport and scrolls, which this test needs.
    source = source.replace("flowchart TD", "flowchart LR", 1).replace(
        'id="security-before-flow" data-height="449"',
        'id="security-before-flow" data-height="200"',
    )
    assert "flowchart LR" in source and 'data-height="200"' in source
    if track:
        source = source.replace(
            "</head>",
            f"<style>lf-diagram::-webkit-scrollbar {{ height:{track}px }}</style></head>",
        )
    page = request.getfixturevalue(browser_fixture).new_page(
        viewport={"width": 678, "height": 900}
    )
    page.add_init_script("""window.diagramFrames = [];
      function read() {
        const box = document.querySelector('#security-before-flow');
        const following = document.querySelector('#security-counterexample');
        if(box && following) {
          const svg=box.querySelector('svg');
          const ink=svg?.getBBox({stroke:true});
          const bottom=ink && new DOMPoint(ink.x,ink.y+ink.height).matrixTransform(svg.getScreenCTM()).y;
          window.diagramFrames.push({drawn:!!svg,visible:box.checkVisibility({visibilityProperty:true}),
            height:box.getBoundingClientRect().height,
            following:following.getBoundingClientRect().top,
            track:box.offsetHeight-box.clientHeight,
            clear:svg ? box.getBoundingClientRect().bottom-bottom : null});
        }
        if(!window.diagramFramesDone) requestAnimationFrame(read);
      }
      requestAnimationFrame(read);
    """)
    render_checks_model.install_driver(page)
    page.goto(serve(source))
    wait_until_ready(page)
    frames = page.evaluate("""async () => {
      for(let i=0;i<3;i++) await new Promise(requestAnimationFrame);
      window.diagramFramesDone=true;
      return window.diagramFrames;
    }""")
    frames = [frame for frame in frames if frame["visible"]]
    assert frames, frames
    assert frames[-1]["drawn"], frames
    assert frames[-1]["track"] == track, frames
    assert frames[-1]["clear"] >= max(15, track + 1), frames
    assert {frame["height"] for frame in frames} == {200}, frames
    assert len({frame["following"] for frame in frames}) == 1, frames
    # A missing or underestimated reservation must not sacrifice content to the bar;
    # extra reserved room must not stretch the drawing into it.
    reservations = page.locator("#security-before-flow").evaluate("""box => {
      const svg=box.querySelector('svg');
      const natural=svg.getBoundingClientRect().height;
      return ['', String(natural - 16), String(natural + 100)].map(height=>{
        box.setAttribute('data-lf-height',height);
        const bounds=box.getBoundingClientRect(), ink=svg.getBBox({stroke:true});
        const bottom=new DOMPoint(ink.x,ink.y+ink.height).matrixTransform(svg.getScreenCTM()).y;
        return {height:bounds.height,svg:svg.getBoundingClientRect().height,
          clear:bounds.bottom-bottom};
      });
    }""")
    natural = reservations[0]["svg"]
    height = natural + max(0, track - 15)
    assert 0 < height < 200, reservations
    assert [reading["height"] for reading in reservations] == [
        height,
        height,
        natural + 100,
    ]
    assert {reading["svg"] for reading in reservations} == {natural}
    assert all(reading["clear"] >= max(15, track + 1) for reading in reservations), (
        reservations
    )
    page.emulate_media(media="print")
    printed = page.locator("#security-before-flow").evaluate("""box => ({
      height:box.getBoundingClientRect().height,
      svg:box.querySelector('svg').getBoundingClientRect().height
    })""")
    assert printed["height"] == printed["svg"], printed


def test_a_widget_box_of_text_that_scrolls_leaves_its_last_line_clear_of_the_bar(
    browser, serve
):
    """A box a widget makes scroll text sideways, a diff's file or a call group, sat its
    last line 4px and 2px above its edge, under the 15px track the pointer widens. Each
    keeps that line 15px clear once it scrolls."""
    url = serve(
        leaf_page(
            "Wide calls",
            '<h1 id="t">Call change</h1>'
            '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
            '<lf-diff id="patch" source="patch-data"></lf-diff>',
        ),
        packages=("diff",),
    )
    wide = "_".join(["argument"] * 40)
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        call_diff(
            call_node(
                "changed()",
                "app.py",
                1,
                children=[call_node(f"{wide}()", "app.py", 2, status="added")],
            )
        ),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        f"@@ -1 +1,2 @@\n changed()\n+{wide}()\n",
    )
    page = open_page(browser, url)
    expect(page.locator("#calls .lf-call-group")).to_have_attribute("open", "")
    page.wait_for_function("() => document.querySelector('lf-diff.lf-rendered')")
    measured = page.evaluate(
        """() => {
        const read = """
        + TEXT_CLEAR_OF_BAR
        + """;
        const diff = document.querySelector('#patch').shadowRoot;
        return { calls: read(document.querySelector('#calls .lf-call-group-body')),
                 file: read(diff.querySelector('code[data-code]')) };
    }"""
    )
    for name, reading in measured.items():
        assert reading["scrolls"], f"the {name} fits, so it proves nothing"
        assert reading["clear"] >= 15, measured


def test_scrollbar_clearance_reads_main_when_it_is_the_scroller(browser, serve):
    """The page's main region can itself own the horizontal track."""
    source = leaf_page(
        "Scrolling main",
        '<button style="flex: 0 0 600px; height: 40px; margin: 0">Wide choice</button>',
        layout=None,
    ).replace(
        "<main>",
        '<main style="display: flex; box-sizing: content-box; width: 240px; '
        'max-width: none; overflow: auto; padding: 0; border: 0">',
    )
    page = open_page(browser, serve(source))
    assert page.locator("main").evaluate("box => box.scrollWidth > box.clientWidth")
    findings = render_checks_model.evaluate_probe(page, "scrollbarClearance")
    assert len(findings) == 1, findings
    assert findings[0]["at"].startswith("<main"), findings
    assert findings[0]["clear"] == 0, findings
    page.add_style_tag(content="main { padding-bottom: 15px !important; }")
    assert render_checks_model.evaluate_probe(page, "scrollbarClearance") == []


def test_scrollbar_clearance_accepts_room_allocated_to_a_classic_track(
    scrollbar_browser, serve
):
    """A classic scrollbar has its own track below the content, so needs no spacer."""
    source = leaf_page(
        "Classic scrollbar room",
        '<h1 id="t">Allocated track</h1>'
        f'<div id="classic">{"sideways words " * 30}</div>',
        head="""<style>
          #classic { width: 240px; overflow: auto; white-space: nowrap;
                     padding: 0; border: 0; }
          #classic::-webkit-scrollbar { height: 20px; }
        </style>""",
    )
    page = open_page(scrollbar_browser, serve(source))
    allocated = page.locator("#classic").evaluate(
        """box => ({scrolls: box.scrollWidth > box.clientWidth,
                     track: box.offsetHeight - box.clientHeight})"""
    )
    assert allocated["scrolls"] and allocated["track"] == 20, allocated
    assert render_checks_model.evaluate_probe(page, "scrollbarClearance") == []


def test_scrollbar_clearance_reads_svg_ink_inside_its_scaled_viewport(browser, serve):
    """SVG has no offsetHeight; its viewport clips ink without erasing it from the
    reading. Empty space inside that viewport can clear the track just like padding."""
    source = leaf_page(
        "Drawing clearance",
        '<h1 id="t">Drawing clearance</h1>'
        '<div id="drawing"><svg width="600" height="100" viewBox="0 0 300 50">'
        '<defs><rect width="300" height="50"/></defs>'
        '<rect id="ink" width="300" height="50"/></svg></div>',
        head="""<style>
          #drawing { width:240px; overflow:auto; transform:scale(.75);
                     transform-origin:top left; }
          #drawing svg { display:block; max-width:none; }
        </style>""",
    )
    page = open_page(browser, serve(source))
    assert page.locator("#drawing").evaluate(
        "box => box.scrollWidth > box.clientWidth && box.offsetHeight === box.clientHeight"
    ), "the positive control needs horizontal overflow without a classic track"
    findings = render_checks_model.evaluate_probe(page, "scrollbarClearance")
    assert len(findings) == 1, findings
    assert findings[0]["at"] == "<div id=drawing>", findings
    assert findings[0]["clear"] == 0, findings
    # The SVG viewport still reaches the bottom; only its drawing gains 20 CSS px
    # of room through the viewBox's 2x scale (15 screen pixels after the CSS scale).
    page.locator("#ink").evaluate("rect => rect.setAttribute('height', '40')")
    assert render_checks_model.evaluate_probe(page, "scrollbarClearance") == []
    # A nested clip can hide the same lower ink without adding space to the SVG.
    page.locator("#drawing").evaluate("""box => {
      const svg = box.querySelector('svg');
      svg.querySelector('#ink').setAttribute('height', '50');
      const clip = document.createElement('div');
      clip.style.cssText = 'width:600px; height:80px; overflow:hidden';
      box.style.height = '100px';
      box.append(clip);
      clip.append(svg);
    }""")
    assert render_checks_model.evaluate_probe(page, "scrollbarClearance") == []


FRAMED_TABLES_PAGE = leaf_page(
    "Framed tables",
    """
<h1 id="t">Checks</h1>
<table id="bare"><tr><th scope="row">Error rate</th><td><code>0.11%</code></td></tr></table>
<table id="allocated" data-width="wide"><tr><th>Session</th><td>9:00</td></tr></table>
<figure data-width="available">
<table id="figure-table"><tr><th>Session</th><td>9:00</td></tr></table>
<lf-ask id="figure-asked">
<h2>Which session ends?</h2>
<table id="figure-asked-table"><tr><th>Session</th><td>17:00</td></tr></table>
<lf-options id="figure-asked-choice" choose>
<lf-option id="figure-asked-early"><strong>Early</strong> End it at 16:00.</lf-option>
<lf-option id="figure-asked-late"><strong>Late</strong> End it at 18:00.</lf-option>
</lf-options>
</lf-ask>
</figure>
<lf-ask id="asked">
<h2>Which session moves?</h2>
<table id="asked-table"><tr><th>Session</th><td>9:00</td></tr></table>
<lf-options id="asked-choice" choose>
<lf-option id="asked-early"><strong>Early</strong> Move it to 8:00.</lf-option>
<lf-option id="asked-late"><strong>Late</strong> Move it to 10:00.</lf-option>
</lf-options>
</lf-ask>
<section class="panel" id="checks">
<h2>Checks</h2>
<table id="framed"><thead><tr><th>Check</th><th>Observed</th></tr></thead>
<tbody><tr><th scope="row">Error rate</th><td><code>0.11%</code> / below <code>0.50%</code></td></tr></tbody></table>
</section>
<section class="panel" id="wide-checks">
<h2>Sessions</h2>
<table id="wide-framed"><tr>{cells}</tr></table>
</section>
""".format(cells="".join(f"<td>value_number_{i}</td>" for i in range(10))),
)


def test_a_scrolling_table_keeps_its_caption_and_status_words_whole(browser, serve):
    """A table that scrolls its columns keeps its caption on the part of it on screen,
    where the caption used to run on past the scrollport; and a status tag in a narrow
    column holds its word, where `overflow-wrap: anywhere` let the table's automatic
    layout squeeze "passed" to "pas" over "sed"."""
    caption = "What the final revision demonstrates and what remains to be measured"
    source = WIDE_TABLE_PAGE.replace(
        '<table id="sessions">', f'<table id="sessions"><caption>{caption}</caption>'
    ).replace(
        "</table>",
        "</table><table id='statuses'><tr><td><span class='tag ok'>passed</span></td>"
        "<td>"
        + "The replay covers every legacy export and the importer's output. " * 3
        + "</td></tr></table>",
    )
    page = open_page(browser, serve(source))
    resized(page, 360, 740)
    table = page.locator("#sessions")
    read = """t => {
      const box = t.getBoundingClientRect(), cap = t.caption.getBoundingClientRect();
      const tag = document.querySelector('#statuses .tag');
      return {scrolls: t.scrollWidth - t.clientWidth,
              inside: cap.left >= box.left - 1 && cap.right <= box.right + 1,
              tagLines: Math.round(tag.getBoundingClientRect().height
                / parseFloat(getComputedStyle(tag).lineHeight))};
    }"""
    measured = table.evaluate(read)
    assert measured["scrolls"] > 0, "this table fits, so it proves nothing"
    assert measured["inside"] and measured["tagLines"] == 1, measured
    table.evaluate("t => { t.scrollLeft = t.scrollWidth; }")
    page.wait_for_function(
        """() => { const t = document.querySelector('#sessions');
                   const box = t.getBoundingClientRect(), cap = t.caption.getBoundingClientRect();
                   return t.scrollLeft > 0 && cap.left >= box.left - 1
                     && cap.right <= box.right + 1; }"""
    )


def test_the_squeeze_reading_follows_words_into_an_open_shadow_root(
    browser, serve, tmp_path, monkeypatch
):
    """A widget's visible words still decide whether the table genuinely overflows.
    The host's light tree is empty after upgrade, so a reading that stops at the shadow
    boundary mistakes this for Chromium's empty inline-box rounding artifact."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entries["lf-callout"].pop("x-verbatim")
    entries["lf-callout"]["x-shadow"] = True
    registry_path.write_text(json.dumps(entries, indent=2))
    module = tmp_path / ".leaf" / "widgets" / "lf-callout.js"
    module.write_text(
        'import { once, shadowStage } from "/runtime/widget-api.js";\n'
        'customElements.define("lf-callout", class extends HTMLElement {\n'
        "  connectedCallback() {\n"
        "    if (!once(this)) return;\n"
        "    const text = this.textContent;\n"
        '    this.textContent = "";\n'
        '    const span = document.createElement("span");\n'
        "    span.textContent = text;\n"
        "    shadowStage(this, [span]);\n"
        "  }\n"
        "});\n"
    )
    serial = itertools.count(1)
    source = re.sub(
        r"<code>(test_[^<]+)</code>",
        lambda match: (
            f'<lf-callout id="shadow-name-{next(serial)}">{match.group(1)}</lf-callout>'
        ),
        IDENTIFIERS_IN_CODE_PAGE,
    )
    page = open_page(browser, serve(source, packages=(*EXAMPLE_PACKAGES, "./.leaf")))
    resized(page, 540, 720)
    host = page.locator("lf-callout").first
    host.evaluate(
        """(el) => {
        const text = el.shadowRoot.lastChild.textContent;
        el.shadowRoot.lastChild.replaceWith(document.createTextNode(text));
    }"""
    )
    assert host.evaluate("(el) => el.textContent") == ""
    assert host.evaluate("(el) => el.shadowRoot.lastChild.nodeType") == 3
    table = page.locator("#held")
    assert table.evaluate("(el) => el.scrollWidth - el.clientWidth") > 1

    squeezed = render_checks_model.evaluate_probe(page, "squeezedTables")

    assert any(
        f["code"] == "squeezed-table" and f["at"] == "<table id=held>" for f in squeezed
    ), squeezed


def test_a_quiet_word_inside_a_scrolling_table_leaves_the_page_its_own_width(
    browser, serve
):
    """A widget hangs a word clipped to nothing among the page's own words (.lf-quiet),
    out of flow so it holds no room. Out of flow with no positioned ancestor is
    positioned against the page, though, and a table scrolling inside itself holds
    its far column three hundred pixels past the window: the cell is there, the
    word is laid out there with it, and the page would grow a sideways scrollbar
    carrying the user to a box nobody can see. The scroller answers for it — a
    box that scrolls contains what it scrolls — so the word keeps the place on its
    own cell that every reading of it expects and the table carries it.

    Asked at both of the table's scroll positions, since the word travels with the
    cell rather than standing still while the cell moves; and the cell has to be off
    the table's own edge at the first of them, or nothing here could have escaped."""
    page = open_page(browser, serve(WIDE_TABLE_PAGE))
    note = plant_quiet_word(page, "#sessions td", "value_number_7")

    # At rest, then with the table scrolled to its far end; the page's own width is
    # the gate's reading, taken at each.
    read = """(n, scrolled) => {
        const table = document.querySelector('#sessions');
        if (scrolled) table.scrollLeft = table.scrollWidth;
        const word = n.getBoundingClientRect();
        const cell = n.closest('td').getBoundingClientRect();
        const shown = table.getBoundingClientRect();
        return {
            holder: n.closest('td').firstChild.data,
            scrolls: Math.round(table.scrollWidth - table.clientWidth),
            onItsCell: word.left >= Math.floor(cell.left)
                       && word.right <= Math.ceil(cell.right),
            // Within a pixel: the table scrolls to a whole-pixel scrollWidth, so a
            // cell ending on a fraction stands that fraction past the box at the end.
            cellShown: cell.left >= shown.left - 1 && cell.right <= shown.right + 1,
        };
    }"""
    measured = {
        position: {
            **note.evaluate(read, position == "scrolled"),
            "sideways": root_overflow(page),
        }
        for position in ("rest", "scrolled")
    }
    assert measured["rest"]["holder"] == "value_number_7", (
        "the word is on the marked cell"
    )
    assert measured["rest"]["scrolls"] > 0, "this table fits, so it proves nothing"
    assert not measured["rest"]["cellShown"], (
        "the cell is on screen already, so nothing here could have escaped"
    )
    assert measured["scrolled"]["cellShown"], (
        f"the table did not scroll to the cell: {measured}"
    )
    assert measured["rest"]["onItsCell"] and measured["scrolled"]["onItsCell"], (
        f"the word left the cell it belongs to: {measured}"
    )
    assert (
        measured["rest"]["sideways"] == 0 and measured["scrolled"]["sideways"] == 0
    ), f"the page grew sideways reaching for the word: {measured}"


@pytest.mark.parametrize("shape", HIDDEN_SCROLLERS)
def test_a_hidden_scroller_is_reached_once_it_is_shown(browser, serve, shape):
    """Reach leaves content the browser skips unasked, since asking about any box in
    it forces the browser to style the whole of it, and sweeps it once it is drawn.
    So a scrolling box in a closed disclosure or a tab not chosen carries no
    borrowed stop or continuation cue until it is shown. Once shown it owes both."""
    html, show = HIDDEN_SCROLLERS[shape]
    page = open_page(browser, serve(html))
    box = page.locator("#unfolded")
    assert box.evaluate("(box) => box.tabIndex") == -1
    assert (
        box.evaluate("(box) => box.hasAttribute('data-lf-scroll-direction')") is False
    )
    show(page)
    expect(box).to_have_attribute("tabindex", "0")
    expect(box).to_have_attribute("data-lf-scroll-direction", "ltr")
    reached = box.evaluate(
        """(box) => ({
            scrolls: box.scrollWidth > box.clientWidth,
            tab: box.tabIndex,
            sideways: box.hasAttribute('data-lf-scroll-direction'),
        })"""
    )
    assert reached == {"scrolls": True, "tab": 0, "sideways": True}, reached


def _added(page: str) -> str:
    """What a LONG_PAGE variant adds at the end of its main."""
    head, tail = LONG_PAGE.split("</main>")
    return page.removeprefix(head).removesuffix("</main>" + tail)


def test_misplaced_boxes_checks_page_overflow_but_not_an_authored_scroller(
    browser, serve
):
    """The column is the page's boundary. Content inside an authored horizontal
    scroller is reachable, while an otherwise identical page box remains a real spill
    and keeps both the column and root-scrollport checks live. Leaf's margin controls
    stand in the chrome, outside the column, so none of them is a box to report."""
    source = leaf_page(
        "compact geometry boundaries",
        """
<h1>Migration plan</h1>
<lf-draft id="draft"><pre>Move the readers first.</pre></lf-draft>
<div id="scroller" style="overflow-x: auto; width: 100%">
  <span id="reachable" style="display: block; width: 700px">Reach by scrolling.</span>
</div>
<div id="root-spill" style="width: 700px">This box leaves the page.</div>
""",
    )
    page = open_page(browser, serve(source, packages=()))
    resized(page, 540, 720)
    scroller_short = page.evaluate(
        """() => {
          const scroller = document.querySelector('#scroller');
          return scroller.scrollWidth - scroller.clientWidth;
        }"""
    )
    misplaced = render_checks_model.evaluate_probe(page, "misplacedBoxes")
    overflow = root_overflow(page)
    page.close()

    assert scroller_short > 1, "the authored scroller fits, so it proves nothing"
    ats = [finding["at"] for finding in misplaced]
    assert not [at for at in ats if at.startswith("<span")], misplaced
    assert not [at for at in ats if "leaf-margin-cluster" in at], misplaced
    assert "<div id=root-spill>" in ats, misplaced
    assert overflow > 1, "the true page spill did not reach the root scrollport"


def test_declared_space_names_containing_holders_as_advice(browser, serve):
    """An authored or declared breakout names the containers withholding its tracks.
    Shared flows, already allocated room, ordinary tables and workspace cells keep
    their intended containment without a warning."""
    source = leaf_page(
        "Contained exhibits",
        """<div class="layout-column">
          <h1>Evidence</h1>
          <section id="plain">
            <table id="wide-table" data-width="wide"><tr><td>Wide evidence</td></tr></table>
            <lf-diff id="declared-wide"><pre>diff --git a/count.py b/count.py
--- a/count.py
+++ b/count.py
@@ -1 +1 @@
-old
+new
</pre></lf-diff>
            <table id="ordinary-table"><tr><td>Ordinary evidence</td></tr></table>
          </section>
          <aside id="framed" class="callout">
            <table id="framed-table" data-width="wide"><tr><td>Framed evidence.</td></tr></table>
          </aside>
          <section id="wrapper"><section class="layout-flow">
            <table id="nested-table" data-width="wide"><tr><td>Nested evidence.</td></tr></table>
          </section></section>
          <section id="flow" class="layout-flow">
            <div id="wide-flow" data-width="wide">Shared tracks.</div>
            <div id="allocated" data-width="available"><section id="inside-wide">
              <div id="nested-wide" data-width="wide">Already has room.</div>
            </section></div>
          </section>
          <div id="custom-grid" style="display:grid;grid-template-columns:1fr 1fr">
            <p>A companion.</p><div id="grid-wide" data-width="wide">Contained.</div>
          </div>
        </div>
        <div class="layout-workspace"><section id="workspace-cell">
          <div id="workspace-wide" data-width="wide">Uses its workspace cell.</div>
        </section></div>""",
        layout=None,
    )
    page = open_page(browser, serve(source))
    reading = render_checks_model.evaluate_probe(page, "geometryReading", [])
    contained = reading["contained"]
    assert {finding["at"]: finding["holders"] for finding in contained} == {
        "<table id=wide-table>": ["<section id=plain>"],
        "<lf-diff id=declared-wide>": ["<section id=plain>"],
        "<div id=grid-wide>": ["<div id=custom-grid>"],
        "<table id=framed-table>": ["<aside id=framed>"],
        "<table id=nested-table>": ["<section id=wrapper>"],
    }
    findings = render_gate_readings.swept_faults([(1280, reading)])
    advice = [finding for finding in findings if finding.code == "contained-space"]
    assert len(advice) == 5
    assert all(finding.severity == "advice" for finding in advice)
    assert 'class="layout-flow"' in str(advice[0])
    assert "put data-width on that holder" in str(advice[0])


def test_an_obligation_spanning_its_block_is_a_breakout(browser, serve):
    """An explicitly widened obligation keeps its evidence inside the ring. Boxes
    pulled or sized past the actual page edge remain render-gate findings."""
    item = """<lf-ask id="{id}" data-width="wide"><h2>Which one?</h2>
  <figure data-width="wide"><p>Evidence the room holds.</p></figure>
  <lf-options id="{id}-o" choose><lf-option id="{id}-a">This one</lf-option></lf-options>
</lf-ask>"""
    source = leaf_page(
        "Reaching past the column",
        f"""
<h1>Reaching past the column</h1>
<style>#sized-ask {{ max-width: 36rem; }}</style>
<p>Prose sets the column.</p>
{item.format(id="ask")}
{item.format(id="sized-ask")}
<div id="bare" style="margin: 0 -600px; padding: 0 600px; text-indent: -600px">Out.</div>
<div id="tinted" style="margin: 0 -600px; padding: 0 600px; background: #eee">Tint.</div>
<div id="sized" style="width: calc(100% + 600px); background: #eee; --lf-block-frame: 1">
  <figure data-width="wide"><p>Evidence that fills the box.</p></figure>
</div>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    grown = page.evaluate("""() => {
      const ask = document.getElementById('ask').getBoundingClientRect();
      const prose = document.querySelector('main > p').getBoundingClientRect();
      return ask.right - prose.right;
    }""")
    misplaced = render_checks_model.evaluate_probe(page, "misplacedBoxes")
    page.close()

    assert grown > 100, "the lf-ask never spanned its block, so nothing here was tested"
    found = sorted((m["code"], m["at"]) for m in misplaced)
    assert found == [
        ("clipped-out", "<div id=bare>"),
        ("clipped-out", "<div id=sized>"),
        ("clipped-out", "<div id=tinted>"),
        ("past-column", "<div id=bare>"),
        ("past-column", "<div id=sized>"),
        ("past-column", "<div id=tinted>"),
    ], misplaced


def test_a_change_level_with_a_note_is_decided_on_the_change(browser, serve):
    """Both elements in the right margin stand level with what they belong to — the
    controls with the change they decide, the note with the block it annotates — so the
    controls of a change beside a note would be drawn over the note's first line. The
    note holds the rail's strip there, so the controls stand as a pin on the change
    instead, clear of the note, and the gate has no covered words to read."""
    url = serve(NOTE_BESIDE_A_CHANGE)
    page = open_page(browser, url)
    # A note hangs in the margin only where the room beside the column holds it.
    resized(page, 1600, 900)
    page.locator("#sug-level").scroll_into_view_if_needed()
    geometry = """() => {
        const note = document.getElementById('level-note');
        const prose = document.getElementById('sug-level').getBoundingClientRect();
        const row = document.querySelector("[data-lf-margin-for='sug-level']");
        const n = note.getBoundingClientRect(), b = row.getBoundingClientRect();
        return {beside: n.left >= prose.right, place: row.dataset.lfPlace,
                across: Math.min(n.right, b.right) - Math.max(n.left, b.left),
                down: Math.min(n.bottom, b.bottom) - Math.max(n.top, b.top)};
    }"""
    level = page.evaluate(geometry)
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    page.close()

    assert level["beside"], (
        f"the note never hung in the margin, so nothing here was tested: {level}"
    )
    assert level["place"] == "pin", level
    assert level["across"] <= 0 or level["down"] <= 0, (
        f"the change's controls were drawn over the note: {level}"
    )
    assert not [
        f for f in covered if "level-note" in f["at"] or "level-note" in f["under"]
    ], covered


def test_the_covered_words_gate_still_reads_a_control_in_the_flow(browser, serve):
    """The other half of the exemption above, put back as a bug: a control the widget
    hangs out of the flow is answered for, and one standing in the flow is an element in the margin
    like any other. Written against a control the page positions itself, because the
    predicate is the computed position rather than any widget's name.

    `relative` is the case it is written for, being the near-miss that reads as
    positioned and is not: the box keeps its place in the flow and is painted offset
    from it, so a control nudged a pixel would have carried the whole exemption with it
    had the predicate been everything that isn't static."""
    covering = LONG_PAGE.replace(
        "</main>",
        "<p id='under'>A paragraph with something standing on it.</p>"
        "<span role='button' id='over' style='position: relative;"
        " display: block; margin-top: -28px'>Covering words</span>\n</main>",
    )
    page = open_page(browser, serve(covering))
    page.locator("#over").evaluate(
        "element => element.setAttribute('data-lf-offer', '')"
    )
    page.locator("#under").scroll_into_view_if_needed()
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    page.close()
    assert [
        f
        for f in covered
        if {f["at"], f["under"]} == {"<p id=under>", "<span id=over>"}
    ], f"a control the page put in the flow covered a paragraph unreported: {covered}"


# A sidenote beside a section of prose and tiles, the content a strip crushing the
# column would push out of it.
COMPARE_NOTE_PAGE = leaf_page(
    "compare note",
    """
<h1 id="title">Maps</h1>
<section id="comparison" class="layout-flow">
  <h2>Compare, Variants, and Chips</h2>
  <div class="layout-note"><p id="compare-guide">Ordinary sections compare alternatives. Small labels carry their
  attributes.</p><aside class="note" id="compare-note">The page puts short alternatives in a row
  and longer explanations below. Narrow the window to see this note follow the text.
  </aside></div>
  <div id="compare" class="layout-tiles">
    <section class="panel"><small class="tag">power: none</small><small class="tag ok"
    >weight: low</small> <strong>Paper map</strong> Easy to annotate and fold.</section>
    <section class="panel"><small class="tag">power: daily</small><small class="tag warn"
    >weight: medium</small> <strong>Tablet map</strong> Searchable and backlit.</section>
  </div>
</section>
"""
    + "\n".join(
        f"<p id='after-{i}'>Paragraph {i}. " + "Filler. " * 30 + "</p>"
        for i in range(8)
    ),
).replace('<main class="layout-column">', '<main class="layout-column layout-notes">')


def test_the_syntax_probe_reports_code_the_user_cannot_tell_from_its_block(
    browser, serve
):
    """The syntax probe checks native token paint on each background and in shadow roots.

    A theme may use surrounding ink for an italic comment; contrast still catches
    faint keywords, strings on tinted code lines, and numbers in dark diff lines.
    Identically styled names on the same background have different inherited inks,
    so a readable earlier name must not hide the later faint palette override.
    Population assertions prove every faulty surface was actually tokenized.
    """
    page = open_page(browser, serve(CODE_FAULT_PAGE))
    population = page.evaluate(
        """() => ({
          document: [...new Set([...document.querySelectorAll('[data-lf-syn]')]
            .map(span => span.style.color))].sort(),
          shadow: [...new Set([...document.querySelector('#shadowed').shadowRoot
            .querySelectorAll('[data-lf-syn]')].map(span => span.style.color))].sort(),
          comment: getComputedStyle(document.querySelector('#snippet [data-lf-syn]')).fontStyle,
          names: ['#snippet', '#snippet-faint-name'].map(selector => {
            const block = document.querySelector(selector);
            const token = [...block.querySelectorAll('[data-lf-syn]')]
              .find(span => span.textContent === 'ceiling');
            return {style: token.style.cssText, ink: getComputedStyle(token).color,
              background: getComputedStyle(block).backgroundColor};
          }),
        })"""
    )
    syntax = unread_syntax(page)
    page.close()
    assert {"var(--syn-comment)", "var(--syn-keyword)", "var(--syn-string)"} <= set(
        population["document"]
    ), population
    assert "var(--syn-number)" in population["shadow"], population
    assert population["comment"] == "italic", population
    readable, faint = population["names"]
    assert readable["style"] == faint["style"], population
    assert readable["background"] == faint["background"], population
    assert readable["ink"] != faint["ink"], population

    assert len(syntax) == 4, "\n".join(map(str, syntax))
    for appearance, color in (
        ("light", "keyword"),
        ("light", "string"),
        ("light", "name"),
        ("dark", "number"),
    ):
        assert any(
            finding.scheme == appearance
            and finding.values["style"].startswith(f"color: var(--syn-{color});")
            and finding.values["ratio"] < 4.5
            for finding in syntax
        ), syntax

    page = open_page(browser, serve(CODE_CONTROL_PAGE))
    population = page.evaluate(
        """() => ({
          document: document.querySelectorAll('[data-lf-syn]').length,
          shadow: document.querySelector('#default-shadow').shadowRoot
            .querySelectorAll('[data-lf-syn]').length,
        })"""
    )
    assert population["document"] > 0 and population["shadow"] > 0, population
    assert unread_syntax(page) == []


def test_an_authored_project_widget_loads_through_the_real_layer(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
    widgets = tmp_path / ".leaf" / "widgets"
    (widgets / "callout-label.js").write_text(
        'export const label = "project-owned helper";\n'
    )
    module = widgets / "lf-callout.js"
    source = module.read_text()
    runtime_import = 'import { LeafElement } from "/runtime/widget-api.js";'
    assert source.count(runtime_import) == 1
    source = source.replace(
        runtime_import,
        runtime_import + '\nimport { label } from "./callout-label.js";',
    )
    starter = "class extends LeafElement {},"
    assert source.count(starter) == 1
    module.write_text(
        source.replace(
            starter,
            "class extends LeafElement { setup() { this.dataset.helper = label; } },",
        )
    )

    url = serve(CUSTOM_WIDGET_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    page = open_page(browser, url)
    widget = page.locator("#custom-note")
    expect(widget).to_have_attribute("data-lf-done", "1")
    expect(widget).to_have_attribute("data-helper", "project-owned helper")
    assert widget.evaluate(
        "(el) => ({display: getComputedStyle(el).display, "
        "border: getComputedStyle(el).borderTopWidth})"
    ) == {"display": "block", "border": "1px"}


def test_the_layer_traps_no_margin_in_the_panel_it_draws(browser, serve):
    """The trapped-margin reading, asked about the layer's own panel.

    It asks computed styles rather than boxes, so it reaches the runtime's chrome, and
    it reads the panel open, where a trapped margin is one somebody can see. The
    control comes first: a rule that traps one inside the panel has to be found, or a
    clean result is only a reading that never arrived. A page is served rather than a
    bare fixture because the panel has to be holding something for its boxes to exist,
    and a seeded example is the corpus's own thread. The log has to hold an
    anchored comment, not merely exist: the planted rule traps its margin against a
    thread's first message, so a page whose log carries only widget events opens the
    panel on nothing and reports the control as missing."""
    seeded = [
        path
        for path in CORPUS_SOURCES
        if (log := path.with_suffix(".jsonl")).exists()
        and any(
            event.get("kind") == "comment" and event.get("anchor")
            for event in map(json.loads, filter(None, log.read_text().splitlines()))
        )
    ]
    assert seeded, (
        "no corpus source ships a log holding an anchored comment, so the panel would "
        "open on nothing"
    )
    page = open_page(browser, serve(seeded[0]))
    resized(page, 1280, 900)
    [thread] = [
        event["id"]
        for event in map(
            json.loads,
            filter(None, seeded[0].with_suffix(".jsonl").read_text().splitlines()),
        )
        if event.get("kind") == "comment" and event.get("anchor")
    ][:1]
    open_panel_thread(page, thread)

    # The control. A thread's own box draws its inset, and a first block reserving a
    # margin against a neighbour it hasn't got is exactly what the reading names.
    # Weighted, because the layer's own rules are scoped to .lf-chrome and @scope
    # proximity settles a tie an equal selector would otherwise lose here.
    page.evaluate(
        """() => {
             const s = document.createElement('style');
             s.id = 'trap';
             s.textContent =
               '.lf-floating-panel .lf-msg-body { padding-top: 8px !important }'
               + '.lf-floating-panel .lf-msg-body > :first-child'
               + ' { margin-block-start: 9px !important }';
             document.head.append(s);
           }"""
    )
    found = render_checks_model.evaluate_probe(page, "trappedMargins")
    planted = [t for t in found if t["chrome"]]
    assert planted, (
        "a margin trapped inside the panel went unreported, so this reading is not "
        "reaching the layer at all and a clean result below would mean nothing"
    )
    page.evaluate("() => document.getElementById('trap').remove()")

    trapped = [
        t
        for t in render_checks_model.evaluate_probe(page, "trappedMargins")
        if t["chrome"]
    ]
    assert trapped == [], "the layer traps a margin in its own chrome: " + "; ".join(
        f"<{t['tag']} class={t['cls']!r}> draws {t['drawn']:g}px of inset and "
        f"shows {t['drawn'] + t['margin']:g}px {t['edge']} its <{t['child']}>"
        for t in trapped
    )


def test_a_code_frame_trims_the_note_on_its_last_line(browser, serve):
    """A line note may be the framed pre's last child. Its bottom margin then belongs
    inside the code frame just as it does between lines; leaving the rendered pre
    unmarked made the reading report the layer's own six-pixel reservation."""
    page = open_page(browser, serve(CODE_PAGE.replace('at="2"', 'at="4"')))
    trapped = render_checks_model.evaluate_probe(page, "trappedMargins")
    assert not [
        finding
        for finding in trapped
        if finding["tag"] == "pre" and not finding["chrome"]
    ], trapped


def test_a_user_arrives_at_what_they_left_rather_than_watching_it_arrive(
    browser, serve
):
    """A page put back the way the user left it is simply there, and does not assemble
    itself in front of them.

    Turning on design mode or hiding the annotations is a gesture, and gestures may
    move. Coming back to a page where it was already done is not a gesture — nothing
    was just decided, and a page that replays the decisions on arrival would be showing
    the user furniture instead of what they came back to read. The runtime puts the
    arrangement back before the page is presented (`restoreUserView`,
    restore-state.js), so it appears without the motion its gesture plays.

    What is read is every motion the browser reports, which it does through the
    inspector's animation agent as it reports a request or a response: nothing is
    injected, and nothing is timed. The report outlives the motion, so what has to be
    caught is the frame a slide begins on and never the fifth of a second it runs
    for — which is the whole difference from reading `getAnimations` once the page is
    up, a race this machine wins and a loaded one does not.

    Held against a first visit rather than against a list of what may move. The page
    plays one animation of its own while it arrives — the waiting surface's — and a
    list would have had to name it, which is naming the page's furniture, the closed
    list this project keeps not writing. A return may move less than a first visit; it
    may not move more.

    That only works if every load here arrives the same way, and left to itself none
    of them does: the waiting surface is what the page shows when the first poll has
    not answered yet, so on a load quick enough to present without painting a frame it
    never runs at all. Comparing two loads then compares two guesses about how busy
    the machine was — the first visit came up too quickly to show it, the return did
    not, and the return was reported as having moved a surface neither of them owns.
    So the poll is held on every load and let go once the surface is up, which is this
    suite's answer to a race wherever it finds one, and the reading it waits for is the
    page's own. The window that opens is also the one this test is about: it is where a
    restore is put back, and waiting in it is strictly more than catching it.

    What the user left open is the restore case the runtime declares, all of them
    in turn, so another remembered surface is covered the day it starts remembering.
    """
    url = serve(CHANGE_SHAPES_PAGE)
    page = open_page(browser, url)
    # A ResizeObserver notice is the render gate's to adjudicate over two attempts on
    # one document; one heard on these loads is the platform under load and says
    # nothing, so the harness hands them here rather than to the fixture.
    page.lf_resize_notices = []
    resized(page, 1200, 900)

    cdp = page.context.new_cdp_session(page)
    started = []
    cdp.on("Animation.animationStarted", lambda event: started.append(event))
    cdp.send("DOM.enable")
    cdp.send("Animation.enable")

    def moved():
        # The inspector's report outlives the motion, so consume it only after the
        # page's own finite-motion reading says the transition has ended. One rendering
        # frame was merely a guess at when Chrome would emit animationStarted; under
        # contention the gesture could be visible while its report was still queued.
        page_at_rest(page)
        # Flush protocol events sent before this command's reply.
        cdp.send("Animation.getPlaybackRate")
        found = motions(started)
        started.clear()
        return found

    def arrive():
        """One load, waiting in the arrival rather than catching it as it goes past."""
        held = []
        polls = itertools.count()
        page.route(
            "**/api/state*",
            lambda route: held.append(route) if next(polls) == 0 else route.continue_(),
        )
        page.goto(url, wait_until="load")
        render_checks_model.wait_for_probe(page, "upgraded")
        # The page's own statement that it is waiting: the surface it shows while the
        # log is outstanding has finished its dwell and is painting. Waiting for it is
        # what makes every load here the same load, so what a return moves can be held
        # against what a first visit moves without either answer depending on how busy
        # the machine was.
        page.wait_for_function(
            "() => Number(getComputedStyle(document.body, '::after').opacity) > 0"
        )
        assert held, "the first poll went through, so no arrival was stood in"
        held.pop(0).continue_()
        wait_until_ready(page)
        # This arrival is complete and the next call navigates away, so no later wait
        # depends on a poll this unroute might strand.
        page.unroute("**/api/state*")
        return moved()

    restore_cases = user_view_restore_cases(page)
    assert len(restore_cases) > 1, "the runtime declares nothing to arrive in"

    # The control, and the whole reason the silences below say anything: opening On me
    # by hand is the gesture whose motion the arrivals must not have. What it paints
    # is the runtime's business and is not named here; that it paints at all is this
    # reading's, and a reading that reports nothing when something moved would pass
    # every assertion after it.
    toggle_queue(page)
    gesture = moved()
    assert gesture, "a gesture moved nothing the browser reported, so no silence counts"

    page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    first_visit = arrive()

    for restore_case in restore_cases:
        apply_restore_case(page, restore_case)
        extra = {k: v for k, v in arrive().items() if k not in first_visit}
        assert not extra, (
            f"returning to {restore_case['name']} moved what a first visit does not: "
            + "; ".join(f"{k} at {moved_at(cdp, node)}" for k, node in extra.items())
        )
    assert take_browser_errors(page) == []


def test_scrollbar_clearance_reads_generic_content_and_open_shadow_words(
    browser, serve, tmp_path, monkeypatch
):
    """An author's scrolling strip needs room for the overlay bar just as code does.

    Controls, ordinary text flow, and words a widget puts in its open shadow tree
    all reach the same check. Fitting content and an intentionally hidden bar do not.
    Adding block-end room preserves both horizontal overflow and keyboard access. The
    gate's report of the same reading is
    `test_the_render_gate_fails_a_wide_page_that_scrolls_sideways_only_between_viewports`'s.
    """
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entries["lf-callout"].pop("x-verbatim")
    entries["lf-callout"]["x-shadow"] = True
    registry_path.write_text(json.dumps(entries, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-callout.js").write_text(
        'import { once, shadowStage } from "/runtime/widget-api.js";\n'
        'customElements.define("lf-callout", class extends HTMLElement {\n'
        "  connectedCallback() {\n"
        "    if (!once(this)) return;\n"
        "    const content = document.createElement('span');\n"
        "    content.textContent = this.textContent;\n"
        "    this.textContent = '';\n"
        "    shadowStage(this, [content]);\n"
        "  }\n"
        "});\n"
    )
    wide = "sideways words " * 30
    source = leaf_page(
        "Scrollbar room",
        '<h1 id="t">Reading a scrolling box</h1>'
        '<div id="strip"><button>First choice</button><button>Middle choice</button>'
        "<button>Last choice</button></div>"
        f'<div id="flow"><span>{wide}</span><span>{wide}</span>'
        f"<span>{wide}</span></div>"
        f'<div id="shadow"><lf-callout id="words">{wide}</lf-callout></div>'
        f'<div id="raw-words">{wide}</div>'
        '<div id="slotted"><div id="slot-host" style="display: block; width: 600px">'
        '<button style="display: block; width: 600px; height: 40px; margin: 0">Slotted choice</button>'
        '<p style="height: 100px; margin: 0">Hidden words below the clip</p></div></div>'
        '<div id="fits">Short words</div>'
        f'<div id="hidden">{wide}</div>',
        head="""<style>
          #strip, #flow, #shadow, #raw-words, #slotted, #fits, #hidden {
            box-sizing: content-box; width: 240px; overflow: auto;
            padding: 0; border: 0; margin-block: 20px; line-height: 20px;
            white-space: nowrap;
          }
          #strip { display: flex; }
          #strip button { flex: 0 0 180px; height: 40px; margin: 0; }
          #flow { height: 40px; }
          #flow span { display: block; }
          #hidden { scrollbar-width: none; }
          #shadow lf-callout { display: inline; padding: 0; border: 0; margin: 0; }
        </style>""",
    )
    page = open_page(browser, serve(source, packages=(*EXAMPLE_PACKAGES, "./.leaf")))
    page.evaluate(
        """() => {
          const raw = document.getElementById('raw-words');
          raw.attachShadow({mode: 'open'}).append(document.createTextNode(raw.textContent));
          raw.textContent = '';
          document.getElementById('slot-host').attachShadow({mode: 'open'}).innerHTML =
            '<div style="height: 40px; overflow: hidden; line-height: 20px"><slot></slot></div>';
        }"""
    )
    before = page.evaluate(
        """() => Object.fromEntries(['strip', 'flow', 'shadow', 'raw-words', 'slotted', 'fits', 'hidden'].map(id => {
          const box = document.getElementById(id);
          return [id, {width: box.scrollWidth, scrolls: box.scrollWidth > box.clientWidth,
                       vertical: box.scrollHeight > box.clientHeight}];
        }))"""
    )
    assert all(
        before[name]["scrolls"]
        for name in ("strip", "flow", "shadow", "raw-words", "slotted", "hidden")
    ), before
    assert before["flow"]["vertical"], before
    assert not before["fits"]["scrolls"], before
    assert page.locator("#words").evaluate("el => el.textContent") == ""
    assert page.locator("#raw-words").evaluate(
        "el => el.shadowRoot.lastChild.nodeType === Node.TEXT_NODE && "
        "el.shadowRoot.lastChild.parentElement === null"
    )

    findings = render_checks_model.evaluate_probe(page, "scrollbarClearance")
    assert {finding["at"] for finding in findings} == {
        "<div id=strip>",
        "<div id=flow>",
        "<div id=shadow>",
        "<div id=raw-words>",
        "<div id=slotted>",
    }, findings
    assert all(finding["clear"] < finding["required"] == 15 for finding in findings), (
        findings
    )

    page.locator("#strip").evaluate("box => { box.style.visibility = 'hidden'; }")
    hidden = render_checks_model.evaluate_probe(page, "scrollbarClearance")
    page.locator("#strip").evaluate("box => { box.style.visibility = ''; }")
    assert not any(finding["at"] == "<div id=strip>" for finding in hidden), hidden

    page.add_style_tag(
        content="#strip { transform: scale(.5); transform-origin: top left; }"
    )
    scaled = render_checks_model.evaluate_probe(page, "scrollbarClearance")
    assert any(finding["at"] == "<div id=strip>" for finding in scaled), scaled

    page.add_style_tag(
        content="#strip, #flow, #shadow, #raw-words, #slotted { padding-bottom: 15px; }"
    )
    page.locator("#flow").evaluate("box => { box.scrollTop = box.scrollHeight; }")
    assert render_checks_model.evaluate_probe(page, "scrollbarClearance") == []
    page.add_style_tag(content="#strip { transform: scale(2); }")
    assert render_checks_model.evaluate_probe(page, "scrollbarClearance") == []
    page.add_style_tag(content="#strip { transform: none; }")
    page.get_by_role("button", name="Middle choice").press("Shift+Tab")
    expect(page.get_by_role("button", name="First choice")).to_be_focused()
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    last = page.get_by_role("button", name="Last choice")
    expect(last).to_be_focused()
    assert last.evaluate("el => el.matches(':focus-visible')")
    # Native focus scrolling can finish after focus arrives (notably on macOS).
    # Read the clearance once the keyboard destination has actually come into view.
    page.wait_for_function(
        """() => {
          const box = document.getElementById('strip');
          return box.lastElementChild.getBoundingClientRect().right <=
                 box.getBoundingClientRect().right + 1;
        }"""
    )
    reached = last.evaluate(
        """el => {
          const box = el.parentElement, rect = box.getBoundingClientRect();
          const control = el.getBoundingClientRect();
          return {left: box.scrollLeft, visible: control.right <= rect.right + 1,
                  clear: rect.bottom - control.bottom};
        }"""
    )
    assert reached["left"] > 0 and reached["visible"], reached
    assert reached["clear"] >= 15, reached
    assert render_checks_model.evaluate_probe(page, "scrollbarClearance") == []
    assert page.evaluate(
        "() => Object.fromEntries(['strip', 'flow', 'shadow', 'raw-words', 'slotted', 'fits', 'hidden']"
        ".map(id => [id, document.getElementById(id).scrollWidth]))"
    ) == {name: reading["width"] for name, reading in before.items()}


def test_a_table_keeps_its_columns_natural_width_wherever_it_stands(browser, serve):
    """A table's rows are as wide as its columns hold wherever it stands: bare in the
    column, in a panel, in a figure granted the page's room, granted the room itself,
    which is a limit rather than a size, and in an obligation, even an obligation inside the granted
    figure. Spreading the columns over a frame worked in Chrome alone, since Firefox
    never widens a table's grid to its caption. One granted room stands where the prose
    starts. A table too wide for the panel still scrolls inside it.
    Code in a cell is set relative to the cell's text rather than at the chip size."""
    page = open_page(browser, serve(FRAMED_TABLES_PAGE))
    measured = page.evaluate(
        """() => {
        const inner = (box) => {
            const r = box.getBoundingClientRect(), s = getComputedStyle(box);
            return r.right - parseFloat(s.paddingRight) - parseFloat(s.borderRightWidth);
        };
        const rowEnd = (t) => t.querySelector('tr:last-child').getBoundingClientRect().right;
        const bare = document.querySelector('#bare'), framed = document.querySelector('#framed');
        const wide = document.querySelector('#wide-framed');
        const cell = framed.querySelector('td'), code = cell.querySelector('code');
        const own = document.querySelector('#allocated');
        const asked = ['asked-table', 'figure-asked-table'].map(id => {
            const table = document.getElementById(id);
            return {short: Math.round(inner(table.parentElement) - rowEnd(table)),
                    scrolls: table.scrollWidth - table.clientWidth};
        });
        const allocated = ['figure-table'].map(id => {
            const table = document.getElementById(id);
            return Math.round(inner(table) - rowEnd(table));
        });
        return {
            allocated,
            framedShort: Math.round(inner(framed.parentElement) - rowEnd(framed)),
            bareShort: Math.round(inner(bare.parentElement) - rowEnd(bare)),
            ownShort: Math.round(inner(own) - rowEnd(own)),
            ownStart: Math.round(own.querySelector('tr').getBoundingClientRect().left
                - bare.querySelector('tr').getBoundingClientRect().left),
            asked,
            wideScrolls: wide.scrollWidth - wide.clientWidth,
            wideInside: Math.round(inner(wide.parentElement) - wide.getBoundingClientRect().right),
            codeRatio: parseFloat(getComputedStyle(code).fontSize)
                / parseFloat(getComputedStyle(cell).fontSize),
        };
    }"""
    )
    assert measured["framedShort"] > 100, measured
    assert all(short > 100 for short in measured["allocated"]), measured
    assert measured["bareShort"] > 100, "the bare table fills its column"
    assert measured["ownShort"] > 100 and measured["ownStart"] == 0, measured
    assert all(a["short"] > 100 and a["scrolls"] == 0 for a in measured["asked"]), (
        measured
    )
    assert measured["wideScrolls"] > 0 and measured["wideInside"] >= 0, measured
    assert measured["codeRatio"] == pytest.approx(0.9, abs=0.01), measured
    assert root_overflow(page) == 0


def test_an_identifier_in_a_cell_breaks_rather_than_holding_its_column(browser, serve):
    """The theme's second case, reached by a table that used to fall through to the
    third: a column of test names beside a column of prose. A name is one word to
    the line breaker, and unbreakable it held its column at 583px of the 720px
    measure, squeezed the prose to 118px and a few words a line, and scrolled the
    table 83px sideways for the rest. In <code> it breaks inside its cell where it
    must, and the table fits. The names are longer than any share of the measure a
    column gets, so a name that did not break is a name that fitted by luck rather
    than by the rule, and the test says so."""
    page = open_page(browser, serve(IDENTIFIERS_IN_CODE_PAGE))
    measured = page.locator("#held").evaluate(
        """(t) => {
        const range = document.createRange(), lines = (code) => {
            range.selectNodeContents(code.firstChild);
            return new Set([...range.getClientRects()].map(r => Math.round(r.top))).size;
        };
        return { scrolls: t.scrollWidth - t.clientWidth,
                 broke: [...t.querySelectorAll('td code')].some(c => lines(c) > 1) };
    }"""
    )
    assert measured["scrolls"] == 0, measured
    assert measured["broke"], "every name fitted whole, so the rule was never asked"
    assert root_overflow(page) == 0
    for width in range(520, 601, 4):
        resized(page, width, 720)
        scrolls = page.locator("#held").evaluate("(t) => t.scrollWidth - t.clientWidth")
        assert scrolls == 0, (width, scrolls)


def test_the_render_gate_measures_sideways_room_at_the_root_scrollport(browser, serve):
    """A narrow authored body is not the page's viewport. Its child can be wider than
    that body while still fitting on screen, so measuring body would invent sideways
    document overflow where the canonical root scrollport has none. Sized in vw, the page
    keeps that contrast at every width the gate reads, so `rootOverflow`, the gate's
    own reading, is asked at both of its viewports."""
    source = leaf_page(
        "root scrollport width",
        """
<style>
body { width: 40vw; }
#wide-inside-window { width: 70vw; }
</style>
<h1>Capacity plan</h1>
<div id="wide-inside-window">This box still fits in the viewport.</div>
""",
    )

    page = open_page(browser, serve(source))
    for width, height in ((1200, 900), (540, 720)):
        resized(page, width, height)
        body = page.evaluate(
            "() => document.body.scrollWidth - document.body.clientWidth"
        )
        assert body > 0, f"the two candidate measurements do not diverge at {width}px"
        assert root_overflow(page) == 0, (width, body)


def test_a_table_too_wide_to_wrap_scrolls_inside_the_column(browser, serve):
    """The theme's answer for a table with more in it than the column holds. Its
    columns hold what is in them, so it takes the measure only when it needs to
    and wraps its cells past that; when even wrapping can't fit it scrolls inside
    itself — like pre, like lf-board — rather than out into the margin
    where a suggestion's controls hang. `width: 100%` had no third case: the
    table spilled, and at this viewport the window is wide enough that nothing
    scrolled to say so."""
    page = open_page(browser, serve(WIDE_TABLE_PAGE))
    measured = page.locator("#sessions").evaluate(
        """(t) => {
        const main = t.closest('main'), pad = parseFloat(getComputedStyle(main).paddingRight);
        const column = main.getBoundingClientRect().right - pad;
        return { past: Math.round(t.getBoundingClientRect().right - column),
                 scrolls: Math.round(t.scrollWidth - t.clientWidth) };
    }"""
    )
    # Where the width went, then that there was width to go anywhere: a table
    # narrow enough to fit satisfies the first of these while proving nothing,
    # and it is the second that says this one was never such a table.
    assert measured["past"] <= 0
    assert measured["scrolls"] > 0, "this table fits, so it proves nothing"
    assert root_overflow(page) == 0


def test_a_page_hands_its_note_strip_back_when_the_panel_takes_the_room(browser, serve):
    """The margin form is granted by the room beside the page's column, and the thread
    panel stands over the page rather than taking room from it, so the panel decides
    nothing about where a note stands: the window does.

    `page check --render` and the render sweep normally open with no panel, so this
    test exercises the panel's state they do not otherwise visit.

    Three readings distinguish a real container response from either never floating the
    note or releasing it whenever the panel opens: the note begins in the margin, returns
    to flow in a window too narrow for it, and stays in the margin with the panel open
    in one wide enough."""
    url = serve(COMPARE_NOTE_PAGE)
    page = open_page(browser, url)
    page.evaluate("location.hash = 'compare-note'")
    expect(page.locator("#compare-note")).to_be_visible()
    resized(page, 1600, 900)
    reading = """() => {
        const note = document.querySelector('aside.note').getBoundingClientRect();
        const prose = document.querySelector('#compare-guide').getBoundingClientRect();
        const main = document.querySelector('main'), s = getComputedStyle(main);
        return {beside: note.left >= prose.right,
                column: Math.round(main.getBoundingClientRect().width
                    - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight))};
    }"""
    roomy = page.evaluate(reading)
    resized(page, 1024, 900)
    open_threads(page)
    cramped = page.evaluate(reading)
    misplaced = render_checks_model.evaluate_probe(page, "misplacedBoxes")
    resized(page, 1728, 900)
    wide = page.evaluate(reading)
    page.close()

    assert roomy["beside"], (
        f"no note stood in the margin to begin with, so this proves nothing: {roomy}"
    )
    assert not cramped["beside"], (
        f"the strip outlived the room for it: {cramped}, {misplaced}"
    )
    assert misplaced == [], (
        f"content set outside a column the strip had crushed: {misplaced}"
    )
    assert wide["beside"], (
        f"a window wide enough for both moved the notes anyway: {wide}"
    )


def test_label_size_reading_ignores_html_elements_inside_a_drawing(browser, serve):
    """An HTML template appended under SVG is not an SVG label; it must not
    crash the label probe or hide the genuine small SVG label beside it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Mixed drawing namespaces",
                '<svg id="drawing" viewBox="0 0 1000 100" '
                'style="width:250px;font-size:20px">'
                '<text x="10" y="30">SVG label</text><g></g></svg>',
            )
        ),
    )
    # Lit's html template creates HTML elements even when its result is rendered
    # into an SVG parent; the svg template is what creates SVG elements.
    page.locator("#drawing").evaluate("""async drawing => {
      const {html, render} = await window.__lfWidgetApi();
      render(html`<text>HTML template content</text>`, drawing.querySelector('g'));
    }""")
    reading = render_checks_model.evaluate_probe(page, "shrunkLabelReading")
    assert reading["threshold_px"] == 10
    [drawing] = reading["drawings"]
    assert drawing["labels"] == 1
    assert drawing["words"] == "SVG label"
    assert drawing["set"] == 20
    assert drawing["drawn"] == 5
