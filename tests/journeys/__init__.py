"""Whole journeys through a served page, with the helpers several of them share."""

from browser.threads import open_panel_thread
from playwright.sync_api import expect
from render_harness import (
    PANEL,
    close_panel_menu,
    open_threads,
    panel_menu,
    panel_settled,
    panel_view,
)

from leaf import event_log as events_model


def listed_threads(page):
    """The keys of every thread the panel's Threads view lists, the open ones and then
    those under Resolved; Threads is put away after."""
    open_threads(page)
    keys = page.locator(f"{panel_view('threads')} .lf-fp-thread").evaluate_all(
        "rows => rows.map(row => row.dataset.key)"
    )
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    return keys


def detached_threads(page, thread_ids):
    """Which of `thread_ids` the panel's view of the thread quotes as detached from
    the page: its quote stands but names words the page no longer holds."""
    detached = set()
    for thread_id in thread_ids:
        view = open_panel_thread(page, thread_id)
        expect(view).to_be_visible()
        if view.locator(".lf-fp-quote.detached").count():
            detached.add(thread_id)
    if page.locator(PANEL).get_attribute("data-open") is not None:
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
    return detached


def first_thread_quote(page, page_dir):
    """The quote heading the first thread's view in the panel, opened for it."""
    first = next(
        event["id"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment"
    )
    return open_panel_thread(page, first).locator(".lf-fp-quote")


def expect_showing(page, version):
    """The leaf's menu names the version the page shows on its Versions row; read it
    and put the menu away."""
    expect(
        panel_menu(page).locator('.lf-fp-item[data-row="versions"]')
    ).to_contain_text(f"v{version}")
    close_panel_menu(page)
