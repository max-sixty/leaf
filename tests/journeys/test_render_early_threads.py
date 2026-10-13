"""Local comments remain usable while the first private-state read is pending."""

import re

import pytest
from browser.test_render_drawing import draw_over
from interact_support import append_command, wait_for
from leaf import event_log as events_model
from leaf.render_checks import wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import _publish
from render_harness import (
    consume_browser_errors,
    holding,
    leaf_page,
    page_comment,
    round_trip,
    select_words,
    stored_draft_text,
    watched,
    write,
)

EARLY_PAGE = leaf_page(
    "Early comments",
    '<h1>Early comments</h1><p id="passage">The words the reader first sees.</p>',
)
SAVED_COMMENT = {
    "id": "saved-comment",
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "A conversation from the previous visit.",
}
HISTORY_UNAVAILABLE = re.compile(
    r"^(?:Loading current threads…|"
    r"Current threads are unavailable while the server is offline\.)$"
)


def _clock_until_ready(page, through="rendering"):
    """Advance a paused product clock only until the runtime states completion."""

    def advance():
        page.clock.run_for(20)
        return page.evaluate(
            """through => {
              const ready = document.querySelector('script[data-lf-entry]')?.lfReadiness;
              return ready ? ready(null, through) : 'started';
            }""",
            through,
        )

    wait_for(
        advance,
        lambda stage: stage is None,
        failure=f"the controlled-clock page never reached {through}",
    )


def _history_outstanding(page):
    """Local interaction finishes while history is still loading, before its deadline."""
    assert (
        page.evaluate("""async () => {
      const {readApplication} = await window.__lfCheckApi();
      return readApplication().phase;
    }""")
        == "waiting"
    )
    assert (
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').lfReadiness(null, 'log')"
        )
        == "log"
    )


def _cold_page(browser, url, *, touch=False, clock=False):
    """Hold this page's private history; embedded sample pages load independently."""
    page = browser.new_page(
        viewport={"width": 390 if touch else 1200, "height": 900}, has_touch=touch
    )
    if clock:
        page.clock.install(time=0)
        page.clock.pause_at(1)
    watched(page)
    held = []
    gate = {"open": False}
    page.route(
        "**/api/state*",
        lambda route: (
            held.append(route)
            if route.request.frame == page.main_frame and not gate["open"]
            else route.continue_()
        ),
    )
    page.goto(url, wait_until="load")
    holding(page, held, 1, "the first private-state read")
    if clock:
        _clock_until_ready(page, "upgraded")
    else:
        wait_until_ready(page, through="upgraded")
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-status-text")).to_have_text("Loading saved state…")

    def release():
        gate["open"] = True
        while held:
            held.pop(0).continue_()

    return page, release


