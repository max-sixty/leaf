"""Board, suggestion, ask, and widget composition tests."""

import re
from itertools import pairwise
from pathlib import Path

import pytest
import turbohtml
from interact_support import (
    _start,
    wait_for,
)
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf import thread as thread_model
from leaf.render_checks import rendered, wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import (
    NESTED_PROPOSAL_PAGE,
    SUGGESTION_PAGE,
    live_url,
)
from render_cases_layout import (
    toggle_queue,
    unfolded_button,
    with_one_ask,
)
from render_cases_navigation import (
    actions,
)
from render_cases_widgets import (
    BAD_CHARTS,
)
from render_harness import (
    BOARD_PAGE,
    RELEASE_FOCUS,
    CutOff,
    consume_browser_errors,
    expect_banner_control_offered,
    holding,
    leaf_page,
    open_page,
    opened_tab,
    resized,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    told,
    undo,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_widgets import MOTION_SAMPLE_CONTENT, PLAYGROUND_PAGE


def test_a_side_list_is_a_queue_beside_the_item_it_opens(browser, serve):
    """`list="side"` stands a tab set's list beside its panels: a queue whose items open
    one at a time. Where the set holds both the list is a column left of the open panel,
    walked down as well as across; on a phone it is one row above the panel, scrolled
    sideways, so the open item never lands below the whole queue. A row carries its
    panel's summary under its name, and beside the name its item's ask state: an open
    mark while the ask is unanswered, then a check and the picked option's title, said
    in the tab's description too. Answered is the log's reading, so an undo puts the
    open mark back once its answer is adopted, and the agent settling the question
    keeps the check. Answering moves no row. A tab's name is its label whatever the row shows, and a panel bounds what it
    holds."""

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
        '<lf-tabs id="queue" list="side">'
        + "".join(map(ticket, "abcdefgh"))
        + "</lf-tabs>",
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
    expect(tabs.first).to_have_accessible_description(
        "sev a · suggested fix. Unanswered"
    )
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
    expect(answer).to_have_attribute("data-lf-asks", "open")
    expect(answer).to_have_text("")
    page.locator("#o-a-fix .lf-pick").click()
    told(page)
    expect(answer).to_be_visible()
    expect(answer).to_have_text("Fix")
    expect(tabs.first).to_have_accessible_name("Ticket a")
    expect(tabs.first).to_have_accessible_description(
        "sev a · suggested fix. Answered: Fix"
    )
    expect(tabs.nth(1)).to_have_accessible_description(
        "sev b · suggested fix. Unanswered"
    )
    assert page.evaluate(rows) == heights
    page.keyboard.press("Tab")
    tabs.first.focus()
    clearance = tabs.first.evaluate("""tab => {
      const name = tab.querySelector('.lf-tab-name');
      const style = getComputedStyle(name);
      return {ringRight: name.getBoundingClientRect().right
        + parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset),
        answerLeft: tab.querySelector('.lf-tab-answer').getBoundingClientRect().left};
    }""")
    assert clearance["ringRight"] <= clearance["answerLeft"], clearance

    moved = page.locator("#queue").evaluate(
        """async queue => {
          const parent = queue.parentElement;
          const next = queue.nextSibling;
          const firstTab = queue.querySelector('.lf-tab-btn');
          await new Promise(resolve => {
            const observer = new MutationObserver(() => {
              observer.disconnect(); resolve();
            });
            observer.observe(parent, {childList: true});
            queue.remove();
            parent.insertBefore(queue, next);
          });
          return firstTab === queue.querySelector('.lf-tab-btn');
        }"""
    )
    assert moved, "moving the tab set replaced its retained answer row"
    expect(answer).to_have_text("Fix")
    expect(tabs.first).to_have_accessible_description(
        "sev a · suggested fix. Answered: Fix"
    )

    expect(page.locator(".lf-shortcut-bar")).to_contain_text("undo")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("z")
    holding(page, held, 1, "the undo")
    expect(answer).to_have_attribute("data-lf-asks", "answered")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(answer).to_have_attribute("data-lf-asks", "open")
    expect(answer).to_have_text("")
    expect(tabs.first).to_have_accessible_description(
        "sev a · suggested fix. Unanswered"
    )

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

    # On a phone the list is one row over the open item, however long the queue.
    resized(page, 390, 844)
    narrow = page.evaluate(boxes)
    assert narrow["stripBottom"] <= narrow["panelTop"] + 1, narrow
    row = page.evaluate("""() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const tops = [...strip.querySelectorAll('.lf-tab-btn')]
        .map((b) => Math.round(b.getBoundingClientRect().top));
      return {rows: new Set(tops).size, runsPast: strip.scrollWidth > strip.clientWidth};
    }""")
    assert row == {"rows": 1, "runsPast": True}, row

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


def test_an_ordinary_two_part_ask_retains_document_flow(browser, serve):
    """An Ask in a document is prose and a control, not a workspace's region.

    The control is the same Ask as a full-height workspace's body, which hands its height to
    the answer."""
    source = leaf_page(
        "Session-store follow-ups",
        """<h1>Session-store follow-ups</h1>
<lf-ask id="session-triage-decision">
  <h2>Which follow-ups should we keep?</h2>
  <lf-options id="session-triage" choose multiple>
    <lf-option id="rolling-expiry">Rolling expiry</lf-option>
    <lf-option id="bounded-fallback">Bounded fallback</lf-option>
  </lf-options>
</lf-ask>
""",
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
          const leaf = await window.__lfRuntimeImport('/runtime/reading-regions.js');
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


def test_pr_walkthrough_moves_from_semantic_call_to_exact_patch_comment(
    browser, serve, one_user
):
    """The specialized report's signature path reaches reviewable source evidence."""
    example = Path(__file__).parents[2] / "examples" / "pr-walkthrough.html"
    page = open_page(browser, live_url(serve(example)), context=one_user)

    page.get_by_role("tab", name="CallDiff").click()
    call_diff = page.locator("#pr-call-diagram")
    expect(call_diff.locator(".lf-call-line")).to_have_count(30)
    location = call_diff.get_by_role("link", name="src/summary.rs:259").first
    expect(location).to_be_visible()
    # Source links keep the platform's separate-tab route for root and child calls.
    # The original tab must keep its semantic view until an ordinary activation.
    before = page.url
    destination = before.split("#")[0] + "#pr-exact-patch"
    for link in [call_diff.locator(".lf-call-root-location a").first, location]:
        tab = opened_tab(
            page, destination, lambda link=link: link.click(modifiers=["ControlOrMeta"])
        )
        expect(tab.locator("#pr-exact-patch")).to_be_visible()
        tab.close()
        expect(page).to_have_url(before)
        expect(page.get_by_role("tab", name="CallDiff")).to_have_attribute(
            "aria-selected", "true"
        )
    tab = opened_tab(page, destination, lambda: location.click(button="middle"))
    expect(tab.locator("#pr-exact-patch")).to_be_visible()
    tab.close()
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
    example = Path(__file__).parents[2] / "examples" / "pr-walkthrough.html"
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
                  color: style.backgroundColor, border: style.borderTopColor,
                  x: box.x + parseFloat(style.left) + parseFloat(style.width) / 2 +
                    new DOMMatrixReadOnly(style.transform).m41,
                  y: box.y + parseFloat(style.top) +
                    new DOMMatrixReadOnly(style.transform).m42 + parseFloat(style.height) / 2,
                  labelCenter: item.querySelector(':scope > a').getBoundingClientRect().y +
                    parseFloat(getComputedStyle(item.querySelector(':scope > a')).lineHeight) / 2};
        })"""
    )
    assert markers[0]["content"] == '""'
    assert [marker["width"] for marker in markers] == [
        "9px",
        "6px",
        "3px",
        "3px",
        "6px",
        "6px",
        "6px",
    ]
    assert all(marker["height"] == marker["width"] for marker in markers)
    assert markers[0]["color"] != "rgba(0, 0, 0, 0)"
    spine_center = nav.locator(".lf-toc-rows").evaluate(
        """rows => {
          const line = getComputedStyle(rows, '::before');
          return rows.getBoundingClientRect().x + parseFloat(line.left) +
            parseFloat(line.width) / 2;
        }"""
    )
    assert all(
        marker["x"] == pytest.approx(spine_center, abs=0.01) for marker in markers
    )
    assert markers[0]["color"] == markers[0]["border"]
    assert markers[1]["color"] != markers[1]["border"]
    assert all(
        marker["y"] == pytest.approx(marker["labelCenter"], abs=1) for marker in markers
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
    assert lens_before["x"] + lens_before["width"] / 2 == pytest.approx(
        spine_center, abs=0.01
    )
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
        '.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-kind="Link"]'
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
    active_marker = prepare.evaluate(
        "node => { const s = getComputedStyle(node.parentElement, '::before'); "
        "return {fill: s.backgroundColor, border: s.borderTopColor}; }"
    )
    assert active_marker["fill"] == active_marker["border"]
    title_marker = start.evaluate(
        "node => { const s = getComputedStyle(node.parentElement, '::before'); "
        "return {fill: s.backgroundColor, border: s.borderTopColor}; }"
    )
    assert title_marker["fill"] != title_marker["border"]
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

    # The On panel stands over the map and changes nothing about it.
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
        "inactive: items.filter(item => item !== current).map(item => { "
        "const style = getComputedStyle(item, '::before'); return { "
        "ring: item.matches('.lf-toc-start, [data-lf-depth=\"0\"]'), "
        "background: style.backgroundColor, border: style.borderColor }; }) }; }"
    )
    canvas = page.locator("body").evaluate(
        "node => getComputedStyle(node).backgroundColor"
    )
    assert forced_colors["spine"] != canvas
    assert forced_colors["lens"] == forced_colors["current"]
    assert forced_colors["lens"] != forced_colors["spine"]
    rings = [item for item in forced_colors["inactive"] if item["ring"]]
    dots = [item for item in forced_colors["inactive"] if not item["ring"]]
    assert rings and dots
    assert all(item["background"] == canvas for item in rings)
    assert all(item["border"] == forced_colors["spine"] for item in rings)
    assert all(item["background"] == forced_colors["spine"] for item in dots)

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


@pytest.mark.parametrize("route", ["pointer", "keyboard"])
def test_board_moves_preserve_live_sample_and_control_state(browser, serve, route):
    """A preview names the move; only the original document and widgets stay live."""
    source = BOARD_PAGE.replace(
        "<strong>Heated perch</strong>",
        "<strong>Heated perch</strong>" + MOTION_SAMPLE_CONTENT,
    )
    page = open_page(browser, serve(source))
    live = page.frame_locator("#card-sample iframe")
    live.locator("#sample-beta").click()
    live.locator("#sample-draft .lf-draft-body").click()
    editor = live.locator("#sample-draft leaf-text")
    write(editor, "Edited sample draft")
    frame = page.locator("#card-sample iframe")
    frame.evaluate("frame => window.originalSampleDocument = frame.contentDocument")
    sample_url = frame.evaluate("frame => frame.src").rstrip("/")
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    card = page.locator("#card-heater")
    original = card.element_handle()
    card.evaluate("""card => {
      const radio = document.createElement('input');
      radio.type = 'radio'; radio.name = 'retained'; radio.checked = true;
      radio.dataset.lfGen = '1'; card.append(radio);
    }""")
    grip = card.locator(":scope > .lf-grip")
    grip.focus()
    page.keyboard.press("Space")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    expect(page.locator("#col-todo > #card-heater")).to_have_count(1)
    assert frame.evaluate(
        "frame => frame.contentDocument === window.originalSampleDocument"
    )
    expect(editor).to_have_js_property("value", "Edited sample draft")
    assert not actions(serve.page_dir)

    if route == "keyboard":
        grip.focus()
        page.keyboard.press("Space")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("Space")
    else:
        grip.scroll_into_view_if_needed()
        page.evaluate("""async () => {
          const {default: Sortable} = await import('/vendor/sortable.esm.js');
          window.previewAllocations = 0;
          for (const column of document.querySelectorAll('#sprint > lf-column')) {
            const owner = Sortable.get(column), produce = owner.option('cloneElement');
            owner.option('cloneElement', card => {
              window.previewAllocations++; return produce(card);
            });
          }
          window.previewFirstPaint = false;
          new MutationObserver((records, observer) => {
            const preview = document.querySelector('.lf-motion-preview.lf-inhand');
            if (!preview) return;
            observer.disconnect();
            requestAnimationFrame(() => window.previewFirstPaint =
              preview.textContent === 'Heated perch' && preview.getBoundingClientRect().height > 0);
          }).observe(document.body, {childList: true, subtree: true});
        }""")
        box = grip.bounding_box()
        source_box = card.bounding_box()
        assert box and source_box
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 20, y + 35, steps=8)
        preview = page.locator(".lf-motion-preview.lf-inhand")
        expect(preview).to_have_text("Heated perch")
        expect(page.locator(".lf-motion-preview")).to_have_count(1)
        assert page.evaluate("window.previewAllocations") == 2
        expect(page.locator("#col-todo > lf-card")).to_have_count(2)
        expect(preview.locator("*")).to_have_count(0)
        expect(preview).to_have_attribute("inert", "")
        page.wait_for_function("window.previewFirstPaint")
        bounds = preview.bounding_box()
        assert bounds and bounds["height"] <= 56
        assert bounds["width"] == pytest.approx(source_box["width"], abs=0.02)
        assert bounds["x"] <= x + 20 <= bounds["x"] + bounds["width"]
        expect(card.locator("input[type=radio]")).to_be_checked()
        expect(
            page.locator("#card-code, #card-tree, #card-sample iframe")
        ).to_have_count(3)
        destination = page.locator("#col-done").bounding_box()
        assert destination
        page.mouse.move(
            destination["x"] + destination["width"] / 2, destination["y"] + 40, steps=15
        )
        page.mouse.up()
        expect(preview).to_have_count(0)
    expect(page.locator("#col-done > #card-heater")).to_have_count(1)
    round_trip(page)
    assert frame.evaluate(
        "frame => frame.contentDocument === window.originalSampleDocument"
    )
    expect(editor).to_have_js_property("value", "Edited sample draft")
    expect(live.locator("#sample-beta")).to_have_attribute("chosen", "")
    card.click(position={"x": 10, "y": 10})
    undo(page)
    expect(page.locator("#col-todo > #card-heater")).to_have_count(1)
    assert original.evaluate("card => card === document.querySelector('#card-heater')")
    assert frame.evaluate(
        "frame => frame.contentDocument === window.originalSampleDocument"
    )
    expect(editor).to_have_js_property("value", "Edited sample draft")
    assert not [
        url
        for url in requests
        if url.rstrip("/") == sample_url or url.rstrip("/").endswith("/api/samples")
    ]


def test_structured_data_explorer_keeps_one_aggregate_query_configuration(
    browser, serve
):
    source = Path(__file__).parents[2] / "examples" / "data-explorer.html"
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
    expect(page.locator(".query-result-count")).to_have_text("2 releases shown")

    rows.nth(1).get_by_label("Value").fill("80")
    expect(page.locator(".query-result-count")).to_have_text("1 release shown")
    rows.nth(1).get_by_role("button", name="Move filter 2 up").click()
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-2",
        "filter-1",
    ]
    page.get_by_role("button", name="Add filter").click()
    expect(rows).to_have_count(3)
    expect(rows.nth(2).get_by_label("Value")).to_be_focused()
    rows.nth(2).get_by_label("Value").fill("risk")
    expect(page.locator(".query-result-count")).to_have_text("1 release shown")
    rows.nth(2).get_by_role("button", name="Remove filter 3").click()
    expect(rows).to_have_count(2)

    playground.get_by_role("button", name="Up to 6 results").click()
    expect(
        playground.locator('lf-playground-control[name="limit"]').get_by_role("slider")
    ).to_have_value("6")
    playground.get_by_role("button", name="Up to 4 results").click()
    expect(
        playground.locator('lf-playground-control[name="limit"]').get_by_role("slider")
    ).to_have_value("4")
    instruction = page.locator("#release-query-instruction")
    expect(instruction).to_contain_text("risk above 80 and region is europe")
    playground.get_by_role("button", name="Copy instruction").click()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == instruction.inner_text()

    page.reload()
    wait_until_ready(page)
    expect(rows).to_have_count(2)
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-2",
        "filter-1",
    ]
    expect(instruction).to_contain_text("risk above 80 and region is europe")
    playground.get_by_role("button", name="Reset").click()
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-1",
        "filter-2",
    ]
    expect(instruction).to_contain_text("region is europe and risk above 40")
    rows.nth(1).get_by_role("button", name="Remove filter 2").click()
    rows.first.get_by_role("button", name="Remove filter 1").click()
    expect(rows).to_have_count(0)
    expect(instruction).to_contain_text("Apply no filters")
    expect(page.locator(".query-result-count")).to_have_text("4 releases shown")
    playground.get_by_role("button", name="Up to 6 results").click()
    expect(page.locator(".query-result-count")).to_have_text("6 releases shown")
    playground.get_by_role("button", name="Up to 4 results").click()
    expect(page.locator(".query-result-count")).to_have_text("4 releases shown")
    playground.get_by_role("button", name="Reset").click()
    rows.first.get_by_label("Value").fill("asia")
    expect(instruction).to_contain_text("region is asia and risk above 40")

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
    wait_until_ready(page)
    expect(rows.first.get_by_label("Value")).to_have_value("asia")
    expect(instruction).to_contain_text("region is asia and risk above 40")
    undo(page)
    expect(rows.first.get_by_label("Value")).to_have_value("europe")
    expect(instruction).to_contain_text("region is europe and risk above 40")
    resized(page, 480, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 480
    resized(page, 1100, 320)
    expect(page.locator("#release-query-ask")).to_be_visible()


def test_built_code_comparison_drives_both_candidates(browser, serve):
    """Candidate measurements follow rendered readers through sizing and reconnection."""
    source = Path(__file__).parents[2] / "examples" / "code-comparison.html"
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, serve(source), context=context)
    playground = page.locator("#code-comparison-playground")
    candidate_a = page.locator('[data-candidate="A"]')
    candidate_b = page.locator('[data-candidate="B"]')

    expect(page.locator("lf-code.lf-rendered")).to_have_count(3)

    def measurements_match_readers():
        rendered(page)
        readings = page.locator("#code-reader-comparison .code-candidate").evaluate_all("""candidates =>
          candidates.map(candidate => {
            const pre = candidate.querySelector('lf-code pre');
            return {
              actual: candidate.querySelector('.code-measurement').textContent,
              expected: `${Math.round(pre.getBoundingClientRect().height)}px tall · ${pre.scrollWidth}px source width`
            };
          })""")
        assert len(readings) == 2, readings
        assert all(reading["actual"] == reading["expected"] for reading in readings), (
            readings
        )

    measurements_match_readers()
    initial_viewport = page.viewport_size
    resized(page, 390, 844)
    measurements_match_readers()
    page.locator("#code-reader-comparison").evaluate("""owner => {
      const parent = owner.parentNode, next = owner.nextSibling;
      owner.remove();
      parent.insertBefore(owner, next);
    }""")
    resized(page, initial_viewport["width"], initial_viewport["height"])
    measurements_match_readers()
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
    measurements_match_readers()
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
    measurements_match_readers()
    assert playground.evaluate("root => root.values.comparison") == {
        "candidateA": {"density": "compact", "wrap": False},
        "candidateB": {"density": "compact", "wrap": False},
    }

    playground.get_by_role("button", name="B at 320px").click()
    expect(
        playground.locator('lf-playground-control[name="width"]').get_by_role("slider")
    ).to_have_value("320")
    expect(playground.get_by_role("radio", name="B", exact=True)).to_be_checked()
    playground.get_by_role("button", name="A at 420px").click()
    expect(
        playground.locator('lf-playground-control[name="width"]').get_by_role("slider")
    ).to_have_value("420")
    playground.get_by_role("button", name="Reset").click()
    assert playground.evaluate("root => root.values.comparison") == {
        "candidateA": {"density": "compact", "wrap": False},
        "candidateB": {"density": "comfortable", "wrap": True},
    }

    playground.get_by_role("radio", name="B", exact=True).click()
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

    resized(page, 480, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 480
    expect(page.locator(".code-comparison-grid")).to_have_css(
        "grid-template-columns", re.compile(r"\d+(?:\.\d+)?px")
    )
    resized(page, 1100, 320)
    expect(page.locator("#code-comparison-ask")).to_be_visible()


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
        Path(__file__).parents[2] / "examples" / "notification-playground.html"
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
    thread_model.post_reply(
        serve.page_dir,
        {"to": comment["id"], "for": comment["id"]},
        "Added the deployment-run link to the artifact.",
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
    copy = playground.locator(".lf-playground-copy-trigger")
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
    # A changed accessible name is not news to a screen reader; the live region is.
    live = page.locator(".lf-live")
    expect(live).to_have_text("Instruction copied")
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
    expect(copy).to_have_attribute("data-copy-state", "success")
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
    expect(live).to_have_text("Could not copy the instruction")
    resized(page, 420, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 420
    assert " " not in playground.evaluate(
        "root => getComputedStyle(root).gridTemplateColumns"
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
          <lf-draft id="child-draft"><pre>A draft the candidate restyles too.</pre></lf-draft>
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

    # The reset child has an opaque origin. Collect its paints there, then request
    # the whole sequence after Reset completes across the browsing-context boundary.
    # The parent's answer to the child's connection is held for a few frames, as a
    # busy machine holds it: no frame the child shows meanwhile may be undressed,
    # including the draft's prepainted markdown, which makes itself visible.
    page.add_init_script("""(() => {
      if (window === top) return;
      const paints = [];
      let sampling = true;
      const tick = () => {
        for (const words of document.querySelectorAll('#child-note, #child-draft p'))
          if (words.checkVisibility({visibilityProperty: true, opacityProperty: true}))
            paints.push(getComputedStyle(words).color);
        if (sampling) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      window.addEventListener('message', event => {
        if (event.source !== parent || !event.ports.length || event.lfHeld) return;
        event.stopImmediatePropagation();
        setTimeout(() => {
          const held = new MessageEvent('message', {
            data: event.data, source: event.source, ports: [...event.ports],
          });
          held.lfHeld = true;
          window.dispatchEvent(held);
        }, 200);
      }, true);
      window.addEventListener('message', event => {
        if (event.source !== parent || event.data?.type !== 'lf-test-tone-read')
          return;
        requestAnimationFrame(() => {
          sampling = false;
          parent.postMessage({type: 'lf-test-tone-paints', paints}, '*');
        });
      });
    })()""")
    page.locator("#tone-sample").evaluate("sample => sample.reset()")
    page.locator("#tone-sample").evaluate("""sample => {
      window.lfTonePaints = null;
      const frame = sample.querySelector('iframe');
      const receive = event => {
        if (event.source !== frame.contentWindow
            || event.data?.type !== 'lf-test-tone-paints') return;
        window.lfTonePaints = event.data.paints;
        window.removeEventListener('message', receive);
      };
      window.addEventListener('message', receive);
      frame.contentWindow.postMessage({type: 'lf-test-tone-read'}, '*');
    }""")
    page.wait_for_function("window.lfTonePaints !== null")
    painted = page.evaluate("window.lfTonePaints")
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

    playground.get_by_role("switch", name="Dim").click()
    assert values()["dim"] is True
    assert child_button.evaluate(standing), "switch"
    page.get_by_role("button", name="Wide", exact=True).click()
    assert values()["width"] == 4
    assert child_button.evaluate(standing), "preset"
    slider = playground.get_by_role("slider", name="Width").bounding_box()
    page.mouse.click(slider["x"] + 2, slider["y"] + slider["height"] / 2)
    assert values()["width"] == 1
    assert child_button.evaluate(standing), "slider"
    page.mouse.move(slider["x"] + 2, slider["y"] + slider["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        slider["x"] + slider["width"] - 2,
        slider["y"] + slider["height"] / 2,
        steps=4,
    )
    page.mouse.up()
    assert values()["width"] == 4
    assert child_button.evaluate(standing), "slider drag"
    sample = page.locator("#ring-sample")
    sample.evaluate(
        """sample => {
          const restore = sample.restoreStanding;
          sample.restoreStanding = () => {
            window.releaseRestore = () => {
              window.restoreDone = restore.call(sample);
            };
            return Promise.resolve(false);
          };
        }"""
    )
    page.mouse.click(slider["x"] + 2, slider["y"] + slider["height"] / 2)
    note = page.get_by_role("textbox", name="Note")
    note.focus()
    expect(note).to_be_focused()
    page.evaluate("window.releaseRestore()")
    assert page.evaluate("() => window.restoreDone") is False
    expect(note).to_be_focused()
    sample.evaluate("sample => delete sample.restoreStanding")
    child_button.focus()
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
    playground.get_by_role("switch", name="Dim").click()
    page.keyboard.press("Space")
    assert values()["dim"] is False

    # A sample whose page stands on nothing holds no one there.
    page.frame_locator("#ring-sample iframe").get_by_text(
        "The page the candidate"
    ).click()
    thin.click()
    expect(thin).to_be_focused()


def test_suggestion_emphasis_skips_generated_interface_between_changed_words(
    browser, serve
):
    """A changed span may cross a nested widget without painting its generated UI."""
    page = open_page(browser, serve(NESTED_PROPOSAL_PAGE))
    page.locator('[data-lf-margin-for="route-ask"] .lf-margin-marker').click()
    page.locator("#route .lf-pick").first.focus()
    badges = page.locator("#route > lf-option > .lf-key-badge")
    expect(
        page.locator("#route > lf-option > .lf-key-badge[data-lf-binding-badge]")
    ).to_have_count(2)
    expect(badges).to_have_text(["1", "2"])

    assert page.locator("#nested-change > lf-new > p").evaluate(
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


def test_a_body_the_module_cannot_draw_says_why_over_its_source(browser, serve):
    """The body is the author's, and the author is the only party who can fix it, so a
    refusal says what is wrong and keeps the source under it: code that does not parse,
    in the parser's own words, a chart with no name for a user who cannot see it, a call
    to something Plot does not export, a drawing Plot already made, which is how Plot's
    own examples end, and a height the page could not have laid out before the chart
    drew. The author hears the same words as the page's
    `error` event, naming the chart, since the user seeing the box is not the author
    seeing it."""
    said = {
        "bad-syntax": "Unexpected token",
        "bad-label": "ariaLabel",
        "bad-mark": "Plot.barz is not a function",
        "bad-drawn": "rather than Plot.plot(...)",
        "bad-height": "as data-height on the element",
    }
    # Each refusal is the chart's own, so every bad body stands on one page.
    source = leaf_page(
        "bad charts",
        '<h1 id="t">Bad</h1>\n'
        + "\n".join(
            f'<lf-chart id="{chart_id}"><pre>\n{body}\n</pre></lf-chart>'
            for chart_id, body in BAD_CHARTS.items()
        ),
    )
    page = open_page(browser, serve(source))
    reports = {chart_id: f'<lf-chart id="{chart_id}"> failed: ' for chart_id in said}
    for chart_id, words in said.items():
        expect(page.locator(f"#{chart_id} .lf-error")).to_contain_text(words)
        # The source stays under the message: a refusal the user cannot check is half a
        # refusal.
        expect(page.locator(f"#{chart_id} .lf-error pre")).to_contain_text("marks")
    reported = wait_for(
        lambda: [
            event["text"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "error"
        ],
        lambda texts: len(texts) >= len(said),
        failure="not every refused chart reached the log as an error",
    )
    consume_browser_errors(page, *reports.values())
    for chart_id, words in said.items():
        mine = [text for text in reported if text.startswith(reports[chart_id])]
        assert len(mine) == 1 and words in mine[0], (chart_id, reported)
    assert len(reported) == len(said), reported


@pytest.mark.parametrize("webkit", [False, True], ids=["chromium", "webkit"])
def test_a_narrow_rename_header_reserves_basenames_before_folders(
    request, serve, webkit
):
    """A rename shares its available width before either path elides a basename."""
    previous = "legacy/worktrunk/skills/worktrunk/reference/original.py"
    path = "plugins/worktrunk/skills/worktrunk/reference/config.py"
    url = serve(
        leaf_page(
            "Rename allocation",
            '<h1 id="title">Review</h1><lf-diff id="patch" source="patch-data">'
            "<pre></pre></lf-diff>",
            layout=None,
        ),
        packages=("diff",),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "patch-data",
        f"diff --git a/{previous} b/{path}\nsimilarity index 50%\n"
        f"rename from {previous}\nrename to {path}\n--- a/{previous}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old()\n+new()\n",
    )
    browser = request.getfixturevalue("iphone" if webkit else "browser")
    page = open_page(None, url, context=browser) if webkit else open_page(browser, url)
    head = page.locator("#patch .lf-diff-head")
    file = page.locator("#patch .lf-diff-file")
    identity = file.get_attribute("data-lf-datum")
    reading = """head => {
      const width = node => {
        const range = new Range(); range.selectNodeContents(node);
        return range.getBoundingClientRect().width;
      };
      const path = head.querySelector('.lf-diff-path');
      return {
        path: path.getBoundingClientRect().width,
        bases: [...path.querySelectorAll('.lf-diff-base')].map(base => ({
          text: base.textContent, natural: width(base), allocated: base.getBoundingClientRect().width,
          box: base.getBoundingClientRect().toJSON(),
        })),
        directories: [...path.querySelectorAll('.lf-diff-dir')].map(dir => {
          return {allocated: dir.getBoundingClientRect().width,
            ellipsis: parseFloat(getComputedStyle(dir, '::before').width),
            visible: getComputedStyle(dir).opacity !== '0'};
        }),
        arrow: path.querySelector('.lf-diff-arrow').getBoundingClientRect().toJSON(),
        arrowMargins: parseFloat(getComputedStyle(path.querySelector('.lf-diff-arrow')).marginLeft)
          + parseFloat(getComputedStyle(path.querySelector('.lf-diff-arrow')).marginRight),
        actions: head.closest('.lf-diff-file').querySelector('.lf-diff-file-actions').children.length,
      };
    }"""
    folder_states = set()
    for width in (280, 390, 470, 800, 1400, 280):
        resized(page, width, 900)
        rendered(page)
        result = head.evaluate(reading)
        assert result["actions"] == 1, result
        assert [base["text"] for base in result["bases"]] == [
            "original.py",
            "config.py",
        ]
        names_fit = (
            sum(base["natural"] for base in result["bases"])
            + result["arrow"]["width"]
            + result["arrowMargins"]
            <= result["path"]
        )
        if names_fit:
            assert all(
                base["allocated"] >= base["natural"] - 0.5 for base in result["bases"]
            ), result
        else:
            assert all(base["allocated"] > 0 for base in result["bases"]), result
            assert all(
                directory["allocated"] == 0 for directory in result["directories"]
            ), result
        assert result["arrow"]["left"] > result["bases"][0]["box"]["right"], result
        assert result["bases"][1]["box"]["left"] > result["arrow"]["right"], result
        for directory in result["directories"]:
            assert directory["visible"] == (
                directory["allocated"] >= directory["ellipsis"]
            ), result
            folder_states.add(directory["visible"])
        assert file.get_attribute("data-lf-datum") == identity
        assert "legacy/" in head.aria_snapshot() and "plugins/" in head.aria_snapshot()
    assert folder_states == {False, True}
    page.get_by_role("button", name=f"Comment on {path}", exact=True).click()
    expect(page.locator("#lf-composer-quote")).to_contain_text(path)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.press("Escape")
