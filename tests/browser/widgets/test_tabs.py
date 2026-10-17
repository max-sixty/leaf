"""Tab sets: a page's views, boxed sets and side lists, switching between them, fragments
and history, a box's stuck strip and the headers stacked under it, and queue rows and
groups."""

import re

import pytest
from leaf import render_checks as render_checks_model
from leaf.render_checks import rendered, wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    ROOT,
    displayed,
    holding,
    leaf_page,
    open_page,
    pane_posture,
    post_event,
    resized,
    root_overflow,
    scroll_settled,
    stamp_page,
    wait_for_revision,
)

pytestmark = pytest.mark.shifts_unsurveyed


ROOT_TABS_PAGE = ROOT / "tests/fixtures/pages/root-tabs.html"


def test_views_switch_without_moving_the_list_and_follow_history(browser, serve):
    """A switch between a page's views is not fragment travel. The list stays where it is
    on screen: a view never read opens at its start, level with the list, and leaves the
    page's title alone when it is on screen, and a view read past its start reopens
    where the user left it. Pointer, keyboard, and Back/Forward agree, and a
    fresh load of the remembered view shows the page's top.

    A view's place is where the user was reading in it, not a pixel offset: a window
    resized while the view is hidden rewraps everything above that passage, and the view
    still reopens with the passage where the user left it."""
    url = serve(ROOT_TABS_PAGE)
    page = open_page(browser, url)
    resized(page, 1280, 720)
    tabs = page.locator("#root-tabs")
    expect(tabs).to_have_attribute("data-lf-tabs-flow", "views")
    plan = tabs.get_by_role("tab", name="Plan", exact=True)
    evidence = tabs.get_by_role("tab", name="Evidence", exact=True)
    summary = tabs.get_by_role("tab", name="Summary", exact=True)
    strip = page.locator("#root-tabs > .lf-tabstrip")

    def switch(tab):
        before = strip.bounding_box()
        # Locator.click would scroll the list's tab into view first.
        box = tab.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(tab).to_have_attribute("aria-selected", "true")
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
        assert top == pytest.approx(strip.bounding_box()["y"], abs=1)

    expect(plan).to_have_attribute("aria-selected", "true")
    assert settled() == 0
    # With the title on screen, a switch leaves it there.
    assert switch(summary) == 0
    assert switch(evidence) == 0
    assert page.url.endswith("#evidence-tab")
    # Read Evidence past its start; Plan, never read, opens at its start, level with the
    # list, rather than at the top of the page.
    evidence_read = read_at(450)
    assert 0 < switch(summary) < evidence_read
    at_start("#summary-tab")
    plan_start = switch(plan)
    assert 0 < plan_start < evidence_read
    at_start("#plan-tab")
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
    # user stands on names it, so pressing away and coming Back returns there.
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
    resized(page, 900, 720)
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


def _stacked_headers(browser, serve):
    """A page of views whose first, a column, holds a long pinned diff, then a short one
    whose code is wide enough to scroll sideways."""
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
                '<header><h1>Stacked</h1></header><lf-tabs id="root-tabs">'
                '<lf-tab id="diff-tab" label="Diff"><article class="layout-column">'
                '<lf-diff id="patch"><pre>'
                + patch
                + '</pre></lf-diff><lf-diff id="wide"><pre>'
                + short
                + '</pre></lf-diff></article></lf-tab><lf-tab id="notes-tab" label="Notes">'
                '<article class="layout-column"><p>Notes.</p></article></lf-tab></lf-tabs>',
                layout=None,
            )
        ),
    )
    resized(page, 1280, 720)
    page.wait_for_function(
        "() => document.querySelectorAll('lf-diff.lf-rendered').length === 2"
    )
    return page


def test_a_diffs_header_in_a_view_pins_at_the_landing_edge(browser, serve):
    """A diff's file header in a view pins at the inset the list of views sticks at: a
    sticky header has a stated height and adds it to `--lf-top` for what it stands over. A
    landing on one of the diff's rows arrives below the header, and the part of a row
    under the header reads as not on screen."""
    page = _stacked_headers(browser, serve)
    read = page.evaluate(
        """async () => {
        const geometry = await window.__lfCheckApi();
        const box = (el) => el.getBoundingClientRect();
        const diff = document.querySelector('lf-diff');
        const head = diff.shadowRoot.querySelector('.lf-diff-file > details > summary');
        const row = [...diff.shadowRoot.querySelectorAll('[data-line]')][150];
        row.scrollIntoView({block: 'start', behavior: 'instant'});
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        // The list of views sticks at the same inset as every header over the page.
        const edge = box(document.querySelector('#root-tabs > .lf-tabstrip')).top;
        const landed = {edge, head: box(head).bottom, row: box(row).top};
        // Half a row under the diff's header.
        document.scrollingElement.scrollTop += box(row).top - box(head).bottom
            + box(row).height / 2;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return {
            landed,
            head: {top: box(head).top, bottom: box(head).bottom},
            row: {top: box(row).top, bottom: box(row).bottom},
            shown: geometry.shownRect(row, new Map())?.top,
        };
    }"""
    )
    landed = read["landed"]
    assert read["head"]["top"] == pytest.approx(landed["edge"], abs=0.5), read
    assert landed["head"] == pytest.approx(landed["edge"] + 35, abs=0.5), landed
    assert landed["row"] > landed["head"], landed
    assert read["row"]["top"] < read["head"]["bottom"] < read["row"]["bottom"], read
    assert read["shown"] == pytest.approx(read["head"]["bottom"], abs=0.5), read


