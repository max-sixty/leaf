"""Drawing-comment browser journeys."""

import json
import re
from io import BytesIO

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, wait_for
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from PIL import Image, ImageChops
from playwright.sync_api import expect
from render_cases_interaction import (
    THREAD_DIFF_PAGE,
    live_url,
)
from render_cases_navigation import (
    TARGETS_PAGE,
    UNDO_PAGE,
)
from render_harness import (
    FEATURE_GALLERY,
    draft_key,
    leaf_page,
    nudge,
    open_page,
    panel_settled,
    resized,
    sending,
    stamp_page,
    told,
    write,
)
from test_render_threads import paste_image

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
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
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
    and the accepted comment keeps its ink positioned over that anchor. The record
    carries the window it was drawn in, its layout viewport and color scheme, which
    is what lays the page out again for the agent's picture of it."""
    url = serve(FEATURE_GALLERY)
    page = open_page(browser, url, color_scheme="dark")
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
    write(field, "This bend is the part I mean.")
    with sending(page, "the drawing comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert event["anchor"] == {"section": "bg-choice-trail"}
    assert event["text"] == "This bend is the part I mean."
    drawing = event["drawing"]
    assert drawing["format"] == "leaf-drawing/3"
    assert drawing["viewport"] == page.evaluate(
        "[document.documentElement.clientWidth, document.documentElement.clientHeight]"
    )
    assert drawing["scheme"] == "dark"
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
    # Ink stacks as page paint, under a covering surface, in the stand that carries it.
    stacking = mark.evaluate(
        "el => ({stand: el.closest('.lf-paint-stand')?.className,"
        " z: getComputedStyle(el.closest('.lf-paint-stand')).zIndex})"
    )
    assert stacking["z"] == "8890", stacking
    stable_mark = mark.element_handle()
    # A state read repaints the marks, as an anchor repaint and a size notice also do.
    # This one describes ink that has not moved, so the mark the user is looking at has
    # to be the same node afterwards.
    nudge(serve.page_dir)
    told(page)
    rendered(page)
    assert stable_mark.evaluate("node => node.isConnected"), (
        "a repaint describing unchanged ink must keep the mark it already painted"
    )
    relation = mark_relation(page, posted, "#bg-choice-trail")
    page.evaluate("scrollBy(0, 100)")
    rendered(page)
    assert mark_relation(page, posted, "#bg-choice-trail") == pytest.approx(
        relation, abs=0.02
    )
    # The scroll carries the mark rather than a repaint redrawing it.
    assert stable_mark.evaluate("node => node.isConnected")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert mark_relation(page, posted, "#bg-choice-trail") == pytest.approx(
        relation, abs=0.02
    )
    expect(target).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(page.locator(".lf-thread-panel .lf-drawing-reference")).to_have_text(
        "Drawing comment"
    )

    returned = open_page(browser, url)
    expect(returned.locator(posted)).to_have_count(1)
    assert mark_relation(returned, posted, "#bg-choice-trail") == pytest.approx(
        relation, abs=0.02
    )


NATIVE_FRAME_PAGE = leaf_page(
    "anonymous visual frames",
    '<h1 id="title">Sketches</h1><figure id="visuals">'
    '<svg viewBox="20 30 400 160"><path d="M20 110 H420" stroke="blue" /></svg>'
    '<svg viewBox="20 30 400 160"><path d="M20 110 H420" stroke="red" /></svg>'
    "<figcaption>Two independently framed sketches.</figcaption></figure>",
    head="<style>#visuals {width:80vw;margin:0}"
    "#visuals svg {display:block;width:100%;height:auto}</style>",
)


def native_ink_start(page, selector, mark=".lf-drawing-pending"):
    """Read ink back in the native SVG viewport, independent of page layout."""
    return page.evaluate(
        """([selector, mark]) => {
          const svg = document.querySelector(selector);
          const path = document.querySelector(`${mark} path`);
          const point = path.getPointAtLength(0).matrixTransform(path.getScreenCTM());
          const local = point.matrixTransform(svg.getScreenCTM().inverse());
          return [local.x, local.y];
        }""",
        [selector, mark],
    )


def test_a_drawing_uses_its_anonymous_svg_inside_its_semantic_figure(browser, serve):
    """Two native visuals share one semantic comment seat. The selected visual's
    user space carries ink through camera pan, resize, addition and replay, even
    with a nonzero viewBox origin and a zero-height path."""
    url = serve(NATIVE_FRAME_PAGE)
    page = open_page(browser, url)
    second = page.locator("#visuals svg").nth(1)
    draw_over(page, second)
    start = native_ink_start(page, "#visuals svg:nth-of-type(2)")
    assert start == pytest.approx([108, 129.2], abs=0.03)
    second.evaluate("""async svg => {
      const {layoutChanged} = await import('/runtime/widget-elements.js');
      svg.setAttribute('viewBox', '50 50 400 160');
      await layoutChanged(svg);
    }""")
    assert native_ink_start(page, "#visuals svg:nth-of-type(2)") == pytest.approx(
        start, abs=0.03
    ), "a camera pan moves the graphic and its ink together"
    page.locator("#visuals").evaluate("""el => {
      el.querySelector('figcaption').textContent += ' Longer caption.'.repeat(20);
      const chrome = document.createElement('aside');
      chrome.dataset.lfRuntime = '';
      el.prepend(chrome);
    }""")
    page.set_viewport_size({"width": 680, "height": 720})
    rendered(page)
    assert native_ink_start(page, "#visuals svg:nth-of-type(2)") == pytest.approx(
        start, abs=0.03
    )
    # Draw on the same graphic points after the camera moved by 30x20 user units.
    stroke_over(
        page, second, points=tuple((x - 30 / 400, y - 20 / 160) for x, y in STROKE)
    )
    with sending(page, "the second anonymous sketch"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "visuals"}
    assert event["drawing"]["box"] == [400, 160]
    assert event["drawing"]["frame"] == {
        "root": "figure",
        "path": [{"tag": "svg", "index": 1, "siblings": 3}],
    }
    assert event["drawing"]["strokes"][0][0] == pytest.approx(start, abs=0.03)
    assert event["drawing"]["strokes"][0][0] == pytest.approx(
        event["drawing"]["strokes"][1][0], abs=0.03
    )
    page.reload(wait_until="load")
    wait_until_ready(page)
    posted = f'.lf-drawing-posted[data-thread="{event["id"]}"]'
    assert native_ink_start(
        page, "#visuals svg:nth-of-type(2)", posted
    ) == pytest.approx(start, abs=0.03)


@pytest.mark.parametrize("change", ["remove", "insert"])
def test_a_missing_native_frame_cannot_retarget_another_svg(browser, serve, change):
    """A removed frame or inserted same-tag sibling parks draft ink rather than
    transferring the mark to whichever visual now occupies its child index."""
    page = open_page(browser, serve(NATIVE_FRAME_PAGE))
    draw_over(page, page.locator("#visuals svg").nth(1))
    before = mark_box(page, ".lf-drawing-pending")
    page.locator("#visuals").evaluate(
        """(el, change) => {
          const svg = el.querySelectorAll('svg')[1];
          if (change === 'remove') svg.remove();
          else el.prepend(svg.cloneNode(true));
        }""",
        change,
    )
    page.set_viewport_size({"width": 1000, "height": 720})
    rendered(page)
    expect(page.locator(".lf-drawing-pending")).to_have_count(0)
    expect(page.locator(".lf-drawing-parked")).to_have_count(1)
    after = mark_box(page, ".lf-drawing-parked")
    assert [after[key] for key in ("width", "height")] == pytest.approx(
        [before[key] for key in ("width", "height")], abs=0.03
    )
    page.get_by_role("button", name="Remove drawing").click()
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)


