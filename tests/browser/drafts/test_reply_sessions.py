"""A reply editor's native session: what typing, clicks, sends, resolution and a
replaced outlet leave of its caret, focus, reading position and Send."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_cases_navigation import source_revision
from render_harness import (
    LONG_PAGE,
    PANEL_THREAD,
    holding,
    leaf_page,
    open_page,
    round_trip,
    scroll_settled,
    sending,
    stored_draft_text,
    take_browser_errors,
    told,
    write,
)

from browser.threads import PANEL_REPLY, open_panel_thread, seed_panel_threads
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

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
    """Pointer entry owns the caret, rather than moving the thread the user reads."""
    url = serve(LONG_PAGE)
    (root,) = seed_panel_threads(serve.page_dir, 1, long_index=0)
    page = open_page(browser, url)
    view = open_panel_thread(page, root)
    place = view.evaluate("view => { view.scrollTop = 70; return view.scrollTop; }")
    assert place == 70
    field = page.locator(PANEL_REPLY)
    field.click()
    expect(field).to_be_focused()
    assert view.evaluate("view => view.scrollTop") == place


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
diff --git a/notes.md b/notes.md
--- a/notes.md
+++ b/notes.md
@@ -1 +1 @@
-before
+after
</pre></lf-diff>""",
        },
    )
    # Turns after the patch, so the thread's view scrolls.
    for index in range(12):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "user",
                "parent": root["id"],
                "revision": 1,
                "text": f"Another turn {index}. " + "Long enough to wrap. " * 6,
            },
        )
    page = open_page(browser, url)
    view = open_panel_thread(page, root["id"])
    field = view.locator("lf-diff .lf-diff-search")
    expect(field).to_be_visible()
    view.evaluate(
        """(view, field) => { view.scrollTop += field.getBoundingClientRect().top
          - view.getBoundingClientRect().top - 40; }""",
        field.element_handle(),
    )
    scroll_settled(page, PANEL_THREAD)
    before_click = view.evaluate("view => view.scrollTop")
    assert before_click > 0
    assert field.evaluate(
        "(field, view) => field.getBoundingClientRect().top > "
        "view.getBoundingClientRect().top",
        view.element_handle(),
    ), "the shadow input must already be visible before the click"

    field.click()

    expect(field).to_be_focused()
    assert view.evaluate("view => view.scrollTop") == before_click


def thread_root(page_dir, surface):
    """The root of the thread a reply session is written in: on the panel, a thread
    about the whole page, which opens there; on the margin, the page's comment on a
    passage, which opens in its margin card."""
    if surface == "panel":
        return panel_comment(page_dir, "A question about the whole page.")
    return next(
        event["id"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment"
    )


def open_reply(page, surface, root):
    """Open `root`'s thread on `surface` and put the caret in its reply; return the
    thread's view or card, and the reply box: the panel's field, or the card's."""
    if surface == "panel":
        thread = open_panel_thread(page, root)
        field = page.locator(PANEL_REPLY)
        field.click()
    else:
        page.keyboard.press("t")
        thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]'
        )
        page.keyboard.press("c")
        field = thread.locator("leaf-text")
    expect(field).to_be_focused()
    return thread, field


def expect_resolved(page, surface, thread, resolved):
    """The thread reads resolved, or not: the panel's by its head's Resolve or Reopen,
    a margin card by its own state."""
    if surface == "panel":
        expect(page.locator(".lf-fp-settle")).to_have_accessible_name(
            "Reopen" if resolved else "Resolve thread"
        )
    else:
        expect(thread).to_have_attribute("data-resolved", str(resolved).lower())


