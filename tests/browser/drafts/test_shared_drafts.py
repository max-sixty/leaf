"""Drafts shared between tabs through the page's server: one appended event per
attempt, edit generations, settlement, a server out of reach, and a draft outliving its
tab."""

import pytest
from interact_support import append_carried_log_record, wait_for
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, SEATED_OBLIGATION_PAGE
from render_cases_navigation import JOURNEY_V1, compose
from render_harness import (
    LONG_PAGE,
    CutOff,
    _traffic,
    _until,
    draft_control,
    expect_panel_says,
    expect_preview_words,
    held_stale,
    holding,
    open_page,
    open_threads,
    page_comment,
    refuse,
    resized,
    round_trip,
    stored_draft,
    stored_draft_settled,
    stored_draft_text,
    told,
    until_draft_settled,
    write,
)

from browser.drafts import (
    cancel_draft,
    choose_comment_target,
)
from leaf import event_log as events_model
from leaf.findings import Finding

pytestmark = pytest.mark.shifts_unsurveyed


def refuse_draft_writes(page):
    """Refuse this tab's draft writes, as a server out of reach would, until the test
    unroutes them: the words stay in the tab until a write gets through."""
    page.route("**/api/draft", refuse)


def test_a_draft_another_tab_writes_waits_behind_threads_notice(
    browser, serve, one_user
):
    """While Threads stands open, a draft another tab writes joins Drafts behind the
    notice that holds new threads, so the rows the user reads stay where they are, and
    the notice's press draws it."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    choose_comment_target(first, "#p9")
    write(first.locator(".lf-fab-input"), "About the ninth paragraph.")
    first.keyboard.press("Escape")
    open_threads(first)
    rows = first.locator(".lf-fp-draft")
    expect(rows).to_have_count(1)

    choose_comment_target(second, "#p3")
    write(second.locator(".lf-fab-input"), "About the third.")
    second.keyboard.press("Escape")
    notice = first.locator(".lf-fp-joined .lf-thread-news")
    expect_preview_words(notice, "1 new draft")
    expect(rows).to_have_count(1)

    notice.click()
    expect(rows).to_have_count(2)
    expect(notice).to_have_count(0)


def test_one_shared_draft_edit_appends_one_action_across_tabs(browser, serve, one_user):
    """The widget's local busy flag is not the shared edit's ownership boundary."""
    url = serve(JOURNEY_V1)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_draft = first.locator("#draft-ops")
    second_draft = second.locator("#draft-ops")
    first_draft.locator(".lf-draft-body").dblclick()
    second_draft.locator(".lf-draft-body").dblclick()
    text = "One absolute edit from the shared draft generation."
    write(first_draft.locator("leaf-text"), text)
    expect(second_draft.locator("leaf-text")).to_have_js_property("value", text)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    draft_control(first, "save", "draft-ops").click()
    holding(first, held, 1, "the first draft edit")
    draft_control(second, "save", "draft-ops").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["action"] == "edit"
    ]
    assert [event["detail"]["value"] for event in edits] == [text]
    assert edits[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1
    expect(second_draft.locator("leaf-text")).to_have_count(0)
    assert stored_draft_settled(second, "edit:draft-ops")


def test_one_shared_added_option_has_one_action_payload_across_tabs(
    browser, serve, one_user
):
    """A draft attempt owns its actions' details as well as its visible words.

    The two views deliberately start from different projected selections. Both can
    submit the one shared add-option generation: its `add` is one event by attempt, and
    the pick behind it comes from the generation's recorded choice rather than from
    each tab's own selection, so the two tabs send one pick.
    """
    url = serve(OBLIGATION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    # Model a tab whose latest projection has not reached its neighbour yet. The draft
    # is born here, so this selection is the state the generation records.
    first.locator("#job-mounts").evaluate("el => el.setAttribute('chosen', '')")
    text = "Use a heated camera sleeve"
    write(first.locator("#jobs > .lf-another leaf-text"), text)
    expect(second.locator("#jobs > .lf-another leaf-text")).to_have_js_property(
        "value", text
    )

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add and select option", exact=True
    ).click()
    holding(first, held, 1, "the first added option")

    second.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add and select option", exact=True
    ).click()
    round_trip(second)
    held_detail = held[0].request.post_data_json["detail"]
    # The pick queues behind the held `add`, so the route comes off before the `add`
    # goes on and nothing sent after it is caught.
    first.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(first)
    # The forged selection is not the state's, so the `add` renders it away and the pick
    # that follows in the same task puts it back.
    moves = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ]
    adds = [event["detail"] for event in moves if event["action"] == "add"]
    assert adds == [held_detail]
    picks = {
        tuple(event["detail"]["value"])
        for event in moves
        if event["action"] == "choose"
    }
    assert picks == {("job-mounts", held_detail["option"])}
    # Each tab sent the generation's `add` and its pick once.
    assert _traffic(first).sends == _traffic(second).sends == 2


def test_a_general_comment_appends_one_event_across_tabs(browser, serve, one_user):
    """Both tabs may POST the shared generation; its attempt appends it once."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    raw = "One general comment, however many tabs show its draft."
    write(page_comment(first), raw)
    expect(page_comment(second)).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator(".lf-fp-send").click()
    holding(first, held, 1, "the first general send")
    second.locator(".lf-fp-send").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    assert roots[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1


def test_words_sent_while_the_server_refuses_drafts_settle_when_it_answers(
    browser, serve, one_user
):
    """Generations written and sent while no draft write gets through each send once,
    and settle when the server answers again, over the predecessor it held."""
    url = serve(LONG_PAGE)
    shared = open_page(browser, url, context=one_user)
    local = open_page(browser, url, context=one_user)
    predecessor = "The predecessor the server holds while the local tab can't write."
    first = "The first comment sent while no draft write gets through."
    second = "The second comment sent the same way."
    write(page_comment(shared), predecessor)
    expect(page_comment(local)).to_have_js_property("value", predecessor)
    refuse_draft_writes(local)

    write(page_comment(local), first)
    local.locator(".lf-fp-send").click()
    round_trip(local)
    expect(page_comment(local)).to_have_js_property("value", "")
    write(page_comment(local), second)
    expect(local.locator(".lf-fp-send")).to_have_attribute("aria-disabled", "false")
    local.locator(".lf-fp-send").click()
    _until(local, lambda traffic: traffic.sends == 2, "sent the second generation")
    round_trip(local)
    assert stored_draft_text(shared, "general") == predecessor

    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [first, second]
    assert len({event["attempt"] for event in comments}) == 2
    local.unroute("**/api/draft")
    until_draft_settled(local, "general")
    expect(page_comment(shared)).to_have_js_property("value", "")


def test_a_stale_question_first_message_cannot_append_across_tabs(
    browser, serve, one_user
):
    """A tab that missed another's send of the generation it shows sends it once more,
    and the log, which knows the attempt, appends nothing."""
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Keep one exact first answer.  "
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    # The second tab hears neither the log nor the drafts from here on.
    cut = CutOff().hold(second)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_say.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first answer")

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    until_draft_settled(first, "say:jobs")
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    second_send = second_say.get_by_role("button", name="Send", exact=True)
    expect(second_send).to_have_attribute("aria-disabled", "false")
    second_send.click()
    expect(second_say.locator("leaf-text")).to_have_js_property("value", "")
    round_trip(second)
    cut.restore()

    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["anchor"], event["text"]) for event in roots] == [
        ({"section": "jobs"}, raw)
    ]


