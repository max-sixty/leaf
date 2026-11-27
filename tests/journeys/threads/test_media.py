"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.threads import capture_page, open_capture_area
from browser.threads.test_media import DIAGRAM, DIAGRAM_SVG
from PIL import Image
from playwright.sync_api import expect
from render_harness import (
    holding,
    leaf_page,
    open_page,
    press_visible,
    resized,
    stance_exit,
)

from leaf.log import event_log as events_model
from leaf.pages import exporting as exporting_model
from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.shifts_unsurveyed
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
        exporting_model.cmd_export(serve.page_dir, out, None, runtime=True)
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
        # A reader outside the page waits for the image, not the empty viewer.
        rendered(page, facts=("updatesSettled",))
        assert not page.evaluate(
            "document.querySelector('script[data-lf-entry]')"
            ".lfRenderingState().preparationsSettled"
        )
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
    expect(page.locator(".lf-fp-mode")).to_have_text("Capture")
    # The panel's row offers only the way out; lifting a drag attaches.
    expect(page.get_by_role("button", name="Attach capture", exact=True)).to_have_count(
        0
    )
    touch_area(3, 2)
    rendered(page)
    expect(surface).to_be_visible()
    expect(selection).to_be_hidden()
    stance_exit(page).tap()
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
