"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json
import re

import pytest
from browser.test_render_application_boundary import (
    PAGE_MODULE,
    THREAD_READER,
    THREAD_READER_DECLARATION,
    activation_page,
    arrived,
    long_thread,
)
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_V1,
    LIVE_V2,
    live_url,
    package_workspace,
)
from render_cases_widgets import PAGE_DECLARATION, PAGE_WIDGET
from render_harness import (
    PANEL,
    before_landing_frame,
    consume_browser_errors,
    expect_open_threads,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_control,
    panel_settled,
    reported_browser_errors,
    resized,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    stored_draft_text,
    told,
    wait_for_revision,
    write,
)

from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD, slow_cpu, text_field


def test_a_settled_delivery_activates_one_fresh_document_with_continuity(
    held_events, serve
):
    """One activation waits for its old document, then restores only Leaf state."""
    browser, held = held_events
    source = activation_page(LIVE_V1)
    version_url = serve(
        source,
        page_files={
            "app.js": PAGE_MODULE,
            "helper.js": 'export const label = "first";',
        },
    )
    page = open_page(browser, live_url(version_url))
    expect(page.locator("html")).to_have_attribute("data-page-module", "first:1")
    first_document = page.evaluate("performance.timeOrigin")
    page.evaluate("window.__pageModuleState.oldDocumentOnly = true")

    write(page_comment(page), "Keep this recoverable draft in the page.")
    page.keyboard.press("Escape")

    page.locator("#live-reading").evaluate(
        "el => { el.scrollIntoView({block: 'start'}); scrollBy(0, -120); }"
    )
    page.locator("#activation-go .lf-pick").click()
    holding(page, held, 1, "the unresolved option pick")
    focused_control = page.locator("#focused-control")
    focused_control.click()
    expect(focused_control).to_be_focused()
    reading_top = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert page.evaluate("scrollY") > 0

    try:
        (serve.page_dir / "page" / "helper.js").write_text(
            'export const label = "second";'
        )
        stamp_page(
            serve.page_dir, activation_page(LIVE_V2), "activate the complete page"
        )
        told(page)

        assert page.evaluate("performance.timeOrigin") == first_document
        expect(page).to_have_title("(1) Live first")
        expect(focused_control).to_be_focused()
        assert len(held) == 1

        # The explicit door may release a composition hold, but it cannot release the
        # delivery hold.
        latest = panel_control(page, "latest")
        with page.expect_response("**/api/state*"):
            latest.click()
        told(page)
        assert page.evaluate("performance.timeOrigin") == first_document
        assert len(held) == 1
    finally:
        held.pop(0).continue_()

    wait_for_revision(page, 2)
    expect(page.locator("html")).to_have_attribute("data-page-module", "second:1")
    assert page.evaluate("performance.timeOrigin") != first_document
    assert page.evaluate("window.__pageModuleState") == {
        "loads": 1,
        "label": "second",
    }
    # Leaf state crosses; the user's place on a control does not. A fresh document
    # cannot know it has found the same control again — an id, a tag and a count among
    # siblings are a shape, not an identity — so it leaves focus on the page, where the
    # page's own keys are live, rather than hand the next press to a guess.
    assert page.evaluate("document.activeElement === document.body")
    expect(page.locator("#activation-go")).to_have_attribute("selected", "")
    restored_top = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(restored_top - reading_top) < 2, (reading_top, restored_top)
    expect(page_comment(page)).to_have_js_property(
        "value", "Keep this recoverable draft in the page."
    )

    historical = open_page(browser, version_url, pin=True)
    expect(historical.locator("html")).to_have_attribute("data-page-module", "first:1")


