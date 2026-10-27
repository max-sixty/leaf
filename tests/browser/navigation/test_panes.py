"""Reading keys and the reader's place in workspace panes and bounded blocks, across
scroll behaviors, drags and revisions."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import NESTED_PROPOSAL_PAGE, executable_revision, live_url
from render_cases_layout import page_at_rest, ring_faults, rings_drawn
from render_cases_navigation import pending_text, wait_for_pending_mark
from render_harness import (
    CORPUS_SOURCES,
    EXAMPLES,
    RELEASE_FOCUS,
    comment_note,
    holding,
    leaf_page,
    margins_laid_out,
    open_page,
    open_threads,
    pane_scroll_behavior,
    panel_settled,
    panel_view,
    resized,
    round_trip,
    scroll_settled,
    stamp_page,
    suggestion_control,
    wait_for_revision,
    write,
)

from browser.navigation import (
    READING_REGIONS_PAGE,
)
from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


# The half-page keys; the line keys take the same scroll chain.
@pytest.mark.parametrize(("down", "up"), [("d", "u")])
def test_reading_keys_chain_at_a_document_bound_but_stop_at_a_task_boundary(
    browser, serve, down, up
):
    """Reading steps follow the browser's scroll chain, including nested bounds,
    but a workspace pane keeps its task's boundary."""
    content = (
        '<div id="reader" data-bound="start">'
        + "<p>Run log line.</p>" * 100
        + '</div><div style="height:1500px"></div>'
    )
    for workspace in (False, True):
        source = (
            leaf_page(
                "A bounded task",
                '<header><h1>Task</h1></header><lf-pane id="task" label="Task">'
                "<div>" + content + "</div></lf-pane>",
                layout="workspace",
            )
            if workspace
            else leaf_page("A bounded document reader", "<h1>Reader</h1>" + content)
        )
        page = open_page(browser, serve(source))
        reader = page.locator("#reader")
        outer_selector = "#task > :not(header, footer)" if workspace else "html"
        outer = page.locator(outer_selector)
        assert reader.evaluate("box => box.scrollHeight > box.clientHeight")
        reader.focus()
        reader.evaluate("box => box.scrollTop = box.scrollHeight")
        before = outer.evaluate("box => box.scrollTop")
        page.keyboard.press(down)
        page.wait_for_function(
            "({selector, before}) => document.querySelector(selector).scrollTop > before",
            arg={"selector": outer_selector, "before": before},
        )
        scroll_settled(page, outer_selector)
        before = outer.evaluate("box => box.scrollTop")
        reader.evaluate("box => box.scrollTop = 0")
        page.keyboard.press(up)
        page.wait_for_function(
            "({selector, before}) => document.querySelector(selector).scrollTop < before",
            arg={"selector": outer_selector, "before": before},
        )
        if workspace:
            outer.evaluate("box => box.scrollTop = box.scrollHeight")
            reader.evaluate("box => box.scrollTop = box.scrollHeight")
            page.keyboard.press(down)
            scroll_settled(page, outer_selector)
            assert page.evaluate("document.scrollingElement.scrollTop") == 0


def test_a_focused_reading_surface_preserves_its_passage_on_reflow(browser, serve):
    paragraphs = "".join(
        f'<p id="passage-{number}">Paragraph {number}. '
        + "The current passage stays readable when the viewport changes width. " * 10
        + "</p>"
        for number in range(12)
    )
    source = leaf_page(
        "A focused reading surface",
        f'<lf-pane id="reading" label="Reading"><div tabindex="0">{paragraphs}</div></lf-pane>',
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    body = page.locator("#reading > div")
    body.focus()
    body.press("PageDown")
    scroll_settled(page, "#reading > div")
    rendered(page)
    landmark = body.evaluate("""body => {
        const top = body.getBoundingClientRect().top;
        return [...body.querySelectorAll('p')].find(
            p => p.getBoundingClientRect().top >= top).id;
    }""")
    assert body.evaluate("body => body.scrollTop") > 0
    resized(page, 390, 900)
    rendered(page)
    expect(body).to_be_focused()
    box = page.locator(f"#{landmark}").bounding_box()
    assert 0 <= box["y"] < 900, "the surface itself displaced its current passage"


@pytest.mark.parametrize("workspace", [True, False])
def test_reading_keys_follow_the_focused_pane_without_moving_its_sibling(
    browser, serve, workspace
):
    source = READING_REGIONS_PAGE
    if not workspace:
        # A bounded pane in document flow keeps its reading body even when the
        # document could carry its header or footer by scrolling instead.
        source = (
            source.replace('class="layout-workspace"', 'class="layout-column"')
            .replace(
                "</head>",
                "<style>#reading-split lf-pane { block-size: 300px; }"
                " #reading-split lf-pane > :not(header, footer)"
                " { min-block-size: 0; overflow: auto; overscroll-behavior: contain; }"
                "</style></head>",
            )
            .replace("</main>", '<div style="height:1500px"></div></main>')
        )
    page = open_page(browser, serve(source))
    if not workspace:
        assert page.evaluate(
            "document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight"
        )
    left = page.locator("#left-reading > :not(header, footer)")
    right = page.locator("#right-reading > :not(header, footer)")
    ranges = page.evaluate(
        """() => Object.fromEntries(['left-reading', 'right-reading'].map(id => {
          const body = document.querySelector(`#${id} > :not(header, footer)`);
          return [id, body.scrollHeight - body.clientHeight];
        }))"""
    )
    assert min(ranges.values()) > 300, ranges

    page.locator("#left-head").focus()
    page.keyboard.press("d")
    page.wait_for_function(
        "() => document.querySelector('#left-reading > :not(header, footer)').scrollTop > 0"
    )
    page.wait_for_timeout(250)
    assert right.evaluate("el => el.scrollTop") == 0
    assert page.evaluate("document.scrollingElement.scrollTop") == 0
    left_position = left.evaluate("el => el.scrollTop")

    page.locator("#right-head").focus()
    page.keyboard.press("d")
    page.wait_for_function(
        "() => document.querySelector('#right-reading > :not(header, footer)').scrollTop > 0"
    )
    page.wait_for_timeout(250)
    assert left.evaluate("el => el.scrollTop") == left_position
    assert page.evaluate("document.scrollingElement.scrollTop") == 0

    # Footer focus still names the pane for reading keys; the footer itself does not
    # become content inside the body scroller.
    page.locator("#left-foot").focus()
    page.keyboard.press("u" if workspace else "k")
    page.wait_for_function(
        f"() => document.querySelector('#left-reading > :not(header, footer)').scrollTop < {left_position}"
    )
    assert page.evaluate("document.scrollingElement.scrollTop") == 0


def test_a_click_on_a_panes_words_makes_it_the_subject_of_every_scroll_key(
    browser, serve
):
    """A click on words focuses nothing, and Chrome then starts Space, PageDown and the
    arrows from the node last pressed. A permanent `tabindex` on body made the body the
    focusable ancestor of every word, so the click focused it and those keys scrolled the
    root, which a full-height workspace keeps still: both panes stayed at 0. Leaf's own `d` and
    `j` read only focus and did the same."""
    left_body = "#left-reading > :not(header, footer)"
    page = open_page(browser, serve(READING_REGIONS_PAGE))
    tops = """() => ['left-reading', 'right-reading'].map((id) =>
      document.querySelector(`#${id} > :not(header, footer)`).scrollTop)"""

    page.locator("#left-start").click()
    page.keyboard.press("j")
    page.wait_for_function(f"() => ({tops})()[0] > 0")
    scroll_settled(page, left_body)
    stepped = page.evaluate(tops)[0]
    page.keyboard.press("PageDown")
    page.wait_for_function(f"() => ({tops})()[0] > {stepped}")
    scroll_settled(page, left_body)
    left, right = page.evaluate(tops)
    assert right == 0, (left, right)

    page.locator("#right-start").click()
    reading = """async () => (await window.__lfCheckApi()).userReadingRegion()?.host.id ?? null"""
    assert page.evaluate(reading) == "right-reading"
    page.keyboard.press("d")
    page.wait_for_function(f"() => ({tops})()[1] > 0")
    scroll_settled(page, "#right-reading > :not(header, footer)")
    assert page.evaluate(tops)[0] == left
    # Escape still takes the user off a control, with no stop of its own on body, and
    # lands them on what they are reading in the pane they stood in: the page outside
    # the panes holds only its header, and landing there left `u` with nothing to move.
    page.locator("#left-head").focus()
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    assert page.evaluate(reading) == "left-reading"
    page.keyboard.press("u")
    page.wait_for_function(f"() => ({tops})()[0] < {left}")


def test_a_closed_threads_panel_hands_the_page_back_where_the_user_was_reading(
    browser, serve
):
    """The Threads list is a reading region of its own, and it used to stand in for the
    page's after the panel closed or while the user left it: `d` after a pointer closed
    the panel scrolled a list no one could see, and `g p` from the open panel landed at
    the top of the document rather than on the paragraph in view."""
    paragraphs = "".join(
        f'<p id="p{n}" style="min-height: 12rem">Paragraph {n} has '
        f'<a href="#p{n}">a link</a>.</p>'
        for n in range(12)
    )
    page = open_page(
        browser, serve(leaf_page("A long page", f"<h1>A long page</h1>{paragraphs}"))
    )
    resized(page, 1440, 900)
    page.locator("#p8").evaluate("p => p.scrollIntoView({block: 'start'})")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(panel_view("threads"))).to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("p")
    page.keyboard.press("Tab")
    assert page.evaluate(
        """() => {
          const at = document.activeElement.getBoundingClientRect();
          return document.activeElement.matches('main a') &&
            at.top > 0 && at.bottom < innerHeight;
        }"""
    )

    open_threads(page)
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    top = page.evaluate("document.scrollingElement.scrollTop")
    page.keyboard.press("d")
    page.wait_for_function(f"() => document.scrollingElement.scrollTop > {top}")


