"""Browser-gate, arrival, layout, and layer integration tests."""

import itertools
import json
import re

import pytest
from interact_support import (
    add_test_widget,
)
from leaf import render_checks as render_checks_model
from leaf.render_checks import wait_until_ready
from leaf.render_gate import scheme as render_gate_scheme
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect
from render_cases_interaction import (
    CHANGE_SHAPES_PAGE,
)
from render_cases_layout import (
    BARE_IDENTIFIERS_PAGE,
    DRAWING_CONTROL_LAYER,
    DRAWING_CONTROL_WIDGETS,
    EDGE_IDS,
    EDGES,
    IDENTIFIERS_IN_CODE_PAGE,
    LINKED_CELLS_PAGE,
    LOOSE_SCROLLER_PAGE,
    OVER_ITS_CONTAINER,
    SIDENOTE_IN_A_WIDGET,
    WIDE_TABLE_PAGE,
    apply_restore_case,
    arrival_findings,
    banner_control,
    draw_edge,
    edge_settled,
    edge_world,
    geometry,
    motions,
    moved_at,
    page_at_rest,
    resize_notice_after_last_probe,
    user_view_restore_cases,
)
from render_cases_widgets import (
    TYPED_PARTS_PAGE,
)
from render_harness import (
    CORPUS_SOURCES,
    EXAMPLE_PACKAGES,
    EXAMPLES,
    LONG_PAGE,
    at_rest,
    leaf_page,
    open_page,
    panel_settled,
    plant_quiet_word,
    primed,
    resized,
    root_overflow,
    still_page,
    take_browser_errors,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_gate import (
    BOUNDED_WORKSPACE_PAGE,
    COMPARE_NOTE_PAGE,
    DIAGRAM_FAMILIES,
    DRAWN_LABELS_PAGE,
    EXPECTED_STALL_MS,
    FRAMED_TABLES_PAGE,
    RESIZE_PATH,
    _added,
    held_scroller_findings,
    resize_findings,
    rest_findings,
    scroll_findings,
    surface_findings,
    typed_box_findings,
    unread_syntax,
    unshown_key_findings,
)


def test_a_drawing_fitted_until_its_labels_are_unreadable_gets_advice_and_still_passes(
    browser, serve
):
    """Drawn size decides, and only the fit is advised about: the 9px glyph at its
    natural size is a size the source chose, and words the drawing never paints have
    no drawn size at all. Each shrunk drawing is named once, with the swept widths it
    spans and its smallest label at the narrowest of them: the drawing whose 11px
    labels came out at 5px on the desktop at every width, and the one whose halved
    28px labels read fine on the desktop only where a narrower window takes them
    under 10px. Side by side in one figure, two id-less drawings share the name the
    advice gives them, and each is still told its own smallest label: the one fitted
    from 1600 units as well as the one fitted from 900."""
    compared = """
<figure id="compare">
  <svg class="drawing" viewBox="0 0 900 120" role="img" aria-label="Before">
    <text x="20" y="40">before</text>
  </svg>
  <svg class="drawing" viewBox="0 0 1600 120" role="img" aria-label="After">
    <text x="20" y="40">canary</text>
    <text x="560" y="40">region</text>
    <text x="1100" y="40">global</text>
  </svg>
</figure>
"""
    url = serve(DRAWN_LABELS_PAGE.replace("</main>", compared + "</main>"), packages=())
    page = open_page(browser, url)
    drawn = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('figure')].map(f => {
          const labels = [...f.querySelectorAll('text')].map(t => {
            const m = t.getScreenCTM();
            const set = parseFloat(getComputedStyle(t).fontSize);
            return {set, drawn: set * Math.hypot(m.c, m.d)};
          });
          return [f.id, labels];
        }))"""
    )
    page.close()
    # Each control is clear of the advice for its own reason, so each reason is shown
    # holding: the large labels were shrunk, the natural glyph is under the floor, and
    # the undrawn labels would be as small as the squeezed ones if they were drawn.
    for figure in ("squeezed", "undrawn"):
        assert all(1 <= label["drawn"] < 0.5 * label["set"] for label in drawn[figure])
    assert all(10 < label["drawn"] < label["set"] for label in drawn["large"]), drawn
    assert any(
        label["drawn"] < 10 and abs(label["drawn"] - label["set"]) < 0.01
        for label in drawn["natural"]
    ), drawn

    reading = render_gate_model.render_version(browser, url)

    assert reading.failures == []

    def named(figure):
        return [line for line in reading.advice if f"<figure id={figure}>" in line]

    assert len(reading.advice) == 4, reading.advice
    (squeezed,), (large,) = named("squeezed"), named("large")
    assert squeezed.startswith(
        "at 360–1920px wide <svg> in <figure id=squeezed> draws labels below 10px, "
        "3 at 360px, the smallest ("
    ), squeezed
    assert "from the 11px it was set at" in squeezed, squeezed
    spans = re.match(
        r"at 360–(\d+)px wide <svg> in <figure id=large> draws labels below 10px, "
        r"2 at 360px, the smallest \(.*\) at [\d.]+px from the 28px it was set at",
        large,
    )
    assert spans and 540 <= int(spans[1]) < 1200, large
    compare = named("compare")
    assert len(compare) == 2, reading.advice
    named_compare = "<svg> in <figure id=compare> draws labels below 10px, "
    assert all(named_compare in advice for advice in compare), compare
    assert {re.search(r"\(('\w+')\)", advice)[1] for advice in compare} == {
        "'before'",
        "'canary'",
    }, compare


def test_the_render_gate_reads_content_through_bounded_pane_regions(browser, serve):
    """Pane bounds are real scroll bounds, so content past a pane's first fold remains
    reachable without being exempted from the ordinary geometry checks."""
    assert (
        render_gate_model.render_version(
            browser, serve(BOUNDED_WORKSPACE_PAGE)
        ).failures
        == []
    )


def test_a_broken_probe_module_is_a_gate_finding(browser, serve):
    """A probe module fault names the browser boundary instead of raising a traceback.

    The neighboring stalled-module test owns the short deadline. This test uses the
    gate's default so the module rejection, rather than the driver's timeout, supplies
    the finding.
    """

    def break_probe(page):
        page.route(
            "**/checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body='throw new Error("probe module failed for test");',
            ),
        )

    failures = render_gate_model.render_version(
        primed(browser, break_probe), serve(LONG_PAGE)
    ).failures

    assert failures
    assert all("browser probe module failed" in failure for failure in failures)
    assert all("probe module failed for test" in failure for failure in failures)


def test_an_async_wait_probe_is_refused_instead_of_passing_as_a_promise(browser, serve):
    """A Promise is not a readiness fact, even when JavaScript treats it as truthy."""

    def make_readiness_async(page):
        page.route(
            "**/checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body="export const runtimeStarted = async () => false;",
            ),
        )

    failures = render_gate_model.render_version(
        primed(browser.unwatched, make_readiness_async),
        serve(LONG_PAGE),
        served_timeout_ms=500,
    ).failures

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

        page.route("**/checks/index.js", never_finishes)

    failures = render_gate_model.render_version(
        primed(browser, hold_probe), serve(LONG_PAGE), served_timeout_ms=500
    ).failures

    assert asked, "the probe route was never requested, so no module load stalled"
    assert failures
    assert all("did not load" in failure for failure in failures)
    assert all("within 500ms" in failure for failure in failures)
    assert all('File "' not in failure for failure in failures), failures


@pytest.mark.parametrize("fault", ["exception", "null"])
def test_a_failed_probe_import_keeps_its_original_throw_site(browser, serve, fault):
    thrown = (
        "new TypeError('probe import rejected')" if fault == "exception" else "null"
    )

    def failing_probe(page):
        page.route(
            "**/checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body=f"function loadBrowserProbes() {{ throw {thrown}; }} loadBrowserProbes();",
            ),
        )

    failures = render_gate_model.render_version(
        primed(browser.unwatched, failing_probe),
        serve(LONG_PAGE),
    ).failures
    assert len(failures) == 2, failures
    assert all('File "' not in failure for failure in failures), failures
    if fault == "exception":
        assert all(
            "TypeError: probe import rejected" in failure
            and "loadBrowserProbes" in failure
            and "checks/index.js:" in failure
            for failure in failures
        ), failures
    else:
        assert all(
            "null" in failure and "did not load" not in failure for failure in failures
        ), failures


def test_every_restore_case_a_user_can_return_to_is_arrived_in(browser, serve):
    """Every restore case the layer restores is exercised on one representative page.

    Restoring user furniture is layer-owned and identical under every authored
    version, so multiplying this reading across the corpus repeats the mechanism rather
    than adding an input. The probe speaks only to a returning user, and every finding
    here is the arrival pass's. It is held to the restore cases the runtime declares —
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

    url = serve(
        CHANGE_SHAPES_PAGE,
        events=[
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "sug-rewrite",
                "action": "decide",
                "detail": {"outcome": "accept"},
                "meaning": {
                    "scope": "page",
                    "unit": "sug-rewrite",
                    "depends": ["sug-rewrite"],
                    "answer": None,
                    "state": {
                        "origin": "lf-suggestion",
                        "unit": "widget",
                        "record": None,
                        "creates": None,
                        "report": False,
                        "detail": {
                            "type": "object",
                            "properties": {"outcome": {"enum": ["accept", "reject"]}},
                            "required": ["outcome"],
                            "additionalProperties": False,
                        },
                    },
                },
            }
        ],
    )
    declared = browser.new_page()
    declared.goto(url, wait_until="load")
    wait_until_ready(declared)
    restore_cases = user_view_restore_cases(declared)
    suggestion_state = declared.locator("#sug-rewrite").get_attribute("data-lf-state")
    option_transition = declared.locator("#wait-day").evaluate(
        "element => getComputedStyle(element).transitionProperty"
    )
    declared.close()
    assert len(restore_cases) > 1, "the runtime declares nothing to arrive in"
    assert suggestion_state == "accept"
    assert option_transition == "box-shadow, transform"

    arrived = [f for f in arrival_findings(primed(browser.unwatched, prepare), url)]
    assert [f.split("]")[0].lstrip("[") for f in arrived] == [
        a["name"] for a in restore_cases
    ]
    # And each was the restore case it names rather than that one plus everything the
    # reloads before it left standing — a difference no finding could show on its own,
    # since all of them would still be reported, each under a name that had stopped
    # being true. Only the other restore cases' keys are held against an arrival: the
    # page writes its own reading position on the way out of every load, so a store
    # holding that too is a page that departed, not a restore case that leaked.
    arranged = {a["key"] for a in restore_cases}
    for finding, restore_case in zip(arrived, restore_cases):
        held = set(finding.split("returned holding ")[1].split(","))
        assert held & arranged == {restore_case["key"]}, finding