def test_focus_in_a_stuck_header_leaves_the_page_where_it_is(browser, serve):
    """A control in a stuck sticky header stands inside the root's landing band, so the
    browser scrolled toward it on every focus and the header never came out from under
    the band: the page crept 17px a focus under a diff's file header. The focus margin
    is read from the sticky-header slot, so focusing one where it sticks scrolls nothing,
    and nor does focusing the open view's name in the list of views, which stays beside
    the page. Focus moving on from the file header into its code, a tab stop since it
    scrolls sideways, clears the header."""
    page = _stacked_headers(browser, serve)
    focus_in = """async (id) => {
        const page = document.scrollingElement;
        const diff = document.getElementById(id);
        const row = [...diff.shadowRoot.querySelectorAll('[data-line]')][150];
        row.scrollIntoView({block: 'start', behavior: 'instant'});
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        const controls = {
            file: diff.shadowRoot.querySelector('.lf-diff-file > details > summary'),
            tab: document.querySelector(
                '#root-tabs > .lf-tabstrip [aria-selected="true"]'),
        };
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


@pytest.mark.parametrize("layout", ["column", "sidebar", "workspace"])
def test_wide_evidence_in_a_view_takes_the_room_it_would_on_a_page_of_its_own(
    browser, serve, layout
):
    """A view of a page of views is laid out as a page of its own Layout, so a `wide` or
    `available` table in it takes the box and the column widths, measured from the
    view's edge, that its twin takes on a page with that Layout as wide as the view: at
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
    views = leaf_page(
        "Evidence in a view",
        '<header><h1>Evidence</h1></header><lf-tabs id="views">'
        f'<lf-tab id="compare" label="Compare"><div id="box" class="layout-{layout}">'
        f'{content}</div></lf-tab><lf-tab id="notes" label="Notes">'
        '<article class="layout-column"><p>Notes.</p></article></lf-tab></lf-tabs>',
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
            page.goto(serve(views), wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"
        first = page.evaluate(measure)
        boot.pop().continue_()
        wait_until_ready(page)
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")
    expect(page.locator("#views")).to_have_attribute("data-lf-tabs-flow", "views")
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

    page.evaluate("document.documentElement.style.fontSize = '20px'")
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


def test_side_tabs_distinguish_withdrawn_asks_from_answers(browser, serve):
    """A row's mark says its item's asks are open until every one is answered, and
    withdrawal retires a request without claiming the user answered it: a row whose
    only ask was withdrawn shows no mark, and one whose other ask is answered shows
    the answer."""
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
    expect(marks.nth(0)).to_have_attribute("data-lf-asks", "open")
    expect(marks.nth(1)).to_have_attribute("data-lf-asks", "open")
    stamp_page(
        serve.page_dir,
        source.replace('id="only-options" choose', 'id="only-options"').replace(
            'id="withdrawn-options" choose', 'id="withdrawn-options"'
        ),
        "Retire unanswered requests",
    )
    wait_for_revision(page, 2)
    expect(marks.nth(0)).not_to_have_attribute("data-lf-asks", re.compile(".*"))
    expect(marks.nth(1)).to_have_attribute("data-lf-asks", "answered")
    expect(marks.nth(1)).to_have_text("Keep")


def test_a_queue_row_names_an_answer_whose_widget_module_arrives_last(browser, serve):
    """An ask answered before the page loads is named once the page presents, however
    late the answering widget's module arrives: startup imports every module the
    document names before the first reading brings the ask inventory."""
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


def test_a_queue_stands_its_items_under_their_groups(browser, serve):
    """Each run of neighbouring queue items that share a `group` stands under a label
    of it: a heading over the run in the column, and a word before the run's first tab
    in a phone's row, which comes into the row with that tab. A run of items with no
    group is ruled off from the run before it, so it never reads as part of that group.
    A label is not a tab, so the walk passes it by and assistive technology hears the
    group in each tab's description instead. A revision that moves an item to another
    group moves it under that group's label."""

    def item(key, group):
        return (
            f'<lf-tab id="i-{key}" label="Item {key} with a long name"'
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
    # walking back onto it from the run after.
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
    label_shown = """() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const room = strip.getBoundingClientRect();
      const tab = strip.querySelector('[aria-selected="true"]');
      const label = tab.parentElement.querySelector('.lf-tab-group')
        .getBoundingClientRect();
      const faces = [...strip.querySelectorAll('.lf-tabstrip-scroll > span')]
        .filter((face) => face.checkVisibility())
        .map((face) => face.getBoundingClientRect());
      return faces.length > 0 && room.left <= label.left && label.right <= room.right
        && faces.every((face) => face.right <= label.left + 0.5 || label.right <= face.left + 0.5);
    }"""
    phone_tabs = phone.locator("#queue").get_by_role("tab")
    phone_tabs.first.click()
    phone.wait_for_function(label_shown)
    phone_tabs.first.focus()
    phone.keyboard.press("End")
    phone.keyboard.press("ArrowLeft")
    expect(phone_tabs.nth(4)).to_have_attribute("aria-selected", "true")
    phone.wait_for_function(label_shown)


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
    pane_posture(page, page.locator("#queue-pane"), "flow")
