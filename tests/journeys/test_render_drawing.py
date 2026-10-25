"""Drawing-comment browser journeys."""

import re

import pytest
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
    told,
    write,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_drawing import (
    MAP_CHOICE_PAGE,
    draw_over,
    mark_box,
    mark_relation,
    stroke_over,
)
from browser.threads import open_panel_thread


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
    panel_settled(page, view="threads")
    assert mark_relation(page, posted, "#map-trail") == pytest.approx(
        relation, abs=0.02
    )
    expect(target).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    view = open_panel_thread(page, event["id"])
    expect(view.locator(".lf-drawing-reference")).to_have_text("Drawing comment")

    returned = open_page(browser, url)
    expect(returned.locator(posted)).to_have_count(1)
    assert mark_relation(returned, posted, "#map-trail") == pytest.approx(
        relation, abs=0.02
    )


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
