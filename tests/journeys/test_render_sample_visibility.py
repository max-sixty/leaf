"""Opaque sample exposure uses current native clipping and parent admission."""

import pytest
from render_harness import (
    open_threads,
    panel_settled,
)

from journeys.test_render_read_state import (
    _expect_news,
    _message_body,
    _on_me_mark,
    _open_first_unread,
    _read_by_the_sample,
    _sample_reading_page,
    _scroll_to_message,
    _still_unread,
)


@pytest.mark.shifts_unsurveyed
def test_narrowing_a_partially_clipped_sample_does_not_acknowledge_hidden_words(
    browser, serve
):
    """Both widths leave the tall frame partly intersecting, without crossing its
    observer's 0/1 thresholds. The message must use the new containing clip when it
    opens, rather than the viewport rectangle transferred at the old width. This test
    deliberately resizes the clip, reflowing the sample's header and frame."""
    page, _, child = _sample_reading_page(
        browser,
        serve,
        '<h1>Current clipping</h1><div id="clip">{sample}</div>',
        "#clip { width: 950px; height: 500px; overflow: hidden; }"
        "#clip iframe { min-width: 900px; }",
    )
    page.locator("#clip").evaluate("clip => clip.style.width = '250px'")
    _on_me_mark(child).evaluate("mark => mark.focus({preventScroll: true})")
    _open_first_unread(page, child)
    # The sample's panel stands at its frame's foot, so the clip is scrolled to show
    # the message's lines, cut at the narrow clip's right edge.
    _scroll_to_message(page, child, "document.querySelector('#clip')")
    _still_unread(page, child)

    page.locator("#clip").evaluate("clip => clip.style.width = '950px'")
    _read_by_the_sample(page, child)


def test_sample_admission_follows_parent_inertness_and_native_modal(browser, serve):
    page, _, child = _sample_reading_page(
        browser,
        serve,
        '<h1>Parent admission</h1><section id="owner">{sample}</section>'
        '<dialog id="modal"><button>Modal action</button></dialog>',
        "",
    )
    child.evaluate("""async () => {
      const module = await window.__lfCheckApi();
      window.sampleIsVisible = () => module.frameVisibility().visible;
      window.sampleCurrentReading = module.readSampleVisibility;
    }""")
    child.wait_for_function("sampleIsVisible()")

    page.locator("#owner").evaluate("owner => owner.inert = true")
    child.wait_for_function("!sampleIsVisible()")
    page.locator("#owner").evaluate("owner => owner.inert = false")
    child.wait_for_function("sampleIsVisible()")

    page.locator("#owner").evaluate("owner => owner.style.visibility = 'hidden'")
    assert not child.evaluate("sampleCurrentReading()")["visible"]
    page.locator("#owner").evaluate("owner => owner.style.visibility = ''")
    assert child.evaluate("sampleCurrentReading()")["visible"]
    page.locator("#owner").evaluate(
        "owner => owner.setAttribute('aria-hidden', 'true')"
    )
    assert not child.evaluate("sampleCurrentReading()")["visible"]
    page.locator("#owner").evaluate("owner => owner.removeAttribute('aria-hidden')")
    assert child.evaluate("sampleCurrentReading()")["visible"]

    page.locator("#modal").evaluate("modal => modal.showModal()")
    child.wait_for_function("!sampleIsVisible()")
    page.locator("#modal").evaluate("modal => modal.close()")
    child.wait_for_function("sampleIsVisible()")
    _expect_news(child)


def test_sample_exposure_preserves_parent_declared_occlusion(browser, serve):
    """The browser's implicit intersection sees through a nonmodal parent panel;
    the containing geometry owner must still withhold the words under that panel. The
    containing page's open Threads view stands over its window's foot, and the page is
    scrolled so the sample's message reaches 20px under it."""
    page, _, child = _sample_reading_page(
        browser,
        serve,
        "<h1>Containing chrome</h1>{sample}",
        "#read-practice { min-width: 950px; }",
    )
    open_threads(page)
    _on_me_mark(child).evaluate("mark => mark.focus({preventScroll: true})")
    _open_first_unread(page, child)
    bottom = _message_body(child).evaluate(
        "body => body.getBoundingClientRect().bottom"
    )
    page.evaluate(
        """([bottom, card]) => scrollBy(0, document.querySelector('#read-practice iframe')
            .getBoundingClientRect().top + bottom - card.getBoundingClientRect().top - 20)""",
        [bottom, page.locator(".lf-fp-card").element_handle()],
    )
    message = _message_body(child).bounding_box()
    panel = page.locator(".lf-fp-card").bounding_box()
    assert message["y"] + message["height"] > panel["y"]
    _still_unread(page, child)

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    # The sample's thread stays open, so its row's seat holds that thread's Close.
    child.locator(".lf-fp-close").evaluate(
        "close => close.focus({preventScroll: true})"
    )
    _read_by_the_sample(page, child)
