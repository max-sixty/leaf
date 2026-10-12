"""End-to-end journey and durable draft tests."""

import json

import pytest
from browser.test_render_application_boundary import (
    THREAD_MIRROR,
    THREAD_MIRROR_DECLARATION,
)
from browser.test_render_threads import hold_visible_thread_presentation
from leaf import event_log as events_model
from leaf.render_checks import wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_QUESTION_PAGE,
    live_url,
    panel_comment,
)
from render_cases_navigation import (
    JOURNEY_V1,
    JOURNEY_V2,
    compose,
)
from render_harness import (
    LONG_PAGE,
    draft_control,
    draft_key,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    refuse,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    stored_draft_settled,
    stored_draft_text,
    take_browser_errors,
    told,
    until_draft_settled,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_drafts import (
    cancel_draft,
    editing_mirror_source,
    editing_read,
    editing_reply_page,
    editing_revision_source,
    replace_editing_document,
)


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
    draft_control(page, "save", "draft-ops").click()
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
    # box in front of it was for: renderState defers while an editor stands open.
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
    is words arriving dead. The other tab's general box joins its card when the card
    first opens and stays there, so its shut card holds the later words all the same."""
    url = serve(LONG_PAGE, comments=1)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    for page in (first, second):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)

    typed = "The page is missing the migration step."
    write(page_comment(first), typed)
    expect(page_comment(second)).to_have_js_property("value", typed)
    expect(second.locator(".lf-general .lf-compose-submit")).to_have_attribute(
        "aria-disabled", "false"
    )
    second.keyboard.press("Escape")

    # The tab doing the typing is the one tab the store says nothing to, which is what
    # leaves the caret where the user put it: writing .value on a focused box sends
    # the caret to the end of it, and a user typing into the middle of a sentence
    # would watch every keystroke jump there.
    first.locator(".lf-general leaf-text").click()
    first.keyboard.press("Home")
    first.keyboard.type("Late: ")
    expect(second.locator(".lf-general leaf-text")).to_have_js_property(
        "value", "Late: " + typed
    )
    assert (
        first.locator(".lf-general leaf-text").evaluate("ta => ta.selectionStart") == 6
    ), "the caret moved in the tab that did the typing"
    typed = "Late: " + typed

    reply = "Typed into the reply box of the other tab."
    second.locator(".lf-thread-summary").first.click()
    write(second.locator(".lf-thread leaf-text").first, reply)
    expect(first.locator(".lf-thread leaf-text").first).to_have_js_property(
        "value", reply
    )
    second.locator(".lf-thread").first.get_by_role(
        "button", name="Send", exact=True
    ).click()
    round_trip(second)
    expect(first.locator(".lf-thread leaf-text").first).to_have_js_property("value", "")

    first.locator(".lf-general .lf-compose-submit").click()
    round_trip(first)
    expect(second.locator(".lf-general leaf-text")).to_have_js_property("value", "")
    expect(second.locator(".lf-general .lf-compose-submit")).to_have_attribute(
        "aria-disabled", "true"
    )
    said = [e["text"] for e in events_model.read_events(serve.page_dir) if "text" in e]
    assert said[-2:] == [reply, typed]


def test_a_failed_concurrent_question_send_keeps_the_accepted_attempt(
    browser, serve, one_user
):
    """One request may lose its answer while another tab gets the same attempt
    accepted. The first tab adopts that durable outcome instead of reporting failure
    or offering the words as a second message."""
    url = serve(SEATED_QUESTION_PAGE)
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
    # The words standing in the seat's own thread are what says the send landed;
    # a notice saying so beside them would be the same acknowledgement twice.
    expect(first.locator("#jobs > .lf-thread-seat")).to_contain_text(raw.strip())
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    # Asked of the words rather than of the box: a seat that can hold keeps its composer
    # standing after every root (renderSeats), so an empty one is what says the
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


def test_executable_revision_routes_one_editor_among_visible_reply_mirrors(
    browser, serve
):
    page = open_page(
        browser,
        live_url(
            serve(
                editing_mirror_source("overlay"),
                layer_registry={"lf-thread-mirror": THREAD_MIRROR_DECLARATION},
                layer_widgets={"lf-thread-mirror.js": THREAD_MIRROR},
            )
        ),
    )
    page.locator("#passage").click(click_count=3)
    page.keyboard.press("c")
    write(page.locator(".lf-composer leaf-text"), "Canonical root for both mirrors.")
    page.keyboard.press("Control+Enter")
    round_trip(page)
    first = page.locator("#first .lf-thread-reply leaf-text")
    second = page.locator("#second .lf-thread-reply leaf-text")
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    write(first, "Kept mirror words with backward selection.")
    first.evaluate("el=>el.setSelectionRange(5,10,'backward')")
    expect(second).to_have_js_property("value", first.evaluate("el=>el.value"))
    before = editing_read(first)
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(
        serve.page_dir,
        editing_mirror_source("page"),
        "Change the mirror page executable",
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == birth:
        page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    current = page.evaluate(
        """async()=>{
      const {focused}=await window.__lfRuntimeImport('/runtime/focus.js');
      const el=focused();
      return {tag:el.tagName,value:el.value,caret:[el.selectionStart,el.selectionEnd,el.selectionDirection]};
    }"""
    )
    assert current.get("value") == before["value"]
    assert current["caret"] == before["caret"]


def test_executable_revision_keeps_a_reader_who_scrolled_away_from_their_reply(
    browser, serve
):
    """A replaced reply box takes focus back without pulling the reader back to it.

    The reader wrote in a thread at the top of the Threads list, then scrolled the
    list on with no other input, so the box keeps focus but no longer marks their
    place (user-place.js, `focusedInView`). A revision that replaces the document
    returns focus and words to the new box and leaves the list where they read."""
    url = live_url(serve(editing_revision_source("before")))
    ids = [panel_comment(serve.page_dir, f"General thread {n}.") for n in range(40)]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads .lf-thread[data-id="{ids[0]}"]')
    thread.click()
    reply = thread.locator(".lf-thread-reply leaf-text")
    words = "Words the reader left to read on."
    write(reply, words)
    threads = page.locator(".lf-threads")
    threads.evaluate("list => { list.scrollTop = list.scrollHeight; }")
    scroll_settled(page, ".lf-threads")
    expect(reply).to_be_focused()
    expect(reply).not_to_be_in_viewport()
    held = threads.evaluate("list => list.scrollTop")
    assert held > 0
    replace_editing_document(page, serve)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", words)
    scroll_settled(page, ".lf-threads")
    assert threads.evaluate("list => list.scrollTop") == pytest.approx(held, abs=2)


def test_executable_revision_does_not_restore_a_new_draft_generation(browser, serve):
    page = editing_reply_page(browser, serve)
    editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    write(editor, "Old reply generation with selected words.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    saved = page.evaluate(
        """async()=>{
      const owner=await window.__lfRuntimeImport('/runtime/drafts.js');
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
        page.evaluate(
            "async()=> (await window.__lfRuntimeImport('/runtime/drafts.js')).captureDraftEditing()"
        )
        is None
    )
    expect(page.locator(".lf-composer leaf-text")).not_to_be_visible()
    actual = page.evaluate("(key)=>JSON.parse(localStorage.getItem(key))", saved["key"])
    assert actual["attempt"] == "1234567890abcdef1234567890abcdef"
    assert actual["text"] == saved["editing"]["words"]


@pytest.mark.parametrize("interruption", ["generation", "input"])
def test_delayed_thread_destination_yields_to_shared_generation_or_new_input(
    browser, serve, one_user, interruption
):
    page = editing_reply_page(browser, serve, one_user)
    reply = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    write(reply, "The exact generation whose route is waiting.")
    known_loss = (
        'typed words left the screen without a key or press: "The exact generation whose route is waiting." in '
        + reply.evaluate("field => window.lfPlace(field)")
    )
    other = open_page(browser, page.url, context=one_user)
    held = page.evaluate(
        """async()=>{
      const drafts=await window.__lfRuntimeImport('/runtime/drafts.js');
      const focus=await window.__lfRuntimeImport('/runtime/thread/focus.js');
      return {editing:drafts.captureDraftEditing(),id:focus.heldThreadId()};
    }"""
    )
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-filter-toggle").click()
    page.get_by_role("searchbox", name="Find in threads").fill(
        "A query that hides this thread"
    )
    expect(page.locator(f""".lf-thread[data-id="{held["id"]}"]""")).to_be_hidden()
    # Find is a deliberate departure from reply editing. Its later narrowing paint
    # may withdraw the saved inactive box after that pointer callback has ended.
    # Calibrate only this exact withdrawal; later route and query errors stay strict.
    assert (
        stored_draft_text(page, held["editing"]["context"]) == held["editing"]["words"]
    )
    page.evaluate("lfWordsJudged()")
    errors = take_browser_errors(page)
    assert errors in ([], [known_loss]), errors
    hold_visible_thread_presentation(page, held["id"])
    page.evaluate(
        """async held=>{
      const drafts=await window.__lfRuntimeImport('/runtime/drafts.js');
      const {replyDestination}=await window.__lfRuntimeImport('/runtime/thread/focus.js');
      const {retainUserIntent,restrictUserIntent}=await window.__lfRuntimeImport('/runtime/user-intent.js');
      const {openThread}=await window.__lfRuntimeImport('/runtime/application.js');
      const button=document.createElement('button');button.id='held-reply-route';button.textContent='Continue the held reply';document.querySelector('main').append(button);
      button.onclick=()=>{
        const original=retainUserIntent();window.readOriginalIntent=original;
        const permission=restrictUserIntent(original,()=>drafts.draftEditingStands(held.editing));
        window.heldRouteResult=undefined;
        void replyDestination(held.id,openThread,permission).then(destination=>window.heldRouteResult=Boolean(destination));
      };
      window.heldEditing=held.editing;
    }""",
        held,
    )
    page.locator("#held-reply-route").click()
    page.wait_for_function("window.visibleThreadPresentationHeld===true")
    if interruption == "generation":
        assert page.evaluate("window.readOriginalIntent()")
        other.evaluate(
            """async editing=>{
          const drafts=await window.__lfRuntimeImport('/runtime/drafts.js');
          drafts.saveDraft(editing.context,editing.words);
        }""",
            held["editing"],
        )
        page.wait_for_function(
            "async()=>!(await window.__lfRuntimeImport('/runtime/drafts.js')).draftEditingStands(heldEditing)"
        )
        assert page.evaluate("window.readOriginalIntent()"), (
            "the state change must not supersede input intent"
        )
    else:
        write(page.locator("#authored-draft"), "Newer native input owns focus.")
    page.evaluate("releaseVisibleThreadPresentation()")
    page.wait_for_function("window.heldRouteResult!==undefined")
    assert page.evaluate("window.heldRouteResult") is False
    if interruption == "generation":
        expect(page.locator("#held-reply-route")).to_be_focused()
    else:
        expect(page.locator("#authored-draft")).to_be_focused()


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
    page.locator("#editable .lf-draft-body").click()
    edit = page.locator("#editable .lf-draft-edit")
    write(edit, "Rewritten page text")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    # Escape would cancel the edit; stepping out to the page leaves it open.
    page.locator("h1").click()
    expect(edit).not_to_be_focused()
    # The desktop More reference invokes the same semantic command as gi.
    page.keyboard.press("?")
    page.keyboard.press("?")
    page.get_by_role("combobox", name="Search commands").fill("Resume writing")
    page.get_by_role("button", name="Resume writing", exact=True).click()
    expect(edit).to_be_focused()
    expect(edit).to_have_js_property("value", "Rewritten page text")
    assert edit.evaluate("el => el.selectionStart") == 1
