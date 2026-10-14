"""Browser-gate, arrival, layout, and layer integration tests."""

import itertools
import json
import re
import threading
from html import escape
from urllib.parse import urlsplit

import pytest
import tinycss2
from click.testing import CliRunner
from interact_support import (
    COMMAND_HUB_PACKAGE,
    STATED_TIMEOUT,
    add_test_widget,
    append_carried_log_record,
    append_command,
    running_http_server,
)
from known_widget_findings import KNOWN, PACKAGES
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import hosting as hosting_model
from leaf import http as http_model
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
from leaf.schema import ELEMENT_ID
from leaf.validation import composition as validation_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    CHANGE_SHAPES_PAGE,
    PANEL_PAGE,
    SHORT_SUGGESTION,
    panel_comment,
)
from render_cases_layout import (
    AUTHORED_LINES_PAGE,
    CODE_CONTROL_PAGE,
    CODE_FAULT_PAGE,
    CUSTOM_WIDGET_PAGE,
    EDGE_IDS,
    EDGES,
    FLOATING_PAGE,
    HIDDEN_SCROLLERS,
    IDENTIFIERS_IN_CODE_PAGE,
    NOTE_BESIDE_A_CHANGE,
    ON_PANEL,
    RESIZE_LOOP_EVENT,
    SCROLLED_CONTAINER,
    SHOT_SRC,
    SHOTS,
    SPILLING_PAGE,
    UNMARKABLE_PAGE,
    WIDE_TABLE_PAGE,
    arrival_findings,
    banner_control,
    draw_edge,
    edge_settled,
    edge_world,
    geometry,
)
from render_cases_navigation import (
    CODE_PAGE,
)
from render_cases_widgets import (
    GENERIC_VISUAL_LAYER,
    PART_DIAGRAM_PAGE,
    prefixed_visual_layer,
    visual_widgets,
)
from render_harness import (
    CORPUS_PAGE,
    CORPUS_SOURCES,
    EXAMPLE_PACKAGES,
    EXAMPLES,
    INLINE_PAGE,
    LONG_PAGE,
    RELEASE_FOCUS,
    TOKEN,
    _traffic,
    _until,
    at_rest,
    consume_browser_errors,
    leaf_page,
    left_alone,
    live_counts,
    names,
    open_page,
    pane_posture,
    panel_settled,
    plant_quiet_word,
    primed,
    reader_state,
    resized,
    root_overflow,
    scroll_followers,
    scroll_settled,
    scroll_writes,
    state_changes,
    still_page,
    stored_draft_text,
    take_browser_errors,
    write,
)

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


def test_the_render_gate_renders_each_scheme_viewport_and_margin_width_on_an_armed_page(
    browser, serve
):
    """The gate renders both color schemes at both viewports, in that order, and then
    the page in the light scheme at each width where its margin content changes. A
    sidebar and a sidenote stand in the margin only where the room beside the column
    holds them, which is above the desktop viewport for a sidebar beside a note, so
    the gate finds each width where the page's own residents change, the sidebar's and
    the note's, and renders the page there too, where each has the least room it will
    ever have. The rail holds only Leaf's markers, so its width is not one of them.

    The gate also empties a page's route list, and that is what takes interception
    down. It holds the Leaf entry through a route and takes that route away again, so
    the `unroute` is a real teardown on a page nothing else has routed. A loaded
    document is not an idle one: measured on the corpus page, `/api/state`,
    `/registry.json` and `/icon.svg` are still open at that call, and losing the first
    is a page that never finishes upgrading with nothing on the console to say so. The
    arm goes on before any route the gate adds and is never taken away, so the list
    the browser consults is never empty and no such transition is sent at all."""
    source = leaf_page(
        "margin residents in the gate",
        """
<h1>Migration plan</h1>
<aside class="sidebar" id="route"><nav aria-label="Route"><a href="#move">Move</a></nav></aside>
<aside class="sidenote" id="frequency">Support runs this twice a month.</aside>
<h2 id="move">Move</h2>
<p>Shift one cohort at a time while keeping the old readers available.</p>
""",
    )
    seen = []
    per_page = []

    def record_page(page):
        viewport = page.viewport_size
        dark = page.evaluate("() => matchMedia('(prefers-color-scheme: dark)').matches")
        seen.append(
            (viewport["width"], viewport["height"], "dark" if dark else "light")
        )
        calls = []
        per_page.append(calls)
        route, unroute = page.route, page.unroute

        def recorded_route(url, handler, **kwargs):
            calls.append(("route", url))
            return route(url, handler, **kwargs)

        def recorded_unroute(url, handler=None):
            calls.append(("unroute", url))
            return unroute(url, handler)

        page.route = recorded_route
        page.unroute = recorded_unroute

    reading = render_gate_model.render_version(
        primed(browser, record_page), serve(source, packages=())
    )

    assert reading.failures == []
    assert len(reading.margin_widths) == 2, reading.margin_widths
    assert reading.margin_widths == sorted(reading.margin_widths)
    assert seen == [
        (1200, 900, "light"),
        (1200, 900, "dark"),
        (540, 720, "light"),
        (540, 720, "dark"),
        *((width, 900, "light") for width in reading.margin_widths),
    ]
    arm = render_gate_scheme.INTERCEPTION_ARM
    assert len(per_page) == len(seen)
    for calls in per_page:
        assert calls[0] == ("route", arm), calls
        assert ("unroute", arm) not in calls, calls


def test_the_render_gate_reports_a_compact_spill_and_unreserved_heights(browser, serve):
    """A row that fits the wide viewport and spills from the compact one fails there
    alone, in both schemes. On the same page, a widget that states the height its
    module draws at holds it from first paint, so the gate has nothing to say about it;
    one stating none, or another height, is told the height to state."""
    source = leaf_page(
        "compact spill and reserved heights",
        """
<style>
@media (max-width: 600px) {
  #compact-overflow { width: 700px; }
}
lf-test-drawn { display: block; }
</style>
<h1>Compact route</h1>
<p id="compact-overflow">This row fits the wide viewport and spills from the compact one.</p>
<lf-test-drawn id="reserved" data-height="120"></lf-test-drawn>
<lf-test-drawn id="unreserved"></lf-test-drawn>
<lf-test-drawn id="misreserved" data-height="40"></lf-test-drawn>
""",
    )

    reading = render_gate_model.render_version(
        browser,
        serve(
            source,
            packages=(),
            layer_registry=RESERVING_LAYER,
            layer_widgets=RESERVING_WIDGETS,
        ),
    )

    overflow = [f for f in reading.failures if f.code == "page-scrolls"]
    assert len(overflow) == 2, reading.failures
    assert all(f.viewports == ("540x720",) for f in overflow), overflow
    assert {f.scheme for f in overflow} == {"light", "dark"}
    assert [(f.code, f.at, f.values) for f in reading.advice] == [
        (
            "unreserved-height",
            "<lf-test-drawn id=unreserved>",
            {"drawn": 120, "reserved": None},
        ),
        (
            "unreserved-height",
            "<lf-test-drawn id=misreserved>",
            {"drawn": 120, "reserved": "40"},
        ),
    ]
    assert str(reading.advice[1]) == (
        "<lf-test-drawn id=misreserved> draws 120px tall where its first paint "
        "reserves 40px, so what follows it moves when it is drawn: state "
        'data-height="120"'
    )


def _panel(name: str) -> str:
    return f'<section class="panel" id="{name}"><h2>{name}</h2><p>Words.</p></section>'


def test_the_render_gate_fails_a_page_that_scrolls_sideways_only_between_viewports(
    browser, serve
):
    """A body beside its track, and a row that spills only from 600 to 900px: both fixed
    viewports read the page clean, and only the sweep between them sees it. A control
    row that loses its scrollbar track room only between them is the same reading for
    the overlay bar."""
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
""",
        head="""<style>
