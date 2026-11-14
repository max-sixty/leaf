"""Modifier aiming and design-mode browser tests."""

import io
import json
import math
import re
from datetime import datetime, timedelta
from itertools import pairwise

import pytest
from interact_support import (
    SHIPPED_PACKAGES,
    append_carried_log_record,
    append_command,
    declare_idle,
    wait_for,
)
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    HOLD_MOTION,
    OBLIGATION_PAGE,
    OBLIGATIONS_PAGE,
    live_url,
)
from render_cases_layout import (
    AIM_PAINT_PAGE,
    AIM_SEAM,
    AIM_SEAM_PAGE,
    AIMED,
    CORNER_PAGE,
    DRAFT_MARK,
    DRAWN_MARK,
    FOCUS_IN_PAGE,
    LEGEND_TRUE,
    MARK,
    PAGE_MARKUP,
    assert_drawn_in,
    token_colour,
)
from render_cases_navigation import source_revision
from render_cases_widgets import (
    GENERIC_VISUAL_LAYER,
    GENERIC_VISUAL_PAGE,
    GENERIC_VISUAL_WIDGETS,
    PART_DIAGRAM_PAGE,
    PART_DIAGRAM_V2,
    PICTURE_PAGE,
    PREFIXED_VISUAL_PAGE,
    SHADOW_VISUAL_LAYER,
    SHADOW_VISUAL_PAGE,
    SHADOW_VISUAL_WIDGETS,
    STAGED_VISUAL_WIDGETS,
    prefixed_visual_layer,
)
from render_harness import (
    EDITOR_ROOTS,
    FOLLOWER_MARK,
    LONG_PAGE,
    PANEL,
    PREVIEW,
    RELEASE_FOCUS,
    REPLAYED_PAGE,
    SUBJECT_MARK,
    assert_follows_in_every_frame,
    draft_key,
    expect_comment_notes,
    field_press,
    gesture_writes,
    judge_watches,
    leaf_page,
    open_page,
    open_threads,
    pane_scroll_behavior,
    panel_settled,
    panel_view,
    regions_side_by_side,
    resized,
    round_trip,
    scroll_followers,
    scroll_settled,
    scroll_writes,
    select,
    selection_field,
    sending,
    stamp_page,
    stored_draft,
    stored_draft_text,
    told,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import anchor_capture as anchor_capture_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import passages as passages_model
from leaf import service as service_model
from leaf import structure as structure_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.render_gate.scheme import collect_page_exceptions
from leaf.served_state import context as served_context
from leaf.validation import composition as validation_model
from leaf_dev.browser import PANEL_THREAD
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


# One page for each reason an aimed press can still reach the page underneath it. The
# capture itself is layer-wide, so another example containing the same click or
# mousedown mechanism repeats the reading. These required paths are non-vacuity floors:
# a representative that loses the feature which earned its place fails rather than
# quietly shrinking the causal corpus.
TAB_AIM_PAGE = leaf_page(
    "tab aim",
    """
<h1>Review the route</h1>
<lf-tabs id="aim-tabs">
  <lf-tab id="aim-current" label="Current"><p>The current route is covered.</p></lf-tab>
  <lf-tab id="aim-context" label="Context"><p>Rain moved the route.</p></lf-tab>
</lf-tabs>
""",
)

AIM_PRESS_CASES = (
    (
        "tabs",
        TAB_AIM_PAGE,
        frozenset({"tab click"}),
    ),
    (
        "release-notes",
        named_source("release-notes"),
        frozenset({"draft mousedown", "suggestion margin control"}),
    ),
    (
        "ship-review",
        named_source("ship-review"),
        frozenset({"option click", "existing mark"}),
    ),
)


def open_compact_comment(page, text=None):
    """Read the in-place comment field after an aimed press."""
    bar = page.locator(".lf-fab-bar")
    field = page.locator(".lf-fab-input")
    composer = page.locator(".lf-composer")
    expect(bar).to_be_visible()
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(composer).to_have_attribute("data-lf-open", "")
    if text is None:
        return field
    else:
        page.keyboard.type(text)
        expect(field).to_have_js_property("value", text)
        expect(field).to_be_focused()
        expect(bar).to_be_visible()
        expect(composer).to_have_attribute("data-lf-open", "")
    return field


# The top of the window the page shows (geometry.js, `shownWindow`): what a float the
# page places stands below.
SHOWN_TOP = """async () => (await window.__lfWidgetApi()).shownWindow().top"""


def test_the_catalog_sidenote_can_be_aimed_whole(browser, serve):
    """The sidenote authors copy carries the identity its advertised aim needs.

    A handwritten fixture would prove the runtime and leave the catalog free to
    regress to an id-less note that renders normally but gives Alt nothing to outline.
    Drive that example itself through the whole gesture, from outline to anchored
    composer."""
    registry = validation_model.incoming_registry(SHIPPED_PACKAGES)
    sidenote = registry["aside.note"]["x-example"]
    html = LONG_PAGE.replace(
        '<h1 id="t">Long</h1>', f'<h1 id="t">Long</h1>\n{sidenote}'
    )
    page = open_page(browser, serve(html))
    note = page.locator("#logout-frequency")

    note.hover()
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("logout-frequency")
    note.click()
    page.keyboard.up("Alt")

    # The sequence already names Comment, so the durable composer is the focused field
    # beside the note. It grows in place, Shift+Enter adds a line, and Enter submits it.
    field = open_compact_comment(page, "why here")
    assert page.evaluate(DRAFT_MARK) == "logout-frequency"
    one_line = field.bounding_box()["height"]
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("because every active session must end before support continues")
    assert field.bounding_box()["height"] > one_line
    expect(page.locator(".lf-composer")).to_have_attribute("data-lf-open", "")
    with sending(page, "the compact comment"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["text"] == (
        "why here\nbecause every active session must end before support continues"
    )
    expect(page.locator(".lf-fab-bar")).to_be_hidden()


def test_a_compact_comment_carries_its_box_into_the_inline_thread(browser, serve):
    """A compact comment keeps its writing face as Send opens its target's thread.

    A pending margin repaint still opens the real card.
    """
    page = open_page(browser, serve(LONG_PAGE), init_script=HOLD_MOTION)
    resized(page, 1440, 900)
    target = page.locator("#p10")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"])
    field = open_compact_comment(page)
    compact = field.evaluate(
        "node => ({family: getComputedStyle(node).fontFamily, "
        "size: getComputedStyle(node).fontSize})"
    )
    assert page.locator(".lf-fab-bar .lf-compose-field").bounding_box()["height"] == 32
    write(field, "Carry this comment into its thread.")
    page.evaluate(
        """() => {
          window.__lfForceMarginRender = true;
          window.__lfRenderCycles = 0;
          const renderAgain = () => {
            if (!window.__lfForceMarginRender) return;
            window.__lfRenderCycles += 1;
            dispatchEvent(new Event('resize'));
            requestAnimationFrame(renderAgain);
          };
          requestAnimationFrame(renderAgain);
        }"""
    )
    page.wait_for_function("() => window.__lfRenderCycles > 0")
    with sending(page, "the compact comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    [admitted] = [
        e
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment" and e["text"] == "Carry this comment into its thread."
    ]

    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    page.evaluate("() => (window.__lfForceMarginRender = false)")
    expect(preview.get_by_text("Carry this comment into its thread.")).to_be_visible()
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    message = preview.locator(".lf-msg-body").first
    expect(preview.locator(".lf-page-thread")).to_have_attribute(
        "data-lf-thread", admitted["id"]
    )
    expect(message).to_have_text("Carry this comment into its thread.")
    full = message.evaluate(
        "node => ({family: getComputedStyle(node).fontFamily, "
        "size: getComputedStyle(node).fontSize})"
    )
    assert compact == full
    expect(message).to_have_text("Carry this comment into its thread.")


@pytest.mark.parametrize("width", [900, 1200])
def test_an_aimed_comment_keeps_its_place_with_on_me_open(browser, serve, width):
    """On Me stands over the page without moving its coordinate plane.

    A broad authored rule may position ordinary divs, and the view may arrive over a
    target without another pointer event. Neither may move the chrome's document origin or
    leave its reading of the page behind. Keep the whole comment route on the item the
    user pointed at.
    """
    source = OBLIGATIONS_PAGE.replace(
        "</head>",
        "<style>html { position: relative; margin-left: 40px; "
        "border-left: 30px solid transparent; } "
        "div { position: relative; }</style></head>",
    )
    page = open_page(browser, serve(source))
    # 900 leaves the composer no side lane, so it takes the vertical route; at 1200 the
    # root's margin once put it 40px left of its lane, over the item.
    resized(page, width, 900)

    target = page.locator("#lq-keep")
    # The expanded queue covers the center; keep the pointer on the exposed start,
    # where the comment press below also lands.
    target.hover(position={"x": 12, "y": 12})
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("lq-keep")
    # Open by script so the pointer remains parked on the target while the view arrives.
    page.locator(".lf-fp-on-user").evaluate("node => node.click()")
    panel_settled(page, view="queue")
    expect(page.locator("[data-lf-aimed]")).to_have_id("lq-keep")
    aligned = page.evaluate(
        """() => {
          const chrome = document.querySelector('.lf-chrome');
          const origin = chrome.getBoundingClientRect();
          return { rootPosition: getComputedStyle(document.documentElement).position,
                   bodyPosition: getComputedStyle(document.body).position,
                   chromeOrigin: [origin.left + scrollX, origin.top + scrollY] };
        }"""
    )
    assert aligned["rootPosition"] == "static", (
        "authored root positioning captured the document coordinate plane"
    )
    assert aligned["bodyPosition"] == "static", (
        "body became a moving containing block for document-attached chrome"
    )
    assert aligned["chromeOrigin"] == [0, 0], (
        "authored div positioning captured the chrome's document coordinate plane"
    )

    # The press lands on the obligation's start, clear of the panel at the window's foot.
    target.click(position={"x": 12, "y": 12})
    page.keyboard.up("Alt")
    open_compact_comment(page)
    placed = page.evaluate(
        """() => {
          const target = document.getElementById('lq-keep').getBoundingClientRect();
              const box = document.querySelector('.lf-fab-input').getBoundingClientRect();
          const overlaps = target.left < box.right && box.left < target.right
              && target.top < box.bottom && box.top < target.bottom;
          return { left: box.left, right: box.right, overlaps, width: innerWidth };
        }"""
    )
    assert 0 <= placed["left"] < placed["right"] <= placed["width"], (
        f"the composer is outside the viewport: {placed}"
    )
    assert not placed["overlaps"], f"the composer covers its aimed element: {placed}"


@pytest.mark.parametrize("width", [1440, 390])
def test_a_growing_text_comment_keeps_its_side_and_the_page_still(
    browser, serve, width
):
    """A growing editor keeps its side and stays in the window, and the page stays put.

    Without a horizontal rail, the compact field first uses a side with visible room,
    clear of its passage. It keeps that side while growing, inside the window, and never
    scrolls the page. Its corners keep the first and last line readable after the
    capsule becomes an editor.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Comment placement",
                '<h1>Comment placement</h1><div style="height: 50vh"></div>'
                '<p id="passage">A short phrase begins a '
                "paragraph with enough surrounding words to expose a field placed over "
                "the rest of the same line. Those surrounding words still belong to the "
                "passage being reviewed, even when the comment names only a few of them.</p>"
                '<p id="after">The following paragraph stays in ordinary reading flow.</p>'
                '<div style="height: 100vh"></div>',
            )
        ),
    )
    resized(page, width, 900)
    paragraph = page.locator("#passage")
    points = paragraph.evaluate(
        """el => {
          const node = el.firstChild;
          const first = document.createRange(), last = document.createRange();
          first.setStart(node, 2); first.setEnd(node, 3);
          last.setStart(node, 13); last.setEnd(node, 14);
          const a = first.getBoundingClientRect(), b = last.getBoundingClientRect();
          return [[a.left, a.top + a.height / 2], [b.right, b.top + b.height / 2]];
        }"""
    )
    select(page, *points)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    compact = field.bounding_box()
    placement = page.locator(".lf-fab-bar").get_attribute("data-lf-placement")
    before_scroll = page.evaluate("scrollY")
    clear = """() => {
          const target = document.getElementById('passage').getBoundingClientRect();
          const field = document.querySelector('.lf-fab-input').getBoundingClientRect();
          return field.right <= target.left || field.left >= target.right
            || field.bottom <= target.top || field.top >= target.bottom;
        }"""
    assert page.evaluate(clear)
    write(field, "test\n")
    content = "\n".join(
        f"Line {n}: every word of this longer comment needs to remain readable."
        for n in range(20)
    )
    write(field, content)
    expect(field).to_have_js_property("value", content)
    rendered(page)
    expanded = field.bounding_box()
    assert page.locator(".lf-fab-bar").get_attribute("data-lf-placement") == placement
    assert page.evaluate("scrollY") == before_scroll
    assert expanded["width"] > compact["width"]
    assert expanded["height"] > compact["height"] * 5
    assert expanded["x"] >= 0 and expanded["x"] + expanded["width"] <= width
    assert expanded["y"] >= 0 and expanded["y"] + expanded["height"] <= 900
    assert field.evaluate(
        "el => parseFloat(getComputedStyle(el).borderTopLeftRadius)"
    ) <= (compact["height"] / 2)
    page.mouse.move(8, 450)
    page.mouse.wheel(0, 300)
    page.wait_for_function("() => scrollY >= 300")
    expect(field).to_have_js_property("value", content)
    write(field, "Brief")
    expect(field).to_have_js_property("value", "Brief")
    assert field.bounding_box()["height"] == compact["height"]


def test_a_text_comment_chooses_above_when_the_page_has_more_room_there(browser, serve):
    """The stable vertical choice reads both the visible band and scroll travel. Growing
    past the room shown above, the box slides over its passage rather than scrolling the
    page, and a scroll then carries it with the passage."""
    passage = (
        "A passage near the end of its page has more reachable room above it. "
        + "Its full block must keep the same room while the viewport clips it. " * 5
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Comment above",
                f'<div style="height: 100vh"></div><p id="passage">{passage}'
                '</p><div style="height: 800px"></div>',
            )
        ),
    )
    resized(page, 390, 900)
    page.evaluate(
        "() => scrollTo({top: document.getElementById('passage').offsetTop - 300})"
    )
    rendered(page)
    paragraph = page.locator("#passage")
    points = paragraph.evaluate(
        """el => {
          const node = el.firstChild;
          const first = document.createRange(), last = document.createRange();
          first.setStart(node, 2); first.setEnd(node, 3);
          last.setStart(node, 18); last.setEnd(node, 19);
          const a = first.getBoundingClientRect(), b = last.getBoundingClientRect();
          return [[a.left, a.top + a.height / 2], [b.right, b.top + b.height / 2]];
        }"""
    )
    select(page, *points)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("data-lf-placement", "top-start")
    before_scroll = page.evaluate("scrollY")

    write(
        field,
        "\n".join(
            f"Line {line}: the whole comment remains above its passage."
            for line in range(40)
        ),
    )
    rendered(page)
    expect(bar).to_have_attribute("data-lf-placement", "top-start")
    assert page.evaluate("scrollY") == before_scroll
    offset = """() => document.querySelector('.lf-fab-bar').getBoundingClientRect().top
      - document.getElementById('passage').getBoundingClientRect().top"""
    grown = page.evaluate(offset)
    last_scroll = page.evaluate("scrollY")
    maximum_scroll = page.evaluate(
        "document.scrollingElement.scrollHeight - innerHeight"
    )
    assert maximum_scroll - last_scroll > 450
    page.mouse.move(8, 450)
    for _ in range(math.ceil((maximum_scroll - last_scroll) / 150)):
        page.mouse.wheel(0, 150)
        page.wait_for_function("before => scrollY > before", arg=last_scroll)
        scroll_settled(page)
        moved = page.evaluate("scrollY")
        assert moved > last_scroll
        expect(bar).to_be_visible()
        last_scroll = moved
    assert paragraph.evaluate("node => node.getBoundingClientRect().top < 48")
    expect(bar).to_have_attribute("data-lf-plane", "page")
    assert page.evaluate(offset) == pytest.approx(grown, abs=1)
    expect(field).to_be_focused()


def test_a_comment_on_a_scrolled_away_paragraph_returns_with_resume(browser, serve):
    """Scrolling its attachment away retains the writer's field for Resume writing,
    with the same words and focus. The page owns its scroll; the draft remains attached
    semantically to the original passage until the writer sends or dismisses it.
    """
    body = "".join(
        f'<p id="p{n}">Paragraph {n} carries enough ordinary reading text to be '
        "covered by a field that wandered into the column while the user scrolled "
        "past the passage the comment was written about.</p>"
        for n in range(30)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Scrolled-away passage",
                '<h1>Scrolled-away passage</h1><p id="passage">A short phrase begins a '
                "paragraph with enough surrounding words that a field seated beside the "
                "selection alone would stand inside the column rather than beside it.</p>"
                + body
                + '<div style="height: 100vh"></div>',
            )
        ),
    )
    # Wide enough that the column leaves a margin the bar fits in. A rail too narrow for
    # it is the other placement branch, which seats the bar over its own block's right
    # end by design; this test is about the branch that has a margin to stay in.
    resized(page, 1440, 900)
    points = page.locator("#passage").evaluate(
        """el => {
          const node = el.firstChild;
          const first = document.createRange(), last = document.createRange();
          first.setStart(node, 2); first.setEnd(node, 3);
          last.setStart(node, 13); last.setEnd(node, 14);
          const a = first.getBoundingClientRect(), b = last.getBoundingClientRect();
          return [[a.left, a.top + a.height / 2], [b.right, b.top + b.height / 2]];
        }"""
    )
    select(page, *points)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    write(field, "A short note.\nSecond line.\nThird line.")

    page.mouse.move(8, 450)
    page.mouse.wheel(0, 900)
    page.wait_for_function("() => scrollY >= 900")
    page.wait_for_function(
        "() => document.getElementById('passage').getBoundingClientRect().bottom < 0"
    )
    scroll_settled(page)

    assert not _draft_in_view(page, "A short note.\nSecond line.\nThird line.")
    assert page.locator(".lf-fab-bar").get_attribute("data-lf-plane") == "page"
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    wait_for(
        lambda: _draft_in_view(page, "A short note.\nSecond line.\nThird line."),
        bool,
        failure="Resume did not reveal the retained draft",
    )


def test_a_growing_comment_is_independent_of_page_controls(browser, serve):
    """Margin controls may be overlaid; they are not placement obstacles.

    This is the reported release-notes geometry: the comment begins beside Console,
    with its target's margin actions immediately below it. Treating those actions as
    hard obstacles first moved a growing draft above its text, then capped it at one
    line. Removing the peers must have no effect on the response rectangle at all.
    """
    page = open_page(
        browser,
        serve(named_source("release-notes")),
    )
    resized(page, 1337, 386)
    page.evaluate("() => { location.hash = '#rn-console-why' }")
    rendered(page)
    paragraph = page.locator("#rn-console-why")
    paragraph.click(modifiers=["Alt"])
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    compact = bar.bounding_box()
    compact_scroll = page.evaluate("scrollY")
    placement = bar.get_attribute("data-lf-placement")
    compact_height = field.bounding_box()["height"]
    write(field, "easato" * 30)
    page.wait_for_function(
        """height => {
          const field = document.querySelector('.lf-fab-input');
          return field.clientHeight === field.scrollHeight && field.clientHeight > height;
        }""",
        arg=compact_height,
    )
    # The field grows by CSS from the foot the bar stands on; placement takes the grown
    # bar back inside the boundary on the render that follows.
    rendered(page)
    grown = bar.bounding_box()
    grown_scroll = page.evaluate("scrollY")
    assert bar.get_attribute("data-lf-placement") == placement
    assert abs(grown["x"] - compact["x"]) <= 1, (compact, grown)
    ceiling = page.evaluate(SHOWN_TOP)
    assert grown["y"] >= ceiling and grown["y"] + grown["height"] <= 378, grown

    peers = page.evaluate(
        """() => {
          const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
          const overlaps = node => {
            const r = node.getBoundingClientRect();
            return r.width && r.height && r.width <= 64 && r.height <= 64 &&
              bar.left < r.right && r.left < bar.right &&
              bar.top < r.bottom && r.top < bar.bottom;
          };
          window.lfPlacementPeers = [...document.querySelectorAll('[data-lf-offer]')]
            .filter(node => !node.closest('.lf-chrome') && overlaps(node));
          return window.lfPlacementPeers.length;
        }"""
    )
    assert peers > 0, "the regression fixture has no margin control under the editor"
    page.evaluate(
        """() => {
          for (const node of window.lfPlacementPeers) {
            node.dataset.lfPriorDisplay = node.style.display;
            node.style.display = 'none';
          }
          dispatchEvent(new Event('resize'));
        }"""
    )
    rendered(page)
    without_peers = bar.bounding_box()
    without_peers_scroll = page.evaluate("scrollY")
    assert abs(without_peers["x"] - grown["x"]) <= 1, (grown, without_peers)
    assert (
        abs(without_peers["y"] + without_peers_scroll - grown["y"] - grown_scroll) <= 1
    ), (grown, without_peers)
    assert abs(without_peers["width"] - grown["width"]) <= 1
    assert abs(without_peers["height"] - grown["height"]) <= 1

    page.evaluate(
        """() => {
          for (const node of window.lfPlacementPeers) {
            node.style.display = node.dataset.lfPriorDisplay;
            delete node.dataset.lfPriorDisplay;
          }
          dispatchEvent(new Event('resize'));
        }"""
    )
    write(field, "A bounded draft remains reachable. " * 200)
    page.wait_for_function(
        """() => {
          const field = document.querySelector('.lf-fab-input');
          return field.scrollHeight > field.clientHeight;
        }"""
    )
    rendered(page)
    bounded = bar.bounding_box()
    ceiling = page.evaluate(SHOWN_TOP)
    assert bounded["y"] >= ceiling and bounded["y"] + bounded["height"] <= 378
    assert bar.get_attribute("data-lf-placement") == placement
    assert field.evaluate("node => node.scrollHeight > node.clientHeight")
    scrolled = field.evaluate(
        "node => { node.scrollTop = node.scrollHeight; return node.scrollTop; }"
    )
    assert scrolled > 0
    # The field's scroll queues placement through the shared captured-scroll listener.
    # Measuring natural growth must not reset the user to the first line of the draft.
    rendered(page)
    assert field.evaluate("node => node.scrollTop") == scrolled
    after = field.evaluate(
        "node => [node.scrollTop, node.scrollHeight - node.clientHeight]"
    )
    assert after[0] == min(scrolled, after[1])  # only the final room may clamp it
    write(field, "Short again")
    rendered(page)
    returned = bar.bounding_box()
    returned_scroll = page.evaluate("scrollY")
    assert abs(returned["x"] - compact["x"]) <= 1, (compact, returned)
    assert abs(returned["y"] + returned_scroll - compact["y"] - compact_scroll) <= 1, (
        compact,
        returned,
    )
    assert abs(returned["width"] - compact["width"]) <= 1, (compact, returned)
    assert abs(returned["height"] - compact["height"]) <= 1, (compact, returned)


# Where the side comment and what it holds stand: the bar's edges, the field's top and
# its scroll (the first line stands at that top only while the field is unscrolled), and
# The visible action's top.
SIDE_COMMENT = """() => {
  const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
  const field = document.querySelector('.lf-fab-input');
  const send = document.querySelector('.lf-fab-bar .lf-compose-field > button:not([hidden])');
  return {top: bar.top, bottom: bar.bottom, field: field.getBoundingClientRect().top,
          height: field.getBoundingClientRect().height, scrolled: field.scrollTop,
          send: send.getBoundingClientRect().top};
}"""


def test_a_side_comment_at_the_window_s_foot_rises_only_as_far_as_it_must(
    browser, serve
):
    """A side editor at the window foot grows upward, then scrolls within its frame."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A low passage",
                '<div style="height: 1200px"></div>'
                '<p id="passage">This passage has room beside it for a response.</p>'
                '<div style="height: 700px"></div>',
            )
        ),
    )
    resized(page, 1440, 900)
    # This margin stands beside the panel, so its frame can reach the window foot.
    foot = page.evaluate("innerHeight - 8")
    passage = page.locator("#passage")
    passage.evaluate(
        """(node, foot) => scrollBy({
          top: node.getBoundingClientRect().top - (foot - 200),
          behavior: 'instant'
        })""",
        foot,
    )
    rendered(page)
    passage.click(modifiers=["Alt"])
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    assert bar.get_attribute("data-lf-placement") == "right-start"
    assert (
        bar.evaluate(
            """async node => {
          const {left, right} = node.getBoundingClientRect();
          return (await window.__lfWidgetApi())
            .shownWindow({gap: 8, across: {left, right}}).bottom;
        }"""
        )
        == foot
    )
    resting = page.evaluate(SIDE_COMMENT)
    assert resting["bottom"] < foot - 20, (resting, foot)
    write(field, "\n".join(f"Line {n}" for n in range(6)))
    rendered(page)
    risen = page.evaluate(SIDE_COMMENT)
    assert risen["bottom"] == pytest.approx(foot, abs=1), (risen, foot)
    assert risen["top"] < resting["top"] - 20, (resting, risen)
    assert risen["scrolled"] == 0, risen
    write(field, "\n".join(f"Line {n}" for n in range(80)))
    rendered(page)
    assert field.evaluate("node => node.scrollHeight > node.clientHeight")
    assert page.evaluate(SIDE_COMMENT)["bottom"] <= foot + 0.5


