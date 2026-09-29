"""Modifier aiming and design-mode browser tests."""

import io
import math
import re
from datetime import datetime, timedelta
from itertools import pairwise

import pytest
from interact_support import (
    SHIPPED_PACKAGES,
    append_command,
)
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf import session as session_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.served_state import page as served_page
from leaf.validation import compatibility as validation_model
from PIL import Image, ImageChops
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
    ASKS_PAGE,
    HOLD_MOTION,
    SUGGESTION_PAGE,
    live_url,
)
from render_cases_layout import (
    AIM_CURSOR,
    AIM_PAINT_PAGE,
    AIM_POINT,
    AIM_SEAM,
    AIM_SEAM_PAGE,
    AIMED,
    CORNER_PAGE,
    DRAFT_MARK,
    EDGES,
    FOCUS_IN_PAGE,
    LEGEND_TRUE,
    NAMED,
    PAGE_MARKUP,
    aim_targets,
    banner_control,
    draw_edge,
    edge_settled,
    geometry,
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
    TYPED_PARTS_PAGE,
    TYPED_PARTS_V2,
    prefixed_visual_layer,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    RELEASE_FOCUS,
    REPLAYED_PAGE,
    SAMPLE_PAGE,
    expect_comment_notes,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    select,
    sending,
    stamp_page,
    told,
    write,
)

pytestmark = pytest.mark.nightly


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
        next(p for p in EXAMPLES if p.stem == "release-notes"),
        frozenset({"draft mousedown", "suggestion margin control"}),
    ),
    (
        "ship-review",
        next(p for p in EXAMPLES if p.stem == "ship-review"),
        frozenset({"option click", "standing mark"}),
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
    expect(composer).to_have_css("display", "contents")
    if text is None:
        return field
    else:
        page.keyboard.type(text)
        expect(field).to_have_js_property("value", text)
        expect(field).to_be_focused()
        expect(bar).to_be_visible()
        expect(composer).to_have_css("display", "contents")
    return field


def test_the_catalog_sidenote_can_be_aimed_whole(browser, serve):
    """The sidenote authors copy carries the identity its advertised aim needs.

    A handwritten fixture would prove the runtime and leave the catalog free to
    regress to an id-less note that renders normally but gives Alt nothing to outline.
    Drive that example itself through the whole gesture, from outline to anchored
    composer."""
    registry = validation_model.incoming_registry(SHIPPED_PACKAGES)
    sidenote = registry["$idioms"]["aside.sidenote"]["example"]
    html = LONG_PAGE.replace(
        '<h1 id="t">Long</h1>', f'<h1 id="t">Long</h1>\n{sidenote}'
    )
    page = open_page(browser, serve(html))
    note = page.locator("#logout-frequency")

    note.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "logout-frequency")
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
    expect(page.locator(".lf-composer")).to_have_css("display", "contents")
    with sending(page, "the compact comment"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["text"] == (
        "why here\nbecause every active session must end before support continues"
    )
    expect(page.locator(".lf-fab-bar")).to_be_hidden()


def test_a_compact_comment_carries_its_box_into_the_inline_thread(browser, serve):
    """The in-place field and the thread are two sizes of one writing surface.

    The field keeps the small footprint that leaves the passage readable, but uses the
    thread UI's type instead of a smaller caption face. On send, its last rectangle is
    carried to the inline thread while the real card fades through it; the card must not
    simply replace the field in one frame.
    """
    page = open_page(browser, serve(LONG_PAGE), init_script=HOLD_MOTION)
    resized(page, 1440, 900)
    target = page.locator("#p10")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"])
    field = open_compact_comment(page)
    compact = field.evaluate(
        """node => {
          const style = getComputedStyle(node), box = node.getBoundingClientRect();
          return { x: box.x, y: box.y, width: box.width, height: box.height,
                   family: style.fontFamily, size: style.fontSize };
        }"""
    )
    assert compact["height"] == 32
    write(field, "Carry this comment into its thread.")
    source = field.bounding_box()
    # Keep a margin render pending across the accepted comment and its next frame.
    # Rendering rebuilds entry records, so the scheduled carry must recognize the same
    # destination by its durable key rather than by the old record's object identity.
    page.evaluate(
        """() => {
          window.__lfForceMarginRender = true;
          const renderAgain = () => {
            if (!window.__lfForceMarginRender) return;
            dispatchEvent(new Event('resize'));
            requestAnimationFrame(renderAgain);
          };
          requestAnimationFrame(renderAgain);
        }"""
    )
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    ghost = page.locator(".lf-thread-transition")
    expect(ghost).to_have_count(1)
    page.evaluate("() => (window.__lfForceMarginRender = false)")
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    thread = preview.locator(".lf-page-thread")
    reply = preview.locator("leaf-text")
    expect(thread).to_be_focused()
    full = reply.evaluate(
        "node => ({ family: getComputedStyle(node).fontFamily, "
        "size: getComputedStyle(node).fontSize })"
    )
    assert (compact["family"], compact["size"]) == (
        full["family"],
        full["size"],
    )

    # Hold the first frame: the field's submitted box still stands exactly where the
    # user left it, and the full card is transparent underneath. Three motions share
    # the one duration — shell, card, and words — so reduced motion can settle all three
    # through the same primitive.
    assert page.evaluate("() => window.__lfHeld.length") == 3
    carried = ghost.bounding_box()
    for dimension in ("x", "y", "width", "height"):
        assert carried[dimension] == pytest.approx(source[dimension], abs=1)
    expect(preview).to_have_css("opacity", "0")
    destination = page.evaluate(
        """() => {
          const preview = document.querySelector('.lf-margin-preview');
          const card = preview.getBoundingClientRect();
          const motion = window.__lfHeld.find((played) =>
            played.effect.target.classList.contains('lf-thread-transition'));
          const end = motion.effect.getKeyframes().at(-1);
          return {
            card: {
              x: parseFloat(preview.style.left), y: parseFloat(preview.style.top),
              width: card.width, height: card.height,
            },
            end: {
              x: parseFloat(end.left), y: parseFloat(end.top),
              width: parseFloat(end.width), height: parseFloat(end.height),
            },
          };
        }"""
    )
    for dimension in ("x", "y", "width", "height"):
        assert destination["end"][dimension] == pytest.approx(
            destination["card"][dimension], abs=1
        ), destination
    page.evaluate(
        """() => {
          const words = window.__lfHeld.find((played) =>
            played.effect.target.classList.contains('lf-thread-transition-text')
          );
          words.currentTime = words.effect.getComputedTiming().duration / 2;
        }"""
    )
    expect(ghost.locator(".lf-thread-transition-text")).to_have_css("opacity", "0")

    page.evaluate("() => [...window.__lfHeld].forEach((played) => played.finish())")
    expect(ghost).to_have_count(0)
    expect(preview).to_have_css("opacity", "1")
    expect(thread).to_be_focused()


def test_an_aimed_comment_keeps_its_place_with_the_asks_drawer_open(browser, serve):
    """The Asks drawer stands over the page without moving its coordinate plane.

    A broad authored rule may position ordinary divs, and the drawer may arrive over a
    target without another pointer event. Neither may move the chrome's document origin or
    leave its reading of the page behind. Keep the whole comment route on the item the
    user pointed at.
    """
    source = ASKS_PAGE.replace(
        "</head>",
        "<style>html { position: relative; margin-left: 40px; "
        "border-left: 30px solid transparent; } "
        "div { position: relative; }</style></head>",
    )
    page = open_page(browser, serve(source))
    # 900 leaves the composer no side lane, so it takes the vertical route.
    resized(page, 900, 900)

    target = page.locator("#lq-keep")
    target.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "lq-keep")
    # Open by script so the pointer remains parked on the target while the drawer arrives.
    page.locator(".lf-asks").evaluate("node => node.click()")
    edge_settled(page, EDGES[1])
    aligned = page.evaluate(
        """() => {
          const target = document.getElementById('lq-keep').getBoundingClientRect();
          const aim = document.querySelector('.lf-aim').getBoundingClientRect();
          const chrome = document.querySelector('.lf-chrome');
          return { rootPosition: getComputedStyle(document.documentElement).position,
                   bodyPosition: getComputedStyle(document.body).position,
                   chromePosition: getComputedStyle(chrome).position,
                   dx: aim.left - target.left, dy: aim.top - target.top };
        }"""
    )
    assert aligned["rootPosition"] == "static", (
        "authored root positioning captured the document coordinate plane"
    )
    assert aligned["bodyPosition"] == "static", (
        "body became a moving containing block for document-attached chrome"
    )
    assert aligned["chromePosition"] == "static", (
        "authored div positioning captured the chrome's document coordinate plane"
    )
    assert abs(aligned["dx"]) < 2 and abs(aligned["dy"]) < 2, (
        f"the aim moved {aligned['dx']:.1f}px across and {aligned['dy']:.1f}px down "
    )

    target.click()
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