def test_a_let_go_never_lands_in_a_closed_fold(browser, serve):
    """A closed `<details>` keeps its contents' boxes where they would stand open, as an
    inactive tab's panel does, so where the fold sat just above the window the let-go
    took a paragraph inside it for what the user was reading. Focus cannot land in a
    closed fold, so closing Threads left the user on its toggle instead of the page."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "closed fold",
                "<h1>Fold</h1>"
                + "".join(f"<p>Before {i}.</p>" for i in range(20))
                + '<details id="fold"><summary>More</summary>'
                "<p>Words inside a closed fold.</p></details>"
                + "".join(f"<p>After {i}.</p>" for i in range(60)),
            )
        ),
    )
    resized(page, 1280, 800)
    # The summary passes above the window, and the closed words would stand below it.
    page.evaluate(
        """() => {
          const fold = document.getElementById('fold');
          fold.scrollIntoView({block: 'start', behavior: 'instant'});
          const summary = fold.querySelector('summary').getBoundingClientRect();
          document.scrollingElement.scrollTop += summary.bottom + 2;
        }"""
    )
    scroll_settled(page)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(panel_view("threads"))).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")


def test_a_pane_bodys_ring_is_drawn_whole_against_the_workspace_edges(browser, serve):
    """A pane body with nothing in it to Tab to is a stop of its own (reach.js), and the
    layer's ring stands outside the box it names. Panes stand flush with the scrollport
    of the workspace body that holds them, so that ring lost its right and bottom sides
    to the scrollport's edge and ran over the pane's header rule at the top."""
    page = open_page(browser, serve(READING_REGIONS_PAGE))
    resized(page, 1440, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")
    page.locator("#left-head").focus()
    page.keyboard.press("Tab")
    body = page.locator("#left-reading > :not(header, footer)")
    expect(body).to_be_focused()
    drawn = rings_drawn(page)
    assert drawn, "the focused pane body wears no ring"
    assert not ring_faults(drawn, "the focused pane body")


def test_workspace_scroll_behavior_changes_keep_each_panes_reading(browser, serve):
    page = open_page(browser, serve(READING_REGIONS_PAGE))
    left = page.locator("#left-reading > :not(header, footer)")
    right = page.locator("#right-reading > :not(header, footer)")
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")
    left.evaluate("el => el.scrollTop = 180")
    right.evaluate("el => el.scrollTop = 380")
    page.locator("#right-subject").focus()

    resized(page, 520, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "flow")
    expect(page.locator("#right-subject")).to_be_focused()
    resized(page, 1200, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")
    readings = [
        left.evaluate("el => el.scrollTop"),
        right.evaluate("el => el.scrollTop"),
    ]
    assert readings[0] > 100 and readings[1] > 250, readings
    assert abs(readings[0] - readings[1]) > 100, readings
    expect(page.locator("#right-subject")).to_be_focused()


CUT_SHORT_PAGE = READING_REGIONS_PAGE.replace(
    "<header><h1>Reading workspace</h1></header>",
    "<header><h1>Reading workspace</h1><p>"
    + " ".join(["A header long enough to wrap to many lines at a phone's width."] * 12)
    + "</p></header>",
)


LEFT_START_BELOW = """async (id) => {
  const {landingBand} = await window.__lfCheckApi();
  return document.getElementById(id ?? 'left-start').getBoundingClientRect().top
    - landingBand(document.scrollingElement).top;
}"""


def cut_short(page):
    """Narrow, read the left pane's first line low in the window, then widen so the pane
    scrolls on its own, already at its top and short of that line. Returns how far below
    the band the reader had the line."""
    left = page.locator("#left-reading")
    resized(page, 520, 900)
    pane_scroll_behavior(page, left, "flow")
    rendered(page)
    page.evaluate("document.scrollingElement.scrollTo(0, 0)")
    rendered(page)
    # The wheel over the pane names it as where the reader reads.
    box = page.locator("#left-start").bounding_box()
    page.mouse.move(box["x"] + 10, box["y"] + 5)
    page.mouse.wheel(0, 60)
    page.wait_for_function("document.scrollingElement.scrollTop > 0")
    scroll_settled(page)
    rendered(page)
    read = page.evaluate(LEFT_START_BELOW)
    resized(page, 1200, 900)
    pane_scroll_behavior(page, left, "bounded")
    rendered(page)
    assert page.evaluate(LEFT_START_BELOW) < read - 40, "the pane should be cut short"
    return read


def test_a_restore_cut_short_by_a_pane_keeps_the_readers_place_for_the_return(
    browser, serve
):
    """Widened, the pane cannot lower the reader's line to where it stood. That is the
    runtime's move, not the reader's, so narrowing again returns the line to where they
    left it."""
    page = open_page(browser, serve(CUT_SHORT_PAGE))
    read = cut_short(page)
    resized(page, 520, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "flow")
    rendered(page)
    assert page.evaluate(LEFT_START_BELOW) == pytest.approx(read, abs=2)


@pytest.mark.parametrize("move", ["script", "fragment", "back"])
def test_a_box_holding_a_restored_place_still_follows_the_reader(browser, serve, move):
    """A place the runtime restored holds only until someone else moves the box: a
    page's script, fragment travel, or Back.
    The box keeps that move through the next layout change, and the next narrowing
    starts from it rather than from the place the runtime held."""
    page = open_page(browser, serve(CUT_SHORT_PAGE))
    read = cut_short(page)
    body = page.locator("#left-reading > :not(header, footer)")
    if move == "script":
        body.evaluate("body => { body.scrollTop += 300; }")
        moved = body.evaluate("body => body.scrollTop")
        scroll_settled(page)
        rendered(page)
        # A later layout change applies no held place over the move.
        page.evaluate(
            "document.querySelector('#right-reading > div').append("
            "Object.assign(document.createElement('p'), {textContent: 'More.'}))"
        )
        rendered(page)
        assert body.evaluate("body => body.scrollTop") == pytest.approx(moved, abs=2)
    else:
        page.evaluate("location.hash = 'left-landmark'")
        rendered(page)
        expect(page.locator("#left-landmark")).to_be_in_viewport()
        if move == "back":
            page.evaluate("location.hash = 'left-end'")
            rendered(page)
            page.go_back()
            rendered(page)
    resized(page, 520, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "flow")
    rendered(page)
    assert page.evaluate(LEFT_START_BELOW) < read - 100, "the held place came back"


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_a_split_drag_keeps_a_panes_reading(engine, request, serve):
    """Each frame of a drag rewraps a pane, and each frame's restore keeps its reading.

    Scroll anchoring would hold the reading itself, so the pane turns it off, as
    Safari has none: the restores do the whole job. The reader's wheel scroll before
    the drag is theirs, and WebKit ends it frames after its last scroll event, so the
    reading continuity takes must follow its end. A restore is no scroll the reader
    chose: counted as theirs, it would make the next frame's restore leave the pane
    where layout had moved it.
    """
    browser = request.getfixturevalue(engine)
    source = READING_REGIONS_PAGE.replace(
        '<p id="left-start">Left start with enough words to preserve this landmark.</p>',
        "<p id='left-start'>"
        + "Left start words rewrap as the pane narrows. " * 60
        + "</p>",
    ).replace("</style>", "#left-reading > div { overflow-anchor: none; }</style>", 1)
    page = open_page(browser, serve(source))
    left = page.locator("#left-reading > :not(header, footer)")
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")
    landmark = (
        "() => document.querySelector('#left-landmark').getBoundingClientRect().top"
        " - document.querySelector('#left-reading > div').getBoundingClientRect().top"
    )
    box = left.bounding_box()
    page.mouse.move(box["x"] + 50, box["y"] + 50)
    left.evaluate(
        "box => box.addEventListener('scrollend', () => { window.ended = true; })"
    )
    page.mouse.wheel(
        0,
        left.evaluate(
            "box => document.querySelector('#left-landmark').offsetTop"
            " - box.offsetTop - 60"
        ),
    )
    page.wait_for_function("window.ended")
    page_at_rest(page)
    before = page.evaluate(landmark)
    # The divider between the panes moves a few pixels each frame, as under a pointer.
    page.evaluate("""async () => {
      const split = document.querySelector('#reading-split');
      for (let left = 60; left > 20; left -= 4) {
        split.style.gridTemplateColumns = `${left}fr ${100 - left}fr`;
        await new Promise(requestAnimationFrame);
      }
    }""")
    page_at_rest(page)
    # Within the pixel the engine rounds a scroll offset to (scrolling.js,
    # `moveScrollerBy`); a lost reading leaves it lines away.
    assert page.evaluate(landmark) == pytest.approx(before, abs=1)


def test_a_passage_read_in_a_flowing_pane_returns_after_the_panes_scroll_alone(
    browser, serve
):
    """Narrow, the reader scrolls wt-merge's page over its Steps pane. Widened, each pane
    scrolls on its own, and layout settling moves boxes nobody chose to move. Narrowed
    again, the panes flow into the page, which returns to the passage the reader read:
    a place only the layout made never outranks the reader's."""
    page = open_page(browser, serve(next(p for p in EXAMPLES if p.stem == "wt-merge")))
    resized(page, 390, 800)
    rendered(page)
    # Reach the Steps pane before reading it; the preceding film grows on a phone.
    page.locator("#merge-steps-pane p").first.scroll_into_view_if_needed()
    scroll_settled(page)
    rendered(page)
    box = page.locator("#merge-steps-pane").bounding_box()
    page.mouse.move(box["x"] + 40, min(box["y"] + 120, 700))
    before = page.evaluate("document.scrollingElement.scrollTop")
    page.mouse.wheel(0, 300)
    page.wait_for_function(f"document.scrollingElement.scrollTop > {before}")
    scroll_settled(page)
    rendered(page)
    below = page.evaluate(
        """() => {
          const band = parseFloat(getComputedStyle(document.scrollingElement)
            .scrollPaddingTop) || 0;
          const block = [...document.querySelectorAll('#merge-steps-pane p')]
            .find(p => p.getBoundingClientRect().top >= band);
          block.id = 'read-step';
          window.__read = block;
          return block.getBoundingClientRect().top - band;
        }"""
    )
    measure = """() => window.__read.getBoundingClientRect().top
      - (parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop) || 0)"""
    expect(page.locator("#read-step")).to_be_in_viewport()
    for width in (1200, 390):
        resized(page, width, 800)
        rendered(page)
    assert page.evaluate(measure) == pytest.approx(below, abs=2)


