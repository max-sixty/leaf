"""Meaningful notices from successfully presented server readings."""

import re

from interact_support import declare_idle, working
from leaf import thread as thread_model
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    panel_comment,
)
from render_harness import open_page, panel_field, told


def said(page):
    """The panel's empty field, whose placeholder says a passing notice."""
    return expect(panel_field(page))


def test_deferred_notice_describes_only_the_current_message_version(browser, serve):
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    page.keyboard.press("g")

    original = thread_model.cmd_comment(
        serve.page_dir, None, None, None, "Initial note.", None
    )
    told(page)
    thread_model.cmd_edit(serve.page_dir, original["id"], "Current note.")
    told(page)

    page.keyboard.press("Escape")
    said(page).to_have_attribute("placeholder", re.compile(r".+ edited a comment"))


def test_initial_history_and_repeated_stage_readings_are_quiet(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What changed?")
    thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "The initial historical answer."
    )
    page = open_page(browser, url)
    said(page).not_to_have_attribute("placeholder", re.compile("replied"))

    # A fresh accepted status reading must not rediscover historical content.
    declare_idle(serve.page_dir)
    told(page)
    said(page).not_to_have_attribute("placeholder", re.compile("replied"))
    assert "replied" not in page.locator(".lf-live").text_content()


def test_page_availability_announces_once_while_work_stage_changes_remain_quiet(
    browser, serve
):
    url = serve(PANEL_PAGE)
    declare_idle(serve.page_dir)
    page = open_page(browser, url)
    available = re.compile(r".+ active on this page")
    said(page).not_to_have_attribute("placeholder", available)

    working(serve.page_dir, "Checking the page")
    told(page)
    said(page).to_have_attribute("placeholder", available)
    expect(page.locator(".lf-live")).to_have_text(available)
    said(page).not_to_have_attribute("placeholder", available)

    working(serve.page_dir, "Using a tool")
    told(page)
    said(page).not_to_have_attribute("placeholder", available)