# Where the side comment's outline is drawn, its top and its foot, and its first line
# of words and its Send's foot: its surface draws the outline, a pixel outside the cut
# of its fill (box-motion.js).
SIDE_COMMENT_DRAWN = r"""() => {
  const ground = document.querySelector('.lf-fab-ground');
  const at = ground.getBoundingClientRect();
  const [top, right = top, bottom = top] = /inset\(([^r)]*)/
    .exec(getComputedStyle(ground.querySelector('.lf-box-fill')).clipPath)[1]
    .trim().split(/\s+/).map(Number.parseFloat);
  const host = document.querySelector('.lf-fab-input');
  const words = window.editorRoots.get(host).querySelector('.cm-line');
  const send = document.querySelector('.lf-fab-bar .lf-compose-submit');
  return {
    top: at.top + top - 1,
    foot: at.bottom - bottom + 1,
    words: words.getBoundingClientRect().top,
    send: send.getBoundingClientRect().bottom,
  };
}"""


def from_the_edges(drawn):
    """How far the words stand below the drawn top edge and Send above its foot."""
    return [drawn["words"] - drawn["top"], drawn["foot"] - drawn["send"]]


def test_a_side_comment_s_words_and_send_keep_to_its_edges_as_lines_come_and_go(
    browser, serve
):
    """A line the comment box gains at the window's foot shifts it up in the frame the
    key lands, its words and Send with its edges, as a textarea's would; a line
    removed carries the words back down with the top edge over the floating boxes'
    tween while Send rides the foot (box-motion.js, "Whose change it is"). The new line
    used to travel too, hiding the word being typed until the edge reached it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A low passage",
                '<div style="height: 1200px"></div>'
                '<p id="passage">This passage has room beside it for a response.</p>'
                '<div style="height: 700px"></div>',
            )
        ),
        init_script=EDITOR_ROOTS,
    )
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    passage = page.locator("#passage")
    passage.evaluate(
        """node => scrollBy({
          top: node.getBoundingClientRect().top - (innerHeight - 260),
          behavior: 'instant'
        })"""
    )
    rendered(page)
    passage.click(modifiers=["Alt"])
    open_compact_comment(page, "Line 0")
    bar = page.locator(".lf-fab-bar")
    foot = bar.evaluate(
        """async node => {
          const {left, right} = node.getBoundingClientRect();
          return (await window.__lfWidgetApi())
            .shownWindow({gap: 8, across: {left, right}}).bottom;
        }"""
    )
    # Lines until one more takes the box past the window's foot.
    lines = 1
    while (box := bar.bounding_box())["y"] + box["height"] + 21 < foot:
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(f"Line {lines}")
        lines += 1
        rendered(page)
    hold = "() => { window.__lfAnimate = Element.prototype.animate;" + HOLD_MOTION + "}"
    release = (
        "() => { Element.prototype.animate = window.__lfAnimate;"
        " __lfHeld.splice(0).filter(motion => motion.playState !== 'idle')"
        ".forEach(motion => motion.finish()); }"
    )
    held_ground = """() => __lfHeld.some(motion =>
      motion.effect?.target?.matches?.('.lf-fab-ground'))"""
    stood = page.evaluate(SIDE_COMMENT_DRAWN)
    page.evaluate(hold)
    page.keyboard.press("Shift+Enter")
    # The line shifts the box up inside the window, which its placement does before
    # the frame paints; the box's reading follows in that frame.
    page.wait_for_function(
        "top => document.querySelector('.lf-fab-bar')"
        ".getBoundingClientRect().top < top - 0.5",
        arg=stood["top"],
    )
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => r()))")
    grown = page.evaluate(SIDE_COMMENT_DRAWN)
    laid = page.locator(".lf-fab-bar .lf-compose-field").bounding_box()
    assert not page.evaluate(held_ground)
    assert [grown["top"], grown["foot"]] == pytest.approx(
        [laid["y"], laid["y"] + laid["height"]], abs=1
    ), (laid, grown)
    assert grown["top"] < stood["top"] - 0.5, (stood, grown)
    assert from_the_edges(grown) == pytest.approx(from_the_edges(stood), abs=1), grown
    page.evaluate(release)
    rendered(page)
    stood = page.evaluate(SIDE_COMMENT_DRAWN)
    page.evaluate(hold)
    page.keyboard.press("Backspace")
    page.wait_for_function(held_ground)
    for at in (0, 60, 150):
        # A motion a later reading cancelled stays cancelled.
        page.evaluate(
            "at => __lfHeld.filter(motion => motion.playState !== 'idle')"
            ".forEach(motion => { motion.currentTime = at; })",
            at,
        )
        drawn = page.evaluate(SIDE_COMMENT_DRAWN)
        if at == 0:
            assert drawn == pytest.approx(stood, abs=1), (stood, drawn)
        assert from_the_edges(drawn) == pytest.approx(from_the_edges(stood), abs=1), (
            at,
            drawn,
        )
    page.evaluate(release)
    rendered(page)
    rest = page.evaluate(SIDE_COMMENT_DRAWN)
    assert from_the_edges(rest) == pytest.approx(from_the_edges(stood), abs=1)
    assert rest["top"] > stood["top"] + 0.5, (stood, rest)


def test_a_key_that_widens_the_comment_box_draws_it_at_once(browser, serve):
    """A comment box sizes to its words, so each key past its least width widens it;
    the box stands at its new width in the frame the key lands, as a textarea sized to
    its words does (box-motion.js, "Whose change it is"). Each key used to start a
    tween that trailed the caret, and the field's cut hid most of the glyph just
    typed until the tween caught up."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A passage with room",
                '<p id="passage">This passage has room around it for a response.</p>',
            )
        ),
    )
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1000, 800)
    page.locator("#passage").click(modifiers=["Alt"])
    open_compact_comment(page)
    box = page.locator(".lf-fab-bar .lf-compose-field")
    least = box.bounding_box()["width"]
    # Words until the box has begun to widen past its least width.
    for word in "the window is too short for what we see in practice".split():
        page.keyboard.type(f"{word} ")
        rendered(page)
        if box.bounding_box()["width"] > least + 0.5:
            break
    else:
        pytest.fail(f"the box never widened past {least}px")
    wide = box.bounding_box()["width"]
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.keyboard.type("m")
    page.wait_for_function(
        "wide => document.querySelector('.lf-fab-bar .lf-compose-field')"
        ".getBoundingClientRect().width > wide + 0.5",
        arg=wide,
    )
    # A reading of the box follows its size change before the frame after it paints.
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => r()))")
    drawn = page.evaluate(
        """() => {
          const ground = document.querySelector('.lf-fab-ground');
          const right = /inset\\(([^r)]*)/
            .exec(getComputedStyle(ground.querySelector('.lf-box-fill')).clipPath)[1]
            .trim().split(/\\s+/).map(Number.parseFloat)[1];
          const host = document.querySelector('.lf-fab-input');
          return {
            right: ground.getBoundingClientRect().right - right + 1,
            cut: getComputedStyle(host).getPropertyValue('--lf-field-cut').trim(),
          };
        }"""
    )
    assert drawn["right"] == pytest.approx(
        box.bounding_box()["x"] + box.bounding_box()["width"], abs=0.5
    )
    assert drawn["cut"] in ("", "none"), drawn


def test_a_comment_near_the_bottom_grows_up_before_it_scrolls(browser, serve):
    """The attached side stays stable while vertical shift consumes free room."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A low target",
                '<div style="height: 620px"></div><p id="low">'
                "This paragraph is near the bottom of the viewport.</p>"
                '<div style="height: 420px"></div>',
            )
        ),
    )
    resized(page, 800, 360)
    target = page.locator("#low")
    target.evaluate(
        """node => scrollBy({
          top: node.getBoundingClientRect().top - 280,
          behavior: 'instant'
        })"""
    )
    rendered(page)
    target.click(modifiers=["Alt"])
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    compact = bar.bounding_box()
    compact_target = target.bounding_box()
    placement = bar.get_attribute("data-lf-placement")
    ceiling = page.evaluate(
        """async () => (await window.__lfWidgetApi())
          .shownWindow({gap: 8}).top"""
    )
    assert compact["y"] > ceiling + 20, compact
    write(
        field,
        "\n".join(f"Line {n}: the whole draft remains reachable." for n in range(50)),
    )
    page.wait_for_function(
        """() => {
          const field = document.querySelector('.lf-fab-input');
          return field.scrollHeight > field.clientHeight;
        }"""
    )
    box = bar.bounding_box()
    assert box["y"] >= ceiling and box["y"] + box["height"] <= 352, box
    assert box["y"] < compact["y"] - 20, (compact, box)
    assert abs(box["x"] - compact["x"]) <= 1, (compact, box)
    assert bar.get_attribute("data-lf-placement") == placement
    assert field.evaluate("node => node.scrollHeight > node.clientHeight")
    write(field, "Short again")
    rendered(page)
    returned = bar.bounding_box()
    returned_target = target.bounding_box()
    assert abs(returned["x"] - compact["x"]) <= 1, (compact, returned)
    assert (
        abs(returned["y"] - returned_target["y"] - compact["y"] + compact_target["y"])
        <= 1
    )


def test_a_comment_uses_the_viewport_when_its_target_fills_the_vertical_lane(
    browser, serve
):
    """A target occupying the lane does not reduce its editor to one line."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A section target",
                '<section id="target" style="min-height: 150vh">'
                "<h2>The section begins at the top of the reading band</h2>"
                "<p>Its content continues past the bottom of the viewport.</p>"
                '<div style="height: 480px"></div></section>',
            )
        ),
    )
    resized(page, 511, 336)
    target = page.locator("#target")
    target.click(modifiers=["Alt"], position={"x": 200, "y": 25})
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    assert bar.get_attribute("data-lf-placement") in {"top-start", "bottom-start"}

    write(field, "\n".join(f"Line {n}: keep the draft visible." for n in range(3)))
    rendered(page)
    assert field.evaluate(
        "node => node.clientHeight === node.scrollHeight && node.clientHeight > 60"
    )

    write(field, "\n".join(f"Line {n}: keep the draft reachable." for n in range(40)))
    page.wait_for_function(
        """() => {
          const field = document.querySelector('.lf-fab-input');
          return field.scrollHeight > field.clientHeight;
        }"""
    )
    # The field's growth to its cap queues one more reveal of the caret at the end,
    # which runs at the field's next scroll; let it run before scrolling the field to
    # its top, or it scrolls the field back down and the wheel below moves the page.
    rendered(page)
    box = bar.bounding_box()
    ceiling = page.evaluate(SHOWN_TOP)
    assert box["y"] >= ceiling and box["y"] + box["height"] <= 328, box

    field.evaluate("node => { node.scrollTop = 0; }")
    field.click(position={"x": 20, "y": 20})
    field_scroll = field.evaluate("node => node.scrollTop")
    page_scroll = page.evaluate("scrollY")
    page.mouse.wheel(0, 180)
    page.wait_for_function(
        "before => document.querySelector('.lf-fab-input').scrollTop > before",
        arg=field_scroll,
    )
    assert page.evaluate("scrollY") == page_scroll


def test_a_long_comment_stays_in_view_when_its_target_fills_the_viewport(
    browser, serve
):
    """Without an adjacent free rail, the viewport still bounds the writing surface."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A tall target",
                '<p id="tall" style="min-height: 150vh; margin: 0">'
                "A tall paragraph occupies all the available reading space.</p>",
            )
        ),
    )
    resized(page, 700, 360)
    page.evaluate("() => scrollBy({top: 80, behavior: 'instant'})")
    rendered(page)
    target = page.locator("#tall")
    target.click(modifiers=["Alt"], position={"x": 20, "y": 90})
    field = open_compact_comment(page)
    write(
        field,
        "\n".join(f"Line {n}: the whole draft remains reachable." for n in range(50)),
    )
    rendered(page)
    bounds = target.bounding_box()
    ceiling = page.evaluate(SHOWN_TOP)
    assert bounds["y"] <= ceiling and bounds["y"] + bounds["height"] >= 352, (
        "the target must fill the available viewport so no adjacent rail can fit"
    )
    box = field.bounding_box()
    assert box["y"] >= ceiling and box["y"] + box["height"] <= 352, box
    assert field.evaluate("node => node.scrollHeight > node.clientHeight")


TALL_ROWS_PAGE = leaf_page(
    "A tall section",
    "<h1>Review</h1><p>These rows are commented on as one section.</p>"
    '<section id="whole"><h2>Rows</h2>'
    + "".join(f"<p>Row {n}: compute({n});</p>" for n in range(80))
    + "</section><p>After the rows.</p>",
)
# Where the pointed row, the comment box and the margin cluster stand in the window.
POINTED_ROW = """() => {
  const row = document.querySelectorAll('#whole p')[50].getBoundingClientRect();
  const top = (selector) =>
    document.querySelector(selector)?.getBoundingClientRect().top ?? null;
  return { row: row.top, height: row.height, bar: top('.lf-fab-bar'),
           cluster: top('.lf-margin-cluster'), card: top('.lf-margin-preview'),
           section: document.querySelector('#whole').getBoundingClientRect().top };
}"""


def test_a_comment_on_a_whole_target_stands_by_the_row_it_was_pointed_at(
    browser, serve
):
    """⌥-clicking a row deep in a section comments on the whole section, while
    the user pointed at that row. The box to write in, the cluster the sent
    comment leaves and the card it opens stand level with it rather than at the
    section's top, a screen above; `t` travels back to that row.
    The event still names the whole section: where the comment stands is presentation."""
    page = open_page(browser, serve(TALL_ROWS_PAGE))
    resized(page, 1440, 900)
    row = page.locator("#whole p").nth(50)
    row.scroll_into_view_if_needed()
    rendered(page)
    row.click(modifiers=["Alt"], position={"x": 60, "y": 5})
    field = open_compact_comment(page)
    rendered(page)
    at = page.evaluate(POINTED_ROW)
    assert at["section"] < -at["height"] * 20, at
    assert abs(at["bar"] - at["row"]) <= 2 * at["height"], (
        f"the comment box stands {at['row'] - at['bar']:.0f}px from the row: {at}"
    )

    write(field, "Why this line?")
    with sending(page, "the comment on the whole section"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["anchor"]) == ("comment", {"section": "whole"})
    rendered(page)
    at = page.evaluate(POINTED_ROW)
    assert abs(at["cluster"] - at["row"]) <= at["height"], (
        f"the cluster stands {at['row'] - at['cluster']:.0f}px from the row: {at}"
    )
    assert abs(at["card"] - at["row"]) <= 2 * at["height"], at

    page.keyboard.press("Escape")
    page.evaluate("() => scrollTo({ top: 0, behavior: 'instant' })")
    rendered(page)
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    scroll_settled(page)
    rendered(page)
    at = page.evaluate(POINTED_ROW)
    assert 0 < at["row"] < 900 and abs(at["card"] - at["row"]) <= 2 * at["height"], (
        f"`t` did not bring the pointed row and its card back: {at}"
    )


TALL_OBLIGATION_PAGE = leaf_page(
    "A tall Ask",
    '<h1>Route</h1><lf-ask id="way"><h2>Which way?</h2>'
    + "".join(
        f"<p>Consideration {n} about the route, at length.</p>" for n in range(30)
    )
    + '<lf-options id="route" choose><lf-option id="north">North</lf-option>'
    '<lf-option id="south">South</lf-option></lf-options></lf-ask><p>After.</p>',
)
# Every margin row by what it stands for: the rows about `target`, each as its top
# measured from the target's, and whether it holds a comment. Rows are read by their
# host, which the margin keeps for as long as what it stands for stands.
ROWS_ON = """([target]) => {
  const at = document.getElementById(target).getBoundingClientRect().top;
  window.__rows ??= new Map();
  return [...document.querySelectorAll('[data-lf-margin-for]')]
    .filter((row) => row.lfTarget?.id === target)
    .map((row) => {
      if (!window.__rows.has(row)) window.__rows.set(row, window.__rows.size);
      return [window.__rows.get(row), Math.round(row.getBoundingClientRect().top - at)];
    })
    .sort((a, b) => a[0] - b[0]);
}"""


@pytest.mark.parametrize("case", ["obligation", "thread"])
def test_a_pointed_comment_keeps_the_rows_still_owed(browser, serve, case):
    """A comment pointed at a row deep in its target stands its own margin row there;
    the rest of the target's margin does not follow it. Commenting on an obligation hands it
    to the agent, so its obligation marker leaves. A comment already on a thread target
    stays at the target's top, where `t` still lands it."""
    if case == "obligation":
        url, target = serve(TALL_OBLIGATION_PAGE), "way"
        row = f"#{target} p >> nth=25"
    else:
        url, target = serve(TALL_ROWS_PAGE), "whole"
        first = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "The whole section first.",
                "anchor": {"section": "whole"},
            },
        )["id"]
        row = "#whole p >> nth=50"
    page = open_page(browser, url)
    resized(page, 1440, 900)
    rendered(page)
    before = page.evaluate(ROWS_ON, [target])
    assert before and all(abs(top) <= 8 for _, top in before), (
        f"the target's own rows must start at its top: {before}"
    )

    pointed = page.locator(row)
    pointed.scroll_into_view_if_needed()
    rendered(page)
    pointed.click(modifiers=["Alt"], position={"x": 20, "y": 5})
    write(open_compact_comment(page), "About this row.")
    with sending(page, "the pointed comment"):
        page.keyboard.press("Enter")
    assert events_model.read_events(serve.page_dir)[-1]["anchor"] == {"section": target}
    page.keyboard.press("Escape")
    rendered(page)
    depth = pointed.evaluate(
        "(row, target) => Math.round(row.getBoundingClientRect().top"
        " - document.getElementById(target).getBoundingClientRect().top)",
        target,
    )
    after = dict(page.evaluate(ROWS_ON, [target]))
    if case == "obligation":
        expect(
            page.locator(f'[data-lf-margin-for="{target}"] > .lf-margin-marker')
        ).to_have_attribute("data-lf-kinds", "comment")
    else:
        for index, top in before:
            assert abs(after.get(index, 1e9) - top) <= 8, (
                f"row {index} of the target moved from {top} to {after.get(index)}: {after}"
            )
    added = (
        list(after.values())
        if case == "obligation"
        else [top for index, top in after.items() if index not in dict(before)]
    )
    assert len(added) == 1 and abs(added[0] - depth) <= 30 and depth > 400, (
        f"the pointed comment has no row of its own at {depth}: {after}"
    )
    if case == "thread":
        # The walk reaches the thread already there at the target's top, in page order
        # before the pointed one.
        page.keyboard.press("t")
        shown = page.locator(".lf-margin-preview .lf-page-thread")
        expect(shown).to_have_count(1)
        if shown.get_attribute("data-lf-thread") != first:
            page.keyboard.press("Shift+t")
        expect(shown).to_have_attribute("data-lf-thread", first)
        scroll_settled(page)
        rendered(page)
        card = page.locator(".lf-margin-preview").bounding_box()
        top = page.locator("#whole").bounding_box()["y"]
        assert abs(card["y"] - top) <= 60, (card, top)


def test_a_pointed_comment_finds_its_row_again_after_a_revision_replaces_it(
    browser, serve
):
    """A revision replaces the pointed row's DOM nodes but keeps its words.
    The comment keeps its place beside that row."""
    page = open_page(browser, live_url(serve(TALL_ROWS_PAGE)))
    resized(page, 1440, 900)
    row = page.locator("#whole p").nth(50)
    row.scroll_into_view_if_needed()
    rendered(page)
    row.click(modifiers=["Alt"], position={"x": 60, "y": 5})
    write(open_compact_comment(page), "Why this line?")
    with sending(page, "the pointed comment"):
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    rendered(page)
    page.evaluate("() => { window.__row = document.querySelectorAll('#whole p')[50]; }")
    (serve.page_dir / "index.html").write_text(
        TALL_ROWS_PAGE.replace("A tall section", "A tall section, revised")
        .replace('<section id="whole">', '<article id="whole">')
        .replace("</section>", "</article>")
    )
    told(page)
    expect(page).to_have_title("A tall section, revised")
    page.wait_for_function(
        "() => document.querySelectorAll('#whole p')[50] !== window.__row"
    )
    rendered(page)
    at = page.evaluate(POINTED_ROW)
    assert abs(at["cluster"] - at["row"]) <= at["height"], (
        f"the revision took the comment's row {at['row'] - at['cluster']:.0f}px from"
        f" the row it was pointed at: {at}"
    )


def point_a_comment(page, text, x=60):
    """⌥-click row 51 of the tall section at `x` and send `text`, leaving the card."""
    row = page.locator("#whole p").nth(50)
    row.scroll_into_view_if_needed()
    rendered(page)
    row.click(modifiers=["Alt"], position={"x": x, "y": 5})
    write(open_compact_comment(page), text)
    with sending(page, text):
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    rendered(page)


def test_a_pointed_cards_reply_brings_the_pointed_row_back(browser, serve):
    """Typing in a card scrolled away brings it back, and for a pointed comment what it
    stands by is its row: the section around it still overlaps the window, so bringing
    the section into view moved nothing and left the reply below the window."""
    page = open_page(browser, serve(TALL_ROWS_PAGE))
    resized(page, 1440, 900)
    expect(page.locator("#whole p")).to_have_count(80)
    point_a_comment(page, "Why this line?")
    page.evaluate("() => scrollTo({ top: 0, behavior: 'instant' })")
    rendered(page)
    page.keyboard.press("t")
    reply = page.locator(".lf-margin-preview leaf-text")
    expect(reply).to_be_visible()
    scroll_settled(page)
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    page.keyboard.type("Still")
    page.evaluate("() => scrollBy({ top: -700, behavior: 'instant' })")
    rendered(page)
    below = reply.bounding_box()
    assert below["y"] > 900, f"the scroll must carry the reply off the window: {below}"
    page.keyboard.type(" here")
    scroll_settled(page)
    rendered(page)
    box = reply.bounding_box()
    assert box["y"] >= 0 and box["y"] + box["height"] <= 900, (
        f"typing left the reply off the window: {box}"
    )


def test_comments_pointed_at_one_row_stand_as_one_margin_row(browser, serve):
    """Two comments pointed at one line, at two places along it, stand as one margin row
    at the line, as two comments on the section's own top share its row; the row the first
    made is the one the second joins."""
    page = open_page(browser, serve(TALL_ROWS_PAGE))
    resized(page, 1440, 900)
    expect(page.locator("#whole p")).to_have_count(80)
    point_a_comment(page, "First about this line.", x=60)
    first = page.evaluate(ROWS_ON, ["whole"])
    point_a_comment(page, "Second about this line.", x=200)
    second = page.evaluate(ROWS_ON, ["whole"])
    assert len(first) == 1 and second == first, (
        f"the second comment made a margin row of its own: {first} then {second}"
    )