#tracks { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-4); }
@media (min-width: 600px) and (max-width: 900px) { #mid-spill { white-space: nowrap; } }
#strip { display: flex; width: 240px; overflow: auto; padding: 0 0 15px; border: 0; }
#strip button { flex: 0 0 180px; height: 40px; margin: 0; }
@media (min-width: 600px) and (max-width: 900px) { #strip { padding-bottom: 0; } }
</style>""",
    )

    reading = render_gate_model.render_version(browser, serve(source, packages=()))

    assert {(f.code, f.at, f.widths) for f in reading.failures} == {
        ("page-scrolls", "", (600, 880)),
        ("scrollbar-clearance", "<div id=strip>", (600, 880)),
    }, reading.failures
    [strip] = [f for f in reading.failures if f.code == "scrollbar-clearance"]
    assert strip.values["clear"] == 0, strip
    assert reading.advice == []


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
    clean at desktop and cross the stated threshold on mobile. Reading leaves the
    DOM, focus, selection, and scroll position intact.
    """
    source = DRAWN_LABELS_PAGE.replace(
        "<h1>Rollout</h1>",
        '<h1>Rollout</h1><div id="arrangement" style="display:flex; gap:16px">'
        "<p>Canary</p><p>Global</p></div>",
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
RESERVING_LAYER = {
    "lf-test-drawn": {
        "description": "A drawing its module makes at a height no rule knows ahead of it.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-height": True,
        "x-example": '<lf-test-drawn id="drawn" data-height="120"></lf-test-drawn>',
    }
}
RESERVING_WIDGETS = {
    "lf-test-drawn.js": """
import { once } from '/runtime/widget-api.js';

customElements.define('lf-test-drawn', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const drawing = document.createElement('div');
    drawing.style.blockSize = '120px';
    this.append(drawing);
    this.classList.add('lf-rendered');
  }
});
"""
}


def test_the_pre_upgrade_proof_reads_the_held_authored_document(browser, serve):
    source = leaf_page(
        "pre-upgrade structure",
        "<h1>Held before Leaf starts</h1>",
    )
    page = browser.new_page()
    page.route(
        "**/theme.css",
        lambda route: route.fulfill(body="main { display: none; }"),
    )
    findings = render_gate_scheme.start_with_pre_upgrade_proof(
        page, serve(source, packages=())
    )

    assert [finding.code for finding in findings] == ["main-unlaid"]


def test_a_module_the_page_never_receives_names_the_wait_that_stopped(browser, serve):
    """A dropped subresource is the timeout the gate used to misattribute.

    The runtime has already started and injected its banner by the time a held module
    stalls the load event, so "the runtime never injected its banner" named the one
    thing that had happened. The document stays at `interactive` with nothing logged
    and no error raised, which leaves the open request as the only evidence of which
    file never arrived — this is where the local server dropping a request the browser
    wrote onto a socket it had already closed reaches the gate.
    """
    source = leaf_page("held module", "<h1>Waiting on a module</h1>")
    page = browser.unwatched.new_page()
    page.set_default_timeout(EXPECTED_STALL_MS)
    holding = []

    def hold_module(route):
        if holding or route.request.url.endswith("/leaf.js"):
            route.continue_()
            return
        holding.append(route)

    page.route("**/runtime/*.js", hold_module)
    try:
        with pytest.raises(RuntimeError) as stopped:
            render_gate_scheme.start_with_pre_upgrade_proof(
                page, serve(source, packages=())
            )
    finally:
        for route in holding:
            route.abort()

    assert holding, "the page asked for no runtime module, so nothing was held"
    path = urlsplit(holding[0].request.url).path
    assert stopped.value.finding.code == "never-reached"
    assert stopped.value.finding.values["arrival"] == "load"
    assert stopped.value.finding.values["requesting"] == [path]


def test_a_wait_before_the_entry_is_released_names_only_the_page_s_own_request(
    browser, serve
):
    """A held head stylesheet may stop parsing before main. At whichever wait
    stops first, the diagnostic names the page's request, not the entry held by
    the gate itself."""
    source = leaf_page("held theme", "<h1>Waiting on a theme</h1>")
    page = browser.unwatched.new_page()
    page.set_default_timeout(EXPECTED_STALL_MS)
    holding = []

    def hold_theme(route):
        holding.append(route)

    page.route("**/theme.css", hold_theme)
    try:
        with pytest.raises(RuntimeError) as stopped:
            render_gate_scheme.start_with_pre_upgrade_proof(
                page, serve(source, packages=())
            )
    finally:
        for route in holding:
            route.abort()

    assert holding, "the page asked for no theme stylesheet, so nothing was held"
    path = urlsplit(holding[0].request.url).path
    assert stopped.value.finding.code == "never-reached"
    assert stopped.value.finding.values["requesting"] == [path]


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


def test_a_released_entry_that_never_arrives_is_named_like_any_other_file(
    dropped_entry_server, dropped_entry_page
):
    """Past the release the entry is the page's own request. What the wait above
    leaves out is the hold, not the file — and a load event still waiting on an entry
    the server accepted and then dropped is exactly the ending this reading exists to
    name, so the release has to hand the entry back to the page."""
    dropped, asked = dropped_entry_server
    page = dropped_entry_page
    page.set_default_timeout(EXPECTED_STALL_MS)
    with pytest.raises(RuntimeError) as stopped:
        render_gate_scheme.start_with_pre_upgrade_proof(page, dropped)
    entry_path = urlsplit(
        page.locator('script[src$="/leaf.js"]').get_attribute("src")
    ).path

    assert asked.is_set(), "the browser never asked for the entry, so nothing dropped"
    assert stopped.value.finding.code == "never-reached"
    assert stopped.value.finding.values["arrival"] == "load"
    assert stopped.value.finding.values["requesting"] == [entry_path]


def test_a_refused_document_reports_the_status_beside_the_wait_that_stopped(
    browser, serve, monkeypatch
):
    """A server that refuses the document leaves the proof with nothing to wait for
    and the page with no console message of its own. The status the gate collected is
    the only thing that says why the wait stopped, so the named wait carries it."""
    real_proof = render_gate_scheme.start_with_pre_upgrade_proof

    def promptly(page, url):
        page.set_default_timeout(EXPECTED_STALL_MS)
        return real_proof(page, url)

    monkeypatch.setattr(render_gate_scheme, "start_with_pre_upgrade_proof", promptly)
    served = serve(leaf_page("refused", "<h1>Refused</h1>"), packages=())
    refused = served.split("?")[0] + "?t=not-the-page-key"

    failures, _notices, completed = render_gate_scheme._render_scheme(
        browser.unwatched, refused, "light", {"width": 1200, "height": 900}, 3_000, []
    )

    assert completed is False
    [failure] = failures
    assert (failure.code, failure.scheme) == ("never-reached", "light")
    assert failure.values["arrival"] == "an authored main"
    assert {
        "code": "failed-load",
        "severity": "error",
        "values": {"status": 401, "url": refused},
    } in failure.values["console"], failure


def test_the_pre_upgrade_proof_holds_its_entry_route_past_the_load_event(
    browser, serve, monkeypatch
):
    """The hold on the entry is also what keeps request interception installed, and
    taking it down belongs after the document has loaded rather than at the release.

    Playwright turns a page's interception off as soon as its last route handler is
    spent, so a `times=1` hold is spent exactly when the module layer starts its
    burst, and the burst loses requests to that transition: measured on the corpus
    page over interleaved attempts, the document never reached load in 5 of 60 with
    the single-shot hold and 0 of 60 with one registered across the load wait. The
    ending is silent — `interactive` with a module still in flight, or with nothing in
    flight at all — so nothing downstream can tell it from a page that is merely slow,
    and the ordering is the only place it can be stated."""
    page = browser.new_page()
    registrations = []
    order = []
    route, unroute = page.route, page.unroute
    wait_for_load_state = page.wait_for_load_state

    def recorded_route(url, handler, **kwargs):
        registrations.append((url, kwargs))
        order.append(f"route {url}")
        return route(url, handler, **kwargs)

    def recorded_unroute(url, handler=None):
        order.append(f"unroute {url}")
        return unroute(url, handler)

    def recorded_wait_for_load_state(state="load", **kwargs):
        order.append(f"reached {state}")
        return wait_for_load_state(state, **kwargs)

    monkeypatch.setattr(page, "route", recorded_route)
    monkeypatch.setattr(page, "unroute", recorded_unroute)
    monkeypatch.setattr(page, "wait_for_load_state", recorded_wait_for_load_state)
    source = leaf_page("entry hold", "<h1>Held before Leaf starts</h1>")
    assert (
        render_gate_scheme.start_with_pre_upgrade_proof(
            page, serve(source, packages=())
        )
        == []
    )

    assert registrations == [("**/leaf.js", {})], registrations
    assert order == ["route **/leaf.js", "reached load", "unroute **/leaf.js"], order


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
    pane_posture(page, upper, "bounded")
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
    pane_posture(page, upper, "flow")
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


def test_a_reload_mid_flight_never_wedges_round_trip(browser, serve, monkeypatch):
    """A navigation ends a trip the browser reports for neither kind, and the ledger
    must not carry it into the next document or every later wait there runs its
    timeout out.

    Accept-all is how a real sweep gets here: it answers its asks one awaited
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
        banner_control(page, ".lf-answer-all").click()
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
    # instead ties this reading to how many asks the page happens to carry.
    #
    # The trip is over when that first attempt leaves `pending`, which is the outbox's
    # own list of attempts with no outcome — a failed post keeps its attempt there and
    # retries it, so an attempt that has left came back. Neither neighbouring fact says
    # that: `acked` is counted in a `finally` around the fetch, so a post that throws
    # counts one and is retried anyway, and an empty `pending` is the momentary gap
    # between the cascade's trips, which paint-to-paint sampling steps over. One
    # attempt leaving is bounded by one trip and stays true once it holds.
    sends = _traffic(page).sends
    banner_control(page, ".lf-answer-all").click()
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
    (theme / "shadow.css").write_text("details { transition: color 60s linear; }\n")
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


def test_the_render_gate_requires_a_declared_threads_host_and_a_defined_element(
    browser, serve, tmp_path, monkeypatch
):
    """A thread declaration whose module omits its host fails visibly, beside the same
    declaration whose module places it and passes. Both are project widgets; only the
    second's starter module leaves out the threadBox placement. A third declares an
    upgrade whose module is valid JavaScript and defines no element, which the gate
    names."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    for tag in ("lf-callout", "lf-unseated", "lf-undefined"):
        add_test_widget(package, tag, upgrade=True)
    (package / "widgets" / "lf-undefined.js").write_text(
        "// Valid JavaScript, but no custom-element definition.\n"
    )
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-callout"]["x-thread-seat"] = {"when": {"id": ["custom-note"]}}
    registry["lf-unseated"]["x-thread-seat"] = {"when": {"id": ["unseated-note"]}}
    registry_path.write_text(json.dumps(registry, indent=2))
    module = package / "widgets" / "lf-callout.js"
    source = module.read_text()
    runtime_import = 'import { once } from "/runtime/widget-api.js";'
    once = "      if (!once(this)) return;\n"
    assert source.count(runtime_import) == 1 and source.count(once) == 1
    module.write_text(
        source.replace(
            runtime_import, 'import { threadBox, once } from "/runtime/widget-api.js";'
        ).replace(
            once, '      if (once(this)) this.append(threadBox(this, "Question"));\n'
        )
    )
    page = CUSTOM_WIDGET_PAGE.replace(
        "</main>",
        '<lf-unseated id="unseated-note"><strong>Heads up</strong> No seat.'
        "</lf-unseated>\n"
        '<lf-undefined id="undefined-note"><strong>Heads up</strong> Never defined.'
        "</lf-undefined>\n</main>",
    )

    failures = render_gate_model.render_version(
        browser, serve(page, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    ).failures

    seats = [f for f in failures if f.code == "missing-thread-seat"]
    assert [(f.at, f.scheme, f.values["hosts"]) for f in seats] == [
        ("<lf-unseated id=unseated-note>", "light", 0)
    ], failures
    assert str(seats[0]) == (
        "[light] <lf-unseated id=unseated-note> declares x-thread-seat but rendered 0 "
        "matching hosts; its module must place exactly one threadBox"
    )
    assert not [f for f in failures if "custom-note" in f.at], failures
    assert any(
        f.code == "missing-upgrades" and f.values["tags"] == ["lf-undefined"]
        for f in failures
    ), failures


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
      const widget = validationWidgetStates().find(s => s.widget?.renderState).widget;
      window.restoreReplay = () => { widget.renderState = original; };
      const original = widget.renderState;
      widget.renderState = function replayProjection() { throw new TypeError('replay rejected'); };
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
    """A class sharing its namespace's identity fails before layout traverses it."""
    page = PART_DIAGRAM_PAGE.replace(
        "</lf-diagram>",
        """</lf-diagram>
<lf-diagram id="model"><pre>
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
        f.values["text"].startswith(
            'leaf: <lf-diagram id="model"> failed: '
            "Mermaid declares diagram identity Job more than once"
        )
        for f in failures
        if f.code == "console-error"
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
          const ink = getComputedStyle(svg.querySelector('.messageText')).color;
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
          const actor = svg.querySelector('rect.actor');
          const targets = [
            ...[...svg.querySelectorAll('text.actor > tspan, text.loopText > tspan, text.noteText > tspan')]
              .map(e => [e, actor, 'fill', 4.5]),
            ...[...document.querySelectorAll('#relationships .edgeLabel .label text, #relationships .edgeLabel .label tspan')]
              .filter(e => !e.children.length)
              .map(e => [e, e.closest('.label').querySelector('rect'), 'fill', 4.5]),
            [document.querySelector('#life rect.outer'), document.querySelector('#life rect.outer'), 'stroke', 3],
            [document.querySelector('#life circle.state-start'), document.querySelector('#life rect.outer'), 'fill', 3],
          ];
          return targets.map(([e, background, property, minimum]) => {
            const paper = luminance(getComputedStyle(background).fill);
            const fill = getComputedStyle(e)[property];
            const text = luminance(fill);
            const contrast = (Math.max(paper, text) + 0.05) / (Math.min(paper, text) + 0.05);
            return {text: e.textContent, fill, ink, contrast, minimum};
          });
        }""")
        assert {p["text"] for p in paint} >= {
            "User",
            "Server",
            "[Retry]",
            "Checks order",
            "runs",
        }, paint
        assert all(
            (p["minimum"] == 3 or p["fill"] == p["ink"])
            and p["contrast"] >= p["minimum"]
            for p in paint
        ), (
            scheme,
            paint,
        )
        assert svg.evaluate("e => e === document.querySelector('#exchange svg')")

    assert page.locator("#identities").evaluate("e => [...e.visualParts.keys()]") == [
        "node:123",
        "node:Ω",
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
        '      const stage = document.createElement("div");\n'
        "      this.append(stage);\n"
        '      stage.attachShadow({ mode: "open" }).textContent = "shadow words";\n'
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
    declared = CliRunner().invoke(
        cli_model.cli, ["status", str(serve.page_dir), "waiting", "Pick a shard."]
    )
    assert declared.exit_code == 0, declared.output
    claim = service_model.page_claim(serve.page_dir)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(serve.page_dir, claim["id"] if claim else None)
    )
    try:
        held = render_gate_scheme.served(page, url, "/api/state").json()
        wait_until_ready(page, held, through="state")
        assert "Pick a shard." in page.locator(".lf-status-text").text_content()
    finally:
        leases_model.release_lease(lease)


def test_the_render_gate_holds_project_widgets_to_their_declarations(
    browser, serve, tmp_path, monkeypatch, declared_reading_package
):
    """Bug-backs for the module contracts the gate enforces, one project widget each,
    on one page, beside the DevTools issues the page owns.

    `lf-callout` declares x-verbatim while its module renders other words in the
    body's stead (quotes would strand on words the screen no longer shows), and
    attaches a shadow root its declaration doesn't declare (the passage walk crosses
    only the declared ones, so an undeclared root's words anchor astray).

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
    source = (
        CUSTOM_WIDGET_PAGE.replace("</head>", control)
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
            "<strong>Heads up</strong> Clipped words.</lf-veil>\n</main>",
        )
    )

    failures = render_gate_model.render_version(
        browser,
        serve(
            source,
            packages=(*EXAMPLE_PACKAGES, "./.leaf"),
            media={src: SHOTS["before"]},
        ),
    ).failures

    def reported(code, at=""):
        return [f for f in failures if f.code == code and at in f.at]

    assert reported("verbatim", "custom-note"), failures
    assert any("<div>" in f.values["hosts"] for f in reported("undeclared-shadow")), (
        failures
    )
    dusk = reported("verbatim", "dusk-note")
    assert [f.scheme for f in dusk] == ["dark"], failures
    assert {f.values["value"] for f in reported("silent-word")} >= {
        "09:00",
        "Escalated",
    }, failures
    # Delivery serves media under the revision, so the issue names that URL.
    issues = reported("devtools-issue")
    assert sorted((f.scheme, f.at, f.values["issue"]) for f in issues) == sorted(
        (scheme, where, "LazyLoadImageIssue")
        for scheme in ("light", "dark")
        for where in ("<img id=unsized>", "<img id=authored>", "<iframe id=frame>")
    ), failures
    assert all(
        [key for key, _ in f.values["details"]] == ["url"]
        and dict(f.values["details"])["url"].endswith(src)
        for f in issues
    ), issues


def test_the_render_gate_checks_custom_controls_at_their_form_boundary(browser, serve):
    page = open_page(browser, serve(leaf_page("Custom control", "<h1>Controls</h1>")))
    page.evaluate(
        """async () => {
          const { offer } = await window.__lfWidgetApi();
          customElements.define('test-control', class extends HTMLElement {
            static formAssociated = true;
            constructor() {
              super();
              this.attachInternals();
              this.attachShadow({mode: 'open'}).innerHTML = '<input aria-label="Choice">';
            }
          });
          const control = offer('test-control');
          control.setAttribute('name', 'choice');
          control.append(offer('test-control'));
          const native = offer('input');
          native.id = 'native-field';
          document.querySelector('main').append(control, native);
        }"""
    )
    assert render_checks_model.evaluate_probe(page, "undeclaredShadowRoots", {}) == []

    page.locator("main > test-control").evaluate(
        "node => node.removeAttribute('data-lf-gen')"
    )
    assert render_checks_model.evaluate_probe(page, "undeclaredShadowRoots", {}) == [
        "<test-control>"
    ]


def test_the_render_gate_checks_undeclared_shadow_roots_inside_thread_chrome(
    browser, serve
):
    """A reply panel is runtime UI, while a widget inside its message remains page
    content. Only a control built through offer is exempt from the declaration check;
    inheriting the panel's UI ancestry cannot hide an undeclared widget root."""
    page = open_page(browser, serve(leaf_page("Reply widget", "<h1>Reply</h1>")))
    page.evaluate(
        """async () => {
          const {offer} = await window.__lfWidgetApi();
          for (const tag of ['generated-control', 'reply-widget'])
            customElements.define(tag, class extends HTMLElement {
              constructor() {
                super();
                this.attachShadow({mode: 'open'}).innerHTML = '<p>Shadow words</p>';
              }
            });
          const panel = document.createElement('div');
          panel.className = 'lf-page-thread lf-ui';
          panel.append(offer('generated-control'), document.createElement('reply-widget'));
          document.querySelector('main').append(panel);
        }"""
    )
    assert render_checks_model.evaluate_probe(page, "undeclaredShadowRoots", {}) == [
        "<reply-widget>"
    ]


def test_the_render_gate_reads_widgets_in_the_page_and_in_replies_alike(
    browser, serve, tmp_path, monkeypatch
):
    """Three contracts the gate holds for a widget wherever it stands, the page or an
    agent's reply in the thread panel, on one page with one reply apiece.

    Anonymous verbatim owners keep distinct page and reply provenance: of two id-less
    `lf-anon` in each place, the second, which replaces its words, is named by its
    occurrence on the page and in the reply event.

    A verbatim wrapper owns its prose and the order of its children, not the
    rendering of the nested widgets it holds: `lf-shell` changing a passive span or
    reordering its pieces is reported, its pieces drawing generated descendants is
    not, and neither is a bare pane.

    Generated paint must resolve against the page's live cascade. A missing custom
    property is valid CSS syntax, so a generated SVG silently falls back to black, in
    `lf-paint` on the page and frozen into a reply alike. A fallback is the control: it
    names an absent property but resolves to a shipped color in both schemes. The
    native SVG is the other control: a gradient reference is valid paint even though
    it is not a color.

    And the replay check reaches a decision made in the panel. `RELATIVE_REPLAYS`
    applies every winner in force again and asks whether anything moved; a widget an
    agent sent in a reply is folded by a projection of its own and replayed into a tree
    the panel built, and the probe reads the validation state adapter, which returns
    early when nothing is in force. No page the gate was ever run over held such an
    action, so it was reporting clean on an empty list, and the population is asserted
    before the gate is asked anything. Both of the group's verbs stand: `choose`
    declares a record, so a second application that moved anything is a finding;
    `answer` declares none, and is held to a second application not throwing."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    for tag in ("lf-anon", "lf-shell", "lf-paint"):
        add_test_widget(package, tag, upgrade=True)
    registry_path = package / "registry.json"
    declarations = json.loads(registry_path.read_text())
    declarations["lf-anon"]["properties"]["mode"] = {
        "type": "string",
        "enum": ["replace"],
    }
    declarations["lf-anon"]["required"] = []
    declarations["lf-shell"]["properties"]["mode"] = {
        "type": "string",
        "enum": ["prose", "order"],
    }
    declarations["lf-piece"] = {
        "description": "An anonymous nested upgraded piece.",
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": True,
        "x-example": "<lf-piece>Example</lf-piece>",
    }
    registry_path.write_text(json.dumps(declarations, indent=2))
    modules = {
        "lf-anon": (
            "  connectedCallback() {\n"
            "    if (!once(this)) return;\n"
            '    if (this.getAttribute("mode") === "replace")\n'
            '      this.textContent = "Replacement words.";\n'
            "  }\n"
        ),
        "lf-piece": (
            "  connectedCallback() {\n"
            "    if (!once(this)) return;\n"
            '    const generated = document.createElement("span");\n'
            '    generated.dataset.lfGen = "1";\n'
            '    generated.textContent = " generated descendant";\n'
            "    this.append(generated);\n"
            "  }\n"
        ),
        "lf-shell": (
            "  connectedCallback() {\n"
            "    if (!once(this)) return;\n"
            '    if (this.getAttribute("mode") === "prose")\n'
            '      this.querySelector("span").textContent = "changed passive prose";\n'
            '    if (this.getAttribute("mode") === "order") {\n'
            '      const pieces = this.querySelectorAll("lf-piece");\n'
            "      pieces[0].before(pieces[1]);\n"
            "    }\n"
            "  }\n"
        ),
        "lf-paint": (
            "  connectedCallback() {\n"
            "    if (!once(this)) return;\n"
            '    this.innerHTML = `<svg width="160" height="80" viewBox="0 0 160 80">\n'
            '      <rect data-id="missing" width="70" height="70" fill="var(--accent-glow)" />\n'
            '      <rect x="80" width="70" height="70" fill="var(--diagram-safe)" />\n'
            "    </svg>`;\n"
            "  }\n"
        ),
    }
    for tag, body in modules.items():
        (package / "widgets" / f"{tag}.js").write_text(
            'import { once } from "/runtime/widget-api.js";\n'
            f'customElements.define("{tag}", class extends HTMLElement {{\n'
            + body
            + "});\n"
        )
    source = leaf_page(
        "widgets in the page and in replies",
        """
<h1 id="title">Widgets in the page and in replies</h1>
<lf-anon>First page owner.</lf-anon>
<lf-anon mode="replace">Second page owner.</lf-anon>
<lf-shell id="honest-shell">Before <span>passive prose</span>
  <lf-piece>First child.</lf-piece>
  <lf-piece>Second child.</lf-piece> After
</lf-shell>
<lf-shell id="prose-shell" mode="prose">Before <span>passive prose</span>
  <lf-piece>First child.</lf-piece>
  <lf-piece>Second child.</lf-piece> After
</lf-shell>
<lf-shell id="order-shell" mode="order">Before <span>passive prose</span>
  <lf-piece>First child.</lf-piece>
  <lf-piece>Second child.</lf-piece> After
</lf-shell>
<lf-pane id="bare-pane" label="Decision"><p>Pane body.</p></lf-pane>
<lf-paint id="flow"></lf-paint>
<svg id="gradient" width="20" height="20" viewBox="0 0 20 20">
  <defs><linearGradient id="blue"><stop stop-color="var(--accent)" /></linearGradient></defs>
  <rect width="20" height="20" fill="var(--diagram-gradient)" />
</svg>
""",
        head="""<style>:root {
  --diagram-safe: var(--not-defined, var(--ok-tint));
  --diagram-gradient: url(#blue) var(--accent);
}</style>""",
    )
    url = serve(source, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    replies = {
        "r-anonymous": (
            "<lf-anon>First reply owner.</lf-anon>"
            '<lf-anon mode="replace">Second reply owner.</lf-anon>'
        ),
        "r-wrapper": (
            '<lf-shell id="reply-shell">Reply before '
            "<lf-piece>reply child</lf-piece> reply after</lf-shell>"
        ),
        "r-paint": '<lf-paint id="sent"></lf-paint>',
        "r-list": (
            '<lf-ask id="an-set-decision"><h3>What should I carry into the patch?</h3>'
            '<lf-options id="an-set" choose multiple>'
            '<lf-option id="an-chase">Chase them monthly</lf-option>'
            '<lf-option id="an-clear">Clear the stall ourselves</lf-option>'
            '<lf-option id="an-say">Say what the spinner is</lf-option>'
            "</lf-options></lf-ask>"
        ),
    }
    for reply, markup in replies.items():
        comment = f"c-{reply.removeprefix('r-')}"
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "id": comment,
                "author": "user",
                "revision": 1,
                "text": "Show it in your reply.",
            },
        )
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "id": reply,
                "author": "agent",
                "parent": comment,
                "revision": 1,
                "text": "Here it is:",
                "markup": markup,
            },
        )

    user = {"kind": "action", "author": "user", "revision": 1, "widget": "an-set"}
    choose = {"action": "choose", "detail": {"value": ["an-chase", "an-say"]}}
    append_command(serve.page_dir, user | choose)
    # The Done press. Recordless, and the last word on the group.
    append_command(serve.page_dir, user | {"action": "answer", "detail": {}})
    # The population first: the probe returns clean for an empty list.
    page = open_page(browser, url)
    resized(page, 1280, 900)
    current = page.evaluate(
        "async () => (await window.__lfCheckApi())"
        ".validationWidgetStates().flatMap(({widget, state}) =>"
        " Object.values(state).map(current => [widget.id, current.action]))"
    )
    page.close()
    assert ["an-set", "choose"] in current and ["an-set", "answer"] in current, (
        f"the user's decisions are not among what the runtime hands the gate: "
        f"{current} — the replay would be handed nothing and report clean"
    )

    failures = render_gate_model.render_version(browser, url).failures

    assert not [f for f in failures if "an-set" in f.at], failures
    dishonest = [failure for failure in failures if failure.code == "verbatim"]
    anonymous = [failure for failure in dishonest if "lf-anon" in failure.at]
    assert sorted((f.scheme, f.values["provenance"]) for f in anonymous) == sorted(
        (scheme, provenance)
        for scheme in ("light", "dark")
        for provenance in (["page", None, 1], ["event", "r-anonymous", 1])
    ), anonymous
    wrapped = [failure for failure in dishonest if "lf-anon" not in failure.at]
    assert sorted(f.at for f in wrapped) == sorted(
        ["<lf-shell id=prose-shell>", "<lf-shell id=order-shell>"] * 2
    ), failures

    unresolved = [f for f in failures if f.code == "invalid-paint"]
    assert sorted((f.at, f.values["element"]) for f in unresolved) == sorted(
        [("<lf-paint id=flow>", "rect"), ("<lf-paint id=sent>", "rect")] * 2
    ), failures
    assert all(
        f.values | {"at": f.at}
        == {
            "at": f.at,
            "part": "missing",
            "element": "rect",
            "property": "fill",
            "value": "var(--accent-glow)",
        }
        for f in unresolved
    ), unresolved


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
        'import { keepsText, once, widgetController } from "/runtime/widget-api.js";\n'
        'customElements.define("lf-stateful", class extends HTMLElement {\n'
        "  controller = widgetController(this);\n"
        "  stop;\n"
        "  connectedCallback() { once(this); this.stop ??= this.controller.subscribe(() => {}); }\n"
        "  disconnectedCallback() { this.stop?.(); this.stop = null; }\n"
        "  renderState(state) {\n"
        '    if (state.change.value === "corrupt" || state.status.value === "corrupt")\n'
        '      keepsText(this.closest("lf-shell")?.querySelector(":scope > p")'
        ' ?? this.querySelector("p"), "State replaced unrelated prose.");\n'
        "  }\n"
        "});\n"
    )


def test_widget_state_excuses_only_the_verbatim_prose_it_projects(
    browser, serve, tmp_path, monkeypatch
):
    """A user's action and an agent's report each excuse the change their widget's
    own state projects and nothing else: a widget whose state rewrites its unrelated
    prose is reported, and so is a child whose action rewrites its preserving
    wrapper's prose. Beside them, the changes projections honestly make (a draft's
    rewrite in force, a suggestion accepted and so retired, and one accepted then
    withdrawn) are not."""
    monkeypatch.chdir(tmp_path)
    _author_stateful_verbatim_widget(tmp_path)
    url = serve(
        leaf_page(
            "verbatim after state",
            """
<h1>Stateful prose</h1>
<lf-stateful id="acted"><p>Authored prose must remain.</p></lf-stateful>
<lf-stateful id="reported"><p>Reported prose must remain.</p></lf-stateful>
<lf-shell id="shell"><p>Wrapper prose must remain.</p>
  <lf-stateful id="child"><p>Child prose.</p></lf-stateful></lf-shell>
<lf-draft id="edited"><pre>Authored draft.</pre></lf-draft>
<lf-suggestion id="retired">
  <lf-old><lf-draft id="retired-draft"><pre>Retired draft.</pre></lf-draft></lf-old>
  <lf-new><p>Accepted replacement.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="undone">
  <lf-old><lf-draft id="undone-draft"><pre>Restored draft.</pre></lf-draft></lf-old>
  <lf-new><p>Withdrawn replacement.</p></lf-new>
</lf-suggestion>
""",
        ),
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    user = {"kind": "action", "author": "user", "revision": 1}
    corrupt = {"action": "change", "detail": {"value": "corrupt"}}
    for widget in ("acted", "child"):
        append_command(serve.page_dir, user | corrupt | {"widget": widget})
    append_command(
        serve.page_dir,
        {
            "kind": "report",
            "author": "agent",
            "agent": "worker",
            "revision": 1,
            "widget": "reported",
            "action": "status",
            "detail": {"value": "corrupt"},
        },
    )
    edit = {"action": "edit", "detail": {"value": "User's current draft."}}
    append_command(serve.page_dir, user | edit | {"widget": "edited"})
    accept = {"action": "decide", "detail": {"outcome": "accept"}}
    append_command(serve.page_dir, user | accept | {"widget": "retired"})
    withdrawn = append_command(serve.page_dir, user | accept | {"widget": "undone"})
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": withdrawn["id"]},
    )

    failures = render_gate_model.render_version(browser, url).failures

    dishonest = [failure for failure in failures if failure.code == "verbatim"]
    assert sorted(f.at for f in dishonest) == sorted(
        ["<lf-stateful id=acted>", "<lf-stateful id=reported>", "<lf-shell id=shell>"]
        * 2
    ), failures


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
    return scroll_followers(scroll_writes(page, SCROLL_PASS, READING_SCROLLER))


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
    # unrelated chrome while these property-only changes are made.
    def draft_reading():
        return [line for line in reader_state(page) if line.startswith("field: ")]

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
# page with nothing for a drawer has no door to it. Escape unwinds any of them to the
# page (keyboard/AGENTS.md); the ones Go-to opens take the most presses. A new surface
# joins by its keys.
#
# A page has a thread card to open when the Threads control counts an open thread, in
# its `data-lf-count` (banner.js). Its words are no door: Playwright's `:text-matches`
# matches the smallest element holding them, the label inside the control.
OPEN_THREADS = '.lf-threads-toggle[data-lf-count]:not([data-lf-count="0"])'
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
    "thread card": (["t"], OPEN_THREADS),
    "threads panel": (["g", "Shift+t"], None),
    "on panel": (["g", "Shift+m"], ".lf-btn.lf-queue"),
    "leaves drawer": (["g", "Shift+l"], ".lf-btn.lf-others"),
    "page map": (["g", "Shift+p"], None),
    "versions menu": (["g", "Shift+v"], None),
    "draw mode": (["w"], None),
    "design mode": (["l"], None),
    "shortcut bar": (["?"], None),
    "command reference": (["?", "?"], None),
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
    left_alone(page)
    page.evaluate(RELEASE_FOCUS)

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
    for surface, (keys, door) in SURFACES.items():
        if door and not page.locator(door).first.is_visible():
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
        page.wait_for_function(
            """async () => {
            const {readingRegions} = await window.__lfCheckApi();
            const boxes = new Set([document.scrollingElement, ...readingRegions().map(region => region.body)]);
            for (const box of boxes) box.scrollTo({left: 0, top: 0, behavior: 'instant'});
            return true;
        }""",
            timeout=render_checks_model.SERVED_TIMEOUT_MS,
        ).dispose()
        rendered(page)
        reading = page.wait_for_function(
            """async () => {
            const {readingRegions} = await window.__lfCheckApi();
            const position = box => [box.scrollLeft, box.scrollTop];
            return Object.fromEntries([
                ['$page', position(document.scrollingElement)],
                ...readingRegions().map(region => [region.id, position(region.body)]),
            ]);
        }""",
            timeout=render_checks_model.SERVED_TIMEOUT_MS,
        )
        try:
            positions = reading.json_value()
        finally:
            reading.dispose()
        return [
            *reader_state(page),
            "scroll positions: " + json.dumps(positions, sort_keys=True),
        ]

    left_alone(page)
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
    "thread card reply": lambda page: (
        page.locator(OPEN_THREADS).first.is_visible() and ["t", "c"]
    ),
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
        page.evaluate(RELEASE_FOCUS)
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
    declares only in another, such as a multiple-choice ask's Done, goes unseen
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
    them. A padded box away from any frame's edge keeps its heading's margin inside its
    inset, and the reading says to declare that box's frame."""
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
<div id="padded" style="padding:12px;border:1px solid">
  <h2 id="padded-heading">Padded, undeclared</h2>
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


def test_the_page_edge_is_no_frame(browser, serve):
    """A page with no Layout keeps the browser's margin on its body, and the live root
    scrolls, so the root holds that margin in. The root draws no frame, its edge
    being the window's, so the reading has nothing to ask of it, where it named the
    root of every such page. A root that draws padding is a frame like any box."""
    page = open_page(
        browser, serve(leaf_page("No Layout", "<p>Plain prose.</p>", layout=None))
    )
    margin = page.evaluate("() => getComputedStyle(document.body).marginTop")
    trapped = render_checks_model.evaluate_probe(page, "trappedMargins")
    page.evaluate("() => document.documentElement.style.padding = '12px'")
    framed = render_checks_model.evaluate_probe(page, "trappedMargins")
    page.close()

    assert margin == "8px", "the body lost the browser's margin, so this tests nothing"
    assert trapped == [], trapped
    assert [f["at"] for f in framed] == ["<html>", "<html>"], framed


@pytest.mark.parametrize("display", ("flex", "grid"))
@pytest.mark.parametrize("frame", ("1", "trim", "propagated"))
def test_a_row_at_a_frame_edge_holds_the_trim_by_declaring_it(
    browser, serve, display, frame
):
    """A row holds its edge whether it declares the frame or receives its edge from
    outside. The advice names the actual split, and its documented declaration stops
    that trim. An unframed row's deliberate item margins remain the author's choice."""
    row = f"""<div id="row" style="display:{display};grid-template-columns:1fr 1fr;gap:12px;
      padding:24px;--lf-block-frame:{"0" if frame == "propagated" else frame}">
  <p id="left">Left.</p><p id="right">Right.</p>
</div>"""
    if frame == "propagated":
        row = f'<div style="--lf-block-frame:1">{row}</div>'
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Split row",
                f"""<h1>Rows</h1>{row}
<div id="deliberate" style="display:{display};grid-template-columns:1fr 1fr">
  <p style="margin-block-start:0">One deliberately higher item.</p>
  <p style="margin-block-start:13px">One lower item.</p>
</div>
<p>Following text keeps the rows away from the page frame's edges.</p>""",
            )
        ),
    )

    def tops():
        return page.evaluate(
            """() => ['left', 'right'].map(id =>
              Math.round(document.getElementById(id).getBoundingClientRect().top))"""
        )

    left, right = tops()
    assert left != right
    assert any(
        f["id"] == "row" and f["edge"] == "above"
        for f in render_checks_model.evaluate_probe(page, "splitEdges")
    )
    assert not [
        f
        for f in render_checks_model.evaluate_probe(page, "splitEdges")
        if f["id"] == "deliberate"
    ]
    page.locator("#row").evaluate("el => el.style.setProperty('--lf-holds-edge', '1')")
    left, right = tops()
    assert left == right
    assert not [
        f
        for f in render_checks_model.evaluate_probe(page, "splitEdges")
        if f["id"] == "row"
    ]


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
# to follow it there. The list states the inline floor; the block floor is padding on
# the controls a flex or grid container could squeeze, and min-height on the rest.
AIM_FLOOR_RULE = "min-width: var(--aim-floor);"


def aim_selectors():
    sheet = (schema_model.ASSETS / "shadow.css").read_text()
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


AIM_BOXES = """(selectors) => {
  const floor = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--aim-floor")
  );
  const short = [];
  let seen = 0;
  const sweep = (root) => {
    for (const el of root.querySelectorAll(selectors)) {
      const box = el.getBoundingClientRect();
      // A box and not checkVisibility(): the corpus renders much of itself inside
      // content-visibility sections, which this browser answers no for, and a control
      // laid out inside one is a control a user reaches by scrolling to it.
      if (!box.width || !box.height) continue;
      const shown = getComputedStyle(el);
      // Hidden, or standing there for a pointer a finger is not: the diff's line
      // comment is transparent and takes no presses until its row is hovered, and a
      // finger never hovers it.
      if (shown.visibility === "hidden") continue;
      if (shown.opacity === "0" || shown.pointerEvents === "none") continue;
      seen += 1;
      if (Math.min(box.width, box.height) < floor - 0.5)
        short.push(`${Math.round(box.width)}x${Math.round(box.height)} ${el.className}`);
    }
    for (const el of root.querySelectorAll("*"))
      if (el.shadowRoot) sweep(el.shadowRoot);
  };
  sweep(document);
  return {floor, seen, short};
}"""


# Everything an injected control still draws once the medium has taken the press away.
# `cursor` first, the hand being the plainest promise a page makes; the rest is the dress
# a control wears — a chip ground, a pill's corner, a border, a link's underline, a
# summary's marker. Colour is not read: a chip that is red is saying something, and what a
# control says is the other half of this bargain rather than this half.
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
        s.listStyleType !== 'none' && 'a marker',
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
    // An authored output placeholder that is explicitly hidden has no paper reading.
    shown: [...d.children].filter(c =>
      !c.matches('summary, script, style, template') &&
      !c.hasAttribute('data-lf-gen') && !c.hidden)
      .every(c => c.checkVisibility()),
  }))"""


def adopted_sheet_findings(page):
    """The runtime's sheets are adopted, so they cascade after theme.css and after every
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
    where it is delivered.

    Layer order is the one other thing the move could reverse. A module sheet adopted
    first names `lf-base` before chrome.css names `lf-reset`, so the copy opens with the
    statement the page's first sheet makes (`@layer lf-reset, lf-base, lf-layouts`). An
    anonymous layer theme.css opens meets nothing here: every rule in it asks for a body
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
    list, then measures every visible control under an emulated finger."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
    try:
        assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
            "the touch emulation never reached Leaf's coarse-pointer rules"
        )
        measured = page.evaluate(AIM_BOXES, aim_selectors())
    finally:
        cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": False})
        cdp.detach()
    assert measured["floor"] == 44, f"a finger asked for {measured['floor']}px"
    assert measured["seen"] > 50, f"only {measured['seen']} aims stood on the corpus"
    if not measured["short"]:
        return []
    return [
        f"{len(measured['short'])} of {measured['seen']} aims are smaller than "
        f"{measured['floor']}px under a finger:\n"
        + "\n".join(sorted(measured["short"]))
    ]


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
    page.get_by_role("tab", name="Command", exact=True).click()
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