def test_a_user_arrives_at_what_they_left_rather_than_watching_it_arrive(
    browser, serve
):
    """A page put back the way the user left it is simply there, and does not assemble
    itself in front of them.

    Standing a drawer up is a gesture and gestures move: the drawer slides in over a fifth
    of a second and the document steps aside to make the room. Coming back to a drawer
    that was already standing is not a gesture — nothing was just decided, and a page
    that replays the decisions on arrival would be showing the user a fifth of a
    second of furniture instead of what they came back to read. The auxiliary-surface
    owner passes arrival separately from a gesture, so even a drawer whose first paint
    waits for presentation appears without an opening slide.

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

    What the user left standing is the restore case the runtime declares, all of them
    in turn, so a fourth remembered surface is covered the day it starts remembering.
    """
    url = serve(CHANGE_SHAPES_PAGE)
    page = open_page(browser, url)
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
        wait_until_ready(page)
        # This arrival is complete and the next call navigates away, so no later wait
        # depends on a poll this unroute might strand.
        page.unroute("**/api/state*")
        return moved()

    restore_cases = user_view_restore_cases(page)
    assert len(restore_cases) > 1, "the runtime declares nothing to arrive in"

    # The control, and the whole reason the silences below say anything: standing the
    # drawer up by hand is the gesture whose motion the arrivals must not have. What it
    # paints is the runtime's business and is not named here; that it paints at all is
    # this reading's, and a reading that reports nothing when something moved would
    # pass every assertion after it.
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
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
    # A ResizeObserver notice is the render gate's to adjudicate over two attempts on
    # one document; one seen here is the platform under load and says nothing.
    errors = take_browser_errors(page)
    assert [e for e in errors if not render_gate_scheme.resize_observer_error(e)] == []


