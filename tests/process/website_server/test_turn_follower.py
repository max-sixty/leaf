"""How the follower tracks a running hosted turn: its stream and activity, stopping it,
and releasing the page's claim and status however the turn ends."""

import json
import os
import threading

import pytest
from interact_support import (
    STATED_TIMEOUT,
    activity_reading,
    declared,
    owed_answers,
    page_state,
    status_and_stream,
    take_stream_activity,
)
from interact_support import append_carried_log_record as append_event

import leaf_website as website_server
from leaf import codex as leaf_codex
from leaf.codex import AppServerRequestRejected
from leaf.delivery import response_addresses
from leaf.event_log import read_events
from leaf.interaction_log import read_interactions
from leaf.state import session_record
from leaf.thread import post_reply
from process.website_server import (
    accept_in_turn,
    hosted_follower,
)


def test_a_turn_that_will_not_stop_leaves_the_thread_rather_than_the_user(
    page_dir, monkeypatch
):
    """A dispatch holds the user's request open, so it does not wait forever.

    The turn being stopped belongs to a container that is already gone. If App
    Server does not report it ended, this start raises, the Worker receipts the
    message as one the agent could not be started for, and the thread is left to
    whichever container start meets it next.
    """
    append_event(page_dir, {"kind": "comment", "author": "user", "text": "hello"})
    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(website_server, "TURN_ABORT_WAIT", 0.0)
    sent = []

    class Socket:
        def recv(self, timeout):
            raise TimeoutError

    def send(socket, method, params, pending=None):
        sent.append(method)
        return {}

    monkeypatch.setattr(harness, "_send", send)

    with pytest.raises(RuntimeError, match="did not stop"):
        harness._end_unfollowed_turn(Socket(), "hosted-thread", [], "user-event")

    assert sent == ["turn/interrupt"]


def test_an_interrupt_refused_by_an_idle_thread_is_recorded_not_raised(
    page_dir, monkeypatch, capsys
):
    """Losing the race to a turn's own ending is not a fault.

    The follower interrupts whatever its turn may still be doing, and App Server
    refuses when that turn has already finished. Raising there would replace the
    ending the follower is in the middle of accounting for with this one.
    """
    harness = website_server.WebsiteCodexHarness("codex")

    class Socket:
        closed = False

        def close(self):
            self.closed = True

    socket = Socket()
    monkeypatch.setattr(website_server, "app_server_connect", lambda _endpoint: socket)
    monkeypatch.setattr(
        website_server, "app_server_handshake", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        harness,
        "_send",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AppServerRequestRejected("no active turn to interrupt")
        ),
    )

    harness._interrupt("hosted-thread", "app-server-turn", eventId="user-event")

    [record] = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert record["event"] == "turn_interrupt_failed"
    assert record["detail"] == "no active turn to interrupt"
    assert record["turnId"] == "app-server-turn"
    assert socket.closed


