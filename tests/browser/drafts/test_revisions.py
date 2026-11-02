"""What a new version or an arriving edit leaves of each open editor: its words, caret,
focus and session, and the revision a draft aims at."""

import os

import pytest
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_cases_navigation import JOURNEY_V1, NOTED_PAGE, _publish
from render_harness import (
    REPLY_HOST_PAGE,
    consume_browser_errors,
    open_page,
    panel_field,
    refuse,
    resized,
    restarting,
    round_trip,
    select,
    select_words,
    sending,
    stamp_page,
    stored_draft_text,
    ticked,
    told,
    wait_for_check_api,
    wait_for_revision,
    write,
)

from browser.drafts import (
    choose_comment_target,
    editing_reply_page,
    editing_revision_source,
    replace_editing_document,
)
from browser.threads import open_panel_thread
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import hosting as hosting_model
from leaf import revisioning as revisioning_model
from leaf import vendoring as vendoring_model
from leaf.registry.storage import layer_packages
from leaf.render_checks import one_frame, rendered, wait_until_ready

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
        f'.lf-margin-thread .lf-page-thread[data-thread="{sent["id"]}"]'
    )
    reply = thread.locator("leaf-text")
    expect(thread).to_be_focused()
    thread.get_by_role("textbox", name="Reply", exact=True).click()
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
    # the attempt the user's own comment opened it with (thread/model.js).
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
        "first-message",
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
    elif kind == "first-message":
        editor = page.locator("#seat-root > .lf-thread-seat > .lf-say leaf-text")
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
        page.keyboard.press("Control+Alt+r")
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


def test_live_executable_replacement_keeps_a_resolved_reply_session(browser, serve):
    """A live replacement continues actual editing; an ordinary reload only saves words."""
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
    expect(page.locator(".lf-thread-reply leaf-text")).not_to_be_visible()
    assert stored_draft_text(page, context) == words


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
            for value in layer_packages(page_dir)
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
        dict,
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


@pytest.mark.parametrize("kind", ["edit", "first-message", "option"])
def test_in_place_revision_restores_the_current_generated_editor(browser, serve, kind):
    original = editing_revision_source("same-module")
    page = open_page(browser, live_url(serve(original)))
    if kind == "edit":
        page.locator("#draft-root .lf-draft-body").click()
        editor = page.locator("#draft-root leaf-text")
        revised = original.replace(
            "Current editable text.", "A revised authored draft body."
        )
    elif kind == "first-message":
        editor = page.locator("#seat-root > .lf-thread-seat > .lf-say leaf-text")
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
    # Takes the panel's offered Latest where the revision waits for one, and is a no-op
    # where it installed by itself.
    page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") == birth
    expect(editor).to_be_visible()
    if kind != "option":
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
            page.keyboard.press("Control+Alt+r")
        first = next(
            route for route in later_readings if route.request == requested.value
        )
        answer = first.fetch()
        first_reading = answer.json()["reading"]
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
        "import {afterPresentation,TEXT_FIELD} from '/runtime/widget-api.js';afterPresentation(()=>window.__deferredArrivalRan=true);document.addEventListener('lf-presentation',()=>window.__presentationDispatched=true);\nconst field=customElements.get(TEXT_FIELD).prototype;const setRange=field.setSelectionRange;\nfield.setSelectionRange=function(a,b,d){if(a===4&&b===9)throw new Error('fresh mechanical caret fixture failed');return setRange.call(this,a,b,d)};\nwindow.__rendererLifetime=",
    )
    stamp_page(serve.page_dir, revised, "Fresh executable with mechanical failure")
    told(page)
    page.keyboard.press("Control+Alt+r")
    wait_for_revision(page, 2)
    errors = consume_browser_errors(page, "fresh mechanical caret fixture failed")
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
            page.keyboard.press("Control+Alt+r")
        wait_for_revision(page, 2)
    if change == "reloaded-revision":
        page.reload()
        wait_until_ready(page)
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
    page.keyboard.press("Control+Alt+r")
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
