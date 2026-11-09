"""Images and captures in threads: pasting and previewing images, image links in the
report, and the screenshot tool that attaches a region of the page."""

import io
import re
from itertools import pairwise

import pytest
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_cases_layout import solid_png
from render_harness import (
    LONG_PAGE,
    example_media,
    field_press,
    leaf_page,
    open_page,
    page_comment,
    panel_field,
    press_visible,
    resized,
    sending,
    stamp_page,
    told,
    write,
)

from browser.threads import (
    capture_page,
    open_capture_area,
    paste_image,
)
from leaf import event_log as events_model
from leaf import media as media_model
from leaf.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("editor", ["comment", "reply"])
def test_a_draft_s_image_closes_back_to_the_draft(browser, serve, editor):
    """Opening a draft's attached image and closing it, by Escape, the close control or
    a press outside, returns the user to the draft with its words and picture, in the
    panel's field whichever editor stands there: the page comment, or an open thread's
    reply, whose view the panel would put away on a press it read as outside it."""
    url = serve(LONG_PAGE)
    if editor == "comment":
        page = open_page(browser, url)
        box = page_comment(page)
    else:
        panel_comment(serve.page_dir, "Can you show me the fault?")
        page = open_page(browser, url)
        page.locator("body").focus()
        page.keyboard.press("t")
        expect(page.locator(PANEL_THREAD)).to_be_visible()
        box = panel_field(page)
    write(box, "See the fault")
    paste_image(box, (example_media() / "051bee487bfb5d13.png").read_bytes())
    thumbnail = page.get_by_role("button", name="View attached image 1", exact=True)
    viewer = page.get_by_role("dialog", name="Image preview")

    for dismiss in (
        lambda: page.keyboard.press("Escape"),
        lambda: viewer.get_by_role("button", name="Close image preview").click(),
        lambda: page.mouse.click(8, 400),
    ):
        thumbnail.click()
        expect(viewer).to_be_visible()
        dismiss()
        expect(viewer).to_be_hidden()
        expect(thumbnail).to_be_focused()
        expect(box).to_be_visible()
        expect(box).to_have_js_property("value", "See the fault")


def test_original_image_link_has_a_standalone_target(browser, serve):
    # Under a finger the link takes the touch floor, the larger of the two.
    context = browser.new_context(
        viewport={"width": 320, "height": 720}, has_touch=True
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Image",
                '<h1>Image</h1><a id="image" href="/media/051bee487bfb5d13.png"><img src="/media/051bee487bfb5d13.png" alt="Image"></a>',
            )
        ),
        context=context,
    )
    page.locator("#image").click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    expect(viewer.locator(".lf-media-viewer-caption")).to_be_hidden()
    original = viewer.get_by_role("link", name="Original")
    box = original.bounding_box()
    assert min(box["width"], box["height"]) >= 44 - 0.5, box
    neighbours = viewer.locator(".lf-media-viewer-actions > *")
    boxes = [node.bounding_box() for node in neighbours.all()]
    for left, right in pairwise(boxes):
        assert left["x"] + left["width"] <= right["x"], boxes
    original.focus()
    with page.expect_popup() as opened:
        original.press("Enter")
    popup = opened.value
    assert "/media/051bee487bfb5d13.png" in popup.url
    popup.close()
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    expect(page.locator("#image")).to_be_focused()


