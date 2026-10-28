"""Motion studies share an inspectable clock across authored views and release it
when detached. Playback and seeking remain local presentation state."""

import pytest
from playwright.sync_api import expect
from render_harness import consume_browser_errors, leaf_page, open_page

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


def test_a_motion_failure_shows_beside_the_study_and_reaches_the_agent(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Motion failures",
                """<h1>Motion failures</h1>
<lf-motion id="sketch" duration="1000" aria-label="A sketch that breaks past its start">
  <figure id="sketch-study"><svg viewBox="0 0 300 80" role="img" aria-label="Travel">
    <circle id="dot" cx="20" cy="40" r="10" /></svg></figure>
</lf-motion>
<lf-motion id="recording" duration="1000" aria-label="A recording that cannot play">
  <figure><video muted playsinline width="160" height="90" aria-label="Clip"></video>
  </figure>
</lf-motion>""",
                head='<script type="module" src="/page/draw.js"></script>',
            ),
            packages=("motion",),
            page_files={
                "draw.js": """
await customElements.whenDefined('lf-motion');
document.getElementById('sketch').renderFrame = time => {
  if (time > 0) throw new Error('the frame broke');
};
"""
            },
        ),
    )
    # A press the browser refuses to play says so in the clock's place, and the agent
    # hears why.
    page.evaluate(
        """() => { HTMLMediaElement.prototype.play = () =>
          Promise.reject(new DOMException('no source to play', 'NotSupportedError')); }"""
    )
    recording = page.locator("#recording")
    recording.locator(".lf-motion-play").click()
    expect(recording.locator(".lf-motion-clock")).to_have_text("Failed")
    expect(recording.locator(".lf-motion-play")).to_have_accessible_name("Play")
    consume_browser_errors(page, "Playback failed: no source to play")

    # A frame that throws shows the box beside the transport, leaves the study whole,
    # and stops the clock: the box stays one, however often the failure recurs.
    sketch = page.locator("#sketch")
    expect(sketch.locator(".lf-motion-play")).not_to_have_attribute(
        "aria-disabled", "true"
    )
    time = sketch.get_by_role("slider", name="Time", exact=True)
    time.press("End")
    box = sketch.locator(":scope > .lf-error")
    expect(box).to_have_text("<lf-motion> failed: the frame broke")
    time.press("ArrowLeft")
    sketch.locator(".lf-motion-play").click()
    expect(box).to_have_count(1)
    expect(sketch.locator(".lf-motion-controls")).to_be_visible()
    expect(page.locator("#sketch-study #dot")).to_be_visible()
    expect(sketch.locator(".lf-motion-play")).to_have_accessible_name("Play")
    consume_browser_errors(page, "the frame broke")
    # A frame that draws again takes the box away.
    time.press("Home")
    expect(box).to_have_count(0)


# Each study's Play availability as the parser finishes, before any module runs.
FIRST_PAINT_PLAY = """
document.addEventListener('readystatechange', () => {
  if (document.readyState !== 'interactive') return;
  window.firstPlay = Object.fromEntries([...document.querySelectorAll('lf-motion')].map(
    (study) => [study.id, study.querySelector('.lf-motion-play')?.getAttribute('aria-disabled')
      ?? null]));
});
"""


def test_play_is_available_from_first_paint_only_where_there_is_something_to_play(
    browser, serve
):
    context = browser.new_context()
    context.add_init_script(FIRST_PAINT_PLAY)
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Play availability",
                """<h1>Play availability</h1>
<lf-motion id="recording" duration="1000" aria-label="A recording">
  <figure><video muted playsinline width="160" height="90" aria-label="Clip"></video>
  </figure>
</lf-motion>
<lf-motion id="sketch" duration="1000" aria-label="A sketch nothing draws">
  <figure><svg viewBox="0 0 300 80" role="img" aria-label="Travel"></svg></figure>
</lf-motion>""",
            ),
            packages=("motion",),
        ),
        context=context,
    )
    assert page.evaluate("window.firstPlay") == {"recording": None, "sketch": "true"}
    recording = page.locator("#recording .lf-motion-play")
    sketch = page.locator("#sketch .lf-motion-play")
    expect(recording).not_to_have_attribute("aria-disabled", "true")
    expect(sketch).to_have_attribute("aria-disabled", "true")
    # A study with nothing to play takes no press.
    sketch.click(force=True)
    expect(sketch).to_have_accessible_name("Play")
