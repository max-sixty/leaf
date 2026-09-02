"""Added-option presentation and replay tests."""

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    DECISION_PAGE,
    DECISION_WITH_CONTEXT_PAGE,
    open_page,
    round_trip,
    sent_events,
    told,
    undo,
)

pytestmark = pytest.mark.nightly


def test_an_add_field_reconnects_to_its_shared_draft(browser, serve, one_reader):
    """Moving the widget restores draft delivery without duplicating its form."""
    url = serve(DECISION_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)

    second.evaluate("""() => {
        const group = document.getElementById("jobs");
        group.remove();
        document.querySelector("main").append(group);
    }""")
    text = "A shared answer after the question moves."
    first.locator("#jobs > .lf-another input").fill(text)

    expect(second.locator("#jobs > .lf-another")).to_have_count(1)
    expect(second.locator("#jobs > .lf-another input")).to_have_value(text)
    assert first_errors == []
    assert second_errors == []
    first.close()
    second.close()


def test_enter_keeps_another_option_separate_from_a_clarification_thread(
    browser, serve
):
    """The add-option field is not replaced by an exact-section conversation."""
    url = serve(DECISION_WITH_CONTEXT_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "anchor": {"section": "storage-options"},
            "text": "Archive them locally or remotely?",
        },
    )

    page, errors = open_page(browser, url)
    mark = page.locator("#storage-evict .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()
    expect(page.locator("#storage-options > .lf-conversation")).to_have_count(0)

    page.keyboard.press("Enter")
    expect(page.locator("#storage-options > .lf-another input")).to_be_focused()
    expect(page.locator("#storage-options > lf-option[chosen]")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(mark).to_be_focused()

    # c keeps its page-wide meaning: it comments on the focused option instead of being a
    # second spelling for adding an answer. Its own Escape restores the same mark too.
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#storage-options > .lf-another input")).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(mark).to_be_focused()
    assert errors == []
    page.close()


def test_another_option_becomes_a_real_option_without_starting_a_thread(browser, serve):
    """The answer the author missed joins the control and travels as selection state.

    It is not a comment with a special response contract: the reader has supplied an
    answer, not opened a conversation. The standing action carries every generated
    option so a later ordinary pick and a reload retain the same set of alternatives.
    """
    url = serve(DECISION_PAGE)
    page, errors = open_page(browser, url)
    d = serve.page_dir

    expect(page.locator("#jobs > .lf-conversation")).to_have_count(0)
    added = page.locator("#jobs > .lf-another")
    assert added.count() == 1, (
        f"the add-option cell was not rendered: {errors}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    field = added.get_by_role("textbox", name="Another option", exact=True)
    field.fill("Insulate the camera battery")
    added.get_by_role("button", name="Add option", exact=True).click()
    round_trip(page)

    new_option = page.locator("#jobs > lf-option[data-lf-added]")
    assert new_option.count() == 1, (
        f"the added option did not stand: {errors}; events={sent_events(d)}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    expect(new_option).to_contain_text("Insulate the camera battery")
    expect(new_option).to_have_attribute("chosen", "")
    event = [
        event
        for event in sent_events(d)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ][-1]
    assert event["action"] == "choose"
    assert event["detail"] == {
        "options": [new_option.get_attribute("id")],
        "additions": {new_option.get_attribute("id"): "Insulate the camera battery"},
    }
    assert event["generated"] == [new_option.get_attribute("id")]
    assert not [event for event in sent_events(d) if event["kind"] == "comment"]

    page.locator("#job-heater").click()
    round_trip(page)
    latest = [
        event
        for event in sent_events(d)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ][-1]
    assert latest["detail"]["additions"] == event["detail"]["additions"]
    assert latest["generated"] == event["generated"]

    page.reload(wait_until="load")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)
    expect(page.locator("#job-heater")).to_have_attribute("chosen", "")

    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_attribute(
        "chosen", ""
    )
    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(0)
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(0)
    assert errors == []
    page.close()


def test_an_arrival_cannot_hide_a_question_draft(browser, serve):
    """An exact-section thread cannot take an unsent option's field.

    The draft remains part of the decision and still becomes a real option. The thread
    stays separate: adding the option sends an action, not a second comment.
    """
    page, errors = open_page(browser, serve(DECISION_PAGE))
    d = serve.page_dir
    first = page.locator("#jobs > .lf-another input")
    draft = "Keep this answer even if another thread arrives first."
    first.fill(draft)

    external = events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Indexer",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "A separate note on this question.",
        },
    )
    told(page)
    expect(page.locator("#jobs > .lf-conversation")).to_have_count(0)
    expect(first).to_be_visible()
    expect(first).to_have_value(draft)

    page.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add option", exact=True
    ).click()
    round_trip(page)
    added = page.locator("#jobs > lf-option[data-lf-added]")
    expect(added).to_contain_text(draft)
    expect(added).to_have_attribute("chosen", "")
    roots = [e for e in sent_events(d) if e["kind"] == "comment"]
    assert [(e["anchor"], e["text"]) for e in roots] == [
        ({"section": "jobs"}, "A separate note on this question."),
    ]
    action = next(e for e in sent_events(d) if e["kind"] == "action")
    assert action["detail"]["additions"] == {added.get_attribute("id"): draft}
    assert action["generated"] == [added.get_attribute("id")]
    page.locator(".lf-threads-toggle").click()
    expect(page.locator(f'.lf-thread[data-id="{external["id"]}"]')).to_have_count(1)
    assert errors == []
    page.close()