def test_a_recurring_resize_notice_fails_the_render_gate(browser, serve):
    """A notice the page raises on the rendering turn after the gate's last probe, in
    every attempt, is heard and confirmed by a second whole four-render attempt, and
    the gate reports it once as recurring. A console warning beside it fails the gate
    once per scheme however many attempts heard it."""
    pages = []

    def prepare(page):
        resize_notice_after_last_probe(page)
        page.add_init_script(
            "addEventListener('DOMContentLoaded', () => "
            "console.warn('authored warning'), {once: true});"
        )
        pages.append(page)

    failures = render_gate_model.render_version(
        primed(browser.unwatched, prepare), serve(LONG_PAGE)
    ).failures

    assert len(pages) == 8
    recurring = [
        failure
        for failure in failures
        if "recurred on the confirming render attempt" in failure
    ]
    assert len(recurring) == 1, failures
    assert recurring[0].startswith("[light]"), recurring
    assert all("ResizeObserver loop" in failure for failure in recurring)
    warnings = [
        failure for failure in failures if "warning: authored warning" in failure
    ]
    assert len(warnings) == 2, failures


def test_the_gate_passes_what_the_renderer_draws(browser, serve):
    """Leaf draws what Mermaid draws, beyond the families its guide documents, and one
    page covers the six diagram types the guide documents with addressable parts.

    State, sequence, class, ER, and XY diagrams draw markup a flowchart never does.
    The whole-page contracts (both palettes, axe, print, export, reachability) are what
    would catch a renderer-specific failure, and the structural types also exercise
    every kind of source id accepted by `parts`: a state diagram's generated markers
    after a comment, authored state ids that resemble those markers, and a class in a
    namespace, whose identity comes from the parser rather than its rendered label.
    The gate reports a source the renderer cannot draw at all (`UNPARSABLE_DIAGRAM`); a
    family it can draw is no failure, whether or not the guide names it.
    """
    extra = (
        """<lf-diagram id="authored-life" parts="node:_start2 node:_end2"><pre>
stateDiagram-v2
  [*] --&gt; _start2
  _start2 --&gt; _end2
  _end2 --&gt; [*]
</pre></lf-diagram>
<lf-diagram id="namespaced" parts="all"><pre>
classDiagram
  namespace Jobs {
    class Job
  }
  Runner --&gt; Job
</pre></lf-diagram>
"""
        + "\n".join(
            f'<lf-diagram id="{name}"><pre>\n{source}\n</pre></lf-diagram>'
            for name, source in DIAGRAM_FAMILIES.items()
        )
        + '\n<lf-diagram id="trend">'
    )
    page = (
        TYPED_PARTS_PAGE.replace(
            "stateDiagram-v2", "%% Release states\nstateDiagram-v2", 1
        )
        .replace(
            "    Fetch --&gt; Build", "    [*] --&gt; Fetch\n    Fetch --&gt; Build", 1
        )
        .replace('<lf-diagram id="trend">', extra, 1)
    )
    url = serve(page)
    assert render_gate_model.render_version(browser, url).failures == []
    drawn = open_page(browser, url)
    assert (
        drawn.locator("#namespaced").evaluate(
            "e => e.visualParts.get('node:Jobs').label"
        )
        == "Jobs"
    )


