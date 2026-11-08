"""Durable user acknowledgement through the rendered Thread surfaces."""

import json
import re
import threading
import time

import pytest
from interact_support import STATED_TIMEOUT, append_carried_log_record
from journeys.test_render_read_state import (
    _CARD_BOXES,
    TASK_SEAT_PAGE,
    _agent_update_reply,
    _box_height,
    _expect_news,
    _first_unread,
    _on_me_mark,
    _read_events,
    _said,
    _select_new_route,
    _thread_row,
)
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_cases_layout import overlapped_words
from render_cases_widgets import LONG_LINE_DIFF_PAGE, MULTI_HUNK_PATCH
from render_harness import (
    RELEASE_FOCUS,
    CutOff,
    _traffic,
    expect_preview_words,
    fetch_whole_state,
    heard_back,
    holding,
    http_error_console,
    is_problem,
    open_page,
    open_threads,
    panel_settled,
    reported_browser_errors,
    resized,
    round_trip,
    sending,
    take_browser_errors,
    told,
    write,
)

from browser.threads import open_panel_thread
from leaf import data as data_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import http as http_model
from leaf import thread as thread_model
from leaf.findings import Finding
from leaf.render_checks import (
    SERVED_TIMEOUT_MS,
    rendered,
    wait_until_ready,
)
from leaf_dev.browser import (
    PANEL_THREAD,
    panel_tab,
    threads_tab,
)


