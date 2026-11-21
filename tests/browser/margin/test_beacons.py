"""Where an active thread stands while its margin entry is scrolled out of the window."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, resized, scroll_settled

from browser.margin import _comment_on

BODY = """
<p id="early">The early paragraph, whose thread has a reply waiting.</p>
<div style="height: 250vh"></div>
<p id="late">The late paragraph, whose thread waits on the agent.</p>
<div style="height: 250vh"></div>
<p id="end">The end.</p>
"""
# The same paragraphs, and the same paragraphs under a page's sticky tab strip, whose
# rows pass under the strip in frames it cuts rather than in the margin's root lane.
PAGES = {
    "plain": leaf_page("Beacons", f'<h1 id="title">Beacons</h1>{BODY}'),
    "under a tab strip": leaf_page(
        "Beacons under tabs",
        f"""<h1 id="title">Beacons under tabs</h1>
<lf-tabs id="tabs" flow="page">
  <lf-tab id="body-tab" label="Body">{BODY}</lf-tab>
  <lf-tab id="other-tab" label="Other"><p id="other">Another tab.</p></lf-tab>
</lf-tabs>""",
    ),
}
EARLY = {**_comment_on("early", "Why this order?"), "id": "e" * 32}
REPLY = {
    "kind": "reply",
    "author": "agent",
    "agent": "Claude",
    "parent": EARLY["id"],
    "responds": EARLY["id"],
    "revision": 1,
    "text": "Setup has to finish before the turn starts.",
    "id": "f" * 32,
}
LATE = {**_comment_on("late", "Is this step needed?"), "id": "1" * 32}

UP = '.lf-margin-beacon[data-lf-towards="up"]'
DOWN = '.lf-margin-beacon[data-lf-towards="down"]'
# What a press at the middle of a box lands on: whether the margin entry over a beacon
# hides it.
LANDS_ON = """box => {
    const r = box.getBoundingClientRect();
    return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)
        ?.closest('.lf-margin-beacon, .lf-margin-cluster')?.className ?? null;
}"""


@pytest.mark.parametrize("page_name", PAGES)
def test_an_active_thread_off_the_window_shows_a_beacon_at_the_edge_toward_it(
    browser, serve, page_name
):
    """A thread with a reply the user hasn't read keeps a beacon at the edge of the
    window nearest its margin entry while the entry is out of the window, in the
    entry's column and clear of a sticky strip over the page; while the entry shows,
    it covers the beacon. A press on the beacon goes to the thread. A thread with
    nothing new for the user keeps none."""
    page = open_page(browser, serve(PAGES[page_name], events=[EARLY, REPLY, LATE]))
    resized(page, 1440, 800)
    entry = page.locator('[data-lf-margin-for="early"] .lf-margin-marker')
    up, down = page.locator(UP), page.locator(DOWN)
    # Only the thread with the unread reply is active.
    expect(up).to_have_count(1)
    expect(down).to_have_count(1)
    assert "lf-margin-cluster" in up.evaluate(LANDS_ON)
    assert "lf-margin-cluster" in down.evaluate(LANDS_ON)

    page.mouse.wheel(0, 1600)
    scroll_settled(page)
    expect(entry).not_to_be_in_viewport()
    box, column = up.bounding_box(), entry.bounding_box()
    head = page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--lf-root-headers')) || 0"
    )
    assert head <= box["y"] <= head + 12, (box, head)
    assert column["x"] <= box["x"] and box["x"] + box["width"] <= column["x"] + 32
    assert "lf-margin-beacon" in up.evaluate(LANDS_ON)
    # The beacon toward the foot stays by the entry, above the window with it.
    assert down.bounding_box()["y"] < 0

    up.click()
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_visible()
    expect(entry).to_be_in_viewport()
    # Read, the thread has nothing new, so its beacons go.
    expect(up).to_have_count(0)