@pytest.mark.parametrize("saved_before", [False, True])
def test_an_early_anchored_send_merges_history_and_keeps_its_seen_revision(
    browser, serve, saved_before
):
    """A pending comment is visible before history and keeps the passage it quoted."""
    page, release_state = _cold_page(
        browser,
        live_url(
            serve(
                EARLY_PAGE.replace("<h1>", '<h1 id="title">'),
                events=[
                    {
                        **SAVED_COMMENT,
                        **({"anchor": {"section": "title"}} if saved_before else {}),
                    }
                ],
            )
        ),
    )
    held_posts = []
    page.route(
        "**/api/event",
        lambda route: (
            held_posts.append(route)
            if route.request.post_data_json["kind"] == "comment"
            else route.continue_()
        ),
    )
    page.locator(".lf-threads-toggle").click()
    select_words(page, "#passage")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    words = "A new comment before the container has answered."
    write(editor, words)
    page.keyboard.press("ControlOrMeta+Enter")

    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending.locator(".lf-msg-body")).to_have_text(words)
    expect(pending).to_be_visible()
    expect(page.locator('.lf-thread[data-id="saved-comment"]')).to_have_count(0)
    _history_outstanding(page)
    expect(page.locator(".lf-empty")).to_have_text(HISTORY_UNAVAILABLE)
    expect(page.locator(".lf-threads-toggle")).not_to_have_attribute(
        "data-lf-count", re.compile(".")
    )
    expect(page.locator(".lf-thread-view-summary")).not_to_have_text(
        re.compile(r"\b\d+(?: of \d+)? open threads?\b")
    )

    # Send lands on the new conversation in Threads. Return to the document
    # before invoking its Draw command, rather than racing that focus handoff.
    page.locator(".lf-threads-toggle").click()
    draw_over(page, page.locator("#passage"))
    expect(page.locator(".lf-drawing-pending")).to_have_count(1)
    drawing_words = "This stroke is also local before history arrives."
    write(page.locator(".lf-fab-input"), drawing_words)
    page.keyboard.press("ControlOrMeta+Enter")
    expect(pending).to_have_count(2)
    expect(pending.locator(".lf-msg-body", has_text=drawing_words)).to_have_count(1)
    expect(page.locator('.lf-drawing-posted[data-thread^="pending:"]')).to_have_count(1)

    _publish(
        serve.page_dir,
        2,
        EARLY_PAGE.replace("The words the reader first sees.", "A later replacement."),
        "Replace the passage while the early comment is pending",
    )
    release_state()
    holding(page, held_posts, 1, "the early anchored comment")
    post = held_posts[0].request.post_data_json
    assert post["revision"] == 1
    assert post["anchor"]["section"] == "passage"
    assert post["anchor"]["quote"] == "The words the reader first sees."
    page.unroute("**/api/event")
    while held_posts:
        held_posts.pop(0).continue_()
    round_trip(page)
    wait_until_ready(page)
    expect(page.locator("#passage")).to_have_text("A later replacement.")

    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("text") == words
    ]
    assert len(comments) == 1
    assert comments[0]["revision"] == 1
    drawings = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("text") == drawing_words
    ]
    assert len(drawings) == 1
    assert drawings[0]["revision"] == 1
    assert drawings[0]["drawing"]["format"] == "leaf-drawing/3"
    expect(
        page.locator(".lf-thread .lf-msg-body", has_text=drawing_words)
    ).to_have_count(1)
    expect(page.locator(".lf-thread .lf-msg-body", has_text=words)).to_have_count(1)
    expect(page.locator('.lf-thread[data-id="saved-comment"]')).to_have_count(1)
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_count(0)


def test_first_history_preserves_the_early_anchored_editor_and_caret(browser, serve):
    """First history preserves the anchored editor's words, focus and caret."""
    page, release_state = _cold_page(browser, serve(EARLY_PAGE) + "#passage")
    select_words(page, "#passage")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    words = "Keep my unfinished comment here."
    write(editor, words)
    editor.press("Home")
    editor.press("Shift+ArrowRight")
    editor.press("Shift+ArrowRight")
    before = editor.evaluate(
        "field => [field.selectionStart, field.selectionEnd, field.selectionDirection]"
    )
    release_state()
    wait_until_ready(page)
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", words)
    assert (
        editor.evaluate(
            "field => [field.selectionStart, field.selectionEnd, field.selectionDirection]"
        )
        == before
    )
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("text") == words
    ]


def test_an_early_touch_comment_returns_its_words_when_delivery_is_refused(
    browser, serve
):
    """The touch route works while cold; a later refusal restores the same draft."""
    page, release_state = _cold_page(browser, serve(EARLY_PAGE), touch=True)
    held_posts = []
    page.route(
        "**/api/event",
        lambda route: (
            held_posts.append(route)
            if route.request.post_data_json["kind"] == "comment"
            else route.continue_()
        ),
    )
    page.locator(".lf-banner-more").tap()
    page.locator(".lf-page-comment").tap()
    editor = page.locator(".lf-page-comment-card .lf-general leaf-text")
    words = "A comment sent from the cold touch page."
    write(editor, words)
    page.locator(".lf-general").get_by_role("button", name="Send", exact=True).tap()
    page.locator(".lf-threads-toggle").tap()
    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending.locator(".lf-msg-body")).to_have_text(words)
    expect(pending).to_be_visible()
    _history_outstanding(page)

    release_state()
    holding(page, held_posts, 1, "the early touch comment")
    attempt = held_posts[0].request.post_data_json["attempt"]
    page.unroute("**/api/event")
    with page.expect_response(re.compile(r"/api/event$")):
        held_posts.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "The cold comment was refused before append",
                "final": True,
            },
        )
    expect(pending).to_have_count(0)
    expect(editor).to_have_js_property("value", words)
    assert stored_draft_text(page, "general") == words
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("text") == words
    ]
    consume_browser_errors(page, {"code": "failed-load", "status": 400})