def test_opening_threads_acknowledges_the_first_visible_answer(
    browser, serve, monkeypatch
):
    """Opening a thread in the panel over an answer it shows marks it read.

    The read is bookkeeping and never enters the outbox, so the ledger's `pending` is
    empty while its post is still on the wire. Holding the post before the server
    appends it puts the log read on that edge every run: a trip judged by the outbox
    alone is over before the event exists."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "An answer already in view.", author="agent")
    page = open_page(browser, url)
    arrived = threading.Event()
    release = threading.Event()
    accept = http_model.accept_event

    def hold_the_read(page_dir, event, *args):
        if event["kind"] == "read":
            arrived.set()
            release.wait()
        return accept(page_dir, event, *args)

    monkeypatch.setattr(http_model, "accept_event", hold_the_read)
    try:
        open_panel_thread(page, root)
        assert arrived.wait(STATED_TIMEOUT), "opening the thread sent no read"
        on_the_wire = _traffic(page).read()
        assert on_the_wire.pending == []
        assert not heard_back(on_the_wire)
    finally:
        release.set()
    round_trip(page)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_authored_reply_is_read_when_its_visible_body_is_shown(browser, serve):
    url = serve(PANEL_PAGE)
    root = thread_model.cmd_comment(
        serve.page_dir,
        None,
        None,
        None,
        "Choose the next step.",
        '<lf-ask id="read-decision"><h3>Which way?</h3>'
        '<lf-options id="read-choice" choose>'
        '<lf-option id="read-yes">Yes</lf-option>'
        '<lf-option id="read-no">No</lf-option>'
        "</lf-options></lf-ask>",
    )["id"]
    page = open_page(browser, url)
    with sending(page, "the shown body's read"):
        view = open_panel_thread(page, root)
        expect(view.locator("#read-choice")).to_be_visible()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]
    expect(view.locator("#read-choice")).to_be_visible()


def test_a_wide_code_reply_is_acknowledged_once_shown(browser, serve):
    """Content inside a message that scrolls on its own, like a long code line, is part
    of what was shown; it does not hold the message unread."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(
        serve.page_dir,
        "Run this:\n\n```\n" + "leaf page state --json " * 40 + "\n```",
        author="agent",
    )
    page = open_page(browser, url)
    with sending(page, "wide reply read"):
        view = open_panel_thread(page, root)
    code = view.locator(f'.lf-msg[data-lf-message="{root}"] pre').first
    assert code.evaluate("element => element.scrollWidth > element.clientWidth")
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_automatic_read_refusal_keeps_message_unread(browser, serve):
    url = serve(PANEL_PAGE)
    root = thread_model.cmd_comment(
        serve.page_dir,
        None,
        None,
        None,
        "Choose this answer.",
        '<lf-ask id="read-refusal"><h3>Choose</h3>'
        '<lf-options id="read-refusal-options" choose>'
        '<lf-option id="read-refusal-yes">Yes</lf-option>'
        "</lf-options></lf-ask>",
    )["id"]
    page = open_page(browser, url)
    cut = CutOff().hold(page)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    open_panel_thread(page, root)
    holding(page, held, 1, "automatic read")
    request = held.pop()
    response, answer = fetch_whole_state(
        request,
        post_data=json.dumps(
            {"kind": "read", "messages": [{"message": "missing", "version": "missing"}]}
        ),
    )
    assert response.status == 400 and answer["final"] is True
    request.fulfill(response=response)
    rendered(page)
    assert _read_events(serve.page_dir) == []
    assert (
        page.evaluate("""async () => {
      const {readApplication} = await window.__lfCheckApi();
      return readApplication().authoritative.taken;
    }""")
        == answer["state"]["taken"]
    )
    assert take_browser_errors(page) == [
        Finding(
            "console-error",
            values={
                "text": "Failed to load resource: the server responded with a status of 400 (Bad Request)",
                "url": request.request.url,
            },
        )
    ]
    page.unroute("**/api/event")
    cut.restore()
    with sending(page, "read on a new visit"):
        page.evaluate("""() => {
          window.dispatchEvent(new Event('blur'));
          window.dispatchEvent(new Event('focus'));
        }""")
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_modal_blocks_exposure_until_user_returns_to_threads(browser, serve):
    # The modal blocks exposure whatever the panel covers.
    width = 1200
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(
        serve.page_dir, "A short answer behind the dialog.", author="agent"
    )
    page = open_page(browser, url)
    resized(page, width, 900)
    open_threads(page)
    panel_tab(page, "Threads").focus()
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    assert reference.evaluate("element => element.matches(':modal')")
    page.locator(f'.lf-fp-thread[data-lf-key="{root}"]').evaluate(
        "element => element.click()"
    )
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    expect(
        view.locator(f'.lf-msg[data-lf-message="{root}"] .lf-msg-body')
    ).to_be_visible()
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    # The pass the resize set off has run, and whatever it sent has come back.
    rendered(page)
    round_trip(page)
    assert _read_events(serve.page_dir) == []
    with sending(page, "the read once the modal closes"):
        page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_reading_a_thread_moves_nothing_in_it(browser, serve):
    """A read receipt keeps the thread's reading position and content in place.

    The New mark disappears when read. Its metadata wrapper can become empty
    where the preceding message already shows the same age; the remaining content,
    message heads, bodies and controls keep their geometry.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Review this progress.\n\n" + "The complete context matters. " * 250,
        author="agent",
    )
    second = _agent_update_reply(serve.page_dir, root, 2)
    accepted, _ = endpoint_model.accept_event(
        serve.page_dir,
        {"kind": "read", "messages": [{"message": second, "version": second}]},
    )
    assert accepted == 200
    third = _agent_update_reply(serve.page_dir, root, 3)
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1440, "height": 1000})
    card = open_panel_thread(page, root)
    rendered(page)
    card.evaluate(f"card => {{ window.__before = ({_CARD_BOXES})(card); }}")

    accepted, _ = endpoint_model.accept_event(
        serve.page_dir,
        {
            "kind": "read",
            "messages": [{"message": m, "version": m} for m in (root, third)],
        },
    )
    assert accepted == 200
    told(page)
    rendered(page)
    moved = card.evaluate(f"""card => {{
      const after = ({_CARD_BOXES})(card);
      const moved = [];
      for (const [element, box] of window.__before) {{
        if (!after.has(element) || !element.isConnected) continue;
        const now = after.get(element);
        // Compare the metadata's contents below, rather than its wrapper: a
        // wrapper holding only New becomes empty without moving any content.
        if (element.matches('.lf-msg-meta')) continue;
        if (now.some((value, at) => value !== box[at]))
          moved.push(`${{element.tagName}}.${{element.className}} ${{box}} -> ${{now}}`);
      }}
      return moved;
    }}""")
    assert moved == []


def test_first_unread_opens_the_exact_message_and_exposure_acknowledges_it(
    browser, serve
):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "An answer for the user.", author="agent")
    page = open_page(browser, url)

    mark = _on_me_mark(page)
    expect(mark).to_have_attribute("aria-label", "On Me, 1 thread with news")
    expect(mark.locator(".lf-fp-news")).to_be_visible()
    thread_control_width = mark.bounding_box()["width"]
    # With news waiting and nothing on the user, the mark opens Threads, where the
    # thread holding it says so.
    mark.click()
    panel_settled(page, view="threads")
    expect(threads_tab(page).locator(".lf-fp-count")).to_have_text("2")
    row = _thread_row(page, root)
    expect(row).to_have_attribute("data-lf-unread", "")
    with sending(page, "first unread acknowledgement"):
        row.click()
    card = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    expect(card).to_be_visible()
    expect(card.locator(f'.lf-msg[data-lf-message="{root}"]')).not_to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    expect(mark).to_have_attribute("aria-label", "On Me")
    expect(mark.locator(".lf-fp-news")).to_be_hidden()
    assert abs(mark.bounding_box()["width"] - thread_control_width) < 1
    page.reload()
    _expect_news(page, False)


def test_progress_is_never_unread_and_reading_its_answer_reads_only_it(browser, serve):
    """Pending progress pulls the user back to nothing; the answer after it is the
    thread's one unread message, and reading the thread, which the panel draws as its
    card does, the completed progress hidden, acknowledges that answer alone."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "An earlier conversation.")
    root = panel_comment(serve.page_dir, "Check the schedule.")
    progress = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Checking mounts.",
        ephemeral=True,
    )["id"]
    page = open_page(browser, url)
    open_threads(page)
    row = _thread_row(page, root)
    expect(row).to_be_visible()
    expect(row).not_to_have_attribute("data-lf-unread", "")
    _expect_news(page, False)

    answer = thread_model.post_reply(
        serve.page_dir, {"responds": root}, "Both mounts fit."
    )["id"]
    told(page)
    expect(row).to_have_attribute("data-lf-unread", "")
    page.reload()
    wait_until_ready(page)
    card = open_panel_thread(page, root)
    expect(card.locator(f'.lf-msg[data-lf-event="{answer}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-lf-event="{progress}"]')).to_be_hidden()
    _expect_news(page, False)
    round_trip(page)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": answer, "version": answer}
    ]
    page.reload()
    wait_until_ready(page)
    _expect_news(page, False)


