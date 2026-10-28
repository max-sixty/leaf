"""Drafts shared between tabs through storage: one appended event per attempt, edit
generations, settlement tombstones, storage failures, and a draft outliving its tab."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, SEATED_OBLIGATION_PAGE
from render_cases_navigation import JOURNEY_V1, compose
from render_harness import (
    LONG_PAGE,
    CutOff,
    _traffic,
    _until,
    draft_control,
    draft_key,
    expect_panel_says,
    held_stale,
    holding,
    open_page,
    page_comment,
    refuse,
    reported_browser_errors,
    resized,
    round_trip,
    stored_draft_settled,
    stored_draft_text,
    told,
    until_draft_settled,
    write,
)

from browser.drafts import (
    cancel_draft,
)
from leaf import event_log as events_model
from leaf.findings import Finding

pytestmark = pytest.mark.shifts_unsurveyed


# A storage fault stands in an init script, because it has to run ahead of the
# runtime's own storage listener and at the window listeners run in the order they
# were added, capture or not. That is before the page can say which key its draft is
# stored under, so the script compares against `window.lfDraftKey`, which
# `name_the_draft` sets once the page has loaded and nothing has been typed.
DEAF_TO_DRAFT_NEWS = """addEventListener('storage', event => {
  if (event.key === window.lfDraftKey) event.stopImmediatePropagation();
}, true);"""


def name_the_draft(page, ctx):
    """Point this page's storage fault at the draft at `ctx`, by the store's key."""
    page.evaluate("key => { window.lfDraftKey = key; }", draft_key(page, ctx))


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


def test_failed_settlement_keeps_the_base_for_a_chained_nondurable_edit(
    browser, serve, one_user
):
    """A failed tombstone does not make the next local edit descend from thin air."""
    url = serve(LONG_PAGE)
    shared = open_page(browser, url, context=one_user)
    local = open_page(browser, url, context=one_user)
    predecessor = "The durable predecessor that this local branch replaces."
    first = "The first nondurable comment on that branch."
    second = "The chained nondurable comment keeps the same base."
    write(page_comment(shared), predecessor)
    expect(page_comment(local)).to_have_js_property("value", predecessor)
    local.evaluate(
        """([draft, first, second]) => {
          const set = Storage.prototype.setItem;
          let secondFailed = false;
          window.lfBranchAttempt = null;
          Storage.prototype.setItem = function (key, value) {
            if (key === draft) {
              const record = JSON.parse(value);
              if (record.text === first) {
                window.lfBranchAttempt = record.attempt;
                throw new DOMException('full', 'QuotaExceededError');
              }
              if (record.settled && record.attempt === window.lfBranchAttempt)
                throw new DOMException('full', 'QuotaExceededError');
              if (record.text === second && !secondFailed) {
                secondFailed = true;
                throw new DOMException('full', 'QuotaExceededError');
              }
            }
            return set.call(this, key, value);
          };
        }""",
        [draft_key(local, "general"), first, second],
    )

    write(page_comment(local), first)
    local.locator(".lf-fp-send").click()
    round_trip(local)
    expect(page_comment(local)).to_have_js_property("value", "")
    write(page_comment(local), second)
    expect(local.locator(".lf-fp-send")).to_have_attribute("aria-disabled", "false")
    local.locator(".lf-fp-send").click()
    _until(local, lambda traffic: traffic.sends == 2, "sent the chained generation")
    round_trip(local)

    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [first, second]
    assert len({event["attempt"] for event in comments}) == 2
    # The tombstone is written where the send reads its own response, one step behind the
    # response itself: `round_trip` watches the browser's trip, and the page settles the
    # generation in the continuation after it — so the log holds the send before the store
    # holds its settlement. Read the store on the fact the page states, the way the tabs
    # below do; a plain read is the same assertion made a step early, and a loaded runner
    # lands in that step, which is what CI read here as an unsettled chain.
    until_draft_settled(local, "general")


def test_a_stale_question_first_message_cannot_append_across_tabs(
    browser, serve, one_user
):
    """A stale visible generation refreshes the shared tombstone before POST.

    The second tab's storage repaint is then deliberately suppressed. Its text box
    remains stale after the first send stored its tombstone, so a second real press
    proves that readable absence is settlement rather than permission to trust the
    old in-memory value.
    """
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(
        browser,
        url,
        context=one_user,
        init_script="""addEventListener('storage', event => {
          if (event.key !== window.lfDraftKey) return;
          try {
            if (JSON.parse(event.newValue)?.settled)
              event.stopImmediatePropagation();
          } catch {}
        }, true);""",
    )
    name_the_draft(second, "say:jobs")
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Keep one exact first answer.  "
    write(first_say.locator("leaf-text"), raw)
    expect(second_say.locator("leaf-text")).to_have_js_property("value", raw)
    # The init-script capture listener beats the runtime's listener for settlement,
    # leaving the old value on screen after the other tab stores its tombstone.
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
    assert stored_draft_settled(second, "say:jobs")
    second_send = second_say.get_by_role("button", name="Send", exact=True)
    expect(second_send).to_have_attribute("aria-disabled", "false")
    second_send.click()
    expect(second_say.locator("leaf-text")).to_have_js_property("value", "")
    cut.restore()

    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["anchor"], event["text"]) for event in roots] == [
        ({"section": "jobs"}, raw)
    ]
    assert _traffic(first).sends + _traffic(second).sends == 1


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
    selector = f'#jobs > .lf-thread-seat > .lf-page-thread[data-thread="{root["id"]}"]'
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


def test_a_question_can_send_when_draft_storage_refuses_writes(browser, serve):
    """Persistence failure costs recovery, not the live box's Send action."""
    page = open_page(
        browser,
        serve(SEATED_OBLIGATION_PAGE),
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    say = page.locator("#jobs > .lf-thread-seat > .lf-say")
    raw = "  Send even though this draft cannot persist.  "
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the live unpersisted answer")
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

    Both tabs are held stale, and each refusal states one half of that sentence. The
    wrapper below closes the send path — the POST lands, the runtime never hears the
    answer — and the poll is the other way the same tab settles a draft
    (settleAcceptedDrafts), so a sender left polling can still tombstone the shared
    generation out from under the replacement. It did: within a poll of the server
    taking the answer, first's own next poll read the attempt back out of the log and
    settled it, second's box emptied, and the send this test is about had nothing left
    to send — sends=0, the failure landing either on `sendDraft` refusing a settled
    record or on Playwright refusing a Send the box had already disabled, depending on
    which side of the click the storage event fell. The race was one poll interval
    against Playwright's own click, which is a gap only a loaded machine loses.

    Second's refusal is the older half and states the same fact from its own side: the
    replacement must not learn the attempt is in the log before it sends, or it would
    correctly decline to. Both go through `held_stale` rather than a live `page.route`,
    which reaches no poll already in the wire."""
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(browser, url, context=held_stale(one_user))
    second_held = held_stale(one_user)
    second = open_page(browser, url, context=second_held)
    raw = "One answer survives its sender closing."
    first_say = first.locator("#jobs > .lf-thread-seat > .lf-say")
    second_say = second.locator("#jobs > .lf-thread-seat > .lf-say")
    write(first_say.locator("leaf-text"), raw)
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


def test_an_older_settlement_cannot_erase_a_newer_failed_write(
    browser, serve, one_user
):
    """A nondurable local generation outranks storage news about its predecessor."""
    url = serve(SEATED_OBLIGATION_PAGE)
    other = open_page(browser, url, context=one_user)
    old = "The older persisted answer."
    other_say = other.locator("#jobs > .lf-thread-seat > .lf-say")
    write(other_say.locator("leaf-text"), old)

    local = open_page(
        browser,
        url,
        context=one_user,
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('full', 'QuotaExceededError');
        };""",
    )
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    expect(local_say.locator("leaf-text")).to_have_js_property("value", old)
    newer = "The newer local answer whose write failed."
    write(local_say.locator("leaf-text"), "A first nondurable edit on the same branch.")
    write(local_say.locator("leaf-text"), newer)
    expect(other_say.locator("leaf-text")).to_have_js_property("value", old)

    other_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(other)
    until_draft_settled(other, "say:jobs")
    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)

    local_say.get_by_role("button", name="Send", exact=True).click()
    _until(local, lambda t: t.sends == 1, "sent the nondurable newer answer")
    round_trip(local)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old, newer]
    assert len({event["attempt"] for event in roots}) == 2


