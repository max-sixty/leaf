"""The real-browser gate the everyday suite keeps."""

import re
from pathlib import Path

import pytest
from leaf import event_log as events_model
from leaf.render_checks import rendered
from leaf.render_gate import version as render_gate_model
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import holding, open_page, resized, scroll_settled

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
    rendered(page)
    assert card.locator(".lf-thread-transcript").evaluate("list => list.scrollTop") == 0
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


@pytest.mark.parametrize("how", ["key", "pointer"])
def test_a_pending_reply_keeps_the_transcript_end_when_card_fitting_reduces_room(
    browser, serve, how
):
    """The Send destination survives the geometry update after local presentation.

    At this width and height the fitted transcript loses room after Send. The old
    scroll destination stayed at 33px while its end moved to 60px, hiding the entire
    reply body. Hold delivery so admission cannot repaint and conceal the failure.
    """
    source = leaf_page(
        "Margin reply",
        "<h1>Reply beside a passage</h1>"
        '<section id="candidate"><h2>Candidate</h2>'
        "<p>Review this candidate and reply beside its passage.</p>"
        '<div style="height:600px"></div></section>',
        layout="wide",
    )
    url = serve(source)
    root = panel_comment(
        serve.page_dir,
        "the keybinding hints look bad? and are always there even when not active?",
        {"section": "candidate"},
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "text": (
                "I removed the prototype’s manually painted option digits. The candidate "
                "now uses the runtime’s bottom shortcut bar: its numeric hints appear at "
                "the question or widget, and disappear while typing or outside that scope. "
                "I checked those transitions and native digit entry in the browser. Shared "
                "inline badges remain part of the proposed keyboard API; they need the "
                "same reachability reading as dispatch."
            ),
        },
    )
    page = open_page(browser, url)
    resized(page, 636, 536)
    page.locator('[data-lf-margin-for="candidate"] .lf-margin-marker').click()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    page.keyboard.press("c")
    expect(card.locator("leaf-text")).to_be_focused()
    words = "Please scroll down to show this reply."
    page.keyboard.type(words)
    pending = []

    def hold_reply(route):
        if route.request.post_data_json["kind"] == "reply":
            pending.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold_reply)
    if how == "key":
        page.keyboard.press("ControlOrMeta+Enter")
    else:
        card.locator(".lf-thread-send").click()
    holding(page, pending, 1, "the pending reply")
    latest = card.locator(".lf-msg.user").last
    expect(latest.locator(".lf-msg-sending")).to_have_text("Sending")
    rendered(page)
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    expect(latest.locator(".lf-msg-body")).to_have_text(words)
    expect(latest.locator(".lf-msg-body")).to_be_in_viewport(ratio=0.99)
    assert pending, "The reply POST must still be pending after fitting"


def test_reading_keys_follow_a_submitted_comment_s_inner_viewport(browser, serve):
    """A long submitted comment retains its editor viewport inside the transcript.

    Reading keys must name that inner viewport, as native wheel/PageUp do, and
    closing it must release the region before another comment adopts the frame.
    """
    source = leaf_page(
        "Read a submitted comment",
        '<h1>Read a submitted comment</h1><p id="topic">A passage to discuss.</p>'
        '<div style="height:900px"></div>',
    )
    page = open_page(browser, serve(source))
    resized(page, 1000, 700)
    words = "\n".join(
        f"Line {line:02d}: A long comment stays readable after submission."
        for line in range(30)
    )
    pending = []

    def hold_comment(route):
        if route.request.post_data_json["kind"] == "comment":
            pending.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold_comment)
    for _ in range(2):
        page.locator("#topic").click(modifiers=["Alt"], position={"x": 40, "y": 10})
        expect(page.locator(".lf-fab-input")).to_be_focused()
        page.keyboard.insert_text(words)
        page.keyboard.press("ControlOrMeta+Enter")
        holding(page, pending, 1, "the submitted comment")
        body = page.locator(".lf-margin-preview .lf-msg-body").first
        expect(body).to_contain_text("Line 29:")
        expect(body.locator("..")).to_have_attribute(
            "data-event", re.compile("pending:.*")
        )
        rendered(page)
        before = body.evaluate("body => body.scrollTop")
        assert before > 0, "The submitted comment must start at its last lines"
        for _ in range(15):
            page.keyboard.press("Tab")
            if body.evaluate("body => document.activeElement === body"):
                break
        expect(body).to_be_focused()
        page.keyboard.press("u")
        page.wait_for_function(
            "before => document.querySelector('.lf-margin-preview .lf-msg-body').scrollTop < before",
            arg=before,
        )
        scroll_settled(page, ".lf-margin-preview .lf-msg-body")
        after = body.evaluate("body => body.scrollTop")
        assert after < before
        pending.pop().continue_()
        expect(body.locator("..")).not_to_have_attribute(
            "data-event", re.compile("pending:.*")
        )
        rendered(page)
        assert abs(body.evaluate("body => body.scrollTop") - after) <= 1
        page.keyboard.press("d")
        page.wait_for_function(
            "after => document.querySelector('.lf-margin-preview .lf-msg-body').scrollTop > after",
            arg=after,
        )
        scroll_settled(page, ".lf-margin-preview .lf-msg-body")
        page.locator(".lf-margin-preview").get_by_role(
            "button", name="Dismiss thread view"
        ).click()
        expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.unroute_all(behavior="wait")