def test_a_capture_in_a_table_is_named_by_its_heads(browser, serve):
    """Image preview keeps a table of captures' labels, which name each axis once.

    Heads count where they stand: spanning heads name every capture under or beside
    them, outer first, a header row needs no <thead>, and a repeated one names once."""
    cell = '<td><a id="{0}" href="/media/051bee487bfb5d13.png"><img src="/media/051bee487bfb5d13.png" width="180" height="75" alt="Release output"></a></td>'
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Captures",
                "<h1>Captures</h1><table id=grid>"
                "<thead><tr><td></td><th scope=col>Light</th><th scope=col>Dark</th></tr></thead>"
                f"<tbody><tr><th scope=row>Before</th>{cell.format('light-before')}{cell.format('dark-before')}</tr>"
                f"<tr><th scope=row>After</th>{cell.format('light-after')}{cell.format('dark-after')}</tr></tbody>"
                "<tbody><tr><td></td><th>Light</th><th>Dark</th></tr>"
                f"<tr><th scope=row>Later</th>{cell.format('light-later')}{cell.format('dark-later')}</tr></tbody></table>"
                "<table id=spanned><tbody>"
                "<tr><td rowspan=2 colspan=2></td><th colspan=2>Light</th><th colspan=2>Dark</th></tr>"
                "<tr><th>Before</th><th>After</th><th>Before</th><th>After</th></tr>"
                "<tr><th scope=row rowspan=2>Phone</th><th scope=row>Portrait</th>"
                + "".join(cell.format(f"portrait-{n}") for n in range(4))
                + "</tr><tr><th scope=row>Landscape</th>"
                + "".join(cell.format(f"landscape-{n}") for n in range(4))
                + "</tr></tbody></table>",
            )
        ),
    )
    viewer = page.get_by_role("dialog", name="Image preview")
    for link, caption in (
        ("dark-before", "Dark · Before"),
        ("light-after", "Light · After"),
        ("dark-later", "Dark · Later"),
        ("portrait-0", "Light · Before · Phone · Portrait"),
        ("landscape-3", "Dark · After · Phone · Landscape"),
    ):
        page.locator(f"#{link}").click()
        expect(viewer.locator(".lf-media-viewer-caption")).to_have_text(caption)
        page.keyboard.press("Escape")
        expect(viewer).to_be_hidden()


def test_a_capture_in_a_reply_s_table_is_named_by_its_column_head(browser, serve):
    """A table of captures an agent writes in Markdown names each capture by the head over
    its column, as the page's own tables do: a message's words are its writer's."""
    url = serve(
        leaf_page(
            "Captures",
            '<h1>Captures</h1><img src="/media/051bee487bfb5d13.png" alt="Release output">',
        )
    )
    image = (
        "[![Release output](/media/051bee487bfb5d13.png)](/media/051bee487bfb5d13.png)"
    )
    panel_comment(
        serve.page_dir,
        f"| | Light | Dark |\n|---|---|---|\n| Before | {image} | {image} |",
        author="agent",
    )
    page = open_page(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(PANEL_THREAD)
    expect(thread).to_be_visible()
    viewer = page.get_by_role("dialog", name="Image preview")
    for index, caption in enumerate(("Light", "Dark")):
        thread.locator('a[href="/media/051bee487bfb5d13.png"]').nth(index).click()
        expect(viewer.locator(".lf-media-viewer-caption")).to_have_text(caption)
        page.keyboard.press("Escape")
        expect(viewer).to_be_hidden()


# A diagram that states no size of its own, only a shape, as a diagram renderer writes one.
DIAGRAM_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
    b'<rect width="400" height="200" fill="#cde"/></svg>'
)


DIAGRAM = media_model.media_name(DIAGRAM_SVG, ".svg")


