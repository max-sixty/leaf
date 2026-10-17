"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json
import re

import pytest
from browser.test_render_application_boundary import (
    PAGE_MODULE,
    THREAD_ACTIONS,
    THREAD_ACTIONS_DECLARATION,
    THREAD_FILTER,
    THREAD_FILTER_DECLARATION,
    THREAD_READER,
    THREAD_READER_DECLARATION,
    activation_page,
    package_workspace,
)
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_V1,
    LIVE_V2,
    live_url,
)
from render_harness import (
    PANEL,
    PANEL_THREAD,
    consume_browser_errors,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    page_comment,
    panel_control,
    panel_settled,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    stored_draft_text,
    told,
    wait_for_revision,
    write,
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
            "text": "Choose a direction.",
            "markup": '<lf-options id="direction" choose><lf-option id="north">North</lf-option><lf-option id="south">South</lf-option></lf-options>',
        },
    ]:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    reader = page.locator("#reader")
    expect(reader).to_contain_text("Decision")
    record = reader.evaluate("""node => {
      const reading = node.reading;
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
    assert '"markup"' not in json.dumps(record) and '"html"' not in json.dumps(record)
    page.locator(".lf-fp-threads").click()
    panel_settled(page, view="threads")
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
    assert reader.evaluate("""node => node.reading.threads[0].msgs[1].body.units
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
        "node => node.reading.threads.find(thread => thread.root.pending)"
    )
    # The send opens the pending thread's view in the panel.
    expect(page.locator(PANEL_THREAD)).to_contain_text("Pending words")
    held.pop().continue_()
    round_trip(page)
    admitted = reader.evaluate(
        "(node, key) => node.reading.threads.find(thread => thread.key === key)",
        pending["key"],
    )
    assert admitted["id"] != pending["id"]
    assert admitted["root"]["key"] == pending["root"]["key"]
    selected = page.locator(f'{PANEL_THREAD}[data-thread="{admitted["id"]}"]')
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
        expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
    expect(page.locator('[data-thread^="pending:"]')).to_have_count(0)
    page.unroute("**/api/event")


def test_package_thread_widgets_keep_local_filters_and_independent_subscriptions(
    browser, serve
):
    """Two widget instances observe one Thread collection and route through core."""
    url = serve(
        leaf_page(
            "Thread widget instances",
            "<h1>Thread widget instances</h1>"
            '<lf-thread-filter id="first" filter="Alpine"></lf-thread-filter>'
            '<lf-thread-filter id="second" filter="Bay"></lf-thread-filter>',
        ),
        layer_registry={"lf-thread-filter": THREAD_FILTER_DECLARATION},
        layer_widgets={"lf-thread-filter.js": THREAD_FILTER},
    )
    for thread_id, words in [("alpine", "Alpine"), ("bay", "Bay")]:
        append_carried_log_record(
            serve.page_dir,
            {
                "id": thread_id,
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": words,
            },
        )
    page = open_page(browser, url)
    first = page.locator("#first")
    second = page.locator("#second")
    expect(first.locator("li")).to_have_text("Alpine")
    expect(second.locator("li")).to_have_text("Bay")
    assert first.evaluate("node => node.sameReading")
    assert second.evaluate("node => node.sameReading")

    second.locator("input").fill("Cedar")
    before = [widget.evaluate("node => node.updates") for widget in (first, second)]
    with sending(page, "a Thread visible to both package widgets"):
        write(page_comment(page), "Cedar")
        page.locator(".lf-fp-field .lf-compose-submit").click()
    expect(second.locator("li")).to_have_text("Cedar")
    expect(first.locator("li")).to_have_text("Alpine")
    for widget, count in zip((first, second), before):
        assert widget.evaluate("node => node.updates") > count
        assert widget.evaluate(
            "node => node.reading.threads.some(thread => thread.root.body.text.trim() === 'Cedar')"
        )

    # Clear the user's filter before this lifecycle test removes its widget.
    second.locator("input").fill("")
    # The widget taken out stands last, so taking it out moves nothing else.
    removed = second.element_handle()
    second.evaluate("node => node.remove()")
    stopped_at = removed.evaluate("node => node.updates")
    first.locator("input").fill("Delta")
    first_before = first.evaluate("node => node.updates")
    with sending(page, "another Thread after one widget disconnected"):
        write(page_comment(page), "Delta")
        page.locator(".lf-fp-field .lf-compose-submit").click()
    expect(first.locator("li")).to_have_text("Delta")
    assert first.evaluate("node => node.updates") > first_before
    assert removed.evaluate("node => node.updates") == stopped_at

    thread_id = first.evaluate(
        "node => node.reading.threads.find(thread => thread.root.body.text.trim() === 'Delta').id"
    )
    # The widget's route through core opens the thread's view in the panel.
    first.locator("button", has_text="Delta").click()
    expect(page.locator(f'{PANEL_THREAD}[data-thread="{thread_id}"]')).to_be_visible()


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

    write(page_comment(page), "Keep this recoverable draft in the page instance.")
    page.keyboard.press("Escape")

    page.locator("#live-reading").evaluate(
        "el => { el.scrollIntoView({block: 'start'}); scrollBy(0, -120); }"
    )
    page.locator("#activation-go .lf-pick").click()
    holding(page, held, 1, "the unresolved option pick")
    standing = page.locator("#standing-control")
    standing.click()
    expect(standing).to_be_focused()
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
        expect(page).to_have_title("Live first")
        expect(standing).to_be_focused()
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
    expect(page.locator("#activation-go")).to_have_attribute("chosen", "")
    restored_top = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(restored_top - reading_top) < 2, (reading_top, restored_top)
    expect(page_comment(page)).to_have_js_property(
        "value", "Keep this recoverable draft in the page instance."
    )

    historical = open_page(browser, version_url, pin=True)
    expect(historical.locator("html")).to_have_attribute("data-page-module", "first:1")


