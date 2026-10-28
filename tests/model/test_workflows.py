"""Workflows and thread attention: each user input's response obligation, its
stage and who acts next, the order surfaces show them in, and the attention a
thread reads from them."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from interact_support import (
    _start,
    append_carried_log_record,
    append_command,
    continued,
    declare_work,
    delivered,
    freeze_events,
    last_deliverable_seq,
    obligations_on_user,
    owed,
    owed_answers,
    page_state,
    publish,
    receive_through,
    served_obligations,
    served_thread,
    served_updates,
    serving,
    state_json,
)

from leaf import activity as activity_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import events as event_folds_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import obligations as obligations_model
from leaf import projection as projection_model
from leaf import revisioning as revisioning_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf.registry import storage as registry_storage
from leaf.served_state import browser as browser_served_model
from leaf.served_state import work as work_served_model


@pytest.mark.parametrize(
    "case",
    json.loads(Path(__file__).parents[1].joinpath("turn_cases.json").read_text()),
    ids=lambda case: case["id"],
)
def test_a_users_turns_are_the_gestures_the_browser_hands_over(case):
    """The user's turns in a thread, each with the message it shows on, are the
    gestures the browser's `isTurnEvent` and `turnMessage` take for its own sends."""
    events = [
        {"author": "user", "seq": seq, "ts": "2026-10-19T00:00:00+00:00", **event}
        for seq, event in enumerate(case["events"], 1)
    ]
    turns = [
        [turn["id"], event_folds_model.turn_message(turn)]
        for thread in event_folds_model.build_threads(events, {}).values()
        for turn in event_folds_model.exchange(thread)
    ]
    assert turns == case["turns"]


def test_consecutive_user_inputs_share_one_exact_response_obligation(page_dir):
    """Each input keeps progress while the newest address owns batch settlement."""
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "batch-first", "author": "user", "text": "A"},
    )
    second = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "batch-second",
            "author": "user",
            "parent": first["id"],
            "text": "B",
        },
    )

    state = page_state(page_dir)
    assert [(item["input"], item["obligation"]) for item in state["workflows"]] == [
        (first["id"], f"update:{second['id']}"),
        (second["id"], f"update:{second['id']}"),
    ]
    assert [(item["input"], item["answer"]) for item in owed_answers(page_dir)] == [
        (
            second["id"],
            {"kind": "reply", "parent": second["id"], "responds": second["id"]},
        )
    ]

    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "batch-answer",
            "author": "agent",
            "parent": second["id"],
            "responds": second["id"],
            "text": "Answered together",
        },
    )
    assert page_state(page_dir)["workflows"] == []


def test_terminal_harness_failure_keeps_exact_user_recovery_without_stop_obligation(
    page_dir,
):
    publish(page_dir)
    source = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "failed-input", "author": "user", "text": "A"},
    )
    failure = thread_model.post_reply(
        page_dir,
        {"parent": source["id"], "responds": source["id"]},
        "The agent's turn ended without an answer. Send it again to retry.",
        failure="turn_failed",
    )

    state = page_state(page_dir)
    [workflow] = state["workflows"]
    assert (
        workflow["input"],
        workflow["stage"],
        workflow["obligation"],
        workflow["condition"],
    ) == (
        source["id"],
        "answered",
        f"update:{source['id']}",
        {"kind": "failed", "operation": "response"},
    )
    [record] = served_updates(state["browser"])
    assert (record["id"], record["status"], record["next_actor"]) == (
        f"update:{source['id']}",
        "open",
        "user",
    )
    assert workflow["activity"] == [
        {
            "kind": "response",
            "detail": None,
            "ts": failure["ts"],
            "session": failure.get("session"),
            "turn": failure.get("turn"),
        }
    ]
    assert owed_answers(page_dir) == []
    # The move is the user's to resend, so the panel counts nothing as saved for
    # the agent to pick up.
    assert set(state["activity"]["counts"].values()) == {0}
    [thread] = served_thread(state["browser"])["threads"]
    assert thread["attention"] == {
        "kind": "needs_user",
        "reason": "resend",
        "workflow": source["id"],
    }