def test_the_readiness_wait_names_the_stage_a_page_still_owes(browser, serve):
    """An upgraded page whose first state answer is held has replayed nothing, so the
    wait fails there by the runtime's own stage rather than timing out unexplained,
    and passes once the answer lands."""
    page = browser.new_page()
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(serve(LONG_PAGE), wait_until="load")
    render_checks_model.wait_for_probe(page, "upgraded")

    with pytest.raises(render_checks_model.PageNotReady) as unready:
        wait_until_ready(page, timeout_ms=EXPECTED_STALL_MS)
    assert unready.value.stage == "log"
    assert str(unready.value) == (
        f"the runtime never finished replaying the log within {EXPECTED_STALL_MS}ms"
    )

    for route in held:
        route.continue_()
    page.unroute("**/api/state*")
    wait_until_ready(page)


def test_rest_watches_a_frame_created_by_contained_arrival(browser, serve):
    source = leaf_page(
        "Nested arrival",
        '<lf-sample id="sample"><template id="content" data-sample>'
        "<p>Example</p></template></lf-sample>",
    )
    page = still_page(browser, serve(source))
    child = page.frames[1]
    wait_until_ready(child)
    child.evaluate(
        """async () => {
            const {deferredArrival} = await window.__lfRuntimeImport('/runtime/presentation.js');
            deferredArrival(new Promise(resolve => setTimeout(() => {
                const nested = document.createElement('iframe');
                nested.srcdoc = `<body><script>
                    Object.defineProperty(window, 'lfRest', {
                        configurable: true,
                        set(rest) {
                            Object.defineProperty(window, 'lfRest', {
                                value: rest, writable: true, configurable: true
                            });
                            queueMicrotask(() => document.body.setAttribute('data-late', 'yes'));
                        }
                    });
                <\\/script></body>`;
                document.body.append(nested);
                nested.addEventListener('load', resolve, {once: true});
            }, 1000)));
        }"""
    )

    assert any("data-late" in finding for finding in at_rest(page))


