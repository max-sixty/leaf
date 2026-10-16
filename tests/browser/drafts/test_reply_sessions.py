"""A reply editor's native session: what typing, clicks, sends, resolution and a
replaced outlet leave of its caret, focus, reading position and Send."""

import pytest
from interact_support import append_carried_log_record
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_harness import (
    LONG_PAGE,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    round_trip,
    scroll_settled,
    sending,
    stored_draft_text,
    take_browser_errors,
    told,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("bounded", [False, True])
def test_typing_in_a_visible_inline_reply_keeps_the_reading_position(
    browser, serve, bounded
):
    """Keeping a reply's controls visible does not reveal its already-scrolled-past turns."""
    content = """
<div style="height:900px"></div>
<lf-test-plan id="hub" label="Tasks"><lf-test-task id="jobs" status="active" talk>
What should we do next?</lf-test-task></lf-test-plan>
<div style="height:900px"></div>
"""
    if bounded:
        content = (
            '<div id="reader" data-bound="start" style="height:480px">'
            + content
            + "</div>"
        )
    url = serve(leaf_page("Reply reading", content))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "text": "A short question the reader has already passed.",
            "anchor": {"section": "jobs"},
        },
    )
    page = open_page(browser, url)
    thread = page.locator("#jobs .lf-page-thread")
    reply = thread.locator("leaf-text")
    reply.click()
    reply.evaluate(
        """(input, bounded) => {
      const scroller = bounded ? document.querySelector('#reader') : document.scrollingElement;
      const top = bounded ? scroller.getBoundingClientRect().top : 0;
      scroller.scrollBy(0, input.getBoundingClientRect().top - top - 55);
    }""",
        bounded,
    )
    scroll_settled(page)
    before = page.evaluate(
        """bounded => ({
      scroll: (bounded ? document.querySelector('#reader') : document.scrollingElement).scrollTop,
      reply: document.querySelector('#jobs leaf-text').getBoundingClientRect().top,
      thread: document.querySelector('#jobs .lf-page-thread').getBoundingClientRect().top,
    })""",
        bounded,
    )
    assert before["thread"] < (
        page.locator("#reader").bounding_box()["y"] if bounded else 0
    ), before
    expect(reply).to_be_focused()
    page.keyboard.type("A")
    round_trip(page)
    after = page.evaluate(
        """bounded => ({
      scroll: (bounded ? document.querySelector('#reader') : document.scrollingElement).scrollTop,
      reply: document.querySelector('#jobs leaf-text').getBoundingClientRect().top,
    })""",
        bounded,
    )
    assert after["scroll"] == pytest.approx(before["scroll"], abs=1), (before, after)
    assert after["reply"] == pytest.approx(before["reply"], abs=1), (before, after)


def test_clicking_a_visible_reply_preserves_the_thread_reading(browser, serve):
    """Pointer entry owns the caret, rather than revealing the whole containing card."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    thread = page.locator(".lf-thread[open]").first
    field = thread.locator("leaf-text")
    place = page.evaluate(
        """() => {
          const list = document.querySelector('.lf-threads');
          list.scrollTop = 70;
          return list.scrollTop;
        }"""
    )
    assert place == 70
    field.click()
    expect(field).to_be_focused()
    assert page.locator(".lf-threads").evaluate("el => el.scrollTop") == place


def test_clicking_a_shadow_widget_input_keeps_its_focus_and_thread_reading(
    browser, serve
):
    """A message's public widget keeps its native input across the thread's pointer-up."""
    url = serve(LONG_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Review the patch.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "revision": 1,
            "text": "Filter the files in this patch.",
            "markup": """<lf-diff id="reply-patch" data-height="151"><pre>
diff --git a/reading.py b/reading.py
--- a/reading.py
+++ b/reading.py
@@ -1,2 +1,2 @@
 def reading():
