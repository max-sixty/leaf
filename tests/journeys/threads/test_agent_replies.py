"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.threads import PANEL_NEWS, claim_for_codex, reply_by_keyboard
from browser.threads.test_agent_replies import TRANSCRIPT_ORDER
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import open_page, sending, told

from leaf.agents import thread as thread_model
from leaf.log import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_a_reply_sent_after_progress_stands_below_it(browser, serve, request):
    """A thread reads in the order its messages were said, and nothing moves above the
    user's message as the agent goes on. The agent's progress line was said before the
    user's next message, so that message stands below it, both as the send draws it
    and once the log holds it; the agent's next step stands below the message, the
    earlier one staying where it was, still. The answer then ends both steps,
    including the one above the user's message."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    thread_model.post_reply(
        serve.page_dir,
        {"parent": root, "responds": root},
        "Checking the board",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    page = open_page(browser, url)
    view = reply_by_keyboard(page, root)
    expect(view.locator(".lf-thread-working")).to_be_visible()
    page.keyboard.type("And the changelog?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(
        view.locator(".lf-msg[data-lf-author=user]", has_text="And the changelog?")
    ).to_be_visible()
    assert view.evaluate(TRANSCRIPT_ORDER)[-2:] == ["working", "And the changelog?"]
    told(page)
    assert view.evaluate(TRANSCRIPT_ORDER)[-2:] == ["working", "And the changelog?"]

    # The agent's next step is said after the user's message, so it stands below it.
    asked = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply" and event["author"] == "user"
    )
    thread_model.post_reply(
        serve.page_dir,
        {"responds": asked["id"]},
        "Reading the changelog",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)
    assert view.evaluate(TRANSCRIPT_ORDER)[-3:] == [
        "working",
        "And the changelog?",
        "working",
    ]
    faces = view.locator(".lf-thread-working")
    expect(faces.first).not_to_have_attribute("data-lf-live", "")
    expect(faces.last).to_have_attribute("data-lf-live", "")
    expect(faces.last).to_have_text(re.compile("Reading the changelog"))

    # The answer ends both steps, including the one above the user's message.
    answer = thread_model.post_reply(
        serve.page_dir,
        {"responds": asked["id"]},
        "Recorded, with the changelog.",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)
    # Ending the step above the user's message waits for their reveal, so the
    # existing words do not move while they read.
    page.locator(PANEL_NEWS).click()
    expect(view.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')).to_be_visible()
    assert view.evaluate(TRANSCRIPT_ORDER) == [
        "Record the release",
        "And the changelog?",
    ]
    expect(view.locator(".lf-thread-working")).to_have_count(0)