def test_a_pointed_row_is_announced_where_it_stands_and_by_its_words(browser, serve):
    """A listener places a margin row by how far down the page it is and tells rows
    apart by their names. A pointed row stands two-thirds of the way down the section, and
    it is named by the line it stands by, not only by the section the target's own row
    names."""
    page = open_page(browser, serve(TALL_ROWS_PAGE))
    resized(page, 1440, 900)
    expect(page.locator("#whole p")).to_have_count(80)
    point_a_comment(page, "Why this line?")
    spoken = page.evaluate(
        """() => {
          const main = document.querySelector('main');
          const row = document.querySelectorAll('#whole p')[50].getBoundingClientRect();
          const host = [...document.querySelectorAll('[data-lf-margin-for]')]
            .find((host) => host.lfTarget?.id === 'whole');
          return {
            at: Math.round((row.top - main.getBoundingClientRect().top)
                           / main.scrollHeight * 100),
            name: host.querySelector('.lf-margin-marker').getAttribute('aria-label'),
          };
        }"""
    )
    said = re.search(r"(\d+) percent down", spoken["name"])
    assert said and abs(int(said[1]) - spoken["at"]) <= 3, spoken
    assert "Row 50: compute(50);" in spoken["name"], spoken


POINTED_WITHIN = {
    # A paragraph's own lines: a comment on its words and one on code inline in its third
    # line both stand at the paragraph.
    "code": (
        '<p id="within" style="width: 260px">'
        + "Words the paragraph runs through at length. " * 3
        + "<code>inline_code()</code> "
        + "and more words after it, to a fourth line. " * 2
        + "</p>",
        ["#within", "#within code"],
        0,
    ),
    # A drawing's shapes: the figure is one target however far down its picture stands.
    "drawing": (
        (
            '<figure id="within"><figcaption>A caption above the picture, which stands '
            "below it.</figcaption><svg viewBox='0 0 240 200' width='240' height='200'>"
            "<rect x='2' y='2' width='100' height='190' fill='#ddd'></rect></svg>"
            "</figure>"
        ),
        ["#within svg rect", "#within svg"],
        0,
    ),
    # A table's row: two cells of one row are the one line the user pointed at.
    "table": (
        '<table id="within">'
        + "".join(
            f"<tr><td>Row {n} first cell</td><td>Row {n} second cell</td></tr>"
            for n in range(40)
        )
        + "</table>",
        ["#within tr >> nth=30 >> td >> nth=0", "#within tr >> nth=30 >> td >> nth=1"],
        "#within tr >> nth=30",
    ),
    # A table's row whatever blocks its cells hold.
    "cell blocks": (
        '<table id="within">'
        + "".join(
            f"<tr><td><p>Row {n} first cell</p></td><td><p>Row {n} second</p></td></tr>"
            for n in range(40)
        )
        + "</table>",
        [
            "#within tr >> nth=30 >> td >> nth=0 >> p",
            "#within tr >> nth=30 >> td >> nth=1 >> p",
        ],
        "#within tr >> nth=30",
    ),
    # A target's first line: its own row stands there already, so a comment pointed at
    # it joins that row, an obligation's marker's, rather than standing pushed below it.
    "first line": (
        (
            '<lf-ask id="within"><h2>Which way?</h2><lf-options id="route" choose>'
            '<lf-option id="north">North</lf-option><lf-option id="south">South'
            "</lf-option></lf-options></lf-ask>"
        ),
        ["#within h2"],
        0,
    ),
}


@pytest.mark.parametrize("case", POINTED_WITHIN)
def test_comments_pointed_within_one_line_share_its_row(browser, serve, case):
    """A point is a line of the target, decided by how the page lays it out: words, a
    link or code inside the target's own lines stand at the target, a drawing's shapes
    have no lines, and a table's cells stand on their row. So two comments pointed
    within one line stand as one margin row, where that line is."""
    body, presses, line = POINTED_WITHIN[case]
    page = open_page(browser, serve(leaf_page("Within", f"<h1>Within</h1>{body}")))
    resized(page, 1440, 900)
    for n, press in enumerate(presses):
        pressed = page.locator(press)
        pressed.scroll_into_view_if_needed()
        rendered(page)
        pressed.click(modifiers=["Alt"], position={"x": 4, "y": 4})
        write(open_compact_comment(page), f"Comment {n}.")
        with sending(page, f"comment {n}"):
            page.keyboard.press("Enter")
        page.keyboard.press("Escape")
        rendered(page)
    depth = (
        page.locator(line).evaluate(
            "(row) => Math.round(row.getBoundingClientRect().top"
            " - document.getElementById('within').getBoundingClientRect().top)"
        )
        if line
        else 0
    )
    rows = page.evaluate(ROWS_ON, ["within"])
    assert len(rows) == 1 and abs(rows[0][1] - depth) <= 8, (
        f"comments within one line stand at {rows}, not as one row at {depth}"
    )
    if case == "table":
        # Named by the row's words as the page reads them, one cell apart from the next.
        name = page.evaluate(
            """() => [...document.querySelectorAll('[data-lf-margin-for]')]
              .find((host) => host.lfTarget?.id === 'within')
              .querySelector('.lf-margin-marker').getAttribute('aria-label')"""
        )
        assert "“Row 30 first cell Row 30" in name, name


def test_a_reflow_keeps_a_pointed_comment_in_its_row_and_its_reply_going(
    browser, serve
):
    """Which margin row a pointed comment stands in is the document's to say, so a
    reflow that moves its line further from the target's top moves the row with it and
    changes nothing else: the row is the same element, and the reply the user is
    writing keeps its words and the focus, in the floating panel once a phone's window
    leaves no room for the card."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Reflow",
                # Set close, so the pointed line starts within a margin row of the
                # section's top at full width and further than that once narrow.
                '<h1>Reflow</h1><section id="s"><p style="margin: 0">'
                + "An opening line that fits the column at full width and wraps when"
                ' narrow.</p><p style="margin: 0">The second paragraph,'
                " which the comment points at.</p></section>",
            )
        ),
    )
    resized(page, 1440, 900)
    first = page.locator("#s p").first
    one_line = first.bounding_box()["height"]
    second = page.locator("#s p").nth(1)
    second.click(modifiers=["Alt"], position={"x": 20, "y": 5})
    write(open_compact_comment(page), "About the second paragraph.")
    with sending(page, "the pointed comment"):
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    rendered(page)
    rows = page.evaluate(ROWS_ON, ["s"])
    assert len(rows) == 1, f"the comment on the section stands in no row of it: {rows}"
    page.keyboard.press("t")
    reply = page.locator(".lf-margin-preview leaf-text")
    expect(reply).to_be_visible()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    page.keyboard.type("Still writing")
    reply.evaluate("el => { window.lfTypedIn = el; }")

    # A phone's column is narrower than the opening line in any font; at 560px whether
    # it wraps depends on the font's width (Linux's did not).
    resized(page, 390, 900)
    rendered(page)
    assert first.bounding_box()["height"] > one_line * 1.5, (
        "the opening line must wrap for the reflow to move the pointed line"
    )
    after = page.evaluate(ROWS_ON, ["s"])
    assert [index for index, _ in after] == [index for index, _ in rows], (
        f"the reflow moved the comment to another margin row: {rows} then {after}"
    )
    typed = page.locator(".lf-fp-field leaf-text")
    expect(typed).to_be_focused()
    assert typed.evaluate("el => el === window.lfTypedIn")
    expect(typed).to_have_js_property("value", "Still writing")


def test_undoing_a_settle_brings_a_pointed_comment_back_to_its_row(browser, serve):
    """Settling a pointed comment and taking that back returns it where it stood, next to
    its line, whatever else is open on the target."""
    url = serve(TALL_ROWS_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Another thread, still open on the section.",
            "anchor": {"section": "whole"},
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 1440, 900)
    expect(page.locator("#whole p")).to_have_count(80)
    point_a_comment(page, "Why this line?")
    pointed = page.evaluate(ROWS_ON, ["whole"])
    assert len(pointed) == 2, pointed
    root = events_model.read_events(serve.page_dir)[-1]
    assert root["kind"] == "comment", root
    settle = append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    told(page)
    rendered(page)
    assert len(page.evaluate(ROWS_ON, ["whole"])) == 1
    append_carried_log_record(
        serve.page_dir, {"kind": "undo", "author": "user", "undoes": settle["id"]}
    )
    told(page)
    rendered(page)
    back = page.evaluate(ROWS_ON, ["whole"])
    assert sorted(top for _, top in back) == pytest.approx(
        sorted(top for _, top in pointed), abs=8
    ), f"the undone settle stood the comment at {back}, not {pointed}"


def test_a_comment_rechooses_after_target_width_reflow(browser, serve):
    """New horizontal room invalidates the old fallback instead of detaching it."""
    page = open_page(
        browser,
        serve(named_source("release-notes")),
    )
    resized(page, 700, 600)
    target = page.locator("#rn-console-why")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"], position={"x": 20, "y": 10})
    field = open_compact_comment(page)
    write(field, "Keep this comment connected while its paragraph changes width.")
    rendered(page)
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("aria-label", re.compile(r"^Respond to paragraph"))
    placement = bar.get_attribute("data-lf-placement")
    assert placement in {"top-start", "bottom-start"}, placement

    target.evaluate("node => { node.style.width = '180px' }")
    expect(bar).to_have_attribute("data-lf-placement", "right-start")
    after = bar.bounding_box()
    target_after = target.bounding_box()
    assert after["x"] >= target_after["x"] + target_after["width"] + 5, (
        target_after,
        after,
    )
    expect(field).to_have_js_property(
        "value", "Keep this comment connected while its paragraph changes width."
    )


def test_a_draft_below_its_passage_keeps_its_lane_whatever_it_holds(browser, serve):
    """Above or below a passage the field starts where the compact control would, ended
    on the passage's right edge. The bar's first measured width is the draft's, so a
    start taken from it put a restored draft further left, in a wider lane, than the
    same draft typed into an empty field."""
    page = open_page(
        browser,
        serve(named_source("release-notes")),
    )
    resized(page, 700, 600)
    target = page.locator("#rn-console-why")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"], position={"x": 20, "y": 10})
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    rendered(page)
    placement = bar.get_attribute("data-lf-placement")
    assert placement in {"top-start", "bottom-start"}, placement
    empty = bar.bounding_box()
    draft = "A draft long enough that its own width would widen the bar it opens in."
    write(field, draft)
    rendered(page)

    page.reload()
    wait_until_ready(page)
    expect(field).to_have_js_property("value", draft)
    assert bar.get_attribute("data-lf-placement") in {"top-start", "bottom-start"}
    rendered(page)
    restored = bar.bounding_box()
    assert abs(restored["x"] - empty["x"]) <= 1, (empty, restored)


# A transform on the target itself and one on a box around it; how a transform reaches
# the target's computed style is nothing the placement reads.
@pytest.mark.parametrize("move", ["inline", "ancestor"])
def test_a_side_comment_rechooses_its_rail_after_horizontal_target_motion(
    browser, serve, move
):
    """Reference geometry, not content size, invalidates the chosen margin rail."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 1440, 800)
    target = page.locator("#p10")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"])
    field = open_compact_comment(page)
    write(field, "Keep this comment connected when its paragraph moves.")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("data-lf-placement", "right-start")

    if move == "inline":
        target.evaluate("node => { node.style.transform = 'translateX(600px)' }")
    else:
        target.evaluate(
            "node => { node.parentElement.style.transform = 'translateX(600px)' }"
        )
    expect(bar).to_have_attribute("data-lf-placement", "left-start")
    target_after = target.bounding_box()
    after = bar.bounding_box()
    assert after["x"] + after["width"] <= target_after["x"] - 5, (
        target_after,
        after,
    )
    expect(field).to_have_js_property(
        "value", "Keep this comment connected when its paragraph moves."
    )
    assert not [
        write
        for write in scroll_writes(page, (5, 5, -5, 5))
        if any("lf-fab" in step for step in write["target"])
    ]


def test_a_comment_rechooses_its_side_after_vertical_target_motion(browser, serve):
    """Moving the reference across the block axis opens a better attachment side, once
    a resize asks for the side again: the room the page can make over the paragraph
    moves with it (comment-placement.js)."""
    page = open_page(
        browser,
        serve(named_source("release-notes")),
    )
    resized(page, 700, 600)
    target = page.locator("#rn-console-why")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"], position={"x": 20, "y": 10})
    field = open_compact_comment(page)
    write(field, "Keep this comment connected when its paragraph moves vertically.")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("aria-label", re.compile(r"^Respond to paragraph"))
    expect(bar).to_have_attribute(
        "data-lf-placement", re.compile(r"^(top|bottom)-start$")
    )
    over = bar.get_attribute("data-lf-placement") == "top-start"

    # Keep the whole attachment visible. Moving it off screen changes the editor to
    # its window posture rather than choosing another side of an invisible target.
    target.evaluate(
        """async (node, up) => {
          const {shownWindow} = await window.__lfWidgetApi();
          const boundary = shownWindow({gap: 8}), box = node.getBoundingClientRect();
          const top = up ? boundary.top + 8
            : boundary.bottom - box.height - 8;
          node.style.transform = `translateY(${top - box.top}px)`;
        }""",
        over,
    )
    resized(page, 700, 601)
    expect(bar).to_have_attribute(
        "data-lf-placement", "bottom-start" if over else "top-start"
    )
    target_after = target.bounding_box()
    after = bar.bounding_box()
    if over:
        assert after["y"] >= target_after["y"] + target_after["height"] + 5, (
            target_after,
            after,
        )
    else:
        assert after["y"] + after["height"] <= target_after["y"] - 5, (
            target_after,
            after,
        )
    expect(field).to_have_js_property(
        "value", "Keep this comment connected when its paragraph moves vertically."
    )


def test_design_legend_tracks_a_height_only_page_reflow(browser, serve):
    """The one shell observer hears movement that no target observer can hear.

    A broad authored div rule must not capture the nested legend host. Once that host is
    stable, an un-ID block growing above an ID target changes the body's height and the
    target's position without changing the target's own size or mutating the DOM during
    the growth. The central body observation repaints the legend for that case.
    """
    source = LONG_PAGE.replace(
        "</head>",
        "<style>html { overflow-anchor: none; } div { position: relative; }</style></head>",
    )
    page = open_page(browser, serve(source))
    resized(page, 1200, 900)
    target = page.locator("#p30")
    target.evaluate("node => node.scrollIntoView({block: 'center'})")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    legend = page.locator('.lf-legend-box[data-lf-for="p30"]')
    expect(legend).to_be_visible()

    before = page.evaluate(
        """() => {
          const target = document.getElementById('p30').getBoundingClientRect();
          const legend = document.querySelector('.lf-legend-box[data-lf-for="p30"]')
            .getBoundingClientRect();
          return {targetTop: target.top, dx: legend.left - target.left,
                  dy: legend.top - target.top,
                  hostPosition: getComputedStyle(document.querySelector('.lf-legend')).position};
        }"""
    )
    assert before["hostPosition"] == "static"
    assert abs(before["dx"] + 1) < 2 and abs(before["dy"] + 1) < 2

    after = page.evaluate(
        """async () => {
          const target = document.getElementById('p30');
          const driver = document.createElement('div');
          driver.style.height = '0px';
          target.before(driver);
          await new Promise(done => requestAnimationFrame(done));
          const growth = driver.animate(
            [{height: '0px'}, {height: '160px'}],
            {duration: 220, easing: 'linear', fill: 'forwards'}
          );
          await growth.finished;
          await new Promise(done => requestAnimationFrame(
            () => requestAnimationFrame(() => requestAnimationFrame(done))
          ));
          const targetBox = target.getBoundingClientRect();
          const legendBox = document.querySelector('.lf-legend-box[data-lf-for="p30"]')
            .getBoundingClientRect();
          return {targetTop: targetBox.top, dx: legendBox.left - targetBox.left,
                  dy: legendBox.top - targetBox.top};
        }"""
    )
    assert after["targetTop"] - before["targetTop"] > 140
    assert abs(after["dx"] + 1) < 2 and abs(after["dy"] + 1) < 2, (
        f"the legend did not follow height-only page growth: {before} then {after}"
    )


def test_a_margin_preview_stands_clear_of_the_target_trace(browser, serve, monkeypatch):
    """A margin marker's preview is about its target, so it stands clear of the target
    and of the trace it summons around it, rather than painting over that trace."""
    single = OBLIGATION_PAGE.replace(
        '<lf-options id="jobs" choose multiple>', '<lf-options id="jobs" choose>'
    )
    page = open_page(browser, live_url(serve(single)))
    page_dir = serve.page_dir
    resized(page, 1440, 900)
    with sending(page, "the mounts choice"):
        page.locator("#job-mounts").click()
    logged_action = next(
        event
        for event in reversed(events_model.read_events(page_dir))
        if event.get("widget") == "jobs" and event.get("action") == "choose"
    )
    sent_at = datetime.fromisoformat(logged_action["ts"])
    advanced = (sent_at + timedelta(minutes=3)).isoformat()
    for clock_owner in (served_context, events_model, service_model):
        monkeypatch.setattr(clock_owner, "now_iso", lambda: advanced)
    declare_idle(page_dir)
    told(page)

    marker = page.locator('[data-lf-margin-for="jobs"] > .lf-margin-marker')
    expect(marker).to_have_attribute(
        "aria-label", re.compile(r"^Still queued for \w+,")
    )
    marker.hover()
    label = page.locator(PREVIEW)
    traced = page.locator("#jobs")
    expect(label).to_be_visible()
    expect(traced).to_have_attribute("data-lf-traced", "")
    label.evaluate(
        "node => Promise.all(node.getAnimations().map(animation => animation.finished))"
    )

    label_box = label.bounding_box()
    ring = traced.evaluate(MARK)["ring"]
    assert (
        label_box["x"] >= ring["right"]
        or label_box["x"] + label_box["width"] <= ring["left"]
        or label_box["y"] >= ring["bottom"]
        or label_box["y"] + label_box["height"] <= ring["top"]
    ), (label_box, ring)


def test_an_aim_at_a_seam_promises_the_element_its_press_takes(
    browser, serve, subtests
):
    """The outline and the press ask one question of one point, down to the sub-pixel.

    The outline hit-tests the pointer record the runtime keeps, and the press takes the
    target the browser resolved for it. `mousemove` carries the pointer's place rounded to
    a whole pixel, so a record kept from one is an answer about a place the pointer is
    not, and within a pixel of a seam that place is a different item: ⌥ over a choose
    group outlined the option above the seam and the press commented on the one below it.
    So the aim is put within a quarter pixel of a seam, where the true point and its
    rounded twin name different items, and the item it is held to is read off the point,
    since which of the two the true point is over depends on where in the pixel the seam
    fell.

    The fixture paragraphs butt, so a pointer resting on their shared edge is inside both
    by the width of a rounding, and nothing makes two hit tests tie-break a shared edge
    alike. The corpus sweep reaches this only where a page happens to put a seam under the
    point it picks, which is a fact about font metrics, so the seam is aimed at here, and
    the assertion is the platform-independent half: whichever way each reading rounds,
    both answer the same item."""
    page = open_page(browser, serve(AIM_SEAM_PAGE))

    with subtests.test(case="within a pixel of the seam"):
        seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
        assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
            "the fixture no longer straddles a seam — the aim point and the whole pixel "
            "it rounds to are not on the two items either side of it, so nothing here is "
            f"under test: {seam}"
        )
        page.mouse.move(seam["x"], seam["y"])
        page.keyboard.down("Alt")
        expect(page.locator("[data-lf-aimed]")).to_have_id(seam["at"])
        page.mouse.click(seam["x"], seam["y"])
        page.keyboard.up("Alt")
        # The press focuses Comment on the item the aim held.
        open_compact_comment(page)
        assert page.evaluate(DRAFT_MARK) == seam["at"]
        page.keyboard.press("Escape")
        expect(page.locator(".lf-fab-bar")).to_be_hidden()

    with subtests.test(case="on the shared edge"):
        edge = page.evaluate(
            """() => {
                const above = document.querySelector('#seam-upper').getBoundingClientRect();
                const below = document.querySelector('#seam-lower').getBoundingClientRect();
                return {y: above.bottom, apart: Math.abs(below.top - above.bottom),
                        x: above.left + above.width / 2};
            }"""
        )
        assert edge["apart"] < 0.5, (
            f"the cells stand {edge['apart']}px apart, so this aims at a gap and not at "
            "the seam the two readings can differ over"
        )
        page.mouse.move(edge["x"], edge["y"])
        page.keyboard.down("Alt")
        promised = page.evaluate(AIMED)
        assert promised in ("seam-upper", "seam-lower"), (
            f"the aim promised {promised} on the seam between the two cells, so the "
            "reading under test never happened"
        )
        page.mouse.click(edge["x"], edge["y"])
        page.keyboard.up("Alt")
        # The press focuses Comment on what it took.
        open_compact_comment(page)
        assert page.evaluate(DRAFT_MARK) == promised, (
            f"the outline promised {promised} on the seam and the press commented on "
            f"{page.evaluate(DRAFT_MARK)}"
        )


def test_the_armed_page_promises_only_what_a_press_would_take(browser, serve, subtests):
    """Holding ⌥ arms the page, and what it shows answers for the next press wherever
    the pointer and the page now stand, while the chrome keeps its own presses."""
    page = open_page(browser, serve(LONG_PAGE))

    # A press can be the first pointer event, and capture still reads its position. Aim
    # claims pointerdown during capture and stops the gesture before it reaches the page,
    # so the shared position recorder has to run earlier in that same phase: a bubble
    # listener never sees this event, and aim would ask about the stale initial point
    # instead of the paragraph the browser dispatched the press to. This case runs first,
    # since any earlier pointer move would leave that stale point on the same paragraph.
    with subtests.test(case="a first press records its pointer before claiming it"):
        page.locator("#p2").evaluate(
            """target => {
              const box = target.getBoundingClientRect();
              const init = {
                bubbles: true,
                clientX: box.left + box.width / 2,
                clientY: box.top + box.height / 2,
                altKey: true,
              };
              target.dispatchEvent(new PointerEvent("pointerdown", init));
              target.dispatchEvent(new MouseEvent("mousedown", init));
              target.dispatchEvent(new PointerEvent("pointerup", init));
              target.dispatchEvent(new MouseEvent("mouseup", init));
              target.dispatchEvent(new MouseEvent("click", {...init, detail: 1}));
            }"""
        )
        open_compact_comment(page)
        assert page.evaluate(DRAFT_MARK) == "p2"
        page.keyboard.press("Escape")
        expect(page.locator(".lf-fab-bar")).to_be_hidden()
        page.evaluate(RELEASE_FOCUS)

    # Holding ⌥ used to draw a plain arrow over the whole page, which leaves the one
    # question the outline can't answer for a user who hasn't looked yet: would this click
    # do anything at all? An armed press takes the addressable element under it and acts
    # on nothing where there is none (claimPress), so the hand and the arrow are those two
    # states, read where the user's pointer is, since the aim declares the cursor on body
    # and the promise is only kept if it arrives at the glyphs. `auto` is the resting
    # state: unarmed, the browser draws an I-beam over words.
    with subtests.test(case="the cursor says whether a press would take anything"):
        at_pointer = """([x, y]) =>
            getComputedStyle(document.elementFromPoint(x, y)).cursor"""
        on_item = page.locator("#p2").evaluate(
            "el => { const r = el.getBoundingClientRect();"
            " return [r.left + 20, r.top + r.height / 2]; }"
        )
        # Beside the column, level with the same paragraph: body's own margin, which the
        # centred 720px column leaves on a 1200px viewport, and no element there carries
        # an id for an armed press to take.
        in_gap = [40, on_item[1]]
        assert page.evaluate(at_pointer, on_item) == "auto", (
            "an unarmed page already named a cursor, so the arm has nothing left to say"
        )

        page.mouse.move(*on_item)
        page.keyboard.down("Alt")
        expect(page.locator("[data-lf-aimed]")).to_have_id("p2")
        assert page.evaluate(at_pointer, on_item) == "pointer", (
            "the aim boxed the paragraph and the cursor declined to promise the press"
        )

        page.mouse.move(*in_gap)
        expect(page.locator("[data-lf-aimed]")).to_have_count(0)
        assert page.evaluate(at_pointer, in_gap) == "default", (
            "the aim had nothing to take and the hand promised a press anyway"
        )

        # Back on the item, so the arm coming off is read from the state that promises
        # most.
        page.mouse.move(*on_item)
        expect(page.locator("[data-lf-aimed]")).to_have_id("p2")
        page.keyboard.up("Alt")
        expect(page.locator("[data-lf-aimed]")).to_have_count(0)
        assert page.evaluate(at_pointer, on_item) == "auto", (
            "the key came up and the page went on offering the aim's press"
        )

    # What a press would take can change with no mouse event to say so. The scroll
    # listener decides the aim again, so scrolling under a held key must not leave the
    # outline on the item that had been under the pointer while a press takes the one now
    # there.
    with subtests.test(case="a scroll under a held aim moves the promise"):
        page.mouse.move(600, 300)
        page.keyboard.down("Alt")
        first = page.evaluate(AIMED)
        assert first, (
            "nothing promised under the parked pointer, so nothing is being aimed"
        )
        # Three whole paragraphs of scroll, measured off the page: the paragraphs are
        # identical, so the pointer's offset into the outlined one becomes the same offset
        # into the one three later, never the margin between two. The browser root is the
        # page's scroller, and scrollBy fires the same scroll events a wheel does.
        page.evaluate(
            """() => document.scrollingElement.scrollBy(0, 3 *
              (document.getElementById("p3").getBoundingClientRect().top -
               document.getElementById("p2").getBoundingClientRect().top))"""
        )
        page.wait_for_function(
            """(first) => {
          const promised = document.querySelector("[data-lf-aimed]")?.closest("[id]")?.id;
          const at = document.elementFromPoint(600, 300)?.closest("[id]:not(.lf-ui)");
          return Boolean(promised) && promised === at?.id && promised !== first;
        }""",
            arg=first,
        )
        page.keyboard.up("Alt")

    # What ⌥ arms is the page. An aim that reached into the chrome would take the panel
    # and the composer away from a user who happens to be holding the key, and there is
    # nothing there to aim at anyway, since an anchor names an element of the page. Last,
    # since it leaves the panel open.
    with subtests.test(case="the chrome keeps its presses"):
        on_me = page.locator(".lf-fp-on-user")
        on_me.hover()
        page.keyboard.down("Alt")
        on_me.click()
        page.keyboard.up("Alt")
        panel_settled(page, view="queue")
        expect(page.locator(".lf-composer")).to_be_hidden()