def test_user_resend_clears_terminal_failure_recovery(page_dir):
    publish(page_dir)
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "failed-first", "author": "user", "text": "A"},
    )
    failure = thread_model.post_reply(
        page_dir,
        {"parent": first["id"], "responds": first["id"]},
        "The agent's turn ended without an answer. Send it again to retry.",
        failure="turn_failed",
    )
    resent = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "failed-resent",
            "author": "user",
            "parent": failure["id"],
            "text": "Please try again.",
        },
    )

    state = page_state(page_dir)
    assert [(item["input"], item["obligation"]) for item in state["workflows"]] == [
        (resent["id"], f"update:{resent['id']}")
    ]
    [thread] = served_thread(state["browser"])["threads"]
    assert thread["attention"] == {
        "kind": "waiting",
        "reason": "workflow",
        "workflow": resent["id"],
    }


def test_answering_an_older_input_leaves_the_newer_response_obligation(page_dir):
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "older-first", "author": "user", "text": "A"},
    )
    second = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "older-second",
            "author": "user",
            "parent": first["id"],
            "text": "B",
        },
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "older-answer",
            "author": "agent",
            "parent": first["id"],
            "responds": first["id"],
            "text": "A only",
        },
    )

    state = page_state(page_dir)
    [workflow] = state["workflows"]
    assert (workflow["input"], workflow["obligation"]) == (
        second["id"],
        f"update:{second['id']}",
    )
    assert [
        (item["input"], item["answer"]["responds"]) for item in owed_answers(page_dir)
    ] == [(second["id"], second["id"])]


def test_input_after_a_settled_response_batch_does_not_revive_older_inputs(page_dir):
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "closed-first", "author": "user", "text": "A"},
    )
    second = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "closed-second",
            "author": "user",
            "parent": first["id"],
            "text": "B",
        },
    )
    answer = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "closed-answer",
            "author": "agent",
            "parent": second["id"],
            "responds": second["id"],
            "text": "A and B",
        },
    )
    third = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "closed-third",
            "author": "user",
            "parent": answer["id"],
            "text": "C",
        },
    )

    state = page_state(page_dir)
    assert [(item["input"], item["obligation"]) for item in state["workflows"]] == [
        (third["id"], f"update:{third['id']}")
    ]


def test_unrelated_agent_update_does_not_clear_an_open_user_obligation(page_dir):
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "ask-root", "author": "user", "text": "Start"},
    )
    question = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "ask-question",
            "author": "agent",
            "parent": root["id"],
            "responds": root["id"],
            "text": "Which option?",
            "obligation": True,
            "revision": 1,
        },
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "ask-update",
            "author": "agent",
            "parent": question["id"],
            "text": "The checks finished.",
        },
    )

    browser = page_state(page_dir)["browser"]
    [thread] = served_thread(browser)["threads"]
    [owed] = served_obligations(browser)["user"]
    assert owed["message"] == question["id"]
    assert thread["attention"] == {
        "kind": "needs_user",
        "reason": "obligation",
        "workflow": None,
    }


def test_settling_reaction_closes_an_agent_root_obligation(page_dir):
    publish(page_dir)
    question = thread_model.cmd_comment(
        page_dir, "", "", "", "Forty?", "", obligation=True
    )
    browser = page_state(page_dir)["browser"]
    [before] = served_thread(browser)["threads"]
    [owed] = served_obligations(browser)["user"]
    assert owed["message"] == question["id"]
    assert before["attention"]["kind"] == "needs_user"

    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": question["id"],
            "token": "keep",
        },
    )

    browser = page_state(page_dir)["browser"]
    [after] = served_thread(browser)["threads"]
    assert served_obligations(browser)["user"] == []
    assert after["attention"] is None