@pytest.mark.parametrize("overscroll", ["auto", "contain"])
def test_a_wheel_in_a_box_is_no_choice_of_the_page_around_it(
    browser, serve, overscroll
):
    """The reader scrolls the page down to a box that scrolls on its own, turns the wheel
    in the box, and then layout scrolls the page without them, as content leaving below
    clamps it. The wheel was the box's, and the clamp no one's. Narrowed, the box flows
    into the page, as a page's own breakpoint lets it, and the page returns to the
    passage the reader scrolled the box to, not to where layout left the page. A box that
    contains its overscroll keeps even a wheel at its end, which the browser passes to
    no one."""
    lines = "".join(
        f'<p id="log-{n}">Log line {n}, long enough to read as its own passage.</p>'
        for n in range(60)
    )
    opening = "".join(
        f"<p>Opening paragraph {n} sets the scene before the log.</p>"
        for n in range(20)
    )
    source = leaf_page(
        "A box in a page",
        "<style>@media (width < 700px) {"
        " #log { block-size: auto !important; overflow: visible !important; } }</style>"
        f'{opening}<div id="log" data-bound="start"'
        f' style="block-size: 320px; overscroll-behavior: {overscroll}">{lines}'
        "</div><div id='room' style='height: 1200px'></div>",
    )
    page = open_page(browser, serve(source))
    resized(page, 1200, 800)
    rendered(page)
    log = page.locator("#log")
    log.scroll_into_view_if_needed()
    page.mouse.move(600, 400)
    page.mouse.wheel(0, 900)
    page.wait_for_function("document.scrollingElement.scrollTop > 0")
    scroll_settled(page)
    rendered(page)
    box = log.bounding_box()
    page.mouse.move(box["x"] + 30, box["y"] + 60)
    page.mouse.wheel(0, 600)
    page.wait_for_function("document.getElementById('log').scrollTop > 0")
    scroll_settled(page)
    rendered(page)
    if overscroll == "contain":
        # At the box's end, one more turn of the wheel goes nowhere.
        log.evaluate("log => { log.scrollTop = log.scrollHeight; }")
        scroll_settled(page)
        rendered(page)
        page.mouse.wheel(0, 300)
        scroll_settled(page)
        rendered(page)
    read = page.evaluate(
        """() => {
          const box = document.getElementById('log').getBoundingClientRect();
          const line = [...document.querySelectorAll('#log p')]
            .find(p => p.getBoundingClientRect().top >= box.top);
          window.__read = line;
          return line.id;
        }"""
    )
    before = page.evaluate("document.scrollingElement.scrollTop")
    page.evaluate("document.getElementById('room').style.height = '0px'")
    page.wait_for_function(f"document.scrollingElement.scrollTop < {before}")
    scroll_settled(page)
    rendered(page)
    resized(page, 390, 800)
    rendered(page)
    expect(page.locator(f"#{read}")).to_be_in_viewport()


