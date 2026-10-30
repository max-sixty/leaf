"""Text and widgets inside thread messages: Markdown and suggestion text, frozen
widgets' initial state and replay, undo, refusals and the Done press."""

import re

import pytest
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import MARKDOWN_REPLY, THREAD_OBLIGATIONS, live_url
from render_cases_navigation import actions
from render_harness import (
    PANEL_THREAD,
    RELEASE_FOCUS,
    REPLY_HOST_PAGE,
    SAMPLE_MARKUP,
    SAMPLE_TEXT,
    consume_browser_errors,
    draft_control,
    expect_obligations_answered,
    expect_on_me,
    holding,
    http_error_console,
    open_page,
    post_event,
    refuse,
    round_trip,
    stamp_page,
    told,
    undo,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import one_frame

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_reply_renders_the_markdown_it_was_written_in(browser, serve):
    """A message's text is Markdown, rendered here by the page's own vendored layer —
    the wire carries the log's words and nothing else. Every raw tag renders as the
    characters it was written in, a block of tags as much as prose saying Vec<T>, and
    swallowing it into an element would lose the words in front of the user with nothing saying so. What the
    panel adds is the page's own dress: the theme's element rules are at document level
    and reach in, a fenced block colors from the tokenizer a version's <pre><code>
    uses, and a bare URL arrives as the link the user will want to follow."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "which one wins?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-decision",
            "revision": 1,
            "text": MARKDOWN_REPLY,
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, "c-decision")
    body = view.locator(".lf-msg.agent .lf-msg-body")
    expect(body.locator("li")).to_have_count(2)
    expect(body.locator("strong")).to_have_text("behind")
    expect(body.locator("blockquote")).to_have_text("which one wins?")
    expect(body.locator("pre code [data-lf-syn]").first).to_have_text("def")
    # Tags are text in this dialect, a block of them as much as one in a sentence, so
    # markup shown without a fence keeps the lines it was written in.
    markup = body.locator("p", has_text="<lf-callout>")
    assert markup.inner_text() == "<lf-callout>\n<div>a tile</div>\n</lf-callout>"
    link = body.locator('a[href="https://example.com/notes"]')
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", re.compile(r"(?:^| )noopener(?: |$)"))
    expect(link).to_have_attribute("data-lf-external", "")
    expect(
        body.locator(
            'a[href^="javascript:"], a[href^="data:"], '
            'a[href^="file:"], a[href^="editor:"]'
        )
    ).to_have_count(0)
    expect(body).to_contain_text(
        "Unsafe destinations stay words: script, inline data, local file, "
        "and custom handler."
    )
    # The paragraph's asterisks are gone from the words, not merely hidden, and the
    # raw tag's characters are still among them: what the user can select is what
    # the message says.
    text = body.inner_text()
    assert "**" not in text and "Vec<T>" in text


def test_a_suggestion_shows_the_characters_it_proposes(browser, serve):
    """A suggestion's words are bound for the page verbatim, so the panel shows them
    as typed. Rendering them would promise the user an italic where the next
    version carries the asterisks they wrote."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "s1",
            "author": "user",
            "revision": 1,
            "suggestion": True,
            "text": "Retry up to *five* times.",
        },
    )
    page = open_page(browser, url)
    body = open_panel_thread(page, "s1").locator(".lf-msg-body.lf-suggest-body")
    expect(body).to_have_text("Retry up to *five* times.")
    expect(body.locator("em")).to_have_count(0)


