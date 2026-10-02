"""Durable user acknowledgement through the rendered Thread surfaces."""

import json
import re
import threading
import time

import pytest
from leaf import data as data_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import http as http_model
from leaf import thread as thread_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_cases_navigation import source_revision
from render_cases_widgets import LONG_LINE_DIFF_PAGE, MULTI_HUNK_PATCH
from render_harness import (
    Traffic,
    _traffic,
    heard_back,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    round_trip,
    select,
    sending,
    take_browser_errors,
    told,
    write,
)


def _read_events(page_dir):
    return [
        event for event in events_model.read_events(page_dir) if event["kind"] == "read"
    ]


def _select_new_route(page):
    """Drag across "new route" on the diff's routes.py line 201, as a user selects it."""
    row = page.locator('lf-diff [data-lf-datum=\'["app/routes.py","new",201]\']')
    row.scroll_into_view_if_needed()
    points = row.evaluate("""element => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const nodes = [], starts = [];
      let text = '';
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        starts.push(text.length); nodes.push(node); text += node.data;
      }
      const start = text.indexOf('new route');
      if (start < 0) throw new Error('diff phrase missing');
      const glyph = offset => {
        const index = starts.findLastIndex(value => value <= offset);
        const range = document.createRange();
        range.setStart(nodes[index], offset - starts[index]);
        range.setEnd(nodes[index], offset - starts[index] + 1);
        return range.getBoundingClientRect();
      };
      const first = glyph(start), last = glyph(start + 'new route'.length - 1);
      return [[first.left, first.top + first.height / 2],
              [last.right, last.top + last.height / 2]];
    }""")
    select(page, *points)


def _agent_metric_reply(page_dir, root, number, for_event=None):
    return thread_model.cmd_reply(
        page_dir,
        root,
        f"Update {number}.",
        (
            f'<lf-metric id="read-update-{number}" value="{number}">'
            "Completed steps</lf-metric>"
        ),
        for_event=for_event,
        when_settled="post",
    )["id"]


def test_unread_summary_keeps_hidden_original_unread(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Can we review this?", author="user")
    first = _agent_metric_reply(serve.page_dir, root, 1, for_event=root)
    user = events_model.append_event(
        serve.page_dir,
        {"kind": "reply", "author": "user", "parent": root, "text": "One more detail."},
    )["id"]
    middle = _agent_metric_reply(serve.page_dir, root, 2, for_event=user)
    _agent_metric_reply(serve.page_dir, root, 3)
    accepted, _ = endpoint_model.accept_event(
        serve.page_dir,
        {
            "kind": "read",
            "messages": [
                {"message": first, "version": first},
                {"message": middle, "version": middle},
            ],
        },
        dict,
    )
    assert accepted == 200
    thread_model.cmd_edit(serve.page_dir, first, "Revised update 1.")
    thread_model.cmd_summarize(
        serve.page_dir, first, middle, "The first two updates in brief."
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    checkpoint = card.locator(".lf-thread-checkpoint")
    expect(checkpoint.locator(".lf-summary-unread")).to_contain_text(
        "1 unread original"
    )
    expect(checkpoint.locator(".lf-summary-originals")).to_be_hidden()
    expect(card.locator(".lf-unread-label")).to_have_count(0)


def test_first_unread_reveals_resolved_summary_original(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Is this metric settled?", author="user")
    answer = _agent_metric_reply(serve.page_dir, root, 4, for_event=root)
    thread_model.cmd_summarize(
        serve.page_dir, root, answer, "The earlier metric discussion."
    )
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_be_hidden()
    page.locator(".lf-first-unread").click()
    expect(card).to_be_visible()
    expect(card.locator(".lf-thread-checkpoint")).to_have_attribute(
        "data-expanded", "true"
    )
    expect(card.locator(f'.lf-msg[data-mid="{answer}"]')).to_be_focused()
    expect(page.locator(".lf-first-unread")).to_be_hidden()


def test_first_unread_opens_the_exact_message_and_exposure_acknowledges_it(
    browser, serve
):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "An answer for the user.", author="agent")
    page = open_page(browser, url)

    expect(page.locator(".lf-first-unread")).to_have_text("Next unread")
    expect(page.locator(".lf-first-unread")).to_have_attribute(
        "aria-label", "1 unread message. Go to first unread message"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 2")
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-label", "Open threads: 2, 1 unread thread"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "data-unread-threads", ""
    )
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "title", "Show or hide the thread panel; 1 unread thread (g T)"
    )
    thread_control_width = page.locator(".lf-threads-toggle").bounding_box()["width"]
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card.locator(".lf-thread-unread")).to_have_text("1 unread")
    page.locator(".lf-first-unread").click()
    expect(card).to_have_attribute("open", "")
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_be_focused()
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).not_to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    expect(page.locator(".lf-threads-toggle")).not_to_have_attribute(
        "data-unread-threads", ""
    )
    expect(page.locator(".lf-threads-toggle")).not_to_have_attribute(
        "aria-label", re.compile("unread")
    )
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "title", "Show or hide the thread panel (g T)"
    )
    assert (
        abs(
            page.locator(".lf-threads-toggle").bounding_box()["width"]
            - thread_control_width
        )
        < 1
    )
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 2")
    page.reload()
    expect(page.locator(".lf-first-unread")).to_be_hidden()