@pytest.mark.parametrize("source", CORPUS_SOURCES, ids=lambda p: p.stem)
def test_page_fixture_renders(browser, serve, source):
    """Every shipped example and developer page passes the render gate, and a
    still_page of it comes back from every journey as it was.

    The gate (render_gate.version.render_version) is the pass `page check --render`
    runs on agent-authored pages, so this sweep also proves the gate a user's page
    goes through: in both color schemes, no fail-soft error box, no console warning or
    error, every visible widget occupies real space, no sideways scroll, no words on
    screen a selection can't reach. A widget that upgrades into a 1x1 box, or a
    heading painted by a pseudo-element, is the shape of failure a static lint cannot
    see.

    The still_page then goes through each journey that must leave it as it found it:
    left alone (`rest_findings`), read for framing and the runtime's apparatus,
    scrolled (`scroll_findings`), every surface opened and closed
    (`surface_findings`), resized to a phone's width and back (`resize_findings`), and
    each typed box scrolled away and back (`typed_box_findings`). The page those
    journeys hand back, at the width it opened at, is then read for commands whose
    context keys it never shows (`unshown_key_findings`) and for widgets that hold
    their height (`held_scroller_findings`), which writes it.

    The frame readings must be empty for shipped pages: every box a shipped theme or
    example frames declares its frame, and a row at a frame's edge holds it, so no box
    shows more inset than it draws. The layer's own panel is held open by its own test;
    shut, its boxes misreport. And nothing the runtime adds stands among the elements
    the page wrote, where it would change which child the page's own rules find first,
    last, or next.

    Code the page shows reads at 4.5:1 or better in both schemes, and no widget puts a
    declared label inside a form control, where no selection reaches it. Both are the
    layer's own, the syntax palette and its widget modules, so the suite holds them over
    the shipped pages rather than the gate asking them of every authored one.

    The journeys share one page because each reads only what its own journey changes,
    and the page the journey before handed over is one a reader could have reached.
    Resting reads the untouched page, so it goes first, and the framing readings and
    the scroll want the page as a reader first opens it, so they follow. A resize
    starting narrow needs a page that first painted narrow, so that journey gets a
    page of its own."""
    url = serve(source)
    gate = render_gate_model.render_version(browser, url).failures
    # Reduced motion, which the still_page asks for, also holds the sort film still
    # while the scroll pass measures its writes.
    page = still_page(browser, url, width=RESIZE_PATH[0])
    findings = {
        "render gate": gate,
        "at rest": rest_findings(page),
        "framing": [
            str(finding)
            for probe in ("trappedMargins", "splitEdges")
            for finding in render_checks_model.evaluate_probe(page, probe)
            if not finding["chrome"]
        ],
        "apparatus among authored": [
            str(stray)
            for stray in render_checks_model.evaluate_probe(
                page, "apparatusAmongAuthored"
            )
        ],
        "words in form controls": [
            str(said)
            for said in render_checks_model.evaluate_probe(page, "wordsInFormControls")
        ],
        "scrolled": scroll_findings(page),
        "closed surfaces": surface_findings(page),
        "resized from the widest": resize_findings(page, RESIZE_PATH),
        "typed boxes": typed_box_findings(page),
        "unshown context keys": unshown_key_findings(page, source),
        "held scrollers": held_scroller_findings(page, source),
        # Last on this page: it moves the page through both color schemes.
        "unread syntax": unread_syntax(page),
        "resized from the narrowest": resize_findings(
            still_page(browser, url, width=RESIZE_PATH[-1]), RESIZE_PATH[::-1]
        ),
    }
    failed = {journey: found for journey, found in findings.items() if found}
    assert failed == {}, "\n\n".join(
        f"{journey}:\n" + "\n".join(found) for journey, found in failed.items()
    )


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