def test_a_tall_local_comment_survives_its_panes_scroll_behavior_and_return(
    browser, serve
):
    source = READING_REGIONS_PAGE.replace(
        '<footer><button id="left-foot">',
        '<footer style="min-height: 220px"><button id="left-foot">',
    )
    page = open_page(browser, serve(source))
    left = page.locator("#left-reading > :not(header, footer)")
    right = page.locator("#right-reading > :not(header, footer)")
    target = page.locator("#left-end")
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")

    left.evaluate("body => body.scrollTop = body.scrollHeight")
    right.evaluate("body => body.scrollTop = 320")
    target.click(click_count=3)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    expect(field).to_be_focused()
    wait_for_pending_mark(page)

    sibling_before = right.evaluate(
        "body => ({scroll: body.scrollTop, box: body.getBoundingClientRect().toJSON()})"
    )
    draft = "\n".join(
        f"Line {line}: keep this unsent pane comment available through reflow."
        for line in range(1, 21)
    )
    write(field, draft)
    expect(field).to_have_js_property("value", draft)
    expect(page.get_by_role("button", name="Comment", exact=True)).to_be_visible()
    sibling_after = right.evaluate(
        "body => ({scroll: body.scrollTop, box: body.getBoundingClientRect().toJSON()})"
    )
    assert sibling_after == sibling_before, (
        f"growing the left composer moved its sibling: {sibling_before}, {sibling_after}"
    )
    rendered(page)
    assert field.evaluate(
        """box => {
          box.scrollTop = box.scrollHeight;
          return box.scrollTop + box.clientHeight >= box.scrollHeight - 1;
        }"""
    ), "the complete multiline draft was not reachable in its field"

    resized(page, 520, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "flow")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", draft)
    expect(page.get_by_role("button", name="Comment", exact=True)).to_be_visible()

    resized(page, 1200, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", draft)
    assert right.evaluate("body => body.scrollTop") == pytest.approx(
        sibling_before["scroll"], abs=1
    )

    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator(".lf-live")).to_contain_text("Draft kept — g i resumes writing")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", draft)
    assert "Left end" in pending_text(page)


def test_a_wheel_reading_without_focus_becomes_the_bounded_pane_subject(browser, serve):
    # A short run between the right pane's opening line and its landmark, so the opening
    # line can sit just above the window while the landmark stands high enough in it
    # for the pane, once it scrolls on its own, to put it back at the same height.
    source = READING_REGIONS_PAGE.replace(
        '<div style="height: 320px"></div>', '<div style="height: 60px"></div>'
    )
    page = open_page(browser, serve(source))
    resized(page, 520, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "flow")
    right_landmark = page.locator("#right-landmark")
    right_landmark.scroll_into_view_if_needed()
    page.evaluate("() => document.activeElement?.blur()")
    box = right_landmark.bounding_box()
    page.mouse.move(box["x"] + 8, box["y"] + 8)
    # Leave the pane's opening line just above the window. The user is on the landmark
    # below it, not on a line they cannot see.
    start = page.locator("#right-start")
    goal = page.evaluate(
        """() => -document.querySelector('#right-start').getBoundingClientRect().height
          - 10"""
    )
    page.mouse.wheel(0, start.bounding_box()["y"] - goal)
    page.wait_for_function(
        "([el, goal]) => Math.abs(el.getBoundingClientRect().top - goal) < 2",
        arg=[start.element_handle(), goal],
    )
    scroll_settled(page)
    hidden = page.evaluate(
        "() => document.querySelector('#right-start').getBoundingClientRect().bottom"
    )
    assert hidden <= 0, hidden
    # How far the landmark stands below the top of what its scroller shows, past any
    # scroll-padding at its top.
    below_band = """([landmark, box]) => landmark.getBoundingClientRect().top -
      (box === document.scrollingElement ? 0 : box.getBoundingClientRect().top) -
      (parseFloat(getComputedStyle(box).scrollPaddingTop) || 0)"""
    relative = page.evaluate(
        below_band,
        [
            right_landmark.element_handle(),
            page.evaluate_handle("() => document.scrollingElement"),
        ],
    )

    resized(page, 1200, 900)
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")
    right = page.locator("#right-reading > :not(header, footer)")
    assert right.evaluate("el => el.scrollTop") > 0
    after = page.evaluate(
        below_band, [right_landmark.element_handle(), right.element_handle()]
    )
    assert after == pytest.approx(relative, abs=3)


