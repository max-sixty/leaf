"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.controls import LIVE_SAMPLES_PAGE
from browser.controls.test_live_samples import RING_INK
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, put_preview_away, rendered, resized

from leaf_dev.rings import current_location_ring

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_gutter_shows_while_keys_go_to_the_sample(browser, serve):
    """A press into the sample's page takes the user's keys there as a Tab does, though
    the containing page hears no focus event, and the gutter says so until they leave.
    Only the Tab rings the frame, as it would any control."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    sample = page.locator("#first-practice")
    sample.evaluate("async sample => { await sample.ready; }")
    gutter = sample.locator(".lf-sample-exhibit")
    resting = gutter.evaluate("el => getComputedStyle(el).borderLeftColor")
    ring_ink = page.evaluate(RING_INK)
    assert resting != ring_ink
    frame = sample.locator("iframe")
    child = frame.element_handle().content_frame()

    child.locator("#child-heading").click()
    expect(gutter).to_have_css("border-left-color", ring_ink)
    rendered(page)
    assert current_location_ring(page) is None
    page.locator("#host-heading").click()
    expect(gutter).to_have_css("border-left-color", resting)

    sample.get_by_role("button", name="Full view", exact=True).focus()
    page.keyboard.press("Tab")
    expect(gutter).to_have_css("border-left-color", ring_ink)
    rendered(page)
    assert current_location_ring(page)
    child.locator("#child-heading").click()
    rendered(page)
    assert current_location_ring(page) is None
    expect(gutter).to_have_css("border-left-color", ring_ink)
    page.keyboard.press("Tab")
    rendered(page)
    assert current_location_ring(page)
    page.keyboard.press("Shift+Tab")
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_focused()
    expect(gutter).to_have_css("border-left-color", resting)


def test_tab_walks_into_and_out_of_a_full_view_sample(browser, serve):
    """Full view is modal and holds its frame, and Tab is the browser's there: it walks
    into the child's controls, on out of the frame, and round to the view's own controls,
    never onto the page beneath."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    sample = page.locator("#first-practice")
    frame = sample.locator("iframe")
    child = frame.element_handle().content_frame()
    gutter = sample.locator(".lf-sample-exhibit")
    ring_ink = page.evaluate(RING_INK)
    sample.get_by_role("button", name="Full view", exact=True).click()
    view = sample.locator("dialog.lf-sample-view")
    expect(
        sample.get_by_role("button", name="Return to page", exact=True)
    ).to_be_focused()

    # Where focus stands in the containing page: in the view, on its frame, or out at
    # the browser's own interface.
    current_location = """view => {
      let at = document.activeElement;
      while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
      if (at === document.body) return "browser";
      if (!view.contains(at)) return "page";
      return at.localName === "iframe" ? "frame" : "view";
    }"""
    entered = left = False
    for _ in range(40):
        page.keyboard.press("Tab")
        at = view.evaluate(current_location)
        assert at != "page", "Tab left Full view for the page beneath"
        if at == "frame" and child.evaluate("() => document.hasFocus()"):
            expect(gutter).to_have_css("border-left-color", ring_ink)
            rendered(page)
            assert current_location_ring(page)
        entered |= at == "frame" and child.evaluate("() => document.hasFocus()")
        if entered and at == "view":
            left = True
            break
    assert entered, "Tab never entered the sample's own page"
    assert left, "Tab never came back out of the sample to the view's controls"

    # Back on the page, Tab past the child's last stop goes on to the page's next stop.
    # The child's last stop is Leaf's own, whose root follows body. The Tab onto the
    # view's control showed its preview, which the first Escape puts away.
    put_preview_away(page)
    page.keyboard.press("Escape")
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_focused()
    child.evaluate(
        """async () => {
          const { tabStops } = await window.__lfCheckApi();
          tabStops(document).at(-1).focus();
        }"""
    )
    expect(frame).to_be_focused()
    page.keyboard.press("Tab")
    expect(frame).not_to_be_focused()


def test_reading_keys_page_on_from_a_sample_to_its_page(browser, serve):
    """d/u in a sample whose own page is spent move the containing page, as the
    wheel does; in Full view the modal keeps them inside."""
    filler = "".join(
        f'<p id="line-{i}">Line {i} of a long child page.</p>' for i in range(60)
    )
    source = leaf_page(
        "Sample reading keys",
        f"""
<h1>Sample reading keys</h1>
<div style="height: 300px"></div>
<lf-sample id="block" label="A block sample">
  <template id="block-page" data-sample>
    <p id="child-text">A short child page.</p>
  </template>
</lf-sample>
<lf-sample id="window" label="A window sample" window>
  <template id="window-page" data-sample>{filler}</template>
</lf-sample>
<div style="height: 2400px"></div>
""",
    )
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1200, 800)
    block = page.locator("#block")
    block.evaluate("async sample => { await sample.ready; }")
    child = block.locator("iframe").element_handle().content_frame()
    assert child.evaluate("() => document.scrollingElement.scrollHeight <= innerHeight")
    child.locator("#child-text").click()
    page.keyboard.press("d")
    expect(page.locator(":root")).not_to_have_js_property("scrollTop", 0)
    below = page.evaluate("scrollY")
    page.keyboard.press("u")
    page.wait_for_function("below => scrollY < below", arg=below)

    window = page.locator("#window")
    window.evaluate("async sample => { await sample.ready; }")
    window.get_by_role("button", name="Full view", exact=True).click()
    inside = window.locator("iframe").element_handle().content_frame()
    inside.locator("#line-59").click()
    inside.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    at = page.evaluate("scrollY")
    page.keyboard.press("d")
    # The frame answers a call made after the press on the port its spent step would
    # take, so a step the frame passed on has reached this page by the answer.
    window.evaluate("sample => sample.restoreCurrentLocation()")
    assert page.evaluate("scrollY") == at
