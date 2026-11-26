"""What a new version or an arriving edit leaves of each open editor: its words, caret,
focus and session, and the revision a draft aims at."""

import pytest
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url, open_seat_box, panel_comment
from render_cases_navigation import JOURNEY_V1, NOTED_PAGE, _publish
from render_harness import (
    REPLY_HOST_PAGE,
    consume_browser_errors,
    holding,
    leaf_page,
    open_latest,
    open_page,
    panel_field,
    refuse,
    reported_browser_errors,
    resized,
    round_trip,
    select,
    select_words,
    sending,
    stamp_page,
    stored_draft,
    stored_draft_text,
    ticked,
    told,
    wait_for_check_api,
    wait_for_revision,
    write,
    write_draft_elsewhere,
)

from browser.drafts import (
    choose_comment_target,
    editing_reply_page,
    editing_revision_source,
    replace_editing_document,
)
from browser.threads import open_panel_thread
from leaf.log import event_log as events_model
from leaf.source.render_checks import one_frame, rendered, wait_until_ready
from leaf_dev.browser import PANEL_THREAD, text_field

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("installation", ["in-place", "fresh"])
def test_an_automatic_revision_keeps_the_empty_panel_reply_focused(
    browser, serve, installation
):
    """A revision, installed in place or as a fresh document, leaves the panel's empty
    reply box, an open thread's, focused and empty."""
    url = live_url(serve(REPLY_HOST_PAGE))
    root = panel_comment(
        serve.page_dir, "Should reads fall back?", author="agent", obligation=True
    )
    page = open_page(browser, url)
    open_panel_thread(page, root)
    editor = panel_field(page)
    editor.click()
    expect(editor).to_be_focused()
    expect(editor).to_have_attribute("name", "reply")
    assert editor.evaluate("el => el.value") == ""
    birth = page.evaluate("performance.timeOrigin")
    revision = int(
        page.locator('meta[name="lf-revision"][data-lf-runtime]').get_attribute(
            "content"
        )
    )
    revised = REPLY_HOST_PAGE.replace(
        "with a signed-cookie fallback", "with a session-cookie fallback"
    )
    if installation == "fresh":
        revised = revised.replace(
            "</head>",
            '<script type="module">window.pageRevision = 2;</script></head>',
        )
    stamp_page(serve.page_dir, revised, "Revise the page beside its empty reply")
    wait_for_revision(page, revision + 1)
    assert (page.evaluate("performance.timeOrigin") != birth) == (
        installation == "fresh"
    )
    expect(editor).to_be_focused()
    assert editor.evaluate("el => el.value") == ""


def test_a_foreign_edit_waits_for_a_live_draft_and_replays_in_order(browser, serve):
    """Replay never replaces words while the user is typing them.

    Deferring one edit must also hold later edits for that draft: otherwise the
    later absolute value lands first and the deferred earlier value overwrites it
    when the box closes. An unrelated board move proves the poll saw the same
    batch while the editor was open, without making the test depend on time.
    Reconnecting the same editor restores its local deferral before semantic catchup.
    """
    page = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    editor = draft.locator("leaf-text")
    write(editor, "Local unsent words.")

    draft.evaluate(
        """node => {
          window.__lfEditingDraft = {
            node, parent: node.parentNode, next: node.nextSibling,
            editor: node.querySelector('leaf-text'),
          };
          node.remove();
        }"""
    )
    # The fixture deliberately removes the editor's subject. Consume that allowed
    # disappearance at the frame where the words watcher observes the removal.
    one_frame(page)
    consume_browser_errors(page, {"code": "words-left-screen"})
    page.evaluate(
        """() => {
          const {node, parent, next} = window.__lfEditingDraft;
          parent.insertBefore(node, next);
        }"""
    )
    assert editor.evaluate("node => node === window.__lfEditingDraft.editor")
    editor.focus()

    d = serve.page_dir
    for text in ("Foreign first edit.", "Foreign committed words."):
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"value": text},
            },
        )
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "board",
            "action": "move",
            "detail": {"unit": "card-x", "value": "col-done", "rank": "0i"},
        },
    )

    told(page)
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    expect(editor).to_have_js_property("value", "Local unsent words.")

    page.route("**/api/state*", refuse)
    page.keyboard.press("Escape")
    ticked(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Foreign committed words.")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")


