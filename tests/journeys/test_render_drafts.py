"""End-to-end journey and durable draft tests."""

import pytest
from browser.margin import leave_card
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_OBLIGATION_PAGE,
    live_url,
)
from render_cases_navigation import (
    JOURNEY_V1,
    JOURNEY_V2,
    compose,
)
from render_harness import (
    LONG_PAGE,
    heard_draft,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_field,
    panel_settled,
    press_draft_control,
    refuse,
    round_trip,
    sending,
    stamp_page,
    stored_draft,
    stored_draft_settled,
    stored_draft_text,
    told,
    until_draft_settled,
    wait_for_revision,
    write,
    write_draft_elsewhere,
)

from leaf.log import event_log as events_model
from leaf.source.render_checks import wait_until_ready

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

    press_draft_control(first, "save", "draft-ops")
    round_trip(first)
    expect(second_draft.locator("leaf-text")).to_have_count(0)
    # The body the other tab is left looking at is the log's, which is what closing the
    # box in front of it was for: lf-draft holds its drawing while an editor is open.
    expect(second_draft.locator(".lf-draft-body")).to_have_text(edited)
    assert stored_draft_settled(second, "edit:draft-ops")

    # A second edit, with only the first tab's box open. The words arriving here are
    # the fact to consume before reading an absence: the drafts read carrying them is
    # the same task that would have opened a box here.
    discarded = "This tab discards these words."
    first_draft.locator(".lf-draft-body").dblclick()
    write(first_draft.locator("leaf-text"), discarded)
    heard_draft(second, "edit:draft-ops", discarded)
    assert second_draft.locator("leaf-text").count() == 0, (
        "the second tab opened an editor for a keystroke nobody made there"
    )
    cancel_draft(first)
    until_draft_settled(second, "edit:draft-ops")
    heard_draft(second, "edit:draft-ops", None)
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
    # Travel through the Threads key route.
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
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job should come first?",
        },
    )["id"]
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    reply = f'#jobs .lf-page-thread[data-lf-thread="{root}"] > .lf-thread-reply'
    first_say = first.locator(reply)
    second_say = second.locator(reply)
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
    # The words shown in the seated thread are what says the send landed;
    # a notice saying so beside them would be the same acknowledgement twice.
    expect(first.locator("#jobs .lf-page-thread")).to_contain_text(raw.strip())
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [raw]
    # Asked of the words rather than of the box: a reply box stays after every send,
    # so an empty one is what says the tab adopted the durable outcome instead of
    # holding the words for a second send.
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
    editing = page.evaluate(
        "async () => (await window.__lfCheckApi()).captureDraftEditing()"
    )
    # Another tab writes the same words as a new generation, which this document hears
    # only when the next one arrives with it.
    page.route("**/api/drafts", refuse)
    attempt = write_draft_elsewhere(page, editing["context"], editing["words"])
    replace_editing_document(page, serve)
    # The entry's record still puts the user back in the reply, which now holds the
    # other tab's generation: the words come from the drafts store, never the handoff.
    arrived = page.evaluate(
        "async()=> (await window.__lfCheckApi()).captureDraftEditing()"
    )
    assert arrived["context"] == editing["context"]
    assert arrived["attempt"] == attempt
    assert arrived["words"] == editing["words"]
    expect(page.locator(".lf-composer leaf-text")).not_to_be_visible()
    actual = stored_draft(page, editing["context"])
    assert actual is not None
    assert actual["attempt"] == attempt
    assert actual["text"] == editing["words"]


