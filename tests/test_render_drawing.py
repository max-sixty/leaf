"""Drawing-comment browser journeys."""

import base64
import re

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import (
    CONVERSATION_DIFF_PAGE,
    live_url,
)
from render_cases_navigation import (
    TARGETS_PAGE,
)
from render_harness import (
    BOTH_STAMPS,
    EXAMPLE_MEDIA,
    FEATURE_GALLERY,
    RENDERED,
    leaf_page,
    nudge,
    open_page,
    panel_settled,
    sending,
    told,
)

pytestmark = pytest.mark.nightly


STROKE = ((0.22, 0.62), (0.5, 0.25), (0.78, 0.62))


def stroke_over(page, locator, *, steps=8, points=STROKE):
    """Drag one stroke through `points`, fractions of the locator's box, in Draw mode.

    Returns the stroke's starting point in the viewport.
    """
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    start, middle, end = [
        (box["x"] + box["width"] * x, box["y"] + box["height"] * y) for x, y in points
    ]
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*middle, steps=steps)
    page.mouse.move(*end, steps=steps)
    page.mouse.up()
    return start


def draw_over(page, locator, *, steps=8, points=STROKE):
    """Enter Draw mode with the pointer at the stroke's start, then draw it."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    x, y = points[0]
    page.mouse.move(box["x"] + box["width"] * x, box["y"] + box["height"] * y)
    page.keyboard.press("w")
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    assert locator.evaluate("el => getComputedStyle(el).cursor") == "crosshair"
    expect(page.locator(".lf-aim")).to_be_hidden()
    return stroke_over(page, locator, steps=steps, points=points)


READ_BOX = """selector => {
  const box = document.querySelector(selector).getBoundingClientRect();
  return {x: box.x, y: box.y, width: box.width, height: box.height, scrollY};
}"""

DATA_REVISION_DIFF_PAGE = leaf_page(
    "data revision drawing",
    '<h1 id="title">Review</h1><lf-diff id="drawing-diff" source="drawing-patch">'
    "<pre></pre></lf-diff>",
)
DATA_REVISION_DIFF = """diff --git a/review.py b/review.py
--- a/review.py
+++ b/review.py
@@ -1,2 +1,2 @@
 def route():
-    return "courtyard"
+    return "terrace"
"""
UPDATED_DATA_REVISION_DIFF = DATA_REVISION_DIFF.replace("terrace", "garden room")


def open_data_revision_diff(browser, serve):
    """Open one live data-backed diff at the first source revision."""
    url = serve(DATA_REVISION_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "drawing-patch", DATA_REVISION_DIFF)
    return open_page(browser, url)


def mark_box(page, selector):
    """Read a drawing mark's box, resolving and measuring it in one page-side call.

    A paint that moves the ink replaces the node that carried it, so a two-step read —
    Playwright resolves the element, then measures the handle it got — can measure a node
    a scroll or a layout change has already detached, and a detached box reads as all
    zeros.
    """
    return page.evaluate(READ_BOX, selector)


def mark_relation(page, mark, target):
    """Read the mark's offset from its anchor and its size, in one page-side call."""
    return page.evaluate(
        """([mark, target]) => {
          const drawn = document.querySelector(mark).getBoundingClientRect();
          const anchored = document.querySelector(target).getBoundingClientRect();
          return [
            drawn.x - anchored.x,
            drawn.y - anchored.y,
            drawn.width,
            drawn.height,
          ];
        }""",
        [mark, target],
    )