def test_oversized_message_needs_contiguous_traversal(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir,
        "\n\n".join(
            f"Paragraph {number}. " + "Complete content matters. " * 20
            for number in range(36)
        ),
        author="agent",
    )
    page = open_page(browser, url)
    _first_unread(page)
    view = page.locator(PANEL_THREAD)
    panel_settled(page, view="thread")
    body = view.locator(f'.lf-msg[data-lf-message="{root}"] .lf-msg-body')
    assert body.bounding_box()["height"] > view.bounding_box()["height"]
    view.evaluate("element => element.scrollTop = element.scrollHeight")
    # The pass the scroll set off has run, and whatever it sent has come back.
    rendered(page)
    round_trip(page)
    assert _read_events(serve.page_dir) == []

    view.evaluate("element => element.scrollTop = 0")
    view.hover()
    list_height = view.evaluate("element => element.clientHeight")
    for _ in range(100):
        if view.evaluate(
            "element => element.scrollTop + element.clientHeight >= element.scrollHeight - 1"
        ):
            break
        page.mouse.wheel(0, list_height / 4)
        page.wait_for_timeout(20)
    else:
        raise AssertionError("mouse wheel did not traverse the complete answer")
    _expect_news(page, False)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_edit_reopens_only_its_new_content_version(browser, serve):
    url = serve(PANEL_PAGE)
    user = panel_comment(serve.page_dir, "The earlier user thread.")
    original = thread_model.cmd_comment(
        serve.page_dir, None, None, None, "Original answer.", None
    )
    root = original["id"]
    page = open_page(browser, url)
    _first_unread(page)
    _expect_news(page, False)
    open_panel_thread(page, user)
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    [edit] = thread_model.cmd_edit(serve.page_dir, root, "Revised answer.")
    told(page)
    _expect_news(page)
    with sending(page, "edited answer read"):
        _first_unread(page)
    _expect_news(page, False)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": edit["id"]}
    ]