@pytest.mark.parametrize(
    "width,panel_open", [(1440, False), (1440, True), (390, False)]
)
def test_a_growing_text_comment_keeps_its_passage_clear_without_changing_sides(
    browser, serve, width, panel_open
):
    """A passage and its growing editor remain visible together.

    Without a horizontal rail, the compact field chooses the vertical side with more
    reachable room. It keeps that side while growing and moves the reading region only
    enough to reveal itself. Its trailing actions stay with the last line, and its
    corners keep the first and last line readable after the capsule becomes an editor.
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
    if panel_open:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
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
    if placement in {"top-end", "bottom-end"}:
        assert placement == "bottom-end", (
            "the page has substantially more reachable room below this passage"
        )
    clear = """() => {
          const target = document.getElementById('passage').getBoundingClientRect();
          const field = document.querySelector('.lf-fab-input').getBoundingClientRect();
          return field.right <= target.left || field.left >= target.right
            || field.bottom <= target.top || field.top >= target.bottom;
        }"""
    assert page.evaluate(clear)
    write(field, "test\n")
    actions = page.evaluate(
        """() => {
          const center = selector => {
            const box = document.querySelector(selector).getBoundingClientRect();
            return box.top + box.height / 2;
          };
          return {send: center('.lf-fab-bar .lf-compose-submit'),
                  more: center('.lf-fab-bar > .lf-response-more')};
        }"""
    )
    assert actions["more"] == pytest.approx(actions["send"], abs=1), (
        f"the multiline comment split its trailing controls: {actions}"
    )
    content = "\n".join(
        f"Line {n}: every word of this longer comment needs to remain readable."
        for n in range(20)
    )
    write(field, content)
    expect(field).to_have_js_property("value", content)
    expanded = field.bounding_box()
    assert page.locator(".lf-fab-bar").get_attribute("data-lf-placement") == placement
    assert page.evaluate(clear), (
        "the growing composer covers the passage it comments on"
    )
    assert expanded["width"] > compact["width"]
    assert expanded["height"] > compact["height"] * 5
    assert expanded["x"] >= 0 and expanded["x"] + expanded["width"] <= width
    assert expanded["y"] >= 0 and expanded["y"] + expanded["height"] <= 900
    assert field.evaluate(
        "el => parseFloat(getComputedStyle(el).borderTopLeftRadius)"
    ) <= (compact["height"] / 2)
    if panel_open:
        assert (
            expanded["x"] + expanded["width"]
            < page.locator(".lf-thread-panel").bounding_box()["x"]
        )
    if placement == "bottom-end":
        assert page.evaluate("scrollY") > before_scroll
        revealed_scroll = page.evaluate("scrollY")
        page.mouse.move(8, 450)
        page.mouse.wheel(0, -200)
        page.wait_for_function("before => scrollY < before", arg=revealed_scroll)
        scroll_settled(page)
        assert page.evaluate("scrollY") < revealed_scroll
        expect(page.locator(".lf-fab-bar")).to_have_attribute(
            "data-lf-placement", placement
        )
    page.mouse.move(8, 450)
    page.mouse.wheel(0, 300)
    page.wait_for_function("() => scrollY >= 300")
    expect(field).to_have_js_property("value", content)
    write(field, "Brief")
    expect(field).to_have_js_property("value", "Brief")
    assert field.bounding_box()["height"] == compact["height"]


def test_a_text_comment_chooses_above_when_the_page_has_more_room_there(browser, serve):
    """The stable vertical choice reads both the visible band and scroll travel."""
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
    expect(bar).to_have_attribute("data-lf-placement", "top-end")
    before_scroll = page.evaluate("scrollY")

    write(
        field,
        "\n".join(
            f"Line {line}: the whole comment remains above its passage."
            for line in range(40)
        ),
    )
    rendered(page)
    expect(bar).to_have_attribute("data-lf-placement", "top-end")
    assert page.evaluate("scrollY") < before_scroll
    boxes = page.evaluate(
        """() => {
          const passage = document.getElementById('passage').getBoundingClientRect();
          const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
          return {passageTop: passage.top, barBottom: bar.bottom};
        }"""
    )
    assert boxes["barBottom"] <= boxes["passageTop"], boxes
    float_height = bar.evaluate(
        "node => parseFloat(getComputedStyle(node).getPropertyValue('--lf-float-h'))"
    )
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
        assert bar.evaluate(
            "node => parseFloat(getComputedStyle(node).getPropertyValue('--lf-float-h'))"
        ) == pytest.approx(float_height, abs=1)
        last_scroll = moved
    assert paragraph.evaluate("node => node.getBoundingClientRect().top < 48")
    expect(bar).to_have_attribute("data-lf-placement", "top-end")


def test_a_comment_on_a_scrolled_away_paragraph_keeps_the_column_clear(browser, serve):
    """The block a comment names decides where the field stands, on screen or off it.

    Placement reads that block through the viewport, so a paragraph scrolled clear of
    the viewport has no shown rect left to read. Falling back to the passage there let a
    short selection lend the words after it after all: the field left the free margin,
    crossed into the column, and came to rest on the sentences the user had scrolled
    down to. The column does not move when the page scrolls, so neither may the field.
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
    beside = page.locator(".lf-fab-bar").bounding_box()["x"]

    page.mouse.move(8, 450)
    page.mouse.wheel(0, 900)
    page.wait_for_function("() => scrollY >= 900")
    page.wait_for_function(
        "() => document.getElementById('passage').getBoundingClientRect().bottom < 0"
    )
    scroll_settled(page)

    covered = page.evaluate(
        """() => {
          const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
          return [...document.querySelectorAll('p')]
            .filter(p => {
              const r = p.getBoundingClientRect();
              return r.width && r.height && r.left < bar.right && bar.left < r.right
                && r.top < bar.bottom && bar.top < r.bottom;
            })
            .map(p => p.id);
        }"""
    )
    assert covered == [], f"the field stands on the user's paragraphs: {covered}"
    assert page.locator(".lf-fab-bar").bounding_box()["x"] == beside, (
        "the field left the column it was seated beside when the passage scrolled away"
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
        serve(next(example for example in EXAMPLES if example.stem == "release-notes")),
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
    assert grown["y"] >= 48 and grown["y"] + grown["height"] <= 378, grown

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
    banner = page.locator(".lf-banner").bounding_box()
    ceiling = max(48, banner["y"] + banner["height"] + 6)
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
# Send's top.
SIDE_COMMENT = """() => {
  const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
  const field = document.querySelector('.lf-fab-input');
  const send = document.querySelector('.lf-fab-bar .lf-compose-submit');
  return {top: bar.top, bottom: bar.bottom, field: field.getBoundingClientRect().top,
          height: field.getBoundingClientRect().height, scrolled: field.scrollTop,
          send: send.getBoundingClientRect().top};
}"""


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
    page.locator("#passage").click(modifiers=["Alt"])
    field = open_compact_comment(page)
    expect(field).to_have_js_property("value", "First line\nSecond line\nThird line")
    rendered(page)
    restored = page.evaluate(SIDE_COMMENT)
    assert restored["top"] == pytest.approx(resting["top"], abs=1), restored
    assert restored["bottom"] > resting["bottom"] + 30, restored


def test_a_side_comment_at_the_window_s_foot_rises_only_as_far_as_it_must(
    browser, serve
):
    """With no room left under it, the field rises by what its next line needs, its
    foot on the window's, and scrolls only once it fills the window."""
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
    passage = page.locator("#passage")
    passage.evaluate(
        """node => scrollBy({
          top: node.getBoundingClientRect().top - (innerHeight - 140),
          behavior: 'instant'
        })"""
    )
    rendered(page)
    passage.click(modifiers=["Alt"])
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    assert bar.get_attribute("data-lf-placement") == "right-start"
    resting = page.evaluate(SIDE_COMMENT)
    foot = page.evaluate(
        """async () => (await window.__lfRuntimeImport('/runtime/geometry.js'))
          .shownWindow({gap: 8}).bottom"""
    )
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
    assert compact["y"] > 200, compact
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
    banner = page.locator(".lf-banner").bounding_box()
    ceiling = max(48, banner["y"] + banner["height"] + 6)
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
    resized(page, 511, 320)
    target = page.locator("#target")
    target.click(modifiers=["Alt"], position={"x": 200, "y": 25})
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    assert bar.get_attribute("data-lf-placement") in {"top-end", "bottom-end"}

    write(field, "\n".join(f"Line {n}: keep the draft visible." for n in range(3)))
    page.wait_for_function(
        """() => {
          const field = document.querySelector('.lf-fab-input');
          return field.clientHeight === field.scrollHeight && field.clientHeight > 100;
        }"""
    )

    write(field, "\n".join(f"Line {n}: keep the draft reachable." for n in range(40)))
    page.wait_for_function(
        """() => {
          const field = document.querySelector('.lf-fab-input');
          return field.scrollHeight > field.clientHeight;
        }"""
    )
    banner = page.locator(".lf-banner").bounding_box()
    box = bar.bounding_box()
    ceiling = max(48, banner["y"] + banner["height"] + 6)
    assert box["y"] >= ceiling and box["y"] + box["height"] <= 312, box

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
    banner = page.locator(".lf-banner").bounding_box()
    ceiling = max(48, banner["y"] + banner["height"] + 6)
    assert bounds["y"] <= ceiling and bounds["y"] + bounds["height"] >= 352, (
        "the target must fill the available viewport so no adjacent rail can fit"
    )
    box = field.bounding_box()
    assert box["y"] >= ceiling and box["y"] + box["height"] <= 352, box
    assert field.evaluate("node => node.scrollHeight > node.clientHeight")


TALL_DIFF_PAGE = leaf_page(
    "A tall diff",
    '<h1>Review</h1><p>One file, commented on whole.</p><lf-diff id="whole"><pre>'
    "diff --git a/src/lib.rs b/src/lib.rs\n--- a/src/lib.rs\n+++ b/src/lib.rs\n"
    "@@ -0,0 +1,80 @@\n"
    + "\n".join(f"+    let value_{n} = compute({n});" for n in range(80))
    + "\n</pre></lf-diff><p>After the diff.</p>",
)
# Where the pointed row, the comment box and the margin cluster stand in the window.
POINTED_ROW = """() => {
  const row = document.querySelector('lf-diff').shadowRoot
    .querySelectorAll('[data-line]')[50].getBoundingClientRect();
  const top = (selector) =>
    document.querySelector(selector)?.getBoundingClientRect().top ?? null;
  return { row: row.top, height: row.height, bar: top('.lf-fab-bar'),
           cluster: top('.lf-margin-cluster'), card: top('.lf-margin-preview'),
           diff: document.querySelector('lf-diff').getBoundingClientRect().top };
}"""


def test_a_comment_on_a_whole_target_stands_by_the_row_it_was_pointed_at(
    browser, serve
):
    """⌥-clicking a line deep in an unbound diff comments on the whole diff, which is
    the target the registry gives it, but the user pointed at that line. The box to
    write in, the cluster the sent comment leaves and the card it opens stand level with
    it rather than at the diff's top, a screen above; `t` travels back to that row. The
    event still names the whole diff: where the comment stands is presentation."""
    page = open_page(browser, serve(TALL_DIFF_PAGE))
    resized(page, 1440, 900)
    expect(page.locator("lf-diff.lf-rendered")).to_have_count(1)
    row = page.locator("lf-diff [data-line]").nth(50)
    row.scroll_into_view_if_needed()
    rendered(page)
    row.click(modifiers=["Alt"], position={"x": 60, "y": 5})
    field = open_compact_comment(page)
    rendered(page)
    at = page.evaluate(POINTED_ROW)
    assert at["diff"] < -at["height"] * 20, f"the diff's top must be off screen: {at}"
    assert abs(at["bar"] - at["row"]) <= 2 * at["height"], (
        f"the comment box stands {at['row'] - at['bar']:.0f}px from the row: {at}"
    )

    write(field, "Why this line?")
    with sending(page, "the comment on the whole diff"):
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


TALL_ASK_PAGE = leaf_page(
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


@pytest.mark.parametrize("case", ["ask", "thread"])
def test_a_pointed_comment_moves_only_its_own_row(browser, serve, case):
    """A comment pointed at a row deep in its target stands its own margin row there;
    the rest of the target's margin does not follow it. An Ask's marker stays with the
    Ask it accompanies, and a comment already on the target stays at the target's top,
    where `t` still lands it."""
    if case == "ask":
        url, target = serve(TALL_ASK_PAGE), "way"
        row = f"#{target} p >> nth=25"
    else:
        url, target = serve(TALL_DIFF_PAGE), "whole"
        first = events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "The whole diff first.",
                "anchor": {"section": "whole"},
            },
        )["id"]
        row = "lf-diff [data-line] >> nth=50"
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
    for index, top in before:
        assert abs(after.get(index, 1e9) - top) <= 8, (
            f"row {index} of the target moved from {top} to {after.get(index)}: {after}"
        )
    added = [top for index, top in after.items() if index not in dict(before)]
    assert len(added) == 1 and abs(added[0] - depth) <= 30 and depth > 400, (
        f"the pointed comment has no row of its own at {depth}: {after}"
    )
    if case == "thread":
        # The walk reaches the thread already there at the target's top, in page order
        # before the pointed one.
        page.keyboard.press("t")
        shown = page.locator(".lf-margin-preview .lf-page-thread")
        expect(shown).to_have_count(1)
        if shown.get_attribute("data-thread") != first:
            page.keyboard.press("Shift+t")
        expect(shown).to_have_attribute("data-thread", first)
        scroll_settled(page)
        rendered(page)
        card = page.locator(".lf-margin-preview").bounding_box()
        top = page.locator("#whole").bounding_box()["y"]
        assert abs(card["y"] - top) <= 60, (card, top)