def test_a_table_fills_its_declared_allocation_or_frame_and_a_bare_one_keeps_its_content(
    browser, serve
):
    """A table directly in a panel runs its rules to the panel's inner edge, where they
    used to stop short and read as a table cut off. An explicit allocation on the
    table's figure also sizes the painted rows, not just their scrollport. The same
    table with no allocation keeps to what its columns hold, and so does one granted the
    room itself, which is a limit rather than a size: its rows stand where the prose
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
            wideScrolls: wide.scrollWidth - wide.clientWidth,
            wideInside: Math.round(inner(wide.parentElement) - wide.getBoundingClientRect().right),
            codeRatio: parseFloat(getComputedStyle(code).fontSize)
                / parseFloat(getComputedStyle(cell).fontSize),
        };
    }"""
    )
    assert abs(measured["framedShort"]) <= 1, measured
    assert all(abs(short) <= 1 for short in measured["allocated"]), measured
    assert measured["bareShort"] > 100, "the bare table fills its column"
    assert measured["ownShort"] > 100 and measured["ownStart"] == 0, measured
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


def test_the_render_gate_reports_a_table_squeezed_by_what_cannot_break(browser, serve):
    """The same table with its names written bare. Every column of a scrolling table
    is at its longest unbreakable run, so the prose column wrapping beside a name
    that cannot break is the squeeze read off the page, and the finding states the
    widths that carry the diagnosis: the names' column several times the prose's.
    The control is `test_every_table_the_theme_sets_honestly_passes_the_gate`: a
    table that scrolls with nothing left to wrap is the theme's honest third case
    and passes. The table has to scroll before the reading has anything to say, and
    the test says so first: a fixture that fitted CI's fonts by ten pixels left the
    gate silent there, and the silence read as the reading's.

    Beside it, a wrap that falls at a node boundary rather than inside a text node: a
    column of owners as links, one word each, in a table eight single-token columns
    hold open. Read node by node it never wraps, and the column stood at 84px on five
    lines with the gate green; set at line-height 1, the second line's glyph box
    overlaps the first's, and a reading of line boxes lost it again."""
    linked = LINKED_CELLS_PAGE[LINKED_CELLS_PAGE.index('<table id="sessions">') :]
    linked = linked[: linked.index("</table>") + len("</table>")]
    url = serve(BARE_IDENTIFIERS_PAGE.replace("</main>", linked + "</main>"))
    page = open_page(browser, url)
    scrolls = page.locator("#held").evaluate("(t) => t.scrollWidth - t.clientWidth")
    assert scrolls > 1, "the names fit the measure here, so the reading is never asked"
    page.close()
    failures = render_gate_model.render_version(browser, url).failures

    squeezed = [f for f in failures if "<table id=held> scrolls" in f]
    assert squeezed, failures
    for finding in squeezed:
        widths = dict(re.findall(r'"([^"]+)" wraps at (\d+)px', finding))
        assert {"Mechanism", "Held by"} <= widths.keys(), finding
        assert int(widths["Held by"]) > 3 * int(widths["Mechanism"]), finding
    owners = [f for f in failures if "<table id=sessions> scrolls" in f]
    assert owners, failures
    assert all('"Owners" wraps at' in f for f in owners), owners
    assert not [f for f in failures if f not in squeezed + owners], failures


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
    page = open_page(browser, serve(LOOSE_SCROLLER_PAGE))
    note = plant_quiet_word(page, "#far", "wider than the box")
    measured = note.evaluate(
        """(n) => {
        const box = document.querySelector('#loose');
        const mark = (el) => ({
            marked: el.hasAttribute('data-lf-holds'),
            position: getComputedStyle(el).position,
        });
        return {
            against: n.offsetParent.id || n.offsetParent.tagName.toLowerCase(),
            scrolls: box.scrollWidth - box.clientWidth,
            loose: mark(box), held: mark(document.querySelector('#held')),
        };
    }"""
    )
    # At rest, then with the box scrolled to its far end; the page's own width is the
    # gate's reading, taken at each.
    read = """(n, scrolled) => {
        const box = document.querySelector('#loose');
        if (scrolled) box.scrollLeft = box.scrollWidth;
        const word = n.getBoundingClientRect();
        const row = document.getElementById('far').getBoundingClientRect();
        return { rowAt: row.left, offset: word.left - row.right };
    }"""
    for position in ("rest", "scrolled"):
        measured[position] = {
            **note.evaluate(read, position == "scrolled"),
            "sideways": root_overflow(page),
        }
    assert measured["scrolls"] > 0, "this box fits, so it proves nothing"
    assert measured["against"] == "loose", (
        f"the word is laid out against {measured['against']}, not the box scrolling it"
    )
    assert measured["loose"] == {"marked": True, "position": "relative"}, measured
    assert measured["held"] == {
        "marked": False,
        "position": "relative",
    }, f"a box the page positioned holds its own and takes no mark: {measured}"
    assert (
        measured["rest"]["sideways"] == 0 and measured["scrolled"]["sideways"] == 0
    ), f"the page grew sideways reaching for the word: {measured}"
    assert measured["scrolled"]["rowAt"] < measured["rest"]["rowAt"], (
        f"the box did not scroll: {measured}"
    )
    assert measured["scrolled"]["offset"] == measured["rest"]["offset"], (
        f"the word stood still while its row scrolled: {measured}"
    )
    page.close()

    example = next(e for e in EXAMPLES if e.stem == "pr-walkthrough")
    page = open_page(browser, serve(example))
    # The lines a diff has drawn, which is not every diff on the page: the shipped patch
    # stands collapsed and fetches one file when it is asked for, so its shadow tree
    # holds nothing to mark until a user opens one. The floor below is what keeps that
    # from reading as a clean sweep of nothing.
    diffed = page.evaluate(
        """() => [...document.querySelectorAll('lf-diff')]
            .map((d) => d.shadowRoot.querySelector('pre'))
            .filter(Boolean)
            .map((pre) => ({ scrolls: getComputedStyle(pre).overflowX,
                             marked: pre.hasAttribute('data-lf-holds'),
                             position: getComputedStyle(pre).position }))"""
    )
    assert diffed, "no diff drew its lines here, so nothing stands in a shadow tree"
    assert all(
        d == {"scrolls": "auto", "marked": True, "position": "relative"} for d in diffed
    ), f"the mark did not reach the diff's lines: {diffed}"


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