def test_opening_threads_acknowledges_the_first_visible_answer(
    browser, serve, monkeypatch
):
    """Opening Threads over an answer already in view marks it read.

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
        page.locator(".lf-threads-toggle").click()
        assert arrived.wait(10), "opening Threads sent no read"
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        expect(card).to_have_attribute("open", "")
        expect(page.locator(".lf-first-unread")).to_be_hidden()
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    expect(card.locator("#read-choice")).to_be_visible()
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).not_to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    expect(card.locator(".lf-mark-read")).to_have_count(0)
    expect(card.locator(".lf-thread-status")).to_have_text("On you to answer")
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]
    expect(card.locator("#read-choice")).to_be_visible()


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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-first-unread").click()
    body = page.locator(f'.lf-msg[data-mid="{root}"] .lf-msg-body')
    assert (
        body.bounding_box()["height"]
        > page.locator(".lf-threads").bounding_box()["height"]
    )
    page.locator(".lf-threads").evaluate(
        "element => element.scrollTop = element.scrollHeight"
    )
    page.wait_for_timeout(100)
    assert _read_events(serve.page_dir) == []

    page.locator(".lf-threads").evaluate("element => element.scrollTop = 0")
    page.locator(".lf-threads").hover()
    list_height = page.locator(".lf-threads").evaluate(
        "element => element.clientHeight"
    )
    for _ in range(100):
        if page.locator(".lf-threads").evaluate(
            "element => element.scrollTop + element.clientHeight >= element.scrollHeight - 1"
        ):
            break
        page.mouse.wheel(0, list_height / 4)
        page.wait_for_timeout(20)
    else:
        raise AssertionError("mouse wheel did not traverse the complete answer")
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_first_unread_reveals_a_resolved_thread_and_covered_original(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "The question.")
    first = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": root,
            "text": "The earlier answer.",
        },
    )["id"]
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": root,
            "text": "The later answer.",
        },
    )
    thread_model.cmd_summarize(
        serve.page_dir, root, first, "Earlier exchange in one line."
    )
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_be_hidden()
    expect(page.locator(".lf-first-unread")).to_have_text("Next unread")
    expect(page.locator(".lf-first-unread")).to_have_attribute(
        "aria-label", "2 unread messages. Go to first unread message"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-label", "Open threads: 0, 1 unread thread"
    )

    page.locator(".lf-first-unread").click()
    expect(card).to_be_visible()
    expect(card).to_have_attribute("open", "")
    expect(card.locator(f'.lf-msg[data-mid="{first}"]')).to_be_focused()
    expect(card.locator(f'.lf-msg[data-mid="{first}"]')).to_be_visible()
    expect(card.locator(".lf-thread-checkpoint")).to_have_attribute(
        "data-expanded", "true"
    )


def test_edit_reopens_only_its_new_content_version(browser, serve):
    url = serve(PANEL_PAGE)
    user = panel_comment(serve.page_dir, "The earlier user thread.")
    original = thread_model.cmd_comment(
        serve.page_dir, None, None, None, "Original answer.", None
    )
    root = original["id"]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-first-unread").click()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    page.locator(f'.lf-thread[data-id="{user}"] > .lf-thread-summary').click()
    page.locator('.lf-thread-panel [aria-label="Close threads"]').click()

    edit = thread_model.cmd_edit(serve.page_dir, root, "Revised answer.")
    told(page)
    expect(page.locator(".lf-first-unread")).to_have_text("Next unread")
    page.locator(".lf-threads-toggle").click()
    with sending(page, "edited answer read"):
        page.locator(".lf-first-unread").click()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(".lf-first-unread").click()
    holding(page, held, 1, "automatic read")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    message = card.locator(f'.lf-msg[data-mid="{root}"]')
    expect(message).not_to_have_class(re.compile(r"(^|\s)lf-unread(\s|$)"))
    expect(message.locator(".lf-msg-sending")).to_have_count(0)
    assert (
        json.loads(page.locator("html").get_attribute("data-lf-traffic"))["pending"]
        == []
    )
    assert page.evaluate(
        "async () => !(await window.__lfRuntimeImport('/runtime/application.js')).hasPending()"
    )

    card.get_by_role("button", name="Resolve thread").click()
    holding(page, held, 2, "a resolve sent while the read is held")
    assert [route.request.post_data_json["kind"] for route in held] == [
        "read",
        "resolve",
    ]
    held[0].fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused before append"}
    )
    expect(message).to_have_class(re.compile(r"(^|\s)lf-unread(\s|$)"))
    page.unroute("**/api/event")
    held[1].abort()
    expect(page.locator(".lf-notice")).to_contain_text("Connection lost")
    told(page)
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir) == []
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["author"] == "user"
    ] == ["comment", "resolve"]
    assert not any(
        "Couldn't send" in text
        for text in page.locator(".lf-notice").all_text_contents()
    )
    assert all(
        "/api/event" in error or "Failed to load" in error
        for error in take_browser_errors(page)
    )


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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    with sending(page, "wide reply read"):
        page.locator(".lf-first-unread").click()
    code = page.locator(f'.lf-msg[data-mid="{root}"] pre').first
    assert code.evaluate("element => element.scrollWidth > element.clientWidth")
    expect(page.locator(".lf-first-unread")).to_be_hidden()
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
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    holding(page, held, 1, "automatic read")
    request = held.pop()
    request.fulfill(
        status=400,
        json={"ok": False, "final": True, "error": "refused before append"},
    )
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    expect(card.locator(".lf-mark-read")).to_have_count(0)
    assert _read_events(serve.page_dir) == []
    assert take_browser_errors(page) == [
        f"400 {request.request.url}",
        "Failed to load resource: the server responded with a status of 400 (Bad Request)",
    ]
    page.unroute("**/api/event")
    with sending(page, "read on a new visit"):
        page.evaluate("""() => {
          window.dispatchEvent(new Event('blur'));
          window.dispatchEvent(new Event('focus'));
        }""")
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).not_to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_visible_message_waits_for_whole_document_presentation(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Please report the result.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    page.evaluate("""() => {
      const list = document.querySelector('leaf-thread-list');
      const present = list.present.bind(list);
      let release;
      list.present = async model => {
        const candidate = await present(model);
        if (!window.__readHeld) {
          window.__readHeld = true;
          await new Promise(resolve => { release = resolve; });
        }
        return candidate;
      };
      window.__releaseReadPresentation = () => release();
    }""")
    reply = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "The result is ready.",
        None,
        for_event=root,
    )
    page.wait_for_function("window.__readHeld === true")
    body = card.locator(f'.lf-msg[data-mid="{reply["id"]}"] .lf-msg-body')
    expect(body).to_be_visible()
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    body.hover()
    page.wait_for_timeout(100)
    assert _read_events(serve.page_dir) == []

    page.evaluate("window.__releaseReadPresentation()")
    told(page)
    for _ in range(100):
        if _read_events(serve.page_dir):
            break
        page.wait_for_timeout(20)
    else:
        raise AssertionError("presented answer was not acknowledged")
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": reply["id"], "version": reply["id"]}
    ]


def test_keyboard_first_unread_exposes_authored_reply(browser, serve):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-threads").focus()
    with sending(page, "authored reply read"):
        page.keyboard.press("u")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_have_attribute("open", "")
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_be_focused()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_read_converges_across_two_tabs(browser, serve):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "The shared user answer.", author="agent")
    first = open_page(browser, url)
    second = open_page(browser, url)
    expect(first.locator(".lf-first-unread")).to_have_text("Next unread")
    expect(second.locator(".lf-first-unread")).to_have_text("Next unread")
    first.locator(".lf-threads-toggle").click()
    panel_settled(first)
    first.locator(".lf-first-unread").click()
    expect(first.locator(".lf-first-unread")).to_be_hidden()
    told(second)
    expect(second.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


SAMPLE_READER = "a1b2c3d4"


def _sample_reading_page(browser, serve, body, style):
    """A page holding one live sample whose child page is taller than the window and
    carries one agent message, so the thread panel it opens stands the message near the
    frame's top. `style` places the sample; the returned child is its page, which keeps
    a log and a ledger of trips of its own (`Traffic`)."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Sample reading practice",
                body.format(
                    sample=f"""<lf-sample id="read-practice" label="Read practice">
  <template id="read-source" data-sample data-sample-threads="{SAMPLE_READER}">
    <style>#child-rest {{ height: 3000px; }}</style>
    <h1>Child page</h1>
    <div id="child-rest"></div>
  </template>
</lf-sample>"""
                ),
                head=f"<style>{style}</style>",
            ),
            events=[
                {
                    "id": SAMPLE_READER,
                    "kind": "comment",
                    "author": "agent",
                    "agent": "Agent",
                    "revision": 1,
                    "text": "A framed answer for the user.",
                }
            ],
        ),
    )
    frame = page.locator("#read-practice iframe")
    child = frame.element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    expect(child.locator(".lf-first-unread")).to_have_attribute(
        "aria-label", "1 unread message. Go to first unread message"
    )
    return page, frame, child