def test_a_pointed_comment_finds_its_row_again_after_a_revision_rewrites_it(
    browser, serve
):
    """A revision that rewrites the diff replaces every row the comment was pointed at.
    The comment's row keeps its place by the words of the row it was pointed at, which
    the new rendering still holds, rather than falling back to the diff's top."""
    page = open_page(browser, live_url(serve(TALL_DIFF_PAGE)))
    resized(page, 1440, 900)
    expect(page.locator("lf-diff.lf-rendered")).to_have_count(1)
    row = page.locator("lf-diff [data-line]").nth(50)
    row.scroll_into_view_if_needed()
    rendered(page)
    row.click(modifiers=["Alt"], position={"x": 60, "y": 5})
    write(open_compact_comment(page), "Why this line?")
    with sending(page, "the pointed comment"):
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    rendered(page)
    page.evaluate(
        "() => { window.__row = document.querySelector('lf-diff').shadowRoot"
        ".querySelectorAll('[data-line]')[50]; }"
    )

    (serve.page_dir / "index.html").write_text(
        TALL_DIFF_PAGE.replace("A tall diff", "A tall diff, revised").replace(
            "compute(3);", "compute(3 + 0);"
        )
    )
    told(page)
    expect(page).to_have_title("A tall diff, revised")
    page.wait_for_function(
        "() => { const rows = document.querySelector('lf-diff').shadowRoot"
        ".querySelectorAll('[data-line]'); return rows.length === 80"
        " && rows[50] !== window.__row; }"
    )
    rendered(page)
    at = page.evaluate(POINTED_ROW)
    assert abs(at["cluster"] - at["row"]) <= at["height"], (
        f"the revision took the comment's row {at['row'] - at['cluster']:.0f}px from"
        f" the row it was pointed at: {at}"
    )


def point_a_comment(page, text, x=60):
    """⌥-click row 51 of the tall diff at `x` and send `text`, leaving the card."""
    row = page.locator("lf-diff [data-line]").nth(50)
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
    stands by is its row: the diff around it still overlaps the window, so bringing the
    diff into view moved nothing and left the reply below the window."""
    page = open_page(browser, serve(TALL_DIFF_PAGE))
    resized(page, 1440, 900)
    expect(page.locator("lf-diff.lf-rendered")).to_have_count(1)
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
    at the line, as two comments on the diff's own top share its row; the row the first
    made is the one the second joins."""
    page = open_page(browser, serve(TALL_DIFF_PAGE))
    resized(page, 1440, 900)
    expect(page.locator("lf-diff.lf-rendered")).to_have_count(1)
    point_a_comment(page, "First about this line.", x=60)
    first = page.evaluate(ROWS_ON, ["whole"])
    point_a_comment(page, "Second about this line.", x=200)
    second = page.evaluate(ROWS_ON, ["whole"])
    assert len(first) == 1 and second == first, (
        f"the second comment made a margin row of its own: {first} then {second}"
    )