def test_a_key_still_reaches_its_control_after_an_aimed_press(browser, serve):
    """The aim holds its claim until the next press starts, and a key is not one.

    The option scope works its selection toggle by calling click(), so a control worked
    from the keyboard sends a click with no press behind it. Taken for the aim's own, it
    goes nowhere at all: the user presses Space on a pick mark and nothing is
    picked, on a page where the last thing they did with the mouse was aim."""
    page = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    composer = page.locator(".lf-composer")
    open_compact_comment(page)
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    page.locator("#opt-shim .lf-pick").focus()
    with sending(page, "the pick"):
        page.keyboard.press(" ")
    expect(page.locator("#approach > lf-option[chosen]")).to_have_count(1)
    assert [
        e["action"] for e in events_model.read_events(serve.page_dir) if "action" in e
    ] == ["choose"]


def test_the_aim_still_promises_while_a_composer_is_open(browser, serve):
    """An armed press with the box up moves it to a new target, so aim still says where.

    claimPress acts whether or not a composer stands open. Holding ⌥ over a second item
    raises its box beside the draft's own mark; two at once is the true state — where
    the draft stands, and where the next comment would land. The press carries the typed
    text onto the new anchor."""
    page = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    composer = page.locator(".lf-composer")
    open_compact_comment(page)
    write(composer.locator("leaf-text"), "carried words")

    card = page.locator("#card-notes")
    card.hover()
    page.keyboard.down("Alt")
    promised = [page.evaluate(AIMED), page.evaluate(DRAFT_MARK)]
    assert promised == ["card-notes", "t"], (
        f"holding ⌥ over a card with a draft open on the heading showed {promised} as "
        "[aim, draft], so the press that would move the draft is blind"
    )
    card.click()
    page.keyboard.up("Alt")
    # The second explicit comment gesture moves the open draft onto the card.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(composer.locator("leaf-text")).to_be_focused()
    expect(composer.locator("leaf-text")).to_have_js_property("value", "carried words")
    assert [page.evaluate(AIMED), page.evaluate(DRAFT_MARK)] == [
        None,
        "card-notes",
    ], "the press re-anchored the draft, so its new anchor alone should stand marked"
    round_trip(page)
    assert [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []


def test_a_reload_under_a_held_aim_rearms_on_the_first_move(browser, serve):
    """The arm survives what the keydown cannot.

    `aiming` is armed by an Alt keydown, and a page reloaded under a held key — the
    poll following a new version does exactly this — never hears one, while claimPress
    reads live modifier state: every press on the new page was claimed and none could
    be promised. Mouse events carry that same live state, so the first move re-derives
    the arm; this drives that move rather than a keydown the reload already ate."""
    page = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("t")
    page.reload()
    wait_until_ready(page)
    expect(page.locator("[data-lf-aimed]")).to_have_count(0)  # the latch is gone
    heading.hover()  # the first move under the still-held key
    expect(page.locator("[data-lf-aimed]")).to_have_id("t")
    page.keyboard.up("Alt")


def test_design_mode_comments_on_what_a_press_lands_on_and_nothing_else(browser, serve):
    """A press in design mode is a design comment, and that is all it does.

    The mode is primary while it stands, even over the ⌥ aim: a modified press on a
    widget names the widget rather than aiming or working it, so a pick mark can be
    pointed at without picking. The comment posts with `about: "design"`, which is how
    the agent tells "this control looks wrong" from a remark about the words — nothing
    about the anchor alone says which. Both halves are asserted: the log's event, and
    the page exactly as it was."""
    page = open_page(browser, serve(REPLAYED_PAGE))
    option = page.locator("#opt-shim")
    before = page.evaluate(PAGE_MARKUP)
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")

    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    expect(
        reference.locator('[role=option][data-lf-command="aim.comment"]')
    ).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")

    # The mode shows what is on the page rather than waiting for the pointer: a legend
    # box on every item, and on every item but a widget's parts its name — the group
    # is named, its options wear the hairline alone and are named under the pointer.
    def box_of(element_id):
        return page.locator(f'.lf-legend-box[data-lf-for="{element_id}"]')

    expect(box_of("t")).to_be_visible()
    assert set(
        page.eval_on_selector_all(
            ".lf-legend-box", "bs => bs.map(b => b.dataset.lfFor)"
        )
    ) == set(page.eval_on_selector_all("main [id]", "es => es.map(e => e.id)"))
    expect(box_of("approach").locator(".lf-legend-tag")).to_have_text(
        "lf-options · approach"
    )
    expect(box_of("t").locator(".lf-legend-tag")).to_have_text("heading · t")
    expect(box_of("opt-shim").locator(".lf-legend-tag")).to_have_count(0)
    page.wait_for_function(LEGEND_TRUE)
    # Hovering names the target — the tag and the id a fix is written against — and
    # draws the aim's own box on it, the promise about the next press.
    option.hover()
    expect(page.locator(".lf-inspect")).to_have_text("lf-option · opt-shim")
    expect(page.locator("[data-lf-aimed]")).to_have_id("opt-shim")
    option.click(modifiers=["Alt"])
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "design · lf-option · opt-shim"
    )
    # The press did nothing to the page: not a pick, not a focus, nothing in the markup
    # but the composer's own outline on the element it is about.
    expect(page.locator("#approach > lf-option[chosen]")).to_have_count(0)
    assert (
        page.evaluate(PAGE_MARKUP).replace(' class="lf-mark-el lf-pending"', "")
        == before
    )
    assert not page.evaluate(FOCUS_IN_PAGE)
    composer_input = page.locator(".lf-composer leaf-text")
    composer_input.click()
    expect(composer_input).to_be_focused()
    write(composer_input, "the ring reads too heavy")
    with sending(page, "the design comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    events = events_model.read_events(serve.page_dir)
    posted = [e for e in events if e["kind"] == "comment"]
    assert [(e["about"], e["anchor"]) for e in posted] == [
        ("design", {"section": "opt-shim"})
    ]
    assert [e for e in events if e["kind"] == "action"] == []
    # The retained thread names the target the same way the composer named the box. The
    # top-layer margin card stays retired while design mode stands, so the send lands
    # on the thread in the panel's thread view.
    panel = page.locator(PANEL_THREAD)
    expect(panel).to_be_visible()
    expect(page.locator(".lf-quote-label")).to_contain_text(
        "design · lf-option · opt-shim"
    )
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    # Escape from the thread is the panel's, which closes onto the page. The mode they
    # put on before the panel comes off last.
    page.locator(".lf-fp-close").click()
    expect(panel).to_have_count(0)
    page.locator("body").focus()
    expect(page.locator("body")).to_be_focused()
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
    expect(page.locator(".lf-inspect")).to_be_hidden()
    expect(page.locator(".lf-legend-box")).to_have_count(0)


# Each mode once and each route once: the route reaches the same picker whatever mode
# it stands in.
@pytest.mark.parametrize(
    ("mode", "route"),
    [
        (None, "keyboard"),
        ("l", "pointer"),
        ("w", "pointer"),
    ],
    ids=[
        "content-keyboard",
        "design-pointer",
        "draw",
    ],
)
def test_target_picker_selects_in_the_current_comment_mode(browser, serve, mode, route):
    """Target selection nests inside Design; Draw retains the page for ink."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Comment modes", '<h1>Modes</h1><p id="subject">Pick this passage.</p>'
            )
        ),
    )
    if mode:
        page.keyboard.press(mode)
    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint")
    if mode == "w":
        expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
        expect(hints).to_have_count(0)
        return
    expect(hints.first).to_be_visible()
    if mode == "l":
        expect(
            page.locator('.lf-legend-box[data-lf-for="subject"] .lf-legend-tag')
        ).to_be_hidden()
        page.keyboard.press("Escape")
        expect(hints).to_have_count(0)
        expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
        expect(
            page.locator('.lf-legend-box[data-lf-for="subject"] .lf-legend-tag')
        ).to_be_visible()
        page.keyboard.press("s")
        expect(hints.first).to_be_visible()
    if route == "keyboard":
        said = page.locator(".lf-live")
        for _ in range(10):
            previous = said.text_content()
            page.keyboard.press("Tab")
            expect(said).not_to_have_text(previous)
            expect(said).to_have_text(re.compile(r"^Hint .*Press Enter to choose\.$"))
            if "Pick this passage." in said.text_content():
                break
        else:
            pytest.fail("The passage was missing from the target map")
        page.keyboard.press("Enter")
    else:
        page.locator("#subject").click()
    expect(hints).to_have_count(0)
    if mode == "l":
        expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    write(page.locator(".lf-fab-input"), "Keep this passage aligned.")
    with sending(page, "the selected element comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert event["anchor"] == {"section": "subject"}
    assert event.get("about") == ("design" if mode == "l" else None)
    if mode == "l":
        page.keyboard.press("Escape")
        expect(page.locator(PANEL_THREAD)).to_have_count(0)
        expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
        page.keyboard.press("Escape")
        expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")


# Each route once, with each role taking at least one of them.
@pytest.mark.parametrize(
    ("role", "route"),
    [("slider", "direct"), ("button", "picker-pointer"), ("slider", "picker-keyboard")],
)
def test_design_mode_owns_every_platform_control_from_the_shared_boundary(
    browser, serve, route, role
):
    """Design mode captures controls from the runtime's full platform list.

    A slider nested in an ordinary section has no widget tag or native element name to
    put it on a smaller selector. Its ARIA role must still become the named design part.
    An unnamed disclosure is the fail-closed control: even without a durable comment
    target, its activation must not leak through the active mode.
    """
    control_markup = (
        '<span role="slider" tabindex="0" aria-label="Volume" '
        'aria-valuemin="0" aria-valuemax="100" aria-valuenow="50">50</span>'
        if role == "slider"
        else '<button aria-label="Volume">Adjust volume</button>'
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "design controls",
                '<h1>Controls</h1><section id="volume">' + control_markup + "</section>"
                "<details><summary>More controls</summary><p>Hidden</p></details>",
            )
        ),
    )
    page.keyboard.press("l")
    control = page.get_by_role(role, name="Volume")
    control.evaluate(
        "el => el.addEventListener('click', () => el.dataset.activated = 'yes')"
    )
    if route != "direct":
        page.keyboard.press("s")
        expect(page.locator(".lf-target-picker-hint").first).to_be_visible()
    control.hover()
    expect(page.locator(".lf-inspect")).to_have_text("Volume · section · volume")
    page.keyboard.down("Alt")
    expect(page.locator(".lf-inspect")).to_have_text("Volume · section · volume")
    page.keyboard.up("Alt")
    if route == "picker-keyboard":
        said = page.locator(".lf-live")
        for _ in range(10):
            previous = said.text_content()
            page.keyboard.press("Tab")
            expect(said).not_to_have_text(previous)
            expect(said).to_have_text(re.compile(r"^Hint .*Press Enter to choose\.$"))
            if "Volume ·" in said.text_content():
                break
        else:
            pytest.fail("The control part was missing from the Design target map")
        page.keyboard.press("Enter")
    else:
        control.click()
    expect(control).not_to_have_attribute("data-activated", "yes")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    expect(page.locator("#lf-composer-quote")).to_contain_text(
        "design · Volume · section · volume"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    disclosure = page.locator("main details")
    summary = disclosure.locator("summary")
    summary.click()
    assert not disclosure.evaluate("el => el.open"), (
        "target resolution failed open and activated the disclosure under Design mode"
    )
    expect(page.locator(".lf-composer")).to_be_hidden()
    summary.focus()
    page.keyboard.press("Enter")
    assert disclosure.evaluate("el => el.open"), (
        "Design mode swallowed the disclosure's keyboard activation"
    )


@pytest.mark.parametrize(
    ("generated", "route"), [(False, "keyboard"), (True, "pointer")]
)
def test_repeated_design_control_names_keep_context_without_inventing_identity(
    browser, serve, generated, route
):
    """Native words disambiguate controls; anonymous chrome keeps only its owner."""
    control = '<button aria-label="Delete row">Remove</button>' if not generated else ""
    rows = "".join(f"<p>{name} {control}</p>" for name in ["api", "web", "worker"])
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Repeated controls",
                    '<h1>Rows</h1><section id="rows"><h2>Release rows</h2>'
                    + rows
                    + "</section>",
                )
            )
        ),
    )
    if generated:
        page.evaluate("""async () => {
          const {offer} = await window.__lfWidgetApi();
          for (const row of document.querySelectorAll('#rows p')) {
            const button = offer('button', '', 'Remove');
            button.setAttribute('aria-label', 'Delete row');
            row.append(button);
          }
        }""")
    page.keyboard.press("l")
    page.keyboard.press("s")
    inventory = page.evaluate("""async () => {
      const {aimTargets, resolveAnchor} = await window.__lfCheckApi();
      return aimTargets({design: true}).filter(t => t.anchor.section === 'rows' && t.anchor.part).map(t => t.capture ? t.capture() : t).map(t => ({
        anchor: t.anchor, label: t.label, resolution: (() => { const resolved = resolveAnchor(t.anchor); return {exact: resolved?.exact, status: resolved?.status}; })()
      }));
    }""")
    assert len(inventory) == 3
    assert all(item["anchor"]["part"] == "Delete row" for item in inventory)
    assert all(
        item["resolution"]
        == {"exact": not generated, "status": "fallback" if generated else "exact"}
        for item in inventory
    )
    if generated:
        assert all("quote" not in item["anchor"] for item in inventory)
    else:
        assert (
            len({json.dumps(item["anchor"], sort_keys=True) for item in inventory}) == 3
        )
        assert all(item["anchor"]["quote"] == "Remove" for item in inventory)
        assert "after …" in inventory[1]["label"]
        assert "web" in inventory[1]["label"]
    if route == "keyboard":
        said = page.locator(".lf-live")
        for _ in range(10):
            previous = said.text_content()
            page.keyboard.press("Tab")
            expect(said).not_to_have_text(previous)
            expect(said).to_have_text(re.compile(r"^Hint .*Press Enter to choose\.$"))
            if (
                f": {inventory[1]['label']}. Press Enter to choose."
                in said.text_content()
            ):
                break
        else:
            pytest.fail("The middle control lost its spoken context")
        page.keyboard.press("Enter")
    else:
        page.get_by_role("button", name="Delete row").nth(1).click()
    write(page.locator(".lf-fab-input"), "Keep this row.")
    with sending(page, "the repeated-control comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert event["anchor"] == inventory[1]["anchor"]
    assert event["about"] == "design"
    if generated:
        card = open_panel_thread(page, event["id"])
        expect(card.locator(".lf-msg-text")).to_contain_text("Keep this row.")
        # Replacing the authored owner retires its generated controls as their producer
        # would. The same owner id now holds just one native matching control.
        revised = leaf_page(
            "Repeated controls",
            '<h1>Rows</h1><article id="rows"><h2>Release rows</h2><p>web <button aria-label="Delete row">Remove</button></p></article>',
        )
        stamp = stamp_page(serve.page_dir, revised, "Keep the remaining row")
        wait_for_revision(page, stamp["revision"])
        expect(
            page.locator("main #rows").get_by_role("button", name="Delete row")
        ).to_have_count(1)
        resolution = page.evaluate(
            """async anchor => {
          const {resolveAnchor} = await window.__lfCheckApi();
          const result = resolveAnchor(anchor);
          return {exact: result.exact, status: result.status, owner: result.element.id};
        }""",
            event["anchor"],
        )
        assert resolution == {"exact": False, "status": "fallback", "owner": "rows"}
        expect(card.locator(".lf-msg-text")).to_contain_text("Keep this row.")


# Each shape of control Design mode can name, in a section of its own on one page: what
# selects the controls of that shape, then for each the part its anchor names and the
# words it quotes, or the whole anchor where it names no part.
CONTROL_SHAPES = {
    # The neighbouring cell tells a repeated label apart. This section comes first, since
    # what its announcement says it follows runs back to the page's own first words.
    "table-row": (
        '<section id="table-row"><h2>Notifications</h2><table><tbody>'
        + "".join(
            f'<tr><td>{name}</td><td><label><input type="checkbox"> Notify me</label></td></tr>'
            for name in ("Primary", "Backup")
        )
        + "</tbody></table></section>",
        "#table-row input",
        [("Notify me", "Notify me")] * 2,
    ),
    # Inline emphasis stays in one passage of the label.
    "inline-label": (
        '<section id="inline-label">'
        + "".join(
            f'<p><label><input type="checkbox"> <b>Notify</b> me</label> about the {name} release.</p>'
            for name in ("Primary", "Backup")
        )
        + "</section>",
        "#inline-label input",
        [("Notify me", "Notify me")] * 2,
    ),
    # Visually hidden words can't be quoted.
    "clipped-label": (
        '<section id="clipped-label">'
        + "".join(
            f'<p>{name} <label><span style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap">Notify me</span><input type="checkbox"></label></p>'
            for name in ("Primary", "Backup")
        )
        + "</section>",
        "#clipped-label input",
        [("Notify me", None)] * 2,
    ),
    # A label around its control supplies the quote. A select's name takes in its option's
    # word too, though its quote doesn't.
    "label-before-control": (
        '<section id="label-before-control">'
        + "".join(
            f'<p>{name} <label>Notify me <input type="checkbox"></label></p>'
            for name in ("Primary", "Backup")
        )
        + "</section>",
        "#label-before-control input",
        [("Notify me", "Notify me")] * 2,
    ),
    "label-around-select": (
        '<section id="label-around-select">'
        + "".join(
            f"<p>{name} <label>Notify me <select><option>Enabled</option></select></label></p>"
            for name in ("Primary", "Backup")
        )
        + "</section>",
        "#label-around-select select",
        [("Notify me Enabled", "Notify me")] * 2,
    ),
    # Only words beyond the prose all three repeat tell these apart.
    "distant-context": (
        '<section id="distant-context">'
        + "".join(
            f'<article><h3>{name}</h3><p>Owned by the platform team and reviewed weekly.</p><button aria-label="Delete flag">Remove</button><p>Changes apply after the next deploy finishes.</p></article>'
            for name in ("checkout", "search", "export")
        )
        + "</section>",
        "#distant-context button",
        [("Delete flag", "Remove")] * 3,
    ),
    # A closed select's option words aren't on the screen.
    "hidden-options": (
        '<section id="hidden-options">'
        + "".join(
            f'<p>{name} <select aria-label="Region"><option>us-east</option><option>eu-west</option></select></p>'
            for name in ("Primary", "Backup")
        )
        + "</section>",
        "#hidden-options select",
        [("Region", None)] * 2,
    ),
    # A native label and its input are one control.
    "label-input": (
        '<section id="label-input"><h2>Options</h2><label><input type="radio" name="treatment" value="a">A</label><label><input type="radio" name="treatment" value="b">B</label></section>',
        "#label-input label",
        [("A", "A"), ("B", "B")],
    ),
    # A control's announcement reads the prose around it, and no neighbouring control's
    # words. The section has a heading of its own, since an unnamed section is named by
    # its words, the neighbour's included.
    "spoken": (
        '<section id="spoken"><h2>Flags</h2><p>Find settings <input aria-label="Search flags"> <button aria-label="Close dialog">×</button></p></section>',
        "#spoken input, #spoken button",
        [("Search flags", None), ("Close dialog", "×")],
    ),
    # The page's file doesn't hold a tab's generated summary, so the anchor names the tab
    # and quotes nothing.
    "queue": (
        '<lf-tabs id="queue" list="side"><lf-tab id="first" label="Primary" summary="pages"><p>Primary evidence.</p></lf-tab><lf-tab id="second" label="Backup" summary="pages"><p>Backup evidence.</p></lf-tab></lf-tabs>',
        "#queue [role=tab] .lf-tab-summary",
        [("Primary", None), ("Backup", None)],
    ),
    # An editor's value never names it, and an authored id does.
    "editable-regions": (
        '<section id="editable-regions">'
        '<div contenteditable="true" role="textbox" aria-label="First editor">First draft</div>'
        '<div contenteditable="true" role="textbox" aria-label="Backup editor">Backup draft</div>'
        '<div id="authored-editor" contenteditable="true" role="textbox">Authored draft</div></section>',
        "#editable-regions > div",
        [
            ("First editor", None),
            ("Backup editor", None),
            {"section": "authored-editor"},
        ],
    ),
    "focusable-regions": (
        '<section id="focusable-regions">'
        '<div tabindex="0" aria-label="Draft region">First draft</div>'
        '<div tabindex="0" aria-label="Draft region">Backup draft</div>'
        '<div id="authored-region" tabindex="0">Authored draft</div></section>',
        "#focusable-regions > div",
        [
            ("Draft region", "First draft"),
            ("Draft region", "Backup draft"),
            {"section": "authored-region"},
        ],
    ),
    # A region quotes its own words without its nested control's, and a list of options
    # has none of its own.
    "region-faces": (
        '<section id="region-faces">'
        '<div tabindex="0" aria-label="Scroller">Own prose <button>Run action</button> tail words</div>'
        '<div role="listbox" aria-label="Fruit"><div role="option">Apple</div><div role="option">Pear</div></div>'
        '</section><button id="icon" aria-label="Settings"></button>',
        "#region-faces > div",
        [("Scroller", "Own prose"), ("Fruit", None)],
    ),
    # A picture has a name and no words to quote. An unnamed one takes its owner's anchor,
    # and one inside a button takes the button's name.
    "pictures": (
        '<section id="pictures">'
        '<svg aria-label="Revenue chart" width="80" height="40"><rect width="80" height="40" fill="teal"/></svg>'
        '<figure aria-label="Cost chart"><svg width="80" height="40"><rect width="80" height="40" fill="tomato"/></svg></figure>'
        '<svg width="80" height="40"><rect width="80" height="40" fill="gold"/></svg>'
        '<button aria-label="Open chart"><svg width="80" height="40"><rect width="80" height="40" fill="green"/></svg></button>'
        '<div tabindex="0" aria-label="Chart region"><svg aria-label="Region chart" width="80" height="40"><rect width="80" height="40" fill="blue"/></svg></div>'
        '<img alt="Margin chart" width="80" height="40" src="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2280%22 height=%2240%22%3E%3Crect width=%2280%22 height=%2240%22 fill=%22teal%22/%3E%3C/svg%3E">'
        "</section>",
        "#pictures svg, #pictures img",
        [
            ("Revenue chart", None),
            ("Cost chart", None),
            {"section": "pictures"},
            ("Open chart", None),
            ("Region chart", None),
            ("Margin chart", None),
        ],
    ),
}
# What a press lands on for each shape with a browser default or a handler of its own to
# keep from, where on it, and the part its comment names.
CONTROL_PRESSES = {
    "a label's words": ("#label-input label >> nth=0", {"x": 30, "y": 10}, "A"),
    "a label around a select": (
        "#label-around-select label >> nth=1",
        None,
        "Notify me Enabled",
    ),
    "a select": ("#hidden-options select >> nth=1", None, "Region"),
    "a field": ("#spoken input", None, "Search flags"),
    "a tab's summary": (
        '#queue [role=tab][aria-controls="second"] .lf-tab-summary',
        None,
        "Backup",
    ),
    "a region": ("#focusable-regions > div >> nth=1", None, "Draft region"),
    "a picture": ("#pictures > figure svg", None, "Cost chart"),
}
# Each control a shape's selector names: the target a press on it reads, and that same
# control's entry in the inventory the picker offers, before and after its capture.
READ_CONTROL_SHAPES = """async (shapes) => {
  const {aimTargets, aimTargetAt, resolveAnchor} = await window.__lfCheckApi();
  const {anchorLabel} = await window.__lfWidgetApi();
  const inventory = aimTargets({design: true});
  const identity = (target) => target.controlElement ?? target.element;
  // A control with no target reads as null, for its own case to report.
  const read = (control) => {
    const target = aimTargetAt(control, {design: true});
    if (!target) return null;
    const resolved = resolveAnchor(target.anchor);
    const listed = inventory.find((offer) => identity(offer) === identity(target));
    const chosen = listed?.capture ? listed.capture() : listed;
    return {
      anchor: target.anchor,
      label: target.label,
      exact: resolved?.exact,
      status: resolved?.status,
      ordinary: anchorLabel(target.anchor),
      design: anchorLabel(target.anchor, "design"),
      listed: listed?.anchor ?? null,
      offers: inventory.filter(
        (offer) => offer.anchor.section === target.anchor.section
          && offer.anchor.part === target.anchor.part).length,
      chosen: chosen ? {anchor: chosen.anchor, label: chosen.label} : null,
    };
  };
  return Object.fromEntries(Object.entries(shapes).map(
    ([shape, selector]) => [shape, [...document.querySelectorAll(selector)].map(read)]));
}"""
# What a press on the page's controls could leave behind it.
CONTROLS_LEFT_ALONE = """() => ({
  checked: [...document.querySelectorAll("main input")].filter((box) => box.checked).length,
  activated: document.querySelectorAll("main [data-activated]").length,
  selected: document.querySelector('#queue [role=tab][aria-selected="true"]')
    ?.getAttribute("aria-controls"),
})"""


def _back_in_design_mode(page):
    """Undo whatever a press case left, passed or failed, so the next starts in the mode
    with nothing open and no effect already standing: a draft left up would move under
    its press, a picker would take it as a choice, and a radio a failed press checked
    could not show the next press checking it."""
    page.evaluate("""() => {
      for (const box of document.querySelectorAll("main input")) box.checked = false;
      for (const box of document.querySelectorAll("main [data-activated]"))
        delete box.dataset.activated;
      const first = document.querySelector('#queue [role=tab][aria-controls="first"]');
      if (first.getAttribute("aria-selected") !== "true") first.click();
    }""")
    if page.locator(".lf-composer").is_visible():
        page.keyboard.press("Escape")
    if page.locator(".lf-target-picker-hint").count():
        page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    page.evaluate(RELEASE_FOCUS)
    if page.locator("body[data-lf-design-mode]").count() == 0:
        page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")


def test_design_mode_reads_each_shape_of_control_into_the_anchor_its_routes_carry(
    browser, serve, subtests
):
    """What varies by shape is which target Design mode reads. One reader decides it
    (anchor-resolution.js, `designTargetAt`), and the press and the picker both go through
    it (`claimPress`, `chooseTarget`), so this reads each shape on one page, walks the
    picker's map to hear each announced as captured, and presses each shape with a default
    or a handler of its own, by each pointer route, up to the comment opening on it.

    The keyboard's choice never touches the control. The composer and the log carry the
    anchor unread, so what is sent differs only by whether it quotes words, and sending
    writes the log, so the tests that send keep their own pages:
    `test_a_unique_anonymous_control_captures_its_visible_face` sends a quote by the press
    and by the keyboard, and
    `test_repeated_design_control_names_keep_context_without_inventing_identity` a quote
    by the keyboard and a name alone by the picker's press, and
    `test_native_textarea_defaults_never_supply_design_passage_context` a name alone by
    the press."""
    markup = leaf_page(
        "Control shapes",
        "<h1>Settings</h1>" + "".join(row[0] for row in CONTROL_SHAPES.values()),
    )
    page = open_page(browser, serve(markup))
    # The picker's map holds what the window shows, so the window holds every shape.
    resized(page, 1400, 3000)
    page.locator("#focusable-regions > div").nth(1).evaluate(
        "el => el.addEventListener('click', () => { el.dataset.activated = 'yes'; })"
    )
    reads = page.evaluate(
        READ_CONTROL_SHAPES, {shape: row[1] for shape, row in CONTROL_SHAPES.items()}
    )
    passages = passages_model.page_passages(structure_model.SourceDocument(markup))

    for shape, (_, _, wants) in CONTROL_SHAPES.items():
        with subtests.test(shape=shape):
            got = reads[shape]
            assert len(got) == len(wants), got
            for target, want in zip(got, wants, strict=True):
                anchor = target["anchor"]
                # The inventory lists a control by name, its words read only once chosen,
                # and either route then reads the one coordinate.
                assert target["chosen"] == {
                    "anchor": anchor,
                    "label": target["label"],
                }, target
                if isinstance(want, dict):
                    assert anchor == want, target
                    continue
                part, quote = want
                assert target["listed"] == {"section": shape, "part": part}, target
                # One offer per control of that name, a native label's included.
                named = [w for w in wants if isinstance(w, tuple) and w[0] == part]
                assert target["offers"] == len(named), target
                if quote is None:
                    assert anchor == {"section": shape, "part": part}, target
                    assert (target["exact"], target["status"]) == (
                        False,
                        "fallback",
                    ), target
                else:
                    assert (anchor["section"], anchor["part"], anchor["quote"]) == (
                        shape,
                        part,
                        quote,
                    ), target
                    assert (target["exact"], target["status"]) == (True, "exact"), (
                        target
                    )
                    # What the browser calls exact, the page's file can read too.
                    assert (
                        anchor_capture_model.resolve_quote(passages, anchor) is not None
                    ), target
            quoted = [
                json.dumps(target["anchor"], sort_keys=True)
                for target in got
                if "quote" in target["anchor"]
            ]
            assert len(set(quoted)) == len(quoted), got

    with subtests.test(reading="what a repeated control is announced by"):
        said = reads["table-row"][0]["label"]
        assert "after …Settings Notifications Primary" in said, said
        assert "after …gs " not in said, said
        assert len(reads["distant-context"][1]["anchor"]["prefix"]) > 24, reads

    with subtests.test(reading="a control's name is its own"):
        field, button = reads["spoken"]
        assert "×" not in field["label"], field
        assert "Find settings" in field["label"], field
        assert "Search flags" in field["ordinary"], field
        assert "Search flags" in field["design"], field
        assert "Close dialog" in button["ordinary"], button

    with subtests.test(reading="a label and its input are one control"):
        assert reads["label-input"][0]["label"].startswith("A ·"), reads["label-input"]
        by_input = page.evaluate("""async () => {
          const {aimTargetAt} = await window.__lfCheckApi();
          return aimTargetAt(document.querySelector('#label-input input'),
                             {design: true}).anchor;
        }""")
        assert by_input == reads["label-input"][0]["anchor"], by_input

    with subtests.test(reading="generated words stay out of the anchor"):
        anchor = reads["queue"][1]["anchor"]
        assert (
            anchor_capture_model.resolve_quote(
                passages, {**anchor, "quote": "Backup pages"}
            )
            is None
        )

    with subtests.test(reading="a range holding no words captures its element"):
        captured = page.evaluate("""async () => {
          const {anchorForRange} = await window.__lfCheckApi();
          const range = document.createRange();
          range.selectNodeContents(document.querySelector('#icon'));
          return anchorForRange(range);
        }""")
        assert captured == {"section": "icon"}

    _back_in_design_mode(page)
    hints = page.locator(".lf-target-picker-hint")

    with subtests.test(route="the picker's walk"):
        page.keyboard.press("s")
        chips = page.locator(".lf-target-picker-hint[data-lf-hint-code]")
        expect(chips.first).to_be_visible()
        live = page.locator(".lf-live")
        heard = []
        for _ in range(chips.count()):
            previous = live.text_content()
            page.keyboard.press("Tab")
            expect(live).not_to_have_text(previous)
            expect(live).to_have_text(re.compile(r"^Hint .*Press Enter to choose\.$"))
            heard.append(live.text_content())
        missing = [
            target["label"]
            for got in reads.values()
            for target in got
            if "part" in target["anchor"]
            and not any(
                f": {target['label']}. Press Enter to choose." in said for said in heard
            )
        ]
        assert not missing, (missing, heard)

    field = page.locator(".lf-fab-input")
    for route in ("press", "picker"):
        for case, (selector, position, part) in CONTROL_PRESSES.items():
            with subtests.test(route=route, case=case):
                _back_in_design_mode(page)
                before = page.evaluate(CONTROLS_LEFT_ALONE)
                if route == "picker":
                    page.keyboard.press("s")
                    expect(hints.first).to_be_visible()
                page.locator(selector).click(position=position)
                expect(field).to_be_focused()
                expect(field).to_be_in_viewport()
                expect(field).to_have_attribute(
                    "aria-label", re.compile(f"design · {re.escape(part)}")
                )
                expect(page.locator("#lf-composer-quote")).to_contain_text(
                    f"design · {part} ·"
                )
                expect(hints).to_have_count(0)
                assert page.evaluate(CONTROLS_LEFT_ALONE) == before

    # Out of the mode, a press is the page's again, and a value is its editor's. These
    # are the effects the presses above kept from happening, so they prove those presses
    # landed where these do.
    with subtests.test(route="out of the mode"):
        _back_in_design_mode(page)
        page.keyboard.press("Escape")
        expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
        selector, position, _ = CONTROL_PRESSES["a label's words"]
        page.locator(selector).click(position=position)
        expect(page.locator("#label-input input").first).to_be_checked()
        region = page.locator("#focusable-regions > div").nth(1)
        region.click(position={"x": 12, "y": 8})
        expect(region).to_be_focused()
        expect(region).to_have_attribute("data-activated", "yes")
        editor = page.locator("#editable-regions > div").nth(1)
        editor.click(position={"x": 12, "y": 8})
        expect(editor).to_be_focused()
        editor.press("End")
        editor.press_sequentially(" edited")
        expect(editor).to_have_text("Backup draft edited")
        expect(field).to_be_hidden()


def test_design_mode_leaves_the_chrome_working(browser, serve):
    """Design mode comments on what the agent made; Leaf's own chrome works as it does
    outside the mode, as it does for the target picker.

    A remark on the panel has no reader who can act on it, and a mode that took the
    chrome took the way out of the view its own send opened. The active mode's ✕ stands
    at the panel's row's end. The Threads key still
    opens the panel's Threads, where nothing under the pointer promises a comment, and
    its close closes it."""
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    resized(page, 1280, 800)

    def comments():
        return [
            e
            for e in events_model.read_events(serve.page_dir)
            if e["kind"] == "comment"
        ]

    seeded = comments()
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    # The control: the same press on the page is a design comment.
    page.locator("#t").click()
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    exit_mode = field_press(page).filter(has_text="Close")
    exit_mode.hover()
    expect(page.locator(".lf-inspect")).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel = page.locator(panel_view("threads"))
    panel_settled(page, view="threads")
    expect(panel).to_be_visible()
    panel.hover()
    expect(page.locator(".lf-inspect")).to_be_hidden()
    expect(composer).to_be_hidden()

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    assert comments() == seeded, "a press on the chrome posted a comment"
    exit_mode.click()
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode")
    open_threads(page)
    expect(panel).to_be_visible()


def test_design_mode_leaves_leaves_surfaces_working_inside_a_widget(browser, serve):
    """Leaf's own surfaces stay Leaf's where a widget seats them.

    A diff seats a thread beside its line, inside page content, where the page's presses
    are the mode's; so does the response bar it seats in its own outlet. The thread's
    reply box still takes the caret and sends a reply. It stands in the diff's shadow
    tree, so the press is read where it lands rather than at the host it is retargeted
    to."""
    url = serve(
        leaf_page(
            "diff in design mode",
            '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch">'
            "</lf-diff>",
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-return "old"
+return "new"
""",
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this check beside the changed line.",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    thread = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root["id"]}"]')
    reply = thread.locator("leaf-text")
    expect(reply).to_be_visible()
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")

    # The control: a press on the diff's own file control is the mode's.
    page.locator("#patch .lf-diff-file-comment").click()
    expect(page.locator("#lf-composer-quote")).to_have_text(re.compile(r"^design · "))
    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()

    reply.click()
    expect(reply).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_hidden()
    write(reply, "Covered now.")
    with sending(page, "the reply from the seated thread"):
        page.keyboard.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["parent"], sent["text"]) == (
        "reply",
        root["id"],
        "Covered now.",
    ), sent


