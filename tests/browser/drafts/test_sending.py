"""What a comment or reply send leaves behind: a held send yielding to later gestures
and drafts, a refusal returning the words, and the spoken acknowledgement."""

import re

import pytest
from interact_support import append_carried_log_record
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import SEATED_OBLIGATION_PAGE, panel_comment
from render_cases_navigation import (
    JOURNEY_V1,
    NOTED_PAGE,
    compose,
    composer_quote,
    pending_text,
)
from render_harness import (
    LONG_PAGE,
    PANEL_THREAD,
    consume_browser_errors,
    draft_control,
    draft_key,
    expect_error_waits_in_menu,
    expect_panel_says,
    holding,
    http_error_console,
    open_page,
    page_comment,
    panel_field,
    panel_says,
    panel_settled,
    panel_view,
    round_trip,
    select_words,
    stored_draft,
    stored_draft_text,
    write,
)

from browser.threads import PANEL_REPLY, open_panel_thread, seed_panel_threads
from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed

# The panel's field's Send.
FIELD_SEND = ".lf-fp-field .lf-compose-submit"


def thread_listed(page, attempt):
    """Whether the page's own reading of its threads holds the thread the send
    `attempt` opened, pending or admitted."""
    return page.evaluate(
        """async (attempt) => {
          const {readThreads} = await window.__lfWidgetApi();
          return readThreads().threads.some((thread) =>
            [attempt, `pending:${attempt}`].includes(thread.key));
        }""",
        attempt,
    )


def test_a_draft_send_owns_the_editor_until_its_response(browser, serve):
    """A second gesture cannot overtake an earlier request or let that request clear
    newer unsent text. Hold the first POST in the browser: while it owns the draft,
    every edit door stays closed and the exact body remains recoverable, and the busy
    draft is readable content.

    A refused save is then an editable state, with Retry and Discard at the same
    target."""
    page = open_page(browser, serve(JOURNEY_V1))
    page.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          let held = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (held && event?.kind === 'action' && event.action === 'edit') {
              return new Promise((resolve, reject) => {
                window.releaseDraftSend = () => {
                  held = false;
                  actualFetch(input, init).then(resolve, reject);
                };
              });
            }
            return actualFetch(input, init);
          };
        }"""
    )
    draft = page.locator("#draft-ops")
    sent = "The first save still owns this body."
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), sent)
    draft_control(page, "save", "draft-ops").click()
    expect(draft).to_have_attribute("aria-busy", "true")
    assert stored_draft_text(page, "edit:draft-ops") == sent
    expect(draft.locator(".lf-draft-body")).to_have_text(sent)
    expect(draft).to_have_css("opacity", "1")
    expect(draft).to_have_css("cursor", "progress")
    assert draft.evaluate("node => node.getAnimations().length") == 0

    expect(draft_control(page, "edit", "draft-ops")).to_be_disabled()
    # The projection owns a native disabled button, so a forced DOM click is refused
    # before the contributor's activation capability can run.
    draft_control(page, "edit", "draft-ops").evaluate("button => button.click()")
    expect(draft.locator("leaf-text")).to_have_count(0)

    page.evaluate("window.releaseDraftSend()")
    page.wait_for_function(
        """key => !document.getElementById('draft-ops').hasAttribute('aria-busy')
          && JSON.parse(localStorage.getItem(key))?.settled === true""",
        arg=draft_key(page, "edit:draft-ops"),
    )
    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in events] == [sent]
    expect(draft.locator(".lf-draft-body")).to_have_text(sent)

    draft_control(page, "edit", "draft-ops").click()
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    write(editor, "Keep these unsent words.")
    page.route(
        "**/api/event",
        lambda route: route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        ),
    )
    draft_control(page, "save", "draft-ops").click()
    item = draft.locator(".lf-draft-tools")
    expect(item.get_by_role("status")).to_have_text("Save failed. The edit is kept.")
    expect(editor).to_have_js_property("value", "Keep these unsent words.")
    expect(item.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Discard", exact=True)).to_be_visible()

    write(editor, "Keep the revised unsent words.")
    expect(item.locator(".lf-draft-status")).to_be_empty()
    item.get_by_role("button", name="Save", exact=True).click()
    expect(item.get_by_role("status")).to_have_text("Save failed. The edit is kept.")
    page.unroute("**/api/event")
    item.get_by_role("button", name="Retry", exact=True).click()
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text(
        "Keep the revised unsent words."
    )
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"] for event in edits] == [
        {"value": sent},
        {"value": "Keep the revised unsent words."},
    ]
    consume_browser_errors(page, http_error_console(400))


def test_a_held_general_send_preserves_a_newer_exact_draft(browser, serve):
    """An earlier response settles only the general generation it posted."""
    page = open_page(browser, serve(LONG_PAGE))
    box = page_comment(page)
    old = "The general comment already in flight."
    newer = "  The newer general thought keeps its spaces.  "
    write(box, old)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(FIELD_SEND).click()
    holding(page, held, 1, "the older general send")
    # The send put the card away; the newer thought is written in it opened again.
    write(page_comment(page), newer)

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(box).to_have_js_property("value", newer)
    assert stored_draft_text(page, "general") == newer
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]


def test_a_refused_selection_comment_leaves_the_words_on_their_passage(
    held_events, serve
):
    """The composer goes down with the send, so a refusal has to put the words back in
    the store rather than in whatever box was on screen — the one they were typed in has
    gone with the thread they went to."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator('leaf-text[name="reply"]:focus')).to_be_visible()
    page.keyboard.press("ArrowRight")  # caret movement is not a later composition
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    # The words went back to a box out of view, so the refusal says where they are.
    expect_panel_says(
        page,
        "Couldn't take this — refused before append. Draft kept — g i resumes writing",
    )

    # Their passage still holds their draft, so opening it again finds the words.
    page.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-composer leaf-text")).to_be_focused()
    expect(page.locator(".lf-composer leaf-text")).to_have_js_property("value", words)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    consume_browser_errors(page, http_error_console(400))