def test_package_thread_actions_share_core_admission_and_current_availability(
    browser, serve
):
    """Package controls use the core reply, settlement, reaction and undo paths."""
    url = serve(
        leaf_page(
            "Thread actions",
            '<h1>Thread actions</h1><lf-thread-actions id="actions"></lf-thread-actions>',
        ),
        layer_registry={"lf-thread-actions": THREAD_ACTIONS_DECLARATION},
        layer_widgets={"lf-thread-actions.js": THREAD_ACTIONS},
    )
    for event in [
        {
            "id": "thread-action-root",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Choose an approach.",
        },
        {
            "id": "thread-action-agent",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "thread-action-root",
            "text": "I propose one.",
        },
    ]:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    actions = page.locator("#actions")
    expect(actions).to_have_attribute("data-resolved", "false")
    actions.get_by_role("textbox", name="Package reply").fill("Package answer")
    with sending(page, "a package reply"):
        actions.get_by_role("button", name="Reply").click()
    assert (
        events_model.read_events(serve.page_dir)[-1]["parent"] == "thread-action-root"
    )
    view = open_panel_thread(page, "thread-action-root")
    expect(view).to_contain_text("Package answer")

    with sending(page, "a package resolution"):
        actions.get_by_role("button", name="Resolve").click()
    expect(actions).to_have_attribute("data-resolved", "true")
    with sending(page, "a package reply that reopens the thread"):
        actions.get_by_role("button", name="Reply").click()
    expect(actions).to_have_attribute("data-accepted", "true")
    expect(actions).to_have_attribute("data-resolved", "false")

    with sending(page, "a package reaction"):
        actions.get_by_role("button", name="React").click()
    expect(actions).to_have_attribute("data-reacted", "true")
    assert actions.evaluate("""node => {
      const thread = node.thread;
      const agent = thread.msgs.find(message => message.author === 'agent');
      const choice = agent.reactions.choices.find(choice => choice.name === 'keep');
      return thread.offers.reply && thread.offers.resolve && !thread.offers.reopen &&
        choice.inForce && choice.glyph && choice.label && Object.isFrozen(choice);
    }""")
    assert page.evaluate("""async () => {
      const {threadActions,readThreads} = await window.__lfWidgetApi();
      const thread = readThreads().threads[0];
      const agent = thread.msgs.find(message => message.author === 'agent');
      return threadActions.setReaction(thread.key, agent.key, 'keep', true) === null;
    }""")
    # The package's resolve moved the panel on from the thread; the user reads its
    # reaction back in the thread's view.
    open_panel_thread(page, "thread-action-root")
    pressed = page.locator(
        f'{PANEL_THREAD}[data-thread="thread-action-root"] .lf-react[aria-pressed="true"]'
    )
    expect(pressed).to_have_count(1)
    # Taking the reaction back is drawn while the log has yet to answer it.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    actions.get_by_role("button", name="React").click()
    holding(page, held, 1, "the same reaction withdrawn")
    expect(actions).to_have_attribute("data-reacted", "false")
    expect(pressed).to_have_count(0)
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(pressed).to_have_count(0)
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("author") == "user" and event["kind"] != "comment"
    ] == ["reply", "resolve", "reply", "reply", "undo"]