def test_an_acknowledgement_neither_waits_for_nor_holds_up_a_gesture(browser, serve):
    """A read acknowledgement is bookkeeping: it creates no work, a gesture made while
    it is in flight goes out beside it, its failure is silent while the gesture's is
    reported, and resolving the thread is itself evidence the user took it in."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "Read this answer.", author="agent")
    page = open_page(browser, url)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    _first_unread(page)
    holding(page, held, 1, "automatic read")
    card = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    message = card.locator(f'.lf-msg[data-lf-message="{root}"]')
    expect(message).not_to_have_class(re.compile(r"(^|\s)lf-unread(\s|$)"))
    expect(message.locator(".lf-msg-sending")).to_have_count(0)
    assert (
        json.loads(page.locator("html").get_attribute("data-lf-traffic"))["pending"]
        == []
    )
    assert page.evaluate(
        "async () => (await window.__lfCheckApi()).readApplication().unresolved.length === 0"
    )

    # Resolving from the thread's view moves the user on to Threads, so the message
    # the refused read leaves unread is no longer on screen to show it.
    page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)").click()
    holding(page, held, 2, "a resolve sent while the read is held")
    assert [route.request.post_data_json["kind"] for route in held] == [
        "read",
        "resolve",
    ]
    held[0].fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused before append"}
    )
    page.unroute("**/api/event")
    held[1].abort()
    round_trip(page)
    told(page)
    _expect_news(page, False)
    assert _read_events(serve.page_dir) == []
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["author"] == "user"
    ] == ["comment", "resolve"]
    assert "Couldn't take this" not in _said(page)
    reported_browser_errors(
        page,
        lambda error: (
            is_problem(error, http_error_console(400))
            and "/api/event" in error.values["url"]
        ),
        lambda error: (
            is_problem(error, "Failed to load resource: net::ERR_FAILED")
            and "/api/event" in error.values["url"]
        ),
    )


@pytest.mark.parametrize("opening", ["notice", "return"])
def test_a_reply_in_a_diff_thread_draws_where_the_user_is_and_waits_elsewhere(
    browser, serve, opening
):
    """A reply landing in the diff thread the user had just written draws at once, as
    in a chat: the user stands on the thread their send left them on, and its reply box
    stays where it stood while the reply takes room above it. Once they leave the
    thread for the file's header before it, the next reply would grow the thread at its
    foot, on screen, and move everything after the diff down the page. It waits behind
    a notice in the thread's control row, which appears without changing the thread's
    height, and stays unread while none of it has shown. A press on the notice
    ("notice") or walking back with t ("return") shows it, and the reply's body, drawn
    inside the widget's shadow tree, is read once shown. Both moves stay inside the
    widget's shadow tree, where the document hears no focus event."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    _select_new_route(page)
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    expect(thread).to_be_visible()
    rendered(page)
    stood = box.bounding_box()["y"]
    thread_model.post_reply(
        serve.page_dir, {"responds": root}, "The route-line answer is ready."
    )
    told(page)
    expect(thread.locator(".lf-msg")).to_have_count(2)
    rendered(page)
    assert box.bounding_box()["y"] == pytest.approx(stood, abs=1)

    box.click()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Shift+Tab")
    assert thread.evaluate(
        """thread => {
          const at = thread.getRootNode().activeElement;
          return Boolean(at) && !thread.contains(at);
        }"""
    ), "Shift+Tab left the widget's shadow tree, so the return proves nothing"
    height = _box_height(thread)
    reply = thread_model.post_reply(
        serve.page_dir, {"parent": root}, "And the old route can go."
    )
    told(page)
    news = thread.locator(":scope > .lf-thread-content").get_by_role(
        "button", name="1 new", exact=True
    )
    expect_preview_words(news, "1 new reply")
    expect(thread.locator(".lf-msg")).to_have_count(2)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)
    assert all(
        message["message"] != reply["id"]
        for event in _read_events(serve.page_dir)
        for message in event["messages"]
    )
    with sending(page, "opened diff reply read"):
        if opening == "notice":
            news.click()
        else:
            page.keyboard.press("t")
        expect(news).to_have_count(0)
        body = thread.locator(f'.lf-msg[data-lf-event="{reply["id"]}"] .lf-msg-body')
        expect(body).to_be_visible()
        assert body.evaluate("element => element.getRootNode() instanceof ShadowRoot")
        body.scroll_into_view_if_needed()
    _expect_news(page, False)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": reply["id"], "version": reply["id"]}
    ]