def test_a_drawing_is_sent_and_replayed_as_an_ordinary_comment(browser, serve):
    """One pointer stroke starts on one semantic anchor, crosses the page beyond it,
    and the accepted comment keeps its context in the page instead of duplicating it."""
    url = serve(FEATURE_GALLERY)
    page = open_page(browser, url)
    target = page.locator("#bg-choice-trail")
    target.evaluate("el => { el.style.position = 'relative'; el.style.zIndex = '1'; }")
    scroll_width = page.evaluate("document.documentElement.scrollWidth")

    draw_over(
        page,
        target,
        steps=300,
        points=((0.22, 0.62), (0.75, -1), (1.7, 1.8)),
    )

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(target).not_to_have_class(re.compile(r"\blf-mark-el\b|\blf-pending\b"))
    assert target.get_attribute("chosen") is None
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    field.fill("This bend is the part I mean.")
    with sending(page, "the drawing comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert event["anchor"] == {"section": "bg-choice-trail"}
    assert event["text"] == "This bend is the part I mean."
    drawing = event["drawing"]
    assert drawing["format"] == "leaf-drawing/2"
    (stroke,) = drawing["strokes"]
    assert 2 <= len(stroke) <= 256
    target_box = target.bounding_box()
    xs, ys = zip(*stroke, strict=True)
    assert min(xs) / target_box["width"] == pytest.approx(0.22, abs=0.02)
    assert min(ys) / target_box["height"] == pytest.approx(-1, abs=0.02)
    assert max(xs) - min(xs) > target_box["width"]
    assert max(ys) - min(ys) > target_box["height"]
    assert all(
        -100000 <= coordinate <= 100000 for point in stroke for coordinate in point
    )
    assert stroke[-1][0] / target_box["width"] == pytest.approx(1.7, abs=0.02)
    assert stroke[-1][1] / target_box["height"] == pytest.approx(1.8, abs=0.02)

    posted = f'.lf-drawing-posted[data-thread="{event["id"]}"]'
    mark = page.locator(posted)
    expect(mark).to_have_count(1)
    drawn = mark_box(page, posted)
    assert drawn["x"] + drawn["width"] > target_box["x"] + target_box["width"]
    assert drawn["y"] < target_box["y"]
    assert page.evaluate("document.documentElement.scrollWidth") == scroll_width
    stacking = page.locator(".lf-drawings").evaluate(
        "el => ({classes: el.getAttribute('class'), z: getComputedStyle(el).zIndex})"
    )
    assert stacking["z"] == "8890", stacking
    stable_mark = mark.element_handle()
    # A state read repaints the marks, as an anchor repaint and a size notice also do.
    # This one describes ink that has not moved, so the mark the user is looking at has
    # to be the same node afterwards.
    nudge(serve.page_dir)
    told(page)
    page.evaluate(RENDERED)
    assert stable_mark.evaluate("node => node.isConnected"), (
        "a repaint describing unchanged ink must keep the mark it already painted"
    )
    relation = mark_relation(page, posted, "#bg-choice-trail")
    page.evaluate("scrollBy(0, 100)")
    page.evaluate(RENDERED)
    assert mark_relation(page, posted, "#bg-choice-trail") == pytest.approx(
        relation, abs=0.02
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert mark_relation(page, posted, "#bg-choice-trail") == pytest.approx(
        relation, abs=0.02
    )
    expect(target).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(page.locator(".lf-thread-panel .lf-drawing-preview")).to_have_count(0)
    expect(page.locator(".lf-thread-panel .lf-drawing-reference")).to_have_text(
        "Drawing comment"
    )

    returned = open_page(browser, url)
    expect(returned.locator(posted)).to_have_count(1)
    assert mark_relation(returned, posted, "#bg-choice-trail") == pytest.approx(
        relation, abs=0.02
    )


WORDS_PAGE = leaf_page(
    "drawn words",
    '<h1 id="t">Words</h1>'
    '<p id="line">Alpha bravo charlie delta echo foxtrot golf.</p>'
    # Longer than a drawing may say, so the reading's cut is what reaches the door.
    f'<p id="para">Arrow {"lorem ipsum dolor sit amet " * 20}target.</p>'
    # Rows the box has cut away still have coordinates, and they are the paragraph's below.
    # The words sit in the box directly, so the clip over them is their own holder's.
    f'<div id="pit">{"buried " * 80}</div>'
    '<p id="under">India juliet kilo.</p>',
    head="<style>#pit { height: 2em; overflow: hidden }</style>",
)

WORDS_BOX = """([selector, words]) => {
  const node = document.querySelector(selector).firstChild;
  const at = node.data.indexOf(words);
  const range = document.createRange();
  range.setStart(node, at);
  range.setEnd(node, at + words.length);
  const box = range.getBoundingClientRect();
  return {x: box.x, y: box.y, width: box.width, height: box.height};
}"""


def trace(page, points):
    """Drag one stroke through viewport `points`."""
    first, *rest = points
    page.mouse.move(*first)
    page.mouse.down()
    for point in rest:
        page.mouse.move(*point, steps=6)
    page.mouse.up()


def strike(page, selector, words, *, below=None):
    """Drag one level stroke along `words`, from inside its first letter to its last:
    through their middle, or `below` pixels under their box."""
    box = page.evaluate(WORDS_BOX, [selector, words])
    y = box["y"] + (box["height"] / 2 if below is None else box["height"] + below)
    trace(
        page,
        [
            (box["x"] + 2, y),
            (box["x"] + box["width"] / 2, y),
            (box["x"] + box["width"] - 2, y),
        ],
    )


def around(page, box):
    """Ring a box: one stroke just inside it that ends where it began."""
    left, top = box["x"] + 2, box["y"] + 2
    right, bottom = box["x"] + box["width"] - 2, box["y"] + box["height"] - 2
    trace(
        page,
        [(left, top), (right, top), (right, bottom), (left, bottom), (left, top + 2)],
    )


def test_a_drawing_says_the_words_it_stands_over_and_the_box_it_was_drawn_in(
    browser, serve
):
    """An agent reads a drawing without the page in front of it, so the comment carries
    the page's words inside the ink's extents, first to last, and the size of the box the
    offsets were measured in. Words the page has cut away from under the ink are not
    among them."""
    page = open_page(browser, serve(WORDS_PAGE))
    line = page.locator("#line")
    line.scroll_into_view_if_needed()
    start = page.evaluate(WORDS_BOX, ["#line", "bravo charlie"])
    page.mouse.move(start["x"] + 2, start["y"] + start["height"] / 2)
    page.keyboard.press("w")
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    field = page.locator(".lf-fab-input")

    def sent(what):
        # Pressed on the field rather than on whatever holds focus: a later stroke reopens
        # the box, and focus is another test's subject.
        expect(field).to_be_focused()
        with sending(page, what):
            field.press("ControlOrMeta+Enter")
        return events_model.read_events(serve.page_dir)[-1]

    # Two strokes are one drawing, which says everything between its first word and last.
    strike(page, "#line", "bravo charlie")
    expect(field).to_be_focused()
    strike(page, "#line", "foxtrot")
    expect(page.locator(".lf-drawing-pending path")).to_have_attribute(
        "d", re.compile(r"^M[^M]*M[^M]*$")
    )
    event = sent("the drawing over two runs of words")
    assert event["anchor"] == {"section": "line"}
    drawing = event["drawing"]
    assert len(drawing["strokes"]) == 2
    assert drawing["says"] == "bravo charlie delta echo foxtrot"
    box = line.bounding_box()
    assert drawing["box"] == pytest.approx([box["width"], box["height"]], abs=0.01)

    # A line under a word is its underline, though it touches none of the word's box.
    strike(page, "#line", "delta", below=3)
    assert sent("the underline")["drawing"]["says"] == "delta"

    # An arrow from a paragraph's first word to its far corner says the paragraph, as
    # far as a drawing's 500 characters go.
    para = page.locator("#para")
    para.scroll_into_view_if_needed()
    # Read before the send, which adds the block's comment note to what it holds.
    whole = " ".join(para.inner_text().split())
    first = page.evaluate(WORDS_BOX, ["#para", "Arrow"])
    box = para.bounding_box()
    assert box["height"] > 3 * first["height"], "the paragraph must wrap"
    trace(
        page,
        [
            (first["x"] + 2, first["y"] + first["height"] / 2),
            (
                box["x"] + box["width"] - 2,
                box["y"] + box["height"] - first["height"] / 2,
            ),
        ],
    )
    assert len(whole) > 500
    assert sent("the arrow")["drawing"]["says"] == whole[:499] + "…"

    # The cut-away rows of the box above lie under this ring's coordinates.
    page.locator("#under").scroll_into_view_if_needed()
    hidden = page.evaluate(
        """() => {
          const under = document.querySelector("#under").getBoundingClientRect();
          const rows = document.createRange();
          rows.selectNodeContents(document.querySelector("#pit"));
          return [...rows.getClientRects()].some(
            (row) => row.bottom > under.top && row.top < under.bottom);
        }"""
    )
    assert hidden, "the control: a hidden row must share the ring's coordinates"
    around(page, page.locator("#under").bounding_box())
    assert (
        sent("the ring under cut-away rows")["drawing"]["says"] == "India juliet kilo."
    )


def test_a_keyboard_send_reaches_send_while_the_stroke_still_owes_its_press(
    browser, serve
):
    """Draw mode swallows the presses the user's own stroke still owes the page, so a
    stroke lifting over a control does not press that control as well. A keyboard
    activation is not one of those presses: `Ctrl+Enter` in the composer the stroke just
    opened is Send's own click, and it has to reach Send whatever the pointer did the
    moment before.

    The claim comes off on a zero-delay timer, so which of the two arrives first is a
    race — and the user loses it whenever the release's own work runs long, the send
    eaten with nothing said, the drawing still pending and Send still reading enabled.
    So the arrangement holds that macrotask rather than racing it: every zero-delay
    callback the release schedules is held until the press has been made, which is the
    window the rule is about, stated rather than waited for.
    """
    page = open_page(browser, serve(TARGETS_PAGE))
    point = page.evaluate(
        """() => {
          const x = 40;
          const y = Math.min(innerHeight - 80, 420);
          const hit = document.elementFromPoint(x, y);
          return {x, y, tag: hit?.tagName ?? "", item: hit?.closest("main > *")?.id ?? ""};
        }"""
    )
    assert point["tag"] in {"HTML", "BODY", "MAIN"} and not point["item"], point

    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    page.mouse.down()
    page.mouse.move(point["x"] + 70, point["y"] - 60, steps=8)
    page.mouse.move(point["x"] + 130, point["y"] + 30, steps=8)
    page.evaluate(
        """() => {
          const schedule = globalThis.setTimeout;
          const held = [];
          window.__releaseHeldTimers = () => {
            globalThis.setTimeout = schedule;
            for (const callback of held.splice(0)) schedule(callback, 0);
            return true;
          };
          globalThis.setTimeout = (callback, delay, ...rest) =>
            delay ? schedule(callback, delay, ...rest) : (held.push(callback), -1);
        }"""
    )
    page.mouse.up()
    submit = page.locator(".lf-general .lf-compose-submit")
    expect(submit).to_have_attribute("aria-disabled", "false")
    with sending(page, "the drawing the keyboard sent"):
        page.keyboard.press("ControlOrMeta+Enter")
    assert page.evaluate("() => window.__releaseHeldTimers()")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment", event
    assert event["drawing"]["strokes"], event


def test_a_drawing_can_begin_on_page_whitespace(browser, serve):
    """Whitespace is part of the drawable page plane. With no addressable element under the
    starting point, the stroke opens a page comment and keeps document coordinates."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("scrollTo(0, 120000)")
    point = page.evaluate(
        """() => {
          const x = innerWidth - 16;
          const y = Math.min(innerHeight - 80, 420);
          const hit = document.elementFromPoint(x, y);
          return {
            x, y,
            tag: hit?.tagName ?? "",
            chrome: Boolean(hit?.closest(".lf-chrome")),
            item: hit?.closest("main > *")?.id ?? "",
            scrollY,
          };
        }"""
    )
    assert point["tag"] in {"HTML", "BODY", "MAIN"}, point
    assert not point["chrome"] and not point["item"], point
    scroll_width = page.evaluate("document.documentElement.scrollWidth")

    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    assert (
        page.evaluate(
            "([x, y]) => getComputedStyle(document.elementFromPoint(x, y)).cursor",
            [point["x"], point["y"]],
        )
        == "crosshair"
    )
    expect(page.locator(".lf-aim")).to_be_hidden()
    page.mouse.down()
    page.mouse.move(point["x"] - 90, point["y"] - 55, steps=8)
    page.mouse.move(point["x"] - 150, point["y"] + 35, steps=8)
    page.mouse.up()

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-general .lf-compose-submit")).to_have_attribute(
        "aria-disabled", "false"
    )

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("y => scrollTo(0, y)", point["scrollY"])
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    # The reloaded page is a new Draw mode session; its stroke joins the kept drawing.
    # Threads comes back open over the right edge, so this one starts in the left gutter.
    again = {"x": 40, "y": point["y"] - 120}
    page.mouse.move(again["x"], again["y"])
    page.keyboard.press("w")
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    page.mouse.down()
    page.mouse.move(again["x"] + 60, again["y"] - 80, steps=8)
    page.mouse.up()
    expect(page.locator(".lf-drawing-pending path")).to_have_attribute(
        "d", re.compile(r"^M[^M]*M[^M]*$")
    )
    field = page.locator(".lf-general textarea")
    expect(field).to_have_value("")
    field.focus()
    with sending(page, "the page drawing"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert "anchor" not in event and "text" not in event
    first, second = event["drawing"]["strokes"]
    assert first[0] == pytest.approx(
        [point["x"], point["y"] + point["scrollY"]], abs=0.1
    )
    assert second[0] == pytest.approx(
        [again["x"], again["y"] + point["scrollY"]], abs=0.1
    )
    posted = f'.lf-drawing-posted[data-thread="{event["id"]}"]'
    mark = page.locator(posted)
    expect(mark).to_have_count(1)
    page.wait_for_function(
        "selector => document.querySelector(selector)?.getBoundingClientRect().x > 0",
        arg=posted,
    )
    before = mark_box(page, posted)
    assert before["x"] > 0, before
    page.evaluate("scrollBy(0, 100)")
    page.evaluate(RENDERED)
    expect(mark).to_have_count(1)
    after = mark_box(page, posted)
    assert after["x"] == pytest.approx(before["x"], abs=0.02)
    assert after["y"] == pytest.approx(
        before["y"] - (after["scrollY"] - before["scrollY"]), abs=0.02
    )
    assert page.evaluate("document.documentElement.scrollWidth") == scroll_width


def test_a_page_drawing_keeps_pasted_media_already_in_the_general_draft(browser, serve):
    """Adding a page drawing preserves the complete compound draft, including image
    Markdown projected out of the textarea as a thumbnail."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    field = page.locator(".lf-general textarea")
    pixels = (EXAMPLE_MEDIA / "051bee487bfb5d13.png").read_bytes()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        field.evaluate(
            """(textarea, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'drawing.png', {type: 'image/png'}));
              textarea.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )
    expect(page.locator(".lf-general .lf-composer-media img")).to_be_visible()
    page.get_by_role("button", name="Close threads").click()

    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("scrollTo(0, 120000)")
    point = page.evaluate(
        """() => {
          const x = innerWidth - 16;
          const y = Math.min(innerHeight - 80, 420);
          return {x, y};
        }"""
    )
    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    page.mouse.down()
    page.mouse.move(point["x"] - 90, point["y"] - 55, steps=8)
    page.mouse.up()

    expect(field).to_be_focused()
    expect(field).to_have_value("")
    expect(page.locator(".lf-general .lf-composer-media img")).to_be_visible()
    with sending(page, "the drawing and image comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["text"] == "![Pasted image](/media/051bee487bfb5d13.png)"
    assert event["drawing"]["format"] == "leaf-drawing/2"


def test_a_page_drawing_draft_repaints_in_another_tab(browser, serve, one_user):
    """The drawing payload follows the general draft's cross-tab notification rather
    than waiting for a reload or an unrelated state poll to repaint."""
    url = serve(TARGETS_PAGE)
    local = open_page(browser, url, context=one_user)
    remote = open_page(browser, url, context=one_user)
    local.evaluate("document.body.style.minHeight = '180000px'")
    local.evaluate("scrollTo(0, 120000)")
    point = local.evaluate(
        """() => ({
          x: innerWidth - 16,
          y: Math.min(innerHeight - 80, 420),
        })"""
    )
    local.mouse.move(point["x"], point["y"])
    local.keyboard.press("w")
    local.mouse.down()
    local.mouse.move(point["x"] - 100, point["y"] - 40, steps=8)
    local.mouse.up()

    expect(remote.locator(".lf-drawing-pending")).to_have_count(1)
    remote.locator(".lf-threads-toggle").click()
    panel_settled(remote)
    expect(remote.locator(".lf-general .lf-compose-submit")).to_have_attribute(
        "aria-disabled", "false"
    )


def test_an_anchored_drawing_draft_repaints_in_another_tab(browser, serve, one_user):
    """The anchored composer's draft watcher repaints its stroke as well as its target
    when another tab adds drawing geometry to the shared draft."""
    url = serve(TARGETS_PAGE)
    local = open_page(browser, url, context=one_user)
    remote = open_page(browser, url, context=one_user)
    draw_over(remote, remote.locator("#prose"))
    remote_path = remote.locator(".lf-drawing-pending path")
    before = remote_path.get_attribute("d")

    draw_over(
        local,
        local.locator("#prose"),
        points=((0.15, 0.2), (0.45, 0.8), (0.85, 0.2)),
    )

    expect(remote.locator(".lf-drawing-pending")).to_have_count(1)
    remote.wait_for_function(
        "before => document.querySelector('.lf-drawing-pending path')"
        "?.getAttribute('d') !== before",
        arg=before,
    )
    assert remote_path.get_attribute("d") == local.locator(
        ".lf-drawing-pending path"
    ).get_attribute("d")


def test_page_and_anchored_drawing_drafts_keep_their_own_ink(browser, serve):
    """The general and anchored composers are independent durable draft contexts, so
    a new anchored stroke must not visually replace a standing page stroke."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate("document.body.style.minHeight = '180000px'")
    page.evaluate("scrollTo(0, 120000)")
    point = page.evaluate(
        """() => ({x: innerWidth - 16, y: Math.min(innerHeight - 80, 420)})"""
    )
    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    page.mouse.down()
    page.mouse.move(point["x"] - 100, point["y"] - 40, steps=8)
    page.mouse.up()
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    page.get_by_role("button", name="Close threads").click()
    # A stroke in the same Draw mode session would join the page drawing, so the
    # anchored one is drawn in a session of its own.
    page.keyboard.press("w")
    expect(page.locator("body")).not_to_have_attribute("data-lf-draw-mode", "")

    draw_over(page, page.locator("#prose"))

    expect(page.locator(".lf-drawing-pending")).to_have_count(2)
    page.locator(".lf-fab-input").fill("The anchored draft.")
    with sending(page, "the anchored drawing beside the page draft"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    expect(page.locator(".lf-drawing-posted")).to_have_count(1)
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)


def test_strokes_join_one_drawing_until_it_is_sent_and_escape_leaves(browser, serve):
    """Draw mode outlasts a stroke. A later stroke joins the drawing its session opened,
    in that drawing's frame wherever it starts, and keeps joining it after Escape puts its
    box away or the user leaves and re-enters the mode; once the draft is sent the next
    stroke starts another, and only Escape leaves the mode."""
    page = open_page(browser, serve(TARGETS_PAGE))
    prose = page.locator("#prose")
    draw_over(page, prose)
    pending = page.locator(".lf-drawing-pending path")
    expect(pending).to_have_count(1)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")

    # Begun over another element, the stroke still belongs to the prose drawing.
    start = stroke_over(page, page.locator("#fig"))
    origin = prose.bounding_box()
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))
    expect(field).to_be_focused()
    field.fill("All of these.")

    # Escape puts the box away and keeps its draft; the next stroke joins that draft.
    page.keyboard.press("Escape")
    expect(pending).to_have_count(0)
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    stroke_over(page, page.locator("#fig"), points=((0.3, 0.3), (0.5, 0.7), (0.7, 0.3)))
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*M[^M]*$"))
    expect(field).to_be_focused()
    expect(field).to_have_value("All of these.")
    with sending(page, "the three-stroke drawing"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    assert event["text"] == "All of these."
    first, second, third = event["drawing"]["strokes"]
    assert min(len(first), len(second), len(third)) >= 2
    assert second[0] == pytest.approx(
        [start[0] - origin["x"], start[1] - origin["y"]], abs=0.5
    )
    expect(
        page.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"] path')
    ).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*M[^M]*$"))

    # The sent draft holds no drawing any more, so the next stroke starts one.
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    stroke_over(page, page.locator("#fig"))
    expect(pending).to_have_count(1)
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*$"))
    expect(field).to_be_focused()

    # The composer the stroke opened stands inside the mode, so it comes off first.
    page.keyboard.press("Escape")
    expect(pending).to_have_count(0)
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-live")).to_contain_text("Draw mode off")

    # A new Draw mode session draws into the draft it finds rather than over it.
    draw_over(page, page.locator("#fig"), points=((0.3, 0.3), (0.5, 0.7), (0.7, 0.3)))
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))