def test_an_accepted_nondurable_branch_cannot_tombstone_a_newer_shared_generation(
    browser, serve, one_user
):
    """A held older send reconciles its base before writing settlement."""
    url = serve(SEATED_OBLIGATION_PAGE)
    older = open_page(
        browser,
        url,
        context=one_user,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === window.lfDraftKey) {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
        })();"""
        + DEAF_TO_DRAFT_NEWS,
    )
    name_the_draft(older, "say:jobs")
    newer_tab = open_page(browser, url, context=one_user)
    older_say = older.locator("#jobs > .lf-thread-seat > .lf-say")
    newer_say = newer_tab.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The older nondurable answer already in flight."
    newer = "The newer durable answer survives the older response."
    write(older_say.locator("leaf-text"), old)

    held = []
    older.route("**/api/event", lambda route: held.append(route))
    older_say.get_by_role("button", name="Send", exact=True).click()
    holding(older, held, 1, "the nondurable send")
    write(newer_say.locator("leaf-text"), newer)
    assert stored_draft_text(newer_tab, "say:jobs") == newer
    newer_tab.close()

    held[0].continue_()
    older.unroute("**/api/event")
    round_trip(older)
    restored = older.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    expect(restored).to_have_js_property("value", newer)
    assert stored_draft_text(older, "say:jobs") == newer
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]


def test_a_nondurable_branch_yields_to_unrelated_live_storage_news(
    browser, serve, one_user
):
    """Only news from a branch's base may be replaced by that local branch."""
    url = serve(SEATED_OBLIGATION_PAGE)
    local = open_page(
        browser,
        url,
        context=one_user,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === window.lfDraftKey) {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
          window.lfDraftNews = 0;
          addEventListener('storage', event => {
            if (event.key === window.lfDraftKey) window.lfDraftNews += 1;
          }, true);
        })();""",
    )
    name_the_draft(local, "say:jobs")
    shared = open_page(browser, url, context=one_user)
    local_say = local.locator("#jobs > .lf-thread-seat > .lf-say")
    shared_say = shared.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The local write failed before shared storage changed."
    newer = "The later durable generation owns the user now."
    write(local_say.locator("leaf-text"), old)
    write(shared_say.locator("leaf-text"), newer)
    local.wait_for_function("() => window.lfDraftNews > 0")

    expect(local_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(shared_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert stored_draft_text(local, "say:jobs") == newer


def test_a_delayed_storage_event_cannot_send_a_stale_durable_generation(
    browser, serve, one_user
):
    """Send refreshes shared storage instead of trusting a stale durable cache."""
    url = serve(SEATED_OBLIGATION_PAGE)
    stale = open_page(
        browser, url, context=held_stale(one_user), init_script=DEAF_TO_DRAFT_NEWS
    )
    name_the_draft(stale, "say:jobs")
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
    assert _traffic(stale).sends == 0
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)
    assert [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == []


def test_a_stale_cancel_cannot_settle_a_newer_durable_generation(
    browser, serve, one_user
):
    """Discard refreshes ownership before writing the shared tombstone."""
    url = serve(JOURNEY_V1)
    stale = open_page(
        browser, url, context=held_stale(one_user), init_script=DEAF_TO_DRAFT_NEWS
    )
    name_the_draft(stale, "edit:draft-ops")
    current = open_page(browser, url, context=one_user)
    stale_draft = stale.locator("#draft-ops")
    current_draft = current.locator("#draft-ops")
    stale_draft.locator(".lf-draft-body").dblclick()
    current_draft.locator(".lf-draft-body").dblclick()
    old = "The older edit visible in the stale tab."
    newer = "The newer edit now owned by shared storage."
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


def test_poll_settlement_cannot_tombstone_a_newer_durable_generation(
    browser, serve, one_user
):
    """Log reconciliation settles only the generation still shared by storage."""
    url = serve(SEATED_OBLIGATION_PAGE)
    # The hold costs the most here, where the poll released at the end is the subject
    # rather than an interruption: an earlier poll reconciling this tab onto the newer
    # generation leaves settlement nothing older to be tempted by, so the assertions
    # below would pass while asking nothing rather than fail.
    stale_held = held_stale(one_user)
    stale = open_page(browser, url, context=stale_held, init_script=DEAF_TO_DRAFT_NEWS)
    name_the_draft(stale, "say:jobs")
    current = open_page(browser, url, context=one_user)
    stale_say = stale.locator("#jobs > .lf-thread-seat > .lf-say")
    current_say = current.locator("#jobs > .lf-thread-seat > .lf-say")
    old = "The accepted generation cached by the stale tab."
    newer = "The newer generation shared before settlement arrived."
    write(stale_say.locator("leaf-text"), old)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", old)
    old_attempt = stale.evaluate(
        "key => JSON.parse(localStorage.getItem(key)).attempt",
        draft_key(stale, "say:jobs"),
    )
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
    # Settlement reconciles before it claims, so this poll adopts the newer generation
    # and leaves it in place. `held_stale`'s refusal is lifted here rather than earlier,
    # with the older attempt in the log and the older generation still cached, which is
    # the only arrangement that asks anything.
    accepted_words = {
        "code": "words-left-screen",
        "words": old,
        "place": stale_say.locator("leaf-text").evaluate(
            "field => window.lfPlace(field)"
        ),
    }
    stale_held.restore()
    told(stale)
    # The fixture blocked the real storage gesture, then explicitly accepted its
    # old generation. Polling must retire those old words in favour of the newer one.
    stale.evaluate("lfWordsJudged()")
    reported_browser_errors(stale, accepted_words)
    assert stored_draft_text(current, "say:jobs") == newer
    expect(stale_say.locator("leaf-text")).to_have_js_property("value", newer)
    expect(current_say.locator("leaf-text")).to_have_js_property("value", newer)


def test_a_read_failure_cannot_make_a_successfully_written_draft_unsendable(
    browser, serve
):
    """The document cache owns its generation even when getItem later refuses it."""
    page = open_page(
        browser,
        serve(SEATED_OBLIGATION_PAGE),
        init_script="""Storage.prototype.getItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    raw = "A live value remains sendable when storage reads fail."
    say = page.locator("#jobs > .lf-thread-seat > .lf-say")
    write(say.locator("leaf-text"), raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the cached draft")
    round_trip(page)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]


def test_a_remove_failure_cannot_resurrect_an_accepted_draft(browser, serve, one_user):
    """Settlement is a record and a log fact; draft cleanup never calls removeItem."""
    url = serve(SEATED_OBLIGATION_PAGE)
    first = open_page(
        browser,
        url,
        context=one_user,
        init_script="""Storage.prototype.removeItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
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
    thread = page.locator(f'#jobs .lf-page-thread[data-thread="{root["id"]}"]')
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
