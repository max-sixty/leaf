"""Root tabs, page tabs, side lists and a page's parts: switching views, fragments and
history, the stuck strip and the headers stacked under it, and queue rows and groups."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_layout import SHOT_SRC, SHOTS
from render_harness import (
    ROOT,
    displayed,
    holding,
    leaf_page,
    open_page,
    open_threads,
    pane_scroll_behavior,
    post_event,
    resized,
    root_overflow,
    scroll_settled,
    stamp_page,
    undo,
    wait_for_revision,
)

from leaf import render_checks as render_checks_model
from leaf.render_checks import rendered, wait_until_ready

ROOT_TABS_PAGE = ROOT / "tests/fixtures/pages/root-tabs.html"
ROOT_PARTS_PAGE = ROOT / "tests/fixtures/pages/root-parts.html"


def test_root_tabs_switch_views_without_moving_the_strip_and_follow_history(
    browser, serve
):
    """A tab switch is not fragment travel. The strip stays where it is on screen: a view
    never read opens at its start when the strip is stuck and leaves the shared header
    alone when it is not, and a view read past its start reopens where the user left it.
    Pointer, keyboard, and Back/Forward agree, and a fresh load of the remembered view
    shows the page's top.

    A view's place is where the user was reading in it, not a pixel offset: a window
    resized while the view is hidden rewraps everything above that passage, and the view
    still reopens with the passage where the user left it."""
    url = serve(ROOT_TABS_PAGE)
    page = open_page(browser, url)
    resized(page, 1280, 720)
    tabs = page.locator("#root-tabs")
    plan = tabs.get_by_role("tab", name="Plan", exact=True)
    evidence = tabs.get_by_role("tab", name="Evidence", exact=True)
    summary = tabs.get_by_role("tab", name="Summary", exact=True)

    def switch(tab):
        # Locator.click would scroll a sticky tab back to its static-flow box.
        box = tab.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(tab).to_have_attribute("aria-selected", "true")
        return settled()

    def settled():
        scroll_settled(page)
        return page.evaluate("scrollY")

    def read_at(y):
        page.evaluate("y => scrollTo({top: y, behavior: 'instant'})", y)
        return settled()

    def stuck_at_start(panel):
        geometry = page.evaluate(
            """selector => {
          const strip = document.querySelector('#root-tabs > .lf-tabstrip');
          return {
            panel: document.querySelector(selector).getBoundingClientRect().top,
            strip: strip.getBoundingClientRect().toJSON(),
            inset: parseFloat(getComputedStyle(strip).top),
          };
        }""",
            panel,
        )
        assert geometry["strip"]["top"] == pytest.approx(geometry["inset"], abs=1)
        assert geometry["panel"] == pytest.approx(geometry["strip"]["bottom"], abs=1)

    expect(plan).to_have_attribute("aria-selected", "true")
    assert settled() == 0
    # With the header on screen, a switch leaves it there.
    assert switch(summary) == 0
    assert switch(evidence) == 0
    assert page.url.endswith("#evidence-tab")
    # Read Evidence past its start; Plan, never read, opens at its start under the
    # stuck strip rather than at the top of the page.
    evidence_read = read_at(450)
    # Even a view shorter than the window keeps enough page below the sticky strip
    # for the browser to land its start without pulling the strip downward.
    assert 0 < switch(summary) < evidence_read
    stuck_at_start("#summary-tab")
    plan_start = switch(plan)
    assert 0 < plan_start < evidence_read
    stuck_at_start("#plan-tab")
    # Evidence reopens where the user left it, and pressing the open tab moves nothing.
    assert switch(evidence) == pytest.approx(evidence_read, abs=2)
    assert switch(evidence) == pytest.approx(evidence_read, abs=2)

    # The keyboard walk is the same switch, and focus stays in the strip.
    expect(evidence).to_be_focused()
    page.keyboard.press("ArrowLeft")
    expect(plan).to_have_attribute("aria-selected", "true")
    expect(plan).to_be_focused()
    assert settled() == pytest.approx(plan_start, abs=2)
    page.keyboard.press("ArrowRight")
    expect(evidence).to_have_attribute("aria-selected", "true")
    expect(evidence).to_be_focused()
    assert settled() == pytest.approx(evidence_read, abs=2)

    # Back and Forward select the entry's view at the offset it was left at.
    page.go_back()
    expect(plan).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#plan-tab")
    assert settled() == pytest.approx(plan_start, abs=2)
    page.go_forward()
    expect(evidence).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#evidence-tab")
    assert settled() == pytest.approx(evidence_read, abs=2)

    # A link into a hidden view still opens it and lands on the target.
    page.evaluate("location.hash = 'plan-rollback'")
    expect(plan).to_have_attribute("aria-selected", "true")
    settled()
    expect(page.locator("#plan-rollback h2")).to_be_in_viewport()
    # Back to that link's entry from another view switches to the view holding it.
    switch(evidence)
    page.go_back()
    expect(plan).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#plan-rollback")

    # A reveal (a comment anchor, find-in-page) opens another view, and the entry the
    # user is located on names it, so pressing away and coming Back returns there.
    page.evaluate(
        """async () => {
          const {reveal} = await window.__lfCheckApi();
          const {retainUserIntent} = await window.__lfWidgetApi();
          reveal(document.querySelector('#evidence-tab'), retainUserIntent());
        }"""
    )
    rendered(page)
    expect(evidence).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#evidence-tab")
    switch(plan)
    page.go_back()
    expect(evidence).to_have_attribute("aria-selected", "true")

    # A fresh load that restores the remembered view opens at the page's top.
    switch(evidence)
    page.goto(url)
    expect(evidence).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#evidence-tab")
    assert settled() == 0

    # The passage read in a hidden view keeps its place through a resize.
    passage = page.locator("#evidence-sign-in p").first
    below_landing_edge = """element => element.getBoundingClientRect().top
        - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)"""
    passage.evaluate("element => element.scrollIntoView({block: 'start'})")
    page.evaluate("scrollBy({top: -40, behavior: 'instant'})")
    settled()
    left = passage.evaluate(below_landing_edge)
    assert left == pytest.approx(40, abs=2)
    switch(plan)
    resized(page, 520, 720)
    switch(evidence)
    assert passage.evaluate(below_landing_edge) == pytest.approx(left, abs=2)


def test_a_url_into_a_hidden_root_view_lands_once_the_view_is_built(browser, serve):
    """The browser lands a fragment while every view still stacks, before the tab set
    has hidden the others or put up its strip. The page lands it again once widgets
    have upgraded, by the browser's own rule, and the state read that follows moves
    nothing."""
    url = serve(ROOT_TABS_PAGE)
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(f"{url}#evidence-sign-in", wait_until="load")
    render_checks_model.wait_for_probe(page, "upgraded")
    assert page.locator("body").get_attribute("data-lf-presented") is None
    expect(page.locator("#evidence-tab")).not_to_have_attribute(
        "hidden", re.compile(".*")
    )
    landing = page.evaluate(
        """() => ({
          target: document.querySelector('#evidence-sign-in')
            .getBoundingClientRect().top,
          edge: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
          scroll: document.scrollingElement.scrollTop,
        })"""
    )
    assert landing["target"] == pytest.approx(landing["edge"], abs=1), landing

    assert held, "the state read completed before the upgraded landing was observed"
    held.pop().continue_()
    page.unroute("**/api/state*")
    wait_until_ready(page)
    scroll_settled(page)
    assert page.evaluate("document.scrollingElement.scrollTop") == pytest.approx(
        landing["scroll"], abs=1
    )


def test_pointer_tab_underline_moves_without_delaying_the_view(browser, serve):
    """Only adjacent pointer selections travel; a new input retargets or ends the cue."""
    source = leaf_page(
        "Selection motion",
        '<h1>Selection motion</h1><section><lf-tabs id="moving-tabs">'
        + "".join(
            f'<lf-tab id="view-{i}" label="View number {i}"><p>Content {i}</p></lf-tab>'
            for i in range(6)
        )
        + '</lf-tabs><lf-tabs id="side-tabs" list="side">'
        '<lf-tab id="side-a" label="First" summary="First context"><p>First.</p></lf-tab>'
        '<lf-tab id="side-b" label="Second" summary="Second context"><p>Second.</p></lf-tab>'
        "</lf-tabs></section>",
        head="<style>#moving-tabs { max-width:480px }</style>",
    )
    page = open_page(
        browser,
        serve(source),
        init_script="""document.addEventListener('transitionrun', event => {
          if (!event.target.matches('.lf-tab-selection')) return;
          for (const animation of event.target.getAnimations()) {
            animation.pause();
            animation.currentTime = 0;
          }
        });""",
    )
    page.emulate_media(reduced_motion="no-preference")
    tabs = page.locator("#moving-tabs").get_by_role("tab")
    mark = page.locator("#moving-tabs > .lf-tabstrip > .lf-tab-selection")
    animating = "node => node.getAnimations().length"
    at = "node => node.getBoundingClientRect().left"
    advance = "(node, time) => node.getAnimations().forEach(a => a.currentTime = time)"

    def travelling():
        expect(mark).to_be_visible()
        page.wait_for_function(
            "s => {const a = document.querySelector(s).getAnimations(); "
            "return a.length > 0 && a.every(a => a.playState === 'paused')}",
            arg="#moving-tabs > .lf-tabstrip > .lf-tab-selection",
        )

    initial = mark.evaluate(at)
    tabs.nth(1).click()
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(page.locator("#view-1 p")).to_be_visible()
    travelling()
    assert mark.evaluate(at) == pytest.approx(initial, abs=0.5)
    mark.evaluate(advance, 80)
    middle = mark.evaluate(at)
    destination = tabs.nth(1).locator(".lf-tab-name").evaluate(at)
    assert initial < middle < destination
    # Reverse while its pixels are between names: no snap back to either endpoint.
    tabs.first.click()
    travelling()
    assert mark.evaluate(at) == pytest.approx(middle, abs=0.5)
    expect(page.locator("#view-0 p")).to_be_visible()
    mark.evaluate(advance, 80)
    assert initial < mark.evaluate(at) < middle
    # Keyboard selection is immediate, including interruption of pointer motion.
    page.keyboard.press("ArrowRight")
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    assert mark.evaluate(animating) == 0
    tabs.first.click()
    tabs.nth(3).click()
    assert mark.evaluate(animating) == 0  # A nonadjacent choice does not travel.
    # Vertical strips keep their selected face, with no travelling mark.
    side = page.locator("#side-tabs").get_by_role("tab")
    side.nth(1).click()
    assert page.locator("#side-tabs .lf-tab-selection").evaluate(animating) == 0
    page.emulate_media(reduced_motion="reduce")
    tabs.nth(2).click()
    assert mark.evaluate(animating) == 0
    page.emulate_media(reduced_motion="no-preference")
    tabs.first.focus()
    page.keyboard.press("Home")
    tabs.nth(1).click()
    travelling()
    page.locator("#moving-tabs > .lf-tabstrip").evaluate("node => node.scrollLeft = 30")
    page.wait_for_function(
        "document.querySelector('#moving-tabs > .lf-tabstrip > .lf-tab-selection').getAnimations().length === 0"
    )
    tabs.first.focus()
    page.keyboard.press("Home")
    tabs.nth(1).click()
    travelling()
    resized(page, 390, 844)
    assert mark.evaluate(animating) == 0
    # The side list now runs horizontally; its mark is below the summary, and travels too.
    side.first.click()
    side_mark = page.locator("#side-tabs > .lf-tabstrip > .lf-tab-selection")
    page.wait_for_function(
        "document.querySelector('#side-tabs > .lf-tabstrip > .lf-tab-selection').getAnimations().length > 0"
    )
    assert side_mark.bounding_box()["height"] == 2
    side_mark.evaluate("node => node.getAnimations().forEach(a => a.finish())")


def test_a_stuck_root_tab_strip_hides_what_passes_under_it(browser, serve):
    """The root strip sticks at the window's top and paints over the document, so what
    passes under it is not on screen: `shownRect`, the one reading of that, clips a
    block behind the stuck strip to the strip's foot, which the strip's stated height
    puts at `--lf-top` inside its panels. At the top of the page the strip is in flow
    and hides nothing. In forced colors only the selected tab's name is marked."""
    page = open_page(browser, serve(ROOT_TABS_PAGE) + "#plan-tab")
    resized(page, 1280, 720)
    READ = """async () => {
      const geometry = await window.__lfCheckApi();
      const strip = document
        .querySelector('#root-tabs > .lf-tabstrip').getBoundingClientRect();
      const behind = document.querySelector('#plan-stages h2');
      return {
        strip: {top: strip.top, bottom: strip.bottom},
        behind: behind.getBoundingClientRect().toJSON(),
        band: geometry.visibleBand(document.scrollingElement, behind).top,
        shown: geometry.shownRect(behind, new Map())?.top,
      };
    }"""
    page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    scroll_settled(page)
    at_top = page.evaluate(READ)
    assert at_top["shown"] == pytest.approx(at_top["behind"]["top"], abs=0.5), at_top
    # Stick the strip, then scroll the heading half under it.
    page.evaluate("scrollTo({top: 600, behavior: 'instant'})")
    scroll_settled(page)
    at = page.evaluate(READ)
    page.evaluate(
        "y => scrollTo({top: y, behavior: 'instant'})",
        page.evaluate("scrollY")
        + at["behind"]["top"]
        - at["strip"]["bottom"]
        + at["behind"]["height"] / 2,
    )
    scroll_settled(page)
    stuck = page.evaluate(READ)
    # Stuck at the window's top, where no chrome stands above it.
    assert stuck["strip"]["top"] == pytest.approx(0, abs=0.5), stuck
    assert stuck["behind"]["top"] < stuck["strip"]["bottom"] < stuck["behind"]["bottom"]
    assert stuck["band"] == pytest.approx(stuck["strip"]["bottom"], abs=0.5), stuck
    assert stuck["shown"] == pytest.approx(stuck["strip"]["bottom"], abs=0.5), stuck

    # A forced transparent border must not make every page tab look selected.
    page.emulate_media(forced_colors="active")
    page.keyboard.press("Tab")
    page.locator("#root-tabs > .lf-tabstrip .lf-tab-btn").first.focus()
    reading = """() => {
      const strip = document.querySelector('#root-tabs > .lf-tabstrip');
      const background = getComputedStyle(strip).backgroundColor;
      const line = strip.querySelector('.lf-tab-selection');
      const mark = getComputedStyle(line);
      const ink = line.getBoundingClientRect();
      return [...strip.querySelectorAll('.lf-tab-btn')].map(tab => {
        const name = tab.querySelector('.lf-tab-name').getBoundingClientRect();
        return {selected: tab.getAttribute('aria-selected') === 'true',
          marked: mark.display !== 'none' && mark.backgroundColor !== background
            && ink.left < name.right && name.left < ink.right};
      });
    }"""
    for _ in range(2):
        marks = page.evaluate(reading)
        assert any(mark["selected"] for mark in marks), marks
        assert all(mark["selected"] == mark["marked"] for mark in marks), marks
        page.keyboard.press("ArrowRight")


