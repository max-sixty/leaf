"""Local comments remain usable while the first private-state read is pending."""

import re

import pytest
from interact_support import append_carried_log_record, append_command
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import _publish
from render_harness import (
    FEATURE_GALLERY,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    round_trip,
    select,
    select_words,
    stored_draft_text,
    told,
    watched,
    write,
)
from test_render_drawing import draw_over

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


def _cold_page(browser, url, *, touch=False):
    """Hold this page's private history; embedded sample pages load independently."""
    page = browser.new_page(
        viewport={"width": 390 if touch else 1200, "height": 900}, has_touch=touch
    )
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
    assert (
        "ready for reading and new comments"
        in page.locator(".lf-status-detail").inner_text()
    )
    words = "A new comment before the container has answered."
    write(editor, words)
    page.keyboard.press("ControlOrMeta+Enter")

    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending.locator(".lf-msg-body")).to_have_text(words)
    expect(pending).to_be_visible()
    expect(page.locator('.lf-thread[data-id="saved-comment"]')).to_have_count(0)
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-empty")).to_have_text("Loading current threads…")
    expect(page.locator(".lf-threads-toggle")).not_to_have_attribute(
        "data-lf-count", re.compile(".")
    )
    expect(page.locator(".lf-thread-view-summary")).not_to_have_text(
        re.compile(r"\b\d+(?: of \d+)? open threads?\b")
    )

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
    if saved_before:
        saved = page.locator('.lf-thread[data-id="saved-comment"]')
        expect(saved).to_be_hidden()
        page.locator(".lf-threads").get_by_role(
            "button", name="1 new thread", exact=True
        ).click()
        expect(saved).to_be_visible()


def test_the_ask_walk_reveals_a_new_card_held_from_first_history(browser, serve):
    """Held history still builds its widgets, and a direct Ask arrival shows its card."""
    saved = {**SAVED_COMMENT, "anchor": {"section": "title"}}
    page, release = _cold_page(
        browser,
        serve(
            EARLY_PAGE.replace("<h1>", '<h1 id="title">'),
            events=[
                saved,
                {
                    "id": "saved-answer",
                    "kind": "reply",
                    "author": "agent",
                    "agent": "Codex",
                    "revision": 1,
                    "parent": saved["id"],
                    "text": "A question from the previous visit.",
                    "markup": '<lf-ask id="saved-question"><h3>Which answer?</h3>'
                    '<lf-options id="saved-choice" choose>'
                    '<lf-option id="saved-yes">Proceed</lf-option>'
                    '<lf-option id="saved-no">Wait</lf-option>'
                    "</lf-options></lf-ask>",
                },
            ],
        ),
    )
    page.locator(".lf-threads-toggle").click()
    select_words(page, "#passage")
    page.keyboard.press("c")
    write(page.locator(".lf-fab-input"), "A new observation before history arrives.")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_be_visible()
    release()
    wait_until_ready(page)
    saved_card = page.locator('.lf-thread[data-id="saved-comment"]')
    expect(saved_card).to_be_hidden()
    expect(saved_card.locator("#saved-question")).to_have_count(1)
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("q")
    expect(saved_card).to_be_visible()
    expect(saved_card.locator("#saved-question")).to_be_focused()