def test_an_image_only_composer_names_and_lays_out_the_draft_it_keeps(browser, serve):
    """The compact composer reads the complete draft hidden behind its text box.

    Several images make its shelf overflow, proving the anchored box gets the same
    horizontal thumbnail projection as the larger thread text boxes. The shelf hangs
    below the box, away from its passage, so attaching leaves the box and its words
    where they were.
    """
    # The narrow box, where the shelf of images overflows soonest.
    width = 390
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, width, 844)
    page.locator("#p1").click(click_count=3)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    rendered(page)
    bar = page.locator(".lf-fab-bar")
    before = (bar.bounding_box(), field.bounding_box())
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()

    # Enough of them to outrun the narrow box.
    pasted = 6
    kept = pasted - 1
    paste_image(field, pixels, count=pasted)

    expect(field).to_have_js_property("value", "")
    shelf = page.locator(".lf-fab-bar .lf-composer-media")
    expect(shelf.locator("img")).to_have_count(pasted)
    rendered(page)
    assert (bar.bounding_box(), field.bounding_box()) == before
    field_box = before[1]
    for picture in shelf.locator(".lf-composer-media-open").all():
        assert picture.bounding_box()["y"] >= field_box["y"] + field_box["height"]
    assert field_box["x"] + field_box["width"] <= width
    layout = shelf.evaluate(
        """element => ({
          display: getComputedStyle(element).display,
          overflowX: getComputedStyle(element).overflowX,
          scrolls: element.scrollWidth > element.clientWidth,
        })"""
    )
    assert layout == {"display": "flex", "overflowX": "auto", "scrolls": True}
    shelf.get_by_role("button", name="Remove attached image 2").click()
    rendered(page)
    expect(shelf).to_be_visible()
    expect(shelf.locator(":scope > .lf-composer-media-item")).to_have_count(kept)
    expect(field).to_be_focused()
    expect(shelf.locator("img")).to_have_count(kept)
    assert shelf.locator(".lf-composer-media-remove").evaluate_all(
        "buttons => buttons.map(button => button.getAttribute('aria-label'))"
    ) == [f"Remove attached image {n}" for n in range(1, kept + 1)]
    assert shelf.locator(".lf-composer-media-open").evaluate_all(
        "buttons => buttons.map(button => button.getAttribute('aria-label'))"
    ) == [f"View attached image {n}" for n in range(1, kept + 1)]
    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    page.locator("#p1").click(click_count=3)
    expect(field).to_be_visible()
    field.click()
    expect(shelf.locator("img")).to_have_count(kept)
    assert shelf.locator(".lf-composer-media-remove").evaluate_all(
        "buttons => buttons.map(button => button.getAttribute('aria-label'))"
    ) == [f"Remove attached image {n}" for n in range(1, kept + 1)]
    with sending(page, "the retained image draft"):
        page.keyboard.press("ControlOrMeta+Enter")
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert len(comments) == 1, comments
    sent = comments[0]
    image_markdown = "![Attached image](/media/051bee487bfb5d13.png)"
    assert sent["kind"] == "comment"
    assert (
        sent["text"].splitlines() == "\n\n".join([image_markdown] * kept).splitlines()
    )
    expect(page.locator(".lf-composer")).to_be_hidden()


@pytest.mark.parametrize(
    ("placement", "picture"),
    [
        pytest.param(
            "bottom",
            lambda: (example_media() / "051bee487bfb5d13.png").read_bytes(),
            id="below-its-passage",
        ),
        pytest.param(
            "top",
            lambda: solid_png(240, 8, (64, 64, 64)),
            id="above-it-a-short-picture",
        ),
    ],
)
def test_a_tap_at_the_comment_field_s_edge_stays_the_field_s(
    browser, serve, placement, picture
):
    """Under a finger, the removal mark on a picture's top corner reaches the aim floor
    around it. Below its passage the comment box hangs its pictures under the field,
    with the marks facing it; above, a picture shorter than that reach lets it hang past
    the picture's foot. Either way the reach once stood inside the field, so a tap at
    the field's edge removed the picture."""
    context = browser.new_context(
        viewport={"width": 900, "height": 900}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(LONG_PAGE), context=context)
    passage = page.locator("#p1")
    if placement == "top":
        # Too near the panel for the box to open below it.
        passage = page.locator("#p20")
        passage.evaluate("p => { p.scrollIntoView({block: 'end'}); scrollBy(0, 80) }")
    passage.click(click_count=3)
    # Under a finger the panel's field offers the selected words, and a press there
    # opens the comment box on them.
    page.locator('.lf-fp-field leaf-text[data-lf-says="selection"]').click()
    field = page.locator(".lf-fab-input")
    field.click()
    paste_image(field, picture())
    remove = page.get_by_role("button", name="Remove attached image 1", exact=True)
    expect(remove).to_be_visible()
    rendered(page)
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "data-lf-placement", re.compile(f"^{placement}")
    )
    box = page.locator(".lf-fab-bar .lf-compose-field").bounding_box()
    mark = remove.bounding_box()
    x = mark["x"] + mark["width"] / 2
    y = box["y"] + box["height"] - 3 if placement == "bottom" else box["y"] + 3
    assert box["x"] < x < box["x"] + box["width"], (box, mark)
    page.touchscreen.tap(x, y)
    rendered(page)
    expect(page.locator(".lf-fab-bar .lf-composer-media img")).to_have_count(1)
    expect(field).to_be_focused()