def _stacked_headers(browser, serve, flow="page"):
    """A tab strip with a long pinned diff in its first tab, then a short one whose code
    is wide enough to scroll sideways, and another long one after the tabs. In the
    page's flow the strip stands over the root; a set in a section is a framed box,
    whose strip stands over only the set."""
    path = "src/lib.rs"
    rows = "".join(f"+    let value_{i} = {i};\n" for i in range(200))
    patch = (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -1 +1,201 @@\n fn main() {{\n{rows}"
    )
    wide = "+    let wide = " + " + ".join(f"term_{i}" for i in range(60)) + ";\n"
    short = (
        "diff --git a/src/wide.rs b/src/wide.rs\n--- a/src/wide.rs\n+++ b/src/wide.rs\n"
        "@@ -1 +1,11 @@\n fn wide() {\n"
        + wide
        + "".join(f"+    let short_{i} = {i};\n" for i in range(9))
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Stacked headers",
                "<h1>Stacked</h1>"
                + ("<section>" if flow == "box" else "")
                + '<lf-tabs id="tabs">'
                '<lf-tab id="diff-tab" label="Diff"><lf-diff id="patch"><pre>'
                + patch
                + '</pre></lf-diff><lf-diff id="wide"><pre>'
                + short
                + '</pre></lf-diff></lf-tab><lf-tab id="notes-tab" label="Notes">'
                "<p>Notes.</p></lf-tab></lf-tabs>"
                + ("</section>" if flow == "box" else "")
                + '<lf-diff id="after-tabs"><pre>'
                + patch
                + "</pre></lf-diff>",
            )
        ),
    )
    resized(page, 1280, 720)
    page.wait_for_function(
        "() => document.querySelectorAll('lf-diff.lf-rendered').length === 3"
    )
    expect(page.locator("#tabs")).to_have_attribute("data-lf-views-flow", flow)
    return page


@pytest.mark.parametrize("flow", ["page", "box"])
def test_sticky_headers_stack_so_a_diff_in_a_tab_pins_under_the_strip(
    browser, serve, flow
):
    """A diff's file header in a tab pins under the stuck tab strip rather than over
    it: each sticky header has a stated height and adds it to `--lf-top` for what it
    stands over. A landing on one of the diff's rows arrives below both headers, and
    the part of a row under the diff's header reads as not on screen. A page's strip
    is cleared by the root's own padding; a framed set's strip stands over only the
    set, so the rows clear it with their margin, read through the code's sideways
    scroller, where a framed set's rows had landed under the file header."""
    page = _stacked_headers(browser, serve, flow)
    read = page.evaluate(
        """async () => {
        const geometry = await window.__lfCheckApi();
        const box = (el) => el.getBoundingClientRect();
        const strip = document.querySelector('#tabs > .lf-tabstrip');
        const diff = document.querySelector('lf-diff');
        const head = diff.shadowRoot.querySelector('.lf-diff-file > details > summary');
        const row = [...diff.shadowRoot.querySelectorAll('[data-line]')][150];
        row.scrollIntoView({block: 'start', behavior: 'instant'});
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        const landed = {strip: box(strip).bottom, head: box(head).bottom, row: box(row).top};
        // Half a row under the diff's header.
        document.scrollingElement.scrollTop += box(row).top - box(head).bottom
            + box(row).height / 2;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return {
            landed,
            strip: {top: box(strip).top, bottom: box(strip).bottom},
            head: {top: box(head).top, bottom: box(head).bottom},
            row: {top: box(row).top, bottom: box(row).bottom},
            shown: geometry.shownRect(row, new Map())?.top,
        };
    }"""
    )
    assert read["head"]["top"] == pytest.approx(read["strip"]["bottom"], abs=0.5), read
    landed = read["landed"]
    assert landed["head"] == pytest.approx(landed["strip"] + 35, abs=0.5), landed
    assert landed["row"] > landed["head"], landed
    assert read["row"]["top"] < read["head"]["bottom"] < read["row"]["bottom"], read
    assert read["shown"] == pytest.approx(read["head"]["bottom"], abs=0.5), read


def test_focus_in_a_stuck_header_leaves_the_page_where_it_is(browser, serve):
    """A control in a stuck sticky header stands inside the root's landing band, so the
    browser scrolled toward it on every focus and the header never came out from under
    the band: the page crept 17px a focus under a diff's file header, and was centred,
    hundreds of pixels a key, under a page tab strip. The focus margin is read from the
    sticky-header slot, so focusing one where it sticks scrolls nothing: in a page tab,
    where the strip stands over it, and after the tabs, where the root's band still
    counts the strip. Focus moving on from the file header into its code, a tab stop
    since it scrolls sideways, clears the header."""
    page = _stacked_headers(browser, serve)
    focus_in = """async (id) => {
        const page = document.scrollingElement;
        const diff = document.getElementById(id);
        const row = [...diff.shadowRoot.querySelectorAll('[data-line]')][150];
        row.scrollIntoView({block: 'start', behavior: 'instant'});
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        const controls = {
            file: diff.shadowRoot.querySelector('.lf-diff-file > details > summary'),
        };
        if (id === 'patch')
            controls.tab = document.querySelector(
                '#tabs > .lf-tabstrip [aria-selected="true"]');
        const moved = {};
        for (const [name, control] of Object.entries(controls)) {
            const before = page.scrollTop;
            control.focus();
            await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
            moved[name] = page.scrollTop - before;
        }
        return moved;
    }"""
    assert page.evaluate(focus_in, "patch") == {"file": 0, "tab": 0}
    assert page.evaluate(focus_in, "after-tabs") == {"file": 0}
    # Tab from a stuck file header into its code, scrolled partly past above it.
    page.evaluate(
        """async () => {
        const root = document.getElementById('wide').shadowRoot;
        const code = root.querySelector('.lf-text-scroller');
        document.scrollingElement.scrollTop += code.getBoundingClientRect().top - 60;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        root.querySelector('.lf-diff-file > details > summary').focus({preventScroll: true});
    }"""
    )
    page.keyboard.press("Tab")
    rendered(page)
    code = page.evaluate(
        """() => {
        const root = document.getElementById('wide').shadowRoot;
        const head = root.querySelector('.lf-diff-file > details > summary');
        const focused = root.activeElement;
        return {scroller: focused?.classList.contains('lf-text-scroller'),
                top: focused?.getBoundingClientRect().top,
                head: head.getBoundingClientRect().bottom};
    }"""
    )
    assert code["scroller"], code
    assert code["top"] >= code["head"], code