def test_a_margin_start_uses_the_addressable_element_alongside_it_as_context(
    browser, serve
):
    """Starting beside content keeps that horizontal item's semantic anchor, so opening
    its composer or reflowing the page cannot separate the ink from what it marks."""
    page = open_page(browser, serve(TARGETS_PAGE))
    target = page.locator("#prose")
    box = target.bounding_box()
    page.evaluate(
        """y => {
          const hidden = document.createElement('p');
          hidden.id = 'hidden-draw-target';
          hidden.dataset.lfProjection = 'prose';
          hidden.dataset.lfDatum = 'hidden';
          Object.assign(hidden.style, {
            position: 'fixed', left: `${innerWidth - 80}px`, top: `${y - 10}px`,
            width: '40px', height: '20px', visibility: 'hidden',
          });
          document.querySelector('main').append(hidden);
        }""",
        box["y"] + box["height"] / 2,
    )
    point = page.evaluate(
        """y => {
          const x = innerWidth - 16;
          const hit = document.elementFromPoint(x, y);
          return {
            x, y,
            tag: hit?.tagName ?? "",
            chrome: Boolean(hit?.closest(".lf-chrome")),
            item: hit?.closest("main > *")?.id ?? "",
          };
        }""",
        box["y"] + box["height"] / 2,
    )
    assert point["tag"] in {"HTML", "BODY", "MAIN"}, point
    assert not point["chrome"] and not point["item"], point

    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    expect(page.locator(".lf-aim")).to_be_hidden()
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.75, point["y"] - 30, steps=8)
    page.mouse.move(box["x"] + box["width"] * 0.35, point["y"] + 20, steps=8)
    page.mouse.up()

    expect(page.locator(".lf-fab-input")).to_be_focused()
    with sending(page, "the margin drawing"):
        page.locator(".lf-composer .lf-compose-field .lf-compose-submit").evaluate(
            "button => button.click()"
        )
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    assert "text" not in event
    expect(
        page.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"]')
    ).to_have_count(1)