def _message_body(child):
    return child.locator(f'.lf-msg[data-mid="{SAMPLE_READER}"] .lf-msg-body')


def _open_first_unread(page, child):
    """The user opens the sample's Threads from its focused toggle and goes to its first
    unread message by key. Once the panel's slide has ended, the message stands whole in
    the child's own viewport, so what the containing page shows of the frame is all that
    is left to keep it unread."""
    page.keyboard.press("Enter")
    expect(child.locator(".lf-threads")).to_be_visible()
    page.keyboard.press("u")
    expect(child.locator(f'.lf-thread[data-id="{SAMPLE_READER}"]')).to_have_attribute(
        "open", ""
    )
    panel_settled(child)
    assert _message_body(child).evaluate("""body => {
        const box = body.getBoundingClientRect();
        return box.top >= 0 && box.bottom <= innerHeight
            && box.left >= 0 && box.right <= innerWidth;
    }"""), "the message is not whole in the child's own viewport"


def _still_unread(child):
    """Read once, after the reading pass the last move scheduled has run (`rendered`).
    The page draws a version read in the pass that sends it, so a pass that read the
    message would have hidden Next unread and counted a send."""
    rendered(child)
    assert child.locator(".lf-first-unread").is_visible()
    assert _traffic(child).sends == 0