WIDE_TABLE_IN_A_FRAMED_SET = leaf_page(
    "A wide table in a framed set",
    '<h1>Framed</h1><section><lf-tabs id="views"><lf-tab id="table-tab" label="Table">'
    + "<p>Reading before the table.</p>" * 30
    + '<table id="wide"><thead><tr><th>Row</th>'
    + "".join(f"<th>Column {c}</th>" for c in range(12))
    + "</tr></thead><tbody>"
    + "".join(
        f'<tr><td><a id="row-{r}" href="#views">row {r}</a></td>'
        + "".join(f"<td>column {c} with some words</td>" for c in range(12))
        + "</tr>"
        for r in range(30)
    )
    + "</tbody></table>"
    + "<p>Reading after the table.</p>" * 30
    + '</lf-tab><lf-tab id="other-tab" label="Other"><p>Other.</p></lf-tab>'
    "</lf-tabs></section>" + "<p>After the set.</p>" * 30,
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_tab_onto_a_link_in_a_wide_table_under_a_framed_strip_clears_the_strip(
    request, serve, engine
):
    """A wide table scrolls only sideways, so the browser's own focus scroll on a link in
    it still counts the framed set's strip stuck over the table. Tab onto a link the
    strip stands over brings the link and its ring out below the strip; where the table
    also scrolled down, its links counted nothing over it and stood with their ring
    under the strip."""
    page = open_page(request.getfixturevalue(engine), serve(WIDE_TABLE_IN_A_FRAMED_SET))
    resized(page, 1280, 720)
    expect(page.locator("#views")).to_have_attribute("data-lf-views-flow", "box")
    # Stick the strip, then stand row 11's link 20px under the strip's top: inside the
    # root's landing band, which the strip covers.
    page.evaluate(
        "scrollBy({top: document.getElementById('wide').getBoundingClientRect().top"
        " - 100, behavior: 'instant'})"
    )
    scroll_settled(page)
    page.evaluate("""() => {
      const strip = document.querySelector('#views > .lf-tabstrip').getBoundingClientRect();
      const link = document.getElementById('row-11').getBoundingClientRect();
      scrollBy({top: link.top - strip.top - 20, behavior: 'instant'});
    }""")
    scroll_settled(page)
    page.locator("#row-10").evaluate("a => a.focus({preventScroll: true})")
    page.keyboard.press("Tab")
    expect(page.locator("#row-11")).to_be_focused()
    scroll_settled(page)
    read = page.evaluate("""() => {
      const strip = document.querySelector('#views > .lf-tabstrip').getBoundingClientRect();
      const link = document.getElementById('row-11');
      const style = getComputedStyle(link);
      const ring = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
      return {strip: [strip.top, strip.bottom], ringTop: link.getBoundingClientRect().top - ring};
    }""")
    assert read["strip"][0] == pytest.approx(0, abs=0.5), read
    assert read["ringTop"] >= read["strip"][1], read


def test_embedded_tab_selection_preserves_the_document_reading_position(browser, serve):
    source = (
        ROOT_TABS_PAGE.read_text()
        .replace('<lf-tabs id="root-tabs">', '<section><lf-tabs id="root-tabs">')
        .replace("</lf-tabs>", "</lf-tabs></section>")
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 720)
    tabs = page.locator("#root-tabs")
    expect(tabs).to_have_attribute("data-lf-views-flow", "box")
    evidence = tabs.get_by_role("tab", name="Evidence", exact=True)
    evidence.evaluate("el => el.scrollIntoView({block: 'start', behavior: 'instant'})")
    scroll_settled(page)
    before = page.evaluate("scrollY")
    assert before > 0, "The embedded tabs must be below the document origin"
    box = evidence.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(evidence).to_have_attribute("aria-selected", "true")
    scroll_settled(page)
    assert page.evaluate("scrollY") == pytest.approx(before, abs=2)


@pytest.mark.parametrize("target_id", ["x", "two"])
def test_back_to_a_fragment_the_page_has_hidden_since_lands_on_it(
    browser, serve, target_id
):
    """Back restores the offset an entry was left at, unless the element its fragment
    names is no longer shown: the user closed its tab since, so that offset belongs to
    a page that has changed, and landing the fragment, which opens the tab, is the
    answer. The fragment may name the panel itself or its contents. The tab set is
    embedded, so it keeps no history of its own."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(60))
    url = serve(
        leaf_page(
            "Back to a hidden fragment",
            f'<h1 id="top">Hidden fragment</h1><p><a href="#{target_id}">To target</a></p>'
            '<section><lf-tabs id="views">'
            '<lf-tab id="one" label="One"><p>One is short.</p></lf-tab>'
            f'<lf-tab id="two" label="Two">{filler}<p id="x">The target.</p></lf-tab>'
            '</lf-tabs></section><p><a href="#top">To top</a></p>',
        )
    )
    page = open_page(browser, url)
    resized(page, 1280, 720)
    tabs = page.locator("#views")
    one = tabs.get_by_role("tab", name="One", exact=True)
    two = tabs.get_by_role("tab", name="Two", exact=True)
    target = page.locator(f"#{target_id}")

    page.get_by_role("link", name="To target").click()
    expect(two).to_have_attribute("aria-selected", "true")
    expect(target).to_be_in_viewport()
    one.click()
    expect(one).to_have_attribute("aria-selected", "true")
    page.get_by_role("link", name="To top").click()
    page.wait_for_url(re.compile("#top$"))

    page.go_back()
    expect(two).to_have_attribute("aria-selected", "true")
    expect(target).to_be_in_viewport()


def test_page_tabs_take_the_page_width_and_its_one_left_edge(browser, serve):
    """Page tabs are sections of one page: on a sidebar page the header, the strip and
    the open panel share main's left edge and the panel takes main's width."""
    source = ROOT_TABS_PAGE.read_text().replace(
        '<main class="layout-column">', '<main class="layout-sidebar">', 1
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    tabs = page.locator("#root-tabs")
    expect(tabs).to_have_attribute("data-lf-views-flow", "page")
    boxes = page.evaluate(
        """() => {
          const box = (el) => {
            const r = el.getBoundingClientRect();
            return {left: Math.round(r.left), width: Math.round(r.width)};
          };
          const main = document.querySelector('main');
          const style = getComputedStyle(main);
          const r = main.getBoundingClientRect();
          return {
            content: {
              left: Math.round(r.left + parseFloat(style.paddingLeft)),
              width: Math.round(r.width - parseFloat(style.paddingLeft)
                - parseFloat(style.paddingRight)),
            },
            title: box(document.querySelector('main > header h1')),
            strip: box(document.querySelector('#root-tabs > .lf-tabstrip')),
            panel: box(document.querySelector('#root-tabs > lf-tab:not([hidden])')),
          };
        }"""
    )
    assert boxes["content"]["width"] > 720, boxes
    assert boxes["panel"] == boxes["content"], boxes
    assert boxes["strip"]["left"] == boxes["content"]["left"], boxes
    assert boxes["title"]["left"] == boxes["content"]["left"], boxes


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_tab_onto_a_nested_workspace_link_clears_the_floating_panel(
    request, serve, engine
):
    """The workspace's tab scroller clears the collapsed panel on native Tab,
    including when an outer tab transfers its end clearance to nested views."""
    source = leaf_page(
        "Review evidence",
        '<header><h1>Review evidence</h1></header><lf-tabs id="views">'
        '<lf-tab id="changes" label="Changes"><lf-tabs id="experiments">'
        '<lf-tab id="runtime" label="Runtime">'
        '<div style="height:380px"></div>'
        '<p style="text-align:center"><a id="output" href="#runtime">'
        "Try the output</a></p>"
        + "<p>Further evidence.</p>" * 20
        + "</lf-tab></lf-tabs></lf-tab></lf-tabs>",
        layout="workspace",
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 900, 600)
    page.get_by_role("tab", name="Changes", exact=True).click()
    for _ in range(4):
        page.keyboard.press("Tab")
    link = page.locator("#output")
    expect(link).to_be_focused()
    scroll_settled(page)
    position = link.evaluate("""link => {
      const box = link.getBoundingClientRect();
      const hits = [box.top + 1, box.bottom - 1].map(y =>
        document.elementFromPoint(box.x + box.width / 2, y));
      return {exposed: hits.every(hit => hit === link || link.contains(hit)),
        link: box.toJSON(), hits: hits.map(hit => hit?.tagName)};
    }""")
    assert position["exposed"], position


def test_a_hidden_workspace_tab_preserves_lazy_image_dimensions(browser, serve):
    """Inactive views keep their column width and zero height, so sized lazy images
    reserve their aspect ratio before the reader opens the view or its disclosure."""
    src = SHOT_SRC["before"]
    source = leaf_page(
        "Saved evidence",
        '<header><h1>Saved evidence</h1></header><lf-tabs id="views">'
        '<lf-tab id="intro" label="Introduction"><p>Introduction.</p></lf-tab>'
        '<lf-tab id="saved" label="Saved"><lf-tabs id="outputs">'
        '<lf-tab id="output" label="Output"><figure><details>'
        "<summary>More screens</summary>"
        f'<img id="capture" src="{src}" alt="Saved screen" loading="lazy"'
        ' width="600" height="300" style="aspect-ratio:2/1">'
        "</details></figure></lf-tab></lf-tabs></lf-tab></lf-tabs>",
        layout="workspace",
    )
    page = browser.new_page(viewport={"width": 900, "height": 600})
    cdp = page.context.new_cdp_session(page)
    cdp.send("Audits.enable")
    issues = []
    cdp.on("Audits.issueAdded", lambda event: issues.append(event["issue"]["code"]))
    page.goto(serve(source, media={src: SHOTS["before"]}))
    wait_until_ready(page)
    dimensions = page.locator("#capture").evaluate("""image => {
      const tab = document.getElementById('saved').getBoundingClientRect();
      const box = image.getBoundingClientRect();
      return {tab: {width: tab.width, height: tab.height},
        image: {width: box.width, height: box.height}};
    }""")
    assert dimensions["tab"]["height"] == 0, dimensions
    assert dimensions["image"]["width"] > 0, dimensions
    assert dimensions["image"]["height"] == pytest.approx(
        dimensions["image"]["width"] / 2
    ), dimensions
    assert "LazyLoadImageIssue" not in issues
    page.get_by_role("tab", name="Saved", exact=True).click()
    page.get_by_text("More screens", exact=True).click()
    page.wait_for_function("document.getElementById('capture').naturalWidth > 0")


def test_a_workspace_page_tab_gives_its_only_block_its_box_before_upgrade(
    browser, serve
):
    """A full-height page tab's only block fills its content box from first paint,
    leaving the tab's panel clearance below it. Upgrade keeps that same box, including
    the ring's room around the set and the clearance after the reading content."""
    source = leaf_page(
        "Workspace page tab",
        '<header><h1>Review</h1></header><lf-tabs id="views">'
        '<lf-tab id="work" label="Work"><template></template>'
        '<section id="surface"><p>Work here.</p>'
        '</section></lf-tab><lf-tab id="notes" label="Notes"><p>Notes.</p>'
        "</lf-tab></lf-tabs>",
        layout="workspace",
    )
    boot = []
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(source), wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"

        def heights():
            return page.evaluate("""() => {
              const panel = document.querySelector('#work');
              const tab = panel.getBoundingClientRect();
              const block = document.querySelector('#surface').getBoundingClientRect();
              const end = parseFloat(getComputedStyle(panel).paddingBottom);
              return {tab: tab.height, block: block.height, bottom: tab.bottom - end - block.bottom,
                      sides: [block.left, block.right]};
            }""")

        first = heights()
        assert first["tab"] > 300 and abs(first["bottom"]) <= 1, first
        boot.pop().continue_()
        wait_until_ready(page)
        upgraded = heights()
        assert abs(upgraded["bottom"]) <= 1, upgraded
        assert upgraded["sides"] == pytest.approx(first["sides"], abs=0.5), (
            first,
            upgraded,
        )
        assert upgraded["block"] == pytest.approx(first["block"], abs=0.5), (
            first,
            upgraded,
        )
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


@pytest.mark.parametrize("layout", ["column", "sidebar", "workspace"])
def test_wide_evidence_in_a_page_tab_takes_the_room_it_would_outside_one(
    browser, serve, layout
):
    """A page tab is a section of the page, so a `wide` or `available` table in its
    open panel takes the box and the column widths its twin outside the set takes: at
    first paint, before the runtime has drawn the strip, then at a desktop window, with
    Threads open over it, and on a phone. A boxed set's panel draws a frame,
    so the same table there stays inside it. Each table has twelve columns, so on a
    column page, where a table granted room takes what its columns need, it needs the
    room."""

    def tables(where):
        heads = "".join(f"<th>Case {i}</th>" for i in range(12))
        cells = "<td>Result</td>" * 12
        return "".join(
            f'<table id="{where}-{space}" data-width="{space}"><thead><tr>{heads}'
            f"</tr></thead><tbody><tr>{cells}</tr></tbody></table>"
            for space in ("wide", "available")
        )

    content = (
        f'<h1 id="t">Evidence in page tabs</h1><p id="prose">Prose.</p>{tables("out")}'
        f'<lf-tabs id="root-tabs"><lf-tab id="compare" label="Compare">{tables("in")}'
        '</lf-tab><lf-tab id="notes" label="Notes"><p>Notes.</p></lf-tab></lf-tabs>'
        f'<section><lf-tabs id="boxed"><lf-tab id="boxed-open" label="Boxed">{tables("boxed")}'
        '</lf-tab><lf-tab id="boxed-other" label="Other"><p>Other.</p></lf-tab></lf-tabs>'
        "</section>"
    )
    # A sidebar page with no aside holds one flow: the page's own CSS gives each block
    # the row, and the tab set stays root, a direct child of main.
    source = leaf_page(
        "Evidence in page tabs",
        content,
        head="<style>main > * { flex-basis: 100%; }</style>"
        if layout == "sidebar"
        else "",
        layout=layout,
    )
    boot = []
    context = browser.new_context(viewport={"width": 1600, "height": 900})
    page = context.new_page()
    page.route("**/leaf.js", lambda route: boot.append(route))
    measure = """() => Object.fromEntries(
      ['prose', 'out-wide', 'out-available', 'in-wide', 'in-available', 'boxed-open',
       'boxed-wide', 'boxed-available'].map(id => {
        const el = document.getElementById(id), box = el.getBoundingClientRect();
        return [id, {left: Math.round(box.left), width: Math.round(box.width),
          columns: Math.round(el.querySelector('thead')?.getBoundingClientRect().width ?? 0)}];
      }))"""

    def twins(state):
        at = page.evaluate(measure)
        for space in ("wide", "available"):
            assert at[f"in-{space}"] == at[f"out-{space}"], (state, space, at)
            boxed, panel = at[f"boxed-{space}"], at["boxed-open"]
            assert boxed["left"] >= panel["left"], (state, space, at)
            assert boxed["left"] + boxed["width"] <= panel["left"] + panel["width"], (
                state,
                space,
                at,
            )
        assert root_overflow(page) == 0, state
        return at

    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(source), wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"
        first = twins("first paint")
        boot.pop().continue_()
        wait_until_ready(page)
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")
    expect(page.locator("#root-tabs")).to_have_attribute("data-lf-views-flow", "page")
    assert twins("desktop") == first
    # Wider than the reading column, which a workspace's prose does not keep.
    assert first["in-wide"]["width"] > 720, first
    open_threads(page)
    twins("threads open")
    resized(page, 390, 800)
    twins("phone")


@pytest.mark.parametrize(
    "side", [True, False], ids=["workspace-side-list", "boxed-panel"]
)
def test_a_scrolling_tab_panel_keeps_nested_headers_on_its_edge(browser, serve, side):
    """A padded panel's nested tab strip sticks on the scrollport's edge. Leaving
    the padding above it lets fragments of the output show through that band."""
    source = leaf_page(
        "Inspect output",
        "<header><h1>Inspect output</h1></header>"
        + (
            ""
            if side
            else "<style>#output { height: 360px; overflow: auto; }</style><section>"
        )
        + f'<lf-tabs id="outputs" {"list=side" if side else ""}>'
        '<lf-tab id="output" label="Alert configuration">'
        '<lf-tabs id="arms"><lf-tab id="baseline" label="Leaf baseline">'
        "<h2>Saved configuration</h2><details><summary>Checks passed</summary>"
        "<p>Both checks passed.</p></details>"
        + "".join(f'<p id="row-{n}">Configuration row {n}.</p>' for n in range(40))
        + '</lf-tab><lf-tab id="control" label="Plain HTML"><p>Control output.</p>'
        "</lf-tab></lf-tabs></lf-tab></lf-tabs>" + ("" if side else "</section>"),
        layout="workspace" if side else "column",
    )
    page = open_page(browser, serve(source))
    panel = page.locator("#output")
    panel.hover()
    page.mouse.wheel(0, 120)
    page.wait_for_function("document.querySelector('#output').scrollTop >= 100")
    scroll_settled(page)
    geometry = page.evaluate("""() => {
      const panel = document.querySelector('#output');
      const strip = document.querySelector('#arms > .lf-tabstrip');
      return {edge: panel.getBoundingClientRect().top + panel.clientTop,
              header: strip.getBoundingClientRect().top};
    }""")
    assert geometry["header"] == pytest.approx(geometry["edge"], abs=0.5), geometry


def test_a_side_list_workspace_scrolls_its_list_and_its_item_apart(browser, serve):
    """A side list that is a workspace's body fills the window, and its list and its open
    item each scroll on their own, as a mail client's do: the page does not scroll,
    reading keys in the item move the item and not the list, and walking down a long
    list keeps the selected row in view and leaves the item where it stands. Where the
    list stacks over the item, as a large root font makes it in a narrow workspace, the
    item takes the room below the list rather than standing over it."""
    tickets = "".join(
        f'<lf-tab id="t-{n}" label="Ticket {n}" summary="sev {n % 3}">'
        + "".join(
            f'<p id="p-{n}-{line}">Line {line} of what went wrong with ticket {n}.</p>'
            for line in range(40)
        )
        + "</lf-tab>"
        for n in range(30)
    )
    source = leaf_page(
        "a long queue",
        f'<header><h1>Queue</h1></header><lf-tabs id="queue" list="side">{tickets}'
        "</lf-tabs>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 720)
    state = """() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const item = document.querySelector('#queue > lf-tab:not([hidden])');
      const selected = strip.querySelector('[aria-selected="true"]').getBoundingClientRect();
      const room = strip.getBoundingClientRect();
      return {page: document.scrollingElement.scrollHeight - innerHeight,
              list: [strip.scrollTop, strip.scrollHeight - strip.clientHeight],
              item: [item.scrollTop, item.scrollHeight - item.clientHeight],
              itemTop: item.getBoundingClientRect().top,
              stripBottom: room.bottom,
              selectedShown: selected.top >= room.top - 1 && selected.bottom <= room.bottom + 1};
    }"""
    before = page.evaluate(state)
    assert before["page"] <= 0, before
    assert before["list"][1] > 0 and before["item"][1] > 0, before

    page.locator("#p-0-2").click()
    page.keyboard.press("d")
    page.wait_for_function("() => document.querySelector('#t-0').scrollTop > 0")
    read = page.evaluate(state)
    assert read["list"][0] == 0 and read["page"] <= 0, read
    # Reading on while the window is too narrow to fill, where the page carries the
    # item, moves the place the item keeps when the workspace fills the window again.
    top_line = """() => {
      const item = document.querySelector('#t-0');
      const top = Math.max(item.getBoundingClientRect().top, 60);
      return [...item.querySelectorAll('p')]
        .findIndex(p => p.getBoundingClientRect().bottom > top + 2);
    }"""
    resized(page, 700, 720)
    rendered(page)
    narrow = page.evaluate(top_line)
    page.keyboard.press("d")
    page.wait_for_function(f"() => ({top_line})() > {narrow + 4}")
    # The place is recorded once the scroll rests, so the read and the resize wait
    # for that rather than landing mid-scroll.
    scroll_settled(page)
    rendered(page)
    read_on = page.evaluate(top_line)
    resized(page, 1280, 720)
    rendered(page)
    widened = page.evaluate(top_line)
    assert abs(widened - read_on) <= 2, (narrow, read_on, widened)

    page.get_by_role("tab", name="Ticket 0").focus()
    for _ in range(20):
        page.keyboard.press("ArrowDown")
    expect(page.get_by_role("tab", name="Ticket 20")).to_have_attribute(
        "aria-selected", "true"
    )
    walked = page.evaluate(state)
    assert walked["list"][0] > 0 and walked["selectedShown"], walked
    assert walked["itemTop"] == before["itemTop"] and walked["page"] <= 0, walked

    # A reader's large root font, there from first paint: a script setting it on the
    # open page would move the page without input.
    large = "<style>html { font-size: 20px }</style></head>"
    page = open_page(browser, serve(source.replace("</head>", large, 1)))
    resized(page, 730, 600)
    page.wait_for_function(
        """() => {
          const strip = document.querySelector('#queue > .lf-tabstrip').getBoundingClientRect();
          const item = document.querySelector('#queue > lf-tab:not([hidden])').getBoundingClientRect();
          return strip.right > item.left + 1 && item.top >= strip.bottom - 1;
        }"""
    )
    stacked = page.evaluate(state)
    assert stacked["page"] <= 0 and stacked["item"][1] > 0, stacked


def test_side_tabs_distinguish_withdrawn_obligations_from_answers(browser, serve):
    """A row's mark, and the words beside it, say its obligations are open until every
    one is answered, and withdrawal retires a request without claiming the user
    answered it: a row whose only obligation was withdrawn shows no mark, and one whose
    other obligation is answered shows the answer."""
    source = leaf_page(
        "Question outcomes",
        '<lf-tabs id="queue" list="side">'
        '<lf-tab id="only" label="Only withdrawn">'
        '<lf-options id="only-options" choose><lf-option id="only-pick">Only</lf-option></lf-options>'
        '</lf-tab><lf-tab id="mixed" label="Answer and withdrawal">'
        '<lf-options id="answered-options" choose><lf-option id="answered-pick" chosen>Keep</lf-option></lf-options>'
        '<lf-options id="withdrawn-options" choose><lf-option id="withdrawn-pick">Retire</lf-option></lf-options>'
        "</lf-tab></lf-tabs>",
    )
    page = open_page(browser, live_url(serve(source)))
    marks = page.locator("#queue .lf-tab-answer")
    expect(marks.nth(0)).to_have_attribute("data-lf-obligations", "open")
    expect(marks.nth(1)).to_have_attribute("data-lf-obligations", "open")
    # The open mark stands alone for the user's turn: the mark and the tally say it,
    # and the tab's description says it in words.
    expect(marks.nth(0)).to_have_text("")
    expect(page.get_by_role("tab").nth(0)).to_have_accessible_description(
        re.compile("To answer")
    )
    stamp_page(
        serve.page_dir,
        source.replace('id="only-options" choose', 'id="only-options"').replace(
            'id="withdrawn-options" choose', 'id="withdrawn-options"'
        ),
        "Retire unanswered requests",
    )
    wait_for_revision(page, 2)
    expect(marks.nth(0)).not_to_have_attribute("data-lf-obligations", re.compile(".*"))
    expect(marks.nth(1)).to_have_attribute("data-lf-obligations", "answered")
    expect(marks.nth(1)).to_have_text("Keep")


def test_a_queue_row_names_an_answer_whose_widget_module_arrives_last(browser, serve):
    """An obligation answered before the page loads is named once the page presents, however
    late the answering widget's module arrives: startup imports every module the
    document names before the first reading brings the obligation inventory. A longer ticket
    name and its summary keep their own lines beside a complete short outcome."""
    url = serve(
        leaf_page(
            "a late queue",
            """<lf-tabs id="queue" list="side">
<lf-tab id="t-a" label="ESC-4107 · Northwind Labs" summary="Company-wide SSO outage · Severity 1">
  <lf-ask id="ask-a"><h3 id="q-a">What happens to a?</h3>
    <lf-options id="o-a" choose>
      <lf-option id="o-a-fix"><strong>Fix</strong> Ship the patch.</lf-option>
      <lf-option id="o-a-close"><strong>Escalate to engineering</strong> Send the logs.</lf-option>
      <lf-option id="o-a-long"><strong>Escalate to the international engineering incident response team</strong> Send all logs.</lf-option>
    </lf-options>
  </lf-ask>
</lf-tab>
<lf-tab id="t-b" label="Ticket b"><p id="p-b">Nothing to decide.</p></lf-tab>
</lf-tabs>""",
            layout="workspace",
            head="<style>#queue {grid-template-columns:14rem minmax(0,1fr)}</style>",
        )
    )
    page = open_page(browser, live_url(url))
    posted = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": 1,
            "widget": "o-a",
            "action": "choose",
            "detail": {"value": ["o-a-fix"]},
        },
    )
    assert posted.ok, posted.text()
    held = []
    page.route("**/widgets/lf-options.js", lambda route: held.append(route))
    page.reload(wait_until="commit")
    holding(page, held, 1, "the options module")
    answer = page.locator("#queue .lf-tab-btn").first.locator(".lf-tab-answer")
    expect(answer).to_be_attached()
    held[0].continue_()
    page.unroute("**/widgets/lf-options.js")
    wait_until_ready(page)
    expect(answer).to_be_visible()
    expect(answer).to_have_text("Fix")
    row = page.locator("#queue .lf-tab-btn").first
    summary = row.locator(".lf-tab-summary")
    expect(summary).to_have_text("Company-wide SSO outage · Severity 1")
    assert answer.bounding_box()["y"] >= (
        summary.bounding_box()["y"] + summary.bounding_box()["height"]
    )
    before = row.bounding_box()
    page.locator("#o-a-close").get_by_role("checkbox").click()
    expect(answer).to_have_text("Escalate to engineering")
    assert row.bounding_box() == before
    words = answer.locator(".lf-tab-answer-words")
    expect(words).to_be_visible()
    assert words.evaluate("el => el.scrollWidth <= el.clientWidth")

    undo(page)
    expect(answer).to_have_text("Fix")
    # The undo is announced by the name the gesture's own announcement used.
    expect(page.locator(".lf-live")).to_have_text(
        "Undid: Chose “Escalate to engineering” · just now"
    )
    assert row.bounding_box() == before
    page.locator("#o-a-long").get_by_role("checkbox").click()
    expect(words).to_have_text(
        "Escalate to the international engineering incident response team"
    )
    assert words.evaluate("el => el.scrollWidth > el.clientWidth")
    assert row.bounding_box() == before