def test_design_mode_settles_on_a_page_with_marked_elements(browser, serve):
    """The legend follows the page's markup, not the runtime's own paint on it.

    A mark rewrites its element's classes on every repaint, and a legend that heard those
    writes as the page moving started the repaint that wrote them again, so a page with a
    reaction or a comment on an element never stopped rendering while the mode stood."""
    url = serve(
        leaf_page(
            "marked elements",
            '<h1 id="t">Review</h1><p id="reacted">Reacted to.</p>'
            '<p id="commented">Commented on.</p>',
        )
    )
    for anchor, extra in (
        ("reacted", {"token": "keep"}),
        ("commented", {"text": "Why?"}),
    ):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": anchor},
                **extra,
            },
        )
    page = open_page(browser, url)
    expect(
        page.locator(
            '[data-lf-margin-for="reacted"] [data-lf-margin-entry-owner="reactions"][data-lf-behavior="disclosure"]'
        )
    ).to_have_count(1)
    expect(page.locator("#commented.lf-mark-el")).to_have_count(1)
    page.keyboard.press("l")
    expect(page.locator('.lf-legend-box[data-lf-for="reacted"]')).to_be_visible()
    rendered(page)


def test_design_mode_leaves_prose_to_the_selection(browser, serve):
    """Words are still the way to point at words: a drag on prose selects, and the
    comment it raises is about design; a plain click on prose comments on the block.

    The mode takes presses on widgets, controls and the chrome at the press, ahead of the
    page. Prose it leaves to the browser, or "this heading is too small" would have no
    way to quote the heading."""
    page = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("l")
    heading = page.locator("#t")
    box = heading.bounding_box()
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 2, box["y"] + box["height"] / 2),
    )
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "design · heading · t · “Rollout”"
    )
    page.keyboard.press("Escape")  # the composer, draft kept; the mode still stands
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    heading.click(position={"x": 4, "y": 4})
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text("design · heading · t")


def test_the_legend_follows_the_page_it_is_a_reading_of(browser, serve):
    """A legend box kept from a previous reading is a claim about a page that has moved.

    Three of the doors that move it: the page scrolling (items come on screen with no
    box yet, and the boxes are drawn in document space), the panel opening (the column
    re-centred, every block reflowed, and no scroll or replay said so — each obligation's own
    resize does), and the name under the pointer, which is drawn beside the box in the
    same space: it sat in viewport space once, with the scroll added on top, and stood a
    screen below its box on any page scrolled at all. The aim's name is one more of
    the chrome's promises over the same page, so the reflow doors repaint it too
    (pageShifted): it once kept its old coordinates through the panel's column motion,
    floating half a panel to the right of the element it named."""
    page = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("l")
    page.wait_for_function(LEGEND_TRUE)
    page.evaluate("() => { document.scrollingElement.scrollTop = 1200; }")
    p = page.locator("#p20")
    expect(p).to_be_in_viewport()
    expect(page.locator('.lf-legend-box[data-lf-for="p20"]')).to_be_visible()
    page.wait_for_function(LEGEND_TRUE)
    # The name floats where the box's tag stood, over the item's corner — on a scrolled
    # page as on a fresh one.
    p.hover()
    expect(page.locator(".lf-inspect")).to_have_text("paragraph · p20")
    expect(page.locator("[data-lf-aimed]")).to_have_id("p20")
    _label_stands_on_the_aim(page, p)
    # Threads opens over the page. Opened by key.
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    panel_settled(page, view="threads")
    page.wait_for_function(LEGEND_TRUE)
    # The legend's repaint above consumed the reflow's edge, and the aim was refreshed
    # in the same pageShifted, so one plain read is the settled answer: the pointer
    # still rests in p20, and the name stands where p20 stands now.
    expect(page.locator("[data-lf-aimed]")).to_have_id("p20")
    _label_stands_on_the_aim(page, p)


def _label_stands_on_the_aim(page, target):
    """The design name stands on the aim's top-left corner, touching the outer edge of
    the outline `target` draws it as, so this still checks attachment when its gap
    changes."""
    ring = target.evaluate(MARK)
    name = page.locator(".lf-inspect").bounding_box()
    assert abs(name["y"] + name["height"] - ring["ring"]["top"]) < 1, (name, ring)
    assert abs(name["x"] - ring["box"]["left"]) < 4, (name, ring)


def test_two_names_at_one_corner_step_apart(browser, serve):
    """A block whose top-left corner is also its container's — the paragraph's margin
    collapses out of the section, exactly the shape a suggestion and the block it wraps
    make — wrote both tags onto one spot, and the longer peeked out past the shorter at
    both ends as fragments of a word nobody wrote. The later tag steps away by tag
    heights until it stands clear."""
    page = open_page(browser, serve(CORNER_PAGE))
    page.keyboard.press("l")
    expect(
        page.locator('.lf-legend-box[data-lf-for="wrap"] .lf-legend-tag')
    ).to_be_visible()
    expect(
        page.locator('.lf-legend-box[data-lf-for="inner"] .lf-legend-tag')
    ).to_be_visible()
    clash = page.evaluate(
        """() => {
      const rs = [...document.querySelectorAll('.lf-legend-tag')]
        .map(t => t.getBoundingClientRect()).filter(r => r.width);
      for (let i = 0; i < rs.length; i++)
        for (let j = i + 1; j < rs.length; j++) {
          const a = rs[i], b = rs[j];
          if (a.left < b.right - 1 && b.left < a.right - 1 &&
              a.top < b.bottom - 1 && b.top < a.bottom - 1)
            return [a, b].map(r => [r.left, r.top, r.width, r.height]);
        }
      return null;
    }"""
    )
    assert clash is None, clash


def test_a_picture_is_one_addressable_element_however_many_ids_its_renderer_coined(
    browser, serve
):
    """A generated SVG node still names the authored widget when no parts are declared.

    The registry's x-visual contract makes the drawing one item rather than exposing
    renderer internals, so both the aim and the legend stop at the widget.
    """
    page = open_page(browser, serve(PICTURE_PAGE))
    node = page.locator("#flow svg g.pele-node[data-id]").first
    expect(node).to_be_visible()
    node.hover()
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("flow")
    page.keyboard.up("Alt")
    page.keyboard.press("l")
    assert set(
        page.eval_on_selector_all(
            ".lf-legend-box", "bs => bs.map(b => b.dataset.lfFor)"
        )
    ) == {"t", "p", "flow", "tree"}
    node.hover()
    expect(page.locator(".lf-inspect")).to_have_text("lf-diagram · flow")


def test_an_authored_drawing_offers_each_named_group_to_a_comment(browser, serve):
    """An id on a group inside a page's own inline SVG makes that part a target.

    Only a registered visual keeps the ids inside it to itself; a figure the author drew
    is ordinary markup, so a named group takes the aim and the comment, and a shape
    without an id still reaches the figure around it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "drawing",
                """