def test_an_untouched_and_an_emptied_reply_follow_live_revisions(browser, serve):
    """Emptying a reply keeps its editing session while unrelated revisions arrive."""
    page = open_page(browser, live_url(serve(NOTED_PAGE)))
    resized(page, 1440, 900)
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Follow this discussion.")
    # The comment's own send in the wire before the log names it. Without that the read
    # below answers with the note the page opened on, and the reply this test is about is
    # looked for under an id no thread wears.
    with sending(page, "the comment the reply follows"):
        page.keyboard.press("ControlOrMeta+Enter")

    sent = events_model.read_events(serve.page_dir)[-1]
    thread = page.locator(
        f'.lf-margin-thread .lf-page-thread[data-lf-thread="{sent["id"]}"]'
    )
    reply = thread.locator("leaf-text")
    expect(thread).to_be_focused()
    text_field(thread, name="Reply", exact=True).click()
    expect(reply).to_be_focused()

    d = serve.page_dir
    v2 = NOTED_PAGE.replace(
        "A short second passage.", "A revised short second passage."
    )
    stamp_page(d, v2, "v2")
    wait_for_revision(page, 2)

    # The untouched reply remains disposable UI rather than becoming a draft merely
    # because the authored page advanced around it.
    expect(reply).to_be_visible()
    write(reply, "A thought I changed my mind about.")
    write(reply, "")
    # A thread's reply draft is keyed by the name the log's answer does not change —
    # the attempt the user's own comment opened it with (state/thread/model.js).
    assert stored_draft_text(page, f"reply:{sent['attempt']}") == ""
    v3 = v2.replace(
        "A revised short second passage.", "A twice-revised short second passage."
    )
    stamp_page(d, v3, "v3")
    wait_for_revision(page, 3)
    expect(reply).to_have_js_property("value", "")
    expect(reply).to_be_focused()


def editing_read(editor):
    return editor.evaluate(
        "el=>({value:el.value,focused:el.matches(':focus'),caret:[el.selectionStart,el.selectionEnd,el.selectionDirection]})"
    )