@pytest.mark.parametrize(
    "position", ["right 10px bottom 20px", "calc(100% - 10px) calc(100% - 20px)"]
)
def test_native_image_frames_follow_object_fit_and_position(browser, serve, position):
    """The painted content, including letterboxing and CSS edge offsets, owns
    native image points through resizing instead of the semantic figure's box."""
    source = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "width='400' height='100'%3E%3Cpath d='M0 50H400' stroke='red'/%3E%3C/svg%3E"
    )
    html = leaf_page(
        "positioned image",
        f'<h1 id="title">Image</h1><figure id="visuals"><img src="{source}" '
        'alt="Horizontal reference line"></figure>',
        head="<style>#visuals {margin:0;width:80vw} #visuals img {display:block;"
        f"width:100%;height:400px;object-fit:contain;object-position:{position}"
        "}</style>",
    )
    page = open_page(browser, serve(html))
    image = page.locator("#visuals img")
    image.evaluate("el => el.decode()")
    box = image.bounding_box()
    page.mouse.move(box["x"] + 100, box["y"] + 100)
    page.keyboard.press("w")
    trace(page, [(box["x"] + 100, box["y"] + 100), (box["x"] + 150, box["y"] + 110)])
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    page.set_viewport_size({"width": 680, "height": 720})
    rendered(page)
    current = image.bounding_box()
    relation = mark_relation(page, ".lf-drawing-pending", "#visuals img")
    # contain's scale is width/400 here; y includes bottom20px letterboxing.
    old_scale = box["width"] / 400
    new_scale = current["width"] / 400
    local_x = (100 + 10) / old_scale
    local_y = (100 - (400 - 100 * old_scale - 20)) / old_scale
    assert relation[:2] == pytest.approx(
        [local_x * new_scale - 10, local_y * new_scale + 400 - 100 * new_scale - 20],
        abs=0.03,
    )
    with sending(page, "the positioned image"):
        page.keyboard.press("ControlOrMeta+Enter")
    drawing = events_model.read_events(serve.page_dir)[-1]["drawing"]
    assert drawing["box"] == [400, 100]
    assert drawing["frame"]["path"] == [{"tag": "img", "index": 0, "siblings": 1}]


@pytest.mark.parametrize("engine", ["firefox_browser", "webkit_browser"])
def test_native_frames_resolve_css_positions_in_supported_engines(
    request, serve, engine
):
    """Browser CSS math resolves native offsets, including negative cover space,
    without experimental Typed OM or repeat geometry-read DOM mutations."""
    source = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "width='400' height='100'%3E%3C/svg%3E"
    )
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Native offsets",
                f'<h1>Offsets</h1><img id="pixels" src="{source}" alt="Reference" style="width:300px;height:200px">',
            )
        ),
    )
    results = page.evaluate("""async () => {
      const {elementFrame} = await import('/runtime/geometry.js');
      const image = document.querySelector('#pixels');
      await image.decode();
      const readings = [];
      for (const fit of ['contain', 'cover']) {
        for (const position of [
          'right 10px bottom 20px',
          'calc(100% - 10px) calc(100% - 20px)',
          'min(100%, 30px) max(0px, calc(100% - 20px))',
          'clamp(10px, 50%, 30px) clamp(-20px, 50%, 20px)',
        ]) {
          image.style.objectFit = fit;
          image.style.objectPosition = position;
          const observer = new MutationObserver(() => {});
          observer.observe(document.body, {subtree:true, childList:true, attributes:true});
          const frame = elementFrame(image);
          observer.takeRecords();
          elementFrame(image);
          const repeatMutations = observer.takeRecords().length;
          observer.disconnect();
          readings.push({fit, position, repeatMutations,
            origin:[frame.matrix.e-frame.box.left, frame.matrix.f-frame.box.top],
            scale:[frame.matrix.a,frame.matrix.d], size:[frame.width,frame.height]});
        }
      }
      return readings;
    }""")
    for result in results:
        cover = result["fit"] == "cover"
        free_x, free_y = (-500, 0) if cover else (0, 125)
        if result["position"].startswith("min"):
            expected = [min(free_x, 30), max(0, free_y - 20)]
        elif result["position"].startswith("clamp"):
            expected = [max(10, min(free_x / 2, 30)), max(-20, min(free_y / 2, 20))]
        else:
            expected = [free_x - 10, free_y - 20]
        assert result["origin"] == pytest.approx(expected, abs=0.03), result
        assert result["scale"] == pytest.approx([2, 2] if cover else [0.75, 0.75])
        assert result["size"] == [400, 100]
        assert result["repeatMutations"] == 0


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


@pytest.mark.parametrize("change", ["wrap", "grow"])
def test_drawing_ink_keeps_its_coordinates_when_its_target_changes_size(
    browser, serve, change
):
    """A one-pixel wrap and unrelated growth cannot stretch a drawing's pixels."""
    page = open_page(browser, serve(WORDS_PAGE))
    line = page.locator("#line")
    line.evaluate("""el => {
      const range = document.createRange();
      range.selectNodeContents(el);
      el.style.width = `${range.getBoundingClientRect().width + 0.5}px`;
    }""")
    drawn_at = line.bounding_box()
    draw_over(page, line)
    mark = ".lf-drawing-pending"
    expect(page.locator(mark)).to_have_count(1)
    relation = mark_relation(page, mark, "#line")
    if change == "wrap":
        line.evaluate("el => el.style.width = `${parseFloat(el.style.width) - 1}px`")
    else:
        line.evaluate("el => el.style.paddingBottom = '40px'")
    rendered(page)
    changed = line.bounding_box()
    assert changed["height"] > drawn_at["height"] + 10, (drawn_at, changed)
    assert mark_relation(page, mark, "#line") == pytest.approx(relation, abs=0.02)