def test_a_question_reply_appends_one_event_across_tabs(browser, serve, one_user):
    """Both inline views may POST the shared reply; its attempt appends it once."""
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
    )
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    selector = (
        f'#jobs > .lf-thread-seat > .lf-page-thread[data-lf-thread="{root["id"]}"]'
    )
    first_thread = first.locator(selector)
    second_thread = second.locator(selector)
    raw = "  The camera, then the mounting work.  "
    write(first_thread.locator("leaf-text"), raw)
    expect(second_thread.locator("leaf-text")).to_have_js_property("value", raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_thread.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first reply")
    second_thread.get_by_role("button", name="Send", exact=True).click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [(event["parent"], event["text"]) for event in replies] == [
        (root["id"], raw)
    ]
    assert _traffic(first).sends == _traffic(second).sends == 1


@pytest.mark.parametrize("newer", [None, "A newer thought must survive."])
def test_a_late_refusal_cannot_restore_an_attempt_another_tab_settled(
    browser, serve, one_user, newer
):
    """A final answer belongs to one execution; the accepted log owns the draft."""
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "The shared generation one tab will accept."
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)

    held_event = []
    held_state = []
    first.route("**/api/event", lambda route: held_event.append(route))
    first.route("**/api/state*", lambda route: held_state.append(route))
    try:
        first_say.get_by_role("button", name="Send", exact=True).click()
        holding(first, held_event, 1, "the first tab's answer")
        attempt = held_event[0].request.post_data_json["attempt"]

        second_say.get_by_role("button", name="Send", exact=True).click()
        round_trip(second)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", "")
        until_draft_settled(first, "say:jobs")
        holding(first, held_state, 1, "the accepted attempt's state read")
        if newer is not None:
            write(first_say.locator("leaf-text"), newer)

        with first.expect_response(
            lambda response: "/api/event" in response.url
        ) as refused:
            held_event.pop(0).fulfill(
                status=400,
                json={
                    "ok": False,
                    "final": True,
                    "attempt": attempt,
                    "error": "the earlier execution was refused",
                },
            )
        expect_panel_says(first, "Couldn't take this")
        expected_error = Finding(
            "console-error",
            values={
                "text": "Failed to load resource: the server responded with a status of 400 (Bad Request)",
                "url": refused.value.url,
            },
        )
        first_errors = first.lf_errors
        first_errors.remove(expected_error)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", newer or "")

        held_state.pop(0).continue_()
        first.unroute("**/api/state*")
        round_trip(first)
        expect(first_say.locator("leaf-text")).to_have_js_property("value", newer or "")
    finally:
        for route in held_event + held_state:
            refuse(route)
        first.unroute_all(behavior="wait")


