"""Undo, refusal, outbox, and reconciliation tests."""

import json
import math
import re

import pytest
from leaf import event_log as events_model
from leaf import schema as schema_model
from playwright.sync_api import expect
from render_support import (
    BOARD_PAGE,
    HOLD_MOTION,
    INLINE_PAGE,
    LONG_PAGE,
    NESTED_SUGGESTION,
    SETTLED_PAGE,
    SUGGESTION_PAGE,
    UNDO_PAGE,
    CutOff,
    Traffic,
    _painted_line,
    _traffic,
    _until,
    actions,
    author_test_widget,
    composer_quote,
    leaf_page,
    live_url,
    mark_shows_beside_composer,
    nudge,
    open_page,
    panel_settled,
    pending_text,
    refuse,
    resized,
    round_trip,
    sending,
    stamp_page,
    told,
    undo,
    unfolded_button,
    wait_for_revision,
    watched,
)

pytestmark = pytest.mark.nightly


def test_z_takes_back_the_thread_the_reader_just_resolved(browser, serve):
    """The gesture with no reverse in front of the reader: a resolved thread folds
    into the disclosure at the foot of the list, so putting it back by hand means
    opening that, finding it, and pressing Reopen. What `z` writes is a withdrawal
    naming the resolve — not a second settlement, which would read as the reader
    deciding to reopen a thread they had only meant not to close."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    comments = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    comment = comments[0]
    # The reader has done nothing, so there is nothing to take back — a thread the
    # agent closed with `leaf resolve` is not theirs to reopen by pressing undo.
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "claude", "agent": "A", "parent": comments[1]},
    )
    told(page)
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")

    page.locator(f'.lf-thread[data-id="{comment}"] .lf-resolve').click()
    round_trip(page)

    undo(page)
    expect(
        page.locator(f'.lf-threads > .lf-thread[data-id="{comment}"]')
    ).to_have_count(1)
    log = events_model.read_events(serve.page_dir)
    assert log[-1] == {
        **log[-1],
        "kind": "undo",
        "author": "user",
        "undoes": next(
            e["id"] for e in log if e["kind"] == "resolve" and e["author"] == "user"
        ),
    }
    assert [e["kind"] for e in log if e["kind"] == "unresolve"] == []
    # The undo is not itself a gesture to take back, so the offer goes with it.
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    assert errors == []
    page.close()


def test_z_waits_for_an_unanswered_thread_resolution(browser, serve):
    """Resolve and reopen are undoable gestures too. While a second resolve is in
    the outbox, undo cannot name the older resolve still visible in the log."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    threads.nth(0).locator(".lf-resolve").click()
    round_trip(page)
    expect(page.locator(".lf-keyline")).to_contain_text("undo")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    sent = _traffic(page).sends
    threads.nth(0).locator(".lf-resolve").click()
    _until(page, lambda traffic: traffic.sends > sent, "held the second resolution")
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    page.keyboard.press("z")
    assert _traffic(page).sends == sent + 1

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    undo(page)
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] in {"resolve", "undo"} and event["author"] == "user"
    ] == ["resolve", "resolve", "undo"]
    assert errors == []
    page.close()


