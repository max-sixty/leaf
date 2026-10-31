"""Durable user acknowledgement through the rendered Thread surfaces."""

import json
import re
import threading
import time

import pytest
from interact_support import STATED_TIMEOUT, append_carried_log_record
from journeys.test_render_read_state import (
    _CARD_BOXES,
    ROUTE_LINE,
    TASK_SEAT_PAGE,
    _agent_turn,
    _agent_update_reply,
    _box_height,
    _expect_news,
    _first_unread,
    _on_me_mark,
    _read_events,
    _said,
    _seat_comment,
    _select_new_route,
    _thread_row,
    _to_upper_third,
)
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_cases_layout import overlapped_words
from render_cases_navigation import source_revision
from render_cases_widgets import LONG_LINE_DIFF_PAGE, MULTI_HUNK_PATCH
from render_harness import (
    PANEL,
    PANEL_THREAD,
    RELEASE_FOCUS,
    CutOff,
    _traffic,
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
    code = view.locator(f'.lf-msg[data-message="{root}"] pre').first
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
    response = request.fetch(
        post_data=json.dumps(
            {"kind": "read", "messages": [{"message": "missing", "version": "missing"}]}
        )
    )
    assert response.status == 400 and response.json()["final"] is True
    request.fulfill(response=response)
    rendered(page)
    assert _read_events(serve.page_dir) == []
    assert (
        page.evaluate("""async () => {
      const {readApplication} = await window.__lfCheckApi();
      return readApplication().authoritative.taken;
    }""")
        == response.json()["state"]["taken"]
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


@pytest.mark.parametrize("pointer", ["fine", "coarse"])
def test_a_reopening_in_a_page_seat_waits_in_its_resolved_summary(
    browser, serve, pointer
):
    """An agent's reply to a resolved thread reopens it. Drawn at once, the reopened
    thread would leave the seat's closed Resolved disclosure and grow under the reader:
    its turns and its reply box pushed the page after it down. It stays folded there,
    and the disclosure's summary says what is waiting, at the summary's height under
    either pointer. A tap on the summary, or Enter on it, opens it, and the thread
    shows open in the disclosure's place, with the new turn after the earlier ones, a
    reply box, and the keyboard on it. Nothing before the opening is input, so the
    shift watch checks that the hold moved nothing."""
    context = (
        browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        if pointer == "coarse"
        else None
    )
    url = serve(TASK_SEAT_PAGE)
    root = _seat_comment(serve.page_dir, "user", "Which of these can wait?")
    first = _agent_turn(serve.page_dir, root, "The gutters can wait.")
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": root, "revision": 1},
    )
    page = open_page(browser, url, context=context)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    resolved = page.locator(".lf-resolved-threads")
    summary = resolved.locator(":scope > summary")
    expect(summary).to_have_text("Resolved · 1")
    expect(thread).to_be_hidden()
    _to_upper_third(resolved)
    if pointer == "fine":
        # The user is located on the summary as the reply comes. The key before the focus
        # makes the chrome's redraw an answer to input.
        page.keyboard.press("Shift")
        summary.focus()
    height = _box_height(resolved)
    second = _agent_turn(serve.page_dir, root, "The roof cannot wait after all.")
    told(page)
    expect(summary).to_have_text("Resolved · 1 · 2 new")
    expect(thread).to_be_hidden()
    assert _box_height(resolved) == pytest.approx(height, abs=0.5)

    if pointer == "coarse":
        summary.tap()
    else:
        page.keyboard.press("Enter")
    expect(resolved).to_have_count(0)
    expect(thread).to_be_focused()
    shown = thread.locator(".lf-msg")
    expect(shown).to_have_count(3)
    assert shown.evaluate_all("turns => turns.map(turn => turn.dataset.event)") == [
        root,
        first,
        second,
    ]
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_be_visible()


@pytest.mark.parametrize(
    ("beside", "end"),
    [
        ("box", "opened"),
        ("box", "focused"),
        ("thread", "opened"),
        ("thread", "started"),
    ],
)
def test_a_thread_the_agent_starts_in_a_page_seat_waits_in_the_row_it_would_follow(
    browser, serve, beside, end
):
    """A thread the agent starts in a seat lands at the seat's foot, and drawn at once
    it pushed the page after the seat down. It waits behind a notice in a row of fixed
    size: the control row of the seat's last thread, or, in a seat that draws no thread,
    a row standing in place of the first-message row at that row's height, since the row
    has no room beside its box. It shows when the user opens the notice from the
    keyboard and when they start a thread of their own, which shows after it. A user
    focused in the first-message box keeps it: the thread shows above the box, which
    stays where it stood. Nothing before the ending is input, so the shift watch checks
    that the hold moved nothing."""
    # The notice's previous Tab stop stays beside the seat. Returning to the page's
    # Skip control scrolls the seat away, which correctly releases its held news.
    source = TASK_SEAT_PAGE.replace(
        "<lf-test-plan", '<button type="button">Before jobs</button><lf-test-plan', 1
    )
    url = serve(source)
    earlier = (
        _seat_comment(serve.page_dir, "user", "Which of these can wait?")
        if beside == "thread"
        else None
    )
    page = open_page(browser, url)
    seat = page.locator('.lf-thread-seat[data-lf-thread-seat="jobs"]')
    box = seat.locator(":scope > .lf-say leaf-text")
    threads = seat.locator(":scope > .lf-page-thread")
    _to_upper_third(seat)
    height = _box_height(seat)
    if end == "focused":
        box.focus()
        top = box.evaluate("box => box.getBoundingClientRect().top")
    started = _seat_comment(serve.page_dir, "agent", "Should the gutters wait too?")
    told(page)
    if end == "focused":
        expect(threads).to_have_count(1)
        expect(box).to_be_focused()
        assert box.evaluate("box => box.getBoundingClientRect().top") == pytest.approx(
            top, abs=0.5
        )
        return
    row = (
        seat.locator(":scope > .lf-seat-news")
        if beside == "box"
        else threads.first.locator(":scope > .lf-thread-content")
    )
    news = row.get_by_role("button", name="1 new thread")
    expect(news).to_be_visible()
    expect(threads).to_have_count(1 if earlier else 0)
    assert _box_height(seat) == pytest.approx(height, abs=0.5)

    if end == "opened":
        # The notice as a Tab stop of its own, in keyboard modality. The key before the
        # focus makes the chrome's redraw for the new stop an answer to input.
        page.keyboard.press("Shift")
        news.focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        expect(news).to_be_focused()
        page.keyboard.press("Enter")
    else:
        write(box, "And the shed roof?")
        with sending(page, "the user's thread"):
            page.keyboard.press("Enter")
    expect(news).to_have_count(0)
    expect(box).to_be_visible()
    keys = [key for key in (earlier, started) if key]
    expect(threads).to_have_count(len(keys) + (end == "started"))
    shown = threads.evaluate_all("threads => threads.map(t => t.dataset.thread)")
    assert shown[: len(keys)] == keys
    if end == "started":
        expect(threads.last).to_contain_text("And the shed roof?")
    if end == "opened":
        # The notice goes with what it held, and the keyboard lands on the thread it
        # stood in, or on the thread it showed.
        expect(threads.first if earlier else threads.last).to_be_focused()


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
    page.locator(f'.lf-fp-thread[data-key="{root}"]').evaluate(
        "element => element.click()"
    )
    view = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
    expect(view.locator(f'.lf-msg[data-message="{root}"] .lf-msg-body')).to_be_visible()
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(100)
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
        dict,
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
        dict,
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
    expect(mark).to_have_attribute("aria-label", "On me, 1 thread with news")
    expect(mark).to_have_attribute("title", "On me, 1 thread with news")
    expect(mark.locator(".lf-fp-news")).to_be_visible()
    thread_control_width = mark.bounding_box()["width"]
    # With news waiting and nothing on the user, the mark opens Threads, where the
    # thread holding it says so.
    mark.click()
    panel_settled(page, view="threads")
    expect(threads_tab(page).locator(".lf-fp-count")).to_have_text("2")
    row = _thread_row(page, root)
    expect(row).to_have_attribute("data-unread", "")
    with sending(page, "first unread acknowledgement"):
        row.click()
    card = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
    expect(card).to_be_visible()
    expect(card.locator(f'.lf-msg[data-message="{root}"]')).not_to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    expect(mark).to_have_attribute("aria-label", "On me")
    expect(mark).to_have_attribute("title", "On me")
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
    expect(row).not_to_have_attribute("data-unread", "")
    _expect_news(page, False)

    answer = thread_model.post_reply(
        serve.page_dir, {"responds": root}, "Both mounts fit."
    )["id"]
    told(page)
    expect(row).to_have_attribute("data-unread", "")
    page.reload()
    wait_until_ready(page)
    card = open_panel_thread(page, root)
    expect(card.locator(f'.lf-msg[data-event="{answer}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-event="{progress}"]')).to_be_hidden()
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
    body = view.locator(f'.lf-msg[data-message="{root}"] .lf-msg-body')
    assert body.bounding_box()["height"] > view.bounding_box()["height"]
    view.evaluate("element => element.scrollTop = element.scrollHeight")
    page.wait_for_timeout(100)
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
    card = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
    message = card.locator(f'.lf-msg[data-message="{root}"]')
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
    page.locator(".lf-fp-settle").click()
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
def test_a_reply_held_in_a_diff_thread_is_read_once_the_keyboard_opens_it(
    browser, serve, opening
):
    """A reply landing in the diff thread the user had just written grew the thread at
    its foot, on screen, and everything after the diff moved down the page. It waits
    behind a notice in the thread's control row, which appears without changing the
    thread's height, and stays unread while none of it has shown. The keyboard reaches
    the notice from the thread and opens it, and the reply's body, drawn inside the
    widget's shadow tree, is read once shown. Leaving the thread for the file's header
    before it and walking back with t ("return") arrives at the thread, so it shows
    there too: both moves stay inside the widget's shadow tree, where the document hears
    no focus event. The browser fixture's shift watch holds the rest: the reply is
    news."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    # Selection opening is outstanding rendering when the native release returns,
    # even if a loaded event loop has not yet stood its response field.
    page.evaluate("""() => {
      window.selectionRelease = [];
      document.addEventListener('mouseup', event => {
        if (!event.composedPath().some(node => node.matches?.('lf-diff'))) return;
        queueMicrotask(() => selectionRelease.push({
          words: getSelection().toString(),
          settled: Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean),
        }));
      }, {once: true});
    }""")
    _select_new_route(page)
    assert page.evaluate("window.selectionRelease") == [
        {"words": "new route", "settled": False}
    ]
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    expect(thread).to_be_visible()
    height = _box_height(thread)
    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The route-line answer is ready.",
    )
    told(page)
    news = thread.locator(":scope > .lf-thread-content").get_by_role(
        "button", name="1 new reply"
    )
    expect(news).to_be_visible()
    expect(thread.locator(".lf-msg")).to_have_count(1)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)
    assert not _read_events(serve.page_dir)

    # A press into the reply box asks for the box, so the reply stays held under it.
    thread.locator(":scope > .lf-thread-reply leaf-text").click()
    expect(news).to_be_visible()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    if opening == "return":
        page.keyboard.press("Shift+Tab")
        assert thread.evaluate(
            """thread => {
              const at = thread.getRootNode().activeElement;
              return Boolean(at) && !thread.contains(at);
            }"""
        ), "Shift+Tab left the widget's shadow tree, so the return proves nothing"
        expect(news).to_be_visible()
        opens = "t"
    else:
        page.keyboard.press("Tab")
        expect(news).to_be_focused()
        opens = "Enter"
    with sending(page, "opened diff reply read"):
        page.keyboard.press(opens)
        expect(news).to_have_count(0)
        if opening == "notice":
            expect(thread).to_be_focused()
        body = thread.locator(f'.lf-msg[data-event="{reply["id"]}"] .lf-msg-body')
        expect(body).to_be_visible()
        assert body.evaluate("element => element.getRootNode() instanceof ShadowRoot")
        body.scroll_into_view_if_needed()
    _expect_news(page, False)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": reply["id"], "version": reply["id"]}
    ]


@pytest.mark.parametrize("end", ["opened", "walked", "onto", "replied"])
def test_replies_held_in_a_page_seat_show_when_the_user_turns_to_them(
    browser, serve, end
):
    """Replies landing while a seated thread's foot is on screen wait behind one
    notice that counts them, and show together, in the order they came: when the user
    presses the notice, when a t press walks them to the thread, when they send a turn
    of their own, which answers the replies and so follows them. A t press
    onto the thread they already stand in ("onto") is a stay, and the replies wait on.
    Nothing before the ending is input, so the browser fixture's shift watch also checks
    that holding the replies moved nothing."""
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
    page = open_page(browser, url)
    thread = page.locator(f'.lf-thread-seat .lf-page-thread[data-thread="{root}"]')
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
        "button", name="2 new replies"
    )
    expect(news).to_be_visible()
    expect(thread.locator(".lf-msg")).to_have_count(1)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)
    # The notice stands after the header's words, in a box of its own, so axe still
    # reads their contrast (`overlapped_words`).
    assert overlapped_words(page) == []

    if end == "opened":
        news.click()
    elif end == "walked":
        page.keyboard.press("t")
    elif end == "onto":
        page.keyboard.press("t")
        # The walk lands on the thread in the margin's card, which is the same thread.
        card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        expect(card).to_be_focused()
        rendered(page)
        expect(news).to_be_visible()
        expect(thread.locator(".lf-msg")).to_have_count(1)
        return
    elif end == "replied":
        write(
            thread.locator(":scope > .lf-thread-reply leaf-text"),
            "Then the roof first.",
        )
        with sending(page, "the user's reply"):
            page.keyboard.press("Enter")
    shown = thread.locator(".lf-msg")
    expect(shown).to_have_count(4 if end == "replied" else 3)
    expect(news).to_have_count(0)
    events = shown.evaluate_all("turns => turns.map(turn => turn.dataset.event)")
    assert events[:3] == [root, *replies]
    if end == "replied":
        expect(shown.last).to_contain_text("Then the roof first.")


def test_a_walk_to_a_thread_a_diff_line_holds_lands_in_its_outlet(browser, serve):
    """A second thread the agent starts on a diff line the user's thread stands on waits
    behind that thread's notice, undrawn. A t walk to it shows it in the line's outlet
    and lands there, rather than opening Threads for a thread the page has no node
    for."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    _select_new_route(page)
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    comment = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{comment["id"]}"]')
    expect(thread).to_be_visible()
    second = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "text": "And should the alias warn?",
            "anchor": comment["anchor"],
        },
    )["id"]
    told(page)
    news = thread.locator(":scope > .lf-thread-content").get_by_role(
        "button", name="1 new thread"
    )
    expect(news).to_be_visible()
    landed = page.locator(f'lf-diff .lf-page-thread[data-thread="{second}"]')
    expect(landed).to_have_count(0)
    page.keyboard.press("t")
    expect(landed).to_be_visible()
    assert landed.evaluate(
        "thread => thread.contains(thread.getRootNode().activeElement)"
    ), "the walk did not land in the outlet"
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
    expect(news).to_have_count(0)


