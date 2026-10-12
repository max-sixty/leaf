"""Meaningful notices from successfully presented server readings."""

import re

from interact_support import record_claim
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import thread as thread_model
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    panel_comment,
)
from render_harness import open_page, told


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

    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "I changed the route. Does this answer your question?",
        ask=True,
    )
    told(page)
    notice = re.compile(r".+ replied; Input needed")
    expect(page.locator(".lf-notice")).to_have_text(notice)
    expect(page.locator(".lf-live")).to_have_text(notice)
    expect(toggle).to_be_focused()


def test_a_new_agent_comment_is_announced_without_moving_focus(browser, serve):
    page = open_page(browser, serve(PANEL_PAGE))
    toggle = page.locator(".lf-threads-toggle")
    toggle.focus()
    expect(toggle).to_be_focused()
    expect(page.locator(".lf-notice")).to_be_hidden()

    thread_model.cmd_comment(
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

    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "The agent turn ended before completion.",
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
    lease = leases_model.take_lease(
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