<h1 id="t">Drawing</h1>
<figure id="fig"><svg viewBox="0 0 240 60" width="240" height="60" role="img"
aria-label="A drawer beside a page"><g id="fig-drawer"><rect x="2" y="2" width="100"
height="56" fill="#ddd"></rect><text x="52" y="34" text-anchor="middle">Drawer</text></g>
<rect x="130" y="2" width="100" height="56" fill="#ddd"></rect></svg></figure>
""",
            )
        ),
    )
    drawer = page.locator("#fig-drawer rect")
    corner = {"x": 8, "y": 8}
    drawer.hover(position=corner)
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("fig-drawer")
    page.keyboard.up("Alt")
    page.locator("#fig svg > rect").hover()
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("fig")
    page.keyboard.up("Alt")

    drawer.click(modifiers=["Alt"], position=corner)
    open_compact_comment(page, "wider")
    with sending(page, "the comment on the drawer"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["anchor"] == {"section": "fig-drawer"}


def test_a_generic_package_gets_nested_hits_and_can_narrow_a_paint_surface(
    browser, serve
):
    """Core derives hit lookup from one package inventory.

    The inner part wins even though the containing part appears first. The outer part's
    explicit surface draws its aim, excluding its decorative line, while the inner part
    draws its own along every shape it contains, its diamond's sides included.
    """
    page = open_page(
        browser,
        serve(
            GENERIC_VISUAL_PAGE,
            layer_registry=GENERIC_VISUAL_LAYER,
            layer_widgets=GENERIC_VISUAL_WIDGETS,
        ),
    )

    page.locator("#outer-surface").hover(position={"x": 20, "y": 20})
    page.keyboard.down("Alt")
    # The outer part's surface draws its aim, leaving out its decorative line.
    expect(page.locator("[data-lf-aimed]")).to_have_id("outer-surface")
    accent = token_colour(page, "--accent")
    assert_drawn_in(page.locator("#outer-surface"), accent, 2)
    assert (
        page.locator("#outer-decoration").evaluate(
            "line => getComputedStyle(line).stroke"
        )
        != accent
    )
    page.keyboard.up("Alt")

    page.locator("#inner path").hover()
    page.keyboard.down("Alt")
    # The inner part, with no surface of its own, draws it along all it holds.
    expect(page.locator("[data-lf-aimed]")).to_have_id("inner")
    assert_drawn_in(page.locator("#inner"), accent, 2)
    page.keyboard.up("Alt")


def test_a_part_drawn_in_another_state_stands_on_its_visual_until_travel_reveals_it(
    browser, serve
):
    """A thread on a part the visual is not drawing now stays attached to the whole
    visual, and travelling to it asks the visual to draw the part and lands there."""
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=STAGED_VISUAL_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "inner-comment",
            "author": "user",
            "revision": 1,
            "text": "Why does this branch?",
            "anchor": {"section": "visual", "visual": "inner"},
        },
    )
    page = open_page(browser, url)
    inner = page.locator("#inner")
    expect(inner).to_be_hidden()
    resized(page, 1800, 900)
    page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    expect(inner).to_be_visible()
    expect(inner).to_have_attribute("data-lf-mark", re.compile(r"\bhere\b"))
    expect(page.locator("#visual")).not_to_have_attribute(
        "data-lf-mark", re.compile(".*")
    )
    assert_drawn_in(inner, token_colour(page, "--mark-contour-ink"), 1.5)


def test_a_prefixed_visual_part_is_marked_and_aimed_like_an_authored_one(
    browser, serve
):
    """A part admitted by its widget's prefixes, with nothing authored on the element,
    replays a stored comment onto its own shape and takes a new one from a click."""
    url = serve(
        PREFIXED_VISUAL_PAGE,
        layer_registry=prefixed_visual_layer("out", "inn", "htm"),
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "inner-comment",
            "author": "user",
            "revision": 1,
            "text": "Why does this branch?",
            "anchor": {"section": "visual", "visual": "inner"},
        },
    )
    page = open_page(browser, url)
    page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    expect(page.locator("#inner")).to_have_class(re.compile(r"\blf-projected-mark\b"))
    expect(page.locator("#outer")).not_to_have_class(
        re.compile(r"\blf-projected-mark\b")
    )

    page.keyboard.press("Escape")
    page.locator("#html-surface").click(modifiers=["Alt"])
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator('[data-lf-mark~="pending"]')).to_have_id("html-surface")
    expect(page.locator("#html")).to_have_class(re.compile(r"\blf-projected-mark\b"))


def test_a_visual_surface_narrows_paint_without_narrowing_semantic_interaction(
    browser, serve
):
    """Decoration omitted from a contour still belongs to its semantic part.

    The posted comment opens from the line inside the registered element, while the
    package-selected rectangle alone draws the contour its open thread raises. A second
    draft on the same part wears the pending contour, since the posted comment draws
    none at rest.
    """
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "outer-comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the boundary visible.",
            "anchor": {"section": "visual", "visual": "outer"},
        },
    )
    page = open_page(browser, url)
    outer = page.locator("#outer")
    decoration = page.locator("#outer-decoration")
    surface = page.locator("#outer-surface")
    expect(page.locator("[data-lf-mark]")).to_have_count(0)

    def midpoint(line):
        return line.evaluate(
            """line => {
          const matrix = line.getScreenCTM();
          const point = new DOMPoint(
            (line.x1.baseVal.value + line.x2.baseVal.value) / 2,
            (line.y1.baseVal.value + line.y2.baseVal.value) / 2,
          ).matrixTransform(matrix);
          return {x: point.x, y: point.y};
        }"""
        )

    point = midpoint(decoration)
    page.mouse.move(point["x"], point["y"])
    page.wait_for_function(
        "({x, y}) => getComputedStyle(document.elementFromPoint(x, y)).cursor"
        " === 'pointer'",
        arg=point,
    )
    page.mouse.click(point["x"], point["y"])
    expect(
        page.locator(
            '.lf-margin-preview .lf-page-thread[data-lf-thread="outer-comment"]'
        )
    ).to_be_visible()
    expect(outer).to_have_class(re.compile(r"\blf-projected-mark\b"))
    expect(page.locator("[data-lf-mark]")).to_have_id("outer-surface")
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile("."))
    expect(page.locator(".lf-composer")).to_be_hidden()

    point = midpoint(decoration)
    page.keyboard.down("Alt")
    page.mouse.move(point["x"], point["y"])
    page.mouse.click(point["x"], point["y"])
    page.keyboard.up("Alt")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(surface).to_have_attribute("data-lf-mark", re.compile(r"\bpending\b"))


def test_a_non_geometry_visual_surface_uses_one_box_for_aim_and_mark(browser, serve):
    """A part's HTML surface draws its comment's mark and the aim, as one box; the part
    it stands for, which holds a decoration too, draws neither."""
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "html-comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the small surface.",
            "anchor": {"section": "visual", "visual": "html"},
        },
    )
    page = open_page(browser, url)
    semantic = page.locator("#html")
    surface = page.locator("#html-surface")

    surface.click()
    expect(semantic).to_have_class(re.compile(r"\blf-projected-mark\b"))
    expect(page.locator("[data-lf-mark]")).to_have_id("html-surface")
    marked = surface.evaluate(MARK)
    assert marked and marked["style"] == "solid", marked

    surface.hover()
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("html-surface")
    aimed = surface.evaluate(MARK)
    assert aimed["ring"] == marked["ring"], (aimed, marked)
    page.keyboard.up("Alt")


def test_a_shadow_visual_surface_is_clipped_by_its_host(browser, serve):
    """A part in a widget's shadow tree draws its comment's mark and the aim itself, so
    the host that clips the part clips its marks as it does any of its content."""
    url = serve(
        SHADOW_VISUAL_PAGE,
        layer_registry=SHADOW_VISUAL_LAYER,
        layer_widgets=SHADOW_VISUAL_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "shadow-comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the clipped edge.",
            "anchor": {"section": "shadow-visual", "visual": "wide"},
        },
    )
    page = open_page(browser, url)
    host = page.locator("#shadow-visual")
    surface = host.locator("#wide-surface")

    surface.click(position={"x": 20, "y": 20})
    expect(surface).to_have_attribute("data-lf-mark", re.compile("."))
    assert_drawn_in(surface, token_colour(page, "--mark-contour-ink"), 1.5)
    assert host.evaluate("host => getComputedStyle(host).overflowX") == "hidden"
    assert surface.bounding_box()["width"] > host.bounding_box()["width"] + 10

    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("wide-surface")
    assert_drawn_in(surface, token_colour(page, "--mark-contour-ink"), 1.5)
    page.keyboard.up("Alt")


def test_a_rounded_diagram_part_aim_follows_its_rounded_edge(browser, serve):
    """A diagram node's aim is drawn along the node's own edge, round its rounded ends,
    as the stroke of the shape it draws, which takes the place of the node's border
    while it shows: an outline round the node's box stood a square frame off its
    rounded ends. The node's words keep their own paint."""
    rounded_page = PART_DIAGRAM_PAGE.replace(
        "S[Start request]", "S([Start request])", 1
    )
    page = open_page(browser, serve(rounded_page))
    rounded = page.locator('#flow g[data-id="S"]')
    border = rounded.evaluate(DRAWN_MARK)["strokes"]
    rounded.hover()
    page.keyboard.down("Alt")
    aimed = page.locator("[data-lf-aimed]")
    expect(aimed).to_have_count(1)
    assert_drawn_in(aimed, token_colour(page, "--accent"), 2)
    assert (
        rounded.locator("text").first.evaluate("text => getComputedStyle(text).stroke")
        == "none"
    )
    page.keyboard.up("Alt")
    expect(aimed).to_have_count(0)
    assert rounded.evaluate(DRAWN_MARK)["strokes"] == border


def test_a_declared_flowchart_node_keeps_its_comment_across_renderings(browser, serve):
    """The authored node id, rather than its generated SVG id, is the anchor.

    A named node outlines only its current SVG group, while the diagram holds the
    accessible note and the panel place. A source revision rebuilds the SVG and the
    stable token resolves to the new box.
    """
    page = open_page(browser, live_url(serve(PART_DIAGRAM_PAGE)))
    diagram = page.locator("#flow")

    start = diagram.locator('g[data-id="S"]')
    start.click(modifiers=["Alt"])
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    write(page.locator(".lf-composer leaf-text"), "name the retry path here")
    with sending(page, "the comment on the node"):
        page.keyboard.press("ControlOrMeta+Enter")

    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in posted] == [
        {"section": "flow", "visual": "node:S"}
    ]
    open_panel_thread(page, posted[0]["id"])
    expect(page.locator(".lf-quote-label")).to_have_text("§ diagram · Start request")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    expect_comment_notes(page, "#flow", 1)
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b"))

    stamp_page(serve.page_dir, PART_DIAGRAM_V2, "reordered")
    wait_for_revision(page, 2)
    expect(diagram.locator('g[data-id="S"]')).to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    expect_comment_notes(page, "#flow", 1)


def test_design_mode_treats_a_renderer_node_as_part_of_its_widget(browser, serve):
    """A renderer node is implementation in design mode, not an authored control."""
    page = open_page(browser, serve(PART_DIAGRAM_PAGE))
    diagram = page.locator("#flow")
    handler = diagram.locator('g[data-id="H"]')
    page.keyboard.press("l")
    handler.click()

    expect(page.locator("#lf-composer-quote")).to_have_text(
        "design · lf-diagram · flow"
    )
    write(
        page.locator(".lf-composer leaf-text"),
        "the diagram needs a stronger affordance",
    )
    with sending(page, "the comment on the diagram"):
        page.keyboard.press("ControlOrMeta+Enter")
    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["about"], event["anchor"]) for event in posted] == [
        ("design", {"section": "flow"})
    ]
    expect(diagram).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(handler).not_to_have_class(re.compile(r"\blf-mark-el\b"))


def test_a_sequence_actor_is_an_addressable_visual_part(browser, serve):
    """The renderer carries a participant's authored id into its drawn actor box."""
    sequence = leaf_page(
        "sequence diagram parts",
        """
<h1 id="t">Exchange</h1>
<lf-diagram id="exchange" parts="all"><pre>
sequenceDiagram
  participant A as User
  participant B as Server
  A->>B: Request
</pre></lf-diagram>
""",
    )
    page = open_page(browser, serve(sequence))

    actor = page.locator('#exchange g[data-id="A"]:not(.pele-actor-footer)')
    actor.click(modifiers=["Alt"])
    open_compact_comment(page)
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · User")
    expect(actor).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))


def test_target_brackets_and_focus_share_the_visible_boundary(browser, serve, subtests):
    """Leaving Comment changes the mark, not which box draws it: the target draws the
    aim, a draft's mark and focus as its own outline, on the region's perimeter at the
    gap the location ring takes, the gestures as brackets and focus whole.

    A table and a card with authored corners draw them alike. A mark stands over an
    outline the page gave the target while it lasts. Focus alone is the box's focus
    ring rather than a mark, so an outline the page gave the box outranks it, and the
    page's own stands again once only focus is marked.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Target boundaries",
                """
<h1>Target boundaries</h1>
<table id="square"><tr><th>West</th><th>East</th></tr>
  <tr><td>16 jobs</td><td>8 jobs</td></tr></table>
<div id="rounded" class="authored-contour">Fallback procedure</div>
""",
                head="""<style>
  #square { display:table; border-collapse:collapse; width:400px; }
  #square :is(th,td) { border:1px solid; }
  #rounded { border:1px solid; border-radius:12px; margin:12px; padding:12px; }
  .authored-contour { outline:1px dashed var(--ink-2); }
  </style>""",
            )
        ),
    )
    resized(page, 1100, 900)
    region = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--focus-region-gap'))"
    )

    def boundary(node, brackets):
        mark = node.evaluate(MARK)
        assert mark and mark["style"] == "solid", mark
        assert (mark["width"], mark["offset"], mark["brackets"]) == (
            2,
            region,
            brackets,
        ), mark

    for target in ("square", "rounded"):
        with subtests.test(target=target):
            node = page.locator(f"#{target}")
            node.hover(position={"x": 10, "y": 10})
            page.keyboard.down("Alt")
            expect(page.locator("[data-lf-aimed]")).to_have_id(target)
            boundary(node, brackets=True)
            page.mouse.down()
            page.mouse.up()
            page.keyboard.up("Alt")
            open_compact_comment(page)
            expect(node).to_have_attribute("data-lf-mark", re.compile(r"\bpending\b"))
            boundary(node, brackets=True)
            page.keyboard.press("Escape")
            expect(node).to_be_focused()
            expect(node).to_have_attribute("data-lf-mark", re.compile(r"\bfocus\b"))
            if target == "rounded":
                expect(node).to_have_css("outline-style", "dashed")
            else:
                boundary(node, brackets=False)
            page.evaluate(RELEASE_FOCUS)
            expect(node).not_to_have_attribute("data-lf-mark", re.compile(".*"))
            if target == "rounded":
                expect(node).to_have_css("outline-style", "dashed")


def test_the_aim_stands_where_its_targets_own_marks_do(browser, serve, subtests):
    """A field's ring replaces its border, so it stands on the field's edge, and the aim
    the field draws stands there too. It stood a control's gap outside, because the
    field's edge, 0, read as no place stated: 0 is also where the outline of a box that
    states nothing stands.

    A joined choice clips its cells, so a cell leaves no room for a mark outside it and
    states its marks one band inside its edge (options.css). The aim and the comment's
    mark both stand there: the aim stood outside, across the frame and the next cell,
    while the comment's stood inside, so going from one to the other moved the frame 7px."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Cramped targets",
                """<h1 id="h">Cramped targets</h1>
<p><label for="name">Name</label> <input id="name" class="lf-field" type="text" value="Ada"></p>
<lf-options id="ship" choose>
  <lf-option id="ship-monday"><strong>Ship Monday</strong> soon</lf-option>
  <lf-option id="ship-thursday"><strong>Ship Thursday</strong> later</lf-option>
</lf-options>""",
            )
        ),
    )

    with subtests.test(target="field"):
        field = page.locator("#name")
        field.hover(position={"x": 8, "y": 6})
        page.keyboard.down("Alt")
        expect(page.locator("[data-lf-aimed]")).to_have_id("name")
        aim = field.evaluate(MARK)
        assert aim and aim["style"] == "solid" and aim["offset"] == 0, aim
        page.keyboard.up("Alt")

    with subtests.test(target="joined cell"):
        cell = page.locator("#ship-thursday")
        cell.hover(position={"x": 300, "y": 10})
        page.keyboard.down("Alt")
        expect(page.locator("[data-lf-aimed]")).to_have_id("ship-thursday")
        aimed = cell.evaluate(MARK)
        assert aimed["offset"] + aimed["width"] <= 0, aimed
        page.mouse.down()
        page.mouse.up()
        page.keyboard.up("Alt")
        open_compact_comment(page)
        expect(cell).to_have_attribute("data-lf-mark", re.compile(r"\bpending\b"))
        pending = cell.evaluate(MARK)
        assert pending["ring"] == aimed["ring"], (aimed, pending)


# A box drawing the target painter's focus state as its ring (visual-mark-paint.js).
FOCUS_MARK = '[data-lf-mark~="focus"]'


def test_focus_projection_follows_modality_and_leaves_private_controls_their_ring(
    browser, serve, subtests
):
    """A keyboard cue can begin without focus moving, and needs no authored id.

    Private shadow controls and controls whose surrounding face owns their ring
    retain that component paint rather than acquiring a second projected ring.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Focus paint ownership",
                "<h1>Focus paint ownership</h1><button>Unnamed control</button>"
                '<button id="named">Named control</button><span id="component"></span>'
                '<label class="lf-choice"><input id="pick" type="checkbox">Keep this choice</label>'
                '<section><lf-tabs id="views">'
                '<lf-tab id="view-a" label="First">First panel</lf-tab>'
                '<lf-tab id="view-b" label="Second">Second panel</lf-tab>'
                '</lf-tabs></section><lf-pane id="pane" label="Findings">'
                '<div id="pane-body" style="height:160px;overflow:auto">'
                '<p style="height:400px">The pane scrolls.</p></div></lf-pane>',
            )
        ),
    )
    page.locator("#component").evaluate(
        """host => {
          host.attachShadow({mode:'open'}).innerHTML = `<style>
            button:focus-visible { outline:var(--focus-ring); outline-offset:3px; }
          </style><button id="private">Private control</button>`;
        }"""
    )
    for name in ("Unnamed control", "Named control"):
        with subtests.test(control=name):
            control = page.get_by_role("button", name=name, exact=True)
            control.click()
            expect(control).to_be_focused()
            rendered(page)
            assert not control.evaluate("node => node.matches(':focus-visible')")
            expect(page.locator(FOCUS_MARK)).to_have_count(0)
            page.keyboard.press("ArrowRight")
            expect(control).to_be_focused()
            assert control.evaluate("node => node.matches(':focus-visible')")
            expect(page.locator(FOCUS_MARK)).to_have_count(1)
            expect(control).to_have_attribute("data-lf-mark", re.compile(r"\bfocus\b"))
            ring = control.evaluate(MARK)
            assert ring and ring["style"] == "solid" and not ring["brackets"], ring

    page.keyboard.press("Tab")
    private = page.get_by_role("button", name="Private control", exact=True)
    expect(private).to_be_focused()
    expect(private).to_have_css("outline-style", "solid")
    expect(private).to_have_css("outline-width", "2px")
    rendered(page)
    expect(page.locator(FOCUS_MARK)).to_have_count(0)
    expect(private).not_to_have_class(re.compile(r"\blf-projected-mark\b"))

    page.keyboard.press("Tab")
    choice = page.get_by_role("checkbox", name="Keep this choice", exact=True)
    expect(choice).to_be_focused()
    expect(choice).to_have_css("outline-style", "none")
    expect(page.locator(".lf-choice")).to_have_css("outline-width", "2px")
    expect(page.locator(".lf-choice")).to_have_css("outline-style", "solid")
    rendered(page)
    expect(page.locator(FOCUS_MARK)).to_have_count(0)

    page.keyboard.press("Tab")
    expect(page.get_by_role("tab", name="First", exact=True)).to_be_focused()
    page.keyboard.press("Tab")
    panel = page.locator("#view-a")
    expect(panel).to_be_focused()
    expect(panel).to_have_css("outline-style", "none")
    rendered(page)
    assert page.locator("#views").evaluate(
        """tabs => {
          const ring = getComputedStyle(tabs, '::after');
          return {content:ring.content, style:ring.outlineStyle, width:ring.outlineWidth};
        }"""
    ) == {"content": '""', "style": "solid", "width": "2px"}
    expect(page.locator(FOCUS_MARK)).to_have_count(0)

    page.keyboard.press("Tab")
    expect(page.locator("#pane-body")).to_be_focused()
    expect(page.locator("#pane-body")).to_have_css("outline-style", "none")
    rendered(page)
    assert (
        page.locator("#pane").evaluate(
            "node => getComputedStyle(node, '::after').outlineStyle"
        )
        == "solid"
    )
    expect(page.locator(FOCUS_MARK)).to_have_count(0)


def test_a_replay_under_a_held_aim_repaints_the_promise(browser, serve):
    """A pass that runs paints the truth, whatever ran it.

    A replay of another tab's action moves content and repaints the marks where they
    now belong — and the aim used to ride that pass as an answer latched from the last
    mouse event, so the pass itself painted a promise about a card no longer there.
    The aimed element is derived inside the pass now, and the events only decide when a
    pass is worth running. Nothing here moves the mouse after the arm: the page moves
    instead, and the box must follow or clear."""
    url = serve(REPLAYED_PAGE)
    page = open_page(browser, url)
    spot = page.locator("#card-importer").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.right - 8, r.top + 8]; }"
    )
    page.mouse.move(*spot)
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("card-importer")
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "work",
            "action": "move",
            "detail": {"unit": "card-importer", "value": "col-done", "rank": "1i"},
        },
    )
    told(page)
    expect(page.locator("#col-done #card-importer")).to_have_count(1)
    page.wait_for_function(
        """([x, y]) => {
      const promised =
        document.querySelector("[data-lf-aimed]")?.closest("[id]")?.id ?? null;
      const at = document.elementFromPoint(x, y)?.closest("[id]:not(.lf-ui)") ?? null;
      return promised === (at?.id ?? null) && promised !== "card-importer";
    }""",
        arg=spot,
    )
    page.keyboard.up("Alt")


def test_the_aim_shows_over_the_widgets_own_paint(browser, serve):
    """The promise is visible over the widget's own paint.

    The aim used to wear the mark's rail, and that band sat at the border edge — the one
    band of an element nobody else paints in, and exactly where a widget draws a border
    of its own. Over an accented option, whose border is already the accent, arming
    changed nothing a user could see. The aim's veil fills the box; the pixel diff
    here is armed against unarmed with the pointer held still, so the widget's own
    hover wash is in both frames and the difference is the promise alone."""
    from PIL import ImageChops  # a dev dependency already, for the demo recorder

    page = open_page(browser, serve(AIM_PAINT_PAGE))
    card = page.locator("#card-star")
    card.hover()
    # The wash and the lift a card answers the pointer with are transitions, and a
    # frame taken mid-glide would bill the arm for pixels the hover was still moving.
    page.wait_for_function(
        """() => document.getElementById("card-star")
                 .getAnimations({subtree: true}).length === 0"""
    )
    box = card.bounding_box()
    clip = {"x": math.floor(box["x"]), "y": math.floor(box["y"])}
    clip |= {"width": math.floor(box["width"]), "height": math.floor(box["height"])}
    quiet = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    page.keyboard.down("Alt")
    expect(page.locator("[data-lf-aimed]")).to_have_id("card-star")
    armed = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    assert quiet.size == armed.size
    pixels = zip(
        *[iter(ImageChops.difference(quiet, armed).tobytes())] * 3, strict=True
    )
    changed = sum(max(p) >= 6 for p in pixels) / (armed.size[0] * armed.size[1])
    assert changed > 0.5, (
        f"arming changed {changed:.0%} of the card's pixels — the promise is not "
        "something a user can see over the widget's own paint"
    )
    page.keyboard.up("Alt")


@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_a_phone_selection_in_a_tall_paragraph_stays_clear(iphone, serve, edge):
    """A phone selection near either viewport edge stays readable.

    WebKit emulation supplies a Selection without the native iOS long-press menu;
    this proves Leaf's own field does not obscure the selected line.
    """
    page = open_page(
        None,
        serve(
            leaf_page(
                "Tall phone passage",
                '<div style="height: 100vh"></div><p id="passage">'
                + " ".join(f"Sentence {n} keeps its words readable." for n in range(90))
                + '</p><div style="height: 100vh"></div>',
            )
        ),
        context=iphone,
    )
    page.locator("#passage").evaluate(
        """(paragraph, edge) => {
      const range = document.createRange();
      range.setStart(paragraph.firstChild, 1500);
      range.setEnd(paragraph.firstChild, 1525);
      const box = range.getBoundingClientRect();
      scrollTo(0, scrollY + box.top - (edge === 'top' ? 65 : innerHeight - 70));
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""",
        edge,
    )
    field = page.locator(".lf-fab-input")
    expect(field).to_be_hidden()
    page.evaluate("window.phoneQuote = getSelection().getRangeAt(0).cloneRange()")
    selection_field(page).tap()
    expect(field).to_be_focused()
    rendered(page)
    geometry = page.evaluate("""() => {
      const quote = window.phoneQuote.getBoundingClientRect();
      const field = document.querySelector('.lf-fab-bar').getBoundingClientRect();
      return {quote: quote.toJSON(), field: field.toJSON(), height: innerHeight};
    }""")
    quote, bar = geometry["quote"], geometry["field"]
    assert bar["bottom"] <= quote["top"] or bar["top"] >= quote["bottom"], geometry
    assert bar["top"] >= 0 and bar["bottom"] <= geometry["height"], geometry


def test_a_phone_comment_stays_inside_the_visual_viewport(browser, serve):
    """A real browser zoom shrinks the visible viewport without changing layout.

    A software keyboard also reduces that viewport, but this emulation does not
    claim to reproduce the keyboard or native selection menu.
    """
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Visible comment",
                '<p id="passage">Words to comment on.</p><div style="height: 150vh"></div>',
            )
        ),
        context=context,
    )
    page.locator("#passage").evaluate("""paragraph => {
      const range = document.createRange();
      range.selectNodeContents(paragraph);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")
    selection_field(page).tap()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    session = context.new_cdp_session(page)
    session.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 1.25})
    page.wait_for_function("visualViewport.scale === 1.25")
    rendered(page)
    box = page.locator(".lf-fab-bar").bounding_box()
    viewport = page.evaluate(
        "({left: visualViewport.offsetLeft, top: visualViewport.offsetTop, width: visualViewport.width, height: visualViewport.height})"
    )
    assert box["x"] >= viewport["left"], (box, viewport)
    assert box["x"] + box["width"] <= viewport["left"] + viewport["width"], (
        box,
        viewport,
    )
    assert box["y"] >= viewport["top"], (box, viewport)
    assert box["y"] + box["height"] <= viewport["top"] + viewport["height"], (
        box,
        viewport,
    )


