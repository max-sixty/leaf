"""Tests scheduled by the measured cost of their boundary."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page


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

    # Pausing aligns every recording to the furthest one's time. Chromium truncates
    # a seek to whole microseconds, which moves about one playback position in fifty
    # back by one, so a recording left unseeked would stay a microsecond ahead.
    play.tap()
    videos.last.evaluate("trailing => trailing.pause()")
    # Pause and resume the leading recording natively until it stops on such a
    # position; without one the step cannot tell the fix from the old seek loop, so
    # the wait's deadline fails the test rather than letting it pass.
    page.wait_for_function(
        """() => {
          if (window.resumingLeader) return false;
          const leading = document.querySelector('video');
          leading.pause();
          const time = leading.currentTime;
          if (Math.trunc(time * 1e6) !== Math.round(time * 1e6)) return true;
          window.resumingLeader = leading.play().finally(() => {
            window.resumingLeader = null;
          });
          return false;
        }"""
    )
    play.tap()
    moments = videos.evaluate_all("vs => vs.map(v => v.currentTime)")
    assert moments[0] == moments[1]

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