def test_a_pane_comment_stays_in_its_reading_region(browser, serve):
    source = READING_REGIONS_PAGE.replace(
        '<footer><button id="left-foot">',
        '<footer style="min-height: 220px"><button id="left-foot">',
    )
    url = serve(source, anchored=[("left-start", "enough words to preserve")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "revision": 1,
            "text": "\n\n".join(
                f"Pane consideration {i}: enough explanation to require local scrolling."
                for i in range(20)
            ),
        },
    )
    page = open_page(browser, url)
    cluster = page.locator('[data-lf-margin-for="left-start"].lf-margin-cluster')
    expect(cluster).to_have_count(1)
    margins_laid_out(page)
    # A pin in the pane's own lane, standing inside the pane's body and nothing of it in
    # the pane beside it. The page's content holds none of the margin.
    expect(cluster).to_have_attribute("data-lf-place", "pin")
    placement = cluster.evaluate(
        """el => ({
          inLane: Boolean(el.closest('.lf-margin-lane')),
          inPage: Boolean(el.closest('main')),
          cluster: el.getBoundingClientRect().toJSON(),
          body: document.querySelector('#left-reading > :not(header, footer)')
            .getBoundingClientRect().toJSON(),
          sibling: document.querySelector('#right-reading').getBoundingClientRect().toJSON(),
        })"""
    )
    assert placement["inLane"] and not placement["inPage"], placement
    assert placement["cluster"]["left"] >= placement["body"]["left"], placement
    assert placement["cluster"]["right"] <= placement["body"]["right"] + 6, placement
    assert placement["cluster"]["right"] <= placement["sibling"]["left"], placement

    comment_note(page, "#left-start").press("Enter")
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    # The card shows before it is placed: opening it resets the placement and leaves it
    # transparent at the viewport origin until the next frame's measurement lands. A
    # non-empty box is visible to Playwright whatever its opacity, so the placement
    # attribute the runtime writes with the position is what says the card has one.
    expect(preview).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
    preview_geometry = preview.evaluate(
        """el => {
          const card = el.getBoundingClientRect();
          const history = el.querySelector('.lf-thread-transcript');
          const body = document.querySelector('#left-reading > :not(header, footer)')
            .getBoundingClientRect();
          return {card: card.toJSON(), body: body.toJSON(),
                  scrollHeight: history.scrollHeight, clientHeight: history.clientHeight};
        }"""
    )
    assert preview_geometry["card"]["top"] >= preview_geometry["body"]["top"], (
        preview_geometry
    )
    assert preview_geometry["card"]["bottom"] <= preview_geometry["body"]["bottom"], (
        preview_geometry
    )
    assert preview_geometry["scrollHeight"] > preview_geometry["clientHeight"], (
        preview_geometry
    )
    history = preview.locator(".lf-thread-transcript")
    history.evaluate("el => el.scrollTop = el.scrollHeight")
    assert history.evaluate("el => el.scrollTop") > 0
    page.keyboard.press("Escape")  # onto the passage, the card beside it
    page.keyboard.press("Escape")  # letting go of the passage takes the card
    expect(preview).to_be_hidden()
    page.keyboard.press("t")
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-page-thread")).to_be_focused()


# The handoff guard decides `wheel` and `reveal`, and on a fresh document `wheel`
# again, since it has no tab controls until its widgets load. `untouched` is the
# control: the restoration a gesture must stop does run when there is none. `focus`
# guards the gesture a user would miss most; the edit, blank and hidden gestures
# are kept today by state captured at install and by kept nodes, not by this guard.
@pytest.mark.parametrize(
    ("install", "gesture"),
    [
        ("patch", "wheel"),
        ("patch", "reveal"),
        ("patch", "untouched"),
        ("patch", "focus"),
        ("reload", "wheel"),
    ],
)
def test_revision_restoration_yields_to_input_while_a_diagram_loads(
    browser, serve, gesture, install
):
    """Hold the real diagram renderer's delivery while the user uses the new pane.

    The panes stand in a page tab, where no workspace holds them, so the page's own
    stylesheet gives each a height its body scrolls within."""
    source = (
        READING_REGIONS_PAGE.replace(
            '<button id="left-head">',
            '<label>Draft <input id="reading-draft"></label><button id="left-head">',
        )
        .replace(
            "</head>",
            "<style>#reading-split lf-pane { block-size: 420px; }"
            " #reading-split lf-pane > :not(header, footer)"
            " { min-block-size: 0; overflow: auto; }</style></head>",
        )
        .replace(
            '<main class="layout-workspace">',
            '<main class="layout-sidebar"><lf-tabs id="reading-tabs">'
            '<lf-tab id="first-tab" label="First">',
        )
        .replace(
            "</main>",
            '</lf-tab><lf-tab id="second-tab" label="Second">'
            '<lf-pane id="other-reading" label="Other reading">'
            '<div><p id="other-start">Another reading with enough words to preserve its landmark.</p>'
            '<div style="height: 1000px"></div></div></lf-pane></lf-tab></lf-tabs></main>',
        )
    )
    page = open_page(browser, live_url(serve(source)))
    page.locator("#reading-draft").fill("kept draft")
    left = page.locator("#left-reading > :not(header, footer)")
    left.evaluate("el => el.scrollTop = 300")
    page.locator("#reading-draft").evaluate("el => el.setSelectionRange(4, 4)")
    held = []
    page.route("**/vendor/pele.esm.js", lambda route: held.append(route))
    revised = source.replace(
        '<p id="left-start">',
        '<p>Added context.</p><p id="left-start">',
    ).replace(
        '<p id="left-end">',
        '<lf-diagram id="late-diagram"><pre>graph LR; A --&gt; B</pre></lf-diagram><p id="left-end">',
    )
    before = page.locator("#left-landmark").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    if install == "reload":
        revised = executable_revision(revised, "new renderer")
    stamp_page(serve.page_dir, revised, "Add a diagram")
    holding(page, held, 1, "the new diagram renderer")
    try:
        # Typing must remain possible throughout replacement, without a click to
        # recover the field while an unrelated renderer finishes downloading.
        draft = page.locator("#reading-draft")
        expect(draft).to_be_focused()
        assert draft.evaluate("el => el.selectionStart") == 4
        if gesture == "wheel":
            left.hover()
            page.mouse.wheel(0, 220)
            page.wait_for_function(
                "() => document.querySelector('#left-reading > :not(header, footer)').scrollTop > 150"
            )
        elif gesture == "focus":
            page.locator("#right-head").click()
        elif gesture == "reveal":
            page.get_by_role("tab", name="Second", exact=True).click()
        scroll = left.evaluate("el => el.scrollTop")
        held.pop().continue_()
        wait_for_revision(page, 2)
        expect(page.locator("#late-diagram svg")).to_have_count(1)
        expect(page.locator("#reading-draft")).to_have_value("kept draft")
        expect(
            page.get_by_role(
                "tab", name="Second" if gesture == "reveal" else "First", exact=True
            )
        ).to_have_attribute("aria-selected", "true")
        if gesture == "wheel":
            assert left.evaluate("el => el.scrollTop") == pytest.approx(scroll, abs=1)
        elif gesture == "focus":
            expect(page.locator("#right-head")).to_be_focused()
        elif gesture == "untouched":
            assert page.locator("#left-landmark").evaluate(
                "el => el.getBoundingClientRect().top"
            ) == pytest.approx(before, abs=2)
        if gesture in ("wheel", "untouched"):
            expect(draft).to_be_focused()
            assert draft.evaluate("el => el.selectionStart") == 4
    finally:
        for route in held:
            route.continue_()
        page.unroute("**/vendor/pele.esm.js")