def test_a_click_draws_nothing_and_escape_leaves_the_mode(browser, serve):
    """Drawing is a drag, not a new click meaning. A click is swallowed without
    opening a comment or activating the page, and Escape restores ordinary reading."""
    page = open_page(browser, serve(TARGETS_PAGE))
    target = page.locator("#prose")
    target.evaluate(
        "el => el.addEventListener('click', () => { el.dataset.activated = ''; })"
    )
    box = target.bounding_box()
    point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*point)
    page.keyboard.press("w")

    assert page.evaluate("getComputedStyle(document.body).touchAction") == "none"
    page.mouse.click(*point)

    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    assert target.get_attribute("data-activated") is None
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "note"
    page.mouse.move(*point)
    page.mouse.down()
    page.keyboard.press("Escape")
    page.mouse.up()
    expect(page.locator("body")).not_to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-live")).to_contain_text("Draw mode off")
    assert target.get_attribute("data-activated") is None


def test_draw_mode_leaves_chrome_controls_usable(browser, serve):
    """The document plane is drawable, but a press on Leaf's chrome remains the
    control's gesture rather than becoming a page drawing."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.press("w")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)


def test_draw_mode_keeps_the_separate_design_mode_binding(browser, serve):
    """Adding Draw on w does not move the existing layer-review mode off l."""
    page = open_page(browser, serve(TARGETS_PAGE))

    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    expect(page.locator("body")).not_to_have_attribute("data-lf-draw-mode", "")
    page.keyboard.press("l")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")


def test_draw_mode_leaves_inline_conversation_controls_usable(browser, serve):
    """A page-widget shadow root retargets document pointer events to its host. The
    inline conversation it contains remains Leaf chrome, not a drawable widget control."""
    url = serve(CONVERSATION_DIFF_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "cd-q"},
            "text": "Can we discuss this line?",
        },
    )
    page = open_page(browser, live_url(url))
    reply = page.get_by_role("textbox", name="Reply", exact=True)
    reply.scroll_into_view_if_needed()

    page.keyboard.press("w")
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    assert reply.evaluate("el => getComputedStyle(el).cursor") != "crosshair"
    reply.click()

    expect(reply).to_be_focused()
    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)


def test_draw_mode_cursor_matches_the_widget_controls_it_captures(browser, serve):
    """Generated controls remain part of the drawable page plane. Their cursor must
    promise the stroke that takes their pointer press instead of promising activation."""
    page = open_page(browser, serve(FEATURE_GALLERY))
    option = page.locator("#bg-choice-trail")
    control = option.locator(".lf-pick")
    control.scroll_into_view_if_needed()
    box = control.bounding_box()
    point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*point)
    page.keyboard.press("w")

    assert control.evaluate("el => getComputedStyle(el).cursor") == "crosshair"
    page.mouse.click(*point)

    expect(page.locator("body")).to_have_attribute("data-lf-draw-mode", "")
    assert option.get_attribute("chosen") is None
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)

    assert control.evaluate("el => getComputedStyle(el).cursor") == "crosshair"
    page.evaluate(
        """() => document.querySelector('.lf-thread-panel').append(
          document.querySelector('#bg-choice-trail')
        )"""
    )
    assert control.evaluate("el => getComputedStyle(el).cursor") != "crosshair"


def test_a_draw_press_uses_the_exact_target_under_its_start(browser, serve):
    """Joined option seams use the target under the pointer when the stroke starts."""
    page = open_page(browser, serve(FEATURE_GALLERY))
    trail = page.locator("#bg-choice-trail")
    trail.scroll_into_view_if_needed()
    box = trail.bounding_box()
    point = (box["x"] + box["width"] * 0.5, box["y"])
    target = page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.closest('lf-option')?.id",
        point,
    )
    assert target in {"bg-choice-street", "bg-choice-trail"}
    page.mouse.move(*point)
    page.keyboard.press("w")
    expect(page.locator(".lf-aim")).to_be_hidden()

    page.mouse.down()
    page.mouse.move(point[0] + 80, point[1], steps=8)
    page.mouse.up()
    page.locator(".lf-fab-input").fill("The seam I pointed at.")
    with sending(page, "the seam drawing"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": target}
    assert page.locator("#bg-choice-street").get_attribute("chosen") is None
    assert page.locator("#bg-choice-trail").get_attribute("chosen") is None


def test_an_active_stroke_re_resolves_a_replaced_target(browser, serve):
    """Projection may replace an anchored element during pointer capture; the stroke
    follows the same semantic target without minting invalid geometry."""
    page = open_page(browser, serve(TARGETS_PAGE))
    target = page.locator("#prose")
    box = target.bounding_box()
    start = (box["x"] + 30, box["y"] + box["height"] / 2)
    page.mouse.move(*start)
    page.keyboard.press("w")
    page.mouse.down()
    target.evaluate("el => el.replaceWith(el.cloneNode(true))")
    page.mouse.move(start[0] + 120, start[1], steps=8)
    page.mouse.up()

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    page.locator(".lf-fab-input").fill("The replaced target still owns this.")
    with sending(page, "the replacement drawing"):
        page.keyboard.press("ControlOrMeta+Enter")
    (stroke,) = events_model.read_events(serve.page_dir)[-1]["drawing"]["strokes"]
    assert all(coordinate is not None for point in stroke for coordinate in point)
    assert len(stroke) >= 2


def test_an_unsent_drawing_survives_reload_before_it_has_words(browser, serve):
    """The stroke is part of the comment draft. It persists as soon as it is captured,
    even when the optional explanatory text is still empty."""
    page = open_page(browser, serve(TARGETS_PAGE))

    draw_over(page, page.locator("#prose"))
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_have_value("")

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_value("")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "note"


def test_a_malformed_page_drawing_draft_keeps_its_words_without_the_mark(
    browser, serve
):
    """Persisted draft payload is an external boundary. Invalid drawing geometry is
    ignored while the independently valid words remain sendable."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate(
        """record => localStorage.setItem('lf-draft:general', JSON.stringify(record))""",
        {
            "text": "Keep these words.",
            "attempt": "a" * 32,
            "base": None,
            "payload": {
                "drawing": {"format": "leaf-drawing/2", "strokes": "not-strokes"}
            },
        },
    )

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    field = page.locator(".lf-general textarea")
    expect(field).to_have_value("Keep these words.")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    with sending(page, "the text-only recovered draft"):
        page.locator(".lf-general .lf-compose-submit").click()

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["text"] == "Keep these words."
    assert "drawing" not in event