@pytest.mark.parametrize(
    "kind",
    [
        "authored",
        "composer",
        # The margin card's reply; the panel's open thread holds the same reply editor.
        "reply",
        # The comment box where a widget seats it, in an outlet of its own.
        "seated",
        "edit",
        # A document edit opened and selected in, with no words changed, so no draft.
        "edit-unchanged",
        "option",
    ],
)
def test_executable_revision_preserves_each_editor_identity(browser, serve, kind):
    page = open_page(browser, live_url(serve(editing_revision_source("overlay"))))
    if kind == "authored":
        editor = page.locator("#authored-draft")
    elif kind == "seated":
        _seat, editor = open_seat_box(page, "#seat-root")
    elif kind in {"edit", "edit-unchanged"}:
        page.locator("#draft-root .lf-draft-body").click()
        editor = page.locator("#draft-root leaf-text")
    elif kind == "option":
        editor = page.locator("#options-root > .lf-another leaf-text")
    else:
        page.locator("#passage").click(click_count=3)
        page.keyboard.press("c")
        editor = page.locator(".lf-composer leaf-text")
        expect(editor).to_be_focused()
        if kind == "reply":
            write(editor, "A canonical root comment.")
            page.keyboard.press("Control+Enter")
            round_trip(page)
            page.keyboard.press("c")
            editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
            expect(editor).to_be_focused()
    words = "Kept words with a selected span."
    if kind == "authored":
        words = "\n".join([words] * 200)
    if kind != "edit-unchanged":
        write(editor, words)
    editor.evaluate("el=>el.setSelectionRange(5,10,'backward')")
    before = editing_read(editor)
    if kind == "authored":
        editor.evaluate("el=>el.scrollTop=20")
        before["scroll"] = editor.evaluate("el=>el.scrollTop")
        assert before["scroll"] > 0, "the native edit field must actually scroll"
    first_document = page.evaluate("performance.timeOrigin")
    page.evaluate(
        "window.__oldRendererRealm=true;dispatchEvent(new Event('renderer-lifetime-probe'))"
    )
    before_digest = page.locator('meta[name="lf-executable"]').get_attribute("content")
    stamp_page(
        serve.page_dir, editing_revision_source("page"), "Change the page executable"
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == first_document:
        open_latest(page)
    wait_for_revision(page, 2)
    after_digest = page.locator('meta[name="lf-executable"]').get_attribute("content")
    assert after_digest != before_digest
    assert page.evaluate("performance.timeOrigin") != first_document
    assert page.evaluate("window.__oldRendererRealm===undefined")
    page.evaluate("dispatchEvent(new Event('renderer-lifetime-probe'))")
    assert page.evaluate("window.__rendererLifetime.hits") == 1
    after = editing_read(editor) if editor.count() else None
    if kind == "authored":
        assert after is not None
        after["scroll"] = editor.evaluate("el=>el.scrollTop")
    assert after == before


def test_a_revision_that_redraws_a_chosen_option_keeps_the_choice(browser, serve):
    """An option the user chose among radios stays chosen through a revision installed
    in place that replaces the radios, as one rewrapping them does: the choice carries
    to the replacements, which no input of the user's has touched since."""

    def page_with(wrapper):
        return leaf_page(
            "Pace",
            f'<h1 id="subject">Pace</h1><form id="f"><{wrapper} id="group">'
            '<label><input type="radio" name="pace" id="slow"> slow</label>'
            '<label><input type="radio" name="pace" id="steady" checked> steady</label>'
            f"</{wrapper}></form>",
        )

    page = open_page(browser, live_url(serve(page_with("p"))))
    page.locator("#slow").check()
    birth = page.evaluate("performance.timeOrigin")
    revision = int(
        page.locator('meta[name="lf-revision"][data-lf-runtime]').get_attribute(
            "content"
        )
    )
    stamp_page(serve.page_dir, page_with("div"), "Rewrap the options")
    wait_for_revision(page, revision + 1)
    assert page.evaluate("performance.timeOrigin") == birth
    expect(page.locator("div#group #slow")).to_be_checked()


def test_a_field_a_fresh_revision_makes_a_file_input_leaves_its_words_behind(
    browser, serve
):
    """A revision that needs a fresh document and turns a field the user typed into into
    a file input carries no words into it, since a file input takes none, and the words
    typed into the page's other fields still come back."""
    body = (
        '<h1 id="subject">Form</h1>'
        '<p><input id="who" aria-label="Name" autocomplete="off">'
        '<input id="where" aria-label="Place" autocomplete="off"></p>'
    )
    page = open_page(browser, live_url(serve(editing_revision_source("before", body))))
    page.locator("#who").fill("Ada")
    page.locator("#where").fill("Rome")
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(
        serve.page_dir,
        editing_revision_source(
            "after", body.replace('id="who"', 'id="who" type="file"')
        ),
        "Make the name a file",
    )
    told(page)
    if page.evaluate("performance.timeOrigin") == birth:
        open_latest(page)
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") != birth
    expect(page.locator("#where")).to_have_value("Rome")


def test_a_reload_after_staying_at_a_revision_s_reload_keeps_the_words_typed_since(
    browser, serve
):
    """Words typed after the user stays at a page's own leave prompt that a revision's
    reload raised, and steps Back to an earlier entry of the page, come back after
    they reload the page."""
    body = (
        '<h1 id="subject">Form</h1>'
        '<p><input id="who" aria-label="Name" autocomplete="off"></p>'
        '<p id="later">Later.</p>'
    )
    page = open_page(browser, live_url(serve(editing_revision_source("before", body))))
    page.locator("#who").click()
    page.locator("#who").fill("Ada")
    page.evaluate("document.activeElement.blur()")
    page.wait_for_function("navigation.transition === null")
    page.evaluate("location.hash = '#later'")
    page.wait_for_function("navigation.transition === null")
    page.on("dialog", lambda dialog: dialog.dismiss())
    page.evaluate(
        """() => {
          window.ownPrompt = (event) => { event.preventDefault(); event.returnValue = ""; };
          addEventListener("beforeunload", window.ownPrompt);
        }"""
    )
    with page.expect_event("dialog"):
        stamp_page(
            serve.page_dir,
            editing_revision_source("after", body),
            "Change the page's module",
        )
    page.evaluate("history.back()")
    page.wait_for_function("location.hash === ''")
    page.locator("#who").fill("Grace")
    page.evaluate('() => removeEventListener("beforeunload", window.ownPrompt)')
    page.reload()
    wait_until_ready(page)
    expect(page.locator("#who")).to_have_value("Grace")


def test_executable_revision_preserves_non_editor_thread_current_location(
    browser, serve
):
    page = editing_reply_page(browser, serve)
    page.keyboard.press("Escape")
    captured = page.evaluate(
        "async()=> (await window.__lfCheckApi()).captureDraftEditing()"
    )
    assert captured is None
    replace_editing_document(page, serve)
    expect(page.locator(".lf-composer leaf-text")).not_to_be_visible()
    assert (
        page.evaluate("async()=> (await window.__lfCheckApi()).captureDraftEditing()")
        is None
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("reader", ["panel", "card"])
def test_executable_revision_keeps_the_user_on_the_message_they_were_on(
    request, serve, engine, reader
):
    """A revision that reloads the page brings the user back to the message they were
    on in the thread it reopens, the panel's view or a card, rather than to the
    thread as a whole: the same place Back returns them to."""
    url = serve(editing_revision_source("before"))
    root = panel_comment(
        serve.page_dir,
        "What does this passage hold?",
        {"section": "passage", "quote": "A stable passage"}
        if reader == "card"
        else None,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "It holds the words a revision keeps exact.",
        },
    )
    page = open_page(request.getfixturevalue(engine), live_url(url))
    page.keyboard.press("g")
    page.keyboard.press("u")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-msg[data-lf-message]')"
    )
    key = page.evaluate("document.activeElement.dataset.lfMessage")
    replace_editing_document(page, serve)
    expect(page.locator(f'.lf-msg[data-lf-message="{key}"]')).to_be_focused()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_executable_revision_keeps_a_reply_where_it_was_written(request, serve, engine):
    """A reply the user writes in the floating panel's view of a thread goes on there,
    with its words and selection, through a revision that reloads the page, rather
    than moving into a card beside the thread's passage."""
    page = editing_reply_page(request.getfixturevalue(engine), serve)
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page.keyboard.press("Escape")
    open_panel_thread(page, root)
    reply = panel_field(page)
    reply.focus()
    expect(reply).to_have_attribute("name", "reply")
    write(reply, "Words written in the panel's view.")
    reply.evaluate("el=>el.setSelectionRange(6,13,'backward')")
    before = editing_read(reply)
    replace_editing_document(page, serve)
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')).to_be_visible()
    expect(reply).to_be_focused()
    assert editing_read(reply) == before
    expect(page.locator(".lf-margin-preview")).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_executable_revision_whose_reply_another_tab_cleared_returns_to_the_entry(
    request, serve, engine
):
    """A revision that reloads the page while the user writes a reply, whose words
    another tab clears before the reload arrives, still returns the user to the entry:
    the thread they were in opens again, though no words are left to put back."""
    page = editing_reply_page(request.getfixturevalue(engine), serve)
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    expect(editor).to_be_focused()
    write(editor, "Words another tab clears.")
    reply = page.evaluate(
        "async()=> (await window.__lfCheckApi()).captureDraftEditing().context"
    )
    written = stored_draft(page, reply)
    assert written and written["text"] == "Words another tab clears."
    # The reload's document waits until the words are cleared, so it is served the
    # drafts as they stand then (runtime/records/drafts.js, `lf-drafts`).
    held = []

    def hold_reload(route):
        if route.request.resource_type == "document" and "_leaf-revision" in (
            route.request.url
        ):
            held.append(route)
        else:
            route.fallback()

    page.route("**/*", hold_reload)
    try:
        stamp_page(
            serve.page_dir, editing_revision_source("after"), "Change the module"
        )
        told(page)
        # Open latest, as `open_latest` runs it, without waiting on the reload it
        # starts, which waits here on the held document.
        page.evaluate(
            "async () => { void (await window.__lfCheckApi()).versionPicker.latest(); }"
        )
        holding(page, held, 1, "the reload's document")
        write_draft_elsewhere(page, reply, "", over=written)
        page.unroute("**/*", hold_reload)
        for route in held:
            route.continue_()
        held.clear()
        wait_for_revision(page, 2)
        expect(
            page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
        ).to_be_visible()
    finally:
        for route in held:
            route.continue_()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_executable_revision_leaves_a_put_away_comment_shut(request, serve, engine):
    """A comment the user put away with Escape stays put away through a revision that
    reloads the page, as through any reload: its words don't take focus."""
    page = open_page(
        request.getfixturevalue(engine),
        live_url(serve(editing_revision_source("before"))),
    )
    page.locator("#passage").click(click_count=3)
    page.keyboard.press("c")
    composer = page.locator(".lf-composer leaf-text")
    write(composer, "Words put away for later.")
    page.keyboard.press("Escape")
    if composer.is_visible():
        page.keyboard.press("Escape")
    expect(composer).to_be_hidden()
    page.evaluate("document.activeElement?.blur?.(); getSelection().removeAllRanges()")
    replace_editing_document(page, serve)
    expect(composer).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_executable_revision_keeps_the_page_selection(request, serve, engine):
    """Words the user selected in prose a revision leaves as it was stay selected
    through the revision's reload, as through any reload."""
    page = open_page(
        request.getfixturevalue(engine),
        live_url(serve(editing_revision_source("before"))),
    )
    page.evaluate("""() => {
      const text = document.getElementById('passage').firstChild;
      const at = text.data.indexOf('stable passage');
      getSelection().setBaseAndExtent(text, at, text, at + 'stable passage'.length);
    }""")
    replace_editing_document(page, serve)
    page.wait_for_function("() => getSelection().toString() === 'stable passage'")