def test_a_turn_whose_stream_drops_is_stopped_and_its_move_receipted(
    page_dir, monkeypatch
):
    """A follower that stops ends its turn and answers for it.

    The connection is the only thing Leaf loses; the provider turn goes on
    running, answering into nobody, and its pickup of this move stops every other
    writer from receipting it. So the follower that took the move is the one that
    has to close both: `turn/interrupt` for the turn, and the receipt that tells
    the user to send again — which the move's own pickup would otherwise refuse,
    leaving the page showing a message picked up by a turn that is gone.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(
        harness, "_send", lambda *a, **k: {"turn": {"id": "app-server-turn"}}
    )

    class LostSocket:
        def recv(self, timeout):
            raise OSError("connection lost")

        def close(self):
            pass

    follow = harness._start_turn(
        LostSocket(),
        page_dir,
        "hosted-thread",
        type("Process", (), {"pid": os.getpid()})(),
    )
    interrupts = []
    monkeypatch.setattr(
        harness,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    harness._hold_waiter(page_dir, "hosted-thread")
    follow.follow()
    events = read_events(page_dir)
    activity = activity_reading(page_dir)

    assert interrupts == [("hosted-thread", "app-server-turn")]
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    assert reply["text"] == website_server.FAILURE_RECEIPTS["turn_failed"]
    claim_record = website_server.page_claim(page_dir)
    assert claim_record is not None
    assert claim_record["turn_closed"] is not None
    assert activity["kind"] != "working"
    assert activity["obligations"] == []


def test_notifications_before_start_response_reach_the_turn_follower(
    page_dir, monkeypatch
):
    # A real delivery, because the follower reads it back by id when it accounts for
    # the turn, and a made-up id is refused there rather than at the send.
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    payload = prepared.payload
    messages = iter(
        [
            json.dumps({"id": 0, "result": {}}),
            json.dumps({"id": 1, "result": {"thread": {"id": "hosted-thread"}}}),
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "startedAtMs": 900,
                        "item": {
                            "id": "delivery",
                            "type": "functionCallOutput",
                            "name": "leaf_delivery",
                            "output": json.dumps(payload),
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "completedAtMs": 1_000,
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Deployment verified.",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "initial-turn",
                            "status": "completed",
                            "items": [],
                        },
                    },
                }
            ),
            json.dumps({"id": 2, "result": {"turn": {"id": "initial-turn"}}}),
        ]
    )

    class Socket:
        closed = False

        def send(self, message):
            pass

        def recv(self, timeout):
            return next(messages)

        def close(self):
            self.closed = True

    socket = Socket()
    monkeypatch.setattr(website_server, "app_server_connect", lambda endpoint: socket)
    take_stream_activity(monkeypatch, [], [])
    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(harness, "_hold_waiter", lambda *args: None)
    monkeypatch.setattr(
        website_server, "prepare_codex_delivery", lambda *args: prepared
    )
    monkeypatch.setattr(
        website_server,
        "open_app_server_delivery",
        lambda *args: "leaf-turn",
    )
    monkeypatch.setattr(
        website_server, "next_unaccepted_agent_event", lambda *args, **kwargs: None
    )
    finished = []
    completed = threading.Event()

    def finish(*args, expected):
        finished.append(args)
        completed.set()

    monkeypatch.setattr(harness, "_finish_turn", finish)

    assert (
        harness._start_thread(
            page_dir,
            type("Process", (), {"pid": os.getpid()})(),
            comment["id"],
        )
        == "hosted-thread"
    )

    assert completed.wait(timeout=STATED_TIMEOUT), "the hosted turn never completed"
    assert finished == [
        (
            page_dir,
            "hosted-thread",
            {"id": "initial-turn", "status": "completed", "items": []},
        )
    ]
    assert socket.closed


def test_the_website_harness_keeps_its_claim_listening_through_the_agent_turn(
    page_dir, monkeypatch
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(
        harness,
        "_send",
        lambda *args: {"turn": {"id": "app-server-turn"}},
    )

    try:
        follow = harness._start_turn(
            "socket",
            page_dir,
            "hosted-thread",
            type("Process", (), {"pid": os.getpid()})(),
        )
        # The reading is the turn's, so it starts when the follower opens the turn
        # rather than when the request that made it went out.
        follow.begin()
        state = page_state(page_dir)

        assert state["listening"] is True
        assert state["activity"]["kind"] == "working"
        assert state["activity"]["observed_kind"] == "working"
        assert owed_answers(page_dir)[0]["input"] == comment["id"]

        leaf_codex.set_stream_activity(
            "hosted-thread",
            "app-server-turn",
            {"kind": "tool", "detail": "Editing index.html"},
            expected=session_record("hosted-thread"),
        )
        working = page_state(page_dir)
        assert working["activity"]["kind"] == "working"
        assert working["activity"]["observed_kind"] == "tool"
        assert working["activity"]["observed"] == "Editing index.html"
    finally:
        harness.close()

    assert page_state(page_dir)["listening"] is False


def test_the_starting_connection_projects_codex_activity(page_dir, monkeypatch, capsys):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    messages = iter(
        [
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "startedAtMs": 1_000,
                        "item": {
                            "id": "command-1",
                            "type": "commandExecution",
                            "command": "leaf page check .",
                            "commandActions": [],
                            "cwd": "/work",
                            "status": "inProgress",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "completedAtMs": 1_080,
                        "item": {
                            "id": "command-1",
                            "type": "commandExecution",
                            "command": "leaf page check .",
                            "status": "completed",
                            "exitCode": 0,
                            "commandActions": [],
                            "cwd": "/work",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "startedAtMs": 2_000,
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "completedAtMs": 2_500,
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Deployment verified.",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "initial-turn",
                            "status": "completed",
                            "items": [
                                {
                                    "id": "message-1",
                                    "type": "agentMessage",
                                    "phase": "final_answer",
                                    "text": "Deployment verified.",
                                }
                            ],
                        },
                    },
                }
            ),
        ]
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            return next(messages)

        def close(self):
            self.closed = True

    socket = Socket()
    updates = []
    clears = []
    streamed = []
    committed = []

    class ReplyStream:
        def __init__(self, session, turn, delivery, target):
            streamed.append((session, turn, delivery, dict(target)))

        def update(self, update):
            message = update.get("message") if update is not None else None
            if message is not None and message["phase"] == "final_answer":
                streamed.append((message["text"], message["complete"]))
                return True
            return False

        def finish(self, state, text):
            committed.append((state, text))

    take_stream_activity(monkeypatch, updates, clears)
    monkeypatch.setattr(leaf_codex, "AppServerReplyStream", ReplyStream)

    harness = website_server.WebsiteCodexHarness("codex")
    finished = []
    monkeypatch.setattr(
        harness, "_finish_turn", lambda *args, expected: finished.append(args)
    )
    hosted_follower(
        harness, page_dir, prepared, socket, turn_id="initial-turn"
    ).follow()

    assert updates == [
        ("hosted-thread", "initial-turn", {"kind": "working"}),
        (
            "hosted-thread",
            "initial-turn",
            {"kind": "tool", "detail": "Running leaf page check ."},
        ),
        ("hosted-thread", "initial-turn", {"kind": "working"}),
        ("hosted-thread", "initial-turn", {"kind": "replying"}),
        ("hosted-thread", "initial-turn", {"kind": "working"}),
    ]
    # The turn's own reading and no other, taken off once, when the follower
    # accounts for the ended turn.
    assert clears == [("hosted-thread", "initial-turn")]
    [address] = response_addresses(prepared.payload)
    assert streamed == [
        (
            "hosted-thread",
            "initial-turn",
            prepared.payload["id"],
            address,
        ),
        ("Deployment verified.", True),
    ]
    assert committed == [("completed", "Deployment verified.")]
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record["event"] for record in logs] == [
        "turn_following_started",
        "turn_delivery_bound",
        "turn_first_notification",
        "turn_first_activity",
        "turn_item_started",
        "turn_item_completed",
        "turn_item_started",
        "turn_item_completed",
        "turn_first_model_message",
        "turn_reply_first_text_published",
        "turn_reply_published",
        "turn_stream_completed",
        # The reply above is this test's stand-in, which records the commit rather
        # than writing it, so the move it was answering is still owed one.
        "turn_failure_reported",
    ]
    assert logs[4] == {
        "component": "leaf-agent",
        "event": "turn_item_started",
        "eventId": comment["id"],
        "turnId": "initial-turn",
        "itemId": "command-1",
        "itemType": "commandExecution",
        "itemAtMs": 1_000,
    }
    assert logs[5]["durationMs"] == 80
    assert logs[5]["status"] == "completed"
    assert logs[5]["exitCode"] == 0
    assert logs[7]["durationMs"] == 500
    assert logs[8]["phase"] == "final_answer"
    assert logs[9]["recovered"] is False
    published = next(
        record
        for record in read_interactions(page_dir)
        if record["type"] == "turn_reply_published"
    )
    assert published["eventId"] == comment["id"]
    assert published["reply"] == {
        "item": "message-1",
        "phase": "final_answer",
        "text": "Deployment verified.",
        "complete": True,
    }
    assert all("reply" not in record for record in logs)
    assert finished == [
        (
            page_dir,
            "hosted-thread",
            {
                "id": "initial-turn",
                "status": "completed",
                "items": [
                    {
                        "id": "message-1",
                        "type": "agentMessage",
                        "phase": "final_answer",
                        "text": "Deployment verified.",
                    }
                ],
            },
        )
    ]
    assert socket.closed


def test_a_stream_that_goes_silent_ends_its_turn_like_a_dropped_one(
    page_dir, monkeypatch
):
    """Silence past the bound ends the turn, because nothing else can end it.

    The subscription that has gone quiet is the one that would carry the turn's
    completion, so waiting longer only holds the user on a page that says the
    agent is working. The turn is stopped, its reading comes off the page, and the
    user is told no answer is coming.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    monkeypatch.setattr(website_server.HostedTurn, "silence", 0.0)

    class Socket:
        def __init__(self):
            self.closed = False

        def recv(self, timeout):
            raise TimeoutError

        def close(self):
            self.closed = True

    silent = Socket()
    harness = website_server.WebsiteCodexHarness("codex")
    interrupts = []
    monkeypatch.setattr(
        harness,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    # Without the lease this page is not listening, and a page that is not
    # listening reads `away` whatever its stream reading holds — which would pass
    # the activity assertion below on a follower that left one held.
    harness._hold_waiter(page_dir, "hosted-thread")

    hosted_follower(harness, page_dir, prepared, silent).follow()

    events = read_events(page_dir)
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    assert interrupts == [("hosted-thread", "app-server-turn")]
    claim_record_2 = website_server.page_claim(page_dir)
    assert claim_record_2 is not None
    assert claim_record_2["turn_closed"] is not None
    assert activity_reading(page_dir)["kind"] != "working"
    assert silent.closed


def test_a_follower_fault_of_any_shape_still_releases_its_website_turn(
    page_dir, monkeypatch, capsys
):
    """The follower owes its turn an outcome for every fault, not a listed few.

    A fault the stream handler does not name would otherwise leave the claim open with
    the activity its first line set, which is a page that reads working for as long as
    the container lives and never reaches a receipt. Catching it takes the traceback
    the excepthook used to print, so the turn's own record has to name the fault.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            raise KeyError("params")

        def close(self):
            self.closed = True

    socket = Socket()
    harness = website_server.WebsiteCodexHarness("codex")
    interrupts = []
    monkeypatch.setattr(
        harness,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    hosted_follower(harness, page_dir, prepared, socket).follow()

    events = read_events(page_dir)
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    assert interrupts == [("hosted-thread", "app-server-turn")]
    claim_record_3 = website_server.page_claim(page_dir)
    assert claim_record_3 is not None
    assert claim_record_3["turn_closed"] is not None
    activity = activity_reading(page_dir)
    assert activity["kind"] != "working"
    assert activity["obligations"] == []
    assert socket.closed
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    [completed] = [
        record for record in logs if record["event"] == "turn_stream_completed"
    ]
    assert (completed["status"], completed["error"]) == ("failed", "KeyError")


def test_an_invalid_source_still_releases_a_finished_website_turn(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    accept_in_turn("hosted-thread")
    (page_dir / "index.html").write_text("<main>unfinished")

    with pytest.raises(ValueError):
        website_server.WebsiteCodexHarness("codex")._finish_turn(
            page_dir,
            "hosted-thread",
            {"id": "app-server-turn", "status": "completed", "error": None},
            expected=session_record("hosted-thread"),
        )

    claim = website_server.page_claim(page_dir)
    assert claim is not None
    assert claim["turn"] == "app-server-turn"
    assert claim["turn_closed"] is not None
    assert declared(page_dir)["state"] == "waiting"
    assert [obligation["input"] for obligation in owed_answers(page_dir)] == [
        comment["id"]
    ]


def test_a_reply_that_cannot_be_written_still_closes_its_website_turn(
    page_dir, monkeypatch
):
    """The page stops saying the agent is working, however the reply went.

    `AppServerReplyStream` guards only the commit of a completed answer. Setting
    its state and releasing the reservation open their own page transactions; the turn's
    work may have left that page unopenable. The turn has ended either way, and until
    its Leaf turn closes the page tells its user the agent is working, with nothing
    but the claim's grace to correct it — and the move it was carrying goes without
    the receipt that says no answer is coming.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    harness = website_server.WebsiteCodexHarness("codex")
    turn = hosted_follower(harness, page_dir, prepared)
    turn.begin()

    def unopenable(*_args):
        raise OSError("the page could not be opened")

    monkeypatch.setattr("leaf.codex.AppServerReplyStream._set_state", unopenable)
    with pytest.raises(OSError, match="could not be opened"):
        turn.commit({"id": "app-server-turn", "status": "completed", "items": []})

    claim_record_4 = website_server.page_claim(page_dir)
    assert claim_record_4 is not None
    assert claim_record_4["turn_closed"] is not None
    [receipt] = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert (receipt["responds"], receipt["failure"]) == (comment["id"], "turn_failed")


def test_a_finished_website_turn_does_not_overwrite_an_agent_reply(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    accept_in_turn("hosted-thread")
    post_reply(
        page_dir,
        {"parent": comment["id"], "responds": comment["id"]},
        "Done.",
        identity={"agent": "Agent", "session": "leaf-website-agent"},
    )
    with website_server.PageTransaction(page_dir) as page:
        page.set_status("waiting")
    before = read_events(page_dir)

    website_server.WebsiteCodexHarness("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        {"id": "app-server-turn", "status": "completed", "error": None},
        expected=session_record("hosted-thread"),
    )

    # The ending declares the page waiting for its agent, and writes nothing else.
    after = read_events(page_dir)
    assert after[: len(before)] == before
    assert [(event["kind"], event["state"]) for event in after[len(before) :]] == [
        ("status", "waiting")
    ]


def test_an_old_website_completion_does_not_close_the_new_leaf_turn(page_dir):
    first = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    harness = website_server.website_harness("hosted-thread", os.getpid())
    website_server.prepare_codex_delivery(page_dir, harness)
    accept_in_turn("hosted-thread", "old-app-turn")
    website_server.close_session_turn("hosted-thread")
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    website_server.prepare_codex_delivery(page_dir, harness)
    accept_in_turn("hosted-thread", "new-app-turn")

    website_server.WebsiteCodexHarness("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        {"id": "old-app-turn", "status": "failed", "error": None},
        expected=session_record("hosted-thread"),
    )

    claim = website_server.page_claim(page_dir)
    assert claim is not None
    assert claim["turn"] == "new-app-turn"
    assert claim["turn_closed"] is None
    replies = {
        event["parent"]: event["text"]
        for event in read_events(page_dir)
        if event["kind"] == "reply"
    }
    assert replies == {}
    assert [item["input"] for item in owed_answers(page_dir)] == [
        first["id"],
        second["id"],
    ]


def test_hosted_completion_cannot_borrow_a_reused_session_generation(page_dir):
    from leaf.state import end_session, prompt_turn

    append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "An old request"}
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir, website_server.website_harness("hosted-thread", os.getpid())
    )
    harness = website_server.WebsiteCodexHarness("codex")
    old = hosted_follower(harness, page_dir, prepared, turn_id="same-turn")
    end_session("hosted-thread")
    prompt_turn("hosted-thread", "same-turn")
    with website_server.PageTransaction(page_dir) as page:
        page.take_claim(website_server.website_harness("hosted-thread", os.getpid()))
        page.set_status("waiting")
    leaf_codex.set_stream_activity(
        "hosted-thread",
        "same-turn",
        {"kind": "tool", "detail": "New activity"},
        expected=session_record("hosted-thread"),
    )
    winner = session_record("hosted-thread")
    status = status_and_stream(page_dir)
    old.close({"id": "same-turn", "status": "completed", "items": []}, None)
    assert session_record("hosted-thread") == winner
    assert status_and_stream(page_dir) == status
