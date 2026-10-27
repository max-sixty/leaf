"""A framed Leaf document reads as visible while its frame shows on screen
(runtime/frame-visibility.js), whatever its own styles do, and places focus only once
the user enters it (runtime/focus.js, `canPlaceFocus`)."""

from playwright.sync_api import expect
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
    """A same-origin parent may embed a live page in an ordinary iframe, here inside
    another. Scrolled out of the top page's scrolling pane, the frame is not on screen,
    which Firefox answers by rendering it about once a second. Under `visibility:
    hidden` on the outer iframe it shows nothing either, and showing it again is
    announced, as reading resumes on that. Under `content-visibility: hidden` on the
    inner iframe itself, Chrome stops rendering it altogether, so a reading that took
    it for visible would wait forever for the update its last request asked for."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Embedding page",
                """
<h1>Embedding page</h1>
<div id="pane" style="height: 300px; overflow: auto">
  <iframe id="outer" title="Outer" style="width: 600px; height: 250px"></iframe>
  <div style="height: 2000px"></div>
</div>
""",
            )
        ),
    )
    page.locator("#outer").evaluate("""outer => {
      const inner = outer.contentDocument.createElement('iframe');
      inner.style.cssText = 'width: 500px; height: 200px';
      inner.src = location.href;
      outer.contentDocument.body.append(inner);
    }""")
    outer = page.locator("#outer")
    inner = outer.element_handle().content_frame().locator("iframe")
    embedded = inner.element_handle().content_frame()
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
    outer.evaluate("frame => frame.style.visibility = 'hidden'")
    embedded.wait_for_function("lastHeard === false")
    assert not embedded.evaluate("frameIsVisible()")
    outer.evaluate("frame => frame.style.visibility = ''")
    embedded.wait_for_function("lastHeard === true")

    inner.evaluate("frame => frame.style.contentVisibility = 'hidden'")
    # A resize asks the runtime for a rendering update the hidden frame never gets.
    assert embedded.evaluate("""() => {
      dispatchEvent(new Event('resize'));
      const state = document.querySelector('script[data-lf-entry]').lfRenderingState();
      return state.updatesSettled && state.preparationsSettled;
    }""")


def test_a_framed_page_moves_nobody_until_the_user_enters_it(browser, serve):
    """A page arriving starts Tab at its first control by focusing its body, and travel
    to a fragment puts the user on the heading it names. In a page framed in another,
    either would take the user out of the page they are working in: the embedding
    page's control they just pressed would lose its focus to the frame. A framed page
    holds no user until they enter it, so neither its arrival nor the embedding page
    sending it to a fragment moves anybody; a press inside it still lands them where
    Leaf puts them, here the composer an ⌥-press opens."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Embedding page",
                """
<h1>Embedding page</h1>
<button id="here" type="button">Stay here</button>
<a id="go" href="#far" target="embedded">Read on in the frame</a>
<iframe id="frame" name="embedded" title="Embedded page"
  style="width: 600px; height: 250px"></iframe>
<p id="passage">A passage to comment on.</p>
<h2 id="far" style="margin-top: 1500px">Far heading</h2>
""",
            )
        ),
    )
    here = page.locator("#here")
    here.click()
    page.locator("#frame").evaluate("frame => frame.src = location.href")
    embedded = page.locator("#frame").element_handle().content_frame()
    embedded.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    expect(here).to_be_focused()

    go = page.locator("#go")
    go.evaluate("(go, url) => go.href = url + '#far'", embedded.url)
    # Travel is the navigation's handler (history.js), so the navigation succeeds once
    # travel has landed and put focus wherever it was going to.
    embedded.evaluate("""() => {
      window.travelled = new Promise((resolve) =>
        navigation.addEventListener('navigatesuccess', resolve, { once: true }));
    }""")
    go.click()
    assert (
        embedded.evaluate("() => window.travelled.then(() => location.hash)") == "#far"
    )
    assert page.evaluate("document.activeElement.id") == "go"
    assert not embedded.evaluate("document.hasFocus()")

    embedded.locator("#passage").click(modifiers=["Alt"])
    expect(embedded.locator(".lf-composer leaf-text")).to_be_focused()