def test_drawing_strokes_keep_their_pixels_across_resize_addition_send_and_replay(
    browser, serve
):
    """Every stroke keeps its target-local pixels even when later strokes are drawn
    after a paragraph reflows, and sending, undoing and reloading use that same frame.
    """
    url = serve(TARGETS_PAGE)
    page = open_page(browser, url)
    prose = page.locator("#prose")
    wide = page.viewport_size
    draw_over(page, prose)
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    original_path = page.locator(".lf-drawing-pending path").get_attribute("d")
    drawn_at = prose.bounding_box()
    original_relation = mark_relation(page, ".lf-drawing-pending", "#prose")

    page.set_viewport_size({"width": 420, "height": wide["height"]})
    rendered(page)
    narrow = prose.bounding_box()
    assert narrow["width"] < 0.8 * drawn_at["width"]
    assert narrow["height"] > drawn_at["height"], "the paragraph must reflow"
    assert mark_relation(page, ".lf-drawing-pending", "#prose") == pytest.approx(
        original_relation, abs=0.02
    )
    stroke_over(page, prose, points=((0.3, 0.3), (0.5, 0.7), (0.7, 0.3)))
    path = page.locator(".lf-drawing-pending path").get_attribute("d")
    assert mark_relation(page, ".lf-drawing-pending", "#prose")[2] == pytest.approx(
        max(drawn_at["width"] * 0.78, narrow["width"] * 0.7)
        - min(drawn_at["width"] * 0.22, narrow["width"] * 0.3),
        abs=0.02,
    ), "a pending drawing wider than the viewport keeps its full width"
    assert path.startswith(original_path + " M"), (
        "adding ink cannot reframe earlier ink"
    )
    page.get_by_role("button", name="Undo last stroke").click()
    expect(page.locator(".lf-drawing-pending path")).to_have_attribute(
        "d", original_path
    )
    stroke_over(page, prose, points=((0.3, 0.3), (0.5, 0.7), (0.7, 0.3)))
    with sending(page, "the resized drawing"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    drawing = event["drawing"]
    first, second = drawing["strokes"]
    assert first[0] == pytest.approx(
        [drawn_at["width"] * STROKE[0][0], drawn_at["height"] * STROKE[0][1]], abs=0.02
    )
    assert second[0] == pytest.approx(
        [narrow["width"] * 0.3, narrow["height"] * 0.3], abs=0.02
    )
    posted = f'.lf-drawing-posted[data-thread="{event["id"]}"]'
    expect(page.locator(posted)).to_have_count(1)
    relation = mark_relation(page, posted, "#prose")
    page.set_viewport_size(wide)
    rendered(page)
    assert mark_relation(page, posted, "#prose") == pytest.approx(relation, abs=0.02)
    page.reload()
    wait_until_ready(page)
    expect(page.locator(posted)).to_have_count(1)
    assert mark_relation(page, posted, "#prose") == pytest.approx(relation, abs=0.02)


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
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
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

    # An arrow can capture a long paragraph from its first word to its far corner.
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
    capture = sent("the arrow")["drawing"]["says"]
    assert isinstance(capture, str) and capture.startswith("Arrow ")
    assert whole.startswith(capture.removesuffix("…"))

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


# The swatch is taller than the pane that scrolls it, and its foot is a blue band: the
# user scrolls the pane to the bottom and draws on the band, so a picture opened with the
# pane at its top has to bring the ink, not just the swatch, back into view.
SWATCH_PAGE = leaf_page(
    "drawn swatch",
    '<h1 id="t">Swatch</h1><p id="lede">The swatch below is half the window wide.</p>'
    '<div id="pane"><div id="filler"></div><div id="swatch"></div></div>',
    head="<style>#pane { height: 320px; overflow: auto }"
    " #filler { height: 600px }"
    " #swatch { width: 50vw; height: 600px;"
    " background: linear-gradient(rgb(0, 200, 0) 84%, rgb(0, 0, 220) 84%) }</style>",
)
# Across the band, which runs from 84% of the swatch's height to its foot.
BAND_STROKE = ((0.22, 0.95), (0.5, 0.88), (0.78, 0.95))


def test_an_active_stroke_keeps_its_start_when_its_pane_scrolls(browser, serve):
    """Sampling another point cannot move earlier ink off its scrolled content."""
    page = open_page(browser, serve(SWATCH_PAGE))
    page.locator("#pane").evaluate("el => el.scrollTop = 600")
    rendered(page)
    swatch = page.locator("#swatch")
    box = swatch.bounding_box()
    x, y = box["x"] + 40, box["y"] + 50
    page.mouse.move(x, y)
    page.keyboard.press("w")
    page.mouse.down()
    page.mouse.move(x + 50, y + 10)
    expect(page.locator(".lf-drawing-active")).to_have_count(1)

    def start():
        return page.evaluate("""() => {
          const path = document.querySelector('.lf-drawing-active path');
          const point = path.getPointAtLength(0).matrixTransform(path.getScreenCTM());
          const box = document.querySelector('#swatch').getBoundingClientRect();
          return [point.x - box.x, point.y - box.y];
        }""")

    before = start()
    page.locator("#pane").evaluate("el => el.scrollTop += 30")
    rendered(page)
    moved = swatch.bounding_box()
    assert moved["y"] == pytest.approx(box["y"] - 30, abs=0.02)
    page.mouse.move(x + 70, y + 20)
    rendered(page)
    assert start() == pytest.approx(before, abs=0.02)
    page.mouse.up()


def test_a_drawing_is_pictured_in_the_window_it_was_drawn_in(browser, serve):
    """`leaf page picture` lays the comment's revision out again in the window the
    drawing was made in, whatever window or version the page is in since, and paints the
    comment's ink, and no later comment's, over the element it was drawn on, with the
    ink scrolled into view inside the pane holding it: the swatch, half the window wide,
    is as wide as it was then, and the ink keeps its place on the band."""
    page = open_page(browser, serve(SWATCH_PAGE), color_scheme="dark")
    page.set_viewport_size({"width": 800, "height": 600})
    page.locator("#pane").evaluate("pane => { pane.scrollTop = pane.scrollHeight; }")
    rendered(page)
    swatch = page.locator("#swatch")
    draw_over(page, swatch, points=BAND_STROKE)
    with sending(page, "the drawing on the swatch"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "swatch"}
    ink = page.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"] path')
    ink_color = ink.evaluate("path => getComputedStyle(path).stroke")
    page.set_viewport_size({"width": 1200, "height": 900})
    stamp_page(serve.page_dir, SWATCH_PAGE.replace("50vw", "25vw"), "Narrow the swatch")
    # A later drawing on the same swatch, just above the band and inside the picture's
    # crop, which the user had not drawn when they drew the first.
    box_width, box_height = event["drawing"]["box"]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": event["revision"],
            "anchor": event["anchor"],
            "drawing": {
                **event["drawing"],
                "strokes": [
                    [
                        [0.3 * box_width, 0.78 * box_height],
                        [0.7 * box_width, 0.78 * box_height],
                    ]
                ],
            },
        },
    )

    pictured = CliRunner().invoke(
        cli_model.cli, ["page", "picture", str(serve.page_dir), event["id"]]
    )
    assert pictured.exit_code == 0, pictured.output
    image = Image.open(pictured.output.strip()).convert("RGB")

    def where(color):
        """The bounding box of the picture's pixels within a few levels of `color`."""
        red, green, blue = ImageChops.difference(
            image, Image.new("RGB", image.size, color)
        ).split()
        furthest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        return furthest.point(lambda level: 255 if level <= 8 else 0).getbbox()

    green = where((0, 200, 0))
    band = where((0, 0, 220))
    drawn = where(tuple(int(part) for part in re.findall(r"\d+", ink_color)[:3]))
    assert green and band and drawn, (green, band, drawn)
    # Only this comment's ink: the later drawing above the band is not painted.
    assert drawn[1] >= band[1], (drawn, band)
    # 50vw of the 800px window the drawing was made in, on the revision it was made on:
    # 576px, cut at the crop, in the page's window now, and 200px on its version now.
    assert green[2] - green[0] == pytest.approx(400, abs=2)
    assert image.width < 800 and image.height < 600
    # The band is 16% of the 600px swatch, and the ink crosses it where it was drawn.
    width, height = band[2] - band[0], band[3] - band[1]
    assert height == pytest.approx(96, abs=2)
    (left, low), (_, high), (right, _) = BAND_STROKE
    band_top = 0.84
    assert (drawn[0] - band[0]) / width == pytest.approx(left, abs=0.03)
    assert (drawn[2] - band[0]) / width == pytest.approx(right, abs=0.03)
    assert (drawn[1] - band[1]) / height == pytest.approx(
        (high - band_top) / (1 - band_top), abs=0.05
    )
    assert (drawn[3] - band[1]) / height == pytest.approx(
        (low - band_top) / (1 - band_top), abs=0.05
    )
    # Drawn in the dark scheme: the page beside the swatch is dark.
    assert sum(image.getpixel((2, 2))) < 200

    missing = CliRunner().invoke(
        cli_model.cli, ["page", "picture", str(serve.page_dir), "nope"]
    )
    assert missing.exit_code != 0 and "no message nope" in missing.output
    # An element the revision does not hold, as one a data source drew and has since
    # dropped, leaves no ink to picture.
    lost = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": event["revision"],
            "anchor": {"section": "gone"},
            "drawing": event["drawing"],
        },
    )
    unresolved = CliRunner().invoke(
        cli_model.cli, ["page", "picture", str(serve.page_dir), lost["id"]]
    )
    assert unresolved.exit_code != 0
    assert "its element #gone does not resolve" in unresolved.output


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
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
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
    submit = page.locator(".lf-composer .lf-compose-submit")
    expect(submit).to_have_attribute("aria-disabled", "false")
    with sending(page, "the drawing the keyboard sent"):
        page.keyboard.press("ControlOrMeta+Enter")
    assert page.evaluate("() => window.__releaseHeldTimers()")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment", event
    assert event["drawing"]["strokes"], event