def test_frozen_widget_workflow_contributes_to_its_thread_attention(page_dir):
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "widget-thread",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-options id="thread-region" choose>'
            '<lf-option id="thread-east"><strong>East</strong></lf-option>'
            "</lf-options>",
        },
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-region",
            "action": "choose",
            "detail": {"value": ["thread-east"]},
        },
    )
    answered = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-region",
            "action": "answer",
            "detail": {},
        },
    )
    # The move owes a reply in its thread, and the agent starts the move itself.
    [owed] = owed_answers(page_dir)
    assert owed["answer"]["parent"] == asked["id"]
    claimed = _start(page_dir, answered["id"], "Checking East")
    assert claimed.exit_code == 0, claimed.output

    state = page_state(page_dir)
    workflow = next(
        item for item in state["workflows"] if item["input"] == answered["id"]
    )
    assert (workflow["subject"], workflow["stage"]) == (
        {"kind": "widget", "id": "thread-region"},
        "working",
    )
    thread = next(
        item
        for item in served_thread(state["browser"])["threads"]
        if item["id"] == asked["id"]
    )
    assert thread["attention"] == {
        "kind": "waiting",
        "reason": "workflow",
        "workflow": answered["id"],
    }

    # A harness that gives up answers the move with a failure reply, which hands it
    # back to the user rather than settling it.
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": asked["id"],
            "responds": answered["id"],
            "failure": "turn_failed",
            "text": "No answer is coming.",
        },
    )
    state = page_state(page_dir)
    [workflow] = state["workflows"]
    assert (workflow["input"], workflow["obligation"], workflow["condition"]) == (
        answered["id"],
        f"update:{answered['id']}",
        {"kind": "failed", "operation": "response"},
    )
    [record] = served_updates(state["browser"])
    assert record["id"] == f"update:{answered['id']}"
    assert owed_answers(page_dir) == []
    [thread] = served_thread(state["browser"])["threads"]
    assert thread["attention"] == {
        "kind": "needs_user",
        "reason": "resend",
        "workflow": answered["id"],
    }


