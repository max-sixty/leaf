"""Motion studies share an inspectable clock across authored views and release it
when detached. Playback and seeking remain local presentation state."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page

from leaf.render_checks import wait_until_ready


def test_motion_views_seek_together_and_play_only_while_requested(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Motion comparison",
                """<h1>Motion comparison</h1>
<div id="holder" style="min-height: 400px">
  <lf-motion id="study" duration="1000" aria-label="Two travel sketches">
    <svg viewBox="0 0 300 80" role="img" aria-label="Forward travel">
      <circle id="forward" cx="20" cy="40" r="10" />
    </svg>
    <svg viewBox="0 0 300 80" role="img" aria-label="Return travel">
      <circle id="backward" cx="280" cy="40" r="10" />
    </svg>
  </lf-motion>
</div>""",
                head='<script type="module" src="/page/draw.js"></script>',
            ),
            packages=("motion",),
            page_files={
                "draw.js": """
import { keeps } from '/runtime/widget-api.js';
await customElements.whenDefined('lf-motion');
const study = document.getElementById('study');
const forward = study.querySelector('#forward');
const backward = study.querySelector('#backward');
study.renderFrame = time => {
  keeps(forward, 'cx', 20 + 260 * time / 1000);
  keeps(backward, 'cx', 280 - 260 * time / 1000);
};
"""
            },
        ),
    )
    play = page.locator(".lf-motion-play")
    time = page.get_by_role("slider", name="Time", exact=True)
    forward = page.locator("#forward")
    backward = page.locator("#backward")
    expect(play).to_have_accessible_name("Play")
    expect(play).to_have_text("")
    expect(page.locator(".lf-motion-controls button")).to_have_count(1)

    # Native range keys seek both ways and repaint all compared views immediately.
    time.press("End")
    expect(forward).to_have_attribute("cx", "280")
    expect(backward).to_have_attribute("cx", "20")
    time.press("ArrowLeft")
    expect(time).to_have_value("999")
    assert float(forward.get_attribute("cx")) == pytest.approx(279.74)
    assert float(backward.get_attribute("cx")) == pytest.approx(20.26)

    # Returning to the page restores the chosen inspection without starting motion.
    speed = page.get_by_role("combobox", name="Speed")
    speed.select_option("0.25")
    page.reload()
    wait_until_ready(page)
    expect(time).to_have_value("999")
    expect(speed).to_have_value("0.25")
    expect(play).to_have_accessible_name("Play")
    assert float(forward.get_attribute("cx")) == pytest.approx(279.74)
    assert float(backward.get_attribute("cx")) == pytest.approx(20.26)
    page.clock.install(time=0)
    page.clock.pause_at(1)
    page.clock.run_for(160)
    expect(time).to_have_value("999")

    time.press("Home")
    expect(forward).to_have_attribute("cx", "20")
    expect(backward).to_have_attribute("cx", "280")

    play.click()
    expect(play).to_have_accessible_name("Pause")
    page.clock.run_for(160)
    current = page.locator("#study").evaluate("study => study.currentTime")
    assert current == pytest.approx(40, abs=4)
    assert float(forward.get_attribute("cx")) == 20 + 260 * current / 1000
    assert float(backward.get_attribute("cx")) == 280 - 260 * current / 1000
    play.click()
    page.clock.run_for(160)
    assert page.locator("#study").evaluate("study => study.currentTime") == current

    time.press("End")
    play.click()
    page.clock.run_for(160)
    assert page.locator("#study").evaluate(
        "study => study.currentTime"
    ) == pytest.approx(40, abs=4)
    play.click()
    current = page.locator("#study").evaluate("study => study.currentTime")

    play.click()
    page.evaluate(
        "window.detachedStudy = document.getElementById('study'); detachedStudy.remove()"
    )
    page.clock.run_for(160)
    assert page.evaluate("detachedStudy.currentTime") == current
    page.evaluate("document.getElementById('holder').append(detachedStudy)")
    page.clock.run_for(160)
    expect(play).to_have_accessible_name("Play")
    assert page.locator("#study").evaluate("study => study.currentTime") == current

    page.emulate_media(reduced_motion="reduce")
    expect(play).to_have_accessible_name("Show end")
    play.click()
    expect(time).to_have_value("1000")
    expect(forward).to_have_attribute("cx", "280")
    expect(backward).to_have_attribute("cx", "20")
    time.press("Home")
    expect(forward).to_have_attribute("cx", "20")
    expect(backward).to_have_attribute("cx", "280")


def test_motion_recordings_share_native_playback_and_a_sticky_transport(browser, serve):
    context = browser.new_context(
        viewport={"width": 390, "height": 600}, has_touch=True
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Recorded comparison",
                """<h1>Recorded comparison</h1>