COMPOSER_ATTACHMENT_PAGE = leaf_page(
    "An open comment keeps its writer",
    """<aside id="bg-sidebar"><div class="layout-track"><lf-toc id="bg-contents" max-level="2"></lf-toc></div></aside>
<div class="layout-column"><h1 id="title">Resize an active comment</h1>
<h2 id="first">First section</h2><p id="ordinary" tabindex="0">An ordinary paragraph remains visible at both widths.</p>
<h2 id="second">Second section</h2><p>Another section gives the contents outline destinations.</p>
<details id="disclosure" open><summary>Disclosure</summary><p id="detail-word" tabindex="0">A comment target inside a disclosure.</p></details>
<section id="tabbed-section"><h2 id="views-title">A tabbed section</h2>
<lf-tabs id="views"><lf-tab id="active-view" label="First view"><p id="tab-word" tabindex="0">A comment target in the first view.</p></lf-tab>
<lf-tab id="other-view" label="Other view"><p>The other view can appear without closing a draft.</p></lf-tab></lf-tabs></section>
<p id="offscreen-word" tabindex="0">A comment target whose paragraph can scroll away.</p>
<p id="quote-holder" style="height:72px;overflow:auto">Quoted words stay attached to this paragraph.<br>
 More lines inside its reading region.<br> More lines inside its reading region.<br> More lines inside its reading region.<br>
 More lines inside its reading region.<br> More lines inside its reading region.<br> More lines inside its reading region.<br>
 More lines inside its reading region.<br> More lines inside its reading region.<br> More lines inside its reading region.</p>
<section id="reading-space" style="min-height:1400px"><h2 id="reading-title">Reading space</h2><p>Scroll downward while a comment remains open, then return.</p></section></div>
""",
    layout="sidebar",
    head="""<style>
@media (max-width: 800px) { #bg-sidebar {display:none} }
</style>""",
)


def _draft_in_view(page, words, field=None):
    if field is None:
        field = page.locator(".lf-fab-input")
    box = field.bounding_box()
    viewport = page.viewport_size
    return (
        field.is_visible()
        and field.evaluate("el => el.value") == words
        and field.evaluate("el => el.matches(':focus')")
        and (box is not None)
        and (
            box["x"] >= 0
            and box["y"] >= 0
            and (box["x"] + box["width"] <= viewport["width"])
            and (box["y"] + box["height"] <= viewport["height"])
        )
    )


def _open_attachment_draft(browser, url, target):
    page = open_page(browser, url)
    rendered(page)
    expect(page.locator(".lf-fp-field leaf-text")).not_to_have_attribute(
        "data-lf-says", "notice"
    )
    destination = page.locator(target).first
    for _ in range(50):
        if destination.evaluate("el => el.matches(':focus-within')"):
            break
        page.keyboard.press("Tab")
    assert destination.evaluate("el => el.matches(':focus-within')"), target
    page.keyboard.press("c")
    rendered(page)
    words = "A draft about " + target
    page.keyboard.type(words)
    rendered(page)
    judge_watches()
    return (page, words)


def test_quote_attachment_can_hide_while_its_paragraph_remains(browser, serve):
    page = open_page(browser, serve(COMPOSER_ATTACHMENT_PAGE))
    rendered(page)
    expect(page.locator(".lf-fp-field leaf-text")).not_to_have_attribute(
        "data-lf-says", "notice"
    )
    page.locator("#quote-holder").scroll_into_view_if_needed()
    points = page.locator("#quote-holder").evaluate(
        """el => {
        const first=document.createRange(), last=document.createRange();
        first.setStart(el.firstChild,0);first.setEnd(el.firstChild,1);
        last.setStart(el.firstChild,11);last.setEnd(el.firstChild,12);
        const a=first.getBoundingClientRect(),b=last.getBoundingClientRect();
        return [[a.left,a.top+a.height/2],[b.right,b.top+b.height/2]];
    }"""
    )
    select(page, *points)
    rendered(page)
    page.keyboard.press("c")
    rendered(page)
    words = "A draft about quoted words"
    page.keyboard.type(words)
    rendered(page)
    judge_watches()
    before = page.locator(".lf-fab-bar").bounding_box()
    page.evaluate("document.getElementById('quote-holder').scrollTop=200")
    rendered(page)
    field = page.locator(".lf-fab-input")
    expect(field).to_have_js_property("value", words)
    expect(field).to_be_focused()
    after = page.locator(".lf-fab-bar").bounding_box()
    moved = page.locator("#quote-holder").evaluate("node => node.scrollTop")
    assert after["y"] - before["y"] == pytest.approx(-moved, abs=1)
    assert page.locator(".lf-fab-bar").get_attribute("data-lf-plane") == "page"
    page.evaluate("document.getElementById('quote-holder').scrollTop=0")
    rendered(page)
    assert _draft_in_view(page, words)
    assert page.locator(".lf-fab-bar").get_attribute("data-lf-plane") == "page"


def test_a_withheld_draft_restores_editing_and_deliberate_dismissal(browser, serve):
    page, words = _open_attachment_draft(
        browser, serve(COMPOSER_ATTACHMENT_PAGE), "#bg-contents a"
    )
    context = 'composer:[["section","bg-contents"]]'
    saved = draft_key(page, context)
    resized(page, 480, 900)
    rendered(page)
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    assert draft_key(page, context) == saved
    resized(page, 1200, 900)
    rendered(page)
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    assert _draft_in_view(page, words)
    page.keyboard.type(" and more words")
    words += " and more words"
    rendered(page)
    judge_watches()
    assert _draft_in_view(page, words)
    assert draft_key(page, context) == saved
    draft = page.evaluate("([read, ctx]) => read(ctx)", [stored_draft(page), context])
    assert draft["payload"]["anchor"] == {"section": "bg-contents"}
    assert draft["text"] == words
    page.keyboard.press("Escape")
    rendered(page)
    assert not page.locator(".lf-fab-input").is_visible()
    assert stored_draft_text(page, context) == words


@pytest.mark.parametrize("reopen", ["resume", "reload", "withheld", "comment"])
def test_explicit_reopening_keeps_a_css_hidden_subject_draft_reachable(
    browser, serve, reopen
):
    page, words = _open_attachment_draft(
        browser, serve(COMPOSER_ATTACHMENT_PAGE), "#bg-contents a"
    )
    if reopen not in {"withheld", "comment"}:
        page.keyboard.press("Escape")
        page.mouse.click(5, 600)
    resized(page, 480, 900)
    if reopen == "reload":
        page.reload()
        wait_until_ready(page)
    elif reopen == "comment":
        page.keyboard.press("c")
    else:
        page.keyboard.press("g")
        page.keyboard.press("i")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    assert _draft_in_view(page, words)
    expect(page.locator(".lf-fab-bar")).to_have_attribute("data-lf-plane", "window")


@pytest.mark.parametrize("reply", [False, True])
def test_a_withheld_draft_observes_visibility_without_a_layout_change(
    browser, serve, reply
):
    page, words = _open_attachment_draft(
        browser, serve(COMPOSER_ATTACHMENT_PAGE), "#ordinary"
    )
    field = page.locator(".lf-fab-input")
    if reply:
        with sending(page, "the visibility target comment"):
            page.keyboard.press("ControlOrMeta+Enter")
        page.keyboard.press("c")
        field = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
        words = "A reply with the same visibility owner."
        write(field, words)
    page.locator("#ordinary").evaluate("el => el.style.visibility='hidden'")
    expect(field).not_to_be_visible()
    page.locator("#ordinary").evaluate("el => el.style.visibility='visible'")
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    assert _draft_in_view(page, words, field)


def test_a_display_contents_comment_editor_observes_visibility_without_layout(
    browser, serve
):
    """An aimed comment editor follows its boxless target's visible parts without
    relying on a resize or render pass to invalidate floating placement."""
    source = leaf_page(
        "a display contents comment target",
        '<h1>Comment visibility</h1><div id="pair" style="display: contents">'
        "<p><span>The first half.</span></p><p><span>The second half.</span></p></div>",
        layout=None,
    )
    page = open_page(browser, serve(source))
    rendered(page)
    page.locator("#pair span").first.click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    words = "An unfinished comment remains with its display contents target."
    write(field, words)
    expect(field).to_have_js_property("value", words)

    parts = page.locator("#pair > p")
    expect(parts).to_have_count(2)
    parts.evaluate_all("els => els.forEach(el => el.style.visibility='hidden')")
    expect(field).not_to_be_visible()
    parts.evaluate_all("els => els.forEach(el => el.style.visibility='visible')")
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)


DESIGN_PANE_PAGE = leaf_page(
    "design paint in a pane",
    """
  <div id="design-split">
    <lf-pane id="design-pane" label="Findings">
      <div>
        <div style="height: 100px"></div>
        <p id="pane-target" style="height: 260px">The first finding, named.</p>
        <p id="pane-later">A later finding.</p>
        <div style="height: 1600px"></div>
      </div>
    </lf-pane>
    <lf-pane id="other-pane" label="Notes"><div><p id="note">Notes.</p></div></lf-pane>
  </div>""",
    head=regions_side_by_side("design-split"),
    layout="workspace",
)


def _design_mode(page):
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")


# A long page whose paragraphs stand under a header stuck at the window's head, which cuts
# paint over them in the window's plane (geometry.js, `headerInset`).
HEADED_PAGE = LONG_PAGE.replace(
    "<p id='p0'>",
    "<section style='--lf-top: calc(var(--lf-safe-top) + 40px)'>"
    "<h2 id='head' style='position: sticky; top: var(--lf-safe-top); height: 40px;"
    " margin: 0; background: var(--paper)'>Head</h2><p id='p0'>",
).replace("</p>\n</main>", "</p></section>\n</main>", 1)


# A suggestion's accept and reject stand in the margin beside it, each wearing the digit
# obligation travel gives it.
OBLIGATION_PANE_PAGE = DESIGN_PANE_PAGE.replace(
    '<p id="pane-later">A later finding.</p>',
    '<p id="pane-later">Bring <lf-suggestion id="pane-ask"><lf-old>nine.</lf-old>'
    "<lf-new>ten.</lf-new></lf-suggestion> now.</p>",
)

# What a paint over the page's targets is made of, by the places the write watch names.
PAINT = re.compile(
    r"lf-(chip-seat|key-chips|key-badge|paint-|legend|page-search-match|inspect|aim"
    r"|drawing)"
)


# A drawing comment circling what it names, from above its left edge to past its right.
def _drawn_on(section):
    return {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "anchor": {"section": section},
        "drawing": {
            "strokes": [[[-20, -10], [200, 30], [420, 60]]],
            "box": [400, 40],
            "viewport": [1280, 720],
            "scheme": "light",
        },
    }


def _paint_mode(page, mode, words):
    page.evaluate(RELEASE_FOCUS)
    if mode == "obligation":
        page.keyboard.press("m")
        expect(page.locator("#pane-ask")).to_be_focused()
        expect(page.locator(".lf-command-binding-badge")).to_have_count(2)
    elif mode == "search":
        page.keyboard.press("/")
        page.keyboard.type(words)
        expect(page.locator(".lf-page-search-match").first).to_be_visible()
    elif mode == "design":
        _design_mode(page)
    elif mode == "ink":
        expect(page.locator(".lf-drawing-posted")).to_have_count(1)
    else:
        page.keyboard.press({"picker": "s", "go-to": "g"}[mode])
        expect(page.locator(".lf-key-hint[data-lf-hint-code]").first).to_be_visible()


# Every mode's paint in a pane, the frame each of them once trailed by a frame; the
# legend in every frame, and chips under a header's cut and in the window's own plane.
@pytest.mark.parametrize(
    ("mode", "scroller"),
    [
        *(
            (mode, "pane")
            for mode in ("design", "picker", "go-to", "search", "obligation", "ink")
        ),
        ("design", "window"),
        ("design", "header"),
        ("picker", "header"),
        ("go-to", "window"),
    ],
)
def test_a_scroll_carries_paint_over_targets_and_writes_it_once_settled(
    browser, serve, mode, scroller
):
    """Paint over what the page shows, a mode's names, chips and marks, stands where
    what it names is carried, anchored to it in the frames that cut it
    (target-paint-geometry.js, `paintSet`), so a scroll of the window or of a pane moves
    it with the scroll and writes none of it on the scroll's frames. What the scroll
    changes, the map's members and a chip the window's head holds in, is read once it
    settles, and a legend's tags step inside their boxes as they cross a cut. The
    design legend, its boxes and tags placed and written on every scroll, trailed a
    pane by a frame, and so did the picker's and Go-to's chips, the search's mark and
    an obligation's binding digits, each written on every frame of the gesture. Saved ink
    stands the same way."""
    source = {
        "window": LONG_PAGE,
        "header": HEADED_PAGE,
        "pane": OBLIGATION_PANE_PAGE if mode == "obligation" else DESIGN_PANE_PAGE,
    }[scroller]
    if mode == "go-to":
        # Go-to names links.
        source = source.replace(
            "<p id='p", "<p><a href='#t'>Top</a></p><p id='p"
        ).replace("finding", "<a href='#note'>finding</a>")
    events = [_drawn_on("pane-target" if scroller == "pane" else "p3")]
    page = open_page(browser, serve(source, events=events if mode == "ink" else []))
    resized(page, 1280, 720)
    if scroller == "pane":
        pane_scroll_behavior(page, page.locator("#design-pane"), "bounded")
    _paint_mode(page, mode, "finding" if scroller == "pane" else "Paragraph 3")
    if mode == "design":
        named = ["pane-target", "pane-later"] if scroller == "pane" else ["p3", "p4"]
        expect(
            page.locator(f'.lf-legend-box[data-lf-for="{named[0]}"]')
        ).to_be_visible()
        # The boxes one set of frames cuts share its stand, each anchored to what it
        # names.
        stand = page.evaluate(
            """([first, next]) => {
              const box = (id) => document.querySelector(`.lf-legend-box[data-lf-for="${id}"]`);
              return {shared: box(first).closest('.lf-paint-stand')
                        === box(next).closest('.lf-paint-stand'),
                      anchors: [box(first), box(next)].map(
                        (b) => getComputedStyle(b).positionAnchor)};
            }""",
            named,
        )
        assert stand["shared"] and all(
            anchor.startswith("--lf-a") for anchor in stand["anchors"]
        ), stand
    writes, frames = gesture_writes(
        page,
        200,
        scroller="document.querySelector('#design-pane > div')"
        if scroller == "pane"
        else "document.scrollingElement",
    )
    # A carrier may gain distinct boxes as targets enter the near-window inventory.
    # Count each box's membership, so those arrivals are legal while removing and
    # reinserting the same box every frame is still a scroll follower.
    painted = []
    for mutation in writes:
        if not any(PAINT.search(step) for step in mutation["target"]):
            continue
        if mutation["type"] == "childList" and any(
            "lf-paint-carrier" in step for step in mutation["target"]
        ):
            painted.extend(
                {**mutation, "key": f"{mutation['key']} {node}"}
                for node in mutation["nodes"]
            )
        else:
            painted.append(mutation)
    assert not scroll_followers(painted, frames), painted


def test_a_chip_seated_below_its_neighbour_rides_the_scroll_with_it(browser, serve):
    """A chip the picker seats below a neighbour's, which rides the scroll, rides it too
    (keyboard/hints.js, `seatHints`): only what stands still as the page scrolls, the
    window's edge or the chrome, holds a chip where the window does. Held because the
    chrome at the foot shared its column, such a chip stood still mid-page through a
    scroll and jumped once it settled."""
    source = LONG_PAGE.replace(
        "<p id='p10'>",
        "<section id='outer' style='padding-bottom: 12px'><p id='inner'>A nested"
        " line.</p></section><p id='p10'>",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 720)
    page.evaluate(
        "() => document.getElementById('outer').scrollIntoView({block: 'center'})"
    )
    rendered(page)
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("s")
    chips = page.locator(".lf-target-picker-hint[data-lf-hint-code]")
    expect(chips.first).to_be_visible()
    _, _, samples = gesture_writes(
        page,
        60,
        sample="""() => {
          const foot = 40;
          return Object.fromEntries([...document.querySelectorAll(
              '.lf-target-picker-hint[data-lf-hint-code]')]
            .map((chip) => [chip.dataset.lfHintCode, chip.getBoundingClientRect().top])
            .filter(([, top]) => top > foot && top < innerHeight - 120));
        }""",
    )
    first, last = samples[0], samples[-1]
    scrolled = last["scrolled"] - first["scrolled"]
    assert scrolled > 20, samples
    carried = {
        code: round(top - last["read"][code], 1)
        for code, top in first["read"].items()
        if code in last["read"]
    }
    assert carried and all(abs(moved - scrolled) < 1 for moved in carried.values()), (
        scrolled,
        carried,
    )


def test_saved_ink_is_cut_where_its_pane_cuts_what_it_marks(browser, serve):
    """Saved ink stands in the frames that cut what it marks, so a pane that scrolls
    its element away cuts the ink at the pane's edge too, rather than leaving it drawn
    over the pane's header and the page beside it."""
    page = open_page(
        browser, serve(DESIGN_PANE_PAGE, events=[_drawn_on("pane-target")])
    )
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#design-pane"), "bounded")
    mark = page.locator(".lf-drawing-posted")
    expect(mark).to_have_count(1)
    page.evaluate("() => document.querySelector('#design-pane > div').scrollBy(0, 150)")
    rendered(page)
    cut = mark.evaluate(
        """el => {
          const pane = document.querySelector('#design-pane > div').getBoundingClientRect();
          const frame = el.closest('.lf-paint-frame');
          return {ink: el.getBoundingClientRect().top, pane: pane.top,
                  frame: frame && frame.getBoundingClientRect().top,
                  clip: frame && getComputedStyle(frame).clipPath};
        }"""
    )
    assert cut["ink"] < cut["pane"], cut
    assert cut["frame"] == pytest.approx(cut["pane"], abs=1), cut
    assert cut["clip"].startswith("inset(0"), cut


@pytest.mark.parametrize("paint", ["inspect", "legend"])
def test_design_paint_in_a_pane_paints_in_the_frame_its_target_scrolls(
    browser, serve, paint
):
    """Every frame Chrome draws while a pane scrolls under the pointer in Design mode
    shows the name and the legend box level with what they name."""
    follower = (
        f".lf-inspect {{ background: {FOLLOWER_MARK} !important; }}"
        if paint == "inspect"
        else '.lf-legend-box[data-lf-for="pane-target"]'
        f" {{ border: 6px solid {FOLLOWER_MARK} !important; }}"
    )
    page = open_page(
        browser,
        serve(
            DESIGN_PANE_PAGE.replace(
                "</head>",
                f"<style>#pane-target {{ background:{SUBJECT_MARK}; }} {follower}"
                ".lf-legend-tag { display: none; }</style></head>",
            )
        ),
    )
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#design-pane"), "bounded")
    _design_mode(page)
    target = page.locator("#pane-target").bounding_box()
    page.mouse.move(target["x"] + 40, target["y"] + 130)
    expect(page.locator(".lf-inspect")).to_have_text(re.compile("pane-target"))
    rendered(page)
    assert_follows_in_every_frame(page, "#design-pane > div")


# A sticky bar, a fixed bar, and a popover's content: three boxes that do not move with
# the page's scroll alone.
OFF_FLOW_PAGE = leaf_page(
    "off flow",
    "<h1 id='t'>Off flow</h1>"
    "<nav id='nav' style='position: sticky; top: var(--lf-top);"
    " background: var(--paper)'>Contents</nav>"
    "<div id='fixedbar' style='position: fixed; bottom: 0; left: 0; right: 0;"
    " background: var(--paper)'>A fixed bar.</div>"
    "<div id='pop' popover='manual' style='top: 120px; left: 40px; margin: 0'>"
    "<p id='inpop'>Inside the popover.</p></div>"
    + "".join(
        f"<p id='p{i}'>Paragraph {i}. " + "Filler. " * 20 + "</p>" for i in range(40)
    ),
)


def test_legend_tags_step_apart_as_the_page_slides_under_a_sticky_bar(browser, serve):
    """A paragraph's tag scrolls past the tag a sticky bar keeps still, and the two
    step apart as they meet, with no legend pass between (design.js, `placeTags`):
    a scroll that left every tag on the same side of its box once kept the steps it
    found, though the tags it had stepped apart now stood elsewhere."""
    page = open_page(browser, serve(OFF_FLOW_PAGE))
    resized(page, 1280, 720)
    _design_mode(page)
    expect(
        page.locator('.lf-legend-box[data-lf-for="nav"] .lf-legend-tag')
    ).to_be_visible()
    overlaps = """() => {
      const tags = [...document.querySelectorAll('.lf-legend-tag')]
        .filter((tag) => tag.checkVisibility())
        .map((tag) => [tag.closest('.lf-legend-box').dataset.lfFor,
                       tag.getBoundingClientRect()]);
      const found = [];
      for (const [i, [a, r]] of tags.entries())
        for (const [b, q] of tags.slice(i + 1))
          if (r.left < q.right - 0.5 && q.left < r.right - 0.5 &&
              r.top < q.bottom - 0.5 && q.top < r.bottom - 0.5)
            found.push([a, b]);
      return found;
    }"""
    met = []
    for _ in range(60):
        page.evaluate("() => document.scrollingElement.scrollBy(0, 4)")
        rendered(page)
        met += page.evaluate(overlaps)
    assert met == [], met


def test_each_legend_box_stays_on_what_it_names_without_a_pass(browser, serve):
    """Each legend box is anchored to its own element, so it stays on a sticky bar the
    page scrolls under and on an element a transform moves, with no pass to place it
    again (design.js, `paintLegend`); a fixed bar and a popover's content, which no
    frame cuts, stand beside it."""
    page = open_page(browser, serve(OFF_FLOW_PAGE))
    resized(page, 1280, 720)
    page.evaluate("() => document.getElementById('pop').showPopover()")
    _design_mode(page)
    offsets = """(ids) => ids.map((id) => {
      const box = document.querySelector(`.lf-legend-box[data-lf-for="${id}"]`);
      if (!box?.isConnected) return [id, null];
      const b = box.getBoundingClientRect();
      const it = document.getElementById(id).getBoundingClientRect();
      return [id, Math.round(b.left - it.left), Math.round(b.top - it.top)];
    })"""
    ids = ["nav", "p3", "fixedbar", "inpop"]
    expect(page.locator('.lf-legend-box[data-lf-for="inpop"]')).to_be_visible()
    assert page.evaluate(offsets, ids) == [[id, -1, -1] for id in ids]
    page.mouse.move(2, 300)
    page.mouse.wheel(0, 600)
    scroll_settled(page)
    assert page.evaluate(offsets, ["nav"]) == [["nav", -1, -1]]
    # A sheet moves the element with no mutation a pass could hear; the box is read in
    # the same task, before any frame.
    moved = page.evaluate(
        """(offsets) => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync('#p3 { transform: translateX(30px); }');
          document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
          return eval(offsets)(['p3']);
        }""",
        offsets,
    )
    assert moved == [["p3", -1, -1]], moved


def test_selected_words_grow_context_until_the_exact_span_resolves(browser, serve):
    """Capture grows to the semantic boundary, rather than another correctness cap: the
    words telling these copies apart stand far beyond any cap a capture could hold."""
    filler = "shared " * 256
    markup = leaf_page(
        "Repeated passages",
        '<h1>Runs</h1><section id="runs"><h2>Run log</h2>'
        + "".join(
            f"<article><h3>{name}</h3><p>{filler}passed {filler}</p></article>"
            for name in ["Alpha", "Beta", "Gamma"]
        )
        + "</section>",
    )
    page = open_page(browser, serve(markup))
    captured = page.evaluate("""async () => {
      const A = await window.__lfCheckApi();
      const P = {...await window.__lfCheckApi(), ...await window.__lfWidgetApi()};
      const text = document.querySelectorAll('#runs p')[1].firstChild;
      const start = text.data.indexOf('passed');
      const range = document.createRange();
      range.setStart(text, start); range.setEnd(text, start+6);
      const anchor = A.anchorForRange(range);
      const resolved = A.resolveAnchor(anchor);
      const wanted = P.spanIn(P.pageText(), P.segmentsIn(range));
      const found = resolved && P.spanIn(P.pageText(), resolved.segments);
      return {anchor, wanted, found};
    }""")
    assert captured["wanted"] == captured["found"]
    assert len(captured["anchor"]["prefix"]) > 96
    passages = passages_model.page_passages(structure_model.SourceDocument(markup))
    offset = anchor_capture_model.resolve_quote(passages, captured["anchor"])
    assert offset == [m.start() for m in re.finditer("passed", passages.text)][1]


