"""End-to-end journey and durable draft tests."""

import json

import pytest
from browser.threads import open_panel_thread
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_OBLIGATION_PAGE,
)
from render_cases_navigation import (
    JOURNEY_V1,
    compose,
)
from render_harness import (
    LONG_PAGE,
    draft_control,
    draft_key,
    holding,
    open_page,
    page_comment,
    panel_field,
    panel_settled,
    refuse,
    round_trip,
    stored_draft_settled,
    until_draft_settled,
    write,
)

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed

from browser.drafts import (
    cancel_draft,
    editing_reply_page,
    replace_editing_document,
)


def test_one_draft_edit_is_what_every_tab_of_the_page_shows(browser, serve, one_user):
    """An edit is one set of words wherever the user typed them, and the two halves
    of that fail in opposite directions. A keystroke has to reach the box the other tab
    has open, or two tabs hold two halves of one thought and whichever is closed takes
    its half with it. A settlement has to empty the other box, rather than leave it
    holding words the log already has — standing over a body replay is about to paint.

    A closed box stays closed for a keystroke made elsewhere: news arriving has no
    gesture behind it, and the words are there at the next opening either way."""
    url = serve(JOURNEY_V1)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_draft = first.locator("#draft-ops")
    second_draft = second.locator("#draft-ops")

    edited = "Run the migration after the backup."
    first_draft.locator(".lf-draft-body").dblclick()
    second_draft.locator(".lf-draft-body").dblclick()
    write(first_draft.locator("leaf-text"), edited)
    expect(second_draft.locator("leaf-text")).to_have_js_property("value", edited)

    draft_control(first, "save", "draft-ops").click()
    round_trip(first)
    expect(second_draft.locator("leaf-text")).to_have_count(0)
    # The body the other tab is left looking at is the log's, which is what closing the
    # box in front of it was for: lf-draft holds its drawing while an editor is open.
    expect(second_draft.locator(".lf-draft-body")).to_have_text(edited)
    assert stored_draft_settled(second, "edit:draft-ops")

    # A second edit, with only the first tab's box open. The store's value arriving is
    # the fact to consume before reading an absence: the storage event carrying it is
    # the same task that would have opened a box here.
    discarded = "This tab discards these words."
    first_draft.locator(".lf-draft-body").dblclick()
    write(first_draft.locator("leaf-text"), discarded)
    second.wait_for_function(
        """([key, text]) => JSON.parse(localStorage.getItem(key))?.text === text""",
        arg=[draft_key(second, "edit:draft-ops"), discarded],
    )
    assert second_draft.locator("leaf-text").count() == 0, (
        "the second tab opened an editor for a keystroke nobody made there"
    )
    cancel_draft(first)
    until_draft_settled(second, "edit:draft-ops")
    second_draft.locator(".lf-draft-body").dblclick()
    expect(second_draft.locator("leaf-text")).to_have_js_property("value", edited)

    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in events] == [edited]


def test_a_comment_being_typed_reaches_the_pages_other_tabs(browser, serve, one_user):
    """The general box and a thread's reply box are each one draft with a view in every
    tab. Both directions of the loop are here: words typed in one tab arrive in the
    other's box live, and a send there empties it — the distinction the store's own
    vocabulary carries, an emptied box being a value and a settled draft a tombstone.
    The Send button is read with the value, since a mirrored draft the box cannot send
    is words arriving dead. Each box is the panel's field: the page comment where no
    view is open, the thread's reply where its view is."""
    url = serve(LONG_PAGE, comments=1)
    [root] = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    general = '.lf-fp-field leaf-text[name="comment"]'
    send = ".lf-fp-field .lf-compose-submit"

    typed = "The page is missing the migration step."
    write(page_comment(first), typed)
    expect(page_comment(second)).to_have_js_property("value", typed)
    expect(second.locator(send)).to_have_attribute("aria-disabled", "false")
    second.keyboard.press("Escape")

    # The tab doing the typing is the one tab the store says nothing to, which is what
    # leaves the caret where the user put it: writing .value on a focused box sends
    # the caret to the end of it, and a user typing into the middle of a sentence
    # would watch every keystroke jump there.
    first.locator(general).click()
    first.keyboard.press("Home")
    first.keyboard.type("Late: ")
    expect(second.locator(general)).to_have_js_property("value", "Late: " + typed)
    assert first.locator(general).evaluate("ta => ta.selectionStart") == 6, (
        "the caret moved in the tab that did the typing"
    )
    typed = "Late: " + typed

    reply = "Typed into the reply box of the other tab."
    # The marks stand beside the field once the caret leaves it. A held draft
    # takes the quick chips' room, so travel through the Threads key route.
    first.keyboard.press("Escape")
    for page in (second, first):
        page.locator("h1").click()
        page.keyboard.press("Shift+t")
        panel_settled(page, view="thread")
        open_panel_thread(page, root)
    write(panel_field(second), reply)
    expect(panel_field(first)).to_have_js_property("value", reply)
    second.locator(send).click()
    round_trip(second)
    expect(panel_field(first)).to_have_js_property("value", "")

    for page in (first, second):
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
    expect(first.locator(general)).to_have_js_property("value", typed)
    first.locator(general).click()
    first.locator(send).click()
    round_trip(first)
    expect(second.locator(general)).to_have_js_property("value", "")
    expect(second.locator(send)).to_have_attribute("aria-disabled", "true")
    said = [e["text"] for e in events_model.read_events(serve.page_dir) if "text" in e]
    assert said[-2:] == [reply, typed]


