"""Opaque sample visibility follows the frame's viewport on screen."""

from render_harness import leaf_page, open_page


def test_a_window_sample_scrolled_past_its_first_screen_stays_visible(browser, serve):
    """A live page's root box is one viewport tall, so scrolling the sample's own page
    past its first screen takes that box out of view while the frame stays on screen.
    The child's own observer of the root box says when that has happened; the sample's
    observer, created first, has had its delivery by then."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Scrolling sample",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample>
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
    child.evaluate("""async () => {
      const module = await window.__lfCheckApi();
      window.sampleIsVisible = () => module.sampleVisibility().visible;
      window.rootLeft = false;
      new IntersectionObserver(([entry]) => {
        window.rootLeft = entry.intersectionRect.height === 0;
      }, { threshold: [0, Number.EPSILON] }).observe(document.documentElement);
    }""")
    child.wait_for_function("sampleIsVisible()")

    box = frame.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 2 * box["height"])
    child.wait_for_function("rootLeft")
    assert child.evaluate("sampleIsVisible()")

    # Control: the containing page scrolling the frame off screen hides the sample.
    page.mouse.move(box["x"] / 2, box["y"] / 2)
    page.mouse.wheel(0, box["y"] + box["height"] + 100)
    # Chrome stops running animation frames in a cross-origin frame off screen, so
    # the wait polls on a timer.
    child.wait_for_function("!sampleIsVisible()", polling=100)
