"End-to-end journey and durable draft tests."

import pytest
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_navigation import (
    JOURNEY_V1,
    JOURNEY_V2,
    compose,
)
from render_harness import (
    draft_control,
    holding,
    leaf_page,
    open_page,
    panel_field,
    scroll_settled,
    sending,
    stamp_page,
    stored_draft_text,
    told,
    until_draft_settled,
    wait_for_revision,
    write,
)

from browser.drafts import (
    editing_revision_source,
    replace_editing_document,
)
from browser.margin import leave_card
from browser.threads import open_panel_thread, seed_panel_threads
from leaf import event_log as events_model
from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


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


def test_executable_revision_keeps_a_reader_who_scrolled_away_from_their_reply(
    browser, serve
):
    """A replaced reply box takes focus back without pulling the reader back to it.

    The reader wrote the reply to a long thread open in the panel, then scrolled its
    view back up the thread with no other input, so the box keeps focus while the
    reader reads elsewhere. A revision that replaces the document returns focus and
    words to the new box and leaves the view where they read."""
    url = live_url(serve(editing_revision_source("before")))
    [root] = seed_panel_threads(serve.page_dir, 1, long_index=0, messages=24)
    page = open_page(browser, url)
    view = open_panel_thread(page, root)
    reply = panel_field(page)
    words = "Words the reader left to read on."
    write(reply, words)
    view.evaluate("list => { list.scrollTop = 0; }")
    scroll_settled(page, view)
    expect(reply).to_be_focused()
    held = view.evaluate("list => list.scrollTop")
    assert view.evaluate("list => list.scrollHeight > list.clientHeight + 100")
    replace_editing_document(page, serve)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", words)
    scroll_settled(page, view)
    assert view.evaluate("list => list.scrollTop") == pytest.approx(held, abs=2)


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