def test_a_refused_selection_comment_reopens_its_words_while_the_send_owns_intent(
    held_events, serve
):
    """A refusal that lands while the user is still where the send left them puts the
    words back in front of them, in the box on their passage, as the page comment card
    does. Left in the store alone, they read as lost: the thread the send drew goes
    away, and nothing on screen says the sentence still exists."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the selection comment")
    expect(page.locator(".lf-fab-input")).not_to_be_visible()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    box = page.locator(".lf-fab-input")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", words)
    # The box is back with the words, so the refusal names no address for them. It is
    # about the passage's box, so it stands there over the words, which send nothing
    # until the user's first key or press there, and the leaf's dot waits for it.
    cover = page.locator(".lf-fab-bar .lf-compose-error")
    expect(cover).to_have_text("Couldn't take this — refused before append")
    expect(page.locator(".lf-fp-error-dot")).to_be_hidden()
    # The first Enter only lifts the cover, with the caret at the words' end, so the
    # words are never sent unseen; the error waits in the leaf's menu.
    page.keyboard.press("Enter")
    expect(cover).to_be_hidden()
    expect(box).to_be_focused()
    assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [
        len(words),
        len(words),
    ]
    assert held == [], "the covered words were sent"
    # The next Enter sends them.
    page.keyboard.press("Enter")
    holding(page, held, 1, "the comment sent again")
    assert held[0].request.post_data_json["text"] == words
    held.pop(0).continue_()
    expect_error_waits_in_menu(page, "Couldn't take this — refused before append")
    consume_browser_errors(page, http_error_console(400))


# A paragraph running into a suggestion: words selected across it cross the widget's
# fence, so the page's text can't name them again and their anchor is detached.
FENCED_PAGE = leaf_page(
    "fenced",
    '<h1 id="t">Fenced</h1><p id="p">The wall is painted <lf-suggestion id="swap">'
    "<lf-old>red</lf-old><lf-new>blue</lf-new></lf-suggestion> before the opening.</p>",
)


def test_a_refused_detached_comment_reopens_beside_its_words(held_events, serve):
    """Only the browser's selection knew where a detached comment's words stand, and
    nothing beside them draws its thread, so the send opens that thread in the panel.
    A refusal brings the box back beside the words, where the user wrote, and the
    thread's view goes with the thread. The box once came back in the window's corner,
    under a view saying the thread was not on the page."""
    browser, held = held_events
    page = open_page(browser, serve(FENCED_PAGE))
    words = "Why this colour?"
    compose(page, "#p", words)
    box = page.locator(".lf-fab-input")
    before = box.bounding_box()
    page.keyboard.press("Enter")
    holding(page, held, 1, "the detached comment")
    expect(page.locator(panel_view("thread"))).to_have_count(1)

    refuse(page, held)
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", words)
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    after = box.bounding_box()
    assert abs(after["x"] - before["x"]) < 1 and abs(after["y"] - before["y"]) < 1, (
        f"the box came back at {after}, not beside its words at {before}"
    )
    consume_browser_errors(page, http_error_console(400))


# The share of a cover's words past its last whole line: zero when it clips whole.
COVER_LINE_REMAINDER = """cover => {
  const words = cover.firstElementChild;
  const line = parseFloat(getComputedStyle(words).lineHeight);
  const lines = words.getBoundingClientRect().height / line;
  return lines - Math.round(lines);
}"""


def refuse(page, held):
    """Answer the held send with a final refusal."""
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )


def test_a_refusals_error_leaves_with_the_words_it_stood_over(held_events, serve):
    """The error stands over the refused words, not over the box: one comment box
    serves every passage, so once Escape puts the words away the error waits in the
    leaf's menu, and the box opened on another passage is free of it. The words over
    them stop at the box's last whole line."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the selection comment")
    refuse(page, held)
    box = page.locator(".lf-fab-input")
    cover = page.locator(".lf-fab-bar .lf-compose-error")
    dot = page.locator(".lf-fp-error-dot")
    expect(cover).to_have_text("Couldn't take this — refused before append")
    expect(dot).to_be_hidden()
    assert cover.evaluate(COVER_LINE_REMAINDER) == pytest.approx(0, abs=0.01)

    page.keyboard.press("Escape")
    expect(box).to_be_hidden()
    expect(dot).to_be_visible()
    compose(page, "#p9")
    expect(box).to_have_js_property("value", "")
    expect(cover).to_be_hidden()
    expect_error_waits_in_menu(page, "Couldn't take this — refused before append")
    consume_browser_errors(page, http_error_console(400))