def test_a_frozen_move_that_answers_no_obligation_keeps_a_receipt_and_owes_nothing(
    page_dir,
):
    """A card moved on a board sent in a reply is a page move in another document:
    it keeps its delivery receipt, owes the agent nothing, publishes no obligation
    and leaves the thread nobody's turn. A start makes it Working without making the
    thread the agent's, and the agent's next turn in the thread takes it in."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    registry = registry_storage.active_registry(page_dir)
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Lay the feeder work out on a board.",
        },
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "text": "Here is the board.",
            "markup": registry["lf-board"]["x-example"],
        },
    )
    moved = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"unit": "card-baffle", "value": "col-doing", "rank": "0i"},
        },
    )

    def reading():
        state = page_state(page_dir)
        [thread] = served_thread(state["browser"])["threads"]
        return state, thread["attention"]

    state, attention = reading()
    [workflow] = state["workflows"]
    assert (workflow["input"], workflow["subject"], workflow["stage"]) == (
        moved["id"],
        {"kind": "widget", "id": "feeder-board"},
        "sent",
    )
    assert workflow["obligation"] is None
    assert owed_answers(page_dir) == []
    assert attention is None

    delivery = freeze_events(page_dir, [moved])
    [event] = delivery["batches"][0]["events"]
    assert "answer" not in event
    # A move that owes nothing can be started, and reads Working on its receipt; the
    # thread holds no record on the agent, so it stays nobody's turn.
    claimed = _start(page_dir, moved["id"], "Rearranging the cards")
    assert claimed.exit_code == 0, claimed.output
    state, attention = reading()
    [workflow] = state["workflows"]
    assert workflow["stage"] == "working"
    assert attention is None

    # Moving the card again supersedes that move, whose receipt goes with it; the
    # agent starts the newer one.
    moved = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"unit": "card-baffle", "value": "col-done", "rank": "0i"},
        },
    )
    renewed = _start(page_dir, moved["id"], "Moving it on")
    assert renewed.exit_code == 0, renewed.output
    state, attention = reading()
    assert [(item["input"], item["stage"]) for item in state["workflows"]] == [
        (moved["id"], "working")
    ]

    # A mark is no turn; the agent's next spoken turn takes the move in.
    append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": asked["id"], "token": "keep"},
    )
    state, attention = reading()
    assert [item["input"] for item in state["workflows"]] == [moved["id"]]
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": asked["id"],
            "text": "Baffle is in progress now.",
        },
    )
    state, attention = reading()
    assert state["workflows"] == []
    assert attention is None

    # Resolution closes the thread without taking in a move made after it.
    thread_model.cmd_resolve(page_dir, asked["id"])
    later = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"unit": "card-heater", "value": "col-done", "rank": "0i"},
        },
    )
    state, attention = reading()
    [workflow] = state["workflows"]
    assert (workflow["input"], workflow["stage"], workflow["obligation"]) == (
        later["id"],
        "sent",
        None,
    )
    assert attention is None


def test_thread_attention_names_the_workflow_the_thread_waits_on():
    """A thread's status reads the records open in it, and names the strongest
    workflow serving the one it waits on. An input a newer one covers serves the newer
    one's record, so its pickup or a reply streaming to it keeps reading on the thread;
    a frozen move that owes nothing serves none, so its further stage never stands in
    for the owed reply's."""

    def workflow(id, seq, subject, stage, obligation=None):
        return {
            "id": id,
            "seq": seq,
            "subject": subject,
            "stage": stage,
            "obligation": obligation,
            "condition": None,
        }

    thread = {"id": "root", "kind": "thread"}
    board = {"kind": "widget", "id": "board"}
    owed = obligations_model.update_obligation(
        "newer", thread, "root", "newer", next_actor="agent"
    )
    cases = [
        (
            [
                workflow("older", 1, thread, "replying", owed["id"]),
                workflow("newer", 2, thread, "sent", owed["id"]),
            ],
            "older",
        ),
        (
            [
                workflow("older", 1, thread, "picked_up", owed["id"]),
                workflow("newer", 2, thread, "sent", owed["id"]),
            ],
            "older",
        ),
        (
            [
                workflow("newer", 1, thread, "sent", owed["id"]),
                workflow("card-move", 2, board, "picked_up"),
            ],
            "newer",
        ),
    ]
    # Only which thread the board widget stands in matters here.
    frozen = projection_model.FrozenThreadReading(None, {}, {}, {"board": "root"}, None)
    todos = [
        {
            "id": "t1",
            "owner": "agent",
            "subject": {"kind": "thread", "id": "root"},
            "title": "Rebuild",
            "thread": "root",
            "running": None,
        }
    ]
    thread = {"id": "root", "resolved": None}
    records = obligations_model.collection([owed])
    for workflows, expected in cases:
        assert browser_served_model._thread_attention(
            thread,
            [owed],
            work_served_model.served_workflows(workflows, frozen, records),
            todos,
        ) == {
            "kind": "waiting",
            "reason": "workflow",
            "workflow": expected,
        }
    # With no record open in it, an open task keeps the thread on the agent.
    assert browser_served_model._thread_attention(thread, [], [], todos) == {
        "kind": "waiting",
        "reason": "todo",
        "workflow": None,
        "todo": "t1",
    }