-    return "before"
+    return "after"
</pre></lf-diff>""",
        },
    )
    for index in range(16):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"Another thread {index}.",
            },
        )
    page = open_page(browser, url)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    field = page.locator(".lf-thread[open] lf-diff .lf-diff-search")
    expect(field).to_be_visible()
    page.locator(".lf-threads").evaluate("list => list.scrollTop = 70")
    scroll_settled(page, ".lf-threads")
    before_click = page.locator(".lf-threads").evaluate("list => list.scrollTop")
    assert before_click > 0
    assert field.evaluate(
        "field => field.getBoundingClientRect().top > "
        "field.getRootNode().host.closest('.lf-threads').getBoundingClientRect().top"
    ), "the shadow input must already be visible before the click"

    field.click()

    expect(field).to_be_focused()
    assert (
        page.locator(".lf-threads").evaluate("list => list.scrollTop") == before_click
    )


@pytest.mark.parametrize(
    "surface, answer", [("panel", "refused"), ("margin", "accepted")]
)
def test_reply_admission_finishes_or_restores_its_native_session(
    browser, serve, one_user, surface, answer
):
    """A provisional send keeps the editor owed a refusal; acceptance finishes editing.

    Refusal returns words to the agent-resolved thread and retries the same attempt.
    After acceptance, another tab's words remain saved without activating this editor.
    """
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url, context=one_user)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        card.locator(".lf-thread-summary").focus()
    else:
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        page.keyboard.press("c")
    field = card.locator("leaf-text")
    words = "This reply still belongs to the resolved thread."
    write(field, words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    expect(field).to_be_focused()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the provisional reply")
    attempt = held[0].request.post_data_json["attempt"]
    expect(field).to_have_js_property("value", "")
    expect(card).to_have_attribute("data-resolved", "false")
    if answer == "accepted":
        held.pop().continue_()
    else:
        held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    page.unroute("**/api/event")
    round_trip(page)
    rendered(page)
    if answer == "refused":
        expect(card).to_be_visible()
        expect(card).to_have_attribute("data-resolved", "true")
        expect(field).to_be_visible()
        expect(field).to_have_js_property("value", words)
        assert stored_draft_text(page, "reply:" + root) == words
        with sending(page, "the same reply after refusal"):
            field.focus()
            page.keyboard.press("ControlOrMeta+Enter")
        reply = events_model.read_events(serve.page_dir)[-1]
        assert (reply["kind"], reply["parent"], reply["text"], reply["attempt"]) == (
            "reply",
            root,
            words,
            attempt,
        )
        return
    expect(field).to_have_js_property("value", "")
    second = open_page(browser, url, context=one_user)
    if second.locator(".lf-threads-toggle").get_attribute("aria-expanded") != "true":
        second.locator(".lf-threads-toggle").click()
    panel_settled(second)
    other = second.locator(f'.lf-thread[data-id="{root}"]')
    other.locator(".lf-thread-summary").focus()
    next_words = "A saved reply written in the other tab."
    write(other.locator("leaf-text"), next_words)
    expect(field).to_have_js_property("value", next_words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    rendered(page)
    if surface == "panel":
        # The open card holds the resolution behind its notice until the user asks.
        card.get_by_role("button", name="Resolved", exact=True).click()
    expect(field).to_be_hidden()
    assert stored_draft_text(page, "reply:" + root) == next_words


@pytest.mark.parametrize(
    "surface, resolution",
    [("panel", "user"), ("margin", "active-agent"), ("panel", "inactive-agent")],
)
def test_reply_editing_and_saved_words_have_separate_resolution_lifetimes(
    browser, serve, surface, resolution
):
    """Only an external settlement interrupting active editing retains the editor.

    Deliberate Resolve and reload close it. Every path preserves the words for an
    explicit Reopen, while an interrupted writer retains the native caret.
    """
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
        thread.locator(".lf-thread-summary").click()
    else:
        page.keyboard.press("t")
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root["id"]}"]'
        )
        page.keyboard.press("c")
    field = thread.locator("leaf-text")
    words = "An unfinished thought about this thread."
    write(field, words)
    field.evaluate("box => box.setSelectionRange(5, 5)")
    if resolution == "user":
        with sending(page, "the deliberate resolution"):
            thread.locator(".lf-resolve").click()
    else:
        if resolution == "inactive-agent":
            page.keyboard.press("Escape")
            assert take_browser_errors(page) == []
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "resolve",
                "author": "agent",
                "agent": "Codex",
                "parent": root["id"],
            },
        )
        told(page)
    if resolution == "active-agent":
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        expect(field).to_have_js_property("value", words)
        assert field.evaluate("box => [box.selectionStart, box.selectionEnd]") == [5, 5]
        page.keyboard.press("Escape")
        if surface == "panel":
            # Escape ends the editing and lands on the card's title, a move within the
            # thread, so the card still holds the resolution behind its notice.
            expect(field).to_be_visible()
            thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(field).not_to_be_visible()
    elif resolution == "inactive-agent" and surface == "panel":
        # The open card holds the resolution behind its notice, words and all, until
        # the user presses it.
        expect(field).to_be_visible()
        expect(field).to_have_js_property("value", words)
        thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(field).not_to_be_visible()
    else:
        expect(thread.locator("leaf-text")).not_to_be_visible()
    assert stored_draft_text(page, f"reply:{root['id']}") == words
    if resolution == "inactive-agent" and surface == "margin":
        # An unresolved thread still draws its inactive reply box after Escape.
        # Agent settlement then closes it, as this lifecycle deliberately requires.
        # The generic words sensor cannot infer that ending the editing session made
        # this later passive close legitimate. Calibrate only this exact loss here;
        # Escape itself, active settlement, and every other field remain strict.
        errors = consume_browser_errors(
            page,
            {"code": "words-left-screen", "words": words, "place": ["leaf-text.lf-ui"]},
        )
        assert len(errors) == 1

    page.reload()
    wait_until_ready(page)
    if surface == "margin":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    recovered = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
    recovered.locator(".lf-thread-summary").click()
    expect(recovered.locator("leaf-text")).to_have_count(0)
    with sending(page, "reopen with the saved reply"):
        recovered.locator(".lf-reopen").click()
    expect(recovered.locator("leaf-text")).to_be_focused()
    expect(recovered.locator("leaf-text")).to_have_js_property("value", words)


@pytest.mark.parametrize(
    "surface, continuation",
    [("panel", "send"), ("margin", "dismiss"), ("panel", "clear")],
)
def test_a_resolved_reply_composition_stays_open_until_deliberately_dismissed(
    browser, serve, surface, continuation
):
    """Tab preserves the composition; Send or a deliberate press elsewhere ends it."""
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    if surface == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root["id"]}"]')
        thread.locator(".lf-thread-summary").click()
    else:
        page.keyboard.press("t")
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root["id"]}"]'
        )
        page.keyboard.press("c")
    words = "I still need to send this reply."
    write(thread.locator("leaf-text"), words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root["id"]},
    )
    told(page)
    if continuation == "clear":
        field = thread.locator("leaf-text")
        field.press("ControlOrMeta+a")
        field.press("Backspace")
        rendered(page)
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        expect(field).to_have_js_property("value", "")
        field.press("Escape")
        if surface == "panel":
            # The card holds the resolution behind its notice until the user asks.
            thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(field).not_to_be_visible()
        assert stored_draft_text(page, f"reply:{root['id']}") == ""
        return
    page.keyboard.press("Tab")
    send = thread.get_by_role("button", name="Send", exact=True)
    expect(send).to_be_focused()
    rendered(page)
    expect(send).to_be_visible()
    expect(thread.locator("leaf-text")).to_have_js_property("value", words)
    if continuation == "send":
        with sending(page, "the retained reply"):
            page.keyboard.press("Enter")
        replies = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "reply"
        ]
        assert [(event["parent"], event["text"]) for event in replies] == [
            (root["id"], words)
        ]
    else:
        page.keyboard.press("Tab")
        rendered(page)
        expect(thread.locator("leaf-text")).to_be_visible()
        page.locator("#p3").click(position={"x": 10, "y": 10})
        if surface == "panel":
            # The open card holds the resolution behind its notice, so it still draws
            # an open thread's reply box until the user asks to see the resolution.
            expect(thread.locator("leaf-text")).to_be_visible()
            thread.get_by_role("button", name="Resolved", exact=True).click()
        expect(thread.locator("leaf-text")).not_to_be_visible()
        if surface == "margin":
            expect(page.locator('[data-lf-margin-for="p3"]')).to_have_count(0)
        assert stored_draft_text(page, f"reply:{root['id']}") == words


def test_send_follows_a_reply_composition_whose_diff_outlet_disappears(browser, serve):
    """A replaced patch carries the same Send control to the thread's margin card."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    page.keyboard.press("Tab")
    expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(inline).to_have_count(0)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    expect(card.get_by_role("button", name="Send", exact=True)).to_be_focused()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)
    with sending(page, "the reply after its Send moved"):
        page.keyboard.press("Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, words)


@pytest.mark.parametrize("resolved, cleared", [(False, True), (True, False)])
def test_tab_browsing_keeps_a_reply_when_its_diff_outlet_is_replaced(
    browser, serve, resolved, cleared
):
    """External source replacement carries editing without reversing native Tab."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    if cleared:
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        words = ""
    if resolved:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
        told(page)
    page.keyboard.press("Tab")
    if not cleared:
        expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    rendered(page)
    expect(inline.locator("leaf-text")).to_be_visible()
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(page.locator("lf-diff").get_by_text("new = 1", exact=True)).to_be_visible()
    expect(inline).to_have_count(0)
    expect(after).to_be_focused()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    expect(card.locator("leaf-text")).to_be_visible()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)


def test_tab_browsing_continues_a_displaced_reply_without_an_annotation_overlay(
    browser, serve
):
    """Native Tab during core continuation preserves its caret and newer authored focus."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><a id="second-link" href="#p3">Second link</a><p id="p3">',
    )
    source = source.replace("<body>", '<body data-annotations="page">', 1)
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can this line return a different value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    page.keyboard.press("t")
    page.keyboard.press("c")
    words = "I still need to send my answer about that line."
    write(inline.locator("leaf-text"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    page.keyboard.press("Tab")
    expect(inline.get_by_role("button", name="Send", exact=True)).to_be_focused()
    rendered(page)
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    rendered(page)
    expect(inline.locator("leaf-text")).to_be_visible()
    # Hold the actual panel presentation, after its route was chosen. Tab is a
    # newer standing intent while the same native editing generation remains alive.
    page.evaluate(
        """() => {
          const list = document.querySelector('.lf-threads');
          const present = list.present.bind(list);
          const held = Promise.withResolvers();
          list.present = model => {
            if (!document.querySelector('.lf-thread-panel').classList.contains('open')) return present(model);
            window.replyContinuationHeld = true;
            return held.promise.then(() => present(model));
          };
          window.releaseReplyContinuation = () => {
            list.present = present;
            held.resolve();
          };
        }"""
    )
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    page.wait_for_function("window.replyContinuationHeld === true")
    expect(after).to_be_focused()
    page.keyboard.press("Tab")
    second = page.locator("#second-link")
    expect(second).to_be_focused()
    page.evaluate("releaseReplyContinuation()")
    wait_until_ready(page)
    expect(page.locator("lf-diff").get_by_text("new = 1", exact=True)).to_be_visible()
    expect(inline).to_have_count(0)
    expect(second).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_have_count(0)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card.locator("leaf-text")).to_be_visible()
    expect(card.locator("leaf-text")).to_have_js_property("value", words)

    assert card.locator("leaf-text").evaluate(
        "node => [node.selectionStart,node.selectionEnd]"
    ) == [1, 1]
    card.locator("leaf-text").focus()
    with sending(page, "the continued reply in Threads"):
        page.keyboard.press("Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, words)


@pytest.mark.parametrize("leave", ["send", "escape"])
def test_replaced_reply_compositions_keep_their_carets_and_leave_commands(
    browser, serve, leave
):
    """One selected card can carry several native sessions without merging their exits.

    Both agent-resolved replies retain their words and carets through source replacement.
    Existing disclosure selects each; Send and Escape dismiss only the addressed one.
    """
    patch = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n-old = 1\n+new = 1\n-old = 2\n+new = 2\n"
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff><a id="after-diff" href="#p3">After the diff</a><p id="p3">',
    )
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    roots = [
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"Please review line {line}.",
                "anchor": {
                    "section": "patch",
                    "datum": f'["app.py","new",{line}]',
                    "source": "review-patch",
                    "source_revision": source_revision(serve.page_dir, "review-patch"),
                },
            },
        )["id"]
        for line in (1, 2)
    ]
    page = open_page(browser, url)
    inputs = [
        page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"] leaf-text')
        for root in roots
    ]
    words = ["My unfinished first answer.", "My unfinished second answer."]
    write(inputs[0], words[0])
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Tab")
    write(inputs[1], words[1])
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    after = page.locator("#after-diff")
    for _ in range(20):
        page.keyboard.press("Tab")
        if after.evaluate('node => node.matches(":focus")'):
            break
    expect(after).to_be_focused()
    for root in roots:
        events_model.append_event(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
    told(page)
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 9\n+new = 9\n"
    )
    told(page)
    expect(after).to_be_focused()
    # One margin card remains the current selection. The other native session keeps
    # its words and caret until the user selects its next route, so its words are off
    # the screen meanwhile.
    page.evaluate("() => window.lfWordsJudged()")
    consume_browser_errors(page, {"code": "words-left-screen", "words": words[0]})
    for root, word in zip(roots, words):
        box = page.locator(f'.lf-thread[data-id="{root}"] leaf-text')
        expect(box).to_have_js_property("value", word)
    current = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[1]}"] leaf-text'
    )
    assert current.evaluate("node => [node.selectionStart,node.selectionEnd]") == [2, 2]
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    first = page.locator(f'.lf-thread[data-id="{roots[0]}"]')
    first.locator(".lf-thread-summary").focus()
    expect(first.locator("leaf-text")).to_be_visible()
    expect(first.locator("leaf-text")).to_have_js_property("value", words[0])

    for index, (root, word) in enumerate(zip(roots, words), 1):
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        card.locator(".lf-thread-summary").focus()
        page.keyboard.press("c")
        expect(card.locator("leaf-text")).to_be_focused()
        assert card.locator("leaf-text").evaluate(
            "node => [node.selectionStart,node.selectionEnd]"
        ) == [index, index]
        if index == 1 and leave == "escape":
            page.keyboard.press("Escape")
            expect(card.locator("leaf-text")).to_have_count(0)
            assert stored_draft_text(page, "reply:" + root) == word
            continue
        with sending(page, "the retained composition selected in Threads"):
            page.keyboard.press("Enter")
        reply = events_model.read_events(serve.page_dir)[-1]
        assert (reply["kind"], reply["parent"], reply["text"]) == ("reply", root, word)