def test_a_question_can_send_when_the_server_refuses_draft_writes(browser, serve):
    """A server out of reach costs the draft its copy elsewhere, not the live box's
    Send action."""
    page = open_page(browser, serve(SEATED_OBLIGATION_PAGE))
    refuse_draft_writes(page)
    say = page.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Send even though this draft cannot reach the server.  "
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the live unsaved answer")
    round_trip(page)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_a_closed_sender_cannot_append_its_accepted_attempt_twice(
    browser, serve, one_user
):
    """The log returns the accepted attempt when its first sender cannot settle it.

    Both tabs are held stale. The wrapper below closes the first tab's send path —
    the POST lands, the runtime never hears the answer — and the server settles the
    draft as it admits the send, which a tab hears through its drafts read: had the
    second tab heard it, its box would have emptied, and the send this test is about
    would have had nothing left to send. So the replacement must not learn the attempt
    is in the log before it sends, or it would correctly decline to. Both go through
    `held_stale` rather than a live `page.route`, which reaches no read already in the
    wire."""
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(browser, url, context=held_stale(one_user))
    raw = "One answer survives its sender closing."
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    write(first_say.locator("leaf-text"), raw)
    assert stored_draft_text(first, "say:jobs") == raw
    # Held from its first read, the second tab has its words from the document.
    second_held = held_stale(one_user)
    second = open_page(browser, url, context=second_held)
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    first.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          window.fetch = (input, init) => {
            const sent = actualFetch(input, init);
            if (!String(input).endsWith('/api/event')) return sent;
            return sent.then(() => {
              window.lfAcceptedAttempt = true;
              return new Promise(() => {});
            });
          };
        }"""
    )
    first_say.get_by_role("button", name="Send", exact=True).click()
    _until(first, lambda t: t.sends == 1, "sent the first answer to the server")
    first.wait_for_function("() => window.lfAcceptedAttempt === true")
    second_say.get_by_role("button", name="Send", exact=True).click()
    _until(second, lambda t: t.acked == 1, "received the accepted attempt")

    first.close()
    second_held.restore()
    told(second)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert len(roots) == 1
    assert roots[0]["text"] == raw
    assert roots[0]["attempt"]


def test_an_older_settlement_cannot_erase_a_newer_unsaved_edit(
    browser, serve, one_user
):
    """Words the server hasn't taken outrank its news that their predecessor was sent."""
    url = serve(SEATED_OBLIGATION_PAGE)
    other = open_page(browser, url, context=one_user)
    old = "The older saved answer."
    other_say = other.locator("#jobs > .lf-thread-seat > .lf-say")
    write(other_say.locator("leaf-text"), old)

    local = open_page(browser, url, context=one_user)
    refuse_draft_writes(local)
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    expect(local_say.locator("leaf-text")).to_have_js_property("value", old)
    newer = "The newer local answer the server hasn't taken."
    write(local_say.locator("leaf-text"), "A first unsaved edit on the same branch.")
    write(local_say.locator("leaf-text"), newer)
    expect(other_say.locator("leaf-text")).to_have_js_property("value", old)

    other_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(other)
    until_draft_settled(other, "say:jobs")
    told(local)
    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)

    local_say.get_by_role("button", name="Send", exact=True).click()
    _until(local, lambda t: t.sends == 1, "sent the unsaved newer answer")
    round_trip(local)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old, newer]
    assert len({event["attempt"] for event in roots}) == 2


