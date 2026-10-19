"""What a comment or reply send leaves behind: a held send yielding to later gestures
and drafts, a refusal returning the words, and the spoken acknowledgement."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import SEATED_ITEM_PAGE
from render_cases_layout import in_threads_scrollport
from render_cases_navigation import (
    JOURNEY_V1,
    NOTED_PAGE,
    compose,
    composer_quote,
    pending_text,
)
from render_harness import (
    LONG_PAGE,
    consume_browser_errors,
    draft_control,
    draft_key,
    hold_pending_thread_presentation,
    holding,
    http_error_console,
    open_page,
    page_comment,
    panel_settled,
    round_trip,
    select_words,
    stored_draft,
    stored_draft_text,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_draft_send_owns_the_editor_until_its_response(browser, serve):
    """A second gesture cannot overtake an earlier request or let that request clear
    newer unsent text. Hold the first POST in the browser: while it owns the draft,
    every edit door stays closed and the exact body remains recoverable, and the busy
    draft is readable content.

    A refused save is then an editable state, with Retry and Cancel at the same
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
    item = draft.locator(".lf-draft-footer")
    expect(item.get_by_role("status")).to_have_text("Save failed. The edit is kept.")
    expect(editor).to_have_js_property("value", "Keep these unsent words.")
    expect(item.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()

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
    page.locator(".lf-general .lf-compose-submit").click()
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
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. Draft kept — g i resumes writing"
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
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    # The box is back with the words, so the refusal names no address for them.
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append"
    )
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
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. Draft kept — g i resumes writing"
    )
    expect(page.locator(".lf-fab-input")).not_to_be_visible()

    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).not_to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    assert stored_draft_text(page, "general") == later
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    parent = "The parent the server will refuse."
    write(page_comment(page), parent)
    page.locator(".lf-general .lf-compose-submit").click()
    holding(page, held, 1, "the parent send")

    card = page.locator('.lf-thread[data-id^="pending:"]')
    expect(card).to_have_count(1)
    reply = "A reply written while the parent was in flight."
    write(card.locator("leaf-text").first, reply)
    if reply_sent:
        card.get_by_role("button", name="Send", exact=True).click()
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
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. "
        "Reply kept — it returns when its comment sends"
    )
    expect(card).to_have_count(0)
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

    # Resume writing leads to the comment, the one place that brings the reply back.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", parent)
    text = parent
    if edited:
        page.keyboard.press("ControlOrMeta+End")
        page.keyboard.type(" Edited.")
        text = parent + " Edited."

    page.locator(".lf-general .lf-compose-submit").click()
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
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread.locator("leaf-text").first).to_have_js_property("value", reply)
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    parent = "The anchored parent the server will refuse."
    compose(page, "#p3", parent)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the anchored parent")
    card = page.locator('.lf-threads .lf-thread[data-id^="pending:"]')
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
    expect(page.locator(".lf-notice")).to_contain_text(
        "Reply kept — it returns when its comment sends"
    )

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
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread.locator("leaf-text").first).to_have_js_property("value", reply)
    consume_browser_errors(page, http_error_console(400))