@pytest.mark.parametrize("opening", ["Enter", "programmatic"])
def test_a_reopening_in_a_folded_diff_thread_waits_in_its_summary(
    browser, serve, opening
):
    """A resolved diff thread stands folded in its outlet's Resolved disclosure. An
    agent's reply that reopened it unfolded it under the reader, and every diff line
    after it moved down by the whole thread. It stays folded, the disclosure's summary
    says what is waiting, and the keyboard, which the resolve left on that summary,
    opens it to the thread, open in the disclosure's place, with the new turn."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    _select_new_route(page)
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    resolved = page.locator("lf-diff .lf-resolved-threads")
    summary = resolved.locator(":scope > summary")
    # The send leaves the user on the thread, and Resolve is its first stop.
    page.keyboard.press("Tab")
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    expect(summary).to_be_focused()
    expect(summary).to_have_text("Resolved · 1")
    expect(thread).to_be_hidden()
    _to_upper_third(resolved)
    height = _box_height(resolved)
    # Resolving answered the comment, so the agent's turn is one nothing asked for.
    reply = thread_model.post_reply(
        serve.page_dir, {"parent": root}, "The route stays."
    )
    told(page)
    expect(summary).to_have_text("Resolved · 1 · 2 new")
    expect(resolved).not_to_have_attribute("open", "")
    assert _box_height(resolved) == pytest.approx(height, abs=0.5)

    # A native open-attribute checkpoint runs before paint. The first opened body
    # must already draw the released news, the thread reopened in the disclosure's
    # place, rather than the older resolved layout inside it.
    resolved.evaluate("""node => {
      window.openedResolved = null;
      new MutationObserver(() => {
        if (!node.open || window.openedResolved) return;
        window.openedResolved = {
          shown: node.isConnected,
          threads: node.querySelectorAll('.lf-page-thread').length,
        };
      }).observe(node, {attributeFilter:['open']});
    }""")
    if opening == "programmatic":
        resolved.evaluate("""node => {
          const open = document.createElement('button');
          open.textContent = 'Open disclosure';
          open.style.cssText = 'position:fixed;left:0;top:80px;z-index:9999';
          open.onclick = () => {node.open = true};
          document.body.append(open);
        }""")
        page.get_by_role("button", name="Open disclosure", exact=True).click()
    else:
        page.keyboard.press(opening)
    assert page.evaluate("openedResolved") == {"shown": False, "threads": 0}
    expect(resolved).to_have_count(0)
    if opening == "Enter":
        expect(thread).to_be_focused()
    expect(thread.locator(".lf-msg")).to_have_count(2)
    expect(thread.locator(f'.lf-msg[data-event="{reply["id"]}"]')).to_be_visible()
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_be_visible()


@pytest.mark.parametrize(
    "end",
    [
        "keyboard",
        "settled",
        "replied",
        "started",
        "left",
        "focused",
        "selecting",
        "returned",
    ],
)
def test_a_thread_the_agent_starts_on_a_bare_diff_line_waits_at_its_margin_marker(
    browser, serve, end
):
    """A thread the agent starts on a diff line with no thread opened a new outlet under
    the line, and every line and paragraph after it moved down under the reader. No row
    the diff draws can say it waits, so the diff does not draw it: it stands in the
    margin, as any thread the diff does not place does, and its marker is the notice.
    Clicking or pressing Enter on the marker shows the thread under its line
    and lands on it, and the marker stays its notice when the agent settles it. It also
    shows when the user replies in it from the margin's card, when they start a
    thread on the same line, which shows after it, and when
    they scroll the line below the window, unless they stand in its card, writing there
    or holding a selection of its words, which stays with them. Returning from a hidden tab reveals current messages while
    preserving that composing margin card. The news lands well past Chrome's half
    second of recent input, so the shift watch checks that holding the thread moved
    nothing."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    line = page.locator(f"lf-diff [data-lf-datum='{ROUTE_LINE}']")
    _to_upper_third(line)
    after = page.locator("#tail-0")
    top = after.evaluate("node => node.getBoundingClientRect().top")
    page.wait_for_function(
        "at => performance.now() - at > 600", arg=page.evaluate("performance.now()")
    )
    held = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "text": "Should the old route name stay as an alias?",
            "anchor": {
                "section": "patch",
                "datum": ROUTE_LINE,
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    told(page)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    expect(marker).to_be_visible()
    outlet = page.locator("lf-diff .lf-diff-thread-outlet")
    expect(outlet).to_have_count(0)
    assert after.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        top, abs=0.5
    )

    if end == "settled":
        # The agent settling its thread is news too, and the marker stays its notice.
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "resolve",
                "author": "agent",
                "agent": "Codex",
                "parent": held,
                "revision": 1,
            },
        )
        told(page)
        expect(outlet).to_have_count(0)
        expect(marker).to_be_visible()
        marker.click()
    elif end == "returned":
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        box = card.locator(":scope > .lf-thread-reply leaf-text")
        words = "Only if the old name stays usable."
        write(box, words)
        box.evaluate("""box => {
          box.setSelectionRange(8, 8);
          window.__returnDiffEditor = box;
        }""")
        page.evaluate("""() => {
          window.__lfTestVisibility = 'hidden';
          Object.defineProperty(document, 'visibilityState', {
            configurable: true, get: () => window.__lfTestVisibility,
          });
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        answer = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "parent": held,
                "text": "The old name will stay usable.",
            },
        )
        with page.expect_request("**/api/news"):
            page.evaluate("""() => {
              window.__lfTestVisibility = 'visible';
              document.dispatchEvent(new Event('visibilitychange'));
            }""")
        told(page)
        rendered(page)
        expect(outlet).to_have_count(0)
        expect(card.locator(f'.lf-msg[data-event="{answer["id"]}"]')).to_be_visible()
        expect(card.locator(".lf-thread-news")).to_have_count(0)
        expect(box).to_be_focused()
        expect(box).to_have_js_property("value", words)
        assert box.evaluate("""field => field === window.__returnDiffEditor
          && field.selectionStart === 8 && field.selectionEnd === 8""")
        return
    elif end == "focused":
        # A user writing in the margin's card keeps it as they scroll the line away.
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        box = card.locator(":scope > .lf-thread-reply leaf-text")
        write(box, "Only if")
        line.evaluate(
            """line => document.scrollingElement.scrollBy({
              top: line.getBoundingClientRect().top - innerHeight - 400,
              behavior: 'instant'})"""
        )
        page.evaluate(
            "() => new Promise(done => requestAnimationFrame("
            "() => requestAnimationFrame(done)))"
        )
        expect(box).to_be_focused()
        expect(outlet).to_have_count(0)
        # A second thread on the line, off screen, shows; the one the user writes in
        # stays with them in the card.
        second = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "text": "And should the alias warn?",
                "anchor": {
                    "section": "patch",
                    "datum": ROUTE_LINE,
                    "source": "review-patch",
                    "source_revision": source_revision(serve.page_dir, "review-patch"),
                },
            },
        )["id"]
        told(page)
        expect(outlet.locator(".lf-page-thread")).to_have_count(1)
        expect(outlet.locator(".lf-page-thread")).to_have_attribute(
            "data-thread", second
        )
        expect(box).to_be_focused()
        return
    elif end == "selecting":
        # A selection of the card's words keeps that current location too, with focus left on a
        # control elsewhere.
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        words = card.locator(".lf-msg-text").first
        words.evaluate(
            """node => { const range = document.createRange();
            range.selectNodeContents(node); const selection = getSelection();
            selection.removeAllRanges(); selection.addRange(range); }"""
        )
        _on_me_mark(page).focus()
        # The user scrolls the line away, a gesture of theirs the page answers.
        page.mouse.move(40, 400)
        page.mouse.wheel(
            0,
            line.evaluate(
                "line => line.getBoundingClientRect().top - innerHeight - 400"
            ),
        )
        page.wait_for_function(
            "line => line.getBoundingClientRect().top > innerHeight",
            arg=line.element_handle(),
        )
        page.evaluate(
            "() => new Promise(done => requestAnimationFrame("
            "() => requestAnimationFrame(done)))"
        )
        expect(outlet).to_have_count(0)
        assert page.evaluate("getSelection().toString()") == (
            "Should the old route name stay as an alias?"
        )
        return
    elif end == "keyboard":
        # The marker as the rail's Tab stop, in keyboard modality. The key before the
        # focus makes the chrome's redraw for the stop an answer to input.
        page.keyboard.press("Shift")
        marker.focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        expect(marker).to_be_focused()
        assert marker.evaluate("marker => marker.matches(':focus-visible')")
        page.keyboard.press("Enter")
    elif end == "replied":
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        write(
            card.locator(":scope > .lf-thread-reply leaf-text"), "Yes, for one release."
        )
        with sending(page, "the user's reply"):
            page.keyboard.press("Enter")
    elif end == "started":
        _select_new_route(page)
        write(page.locator(".lf-composer leaf-text"), "And the handler's name?")
        with sending(page, "the user's thread"):
            page.keyboard.press("ControlOrMeta+Enter")
    else:
        line.evaluate(
            """line => document.scrollingElement.scrollBy({
              top: line.getBoundingClientRect().top - innerHeight - 400,
              behavior: 'instant'})"""
        )
    threads = outlet.locator(".lf-page-thread")
    expect(threads).to_have_count(2 if end == "started" else 1)
    expect(threads.first).to_have_attribute("data-thread", held)
    expect(marker).to_have_count(0)
    if end == "started":
        expect(threads.last).to_contain_text("And the handler's name?")
    if end == "replied":
        expect(threads.first).to_contain_text("Yes, for one release.")
    if end in ("keyboard", "settled"):
        # The marker goes with what it held, and the user lands on the thread it showed,
        # a settled one in its outlet's Resolved disclosure, which opens to show it.
        expect(threads.first).to_be_focused()
    if end == "settled":
        expect(outlet.locator(".lf-resolved-threads")).to_have_attribute("open", "")


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
        f'lf-diff .lf-diff-thread-outlet .lf-msg[data-event="{reply["id"]}"]'
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
        # Long enough for an observation pass to have sent a receipt had it counted.
        page.wait_for_timeout(1500)
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