def test_live_executable_replacement_keeps_a_resolved_reply_session(browser, serve):
    """A live replacement continues actual editing, with its selection; an ordinary
    reload returns the user to the reply with the selection's ends."""
    page = editing_reply_page(browser, serve)
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    # A passage thread's reply is its margin card's, where `c` left the user.
    editor = page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
    expect(editor).to_be_focused()
    words = "Keep this actual editing session through the executable replacement."
    write(editor, words)
    editor.evaluate("el=>el.setSelectionRange(5,12,'backward')")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    expect(editor).to_be_focused()
    before = editing_read(editor)
    context = page.evaluate(
        "async()=> (await window.__lfCheckApi()).captureDraftEditing().context"
    )
    replace_editing_document(page, serve)
    expect(editor).to_be_focused()
    assert editing_read(editor) == before
    assert stored_draft_text(page, context) == words

    page.reload()
    wait_until_ready(page)
    # The entry's record names the reply focus was in, so the reload opens the thread
    # again with focus in its reply.
    reply = page.locator(".lf-thread-reply leaf-text:focus")
    expect(reply).to_have_count(1)
    expect(reply).to_have_js_property("value", words)
    assert reply.evaluate("el=>[el.selectionStart,el.selectionEnd]") == [5, 12]
    assert stored_draft_text(page, context) == words


