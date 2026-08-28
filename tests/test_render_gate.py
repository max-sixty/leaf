"""Browser-gate, arrival, layout, and layer integration tests."""

import itertools
import json
import re
import time

import pytest
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf import schema as schema_model
from leaf.render_gate import scheme as render_gate_scheme
from leaf.render_gate import version as render_gate_model
from leaf.validation import compatibility as validation_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_support import (
    ASK_PAGE,
    ASKS_PAGE,
    AUTHORED_LINES_PAGE,
    BARE_IDENTIFIERS_PAGE,
    BOTH_STAMPS,
    CHANGE_SHAPES_PAGE,
    COLORED_CODE_PAGE,
    COMMAND_HUB_PACKAGE,
    CUSTOM_WIDGET_PAGE,
    EDGE_IDS,
    EDGES,
    EXAMPLES,
    FAINT_CODE_PAGE,
    FLAT_SHADOW_PAGE,
    FLOATING_PAGE,
    IDENTIFIERS_IN_CODE_PAGE,
    LINKED_CELLS_PAGE,
    LONG_PAGE,
    LOOSE_SCROLLER_PAGE,
    NOTE_BESIDE_A_CHANGE,
    OVER_ITS_CONTAINER,
    REPLY_HOST_PAGE,
    RESIZE_LOOP_EVENT,
    ROOM_EVERY_FRAME,
    SCROLLED_CONTAINER,
    SHADOW_CODE_PAGE,
    SHADOW_HOST_PAGE,
    SIDENOTE_IN_A_WIDGET,
    SPILLING_PAGE,
    TINTED_LINE_PAGE,
    UNANSWERED_CODE_PAGE,
    UNMARKABLE_PAGE,
    WIDE_TABLE_PAGE,
    Traffic,
    _traffic,
    _until,
    arrange_return,
    arrival_findings,
    author_test_widget,
    draw_edge,
    edge_settled,
    geometry,
    leaf_page,
    motions,
    moved_at,
    open_page,
    page_at_rest,
    panel_settled,
    primed,
    reader_arrangements,
    resize_notice_after_last_probe,
    resized,
    round_trip,
)

pytestmark = pytest.mark.nightly


def test_a_traffic_wait_stops_when_responses_outlive_its_deadline(monkeypatch):
    """A busy response stream cannot keep a false delivery fact alive forever."""

    class BusyTraffic:
        def settle(self):
            pass

        def __str__(self):
            return "busy"

    class BusyPage:
        lf_traffic = BusyTraffic()

        def wait_for_event(self, *_args, **_kwargs):
            raise AssertionError("the expired wait listened for another response")

    times = iter((0, 31))
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    with pytest.raises(AssertionError, match="never reached a false fact"):
        _until(BusyPage(), lambda _traffic: False, "reached a false fact")


def test_a_broken_probe_module_is_a_gate_finding(browser, serve):
    """A missing public export names the browser boundary instead of raising a traceback."""

    def break_probe(page):
        page.route(
            "**/_leaf/render-checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body='import { missingForTest } from "/runtime/widget-api.js";',
            ),
        )

    failures = render_gate_model.render_version(
        primed(browser, break_probe), serve(LONG_PAGE), served_timeout_ms=500
    )

    assert failures
    assert all("browser probe module failed" in failure for failure in failures)
    assert all("missingForTest" in failure for failure in failures)


def test_an_async_wait_probe_is_refused_instead_of_passing_as_a_promise(browser, serve):
    """A Promise is not a readiness fact, even when JavaScript treats it as truthy."""

    def make_readiness_async(page):
        page.route(
            "**/_leaf/render-checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body="export const runtimeStarted = async () => false;",
            ),
        )

    failures = render_gate_model.render_version(
        primed(browser, make_readiness_async),
        serve(LONG_PAGE),
        served_timeout_ms=500,
    )

    assert failures
    assert all("must be synchronous" in failure for failure in failures)


def test_a_probe_module_that_stops_loading_is_a_gate_finding(browser, serve):
    """The module loader has the gate's deadline even though page.evaluate has none."""
    asked = []

    def hold_probe(page):
        def never_finishes(route):
            asked.append(route.request.url)
            route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body="await new Promise(() => {});",
            )

        page.route("**/_leaf/render-checks/index.js", never_finishes)

    failures = render_gate_model.render_version(
        primed(browser, hold_probe), serve(LONG_PAGE), served_timeout_ms=100
    )

    assert asked, "the probe route was never requested, so no module load stalled"
    assert failures
    assert all("did not load" in failure for failure in failures)
    assert all("within 100ms" in failure for failure in failures)


def test_the_render_gate_waits_for_the_page_to_be_presented(browser, serve):
    """Applied state is not yet a visible page when the first read was slow enough to
    show the recovery sheet. The sheet's animation ends before its minimum dwell does,
    so neither caught-up state nor an empty animation list says the page is available
    to a visual reading. Hold each scheme's first read past the sheet's delay and plant
    syntax the gate can report only after the runtime's presentation stamp releases it.
    """
    delayed = []

    def delay_first_read(page):
        first = True

        def answer(route):
            nonlocal first
            if first:
                first = False
                delayed.append(route.request.url)
                time.sleep(0.05)
            route.continue_()

        page.route("**/api/state*", answer)

    waiting_page = UNANSWERED_CODE_PAGE.replace(
        "</head>",
        "<style>:root { --lf-presentation-delay: 0ms; "
        "--lf-presentation-dwell: 800ms; }</style>\n</head>",
    )
    failures = render_gate_model.render_version(
        primed(browser, delay_first_read), serve(waiting_page)
    )

    assert len(delayed) == 2, "both scheme reads must cross the presentation boundary"
    for scheme in ("light", "dark"):
        assert any(
            failure.startswith(
                f"[{scheme}] code marked cm is the ink of the code around it"
            )
            for failure in failures
        ), (scheme, failures)