def test_a_queue_stands_its_items_under_their_groups(browser, serve):
    """Each run of neighbouring queue items that share a `group` stands under a label
    of it: a heading over the run in the column, and a word before the run's first tab
    in a phone's row, which comes into the row with that tab and stays at the row's
    start, clear of the press there, while a later tab of a run longer than the row is
    open, so the open item's group stays named. A tab too long to share the row with
    its label comes in whole instead, and the label scrolls with its run. A run of
    items with no group is ruled off from the run before it, so it never reads as part
    of that group. A label is not a tab, so the walk passes it by and assistive
    technology hears the group in each tab's description instead. A revision that
    moves an item to another group moves it under that group's label."""

    def item(key, group):
        name = f"Item {key} with a long name" + (
            " that no label can share a phone's row with" if key == "c" else ""
        )
        return (
            f'<lf-tab id="i-{key}" label="{name}"'
            + (f' group="{group}"' if group else "")
            + f' summary="{key} summary"><p id="p-{key}">Item {key}.</p></lf-tab>'
        )

    def queue(groups):
        return leaf_page(
            "Grouped queue",
            '<h1 id="title">Triage</h1><lf-tabs id="queue" list="side">'
            + "".join(item(key, group) for key, group in zip("abcdef", groups))
            + "</lf-tabs>",
        )

    url = live_url(serve(queue(["Merge", "Merge", "Close", None, "FYI", "FYI"])))
    page = open_page(browser, url)
    resized(page, 1200, 900)
    # Each run: its label's words, whether the label stands above (in the column) or
    # before (in the row) the run's first tab and is hidden from assistive technology
    # and the keyboard, whether a rule stands between it and the run before, and its
    # tabs.
    runs = """() => {
      const box = (el) => el.getBoundingClientRect();
      return [...document.querySelectorAll('#queue > .lf-tabstrip > .lf-tab-run')]
        .map((run) => {
          const label = run.querySelector(':scope > .lf-tab-group');
          const first = run.querySelector('[role="tab"]');
          const style = getComputedStyle(run);
          return {
            label: label?.textContent ?? null,
            placed: !label || (label.getAttribute('aria-hidden') === 'true'
              && label.tabIndex === -1
              && (box(label).bottom <= box(first).top + 0.5
                || box(label).right <= box(first).left + 0.5)),
            ruled: parseFloat(style.borderTopWidth) + parseFloat(style.borderLeftWidth) > 0,
            tabs: [...run.querySelectorAll('[role="tab"]')]
              .map((tab) => tab.getAttribute('aria-controls')),
          };
        });
    }"""
    expected = [
        {"label": "Merge", "placed": True, "ruled": False, "tabs": ["i-a", "i-b"]},
        {"label": "Close", "placed": True, "ruled": True, "tabs": ["i-c"]},
        {"label": None, "placed": True, "ruled": True, "tabs": ["i-d"]},
        {"label": "FYI", "placed": True, "ruled": True, "tabs": ["i-e", "i-f"]},
    ]
    assert page.evaluate(runs) == expected
    # The list says the group, so the open panel carries no stacked heading of it.
    assert page.evaluate(
        "() => getComputedStyle(document.getElementById('i-a'), '::before').content"
    ) in ("none", "normal")

    tabs = page.locator("#queue").get_by_role("tab")
    expect(tabs).to_have_count(6)
    expect(tabs.nth(2)).to_have_accessible_description("Close group. c summary")
    expect(tabs.nth(3)).to_have_accessible_description("d summary")
    tabs.nth(1).focus()
    page.keyboard.press("ArrowDown")
    expect(tabs.nth(2)).to_have_attribute("aria-selected", "true")
    expect(tabs.nth(2)).to_be_focused()

    revised = queue(["Merge", "Merge", "Merge", None, "FYI", "FYI"])
    wait_for_revision(page, stamp_page(serve.page_dir, revised, "Regroup")["revision"])
    expect(page.locator("#queue > .lf-tabstrip .lf-tab-group")).to_have_text(
        ["Merge", "FYI"]
    )
    expect(tabs.nth(2)).to_have_accessible_description("Merge group. c summary")

    # On a phone, loaded there so the row has its presses from the start. A run's
    # first tab comes into the row with its label, clear of the presses: at rest, and
    # walking back onto it from the run after. Its second tab, past the row's end,
    # comes in beside the label, which the row keeps at its start; its third, too long
    # to share the row with the label, comes in whole with the label out of its way.
    phone = open_page(
        browser,
        url,
        context=browser.new_context(viewport={"width": 390, "height": 844}),
    )
    assert phone.evaluate(runs) == [
        {
            "label": "Merge",
            "placed": True,
            "ruled": False,
            "tabs": ["i-a", "i-b", "i-c"],
        },
        {"label": None, "placed": True, "ruled": True, "tabs": ["i-d"]},
        {"label": "FYI", "placed": True, "ruled": True, "tabs": ["i-e", "i-f"]},
    ]
    # The open tab's label in the row before the tab, both clear of the presses.
    label_shown = """() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const room = strip.getBoundingClientRect();
      const open = strip.querySelector('[aria-selected="true"]');
      const tab = open.getBoundingClientRect();
      const label = open.parentElement.querySelector('.lf-tab-group')
        .getBoundingClientRect();
      const faces = [...strip.querySelectorAll('.lf-tabstrip-scroll > span')]
        .filter((face) => face.checkVisibility())
        .map((face) => face.getBoundingClientRect());
      return faces.length > 0 && room.left <= label.left
        && label.right <= tab.left + 0.5 && tab.right <= room.right
        && faces.every((face) => face.right <= label.left + 0.5 || tab.right <= face.left + 0.5);
    }"""
    # The open tab whole in the row and clear of the presses, with no label over it.
    tab_whole = """() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const room = strip.getBoundingClientRect();
      const open = strip.querySelector('[aria-selected="true"]');
      const tab = open.getBoundingClientRect();
      const label = open.parentElement.querySelector('.lf-tab-group')
        .getBoundingClientRect();
      const faces = [...strip.querySelectorAll('.lf-tabstrip-scroll > span')]
        .filter((face) => face.checkVisibility())
        .map((face) => face.getBoundingClientRect());
      return faces.length > 0 && room.left <= tab.left && tab.right <= room.right
        && (label.right <= tab.left + 0.5 || tab.right <= label.left + 0.5)
        && faces.every((face) => face.right <= tab.left + 0.5 || tab.right <= face.left + 0.5);
    }"""
    phone_tabs = phone.locator("#queue").get_by_role("tab")
    phone_tabs.first.click()
    phone.wait_for_function(label_shown)
    phone_tabs.first.focus()
    phone.keyboard.press("End")
    phone.keyboard.press("ArrowLeft")
    expect(phone_tabs.nth(4)).to_have_attribute("aria-selected", "true")
    phone.wait_for_function(label_shown)
    phone_tabs.nth(1).click()
    assert phone.evaluate(
        """() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      return strip.querySelector('.lf-tab-run').getBoundingClientRect().width
        > strip.clientWidth;
    }"""
    ), "the run is longer than the row"
    phone.wait_for_function(label_shown)
    phone_tabs.nth(2).click()
    phone.wait_for_function(tab_whole)
    assert phone.evaluate(
        """() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const tab = strip.querySelector('[aria-selected="true"]').getBoundingClientRect();
      const label = strip.querySelector('.lf-tab-group').getBoundingClientRect();
      const press = parseFloat(getComputedStyle(strip).scrollPaddingLeft);
      return tab.width + label.width > strip.clientWidth - 2 * press;
    }"""
    ), "the tab and its label cannot share the row between the presses"