def test_capture_leaves_selected_content_visible_through_the_drag(browser, serve):
    page = capture_page(browser, serve)
    baseline = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    target = page.locator("#capture-copy").bounding_box()
    left, top = int(target["x"]) + 100, int(target["y"]) + 4
    surface = open_capture_area(page)
    page.mouse.move(left, top)
    page.mouse.down()
    # Judge the selected content while the pointer is held, including a small
    # rectangle and a reversal. A successful final attachment cannot prove this.
    for dx, dy in ((4, 4), (88, 44), (180, 90), (-88, -44)):
        page.mouse.move(left + dx, top + dy, steps=3)
        selected = surface.locator(".lf-region-selection").bounding_box()
        crop = tuple(
            round(value * 2)
            for value in (
                selected["x"],
                selected["y"],
                selected["x"] + selected["width"],
                selected["y"] + selected["height"],
            )
        )
        actual = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        assert actual.crop(crop).tobytes() == baseline.crop(crop).tobytes(), (
            f"Capture paint obscures the selected content during a {dx}×{dy} drag"
        )
    # Leave before lifting, which would attach the area.
    page.keyboard.press("Escape")
    page.mouse.up()
    expect(surface).to_be_hidden()
    expect(page.locator(".lf-composer-media-item")).to_have_count(0)


def test_touch_capture_attaches_on_lift_and_a_tap_or_cancel_attaches_nothing(
    browser, serve
):
    """A finger's drag is the whole gesture: lifting it attaches the area, and the
    attachment's ✕ takes a bad one back. Capture opens with no area, and the field
    asks for a drag. A tap draws no area, so it leaves capture standing with none; the
    field's Close or Escape leaves with nothing attached."""
    page = capture_page(browser, serve, touch=True)
    touch = page.context.new_cdp_session(page)
    # Retain the native event so the assertion reads its final cancellation state.
    page.evaluate("""() => {
        window.captureTouchStarts = [];
        window.addEventListener('touchstart', event => captureTouchStarts.push(event),
            {capture: true, passive: true});
    }""")

    def touch_area(dx, dy):
        target = page.locator("#capture-target").bounding_box()
        left, top = int(target["x"]) + 10, int(target["y"]) + 20
        for kind, points in (
            ("touchStart", [{"x": left, "y": top}]),
            ("touchMove", [{"x": left + dx, "y": top + dy}]),
            ("touchEnd", []),
        ):
            touch.send(
                "Input.dispatchTouchEvent", {"type": kind, "touchPoints": points}
            )

    before = events_model.read_events(serve.page_dir)
    before_media = sorted((serve.page_dir / "media").glob("*"))
    surface = open_capture_area(page, touch=True)
    selection = surface.locator(".lf-region-selection")
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "placeholder", re.compile("^Drag an area to capture")
    )
    # The panel's row offers only the way out; lifting a drag attaches.
    expect(page.get_by_role("button", name="Attach capture", exact=True)).to_have_count(
        0
    )
    touch_area(3, 2)
    rendered(page)
    expect(surface).to_be_visible()
    expect(selection).to_be_hidden()
    field_press(page).filter(has_text="Close").tap()
    expect(surface).to_be_hidden()
    assert page.evaluate("captureTouchStarts.at(-2).defaultPrevented"), (
        "a selection must consume its native touch gesture, including fling generation"
    )
    assert page.evaluate("!captureTouchStarts.at(-1).defaultPrevented")
    expect(page.locator(".lf-composer-media-item")).to_have_count(0)
    assert events_model.read_events(serve.page_dir) == before
    assert sorted((serve.page_dir / "media").glob("*")) == before_media
    surface = open_capture_area(page, touch=True)
    page.keyboard.press("Escape")
    expect(surface).to_be_hidden()
    expect(page.locator(".lf-composer-media-item")).to_have_count(0)
    surface = open_capture_area(page, touch=True)
    # The lift must start capture, and the next press must belong to its own gesture,
    # before queued work from the drag runs. Keep that ordering independent of load.
    page.clock.install(time=0)
    page.clock.pause_at(1)
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        touch_area(180, 130)
        assert surface.get_attribute("aria-busy") == "true", (
            "lifting the drag must start capture before drag timers run"
        )
    expect(surface).to_be_hidden()
    attachment = page.locator(".lf-composer-media-item img")
    expect(attachment).to_be_visible()
    image = Image.open(serve.page_dir / attachment.get_attribute("src").lstrip("/"))
    assert image.size == (360, 260)
    # Which element each part of the removal tap reached, for the reading below.
    page.evaluate("""() => {
        window.removalTap = [];
        const original = document.querySelector('.lf-composer-media-remove');
        const box = node => node?.getBoundingClientRect().toJSON();
        const named = node => node instanceof Element
            ? `${node.localName}.${[...node.classList].join('.')}`
              + (node.isConnected ? '' : ' (removed)')
            : String(node);
        for (const type of ['pointerdown', 'pointerup', 'touchstart', 'touchend',
                            'mousedown', 'mouseup', 'click'])
            window.addEventListener(type, event => {
                const point = event.changedTouches?.[0] ?? event;
                removalTap.push({
                    type, target: named(event.composedPath()[0]),
                    prevented: event.defaultPrevented,
                    point: [point.clientX, point.clientY],
                    hit: named(document.elementFromPoint(point.clientX, point.clientY)),
                    originalConnected: original.isConnected,
                    sameButton: original === document.querySelector('.lf-composer-media-remove'),
                    button: box(original),
                    grip: box(document.querySelector('.lf-fab-bar > .lf-surface-grip')),
                });
            }, {capture: true});
    }""")
    press_visible(
        page,
        page.get_by_role("button", name="Remove attached image 1", exact=True),
        touch=True,
    )
    # Removal is synchronous in the click, so the shelf is empty as the tap returns,
    # with the drag's timers still held. An image here with the click on the ✕ says
    # the click did not remove it; a click elsewhere, or none, says the tap missed.
    assert attachment.count() == 0, page.evaluate("removalTap")
    # The next press began while drag timers were held; let its native activation
    # finish before reading the result.
    page.clock.resume()
    expect(attachment).to_have_count(0)
    assert events_model.read_events(serve.page_dir) == before
    assert page.evaluate("!captureTouchStarts.at(-1).defaultPrevented")
    touch.detach()


