"""A framed Leaf document reads as visible while its frame shows on screen
(runtime/frame-visibility.js), whatever its own styles do."""

from render_harness import leaf_page, open_page

VISIBLE = """async () => {
  const module = await window.__lfCheckApi();
  window.frameIsVisible = () => module.frameVisibility().visible;
}"""


def test_a_window_sample_scrolled_past_its_first_screen_stays_visible(browser, serve):
    """A live page's root box is one viewport tall, so scrolling the sample's own page
    past its first screen takes that box out of view while the frame stays on screen.
    The sample's page transforms `html`, which makes the root the containing block of
    any box the sample fixes over its viewport, so such a box scrolls away too. The
    child's own observer of the root box says when that has happened; the sample's
    reading has had its delivery by then."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Scrolling sample",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample>
    <style>html { transform: scale(1); }</style>
    <h1>Practice page</h1><div style="height: 4000px"></div>
  </template>
</lf-sample>
<div style="height: 2000px"></div>
""",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    frame = sample.locator("iframe")
    child = frame.element_handle().content_frame()
    child.evaluate(VISIBLE)
    child.evaluate("""() => {
      window.rootLeft = false;
      new IntersectionObserver(([entry]) => {
        window.rootLeft = entry.intersectionRect.height === 0;
      }, { threshold: [0, Number.EPSILON] }).observe(document.documentElement);
    }""")
    child.wait_for_function("frameIsVisible()")

    box = frame.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 2 * box["height"])
    child.wait_for_function("rootLeft")
    assert child.evaluate("frameIsVisible()")

    # Control: the containing page scrolling the frame off screen hides the sample.
    page.mouse.move(box["x"] / 2, box["y"] / 2)
    page.mouse.wheel(0, box["y"] + box["height"] + 100)
    # Chrome stops running animation frames in a cross-origin frame off screen, so
    # the wait polls on a timer.
    child.wait_for_function("!frameIsVisible()", polling=100)


def test_a_same_origin_frame_reads_hidden_and_settled_off_screen(browser, serve):
    """A same-origin parent may embed a live page in an ordinary iframe. Scrolled out of
    its parent's scrolling pane, the frame is not on screen, which Firefox answers by
    rendering it about once a second. Under `visibility: hidden` it shows nothing
    either, and showing it again is announced, as reading resumes on that. Under
    `content-visibility: hidden` on the iframe itself, Chrome stops rendering it
    altogether, so a reading that took it for visible would wait forever for the
    update its last request asked for."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Embedding page",
                """
<h1>Embedding page</h1>
<div id="pane" style="height: 300px; overflow: auto">
  <iframe id="embedded" title="Embedded" style="height: 200px"></iframe>
  <div style="height: 2000px"></div>
</div>
""",
            )
        ),
    )
    page.locator("#embedded").evaluate("frame => frame.src = location.href")
    embedded = page.locator("#embedded").element_handle().content_frame()
    embedded.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    embedded.evaluate(VISIBLE)
    embedded.wait_for_function("frameIsVisible()")

    page.locator("#pane").evaluate("pane => pane.scrollTop = 1000")
    embedded.wait_for_function("!frameIsVisible()", polling=100)
    page.locator("#pane").evaluate("pane => pane.scrollTop = 0")
    embedded.wait_for_function("frameIsVisible()")

    embedded.evaluate("""async () => {
      const module = await window.__lfCheckApi();
      window.lastHeard = null;
      module.onFrameVisibility(({ visible }) => (window.lastHeard = visible));
    }""")
    page.locator("#embedded").evaluate("frame => frame.style.visibility = 'hidden'")
    embedded.wait_for_function("lastHeard === false")
    assert not embedded.evaluate("frameIsVisible()")
    page.locator("#embedded").evaluate("frame => frame.style.visibility = ''")
    embedded.wait_for_function("lastHeard === true")

    page.locator("#embedded").evaluate(
        "frame => frame.style.contentVisibility = 'hidden'"
    )
    # A resize asks the runtime for a rendering update the hidden frame never gets.
    assert embedded.evaluate("""() => {
      dispatchEvent(new Event('resize'));
      const state = document.querySelector('script[data-lf-entry]').lfRenderingState();
      return state.updatesSettled && state.preparationsSettled;
    }""")