# `seated` is the comment box in a widget's outlet, the one editor here Leaf carries
# from the replaced widget to its successor rather than generating again.
@pytest.mark.parametrize("kind", ["edit", "seated", "option"])
def test_in_place_revision_restores_the_current_generated_editor(browser, serve, kind):
    original = editing_revision_source("same-module")
    page = open_page(browser, live_url(serve(original)))
    if kind == "edit":
        page.locator("#draft-root .lf-draft-body").click()
        editor = page.locator("#draft-root leaf-text")
        revised = original.replace(
            "Current editable text.", "A revised authored draft body."
        )
    elif kind == "seated":
        _seat, editor = open_seat_box(page, "#seat-root")
        revised = original.replace("What should we do?", "What should we do next?")
    else:
        editor = page.locator("#options-root > .lf-another leaf-text")
        revised = original.replace("Initial choice", "A revised initial choice")
    write(editor, "An unsent edit keeps its exact selection.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    before = editing_read(editor)
    editor.evaluate("el=>el.__outgoingEditor=true")
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(serve.page_dir, revised, "Replace authored widget, retain executable")
    told(page)
    # Opens the latest where the revision waits for it, and is a no-op where it
    # installed by itself.
    open_latest(page)
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") == birth
    expect(editor).to_be_visible()
    if kind == "edit":
        assert not editor.evaluate("el=>Boolean(el.__outgoingEditor)")
    expect(editor).to_be_focused()
    assert editing_read(editor) == before


def test_a_mechanical_revision_failure_leaves_accepted_publication_ready(
    browser, serve
):
    original = editing_revision_source("same-module")
    page = open_page(browser, live_url(serve(original)))
    page.locator("#draft-root .lf-draft-body").click()
    editor = page.locator("#draft-root leaf-text")
    write(editor, "The actual editor keeps these unsent words.")
    before = editing_read(editor)
    later_readings = []

    def hold_later_readings(route):
        later_readings.append(route)

    # The interface event can precede Lit's editor paint. Hold its preparation until
    # that editor exists so the mechanical caret failure is installed before landing.
    page.evaluate(
        """() => document.addEventListener('lf-page-interface', event => {
          event.detail.present(new Promise(resolve => {
            const install = () => {
              const editor = document.querySelector('#draft-root leaf-text');
              if (!editor) return false;
              editor.setSelectionRange = () => {
                window.__mechanicalCaretFailure = true;
                throw new Error('mechanical caret fixture failed');
              };
              resolve();
              return true;
            };
            if (install()) return;
            const observer = new MutationObserver(() => {
              if (install()) observer.disconnect();
            });
            observer.observe(document.body, { childList: true, subtree: true });
          }));
        }, { once: true })"""
    )
    stamp_page(
        serve.page_dir,
        original.replace("Current editable text.", "New authored body."),
        "Install while generated editor has a failing caret",
    )
    told(page)
    before_reading = page.locator("body").get_attribute("data-lf-reading")
    page.route("**/api/state**", hold_later_readings)
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "installation-evidence",
            "kind": "comment",
            "author": "agent",
            "revision": 2,
            "text": "This fact joins the first installed publication.",
            "anchor": {"section": "passage"},
        },
    )
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/event")
            and response.request.method == "POST"
            and response.request.post_data_json.get("kind") == "error"
        )
    ):
        with page.expect_request("**/api/state**") as requested:
            open_latest(page)
        holding(page, later_readings, 1, "the latest's reading")
        first = next(
            route for route in later_readings if route.request == requested.value
        )
        answer = first.fetch()
        # The tab names the reading it holds, so the answer patches it
        # (`served_state/tail.py`) and carries the new reading's name as a change.
        first_reading = next(
            change["value"]
            for change in answer.json()["patch"]
            if change["at"] == ["reading"]
        )
        assert first_reading != before_reading
        later_readings.remove(first)
        first.fulfill(response=answer)
    page.wait_for_function(
        "document.querySelector('meta[name=lf-revision][data-lf-runtime]')?.content==='2'"
        " && window.__mechanicalCaretFailure"
    )
    expect(editor).to_have_js_property("value", before["value"])
    expect(page.locator("body")).to_have_attribute("data-lf-reading", first_reading)
    wait_for_check_api(page, "api => api.applicationPresented()")
    errors = consume_browser_errors(page, "mechanical caret fixture failed")
    assert len(errors) == 1, errors
    assert "Revision continuity failed" in errors[0].values["text"], errors
    wait_for_check_api(page, "api => api.readApplication().document.revision === 2")
    reported = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "error"
    ]
    assert len(reported) == 1, reported
    assert reported[0]["text"].startswith(
        "Revision continuity failed: mechanical caret fixture failed\n"
    )

    # Error reporting may advance server freshness, but no later state answer may
    # rescue this reading: the first proved application must complete itself.
    page.unroute("**/api/state**", hold_later_readings)
    for route in later_readings:
        route.continue_()