def test_z_puts_a_card_back_where_the_version_had_it(browser, serve):
    """A withdrawal leaves the log holding one gesture and one word taking it back,
    and the page derives the rest. What it derives here is the placement this
    version's markup arrived showing, read before replay first touched the page —
    column *and* index, which is why a position record names the detail field
    carrying the order. Compared, a column is the whole comparison; stated, it puts
    a card back on the right list in the wrong place.

    The card is told where it goes rather than the board being rebuilt around it,
    because that state can be stated: the reader watches it travel back, and the
    grip they were standing on is still under their hands."""
    page, errors = open_page(browser, live_url(serve(BOARD_PAGE)))
    grip = page.locator("#card-baffle .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)

    undo(page)
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    # Second of the two, as the version wrote it — not merely back on the list.
    assert page.eval_on_selector_all(
        "#col-todo > lf-card", "e => e.map(c => c.id)"
    ) == [
        "card-heater",
        "card-baffle",
    ]
    expect(grip).to_be_focused()
    log = events_model.read_events(serve.page_dir)
    (moved,) = actions(serve.page_dir)
    assert moved["detail"] == {"card": "card-baffle", "to": "col-done", "index": 0}
    assert [(e["kind"], e.get("undoes")) for e in log if e["kind"] == "undo"] == [
        ("undo", moved["id"])
    ]
    assert errors == []
    page.close()


def test_z_reaches_the_gestures_made_on_the_version_being_read(browser, serve):
    """Where a unit has no earlier action, the state a move is taken back to is what
    this version's markup arrived showing — and a version written around the
    decision shows the decision. So on v2 the authored placement of a card moved on
    v1 is where the move put it, and a press offered there would paint nothing at
    all. The conversation is not scoped this way and must not be: a thread outlives
    the version it was opened on, which is why resolve carries no version."""
    page, errors = open_page(browser, live_url(serve(BOARD_PAGE)))
    page.locator("#card-baffle .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator(".lf-keyline")).to_contain_text("undo")

    d = serve.page_dir
    carried = BOARD_PAGE.replace(
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>\n', ""
    ).replace(
        '<lf-column id="col-done" label="Done">',
        '<lf-column id="col-done" label="Done">'
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>',
    )
    stamp_page(d, carried, "carried")
    wait_for_revision(page, 2)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    page.keyboard.press("z")
    told(page)
    # An undo posts no action, so counting actions says nothing about whether the
    # press was refused — it stays at one either way, which is the assertion passing
    # in exactly the failure the test is named for. The log holding no withdrawal is
    # what says it, and the card still being where the move put it is what that means
    # on the page.
    assert [e["kind"] for e in events_model.read_events(d) if e["kind"] == "undo"] == []
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    assert errors == []
    page.close()


def test_z_waits_for_the_gesture_the_log_has_not_taken(browser, serve):
    """The walk finds the last thing the reader did by reading the log, so while the
    page holds a gesture the log has not taken it would name the gesture *before*
    that one — and take the wrong thing back, with the card they had just moved
    left where it was. A machine quick enough closes that window before the next
    press can land in it, so the send is stopped in the wire and the press made
    while it is still there."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    move = ["Enter", "ArrowRight", "Enter"]
    page.locator("#card-heater .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    round_trip(page)
    expect(page.locator(".lf-keyline")).to_contain_text("undo")

    held = []

    def hold(route):
        # The first send only: what follows has to reach the server, or the press
        # this test is about would be held too and prove nothing.
        if held:
            route.continue_()
        else:
            held.append(route)

    page.route("**/api/event", hold)
    page.locator("#card-baffle .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    _until(page, lambda t: t.sends >= 2, "sent the move it was asked for")
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    page.keyboard.press("z")
    assert _traffic(page).sends == 2, (
        "the press took back a gesture read off a log missing the one before it"
    )

    held[0].continue_()
    round_trip(page)
    undo(page)
    # The newest move, which is the one the reader would have meant — and the older
    # one still stands, where taking back the wrong gesture would have reversed it.
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    assert errors == []
    page.close()


def test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll(
    browser, serve
):
    """The event response is state through the event it accepted. Even when every
    later GET is unavailable, the page can take undo immediately and the press names
    the newest gesture rather than the stale one before it."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    move = ["Enter", "ArrowRight", "Enter"]
    page.locator("#card-heater .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    round_trip(page)
    page.wait_for_function("() => document.body.dataset.lfApplied === '1'")

    page.route("**/api/state*", refuse)
    page.locator("#card-baffle .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    round_trip(page)
    # `round_trip` proves delivery, not that the page has applied the state carried by
    # the response. With GETs cut off, coverage reaching two can only come from this
    # POST response; it also puts the outbox release and its key repaint behind us.
    page.wait_for_function("() => document.body.dataset.lfApplied === '2'")

    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    # The key line has only two contextual slots, and the focused grip's nearer commands
    # may occupy both; waiting for the word "undo" there observes a transient repaint, not
    # liveness.
    # The withdrawal entering the wire is the durable edge that proves the press worked.
    with sending(page, "the withdrawal"):
        page.keyboard.press("z")
    page.wait_for_function("() => document.body.dataset.lfApplied === '3'")
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    assert errors == []
    page.close()


def test_one_supplied_attempt_cannot_name_two_queued_actions(browser, serve):
    """Attempt identity includes the gesture it names. Reusing a token while its
    first action is still in the outbox must refuse the second locally; accounting
    the first by token alone would otherwise resolve both callers with the first
    event and silently discard the second payload before it reached the server."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    outcome = page.evaluate(
        """async () => {
          const {sendAction} = await import('/runtime/widget-api.js');
          const board = document.querySelector('#sprint');
          const attempt = 'one-attempt-two-actions';
          const first = sendAction(
            board,
            'move',
            {card: 'card-heater', to: 'col-done', index: 0},
            {attempt},
          );
          const second = sendAction(
            board,
            'move',
            {card: 'card-baffle', to: 'col-done', index: 0},
            {attempt},
          );
          return Promise.all([first, second]);
        }"""
    )
    round_trip(page)

    assert outcome[0]["detail"]["card"] == "card-heater"
    assert outcome[1] is None
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-heater"
    ]
    assert _traffic(page).sends == 1
    expect(page.locator(".lf-notice")).to_contain_text("is already in use")
    assert errors == []
    page.close()


def test_an_accepted_event_is_not_retried_when_its_state_cannot_render(
    browser, serve, request
):
    """Acceptance and rendering are separate outcomes. A malformed response state
    cannot be repaired by re-posting its accepted attempt, so delivery advances, while
    replay and undo remain held until a later complete response accounts for it."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))

    def close_page():
        if page.is_closed():
            return
        try:
            page.unroute_all(behavior="wait")
        finally:
            page.close()

    request.addfinalizer(close_page)
    older = []
    lifted = False

    def hold_older_state(route):
        if lifted:
            route.continue_()
        elif older:
            refuse(route)
        else:
            older.append(route)

    page.route("**/api/state*", hold_older_state)
    with page.expect_request("**/api/state"):
        nudge(serve.page_dir)
    page.wait_for_timeout(0)
    assert len(older) == 1
    old_route = older[0]
    old_state = old_route.fetch().json()

    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator(".lf-keyline")).to_contain_text("undo")

    requests = []
    first_attempt = []
    refused = []

    def break_first_state(route):
        event = route.request.post_data_json
        if "attempt" not in event:
            route.continue_()
            return
        requests.append(event)
        if event.get("widget") == "sug-in-card" and not refused:
            refused.append(event["attempt"])
            route.fulfill(
                status=400,
                json={
                    "ok": False,
                    "attempt": event["attempt"],
                    "error": "refused before append",
                    "final": True,
                },
            )
            return
        response = route.fetch()
        answer = response.json()
        if not first_attempt:
            first_attempt.append(event["attempt"])
        if event["attempt"] == first_attempt[0]:
            # A valid event list proves delivery, but the invalid neighbour makes
            # receiveState fail after assigning that list globally. It is deliberately
            # not a complete read, and a later stale response must not account from it.
            answer["state"]["others"] = [None]
        route.fulfill(status=response.status, json=answer)

    page.route("**/api/event", break_first_state)
    with page.expect_console_message(
        lambda message: (
            message.type == "error" and "leaf: state in event response" in message.text
        )
    ) as reported:
        page.locator("[data-lf-for='sug-thistle'] .lf-sug-accept").click()
    expect(page.locator("#sug-thistle")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#sug-thistle")).to_have_attribute("data-lf-state", "accept")

    old_route.fulfill(json=old_state)
    page.title()  # let the stale response run before reading the undo surface

    # The caller knows the send succeeded, but no whole state containing it has been
    # adopted. The stale response must not release the hold merely because the failed
    # application assigned an event list containing the attempt before it threw.
    assert first_attempt[0] not in _traffic(page).pending
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    sent = _traffic(page).sends
    page.keyboard.press("z")
    assert _traffic(page).sends == sent
    # The local Button shares the keyboard's guard; it cannot post around an
    # accepted event whose authoritative state is still incomplete.
    first_item = page.locator('[data-lf-margin-for="sug-refill"]')
    first_item.get_by_role("button", name=re.compile(r"^Undo accepting")).click()
    expect(first_item.locator(".lf-sug-receipt")).to_have_text("Undo failed · Accepted")
    assert _traffic(page).sends == sent
    first_item.get_by_role("button", name="Cancel", exact=True).click()

    # A later refusal is another asynchronous reconciliation wake-up. It may not use
    # the accepted-but-incomplete event tail or release either hold merely because its
    # delivery completed.
    page.locator("[data-lf-for='sug-in-card'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-in-card")).not_to_have_attribute(
        "data-lf-state", "accept"
    )
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")

    # A complete poll accounts for the older acceptance and the refused correction.
    # The re-offered action can then send under a fresh attempt, whose valid answer
    # includes both accepted gestures and makes the newest one safe to undo.
    lifted = True
    told(page)
    expect(page.locator(".lf-keyline")).to_contain_text("undo")
    page.locator("[data-lf-for='sug-in-card']").get_by_role(
        "button", name="Retry", exact=True
    ).click()
    round_trip(page)

    assert [request["attempt"] for request in requests].count(first_attempt[0]) == 1
    assert len(refused) == 1
    assert [
        (event["widget"], event["action"]) for event in actions(serve.page_dir)
    ] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ]

    undo(page)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    expect(page.locator("#sug-thistle")).to_have_attribute("data-lf-state", "accept")
    expect(page.locator("#sug-in-card")).not_to_have_attribute(
        "data-lf-state", "accept"
    )
    expect(page.locator("#sug-in-card lf-old")).to_be_visible()
    assert "leaf: state in event response" in reported.value.text
    assert reported.value.text in errors
    # This test transforms event responses with route.fetch(). A news-triggered POST
    # can enter that handler after the last assertion; closing its context then disposes
    # the APIResponse while the handler is still reading it, and Playwright reports that
    # callback's `Response has been disposed` from the next test's browser call. Remove
    # the routes and wait for any handler already running before their owning page goes.
    page.unroute_all(behavior="wait")
    assert all(error == reported.value.text or "400" in error for error in errors)
    page.close()


def test_a_failed_background_read_cannot_aim_undo_at_its_partial_history(
    browser, serve
):
    """A timer response installs candidate events only while rendering that state.
    If a required neighbour makes the read fail, a focus repaint and z still read the
    last fully adopted history—not the newer gesture whose DOM was never projected."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    heater = page.locator("#card-heater .lf-grip")
    heater.focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)
    first = actions(serve.page_dir)[0]

    malformed_reads = []

    def malformed_state(route):
        if malformed_reads:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        state["others"] = [None]
        malformed_reads.append(True)
        route.fulfill(status=response.status, json=state)

    # The route before the append: the page is told of an append as it lands and
    # asks at once, so a route registered after it is a route the read has passed.
    page.route("**/api/state*", malformed_state)
    with (
        page.expect_console_message(lambda message: "read failed" in message.text),
        page.expect_request("**/api/state*"),
    ):
        second = events_model.append_event(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "sprint",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-done", "index": 0},
            },
        )

    expect(page.locator(".lf-keyline")).to_contain_text("undo")
    with page.expect_response(
        lambda response: (
            "/api/event" in response.url
            and (response.request.post_data_json or {}).get("kind") == "undo"
        )
    ):
        page.keyboard.press("z")
    logged_undo = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "undo"
    )
    assert logged_undo["undoes"] == first["id"]
    assert logged_undo["undoes"] != second["id"]
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    assert any("read failed" in error for error in errors)
    page.close()


def test_a_newer_queued_action_survives_an_older_refusal(browser, serve):
    """A later absolute action on the same widget is already painted while an older
    send waits. Refusing the older action must preserve that outbox overlay, including
    while an accepted intermediate answer is older than the newest local gesture. The
    queued state is not a result, so it mints no page-map record before acceptance."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    page.locator("#card-heater .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)

    page.route("**/api/state*", refuse)
    held = []

    page.route("**/api/event", lambda route: held.append(route))
    baffle = page.locator("#card-baffle .lf-grip")
    with page.expect_request("**/api/event"):
        baffle.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    page.wait_for_timeout(0)
    expect(
        page.locator('[data-lf-margin-for="card-baffle"] [data-lf-behavior="status"]')
    ).to_have_count(0)
    assert len(held) == 1
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)

    # Reorder the same card twice while its move waits. Each action is queued locally
    # and describes its placement whole; the newest says Done, before the heater.
    baffle.focus()
    for key in ["Enter", "ArrowDown", "Enter"]:
        page.keyboard.press(key)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-heater", "card-baffle"]
    assert _traffic(page).sends == 2
    baffle.focus()
    for key in ["Enter", "ArrowUp", "Enter"]:
        page.keyboard.press(key)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    assert (
        _traffic(page).sends == 2
    )  # the later two actions are queued, not on the wire

    first_attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != first_attempt
        )
    ) as second_request:
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": first_attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    page.wait_for_timeout(0)
    assert len(held) == 2
    second_attempt = second_request.value.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt")
            not in {first_attempt, second_attempt}
        )
    ):
        held[1].continue_()
    page.wait_for_timeout(0)
    assert len(held) == 3

    # The accepted second response states "after heater", but the third gesture is
    # still unresolved and already painted "before heater". The older refusal and
    # intermediate answer may disturb neither half of that local placement.
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]

    held[2].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    assert [
        (event["detail"]["card"], event["detail"]["to"], event["detail"]["index"])
        for event in actions(serve.page_dir)
    ] == [
        ("card-heater", "col-done", 0),
        ("card-baffle", "col-done", 1),
        ("card-baffle", "col-done", 0),
    ]
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]

    undo(page)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-heater", "card-baffle"]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_refused_recorded_actions_restore_from_the_log_and_surviving_outbox(
    browser, serve
):
    """Rollback snapshots compose the wrong state: B captures optimistic A, so if
    both are refused, B's snapshot resurrects A. The runtime instead removes each
    action from one overlay and derives the widget from the log plus what survives."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    page.locator("#card-heater .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)

    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    baffle = page.locator("#card-baffle .lf-grip")
    with page.expect_request("**/api/event"):
        baffle.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    baffle.focus()
    for key in ["Enter", "ArrowDown", "Enter"]:
        page.keyboard.press(key)
    baffle.focus()
    for key in ["Enter", "ArrowUp", "Enter"]:
        page.keyboard.press(key)
    assert (
        _traffic(page).sends == 2
    )  # the later two actions are queued, not on the wire

    for at in range(3):
        attempt = held[at].request.post_data_json["attempt"]
        if at < 2:
            with page.expect_request(
                lambda request, attempt=attempt: (
                    "/api/event" in request.url
                    and request.post_data_json.get("attempt") != attempt
                )
            ):
                held[at].fulfill(
                    status=400,
                    json={
                        "ok": False,
                        "attempt": attempt,
                        "error": "refused before append",
                        "final": True,
                    },
                )
            page.wait_for_timeout(0)
        else:
            with page.expect_response(lambda response: "/api/event" in response.url):
                held[at].fulfill(
                    status=400,
                    json={
                        "ok": False,
                        "attempt": attempt,
                        "error": "refused before append",
                        "final": True,
                    },
                )
        if at < 2:
            assert len(held) == at + 2
            assert page.eval_on_selector_all(
                "#col-done > lf-card", "cards => cards.map(card => card.id)"
            ) == ["card-baffle", "card-heater"]

    round_trip(page)
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-heater"
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_refused_position_reconciles_the_logged_order_of_sibling_units(
    browser, serve
):
    """A position unit shares an ordered container with its siblings. Restoring only
    the refused card's authored index can overwrite a different card's logged reorder;
    reconciliation must fold the board whole in action order."""
    page, errors = open_page(browser, serve(BOARD_PAGE), init_script=HOLD_MOTION)
    baffle = page.locator("#card-baffle .lf-grip")
    baffle.focus()
    for key in ["Enter", "ArrowUp", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)
    assert page.eval_on_selector_all(
        "#col-todo > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    page.evaluate(
        "() => { for (const a of window.__lfHeld) a.cancel(); window.__lfHeld = []; }"
    )

    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("#card-heater .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    page.wait_for_timeout(0)
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
    round_trip(page)

    assert page.eval_on_selector_all(
        "#col-todo > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-baffle"
    ]
    motions = page.evaluate(
        """() => window.__lfHeld.map(animation => ({
          target: animation.effect.target.id,
          state: animation.playState,
        }))"""
    )
    assert motions and motions[0] == {
        "target": "card-heater",
        "state": "idle",
    }, "the optimistic move was not the cancelled animation positive control"
    active = [motion["target"] for motion in motions if motion["state"] != "idle"]
    assert len(motions) <= 3 and len(active) == len(set(active)), (
        "reconstruction exposed synthetic authored/log placements as gestures: "
        f"{motions}"
    )
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_refused_position_rebuilds_the_whole_authored_sibling_order(browser, serve):
    """Authored indices are one container composition, not per-card snapshots. A
    refused move must reset every sibling before replaying a surviving reorder; putting
    back only the refused card makes both indices relative to a synthetic order."""
    three_cards = BOARD_PAGE.replace(
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>',
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>\n'
        '    <lf-card id="card-third"><strong>Third card</strong></lf-card>',
    )
    url = serve(three_cards)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sprint",
            "action": "move",
            "detail": {"card": "card-heater", "to": "col-todo", "index": 2},
        },
    )
    page, errors = open_page(browser, url)
    cards = "cards => cards.map(card => card.id)"
    assert page.eval_on_selector_all("#col-todo > lf-card", cards) == [
        "card-baffle",
        "card-third",
        "card-heater",
    ]

    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.evaluate(
            """() => { void import('/runtime/widget-api.js').then(({sendAction}) => {
              const widget = document.querySelector('#sprint');
              const detail = {card: 'card-baffle', to: 'col-todo', index: 2};
              widget.applyAction('move', detail);
              void sendAction(widget, 'move', detail);
            }); }"""
        )
    expect(page.locator("#col-todo > lf-card")).to_have_count(3)
    assert page.eval_on_selector_all("#col-todo > lf-card", cards) == [
        "card-third",
        "card-heater",
        "card-baffle",
    ]

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
    round_trip(page)
    assert page.eval_on_selector_all("#col-todo > lf-card", cards) == [
        "card-baffle",
        "card-third",
        "card-heater",
    ]
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-heater"
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_an_outer_refusal_preserves_a_different_nested_widgets_state(
    browser, serve, tmp_path, monkeypatch
):
    """A recorded container owns only its nearest stateful parts. Projecting a
    project's outer board must not capture cards owned by a nested shipped board merely
    because both record positions within lf-column."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-outer-board", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    outer = entries["lf-outer-board"]
    outer["properties"]["restated"] = {"type": "boolean"}
    outer["x-content"] = "items"
    outer["x-example"] = (
        '<lf-outer-board id="x-outer"><lf-column id="x-col" label="Todo">'
        '<lf-card id="x-card"><strong>Card</strong></lf-card></lf-column>'
        "</lf-outer-board>"
    )
    outer["x-state"] = {
        "move": {
            "detail": {
                "type": "object",
                "properties": {
                    "card": {"type": "string"},
                    "to": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0},
                },
                "required": ["card", "to", "index"],
                "additionalProperties": False,
            },
            "facet": "placement",
            "unit": "card",
            "record": {
                "kind": "position",
                "within": "lf-column",
                "value": "to",
                "order": "index",
            },
        }
    }
    standard = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())
    entries["lf-column"] = standard["lf-column"]
    entries["lf-column"]["x-parent"].append("lf-outer-board")
    registry_path.write_text(json.dumps(entries))
    (tmp_path / ".leaf" / "widgets" / "lf-outer-board.js").write_text(
        """import { once } from "/runtime/widget-api.js";
customElements.define("lf-outer-board", class extends HTMLElement {
  connectedCallback() { once(this); }
  applyAction(action, detail) {
    if (action !== "move") return;
    const card = document.getElementById(detail.card);
    const col = document.getElementById(detail.to);
    if (!card?.matches("lf-card") || !col?.matches("lf-column") || !this.contains(col)) return;
    const cards = [...col.children].filter(node => node.matches("lf-card") && node !== card);
    col.insertBefore(card, cards[detail.index] ?? null);
  }
});
"""
    )
    nested = leaf_page(
        "nested owners",
        """
<h1 id="h">Nested owners</h1>
<lf-outer-board id="outer">
  <lf-column id="outer-todo" label="Todo"><lf-card id="outer-card"><strong>Outer</strong>
    <lf-board id="inner"><lf-column id="inner-todo" label="Todo">
      <lf-card id="inner-card"><strong>Inner</strong></lf-card></lf-column>
      <lf-column id="inner-done" label="Done"></lf-column></lf-board>
  </lf-card></lf-column><lf-column id="outer-done" label="Done"></lf-column>
</lf-outer-board>""",
    )
    page, errors = open_page(browser, serve(nested))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))

    with page.expect_request("**/api/event"):
        page.evaluate(
            """() => { void import('/runtime/widget-api.js').then(({sendAction}) => {
              const widget = document.querySelector('#outer');
              const detail = {card: 'outer-card', to: 'outer-done', index: 0};
              widget.applyAction('move', detail);
              void sendAction(widget, 'move', detail);
            }); }"""
        )
    page.wait_for_timeout(0)
    page.evaluate(
        """() => { void import('/runtime/widget-api.js').then(({sendAction}) => {
          const widget = document.querySelector('#inner');
          const detail = {card: 'inner-card', to: 'inner-done', index: 0};
          widget.applyAction('move', detail);
          void sendAction(widget, 'move', detail);
        }); }"""
    )
    expect(page.locator("#inner-done #inner-card")).to_have_count(1)

    outer_attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != outer_attempt
        )
    ):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": outer_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#outer-todo > #outer-card")).to_have_count(1)
    expect(page.locator("#inner-done #inner-card")).to_have_count(1)
    held[1].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#inner-done #inner-card")).to_have_count(1)
    assert [
        (event["widget"], event["detail"]["card"]) for event in actions(serve.page_dir)
    ] == [("inner", "inner-card")]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_refusal_does_not_overlay_an_accepted_attempt_already_in_the_log(
    browser, serve
):
    """Acceptance may be known while a malformed state keeps the outbox hold. If
    later log events arrive before another refusal, the retained accepted attempt is
    replayed at its log sequence—not overlaid again as though it were newest."""
    page, errors = open_page(browser, serve(BOARD_PAGE))

    def malformed_read_state(route):
        if lifted:
            route.continue_()
            return
        if malformed_reads:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        state["others"] = [None]
        malformed_reads.append(True)
        route.fulfill(status=response.status, json=state)

    def malformed_event_state(route):
        response = route.fetch()
        answer = response.json()
        answer["state"]["others"] = [None]
        route.fulfill(status=response.status, json=answer)

    malformed_reads = []
    lifted = False
    page.route("**/api/state*", malformed_read_state)
    page.route("**/api/event", malformed_event_state)
    heater = page.locator("#card-heater .lf-grip")
    with (
        page.expect_console_message(
            lambda message: "leaf: state in event response" in message.text
        ),
        # The move's own append is what the page hears next, so the malformed read
        # it prompts fails here rather than on a later timer.
        page.expect_console_message(lambda message: "read failed" in message.text),
    ):
        heater.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    page.unroute("**/api/event")

    with page.expect_request("**/api/state*"):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "sprint",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-done", "index": 0},
            },
        )

    refused = []

    def refuse_move(route):
        body = route.request.post_data_json or {}
        if body.get("kind") != "action":
            route.continue_()
            return
        attempt = body["attempt"]
        refused.append(attempt)
        route.fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    page.route("**/api/event", refuse_move)
    with page.expect_response(
        lambda response: (
            "/api/event" in response.url
            and (response.request.post_data_json or {}).get("kind") == "action"
        )
    ):
        heater.focus()
        for key in ["Enter", "ArrowLeft", "Enter"]:
            page.keyboard.press(key)
    assert len(refused) == 1
    # Neither malformed read is a state the projector may consume. The accepted
    # baffle move remains held until a complete read can place it in chronology.
    expect(page.locator("#col-done #card-baffle")).to_have_count(0)
    lifted = True
    with page.expect_response(
        lambda response: "/api/state" in response.url and response.ok
    ):
        nudge(serve.page_dir)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)

    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-heater",
        "card-baffle",
    ]
    assert errors
    page.close()