def test_a_scrolling_queue_brings_a_group_s_heading_in_with_its_first_item(
    browser, serve
):
    """In a workspace whose queue scrolls on its own, walking up onto the first item of
    a group brings the group's heading into the list with it, so the item the user
    reaches is named by its group rather than standing under a heading cut off above
    the list."""
    groups = ["Merge", "Close", "FYI"]
    tickets = "".join(
        f'<lf-tab id="t-{n}" label="Ticket {n}" group="{groups[n // 10]}"'
        f' summary="sev {n % 3}"><p id="p-{n}">What went wrong with ticket {n}.</p>'
        "</lf-tab>"
        for n in range(30)
    )
    source = leaf_page(
        "a grouped queue",
        f'<header><h1>Queue</h1></header><lf-tabs id="queue" list="side">{tickets}'
        "</lf-tabs>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 500)
    page.get_by_role("tab", name="Ticket 11").click()
    # Cut the run's first item off above the list, its heading hidden over it.
    page.evaluate("""() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const first = strip.querySelector('[aria-controls="t-10"]');
      strip.scrollTop +=
        first.getBoundingClientRect().top - strip.getBoundingClientRect().top + 10;
    }""")
    page.get_by_role("tab", name="Ticket 11").focus()
    page.keyboard.press("ArrowUp")
    expect(page.get_by_role("tab", name="Ticket 10")).to_have_attribute(
        "aria-selected", "true"
    )
    page.wait_for_function("""() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const band = strip.getBoundingClientRect();
      const tab = strip.querySelector('[aria-selected="true"]').getBoundingClientRect();
      const heading = [...strip.querySelectorAll('.lf-tab-group')]
        .find((label) => label.textContent === 'Close').getBoundingClientRect();
      return strip.scrollTop > 0 && heading.top >= band.top - 0.5
        && heading.bottom <= tab.top + 0.5 && tab.bottom <= band.bottom + 0.5;
    }""")


def test_a_tab_strip_keeps_its_open_tab_in_its_one_row(browser, serve):
    """A strip whose names outrun its one row scrolls them sideways, and keeps the open
    tab in the row and clear of the press at either edge: when the window narrows under
    it, which turns a side list's column into a row, and when a walk opens another tab,
    the tab already open included. The press stands at the strip's edge, so no name
    shows unfaded beside it."""

    def views(key, summary):
        return "".join(
            f'<lf-tab id="{key}-{i}" label="View {key} {i}"'
            + (f' summary="sev {i} · suggested fix"' if summary else "")
            + f'><p id="{key}-words-{i}">View {key} {i}.</p></lf-tab>'
            for i in range(12)
        )

    source = leaf_page(
        "Long strips",
        '<h1 id="title">Strips</h1><section id="framed-section">'
        f'<lf-tabs id="framed">{views("framed", False)}</lf-tabs></section>'
        f'<lf-tabs id="queue" list="side">{views("queue", True)}</lf-tabs>'
        f'<section id="rtl-section" dir="rtl"><lf-tabs id="rtl">{views("rtl", False)}'
        "</lf-tabs></section>",
    )
    page = open_page(browser, serve(source))
    resized(page, 1200, 900)
    # The open tab inside the strip and clear of every press showing, with at least
    # `presses` of them showing.
    shown = """([id, presses]) => {
      const strip = document.querySelector(`#${id} > .lf-tabstrip`);
      const room = strip.getBoundingClientRect();
      const tab = strip.querySelector('[aria-selected="true"]').getBoundingClientRect();
      const faces = [...strip.querySelectorAll('.lf-tabstrip-scroll > span')]
        .filter((face) => face.checkVisibility())
        .map((face) => face.getBoundingClientRect());
      return strip.scrollWidth > strip.clientWidth && faces.length >= presses
        && room.left <= tab.left && tab.right <= room.right
        && faces.every((face) => face.right <= tab.left || tab.right <= face.left);
    }"""
    # Focus brings itself into view, so the tabs opened before the window narrows are
    # left unfocused.
    for name in ("View framed 11", "View queue 11"):
        tab = page.get_by_role("tab", name=name, exact=True)
        tab.click()
        tab.blur()
    resized(page, 390, 844)
    for strip in ("framed", "queue"):
        page.wait_for_function(shown, arg=[strip, 0])

    framed = page.locator("#framed").get_by_role("tab")
    framed.last.focus()
    page.keyboard.press("Home")
    expect(framed.first).to_have_attribute("aria-selected", "true")
    page.wait_for_function(shown, arg=["framed", 1])
    # Walking to the tab already open brings it back after a scroll took it away.
    page.evaluate("""() => {
      const strip = document.querySelector('#framed > .lf-tabstrip');
      strip.scrollLeft = strip.scrollWidth;
    }""")
    page.keyboard.press("Home")
    page.wait_for_function(shown, arg=["framed", 1])
    page.keyboard.press("ArrowLeft")
    expect(framed.last).to_have_attribute("aria-selected", "true")
    page.wait_for_function(shown, arg=["framed", 1])
    for _ in range(4):
        page.keyboard.press("ArrowLeft")
    expect(framed.nth(7)).to_have_attribute("aria-selected", "true")
    page.wait_for_function(shown, arg=["framed", 2])

    # In a right-to-left strip the names run from the right, so ArrowLeft is ahead.
    rtl = page.locator("#rtl").get_by_role("tab")
    rtl.first.focus()
    page.keyboard.press("ArrowLeft")
    expect(rtl.nth(1)).to_have_attribute("aria-selected", "true")
    page.wait_for_function(shown, arg=["rtl", 1])
    page.keyboard.press("ArrowRight")
    expect(rtl.first).to_have_attribute("aria-selected", "true")

    # Paging observes the live motion preference too, in both text directions.
    page.emulate_media(reduced_motion="reduce")
    for strip_id, sign in (("framed", 1), ("rtl", -1)):
        paged = page.evaluate(
            """([id, sign]) => {
          const strip = document.querySelector(`#${id} > .lf-tabstrip`);
          strip.scrollLeft = 0;
          const expected = sign * Math.min(
            0.8 * strip.clientWidth, strip.scrollWidth - strip.clientWidth);
          strip.querySelector('.lf-tabstrip-scroll[data-to="end"] > span').click();
          return {expected, actual: strip.scrollLeft};
        }""",
            [strip_id, sign],
        )
        assert paged["actual"] == pytest.approx(paged["expected"], abs=1), paged


def test_tab_reaches_the_open_panel_and_no_closed_one(browser, serve):
    """Tab from the open tab lands on its panel, whose prose holds nothing focusable,
    and never on a closed panel. hidden="until-found" skips what a closed panel holds
    but not the panel, so each one that kept its own stop put a zero-height stop in
    the walk: a queue of thirteen items took thirteen invisible presses to leave."""
    views = "".join(
        f'<lf-tab id="item-{i}" label="Item {i}"><p>Item {i} is prose.</p></lf-tab>'
        for i in range(4)
    )
    source = leaf_page(
        "Queue walk",
        f'<h1 id="title">Queue</h1><lf-tabs id="queue" list="side">{views}</lf-tabs>'
        '<p><button id="after">After the queue</button></p>',
    )
    page = open_page(browser, serve(source))
    resized(page, 1200, 900)
    tabs = page.locator("#queue").get_by_role("tab")

    for opened in (0, 2):
        tabs.nth(opened).click()
        expect(tabs.nth(opened)).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.locator(f"#item-{opened}")).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.locator("#after")).to_be_focused()