def test_the_layer_holds_its_whole_page_rules_on_the_corpus(browser, serve):
    """The corpus is the page that holds every widget and idiom at once, so the layer's
    whole-page rules are read on it, on one page, in turn: the adopted sheet decides
    nothing by standing last (`adopted_sheet_findings`), every aim takes a finger
    (`short_aim_findings`), and paper takes the press off everything it cannot press
    (`pressable_paper_findings`). The touch emulation and print media are each put back
    before the next reading.

    First, composition preserves markup, not another page's durable versions: the
    gallery's durable-embedding scenario stays hidden and unloaded in the corpus,
    which has no version 2 to embed. The corpus then goes back to its first tab, where
    the aims are measured."""
    # The corpus's sort film otherwise repaints SVG values while the sheets move.
    page = open_page(
        browser,
        serve(CORPUS_PAGE),
        context=browser.new_context(
            viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
        ),
    )
    page.locator('[role="tab"][aria-controls="corpus-feature-gallery"]').click()
    page.locator('[role="tab"][aria-controls="bg-view-page"]').click()
    expect(page.locator("#bg-durable-embedding")).to_have_attribute("hidden", "")
    assert page.locator("#bg-durable-frame").get_attribute("src") == "about:blank"
    page.locator('[role="tab"][aria-controls="corpus-review-a-plan"]').click()
    expect(page.locator("#corpus-review-a-plan")).to_be_visible()

    findings = {
        "sheet order": adopted_sheet_findings(page),
        "aims": short_aim_findings(page),
        "paper": pressable_paper_findings(page),
    }
    failed = {reading: found for reading, found in findings.items() if found}
    assert failed == {}, "\n\n".join(
        f"{reading}:\n" + "\n".join(found) for reading, found in failed.items()
    )


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
    that and loop. One that fits keeps its padding, with no bar to make room for."""
    url = serve(WIDE_TABLE_PAGE)
    wide = "word " * 60
    panel_comment(
        serve.page_dir,
        f"A wide block:\n\n```\n{wide}\n{wide}\n```\n\nAnd one that fits:\n\n"
        "```\nshort\n```",
        {"section": "p"},
        author="agent",
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    measured = page.evaluate(
        """() => {
        const read = """
        + TEXT_CLEAR_OF_BAR
        + """;
        const [wide, fits] = document.querySelectorAll('.lf-threads .lf-msg-body pre');
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
    assert measured["fits"]["clear"] <= measured["fitsPad"] + 3, measured


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
            '<lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>',
        ),
        packages=("diff",),
    )
    wide = "_".join(["argument"] * 40)
    data_model.cmd_data_set(
        serve.page_dir,
        "calls-data",
        f"calldiff diff main → feature\n  changed()  app.py:1\n+ └─ {wide}()  app.py:2",
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


FRAMED_TABLES_PAGE = leaf_page(
    "Framed tables",
    """
<h1 id="t">Checks</h1>
<table id="bare"><tr><th scope="row">Error rate</th><td><code>0.11%</code></td></tr></table>
<table id="allocated" data-width="wide"><tr><th>Session</th><td>9:00</td></tr></table>
<figure data-width="available">
<table id="figure-table"><tr><th>Session</th><td>9:00</td></tr></table>
</figure>
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


def test_every_table_the_theme_sets_honestly_passes_the_gate(browser, serve):
    """The theme's three cases leave the whole gate with nothing to report, on one page:
    a table too wide to wrap that scrolls inside the column, tables a panel or an
    allocation frames, and identifiers in <code> that break inside their cells.

    The scrolling table carries every line an author can write and no wrap:
    `value <code>7</code>` on one line (an inline <code> is set at 84% and starts 3px
    lower, so a reading of rect tops called it a wrap and told the author to write the
    <code> they had written), a <br>, a newline under <pre>, and words either side of a
    nested table. A wrap is what goes away with soft wrapping turned off, and none of
    these does. A comment on one of its cells leaves it clean too, as one on a widget's
    option beside it does: the mark paints the words and the runtime's count stands in
    the chrome, so nothing the runtime writes is read as the page's words or widens the
    page."""

    def tables(page, first):
        start = page.index(first)
        return page[start : page.rindex("</main>")]

    option = INLINE_PAGE[INLINE_PAGE.index("<lf-ask") :]
    option = option[: option.index("</lf-ask>") + len("</lf-ask>")]
    page = AUTHORED_LINES_PAGE.replace(
        "</main>",
        tables(FRAMED_TABLES_PAGE, '<table id="bare">')
        + tables(IDENTIFIERS_IN_CODE_PAGE, '<table id="held">')
        + option
        + "</main>",
    )
    url = serve(
        page,
        anchored=[("sessions", "value_number_3"), ("opt-b", "quietly puts one back")],
    )
    # Vacuous otherwise: the gate has to be looking at a page that carries both.
    expect(open_page(browser, url).locator(".lf-mark-note")).to_have_count(2)

    reading = render_gate_model.render_version(browser, url)
    assert (reading.failures, reading.advice) == ([], []), reading


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
    So a scrolling box in a closed disclosure or a tab not chosen carries nothing of
    reach's until it is shown — the holds mark would say it had been read — and once
    shown it owes what reach owes any overflowing box: a tab stop, the holds mark,
    and the sideways paint."""
    html, show = HIDDEN_SCROLLERS[shape]
    page = open_page(browser, serve(html))
    box = page.locator("#unfolded")
    assert box.evaluate("(box) => box.hasAttribute('data-lf-holds')") is False, (
        "reach read a box in skipped content"
    )
    show(page)
    expect(box).to_have_attribute("data-lf-holds", "1")
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


def test_the_render_gate_tells_what_a_column_loses_from_what_stands_beside_it(
    browser, serve
):
    """The column's readings, put on one page beside their controls.

    Content set past the column: the window is the wider of the two boxes, 1200px
    against a 720px column, so content can stand out in the margin with the document
    still not scrolling sideways, and the static lint reads pinned pixels, which a vw
    width is not. The failure names the element and how far out it is.

    Floats: what tells a margin resident from a spill is where its box sits, clear of
    the column on the side it floats to or across the edge it started inside.
    Exempting floats outright would retire the check for every element that happens to
    carry one. Both readings run up the ancestors, because a resident answers for what
    it holds, and the side is resolved rather than string-matched, so `inline-start`
    is the same left edge. A float carried off the window's leading edge is drawn
    outside the root scrollport, which never scrolls before that edge, so only the
    clipping reading sees it. Fixed placement answers for a box wholly outside the
    column, not one crossing it; only the desktop leaves an outer gutter wider than
    the 174px the fixed resident takes.

    Words no mark can be shown on: an element with `display: contents` generates no
    box, and the runtime hangs a mark on the boxes it shows through instead. `#veiled`
    has one; `#ghost` has none, which reached a user as `d` appearing to do nothing.
    TINY_BOXES cannot take this reading, since checkVisibility() is false for an
    element with no box.

    A scrolled box, which the runtime scrolls to bring an anchor into view, is read
    from its content rather than from rects that say where it is scrolled to; the
    stand-in `primed` holds the scroll each frame for the whole of the gate's read.
    A right-margin resident would shift the column and carry the left-margin floats
    off the window, so the clipped sidenote stands on the container-clip page."""
    fixed = """
<style>
#fixed-margin { position: fixed; top: 80px; left: 24px; width: 150px; }
#fixed-half { position: fixed; top: 500px; left: 180px; width: 180px; }
@media (max-width: 1199px) {
  #fixed-margin, #fixed-half { display: none; }
}
</style>
<div id="fixed-margin">A stable route in the margin.</div>
<div id="fixed-half">A route crossing into the argument.</div>
"""
    source = LONG_PAGE.replace(
        "</main>",
        "".join(
            _added(page)
            for page in (
                SPILLING_PAGE,
                FLOATING_PAGE,
                UNMARKABLE_PAGE,
                SCROLLED_CONTAINER.replace("width: 900px", "width: 100%"),
            )
        )
        + fixed
        + "</main>",
    )

    def scroll_it(page):
        page.add_init_script(
            "addEventListener('DOMContentLoaded', () => {"
            "  const hold = () => {"
            "    const box = document.getElementById('rolled');"
            "    const content = document.getElementById('riding');"
            "    if (content) content.style.width = '900px';"
            "    if (box) box.scrollLeft = 400;"
            "    requestAnimationFrame(hold);"
            "  };"
            "  hold();"
            "});"
        )

    url = serve(source)
    failures = render_gate_model.render_version(
        primed(browser, scroll_it), url
    ).failures

    def reported(code, at):
        return [f for f in failures if f.code == code and f.at == at]

    def naming(*words):
        return [f for f in failures if names(f, *words)]

    assert reported("past-column", "<div id=too-wide>"), failures
    assert not [f for f in failures if f.code == "page-scrolls"], (
        "the window absorbed it, which is what leaves the column reading the only one "
        f"that sees it: {failures}"
    )
    assert reported("past-column", "<div id=half-out>"), failures
    assert not naming("in-the-margin", "logical"), (
        "a float whose own margin carried it clear of the column is where it meant to be"
    )
    assert not naming("inner-word"), (
        "a resident's own words were named for standing where their parent put them"
    )
    assert [
        f
        for f in reported("clipped-out", "<div id=off-window>")
        if f.values["container"] == "<root scrollport>"
    ], (
        f"a float carried off the edge of the window went out with the handover: {failures}"
    )
    assert not naming("fixed-margin"), (
        f"the fixed margin resident was reported for standing where it was put: {failures}"
    )
    assert reported("past-column", "<div id=fixed-half>"), (
        f"a fixed box crossing the column escaped the gate: {failures}"
    )
    assert reported("unmarkable", "<div id=ghost>"), (
        f"the gate said nothing about words no mark can be shown on: {failures}"
    )
    assert not naming("veiled", "seen"), (
        "a wrapper whose words are in a box of their own is what every suggestion is, "
        f"and the gate reported it: {failures}"
    )
    assert not naming("riding", "rolled"), (
        f"a scrolled box was read as having lost what it was scrolled past: {failures}"
    )


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


def test_a_breakout_takes_the_rooms_width_unless_the_page_sizes_it(browser, serve):
    """A breakout's margins move it out past its holder and its width is the room's,
    so an iframe granted `wide` covers the prose evenly where it had collapsed to its
    borders at the room's left edge. A page rule sizing it keeps the margins and
    replaces the width: the frame stood out in the left margin and stopped short of
    the prose's right edge, and the gate read it as clean. A width past the prose's
    edge but short of the room is off the axis too, and a room inside a scroller is
    read inside its scrollbar gutter, which a styled scrollbar keeps classic headless. The reading asks only of a
    box the margins grew that the user can see: a positioned frame is placed by its
    own offsets, and its parent is not what holds it. A link around a frame holds it
    no more than a wrapper drawing no box does, so the room is read past the link."""
    source = leaf_page(
        "Sized breakouts",
        """
<h1>Sized breakouts</h1>
<style>.sized { width: 100%; }</style>
<p id="prose">Prose sets the column the frames break out of.</p>
<iframe id="granted" title="Granted" data-width="wide" style="display: block"></iframe>
<iframe id="sized" class="sized" title="Sized" data-width="wide" style="display: block"></iframe>
<iframe id="wider" title="Wider" data-width="wide" style="display: block; width: 130%"></iframe>
<a href="#prose"><iframe id="linked" title="Linked" data-width="wide" style="display: block"></iframe></a>
<style>#gutter::-webkit-scrollbar { width: 15px; height: 15px; }</style>
<div id="gutter" style="overflow: scroll; scrollbar-gutter: stable">
  <iframe id="guttered" title="Guttered" data-width="wide" style="display: block"></iframe>
</div>
<iframe id="unseen" class="sized" title="Unseen" data-width="wide"
  style="display: block; opacity: 0"></iframe>
<div style="position: relative; height: 160px"><div style="width: 50%; margin-left: 25%">
  <iframe id="placed" title="Placed" data-width="wide"
    style="position: absolute; left: 0; width: 50%"></iframe>
</div></div>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    at = page.evaluate("""() => Object.fromEntries(['prose', 'granted'].map(id => {
      const b = document.getElementById(id).getBoundingClientRect();
      return [id, {left: b.left, right: b.right}];
    }))""")
    misplaced = render_checks_model.evaluate_probe(page, "misplacedBoxes")
    page.close()

    grown = at["prose"]["left"] - at["granted"]["left"]
    assert grown > 100, at
    assert at["granted"]["right"] - at["prose"]["right"] == pytest.approx(grown, abs=1)
    off = [m["at"] for m in misplaced if m["code"] == "off-axis"]
    assert off == ["<iframe id=sized>", "<iframe id=wider>"], misplaced


def test_an_ask_spanning_its_block_is_a_breakout(browser, serve):
    """An Ask allocated the column spans the wide block it holds, so its ring goes round
    the block, and the gate named it as set out in the margin on every page with one.
    The theme says which boxes it lets stand past their holders, so the gate reads the
    Ask as the breakout it is, and a page width that moves it off the block is named,
    as for any breakout. A box padded or sized past the
    column without that leave is named, whether or not it paints there or a breakout
    fills it."""
    ask = """<lf-ask id="{id}"><h2>Which one?</h2>
  <figure data-width="wide"><p>Evidence the room holds.</p></figure>
  <lf-options id="{id}-o" choose><lf-option id="{id}-a">This one</lf-option></lf-options>
</lf-ask>"""
    source = leaf_page(
        "Reaching past the column",
        f"""
<h1>Reaching past the column</h1>
<style>#sized-ask {{ max-width: 36rem; }}</style>
<p>Prose sets the column.</p>
{ask.format(id="ask")}
{ask.format(id="sized-ask")}
<div id="bare" style="margin: 0 -120px; padding: 0 120px; text-indent: -120px">Out.</div>
<div id="tinted" style="margin: 0 -120px; padding: 0 120px; background: #eee">Tint.</div>
<div id="sized" style="width: calc(100% + 120px); background: #eee; --lf-block-frame: 1">
  <figure data-width="wide"><p>Evidence that fills the box.</p></figure>
</div>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    grown = page.evaluate("""() => {
      const ask = document.getElementById('ask').getBoundingClientRect();
      const prose = document.querySelector('main > p').getBoundingClientRect();
      return prose.left - ask.left;
    }""")
    misplaced = render_checks_model.evaluate_probe(page, "misplacedBoxes")
    page.close()

    assert grown > 100, "the Ask never spanned its block, so nothing here was tested"
    found = sorted((m["code"], m["at"]) for m in misplaced)
    assert found == [
        ("off-axis", "<lf-ask id=sized-ask>"),
        ("past-column", "<div id=bare>"),
        ("past-column", "<div id=sized>"),
        ("past-column", "<div id=tinted>"),
    ], misplaced


def test_a_change_level_with_a_note_is_decided_on_the_change(browser, serve):
    """Both residents of the right margin stand level with what they belong to — the
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
        const row = document.querySelector("[data-lf-margin-for='sug-level']");
        const n = note.getBoundingClientRect(), b = row.getBoundingClientRect();
        return {float: getComputedStyle(note).float, place: row.dataset.lfPlace,
                across: Math.min(n.right, b.right) - Math.max(n.left, b.left),
                down: Math.min(n.bottom, b.bottom) - Math.max(n.top, b.top)};
    }"""
    level = page.evaluate(geometry)
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    page.close()

    assert level["float"] == "right", (
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
    hangs out of the flow is answered for, and one standing in the flow is a resident
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
<section id="comparison">
  <h2>Compare, Variants, and Chips</h2>
  <aside class="sidenote" id="compare-note">The page puts short alternatives in a row
  and longer explanations below. Narrow the window to see this note return to the text
  flow.</aside>
  <p id="compare-guide">Ordinary sections compare alternatives. Small labels carry their
  attributes.</p>
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
)


@pytest.mark.parametrize("pointer", ["mouse", "touch", "touch-cancel"])
def test_dragging_an_edge_preserves_user_state(browser, serve, pointer):
    """Resizing owns its gesture, leaving drafts, selections, and arrow keys intact.

    On the right edge, the one that leaves the page live beside it: the left one's Leaves
    drawer covers the page, so there is no draft or selection beside it to keep."""
    edge = EDGES[0]
    context = browser.new_context(
        viewport={"width": 1400, "height": 900}, has_touch=pointer != "mouse"
    )
    page = open_page(
        browser, serve(edge.html(), comments=edge.comments), context=context
    )
    edge.stand(page)
    edge_settled(page, edge)
    handle = page.locator(f"{edge.region} .lf-edge")
    cdp = context.new_cdp_session(page) if pointer != "mouse" else None

    def drag():
        box = handle.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        dx = -40 if edge.side == "right" else 40
        before = geometry(page, edge)["width"]
        if pointer == "mouse":
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + dx, y, steps=8)
        else:
            for event, at in [("touchStart", x), ("touchMove", x + dx)]:
                cdp.send(
                    "Input.dispatchTouchEvent",
                    {"type": event, "touchPoints": [{"x": at, "y": y}]},
                )
        if pointer == "mouse":
            # A pointer drag leaves the existing keyboard focus in place.
            assert handle.evaluate(
                "e => e.matches(':focus') && e.hasAttribute('data-lf-focus')"
            )
            assert handle.evaluate("e => getComputedStyle(e).outlineStyle") == "solid"
        else:
            assert handle.evaluate("e => getComputedStyle(e).outlineStyle") == "none"
        if pointer == "mouse":
            page.mouse.up()
            assert not handle.evaluate("e => e.matches(':focus-visible')")
        else:
            cdp.send(
                "Input.dispatchTouchEvent",
                {
                    "type": "touchCancel" if pointer == "touch-cancel" else "touchEnd",
                    "touchPoints": [],
                },
            )
        assert handle.evaluate("e => e === document.activeElement")
        assert geometry(page, edge)["width"] == before + 40

    handle.focus()
    page.keyboard.press("ArrowRight")
    assert handle.evaluate("e => e.matches(':focus-visible')")
    drag()
    drawn = geometry(page, edge)
    page.keyboard.press("ArrowRight")
    assert handle.evaluate("e => e.matches(':focus-visible')")
    assert geometry(page, edge)["width"] == drawn["width"] + (
        -24 if edge.side == "right" else 24
    )

    page.locator("main p").first.click(modifiers=["Alt"])
    composer = page.locator(".lf-fab-input")
    write(composer, "half a comment")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Shift+ArrowLeft")
    editing = composer.evaluate("""async input => {
        const {captureDraftEditing} = await window.__lfCheckApi();
        return captureDraftEditing(input);
    }""")
    drag()
    expect(composer).to_be_visible()
    expect(composer).to_have_js_property("value", "half a comment")
    composer.focus()
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    # An existing partial-word selection can come from native keyboard selection or
    # browser commands. Only a new selection gesture may expand it to a sentence.
    paragraph = page.locator("main p").nth(1)
    paragraph.evaluate(
        "p => getSelection().setBaseAndExtent(p.firstChild, 3, p.firstChild, 14)"
    )
    selected = page.evaluate("() => getSelection().toString()")
    assert selected == paragraph.evaluate("p => p.firstChild.textContent.slice(3, 14)")
    drag()
    assert (
        page.evaluate("""async () => {
        await new Promise(resolve => setTimeout(resolve));
        return getSelection().toString();
    }""")
        == selected
    )
    rendered(page)
    expect(composer).to_be_hidden()
    assert (
        json.loads(stored_draft_text(page, editing["context"]))["text"]
        == "half a comment"
    )
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(composer).to_be_focused()
    expect(composer).to_have_js_property("value", "half a comment")
    resumed = composer.evaluate("""async input => {
        const {captureDraftEditing} = await window.__lfCheckApi();
        return captureDraftEditing(input);
    }""")
    assert resumed["context"] == editing["context"]
    assert resumed["selection"] == editing["selection"]


@pytest.mark.parametrize("edge", EDGES, ids=EDGE_IDS)
def test_edge_resizing_belongs_to_one_primary_pointer(browser, serve, edge, request):
    """Other buttons, outside presses, and a second touch cannot take a resize."""
    edge_world(request, edge)
    context = browser.new_context(
        viewport={"width": 1400, "height": 900}, has_touch=True
    )
    page = open_page(
        browser, serve(edge.html(), comments=edge.comments), context=context
    )
    edge.stand(page)
    edge_settled(page, edge)
    handle = page.locator(f"{edge.region} .lf-edge")
    box = handle.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    dx = -40 if edge.side == "right" else 40
    before = geometry(page, edge)["width"]

    page.mouse.move(x, y)
    page.mouse.down(button="right")
    page.mouse.move(x + dx, y)
    assert geometry(page, edge)["width"] == before
    page.mouse.up(button="right")

    # A press that starts inside the region, which is open on either edge: past a
    # covering drawer it would land on the scrim, which puts the drawer away.
    page.mouse.move(x + 150 if edge.side == "right" else x - 150, y)
    page.mouse.down()
    page.mouse.move(x, y)
    page.mouse.up()
    assert geometry(page, edge)["width"] == before
    assert not handle.evaluate("e => e === document.activeElement")

    cdp = context.new_cdp_session(page)

    def touch(kind, *points):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": kind,
                "touchPoints": [
                    {"id": pointer_id, "x": at, "y": y} for pointer_id, at in points
                ],
            },
        )

    touch("touchStart", (1, x))
    touch("touchMove", (1, x + dx))
    assert geometry(page, edge)["width"] == before + 40
    second_box = handle.bounding_box()
    second_x = second_box["x"] + second_box["width"] / 2 + 10
    touch("touchStart", (1, x + dx), (2, second_x))
    touch("touchMove", (1, x + dx + dx / 2), (2, second_x))
    page.evaluate("() => new Promise(requestAnimationFrame)")
    assert geometry(page, edge)["width"] == before + 60
    touch("touchEnd", (2, second_x))
    touch("touchMove", (1, x + dx + dx))
    page.evaluate("() => new Promise(requestAnimationFrame)")
    assert geometry(page, edge)["width"] == before + 80
    touch("touchEnd", (1, x + dx + dx))