<div id="holder">
  <lf-motion id="study" duration="8000" aria-label="Two recordings">
    <figure style="margin: 0; padding-block-end: 160px">
      <video muted playsinline width="320" height="180"
        aria-label="Current" src="/media/2930ad3df7819c50.mp4"></video>
      <figcaption>Current</figcaption>
    </figure>
    <figure style="margin: 0; padding-block-end: 160px">
      <video muted playsinline width="320" height="180"
        aria-label="Candidate" src="/media/2930ad3df7819c50.mp4"></video>
      <figcaption>Candidate</figcaption>
    </figure>
  </lf-motion>
</div>""",
                head="<style>#study video { border-radius: 17px; }</style>",
            ),
            packages=("motion",),
        ),
        context=context,
    )
    page.wait_for_function(
        "[...document.querySelectorAll('video')].every(v => v.readyState >= 2)"
    )
    videos = page.locator("video")
    expect(videos.first).to_have_css("border-radius", "17px")
    assert videos.evaluate_all("vs => vs.every(v => v.paused && v.currentTime === 0)")
    page.evaluate(
        """() => {
          window.videoSeeks = 0;
          document.querySelectorAll('video').forEach(video => {
            video.addEventListener('seeking', () => window.videoSeeks++);
          });
        }"""
    )
    play = page.locator(".lf-motion-play")
    time = page.get_by_role("slider", name="Time", exact=True)
    play.tap()
    page.wait_for_function(
        "[...document.querySelectorAll('video')].every(v => !v.paused && v.currentTime > 0)"
    )
    # Native media advances; the transport must not seek each decoded frame.
    assert page.evaluate("window.videoSeeks") == 0
    play.tap()
    assert videos.evaluate_all("vs => vs.every(v => v.paused)")
    # A fractional seek exercises native media precision without timing playback.
    for requested_time in (None, 252.00699999999998):
        if requested_time is not None:
            page.locator("#study").evaluate(
                "(study, time) => study.currentTime = time", requested_time
            )
        moments = videos.evaluate_all("vs => vs.map(v => v.currentTime)")
        assert moments[0] == moments[1]
        # Native seeking can truncate a microsecond; allow that plus float rounding.
        assert moments[0] * 1000 == pytest.approx(
            page.locator("#study").evaluate("study => study.currentTime"),
            rel=0,
            abs=0.002,
        )

    page.get_by_role("combobox", name="Speed").select_option("0.25")
    assert videos.evaluate_all("vs => vs.every(v => v.playbackRate === 0.25)")
    time.press("End")
    assert videos.evaluate_all("vs => vs.every(v => v.currentTime === 8 && v.paused)")
    play.tap()
    page.wait_for_function(
        "[...document.querySelectorAll('video')].every(v => !v.paused && v.currentTime < 8)"
    )
    play.tap()

    # The same controls remain reachable when stacked previews extend past the screen.
    page.mouse.wheel(0, 300)
    page.wait_for_function("document.scrollingElement.scrollTop >= 250")
    controls = page.locator(".lf-motion-controls")
    box = controls.bounding_box()
    top = controls.evaluate("el => parseFloat(getComputedStyle(el).top)")
    assert box["y"] == pytest.approx(top, abs=1)
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390
    time.press("Home")
    assert videos.evaluate_all("vs => vs.every(v => v.currentTime === 0)")

    play.tap()
    page.wait_for_function(
        "[...document.querySelectorAll('video')].every(v => !v.paused)"
    )
    page.evaluate(
        "window.detachedStudy = document.getElementById('study'); detachedStudy.remove()"
    )
    assert page.evaluate(
        "[...detachedStudy.querySelectorAll('video')].every(v => v.paused)"
    )