@pytest.mark.parametrize(
    ("primary", "travel", "source_top", "cross_boundary", "back_before_frame"),
    [
        (True, True, 200, False, False),
        (True, False, 200, False, False),
        # Back interrupts the trip before its first frame.
        (False, True, 1000, False, True),
        # A contextual card's travel, slowed until it crosses into the viewport.
        (False, True, 1000, True, False),
    ],
)
def test_primary_arrival_records_a_return_place_only_when_travelling(
    browser, serve, primary, travel, source_top, cross_boundary, back_before_frame
):
    """Back restores the working place left by a jump to the primary reader."""
    url = package_workspace(
        serve,
        before_reader='<p style="min-height:1600px">Earlier page context.</p>',
        primary=primary,
    )
    if not primary:
        append_carried_log_record(
            serve.page_dir,
            {
                "id": "anchored",
                "kind": "comment",
                "author": "agent",
                "revision": 1,
                "text": "Inspect this passage.",
                "anchor": {"section": "notes"},
            },
        )
    page = open_page(browser, url)
    # The short window moves the workspace's reading regions, and the page puts back
    # the place it recorded before them on the frame after; scrolling to the source
    # before that has the page undo it (features/version.js, `restoreShifted`).
    resized(page, 1440, 320)
    rendered(page)
    heading = page.locator("h1")
    heading.evaluate(
        """(node, top) => {
      node.tabIndex = -1;
      node.focus({preventScroll:true});
      const range = document.createRange();
      range.selectNodeContents(node);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
      window.scrollTo({top, behavior:'instant'});
    }""",
        source_top,
    )
    if cross_boundary:
        # Long native frames expose the compositor's one-frame anchor delay as the
        # contextual card travels into the viewport and changes placement plane.
        slow_cpu(page, 6)
    if back_before_frame:
        before_landing_frame(
            page,
            """() => {
              window.backRequestedAt = scrollY;
              queueMicrotask(() => history.back());
            }""",
        )
    entries = page.evaluate("history.length")
    assert page.evaluate(
        """async ({travel, primary}) => {
          const api = await window.__lfWidgetApi();
          const thread = api.readThreads().threads.find(thread => thread.id === (primary ? 'opening' : 'anchored'));
          window.returnTripDestination = await api.threadActions.open(thread.key, {part:'reply', travel});
          return Boolean(returnTripDestination);
        }""",
        {"travel": travel, "primary": primary},
    )
    if not back_before_frame:
        assert page.evaluate("""() => {
          let active = document.activeElement;
          while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
          return active === returnTripDestination;
        }""")
    assert page.evaluate("history.length") == entries + int(travel)
    if travel:
        if back_before_frame:
            assert page.evaluate("backRequestedAt") == source_top
        else:
            # Back is ordinary input as soon as arrival returns, during smooth placement.
            page.wait_for_function("top => scrollY !== top", arg=source_top)
            if cross_boundary:
                page.wait_for_function("scrollY < 200")
                expect(page.locator("#lf-margin-preview")).to_be_in_viewport()
            page.go_back()
        expect(heading).to_be_focused()
        scroll_settled(page)
        assert page.evaluate("scrollY") == source_top
        assert page.evaluate("getSelection().toString()") == heading.text_content()
    else:
        assert page.evaluate("scrollY") == source_top


