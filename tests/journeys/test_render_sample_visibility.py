"""Opaque sample exposure uses current native clipping and parent admission."""

from playwright.sync_api import expect
from render_harness import panel_settled

from journeys.test_render_read_state import (
    _message_body,
    _open_first_unread,
    _read_by_the_sample,
    _sample_reading_page,
    _still_unread,
)


def test_narrowing_a_partially_clipped_sample_does_not_acknowledge_hidden_words(
    browser, serve
):
    """Both widths leave the tall frame partly intersecting, without crossing its
    observer's 0/1 thresholds. The message must use the new containing clip when it
    opens, rather than the viewport rectangle transferred at the old width."""
    page, _, child = _sample_reading_page(
        browser,
        serve,
        '<h1>Current clipping</h1><div id="clip">{sample}</div>',
        "#clip { width: 950px; height: 500px; overflow: hidden; }"
        "#clip iframe { min-width: 900px; }",
    )
    page.locator("#clip").evaluate("clip => clip.style.width = '250px'")
    child.locator(".lf-threads-toggle").evaluate(
        "toggle => toggle.focus({preventScroll: true})"
    )
    _open_first_unread(page, child)
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
      window.sampleIsVisible = () => module.sampleVisibility().visible;
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
    expect(child.locator(".lf-first-unread")).to_have_attribute(
        "aria-label", "1 unread message. Go to first unread message"
    )


def test_sample_exposure_preserves_parent_declared_occlusion(browser, serve):
    """The browser's implicit intersection sees through a nonmodal parent panel;
    the containing geometry owner must still withhold the words under that panel."""
    page, _, child = _sample_reading_page(
        browser,
        serve,
        "<h1>Containing chrome</h1>{sample}",
        "#read-practice { min-width: 950px; }",
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    child.locator(".lf-threads-toggle").evaluate(
        "toggle => toggle.focus({preventScroll: true})"
    )
    _open_first_unread(page, child)
    message = _message_body(child).bounding_box()
    panel = page.locator(".lf-threads").bounding_box()
    assert message["x"] + message["width"] > panel["x"]
    _still_unread(page, child)

    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)
    child.locator(".lf-threads-toggle").evaluate(
        "toggle => toggle.focus({preventScroll: true})"
    )
    _read_by_the_sample(page, child)