def _read_by_the_sample(page, child):
    """The control: the child sends the message read, and its server holds it read."""
    expect(child.locator(".lf-first-unread")).to_be_hidden()
    round_trip(child)
    state = page.request.get(f"{child.url}api/state").json()
    (thread,) = state["browser"]["thread"]["threads"]
    assert thread["id"] == SAMPLE_READER
    assert thread["unread"] == []


def test_clipped_sample_cannot_acknowledge_child_viewport(browser, serve):
    # On the first screen, inside a scrolling box that shows only its top, the sample's
    # own page shows the message and the containing page does not.
    page, _, child = _sample_reading_page(
        browser,
        serve,
        '<h1>Practice page</h1><div id="read-clip">{sample}</div>',
        "#read-clip { height: 100px; overflow: auto; }",
    )
    child.locator(".lf-threads-toggle").focus()
    _open_first_unread(page, child)
    _still_unread(child)

    # Scrolling the box until the message stands 20px below its top shows it, and the
    # same message is read.
    top = _message_body(child).evaluate("body => body.getBoundingClientRect().top")
    page.locator("#read-clip").evaluate(
        """(clip, top) => clip.scrollBy(0, clip.querySelector('iframe')
            .getBoundingClientRect().top + top - clip.getBoundingClientRect().top - 20)""",
        top,
    )
    _read_by_the_sample(page, child)


def test_offscreen_sample_cannot_acknowledge_child_viewport(browser, serve):
    page, frame, child = _sample_reading_page(
        browser,
        serve,
        '<h1>Practice page</h1><div id="read-gap"></div>{sample}',
        "#read-gap { height: 2000px; }",
    )
    # Below the first screen it shows nothing: the user focuses its Threads toggle and
    # scrolls the containing page back to the top first.
    child.locator(".lf-threads-toggle").focus()
    page.evaluate("scrollTo(0, 0)")
    _open_first_unread(page, child)
    assert frame.bounding_box()["y"] > page.viewport_size["height"]
    _still_unread(child)

    # Taller than the window, the sample is read through the band the containing page
    # shows as it scrolls: its edge coming into view shows nothing, and a later scroll of
    # the containing page shows the message.
    page.evaluate("""() => {
        const top = document.querySelector('#read-practice iframe')
            .getBoundingClientRect().top;
        scrollBy(0, top - innerHeight + 20);
    }""")
    _still_unread(child)
    page.evaluate("scrollBy(0, 700)")
    _read_by_the_sample(page, child)