def test_a_reload_mid_flight_never_wedges_round_trip(browser, serve):
    """A navigation ends a trip the browser reports for neither kind, and the
    counters must say so or every later wait on this page runs its timeout out.

    Accept-all is how a real sweep gets here: it answers its asks one awaited
    trip at a time, so a reload after the press lands mid-cascade and kills an
    /api/event POST that then produces no `response` and no `requestfailed`.
    The route's delay holds a post in the air so the navigation reliably lands
    on one; the assertion is Traffic's books balancing, and then `round_trip`
    returning on a page whose only unfinished trip ended at the reload."""
    gallery = next(p for p in EXAMPLES if p.stem == "gallery")
    url = serve(gallery.read_text())
    # The console is not the subject here: a reload mid-post leaves Chrome's own
    # "Failed to load resource" behind, which is the navigation working.
    page, _ = open_page(browser, url)

    def slow(route):
        if "/api/event" in route.request.url:
            time.sleep(0.5)
        route.continue_()

    page.route("**/api/event", slow)
    page.locator(".lf-answer-all").first.click()
    page.wait_for_event(
        "request", predicate=lambda r: "/api/event" in r.url, timeout=5000
    )
    page.unroute("**/api/event")
    page.goto(url, wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    t = _traffic(page)
    assert t.acked >= t.sends, (
        f"a trip the navigation ended was never counted: sends={t.sends} "
        f"acked={t.acked}"
    )
    round_trip(page)


def test_every_arrangement_a_reader_can_return_to_is_arrived_in(browser, serve):
    """Every arrangement the layer restores is exercised on one representative page.

    Restoring reader furniture is layer-owned and identical under every authored
    version, so multiplying this reading across the corpus repeats the mechanism rather
    than adding an input. The probe speaks only to a returning reader, and every finding
    here is the arrival pass's. It is held to the arrangements the runtime declares —
    all of them, in order, because a pass that stopped at the first would leave every
    surface after it exactly as unwatched as it was before.
    """

    def prepare(page):
        # At document start, before the page's own scripts, so what is read is what the
        # gate seeded and not what the runtime has since written back over it.
        page.add_init_script(
            "const held = [...Object.keys(localStorage), ...Object.keys(sessionStorage)];"
            "if (held.length) console.error('returned holding ' + held.join());"
        )

    url = serve(LONG_PAGE)
    declared = browser.new_page()
    declared.goto(url, wait_until="load")
    render_checks_model.wait_for_probe(declared, "upgraded")
    arrangements = reader_arrangements(declared)
    declared.close()
    assert len(arrangements) > 1, "the runtime declares nothing to arrive in"

    arrived = [f for f in arrival_findings(primed(browser, prepare), url)]
    assert [f.split("]")[0].lstrip("[") for f in arrived] == [
        a["name"] for a in arrangements
    ]
    # And each was the arrangement it names rather than that one plus everything the
    # reloads before it left standing — a difference no finding could show on its own,
    # since all of them would still be reported, each under a name that had stopped
    # being true. Only the other arrangements' keys are held against an arrival: the
    # page writes its own reading position on the way out of every load, so a store
    # holding that too is a page that departed, not an arrangement that leaked.
    arranged = {a["key"] for a in arrangements}
    for finding, arrangement in zip(arrived, arrangements):
        held = set(finding.split("returned holding ")[1].split(","))
        assert held & arranged == {arrangement["key"]}, finding


def test_a_reader_arrives_at_what_they_left_rather_than_watching_it_arrive(
    browser, serve
):
    """A page put back the way the reader left it is simply there, and does not assemble
    itself in front of them.

    Standing a tray up is a gesture and gestures move: the tray slides in over a fifth
    of a second and the document steps aside to make the room. Coming back to a tray
    that was already standing is not a gesture — nothing was just decided, and a page
    that replays the decisions on arrival would be showing the reader a fifth of a
    second of furniture instead of what they came back to read. The runtime says so in
    two places, and neither had anything holding it: `motion` refuses to animate behind
    the presentation boundary, and `restoreTray` paints the tray without going through
    the opener a press uses. Route the restore through that opener — the natural tidy,
    since it is otherwise two writers of one fact — and the tray slides on every load,
    with every gate here green.

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
    restore is put back, and standing in it is strictly more than catching it.

    What the reader left standing is the arrangement the runtime declares, all of them
    in turn, so a fourth remembered surface is covered the day it starts remembering.
    One thing was caught the day this was written: a panel left open moved the toast
    across the page's foot, because its resting corner is the panel's and the
    stylesheet transitions it there. Invisible, the toast being transparent until it
    speaks — and exactly the shape of the visible one.
    """
    url = serve(CHANGE_SHAPES_PAGE)
    page, errors = open_page(browser, url)
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
        """One load, standing in the arrival rather than catching it as it goes past."""
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
        page.wait_for_function(BOTH_STAMPS)
        # This arrival is complete and the next call navigates away, so no later wait
        # depends on a poll this unroute might strand.
        page.unroute("**/api/state*")
        return moved()

    arrangements = reader_arrangements(page)
    assert len(arrangements) > 1, "the runtime declares nothing to arrive in"

    # The control, and the whole reason the silences below say anything: standing the
    # tray up by hand is the gesture whose motion the arrivals must not have. What it
    # paints is the runtime's business and is not named here; that it paints at all is
    # this reading's, and a reading that reports nothing when something moved would
    # pass every assertion after it.
    page.keyboard.press("a")
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    gesture = moved()
    assert gesture, "a gesture moved nothing the browser reported, so no silence counts"

    page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    first_visit = arrive()

    for arrangement in arrangements:
        arrange_return(page, arrangement)
        extra = {k: v for k, v in arrive().items() if k not in first_visit}
        assert not extra, (
            f"returning to {arrangement['name']} moved what a first visit does not: "
            + "; ".join(f"{k} at {moved_at(cdp, node)}" for k, node in extra.items())
        )
    # A ResizeObserver notice is the render gate's to adjudicate over two attempts on
    # one document; one seen here is the platform under load and says nothing.
    assert [e for e in errors if not render_gate_scheme.resize_observer_error(e)] == []
    page.close()


def test_a_transient_resize_notice_gets_a_complete_confirmation(browser, serve):
    """The notice can arrive on the rendering turn after the gate's last probe. A
    navigation-only confirmation would call the attempt clean, and an immediate close
    would never hear it; the confirmation is the whole two-scheme gate."""
    pages = []

    def prepare(page):
        if len(pages) < 2:  # both pages in the first light-and-dark attempt
            resize_notice_after_last_probe(page)
        pages.append(page)

    failures = render_gate_model.render_version(
        primed(browser, prepare), serve(LONG_PAGE)
    )

    assert failures == []
    assert len(pages) == 4, "the complete gate was not confirmed once"


def test_an_ordinary_error_survives_a_successful_resize_confirmation(browser, serve):
    pages = []

    def prepare(page):
        if not pages:
            page.add_init_script(
                "addEventListener('DOMContentLoaded', () => "
                "console.error('ordinary error from first attempt'), {once: true});"
            )
        if len(pages) < 2:
            resize_notice_after_last_probe(page)
        pages.append(page)

    failures = render_gate_model.render_version(
        primed(browser, prepare), serve(LONG_PAGE)
    )

    assert len(pages) == 4
    assert sum("ordinary error from first attempt" in f for f in failures) == 1


def test_a_recurring_resize_notice_fails_the_render_gate(browser, serve):
    pages = []

    def prepare(page):
        resize_notice_after_last_probe(page)
        pages.append(page)

    failures = render_gate_model.render_version(
        primed(browser, prepare), serve(LONG_PAGE)
    )

    assert len(pages) == 4
    assert (
        render_gate_scheme.recurring_resize_observer_error("render attempt") in failures
    )


def test_an_ordinary_error_survives_an_incomplete_resize_confirmation(browser, serve):
    pages = []

    def prepare(page):
        number = len(pages)
        if number == 0:
            page.add_init_script(
                "addEventListener('DOMContentLoaded', () => "
                "console.error('ordinary error from first attempt'), {once: true});"
            )
            resize_notice_after_last_probe(page)
        elif number >= 2:  # the arrival page, then the confirming attempt's two
            page.set_default_timeout(500)
            page.route("**/leaf.js", lambda route: route.abort())
        pages.append(page)

    failures = render_gate_model.render_version(
        primed(browser, prepare), serve(LONG_PAGE)
    )

    assert any("ordinary error from first attempt" in failure for failure in failures)
    assert any("runtime never injected its banner" in failure for failure in failures)
    assert any(
        "confirming render attempt did not complete" in failure for failure in failures
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
    page, errors = open_page(browser, serve(LONG_PAGE), init_script=first_load_only)

    assert errors == []
    page.evaluate(RESIZE_LOOP_EVENT)
    assert errors == [
        "window error: ResizeObserver loop completed with undelivered notifications."
    ], "a notice after the classified navigation was hidden too"
    page.close()


def test_page_navigation_reports_a_recurring_resize_notice(browser, serve):
    every_load = (
        "addEventListener('DOMContentLoaded', () => {" + RESIZE_LOOP_EVENT + "});"
    )
    page, errors = open_page(browser, serve(LONG_PAGE), init_script=every_load)

    assert errors == [render_gate_scheme.recurring_resize_observer_error("navigation")]
    page.close()


def test_the_render_gate_rejects_an_upgrade_that_defines_no_element(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-callout", upgrade=True)
    module = tmp_path / ".leaf" / "widgets" / "lf-callout.js"
    module.write_text("// Valid JavaScript, but no custom-element definition.\n")

    failures = render_gate_model.render_version(browser, serve(CUSTOM_WIDGET_PAGE))

    assert any(
        "upgraded widgets did not define their elements: <lf-callout>" in failure
        for failure in failures
    )


def test_the_render_gate_requires_a_declared_conversations_host(browser, serve):
    """A conversation declaration whose module omits its host fails visibly.

    The shipped module first proves the gate accepts the real page. The bug-back then
    removes only its conversationBox placement from the vendored module; a fresh browser
    context prevents the clean load's module cache from answering for the changed file."""
    url = serve(ASK_PAGE)
    assert render_gate_model.render_version(browser, url) == []

    module = serve.page_dir / "widgets" / "lf-options.js"
    source = module.read_text()
    placement = """        this.#another = conversationBox(this, ANOTHER);
        if (this.#another) this.append(this.#another);
"""
    assert source.count(placement) == 1
    module.write_text(source.replace(placement, ""))

    failures = render_gate_model.render_version(browser, url)
    assert (
        "[light] <lf-options id='jobs'> declares x-conversation but rendered 0 "
        "matching hosts; its module must place exactly one conversationBox"
    ) in failures


def test_the_render_gate_requires_a_visual_parts_provider(
    browser, serve, tmp_path, monkeypatch
):
    """A part declaration without both browser methods cannot silently fall back.

    The CLI can validate authored tokens without rendering them, so the browser gate
    holds the other half: every matching instance must implement the generic lookup in
    both directions before a page carrying semantic visual anchors can publish.
    """
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-callout", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entries["lf-callout"]["properties"]["parts"] = {
        "type": "string",
        "minLength": 1,
    }
    entries["lf-callout"]["x-visual"] = {"parts": "parts"}
    registry_path.write_text(json.dumps(entries, indent=2))

    failures = render_gate_model.render_version(browser, serve(CUSTOM_WIDGET_PAGE))

    assert any(
        "declares addressable visual parts but its module does not provide "
        "lfVisualPart, lfVisualPartAt" in failure
        for failure in failures
    ), failures


def test_the_render_gate_catches_a_lying_verbatim_and_an_undeclared_shadow_root(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for two module contracts the gate enforces: an entry that says
    x-verbatim while the module renders other words in the body's stead (quotes
    would strand on words the screen no longer shows), and a module attaching a
    shadow root its entry doesn't declare (the passage walk crosses only the
    declared ones, so an undeclared root's words anchor astray)."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-callout", upgrade=True)
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

    failures = render_gate_model.render_version(browser, serve(CUSTOM_WIDGET_PAGE))

    assert any("x-verbatim" in f for f in failures), failures
    assert any("shadow roots the registry doesn't declare" in f for f in failures), (
        failures
    )


def test_the_render_gate_catches_a_declared_word_that_never_reached_the_page(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for the other thing a declaration promises: that the words arrive. Both
    word passes stop at a shadow boundary on purpose — which widgets the page holds is
    the document's question — so an element a module stages into its own tree keeps its
    declarations and gets neither pass, and the failure is silence: no error, no missing
    box, nothing a reading of the drawn page can tell from an attribute with nothing to
    say. Here a project widget stages an <lf-event>, whose entry declares both keys, and
    the gate is asked for each.

    A staged element rather than a module that wipes its own body after the passes have
    run, which is the same failure by the reachable-today route: that one is a race with
    the next poll for the painted half, and a bug-back that has to win a race is a
    bug-back that reports the machine."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-callout", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    # The fixture's x-verbatim claim is about a body this module no longer shows, and
    # the gate says so on its own; declaring the root keeps this test's finding the
    # only one about the tree.
    entries["lf-callout"].pop("x-verbatim")
    entries["lf-callout"]["x-shadow"] = True
    registry_path.write_text(json.dumps(entries, indent=2))
    module = tmp_path / ".leaf" / "widgets" / "lf-callout.js"
    module.write_text(
        'import { once, shadowStage } from "/runtime/widget-api.js";\n'
        "customElements.define(\n"
        '  "lf-callout",\n'
        "  class extends HTMLElement {\n"
        "    connectedCallback() {\n"
        "      if (!once(this)) return;\n"
        '      const staged = document.createElement("lf-event");\n'
        '      staged.id = "staged-event";\n'
        '      staged.setAttribute("at", "09:00");\n'
        '      staged.setAttribute("kind", "failure");\n'
        '      staged.textContent = "The feeder stopped.";\n'
        "      shadowStage(this, [staged]);\n"
        "    }\n"
        "  },\n"
        ");\n"
    )

    failures = render_gate_model.render_version(browser, serve(CUSTOM_WIDGET_PAGE))

    assert any('never says "09:00"' in f for f in failures), failures
    assert any('paints kind="failure" and says nothing' in f for f in failures), (
        failures
    )


def test_the_render_gate_catches_a_shadow_host_whose_own_words_never_render(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for the half a reading of the markup cannot see. `textContent` returns a
    hidden light-DOM span and `querySelector` finds it, so a check written against the
    markup passes on a page whose reader is handed neither word. Asking `says()` for the
    words and a box for the clipped one is what tells the two apart — the layer's own
    reading enters a declared root in the host's stead, and a span rendered nowhere has
    no rects."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-callout", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entry = entries["lf-callout"]
    entry.pop("x-verbatim")  # the module shows a tree of its own, not the body
    entry["x-shadow"] = True
    entry["properties"]["label"] = {"type": "string"}
    entry["properties"]["urgent"] = {"type": "boolean"}
    entry["x-says"] = {"label": "before"}
    entry["x-paints"] = ["urgent"]
    registry_path.write_text(json.dumps(entries, indent=2))
    module = tmp_path / ".leaf" / "widgets" / "lf-callout.js"
    module.write_text(
        'import { once, shadowStage } from "/runtime/widget-api.js";\n'
        "customElements.define(\n"
        '  "lf-callout",\n'
        "  class extends HTMLElement {\n"
        "    connectedCallback() {\n"
        "      if (!once(this)) return;\n"
        '      const stage = document.createElement("p");\n'
        '      stage.textContent = "The feeder stopped overnight.";\n'
        "      shadowStage(this, [stage]);\n"
        "    }\n"
        "  },\n"
        ");\n"
    )

    failures = render_gate_model.render_version(browser, serve(SHADOW_HOST_PAGE))

    assert any('never says "Escalated"' in f for f in failures), failures
    assert any('paints urgent="" and says nothing' in f for f in failures), failures


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_example_renders(browser, serve, example):
    """Every shipped example loads clean and lays out, in both color schemes: no
    fail-soft error box, no console error, every visible widget occupies real
    space, no sideways scroll, no words on screen a selection can't reach. A
    widget that upgrades into a 1x1 box, or a heading painted by a pseudo-element,
    is the shape of failure a static lint cannot see. The invariants live in
    render_gate.version.render_version — the pass `version check --render` runs on
    agent-authored pages — so this sweep also proves the gate a user's page goes through."""
    assert render_gate_model.render_version(browser, serve(example)) == []


def test_every_idiom_in_the_catalog_stands_in_an_example(browser):
    """The sweep above is the corpus's own gate, and an idiom no example holds never
    reaches it: the shape passes every test it has, because it has none. It is the
    floor test_every_widget_in_the_vocabulary_stands_in_an_example is for widgets, and
    the reason it is here rather than beside that one is that an idiom is declared as a
    selector, which only a layout engine can answer.

    Asked of the authored markup and not of the upgraded page, so an idiom stands
    because an example writes it rather than because a widget's own rendering happens
    to match — a `<table>` a module builds demonstrates nothing about the shape an
    author is being pointed at. The gallery is left out for the same reason it is left
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
    idioms = [key for key in registry["$idioms"] if key != "description"]
    assert idioms, "no idioms read — an empty catalog demonstrates itself"
    page = browser.new_page()
    held, invalid = set(), set()
    for example in EXAMPLES:
        if example.stem == "gallery":
            continue
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
    page.close()

    assert not invalid, f"not selectors, so nothing can ask for them: {sorted(invalid)}"
    assert not set(idioms) - held, (
        f"no example holds {', '.join(sorted(set(idioms) - held))}"
        " — see examples/CLAUDE.md"
    )


def test_a_table_too_wide_to_wrap_scrolls_inside_the_column(browser, serve):
    """The theme's answer for a table with more in it than the column holds. Its
    columns hold what is in them, so it takes the measure only when it needs to
    and wraps its cells past that; when even wrapping can't fit it scrolls inside
    itself — like pre, like lf-board — rather than out into the margin
    where a suggestion's controls hang. `width: 100%` had no third case: the
    table spilled, and at this viewport the window is wide enough that nothing
    scrolled to say so."""
    url = serve(WIDE_TABLE_PAGE)
    page, errors = open_page(browser, url)
    measured = page.locator("#sessions").evaluate(
        """(t) => {
        const main = t.closest('main'), pad = parseFloat(getComputedStyle(main).paddingRight);
        const column = main.getBoundingClientRect().right - pad;
        return { past: Math.round(t.getBoundingClientRect().right - column),
                 scrolls: Math.round(t.scrollWidth - t.clientWidth),
                 sideways: document.body.scrollWidth - document.body.clientWidth };
    }"""
    )
    # Where the width went, then that there was width to go anywhere: a table
    # narrow enough to fit satisfies the first of these while proving nothing,
    # and it is the second that says this one was never such a table.
    assert measured["past"] <= 0
    assert measured["scrolls"] > 0, "this table fits, so it proves nothing"
    assert measured["sideways"] == 0
    assert errors == []
    page.close()
    assert render_gate_model.render_version(browser, url) == []


def test_an_identifier_in_a_cell_breaks_rather_than_holding_its_column(browser, serve):
    """The theme's second case, reached by a table that used to fall through to the
    third: a column of test names beside a column of prose. A name is one word to
    the line breaker, and unbreakable it held its column at 583px of the 720px
    measure, squeezed the prose to 118px and a few words a line, and scrolled the
    table 83px sideways for the rest. In <code> it breaks inside its cell where it
    must, and the table fits. The names are longer than any share of the measure a
    column gets, so a name that did not break is a name that fitted by luck rather
    than by the rule, and the test says so."""
    url = serve(IDENTIFIERS_IN_CODE_PAGE)
    page, errors = open_page(browser, url)
    measured = page.locator("#held").evaluate(
        """(t) => {
        const range = document.createRange(), lines = (code) => {
            range.selectNodeContents(code.firstChild);
            return new Set([...range.getClientRects()].map(r => Math.round(r.top))).size;
        };
        return { scrolls: t.scrollWidth - t.clientWidth,
                 broke: [...t.querySelectorAll('td code')].some(c => lines(c) > 1),
                 sideways: document.body.scrollWidth - document.body.clientWidth };
    }"""
    )
    assert measured["scrolls"] == 0, measured
    assert measured["broke"], "every name fitted whole, so the rule was never asked"
    assert measured["sideways"] == 0
    assert errors == []
    page.close()
    assert render_gate_model.render_version(browser, url) == []


def test_the_render_gate_reports_a_table_squeezed_by_what_cannot_break(browser, serve):
    """The same table with its names written bare. Every column of a scrolling table
    is at its longest unbreakable run, so the prose column wrapping beside a name
    that cannot break is the squeeze read off the page, and the finding states the
    widths that carry the diagnosis: the names' column several times the prose's.
    The control is `test_a_table_too_wide_to_wrap_scrolls_inside_the_column`: a
    table that scrolls with nothing left to wrap is the theme's honest third case
    and passes. The table has to scroll before the reading has anything to say, and
    the test says so first: a fixture that fitted CI's fonts by ten pixels left the
    gate silent there, and the silence read as the reading's."""
    url = serve(BARE_IDENTIFIERS_PAGE)
    page, errors = open_page(browser, url)
    scrolls = page.locator("#held").evaluate("(t) => t.scrollWidth - t.clientWidth")
    assert scrolls > 1, "the names fit the measure here, so the reading is never asked"
    assert errors == []
    page.close()
    failures = render_gate_model.render_version(browser, url)

    squeezed = [f for f in failures if "<table id=held> scrolls" in f]
    assert squeezed, failures
    for finding in squeezed:
        widths = dict(re.findall(r'"([^"]+)" wraps at (\d+)px', finding))
        assert {"Mechanism", "Held by"} <= widths.keys(), finding
        assert int(widths["Held by"]) > 3 * int(widths["Mechanism"]), finding
    assert not [f for f in failures if "<table id=held> scrolls" not in f], failures


def test_the_squeeze_reading_sees_a_wrap_between_two_links(browser, serve):
    """A wrap that falls at a node boundary rather than inside a text node: a
    column of owners as links, one word each, in a table eight single-token
    columns hold open. Read node by node it never wraps, and the column stood at
    84px on five lines with the gate green; set at line-height 1, the second
    line's glyph box overlaps the first's, and a reading of line boxes lost it
    again. The table without that column is
    `test_a_table_too_wide_to_wrap_scrolls_inside_the_column`'s, and passes."""
    failures = render_gate_model.render_version(browser, serve(LINKED_CELLS_PAGE))

    squeezed = [f for f in failures if "<table id=sessions> scrolls" in f]
    assert squeezed, failures
    assert all('"Owners" wraps at' in f for f in squeezed), squeezed


def test_a_line_the_author_drew_is_not_a_wrap(browser, serve):
    """Four cells of a table single tokens hold open, each with a line the author
    wrote and nothing wrapped: `value <code>7</code>` on one line (an inline <code>
    is set at 84% and starts 3px lower, so a reading of rect tops called it a wrap
    and told the author to write the <code> they had written), a <br>, a newline
    under <pre>, and words either side of a nested table. A wrap is what goes away
    with soft wrapping turned off, and none of these does."""
    assert render_gate_model.render_version(browser, serve(AUTHORED_LINES_PAGE)) == []


def test_a_comment_on_a_cell_is_not_a_wrap_in_it(browser, serve):
    """The mark pass puts a comment badge in the cell it marks, and the badge is
    two words in `.lf-ui` that wrap in a 33px cell. Read as the cell's words it
    turned this table — single tokens, the theme's honest third case — red the
    moment a reader commented on it. The runtime's words are not the page's.

    The whole gate, rather than this one reading of it: the badge also stood the
    page three hundred pixels wide of itself until the scroller was made to
    contain what it scrolls, and a commented page has nothing left to report."""
    url = serve(WIDE_TABLE_PAGE, anchored=[("sessions", "value_number_7")])

    assert render_gate_model.render_version(browser, url) == []


def test_a_comment_inside_a_scrolling_table_leaves_the_page_its_own_width(
    browser, serve
):
    """The runtime hangs a word clipped to nothing inside the block a comment lands
    on, out of flow so it holds no room. Out of flow with no positioned ancestor is
    positioned against the page, though, and a table scrolling inside itself holds
    its far column three hundred pixels past the window: the cell was there, the
    word was laid out there with it, and the page grew a sideways scrollbar
    carrying the reader to a box nobody can see. The scroller answers for it — a
    box that scrolls contains what it scrolls — so the word keeps the place on its
    own cell that every reading of it expects and the table carries it.

    Asked at both of the table's scroll positions, since the word travels with the
    cell now rather than standing still while the cell moves; and the cell has to
    be off the table's own edge at the first of them, or nothing here could have
    escaped. Then the two things the place is for: the reader who takes the skip
    link, and the gate."""
    url = serve(WIDE_TABLE_PAGE, anchored=[("sessions", "value_number_7")])
    page, errors = open_page(browser, url)
    note = page.locator(".lf-mark-note")
    expect(note).to_have_count(1)
    expect(note).to_have_text("1 comment")

    measured = note.evaluate(
        """(n) => {
        const table = document.querySelector('#sessions');
        const read = () => {
            const word = n.getBoundingClientRect();
            const cell = n.parentElement.getBoundingClientRect();
            const shown = table.getBoundingClientRect();
            return {
                onItsCell: word.left >= Math.floor(cell.left)
                           && word.right <= Math.ceil(cell.right),
                cellShown: cell.left >= Math.floor(shown.left)
                           && cell.right <= Math.ceil(shown.right),
                sideways: document.body.scrollWidth - document.body.clientWidth,
            };
        };
        const out = { holder: n.parentElement.firstChild.data,
                      scrolls: Math.round(table.scrollWidth - table.clientWidth),
                      rest: read() };
        table.scrollLeft = table.scrollWidth;
        out.scrolled = read();
        return out;
    }"""
    )
    assert measured["holder"] == "value_number_7", "the word is on the marked cell"
    assert measured["scrolls"] > 0, "this table fits, so it proves nothing"
    assert not measured["rest"]["cellShown"], (
        "the cell is on screen already, so nothing here could have escaped"
    )
    assert measured["scrolled"]["cellShown"], "the table did not scroll to the cell"
    assert measured["rest"]["onItsCell"] and measured["scrolled"]["onItsCell"], (
        f"the word left the cell it belongs to: {measured}"
    )

    # Reached the way a reader reaches it. `focus()` alone sets :focus and leaves
    # :focus-visible to Chrome's focus modality, which one earlier mouse press flips
    # — the skip link would then be asked for its resting form and the failure would
    # talk about `position` (tests/CLAUDE.md).
    note.evaluate("(n) => n.focus()")
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    reached = note.evaluate(
        """(n) => {
        const r = n.getBoundingClientRect();
        return { held: document.activeElement === n, said: n.textContent,
                 inTheWindow: r.width > 1 && r.left >= 0 && r.right <= innerWidth
                              && r.top >= 0 && r.bottom <= innerHeight };
    }"""
    )
    assert reached == {"held": True, "said": "1 comment", "inTheWindow": True}
    assert errors == []
    page.close()
    assert render_gate_model.render_version(browser, url) == []


def test_the_runtime_holds_a_scroller_the_page_wrote(browser, serve):
    """The table above is the theme's box. A page writes `overflow-x: auto` on a box
    of its own, and a package on a widget's, and the word escapes a static one of
    those the same way. The sweep that gives every scrolling box its tab stop marks
    each static one (reachScrollers), and one theme rule positions the mark — read
    from the composed box, so the page was asked to declare nothing.

    Asked three ways. The containing block itself, through offsetParent, which for
    an out-of-flow box is the positioned ancestor it is laid out against: the
    scroller now, `main` before. The symptom: the page's width, and the word's
    distance from its row's end edge before and after the box scrolls, which a word
    laid out against the page keeps only while the row stands still — at rest that
    word sits at the row's end too, on the page's own account. And the two boxes the
    mark must leave and must reach: a scroller the page positioned itself, which
    holds its own and takes no mark, and a diff's lines, which scroll in a declared
    shadow tree where a document rule does not go."""
    url = serve(LOOSE_SCROLLER_PAGE, anchored=[("far", "wider than the box")])
    page, errors = open_page(browser, url)
    note = page.locator("#far > .lf-mark-note")
    expect(note).to_have_count(1)
    measured = note.evaluate(
        """(n) => {
        const box = document.querySelector('#loose');
        const read = () => {
            const word = n.getBoundingClientRect();
            const row = n.parentElement.getBoundingClientRect();
            return {
                rowAt: row.left, offset: word.left - row.right,
                sideways: document.body.scrollWidth - document.body.clientWidth,
            };
        };
        const mark = (el) => ({
            marked: el.hasAttribute('data-lf-holds'),
            position: getComputedStyle(el).position,
        });
        const out = {
            against: n.offsetParent.id || n.offsetParent.tagName.toLowerCase(),
            scrolls: box.scrollWidth - box.clientWidth,
            loose: mark(box), held: mark(document.querySelector('#held')),
            rest: read(),
        };
        box.scrollLeft = box.scrollWidth;
        out.scrolled = read();
        return out;
    }"""
    )
    assert measured["scrolls"] > 0, "this box fits, so it proves nothing"
    assert measured["against"] == "loose", (
        f"the word is laid out against {measured['against']}, not the box scrolling it"
    )
    assert measured["loose"] == {"marked": True, "position": "relative"}, measured
    assert measured["held"] == {"marked": False, "position": "relative"}, (
        f"a box the page positioned holds its own and takes no mark: {measured}"
    )
    assert (
        measured["rest"]["sideways"] == 0 and measured["scrolled"]["sideways"] == 0
    ), f"the page grew sideways reaching for the word: {measured}"
    assert measured["scrolled"]["rowAt"] < measured["rest"]["rowAt"], (
        f"the box did not scroll: {measured}"
    )
    assert measured["scrolled"]["offset"] == measured["rest"]["offset"], (
        f"the word stood still while its row scrolled: {measured}"
    )
    assert errors == []
    page.close()

    example = next(e for e in EXAMPLES if e.stem == "pr-walkthrough")
    page, errors = open_page(browser, serve(example))
    diffed = page.evaluate(
        """() => [...document.querySelectorAll('lf-diff')].map((d) => {
            const pre = d.shadowRoot.querySelector('pre');
            return { scrolls: getComputedStyle(pre).overflowX,
                     marked: pre.hasAttribute('data-lf-holds'),
                     position: getComputedStyle(pre).position };
        })"""
    )
    assert diffed, "no diff on the page, so nothing here stands in a shadow tree"
    assert all(
        d == {"scrolls": "auto", "marked": True, "position": "relative"} for d in diffed
    ), f"the mark did not reach the diff's lines: {diffed}"
    assert errors == []
    page.close()


def test_the_render_gate_reports_content_set_past_the_column(browser, serve):
    """The reading neither of the gate's older ones can give. The window is the
    wider of the two boxes — 1200px against a 720px column — so content can stand
    out in the margin with the body still not scrolling sideways, and the
    static lint reads pinned pixels, which a vw width is not. The failure names
    the element and how far out it is, because "something overflows" sends its
    reader back to the browser to find out what."""
    failures = render_gate_model.render_version(browser, serve(SPILLING_PAGE))

    assert [
        f
        for f in failures
        if "<div id=too-wide> is set" in f and "px past the column" in f
    ]
    assert not [f for f in failures if "scrolls sideways" in f], (
        "the window absorbed it, which is what leaves this reading the only one that sees it"
    )


def test_the_render_gate_reports_words_no_mark_can_be_shown_on(browser, serve):
    """An element the reader can see and no mark can be drawn on, which the gate reads
    without pressing a key.

    The marks are the ask walk's ring and an element-anchored comment's outline, and both
    need a box. An element with `display: contents` generates none, so its own rect is the
    empty one every rect starts as — zero-sized at the document's origin — and the runtime
    hangs the mark on the boxes the element shows through instead. `#veiled` has one and
    is fine. `#ghost` has none, and there the paint has nowhere to land: this is the fault
    that reached a reader as `n` appearing to do nothing at all, on a page whose remaining
    asks were all suggestions, while the gate rendered it green.

    TINY_BOXES stands next to this reading and cannot take it: `checkVisibility()` is false
    for an element with no box, so it filters out exactly the elements at issue."""
    failures = render_gate_model.render_version(browser, serve(UNMARKABLE_PAGE))

    assert [f for f in failures if "<div id='ghost'>" in f and "no box to mark" in f], (
        f"the gate said nothing about words no mark can be shown on: {failures}"
    )
    assert not [f for f in failures if "veiled" in f or "seen" in f], (
        "a wrapper whose words are in a box of their own is what every suggestion is, "
        f"and the gate reported it: {failures}"
    )


def test_the_render_gate_tells_a_float_in_the_margin_from_one_spilling_out_of_it(
    browser, serve
):
    """What tells a margin resident from a spill is where its box sits: clear of the
    column on the side it floats to, or across the edge it started inside. Both halves
    are load-bearing, and the second is the one a shortcut drops — exempting floats
    outright would retire this check for every element that happens to carry one, and
    the gate reads `position` alone no longer, a sidenote being a float.

    Both readings run up the ancestors, because a resident answers for what it holds. A
    sidenote is prose and carries the code, links and emphasis prose carries; asking
    only the element itself named every one of them as spilling out of a column it was
    never in, which is a handover refused over the words the idiom exists to hold.

    And the side is resolved rather than string-matched: `float` computes to whichever
    of its four values was written, so `inline-start` — the same left edge — read as
    neither 'left' nor 'right' and failed the page for it."""
    failures = render_gate_model.render_version(browser, serve(FLOATING_PAGE))

    assert [
        f
        for f in failures
        if "<div id=half-out> is set" in f and "past the column" in f
    ]
    assert not [f for f in failures if "in-the-margin" in f or "logical" in f], (
        "a float whose own margin carried it clear of the column is where it meant to be"
    )
    assert not [f for f in failures if "inner-word" in f], (
        "a resident's own words were named for standing where their parent put them"
    )
    # Clear of the column and clear of the window with it. Body is the page's scroller
    # and scrollLeft never runs below zero, so the sideways reading is blind to this one
    # and the margin exemption would carry it straight through.
    assert [
        f
        for f in failures
        if "<div id=off-window> is drawn" in f and "outside <body>" in f
    ], "a float carried off the edge of the window went out with the handover"


def test_a_change_may_be_decided_over_the_note_it_stands_level_with(browser, serve):
    """Both residents of the right margin are pinned by the flow — the controls level
    with the change they decide, the note level with the block it annotates — so on a
    page that writes one beside the other, neither can step aside and the controls are
    drawn over the note's first line. That is the arrangement leaf ships, so the gate
    that reads words drawn on words has to let it through, or every page composing the
    two idioms is refused at handover.

    The exemption is the float rather than the control, which is what keeps it from
    swallowing the check it lives in: the same row docks into the flow when it finds no
    room, and a docked row covering a word is a fault again. So the docked reading is
    asserted beside the floating one — a gate that has only ever passed has been tested
    for nothing, and this one is one predicate away from exempting every control there
    is."""
    url = serve(NOTE_BESIDE_A_CHANGE)
    page, errors = open_page(browser, url)
    page.locator("#sug-level").scroll_into_view_if_needed()
    geometry = """() => {
        const note = document.getElementById('level-note').getBoundingClientRect();
        const row = document.querySelector('.lf-sug-actions');
        const b = row.getBoundingClientRect();
        return {position: getComputedStyle(row).position,
                across: Math.min(note.right, b.right) - Math.max(note.left, b.left),
                down: Math.min(note.bottom, b.bottom) - Math.max(note.top, b.top)};
    }"""
    level = page.evaluate(geometry)
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    # The same row, docked: the theme releases the rail below its breakpoint, and the
    # module observes the resulting body geometry on its next layout frame. What the
    # gate asks is the computed position, so narrowing the window is how the other half
    # of the predicate is reached — and the class is the fact that frame states.
    resized(page, 800, 900)
    page.wait_for_function(
        "() => document.querySelector('.lf-sug-actions')"
        ".classList.contains('lf-docked')"
    )
    docked = page.evaluate(geometry)
    page.close()

    assert level["position"] == "absolute", (
        f"the row never hung in the margin, so nothing here was tested: {level}"
    )
    assert level["across"] > 2 and level["down"] > 2, (
        f"the controls and the note never met, so this proves nothing: {level}"
    )
    assert not [f for f in covered if "level-note" in f], (
        f"a change's controls were refused the margin they are decided in: {covered}"
    )
    assert docked["position"] == "static", (
        f"the row stayed out of the flow at a width that docks it: {docked}"
    )
    assert errors == []


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
    page, errors = open_page(browser, serve(covering))
    page.locator("#over").evaluate(
        "element => element.setAttribute('data-lf-offer', '')"
    )
    page.locator("#under").scroll_into_view_if_needed()
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    page.close()
    assert [f for f in covered if "id=under" in f and "id=over" in f], (
        f"a control the page put in the flow covered a paragraph unreported: {covered}"
    )
    assert errors == []


def test_the_render_gate_reports_a_sidenote_a_box_clips_away(browser, serve):
    """A choose group clips its own box, so a note pulled into the page's margin from
    inside one is painted nowhere. Every other reading calls that well — the column
    check excuses a margin resident, checkVisibility() is true of a clipped box so
    screen and print agree, and the copy, which withholds the clip, shows the words the
    live page dropped — so the reader is the only party who loses them, and a reviewer
    proofing the export sees a note that never reached anybody.

    The question is put to every box rather than to floats alone, since the excuse the
    note is claiming — my container took my overflow, so it answers for me — is granted
    to whatever stands inside one. And the boxes that clip are the minority: a section,
    a tab panel and a disclosure all pass a note through to the margin. So the gate
    names the one that doesn't, at handover, to the one party who can still move it."""
    url = serve(SIDENOTE_IN_A_WIDGET)
    page, errors = open_page(browser, url)
    # elementFromPoint answers about the viewport, so the question can only be put to a
    # note that is in it — LONG_PAGE puts this one four thousand pixels down. The group
    # is what gets scrolled to, never the note: `overflow: hidden` refuses a reader and
    # not a script, so scrolling to the clipped element hands the group's own box
    # sideways until the note is inside it, and the test then measures a page it made.
    page.locator("#where").scroll_into_view_if_needed()
    seen = page.evaluate("""() => {
        const n = document.getElementById('boxed-note');
        const b = n.getBoundingClientRect();
        const mid = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
        // The note or something of its own, never an ancestor: a clipped note leaves
        // the point to <body>, which contains it and paints none of it.
        return {painted: !!mid && (n === mid || n.contains(mid)),
                at: mid && mid.tagName};
    }""")
    failures = render_gate_model.render_version(browser, url)
    page.close()

    assert not seen["painted"], (
        f"nothing clipped the note, so this proves nothing about the gate: {seen}"
    )
    assert [
        f
        for f in failures
        if "<aside id=boxed-note> is drawn" in f
        and "outside <lf-options id=where>" in f
    ], f"a note the reader never sees went out with the handover: {failures}"
    assert errors == []


def test_the_render_gate_reports_a_box_its_container_clips_away(browser, serve):
    """A box need not float to be lost. The column reading hands a whole subtree to the
    first ancestor that takes its own overflow, and that container answers for what ran
    out of it only where the reader can still get to it — so the gate asks which kind of
    container it was, of every box rather than of floats alone.

    And asks it of what the container does rather than of its overflow, which is one of
    three ways to draw nothing past an edge: paint containment and content-visibility
    cut a box while overflow computes `visible`. Containment carries the placed case
    too, being what makes a static box the containing block of the box it then cuts —
    the converse of the box hung off `holding`, which is placed out of a clip that never
    held it."""
    failures = render_gate_model.render_version(browser, serve(OVER_ITS_CONTAINER))

    assert [
        f
        for f in failures
        if "<div id=eaten> is drawn" in f and "outside <div id=clipping>" in f
    ], f"a box drawn nowhere went out with the handover: {failures}"
    assert not [f for f in failures if "reachable" in f or "scrolling" in f], (
        "a box the reader scrolls to is where its container means it to be"
    )
    assert not [f for f in failures if "id=hung>" in f and "id=holding>" in f], (
        "a placed box was laid at the door of a static box that never held it"
    )
    assert not [f for f in failures if "id=told>" in f], (
        "a box that marks its own cut was refused for making it"
    )
    assert not [f for f in failures if "foreignobject" in f], (
        "a drawing's own accounting inside its svg read as the page losing words"
    )
    assert [
        f
        for f in failures
        if "<div id=under-border> is drawn" in f and "outside <div id=bordered>" in f
    ], f"a box drawn under a border read as inside it: {failures}"
    assert [
        f
        for f in failures
        if "<div id=over-by-far> is drawn" in f and "outside <div id=inner-box>" in f
    ], f"a 3px loss out of one box hid a 400px loss out of another: {failures}"
    assert [
        f
        for f in failures
        if "<div id=cut-by-paint> is drawn" in f and "outside <div id=contained>" in f
    ], f"a container that cuts by containment answered for nothing: {failures}"


def test_the_render_gate_reads_a_scrolled_container_from_its_content(browser, serve):
    """A scroller's rects say where it is scrolled to, not how far its content reaches,
    and the gate reads a page the reader has already worked: the runtime scrolls a
    board or a table sideways to bring a comment's anchor into view. Read off the rects,
    every box at the content's start then sits left of the container drawing it and
    reports as lost out of a box showing it perfectly — a handover refused over a page
    that is exactly as its author left it.

    The scroll is put on from outside, through the stand-in `primed` supplies, because
    the page's own CSP takes no inline script and the gate opens its own page. It is
    re-applied each frame so it stands for the whole of the gate's read."""

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

    url = serve(SCROLLED_CONTAINER.replace("width: 900px", "width: 100%"))
    failures = render_gate_model.render_version(primed(browser, scroll_it), url)

    assert not [f for f in failures if "riding" in f or "rolled" in f], (
        f"a scrolled box was read as having lost what it was scrolled past: {failures}"
    )


def test_a_page_hands_its_note_strip_back_when_the_panel_takes_the_room(browser, serve):
    """The margin form is granted by a media query, which asks the window — and the
    panel takes 420px off the page's box without the window changing at all. Held
    through that, a 1024px window left this page's column 151px wide and its widest
    widgets painting out past the edge of it. So syncLayout asks the theme's own floor
    of the box instead and says whether the page is cramped, and the strip stands down
    for as long as it is.

    Nothing else can see this posture. `version check --render` and the render sweep
    both open a 1200px window with no panel in it, which is the width the query is
    right at, so the gate that reads a spill is reading the one layout where there
    isn't one.

    Three readings, because each of the other two designs passes one of them. A page
    that never had a note in the margin passes the cramped read on its own; a strip
    released on every open panel, room or no room, passes that one too — and it is the
    third that says no, the room being there on a wide window and the notes staying
    where the reader had them."""
    example = next(p for p in EXAMPLES if p.stem == "design-decision")
    url = serve(example)
    page, errors = open_page(browser, url)
    reading = """() => {
        const note = document.querySelector('aside.sidenote');
        const main = document.querySelector('main'), s = getComputedStyle(main);
        return {float: getComputedStyle(note).float,
                cramped: document.body.hasAttribute('data-lf-cramped'),
                column: Math.round(main.getBoundingClientRect().width
                    - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight))};
    }"""
    roomy = page.evaluate(reading)
    resized(page, 1024, 900)
    page.locator(".lf-comments").click()
    panel_settled(page)
    cramped = page.evaluate(reading)
    misplaced = render_checks_model.evaluate_probe(page, "misplacedBoxes")
    # Wide enough that the panel's 420px still leaves the floor a clear margin rather
    # than the twenty-odd pixels 1600 leaves it: the reading is meant to say the strip
    # survives a window with room for both, not to sit on the boundary and report which
    # side of it this month's --note falls.
    resized(page, 1728, 900)
    wide = page.evaluate(reading)
    page.close()

    assert roomy["float"] == "right", (
        f"no note stood in the margin to begin with, so this proves nothing: {roomy}"
    )
    assert cramped["float"] == "none", (
        f"the strip outlived the room for it: {cramped}, {misplaced}"
    )
    assert misplaced == [], (
        f"content set outside a column the strip had crushed: {misplaced}"
    )
    assert wide["float"] == "right", (
        f"a window wide enough for both moved the notes anyway: {wide}"
    )
    assert errors == []


@pytest.mark.parametrize("edge", EDGES, ids=EDGE_IDS)
def test_the_reader_draws_an_edge_to_the_width_they_want(browser, serve, edge):
    """A conversation about a table wants room a conversation about a sentence does not,
    and a tray of long names wants room a tray of short ones does not; only the reader
    looking at one knows which this is. So each region's edge is a thing they take hold
    of, and the page yields exactly the strip they leave it.

    Both sides of that strip are read, because the failure this is written against does
    not show on either alone: a region that resizes while the page keeps yielding the old
    margin lays out perfectly well, with a band of page underneath it or a band of nothing
    beside it, and either is a width stated twice by two writers who have come apart. They
    are one number here — the property the runtime writes — and the reading is what says
    so.

    Then the same edge from the keyboard, because a reader who is not holding a pointer is
    still reading the same page, and then a reload, because a width set once and lost on
    the next version is a width they would have to set on every revision."""
    page, errors = open_page(browser, serve(edge.html(), comments=edge.comments))
    edge.stand(page)
    edge_settled(page, edge)
    default = geometry(page, edge)

    draw_edge(page, edge, 160)
    drawn = geometry(page, edge)

    # Focus lands on the edge with the drag, so the arrows are live on what the hand was
    # just holding; the press states that in the form a reader without a pointer makes it.
    # Toward the side the region is held to narrows it.
    page.locator(f"{edge.region} .lf-edge").press(
        "ArrowRight" if edge.side == "right" else "ArrowLeft"
    )
    page.wait_for_function("() => document.body.getAnimations().length === 0")
    stepped = geometry(page, edge)

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    edge_settled(page, edge)
    returned = geometry(page, edge)
    page.close()

    assert default["width"] == edge.wide, (
        f"the region did not start at the width a reader who has said nothing gets: "
        f"{default}"
    )
    assert drawn["width"] == edge.wide + 160, (
        f"the edge did not follow the hand: {default} then {drawn}"
    )
    assert drawn["page"] == drawn["edge"], (
        f"the page yielded a strip of its own rather than the one the region took: {drawn}"
    )
    assert drawn["chosen"] == str(edge.wide + 160), (
        f"the reader's width was not kept: {drawn}"
    )
    assert (stepped["width"], stepped["page"]) == (
        drawn["width"] - 24,
        stepped["edge"],
    ), f"the arrow moved something other than the edge and the page with it: {stepped}"
    assert returned["width"] == stepped["width"], (
        f"the width did not survive the reload a version switch makes: {returned}"
    )
    assert errors == []


@pytest.mark.parametrize("edge", EDGES, ids=EDGE_IDS)
def test_a_window_with_no_room_for_a_chosen_width_does_not_un_choose_it(
    browser, serve, edge
):
    """A region may take half of a window it stands beside and no more — the same bargain
    the covering breakpoint strikes one window down, that the page keeps at least what the
    region takes. A window that shrinks past that is a window, not a retraction: the reader
    said 580 once, and a laptop lid opened narrower is not them saying 400 instead.

    So the choice and the standing width are two facts. Clamping the stored one would read
    identically on the narrow window and lose the reader's answer for good on the wide one
    they came back to, which is the failure this reading is here to catch — the third
    geometry below is the whole of it."""
    narrow, stands = edge.squeeze
    page, errors = open_page(browser, serve(edge.html(), comments=edge.comments))
    edge.stand(page)
    edge_settled(page, edge)
    draw_edge(page, edge, 160)
    drawn = geometry(page, edge)

    resized(page, narrow, 900)
    page.wait_for_function("() => document.body.getAnimations().length === 0")
    squeezed = geometry(page, edge)

    resized(page, 1400, 900)
    page.wait_for_function("() => document.body.getAnimations().length === 0")
    roomy = geometry(page, edge)
    page.close()

    assert drawn["width"] == edge.wide + 160, f"the drag did not land: {drawn}"
    assert squeezed["width"] == stands, (
        f"a {narrow}px window left the page less than the region took: {squeezed}"
    )
    assert squeezed["page"] == squeezed["edge"], (
        f"the page yielded a strip the region was not standing in: {squeezed}"
    )
    assert squeezed["chosen"] == str(edge.wide + 160), (
        f"the narrow window un-said what the reader had said: {squeezed}"
    )
    assert roomy["width"] == edge.wide + 160, (
        f"the width the reader chose did not come back with the room for it: {roomy}"
    )
    assert errors == []


def test_both_trays_stand_on_the_one_edge_the_reader_drew(browser, serve, other_leaf):
    """Leaves and asks are the same furniture at two scopes, one at a time on one side of
    the window, so the width is the side's rather than either tray's. A reader who drew
    the edge out to read long names has drawn the edge, and finding the other tray back
    at its default would be one fact kept in two places — which is what a width per tray
    would have been, and what the shared property is instead.

    The `other_leaf` fixture is the whole reason there is a second tray to swap to: a
    tray of one — the page the reader is already on — is not worth a control, so without
    a neighbour `l` is dead."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    trays = EDGES[1]
    trays.stand(page)
    edge_settled(page, trays)
    draw_edge(page, trays, 160)

    page.keyboard.press("l")
    expect(page.locator(".lf-others-panel")).to_be_visible()
    page.wait_for_function(
        "() => document.querySelector('.lf-others-panel').getAnimations().length === 0"
    )
    leaves = page.evaluate(
        "() => document.querySelector('.lf-others-panel').getBoundingClientRect().width"
    )
    page.close()

    assert round(leaves) == trays.wide + 160, (
        f"the second tray came up at a width the reader had already moved: {leaves}"
    )
    assert errors == []


def test_a_tray_that_takes_a_strip_is_counted_against_the_margins_floor(browser, serve):
    """The theme's margin idioms are granted by a media query, which asks the window; what
    they hang in is the page's own box, which is the window less whatever the chrome holds
    of it. The panel's strip was counted there and the tray's was not, so a 1200px window
    with a tray standing granted a sidenote its margin against a 900px page — 84px under
    the floor the theme states, on the most ordinary window there is.

    Read as the veto rather than as a note's position, because the veto is the fact and a
    note is one idiom that spends it: a reading of the note would go on passing the day a
    second idiom stopped asking. Both states, because the attribute standing permanently
    would read the same way here and would cost every wide page its margins."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1200, 900)
    cramped = "() => document.body.hasAttribute('data-lf-cramped')"
    room = page.evaluate(cramped)

    page.keyboard.press("a")
    edge_settled(page, EDGES[1])
    standing = page.evaluate(cramped)

    page.keyboard.press("a")
    expect(page.locator(".lf-asks-panel")).to_be_hidden()
    page.wait_for_function("() => document.body.getAnimations().length === 0")
    given_back = page.evaluate(cramped)
    page.close()

    assert not room, "a 1200px window with no tray was already short of the floor"
    assert standing, (
        "the tray took 300px out of a 1200px page and the margins were granted anyway"
    )
    assert not given_back, "the page kept the veto after the tray gave its strip back"
    assert errors == []


def test_the_room_does_not_flicker_while_a_strip_arrives(browser, serve, other_leaf):
    """The room a wide exhibit may take is the page's box less the strips the chrome
    holds, and for the fifth of a second a strip takes to arrive that box is neither the
    width the page has nor the one it is going to. Written as the box minus the strip the
    margin has not taken yet, the two readings are in different number systems — a client
    box is an integer and a transitioning margin is not — and the sum landed a pixel either
    way on alternate frames.

    A pixel is nothing to look at and the flicker is not the failure. Each flip is a
    relayout of every exhibit on the page, made from inside the observation that asked for
    it, and Chrome answers a loop of those on the window's error channel and nowhere else:
    the first sight of it was a press sweep going red on one example with nothing on screen
    to say why.

    So the reading is of the property rather than of anything laid out from it, and what it
    asks is that the room never returns to a value it has left. That is true of a slide
    both ways — arriving, the room is stated at once and holds; leaving, it grows back
    frame by frame — and it is false the moment two readings disagree by a pixel."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1200, 900)
    page.evaluate(ROOM_EVERY_FRAME, 60)
    page.keyboard.press("a")
    edge_settled(page, EDGES[1])
    page.wait_for_function("() => window.__room.length >= 60")
    trace = page.evaluate("() => window.__room")
    page.close()

    steps = [room for i, room in enumerate(trace) if i == 0 or room != trace[i - 1]]
    assert len(steps) > 1, (
        f"the tray took no room out of the page, so nothing here was measured: {steps}"
    )
    assert len(steps) == len(set(steps)), (
        "the room went back to a width it had already left, which is a relayout of every "
        f"exhibit on the page on alternate frames: {steps}"
    )
    assert errors == []


def test_the_render_gate_reports_code_the_reader_cannot_tell_from_its_block(
    browser, serve
):
    """Colouring code takes the runtime writing a role and the theme answering it, and
    the two meet only in the browser — so a stylesheet that stops answering, or answers
    too faintly, is a page of flat code and no error anywhere. Both failures are one
    question asked of the drawn page: can the reader tell this run of characters from
    the code around it.

    Each goes back as CSS and the gate is watched to fail, the third of them for the
    reading the other two can't distinguish: a role is fine on the block and unreadable
    on the tint one line wears, which a gate taking one colour per role never reaches,
    because the clean line comes first.

    The clean page is asserted to carry the roles first, because a block the tokenizer
    found nothing in passes this gate while proving nothing about it — which is the
    vacuous half of every reading here."""
    page, errors = open_page(browser, serve(COLORED_CODE_PAGE))
    roles = page.evaluate(
        "() => [...new Set([...document.querySelectorAll('[data-lf-syn]')]"
        ".map(s => s.dataset.lfSyn))].sort()"
    )
    page.close()
    assert errors == []
    assert "cm" in roles and len(roles) > 1, (
        f"this block came out {roles}, so it says nothing about a role going unread"
    )
    assert render_gate_model.render_version(browser, serve(COLORED_CODE_PAGE)) == []

    unanswered = render_gate_model.render_version(browser, serve(UNANSWERED_CODE_PAGE))
    assert [
        f
        for f in unanswered
        if f.startswith("[light] code marked cm is the ink of the code around it")
    ], unanswered

    faint = render_gate_model.render_version(browser, serve(FAINT_CODE_PAGE))
    assert [
        f for f in faint if f.startswith("[light] code marked cm reads at 3.3:1")
    ], faint
    assert not [f for f in faint if "code marked st" in f], (
        "only the role the style touched is unread, so the rest name the reading "
        "rather than the rule"
    )

    tinted = render_gate_model.render_version(browser, serve(TINTED_LINE_PAGE))
    assert [
        f for f in tinted if f.startswith("[light] code marked st reads at 1.6:1")
    ], (
        "the reading is of the surface each span is actually set on, not of one "
        f"block colour taken once per role — {tinted}"
    )

    page, errors = open_page(browser, serve(SHADOW_CODE_PAGE))
    where = page.evaluate(
        "() => ({ doc: document.querySelectorAll('[data-lf-syn]').length,"
        " shadow: [...document.querySelectorAll('*')].filter(e => e.shadowRoot)"
        ".flatMap(e => [...e.shadowRoot.querySelectorAll('[data-lf-syn=cm]')]).length })"
    )
    page.close()
    assert errors == []
    assert where["doc"] == 0 and where["shadow"] > 0, (
        "this page has to put its only comment inside a shadow root, or the gate "
        f"passing it says nothing about the boundary — {where}"
    )
    shadowed = render_gate_model.render_version(browser, serve(SHADOW_CODE_PAGE))
    assert [finding for finding in shadowed if "code marked cm" in finding], (
        "a widget that renders the page's words into a shadow root renders code the "
        f"reader still has to read — {shadowed}"
    )
    assert render_gate_model.render_version(browser, serve(FLAT_SHADOW_PAGE)) == [], (
        "with the box's own surface flattened, what is behind the comment is the "
        "page's paper — which is above the host, and reached by climbing out of the "
        "root rather than stopping where parentElement runs out"
    )


def test_a_traffic_wait_accounts_for_the_trip_it_consumes():
    """The waiter may resume before Traffic's ordinary listeners under load."""

    class LateTraffic:
        done = False

        def settle(self):
            pass

        def settle_finished(self, request):
            assert request == "trip"
            self.done = True

        def __str__(self):
            return f"done={self.done}"

    class EarlyPage:
        lf_traffic = LateTraffic()

        def wait_for_event(self, event, **_kwargs):
            assert event == "requestfinished"
            return "trip"

    _until(EarlyPage(), lambda traffic: traffic.done, "accounted for the trip")


def test_traffic_leaves_a_body_the_browser_has_not_finished_handing_over():
    """`Response.json` waits on the finished fact with no deadline of its own, so a
    body read before the browser has one is the single wait here that cannot run out —
    the one that spent a whole CI run's bound and named no test. A response settles
    when its trip finishes and waits in the queue until then."""

    class Request:
        url = "http://page/api/state"

    class Unfinished:
        ok = True
        read = False
        request = Request()

        def json(self):
            self.read = True
            return {"events": []}

    class Page:
        """The page's own event surface, which is all Traffic asks of one."""

        def __init__(self):
            self.listeners = {}

        def on(self, event, handler):
            self.listeners[event] = handler

    page = Page()
    traffic = Traffic(page)
    response = Unfinished()

    page.listeners["response"](response)
    traffic.settle()
    assert not response.read, "a body was read before the browser had all of it"
    assert traffic.heard == 1, "the headers stopped counting as a state answer"

    page.listeners["requestfinished"](response.request)
    traffic.settle()
    assert response.read, "the finished body never settled, so the queue only grows"


def test_a_traffic_wait_accepts_completion_delivered_with_its_timeout():
    """Traffic's own requestfinished listener can settle the trip as the waiter times
    out, so the final reading is taken after the deadline rather than before it."""

    class EdgeTraffic:
        done = False

        def settle(self):
            pass

        def __str__(self):
            return f"done={self.done}"

    class EdgePage:
        lf_traffic = EdgeTraffic()

        def wait_for_event(self, event, **_kwargs):
            assert event == "requestfinished"
            self.lf_traffic.done = True
            raise PlaywrightTimeout("the trip met its deadline")

    _until(EdgePage(), lambda traffic: traffic.done, "accounted for the trip")


def test_an_authored_project_widget_loads_through_the_real_layer(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-callout", upgrade=True)
    widgets = tmp_path / ".leaf" / "widgets"
    (widgets / "callout-label.js").write_text(
        'export const label = "project-owned helper";\n'
    )
    module = widgets / "lf-callout.js"
    module.write_text(
        module.read_text()
        .replace(
            'import { once } from "/runtime/widget-api.js";',
            'import { once } from "/runtime/widget-api.js";\n'
            'import { label } from "./callout-label.js";',
        )
        .replace(
            "if (!once(this)) return;",
            "if (!once(this)) return;\n      this.dataset.helper = label;",
        )
    )

    url = serve(CUSTOM_WIDGET_PAGE)
    page, errors = open_page(browser, url)
    widget = page.locator("#custom-note")
    expect(widget).to_have_attribute("data-lf-done", "1")
    expect(widget).to_have_attribute("data-helper", "project-owned helper")
    assert widget.evaluate(
        "(el) => ({display: getComputedStyle(el).display, "
        "border: getComputedStyle(el).borderTopWidth})"
    ) == {"display": "block", "border": "1px"}
    assert errors == []
    page.close()


def test_the_layer_traps_no_margin_in_the_panel_it_draws(browser, serve):
    """The trapped-margin reading, asked about the layer instead of the page.

    `TRAPPED_MARGINS` is the one render-gate reading that reaches the runtime's own
    chrome: it asks computed styles rather than boxes, and a shut panel's descendants
    carry every style they will carry open, where the box readings beside it see zero
    and stop. So the gate saw the panel and every other geometry reading did not — an
    asymmetry with no principle behind it, and a live hazard on the side the gate saw:
    a margin trapped in leaf's panel would refuse an author's version over markup they
    did not write, cannot edit, and would hear about in the words of a class no page
    has. examples/CLAUDE.md names that failure as the reason a gate reading was moved
    out once already.

    So the gate now takes the document's half and this takes the layer's, off the one
    reading, with the panel open — where a trapped margin is one somebody can see. The
    control comes first: a rule that traps one inside the panel has to be found, or a
    clean result is only a reading that never arrived. A page is served rather than a
    bare fixture because the panel has to be holding something for its boxes to exist,
    and a seeded example is the corpus's own conversation."""
    seeded = [p for p in EXAMPLES if p.with_suffix(".jsonl").exists()]
    assert seeded, "no example ships a log, so the panel would open on nothing"
    page, errors = open_page(browser, serve(seeded[0]))
    resized(page, 1280, 900)
    page.locator(".lf-comments").click()
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
               + '.lf-thread > .lf-quote { margin-block-start: 9px !important }';
             document.head.append(s);
           }"""
    )
    found = render_checks_model.evaluate_probe(page, "trappedMargins")
    planted = [t for t in found if t["chrome"]]
    assert planted, (
        "a margin trapped inside the panel went unreported, so this reading is not "
        "reaching the layer at all and a clean result below would mean nothing"
    )
    # And the gate's half of the same reading, which must not have moved: a margin in
    # leaf's panel is not a finding about the author's page, and reporting it there is
    # what would refuse their version over markup they cannot edit.
    assert [t for t in found if not t["chrome"]] == [], (
        "a margin planted in the layer reached the document's half of this reading, "
        "which is the half `version check --render` refuses a handover over"
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
    assert errors == []
    page.close()


def test_the_gate_replays_a_decision_made_on_a_widget_no_version_holds(browser, serve):
    """`RELATIVE_REPLAYS` applies every standing winner again and asks whether anything
    moved. It had never been pointed at a decision made in the panel.

    A widget an agent sent in a reply is folded by a projection of its own
    (`thread_state`) and replayed into a tree the panel built, and the probe reads
    `standingState`, which returns early when nothing is standing. No page the gate was
    ever run over held an action at all, so it was reporting clean on an empty list.
    The population is therefore asserted before the gate is asked anything.

    Both of the group's verbs stand here, and only one of them can be held to much.
    `choose` declares a record, so replaying it writes a state `shallowSigs` reads and
    a second application that moved anything is a finding. `answer` declares none: the
    Done press writes `aria-pressed` on a control the runtime built, which carries no
    id and is not in that reading. What it is held to here is that a second application
    does not throw, which is the other half of what the probe reports — its absoluteness
    is still nobody's check."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-list",
            "author": "user",
            "revision": 1,
            "text": "What should I carry into the patch?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-list",
            "revision": 1,
            "text": "Tick what belongs and press Done:",
            "markup": (
                '<lf-options id="an-set" choose multiple '
                'label="What should I carry into the patch?">'
                '<lf-option id="an-chase">Chase them monthly</lf-option>'
                '<lf-option id="an-clear">Clear the stall ourselves</lf-option>'
                '<lf-option id="an-say">Say what the spinner is</lf-option>'
                "</lf-options>"
            ),
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "an-set",
            "action": "choose",
            "detail": {"options": ["an-chase", "an-say"]},
        },
    )
    # The Done press. Recordless, and the last word on the group.
    events_model.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "an-set",
            "action": "answer",
            "detail": {},
        },
    )
    # The population first: the probe returns clean for an empty list, which is exactly
    # how a decision made in the panel went unread for as long as it did.
    page, errors = open_page(browser, url)
    resized(page, 1280, 900)
    standing = page.evaluate(
        "async () => (await import('/runtime/widget-api.js')).standingState()"
        ".map((s) => [s.unit, s.action])"
    )
    assert ["an-set", "choose"] in standing and ["an-set", "answer"] in standing, (
        f"the reader's decisions are not among what the runtime hands the gate: "
        f"{standing} — the replay below would be handed nothing and report clean"
    )
    assert errors == []
    page.close()

    assert render_gate_model.render_version(browser, url) == []


