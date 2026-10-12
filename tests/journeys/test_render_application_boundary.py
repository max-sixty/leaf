"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json
import re
import time

import pytest
from browser.test_render_application_boundary import (
    PAGE_DECLARATION,
    PAGE_MODULE,
    PAGE_WIDGET,
    THREAD_ACTIONS,
    THREAD_ACTIONS_DECLARATION,
    THREAD_FILTER,
    THREAD_FILTER_DECLARATION,
    THREAD_MIRROR,
    THREAD_MIRROR_DECLARATION,
    THREAD_READER,
    THREAD_READER_DECLARATION,
    activation_page,
    package_workspace,
)
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_V1,
    LIVE_V2,
    SEATED_ASK_ENTRY,
    SEATED_ASK_MODULE,
    live_url,
)
from render_harness import (
    banner_control,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    reported_browser_errors,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    take_browser_errors,
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # The agent answered without naming the thread, so it reads its opening words.
    expect(page.locator(".lf-thread-topic")).to_have_text("Decision")
    page.locator(".lf-thread-summary").click()
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
    send = page.locator(".lf-page-comment-card .lf-general .lf-compose-submit")
    write(box, "Pending **words**")
    send.click()
    holding(page, held, 1, "the shared collection's pending root")
    expect(reader).to_contain_text("Pending words")
    pending = reader.evaluate(
        "node => node.reading.threads.find(thread => thread.root.pending)"
    )
    expect(page.locator(f'.lf-thread[data-id="{pending["id"]}"]')).to_have_attribute(
        "open", ""
    )
    held.pop().continue_()
    round_trip(page)
    admitted = reader.evaluate(
        "(node, key) => node.reading.threads.find(thread => thread.key === key)",
        pending["key"],
    )
    assert admitted["id"] != pending["id"]
    assert admitted["root"]["key"] == pending["root"]["key"]
    selected = page.locator(f'.lf-thread[data-id="{admitted["id"]}"]')
    expect(selected).to_have_attribute("open", "")

    page_comment(page)
    write(box, "Refused words")
    send.click()
    holding(page, held, 1, "the shared collection's refused root")
    expect(reader).to_contain_text("Refused words")
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_attribute(
        "open", ""
    )
    if while_pending == "choose-earlier":
        # Refusal restores the earlier selection only while the provisional root
        # still owns it; a later user choice must remain the selected conversation.
        selected = page.locator('.lf-thread[data-id="question"]')
        selected.locator(".lf-thread-summary").click()
        expect(selected).to_have_attribute("open", "")
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
    consume_browser_errors(page, "400")
    expect(reader).not_to_contain_text("Refused words")
    expect(box).to_have_js_property("value", "Refused words")
    if while_pending == "choose-earlier":
        # The card takes no keys from a user who has moved on; the words wait in it.
        expect(box).to_be_hidden()
        expect(selected.locator(".lf-thread-summary")).to_be_focused()
    else:
        # Where the send left the user, the card opens again on the refused words.
        expect(box).to_be_focused()
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_count(0)
    expect(selected).to_have_attribute("open", "")
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
        page.locator(".lf-page-comment-card .lf-general .lf-compose-submit").click()
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
        page.locator(".lf-page-comment-card .lf-general .lf-compose-submit").click()
    expect(first.locator("li")).to_have_text("Delta")
    assert first.evaluate("node => node.updates") > first_before
    assert removed.evaluate("node => node.updates") == stopped_at

    thread_id = first.evaluate(
        "node => node.reading.threads.find(thread => thread.root.body.text.trim() === 'Delta').id"
    )
    # The widget's route through core opens the shut Threads on that thread.
    first.locator("button", has_text="Delta").click()
    expect(page.locator(f'.lf-thread[data-id="{thread_id}"]')).to_be_visible()


def test_package_thread_mirrors_share_core_conversation_without_claiming_placement(
    browser, serve
):
    """Two package containers render one Thread and keep independent lifetimes."""
    url = serve(
        leaf_page(
            "Thread mirrors",
            '<h1>Thread mirrors</h1><button id="mirror-subject">Subject</button>'
            '<lf-thread-mirror id="first" filter="Shared"></lf-thread-mirror>'
            '<lf-thread-mirror id="second" filter="opening"></lf-thread-mirror>',
        ),
        layer_registry={"lf-thread-mirror": THREAD_MIRROR_DECLARATION},
        layer_widgets={"lf-thread-mirror.js": THREAD_MIRROR},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "shared-thread",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Shared opening",
            "anchor": {"section": "mirror-subject"},
        },
    )
    page = open_page(browser, url)
    first = page.locator("#first")
    second = page.locator("#second")
    expect(first.locator(".lf-page-thread")).to_contain_text("Shared opening")
    expect(second.locator(".lf-page-thread")).to_contain_text("Shared opening")
    assert first.evaluate("node => node.updates")
    assert second.evaluate("node => node.updates")
    expect(page.locator('.lf-margin-marker[data-lf-kinds="comment"]')).to_have_count(1)

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator('.lf-thread[data-id="shared-thread"]')).to_be_visible()
    page.locator(".lf-threads-toggle").click()

    with sending(page, "a reply from the first package mirror"):
        write(
            first.locator(".lf-page-thread .lf-thread-reply leaf-text"), "Shared reply"
        )
        first.locator(".lf-page-thread .lf-thread-reply").get_by_role(
            "button", name="Send"
        ).click()
    expect(first.locator(".lf-page-thread")).to_contain_text("Shared reply")
    expect(second.locator(".lf-page-thread")).to_contain_text("Shared reply")
    expect(page.locator('.lf-thread[data-id="shared-thread"]')).to_contain_text(
        "Shared reply"
    )
    second.locator("input").fill("Absent")
    expect(second.locator(".lf-page-thread")).to_have_count(0)
    expect(first.locator(".lf-page-thread")).to_contain_text("Shared reply")
    second.locator("input").fill("opening")
    expect(second.locator(".lf-page-thread")).to_contain_text("Shared reply")

    second.evaluate("node => { node.holding = true; node.consumer.update(); }")
    expect(second).to_have_attribute("data-held", "true")
    with sending(page, "a reply while a package mirror is held"):
        write(first.locator(".lf-page-thread .lf-thread-reply leaf-text"), "While held")
        first.locator(".lf-page-thread .lf-thread-reply").get_by_role(
            "button", name="Send"
        ).click()
    expect(first.locator(".lf-page-thread")).to_contain_text("While held")
    expect(page.locator('.lf-thread[data-id="shared-thread"]')).to_contain_text(
        "While held"
    )
    assert second.evaluate("node => node.signals.at(-2).aborted")
    assert not page.evaluate(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport('/runtime/semantic-state.js');
          return readApplicationPresentation().pending.includes('thread');
        }"""
    )
    second.evaluate("""node => {
      node.holding = false;
      for (const release of node.releases.splice(0)) release();
      node.removeAttribute('data-held');
      node.consumer.update();
    }""")
    # The log answered the reply before the held mirror drew it, so to that mirror it is
    # news, which waits behind a notice rather than moving its reply box. It is the
    # user's own message, not a reply.
    expect(second.locator(".lf-thread-news")).to_have_text("1 new message")
    expect(second.locator(".lf-page-thread")).not_to_contain_text("While held")

    # This lifecycle removal follows the user's clearing their local filter.
    second.locator("input").fill("")
    second_handle = second.element_handle()
    second.evaluate("node => node.remove()")
    stopped_at = second_handle.evaluate("node => node.updates")
    with sending(page, "a reply after the second mirror disconnected"):
        write(
            first.locator(".lf-page-thread .lf-thread-reply leaf-text"), "After removal"
        )
        first.locator(".lf-page-thread .lf-thread-reply").get_by_role(
            "button", name="Send"
        ).click()
    expect(first.locator(".lf-page-thread")).to_contain_text("After removal")
    assert second_handle.evaluate("node => node.updates") == stopped_at
    expect(page.locator('.lf-margin-marker[data-lf-kinds="comment"]')).to_have_count(1)
    page.locator("#mirror-subject").focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(page.locator("#mirror-subject")).to_be_focused()
    expect(page.locator(".lf-margin-thread")).to_contain_text("After removal")


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
        latest = banner_control(page, ".lf-latest-chip")
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


@pytest.mark.parametrize(
    "place",
    ["inline-editor", "page-comment", "choose-earlier", "leave-displaced-title"],
)
def test_a_failed_list_candidate_restores_its_complete_committed_reading(
    browser, serve, place
):
    """Rows, count, narrowing, and native islands roll back as one checkpoint."""
    layer = {**PAGE_DECLARATION, "lf-verdict": SEATED_ASK_ENTRY}
    widgets = {"lf-local.js": PAGE_WIDGET, "lf-verdict.js": SEATED_ASK_MODULE}
    url = serve(
        leaf_page(
            "Thread rollback",
            '<h1>Review</h1><p id="earlier">An earlier passage.</p>'
            '<p id="selected">The selected passage.</p><lf-verdict id="proposal" asks>Ship it?</lf-verdict>',
        ),
        layer_registry=layer,
        layer_widgets=widgets,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "earlier-thread",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "earlier"},
            "text": "An earlier accepted conversation.",
        },
    )
    selected_record = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "selected-thread",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "selected"},
            "text": "The selected accepted conversation.",
        },
    )
    kept = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "kept-thread",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "proposal"},
            "text": "Keep this thread and its editor.",
        },
    )
    # A fixed wall clock keeps every age label still, so no clock repaint starts a
    # reading of its own while the failing ones are arranged.
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    context.clock.set_fixed_time(time.time())
    page = open_page(browser, live_url(url), context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    selected = page.locator('.lf-thread[data-id="selected-thread"]')
    expect(page.locator(".lf-thread").first).not_to_have_attribute(
        "data-id", "selected-thread"
    )
    selected.locator(".lf-thread-summary").click()
    expect(selected).to_have_attribute("open", "")
    inline = page.locator(f'#proposal > .lf-thread-seat > [data-thread="{kept["id"]}"]')
    editor = inline.locator(":scope > .lf-thread-reply leaf-text")
    write(editor, "draft survives sibling rollback")
    editor.evaluate("node => node.setSelectionRange(6, 14, 'backward')")
    expect(editor).to_be_focused()
    general = page.locator(".lf-page-comment-card .lf-general leaf-text")
    if place == "page-comment":
        page_comment(page)
    elif place in {"choose-earlier", "leave-displaced-title"}:
        selected.locator(".lf-thread-summary").click()

    # Choosing an earlier thread while the failing reading is in flight starts two
    # newer readings (its disclosure's and the publication's), and an attempt a newer
    # one supersedes restores nothing. Both fail too, so restoring the committed reading
    # is the last one's to do. There each failing reading waits before it paints and
    # then fails in the same turn as its paint, as a renderer exception does, so the
    # test decides which attempt is current and no candidate stands on screen between.
    choose_earlier = place == "choose-earlier"
    failures = 3 if choose_earlier else 1
    page.evaluate(
        "([failures, gateBeforePaint]) => {"
        " window.listFailures = failures; window.gateBeforePaint = gateBeforePaint; }",
        [failures, choose_earlier],
    )
    page.evaluate(
        """async id => {
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          let release;
          const promise = new Promise(done => { release = done; });
          window.threadPreparation = {promise, release};
          window.threadPreparationSettled = false;
          promise.then(() => { window.threadPreparationSettled = true; });
          window.__heldLocalPresentations = new Map([['thread-held', promise]]);
          window.readLeafPresentation = presentation.readApplicationPresentation;
          window.keptPanel = document.querySelector(
            `.lf-thread[data-id="${id}"]`
          );
          window.keptInline = document.querySelector(
            `#proposal > .lf-thread-seat > [data-thread="${id}"]`
          );
          window.keptEditor = keptInline.querySelector(':scope > .lf-thread-reply leaf-text');

          const list = document.querySelector('leaf-thread-list');
          const present = list.present.bind(list);
          let failures = window.listFailures;
          let releaseFailure;
          const failedCandidate = new Promise(done => { releaseFailure = done; });
          window.releaseFirstListFailure = releaseFailure;
          let releaseNext;
          const next = new Promise(done => { releaseNext = done; });
          window.releaseNextReading = releaseNext;
          window.nextReadingReleased = false;
          list.present = async model => {
            const candidate = model.rows.some(
              row => row.kind === 'thread' &&
                row.descriptor.id === 'held-widget-thread'
            );
            if (!candidate) return present(model);
            if (failures > 0) {
              const attempt = failures--;
              if (window.gateBeforePaint) {
                window.heldCandidates = (window.heldCandidates ?? 0) + 1;
                await failedCandidate;
                await present(model);
              } else {
                await present(model);
                window.heldCandidates = 1;
                await failedCandidate;
              }
              window.completeListFailures = (window.completeListFailures ?? 0) + 1;
              throw new Error('injected complete-list failure');
            }
            if (!window.nextReadingReleased) {
              window.nextReadingHeld = true;
              await next;
            }
            return present(model);
          };
        }""",
        kept["id"],
    )

    # One departed root and two arrivals distinguish candidate and committed counts.
    # Hold delivery while the admitted undo and arriving frozen content become one
    # application reading. The failed candidate removes the selected root; retention
    # must restore the complete committed reading before the next reading, held here,
    # proceeds.
    held_readings = []
    page.route("**/api/state*", lambda route: held_readings.append(route))
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": selected_record["id"]},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "held-widget-thread",
            "author": "user",
            "revision": 1,
            "text": "Prepare the frozen widget.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "id": "held-widget-reply",
            "author": "agent",
            "revision": 1,
            "parent": "held-widget-thread",
            "text": "This preparation remains held.",
            "markup": '<lf-local id="thread-held" choice="idle"></lf-local>',
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "another-arriving-thread",
            "author": "user",
            "revision": 1,
            "text": "Another accepted conversation arrived.",
        },
    )
    page.unroute("**/api/state*")
    for route in held_readings:
        route.continue_()
    page.wait_for_function("() => window.heldCandidates === 1")
    # Later state reads wait too while the failures are arranged, so no reading but
    # the ones the test starts can supersede them.
    held_readings = []
    page.route("**/api/state*", lambda route: held_readings.append(route))
    if choose_earlier:
        selected = page.locator('.lf-thread[data-id="earlier-thread"]')
        selected.locator(".lf-thread-summary").click()
        expect(selected).to_have_attribute("open", "")
        # Both of the choice's readings stand at the gate, so the first is superseded,
        # and all three fail once it opens.
        page.wait_for_function("() => window.heldCandidates === 3")
        page.evaluate("window.releaseFirstListFailure()")
    else:
        expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 4")
        if place == "leave-displaced-title":
            expect(
                page.locator('[data-withdrawn="selected-thread"] button')
            ).to_be_focused()
            page_comment(page)
        page.evaluate("window.releaseFirstListFailure()")
    page.wait_for_function(
        "failures => window.completeListFailures === failures", arg=failures
    )
    page.unroute("**/api/state*")
    for route in held_readings:
        route.continue_()
    page.wait_for_function(
        """failures => window.completeListFailures === failures &&
          window.nextReadingHeld === true""",
        arg=failures,
    )

    assert page.evaluate("() => !window.threadPreparationSettled")
    expect(page.locator("#thread-held")).to_have_count(0)
    expect(page.locator('[data-id="held-widget-thread"]')).to_have_count(0)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 3")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("3 open threads")
    expect(selected).to_have_attribute("open", "")
    assert page.evaluate(
        """id => {
          const panel = document.querySelector(`.lf-thread[data-id="${id}"]`);
          const inline = document.querySelector(
            `#proposal > .lf-thread-seat > [data-thread="${id}"]`
          );
          return panel === window.keptPanel && inline === window.keptInline &&
            inline.querySelector(':scope > .lf-thread-reply leaf-text') === window.keptEditor;
        }""",
        kept["id"],
    ), "list retention replaced a committed panel card, seat, or editor"
    expect(editor).to_have_js_property("value", "draft survives sibling rollback")
    if place == "inline-editor":
        expect(editor).to_be_focused()
    elif place == "choose-earlier":
        expect(selected.locator(".lf-thread-summary")).to_be_focused()
    else:
        expect(general).to_be_focused()
    assert editor.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [6, 14, "backward"]
    assert "thread" in page.evaluate("window.readLeafPresentation().pending")
    # The restored card must stand for a frame before the next reading withdraws it;
    # the choice made while the reading failed cannot hide a later jump.
    page.evaluate("lfShiftsJudged()")
    restored_top = page.evaluate("window.keptPanel.getBoundingClientRect().top")

    # The next reading paints the whole candidate again and then reaches the
    # independently held frozen-widget preparation. Only that complete reading may commit.
    page.evaluate(
        """() => {
          window.nextReadingReleased = true;
          window.releaseNextReading();
        }"""
    )
    page.wait_for_function(
        """() => document.querySelector('#thread-held') &&
          document.querySelector('.lf-threads-toggle')?.textContent === 'Threads: 4' &&
          window.readLeafPresentation().pending.includes(
            'widget:thread-held:preparation'
          )""",
    )
    page.evaluate("window.threadPreparation.release('prepared')")
    page.wait_for_function("() => window.threadPreparationSettled === true")
    page.wait_for_function(
        "() => !window.readLeafPresentation().pending.includes('thread')",
    )
    expect(page.locator("#thread-held")).to_have_count(1)
    expect(page.locator('[data-id="held-widget-thread"]')).to_have_count(1)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 4")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("4 open threads")
    if place == "choose-earlier":
        expect(selected).to_have_attribute("open", "")
    else:
        expect(selected).to_have_count(0)
    assert page.evaluate(
        """id => {
          const panel = document.querySelector(`.lf-thread[data-id="${id}"]`);
          const inline = document.querySelector(
            `#proposal > .lf-thread-seat > [data-thread="${id}"]`
          );
          return panel === window.keptPanel && inline === window.keptInline &&
            inline.querySelector(':scope > .lf-thread-reply leaf-text') === window.keptEditor;
        }""",
        kept["id"],
    ), "the next reading replaced a committed panel card, seat, or editor"
    expect(editor).to_have_js_property("value", "draft survives sibling rollback")
    if place == "choose-earlier":
        expect(page.locator('[data-withdrawn="selected-thread"]')).to_have_count(1)
        assert page.evaluate(
            "window.keptPanel.getBoundingClientRect().top"
        ) == pytest.approx(restored_top, abs=0.1)
    expected_errors = ["leaf: Presentation failed: injected complete-list failure"]
    page.evaluate("lfShiftsJudged()")
    errors = take_browser_errors(page)
    assert [error.splitlines()[0] for error in errors] == expected_errors, errors


@pytest.mark.parametrize("place", ["closed", "selected", "scrolled", "scaled"])
def test_an_external_withdrawal_keeps_the_readers_allocation(browser, serve, place):
    """Absent threads retain room, never live controls or semantic membership."""
    selected = place not in {"closed", "scaled"}
    url = serve(
        leaf_page(
            "Withdrawn thread",
            '<h1>Review</h1><p id="one">First passage.</p><p id="two">Next passage.</p>',
        ),
        layer_registry=PAGE_DECLARATION,
        layer_widgets={"lf-local.js": PAGE_WIDGET},
    )
    first = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "first-thread",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "one"},
            "text": "The conversation that will be withdrawn."
            + (
                "\n\n"
                + "\n\n".join(
                    f"Paragraph {i}: A long conversation stays readable while the panel scrolls."
                    for i in range(28)
                )
                if place == "scrolled"
                else ""
            ),
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "next-thread",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "two"},
            "text": "The conversation that stays.",
        },
    )
    if place == "scrolled":
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "id": "long-reply",
                "author": "agent",
                "revision": 1,
                "parent": first["id"],
                "text": "\n\n".join(
                    f"Paragraph {i}: The full conversation remains available as the reader scrolls."
                    for i in range(28)
                ),
            },
        )
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "id": "widget-reply",
                "author": "agent",
                "revision": 1,
                "parent": first["id"],
                "text": "A frozen control in the withdrawn thread.",
                "markup": '<lf-local id="withdraw-widget" choice="idle"></lf-local>',
            },
        )
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    if place == "scaled":
        page.add_style_tag(
            content=".lf-thread-panel { transform:scale(1.2); transform-origin:top right; }"
        )
        assert (
            page.locator(".lf-thread-panel").evaluate(
                "node => getComputedStyle(node).transform"
            )
            == "matrix(1.2, 0, 0, 1.2, 0, 0)"
        )
    first_card = page.locator('.lf-threads > [data-id="first-thread"]')
    next_card = page.locator('.lf-threads > [data-id="next-thread"]')
    (first_card if selected else next_card).locator(".lf-thread-summary").click()
    if place == "scrolled":
        write(
            first_card.locator(":scope > .lf-thread-reply leaf-text"),
            "A draft for this conversation",
        )
        expect(page.locator("#withdraw-widget")).not_to_have_count(0)
        panel = page.locator("leaf-thread-list")
        box = panel.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.wheel(0, 600)
        page.wait_for_function(
            "document.querySelector('leaf-thread-list').scrollTop > 0"
        )
        scroll_settled(page, "leaf-thread-list")
        assert first_card.evaluate(
            "node => node.getBoundingClientRect().top < node.parentElement.getBoundingClientRect().top"
        )
    rendered(page)
    allocation = first_card.evaluate("node => node.getBoundingClientRect().height")
    position = next_card.evaluate("node => node.getBoundingClientRect().top")
    if place == "scrolled":
        for reply in ["long-reply", "widget-reply"]:
            append_carried_log_record(
                serve.page_dir, {"kind": "undo", "author": "agent", "undoes": reply}
            )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "undo",
            "id": "withdraw-first",
            "author": "user",
            "revision": 1,
            "undoes": first["id"],
        },
    )
    told(page)
    withdrawn = page.locator('[data-withdrawn="first-thread"]')
    expect(withdrawn).to_contain_text("Thread withdrawn")
    expect(first_card).to_have_count(0)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("1 open thread")
    assert withdrawn.evaluate(
        "node => node.getBoundingClientRect().height"
    ) == pytest.approx(allocation, abs=0.1)
    assert next_card.evaluate(
        "node => node.getBoundingClientRect().top"
    ) == pytest.approx(position, abs=0.1)
    if selected:
        expect(withdrawn.locator("button")).to_be_focused()
        expect(next_card).not_to_have_attribute("open", "")
        assert withdrawn.locator("button").evaluate("""node => {
            const box = node.getBoundingClientRect();
            const panel = node.closest('leaf-thread-list').getBoundingClientRect();
            return box.top >= panel.top && box.bottom <= panel.bottom;
        }""")
    else:
        expect(next_card.locator(".lf-thread-summary")).to_be_focused()
        expect(next_card).to_have_attribute("open", "")
    if place == "scrolled":
        expect(page.locator("#withdraw-widget")).to_have_count(0)
        # The subject has left the document: its editor ends, while the draft's
        # independent saved owner keeps the words for a genuine return.
        page.evaluate("lfWordsJudged()")
        assert take_browser_errors(page) == [
            'typed words left the screen without a key or press: "A draft for this conversation" in leaf-text.lf-ui'
        ]
    # A view change or choosing another conversation releases retained news too.
    if place == "scaled":
        find = page.get_by_role("searchbox", name="Find in threads")
        find.fill("stays")
        rendered(page)
        expect(withdrawn).to_have_count(0)
        expect(find).to_be_focused()
        find.press("Escape")
    elif place == "selected":
        page.keyboard.press("t")
    else:
        withdrawn.get_by_role("button", name="Dismiss").focus()
        page.keyboard.press("Enter")
    rendered(page)
    expect(withdrawn).to_have_count(0)
    expect(next_card).to_have_attribute("open", "")
    expect(next_card.locator(".lf-thread-summary")).to_be_focused()

    if place == "scrolled":
        assert (
            page.evaluate("""async () => {
            const {loadDraft} = await window.__lfRuntimeImport('/runtime/drafts.js');
            return loadDraft('reply:first-thread');
        }""")
            == "A draft for this conversation"
        )


def test_a_refused_thread_reading_leaves_a_user_who_moved_on_where_they_went(
    browser, serve
):
    """A seat the user left while a reading waited does not pull them back to it.

    Rolling back a refused reading puts back only what the reading itself took: a user
    who stood in one seat's reply when it began and moved to another seat's box before
    it failed keeps the box they moved to, caret included."""
    layer = {**PAGE_DECLARATION, "lf-verdict": SEATED_ASK_ENTRY}
    widgets = {"lf-local.js": PAGE_WIDGET, "lf-verdict.js": SEATED_ASK_MODULE}
    url = serve(
        leaf_page(
            "Thread rollback",
            '<h1>Review</h1><lf-verdict id="proposal" asks>Ship it?</lf-verdict>'
            '<lf-verdict id="other" asks>Hold it?</lf-verdict>',
        ),
        layer_registry=layer,
        layer_widgets=widgets,
    )
    kept = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "kept-thread",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "proposal"},
            "text": "The user starts here.",
        },
    )
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    left = page.locator(
        f'#proposal > .lf-thread-seat > [data-thread="{kept["id"]}"]'
        " > .lf-thread-reply leaf-text"
    )
    went = page.locator("#other > .lf-thread-seat leaf-text")
    write(left, "where the user was")
    expect(left).to_be_focused()

    # The reading that brings the arriving thread waits at a gate, and its paint fails,
    # so the whole reading is refused.
    page.evaluate(
        """() => {
          const list = document.querySelector('leaf-thread-list');
          const present = list.present.bind(list);
          let open;
          window.gate = new Promise(done => { open = done; });
          window.openGate = open;
          list.present = async model => {
            if (!model.rows.some(row => row.descriptor?.id === 'arriving')) {
              return present(model);
            }
            window.waiting = true;
            await window.gate;
            throw new Error('injected refusal');
          };
        }"""
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "arriving",
            "author": "user",
            "revision": 1,
            "text": "A thread whose reading is refused once.",
        },
    )
    page.wait_for_function("() => window.waiting === true")

    write(went, "where the user went")
    went.evaluate("node => node.setSelectionRange(6, 10, 'backward')")
    page.evaluate("() => window.openGate()")
    reported_browser_errors(
        page,
        "leaf: Presentation failed: injected refusal",
    )
    expect(page.locator('[data-id="arriving"]')).to_have_count(0)

    expect(went).to_be_focused()
    expect(went).to_have_js_property("value", "where the user went")
    assert went.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [6, 10, "backward"]
    expect(left).to_have_js_property("value", "where the user was")


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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator('.lf-thread[data-id="thread-action-root"]')).to_contain_text(
        "Package answer"
    )

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
        choice.standing && choice.glyph && choice.label && Object.isFrozen(choice);
    }""")
    assert page.evaluate("""async () => {
      const {threadActions,readThreads} = await window.__lfRuntimeImport('/runtime/widget-api.js');
      const thread = readThreads().threads[0];
      const agent = thread.msgs.find(message => message.author === 'agent');
      return threadActions.setReaction(thread.key, agent.key, 'keep', true) === null;
    }""")
    pressed = page.locator(
        '.lf-thread[data-id="thread-action-root"] .lf-react[aria-pressed="true"]'
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
    """The panel's compact message routes to the primary that owns its widget."""
    page = open_page(browser, package_workspace(serve))
    page.set_viewport_size({"width": width, "height": 900})
    workspace = page.locator("#workspace")
    page.evaluate("window.nativeEmail = document.querySelector('#email')")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel = page.locator(".lf-thread-panel")
    panel.get_by_role("button", name="Open interactive reply", exact=True).click()
    message = workspace.locator('.lf-msg[data-event="channel-question"]')
    expect(message).to_be_focused()
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
          const api = await window.__lfRuntimeImport('/runtime/widget-api.js');
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
    # One reply answers both prose Questions. Counts include them, while the
    # compact answer summary names only widget choices instead of repeating prose.
    expect(workspace.locator(".counts")).to_have_text(
        "0 asks on you · 3 answered · Email"
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
        window.api = await window.__lfRuntimeImport('/runtime/widget-api.js');
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
      window.api = await window.__lfRuntimeImport('/runtime/widget-api.js');
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
          const api = await window.__lfRuntimeImport('/runtime/widget-api.js');
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
    write(editor, "Keep this draft while updates wait.")
    assert editor.evaluate("""async editor => {
      const {scrollerFor, readingRegionFor} = await window.__lfRuntimeImport('/runtime/reading-regions.js');
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
    banner_control(page, ".lf-latest-chip").focus()
    page.keyboard.press("Enter")
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