def _box_height(locator):
    return locator.evaluate("node => node.getBoundingClientRect().height")


def test_a_reply_held_in_a_diff_thread_is_read_once_the_keyboard_opens_it(
    browser, serve
):
    """A reply landing in the diff thread the user had just written grew the thread at
    its foot, on screen, and everything after the diff moved down the page. It waits
    behind a notice in the thread's head row, which appears without changing the
    thread's height, and stays unread while none of it has shown. The keyboard reaches
    the notice from the thread and opens it, and the reply's body, drawn inside the
    widget's shadow tree, is read once shown. The browser fixture's shift watch holds
    the rest: the reply is news."""
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
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    expect(thread).to_be_visible()
    height = _box_height(thread)
    reply = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "The route-line answer is ready.",
        None,
        for_event=root,
    )
    told(page)
    news = thread.locator(":scope > .lf-thread-root-meta").get_by_role(
        "button", name="1 new reply"
    )
    expect(news).to_be_visible()
    expect(thread.locator(".lf-msg")).to_have_count(1)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)
    assert not _read_events(serve.page_dir)

    thread.locator(":scope > .lf-thread-reply leaf-text").focus()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Tab")
    expect(news).to_be_focused()
    page.keyboard.press("Enter")
    expect(news).to_have_count(0)
    expect(thread).to_be_focused()
    body = thread.locator(f'.lf-msg[data-event="{reply["id"]}"] .lf-msg-body')
    expect(body).to_be_visible()
    assert body.evaluate("element => element.getRootNode() instanceof ShadowRoot")
    body.scroll_into_view_if_needed()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": reply["id"], "version": reply["id"]}
    ]


# A task whose seat stands past a screen of prose, with more prose after it for a
# thread's growth to move.
def _seat_filler(name):
    return "".join(
        f"<p id='{name}-{n}'>Filler paragraph {n}, long enough to take a line.</p>"
        for n in range(30)
    )


TASK_SEAT_PAGE = leaf_page(
    "seat",
    f"<h1 id='h'>Three jobs</h1>{_seat_filler('lead')}<lf-command id='hub' "
    "label='Before the frost'><lf-task id='jobs' status='active' talk>"
    f"<strong>Which jobs are worth starting?</strong></lf-task></lf-command>"
    f"{_seat_filler('tail')}",
)


@pytest.mark.parametrize("end", ["opened", "replied", "left"])
def test_replies_held_in_a_page_seat_show_when_the_user_turns_to_them(
    browser, serve, end
):
    """Replies landing while a seated thread's foot is on screen wait behind one
    notice that counts them, and show together, in the order they came: when the user
    presses the notice, when they send a turn of their own, which answers the replies
    and so follows them, and when they scroll the thread below the window, where its
    growth moves nothing they see. Nothing before the ending is input, so the browser
    fixture's shift watch also checks that holding the replies moved nothing."""
    url = serve(TASK_SEAT_PAGE)
    root = events_model.append_event(
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
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    thread.evaluate(
        """thread => document.scrollingElement.scrollBy({
          top: thread.getBoundingClientRect().top - innerHeight / 3,
          behavior: 'instant'})"""
    )
    height = _box_height(thread)
    replies = []
    for n in (1, 2):
        replies.append(
            events_model.append_event(
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
    news = thread.locator(":scope > .lf-thread-root-meta").get_by_role(
        "button", name="2 new replies"
    )
    expect(news).to_be_visible()
    expect(thread.locator(".lf-msg")).to_have_count(1)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)

    if end == "opened":
        news.click()
    elif end == "replied":
        write(
            thread.locator(":scope > .lf-thread-reply leaf-text"),
            "Then the roof first.",
        )
        with sending(page, "the user's reply"):
            page.keyboard.press("Enter")
    else:
        thread.evaluate(
            """thread => document.scrollingElement.scrollBy({
              top: thread.getBoundingClientRect().top - innerHeight - 400,
              behavior: 'instant'})"""
        )
    shown = thread.locator(".lf-msg")
    expect(shown).to_have_count(4 if end == "replied" else 3)
    expect(news).to_have_count(0)
    events = shown.evaluate_all("turns => turns.map(turn => turn.dataset.event)")
    assert events[:3] == [root, *replies]
    if end == "replied":
        expect(shown.last).to_contain_text("Then the roof first.")


def _seat_comment(page_dir, author, text):
    event = {
        "kind": "comment",
        "author": author,
        "revision": 1,
        "text": text,
        "anchor": {"section": "jobs"},
    }
    if author == "agent":
        event["agent"] = "Codex"
    return events_model.append_event(page_dir, event)["id"]


def _agent_turn(page_dir, root, text):
    return events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "revision": 1,
            "text": text,
        },
    )["id"]


