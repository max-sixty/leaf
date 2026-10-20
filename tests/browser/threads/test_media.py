"""Images and captures in threads: pasting and previewing images, image links in the
report, and the screenshot tool that attaches a region of the page."""

import io
import re
from itertools import pairwise

import pytest
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import media as media_model
from leaf.render_checks import rendered
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_harness import (
    LONG_PAGE,
    PANEL_THREAD,
    example_media,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_field,
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
    touch = True
    context = browser.new_context(
        viewport={"width": 320, "height": 720}, has_touch=touch
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
    floor = 44 if touch else 24
    assert min(box["width"], box["height"]) >= floor - 0.5, box
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


# A diagram that states no size of its own, only a shape, as a diagram renderer writes one.
DIAGRAM_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
    b'<rect width="400" height="200" fill="#cde"/></svg>'
)


DIAGRAM = media_model.media_name(DIAGRAM_SVG, ".svg")


@pytest.mark.parametrize("offline", [False, True])
def test_linked_images_zoom_and_return_to_the_report(browser, serve, tmp_path, offline):
    """An authored image link inspects in place, including in the offline artifact."""
    url = serve(
        leaf_page(
            "Screenshot report",
            f"""
      <h1>Screenshot report</h1>
      <figure id="screenshot"><a href="/media/051bee487bfb5d13.png">
        <img src="/media/051bee487bfb5d13.png" width="1800" height="746"
          alt="Release output with two highlighted changes"></a>
        <figcaption>Release output after the fix.</figcaption></figure>
      <p><a id="other" href="#context"><img src="/media/051bee487bfb5d13.png"
        alt="Go to the context"></a></p>
      <figure id="diagram"><a href="/media/{DIAGRAM}">
        <img src="/media/{DIAGRAM}" alt="Release flow"></a></figure>
      <section id="context"><h2>Context</h2><p>The release passed.</p></section>
    """,
        ),
        media={f"media/{DIAGRAM}": DIAGRAM_SVG},
    )
    if offline:
        out = tmp_path / "image-report.html"
        exporting_model.cmd_export(serve.page_dir, out, None)
        url = out.as_uri()
    page = open_page(browser, url)
    viewer = page.get_by_role("dialog", name="Image preview")
    if not offline:
        # Until PhotoSwipe arrives the viewer shows no image, so the image's first
        # box is PhotoSwipe's, here where the viewport's height binds the fit.
        held = []
        page.route("**/photoswipe.esm.js", lambda route: held.append(route))
        resized(page, 1440, 500)
        page.locator("#screenshot a").click()
        holding(page, held, 1, "the image tools")
        expect(viewer.locator("img:visible")).to_have_count(0)
        held.pop().continue_()
        fitted = viewer.locator("img.pswp__img")
        expect(fitted).to_be_visible()
        stage = viewer.locator(".lf-media-viewer-stage").bounding_box()
        box = fitted.bounding_box()
        assert box["y"] >= stage["y"] + 16
        assert box["y"] + box["height"] <= stage["y"] + stage["height"] - 16 + 1
        page.unroute("**/photoswipe.esm.js")
        page.keyboard.press("Escape")
        expect(viewer).to_be_hidden()
    # The diagram fills the room it fits in, not the browser's 300x150 stand-in, even
    # a room narrower than that stand-in, and zooms past that fit for a closer look.
    fills = """() => {
      const stage = document.querySelector('.lf-media-viewer-stage');
      const inset = getComputedStyle(stage);
      const room = [
        stage.clientWidth - parseFloat(inset.paddingLeft) - parseFloat(inset.paddingRight),
        stage.clientHeight - parseFloat(inset.paddingTop) - parseFloat(inset.paddingBottom),
      ];
      const box = document.querySelector('.lf-media-viewer .pswp__img')
        .getBoundingClientRect();
      return [box.width, box.height].some((side, i) => Math.abs(side - room[i]) < 1);
    }"""
    resized(page, 320, 500)
    page.locator("#diagram a").click()
    expect(viewer.locator("img.pswp__img")).to_be_visible()
    assert page.evaluate(fills)
    expect(
        viewer.get_by_role("button", name="Zoom to actual size", exact=True)
    ).to_be_enabled()
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    for width in (1440, 390):
        resized(page, width, 900)
        image_link = page.locator("#screenshot a")
        image_link.scroll_into_view_if_needed()
        # Enter follows the authored link's same inspection route as a tap.
        page.keyboard.press("Tab")
        image_link.focus()
        before = page.evaluate("({url:location.href,scroll:scrollY})")
        image_link.press("Enter")
        expect(viewer).to_be_visible()
        zoom = viewer.get_by_role("button", name="Zoom to actual size", exact=True)
        expect(zoom).to_be_enabled()
        if not offline:
            expect(zoom).to_have_attribute("aria-keyshortcuts", "z")
        expect(viewer.locator(".lf-media-viewer-caption")).to_have_text(
            "Release output after the fix."
        )
        fitted = viewer.locator("img.pswp__img").bounding_box()
        head = viewer.locator(".lf-media-viewer-head").bounding_box()
        caption = viewer.locator(".lf-media-viewer-caption").bounding_box()
        assert fitted["y"] >= head["y"] + head["height"]
        assert fitted["y"] + fitted["height"] <= caption["y"]
        zoom.click()
        expect(
            viewer.get_by_role("button", name="Fit image", exact=True)
        ).to_be_visible()
        # Pixel scale is the reader's goal: enlarging a modal alone does not prove it.
        expect(viewer.locator("img.pswp__img")).to_have_css("width", "1800px")
        zoomed = viewer.locator("img.pswp__img").bounding_box()
        assert zoomed["width"] == pytest.approx(1800, abs=1)
        if not offline and width == 1440:
            page.keyboard.press("?")
            help_dialog = page.get_by_role(
                "dialog", name="Command reference", exact=True
            )
            expect(help_dialog).to_be_visible()
            search = help_dialog.get_by_role("combobox", name="Search commands")
            search.press("ArrowRight")
            search.press_sequentially("z")
            expect(search).to_have_value("z")
            rendered(page)
            assert viewer.locator("img.pswp__img").bounding_box() == zoomed
            page.keyboard.press("Escape")
            expect(help_dialog).to_be_hidden()
        page.keyboard.press("ArrowRight")
        panned = viewer.locator("img.pswp__img").bounding_box()
        assert panned["x"] < zoomed["x"]
        page.keyboard.press("z")
        expect(
            viewer.get_by_role("button", name="Zoom to actual size", exact=True)
        ).to_be_visible()
        page.keyboard.press("w")
        expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
        page.keyboard.press("Escape")
        expect(viewer).to_be_hidden()
        expect(image_link).to_be_focused()
        assert page.evaluate("({url:location.href,scroll:scrollY})") == before
        image_link.click()
        expect(viewer).to_be_visible()
        viewer.get_by_role("button", name="Close image preview", exact=True).click()
        expect(viewer).to_be_hidden()
        expect(image_link).to_be_focused()
    # Even an image that initially fits at 100% can be enlarged by a wheel gesture.
    # Its retained Fit command must remain available after that manipulation.
    resized(page, 2200, 1600)
    image_link.click()
    expect(viewer.locator("img.pswp__img")).to_be_visible()
    expect(
        viewer.get_by_role("button", name="Zoom to actual size", exact=True)
    ).to_be_disabled()
    page.mouse.move(1100, 800)
    page.keyboard.down("Control")
    page.mouse.wheel(0, -300)
    page.keyboard.up("Control")
    fit = viewer.get_by_role("button", name="Fit image", exact=True)
    expect(fit).to_be_enabled()
    fit.click()
    expect(viewer.locator("img.pswp__img")).to_have_css("width", "1800px")
    page.keyboard.press("Escape")
    page.locator("#other").click()
    expect(page).to_have_url(re.compile(r"#context$"))
    expect(viewer).to_be_hidden()


def test_an_image_only_composer_names_and_lays_out_the_draft_it_keeps(browser, serve):
    """The compact composer reads the complete draft hidden behind its text box.

    Several images make its shelf overflow, proving the anchored box gets the same
    horizontal thumbnail projection as the larger thread text boxes. The shelf stands
    above the field, so attaching leaves the box and its words where they were.
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
        assert (
            picture.bounding_box()["y"] + picture.bounding_box()["height"]
            <= (field_box["y"])
        )
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


@pytest.mark.parametrize("touch", [False, True])
def test_capture_leaves_selected_content_visible_through_the_drag(
    browser, serve, touch
):
    page = capture_page(browser, serve, touch=touch)
    baseline = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    target = page.locator("#capture-copy").bounding_box()
    left, top = int(target["x"]) + 100, int(target["y"]) + 4
    surface = open_capture_area(page, touch=touch)
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
    page.mouse.up()
    page.keyboard.press("Escape")


def test_touch_capture_can_cancel_and_reopen_before_attaching(browser, serve):
    page = capture_page(browser, serve, touch=True)
    touch = page.context.new_cdp_session(page)
    # Retain the native event so the assertion reads its final cancellation state.
    page.evaluate("""() => {
        window.captureTouchStarts = [];
        window.addEventListener('touchstart', event => captureTouchStarts.push(event),
            {capture: true, passive: true});
    }""")

    def drag_area():
        target = page.locator("#capture-target").bounding_box()
        left, top = int(target["x"]) + 10, int(target["y"]) + 20
        for kind, points in (
            ("touchStart", [{"x": left, "y": top}]),
            ("touchMove", [{"x": left + 180, "y": top + 130}]),
            ("touchEnd", []),
        ):
            touch.send(
                "Input.dispatchTouchEvent", {"type": kind, "touchPoints": points}
            )

    before = events_model.read_events(serve.page_dir)
    before_media = sorted((serve.page_dir / "media").iterdir())
    surface = open_capture_area(page, touch=True)
    drag_area()
    page.get_by_role("button", name="Cancel capture", exact=True).tap()
    expect(surface).to_be_hidden()
    assert page.evaluate("captureTouchStarts.at(-2).defaultPrevented"), (
        "a selection must consume its native touch gesture, including fling generation"
    )
    assert page.evaluate("!captureTouchStarts.at(-1).defaultPrevented")
    expect(page.locator(".lf-composer-media-item")).to_have_count(0)
    assert events_model.read_events(serve.page_dir) == before
    assert sorted((serve.page_dir / "media").iterdir()) == before_media
    surface = open_capture_area(page, touch=True)
    drag_area()
    page.get_by_role("button", name="Cancel capture", exact=True).press("Enter")
    expect(surface).to_be_hidden()
    expect(page.locator(".lf-composer-media-item")).to_have_count(0)
    surface = open_capture_area(page, touch=True)
    page.keyboard.press("Escape")
    expect(surface).to_be_hidden()
    expect(page.locator(".lf-composer-media-item")).to_have_count(0)
    surface = open_capture_area(page, touch=True)
    # A new press must belong to its own gesture, even before queued work from
    # the preceding drag runs. Keep that ordering independent of machine load.
    page.clock.install(time=0)
    page.clock.pause_at(1)
    drag_area()
    expect(surface.locator(".lf-region-selection")).to_be_visible()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.get_by_role("button", name="Attach capture", exact=True).tap()
        assert surface.get_attribute("aria-busy") == "true", (
            "the first confirmation tap must start capture before drag timers run"
        )
        page.clock.resume()
    expect(surface).to_be_hidden()
    attachment = page.locator(".lf-composer-media-item img")
    expect(attachment).to_be_visible()
    image = Image.open(serve.page_dir / attachment.get_attribute("src").lstrip("/"))
    assert image.size == (360, 260)
    assert events_model.read_events(serve.page_dir) == before
    assert page.evaluate("!captureTouchStarts.at(-1).defaultPrevented")
    touch.detach()


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
        box = control.bounding_box()
        left, top = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(left, top)
        page.mouse.down()
        page.mouse.move(left + 180, top + 100, steps=5)
        page.mouse.up()
        selected = surface.locator(".lf-region-selection").bounding_box()
        assert selected["width"] == pytest.approx(180)
        assert selected["height"] == pytest.approx(100)
        rendered(page)
        expect(control).not_to_be_checked()
        expect(page.locator(".lf-drawing-mark")).to_have_count(0)
        expect(page.locator(".lf-fab-input")).to_be_hidden()
        if attach:
            with page.expect_response(
                lambda response: response.url.endswith("/api/media")
            ):
                page.get_by_role("button", name="Attach capture", exact=True).click()
            expect(page.locator(".lf-composer-media-item img")).to_be_visible()
        else:
            page.keyboard.press("Escape")
        expect(surface).to_be_hidden()
        expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
        expect(page.locator(".lf-drawing-mark")).to_have_count(0)
        expect(control).not_to_be_checked()
        assert events_model.read_events(serve.page_dir) == before


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
    page.mouse.up()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.keyboard.press("Enter")
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
    page.mouse.up()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.keyboard.press("Enter")
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
