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
    first.locator("#jobs > .lf-another textarea").fill(text)

    expect(second.locator("#jobs > .lf-another")).to_have_count(1)
    expect(second.locator("#jobs > .lf-another textarea")).to_have_value(text)
    assert first_errors == []
    assert second_errors == []
    first.close()
    second.close()


def test_the_add_field_previews_the_option_it_will_make(browser, serve):
    """The reader writes on the same line and in the same voice as the options.

    The trailing action stays out of an empty row, then submits without borrowing the
    selection mark's circle. It remains a full-sized pointer target aligned with the
    last line as the textarea grows.
    """
    page, errors = open_page(browser, serve(DECISION_PAGE))
    option = page.locator("#job-camera")
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    add = form.get_by_role("button", name="Add option", exact=True, include_hidden=True)

    typography = """el => { const s = getComputedStyle(el);
                             return [s.fontFamily, s.fontSize, s.lineHeight]; }"""
    assert field.evaluate(typography) == option.evaluate(typography)
    option_text_x = option.evaluate(
        """el => {
             const text = [...el.childNodes].find(
               n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
             const range = document.createRange();
             range.selectNodeContents(text);
             return range.getBoundingClientRect().x;
           }"""
    )
    assert abs(field.bounding_box()["x"] - option_text_x) < 0.5
    inner_height = """el => { const s = getComputedStyle(el);
                               return el.getBoundingClientRect().height
                                 - parseFloat(s.borderTopWidth)
                                 - parseFloat(s.borderBottomWidth); }"""
    assert abs(form.evaluate(inner_height) - option.evaluate(inner_height)) < 0.5

    card_words = page.locator("#br-steel > strong")
    card_field = page.locator("#bracket > .lf-another textarea")
    assert card_field.evaluate(typography) == card_words.evaluate(typography)
    assert abs(card_field.bounding_box()["x"] - card_words.bounding_box()["x"]) < 0.5

    expect(add).to_have_text("Add")
    expect(add).to_be_hidden()
    expect(add).to_have_attribute("aria-disabled", "true")
    empty_field_box = field.bounding_box()
    field.fill("Portrait sketch")
    expect(add).to_be_visible()
    expect(add).to_have_attribute("aria-disabled", "false")
    expect(add).to_have_css("opacity", "1")
    aim_floor = page.locator("html").evaluate(
        "el => parseFloat(getComputedStyle(el).getPropertyValue('--aim-floor'))"
    )
    form_box = form.bounding_box()
    field_box = field.bounding_box()
    assert field_box == empty_field_box
    add_box = add.bounding_box()
    assert add_box["width"] >= aim_floor
    assert add_box["height"] >= aim_floor
    assert (
        abs(field_box["y"] + field_box["height"] - add_box["y"] - add_box["height"]) < 2
    )
    field.fill("First line\nSecond line\nThird line")
    grown_field_box = field.bounding_box()
    grown_add_box = add.bounding_box()
    assert grown_field_box["height"] > field_box["height"]
    assert (
        abs(
            grown_field_box["y"]
            + grown_field_box["height"]
            - grown_add_box["y"]
            - grown_add_box["height"]
        )
        < 2
    )
    face = """el => { const s = getComputedStyle(el);
                       return [s.backgroundColor, s.borderTopColor, s.borderTopStyle,
                               s.borderTopWidth, s.borderRadius, s.color]; }"""
    add_face = add.evaluate(face)
    ordinary_face = page.locator("body").evaluate(
        """body => {
          const probe = document.createElement("button");
          probe.className = "lf-btn";
          body.append(probe);
          const s = getComputedStyle(probe);
          const result = [s.backgroundColor, s.borderTopColor, s.borderTopStyle,
                          s.borderTopWidth, s.borderRadius, s.color];
          probe.remove();
          return result;
        }"""
    )
    assert add_face == ordinary_face
    page.keyboard.press("Tab")
    expect(add).to_be_focused()

    page.locator("html").evaluate("el => el.style.setProperty('--aim-floor', '44px')")
    form_box = form.bounding_box()
    add_box = add.bounding_box()
    assert form_box["height"] >= 44
    assert add_box["y"] >= form_box["y"]
    assert add_box["y"] + add_box["height"] <= form_box["y"] + form_box["height"]
    assert errors == []
    page.close()


def test_an_option_mark_keeps_addition_and_clarification_as_separate_routes(
    browser, serve
):
    """The add form stays in Tab order while c opens a clarification thread."""
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

    # Enter is not navigation from a checkbox. It neither chooses the option nor enters
    # the add field; the field is an ordinary later stop in the Tab order.
    page.keyboard.press("Enter")
    expect(mark).to_be_focused()
    expect(page.locator("#storage-options > .lf-another textarea")).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[chosen]")).to_have_count(0)

    # c keeps its page-wide meaning: it comments on the focused option rather than adding
    # an answer. Its own Escape restores the same mark.
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#storage-options > .lf-another textarea")).not_to_be_focused()
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
    add = added.get_by_role("button", name="Add option", exact=True)
    add.focus()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(field).to_be_focused()

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
    first = page.locator("#jobs > .lf-another textarea")
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