def _to_upper_third(locator):
    """Scroll the page, without input, so the element's top stands a third of the way
    down the window and the page after it is on screen."""
    locator.evaluate(
        """node => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().top - innerHeight / 3,
          behavior: 'instant'})"""
    )


@pytest.mark.parametrize("pointer", ["fine", "coarse"])
def test_a_reopening_in_a_page_seat_waits_where_reopen_stood(browser, serve, pointer):
    """An agent's reply to a resolved thread reopens it. Drawn at once, the reopened
    thread grew in place under the reader: its new turn and its reply box pushed the
    page after it down. It stands as drawn, resolved, and its resolved row says what is
    waiting in Reopen's place and face, at the row's height under either pointer (a
    chip's face stood 6px shorter than Reopen at a fine pointer). On a phone a tap opens
    it; on the desktop `r` on the thread, which reopens a resolved thread, does. The
    thread shows open, with the new turn after the earlier ones and a reply box. Nothing
    before the opening is input, so the shift watch checks that the hold moved nothing."""
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
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": root, "revision": 1},
    )
    page = open_page(browser, url, context=context)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    _to_upper_third(thread)
    height = _box_height(thread)
    second = _agent_turn(serve.page_dir, root, "The roof cannot wait after all.")
    told(page)
    row = thread.locator(":scope > .lf-page-thread-resolved")
    news = row.get_by_role("button", name="Reopened · 1 new reply")
    expect(news).to_be_visible()
    expect(row.get_by_role("button", name="Reopen", exact=True)).to_have_count(0)
    expect(thread.locator(".lf-msg")).to_have_count(2)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)

    if pointer == "coarse":
        news.tap()
    else:
        # The key before the focus makes the shortcut bar's redraw an answer to input.
        page.keyboard.press("Shift")
        thread.focus()
        page.keyboard.press("r")
    expect(row).to_have_count(0)
    shown = thread.locator(".lf-msg")
    expect(shown).to_have_count(3)
    assert shown.evaluate_all("turns => turns.map(turn => turn.dataset.event)") == [
        root,
        first,
        second,
    ]
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_be_visible()


@pytest.mark.parametrize("opening", ["Enter", "Space", "pointer", "programmatic"])
def test_a_reopening_in_a_folded_diff_thread_waits_in_its_summary(
    browser, serve, opening
):
    """A resolved diff thread stands folded to its summary. An agent's reply that
    reopened it unfolded it under the reader, and every diff line after it moved down by
    the whole thread. It stays folded, its summary says what is waiting, and the
    keyboard, left on the thread by the resolve, reaches the summary and opens it to the
    thread, open, with the new turn."""
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
    # The send leaves the user on the thread, and Resolve is its first stop.
    page.keyboard.press("Tab")
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    expect(thread).to_be_focused()
    summary = thread.locator(":scope > summary")
    expect(summary).to_have_text("Resolved · 1 message")
    _to_upper_third(thread)
    height = _box_height(thread)
    # Resolving answered the comment, so the agent's turn is one nothing asked for.
    reply = thread_model.cmd_reply(
        serve.page_dir, root, "The route stays.", None, for_event=None
    )
    told(page)
    expect(summary).to_have_text("Reopened · 1 new reply")
    expect(thread).not_to_have_attribute("open", "")
    assert _box_height(thread) == pytest.approx(height, abs=0.5)

    # A native open-attribute checkpoint runs before paint. The first opened body
    # must already contain the released news, rather than the older resolved layout.
    thread.evaluate("""node => {
      window.openedThread = null;
      new MutationObserver(() => {
        if (!node.open || window.openedThread) return;
        window.openedThread = {
          messages: [...node.querySelectorAll('.lf-msg')].map(message => message.dataset.event),
          reply: Boolean(node.querySelector(':scope > .lf-thread-reply leaf-text')),
        };
      }).observe(node, {attributeFilter:['open']});
    }""")
    page.keyboard.press("Tab")
    expect(summary).to_be_focused()
    if opening == "pointer":
        summary.click()
    elif opening == "programmatic":
        thread.evaluate("""node => {
          const open = document.createElement('button');
          open.textContent = 'Open disclosure';
          open.style.cssText = 'position:fixed;left:0;top:80px;z-index:9999';
          open.onclick = () => {node.open = true};
          document.body.append(open);
        }""")
        page.get_by_role("button", name="Open disclosure", exact=True).click()
    else:
        page.keyboard.press(opening)
    assert page.evaluate("openedThread") == {
        "messages": [root, reply["id"]],
        "reply": True,
    }
    expect(thread).to_have_attribute("open", "")
    expect(summary).to_be_hidden()
    expect(thread.locator(f'.lf-msg[data-event="{reply["id"]}"]')).to_be_visible()
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_be_visible()


