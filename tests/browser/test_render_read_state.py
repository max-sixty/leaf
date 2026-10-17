"""Durable user acknowledgement through the rendered Thread surfaces."""

import json
import threading

import pytest
from interact_support import STATED_TIMEOUT, append_carried_log_record
from journeys.test_render_read_state import (
    _CARD_BOXES,
    TASK_SEAT_PAGE,
    _agent_turn,
    _agent_update_reply,
    _box_height,
    _read_events,
    _seat_comment,
    _to_upper_third,
)
from leaf import event_endpoint as endpoint_model
from leaf import http as http_model
from leaf import thread as thread_model
from leaf.findings import Finding
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    PANEL_THREAD,
    CutOff,
    _traffic,
    heard_back,
    holding,
    open_page,
    panel_settled,
    resized,
    round_trip,
    sending,
    take_browser_errors,
    told,
    write,
)

from browser.threads import open_panel_thread


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
        # The user stands on the summary as the reply comes. The key before the focus
        # makes the shortcut bar's redraw an answer to input.
        page.keyboard.press("Shift")
        summary.focus()
    height = _box_height(resolved)
    second = _agent_turn(serve.page_dir, root, "The roof cannot wait after all.")
    told(page)
    expect(summary).to_have_text("Resolved · 1 · Reopened · 1 new reply")
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
        ("box", "standing"),
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
    standing in the first-message box keeps it: the thread shows above the box, which
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
    if end == "standing":
        box.focus()
        top = box.evaluate("box => box.getBoundingClientRect().top")
    started = _seat_comment(serve.page_dir, "agent", "Should the gutters wait too?")
    told(page)
    if end == "standing":
        expect(threads).to_have_count(1)
        expect(box).to_be_focused()
        assert box.evaluate("box => box.getBoundingClientRect().top") == pytest.approx(
            top, abs=0.5
        )
        return
    row = (
        seat.locator(":scope > .lf-seat-news")
        if beside == "box"
        else threads.first.locator(":scope > .lf-thread-content > .lf-thread-controls")
    )
    news = row.get_by_role("button", name="1 new thread")
    expect(news).to_be_visible()
    expect(threads).to_have_count(1 if earlier else 0)
    assert _box_height(seat) == pytest.approx(height, abs=0.5)

    if end == "opened":
        # The notice as a Tab stop of its own, in keyboard modality. The key before the
        # focus makes the shortcut bar's redraw for the new stop an answer to input.
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
    page.locator(".lf-fp-threads").click()
    panel_settled(page, view="threads")
    page.locator(".lf-fp-threads").focus()
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
    """A read receipt moves nothing in the thread's view in the panel."""
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
        if ([0, 1, 2, 3].some(at => now[at] !== box[at]))
          moved.push(`${{element.tagName}}.${{element.className}} ${{box}} -> ${{now}}`);
      }}
      return moved;
    }}""")
    assert moved == []
