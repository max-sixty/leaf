"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.widgets.test_tabs import ROOT_PARTS_PAGE, ROOT_TABS_PAGE
from playwright.sync_api import expect
from render_harness import (
    displayed,
    leaf_page,
    open_page,
    resized,
    root_overflow,
    scroll_settled,
)

from leaf.source.render_checks import rendered, wait_until_ready


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
      const strip = document.querySelector('#queue').shadowRoot.querySelector('.lf-tabstrip');
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
          const strip = document.querySelector('#queue').shadowRoot.querySelector('.lf-tabstrip').getBoundingClientRect();
          const item = document.querySelector('#queue > lf-tab:not([hidden])').getBoundingClientRect();
          return strip.right > item.left + 1 && item.top >= strip.bottom - 1;
        }"""
    )
    stacked = page.evaluate(state)
    assert stacked["page"] <= 0 and stacked["item"][1] > 0, stacked


def test_root_tabs_switch_views_without_moving_the_strip_and_follow_history(
    browser, serve
):
    """A tab switch is not fragment travel. The strip stays where it is on screen: a view
    never read opens at its start when the strip is stuck and leaves the shared header
    alone when it is not, and a view read past its start reopens where the user left it.
    Pointer and keyboard agree. Back and Forward open their entry's view where the user
    was on that entry, and a fresh load of the remembered view shows the page's top.

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
          const strip = document.querySelector('#root-tabs').shadowRoot.querySelector('.lf-tabstrip');
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


def test_parts_switch_without_moving_the_list_and_follow_history(browser, serve):
    """A switch between a page's parts is not fragment travel. The list stays where it is
    on screen under the page's title: a part never read opens at its start, at the top
    of the page level with the title, and a part read past its start reopens where the
    user left it. Pointer and keyboard agree. Back and Forward open their entry's part
    where the user was on that entry, and a fresh load of the remembered part shows the
    page's top.

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
    strip = page.locator("#root-parts .lf-tabstrip")

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
        column = page.locator(f"{strip} .lf-tabstrip").evaluate(mark)
        assert column["flow"] == "column", column
        assert column["filled"] and column["contoured"], column
        assert column["rule"] == 0 and column["nameRule"] == 0, column
        resized(page, 390, 800)
        page.wait_for_function(
            "s => getComputedStyle(document.querySelector(s)).flexDirection === 'row'",
            arg=f"{strip} .lf-tabstrip",
        )
        row = page.locator(f"{strip} .lf-tabstrip").evaluate(mark)
        assert not row["filled"] and not row["contoured"], row
        assert row["rule"] == 2 and row["ruleInk"] and row["nameRule"] == 0, row
        assert row["lastRow"] == "2px", row
        if strip == "#queue":
            # Name, summary, then the rule.
            assert row["rows"] == 3, row
            assert row["height"] == pytest.approx(row["reserved"], abs=0.01), row
            assert row["ground"] == row["frame"], row
        page.emulate_media(forced_colors="active")
        ruled = page.locator(f"{strip} .lf-tabstrip").evaluate(
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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_side_list_longer_than_the_window_keeps_its_tab_and_open_item_in_view(
    request, serve, engine
):
    """A side list longer than the window sticks beside the item it opens and scrolls on
    its own. Each arrow opens the next tab and keeps focus on it in the window, down
    and, coming round, back up through the list, while the item it opens starts in the
    window. Running with the page, the walk scrolled each item's start away, and a tab
    left past the window's foot, or read away from, was out of sight, so the next arrow
    let go of it (panel/page-keys/controller.js), focus fell to the page and no tab opened.
    The row the walk heads for shows beside the open tab, so the list doesn't look as
    though it starts or ends there. Read down an item, the list stays beside it, and the
    next arrow opens the next item at its start. A list shorter than the window stays
    beside its item until the item ends. The stuck list reaches the window's foot, so
    its last rows stand under the floating panel's row, and the arrow onto the first of
    them folds the panel to the leaf, where focus would otherwise be out of sight."""

    def items(key, count):
        return "".join(
            f'<lf-tab id="{key}-{i}" label="{key.title()} {i}">'
            + "".join(f"<p>{key} {i} reads on, paragraph {n}.</p>" for n in range(30))
            + "</lf-tab>"
            for i in range(count)
        )

    source = leaf_page(
        "Long queue",
        f'<h1 id="title">Queue</h1><lf-tabs id="queue" list="side">{items("item", 30)}'
        f'</lf-tabs><lf-tabs id="brief" list="side">{items("brief", 4)}</lf-tabs>'
        + "".join(f"<p>What follows, paragraph {n}.</p>" for n in range(20)),
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 1200, 500)
    tabs = page.locator("#queue").get_by_role("tab")
    item_starts_in_view = """id => {
      const top = document.getElementById(id).getBoundingClientRect().top;
      return top >= 0 && top < innerHeight / 2;
    }"""
    expect(tabs.last).not_to_be_in_viewport()
    tabs.first.click()
    expect(tabs.first).to_be_focused()
    # Down every tab and round to the first, then up round to the last and on up
    # through the middle of the list; the panel folds off the list's last rows.
    panel = page.locator(".lf-floating-panel")
    expect(panel).to_have_attribute("data-lf-rest", "row")
    for key, landing in [("ArrowDown", i % 30) for i in range(1, 31)] + [
        ("ArrowUp", i) for i in [29, *range(28, 9, -1)]
    ]:
        page.keyboard.press(key)
        tab = tabs.nth(landing)
        expect(tab).to_be_focused()
        expect(tab).to_have_attribute("aria-selected", "true")
        expect(tab).to_be_in_viewport(ratio=0.99)
        ahead = landing + 1 if key == "ArrowDown" else landing - 1
        if 0 <= ahead < 30:
            expect(tabs.nth(ahead)).to_be_in_viewport(ratio=0.99)
        page.wait_for_function(item_starts_in_view, arg=f"item-{landing}")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    # Read down the open item, then walk on from the list.
    item = page.locator("#item-10").bounding_box()
    assert item is not None
    page.mouse.move(item["x"] + item["width"] / 2, 300)
    page.mouse.wheel(0, 400)
    scroll_settled(page)
    expect(page.locator("#item-10")).not_to_be_in_viewport(ratio=0.9)
    expect(tabs.nth(10)).to_be_in_viewport(ratio=0.99)
    page.keyboard.press("ArrowDown")
    expect(tabs.nth(11)).to_be_focused()
    expect(tabs.nth(11)).to_have_attribute("aria-selected", "true")
    page.wait_for_function(item_starts_in_view, arg="item-11")
    # Read the short list's item to near its end: the list still stands beside it.
    page.evaluate("""() => {
      const item = document.getElementById('brief-0');
      scrollTo({top: scrollY + item.getBoundingClientRect().bottom - 200,
        behavior: 'instant'});
    }""")
    scroll_settled(page)
    expect(page.locator("#brief").get_by_role("tab").first).to_be_in_viewport(
        ratio=0.99
    )
