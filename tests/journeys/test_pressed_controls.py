"""The press check over the panel's views, on every corpus page.

`browser/widgets/test_pressed_controls.py` holds the rule and presses each bundled
package's widgets. Leaf's own controls that send a reader's gestures stand in the
floating panel's views: in On me, where a reader answers a question and ends a to-do,
and in a thread's view, where they resolve and reopen the thread and react to its
messages. A thread lives only in a page's log, so this opens On me and then each
thread the Threads view lists, on every corpus page with its log, and presses every
control in the view. A thread's card in the margin offers the same gestures, but each
takes away the control it was pressed on, so it leaves nothing to check."""

import pytest
from browser.widgets.test_pressed_controls import open_served, press_each_control
from render_harness import (
    CORPUS_SOURCES,
    open_threads,
    panel_settled,
    panel_view,
    show_resolved,
)

# A view of the panel and the actions on what it shows, such as a thread's Resolve,
# but not the way out of it, its tabs, or the panel's own row.
VIEWS = ".lf-fp-view, .lf-fp-aux"


def open_on_me(page):
    """Open On me by its keys, unless it stands open already, since the same keys put
    it away."""
    if page.locator(".lf-floating-panel").get_attribute("data-open") != "queue":
        page.locator("body").focus()
        page.keyboard.press("g")
        page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")


def open_thread(page, key):
    """The thread `key`'s view, from its row in Threads, folded under Resolved once it
    is resolved."""
    open_threads(page)
    row = page.locator(f'{panel_view("threads")} .lf-fp-thread[data-key="{key}"]')
    if not row.count():
        show_resolved(page)
    row.click()
    panel_settled(page, view="thread")


@pytest.mark.parametrize("source", CORPUS_SOURCES, ids=lambda source: source.stem)
def test_a_pressed_panel_control_keeps_its_face_and_takes_the_next_press(
    browser, serve, source
):
    """Each control in On me and in each listed thread's view keeps its face while
    its gesture travels and takes the next press (`press_each_control`). The sweep
    presses in On me wherever it lists an item, and reaches each thread's Resolve or
    Reopen."""
    page = open_served(browser.unwatched, serve(source))
    open_on_me(page)
    owed = page.locator(f"{panel_view('queue')} .lf-fp-on-item").count()
    answered, _, failures = press_each_control(page, VIEWS, lambda: open_on_me(page))
    open_threads(page)
    if page.locator(f"{panel_view('threads')} .lf-fp-settled").count():
        show_resolved(page)
    keys = page.locator(f"{panel_view('threads')} .lf-fp-thread").evaluate_all(
        "(rows) => rows.map((row) => row.dataset.key)"
    )
    unsettled = []
    for key in keys:
        open_thread(page, key)
        _, sent, found = press_each_control(
            page, VIEWS, lambda key=key: open_thread(page, key)
        )
        failures += found
        if not {kind for _, kind in sent} & {"resolve", "unresolve"}:
            unsettled.append(key)
    assert not failures, "\n".join(failures)
    assert answered or not owed, "On me lists items but the sweep pressed nothing"
    assert not unsettled, f"no settlement was checked for {unsettled} of {keys}"
