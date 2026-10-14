"""Meaningful notices from successfully presented server readings."""

import re

from interact_support import declare_idle, working
from leaf import thread as thread_model
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    panel_comment,
)
from render_harness import open_page, told


def test_deferred_notice_describes_only_the_current_message_version(browser, serve):
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    page.keyboard.press("g")

    original = thread_model.cmd_comment(
        serve.page_dir, None, None, None, "Initial note.", None
    )
    told(page)
    expect(page.locator(".lf-notice")).to_be_hidden()
    thread_model.cmd_edit(serve.page_dir, original["id"], "Current note.")
    told(page)

    page.keyboard.press("Escape")
    expect(page.locator(".lf-notice")).to_have_text(re.compile(r".+ updated a comment"))


def test_initial_history_and_repeated_stage_readings_are_quiet(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What changed?")
    thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "The initial historical answer."
    )
    page = open_page(browser, url)
    expect(page.locator(".lf-notice")).to_be_hidden()

    # A fresh accepted status reading must not rediscover historical content.
    declare_idle(serve.page_dir)
    told(page)
    expect(page.locator(".lf-notice")).to_be_hidden()
    assert "replied" not in page.locator(".lf-live").text_content()


def test_page_availability_announces_once_while_work_stage_changes_remain_quiet(
    browser, serve
):
    url = serve(PANEL_PAGE)
    declare_idle(serve.page_dir)
    page = open_page(browser, url)
    expect(page.locator(".lf-notice")).to_be_hidden()

    working(serve.page_dir, "Checking the page")
    told(page)
    expect(page.locator(".lf-notice")).to_have_text("Agent active on this page")
    expect(page.locator(".lf-live")).to_have_text("Agent active on this page")
    expect(page.locator(".lf-notice")).to_be_hidden()

    working(serve.page_dir, "Using a tool")
    told(page)
    expect(page.locator(".lf-notice")).to_be_hidden()