def test_root_tab_targets_remain_global(browser, serve):
    """Obligation travel crosses hidden tabs."""
    url = serve(ROOT_TABS_PAGE)
    page = open_page(
        browser,
        url + "#plan-stages",
        context=browser.new_context(viewport={"width": 1280, "height": 720}),
    )
    tabs = page.locator("#root-tabs")
    scroll_settled(page)
    expect(page.locator("#plan-stages")).to_be_in_viewport()
    arrival = page.evaluate("""() => ({
      target: document.querySelector('#plan-stages').getBoundingClientRect().top,
      strip: document.querySelector('#root-tabs > .lf-tabstrip').getBoundingClientRect().bottom
    })""")
    assert arrival["target"] >= arrival["strip"] - 1, arrival
    page.keyboard.press("m")
    expect(tabs.get_by_role("tab", name="Evidence", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator("#evidence-question")).to_be_in_viewport()
    page.locator('a[href="#plan-return"]').first.click()
    expect(tabs.get_by_role("tab", name="Plan", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator("#plan-return")).to_be_in_viewport()
    tabs.get_by_role("tab", name="Workbench", exact=True).click()
    pane_scroll_behavior(page, page.locator("#queue-pane"), "flow")


def test_parts_switch_without_moving_the_list_and_follow_history(browser, serve):
    """A switch between a page's parts is not fragment travel. The list stays where it is
    on screen under the page's title: a part never read opens at its start, at the top
    of the page level with the title, and a part read past its start reopens where the
    user left it. Pointer, keyboard, and Back/Forward agree, and a fresh load of the
    remembered part shows the page's top.

    A part's place is where the user was reading in it, not a pixel offset: a window
    resized while the part is hidden rewraps everything above that passage, and the part
    still reopens with the passage where the user left it."""
    url = serve(ROOT_PARTS_PAGE)
    page = open_page(browser, url)
    resized(page, 1280, 720)
    tabs = page.locator("#root-parts")
    plan = tabs.get_by_role("tab", name="Plan", exact=True)
    evidence = tabs.get_by_role("tab", name="Evidence", exact=True)
    summary = tabs.get_by_role("tab", name="Summary", exact=True)
    strip = page.locator("#root-parts > .lf-tabstrip")

    def switch(tab):
        before = strip.bounding_box()
        # Locator.click would scroll the list's tab into view first.
        box = tab.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(tab).to_have_attribute("aria-selected", "true")
        # Down the column, the open part's name wears the face a column strip's open
        # tab wears: a raised fill on the strip's ground, outlined, focused or not.
        face, ground, contour = tab.evaluate(
            """tab => {
              const name = getComputedStyle(tab.querySelector('.lf-tab-name'));
              const strip = getComputedStyle(tab.closest('.lf-tabstrip'));
              return [name.backgroundColor, strip.backgroundColor, name.boxShadow];
            }"""
        )
        assert face != ground and "inset" in contour, (face, ground, contour)
        at = settled()
        after = strip.bounding_box()
        assert all(after[k] == pytest.approx(before[k], abs=1) for k in after), (
            "the list moved",
            before,
            after,
        )
        return at

    def settled():
        scroll_settled(page)
        return page.evaluate("scrollY")

    def read_at(y):
        page.evaluate("y => scrollTo({top: y, behavior: 'instant'})", y)
        return settled()

    def at_start(panel):
        top = page.evaluate(
            "selector => document.querySelector(selector).getBoundingClientRect().top",
            panel,
        )
        title = page.locator("main > header").bounding_box()["y"]
        assert top == pytest.approx(title, abs=1)

    expect(plan).to_have_attribute("aria-selected", "true")
    assert settled() == 0
    # With the title on screen, a switch leaves it there.
    assert switch(summary) == 0
    assert switch(evidence) == 0
    assert page.url.endswith("#evidence-part")
    # Read Evidence past its start; Plan, never read, opens at its start, the top of the
    # page.
    evidence_read = read_at(450)
    plan_start = switch(plan)
    assert plan_start == 0
    at_start("#plan-part")
    # Summary fits under the title, so it opens with the title and nothing to scroll.
    assert switch(summary) == 0
    assert page.evaluate("document.scrollingElement.scrollHeight - innerHeight") <= 0
    # Evidence reopens where the user left it, and pressing the open tab moves nothing.
    assert switch(evidence) == pytest.approx(evidence_read, abs=2)
    assert switch(evidence) == pytest.approx(evidence_read, abs=2)

    # The keyboard walk is the same switch, down the list or across it, and focus stays
    # in the list.
    expect(evidence).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(plan).to_have_attribute("aria-selected", "true")
    expect(plan).to_be_focused()
    assert settled() == pytest.approx(plan_start, abs=2)
    page.keyboard.press("ArrowRight")
    expect(evidence).to_have_attribute("aria-selected", "true")
    expect(evidence).to_be_focused()
    assert settled() == pytest.approx(evidence_read, abs=2)

    # Back and Forward select the entry's part at the offset it was left at.
    page.go_back()
    expect(plan).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#plan-part")
    assert settled() == pytest.approx(plan_start, abs=2)
    page.go_forward()
    expect(evidence).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#evidence-part")
    assert settled() == pytest.approx(evidence_read, abs=2)

    # A link into a hidden part still opens it and lands on the target.
    page.evaluate("location.hash = 'part-plan-rollback'")
    expect(plan).to_have_attribute("aria-selected", "true")
    settled()
    expect(page.locator("#part-plan-rollback h2")).to_be_in_viewport()
    # Back to that link's entry from another part switches to the part holding it.
    switch(evidence)
    page.go_back()
    expect(plan).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#part-plan-rollback")

    # A reveal (a comment anchor, find-in-page) opens another part, and the entry the
    # user is located on names it, so pressing away and coming Back returns there.
    page.evaluate(
        """async () => {
          const {reveal} = await window.__lfCheckApi();
          const {retainUserIntent} = await window.__lfWidgetApi();
          reveal(document.querySelector('#evidence-part'), retainUserIntent());
        }"""
    )
    rendered(page)
    expect(evidence).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#evidence-part")
    switch(plan)
    page.go_back()
    expect(evidence).to_have_attribute("aria-selected", "true")

    # A fresh load that restores the remembered part opens at the page's top.
    switch(evidence)
    page.goto(url)
    expect(evidence).to_have_attribute("aria-selected", "true")
    assert page.url.endswith("#evidence-part")
    assert settled() == 0

    # The passage read in a hidden part keeps its place through a resize.
    passage = page.locator("#part-evidence-sign-in p").first
    below_landing_edge = """element => element.getBoundingClientRect().top
        - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)"""
    passage.evaluate("element => element.scrollIntoView({block: 'start'})")
    page.evaluate("scrollBy({top: -40, behavior: 'instant'})")
    settled()
    left = passage.evaluate(below_landing_edge)
    assert left == pytest.approx(40, abs=2)
    switch(plan)
    resized(page, 900, 720)
    switch(evidence)
    assert passage.evaluate(below_landing_edge) == pytest.approx(left, abs=2)


def test_a_strip_marks_its_open_tab_by_the_way_it_runs(browser, serve):
    """Whichever widget writes a strip, the open tab's mark follows which way the strip
    runs: down a column the open name paints a raised, outlined face; along a row the
    tab stands on a rule, with no fill, as a page tab's name does. A tab with a summary
    takes the rule at its foot, a line of its own under its last line, so the rule
    underlines the whole tab rather than the name above its summary. A page's parts and
    a queue each run both ways, so each shows both marks. The rule costs a tab no height,
    so a queue's row stays within the room its strip reserves before upgrade, and the
    row stands on its frame's ground rather than the column's tint. Forced colors draw
    only the open tab's rule."""
    queue = leaf_page(
        "Queue",
        '<h1 id="title">Queue</h1><section id="queue-section"><lf-tabs id="queue" '
        'list="side">'
        + "".join(
            f'<lf-tab id="q-{i}" label="Item {i}" summary="sev {i}">'
            f'<p id="q-words-{i}">Item {i}.</p></lf-tab>'
            for i in range(3)
        )
        + "</lf-tabs></section>",
    )
    mark = """strip => {
      const tab = strip.querySelector('[aria-selected="true"]');
      const name = getComputedStyle(tab.querySelector('.lf-tab-name'));
      const foot = getComputedStyle(strip.querySelector('.lf-tab-selection'));
      const rows = getComputedStyle(tab).gridTemplateRows.split(' ');
      return {flow: getComputedStyle(strip).flexDirection,
        filled: name.backgroundColor !== 'rgba(0, 0, 0, 0)',
        contoured: name.boxShadow.includes('inset'),
        nameRule: parseFloat(name.borderBottomWidth),
        rule: foot.display === 'none' ? 0 : parseFloat(foot.blockSize),
        ruleInk: foot.backgroundColor === name.color,
        lastRow: rows.at(-1), rows: rows.length,
        ground: getComputedStyle(strip).backgroundColor,
        frame: getComputedStyle(strip.parentElement).backgroundColor,
        height: strip.getBoundingClientRect().height,
        reserved: parseFloat(getComputedStyle(strip).minBlockSize)};
    }"""
    for source, strip in ((ROOT_PARTS_PAGE, "#root-parts"), (queue, "#queue")):
        page = open_page(browser, serve(source))
        resized(page, 1280, 720)
        column = page.locator(f"{strip} > .lf-tabstrip").evaluate(mark)
        assert column["flow"] == "column", column
        assert column["filled"] and column["contoured"], column
        assert column["rule"] == 0 and column["nameRule"] == 0, column
        resized(page, 390, 800)
        page.wait_for_function(
            "s => getComputedStyle(document.querySelector(s)).flexDirection === 'row'",
            arg=f"{strip} > .lf-tabstrip",
        )
        row = page.locator(f"{strip} > .lf-tabstrip").evaluate(mark)
        assert not row["filled"] and not row["contoured"], row
        assert row["rule"] == 2 and row["ruleInk"] and row["nameRule"] == 0, row
        assert row["lastRow"] == "2px", row
        if strip == "#queue":
            # Name, summary, then the rule.
            assert row["rows"] == 3, row
            assert row["height"] == pytest.approx(row["reserved"], abs=0.01), row
            assert row["ground"] == row["frame"], row
        page.emulate_media(forced_colors="active")
        ruled = page.locator(f"{strip} > .lf-tabstrip").evaluate(
            """strip => {
              const ground = getComputedStyle(strip).backgroundColor;
              const line = strip.querySelector('.lf-tab-selection');
              const selected = strip.querySelector('[aria-selected="true"] .lf-tab-mark');
              const style = getComputedStyle(line);
              const box = line.getBoundingClientRect();
              const at = selected.getBoundingClientRect();
              return {visible: style.display !== 'none' && style.backgroundColor !== ground,
                line: [box.left, box.top, box.width, box.height],
                selected: [at.left, at.top, at.width, at.height]};
            }"""
        )
        assert ruled["visible"], ruled
        assert ruled["line"] == pytest.approx(ruled["selected"], abs=0.5), ruled


def test_a_workspace_part_fills_the_window_from_first_paint(browser, serve):
    """A page of parts whose opening part is a workspace gives that workspace the
    window's height above the floating panel's row before the runtime upgrades the parts,
    so nothing grows or moves when it does. The row's room is the part's own end, so the
    part and the page reach the window's foot with no band below them."""
    source = leaf_page(
        "Workspace part",
        '<header><h1>Review</h1></header><lf-parts id="parts">'
        '<lf-part id="work" label="Work"><div id="surface" class="layout-workspace">'
        "<p>Work here.</p></div></lf-part>"
        '<lf-part id="notes" label="Notes"><article class="layout-column"><p>Notes.</p>'
        "</article></lf-part></lf-parts>",
        layout=None,
    )
    boot = []
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(source), wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"

        def heights():
            return page.evaluate("""() => {
              const block = document.querySelector('#surface').getBoundingClientRect();
              const part = document.querySelector('#work').getBoundingClientRect();
              const room = parseFloat(getComputedStyle(document.querySelector('#work'))
                .paddingBlockEnd);
              const scroller = document.scrollingElement;
              return {top: Math.round(block.top), height: Math.round(block.height),
                      room: Math.round(room),
                      under: Math.round(part.bottom - block.bottom - room),
                      foot: Math.round(innerHeight - part.bottom),
                      scrolls: scroller.scrollHeight - scroller.clientHeight};
            }""")

        first = heights()
        assert first["height"] > 400 and first["room"] > 0, first
        assert first["under"] == first["foot"] == 0, first
        assert first["scrolls"] <= 0, first
        boot.pop().continue_()
        wait_until_ready(page)
        assert heights() == first
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


@pytest.mark.parametrize("layout", ["column", "sidebar", "workspace"])
def test_wide_evidence_in_a_part_takes_the_room_it_would_on_a_page_of_its_own(
    browser, serve, layout
):
    """A part of a page of parts is laid out as a page of its own Layout, so a `wide` or
    `available` table in it takes the box and the column widths, measured from the
    part's edge, that its twin takes on a page with that Layout as wide as the part: at
    first paint, before the runtime has drawn the list, then at a desktop window, and on
    a phone. A boxed set's panel draws a frame, so the same table there stays inside it.
    Each table has twelve columns, so on a column page, where a table granted room takes
    what its columns need, it needs the room."""

    def tables(where):
        heads = "".join(f"<th>Case {i}</th>" for i in range(12))
        cells = "<td>Result</td>" * 12
        return "".join(
            f'<table id="{where}-{space}" data-width="{space}"><thead><tr>{heads}'
            f"</tr></thead><tbody><tr>{cells}</tr></tbody></table>"
            for space in ("wide", "available")
        )

    content = (
        f'<h1 id="t">Evidence</h1><p id="prose">Prose.</p>{tables("in")}'
        f'<section><lf-tabs id="boxed"><lf-tab id="boxed-open" label="Boxed">{tables("boxed")}'
        '</lf-tab><lf-tab id="boxed-other" label="Other"><p>Other.</p></lf-tab></lf-tabs>'
        "</section>"
    )
    # A sidebar page with no aside holds one flow: the page's own CSS gives each block
    # the row.
    head = (
        "<style>.layout-sidebar > * { flex-basis: 100%; }</style>"
        if layout == "sidebar"
        else ""
    )
    parts = leaf_page(
        "Evidence in a part",
        '<header><h1>Evidence</h1></header><lf-parts id="parts">'
        f'<lf-part id="compare" label="Compare"><div id="box" class="layout-{layout}">'
        f'{content}</div></lf-part><lf-part id="notes" label="Notes">'
        '<article class="layout-column"><p>Notes.</p></article></lf-part></lf-parts>',
        head=head,
        layout=None,
    )
    alone = leaf_page("Evidence on a page", content, head=head, layout=layout)
    measure = """() => {
      const box = document.getElementById('box') ?? document.querySelector('main');
      const shell = box.parentElement;
      const origin = shell.getBoundingClientRect().left + shell.clientLeft;
      return {width: shell.clientWidth, ...Object.fromEntries(
        ['prose', 'in-wide', 'in-available', 'boxed-open', 'boxed-wide',
         'boxed-available'].map(id => {
          const el = document.getElementById(id), box = el.getBoundingClientRect();
          return [id, {left: Math.round(box.left - origin), width: Math.round(box.width),
            columns: Math.round(
              el.querySelector('thead')?.getBoundingClientRect().width ?? 0)}];
        }))};
    }"""

    def boxed(state, at):
        for space in ("wide", "available"):
            table, panel = at[f"boxed-{space}"], at["boxed-open"]
            assert table["left"] >= panel["left"], (state, space, at)
            assert table["left"] + table["width"] <= panel["left"] + panel["width"], (
                state,
                space,
                at,
            )

    def twin(at, state):
        page = open_page(browser, serve(alone))
        resized(page, at["width"], 900)
        alone_at = page.evaluate(measure)
        page.close()
        assert alone_at == at, (state, alone_at, at)

    boot = []
    context = browser.new_context(viewport={"width": 1600, "height": 900})
    page = context.new_page()
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(parts), wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"
        first = page.evaluate(measure)
        boot.pop().continue_()
        wait_until_ready(page)
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")
    desktop = page.evaluate(measure)
    assert desktop == first
    boxed("desktop", desktop)
    twin(desktop, "desktop")
    assert root_overflow(page) == 0
    # Wider than the reading column, which a workspace's prose does not keep.
    assert desktop["in-wide"]["width"] > 720, desktop
    resized(page, 390, 800)
    phone = page.evaluate(measure)
    boxed("phone", phone)
    assert root_overflow(page) == 0
    twin(phone, "phone")


def test_the_list_of_parts_lands_its_last_name_above_the_floating_row(browser, serve):
    """The list of parts runs to the window's foot, under the floating panel's row where
    a narrow window puts the row over the column. A name the keyboard moves to still
    lands above the row, as a landing in the page does. The window leaves the list
    100 px between its title and the row, whatever height the host's fonts give the
    title, so the list scrolls to reach its last name."""
    page = open_page(browser, serve(ROOT_PARTS_PAGE))
    resized(page, 800, 900)
    title = page.locator("main > header").bounding_box()
    under_row = 900 - page.locator(".lf-fp-row").bounding_box()["y"]
    resized(page, 800, round(title["y"] + title["height"] + 100 + under_row))
    tabs = page.locator("#root-parts")
    tabs.get_by_role("tab", name="Plan", exact=True).focus()
    page.keyboard.press("End")
    last = tabs.get_by_role("tab", name="Summary", exact=True)
    expect(last).to_be_focused()
    scroll_settled(page)
    row = page.locator(".lf-fp-row").bounding_box()
    box = last.bounding_box()
    assert box["x"] < row["x"] + row["width"], (box, row)
    assert box["y"] + box["height"] <= row["y"], (box, row)


def test_a_short_window_keeps_the_list_of_parts_in_reach(browser, serve):
    """The column stands fixed in the window, so a title taller than a short window
    scrolls on its own and leaves the list a few names' room, rather than pushing the
    list below the window's foot."""
    page = open_page(browser, serve(ROOT_PARTS_PAGE))
    resized(page, 1280, 300)
    tabs = page.locator("#root-parts")
    tabs.get_by_role("tab", name="Plan", exact=True).focus()
    page.keyboard.press("End")
    last = tabs.get_by_role("tab", name="Summary", exact=True)
    expect(last).to_be_focused()
    scroll_settled(page)
    box = last.bounding_box()
    assert 0 <= box["y"] and box["y"] + box["height"] <= 300, box


def test_a_phone_keeps_the_list_of_parts_in_reach_and_each_part_s_place(browser, serve):
    """On a phone the list of parts is a row over the open part, and it sticks there as
    page tabs' strip does: the reader reaches another part from deep in this one, the
    part they leave keeps their place, and a link lands below the row rather than under
    it."""
    page = open_page(browser, serve(ROOT_PARTS_PAGE))
    resized(page, 390, 800)
    tabs = page.locator("#root-parts")
    plan = tabs.get_by_role("tab", name="Plan", exact=True)
    evidence = tabs.get_by_role("tab", name="Evidence", exact=True)
    strip = page.locator("#root-parts > .lf-tabstrip")

    def settled():
        scroll_settled(page)
        return page.evaluate("scrollY")

    def press(tab):
        # Locator.click would scroll the stuck row's tab to where the row stands in
        # flow first.
        box = tab.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    evidence.click()
    expect(evidence).to_have_attribute("aria-selected", "true")
    page.evaluate("scrollTo({top: 1000, behavior: 'instant'})")
    read = settled()
    assert read == 1000
    row = strip.bounding_box()
    assert 0 <= row["y"] < 40, row
    press(plan)
    expect(plan).to_have_attribute("aria-selected", "true")
    settled()
    press(evidence)
    expect(evidence).to_have_attribute("aria-selected", "true")
    assert settled() == pytest.approx(read, abs=2)

    page.evaluate("location.hash = 'part-plan-rollback'")
    expect(plan).to_have_attribute("aria-selected", "true")
    settled()
    row = strip.bounding_box()
    heading = page.locator("#part-plan-rollback h2").bounding_box()
    assert heading["y"] >= row["y"] + row["height"] - 1, (heading, row)


@pytest.mark.parametrize("route", ["pointer", "keyboard", "touch"])
def test_side_list_history_restores_the_reading_offset_of_each_entry(
    browser, serve, route
):
    """A root side list reveals the history view without losing its return offset."""
    body = '<h1>Views</h1><p>Shared context.</p><lf-tabs id="views" list="side">'
    body += "".join(
        f'<lf-tab id="view-{name.lower()}" label="{name}">'
        + "".join(
            f"<p>{name} paragraph {i}. Reading continues here.</p>" for i in range(180)
        )
        + "</lf-tab>"
        for name in ("A", "B")
    )
    body += "</lf-tabs>"
    head = """<style>
    @container (width >= 36rem) {
      #views > .lf-tabstrip {position: sticky; top: var(--lf-top, 0px);
        align-self: start; max-block-size: 100dvh; overflow-y: auto;}
    }
    </style>"""
    context = browser.new_context(has_touch=route == "touch")
    page = open_page(
        browser, serve(leaf_page("Reading views", body, head=head)), context=context
    )
    resized(page, 1600, 1000)
    a = page.get_by_role("tab", name="A", exact=True)
    b = page.get_by_role("tab", name="B", exact=True)
    page.evaluate("scrollTo({top: 3000, behavior: 'instant'})")
    scroll_settled(page)
    box = b.bounding_box()
    assert box is not None and 0 <= box["y"] < 1000
    if route == "keyboard":
        # Walk from the selected tab; focus already stands there after a press.
        a.click()
        page.evaluate("scrollTo({top: 3000, behavior: 'instant'})")
        page.keyboard.press("ArrowDown")
    elif route == "touch":
        b.tap()
    else:
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(b).to_have_attribute("aria-selected", "true")
    rendered(page)
    page.evaluate("scrollTo({top: 4000, behavior: 'instant'})")
    scroll_settled(page)
    for direction, tab, offset in [
        ("back", a, 3000),
        ("forward", b, 4000),
        ("back", a, 3000),
    ]:
        getattr(page, f"go_{direction}")()
        expect(tab).to_have_attribute("aria-selected", "true")
        page.evaluate("window.navigation.transition?.finished")
        scroll_settled(page)
        assert page.evaluate("scrollY") == pytest.approx(offset, abs=2)