def test_a_fresh_revision_caret_failure_does_not_strand_deferred_arrivals(
    browser, serve
):
    original = editing_revision_source("before")
    page = open_page(browser, live_url(serve(original)))
    page.locator("#draft-root .lf-draft-body").click()
    editor = page.locator("#draft-root leaf-text")
    write(editor, "Fresh words preserve exact original draft attempt.")
    editor.evaluate("el=>el.setSelectionRange(4,9,'backward')")
    revised = editing_revision_source("after").replace(
        "window.__rendererLifetime=",
        "import {afterPresentation} from '/runtime/widget-api.js';afterPresentation(()=>window.__deferredArrivalRan=true);document.addEventListener('lf-presentation',()=>window.__presentationDispatched=true);\nconst field=customElements.get('leaf-text').prototype;const setRange=field.setSelectionRange;\nfield.setSelectionRange=function(a,b,d){if(a===4&&b===9)throw new Error('fresh mechanical caret fixture failed');return setRange.call(this,a,b,d)};\nwindow.__rendererLifetime=",
    )
    stamp_page(serve.page_dir, revised, "Fresh executable with mechanical failure")
    told(page)
    open_latest(page)
    wait_for_revision(page, 2)
    errors = reported_browser_errors(page, "fresh mechanical caret fixture failed")
    assert page.evaluate("Boolean(window.__presentationDispatched)")
    page.wait_for_function("window.__deferredArrivalRan===true")
    assert len(errors) == 1, errors
    assert "Revision continuity failed" in errors[0].values["text"], errors


