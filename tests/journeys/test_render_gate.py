"""Browser-gate, arrival, layout, and layer integration tests."""

import itertools
import json
from html import escape
from urllib.parse import urlsplit

import pytest
from browser.margin.test_entries import _refreshes_restate_no_margin_name
from browser.test_render_gate import (
    BOUNDED_WORKSPACE_PAGE,
    DIAGRAM_FAMILIES,
    DRAWN_LABELS_PAGE,
    EXPECTED_STALL_MS,
    FRAMED_TABLES_PAGE,
    RESIZE_PATH,
    _added,
    adopted_sheet_findings,
    axe_findings,
    held_scroller_findings,
    pressable_paper_findings,
    resize_findings,
    rest_findings,
    scroll_findings,
    short_aim_findings,
    short_aim_findings_in_every_tab,
    surface_findings,
    typed_box_findings,
    unread_syntax,
    unshown_key_findings,
    untouched_resize_findings,
)
from interact_support import (
    add_test_widget,
    append_carried_log_record,
    append_command,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    CHANGE_SHAPES_PAGE,
)
from render_cases_layout import (
    AUTHORED_LINES_PAGE,
    BARE_IDENTIFIERS_PAGE,
    CUSTOM_WIDGET_PAGE,
    CUT_CONTENT,
    DRAWING_CONTROL_LAYER,
    DRAWING_CONTROL_WIDGETS,
    FLOATING_PAGE,
    IDENTIFIERS_IN_CODE_PAGE,
    LINKED_CELLS_PAGE,
    LOOSE_SCROLLER_PAGE,
    OVER_ITS_CONTAINER,
    PHONE_SQUEEZED_TABLE,
    SCROLLED_CONTAINER,
    SHOT_SRC,
    SHOTS,
    SPILLING_PAGE,
    UNMARKABLE_PAGE,
    apply_restore_case,
    arrival_findings,
    motions,
    moved_at,
    page_at_rest,
    resize_notice_after_last_probe,
    toggle_queue,
    user_view_restore_cases,
)
from render_cases_widgets import (
    GENERIC_VISUAL_LAYER,
    TYPED_PARTS_PAGE,
    prefixed_visual_layer,
    visual_widgets,
)
from render_harness import (
    EXAMPLE_PACKAGES,
    INLINE_PAGE,
    LONG_PAGE,
    at_rest,
    leaf_page,
    margins_laid_out,
    names,
    open_page,
    plant_quiet_word,
    primed,
    resized,
    root_overflow,
    still_page,
    take_browser_errors,
)

