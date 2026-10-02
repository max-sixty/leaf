"""The real-browser gate the everyday suite keeps."""

from pathlib import Path

import pytest
from leaf import event_log as events_model
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import holding, open_page, resized

ROOT = Path(__file__).parent.parent


def test_a_shipped_page_passes_the_real_browser_gate(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    assert render_gate_model.render_version(browser, serve(example)).failures == []


def test_ship_review_asks_are_directly_answerable(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    page = open_page(browser, serve(example))

    expect(page.locator(".lf-asks")).to_have_text("Asks 1/2")
    expect(page.locator("#off-workaround-review .lf-pick")).to_have_count(2)
    expect(page.locator("#off-workaround-review .lf-pick").first).to_be_visible()
    expect(page.locator("#off-workaround-approve .lf-pick")).to_have_attribute(
        "aria-checked", "true"
    )
    # A shortcut bar with no rows in it is silent: the chrome paints, the console stays
    # clean, and every other everyday assertion holds while no user can see a key.
    # The boot's own failure is loud and covered by `errors` below, so what is asked
    # for here is the rows — the More control's keycap is static and would show
    # whatever happened. At rest a page shows `c` and `e`.
    expect(
        page.locator(".lf-shortcut-bar .lf-shortcut:not([hidden])")
    ).not_to_have_count(0)
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "2")


@pytest.mark.parametrize("size", [(1200, 520), (509, 429)])
@pytest.mark.parametrize("prior_turns", [1, 5])
def test_a_sent_margin_reply_shows_its_words_while_delivery_is_pending(
    browser, serve, size, prior_turns
):
    """Sending reveals the new turn, including when its POST cannot complete.

    The editor is outside the margin transcript's scrollport. Reusing its former
    scroll offset after adding a turn leaves only the new turn's metadata above
    the editor, with the words clipped below the transcript's foot.
    """
    history = (
        "The current keyboard API forwards the widget commands at the question. "
        "Numbers stay active while you read the question or operate the widget, "
        "and disappear while typing or after moving outside that scope. "
    )
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Opening turn. " + history, {"section": "how-store"}
    )
    for turn in range(prior_turns):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root,
                "text": f"Turn {turn}. " + history,
            },
        )
    page = open_page(browser, url)
    resized(page, *size)
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    page.keyboard.press("c")
    reply = card.locator("leaf-text")
    expect(reply).to_be_focused()
    words = "The sent reply must be readable above the composer."
    page.keyboard.type(words)
    pending = []
    page.route("**/api/event", lambda route: pending.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, pending, 1, "the margin reply")
    latest = card.locator(".lf-msg.user").last
    expect(latest.locator(".lf-msg-sending")).to_have_text("Sending")
    body = latest.locator(".lf-msg-body")
    expect(body).to_have_text(words)
    # Allow subpixel rounding at the transcript's scroll edge.
    expect(body).to_be_in_viewport(ratio=0.99)
    assert pending, "The reply POST must still be pending when its body is checked"