def test_a_pointed_row_is_announced_where_it_stands_and_by_its_words(browser, serve):
    """A listener places a margin row by how far down the page it is and tells rows
    apart by their names. A pointed row stands two-thirds of the way down the diff, and
    it is named by the line it stands by, not only by the diff the target's own row
    names."""
    page = open_page(browser, serve(TALL_DIFF_PAGE))
    resized(page, 1440, 900)
    expect(page.locator("lf-diff.lf-rendered")).to_have_count(1)
    point_a_comment(page, "Why this line?")
    spoken = page.evaluate(
        """() => {
          const main = document.querySelector('main');
          const row = document.querySelector('lf-diff').shadowRoot
            .querySelectorAll('[data-line]')[50].getBoundingClientRect();
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
    assert "let value_50 = compute(50);" in spoken["name"], spoken


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
    # it joins that row, an Ask's marker's, rather than standing pushed below it.
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


def test_a_reflow_keeps_a_pointed_comment_in_its_row_and_its_card_open(browser, serve):
    """Which margin row a pointed comment stands in is the document's to say, so a
    reflow that moves its line further from the target's top moves the row with it and
    changes nothing else: the row is the same element, and the card the user is
    writing in stays up with the words and the focus in it."""
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

    resized(page, 560, 900)
    rendered(page)
    assert first.bounding_box()["height"] > one_line * 1.5, (
        "the opening line must wrap for the reflow to move the pointed line"
    )
    after = page.evaluate(ROWS_ON, ["s"])
    assert [index for index, _ in after] == [index for index, _ in rows], (
        f"the reflow moved the comment to another margin row: {rows} then {after}"
    )
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Still writing")


def test_undoing_a_settle_brings_a_pointed_comment_back_to_its_row(browser, serve):
    """Settling a pointed comment and taking that back returns it where it stood, next to
    its line, whatever else is open on the target."""
    url = serve(TALL_DIFF_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Another thread, still open on the diff.",
            "anchor": {"section": "whole"},
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 1440, 900)
    expect(page.locator("lf-diff.lf-rendered")).to_have_count(1)
    point_a_comment(page, "Why this line?")
    pointed = page.evaluate(ROWS_ON, ["whole"])
    assert len(pointed) == 2, pointed
    root = events_model.read_events(serve.page_dir)[-1]
    assert root["kind"] == "comment", root
    settle = events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    told(page)
    rendered(page)
    assert len(page.evaluate(ROWS_ON, ["whole"])) == 1
    events_model.append_event(
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
        serve(next(example for example in EXAMPLES if example.stem == "release-notes")),
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
    assert placement in {"top-end", "bottom-end"}, placement

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
        serve(next(example for example in EXAMPLES if example.stem == "release-notes")),
    )
    resized(page, 700, 600)
    target = page.locator("#rn-console-why")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"], position={"x": 20, "y": 10})
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    rendered(page)
    placement = bar.get_attribute("data-lf-placement")
    assert placement in {"top-end", "bottom-end"}, placement
    empty = bar.bounding_box()
    draft = "A draft long enough that its own width would widen the bar it opens in."
    write(field, draft)
    rendered(page)

    page.reload()
    wait_until_ready(page)
    expect(field).to_have_js_property("value", draft)
    expect(bar).to_have_attribute("data-lf-placement", placement)
    rendered(page)
    restored = bar.bounding_box()
    assert abs(restored["x"] - empty["x"]) <= 1, (empty, restored)


def test_a_side_comment_rechooses_its_rail_after_horizontal_target_motion(
    browser, serve
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

    target.evaluate("node => { node.style.transform = 'translateX(600px)' }")
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


def test_an_above_comment_rechooses_after_vertical_target_motion(browser, serve):
    """Moving the reference across the block axis opens a better attachment side."""
    page = open_page(
        browser,
        serve(next(example for example in EXAMPLES if example.stem == "release-notes")),
    )
    resized(page, 700, 600)
    target = page.locator("#rn-console-why")
    target.scroll_into_view_if_needed()
    target.click(modifiers=["Alt"], position={"x": 20, "y": 10})
    field = open_compact_comment(page)
    write(field, "Keep this comment connected when its paragraph moves vertically.")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("aria-label", re.compile(r"^Respond to paragraph"))
    expect(bar).to_have_attribute("data-lf-placement", "top-end")

    target.evaluate(
        """node => {
          node.style.transform = 'translateY(-180px)';
        }"""
    )
    resized(page, 700, 601)
    expect(bar).to_have_attribute("data-lf-placement", "bottom-end")
    target_after = target.bounding_box()
    after = bar.bounding_box()
    assert after["y"] >= target_after["y"] + target_after["height"] + 5, (
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
    legend = page.locator('.lf-legend-box[data-for="p30"]')
    expect(legend).to_be_visible()

    before = page.evaluate(
        """() => {
          const target = document.getElementById('p30').getBoundingClientRect();
          const legend = document.querySelector('.lf-legend-box[data-for="p30"]')
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
          const legendBox = document.querySelector('.lf-legend-box[data-for="p30"]')
            .getBoundingClientRect();
          return {targetTop: targetBox.top, dx: legendBox.left - targetBox.left,
                  dy: legendBox.top - targetBox.top};
        }"""
    )
    assert after["targetTop"] - before["targetTop"] > 140
    assert abs(after["dx"] + 1) < 2 and abs(after["dy"] + 1) < 2, (
        f"the legend did not follow height-only page growth: {before} then {after}"
    )


def test_a_covering_auxiliary_surface_holds_design_paint_beneath_it(browser, serve):
    """A covering auxiliary surface owns its pixels, and in Design mode stays Leaf's.

    Covered page content is inert, so neither the aim nor a design comment reaches it
    through the visible remainder, and the page's standing design legend paints beneath
    the sheet. The sheet itself is Leaf's chrome, which the mode leaves working: nothing
    on it is a design target, and a press on its scrim puts it away as it would outside
    the mode, which is how a phone the sheet covers gets back to its page.
    """
    page = open_page(browser, serve(ASKS_PAGE))
    resized(page, 700, 900)
    banner_control(page, ".lf-asks").click()
    edge_settled(page, EDGES[1])
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    resized(page, 560, 900)
    drawer = page.locator(".lf-asks-panel")
    expect(drawer).to_be_visible()

    target = page.locator("#lq-keep")
    target_box = target.bounding_box()
    assert target_box is not None and target_box["x"] + target_box["width"] > 320
    point = {
        "x": target_box["x"] + target_box["width"] - 18,
        "y": target_box["y"] + target_box["height"] / 2,
    }
    page.mouse.move(point["x"], point["y"])
    expect(page.locator(".lf-aim")).to_be_hidden()
    drawer_box = drawer.bounding_box()
    assert drawer_box is not None
    page.mouse.move(drawer_box["x"] + 12, drawer_box["y"] + 12)
    expect(page.locator(".lf-aim")).to_be_hidden()
    planes = page.evaluate(
        """() => ({
          drawer: Number(getComputedStyle(document.querySelector('.lf-asks-panel')).zIndex),
          legend: Number(getComputedStyle(
            document.querySelector('.lf-legend-box[data-for="lq-keep"]')).zIndex),
        })"""
    )
    assert planes["legend"] < planes["drawer"], planes

    page.mouse.click(point["x"], point["y"])
    expect(drawer).not_to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")


def test_a_margin_label_covers_the_target_trace(browser, serve, monkeypatch):
    """A transient chrome label paints above the page-level trace it summons."""
    single = ASK_PAGE.replace(
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
    for clock_owner in (served_page, events_model, service_model):
        monkeypatch.setattr(clock_owner, "now_iso", lambda: advanced)
    session_model.cmd_status(page_dir, "idle", "")
    told(page)

    marker = page.locator('[data-lf-margin-for="jobs"] > .lf-margin-marker')
    expect(marker).to_have_attribute("aria-label", re.compile(r"^Waiting for pickup,"))
    marker.hover()
    label = marker.locator(":scope > .lf-margin-entry-label")
    trace = page.locator('.lf-target-trace[data-for="jobs"]')
    expect(label).to_be_visible()
    expect(trace).to_be_visible()
    label.evaluate(
        "node => Promise.all(node.getAnimations().map(animation => animation.finished))"
    )

    label_box = label.bounding_box()
    trace_box = trace.bounding_box()
    assert (
        label_box["x"]
        < trace_box["x"] + trace_box["width"]
        < label_box["x"] + label_box["width"]
    ), "the status label does not cross the target trace"
    traced = Image.open(io.BytesIO(label.screenshot())).convert("RGB")
    trace.evaluate("node => { node.style.visibility = 'hidden' }")
    untraced = Image.open(io.BytesIO(label.screenshot())).convert("RGB")
    center = (3, 3, traced.width - 3, traced.height - 3)
    assert (
        ImageChops.difference(traced.crop(center), untraced.crop(center)).getbbox()
        is None
    ), "the target trace paints over the status label"


def test_the_aim_reads_the_pointer_where_the_press_is_dispatched_from(browser, serve):
    """The outline and the press ask one question of one point, down to the sub-pixel.

    The two readings of "what is under the pointer" come from different doors: the
    outline hit-tests the pointer record the runtime keeps, and the press takes the
    target the browser resolved for it. `mousemove` carries the pointer's place rounded
    to a whole pixel, so a record kept from one is an answer about a place the pointer is
    not — and within a pixel of a seam that place is a different item. It cost a corpus
    page a promise: ⌥ over a choose group outlined the option above the seam and the
    press commented on the one below it, which is the composer opening on an item the
    user was never shown.

    So the aim is put within a quarter pixel of a seam, where the true point and its
    rounded twin name different items. Which of the two the true point is over depends on
    where in the pixel the seam fell, so the item the aim is held to is read off the point
    rather than named here; what is asserted first is that the two readings differ at all,
    since a seam that fell on a whole pixel would leave this proving that two agreeing
    readings agree."""
    page = open_page(browser, serve(AIM_SEAM_PAGE))
    seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
    assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
        "the fixture no longer straddles a seam — the aim point and the whole pixel it "
        "rounds to are not on the two items either side of it, so nothing here is under "
        f"test: {seam}"
    )

    page.mouse.move(seam["x"], seam["y"])
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", seam["at"])
    page.mouse.click(seam["x"], seam["y"])
    page.keyboard.up("Alt")

    # The press focuses Comment on the item the aim held.
    open_compact_comment(page)
    assert page.evaluate(DRAFT_MARK) == seam["at"]


def test_an_aimed_first_press_records_its_pointer_before_claiming_it(browser, serve):
    """A press can be the first pointer event, and capture still reads its position.

    Aim claims pointerdown during capture and stops the gesture before it reaches the
    page. The shared position recorder therefore has to run earlier in that same phase:
    a bubble listener never sees this event, and aim would ask about the stale initial
    point instead of the paragraph the browser dispatched the press to.
    """
    page = open_page(browser, serve(LONG_PAGE))
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


@pytest.mark.parametrize(
    ("case_name", "example", "required_paths"),
    AIM_PRESS_CASES,
    ids=[case[0] for case in AIM_PRESS_CASES],
)
def test_an_aimed_press_does_only_what_the_outline_promised(
    browser, serve, case_name, example, required_paths
):
    """⌥-click takes the addressable element under the pointer, and that is the whole of what it does.

    Holding ⌥ outlines what a click would take, which is a promise about the next press.
    The runtime used to read that press on the way back up, after every handler out on the
    page had already had it, so the press kept the promise and did something else besides:
    ⌥-clicking an option card opened the composer *and* picked the option, sending Claude a
    decision the user never made, while ⌥-clicking a tab's name aimed at the widget and
    switched the panel under it. Neither shows in the composer, which opens either way.

    So both halves are asserted together — the composer opens on the item that was
    outlined, and the page is exactly as it was, in its markup and in where its focus
    sits. The capture mechanism is layer-wide; these pages are retained for the distinct
    downstream paths they put under it rather than for every repetition of those paths.
    `required_paths` keeps that causal selection honest when an example changes.
    """
    url = serve(example)
    page = open_page(browser, url)
    # What the log already held. A shipped seed can carry a decision the user made
    # before this page was opened, and what an aim may not do is add one of its own —
    # so the reading below is against this rather than against nothing.
    standing = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ]
    # A suggestion's ✓/✗ stands in the margin layer, which is chrome and no aim target,
    # but a press there is one the page answers, so the sweep takes it as well.
    targets = (
        f"{aim_targets(serve.page_dir)}, "
        ".lf-margin-cluster :is(.lf-sug-accept, .lf-sug-reject)"
    )
    total = page.locator(targets).count()
    pressed = aimed = 0
    reached_paths = set()
    for i in range(total):
        # A control inside a fold or behind an unopened tab is nowhere a user can aim,
        # which is the press sweep's reading of the same question, and a point the banner
        # or a neighbour covers is not this target's press at all.
        target = page.locator(targets).nth(i)
        if not target.is_visible():
            continue
        # A wrapper with no box of its own — one a page's style leaves
        # display: contents — is nowhere a user can aim (AIM_POINT finds no point
        # in it either), and
        # scroll_into_view can wait on its stability forever when it stands inside
        # a table box (a sample). Its slots are their own targets.
        if not target.evaluate("el => el.getClientRects().length"):
            continue
        target.scroll_into_view_if_needed()
        point = target.evaluate(AIM_POINT)
        if not point:
            continue
        target_paths = set(
            target.evaluate(
                """el => [
                  [el.matches('[role=tab]'), 'tab click'],
                  [el.matches('.lf-pick') || !!el.closest('lf-option'), 'option click'],
                  [el.matches('lf-draft') || !!el.closest('lf-draft'),
                   'draft mousedown'],
                  [el.matches('.lf-sug-accept, .lf-sug-reject'),
                   'suggestion control'],
                ].filter(([reached]) => reached).map(([, name]) => name)"""
            )
        )
        reached_paths.update(target_paths - {"suggestion control"})
        label = target.evaluate(NAMED)
        before = page.evaluate(PAGE_MARKUP)
        page.mouse.move(*point)
        page.keyboard.down("Alt")
        promised = page.evaluate(AIMED)
        # The cursor is the other half of the same promise, and it is derived from the
        # same value the outline is: the hand where a press takes something, the arrow
        # where it takes nothing. Read off body, which is where the aim declares it —
        # a widget's own control still states its resting cursor, and does so whether or
        # not the key is down.
        assert page.evaluate(AIM_CURSOR) == ("pointer" if promised else "default"), (
            f"holding ⌥ over {label} in {case_name} promised {promised} and pointed "
            f"a {page.evaluate(AIM_CURSOR)} cursor at it"
        )
        # An element a standing thread already marks, read before the press marks it
        # as the draft's too.
        already_marked = bool(
            promised and page.locator(f"#{promised}.lf-mark-el").count()
        )
        page.mouse.click(*point)
        page.keyboard.up("Alt")
        composer = page.locator(".lf-composer")
        bar = page.locator(".lf-fab-bar")
        if "suggestion control" in target_paths and promised:
            # A suggestion's ✓ Accept stands in the margin layer over the page, and a
            # press let through there would send Claude a decision. The aim takes it as
            # a press on the change it stands by, which the markup reading below holds.
            reached_paths.add("suggestion margin control")
        if promised is None:
            # Nothing outlined is nothing to aim at — no item encloses this point — and an
            # armed press then acts on nothing rather than falling back to the page.
            expect(bar).to_be_hidden()
            expect(composer).to_be_hidden()
        else:
            # The sequence promised Comment, so the press focuses its compact field.
            open_compact_comment(page)
            mark = page.evaluate(DRAFT_MARK)
            # A standing thread draws nothing on its element at rest, so a draft on an
            # element the log already marks wears the pending contour like any other.
            if already_marked:
                reached_paths.add("standing mark")
            assert mark == promised, (
                f"⌥-clicking {label} in {case_name} promised {promised} and "
                f"commented on {mark}"
            )
            # And the promise is kept where the user can see it kept. An outline needs
            # a box, and an item that draws none — every suggestion is display: contents —
            # would take the mark to 0x0 at the document's origin, showing nothing. The
            # composer places itself off this same record, so it would go to the top of
            # the window along with it, beside a passage it is no longer beside.
            unshown = page.evaluate(
                """() => [...document.querySelectorAll('.lf-mark-el.lf-pending')]
                   .filter(e => { const b = e.getBoundingClientRect();
                                  return !(b.width && b.height); })
                   .map(e => e.tagName.toLowerCase())"""
            )
            assert not unshown, (
                f"⌥-clicking {label} in {case_name} outlined {unshown}, which draws "
                "no box, so the promise is invisible and the composer stands off a rect "
                "at the top of the document"
            )
            # Put the composer away before reading the page back: its own passage wears
            # the outline, which is the one mark an aim is supposed to leave.
            page.keyboard.press("Escape")
            expect(composer).to_be_hidden()
            aimed += 1
        assert page.evaluate(PAGE_MARKUP) == before, (
            f"⌥-clicking {label} in {case_name} changed the page, so a press the aim "
            "had taken reached a widget as well"
        )
        assert not page.evaluate(FOCUS_IN_PAGE), (
            f"⌥-clicking {label} in {case_name} left the focus on the page, so the "
            "press reached the control under it"
        )
        pressed += 1
    assert pressed, f"{case_name} pressed nothing, so it asserts nothing"
    # And that the outline is still painted at all: a preview that stopped appearing would
    # leave every press above asserting only that nothing happened, which is the shape of
    # vacuous pass this sweep is most exposed to.
    assert aimed, f"{case_name} outlined nothing, so no press was held to a promise"
    assert reached_paths >= required_paths, (
        f"{case_name} no longer exercises the paths that earned its place in the "
        f"aim corpus: missing {sorted(required_paths - reached_paths)}, reached "
        f"{sorted(reached_paths)}"
    )
    # The other half of "did nothing else", and the half the markup cannot show: a widget
    # that acts tells Claude so, and a decision the user never made is worse in the log
    # than on the page. The wait is the page's own sends coming back, so a stray one is in
    # the log to be read rather than still in flight.
    round_trip(page)
    assert [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == standing, (
        f"⌥-clicking through {case_name} left a decision in the log that the aim "
        "never promised"
    )


def test_an_aim_on_a_seam_promises_and_takes_the_same_element(browser, serve):
    """One reading, at the one place the pointer is.

    The cells of a joined group butt, so two of them share an edge with no gap between,
    and a pointer resting on it is inside both by the width of a rounding. The outline
    and the press each used to hit-test that point for themselves — elementFromPoint
    against the browser's own dispatch — and nothing makes two hit tests tie-break a
    shared edge alike. What a user got was one option outlined and the next one
    commented on.

    The sweep over the corpus reaches this case only where the page happens to put a
    seam under the point it picks, which is a fact about font metrics: the same aim was
    a cell's interior on one platform and a seam on another, and the corpus said the
    promise was kept for a year on the machine where it was. So the seam is aimed at
    here rather than waited for, and the assertion is the platform-independent half —
    whichever way each reading rounds, both answer the same item."""
    page = open_page(browser, serve(SAMPLE_PAGE))
    edge = page.evaluate(
        """() => {
            const above = document.querySelector('#l-shim').getBoundingClientRect();
            const below = document.querySelector('#l-stage').getBoundingClientRect();
            return {y: above.bottom, apart: Math.abs(below.top - above.bottom),
                    x: above.left + above.width / 2};
        }"""
    )
    assert edge["apart"] < 0.5, (
        f"the cells stand {edge['apart']}px apart, so this aims at a gap and not at the "
        "seam the two readings can differ over"
    )
    page.mouse.move(edge["x"], edge["y"])
    page.keyboard.down("Alt")
    promised = page.evaluate(AIMED)
    assert promised in ("l-shim", "l-stage"), (
        f"the aim promised {promised} on the seam between the two cells, so the reading "
        "under test never happened"
    )
    page.mouse.click(edge["x"], edge["y"])
    page.keyboard.up("Alt")
    # The press focuses Comment on what it took.
    open_compact_comment(page)
    assert page.evaluate(DRAFT_MARK) == promised, (
        f"the outline promised {promised} on the seam and the press commented on "
        f"{page.evaluate(DRAFT_MARK)}"
    )


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
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "t")
    page.reload()
    wait_until_ready(page)
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)  # the latch is gone
    heading.hover()  # the first move under the still-held key
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "t")
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
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    expect(reference.locator('tr[data-lf-command="aim.comment"]')).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")

    # The mode shows what is on the page rather than waiting for the pointer: a legend
    # box on every item, and on every item but a widget's parts its name — the group
    # is named, its options wear the hairline alone and are named under the pointer.
    def box_of(element_id):
        return page.locator(f'.lf-legend-box[data-for="{element_id}"]')

    expect(box_of("t")).to_be_visible()
    assert set(
        page.eval_on_selector_all(".lf-legend-box", "bs => bs.map(b => b.dataset.for)")
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
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "opt-shim")
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
    # on the thread in the ordinary Threads panel.
    panel = page.locator(".lf-thread-panel")
    expect(panel).to_be_visible()
    expect(panel.locator(".lf-thread .lf-quote")).to_have_text(
        "design · lf-option · opt-shim"
    )
    expect(panel.locator(".lf-thread > .lf-thread-summary")).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    # Escape leaves the thread for the whole panel, then the page. The mode they put
    # on before either surface comes off last.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(page.locator("body")).to_be_focused()
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
    expect(page.locator(".lf-inspect")).to_be_hidden()
    expect(page.locator(".lf-legend-box")).to_have_count(0)


def test_design_mode_owns_every_platform_control_from_the_shared_boundary(
    browser, serve
):
    """Design mode captures controls from the runtime's full platform list.

    A slider nested in an ordinary section has no widget tag or native element name to
    put it on a smaller selector. Its ARIA role must still become the named design part.
    An unnamed disclosure is the fail-closed control: even without a durable comment
    target, its activation must not leak through the active mode.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "design controls",
                '<h1>Controls</h1><section id="volume">'
                '<span role="slider" tabindex="0" aria-label="Volume" '
                'aria-valuemin="0" aria-valuemax="100" aria-valuenow="50">50</span>'
                "</section>"
                "<details><summary>More controls</summary><p>Hidden</p></details>",
            )
        ),
    )
    page.keyboard.press("l")
    slider = page.get_by_role("slider", name="Volume")
    slider.hover()
    expect(page.locator(".lf-inspect")).to_have_text("Volume · section · volume")
    page.keyboard.down("Alt")
    expect(page.locator(".lf-inspect")).to_have_text("Volume · section · volume")
    page.keyboard.up("Alt")
    slider.click()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "design · Volume · section · volume"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    disclosure = page.locator("details")
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


