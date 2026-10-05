"""Board, suggestion, ask, and widget composition tests."""

import re
from itertools import pairwise
from pathlib import Path

import pytest
import turbohtml
from interact_support import _start, append_carried_log_record, append_command
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf import service as service_model
from leaf import thread as thread_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.render_gate import version as render_gate_model
from leaf.schema import ELEMENT_ID
from leaf_dev.example_data import patch_manifest
from playwright.sync_api import expect
from render_cases_interaction import (
    ALL_ASKS_IN_ORDER,
    ASK_IN_A_CARD_PAGE,
    ASK_WITH_CONTEXT_PAGE,
    ASKS_IN_A_ROW_PAGE,
    ASKS_IN_ORDER,
    ASKS_PAGE,
    CHANGE_SHAPES_PAGE,
    CHIP_PAGE,
    COLLAPSED_PAGE,
    HOLD_MOTION,
    MESSAGE_ROOM_PAGE,
    PROPOSED_PAGE,
    QUEUE_ROW_SAYS,
    REBUILT_INLINE_PAGE,
    ROOM_HELD,
    ROOM_WIDGETS,
    ROOMS,
    SHORT_SUGGESTION,
    STANDING_ASK,
    SUGGESTION_IN_CONTEXT_PAGE,
    SUGGESTION_PAGE,
    SWAP_PAGE,
    THREAD_DIFF_PAGE,
    live_url,
)
from render_cases_layout import (
    banner_control,
    toggle_queue,
    unfolded_button,
    with_one_ask,
)
from render_cases_navigation import (
    BINDING_BADGE_PAGE,
    actions,
    painted,
)
from render_cases_widgets import (
    BAD_CHARTS,
    CHART_IN_A_MESSAGE_PAGE,
    CHART_MARKS,
    CHART_PAGE,
    DIFF_CLIPPING,
    DIFF_LANDING,
    DIFF_PRESS,
    DIFF_ROW_FILL,
    DIFF_ROW_PLACEMENT,
    LONG_LINE_DIFF_PAGE,
    MANIFEST_DIFF_PAGE,
    MESSAGE_CHART,
    MULTI_HUNK_PATCH,
    PANE_DIFF_PAGE,
    SQUEEZED_BOARD_PAGE,
    chart_markup,
)
from render_harness import (
    BOARD_PAGE,
    FEATURE_GALLERY,
    LONG_PAGE,
    RELEASE_FOCUS,
    REPLY_HOST_PAGE,
    CutOff,
    active_digit_bindings,
    compare_with,
    consume_browser_errors,
    displayed,
    expect_asks_answered,
    expect_banner_control_offered,
    expect_comment_notes,
    fills_the_window,
    holding,
    leaf_page,
    margins_laid_out,
    open_page,
    pane_posture,
    panel_settled,
    plant_quiet_word,
    post_event,
    refuse,
    regions_side_by_side,
    resized,
    root_overflow,
    round_trip,
    scroll_settled,
    select,
    select_words,
    sending,
    shortcut_bar_text,
    stamp_page,
    suggestion_control,
    take_browser_errors,
    told,
    undo,
    wait_for_revision,
    write,
)

DRAG_HELD = (
    "async () => (await window.__lfRuntimeImport("
    "'/runtime/widget-elements.js')).dragHeld()"
)

pytestmark = pytest.mark.nightly


def observe_live_region(page):
    """Record announcements without disturbing the renderer-owned live region."""
    page.evaluate(
        """() => {
          const live = document.querySelector('.lf-live');
          const changes = [];
          window.__lfLiveRegionChanges = changes;
          new MutationObserver(() => changes.push(live.textContent))
            .observe(live, {childList: true, characterData: true, subtree: true});
        }"""
    )


WORKSPACE_PAGE = leaf_page(
    "workspace reading regions",
    """
  <header>
    <h1>Review queue</h1>
    <p id="review-status"><span class="tag warn">3 waiting</span></p>
  </header>
  <div id="review-regions">
    <lf-pane id="queue" label="Items">
      <div>
        <p>Queue start</p>
        <div style="height: 1100px"></div>
        <p>Queue end</p>
      </div>
    </lf-pane>
    <lf-pane id="detail" label="Selected item">
      <div>
        <p>Detail start</p>
        <div style="height: 1100px"></div>
        <p>Detail end</p>
      </div>
    </lf-pane>
  </div>
  <footer>2 items</footer>
""",
    head=regions_side_by_side("review-regions"),
    layout="workspace",
)


def test_bounded_text_document_keeps_its_caption_above_the_scrolling_source(
    browser, serve
):
    source = leaf_page(
        "Captured document",
        '<h1>Capture</h1><lf-text-document id="capture" source="capture" '
        'label="A captured source" data-bound="start"></lf-text-document>',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "capture", "line of source\n" * 100)
    page = open_page(browser, url)
    capture = page.locator("#capture")
    caption = capture.locator("figcaption")
    listing = capture.locator("pre")
    expect(caption).to_be_visible()
    assert capture.evaluate("el => el.scrollHeight === el.clientHeight")
    assert listing.evaluate("el => el.scrollHeight > el.clientHeight")
    assert caption.evaluate(
        "el => Math.abs(el.getBoundingClientRect().width - "
        "el.parentElement.getBoundingClientRect().width) <= 2"
    )


def test_a_root_workspace_bounds_independent_regions_and_flows_when_it_cannot_fit(
    browser, serve
):
    """The workspace Layout takes the whole window, wider than the wide page's capped
    frame, and its height below the banner: each pane's body scrolls on its own. Its
    header is one row, the title with the status beside it, so the panes keep the
    window. A window too short to hold it hands the scroll to the page."""
    frame = """() => {
      const main = document.querySelector('main');
      const style = getComputedStyle(main);
      const box = main.getBoundingClientRect();
      return [box.left + parseFloat(style.paddingLeft),
              box.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)];
    }"""
    declared = open_page(
        browser,
        serve(
            WORKSPACE_PAGE.replace('class="layout-workspace"', 'class="layout-wide"')
        ),
    )
    resized(declared, 1920, 720)
    wide = declared.evaluate(frame)
    declared.close()
    page = open_page(browser, serve(WORKSPACE_PAGE))
    resized(page, 1920, 720)
    workspace = page.locator("main")
    queue_pane = page.locator("#queue")
    queue = page.locator("#queue > :not(header, footer)")
    detail = page.locator("#detail > :not(header, footer)")

    pane_posture(page, queue_pane, "bounded")
    fills_the_window(page, workspace, True)
    own = page.evaluate(frame)
    assert own[0] < wide[0] and own[1] > wide[1], (own, wide)
    header = page.evaluate(
        """() => {
          const title = document.querySelector('main > header h1');
          const status = document.getElementById('review-status');
          const t = title.getBoundingClientRect(), s = status.getBoundingClientRect();
          return {oneRow: s.top < t.bottom && s.left >= t.right};
        }"""
    )
    assert header["oneRow"], header
    assert page.evaluate("() => document.scrollingElement.scrollTop") == 0
    readings = page.evaluate(
        """() => {
          const body = id => document.querySelector(`#${id} > :not(header, footer)`);
          const queue = body('queue');
          const detail = body('detail');
          return {queue: [queue.clientHeight, queue.scrollHeight],
                  detail: [detail.clientHeight, detail.scrollHeight]};
        }"""
    )
    assert readings["queue"][1] > readings["queue"][0], readings
    assert readings["detail"][1] > readings["detail"][0], readings
    expect(queue).to_have_attribute("data-lf-more-below", "")
    expect(detail).to_have_attribute("data-lf-more-below", "")
    queue.evaluate("el => el.scrollTop = 300")
    page.wait_for_function(
        "() => document.querySelector('#queue > :not(header, footer)').scrollTop > 0"
    )
    assert detail.evaluate("el => el.scrollTop") == 0
    # A pane that leaves the document and returns registers its body again, so the cue
    # that the body holds more comes back with it.
    queue_pane.evaluate(
        """owner => {
          const parent = owner.parentNode;
          const next = owner.nextSibling;
          owner.remove();
          parent.insertBefore(owner, next);
        }"""
    )
    pane_posture(page, queue_pane, "bounded")
    expect(queue).to_have_attribute("data-lf-more-below", "")
    queue.evaluate("el => el.scrollTop = el.scrollHeight")
    expect(queue).not_to_have_attribute("data-lf-more-below", "")
    queue.evaluate(
        """el => {
          const more = document.createElement('div');
          more.style.height = '200px';
          el.append(more);
          el.dispatchEvent(new CustomEvent('lf-layout', {bubbles: true}));
        }"""
    )
    expect(queue).to_have_attribute("data-lf-more-below", "")

    # A window too short to hold the regions hands the scroll to the page, and the
    # page's grid keeps the columns its width allows: the hold decides heights, not
    # placement.
    resized(page, 1280, 420)
    pane_posture(page, queue_pane, "flow")
    fills_the_window(page, workspace, False)
    flow = page.evaluate(
        """() => {
          const queue = document.querySelector('#queue').getBoundingClientRect();
          const detail = document.querySelector('#detail').getBoundingClientRect();
          return {queue, detail};
        }"""
    )
    assert flow["detail"]["left"] >= flow["queue"]["right"] - 1, flow
    assert flow["queue"]["height"] > 1100, flow
    expect(queue).not_to_have_attribute("data-lf-more-below", "")
    expect(detail).not_to_have_attribute("data-lf-more-below", "")
    # The posture is the window's, not the one the user came from.
    resized(page, 1280, 720)
    pane_posture(page, queue_pane, "bounded")
    fills_the_window(page, workspace, True)


PANE_BAND_PAGE = leaf_page(
    "A pane that opens on its words",
    """
  <div id="band-regions">
    <lf-pane id="band-queue" label="Queue"><ul><li>First ticket</li></ul></lf-pane>
    <lf-pane id="band-detail" label="Detail">
      <div id="band-body">
        <section id="band-ticket">
          <p class="eyebrow" id="band-eyebrow">ESC-1 · sev 1</p>
          <h2>The ticket's title</h2>
          <p>What happened.</p>
        </section>
        <section><h2>Another ticket</h2><p>Its account.</p></section>
      </div>
    </lf-pane>
  </div>
""",
    head=regions_side_by_side("band-regions", "1fr 2fr"),
    layout="workspace",
)


def test_a_pane_opens_on_its_first_words_through_a_bare_wrapper(browser, serve):
    """A pane's body trims the margin at its top edge, and a declared section wrapping its
    content passes its first child's margin to that edge. The eyebrow above a heading
    carries the heading's 48px, which stood as an empty band at the top of the pane;
    the body's own padding is all that stands above the first words."""
    page = open_page(browser, serve(PANE_BAND_PAGE))
    resized(page, 1440, 900)
    rendered(page)
    above = page.evaluate(
        """() => {
          const body = document.getElementById('band-body');
          const top = body.getBoundingClientRect().top
            + parseFloat(getComputedStyle(body).paddingTop);
          return document.getElementById('band-eyebrow').getBoundingClientRect().top - top;
        }"""
    )
    assert abs(above) < 1, above


ROOT_TABS_PAGE = Path(__file__).parent / "fixtures/pages/root-tabs.html"


def test_root_tabs_switch_views_without_moving_the_strip_and_follow_history(
    browser, serve
):
    """A tab switch is not fragment travel. The strip stays where it is on screen: a view
    never read opens at its start when the strip is stuck and leaves the shared header
    alone when it is not, and a view read past its start reopens where the user left it.
    Pointer, keyboard, and Back/Forward agree, and a fresh load of the remembered view
    shows the page's top."""
    url = serve(ROOT_TABS_PAGE)
    page = open_page(browser, url)
    resized(page, 1280, 720)
    tabs = page.locator("#root-tabs")
    plan = tabs.get_by_role("tab", name="Plan", exact=True)
    evidence = tabs.get_by_role("tab", name="Evidence", exact=True)

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
    assert switch(evidence) == 0
    assert page.url.endswith("#evidence-tab")
    # Read Evidence past its start; Plan, never read, opens at its start under the
    # stuck strip rather than at the top of the page.
    evidence_read = read_at(450)
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
    # user stands on then names it, so pressing away and coming Back returns there.
    page.evaluate(
        """async () => {
          const {reveal} = await window.__lfRuntimeImport('/runtime/widget-elements.js');
          const {retainUserIntent} = await window.__lfRuntimeImport('/runtime/user-intent.js');
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


def test_a_root_view_keeps_its_place_through_a_resize_while_hidden(browser, serve):
    """A view's place is where the user was reading in it, not a pixel offset: a window
    resized while the view is hidden rewraps everything above that passage, and the
    view still reopens with the passage where the user left it."""
    page = open_page(browser, serve(ROOT_TABS_PAGE))
    resized(page, 1280, 720)
    tabs = page.locator("#root-tabs")
    plan = tabs.get_by_role("tab", name="Plan", exact=True)
    evidence = tabs.get_by_role("tab", name="Evidence", exact=True)
    passage = page.locator("#evidence-sign-in p").first
    below_landing_edge = """element => element.getBoundingClientRect().top
        - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)"""

    def switch(tab):
        box = tab.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(tab).to_have_attribute("aria-selected", "true")
        scroll_settled(page)

    switch(evidence)
    passage.evaluate("element => element.scrollIntoView({block: 'start'})")
    page.evaluate("scrollBy({top: -40, behavior: 'instant'})")
    scroll_settled(page)
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


def test_a_stuck_root_tab_strip_hides_what_passes_under_it(browser, serve):
    """The root strip sticks under the banner and paints over the document, so what
    passes under it is not on screen: `shownRect`, the one reading of that, clips a
    block behind the stuck strip to the strip's foot, which the strip's stated height
    puts at `--lf-top` inside its panels. At the top of the page the strip is in flow
    and hides nothing."""
    page = open_page(browser, serve(ROOT_TABS_PAGE) + "#plan-tab")
    resized(page, 1280, 720)
    READ = """async () => {
      const geometry = await window.__lfRuntimeImport('/runtime/geometry.js');
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
    assert stuck["strip"]["top"] > 0, stuck
    assert stuck["behind"]["top"] < stuck["strip"]["bottom"] < stuck["behind"]["bottom"]
    assert stuck["band"] == pytest.approx(stuck["strip"]["bottom"], abs=0.5), stuck
    assert stuck["shown"] == pytest.approx(stuck["strip"]["bottom"], abs=0.5), stuck


def test_sticky_headers_stack_so_a_diff_in_a_page_tab_pins_under_the_strip(
    browser, serve
):
    """A diff's file header in a page tab pins under the stuck tab strip rather than
    over it: each sticky header has a stated height and adds it to `--lf-top` for what
    it stands over. A landing on one of the diff's rows arrives below both headers, and
    the part of a row under the diff's header reads as not on screen."""
    path = "src/lib.rs"
    rows = "".join(f"+    let value_{i} = {i};\n" for i in range(200))
    patch = (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -1 +1,201 @@\n fn main() {{\n{rows}"
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Stacked headers",
                '<h1>Stacked</h1><lf-tabs id="root-tabs">'
                '<lf-tab id="diff-tab" label="Diff"><lf-diff id="patch"><pre>'
                + patch
                + '</pre></lf-diff></lf-tab><lf-tab id="notes-tab" label="Notes">'
                "<p>Notes.</p></lf-tab></lf-tabs>",
            )
        ),
    )
    resized(page, 1280, 720)
    page.wait_for_function("() => document.querySelector('lf-diff.lf-rendered')")
    read = page.evaluate(
        """async () => {
        const geometry = await window.__lfRuntimeImport('/runtime/geometry.js');
        const box = (el) => el.getBoundingClientRect();
        const strip = document.querySelector('#root-tabs > .lf-tabstrip');
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


def test_a_table_at_a_pane_top_is_under_no_sticky_header(browser, serve):
    """A workspace pane's body starts `--lf-top` at minus its top padding and a table
    starts it at 0, since each scrolls; neither stacks a header, so a cell scrolled to
    just below the pane's top edge reads as shown from where it stands."""
    filler = "<p>Filler.</p>" * 40
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Pane table",
                '<header><h1>Pane table</h1></header><lf-pane id="p1" label="Detail">'
                "<header><h2>Detail</h2></header><div><p>Lead paragraph.</p>"
                '<table id="t1"><tbody><tr><td id="c1">one</td><td>1</td></tr>'
                "<tr><td>two</td><td>2</td></tr></tbody></table>"
                + filler
                + "</div></lf-pane>",
                layout="workspace",
            )
        ),
    )
    resized(page, 1280, 720)
    read = page.evaluate(
        """async () => {
        const geometry = await window.__lfRuntimeImport('/runtime/geometry.js');
        const body = document.querySelector('#p1 > div');
        const cell = document.querySelector('#c1');
        const band = geometry.shownBand(body);
        body.scrollTop += cell.getBoundingClientRect().top - band.top - 5;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return {
            band: geometry.shownBand(body).top,
            cell: cell.getBoundingClientRect().top,
            shown: geometry.shownRect(cell, new Map())?.top,
        };
    }"""
    )
    assert read["cell"] == pytest.approx(read["band"] + 5, abs=1), read
    assert read["shown"] == pytest.approx(read["cell"], abs=0.5), read


def test_embedded_tab_selection_preserves_the_document_reading_position(browser, serve):
    source = (
        ROOT_TABS_PAGE.read_text()
        .replace('<lf-tabs id="root-tabs">', '<section><lf-tabs id="root-tabs">')
        .replace("</lf-tabs>", "</lf-tabs></section>")
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 720)
    tabs = page.locator("#root-tabs")
    expect(tabs).to_have_attribute("data-lf-tabs-flow", "box")
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


def test_back_to_a_fragment_the_page_has_hidden_since_lands_on_it(browser, serve):
    """Back restores the offset an entry was left at, unless the element its fragment
    names is no longer shown: the user closed its tab since, so that offset belongs to
    a page that has changed, and landing the fragment, which opens the tab, is the
    answer. The tab set is embedded, so it keeps no history of its own."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(60))
    url = serve(
        leaf_page(
            "Back to a hidden fragment",
            '<h1 id="top">Hidden fragment</h1><p><a href="#x">To x</a></p>'
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
    target = page.locator("#x")

    page.get_by_role("link", name="To x").click()
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
    """Page tabs are sections of one page: on a wide page the header, the strip and the
    open panel share main's left edge and the panel takes main's width."""
    source = ROOT_TABS_PAGE.read_text().replace(
        '<main class="layout-column">', '<main class="layout-wide">', 1
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    tabs = page.locator("#root-tabs")
    expect(tabs).to_have_attribute("data-lf-tabs-flow", "page")
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


@pytest.mark.parametrize("layout", ["column", "wide", "workspace"])
def test_wide_evidence_in_a_page_tab_takes_the_room_it_would_outside_one(
    browser, serve, layout
):
    """A page tab is a section of the page, so a `wide` or `available` table in its
    open panel takes the box and the column widths its twin outside the set takes: at
    first paint, before the runtime has drawn the strip, then at a desktop window, with
    the thread panel open over it, and on a phone. A boxed set's panel draws a frame,
    so the same table there stays inside it."""

    def tables(where):
        return "".join(
            f'<table id="{where}-{space}" data-width="{space}"><thead><tr><th>Case</th>'
            "<th>Result</th></tr></thead><tbody><tr><td>One</td><td>Two</td></tr>"
            "</tbody></table>"
            for space in ("wide", "available")
        )

    source = leaf_page(
        "Evidence in page tabs",
        f'<h1 id="t">Evidence in page tabs</h1><p id="prose">Prose.</p>{tables("out")}'
        f'<lf-tabs id="root-tabs"><lf-tab id="compare" label="Compare">{tables("in")}'
        '</lf-tab><lf-tab id="notes" label="Notes"><p>Notes.</p></lf-tab></lf-tabs>'
        f'<section><lf-tabs id="boxed"><lf-tab id="boxed-open" label="Boxed">{tables("boxed")}'
        '</lf-tab><lf-tab id="boxed-other" label="Other"><p>Other.</p></lf-tab></lf-tabs>'
        "</section>",
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
    expect(page.locator("#root-tabs")).to_have_attribute("data-lf-tabs-flow", "page")
    assert twins("desktop") == first
    assert first["in-wide"]["width"] > first["prose"]["width"], first
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    twins("panel open")
    resized(page, 390, 800)
    twins("phone")


def test_a_side_list_is_a_queue_beside_the_item_it_opens(browser, serve):
    """`list="side"` stands a tab set's list beside its panels: a queue whose items open
    one at a time. Where the set holds both the list is a column left of the open panel,
    walked down as well as across; on a phone it is a row above the panel, so the open
    item never lands below the whole queue. A row carries its panel's summary under its
    name, and once its item's Ask is answered, a check and the picked option's title
    beside the name, said in the tab's description too. Answered is the log's reading,
    so an undo takes them off once its answer is adopted, and the agent settling the
    question keeps them on. Answering moves no row. A tab's name is its label whatever
    the row shows, and a panel bounds what it holds."""

    BOARD = (
        '<lf-board id="board">'
        + "".join(
            f'<lf-column id="col-{i}" label="Column {i}"><lf-card id="card-{i}">'
            f"<strong>Card {i}</strong> text</lf-card></lf-column>"
            for i in range(6)
        )
        + "</lf-board>"
    )

    def ticket(key):
        return f"""
<lf-tab id="t-{key}" label="Ticket {key}" summary="sev {key} · suggested fix">
  <p id="p-{key}">What went wrong with {key}.</p>{BOARD if key == "a" else ""}
  <lf-ask id="ask-{key}"><h3 id="q-{key}">What happens to {key}?</h3>
    <lf-options id="o-{key}" choose>
      <lf-option id="o-{key}-fix"><strong>Fix</strong> Ship the patch.</lf-option>
      <lf-option id="o-{key}-close"><strong>Close</strong> Explain and close.</lf-option>
    </lf-options>
  </lf-ask>
</lf-tab>"""

    source = leaf_page(
        "a queue",
        "<header><h1>Queue</h1></header>"
        '<lf-tabs id="queue" list="side">' + "".join(map(ticket, "abc")) + "</lf-tabs>",
        layout="workspace",
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1200, 900)
    boxes = """() => {
      const r = (s) => document.querySelector(s).getBoundingClientRect();
      const strip = r('#queue > .lf-tabstrip'), panel = r('#queue > lf-tab:not([hidden])');
      return {stripRight: strip.right, stripTop: strip.top, stripBottom: strip.bottom,
              panelLeft: panel.left, panelTop: panel.top};
    }"""
    wide = page.evaluate(boxes)
    assert wide["stripRight"] <= wide["panelLeft"] + 1, wide
    bounds = page.evaluate("""() => ({
      board: document.querySelector('#board').getBoundingClientRect().right,
      panel: document.querySelector('#t-a').getBoundingClientRect().right})""")
    assert bounds["board"] <= bounds["panel"] + 1, bounds
    expect(page.locator("#queue > .lf-tabstrip .lf-tab-summary").first).to_have_text(
        "sev a · suggested fix"
    )

    tabs = page.get_by_role("tab")
    expect(tabs.first).to_have_accessible_name("Ticket a")
    expect(tabs.first).to_have_text("Ticket asev a · suggested fix")
    expect(tabs.first).to_have_accessible_description("sev a · suggested fix")
    rows = (
        "() => [...document.querySelectorAll('#queue .lf-tab-btn')]"
        ".map((b) => b.getBoundingClientRect().height)"
    )
    heights = page.evaluate(rows)
    tabs.first.focus()
    page.keyboard.press("ArrowDown")
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    page.keyboard.press("ArrowUp")
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    answer = page.locator("#queue .lf-tab-btn").first.locator(".lf-tab-answer")
    expect(answer).not_to_be_visible()
    page.locator("#o-a-fix .lf-pick").click()
    told(page)
    expect(answer).to_be_visible()
    expect(answer).to_have_text("Fix")
    expect(tabs.first).to_have_accessible_name("Ticket a")
    expect(tabs.first).to_have_accessible_description(
        "sev a · suggested fix. Answered: Fix"
    )
    expect(tabs.nth(1)).to_have_accessible_description("sev b · suggested fix")
    assert page.evaluate(rows) == heights

    expect(page.locator(".lf-shortcut-bar")).to_contain_text("undo")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("z")
    holding(page, held, 1, "the undo")
    expect(answer).to_be_visible()
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(answer).not_to_be_visible()
    expect(tabs.first).to_have_accessible_description("sev a · suggested fix")

    page.locator("#o-a-fix .lf-pick").click()
    round_trip(page)
    expect(answer).to_have_text("Fix")
    settled = source.replace(
        '<lf-options id="o-a" choose>', '<lf-options id="o-a" choose settled>'
    ).replace('<lf-option id="o-a-fix">', '<lf-option id="o-a-fix" chosen>')
    assert settled.count("settled") == 1 and settled.count("chosen") == 1
    wait_for_revision(page, stamp_page(serve.page_dir, settled, "Settle a")["revision"])
    expect(page.locator("#o-a .lf-settled")).to_be_visible()
    expect(answer).to_be_visible()
    expect(answer).to_have_text("Fix")
    expect(tabs.first).to_have_accessible_description(
        "sev a · suggested fix. Answered: Fix"
    )

    resized(page, 390, 844)
    narrow = page.evaluate(boxes)
    assert narrow["stripBottom"] <= narrow["panelTop"] + 1, narrow

    # As a scrolling page's root set, a side list keeps the page's history but is a
    # box: nothing sticks, so a switch leaves the page where the user stands.
    def long(key):
        return "".join(
            f"<p id='filler-{key}-{i}'>{'Background. ' * 40}</p>" for i in range(12)
        )

    column = leaf_page(
        "a long queue",
        "<header><h1>Queue</h1></header>"
        '<lf-tabs id="queue" list="side">'
        + "".join(ticket(k).replace("</lf-tab>", long(k) + "</lf-tab>") for k in "bc")
        + "</lf-tabs>",
    )
    page = open_page(browser, serve(column))
    resized(page, 1200, 900)
    # The list is off screen above, so the walk is the gesture: a click would first
    # scroll the tab into view.
    page.get_by_role("tab", name="Ticket b", exact=True).evaluate(
        "tab => tab.focus({preventScroll: true})"
    )
    page.evaluate("document.scrollingElement.scrollTop = 900")
    before = page.evaluate("document.scrollingElement.scrollTop")
    page.keyboard.press("ArrowDown")
    expect(page.get_by_role("tab", name="Ticket c", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    rendered(page)
    assert page.evaluate("document.scrollingElement.scrollTop") == before
    # Back is made from wherever the user reads, so it lands the set's start rather than
    # leaving them partway down, or at the end of, a view that is not the one they read.
    page.evaluate("document.scrollingElement.scrollTop = 1600")
    page.go_back()
    expect(page.get_by_role("tab", name="Ticket b", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    rendered(page)
    top = page.evaluate("document.getElementById('queue').getBoundingClientRect().top")
    assert 0 <= top < 200, top


def test_a_queue_row_names_an_answer_whose_widget_module_arrives_last(browser, serve):
    """An Ask answered before the page loads is named once the page presents, however
    late the answering widget's module arrives: startup imports every module the
    document names before the first reading brings the Ask inventory."""
    url = serve(
        leaf_page(
            "a late queue",
            """<lf-tabs id="queue" list="side">
<lf-tab id="t-a" label="Ticket a">
  <lf-ask id="ask-a"><h3 id="q-a">What happens to a?</h3>
    <lf-options id="o-a" choose>
      <lf-option id="o-a-fix"><strong>Fix</strong> Ship the patch.</lf-option>
      <lf-option id="o-a-close"><strong>Close</strong> Explain and close.</lf-option>
    </lf-options>
  </lf-ask>
</lf-tab>
<lf-tab id="t-b" label="Ticket b"><p id="p-b">Nothing to decide.</p></lf-tab>
</lf-tabs>""",
            layout="workspace",
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
            "detail": {"options": ["o-a-fix"]},
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


def test_root_tab_targets_remain_global(browser, serve):
    """Ask travel crosses hidden tabs."""
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
    page.keyboard.press("a")
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
    pane_posture(page, page.locator("#queue-pane"), "flow")


def test_an_ordinary_two_part_ask_retains_document_flow(browser, serve):
    """An Ask in a document is prose and a control, not a workspace's region.

    The control is the same Ask as a full-height workspace's body, which hands its height to
    the answer."""
    source = SWIPE_PAGE.replace(
        "  <p>Pass removes an item from this design; Keep carries it into implementation.</p>\n",
        "",
    )
    page = open_page(browser, serve(source))
    ask = page.locator("#session-triage-decision")
    assert ask.evaluate("node => getComputedStyle(node).display") == "block"
    assert (
        ask.locator(":scope > h2").evaluate(
            "heading => getComputedStyle(heading).marginTop"
        )
        != "0px"
    )
    assert ask.evaluate(
        """async node => {
          const leaf = await window.__lfRuntimeImport('/runtime/widget-api.js');
          return leaf.readingPosture(node) === 'flow'
            && leaf.effectiveScroller(node) === document.scrollingElement;
        }"""
    )
    page.close()

    held = source.replace("<h1>Session-store follow-ups</h1>\n", "").replace(
        '<main class="layout-column">', '<main class="layout-workspace">'
    )
    page = open_page(browser, serve(held))
    resized(page, 1280, 720)
    expect(page.locator("#session-triage-decision")).to_have_css("display", "flex")
    page.close()

    # The workspace's full height reaches every Ask in it; an Ask held in a pane is
    # that pane's content, not the body, and keeps its document flow.
    in_pane = held.replace(
        '<lf-ask id="session-triage-decision">',
        '<lf-pane id="triage-pane" label="Triage"><div>\n<lf-ask id="session-triage-decision">',
    ).replace("</lf-ask>\n", "</lf-ask>\n</div></lf-pane>\n")
    page = open_page(browser, serve(in_pane))
    resized(page, 1280, 720)
    expect(page.locator("#session-triage-decision")).to_have_css("display", "block")


TRACKED_ASK_PAGE = leaf_page(
    "options track",
    """
  <h1>Retention</h1>
  <lf-ask id="tracked">
    <h3>How long should logs be kept?</h3>
    <table id="tracked-figure">
      <thead><tr><th>Store</th><th class="num">Daily GB</th></tr></thead>
      <tbody><tr><td>Hot</td><td class="num">40</td></tr>
        <tr><td>Warm</td><td class="num">120</td></tr></tbody>
    </table>
    <lf-ask id="nested">
      <h4>Archive the warm tier too?</h4>
      <p id="nested-premise">It holds the last quarter.</p>
      <lf-options id="nested-choice" choose>
        <lf-option id="nested-yes"><strong>Archive</strong> Move it to cold storage.</lf-option>
        <lf-option id="nested-no"><strong>Keep</strong> Leave it warm.</lf-option>
      </lf-options>
    </lf-ask>
    <lf-options id="tracked-choice" choose>
      <lf-option id="keep-30"><strong>30 days</strong> Covers every incident review.</lf-option>
      <lf-option id="keep-90"><strong>90 days</strong> Covers a quarter's audit.</lf-option>
    </lf-options>
  </lf-ask>
""",
    layout="wide",
)


def test_an_ask_framing_a_figure_sets_its_options_beside_it(browser, serve):
    """An Ask whose heading, figure and one option list come in that order sets the
    list in a track beside the figure where the Ask has the room, and stacks it below
    where it hasn't. The track belongs to that Ask alone: an ordinary Ask held among
    its evidence finds the same named container and keeps its own block flow."""
    page = open_page(browser, serve(TRACKED_ASK_PAGE))
    geometry = """() => {
      const box = (id) => document.getElementById(id).getBoundingClientRect();
      const figure = box('tracked-figure'), options = box('tracked-choice');
      const style = (id) => getComputedStyle(document.getElementById(id));
      return {
        beside: options.left >= figure.right && options.top < figure.bottom,
        below: options.top >= figure.bottom,
        nestedFloat: style('nested-premise').float,
        nestedListPosition: style('nested-choice').position,
      };
    }"""
    resized(page, 1440, 900)
    wide = page.evaluate(geometry)
    assert wide["beside"], wide
    assert wide["nestedFloat"] == "none", wide
    assert wide["nestedListPosition"] != "sticky", wide
    resized(page, 700, 900)
    narrow = page.evaluate(geometry)
    assert narrow["below"], narrow


def clear_of_the_bottom_chrome(page, selector):
    """Scroll the page to its end and measure one box against the shortcut bar.

    The bar is the fixed chrome a page's last line has to scroll clear of; a page whose
    end room is missing leaves that line under it however far the user scrolls."""
    return page.evaluate(
        """selector => {
          const page = document.scrollingElement;
          page.scrollTop = page.scrollHeight;
          const bar = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          const box = document.querySelector(selector).getBoundingClientRect();
          return {bottom: box.bottom, bar: bar.top, clear: box.bottom <= bar.top + 1};
        }""",
        selector,
    )


LONG_PANE = """<lf-pane id="workspace-pane" label="Long reading"><div>
  <p>Start</p><div style="height: 900px"></div><p id="pane-end">End</p>
</div></lf-pane>"""


SECTIONED_PANE_PAGE = leaf_page(
    "a pane in a section",
    f"""<div id="cells">
  <section><h2>Section heading</h2>{LONG_PANE}</section>
  <section><h2>Beside it</h2><p>A short cell.</p></section>
</div>""",
    head=regions_side_by_side("cells"),
    layout="workspace",
)
THREE_PART_ASK_PAGE = leaf_page(
    "a three-part Ask as the workspace",
    """
  <lf-ask id="workspace-ask">
    <h2>Which release should go out?</h2>
    <div id="ask-context" style="height: 900px">The context the user weighs.</div>
    <lf-options id="workspace-options" choose>
      <lf-option id="workspace-ship">Ship it</lf-option>
      <lf-option id="workspace-hold">Hold it</lf-option>
    </lf-options>
  </lf-ask>
""",
    layout="workspace",
)


def test_a_pane_inside_a_plain_section_of_a_workspace_flows(browser, serve):
    """Only a box that passes the height on holds what it contains. A section in the
    body's grid is a grouping, so a pane in one takes its natural height and the body,
    which fills the window, scrolls it. The control is the same pane as the workspace's
    body, which fills the window."""
    page = open_page(browser, serve(SECTIONED_PANE_PAGE))
    resized(page, 1280, 720)
    pane = page.locator("#workspace-pane")
    pane_posture(page, pane, "flow")
    assert pane.evaluate(
        """async node => {
          const leaf = await window.__lfRuntimeImport('/runtime/widget-api.js');
          return leaf.readingPosture(node) === 'flow'
            && leaf.effectiveScroller(node) === document.getElementById('cells');
        }"""
    )
    page.close()

    direct = leaf_page("a pane as the workspace body", LONG_PANE, layout="workspace")
    page = open_page(browser, serve(direct))
    resized(page, 1280, 720)
    pane_posture(page, page.locator("#workspace-pane"), "bounded")
    fills_the_window(page, page.locator("main"), True)


ZONE_PACKAGE = {
    "lf-zone": {
        "description": "A project package's differently named pane.",
        "type": "object",
        "properties": {"id": {"type": "string"}, "label": {"type": "string"}},
        "required": ["id", "label"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-reading-role": "pane",
        "x-upgrade": False,
    }
}
NESTED_PANES_PAGE = leaf_page(
    "a pane in a pane's body",
    """<div id="cells">
  <lf-zone id="outer-zone" label="Zones"><div>
    <lf-zone id="inner-zone" label="Inner zone"><div>
      <p>A zone's reading.</p><div style="height: 900px"></div>
    </div></lf-zone>
  </div></lf-zone>
  <lf-pane id="outer-pane" label="Panes"><div>
    <lf-pane id="inner-pane" label="Inner pane"><div>
      <p>A pane's reading.</p><div style="height: 900px"></div>
    </div></lf-pane>
  </div></lf-pane>
</div>""",
    head=regions_side_by_side("cells"),
    layout="workspace",
)


def test_a_package_pane_is_held_where_an_lf_pane_is(browser, serve):
    """Which panes a full-height workspace scrolls is read from the pane role, whichever
    package names the tag. A package's pane that is a cell of the body scrolls its own
    body, and one written inside that pane's body is content there and scrolls with it,
    exactly as lf-panes nested the same way do. The role arrives with the document, so
    the workspace holds the same panes while the runtime has not started."""
    boot = []
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.route("**/leaf.js", lambda route: boot.append(route))
    url = serve(NESTED_PANES_PAGE, layer_registry=ZONE_PACKAGE)

    def postures():
        for tag in ("zone", "pane"):
            pane_posture(page, page.locator(f"#outer-{tag}"), "bounded")
            pane_posture(page, page.locator(f"#inner-{tag}"), "flow")

    try:
        with page.expect_request("**/leaf.js"):
            page.goto(url, wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"
        postures()
        boot.pop().continue_()
        wait_until_ready(page)
        postures()
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_an_ask_with_more_than_one_answer_part_keeps_each_parts_height(browser, serve):
    """An Ask passes the height on only when it is a heading and one answer, which then
    takes what is left. With context between the heading and the options there is no one
    box to give it to, so nothing is drawn over the options and none is squeezed. The
    control is a heading and a playground, whose answer the workspace holds."""
    page = open_page(browser, serve(THREE_PART_ASK_PAGE))
    resized(page, 1280, 720)
    geometry = page.evaluate(
        """() => ({
          context: document.querySelector('#ask-context').getBoundingClientRect().bottom,
          options: document.querySelector('#workspace-options').getBoundingClientRect(),
        })"""
    )
    assert geometry["options"]["top"] >= geometry["context"] - 1, geometry
    assert geometry["options"]["height"] > 40, geometry
    end = clear_of_the_bottom_chrome(page, "#workspace-options")
    assert end["clear"], end
    page.close()

    two_part = PLAYGROUND_PAGE.replace("<h1>Card playground</h1>\n", "").replace(
        '<main class="layout-column">', '<main class="layout-workspace">'
    )
    page = open_page(browser, serve(two_part))
    resized(page, 1280, 720)
    expect(page.locator("#card-playground-ask")).to_have_css("display", "flex")
    pane_posture(page, page.locator(".lf-playground-controls-region"), "bounded")
    fills_the_window(page, page.locator("main"), True)


def test_a_full_height_workspace_that_overflows_scrolls_its_end_clear_of_the_bottom_bar(
    browser, serve
):
    """Whatever the user scrolls to in a full-height workspace clears the bottom bar, as a
    document's last line does. A pane inside a section of the body takes its content's
    height, so the body scrolls as a whole and its end stands above the band."""
    page = open_page(browser, serve(SECTIONED_PANE_PAGE))
    resized(page, 1280, 720)
    fills_the_window(page, page.locator("main"), True)
    # Every reader asks one owner which box scrolls a node, so the body that now scrolls
    # is the answer for the pane it carries: page steps and reading-place recovery move
    # the box the user sees move.
    carrier = page.evaluate(
        """async () => {
          const {scrollerFor} = await window.__lfRuntimeImport('/runtime/reading-regions.js');
          return scrollerFor(document.getElementById('pane-end'))?.id ?? null;
        }"""
    )
    assert carrier == "cells", carrier
    page.locator("#pane-end").evaluate("node => node.scrollIntoView({block: 'end'})")
    end = clear_of_the_bottom_chrome(page, "#pane-end")
    assert end["clear"], end


def test_the_page_end_clears_the_bottom_chrome_around_a_workspace(browser, serve):
    """A document keeps its end room with a pane inside it; a workspace that flows gives
    its last block that room, and a full-height one does not scroll."""
    document = leaf_page(
        "a pane mid-document",
        f"""
<h1>A document with a pane</h1>
<p>Before the pane.</p>
{LONG_PANE}
{"<p>After the pane.</p>" * 30}
<p id="document-end">The document's last line.</p>
""",
    )
    page = open_page(browser, serve(document))
    resized(page, 1280, 720)
    pane_posture(page, page.locator("#workspace-pane"), "flow")
    room = page.evaluate(
        """() => {
          const probe = document.createElement('div');
          probe.style.cssText = 'position:fixed;visibility:hidden;height:var(--lf-bottom-bar-h)';
          document.body.append(probe);
          const band = probe.getBoundingClientRect().height;
          probe.remove();
          return {
            padding: parseFloat(getComputedStyle(document.body).paddingBottom),
            band,
            line: document.querySelector('.lf-shortcut-bar').getBoundingClientRect().height,
          };
        }"""
    )
    # The page's end room is the band's stated height, and the band is that tall.
    assert room["padding"] == room["band"] == room["line"] and room["band"] > 0, room
    end = clear_of_the_bottom_chrome(page, "#document-end")
    assert end["clear"], end
    page.close()

    root = leaf_page("a workspace", LONG_PANE, layout="workspace")
    page = open_page(browser, serve(root))
    resized(page, 1280, 420)
    pane_posture(page, page.locator("#workspace-pane"), "flow")
    end = clear_of_the_bottom_chrome(page, "#pane-end")
    assert end["clear"], end

    resized(page, 1280, 720)
    pane_posture(page, page.locator("#workspace-pane"), "bounded")
    fills_the_window(page, page.locator("main"), True)


def test_a_comment_in_a_pane_leaves_its_grammar_whole(browser, serve):
    """A comment in a pane stands as a pin in the pane's own lane, over the block it
    serves. Leaf inserts nothing into the pane, so a pane whose one body element is that
    block keeps it as its one body and goes on scrolling it."""
    source = leaf_page(
        "a comment in a pane",
        """
  <lf-pane id="workspace-pane" label="Only a paragraph">
    <p id="only">A paragraph that is the whole body of its pane.</p>
  </lf-pane>
""",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1000, 720)
    pane_posture(page, page.locator("#workspace-pane"), "bounded")
    page.locator("#only").click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.keyboard.type("A thread on the paragraph.")
    with sending(page, "the comment on the paragraph"):
        page.keyboard.press("ControlOrMeta+Enter")
    page.keyboard.press("Escape")  # off the paragraph the send landed on, and its card
    row = page.locator('.lf-margin-lane > [data-lf-margin-for="only"]')
    expect(row).to_have_count(1)
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(page.locator("#workspace-pane .lf-margin-cluster")).to_have_count(0)
    expect(page.locator("#workspace-pane > *")).to_have_count(1)
    pane_posture(page, page.locator("#workspace-pane"), "bounded")


def test_regions_inside_a_bounded_pane_body_flow_within_the_body_that_scrolls(
    browser, serve
):
    """A pane written inside a bounded pane's body is that body's content, loose or in a
    section: it takes its natural height and the outer body scrolls it, so reading keys
    and continuity name the box that actually moves. The control is the outer pane,
    which fills the same window."""
    source = leaf_page(
        "regions inside a pane body",
        """
  <lf-pane id="host" label="Host"><div id="host-body">
    <p>Host start</p>
    <section>
      <lf-pane id="inner-pane" label="Inner pane">
        <div><p>Start</p><div style="height: 900px"></div><p>End</p></div>
      </lf-pane>
    </section>
    <lf-pane id="loose-pane" label="Loose pane">
      <div><p>Start</p><div style="height: 900px"></div><p>End</p></div>
    </lf-pane>
  </div></lf-pane>
""",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 720)
    pane_posture(page, page.locator("#host"), "bounded")
    for inner in ("#inner-pane", "#loose-pane"):
        pane_posture(page, page.locator(inner), "flow")
    readings = page.evaluate(
        """async () => {
          const leaf = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const host = document.querySelector('#host-body');
          return Object.fromEntries(['inner-pane', 'loose-pane'].map(id => {
            const body = document.querySelector(`#${id} > div`);
            return [id, {posture: leaf.readingPosture(id),
                         scroller: leaf.effectiveScroller(id) === host,
                         fits: body.scrollHeight <= body.clientHeight}];
          }).concat([['host', host.scrollHeight > host.clientHeight]]));
        }"""
    )
    assert readings == {
        "inner-pane": {"posture": "flow", "scroller": True, "fits": True},
        "loose-pane": {"posture": "flow", "scroller": True, "fits": True},
        "host": True,
    }


def test_a_release_page_is_wide_and_keeps_the_log_on_its_newest_line(browser, serve):
    """A sidebar page of body and track: the lede starts at the page's edge and keeps
    the reading measure, every region of the body shares the body's two edges and every
    region of the track the track's, and the checks table fills its panel. On a narrow
    window the track stacks under the body, and the bounded log opens on its newest
    line. Paper shows the log whole."""
    example = Path(__file__).parent.parent / "examples" / "live-progress.html"
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = open_page(browser, live_url(serve(example)), context=context)
    body = ["lp-status", "lp-current-state", "lp-traffic", "lp-log"]
    rail = ["lp-steps", "lp-checks", "lp-release"]
    ids = [*body, *rail, "lp-checks-table", "lp-lede"]
    boxes = f"""() => {{
      const read = Object.fromEntries({ids!r}.map(id =>
        [id, document.getElementById(id).getBoundingClientRect().toJSON()]));
      const main = document.querySelector('main');
      const style = getComputedStyle(main);
      const box = main.getBoundingClientRect();
      const left = box.left + parseFloat(style.paddingLeft);
      const right = box.right - parseFloat(style.paddingRight);
      read.main = {{left, right, width: right - left}};
      return read;
    }}"""

    wide = page.evaluate(boxes)
    page_box = wide["main"]
    assert page_box["width"] > 1080, "the page should take the room past the wide width"
    assert wide["lp-lede"]["left"] == pytest.approx(page_box["left"], abs=1)
    assert wide["lp-lede"]["width"] <= 720 + 1
    for track in (body, rail):
        for edge in ("left", "right"):
            assert {round(wide[i][edge]) for i in track} == {
                round(wide[track[0]][edge])
            }
    assert wide["lp-status"]["left"] == pytest.approx(page_box["left"], abs=1)
    assert wide["lp-steps"]["right"] == pytest.approx(page_box["right"], abs=1)
    assert wide["lp-log"]["right"] < wide["lp-steps"]["left"]
    assert wide["lp-checks-table"]["width"] > wide["lp-checks"]["width"] - 48
    listing = page.locator("#lp-live-log pre")
    assert listing.evaluate(
        "pre => pre.scrollHeight > pre.clientHeight && "
        "pre.scrollHeight - pre.scrollTop - pre.clientHeight <= 2"
    ), "the bounded log should open on its newest line"
    assert page.evaluate("scrollY") == 0, "following the log should not move the page"
    page.locator("#lp-live-log").scroll_into_view_if_needed()
    expect(page.locator("#lp-live-log figcaption")).to_be_in_viewport()

    resized(page, 560, 900)
    narrow = page.evaluate(boxes)
    assert narrow["lp-steps"]["top"] >= narrow["lp-log"]["bottom"]
    assert narrow["lp-checks"]["top"] >= narrow["lp-steps"]["bottom"]
    assert narrow["lp-steps"]["width"] == narrow["lp-log"]["width"]

    page.emulate_media(media="print")
    assert listing.evaluate("pre => getComputedStyle(pre).maxHeight") == "none"


FEED_PAGE = leaf_page(
    "A feed that follows its newest entry",
    """<h1>Feed</h1>
<div id="feed" data-bound="end"></div>""",
)


def test_a_bound_at_its_end_follows_a_rebuilt_feed_until_the_user_scrolls_back(
    browser, serve
):
    """A widget that replaces its children on every change stays on its newest entry
    while the user is at the end, and leaves a user who scrolled back where they
    stopped."""
    page = open_page(browser, live_url(serve(FEED_PAGE)))
    rebuild = """count => document.getElementById('feed').replaceChildren(
      ...Array.from({length: count}, (_, i) => Object.assign(
        document.createElement('p'), {textContent: `entry ${i}`})))"""
    at_end = """() => { const feed = document.getElementById('feed');
      return feed.scrollHeight > feed.clientHeight
        && feed.scrollHeight - feed.scrollTop - feed.clientHeight <= 2; }"""
    page.evaluate(rebuild, 60)
    page.wait_for_function(at_end)
    page.evaluate(rebuild, 90)
    page.wait_for_function(at_end)

    page.locator("#feed").evaluate("feed => feed.scrollTop = 200")
    page.wait_for_function("() => document.getElementById('feed').scrollTop === 200")
    page.evaluate(rebuild, 120)
    page.evaluate("() => new Promise(requestAnimationFrame)")
    assert page.locator("#feed").evaluate("feed => feed.scrollTop") == 200


def revised_log(first, last):
    """A page whose log bounded at its end holds entries `first` to `last`."""
    filler = "".join(
        f"<p>Filler paragraph {n}, long enough to occupy a line of reading.</p>"
        for n in range(20)
    )
    entries = "".join(
        f"<p>Entry {n}: the deploy copied shard {n} to the new key format.</p>"
        for n in range(first, last)
    )
    return leaf_page(
        "a revised log",
        f'<h1 id="t">Deploy</h1>{filler}<div id="log" data-bound="end">{entries}'
        f"</div>{filler}",
    )


def test_a_revision_leaves_a_following_log_at_its_end_and_a_reader_on_their_line(
    browser, serve
):
    """A bounded log is a reading region, so a revision restores the place the user had
    in it. The place of a log following its newest entry is its end: restoring the line
    that stood at its top would have left the user above the entries the revision
    added, and ended the following. A user who scrolled back keeps the line they were
    reading, however many entries arrived above it."""
    url = serve(revised_log(10, 60))
    page = open_page(browser, live_url(url))
    resized(page, 1280, 900)
    log = page.locator("#log")
    at_end = """log => log.scrollHeight > log.clientHeight
      && log.scrollHeight - log.scrollTop - log.clientHeight <= 2"""
    page.wait_for_function(f"({at_end})(document.getElementById('log'))")
    page.evaluate(
        """log => { const at = log.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        log.element_handle(),
    )
    scroll_settled(page)

    (serve.page_dir / "index.html").write_text(revised_log(10, 80))
    told(page)
    expect(log.locator("p")).to_have_count(70)
    rendered(page)
    assert log.evaluate(at_end), "the revision left the log above its newest entries"

    # Scrolled back to Entry 30, with ten entries arriving above it.
    reading = log.locator("p", has_text="Entry 30:")
    log.evaluate(
        """(log, line) => log.scrollTop += line.getBoundingClientRect().top
          - log.getBoundingClientRect().top""",
        reading.element_handle(),
    )
    scroll_settled(page, "#log")
    where = """([log, line]) => line.getBoundingClientRect().top
      - log.getBoundingClientRect().top"""
    handles = [log.element_handle(), reading.element_handle()]
    before = page.evaluate(where, handles)
    (serve.page_dir / "index.html").write_text(revised_log(0, 80))
    told(page)
    expect(log.locator("p")).to_have_count(80)
    rendered(page)
    after = page.evaluate(
        where,
        [log.element_handle(), log.locator("p", has_text="Entry 30:").element_handle()],
    )
    assert after == pytest.approx(before, abs=2), "the reader lost their line"
    assert not log.evaluate(at_end)


def test_release_rollback_is_the_operators_answer_to_an_ask(browser, serve):
    """The release escape path is a question the operator answers: the page lists it
    among its Asks, and the pick reaches the agent as an action naming the option."""
    example = Path(__file__).parent.parent / "examples" / "live-progress.html"
    page = open_page(browser, live_url(serve(example)))
    expect_asks_answered(page, "0/1")
    rollback = page.locator("#lp-rollback-now")

    with sending(page, "the rollback pick"):
        rollback.click()

    pick = events_model.read_events(serve.page_dir)[-1]
    assert (pick["kind"], pick["widget"], pick["action"]) == (
        "action",
        "lp-rollback",
        "choose",
    )
    assert pick["detail"] == {"options": ["lp-rollback-now"]}
    expect_asks_answered(page, "1/1")


def test_monitoring_evidence_moves_without_stealing_position_or_the_summary(
    browser, serve
):
    """Replaceable log evidence does not become the authority for release state."""
    example = Path(__file__).parent.parent / "examples" / "live-progress.html"
    page = open_page(browser, live_url(serve(example)))
    log = page.locator("#lp-live-log")
    listing = log.locator("pre")

    # A user who scrolled back through the log stays where they stopped.
    listing.evaluate("pre => pre.scrollTop = 120")
    page.wait_for_function(
        "() => document.querySelector('#lp-live-log pre').scrollTop === 120"
    )
    original = listing.text_content()
    data_model.cmd_data_set(
        serve.page_dir,
        "release-log",
        f"{original.rstrip()}\n14:24:49 observer  checkout remains healthy\n",
    )
    told(page)
    expect(log).to_contain_text("14:24:49 observer  checkout remains healthy")
    assert listing.evaluate("pre => pre.scrollTop") == 120

    # One at the end follows what arrives there.
    listing.evaluate("pre => pre.scrollTop = pre.scrollHeight")
    data_model.cmd_data_set(
        serve.page_dir,
        "release-log",
        f"{listing.text_content().rstrip()}\n14:24:54 observer  sample=49 healthy\n",
    )
    told(page)
    expect(log).to_contain_text("14:24:54 observer  sample=49 healthy")
    page.wait_for_function(
        """() => { const pre = document.querySelector('#lp-live-log pre');
          return pre.scrollHeight - pre.scrollTop - pre.clientHeight <= 2; }"""
    )

    current = (serve.page_dir / "index.html").read_text(encoding="utf-8")
    incorporated = current
    revisions = (
        (
            (
                "The production canary is paused at 25%. Customer checkout is healthy, but\n"
                "        finance export is one row short and must reconcile before traffic expands."
            ),
            (
                "Finance export parity now passes. The production release is expanding from\n"
                "        the 25% canary to all checkout traffic."
            ),
        ),
        (
            "<strong>Paused at 25%</strong>",
            "<strong>Promoting to 100%</strong>",
        ),
        (
            (
                "Automatic promotion stopped when the finance-parity check failed. The candidate\n"
                "        remains live for canary traffic while Ledger traces a partial-refund fixture\n"
                "        mismatch; the exact failing producer is not yet established."
            ),
            (
                "The rebuilt export contains every expected order. Traffic is increasing\n"
                "        while the observer keeps the release checks active."
            ),
        ),
        (
            '<lf-metric id="lp-k-traffic" value="25%">candidate traffic</lf-metric>',
            '<lf-metric id="lp-k-traffic" value="100%">target traffic</lf-metric>',
        ),
        (
            'id="lp-k-checks" value="4 of 5" delta="-1" direction="up-good"',
            'id="lp-k-checks" value="5 of 5"',
        ),
        (
            '<lf-milestone id="lp-step-checks" status="blocked" when="now">',
            '<lf-milestone id="lp-step-checks" status="done" when="14:25">',
        ),
        (
            (
                "<strong>Pass release checks</strong> Finance export has 1,998 of 1,999\n"
                "            expected rows."
            ),
            "<strong>Pass release checks</strong> All five production checks pass.",
        ),
        (
            '<lf-milestone id="lp-step-promote" status="planned">',
            '<lf-milestone id="lp-step-promote" status="active" when="now">',
        ),
        (
            "Four checks pass. One blocks promotion.",
            "All five checks pass. Promotion is running.",
        ),
        (
            '<span class="release-check-result" data-status="fail">Fail</span>',
            '<span class="release-check-result" data-status="pass">Pass</span>',
        ),
        (
            "<code>1,998</code> / <code>1,999</code> rows",
            "<code>1,999</code> / <code>1,999</code> rows",
        ),
    )
    # The example's line wrapping is layout, not content: match each passage across
    # whatever whitespace the source wraps it with.
    for before, after in revisions:
        pattern = r"\s+".join(map(re.escape, before.split()))
        incorporated, count = re.subn(
            pattern, lambda _, after=after: after, incorporated, count=1
        )
        assert count == 1, before
    stamp = stamp_page(
        serve.page_dir,
        incorporated,
        "Pass finance parity and promote checkout-v2",
    )
    wait_for_revision(page, stamp["version"])
    expect(page.locator("#lp-lede")).to_contain_text("expanding")
    expect(page.locator("#lp-current-state")).to_contain_text("Promoting to 100%")
    expect(page.locator("#lp-k-traffic")).to_have_attribute("value", "100%")
    expect(page.locator("#lp-k-checks")).to_have_attribute("value", "5 of 5")
    expect(page.locator("#lp-step-checks")).to_have_attribute("status", "done")
    expect(page.locator("#lp-step-promote")).to_have_attribute("status", "active")
    expect(page.locator("#lp-checks-note")).to_have_text(
        "All five checks pass. Promotion is running."
    )
    expect(page.locator("#lp-check-finance .release-check-result")).to_have_text("Pass")
    expect(log).to_contain_text("14:24:49 observer  checkout remains healthy")


def test_pr_walkthrough_moves_from_semantic_call_to_exact_patch_comment(browser, serve):
    """The specialized report's signature path reaches reviewable source evidence."""
    example = Path(__file__).parent.parent / "examples" / "pr-walkthrough.html"
    page = open_page(browser, live_url(serve(example)))

    page.get_by_role("tab", name="CallDiff").click()
    call_diff = page.locator("#pr-call-diagram")
    expect(call_diff.locator(".lf-call-line")).to_have_count(30)
    location = call_diff.get_by_role("link", name="src/summary.rs:259").first
    expect(location).to_be_visible()
    location.click()

    line = page.locator(
        '#pr-exact-patch [data-lf-datum=\'["src/summary.rs","new",259]\']'
    )
    expect(page).to_have_url(re.compile(r"#pr-exact-patch$"))
    expect(line).to_be_in_viewport()
    expect(page.locator(".lf-live")).to_have_text(
        "Opened src/summary.rs:259 in the exact patch"
    )

    expect(line).to_be_focused()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    write(
        page.locator(".lf-composer leaf-text"),
        "Does this preserve sparse-checkout behavior?",
    )
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    expect(page.locator(".lf-thread .lf-quote").first).to_contain_text("src/summary.rs")
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("text")
    ]
    assert comments[-1]["anchor"]["datum"] == '["src/summary.rs","new",259]'


@pytest.mark.parametrize("destination", ["call", "patch"])
def test_focus_reactions_keep_a_projected_data_target(browser, serve, destination):
    """Light-DOM data and its shadow-DOM destination keep exact identity."""
    example = Path(__file__).parent.parent / "examples" / "pr-walkthrough.html"
    page = open_page(browser, live_url(serve(example)))
    page.get_by_role("tab", name="CallDiff").click()
    location = (
        page.locator("#pr-call-diagram")
        .get_by_role("link", name="src/summary.rs:259")
        .first
    )
    # Reach the real link through the browser's tab order. The source case reads
    # keyboard focus inside a generated datum, rather than focusing the datum directly.
    for _ in range(40):
        page.keyboard.press("Tab")
        if location.evaluate("node => node.matches(':focus')"):
            break
    expect(location).to_be_focused()
    assert location.evaluate("node => node.matches(':focus-visible')")
    target = location.locator("xpath=..")
    if destination == "patch":
        page.keyboard.press("Enter")
        target = page.locator(
            '#pr-exact-patch [data-lf-datum=\'["src/summary.rs","new",259]\']'
        )
        expect(target).to_be_focused()
        expect(page.locator(".lf-live")).to_have_text(
            "Opened src/summary.rs:259 in the exact patch"
        )
        expect(target).to_be_in_viewport()
    datum = target.get_attribute("data-lf-datum")
    owner = target.get_attribute("data-lf-projection")
    revision = target.get_attribute("data-lf-source-revision")
    assert datum and owner and revision
    page.keyboard.press("e")
    expect(
        page.locator('[data-lf-margin-entry-owner="responses"]:visible')
    ).not_to_have_count(0)
    page.keyboard.press("1")
    round_trip(page)
    reaction = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "comment" and event.get("token")
    )
    assert reaction["anchor"]["section"] == owner
    assert reaction["anchor"]["datum"] == datum
    assert reaction["anchor"]["source_revision"] == revision


def test_newer_navigation_wins_while_a_call_diff_target_loads(browser, serve):
    """A lazy exact-patch fetch must not undo a later tab choice and focus."""
    example = Path(__file__).parent.parent / "examples" / "pr-walkthrough.html"
    page = open_page(browser, live_url(serve(example)))
    page.get_by_role("tab", name="CallDiff").click()
    held = []
    page.route("**/api/deferred*", lambda route: held.append(route))
    page.get_by_role("link", name="src/summary.rs:259").first.click()
    page.wait_for_function(
        "() => document.querySelector('#pr-exact-patch').shadowRoot.querySelector('details[open]') !== null"
    )
    assert held, "the real exact-patch request must remain pending"

    other = page.get_by_role("tab", name="Behavior diff")
    other.click()
    expect(other).to_be_focused()
    before = page.evaluate(
        "() => ({url: location.href, y: document.scrollingElement.scrollTop})"
    )
    page.unroute("**/api/deferred*")
    for route in held:
        route.continue_()
    line = page.locator(
        '#pr-exact-patch [data-lf-datum=\'["src/summary.rs","new",259]\']'
    )
    expect(line).to_have_count(1)
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    expect(other).to_be_focused()
    assert page.url == before["url"]
    assert (
        abs(page.evaluate("() => document.scrollingElement.scrollTop") - before["y"])
        < 2
    )


SWIPE_PAGE = leaf_page(
    "session backlog triage",
    """
<h1>Session-store follow-ups</h1>
<lf-ask id="session-triage-decision">
  <h2>Which session-store follow-ups should we keep?</h2>
  <p>Pass removes an item from this design; Keep carries it into implementation.</p>
  <lf-swipe-deck id="session-triage">
    <lf-swipe-pile id="session-queue" verdict="unseen">
      <lf-swipe-card id="swipe-a"><strong>Buffer rolling expiry</strong><p>Refresh once a minute.</p></lf-swipe-card>
      <lf-swipe-card id="swipe-b"><strong>Bound fallback lifetime</strong><p>Refuse snapshots after 90 seconds.</p></lf-swipe-card>
      <lf-swipe-card id="swipe-c"><strong>Partition capacity</strong><p>Separate rate-limit eviction.</p></lf-swipe-card>
      <lf-swipe-card id="swipe-d"><strong>Index account sessions</strong><p>Make device-wide revocation bounded.</p></lf-swipe-card>
    </lf-swipe-pile>
    <lf-swipe-pile id="session-pass" verdict="pass">
      <lf-swipe-card id="already-passed"><strong>Add Dynamo</strong><p>A new operating model.</p></lf-swipe-card>
    </lf-swipe-pile>
    <lf-swipe-pile id="session-keep" verdict="keep">
      <lf-swipe-card id="already-kept"><strong>Delete session keys</strong><p>The revocation primitive.</p></lf-swipe-card>
    </lf-swipe-pile>
  </lf-swipe-deck>
</lf-ask>
""",
)

EMPTY_QUOTED_SWIPE_PAGE = leaf_page(
    "completed swipe deck",
    """
<h1>Completed triage</h1>
<lf-sample id="swipe-example" label="completed triage">
  <lf-swipe-deck id="completed-swipe">
    <lf-swipe-pile id="completed-queue" verdict="unseen"></lf-swipe-pile>
    <lf-swipe-pile id="completed-pass" verdict="pass"></lf-swipe-pile>
    <lf-swipe-pile id="completed-keep" verdict="keep">
      <lf-swipe-card id="kept-card"><strong>Keep the expiry bound</strong></lf-swipe-card>
    </lf-swipe-pile>
  </lf-swipe-deck>
</lf-sample>
""",
)


TALL_BOARD_PAGE = leaf_page(
    "tall board",
    """
<h1 id="t">Sprint</h1>
<lf-board id="crowd">
  <lf-column id="sq-col-0" label="Lane 0">
"""
    + "".join(
        f"""    <lf-card id="sq-card-{i}"><strong>Perch {i}</strong>
    The warden has documented every reading she takes at dawn.</lf-card>
"""
        for i in range(8)
    )
    + """  </lf-column>
</lf-board>
""",
)


PLAYGROUND_PAGE = leaf_page(
    "card playground",
    """
<h1>Card playground</h1>
<style>
  #card-playground {
    --playground-accent: #4f766f;
    --playground-radius: 12px;
    --playground-title: "Field note";
  }
  #playground-card {
    --lf-block-frame: 1;
    border: 2px solid var(--playground-accent);
    border-radius: var(--playground-radius);
    padding: 24px;
  }
  #playground-card::before { content: var(--playground-title); }
  #card-playground[data-playground-compact="true"] #playground-card { padding: 8px; }
  #card-playground[data-playground-tone="bold"] #playground-card { font-weight: 700; }
</style>
<lf-ask id="card-playground-ask">
  <h2>How should the card look?</h2>
  <lf-playground id="card-playground">
    <lf-playground-control name="radius" label="Corner radius" kind="range"
      value="12" min="0" max="28" step="1" unit="px"></lf-playground-control>
    <lf-playground-control name="compact" label="Compact spacing" kind="toggle"
      value="false"></lf-playground-control>
    <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
      <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
      <lf-playground-choice value="bold" label="Bold"></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-control name="accent" label="Accent" kind="color"
      value="#4f766f"></lf-playground-control>
    <lf-playground-control name="title" label="Title" kind="text"
      value="Field note" placeholder="Card title"></lf-playground-control>
    <lf-playground-preset label="Dense">
      <lf-playground-setting for="radius" value="4"></lf-playground-setting>
      <lf-playground-setting for="compact" value="true"></lf-playground-setting>
      <lf-playground-setting for="tone" value="bold"></lf-playground-setting>
    </lf-playground-preset>
    <lf-playground-preview id="card-preview">
      <article id="playground-card"><strong>Card preview</strong><p>Open until dusk.</p></article>
    </lf-playground-preview>
    <lf-playground-output id="card-instruction">Use a
      <lf-playground-value for="radius"></lf-playground-value> radius,
      compact spacing set to <lf-playground-value for="compact"></lf-playground-value>,
      a <lf-playground-value for="tone"></lf-playground-value> tone,
      <lf-playground-value for="accent"></lf-playground-value> accents, and the title
      <lf-playground-value for="title"></lf-playground-value>.
    </lf-playground-output>
  </lf-playground>
</lf-ask>
""",
)


def test_a_milestone_marker_is_centred_on_its_title(browser, serve):
    source = leaf_page(
        "milestone marker alignment",
        """
<h1>Release plan</h1>
<style>#rail { width: 160px; }</style>
<lf-milestones id="rail">
  <lf-milestone id="publish" status="active"><strong>Publish the release after validation</strong></lf-milestone>
</lf-milestones>
""",
    )
    page = open_page(browser, serve(source))
    centres = page.locator("#publish").evaluate(
        """item => {
          const titleNode = item.querySelector(':scope > strong');
          const title = titleNode.getBoundingClientRect();
          const lineHeight = parseFloat(getComputedStyle(titleNode).lineHeight);
          const box = item.getBoundingClientRect();
          const marker = getComputedStyle(item, '::before');
          const border = marker.boxSizing === 'content-box'
            ? parseFloat(marker.borderTopWidth) + parseFloat(marker.borderBottomWidth)
            : 0;
          return {
            title: title.top + lineHeight / 2,
            titleLines: title.height / lineHeight,
            marker: box.top + parseFloat(marker.top)
              + (parseFloat(marker.height) + border) / 2,
          };
        }"""
    )
    assert centres["titleLines"] >= 2, centres
    assert centres["marker"] == pytest.approx(centres["title"], abs=0.5), centres


def test_suggestions_sharing_a_block_keep_source_and_keyboard_order(browser, serve):
    """Decision rows keep source order in the margin layer, and so in the tab order,
    through upgrade and reconnection."""
    source = leaf_page(
        "suggestion-order",
        """
<h1>Release wording</h1>
<section id="shared-block">
  <p>First <lf-suggestion id="first-change"><lf-new>first proposal</lf-new></lf-suggestion>.</p>
  <p>Second <lf-suggestion id="second-change"><lf-new>second proposal</lf-new></lf-suggestion>.</p>
  <p>Third <lf-suggestion id="third-change"><lf-new>third proposal</lf-new></lf-suggestion>.</p>
</section>
""",
    )
    page = open_page(browser, serve(source))
    rows = page.locator(".lf-margin-cluster")
    expect(rows).to_have_count(3)
    assert rows.evaluate_all("rows => rows.map(row => row.dataset.lfMarginFor)") == [
        "first-change",
        "second-change",
        "third-change",
    ]
    page.locator("#first-change").evaluate(
        "el => { const parent = el.parentNode; const next = el.nextSibling;"
        "        el.remove();"
        "        parent.insertBefore(el, next); }"
    )
    assert rows.evaluate_all("rows => rows.map(row => row.dataset.lfMarginFor)") == [
        "first-change",
        "second-change",
        "third-change",
    ], "reconnecting the first suggestion moved its controls after later source rows"
    first_accept = page.locator("[data-lf-margin-for='first-change'] .lf-sug-accept")
    first_accept.evaluate(
        """control => {
          control.disabled = true;
          const widget = document.getElementById('first-change');
          const parent = widget.parentNode;
          const next = widget.nextSibling;
          widget.remove();
          parent.insertBefore(widget, next);
        }"""
    )
    expect(first_accept).to_be_enabled()
    page.locator("[data-lf-margin-for='first-change'] .lf-sug-accept").focus()
    walked = []
    for _ in range(3):
        walked.append(
            page.evaluate(
                "() => document.activeElement.closest('.lf-margin-cluster')"
                "?.dataset.lfMarginFor"
            )
        )
        # Each row has two decision controls, and the roving semantic marker now joins
        # them in the same item. Walk past whichever row currently owns that one stop.
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        # The rows stand after the page's content in the margin layer, so the last
        # row's Tab leaves the document.
        if page.evaluate("() => document.activeElement.matches('.lf-margin-marker')"):
            page.keyboard.press("Tab")
    assert walked == ["first-change", "second-change", "third-change"]


def test_a_detached_board_releases_and_restores_its_lifecycle(browser, serve):
    """Version replacement releases board resources and restores pointer dragging."""
    context = browser.new_context(viewport={"width": 1000, "height": 800})
    context.add_init_script(
        """(() => {
          window.__lfMotionListeners = {added: 0, removed: 0};
          const add = MediaQueryList.prototype.addEventListener;
          const remove = MediaQueryList.prototype.removeEventListener;
          MediaQueryList.prototype.addEventListener = function(type, listener, options) {
            if (type === 'change' && this.media === '(prefers-reduced-motion: reduce)')
              window.__lfMotionListeners.added++;
            return add.call(this, type, listener, options);
          };
          MediaQueryList.prototype.removeEventListener = function(type, listener, options) {
            if (type === 'change' && this.media === '(prefers-reduced-motion: reduce)')
              window.__lfMotionListeners.removed++;
            return remove.call(this, type, listener, options);
          };
        })()"""
    )
    try:
        page = open_page(browser, serve(BOARD_PAGE), context=context)
        cdp = context.new_cdp_session(page)
        # The board's own specifier, which the document's import map sends to the
        # revision, so this is the instance the board constructs from.
        page.evaluate(
            """async () => {
              window.__lfSortablePrototype =
                (await import('/vendor/sortable.esm.js')).default.prototype;
            }"""
        )

        def sortable_count():
            # Keep the query handles in a disposable group. In particular, the probe
            # must not become the new owner of the DOM it is checking.
            group = "board-lifecycle-probe"
            prototype = cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "window.__lfSortablePrototype",
                    "returnByValue": False,
                    "objectGroup": group,
                },
            )["result"]["objectId"]
            try:
                objects = cdp.send(
                    "Runtime.queryObjects",
                    {"prototypeObjectId": prototype, "objectGroup": group},
                )["objects"]["objectId"]
                return cdp.send(
                    "Runtime.callFunctionOn",
                    {
                        "objectId": objects,
                        "functionDeclaration": "function () { return this.length; }",
                        "returnByValue": True,
                    },
                )["result"]["value"]
            finally:
                cdp.send("Runtime.releaseObjectGroup", {"objectGroup": group})

        before = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert sortable_count() == 2
        page.evaluate(
            """() => {
              window.__lfDetachedBoard = document.querySelector('lf-board');
              window.__lfDetachedBoard.remove();
            }"""
        )
        released = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert released["removed"] > before["removed"], (
            f"detaching the board retained its motion listener: {before=}, {released=}"
        )
        cdp.send("HeapProfiler.collectGarbage")
        assert sortable_count() == 0, (
            "detaching the board retained its Sortable instances"
        )
        page.evaluate(
            "() => document.querySelector('main').append(window.__lfDetachedBoard)"
        )
        restored = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert restored["added"] > before["added"], (
            f"reconnecting the board did not restore live motion changes: {restored=}"
        )
        assert sortable_count() == 2

        grip = page.locator("#card-heater .lf-grip").bounding_box()
        dest = page.locator("#col-done").bounding_box()
        page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            dest["x"] + dest["width"] / 2,
            dest["y"] + dest["height"] / 2,
            steps=15,
        )
        page.mouse.up()
        page.wait_for_selector("#col-done #card-heater")
    finally:
        if "cdp" in locals():
            cdp.detach()


def test_live_widget_subscription_releases_and_reconnects(browser, serve):
    """A detached widget ignores semantic news and catches up when reconnected."""
    source = leaf_page(
        "widget watcher lifecycle",
        """
<section id="watched">
  <lf-draft id="watched-draft"><pre>Draft words.</pre></lf-draft>
</section>
""",
    )
    page = open_page(browser, serve(source))
    before = page.locator("#watched").evaluate("section => section.innerHTML")
    page.evaluate(
        """() => {
          window.__lfWatchedSection = document.querySelector('#watched');
          window.__lfWatchedSection.remove();
        }"""
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "watched-draft",
            "action": "edit",
            "detail": {"text": "Reconnected words."},
        },
    )
    told(page)
    assert page.evaluate("window.__lfWatchedSection.innerHTML") == before

    page.evaluate("document.querySelector('main').append(window.__lfWatchedSection)")
    expect(page.locator("#watched-draft .lf-draft-history > summary")).to_have_text(
        "Changes · 1 edit"
    )


def test_a_table_of_contents_reads_the_page_outline_and_reveals_its_heading(
    browser, serve
):
    """The authored element is only a request for navigation. The module reads the
    page's headings in document order, keeps their relative depth, and gives an
    id-less heading an id reserved for the runtime, on the heading itself, so nothing
    is added among the page's own elements. A real fragment link lets the browser reveal
    a heading in a closed disclosure, so it is reachable rather than merely named."""
    source = leaf_page(
        "contents",
        """
<h1>Migration plan</h1>
<lf-toc id="contents"></lf-toc>
<section><h2 id="prepare">Prepare <lf-gloss tip="One cohort at a time.">gradually</lf-gloss></h2><p>Take a snapshot.</p></section>
<details style="margin-top: 110vh">
  <summary>Implementation detail</summary>
  <h3>Move the readers</h3>
  <p>Shift one cohort at a time.</p>
</details>
<section style="margin-bottom: 110vh"><h2>Verify</h2><p>Compare the totals.</p></section>
""",
    )
    url = serve(source)
    page = open_page(browser, url)
    toc = page.get_by_role("navigation", name="On this page")

    expect(toc.get_by_role("link")).to_have_count(3)
    assert toc.get_by_role("link").all_text_contents() == [
        "Prepare gradually",
        "Move the readers",
        "Verify",
    ]
    assert toc.locator("li").evaluate_all(
        "nodes => nodes.map(node => node.dataset.lfDepth)"
    ) == ["0", "1", "0"]
    assert page.locator("h2, h3").evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('id'))"
    ) == ["prepare", "lf-contents-section-2", "lf-contents-section-3"]

    hrefs = toc.get_by_role("link").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"
    )
    assert hrefs[0] == "#prepare"
    assert hrefs[1] == "#lf-contents-section-2"

    # The heading stays its section's first child, so its collapsed top margin is not
    # trapped inside an otherwise transparent section: both begin at the same edge.
    verify_geometry = page.get_by_role("heading", name="Verify").evaluate(
        """heading => ({
          sectionTop: heading.parentElement.getBoundingClientRect().top,
          headingTop: heading.getBoundingClientRect().top,
        })"""
    )
    assert max(verify_geometry.values()) - min(verify_geometry.values()) < 0.5, (
        verify_geometry
    )

    details = page.locator("details")
    expect(details).not_to_have_attribute("open", "")
    toc.get_by_role("link", name="Move the readers").click()
    expect(details).to_have_attribute("open", "")
    expect(page).to_have_url(re.compile(f"{re.escape(hrefs[1])}$"))
    scroll_settled(page)
    top = page.locator("h3").evaluate("heading => heading.getBoundingClientRect().top")
    assert 0 <= top < 150, f"the revealed heading stopped at {top}px"

    # The title is a visible page label, while each repeated heading is the label of a
    # browser-owned link under .lf-ui. The authored heading remains the one passage.
    spoken = page.locator("main").evaluate(
        "async main => (await window.__lfRuntimeImport('/runtime/widget-api.js')).says(main)"
    )
    assert spoken.count("Prepare gradually") == 1
    assert spoken.count("Move the readers") == 1
    assert spoken.count("Verify") == 1
    expect(toc).to_have_class(re.compile(r"\blf-ui\b"))
    expect(toc).to_have_attribute("data-lf-gen", "1")
    page.close()

    # On first parse this id does not exist yet. The shared arrival pass runs after every
    # widget settles, so a copied link still reveals and reaches the heading it names.
    direct = open_page(browser, url + hrefs[1])
    expect(direct.locator("details")).to_have_attribute("open", "")
    expect(direct).to_have_url(re.compile(f"{re.escape(hrefs[1])}$"))
    direct.wait_for_function(
        "heading => { const box = heading.getBoundingClientRect(); "
        "return box.top >= 0 && box.bottom <= innerHeight; }",
        arg=direct.locator("h3").element_handle(),
    )
    assert direct.locator("h3").evaluate(
        "heading => { const box = heading.getBoundingClientRect(); "
        "return box.top >= 0 && box.bottom <= innerHeight; }"
    )


def test_contents_addresses_a_title_group_and_maps_its_complete_box(browser, serve):
    """The heading supplies words; its group supplies the destination and map origin.

    A grouped section title still belongs to the identified section it titles. Marker
    centers and the viewport lens share one coordinate, including the track's origin.
    """
    source = leaf_page(
        "grouped contents titles",
        """
<hgroup id="page-title">
  <p class="eyebrow">Eval consolidation</p>
  <h1 id="title-label">One catalog, with short cases and complete workflows</h1>
</hgroup>
<aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>
<div style="height: 110vh"></div>
<hgroup id="standalone-title">
  <p class="eyebrow">One vocabulary</p>
  <h2 id="standalone-label">Name each case</h2>
</hgroup>
<p>The whole title arrives together.</p>
<div style="height: 110vh"></div>
<section id="owned-section">
  <hgroup id="owned-title">
    <p class="eyebrow">One command</p>
    <h2 id="owned-label">Run each case</h2>
  </hgroup>
  <p>The fragment names the section that owns this title.</p>
</section>
<div style="height: 110vh"></div>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    start = nav.locator(".lf-toc-start a")
    expect(start).to_have_text("One catalog, with short cases and complete workflows")
    expect(start).to_have_attribute("href", "#page-title")
    standalone = nav.get_by_role("link", name="Name each case", exact=True)
    expect(standalone).to_have_attribute("href", "#standalone-title")
    expect(nav.get_by_role("link", name="Run each case", exact=True)).to_have_attribute(
        "href", "#owned-section"
    )

    geometry = nav.evaluate(
        """nav => {
          const rows = nav.querySelector('.lf-toc-rows');
          const start = nav.querySelector('.lf-toc-start');
          const marker = getComputedStyle(start, '::before');
          const title = document.querySelector('#page-title');
          return {
            trackTop: rows.getBoundingClientRect().top,
            markerCenter: start.getBoundingClientRect().top +
              parseFloat(marker.top) + new DOMMatrixReadOnly(marker.transform).m42 +
              parseFloat(marker.height) / 2,
            lensTop: nav.querySelector('.lf-toc-window').getBoundingClientRect().top,
            titleTop: title.getBoundingClientRect().top,
            headingTop: title.querySelector('h1').getBoundingClientRect().top,
            nextTitleTop: document.querySelector('#standalone-title').getBoundingClientRect().top,
            startSpan: Number(start.style.getPropertyValue('--lf-toc-span')),
          };
        }"""
    )
    assert geometry["headingTop"] > geometry["titleTop"], geometry
    assert geometry["startSpan"] == pytest.approx(
        geometry["nextTitleTop"] - geometry["titleTop"], abs=1
    ), geometry
    assert geometry["markerCenter"] == pytest.approx(geometry["trackTop"], abs=1), (
        geometry
    )
    assert geometry["lensTop"] == pytest.approx(geometry["markerCenter"], abs=1), (
        geometry
    )

    # Native fragment navigation brings the eyebrow with the heading; the viewport
    # lens meets that destination's marker rather than the top of its link box.
    standalone.focus()
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"#standalone-title$"))
    scroll_settled(page)
    expect(standalone).to_have_attribute("aria-current", "location")
    alignment = standalone.evaluate(
        """link => {
          const row = link.parentElement;
          const marker = getComputedStyle(row, '::before');
          return {
            markerCenter: row.getBoundingClientRect().top +
              parseFloat(marker.top) + new DOMMatrixReadOnly(marker.transform).m42 +
              parseFloat(marker.height) / 2,
            lensTop: link.closest('nav').querySelector('.lf-toc-window')
              .getBoundingClientRect().top,
            eyebrowTop: document.querySelector('#standalone-title .eyebrow')
              .getBoundingClientRect().top,
          };
        }"""
    )
    assert alignment["eyebrowTop"] >= 0, alignment
    assert alignment["lensTop"] == pytest.approx(alignment["markerCenter"], abs=2), (
        alignment
    )


def test_contents_with_every_destination_hidden_returns_when_the_disclosure_opens(
    browser, serve
):
    """An empty displayed route has no current destination, then recovers on reveal."""
    source = leaf_page(
        "closed contents",
        """
<details>
  <summary>Open the migration plan</summary>
  <h1>Migration plan</h1>
  <aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>
  <h2 id="prepare">Prepare the readers</h2>
  <div style="height: 110vh"></div>
  <h2 id="verify">Verify both copies</h2>
  <div style="height: 110vh"></div>
</details>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page", include_hidden=True)
    expect(nav).to_be_hidden()
    expect(nav.locator("[aria-current]")).to_have_count(0)
    page.get_by_text("Open the migration plan", exact=True).click()
    expect(nav).to_be_visible()
    expect(nav.locator(".lf-toc-start a")).to_have_attribute("aria-current", "location")
    expect(nav.locator("[data-lf-toc-hidden]")).to_have_count(0)
    page.get_by_text("Open the migration plan", exact=True).click()
    expect(nav).to_be_hidden()
    expect(nav.locator("[aria-current]")).to_have_count(0)


def test_contents_reconciles_live_title_boundaries_and_preserves_its_reading_position(
    browser, serve
):
    """A retained ToC follows the current authored outline without replacing its links.

    Grouping a title changes its destination, and adding, dropping or renaming a heading
    changes the route. Surviving links retain focus and the outline's native scroll.
    """
    title = '<p class="eyebrow">Stage</p><h1 id="title">Report</h1>'
    sections = [
        f'<section id="part-{index}"><h2 id="label-{index}">Migration part {index}</h2></section>'
        for index in range(1, 81)
    ]
    source = leaf_page(
        "live contents",
        title
        + '<aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>'
        + '<h2 id="body-title">Body</h2>'
        + "".join(sections),
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1400, 900)
    toc = page.locator("#contents")
    nav = page.get_by_role("navigation", name="On this page")
    start = nav.locator(".lf-toc-start a")
    expect(start).to_have_attribute("href", "#title")
    expect(toc).to_have_attribute("data-lf-outline", "")
    expect(nav.locator("a")).to_have_count(82)
    body = nav.get_by_role("link", name="Body", exact=True)
    expect(body).to_have_attribute("href", "#body-title")
    held_body = body.element_handle()
    survivor = nav.get_by_role("link", name="Migration part 80", exact=True)
    survivor.focus()
    expect(survivor).to_be_focused()
    held_survivor = survivor.element_handle()
    reading_position = nav.evaluate("node => node.scrollTop")
    assert reading_position > 0

    grouped = source.replace(
        title, f'<hgroup id="title-group">{title}</hgroup>'
    ).replace(
        '<h2 id="body-title">Body</h2>',
        '<hgroup id="body-group"><p class="eyebrow">One section</p>'
        '<h2 id="body-title">Named body</h2></hgroup>',
    )
    (serve.page_dir / "index.html").write_text(grouped, encoding="utf-8")
    told(page)
    rendered(page)
    expect(start).to_have_attribute("href", "#title-group")
    renamed_body = nav.get_by_role("link", name="Named body", exact=True)
    expect(renamed_body).to_have_attribute("href", "#body-group")
    assert held_body.evaluate(
        "held => held === document.querySelector('#contents a[href=\"#body-group\"]')"
    )
    assert held_survivor.evaluate("held => held === document.activeElement")
    assert nav.evaluate("node => node.scrollTop") == pytest.approx(
        reading_position, abs=1
    )

    changed = grouped.replace(
        sections[39],
        '<section id="new-part"><h2>New destination</h2></section>',
    ).replace("Migration part 41", "Renamed destination")
    (serve.page_dir / "index.html").write_text(changed, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav.locator("a")).to_have_count(82)
    expect(nav.get_by_role("link", name="Migration part 40", exact=True)).to_have_count(
        0
    )
    expect(
        nav.get_by_role("link", name="New destination", exact=True)
    ).to_have_attribute("href", "#new-part")
    expect(
        nav.get_by_role("link", name="Renamed destination", exact=True)
    ).to_have_attribute("href", "#part-41")
    assert held_survivor.evaluate(
        "held => held === document.activeElement && held === "
        "document.querySelector('#contents a[href=\"#part-80\"]')"
    )
    assert nav.evaluate("node => node.scrollTop") == pytest.approx(
        reading_position, abs=1
    )


def test_an_empty_contents_route_follows_headings_arriving_and_leaving(browser, serve):
    """A ToC with no initial outline can present one later and retire it again."""
    source = leaf_page(
        "changing contents",
        '<h1>Report</h1><aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>'
        '<p id="body">The body has no section headings.</p>',
    )
    page = open_page(browser, live_url(serve(source)))
    nav = page.get_by_role("navigation", name="On this page", include_hidden=True)
    expect(nav).to_be_hidden()
    expect(nav.locator("li a")).to_have_count(0)

    headed = source.replace(
        '<p id="body">', '<h2 id="arrived">An arriving section</h2><p id="body">'
    )
    (serve.page_dir / "index.html").write_text(headed, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav).to_be_visible()
    expect(nav.get_by_role("link", name="An arriving section")).to_have_attribute(
        "href", "#arrived"
    )

    (serve.page_dir / "index.html").write_text(source, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav).to_be_hidden()
    expect(nav.locator("li a")).to_have_count(0)
    expect(nav.locator("[aria-current]")).to_have_count(0)


def test_a_table_of_contents_link_is_a_finger_s_aim(browser, serve):
    """The open outline stacks its links with no gap between them, so each link's box
    is all there is to land on. Under a finger they stood 24px tall where the layer's
    floor is 44; a mouse keeps its compact rows."""
    source = leaf_page(
        "contents",
        """
<h1>Migration plan</h1>
<lf-toc id="contents"></lf-toc>
<section><h2 id="prepare">Prepare</h2><p>Take a snapshot.</p></section>
<section><h2 id="verify">Verify</h2><p>Compare the totals.</p></section>
""",
    )
    url = serve(source)
    heights = "links => links.map(link => link.getBoundingClientRect().height)"
    touch = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=touch)
    links = page.get_by_role("navigation", name="On this page").get_by_role("link")
    expect(links).to_have_count(2)
    assert all(h >= 44 for h in links.evaluate_all(heights))
    mouse = open_page(browser, url)
    links = mouse.get_by_role("navigation", name="On this page").get_by_role("link")
    expect(links).to_have_count(2)
    assert all(24 <= h < 30 for h in links.evaluate_all(heights))


def test_a_table_of_contents_can_stop_at_an_authored_heading_level(browser, serve):
    """The author decides which semantic levels belong in the page route.

    Deeper headings remain ordinary page headings: the contents widget neither links
    them nor gives them a fragment id. A linked heading without an id of its own takes
    one reserved for the runtime, and nothing stands beside it, so a page rule about
    which element follows which still finds the page's own."""
    source = leaf_page(
        "bounded contents",
        """
<h1>Migration plan</h1>
<lf-toc id="contents" max-level="3"></lf-toc>
<section>
  <h2 id="prepare">Prepare the readers</h2>
  <h3>Move one cohort</h3>
  <h4>Verify its checksum</h4>
</section>
""",
    )
    page = open_page(browser, serve(source))
    toc = page.get_by_role("navigation", name="On this page")

    assert toc.get_by_role("link").all_text_contents() == [
        "Prepare the readers",
        "Move one cohort",
    ]
    assert page.locator("h2, h3, h4").evaluate_all(
        "nodes => nodes.map(node => [node.localName, node.getAttribute('id'), "
        "node.previousElementSibling?.className || null])"
    ) == [
        ["h2", "prepare", None],
        ["h3", "lf-contents-section-2", None],
        ["h4", None, None],
    ]
    # That id is the runtime's, so a passage in the heading is addressed by the
    # section the page wrote, which the file can resolve too.
    # The user selects the heading's words.
    page.locator("h3").click(click_count=3)
    anchor = page.evaluate(
        """async () => {
          const { selectionAnchor } = await window.__lfRuntimeImport(
            '/runtime/composing/capture.js');
          return selectionAnchor(getSelection());
        }"""
    )
    assert anchor["quote"] == "Move one cohort", anchor
    assert not (anchor.get("section") or "").startswith("lf-"), anchor

    # A revision can give the heading an id of its own, or take it away again; the
    # row's link follows whichever id the heading carries.
    link = toc.get_by_role("link", name="Move one cohort")
    page.locator("h3").evaluate("heading => { heading.id = 'move'; }")
    expect(link).to_have_attribute("href", "#move")
    page.locator("h3").evaluate("heading => heading.removeAttribute('id')")
    expect(link).to_have_attribute("href", "#lf-contents-section-2")
    expect(page.locator("h3")).to_have_attribute("id", "lf-contents-section-2")


def test_generated_page_interface_reconciles_before_semantic_interaction(
    browser, serve
):
    """Generated interface paints while replay waits, then reconciles its geometry
    against the complete presented page before semantic interaction opens.

    The recorded draft makes the first section much taller during replay. The contents
    map has already painted the short authored form, so the presentation signal must
    replace that stale span in the same turn that releases durable interaction."""
    source = leaf_page(
        "stable generated interface",
        """
<h1>Migration plan</h1>
<aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>
<section>
  <h2 id="prepare">Prepare the readers</h2>
  <lf-draft id="notes"><pre>One short line.</pre></lf-draft>
</section>
<section>
  <h2 id="verify">Verify the readers</h2>
  <div style="height: 600px"></div>
</section>
""",
    )
    url = serve(source)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "notes",
            "action": "edit",
            "detail": {
                "text": "\n".join(
                    f"Migration checkpoint {number}." for number in range(1, 17)
                )
            },
        },
    )
    held = []
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.add_init_script(
        """
        window.__tocFirstPaint = null;
        new MutationObserver((records, observer) => {
          if (document.body?.dataset.lfPresented !== '1') return;
          const first = document.getElementById('prepare');
          const second = document.getElementById('verify');
          const nav = document.querySelector('.lf-toc-nav');
          const row = nav.querySelector('a[href="#prepare"]').parentElement;
          window.__tocFirstPaint = {
            visible: nav.checkVisibility({visibilityProperty: true}),
            span: Number(row.style.getPropertyValue('--lf-toc-span')),
            actual: second.getBoundingClientRect().top
              - first.getBoundingClientRect().top,
          };
          observer.disconnect();
        }).observe(document, {
          subtree: true,
          attributes: true,
          attributeFilter: ['data-lf-presented'],
        });
        """
    )
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    nav = page.locator(".lf-toc-nav")
    expect(nav).to_be_visible()
    prepare = nav.locator('a[href="#prepare"]')
    page.wait_for_function(
        "link => Number(link.parentElement.style"
        ".getPropertyValue('--lf-toc-span')) > 0",
        arg=prepare.element_handle(),
    )
    authored_span = prepare.evaluate(
        "link => Number(link.parentElement.style.getPropertyValue('--lf-toc-span'))"
    )

    held.pop(0).continue_()
    page.wait_for_function("() => window.__tocFirstPaint !== null")
    first_paint = page.evaluate("() => window.__tocFirstPaint")
    assert first_paint["visible"], first_paint
    assert first_paint["actual"] > authored_span + 200, (
        authored_span,
        first_paint,
    )
    assert first_paint["span"] == pytest.approx(first_paint["actual"], abs=1)
    wait_until_ready(page)


def test_an_eyebrow_and_heading_keep_one_title_rhythm_through_contents(browser, serve):
    """An eyebrow is the heading's label, so its small bottom margin is the room inside
    the title while the heading level's larger top margin remains outside the pair.

    An identified section owns the contents destination while its heading supplies the
    label. The clean section fragment brings the whole title into view and needs no
    generated node between the eyebrow and heading."""
    source = leaf_page(
        "eyebrow title rhythm",
        """
<h1>Two labeled sections</h1>
<lf-toc id="contents"></lf-toc>
<div style="height: 110vh"></div>
<p id="before-two">First section follows.</p>
<section id="section-two" aria-labelledby="title-two">
  <p class="eyebrow">release shape</p>
  <h2 id="title-two">Prepare the readers</h2>
  <p>Take a snapshot.</p>
</section>
<div style="height: 110vh"></div>
<p id="before-three">A subsection follows.</p>
<section id="section-three">
  <p class="eyebrow">first cohort</p>
  <h3>Move the readers</h3>
  <p>Shift one cohort at a time.</p>
</section>
<div style="height: 110vh"></div>
""",
    )
    page = open_page(browser, serve(source))
    rhythm = page.evaluate(
        """() => Object.fromEntries([
          ['h2', ['section-two', 'before-two']],
          ['h3', ['section-three', 'before-three']],
        ].map(([level, [sectionId, beforeId]]) => {
          const section = document.getElementById(sectionId);
          const eyebrow = section.querySelector(':scope > .eyebrow');
          const heading = section.querySelector(`:scope > ${level}`);
          const before = document.getElementById(beforeId);
          const between = [];
          for (let node = eyebrow.nextElementSibling; node !== heading;
               node = node.nextElementSibling) between.push(node.className);
          const eyebrowBox = eyebrow.getBoundingClientRect();
          const headingBox = heading.getBoundingClientRect();
          return [level, {
            outer: eyebrowBox.top - before.getBoundingClientRect().bottom,
            inner: headingBox.top - eyebrowBox.bottom,
            between,
          }];
        }))"""
    )
    assert rhythm == {
        "h2": {"outer": 48, "inner": 10, "between": []},
        "h3": {"outer": 32, "inner": 10, "between": []},
    }

    toc = page.get_by_role("navigation", name="On this page")
    assert toc.get_by_role("link").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"
    ) == ["#section-two", "#section-three"]
    expect(page.locator("#section-two")).to_have_attribute(
        "aria-labelledby", "title-two"
    )
    expect(page.locator("#section-two > h2")).to_have_attribute("id", "title-two")
    toc.get_by_role("link", name="Move the readers").click()
    expect(page).to_have_url(re.compile(r"#section-three$"))
    scroll_settled(page)
    arrival = page.locator("#section-three").evaluate(
        """section => {
          const root = document.scrollingElement;
          const eyebrow = section.querySelector(':scope > .eyebrow');
          const heading = section.querySelector(':scope > h3');
          return {
            clear: parseFloat(getComputedStyle(root).scrollPaddingTop),
            margin: parseFloat(getComputedStyle(section).scrollMarginTop),
            section: section.getBoundingClientRect().top,
            eyebrow: eyebrow.getBoundingClientRect().top,
            heading: heading.getBoundingClientRect().top,
          };
        }"""
    )
    destination_top = arrival["clear"] + arrival["margin"]
    assert arrival["section"] == pytest.approx(destination_top, abs=1)
    assert arrival["eyebrow"] == pytest.approx(destination_top, abs=1)
    assert arrival["heading"] > arrival["eyebrow"]


def test_table_of_contents_history_is_native_back_and_forward(browser, serve):
    """A map link creates an ordinary fragment-history entry on the root scrollport.

    Back restores the reading position from before the click and Forward restores the
    fragment destination. The shared travel pass reveals the destination while the
    browser retains each entry's reading position."""
    source = leaf_page(
        "native contents history",
        """
<h1>Migration plan</h1>
<aside class="sidebar"><lf-toc id="history-contents"></lf-toc></aside>
<section><h2 id="prepare">Prepare the readers</h2><div style="height: 900px"></div></section>
<section><h2 id="move">Move the readers</h2><div style="height: 900px"></div></section>
<section><h2 id="verify">Verify the readers</h2><div style="height: 600px"></div></section>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 800)
    assert page.evaluate("history.scrollRestoration") == "auto"

    bookmark = 420
    page.evaluate(
        "top => document.scrollingElement.scrollTo({top, behavior: 'instant'})",
        bookmark,
    )
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 1", arg=bookmark
    )
    navigation = page.get_by_role("navigation", name="On this page")
    move = navigation.get_by_role("link", name="Move the readers")
    navigation_box = navigation.bounding_box()
    assert navigation_box is not None
    # At rest the map takes the pointer on its spine alone.
    page.mouse.move(
        navigation_box["x"] + 2,
        navigation_box["y"] + navigation_box["height"] / 2,
    )
    expect(move).to_have_css("pointer-events", "auto")
    move.click()
    expect(page).to_have_url(re.compile(r"#move$"))
    page.wait_for_function(
        "() => document.getElementById('move').getBoundingClientRect().top < 150"
    )
    destination = page.evaluate("document.scrollingElement.scrollTop")
    assert destination > bookmark + 400

    page.evaluate("history.back()")
    page.wait_for_function("() => location.hash === ''")
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=bookmark
    )

    page.evaluate("history.forward()")
    page.wait_for_function("() => location.hash === '#move'")
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2",
        arg=destination,
    )


def test_a_margin_table_of_contents_maps_the_document_until_the_user_enters_it(
    browser, serve
):
    """The roomy margin is a stable reading map rather than a compressed outline.

    Section rows divide the available height according to the content they lead, a
    moving lens shows the visible band, and late content growth redraws both. Labels
    reveal without moving the map or changing the item under the pointer. The same
    links remain an ordinary open outline where the margin posture is unavailable.

    The map runs to the window's foot, so the shortcut bar stands over the last section it
    names — always the last, the map being sized to the viewport rather than scrolled.
    The line is a hover here and the map is not one of the regions that ends above it;
    `lf-toc`'s own rule in the default theme carries that decision and its TODO. This
    holds the map to the window so the cutoff cannot close a region at a time."""
    source = leaf_page(
        "contents map",
        """
<h1>Migration plan for the readers already in flight</h1>
<style>
  html { scroll-behavior: smooth; }
  #capacity, #limits { margin-block: 0; }
</style>
<div id="orientation" style="height: 420px"></div>
<aside class="sidebar" id="route"><lf-toc id="contents"></lf-toc></aside>
<section><h2 id="prepare">Prepare the copy without moving the active readers</h2><p><button id="underlying">Take a snapshot.</button></p></section>
<div style="height: 90px"></div>
<section>
  <h3 id="capacity">Check capacity before opening the longer transfer window</h3>
  <h3 id="limits">Confirm the limits without moving the waiting readers</h3>
  <p>Leave room for both copies.</p>
</section>
<div id="late-content" style="height: 180px"></div>
<section><h2 id="move">Move each cohort while preserving its reading position</h2><p>Shift one cohort at a time.</p></section>
<div style="height: 640px"></div>
<section><h2 id="verify">Verify both readings before releasing the original copy</h2><p>Compare the totals.</p></section>
<div style="height: 380px"></div>
""",
    )
    url = serve(with_one_ask(source))
    page = open_page(browser, url)
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    toc = page.locator("#contents")
    start = nav.locator(".lf-toc-start a")
    prepare = nav.get_by_role("link", name="Prepare the copy", exact=False)
    capacity = nav.get_by_role("link", name="Check capacity", exact=False)
    verify = nav.get_by_role("link", name="Verify both readings", exact=False)
    page.mouse.move(1200, 700)
    # Every row says its own word as text, the start row included. Its word used to be an
    # attribute the rail form drew with `content: attr()`, which left the link that names
    # the whole document saying nothing at all to any reading that asks a link what it
    # says — the accessible name it falls back to, a text dump, the widget's own outline.
    said = nav.locator("a").evaluate_all(
        "links => links.map(a => a.textContent.trim())"
    )
    assert said and all(said), f"a contents row carries no words: {said}"
    expect(start).to_have_text("Migration plan for the readers already in flight")
    expect(start).to_have_attribute("href", re.compile(r"^#lf-contents-section-0"))
    expect(start).to_have_attribute("aria-current", "location")
    expect(toc).to_have_css("position", "fixed")
    # The map is all its sidebar holds, so the sidebar stands as the map alone and floats
    # nothing beside the column.
    expect(page.locator("main")).to_have_attribute(
        "data-lf-margin", re.compile(r"\bmap\b")
    )
    expect(page.locator("aside.sidebar")).to_have_css("float", "none")
    expect(prepare).to_have_css("opacity", "0")
    expect(prepare).to_have_css("pointer-events", "none")
    motion = prepare.evaluate(
        "node => { const s = getComputedStyle(node); "
        "return {property: s.transitionProperty, duration: s.transitionDuration, "
        "timing: s.transitionTimingFunction}; }"
    )
    assert motion == {
        "property": "color, opacity",
        "duration": "0.12s, 0.24s",
        "timing": "ease-out, ease-out",
    }
    nav_box = nav.bounding_box()
    toc_box = toc.bounding_box()
    banner_box = page.locator(".lf-banner").bounding_box()
    assert nav_box is not None
    assert toc_box is not None
    assert banner_box is not None
    assert 23 <= nav_box["x"] <= 25
    assert 64 <= nav_box["y"] <= 68
    assert nav_box["height"] >= 740, f"the reading map used only {nav_box['height']}px"
    padding = toc.evaluate(
        "node => parseFloat(getComputedStyle(node).paddingBlockStart)"
    )
    assert toc_box["y"] == pytest.approx(banner_box["y"] + banner_box["height"], abs=1)
    # The map ends where the bottom bar starts.
    assert toc_box["y"] + toc_box["height"] == pytest.approx(
        page.locator(".lf-shortcut-bar").bounding_box()["y"], abs=1
    )
    assert nav_box["y"] == pytest.approx(toc_box["y"] + padding, abs=1)
    assert nav_box["y"] + nav_box["height"] == pytest.approx(
        toc_box["y"] + toc_box["height"] - padding, abs=1
    )

    # At rest the map takes the pointer on its spine alone, so the words beside it stay
    # the page's; once entered, the whole map keeps the pointer across its labels and
    # the padding that keeps it clear of the banner.
    page.mouse.move(nav_box["x"] + 100, nav_box["y"] + 20)
    assert not toc.evaluate("node => node.matches(':hover')")
    page.mouse.move(nav_box["x"] + 2, nav_box["y"] + 20, steps=4)
    assert toc.evaluate("node => node.matches(':hover')")
    expect(prepare).to_have_css("opacity", "1")
    expect(prepare).to_have_css("pointer-events", "auto")
    page.mouse.move(nav_box["x"] + 100, nav_box["y"] - 8, steps=8)
    assert toc.evaluate("node => node.matches(':hover')")
    page.mouse.move(nav_box["x"] + 100, toc_box["y"] - 2)
    assert page.evaluate(
        "point => document.elementFromPoint(point.x, point.y)?.closest('.lf-banner') !== null",
        {"x": nav_box["x"] + 100, "y": toc_box["y"] - 2},
    )
    expect(prepare).to_have_css("opacity", "0")
    # The bottom bar is attached to the window's foot, so the map ends above it with its
    # last entry in view, as every region does.
    line_box = page.locator(".lf-shortcut-bar").bounding_box()
    assert line_box is not None, "the fixture drew no shortcut bar"
    assert nav_box["y"] + nav_box["height"] <= line_box["y"] + 1, (
        f"the bottom bar stands over the map's foot: map {nav_box}, band {line_box}"
    )
    assert nav_box["width"] == pytest.approx(320, abs=1)

    resized(page, 1800, 900)
    expect(nav).to_have_css("width", "320px")
    resized(page, 1188, 900)
    expect(nav).to_have_css("width", "320px")
    underlying = page.locator("#underlying")
    underlying.evaluate(
        "node => node.addEventListener('pointerdown', "
        "() => { window.lfUnderlyingPressed = true; }, { once: true })"
    )
    underlying_box = underlying.bounding_box()
    assert underlying_box is not None
    underlying_point = {
        "x": underlying_box["x"] + 4,
        "y": underlying_box["y"] + underlying_box["height"] / 2,
    }
    assert page.evaluate(
        "point => document.elementFromPoint(point.x, point.y)?.closest('#underlying') !== null",
        underlying_point,
    ), "the dormant contents map covered an authored control"
    page.mouse.click(underlying_point["x"], underlying_point["y"])
    assert page.evaluate("window.lfUnderlyingPressed") is True
    resized(page, 1400, 900)
    page.mouse.move(1200, 700)
    assert nav.bounding_box() == nav_box
    markers = nav.locator(".lf-toc-start, li").evaluate_all(
        """items => items.map(item => {
          const style = getComputedStyle(item, '::before');
          const box = item.getBoundingClientRect();
          return {content: style.content, width: style.width, height: style.height,
                  color: style.backgroundColor, x: box.x + parseFloat(style.left),
                  y: box.y + parseFloat(style.top) +
                    new DOMMatrixReadOnly(style.transform).m42, rowY: box.y,
                  labelY: item.querySelector(':scope > a').getBoundingClientRect().y};
        })"""
    )
    assert markers[0]["content"] == '""' and markers[0]["width"] == "3px"
    assert markers[0]["color"] != "rgba(0, 0, 0, 0)"
    assert len({round(marker["x"]) for marker in markers}) == 1
    assert all(
        marker["y"] == pytest.approx(marker["labelY"] + 7, abs=1) for marker in markers
    )
    assert markers[-1]["y"] > nav_box["y"] + nav_box["height"] * 0.68
    assert markers[4]["y"] - markers[3]["y"] > markers[3]["y"] - markers[2]["y"]

    # The flex rows preserve the raw document scale from which the visible map is fitted.
    # Nearby destinations bend together just enough for every label to remain distinct.
    map_layout = nav.locator(".lf-toc-rows").evaluate(
        """rows => {
          const track = rows.getBoundingClientRect();
          const items = [...rows.querySelectorAll('.lf-toc-start, li')];
          const spans = items.map(item =>
            Number(item.style.getPropertyValue('--lf-toc-span')));
          const total = spans.reduce((sum, span) => sum + span, 0);
          let before = 0;
          return items.map((item, index) => {
            const row = item.getBoundingClientRect();
            const label = item.querySelector(':scope > a').getBoundingClientRect();
            const expected = track.top + track.height * before / total;
            before += spans[index];
            return {rowTop: row.top, rowHeight: row.height, expected,
                    labelTop: label.top, labelBottom: label.bottom,
                    labelHeight: label.height};
          });
        }"""
    )
    assert all(
        item["rowTop"] == pytest.approx(item["expected"], abs=1) for item in map_layout
    )
    assert capacity.evaluate(
        "node => node.parentElement.getBoundingClientRect().height "
        "< node.getBoundingClientRect().height"
    )
    assert any(
        item["labelTop"] != pytest.approx(item["rowTop"], abs=1) for item in map_layout
    ), "the crowded destinations stayed on their overlapping raw positions"
    assert all(
        right["labelTop"] >= left["labelBottom"] - 1
        for left, right in pairwise(map_layout)
    ), f"the fitted contents labels overlap: {map_layout}"

    # The start row and top-level sections share one typographic edge. Depth changes
    # indentation, never the spine or the marker position.
    text_edge = (
        "node => node.getBoundingClientRect().x "
        "+ parseFloat(getComputedStyle(node).paddingLeft)"
    )
    assert abs(start.evaluate(text_edge) - prepare.evaluate(text_edge)) <= 1
    assert capacity.evaluate(text_edge) > prepare.evaluate(text_edge) + 7
    title_type = start.evaluate(
        "node => { const s = getComputedStyle(node); "
        "return {family: s.fontFamily, caps: s.fontVariantCaps}; }"
    )
    section_type = prepare.evaluate(
        "node => { const s = getComputedStyle(node); "
        "return {family: s.fontFamily, caps: s.fontVariantCaps}; }"
    )
    assert title_type == {**section_type, "caps": "normal"}
    expect(prepare).to_have_css("-webkit-line-clamp", "2")

    lens = nav.locator(".lf-toc-window")
    lens_before = lens.bounding_box()
    assert lens_before is not None
    assert 14 <= lens_before["height"] < nav_box["height"]

    # A Mermaid render, image load, disclosure, or other late block can change the
    # document after upgrade. Growing one such block must move the later sections in
    # the map without changing the rail's own box.
    move_before = markers[4]["y"]
    page.locator("#late-content").evaluate("node => { node.style.height = '580px'; }")
    page.wait_for_function(
        "before => { const item = document.querySelector('a[href=\"#move\"]').parentElement; "
        "const style = getComputedStyle(item, '::before'); "
        "return item.getBoundingClientRect().y + parseFloat(style.top) "
        "+ new DOMMatrixReadOnly(style.transform).m42 > before + 20; }",
        arg=move_before,
    )
    assert nav.bounding_box() == nav_box
    hidden_boxes = nav.locator(".lf-toc-start, li, a").evaluate_all(
        "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); "
        "return [r.x, r.y, r.width, r.height]; })"
    )
    resting_rows = nav.locator(".lf-toc-start, li").evaluate_all(
        "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); "
        "return [r.x, r.y, r.width, r.height]; })"
    )
    resting_marker_centers = nav.locator(".lf-toc-start, li").evaluate_all(
        "items => items.map(item => { const s = getComputedStyle(item, '::before'); "
        "const r = item.getBoundingClientRect(); "
        "return r.y + parseFloat(s.top) + new DOMMatrixReadOnly(s.transform).m42 "
        "+ parseFloat(s.height) / 2; })"
    )

    # The go-to menu can address the complete route without moving its geometry or focus
    # into the rail.
    page.keyboard.press("g")
    for link in nav.locator("a").all():
        expect(link).to_have_css("opacity", "1")
        expect(link).to_have_css("pointer-events", "auto")
    link_hints = page.locator(
        '.lf-go-to-hints > .lf-go-to-hint[data-lf-go-to-kind="Link"]'
    )
    expect(link_hints).to_have_count(nav.locator("a").count())
    assert (
        nav.locator(".lf-toc-start, li").evaluate_all(
            "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); "
            "return [r.x, r.y, r.width, r.height]; })"
        )
        == resting_rows
    )
    assert nav.evaluate("node => !node.contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(prepare).to_have_css("opacity", "0")
    expect(prepare).to_have_css("pointer-events", "none")

    page.mouse.move(nav_box["x"] + 20, nav_box["y"] + nav_box["height"] / 2)
    page.keyboard.press("g")
    expect(link_hints).to_have_count(nav.locator("a").count())
    for link in nav.locator("a").all():
        expect(link).to_have_css("pointer-events", "auto")
    page.keyboard.press("Escape")
    page.mouse.move(1200, 700)
    expect(prepare).to_have_css("opacity", "0")
    expect(prepare).to_have_css("pointer-events", "none")

    prepare.evaluate(
        "node => node.addEventListener('pointerdown', "
        "() => { window.lfTocPressed = true; }, { once: true })"
    )
    prepare_box = prepare.bounding_box()
    assert prepare_box is not None
    label_point = {"x": prepare_box["x"] + 100, "y": prepare_box["y"] + 4}
    # Entering at the spine reveals the labels, and the map keeps the pointer as it
    # moves on to one. There is no discovery click or dwell time to learn.
    page.mouse.move(1200, 700)
    expect(prepare).to_have_css("opacity", "0")
    expect(prepare).to_have_css("pointer-events", "none")
    page.mouse.move(nav_box["x"] + 2, label_point["y"])
    page.mouse.move(label_point["x"], label_point["y"], steps=8)
    assert nav.evaluate("node => node.matches(':hover')")
    assert prepare.evaluate("node => getComputedStyle(node).pointerEvents") == "auto"
    assert prepare.evaluate(
        "node => document.elementFromPoint("
        f"{label_point['x']}, {label_point['y']}) === node"
    ), "the fading label was visible but not the pointer target"
    page.mouse.click(label_point["x"], label_point["y"])
    expect(page).to_have_url(re.compile(r"#prepare$"))
    scroll_settled(page)
    assert page.evaluate("window.lfTocPressed") is True
    expect(prepare).to_have_attribute("aria-current", "location")
    assert prepare.evaluate("node => node.matches(':hover')")
    current_hover_color = prepare.evaluate("node => getComputedStyle(node).color")
    capacity_box = capacity.bounding_box()
    assert capacity_box is not None
    page.mouse.move(capacity_box["x"] + 100, capacity_box["y"] + 4)
    expect(capacity).not_to_have_attribute("aria-current", "location")
    expect(capacity).to_have_css("color", current_hover_color)
    revealed_boxes = nav.locator(".lf-toc-start, li, a").evaluate_all(
        "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); "
        "return [r.x, r.y, r.width, r.height]; })"
    )
    assert revealed_boxes == hidden_boxes

    marker_alignment = nav.locator(".lf-toc-start, li").evaluate_all(
        """items => items.map(item => {
          const marker = getComputedStyle(item, '::before');
          const row = item.getBoundingClientRect();
          const label = item.querySelector(':scope > a');
          const labelBox = label.getBoundingClientRect();
          const lineHeight = parseFloat(getComputedStyle(label).lineHeight);
          return {
            label: label.textContent.trim(),
            visible: getComputedStyle(label).opacity === '1',
            rowTop: row.top,
            markerCenter:
              row.top + parseFloat(marker.top) + new DOMMatrixReadOnly(marker.transform).m42 +
              parseFloat(marker.height) / 2,
            labelCenter: labelBox.top + lineHeight / 2,
          };
        })"""
    )
    assert sum(item["visible"] for item in marker_alignment) == len(marker_alignment)
    assert all(
        item["markerCenter"] == pytest.approx(item["labelCenter"], abs=2)
        for item in marker_alignment
    ), f"a contents marker parted from its revealed label: {marker_alignment}"
    assert all(
        item["markerCenter"] == pytest.approx(resting, abs=1)
        for item, resting in zip(marker_alignment, resting_marker_centers, strict=True)
    ), f"revealing the contents map moved a marker: {marker_alignment}"

    # The viewport rail stays put through the whole document, including where its
    # authored sidebar has not reached the sticky edge yet and where main ends.
    for position in (0, 750, 10_000):
        page.evaluate(
            "top => document.scrollingElement.scrollTo({top, behavior: 'instant'})",
            position,
        )
        assert nav.bounding_box() == nav_box

    # A wheel over the rail stays in the document's native scroll chain.
    page.evaluate("document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})")
    page.mouse.move(nav_box["x"] + nav_box["width"] / 2, nav_box["y"] + 300)
    page.mouse.wheel(0, 260)
    page.wait_for_function("() => document.scrollingElement.scrollTop >= 250")
    page.mouse.wheel(0, 260)
    page.mouse.wheel(0, 260)
    page.wait_for_function("() => document.scrollingElement.scrollTop >= 750")
    assert page.locator("aside.sidebar").evaluate("node => node.scrollTop") == 0

    # Map travel keeps the user oriented rather than teleporting. Start recording
    # on the click so preparing the gesture cannot exhaust the frame sequence.
    verify.evaluate("""link => {
      document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
      window.lfTocFrames = [];
      link.addEventListener('click', () => {
        const sample = () => {
          window.lfTocFrames.push(document.scrollingElement.scrollTop);
          if (window.lfTocFrames.length < 90) requestAnimationFrame(sample);
        };
        sample();
      }, {once: true});
    }""")
    verify_box = verify.bounding_box()
    assert verify_box is not None
    page.mouse.move(verify_box["x"] + 4, verify_box["y"] + 4)
    expect(verify).to_have_css("pointer-events", "auto")
    verify.click()
    expect(page).to_have_url(re.compile(r"#verify$"))
    page.wait_for_function("() => document.scrollingElement.scrollTop > 0")
    scroll_settled(page)
    frames = page.evaluate("window.lfTocFrames")
    travelled = [position for position in frames if position > 0]
    assert len({round(position) for position in travelled}) >= 3, frames
    assert all(left <= right for left, right in pairwise(travelled)), frames

    start_href = start.get_attribute("href")
    assert start_href is not None
    start_box = start.bounding_box()
    assert start_box is not None
    page.mouse.move(start_box["x"] + 4, start_box["y"] + 4)
    expect(start).to_have_css("pointer-events", "auto")
    start.click()
    expect(page).to_have_url(re.compile(rf"{re.escape(start_href)}$"))
    scroll_settled(page)
    assert (
        page.locator(start_href).evaluate("node => node.getBoundingClientRect().top")
        < 150
    )

    page.evaluate("document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})")
    prepare_box = prepare.bounding_box()
    assert prepare_box is not None
    page.mouse.move(prepare_box["x"] + 4, prepare_box["y"] + 4)
    expect(prepare).to_have_css("pointer-events", "auto")
    prepare.click()
    expect(page).to_have_url(re.compile(r"#prepare$"))
    expect(prepare).to_have_attribute("aria-current", "location")
    scroll_settled(page)
    after_navigation = nav.bounding_box()
    assert after_navigation is not None
    assert after_navigation == nav_box, "following a link moved the contents rail"
    assert prepare.evaluate("node => node.matches(':hover')")
    current_alignment = prepare.evaluate(
        "node => ({label: node.getBoundingClientRect().top "
        "+ parseFloat(getComputedStyle(node).lineHeight) / 2, "
        "lens: node.closest('nav').querySelector('.lf-toc-window')"
        ".getBoundingClientRect().top})"
    )
    assert current_alignment["lens"] == pytest.approx(
        current_alignment["label"], abs=2
    ), f"the viewport lens parted from the current title: {current_alignment}"

    # The lens is the viewport's position, not a destination travelling toward it: the
    # scroll itself moves it, so the first frame after the scroll finds it beside the
    # title it scrolled to.
    lens_frame = verify.evaluate(
        """node => new Promise((resolve) => {
          document.querySelector('#verify')
            .scrollIntoView({block: 'start', behavior: 'instant'});
          requestAnimationFrame(() => resolve({
            lens: node.closest('nav').querySelector('.lf-toc-window')
              .getBoundingClientRect().top,
            label: node.getBoundingClientRect().top +
              parseFloat(getComputedStyle(node).lineHeight) / 2,
          }));
        })"""
    )
    assert lens_frame["lens"] == pytest.approx(lens_frame["label"], abs=2), lens_frame
    expect(verify).to_have_attribute("aria-current", "location")
    lens_after = lens.bounding_box()
    assert lens_after is not None
    assert lens_after["y"] > lens_before["y"] + nav_box["height"] * 0.08

    page.mouse.move(1200, 700)
    expect(prepare).to_have_css("opacity", "0")
    page.evaluate(RELEASE_FOCUS)
    # Twice: the layer's skip link is the document's first stop, and the map is what the
    # page itself opens with.
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(start).to_be_focused()
    expect(start).to_have_css("opacity", "1")
    expect(start).to_have_css("outline-style", "solid")
    expect(start).to_have_css("outline-width", "2px")
    expect(start).to_have_css("outline-offset", "-2px")

    # The Queue panel stands over the map and changes nothing about it.
    page.evaluate(RELEASE_FOCUS)
    toggle_queue(page)
    expect(toc).to_have_css("position", "fixed")
    expect(prepare).to_have_css("opacity", "0")
    toggle_queue(page, open=False)

    resized(page, 700, 900)
    expect(prepare).to_have_css("opacity", "1")
    expect(prepare).to_have_css("pointer-events", "auto")
    expect(start).to_be_hidden()

    resized(page, 1400, 900)
    page.emulate_media(media="print")
    rendered(page)
    expect(prepare).to_have_css("opacity", "1")
    expect(start).to_be_visible()

    page.emulate_media(media="screen", forced_colors="active")
    rendered(page)
    page.mouse.move(1200, 700)
    expect(prepare).to_have_css("opacity", "0")
    forced_colors = nav.evaluate(
        "node => { const rows = node.querySelector('.lf-toc-rows'); "
        "const lens = node.querySelector('.lf-toc-window'); "
        "const items = [...node.querySelectorAll('.lf-toc-start, li')]; "
        "const current = items.find(item => item.querySelector('[aria-current]')); "
        "return { spine: getComputedStyle(rows, '::before').backgroundColor, "
        "lens: getComputedStyle(lens).backgroundColor, "
        "current: getComputedStyle(current, '::before').backgroundColor, "
        "inactive: items.filter(item => item !== current).map(item => "
        "getComputedStyle(item, '::before').backgroundColor) }; }"
    )
    canvas = page.locator("body").evaluate(
        "node => getComputedStyle(node).backgroundColor"
    )
    assert forced_colors["spine"] != canvas
    assert forced_colors["lens"] == forced_colors["current"]
    assert forced_colors["lens"] != forced_colors["spine"]
    assert all(color == forced_colors["spine"] for color in forced_colors["inactive"])

    page.emulate_media(media="screen", forced_colors="none", reduced_motion="reduce")
    rendered(page)
    prepare_box = prepare.bounding_box()
    assert prepare_box is not None
    page.mouse.move(prepare_box["x"] + 4, prepare_box["y"] + 4)
    expect(prepare).to_have_css("opacity", "1")
    expect(prepare).to_have_css("pointer-events", "auto")
    expect(prepare).to_have_css("transition-duration", "0s")
    start_box = start.bounding_box()
    assert start_box is not None
    page.mouse.move(start_box["x"] + 4, start_box["y"] + 4)
    start.click()
    expect(page).to_have_url(re.compile(rf"{re.escape(start_href)}$"))
    assert (
        page.locator(start_href).evaluate("node => node.getBoundingClientRect().top")
        < 150
    )
    page.close()

    # A wide touch screen still gets the ordinary sticky sidebar. The ToC fixes itself
    # only in the fine-pointer posture where its hover map and wheel bridge are active.
    context = browser.new_context(
        viewport={"width": 1400, "height": 900}, has_touch=True
    )
    coarse = open_page(browser, url, context=context)
    expect(coarse.locator("aside.sidebar")).to_have_css("position", "sticky")
    expect(coarse.locator("#contents")).to_have_css("position", "static")
    expect(
        coarse.get_by_role("navigation", name="On this page").get_by_role(
            "link", name="Prepare the copy", exact=False
        )
    ).to_have_css("opacity", "1")
    coarse.locator("aside.sidebar").evaluate(
        "node => { node.style.maxHeight = '80px'; node.scrollTop = 0; }"
    )
    coarse.evaluate("document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})")
    coarse_box = coarse.locator("aside.sidebar").bounding_box()
    assert coarse_box is not None
    coarse.mouse.move(coarse_box["x"] + 40, coarse_box["y"] + 40)
    coarse.mouse.wheel(0, 80)
    coarse.wait_for_function(
        "() => document.querySelector('aside.sidebar').scrollTop > 0"
    )
    assert coarse.evaluate("document.scrollingElement.scrollTop") == 0, (
        "the in-flow ToC stole a wheel from its own overflowing sidebar"
    )


def test_the_reading_map_returns_when_a_hidden_sidebar_comes_back(browser, serve):
    """A wrapper that leaves the box tree and returns leaves the map as it found it.

    An author whose sidebar has nothing to say on a narrow shell hides it, which is
    what the developer gallery does; narrowing the window across that floor and back
    removes the map's whole wrapper and puts it back. The
    map is restored from the page's own posture, not from anything the wrapper
    remembers, because a box that has been away answers a style query with the reading
    it left with: asking the wrapper cost the user the spine for the rest of the
    session — an outline of thirteen laid rows became a fifteen-pixel heading stub that
    no settle, scroll, or further toggle brought back."""
    source = leaf_page(
        "hidden sidebar map",
        """
<style>
  main:not([data-lf-margin~="map"], [data-lf-margin~="sidebar"]) #route {
    display: none; }
</style>
<h1>Migration plan for the readers already in flight</h1>
<aside class="sidebar" id="route"><lf-toc id="contents"></lf-toc></aside>
<section><h2 id="prepare">Prepare the copy</h2><p>Take a snapshot.</p></section>
<div style="height: 600px"></div>
<section><h2 id="move">Move each cohort</h2><p>Shift one cohort at a time.</p></section>
<div style="height: 600px"></div>
<section><h2 id="verify">Verify both readings</h2><p>Compare the totals.</p></section>
<div style="height: 600px"></div>
""",
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    page = open_page(browser, serve(source), context=context)
    toc = page.locator("#contents")
    nav = page.get_by_role("navigation", name="On this page")
    heading = nav.locator(".lf-toc-heading")

    def rows():
        return nav.locator("li").evaluate_all(
            "items => items.filter(item => item.getBoundingClientRect().height > 0)"
            ".length"
        )

    expect(toc).to_have_css("position", "fixed")
    expect(heading).to_be_hidden()
    settled = toc.bounding_box()
    assert settled is not None
    laid = rows()
    assert laid >= 3, f"the fixture laid only {laid} map rows to begin with"

    resized(page, 800, 900)
    # Read the hidden posture rather than merely waiting the wrapper out. The page reads
    # it too — the map measures its own track on every reflow, hidden or not — and the
    # reading is what leaves the wrapper repeating it after the box comes back.
    expect(page.locator("#route")).to_have_css("display", "none")
    expect(toc).to_have_css("position", "static")

    resized(page, 1200, 900)
    # The wrapper itself holds no height in this posture — the map inside it is fixed —
    # so its return is a display reading rather than a visible box.
    expect(page.locator("#route")).not_to_have_css("display", "none")
    expect(toc).to_have_css("position", "fixed")
    expect(heading).to_be_hidden()
    assert toc.bounding_box() == settled, (
        f"the map came back as {toc.bounding_box()} rather than {settled}"
    )
    assert rows() == laid, "the map came back without its rows"


def test_a_crowded_document_map_reveals_every_heading_on_one_fitted_scale(
    browser, serve
):
    """Crowded destinations remain a complete route when the user enters it.

    The raw document positions leave less than half a line between neighbors. The
    fitted scale keeps every heading, marker, and label distinct without overflowing."""
    sections = "\n".join(
        f"<section><h2 id='part-{index}'>Migration part {index}</h2>"
        f"<p>Move cohort {index} only after its reading is stable.</p></section>"
        for index in range(1, 31)
    )
    source = leaf_page(
        "dense contents map",
        f"""
<h1>A migration with many independently verifiable steps</h1>
<aside class="sidebar"><lf-toc id="dense-contents"></lf-toc></aside>
{sections}
<div style="height: 1200px"></div>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    toc = page.locator("#dense-contents")

    expect(toc).to_have_attribute("data-lf-compact", "")
    nav_box = nav.bounding_box()
    assert nav_box is not None
    assert nav.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    markers = nav.locator(".lf-toc-start, li").evaluate_all(
        "items => items.map(item => { const s = getComputedStyle(item, '::before'); "
        "const r = item.getBoundingClientRect(); return r.y + parseFloat(s.top) "
        "+ new DOMMatrixReadOnly(s.transform).m42; })"
    )
    assert markers[-1] <= nav_box["y"] + nav_box["height"]
    shifts = nav.locator(".lf-toc-start, li").evaluate_all(
        "items => items.map(item => "
        "parseFloat(item.style.getPropertyValue('--lf-toc-row-shift')) || 0)"
    )
    assert any(abs(shift) > 1 for shift in shifts), shifts

    page.mouse.move(nav_box["x"] + 2, nav_box["y"] + 100)
    page.wait_for_function(
        """nav => {
          const links = [...nav.querySelectorAll('.lf-toc-start a, li a')];
          return links.every(link => getComputedStyle(link).opacity === '1'
            && link.getAnimations().every(m => m.playState === 'finished'));
        }""",
        arg=nav.element_handle(),
    )
    shown = nav.locator(".lf-toc-start a, li a").evaluate_all(
        "links => links.filter(link => getComputedStyle(link).opacity === '1')"
        ".map(link => link.textContent || link.getAttribute('aria-label'))"
    )
    assert len(shown) == nav.locator("a").count(), shown
    label_boxes = nav.locator(".lf-toc-start a, li a").evaluate_all(
        "links => links.map(link => { const box = link.getBoundingClientRect(); "
        "return {top: box.top, bottom: box.bottom}; })"
    )
    assert all(
        right["top"] >= left["bottom"] - 1 for left, right in pairwise(label_boxes)
    ), label_boxes
    first = nav.locator("li a").first
    expect(first).to_have_css("-webkit-line-clamp", "1")
    expect(first).to_have_css("pointer-events", "auto")
    href = first.get_attribute("href")
    first.click()
    expect(page).to_have_url(re.compile(rf"{re.escape(href)}$"))


def test_co_located_headings_share_the_current_title_and_lens_position(browser, serve):
    """The last title at one document position owns both readings of that position."""
    source = leaf_page(
        "co-located contents destinations",
        """
<h1>A migration with a shared handoff point</h1>
<aside class="sidebar"><lf-toc id="shared-contents"></lf-toc></aside>
<div style="height: 500px"></div>
<section style="position: relative; height: 120px">
  <h2 id="handoff" style="position: absolute; top: 0; margin: 0">Handoff</h2>
  <h3 id="checks" style="position: absolute; top: 0; margin: 0">Checks at handoff</h3>
</section>
<div style="height: 1200px"></div>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    handoff = nav.get_by_role("link", name="Handoff", exact=True)
    checks = nav.get_by_role("link", name="Checks at handoff", exact=True)

    assert handoff.bounding_box()["y"] < checks.bounding_box()["y"]
    page.locator("#checks").evaluate(
        "node => node.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    expect(checks).to_have_attribute("aria-current", "location")
    alignment = checks.evaluate(
        "node => ({label: node.getBoundingClientRect().top "
        "+ parseFloat(getComputedStyle(node).lineHeight) / 2, "
        "lens: node.closest('nav').querySelector('.lf-toc-window')"
        ".getBoundingClientRect().top})"
    )
    assert alignment["lens"] == pytest.approx(alignment["label"], abs=2), alignment


def test_a_route_taller_than_the_map_returns_to_an_open_outline(browser, serve):
    """A route that cannot physically fit keeps every heading in one honest form."""
    sections = "\n".join(
        f"<section><h2 id='part-{index}'>Migration part {index}</h2></section>"
        for index in range(1, 81)
    )
    source = leaf_page(
        "long contents route",
        f"""
<h1>A migration with more steps than the margin can show at once</h1>
<aside class="sidebar"><lf-toc id="long-contents"></lf-toc></aside>
{sections}
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 1800)
    toc = page.locator("#long-contents")
    nav = page.get_by_role("navigation", name="On this page")
    links = nav.locator("a")
    expect(links).to_have_count(81)
    expect(toc).not_to_have_attribute("data-lf-outline", "")
    links.last.focus()
    expect(links.last).to_be_focused()

    resized(page, 1400, 900)
    expect(toc).to_have_attribute("data-lf-outline", "")
    expect(nav.locator(".lf-toc-heading")).to_be_visible()
    assert nav.evaluate("node => node.scrollHeight > node.clientHeight")
    for link in (links.first, links.last):
        expect(link).to_have_css("opacity", "1")
        expect(link).to_have_css("pointer-events", "auto")
    expect(links.last).to_be_focused()
    expect(links.last).to_be_in_viewport()

    resized(page, 1400, 700)
    expect(toc).to_have_attribute("data-lf-outline", "")
    expect(links.last).to_be_focused()
    expect(links.last).to_be_in_viewport()

    resized(page, 1188, 600)
    expect(toc).to_have_attribute("data-lf-outline", "")
    nav_box = nav.bounding_box()
    column_left = page.locator("h1").bounding_box()["x"]
    assert nav_box["x"] + nav_box["width"] <= column_left - 16, (
        "the persistent outline covers the document instead of fitting its gutter: "
        f"outline ends at {nav_box['x'] + nav_box['width']:.0f}px, "
        f"column starts at {column_left:.0f}px"
    )
    assert nav.evaluate("node => getComputedStyle(node).backgroundColor") != (
        "rgba(0, 0, 0, 0)"
    )


def test_outline_measurement_preserves_manual_reading_position(browser, serve):
    sections = "\n".join(
        f"<section><h2 id='part-{index}'>Migration part {index}</h2></section>"
        for index in range(1, 81)
    )
    source = leaf_page(
        "long contents route",
        f"<h1>Migration</h1><aside class='sidebar'><lf-toc id='contents'></lf-toc></aside>{sections}",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    links = nav.locator("a")
    links.last.focus()
    nav.evaluate("node => { node.scrollTop = 0; }")
    assert nav.evaluate("node => node.scrollTop") == 0
    page.evaluate("""async () => {
      window.dispatchEvent(new Event('resize'));
      await new Promise(requestAnimationFrame);
      await new Promise(requestAnimationFrame);
    }""")
    assert nav.evaluate("node => node.scrollTop") == 0
    resized(page, 1400, 700)
    assert nav.evaluate("node => node.scrollTop") == 0


def test_the_document_map_remeasures_tab_swaps_and_skips_hidden_headings(
    browser, serve
):
    """An equal-height panel swap changes the map without resizing the document.

    Both panels occupy the same outer height but put their heading at a different point.
    The active panel's heading must own the remaining span and the hidden panel must own
    none; at the bottom, current location means the last visible heading rather than the
    last heading in DOM order."""
    source = leaf_page(
        "tabbed contents map",
        """
<h1>Two routes through the same migration window</h1>
<style>#first-route, #second-route { height: 1100px; overflow: hidden; }</style>
<aside class="sidebar"><lf-toc id="tab-contents"></lf-toc></aside>
<lf-tabs id="routes">
  <lf-tab id="first-route" label="First route">
    <h2 id="first-heading">Prepare the readers before opening the window</h2>
    <div style="height: 900px"></div>
  </lf-tab>
  <lf-tab id="second-route" label="Second route">
    <div style="height: 420px"></div>
    <h2 id="second-heading">Verify the readers after closing the window</h2>
    <div style="height: 480px"></div>
  </lf-tab>
</lf-tabs>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    first = nav.locator('a[href="#first-heading"]')
    second = nav.locator('a[href="#second-heading"]')
    span = "node => Number(node.parentElement.style.getPropertyValue('--lf-toc-span'))"
    main_height = page.locator("main").evaluate("node => node.scrollHeight")
    assert first.evaluate(span) > 500
    assert second.evaluate(span) == 0
    expect(first).to_be_visible()
    expect(second).to_be_hidden()

    page.evaluate(
        "document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight"
    )
    expect(first).to_have_attribute("aria-current", "location")
    expect(second).not_to_have_attribute("aria-current", "location")

    page.get_by_role("tab", name="Second route").click()
    page.wait_for_function(
        "() => Number(document.querySelector('a[href=\"#second-heading\"]')"
        ".parentElement.style.getPropertyValue('--lf-toc-span')) > 400"
    )
    assert page.locator("main").evaluate("node => node.scrollHeight") == main_height
    assert first.evaluate(span) == 0
    assert second.evaluate(span) > 400
    expect(first).to_be_hidden()
    expect(second).to_be_visible()
    page.evaluate(
        "document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight"
    )
    expect(second).to_have_attribute("aria-current", "location")
    expect(first).not_to_have_attribute("aria-current", "location")


def test_a_gloss_opens_at_its_phrase_for_pointer_keyboard_and_touch(browser, serve):
    """The explanation is a glance, not a mouse-only tooltip: the phrase opens it on
    hover, Tab reaches its Explain control, and a click pins it for mouse or touch. In
    every form the top-layer card remains inside the viewport, and both the phrase and
    explanation remain the page's authored words."""
    source = leaf_page(
        "gloss",
        """
<h1>Rollout</h1>
<p style="margin-top: 110vh; text-align: right">
  Start with a
  <lf-gloss id="gloss-path" tip="A thin, end-to-end path through the real system."
    >walking skeleton</lf-gloss
  >.
</p>
""",
    )
    url = serve(source)
    page = open_page(browser, url)
    gloss = page.locator("#gloss-path")
    mark = gloss.get_by_role("button", name="Explain “walking skeleton”")
    bubble = page.locator("#lf-gloss-tip-1")

    expect(bubble).to_be_hidden()
    affordance = gloss.evaluate(
        """el => {
          const phrase = getComputedStyle(el);
          const mark = el.querySelector('.lf-gloss-mark');
          const words = document.createRange();
          words.selectNodeContents(el.childNodes[0]);
          const tokens = document.createElement('span');
          tokens.style.cssText = 'color: var(--accent)';
          document.body.append(tokens);
          const tokenStyle = getComputedStyle(tokens);
          const accent = tokenStyle.color;
          tokens.remove();
          return {
            accent,
            extraWidth: el.getBoundingClientRect().width - words.getBoundingClientRect().width,
            underline: phrase.textDecorationColor,
            markOpacity: getComputedStyle(mark).opacity,
            markText: mark.textContent,
            markWidth: mark.getBoundingClientRect().width,
            pointer: phrase.cursor,
          };
        }"""
    )
    assert affordance["markText"] == ""
    assert affordance["markWidth"] == 1
    assert affordance["markOpacity"] == "0"
    assert affordance["pointer"] == "help"
    assert affordance["extraWidth"] == pytest.approx(0, abs=1)
    assert affordance["underline"] == affordance["accent"]
    gloss.hover()
    expect(bubble).to_be_visible()
    expect(bubble).to_have_text("A thin, end-to-end path through the real system.")

    # Auto popovers light-dismiss on a press outside the card. The phrase is outside
    # the card too, so the click that pins a hovered explanation must reconcile the
    # browser's just-closed popover with the widget state before the pointer leaves.
    gloss.click(position={"x": 20, "y": 8})
    page.mouse.move(0, 0)
    expect(bubble).to_be_visible()
    page.locator("h1").click()
    expect(bubble).to_be_hidden()
    gloss.hover()
    expect(bubble).to_be_visible()

    rect = bubble.evaluate("el => el.getBoundingClientRect()")
    viewport = page.evaluate("() => ({ width: innerWidth, height: innerHeight })")
    assert rect["left"] >= 0 and rect["right"] <= viewport["width"]
    assert rect["top"] >= 0 and rect["bottom"] <= viewport["height"]
    bubble.hover()
    expect(bubble).to_be_visible()

    # WCAG's hover-content route: Escape dismisses the card without requiring the
    # pointer to move away or transferring focus to a control the user never used.
    page.keyboard.press("Escape")
    expect(bubble).to_be_hidden()

    page.mouse.move(0, 0)
    expect(bubble).to_be_hidden()
    page.evaluate(RELEASE_FOCUS)
    # Walk from the layer's skip link through the current banner controls to the
    # first action in the page. The exact number of banner stops can change.
    for _ in range(12):
        page.keyboard.press("Tab")
        if mark.evaluate("node => document.activeElement === node"):
            break
    expect(mark).to_be_focused()
    expect(bubble).to_be_visible()
    expect(gloss).to_have_css("outline-style", "solid")
    page.keyboard.press("Escape")
    expect(bubble).to_be_hidden()

    assert gloss.evaluate("el => el.childNodes[0].textContent.trim()") == (
        "walking skeleton"
    )
    page.close()

    # A real touch context, not a mouse click standing in for one: the tap pins the
    # explanation without a hover state, and a tap elsewhere light-dismisses it.
    context = browser.new_context(
        viewport={"width": 420, "height": 900}, has_touch=True
    )
    touch = open_page(browser, url, context=context)
    touch_gloss = touch.locator("#gloss-path")
    touch_bubble = touch.locator("#lf-gloss-tip-1")
    touch_gloss.tap(position={"x": 20, "y": 8})
    expect(touch_bubble).to_be_visible()
    touch.locator("h1").tap()
    expect(touch_bubble).to_be_hidden()


def test_a_nested_platform_control_does_not_pin_its_gloss(browser, serve):
    """A nested control owns its click even when its platform contract is an ARIA role."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "gloss control",
                '<h1>Term</h1><p><lf-gloss tip="An explanation.">'
                'term <span role="button" tabindex="0">work it</span>'
                "</lf-gloss></p>",
            )
        ),
    )
    control = page.get_by_role("button", name="work it", exact=True)
    bubble = page.get_by_role("note")
    control.hover()
    expect(bubble).to_be_visible()
    control.click()
    page.mouse.move(0, 0)
    page.evaluate(RELEASE_FOCUS)
    expect(bubble).to_be_hidden()


def test_a_comment_on_a_gloss_reopens_its_explanation(browser, serve):
    """The tip is x-says page text, so a comment can rest on it like a tab's rendered
    label. Following that comment must reveal the otherwise hidden popover before the
    anchor scrolls; a durable thread cannot point to words the page then keeps closed."""
    tip = "A thin, end-to-end path through the real system."
    source = leaf_page(
        "gloss comment",
        f"""
<h1>Rollout</h1>
<p>Start with a <lf-gloss id="gloss-path" tip="{tip}">walking skeleton</lf-gloss>.</p>
""",
    )
    page = open_page(browser, serve(source, anchored=[("gloss-path", tip)]))
    bubble = page.locator("#lf-gloss-tip-1")

    expect(bubble).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").click()
    page.locator(".lf-thread .lf-quote").click()
    expect(bubble).to_be_visible()


def test_a_board_says_which_column_each_card_is_in(browser, serve):
    """Which column a card sits in is the one fact about it that isn't in its own
    text, and columns are three boxes side by side — geometry, which the
    accessibility tree doesn't carry. Flat, this board was six text runs and two
    Move buttons in a row: no boundary between the columns, and no button saying
    where its card was.

    Both halves are asserted from the tree itself rather than from the attributes
    behind it, because that is where they can be wrong: the column heading is CSS
    generated content, so the name reaching the tree once (as the list's) rather
    than twice depends on its alt text. Then a card moves, and the assertion is
    the second snapshot — a name set where the move happens goes stale on
    whichever path forgets to restate its location. The runtime's one quiet origin word
    remains on the card rather than being repeated in the Move control's name."""
    page = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Todo\"': ⠿\n"
        '- list "Done"'  # empty, and still announced: it is a drop target
    )

    # Grab the second card and push it into the next column, the keyboard's path.
    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    page.wait_for_selector("#col-done #card-baffle")
    expect(
        board.get_by_role(
            "button",
            name="Move: Squirrel baffle — Done",
            exact=True,
        )
    ).to_be_visible()
    expect(page.locator("#card-baffle > .lf-quiet")).to_have_text("your change")

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        '- list "Done":\n'
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - text: your change\n"
        "    - 'button \"Move: Squirrel baffle — Done\"': ⠿"
    )


@pytest.mark.parametrize(
    ("axis", "source", "key", "steps"),
    [
        pytest.param("column", SQUEEZED_BOARD_PAGE, "ArrowRight", 4, id="columns"),
        pytest.param("row", TALL_BOARD_PAGE, "ArrowDown", 7, id="rows"),
    ],
)
@pytest.mark.parametrize("reduced_motion", ["no-preference", "reduce"])
def test_a_keyboard_move_keeps_the_card_in_view(
    browser, serve, reduced_motion, axis, source, key, steps
):
    """A move and its Escape return keep the focused card on screen."""
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion=reduced_motion)
    resized(page, 390, 500)
    board = page.locator("#crowd")
    card = page.locator("#sq-card-0")
    grip = card.locator(".lf-grip")

    if axis == "column":
        assert board.evaluate("el => el.scrollWidth > el.clientWidth"), (
            "the board fits, so the keyboard move has no hidden column to reveal"
        )
    else:
        assert page.locator("#sq-card-7").evaluate(
            "el => el.getBoundingClientRect().bottom > innerHeight"
        ), "the lane fits, so the row move has no hidden destination to reveal"

    def wait_for_placement(column, row):
        placement = """([column, row, axis]) => {
          const board = document.querySelector('#crowd');
          const card = board.querySelector('#sq-card-0');
          const cards = [...card.parentElement.querySelectorAll(':scope > lf-card')];
          const outer = board.getBoundingClientRect();
          const inner = card.getBoundingClientRect();
          const visible = axis === 'column'
            ? inner.left >= outer.left - 1 && inner.right <= outer.right + 1
            : inner.top >= -1 && inner.bottom <= innerHeight + 1;
          return card.parentElement.id === `sq-col-${column}`
            && cards.indexOf(card) === row && card.getAnimations().length === 0
            && visible;
        }"""
        where = [column, row, axis]
        page.wait_for_function(placement, arg=where)
        # A move along the columns travels the board's own scrollport; a move down a
        # column travels the document.
        if axis == "column":
            scroll_settled(page, scroller="#crowd", axis="x")
        else:
            scroll_settled(page)
        page.wait_for_function(placement, arg=where)

    grip.focus()
    page.keyboard.press("Enter")
    for step in range(1, steps + 1):
        page.keyboard.press(key)
        # Each key gets its own rendered placement. Otherwise a later press can cancel
        # the prior FLIP before the test has exercised its scroll tracking.
        wait_for_placement(
            step if axis == "column" else 0, step if axis == "row" else 0
        )

    page.keyboard.press("Escape")
    wait_for_placement(0, 0)
    expect(page.locator("#sq-col-0 > #sq-card-0")).to_have_count(1)
    expect(grip).to_be_focused()


def test_tabbing_to_a_grip_reveals_its_whole_card(browser, serve):
    """The browser scrolls a sideways board only far enough to show the focused 30px
    grip, which at a narrow width left the card's words cut off at the board's edge."""
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE))
    resized(page, 390, 500)
    # A restored focus is not an arrival: it leaves the board where the user put it.
    assert page.evaluate(
        """() => {
          const board = document.querySelector('#crowd');
          const before = board.scrollLeft;
          document.querySelector('#sq-card-5 .lf-grip').focus({preventScroll: true});
          return board.scrollLeft === before;
        }"""
    )
    page.locator("#sq-card-0 .lf-grip").focus()
    whole = """() => {
      const card = document.activeElement.closest('lf-card');
      const outer = card.closest('lf-board').getBoundingClientRect();
      const inner = card.getBoundingClientRect();
      return inner.left >= outer.left - 1 && inner.right <= outer.right + 1;
    }"""
    for i in range(1, 4):
        page.keyboard.press("Tab")
        expect(page.locator(f"#sq-card-{i} .lf-grip")).to_be_focused()
        page.wait_for_function(whole)
    # Grabbing it says so with the card's contour, not a shadow the dark paper hides.
    page.keyboard.press("Enter")
    card = page.locator("#sq-card-3")
    expect(card).to_have_class(re.compile(r"\blf-lift\b"))
    accent, border = card.evaluate(
        """el => [getComputedStyle(document.documentElement).getPropertyValue('--accent'),
                  getComputedStyle(el).borderTopColor]"""
    )
    rest = page.locator("#sq-card-2").evaluate(
        "el => getComputedStyle(el).borderTopColor"
    )
    assert border != rest, (border, rest, accent)


def test_cancelling_a_keyboard_move_stops_its_scroll(browser, serve):
    """Escape supersedes a reveal still travelling toward the abandoned placement."""
    page = open_page(browser, serve(TALL_BOARD_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 390, 500)
    card = page.locator("#sq-card-0")
    grip = card.locator(".lf-grip")
    origin = card.evaluate(
        """el => { const box = el.getBoundingClientRect();
                    return {top: box.top + scrollY, bottom: box.bottom + scrollY}; }"""
    )

    grip.focus()
    page.keyboard.press("Enter")
    for _ in range(7):
        page.keyboard.press("ArrowDown")
    expect(page.locator("#sq-col-0 > #sq-card-0")).to_have_count(1)
    assert (
        card.evaluate(
            "el => [...el.parentElement.querySelectorAll(':scope > lf-card')].indexOf(el)"
        )
        == 7
    )
    page.wait_for_function(
        """origin => {
          const top = origin.top - scrollY;
          const bottom = origin.bottom - scrollY;
          return scrollY > 0 && top >= 0 && bottom <= innerHeight;
        }""",
        arg=origin,
    )
    page.keyboard.press("Escape")

    # Read only once the document has held one position. Without cancellation, the
    # abandoned smooth reveal continues past Escape and settles with the restored,
    # focused card above the viewport.
    scroll_settled(page)
    page.wait_for_function(
        "() => document.querySelector('#sq-card-0').getAnimations().length === 0"
    )
    reading = card.evaluate(
        """el => {
          const cards = [...el.parentElement.querySelectorAll(':scope > lf-card')];
          const box = el.getBoundingClientRect();
          return {index: cards.indexOf(el), top: box.top, bottom: box.bottom,
                  viewport: innerHeight};
        }"""
    )
    assert reading["index"] == 0, reading
    assert reading["top"] >= -1 and reading["bottom"] <= reading["viewport"] + 1, (
        reading
    )
    expect(grip).to_be_focused()


def test_a_board_at_its_floor_scrolls_rather_than_breaking_a_card_s_words(
    browser, serve
):
    """A board lays its columns into whatever width it is given and scrolls once they
    are as narrow as they go, which is the right order — but the floor has to know what
    a column costs before it can say where narrow enough stops. Stated as the column's
    own box (10rem), 70 of those 160 pixels were the column's inset and border, the
    card's inset and border, and the column the drag grip hangs in, and the card's prose
    got 90: `documented` is 92px of the page's own serif, so the shipped board broke
    ordinary words across lines the moment the thread strip took its margin.

    The reading is the visible failure and not the number behind it. A word set across
    two lines with no hyphen is what the user sees, and it is what the page-wide
    `overflow-wrap` does with a box narrower than the word it has to show — the bargain
    leaf makes for paths and shas, arriving here on an English sentence. The premise is
    asserted first: the board must be at its floor and scrolling for the rest, or a
    board that simply fitted would pass this while proving nothing."""
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE))
    measured = page.evaluate(
        """() => {
        const board = document.getElementById('crowd');
        const columns = [...board.querySelectorAll('lf-column')];
        // A word broken to fit lands on two lines with no break opportunity in it, so
        // the rects a range over it returns sit at two different tops. Ordinary words
        // only: a path or a sha has nowhere to break and breaking one is the page's
        // own bargain, not this floor's business.
        const range = document.createRange(), broken = [];
        for (const card of board.querySelectorAll('lf-card')) {
            const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
            for (let node = walker.nextNode(); node; node = walker.nextNode())
                for (const m of node.textContent.matchAll(/[^\\s]+/g)) {
                    if (!/^[A-Za-z]+[.,;:]?$/.test(m[0])) continue;
                    range.setStart(node, m.index);
                    range.setEnd(node, m.index + m[0].length);
                    const rects = [...range.getClientRects()];
                    if (new Set(rects.map((r) => Math.round(r.top))).size > 1)
                        broken.push(m[0]);
                }
        }
        return { broken,
                 scrolls: board.scrollWidth - board.clientWidth,
                 widths: columns.map((c) => c.getBoundingClientRect().width),
                 measure: (() => {
                     const card = board.querySelector('lf-card');
                     const s = getComputedStyle(card), b = card.getBoundingClientRect();
                     return b.width - parseFloat(s.paddingLeft)
                          - parseFloat(s.paddingRight) - parseFloat(s.borderLeftWidth)
                          - parseFloat(s.borderRightWidth);
                 })() };
    }"""
    )
    # The premise, read off the layout rather than off the property behind it: a grid of
    # `1fr` tracks that scrolls has every track at its minimum, so a board that scrolls
    # is a board at its floor whatever the floor is written as. A board with room to
    # spare would pass the reading below while asking it nothing.
    assert measured["scrolls"] > 1 and len(set(measured["widths"])) == 1, (
        f"this board is not at its floor, so its words prove nothing: {measured}"
    )
    assert measured["broken"] == [], (
        f"a board at its floor gave each card {measured['measure']:.0f}px of measure "
        f"and broke {', '.join(sorted(set(measured['broken'])))} across two lines"
    )


GRIPPED_CARD_PAGE = leaf_page(
    "Gripped card",
    """
<h1 id="t">Release triage</h1>
<lf-board id="gripped">
  <lf-column id="col-a" label="Fix in 2.4.1">
    <lf-card id="card-a"><strong>Webhook retries ignore the Retry-After header</strong>
      Three partners rate limit us during their own deploys, and we back off on a fixed
      schedule that ignores what they asked for.</lf-card>
  </lf-column>
  <lf-column id="col-b" label="Defer"></lf-column>
  <lf-column id="col-c" label="Repro"></lf-column>
</lf-board>
""",
    # Justified, so each full line ends where the card lets it rather than at a word.
    head="<style>#card-a { text-align: justify; }</style>",
)


def test_only_a_card_s_title_clears_its_grip(browser, serve):
    """The grip stands at the card's top corner and the lines beside it, the title's,
    stop short of it; the prose below runs the card's whole width, where it used to be
    set in a column that kept clear of the grip down the card's full height. No line
    stands under the grip's box, so a press there is always the grip's."""
    page = open_page(browser, serve(GRIPPED_CARD_PAGE))
    measured = page.locator("#card-a").evaluate(
        """(card) => {
        const grip = card.querySelector(':scope > .lf-grip').getBoundingClientRect();
        const range = document.createRange(), lines = [];
        const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (node.parentElement.closest('.lf-grip') || !node.textContent.trim()) continue;
            range.selectNodeContents(node);
            for (const r of range.getClientRects())
                lines.push({title: node.parentElement.localName === 'strong',
                            top: r.top, bottom: r.bottom, right: r.right});
        }
        const beside = (l) => l.top < grip.bottom && l.bottom > grip.top;
        return {
            under: lines.filter((l) => beside(l) && l.right > grip.left).length,
            titleBeside: lines.some((l) => l.title && beside(l)),
            // Past the grip's left edge is the room the column held back.
            prose: lines.filter((l) => !l.title && !beside(l)).slice(0, -1)
                .map((l) => Math.round(l.right - grip.left)),
        };
    }"""
    )
    assert measured["titleBeside"], measured
    assert measured["under"] == 0, measured
    # Every full line of prose below the grip runs into the room beneath it.
    assert measured["prose"] and all(d > 0 for d in measured["prose"]), measured


GRIPPED_BLOCK_CARD_PAGE = leaf_page(
    "Gripped block card",
    """
<h1 id="t">Release triage</h1>
<lf-board id="gripped">
  <lf-column id="col-a" label="Fix in 2.4.1">
    <lf-card id="card-a"><strong>Retries ignore Retry-After</strong>
      <pre id="card-a-code">retry(after=fixed(30))</pre>
      <p id="card-a-note">Three partners rate limit us during their own deploys.</p>
    </lf-card>
  </lf-column>
</lf-board>
""",
)


def test_a_finger_s_taller_grip_leaves_the_blocks_under_a_title_their_width(
    browser, serve
):
    """Under a finger the grip is the aim floor tall, so it reaches past a one-line
    title. A block after the title that lays itself out on its own (a pre) was set
    beside the grip's room for its whole height, 30px narrower than the card; a block
    after the title now clears the grip and takes the card's width, and nothing stands
    under the grip's box."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(GRIPPED_BLOCK_CARD_PAGE), context=context)
    measured = page.locator("#card-a").evaluate(
        """(card) => {
        const grip = card.querySelector(':scope > .lf-grip').getBoundingClientRect();
        const s = getComputedStyle(card), box = card.getBoundingClientRect();
        const content = box.width - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)
            - parseFloat(s.borderLeftWidth) - parseFloat(s.borderRightWidth);
        const title = card.querySelector('strong').getBoundingClientRect();
        const blocks = ['#card-a-code', '#card-a-note'].map((id) =>
            card.querySelector(id).getBoundingClientRect());
        const under = (b) => b.top < grip.bottom && b.bottom > grip.top
            && b.right > grip.left;
        return {grip: Math.round(grip.height), title: Math.round(title.height),
                widths: blocks.map((b) => Math.round(content - b.width)),
                under: blocks.filter(under).length};
    }"""
    )
    # The premise: the grip reaches past the title's one line.
    assert measured["grip"] == 44 and measured["title"] < 30, measured
    assert measured["widths"] == [0, 0], measured
    assert measured["under"] == 0, measured


def test_a_phone_board_gives_its_column_room_and_keeps_the_next_one_discoverable(
    browser, serve
):
    """A phone shows one readable column and moves a card without a distant drop target.

    The desktop grid divided its wide target across every column even after the board
    itself had narrowed to the page. On a phone that left most of a second column on
    screen and squeezed the first into a narrow card. Wide columns then put the next
    pointer drop target off screen, so the phone offers every other column on the card.
    """
    context = browser.new_context(
        viewport={"width": 390, "height": 900}, has_touch=True
    )
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE), context=context)
    measured = page.locator("#crowd").evaluate(
        """board => {
        const box = board.getBoundingClientRect();
        const columns = [...board.querySelectorAll(':scope > lf-column')]
          .slice(0, 2).map(column => column.getBoundingClientRect());
        return {board: box, columns,
                scrolls: board.scrollWidth > board.clientWidth};
    }"""
    )
    board = measured["board"]
    first, second = measured["columns"]
    assert first["width"] > board["width"] * 0.85, measured
    assert first["right"] <= board["right"] + 1, measured
    assert first["right"] < second["left"] < board["right"], measured
    assert measured["scrolls"], measured

    card = page.locator("#sq-card-0")
    expect(card.locator(".lf-grip")).to_be_visible()
    to_lane_1 = card.get_by_role("button", name="Move Perch 0 to Lane 1")
    expect(to_lane_1).to_be_visible()
    with sending(page, "the phone category move"):
        to_lane_1.tap()
    expect(page.locator("#sq-col-1 > #sq-card-0")).to_have_count(1)
    expect(card.locator(".lf-grip")).to_be_focused()
    # The card passes through the visible area while its move is still animating.
    page.wait_for_function(
        """() => {
          const moved = document.querySelector('#sq-card-0');
          if (moved.getAnimations().length) return false;
          const board = document.querySelector('#crowd').getBoundingClientRect();
          const card = moved.getBoundingClientRect();
          return card.left >= board.left - 1 && card.right <= board.right + 1;
        }"""
    )
    moved = card.bounding_box()
    board = page.locator("#crowd").bounding_box()
    assert moved and board
    assert board["x"] <= moved["x"] and moved["x"] + moved["width"] <= (
        board["x"] + board["width"] + 1
    )

    to_lane_0 = card.get_by_role("button", name="Move Perch 0 to Lane 0")
    expect(to_lane_0).to_be_visible()
    with sending(page, "the phone return move"):
        to_lane_0.tap()
    expect(page.locator("#sq-col-0 > #sq-card-0")).to_have_count(1)


@pytest.mark.parametrize(
    "typed_color, close_editor",
    [("#8b4a5f", "escape"), ("#8B4A5F", "escape"), ("#8b4a5f", "outside-press")],
)
def test_a_playground_keeps_one_typed_working_state_until_the_user_chooses(
    browser, serve, typed_color, close_editor
):
    page = open_page(browser, serve(PLAYGROUND_PAGE))
    playground = page.locator("#card-playground")
    before = len(events_model.read_events(serve.page_dir))
    changes = playground.evaluate(
        """root => {
          window.playgroundChanges = [];
          root.addEventListener('lf-playground-change', event =>
            window.playgroundChanges.push(event.detail.values));
          return root.values;
        }"""
    )
    assert changes == {
        "accent": "#4f766f",
        "compact": False,
        "radius": 12,
        "title": "Field note",
        "tone": "quiet",
    }

    radius = playground.get_by_role("slider", name="Corner radius")
    for _ in range(5):
        radius.press("ArrowRight")
    playground.get_by_role("switch", name="Compact spacing").press("Space")
    playground.get_by_role("radio", name="Quiet", exact=True).press("ArrowRight")
    picker = playground.locator("wa-color-picker")
    picker.get_by_role("button", name="Accent", exact=True).click()
    color_field = picker.get_by_role("textbox")
    color_field.fill(typed_color)
    color_field.press("Enter")
    if close_editor == "escape":
        color_field.press("Escape")
    else:
        page.locator('lf-playground-control[name="title"] input').click()
    page.locator('lf-playground-control[name="title"] input').fill("Ridge note; alert")

    assert len(events_model.read_events(serve.page_dir)) == before
    assert playground.evaluate("root => root.values") == {
        "accent": "#8b4a5f",
        "compact": True,
        "radius": 17,
        "title": "Ridge note; alert",
        "tone": "bold",
    }
    assert playground.evaluate("root => window.playgroundChanges.at(-1)")["title"] == (
        "Ridge note; alert"
    )
    expect(page.locator("#playground-card")).to_have_css("border-radius", "17px")
    expect(page.locator("#playground-card")).to_have_css("padding", "8px")
    assert (
        page.locator("#playground-card").evaluate(
            "element => getComputedStyle(element, '::before').content"
        )
        == '"Ridge note; alert"'
    )
    expect(page.locator("#card-instruction")).to_have_text(
        "Use a 17px radius, compact spacing set to true, a bold tone, #8b4a5f accents, "
        "and the title Ridge note; alert."
    )
    expect(page.locator("#card-instruction")).to_have_css(
        "font-family", 'system-ui, -apple-system, "Segoe UI", sans-serif'
    )
    expect(page.locator("#card-instruction")).to_have_css("font-size", "14px")

    with sending(page, "the playground configuration"):
        playground.get_by_role("button", name="Use these settings").click()
    action = events_model.read_events(serve.page_dir)[-1]
    assert action["action"] == "choose"
    assert action["detail"] == {
        "values": {
            "accent": "#8b4a5f",
            "compact": True,
            "radius": 17,
            "title": "Ridge note; alert",
            "tone": "bold",
        },
        "instruction": (
            "Use a 17px radius, compact spacing set to true, a bold tone, #8b4a5f accents, "
            "and the title Ridge note; alert."
        ),
    }

    page.reload()
    expect(page.locator("#card-instruction")).to_contain_text("17px radius")
    assert playground.evaluate("root => root.values")["title"] == "Ridge note; alert"
    undo(page)
    expect(page.locator("#card-instruction")).to_contain_text("12px radius")
    assert playground.evaluate("root => root.values")["compact"] is False


def test_notification_playground_sets_regions_side_by_side_while_its_workspace_is_full_height(
    browser, serve
):
    """A playground is a workspace with its relationship declared: the preview is the
    stage, with the controls and the instruction they write in a rail beside it. While
    the root workspace fills the window each region scrolls on its own, the controls
    under their fixed presets and the instruction above its fixed actions; where it
    doesn't, the page scrolls, and a narrow one stacks the regions. Either way each is a
    named reading region."""
    source = Path(__file__).parents[1] / "examples" / "notification-playground.html"
    page = open_page(browser, serve(source))
    playground = page.locator("#notification-playground")
    controls = playground.locator(".lf-playground-controls")
    preview = playground.locator(".lf-playground-preview-body")
    presets = playground.get_by_role("group", name="Starting points")
    actions = playground.locator(".lf-playground-actions")
    reading = """async () => {
      const leaf = await window.__lfRuntimeImport('/runtime/widget-api.js');
      const playground = document.querySelector('#notification-playground');
      const controls = playground.querySelector('.lf-playground-controls');
      const preview = playground.querySelector('.lf-playground-preview-body');
      const instruction = playground.querySelector('lf-playground-output');
      const region = (body) => leaf.readingRegionFor(body);
      const controlsBox = region(controls).host.getBoundingClientRect();
      const previewBox = region(preview).host.getBoundingClientRect();
      const instructionBox = region(instruction).host.getBoundingClientRect();
      return {
        controlsId: region(controls).id,
        previewId: region(preview).id,
        instructionId: region(instruction).id,
        postures: [controls, preview, instruction].map((body) =>
          leaf.readingPosture(region(body))),
        scrollers: [controls, preview, instruction].map((body) =>
          leaf.effectiveScroller(body) === body ? 'own' :
          leaf.effectiveScroller(body) === document.scrollingElement ? 'page' : 'other'),
        sideBySide: Math.abs(previewBox.top - controlsBox.top) < 1
          && controlsBox.left >= previewBox.right
          && Math.abs(instructionBox.left - controlsBox.left) < 1
          && instructionBox.top >= controlsBox.bottom,
        stacked: controlsBox.top >= previewBox.bottom - 1,
        presetsHeadControls: controls.previousElementSibling
          === playground.querySelector('.lf-playground-presets'),
        controlsSize: [controls.clientHeight, controls.scrollHeight],
        pageScrolls: document.scrollingElement.scrollHeight > innerHeight,
        askDisplay: getComputedStyle(document.querySelector('#notification-ask')).display,
        authoredWords: leaf.wrote(playground).includes('Drag event pressure'),
        spokenWords: leaf.says(playground).includes('Drag event pressure'),
      };
    }"""

    resized(page, 1100, 700)
    expect(actions).to_be_visible()
    bounded = page.evaluate(reading)
    assert bounded == {
        **bounded,
        "controlsId": "lf-region:notification-playground:controls",
        "previewId": "lf-region:notification-playground:preview",
        "instructionId": "lf-region:notification-playground:instruction",
        "postures": ["bounded", "bounded", "bounded"],
        "scrollers": ["own", "own", "own"],
        "sideBySide": True,
        "presetsHeadControls": True,
        "pageScrolls": False,
        "askDisplay": "flex",
        "authoredWords": True,
        "spokenWords": True,
    }
    assert bounded["controlsSize"][1] > bounded["controlsSize"][0], bounded
    # The rail's two titles are one voice: the package draws its generated panes, and
    # the kernel's default pane header must not outrank the class that says so.
    voice = """node => {
      const style = getComputedStyle(node);
      return [style.fontFamily, style.fontSize, style.fontWeight];
    }"""
    assert playground.locator(".lf-playground-instruction-title").evaluate(
        voice
    ) == playground.locator(".lf-playground-presets-title").evaluate(voice)
    # The presets band heading the controls is ruled off from them, over the generic
    # region header's unruled box.
    assert playground.locator(".lf-playground-presets").evaluate(
        """node => {
          const style = getComputedStyle(node);
          return [style.borderBottomStyle, style.paddingBottom];
        }"""
    ) == ["solid", "14px"]
    first_control = playground.locator("lf-playground-control").first
    control_box = first_control.bounding_box()
    controls_box = controls.bounding_box()
    assert control_box["y"] >= controls_box["y"] and (
        control_box["y"] + control_box["height"]
        <= controls_box["y"] + controls_box["height"]
    ), f"the fixed presets left no complete control row: {bounded['controlsSize']}"
    assert controls.evaluate("body => body.scrollWidth === body.clientWidth"), (
        "native control margins must fit inside the allocated pane width"
    )
    presets_top = presets.bounding_box()["y"]
    controls.evaluate("body => body.scrollTop = body.scrollHeight")
    assert controls.evaluate("body => body.scrollTop") > 0
    expect(presets).to_be_visible()
    assert presets.bounding_box()["y"] == pytest.approx(presets_top, abs=1)
    expect(playground.get_by_role("button", name="Routine release")).to_be_visible()
    expect(playground.get_by_role("button", name="Needs attention")).to_be_visible()
    pressure = playground.get_by_role("slider", name="Concurrent release events")
    expect(pressure).to_have_attribute("aria-valuenow", "2")
    expect(page.locator(".notification-demo-card-banner")).to_have_count(2)
    expect(page.locator(".notification-demo-card-status-strip")).to_have_count(2)
    expect(page.locator(".notification-demo-strip-owner")).to_have_count(2)
    assert playground.evaluate(
        """owner => {
          const parent = owner.parentNode;
          const next = owner.nextSibling;
          const nodes = [...owner.querySelectorAll('*')];
          const values = JSON.stringify(owner.values);
          owner.remove();
          parent.insertBefore(owner, next);
          return values === JSON.stringify(owner.values)
            && nodes.every((node, index) => owner.querySelectorAll('*')[index] === node);
        }"""
    )
    reattached = page.evaluate(reading)
    assert (reattached["controlsId"], reattached["previewId"]) == (
        "lf-region:notification-playground:controls",
        "lf-region:notification-playground:preview",
    )
    regular_strip_padding = page.locator(
        ".notification-demo-card-status-strip"
    ).first.evaluate("card => getComputedStyle(card).paddingTop")
    pressure.press("ArrowRight")
    pressure.press("ArrowRight")
    expect(page.locator(".notification-demo-card-banner")).to_have_count(4)
    expect(page.locator(".notification-demo-card-status-strip")).to_have_count(4)
    expect(page.locator(".notification-demo-candidate").first).to_contain_text(
        "4 cards · full detail"
    )
    expect(page.locator(".notification-demo-candidate").last).to_contain_text(
        "4 rows · compact summary"
    )
    playground.get_by_role("button", name="Needs attention").click()
    expect(pressure).to_have_attribute("aria-valuenow", "4")
    expect(page.locator("#notification-simulator")).to_have_attribute(
        "data-compact", "true"
    )
    compact_strip_padding = page.locator(
        ".notification-demo-card-status-strip"
    ).first.evaluate("card => getComputedStyle(card).paddingTop")
    assert float(compact_strip_padding.removesuffix("px")) < float(
        regular_strip_padding.removesuffix("px")
    )
    playground.get_by_role("button", name="Routine release").click()
    expect(pressure).to_have_attribute("aria-valuenow", "2")
    assert preview.evaluate("body => body.scrollTop") == 0
    action_box = actions.bounding_box()
    playground_box = playground.bounding_box()
    shortcut_box = page.locator("#lf-shortcut-bar").bounding_box()
    assert (
        action_box["y"] + action_box["height"]
        <= playground_box["y"] + playground_box["height"] + 1
    )
    assert action_box["y"] + action_box["height"] <= shortcut_box["y"] + 1

    # Beside Threads, the notification wraps beyond the preview's minimum height.
    # The preview must grow around its content rather than clip it.
    resized(page, 1280, 720)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.evaluate(reading)["postures"] == ["bounded", "bounded", "bounded"]
    notification_box = page.locator(
        ".notification-demo-card-banner"
    ).first.bounding_box()
    preview_box = page.locator("#notification-preview").bounding_box()
    assert notification_box["y"] + notification_box["height"] <= (
        preview_box["y"] + preview_box["height"]
    )
    page.locator(".lf-threads-toggle").click()

    for width, height in [(1100, 300), (700, 500), (500, 900)]:
        resized(page, width, height)
        flow = page.evaluate(reading)
        assert flow == {
            **flow,
            "postures": ["flow", "flow", "flow"],
            "scrollers": ["page", "page", "page"],
            "pageScrolls": True,
            "askDisplay": "block",
        }, (width, height)
        # Too short to hold the regions is not too narrow to set them side by side.
        assert flow["stacked"] is (width < 1100), (width, height, flow)


def test_composed_corpus_runs_authored_page_modules(browser, serve):
    corpus = Path(__file__).parent.parent / "examples" / "corpus.html"
    page = open_page(browser, serve(corpus))
    page.get_by_role("tab", name="Notification", exact=True).click()

    expect(
        page.locator("#notification-playground").get_by_role(
            "slider", name="Concurrent release events"
        )
    ).to_have_attribute("aria-valuenow", "2")
    expect(page.locator(".notification-demo-card-banner")).to_have_count(2)
    expect(page.locator(".notification-demo-card-status-strip")).to_have_count(2)


def test_notification_playground_admits_only_its_exact_page_configuration(
    browser, serve
):
    source = Path(__file__).parents[1] / "examples" / "notification-playground.html"
    url = serve(source)
    page = open_page(browser, url)
    playground = page.locator("#notification-playground")
    values = playground.evaluate("root => root.values")
    assert set(values) == {
        "accent",
        "compact",
        "events",
        "format",
        "radius",
        "show-owner",
        "title",
        "tone",
    }

    refused = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": 1,
            "widget": "notification-playground",
            "action": "choose",
            "detail": {
                "values": {**values, "unknown": "not part of this page"},
                "instruction": "Build the notification.",
            },
        },
    )
    assert refused.status == 400
    assert "unknown" in refused.json()["error"]
    off_step = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": 1,
            "widget": "notification-playground",
            "action": "choose",
            "detail": {
                "values": {**values, "events": 2.5},
                "instruction": "Build the notification.",
            },
        },
    )
    assert off_step.status == 400
    assert "2.5" in off_step.json()["error"]
    assert actions(serve.page_dir) == []


def test_structured_data_explorer_keeps_one_aggregate_query_configuration(
    browser, serve
):
    source = Path(__file__).parents[1] / "examples" / "data-explorer.html"
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, serve(source), context=context)
    playground = page.locator("#release-query-playground")
    rows = page.locator(".query-row")

    expect(rows).to_have_count(2)
    assert playground.evaluate("root => root.values") == {
        "filters": {
            "order": ["filter-1", "filter-2"],
            "rows": [
                {
                    "field": "region",
                    "id": "filter-1",
                    "operator": "is",
                    "value": "europe",
                },
                {
                    "field": "risk",
                    "id": "filter-2",
                    "operator": "above",
                    "value": "40",
                },
            ],
        },
        "limit": 4,
    }
    assert (
        playground.evaluate(
            """root => {
          const returned = root.values;
          returned.filters.rows[0].value = 'tampered';
          return root.values.filters.rows[0].value;
        }"""
        )
        == "europe"
    )
    assert playground.evaluate(
        """root => {
          const errors = [];
          for (const [name, value] of [
            ['limit', {}],
            ['filters', {}],
            ['bad-date', new Date()],
          ]) {
            try {
              root.registerContributor(name, value, {read: () => value, apply: () => {}});
            } catch (error) {
              errors.push(error.message);
            }
          }
          try {
            root.registerInstructionProvider(() => 'A second provider');
          } catch (error) {
            errors.push(error.message);
          }
          return errors;
        }"""
    ) == [
        "contributor limit collides with a control",
        "repeats contributor filters",
        "contributor bad-date must be JSON-safe",
        "playground already has an instruction provider",
    ]
    expect(page.locator(".query-result-count")).to_have_text("2 matching releases")

    rows.nth(1).get_by_label("Value").fill("80")
    expect(page.locator(".query-result-count")).to_have_text("1 matching release")
    rows.nth(1).get_by_role("button", name="Move filter 2 up").click()
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-2",
        "filter-1",
    ]
    page.get_by_role("button", name="Add filter").click()
    expect(rows).to_have_count(3)
    expect(rows.nth(2).get_by_label("Value")).to_be_focused()
    rows.nth(2).get_by_label("Value").fill("risk")
    expect(page.locator(".query-result-count")).to_have_text("1 matching release")
    rows.nth(2).get_by_role("button", name="Remove filter 3").click()
    expect(rows).to_have_count(2)

    playground.get_by_role("button", name="Broad query").click()
    expect(
        playground.locator('lf-playground-control[name="limit"]').get_by_role("slider")
    ).to_have_attribute("aria-valuenow", "6")
    playground.get_by_role("button", name="Focused query").click()
    expect(
        playground.locator('lf-playground-control[name="limit"]').get_by_role("slider")
    ).to_have_attribute("aria-valuenow", "4")
    instruction = page.locator("#release-query-instruction")
    expect(instruction).to_contain_text("risk above 80, then region is europe")
    playground.get_by_role("button", name="Copy instruction").click()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == instruction.inner_text()

    page.reload()
    expect(rows).to_have_count(2)
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-2",
        "filter-1",
    ]
    expect(instruction).to_contain_text("risk above 80, then region is europe")
    playground.get_by_role("button", name="Reset").click()
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-1",
        "filter-2",
    ]
    expect(instruction).to_contain_text("region is europe, then risk above 40")
    rows.nth(1).get_by_role("button", name="Remove filter 2").click()
    rows.first.get_by_role("button", name="Remove filter 1").click()
    expect(rows).to_have_count(0)
    expect(instruction).to_contain_text("Apply no filters")
    expect(page.locator(".query-result-count")).to_have_text("4 matching releases")
    playground.get_by_role("button", name="Broad query").click()
    expect(page.locator(".query-result-count")).to_have_text("6 matching releases")
    playground.get_by_role("button", name="Focused query").click()
    expect(page.locator(".query-result-count")).to_have_text("4 matching releases")
    playground.get_by_role("button", name="Reset").click()
    rows.first.get_by_label("Value").fill("asia")
    expect(instruction).to_contain_text("region is asia, then risk above 40")

    with sending(page, "the release query"):
        playground.get_by_role("button", name="Build query").click()
    action = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "release-query-playground"
    )
    assert action["detail"] == {
        "instruction": instruction.inner_text(),
        "values": playground.evaluate("root => root.values"),
    }
    page.reload()
    expect(rows.first.get_by_label("Value")).to_have_value("asia")
    expect(instruction).to_contain_text("region is asia, then risk above 40")
    undo(page)
    expect(rows.first.get_by_label("Value")).to_have_value("europe")
    expect(instruction).to_contain_text("region is europe, then risk above 40")
    resized(page, 480, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 480
    resized(page, 1100, 320)
    expect(page.locator("#release-query-ask")).to_be_visible()


def test_built_code_comparison_drives_both_candidates_and_composes_targeting(
    browser, serve
):
    source = Path(__file__).parents[1] / "examples" / "code-comparison.html"
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, serve(source), context=context)
    playground = page.locator("#code-comparison-playground")
    candidate_a = page.locator('[data-candidate="A"]')
    candidate_b = page.locator('[data-candidate="B"]')

    expect(page.locator("lf-code.lf-rendered")).to_have_count(3)
    assert playground.evaluate("root => root.values") == {
        "chosen": "A",
        "comparison": {
            "candidateA": {"density": "compact", "wrap": False},
            "candidateB": {"density": "comfortable", "wrap": True},
        },
        "width": 420,
    }
    expect(candidate_a).to_have_attribute("style", re.compile(r"width: 420px"))
    expect(candidate_b).to_have_attribute("style", re.compile(r"width: 420px"))
    before_a = candidate_a.locator(".code-measurement").inner_text()
    before_b = candidate_b.locator(".code-measurement").inner_text()
    assert before_a != before_b

    width = playground.locator('lf-playground-control[name="width"]').get_by_role(
        "slider"
    )
    for _ in range(5):
        width.press("ArrowLeft")
    expect(candidate_a).to_have_attribute("style", re.compile(r"width: 320px"))
    expect(candidate_b).to_have_attribute("style", re.compile(r"width: 320px"))
    assert playground.evaluate("root => root.values.width") == 320

    page.get_by_role("button", name="Toggle A density").click()
    assert playground.evaluate("root => root.values.comparison") == {
        "candidateA": {"density": "comfortable", "wrap": False},
        "candidateB": {"density": "comfortable", "wrap": True},
    }
    page.get_by_role("button", name="Toggle B density").click()
    assert playground.evaluate("root => root.values.comparison.candidateB.density") == (
        "compact"
    )
    page.get_by_role("button", name="Copy A to B").click()
    assert playground.evaluate("root => root.values.comparison") == {
        "candidateA": {"density": "comfortable", "wrap": False},
        "candidateB": {"density": "comfortable", "wrap": False},
    }
    expect(candidate_a.locator(".code-candidate-title")).to_have_text(
        "A · comfortable · scroll"
    )
    expect(candidate_b.locator(".code-candidate-title")).to_have_text(
        "B · comfortable · scroll"
    )
    assert playground.evaluate("root => root.values.comparison.candidateA") == {
        "density": "comfortable",
        "wrap": False,
    }
    page.get_by_role("button", name="Toggle B density").click()
    page.get_by_role("button", name="Copy B to A").click()
    assert playground.evaluate("root => root.values.comparison") == {
        "candidateA": {"density": "compact", "wrap": False},
        "candidateB": {"density": "compact", "wrap": False},
    }

    playground.get_by_role("button", name="Wrapped reader").click()
    expect(
        playground.locator('lf-playground-control[name="width"]').get_by_role("slider")
    ).to_have_attribute("aria-valuenow", "320")
    expect(
        playground.locator('lf-playground-choice[value="B"] wa-radio')
    ).to_be_checked()
    playground.get_by_role("button", name="Compact reader").click()
    expect(
        playground.locator('lf-playground-control[name="width"]').get_by_role("slider")
    ).to_have_attribute("aria-valuenow", "420")
    playground.get_by_role("button", name="Reset").click()
    assert playground.evaluate("root => root.values.comparison") == {
        "candidateA": {"density": "compact", "wrap": False},
        "candidateB": {"density": "comfortable", "wrap": True},
    }

    playground.locator('lf-playground-choice[value="B"] wa-radio').click()
    instruction = page.locator("#code-comparison-instruction")
    expect(instruction).to_contain_text("comfortable reading density")
    expect(instruction).to_contain_text("wrap long lines")
    playground.get_by_role("button", name="Copy instruction").click()
    assert page.evaluate("navigator.clipboard.readText()") == instruction.inner_text()
    with sending(page, "the code reader treatment"):
        playground.get_by_role("button", name="Apply treatment").click()
    action = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "code-comparison-playground"
    )
    assert action["detail"] == {
        "instruction": instruction.inner_text(),
        "values": playground.evaluate("root => root.values"),
    }

    targeting = page.locator("#code-comparison-targeting")
    targeting.get_by_role("button", name="Select element").click()
    page.locator(".reader-treatment-title").focus()
    page.keyboard.press("Enter")
    targeting.locator(".lf-targeting-candidate-choice").first.click()
    target = targeting.locator('.lf-targeting-target[data-target-key="target-1"]')
    target.locator("wa-input").click()
    target.locator("wa-input").press("ControlOrMeta+A")
    target.locator("wa-input").press_sequentially("Reader treatment heading")
    target.locator("wa-input").press("Tab")
    assert targeting.evaluate("root => root.currentDraft().resolutions") == {
        "target-1": "resolved"
    }

    resized(page, 480, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 480
    expect(page.locator(".code-comparison-grid")).to_have_css(
        "grid-template-columns", re.compile(r"\d+(?:\.\d+)?px")
    )
    resized(page, 1100, 320)
    expect(page.locator("#code-comparison-ask")).to_be_visible()


def test_playground_composed_structural_target_resolves_in_the_next_revision(
    browser, serve
):
    source_path = Path(__file__).parents[1] / "examples" / "code-comparison.html"
    source = source_path.read_text(encoding="utf-8")
    page = open_page(browser, live_url(serve(source_path)))
    targeting = page.locator("#code-comparison-targeting")

    targeting.get_by_role("button", name="Select element").click()
    page.locator(".reader-treatment-title").focus()
    page.keyboard.press("Enter")
    targeting.locator(".lf-targeting-candidate-choice").first.click()
    target = targeting.locator('.lf-targeting-target[data-target-key="target-1"]')
    target.locator("wa-input").click()
    target.locator("wa-input").press("ControlOrMeta+A")
    target.locator("wa-input").press_sequentially("Reader treatment heading")
    target.locator("wa-input").press("Tab")
    targeting.locator('[name="code-comparison-targeting-instruction"] textarea').fill(
        "Keep this heading aligned with the selected reader treatment."
    )
    targeting.get_by_role("button", name="Add instruction").click()
    with sending(page, "the structural reader target"):
        targeting.get_by_role("button", name="Propose exact edit").click()

    action = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "code-comparison-targeting"
    )
    assert action["detail"]["targets"][0]["reference"] == {
        "anchor": "target-reader-artifact",
        "kind": "structure",
        "path": [{"tag": "h3", "tree": "light"}],
    }

    revised = source.replace(
        "One width gesture\n        reaches both",
        "One shared width gesture\n        reaches both",
    )
    assert revised != source
    stamp = stamp_page(serve.page_dir, revised, "Clarify the comparison gesture")
    wait_for_revision(page, stamp["revision"])
    target = page.locator(
        '#code-comparison-targeting .lf-targeting-target[data-target-key="target-1"]'
    )
    expect(target).to_have_attribute("data-lf-target-status", "resolved")
    expect(page.locator(".reader-treatment-title")).to_have_text(
        "Built reader treatment"
    )


def test_notification_configuration_becomes_a_commentable_local_artifact(
    browser, serve
):
    """The example's instruction is a complete task through Leaf's existing loop.

    A playground action enters the ordinary event log, pickup and a work claim use the
    same delivery projection as an agent in a harness, and the agent writes a real local file.
    The page exposes that file through data, then a user comment changes the file and
    remains anchored on the revised result.
    """
    source_path = (
        Path(__file__).parents[1] / "examples" / "notification-playground.html"
    )
    source = source_path.read_text(encoding="utf-8")
    page = open_page(browser, live_url(serve(source_path)))
    playground = page.locator("#notification-playground")

    playground.get_by_role("button", name="Needs attention").click()
    page.locator('lf-playground-control[name="title"] input').fill(
        "Checkout needs attention"
    )
    expect(playground).to_have_attribute("data-playground-tone", "urgent")
    expect(playground).to_have_attribute("data-playground-compact", "true")
    expect(playground).to_have_attribute("data-playground-format", "status strip")
    expect(
        page.locator(".notification-demo-card-banner").first
    ).to_have_accessible_name("Checkout needs attention")
    expect(
        page.locator(".notification-demo-card-status-strip").first
    ).to_have_accessible_name("Checkout needs attention")
    with sending(page, "the notification configuration"):
        playground.get_by_role("button", name="Create notification").click()
    # The user can revise the configuration until the host stamps its result.
    expect(playground.get_by_role("button", name="Create notification")).to_be_enabled()
    action = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "notification-playground"
    )
    assert action["detail"]["values"] == {
        "accent": "#b6533c",
        "compact": True,
        "events": 4,
        "format": "status strip",
        "radius": 10,
        "show-owner": True,
        "title": "Checkout needs attention",
        "tone": "urgent",
    }
    assert action["detail"]["instruction"] == (
        "Build the status strip deployment notification as deployment-notification.html. "
        "Use urgent styling, 10px corners, #b6533c accents, compact spacing set to true, "
        "owner visibility set to true, and title it Checkout needs attention. Exercise 4 "
        "concurrent release events in its browser test, then show me the generated source "
        "here for review."
    )

    logged_action = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["id"] == action["id"]
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(
            transaction,
            [logged_action],
            session="notification-agent",
            turn="create-artifact",
        )
    with (
        service_model.PageTransaction(serve.page_dir) as receipt_page,
        delivery_model.receive_batch(
            receipt_page,
            {"events": [{"seq": logged_action["seq"], "id": logged_action["id"]}]},
            session_id=None,
        ),
    ):
        pass
    started = _start(
        serve.page_dir, logged_action["id"], "creating deployment-notification.html"
    )
    assert started.exit_code == 0, started.output
    told(page)
    expect(
        page.locator('[data-lf-margin-for="notification-playground"] .lf-margin-marker')
    ).to_have_attribute(
        "aria-description", re.compile("creating deployment-notification")
    )

    artifact = serve.page_dir / "deployment-notification.html"
    first_artifact = """<!doctype html>
<html lang="en">
<title>Checkout needs attention</title>
<style>
body { font-family: system-ui, sans-serif; }
.notification { border-top: 5px solid #b6533c; border-radius: 10px; padding: 8px 12px; }
</style>
<article class="notification">
  <h1>Checkout needs attention</h1>
  <p>Version 2.8.0 changed the checkout service. Review the deployment run and current service health.</p>
  <p><strong>Owner:</strong> Payments platform</p>
</article>
</html>
"""
    artifact.write_text(first_artifact, encoding="utf-8")
    # The result is a document: the configuration folds away above the artifact, so
    # the page leaves the workspace Layout. Select the authored identities rather
    # than copying their class lists and source whitespace into this revision writer.
    result = turbohtml.parse(source)
    for control in result.select("#notification-playground lf-playground-control"):
        value = action["detail"]["values"][control.attrs["name"]]
        control.attrs["value"] = (
            str(value).lower() if isinstance(value, bool) else str(value)
        )
    workspace = result.select_one("#notification-workspace")
    workspace.attrs["class"] = "layout-column"
    artifact_section = result.select_one("#notification-artifact")
    configuration = turbohtml.E(
        "details",
        {"id": "notification-configuration", "open": ""},
        turbohtml.E("summary", "Original configuration"),
    )
    result.select_one("#notification-ask").wrap(configuration)
    configuration.insert_before(turbohtml.E("h1", "Review the deployment notification"))
    artifact_section.attrs.pop("hidden")
    artifact_section.select_one("#notification-artifact-source").attrs["label"] = (
        "deployment-notification.html"
    )
    workspace.append(artifact_section)
    result_source = result.serialize()
    assert "notification-configuration" in result_source
    assert "layout-workspace" not in result_source
    assert 'notification-artifact" hidden' not in result_source
    data_model.cmd_data_set(
        serve.page_dir,
        "notification-artifact",
        artifact.read_text(encoding="utf-8"),
    )
    first_result = stamp_page(
        serve.page_dir,
        result_source,
        "Created deployment-notification.html",
    )
    wait_for_revision(page, first_result["revision"])

    source_widget = page.locator("#notification-artifact-source")
    expect(source_widget).to_be_visible()
    assert source_widget.evaluate(
        "source => source.closest('lf-playground-preview') === null"
    )
    expect(source_widget.locator("code")).to_contain_text(
        "<title>Checkout needs attention</title>"
    )
    expect(
        page.locator('[data-lf-margin-for="notification-playground"]')
    ).to_have_count(0)

    configuration = page.locator("#notification-configuration")
    expect(configuration).to_have_attribute("open", "")
    expect(
        configuration.locator('lf-playground-control[name="title"] input')
    ).to_have_value("Checkout needs attention")
    configuration.locator(":scope > summary").click()
    expect(configuration).not_to_have_attribute("open", "")
    configuration.locator(":scope > summary").click()
    receipt_copy = page.locator(
        ".notification-demo-card-banner .notification-demo-detail"
    ).first
    expect(receipt_copy).to_be_visible()
    # The preview is its own scroller while the workspace fills the window, and a
    # user selects the receipt where that pane shows it.
    receipt_copy.scroll_into_view_if_needed()
    receipt_copy.select_text()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "Add a link to the deployment run without changing this receipt copy.",
    )
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    comment = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "comment"
    )
    assert comment["anchor"]["section"] == "notification-simulator"
    assert comment["anchor"]["quote"] == ("Version 2.8.0 passed all 18 release checks.")
    logged_comment = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["id"] == comment["id"]
    )

    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(
            transaction,
            [logged_comment],
            session="notification-agent",
            turn="refine-artifact",
        )
    with (
        service_model.PageTransaction(serve.page_dir) as receipt_page,
        delivery_model.receive_batch(
            receipt_page,
            {"events": [{"seq": logged_comment["seq"], "id": logged_comment["id"]}]},
            session_id=None,
        ),
    ):
        pass
    second_artifact = first_artifact.replace(
        "</article>",
        '  <footer><a href="/deployments/2.8.0">Open deployment run</a></footer>\n'
        "</article>",
    )
    artifact.write_text(second_artifact, encoding="utf-8")
    data_model.cmd_data_set(
        serve.page_dir,
        "notification-artifact",
        artifact.read_text(encoding="utf-8"),
    )
    refined_source = result_source.replace(
        "<h1>Review the deployment notification</h1>",
        "<h1>Deployment notification revised</h1>",
    )
    thread_model.cmd_reply(
        serve.page_dir,
        comment["id"],
        "Added the deployment-run link to the artifact.",
        "",
        for_event=comment["id"],
    )
    refined = stamp_page(
        serve.page_dir,
        refined_source,
        "Added the deployment-run link",
    )
    wait_for_revision(page, refined["revision"])

    expect(page.locator("#notification-artifact-source code")).to_contain_text(
        '<a href="/deployments/2.8.0">Open deployment run</a>'
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    marked = page.evaluate(
        "() => [...CSS.highlights.get('lf-mark')].map(range => range.toString()).join('')"
    )
    assert " ".join(marked.split()) == ("Version 2.8.0 passed all 18 release checks.")
    assert artifact.read_text(encoding="utf-8") == second_artifact


def test_a_playground_sends_one_choice_while_the_first_press_is_in_flight(
    browser, serve
):
    page = open_page(browser, serve(PLAYGROUND_PAGE))
    playground = page.locator("#card-playground")
    choose = playground.get_by_role("button", name="Use these settings")
    held = []
    page.route("**/api/event", lambda route: held.append(route))

    choose.evaluate("button => { button.click(); button.click(); }")
    holding(page, held, 1, "the playground choice")
    expect(choose).to_be_disabled()
    expect(choose).to_have_attribute("aria-busy", "true")
    page.wait_for_timeout(100)
    assert len(held) == 1

    held[0].continue_()
    round_trip(page)
    expect(choose).to_be_enabled()
    expect(choose).not_to_have_attribute("aria-busy", "true")
    assert len(actions(serve.page_dir)) == 1


def test_a_playground_switch_is_reachable_through_go_to(browser, serve):
    page = open_page(browser, serve(PLAYGROUND_PAGE))
    playground = page.locator("#card-playground")

    page.keyboard.press("g")
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-go-to-hints > .lf-go-to-hint[data-lf-hint-code]').length"
    )
    switch_hint = page.locator(
        '.lf-go-to-hint[data-lf-go-to-target="card-playground-compact"]'
    )
    expect(switch_hint).to_have_count(1)
    switch_code = switch_hint.get_attribute("data-lf-hint-code")
    assert switch_code

    page.keyboard.type(switch_code)
    expect(playground.get_by_role("switch", name="Compact spacing")).to_be_checked()


def test_a_playground_copy_is_reachable_through_go_to(browser, serve):
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, serve(PLAYGROUND_PAGE), context=context)
    playground = page.locator("#card-playground")
    playground.locator(".lf-playground-copy").scroll_into_view_if_needed()

    page.keyboard.press("g")
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-go-to-hints > .lf-go-to-hint[data-lf-hint-code]').length"
    )
    hint_targets = page.locator(".lf-go-to-hint").evaluate_all(
        "els => els.map(el => [el.dataset.lfGoToTarget, el.dataset.lfGoToKind])"
    )
    assert hint_targets, hint_targets
    copy_hint = page.locator(
        '.lf-go-to-hint[data-lf-go-to-target="card-playground-copy"]'
    )
    expect(copy_hint).to_have_count(1)
    copy_code = copy_hint.get_attribute("data-lf-hint-code")
    assert copy_code

    page.keyboard.type(copy_code)
    assert "12px radius" in page.evaluate("navigator.clipboard.readText()")


def test_a_playground_preset_reset_copy_and_narrow_layout_share_the_same_state(
    browser, serve
):
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    # Present a wider rendered face before the control reserves its words, so a stated
    # width cannot pass merely because it happens to fit this machine's font.
    source = PLAYGROUND_PAGE.replace(
        "</style>",
        ".lf-playground-copy-trigger { letter-spacing: 0.125rem; }</style>",
        1,
    )
    page = open_page(browser, serve(source), context=context)
    playground = page.locator("#card-playground")
    expect(playground.get_by_role("group", name="Starting points")).to_be_visible()
    expect(playground.get_by_role("group", name="Controls")).to_be_visible()

    playground.get_by_role("button", name="Dense").click()
    expect(playground.get_by_role("button", name="Dense")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert playground.evaluate("root => root.values") == {
        "accent": "#4f766f",
        "compact": True,
        "radius": 4,
        "title": "Field note",
        "tone": "bold",
    }
    playground.get_by_role("slider", name="Corner radius").press("ArrowRight")
    expect(playground.get_by_role("button", name="Dense")).to_have_attribute(
        "aria-pressed", "false"
    )
    playground.get_by_role("button", name="Dense").click()
    copy = playground.locator(".lf-playground-copy").get_by_role("button")
    copy.scroll_into_view_if_needed()

    def copy_width(label):
        expect(copy).to_have_accessible_name(label)
        reading = copy.evaluate(
            """button => {
              const visible = [...button.querySelectorAll('.lf-playground-copy-label')]
                .find(label => getComputedStyle(label).display !== 'none');
              const buttonBox = button.getBoundingClientRect();
              const labelBox = visible.getBoundingClientRect();
              const style = getComputedStyle(button);
              return {
                label: visible.textContent,
                width: buttonBox.width,
                labelLeft: labelBox.left,
                labelRight: labelBox.right,
                contentLeft: buttonBox.left + parseFloat(style.paddingLeft),
                contentRight: buttonBox.right - parseFloat(style.paddingRight),
              };
            }"""
        )
        assert reading["labelLeft"] >= reading["contentLeft"], reading
        assert reading["labelRight"] <= reading["contentRight"], reading
        return reading["width"]

    reserved_width = copy_width("Copy instruction")
    copy.click()
    assert copy_width("Copied") == reserved_width
    expect(copy).to_have_css(
        "color",
        page.evaluate(
            """() => {
          const probe = document.createElement('span');
          probe.style.color = 'var(--ok-ink)';
          document.body.append(probe);
          const color = getComputedStyle(probe).color;
          probe.remove();
          return color;
        }"""
        ),
    )
    expect(playground.locator("wa-copy-button:state(success)")).to_have_count(1)
    assert page.evaluate("navigator.clipboard.readText()") == (
        "Use a 4px radius, compact spacing set to true, a bold tone, #4f766f accents, "
        "and the title Field note."
    )

    playground.get_by_role("button", name="Reset").click()
    expect(copy).to_have_accessible_name("Copy instruction")
    assert playground.evaluate("root => root.values")["radius"] == 12
    copy.press("Enter")
    assert copy_width("Copied") == reserved_width
    assert "12px radius" in page.evaluate("navigator.clipboard.readText()")
    expect(copy).to_have_accessible_name("Copy instruction")
    page.evaluate(
        """() => {
          window.clipboardWrites = [];
          window.clipboardReleases = [];
          window.clipboardWrite = navigator.clipboard.writeText.bind(navigator.clipboard);
          navigator.clipboard.writeText = value => {
            window.clipboardWrites.push(value);
            return new Promise(resolve => window.clipboardReleases.push(resolve));
          };
        }"""
    )
    copy.click()
    radius = playground.get_by_role("slider", name="Corner radius")
    radius.press("Home")
    for _ in range(5):
        radius.press("ArrowRight")
    copy.click()
    assert page.evaluate("window.clipboardWrites") == [
        (
            "Use a 12px radius, compact spacing set to false, a quiet tone, "
            "#4f766f accents, and the title Field note."
        ),
        (
            "Use a 5px radius, compact spacing set to false, a quiet tone, "
            "#4f766f accents, and the title Field note."
        ),
    ]
    page.evaluate(
        """() => {
          navigator.clipboard.writeText = window.clipboardWrite;
          for (const release of window.clipboardReleases) release();
        }"""
    )
    assert copy_width("Copied") == reserved_width
    expect(copy).to_have_accessible_name("Copy instruction")
    page.evaluate(
        """() => {
          navigator.clipboard.writeText = () => { throw new Error('refused'); };
        }"""
    )
    copy.click()
    assert copy_width("Copy failed") == reserved_width
    resized(page, 420, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 420
    assert " " not in playground.evaluate(
        "root => getComputedStyle(root).gridTemplateColumns"
    )


def test_a_playground_rejects_restored_values_that_do_not_match_its_controls(
    browser, serve
):
    url = serve(PLAYGROUND_PAGE)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "card-playground",
            "action": "choose",
            "detail": {
                "values": {
                    "accent": "#4f766f",
                    "compact": False,
                    "radius": 12,
                    "title": "Field note",
                    "tone": "quiet",
                    "unknown": "value",
                },
                "instruction": "Use the unknown setting.",
            },
        },
    )

    page = open_page(browser, url)
    expect(page.locator("#card-playground .lf-error")).to_contain_text(
        "configuration needs exactly these fields"
    )
    consume_browser_errors(page, "configuration needs exactly these fields")


def test_a_playground_rejects_range_values_that_do_not_land_on_its_step(browser, serve):
    source = PLAYGROUND_PAGE.replace('value="12" min="0"', 'value="12.5" min="0"')
    page = open_page(browser, serve(source))

    expect(page.locator("#card-playground .lf-error")).to_contain_text(
        "control radius has a value off its step"
    )
    consume_browser_errors(
        page,
        '<lf-playground id="card-playground"> failed: '
        "control radius has a value off its step",
    )


def test_a_quoted_playground_is_a_static_preview_with_its_authored_output(
    browser, serve
):
    source = PLAYGROUND_PAGE.replace(
        '<lf-ask id="card-playground-ask">',
        '<lf-sample id="playground-example" label="card playground">',
    ).replace("</lf-ask>", "</lf-sample>")
    page = open_page(browser, serve(source))
    playground = page.locator("#card-playground")

    expect(playground.get_by_role("button")).to_have_count(0)
    expect(playground.locator("lf-playground-control:visible")).to_have_count(0)
    expect(playground.locator("lf-playground-preset:visible")).to_have_count(0)
    expect(playground.locator("#playground-card")).to_be_visible()
    expect(playground.locator("#card-instruction")).to_contain_text("12px radius")
    assert playground.evaluate("root => root.values")["compact"] is False
    assert playground.evaluate(
        """async root => {
          const {readingRegionFor} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          return readingRegionFor(root.querySelector('lf-playground-preview')) === undefined
            && !root.querySelector('[data-lf-reading-role]');
        }"""
    )


def test_a_playground_dresses_each_sample_child_and_never_its_own_page(browser, serve):
    """A candidate that restyles a whole page lives in a sample's template and keys on
    that child's root. Each child the sample presents, the first and one a reset makes,
    wears the playground's values from its first paint, and the page around the
    playground keeps its own styling."""
    source = leaf_page(
        "sample playground",
        """
<h1>Tone playground</h1>
<p id="host-note">The page around the playground.</p>
<lf-ask id="tone-ask">
  <h2>Which tone?</h2>
  <lf-playground id="tone-playground">
    <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
      <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
      <lf-playground-choice value="loud" label="Loud"></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-preview>
      <lf-sample id="tone-sample" label="tone sample">
        <template id="tone-page" data-sample>
          <style>:root[data-playground-tone="loud"] p { color: rgb(200, 0, 0); }</style>
          <h1 id="child-title">Child page</h1>
          <p id="child-note">The page the candidate restyles.</p>
        </template>
      </lf-sample>
    </lf-playground-preview>
    <lf-playground-output id="tone-instruction">Use the
      <lf-playground-value for="tone"></lf-playground-value> tone.</lf-playground-output>
  </lf-playground>
</lf-ask>
""",
    )
    page = open_page(browser, serve(source))
    child = page.frame_locator("#tone-sample iframe")
    expect(child.locator(":root")).to_have_attribute("data-playground-tone", "quiet")

    page.get_by_role("radio", name="Quiet", exact=True).press("ArrowRight")
    expect(child.locator(":root")).to_have_attribute("data-playground-tone", "loud")
    expect(child.locator("#child-note")).to_have_css("color", "rgb(200, 0, 0)")
    assert (
        page.locator("#host-note").evaluate("note => getComputedStyle(note).color")
        != "rgb(200, 0, 0)"
    )

    # Every frame of the child a Reset makes that draws the note draws it loud.
    painted = page.locator("#tone-sample").evaluate(
        """async sample => {
          const frames = [];
          let sampling = true;
          const tick = () => {
            const note = sample.querySelector('iframe').contentDocument
              ?.getElementById('child-note');
            if (note) frames.push(getComputedStyle(note).color);
            if (sampling) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          await sample.reset();
          sampling = false;
          return frames;
        }"""
    )
    assert painted and set(painted) == {"rgb(200, 0, 0)"}
    expect(child.locator(":root")).to_have_attribute("data-playground-tone", "loud")


def test_a_pointer_press_on_a_playground_control_leaves_the_user_in_the_preview(
    browser, serve
):
    """A candidate can draw only on what the user stands at in the preview, such as a
    focus treatment inside a sample child, so clicking a choice, a toggle, a preset or
    Reset, or dragging a slider, changes the candidate without taking the user out of
    the preview. A text control takes focus to be typed in, and from anywhere else a
    click takes the user to the control, where the next key acts."""
    source = leaf_page(
        "focus playground",
        """
<h1>Ring playground</h1>
<lf-ask id="ring-ask">
  <h2>Which ring?</h2>
  <lf-playground id="ring-playground">
    <lf-playground-preset label="Wide">
      <lf-playground-setting for="width" value="4"></lf-playground-setting>
    </lf-playground-preset>
    <lf-playground-control name="ring" label="Ring" kind="choice" value="thin">
      <lf-playground-choice value="thin" label="Thin"></lf-playground-choice>
      <lf-playground-choice value="thick" label="Thick"></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-control name="width" label="Width" kind="range" value="2" min="1" max="4" step="1" unit="px"></lf-playground-control>
    <lf-playground-control name="dim" label="Dim" kind="toggle" value="false"></lf-playground-control>
    <lf-playground-control name="note" label="Note" kind="text" value="hi"></lf-playground-control>
    <lf-playground-preview>
      <button id="preview-button" type="button">A candidate button</button>
      <lf-sample id="ring-sample" label="ring sample">
        <template id="ring-page" data-sample>
          <p>The page the candidate restyles.</p>
          <button id="child-button" type="button">Where the user stands</button>
        </template>
      </lf-sample>
    </lf-playground-preview>
    <lf-playground-output>Use the
      <lf-playground-value for="ring"></lf-playground-value> ring.</lf-playground-output>
  </lf-playground>
</lf-ask>
""",
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#ring-playground")
    child_button = page.frame_locator("#ring-sample iframe").locator("#child-button")
    standing = "button => button.matches(':focus') && document.hasFocus()"

    def values():
        return playground.evaluate("root => root.values")

    child_button.focus()
    assert child_button.evaluate(standing)
    page.get_by_role("radio", name="Thick", exact=True).click()
    assert values()["ring"] == "thick"
    assert child_button.evaluate(standing)

    playground.locator("wa-switch").click()
    assert values()["dim"] is True
    assert child_button.evaluate(standing), "switch"
    page.get_by_role("button", name="Wide", exact=True).click()
    assert values()["width"] == 4
    assert child_button.evaluate(standing), "preset"
    slider = playground.locator("wa-slider").bounding_box()
    page.mouse.click(slider["x"] + 2, slider["y"] + slider["height"] / 2)
    assert values()["width"] == 1
    assert child_button.evaluate(standing), "slider"
    playground.locator(".lf-playground-reset").click()
    assert values()["ring"] == "thin"
    assert child_button.evaluate(standing)

    # The same holds in the preview's own light DOM.
    preview_button = page.locator("#preview-button")
    preview_button.focus()
    page.get_by_role("radio", name="Thick", exact=True).click()
    expect(preview_button).to_be_focused()

    # A text control is operated from focus, so a press there takes it.
    note = page.get_by_role("textbox", name="Note")
    note.click()
    expect(note).to_be_focused()

    # From outside the preview, a click takes the user to the control, and the next
    # key acts there.
    thin = page.get_by_role("radio", name="Thin", exact=True)
    thin.click()
    expect(thin).to_be_focused()
    page.keyboard.press("ArrowRight")
    assert values()["ring"] == "thick"
    playground.locator("wa-switch").click()
    page.keyboard.press("Space")
    assert values()["dim"] is False

    # A sample whose page stands on nothing holds no one there.
    page.frame_locator("#ring-sample iframe").get_by_text(
        "The page the candidate"
    ).click()
    thin.click()
    expect(thin).to_be_focused()


def test_playground_labels_can_be_selected_without_changing_the_controls(
    browser, serve
):
    """A label is readable text even while the preview holds focus. Dragging its
    words selects them; clicking the switch or pressing Space still changes it."""
    source = PLAYGROUND_PAGE.replace(
        "<p>Open until dusk.</p>",
        '<p>Open until dusk.</p><button id="preview-focus">Try the card</button>',
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#card-playground")
    toggle = playground.get_by_role("switch", name="Compact spacing")

    for in_preview in (False, True):
        for name, words in (
            ("compact", "Compact spacing"),
            ("radius", "Corner radius"),
        ):
            page.evaluate("getSelection().removeAllRanges()")
            if in_preview:
                page.locator("#preview-focus").click()
            else:
                page.locator("h1").click()
            before = playground.evaluate("root => root.values")
            label = playground.locator(
                f'lf-playground-control[name="{name}"] .lf-playground-control-label'
            )
            label.scroll_into_view_if_needed()
            box = label.evaluate("""label => {
                const range = document.createRange();
                range.selectNodeContents(label);
                return range.getBoundingClientRect().toJSON();
            }""")
            y = box["y"] + box["height"] / 2
            page.mouse.move(box["x"] + 0.5, y)
            page.mouse.down()
            page.mouse.move(box["right"] - 0.5, y, steps=12)
            page.mouse.up()
            assert page.evaluate("getSelection().toString()") == words
            assert playground.evaluate("root => root.values") == before

    # Selecting a word with a double-click must not operate the switch either.
    label = playground.locator(
        'lf-playground-control[name="compact"] .lf-playground-control-label'
    )
    label.dblclick(position={"x": 5, "y": 5})
    assert page.evaluate("getSelection().toString()") == "Compact"
    expect(toggle).not_to_be_checked()

    # The control face keeps the preview focused and remains usable after selecting
    # its label. Reading that label does not change the control.
    preview = page.locator("#preview-focus")
    preview.click()
    assert page.evaluate("getSelection().toString()") == "Compact"
    playground.locator("wa-switch [part=control]").click()
    expect(toggle).to_be_checked()
    expect(preview).to_be_focused()
    label.click()
    expect(toggle).to_be_checked()
    toggle.press("Space")
    expect(toggle).not_to_be_checked()


def test_targeting_selects_names_previews_reverts_and_submits_structured_changes(
    browser, serve
):
    authored = leaf_page(
        "visual targeting",
        """
<h1 id="title">Landing page review</h1>
<lf-ask id="landing-change-ask">
  <h2>Which changes should the agent make?</h2>
  <lf-targeting id="landing-targeting">
    <lf-target-preview id="landing-preview">
      <section id="hero" class="landing-card">
        <h3 class="section-title"><span>Build the next release with complete instructions that remain available even when the candidate display has less room</span></h3>
        <p>Keep the request path visible.</p>
      </section>
      <section id="evidence" class="landing-card">
        <h3 class="section-title">Inspect the evidence</h3>
      </section>
    </lf-target-preview>
  </lf-targeting>
</lf-ask>
""",
    )
    page = open_page(browser, serve(authored, packages=("targeting",)))
    workbench = page.locator("#landing-targeting")

    workbench.get_by_role("button", name="Select element").click()
    expect(workbench).to_have_attribute("data-lf-targeting-armed", "")
    page.locator("#hero span").click()
    candidates = workbench.locator(".lf-targeting-candidate-choice")
    expect(candidates).to_have_count(4)
    candidates.filter(has_text="<section#hero>").click()

    first = workbench.locator('.lf-targeting-target[data-target-key="target-1"]')
    expect(first.locator("wa-input")).to_have_js_property(
        "value",
        "Build the next release with complete instructions that remain available even "
        "when the candidate display has less room",
    )
    first.locator("wa-input").click()
    first.locator("wa-input").press("ControlOrMeta+A")
    first.locator("wa-input").press_sequentially("Hero cards")
    expect(
        workbench.get_by_role("combobox", name="Style target", exact=True)
    ).to_have_value("Hero cards")
    first.locator("wa-input input").press("Tab")
    first.locator("wa-select").first.click()
    first.get_by_role("option", name="Shared class").click()
    expect(first.locator("wa-select").first).to_have_js_property("value", "class")
    expect(first.locator("wa-select").nth(1)).to_have_js_property(
        "value", "landing-card"
    )
    expect(
        first.locator("wa-select").nth(1).locator('[part="display-input"]')
    ).to_have_value(".landing-card · 2 matches")
    expect(first.locator("wa-select").nth(1)).to_be_visible()
    first.locator("wa-select").first.click()
    page.keyboard.press("g")
    expect(
        page.locator(".lf-go-to-hints > .lf-go-to-hint[data-lf-hint-code]")
    ).to_have_count(0)
    page.keyboard.press("Escape")
    expect(first.locator("wa-select").first).to_have_js_property("open", False)
    expect(workbench.locator(".lf-targeting-candidates")).to_be_hidden()

    workbench.get_by_role("button", name="Select element").click()
    page.locator("#evidence h3").focus()
    page.keyboard.press("Enter")
    workbench.locator(".lf-targeting-candidate-choice").first.click()
    second = workbench.locator('.lf-targeting-target[data-target-key="target-2"]')
    second.locator("wa-input").click()
    second.locator("wa-input").press("ControlOrMeta+A")
    second.locator("wa-input").press_sequentially("Evidence heading")
    second.locator("wa-input").press("Tab")
    assert (
        workbench.locator('[name="landing-targeting-instruction-target"]').evaluate(
            "element => element.value"
        )
        == "target-2"
    )

    style_target = workbench.locator('[name="landing-targeting-style-target"]')
    style_target.click()
    style_target.get_by_role("option", name="Hero cards", exact=True).click()
    expect(
        workbench.locator('[name="landing-targeting-style-property"]')
    ).to_have_js_property("value", "padding")
    expect(workbench.locator("wa-number-input")).to_have_js_property("value", "24")
    workbench.get_by_role("button", name="Add style").click()
    assert page.locator("#hero").evaluate("element => element.style.padding") == "24px"
    assert (
        page.locator("#evidence").evaluate("element => element.style.padding") == "24px"
    )

    style_change = workbench.locator(".lf-targeting-change", has_text="padding 24px")
    style_change.get_by_role("button", name="Remove").click()
    assert page.locator("#hero").evaluate("element => element.style.padding") == ""
    assert page.locator("#evidence").evaluate("element => element.style.padding") == ""

    workbench.get_by_role("button", name="Add style").click()
    instruction_target = workbench.locator(
        '[name="landing-targeting-instruction-target"]'
    )
    instruction_target.click()
    instruction_target.get_by_role(
        "option", name="Evidence heading", exact=True
    ).click()
    instruction = workbench.locator("wa-textarea textarea")
    before_height = instruction.bounding_box()["height"]
    instruction.fill("First line\n" * 12)
    expect(instruction).to_have_value("First line\n" * 12)
    assert instruction.bounding_box()["height"] > before_height
    instruction.press("Enter")
    expect(workbench.locator(".lf-targeting-change")).to_have_count(1)
    instruction.fill("Use the same sentence case as the navigation label.")
    workbench.get_by_role("button", name="Add instruction").click()

    with sending(page, "the structured targeting action"):
        workbench.get_by_role("button", name="Submit changes").click()

    actions = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["widget"] == "landing-targeting"
    ]
    assert len(actions) == 1
    assert actions[0]["action"] == "submit"
    assert actions[0]["detail"] == {
        "targets": [
            {
                "key": "target-1",
                "name": "Hero cards",
                "scope": "class",
                "className": "landing-card",
                "reference": {"kind": "id", "id": "hero"},
                "label": "<section#hero>",
                "text": "Build the next release with complete instructions that remain "
                "available even when the candidate display has less room "
                "Keep the request path visible.",
            },
            {
                "key": "target-2",
                "name": "Evidence heading",
                "scope": "element",
                "className": None,
                "reference": {
                    "kind": "structure",
                    "anchor": "evidence",
                    "path": [{"tree": "light", "tag": "h3"}],
                },
                "label": "<h3.section-title>",
                "text": "Inspect the evidence",
            },
        ],
        "changes": [
            {
                "id": "change-2",
                "target": "target-1",
                "kind": "style",
                "property": "padding",
                "value": "24px",
            },
            {
                "id": "change-3",
                "target": "target-2",
                "kind": "instruction",
                "text": "Use the same sentence case as the navigation label.",
            },
        ],
    }

    page.reload(wait_until="load")
    wait_until_ready(page)
    assert (
        page.locator("#landing-targeting wa-input").first.evaluate(
            "element => element.value"
        )
        == "Hero cards"
    )
    assert page.locator("#hero").evaluate("element => element.style.padding") == "24px"
    assert (
        page.locator("#evidence").evaluate("element => element.style.padding") == "24px"
    )

    workbench = page.locator("#landing-targeting")
    workbench.locator("wa-number-input").click()
    workbench.locator("wa-number-input").press("ControlOrMeta+A")
    workbench.locator("wa-number-input").press_sequentially("40")
    workbench.get_by_role("button", name="Add style").click()
    assert page.locator("#hero").evaluate("element => element.style.padding") == "40px"
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": actions[0]["id"]},
    )
    told(page)
    assert page.locator("#hero").evaluate("element => element.style.padding") == "40px"
    assert workbench.evaluate("element => element.currentDraft().dirty") is True
    workbench.get_by_role("button", name="Revert draft").click()
    assert page.locator("#hero").evaluate("element => element.style.padding") == ""
    expect(workbench.locator(".lf-targeting-change")).to_have_count(0)


def test_targeting_controller_keeps_unresolved_targets_visible_and_blocks_submit(
    browser, serve
):
    authored = leaf_page(
        "target lifecycle",
        """
<lf-ask id="target-lifecycle-ask">
  <h2>What should change?</h2>
  <lf-targeting id="target-lifecycle">
    <lf-target-preview id="target-lifecycle-preview">
      <article><div><span><button type="button">Keep this card identifiable</button></span></div></article>
    </lf-target-preview>
  </lf-targeting>
</lf-ask>
""",
    )
    page = open_page(browser, serve(authored, packages=("targeting",)))
    workbench = page.locator("#target-lifecycle")
    target = workbench.locator("article")
    focused = target.get_by_role("button", name="Keep this card identifiable")

    armed = workbench.evaluate(
        """element => {
          element.arm();
          const armed = element.currentDraft().armed;
          element.disarm();
          const disarmed = element.currentDraft().armed;
          element.arm();
          return {armed, disarmed, rearmed: element.currentDraft().armed};
        }"""
    )
    assert armed == {"armed": True, "disarmed": False, "rearmed": True}

    focused.focus()
    page.keyboard.press("Enter")
    candidates = workbench.locator(".lf-targeting-candidate-choice")
    expect(candidates).to_have_count(5)
    candidates.filter(has_text="<article>").click()
    workbench.get_by_role("button", name="Add style").click()
    submit = workbench.get_by_role("button", name="Submit changes")
    card = workbench.locator('[data-target-key="target-1"]')
    expect(card).to_have_attribute("data-lf-target-status", "resolved")
    expect(submit).to_be_enabled()

    draft = workbench.evaluate("element => element.currentDraft()")
    assert draft["armed"] is False
    assert draft["dirty"] is True
    assert draft["resolutions"] == {"target-1": "resolved"}
    assert draft["configuration"]["targets"][0]["reference"] == {
        "kind": "structure",
        "path": [{"tree": "light", "tag": "article"}],
    }

    workbench.locator("lf-target-preview").evaluate(
        """preview => {
          const inserted = document.createElement('article');
          inserted.dataset.insertedTarget = '';
          preview.prepend(inserted);
        }"""
    )
    expect(card).to_have_attribute("data-lf-target-status", "ambiguous")
    expect(card).to_contain_text("Ambiguous target")
    expect(card).to_be_visible()
    expect(submit).to_be_disabled()
    assert workbench.evaluate("element => element.currentDraft().resolutions") == {
        "target-1": "ambiguous"
    }

    workbench.locator("[data-inserted-target]").evaluate("element => element.remove()")
    expect(card).to_have_attribute("data-lf-target-status", "resolved")
    expect(submit).to_be_enabled()

    target.evaluate("element => element.remove()")
    expect(card).to_have_attribute("data-lf-target-status", "detached")
    expect(card).to_contain_text("Detached target")
    expect(card).to_be_visible()
    expect(submit).to_be_disabled()
    assert workbench.evaluate("element => element.currentDraft().resolutions") == {
        "target-1": "detached"
    }

    # Armed and reset in two tasks, as two gestures are: in one, arming would be a write
    # the reset takes back.
    workbench.evaluate("element => element.arm()")
    reset = workbench.evaluate(
        """element => {
          element.reset();
          return element.currentDraft();
        }"""
    )
    assert reset == {
        "armed": False,
        "dirty": False,
        "configuration": {"targets": [], "changes": []},
        "resolutions": {},
    }
    expect(workbench.locator(".lf-targeting-target")).to_have_count(0)
    expect(workbench.locator(".lf-targeting-change")).to_have_count(0)


def test_a_swipe_deck_reflows_with_its_parent_allocation(browser, serve):
    page = open_page(browser, serve(SWIPE_PAGE))
    decision = page.locator("#session-triage-decision")
    deck = page.locator("#session-triage")

    def layout(width):
        decision.evaluate("(element, value) => element.style.width = value", width)
        return deck.evaluate(
            """element => {
              const box = node => {
                const rect = node.getBoundingClientRect();
                return {
                  left: rect.left,
                  right: rect.right,
                  top: rect.top,
                  bottom: rect.bottom,
                  width: rect.width,
                };
              };
              return {
                deck: box(element),
                queue: box(element.querySelector('[verdict="unseen"]')),
                controls: box(element.querySelector('.lf-swipe-controls')),
                passed: box(element.querySelector('[verdict="pass"]')),
                kept: box(element.querySelector('[verdict="keep"]')),
              };
            }"""
        )

    narrow = layout("20rem")
    for name in ("queue", "controls", "passed", "kept"):
        assert narrow[name]["width"] == pytest.approx(narrow["deck"]["width"]), narrow
    assert narrow["queue"]["bottom"] < narrow["controls"]["top"], narrow
    assert narrow["controls"]["bottom"] < narrow["passed"]["top"], narrow
    assert narrow["passed"]["bottom"] < narrow["kept"]["top"], narrow

    stacked = layout("40rem")
    assert stacked["passed"]["top"] == pytest.approx(stacked["kept"]["top"]), stacked
    assert stacked["passed"]["right"] < stacked["kept"]["left"], stacked

    # With room for a rail the deck is a body beside it: the queue and its controls on
    # the left, Kept above Passed on the right, the rail as tall as the queue.
    railed = layout("60rem")
    assert railed["deck"]["width"] == pytest.approx(
        decision.evaluate("element => element.clientWidth")
    ), railed
    assert railed["queue"]["right"] < railed["kept"]["left"], railed
    assert railed["kept"]["left"] == pytest.approx(railed["passed"]["left"]), railed
    assert railed["kept"]["bottom"] < railed["passed"]["top"], railed
    assert railed["queue"]["top"] == pytest.approx(railed["kept"]["top"]), railed
    assert railed["queue"]["bottom"] == pytest.approx(railed["passed"]["bottom"]), (
        railed
    )
    assert railed["queue"]["bottom"] < railed["controls"]["top"], railed
    assert railed["controls"]["right"] <= railed["queue"]["right"], railed


def test_a_swipe_deck_is_one_ask_with_directional_action_hints(browser, serve):
    """The deck owns digits forwarded at its Ask and keeps local directional keys.

    The last classification both places its card and closes the Ask, so z reopens the
    question with that card back in the queue.
    """
    page = open_page(browser, serve(SWIPE_PAGE))
    decision = page.locator("#session-triage-decision")
    deck = page.locator("#session-triage")

    expect_asks_answered(page, "0/1")
    expect(deck).to_have_attribute(
        "aria-label", "Which session-store follow-ups should we keep?"
    )
    # Outside the Ask projection, the package command still spells its real binding;
    # the Decision action name is not a keycap override.
    page.keyboard.press("?")
    page.keyboard.press("?")
    pass_reference = page.locator(
        '.lf-command-reference tr[data-lf-command="swipe.pass"]'
    )
    expect(pass_reference.locator("kbd")).to_have_text("← / 1")
    expect(pass_reference.locator(".lf-binding-sequence")).to_have_attribute(
        "aria-label", "← or 1"
    )
    expect(
        page.locator('.lf-command-reference tr[data-lf-command="swipe.undo-last"]')
    ).to_have_count(0)
    page.keyboard.press("Escape")

    page.keyboard.press("a")
    expect(decision).to_be_focused()
    expect(page.locator(".lf-swipe-pass")).to_have_attribute("aria-keyshortcuts", "1")
    expect_asks_answered(page, "0/1")
    expect(
        page.locator(".lf-command-binding-badges > .lf-command-binding-badge")
    ).to_have_text(["1", "2"])
    assert active_digit_bindings(page) == "1–2"

    page.keyboard.press("Tab")
    expect(page.locator(".lf-swipe-pass")).to_have_attribute(
        "aria-keyshortcuts", "ArrowLeft 1"
    )
    assert "←\nPass" in shortcut_bar_text(page)
    assert "Pass\nPass" not in shortcut_bar_text(page)
    page.keyboard.press("a")
    expect(decision).to_be_focused()

    # The reference exposes the same exact commands through the Ask's digit routes.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(
        page.locator('.lf-command-reference-command[data-lf-command="swipe.pass"]')
    ).to_have_text("Pass")
    expect(
        page.locator('.lf-command-reference-command[data-lf-command="swipe.keep"]')
    ).to_have_text("Keep")
    expect(
        page.locator(
            '.lf-command-reference-command[data-lf-command="ask.activate-nth"]'
        )
    ).to_have_count(0)
    page.keyboard.press("Escape")

    # Directional keys remain the widget's intrinsic routes while focus is in the deck.
    page.keyboard.press("Tab")
    for binding in ("ArrowRight", "ArrowLeft", "ArrowRight", "ArrowLeft"):
        page.keyboard.press(binding)
    round_trip(page)
    expect_asks_answered(page, "1/1")
    expect(
        page.locator(".lf-command-binding-badges > .lf-command-binding-badge")
    ).to_have_count(0)
    assert "Undo last swipe" not in shortcut_bar_text(page)
    assert [event["action"] for event in actions(serve.page_dir)] == [
        "swipe",
        "swipe",
        "swipe",
        "swipe",
    ]

    page.reload(wait_until="load")
    expect(page.locator("#session-pass > #swipe-d")).to_have_count(1)
    expect_asks_answered(page, "1/1")

    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    # End is the Done fold's door; Enter opens it and the row below is the deck's.
    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    row = page.locator(".lf-queue-done button.lf-queue-row")
    expect(row).to_be_focused()
    expect(row.locator(".lf-queue-where")).to_contain_text("Answered 3 kept · 3 passed")
    page.keyboard.press("Enter")
    assert "Undo last swipe" not in shortcut_bar_text(page)

    page.keyboard.press("1")
    expect(page.locator("#session-pass > #swipe-d")).to_have_count(1)
    expect_asks_answered(page, "1/1")

    page.keyboard.press("z")
    round_trip(page)
    expect(page.locator("#session-queue > #swipe-d")).to_have_count(1)
    expect_asks_answered(page, "0/1")
    page.keyboard.press("a")
    expect_asks_answered(page, "0/1")


def test_ideas_to_implement_is_a_fast_mobile_decision_queue(browser, serve):
    """The worked example keeps the decision and both actions in one phone view,
    then records a rapid mix of touch, button, and keyboard classifications."""
    source = Path(__file__).parent.parent / "examples" / "ideas-to-implement.html"
    url = serve(source)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, url, context=context)
    deck = page.locator("#ideas-deck")
    approve = page.locator(".lf-signoff")
    expect(approve).to_be_disabled()
    expect(approve).to_have_attribute(
        "title", "Answer every Ask before approving this work"
    )
    first = page.locator("#idea-shared-filters")

    layout = page.evaluate(
        """() => {
          const card = document.querySelector('#idea-shared-filters').getBoundingClientRect();
          const controls = document.querySelector('.lf-swipe-controls').getBoundingClientRect();
          return {
            cardBottom: card.bottom,
            controlsBottom: controls.bottom,
            viewportHeight: innerHeight,
            pageWidth: document.documentElement.scrollWidth,
            viewportWidth: document.documentElement.clientWidth,
          };
        }"""
    )
    assert layout["cardBottom"] <= layout["viewportHeight"]
    assert layout["controlsBottom"] <= layout["viewportHeight"]
    assert layout["pageWidth"] == layout["viewportWidth"] == 390

    box = first.bounding_box()
    assert box
    x = round(box["x"] + box["width"] / 2)
    y = round(box["y"] + box["height"] / 2)
    cdp = context.new_cdp_session(page)
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]},
    )
    for step in range(1, 8):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [
                    {"x": x + round(box["width"] * 0.35 * step / 7), "y": y}
                ],
            },
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    expect(page.locator("#ideas-keep > #idea-shared-filters")).to_have_count(1)

    deck.get_by_role("button", name="← Pass", exact=True).click()
    page.locator("#idea-csv-export").focus()
    page.keyboard.press("ArrowRight")
    round_trip(page)

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        deck.get_by_role("button", name="← Pass", exact=True).click()

    # The deck is the user's own gesture on their own widget, so the last card leaves
    # the queue while its POST is still held. Whether the deck has answered its Ask is
    # the log's reading, so the progress count and the approval gate turn over together
    # when that answer lands.
    expect(page.locator("#ideas-queue > lf-swipe-card")).to_have_count(0)
    expect_asks_answered(page, "0/1")
    expect(approve).to_be_disabled()
    holding(page, held, 1, "the final classification")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect_asks_answered(page, "1/1")
    expect(approve).to_be_enabled()
    assert page.eval_on_selector_all(
        "#ideas-pass > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["idea-draft-warning", "idea-report-prefetch"]
    assert page.eval_on_selector_all(
        "#ideas-keep > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["idea-shared-filters", "idea-csv-export"]
    assert [
        (event["detail"]["card"], event["detail"]["to"])
        for event in actions(serve.page_dir)
    ] == [
        ("idea-shared-filters", "ideas-keep"),
        ("idea-draft-warning", "ideas-pass"),
        ("idea-csv-export", "ideas-keep"),
        ("idea-report-prefetch", "ideas-pass"),
    ]

    page.set_viewport_size({"width": 1200, "height": 900})
    wide = page.evaluate(
        """() => {
          const queue = document.querySelector('#ideas-queue').getBoundingClientRect();
          const passed = document.querySelector('#ideas-pass').getBoundingClientRect();
          const kept = document.querySelector('#ideas-keep').getBoundingClientRect();
          return {
            queueRight: queue.right,
            keptLeft: kept.left,
            keptBottom: kept.bottom,
            passedTop: passed.top,
            pageWidth: document.documentElement.scrollWidth,
            viewportWidth: document.documentElement.clientWidth,
          };
        }"""
    )
    # The wide page gives the deck room for its rail: both piles stay beside the queue.
    assert wide["queueRight"] < wide["keptLeft"], wide
    assert wide["keptBottom"] < wide["passedTop"], wide
    assert wide["pageWidth"] == wide["viewportWidth"] == 1200

    expect(approve).to_have_text("Approve version")
    expect(approve).to_be_enabled()
    approve.click()
    round_trip(page)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "done"


def test_an_unchanged_swipe_projection_repaints_nothing(browser, serve):
    """Reapplying the controller's standing state does not restate a settled deck."""
    page = open_page(browser, serve(SWIPE_PAGE))
    mutations = page.locator("#session-triage").evaluate(
        """async deck => {
          const {widgetController} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const observer = new MutationObserver(() => {});
          observer.observe(deck, {
            subtree: true,
            childList: true,
            characterData: true,
            attributes: true,
          });
          deck.renderState(widgetController(deck).read().state);
          const records = observer.takeRecords().map(record => ({
            kind: record.type,
            attribute: record.attributeName,
            target: record.target.id || record.target.className || record.target.nodeName,
          }));
          observer.disconnect();
          return records;
        }"""
    )
    assert mutations == []


def test_clearing_an_answer_reopens_its_ask_and_shuts_the_approval_gate(browser, serve):
    """An answer verb with an empty recorded value leaves its Ask unanswered."""
    html = leaf_page(
        "approval after a cleared pick",
        """
<lf-ask id="release-decision"><h1>Ship this release?</h1>
  <lf-options id="release-options" choose>
    <lf-option id="release-ship">Ship it</lf-option>
    <lf-option id="release-hold">Hold it</lf-option>
  </lf-options>
</lf-ask>
""",
        head='<meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    approve = page.locator(".lf-signoff")
    pick = page.locator("#release-ship .lf-pick")

    pick.click()
    round_trip(page)
    expect_asks_answered(page, "1/1")
    expect(approve).to_be_enabled()

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    pick.click()
    holding(page, held, 1, "the cleared selection")
    # The pick clears under the user at once; whether that leaves the Ask unanswered
    # is the log's reading, and the gate waits for it.
    expect(page.locator("#release-ship")).not_to_have_attribute("chosen", "")

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_asks_answered(page, "0/1")
    expect(approve).to_be_disabled()
    expect(approve).to_have_attribute(
        "title", "Answer every Ask before approving this work"
    )


def test_swipe_deck_buttons_arrows_and_rapid_actions_share_order(browser, serve):
    """Every input route ends at a button click, and quick classifications retain
    gesture order while the outbox serializes their requests."""
    page = open_page(browser, serve(SWIPE_PAGE))
    deck = page.locator("#session-triage")
    passed = deck.locator("#session-pass > lf-swipe-card")
    kept = deck.locator("#session-keep > lf-swipe-card")
    buttons = deck.locator(".lf-swipe-controls button:visible")

    expect(buttons).to_have_count(2)
    expect(deck).to_have_attribute("aria-keyshortcuts", "ArrowLeft ArrowRight 1 2")
    deck.get_by_role("button", name="← Pass", exact=True).click()
    expect(passed).to_have_count(2)
    round_trip(page)

    page.locator("#swipe-b").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#session-keep > #swipe-b")).to_have_count(1)
    expect(page.locator("#swipe-c")).to_be_focused()
    round_trip(page)

    # No wait between these activations: the arrow's button click exposes the next
    # card synchronously while its network attempt is still the outbox's head.
    page.locator("#swipe-c").focus()
    page.keyboard.press("ArrowLeft")
    deck.get_by_role("button", name="Keep →", exact=True).click()
    expect(passed).to_have_count(3)
    expect(kept).to_have_count(3)
    expect(deck.locator(".lf-swipe-progress")).to_be_focused()
    round_trip(page)

    logged = actions(serve.page_dir)
    assert [event["action"] for event in logged] == [
        "swipe",
        "swipe",
        "swipe",
        "swipe",
    ]
    assert [(e["detail"]["card"], e["detail"]["to"]) for e in logged] == [
        ("swipe-a", "session-pass"),
        ("swipe-b", "session-keep"),
        ("swipe-c", "session-pass"),
        ("swipe-d", "session-keep"),
    ]
    # Each swipe lands after the pile's authored card ("1") and the swipe before it.
    a, b, c, d = (event["detail"]["rank"] for event in logged)
    assert "1" < a < c and "1" < b < d


def test_a_classification_can_return_before_its_send_finishes(browser, serve):
    """An exact Return control can name its pending classification. The visual
    withdrawal is immediate, while the outbox preserves the durable action then undo
    order and resolves the local identity before the second POST reaches the server.
    """
    page = open_page(browser, serve(SWIPE_PAGE))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    card = page.locator("#swipe-a")

    with page.expect_request("**/api/event"):
        page.locator("#session-triage .lf-swipe-pass").click()
    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    returned = card.get_by_role(
        "button", name="Return Buffer rolling expiry to queue", exact=True
    )
    expect(returned).to_be_visible()
    returned.click()
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    assert len(held) == 1

    accepted = held[0].fetch()
    action = next(
        event
        for event in accepted.json()["state"]["events"]
        if event.get("attempt") == held[0].request.post_data_json["attempt"]
    )
    held[0].fulfill(response=accepted)
    holding(page, held, 2, "the dependent withdrawal")
    assert held[1].request.post_data_json["undoes"] == action["id"]
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    held[1].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    log = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] in {"action", "undo"}
    ]
    assert [(event["kind"], event.get("undoes")) for event in log] == [
        ("action", None),
        ("undo", action["id"]),
    ]


def test_return_disappears_with_a_refused_pending_classification(browser, serve):
    """A withdrawal dependent on an unaccepted action has nothing durable to name.
    Refusal drops both local entries, leaves the authored card queued, and never sends
    an invalid undo command.
    """
    page = open_page(browser, serve(SWIPE_PAGE))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    card = page.locator("#swipe-a")

    with page.expect_request("**/api/event"):
        page.locator("#session-triage .lf-swipe-pass").click()
    card.get_by_role(
        "button", name="Return Buffer rolling expiry to queue", exact=True
    ).click()
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    attempt = held[0].request.post_data_json["attempt"]
    held[0].fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    page.wait_for_timeout(50)

    assert len(held) == 1
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    assert actions(serve.page_dir) == []
    consume_browser_errors(page, "400")


def test_a_refused_return_restores_the_classification(browser, serve):
    """A fallible optimistic withdrawal is an overlay on the durable projection.
    If the undo door refuses it, the same accepted classification reappears.
    """
    page = open_page(browser, serve(SWIPE_PAGE))
    card = page.locator("#swipe-a")
    page.locator("#session-triage .lf-swipe-pass").click()
    round_trip(page)

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        card.get_by_role(
            "button", name="Return Buffer rolling expiry to queue", exact=True
        ).click()
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    attempt = held[0].request.post_data_json["attempt"]
    held[0].fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    assert len(actions(serve.page_dir)) == 1
    consume_browser_errors(page, "400")


def test_each_classified_swipe_card_can_return_to_the_queue(browser, serve):
    """A classified card returns to the front of the queue, including the one whose
    classification finished the deck."""
    page = open_page(browser, serve(SWIPE_PAGE))
    deck = page.locator("#session-triage")

    deck.get_by_role("button", name="← Pass", exact=True).click()
    deck.get_by_role("button", name="Keep →", exact=True).click()
    round_trip(page)

    first = page.locator("#swipe-a")
    second = page.locator("#swipe-b")
    first.get_by_role(
        "button", name="Return Buffer rolling expiry to queue", exact=True
    ).click()
    round_trip(page)
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(page.locator("#session-keep > #swipe-b")).to_have_count(1)
    expect(first).to_be_focused()

    for binding in ("ArrowLeft", "ArrowLeft", "ArrowRight"):
        page.locator("#session-queue > lf-swipe-card").first.focus()
        page.keyboard.press(binding)
    round_trip(page)
    expect_asks_answered(page, "1/1")
    expect(deck.locator(".lf-swipe-progress")).to_have_text("All done! · 6 classified")
    expect(
        second.get_by_role(
            "button", name="Return Bound fallback lifetime to queue", exact=True
        )
    ).to_be_visible()

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        second.get_by_role(
            "button", name="Return Bound fallback lifetime to queue", exact=True
        ).click()
    expect(page.locator("#session-queue > #swipe-b")).to_have_count(1)
    holding(page, held, 1, "the earlier card's withdrawal")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_asks_answered(page, "0/1")

    final = page.locator("#swipe-d")
    final.get_by_role(
        "button", name="Return Index account sessions to queue", exact=True
    ).click()
    round_trip(page)
    # A returned card goes to the front of the queue, so it is the one decided next.
    assert page.eval_on_selector_all(
        "#session-queue > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["swipe-d", "swipe-b"]
    expect_asks_answered(page, "0/1")
    expect(final).to_be_focused()


def _kept(card_id: str) -> str:
    """SWIPE_PAGE with one queued card written into the keep pile, after the card
    the page already kept: what a version writes after the user kept it."""
    start = SWIPE_PAGE.index(f'<lf-swipe-card id="{card_id}">')
    card = SWIPE_PAGE[start : SWIPE_PAGE.index("</lf-swipe-card>", start)]
    card += "</lf-swipe-card>"
    return SWIPE_PAGE.replace(card, "").replace(
        "<p>The revocation primitive.</p></lf-swipe-card>",
        f"<p>The revocation primitive.</p></lf-swipe-card>{card}",
    )


def test_a_card_a_later_version_wrote_into_its_pile_returns_to_the_queue(
    browser, serve
):
    """Once a version writes a swipe in, its markup places the card and an undo of the
    swipe would restore nothing. Returning the card is a new swipe to the front of
    the queue, so it still works, and the earlier swipe is no longer offered."""
    url = serve(SWIPE_PAGE)
    swiped = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "session-triage",
            "action": "swipe",
            "detail": {"card": "swipe-a", "to": "session-keep", "rank": "2"},
        },
    )
    stamp_page(serve.page_dir, _kept("swipe-a"), "kept")
    page = open_page(browser, live_url(url))
    wait_for_revision(page, 2)
    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)
    offered = """() => window.__lfRuntimeImport('/runtime/widget-api.js').then(
        ({widgetController}) => widgetController(
          document.getElementById('session-triage')).read().actions.swipe.undo
          .map(event => event.id))"""
    assert swiped["id"] not in page.evaluate(offered)

    page.locator("#swipe-a").get_by_role(
        "button", name="Return Buffer rolling expiry to queue", exact=True
    ).click()
    round_trip(page)
    assert page.eval_on_selector_all(
        "#session-queue > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["swipe-a", "swipe-b", "swipe-c", "swipe-d"]
    returned = actions(serve.page_dir)[-1]
    assert (returned["action"], returned["revision"]) == ("swipe", 2)
    assert returned["detail"]["to"] == "session-queue"
    expect(page.locator("#swipe-a")).to_be_focused()


def test_a_newer_swipe_survives_an_older_swipe_refusal(browser, serve):
    """Optimistic cards are an outbox overlay, not snapshots of one another. If an
    older swipe is refused, its card returns while a later queued verdict still lands."""
    page = open_page(browser, serve(SWIPE_PAGE))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#swipe-a").focus()

    with page.expect_request("**/api/event"):
        page.keyboard.press("ArrowLeft")
    expect(page.locator("#swipe-b")).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#swipe-c")).to_be_focused()
    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    expect(page.locator("#session-keep > #swipe-b")).to_have_count(1)
    assert len(held) == 1, (
        "the outbox sent a later gesture before its predecessor settled"
    )

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != attempt
        )
    ):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    holding(page, held, 2, "the surviving swipe")
    held[1].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(page.locator("#session-keep > #swipe-b")).to_have_count(1)
    expect(page.locator("#swipe-a")).to_be_focused()
    page.keyboard.press("ArrowLeft")
    round_trip(page)
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "swipe-b",
        "swipe-a",
    ]
    consume_browser_errors(page, "400")


def test_a_refused_early_swipe_leaves_the_deck_asking(browser, serve):
    """Four rapid gestures leave the queue looking empty locally. If the first is
    refused its card returns to the queue, and the Ask reads open again however the
    later swipes landed, because the answer is the empty queue itself.
    """
    page = open_page(browser, serve(SWIPE_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#swipe-a").focus()

    with page.expect_request("**/api/event"):
        for binding in ("ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight"):
            page.keyboard.press(binding)
    expect(page.locator(".lf-swipe-progress")).to_be_focused()
    assert len(held) == 1

    first_attempt = held[0].request.post_data_json["attempt"]
    held[0].fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": first_attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    for index in range(1, 4):
        holding(page, held, index + 1, f"gesture {index + 1}")
        held[index].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(page.locator("#session-queue > lf-swipe-card")).to_have_count(1)
    expect_asks_answered(page, "0/1")
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "swipe-b",
        "swipe-c",
        "swipe-d",
    ]
    consume_browser_errors(page, "400")


def test_swipe_deck_pointer_threshold_cancel_and_commit(browser, serve):
    """Pointer Events preserve a vertical/tentative read and cancel cleanly; only a
    horizontal drag beyond the deck's threshold reaches a verdict button."""
    url = serve(SWIPE_PAGE)
    page = open_page(browser, url)
    card = page.locator("#swipe-a")
    box = card.bounding_box()
    assert box
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 24, y)
    page.mouse.up()
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(card).not_to_have_class(re.compile(r"\blf-swipe-dragging\b"))
    assert card.evaluate("el => el.style.getPropertyValue('--lf-swipe-drag-x')") == ""

    page.mouse.move(x, y)
    page.evaluate(
        """() => document.addEventListener('pointerdown', event => {
          window.__swipePointerId = event.pointerId;
        }, {capture: true, once: true})"""
    )
    page.mouse.down()
    page.mouse.move(x + 80, y)
    pointer_id = page.evaluate("window.__swipePointerId")
    assert isinstance(pointer_id, int)
    card.dispatch_event("pointercancel", {"pointerId": pointer_id})
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(card).not_to_have_class(re.compile(r"\blf-swipe-dragging\b"))
    assert not page.evaluate(DRAG_HELD), "a cancelled pointer left the drag held"
    assert card.evaluate("el => el.style.getPropertyValue('--lf-swipe-drag-x')") == ""
    page.mouse.up()

    select_words(page, "#swipe-a p:first-of-type")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    assert page.evaluate("() => getSelection().toString().trim()")

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - 30, y)
    page.mouse.up()
    # Read after the selection surface's release rendering: before the claim boundary
    # existed, a swipe the deck let go of restored the pointerdown range and raised
    # the Comment bar again.
    rendered(page)
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    assert page.evaluate("() => getSelection().toString()") == ""
    assert not page.locator(".lf-fab-bar").is_visible()

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - box["width"] * 0.35, y)
    page.mouse.up()
    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    round_trip(page)
    page.close()

    context = browser.new_context(
        viewport={"width": 420, "height": 900}, has_touch=True
    )
    touch = open_page(browser, url, context=context)
    touch_card = touch.locator("#swipe-b")
    touch_box = touch_card.bounding_box()
    assert touch_box
    tx = round(touch_box["x"] + touch_box["width"] / 2)
    ty = round(touch_box["y"] + touch_box["height"] / 2)
    cdp = context.new_cdp_session(touch)
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": tx, "y": ty}]},
    )
    for step in range(1, 8):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [
                    {
                        "x": tx + round(touch_box["width"] * 0.35 * step / 7),
                        "y": ty,
                    }
                ],
            },
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    expect(touch.locator("#session-keep > #swipe-b")).to_have_count(1)
    round_trip(touch)


def test_swipe_deck_exit_echo_starts_at_the_dragged_card_box(browser, serve):
    """The Tinder-like exit continues from the held card instead of gaining its
    padding and border a second time when the fixed-position echo is sized."""
    page = open_page(browser, serve(SWIPE_PAGE), init_script=HOLD_MOTION)
    card = page.locator("#swipe-a")
    box = card.bounding_box()
    assert box
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - box["width"] * 0.35, y)
    dragged = card.bounding_box()
    assert dragged
    page.mouse.up()

    echo = page.locator(".lf-swipe-exit")
    expect(echo).to_have_count(1)
    echo_box = echo.bounding_box()
    assert echo_box
    assert echo_box == pytest.approx(dragged, abs=0.02)
    page.evaluate("window.__lfHeld[0].finish()")
    expect(echo).to_have_count(0)
    round_trip(page)


def test_swipe_deck_projects_the_same_exit_motion_as_a_local_swipe(browser, serve):
    """A remote action carries its production projection through the exit motion.

    A reload reads the same standing unit but arrives before presentation, so it restores
    the final placement without replaying old news as a new transition.
    """
    url = serve(SWIPE_PAGE)
    page = open_page(browser, url, init_script=HOLD_MOTION)

    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "session-triage",
            "action": "swipe",
            "detail": {"card": "swipe-a", "to": "session-keep", "rank": "j"},
        },
    )
    told(page)

    expect(page.locator(".lf-swipe-exit")).to_have_count(1)
    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)
    page.evaluate("window.__lfHeld[0].finish()")
    expect(page.locator(".lf-swipe-exit")).to_have_count(0)

    page.reload()
    wait_until_ready(page)
    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)
    expect(page.locator(".lf-swipe-exit")).to_have_count(0)


def test_swipe_deck_activation_restores_a_standing_swipe_without_motion(browser, serve):
    """A new revision that writes an old classification shows it at rest, as an
    arrival."""
    url = serve(SWIPE_PAGE)
    page = open_page(browser, live_url(url), init_script=HOLD_MOTION)

    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "session-triage",
            "action": "swipe",
            "detail": {"card": "swipe-a", "to": "session-keep", "rank": "j"},
        },
    )
    told(page)
    expect(page.locator(".lf-swipe-exit")).to_have_count(1)
    page.evaluate("window.__lfHeld[0].finish()")
    expect(page.locator(".lf-swipe-exit")).to_have_count(0)

    stamp_page(serve.page_dir, _kept("swipe-a"), "second")
    wait_for_revision(page, 2)

    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)
    expect(page.locator(".lf-swipe-exit")).to_have_count(0)


def test_swipe_deck_reloads_replays_and_undoes_absolute_placement(browser, serve):
    """The pile position is durable state, not module memory: reload reconstructs it,
    and undo restores the card to its authored queue position."""
    url = serve(SWIPE_PAGE)
    page = open_page(browser, url)
    page.get_by_role("button", name="Keep →", exact=True).click()
    round_trip(page)
    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)

    page.reload(wait_until="load")
    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)
    assert page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const deck = document.getElementById('session-triage');
          const {state} = widgetController(deck).read();
          window.swipeCards = [...deck.querySelectorAll('lf-swipe-card')];
          deck.renderState(state);
          deck.renderState(state);
          return window.swipeCards.every(card => document.getElementById(card.id) === card);
        }"""
    )
    assert page.eval_on_selector_all(
        "#session-keep > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["already-kept", "swipe-a"]
    undo(page)
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    assert page.eval_on_selector_all(
        "#session-queue > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["swipe-a", "swipe-b", "swipe-c", "swipe-d"]
    assert page.evaluate(
        "window.swipeCards.every(card => document.getElementById(card.id) === card)"
    )


def test_a_quoted_swipe_deck_is_a_static_labeled_exhibit(browser, serve):
    source = SWIPE_PAGE.replace(
        '<lf-ask id="session-triage-decision">',
        '<lf-sample id="swipe-example" label="session triage">',
    ).replace("</lf-ask>", "</lf-sample>")
    page = open_page(browser, serve(source))
    deck = page.locator("#session-triage")

    expect(deck).to_have_attribute("aria-label", "Card classification")
    expect(deck.locator(".lf-swipe-controls")).to_have_count(0)
    expect(deck.get_by_role("button")).to_have_count(0)
    expect(deck.locator("lf-swipe-card[tabindex]")).to_have_count(0)
    expect(deck.locator("lf-swipe-card:visible")).to_have_count(6)
    assert deck.get_by_role("list").count() == 3
    deck.locator("#session-queue > lf-swipe-card").evaluate_all(
        "cards => cards.forEach(card => document.querySelector('#session-keep').append(card))"
    )
    deck_box = deck.bounding_box()
    queue_box = deck.locator("#session-queue").bounding_box()
    assert deck_box and queue_box
    assert queue_box["x"] == pytest.approx(deck_box["x"], abs=0.02)
    assert queue_box["width"] == pytest.approx(deck_box["width"], abs=0.02)
    resized(page, 420, 900)
    passed = page.locator("#session-pass").bounding_box()
    kept = page.locator("#session-keep").bounding_box()
    assert passed and kept and passed["y"] + passed["height"] <= kept["y"]


def test_a_quoted_swipe_queue_spaces_its_flat_cards(browser, serve):
    """A quoted queue is flat rather than a stack, so its cards stand in flow, a gap
    apart rather than touching."""
    source = SWIPE_PAGE.replace(
        '<lf-ask id="session-triage-decision">',
        '<lf-sample id="swipe-example" label="session triage">',
    ).replace("</lf-ask>", "</lf-sample>")
    page = open_page(browser, serve(source))
    boxes = [page.locator(f"#swipe-{card}").bounding_box() for card in ("a", "b", "c")]
    gaps = [
        lower["y"] - (upper["y"] + upper["height"]) for upper, lower in pairwise(boxes)
    ]
    gap = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--sp-2'))"
    )
    assert gap > 0
    assert gaps == pytest.approx([gap, gap], abs=0.5)


def test_an_empty_quoted_swipe_queue_says_it_is_empty(browser, serve):
    page = open_page(browser, serve(EMPTY_QUOTED_SWIPE_PAGE))
    labels = page.locator("#completed-swipe .lf-swipe-pile-label")

    assert labels.all_inner_texts() == ["QUEUE · 0", "PASSED · 0", "KEPT · 1"]


def test_a_reduced_motion_swipe_moves_without_an_exit_animation(browser, serve):
    context = browser.new_context(reduced_motion="reduce")
    page = open_page(browser, serve(SWIPE_PAGE), context=context)
    page.get_by_role("button", name="← Pass", exact=True).click()

    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    expect(page.locator(".lf-swipe-exit")).to_have_count(0)
    round_trip(page)


def test_composer_grows_caps_and_shrinks_with_its_text(browser, serve):
    """The comment box fits its content, scrolls at its cap, and shrinks back."""
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    box = page.locator(".lf-general leaf-text")

    def state():
        return box.evaluate("""ta => ({ h: Math.round(ta.getBoundingClientRect().height),
                                        scrollable: ta.scrollHeight > ta.clientHeight })""")

    empty = state()
    box.type("A comment long enough to wrap onto a second line and then a third.")
    grown = state()
    write(box, "x " * 900)  # far past the ceiling
    capped = state()
    write(box, "short again")
    shrunk = state()

    assert grown["h"] > empty["h"], "the box must grow with its content"
    assert not grown["scrollable"], "a box that fits its text must not be scrollable"
    # The ceiling is 50vh — the viewport's share, not a count of lines — measured
    # here in the suite's 900px-tall window.
    assert capped["h"] == 450, f"the box must stop at its ceiling, got {capped['h']}px"
    assert capped["scrollable"], (
        "past the ceiling the scrollbar is real and belongs there"
    )
    assert shrunk["h"] == empty["h"], "and it must shrink back"


@pytest.mark.parametrize("reduced_motion", ["no-preference", "reduce"])
def test_suggestion_controls_stay_out_of_the_column(browser, serve, reduced_motion):
    """Suggestion chrome hangs in the page margin, so the prose keeps the full column
    and reads as it will once the change is settled. The row is the column's own
    child and takes its line from an anchor inside the change, so how deep the
    change sits costs it nothing: one inside a card — a positioned ancestor, which
    `left: 100%` used to resolve against, dropping the row back into the text —
    hangs in the rail beside its card like any other. What is left is a
    measurement no lint can make: where a row stands as a pin, it stands by the change
    it decides, level with the line the change ends on, over none of the change's
    words, and on the change's own card."""
    page = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    page.emulate_media(reduced_motion=reduced_motion)
    column = page.locator("main").evaluate("el => el.getBoundingClientRect().right")
    box = "el => el.getBoundingClientRect()"

    margin_rows = page.locator(
        "[data-lf-margin-for='sug-refill'], [data-lf-margin-for='sug-thistle']"
    )
    assert margin_rows.count() == 2
    for i in range(2):
        assert margin_rows.nth(i).evaluate(box)["left"] > column, (
            "a control row overlapping the column re-wraps the prose it reviews"
        )
    # Two changes a line apart, so the rows would collide at their natural offsets.
    first, second = (margin_rows.nth(i).evaluate(box) for i in range(2))
    assert first["bottom"] <= second["top"], "control rows must not stack on each other"

    # The board grows past the rail, so the row pins near the change. Its seat can
    # move off the card when that is the nearest room that covers no words.
    in_card_row = page.locator("[data-lf-margin-for='sug-in-card']")
    expect(in_card_row).to_have_attribute("data-lf-place", "pin")
    stands_by = """row => {
      const edges = ({left, top, right, bottom}) => ({left, top, right, bottom});
      const change = row.lfTarget;
      const words = [];
      for (const node of [change, ...change.querySelectorAll('*')])
        for (const text of node.childNodes)
          if (text.nodeType === Node.TEXT_NODE && text.data.trim()) {
            const range = document.createRange();
            range.selectNodeContents(text);
            words.push(...[...range.getClientRects()]
              .filter((b) => b.width > 2 && b.height > 2).map(edges));
          }
      const entries = [...row.querySelectorAll('.lf-margin-entry')]
        .filter((entry) => entry.checkVisibility())
        .map((entry) => edges(entry.getBoundingClientRect()));
      const hit = (a, b) => a.left < b.right && b.left < a.right
        && a.top < b.bottom && b.top < a.bottom;
      const last = edges([...change.getClientRects()].at(-1));
      const r = row.getBoundingClientRect();
      return {
        covers: entries.filter((e) => words.some((w) => hit(e, w))).length,
        near: Math.hypot(
          Math.max(0, r.left - last.right, last.left - r.right),
          Math.max(0, r.top - last.bottom, last.top - r.bottom)) <= 12,
        inPage: r.right <= document.body.getBoundingClientRect().right,
      };
    }"""
    placed = in_card_row.evaluate(stands_by)
    assert placed == {
        "covers": 0,
        "near": True,
        "inPage": True,
    }, f"a change inside a board is decided near its words: {placed}"

    # No rail: every row is a pin by its own change, and nothing spills sideways.
    resized(page, 820, 900)
    page.wait_for_function(
        "() => [...document.querySelectorAll('[data-lf-margin-for^=sug-]')]"
        ".every(r => r.dataset.lfPlace === 'pin')"
    )
    assert root_overflow(page) == 0
    for widget in ("sug-refill", "sug-in-card"):
        placed = page.locator(f"[data-lf-margin-for='{widget}']").evaluate(stands_by)
        assert placed == {
            "covers": 0,
            "near": True,
            "inPage": True,
        }, f"a pin stands near the change it decides, over none of its words: {placed}"


def test_the_page_says_a_change_is_only_proposed(browser, serve):
    """Who says the change is still a proposal, in each medium the page reaches.

    On screen the ✓/✗ row hanging on the change's own line says it, and the word is
    for whoever is listening, so it stays clipped. Paper has no row, so each pending
    slot needs visible words distinguishing a proposal from ordinary settled content.

    The word also had to change to be worth showing. Pendingness was carried by the
    word's mere presence, which no user can perceive — nothing sits alongside to
    compare it against — and `deletion` is ARIA's own name for the completed act, so
    a listener heard the change announced as made while the page was still asking."""
    url = serve(PROPOSED_PAGE)
    page = open_page(browser, url)

    quiet = "lf-suggestion:not([data-lf-state]) > :is(lf-old, lf-new) > .lf-quiet"
    read = """(sel) => [...document.querySelectorAll(sel)].map(el => {
        const r = el.getBoundingClientRect();
        return {word: el.textContent, shown: el.checkVisibility(),
                w: Math.round(r.width), h: Math.round(r.height)};
    })"""
    live = page.evaluate(read, quiet)
    assert [q["word"] for q in live] == [
        "proposed deletion",
        "proposed insertion",
        "proposed insertion",
        "proposed deletion",
    ], live
    for q in live:
        assert q["w"] <= 1 and q["h"] <= 1, (
            f"on screen the row says it; `{q['word']}` must hold no room, got {q}"
        )
    # And the row is there to say it — the fact paper is about to lose.
    expect(page.locator(".lf-margin-cluster")).to_have_count(3)

    page.emulate_media(media="print")
    shown = page.evaluate(read, quiet)
    assert [q["word"] for q in shown] == [q["word"] for q in live], shown
    for q in shown:
        assert q["shown"] and q["w"] > 1, (
            f"with no row on paper, `{q['word']}` is the only thing saying the "
            f"change is unmade, and it is not printed: {q}"
        )


def test_a_moved_change_takes_its_controls_with_it(browser, serve):
    """The row is the column's child, not the change's, so the subtree a card
    travels in no longer carries it: a card dragged to another column, or moved by
    the replay of someone else's drag, leaves and re-enters the document with its
    row unhooked. Re-connection has to hang it again, or the user loses the
    only way to decide a change that is still plainly pending on the page. Replayed
    rather than dragged, because that is the same move with no gesture in the way."""
    url = serve(SUGGESTION_PAGE)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeders",
            "action": "move",
            "detail": {"card": "card-heater", "to": "col-done", "rank": "0i"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#col-done #card-heater")).to_be_visible()
    page.locator("#col-done #card-heater").scroll_into_view_if_needed()
    margins_laid_out(page)
    box = "el => el.getBoundingClientRect()"
    row = page.locator("[data-lf-margin-for='sug-in-card']")
    expect(row).to_be_visible()
    # The row stands on the moved card: at its line, or packed just below the card's
    # own marker where the two would otherwise stand on one corner.
    card = page.locator("#card-heater").evaluate(box)
    change = page.locator("#sug-in-card lf-old").evaluate(box)
    stands = row.evaluate(box)
    assert change["top"] - 5 <= stands["top"] <= change["top"] + 48, (
        "the row must find the moved change's line again, not the one it left"
    )
    assert card["left"] < stands["right"] <= card["right"] + 40, (stands, card)
    row.locator(".lf-sug-accept").click()
    expect(page.locator("#sug-in-card lf-old")).to_be_hidden()


# A change the user hasn't opened yet. The row hangs off an anchor in the
# change, and a collapsed container reports its content's last rendered geometry
# rather than nothing at all — so a row that trusted a measurement would hang in
# the margin deciding a change nobody can see.
def test_a_terse_compare_keeps_its_side_by_side_grid(browser, serve):
    """An exhibition is looked across where a decision is read down: terse variants
    share a row while block content stacks the group. Which children count as block
    is the phrasing-set inversion, and its one hazard is an inline widget — a
    chip-led pair must not stack, which is why the stylesheet's list excludes the
    marker the runtime paints from x-inline and this reads the shipped page to prove
    the grid actually held. It is the whole chain in one assertion: a declaration
    unpainted, a marker unread, or a selector naming the wrong attribute all arrive
    here as two variants that stacked."""
    page = open_page(
        browser,
        serve(Path(__file__).parent.parent / "examples/developer/feature-gallery.html"),
    )
    top = "el => el.getBoundingClientRect().top"
    assert page.locator("#bg-variant-paper").evaluate(top) == page.locator(
        "#bg-variant-screen"
    ).evaluate(top), "chip-led terse variants must share a row"
    assert page.locator("#bg-variant-paper-detail").evaluate(top) != page.locator(
        "#bg-variant-screen-detail"
    ).evaluate(top), "block-content variants must stack"


def test_an_undone_suggestion_stays_inline_among_the_words(browser, serve):
    """An undone suggestion retains its inline presentation and the surrounding comparison layout."""
    page = open_page(browser, serve(REBUILT_INLINE_PAGE))
    form = "() => getComputedStyle(document.getElementById('cmp-stores')).display"
    assert page.evaluate(form) == "grid", (
        "the exhibition stacked before anything was decided, so this proves nothing"
    )

    page.locator("[data-lf-margin-for='sug-store'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-store lf-old")).to_be_hidden()
    undo(page)
    expect(page.locator("#sug-store lf-old")).to_be_visible()
    assert page.evaluate(form) == "grid", (
        "the rebuilt suggestion lost its inline mark, so the exhibition stacked"
    )


def test_a_block_change_emphasizes_the_words_that_moved(browser, serve):
    """A replacement's slots paint whole — which is all a dead copy keeps — and on
    the live page the words that differ deepen through the highlight registry, so
    the user isn't left to eyeball-diff two paragraphs. Deciding clears the
    emphasis with the slot it retires: the survivor is plain prose."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    inside = """(id) => Object.fromEntries(['lf-sug-del', 'lf-sug-ins'].map(name =>
        [name, [...(CSS.highlights.get(name) ?? [])]
            .filter(r => document.getElementById(id).contains(r.startContainer))
            .length]))"""
    refill = page.evaluate(inside, "sug-refill")
    assert refill["lf-sug-del"] >= 1 and refill["lf-sug-ins"] >= 1, (
        "an edited sentence must emphasize the words that moved, on both sides"
    )

    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate(inside, "sug-refill") == {
        "lf-sug-del": 0,
        "lf-sug-ins": 0,
    }, "deciding must clear the emphasis with the slot it retires"


def test_suggestion_emphasis_skips_generated_interface_between_changed_words(
    browser, serve
):
    """A changed span may cross a nested widget without painting its generated UI."""
    page = open_page(browser, serve(FEATURE_GALLERY))
    page.locator('[data-lf-margin-for="bg-route-ask"] .lf-margin-marker').click()
    badges = page.locator("#bg-route > lf-option > .lf-key-badge")
    expect(badges).to_have_text(["1", "2"])

    assert page.locator("#bg-nested-change > lf-new > p").evaluate(
        """node => [...(CSS.highlights.get('lf-sug-ins') ?? [])]
          .some(range => range.intersectsNode(node.firstChild))"""
    ), "the proposal has to carry word-level insertion emphasis"
    assert badges.evaluate_all(
        """nodes => {
          const ranges = [...(CSS.highlights.get('lf-sug-ins') ?? [])];
          return nodes.map(node =>
            ranges.some(range => range.intersectsNode(node.firstChild)));
        }"""
    ) == [
        False,
        False,
    ], "the authored change's emphasis crossed into the Ask's generated key hints"


def test_a_whole_swap_paints_no_emphasis(browser, serve):
    """An alignment that shares almost nothing is a replacement, not an edit, and
    emphasis over everything says nothing — the similarity gate every mature diff
    view applies. The whole-slot tints already say a swap is on offer."""
    page = open_page(browser, serve(SWAP_PAGE))
    total = page.evaluate(
        "() => (CSS.highlights.get('lf-sug-del')?.size ?? 0)"
        " + (CSS.highlights.get('lf-sug-ins')?.size ?? 0)"
    )
    assert total == 0, "unrelated old and new text must not be word-marked"


def test_a_row_waits_for_the_change_it_decides_to_be_on_screen(browser, serve):
    """A change inside a collapsed container has no line for its row to hang on,
    and an anchor that isn't rendered is no anchor at all: the row falls back to
    the block it was hoisted to and hangs there in the margin, offering to decide
    something the user can't see. It waits instead, and arrives on the change's
    own line the moment the container opens — a real click on the summary, because
    opening it is the user's gesture and the reflow it causes is the point."""
    page = open_page(browser, serve(COLLAPSED_PAGE))
    waiting = page.locator("[data-lf-margin-for='sug-boxes']")
    expect(page.locator("[data-lf-margin-for='sug-now']")).to_be_visible()
    expect(waiting).to_be_hidden()

    page.locator("#sum").click()
    expect(waiting).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = waiting.evaluate(box)
    assert row["left"] > page.locator("main").evaluate(box)["right"], (
        "the row must arrive in the margin, not over the prose that just opened"
    )
    assert (
        abs(row["top"] - page.locator("#sug-boxes lf-new").evaluate(box)["top"]) <= 5
    ), "and on the line of the change it decides"


def test_the_ask_walk_lands_on_a_suggestion_the_reveal_just_opened(browser, serve):
    """Stepping the Asks opens the closed <details> a change waits inside, and does
    it in the same task as the arrival. The row un-waits on the runtime's reveal signal
    rather than at the observer's next frame: settled asynchronously, the arrival landed
    on a display:none element and the user stayed where they were — at the previous
    decision — while the announce said otherwise, so Enter was aimed at a decision they
    had already seen."""
    page = open_page(browser, serve(COLLAPSED_PAGE))
    page.keyboard.press("a")
    expect(page.locator("#sug-now[data-lf-ask]")).to_have_count(1)
    page.keyboard.press("a")
    expect(page.locator("#later")).to_have_attribute("open", "")
    expect(page.locator("#sug-boxes[data-lf-ask]")).to_have_count(1)
    # The arrival stands on the suggestion; what the reveal has to have done is leave the
    # control that answers it a thing the user can reach, which a display:none control
    # is not.
    expect(
        page.locator("[data-lf-margin-for='sug-boxes'] .lf-sug-accept")
    ).to_be_visible()


def test_accepting_a_suggestion_settles_it_and_reaches_claude(browser, serve):
    """Accepting collapses the change to the proposal as ordinary prose — no
    tint, no strike — because the live view is the version plus the user's
    actions, and the honoring version only has to catch up.
    The outcome has to reach the log too: what the user sees settle and what
    Claude is told must be the same event.

    The resulting content and Undo control are sufficient visual confirmation. No
    status or transient notice repeats them, while the live region says the same
    decision for a user listening to the page."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    row = page.locator("[data-lf-margin-for='sug-refill']")
    accept = row.locator(".lf-sug-accept")
    reject = row.locator(".lf-sug-reject")
    assert accept.get_attribute("aria-label").startswith(
        "Accept the suggested change: Refill a feeder when"
    ), "the button names the proposal, not the text being replaced"
    # Inside the row rather than on the page: the row is positioned, so a button's
    # offset box is its place on that row, and an inline change that reflows the
    # paragraph it sits in carries the whole row with it legitimately. What must not
    # move is one control against the other.
    box = "el => [el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight]"
    before = accept.evaluate(box)
    # The verb is discovery chrome; at rest the margin entry is the canonical circle.
    expect(accept.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "check"
    )

    # A strike and two tints say which words are going and which are proposed, and say
    # it in no text at all: a user listening got the sentence twice, the two readings
    # contradicting each other, with nothing to say either was a change.
    assert "deletion" in page.locator("#sug-refill lf-old").aria_snapshot()
    assert "insertion" in page.locator("#sug-refill lf-new").aria_snapshot()

    accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(accept).to_have_count(0)
    undo_button = row.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo_button.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "undo"
    )
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(row).not_to_contain_text("Accepted")
    assert undo_button.get_attribute("data-lf-said") is None
    expect(undo_button).to_be_enabled()
    expect(undo_button).to_be_focused()
    assert undo_button.evaluate(box) == before, (
        "Undo moved away from the press it replaces"
    )
    expect(page.locator(".lf-notice")).to_have_text("")
    expect(page.locator(".lf-notice")).not_to_have_class(re.compile(r"\bshow\b"))
    expect(page.locator(".lf-live")).to_have_text(
        re.compile(r"^Accepted suggested change: Refill a feeder when")
    )
    expect(reject).to_be_hidden()
    settled = page.locator("#sug-refill lf-new").evaluate(
        "el => getComputedStyle(el).textDecorationLine + ' ' + getComputedStyle(el).backgroundColor"
    )
    # And the word goes with the marks, the settled slot being ordinary prose now:
    # a user listening is told about a change while there is one to decide.
    assert "insertion" not in page.locator("#sug-refill lf-new").aria_snapshot()
    assert "line-through" not in settled and "rgba(0, 0, 0, 0)" in settled, (
        f"settled text still wears a pending mark: {settled}"
    )
    # The banner's count follows the page: three pending, one decided.
    expect(page.locator(".lf-answer-all")).to_have_text("Accept all (2)")
    expect_banner_control_offered(page.locator(".lf-answer-all"))

    # The boundary before reading the shared log: what the press sent has to have a
    # definitive outcome first. The fetch this replaced proved nothing —
    # `wait_for_function` awaits the promise a predicate returns, but a falsy
    # resolution ends the wait instead of polling again, so it came back `False` on
    # the first poll and the read below ran unguarded.
    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["action"], e["author"]) for e in logged] == [
        ("sug-refill", "decide", "user")
    ]


def test_a_pointer_decision_announces_without_needing_button_focus(browser, serve):
    """The live result is independent of browsers focusing a clicked margin entry."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    assert page.evaluate("document.activeElement === document.body")

    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").evaluate(
        "button => button.click()"
    )

    assert page.evaluate("document.activeElement === document.body")
    expect(page.locator(".lf-live")).to_have_text(
        re.compile(r"^Accepted suggested change: Refill a feeder when")
    )
    expect(page.locator(".lf-notice")).to_have_text("")
    expect(page.locator(".lf-notice")).not_to_have_class(re.compile(r"\bshow\b"))


def test_a_settled_deletion_keeps_undo_on_the_containing_passage(browser, serve):
    """A pure deletion leaves no suggestion box, but Undo remains reachable."""
    page = open_page(browser, serve(PROPOSED_PAGE))
    page.locator("[data-lf-margin-for='sug-delete'] .lf-sug-accept").click()

    expect(page.locator("#sug-delete")).to_be_hidden()
    undo = page.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo).to_be_visible()
    expect(
        undo.locator("xpath=ancestor::*[contains(@class, 'lf-margin-cluster')]")
    ).not_to_have_class(re.compile(r"\blf-withheld\b"))
    expect(page.locator(".lf-margin-receipt")).to_have_count(0)


def test_rejecting_a_suggestion_promotes_the_surviving_button(browser, serve):
    """Reject leaves an active Undo, never a dead circle or a second status."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    row = page.locator("[data-lf-margin-for='sug']")
    reject = row.locator(".lf-sug-reject")
    unfolded_button(reject).click()

    expect(reject).to_have_count(0)
    undo_button = row.get_by_role("button", name=re.compile(r"^Undo rejecting"))
    expect(undo_button).to_have_attribute("data-lf-margin-entry-primary", "")
    expect(row.locator(".lf-sug-accept")).to_be_hidden()
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(row).not_to_contain_text("Rejected")
    undo_button.click()
    round_trip(page)
    expect(page.locator("#sug")).not_to_have_attribute(
        "data-lf-state", re.compile(".+")
    )
    expect(page.locator("[data-lf-margin-for='sug'] .lf-sug-accept")).to_be_visible()


def test_a_settled_boxless_suggestion_keeps_its_own_margin_identity(browser, serve):
    """A `display: contents` suggestion still paints through its children; settling it
    must not re-perch Undo on the containing section and change the map target."""
    styled = SHORT_SUGGESTION.replace(
        "</head>", "<style>#sug { display: contents; }</style>\n</head>"
    )
    page = open_page(browser, serve(styled))
    item = page.locator("[data-lf-margin-for='sug']")
    assert item.evaluate("row => row.lfTarget.id") == "sug"

    item.locator(".lf-sug-accept").click()
    expect(
        item.get_by_role("button", name=re.compile(r"^Undo accepting"))
    ).to_be_visible()
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    assert item.evaluate("row => row.lfTarget.id") == "sug"


def test_a_refused_undo_keeps_the_outcome_and_can_be_retried(browser, serve):
    """Undo has the same failure lifecycle without inventing a counter-decision."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    row = page.locator("[data-lf-margin-for='sug']")
    with sending(page, "the decision to be withdrawn"):
        unfolded_button(row.locator(".lf-sug-reject")).click()
    decision = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["detail"]["outcome"] == "reject"
    )
    refused = []

    def refuse_undo(route):
        event = route.request.post_data_json
        if event["kind"] != "undo":
            route.continue_()
            return
        refused.append(event)
        route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        )

    page.route("**/api/event", refuse_undo)
    with sending(page, "the refused withdrawal"):
        row.get_by_role("button", name=re.compile(r"^Undo rejecting")).click()
    assert [(event["kind"], event["undoes"]) for event in refused] == [
        ("undo", decision["id"])
    ]
    receipt = row.locator(".lf-margin-receipt")
    expect(receipt).to_have_text("Undo failed · Rejected")
    consume_browser_errors(page, "400")
    assert receipt.evaluate(
        """element => {
          const probe = document.createElement('span');
          probe.style.color = 'var(--danger-ink)';
          document.body.append(probe);
          const matches = getComputedStyle(element).color === getComputedStyle(probe).color;
          probe.remove();
          return matches;
        }"""
    )
    expect(page.locator("#sug")).to_have_attribute("data-lf-state", "reject")
    item = row.locator("xpath=..")
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    page.unroute("**/api/event")
    with sending(page, "the retried withdrawal"):
        item.get_by_role("button", name="Retry", exact=True).click()
    expect(page.locator("#sug")).not_to_have_attribute(
        "data-lf-state", re.compile(".+")
    )
    logged = events_model.read_events(serve.page_dir)
    assert [event["undoes"] for event in logged if event["kind"] == "undo"] == [
        decision["id"]
    ]


# `folded` is the layer's own division of the pair rather than a convenience: accept
# rests in the rail as the target's primary margin entry, and reject is one press behind `…`.
@pytest.mark.parametrize(
    "outcome,verb,folded",
    [("accept", "Accepted", False), ("reject", "Rejected", True)],
)
def test_a_widget_naming_its_own_words_does_not_read_the_runtimes(
    browser, serve, outcome, verb, folded
):
    """The line saying a block carries a comment goes in the block, and a block inside a
    widget is still a block — so `textContent` on a widget's own slot now returns the
    author's words with the runtime's appended. A suggestion labels itself from that slot,
    and offered to accept “Retry three times. 1 comment”. It reads the slot the way the
    page is read instead, which is what `says` is for — read before deciding, because a
    reject retires the very slot the label comes from, and a retired slot says nothing:
    the announcement then named the widget's id instead of the words the user judged. Short
    on purpose: the label cuts at 48 characters, which hid this on every shipped example."""
    url = serve(SHORT_SUGGESTION, anchored=[("now", "Retry three times")])
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Vacuous otherwise: the slot the label is read from has to carry the comment.
    expect_comment_notes(page, "lf-new #now", 1)
    control = page.locator(f"[data-lf-margin-for='sug'] .lf-sug-{outcome}")
    (unfolded_button(control) if folded else control).click()
    expect(page.locator(".lf-live")).to_have_text(
        f"{verb} suggested change: Retry three times."
    )
    expect(page.locator(".lf-notice")).to_have_text("")
    expect(page.locator(".lf-notice")).not_to_have_class(re.compile(r"\bshow\b"))


def test_a_decided_change_folds_away_rather_than_vanishing(browser, serve):
    """A decision may move the page; it may not teleport it.

    A block change is a struck old paragraph stacked over a tinted new one, and
    accepting used to drop the old one with `display: none` in the frame of the press —
    179 measured pixels out of the middle of the shipped design page, with everything
    below jumping up under the pointer that had just pressed. The rule this layer
    already carries is that a change the user asked for may move the page and must do
    it as motion, because motion is the form the eye can follow to where the sentence
    went.

    Held at its first frame rather than sampled mid-flight, which would be a race with
    the clock and would pass on a fast machine either way: the fold is read where it
    starts (the slot's own height, not zero), stepped to the middle, and then let go, so
    what the test proves is the shape of the motion and not how long the run took.

    An inline change is the test below: it has nothing to follow, and folding one would
    be the harm rather than the fix."""
    page = open_page(browser, serve(SHORT_SUGGESTION), init_script=HOLD_MOTION)
    old = page.locator("#sug lf-old")
    after = page.locator("#after")
    tall = old.evaluate("el => el.getBoundingClientRect().height")
    assert tall > 0
    below = after.evaluate("el => el.getBoundingClientRect().top")

    page.locator("[data-lf-margin-for='sug'] .lf-sug-accept").click()
    # The state lands in the frame of the press. Its fold then carries the pixels toward
    # that already-current reading while the outbox carries it toward the log.
    expect(page.locator("#sug[data-lf-state='accept']")).to_have_count(1)
    held = page.evaluate(
        """() => window.__lfHeld.map((m) => [m.effect.target.tagName.toLowerCase(),
                                             m.effect.getTiming().duration])"""
    )
    assert [t for t, _ in held] == ["lf-old"], (
        f"the retired slot went without motion to follow: {held}"
    )
    at = "() => document.querySelector('#sug lf-old').getBoundingClientRect().height"
    assert page.evaluate(at) == pytest.approx(tall, abs=1), (
        "the fold begins somewhere other than where the paragraph was standing"
    )
    page.evaluate(
        "() => { const m = window.__lfHeld[0];"
        "        m.currentTime = m.effect.getTiming().duration / 2; }"
    )
    middle = page.evaluate(at)
    assert 0 < middle < tall, f"the fold's midpoint is not between its ends: {middle}"

    # The endpoint is part of the motion, not a scheduling gap the finish handler has
    # to beat. Read it synchronously at the exact duration: without a forwards fill the
    # effect has already stopped applying here and the slot springs back to its
    # unanimated height before cleanup gets its turn.
    endpoint = page.evaluate(
        """() => {
          const m = window.__lfHeld[0];
          m.currentTime = m.effect.getTiming().duration;
          return {
            height: m.effect.target.getBoundingClientRect().height,
            opacity: Number(getComputedStyle(m.effect.target).opacity),
            fill: m.effect.getTiming().fill,
          };
        }"""
    )
    assert endpoint["height"] == pytest.approx(0, abs=0.1), (
        f"the fold exposed its unanimated box at the endpoint: {endpoint}"
    )
    assert endpoint["opacity"] == pytest.approx(0, abs=0.001), (
        f"the fold exposed its unanimated ink at the endpoint: {endpoint}"
    )

    page.evaluate("() => window.__lfHeld[0].finish()")
    expect(old).to_be_hidden()
    page.wait_for_function(
        "() => document.querySelector('#sug lf-old').getAnimations().length === 0"
    )
    assert after.evaluate("el => el.getBoundingClientRect().top") < below, (
        "the page never gave back the room the retired paragraph was holding"
    )


def test_an_inline_change_is_swapped_rather_than_folded(browser, serve):
    """The other half of the rule above, and the half where folding would be the harm.

    A height to animate means a `display: block` held over the slot for the duration, so
    a few words swapped mid-sentence would open a paragraph break and close it again —
    motion answering a change that moved nothing. The shipped inline corpus is the case,
    and what it asserts is that nothing was started at all."""
    page = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a few words swapped inside a line were given a fold, and a block box to do it in"
    )


def test_a_user_who_asked_for_less_motion_gets_the_collapse_at_once(browser, serve):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the same bargain the board's own FLIP makes.

    Asked of the context rather than of the page, because the runtime reads the
    preference once as it loads: emulating it afterwards changes what the media query
    would answer and not what the module already recorded."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(
        browser, serve(SHORT_SUGGESTION), context=context, init_script=HOLD_MOTION
    )
    page.locator("[data-lf-margin-for='sug'] .lf-sug-accept").click()
    expect(page.locator("#sug lf-old")).to_be_hidden()
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a user who asked for less motion was given a fold to sit through"
    )


def test_accept_all_decides_every_pending_suggestion(browser, serve):
    """The banner's button is a shortcut for the user who has read the page
    and wants all of it, so it has to reach the ones their eye didn't: the
    suggestion inside a widget, whose controls stand on the widget as a pin rather
    than in the rail. Each is decided individually, so the log records what was
    consented to one change at a time rather than one blanket yes."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    answer_all = page.locator(".lf-answer-all")
    expect(answer_all).to_have_text("Accept all (3)")
    page.evaluate(
        "button => { window.__lfAnswerAll = button; }", answer_all.element_handle()
    )

    # The same public control survives a semantic change, and its later press resolves
    # the current open inventory rather than replaying the list from its earlier face.
    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    expect(
        page.locator("[data-lf-margin-for='sug-refill']").get_by_role(
            "button", name=re.compile(r"^Undo accepting")
        )
    ).to_be_enabled()
    expect(answer_all).to_have_text("Accept all (2)")
    assert answer_all.evaluate("button => button === window.__lfAnswerAll")
    banner_control(page, ".lf-answer-all").click()

    for widget in ("sug-refill", "sug-thistle", "sug-in-card"):
        expect(page.locator(f"#{widget} lf-new")).to_be_visible()
        # Waited for, not read once: each is decided by its own round trip, so the
        # last of them is still in flight when the first has settled. Undo stands
        # disabled while the decision it takes back is in the wire, so an enabled
        # one is this row's own answer come back.
        undo_button = page.locator(f"[data-lf-margin-for='{widget}']").get_by_role(
            "button", name=re.compile(r"^Undo accepting")
        )
        expect(undo_button).to_be_visible()
        expect(undo_button).to_be_enabled()
        expect(
            page.locator(f"[data-lf-margin-for='{widget}'] .lf-margin-receipt")
        ).to_have_count(0)
    for widget in (
        "sug-refill",
        "sug-in-card",
    ):  # the two that replace rather than insert
        expect(page.locator(f"#{widget} lf-old")).to_be_hidden()
    # Nothing left to accept, so the button says nothing rather than saying zero.
    expect(page.get_by_role("button", name=re.compile("Accept all"))).to_be_hidden()

    # Every decision above is settled; this is the boundary for a stray post the
    # sequence below would otherwise read as absent.
    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["detail"].get("outcome", e["action"])) for e in logged] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ]


def test_a_refused_decision_returns_to_pending_with_failure_controls(
    held_events, serve
):
    """The reversible result paints immediately, then refusal restores the offer."""
    browser, held = held_events
    page = open_page(browser, serve(SUGGESTION_PAGE))
    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()

    holding(page, held, 1, "the accepted suggestion")
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    pending_item = page.locator('[data-lf-margin-for="sug-refill"]')
    expect(pending_item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(pending_item.get_by_text("Accepted", exact=True)).to_have_count(0)

    held.pop(0).fulfill(
        status=400,
        json={
            "ok": False,
            "error": "refused before append",
            "final": True,
        },
    )
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert page.locator("#sug-refill").get_attribute("data-lf-state") is None
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    expect(item).to_have_attribute("data-lf-state", "failed")
    expect(item.locator(".lf-margin-more")).to_be_hidden()
    expect(item.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Details", exact=True)).to_have_count(0)
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    item.get_by_role("button", name="Cancel", exact=True).click()
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(item.locator(".lf-sug-accept")).to_be_focused()
    item.locator(".lf-sug-accept").click()
    holding(page, held, 1, "the repeated accepted suggestion")
    held.pop(0).fulfill(
        status=400,
        json={
            "ok": False,
            "error": "refused before append",
            "final": True,
        },
    )
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    # And the page's own count is derived from that, so it comes back too.
    expect(page.locator(".lf-answer-all")).to_have_text("Accept all (3)")
    expect_banner_control_offered(page.locator(".lf-answer-all"))
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")
    assert [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []

    # Retry starts a fresh attempt without reloading or pretending the failed one won.
    page.unroute("**/api/event")
    item.get_by_role("button", name="Retry", exact=True).click()
    round_trip(page)
    logged = actions(serve.page_dir)
    assert [
        (event["widget"], event["detail"].get("outcome", event["action"]))
        for event in logged
    ] == [("sug-refill", "accept")]
    assert logged[0]["attempt"]
    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    consume_browser_errors(page, "400")


def test_an_ambiguous_decision_stays_one_gesture_while_retrying(browser, serve):
    """Losing an accepted action answer keeps the original press busy and retries
    that exact attempt. Repeating the press cannot mint a second decision that one
    undo would merely uncover."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    requests = []
    accepted = []

    def lose_first_answer(route):
        requests.append(route.request.post_data_json)
        if len(requests) == 1:
            accepted.append(route.fetch().status)
            refuse(route)
        else:
            route.continue_()

    # Force recovery through the outbox rather than letting a periodic read observe
    # the accepted attempt first. Both are valid recovery paths; this one proves the
    # retry reuses the identity whose answer was lost.
    page.route("**/api/state*", refuse)
    page.route("**/api/event", lose_first_answer)
    accept = page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept")
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/event" in request.url
    ):
        accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(page.locator(".lf-notice")).to_contain_text("retrying your change")

    expect(accept).to_have_count(0)
    expect(
        page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-reject")
    ).to_have_count(0)
    holding(page, requests, 2, "the retried decision")
    assert accepted == [200]
    assert len(requests) == 2
    assert len({request["attempt"] for request in requests}) == 1
    assert [
        (event["widget"], event["detail"].get("outcome", event["action"]))
        for event in actions(serve.page_dir)
    ] == [("sug-refill", "accept")]

    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()


def test_a_pending_suggestion_decision_records_one_action(browser, serve):
    """One press replaces both verdicts and records the accepted decision once."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    row = page.locator("[data-lf-margin-for='sug-refill']")
    row.locator(".lf-sug-accept").click()
    holding(page, held, 1, "the decision")
    expect(row.locator(".lf-sug-accept")).to_have_count(0)
    expect(row.locator(".lf-sug-reject")).to_have_count(0)
    pending_undo = row.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(pending_undo).to_be_visible()
    assert len(held) == 1

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#sug-refill[data-lf-state='accept']")).to_have_count(1)
    assert [
        (e["widget"], e["detail"].get("outcome", e["action"]))
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [("sug-refill", "accept")]


def test_an_optimistic_decision_stays_plain_while_delivery_waits(held_events, serve):
    """A held send leaves the settled content legible and its Undo in place."""
    browser, held = held_events
    page = open_page(browser, serve(SUGGESTION_PAGE))
    accept = page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept")
    resting = accept.bounding_box()
    accept.click()
    holding(page, held, 1, "the accepted suggestion")

    suggestion = page.locator("#sug-refill")
    expect(suggestion.locator("lf-old")).to_be_hidden()
    expect(suggestion.locator("lf-new")).to_be_visible()
    expect(suggestion).not_to_have_attribute("aria-busy", "true")
    expect(suggestion).to_have_css("opacity", "1")
    pending_undo = page.locator("[data-lf-margin-for='sug-refill']").get_by_role(
        "button", name=re.compile(r"^Undo accepting")
    )
    assert pending_undo.bounding_box() == resting

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#sug-refill[data-lf-state='accept']")).to_have_count(1)
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")


def test_a_decision_travels_between_tabs_and_the_log_has_the_last_word(browser, serve):
    """Two windows on one page are two views of one log, not two documents. A
    decision taken in either arrives in the other by the same replay that keeps a
    reload's drag, and the record it leaves in the margin has to arrive with it: the
    tab that receives one settles it without the click that settled the tab that sent
    it, and a row still offering the press is a window disagreeing with the log about
    what has already been decided. Where the two disagree, the later entry in the log
    is what both end on."""
    url = serve(SUGGESTION_PAGE)
    first = open_page(browser, url)
    second = open_page(browser, url)

    # A tab that did not click has only its own poll to learn from.
    first.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    told(second)
    expect(second.locator("#sug-refill lf-old")).to_be_hidden()
    expect(second.locator("#sug-refill lf-new")).to_be_visible()
    # Nothing is left to decide. Replay replaces both offers with the existing Undo
    # action without adding a second status beside the settled content.
    row = second.locator("[data-lf-margin-for='sug-refill']")
    accepted = row.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(accepted.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "undo"
    )
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(accepted).to_be_enabled()
    # Its pair leaves; the surviving content and Undo carry the settled state.
    rejected = second.locator("[data-lf-margin-for='sug-refill'] .lf-sug-reject")
    expect(rejected).to_be_hidden()
    expect(second.locator(".lf-answer-all")).to_have_text("Accept all (2)")
    expect_banner_control_offered(second.locator(".lf-answer-all"))

    # Now the race the controls make possible: a window cut off from the log still
    # shows both buttons, so the user can decide the other way there. Two
    # decisions on one change, and the log's order — not either tab's belief —
    # settles it for both once the cut-off one catches up.
    third = open_page(browser, url)
    cut = CutOff().hold(third)
    first.locator("[data-lf-margin-for='sug-thistle'] .lf-sug-accept").click()
    # In the log before the reject is clicked, so which one is later is this test's
    # to decide rather than the network's.
    told(second)
    expect(second.locator(".lf-answer-all")).to_have_text("Accept all (1)")
    expect_banner_control_offered(second.locator(".lf-answer-all"))
    unfolded_button(
        third.locator("[data-lf-margin-for='sug-thistle'] .lf-sug-reject")
    ).click()
    cut.restore()
    # The reject went out over a live channel, so every tab has to read it back —
    # the cut-off one included, which is where it stops being its own local click.
    for tab in (first, second, third):
        told(tab)
        expect(tab.locator("#sug-thistle lf-new")).to_be_hidden()


def test_the_ask_reading_counts_completed_asks_against_the_active_total(browser, serve):
    """Two semantic readings, collected from declarations rather than from any tag.

    The count used to be a query for `lf-suggestion:not([data-lf-state])`: perfect for
    suggestions, and silently nothing for every other thing a page waits on. What
    makes an instance an Ask is now the entry's own attribute condition, and the entry
    explicitly names which state verbs answer it — so this page's five active Asks are
    one authored answer, a live question, a change nobody has decided, and two explicit
    questions nested in tasks.

    The rest of the page is every way of not being one, and each was a way of getting
    it wrong: a group whose pick the version already carries (`chosen`, with nothing in
    the log — a fold-only reading counts it as open on every shipped example), one the
    author has settled, one that takes no picks at all, an exhibited decision inside a
    lf-sample, and a milestone at `blocked`, which is the same word on a widget whose
    entry does not declare it."""
    page = open_page(browser, serve(ASKS_PAGE))
    expect_asks_answered(page, "1/5")
    # The blanket answer counts the same list, narrowed to the one kind that declares
    # a verb for it, so the two numbers cannot describe different sets.
    expect(page.locator(".lf-answer-all")).to_have_text("Accept all (1)")

    # Answering advances the numerator without erasing the denominator. A pick is state
    # the page itself carries, so the count follows the click; the suggestion's outcome
    # is in the log alone, so that one follows the round trip.
    page.locator("#lq-token").click()
    expect_asks_answered(page, "2/5")
    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    expect_asks_answered(page, "3/5")
    expect_banner_control_offered(page.locator(".lf-answer-all"), offered=False)

    # And clearing the pick asks again: an empty answer is no answer, which only a
    # reading of what the page carries can say.
    page.locator("#lq-token").click()
    expect_asks_answered(page, "2/5")


def test_a_key_walks_the_page_s_open_asks(browser, serve):
    """t/T step the open threads; a/A step the things the page is waiting on the user
    for. The category letter stays under one finger: lowercase advances and Shift goes
    back. Both walks repeat when held because walking often takes several presses.
    Both clamp at the ends like every other one-dimensional list, so another press keeps
    the user on the edge instead of jumping across the page.

    The landing is marked on the ask and stands the user on it, which is the same
    element the scroll has just brought to the top of the window — a walk that landed the
    control instead put them on whatever the decision's context and evidence had pushed
    off the bottom of the screen. Its contributed actions are directly addressable there;
    the controls themselves remain the next Tab stops."""
    page = open_page(browser, serve(ASKS_PAGE))
    expect_asks_answered(page, "1/5")
    walked = []
    for expected in [*ASKS_IN_ORDER, ASKS_IN_ORDER[-1]]:
        page.keyboard.press("a")
        # The ring is painted from the focus, in the frame after the press, so waiting
        # for it on the Ask this press stepped to is both the wait and the assertion —
        # a bare count would pass on the ring an earlier press left standing.
        expect(page.locator(f"#{expected}[data-lf-ask]")).to_have_count(1)
        # And exactly one decision wears it, the user standing in one place at a time.
        expect(page.locator(STANDING_ASK)).to_have_count(1)
        # Walking changes the ring and not the durable progress count.
        expect_asks_answered(page, "1/5")
        walked.append(page.evaluate("document.activeElement.id"))
    assert walked == [
        *ASKS_IN_ORDER,
        ASKS_IN_ORDER[-1],
    ], f"the walk landed on something else: {walked}"

    # And back, including one press past the first edge. The step off a suggestion is
    # measured from the suggestion rather than from the ✓ Accept holding the focus —
    # that row is hoisted out into the page margin as a sibling of the block it decides,
    # so a walk reading it where it hangs would step back onto the change the user is
    # standing on.
    for expected in [*reversed(ASKS_IN_ORDER[:-1]), ASKS_IN_ORDER[0]]:
        page.keyboard.press("Shift+a")
        expect(page.locator(f"#{expected}[data-lf-ask]")).to_have_count(1)
        expect(page.locator(STANDING_ASK)).to_have_count(1)
        expect_asks_answered(page, "1/5")

    # Every request has an answering control, so the walk never has to leave a borrowed
    # tab stop on an Ask it has left. A generated custom element may now be the public
    # role-bearing control itself, so a dash in its tag no longer means authored widget
    # paint. Ask ids are the exact ownership boundary this assertion is about; the
    # currently standing Ask alone may retain the stop that focus is using.
    expect(page.locator(STANDING_ASK)).to_have_count(1)
    assert (
        page.evaluate(
            "ids => ids.filter(id => {"
            "  const ask = document.getElementById(id);"
            "  return ask.hasAttribute('tabindex') && !ask.hasAttribute('data-lf-ask');"
            "})",
            ASKS_IN_ORDER,
        )
        == []
    ), "a lent tab stop was left on a decision the user has walked off"

    # The overlay and the shortcut bar offer it because there is something to reach.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text(
        "thread or move to resend waiting on you"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("on you")

    # Leaving the ask takes the place off the count the way it takes the ring off the
    # page: a click into the prose is the user standing nowhere in the list.
    page.locator("#h").click()
    expect(page.locator(STANDING_ASK)).to_have_count(0)
    expect_asks_answered(page, "1/5")

    # An answered decision leaves the walk: deciding the change on its own control is where
    # the user now stands, and the next press reaches what followed it rather than the
    # change they have just settled. The control the user answered from keeps the
    # focus. It leaves the open walk while the completed/total count advances.
    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    expect_asks_answered(page, "2/5")
    page.keyboard.press("a")
    expect(page.locator("#t-baffles-decision[data-lf-ask]")).to_have_count(1)
    expect(page.locator("#t-baffles-decision")).to_be_focused()
    expect_asks_answered(page, "2/5")


def test_an_ask_the_user_stands_on_survives_the_window_losing_focus(browser, serve):
    """Another app taking key focus for a moment, such as macOS verifying a newly
    installed binary, blurs the Ask the user stands on but leaves it the document's
    focused area, and the browser puts them back on it when the window returns. The tab
    stop the walk lent the Ask is held through that blur. Taking it back made the Ask
    unfocusable while focused, the browser dropped the user to the body, and the window
    came back with them standing nowhere.

    Headless Playwright cannot take system focus from its window, so the test delivers
    the platform's blur at the Ask while it stays the focused area, which is what the
    window losing focus does."""
    page = open_page(browser, serve(ASKS_PAGE))
    first = page.locator(f"#{ASKS_IN_ORDER[0]}")
    page.keyboard.press("a")
    expect(first).to_be_focused()
    first.evaluate("ask => ask.dispatchEvent(new FocusEvent('blur'))")
    expect(first).to_be_focused()
    expect(first).to_have_attribute("tabindex", "-1")

    # Moving off within the page still gives the stop back.
    page.keyboard.press("a")
    expect(page.locator(f"#{ASKS_IN_ORDER[1]}")).to_be_focused()
    expect(first).not_to_have_attribute("tabindex", re.compile(".*"))


def test_an_ask_arrival_starts_with_the_context_that_frames_it(browser, serve):
    """The decision is the question's whole reading region, not only its answer control.

    An options group used to be both the state owner and the navigation target. When
    the heading, premise, and evidence stood immediately above it, `d` centred the
    options and made the user scroll backward before they could answer. `lf-ask`
    encodes that broader unit while the nested x-awaits widget still owns the action:
    the walk rings the region, aligns its opening below the banner, and stands the
    user on it.

    On it, and not on the control that answers it, which was where the walk landed until
    the scroll and the focus were measured against each other. The scroll puts the
    region's opening at the top of the window and the answering control is as far down as
    the context and evidence are long: on the shipped corpus at 1200x900 the heading stood
    at 54px and the focused pick ran from 847 to 1107 in a 900px window, so the user was
    told to look at one thing while standing on another they could not see, and their next
    Space would have worked it. The picks are the next Tab stops instead, which is what a
    stop at `tabindex: -1` on the region buys: it keeps its place in document order and
    everything inside the decision comes after it.
    """
    page = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    # Short enough that even the pick in the card's compact header falls past the foot of
    # the window once the decision's opening is at its head, which is the shape the fault
    # has: the walk cannot both show the question and stand the user on its answer.
    resized(page, 900, 230)

    # The options really do begin below context, and enough page follows the region for
    # aligning its start to be possible. Without either condition, centring the inner
    # widget could happen to look like the requested arrival.
    before = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-decision').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          return {context: options.top - ask.top,
                  room: document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight};
        }"""
    )
    assert before["context"] > 100, (
        "the fixture has no meaningful context above the options"
    )
    assert before["room"] > 500, "the page has no room to put the decision at its start"

    page.keyboard.press("a")
    expect(page.locator("#storage-decision")).to_be_focused()
    expect(page.locator("#storage-decision")).to_have_attribute("data-lf-ask", "1")
    expect(page.locator("#storage-options")).not_to_have_attribute("data-lf-ask", "1")
    scroll_settled(page)
    # Where the user was left is on the screen the walk has just arranged, and the pick
    # the walk used to stand them on is the measurement that says the two cannot both be.
    standing = page.evaluate(
        """() => {
          const box = document.activeElement.getBoundingClientRect();
          const pick = document.querySelector('#storage-options .lf-pick')
            .getBoundingClientRect();
          return {top: box.top, pick: pick.top, height: innerHeight};
        }"""
    )
    assert standing["pick"] > standing["height"], (
        f"the first pick is on screen at this size, so standing on it would have been no "
        f"worse than standing on the Ask and nothing below is evidence: {standing}"
    )
    assert 0 <= standing["top"] < standing["height"], (
        f"the walk left the user standing off the screen it had just scrolled: "
        f"{standing}"
    )
    landed = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-decision').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          // Below the banner, and the room the Ask's ring takes above it.
          const clear = parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)
            + parseFloat(getComputedStyle(document.getElementById('storage-decision'))
              .scrollMarginTop);
          return {ask: ask.top, options: options.top, clear};
        }"""
    )
    assert abs(landed["ask"] - landed["clear"]) <= 2, (
        f"the Ask starts at {landed['ask']:.1f}px instead of below the banner and its "
        f"ring's room at {landed['clear']:.1f}px"
    )
    assert landed["options"] > landed["ask"] + 100, (
        "the arrival did not leave the Ask's context above its options"
    )

    # Tab remains the complementary route into the widget's controls. Read after the
    # landing above, because a Tab onto a control below the fold scrolls to it and would
    # take the arrival's own geometry with it. The Ask action context remains the same;
    # its key badges may move to the shared chrome when Linux font metrics leave a local
    # badge clipped, but the controls retain the same semantic routes.
    page.keyboard.press("Tab")
    expect(page.locator("#storage-options .lf-pick").first).to_be_focused()
    picks = page.locator("#storage-options .lf-pick")
    expect(picks.nth(0)).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space 1"
    )
    expect(picks.nth(1)).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space 2"
    )

    # And nothing of the borrowed stop is left behind: PAGE_PAINT_ATTRIBUTES is the whole
    # of what the runtime may leave on an author's element, and `tabindex` is not in it.
    page.keyboard.press("Escape")
    expect(page.locator("#storage-decision")).not_to_have_attribute("tabindex", "-1")


def test_the_ask_itself_binds_each_contributed_action(browser, serve):
    """a lands semantic focus on the Ask; digits work its exact action list there.

    The list is contributed by the decision widget rather than inferred from generated
    descendants: options own controls inside the Ask, while a suggestion's margin entries are
    hoisted into the shared margin. Each widget declares the aliases forwarded by
    the keyboard layer; a digit activates the original command without first moving
    focus into the widget.
    """
    page = open_page(browser, serve(ASKS_PAGE))
    resized(page, 900, 900)

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision")).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    expect(
        page.locator(
            "#live-question > lf-option > .lf-key-badge[data-lf-binding-badge]"
        )
    ).to_have_text(["1", "2"])

    page.keyboard.press("2")
    expect(page.locator("#lq-token")).to_have_attribute("chosen", "")
    round_trip(page)
    expect_asks_answered(page, "2/5")

    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_be_focused()
    assert active_digit_bindings(page) == "1–2"
    expect(
        page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept")
    ).to_have_attribute("aria-keyshortcuts", "1")
    expect(
        page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-reject")
    ).to_have_attribute("aria-keyshortcuts", "2")
    page.keyboard.press("2")
    round_trip(page)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")


def test_ask_contextual_bindings_are_independent_of_widget_bindings(browser, serve):
    """An Ask digit aliases a command without replacing its focused widget binding."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    resized(page, 900, 900)

    page.evaluate(
        """async () => {
          const {commands} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const suggestion = document.getElementById('sug');
          const source = document.createElement('span');
          const inspect = document.createElement('button');
          inspect.id = 'inspect-action';
          inspect.textContent = 'Inspect';
          source.append(inspect);
          suggestion.append(source);
          commands(source, 'Suggestion action', [
            {
              id: 'test.inspect',
              keys: ['x', 'y'], contextKeys: ['3'],
              control: inspect, bindingBadge: null,
              label: 'I',
              decision: true,
              title: 'Inspect',
              line: 'Inspect',
              run: () => { inspect.dataset.activated = '1'; },
            },
          ]);
        }"""
    )

    # The source scope keeps its intrinsic presentation in the global reference.
    page.keyboard.press("?")
    page.keyboard.press("?")
    inspect_reference = page.locator(
        '.lf-command-reference tr[data-lf-command="test.inspect"]'
    )
    expect(inspect_reference.locator("kbd")).to_have_text("I")
    expect(inspect_reference.locator(".lf-binding-sequence")).to_have_attribute(
        "aria-label", "I"
    )
    page.keyboard.press("Escape")

    inspect = page.get_by_role("button", name="Inspect")
    page.keyboard.press("a")
    expect(page.locator("#sug")).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    expect(inspect).to_have_attribute("aria-keyshortcuts", "3")
    rendered(page)
    assert sorted(
        page.locator(
            ".lf-command-binding-badges > .lf-command-binding-badge"
        ).all_text_contents()
    ) == ["1", "2", "3"]

    # The Ask's third route invokes the original command. Once the command's own control
    # is focused, both equivalent intrinsic bindings and the independent Ask digit remain
    # reachable routes to that command.
    page.keyboard.press("3")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")
    inspect.focus()
    rendered(page)
    assert set(inspect.get_attribute("aria-keyshortcuts").split()) == {"x", "y", "3"}
    assert "I\nInspect" in shortcut_bar_text(page)
    rendered(page)
    assert sorted(
        page.locator(
            ".lf-command-binding-badges > .lf-command-binding-badge"
        ).all_text_contents()
    ) == ["1", "2", "3"]
    page.keyboard.press("y")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")

    # A nearer dead declaration removes only x. The route snapshot keeps y rather than
    # collapsing the command's equivalent bindings into whichever one came first.
    page.evaluate(
        """async () => {
          const {commands} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const inspect = document.getElementById('inspect-action');
          commands(inspect, 'Inspect control', [{
            id: 'test.dead-local-x', keys: ['x'],
            title: 'Run an unavailable local command',
            line: 'unavailable local command', when: () => false,
            run: () => { inspect.dataset.deadLocalX = '1'; },
          }]);
        }"""
    )
    rendered(page)
    assert set(inspect.get_attribute("aria-keyshortcuts").split()) == {"y", "3"}
    assert "y\nInspect" in shortcut_bar_text(page)
    page.keyboard.press("x")
    expect(inspect).not_to_have_attribute("data-dead-local-x", "1")
    expect(inspect).not_to_have_attribute("data-activated", "1")
    page.keyboard.press("y")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")
    page.keyboard.press("3")
    expect(inspect).to_have_attribute("data-activated", "1")

    # The complete reference preserves the command's keycap override while its
    # contextual and intrinsic bindings still refer to one command identity.
    page.keyboard.press("?")
    page.keyboard.press("?")
    focused_inspect = page.locator(
        '.lf-command-reference tr[data-lf-command="test.inspect"]'
    )
    expect(focused_inspect.locator("kbd")).to_have_text("I")


def test_a_widget_digit_shadows_only_the_matching_ask_alias(browser, serve):
    """A focused widget digit suppresses its Ask alias without taking other digits."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    page.evaluate(
        """async () => {
          const {commands} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const suggestion = document.getElementById('sug');
          const inspect = document.createElement('button');
          inspect.textContent = 'Inspect';
          suggestion.append(inspect);
          commands(inspect, 'Inspect control', [
            {
              id: 'test.inspect', keys: ['1'], contextKeys: ['3'], control: inspect, label: 'I',
              decision: true, title: 'Inspect', line: 'Inspect',
              run: () => { inspect.dataset.activated = '1'; },
            },
            {
              id: 'test.local-three', keys: ['3'],
              title: 'Run the local third command', line: 'local three',
              run: () => { inspect.dataset.localThree = '1'; },
            },
          ]);
        }"""
    )

    inspect = page.get_by_role("button", name="Inspect")
    page.keyboard.press("a")
    # The control's own scope names its keys wherever the user stands; the Ask adds
    # the widget's explicitly declared digit that reaches it from the Ask.
    expect(inspect).to_have_attribute("aria-keyshortcuts", "1 3")
    inspect.focus()
    expect(inspect).to_have_attribute("aria-keyshortcuts", "1 3")
    expect(
        page.locator(".lf-command-binding-badges > .lf-command-binding-badge")
    ).to_have_text(["2"])
    page.keyboard.press("1")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")
    page.keyboard.press("3")
    expect(inspect).to_have_attribute("data-local-three", "1")
    expect(inspect).not_to_have_attribute("data-activated", "1")


def test_an_ask_alias_runs_the_original_command_in_its_own_scope(browser, serve):
    """A projected digit enters through the widget command's own declaration, and the
    layer it opens declares its own way out.

    Nothing records which press opened the layer: Escape reads the layer standing in
    front of the user, so the widget owning it owns the step that takes it off, and
    that step is the same one whether the digit, the control, or a Tab put the user
    inside."""
    page = open_page(browser, serve(SHORT_SUGGESTION))

    page.evaluate(
        """async () => {
          const { commands } = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const suggestion = document.getElementById('sug');
          const control = document.createElement('button');
          control.textContent = 'Configure';
          const layer = document.createElement('div');
          layer.id = 'test-command-layer';
          layer.hidden = true;
          const inside = document.createElement('button');
          inside.textContent = 'Inside configuration';
          layer.append(inside);
          suggestion.append(control, layer);
          commands(control, 'Configuration action', [{
            id: 'test.configure', keys: [], contextKeys: ['3'], control,
            decision: true, title: 'Configure', line: 'configure',
            run: () => { layer.hidden = false; inside.focus(); },
          }]);
          commands(inside, 'In the configuration layer', [{
            id: 'test.configure.close', keys: ['Escape'],
            title: 'Close configuration', line: 'close configuration',
            run: () => { layer.hidden = true; control.focus(); },
          }]);
        }"""
    )

    page.keyboard.press("a")
    expect(page.locator("#sug")).to_be_focused()
    page.keyboard.press("3")
    expect(page.get_by_role("button", name="Inside configuration")).to_be_focused()
    assert "close configuration" in shortcut_bar_text(page)
    page.keyboard.press("Escape")
    expect(page.locator("#test-command-layer")).to_be_hidden()
    expect(page.get_by_role("button", name="Configure")).to_be_focused()


def test_command_title_functions_must_return_text(browser, serve):
    """Computed row and route names fail with the command-scoped contract error."""
    page = open_page(browser, serve(SHORT_SUGGESTION))

    messages = page.evaluate(
        """async () => {
          const {decisionControls} = await window.__lfRuntimeImport('/runtime/keyboard/bindings.js');
          const source = document.getElementById('sug');
          const control = document.createElement('button');
          source.append(control);
          const read = (row) => {
            try {
              decisionControls([{source, row}], 'the test Ask');
            } catch (error) {
              return error.message;
            }
            return null;
          };
          return {
            row: read({
              id: 'test.invalid-row-name', keys: [], control,
              decision: true, title: () => true,
            }),
            route: read({
              id: 'test.route-family', keys: ['ArrowLeft'], title: 'Inspect', control,
              routes: [{
                id: 'test.invalid-route-name', binding: 'ArrowLeft',
                decision: true, title: () => true,
              }],
            }),
          };
        }"""
    )

    assert "test.invalid-row-name" in messages["row"]
    assert "test.invalid-route-name" in messages["route"]
    assert "title" in messages["row"]
    assert "title" in messages["route"]


def test_ask_action_binding_badges_use_the_available_card_action_seats(browser, serve):
    """The draft route borrows an empty Add seat and moves beside a live Add press.

    The cards share one trailing column. An empty draft has only the route into its
    field, so that badge sits over the hidden Add press. Once content reveals Add and
    focus leaves the field, both actions are available and the route takes the inner
    seat. The field reserves both seats before either face appears.
    """
    page = open_page(browser, serve(ASKS_PAGE))
    resized(page, 900, 900)

    page.keyboard.press("a")
    selector = (
        "#live-question > :is(lf-option, .lf-another) "
        "> .lf-key-badge[data-lf-binding-badge]"
    )
    ask = page.locator(selector)
    expect(ask).to_have_text(["1", "2", "3"])
    centers = """nodes => nodes.map(node => {
          const box = node.getBoundingClientRect();
          return {x: box.left + box.width / 2, y: box.top + box.height / 2 + scrollY,
                  right: box.right};
        })"""
    ask_centers = ask.evaluate_all(centers)
    addition = page.locator("#live-question > .lf-another")
    submit = addition.locator(".lf-compose-submit")
    empty_submit = submit.evaluate(
        """el => { const box = el.getBoundingClientRect();
                    return {x: box.left + box.width / 2}; }"""
    )
    assert ask_centers[-1]["x"] == pytest.approx(empty_submit["x"], abs=0.5)

    page.keyboard.press("Tab")
    focused = page.locator(selector)
    expect(focused).to_have_text(["1", "2", "3"])
    focused_centers = focused.evaluate_all(centers)
    assert len(ask_centers) == len(focused_centers) == 3
    assert len({round(point["x"], 1) for point in ask_centers[:-1]}) == 1
    for ask_point, focused_point in zip(ask_centers, focused_centers, strict=True):
        assert ask_point["x"] == pytest.approx(focused_point["x"], abs=0.5)
        assert ask_point["y"] == pytest.approx(focused_point["y"], abs=0.5)

    # The Add press must enter the tab order in the input event itself. A paint on
    # the next frame can come after the next Tab and send focus to the next Ask.
    page.evaluate("""() => document.addEventListener('input', () => {
      window.__addEmptyAtInput = document.querySelector(
        '#live-question .lf-compose-submit').hasAttribute('data-lf-empty');
    }, {once: true})""")
    write(addition.get_by_role("textbox", name="Another option"), "A fourth option")
    assert page.evaluate("window.__addEmptyAtInput") is False
    page.keyboard.press("Tab")
    binding_badge = addition.locator("> .lf-key-badge[data-lf-binding-badge]")
    expect(binding_badge).to_be_visible()
    expect(submit).to_be_visible()
    badge_box = binding_badge.bounding_box()
    submit_box = submit.bounding_box()
    assert badge_box is not None
    assert submit_box is not None
    # The press remains in the seat the empty badge borrowed. With both actions now live,
    # the write badge takes the adjacent seat at the form's declared action gap.
    assert submit_box["x"] + submit_box["width"] > ask_centers[0]["right"]
    assert submit_box["x"] + submit_box["width"] / 2 == pytest.approx(
        empty_submit["x"], abs=0.5
    )
    gap = submit_box["x"] - badge_box["x"] - badge_box["width"]
    expected_gap = page.locator("html").evaluate(
        "el => parseFloat(getComputedStyle(el).getPropertyValue('--sp-2'))"
    )
    assert gap == pytest.approx(expected_gap, abs=0.5)
    expect(
        page.locator(".lf-command-binding-badges > .lf-command-binding-badge")
    ).to_have_count(0)


def test_ask_actions_replace_unusable_package_binding_badge_faces(browser, serve):
    """Disconnected, shared, covered, and clipped faces use core binding badges."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    resized(page, 900, 900)

    page.evaluate(
        """async () => {
           const {commands} = await window.__lfRuntimeImport('/runtime/widget-api.js');
           const source = document.getElementById('sug');
           const face = (id, top) => {
             const bindingBadge = document.createElement('span');
             bindingBadge.id = id;
             bindingBadge.className = 'lf-key-badge';
             bindingBadge.style.cssText = `position: fixed; left: 90px; top: ${top}px;`;
             return bindingBadge;
           };
           let nextKey = 3;
           const add = (id, top, bindingBadge) => {
             const control = document.createElement('button');
            control.id = id;
            control.textContent = id;
            control.style.cssText = `position: fixed; left: 560px; top: ${top}px;`;
            source.append(control);
            commands(control, id, [{
               id: `test.${id}`, keys: [], contextKeys: [String(nextKey++)], control, bindingBadge,
              decision: true, title: `Activate ${id}`, line: id,
              run: () => { control.dataset.activated = '1'; },
            }]);
          };

           add('disconnected-face', 220, face('detached-binding-badge', 100));
           const shared = face('shared-binding-badge', 120);
          source.append(shared);
          add('shared-face-one', 300, shared);
          add('shared-face-two', 380, shared);
           const covered = face('covered-binding-badge', 200);
          source.append(covered);
          const cover = document.createElement('span');
           cover.id = 'binding-badge-cover';
          cover.style.cssText =
            'position: fixed; left: 90px; top: 200px; width: 24px; height: 24px;' +
            ' z-index: 2; background: black;';
          source.append(cover);
          add('covered-face', 460, covered);
          const clip = document.createElement('span');
          clip.id = 'binding-badge-clip';
          clip.style.cssText =
            'position: fixed; left: 90px; top: 240px; width: 24px; height: 8px;' +
            ' overflow: hidden;';
          const clipped = document.createElement('span');
          clipped.id = 'clipped-binding-badge';
          clipped.className = 'lf-key-badge';
          clipped.style.cssText = 'position: absolute; left: 0; top: 0;';
          clip.append(clipped);
          source.append(clip);
          add('clipped-face', 540, clipped);
        }"""
    )

    # The Ask's bindings are chrome, painted on the frame after the press that enters it.
    page.keyboard.press("a")
    for control, binding in (
        ("#disconnected-face", "3"),
        ("#shared-face-one", "4"),
        ("#shared-face-two", "5"),
        ("#covered-face", "6"),
        ("#clipped-face", "7"),
    ):
        expect(page.locator(control)).to_have_attribute("aria-keyshortcuts", binding)
    expect(page.locator("#shared-binding-badge[data-lf-binding-badge]")).to_have_count(
        0
    )
    expect(page.locator("#covered-binding-badge[data-lf-binding-badge]")).to_have_count(
        0
    )
    expect(page.locator("#clipped-binding-badge[data-lf-binding-badge]")).to_have_count(
        0
    )
    for binding in ("3", "4", "5", "6", "7"):
        expect(
            page.locator(
                ".lf-command-binding-badges > .lf-command-binding-badge",
                has_text=binding,
            )
        ).to_have_count(1)


def test_ask_binding_badges_do_not_cover_their_key_line(browser, serve):
    """A binding badge that reaches the shortcut bar yields to its digit's legend."""
    page = open_page(browser, serve(BINDING_BADGE_PAGE))
    resized(page, 900, 520)

    # The first Ask uses titled cards, whose trailing binding badges cannot meet the leading
    # shortcut bar. Step to the compact row Ask, where both occupy the leading edge.
    #
    # The walk arrives and then travels, in that order and in one task, so the arrival is
    # the fact each stillness reading is taken behind. Stillness on its own answers the
    # same for a page that has finished travelling and one whose asynchronous reveal has
    # not started it, and the second answer is the one that loses this test: the geometry
    # below is measured where the walk began, the scroll it computes is issued there, and
    # the travel then lands on top of it with the badge back above the bar.
    page.keyboard.press("a")
    expect(page.locator("#cards-decision")).to_be_focused()
    scroll_settled(page)
    page.keyboard.press("a")
    expect(page.locator("#rows-decision")).to_be_focused()
    scroll_settled(page)
    expect(
        page.locator("#rows > lf-option > .lf-key-badge[data-lf-binding-badge]")
    ).to_have_text(["1", "2"])
    # Put the second row's badge one pixel into the shortcut bar's band. The first stays a
    # row above it, so a placement pass that reserves the legend keeps one and removes
    # the other. Calculate the scroll from their current boxes rather than pinning the
    # fixture to today's spacing.
    page.evaluate(
        """() => {
          const badges = document.querySelectorAll(
            '#rows > lf-option > .lf-key-badge[data-lf-binding-badge]'
          );
          const last = badges[badges.length - 1].getBoundingClientRect();
          const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          scrollTo(0, scrollY + last.top - line.top - 1);
        }"""
    )
    scroll_settled(page)
    expect(
        page.locator("#rows > lf-option > .lf-key-badge[data-lf-binding-badge]")
    ).to_have_count(1)
    geometry = page.evaluate(
        """() => {
          const read = node => {
            const box = node.getBoundingClientRect();
            return {left: box.left, right: box.right, top: box.top, bottom: box.bottom};
          };
          return {
            line: read(document.querySelector('.lf-shortcut-bar')),
            chips: [...document.querySelectorAll(
              '.lf-command-binding-badges > .lf-command-binding-badge, [data-lf-binding-badge]'
            )].filter(node => node.checkVisibility({visibilityProperty: true})).map(read),
          };
        }"""
    )
    assert geometry["chips"], "the fixture did not leave an Ask binding badge on screen"
    assert all(
        chip["right"] <= geometry["line"]["left"]
        or geometry["line"]["right"] <= chip["left"]
        or chip["bottom"] <= geometry["line"]["top"]
        or geometry["line"]["bottom"] <= chip["top"]
        for chip in geometry["chips"]
    ), geometry


def test_a_needed_draft_contributes_its_current_ask_action(browser, serve):
    source = leaf_page(
        "needed draft binding",
        """
<h1>Supply the copy</h1>
<lf-ask id="copy-ask"><h2>What should the invitation say?</h2>
  <lf-draft id="copy" needed><pre>Draft invitation</pre></lf-draft>
</lf-ask>
""",
    )
    page = open_page(browser, serve(source))

    page.keyboard.press("a")
    expect(page.locator("#copy-ask")).to_be_focused()
    assert active_digit_bindings(page) == "1"
    page.keyboard.press("1")
    expect(page.get_by_role("textbox", name="Edit copy")).to_be_focused()


def test_an_ask_that_cannot_name_itself_arrives_on_the_words_that_explain_it(
    browser, serve
):
    """A change to a phrase has no region to declare, so the document supplies one.

    An x-ask-surface widget states its own arrival region: a heading, the context, then the
    control. A suggestion can stand mid-sentence, so it can never satisfy "an ask must
    name itself without context outside the ask" and no region can be written round it.
    Arriving on the change alone put its own top edge under the banner and took the
    sentence and the heading with it, leaving the user on the change with nothing on
    screen saying what they would be accepting.

    The heading, the sentence, and the change are read together: a landing on the
    sentence alone would satisfy a heading assertion by accident on a page whose
    heading happens to sit one line above it, and this page's does not.
    """
    page = open_page(browser, serve(SUGGESTION_IN_CONTEXT_PAGE))
    resized(page, 900, 500)

    # The change is below the fold and the page can scroll, or standing still would look
    # like the arrival this asks for.
    assert page.evaluate(
        """() => {
          const box = document.getElementById('sc-sug').getBoundingClientRect();
          const se = document.scrollingElement;
          return box.top > se.clientHeight && se.scrollHeight - se.clientHeight > 500;
        }"""
    ), "the fixture already shows the change on the first screen"

    page.keyboard.press("a")
    expect(page.locator("#sc-sug")).to_be_focused()
    scroll_settled(page)

    landed = page.evaluate(
        """() => {
          const at = (id) => document.getElementById(id).getBoundingClientRect();
          return {
            heading: at('sc-api-heading').top,
            sentence: at('sc-api-why').top,
            change: at('sc-sug').top,
            foot: at('sc-sug').bottom,
            view: document.scrollingElement.clientHeight,
            clear: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
          };
        }"""
    )
    assert abs(landed["heading"] - landed["clear"]) <= 2, (
        f"the arrival put the heading over this change at {landed['heading']:.1f}px "
        f"rather than below the banner at {landed['clear']:.1f}px"
    )
    assert landed["clear"] < landed["sentence"] < landed["change"], (
        "the sentence the change stands in is not on screen above it"
    )
    assert landed["foot"] <= landed["view"], "the change itself ran off the screen"


def test_an_arrival_region_fits_above_the_bottom_bar(browser, serve):
    """The region an arrival takes in is measured against the landing band.

    The shortcut bar stands over the window's foot, so a region measured against the
    window below the banner put the heading at the top of the screen and the change it
    was chosen for under the bar. The window is sized so the heading's region fits below
    the banner but not above the bottom bar: the arrival takes a narrower region, and the
    change stays where the user can read it.
    """
    page = open_page(browser, serve(SUGGESTION_IN_CONTEXT_PAGE))
    resized(page, 900, 500)
    measure = """() => {
      const at = (id) => document.getElementById(id).getBoundingClientRect();
      const style = getComputedStyle(document.scrollingElement);
      return {
        span: at('sc-sug').bottom - at('sc-api-heading').top,
        foot: at('sc-sug').bottom,
        view: document.scrollingElement.clientHeight,
        top: parseFloat(style.scrollPaddingTop),
        bottom: parseFloat(style.scrollPaddingBottom),
      };
    }"""
    before = page.evaluate(measure)
    assert before["bottom"] > 0, "the fixture has no bottom bar to land clear of"
    resized(page, 900, round(before["span"] + before["top"] + before["bottom"] / 2))

    page.keyboard.press("a")
    expect(page.locator("#sc-sug")).to_be_focused()
    scroll_settled(page)

    landed = page.evaluate(measure)
    assert landed["span"] == pytest.approx(before["span"], abs=1), (
        "the resize reflowed the region, so the window no longer falls between the two "
        "readings of the room"
    )
    assert landed["foot"] <= landed["view"] - landed["bottom"] + 0.5, (
        f"the arrival put the change's foot at {landed['foot']:.1f}px, under the foot "
        f"band that starts at {landed['view'] - landed['bottom']:.1f}px"
    )


def test_an_arrival_does_not_reach_back_into_the_ask_before_it(browser, serve):
    """The heading over a change is the one it stands under, not the last one written.

    Two asks in a row is the ordinary way to write two, and the second here has no
    heading of its own under its container. The nearest heading written before it is
    then the first ask's own, and arriving there would put a different question in
    front of the user as this change's context. A candidate has to share a container
    with the change for that reason, which also stops the search at the part of the
    document the change is in.

    The change is reached from the foot of the page rather than by stepping forward off
    the ask above it. Arriving at that ask leaves this one on screen already, where the
    press deliberately moves nothing and there is no travel to read.
    """
    page = open_page(browser, serve(ASKS_IN_A_ROW_PAGE))
    resized(page, 900, 500)

    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    scroll_settled(page)

    page.keyboard.press("Shift+a")  # back to the nearest ask above, which is the change
    expect(page.locator("#ar-sug")).to_be_focused()
    scroll_settled(page)

    landed = page.evaluate(
        """() => {
          const at = (id) => document.getElementById(id).getBoundingClientRect();
          return {
            other: at('ar-other-heading').top,
            otherFoot: at('ar-other-decision').bottom,
            change: at('ar-sug').top,
            foot: at('ar-sug').bottom,
            view: document.scrollingElement.clientHeight,
            clear: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
          };
        }"""
    )
    assert landed["otherFoot"] <= landed["change"], (
        "the fixture no longer has the previous ask standing above this one"
    )
    # The previous ask's heading is close enough to reach: without the container bound
    # it fits the screen from its own top to this change's foot, so it would be chosen
    # and the user would start on the question they are not being asked.
    assert landed["foot"] - landed["other"] <= landed["view"] - landed["clear"], (
        "the fixture has moved the two asks too far apart for the wrong heading to be "
        "reachable, so this test can no longer tell the container bound is working"
    )
    assert abs(landed["other"] - landed["clear"]) > 2, (
        "the arrival put the previous ask's heading below the banner, so the user "
        "starts on the question they are not being asked"
    )
    assert landed["foot"] <= landed["view"], "the change itself ran off the screen"


def test_an_ask_inside_a_card_is_brought_into_that_card(browser, serve):
    """The arrival places a region out on the page; the ask may be in a box of its own.

    The placement moves whichever scroller the region belongs to, and for a region on
    the page that is never the card's. So the ask's own box comes into view first, which
    is the one pass that moves a nested scroller. Handing the placement the region alone
    left the ask unscrolled in its card, with the ring and focus on a change the user
    could not see — and the walk's next press repeated the same non-arrival.
    """
    page = open_page(browser, serve(ASK_IN_A_CARD_PAGE))
    resized(page, 900, 500)

    # The card hides the ask to begin with, or the reveal has nothing to do — and the
    # region really is outside the card, or the region's own reveal would scroll the card
    # whatever the arrival did, and a green result would say nothing about it.
    assert page.evaluate(
        """() => {
          const card = document.getElementById('ac-card');
          const box = document.getElementById('ac-sug').getBoundingClientRect();
          const head = document.getElementById('ac-heading').getBoundingClientRect();
          const se = document.scrollingElement;
          const clear = parseFloat(getComputedStyle(se).scrollPaddingTop) || 0;
          const inside = card.querySelector(
            'p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary');
          return card.scrollHeight > card.clientHeight &&
                 box.top > card.getBoundingClientRect().bottom &&
                 box.bottom - head.top <= se.clientHeight - clear &&
                 !(inside && !inside.closest('lf-suggestion'));
        }"""
    ), (
        "the fixture's card shows the change already, holds a block before it, or has "
        "grown past the heading's reach — the region would then be the change itself"
    )

    page.keyboard.press("a")
    expect(page.locator("#ac-sug")).to_be_focused()
    scroll_settled(page)

    seen = page.evaluate(
        """() => {
          const box = document.getElementById('ac-sug').getBoundingClientRect();
          const card = document.getElementById('ac-card').getBoundingClientRect();
          const view = document.scrollingElement.clientHeight;
          return {
            insideCard: box.top >= card.top - 0.5 && box.bottom <= card.bottom + 0.5,
            onScreen: box.top >= 0 && box.bottom <= view,
          };
        }"""
    )
    assert seen["insideCard"], (
        "the change is still outside its card's own band, so the card was never scrolled"
    )
    # Where the card's own top ends up is not promised: the region can be a block inside
    # the card, and placing that at the banner takes the card's top edge above it. What
    # is promised is the change, in the window and in its card's band at once.
    assert seen["onScreen"], "the change is in its card's band but off the window"


def test_an_ask_already_in_front_of_the_user_is_not_travelled_to(browser, serve):
    """The press moves the ring and the focus and leaves the page where it stands.

    Rebuilding a view the user is already looking at is motion that says nothing, and
    it costs them whatever adjustment they had made within it. The gate reads what the
    page shows of the ask rather than what its own box claims, which is the reading
    commentOnAddressable makes before its own travel.

    The first press is the control: the walk does travel, from a page that opens above
    the change, so a second press standing still is this gate rather than a walk that
    never moves the page at all.
    """
    page = open_page(browser, serve(SUGGESTION_IN_CONTEXT_PAGE))
    resized(page, 900, 500)

    page.keyboard.press("a")
    expect(page.locator("#sc-sug")).to_be_focused()
    scroll_settled(page)
    arrived = page.evaluate("() => document.scrollingElement.scrollTop")
    assert arrived > 0, "the walk did not travel to the ask at all"

    # A little above that arrival: the region's start is still clear of the banner and
    # the change's foot is still on screen, so this is the same view with the user's
    # own adjustment in it.
    page.evaluate("() => document.scrollingElement.scrollBy(0, -40)")
    scroll_settled(page)
    held = page.evaluate("() => document.scrollingElement.scrollTop")
    assert held == arrived - 40, "the page did not take the user's own adjustment"

    # The press's own announcement is the edge this absence stands behind. `goToAsk`
    # travels before it announces, so a live region that has spoken again is a press whose
    # travel has already been decided and begun. Waiting on the scroll alone cannot say
    # that: frames held still before a glide starts read the same as a page that never
    # moved, and only the announcement puts the read behind the decision.
    observe_live_region(page)
    page.keyboard.press("a")  # one ask, so the clamped walk stays on it
    page.wait_for_function(
        "() => window.__lfLiveRegionChanges.some("
        "words => words.includes('waiting on you'))"
    )
    expect(page.locator(".lf-live")).to_have_text(re.compile(r"waiting on you"))
    assert "" in page.evaluate("window.__lfLiveRegionChanges")
    expect(page.locator("#sc-sug")).to_be_focused()
    scroll_settled(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == held, (
        "the walk travelled to an ask the user could already see"
    )


def test_the_ask_walk_starts_from_where_the_user_is(browser, serve):
    """The walk measures from the user, the way Space page travel measures from the scroll position
    and t/T from the focused thread. It kept an id of its own instead, so every walk
    the user had not made with this key started at the top of the page: scroll
    halfway down and press `d` and you were taken back past everything you had read,
    and so was anyone who had just selected a paragraph to comment on.

    Two readings of where they are are left in turn: what they are reading, and where
    the walk itself last left off. The banner's button is no place — pressing it opens
    the drawer and leaves the focus on itself, so a walk measured from the focus after it
    would restart on every press, and the ring is gone from the page by then, the user
    being in the banner. A selected passage now enters its comment field immediately;
    while that field stands, letters are text rather than page-navigation keys."""
    page = open_page(browser, serve(ASKS_PAGE))

    # A window short enough that reading down the page leaves the top of it behind,
    # which is the whole of what the user has to do to be somewhere.
    resized(page, 900, 400)

    # Scrolled to the change with nothing selected and nothing focused: the decision after
    # it, not the question above it. They are standing *in* that suggestion, which is
    # why it is the decision they step off rather than the one they step to.
    page.locator("#refill-now").evaluate("el => el.scrollIntoView({block: 'center'})")
    page.keyboard.press("a")
    expect(page.locator("#t-baffles-decision")).to_have_attribute("data-lf-ask", "1")

    # The banner's press opens the drawer and keeps the focus, so the walk after it
    # measures from where the user stands in the page and steps on rather than
    # restarting — the button being no place to measure from.
    #
    # Reached through `banner_control` rather than by clicking the button where it
    # would stand on a wide row: at this fixture's 900px the row cannot hold every
    # control in a face wider than this desk's, and folding one is the row's stated
    # answer. Which control the fold takes is the banner's business and not this
    # walk's, so the helper opens the door where it has to.
    banner_control(page, ".lf-queue").click()
    page.keyboard.press("a")
    expect(page.locator("#t-bath-decision")).to_have_attribute("data-lf-ask", "1")


def test_the_queue_names_an_ask_a_message_carries(browser, serve):
    """A decision carried by a reply is a decision, and the Queue has to name it in its words.

    The page holds none of its own, so the one row here is the question Claude put in
    the thread — the AskUserQuestion shape, which reaches a user through the
    panel and through the Queue panel and nowhere else. It is read here exactly as a group
    on the page is read: the decision's own words, its label first, run together and cut at
    the row's cap. `startswith` for that reason — the cut is the panel's business and
    this is about which words reach it, which is the whole of what the row asserts for
    a page-borne ask two tests below.

    It read `rp-decision` before, and then read the label alone: a veto on chrome threw the
    reading away, and lifting it left the panel over the widget standing in for the
    widget's own chrome, so only a declared label got out. The reading is rooted at the
    ask now, so the layer above it is nobody's apparatus and the words underneath are
    the widget's own."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-which",
            "author": "user",
            "revision": 1,
            "text": "Either would do. Which are you leaning towards?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-which",
            "revision": 1,
            "text": "The second, but the cost lands on you either way:",
            "markup": (
                '<lf-ask id="rp-decision-region"><h3>Which should I write up first?</h3>'
                '<lf-options id="rp-decision" choose>'
                '<lf-option id="rp-now">The migration</lf-option>'
                '<lf-option id="rp-later">The rollback</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)

    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    # The Ask is the user's one item; the comment the reply carried it in is still owed
    # an answer, which is the agent's.
    rows = [row for row in page.evaluate(QUEUE_ROW_SAYS) if row["list"] == "you"]
    assert len(rows) == 1, rows
    assert rows[0]["at"] == "rp-decision-region", rows
    assert rows[0]["title"].startswith("Which should I write up first?"), rows


def test_a_widget_a_message_carries_holds_the_room_its_words_will_need(browser, serve):
    """A measurement is a measurement wherever the widget was built, or it is a zero.

    Two shipped widgets take a number off a live box at upgrade — the room a card keeps
    clear of its grip and the width of a roster's state column — because a constant goes
    stale in the next face. A widget
    upgrades wherever the runtime connects it, and one of those places is a message body
    inside a thread panel nobody has opened: `display: none`, so every box under it is
    zero. `once` then refuses the second upgrade that would put it right and the body is
    cached for the life of the tab, so the zero is permanent.

    The reply is in the log before the page loads and the panel is shut, which is the
    only reading arrangement that reproduces it: a reply arriving into an open panel upgrades
    into boxes and was always right. Rooms are compared rather than named, because the
    number is the face's and this is about whether it was ever read.

    Both of them, because `measure` is the primitive and each module's wiring to it is
    its own line."""
    url = serve(MESSAGE_ROOM_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-room",
            "author": "user",
            "revision": 1,
            "text": "Anything else worth adding?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-room",
            "revision": 1,
            "text": "These, and who is on them:",
            "markup": ROOM_WIDGETS.format(id="mr-msg"),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)

    held = {}
    for suffix, prop in ROOMS:
        held[suffix] = page.evaluate(ROOM_HELD, [f"mr-page{suffix}", prop])
        # Against a page that stopped reserving anything, where this would pass on both
        # sides reading the same nothing.
        assert held[suffix] not in ("0px", "", None), (suffix, prop, held)

    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").click()
    expect(page.locator("#mr-msg-b")).to_be_visible()
    # The re-measure is delivered with the layout that gave these their boxes, so the
    # reading waits for the rendering it queued to settle.
    rendered(page)
    for suffix, prop in ROOMS:
        assert page.evaluate(ROOM_HELD, [f"mr-msg{suffix}", prop]) == held[suffix], (
            suffix,
            prop,
        )


def test_a_drag_across_a_question_in_a_reply_is_not_a_passage_of_the_page(
    browser, serve
):
    """A selection made in the panel is not the page's words, whatever it looks like.

    `leaf thread open --section` refuses to anchor on a widget an agent sent, and it is the
    reading that is supposed to promise less than the browser's. The browser offered
    the 💬 over a question in a reply and wrote an anchor onto that widget's own id into
    an append-only log — naming a section no version holds, so it could never paint and
    never be found again.

    A declared label is the hole it came through: it is the page speaking inside the
    control it labels, so it answers the "are these the runtime's words" question for
    itself and the panel above it never got asked. That question was standing in for a
    second one nobody was putting — which document is this — and the drag needs both.

    The same drag on the page's own prose comes first and must raise the button. It is
    the control: this asserts an absence, and an absence proves nothing on a page where
    nothing was ever going to appear. The drags are real ones, so the mouseup guard is
    under test with the button.

    Then two turns of the macrotask queue, because the handler raises the button from a
    bare `setTimeout` — asserting straight after the drag reads the frame before the
    decision and passes whatever the decision would have been."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-store",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-store",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-ask id="ps-decision-region"><h3>Which store should I write up?</h3>'
                '<lf-options id="ps-decision" choose>'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)

    def drag(locator):
        expect(locator).to_be_visible()
        box = locator.bounding_box()
        y = box["y"] + box["height"] / 2
        select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
        return page.evaluate("() => getSelection().toString()")

    # The control, taken with the panel still shut: the same gesture on the page's own
    # words raises the button here. Opening the panel slides the document over, and a
    # drag run across that reads a box from the frame before and selects nothing — the
    # panel's own contents are fixed and stay where they are read.
    intro = page.locator("#intro")
    box = intro.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    expect(page.locator("#lf-composer-quote")).to_contain_text("signed-cookie")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    # Put it down again, so what follows is a rise and not a leftover.
    page.locator("#h").click()
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").click()
    assert "Which store" in drag(page.locator("#ps-decision-region > h3"))
    # Both turns the handler could have used: it defers with a bare setTimeout, and the
    # step it queues queues nothing further.
    for _ in range(2):
        page.evaluate("() => new Promise((r) => setTimeout(r))")
    expect(page.locator(".lf-fab-input")).to_be_hidden()


def test_a_thread_seated_in_a_widget_is_not_a_change_to_the_document(browser, serve):
    """What a user and an agent said to each other is not something the page changed.

    A widget declaring x-thread-seat grows a seat on the page, and the layer fills it
    from the log — messages the runtime built, wearing `.lf-ui` and `data-lf-gen`, and
    standing inside the widget out in `<main>`. The version diff walks every block the
    page holds and keys each by `wrote`, which is exactly the reading that leaves
    generated words out, so those blocks key to nothing and are skipped.

    They stopped being skipped when `wrote` was bounded at the element handed in: a
    reading can start *inside* generated chrome, and rooted at one of those `<p>`s the
    box above it was no longer over the reading. The base version is parsed unupgraded
    and holds no thread at all, so every message became an insertion — the
    user's own comment and the agent's reply painted as changes to the document, and
    the count in the version note inflated by both.

    The bound is the widget the reading belongs to now, and a thread seat is
    inside its widget, so the box is between the words and their frame either way."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "cd-thread",
            "author": "user",
            "revision": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "cd-thread",
            "revision": 1,
            "text": "It does, with the wider plate.",
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 1200, 900)
    # The seat is filled before the diff runs, or this asserts over a page that never
    # had the blocks in question.
    expect(page.locator("#cd-q .lf-msg")).to_have_count(2)

    stamp_page(
        d,
        THREAD_DIFF_PAGE.replace(
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>',
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>\n'
            '<p id="cd-new">The north pair waits on brackets.</p>',
        ),
        "two",
    )
    wait_for_revision(page, 2)
    expect(page.locator("#cd-q .lf-msg")).to_have_count(2)

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map((e) => e.id)"
    ) == ["cd-new"], "the diff read the thread as words the base version lacked"


def test_an_agent_message_edit_updates_the_panel_and_its_inline_thread(browser, serve):
    """The edit is one log arrival and both views fold it onto the original message.

    Neither view gains a second message. Their standing message nodes survive the
    arrival, so an edit cannot disturb a user working elsewhere in the same thread;
    only the prose inside changes, and both heads disclose that it changed.
    """
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    message = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "edited-agent-message",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "revision": 1,
            "text": "The north bracket fit.",
            "anchor": {"section": "cd-q"},
            "markup": (
                '<lf-options id="edited-message-choice" choose>'
                '<lf-option id="edited-message-now">Fit it now</lf-option>'
                "</lf-options>"
            ),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    inline = page.locator(f'#cd-q .lf-msg[data-event="{message["id"]}"]')
    inline_thread = page.locator(
        f'#cd-q .lf-page-thread:has(.lf-msg[data-event="{message["id"]}"])'
    )
    expect(inline.locator(".lf-msg-body")).to_have_text("The north bracket fit.")
    page.locator(".lf-threads-toggle").click()
    panel = page.locator(f'.lf-msg[data-mid="{message["id"]}"]')
    panel_thread = page.locator(f'.lf-thread:has(.lf-msg[data-mid="{message["id"]}"])')
    expect(panel.locator(".lf-msg-text")).to_have_text("The north bracket fit.")
    page.evaluate(
        """([message]) => {
          window.__editedInline = document.querySelector(
            `#cd-q .lf-msg[data-event="${message}"]`);
          window.__editedPanel = document.querySelector(`.lf-msg[data-mid="${message}"]`);
          window.__editedWidget = document.querySelector('#edited-message-choice');
        }""",
        [message["id"]],
    )

    revision = append_carried_log_record(
        d,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "message": message["id"],
            "text": (
                "The north bracket fits.\n\n"
                "```python\n"
                "def fitted():\n"
                "    return True\n"
                "```"
            ),
        },
    )
    told(page)
    panel_thread.get_by_role("button", name="1 new reply", exact=True).click()
    inline_thread.get_by_role("button", name="1 new reply", exact=True).click()

    expect(inline.locator(".lf-msg-body")).to_contain_text("The north bracket fits.")
    expect(panel.locator(".lf-msg-text")).to_contain_text("The north bracket fits.")
    expect(panel.locator('pre code [data-lf-syn="kw"]').first).to_have_text("def")
    # The disclosure is on the head, and a thread's first message lends its head to the
    # card, where the thread's own actions sit beside the author. So the mark belongs to
    # the card holding the message rather than to the message node, on both surfaces.
    expect(inline_thread.locator(".lf-thread-root-meta .lf-edited")).to_have_text(
        "edited"
    )
    expect(panel_thread.locator(".lf-thread-root-meta .lf-edited")).to_have_text(
        "edited"
    )
    expect(page.locator(f'.lf-msg[data-mid="{revision["id"]}"]')).to_have_count(0)
    assert page.evaluate(
        f"""() => window.__editedInline === document.querySelector(
          '#cd-q .lf-msg[data-event="{message["id"]}"]')
          && window.__editedPanel === document.querySelector(
            '.lf-msg[data-mid="{message["id"]}"]')
          && window.__editedWidget === document.querySelector('#edited-message-choice')"""
    ), "the edit replaced a standing message or its frozen widget"
    assert (
        next(
            event
            for event in events_model.read_events(d)
            if event["id"] == message["id"]
        )["text"]
        == "The north bracket fit."
    )


def test_a_thread_on_a_widget_an_agent_sent_names_it_and_stands_apart(browser, serve):
    """A question the agent asked is not one of the runtime's own buttons.

    Design mode lets a user comment on anything the layer draws, so a thread can be
    anchored on a widget that arrived in a reply. Two things were then said about it and
    both were wrong. The panel filed it under "The page's own layer", which groups the
    agent's question with the composer and the version picker — the layer's parts wear
    the runtime's id namespace, which authored markup may not take, and that is what
    tells one from the other. And the thread's label read `§ ps-decision`, the bare id.

    The label is the part with the mechanism worth naming. An element anchor is labelled
    with its element's opening words, read when the node is built — and on the reconcile
    that first builds this node, the message body carrying the widget has not been
    connected yet, so the element did not exist and the reading came back empty. A node the
    reconcile keeps is never built again, so nothing asked a second time. It is repainted
    with the quote now, which is the pass that already exists for records whose subject
    the reconcile has just written."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-sent",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-sent",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-ask id="ps-decision-region"><h3>Which store should I write up?</h3>'
                '<lf-options id="ps-decision" choose>'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    # The shape design mode writes: an element anchor naming a widget no version holds.
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-on-sent",
            "author": "user",
            "revision": 1,
            "text": "Redis, and say why in the patch.",
            "anchor": {"section": "ps-decision-region"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()

    thread = page.locator('.lf-thread[data-id="c-on-sent"]')
    expect(thread).to_be_visible()
    # The card is a native disclosure; its quote is behind the title until it is opened.
    thread.locator(":scope > .lf-thread-summary").click()
    label = thread.locator(".lf-quote").inner_text()
    assert "Which store should I write up?" in label, label
    assert "ps-decision-region" not in label, label


def test_a_change_says_which_of_the_three_it_is(browser, serve):
    """A Queue row names its Ask by kind and then by the decision's own opening words,
    and for a change those opening words are whichever half comes first — the current
    text, where there is one. So a deletion arrived in the list under the words it was
    proposing to remove, with nothing to tell it from the insertion above it, which was
    proposing to add its own. Three shapes, one tag, one word for all of them.

    The tag is the right word wherever one tag is one kind of thing, which is every
    other widget here, so the fix is not to teach the Queue about suggestions: the
    entry declares that this tag's word comes from its module (x-word), and the module
    reads it off the slots it holds. The group below is in this page to hold the other
    half of that — a widget declaring nothing still gets its tag, and would go on
    getting it if the declaration were dropped."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 1200, 900)

    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    rows = [row for row in page.evaluate(QUEUE_ROW_SAYS) if row["kind"] == "ask"]

    assert {r["at"]: r["word"] for r in rows} == {
        "sug-rewrite": "Rewrite",
        "sug-insert": "Insertion",
        "sug-delete": "Deletion",
        "shapes-decision": "Ask",
    }
    # The words beside the kind are still the element's own, and the two changes that
    # keep a current paragraph still open on it — the reading did not move, only what
    # is said about it.
    said = {r["at"]: r["title"] for r in rows}
    assert said["sug-delete"].startswith("Retries are logged"), said
    assert said["sug-insert"].startswith("Parked jobs"), said


def test_the_queue_control_opens_open_and_answered_asks(browser, serve):
    """The banner's Queue control lists every open Ask under On you, in document order,
    and every answered one under Done with its current answer, so the user can review
    and revise. A twelfth widget joins by declaring x-awaits.

    A closed panel holds no rows at all. That is not tidiness: they are the open
    panel's rendering, the banner's counts are the closed panel's, and a hidden list of
    buttons is a set of controls no user can press — which the press sweep sees as
    the page's control set changing under it."""
    page = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1200, 900)
    panel = page.locator(".lf-queue-panel")
    expect(panel).to_be_hidden()
    assert page.evaluate(QUEUE_ROW_SAYS) == [], "a closed panel holds no rows"

    control = banner_control(page, ".lf-queue")
    control.focus()
    page.keyboard.press("Enter")
    expect(panel).to_be_visible()
    rows = page.evaluate(QUEUE_ROW_SAYS)
    assert [(r["at"], r["list"]) for r in rows] == [
        *((at, "you") for at in ASKS_IN_ORDER),
        ("honored-decision", "done"),
    ]
    for row in rows:
        assert row["kind"] == "ask", row
        assert row["word"] == ("Rewrite" if row["at"] == "sug-refill" else "Ask"), row
        if row["list"] == "you":
            assert row["w"] > 100 and row["h"] > 20, f"{row['at']}'s row has no size"

    # The Ask leads with its authored heading rather than the first option's answer.
    said = {r["at"]: r for r in rows}
    assert said["live-question-decision"]["title"].startswith(
        "Where should sessions live?"
    ), said
    assert said["t-baffles-decision"]["title"].startswith("Are the baffles ready?"), (
        said
    )
    assert said["honored-decision"]["where"].startswith("Answered Two-tier gates"), said

    # Answered, and the row moves to Done as the route back, saying its current answer.
    # The pick is a move the agent now owes a reply, which is its row and not the Ask's.
    page.locator("#lq-token").click()
    expect_asks_answered(page, "2/5")
    expect(page.locator("button.lf-queue-row[data-lf-kind='ask']")).to_have_count(5)
    answered = {r["at"]: r for r in page.evaluate(QUEUE_ROW_SAYS)}
    assert answered["live-question-decision"]["list"] == "done", answered
    assert answered["live-question-decision"]["where"].startswith(
        "Answered Signed tokens"
    ), answered

    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    suggestion = next(
        row for row in page.evaluate(QUEUE_ROW_SAYS) if row["at"] == "sug-refill"
    )
    assert suggestion["list"] == "done", suggestion
    assert suggestion["where"].startswith("Answered Accepted"), suggestion

    # And closing takes the rest with it, for the reason the docstring gives: a panel
    # that is down is not a list, so it holds nothing to reach and nothing to press.
    banner_control(page, ".lf-queue").focus()
    page.keyboard.press("Enter")
    expect(panel).to_be_hidden()
    assert page.evaluate(QUEUE_ROW_SAYS) == [], "a closed panel keeps its rows"


def test_an_answered_asks_words_are_its_widgets_semantic_state(browser, serve):
    """Each family names its answer from the state it was answered with.

    A draft says its standing words, a playground the instruction it sent rather than
    whatever its controls show now, and an option the user added is named by the
    rendered words its `add` carried. A `multiple` group answered by Done with no pick
    of the user's names its authored choice."""
    url = serve(
        leaf_page(
            "answer words",
            """
<h1 id="h">Answers</h1>
<lf-ask id="note-ask"><h2>Is this release note right?</h2>
<lf-draft id="note" needed><pre>
Adds --dry-run to every mutating command.
</pre></lf-draft></lf-ask>
<lf-ask id="cache-ask"><h2>Which cache?</h2>
<lf-options id="cache" choose>
  <lf-option id="cache-none"><strong>No cache</strong> Read through.</lf-option>
</lf-options></lf-ask>
<lf-ask id="tags-ask"><h2>Which tags?</h2>
<lf-options id="tags" choose multiple>
  <lf-option id="tag-alpha" chosen><strong>Alpha</strong></lf-option>
  <lf-option id="tag-beta"><strong>Beta</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="tone-ask"><h2>Which notification?</h2>
<lf-playground id="tone">
  <lf-playground-control name="format" label="Format" kind="choice" value="banner">
    <lf-playground-choice value="banner" label="Banner"></lf-playground-choice>
    <lf-playground-choice value="strip" label="Strip"></lf-playground-choice>
  </lf-playground-control>
  <lf-playground-preview><p id="tone-preview">The notification.</p></lf-playground-preview>
  <lf-playground-output>Build the <lf-playground-value for="format"></lf-playground-value>
  notification.</lf-playground-output>
</lf-playground></lf-ask>
""",
        )
    )
    page = open_page(browser, url)
    door = url.rsplit("/versions/", 1)[0] + "/api/event"
    for widget, action, detail in [
        ("note", "edit", {"text": "Adds --dry-run to every command."}),
        ("cache", "add", {"option": "cache-redis", "text": "**Redis** in front"}),
        ("cache", "choose", {"options": ["cache-redis"]}),
        ("tags", "answer", {}),
        (
            "tone",
            "choose",
            {"values": {"format": "strip"}, "instruction": "Build the strip one."},
        ),
    ]:
        posted = post_event(
            page,
            door,
            data={
                "kind": "action",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )
        assert posted.ok, posted.text()
    expect_asks_answered(page, "4/4")
    banner_control(page, ".lf-queue").click()
    output = page.locator("#tone lf-playground-output")
    expect(output).to_contain_text("strip")
    page.locator("#tone").get_by_role("radio", name="Banner").click()
    expect(output).to_contain_text("banner")
    answers = {
        "note-ask": "Adds --dry-run to every command.",
        "cache-ask": "Redis in front",
        "tags-ask": "Alpha",
        "tone-ask": "Build the strip one.",
    }
    for at, words in answers.items():
        expect(
            page.locator(f'.lf-queue-row[data-lf-at="{at}"] .lf-queue-where')
        ).to_contain_text(f"Answered {words}")


def test_ask_rows_keep_identity_and_publisher_order_when_the_live_dom_moves(
    browser, serve
):
    """A keyed row follows the published document, not later presentation DOM edits."""
    page = open_page(browser, serve(ASKS_PAGE))
    banner_control(page, ".lf-queue").click()
    rows = page.locator("button.lf-queue-row")
    expect(rows).to_have_count(len(ALL_ASKS_IN_ORDER))

    page.evaluate(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          window.__lfReadAskPresentation = readApplicationPresentation;
          const rows = [...document.querySelectorAll('button.lf-queue-row')];
          window.__lfAskRows = new Map(rows.map(row => [row.dataset.lfAt, row]));
          const honored = document.querySelector('#honored-decision');
          document.querySelector('#live-question-decision').before(honored);
          window.__lfAskRows.get('sug-refill').focus();
          document.dispatchEvent(new Event('lf-presentation'));
        }"""
    )
    page.wait_for_function("__lfReadAskPresentation().pending.length === 0")
    assert (
        rows.evaluate_all("items => items.map(item => item.dataset.lfAt)")
        == ALL_ASKS_IN_ORDER
    )
    assert rows.evaluate_all(
        "items => items.every(item => window.__lfAskRows.get(item.dataset.lfAt) === item)"
    )
    expect(page.locator('.lf-queue-row[data-lf-at="sug-refill"]')).to_be_focused()

    # Removing a presentation node does not rewrite the application inventory. The
    # route and its keyed row remain exactly as they were published.
    page.evaluate(
        """() => {
          document.querySelector('#sug-refill').remove();
          document.dispatchEvent(new Event('lf-presentation'));
        }"""
    )
    page.wait_for_function("__lfReadAskPresentation().pending.length === 0")
    expect(page.locator('.lf-queue-row[data-lf-at="sug-refill"]')).to_be_focused()
    assert (
        rows.evaluate_all("items => items.map(item => item.dataset.lfAt)")
        == ALL_ASKS_IN_ORDER
    )
    assert rows.evaluate_all(
        "items => items.every(item => window.__lfAskRows.get(item.dataset.lfAt) === item)"
    )

    # A row still resolves its current presentation node at activation, but its ordinal
    # comes from the same immutable publication as the route.
    page.evaluate(
        """() => document.querySelector('main').append(
          document.querySelector('#honored-decision'))"""
    )
    observe_live_region(page)
    page.locator(".lf-queue-done > summary").click()
    page.locator('.lf-queue-row[data-lf-at="honored-decision"]').click()
    expect(page.locator("#honored-decision")).to_be_focused()
    expect(page.locator(".lf-live")).to_have_text("Ask 1 of 1 done")
    assert "Ask 1 of 1 done" in page.evaluate("window.__lfLiveRegionChanges")


def test_pending_action_waits_for_the_ask_list_paint_before_retiring(
    held_events, serve
):
    """Receipt settlement cannot retire optimism before the Queue row has painted it."""
    browser, held = held_events
    page = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    banner_control(page, ".lf-queue").click()
    row = page.locator('button.lf-queue-row[data-lf-at="storage-decision"]')
    expect(row).to_have_count(1)
    expect(row).to_have_attribute("data-lf-kind", "ask")
    expect(page.locator("[data-lf-queue='you'] .lf-queue-row")).to_have_count(1)
    page.evaluate(
        """async () => {
          const {readApplication, readApplicationPresentation} =
            await window.__lfRuntimeImport('/runtime/semantic-state.js');
          window.__lfReadAskApplication = readApplication;
          window.__lfReadAskPresentation = readApplicationPresentation;
          const list = document.querySelector('lf-queue-list');
          const schedule = list.scheduleUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          window.__lfReleaseAskPaint = release;
          let next = true;
          list.scheduleUpdate = async () => {
            if (next) {
              next = false;
              await held;
            }
            return schedule();
          };
        }"""
    )

    page.locator("#storage-stop").click()
    holding(page, held, 1, "the held answer")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    page.wait_for_function(
        "() => __lfReadAskApplication().unresolved.some("
        "entry => entry.state === 'accepted:logged')"
    )
    assert "queue" in page.evaluate("__lfReadAskPresentation().pending")
    assert page.evaluate("__lfReadAskApplication().unresolved.length") == 1
    expect(page.locator("[data-lf-queue='you'] .lf-queue-row")).to_have_count(1)

    page.evaluate("__lfReleaseAskPaint()")
    round_trip(page)
    page.wait_for_function("() => __lfReadAskApplication().unresolved.length === 0")
    expect(row.locator(".lf-queue-where")).to_contain_text(
        "Answered Pause offline editing"
    )


def test_a_failed_queue_list_paint_reports_once_and_retains_the_prior_list(
    browser, serve
):
    """A Queue list failure restores its earlier rows and leaves the banner controls."""
    page = open_page(browser, serve(ASKS_PAGE))
    answer_all = page.locator(".lf-answer-all")
    expect_asks_answered(page, "1/5")
    expect(answer_all).to_have_text("Accept all (1)")
    banner_control(page, ".lf-queue").click()
    rows = page.locator("button.lf-queue-row")
    expect(rows).to_have_count(len(ALL_ASKS_IN_ORDER))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.evaluate(
        """async () => {
          const {readApplicationPresentation, whenApplicationPresented} =
            await window.__lfRuntimeImport('/runtime/semantic-state.js');
          window.__lfReadAskPresentation = readApplicationPresentation;
          const list = document.querySelector('lf-queue-list');
          window.__lfAskRows = [...list.querySelectorAll('button.lf-queue-row')];
          const render = list.render.bind(list);
          list.render = () => {
            list.render = render;
            throw new Error('deliberate Queue list failure');
          };
          window.__lfAskListCurrentReady = false;
          window.__lfWaitForAskListCurrent = () =>
            void whenApplicationPresented().then(() => {
              window.__lfAskListCurrentReady = true;
            });
        }"""
    )
    page.locator("#lq-token").click()
    holding(page, held, 1, "the semantic answer")
    page.evaluate("__lfWaitForAskListCurrent()")
    page.wait_for_function("__lfAskListCurrentReady")
    assert page.evaluate("__lfReadAskPresentation().pending.length") == 0
    expect_asks_answered(page, "1/5")
    expect(answer_all).to_have_text("Accept all (1)")
    expect(rows).to_have_count(len(ALL_ASKS_IN_ORDER))
    assert rows.evaluate_all(
        "items => items.every((item, at) => item === window.__lfAskRows[at])"
    )
    rows.first.click()
    expect(page.locator("#live-question-decision")).to_be_focused()
    assert take_browser_errors(page) == [
        "leaf: Presentation failed: deliberate Queue list failure"
    ]
    holding(page, held, 2, "the gesture and the page's report of its failure")
    for route in held:
        route.continue_()
    page.unroute("**/api/event")
    round_trip(page)


def test_a_failed_ask_banner_paint_reports_once_and_retains_prior_controls(
    browser, serve
):
    """One failed Lit face leaves the prior stable bulk controls usable."""
    page = open_page(browser, serve(ASKS_PAGE))
    answer_all = page.locator(".lf-answer-all")
    expect_asks_answered(page, "1/5")
    expect(answer_all).to_have_text("Accept all (1)")
    banner_control(page, ".lf-queue").click()
    rows = page.locator("button.lf-queue-row")
    expect(rows).to_have_count(len(ALL_ASKS_IN_ORDER))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.evaluate(
        """async () => {
          const {readApplicationPresentation, whenApplicationPresented} =
            await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          window.__lfReadAskPresentation = readApplicationPresentation;
          window.__lfAskBulk = document.querySelector('.lf-answer-all');
          window.__lfAskRows = [
            ...document.querySelectorAll('button.lf-queue-row')];
          const bulkFace = window.__lfAskBulk.querySelector('lf-ask-banner-face');
          const render = bulkFace.render.bind(bulkFace);
          bulkFace.render = () => {
            bulkFace.render = render;
            throw new Error('deliberate Ask banner failure');
          };
          window.__lfAskCurrentReady = false;
          window.__lfWaitForAskCurrent = () =>
            void whenApplicationPresented().then(() => {
              window.__lfAskCurrentReady = true;
            });
        }"""
    )
    page.locator("#lq-token").click()
    holding(page, held, 1, "the semantic answer")
    page.evaluate("__lfWaitForAskCurrent()")
    page.wait_for_function("__lfAskCurrentReady")
    assert page.evaluate("__lfReadAskPresentation().pending.length") == 0
    expect_asks_answered(page, "1/5")
    expect(answer_all).to_have_text("Accept all (1)")
    expect(rows).to_have_count(len(ALL_ASKS_IN_ORDER))
    assert rows.evaluate_all(
        "items => items.every((item, at) => item === window.__lfAskRows[at])"
    )
    assert answer_all.evaluate("control => control === window.__lfAskBulk")
    rows.first.click()
    expect(page.locator("#live-question-decision")).to_be_focused()
    assert take_browser_errors(page) == [
        "leaf: Presentation failed: deliberate Ask banner failure"
    ]
    holding(page, held, 2, "the gesture and the page's report of its failure")
    for route in held:
        route.continue_()
    page.unroute("**/api/event")
    round_trip(page)


def test_a_completed_ask_persists_and_its_done_row_can_revise_by_keyboard(
    browser, serve
):
    """Completion keeps the same concise route back through the existing action model:
    the Queue's Done row, reached and opened from the keyboard, arrives at the Ask."""
    page = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    resized(page, 1200, 900)
    expect_asks_answered(page, "0/1")

    page.locator("#storage-stop").click()
    round_trip(page)
    expect_asks_answered(page, "1/1")

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect_asks_answered(page, "1/1")

    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    expect(page.locator("button.lf-queue-row").first).to_be_focused()
    # End is the Done fold's door; Enter opens it and the row below is the Ask's.
    page.keyboard.press("End")
    expect(page.locator(".lf-queue-done > summary")).to_be_focused()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    row = page.locator('.lf-queue-done .lf-queue-row[data-lf-at="storage-decision"]')
    expect(row).to_be_focused()
    expect(row.locator(".lf-queue-where")).to_contain_text(
        "Answered Pause offline editing"
    )

    page.keyboard.press("Enter")
    expect(page.locator("#storage-decision")).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#storage-evict")).to_have_attribute("chosen", "")
    expect_asks_answered(page, "1/1")
    expect(row.locator(".lf-queue-where")).to_contain_text(
        "Answered Drop the oldest documents"
    )


def test_an_answered_boxless_ask_reopens_on_its_visible_revision_control(
    browser, serve
):
    """A Queue row's arrival preserves Ask semantics when its source has no box to focus."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 560, 620)
    expect_asks_answered(page, "0/4")

    page.locator("[data-lf-margin-for='sug-delete'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_hidden()
    expect_asks_answered(page, "1/4")

    banner_control(page, ".lf-queue").click()
    row = page.locator('.lf-queue-row[data-lf-at="sug-delete"]')
    expect(row.locator(".lf-queue-where")).to_contain_text("Answered Accepted")
    page.locator(".lf-queue-done > summary").click()
    row.click()
    expect(page.locator(".lf-queue-panel")).to_be_hidden()
    undo = suggestion_control(page, "sug-delete", "undo", visible=False)
    expect(undo).to_be_focused()
    assert active_digit_bindings(page) == "1"

    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_visible()
    expect_asks_answered(page, "0/4")


def test_a_drawer_the_user_left_standing_comes_back_standing(browser, serve):
    """Reloading is not resetting: a drawer someone stood up to watch stays stood, the
    rule the thread panel already keeps. Which makes the reload the one moment a
    drawer is put up by something other than a press, and that is where it broke — the
    restore ran while the module was still evaluating and filled the drawer from a
    reading of the page's active Asks declared further down the file, so the user who
    had left it open got a ReferenceError instead of a page.

    Nothing static could have caught it and neither could the render gate, which
    presses no keys and so never has a drawer to restore. It took a user with the
    drawer open pressing reload, which is what this now is."""
    page = open_page(browser, serve(ASKS_PAGE))
    banner_control(page, ".lf-queue").click()
    drawer = page.locator(".lf-queue-panel")
    expect(drawer).to_be_visible()
    expect(page.locator("button.lf-queue-row")).to_have_count(len(ALL_ASKS_IN_ORDER))

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect(drawer).to_be_visible()
    expect(page.locator("button.lf-queue-row")).to_have_count(len(ALL_ASKS_IN_ORDER))


def test_a_drawer_sliding_out_takes_no_focus(browser, serve):
    """A drawer on its way out is already gone to the user: switching to Threads leaves
    none of its rows reachable while it slides away, and reopening it brings them back."""
    page = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1200, 900)
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    leaving = page.evaluate(
        """() => {
          document.querySelector('.lf-threads-toggle').click();
          const drawer = document.querySelector('.lf-queue-panel');
          const row = drawer.querySelector('button.lf-queue-row');
          row.focus();
          return { shown: drawer.checkVisibility(), inert: drawer.inert,
                   focused: document.activeElement === row };
        }"""
    )
    assert leaving == {"shown": True, "inert": True, "focused": False}, leaving
    expect(page.locator(".lf-queue-panel")).to_be_hidden()

    banner_control(page, ".lf-queue").click()
    row = page.locator("button.lf-queue-row").first
    row.focus()
    expect(row).to_be_focused()


def test_a_drawer_standing_over_most_of_an_ask_clears_for_it(browser, serve):
    """The drawer stands over the page, so an Ask its row sends the user to may be under it.
    Drawn wide but still leaving a usable page, the drawer stays live and stands over most of
    the column; pressing a row then clears the drawer, as travel clears any surface hiding
    its destination, rather than landing the user on a decision they cannot see. Beside
    a drawer at its default width the same press keeps the drawer up."""
    page = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1440, 900)
    drawer = page.locator(".lf-queue-panel")
    row = page.locator("button.lf-queue-row[data-lf-at='t-bath-decision']")
    covering = page.locator("html[data-lf-covering-surface]")

    banner_control(page, ".lf-queue").click()
    expect(drawer).to_be_visible()
    row.click()
    expect(page.locator("#t-bath-decision")).to_be_focused()
    expect(drawer).to_be_visible()

    edge = page.locator(".lf-queue-panel > .lf-edge")
    edge.focus()
    for _ in range(21):
        page.keyboard.press("ArrowRight")
    width = drawer.evaluate("el => el.getBoundingClientRect().width")
    assert 1440 - width >= 320 and width > 360 + 360, width
    expect(covering).to_have_count(0)
    row.click()
    expect(drawer).to_be_hidden()
    expect(page.locator("#t-bath-decision")).to_be_focused()


def test_a_row_stands_the_user_on_the_ask_it_names(browser, serve):
    """Pressing a row uses the same arrival as the Ask walk. It scrolls there, rings the
    Ask, and stands the user on its opening context; its controls are the next Tab
    stops, while the numeric action map is already available for direct revision.

    The ring lands in two places for one reason: the decision on the page and its row on the
    drawer are two surfaces showing where the user is standing, painted from the one
    reading of it (markHere), so neither can say something the other doesn't."""
    page = open_page(browser, serve(ASKS_PAGE))
    # Narrow enough that the drawer covers the page. A destination selected from a covering
    # sheet must dismiss the sheet; otherwise all the focus and scrolling below happen
    # correctly behind an opaque surface.
    resized(page, 560, 620)
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()

    # The last of the four, which a short window leaves well off screen.
    on_screen = """() => {
      const r = document.querySelector('#t-bath-decision').getBoundingClientRect();
      return r.top >= 0 && r.bottom <= innerHeight;
    }"""
    assert not page.evaluate(on_screen), (
        "the fixture must start with #t-bath-decision off screen"
    )

    page.locator("button.lf-queue-row[data-lf-at='t-bath-decision']").click()
    expect(page.locator(".lf-queue-panel")).to_be_hidden()
    page.wait_for_function(on_screen)
    expect(page.locator("#t-bath-decision")).to_be_focused()
    expect(page.locator("#t-bath-decision")).to_have_attribute("data-lf-ask", "1")
    page.keyboard.press("Tab")
    expect(page.locator("#t-bath-decision .lf-pick").first).to_be_focused()
    # The covering drawer has gone, so its projected rows go with it. The page carries the
    # one standing mark rather than leaving a second, hidden authority in the closed drawer.
    marked = page.evaluate(
        """() => [...document.querySelectorAll('[data-lf-ask]')]
             .map((e) => e.id || e.getAttribute('data-lf-at'))"""
    )
    assert sorted(set(marked)) == ["t-bath-decision"], marked


def test_the_queue_panel_covers_the_page_only_where_it_leaves_no_usable_page(
    browser, serve
):
    """A Queue row is a way around this page, so pressing one sends the user into the
    document, and the page beside the drawer stays live for it. Where the drawer would leave
    less than a usable page beside it, it covers instead — the rule the panel follows,
    asked of the room the drawer leaves rather than of the window, so a narrow window and a
    drawer drawn wide on a wide one come to the same answer, and a user who has learned one
    edge has learned the other. Either way the drawer stands over the page and moves none
    of it."""
    page = open_page(browser, serve(ASKS_PAGE))
    geometry = """() => ({
      column: Math.round(document.querySelector('main').getBoundingClientRect().left),
      drawer: Math.round(
        document.querySelector('.lf-queue-panel').getBoundingClientRect().right),
    })"""

    resized(page, 1200, 800)
    closed = page.evaluate(geometry)
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    covering = page.locator("html[data-lf-covering-surface='lf-queue']")
    expect(covering).to_have_count(0)
    wide = page.evaluate(geometry)
    assert wide["column"] == closed["column"], "the drawer moved the column"
    assert root_overflow(page) == 0, "the page scrolls sideways with the drawer up"

    # At 610 the default 300px drawer would leave 310, short of a usable page.
    resized(page, 610, 800)
    expect(covering).to_have_count(1)
    assert root_overflow(page) == 0
    resized(page, 1200, 800)
    expect(covering).to_have_count(0)

    # Drawn wide enough on a wide window, the strip is more than the page can give,
    # so the drawer covers. One step back and the page has its usable width again.
    edge = page.locator(".lf-queue-panel > .lf-edge")
    edge.focus()
    for _ in range(40):
        if covering.count():
            break
        page.keyboard.press("ArrowRight")
    expect(covering).to_have_count(1)
    left = page.evaluate(
        """() => innerWidth
             - document.querySelector('.lf-queue-panel').getBoundingClientRect().width"""
    )
    assert left < 320, f"the drawer covered with {left}px of page beside it"
    page.keyboard.press("ArrowLeft")
    expect(covering).to_have_count(0)
    assert page.evaluate(geometry)["column"] == closed["column"]


def test_one_drawer_stands_on_the_left_edge_at_a_time(browser, serve, other_leaf):
    """Both drawers want the edge, so opening either closes the other. Which one is up
    is one fact in one place: a boolean per drawer would be one guarantee written twice,
    and the two would first disagree the day a third surface opened one without closing
    the other — leaving two drawers over one edge with the lower unreachable.

    Escape names whichever is up rather than saying "close the drawer" over two of
    them, which is the rung the user is actually holding.

    The `other_leaf` fixture is the whole reason the leaves drawer has anything to show:
    a drawer of one — the page the user is already on — is not worth a control, so
    without a neighbour `g L` is unavailable and there is no second drawer to be exclusive
    with."""
    page = open_page(browser, serve(ASKS_PAGE))
    decisions, leaves = (
        page.locator(".lf-queue-panel"),
        page.locator(".lf-others-panel"),
    )

    banner_control(page, ".lf-queue").click()
    expect(decisions).to_be_visible()
    expect(leaves).to_be_hidden()

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(leaves).to_be_visible()
    expect(decisions).to_be_hidden()

    # Leaves is a modal covering workspace, so its scrim correctly makes the page and
    # banner inert. The global destination remains the route from one drawer to the other.
    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    expect(decisions).to_be_visible()
    expect(leaves).to_be_hidden()

    # Exchanging one covering drawer for another is lateral, so one Escape closes the
    # drawer standing and lands the user on the page; the drawer it replaced is not put
    # back, and they reach it the way they reached it the first time.
    page.keyboard.press("Escape")
    expect(decisions).to_be_hidden()
    expect(leaves).to_be_hidden()


def test_the_ring_is_one_box_around_the_whole_change(browser, serve):
    """A suggestion is one decision, so it wears one ring, whatever its slots are made of.

    The wrapper generated no box once — the same "take the form your content takes" with
    the box left out — and an element with none measures (0,0) at the document's origin,
    which is not a degenerate answer but a wrong one. Everything that asked the wrapper
    where it was believed it, so the travel centred the top of the document and a page
    whose open decisions were all suggestions answered `d` by appearing to do nothing at all.

    Hanging the ring on the pieces instead covered that and said the wrong thing about
    the change: two outlines meeting down the middle of a sentence, or stacked across
    two block slots, read as two boxes touching rather than as the one decision the user is
    standing in. So what is asserted here is that the user is taken to the change, and
    that the wrapper alone wears the mark, in one box reaching round both slots."""
    page = open_page(browser, serve(ASKS_PAGE))

    # Short enough that reaching the change is travel rather than a press with the
    # change already on screen.
    resized(page, 900, 400)

    # Where the change stands, which is where its contents paint — the wrapper's own
    # rect answers this question wrongly, which is the whole subject here. Whole in the
    # window rather than merely overlapping it: the bug leaves the change a little below
    # the fold, so "some part of it showing" is a bar the wrong answer can clear.
    fully_shown = """() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('sug-refill'));
      const box = r.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight; }"""

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision")).to_have_attribute(
        "data-lf-ask", "1"
    )
    # Where the user now stands, which is what the next press is measured against. The
    # bug takes them to the document's origin, so a scroll that ends *below* where they
    # started is the whole of what says they were carried to the change instead.
    #
    # Said that way rather than as "the change was off screen before the press": that was
    # true by a few dozen pixels, which made it a fact about how tall the blocks above the
    # change happened to be. Giving the question above it a label set one more line and
    # the precondition stopped holding, with nothing wrong anywhere.
    scroll_settled(page)
    was = page.evaluate("() => document.scrollingElement.scrollTop")
    assert was > 0, "the user must have somewhere to have come from"

    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")

    # The condition everything below rests on, stated rather than assumed: put
    # display: contents back on the wrapper and it measures (0,0), the mark paints
    # nothing, and the count further down passes on an element no user can see.
    box = page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    )
    assert box[0] > 40 and box[1] > 10, f"the wrapper drew no box to ring: {box}"

    # The travel is a glide, so the fact to wait on is that it has finished. Both
    # assertions are then about the landing: measured from the wrapper's own rect the
    # change sits at the document's origin, so the user is carried to the top of the
    # page — up from where they stood, with the change still below the fold.
    scroll_settled(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # What wears the mark: the wrapper, which carries the id every reader of the mark
    # asks after. Not the slots, and not the empty span the widget prepends to itself to
    # anchor its controls from — a 2px mark of its own beside the change is not the
    # promise.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-ask]')].map(e => {
      return { what: e.id || e.tagName, fragments: e.getClientRects().length,
               ring: getComputedStyle(e).outlineStyle !== 'none' };
    })""")
    assert [m["what"] for m in marks] == ["sug-refill"]
    assert marks[0]["ring"]
    # One fragment, so the outline closes round the change once. An inline box broken
    # around block children has three and draws no visible edge on any of them, which is
    # what a wrapper that only says `inline` gets for a change made of paragraphs.
    assert marks[0]["fragments"] == 1, marks

    # And the box reaches round both slots, which a ring on the pieces could not promise:
    # the user is standing in the change, not in half of it.
    assert page.evaluate("""() => {
      const w = document.getElementById('sug-refill').getBoundingClientRect();
      return ['refill-was', 'refill-now'].every(id => {
        const r = document.getElementById(id).getBoundingClientRect();
        return r.top >= w.top - 1 && r.bottom <= w.bottom + 1
            && r.left >= w.left - 1 && r.right <= w.right + 1; });
    }"""), "the wrapper's box does not reach round both slots"


def test_the_walk_travels_to_an_ask_a_page_left_boxless(browser, serve):
    """`display: contents` is one line of CSS, and a page or a project layer can put it
    on anything. Nothing in the shipped vocabulary carries it now, so this case only
    reaches the runtime from outside — which is where the reading has to hold, because
    an element generating no box measures (0,0) at the document's origin and every
    consumer that believes it travels to the top of the page.

    The travel reads where the content paints (shownBox), and the ring hangs on the
    boxes the decision shows through (shownParts) — the same answer an element-anchored
    comment's outline gives, so the walk's mark and the thread's cannot disagree about
    where a boxless decision is. The outermost mark still names the decision, one place for the
    user to be standing."""
    styled = ASKS_PAGE.replace(
        "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
    )
    page = open_page(browser, serve(styled))
    resized(page, 900, 400)

    # Asked of what the change paints, since the wrapper itself no longer says: this is
    # the reading the runtime has to take for the travel to land anywhere real. Whole in
    # the window because merely overlapping it is a state the glide passes through.
    fully_shown = """() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('sug-refill'));
      const box = r.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight; }"""

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision")).to_have_attribute(
        "data-lf-ask", "1"
    )
    scroll_settled(page)
    was = page.evaluate("() => document.scrollingElement.scrollTop")
    assert was > 0, "the user must have somewhere to have come from"

    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")
    assert page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    ) == [0, 0], "the page's own style no longer takes the wrapper's box away"
    scroll_settled(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # The decision and the boxes it shows through wear the mark, the decision outermost — one
    # place to stand, painted where the user can see it.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-ask]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the mark went somewhere else than the decision and its shown boxes: {marks}"
    expect(page.locator(STANDING_ASK)).to_have_count(1)


def test_a_commented_ask_does_not_wear_its_ring_on_the_runtime_s_own_note(
    browser, serve
):
    """The boxes a decision shows through are the page's, never the runtime's.

    The paint pass writes one hidden line per block holding a comment, saying how many
    it holds, and for an element anchor that line lands inside the element the anchor
    names. It is clipped to a pixel, so it has a box — and a wrapper that draws none of
    its own then had two children with area, its slot and the runtime's word about the
    page. Area alone kept the wrong ones out only by luck: the family's control line
    happens to be zero-wide, and this one is not.

    The order is why nothing caught it. The note is written after the marks are placed,
    so the first paint of a page sees no note and the ring is right; it moves onto the
    pixel on the next pass — which the Ask walk always is, the user having pressed a
    key. So the fault needs a comment on the page *and* a repaint, and shows as a 1px
    ring beside the change instead of on it.

    The shipped wrapper draws a box of its own now, so the page supplies the boxless
    one here — the line of CSS any page can write is what keeps this reachable."""
    url = serve(
        ASKS_PAGE.replace(
            "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Does this hold when the camera is offline?",
            "anchor": {"section": "sug-refill"},
        },
    )
    page = open_page(browser, url)
    # The note is what this test is about, so its presence is stated rather than assumed:
    # without it every assertion below holds for the wrong reason.
    expect_comment_notes(page, "#sug-refill", 1)

    page.keyboard.press("a")
    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")

    # By tag rather than by class: the slots are wearing the comment's own outline too,
    # this decision being the one that carries the comment, and a class would read that back
    # instead of naming the element.
    marks = page.evaluate("""() => [...document.querySelectorAll('[data-lf-ask]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the ring reached past the page's own boxes: {marks}"


# Charts. Every reading here is of the composed drawing rather than of the body it was
# built from: the body is Plot's options, and what the module owns is getting them to Plot
# and the drawing onto the page.
DREW = {
    # chart: (Plot's name for the mark group, shapes drawn, the element each is drawn as)
    "c-bars": ("bar", 6, "rect"),
    "c-rows": ("bar", 2, "rect"),
    "c-stack": ("bar", 4, "rect"),
    "c-line": ("line", 1, "path"),
    "c-dots": ("dot", 3, "circle"),
}


def test_every_mark_in_a_chart_body_reaches_the_drawing(browser, serve):
    """A chart that drew nothing still has a box and no console error, so the render gate
    passes it: the drawing is the one part of a chart no other reading looks at. Each
    body makes a different shape of call — rows handed to a mark, a faceted mark, marks
    stacked by Plot, a line over ISO dates on a time scale, dots — and each is counted
    rather than merely found, because a call that lost its data would still draw axes."""
    page = open_page(browser, serve(CHART_PAGE))
    for widget, (part, count, tag) in DREW.items():
        drew = page.evaluate(CHART_MARKS, widget)
        assert drew, f"{widget} drew nothing at all"
        shapes = drew["marks"].get(part, [])
        assert [shape[0] for shape in shapes] == [tag] * count, (widget, drew["marks"])


def test_the_gate_passes_a_chart_whose_tick_names_its_month_on_a_second_line(
    browser, serve
):
    """A dated axis names the month where one begins, on a line under the day: the tick
    for the first week of June reads 1 over Jun. Those two lines are two tspans of one
    <text>, offset by the dy the drawing asked for, and each reports a line box carrying
    the font's own leading — a couple of pixels taller than the step between them. So the
    pass hunting words drawn on other words read every such tick as a collision, on a
    drawing where no glyph comes near another, and the corpus's own heat-loss page failed
    the gate for drawing a perfectly ordinary axis.

    The reading is taken twice, as the float and the collapse are: once as the gate runs
    it, where the label's lines are held out, and once with that hold defeated, where it
    has to report. Otherwise a pass here would also be what a gate that never looked at
    the drawing returns. The two lines are pulled onto each other before either reading,
    so the second leg rests on an overlap this test arranged rather than on the leading
    the axis happens to be drawn with."""
    url = serve(CHART_PAGE)
    page = open_page(browser, url)
    # Vacuous otherwise: the page has to be carrying a tick that takes two lines.
    stacked = page.evaluate(
        """() => [...document.querySelectorAll('#c-line text')]
             .filter((t) => t.querySelectorAll('tspan').length > 1)
             .map((t) => t.textContent)"""
    )
    assert stacked, "no tick names its month on a second line, so nothing is held out"
    # The overlap the second reading needs belongs to the test rather than to whatever
    # leading Plot draws with: the month is pulled onto the day above it, so the two
    # boxes have to land on each other whatever step the drawing asked for. `held` does
    # not move, because the hold asks which label a line belongs to and not how far apart
    # a label's lines are.
    page.evaluate(
        """() => [...document.querySelectorAll('#c-line text')]
             .flatMap((t) => [...t.querySelectorAll('tspan')].slice(1))
             .forEach((line) => line.setAttribute('dy', '0'))"""
    )
    # The same named reading with its same-label hold disabled.
    held, reported = (
        render_checks_model.evaluate_probe(page, "coveredWords"),
        render_checks_model.evaluate_probe(
            page, "coveredWords", {"holdLabelLines": False}
        ),
    )
    assert held == []
    assert any("c-line" in found for found in reported), (
        "the lines land on nothing, so a gate that never looked would pass this too"
    )
    page.close()
    assert render_gate_model.render_version(browser, url).failures == []


@pytest.mark.parametrize("scroll_to_chart", [False, True])
def test_the_covered_words_gate_still_reads_two_of_a_chart_s_labels_on_each_other(
    browser, serve, scroll_to_chart
):
    """The other half of the exemption above, put back as a bug: a label's own lines are
    one run of words the drawing lays out together, and two labels landing on each other
    is the fault this pass exists to report. Arranged by standing one whole <text> on
    another rather than by spreading a label's lines, because the hold asks which <text>
    drew a line and not how far a line was moved.

    `<text>` is the case it is written for, being the near-miss that reads as one label
    and is not: every tick of an axis is a <text> inside one <g> inside one <svg>, so a
    hold reaching for either of those carries the whole drawing with it — every word of a
    chart stops being read against every other word of that chart — and nothing else in
    the suite would say so. The corpus sweeps and the copy assert this pass returns
    nothing, which a wider hold only makes more true, and the exemption above defeats the
    predicate wholesale, so it reports the same either way. The only standing bug-back on
    this pass reporting is the float's, and that is an HTML page whose runs never get an
    SVG label at all."""
    page = open_page(browser, serve(CHART_PAGE))
    # The root scrollport must not hide page-content collisions from this reading,
    # whether the chart starts below the fold or the user has scrolled to it.
    if scroll_to_chart:
        page.locator("#c-line").scroll_into_view_if_needed()
    # Two ticks the drawing places by transform, one stood on the other. The labels stay
    # whole, so what lands is two <text> elements rather than two lines of one.
    moved = page.evaluate(
        """() => {
            const ticks = [...document.querySelectorAll('#c-line text')]
                .filter((t) => t.hasAttribute('transform') && !t.querySelector('tspan'));
            if (ticks.length < 2) return null;
            ticks[1].setAttribute('transform', ticks[0].getAttribute('transform'));
            return [ticks[0].textContent, ticks[1].textContent];
        }"""
    )
    assert moved, "no two ticks the drawing places by transform, so nothing was stacked"
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    assert [f for f in covered if all(f'"{word}"' in f for word in moved)], (
        f"two of a chart's labels stood on each other unreported: {covered}"
    )


def test_a_chart_is_one_picture_named_by_its_author(browser, serve):
    """A drawing is where the body went: after the upgrade the numbers exist on the page
    as geometry, so a user on a screen reader hears whatever the drawing is named. The
    name is the author's `ariaLabel`, which is why a body without one is refused. Plot
    names every group inside the drawing too — `bar`, `x-axis tick label` — on <g>
    elements carrying no role, which axe reports as a serious failure; the drawing is one
    picture instead, and those names are kept as data a test can still ask for."""
    page = open_page(browser, serve(CHART_PAGE))
    drawing = page.locator("#c-bars svg[role=img]")
    assert drawing.get_attribute("aria-label") == (
        "Merged by quarter: apps 12, 19, 14; infra 7, 11, 17"
    )
    assert (
        page.evaluate("() => document.querySelectorAll('#c-bars g[aria-label]').length")
        == 0
    )
    assert (
        page.evaluate(
            "() => document.querySelectorAll('#c-bars g[data-lf-part=bar]').length"
        )
        > 0
    )
    # A colour ramp beside the drawing is an <svg> too, and not the picture.
    ramp = page.evaluate(
        """() => [...document.querySelectorAll('#c-dots .lf-chart-drawing svg')]
             .map((svg) => svg.getAttribute('role'))"""
    )
    assert ramp.count("img") == 1 and len(ramp) > 1, ramp
    assert (
        page.locator("#c-dots svg[role=img]").get_attribute("aria-label")
        == "Review minutes against lines changed: 12 and 4, 90 and 26, 310 and 71"
    )


def test_a_chart_wears_the_page_s_colors_and_turns_over_with_the_scheme(browser, serve):
    """A series takes the theme's token, `var(--series-N)`, which Plot writes into the
    drawing as it was given. Resolved to a value in JavaScript it would freeze the scheme
    the browser was in when the chart was drawn: a copy exported from a light window
    opens as a light slab for a dark user, and a scheme flipped mid-read leaves the
    drawing behind. So this asserts both halves: that each series is painted the token it
    names, and that no hex colour was written into the drawing at all. The flip is made
    with no reload, so the nodes under it are the same nodes; a drawing that had been
    painted values would fail here and pass every static check."""
    page = open_page(browser, serve(CHART_PAGE))

    def worn():
        drew = page.evaluate(CHART_MARKS, "c-bars")
        assert drew["painted"] == [], drew["painted"]
        fills = [fill for _, fill, _ in drew["marks"]["bar"]]
        return drew["tokens"], fills

    tokens, fills = worn()
    assert tokens[0] != tokens[1], "two series wearing one colour proves nothing"
    assert sorted(set(fills)) == sorted(tokens), (tokens, fills)

    page.emulate_media(color_scheme="dark")
    dark, fills = worn()
    assert dark != tokens, "the dark palette must differ, or the flip proves nothing"
    assert sorted(set(fills)) == sorted(dark), (dark, fills)
    # And the paper Plot fills its halos and tips with is the page's, not its white.
    assert (
        page.evaluate(
            """() => getComputedStyle(document.querySelector('#c-bars svg[role=img]'))
             .getPropertyValue('--plot-background').trim()"""
        )
        != "white"
    )


def test_a_chart_is_drawn_for_the_room_it_has_rather_than_scaled_into_it(
    browser, serve
):
    """A drawing that scales takes its labels with it. That is what a diagram does, and
    at 63% of its natural size a five-node flowchart's labels went under legibility; a
    chart has no natural size to keep, so it is drawn again for the width it now has and
    its text stays the size the theme set. The room changes for reasons a user never
    asked about — a window narrower than the column, the thread panel taking its strip
    out of one — so this is the ordinary case rather than a window somebody dragged."""
    page = open_page(browser, serve(CHART_PAGE))
    before = page.evaluate(CHART_MARKS, "c-bars")
    assert before["width"] == before["room"], before

    # Narrower than the column, which is where the room actually changes: the column is
    # capped, so a wider window leaves a chart exactly where it was.
    resized(page, 620, 900)
    page.wait_for_function(
        """(id) => {
            const el = document.getElementById(id);
            const svg = el.querySelector('svg[role=img]');
            return svg && Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
        }""",
        arg="c-bars",
    )
    after = page.evaluate(CHART_MARKS, "c-bars")
    assert after["room"] < before["room"], (before, after)
    # The painted box of a tick label, not its computed font-size: a drawing scaled by its
    # viewBox keeps the same computed size and renders smaller, so the property this test
    # is about is invisible to the one reading and plain in the other.
    assert after["tick"] == before["tick"], (before, after)


def test_a_chart_draws_into_the_box_its_data_height_states(browser, serve):
    """The page lays a chart's box out before Plot draws (x-height), so the drawing fills
    that box rather than sizing it: with a legend Plot sets above it, the legend and the
    drawing together end at the box's foot, and the box keeps the height it had at first
    paint. Drawn at the options' own height instead, the legend overhangs the box."""
    body = """{
  ariaLabel: "Merged by team: backend 12, frontend 19",
  color: {legend: true, range: ["var(--series-1)", "var(--series-2)"]},
  marks: [Plot.barY([{team: "backend", n: 12}, {team: "frontend", n: 19}],
                    {x: "team", y: "n", fill: "team"})],
}"""
    source = leaf_page(
        "tall chart",
        '<h1 id="t">Merged</h1>\n'
        + chart_markup("c-tall", body).replace(
            '<lf-chart id="c-tall">', '<lf-chart id="c-tall" data-height="240">'
        ),
    )
    page = open_page(browser, serve(source))
    box = page.evaluate(
        """() => {
            const el = document.getElementById('c-tall');
            const own = el.getBoundingClientRect();
            const drawing = el.querySelector('.lf-chart-drawing').getBoundingClientRect();
            const svg = el.querySelector('svg[role=img]').getBoundingClientRect();
            return {height: own.height, bottom: own.bottom,
                    drawing: drawing.bottom, svg: svg.bottom,
                    legends: el.querySelectorAll('svg:not([role=img]), div[class$=swatches]').length};
        }"""
    )
    assert box["height"] == 240, box
    assert box["legends"], box
    assert box["svg"] == box["drawing"] == box["bottom"], box


def test_a_body_the_module_cannot_draw_says_why_over_its_source(browser, serve):
    """The body is the author's, and the author is the only party who can fix it, so a
    refusal says what is wrong in the author's terms and keeps the source under it: code
    that does not parse, a chart with no name for a user who cannot see it, a call to
    something Plot does not export, a value that is not Plot's options, a drawing Plot
    already made, which is how Plot's own examples end, and a height the page could not
    have laid out before the chart drew. The author hears the same words as the page's
    `error` event, naming the chart, since the user seeing the box is not the author
    seeing it."""
    said = {
        "bad-syntax": "does not parse",
        "bad-label": "ariaLabel",
        "bad-mark": "Plot.barz is not a function",
        "bad-shape": "the options Plot.plot takes",
        "bad-drawn": "rather than Plot.plot(...)",
        "bad-height": "as data-height on the element",
    }
    for chart_id, body in BAD_CHARTS.items():
        source = leaf_page(
            "bad chart",
            f'<h1 id="t">Bad</h1>\n<lf-chart id="{chart_id}"><pre>\n{body}\n</pre></lf-chart>',
        )
        page = open_page(browser, serve(source))
        expect(page.locator(f"#{chart_id} .lf-error")).to_contain_text(said[chart_id])
        # The source stays under the message: a refusal the user cannot check is half a
        # refusal.
        expect(page.locator(f"#{chart_id} .lf-error pre")).to_contain_text("marks")
        report = f'<lf-chart id="{chart_id}"> failed: '
        consume_browser_errors(page, report)
        reported = []
        for _ in range(400):
            reported = [
                event["text"]
                for event in events_model.read_events(serve.page_dir)
                if event["kind"] == "error"
            ]
            if reported:
                break
            page.wait_for_timeout(25)
        assert len(reported) == 1 and reported[0].startswith(report), reported
        assert said[chart_id] in reported[0], reported


def test_a_chart_body_is_plot_code_that_reads_the_width_it_is_drawn_at(browser, serve):
    """The body is JavaScript, so what Plot takes as a function reaches it as one — here
    a tick format — and the body reads the width the host draws at, which is how it fits
    its labels to the room. The label below is the wider one only if the body was
    handed the width: without it, the comparison is false."""
    page = open_page(browser, serve(CHART_PAGE))
    ticks = page.locator(
        '#c-stack [data-lf-part="y-axis tick label"] text'
    ).all_text_contents()
    assert ticks and all(tick.endswith("h") for tick in ticks), ticks
    assert page.evaluate(CHART_MARKS, "c-rows")["room"] > 500
    expect(page.locator('#c-rows [data-lf-part="x-axis label"]')).to_contain_text(
        "open issues"
    )


def test_a_redraw_keeps_the_words_the_runtime_hung_on_the_chart(browser, serve):
    """A chart redraws for a new width, and the runtime writes inside widgets.

    A word the runtime hangs on the chart, such as a quiet word for a user listening, is a
    child of the element. Replacing the element's children to hold the new drawing takes
    it away, for the life of the tab, since nothing puts it back. So the drawing lives in
    a box of its own and the redraw replaces what is in that box.

    The room is changed by the window, the one thing that changes it; what this is about
    is that a redraw happened at all, which the drawing's own width says."""
    page = open_page(browser, serve(CHART_PAGE), context=None)
    page.wait_for_function("() => document.querySelector('#c-bars svg[role=img]')")
    plant_quiet_word(page, "#c-bars", "")
    read = """() => {
        const el = document.getElementById('c-bars');
        return { room: Math.round(el.clientWidth),
                 notes: el.querySelectorAll('.lf-ui').length,
                 drawn: Number(el.querySelector('svg[role=img]').getAttribute('width')) };
    }"""
    before = page.evaluate(read)
    assert before["notes"] > 0, "the chart holds no word of the runtime's"

    resized(page, 620, 900)
    page.wait_for_function(
        """(was) => {
            const el = document.getElementById('c-bars');
            const svg = el.querySelector('svg[role=img]');
            return svg && Number(svg.getAttribute('width')) !== was;
        }""",
        arg=before["drawn"],
    )
    after = page.evaluate(read)
    assert after["drawn"] < before["drawn"], (before, after)
    assert after["notes"] == before["notes"], (before, after)


def test_a_chart_in_a_closed_thread_draws_at_its_visible_width_when_opened(
    browser, serve
):
    """A chart an agent sends in a reply is markup like any other, which is why the body
    is JSON rather than a script: a message carries no module. It connects inside a
    closed panel and must draw at its visible width once the user opens the panel and
    the thread.

    A closed native details element can answer layout queries with a nonzero width.
    Read the visible drawing after opening both disclosures; an intermediate absence
    of SVG cannot distinguish a closed card from a drawing that has not finished.
    """
    url = serve(CHART_IN_A_MESSAGE_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-chart",
            "author": "user",
            "revision": 1,
            "text": "How did the quarter go?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-chart",
            "revision": 1,
            "text": "Like this:",
            "markup": chart_markup("msg-chart", MESSAGE_CHART),
        },
    )
    page = open_page(browser, url)
    assert (
        page.evaluate("() => document.getElementById('msg-chart').clientWidth") == 0
    ), "the panel must be shut, or there was a box all along"

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").click()
    expect(page.locator("#msg-chart svg[role=img]")).to_be_visible()
    page.wait_for_function(
        """() => {
            const el = document.getElementById('msg-chart');
            const svg = el.querySelector('svg[role=img]');
            return svg && Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
        }"""
    )
    drawn = page.evaluate(CHART_MARKS, "msg-chart")
    assert drawn["room"] > 100, drawn
    assert len(drawn["marks"]["bar"]) == 2, drawn


def _bound_diff(browser, serve, patch=MULTI_HUNK_PATCH):
    """The review the four diff tests below read, with its feed in place before the page
    loads. Bound rather than written inline because that is the form a review arrives in,
    and the only one whose rows are commentable data — `projectData` keys each by file,
    side and source line, which is the coordinate a remark on a line is recorded at."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    return page


@pytest.mark.parametrize("manifest", [False, True])
def test_a_diff_refresh_keeps_the_readers_inspection(browser, serve, manifest):
    """A new patch changes evidence, while wrap, file disclosure and reading position
    belong to the reader inspecting the same files."""
    url = serve(LONG_LINE_DIFF_PAGE)
    value = patch_manifest if manifest else lambda patch: patch
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(MULTI_HUNK_PATCH))
    page = open_page(browser, url)
    wrap = page.locator("lf-diff .lf-diff-wrap")
    wrap.click()
    page.locator("lf-diff summary").last.click()
    search = page.locator("lf-diff .lf-diff-search input")
    search.fill("handlers")
    row = page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",81]\']')
    row.scroll_into_view_if_needed()
    scroll_settled(page)
    reading = """() => {
      const diff = document.querySelector('lf-diff');
      return {scroll: scrollY, wrap: diff.wrapped(),
              files: diff.shownEntries().map(entry => entry.record.path),
              open: diff.fileEntries.map(entry => entry.details.open),
              focus: diff.shadowRoot.activeElement?.className,
              top: diff.lfDataDatum('[\"app/handlers.py\",\"new\",81]').getBoundingClientRect().top};
    }"""
    before = page.evaluate(reading)
    assert before["wrap"]
    if not manifest:
        changed_line = page.locator(
            'lf-diff [data-lf-datum=\'["app/routes.py","new",201]\']'
        )
        assert (
            changed_line.evaluate("el => el.closest('pre').dataset.overflow") == "wrap"
        )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        value(MULTI_HUNK_PATCH.replace("new route", "new routing")),
    )
    told(page)
    rendered(page)
    after = page.evaluate(reading)
    expect(search).to_have_value("handlers")
    assert after == before, (before, after)
    if not manifest:
        assert (
            changed_line.evaluate("el => el.closest('pre').dataset.overflow") == "wrap"
        )


@pytest.mark.parametrize("manifest", [False, True])
def test_a_changed_diff_file_keeps_its_sideways_reader(browser, serve, manifest):
    """Replacing a file's evidence retains its code scrollport and focused line."""
    url = serve(LONG_LINE_DIFF_PAGE)
    value = patch_manifest if manifest else lambda patch: patch
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(MULTI_HUNK_PATCH))
    page = open_page(browser, url)
    page.locator("lf-diff summary").first.click()
    page.keyboard.press("Tab")
    page.locator("lf-diff summary").first.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("]")
    page.keyboard.press("]")
    page.keyboard.press("]")
    reading = """() => {
      const diff = document.querySelector('lf-diff');
      const row = diff.lfDataDatum('[\"app/handlers.py\",\"new\",81]');
      return {scroll: scrollY, sideways: row.closest('code').scrollLeft,
              focus: diff.shadowRoot.activeElement?.dataset.lfDatum};
    }"""
    page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",81]\']').evaluate(
        "row => { row.closest('code').scrollLeft = 200; }"
    )
    scroll_settled(page)
    before = page.evaluate(reading)
    assert before["sideways"] == 200
    assert before["focus"] is not None
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        value(MULTI_HUNK_PATCH.replace("new first", "new beginning")),
    )
    told(page)
    rendered(page)
    after = page.evaluate(reading)
    assert after == before, (before, after)


@pytest.mark.parametrize("manifest", [False, True])
@pytest.mark.parametrize("inserts_line", [False, True])
def test_a_diff_refresh_keeps_a_selection_in_unchanged_lines(
    browser, serve, manifest, inserts_line
):
    """A change in another hunk does not take the passage the reader selected."""
    url = serve(LONG_LINE_DIFF_PAGE)
    value = patch_manifest if manifest else lambda patch: patch
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(MULTI_HUNK_PATCH))
    page = open_page(browser, url)
    row = page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",41]\']')
    row.scroll_into_view_if_needed()
    ends = row.evaluate("""row => {
      const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const start = node.textContent.indexOf('second');
        if (start < 0) continue;
        const range = document.createRange();
        range.setStart(node, start); range.setEnd(node, start + 'second'.length);
        const box = range.getBoundingClientRect();
        return [[box.left, box.top + box.height / 2], [box.right, box.top + box.height / 2]];
      }
    }""")
    select(page, *ends)
    before = page.evaluate("() => getSelection().toString()")
    assert before == "second"
    patch = MULTI_HUNK_PATCH.replace("new first", "new beginning")
    if inserts_line:
        patch = patch.replace("@@ -1,5 +1,5 @@", "@@ -1,5 +1,6 @@").replace(
            '+    return "new beginning"\n',
            '+    return "new beginning"\n+    inserted = True\n',
        )
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(patch))
    told(page)
    rendered(page)
    assert page.evaluate("() => getSelection().toString()") == before
    gutters = page.evaluate("""() => {
      const widget = document.querySelector('lf-diff');
      const entry = widget.fileEntries[0];
      return entry.lines.map(line => {
        const {gutterRow} = widget.threadPair(line.node);
        const number = String(line.side === 'old' ? line.oldLine : line.newLine);
        return {
          datum: line.node.dataset.lfDatum,
          commentInPairedGutter: line.comment.isConnected && line.comment.parentElement === gutterRow,
          column: gutterRow.dataset.columnNumber,
          label: gutterRow.querySelector('[data-line-number-content]').textContent,
          expected: number,
          lineTypeMatches: gutterRow.dataset.lineType === line.node.dataset.lineType,
          commentCount: gutterRow.querySelectorAll('.lf-diff-line-comment').length,
        };
      });
    }""")
    assert all(
        gutter["commentInPairedGutter"]
        and gutter["column"] == gutter["expected"]
        and gutter["label"] == gutter["expected"]
        and gutter["lineTypeMatches"]
        and gutter["commentCount"] == 1
        for gutter in gutters
    ), gutters


@pytest.mark.parametrize("starts_as_manifest", [False, True])
def test_a_closed_diff_file_reads_current_evidence_across_source_forms(
    browser, serve, starts_as_manifest
):
    """File disclosure keeps its owner and loads the current patch in either form."""
    url = serve(LONG_LINE_DIFF_PAGE)
    initial = (
        patch_manifest(MULTI_HUNK_PATCH) if starts_as_manifest else MULTI_HUNK_PATCH
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", initial)
    page = open_page(browser, url)
    code = page.locator("lf-diff code[data-code]").first
    code.evaluate("node => { node.scrollLeft = 200; }")
    summary = page.locator("lf-diff summary").first
    summary.click()
    patch = MULTI_HUNK_PATCH.replace("new first", "new beginning")
    next_value = patch if starts_as_manifest else patch_manifest(patch)
    data_model.cmd_data_set(serve.page_dir, "review-patch", next_value)
    told(page)
    rendered(page)
    summary.click()
    row = page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",2]\']')
    expect(row).to_contain_text("new beginning")
    assert code.evaluate("node => node.scrollLeft") == 200


def test_a_diff_recovers_when_a_failed_manifest_file_is_repaired(browser, serve):
    """A failed render cannot authorize reuse of the evidence its error removed."""
    url = serve(LONG_LINE_DIFF_PAGE)
    good = patch_manifest(MULTI_HUNK_PATCH)
    data_model.cmd_data_set(serve.page_dir, "review-patch", good)
    page = open_page(browser, url)
    bad = patch_manifest(MULTI_HUNK_PATCH)
    bad["files"][0]["patch"] = "invalid diff"
    data_model.cmd_data_set(serve.page_dir, "review-patch", bad)
    told(page)
    rendered(page)
    expect(page.locator("lf-diff .lf-error")).to_be_visible()
    data_model.cmd_data_set(serve.page_dir, "review-patch", good)
    told(page)
    rendered(page)
    expect(page.locator("lf-diff .lf-error")).to_have_count(0)
    expect(
        page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",2]\']')
    ).to_contain_text("new first")


@pytest.mark.parametrize("manifest", [False, True])
@pytest.mark.parametrize("starts_as_rename", [False, True])
def test_a_diff_file_keeps_focus_when_its_evidence_changes_kind(
    browser, serve, manifest, starts_as_rename
):
    """A path keeps its file controls; replaced presentation hands focus to that file."""
    rename = (
        "diff --git a/old.py b/app/handlers.py\n"
        "similarity index 100%\nrename from old.py\nrename to app/handlers.py\n"
    )
    regular = MULTI_HUNK_PATCH
    value = patch_manifest if manifest else lambda patch: patch
    initial, other = (rename, regular) if starts_as_rename else (regular, rename)
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(initial))
    page = open_page(browser, url)
    owner = page.locator("lf-diff .lf-diff-file").first.element_handle()
    comment = page.locator("lf-diff .lf-diff-file-comment").first.element_handle()
    if starts_as_rename:
        page.locator("lf-diff .lf-diff-file-comment").first.click()
        page.keyboard.press("Escape")
    else:
        page.locator("lf-diff summary").first.click()
        page.keyboard.press("ArrowRight")
    scroll_settled(page)
    before = page.evaluate("() => scrollY")
    for patch in (other, initial):
        data_model.cmd_data_set(serve.page_dir, "review-patch", value(patch))
        told(page)
        rendered(page)
        assert owner.evaluate("node => node.isConnected")
        assert comment.evaluate("node => node.isConnected")
        assert owner.evaluate("node => node.contains(node.getRootNode().activeElement)")
        assert page.evaluate("() => scrollY") == before
        if patch == regular:
            expect(
                page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",2]\']')
            ).to_contain_text("new first")
    if starts_as_rename:
        assert comment.evaluate("node => node === node.getRootNode().activeElement")
        data_model.cmd_data_set(serve.page_dir, "review-patch", value(regular))
        told(page)
        rendered(page)
    summary = page.locator("lf-diff summary").first
    summary.click()
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        value(regular.replace("new first", "new beginning")),
    )
    told(page)
    rendered(page)
    summary.click()
    expect(
        page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",2]\']')
    ).to_contain_text("new beginning")


@pytest.mark.parametrize("language", [None, "python"])
def test_a_text_document_refresh_keeps_selection_in_unchanged_text(
    browser, serve, language
):
    """Changing evidence beside a selected passage keeps its native selection."""
    tag = '<lf-text-document id="document" source="document-text"'
    if language:
        tag += f' language="{language}"'
    tag += "></lf-text-document>"
    source = LONG_LINE_DIFF_PAGE.replace(
        '<lf-diff id="patch" source="review-patch" review><pre></pre></lf-diff>', tag
    )
    url = serve(source)
    data_model.cmd_data_set(
        serve.page_dir, "document-text", 'first = "old"\nsecond = "selected"\n'
    )
    page = open_page(browser, url)
    code = page.locator("lf-text-document code")
    code.scroll_into_view_if_needed()
    ends = code.evaluate("""row => {
      const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const start = node.textContent.indexOf('selected');
        if (start < 0) continue;
        const range = document.createRange();
        range.setStart(node, start); range.setEnd(node, start + 'selected'.length);
        const box = range.getBoundingClientRect();
        return [[box.left, box.top + box.height / 2], [box.right, box.top + box.height / 2]];
      }
    }""")
    select(page, *ends)
    reading = "() => ({selection: getSelection().toString(), scroll: scrollY})"
    before = page.evaluate(reading)
    assert before["selection"] == "selected"
    data_model.cmd_data_set(
        serve.page_dir,
        "document-text",
        'first = "new beginning"\nsecond = "selected"\n',
    )
    told(page)
    rendered(page)
    expect(code).to_contain_text('first = "new beginning"')
    assert page.evaluate(reading) == before


@pytest.mark.parametrize("manifest", [False, True])
@pytest.mark.parametrize("changes_kind", [False, True])
def test_a_diff_refresh_leaves_an_inline_reply_to_its_thread_owner(
    browser, serve, manifest, changes_kind
):
    """A replacement carries its source focus; core carries the reply and its caret."""
    patch = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
    )
    next_patch = (
        "diff --git a/old.py b/a.py\nsimilarity index 100%\n"
        "rename from old.py\nrename to a.py\n"
        if changes_kind
        else patch.replace("+new\n", "+newer\n")
    )
    value = patch_manifest if manifest else lambda patch: patch
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(patch))
    page = open_page(browser, url)
    row = page.locator('lf-diff [data-lf-datum=\'["a.py","new",1]\']')
    row.hover()
    page.get_by_title("Comment on a.py · new line 1", exact=True).click()
    write(page.locator(".lf-composer leaf-text"), "Please clarify this.")
    with sending(page, "a line comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    reply = page.locator("lf-diff .lf-diff-thread-outlet .lf-thread-reply leaf-text")
    draft = "An unsent reader draft"
    write(reply, draft)
    page.keyboard.press("Home")
    for _ in range(3):
        page.keyboard.press("ArrowRight")
    for _ in range(4):
        page.keyboard.press("Shift+ArrowRight")
    reading = "e => ({scroll: scrollY, value: e.value, start: e.selectionStart, end: e.selectionEnd})"
    before = reply.evaluate(reading)
    assert before["end"] - before["start"] == 4
    data_model.cmd_data_set(serve.page_dir, "review-patch", value(next_patch))
    told(page)
    rendered(page)
    current = page.locator(".lf-thread-reply leaf-text:focus-within")
    expect(current).to_have_js_property("value", draft)
    assert current.evaluate(reading) == before


def test_a_diff_disclosure_waits_for_the_source_render_that_owns_its_evidence(
    browser, serve
):
    """Opening a retained closed file joins a pending revision without a false error."""

    def patch(path, word):
        return (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1 +1 @@\n-old\n+{word}\n"
        )

    def value(word):
        return patch_manifest(patch("a.py", word) + patch("b.py", "second"))

    url = serve(MANIFEST_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", value("first"))
    page = open_page(browser, url)
    a = page.locator("lf-diff summary").nth(0)
    b = page.locator("lf-diff summary").nth(1)
    a.click()
    expect(page.locator('lf-diff [data-lf-datum=\'["a.py","new",1]\']')).to_have_text(
        "first"
    )
    b.click()
    line = page.locator('lf-diff [data-lf-datum=\'["b.py","new",1]\']')
    expect(line).to_have_text("second")
    b.click()
    data_model.cmd_data_set(serve.page_dir, "review-patch", value("middle"))
    told(page)
    rendered(page)
    held = []

    def hold(route):
        if "key=a.py" in route.request.url:
            held.append((route, route.fetch()))
        else:
            route.continue_()

    page.route("**/api/deferred*", hold)
    data_model.cmd_data_set(serve.page_dir, "review-patch", value("latest"))
    holding(page, held, 1, "the new open-file evidence")
    b.click()
    # Let the native toggle and its lazy load answer while the source revision is held.
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    try:
        assert page.locator("lf-diff .lf-error").count() == 0
    finally:
        for route, response in held:
            route.fulfill(response=response)
    rendered(page)
    expect(line).to_have_text("second")
    expect(page.locator('lf-diff [data-lf-datum=\'["a.py","new",1]\']')).to_have_text(
        "latest"
    )
    expect(page.locator("lf-diff .lf-error")).to_have_count(0)


WEB_AWESOME_SHEET = """sheets => sheets.some(
  sheet => [...sheet.cssRules].some(rule => rule.cssText.includes('wa-color-picker'))
)"""


def test_webawesome_chrome_loads_without_optional_controls(browser, serve):
    plain = open_page(browser, serve(leaf_page("Plain", "<h1>Plain page</h1>")))
    assert (
        plain.evaluate(f"() => ({WEB_AWESOME_SHEET})(document.adoptedStyleSheets)")
        is True
    )
    assert not any(
        entry.endswith("/vendor/webawesome.esm.js")
        for entry in plain.evaluate(
            "() => performance.getEntriesByType('resource').map(entry => entry.name)"
        )
    )

    assert plain.evaluate("() => customElements.get('wa-input') !== undefined")
    assert plain.evaluate("() => customElements.get('wa-switch') === undefined")

    playground = open_page(browser, serve(PLAYGROUND_PAGE))
    assert (
        playground.evaluate(f"() => ({WEB_AWESOME_SHEET})(document.adoptedStyleSheets)")
        is True
    )
    control = playground.locator("lf-playground wa-switch").first
    # A page rule with no specificity at all. It can outrank the generated sheet's own
    # `:is(wa-switch, …)` mapping only because that sheet sits in @layer lf-vendor.
    playground.add_style_tag(
        content=":where(wa-switch){--wa-color-text-quiet: rgb(1, 2, 3);}"
    )
    assert (
        control.evaluate(
            "el => getComputedStyle(el).getPropertyValue('--wa-color-text-quiet')"
        ).strip()
        == "rgb(1, 2, 3)"
    ), "the package theme must outrank the lazy vendor defaults"


def test_webawesome_theme_reaches_a_declared_shadow_stage(browser, serve):
    page = _bound_diff(browser, serve)
    diff = page.locator("lf-diff")
    assert diff.evaluate("el => el.shadowRoot !== null")
    assert (
        diff.evaluate(f"el => ({WEB_AWESOME_SHEET})(el.shadowRoot.adoptedStyleSheets)")
        is True
    )


# A phrase late in the diff's longest line: unwrapped it is off the right of the box, and
# wrapped it is on a line box of its own — the two states the test below is about.
_DIFF_TAIL = "whichever remote it came from"
# The line is one row split across syntax spans inside a shadow root, so the range is built
# over its text nodes rather than dragged: a pointer drag cannot reach words that are off
# the box in the state this starts in.
_SELECT_IN_ROW = """(row, phrase) => {
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
    const nodes = [], starts = [];
    let flat = '';
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      starts.push(flat.length); nodes.push(node); flat += node.data;
    }
    const start = flat.indexOf(phrase);
    if (start < 0) return null;
    const at = (offset) => {
      const index = starts.findLastIndex((value) => value <= offset);
      return [nodes[index], offset - starts[index]];
    };
    const range = document.createRange();
    range.setStart(...at(start));
    range.setEnd(...at(start + phrase.length));
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    // The row is a block, so it has one client rectangle however many line boxes are in
    // it, and its height is what says how many. Whether the words selected were on screen
    // is the range's own right edge against the file's scrolling box — not the row's,
    // which is sized to the longest line in the file so its fill reaches the end of it.
    const box = row.closest('code[data-code]').getBoundingClientRect();
    return { text: selection.toString(),
             height: Math.round(row.getBoundingClientRect().height),
             cut: range.getBoundingClientRect().right > box.right };
}"""


def test_a_diff_row_fills_to_the_end_of_its_line_and_to_the_end_of_a_narrow_box(
    browser, serve
):
    """A changed row says it changed by the colour behind it, and that colour is the row's
    own background, so it stops where the row's box stops. The renderer sizes the code
    column to the box that scrolls, which is the width the user could already see: on
    this patch the fill ran out 2,563px short of the line's end, so scrolling right left
    every addition and deletion sitting on the file's plain paper with nothing to say
    which it was.

    Every direction in one reading, because they are one track. The floor that carries the
    fill past the scrollport would, left alone, shrink a short file's rows to its own
    longest line and leave the rest of the box blank; and it measures whatever stands in
    that column, so a user's own remark would size the file too. Then again with the
    rows wrapped, where the scrollbar is gone and the room is all there is."""
    page = _bound_diff(browser, serve)

    filled = page.evaluate(DIFF_ROW_FILL)
    assert filled["rows"] > 20 and filled["scrolls"] > 0, (
        f"no file runs past its box, so a filled result would prove nothing: {filled}"
    )
    assert filled["short"] == 0, (
        f"a row's fill stops before its own text ends, worst by {filled['gap']}px: "
        f"{filled}"
    )
    assert filled["narrow"] == 0, f"a row's fill stops before its box does: {filled}"

    # A thread stands in the code column with the lines, and its prose unwrapped is far
    # wider than any of them, so the floor would take it for a line and size the file by
    # the longest remark. `app/routes.py` is what makes that reading sharp: its rows fit
    # their box, so a comment that reached the measure starts a file the user could see
    # whole scrolling sideways — 671px of rows in a 718px box became 796px in 843px.
    page.locator('lf-diff [data-lf-datum=\'["app/routes.py","new",201]\']').evaluate(
        _SELECT_IN_ROW, "new route"
    )
    page.get_by_role("button", name="Comment on selection").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "A remark of the ordinary length a reviewer writes, long enough that the line it "
        "would make unwrapped runs well past the longest line in this file, which is the "
        "whole of what the column is supposed to be measuring.",
    )
    with sending(page, "the comment on the short file's line"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("lf-diff .lf-diff-thread-outlet")).to_be_visible()

    remarked = page.evaluate(DIFF_ROW_FILL)
    assert remarked["scrolls"] == filled["scrolls"], (
        f"a remark sized the code, so a file that fit its box now scrolls: {remarked}"
    )
    assert (remarked["short"], remarked["narrow"]) == (
        0,
        0,
    ), f"the rows do not fill their box with a thread among them: {remarked}"

    page.locator("lf-diff .lf-diff-wrap").click()
    wrapped = page.evaluate(DIFF_ROW_FILL)
    assert wrapped["rows"] == filled["rows"] and wrapped["scrolls"] == 0, (
        wrapped,
        filled,
    )
    assert (wrapped["short"], wrapped["narrow"]) == (
        0,
        0,
    ), f"wrapped rows do not fill the box they wrapped into: {wrapped}"


def test_a_wrapped_diff_shows_every_line_whole_and_paper_wraps_whatever_the_switch_says(
    browser, serve
):
    """A diff line is `white-space: pre` inside a box that scrolls sideways, so the only
    way to read the end of a long one is a scrollbar at the foot of the whole file. On the
    shipped review that bar sits about 24,000px below the line being read, which is not an
    answer at all; on paper there is no bar and the text is simply gone — 40 of that
    patch's 2,348 rows came out cut, the worst by 744px.

    Three claims, and the middle one is why the other two are in the same test. The switch
    wraps and unwraps: pressed off again the rows are cut again, so it is the switch doing
    it rather than the page having settled differently. And paper wraps with the switch
    off, because the sheet cannot be left holding an answer nobody can press.

    The unwrapped reading is the population as well as the anchor: a clean wrapped result
    means nothing unless the same reading, on the same rows, can see a cut line."""
    page = _bound_diff(
        browser,
        serve,
        MULTI_HUNK_PATCH + "\ndiff --git a/old.py b/new.py\nsimilarity index 100%\n"
        "rename from old.py\nrename to new.py\n",
    )
    expect(page.locator("lf-diff .lf-diff-rename")).to_be_visible()
    switch = page.locator("lf-diff .lf-diff-wrap")

    cut = page.evaluate(DIFF_CLIPPING)
    assert cut["rows"] > 20, f"nothing to read: {cut}"
    assert cut["cut"] > 0 and cut["worst"] > 300, (
        f"no line runs past its box, so a wrapped result would prove nothing: {cut}"
    )
    # Which line, not just how many. The rows are all one width now — each is sized to the
    # longest line in its file so its fill reaches the end of it — so a reading taken off
    # the row's box rather than its text reports the file's overhang for every row alike
    # and still satisfies the count above. Naming the line is what tells the two apart.
    assert cut["widest"].strip().startswith('return "The comparison base'), (
        f"the reading does not name the line that overflows, so it is measuring the rows' "
        f"boxes rather than their text: {cut}"
    )

    switch.click()
    wrapped = page.evaluate(DIFF_CLIPPING)
    assert wrapped["rows"] == cut["rows"], (wrapped, cut)
    assert wrapped["cut"] == 0, f"wrapped and still cut off: {wrapped}"

    switch.click()
    assert page.evaluate(DIFF_CLIPPING)["cut"] == cut["cut"], (
        "unwrapping left the lines inside their box, so the switch was not what wrapped "
        "them"
    )

    # Paper also takes the "Mark reviewed" press off each file, and the row it stood ahead
    # of is pulled back up over where it was: with the press gone the pull has nothing to
    # take back, and it drew every file's header 24px inside the file before it. The row
    # starts at its wrapper's top in both media, which is where it would with no press.
    placed = page.evaluate(DIFF_ROW_PLACEMENT)
    assert placed["files"] == 3 and (placed["lift"], placed["drop"]) == (
        0,
        0,
    ), f"a file's row does not start where its wrapper does: {placed}"
    page.emulate_media(media="print")
    printed = page.evaluate(DIFF_CLIPPING)
    on_paper = page.evaluate(DIFF_ROW_PLACEMENT)
    page.emulate_media(media="screen")
    assert printed["rows"] == cut["rows"], (printed, cut)
    assert printed["cut"] == 0, (
        f"the switch is off and paper cannot press it, so this text is gone: {printed}"
    )
    assert on_paper["files"] == 3 and (on_paper["lift"], on_paper["drop"]) == (
        0,
        0,
    ), f"on paper a file's row is drawn above its own wrapper: {on_paper}"


def test_a_diff_keeps_the_file_named_while_its_hunks_go_past_and_lands_below_that_name(
    browser, serve
):
    """Two halves of one question — which file am I reading, and where did that press put
    me. The shipped review is 46 files and 32,000px: opening one and reading down it left
    nothing on screen saying whose lines these were, because the file's header stood in
    flow and scrolled away with its own first rows.

    Pinned, the header stands exactly where the banner ends. A press then has to land
    past it:
    `scrollIntoView` reads the document's scroll-padding, which reserves the banner, and
    the header's own height is added to that as the rows' scroll-margin — measured,
    because a long path wraps and no stylesheet can work that number out.

    Reduced motion so the landing read is the product's and not the frame a smooth scroll
    happened to be on. The walk starts from the tools row, which belongs to no file, so
    the first `]` is the first hunk and the second is the step this test is about."""
    page = _bound_diff(browser, serve)
    page.emulate_media(reduced_motion="reduce")

    in_flow = page.evaluate(DIFF_LANDING)
    assert in_flow["headTop"] > in_flow["bannerBottom"], (
        f"the header already meets the banner before anything scrolled: {in_flow}"
    )
    page.evaluate(
        """() => {
            const file = document.querySelector('lf-diff').shadowRoot
                .querySelector('details');
            file.scrollIntoView({ block: 'start' });
            window.scrollBy(0, 200);
        }"""
    )
    pinned = page.evaluate(DIFF_LANDING)
    assert pinned["headTop"] == pinned["bannerBottom"], (
        f"the file's name is not against the banner: {pinned}"
    )
    assert pinned["bannerBottom"] == in_flow["bannerBottom"], (
        "the banner moved, so the header meeting it says nothing"
    )
    # The press drawn onto that line came with it. It stands outside the disclosure, so
    # nothing about the summary pinning moves it; placed against the file's top it stayed
    # there and scrolled off under the banner, leaving the pinned header's column empty
    # and "Mark reviewed" out of reach for the whole of the file it names. Reached by a
    # pointer as well as measured, because a box can stand on the line and still be
    # painted under the header.
    press = page.evaluate(DIFF_PRESS)
    assert abs(press["top"] - (press["headTop"] + 5)) <= 2, (
        f"the review press is not on the pinned header's line: {press}"
    )
    assert press["hit"] == "review", (
        f"a pointer on the press reaches something else: {press}"
    )
    # And it leaves with the file. A sticky box is held inside its containing block by
    # its margin box, so a negative margin on the press lent it that much travel past
    # the file's end: with the header unpinned and gone, the press stood on for 32px of
    # scroll over the next file's header and that file's own press. Scrolled to where
    # the file's foot is 15px under the banner's edge, the press's foot is no lower than
    # the file's.
    page.evaluate(
        """() => {
            const file = document.querySelector('lf-diff').shadowRoot
                .querySelector('.lf-diff-file').getBoundingClientRect();
            const banner = document.querySelector('.lf-banner').getBoundingClientRect();
            window.scrollBy(0, file.bottom - banner.bottom + 15);
        }"""
    )
    leaving = page.evaluate(DIFF_PRESS)
    assert leaving["fileBottom"] < pinned["bannerBottom"], (
        f"the file has not left the banner's edge, so nothing is being measured: {leaving}"
    )
    assert leaving["bottom"] <= leaving["fileBottom"], (
        f"the review press outlives its file: {leaving}"
    )
    page.evaluate("() => window.scrollTo(0, 0)")

    page.locator("lf-diff .lf-diff-wrap").focus()
    page.keyboard.press("]")
    first = page.evaluate(DIFF_LANDING)
    assert first["line"] == "1", f"the first hunk of the first file: {first}"
    expect(page.locator(".lf-walk-position")).to_have_text("Hunk 1 of 3")

    page.keyboard.press("]")
    landed = page.evaluate(DIFF_LANDING)
    expect(page.locator(".lf-walk-position")).to_have_text("Hunk 2 of 3")
    assert landed["line"] == "40", (
        f"the next hunk starts at new line 40, which its @@ header says: {landed}"
    )
    assert landed["path"] == "app/handlers.py", landed
    assert landed["top"] >= landed["headBottom"], (
        f"the row it landed on is behind the file's own pinned header: {landed}"
    )
    assert landed["headTop"] == landed["bannerBottom"], (
        f"the header is not pinned where the landing was measured against: {landed}"
    )
    page.keyboard.press("}")
    expect(page.locator(".lf-walk-position")).to_have_text("File 2 of 2")
    page.keyboard.press("Alt+ArrowDown")
    expect(page.locator(".lf-walk-position")).to_have_text("File 1 of 2 unreviewed")


def test_a_diff_in_a_pane_pins_the_file_name_at_the_pane_top_and_lands_below_it(
    browser, serve
):
    """The same two halves inside a full-height workspace pane, whose body is the box that
    scrolls the rows. The header used to stop the banner's height below the pane's top,
    because the offset it pinned at was the window's: rows scrolled past in the 42px
    above the name that headed them, and a `]` landing, which aligns to the pane's own
    top, put the row above its header. Where a sticking box stops is `--lf-top`, and a
    scrolling pane body declares it as its own top edge.

    Short enough a window that the patch overflows the pane, and still tall enough that
    the workspace holds it."""
    url = serve(PANE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1024, "height": 560})
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    page.emulate_media(reduced_motion="reduce")
    scrollport = """() => {
        const body = document.querySelector('lf-diff');
        return { top: Math.round(body.getBoundingClientRect().top),
                 scrolls: body.scrollHeight > body.clientHeight,
                 window: document.scrollingElement.scrollTop };
    }"""
    pane = page.evaluate(scrollport)
    assert pane["scrolls"], f"the patch fits its pane, so nothing can pin: {pane}"

    page.evaluate("() => { document.querySelector('lf-diff').scrollTop = 200; }")
    pinned = page.evaluate(DIFF_LANDING)
    assert pinned["headTop"] == pane["top"], (
        f"the file's name is not at the top of the pane that scrolls it: {pinned}, {pane}"
    )
    page.evaluate("() => { document.querySelector('lf-diff').scrollTop = 0; }")

    page.locator("lf-diff .lf-diff-wrap").focus()
    page.keyboard.press("]")
    page.keyboard.press("]")
    expect(page.locator(".lf-walk-position")).to_have_text("Hunk 2 of 3")
    landed = page.evaluate(DIFF_LANDING)
    assert landed["line"] == "40", landed
    assert landed["headTop"] == pane["top"], (
        f"the header is not pinned where the landing was measured against: {landed}"
    )
    assert landed["top"] >= landed["headBottom"], (
        f"the row it landed on is above or behind its file's pinned header: {landed}"
    )
    assert page.evaluate(scrollport)["window"] == 0, "the window scrolled, not the pane"
    # The landed row wears the band where it can be seen: inside the code box that clips
    # it and below the header pinned over the row above. Drawn outset, its sides fell
    # outside that box and its upper run under the header, and the row showed no ring.
    row_ring = page.evaluate(f"""() => {{
        const at = document.querySelector('lf-diff').shadowRoot.activeElement;
        return ({_RING_WITHIN})(at, at.closest('code'));
    }}""")
    # Its right run is the row's end, as far off as the file's longest line, which the
    # code box scrolls sideways to reach; the other three are on screen.
    inside = row_ring["inside"]
    assert row_ring["drawn"] and inside["top"] and inside["bottom"], row_ring
    # And the code box has not moved sideways. The row runs past the box, so a landing
    # that let the browser bring it "nearest" scrolled the box to the row's start, the
    # width of the line numbers over it, hiding every line's marker and first characters.
    assert row_ring["sideways"] == 0 and inside["left"], (
        f"the landing scrolled the file's lines sideways under their numbers: {row_ring}"
    )
    assert row_ring["top"] >= landed["headBottom"], (
        f"the landed row's ring runs under its file's pinned header: {row_ring}"
    )
    # The pane's body is a Tab stop because it scrolls, and it fills its pane, so its
    # band stays inside the pane: the pane draws it inset over the body's cell
    # (theme.css), where outset on the body the workspace body clipped its right and
    # lower runs.
    page.evaluate("() => document.querySelector('lf-diff').focus()")
    host_ring = page.evaluate(
        """() => {
          const host = document.querySelector('lf-diff');
          const pane = host.closest('[data-lf-reading-role="pane"]');
          const band = getComputedStyle(pane, '::after');
          return { focus: host.matches(':focus-visible'),
                   own: getComputedStyle(host).outlineStyle,
                   band: [band.outlineStyle, band.outlineWidth,
                          parseFloat(band.outlineOffset) + parseFloat(band.outlineWidth)] };
        }"""
    )
    assert host_ring["focus"] and host_ring["own"] == "none", host_ring
    assert host_ring["band"][:2] == ["solid", "2px"] and host_ring["band"][2] <= 0, (
        host_ring
    )


# Where an element's focus band falls, from its computed outline, and whether that box
# stays inside `frame`'s border box, which is what clips it or covers its edge.
_RING_WITHIN = """(el, frame) => {
    const s = getComputedStyle(el);
    const out = parseFloat(s.outlineOffset) + parseFloat(s.outlineWidth);
    const box = el.getBoundingClientRect(), edge = frame.getBoundingClientRect();
    const ring = { top: box.top - out, left: box.left - out,
                   right: box.right + out, bottom: box.bottom + out };
    return { drawn: s.outlineStyle === 'solid' && s.outlineWidth === '2px',
             focus: el.matches(':focus-visible'), top: Math.round(ring.top),
             sideways: frame.scrollLeft,
             inside: { top: ring.top >= edge.top, left: ring.left >= edge.left,
                       right: ring.right <= edge.right,
                       bottom: ring.bottom <= edge.bottom } };
}"""


@pytest.mark.parametrize(
    "engine", ["browser", "webkit_browser"], ids=["chromium", "webkit"]
)
@pytest.mark.parametrize("wide_host", [False, True], ids=["code", "outer-reader"])
def test_horizontal_wheel_reaches_the_diff_reader(request, serve, engine, wide_host):
    """A fitting code box lets horizontal input reach its enclosing reader in WebKit too."""
    source = leaf_page(
        "Nested patch reader",
        '<h1>Review</h1><div id="reader" data-bound="start">'
        '<lf-diff id="patch"><pre>'
        "diff --git a/reading.py b/reading.py\n"
        "--- a/reading.py\n+++ b/reading.py\n@@ -1 +1 @@\n"
        '-return "The previous release remains available for inspection."\n'
        '+return "The current release remains available for inspection."\n'
        "</pre></lf-diff></div>",
        head="<style>#reader { width: 500px; }"
        f"#patch {{ width: {1000 if wide_host else 300}px; }}</style>",
    )
    driver = request.getfixturevalue(engine)
    url = serve(source)
    page = open_page(driver, url)
    resized(page, 1000, 900)
    code = page.locator("#patch code[data-code]")
    reader = page.locator("#reader") if wide_host else code
    assert reader.evaluate("el => el.scrollWidth > el.clientWidth")
    if wide_host:
        assert code.evaluate("el => el.scrollWidth === el.clientWidth")
    box = code.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 120, box["y"] + 25)
    page.mouse.wheel(200, 0)
    page.wait_for_function(
        "wide => { const host = document.querySelector('#patch'); "
        "const box = wide ? document.querySelector('#reader') : "
        "host.shadowRoot.querySelector('code[data-code]'); return box.scrollLeft > 0; }",
        arg=wide_host,
    )
    assert reader.evaluate("el => el.scrollLeft") > 0


@pytest.mark.parametrize("left", [0, 150])
def test_a_diff_hunk_landing_preserves_sideways_reading_outside_its_shadow_tree(
    browser, serve, left
):
    """A hunk step moves vertically without travelling sideways through its host."""
    source = leaf_page(
        "Sideways patch",
        '<h1>Review</h1><div id="sideways">'
        '<lf-diff id="patch" source="review-patch" review><pre></pre></lf-diff>'
        "</div>",
        head="<style>#sideways { width: 500px; overflow: auto; }"
        "#patch { width: 1000px; }</style>",
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.keyboard.press("Tab")
    page.locator("#patch summary").first.focus()
    page.locator("#sideways").evaluate("(el, left) => { el.scrollLeft = left; }", left)
    before = page.locator("#sideways").evaluate("el => el.scrollLeft")
    assert before == left
    page.keyboard.press("]")
    expect(page.locator(".lf-walk-position")).to_have_text("Hunk 1 of 3")
    scroll_settled(page)
    assert page.locator("#sideways").evaluate("el => el.scrollLeft") == before


def test_a_backward_hunk_step_from_the_diff_itself_opens_one_file_and_lands_in_it(
    browser, serve
):
    """The mirror of the first `]` above, from the same standing: nothing focused inside
    the diff. That is where an in-page link to the diff's own id leaves a user, since
    `focusDestination` focuses the host, and the diff's keys answer there because the
    scope climb starts at the focused node itself.

    Going forward, nothing-focused meant every hunk lay ahead and the walk stopped at the
    first. Going back it meant every hunk lay ahead too, so none lay behind: the walk ran
    through the whole list, opened each file and fetched its lines, and landed nowhere. A
    collapsed manifest is where that costs — one fetch per file — so the reading here is
    the fetch count and the open count beside the landing, on the review's last hunk."""
    url = serve(MANIFEST_DIFF_PAGE)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch_manifest(MULTI_HUNK_PATCH),
    )
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    fetched = []
    page.on(
        "request",
        lambda request: (
            fetched.append(request.url) if "/api/deferred" in request.url else None
        ),
    )
    # Focused as `focusDestination` leaves a host that an in-page link named.
    page.evaluate(
        """() => {
            const diff = document.querySelector('lf-diff');
            diff.tabIndex = -1;
            diff.focus();
        }"""
    )
    assert page.evaluate("() => document.activeElement.localName") == "lf-diff"
    assert (
        page.evaluate(
            "() => document.querySelector('lf-diff').shadowRoot.activeElement"
        )
        is None
    ), "the standing this test is about is nothing focused inside the diff"

    page.keyboard.press("[")
    page.wait_for_function(
        """() => {
            const at = document.querySelector('lf-diff').shadowRoot.activeElement;
            return at && at.dataset.line !== undefined;
        }"""
    )
    landed = page.evaluate(DIFF_LANDING)
    assert landed["line"] == "200", f"the last file's last hunk starts at 200: {landed}"
    assert landed["path"] == "app/routes.py", landed
    opened = page.evaluate(
        "() => document.querySelector('lf-diff').shadowRoot"
        ".querySelectorAll('details[open]').length"
    )
    assert opened == 1, f"the step opened files it never reached: {opened} open"
    assert len(fetched) == 1, (
        f"one file's lines were needed, {len(fetched)} were fetched"
    )


def test_a_comment_on_a_wrapped_diff_line_names_the_line_an_unwrapped_one_names(
    browser, serve
):
    """Wrapping is a decision about line boxes; a comment's coordinate is a decision about
    lines of the patch. A wrapped line is still one line to the anchor, so the same words
    selected in the same row record the same coordinate either way — file, side, and
    source line — or turning the switch on would quietly move where a remark lands.

    The same row and the same phrase both times, with wrap the only difference, and the
    row's own box is read to prove that difference was real: one line tall and running
    past its box unwrapped, several lines tall and whole wrapped. Two identical anchors
    off a line that never wrapped would be asserting nothing at all."""
    page = _bound_diff(browser, serve)
    row = page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",81]\']')

    flat = row.evaluate(_SELECT_IN_ROW, _DIFF_TAIL)
    assert flat["text"] == _DIFF_TAIL, flat
    assert flat["cut"], f"the words selected are inside the box already: {flat}"
    page.get_by_role("button", name="Comment on selection").click()
    write(
        page.locator(".lf-composer leaf-text"), "Unwrapped, this line runs off the box."
    )
    with sending(page, "the comment on the unwrapped line"):
        page.keyboard.press("ControlOrMeta+Enter")

    page.locator("lf-diff .lf-diff-wrap").click()
    folded = row.evaluate(_SELECT_IN_ROW, _DIFF_TAIL)
    assert folded["text"] == _DIFF_TAIL, folded
    assert folded["height"] > flat["height"] and not folded["cut"], (
        f"the line did not wrap, so both anchors describe one geometry: {folded}"
    )
    page.get_by_role("button", name="Comment on selection").click()
    write(
        page.locator(".lf-composer leaf-text"), "Wrapped, the same words are on screen."
    )
    with sending(page, "the comment on the wrapped line"):
        page.keyboard.press("ControlOrMeta+Enter")

    anchors = [
        event["anchor"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("anchor")
    ]
    assert len(anchors) == 2, anchors
    assert (
        anchors[0]
        == anchors[1]
        == {
            "section": "patch",
            "datum": '["app/handlers.py","new",81]',
            "quote": _DIFF_TAIL,
            "source": "review-patch",
            "source_revision": row.get_attribute("data-lf-source-revision"),
        }
    ), anchors


def test_a_control_a_widget_built_is_told_from_a_label_it_wrote(browser, serve):
    """One rule, read off the marker `offer` already writes, rather than each widget
    deciding for itself whether the user can press what it drew.

    The measured fault was that they could not tell: on the command hub a chip that
    opened a section and a badge that counted something computed the same ground, the
    same ink, the same 999px corner and the same 11.5px size, so the only way to learn
    which was which was to press one. That is not a fact about chips — it is what happens
    when "this is pressable" has no owner, and every widget that draws a small filled
    shape has to remember to say it again.

    So the layer says it once, against `data-lf-offer`, and the value is what it reads:
    `offer` writes the tag, input type, or role for a thing to press and the empty string
    for the rest of the chrome it builds — a controls row, a history disclosure, an edit
    box. A badge
    the page wrote carries no marker at all and needs no exclusion, which is the half
    worth pinning: the rule stays off it because the marker means what it says, not
    because a list of static classes is kept beside the rule.

    Three registers, because a pointer, a hand and a keyboard arrive by different routes
    and only one of them is on screen at rest. The hand is the resting answer, and a
    control with nothing left to do gives it up along with the face it wore while it was
    live. The face is read as that change and not as the layer's own `.55`, for the
    reason the ring below is: a control is free to dress its own spent state and outrank
    the floor, and the composer's submit does — an empty Send trades an accent disc for a
    muted ring on paper at full opacity, so that a field with nothing in it reads as
    quiet rather than as broken. Pinning the number would pin whichever of the two
    happened to be on this page. The badges are
    read outside a choose group on purpose: a card group makes the whole option the
    press, so a chip inside one inherits the hand from the control it is sitting in and
    would be answering this question about its parent. The wash is the aim, read as a
    change against each control's own resting shadow rather than against a constant: a
    control is free to wear a drop shadow of its own, and several here do, so an
    absolute reading would pin the theme's current furniture instead of the rule. The
    ring is the keyboard's, and this is the half of it a shared rule has to get right by
    losing: a control with a ring of its own keeps it and keeps its name, so what is
    asserted here is that a named ring is drawn and not which rule drew it. Which box
    wears it is a separate question from which one holds the focus - a joined option group
    draws it on the row its picks give up, and getComputedStyle(activeElement) reports
    'no ring' for a control whose ring is perfectly fine. Where nothing else claims one,
    the shared rule is what draws it, and that case is asserted on a request press in
    test_render_projection.py, which is where the layer has a control no widget rings."""
    page = open_page(browser, serve(CHIP_PAGE))
    state = """() => lfUnwatched(() => {
      // Whatever a control spends on saying it is live: the layer's wash, its own ink
      // and ground, and the disc a compose submit paints in its ::before.
      const face = (el) => [getComputedStyle(el), getComputedStyle(el, '::before')]
        .map((cs) => [cs.opacity, cs.color, cs.backgroundColor, cs.borderTopColor,
                      cs.filter].join(' '))
        .join(' / ');
      // The same control with the fact of being spent lifted off it, and put straight
      // back: the comparison is against what this control would wear with something
      // left to do, not against a number. The lift is the test's own write, outside
      // what the page is held to (`lfUnwatched`).
      const armed = (el) => {
        const native = el.disabled;
        const declared = el.getAttribute('aria-disabled');
        if (native) el.disabled = false;
        if (declared !== null) el.removeAttribute('aria-disabled');
        const reading = face(el);
        if (native) el.disabled = true;
        if (declared !== null) el.setAttribute('aria-disabled', declared);
        return reading;
      };
      const kind = (el) => {
        const cs = getComputedStyle(el);
        const off = el.matches('[aria-disabled="true"], :disabled');
        return {cursor: cs.cursor, opacity: cs.opacity, off,
                face: face(el), armed: off ? armed(el) : null};
      };
      const presses = [...document.querySelectorAll('[data-lf-offer]')]
        .filter((el) => el.dataset.lfOffer !== '');
      const said = [document.querySelector('#intro > .tag'),
                    document.querySelector('#t-camera .lf-chips > span')];
      return {
        presses: presses.map(kind), said: said.map(kind),
        saidMarked: said.map((el) => el.hasAttribute('data-lf-offer')),
      };
    })"""
    rest = page.evaluate(state)
    live = [p for p in rest["presses"] if not p["off"]]
    spent = [p for p in rest["presses"] if p["off"]]
    assert live and spent and len(rest["said"]) == 2, (
        f"the page is missing one of the three populations this compares: {rest}"
    )
    assert all(p["cursor"] == "pointer" for p in live), (
        f"a control a widget built does not take the hand: {live}"
    )
    assert all(p["cursor"] == "default" and p["face"] != p["armed"] for p in spent), (
        f"a control with nothing left to do still offers itself: {spent}"
    )
    assert not any(s["cursor"] == "pointer" for s in rest["said"]), (
        "a label the page wrote takes the hand, so the user is invited to press words"
    )
    assert rest["saidMarked"] == [False, False], (
        "a static label carries the control marker, so the rule is being kept off it by "
        "an exclusion rather than by the marker meaning what it says"
    )
    # The aim. The wash is an inset shadow so that it deepens whatever fill the control
    # already wears instead of contesting the `background` its own widget wrote, which is
    # what lets it be read as an addition to whatever the control had at rest.
    shadow = "el => getComputedStyle(el).boxShadow"
    mark = page.locator("#p-keep .lf-pick")
    before = mark.evaluate(shadow)
    mark.hover()
    washed = mark.evaluate(shadow)
    assert washed != before and "inset" in washed, (
        f"the control under the pointer says nothing about being pressed: "
        f"{before!r} -> {washed!r}"
    )
    tag = page.locator("#intro > .tag")
    tag_rest = tag.evaluate(shadow)
    tag.hover()
    assert tag.evaluate(shadow) == tag_rest, (
        "a label the page wrote answers the pointer as though it were a control"
    )

    # The keyboard. Reached by a real Tab, because :focus-visible is a fact about how
    # focus arrived and element.focus() alone draws no ring at all.
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    ring = page.evaluate(
        """() => { const on = document.activeElement.closest('lf-option')
                          ?? document.activeElement;
             const cs = getComputedStyle(on);
             return [cs.outlineStyle, cs.outlineWidth,
                     cs.getPropertyValue('--focus-ring-w').trim(),
                     cs.getPropertyValue('--lf-focus-ring').trim()]; }"""
    )
    assert ring[0] == "solid" and ring[1] == ring[2] and ring[3] != "none", (
        f"nothing draws a named focus ring where the keyboard is standing: {ring}"
    )


def test_a_phone_can_wrap_diff_lines_by_tapping_the_label(iphone, serve):
    patch = (
        "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+" + "long_line " * 40 + "\n"
    )
    page = open_page(
        None,
        serve(
            leaf_page(
                "Phone diff",
                '<h1>Review</h1><lf-diff id="patch"><pre>' + patch + "</pre></lf-diff>",
            )
        ),
        context=iphone,
    )
    label = page.locator(".lf-diff-wrap-label")
    line = page.locator("lf-diff [data-line]").last
    expect(line).to_have_css("white-space", "pre")
    assert label.bounding_box()["height"] >= 44
    before = line.bounding_box()["height"]
    label.tap()
    expect(line).to_have_css("white-space", "pre-wrap")
    assert line.bounding_box()["height"] > before
    label.tap()
    expect(line).to_have_css("white-space", "pre")


def test_a_phone_keeps_the_diff_file_name_and_the_sticky_header_height(iphone, serve):
    """The space reserved above a landed row clears its sticky file header. The
    basename remains readable on a phone; the title retains the complete path."""
    path = "plugins/worktrunk/skills/worktrunk/reference/config.md"
    patch = (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    page = open_page(
        None,
        serve(
            leaf_page(
                "Phone header",
                '<h1>Review</h1><lf-diff id="patch" review><pre>'
                + patch
                + "</pre></lf-diff>",
            )
        ),
        context=iphone,
    )
    page.wait_for_function("() => document.querySelector('lf-diff.lf-rendered')")
    head = page.evaluate(
        """() => {
        const head = document.querySelector('lf-diff').shadowRoot
            .querySelector('summary');
        const path = head.querySelector('.lf-diff-path');
        const base = path.querySelector('.lf-diff-base');
        return {
            height: head.getBoundingClientRect().height,
            reserved: parseFloat(getComputedStyle(
                head.parentElement.querySelector('[data-line]')
            ).scrollMarginTop),
            title: path.title,
            base: base.textContent,
            baseCut: base.scrollWidth > base.clientWidth,
        };
    }"""
    )
    assert head["height"] == pytest.approx(head["reserved"], abs=0.5), head
    assert head["base"] == "config.md" and not head["baseCut"], head
    assert head["title"] == path, head


# A page-authored driver that points at a code block's lines through its declared `for`,
# from its first connection, before the block's lazy tokenizer has put any line in.
POINTER_REGISTRY = {
    "lf-pointer": {
        "description": "Points at lines of the code block its `for` names.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
            "for": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
        },
        "required": ["id", "for"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-refers": {"for": {}},
        "x-upgrade": True,
    }
}
POINTER_MODULE = """import { indicate } from "/runtime/widget-api.js";
customElements.define("lf-pointer", class extends HTMLElement {
  connectedCallback() { indicate(this, "for", "3-4"); }
  disconnectedCallback() { indicate(this, "for", null); }
  point(key) { return indicate(this, "for", key); }
});
"""


def test_a_widget_indicates_lines_of_a_code_block_without_moving_the_page(
    browser, serve
):
    """One widget marks part of another through a reference its entry declares: here
    a driver standing for a film, and the code block whose lines it is executing.

    The mark is the page's own state, like hover, so it is asserted where a user meets
    it: the lines the key names wear it and nothing else does, the
    block's authored `hi` line keeps its own face, a comment painted on a marked line
    still paints, and neither the scroll nor the focus moves as the indication does."""
    url = serve(
        leaf_page(
            "indication",
            """
<h1 id="t">Bracket</h1>
<p id="lede">The function below is the whole rule.</p>
<div style="height: 1400px"></div>
<lf-code id="walk" language="python" hi="2"><pre>
def bracket(temp):
    if temp &lt; 0:
        return "steel"
    return "cedar"
print(bracket(3))
</pre></lf-code>
<lf-pointer id="film" for="walk"></lf-pointer>
""",
        ),
        layer_registry=POINTER_REGISTRY,
        layer_widgets={"lf-pointer.js": POINTER_MODULE},
    )
    page = open_page(browser, url)
    lines = page.locator("#walk .lf-code-line")
    expect(lines).to_have_count(5)
    indicated = page.locator("#walk .lf-code-line[data-lf-indicated]")

    def marked():
        return lines.evaluate_all(
            """ls => ls.flatMap((l, i) => l.hasAttribute('data-lf-indicated')
                   ? [i + 1] : [])"""
        )

    # Asked for before the block had lines; resolved when the render stated them. No
    # comment stands yet, so no thread list lays itself out and says so on the way.
    expect(indicated).to_have_count(2)
    assert marked() == [3, 4]
    expect(page.locator("#walk .lf-code-line.hi")).to_have_count(1)

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-steel",
            "author": "user",
            "revision": 1,
            "text": "Why steel?",
            "anchor": {"section": "walk", "quote": 'return "steel"'},
        },
    )
    told(page)
    page.wait_for_function(
        """() => [...(CSS.highlights.get('lf-mark') ?? [])]
                   .some(r => r.toString().includes('steel'))"""
    )
    assert marked() == [3, 4]

    faces = lines.evaluate_all(
        "ls => ls.map(l => getComputedStyle(l, '::before').boxShadow)"
    )
    assert faces[2] != "none" and faces[0] == "none" and faces[1] == "none", faces

    before = page.evaluate("[scrollY, document.activeElement.localName]")
    assert page.evaluate("document.querySelector('#film').point('2,5')") is True
    assert marked() == [2, 5]
    expect(page.locator("#walk .lf-code-line.hi")).to_have_count(1)
    assert page.evaluate("document.querySelector('#film').point('9')") is False
    assert marked() == []
    page.evaluate("document.querySelector('#film').point('3')")
    assert marked() == [3]
    assert "steel" in painted(page, "lf-mark")
    assert page.evaluate("[scrollY, document.activeElement.localName]") == before

    page.evaluate("document.querySelector('#film').point(null)")
    assert marked() == []
    page.evaluate("document.querySelector('#film').point('1')")
    page.evaluate("document.querySelector('#film').remove()")
    assert marked() == [], "a driver that leaves takes its indication with it"


def test_an_excerpt_shows_and_answers_to_its_source_line_numbers(browser, serve):
    """An lf-code body with `lines` is a quotation from a longer file. What the user
    reads is the file's own numbering: the gutter counts from where the quote starts
    and jumps where it skips, each skip stands as an elided row saying how much is
    left out, and the gutter widens so four digits still leave the code in line with
    its notes. Everything that points into the block — `hi`, a note's `at`, a driver's
    indication — names lines by those numbers. A left-out number addresses the elided
    row standing for it, so a note placed there is that row's caption, and a number
    outside the block addresses nothing. A copied excerpt is the quoted source and the
    authored notes, never the numbers or the elided rows' counts."""
    url = serve(
        leaf_page(
            "excerpt",
            """
<h1 id="t">Runs</h1>
<p id="lede">The loop that finds each run.</p>
<lf-code id="walk" language="rust" lines="1505-1507,1550-1552" hi="1550"><pre>
fn merge_sort()
{
    let len = v.len();
    while end &gt; 0 {
        let mut start = end - 1;
        start -= 1;
</pre>
<lf-note at="1551">One run per pass.</lf-note>
<lf-note id="gap" at="1520">Setup, left out.</lf-note>
</lf-code>
<lf-pointer id="film" for="walk"></lf-pointer>
""",
        ),
        layer_registry=POINTER_REGISTRY,
        layer_widgets={"lf-pointer.js": POINTER_MODULE},
    )
    page = open_page(browser, url)
    rows = page.locator("#walk pre > *")
    expect(rows).to_have_count(8)
    assert rows.evaluate_all(
        """rs => rs.map(r => r.classList.contains('lf-code-elided')
                   ? ['elided', r.dataset.elided, r.textContent]
                   : r.localName === 'lf-note' ? ['note']
                   : [getComputedStyle(r, '::before').content, r.classList.contains('hi')])"""
    ) == [
        ['"1505"', False],
        ['"1506"', False],
        ['"1507"', False],
        ["elided", "42 lines", "Setup, left out."],
        ['"1550"', True],
        ['"1551"', False],
        ["note"],
        ['"1552"', False],
    ]

    code_x, note_x = page.evaluate(
        """() => {
          const start = (node) => {
            const range = document.createRange();
            range.setStart(node.firstChild.firstChild ?? node.firstChild, 0);
            return range.getBoundingClientRect().left;
          };
          return [start(document.querySelector('#walk .lf-code-line')),
                  start(document.querySelector('#walk pre > lf-note'))];
        }"""
    )
    assert abs(code_x - note_x) < 1, (code_x, note_x)

    # The caption sits after the gutter and the count, on the elided row's own line.
    gutter, caption = page.evaluate(
        """() => [document.querySelector('#walk .lf-code-line').getBoundingClientRect(),
                  document.querySelector('#gap').getBoundingClientRect()]
                 .map(r => [r.left, r.height])"""
    )
    assert caption[0] > code_x and caption[1] < 2 * gutter[1], (gutter, caption)

    marked = page.locator("#walk pre > [data-lf-indicated]")
    rows_of = "ls => ls.map(l => l.dataset.line ?? `${l.dataset.from}-${l.dataset.to}`)"
    assert page.evaluate("document.querySelector('#film').point('1507-1550')") is True
    assert marked.evaluate_all(rows_of) == ["1507", "1508-1549", "1550"]
    assert page.evaluate("document.querySelector('#film').point('1520')") is True
    assert marked.evaluate_all(rows_of) == ["1508-1549"]
    assert page.evaluate("document.querySelector('#film').point('3')") is False
    expect(marked).to_have_count(0)

    # The user drags from the excerpt's first word to its last.
    ends = page.locator("#walk pre").evaluate(
        """pre => {
          const walker = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT,
            (node) => node.data.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP);
          const texts = [];
          for (let node = walker.nextNode(); node; node = walker.nextNode()) texts.push(node);
          const glyph = (node, at) => {
            const range = document.createRange();
            range.setStart(node, at);
            range.setEnd(node, at + 1);
            return range.getBoundingClientRect();
          };
          const first = texts[0], last = texts.at(-1);
          const a = glyph(first, first.data.search(/\\S/));
          const b = glyph(last, last.data.trimEnd().length - 1);
          return [[a.left, a.top + a.height / 2], [b.right, b.top + b.height / 2]];
        }"""
    )
    select(page, *ends)
    copied = page.evaluate("() => getSelection().toString()")
    # The notes come along on lines of their own, as authored text; the numbers,
    # the elided mark and its count do not.
    assert copied == (
        "fn merge_sort()\n{\n    let len = v.len();\nSetup, left out.\n"
        "    while end > 0 {\n        let mut start = end - 1;\nOne run per pass.\n"
        "        start -= 1;"
    )


def test_a_code_line_longer_than_its_block_wraps_under_its_own_indent(browser, serve):
    """A line longer than its lf-code block wraps inside the frame rather than running
    past it behind a scrollbar, where a reader on a narrow window never saw its end. The
    rows after the first hang two characters past the line's own indent, so a wrapped
    call deep in a block stays under the code it belongs to, and the gutter stands the
    whole height of the line. What no line box can break, a hash, breaks anywhere."""
    call = "        return compute(" + ", ".join(f"arg_{i}" for i in range(40)) + ")"
    digest = "".join(f"{i:02x}" for i in range(100))
    url = serve(
        leaf_page(
            "wrap",
            f"""
<h1 id="t">Wrap</h1>
<lf-code id="walk" language="python"><pre>
def ceiling(limit):
{call}
{digest}
</pre></lf-code>
""",
        )
    )
    page = open_page(browser, url)
    expect(page.locator("#walk .lf-code-line")).to_have_count(3)
    reading = page.evaluate(
        """() => {
          const pre = document.querySelector('#walk pre');
          const [first, ...long] = pre.querySelectorAll('.lf-code-line');
          const glyph = document.createRange();
          const text = document.createTreeWalker(first, NodeFilter.SHOW_TEXT).nextNode();
          glyph.setStart(text, 0);
          glyph.setEnd(text, 1);
          const {left: codeX, width: ch} = glyph.getBoundingClientRect();
          // Each row's first painted glyph, in characters from the first line's first.
          const rows = (line) => {
            const range = document.createRange();
            range.selectNodeContents(line);
            const starts = new Map();
            for (const r of range.getClientRects()) {
              if (!r.width || !r.height) continue;
              const top = Math.round(r.top);
              starts.set(top, Math.min(starts.get(top) ?? Infinity, r.left));
            }
            return [...starts].sort(([a], [b]) => a - b)
              .map(([, left]) => Math.round((left - codeX) / ch));
          };
          return {
            scrolls: pre.scrollWidth > pre.clientWidth,
            rows: long.map(rows),
            gutterSpans: long.map((line) =>
              getComputedStyle(line, '::before').height ===
                `${line.getBoundingClientRect().height}px`),
          };
        }"""
    )
    assert reading["scrolls"] is False, reading
    call_rows, digest_rows = reading["rows"]
    # The call's leading spaces are text, so its first row starts at the code's edge.
    assert call_rows[0] == 0 and len(call_rows) > 1, reading
    assert set(call_rows[1:]) == {10}, reading
    assert digest_rows[0] == 0 and len(digest_rows) > 1, reading
    assert set(digest_rows[1:]) == {2}, reading
    assert reading["gutterSpans"] == [True, True], reading