@pytest.mark.parametrize("asynchronous", [False, True], ids=["draft", "async-body"])
def test_thread_body_initial_state_comes_from_source_before_upgrade(
    browser, serve, asynchronous
):
    """Frozen widgets undo to source even when presentation rewrites its body."""
    tag = "lf-delayed-body" if asynchronous else "lf-draft"
    layer = {}
    if asynchronous:
        layer = {
            "layer_registry": {
                tag: {
                    "description": "A body normalized by an asynchronous renderer.",
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "restated": {"type": "boolean"},
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                    "x-content": "data",
                    "x-upgrade": True,
                    "x-verbatim": True,
                    "x-state": {
                        "edit": {
                            "unit": "widget",
                            "record": {"kind": "body"},
                        }
                    },
                    "x-example": '<lf-delayed-body id="example"><pre>Text</pre></lf-delayed-body>',
                },
            },
            "layer_widgets": {
                f"{tag}.js": """
import {LeafElement, keepsText} from '/runtime/widget-api.js';
customElements.define('lf-delayed-body', class extends LeafElement {
  setup() {
    this.controller.present(new Promise(resolve => requestAnimationFrame(() => {
      this.querySelector('pre').textContent = 'Presentation-only rewrite.';
      resolve();
    })));
  }
  render() { keepsText(this.querySelector('pre'), this.state.edit.value); }
});
"""
            },
        }
    url = serve(REPLY_HOST_PAGE, **layer)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "body-question",
            "author": "user",
            "revision": 1,
            "text": "Please draft it.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "body-question",
            "text": "Edit these words.",
            "markup": f'<{tag} id="reply-body"><pre>\n    First line.\n    Second line.\n</pre></{tag}>',
        },
    )
    page = open_page(browser, live_url(url))
    open_panel_thread(page, "body-question")
    widget = page.locator("#reply-body")
    original = widget.element_handle()
    body = widget.locator("pre" if asynchronous else ".lf-draft-body")
    expect(body).to_have_text(
        "Presentation-only rewrite." if asynchronous else "First line. Second line."
    )
    response = post_event(
        page,
        live_url(url).split("?")[0] + "api/event",
        data={
            "kind": "action",
            "widget": "reply-body",
            "action": "edit",
            "detail": {"value": "User's exact words.\n"},
            "revision": 1,
        },
    )
    assert response.ok, response.text()
    told(page)
    assert body.text_content() == "User's exact words.\n"
    # The thread opened with the caret in its reply, where `z` is a letter.
    page.evaluate(RELEASE_FOCUS)
    undo(page)
    expect(body).to_have_text("First line. Second line.")
    if asynchronous:
        assert body.text_content() == "    First line.\n    Second line.\n"
    else:
        expect(body).to_have_attribute(
            "data-lf-source-words", "    First line.\n    Second line.\n"
        )
    assert original.evaluate("node => node === document.getElementById('reply-body')")


def test_crossed_responses_wait_for_the_same_frozen_widget_module(browser, serve):
    """A later POST must join the reply's import before mounting or capturing it."""
    host = REPLY_HOST_PAGE.replace(
        "</main>",
        """
<lf-ask id="delivery"><h2>Which delivery?</h2>
  <lf-options id="delivery-choice" choose>
    <lf-option id="delivery-now">Now</lf-option>
    <lf-option id="delivery-later">Later</lf-option>
  </lf-options>
</lf-ask></main>""",
    )
    url = serve(host)
    page = open_page(browser, live_url(url))
    held = []
    page.route("**/widgets/lf-draft.js", lambda route: held.append(route))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "draft-question",
            "author": "user",
            "revision": 1,
            "text": "Please draft this.",
        },
    )
    with page.expect_request("**/widgets/lf-draft.js"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "parent": "draft-question",
                "author": "agent",
                "revision": 1,
                "text": "Edit this draft.",
                "markup": '<div id="crossed-region">'
                '<lf-tally id="crossed-tally" for="crossed-region" next></lf-tally>'
                '<lf-draft id="crossed-draft"><pre>\n    First line.\n    Second line.\n'
                "</pre></lf-draft></div>",
            },
        )
    holding(page, held, 1, "the frozen draft module")
    assert len(held) == 1
    frozen_reading = """async () => {
      const {readApplication} = await window.__lfCheckApi();
      const root = readApplication();
      return {
        descriptor: root.document.descriptors.has('crossed-draft'),
        authored: root.document.authored.has('crossed-draft'),
        body: root.effective.widgets.get('crossed-draft')?.state.edit?.value ?? null,
        mounted: Boolean(document.getElementById('crossed-draft')),
      };
    }"""
    assert page.evaluate(frozen_reading) == {
        "descriptor": False,
        "authored": False,
        "body": None,
        "mounted": False,
    }
    with page.expect_response("**/api/event") as newer:
        page.locator("#delivery-now").click()
    assert newer.value.ok
    newer.value.finished()
    one_frame(page)
    assert page.locator("#crossed-draft").count() == 0
    held[0].continue_()
    page.unroute("**/widgets/lf-draft.js")
    told(page)
    # The reply's widget mounts where its thread is drawn, which is the panel's view
    # once the user opens it there.
    reading = page.evaluate(frozen_reading)
    assert {key: reading[key] for key in ("descriptor", "authored", "body")} == {
        "descriptor": True,
        "authored": True,
        "body": "    First line.\n    Second line.\n",
    }
    open_panel_thread(page, "draft-question")
    expect(page.locator("#crossed-draft")).to_have_count(1)
    expect(page.locator("#crossed-tally .lf-tally-face")).to_have_count(1)
    expect(page.locator("#crossed-tally .lf-tally-next")).to_be_disabled()
    widget = page.locator("#crossed-draft")
    original = widget.element_handle()
    body = widget.locator(".lf-draft-body")
    expect(body).to_have_text("First line. Second line.")
    expect(body).to_have_attribute(
        "data-lf-source-words", "    First line.\n    Second line.\n"
    )
    draft_control(page, "edit", "crossed-draft").click()
    write(widget.locator("leaf-text"), "A user's exact words.\n")
    draft_control(page, "save", "crossed-draft").click()
    round_trip(page)
    assert body.text_content() == "A user's exact words.\n"
    # The thread opened with the caret in its reply, where `z` is a letter.
    page.evaluate(RELEASE_FOCUS)
    undo(page)
    expect(body).to_have_text("First line. Second line.")
    expect(body).to_have_attribute(
        "data-lf-source-words", "    First line.\n    Second line.\n"
    )
    assert original.evaluate(
        "node => node === document.getElementById('crossed-draft')"
    )
    expect(page.locator("#delivery-now")).to_have_attribute("chosen", "")


