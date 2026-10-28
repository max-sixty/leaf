"""A recording's bar (`runtime/video-controls.js`): full screen by its button or `f`."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page

pytestmark = pytest.mark.shifts_unsurveyed

RECORDING = leaf_page(
    "Recording",
    '<h1>Recording</h1><video id="video" controls width="320" height="180" '
    'aria-label="Test pattern" src="/media/2930ad3df7819c50.mp4"></video>',
)
# Each also waits for the bar's answer, which follows the browser's change.
FILLS = "v => document.fullscreenElement === v && v.controls"
LEFT = "v => document.fullscreenElement === null && !v.controls"
KEYS = "Space ArrowLeft ArrowRight f"


@pytest.mark.parametrize("touch", [False, True], ids=["keyboard", "touch"])
def test_a_recording_fills_the_screen_under_the_browsers_controls(
    browser, serve, touch
):
    """`f` on the video, or a finger on the bar's Full screen button, puts the video in
    full screen with focus on it. The bar lies outside the video, so while it fills the
    screen the browser's controls and keys stand in for it, each press acting once, and
    leaving full screen gives the bar its place back."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844} if touch else None, has_touch=touch
    )
    page = open_page(browser, serve(RECORDING), context=context)
    video = page.locator("#video")
    handle = video.element_handle()
    page.wait_for_function("v => v.readyState >= 2", arg=handle)
    if touch:
        bar = page.get_by_role("group", name="Test pattern")
        bar.get_by_role("button", name="Full screen").tap()
    else:
        video.focus()
        page.keyboard.press("f")
    page.wait_for_function(FILLS, arg=handle)
    assert video.evaluate("v => document.activeElement === v")
    assert video.get_attribute("aria-keyshortcuts") is None
    if not touch:
        page.keyboard.press("Space")
        page.wait_for_function("v => !v.paused", arg=handle)
        page.keyboard.press("Space")
        page.wait_for_function("v => v.paused", arg=handle)

    page.evaluate("() => document.exitFullscreen()")
    page.wait_for_function(LEFT, arg=handle)
    expect(video).to_have_attribute("aria-keyshortcuts", KEYS)