def test_first_history_keeps_an_early_annotation_rail_reply_in_view(browser, serve):
    """A released local rail reading protects its native editor before history loads."""
    source = leaf_page(
        "Rail reading",
        '<section id="reading"><h1>Two passages</h1>'
        "<p>The earlier passage describes a sheltered garden route.</p>"
        "<p>The later passage recommends taking the river footbridge.</p>"
        '</section><lf-annotation-rail id="annotations"></lf-annotation-rail>',
        head="<style>main.layout-column {display:grid;grid-template-columns:"
        "minmax(0,1fr) 360px;gap:40px;max-width:1100px}"
        "lf-annotation-rail {width:360px;height:650px;overflow:auto}</style>",
    ).replace("<body>", '<body data-annotations="page">')
    page, release = _cold_page(
        browser,
        serve(
            source,
            events=[
                {
                    **SAVED_COMMENT,
                    "anchor": {
                        "section": "reading",
                        "quote": "The earlier passage describes a sheltered garden route.",
                    },
                    "text": "Earlier saved discussion. " + "Supporting context. " * 50,
                }
            ],
        ),
    )
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route)
            if route.request.post_data_json["kind"] == "comment"
            else route.continue_()
        ),
    )
    select_words(page, "#reading p:last-child")
    page.keyboard.press("c")
    write(page.locator(".lf-fab-input"), "An early observation about the footbridge.")
    page.keyboard.press("ControlOrMeta+Enter")
    rail = page.locator("lf-annotation-rail")
    card = rail.locator('.lf-page-thread[data-thread^="pending:"]')
    expect(card).to_be_visible()
    reply = card.get_by_role("textbox")
    write(reply, "An unfinished reply")
    reply.press("ArrowLeft")
    caret = reply.evaluate("e => [e.selectionStart, e.selectionEnd]")
    before = reply.bounding_box()
    release()
    wait_until_ready(page)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "An unfinished reply")
    assert reply.evaluate("e => [e.selectionStart, e.selectionEnd]") == caret
    assert abs(reply.bounding_box()["y"] - before["y"]) < 1
    expect(rail.get_by_role("button", name="Show updated annotations")).to_be_enabled()


@pytest.mark.parametrize("edited", [False, True], ids=["seed", "edited"])
def test_commenting_on_the_same_selection_preserves_the_existing_suggestion(
    browser, serve, edited
):
    """Activating an already captured passage focuses its existing draft and mode."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Selection mode",
                '<h1>Selection mode</h1><p id="words">The same selected passage.</p>',
            )
        ),
    )
    select_words(page, "#words")
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    page.keyboard.press("Tab")
    page.locator(".lf-fab-suggest").click()
    expect(editor).to_have_attribute("placeholder", re.compile(r"^Replacement text"))
    words = "My replacement" if edited else "The same selected passage."
    if edited:
        write(editor, words)
    select_words(page, "#words")
    rendered(page)
    expect(page.locator('input[name="suggest-replacement"]')).to_be_checked()
    page.keyboard.press("c")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", words)
    expect(editor).to_have_attribute("placeholder", re.compile(r"^Replacement text"))


def test_filtered_neighbors_cannot_hide_a_new_cards_visible_insertion(browser, serve):
    """A filtered intervening card cannot mask the live row an arrival would move."""
    source = leaf_page(
        "Neighbors",
        '<h1>Neighbors</h1><p id="a">First passage.</p>'
        '<p id="b">Second passage.</p><p id="c">Third passage.</p>',
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                {**SAVED_COMMENT, "id": "hidden", "anchor": {"section": "b"}},
                {
                    **SAVED_COMMENT,
                    "id": "visible",
                    "author": "agent",
                    "text": "Visible agent question.",
                    "anchor": {"section": "c"},
                },
            ],
        ),
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    title = page.locator('.lf-thread[data-id="visible"] > .lf-thread-summary')
    title.click()
    expect(title).to_be_focused()
    page.keyboard.press("w")
    expect(page.locator('.lf-thread[data-id="hidden"]')).to_be_hidden()
    expect(title).to_be_visible()
    rendered(page)
    before = title.bounding_box()["y"]
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "new",
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "New agent question.",
            "anchor": {"section": "a"},
        },
    )
    told(page)
    assert abs(title.bounding_box()["y"] - before) < 1
    expect(page.locator('.lf-thread[data-id="new"]')).to_be_hidden()
    page.locator(".lf-threads").get_by_role(
        "button", name="1 new thread", exact=True
    ).click()
    expect(page.locator('.lf-thread[data-id="new"]')).to_be_visible()


def test_first_history_preserves_the_early_anchored_editor_and_caret(browser, serve):
    """The gallery's new-thread scenario stays editable while history loads."""
    page, release_state = _cold_page(browser, serve(FEATURE_GALLERY) + "#bg-new-thread")
    select_words(page, "#bg-new-thread")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    assert (
        "ready for reading and new comments"
        in page.locator(".lf-status-detail").inner_text()
    )
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


