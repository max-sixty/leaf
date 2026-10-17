"""Whole journeys through a served page, with the helpers several of them share."""

from browser.threads import open_panel_thread
from playwright.sync_api import expect
from render_harness import PANEL, panel_settled

THREADS_VIEW = '.lf-fp-view[data-view="threads"]:not([data-leaving])'


def listed_threads(page):
    """The keys of every thread the panel's Threads view lists, open and resolved, read
    by opening Threads under each filter; Threads is put away after."""
    if page.locator(PANEL).get_attribute("data-open") != "threads":
        page.locator(".lf-fp-threads").click()
        panel_settled(page, view="threads")
    keys = []
    for name in ("Open", "Resolved"):
        page.locator(".lf-fp-filters button").filter(has_text=name).click()
        keys += page.locator(f"{THREADS_VIEW} .lf-fp-thread").evaluate_all(
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