@pytest.mark.parametrize("width", [1440, 390])
def test_primary_package_reader_retains_native_widgets_drafts_and_creation(
    browser, serve, width
):
    context = browser.new_context(
        viewport={"width": width, "height": 900},
        has_touch=width < 500,
        is_mobile=width < 500,
    )
    url = package_workspace(serve)
    for question_id, text in [
        ("tone-question", "Should it stay concise?"),
        ("followup-question", "When should it send?"),
    ]:
        append_carried_log_record(
            serve.page_dir,
            {
                "id": question_id,
                "kind": "reply",
                "author": "agent",
                "revision": 1,
                "parent": "opening",
                "text": text,
                "obligation": True,
            },
        )
    page = open_page(browser, url, context=context)
    workspace = page.locator("#workspace")
    email = workspace.locator("lf-option#email")
    expect(email).to_be_visible()
    if width < 500:
        # Playwright's automatic click scroll has no trusted input for the
        # shift watcher; move the short reader with a user scroll first.
        workspace.locator(".reader").hover()
        page.mouse.wheel(0, 100)
    page.evaluate(
        "window.originalOption = document.querySelector('#workspace').querySelector('#email')"
    )
    with sending(page, "answer the package's native obligation"):
        email.get_by_role("checkbox").click()
    expect(workspace.locator(".counts")).to_contain_text("Email")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    editor = text_field(workspace, name="Reply", exact=True)
    write(editor, "A shared draft")
    workspace.get_by_role("button", name="Feed", exact=True).click()
    expect(editor).to_have_js_property("value", "A shared draft")
    workspace.get_by_role("button", name="Shelf", exact=True).click()
    assert page.evaluate(
        "document.querySelector('#workspace').querySelector('#email') === window.originalOption"
    )
    expect(text_field(workspace, name="Reply", exact=True).last).to_have_js_property(
        "value", "A shared draft"
    )
    with sending(page, "send the retained reply"):
        text_field(workspace, name="Reply", exact=True).last.press("Control+Enter")
    expect(workspace.get_by_text("A shared draft", exact=True)).to_be_visible()
    # One reply answers both questions. Counts include them, while the compact
    # answer summary names only widget choices instead of repeating words.
    expect(workspace.locator(".counts")).to_have_text(
        "0 waiting on me · 3 answered · Email"
    )
    with sending(page, "create a real conversation from a package"):
        workspace.get_by_role("textbox", name="New conversation").fill(
            "New package conversation"
        )
        workspace.get_by_role("button", name="Start conversation").click()
    expect(
        workspace.locator(".lf-page-thread").get_by_text(
            "New package conversation", exact=True
        )
    ).to_be_visible()
    assert any(
        event.get("text") == "New package conversation" and event["kind"] == "comment"
        for event in events_model.read_events(serve.page_dir)
    )