def test_accounting_an_action_projects_newer_same_widget_news_before_release(
    browser, serve
):
    """A complete poll can account for held A while also carrying newer B. Replay
    skips the widget under A's outbox hold; releasing A must project A+B before that
    hold disappears, or the page offers its next gesture against stale optimistic A."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    heater = page.locator("#card-heater .lf-grip")
    with page.expect_request("**/api/event"):
        heater.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    page.wait_for_timeout(0)
    assert len(held) == 1
    # Reads held until B is appended, so one complete state carries A and B: the
    # stream would otherwise have the page read A alone in the time B takes.
    cut = CutOff().hold(page)
    older_answer = held[0].fetch()  # the server appends A; its response stays held
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sprint",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-done", "index": 0},
        },
    )
    cut.restore()
    told(page)  # a complete state accounts A and projects A+B before release
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    expect(page.locator(".lf-keyline")).to_contain_text("undo")
    cut.cut()

    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(response=older_answer)
    page.title()  # let the stale response settle before reading the page again

    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    expect(page.locator(".lf-keyline")).to_contain_text("undo")
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-heater",
        "card-baffle",
    ]
    assert errors == []
    page.close()


def test_accounting_an_action_also_applies_the_undo_that_arrived_with_it(
    browser, serve
):
    """A complete read may first reveal both optimistic A and another tab's undo of A.
    The outbox entry is no longer a hold against that same read: the withdrawal must
    restore authored state before accounting releases A, or the sender keeps showing a
    gesture the log and every fresh page have already taken back."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    heater = page.locator("#card-heater .lf-grip")
    with page.expect_request("**/api/event"):
        heater.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    page.wait_for_timeout(0)
    assert len(held) == 1
    # Reads held until the undo is appended, so the first complete read reveals both.
    cut = CutOff().hold(page)
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    events_model.append_event(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    cut.restore()
    told(page)
    cut.cut()
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(0)
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    assert errors == []
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")
    page.close()


def test_a_first_complete_read_restores_its_own_already_undone_action(browser, serve):
    """Offline presentation has not replayed the log, but a recorded local action is
    still optimistic DOM. If the first successful read contains both that action and an
    undo from another tab, the startup guard must not mistake the painted action for one
    this page never saw."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.lf_traffic = Traffic(page)
    errors = watched(page)
    cut = CutOff().hold(page)
    page.goto(serve(BOARD_PAGE), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    heater = page.locator("#card-heater .lf-grip")
    with page.expect_request("**/api/event"):
        heater.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    page.wait_for_timeout(0)
    assert len(held) == 1
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    events_model.append_event(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    cut.restore()
    told(page)
    cut.cut()
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(0)
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    assert errors == []
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")
    page.close()


def test_a_first_complete_read_does_not_repaint_an_already_undone_settlement(
    browser, serve
):
    """A record-less decision waits for the log instead of painting optimistically.
    If the first complete read contains both that decision and its undo, replay leaves
    authored markup standing. The send continuation must not paint the withdrawn
    decision after that authoritative read has released it."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.lf_traffic = Traffic(page)
    errors = watched(page)
    cut = CutOff().hold(page)
    page.goto(serve(SUGGESTION_PAGE), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    page.wait_for_timeout(0)
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    events_model.append_event(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    cut.restore()
    told(page)
    cut.cut()
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#sug-refill")).not_to_have_attribute("data-lf-state", "accept")
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    expect(page.locator(".lf-keyline")).not_to_contain_text("undo")
    assert errors == []
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")
    page.close()


def test_an_older_settlement_cannot_repaint_over_a_newer_decision(browser, serve):
    """A later record-less action on the same declared unit supersedes the first.
    When one complete read accounts the held accept and also replays another tab's
    reject, the older send continuation must not paint accept over that chronology."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    page.wait_for_timeout(0)
    # Append the accept while its browser response remains held, with the page's
    # reads held too, so one complete read accounts the accept and replays the reject.
    cut = CutOff().hold(page)
    accepted_answer = held[0].fetch()
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "reject",
            "detail": {},
        },
    )

    cut.restore()
    told(page)
    cut.cut()
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    expect(page.locator("#sug-refill lf-new")).to_be_hidden()
    assert [
        (event["widget"], event["action"]) for event in actions(serve.page_dir)
    ] == [
        ("sug-refill", "accept"),
        ("sug-refill", "reject"),
    ]
    assert errors == []
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")
    page.close()


def test_poll_proven_acceptance_advances_past_a_hung_post_response(browser, serve):
    """A complete read containing an attempt is authoritative delivery evidence. Once
    it accounts for A, the ordered outbox may send queued B even if A's original browser
    response never finishes; the server append A was already observed before B starts."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("#card-baffle .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    page.wait_for_timeout(0)
    assert len(held) == 1
    first_attempt = held[0].request.post_data_json["attempt"]

    # B, queued behind A: the outbox is ordered, and A has not been answered.
    page.locator("#card-heater .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != first_attempt
        )
    ):
        # Append A on the server and leave its browser response unresolved. The
        # stream tells the page the log moved, the read that prompts accounts for A,
        # and B goes out — within the stream's look, so the listener has to be armed
        # before the append rather than after it.
        first_answer = held[0].fetch()
    page.wait_for_timeout(0)

    assert len(held) == 2
    held[0].fulfill(response=first_answer)  # cleanup after B has proved release
    with page.expect_response(
        lambda response: (
            "/api/event" in response.url
            and response.request.post_data_json.get("attempt") != first_attempt
        )
    ):
        held[1].continue_()
    page.unroute("**/api/event")

    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-baffle",
        "card-heater",
    ]
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_refused_action_waits_for_a_live_gesture_before_reconciling(browser, serve):
    """A board grab owns its captured origin until release. A refusal arriving under
    that grab must remain in the outbox, then reconcile after Escape, or the cancel can
    resurrect the move the server refused."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    baffle = page.locator("#card-baffle .lf-grip")
    with page.expect_request("**/api/event"):
        baffle.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    page.wait_for_timeout(0)

    baffle.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#sprint")).to_have_class(re.compile(r"\blf-dragging\b"))
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
    round_trip(page)

    # The live gesture still owns the DOM; its origin must not move under it.
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator('[data-lf-behavior="status"]')).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    assert actions(serve.page_dir) == []
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_lost_accepted_response_keeps_later_gestures_in_order(browser, serve):
    """The outbox retries an accepted gesture whose response was lost before it
    sends the next gesture. Both arrive once, in the order the reader made them."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    requests = []
    accepted = []

    def lose_first_answer(route):
        requests.append(route.request.post_data_json)
        if len(requests) == 1:
            accepted.append(route.fetch().status)
            refuse(route)
        else:
            route.continue_()

    page.route("**/api/state*", refuse)
    page.route("**/api/event", lose_first_answer)
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/event" in request.url
    ):
        page.locator("#card-baffle .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)

    first_attempt = requests[0]["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != first_attempt
        )
    ):
        page.locator("#card-heater .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    round_trip(page)

    assert accepted == [200]
    assert [request["detail"]["card"] for request in requests] == [
        "card-baffle",
        "card-baffle",
        "card-heater",
    ]
    assert requests[0]["attempt"] == requests[1]["attempt"]
    assert requests[2]["attempt"] != first_attempt
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "card-baffle",
        "card-heater",
    ]
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)

    undo(page)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_refused_draft_keeps_newer_authoritative_words_under_its_editor(
    browser, serve
):
    """The centralized projector runs before a refused send resolves. A draft caller
    may reopen the unsent text, but must not restore its stale pre-send body over a newer
    remote edit the projector just applied and marked complete."""
    page, errors = open_page(browser, serve(UNDO_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft = page.locator("#note-cli")
    with page.expect_request("**/api/event"):
        page.locator(
            ".lf-draft-controls[data-lf-for='note-cli'] .lf-draft-pencil"
        ).click()
        draft.locator("textarea").fill("Local C")
        page.keyboard.press("Meta+Enter")
    page.wait_for_timeout(0)
    expect(draft.locator(".lf-draft-body")).to_have_text("Local C")

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "note-cli",
            "action": "edit",
            "detail": {"text": "Remote B"},
        },
    )
    told(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Local C")
    page.route("**/api/state*", refuse)

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
    round_trip(page)

    expect(draft.locator("textarea")).to_have_value("Local C")
    expect(draft.locator(".lf-draft-body")).to_have_text("Remote B")
    page.keyboard.press("Escape")
    expect(draft.locator("textarea")).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text("Remote B")
    assert [event["detail"]["text"] for event in actions(serve.page_dir)] == [
        "Remote B"
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_z_walks_back_through_gestures_rather_than_toggling_one(browser, serve):
    """The walk steps past what it has already taken and reaches the gesture before
    it — the edit here, whose authored text comes back with its paragraphs, where
    the facet a comparison reads is collapsed. That is what withdrawing buys over
    stating a counter-gesture: a second press would otherwise land on a statement
    the first press had just made and put the reader back where they started."""
    page, errors = open_page(browser, serve(UNDO_PAGE))
    body = page.locator("lf-draft .lf-draft-body")
    authored = body.inner_text()
    assert "\n\n" in authored

    page.locator(".lf-draft-controls .lf-draft-pencil").click()
    page.locator("lf-draft textarea").fill("Rewritten.")
    page.keyboard.press("Meta+Enter")
    round_trip(page)
    expect(body).to_have_text("Rewritten.")
    page.locator("#opt-a").click()
    round_trip(page)
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-a")

    undo(page)
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-b")
    undo(page)
    # The arrival first, read the way every assertion after a trip reads it, and then
    # the reading a retry cannot make: `to_have_text` collapses the blank line, which
    # is the very thing the authored text is here to bring back.
    expect(body).to_have_text(authored)
    assert body.inner_text() == authored
    # Two gestures and two words taking them back, newest first: nothing in the log
    # claims the reader chose opt-b or typed the authored draft, because they did
    # neither — the page derived both from what still stands.
    log = events_model.read_events(serve.page_dir)
    edit, choose = actions(serve.page_dir)
    assert [(e["action"], e["detail"]) for e in (edit, choose)] == [
        ("edit", {"text": "Rewritten."}),
        ("choose", {"options": ["opt-a"]}),
    ]
    assert [e["undoes"] for e in log if e["kind"] == "undo"] == [
        choose["id"],
        edit["id"],
    ]
    assert errors == []
    page.close()


def test_z_takes_back_a_decision_no_state_can_state(browser, serve):
    """A suggestion's accept records nothing and retires the losing half of the
    page on its way through, so there is no value to state it back to: undecided
    is not a value any verb carries. Withdrawing needs none — the fold drops the
    accept, and the widget goes back to the markup this version wrote, with what
    survives replayed onto it. That is the whole of the rebuild's reason, and why
    it is chosen by a declaration (no record) rather than by the tag's name.

    The controls come back with it, which is the half a subtree swap could lose:
    the row hangs in the page margin as the column's child, outside the subtree
    that was replaced, and it is the widget's own to take away and hang again."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    old = page.locator("#sug-refill lf-old")
    accept = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    expect(old).to_be_visible()
    expect(page.locator(".lf-decisions")).to_have_text("Asks 0/3")

    accept.click()
    round_trip(page)
    expect(old).to_be_hidden()
    expect(page.locator(".lf-decisions")).to_have_text("Asks 1/3")

    undo(page)
    # Pending again, in every reading of it: the retired half is back on the page,
    # the control offers the decision rather than recording it, and the banner
    # counts the question among the ones still waiting on the reader.
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    expect(page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")).to_have_attribute(
        "aria-label", re.compile(r"^Accept the suggested change")
    )
    expect(page.locator(".lf-decisions")).to_have_text("Asks 0/3")
    assert page.locator("[data-lf-for='sug-refill']").count() == 1, (
        "the rebuilt change hung a second row beside the one it replaced"
    )
    (accepted,) = actions(serve.page_dir)
    assert accepted["action"] == "accept"
    assert [
        e["undoes"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "undo"
    ] == [accepted["id"]]
    assert errors == []
    page.close()


def test_a_rebuild_hands_back_the_place_and_the_marks(browser, serve):
    """Two things the rebuild owes beyond the state, and both were missing because a
    rebuild is the one restore that replaces nodes rather than moving them.

    The marks are painted ranges over text nodes, so the ones on a retired sentence
    were pointing into a subtree the document no longer had: the sentence came back
    and the comment on it did not, which reads as a thread detached from a passage
    that is plainly there. Replay repaints them when it has moved the page's text,
    and a restore is replay moving it.

    The place is the reader's own. They pressed the key standing on the control
    that decided the change, and that control went with the subtree — so the press
    put them on <body> with nothing saying so, which is the silence the ladder's
    rung exists to avoid. A widget told its state keeps its focus by itself, so only
    this route ever lost it."""
    url = serve(SUGGESTION_PAGE)
    page, errors = open_page(browser, url)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "this one matters",
            "anchor": {"quote": "Refill every feeder each morning."},
        },
    )
    # Parenthesised, because `??` binds looser than a comparison: written
    # `size ?? 0 === 0` the predicate is `size ?? true`, which is 0 — falsy — exactly
    # when the assertion is meant to hold, and the wait runs its timeout out on a
    # page that is doing the right thing.
    marks = "() => (CSS.highlights.get('lf-mark')?.size ?? 0)"
    page.wait_for_function(f"{marks} > 0")

    accept = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    accept.click()
    round_trip(page)
    # The sentence left the page with the decision, so the mark goes with it.
    page.wait_for_function(f"{marks} === 0")
    expect(
        page.locator("[data-lf-for='sug-refill']").get_by_role(
            "button", name=re.compile(r"^Undo accepting")
        )
    ).to_be_focused()

    undo(page)
    page.wait_for_function(f"{marks} === 1")
    expect(page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")).to_be_focused()
    assert errors == []
    page.close()


def test_a_rebuild_leaves_a_reader_standing_elsewhere_where_they_are(browser, serve):
    """The place is handed back only to the reader who was standing in what was
    replaced. Pressing the key from the page is not a request to be taken to the
    change it takes back, and a focus move nobody asked for is the page moving
    under the reader in the one way no geometry reports."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    page.evaluate("() => document.body.focus()")

    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")
    assert errors == []
    page.close()


def test_a_withdrawal_waits_for_a_widget_that_cannot_take_it_yet(browser, serve):
    """The withdrawal pass has to keep the discipline the replay loop keeps, because
    it is replay: a widget the page has painted ahead of the log gets the next poll
    rather than being written over. `lf-draft` says so outright — its applyAction
    returns false while an editor stands, so the reader's unsent words are not yanked
    out from under them — and a pass that drops that answer and marks the withdrawal
    answered leaves the tab holding the withdrawn text for the rest of its life, with
    the reader-origin mark cleared because the fold agrees the edit is gone. A reload would
    show the authored words; this tab never would again."""
    url = serve(UNDO_PAGE)
    one, errors_one = open_page(browser, url)
    two, errors_two = open_page(browser, url)
    body = "lf-draft .lf-draft-body"
    authored = one.locator(body).inner_text()

    one.locator(".lf-draft-controls .lf-draft-pencil").click()
    one.locator("lf-draft textarea").fill("Rewritten.")
    one.keyboard.press("Meta+Enter")
    round_trip(one)
    expect(two.locator(body)).to_have_text("Rewritten.")

    # The second tab is now holding words of its own, so the log may not write over it.
    two.locator(".lf-draft-controls .lf-draft-pencil").click()
    expect(two.locator("lf-draft textarea")).to_be_focused()
    undo(one)
    expect(one.locator(body)).to_have_text(authored)
    expect(one.locator("lf-draft .lf-draft-history > summary")).to_have_text(
        "Changes · 1 edit"
    )

    # The withdrawal has to reach the second tab *while* its editor stands — heard
    # after the box closes, it applies on the way past and says nothing about the
    # hold. told() consumes the poll that carries it.
    told(two)
    expect(two.locator(body)).to_have_text("Rewritten.")

    # Let go, and the withdrawal it could not take yet lands on the next poll.
    two.keyboard.press("Escape")
    expect(two.locator("lf-draft textarea")).to_have_count(0)
    expect(two.locator(body)).to_have_text(authored)
    expect(two.locator("lf-draft .lf-draft-history > summary")).to_have_text(
        "Changes · 1 edit"
    )
    assert errors_one == [] and errors_two == []
    one.close()
    two.close()


def test_a_withdrawal_restores_what_still_stands_not_what_stood_then(browser, serve):
    """An undo names a gesture, and what the page owes afterwards is the unit's state
    *now* — the fold minus that gesture — not the state that stood before it at the
    time. The two differ whenever the withdrawn action is no longer the unit's last
    word, which two tabs reach without trying: one presses `z` on the move it knows
    about while the other has already moved the same card past it, and the door takes
    it, recency not being a thing an event can be checked for.

    The tab that hears it then paints the older reading over the standing move. Which
    tab shows the damage is the part worth arranging: the tab that *made* the later
    move painted it itself, so replay never marked it applied and the next poll lays
    it down again, healing the page by luck. A tab that got that move through replay
    has it marked applied and will never lay it down again — so it holds the wrong
    board for the rest of its life, disagreeing with every fresh load of the same
    log."""
    url = serve(BOARD_PAGE)
    order = "#col-todo > lf-card", "e => e.map(c => c.id)"
    stale, errors_stale = open_page(browser, url)
    mover, errors_mover = open_page(browser, url)

    stale.locator("#card-baffle .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        stale.keyboard.press(key)
    round_trip(stale)
    expect(mover.locator("#col-done #card-baffle")).to_have_count(1)

    # Hold the first tab's reading of the log where it is, so its `z` names the move
    # it knows about while the second tab moves the same card on past it.
    cut = CutOff().hold(stale)
    # Back to the list it came from and up past its neighbour, which is neither where
    # the first move put it nor where the version wrote it: a second move that landed
    # on the authored placement would make the wrong restore a no-op by luck, and the
    # test would pass on a page doing the wrong thing.
    mover.locator("#card-baffle .lf-grip").focus()
    for key in ["Enter", "ArrowLeft", "ArrowUp", "Enter"]:
        mover.keyboard.press(key)
    round_trip(mover)
    standing = ["card-baffle", "card-heater"]
    assert mover.eval_on_selector_all(*order) == standing

    # The tab the damage shows in: it reads the second move off the log rather than
    # making it, so replay has it marked applied and will not lay it down twice.
    heard, errors_heard = open_page(browser, url)
    assert heard.eval_on_selector_all(*order) == standing

    # Not undo(): the helper ends in round_trip, and this tab's polls are stopped, so
    # what it sends can never come back to it. The offer the helper waits on first is
    # the part that still applies — the line and the dispatcher ask one predicate, so
    # a press made before it stands is one the dispatcher refuses.
    expect(stale.locator(".lf-keyline")).to_contain_text("undo")
    stale.keyboard.press("z")
    # The server answering the post is the fact this wait consumes.
    _until(stale, lambda t: t.acked >= 2, "heard the server take the undo")
    cut.restore()
    told(heard)
    told(heard)

    assert heard.eval_on_selector_all(*order) == standing, (
        "a tab that heard the undo painted the state that stood before the move it "
        "named, over the move that still stands"
    )
    fresh, errors_fresh = open_page(browser, url)
    assert fresh.eval_on_selector_all(*order) == standing, (
        "a tab reading the log fresh disagrees with the tab that heard the undo"
    )
    # The stale tab's own console too: `refuse` cancels rather than fails a
    # request, so stopping its polls leaves nothing for it to report.
    assert errors_stale == [] and errors_mover == []
    assert errors_heard == [] and errors_fresh == []
    stale.close()
    mover.close()
    heard.close()
    fresh.close()


def test_a_withdrawal_is_heard_by_a_tab_reading_a_later_version(browser, serve):
    """Which version a gesture was made against decides whether `z` is *offered*, and
    says nothing about whether an undo must be *heard*. A tab holding an older version
    can still gesture — `?pin` is a URL a reader keeps, and a tab mid-composition holds
    its version too — so its undo reaches a tab that has moved on, and that tab applied
    the action being withdrawn (replay takes every action up to the version it reads).

    Refusing to hear it there leaves the newer tab showing a gesture the log no longer
    holds, and only until someone reloads it. What this load's markup says is the right
    answer either way: a version written around the decision states the same placement,
    so the restore is a no-op, and one that was not, like this one, catches up."""
    url = serve(BOARD_PAGE)
    pinned, errors_pinned = open_page(browser, url + "&pin")
    moved_on, errors_moved_on = open_page(browser, live_url(url))

    pinned.locator("#card-baffle .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        pinned.keyboard.press(key)
    round_trip(pinned)
    expect(moved_on.locator("#col-done #card-baffle")).to_have_count(1)

    # A second version that says nothing about the move — the card is where v1 wrote
    # it — so what the two tabs owe the card afterwards is visibly different.
    d = serve.page_dir
    stamp_page(d, BOARD_PAGE, "unchanged")
    wait_for_revision(moved_on, 2)
    expect(moved_on).not_to_have_url(re.compile("/versions/"))
    expect(pinned).to_have_url(re.compile("v1"))
    # Replay carries the v1 move onto v2, so this tab is showing it.
    expect(moved_on.locator("#col-done #card-baffle")).to_have_count(1)

    undo(pinned)
    told(moved_on)
    told(moved_on)
    expect(moved_on.locator("#col-todo #card-baffle")).to_have_count(1)
    assert errors_pinned == [] and errors_moved_on == []
    pinned.close()
    moved_on.close()


def test_a_second_tab_takes_the_decision_back_too(browser, serve):
    """The rebuild happens in every tab off the log, not in the one that pressed off
    the gesture — so a tab that never saw the press arrives at the same page. That
    is the difference between taking a decision back and painting over it: this tab
    applied the accept through replay, and what puts it right is the withdrawal
    arriving, not anything the other tab did to its own DOM.

    It is also where the reader is left free to decide again, the other way: the
    accept is withdrawn rather than reversed, so a reject after it is an ordinary
    first decision and both tabs follow it."""
    url = serve(SUGGESTION_PAGE)
    one, errors_one = open_page(browser, url)
    two, errors_two = open_page(browser, url)
    marks = """(id) => Object.fromEntries(['lf-sug-del', 'lf-sug-ins'].map(name =>
        [name, [...(CSS.highlights.get(name) ?? [])]
            .filter(r => document.getElementById(id).contains(r.startContainer))
            .length]))"""
    pending = one.evaluate(marks, "sug-refill")
    assert pending["lf-sug-del"] and pending["lf-sug-ins"]

    one.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    round_trip(one)
    expect(two.locator("#sug-refill lf-old")).to_be_hidden()

    undo(one)
    expect(two.locator("#sug-refill lf-old")).to_be_visible()
    expect(two.locator(".lf-decisions")).to_have_text("Asks 0/3")
    # Everything the change had when it was pending, including what the theme paints
    # from ranges the module registers — a rebuild that dropped those would leave a
    # proposal on the page with nothing marking what it changes.
    assert one.evaluate(marks, "sug-refill") == pending
    assert (
        one.evaluate(
            "() => document.querySelectorAll('[data-lf-reader-override]').length"
        )
        == 0
    )

    unfolded_button(two.locator("[data-lf-for='sug-refill'] .lf-sug-reject")).click()
    round_trip(two)
    expect(one.locator("#sug-refill lf-new")).to_be_hidden()
    assert [
        e.get("action", e["kind"])
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] in ("action", "undo")
    ] == ["accept", "undo", "reject"]
    assert errors_one == [] and errors_two == []
    one.close()
    two.close()


def test_a_rebuild_keeps_what_the_reader_did_inside_the_change(browser, serve):
    """A change may propose markup that holds a widget — the family's own answer to
    a widget-state change, there being no separate patch shape — and a pick the
    reader made inside it is theirs, not part of the decision they took back.

    The rebuild replaces the subtree those actions were applied to, so what this
    load had already applied inside it has to land again on the new nodes. Counting
    only the rebuilt widget's own events leaves the nested pick marked as applied to
    a node the page no longer has, and it comes back authored with the reader's
    answer silently gone."""
    page, errors = open_page(browser, serve(NESTED_SUGGESTION))
    page.locator("#blend-mixed").click()
    round_trip(page)
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "blend-mixed")

    page.locator("[data-lf-for='sug-thistle'] .lf-sug-accept").click()
    round_trip(page)
    undo(page)

    expect(page.locator("#sug-thistle lf-old, #sug-thistle lf-new")).to_have_count(1)
    expect(
        page.locator("[data-lf-for='sug-thistle'] .lf-sug-accept")
    ).to_have_attribute("aria-label", re.compile(r"^Accept the suggested change"))
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "blend-mixed")
    assert errors == []
    page.close()


def test_a_withdrawn_decision_is_still_withdrawn_after_a_reload(browser, serve):
    """The rebuild is how the page in front of the reader catches up; it is not
    where the outcome lives. A page loaded after the fact never applies the
    withdrawn accept at all — replay skips it exactly as it skips one a version
    restated — so the same page comes back without a rebuild having run on it."""
    url = serve(SUGGESTION_PAGE)
    page, errors = open_page(browser, url)
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    undo(page)
    page.close()

    again, errors = open_page(browser, url)
    expect(again.locator("#sug-refill lf-old")).to_be_visible()
    expect(again.locator(".lf-decisions")).to_have_text("Asks 0/3")
    assert errors == []
    again.close()


def test_the_composer_never_stands_on_its_own_mark(browser, serve):
    """The mark is the only thing naming the passage the box is about, so a box covering
    all of it is a box about nothing. That is not hypothetical: a restored draft reappears
    just under the banner, and the reading position puts the passage it was made on back
    where it was — which, for a passage that was near the top of a narrow column, is
    exactly there. The box has to move off it.

    Not off every pixel of it. The box has always covered the tail of a long passage and
    that reads fine; what may not happen is every rect hidden at once."""
    filler = "\n".join(
        f"<p id='f{i}'>Filler {i}. " + "Words. " * 20 + "</p>" for i in range(30)
    )
    url = serve(SETTLED_PAGE.replace("</main>", filler + "\n</main>"))
    page, errors = open_page(browser, url)

    page.locator(".lf-settled").click()  # open the settled group, as a reader would
    page.wait_for_selector("#opt-strict:visible")
    # A card in the middle column, scrolled just under the banner: narrower than the 320px
    # box and centred on it, which is the geometry the box can swallow whole.
    page.evaluate("""() => {
        const r = document.querySelector('#opt-strict').getBoundingClientRect();
        document.scrollingElement.scrollBy({top: r.top - 60, behavior: 'instant'});
    }""")
    page.locator("#opt-strict").click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill("what did the trial actually show?")
    assert mark_shows_beside_composer(page), (
        "the box covered the passage it just opened on"
    )

    page.reload()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'contents'"
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-pending')?.size ?? 0) > 0")
    assert mark_shows_beside_composer(page), (
        "the restored box came back on top of its own mark, and with the mark hidden "
        "nothing on screen says what the draft is about"
    )
    assert not composer_quote(page)["shown"], (
        "the mark is showing and the composer prints the passage as well"
    )
    assert errors == []
    page.close()


def test_the_comment_field_scrolls_with_the_passage_it_is_about(browser, serve):
    """The field points at a passage, so it lives in the document's coordinate space and
    scrolling moves the two together. A viewport-fixed field would let the page scroll
    underneath until the response sat over something it was never about.

    Both readings and the scroll happen in one synchronous evaluate — writing
    scrollTop reflows before the very next read — so there is no trip here to wait
    on."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    moved = page.evaluate("""() => {
        const top = (el) => el.getBoundingClientRect().top;
        const composer = document.querySelector('.lf-fab-bar');
        const passage = document.getElementById('p30');
        const before = { composer: top(composer), passage: top(passage) };
        document.scrollingElement.scrollTop += 240;
        return { composer: top(composer) - before.composer,
                 passage: top(passage) - before.passage };
    }""")
    assert moved["passage"] < 0, "the scroll must actually have moved the page"
    assert moved["composer"] == moved["passage"], (
        f"the box parted from its passage: the page moved {-moved['passage']}px "
        f"and the composer {-moved['composer']}px"
    )
    assert errors == []
    page.close()


def test_the_comment_field_stands_in_the_margin_beside_the_passage(browser, serve):
    """Where the column leaves room, the field goes into the margin rather than onto
    somebody's words. The passage and its neighbours stay fully readable while the
    user writes about them.

    The window is wide enough for that room to be there wherever this runs. What the
    placement asks is whether the box and its two 8px gaps fit beside the column in
    body's client box, and that box is the window less whatever the platform spends on
    a scrollbar — nothing under macOS's overlay ones, 15px of gutter on the Linux
    runner. 1440 made the question exact rather than true: the margin fitted the box
    with nothing at all to spare where this was written, and fell 15px short where it
    ran, so a placement doing precisely what it should read as a bug."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    resized(page, 1600, 900)
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    standing = page.evaluate("""() => {
        const box = document.querySelector('.lf-fab-bar').getBoundingClientRect();
        const touching = [...document.querySelectorAll('main p, main h1')]
            .filter(el => el.checkVisibility())
            .filter(el => {
                const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                for (let node = walk.nextNode(); node; node = walk.nextNode()) {
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    if ([...range.getClientRects()].some(r =>
                        r.left < box.right && box.left < r.right
                        && r.top < box.bottom && box.top < r.bottom)) return true;
                }
                return false;
            })
            .map(el => el.id || el.tagName);
        return { touching };
    }""")
    assert standing["touching"] == [], (
        f"the box stands on the page's own text: {standing['touching']}"
    )
    assert errors == []
    page.close()


def test_opening_the_panel_stands_down_the_field_without_losing_its_draft(
    browser, serve
):
    """Opening the thread workspace stands the compact field down, so its old absolute
    position cannot create sideways overflow after the page narrows. The words remain
    the passage's draft and return when the reader selects that passage again."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    # Start with enough room for the field beside the passage; opening the panel then
    # changes the body's available right edge around that standing float.
    resized(page, 1600, 900)
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    page.locator(".lf-composer textarea").fill("held open across the panel opening")
    # A press on the banner's own button gives the workspace the screen and focus.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    page.wait_for_function(
        "() => document.body.scrollWidth - document.body.clientWidth === 0"
    )

    page.get_by_role("button", name="Close threads").click()
    page.locator("#p30").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_value(
        "held open across the panel opening"
    )
    assert errors == []
    page.close()


def test_a_draft_that_outlives_its_passage_returns_with_that_passage(browser, serve):
    """A draft survives the version it was written against even when that version's
    replacement removes its passage. With no detached composer card, the compact field
    stands down on the new page and the words return when the original passage does."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill(
        "half-written when the version turned over"
    )
    passage = " ".join(page.locator("#p").inner_text().split())
    assert not composer_quote(page)["shown"], "the passage is right here, and marked"

    # Claude ships a version that rewrites the passage out. The page holds still — a
    # draft is mid-composition — and offers the new version as a chip, which the
    # user takes.
    d = serve.page_dir
    rewritten = INLINE_PAGE.replace(
        "A paragraph carrying <strong>bold text</strong> and <em>emphasis</em> inside it,\n"
        "so that a selection across the middle of it lands in more than one text node.",
        "Rewritten, with nothing left of the sentence the draft was about.",
    )
    stamp_page(d, rewritten, "two")
    told(page)
    expect(page.locator(".lf-latest-chip")).to_be_visible()
    page.get_by_role("button", name="New page available", exact=False).click()
    wait_for_revision(page, 2)
    expect(page).not_to_have_url(re.compile("/versions/"))
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert pending_text(page) == "", (
        "v2 rewrote the passage and the page marked it anyway"
    )

    page.goto(url)
    page.wait_for_selector("#p")
    page.locator("#p").click(click_count=3)
    expect(page.locator("#lf-composer-quote")).to_have_text(f"“{passage}”")
    expect(page.locator(".lf-fab-input")).to_have_value(
        "half-written when the version turned over"
    )
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    quote = composer_quote(page)
    assert quote["text"] == f"“{passage}”", f"the quote says {quote['text']!r}"
    assert errors == []
    page.close()