def test_a_reply_widget_replays_and_withdraws_its_action(browser, serve):
    """A widget inside a reply exists only once the panel has rendered the log,
    which is later than everything on the page — so the replay runs at the end of
    a poll, after that render, and an action naming a widget it doesn't find is
    one no version will ever hold (an honored suggestion, whose id the honoring
    version dropped) rather than one to look for again on the next poll. Its authored
    record is captured from frozen source before the reply is admitted, so withdrawing
    the action restores that baseline without authored version markup for the chrome
    widget."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "Which of these?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-decision",
            "revision": 1,
            "text": SAMPLE_TEXT,
            "markup": SAMPLE_MARKUP,
        },
    )
    decision = append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "rp-live",
            "action": "choose",
            "detail": {"value": ["rp-shim"]},
        },
    )
    page = open_page(browser, live_url(url))
    open_panel_thread(page, "c-decision")
    expect(page.locator("#rp-shim")).to_have_attribute("chosen", "")
    assert page.locator("#rp-live lf-option[chosen]").count() == 1

    # Chrome belongs to the thread rather than the page version. Its action therefore
    # still stands, and is still the user's newest undoable gesture, after the page
    # advances around the thread.
    stamp_page(d, REPLY_HOST_PAGE, "v2")
    wait_for_revision(page, 2)
    open_panel_thread(page, "c-decision")
    expect(page.locator("#rp-shim")).to_have_attribute("chosen", "")

    # The thread opened with the caret in its reply, where `z` is a letter.
    page.evaluate(RELEASE_FOCUS)
    undo(page)
    assert [
        event["undoes"]
        for event in events_model.read_events(d)
        if event["kind"] == "undo"
    ] == [decision["id"]]
    expect(page.locator("#rp-live lf-option[chosen]")).to_have_count(0)


def _gesture_request(request):
    return "/api/event" in request.url and bool(request.post_data_json.get("attempt"))


def _hold_gesture(route, held):
    if _gesture_request(route.request):
        held.append(route)
    else:
        route.continue_()


def test_a_thread_answer_is_not_repainted_after_its_undo_arrives_with_it(
    browser, serve
):
    """The Done press paints only from replay. If one read first reveals both the
    answer and its undo, the send continuation must not overwrite that authoritative
    authored state after replay has accounted for the action."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_OBLIGATIONS[1])
    page = open_page(browser, url)
    page.keyboard.press("m")
    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    done = page.locator("#tq-set .lf-done")
    with page.expect_request(_gesture_request):
        done.click()
    holding(page, held, 1, "the thread answer")
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    told(page)
    page.route("**/api/state*", refuse)
    expect(done).not_to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "false")
    assert [
        (event["widget"], event["action"]) for event in actions(serve.page_dir)
    ] == [("tq-set", "answer")]
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")