def test_a_failed_concurrent_question_send_keeps_the_accepted_attempt(
    browser, serve, one_user
):
    """One request may lose its answer while another tab gets the same attempt
    accepted. The first tab adopts that durable outcome instead of reporting failure
    or offering the words as a second message."""
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Retry this exact answer.  "
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_say.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the failing answer")
    second_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(second)

    refuse(held[0])
    first.unroute("**/api/event")
    round_trip(first)
    # The words shown in the seat's own thread are what says the send landed;
    # a notice saying so beside them would be the same acknowledgement twice.
    expect(first.locator("#jobs > .lf-thread-seat")).to_contain_text(raw.strip())
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    # Asked of the words rather than of the box: a seat that can hold keeps its composer
    # open after every root (renderSeats), so an empty one is what says the
    # tab adopted the durable outcome instead of holding the words for a second send.
    expect(first_say.locator("leaf-text")).to_have_js_property("value", "")
    expect(second_say.locator("leaf-text")).to_have_js_property("value", "")


def test_two_passages_hold_two_composer_drafts(browser, serve, one_user):
    """One key for the composer was enough while a draft died with its tab; shared, it
    is a draft on one passage overwriting the words being typed on another. The key is
    the anchor, so the two coexist — and the record says when it was touched, which is
    what a tab arriving to both of them reopens on."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    early = "This paragraph buries the point."
    late = "And this one repeats it."
    compose(first, "#p3", early)
    compose(second, "#p9", late)
    expect(first.locator(".lf-composer leaf-text")).to_have_js_property("value", early)
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", late)

    # A tab arriving now: one composer, on the passage touched last.
    third = open_page(browser, url, context=one_user)
    expect(third.locator(".lf-composer leaf-text")).to_have_js_property("value", late)


def test_executable_revision_does_not_restore_a_new_draft_generation(browser, serve):
    page = editing_reply_page(browser, serve)
    editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    write(editor, "Old reply generation with selected words.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    saved = page.evaluate(
        """async()=>{
      const owner=await window.__lfCheckApi();
      const editing=owner.captureDraftEditing();
      return {editing,key:owner.whereDraft(editing.context).key};
    }"""
    )
    page.add_init_script(
        """(() => {
      const key=KEY;
      const record=JSON.parse(localStorage.getItem(key));
      localStorage.setItem(key,JSON.stringify({...record,attempt:'1234567890abcdef1234567890abcdef',base:record.attempt}));
    })()""".replace("KEY", json.dumps(saved["key"]))
    )
    replace_editing_document(page, serve)
    assert (
        page.evaluate("async()=> (await window.__lfCheckApi()).captureDraftEditing()")
        is None
    )
    expect(page.locator(".lf-composer leaf-text")).not_to_be_visible()
    actual = page.evaluate("(key)=>JSON.parse(localStorage.getItem(key))", saved["key"])
    assert actual["attempt"] == "1234567890abcdef1234567890abcdef"
    assert actual["text"] == saved["editing"]["words"]