def test_resume_writing_comes_back_to_refused_words_at_their_end(held_events, serve):
    """Words a refusal hands back to a box still on screen are where Resume writing
    goes, and it lands at their end, where Enter sends them, wherever the caret stood
    when they were sent."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    box = page_comment(page)
    words = "The comment sent with the caret at its start."
    write(box, words)
    page.keyboard.press("ArrowUp")
    assert box.evaluate("box => box.selectionStart") == 0
    page.keyboard.press("Enter")
    holding(page, held, 1, "the general send")
    refuse(page, held)
    expect(box).to_have_js_property("value", words)
    page.keyboard.press("Escape")
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [
        len(words),
        len(words),
    ]
    consume_browser_errors(page, http_error_console(400))


def test_a_refused_selection_comment_written_past_is_where_resume_writing_goes(
    held_events, serve
):
    """The user has gone on to write somewhere else when the refusal lands. Their
    refused words go back to the passage's box, which is out of view, so the notice says
    they are kept and Resume writing takes the user to them, rather than to the box they
    can already see."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the selection comment")
    later = "A page comment written while the first was in flight."
    write(page_comment(page), later)

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    # The field holds the later words, so it cannot say an error about nothing in
    # particular: the refusal waits in the leaf's menu, its dot on the leaf.
    expect(page.locator(".lf-fp-error-dot")).to_be_visible()
    expect(page.locator(".lf-fab-input")).not_to_be_visible()

    page.keyboard.press("Escape")
    expect(panel_field(page)).not_to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    assert stored_draft_text(page, "general") == later
    expect_error_waits_in_menu(
        page,
        "Couldn't take this — refused before append. Draft kept — g i resumes writing",
    )
    consume_browser_errors(page, http_error_console(400))