def test_design_mode_comments_on_a_margin_action_without_performing_it(browser, serve):
    """A hoisted target control remains a design target, not a live action.

    Margin actions stand beside the readable column rather than inside the widget they
    act on. Design mode still has to name the underlying widget and take the pointer
    press before the action starts; otherwise Accept sends while the composer opens
    nowhere.
    """
    page = open_page(browser, serve(SUGGESTION_PAGE))
    resized(page, 1440, 900)
    page.keyboard.press("l")
    accept = page.locator('[data-lf-margin-for="sug-refill"] .lf-sug-accept')
    expect(accept).to_be_visible()

    accept.hover()
    expect(page.locator(".lf-inspect")).to_have_text(
        re.compile(r"^Accept .* · lf-suggestion · sug-refill$")
    )
    accept.click()

    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        re.compile(r"^design · Accept .* · lf-suggestion · sug-refill$")
    )
    assert page.locator("#sug-refill").get_attribute("aria-busy") is None, (
        "the margin entry action started while Design mode was opening its comment"
    )
    round_trip(page)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["widget"] == "sug-refill"
    ], "the margin entry action reached the durable log despite Design mode"
    page.close()

    # The same hoist exists inside frozen markup in a thread. Its target belongs
    # to that thread document, so the margin owner hands Design mode the exact
    # element rather than making it reconstruct ownership from a diagnostic id or path.
    url = serve(leaf_page("inline margin entry action", '<h1 id="h">Review</h1>'))
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-inline-margin",
            "author": "user",
            "revision": 1,
            "text": "Show me the proposed wording.",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-inline-margin",
            "revision": 1,
            "text": "Here is the change:",
            "markup": (
                '<lf-suggestion id="reply-suggestion">'
                "<lf-old>Keep the long label.</lf-old>"
                "<lf-new>Use the short label.</lf-new>"
                "</lf-suggestion>"
            ),
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator('.lf-thread[data-id="c-inline-margin"] .lf-thread-summary').click()
    page.keyboard.press("l")
    accept = page.locator('[data-lf-margin-for="reply-suggestion"] .lf-sug-accept')
    expect(accept).to_be_visible()

    accept.click()

    expect(page.locator("#lf-composer-quote")).to_have_text(
        re.compile(r"^design · Accept .* · lf-suggestion · reply-suggestion$")
    )
    round_trip(page)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["widget"] == "reply-suggestion"
    ], "the inline margin entry action reached the durable log despite Design mode"