def test_served_workflows_list_the_strongest_first():
    """Every surface that shows one workflow of several shows the first, so the served
    order is the one comparator: a move handed back to the user, then work under way,
    then an uncertain one, then plain delivery by stage, then the newer input. A
    failed response is the furthest stage a move reaches."""

    def workflow(id, seq, stage, condition=None, obligation=None):
        return {
            "id": id,
            "seq": seq,
            "subject": {"kind": "thread", "id": "root"},
            "stage": stage,
            "obligation": obligation,
            "condition": condition,
        }

    handed_back = obligations_model.update_obligation(
        "back", {"kind": "thread", "id": "root"}, "root", "back", next_actor="user"
    )

    stale = {"kind": "stale", "operation": "work"}
    failed = {"kind": "failed", "operation": "response"}
    cases = [
        (
            [workflow("stale", 1, "picked_up", stale), workflow("work", 2, "working")],
            ["work", "stale"],
        ),
        (
            [workflow("older", 1, "working"), workflow("newer", 2, "working")],
            ["newer", "older"],
        ),
        (
            [workflow("fresh", 1, "working"), workflow("stale", 2, "working", stale)],
            ["fresh", "stale"],
        ),
        (
            [
                workflow("work", 1, "working"),
                workflow("back", 2, "answered", failed, handed_back["id"]),
            ],
            ["back", "work"],
        ),
        (
            [workflow("queued", 1, "queued"), workflow("sent", 2, "sent")],
            ["queued", "sent"],
        ),
        (
            [
                workflow("working", 1, "working", stale),
                workflow("back", 2, "answered", failed),
            ],
            ["back", "working"],
        ),
    ]
    frozen = projection_model.FrozenThreadReading(None, {}, {}, {}, None)
    records = obligations_model.collection([handed_back])
    for workflows, expected in cases:
        served = work_served_model.served_workflows(workflows, frozen, records)
        assert [item["id"] for item in served] == expected


def test_a_weaker_old_receipt_does_not_duplicate_a_thread_claim(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    assert _start(page_dir, "c1", "reading the traces").exit_code == 0
    with service_model.PageTransaction(page_dir) as transaction:
        delivery_model.record_pickup(transaction, [comment])
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "c2",
            "author": "user",
            "parent": "c1",
            "text": "and this?",
        },
    )

    interactions = page_state(page_dir)["workflows"]
    assert [(item["input"], item["stage"]) for item in interactions] == [
        ("c1", "working"),
        ("c2", "sent"),
    ]


def test_quiet_exact_workflow_has_a_stale_work_condition(claimed):
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "new input"}
    )
    declare_work(
        claimed,
        "reading it",
        item=comment["id"],
        ts=(datetime.now().astimezone() - timedelta(minutes=20)).isoformat(),
    )

    [workflow] = page_state(claimed)["workflows"]
    assert workflow["stage"] == "working"
    assert workflow["condition"] == {"kind": "stale", "operation": "work"}


def test_fresh_exact_reply_supersedes_an_older_workflow_condition():
    now = datetime.now().astimezone()
    workflow = {
        "id": "input-1",
        "input": "input-1",
        "seq": 1,
        "coordinate": ["thread", "input-1"],
        "obligation": "update:input-1",
        "stage": "working",
        "ts": (now - timedelta(minutes=20)).isoformat(),
        "detail": "Old work",
        "agent": "Leaf guide",
        "session": "session-1",
        "activity": [],
        "condition": None,
        "response": None,
    }
    present = {
        "status": {"state": "idle", "ts": now.isoformat()},
        "claim_session": "session-1",
        "claim_turn": "turn-1",
        "cursor": 0,
        "turn_closed": None,
        "listening": True,
        "session_alive": True,
    }
    reply = {
        "state": "active",
        "session": "session-1",
        "turn": "turn-1",
        "parent": "input-1",
        "responds": "input-1",
        "settles": False,
        "text": "Fresh response",
        "attempt": "reply-attempt",
        "updated_at": now.isoformat(),
    }

    record = obligations_model.update_obligation(
        "input-1",
        {"kind": "thread", "id": "input-1"},
        "input-1",
        "input-1",
        next_actor="agent",
    )
    activity = activity_model.canonical_activity(
        present,
        [workflow],
        [],
        now.isoformat(),
        reply=reply,
        updates=obligations_model.collection([record]),
    )
    [projected] = activity["workflows"]
    assert (projected["stage"], projected["condition"]) == ("replying", None)


