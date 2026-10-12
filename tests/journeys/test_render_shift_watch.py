"""The browser fixture fails the layout shifts the "Stability" rule forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""

from datetime import datetime, timedelta

import pytest
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import ASK_PAGE
from render_harness import (
    judge_watches,
    leaf_page,
    open_page,
    resized,
)


@pytest.mark.parametrize("surface", ["card", "inline"])
def test_message_age_may_shift_metadata_but_leaves_the_thread_in_place(
    browser, serve, surface
):
    """Age advances while the thread and its controls stay put.

    Metadata may move or stay reserved. The passive-region fault controls above
    exercise the watcher's permitted motion independently of this surface's layout.
    """
    source = (
        leaf_page(
            "Inline task thread",
            '<h1 id="title">Before the frost</h1><lf-test-plan id="jobs" label="Jobs">'
            '<lf-test-task id="bracket" status="active" talk>'
            "<strong>Which jobs can share a visit?</strong></lf-test-task></lf-test-plan>",
        )
        if surface == "inline"
        else ASK_PAGE
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    resized(page, 1440, 900)
    if surface == "card":
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
        surface_root = page.locator(".lf-margin-preview")
    else:
        surface_root = page.locator(".lf-page-thread[data-lf-runtime]")
    header = surface_root.locator(".lf-msg-head").first
    receipt = header.locator(".lf-msg-sending")
    timestamp = header.locator("time")
    expect(receipt).to_have_text("Sent")
    expect(timestamp).to_have_text("just now")
    # Age changes are news after Chrome's recent-input grace, even when opening the
    # surface and resizing it happened immediately before this clock transition.
    rendered(page)
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    protected = surface_root.locator("b, button, leaf-text, .lf-msg-body")
    boxes = "nodes => nodes.map(node => node.getBoundingClientRect().toJSON())"
    before = protected.evaluate_all(boxes)
    assert before
    thread_before = surface_root.bounding_box()
    owner = header.locator("xpath=..")
    owner_before = owner.bounding_box()
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    now = datetime.now().astimezone()
    for delta, age in [
        (timedelta(minutes=1), "1m ago"),
        (timedelta(minutes=10), "10m ago"),
        (timedelta(hours=3), "3h ago"),
    ]:
        # Advance Leaf's calibrated server clock without changing the browser's
        # monotonic clock: native LayoutShift and frame readings must share time.
        page.evaluate(
            """async now => {
              const clock = await window.__lfRuntimeImport('/runtime/presence.js');
              const {reportPageError} = await window.__lfRuntimeImport('/runtime/layer-client.js');
              clock.observeServerNow(now);
              await clock.tickClock(reportPageError);
            }""",
            (now + delta).isoformat(),
        )
        expect(timestamp).to_have_text(age)
        expect(receipt).to_have_text("Sent")
        judge_watches()
        assert surface_root.bounding_box() == thread_before
        assert owner.bounding_box() == owner_before
        assert protected.evaluate_all(boxes) == before