def test_an_accepted_unsaved_branch_cannot_settle_a_newer_shared_generation(
    browser, serve, one_user
):
    """A send whose words never reached the server settles them only over the
    generation it replaced, so words another tab wrote meanwhile stand."""
    url = serve(SEATED_OBLIGATION_PAGE)
    older = open_page(browser, url, context=held_stale(one_user))
    refuse_draft_writes(older)
    newer_tab = open_page(browser, url, context=one_user)
    older_say = older.locator("#jobs > .lf-thread-seat > .lf-say")
    newer_say = newer_tab.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The older unsaved answer already in flight."
    newer = "The newer saved answer survives the older response."
    write(older_say.locator("leaf-text"), old)

    held = []
    older.route("**/api/event", lambda route: held.append(route))
    older_say.get_by_role("button", name="Send", exact=True).click()
    holding(older, held, 1, "the unsaved send")
    write(newer_say.locator("leaf-text"), newer)
    assert stored_draft_text(newer_tab, "say:jobs") == newer
    newer_tab.close()

    held[0].continue_()
    older.unroute("**/api/event")
    round_trip(older)
    # The send settles its generation over the none the server held of it as this tab
    # knew it, which the server, holding the newer words, refuses and answers with them.
    older.unroute("**/api/draft")
    restored = older.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    expect(restored).to_have_js_property("value", newer)
    assert stored_draft_text(older, "say:jobs") == newer
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]


