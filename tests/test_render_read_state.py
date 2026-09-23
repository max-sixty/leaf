"""Durable reader acknowledgement through the rendered Thread surfaces."""

import json
import re

from leaf import conversation as conversation_model
from leaf import data as data_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_cases_widgets import LONG_LINE_DIFF_PAGE, MULTI_HUNK_PATCH
from render_harness import (
    holding,
    leaf_page,
    open_page,
    panel_settled,
    sending,
    take_browser_errors,
    told,
)


def _read_events(page_dir):
    return [
        event for event in events_model.read_events(page_dir) if event["kind"] == "read"
    ]


def _agent_metric_reply(page_dir, root, number, for_event=None):
    return conversation_model.cmd_reply(
        page_dir,
        root,
        f"Update {number}.",
        (
            f'<lf-metrics><lf-metric id="read-update-{number}" value="{number}">'
            "Completed steps</lf-metric></lf-metrics>"
        ),
        for_event=for_event,
        initiates=for_event is None,
        when_settled="post",
    )["id"]


def test_new_since_last_looked_bounds_each_unread_run_and_summary_originals(
    browser, serve
):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Can we review this?", author="user")
    first = _agent_metric_reply(serve.page_dir, root, 1, for_event=root)
    reader = events_model.append_event(
        serve.page_dir,
        {"kind": "reply", "author": "user", "parent": root, "text": "One more detail."},
    )["id"]
    middle = _agent_metric_reply(serve.page_dir, root, 2, for_event=reader)
    last = _agent_metric_reply(serve.page_dir, root, 3)
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
    conversation_model.cmd_edit(serve.page_dir, first, "Revised update 1.")
    conversation_model.cmd_summarize(
        serve.page_dir, root, first, middle, "The first two updates in brief."
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
    expect(card.locator('.lf-read-boundary[data-kind="end"]')).to_have_count(0)
    expect(
        card.locator(f'.lf-read-boundary[data-kind="new"] + .lf-msg[data-mid="{last}"]')
    ).to_be_visible()
    checkpoint.locator(".lf-summary-expand").click()
    expect(
        card.get_by_role("separator", name="New since you last looked")
    ).to_have_count(2)
    expect(
        card.locator(
            f'.lf-read-boundary[data-kind="new"] + .lf-msg[data-mid="{first}"]'
        )
    ).to_be_visible()
    expect(card.locator('.lf-read-boundary[data-kind="new"]')).to_have_count(2)
    expect(card.locator('.lf-read-boundary[data-kind="end"]')).to_have_count(1)
    expect(
        card.locator(f'.lf-read-boundary + .lf-msg[data-mid="{middle}"]')
    ).to_have_count(0)

    draft = card.locator("textarea").first
    draft.fill("Compare the revised update.")
    last_message = card.locator(f'.lf-msg[data-mid="{last}"]')
    last_message.focus()
    list_scroll = page.locator(".lf-threads")
    list_scroll.evaluate("element => element.scrollTop = element.scrollHeight")
    assert list_scroll.evaluate(
        "element => element.scrollTop + element.clientHeight >= element.scrollHeight - 1"
    )
    page.keyboard.press("m")
    expect(card.locator(".lf-read-boundary")).to_have_count(0)
    expect(checkpoint.locator(".lf-summary-unread")).to_have_count(0)
    expect(draft).to_have_value("Compare the revised update.")
    expect(last_message).to_be_focused()
    assert last_message.is_visible()
    assert list_scroll.evaluate(
        "element => element.scrollTop + element.clientHeight >= element.scrollHeight - 1"
    )


def test_first_unread_reveals_divider_inside_resolved_summary(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Is this metric settled?", author="user")
    answer = _agent_metric_reply(serve.page_dir, root, 4, for_event=root)
    conversation_model.cmd_summarize(
        serve.page_dir, root, root, answer, "The earlier metric discussion."
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
    expect(
        card.locator(
            f'.lf-read-boundary[data-kind="new"] + .lf-msg[data-mid="{answer}"]'
        )
    ).to_be_visible()


def test_unread_agent_root_boundary_precedes_hoisted_header(browser, serve):
    url = serve(PANEL_PAGE)
    root = conversation_model.cmd_comment(
        serve.page_dir,
        "",
        "",
        "",
        "Review this metric.",
        '<lf-metrics><lf-metric id="root-metric" value="1">Completed steps</lf-metric></lf-metrics>',
    )["id"]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    expect(
        card.locator(":scope > .lf-read-boundary + .lf-thread-root-meta")
    ).to_be_visible()
    expect(
        card.locator(f':scope > .lf-thread-root-meta + .lf-msg[data-mid="{root}"]')
    ).to_be_visible()
    expect(
        card.get_by_role("separator", name="New since you last looked")
    ).to_have_count(1)
    resolve = card.get_by_role("button", name="Resolve thread")
    resolve.focus()
    accepted, _ = endpoint_model.accept_event(
        serve.page_dir,
        {"kind": "read", "messages": [{"message": root, "version": root}]},
        dict,
    )
    assert accepted == 200
    told(page)
    expect(card.locator(".lf-read-boundary")).to_have_count(0)
    expect(resolve).to_be_focused()


def test_first_unread_opens_the_exact_message_and_exposure_acknowledges_it(
    browser, serve
):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier reader thread.")
    root = panel_comment(serve.page_dir, "An answer for the reader.", author="agent")
    page = open_page(browser, url)

    expect(page.locator(".lf-first-unread")).to_have_text("Unread 1")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (2)")
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-label", "Threads (2), 1 unread thread"
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
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (2)")
    page.reload()
    expect(page.locator(".lf-first-unread")).to_be_hidden()


def test_opening_threads_acknowledges_the_first_visible_answer(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "An answer already in view.", author="agent")
    page = open_page(browser, url)
    with sending(page, "read from expanded thread"):
        page.locator(".lf-threads-toggle").click()
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_have_attribute("open", "")
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_authored_reply_requires_explicit_read_even_when_open(browser, serve):
    url = serve(PANEL_PAGE)
    root = conversation_model.cmd_comment(
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
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    assert _read_events(serve.page_dir) == []

    page.keyboard.press("Tab")
    expect(card.get_by_role("button", name="Mark thread read")).to_be_focused()
    page.keyboard.press("Enter")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("Tab")
    expect(card.get_by_role("button", name="Resolve")).to_be_focused()
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).not_to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]
    expect(card.locator("#read-choice")).to_be_visible()


def test_oversized_message_needs_contiguous_traversal_or_explicit_read(browser, serve):
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
    conversation_model.cmd_summarize(
        serve.page_dir, root, root, first, "Earlier exchange in one line."
    )
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_be_hidden()
    expect(page.locator(".lf-first-unread")).to_have_text("Unread 2")
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-label", "Threads (0), 1 unread thread"
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
    reader = panel_comment(serve.page_dir, "The earlier reader thread.")
    original = conversation_model.cmd_comment(
        serve.page_dir, None, None, None, "Original answer.", None
    )
    root = original["id"]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-first-unread").click()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    page.locator(f'.lf-thread[data-id="{reader}"] > .lf-thread-summary').click()
    page.locator('.lf-thread-panel [aria-label="Close threads"]').click()

    edit = conversation_model.cmd_edit(serve.page_dir, root, "Revised answer.")
    told(page)
    expect(page.locator(".lf-first-unread")).to_have_text("Unread 1")
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
    reported, and resolving the thread is itself evidence the reader took it in."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier reader thread.")
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
    panel_comment(serve.page_dir, "The earlier reader thread.")
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


def test_explicit_mark_read_reports_refusal_as_read_action(browser, serve):
    url = serve(PANEL_PAGE)
    root = conversation_model.cmd_comment(
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    card.get_by_role("button", name="Mark thread read").click()
    holding(page, held, 1, "explicit read")
    request = held.pop()
    request.fulfill(
        status=400,
        json={"ok": False, "final": True, "error": "refused before append"},
    )
    expect(card.get_by_role("button", name="Mark thread read")).to_be_visible()
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't mark thread read")
    assert _read_events(serve.page_dir) == []
    assert take_browser_errors(page) == [
        f"400 {request.request.url}",
        "Failed to load resource: the server responded with a status of 400 (Bad Request)",
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
    reply = conversation_model.cmd_reply(
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


def test_keyboard_first_unread_and_mark_read_retain_draft_and_focus(browser, serve):
    url = serve(PANEL_PAGE)
    root = conversation_model.cmd_comment(
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
    page.keyboard.press("u")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_have_attribute("open", "")
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_be_focused()
    expect(card.locator(".lf-thread-unread")).to_have_text("1 unread")

    draft = card.locator("textarea").first
    draft.fill("I need to compare these choices.")
    draft.evaluate("element => { window.__readDraft = element; }")
    draft.blur()
    card.locator(":scope > .lf-thread-summary").focus()
    page.keyboard.press("m")
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    expect(draft).to_have_value("I need to compare these choices.")
    assert draft.evaluate("element => element === window.__readDraft")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_read_converges_across_two_tabs(browser, serve):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier reader thread.")
    root = panel_comment(serve.page_dir, "The shared reader answer.", author="agent")
    first = open_page(browser, url)
    second = open_page(browser, url)
    expect(first.locator(".lf-first-unread")).to_have_text("Unread 1")
    expect(second.locator(".lf-first-unread")).to_have_text("Unread 1")
    first.locator(".lf-threads-toggle").click()
    panel_settled(first)
    first.locator(".lf-first-unread").click()
    expect(first.locator(".lf-first-unread")).to_be_hidden()
    told(second)
    expect(second.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_offscreen_specimen_cannot_acknowledge_child_viewport(browser, serve):
    root = "a1b2c3d4"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Offscreen reading practice",
                f"""
<h1>Practice page</h1>
<div id="read-clip">
<lf-specimen id="read-practice" label="Read practice">
  <template id="read-source" data-specimen data-specimen-threads="{root}">
    <h1>Child page</h1>
  </template>
</lf-specimen>
</div>
""",
            ),
            events=[
                {
                    "id": root,
                    "kind": "comment",
                    "author": "agent",
                    "agent": "Agent",
                    "revision": 1,
                    "text": "A framed answer for the reader.",
                }
            ],
        ),
    )
    clip = page.locator("#read-clip")
    specimen = page.locator("#read-practice")
    frame = specimen.locator("iframe")
    child = frame.element_handle().content_frame()
    expect(child.locator(".lf-first-unread")).to_have_text("Unread 1")
    assert child.locator("body").evaluate("element => element.inert")
    specimen.get_by_role("button", name="Enter specimen").click()
    expect(child.locator("body")).not_to_have_attribute("inert", "")
    frame.evaluate("element => element.style.transform = 'translateY(1200px)'")
    child.locator(".lf-threads-toggle").evaluate("element => element.click()")
    child.locator(".lf-first-unread").evaluate("element => element.click()")
    page.wait_for_timeout(100)
    expect(child.locator(".lf-first-unread")).to_have_text("Unread 1")
    assert frame.bounding_box()["y"] > 800

    clip.evaluate(
        "element => { element.style.height = '100px'; element.style.overflow = 'hidden'; }"
    )
    frame.evaluate("element => element.style.transform = ''")
    page.set_viewport_size({"width": 1280, "height": 1400})
    page.wait_for_timeout(100)
    expect(child.locator(".lf-first-unread")).to_have_text("Unread 1")
    clip.evaluate(
        "element => { element.style.height = ''; element.style.overflow = ''; }"
    )
    frame.scroll_into_view_if_needed()
    expect(child.locator(".lf-first-unread")).to_be_hidden()


def test_shadow_package_thread_registers_its_real_message_body(browser, serve):
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    row = page.locator('lf-diff [data-lf-datum=\'["app/routes.py","new",201]\']')
    row.scroll_into_view_if_needed()
    row.evaluate("""element => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const nodes = [], starts = [];
      let text = '';
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        starts.push(text.length); nodes.push(node); text += node.data;
      }
      const start = text.indexOf('new route');
      if (start < 0) throw new Error('diff phrase missing');
      const at = offset => {
        const index = starts.findLastIndex(value => value <= offset);
        return [nodes[index], offset - starts[index]];
      };
      const range = document.createRange();
      range.setStart(...at(start)); range.setEnd(...at(start + 'new route'.length));
      const selection = getSelection();
      selection.removeAllRanges(); selection.addRange(range);
      document.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
    }""")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-composer textarea").fill("Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    reply = conversation_model.cmd_reply(
        serve.page_dir,
        root,
        "The route-line answer is ready.",
        None,
        for_event=root,
    )
    told(page)
    body = page.locator(
        f'lf-diff .lf-diff-thread-outlet .lf-conversation-msg[data-event="{reply["id"]}"] .lf-conversation-body'
    )
    expect(body).to_be_visible()
    assert body.evaluate("element => element.getRootNode() instanceof ShadowRoot")
    body.scroll_into_view_if_needed()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": reply["id"], "version": reply["id"]}
    ]


def test_modal_blocks_exposure_until_reader_returns_to_threads(browser, serve):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier reader thread.")
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
    """Read state is bookkeeping: a read receipt takes a thread's rails, boundaries,
    labels and Mark read control away without moving anything the reader is looking
    at. Only a row that loses a label or control may close up sideways."""
    url = serve(PANEL_PAGE)
    root = conversation_model.cmd_comment(
        serve.page_dir,
        None,
        None,
        None,
        "Review this metric.",
        '<lf-metrics><lf-metric id="root-metric" value="1">Completed steps</lf-metric>'
        "</lf-metrics>",
    )["id"]
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