def test_a_refused_thread_choice_replays_recorded_and_recordless_history(
    browser, serve
):
    """Thread widgets arrive after page startup, but their comment markup is still
    their authored baseline: a definitive refusal with no history removes the
    optimistic choice from that baseline instead of leaving a decision the log never
    took. A recordless accepted action then belongs to the widget's history too.
    Reconstructing after a later refusal must replay both the recorded selection and
    the separate `answer` verb, retaining both visible facts."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_OBLIGATIONS[1])
    page = open_page(browser, url)
    page.keyboard.press("m")
    expect(page.locator(PANEL_THREAD)).to_be_visible()

    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    with page.expect_request(_gesture_request):
        page.locator("#tq-logs").click()
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator("#tq-logs")).not_to_have_attribute("chosen", "")
    assert actions(serve.page_dir) == []
    consume_browser_errors(page, http_error_console(400))
    page.unroute("**/api/event")

    page.locator("#tq-logs").click()
    round_trip(page)
    page.locator("#tq-set .lf-done").click()
    round_trip(page)
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")

    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    with page.expect_request(_gesture_request):
        page.locator("#tq-metrics").click()
    expect(page.locator("#tq-metrics")).to_have_attribute("chosen", "")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-metrics")).not_to_have_attribute("chosen", "")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    assert [
        (event["action"], event["detail"]) for event in actions(serve.page_dir)
    ] == [
        ("choose", {"value": ["tq-logs"]}),
        ("answer", {}),
    ]
    consume_browser_errors(page, http_error_console(400))


def test_refusal_restores_queued_recordless_thread_actions_in_order(browser, serve):
    """A queued recordless action paints immediately and each refusal removes only
    the local outcome belonging to that attempt."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_OBLIGATIONS[1])
    page = open_page(browser, url)
    page.keyboard.press("m")
    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    with page.expect_request(_gesture_request):
        page.locator("#tq-logs").click()
    done = page.locator("#tq-set .lf-done")
    done.click()
    expect(done).to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "true")

    first_attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            _gesture_request(request)
            and request.post_data_json.get("attempt") != first_attempt
        )
    ):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": first_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#tq-logs")).not_to_have_attribute("chosen", "")
    expect(done).to_have_attribute("aria-pressed", "true")
    second_attempt = held[1].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[1].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": second_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(done).not_to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "false")
    assert actions(serve.page_dir) == []
    consume_browser_errors(page, http_error_console(400))


def test_a_done_press_answers_optimistically_and_only_once(browser, serve):
    """Done paints its semantic result while delivery is held, and repeated presses
    still produce one action."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_OBLIGATIONS:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    page.keyboard.press("m")
    expect(page.locator(PANEL_THREAD)).to_be_visible()
    page.keyboard.press("m")
    expect(page.locator("#tq-set-decision")).to_be_focused()
    done = page.locator("#tq-set .lf-done")
    held = []
    page.route("**/api/event", lambda route: _hold_gesture(route, held))
    done.click()
    holding(page, held, 1, "the answer")

    expect(done).to_have_attribute("aria-busy", "true")
    expect(done).to_have_attribute("aria-pressed", "true")
    done.click()
    done.click()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(done).to_have_attribute("aria-pressed", "true")
    expect(done).not_to_have_attribute("aria-busy", "true")
    assert [
        (e["widget"], e["action"])
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [("tq-set", "answer")]


def test_closing_a_thread_withdraws_the_obligation_in_it(browser, serve):
    """A question in a thread is the thread's, so closing the thread takes the decision
    with it. The group is still there to read in the Resolved state, and still holds no
    answer — what went is the page's claim on the user, who would otherwise carry a
    decision in force for the life of the page and have `d` step them into a closed
    hidden thread to reach it."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(serve.page_dir, THREAD_OBLIGATIONS[0])
    page = open_page(browser, url)
    expect_obligations_answered(page, "0/1")

    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": "c-which"}
    )
    told(page)
    expect_on_me(page, 0)
    view = open_panel_thread(page, "c-which")
    expect(view.locator("#tq-one")).to_have_count(1)
    expect(page.locator("#tq-redis")).not_to_have_attribute("chosen", "")