@pytest.mark.parametrize("reply_sent", [True, False], ids=["sent", "unsent"])
@pytest.mark.parametrize("edited", [False, True], ids=["as-sent", "edited"])
def test_a_reply_under_a_refused_parent_comes_back_with_it(
    held_events, serve, reply_sent, edited
):
    """A refusal takes down the thread a comment opened, and the box under it: a reply
    written there, sent behind the comment or not, keys by the comment's attempt, which
    the refusal withdraws and an edit of the comment replaces. The words go to the
    comment's own draft instead, so the notice says where they wait, Resume writing
    leads to that draft, and the thread its next send opens, edited or not, has the
    reply back in its box. A reply sent behind the comment never reaches the wire under
    the pending name only this page used."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    parent = "The parent the server will refuse."
    write(page_comment(page), parent)
    page.locator(FIELD_SEND).click()
    holding(page, held, 1, "the parent send")

    attempt = held[0].request.post_data_json["attempt"]
    card = page.locator(f'{PANEL_THREAD}[data-thread="pending:{attempt}"]')
    expect(card).to_be_visible()
    reply = "A reply written while the parent was in flight."
    write(page.locator(PANEL_REPLY), reply)
    if reply_sent:
        page.locator(FIELD_SEND).click()
    # The user goes back to the page comment box, so the parent's words return in view.
    box = page_comment(page)

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(box).to_have_js_property("value", parent)
    expect_panel_says(
        page,
        "Couldn't take this — refused before append. "
        "Reply kept — it comes back once its comment is saved",
    )
    expect(card).to_have_count(0)
    assert not thread_listed(page, attempt), "the refused thread is still listed"
    assert not [
        route for route in held if "pending:" in (route.request.post_data or "")
    ], "a gesture reached the wire naming a thread the log never took"
    # The thread went with its parent, so the reply's words wait in the parent's draft.
    assert stored_draft_text(page, f"reply:{attempt}") is None
    assert (
        page.evaluate(
            "([read, ctx]) => read(ctx)?.held ?? null",
            [stored_draft(page), "general"],
        )
        == reply
    )

    # The refusal covers the words it gave back until the user comes back to them.
    cover = page.locator(".lf-fp-field .lf-compose-error")
    expect(cover).to_contain_text("Couldn't take this — refused before append")
    # Resume writing leads to the comment, the one place that brings the reply back,
    # and is the user coming back to its words: the error goes to the leaf's menu and
    # the caret stands at the words' end, where Enter sends them.
    page.keyboard.press("Escape")
    expect(box).not_to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", parent)
    expect(cover).to_be_hidden()
    expect(page.locator(".lf-fp-error-dot")).to_be_visible()
    assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [
        len(parent),
        len(parent),
    ]
    text = parent
    if edited:
        page.keyboard.type(" Edited.")
        text = parent + " Edited."

    page.keyboard.press("Enter")
    holding(page, held, 1, "the parent sent again")
    assert (held[0].request.post_data_json["attempt"] == attempt) is not edited
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    sent = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == text
    )
    # The comment's send opens its thread in the panel, its reply back in the field.
    expect(page.locator(f'{PANEL_THREAD}[data-thread="{sent["id"]}"]')).to_be_visible()
    expect(page.locator(PANEL_REPLY)).to_have_js_property("value", reply)
    # An unsent reply's box goes down with the thread; the notice says where its words
    # went, which is what the guard's report is about.
    consume_browser_errors(
        page,
        http_error_console(400),
        *([] if reply_sent else [{"code": "words-left-screen", "words": reply}]),
    )


def test_a_refused_comments_reply_travels_with_it_to_another_passage(
    held_events, serve
):
    """The reply a refusal hands back is part of the comment's draft, so whatever moves
    the draft moves the reply: carried with Alt-click to another passage and sent from
    there, the comment's new thread has the reply back in its box."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    parent = "The anchored parent the server will refuse."
    compose(page, "#p3", parent)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the anchored parent")
    card = page.locator(".lf-margin-preview .lf-page-thread")
    expect(card).to_have_count(1)
    reply = "A reply under the anchored parent."
    write(card.locator("leaf-text").first, reply)
    card.get_by_role("button", name="Send", exact=True).click()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect_panel_says(page, "Reply kept — it comes back once its comment is saved")

    page.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("i")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", parent)
    page.locator("#p5").scroll_into_view_if_needed()
    page.locator("#p5").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", parent)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the parent sent from its new passage")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    sent = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == parent
    )
    assert sent["anchor"]["section"] == "p5"
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    expect(thread.locator("leaf-text").first).to_have_js_property("value", reply)
    consume_browser_errors(page, http_error_console(400))