def test_a_pointer_drag_stops_the_line_offering_the_press_it_refuses(browser, serve):
    """`.lf-dragging` is half of the `z` liveness the runtime declares, and a pointer
    drag is a whole gesture rather than a frame: the focus paint lands on the
    mousedown, `fallbackTolerance` fires the drag's start after it, and on a quiet
    board nothing repaints between the pick-up and the drop. So unpainted, the line
    goes on offering `undo` for as long as the reader holds the card, over a press the
    dispatcher is already refusing. The drop is the same gap read backwards: a card
    put down where it was picked up takes the class off and returns before #send, so
    there is no send downstream to paint in its place."""
    url = serve(BOARD_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sprint",
            "action": "move",
            "detail": {"card": "card-heater", "to": "col-done", "index": 0},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    # A box measured across replay's FLIP is a box the card has already left: the press
    # lands on the grip at that instant and the pointer is somewhere else by the
    # mousemove after it, so the drag never starts.
    page.wait_for_function(
        "() => document.getElementById('card-heater').getAnimations().length === 0"
    )
    assert "z undo" in _painted_line(page)
    sent = _traffic(page).sends

    # The mousedown lands on an already-focused control and fires no focusin, so the
    # paint under test is the only one that could clear the offer. Held inside the
    # column it has to itself, the card reorders nothing and onEnd returns before #send.
    box = grip.bounding_box()
    start = (
        math.floor(box["x"] + box["width"] / 2),
        math.floor(box["y"] + box["height"] / 2),
    )
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(start[0], start[1] + 24, steps=8)  # past fallbackTolerance
    page.wait_for_selector("lf-board.lf-dragging")  # the gesture is live in the page
    # Read once, on the frame the paint coalesces to, rather than through `expect`:
    # a heartbeat two seconds out repaints the line whatever this drag did, so an
    # assertion that re-decisions passes on the poll and says nothing about the edge.
    assert "z undo" not in _painted_line(page), (
        "the line offered a press the dispatcher refuses for the length of a drag"
    )

    page.mouse.up()
    assert page.locator("lf-board.lf-dragging").count() == 0
    assert "z undo" in _painted_line(page), (
        "the drop that sent nothing left the line refusing a press that is live"
    )
    assert _traffic(page).sends == sent, "the drop that moved nothing sent a move"
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    assert errors == []
    page.close()