@pytest.mark.parametrize("edge", EDGES, ids=EDGE_IDS)
def test_a_window_with_no_room_for_a_chosen_width_does_not_un_choose_it(
    browser, serve, edge, request
):
    """A region may take the window and no more, and one that leaves no usable page
    beside it covers the page rather than taking a strip from it. A window that shrinks
    past what the user chose is a window, not a retraction: the user said 580 once, and a
    laptop lid opened narrower is not them saying 500 instead.

    So the choice and the current width are two facts. Clamping the stored one would read
    identically on the narrow window and lose the user's answer for good on the wide one
    they came back to, which is the failure this reading is here to catch — the third
    geometry below is the whole of it."""
    narrow, stands = edge.squeeze
    edge_world(request, edge)
    page = open_page(browser, serve(edge.html(), comments=edge.comments))
    edge.stand(page)
    edge_settled(page, edge)
    draw_edge(page, edge, 160)
    drawn = geometry(page, edge)

    resized(page, narrow, 900)
    squeezed = geometry(page, edge)
    covering = page.locator("html[data-lf-covering-surface]").count()

    resized(page, 1400, 900)
    roomy = geometry(page, edge)
    page.close()

    assert drawn["width"] == edge.wide + 160, f"the drag did not land: {drawn}"
    assert squeezed["width"] == stands, (
        f"a {narrow}px window left the page less than the region took: {squeezed}"
    )
    assert covering, f"a region leaving no page beside it stood beside it: {squeezed}"
    assert squeezed["page"] == (0 if edge.side == "left" else narrow), (
        f"the page yielded a strip to a region covering it: {squeezed}"
    )
    assert squeezed["chosen"] == str(edge.wide + 160), (
        f"the narrow window un-said what the user had said: {squeezed}"
    )
    assert roomy["width"] == edge.wide + 160, (
        f"the width the user chose did not come back with the room for it: {roomy}"
    )