def test_the_keyboard_moves_resizes_and_attaches_the_area(browser, serve):
    """The first arrow draws the preset area, then arrows move it and Shift with an
    arrow resizes it, 10 pixels a press, and Enter attaches it, so capture needs no
    drag. Enter before any area attaches nothing."""
    page = capture_page(browser, serve)
    surface = open_capture_area(page)
    selection = surface.locator(".lf-region-selection")
    page.keyboard.press("Enter")
    expect(surface).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(selection).to_be_visible()
    shown = selection.bounding_box()
    for key in ("ArrowRight", "ArrowDown", "Shift+ArrowRight", "Shift+ArrowUp"):
        page.keyboard.press(key)
    moved = selection.bounding_box()
    assert (moved["x"], moved["y"], moved["width"], moved["height"]) == (
        pytest.approx(shown["x"] + 10),
        pytest.approx(shown["y"] + 10),
        pytest.approx(shown["width"] + 10),
        pytest.approx(shown["height"] - 10),
    )
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.keyboard.press("Enter")
    expect(surface).to_be_hidden()
    attachment = page.locator(".lf-composer-media-item img")
    expect(attachment).to_be_visible()
    image = Image.open(serve.page_dir / attachment.get_attribute("src").lstrip("/"))
    assert image.size == (round(moved["width"] * 2), round(moved["height"] * 2))


# The renderer, failing its first drawing and drawing every later one.
RENDERER_FAILING_ONCE = """
import * as renderer from "./snapdom.esm.js?draws";
let failed = false;
export const snapdom = (...args) => {
  if (failed) return renderer.snapdom(...args);
  failed = true;
  throw new Error("the renderer failed");
};
"""