def test_design_mode_leaves_the_chrome_working(browser, serve):
    """Design mode comments on what the agent made; Leaf's own chrome works as it does
    outside the mode, as it does for the target picker.

    A remark on the banner or a panel has no reader who can act on it, and a mode that
    took the chrome took the way out of the panel its own send opened: on a phone that
    panel covers the page, the banner goes inert under it, and its close was a comment.
    So under the mode the Threads button opens the panel rather than a composer, nothing
    under the pointer promises a comment there, the panel's edge draws it wider, and its
    close closes it."""
    edge = EDGES[0]
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

    threads = page.locator(".lf-banner .lf-threads-toggle")
    threads.hover()
    expect(page.locator(".lf-inspect")).to_be_hidden()
    threads.click()
    panel = page.locator(".lf-thread-panel")
    panel_settled(page)
    expect(panel).to_be_visible()
    expect(composer).to_be_hidden()

    standing = geometry(page, edge)
    draw_edge(page, edge, 160)
    held = geometry(page, edge)
    assert held["width"] > standing["width"] and held["chosen"], (
        f"the mode took the edge rather than drawing it: {standing} then {held}"
    )
    expect(composer).to_be_hidden()

    panel.get_by_role("button", name="Close threads").click()
    expect(panel).to_be_hidden()
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    assert comments() == seeded, "a press on the chrome posted a comment"


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
            "<pre></pre></lf-diff>",
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
    root = events_model.append_event(
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
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root["id"]}"]')
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
        events_model.append_event(
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
    expect(page.locator('[data-lf-margin-for="reacted"] .lf-react-mark')).to_have_count(
        1
    )
    expect(page.locator("#commented.lf-mark-el")).to_have_count(1)
    page.keyboard.press("l")
    expect(page.locator('.lf-legend-box[data-for="reacted"]')).to_be_visible()
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
    expect(page.locator('.lf-legend-box[data-for="approach"]')).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
    page.reload()
    wait_until_ready(page)
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")


def test_the_legend_follows_the_page_it_is_a_reading_of(browser, serve):
    """A legend box kept from a previous reading is a claim about a page that has moved.

    Three of the doors that move it: the page scrolling (items come on screen with no
    box yet, and the boxes are drawn in document space), the panel opening (the column
    re-centres, every block reflows, and no scroll or replay says so — each item's own
    resize does), and the name under the pointer, which is drawn beside the box in the
    same space: it sat in viewport space once, with the scroll added on top, and stood a
    screen below its box on any page scrolled at all. The aim is one more of the
    chrome's promises over the same page, so the reflow doors repaint it too
    (pageShifted): it once kept its old coordinates through the panel's column motion, a box
    and name floating half a panel to the right of the element they claimed."""
    page = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("l")
    page.wait_for_function(LEGEND_TRUE)
    page.evaluate("() => { document.scrollingElement.scrollTop = 1200; }")
    p = page.locator("#p20")
    expect(p).to_be_in_viewport()
    expect(page.locator('.lf-legend-box[data-for="p20"]')).to_be_visible()
    page.wait_for_function(LEGEND_TRUE)
    # The name floats where the box's tag stood, over the item's corner — on a scrolled
    # page as on a fresh one.
    p.hover()
    expect(page.locator(".lf-inspect")).to_have_text("paragraph · p20")
    box = page.locator(".lf-aim").bounding_box()
    name = page.locator(".lf-inspect").bounding_box()
    assert abs(name["y"] + name["height"] - box["y"]) < 4, (name, box)
    assert abs(name["x"] - box["x"]) < 4, (name, box)
    # The panel stands over the right of the page, and each box ends where the panel
    # begins. Opened by key: in the mode a press on the Threads button is a comment
    # about the button.
    page.keyboard.press("c")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    page.wait_for_function(LEGEND_TRUE)
    # The legend's repaint above consumed the reflow's edge, and the aim was refreshed
    # in the same pageShifted, so one plain read is the settled answer: the pointer
    # still rests in p20, and the promise is about where p20 stands now.
    aim = page.evaluate(
        """() => {
      const b = document.querySelector('.lf-aim');
      const it = document.getElementById(b.dataset.for);
      const r = it.getBoundingClientRect();
      const bb = b.getBoundingClientRect();
      return { on: b.dataset.for, dx: bb.left - r.left, dy: bb.top - r.top };
    }"""
    )
    assert aim["on"] == "p20" and abs(aim["dx"]) < 2 and abs(aim["dy"]) < 2, aim


def test_two_names_at_one_corner_step_apart(browser, serve):
    """A block whose top-left corner is also its container's — the paragraph's margin
    collapses out of the section, exactly the shape a suggestion and the block it wraps
    make — wrote both tags onto one spot, and the longer peeked out past the shorter at
    both ends as fragments of a word nobody wrote. The later tag steps away by tag
    heights until it stands clear."""
    page = open_page(browser, serve(CORNER_PAGE))
    page.keyboard.press("l")
    expect(
        page.locator('.lf-legend-box[data-for="wrap"] .lf-legend-tag')
    ).to_be_visible()
    expect(
        page.locator('.lf-legend-box[data-for="inner"] .lf-legend-tag')
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
    node = page.locator("#flow svg g[data-id]").first
    expect(node).to_be_visible()
    node.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "flow")
    page.keyboard.up("Alt")
    page.keyboard.press("l")
    assert set(
        page.eval_on_selector_all(".lf-legend-box", "bs => bs.map(b => b.dataset.for)")
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
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "fig-drawer")
    page.keyboard.up("Alt")
    page.locator("#fig svg > rect").hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "fig")
    page.keyboard.up("Alt")

    drawer.click(modifiers=["Alt"], position=corner)
    open_compact_comment(page, "wider")
    with sending(page, "the comment on the drawer"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["anchor"] == {"section": "fig-drawer"}


def test_a_visual_part_aim_follows_its_drawn_svg_shape(browser, serve):
    """A visual part's rendered SVG supplies its contour without a package contract.

    A diamond leaves the four corners of that box empty. The armed pixel diff must do
    the same while still washing the shape's middle, which distinguishes the rendered
    contour from a rectangle that merely has the same dimensions.
    """
    from PIL import Image, ImageChops

    diamond_page = PART_DIAGRAM_PAGE.replace("S[Start request]", "S{Start request}", 1)
    page = open_page(browser, serve(diamond_page))
    diamond = page.locator('#flow g[data-id="S"]')
    diamond.hover()
    box = diamond.bounding_box()
    clip = {
        "x": math.floor(box["x"]),
        "y": math.floor(box["y"]),
        "width": math.floor(box["width"]),
        "height": math.floor(box["height"]),
    }
    quiet = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")

    page.keyboard.down("Alt")
    armed = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    delta = ImageChops.difference(quiet, armed)
    changed = [max(pixel) >= 6 for pixel in zip(*[iter(delta.tobytes())] * 3)]
    width, height = delta.size

    def ratio(where):
        pixels = [
            changed[y * width + x]
            for y in range(height)
            for x in range(width)
            if where(x / width, y / height)
        ]
        return sum(pixels) / len(pixels)

    middle = ratio(lambda x, y: abs(x - 0.5) + abs(y - 0.5) < 0.25)
    corners = ratio(lambda x, y: abs(x - 0.5) + abs(y - 0.5) > 0.75)
    assert middle > 0.5, f"the diamond's middle changed by only {middle:.0%}"
    assert corners < 0.05, f"the empty corners changed by {corners:.0%}"
    page.keyboard.up("Alt")


def test_a_generic_package_gets_nested_hits_and_can_narrow_a_paint_surface(
    browser, serve
):
    """Core derives hit lookup from one package inventory.

    The inner part wins even though the containing part appears first. The outer part's
    explicit surface excludes its decorative line, while the inner part's default surface
    follows all painted geometry it contains.
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
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "outer")
    assert page.eval_on_selector_all(
        ".lf-aim-shape > g > *", "nodes => nodes.map(node => node.localName)"
    ) == ["rect"]
    page.keyboard.up("Alt")

    page.locator("#inner path").hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "inner")
    assert page.eval_on_selector_all(
        ".lf-aim-shape > g > *", "nodes => nodes.map(node => node.localName)"
    ) == ["path", "line"]
    page.keyboard.up("Alt")


def test_an_undeclared_nested_part_does_not_shadow_its_declared_parent(browser, serve):
    """Authored tokens bound hit-testing, not only the event after it has chosen a hit.

    The package may register more parts than this instance exposes. A hit inside one of
    those parts still belongs to the nearest declared ancestor rather than widening to
    the visual as a whole.
    """
    page = open_page(
        browser,
        serve(
            GENERIC_VISUAL_PAGE.replace(
                'parts="outer inner html"', 'parts="outer html"'
            ),
            layer_registry=GENERIC_VISUAL_LAYER,
            layer_widgets=GENERIC_VISUAL_WIDGETS,
        ),
    )

    page.locator("#inner path").hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "outer")
    assert page.eval_on_selector_all(
        ".lf-aim-shape > g > *", "nodes => nodes.map(node => node.localName)"
    ) == ["rect"]
    page.keyboard.up("Alt")


def test_a_registered_visual_rebuilds_same_bounds_geometry_on_update(browser, serve):
    """The package's update signal rebuilds a contour even when its box does not move.

    The contour is the one standing in the part's thread raises; at rest a thread draws
    nothing on its element."""
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    events_model.append_event(
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
    page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    contour = page.locator(".lf-visual-mark-shape > g > rect")
    expect(contour).to_have_attribute("rx", "8")
    before = page.evaluate(
        """() => {
          const contour = document.querySelector('.lf-visual-mark-shape > g > rect');
          window.lfOldContour = contour;
          return contour.getBoundingClientRect();
        }"""
    )

    page.locator("#visual").evaluate("visual => visual.redraw()")
    expect(contour).to_have_attribute("rx", "28")
    after = contour.evaluate("contour => contour.getBoundingClientRect()")
    assert before == after
    assert page.evaluate(
        "() => window.lfOldContour !== document.querySelector('.lf-visual-mark-shape > g > rect')"
    )


def test_a_part_drawn_in_another_state_stands_on_its_visual_until_travel_reveals_it(
    browser, serve
):
    """A thread on a part the visual is not drawing now stays attached, to the whole
    visual, and travelling to it asks the visual to draw the part and lands there."""
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=STAGED_VISUAL_WIDGETS,
    )
    events_model.append_event(
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
    # Pointing at the visual raises the thread's contour, and it encloses the whole.
    page.locator("#visual").hover()
    placed = page.evaluate(
        """() => {
          const box = (el) => el.getBoundingClientRect();
          const mark = document.querySelector('.lf-visual-mark-hover');
          const visual = box(document.querySelector('#visual'));
          return Boolean(mark) && box(mark).width >= visual.width
            && box(mark).height >= visual.height;
        }"""
    )
    assert placed
    page.mouse.move(0, 0)

    page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    expect(inner).to_be_visible()
    page.wait_for_function(
        """() => {
          const mark = document.querySelector('.lf-visual-mark-here');
          const inner = document.querySelector('#inner').getBoundingClientRect();
          const box = mark?.getBoundingClientRect();
          return box && box.width < inner.width + 40 && box.height < inner.height + 40;
        }"""
    )


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
    events_model.append_event(
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
    assert (
        page.evaluate(
            "() => [...document.querySelectorAll('.lf-visual-mark-pending')].length"
        )
        == 1
    )
    expect(page.locator("#html")).to_have_class(re.compile(r"\blf-projected-mark\b"))


def test_a_visual_surface_narrows_paint_without_narrowing_semantic_interaction(
    browser, serve
):
    """Decoration omitted from a contour still belongs to its semantic part.

    The posted comment opens from the line inside the registered element, while the
    package-selected rectangle remains the only cloned paint of the contour the pointer
    raises. A second draft on the same part wears the pending contour, since the posted
    comment draws none at rest.
    """
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    events_model.append_event(
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
    mark = page.locator(".lf-visual-mark")
    expect(mark).to_have_count(0)

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
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-over-mark\b"))
    expect(outer).to_have_class(re.compile(r"\blf-projected-mark\b"))
    assert page.eval_on_selector_all(
        ".lf-visual-mark-shape > g > *", "nodes => nodes.map(node => node.localName)"
    ) == ["rect"]
    page.mouse.click(point["x"], point["y"])
    expect(
        page.locator('.lf-margin-preview .lf-page-thread[data-thread="outer-comment"]')
    ).to_be_visible()
    expect(page.locator(".lf-thread-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-composer")).to_be_hidden()

    point = midpoint(decoration)
    page.keyboard.down("Alt")
    page.mouse.move(point["x"], point["y"])
    page.mouse.click(point["x"], point["y"])
    page.keyboard.up("Alt")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(mark).to_have_class(re.compile(r"\blf-visual-mark-pending\b"))


def test_a_non_geometry_visual_surface_uses_one_box_for_aim_and_mark(browser, serve):
    """The painter owns the rectangular fallback as well as SVG contours."""
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    events_model.append_event(
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
    mark = page.locator(".lf-visual-mark")

    surface.hover()
    expect(semantic).to_have_class(re.compile(r"\blf-projected-mark\b"))
    expect(mark).to_be_visible()
    expect(mark).not_to_have_class(re.compile(r"\blf-shaped\b"))
    expect(mark).to_have_css("border-radius", "12px")
    assert mark.locator(".lf-visual-mark-shape > *").count() == 0
    marked = mark.bounding_box()
    painted = surface.bounding_box()
    assert all(
        abs(marked[key] - painted[key]) <= 1 for key in ("x", "y", "width", "height")
    ), (marked, painted)

    surface.hover()
    page.keyboard.down("Alt")
    aim = page.locator(".lf-aim")
    expect(aim).not_to_have_class(re.compile(r"\blf-shaped\b"))
    expect(aim).to_have_css("border-radius", "12px")
    aimed = aim.bounding_box()
    assert all(
        abs(aimed[key] - painted[key]) <= 1 for key in ("x", "y", "width", "height")
    ), (aimed, painted)
    page.keyboard.up("Alt")


def test_a_shadow_visual_surface_is_clipped_by_its_host(browser, serve):
    """Core follows package geometry through its host into the page's clip chain."""
    url = serve(
        SHADOW_VISUAL_PAGE,
        layer_registry=SHADOW_VISUAL_LAYER,
        layer_widgets=SHADOW_VISUAL_WIDGETS,
    )
    events_model.append_event(
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
    mark = page.locator(".lf-visual-mark")

    surface.hover(position={"x": 20, "y": 20})
    expect(mark).to_be_visible()
    host_box = host.bounding_box()
    mark_box = mark.bounding_box()
    assert mark_box["x"] >= host_box["x"]
    assert mark_box["x"] + mark_box["width"] <= host_box["x"] + host_box["width"]

    page.keyboard.down("Alt")
    aim = page.locator(".lf-aim")
    expect(aim).to_have_attribute("data-for", "wide-surface")
    aim_box = aim.bounding_box()
    assert aim_box["x"] >= host_box["x"]
    assert aim_box["x"] + aim_box["width"] <= host_box["x"] + host_box["width"]
    page.keyboard.up("Alt")


def test_a_visual_part_mark_follows_its_drawn_svg_shape(browser, serve):
    """A posted comment's contour keeps the same semantic geometry the aim promised.

    The diamond's diagonal contour must change while the empty bounding-box corners do
    not. A CSS outline on the returned group produces the opposite result.
    """
    from PIL import Image, ImageChops

    diamond_page = PART_DIAGRAM_PAGE.replace("S[Start request]", "S{Start request}", 1)
    page = open_page(browser, serve(diamond_page))
    diamond = page.locator('#flow g[data-id="S"]')
    expect(diamond).to_be_visible()
    box = diamond.bounding_box()
    clip = {
        "x": math.floor(box["x"]),
        "y": math.floor(box["y"]),
        "width": math.floor(box["width"]),
        "height": math.floor(box["height"]),
    }
    quiet = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "diamond-comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this branch explicit.",
            "anchor": {"section": "flow", "visual": "node:S"},
        },
    )
    told(page)
    expect(diamond).to_have_class(re.compile(r"\blf-mark-el\b"))
    # Standing in the thread raises the contour; at rest the thread draws none.
    page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    expect(diamond).to_have_class(re.compile(r"\blf-projected-mark\b"))
    # The comment's margin row stands on the diagram; nothing Leaf draws moves the
    # page's content, so the diamond is read where it stands rather than assumed.
    moved = diamond.bounding_box()
    clip = {**clip, "x": math.floor(moved["x"]), "y": math.floor(moved["y"])}
    painted = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    delta = ImageChops.difference(quiet, painted)
    changed = [max(pixel) >= 6 for pixel in zip(*[iter(delta.tobytes())] * 3)]
    width, height = delta.size

    def ratio(where):
        pixels = [
            changed[y * width + x]
            for y in range(height)
            for x in range(width)
            if where(x / width, y / height)
        ]
        return sum(pixels) / len(pixels)

    diagonal = ratio(lambda x, y: 0.45 < abs(x - 0.5) + abs(y - 0.5) < 0.55)
    corners = ratio(lambda x, y: abs(x - 0.5) + abs(y - 0.5) > 0.8)
    assert diagonal > 0.08, f"only {diagonal:.0%} of the diamond contour changed"
    assert corners < 0.03, f"the empty corners changed by {corners:.0%}"

    offset = page.evaluate(
        """() => {
          const source = document.querySelector('#flow g[data-id="S"]').getBoundingClientRect();
          const mark = document.querySelector('.lf-visual-mark').getBoundingClientRect();
          return [mark.left - source.left, mark.top - source.top,
                  mark.right - source.right, mark.bottom - source.bottom];
        }"""
    )
    page.evaluate(
        """() => {
          window.__lfStandingContour = document.querySelector(
            '.lf-visual-mark-shape > g > *'
          );
        }"""
    )
    page.evaluate("() => scrollBy(0, 80)")
    page.wait_for_function(
        """(before) => {
          const source = document.querySelector('#flow g[data-id="S"]').getBoundingClientRect();
          const mark = document.querySelector('.lf-visual-mark').getBoundingClientRect();
          const after = [mark.left - source.left, mark.top - source.top,
                         mark.right - source.right, mark.bottom - source.bottom];
          return after.every((value, index) => Math.abs(value - before[index]) < 0.5);
        }""",
        arg=offset,
    )
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    assert page.evaluate(
        """() => window.__lfStandingContour === document.querySelector(
          '.lf-visual-mark-shape > g > *'
        )"""
    )