@pytest.mark.parametrize(
    ("beside", "end"),
    [
        ("box", "opened"),
        ("box", "left"),
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
    size: the head row of the seat's last thread, or, in a seat that draws no thread, a
    row standing in place of the first-message row at that row's height, since the row
    has no room beside its box. It shows when the user opens the notice from the
    keyboard, when they start a thread of their own, which shows after it, and when they
    scroll the seat below the window. A user standing in the first-message box keeps it:
    the thread shows above the box, which stays where it stood. Nothing before the
    ending is input, so the shift watch checks that the hold moved nothing."""
    url = serve(TASK_SEAT_PAGE)
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
        else threads.first.locator(":scope > .lf-thread-root-meta")
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
    elif end == "started":
        write(box, "And the shed roof?")
        with sending(page, "the user's thread"):
            page.keyboard.press("Enter")
    else:
        seat.evaluate(
            """seat => document.scrollingElement.scrollBy({
              top: seat.getBoundingClientRect().top - innerHeight - 400,
              behavior: 'instant'})"""
        )
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


ROUTE_LINE = '["app/routes.py","new",201]'


@pytest.mark.parametrize(
    "end",
    [
        "clicked",
        "tapped",
        "keyboard",
        "settled",
        "replied",
        "resolved",
        "started",
        "left",
        "standing",
    ],
)
def test_a_thread_the_agent_starts_on_a_bare_diff_line_waits_at_its_margin_marker(
    browser, serve, end
):
    """A thread the agent starts on a diff line with no thread opened a new outlet under
    the line, and every line and paragraph after it moved down under the reader. No row
    the diff draws can say it waits, so the diff does not draw it: it stands in the
    margin, as any thread the diff does not place does, and its marker is the notice.
    Clicking, tapping, or pressing Enter on the marker shows the thread under its line
    and lands on it, and the marker stays its notice when the agent settles it. It also
    shows when the user replies in it from the margin's card, when they resolve it
    there, when they start a thread on the same line, which shows after it, and when
    they scroll the line below the window, unless they are writing in its card, which
    stays with them. The news lands well past Chrome's half second of recent input, so
    the shift watch checks that holding the thread moved nothing."""
    context = (
        browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        if end == "tapped"
        else None
    )
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url, context=context)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    line = page.locator(f"lf-diff [data-lf-datum='{ROUTE_LINE}']")
    _to_upper_third(line)
    after = page.locator("#tail-0")
    top = after.evaluate("node => node.getBoundingClientRect().top")
    page.wait_for_function(
        "at => performance.now() - at > 600", arg=page.evaluate("performance.now()")
    )
    held = events_model.append_event(
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
        events_model.append_event(
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
    elif end == "standing":
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
        second = events_model.append_event(
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
    elif end == "clicked":
        marker.click()
    elif end == "tapped":
        marker.tap()
    elif end == "keyboard":
        # The marker as the rail's Tab stop, in keyboard modality. The key before the
        # focus makes the shortcut bar's redraw for the stop an answer to input.
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
    elif end == "resolved":
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        with sending(page, "the resolve"):
            card.get_by_role("button", name="Resolve thread").click()
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
    if end in ("resolved", "settled"):
        expect(threads.first.locator(":scope > summary")).to_have_text(
            "Resolved · 1 message"
        )
    if end in ("clicked", "tapped", "keyboard"):
        # The marker goes with what it held, and the user lands on the thread it showed,
        # or on the summary a settled thread folds to.
        expect(threads.first).to_be_focused()
    if end == "settled":
        expect(threads.first.locator(":scope > summary")).to_be_focused()


@pytest.mark.parametrize(("width", "under_panel"), [(900, True), (1920, False)])
def test_a_page_seat_the_open_panel_stands_over_is_not_read(
    browser, serve, width, under_panel
):
    """Exposure counts a message read once all of it has been shown. The open Threads
    panel stands over the right of the page, so an answer in a page-side seat that
    reaches under it has not been shown whole, however much of it is clear: at 900px
    the diff's thread outlet runs under the panel and earns no receipt until the panel
    closes. At 1920px the panel stands over empty margin and the same answer is read
    with the panel open. The panel's list is narrowed to no card, so the page seat is the
    only copy in view."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.set_viewport_size({"width": width, "height": 900})
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # A find that matches nothing narrows the panel's list to no card, so the page seat
    # is the one copy of the answer in view.
    find = page.get_by_role("searchbox", name="Find in threads")
    find.focus()
    page.keyboard.type("nothing matches this")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(0)
    find.blur()
    reply = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "The route-line answer is ready.",
        None,
        for_event=root,
    )
    told(page)
    # The answer landed on screen, so the user opens it where it waits.
    page.locator("lf-diff .lf-page-thread").get_by_role(
        "button", name="1 new reply"
    ).click()
    body = page.locator(
        f'lf-diff .lf-diff-thread-outlet .lf-msg[data-event="{reply["id"]}"]'
        " .lf-msg-body"
    )
    expect(body).to_be_visible()
    body.scroll_into_view_if_needed()
    read = [{"message": reply["id"], "version": reply["id"]}]

    def receipt():
        return any(event["messages"] == read for event in _read_events(serve.page_dir))

    body_right = body.evaluate("element => element.getBoundingClientRect().right")
    panel_left = page.locator(".lf-thread-panel").bounding_box()["x"]
    assert (body_right > panel_left) == under_panel, (
        f"the fixture put the seat's right edge at {body_right} against the panel's "
        f"{panel_left}, so it does not test what it names"
    )
    if under_panel:
        # Long enough for an observation pass to have sent a receipt had it counted.
        page.wait_for_timeout(1500)
        assert not receipt(), "a message partly under the open panel was marked read"
        page.get_by_role("button", name="Close threads").click()
        panel_settled(page, open=False)
    deadline = time.monotonic() + 10
    while not receipt() and time.monotonic() < deadline:
        page.wait_for_timeout(100)
    assert receipt(), "the answer shown whole was never marked read"


def test_modal_blocks_exposure_until_user_returns_to_threads(browser, serve):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(
        serve.page_dir, "A short answer behind the dialog.", author="agent"
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-threads-toggle").focus()
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    assert reference.evaluate("element => element.matches(':modal')")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").evaluate("element => element.click()")
    expect(card.locator(f'.lf-msg[data-mid="{root}"] .lf-msg-body')).to_be_visible()
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(100)
    assert _read_events(serve.page_dir) == []
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(page.locator(".lf-first-unread")).to_be_hidden()


# Every element box in a card, keyed by the element itself, so a later reading
# compares exactly the nodes that survived.
_CARD_BOXES = """card => {
  const boxes = new Map();
  for (const element of [card, ...card.querySelectorAll("*")]) {
    const box = element.getBoundingClientRect();
    boxes.set(element, [box.x, box.y, box.width, box.height].map(Math.round));
  }
  return boxes;
}"""


def test_reading_a_thread_moves_nothing_in_it(browser, serve):
    """A read receipt removes rails and boundaries without moving the thread's
    content. The title's unread count may close up sideways."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Review this metric.\n\n" + "The complete context matters. " * 250,
        author="agent",
    )
    second = _agent_metric_reply(serve.page_dir, root, 2)
    accepted, _ = endpoint_model.accept_event(
        serve.page_dir,
        {"kind": "read", "messages": [{"message": second, "version": second}]},
        dict,
    )
    assert accepted == 200
    third = _agent_metric_reply(serve.page_dir, root, 3)
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_have_attribute("open", "")
    expect(card.locator('.lf-read-boundary[data-kind="new"]')).to_have_count(2)
    expect(card.locator('.lf-read-boundary[data-kind="end"]')).to_have_count(1)
    expect(card.locator(".lf-msg.lf-unread")).to_have_count(2)
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
    expect(card.locator(".lf-msg.lf-unread")).to_have_count(0)
    expect(card.locator(".lf-read-boundary")).to_have_count(0)
    moved = card.evaluate(f"""card => {{
      const after = ({_CARD_BOXES})(card);
      const rows = ":is(.lf-thread-summary, .lf-msg-meta, .lf-thread-meta-actions)";
      const moved = [];
      for (const [element, box] of window.__before) {{
        if (!after.has(element) || !element.isConnected) continue;
        const now = after.get(element);
        const sideways = element.matches(`${{rows}}, ${{rows}} *`);
        const kept = sideways ? [1, 3] : [0, 1, 2, 3];
        if (kept.some(at => now[at] !== box[at]))
          moved.push(`${{element.tagName}}.${{element.className}} ${{box}} -> ${{now}}`);
      }}
      return moved;
    }}""")
    assert moved == []
