"""Meaningful notices from successfully presented server readings."""

import re

from interact_support import declare_idle, record_claim, working
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    panel_comment,
)
from render_harness import open_page, panel_field, told

from leaf import leases as leases_model
from leaf import service as service_model
from leaf import thread as thread_model


def said(page):
    """The panel's empty field, whose placeholder says a passing notice."""
    return expect(panel_field(page))


def test_a_reply_asking_the_user_is_heard_whole_and_shown_as_the_question(
    browser, serve
):
    """The live region hears the reply, whose question is the same news; the panel's
    seat shows only the question, since the On me mark's dot already shows the reply."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What should change?")
    page = open_page(browser, url)
    toggle = page.locator(".lf-fp-on-user")
    toggle.focus()
    expect(toggle).to_be_focused()
    said(page).not_to_have_attribute("data-says", "notice")

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "I changed the route.",
        markup='<lf-ask id="route-answers">Does this answer your question?</lf-ask>',
    )
    told(page)
    # One fact: the question is the reply, not a second clause beside it.
    expect(page.locator(".lf-live")).to_have_text(
        re.compile(r"^I changed the route\.(?! ·)")
    )
    said(page).to_have_attribute("placeholder", re.compile("^New on me"))
    said(page).not_to_have_attribute("placeholder", re.compile("changed the route"))
    expect(toggle).to_be_focused()


def test_a_new_agent_comment_is_announced_without_moving_focus(browser, serve):
    """An agent's new comment is heard, and the panel's seat keeps the agent's status."""
    page = open_page(browser, serve(PANEL_PAGE))
    toggle = page.locator(".lf-fp-on-user")
    toggle.focus()
    expect(toggle).to_be_focused()
    said(page).not_to_have_attribute("data-says", "notice")

    thread_model.cmd_comment(
        serve.page_dir, None, None, None, "A new page-wide agent note.", None
    )
    told(page)
    expect(page.locator(".lf-live")).to_have_text(
        re.compile(r"^A new page-wide agent note\.")
    )
    said(page).not_to_have_attribute("placeholder", re.compile("page-wide agent note"))
    expect(toggle).to_be_focused()


def test_terminal_failure_is_a_response_notice_not_an_agent_reply(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Please run this request.")
    page = open_page(browser, url)
    said(page).not_to_have_attribute("data-says", "notice")

    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The agent turn ended before completion.",
        failure="turn_failed",
        attempt="response-failed-attempt",
    )
    told(page)
    said(page).to_have_attribute("placeholder", re.compile("^Couldn't answer"))
    expect(page.locator(".lf-live")).to_have_text("Couldn't answer")


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
        transaction.set_status("waiting")
        transaction.set_stream_reply(
            "codex-thread",
            "leaf-turn",
            {"parent": root, "responds": root},
            attempt,
            None,
            "Draft",
            "active",
        )
    page = open_page(browser, url)
    said(page).not_to_have_attribute("data-says", "notice")

    with service_model.PageTransaction(serve.page_dir) as transaction:
        assert transaction.set_stream_reply_state(
            "codex-thread", "leaf-turn", attempt, "Draft", "interrupted"
        )
    told(page)
    said(page).to_have_attribute("placeholder", re.compile("^Interrupted mid-answer"))
    expect(page.locator(".lf-live")).to_have_text("Interrupted mid-answer")


def test_an_edited_agent_message_is_heard_as_an_edit(browser, serve):
    """An edit the agent makes is heard as an edit, even while a command holds the
    seat, and the seat never shows it."""
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    page.keyboard.press("g")

    original = thread_model.cmd_comment(
        serve.page_dir, None, None, None, "Initial note.", None
    )
    told(page)
    thread_model.cmd_edit(serve.page_dir, original["id"], "Current note.")
    told(page)

    expect(page.locator(".lf-live")).to_have_text(
        re.compile(r"^Edited: Current note\.")
    )
    page.keyboard.press("Escape")
    said(page).not_to_have_attribute("placeholder", re.compile("Current note"))


def test_initial_history_and_repeated_stage_readings_are_quiet(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What changed?")
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The initial historical answer.",
    )
    page = open_page(browser, url)
    history = re.compile("The initial historical answer")
    said(page).not_to_have_attribute("placeholder", history)

    # A fresh accepted status reading must not rediscover historical content.
    declare_idle(serve.page_dir)
    told(page)
    said(page).not_to_have_attribute("placeholder", history)
    assert (
        "The initial historical answer" not in page.locator(".lf-live").text_content()
    )


def test_the_agent_starting_work_is_said_by_the_status_not_a_notice(browser, serve):
    """The status line names the agent's work in the seat a notice would take, so no
    notice stands in front of it, and a later step changes only the status."""
    url = serve(PANEL_PAGE)
    declare_idle(serve.page_dir)
    page = open_page(browser, url)

    for line in ("Checking the page", "Using a tool"):
        working(serve.page_dir, line)
        told(page)
        said(page).to_have_attribute("data-says", "status")
        said(page).to_have_attribute("placeholder", re.compile(f"^{line}"))
