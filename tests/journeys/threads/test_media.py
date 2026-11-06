"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.threads.test_media import DIAGRAM, DIAGRAM_SVG
from playwright.sync_api import expect
from render_harness import (
    holding,
    leaf_page,
    open_page,
    resized,
)

from leaf import exporting as exporting_model
from leaf.render_checks import rendered


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