def test_revision_carries_apparatus_when_an_arriving_element_takes_focus(
    browser, serve
):
    """A synchronous widget focus handoff cannot discard unrelated carried state."""
    source = READING_REGIONS_PAGE.replace(
        '<button id="left-head">',
        '<label>Draft <input id="reading-draft"></label>'
        '<label>Flag <input id="reading-flag" type="checkbox"></label>'
        '<details id="reading-detail"><summary>Context</summary>Kept open</details>'
        '<div id="reading-inner" style="height: 60px; overflow: auto">'
        '<div style="height: 600px">Scrollable evidence</div></div>'
        '<button id="left-head">',
    )
    page = open_page(browser, live_url(serve(source)))
    page.locator("#reading-flag").check()
    page.locator("#reading-detail summary").click()
    page.locator("#reading-draft").fill("kept draft")
    page.locator("#reading-inner").evaluate("el => el.scrollTop = 220")
    page.evaluate("""() => {
      customElements.define('page-focus-transfer', class extends HTMLElement {
        connectedCallback() { document.getElementById('right-head').focus(); }
      });
    }""")
    revised = source.replace(
        '<p id="left-start">', '<p>Added context.</p><p id="left-start">'
    ).replace("</main>", "<page-focus-transfer></page-focus-transfer></main>")
    stamp_page(serve.page_dir, revised, "Update reading with a focus handoff")
    wait_for_revision(page, 2)

    expect(page.locator("#right-head")).to_be_focused()
    expect(page.locator("#reading-draft")).to_have_value("kept draft")
    expect(page.locator("#reading-flag")).to_be_checked()
    expect(page.locator("#reading-detail")).to_have_attribute("open", "")
    assert page.locator("#reading-inner").evaluate("el => el.scrollTop") == 220


@pytest.mark.parametrize("named", [False, True], ids=["unnamed-bodies", "named-bodies"])
def test_a_new_revision_restores_each_panes_semantic_landmark(browser, serve, named):
    """A pane body is the region's scroller whether or not its author named it.

    A named element's scroll offset otherwise crosses a revision as a raw number, which
    would undo the landmark: the new material above it moves the passage, not the pixel.
    """
    source = READING_REGIONS_PAGE
    if named:
        for side in ("left", "right"):
            source = source.replace(
                f'<div>\n        <p id="{side}-start">',
                f'<div id="{side}-body">\n        <p id="{side}-start">',
            )
        assert source.count('-body">') == 2
    url = serve(source)
    page = open_page(browser, live_url(url))
    pane_scroll_behavior(page, page.locator("#left-reading"), "bounded")
    left = page.locator("#left-reading > :not(header, footer)")
    right = page.locator("#right-reading > :not(header, footer)")
    left.evaluate("el => el.scrollTop = 300")
    right.evaluate("el => el.scrollTop = 360")
    before = page.evaluate(
        """() => ['left-landmark', 'right-landmark'].map(id => {
          const landmark = document.getElementById(id);
          return landmark.getBoundingClientRect().top -
            landmark.closest('lf-pane > :not(header, footer)').getBoundingClientRect().top;
        })"""
    )

    revised = source.replace(
        '<p id="left-start">',
        '<p>New left material above the saved reading.</p><p id="left-start">',
    ).replace(
        '<p id="right-start">',
        '<p>New right material above the saved reading.</p><p id="right-start">',
    )
    stamp_page(serve.page_dir, revised, "add context above both readings")
    wait_for_revision(page, 2)
    after = page.evaluate(
        """() => ['left-landmark', 'right-landmark'].map(id => {
          const landmark = document.getElementById(id);
          return landmark.getBoundingClientRect().top -
            landmark.closest('lf-pane > :not(header, footer)').getBoundingClientRect().top;
        })"""
    )
    scrolls = [
        left.evaluate("el => el.scrollTop"),
        right.evaluate("el => el.scrollTop"),
    ]
    assert all(abs(old - new) < 2 for old, new in zip(before, after, strict=True)), (
        before,
        after,
        scrolls,
    )
    assert left.evaluate("el => el.scrollTop") > 0
    assert right.evaluate("el => el.scrollTop") > 0


def test_review_queue_links_are_its_only_navigator_and_keep_both_readings(
    browser, serve
):
    example = next(e for e in CORPUS_SOURCES if e.stem == "review-queue")
    page = open_page(browser, serve(example))
    # Short, but tall enough to hold the workspace, so each pane scrolls on its own.
    resized(page, 1100, 640)
    pane_scroll_behavior(page, page.locator("#review-detail"), "bounded")
    queue = page.locator("#review-queue > :not(header, footer)")
    detail = page.locator("#review-detail > :not(header, footer)")
    links = queue.locator('nav[aria-label="Review items"] a')
    assert links.count() == 8
    assert page.get_by_role("tab").count() == 0
    assert (
        links.evaluate_all("els => new Set(els.map(el => el.hash)).size")
        == page.locator("#review-items > section").count()
    )

    billing = links.filter(has_text="Billing reconciliation")
    billing.scroll_into_view_if_needed()
    billing.focus()
    queue_before = queue.evaluate("el => el.scrollTop")
    detail_before = detail.evaluate("el => el.scrollTop")
    events_before = events_model.read_events(serve.page_dir)

    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"#review-billing$"))
    expect(page.locator("#review-billing")).to_be_in_viewport()
    assert detail.evaluate("el => el.scrollTop") > detail_before
    assert queue.evaluate("el => el.scrollTop") == queue_before
    assert events_model.read_events(serve.page_dir) == events_before