def test_an_unsaved_branch_yields_to_another_tab_s_later_words(
    browser, serve, one_user
):
    """Words the server never took give way to a generation another tab wrote there."""
    url = serve(SEATED_OBLIGATION_PAGE)
    local = open_page(browser, url, context=one_user)
    refuse_draft_writes(local)
    shared = open_page(browser, url, context=one_user)
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    shared_say = shared.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The local write failed before the server held anything."
    newer = "The later saved generation owns the draft now."
    write(local_say.locator("leaf-text"), old)
    write(shared_say.locator("leaf-text"), newer)
    assert stored_draft_text(shared, "say:jobs") == newer
    local.unroute("**/api/draft")

    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(shared_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(local, "say:jobs") == newer


def test_a_stale_tab_sends_what_it_shows_and_the_newer_words_stay_a_draft(
    browser, serve, one_user
):
    """A tab that missed another's later words sends the words on its screen, and the
    later words stay the draft in both tabs."""
    url = serve(SEATED_OBLIGATION_PAGE)
    stale_held = held_stale(one_user)
    stale = open_page(browser, url, context=stale_held)
    current = open_page(browser, url, context=one_user)
    stale_say = stale.locator("#jobs > .lf-thread-seat > .lf-say")
    current_say = current.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The stale tab's older generation."
    newer = "The newer shared generation."
    write(stale_say.locator("leaf-text"), old)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", old)
    write(current_say.locator("leaf-text"), newer)
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", old)
    assert stored_draft_text(stale, "say:jobs") == newer

    stale_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(stale)
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    stale_held.restore()
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(current, "say:jobs") == newer
    assert [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == [old]


def test_a_stale_cancel_cannot_settle_a_newer_durable_generation(
    browser, serve, one_user
):
    """A discard settles only the generation the server holds as the tab knew it."""
    url = serve(JOURNEY_V1)
    stale = open_page(browser, url, context=held_stale(one_user))
    current = open_page(browser, url, context=one_user)
    stale_draft = stale.locator("#draft-ops")
    current_draft = current.locator("#draft-ops")
    stale_draft.locator(".lf-draft-body").dblclick()
    current_draft.locator(".lf-draft-body").dblclick()
    old = "The older edit visible in the stale tab."
    newer = "The newer edit the server now holds."
    write(stale_draft.locator("leaf-text"), old)
    expect(current_draft.locator("leaf-text")).to_have_js_property("value", old)
    write(current_draft.locator("leaf-text"), newer)
    expect(stale_draft.locator("leaf-text")).to_have_js_property("value", old)
    assert stored_draft_text(stale, "edit:draft-ops") == newer

    cancel_draft(stale)
    expect(current_draft.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(current, "edit:draft-ops") == newer
    stale_draft.locator(".lf-draft-body").dblclick()
    expect(stale_draft.locator("leaf-text")).to_have_js_property("value", newer)


def test_the_log_taking_an_older_attempt_leaves_a_newer_generation_standing(
    browser, serve, one_user
):
    """An older attempt reaching the log settles nothing written after it."""
    url = serve(SEATED_OBLIGATION_PAGE)
    stale_held = held_stale(one_user)
    stale = open_page(browser, url, context=stale_held)
    current = open_page(browser, url, context=one_user)
    stale_say = stale.locator("#jobs > .lf-thread-seat > .lf-say")
    current_say = current.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The accepted generation the stale tab still shows."
    newer = "The newer generation written before the older one was accepted."
    write(stale_say.locator("leaf-text"), old)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", old)
    old_record = stored_draft(stale, "say:jobs")
    assert old_record is not None
    old_attempt = old_record["attempt"]
    write(current_say.locator("leaf-text"), newer)
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", old)

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": old,
            "attempt": old_attempt,
        },
    )
    # Lifted with the older attempt in the log and the older generation still shown,
    # the one arrangement that asks anything: the tab hears the log and the drafts
    # together, and keeps the newer words.
    stale_held.restore()
    told(stale)
    assert stored_draft_text(current, "say:jobs") == newer
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)


def test_a_sent_draft_does_not_return_in_another_tab(browser, serve, one_user):
    """Settlement is the server's as it admits the send, so a tab opened after it
    is handed no words."""
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(browser, url, context=one_user)
    raw = "A sent draft must not return."
    say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    round_trip(first)
    until_draft_settled(first, "say:jobs")

    again = open_page(browser, url, context=one_user)
    # The composer is still open — a seat that can hold keeps it — so the claim is
    # about what it opens with: a settled draft is words the next tab must not be handed.
    expect(
        again.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    ).to_have_js_property("value", "")
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_an_intentional_later_identical_reply_gets_a_fresh_attempt(browser, serve):
    """Identity follows the edit generation, never content or a time window."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Repeat the confirmation if it remains true.",
        },
    )
    page = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root["id"]}"]')
    text = "Still true."
    for _ in range(2):
        write(thread.locator("leaf-text"), text)
        thread.get_by_role("button", name="Send", exact=True).click()
        round_trip(page)
        expect(thread.locator("leaf-text")).to_have_js_property("value", "")

    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [text, text]
    assert len({event["attempt"] for event in replies}) == 2


def test_an_unsent_draft_outlives_the_tab_it_was_typed_in(browser, serve, one_user):
    """The one gesture the tab-local store lost a draft to, and it is the ordinary one:
    every round's reply hands the URL over again, so a page's tabs accumulate and the
    one holding a half-written sentence is as likely to be shut as any other."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url, context=one_user)
    typed = "Half a thought, and then the tab went."
    write(page_comment(page), typed)
    page.close()

    again = open_page(browser, url, context=one_user)
    expect(page_comment(again)).to_have_js_property("value", typed)


