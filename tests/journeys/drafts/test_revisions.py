"""Tests scheduled by the measured cost of their boundary."""

import os

import pytest
from browser.drafts import editing_revision_source
from playwright.sync_api import expect
from render_harness import (
    open_page,
    restarting,
    round_trip,
    told,
    wait_for_revision,
    write,
)

from leaf.log import event_log as events_model
from leaf.pages import hosting as hosting_model
from leaf.pages import vendoring as vendoring_model
from leaf.records import revisioning as revisioning_model
from leaf.serving import event_endpoint as endpoint_model
from leaf.source.registry.storage import layer_packages

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_re_vendor_waits_for_the_reply_being_written(browser, serve):
    """A re-vendor replaces the page's server under a tab whose user is writing a
    reply. The tab hears the newer layer as a revision and holds it while the words are
    unsent, then follows it once they are sent, rather than reloading mid-keystroke."""
    serve(editing_revision_source("before"))
    page_dir = serve.page_dir
    with hosting_model.TemporaryPageServer(page_dir) as before:
        page = open_page(browser, before.url)
        page.locator("#passage").click(click_count=3)
        page.keyboard.press("c")
        write(page.locator(".lf-composer leaf-text"), "An anchored root.")
        page.keyboard.press("Control+Enter")
        round_trip(page)
        root = next(
            event["id"]
            for event in events_model.read_events(page_dir)
            if event["kind"] == "comment"
        )
        page.keyboard.press("c")
        editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
        words = "Half a thought the reload must not take"
        write(editor, words)
        birth = page.evaluate("performance.timeOrigin")
        # A newer layer: the page selects one more package. Its record names each
        # package copy relative to the page, and init resolves a path from where it
        # runs.
        newer = page_dir.parent / "newer-layer"
        newer.mkdir()
        (newer / "overrides.css").write_text("/* a newer layer */\n")
        held = tuple(
            "./" + os.path.relpath(page_dir / value)
            if value.startswith("./")
            else value
            for value in layer_packages(page_dir) or ()
        )
        vendoring_model.cmd_init(page_dir, (*held, "./" + os.path.relpath(newer)))
        revised = revisioning_model.activate_source(page_dir)
        assert revised.error is None
        with restarting(page):
            before.close()
            # `serve` ends it with its own server, once the test body's pages
            # have painted their last frame.
            serve.servers.append(
                hosting_model.TemporaryPageServer(
                    page_dir, token=before.token, port=before.port
                ).start()
            )
            # The tab has read the state naming the newer revision.
            told(page)
    # A second of news from the replaced server, which is where a token the tab
    # refused would have sent it to reload.
    for _ in range(4):
        with page.expect_response("**/api/news*"):
            pass
    assert page.evaluate("performance.timeOrigin") == birth
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", words)
    page.keyboard.press("Control+Enter")
    assert revised.revision is not None
    wait_for_revision(page, revised.revision)
    assert page.evaluate("performance.timeOrigin") != birth
    # Bookkeeping may follow delivery; make that order deterministic.
    accepted, _ = endpoint_model.accept_event(
        page_dir,
        {"kind": "seen", "revision": revised.revision},
    )
    assert accepted == 200
    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply" and event["parent"] == root
    ]
    assert len(replies) == 1
    assert replies[0]["author"] == "user"
    assert replies[0]["text"] == words