def test_a_stroke_in_empty_space_belongs_to_the_nearest_element(browser, serve):
    """Whitespace is part of the drawable page plane. A stroke that starts over no
    addressable element belongs to the nearest one on screen, so its comment box opens
    beside the ink rather than in Threads, and the drawing persists, joins and undoes as
    any other."""
    page = open_page(browser, serve(TARGETS_PAGE))
    fig = page.locator("#fig")
    box = fig.bounding_box()
    point = page.evaluate(
        """([x, y]) => {
          const hit = document.elementFromPoint(x, y);
          return {
            x, y,
            tag: hit?.tagName ?? "",
            item: hit?.closest("main > *")?.id ?? "",
          };
        }""",
        [box["x"] + 40, box["y"] + box["height"] + 50],
    )
    assert point["tag"] in {"HTML", "BODY", "MAIN"}, point
    assert not point["item"], point
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
    page.mouse.down()
    page.mouse.move(point["x"] + 90, point["y"] - 30, steps=8)
    page.mouse.move(point["x"] + 150, point["y"] + 20, steps=8)
    page.mouse.up()

    pending = page.locator(".lf-drawing-pending path")
    expect(pending).to_have_count(1)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect(page.locator(".lf-drawing-mark")).to_have_count(1)
    # The reloaded page reopens the draft's box with the user in it, so `w` would be a
    # letter there; Escape puts the box away first. The new Draw mode session's stroke
    # then joins the kept drawing.
    expect(field).to_be_focused()
    page.keyboard.press("Escape")
    page.mouse.move(point["x"], point["y"])
    page.keyboard.press("w")
    page.mouse.down()
    page.mouse.move(point["x"] + 60, point["y"] + 30, steps=8)
    page.mouse.up()
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))
    page.mouse.move(point["x"], point["y"] - 20)
    page.mouse.down()
    page.mouse.move(point["x"] + 40, point["y"] + 40, steps=8)
    page.mouse.up()
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*M[^M]*$"))
    page.get_by_role("button", name="Undo last stroke").click()
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))

    expect(field).to_have_js_property("value", "")
    with sending(page, "the drawing beside the figure"):
        page.locator(".lf-composer .lf-compose-field .lf-compose-submit").evaluate(
            "button => button.click()"
        )
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert event["anchor"] == {"section": "fig"}
    assert "text" not in event and "at" not in event["drawing"]
    assert len(event["drawing"]["strokes"]) == 2
    expect(
        page.locator(f'.lf-drawing-posted[data-thread="{event["id"]}"]')
    ).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth") == scroll_width