def test_a_refused_comment_takes_its_message_back_and_returns_the_words(
    held_events, serve
):
    """A refusal leaves nothing behind and the words back where they were written.

    The user has moved on to the pending thread in Threads by the time the refusal
    lands, so the card's box does not take their keys back: the words wait in it, and
    focus falls from the withdrawn thread to the list it stood in."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page_comment(page)
    words = "The comment the server will refuse."
    write(box, words)
    before = page.locator(".lf-threads > .lf-thread").count()
    page.locator(".lf-general .lf-compose-submit").click()
    holding(page, held, 1, "the general send")
    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending).to_have_count(1)
    # The card is a native disclosure, so its title is the stop the user stands on.
    title = pending.locator(":scope > .lf-thread-summary")
    title.focus()
    expect(title).to_be_focused()

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
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_count(0)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(before)
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(box).not_to_be_focused()
    expect(box).to_have_js_property("value", words)
    # The card the box stands in closed with the send, so the words are back out of
    # view, and the refusal names the address that opens it again.
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append. Draft kept — g i resumes writing"
    )
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
    page = open_page(browser, serve(SEATED_ITEM_PAGE))
    live = page.locator(".lf-live")
    seat = page.locator("#jobs > .lf-thread-seat > .lf-say")
    field = seat.locator("leaf-text")
    press = seat.get_by_role("button", name="Send", exact=True)
    write(field, "A remark whose arrival nothing else will say.")
    press.click()
    # Held: the gesture is the only thing that can have written the region, and the
    # words are said before the log has answered rather than because it did.
    holding(page, held, 1, "the send")
    expect(live).to_have_text("Message sent")

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
    url = serve(SEATED_ITEM_PAGE)
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.locator(".lf-thread-summary").click()
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
          return api.loadDraft(ctx);
        }""",
        f"reply:{root['id']}",
    )
    assert offered is None, "the second send's words were offered back while in flight"
    expect(reply).to_have_js_property("value", "")
    expect(page.locator("#jobs .lf-page-thread leaf-text")).to_have_js_property(
        "value", ""
    )

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

    The long sent message tests reflow above a draft in the same card; the distant
    card tests a user who has moved to another thread.
    """
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE, comments=8))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first_id = threads.nth(0).get_attribute("data-id")
    later_id = first_id if same_thread else threads.last.get_attribute("data-id")
    first = page.locator(f'.lf-thread[data-id="{first_id}"] leaf-text')
    later = page.locator(f'.lf-thread[data-id="{later_id}"] leaf-text')
    page.locator(f'.lf-thread[data-id="{first_id}"] .lf-thread-summary').click()
    write(first, "\n\n".join(["The first reply is in flight."] * 15))

    page.locator(f'.lf-thread[data-id="{first_id}"]').get_by_role(
        "button", name="Send", exact=True
    ).click()
    holding(page, held, 1, "the first reply send")

    if not same_thread:
        page.locator(f'.lf-thread[data-id="{later_id}"] .lf-thread-summary').click()
    later.click()
    newer = "The later reply keeps the user here.\n" * (14 if same_thread else 1)
    write(later, newer)
    expect(later).to_be_focused()
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] leaf-text')

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(
        page.locator(f'.lf-thread[data-id="{first_id}"] .lf-msg').last
    ).to_contain_text("The first reply is in flight.")
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", newer)
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] leaf-text')


@pytest.mark.parametrize("continue_inline", [False, True])
def test_a_held_reply_send_leaves_the_panel_closed(held_events, serve, continue_inline):
    """Closing Threads during delivery is later than sending the reply."""
    browser, held = held_events
    url = serve(SEATED_ITEM_PAGE)
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
    page.emulate_media(reduced_motion="reduce")
    toggle = page.locator(".lf-threads-toggle")
    toggle.click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    write(reply, "Send this while I return to reading.")
    thread.get_by_role("button", name="Send", exact=True).click()
    holding(page, held, 1, "the reply send")

    toggle.click()
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(toggle).to_be_focused()
    inline = page.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    newer = "Continue this reply beside the question."
    if continue_inline:
        write(inline, newer)
        inline.evaluate("box => box.setSelectionRange(9, 9)")
        expect(reply).to_have_js_property("value", newer)
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_js_property("value", newer if continue_inline else "")
    expect(thread.locator(".lf-msg").last).to_contain_text(
        "Send this while I return to reading."
    )
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    if continue_inline:
        expect(inline).to_be_focused()
        expect(inline).to_have_js_property("value", newer)
        assert inline.evaluate("box => box.selectionStart") == 9
    else:
        expect(toggle).to_be_focused()


def test_a_held_reply_send_preserves_a_later_scroll(held_events, serve):
    """A wheel can move the reading place while the user stands on the thread the
    reply was sent in; its delivery moves neither."""
    browser, held = held_events
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first = threads.first
    later = threads.last
    first.locator(".lf-thread-summary").click()
    reply = first.locator("leaf-text")
    write(reply, "A reply whose delivery is slow.")
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply send")

    bounds = page.locator(".lf-threads").bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    expect(later).not_to_be_in_viewport()
    page.mouse.wheel(0, 3500)
    expect(later).to_be_in_viewport()
    expect(first.locator(".lf-thread-summary")).to_be_focused()
    before = later.evaluate("node => node.getBoundingClientRect().top")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_js_property("value", "")
    expect(first.locator(".lf-msg").last).to_contain_text(
        "A reply whose delivery is slow."
    )
    expect(later).to_be_in_viewport()
    assert later.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )
    expect(first.locator(".lf-thread-summary")).to_be_focused()


def test_a_held_comment_send_leaves_a_later_reply_box_focused(browser, serve):
    """Opening a reply while a new comment is in flight is a later gesture. The
    comment still appears, but its arrival must not move focus into its new thread."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    select_words(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "The earlier comment in flight.")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Another thread than the one in flight: that one's card is in this list too now,
    # standing for the comment while the log answers for it.
    later_id = page.locator(
        '.lf-threads > .lf-thread:not([data-id^="pending:"])'
    ).first.get_attribute("data-id")
    later = page.locator(f'.lf-thread[data-id="{later_id}"] leaf-text')
    page.locator(f'.lf-thread[data-id="{later_id}"] .lf-thread-summary').click()
    write(later, "The later reply keeps the user here.")
    later.evaluate("ta => ta.setSelectionRange(9, 9)")
    expect(later).to_be_focused()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(3)
    expect(later).to_be_focused()
    expect(later).to_have_js_property("value", "The later reply keeps the user here.")
    assert later.evaluate("ta => ta.selectionStart") == 9