def test_a_malformed_anchored_drawing_draft_keeps_its_words_without_the_mark(
    browser, serve
):
    """The selection draft has its own serialized envelope and applies the same
    drawing validation before page presentation or submission."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.evaluate(
        """record => {
          const anchor = {section: 'prose'};
          const ctx = 'composer:' + JSON.stringify([['section', 'prose']]);
          localStorage.setItem('lf-draft:' + ctx, JSON.stringify({
            text: JSON.stringify({
              text: 'Keep these anchored words.',
              anchor,
              suggest: false,
              about: null,
              drawing: {format: 'leaf-drawing/2', strokes: [[[0, 0]]]},
              touched: Date.now(),
            }),
            attempt: record.attempt,
            base: null,
          }));
        }""",
        {"attempt": "b" * 32},
    )

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    expect(field).to_have_value("Keep these anchored words.")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    with sending(page, "the text-only recovered anchored draft"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    assert event["text"] == "Keep these anchored words."
    assert "drawing" not in event


def test_a_drawing_can_be_sent_without_words(browser, serve):
    """The ink is the comment's content, so its normal send action works while the
    accompanying text field is empty. Its thread does not repeat contextless ink."""
    page = open_page(browser, serve(TARGETS_PAGE))

    draw_over(page, page.locator("#prose"))
    field = page.locator(".lf-fab-input")
    expect(field).to_have_value("")
    expect(field).to_be_focused()
    expect(
        page.locator(".lf-composer .lf-compose-field .lf-compose-submit")
    ).to_have_attribute("aria-disabled", "false")
    with sending(page, "the drawing-only comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert "text" not in event
    assert event["drawing"]["format"] == "leaf-drawing/2"
    thread = page.get_by_role("dialog", name=re.compile("Conversation for"))
    expect(thread).to_be_visible()
    expect(page.locator(".lf-drawing-preview")).to_have_count(0)
    expect(thread.locator(".lf-drawing-reference")).to_have_text("Drawing comment")
    expect(page.locator("#prose")).not_to_have_class(re.compile(r"\blf-mark-el\b"))


def test_an_inline_conversation_keeps_drawing_context_on_the_page(browser, serve):
    """A widget-owned conversation leaves the drawing over its page target instead of
    showing the detached stroke again inside the conversation."""
    url = serve(CONVERSATION_DIFF_PAGE)
    drawing = {
        "format": "leaf-drawing/2",
        "strokes": [[[-20, 74], [50, 10], [120, 74]]],
    }
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "cd-q"},
            "drawing": drawing,
        },
    )

    page = open_page(browser, live_url(url))
    expect(
        page.locator("#cd-q .lf-conversation-body .lf-drawing-preview")
    ).to_have_count(0)
    expect(page.locator("#cd-q .lf-drawing-reference")).to_have_text("Drawing comment")
    expect(page.locator(".lf-drawing-posted")).to_have_count(1)
    expect(page.locator("#cd-q")).not_to_have_class(re.compile(r"\blf-mark-el\b"))


def test_an_unsent_drawing_stands_down_when_its_data_revision_changes(browser, serve):
    """Draft ink consumes the anchor pass's outdated reading instead of stretching
    itself over the text-document widget after its original datum version disappears."""
    page = open_data_revision_diff(browser, serve)
    target = page.locator(
        "lf-diff [data-line-type='change-deletion'][data-lf-datum]"
    ).first

    draw_over(page, target)
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    data_model.cmd_data_set(
        serve.page_dir,
        "drawing-patch",
        UPDATED_DATA_REVISION_DIFF,
    )
    told(page)

    expect(page.locator(".lf-drawing-pending")).to_have_count(0)
    expect(page.locator(".lf-fab-input")).to_be_visible()


def test_a_posted_drawing_stands_down_without_a_false_page_reference(browser, serve):
    """When a data revision detaches a drawing target, its thread still names the
    drawing without claiming that the suppressed stroke is visible on the page."""
    page = open_data_revision_diff(browser, serve)
    target = page.locator(
        "lf-diff [data-line-type='change-deletion'][data-lf-datum]"
    ).first

    draw_over(page, target)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    with sending(page, "the data-anchored drawing"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-drawing-posted")).to_have_count(1)

    data_model.cmd_data_set(
        serve.page_dir,
        "drawing-patch",
        UPDATED_DATA_REVISION_DIFF,
    )
    told(page)

    expect(page.locator(".lf-drawing-posted")).to_have_count(0)
    references = page.locator(".lf-drawing-reference")
    expect(references.first).to_have_text("Drawing comment")
    assert set(references.all_text_contents()) == {"Drawing comment"}