@pytest.mark.parametrize(
    ("end", "engine"),
    [
        ("opened", "browser"),
        ("walked", "browser"),
        ("onto", "browser"),
        ("pressed", "browser"),
        ("replied", "browser"),
        ("tabbed", "browser"),
        ("opened", "firefox_browser"),
        ("onto", "firefox_browser"),
    ],
)
def test_replies_held_in_a_page_seat_show_when_the_user_turns_to_them(
    request, serve, end, engine
):
    """Replies landing while a seated thread's foot is on screen wait behind one
    notice that counts them, and show together, in the order they came: when the user
    presses the notice, when a t press walks them to the thread, when they press one of
    its messages, and when a press or Shift+Tab takes them into its reply row. What the
    walk, the press or the Tab reached stays where it stood, and the replies push what
    follows down or what precedes up; a turn the user then sends follows the replies it
    answers. A user who stands on the thread ("onto")
    sees them as they come, as in a chat. Nothing before the ending is input, so the
    browser fixture's shift watch also checks that holding the replies moved nothing,
    in Firefox as in Chromium."""
    url = serve(TASK_SEAT_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Which of these can wait until spring?",
            "anchor": {"section": "jobs"},
        },
    )["id"]
    page = open_page(request.getfixturevalue(engine), url)
    thread = page.locator(f'.lf-thread-seat .lf-page-thread[data-lf-thread="{root}"]')
    thread.evaluate(
        """thread => document.scrollingElement.scrollBy({
          top: thread.getBoundingClientRect().top - innerHeight / 3,
          behavior: 'instant'})"""
    )
    if end == "onto":
        # The key before the focus makes the chrome's redraw an answer to input.
        page.keyboard.press("Shift")
        thread.focus()
    height = _box_height(thread)
    replies = []
    for n in (1, 2):
        replies.append(
            append_carried_log_record(
                serve.page_dir,
                {
                    "kind": "reply",
                    "author": "agent",
                    "agent": "Codex",
                    "parent": root,
                    "revision": 1,
                    "text": f"Answer {n}: the gutters can wait, the roof cannot.",
                },
            )["id"]
        )
        told(page)
    news = thread.locator(":scope > .lf-thread-content").get_by_role(
        "button", name="2 new", exact=True
    )
    if end == "onto":
        expect(thread.locator(".lf-msg")).to_have_count(3)
        expect(thread.locator(".lf-thread-news")).to_have_count(0)
        return
    expect(news).to_be_visible()
    expect_preview_words(news, "2 new replies")
    expect(thread.locator(".lf-msg")).to_have_count(1)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)
    # The notice stands after the header's words, in a box of its own, so axe still
    # reads their contrast (`overlapped_words`).
    assert overlapped_words(page) == []

    if end == "opened":
        news.click()
    elif end == "walked":
        # The thread is already shown, so the walk lands on it where it stands.
        stood = thread.bounding_box()["y"]
        page.keyboard.press("t")
        expect(thread).to_be_focused()
        expect(thread.locator(".lf-msg")).to_have_count(3)
        assert thread.bounding_box()["y"] == pytest.approx(stood, abs=1)
    elif end == "pressed":
        words = thread.locator(".lf-msg .lf-msg-body").first
        stood = words.bounding_box()["y"]
        words.click()
        expect(thread.locator(".lf-msg")).to_have_count(3)
        assert words.bounding_box()["y"] == pytest.approx(stood, abs=1)
    elif end == "replied":
        box = thread.locator(":scope > .lf-thread-reply leaf-text")
        stood = box.bounding_box()["y"]
        box.click()
        expect(thread.locator(".lf-msg")).to_have_count(3)
        # Chrome hides a shift for half a second after a click, so the watch can't see
        # the box leave the pointer.
        assert box.bounding_box()["y"] == pytest.approx(stood, abs=1)
        write(box, "Then the roof first.")
        with sending(page, "the user's reply"):
            page.keyboard.press("Enter")
    elif end == "tabbed":
        # The seat's comment box stands below the thread, so Shift+Tab from it arrives
        # in the thread's reply row, which the replies draw above.
        page.locator(".lf-thread-seat > .lf-say leaf-text").click()
        row = thread.locator(":scope > .lf-thread-reply")
        stood = row.bounding_box()["y"]
        page.keyboard.press("Shift+Tab")
        expect(thread.locator(".lf-msg")).to_have_count(3)
        assert row.bounding_box()["y"] == pytest.approx(stood, abs=1)
    shown = thread.locator(".lf-msg")
    expect(shown).to_have_count(4 if end == "replied" else 3)
    expect(news).to_have_count(0)
    events = shown.evaluate_all("turns => turns.map(turn => turn.dataset.lfEvent)")
    assert events[:3] == [root, *replies]
    if end == "replied":
        expect(shown.last).to_contain_text("Then the roof first.")