@pytest.mark.parametrize("first_history", [True, False])
@pytest.mark.parametrize("resumed", [False, True])
def test_saved_widget_words_cannot_dismiss_an_unfinished_comment(
    browser, serve, first_history, resumed
):
    """An editor survives quoted words changing on initial or subsequent replay."""
    source = leaf_page(
        "Mutable words",
        '<h1>Mutable words</h1><lf-draft id="mutable">'
        "<pre>The words first shown.</pre></lf-draft>",
    )
    url = serve(source)

    def replace_words(value="Different saved words."):
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "mutable",
                "action": "edit",
                "detail": {"value": value},
            },
        )

    if first_history:
        replace_words()
        page, release = _cold_page(browser, url)
    else:
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.goto(url)
        wait_until_ready(page)
    shown = page.locator("#mutable .lf-draft-body")
    expect(shown).to_have_text("The words first shown.")
    bounds = shown.evaluate(
        "e => { const r = document.createRange(); r.selectNodeContents(e); "
        "return r.getBoundingClientRect().toJSON(); }"
    )
    y = bounds["top"] + bounds["height"] / 2
    select(page, (bounds["left"] + 1, y), (bounds["right"] - 1, y))
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    words = "Keep this unfinished observation."
    write(editor, words)
    if resumed:
        page.keyboard.press("Escape")
        page.mouse.click(5, 600)
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(editor).to_be_focused()
    editor.press("Home")
    editor.press("Shift+ArrowRight")
    caret = editor.evaluate("e => [e.selectionStart, e.selectionEnd]")
    rendered(page)
    editor_before = editor.bounding_box()
    if first_history:
        release()
        wait_until_ready(page)
    else:
        replace_words()
        told(page)
    expect(shown).to_have_text("Different saved words.")
    rendered(page)
    editor_after = editor.bounding_box()
    assert abs(editor_after["x"] - editor_before["x"]) < 1
    assert abs(editor_after["y"] - editor_before["y"]) < 1
    expect(editor).to_be_visible()
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", words)
    assert editor.evaluate("e => [e.selectionStart, e.selectionEnd]") == caret
    replace_words("The words first shown.")
    told(page)
    rendered(page)
    editor_restored = editor.bounding_box()
    assert abs(editor_restored["x"] - editor_before["x"]) < 1
    assert abs(editor_restored["y"] - editor_before["y"]) < 1
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    assert len(comments) == 1
    assert comments[0]["revision"] == 1
    assert comments[0]["anchor"]["quote"] == "The words first shown."


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
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")

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
    consume_browser_errors(page, "400")


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
    """Ask walking, Decisions, and Undo wait for their own standing history."""
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
    page, release_state = _cold_page(browser, url)
    if key == "1":
        # This scopes the digit to the generated option control; focus paint is not
        # the subject here, but the command must retain the same scope across replay.
        page.locator("#cold-a .lf-pick").focus()
    page.keyboard.press(key)
    expect(page.locator(".lf-held-keys kbd")).to_have_text(key)
    if key == "q":
        expect(page.locator("#cold-ask")).not_to_be_focused()
    expect(page.locator("#cold-a")).not_to_have_attribute("chosen", "")
    expect(page.locator("#cold-b")).not_to_have_attribute("chosen", "")
    assert (
        "ready for reading and new comments"
        in page.locator(".lf-status-detail").inner_text()
    )

    release_state()
    wait_until_ready(page)
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
    expect(
        page.locator(".lf-empty", has_text="Loading current threads…")
    ).to_be_visible()
    search.fill("")
    expect(pending).to_be_visible()
    expect(pending.locator(".lf-msg-body")).to_have_text([root_words, reply_words])
    pending.get_by_role("button", name="Resolve thread", exact=True).click()
    expect(pending).to_have_attribute("data-resolved", "true")
    assert (
        "ready for reading and new comments"
        in page.locator(".lf-status-detail").inner_text()
    )
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")

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