def test_a_capture_that_fails_to_draw_stands_for_another_drag(browser, serve):
    """A pointer has no Attach to press again after a capture fails, so capture stays
    open over the same area: the next drag attaches."""
    page = capture_page(browser, serve)
    page.route(
        lambda url: url.endswith("/snapdom.esm.js"),
        lambda route: route.fulfill(
            content_type="text/javascript", body=RENDERER_FAILING_ONCE
        ),
    )
    target = page.locator("#capture-target").bounding_box()
    left, top = int(target["x"]) + 10, int(target["y"]) + 10
    surface = open_capture_area(page)

    def drag():
        page.mouse.move(left, top)
        page.mouse.down()
        page.mouse.move(left + 200, top + 120, steps=4)
        page.mouse.up()

    drag()
    expect(surface.locator(".lf-region-status")).to_have_text(
        "Could not capture — the renderer failed"
    )
    expect(surface).to_be_visible()
    expect(surface).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-composer-media-item")).to_have_count(0)
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        drag()
    expect(surface).to_be_hidden()
    attachment = page.locator(".lf-composer-media-item img")
    expect(attachment).to_be_visible()
    image = Image.open(serve.page_dir / attachment.get_attribute("src").lstrip("/"))
    assert image.size == (400, 240)


def test_capture_temporarily_owns_page_input_without_leaving_draw_mode(browser, serve):
    source = leaf_page(
        "Capture while drawing",
        """<h1>Capture while drawing</h1>
<section id="capture-zone" style="margin-top:160px;height:300px;background:#eaf1ef">
  <label><input type="checkbox" aria-label="Enable annotation"> Enable annotation</label>
  <p>The capture gesture must not activate the checkbox or draw on this passage.</p>
</section>""",
    )
    page = open_page(browser, serve(source))
    control = page.get_by_role("checkbox", name="Enable annotation")
    # Establish that this real page control responds normally before Capture owns it.
    control.check()
    expect(control).to_be_checked()
    control.uncheck()
    page.keyboard.press("w")
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    before = events_model.read_events(serve.page_dir)

    for attach in (False, True):
        surface = open_capture_area(page)
        selection = surface.locator(".lf-region-selection")
        box = control.bounding_box()
        left, top = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        # A click draws no area: it attaches nothing and leaves capture standing.
        page.mouse.click(left, top)
        rendered(page)
        expect(surface).to_be_visible()
        expect(selection).to_be_hidden()
        expect(control).not_to_be_checked()
        expect(page.locator(".lf-drawing-mark")).to_have_count(0)
        expect(page.locator(".lf-fab-input")).to_be_hidden()
        page.mouse.move(left, top)
        page.mouse.down()
        page.mouse.move(left + 180, top + 100, steps=5)
        selected = selection.bounding_box()
        assert selected["width"] == pytest.approx(180)
        assert selected["height"] == pytest.approx(100)
        if attach:
            with page.expect_response(
                lambda response: response.url.endswith("/api/media")
            ):
                page.mouse.up()
            expect(page.locator(".lf-composer-media-item img")).to_be_visible()
        else:
            # Leaving mid-drag attaches nothing, and the drag still owns its release.
            page.keyboard.press("Escape")
            page.mouse.up()
        rendered(page)
        expect(surface).to_be_hidden()
        expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
        expect(page.locator(".lf-drawing-mark")).to_have_count(0)
        expect(control).not_to_be_checked()
        assert events_model.read_events(serve.page_dir) == before