def test_thread_presentation_waits_for_its_own_widgets_only(browser, serve):
    """The thread parent absorbs descendants without joining unrelated page work."""
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local" choice="idle"></lf-local>',
    )
    page = open_page(
        browser,
        live_url(
            serve(
                source,
                page_files={
                    "registry.json": json.dumps(PAGE_DECLARATION),
                    "widgets/lf-local.js": PAGE_WIDGET,
                },
            )
        ),
    )
    page.evaluate(
        """async () => {
          const presentation = await window.__lfCheckApi();
          const held = () => {
            let release, reject;
            const promise = new Promise((resolve, fail) => {
              release = resolve;
              reject = fail;
            });
            return {promise, release, reject};
          };
          window.pagePreparation = held();
          window.threadPreparation = held();
          window.__heldLocalPresentations = new Map([
            ['thread-local', threadPreparation.promise],
          ]);
          // Said from inside the widget, the work is its preparation.
          const {PendingTaskEvent} = await window.__lfLibImport('pending-task.js');
          document.querySelector('#page-local').shadowRoot
            .dispatchEvent(new PendingTaskEvent(pagePreparation.promise));
          window.whenLeafPresented = presentation.whenApplicationPresented;
          window.whenLeafRegionsPresented =
            presentation.whenApplicationRegionsPresented;
          window.readLeafPresentation = presentation.readApplicationPresentation;
        }"""
    )

    long_thread(serve.page_dir, "thread-widget-question", "Show the thread widget.")
    # The panel's thread view is the reader that draws the reply's widget.
    open_panel_thread(page, arrived(page, "thread-widget-question"))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "thread-widget-question",
            "text": "This widget prepares inside the thread.\n\n"
            '<lf-local id="thread-local" choice="idle"></lf-local>',
        },
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-local",
            "action": "choose",
            "detail": {"value": "chosen"},
        },
    )
    page.wait_for_function(
        """() => {
          const pending = readLeafPresentation().pending;
          return document.querySelector('.lf-floating-panel #thread-local') &&
            pending.includes('thread') &&
            pending.includes('widget:thread-local:preparation') &&
            pending.includes('widget:page-local:preparation');
        }""",
    )
    page.evaluate(
        "threadReady = false; allReady = false; "
        "whenLeafRegionsPresented(['thread'], () => true)"
        ".then(() => { threadReady = true; }); "
        "whenLeafPresented().then(() => { allReady = true; }); true"
    )
    assert page.evaluate("threadReady") is False
    page.evaluate("threadPreparation.release('thread')")
    page.wait_for_function("threadReady")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "1")
    expect(page.locator(".lf-floating-panel #thread-local")).to_have_attribute(
        "data-rendered-choice", "chosen"
    )
    assert page.evaluate("allReady") is False
    assert "widget:page-local:preparation" in page.evaluate(
        "readLeafPresentation().pending"
    )
    page.evaluate("pagePreparation.release('page')")
    page.wait_for_function("allReady")

    # A descendant owns its own fail-soft result. Its failure reports once and settles,
    # while the parent list, count, and narrowing keep the same candidate reading.
    page.evaluate(
        """() => {
          window.failedThreadPreparation = (() => {
            let reject;
            const promise = new Promise((_resolve, fail) => { reject = fail; });
            return {promise, reject};
          })();
          window.__heldLocalPresentations.set(
            'thread-failing', failedThreadPreparation.promise
          );
        }"""
    )
    long_thread(
        serve.page_dir, "failing-widget-question", "Show another thread widget."
    )
    open_panel_thread(page, arrived(page, "failing-widget-question"))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "failing-widget-question",
            "text": "This widget fails its preparation.\n\n"
            '<lf-local id="thread-failing" choice="idle"></lf-local>',
        },
    )
    page.wait_for_function(
        """() => document.querySelector('.lf-floating-panel #thread-failing') &&
          readLeafPresentation().pending.includes('thread') &&
          readLeafPresentation().pending.includes(
            'widget:thread-failing:preparation'
          )""",
    )
    expect_open_threads(page, 2)
    page.evaluate(
        "threadReady = false; "
        "whenLeafRegionsPresented(['thread'], () => true)"
        ".then(() => { threadReady = true; }); "
        "failedThreadPreparation.reject(new Error('thread descendant failure')); true"
    )
    page.wait_for_function("threadReady")
    expect(page.locator(".lf-floating-panel #thread-failing")).to_have_count(1)
    expect_open_threads(page, 2)
    reported_browser_errors(
        page, "leaf: Presentation failed: thread descendant failure"
    )


