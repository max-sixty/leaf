"""Whole journeys through a served page, with the helpers several of them share."""

from browser.threads import open_panel_thread
from leaf import event_log as events_model
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


# Where the panel says a passing notice: the empty field's placeholder, the line over a
# focused field, or, over an open view, the leaf's peek (floating-panel.js).
_SAYS = """() => [document.querySelector('.lf-fp-field leaf-text')?.getAttribute('placeholder'),
  ...[...document.querySelectorAll('.lf-fp-context, .lf-fp-peek')].map((n) => n.textContent)]
  .filter(Boolean).join(' | ')"""


def expect_panel_says(page, words):
    """Wait until the panel says `words` in a passing notice, wherever it says one."""
    page.wait_for_function(f"(words) => ({_SAYS})().includes(words)", arg=words)


def panel_says(page):
    """Everything the panel says in passing now, joined."""
    return page.evaluate(_SAYS)


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