def test_a_capture_attaches_to_the_box_an_error_stood_over(browser, serve):
    """Attaching an image is the user coming back to the comment box, as typing is, so
    an error that stood over the box never swallows a capture: Escape puts the words
    and the error away, and the drag's lift lands the capture in the box."""
    page = open_page(browser, serve(LONG_PAGE))
    target = page.locator("#p3")
    target.scroll_into_view_if_needed()
    target.click(click_count=3)
    page.keyboard.press("c")
    box = page.locator(".lf-fab-input")
    write(box, "Words a refusal handed back.")
    page.evaluate(
        """async () => (await window.__lfWidgetApi()).raiseError(
          "Couldn't take this — refused before append",
          { subject: document.querySelector('.lf-fab-input') })"""
    )
    cover = page.locator(".lf-fab-bar .lf-compose-error")
    expect(cover).to_be_visible()
    page.keyboard.press("Escape")
    expect(box).to_be_hidden()

    surface = open_capture_area(page)
    area = target.bounding_box()
    page.mouse.move(area["x"] + 20, area["y"] + 5)
    page.mouse.down()
    page.mouse.move(area["x"] + 220, area["y"] + 60, steps=5)
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.mouse.up()
    expect(surface).to_be_hidden()
    expect(page.locator(".lf-composer-media-item img")).to_be_visible()
    expect(cover).to_be_hidden()


@pytest.mark.parametrize("change", ["resize", "revision"])
def test_a_region_capture_anchors_the_page_as_it_stands_at_confirmation(
    browser, serve, change
):
    """An open selector must keep following the current target inventory and geometry."""
    source = leaf_page(
        "Capture after the page changes",
        "<h1>Capture current content</h1>"
        '<section id="capture-first" class="capture-zone">First area</section>'
        '<section id="capture-second" class="capture-zone">Second area</section>',
        head="""<style>
          .capture-zone { position:fixed; top:240px; width:180px; height:120px;
            background:rgb(10,150,30); }
          #capture-first, #capture-revised { left:100px; }
          #capture-second { left:650px; }
          @media (max-width:1000px) {
            #capture-first { left:650px; }
            #capture-second { left:100px; }
          }
        </style>""",
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    page = open_page(browser, live_url(serve(source)), context=context)
    surface = open_capture_area(page)
    if change == "resize":
        resized(page, 900, 900)
        expected = "capture-second"
    else:
        stamp_page(
            serve.page_dir,
            source.replace('id="capture-first"', 'id="capture-revised"'),
            "Replace the first capture area",
        )
        told(page)
        expected = "capture-revised"
    expect(surface).to_be_visible()
    target = page.locator(f"#{expected}").bounding_box()
    page.mouse.move(target["x"] + 20, target["y"] + 20)
    page.mouse.down()
    page.mouse.move(target["x"] + 100, target["y"] + 80)
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.mouse.up()
    expect(surface).to_be_hidden()
    expect(page.locator(".lf-composer-media-item img")).to_be_visible()
    field = page.locator(".lf-fab-bar leaf-text")
    expect(field).to_be_focused()
    with sending(page, "the capture of the current page target"):
        field.press("ControlOrMeta+Enter")
    comment = events_model.read_events(serve.page_dir)[-1]
    assert comment["kind"] == "comment"
    assert comment["anchor"]["section"] == expected


def test_capture_in_design_keeps_the_exact_repeated_control(browser, serve):
    """Capture materializes the chosen Design control's distinguishing passage."""
    rows = "".join(
        f'<p>{name} <button aria-label="Delete row">Remove</button></p>'
        for name in ("api", "web", "worker")
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Capture a control",
                '<h1>Rows</h1><section id="rows">' + rows + "</section>",
            )
        ),
    )
    page.keyboard.press("l")
    surface = open_capture_area(page)
    target = (
        page.get_by_role("button", name="Delete row", exact=True).nth(1).bounding_box()
    )
    page.mouse.move(target["x"], target["y"])
    page.mouse.down()
    page.mouse.move(target["x"] + target["width"], target["y"] + target["height"])
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.mouse.up()
    expect(surface).to_be_hidden()
    field = page.locator(".lf-fab-input")
    expect(page.locator(".lf-composer-media-item img")).to_be_visible()
    with sending(page, "the capture of the middle repeated control"):
        field.press("ControlOrMeta+Enter")
    comment = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    anchor = comment["anchor"]
    assert anchor["section"] == "rows"
    assert anchor["part"] == "Delete row"
    assert anchor["quote"] == "Remove"
    assert "web" in anchor.get("prefix", "") + anchor.get("suffix", "")