def test_thread_travel_reveals_a_review_detail_in_its_pane_only(browser, serve):
    example = next(e for e in CORPUS_SOURCES if e.stem == "review-queue")
    page = open_page(
        browser,
        serve(
            example,
            anchored=[
                (
                    "review-cache",
                    "The deploy copies active entries to the new key format before readers",
                )
            ],
        ),
    )
    resized(page, 1400, 900)
    pane_scroll_behavior(page, page.locator("#review-detail"), "bounded")
    queue = page.locator("#review-queue > :not(header, footer)")
    detail = page.locator("#review-detail > :not(header, footer)")
    queue.evaluate(
        "el => el.scrollTop = Math.min(120, el.scrollHeight - el.clientHeight)"
    )
    queue_before = queue.evaluate("el => el.scrollTop")
    detail.evaluate("el => el.scrollTop = el.scrollHeight")
    detail_before = detail.evaluate("el => el.scrollTop")
    assert detail_before > 0
    expect(page.locator("#review-cache")).not_to_be_in_viewport()

    travel_to_passage(page, only_thread(serve.page_dir))
    expect(page.locator("#review-cache")).to_be_in_viewport()
    assert detail.evaluate("el => el.scrollTop") < detail_before
    assert queue.evaluate("el => el.scrollTop") == queue_before