@pytest.mark.parametrize("width", [693, 1440])
def test_panel_authored_message_button_reaches_primary_reader(browser, serve, width):
    """Threads routes a thread whose widget a primary reader owns to that reader."""
    page = open_page(browser, package_workspace(serve))
    page.set_viewport_size({"width": width, "height": 900})
    workspace = page.locator("#workspace")
    page.evaluate("window.nativeEmail = document.querySelector('#email')")
    # The thread's row in Threads takes the user to the reader that owns its widget.
    page.locator(".lf-fp-threads").click()
    panel_settled(page, view="threads")
    page.locator(".lf-fp-filters button").filter(has_text="Open").click()
    page.locator('.lf-fp-thread[data-key="channel-question"]').click()
    panel_settled(page, open=False)
    message = workspace.locator('.lf-msg[data-event="channel-question"]')
    email = message.locator("#email")
    expect(email).to_be_in_viewport()
    assert email.evaluate("node => node === nativeEmail")
    with sending(page, "answer in the primary reader reached from Threads"):
        email.click()
    expect(email.get_by_role("checkbox")).to_be_checked()


@pytest.mark.parametrize(
    ("primary", "travel", "source_top", "cross_boundary"),
    [
        (True, True, 200, False),
        (True, False, 200, False),
        # A contextual card's travel, slowed until it crosses into the viewport.
        (False, True, 1000, True),
    ],
)
def test_primary_arrival_records_a_return_place_only_when_travelling(
    browser, serve, primary, travel, source_top, cross_boundary
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
    page.set_viewport_size({"width": 1440, "height": 320})
    heading = page.locator("h1")
    heading.evaluate(
        """(node, top) => {
      node.tabIndex = -1;
      node.focus({preventScroll:true});
      window.scrollTo({top, behavior:'instant'});
    }""",
        source_top,
    )
    if cross_boundary:
        # Long native frames expose the compositor's one-frame anchor delay as the
        # contextual card travels into the viewport and changes placement plane.
        page.context.new_cdp_session(page).send(
            "Emulation.setCPUThrottlingRate", {"rate": 6}
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
    assert page.evaluate("""() => {
      let active = document.activeElement;
      while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
      return active === returnTripDestination;
    }""")
    assert page.evaluate("history.length") == entries + int(travel)
    if travel:
        # Back is ordinary input as soon as arrival returns, during smooth placement.
        page.wait_for_function("top => scrollY !== top", arg=source_top)
        if cross_boundary:
            page.wait_for_function("scrollY < 200")
            expect(page.locator("#lf-margin-preview")).to_be_in_viewport()

        page.go_back()
        expect(heading).to_be_focused()
        scroll_settled(page)
        assert page.evaluate("scrollY") == source_top
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
                "ask": True,
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
    with sending(page, "answer the package's native Ask"):
        email.get_by_role("checkbox").click()
    expect(workspace.locator(".counts")).to_contain_text("Email")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    editor = workspace.get_by_role("textbox", name="Reply", exact=True)
    write(editor, "A shared draft")
    workspace.get_by_role("button", name="Feed", exact=True).click()
    expect(editor).to_have_js_property("value", "A shared draft")
    workspace.get_by_role("button", name="Shelf", exact=True).click()
    assert page.evaluate(
        "document.querySelector('#workspace').querySelector('#email') === window.originalOption"
    )
    expect(
        workspace.get_by_role("textbox", name="Reply", exact=True).last
    ).to_have_js_property("value", "A shared draft")
    with sending(page, "send the retained reply"):
        workspace.get_by_role("textbox", name="Reply", exact=True).last.press(
            "Control+Enter"
        )
    expect(workspace.get_by_text("A shared draft", exact=True)).to_be_visible()
    # One reply answers both prose asks. Counts include them, while the
    # compact answer summary names only widget choices instead of repeating prose.
    expect(workspace.locator(".counts")).to_have_text(
        "0 asks on me · 3 answered · Email"
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


def test_nested_primary_reader_keeps_native_scope_navigation_and_read_evidence(
    browser, serve
):
    """Forwarding slots preserve native widgets and respect rendered inert ancestors."""
    from render_harness import ROOT

    companion = ROOT / "examples/developer/feature-gallery.page"
    registry = {
        "lf-conversation-workspace": json.loads(
            (companion / "registry.json").read_text()
        )["lf-conversation-workspace"]
    }
    registry["lf-nested-reader"] = {
        "description": "A declared nested physical reader stage.",
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "x-content": "empty",
        "x-shadow": True,
        "x-upgrade": True,
    }
    module = (companion / "widgets/lf-conversation-workspace.js").read_text()
    module = module.replace(
        "body.append(index, this.reader);",
        """const nested = offer('lf-nested-reader');
        nested.style.display = 'block';
        nested.style.minWidth = '0';
        nested.style.minHeight = '0';
        nested.inert = true;
        const nestedStyle = document.createElement('style');
        nestedStyle.textContent = '.reader { height:100%; min-height:0; overflow:auto; }';
        shadowStage(nested, [nestedStyle, this.reader]);
        body.append(index, nested);""",
    )
    url = serve(
        leaf_page(
            "Nested package reader",
            '<h1>Nested package reader</h1><lf-conversation-workspace id="workspace"></lf-conversation-workspace>',
        ),
        layer_registry=registry,
        layer_widgets={
            "lf-conversation-workspace.js": module,
            "lf-nested-reader.js": "customElements.define('lf-nested-reader', class extends HTMLElement {});",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "nested-question",
            "attempt": "nested-question-key",
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which channel?",
            "markup": '<lf-ask id="channel-ask"><h3>Channel</h3><lf-options id="channel-options" choose><lf-option id="email">Email</lf-option><lf-option id="chat">Chat</lf-option></lf-options></lf-ask>',
        },
    )
    page = open_page(browser, url)
    workspace = page.locator("#workspace")
    email = workspace.locator("lf-option#email")
    expect(email).to_be_visible()
    page.evaluate(
        """async () => {
        window.api = await window.__lfWidgetApi();
        window.nestedOption = document.querySelector('#email');
        }"""
    )
    assert email.evaluate("node => node.getRootNode() === document")
    assert page.evaluate(
        "document.querySelector('#workspace').shadowRoot.querySelector('lf-nested-reader').shadowRoot !== null"
    )
    workspace.get_by_role("button", name="Feed", exact=True).click()
    assert email.evaluate(
        "node => node === nestedOption && node.closest('#workspace') !== null"
    )
    round_trip(page)
    assert page.evaluate("api.readThreads().threads[0].unread") == [
        {"message": "nested-question", "version": "nested-question"}
    ]
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "read"
    ]
    page.evaluate(
        "document.querySelector('#workspace').shadowRoot.querySelector('lf-nested-reader').inert = false"
    )
    workspace.get_by_role("button", name="Shelf", exact=True).click()
    expect(
        workspace.locator('.lf-msg[data-event="nested-question"]')
    ).not_to_have_class(re.compile(r"\blf-unread\b"))
    round_trip(page)
    assert [
        event["messages"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "read"
    ] == [[{"message": "nested-question", "version": "nested-question"}]]
    assert email.evaluate("node => node === nestedOption")
    assert page.evaluate(
        "async () => await api.threadActions.open('nested-question-key', {message:'nested-question-key'}) !== null"
    )
    expect(workspace.locator('.lf-msg[data-event="nested-question"]')).to_be_focused()
    assert page.evaluate("api.standingIn(document.querySelector('#workspace').reader)")
    assert page.evaluate(
        "typeof api.holdFocus(document.querySelector('#workspace').reader) === 'function'"
    )
    assert email.evaluate(
        "node => node === nestedOption && node.getRootNode() === document"
    )
    with sending(page, "answer through a nested package reader"):
        email.click()
    expect(workspace.locator(".counts")).to_contain_text("Email")


def test_primary_parts_keep_identity_and_nomination_order_through_admission(
    browser, serve
):
    """A shared outlet follows nomination order without remounting admitted turns."""
    page = open_page(browser, package_workspace(serve))
    page.evaluate("""async () => {
      window.api = await window.__lfWidgetApi();
      const workspace = document.querySelector('#workspace');
      const present = (collection, parts) => {
        const messages = collection.threads.flatMap(thread =>
          api.threadTurns(thread).map(message => [thread, message]));
        if (workspace.reversed) messages.reverse();
        for (const [thread, message] of messages)
          parts.message(thread.key, message.key, workspace.reader);
      };
      document.addEventListener('keydown', async event => {
        if (event.key === 'F8') {
          workspace.present = present;
          workspace.reader.replaceChildren();
          await workspace.presentation.update();
          window.firstPart = workspace.querySelector('[data-event="answer"]');
        }
        if (event.key === 'F9') {
          workspace.reversed = true;
          await workspace.presentation.update();
        }
        if (event.key === 'F10')
          window.created = api.threadActions.create({text:'Retain this turn'});
      });
    }""")
    page.keyboard.press("F8")
    rendered(page)
    order = """node => [...node.shadowRoot.querySelector('.reader').children]
      .flatMap(slot => slot.assignedElements())
      .map(part => part.querySelector('.lf-msg').dataset.event)"""
    workspace = page.locator("#workspace")
    assert workspace.evaluate(order) == ["channel-question", "opening", "answer"]
    page.keyboard.press("F9")
    rendered(page)
    assert workspace.evaluate(order) == ["answer", "opening", "channel-question"]
    assert page.evaluate("document.querySelector('[data-event=answer]') === firstPart")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("F10")
    holding(page, held, 1, "the new fragment's admission")
    rendered(page)
    page.evaluate("""() => {
      window.pendingPart = document.querySelector('.lf-msg[data-attempt="' + created.key + '"]');
    }""")
    assert page.evaluate("pendingPart !== null")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    page.evaluate("created.delivery")
    rendered(page)
    assert page.evaluate("""() => pendingPart.isConnected &&
      document.querySelector('.lf-msg[data-attempt="' + created.key + '"]') === pendingPart &&
      !pendingPart.dataset.event.startsWith('pending:')""")


@pytest.mark.parametrize("mode", ["Conversation", "Feed", "Reply only"])
def test_primary_reading_holds_remote_changes_before_package_layout(
    browser, serve, mode
):
    """A primary reader keeps one shown thread reading until its native notice opens it."""
    page = open_page(browser, package_workspace(serve))
    workspace = page.locator("#workspace")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    if mode == "Reply only":
        workspace.evaluate("""async workspace => {
          const api = await window.__lfWidgetApi();
          const outlet = workspace.outlet('reply-only');
          workspace.present = (collection, parts) => {
            api.setChildren(workspace.reader, [outlet]);
            parts.reply(collection.threads.find(thread => thread.id === 'opening').key, outlet);
          };
          await workspace.presentation.update({release: true});
        }""")
    else:
        workspace.get_by_role("button", name=mode, exact=True).click()
    editor = workspace.get_by_role("textbox", name="Reply", exact=True)
    editor.click()
    write(editor, "Keep this draft while updates wait.")
    assert editor.evaluate("""async editor => {
      const {scrollerFor} = await window.__lfWidgetApi();
      const {readingRegionFor} = await window.__lfCheckApi();
      const reader = document.querySelector('#workspace').reader;
      return scrollerFor(editor) === reader && readingRegionFor(editor).body === reader;
    }""")
    editor.evaluate("node => node.setSelectionRange(2, 8, 'backward')")
    page.evaluate("""() => {
      const workspace = document.querySelector('#workspace');
      window.readerNodes = [...workspace.reader.children];
      window.heldMessage = workspace.querySelector('[data-event="answer"]');
      window.heldEditor = workspace.querySelector('leaf-text');
    }""")
    before = editor.bounding_box()
    page.wait_for_timeout(600)  # Let Chrome's recent-input grace expire before news.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "message": "answer",
            "text": "A much longer edited answer. " * 25,
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "later-answer",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "opening",
            "text": "A later turn.",
        },
    )
    told(page)
    if mode != "Reply only":
        expect(workspace.locator('[data-event="answer"] .lf-msg-text')).to_have_text(
            "One paragraph."
        )
    expect(workspace.locator('[data-event="later-answer"]')).to_have_count(0)
    assert page.evaluate("""() => {
      const current = [...document.querySelector('#workspace').reader.children];
      return current.length === readerNodes.length && current.every((node, i) => node === readerNodes[i]);
    }""")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Keep this draft while updates wait.")
    assert editor.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [2, 8, "backward"]
    assert editor.bounding_box() == before
    workspace.evaluate("async node => await node.presentation.update()")
    if mode != "Reply only":
        expect(workspace.locator('[data-event="answer"] .lf-msg-text')).to_have_text(
            "One paragraph."
        )
    expect(workspace.locator('[data-event="later-answer"]')).to_have_count(0)
    assert editor.bounding_box() == before
    workspace.get_by_role(
        "button", name="1 new reply · 1 message edited", exact=True
    ).click()
    if mode != "Reply only":
        expect(workspace.locator('[data-event="later-answer"]')).to_contain_text(
            "A later turn."
        )
        expect(workspace.locator('[data-event="answer"] .lf-msg-text')).to_contain_text(
            "A much longer edited answer."
        )
        assert page.evaluate(
            "document.querySelector('#workspace [data-event=answer]') === heldMessage"
        )
    expect(
        workspace.get_by_role(
            "button", name="1 new reply · 1 message edited", exact=True
        )
    ).to_have_count(0)
    expect(editor).to_have_js_property("value", "Keep this draft while updates wait.")
    rendered(page)


def test_primary_reader_revision_replaces_owner_without_losing_thread_draft(
    browser, serve
):
    """An authored owner replacement carries the thread's session and frozen widgets."""
    page = open_page(browser, live_url(package_workspace(serve)))
    page.evaluate(
        """() => {
        window.originalWorkspace = document.querySelector('#workspace');
        window.originalOption = document.querySelector('#email');
        window.originalDocument = performance.timeOrigin;
        }"""
    )
    workspace = page.locator("#workspace")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    editor = workspace.get_by_role("textbox", name="Reply", exact=True)
    words = "Keep this unfinished answer across the revision."
    write(editor, words)
    editor.evaluate("node => node.setSelectionRange(2, 8, 'backward')")
    before = editor.evaluate("node => [node.selectionStart, node.selectionEnd]")
    stamp_page(
        serve.page_dir,
        leaf_page(
            "Package reader",
            '<h1>Package reader</h1><p id="notes">Revised announcement notes</p><lf-conversation-workspace id="replacement"></lf-conversation-workspace>',
        ),
        "Replace the reader owner while retaining its conversations",
    )
    told(page)
    # The panel's row notice for the newer version, pressed without taking the
    # editor's focus first, as a press on it does.
    page.locator(".lf-fp-row-notice-press").filter(has_text="Latest").dispatch_event(
        "click"
    )
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin === originalDocument")
    assert page.evaluate("!originalWorkspace.isConnected")
    replacement = page.locator("#replacement")
    reply = replacement.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_have_js_property("value", words)
    assert reply.evaluate("node => [node.selectionStart, node.selectionEnd]") == before
    expect(
        replacement.locator('.lf-page-thread[data-thread="opening"]')
    ).to_contain_text("One paragraph.")
    replacement.get_by_role("button", name=re.compile(r"Which channel\?")).click()
    email = replacement.locator("lf-option#email")
    expect(email).to_be_visible()
    assert email.evaluate(
        "node => node === originalOption && node.getRootNode() === document"
    )
    with sending(page, "answer the unchanged native Ask after reader replacement"):
        email.click()
    expect(replacement.locator(".counts")).to_contain_text("Email")
    replacement.get_by_role("button", name="Keep it concise.", exact=True).click()
    reply = replacement.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_have_js_property("value", words)
    with sending(page, "send the thread draft carried across reader replacement"):
        reply.press("Control+Enter")
    expect(
        replacement.locator('.lf-page-thread[data-thread="opening"]')
    ).to_contain_text(words)
    assert [
        event["parent"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply" and event.get("text") == words
    ] == ["opening"]