def test_an_anchored_drawing_draft_repaints_in_another_tab(browser, serve, one_user):
    """The anchored composer's draft watcher repaints its stroke as well as its target
    when another tab adds drawing geometry to the shared draft, and takes the draft up
    as it now stands rather than as a change of its own to take back."""
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

    # The other tab's stroke is the draft this box takes up, not a step its ⌘Z takes
    # back.
    remote.locator(".lf-fab-input").focus()
    remote.keyboard.press("ControlOrMeta+z")
    remote.keyboard.type("y")
    expect(remote.locator(".lf-fab-input")).to_have_js_property("value", "y")
    expect(remote_path).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))

    # With its box moved to another drawing, the prose drawing is parked and its own
    # watch gone; the other tab taking a stroke back still repaints it here.
    remote.keyboard.press("Escape")
    remote.keyboard.press("Escape")
    draw_over(remote, remote.locator("#fig"))
    parked = remote.locator(".lf-drawing-parked path")
    expect(parked).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))
    local.get_by_role("button", name="Undo last stroke").click()
    expect(parked).to_have_attribute("d", re.compile(r"^M[^M]*$"))


def test_strokes_join_one_drawing_until_it_is_sent_and_escape_leaves(browser, serve):
    """Draw mode outlasts a stroke. A later stroke joins the drawing its session opened,
    in that drawing's frame wherever it starts, and keeps joining it after Escape puts its
    box away or the user leaves and re-enters the mode; once the draft is sent the next
    stroke starts another, and only Escape leaves the mode. Unsent ink never leaves the
    page: with its box put away it stands parked, in and out of the mode, so the drawing
    a stroke joins is the one the user can see."""
    page = open_page(browser, serve(TARGETS_PAGE))
    prose = page.locator("#prose")
    draw_over(page, prose)
    pending = page.locator(".lf-drawing-pending path")
    parked = page.locator(".lf-drawing-parked path")
    expect(pending).to_have_count(1)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")

    # Begun over another element, the stroke still belongs to the prose drawing.
    start = stroke_over(page, page.locator("#fig"))
    origin = prose.bounding_box()
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))
    expect(field).to_be_focused()
    write(field, "All of these.")

    # Escape puts the box away and keeps its draft, ink and all; the next stroke joins
    # that draft.
    page.keyboard.press("Escape")
    expect(pending).to_have_count(0)
    expect(parked).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    stroke_over(page, page.locator("#fig"), points=((0.3, 0.3), (0.5, 0.7), (0.7, 0.3)))
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*M[^M]*$"))
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "All of these.")
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
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    stroke_over(page, page.locator("#fig"))
    expect(pending).to_have_count(1)
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*$"))
    expect(field).to_be_focused()

    # The composer the stroke opened stands inside the mode, so it comes off first.
    page.keyboard.press("Escape")
    expect(pending).to_have_count(0)
    expect(parked).to_have_count(1)
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    page.keyboard.press("Escape")
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-live")).to_contain_text("Draw mode off")
    expect(parked).to_have_attribute("d", re.compile(r"^M[^M]*$"))

    # A new Draw mode session shows the draft before its first stroke, and draws into
    # it rather than over it.
    page.keyboard.press("w")
    expect(parked).to_have_attribute("d", re.compile(r"^M[^M]*$"))
    page.keyboard.press("w")
    draw_over(page, page.locator("#fig"), points=((0.3, 0.3), (0.5, 0.7), (0.7, 0.3)))
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*M[^M]*$"))
    expect(parked).to_have_count(0)