def test_an_empty_draft_survives_reload_and_a_live_revision(browser, serve):
    """Empty text is a real replacement, not the absence of a saved draft. Deleting
    the whole body must survive a live revision and reload, then arrive in the log
    as an ordinary absolute edit."""
    url = serve(JOURNEY_V1)
    page = open_page(browser, live_url(url))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), "")
    assert stored_draft_text(page, "edit:draft-ops") == ""

    d = serve.page_dir
    stamp_page(d, JOURNEY_V2, "v2")
    told(page)
    wait_for_revision(page, 2)
    expect(draft.locator("leaf-text")).to_be_focused()
    expect(draft.locator("leaf-text")).to_have_js_property("value", "")
    assert "/versions/" not in page.url

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect(draft.locator("leaf-text")).to_be_visible()
    expect(draft.locator("leaf-text")).to_have_js_property("value", "")

    page.evaluate(
        """() => {
          window.lfActualFetch = window.fetch.bind(window);
          window.lfFailDraft = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (window.lfFailDraft &&
                event?.kind === 'action' && event.action === 'edit')
              return Promise.resolve(new Response('offline', {status: 503}));
            return window.lfActualFetch(input, init);
          };
        }"""
    )
    press_draft_control(page, "save", "draft-ops")
    # A 503 cannot say whether the server appended before its answer was lost. Keep
    # the one saved gesture visibly pending and its draft recoverable; reopening the
    # editor would invite a second gesture while this attempt is still retrying.
    expect(draft).to_have_attribute("aria-busy", "true")
    expect(draft.locator("leaf-text")).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text("")
    assert stored_draft_text(page, "edit:draft-ops") == ""

    page.evaluate("window.lfFailDraft = false")
    wait_for_revision(page, 2)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text("")
    until_draft_settled(page, "edit:draft-ops")
    events = [e for e in events_model.read_events(d) if e["kind"] == "action"]
    assert events[-1]["action"] == "edit"
    assert events[-1]["detail"] == {"value": ""}


def test_resume_writing_keeps_editor_identity_caret_and_sent_conversation(
    browser, serve
):
    """Resume follows actual edits across comment, reply and document editors."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Resume writing",
                '<h1>Resume writing</h1><p id="subject">A passage worth discussing.</p>'
                '<lf-draft id="editable"><pre>Original page text</pre></lf-draft>',
            )
        ),
    )
    compose(page, "#subject", "My original comment")
    box = page.locator(".lf-fab-input")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    caret = box.evaluate("el => el.selectionStart")
    page.keyboard.press("Escape")
    page.locator("#editable .lf-draft-body").click()
    expect(page.locator("#editable .lf-draft-edit")).to_be_focused()
    page.keyboard.press("Escape")  # focusing an editor is not an edit
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "My original comment")
    assert box.evaluate("el => el.selectionStart") == caret
    # Native input still owns the letters; gi must never run inside an editor.
    page.keyboard.type("gi")
    expect(box).to_have_js_property("value", "Mygi original comment")
    page.keyboard.press("Escape")
    held = []
    page.route("**/api/state", lambda route: held.append(route))
    page.reload()
    holding(page, held, 1, "the reloaded page's initial state")
    # A user gesture while presentation waits supersedes automatic draft recovery.
    # It must not later steal focus and turn the page shortcut into typed letters.
    page.keyboard.press("Escape")
    held[0].continue_()
    page.unroute("**/api/state")
    wait_until_ready(page)
    # The composer stays shut, so its box is not on the page to hold focus.
    expect(page.locator("leaf-text:focus")).to_have_count(0)
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "Mygi original comment")
    expect(box).to_have_js_property("selectionStart", caret + 2)
    with sending(page, "first comment"):
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    reply = page.locator("leaf-text[name=reply]:focus")
    expect(reply).to_be_visible()
    expect(reply).to_have_js_property("value", "")
    write(reply, "Continue this thread")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator("leaf-text[name=reply]:focus")).to_have_js_property(
        "value", "Continue this thread"
    )
    assert (
        page.locator("leaf-text[name=reply]:focus").evaluate("el => el.selectionStart")
        == 1
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    # Leaving the reply keeps its card; close that layer before editing beneath it.
    leave_card(page)
    page.locator("#editable .lf-draft-body").click()
    edit = page.locator("#editable .lf-draft-edit")
    write(edit, "Rewritten page text")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    # Escape discards and a press away saves; Tab leaves the edit open to resume.
    page.keyboard.press("Tab")
    expect(edit).not_to_be_focused()
    # The desktop More reference invokes the same semantic command as gi.
    page.keyboard.press("?")
    page.get_by_role("combobox", name="Search commands").fill("Resume writing")
    page.keyboard.press("Enter")
    expect(edit).to_be_focused()
    expect(edit).to_have_js_property("value", "Rewritten page text")
    assert edit.evaluate("el => el.selectionStart") == 1