def test_a_refused_comment_takes_its_message_back_and_returns_the_words(
    held_events, serve
):
    """A refusal leaves nothing behind and the words back where they were written.

    The user has moved on from the field to the pending thread's view by the time the
    refusal lands. The view goes with the thread, so the caret goes back to the words,
    in the field that stands for the page again."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    box = page_comment(page)
    words = "The comment the server will refuse."
    write(box, words)
    page.locator(FIELD_SEND).click()
    holding(page, held, 1, "the general send")
    attempt = held[0].request.post_data_json["attempt"]
    pending = page.locator(f'{PANEL_THREAD}[data-thread="pending:{attempt}"]')
    expect(pending).to_be_visible()
    # The thread's view is the stop the user is located on.
    pending.focus()
    expect(pending).to_be_focused()

    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(pending).to_have_count(0)
    assert not thread_listed(page, attempt), "the refused thread is still listed"
    # The view the user was located on went with the thread, so the field stands for the page
    # again with the words in it and the caret in them, and the refusal needs no
    # address for them.
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", words)
    expect_panel_says(page, "Couldn't take this — refused before append")
    assert "Draft kept" not in panel_says(page)
    assert stored_draft_text(page, "general") == words
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    consume_browser_errors(page, http_error_console(400))


def test_every_message_send_says_so_to_a_user_listening(held_events, serve):
    """A send whose result the user cannot see still reaches them.

    The message shown in the thread is the whole acknowledgement for a user
    looking at it, which is why no box writes a success notice for it. But neither the
    seat nor the Threads list is a live region, so for a user listening to the page
    that send would pass in silence. `post` says it once, where a gesture is first known
    to be a message, which is what covers every box that sends one.
    """
    browser, held = held_events
    page = open_page(browser, serve(SEATED_OBLIGATION_PAGE))
    live = page.locator(".lf-live")
    seat = page.locator("#jobs > .lf-thread-seat > .lf-say")
    field = seat.locator("leaf-text")
    press = seat.get_by_role("button", name="Send", exact=True)
    write(field, "A remark whose arrival nothing else will say.")
    press.click()
    # Held: the gesture is the only thing that can have written the region, and the
    # words are said before the log has answered rather than because it did.
    holding(page, held, 1, "the send")
    expect(live).to_have_text("Message added")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)


def test_a_first_answer_leaves_a_later_sends_words_masked(held_events, serve):
    """One box, two sends: answering the first must not hand back the second's words.

    A send empties the box it was written in and masks that generation, so this
    document stops showing words it is now showing in the thread. The answer lifts that
    mask — and lifting whichever mask happens to be current, rather than the one this
    send put there, lifts a later send's: words the user is already watching as a
    pending reply go back on offer while that reply is still in flight. The outbox
    delivers in order, so the first answer always lands while the second send is
    unanswered. That makes the window ordinary rather than rare.
    """
    browser, held = held_events
    url = serve(SEATED_OBLIGATION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-page-thread[data-thread="{root["id"]}"]')
    reply = thread.locator("leaf-text")
    send = thread.get_by_role("button", name="Send", exact=True)

    first = "The reply already on its way."
    write(reply, first)
    send.click()
    holding(page, held, 1, "the first reply send")
    expect(reply).to_have_js_property("value", "")

    second = "The reply the user is watching."
    write(reply, second)
    send.click()
    expect(reply).to_have_js_property("value", "")
    # Both stand, in the order they were written. A card gains messages by insertion,
    # and a receipt acknowledging an earlier one sits between them.
    expect(thread.locator(".lf-msg").last).to_contain_text(second)
    expect(thread.locator(".lf-msg").nth(-2)).to_contain_text(first)

    held.pop(0).continue_()
    holding(page, held, 1, "the second reply send, once the first is answered")

    # What a widget asks of a draft box, through the public helper surface. The boxes
    # alone would not say this: nothing repaints one when a mask is lifted, so the
    # offer stands unseen until some view of this thread is next built and reads it.
    offered = page.evaluate(
        """async (ctx) => {
          const api = await window.__lfWidgetApi();
          return api.loadDraft(ctx)?.text ?? null;
        }""",
        f"reply:{root['id']}",
    )
    assert offered is None, "the second send's words were offered back while in flight"
    expect(reply).to_have_js_property("value", "")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    spoken = thread.locator(".lf-msg").all_inner_texts()
    assert [
        words for words in (first, second) if not any(words in s for s in spoken)
    ] == []


@pytest.mark.parametrize("same_thread", [False, True])
def test_a_held_reply_send_leaves_a_later_reply_box_focused(
    held_events, serve, same_thread
):
    """A later draft keeps its focus and remains visible when a reply arrives.

    The long sent message tests reflow above a draft in the same thread; the other
    thread tests a user who has moved on to another one in the panel.
    """
    browser, held = held_events
    url = serve(LONG_PAGE, comments=8)
    ids = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    first_id = ids[0]
    later_id = first_id if same_thread else ids[-1]
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    open_panel_thread(page, first_id)
    reply = page.locator(PANEL_REPLY)
    sent = "\n\n".join(["The first reply is in flight."] * 15)
    write(reply, sent)
    page.locator(FIELD_SEND).click()
    holding(page, held, 1, "the first reply send")

    if not same_thread:
        open_panel_thread(page, later_id)
    later = page.locator(PANEL_REPLY)
    later.click()
    newer = "The later reply keeps the user here.\n" * (14 if same_thread else 1)
    write(later, newer)
    expect(later).to_be_focused()
    expect(later).to_be_in_viewport()

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert events_model.read_events(serve.page_dir)[-1]["text"] == sent
    if same_thread:
        expect(page.locator(f"{PANEL_THREAD} .lf-msg").last).to_contain_text(
            "The first reply is in flight."
        )
    expect(page.locator(f'{PANEL_THREAD}[data-thread="{later_id}"]')).to_be_visible()
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", newer)
    expect(later).to_be_in_viewport()


def test_a_held_reply_send_leaves_the_panel_closed(held_events, serve):
    """Putting the thread away during delivery is later than sending the reply."""
    browser, held = held_events
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    open_panel_thread(page, root)
    reply = page.locator(PANEL_REPLY)
    write(reply, "Send this while I return to reading.")
    page.locator(FIELD_SEND).click()
    holding(page, held, 1, "the reply send")

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    current_location = page.evaluate("() => document.activeElement.className")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert events_model.read_events(serve.page_dir)[-1]["text"] == (
        "Send this while I return to reading."
    )
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement.className") == current_location


def test_a_held_reply_send_preserves_a_later_scroll(browser, serve):
    """A wheel can move the reading place while the user is located in the thread the
    reply was sent in; its delivery moves neither."""
    url = serve(LONG_PAGE)
    (root,) = seed_panel_threads(serve.page_dir, 1, long_index=0, messages=20)
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    view = open_panel_thread(page, root)
    # Opening the thread reads the agent's turns; that lands before the reply is held.
    round_trip(page)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    reply = page.locator(PANEL_REPLY)
    write(reply, "A reply whose delivery is slow.")
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply send")
    assert held[0].request.post_data_json["kind"] == "reply"
    expect(view.locator(".lf-msg").last).to_contain_text(
        "A reply whose delivery is slow."
    )

    bounds = view.bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    page.mouse.wheel(0, -3500)
    page.wait_for_function("view => view.scrollTop < 1", arg=view.element_handle())
    expect(reply).to_be_focused()
    opening = view.locator(".lf-msg").first
    before = opening.evaluate("node => node.getBoundingClientRect().top")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_js_property("value", "")
    expect(view.locator(".lf-msg").last).to_contain_text(
        "A reply whose delivery is slow."
    )
    assert opening.evaluate(
        "node => node.getBoundingClientRect().top"
    ) == pytest.approx(before, abs=1)
    expect(reply).to_be_focused()


def test_a_held_comment_send_leaves_a_later_reply_box_focused(browser, serve):
    """Opening a reply while a new comment is in flight is a later gesture. The
    comment still appears, but its arrival must not move focus into its new thread."""
    url = serve(LONG_PAGE, comments=2)
    later_id = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    select_words(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "The earlier comment in flight.")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    # Another thread than the one in flight.
    open_panel_thread(page, later_id)
    later = page.locator(PANEL_REPLY)
    later.click()
    write(later, "The later reply keeps the user here.")
    later.evaluate("ta => ta.setSelectionRange(9, 9)")
    expect(later).to_be_focused()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ][-1] == "The earlier comment in flight."
    expect(page.locator(f'{PANEL_THREAD}[data-thread="{later_id}"]')).to_be_visible()
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", "The later reply keeps the user here.")
    assert later.evaluate("ta => ta.selectionStart") == 9


def test_a_held_comment_send_leaves_the_passage_picked_out_behind_it(
    held_events, serve
):
    """A comment's send must not take a newer passage selection with its focus handoff.

    The newer selection remains native and keeps its response field available while the
    earlier send becomes a thread behind it.

    Held rather than raced: the window is one request's flight, and a machine quick
    enough closes it before the next gesture. A loaded CI runner is not, and it said so
    as a 💬 that never came up for the passage picked out after a send.

    The next passage is the one above the first, because the sent comment's card stands
    under its passage, over whatever follows it. The card is placed and revealed some
    frames after the send, so a passage below was reachable only on a machine quick
    enough to press it before the card arrived."""
    browser, held = held_events
    page = open_page(browser, serve(NOTED_PAGE))
    select_words(page, "#p2")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")
    # Every machine reaches the next gesture with the card open, as a user would.
    expect(page.locator(".lf-margin-preview[data-lf-thread-placement]")).to_be_visible()

    # The user picks out their next passage while the first send is still in the wire.
    passage = " ".join(page.locator("#p1").inner_text().split())
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", "")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    # The earlier comment is the page's one thread.
    assert [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == ["The first remark."]

    # The send landed behind them and left the passage picked out. Read as the user's
    # own next gesture rather than as the button's rendering: the button is a state that
    # only a fresh decision repaints, so it stands wherever the last one left it — while
    # the key that comments on a selection reads the live one, and answers the general
    # box where there is none.
    assert pending_text(page) == passage, (
        "the send's landing lost the passage the user had picked out"
    )
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == passage


def test_a_held_comment_send_leaves_a_later_keyboard_comment_open(held_events, serve):
    """The Comment opened with `s` is later than a comment already in flight."""
    browser, held = held_events
    page = open_page(browser, serve(NOTED_PAGE))
    compose(page, "#p1", "The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    # Leave the sending field, then use the keyboard Comment path on p2.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    target_code = page.evaluate(
        """() => {
          const top = document.querySelector('#p2').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-picker-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
        }"""
    )
    page.keyboard.type(target_code)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)

    # The earlier comment is the page's one thread.
    assert [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == ["The first remark."]
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )
    assert composer_quote(page)["text"].endswith("A short second passage.")


def test_a_held_thread_send_cannot_clear_a_newer_raw_draft(browser, serve, one_user):
    """Settlement compares raw words, so an older POST cannot erase a later edit."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "What should the order be?",
        },
    )
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    thread = first.locator(f'#jobs .lf-page-thread[data-thread="{root["id"]}"]')
    inline = thread.locator("leaf-text")
    second_inline = second.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    sent_raw = "  Send this part first.  "
    newer_raw = "  A later thought stays raw.  "
    write(inline, sent_raw)
    expect(second_inline).to_have_js_property("value", sent_raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    thread.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the older reply")
    write(second_inline, newer_raw)
    expect(inline).to_have_js_property("value", newer_raw)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    expect(inline).to_have_js_property("value", newer_raw)
    expect(second_inline).to_have_js_property("value", newer_raw)
    # This root was appended by the agent, so it carries no attempt and its reply draft
    # keys by the id, which for such a thread never changes either.
    assert stored_draft_text(first, f"reply:{root['id']}") == newer_raw
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [sent_raw]


def test_a_held_selection_comment_preserves_a_newer_exact_draft(held_events, serve):
    """A selection send owns one composer generation, not the passage.

    The send takes its own words with it — they stand in the thread it drew before the
    log has answered — and the composer opened again on that passage holds a generation
    of its own, which the older answer must not settle."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    old = "The selected passage needs this first comment."
    newer = "  A newer selection comment remains in the composer.  "
    compose(page, "#p3", old)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")
    expect(page.locator("[data-attempt]").first).to_contain_text(old)

    compose(page, "#p3", newer)
    box = page.locator(".lf-composer leaf-text")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(box).to_have_js_property("value", newer)
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [old]
    assert comments[0]["attempt"]
