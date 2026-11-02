"""The motion recorder retains a run's identity while its words are edited."""

from browser_sources import browser_source
from journeys.test_floating_box_motion import jerks


def test_an_edit_keeps_the_first_letter_in_its_recorded_path(browser):
    page = browser.unwatched.new_page()
    page.add_init_script(browser_source("motion_frames.js"))
    page.goto(
        'data:text/html,<div id="box"><span style="position:relative">A</span></div>'
    )
    page.evaluate('lfMotionFrames.begin({box:"#box",ring:"#missing"})')
    page.wait_for_function("lfMotionFrames.count() >= 2")
    mark = page.evaluate("lfMotionFrames.inputs()")
    page.evaluate("""() => {
      const run = document.querySelector('span');
      run.firstChild.appendData('b');
      run.style.top = '100px';
      run.dispatchEvent(new InputEvent('input', {bubbles:true}));
    }""")
    count = page.evaluate("lfMotionFrames.count()")
    page.wait_for_function("count => lfMotionFrames.count() > count", arg=count)
    page.evaluate("document.querySelector('span').style.top = '0px'")
    count = page.evaluate("lfMotionFrames.count()")
    page.wait_for_function("count => lfMotionFrames.count() > count", arg=count)
    frames = page.evaluate("lfMotionFrames.end()")
    assert jerks(frames, [mark]), frames
