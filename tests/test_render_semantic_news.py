"""Meaningful notices from successfully presented server readings."""

import re

import pytest
from interact_support import record_claim
from leaf import conversation as conversation_model
from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import requests as requests_model
from leaf import service as service_model
from leaf import session as session_model
from playwright.sync_api import expect
from render_cases_interaction import (
    COMMAND_HUB_EXAMPLE,
    PANEL_PAGE,
    live_url,
    panel_comment,
)
from render_harness import FEATURE_GALLERY, open_page, sending, told


def test_new_reply_and_user_question_share_one_notice_without_moving_focus(
    browser, serve
):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What should change?")
    page = open_page(browser, url)
    toggle = page.locator(".lf-threads-toggle")
    toggle.focus()
    expect(toggle).to_be_focused()
    expect(page.locator(".lf-notice")).to_be_hidden()

    conversation_model.cmd_reply(
        serve.page_dir,
        root,
        "I changed the route. Does this answer your question?",
        None,
        awaits=True,
        for_event=root,
    )
    told(page)
    notice = re.compile(r".+ replied; Input needed")
    expect(page.locator(".lf-notice")).to_have_text(notice)
    expect(page.locator(".lf-live")).to_have_text(notice)
    expect(toggle).to_be_focused()


def test_gallery_new_information_specimen_preserves_focus(browser, serve):
    page = open_page(browser, serve(FEATURE_GALLERY))
    guide = page.locator("#bg-thread-notices")
    expect(guide).to_contain_text("status-line notice")
    toggle = page.locator(".lf-threads-toggle")
    toggle.focus()
    expect(toggle).to_be_focused()
    expect(page.locator(".lf-notice")).to_be_hidden()

    conversation_model.cmd_comment(
        serve.page_dir, None, None, None, "A new page-wide agent note.", None
    )
    told(page)
    expect(page.locator(".lf-notice")).to_have_text(re.compile(r".+ commented"))
    expect(page.locator(".lf-live")).to_have_text(re.compile(r".+ commented"))
    expect(toggle).to_be_focused()


def test_terminal_failure_is_a_response_notice_not_an_agent_reply(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Please run this request.")
    page = open_page(browser, url)
    expect(page.locator(".lf-notice")).to_be_hidden()

    conversation_model.cmd_reply(
        serve.page_dir,
        root,
        "The agent turn ended before completion.",
        None,
        for_event=root,
        failure="turn_failed",
        attempt="response-failed-attempt",
    )
    told(page)
    expect(page.locator(".lf-notice")).to_have_text("Response failed")
    expect(page.locator(".lf-live")).to_have_text("Response failed")


def test_interrupted_live_response_announces_its_exact_attempt(browser, serve, request):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Please answer here.")
    claim = record_claim(
        serve.page_dir, id="codex-thread", harness="codex", agent="Codex"
    )
    lease = leases_model.take_waiter_lease(
        leases_model.waiter_lease_path(serve.page_dir, claim["id"])
    )
    assert lease
    request.addfinalizer(lease.close)
    attempt = service_model.delivery_reply_attempt("delivery-interrupted")
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_status("waiting", "User feedback")
        transaction.set_stream_reply(
            "codex-thread", "leaf-turn", root, root, attempt, None, "Draft", "active"
        )
    page = open_page(browser, url)
    expect(page.locator(".lf-notice")).to_be_hidden()

    with service_model.PageTransaction(serve.page_dir) as transaction:
        assert transaction.set_stream_reply_state(
            "codex-thread", "leaf-turn", attempt, "Draft", "interrupted"
        )
    told(page)
    expect(page.locator(".lf-notice")).to_have_text("Response interrupted")
    expect(page.locator(".lf-live")).to_have_text("Response interrupted")


def test_deferred_notice_describes_only_the_current_message_version(browser, serve):
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    page.evaluate("""async () => {
      const {setNoticeContext} = await window.__lfRuntimeImport('/runtime/notifications.js');
      setNoticeContext(true);
    }""")

    original = conversation_model.cmd_comment(
        serve.page_dir, None, None, None, "Initial note.", None
    )
    told(page)
    expect(page.locator(".lf-notice")).to_be_hidden()
    conversation_model.cmd_edit(serve.page_dir, original["id"], "Current note.")
    told(page)

    page.evaluate("""async () => {
      const {setNoticeContext} = await window.__lfRuntimeImport('/runtime/notifications.js');
      setNoticeContext(false);
    }""")
    expect(page.locator(".lf-notice")).to_have_text(re.compile(r".+ updated a comment"))


@pytest.mark.parametrize(
    ("status", "words"),
    [
        ("succeeded", "Request succeeded"),
        ("failed", "Request failed; Input needed"),
    ],
)
def test_native_request_outcome_uses_the_same_notice_as_a_reopened_ask(
    browser, serve, status, words
):
    page = open_page(browser, live_url(serve(COMMAND_HUB_EXAMPLE)))
    expect(page.locator(".lf-notice")).to_be_hidden()
    with sending(page, "the native request"):
        page.locator("#dedupe-operations").get_by_role(
            "button", name="Restart with a fresh worker"
        ).click()
    [request] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "request"
    ]
    requests_model.cmd_receipt(serve.page_dir, request["id"], status, "Host outcome")
    told(page)
    expect(page.locator(".lf-notice")).to_have_text(words)
    expect(page.locator(".lf-live")).to_have_text(words)


def test_initial_history_and_repeated_stage_readings_are_quiet(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What changed?")
    conversation_model.cmd_reply(
        serve.page_dir, root, "The initial historical answer.", None, for_event=root
    )
    page = open_page(browser, url)
    expect(page.locator(".lf-notice")).to_be_hidden()

    # A fresh accepted status reading must not rediscover historical content.
    session_model.cmd_status(serve.page_dir, "idle", "done")
    told(page)
    expect(page.locator(".lf-notice")).to_be_hidden()
    assert "replied" not in page.locator(".lf-live").text_content()


def test_page_availability_announces_once_while_work_stage_changes_remain_quiet(
    browser, serve
):
    url = serve(PANEL_PAGE)
    session_model.cmd_status(serve.page_dir, "idle", "done")
    page = open_page(browser, url)
    expect(page.locator(".lf-notice")).to_be_hidden()

    session_model.cmd_status(serve.page_dir, "working", "Checking the page")
    told(page)
    expect(page.locator(".lf-notice")).to_have_text("Agent active on this page")
    expect(page.locator(".lf-live")).to_have_text("Agent active on this page")
    expect(page.locator(".lf-notice")).to_be_hidden(timeout=6000)

    session_model.cmd_status(serve.page_dir, "working", "Using a tool")
    told(page)
    expect(page.locator(".lf-notice")).to_be_hidden()