def test_a_composer_on_one_passage_is_one_box_in_every_tab(browser, serve, one_user):
    """The composer is a box and a piece of chrome at once, so a second tab owes it
    more than the words. An emptied box is a box the user is still holding open and
    must stay up; a settled one has nothing left to be open about and goes down, or the
    other tab is left offering to send words the log already carries.

    The mirrored value is read for its height as well, because a box that took another
    tab's words and did not grow to them is one whose text is out of sight — the shape
    of bug a script sizing the box on `input` alone would reintroduce.

    Read in a window whose margin holds the bar beside the passage, so both tabs size
    one box in one place."""
    url = serve(LONG_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)
    for tab in (first, second):
        resized(tab, 1440, 900)

    height = "ta => Math.round(ta.getBoundingClientRect().height)"
    compose(first, "#p3")
    compact_height = first.locator(".lf-composer leaf-text").evaluate(height)
    opened = "This paragraph buries the point."
    write(first.locator(".lf-composer leaf-text"), opened)
    compose(second, "#p3")
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property(
        "value", opened
    )

    grown = opened + "\n\n" + "And the one after it says the same thing again. " * 4
    write(first.locator(".lf-composer leaf-text"), grown)
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", grown)
    assert first.locator(".lf-composer leaf-text").evaluate(height) > compact_height
    assert second.locator(".lf-composer leaf-text").evaluate(height) == first.locator(
        ".lf-composer leaf-text"
    ).evaluate(height), (
        "a box grown from another tab's keystrokes must be laid out like a typed one"
    )

    # Emptying is an edit and not a settlement: the box stays up, holding nothing.
    write(first.locator(".lf-composer leaf-text"), "")
    expect(second.locator(".lf-composer leaf-text")).to_have_js_property("value", "")
    expect(second.locator(".lf-composer")).to_be_visible()
    assert second.locator(".lf-composer leaf-text").evaluate(height) == compact_height

    sent = "The point is buried, and the paragraph after it repeats it."
    write(first.locator(".lf-composer leaf-text"), sent)
    first.keyboard.press("ControlOrMeta+Enter")
    round_trip(first)
    expect(second.locator(".lf-composer")).to_be_hidden()
    said = [
        e["text"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    assert said == [sent], "one box, and so one comment however many tabs showed it"


def test_a_draft_follows_the_user_to_another_device(browser, serve):
    """Two browsers that share nothing but the page's server show one draft, each
    taking the words the other last wrote."""
    url = serve(LONG_PAGE)
    laptop = open_page(browser, url)
    phone = open_page(browser, url)
    started = "Started on the laptop."
    write(page_comment(laptop), started)
    expect(page_comment(phone)).to_have_js_property("value", started)
    finished = started + " Finished on the phone."
    write(page_comment(phone), finished)
    expect(page_comment(laptop)).to_have_js_property("value", finished)


def test_a_tab_gives_back_the_words_a_server_lost(browser, serve):
    """A server that comes back holding less than a tab heard from it, as one restarting
    from an older copy of its page does, gets the tab's words back."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url)
    typed = "Words the server is about to lose."
    write(page_comment(page), typed)
    assert stored_draft_text(page, "general") == typed
    (serve.page_dir / "drafts.json").unlink()
    wait_for(
        lambda: stored_draft_text(page, "general"),
        lambda text: text == typed,
        failure="the tab never gave its words back to the server",
    )
    expect(page_comment(page)).to_have_js_property("value", typed)