@pytest.mark.parametrize("while_pending", ["stay", "choose-earlier"])
def test_packages_and_panel_share_threads_through_gestures_and_authored_content(
    browser, serve, while_pending
):
    """One public reading carries both optimistic turns and live authored unit state."""
    url = serve(
        leaf_page(
            "Shared Threads",
            '<h1>Shared Threads</h1><lf-thread-reader id="reader"></lf-thread-reader>',
        ),
        layer_registry={"lf-thread-reader": THREAD_READER_DECLARATION},
        layer_widgets={"lf-thread-reader.js": THREAD_READER},
    )
    for event in [
        {
            "id": "question",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "**Decision**",
        },
        {
            "id": "answer",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "question",
            "text": "Choose a direction.\n\n"
            '<lf-options id="direction"><lf-option id="north">North</lf-option><lf-option id="south">South</lf-option></lf-options>',
        },
    ]:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    reader = page.locator("#reader")
    expect(reader).to_contain_text("Decision")
    record = reader.evaluate("""node => {
      const reading = node.collection;
      const cloned = structuredClone(reading);
      const allFrozen = value => !value || typeof value !== 'object' ||
        (Object.isFrozen(value) && Object.values(value).every(allFrozen));
      return {reading: cloned, frozen: allFrozen(reading), same: node.sameReading, topic: node.topic};
    }""")
    assert record["frozen"] and record["same"]
    assert record["topic"] == "Decision"
    root, reply = record["reading"]["threads"][0]["msgs"]
    assert root["text"] == "**Decision**" and root["body"]["text"].strip() == "Decision"
    assert reply["body"]["document"] == {"thread": "question", "message": "answer"}
    assert reply["body"]["kind"] == "authored"
    assert "North" in reply["body"]["text"]
    assert "html" not in root and "html" not in reply
    assert '"html"' not in json.dumps(record)
    open_threads(page)
    # The agent answered without naming the thread, so it reads its opening words.
    expect(page.locator(".lf-fp-thread")).to_contain_text("Decision")
    open_panel_thread(page, "question")
    expect(page.locator("#direction")).to_have_count(1)
    message_top = page.locator("#direction").evaluate(
        "node => node.getBoundingClientRect().top"
    )
    with sending(page, "choose North in the authored reply"):
        page.locator("#north .lf-pick").click()
    round_trip(page)
    assert (
        page.locator("#direction").evaluate("node => node.getBoundingClientRect().top")
        == message_top
    )
    assert reader.evaluate("""node => node.collection.threads[0].msgs[1].body.units
      .find(unit => unit.id === 'direction').state.choose.value""") == ["north"]

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    box = page_comment(page)
    send = page.locator(".lf-fp-field .lf-compose-submit")
    write(box, "Pending **words**")
    send.click()
    holding(page, held, 1, "the shared collection's pending root")
    expect(reader).to_contain_text("Pending words")
    pending = reader.evaluate(
        "node => node.collection.threads.find(thread => thread.root.pending)"
    )
    # The send opens the pending thread's view in the panel.
    expect(page.locator(PANEL_THREAD)).to_contain_text("Pending words")
    held.pop().continue_()
    round_trip(page)
    admitted = reader.evaluate(
        "(node, key) => node.collection.threads.find(thread => thread.key === key)",
        pending["key"],
    )
    assert admitted["id"] != pending["id"]
    assert admitted["root"]["key"] == pending["root"]["key"]
    selected = page.locator(f'{PANEL_THREAD}[data-lf-thread="{admitted["id"]}"]')
    expect(selected).to_be_visible()

    box = page_comment(page)
    write(box, "Refused words")
    send.click()
    holding(page, held, 1, "the shared collection's refused root")
    expect(reader).to_contain_text("Refused words")
    expect(page.locator(PANEL_THREAD)).to_contain_text("Refused words")
    if while_pending == "choose-earlier":
        # Refusal restores the earlier selection only while the provisional root
        # still owns it; a later user choice must remain the selected conversation.
        selected = open_panel_thread(page, "question")
    # Chrome reports no shift within 500ms of input, so the refusal lands after it:
    # taking back the view the send opened moves nothing the pointer was not near.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    route = held.pop()
    route.fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": route.request.post_data_json["attempt"],
            "error": "refused before append",
            "final": True,
        },
    )
    round_trip(page)
    consume_browser_errors(page, http_error_console(400))
    expect(reader).not_to_contain_text("Refused words")
    assert stored_draft_text(page, "general") == "Refused words"
    if while_pending == "choose-earlier":
        # The field takes no keys from a user who has moved on: the thread they chose
        # stays open in it, and the words wait in the page comment.
        expect(box).to_have_count(0)
        expect(selected).to_be_visible()
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
        expect(box).to_have_js_property("value", "Refused words")
    else:
        # Where the send left the user, the field returns to the refused words.
        expect(box).to_be_focused()
        expect(page.locator(PANEL)).not_to_have_attribute(
            "data-lf-open", re.compile(".")
        )
    expect(page.locator('[data-lf-thread^="pending:"]')).to_have_count(0)
    page.unroute("**/api/event")