def test_the_render_gate_reports_a_box_its_container_clips_away(browser, serve):
    """A box need not float to be lost. The column reading hands a whole subtree to the
    first ancestor that takes its own overflow, and that container answers for what ran
    out of it only where the user can still get to it — so the gate asks which kind of
    container it was, of every box rather than of floats alone.

    And asks it of what the container does rather than of its overflow, which is one of
    three ways to draw nothing past an edge: paint containment and content-visibility
    cut a box while overflow computes `visible`. Containment carries the placed case
    too, being what makes a static box the containing block of the box it then cuts —
    the converse of the box hung off `holding`, which is placed out of a clip that never
    held it.

    HTML drawings own their clipped internal coordinates just as SVG does. Their
    viewport still belongs to page flow, and offered controls still lose presses
    when clipped, beside a clean control the viewport shows completely.

    A choose group clips its own box too, so a note pulled into the page's margin from
    inside one is painted nowhere. Every other reading calls that well — the column
    check excuses a margin resident, checkVisibility() is true of a clipped box so
    screen and print agree, and the copy, which withholds the clip, shows the words the
    live page dropped — so the user is the only party who loses them. A section, a tab
    panel and a disclosure all pass a note through to the margin, so the gate names the
    box that doesn't, at handover, to the one party who can still move it."""
    url = serve(
        OVER_ITS_CONTAINER.replace("</main>", _added(SIDENOTE_IN_A_WIDGET) + "</main>"),
        layer_registry=DRAWING_CONTROL_LAYER,
        layer_widgets=DRAWING_CONTROL_WIDGETS,
    )
    page = open_page(browser, url)
    expect(page.locator("lf-test-drawing-control [data-lf-offer]")).to_have_count(2)
    expect(page.locator("#clipped-drawing-control")).to_have_text("Inspect")
    expect(page.locator("#clean-drawing-control")).to_have_text("Inspect")
    # elementFromPoint answers about the viewport, so the question can only be put to
    # a note that is in it. The group is what gets scrolled to, never the note:
    # `overflow: hidden` refuses a user and not a script, so scrolling to the clipped
    # element hands the group's own box sideways until the note is inside it.
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
    page.close()
    assert not seen["painted"], (
        f"nothing clipped the note, so this proves nothing about the gate: {seen}"
    )
    failures = render_gate_model.render_version(browser, url).failures

    assert [
        f
        for f in failures
        if "<aside id=boxed-note> is drawn" in f
        and "outside <lf-options id=where>" in f
    ], f"a note the user never sees went out with the handover: {failures}"

    assert [
        f
        for f in failures
        if "<div id=eaten> is drawn" in f and "outside <div id=clipping>" in f
    ], f"a box drawn nowhere went out with the handover: {failures}"
    assert not [f for f in failures if "reachable" in f or "scrolling" in f], (
        "a box the user scrolls to is where its container means it to be"
    )
    assert not [f for f in failures if "id=hung>" in f and "id=holding>" in f], (
        "a placed box was laid at the door of a static box that never held it"
    )
    assert not [f for f in failures if "<span id=told> is drawn" in f], (
        f"a box that marks its own cut was refused for making it: {failures}"
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
    assert not [f for f in failures if "id=drawing-pixels>" in f], failures
    assert [
        f
        for f in failures
        if "<div id=outside-viewport> is drawn" in f
        and "outside <div id=drawing-holder>" in f
    ], f"a drawing viewport escaped its page-flow holder: {failures}"
    assert [
        f
        for f in failures
        if "(#clipped-drawing-control)" in f
        and "page offers a press it does not show" in f
    ], f"the drawing declaration concealed a lost control: {failures}"
    assert not [f for f in failures if "(#clean-drawing-control)" in f], failures


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
        const note = document.querySelector('aside.sidenote');
        const main = document.querySelector('main'), s = getComputedStyle(main);
        return {float: getComputedStyle(note).float,
                column: Math.round(main.getBoundingClientRect().width
                    - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight))};
    }"""
    roomy = page.evaluate(reading)
    resized(page, 1024, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    cramped = page.evaluate(reading)
    misplaced = render_checks_model.evaluate_probe(page, "misplacedBoxes")
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


@pytest.mark.parametrize("edge", EDGES, ids=EDGE_IDS)
def test_the_user_draws_an_edge_to_the_width_they_want(browser, serve, edge, request):
    """A thread about a table wants room a thread about a sentence does not,
    and a drawer of long names wants room a drawer of short ones does not; only the user
    looking at one knows which this is. So each region's edge is a thing they take hold
    of. The region stands over the page, so the page yields nothing at any width.

    Then the same edge from the keyboard, because a user who is not holding a pointer is
    still reading the same page, and then a reload, because a width set once and lost on
    the next version is a width they would have to set on every revision."""
    edge_world(request, edge)
    page = open_page(browser, serve(edge.html(), comments=edge.comments))
    edge.stand(page)
    edge_settled(page, edge)
    default = geometry(page, edge)

    draw_edge(page, edge, 160)
    drawn = geometry(page, edge)

    # Focus lands on the edge with the drag, so the arrows are live on what the hand was
    # just holding; the press states that in the form a user without a pointer makes it.
    # Toward the side the region is held to narrows it.
    page.locator(f"{edge.region} .lf-edge").press(
        "ArrowRight" if edge.side == "right" else "ArrowLeft"
    )
    stepped = geometry(page, edge)

    page.reload(wait_until="load")
    wait_until_ready(page)
    edge_settled(page, edge)
    returned = geometry(page, edge)
    page.close()

    assert default["width"] == edge.wide, (
        f"the region did not start at the width a user who has said nothing gets: "
        f"{default}"
    )
    assert drawn["width"] == edge.wide + 160, (
        f"the edge did not follow the hand: {default} then {drawn}"
    )
    assert drawn["page"] == default["page"], (
        f"the page yielded room to the region: {drawn}"
    )
    assert drawn["chosen"] == str(edge.wide + 160), (
        f"the user's width was not kept: {drawn}"
    )
    assert (stepped["width"], stepped["page"]) == (
        drawn["width"] - 24,
        default["page"],
    ), f"the arrow moved something other than the edge: {stepped}"
    assert returned["width"] == stepped["width"], (
        f"the width did not survive the reload a version switch makes: {returned}"
    )