@pytest.mark.parametrize(
    "change",
    [
        "widget",
        "revision",
        "dragged-revision",
        "hidden-revision",
        "window-revision",
        "reloaded-revision",
    ],
)
def test_saved_widget_words_cannot_dismiss_an_unfinished_comment(
    browser, serve, change
):
    """Changed words retain the editor and sending keeps its original semantic anchor."""
    source = editing_revision_source(
        "mutable",
        '<h1>Mutable words</h1><lf-draft id="mutable">'
        "<pre>The words first shown.</pre></lf-draft>",
    )
    source = source.replace(
        "</head>",
        "<style>@media(max-width:600px){#mutable{display:none}}</style></head>",
    )
    url = live_url(serve(source))

    def replace_words(value="Different saved words."):
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "mutable",
                "action": "edit",
                "detail": {"value": value},
            },
        )

    page = open_page(browser, url)
    shown = page.locator("#mutable .lf-draft-body")
    expect(shown).to_have_text("The words first shown.")
    bounds = shown.evaluate(
        "e => { const r = document.createRange(); r.selectNodeContents(e); "
        "return r.getBoundingClientRect().toJSON(); }"
    )
    y = bounds["top"] + bounds["height"] / 2
    select(page, (bounds["left"] + 1, y), (bounds["right"] - 1, y))
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    words = "Keep this unfinished observation."
    write(editor, words)
    editor.press("Home")
    editor.press("Shift+ArrowRight")
    caret = editor.evaluate("e => [e.selectionStart, e.selectionEnd]")
    rendered(page)
    if change == "dragged-revision":
        before_drag = editor.bounding_box()
        grip = page.locator(".lf-fab-bar > .lf-surface-grip").bounding_box()
        x, y = grip["x"] + grip["width"] / 2, grip["y"] + 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x - 60, y + 80, steps=8)
        page.mouse.up()
        page.wait_for_function(
            """before => {
              const box = document.querySelector('.lf-fab-input').getBoundingClientRect();
              return Math.abs(box.x - before.x + 60) < 1 &&
                     Math.abs(box.y - before.y - 80) < 1;
            }""",
            arg=before_drag,
        )
        expect(editor).to_be_focused()
    if change == "window-revision":
        resized(page, 480, 900)
        # The hidden subject withholds its editor. Resume writing restores the same
        # native field before the revision changes underneath it.
        expect(editor).to_be_hidden()
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(editor).to_be_visible()
        expect(editor).to_be_focused()
        rendered(page)
    editor_before = editor.bounding_box()
    if change in {"hidden-revision", "reloaded-revision"}:
        page.keyboard.press("Escape")
        page.mouse.click(5, 600)
    if change == "widget":
        replace_words()
    else:
        _publish(
            serve.page_dir,
            2,
            source.replace("The words first shown.", "Different saved words."),
            "Replace the quoted words",
        )
    told(page)
    if change != "widget":
        rendered(page)
        if change in {"revision", "dragged-revision", "window-revision"}:
            open_latest(page)
        wait_for_revision(page, 2)
    if change == "reloaded-revision":
        page.reload()
        wait_until_ready(page)
        # The reload leaves the box the user put away shut; Resume writing opens it.
        expect(editor).to_be_hidden()
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(editor).to_be_focused()
    elif change == "hidden-revision":
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(editor).to_be_focused()
    expect(shown).to_have_text("Different saved words.")
    rendered(page)
    editor_after = editor.bounding_box()
    if change not in {"hidden-revision", "reloaded-revision"}:
        assert abs(editor_after["x"] - editor_before["x"]) < 1
        assert abs(editor_after["y"] - editor_before["y"]) < 1
    expect(editor).to_be_visible()
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", words)
    if change != "reloaded-revision":
        assert editor.evaluate("e => [e.selectionStart, e.selectionEnd]") == caret
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    assert len(comments) == 1
    assert comments[0]["revision"] == 1
    assert comments[0]["anchor"]["quote"] == "The words first shown."