def test_a_rounded_diagram_part_aim_has_room_to_cover_the_shape_edge(browser, serve):
    """A contour's paint viewport includes the outside half of its stroke.

    SVG strokes straddle their geometry. If the runtime gives the cloned contour the
    node's exact bounds, the viewport cuts off its outside half: on rounded ends the
    original border then remains visible beside the aim instead of under it.
    """
    rounded_page = PART_DIAGRAM_PAGE.replace(
        "S[Start request]", "S([Start request])", 1
    )
    page = open_page(browser, serve(rounded_page))
    rounded = page.locator('#flow g[data-id="S"]')
    rounded.hover()
    page.keyboard.down("Alt")
    geometry = page.evaluate(
        """() => ({
          node: document.querySelector('#flow g[data-id="S"]').getBoundingClientRect(),
          aim: document.querySelector('.lf-aim').getBoundingClientRect(),
        })"""
    )

    node, aim = geometry["node"], geometry["aim"]
    assert node["left"] - aim["left"] >= 1
    assert node["top"] - aim["top"] >= 1
    assert aim["right"] - node["right"] >= 1
    assert aim["bottom"] - node["bottom"] >= 1
    page.keyboard.up("Alt")


def test_a_declared_flowchart_node_keeps_its_comment_across_renderings(browser, serve):
    """The authored Mermaid id, rather than its generated SVG id, is the anchor.

    An unlisted node is the control: it still takes the whole diagram. A listed node
    outlines only its current SVG group, while the diagram holds the accessible note
    and the panel place. Reloading makes Mermaid generate the SVG again and proves the
    stable token resolves to that new box.
    """
    page = open_page(browser, live_url(serve(PART_DIAGRAM_PAGE)))
    diagram = page.locator("#flow")

    unlisted = diagram.locator('g[data-id="U"]')
    unlisted.click(modifiers=["Alt"])
    expect(diagram).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    page.keyboard.press("Escape")

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
    expect(page.locator(".lf-thread .lf-quote")).to_have_text(
        "§ diagram · Start request"
    )
    expect_comment_notes(page, "#flow", 1)
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b"))

    stamp_page(serve.page_dir, PART_DIAGRAM_V2, "reordered")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
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
<lf-diagram id="exchange" parts="node:A"><pre>
sequenceDiagram
  participant A as User
  participant B as Server
  A->>B: Request