def test_threads_and_the_on_panel_stand_on_the_one_edge_the_user_drew(browser, serve):
    """Threads and the On panel are two views of one side panel, one at a time on the right
    of the window, so the width is the side's rather than either panel's. A user who drew
    the edge out to read a long question has drawn the edge, and finding Threads back at
    its default would be one fact kept in two places — which is what a width per panel
    would have been, and what the shared property is instead. The handle names the side
    panel it sizes, whichever view stands."""
    page = open_page(browser, serve(ON_PANEL.html(), comments=1))
    ON_PANEL.stand(page)
    edge_settled(page, ON_PANEL)
    handle = page.locator(f"{ON_PANEL.region} .lf-edge")
    expect(handle).to_have_attribute("aria-label", "Side panel width")
    draw_edge(page, ON_PANEL, 160)
    drawn = geometry(page, ON_PANEL)

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    threads = EDGES[0]
    edge_settled(page, threads)
    expect(page.locator(ON_PANEL.region)).to_be_hidden()
    expect(page.locator(f"{threads.region} .lf-edge")).to_have_attribute(
        "aria-label", "Side panel width"
    )
    panel = geometry(page, threads)
    page.close()

    assert drawn["width"] == ON_PANEL.wide + 160, f"the drag did not land: {drawn}"
    assert panel["width"] == drawn["width"], (
        f"Threads came up at a width the user had already moved: {panel}"
    )


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
    runtime_import = 'import { once } from "/runtime/widget-api.js";'
    assert source.count(runtime_import) == 1
    source = source.replace(
        runtime_import,
        runtime_import + '\nimport { label } from "./callout-label.js";',
    )
    once = "      if (!once(this)) return;"
    assert source.count(once) == 1
    module.write_text(
        source.replace(once, "      if (once(this)) this.dataset.helper = label;")
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
    thread's title, so a page whose log carries only widget events opens the
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    # The control. A thread's own box draws its inset, and a first block reserving a
    # margin against a neighbour it hasn't got is exactly what the reading names.
    # Weighted, because the layer's own rules are scoped to .lf-chrome and @scope
    # proximity settles a tie an equal selector would otherwise lose here.
    page.evaluate(
        """() => {
             const s = document.createElement('style');
             s.id = 'trap';
             s.textContent =
               '.lf-thread { padding-top: 8px !important }'
               + '.lf-thread > .lf-thread-summary { margin-block-start: 9px !important }';
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


def test_thread_content_keeps_spacing_with_or_without_quote(browser, serve):
    example = next(path for path in EXAMPLES if path.stem == "ship-review")
    page = open_page(browser, serve(example))
    page.locator(".lf-threads-toggle").click()
    gap = """el => {
      const content = el.querySelector(':scope > .lf-thread-content');
      const transcript = content.querySelector(':scope > .lf-thread-transcript');
      const head = content.querySelector(':scope > .lf-thread-head');
      return transcript.getBoundingClientRect().top -
        (head || content).getBoundingClientRect()[head ? 'bottom' : 'top'];
    }"""
    quoted = page.locator('.lf-thread-compact[data-id="7b3e0a41"]')
    assert quoted.evaluate(gap) == 12
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-kind="status"][data-filter-value="resolved"]').click()
    card = page.locator('.lf-thread-compact[data-id="5a81c093"]')
    card.locator(":scope > .lf-thread-summary").click()
    panel_settled(page)
    assert card.evaluate(gap) == 12


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