COLD_ASK = leaf_page(
    "Cold decisions",
    """<h1>Cold decisions</h1><lf-ask id="cold-ask"><h2>What now?</h2>
<lf-options id="cold-choice" choose>
<lf-option id="cold-a">A</lf-option><lf-option id="cold-b">B</lf-option>
</lf-options></lf-ask>""",
)


@pytest.mark.parametrize("key", ["q", "1", "z"])
def test_history_dependent_keys_keep_their_place_until_the_first_reading(
    browser, serve, key
):
    """Ask walking, Decisions, and Undo wait for their own saved history."""
    url = serve(COLD_ASK)
    if key != "q":
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "cold-choice",
                "action": "choose",
                "detail": {"value": ["cold-b"]},
            },
        )
    page, release_state = _cold_page(browser, url, clock=True)
    if key == "1":
        # This scopes the digit to the generated option control; focus paint is not
        # the subject here, but the command must retain the same scope across replay.
        page.locator("#cold-a .lf-pick").focus()
    page.keyboard.press(key)

    def echoed():
        page.clock.run_for(20)
        return page.locator(".lf-held-keys kbd").all_text_contents()

    wait_for(
        echoed,
        lambda keys: keys == [key],
        failure="the retained key never appeared",
    )
    if key == "q":
        expect(page.locator("#cold-ask")).not_to_be_focused()
    expect(page.locator("#cold-a")).not_to_have_attribute("chosen", "")
    expect(page.locator("#cold-b")).not_to_have_attribute("chosen", "")
    _history_outstanding(page)

    with page.expect_response(re.compile(r"/api/state(?:\?|$)")):
        release_state()
    _clock_until_ready(page)
    page.clock.resume()
    if key == "q":
        expect(page.locator("#cold-ask")).to_be_focused()
    elif key == "1":
        expect(page.locator("#cold-a")).to_have_attribute("chosen", "")
        round_trip(page)
    else:
        expect(page.locator(".lf-notice")).to_contain_text("Undid")
        round_trip(page)
        expect(page.locator("#cold-b")).not_to_have_attribute("chosen", "")
        assert (
            len(
                [
                    event
                    for event in events_model.read_events(serve.page_dir)
                    if event["kind"] == "undo"
                ]
            )
            == 1
        )
    expect(page.locator(".lf-held-keys")).to_have_count(0)


def test_a_known_local_thread_accepts_reply_search_and_resolve_before_history(
    browser, serve
):
    """Known local messages stay operable while the saved inventory is unknown."""
    page, release_state = _cold_page(browser, serve(EARLY_PAGE))
    held_posts = []
    page.route("**/api/event", lambda route: held_posts.append(route))
    page.locator(".lf-threads-toggle").click()
    root_words = "A known local conversation."
    write(page_comment(page), root_words)
    page.locator(".lf-general").get_by_role("button", name="Send", exact=True).click()
    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending.locator(".lf-msg-body")).to_have_text(root_words)
    reply_words = "An early reply to that conversation."
    write(pending.locator(".lf-thread-reply leaf-text"), reply_words)
    pending.locator(".lf-thread-send").click()
    expect(pending.locator(".lf-msg-body")).to_have_text([root_words, reply_words])

    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("a phrase absent from both messages")
    expect(pending).to_be_hidden()
    expect(page.locator(".lf-empty", has_text=HISTORY_UNAVAILABLE)).to_be_visible()
    search.fill("")
    expect(pending).to_be_visible()
    expect(pending.locator(".lf-msg-body")).to_have_text([root_words, reply_words])
    pending.get_by_role("button", name="Resolve thread", exact=True).click()
    expect(pending).to_have_attribute("data-resolved", "true")
    _history_outstanding(page)

    release_state()
    holding(page, held_posts, 1, "the known local conversation")
    page.unroute("**/api/event")
    while held_posts:
        held_posts.pop(0).continue_()
    round_trip(page)
    wait_until_ready(page)
    records = events_model.read_events(serve.page_dir)
    roots = [event for event in records if event.get("text") == root_words]
    replies = [event for event in records if event.get("text") == reply_words]
    assert len(roots) == len(replies) == 1
    assert roots[0]["kind"] == "comment"
    assert replies[0]["kind"] == "reply"
    assert replies[0]["parent"] == roots[0]["id"]
    assert (
        len(
            [
                event
                for event in records
                if event["kind"] == "resolve" and event["parent"] == roots[0]["id"]
            ]
        )
        == 1
    )
