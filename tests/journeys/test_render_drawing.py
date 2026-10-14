"""Drawing-comment browser journeys."""

import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from PIL import Image, ImageChops
from playwright.sync_api import expect
from render_cases_navigation import (
    TARGETS_PAGE,
    UNDO_PAGE,
)
from render_harness import (
    nudge,
    open_page,
    panel_settled,
    sending,
    stamp_page,
    told,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_drawing import (
    BAND_STROKE,
    MAP_CHOICE_PAGE,
    STROKE,
    SWATCH_PAGE,
    draw_over,
    mark_box,
    mark_relation,
    stroke_over,
)


def test_a_drawing_is_sent_and_replayed_as_an_ordinary_comment(browser, serve):
    """One pointer stroke starts on one semantic anchor, crosses the page beyond it,
    and the accepted comment keeps its ink positioned over that anchor. The record
    carries the window it was drawn in, its layout viewport and color scheme, which
    is what lays the page out again for the agent's picture of it."""
    url = serve(MAP_CHOICE_PAGE)
    page = open_page(browser, url, color_scheme="dark")
    target = page.locator("#map-trail")
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
    assert event["anchor"] == {"section": "map-trail"}
    assert event["text"] == "This bend is the part I mean."
    drawing = event["drawing"]
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
    relation = mark_relation(page, posted, "#map-trail")
    page.evaluate("scrollBy(0, 100)")
    rendered(page)
    assert mark_relation(page, posted, "#map-trail") == pytest.approx(
        relation, abs=0.02
    )
    # The scroll carries the mark rather than a repaint redrawing it.
    assert stable_mark.evaluate("node => node.isConnected")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    assert mark_relation(page, posted, "#map-trail") == pytest.approx(
        relation, abs=0.02
    )
    expect(target).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(page.locator(".lf-thread-panel .lf-drawing-reference")).to_have_text(
        "Drawing comment"
    )

    returned = open_page(browser, url)
    expect(returned.locator(posted)).to_have_count(1)
    assert mark_relation(returned, posted, "#map-trail") == pytest.approx(
        relation, abs=0.02
    )


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
    tile = page.get_by_role("button", name=re.compile(r"^Inspect drawing,"))
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
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 1 stroke")
    stroke_over(page, heading, points=other)
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 1 stroke")
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*$"))

    # Words typed after a stroke are the latest change, and a stroke drawn after the
    # words is: ⌘Z takes back each in turn, the words through the field's own history.
    stroke_over(page, heading, points=other)
    write(field, "Here.")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 1 stroke")
    stroke_over(page, heading, points=other)
    write(field, "Here.")
    stroke_over(page, heading)
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 3 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
    expect(field).to_have_js_property("value", "Here.")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")

    # The words' history orders them, not the words' text: words typed and taken out
    # again are the latest change, and words typed hard on a stroke's heels, which the
    # history would fold into the words before it, are a step of their own.
    page.keyboard.type("x")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("End")
    page.keyboard.press("Backspace")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "x")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    page.keyboard.type("a")
    stroke_over(page, heading, steps=2, points=other)
    field.focus()
    page.keyboard.type("b")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "a")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 3 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
    page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")

    # ⌘⇧Z makes the steps again in the same order, and a new change drops what was
    # taken back before it, so redo never brings words back past a later stroke.
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(field).to_have_js_property("value", "a")
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 3 strokes")
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(field).to_have_js_property("value", "ab")
    for _ in range(3):
        page.keyboard.press("ControlOrMeta+z")
    expect(field).to_have_js_property("value", "")
    stroke_over(page, heading, points=other)
    field.focus()
    page.keyboard.press("ControlOrMeta+Shift+Z")
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
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
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
    field.focus()
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 2 strokes")
    expect(field).to_have_js_property("value", "Here.")
    page.get_by_role("button", name="Undo last stroke").click()
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 1 stroke")
    page.get_by_role("button", name="Remove drawing").click()
    expect(tile).to_have_count(0)
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    expect(field).to_be_focused()
    page.keyboard.press("ControlOrMeta+z")
    expect(tile).to_have_attribute("aria-label", "Inspect drawing, 1 stroke")
    expect(pending).to_have_attribute("d", re.compile(r"^M[^M]*$"))
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(tile).to_have_count(0)
    expect(page.locator(".lf-drawing-mark")).to_have_count(0)
    with sending(page, "the words without their drawing"):
        page.keyboard.press("ControlOrMeta+Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert event["text"] == "Here."
    assert "drawing" not in event


def test_a_draw_press_uses_the_exact_target_under_its_start(browser, serve):
    """Joined option seams use the target under the pointer when the stroke starts."""
    page = open_page(browser, serve(MAP_CHOICE_PAGE))
    trail = page.locator("#map-trail")
    trail.scroll_into_view_if_needed()
    box = trail.bounding_box()
    point = (box["x"] + box["width"] * 0.5, box["y"])
    target = page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.closest('lf-option')?.id",
        point,
    )
    assert target in {"map-street", "map-trail"}
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
    assert page.locator("#map-street").get_attribute("chosen") is None
    assert page.locator("#map-trail").get_attribute("chosen") is None