</pre></lf-diagram>
""",
    )
    page = open_page(browser, serve(sequence))

    actor = page.locator('#exchange g[data-id="A"]')
    actor.click(modifiers=["Alt"])
    open_compact_comment(page)
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · User")
    expect(actor).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))


def test_a_declared_box_takes_its_comment_on_every_type_that_carries_an_id(
    browser, serve
):
    """`parts` follows the ids the renderer carries, not one diagram type.

    State names, sequence participants, class names, and ER entities are written in the
    source the way a flowchart node is, so each addresses a box across a re-render. A
    composite state and a box inside it each take their own comment. An entity's box
    holds its whole attribute table, so the thread label stays the source name. A later
    version then inserts a state above the anchored one and rebuilds the SVG while the
    authored token remains stable.
    """
    page = open_page(browser, live_url(serve(TYPED_PARTS_PAGE)))

    def aim(target, **press):
        target.click(modifiers=["Alt"], **press)
        open_compact_comment(page)

    state = page.locator('#life g[data-id="Queued"]')
    aim(state)
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Queued")
    write(page.locator(".lf-composer leaf-text"), "how long does it sit here")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    # The trip ends when the page has heard back what it sent, which is before it has
    # drawn what came back. Applying the comment repaints this diagram's marks and hangs
    # its note on the element, and that repaint takes an open response surface down with
    # it — so an aim placed in the gap opens a composer the arriving comment then closes.
    # The note is the projection landing, and every later aim is on a settled page.
    expect_comment_notes(page, "#life", 1)

    # A box inside the composite state, declared in its own right.
    aim(page.locator('#life g[data-id="Build"]'))
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Build")
    page.keyboard.press("Escape")

    aim(page.locator('#life g[data-id="Working"]'), position={"x": 6, "y": 6})
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Working")
    page.keyboard.press("Escape")

    entity = page.locator('#shape g[data-id="RUNNER"]')
    aim(entity)
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · RUNNER")
    page.keyboard.press("Escape")

    # A node's label is the words the box shows.
    aim(page.locator('#path g[data-id="A"]'))
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "§ diagram · Bold and plain"
    )
    page.keyboard.press("Escape")

    aim(page.locator('#exchange g[data-id="User"]'))
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · User")
    page.keyboard.press("Escape")

    aim(page.locator('#model g[data-id="Job"]'))
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Job")
    page.keyboard.press("Escape")

    aim(entity)
    write(page.locator(".lf-composer leaf-text"), "one runner or many")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    # The same gap as above, read from the other side. The trip ends on what the page has
    # sent, and a post the browser has not reported yet is not pending, so a trip taken on
    # the heels of the press can end before this comment is in the wire at all — and the
    # log read below then answers with the log as it stood before the gesture. This note is
    # the second comment applied, which it cannot be before the log holds it.
    expect_comment_notes(page, "#shape", 1)

    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in posted] == [
        {"section": "life", "visual": "node:Queued"},
        {"section": "shape", "visual": "node:RUNNER"},
    ]
    expect(state).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(entity).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(page.locator("#life")).not_to_have_class(re.compile(r"\blf-mark-el\b"))

    # v2 rebuilds the SVG around an inserted state. The mark follows the authored token
    # to the replacement box rather than retaining a detached renderer node.
    state.evaluate("el => { window.lfOldQueued = el; }")
    stamp_page(serve.page_dir, TYPED_PARTS_V2, "one state earlier")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    assert page.evaluate("() => !window.lfOldQueued.isConnected")
    expect(state).to_have_class(re.compile(r"\blf-mark-el\b"))


def test_a_scroll_under_a_held_aim_moves_the_promise_with_the_page(browser, serve):
    """What a press would take can change with no mouse event to say so.

    Only a pointer move used to re-decision the aim, so scrolling under a held key left the
    outline on the item that had been under the pointer while a press took the one now
    there — the paint answering an old page, the claim the current one. The scroll
    listener re-decisions; this scrolls the page under a parked pointer and requires the
    promise to answer for where the page now stands."""
    page = open_page(browser, serve(LONG_PAGE))
    page.mouse.move(600, 300)
    page.keyboard.down("Alt")
    first = page.evaluate(AIMED)
    assert first, "nothing promised under the parked pointer, so nothing is being aimed"
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
      const promised = document.querySelector(".lf-aim")?.getAttribute("data-for");
      const at = document.elementFromPoint(600, 300)?.closest("[id]:not(.lf-ui)");
      return Boolean(promised) && promised === at?.id && promised !== first;
    }""",
        arg=first,
    )
    page.keyboard.up("Alt")


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
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "card-importer")
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "work",
            "action": "move",
            "detail": {"card": "card-importer", "to": "col-done", "rank": "1i"},
        },
    )
    told(page)
    expect(page.locator("#col-done #card-importer")).to_have_count(1)
    page.wait_for_function(
        """([x, y]) => {
      const promised =
        document.querySelector(".lf-aim")?.getAttribute("data-for") ?? null;
      const at = document.elementFromPoint(x, y)?.closest("[id]:not(.lf-ui)") ?? null;
      return promised === (at?.id ?? null) && promised !== "card-importer";
    }""",
        arg=spot,
    )
    page.keyboard.up("Alt")


def test_the_aims_box_is_what_the_page_shows_of_the_element(browser, serve):
    """The promise paints in the chrome's layer, and claims what the page shows.

    The aim used to wear the mark's rail, and that band sat at the
    border edge — the one band of an element nobody else paints in, and exactly where a
    widget draws a border of its own. Over an accented option, whose border is
    already the accent, arming changed nothing a user could see, and what was
    reported was no box at all. So the aim paints in the layer above the page, which no
    widget can reach; the pixel diff here is armed against unarmed with the pointer
    held still, so the widget's own hover wash is in both frames and the difference is
    the promise alone.

    A layer no widget can paint over is also one no ancestor's clip can reach, so the
    second half holds the box to the page's own showing of the item: a row's table box
    runs on under its group's overflow: hidden, and a box drawn from the raw rect
    would claim pixels the page has refused, over whatever stands in them."""
    from PIL import Image, ImageChops  # a dev dependency already, for the demo recorder

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
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "card-star")
    armed = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    assert quiet.size == armed.size
    geometry = page.evaluate("""() => {
        const item = document.getElementById("card-star").getBoundingClientRect();
        const box = document.querySelector(".lf-aim").getBoundingClientRect();
        return [box.left - item.left, box.top - item.top,
                box.width - item.width, box.height - item.height].map(Math.abs);
    }""")
    assert max(geometry) < 1, f"the box missed the card it promises by {geometry}"
    pixels = zip(*[iter(ImageChops.difference(quiet, armed).tobytes())] * 3)
    changed = sum(max(p) >= 6 for p in pixels) / (armed.size[0] * armed.size[1])
    assert changed > 0.5, (
        f"arming changed {changed:.0%} of the card's pixels — the promise is not "
        "something a user can see over the widget's own paint"
    )

    row = page.locator("#row-ship")
    row.hover()
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "row-ship")
    edges = page.evaluate("""() => {
        const group = document.getElementById("rows").getBoundingClientRect();
        const row = document.getElementById("row-ship").getBoundingClientRect();
        const box = document.querySelector(".lf-aim").getBoundingClientRect();
        return { box: box.right, shown: Math.min(row.right, group.right),
                 raw: row.right };
    }""")
    assert abs(edges["box"] - edges["shown"]) < 1, (
        f"the box ends at {edges['box']} where the page shows the row to "
        f"{edges['shown']} (its unclipped box runs to {edges['raw']}): a clip the "
        "page enforces went unhonoured"
    )
    page.keyboard.up("Alt")


def test_the_chrome_keeps_its_presses_while_the_page_is_armed(browser, serve):
    """What ⌥ arms is the page, and the line around it is the chrome's container.

    An aim that reached in there would take the panel, the composer and the banner away
    from a user who happens to be holding the key — and there is nothing in the layer
    to aim at anyway, since an anchor names an element of the page."""
    page = open_page(browser, serve(LONG_PAGE))
    comments = page.locator(".lf-threads-toggle")
    comments.hover()
    page.keyboard.down("Alt")
    comments.click()
    page.keyboard.up("Alt")
    panel_settled(page)
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_hidden()


def test_the_armed_cursor_says_whether_a_press_would_take_anything(browser, serve):
    """The sequence's cost is that it is invisible, and the cursor pays part of it.

    Holding ⌥ used to draw a plain arrow over the whole page: it said "not a text
    selection" and nothing else, which leaves the one question the outline can't answer
    for a user who hasn't looked yet — would this click do anything at all? An armed
    press takes the addressable element under it and acts on nothing where there is none (claimPress),
    so the hand and the arrow are those two states, and the hand is exactly as good as
    the outline beside it because both are read off the same value.

    Read where the user's pointer is rather than off body, since the aim declares it
    on body and everything on the page inherits it — the promise is only kept if it
    arrives at the glyphs. The margin beside the column is the page's own gap: no
    element there carries an id, so an armed press has nothing to take.

    `auto` is the resting state, and it is the whole point of the arrow: unarmed, the
    browser decides from what is under the pointer and draws an I-beam over words, so
    naming a cursor at all is the runtime saying those words are not a selection now."""
    page = open_page(browser, serve(LONG_PAGE))
    at_pointer = """([x, y]) =>
        getComputedStyle(document.elementFromPoint(x, y)).cursor"""
    on_item = page.locator("#p2").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.left + 20, r.top + r.height / 2]; }"
    )
    # Beside the column, level with the same paragraph: body's own margin, which the
    # centred 720px column leaves on a 1200px viewport.
    in_gap = [40, on_item[1]]
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "an unarmed page already named a cursor, so the arm has nothing left to say"
    )

    page.mouse.move(*on_item)
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "p2")
    assert page.evaluate(at_pointer, on_item) == "pointer", (
        "the aim boxed the paragraph and the cursor declined to promise the press"
    )

    page.mouse.move(*in_gap)
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    assert page.evaluate(at_pointer, in_gap) == "default", (
        "the aim had nothing to take and the hand promised a press anyway"
    )

    # Back on the item, so the arm coming off is read from the state that promises most.
    page.mouse.move(*on_item)
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "p2")
    page.keyboard.up("Alt")
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "the key came up and the page went on offering the aim's press"
    )


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
    page.locator(".lf-banner-actions").get_by_role(
        "button", name="Comment on selection"
    ).tap()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
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
    page.locator(".lf-banner-actions").get_by_role(
        "button", name="Comment on selection"
    ).tap()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
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