def send_button(page, surface, thread):
    holder = page.locator(".lf-fp-field") if surface == "panel" else thread
    return holder.get_by_role("button", name="Send", exact=True)


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
    root = thread_root(serve.page_dir, surface)
    page = open_page(browser, url, context=one_user)
    card, field = open_reply(page, surface, root)
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
    expect_resolved(page, surface, card, False)
    if answer == "accepted":
        held.pop().continue_()
    else:
        held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    page.unroute("**/api/event")
    round_trip(page)
    rendered(page)
    if answer == "refused":
        expect(card).to_be_visible()
        expect_resolved(page, surface, card, True)
        expect(field).to_be_visible()
        expect(field).to_have_js_property("value", words)
        assert stored_draft_text(page, "reply:" + root) == words
        # The refusal covers the words it gave back in the panel's field, which sends
        # nothing until the user's first edit or press there brings them back. The
        # press is one in the reply's row, so the resolved thread keeps its editor
        # once the press has finished painting.
        cover = page.locator(".lf-fp-field .lf-compose-error")
        expect(cover).to_contain_text("Please retry.")
        cover.click()
        rendered(page)
        expect(field).to_be_focused()
        with sending(page, "the same reply after refusal"):
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
    _, other = open_reply(second, surface, root)
    next_words = "A saved reply written in the other tab."
    write(other, next_words)
    expect(field).to_have_js_property("value", next_words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    rendered(page)
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

    Deliberate Resolve and reload close it. Every path preserves the words, which the
    panel's reply box shows in the resolved thread and keeps through Reopen, while an
    interrupted writer retains the native caret.
    """
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = thread_root(serve.page_dir, surface)
    page = open_page(browser, url)
    _, field = open_reply(page, surface, root)
    words = "An unfinished thought about this thread."
    write(field, words)
    field.evaluate("box => box.setSelectionRange(5, 5)")
    if resolution == "user":
        with sending(page, "the deliberate resolution"):
            page.locator(".lf-fp-settle").click()
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
                "parent": root,
            },
        )
        told(page)
    if resolution == "active-agent":
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        expect(field).to_have_js_property("value", words)
        assert field.evaluate("box => [box.selectionStart, box.selectionEnd]") == [5, 5]
        page.keyboard.press("Escape")
    if resolution == "user":
        # Resolving from the panel moves the user on, so the field is the next
        # thread's.
        expect(page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')).to_have_count(0)
    elif surface == "panel":
        # The panel's reply box stands in a resolved thread, its words with it.
        expect(field).to_have_js_property("value", words)
    else:
        expect(field).not_to_be_visible()
    assert stored_draft_text(page, f"reply:{root}") == words

    page.reload()
    wait_until_ready(page)
    recovered = open_panel_thread(page, root)
    expect(page.locator(PANEL_REPLY)).to_have_js_property("value", words)
    with sending(page, "reopen with the saved reply"):
        page.locator(".lf-fp-settle").click()
    expect(recovered).to_be_visible()
    expect(page.locator(PANEL_REPLY)).to_be_visible()
    expect(page.locator(PANEL_REPLY)).to_have_js_property("value", words)


@pytest.mark.parametrize(
    "surface, continuation",
    [("panel", "send"), ("margin", "dismiss"), ("panel", "clear")],
)
def test_a_resolved_reply_composition_stays_open_until_deliberately_dismissed(
    browser, serve, surface, continuation
):
    """Tab preserves the composition; Send or a deliberate press elsewhere ends it."""
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    root = thread_root(serve.page_dir, surface)
    page = open_page(browser, url)
    thread, field = open_reply(page, surface, root)
    words = "I still need to send this reply."
    write(field, words)
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    if continuation == "clear":
        field.press("ControlOrMeta+a")
        field.press("Backspace")
        rendered(page)
        expect(field).to_be_visible()
        expect(field).to_be_focused()
        expect(field).to_have_js_property("value", "")
        field.press("Escape")
        # The panel's field stands in a resolved thread, where a reply reopens it.
        if surface == "panel":
            expect(field).not_to_be_focused()
        else:
            expect(field).not_to_be_visible()
        assert stored_draft_text(page, f"reply:{root}") == ""
        return
    page.keyboard.press("Tab")
    send = send_button(page, surface, thread)
    expect(send).to_be_focused()
    rendered(page)
    expect(send).to_be_visible()
    expect(field).to_have_js_property("value", words)
    if continuation == "send":
        with sending(page, "the retained reply"):
            page.keyboard.press("Enter")
        replies = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "reply"
        ]
        assert [(event["parent"], event["text"]) for event in replies] == [
            (root, words)
        ]
    else:
        page.keyboard.press("Tab")
        rendered(page)
        expect(field).to_be_visible()
        page.locator("#p3").click(position={"x": 10, "y": 10})
        expect(field).not_to_be_visible()
        expect(page.locator('[data-lf-margin-for="p3"]')).to_have_count(0)
        assert stored_draft_text(page, f"reply:{root}") == words


def test_send_follows_a_reply_composition_whose_diff_outlet_disappears(browser, serve):
    """A replaced patch carries the same Send control to the thread's margin card."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    source = LONG_PAGE.replace(
        "<p id='p3'>",
        '<lf-diff id="patch" source="review-patch"></lf-diff><p id="p3">',
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
        '<lf-diff id="patch" source="review-patch"></lf-diff><a id="after-diff" href="#p3">After the diff</a><p id="p3">',
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


def test_keyboard_file_navigation_keeps_its_destination_beside_a_retained_reply(
    browser, serve
):
    """A tabbed-away reply continues without reopening the file the reader left."""
    patch = "".join(
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f'@@ -1 +1 @@\n-return "old"\n+return "{value}"\n'
        for path, value in [("app.py", "new"), ("tests.py", "checked")]
    )
    url = serve(
        leaf_page(
            "Review files beside a reply",
            '<h1>Review the patch</h1><lf-diff id="patch" source="review-patch" '
            'view="file"></lf-diff>'
            '<lf-file-tree id="files" for="patch"></lf-file-tree>'
            '<a id="after-files" href="#patch">Back to the patch</a>',
        ),
        packages=("diff", "file-tree"),
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "What about this return value?",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    page = open_page(browser, url)
    reply = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"] leaf-text')
    words = "Keep this draft while I inspect the test."
    write(reply, words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    caret = reply.evaluate("node => node.selectionStart")
    search = page.locator("#files").get_by_role("textbox")
    for _ in range(20):
        page.keyboard.press("Tab")
        if search.evaluate('node => node.matches(":focus")'):
            break
    expect(search).to_be_focused()
    page.keyboard.press("Tab")
    page.keyboard.press("End")
    target = page.locator("#files").get_by_role("treeitem", name="tests.py", exact=True)
    expect(target).to_be_focused()
    page.keyboard.press("Enter")
    wait_until_ready(page)
    expect(target).to_have_attribute("aria-selected", "true")
    expect(
        page.locator("#patch").get_by_text('return "checked"', exact=True)
    ).to_be_visible()
    expect(target).to_be_focused()
    assert stored_draft_text(page, f"reply:{root}") == words
    # Resuming is explicit; merely inspecting another file must not take the reader back.
    page.keyboard.press("Tab")
    expect(page.locator("#after-files")).to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("i")
    resumed = page.locator("leaf-text:focus")
    expect(resumed).to_have_js_property("value", words)
    expect(resumed).to_have_js_property("selectionStart", caret)


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
        '<lf-diff id="patch" source="review-patch"></lf-diff><a id="after-diff" href="#p3">After the diff</a><a id="second-link" href="#p3">Second link</a><p id="p3">',
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
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", patch + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    # Tab is a newer location intent while the same native editing generation remains
    # alive: the reply's continuation does not take it back.
    expect(after).to_be_focused()
    page.keyboard.press("Tab")
    second = page.locator("#second-link")
    expect(second).to_be_focused()
    wait_until_ready(page)
    expect(page.locator("lf-diff").get_by_text("new = 1", exact=True)).to_be_visible()
    expect(inline).to_have_count(0)
    expect(second).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_have_count(0)
    # A page drawing no margin continues the reply in the panel's thread.
    expect(page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')).to_be_visible()
    reply = page.locator(PANEL_REPLY)
    expect(reply).to_be_visible()
    expect(reply).to_have_js_property("value", words)
    assert reply.evaluate("node => [node.selectionStart,node.selectionEnd]") == [1, 1]
    reply.focus()
    with sending(page, "the continued reply in the panel"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["parent"], sent["text"]) == ("reply", root, words)