def test_revisiting_a_passage_recaptures_its_revision_without_losing_words(
    browser, serve
):
    """A fresh aim keeps saved words but captures the document currently on screen."""
    source = editing_revision_source("revisit")
    page = open_page(browser, live_url(serve(source)))
    select_words(page, "#passage")
    page.keyboard.press("c")
    words = "An observation captured on the first revision."
    write(page.locator(".lf-fab-input"), words)
    select_words(page, "#subject")
    rendered(page)
    _publish(
        serve.page_dir,
        2,
        source.replace(
            "<title>Editor continuity</title>", "<title>A newer revision</title>"
        ),
        "A new revision",
    )
    told(page)
    open_latest(page)
    wait_for_revision(page, 2)
    select_words(page, "#passage")
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    expect(editor).to_have_js_property("value", words)
    editor.press("ControlOrMeta+Enter")
    round_trip(page)
    sent = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == words
    ]
    assert len(sent) == 1
    assert sent[0]["revision"] == 2


def test_a_shared_composer_sends_the_revision_its_draft_last_aimed_at(
    browser, serve, one_user
):
    source = editing_revision_source("shared")
    url = live_url(serve(source))
    first = open_page(browser, url, context=one_user)
    choose_comment_target(first, "#passage")
    first.keyboard.press("c")
    editor = first.locator(".lf-fab-input")
    write(editor, "First words.")
    _publish(
        serve.page_dir,
        2,
        source.replace("Editor continuity", "A newer heading"),
        "A new revision",
    )
    second = open_page(browser, url, context=one_user)
    wait_for_revision(second, 2)
    second.keyboard.press("Escape")
    choose_comment_target(second, "#passage")
    second.keyboard.press("c")
    words = "Both views now hold this revision's draft."
    write(second.locator(".lf-fab-input"), words)
    expect(editor).to_have_js_property("value", words)
    second.keyboard.press("Escape")
    editor.press("ControlOrMeta+Enter")
    round_trip(first)
    sent = [
        e for e in events_model.read_events(serve.page_dir) if e.get("text") == words
    ]
    assert len(sent) == 1
    assert sent[0]["revision"] == 2