@pytest.mark.parametrize("change", [None, "text", "replacement", "revision"])
def test_a_detached_selection_still_has_a_live_writable_composer(
    browser, serve, change
):
    """The native Range owns composition geometry; saved ambiguity stays detached."""
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Repeated fenced passages",
                    '<h1>Runs</h1><section id="runs"><p>Repeated passed text.</p><p>Repeated passed text.</p></section><div style="height:2000px"></div>',
                )
            )
        ),
    )
    errors = []
    collect_page_exceptions(page, errors)
    anchor = page.evaluate("""async () => {
      const P = {...await window.__lfCheckApi(), ...await window.__lfWidgetApi()};
      const A = await window.__lfCheckApi();
      const owner = document.querySelector('#runs');
      P.fencePassageParts(owner);
      const text = owner.querySelectorAll('p')[1].firstChild;
      const range = document.createRange();
      const start = text.data.indexOf('passed');
      range.setStart(text, start); range.setEnd(text, start+6);
      const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
      const anchor = A.anchorForRange(range);
      if (A.resolveAnchor(anchor) !== null) throw Error('fixture must stay ambiguous');
      return anchor;
    }""")
    assert anchor["detached"] is True
    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(field).to_be_in_viewport()
    write(field, "Review the second occurrence.")
    page.set_viewport_size({"width": 1000, "height": 800})
    expect(field).to_be_in_viewport()
    expect(field).to_be_focused()
    # Recovery uses the same native Range that placed this editor, even though its
    # semantic anchor remains detached.
    page.evaluate("window.scrollTo(0, 500)")
    expect(field).not_to_be_in_viewport()
    page.evaluate("""async () => {
      const {bringBackSurfaceOf} = await window.__lfCheckApi();
      bringBackSurfaceOf(document.querySelector('.lf-fab-input'), 'instant');
    }""")
    expect(field).to_be_in_viewport()
    if change == "revision":
        page.keyboard.press("Escape")
        source = (serve.page_dir / "index.html").read_text()
        source = source.replace(
            "<p>Repeated passed text.</p><p>Repeated passed text.</p>",
            "<p>Repeated passed text.</p><p>Replacement passage.</p>",
        )
        stamp = stamp_page(serve.page_dir, source, "Replace the selected occurrence")
        wait_for_revision(page, stamp["revision"])
        field = page.locator(".lf-fab-input")
    elif change:
        before = page.evaluate(
            """async change => {
          const {bringBackSurfaceOf} = await window.__lfCheckApi();
          window.scrollTo(0, 500);
          const paragraph = document.querySelectorAll('#runs p')[1];
          if (change === 'text') paragraph.firstChild.data = 'Repeated failed text.';
          else {
            const replacement = document.createElement('p');
            replacement.textContent = 'Replacement passage.';
            paragraph.replaceWith(replacement);
          }
          const before = scrollY;
          bringBackSurfaceOf(document.querySelector('.lf-fab-input'), 'instant');
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          return {before, after: scrollY};
        }""",
            change,
        )
        assert before["after"] == before["before"]
        assert page.evaluate(
            """async anchor => {
          const A = await window.__lfCheckApi();
          const P = {...await window.__lfCheckApi(), ...await window.__lfWidgetApi()};
          return A.resolveAnchor(anchor) === null;
        }""",
            anchor,
        )
    if change:
        # Losing the Range never abandons the editor's words or durable uncertainty.
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(field).to_be_focused()
        expect(field).to_be_in_viewport()
        expect(field).to_have_js_property("value", "Review the second occurrence.")
    with sending(page, "the detached quoted comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert event["anchor"] == anchor
    assert page.evaluate(
        """async anchor => {
      const {resolveAnchor} = await window.__lfCheckApi();
      return resolveAnchor(anchor) === null;
    }""",
        anchor,
    )
    if change == "revision":
        # Its words gone from the page, the thread is still reached in the panel.
        expect(open_panel_thread(page, event["id"])).to_contain_text(
            "Review the second occurrence."
        )
    assert errors == []


def test_design_hint_faces_follow_controls_and_their_native_labels(browser, serve):
    """A hint stands above its own face, including wrapping and stacked labels."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Control hint faces",
                '<h1>Controls</h1><section id="controls" style="padding:80px">'
                '<div style="display:flex;gap:8px;margin-bottom:80px"><button>Reset</button><button>Copy instruction</button><button>Apply treatment</button></div>'
                '<label style="display:inline-block;padding:8px"><input type="radio" name="choice" aria-label="Choice A">Choice A</label>'
                '<label style="display:inline-block;padding:8px"><input type="radio" name="choice" aria-label="Choice B">Choice B</label>'
                '<div style="margin-top:80px"><label for="stacked">Stacked label</label><br><input id="stacked" aria-label="Stacked input"></div>'
                "</section>",
            )
        ),
    )
    page.set_viewport_size({"width": 1400, "height": 1200})
    page.keyboard.press("l")
    page.keyboard.press("s")
    said = page.locator(".lf-live")
    seen = set()
    heard = []
    names = {
        "Reset",
        "Copy instruction",
        "Apply treatment",
        "Choice A",
        "Choice B",
        "Stacked input",
    }
    for _ in range(12):
        before = said.text_content()
        page.keyboard.press("Tab")
        expect(said).not_to_have_text(before)
        expect(said).to_have_text(re.compile(r"^Hint .*Press Enter to choose\.$"))
        heard.append(said.text_content())
        name = next(
            (
                name
                for name in names
                if f": {name} ·" in said.text_content()
                or f": control: {name}." in said.text_content()
            ),
            None,
        )
        if not name:
            continue
        seen.add(name)
        control = page.get_by_role(
            "radio"
            if name.startswith("Choice")
            else "textbox"
            if name == "Stacked input"
            else "button",
            name=name,
            exact=True,
        )
        face = control.evaluate("""control => {
          const boxes = [control, ...(control.labels ?? [])].map(n => n.getBoundingClientRect());
          return {left: Math.min(...boxes.map(b => b.left)), top: Math.min(...boxes.map(b => b.top))};
        }""")
        hint = page.locator(".lf-target-picker-hint.lf-current").bounding_box()
        assert abs(hint["x"] - face["left"]) < 1
        assert hint["y"] + hint["height"] <= face["top"]
        if seen == names:
            break
    assert seen == names, heard


@pytest.mark.parametrize("route", ["pointer", "keyboard"])
def test_a_unique_anonymous_control_captures_its_visible_face(browser, serve, route):
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Control face",
                    '<h1>Settings</h1><section id="controls" style="padding:80px"><label><input type="radio" name="choice" aria-label="Choice A">Choice A</label> <label><input type="radio" name="choice" aria-label="Choice B">Choice B</label><div style="height:400px"></div></section>',
                )
            )
        ),
    )
    page.keyboard.press("l")
    control = page.get_by_role("radio", name="Choice B")
    target = page.evaluate("""async () => {
      const A=await window.__lfCheckApi();const P={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};
      const target=A.aimTargetAt(document.querySelector('[aria-label="Choice B"]'),{design:true});
      const resolved=A.resolveAnchor(target.anchor);
      return {anchor:target.anchor,label:target.label,exact:resolved.exact};
    }""")
    assert target["exact"] and target["anchor"]["quote"] == "Choice B"
    assert target["anchor"]["part"] == "Choice B"
    if route == "pointer":
        control.click()
    else:
        page.keyboard.press("s")
        said = page.locator(".lf-live")
        for _ in range(8):
            previous = said.text_content()
            page.keyboard.press("Tab")
            expect(said).not_to_have_text(previous)
            expect(said).to_have_text(re.compile(r"^Hint .*Press Enter to choose\.$"))
            if f": {target['label']}. Press Enter to choose." in said.text_content():
                break
        else:
            pytest.fail("The Choice B control was not offered")
        page.keyboard.press("Enter")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(control).not_to_be_checked()
    field_box, control_box = field.bounding_box(), control.bounding_box()
    assert abs(field_box["y"] - control_box["y"]) < 100
    write(field, "Clarify Choice B.")
    with sending(page, "the selected control's visible face"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert event["anchor"] == target["anchor"]
    source = (serve.page_dir / "index.html").read_text()
    passages = passages_model.page_passages(structure_model.SourceDocument(source))
    assert anchor_capture_model.resolve_quote(passages, event["anchor"]) is not None
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    stamp = stamp_page(
        serve.page_dir,
        source.replace("<h1>Settings</h1>", "<h1>Updated settings</h1>"),
        "Revise the page around the retained control",
    )
    wait_for_revision(page, stamp["revision"])
    page.keyboard.press("Shift+t")
    card = page.locator(".lf-margin-thread .lf-page-thread")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Clarify Choice B.")
    assert abs(card.bounding_box()["y"] - control.bounding_box()["y"]) < 100
    # A revision around the control leaves its captured words exact.
    assert page.evaluate(
        """async anchor => {
          const {resolveAnchor} = await window.__lfCheckApi();
          return resolveAnchor(anchor).exact;
        }""",
        event["anchor"],
    )


def test_automatic_design_capture_never_borrows_mutable_editor_context(browser, serve):
    """Static neighbours stay file-readable; unnamed edited values never name parts."""
    markup = leaf_page(
        "Editing fences",
        '<h1>Review</h1><section id="controls">'
        "<button>Save</button>"
        '<div contenteditable="plaintext-only">Draft words</div>'
        "<button>Save</button>"
        '<div contenteditable="plaintext-only" role="textbox">Backup words</div>'
        '<div contenteditable="true" aria-label="Equal editor">Alpha words</div>'
        '<div contenteditable="true" aria-label="Equal editor">Beta words</div>'
        "</section>",
    )
    page = open_page(browser, live_url(serve(markup)))
    editor = page.locator("#controls > div").first
    editor.click()
    editor.press("End")
    editor.press_sequentially(" plus my notes")
    reading = page.evaluate("""async()=>{
      const A=await window.__lfCheckApi();
      const P={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};
      return [...document.querySelectorAll('#controls > *')].map(el=>{
        const t=A.aimTargetAt(el,{design:true});
        return {anchor:t.anchor,exact:A.resolveAnchor(t.anchor).exact};
      });
    }""")
    passages = passages_model.page_passages(structure_model.SourceDocument(markup))
    for target in (reading[0], reading[2]):
        assert "my notes" not in json.dumps(target["anchor"])
        if target["exact"]:
            assert (
                anchor_capture_model.resolve_quote(passages, target["anchor"])
                is not None
            )
        else:
            assert target["anchor"] == {"section": "controls", "part": "Save"}
    assert reading[1]["anchor"] == reading[3]["anchor"] == {"section": "controls"}
    assert (
        reading[4]["anchor"]
        == reading[5]["anchor"]
        == {"section": "controls", "part": "Equal editor"}
    )
    assert not reading[4]["exact"] and not reading[5]["exact"]
    # An actual native selection still carries observed words and a writable live
    # editor. The automatic file-readable route does not restrict a user's Range.
    box = editor.bounding_box()
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + 240, box["y"] + box["height"] / 2),
    )
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    write(field, "Keep this manually selected text.")
    with sending(page, "the edited native selection"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert "plus my notes" in event["anchor"]["quote"]
    assert event["text"] == "Keep this manually selected text."


def test_native_editing_cells_share_file_and_browser_passage_fences(browser, serve):
    markup = leaf_page(
        "Reading cells",
        '<h1>Review</h1><p id="cells">Before '
        '<span contenteditable="plaintext-only">Editable <em>inline</em> '
        '<span contenteditable="false">Readonly <b>island</b> '
        '<span contenteditable="true">Nested value</span> Endreadonly</span> Endedit</span> After '
        "<svg><text>Vector <tspan>words</tspan> here</text></svg></p>",
    )
    page = open_page(browser, live_url(serve(markup)))
    quotes = [
        "Before Editable",
        "Editable inline",
        "inline Readonly",
        "Readonly island",
        "island Nested",
        "Nested value",
        "value Endreadonly",
        "Endreadonly Endedit",
        "Endedit After",
        "Vector words here",
    ]
    browser_found = page.evaluate(
        """async quotes=>{
      const P={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};
      return quotes.map(quote=>P.findQuote(P.pageText(),quote,{section:'cells'},document.querySelector('#cells')).length>0);
    }""",
        quotes,
    )
    passages = passages_model.page_passages(structure_model.SourceDocument(markup))
    file_found = [
        anchor_capture_model.resolve_quote(
            passages, {"section": "cells", "quote": quote}
        )
        is not None
        for quote in quotes
    ]
    assert (
        browser_found
        == file_found
        == [False, True, False, True, False, True, False, False, False, True]
    )
    # The editable attribute changes the indexed reading even without a text change.
    page.locator("#cells > span").evaluate(
        "el=>el.setAttribute('contenteditable','false')"
    )
    assert page.evaluate("""async()=>{
      const P={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};
      return P.findQuote(P.pageText(),'Before Editable',{section:'cells'},document.querySelector('#cells')).length>0;
    }""")


def test_a_native_cross_cell_selection_sends_its_quote_without_claiming_location(
    browser, serve
):
    markup = leaf_page(
        "Cross-cell selection",
        '<h1>Review</h1><p id="cross-cell">Before field '
        '<span contenteditable="true">Editor words</span> After field.</p>',
    )
    page = open_page(browser, live_url(serve(markup)))
    passage = page.locator("#cross-cell")
    box = passage.bounding_box()
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 2, box["y"] + box["height"] / 2),
    )
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    observed = page.evaluate("""async()=>{
      const A=await window.__lfCheckApi();
      const P={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};
      return A.anchorForRange(P.pageRange(getSelection()));
    }""")
    assert observed["quote"] == "Before field Editor words After field."
    assert observed["detached"] is True
    write(field, "Keep this entire selection in the comment.")
    with sending(page, "the native cross-cell quotation"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert event["anchor"] == observed
    assert event["text"] == "Keep this entire selection in the comment."
    passages = passages_model.page_passages(structure_model.SourceDocument(markup))
    assert anchor_capture_model.resolve_quote(passages, event["anchor"]) is None
    assert page.evaluate(
        """async anchor=>{
      const A=await window.__lfCheckApi();
      const P={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};
      return A.resolveAnchor(anchor) === null;
    }""",
        event["anchor"],
    )
    expect(open_panel_thread(page, event["id"])).to_contain_text(
        "Keep this entire selection in the comment."
    )


@pytest.mark.parametrize("authored", [None, "-1", "0"])
def test_borrowed_scroll_stops_leave_code_selection_and_marks_with_their_owners(
    browser, serve, authored
):
    """Reachable code is prose; only an authored working region owns its click."""
    attrs = "" if authored is None else f' tabindex="{authored}"'
    markup = leaf_page(
        "Code reachability",
        '<h1>Review code</h1><section id="snippets">'
        f'<pre id="code"{attrs} style="width:260px"><code>'
        "alpha_function_name = compute_the_overly_long_value(first_argument, second_argument, third_argument)"
        "</code></pre></section>",
    )
    page = open_page(browser, live_url(serve(markup)))
    code = page.locator("#code")
    expect(code).to_have_attribute("tabindex", "0")
    borrowed = authored != "0"
    if borrowed:
        expect(code).to_have_attribute("data-lf-lent-reach-stop", "")
    else:
        expect(code).not_to_have_attribute("data-lf-lent-reach-stop", "")
    assert code.evaluate("""async el=>{
      const {WORKS}=await window.__lfCheckApi();
      return el.matches(WORKS);
    }""") is (not borrowed)
    if borrowed:
        page.keyboard.press("Escape")
        page.locator("h1").click()
        page.keyboard.press("l")
        box = page.locator("#code code").bounding_box()
        start = (box["x"] + 2, box["y"] + 8)
        end = (box["x"] + 130, box["y"] + 8)
        select(page, start, end)
        field = page.locator(".lf-fab-input")
        expect(field).to_be_visible()
        selected = page.evaluate("getSelection().toString()")
        assert "alpha" in selected
        write(field, "Clarify this code.")
        with sending(page, "the selected code in Design"):
            page.keyboard.press("ControlOrMeta+Enter")
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        page.locator("h1").click()
        page.mouse.click(start[0] + 30, start[1])
        dialog = page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text("Clarify this code.")
        reply = dialog.get_by_role("textbox", name="Reply")
        reply.click()
        expect(reply).to_be_focused()
        page.keyboard.press("Escape")
    # Retiring scrolling and the code-copy claim returns authored focus state.
    code.evaluate("""async el=>{
      el.style.overflow='visible';
      const words=el.querySelector('code');
      words.replaceWith(...words.childNodes);
      const {reachScrollers}=await window.__lfCheckApi();
      reachScrollers(el);
    }""")
    expect(code).not_to_have_attribute("data-lf-lent-reach-stop", "")
    if authored is None:
        expect(code).not_to_have_attribute("tabindex", "0")
    else:
        expect(code).to_have_attribute("tabindex", authored)


def test_releasing_a_claimed_stop_keeps_another_owners_focus_value(browser, serve):
    markup = leaf_page(
        "Reach ownership",
        '<h1>Review</h1><pre id="code"><code>alpha_function_name</code></pre>',
    )
    page = open_page(browser, live_url(serve(markup)))
    expect(page.locator("#code")).to_have_attribute("data-lf-lent-reach-stop", "")
    transferred = page.locator("#code").evaluate("""async el=>{
      const {releaseReachStop}=await window.__lfCheckApi();
      el.setAttribute('tabindex','5');
      releaseReachStop(el);
      return {value:el.getAttribute('tabindex'),borrowed:el.hasAttribute('data-lf-lent-reach-stop')};
    }""")
    assert transferred == {"value": "5", "borrowed": False}


def test_native_textarea_defaults_never_supply_design_passage_context(browser, serve):
    markup = leaf_page(
        "Native values",
        '<h1>Review fields</h1><section id="fields">'
        '<p id="guidance">Stable surrounding field guidance.</p>'
        "<textarea>Original draft words.</textarea>"
        '<textarea aria-label="Notes">Other draft words.</textarea>'
        "<button>Publish draft</button><p>Further stable guidance.</p></section>",
    )
    page = open_page(browser, live_url(serve(markup)))
    fields = page.locator("textarea")

    def capture():
        return page.evaluate("""async()=>{
          const A=await window.__lfCheckApi();
          const P={...await window.__lfCheckApi(),...await window.__lfWidgetApi()};
          return {
            fields:[...document.querySelectorAll('textarea')].map(el=>{
              const target=A.aimTargetAt(el,{design:true});
              return {anchor:target.anchor,label:target.label,
                exact:A.resolveAnchor(target.anchor).exact,
                says:P.textNodesUnder(el).map(s=>s.node.data).join('')};
            }),
            button:A.aimTargetAt(document.querySelector('#fields button'),{design:true}).anchor,
            words:P.pageText().raw,
          };
        }""")

    before = capture()
    fields.nth(0).fill("Changed live value.")
    fields.nth(1).fill("Changed named value.")
    after = capture()
    assert before == after
    assert [field["anchor"] for field in after["fields"]] == [
        {"section": "fields", "part": "textarea"},
        {"section": "fields", "part": "Notes"},
    ]
    assert not any(field["exact"] for field in after["fields"])
    assert all(field["says"] == "" for field in after["fields"])
    for words in (
        "Original draft words.",
        "Other draft words.",
        "Changed live value.",
        "Changed named value.",
    ):
        assert words not in after["words"]
        assert all(words not in field["label"] for field in after["fields"])
    passages = passages_model.page_passages(structure_model.SourceDocument(markup))
    for quote in ("Original draft words.", "Other draft words."):
        assert (
            anchor_capture_model.resolve_quote(
                passages, {"section": "fields", "quote": quote}
            )
            is None
        )
    assert anchor_capture_model.resolve_quote(passages, after["button"]) is not None
    assert (
        anchor_capture_model.resolve_quote(
            passages,
            {"section": "guidance", "quote": "Stable surrounding field guidance."},
        )
        is not None
    )
    page.locator("h1").click()
    page.keyboard.press("l")
    fields.nth(0).click()
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    write(field, "Clarify this field.")
    with sending(page, "the anonymous native field"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert event["anchor"] == after["fields"][0]["anchor"]
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    fields.nth(0).click()
    expect(fields.nth(0)).to_be_focused()
    fields.nth(0).press("End")
    fields.nth(0).press_sequentially(" still editable")
    expect(fields.nth(0)).to_have_value("Changed live value. still editable")


@pytest.mark.parametrize("shift, placement", [(0, "right-start"), (250, "left-start")])
def test_a_side_comment_grows_down_from_the_line_it_was_opened_on(
    browser, serve, shift, placement
):
    """Beside a passage, a draft that wraps keeps what the user has written where they
    wrote it: the field's top holds and its foot, with Send, moves down a line per wrap,
    as in an editor. Enter sends, so a hand on the keys never chases Send. (#1159 held
    the foot and raised the words above it; the user chose this instead.)"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Side comment growth",
                '<div style="height: 240px"></div>'
                f'<p id="passage" style="position:relative;left:{shift}px">'
                "This passage has room beside it for a response.</p>"
                '<div style="height: 700px"></div>',
            )
        ),
    )
    resized(page, 1440, 900)
    page.locator("#passage").click(modifiers=["Alt"])
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    assert bar.get_attribute("data-lf-placement") == placement
    resting = page.evaluate(SIDE_COMMENT)

    # Word by word until the field has wrapped twice, reading every keystroke's result.
    readings = [resting]
    words = iter(("the words keep coming as the user writes " * 12).split())
    while len({round(reading["height"]) for reading in readings}) < 3:
        page.keyboard.type(next(words) + " ")
        rendered(page)
        readings.append(page.evaluate(SIDE_COMMENT))
    for reading in readings:
        assert reading["top"] == pytest.approx(resting["top"], abs=0.5), reading
        assert reading["field"] == pytest.approx(resting["field"], abs=0.5), reading
        assert reading["scrolled"] == 0, reading
    for before, after in pairwise(readings):
        assert after["bottom"] >= before["bottom"] - 0.5, (before, after)
    grown = readings[-1]
    assert grown["bottom"] > resting["bottom"] + 30, (resting, grown)
    assert grown["send"] > resting["send"] + 30, (resting, grown)

    write(field, "Short again")
    rendered(page)
    shortened = page.evaluate(SIDE_COMMENT)
    assert shortened["top"] == pytest.approx(resting["top"], abs=0.5), shortened
    assert shortened["bottom"] == pytest.approx(resting["bottom"], abs=0.5), shortened

    # A restored draft opens from the same line, its lines under it.
    write(field, "First line\nSecond line\nThird line")
    page.reload()
    rendered(page)
    # Startup recovery has already reopened the editor at its saved passage.
    field = open_compact_comment(page)
    expect(field).to_have_js_property("value", "First line\nSecond line\nThird line")
    rendered(page)
    restored = page.evaluate(SIDE_COMMENT)
    assert restored["top"] == pytest.approx(resting["top"], abs=1), restored
    assert restored["bottom"] > resting["bottom"] + 30, restored


def test_design_mode_survives_the_reload_a_new_version_brings(browser, serve):
    """A version landing mid-batch reloads the document, and a user put out of the
    mode by news they never asked for is a mode error the page made — so the mode is
    this tab's working state, kept the way the panel's open state is."""
    page = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    page.reload()
    wait_until_ready(page)
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    expect(page.locator('.lf-legend-box[data-lf-for="approach"]')).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
    page.reload()
    wait_until_ready(page)
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