from leaf.base.files import latest_revision
from leaf.base.findings import Finding
from leaf.pages.page_snapshot import capture_page_snapshot
from leaf.pages.render_gate import scheme as render_gate_scheme
from leaf.pages.render_gate import version as render_gate_model
from leaf.pages.render_gate.preview import preview_server
from leaf.source import render_checks as render_checks_model
from leaf.source.render_checks import rendered, wait_until_ready
from leaf.source.revision_artifact import read_revision
from leaf_dev.browser import chromium_metrics
from leaf_dev.example_data import authored_sources, named_source

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_layer_holds_its_whole_page_rules_on_the_corpus(browser, serve, subtests):
    """The corpus is the page that holds every widget and idiom at once, so the layer's
    whole-page rules are read on it, on one page, in turn.

    First, at 1440px, where the corpus draws the widest margin the examples draw, most
    of it withheld, margin passes that change nothing write nothing and cost the
    browser work bounded by their count, not by the rows they place. The refresh count
    is read first, on the page as it presents: on CI's runner it read 73 layouts for
    five refreshes when it followed the other two passes.

    Back at 1200px, composition preserves markup, not another page's durable versions:
    the gallery's durable-embedding scenario stays hidden and unloaded in the corpus,
    which has no version 2 to embed. The corpus then goes back to its first tab, where
    the adopted sheet decides nothing by standing last (`adopted_sheet_findings`),
    every aim takes a finger (`short_aim_findings`), and paper takes the press off
    everything it cannot press (`pressable_paper_findings`). The touch emulation and
    print media are each put back before the next reading. Last, at 390px, every
    tab's aims are read under a finger again, since a page's own CSS can shrink a
    control only in a narrow window or only in a tab the first view never opens."""
    # The corpus's sort film otherwise repaints SVG values while the sheets move.
    page = open_page(
        browser,
        serve(named_source("corpus")),
        context=browser.new_context(
            viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
        ),
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    # The placement event precedes deferred Reach and chrome work. A measurement
    # starting here would include whatever that previous invalidation still owes.
    rendered(page)
    # Each a subtest, so a failing margin reading leaves the later readings to report.
    with subtests.test(reading="margin refresh count"):
        _refreshes_force_layout_by_refresh_count(page)
    with subtests.test(reading="margin names"):
        _refreshes_restate_no_margin_name(page, {".lf-margin-cluster": 15})
    with subtests.test(reading="margin passes"):
        _layout_passes_batch_without_refolding_controls(page)
    resized(page, 1200, 900)

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
    # Last, because it opens every tab and leaves the corpus on the last of them.
    resized(page, 390, 844)
    findings["phone aims"] = short_aim_findings_in_every_tab(page)
    failed = {reading: found for reading, found in findings.items() if found}
    assert failed == {}, "\n\n".join(
        f"{reading}:\n" + "\n".join(found) for reading, found in failed.items()
    )


def _layout_passes_batch_without_refolding_controls(page):
    """Layout work is bounded by phases, not the number of contributed controls.

    Count the browser's work rather than time;
    the contributor's primary/overflow state must also remain untouched.
    """
    # A placement delivery precedes deferred Reach and chrome paints. Finish the
    # warmup invalidation before recording the work of the five passes below.
    margins_laid_out(page)
    rendered(page)
    with chromium_metrics(page) as metrics:
        before = metrics()
        page.evaluate(
            """async () => {
              const rows = [...document.querySelectorAll('.lf-margin-cluster')];
              const boxes = () => rows.map(row => {
                const {x, y, width, height} = row.getBoundingClientRect();
                return {x, y, width, height};
              });
              const before = boxes();
              // Collected from the callback rather than by `takeRecords` alone:
              // letting a frame settle passes a microtask checkpoint, which delivers
              // the records to the callback and empties the queue a bare
              // `takeRecords` would read.
              const seen = [];
              const observer = new MutationObserver(list => seen.push(...list));
              observer.observe(document.body, {subtree: true, attributes: true,
                attributeFilter: ['data-lf-margin-entry-primary', 'data-lf-margin-entry-overflow']});
              window.__lfFinishMarginPasses = () => {
                const mutations = seen.length + observer.takeRecords().length;
                observer.disconnect();
                delete window.__lfFinishMarginPasses;
                return {before, after: boxes(), mutations};
              };
              for (let i = 0; i < 5; i++) await new Promise(done => {
                document.addEventListener('lf-margin-layout', done, {once: true});
                document.body.dispatchEvent(new CustomEvent('lf-layout', { bubbles: true, composed: true }));
              });
            }"""
        )
        rendered(page)
        reading = page.evaluate("window.__lfFinishMarginPasses()")
        after = metrics()
    assert reading["mutations"] == 0
    assert reading["after"] == reading["before"]
    work = {
        name: after[name] - before[name] for name in ("LayoutCount", "RecalcStyleCount")
    }
    # The current corpus takes 32 style recalculations across five passes with
    # playback stopped; this bound still excludes work proportional to its rows.
    assert all(count <= 35 for count in work.values()), work


def _refreshes_force_layout_by_refresh_count(page):
    """A viewport refresh cannot force layout once per Page Map location."""
    refreshes = 5
    with chromium_metrics(page) as metrics:
        before = metrics()
        page.evaluate(
            """async refreshes => {
              const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
              for (let i = 0; i < refreshes; i++) {
                window.dispatchEvent(new Event('resize'));
                await frame();
              }
            }""",
            refreshes,
        )
        # A frame callback is before ResizeObserver delivery and the rereads it
        # queues. Include the complete work caused by these refreshes before reading
        # the count.
        rendered(page)
        after = metrics()
    work = {
        name: after[name] - before[name]
        for name in (
            "LayoutCount",
            "RecalcStyleCount",
        )
    }
    # These bounds include the browser's viewport bookkeeping while refusing work that
    # scales with every Page Map location.
    assert work["LayoutCount"] <= refreshes * 8, work
    assert work["RecalcStyleCount"] <= refreshes * 30, work


def test_a_drawing_fitted_until_its_labels_are_unreadable_gets_advice_and_still_passes(
    browser, serve
):
    """Drawn size decides, and only the fit is advised about: the 9px glyph at its
    natural size is a size the source chose, and words the drawing never paints have
    no drawn size at all. Each shrunk drawing is named once, with the swept widths it
    spans and its smallest label at the narrowest of them: the drawing whose 11.5px
    labels came out at 5px on the desktop at every width, and the one whose halved
    28px labels read fine on the desktop only where a narrower window takes them
    under 10px. Side by side in one figure, two id-less drawings share the name the
    advice gives them, and each is still told its own smallest label: the one fitted
    from 1600 units as well as the one fitted from 900."""
    compared = """
<figure id="compare">
  <svg class="lf-drawing" viewBox="0 0 900 120" role="img" aria-label="Before">
    <text x="20" y="40">before</text>
  </svg>
  <svg class="lf-drawing" viewBox="0 0 1600 120" role="img" aria-label="After">
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
        return [
            advice
            for advice in reading.advice
            if advice.at == f"<svg> in <figure id={figure}>"
        ]

    assert len(reading.advice) == 4, reading.advice
    assert {advice.code for advice in reading.advice} == {"shrunk-labels"}
    assert {advice.values["threshold"] for advice in reading.advice} == {10}
    (squeezed,), (large,) = named("squeezed"), named("large")
    assert squeezed.widths == (360, 1920), squeezed
    assert (squeezed.values["labels"], squeezed.values["set"]) == (3, 11.5), squeezed
    low, high = large.widths
    assert low == 360 and 540 <= high < 1200, large
    assert (large.values["labels"], large.values["set"]) == (2, 28), large
    compare = named("compare")
    assert len(compare) == 2, reading.advice
    assert {advice.values["words"] for advice in compare} == {
        "before",
        "canary",
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

    # A probe that never loads reads nothing of the page, which the check says
    # beside a passing status, as a host with no browser does.
    failures = render_gate_model.render_version(
        primed(browser, hold_probe), serve(LONG_PAGE), served_timeout_ms=500
    ).findings

    assert asked, "the probe route was never requested, so no module load stalled"
    errors = [failure.values["error"] for failure in failures]
    assert errors
    assert all("did not load" in error and "within 500ms" in error for error in errors)
    assert all('File "' not in error for error in errors), failures


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

    # A probe that fails reads nothing of the page, which the check says beside a
    # passing status, as a host with no browser does.
    failures = render_gate_model.render_version(
        primed(browser.unwatched, failing_probe),
        serve(LONG_PAGE),
    ).findings
    assert len(failures) == 1, failures
    assert {failure.code for failure in failures} == {"probe-failed"}, failures
    # A dynamic import's failure is no page fault. The gate's own wait must not echo it
    # back as one, or its timing would split one finding per render.
    assert all(failure.values["console"] == [] for failure in failures), failures
    errors = [failure.values["error"] for failure in failures]
    assert all('File "' not in error for error in errors), failures
    if fault == "exception":
        assert all(
            "TypeError: probe import rejected" in error
            and "loadBrowserProbes" in error
            and "checks/index.js:" in error
            for error in errors
        ), failures
    else:
        assert all(
            "null" in error and "did not load" not in error for error in errors
        ), failures


def test_a_recurring_resize_notice_fails_the_render_gate(browser, serve):
    """A notice the page raises on the rendering turn after the gate's last probe, in
    every attempt, is heard and confirmed by a second whole attempt, and the gate
    reports it once as recurring. A console warning beside it is advice, reported once
    however many attempts heard it."""
    pages = []

    def prepare(page):
        resize_notice_after_last_probe(page)
        page.add_init_script(
            "addEventListener('DOMContentLoaded', () => "
            "console.warn('authored warning'), {once: true});"
        )
        pages.append(page)

    reading = render_gate_model.render_version(
        primed(browser.unwatched, prepare), serve(LONG_PAGE)
    )
    failures = reading.failures

    assert len(pages) == 2
    recurring = [
        failure
        for failure in failures
        if failure.code == "resize-loop"
        and failure.values.get("confirmation") == "recurred"
    ]
    assert len(recurring) == 1, failures
    assert recurring[0].values["text"].startswith("ResizeObserver loop"), recurring
    warnings = [
        advice
        for advice in reading.advice
        if advice.code == "console-warning"
        and advice.values["text"] == "authored warning"
    ]
    assert len(warnings) == 1, reading.findings


def test_the_gate_passes_what_the_renderer_draws(browser, serve):
    """Leaf draws every family its renderer accepts, beyond those its guide names.

    One page covers the structural diagram types with addressable parts and an XY chart.

    State, sequence, class, ER, and XY diagrams draw markup a flowchart never does.
    The whole-page contracts (the gate, axe, print, export, reachability) are what
    would catch a renderer-specific failure, and the structural types also exercise
    every kind of source id a box is named by: a state diagram's generated markers
    after a comment, authored state ids that resemble those markers, and a class in a
    namespace, whose identity comes from the parser rather than its rendered label.
    The gate reports a source the renderer cannot draw at all (`UNPARSABLE_DIAGRAM`); a
    family it can draw is no failure, whether or not the guide names it.
    """
    extra = (
        """<lf-diagram id="authored-life"><pre>
stateDiagram-v2
  [*] --&gt; _start2
  _start2 --&gt; _end2
  _end2 --&gt; [*]
</pre></lf-diagram>
<lf-diagram id="namespaced"><pre>
classDiagram
  namespace Jobs {
    class Job
  }
  Runner --&gt; Job
</pre></lf-diagram>
<lf-diagram id="quoted-name"><pre>
erDiagram
  "Line Item" ||--o{ ORDER : in
</pre></lf-diagram>
"""
        + "\n".join(
            f'<lf-diagram id="namespace-{mode}"><pre>\n'
            f"---\nconfig:\n  class:\n    hierarchicalNamespaces: {mode}\n---\n"
            "classDiagram\n  namespace Org.Unit {\n    class Job\n  }\n"
            "</pre></lf-diagram>"
            for mode in ("true", "false")
        )
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
    reading = render_gate_model.render_version(browser, serve(page))
    assert reading.failures == []
    # The parts each diagram drew, as the reading keeps them for `page state`.
    drawn = {
        name: {part["id"]: part["label"] for part in visual["parts"]}
        for name, visual in reading.visuals.items()
    }
    assert drawn["namespaced"]["node:Jobs"] == "Jobs"
    assert drawn["quoted-name"]["node:Line%20Item"] == "Line Item"
    assert set(drawn["namespace-true"]) == {"node:Job", "node:Org", "node:Org.Unit"}
    assert set(drawn["namespace-false"]) == {"node:Job", "node:Org.Unit"}


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
            const {afterPresentation} = await window.__lfWidgetApi();
            afterPresentation(() => new Promise(resolve => setTimeout(() => {
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


@pytest.mark.parametrize("source", authored_sources(), ids=lambda p: p.stem)
def test_page_fixture_renders(browser, serve, source):
    """Every shipped example and developer page passes the render gate, and a
    still_page of it comes back from every journey as it was.

    The gate (render_gate.version.render_version) is the pass `page check --render`
    runs on agent-authored pages, served as that command serves it, from a read-only
    capture (`preview_server`), so this sweep also proves the gate a user's page
    goes through: no fail-soft error box, no console warning or
    error, every visible widget occupies real space, no sideways scroll, no unmarkable
    elements or undeclared text nodes under widget chrome. A widget that upgrades into
    a 1x1 box, or a heading hidden from comment anchoring under widget chrome, is the
    shape of failure a static lint cannot see.

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
    the shipped pages rather than the gate asking them of every authored one. Axe
    finds no serious WCAG A/AA violation in either scheme, such as text under 4.5:1, a
    control under 24px with a neighbour too close, or a role holding children it may
    not own, in the page's own styles or in a widget's.

    The journeys share one page because each reads only what its own journey changes,
    and the page the journey before handed over is one a reader could have reached.
    Resting reads the untouched page, so it goes first, and the framing readings want
    the page as a reader first opens it, so they follow. The journeys after them
    compare the page with itself, so every live sample starts before them, since a
    sample starts as it nears the window and stays started. A resize
    starting narrow needs a page that first painted narrow, so that journey gets a
    page of its own, as does a narrowing no one scrolled before
    (`untouched_resize_findings`)."""
    url = serve(source)
    revision = latest_revision(serve.page_dir)
    assert revision is not None
    snapshot = capture_page_snapshot(
        serve.page_dir,
        read_revision(serve.page_dir, revision).document,
        revision,
        url="/",
    )
    with preview_server(serve.page_dir, snapshot) as preview:
        gate = render_gate_model.render_version(browser, preview).failures
    # Reduced motion, which the still_page asks for, also holds the sort film still
    # while the scroll pass measures its writes.
    page = still_page(browser, url, width=RESIZE_PATH[0])
    findings = {
        "render gate": [str(finding) for finding in gate],
        "at rest": rest_findings(page),
        "framing": [
            str(finding)
            for probe in ("trappedMargins", "splitEdges")
            for finding in render_checks_model.evaluate_probe(page, probe)
            if not finding["chrome"]
        ],
        "apparatus among authored": [
            str(Finding.read(stray))
            for stray in render_checks_model.evaluate_probe(
                page, "apparatusAmongAuthored"
            )
        ],
        "words in form controls": [
            str(Finding.read(said))
            for said in render_checks_model.evaluate_probe(page, "wordsInFormControls")
        ],
    }
    # Work the page holds until the reader nears it, such as a live sample's page,
    # stays started once it starts, so the journeys that compare the page with itself
    # start it all first.
    render_checks_model.start_near_work(page)
    findings |= {
        "scrolled": scroll_findings(page),
        "closed surfaces": surface_findings(page),
        "resized from the widest": resize_findings(page, RESIZE_PATH),
        "typed boxes": typed_box_findings(page),
        "unshown context keys": unshown_key_findings(page, source),
        "held scrollers": held_scroller_findings(page, source),
        # Last on this page: these move the page through both color schemes.
        "unread syntax": [
            f"[{scheme}] {finding}" for scheme, finding in unread_syntax(page)
        ],
        "axe": axe_findings(page),
        "resized from the narrowest": resize_findings(
            still_page(browser, url, width=RESIZE_PATH[-1]), RESIZE_PATH[::-1]
        ),
        "narrowed untouched": untouched_resize_findings(
            still_page(browser, url, width=RESIZE_PATH[0])
        ),
    }
    failed = {journey: found for journey, found in findings.items() if found}
    assert failed == {}, "\n\n".join(
        f"{journey}:\n" + "\n".join(found) for journey, found in failed.items()
    )


@pytest.mark.parametrize("source", authored_sources(), ids=lambda p: p.stem)
def test_page_fixture_opens_without_firefox_console_warnings(
    firefox_browser, serve, source
):
    """Firefox says in its console what Chrome never does, such as a `document.write`
    that made it reparse the document, layout forced before the page loaded, or a
    response blocked as opaque. Every page of the corpus, each live sample loaded,
    leaves the console as `firefox_browser` requires: empty."""
    page = open_page(firefox_browser, serve(source))
    # A sample starts its page as it nears the window, so every one starts first.
    render_checks_model.start_near_work(page)
    for sample in page.locator("lf-sample:has(> template[data-sample])").all():
        sample.scroll_into_view_if_needed()
        sample.evaluate(
            """sample => Promise.race([sample.ready, new Promise((_, reject) =>
              setTimeout(() => reject(new Error(`${sample.id} never got ready: ${
                sample.textContent.trim().slice(0, 80)}`)), 60_000))])"""
        )


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
    overlaps the first's, and a reading of line boxes lost it again.

    And a table that fits at 540px and squeezes only on a phone narrower than that,
    which the width sweep finds at the widths it spans.

    Each is advice and refuses nothing: the table still scrolls with every word in
    reach, and the remedy is the author's choice of composition."""
    linked = LINKED_CELLS_PAGE[LINKED_CELLS_PAGE.index('<table id="sessions">') :]
    linked = linked[: linked.index("</table>") + len("</table>")]
    url = serve(
        BARE_IDENTIFIERS_PAGE.replace(
            "</main>", linked + PHONE_SQUEEZED_TABLE + "</main>"
        )
    )
    page = open_page(browser, url)
    scrolls = page.locator("#held").evaluate("(t) => t.scrollWidth - t.clientWidth")
    assert scrolls > 1, "the names fit the measure here, so the reading is never asked"
    options = page.locator("#options")
    for width, fits in ((540, True), (360, False)):
        resized(page, width, 720)
        scrolls = options.evaluate("(t) => t.scrollWidth - t.clientWidth")
        assert (scrolls <= 1) == fits, (width, scrolls)
    page.close()
    reading = render_gate_model.render_version(browser, url)
    advice = reading.advice

    assert reading.failures == [], reading.failures
    assert {a.code for a in advice} == {"squeezed-table"}, advice

    def wrapped(table):
        return [
            {c["heading"]: c["width"] for c in a.values["columns"] if c["wraps"]}
            for a in advice
            if a.at == f"<table id={table}>"
        ]

    squeezed = wrapped("held")
    assert squeezed, advice
    for widths in squeezed:
        assert {"Mechanism", "Held by"} <= widths.keys(), squeezed
        assert widths["Held by"] > 3 * widths["Mechanism"], squeezed
    owners = wrapped("sessions")
    assert owners and all("Owners" in widths for widths in owners), advice
    phone = [a for a in advice if a.at == "<table id=options>"]
    assert phone and all(a.widths is not None and a.widths[0] == 360 for a in phone), (
        advice
    )
    assert len(squeezed) + len(owners) + len(phone) == len(advice), advice


def test_the_runtime_holds_a_declared_scroll_surface(browser, serve):
    """The table above is the theme's box. A page declares a scrolling surface
    and positions a word against it. The shared class holds positioned descendants,
    and reach gives the surface a keyboard stop when it overflows.

    Asked three ways. The containing block itself, through offsetParent, which for
    an out-of-flow box is the positioned ancestor it is laid out against: the
    scroller, not `main`. The symptom: the page's width, and the word's
    distance from its row's end edge before and after the box scrolls, which a word
    laid out against the page keeps only while the row stands still — at rest that
    word sits at the row's end too, on the page's own account. And the two boxes the
    surface must cover: a scroller the page positioned itself and a diff's lines
    in a declared
    shadow tree where a document rule does not go."""
    page = open_page(browser, serve(LOOSE_SCROLLER_PAGE))
    note = plant_quiet_word(page, "#far", "wider than the box")
    measured = note.evaluate(
        """(n) => {
        const box = document.querySelector('#loose');
        const mark = (el) => ({ position: getComputedStyle(el).position });
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
    assert measured["loose"] == {"position": "relative"}, measured
    assert measured["held"] == {"position": "relative"}, measured
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

    example = named_source("pr-walkthrough")
    page = open_page(browser, serve(example))
    # The lines a diff has drawn, which is not every diff on the page: the shipped patch
    # stands collapsed and fetches one file when it is asked for, so its shadow tree
    # holds nothing to mark until a user opens one. The floor below is what keeps that
    # from reading as a clean sweep of nothing.
    diffed = page.evaluate(
        """() => [...document.querySelectorAll('lf-diff')]
            .map((d) => d.shadowRoot.querySelector('.lf-text-scroller'))
            .filter(Boolean)
            .map((box) => ({ scrolls: getComputedStyle(box).overflowX,
                             position: getComputedStyle(box).position }))"""
    )
    assert diffed, "no diff drew its lines here, so nothing stands in a shadow tree"
    assert all(d == {"scrolls": "auto", "position": "relative"} for d in diffed), (
        f"the scroll surface did not contain the diff's lines: {diffed}"
    )


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

    A box's own content has no box to lose, so the box answers for it, down as well as
    across: a log capped by a max-height, a short box of paragraphs and a label that
    does not wrap each cut off what they hold. A bounded log scrolls, a closed
    disclosure draws nothing, a line clamp and an ellipsis mark their cut, a tight line
    box overhangs by less than a line, and words clipped to a pixel for whoever is
    listening show nothing to cut from, so none of those is named."""
    url = serve(
        OVER_ITS_CONTAINER.replace("</main>", CUT_CONTENT + "</main>"),
        layer_registry=DRAWING_CONTROL_LAYER,
        layer_widgets=DRAWING_CONTROL_WIDGETS,
    )
    page = open_page(browser, url)
    expect(page.locator("lf-test-drawing-control [data-lf-offer]")).to_have_count(2)
    expect(page.locator("#clipped-drawing-control")).to_have_text("Inspect")
    expect(page.locator("#clean-drawing-control")).to_have_text("Inspect")
    page.close()
    failures = render_gate_model.render_version(browser, url).failures
    clipped = {
        (f.at, f.values["container"]) for f in failures if f.code == "clipped-out"
    }
    controls = {f.values["id"] for f in failures if f.code == "clipped-control"}

    assert (
        "<div id=eaten>",
        "<div id=clipping>",
    ) in clipped, f"a box drawn nowhere went out with the handover: {failures}"
    assert not [f for f in failures if names(f, "reachable", "scrolling")], (
        "a box the user scrolls to is where its container means it to be"
    )
    assert not [
        f for f in failures if names(f, "id=hung>") and names(f, "id=holding>")
    ], "a placed box was laid at the door of a static box that never held it"
    assert not [f for f in failures if f.at == "<span id=told>"], (
        f"a box that marks its own cut was refused for making it: {failures}"
    )
    assert not [f for f in failures if names(f, "foreignobject")], (
        "a drawing's own accounting inside its svg read as the page losing words"
    )
    assert (
        "<div id=under-border>",
        "<div id=bordered>",
    ) in clipped, f"a box drawn under a border read as inside it: {failures}"
    assert ("<div id=over-by-far>", "<div id=inner-box>") in clipped, (
        f"a 3px loss out of one box hid a 400px loss out of another: {failures}"
    )
    assert ("<div id=cut-by-paint>", "<div id=contained>") in clipped, (
        f"a container that cuts by containment answered for nothing: {failures}"
    )
    assert not [f for f in failures if names(f, "id=drawing-pixels>")], failures
    assert (
        "<div id=outside-viewport>",
        "<div id=drawing-holder>",
    ) in clipped, f"a drawing viewport escaped its page-flow holder: {failures}"
    assert "clipped-drawing-control" in controls, (
        f"the drawing declaration concealed a lost control: {failures}"
    )
    assert "clean-drawing-control" not in controls, failures
    cut = {
        f.at: (f.values["down"], f.values["across"])
        for f in failures
        if f.code == "clipped-content"
    }
    assert cut.get("<pre id=capped-log>", (0, 0))[0] > 500, (
        f"a log cut off at a max-height went out with the handover: {failures}"
    )
    assert cut.get("<div id=short-box>", (0, 0))[0] > 0, failures
    assert cut.get("<div id=unwrapped>", (0, 0))[1] > 0, (
        f"words with no box of their own ran out of their box unnamed: {failures}"
    )
    quiet = {
        "<div id=clipping>",
        "<div id=telling>",
        "<pre id=bounded-log>",
        "<pre id=shut-capped>",
        "<p id=clamped>",
        "<p id=tight-line>",
        "<span id=listening>",
    }
    assert not quiet & cut.keys(), (
        f"a box that cuts on purpose, or one a lost box already names: {failures}"
    )


def test_the_render_gate_reads_one_light_page_at_the_desktop_window(browser, serve):
    """The gate loads the page once, in the light scheme at the desktop window, and a
    page laid out by Leaf's native arrangements passes it."""
    source = leaf_page(
        "native layout in the gate",
        '<aside><div class="layout-track"><nav aria-label="Route"><a href="#move">Move</a></nav></div></aside>'
        '<div class="layout-column"><h1>Migration plan</h1><h2 id="move">Move</h2>'
        "<p>Shift one cohort at a time while keeping the old readers available.</p></div>",
        layout="sidebar",
    )
    seen = []

    def record_page(page):
        viewport = page.viewport_size
        dark = page.evaluate("() => matchMedia('(prefers-color-scheme: dark)').matches")
        seen.append(
            (viewport["width"], viewport["height"], "dark" if dark else "light")
        )

    reading = render_gate_model.render_version(
        primed(browser, record_page), serve(source, packages=())
    )
    assert reading.failures == []
    assert seen == [(1280, 720, "light")]


def test_the_render_gate_requires_a_defined_element(
    browser, serve, tmp_path, monkeypatch
):
    """A project widget declares an upgrade whose module is valid JavaScript and defines
    no element, which the gate names."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    for tag in ("lf-callout", "lf-undefined"):
        add_test_widget(package, tag, upgrade=True)
    (package / "widgets" / "lf-undefined.js").write_text(
        "// Valid JavaScript, but no custom-element definition.\n"
    )
    page = CUSTOM_WIDGET_PAGE.replace(
        "</main>",
        '<lf-undefined id="undefined-note"><strong>Heads up</strong> Never defined.'
        "</lf-undefined>\n</main>",
    )

    failures = render_gate_model.render_version(
        browser, serve(page, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    ).failures

    assert not [f for f in failures if "custom-note" in f.at], failures
    assert any(
        f.code == "missing-upgrades" and f.values["tags"] == ["lf-undefined"]
        for f in failures
    ), failures


def test_the_render_gate_reads_widgets_in_the_page_and_in_replies_alike(
    browser, serve, tmp_path, monkeypatch
):
    """Two contracts the gate holds for a widget wherever it stands, the page or an
    agent's reply in the thread panel, on one page with one reply apiece.

    Generated paint must resolve against the page's live cascade. A missing custom
    property is valid CSS syntax, so a generated SVG silently falls back to black, in
    `lf-paint` on the page and in a reply alike. A fallback is the control: it
    names an absent property but resolves to a shipped color. The
    native SVG is the other control: a gradient reference is valid paint even though
    it is not a color.

    And the replay check reaches a decision made in the panel. `relativeReplays`
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
    add_test_widget(package, "lf-paint", upgrade=True)
    (package / "widgets" / "lf-paint.js").write_text(
        'import { once } from "/runtime/lib/once.js";\n'
        'customElements.define("lf-paint", class extends HTMLElement {\n'
        "  connectedCallback() {\n"
        "    if (!once(this)) return;\n"
        '    this.innerHTML = `<svg width="160" height="80" viewBox="0 0 160 80">\n'
        '      <rect data-id="missing" width="70" height="70" fill="var(--accent-glow)" />\n'
        '      <rect x="80" width="70" height="70" fill="var(--diagram-safe)" />\n'
        "    </svg>`;\n"
        "  }\n"
        "});\n"
    )
    source = leaf_page(
        "widgets in the page and in replies",
        """
<h1 id="title">Widgets in the page and in replies</h1>
<lf-paint id="flow"></lf-paint>
<svg id="gradient" width="20" height="20" viewBox="0 0 20 20">
  <defs><linearGradient id="blue"><stop stop-color="var(--lf-accent)" /></linearGradient></defs>
  <rect width="20" height="20" fill="var(--diagram-gradient)" />
</svg>
""",
        head="""<style>:root {
  --diagram-safe: var(--not-defined, var(--lf-ok-tint));
  --diagram-gradient: url(#blue) var(--lf-accent);
}</style>""",
    )
    url = serve(source, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    replies = {
        "r-paint": '<lf-paint id="sent"></lf-paint>',
        "r-list": (
            '<lf-group id="an-set-decision" label="What should I carry into the patch?"><h3 id="an-set-decision-h">What should I carry into the patch?</h3>'
            '<lf-options id="an-set" multiple>'
            '<lf-option id="an-chase">Chase them monthly</lf-option>'
            '<lf-option id="an-clear">Clear the stall ourselves</lf-option>'
            '<lf-option id="an-say">Say what the spinner is</lf-option>'
            "</lf-options></lf-group>"
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
                "text": f"Here it is:\n\n{markup}",
            },
        )

    user = {"kind": "action", "author": "user", "revision": 1, "widget": "an-set"}
    # The group takes several options, so only its Done answers it.
    choose = {
        "action": "choose",
        "detail": {"value": ["an-chase", "an-say"]},
        "answered": False,
    }
    append_command(serve.page_dir, user | choose)
    # The Done press. Recordless, and the last word on the group.
    append_command(
        serve.page_dir,
        user | {"action": "answer", "detail": {}, "answered": True},
    )
    # The population first: the probe returns clean for an empty list.
    page = open_page(browser, url)
    resized(page, 1280, 900)
    current = page.evaluate(
        "async () => (await window.__lfCheckApi())"
        ".validationWidgetStates().flatMap(({id, state}) =>"
        " Object.values(state).map(current => [id, current.action]))"
    )
    page.close()
    assert ["an-set", "choose"] in current and ["an-set", "answer"] in current, (
        f"the user's decisions are not among what the runtime hands the gate: "
        f"{current} — the replay would be handed nothing and report clean"
    )

    failures = render_gate_model.render_version(browser, url).failures

    assert not [f for f in failures if "an-set" in f.at], failures

    unresolved = [f for f in failures if f.code == "invalid-paint"]
    assert sorted((f.at, f.values["element"]) for f in unresolved) == sorted(
        [("<lf-paint id=flow>", "rect"), ("<lf-paint id=sent>", "rect")]
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

    def without(page, start, end):
        cut = page.index(start)
        return page[:cut] + page[page.index(end, cut) + len(end) :]

    option = INLINE_PAGE[INLINE_PAGE.index('<lf-group id="opts-decision"') :]
    option = option[: option.index("</lf-group>") + len("</lf-group>")]
    # The question the granted figure holds takes its words off the column, which the
    # gate rightly advises against (`words-off-column`); the figure's table stays.
    framed = without(
        tables(FRAMED_TABLES_PAGE, '<table id="bare">'),
        '<lf-group id="figure-asked"',
        "</lf-group>",
    )
    page = AUTHORED_LINES_PAGE.replace(
        "</main>",
        framed
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


def test_the_render_gate_tells_what_a_column_loses_from_what_stands_beside_it(
    browser, serve
):
    """The column's readings, put on one page beside their controls.

    Content set past the column: the window is the wider of the two boxes, 1280px
    against a 720px column, so content can stand out in the margin with the document
    still not scrolling sideways, and the static lint reads pinned pixels, which a vw
    width is not. The failure names the element and how far out it is.

    Floats: what tells a margin content from a spill is where its box sits, clear of
    the column on the side it floats to or across the edge it started inside.
    Exempting floats outright would retire the check for every element that happens to
    carry one. Both readings run up the ancestors, because an element in the margin answers for what
    it holds, and the side is resolved rather than string-matched, so `inline-start`
    is the same left edge. A float carried off the window's leading edge is drawn
    outside the root scrollport, which never scrolls before that edge, so only the
    clipping reading sees it. Fixed placement answers for a box wherever it stands,
    outside the column or across its edge, since it hangs off the window, though one
    drawn over the prose is still named for the words it covers; only the desktop
    leaves an outer gutter wider than the 174px the fixed margin content takes.

    Words no mark can be shown on: an element with `display: contents` generates no
    box, and the runtime hangs a mark on the boxes it shows through instead. `#veiled`
    has one; `#ghost` has none, which reached a user as `d` appearing to do nothing.
    `tinyBoxes` cannot take this reading, since checkVisibility() is false for an
    element with no box.

    A scrolled box, which the runtime scrolls to bring an anchor into view, is read
    from its content rather than from rects that say where it is scrolled to; the
    stand-in `primed` holds the scroll each frame for the whole of the gate's read.
    A right-margin content would shift the column and carry the left-margin floats
    off the window, so the clipped sidenote stands on the container-clip page."""
    fixed = """
<style>
/* The probe reads what spills past a column with no room beside it. */
body { max-width: 768px; margin-inline: auto; }
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
    ).findings

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
        "an element in the margin's own words were named for standing where their parent put them"
    )
    assert [
        f
        for f in reported("clipped-out", "<div id=off-window>")
        if f.values["container"] == "<root scrollport>"
    ], (
        f"a float carried off the edge of the window went out with the handover: {failures}"
    )
    assert not naming("fixed-margin"), (
        f"the fixed margin content was reported for standing where it was put: {failures}"
    )
    assert not reported("past-column", "<div id=fixed-half>"), (
        f"a fixed box crossing the column was read as a spill: {failures}"
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


from browser.test_render_gate import (
    SAMPLE_FAULT,
    _panel,
)


@pytest.mark.shifts_unsurveyed
def test_the_render_gate_reports_a_compact_spill(browser, serve):
    source = leaf_page(
        "Compact spill",
        "<h1>Compact route</h1>"
        '<p id="compact-overflow">This row spills only from compact viewports.</p>',
        head="<style>@media(max-width:600px){#compact-overflow{width:700px}}</style>",
    )
    reading = render_gate_model.render_version(browser, serve(source, packages=()))
    overflow = [finding for finding in reading.advice if finding.code == "page-scrolls"]
    assert [f.widths for f in overflow] == [(360, 600)], reading.findings


@pytest.mark.shifts_unsurveyed
def test_the_render_gate_reads_a_page_that_scrolls_sideways_only_between_viewports(
    browser, serve
):
    """A body beside its track, and a row that spills only from 600 to 900px: the
    desktop window reads the page clean, and only the sweep below it sees it. A control
    row that loses its scrollbar track room only there is the same reading for the
    overlay bar. Below both, a decision in a card of fixed height, whose prose grows at
    440px and narrower (a margin stands in for its wrapping) until it pushes the
    decision's controls under the card's clip: a press nobody can reach, which only
    the sweep's narrowest widths see."""
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
<div id="card"><lf-group id="go-decision" label="Ship it?"><h2 id="go-decision-h">Ship it?</h2>
<p>The release passed its checks.</p><lf-options id="go">
<lf-option id="go-yes" label="Yes"><strong>Yes</strong></lf-option>
</lf-options></lf-group></div>
""",
        head="""<style>
#tracks { display: grid; grid-template-columns: 1fr 1fr; gap: var(--lf-sp-4); }
@media (min-width: 600px) and (max-width: 900px) { #mid-spill { white-space: nowrap; } }
#strip { display: flex; width: 240px; overflow: auto; padding: 0 0 15px; border: 0; }
#strip button { flex: 0 0 180px; height: 40px; margin: 0; }
@media (min-width: 600px) and (max-width: 900px) { #strip { padding-bottom: 0; } }
#card { height: 400px; overflow: hidden; }
@media (max-width: 440px) { #card p { margin-bottom: 400px; } }
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
    }, clipped
    # The card that loses its controls loses the prose above them too, at the same
    # widths: the content reading names the card, with what would show the rest.
    cut = {(f.at, f.widths) for f in reading.failures if f.code == "clipped-content"}
    assert cut == {(f.values["by"], f.widths) for f in clipped}, reading.failures
    assert {(f.code, f.at, f.widths) for f in reading.failures} - {
        (f.code, f.at, f.widths) for f in clipped
    } - {("clipped-content", *box) for box in cut} == set(), reading.failures
    # The row that spills between 600 and 880px scrolls the page sideways, which keeps
    # every word in reach, and a strip that leaves no room for an overlay scrollbar
    # covers its last line only under the pointer: both are the author's to judge.
    [scrolls] = [f for f in reading.advice if f.code == "page-scrolls"]
    assert (scrolls.at, scrolls.widths) == ("", (600, 880)), reading.advice
    [strip] = [f for f in reading.advice if f.code == "scrollbar-clearance"]
    assert (strip.code, strip.at, strip.widths) == (
        "scrollbar-clearance",
        "<div id=strip>",
        (600, 880),
    ), reading.advice
    assert strip.values["clear"] == 0, strip


@pytest.mark.shifts_unsurveyed
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
                "answered": True,
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
                        "decides": True,
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
    fold_transition = declared.locator("#sug-rewrite > lf-old").evaluate(
        "element => getComputedStyle(element).transitionProperty"
    )
    declared.close()
    assert len(restore_cases) > 1, "the runtime declares nothing to arrive in"
    assert suggestion_state == "accept"
    assert fold_transition == "padding"

    arrived = [f for f in arrival_findings(primed(browser.unwatched, prepare), url)]
    assert [f.split("]")[0].lstrip("[") for f in arrived] == [
        a["name"] for a in restore_cases
    ]
    # And each was the restore case it names rather than that one plus everything the
    # reloads before it left open — a difference no finding could show on its own,
    # since all of them would still be reported, each under a name that had stopped
    # being true. Only the other restore cases' keys are held against an arrival: the
    # page writes its own reading position on the way out of every load, so a store
    # holding that too is a page that departed, not a restore case that leaked.
    arranged = {a["key"] for a in restore_cases}
    for finding, restore_case in zip(arrived, restore_cases, strict=True):
        held = set(finding.split("returned holding ")[1].split()[0].split(","))
        assert held & arranged == {restore_case["key"]}, finding


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
        f"the runtime never finished replaying the log: no progress in {EXPECTED_STALL_MS}ms"
    )

    for route in held:
        route.continue_()
    page.unroute("**/api/state*")
    wait_until_ready(page)


def test_a_frame_of_another_live_leaf_page_is_checked_on_its_own(
    browser, serve, live_leaf
):
    """The gate's browser holds no key for another live Leaf page, whose server
    refuses the gate as a framer, so its frame would fail the page framing it with a
    fault that page's author can't fix. The gate shows a stand-in there, and a frame
    of any other server still reports. Only the frame stands in: a request the
    framing page itself makes to that server, such as a fetch, still reaches it."""
    framed, _ = live_leaf("framed", "Framed")
    other = urlsplit(serve(leaf_page("Other", "<h1>Other</h1>"), packages=()))
    other = f"{other.scheme}://{other.netloc}"
    frames = "".join(
        f'<iframe src="{src}/" title="{title}" '
        'style="display:block;width:100%;height:200px;border:0"></iframe>'
        for src, title in ((framed, "Another Leaf page"), (other, "Another server"))
    )
    failures = render_gate_model.render_version(
        browser.unwatched,
        serve(leaf_page("Framing", f"<h1>Framing</h1>{frames}"), packages=()),
    ).failures
    assert failures and all(
        failure.code == "console-error"
        and other in failure.values["text"] + failure.values["url"]
        for failure in failures
    ), failures

    page = browser.unwatched.new_page()
    render_gate_scheme.stand_in_other_leaves(page)
    page.set_content(f'<iframe src="{framed}/"></iframe>')
    expect(page.frame_locator("iframe").locator("p")).to_have_text(
        "Another Leaf page, checked on its own."
    )
    state = f"{framed}/api/state"
    with page.expect_response(state) as answer:
        page.evaluate("url => fetch(url, {mode: 'no-cors'}).catch(() => {})", state)
    # The live server's own refusal of a browser without its key.
    assert answer.value.status == 401


def test_the_render_gate_refuses_visual_inventories_it_cannot_trust(
    browser, serve, tmp_path, monkeypatch
):
    """A visual's parts carry ids its declaration admits. One that offers no part, as a
    callout that neither registers nor marks any, is a picture commented on whole."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
    callout = json.loads((tmp_path / ".leaf" / "registry.json").read_text())[
        "lf-callout"
    ]
    callout["visual"] = {"prefixes": ["box:"]}
    prefixed = prefixed_visual_layer("out", "inn")["lf-test-visual"]
    layer = {
        **GENERIC_VISUAL_LAYER,
        "lf-test-visual-prefixed": {
            **prefixed,
            "example": '<lf-test-visual-prefixed id="example"></lf-test-visual-prefixed>',
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
            (f.at, problem)
            for f in failures
            if f.code == "visual-parts" and f.at.startswith(f"<{tag} ")
            for problem in f.values["problems"]
        ]

    assert problems("lf-callout") == [], failures
    assert problems("lf-test-visual-prefixed") == [
        (
            "<lf-test-visual-prefixed id=prefixed>",
            {"kind": "unadmitted-parts", "parts": ["html"]},
        )
    ]


def test_the_render_gate_accepts_a_page_script_s_own_shadow_root_and_places_devtools_issues(
    browser, serve, tmp_path, monkeypatch
):
    """A page script's own custom element with a shadow root it attached itself,
    `author-card`, passes the gate, since the passage reading leaves an undeclared
    root's words alone and reads its host by its light children; beside it, the
    DevTools issues the page owns are placed at the nodes that own them."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-callout", upgrade=True)
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

    assert not [f for f in failures if "author-card" in f.at + str(f)], failures
    # Delivery serves media under the revision, so the issue names that URL.
    issues = [f for f in reading.advice if f.code == "devtools-issue"]
    # Chromium may emit the same issue for a frame more than once. The gate's
    # contract is which owned source nodes receive it, not CDP's event count.
    assert {(f.at, f.values["issue"]) for f in issues} == {
        (where, "LazyLoadImageIssue")
        for where in ("<img id=unsized>", "<img id=authored>", "<iframe id=frame>")
    }, failures
    assert all(
        [key for key, _ in f.values["details"]] == ["url"]
        and dict(f.values["details"])["url"].endswith(src)
        for f in issues
    ), issues


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
    state/restore-state.js), so it appears without the motion its gesture plays.

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
    the machine was — the first visit can come up too quickly to show it while the
    return does not, and the return would then read as having moved a surface neither
    of them owns.
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

    # The control, and the whole reason the silences below say anything: opening On Me
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


def test_a_handover_waits_while_arrivals_land_and_ends_once_they_stop(browser, serve):
    """A page whose deferred work lands a piece at a time is waited for however long
    the whole takes, as a gallery's samples load on a starved machine, while a page
    whose arrivals only make way for others is wedged and fails, naming `arrived`."""
    page = open_page(browser, serve(leaf_page("Arrivals", "<p>Words.</p>")))
    step_ms = EXPECTED_STALL_MS // 10
    # Fifteen arrivals a step apart: one and a half bounds in all.
    page.evaluate(
        """async step => {
          const {afterPresentation} = await window.__lfWidgetApi();
          for (let i = 1; i <= 15; i++)
            afterPresentation(() => new Promise(resolve => setTimeout(resolve, i * step)));
        }""",
        step_ms,
    )
    wait_until_ready(page, timeout_ms=EXPECTED_STALL_MS)

    # One arrival never lands, and above it each new one lands a step after the next
    # has taken its place, so the arrivals left swing between two and three.
    page.evaluate(
        """async step => {
          const {afterPresentation} = await window.__lfWidgetApi();
          afterPresentation(() => new Promise(() => {}));
          window.churn = setInterval(() => {
            afterPresentation(() => new Promise(resolve => setTimeout(resolve, step * 1.5)));
          }, step);
        }""",
        step_ms,
    )
    with pytest.raises(render_checks_model.PageNotReady) as unready:
        wait_until_ready(page, timeout_ms=EXPECTED_STALL_MS)
    page.evaluate("() => clearInterval(window.churn)")
    assert unready.value.stage == "arrived", unready.value


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

    failures, _, completed = render_gate_model._render_page(
        primed(browser.unwatched, configure),
        serve(
            leaf_page("Unanswered resource", "<h1>Waiting for a resource</h1>"),
            packages=(),
        ),
        {"width": 1200, "height": 900},
        EXPECTED_STALL_MS,
        [],
    )
    assert holding, "the positive control held no resource"
    assert completed is False
    assert [failure.code for failure in failures] == ["no-runtime"]


@pytest.mark.parametrize("nested", [False, True], ids=["far", "nested"])
def test_the_gate_reads_a_sample_far_below_the_window(browser, serve, nested):
    """A live sample starts its page only as the reader nears it, but the gate reads
    every document the page can show (`start_near_work`), so it refuses a page whose
    sample's own script throws wherever on the page the sample stands, a sample far
    down inside another one included: each started child starts its own."""
    content = SAMPLE_FAULT
    if nested:
        content = (
            '<p id="outer-words">Outer.</p><div style="height: 400vh"></div>'
            '<lf-sample id="inner"><template id="inner-source" data-sample>'
            f"{SAMPLE_FAULT}</template></lf-sample>"
        )
    source = leaf_page(
        "Far fault",
        '<p id="words">Words.</p><div style="height: 400vh"></div>'
        '<lf-sample id="far"><template id="far-source" data-sample>'
        f"{content}</template></lf-sample>",
    )
    failures = render_gate_model.render_version(
        browser.unwatched, serve(source)
    ).failures
    assert any(
        failure.code == "page-exception"
        and "thrown in the sample" in failure.values["text"]
        for failure in failures
    ), failures