def only_thread(page_dir):
    """The id of the one thread a test's page holds."""
    (root,) = [
        event["id"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment"
    ]
    return root


def travel_to_passage(page, thread_id):
    """Open the thread in the panel and take its way to the passage it is about."""
    open_panel_thread(page, thread_id)
    page.locator(".lf-fp-controls").get_by_role("button", name="Show on page").click()


BOUNDED_LOG_FILLER = "".join(
    f"<p>Filler paragraph {n}, long enough to occupy a line of reading.</p>"
    for n in range(40)
)


def bounded_log_page(named):
    """A log bounded at its end between screens of filler, `named` or anonymous."""
    entries = "".join(
        f"<p>Entry {n}: the deploy copied shard {n} to the new key format.</p>"
        for n in range(60)
    )
    name = ' id="log"' if named else ""
    return leaf_page(
        "bounded log",
        f'<h1 id="t">Deploy</h1>{BOUNDED_LOG_FILLER}<section id="deploy">'
        f'<div{name} class="log" data-bound="end">{entries}</div></section>'
        f"{BOUNDED_LOG_FILLER}",
    )


@pytest.mark.parametrize("named", [True, False], ids=["named", "anonymous"])
def test_thread_travel_into_a_bounded_log_scrolls_the_log_and_the_page_no_more(
    browser, serve, named
):
    """A block that bounds its height is the box scrolling a passage inside it, with an
    id or without one. Travel centred the passage by moving the page, scrolling the log
    only as far as its edge, so a log already on screen slid under the user; one
    scrolled off the window must still come back with the passage in it."""
    page = open_page(
        browser,
        serve(
            bounded_log_page(named),
            anchored=[("deploy", "the deploy copied shard 3 to the new key format")],
        ),
    )
    resized(page, 1400, 900)
    thread = only_thread(serve.page_dir)
    log = page.locator(".log")
    passage = log.locator("p").nth(3)
    placed = """([log, passage, bar]) => {
      const box = log.getBoundingClientRect();
      const at = passage.getBoundingClientRect();
      const foot = bar ? bar.getBoundingClientRect().top : innerHeight;
      return at.top >= box.top && at.bottom <= box.bottom
        && at.top >= 0 && at.bottom <= foot;
    }"""
    handles = [
        log.element_handle(),
        passage.element_handle(),
        page.locator(".lf-fp-row").element_handle(),
    ]

    # The log stands in the middle of the window, opened on its newest entry.
    page.evaluate(
        """log => { const at = log.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        log.element_handle(),
    )
    scroll_settled(page)
    assert not page.evaluate(placed, handles)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    travel_to_passage(page, thread)
    scroll_settled(page, ".log")
    scroll_settled(page)
    assert page.evaluate(placed, handles), "the passage was left out of view"
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert after == pytest.approx(before, abs=1), f"the page moved {after - before}px"

    # The log scrolled back to its end and the page taken to its top: the travel
    # brings both the log and the passage in it into the window.
    log.evaluate("log => log.scrollTop = log.scrollHeight")
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    scroll_settled(page)
    assert not page.evaluate(placed, handles)
    travel_to_passage(page, thread)
    scroll_settled(page, ".log")
    scroll_settled(page)
    assert page.evaluate(placed, handles), "the passage stayed off the window"


def test_reading_keys_page_the_bounded_log_the_user_stands_in(browser, serve):
    """Focus inside a bounded block puts the user in that region, so d and u page the
    block, as they page a pane, and leave the page where it stands."""
    entries = "".join(
        f'<p>Entry {n}: <a href="#t">shard {n}</a> copied to the new key format.</p>'
        for n in range(60)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "bounded keys",
                f'<h1 id="t">Deploy</h1>{BOUNDED_LOG_FILLER}<div id="log" '
                f'data-bound="start">{entries}</div>{BOUNDED_LOG_FILLER}',
            )
        ),
    )
    resized(page, 1280, 900)
    log = page.locator("#log")
    page.evaluate(
        """log => { const at = log.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        log.element_handle(),
    )
    scroll_settled(page)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    log.locator("a").first.focus()
    page.keyboard.press("d")
    page.wait_for_function("() => document.getElementById('log').scrollTop > 100")
    scroll_settled(page, "#log")
    paged = log.evaluate("log => log.scrollTop")
    page.keyboard.press("u")
    page.wait_for_function(f"() => document.getElementById('log').scrollTop < {paged}")
    scroll_settled(page, "#log")
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert after == pytest.approx(before, abs=1), f"the page moved {after - before}px"


def test_the_obligation_walk_lands_an_obligation_in_a_bounded_log_at_the_log_top(
    browser, serve
):
    """An obligation inside a block that bounds its height arrives at the top of that block,
    which is the box scrolling it. The walk measured its run-up against the window and
    moved the page to put it at the window's top, sliding a log the user could
    already see."""
    early = "".join(f"<p>Early {n}: a line before the question.</p>" for n in range(8))
    entries = "".join(
        f"<p>Entry {n}: the deploy copied shard {n} to the new key format.</p>"
        for n in range(40)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "bounded ask",
                f'<h1 id="t">Deploy</h1>{BOUNDED_LOG_FILLER}<div id="log" '
                f'data-bound="end">{early}<lf-ask id="q"><h3>Which shard next?</h3>'
                '<lf-options id="o" choose><lf-option id="o1">The first</lf-option>'
                '<lf-option id="o2">The second</lf-option></lf-options></lf-ask>'
                f"{entries}</div>{BOUNDED_LOG_FILLER}",
            )
        ),
    )
    resized(page, 1280, 900)
    log = page.locator("#log")
    page.evaluate(
        """log => { const at = log.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        log.element_handle(),
    )
    scroll_settled(page)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("m")
    expect(page.locator("#q")).to_be_focused()
    scroll_settled(page, "#log")
    scroll_settled(page)
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert after == pytest.approx(before, abs=1), f"the page moved {after - before}px"
    # Leave the obligation's focus ring inside the bounded log's visible edge.
    landed = page.evaluate(
        """() => { const q = document.getElementById('q');
          return q.getBoundingClientRect().top
            - document.getElementById('log').getBoundingClientRect().top
            - parseFloat(getComputedStyle(q).scrollMarginTop); }"""
    )
    assert landed == pytest.approx(0, abs=2), (
        f"the lf-ask landed {landed}px down the log"
    )


def test_current_and_proposed_results_share_one_review_and_flow_in_order(
    browser, serve
):
    """The comparison is simultaneous when room permits and sequential when it does not."""
    example = next(e for e in CORPUS_SOURCES if e.stem == "current-proposed-comparison")
    page = open_page(browser, serve(example))
    current = page.locator("#comparison-current")
    proposed = page.locator("#comparison-proposed")

    resized(page, 1200, 900)
    pane_scroll_behavior(page, current, "bounded")
    expect(current).to_be_visible()
    expect(proposed).to_be_visible()
    boxes = [
        current.evaluate("el => el.getBoundingClientRect().toJSON()"),
        proposed.evaluate("el => el.getBoundingClientRect().toJSON()"),
    ]
    assert boxes[0]["right"] <= boxes[1]["x"] + 1, boxes
    assert page.locator("lf-ask").count() == 1
    assert page.locator("lf-options[choose]").count() == 1

    resized(page, 420, 900)
    pane_scroll_behavior(page, current, "flow")
    boxes = [
        current.evaluate("el => el.getBoundingClientRect().toJSON()"),
        proposed.evaluate("el => el.getBoundingClientRect().toJSON()"),
    ]
    decision = page.locator("#comparison-policy-decision").evaluate(
        "el => el.getBoundingClientRect().toJSON()"
    )
    assert boxes[0]["bottom"] <= boxes[1]["y"] + 1, boxes
    assert boxes[1]["bottom"] <= decision["y"] + 1, [*boxes, decision]


def test_a_nested_pane_footer_travels_in_the_outer_region_that_contains_it(
    browser, serve
):
    source = READING_REGIONS_PAGE.replace(
        '<p id="left-end">Left end</p>',
        """<section>
  <lf-pane id="nested-pane" label="Nested reading">
    <div><p>Nested body context stays in ordinary flow.</p></div>
    <footer><p id="nested-footer">Nested footer destination with enough words to anchor.</p></footer>
  </lf-pane>
</section>
<p id="left-end">Left end</p>""",
    )
    page = open_page(
        browser,
        serve(source, anchored=[("nested-footer", "footer destination")]),
    )
    outer = page.locator("#left-reading > :not(header, footer)")
    inner = page.locator("#nested-pane > :not(header, footer)")
    sibling = page.locator("#right-reading > :not(header, footer)")
    pane_scroll_behavior(page, page.locator("#nested-pane"), "flow")
    assert outer.evaluate("el => el.scrollHeight - el.clientHeight") > 300
    assert inner.evaluate("el => el.scrollTop") == 0

    page.keyboard.press("t")
    expect(page.locator("#nested-footer")).to_be_in_viewport()
    assert outer.evaluate("el => el.scrollTop") > 0
    assert inner.evaluate("el => el.scrollTop") == 0
    assert sibling.evaluate("el => el.scrollTop") == 0


def test_a_choice_inside_a_proposal_survives_its_undo(browser, serve):
    """Accepting a block proposal hides the slot its decision retired, and the page
    keeps nested user work through an outer undo and reload."""
    url = serve(NESTED_PROPOSAL_PAGE)
    page = open_page(browser, url)
    old = page.locator("#nested-change > lf-old")
    expect(old).to_be_visible()
    page.locator("#route-river").click()
    round_trip(page)
    suggestion_control(page, "nested-change", "accept").click()
    round_trip(page)
    expect(page.locator("#nested-change")).to_have_attribute("data-lf-state", "accept")
    expect(old).to_be_hidden()

    suggestion_control(page, "nested-change", "undo").click()
    round_trip(page)

    expect(page.locator("#nested-change")).not_to_have_attribute(
        "data-lf-state", "accept"
    )
    expect(page.locator("#nested-change > lf-old")).to_be_visible()
    expect(page.locator("#route lf-option[chosen]")).to_have_attribute(
        "id", "route-river"
    )
    page.close()

    page = open_page(browser, url)
    expect(page.locator("#nested-change > lf-old")).to_be_visible()
    expect(page.locator("#route lf-option[chosen]")).to_have_attribute(
        "id", "route-river"
    )


def test_a_pane_frame_comment_preview_is_not_confined_to_its_body(browser, serve):
    """A region's frame names it for reading keys but does not live in its body."""
    page = open_page(
        browser,
        serve(READING_REGIONS_PAGE, anchored=[("left-head", "Left header")]),
    )
    resized(page, 1200, 900)
    page.locator('[data-lf-margin-for="left-head"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(preview).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
    geometry = preview.evaluate(
        """card => {
          const box = card.getBoundingClientRect();
          const pane = document.querySelector('#left-reading > :not(header, footer)')
            .getBoundingClientRect();
          return {
            box: box.toJSON(),
            pane: pane.toJSON(),
            viewport: {width: innerWidth, height: innerHeight},
          };
        }"""
    )
    assert geometry["box"]["left"] >= 0, geometry
    assert geometry["box"]["right"] <= geometry["viewport"]["width"], geometry
    # The card stands beside the header's pinned cluster, above the body it would have
    # been clamped into had the body been its boundary.
    assert (
        geometry["box"]["left"] < geometry["pane"]["left"]
        or geometry["box"]["right"] > geometry["pane"]["right"]
        or geometry["box"]["top"] < geometry["pane"]["top"]
        or geometry["box"]["bottom"] > geometry["pane"]["bottom"]
    ), geometry