def test_a_drawing_takes_back_its_strokes_and_comes_off_its_comment(browser, serve):
    """Every route takes back the last stroke: ⌘Z in its composer while a stroke is the
    draft's latest change, `z` or ⌘Z in Draw mode with the box put away, and the
    composer's own control. In the composer ⌘Z and ⌘⇧Z walk strokes and words as one
    history, in the order they were made, and a press on the drawing's controls is a step
    in it too. Taking back the last stroke removes the drawing, as the composer's own
    removal does at once, and either leaves the words to send alone. In Draw mode `z` is
    the stroke's undo and never the page's, drawing or not."""
    page = open_page(browser, serve(UNDO_PAGE))
    with sending(page, "the pick"):
        page.locator("#opt-a").click()
    picked = len(events_model.read_events(serve.page_dir))
    heading = page.locator("#h")
    tile = page.locator(".lf-composer-drawing [role=img]")
    pending = page.locator(".lf-drawing-pending path")
    parked = page.locator(".lf-drawing-parked path")
    field = page.locator(".lf-fab-input")
    other = ((0.3, 0.3), (0.5, 0.7), (0.7, 0.3))

    # The stroke that opens the box is the draft's first change, and the box's to take
    # back and make again.
    draw_over(page, heading)
    field.focus()
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_count(0)
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    # Redo is pressed as a keyboard sends it, Shift making the key "Z": a "Shift+z"
    # press sends "z", which CodeMirror on Linux reads as Ctrl+Z, undo.
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 1 stroke")
    stroke_over(page, heading, points=other)
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 1 stroke")
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*$"))

    # Words typed after a stroke are the latest change, and a stroke drawn after the
    # words is: ⌘Z takes back each in turn, the words through the field's own history.
    stroke_over(page, heading, points=other)
    write(field, "Here.")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 1 stroke")
    stroke_over(page, heading, points=other)
    write(field, "Here.")
    stroke_over(page, heading)
    expect(tile).to_have_attribute("aria-label", "Drawing, 3 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    expect(field).to_have_js_property("value", "Here.")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")

    # The words' history orders them, not the words' text: words typed and taken out
    # again are the latest change, and words typed hard on a stroke's heels, which the
    # history would fold into the words before it, are a step of their own.
    page.keyboard.type("x")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("End")
    page.keyboard.press("Backspace")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "x")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    page.keyboard.type("a")
    stroke_over(page, heading, steps=2, points=other)
    field.focus()
    page.keyboard.type("b")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "a")
    expect(tile).to_have_attribute("aria-label", "Drawing, 3 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")

    # ⌘⇧Z makes the steps again in the same order, and a new change drops what was
    # taken back before it, so redo never brings words back past a later stroke.
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(field).to_have_js_property("value", "a")
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 3 strokes")
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(field).to_have_js_property("value", "ab")
    for _ in range(3):
        page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")
    stroke_over(page, heading, points=other)
    field.focus()
    page.keyboard.press("ControlOrMeta+Shift+Z")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    expect(field).to_have_js_property("value", "")
    write(field, "Here.")

    # With the box put away, ⌘Z or `z` takes back the strokes of the parked drawing,
    # and the last one takes the drawing; the pick `z` undoes outside the mode stands.
    page.keyboard.press("Escape")
    page.keyboard.press("ControlOrMeta+z")
    expect(parked).to_have_attribute("d", re.compile(r"^M[^M]*$"))
    page.keyboard.press("z")
    expect(parked).to_have_count(0)
    page.keyboard.press("z")
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-a")
    assert len(events_model.read_events(serve.page_dir)) == picked

    # The composer's controls: one stroke back, then the drawing off, the words kept.
    stroke_over(page, heading)
    stroke_over(page, heading, points=other)
    expect(field).to_have_js_property("value", "Here.")

    # A draft reopened after a reload starts its history as it stands: its drawing is
    # part of where ⌘Z starts, not a change to take back.
    page.reload()
    wait_until_ready(page)
    expect(field).to_have_js_property("value", "Here.")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    field.focus()
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 2 strokes")
    expect(field).to_have_js_property("value", "Here.")
    page.get_by_role("button", name="Undo last stroke").click()
    expect(tile).to_have_attribute("aria-label", "Drawing, 1 stroke")
    page.get_by_role("button", name="Remove drawing").click()
    expect(tile).to_have_count(0)
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    expect(field).to_be_focused()
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Drawing, 1 stroke")
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*$"))
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(tile).to_have_count(0)
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    with sending(page, "the words without their drawing"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["text"] == "Here."
    assert "drawing" not in event


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

    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    assert target.get_attribute("data-activated") is None
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "note"
    page.mouse.move(*point)
    page.mouse.down()
    page.keyboard.press("Escape")
    page.mouse.up()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-live")).to_contain_text("Draw mode off")
    assert target.get_attribute("data-activated") is None


def test_draw_mode_leaves_chrome_controls_usable(browser, serve):
    """The document plane is drawable, but a press on Leaf's chrome remains the
    control's gesture rather than becoming a drawing."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.press("w")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)


def test_draw_mode_keeps_the_separate_design_mode_binding(browser, serve):
    """Adding Draw on w does not move the existing layer-review mode off l."""
    page = open_page(browser, serve(TARGETS_PAGE))

    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    page.keyboard.press("l")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")


def test_draw_mode_leaves_inline_thread_controls_usable(browser, serve):
    """A page-widget shadow root retargets document pointer events to its host. The
    inline thread it contains remains Leaf chrome, not a drawable widget control."""
    url = serve(THREAD_DIFF_PAGE)
    append_carried_log_record(
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
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    assert reply.evaluate("el => getComputedStyle(el).cursor") != "crosshair"
    reply.click()

    expect(reply).to_be_focused()
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)


def test_draw_mode_leaves_widget_controls_usable(browser, serve):
    """An offered widget control keeps its pointer action and cursor in Draw mode."""
    page = open_page(browser, serve(FEATURE_GALLERY))
    option = page.locator("#bg-choice-trail")
    control = option.locator(".lf-pick")
    control.scroll_into_view_if_needed()
    box = control.bounding_box()
    point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*point)
    page.keyboard.press("w")

    assert control.evaluate("el => getComputedStyle(el).cursor") != "crosshair"
    page.mouse.click(*point)

    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    expect(option).to_have_attribute("chosen", "")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)


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
    write(page.locator(".lf-fab-input"), "The seam I pointed at.")
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
    # Marked, so the replacement is a different element and not the same one written
    # again.
    target.evaluate(
        "el => { const next = el.cloneNode(true); next.dataset.replaced = ''; "
        "el.replaceWith(next); }"
    )
    page.mouse.move(start[0] + 120, start[1], steps=8)
    page.mouse.up()

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    write(page.locator(".lf-fab-input"), "The replaced target still owns this.")
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
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")

    page.reload(wait_until="load")
    wait_until_ready(page)

    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "note"


def test_a_malformed_anchored_drawing_draft_keeps_its_words_without_the_mark(
    browser, serve
):
    """The selection draft has its own serialized envelope and applies the same
    drawing validation before page presentation or submission."""
    page = open_page(browser, serve(TARGETS_PAGE))
    # The composer's draft is keyed on the passage it is on.
    ctx = "composer:" + json.dumps([["section", "prose"]], separators=(",", ":"))
    page.evaluate(
        """([key, record]) => {
          const anchor = {section: 'prose'};
          localStorage.setItem(key, JSON.stringify({
            text: JSON.stringify({
              text: 'Keep these anchored words.',
              anchor,
              suggest: false,
              about: null,
              drawing: {format: 'leaf-drawing/3', strokes: [[[0, 0]]]},
              touched: Date.now(),
            }),
            attempt: record.attempt,
            base: null,
          }));
        }""",
        [draft_key(page, ctx), {"attempt": "b" * 32}],
    )

    page.reload(wait_until="load")
    wait_until_ready(page)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    expect(field).to_have_js_property("value", "Keep these anchored words.")
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    with sending(page, "the text-only recovered anchored draft"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {"section": "prose"}
    assert event["text"] == "Keep these anchored words."
    assert "drawing" not in event


def test_a_drawing_can_be_sent_without_words(browser, serve):
    """The ink is the comment's content, so its normal send action works while the
    accompanying text field is empty. Its thread still names the drawing."""
    page = open_page(browser, serve(TARGETS_PAGE))

    draw_over(page, page.locator("#prose"))
    field = page.locator(".lf-fab-input")
    expect(field).to_have_js_property("value", "")
    expect(field).to_be_focused()
    expect(
        page.locator(".lf-composer .lf-compose-field .lf-compose-submit")
    ).to_have_attribute("aria-disabled", "false")
    with sending(page, "the drawing-only comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert "text" not in event
    assert event["drawing"]["format"] == "leaf-drawing/3"
    thread = page.get_by_role("dialog", name=re.compile("Thread for"))
    expect(thread).to_be_visible()
    expect(thread.locator(".lf-drawing-reference")).to_have_text("Drawing comment")
    expect(page.locator("#prose")).not_to_have_class(re.compile(r"\blf-mark-el\b"))


def test_an_inline_thread_keeps_drawing_context_on_the_page(browser, serve):
    """A widget-owned thread keeps the drawing over its page target and names it
    in the inline transcript."""
    url = serve(THREAD_DIFF_PAGE)
    drawing = {
        "format": "leaf-drawing/3",
        "strokes": [[[-20, 74], [50, 10], [120, 74]]],
        "box": [640.5, 96],
        "viewport": [1280, 720],
        "scheme": "light",
    }
    append_carried_log_record(
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
    expect(page.locator("#cd-q .lf-drawing-reference")).to_have_text("Drawing comment")
    expect(page.locator(".lf-drawing-posted")).to_have_count(1)
    expect(page.locator("#cd-q")).not_to_have_class(re.compile(r"\blf-mark-el\b"))


def test_an_unsent_drawing_stays_where_it_was_when_its_data_revision_changes(
    browser, serve
):
    """A revision that takes a draft's element away leaves its ink where the element last
    stood, dashed as detached, rather than stretched over the widget its anchor now falls
    back to or vanishing; the box can still take it off."""
    page = open_data_revision_diff(browser, serve)
    target = page.locator(
        "lf-diff [data-line-type='change-deletion'][data-lf-datum]"
    ).first

    draw_over(page, target)
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    before = mark_box(page, ".lf-drawing-pending")
    data_model.cmd_data_set(
        serve.page_dir,
        "drawing-patch",
        UPDATED_DATA_REVISION_DIFF,
    )
    told(page)

    expect(page.locator(".lf-drawing-pending")).to_have_count(0)
    expect(page.locator(".lf-drawing-parked")).to_have_count(1)
    after = mark_box(page, ".lf-drawing-parked")
    for side in ("x", "width", "height"):
        assert after[side] == pytest.approx(before[side], abs=1), (before, after)
    assert after["y"] + after["scrollY"] == pytest.approx(
        before["y"] + before["scrollY"], abs=1
    )
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.get_by_role("button", name="Remove drawing").click()
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)


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


def test_page_mode_keeps_visible_native_ink_and_exact_drawing_comment(browser, serve):
    source = leaf_page(
        "Page ink",
        '<h1>Page ink</h1><p id="subject" style="height:160px">Draw the bend beside these words.</p>',
    ).replace("<body>", '<body data-annotations="page">')
    page = open_page(browser, serve(source))
    target = page.locator("#subject")
    draw_over(page, target)
    pending = page.locator(".lf-drawing-pending")
    expect(pending).to_have_count(1)
    assert pending.evaluate(
        "el => el.getBoundingClientRect().width > 0 && getComputedStyle(el.querySelector('path')).strokeWidth === '3px'"
    )
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    write(editor, "The bend I mean")
    with sending(page, "the exact page-owned drawing"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["kind"] == "comment"
    assert event["anchor"] == {"section": "subject"}
    assert event["drawing"]["strokes"]
    expect(page.locator(".lf-drawing-pending")).to_have_count(0)
    expect(page.locator(".lf-drawing-posted")).to_have_count(0)
    expect(
        page.locator(".lf-thread-panel .lf-msg").filter(has_text="The bend I mean")
    ).to_be_visible()
    physical = page.evaluate(
        "() => performance.getEntriesByType('resource').some(e=>new URL(e.name).pathname.includes('/annotation-overlay/'))"
    )
    assert not physical


CLIPPED_DRAWING_PAGE = leaf_page(
    "drawing clips",
    '<h1 id="title">Inspect a captured detail</h1>'
    '<div id="viewport"><div id="pixels">Captured pixels</div></div>',
    head="<style>#viewport { width: 360px; height: 200px; overflow: hidden; }"
    "#pixels { width: 360px; height: 200px; background: var(--paper); }</style>",
)


@pytest.mark.parametrize(
    "transform", ["scale(.5)", "rotate(90deg)", "ancestor scale(.5)"]
)
def test_drawing_ink_follows_its_targets_transform(browser, serve, transform):
    """A page transform moves marked visual features and their ink together."""
    page = open_page(browser, serve(CLIPPED_DRAWING_PAGE))
    target = page.locator("#pixels")
    target.evaluate("el => el.style.transformOrigin = '0 0'")
    draw_over(page, target, points=((0.2, 0.4), (0.4, 0.4), (0.7, 0.4)))
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    box = target.bounding_box()
    transformed = (
        page.locator("#viewport") if transform.startswith("ancestor") else target
    )
    transformed.evaluate(
        """async (el, value) => {
      const {layoutChanged} = await import('/runtime/widget-elements.js');
      el.style.transformOrigin = '0 0';
      el.style.transform = value;
      await layoutChanged(el);
    }""",
        transform.removeprefix("ancestor "),
    )
    rendered(page)
    point = page.evaluate("""() => {
      const path = document.querySelector('.lf-drawing-pending path');
      const point = path.getPointAtLength(0).matrixTransform(path.getScreenCTM());
      return [point.x, point.y];
    }""")
    if "scale" in transform:
        expected = [box["x"] + 0.1 * box["width"], box["y"] + 0.2 * box["height"]]
    else:
        expected = [box["x"] - 0.4 * box["height"], box["y"] + 0.2 * box["width"]]
    assert point == pytest.approx(expected, abs=0.02)


def test_a_drawing_captured_on_a_scaled_svg_keeps_its_local_feature(browser, serve):
    """SVG viewBox scale and a CSS transform are both part of the drawing frame."""
    source = CLIPPED_DRAWING_PAGE.replace(
        '<div id="pixels">Captured pixels</div>',
        '<svg id="pixels" viewBox="0 0 180 100" role="img" aria-label="Sample">'
        '<rect width="180" height="100" fill="var(--paper)"/></svg>',
    )
    page = open_page(browser, serve(source))
    target = page.locator("#pixels")
    target.evaluate(
        "el => { el.style.transformOrigin = '0 0'; el.style.transform = 'scale(.5)'; }"
    )
    draw_over(page, target)
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    with sending(page, "the drawing on the scaled SVG"):
        page.keyboard.press("ControlOrMeta+Enter")
    drawing = events_model.read_events(serve.page_dir)[-1]["drawing"]
    assert drawing["box"] == pytest.approx([180, 100], abs=0.02)
    assert drawing["strokes"][0][0] == pytest.approx([180 * 0.22, 100 * 0.62], abs=0.02)
    target.evaluate("""async el => {
      const {layoutChanged} = await import('/runtime/widget-elements.js');
      el.style.transform = 'none';
      await layoutChanged(el);
    }""")
    rendered(page)
    box = target.bounding_box()
    point = page.evaluate("""() => {
      const path = document.querySelector('.lf-drawing-posted path');
      const point = path.getPointAtLength(0).matrixTransform(path.getScreenCTM());
      return [point.x, point.y];
    }""")
    assert point == pytest.approx(
        [box["x"] + box["width"] * 0.22, box["y"] + box["height"] * 0.62], abs=0.02
    )


def test_drawing_ink_follows_pixels_inside_their_ancestor_viewport(browser, serve):
    """Panning a marked surface moves its ink, while its viewport cuts the paint.

    The complete surface remains the drawing's coordinate frame: clipping must
    not renormalize the mark to only the pixels currently visible. Completed
    draft ink uses the same clipping owner as posted ink; measuring it before
    sending keeps a second drawing thumbnail and moving thread card out of the
    pixel comparison.
    """
    page = open_page(browser, serve(CLIPPED_DRAWING_PAGE))
    target = page.locator("#pixels")
    draw_over(page, target, points=((0.2, 0.4), (0.4, 0.4), (0.7, 0.4)))
    mark = page.locator(".lf-drawing-pending")
    expect(mark).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    for pan in (-100, 180):
        target.evaluate(
            "(el, x) => { el.style.transform = `translateX(${x}px)`; }", pan
        )
        rendered(page)
        viewport = page.locator("#viewport").bounding_box()
        pixels = target.bounding_box()
        # The horizontal stroke's full band, including the hidden part of the
        # surface. Whole-page chrome can change independently between captures.
        left = min(viewport["x"], pixels["x"]) - 4
        top = pixels["y"] + pixels["height"] * 0.4 - 4
        clip = {
            "x": left,
            "y": top,
            "width": max(
                viewport["x"] + viewport["width"], pixels["x"] + pixels["width"]
            )
            + 4
            - left,
            "height": 8,
        }
        # Read painted pixels rather than the mark's deliberately uncut SVG box.
        shown = Image.open(
            BytesIO(page.screenshot(clip=clip, animations="disabled"))
        ).convert("RGB")
        mark.evaluate("el => { el.style.visibility = 'hidden'; }")
        bare = Image.open(
            BytesIO(page.screenshot(clip=clip, animations="disabled"))
        ).convert("RGB")
        mark.evaluate("el => { el.style.visibility = ''; }")
        difference = ImageChops.difference(shown, bare).getbbox()
        assert difference is not None, "the visible part of the stroke must remain"
        assert difference[0] + left >= viewport["x"] - 1
        assert difference[2] + left <= viewport["x"] + viewport["width"] + 1
        assert difference[1] + top >= viewport["y"] - 1
        assert difference[3] + top <= viewport["y"] + viewport["height"] + 1
        # Panning moves the full stroke's coordinates; clipping must not refit it.
        assert difference[0] + left == pytest.approx(
            max(viewport["x"], pixels["x"] + pixels["width"] * 0.2 - 1.5), abs=1
        )
        assert difference[2] + left == pytest.approx(
            min(
                viewport["x"] + viewport["width"],
                pixels["x"] + pixels["width"] * 0.7 + 1.5,
            ),
            abs=1,
        )


@pytest.mark.parametrize("long", [False, True], ids=["short", "scrolled"])
@pytest.mark.parametrize("touch", [False, True], ids=["desktop", "phone"])
def test_sent_drawing_keeps_its_reference_outside_the_retained_text_viewport(
    browser, serve, long, touch
):
    """Sending retains the editor's text viewport, not a cap on added metadata."""
    context = browser.new_context(has_touch=touch, is_mobile=touch)
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Drawing feedback",
                '<h1>Review</h1><p id="target">Evidence to annotate.</p>',
            )
        ),
        context=context,
    )
    if touch:
        page.set_viewport_size({"width": 390, "height": 844})
    draw_over(page, page.locator("#target"))
    field = page.locator(".lf-fab-input")
    write(
        field, "still a gap here!" if not long else "A line of drawing feedback.\n" * 60
    )
    rendered(page)
    before = field.evaluate(
        "node => ({height:node.clientHeight, scroll:node.scrollTop, "
        "top:node.getBoundingClientRect().top})"
    )
    with sending(page, "the drawing comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    rendered(page)
    body = card.locator(".lf-msg-body").first
    reading = body.evaluate("""body => {
      const reference = body.querySelector('.lf-drawing-reference').getBoundingClientRect();
      const text = body.querySelector('.lf-msg-text').getBoundingClientRect();
      return {height: body.clientHeight, extent: body.scrollHeight,
              textBottom: text.bottom, referenceTop: reference.top,
              referenceBottom: reference.bottom, bodyBottom:body.getBoundingClientRect().bottom};
    }""")
    assert reading["extent"] <= reading["height"] + 1, reading
    assert reading["referenceTop"] >= reading["textBottom"], reading
    assert reading["referenceBottom"] <= reading["bodyBottom"] + 1, reading
    text = body.locator(".lf-msg-text")
    if not long:
        assert text.bounding_box()["y"] == pytest.approx(before["top"], abs=1)
    assert text.evaluate("node => node.scrollHeight > node.clientHeight + 1") == long
    assert text.evaluate("node => node.scrollTop") == pytest.approx(
        before["scroll"], abs=1
    )
    if long:
        resized(page, 390 if touch else 1280, 600)
        rendered(page)
        reference = body.locator(".lf-drawing-reference").bounding_box()
        viewport = card.locator(".lf-thread-transcript").bounding_box()
        assert reference["y"] >= viewport["y"] - 1
        assert reference["y"] + reference["height"] <= (
            viewport["y"] + viewport["height"] + 1
        )


def test_a_sent_drawing_keeps_its_pasted_photo_outside_the_text_viewport(
    browser, serve
):
    """The attachment remains visible and clickable beside a retained short comment."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Drawing with photo", '<h1>Review</h1><p id="target">Evidence.</p>'
            )
        ),
    )
    draw_over(page, page.locator("#target"))
    field = page.locator(".lf-fab-input")
    pixels = BytesIO()
    Image.new("RGB", (640, 480), "teal").save(pixels, "PNG")
    paste_image(field, pixels.getvalue())
    write(field, "The photo shows the gap.")
    with sending(page, "the drawing and photo"):
        page.keyboard.press("ControlOrMeta+Enter")
    card = page.locator(".lf-margin-preview")
    rendered(page)
    text = card.locator(".lf-msg-text").first
    assert text.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    photo = card.get_by_role("button", name="View Attached image", exact=True)
    wait_for(
        lambda: photo.evaluate("""node => {
          const box = node.getBoundingClientRect();
          return node.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
        }"""),
        bool,
        failure="The pasted photo's center remains clipped after the card reveals",
    )
    box = photo.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(page.get_by_role("dialog", name="Image preview", exact=True)).to_be_visible()