TRAP_PAIR_PAGE = leaf_page(
    "trap-pair",
    """
<h1 id="tp-h">Session store</h1>
<section class="tp-inset" id="tp-box">
  <p id="tp-first">Redis, with a signed-cookie fallback for reads.</p>
</section>
""",
)


def test_the_gate_reports_a_trapped_margin_in_the_page_and_not_in_the_layer(
    browser, serve, tmp_path, monkeypatch
):
    """`version check --render` answers for the document it is handed.

    The trapped-margin reading is the only one here that reaches the runtime's own
    chrome, because it asks computed styles and a shut panel's descendants have every
    style they will have open. So one project theme could refuse an author's version
    twice over: once for their own box, which is theirs to fix, and once for leaf's
    thread list, which is not — markup they did not write, cannot edit, and would be
    told about in the words of a class no page of theirs has. On an append-only log
    that is a page that can never publish again.

    One theme states the same trap in both documents here, so the pair differs in
    nothing but which document it is in. The page's must be reported, or this says
    only that the gate found nothing — and the author's box is a <section> against
    the thread list's <div> because findings dedupe per tag and edge, keeping the
    last: as two divs, the layer's finding displaced the author's and the assertion
    that the layer's is absent passed on the page's absence instead."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".leaf").mkdir(exist_ok=True)
    (tmp_path / ".leaf" / "theme.css").write_text(
        "/* the author's own box, drawing an inset its first block reserves against */\n"
        ".tp-inset { padding: 8px }\n"
        ".tp-inset > p { margin-block: 9px }\n"
        "/* and the same shape in the layer's thread list. Weighted, because the\n"
        "   layer scopes its own rules to .lf-chrome and @scope proximity settles a\n"
        "   tie a project's plain selector would otherwise lose. */\n"
        ".lf-thread { padding: 8px !important }\n"
        ".lf-thread > * { margin-block: 9px !important }\n"
    )
    # A comment, so the thread list has a thread to draw and the layer's half of the
    # trap has a box to be trapped in.
    url = serve(TRAP_PAIR_PAGE, anchored=[("tp-first", "signed-cookie fallback")])
    failures = render_gate_model.render_version(browser, url)
    trapped = [f for f in failures if "of inset and shows" in f]
    assert any("tp-inset" in f for f in trapped), (
        "the author's own trapped margin went unreported, so the silence below is "
        f"the gate finding nothing at all: {failures}"
    )
    assert not any("lf-thread" in f for f in trapped), (
        "the gate refused the author's version over a margin in leaf's own thread "
        f"list: {[f for f in trapped if 'lf-thread' in f]}"
    )