def test_newer_filter_wins_over_send_waiting_for_presentation(browser, serve):
    """A delayed Send cannot widen a newer filter or navigate its reader away."""
    page = open_page(browser, serve(NOTED_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("Comment 0")
    select_words(page, "#p1")
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"), "Earlier Send waiting for presentation."
    )
    hold_pending_thread_presentation(page)
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function("() => window.commentPresentationHeld === true")
    search.fill("Keep this newer search")
    expect(search).to_be_focused()
    page.evaluate("releaseCommentPresentation()")
    round_trip(page)
    page.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    expect(search).to_have_value("Keep this newer search")
    expect(search).to_be_focused()

    assert any(
        event.get("text") == "Earlier Send waiting for presentation."
        for event in events_model.read_events(serve.page_dir)
    )


@pytest.mark.parametrize("later_selection", [False, True])
def test_a_comment_hidden_by_narrowing_is_revealed_in_the_open_panel(
    browser, serve, later_selection
):
    """A new comment widens the panel's filter without taking a later selection."""
    page = open_page(browser, serve(NOTED_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.get_by_role("searchbox", name="Find in threads").fill("Comment 0")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)

    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "This comment starts outside the filter.",
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the filtered comment send")
    if later_selection:
        select_words(page, "#p2")
        expect(page.locator(".lf-fab-input")).to_be_visible()
        assert pending_text(page) == "A short second passage."

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    sent = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("text") == "This comment starts outside the filter."
    )
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread).to_contain_text(sent["text"])
    if later_selection:
        assert pending_text(page) == "A short second passage."
        expect(page.locator(".lf-fab-input")).to_be_visible()
        expect(page.locator(".lf-fab-input")).not_to_be_focused()
        assert composer_quote(page)["text"].strip("“”") == "A short second passage."
    else:
        expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()


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
    expect(page.locator(".lf-thread")).to_have_count(1)

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

    expect(page.locator(".lf-thread")).to_have_count(1)
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
    url = serve(SEATED_ITEM_PAGE)
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
    first.locator(".lf-threads-toggle").click()
    panel_settled(first)
    inline = first.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    panel = first.locator(f'.lf-thread[data-id="{root["id"]}"]')
    second_inline = second.locator(
        f'#jobs .lf-page-thread[data-thread="{root["id"]}"] leaf-text'
    )
    sent_raw = "  Send this part first.  "
    newer_raw = "  A later thought stays raw.  "
    write(inline, sent_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", sent_raw)
    expect(second_inline).to_have_js_property("value", sent_raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    panel.locator(".lf-thread-summary").click()
    panel.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the older reply")
    write(second_inline, newer_raw)
    expect(inline).to_have_js_property("value", newer_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", newer_raw)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    expect(inline).to_have_js_property("value", newer_raw)
    expect(panel.locator("leaf-text")).to_have_js_property("value", newer_raw)
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