def test_pickup_from_an_older_turn_has_a_stale_work_condition(claimed, capsys):
    serving(claimed, 1)
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "new input"}
    )
    assert session_model.cmd_wait(claimed) == 0
    delivered(capsys)
    old = service_model.page_claim(claimed)
    cleanup_model.close_session_turn(old["id"])
    cleanup_model.prompt_turn("s1")
    assert service_model.claim_page(claimed)
    assert service_model.page_claim(claimed)["turn"] != old["turn"]

    [workflow] = page_state(claimed)["workflows"]
    assert workflow["stage"] == "picked_up"
    assert workflow["condition"] == {"kind": "stale", "operation": "work"}


def test_a_widget_reply_does_not_settle_newer_thread_input(page_dir):
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-options id="region" choose>'
            '<lf-option id="east"><strong>East</strong></lf-option>'
            '<lf-option id="west"><strong>West</strong></lf-option>'
            "</lf-options>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "region",
            "action": "choose",
            "detail": {"value": ["east"]},
        },
    )
    newer = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": asked["id"],
            "text": "Wait, do not deploy yet.",
        },
    )
    before = [item["input"] for item in owed(state_json(page_dir))]
    assert before == [chose["id"], newer["id"]]

    replied = thread_model.post_reply(
        page_dir, {"parent": asked["id"], "responds": chose["id"]}, "East noted."
    )
    assert replied["responds"] == chose["id"]
    after = state_json(page_dir)
    assert [item["input"] for item in owed(after)] == [newer["id"]]
    assert owed(after)[0]["answer"] == {
        "kind": "reply",
        "parent": newer["id"],
        "responds": newer["id"],
    }


def test_settling_a_frozen_widget_move_does_not_revive_its_superseded_move(
    claimed, printing, capsys
):
    page_dir = claimed
    session_model.cmd_waiting(page_dir)
    session = service_model.page_claim(page_dir)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(page_dir, session["id"])
    )
    assert lease
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which regions?",
            "markup": '<lf-options id="regions" choose multiple>'
            '<lf-option id="east"><strong>East</strong></lf-option>'
            '<lf-option id="west"><strong>West</strong></lf-option>'
            "</lf-options>",
        },
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "regions",
            "action": "choose",
            "detail": {"value": ["east"]},
        },
    )
    selecting = state_json(page_dir)
    assert [item["widget"] for item in obligations_on_user(selecting)] == ["regions"]
    assert owed(selecting) == []
    assert selecting["workflows"] == []
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == []
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    answered = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "regions",
            "action": "answer",
            "detail": {},
        },
    )
    completed = state_json(page_dir)
    assert obligations_on_user(completed) == []
    assert [item["input"] for item in owed(completed)] == [answered["id"]]
    cleanup_model.prompt_turn("s1")
    receive_through(page_dir, last_deliverable_seq(page_dir))
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    blocked = json.loads(capsys.readouterr().out)
    assert "decision" not in blocked
    assert "1 acknowledged user update with no answer" in continued(blocked)
    assert answered["id"] in continued(blocked)

    append_carried_log_record(
        page_dir,
        {"kind": "undo", "author": "user", "undoes": answered["id"]},
    )
    resumed = state_json(page_dir)
    assert [item["widget"] for item in obligations_on_user(resumed)] == ["regions"]
    assert owed(resumed) == []
    answered = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "regions",
            "action": "answer",
            "detail": {},
        },
    )
    assert [item["input"] for item in owed(state_json(page_dir))] == [answered["id"]]

    thread_model.post_reply(
        page_dir, {"parent": asked["id"], "responds": answered["id"]}, "East noted."
    )
    assert owed(state_json(page_dir)) == []