@pytest.mark.parametrize("under_panel", [True, False])
def test_a_page_seat_the_open_panel_stands_over_is_not_read(
    browser, serve, under_panel
):
    """Exposure counts a message read once all of it has been shown. The open panel's
    view stands over the window's foot, so an answer in a page-side seat that reaches
    under it has not been shown whole, however much of it is clear: scrolled so the
    diff's thread outlet runs under the open Threads view, it earns no receipt until the
    view closes. Scrolled clear above it, the same answer is read with the view open.
    Threads lists rows rather than messages, so the page seat is the only copy in view.
    The answer arrives below the window's foot, where it is drawn at once."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    _select_new_route(page)
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    # The user lets go of the thread the send left them on and scrolls back up, so the
    # whole thread stands below the window and the answer joining it moves nothing they
    # see: it is drawn at once rather than held.
    page.evaluate(RELEASE_FOCUS)
    page.evaluate(
        """thread => scrollBy(0, thread.getBoundingClientRect().top - innerHeight - 40)""",
        page.locator("lf-diff .lf-page-thread").element_handle(),
    )
    open_threads(page)
    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The route-line answer is ready.",
    )
    told(page)
    body = page.locator(
        f'lf-diff .lf-diff-thread-outlet .lf-msg[data-lf-event="{reply["id"]}"]'
        " .lf-msg-body"
    )
    expect(body).to_have_count(1)
    # The answer's foot 20px under the open view's top edge, or 20px above it.
    page.evaluate(
        """([body, card, under]) => scrollBy(0, body.getBoundingClientRect().bottom
            - card.getBoundingClientRect().top + (under ? -20 : 20))""",
        [
            body.element_handle(),
            page.locator(".lf-fp-card").element_handle(),
            under_panel,
        ],
    )
    read = [{"message": reply["id"], "version": reply["id"]}]

    def receipt():
        return any(event["messages"] == read for event in _read_events(serve.page_dir))

    body_bottom = body.evaluate("element => element.getBoundingClientRect().bottom")
    panel_top = page.locator(".lf-fp-card").bounding_box()["y"]
    assert (body_bottom > panel_top) == under_panel, (
        f"the fixture put the seat's foot at {body_bottom} against the panel's "
        f"{panel_top}, so it does not test what it names"
    )
    if under_panel:
        # The pass the scroll set off has run, and whatever it sent has come back.
        rendered(page)
        round_trip(page)
        assert not receipt(), "a message partly under the open panel was marked read"
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
        rendered(page)
        round_trip(page)
        assert receipt(), "the view closing off the answer set off no reading"
        return
    deadline = time.monotonic() + SERVED_TIMEOUT_MS / 1000
    while not receipt() and time.monotonic() < deadline:
        page.wait_for_timeout(100)
    assert receipt(), "the answer shown whole was never marked read"


import pytest
