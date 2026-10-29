"""Codex's App Server as Leaf drives it: the task connection's subscription and
starts, each turn's fold of its notifications into activity, reply and ending, the
reply reservation a turn holds, recovery from the provider's history, and the
private App Servers Leaf launches."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psutil
import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    _codex_delivery,
    _delivery_item,
    _observer,
    acknowledge_through,
    acknowledged_through,
    append_carried_log_record,
    append_command,
    codex_records,
    delivered_ref,
    owed_answers,
    page_state,
    publish,
    read_record,
    record_claim,
    refused_on,
    response_reference,
    served_thread,
    status_and_stream,
    take_stream_activity,
    wait_for,
    write_record,
)
from leaf_dev.commands.response_times import page_timings

from leaf import activity as activity_model
from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import codex_adapter as codex_adapter_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hook_transport as hook_transport_model
from leaf import hooks as hooks_model
from leaf import interaction_log as interaction_log_model
from leaf import leases as leases_model
from leaf import revisioning as revisioning_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf.refusals import Refused


def test_only_one_turn_reply_can_bind_the_app_server_final_message():
    """Only a sole turn-written reply binds the provider final; keep its captured address."""

    def selected(*answers):
        return codex_model.stream_reply_target(
            {
                "batches": [
                    {
                        "page": "/tmp/page",
                        "claim": None,
                        "events": [
                            {"id": f"input-{index}", "seq": index + 1, "answer": answer}
                            for index, answer in enumerate(answers)
                        ],
                    }
                ],
            }
        )

    reply = {
        "kind": "reply",
        "parent": "thread-1",
        "responds": "event-1",
        "ref": "ref:event-1",
    }
    turn = {**reply, "writer": "turn"}
    markup = {"kind": "markup", "action": "event-2"}
    expected = {
        **turn,
        "page": "/tmp/page",
        "claim": None,
        "input": {"id": "input-0", "seq": 1},
    }
    assert selected(turn) == expected
    assert selected(reply) is None
    assert selected(markup) is None
    assert selected(turn, markup) == expected
    assert selected(turn, {**turn, "parent": "thread-2", "responds": "event-2"}) is None


@pytest.fixture
def codex_app_server(app_server):
    """A WebSocket App Server that emits two turns when the test advances it.

    After the second turn it reads whatever else the observer sends until the
    observer closes the connection, so `observer_replies` is complete once `closed`
    is set: an answer to the approval request, which only Codex's own client may
    give, would be among them."""
    received = []
    observer_replies = []
    first_turn = threading.Event()
    second_turn = threading.Event()
    closed = threading.Event()

    def handle(socket):
        initialize = json.loads(socket.recv())
        received.append(initialize)
        socket.send(json.dumps({"id": initialize["id"], "result": {}}))
        received.append(json.loads(socket.recv()))
        resume = json.loads(socket.recv())
        received.append(resume)
        socket.send(
            json.dumps(
                {
                    "id": resume["id"],
                    "result": {
                        "thread": {
                            "id": "codex-thread",
                            "status": {"type": "idle"},
                            "turns": [],
                        }
                    },
                }
            )
        )
        first_turn.wait(timeout=STATED_TIMEOUT)
        socket.send(
            json.dumps(
                {
                    "method": "turn/started",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {
                            "id": "turn-live",
                            "items": [],
                            "status": "inProgress",
                        },
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "turn-live",
                        "startedAtMs": 1_000,
                        "item": {
                            "id": "command-live",
                            "type": "commandExecution",
                            "command": "uv run pytest tests",
                            "commandActions": [],
                            "cwd": "/work",
                            "status": "inProgress",
                        },
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "item/commandExecution/requestApproval",
                    "id": 42,
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "turn-live",
                        "itemId": "command-live",
                        "startedAtMs": 0,
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {"id": "turn-live", "items": [], "status": "completed"},
                    },
                }
            )
        )
        second_turn.wait(timeout=STATED_TIMEOUT)
        socket.send(
            json.dumps(
                {
                    "method": "turn/started",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {
                            "id": "turn-next",
                            "items": [],
                            "status": "inProgress",
                        },
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {"id": "turn-next", "items": [], "status": "completed"},
                    },
                }
            )
        )
        try:
            for message in socket:
                observer_replies.append(json.loads(message))
        finally:
            closed.set()

    yield (
        app_server(handle),
        received,
        observer_replies,
        first_turn,
        second_turn,
        closed,
    )
    # Released here rather than left to the server's own stop, which would otherwise
    # wait out the handler's deadline on every test that used this.
    first_turn.set()
    second_turn.set()


def test_app_server_delivery_id_reads_only_canonical_delivery_inputs():
    pointer = delivery_model.delivery_pointer_prompt("aaaaaaaa")
    invalid_pointer = delivery_model.delivery_pointer_prompt("../status")
    payload = {
        "format": delivery_model.DELIVERY.format,
        "id": "bbbbbbbb",
        "batches": [],
    }

    def started_turn(item):
        return {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn", "items": [item], "status": "inProgress"},
            },
        }

    def started_item(item):
        return {
            "method": "item/started",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn",
                "startedAtMs": 0,
                "item": item,
            },
        }

    def said(text):
        return {
            "id": "said",
            "type": "userMessage",
            "content": [{"type": "text", "text": text}],
        }

    delivery = {
        "id": "delivery",
        "type": "functionCallOutput",
        "name": "leaf_delivery",
        "output": json.dumps(payload),
    }
    assert codex_model.app_server_delivery_id(started_turn(said(pointer))) == "aaaaaaaa"
    assert (
        codex_model.app_server_delivery_id(started_item(said(invalid_pointer))) is None
    )
    assert codex_model.app_server_delivery_id(started_turn(delivery)) == "bbbbbbbb"
    assert codex_model.app_server_delivery_id(started_item(said(pointer))) == "aaaaaaaa"
    assert (
        codex_model.app_server_delivery_id(
            started_turn(said(pointer + "\nPlease do this."))
        )
        is None
    )


def test_app_server_events_report_semantic_codex_progress():
    events = codex_model.AppServerEvents("codex-thread", "turn-live")

    assert events.read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-live", "items": [], "status": "inProgress"},
            },
        }
    ) == {"turn": "turn-live", "activity": {"kind": "working"}}
    assert events.read(
        {
            "method": "turn/plan/updated",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "plan": [
                    {"step": "Inspect the page", "status": "completed"},
                    {"step": "Run the browser checks", "status": "inProgress"},
                ],
            },
        }
    ) == {
        "turn": "turn-live",
        "activity": {"kind": "working", "detail": "Run the browser checks"},
    }
    # The turn's first agent message is its opening, which the reply stream posts as
    # progress, its own words alone; the commentary that follows it is working narration
    # and stays private.
    assert events.read(
        {
            "method": "item/completed",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "completedAtMs": 900,
                "item": {
                    "id": "opening-live",
                    "type": "agentMessage",
                    "phase": "commentary",
                    "text": "Checking the page now.",
                },
            },
        }
    ) == {
        "turn": "turn-live",
        "item": {
            "id": "opening-live",
            "type": "agentMessage",
            "state": "completed",
            "atMs": 900,
        },
        "activity": {"kind": "working"},
        "message": {
            "item": "opening-live",
            "phase": "commentary",
            "text": "Checking the page now.",
            "complete": True,
        },
        "opening": "Checking the page now.",
    }
    assert events.read(
        {
            "method": "item/started",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "startedAtMs": 1_000,
                "item": {
                    "id": "command-live",
                    "type": "commandExecution",
                    "command": "uv run pytest tests",
                    "commandActions": [],
                    "cwd": "/work",
                    "status": "inProgress",
                },
            },
        }
    ) == {
        "turn": "turn-live",
        "item": {
            "id": "command-live",
            "type": "commandExecution",
            "state": "started",
            "atMs": 1_000,
        },
        "activity": {"kind": "tool", "detail": "Running uv run pytest tests"},
    }
    assert events.read(
        {
            "method": "item/commandExecution/outputDelta",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "itemId": "command-live",
                "delta": ".",
            },
        }
    ) == {
        "turn": "turn-live",
        "activity": {"kind": "tool", "detail": "Running uv run pytest tests"},
    }
    assert events.read(
        {
            "method": "item/started",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "startedAtMs": 1_100,
                "item": {
                    "id": "commentary-live",
                    "type": "agentMessage",
                    "phase": "commentary",
                    "text": "I am checking the implementation.",
                },
            },
        }
    ) == {
        "turn": "turn-live",
        "item": {
            "id": "commentary-live",
            "type": "agentMessage",
            "state": "started",
            "atMs": 1_100,
        },
    }
    assert (
        events.read(
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "codex-thread",
                    "turnId": "turn-live",
                    "itemId": "commentary-live",
                    "delta": " Next I will run tests.",
                },
            }
        )
        is None
    )
    assert events.read(
        {
            "method": "item/completed",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "completedAtMs": 1_200,
                "item": {
                    "id": "commentary-live",
                    "type": "agentMessage",
                    "phase": "commentary",
                    "text": "I am checking the implementation. Next I will run tests.",
                },
            },
        }
    ) == {
        "turn": "turn-live",
        "item": {
            "id": "commentary-live",
            "type": "agentMessage",
            "state": "completed",
            "atMs": 1_200,
            "durationMs": 100,
        },
    }
    reply_delta = events.read(
        {
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "itemId": "message-live",
                "delta": "The page is ready for review.",
            },
        }
    )
    delta_text = reply_delta["message"].pop("text")
    assert delta_text.endswith("The page is ready for review.")
    assert "I am checking the implementation." not in delta_text
    assert "Next I will run tests." not in delta_text
    assert reply_delta == {
        "turn": "turn-live",
        "activity": {"kind": "replying"},
        "message": {
            "item": "message-live",
            "phase": None,
            "complete": False,
        },
    }
    assert events.read(
        {
            "method": "item/tool/requestUserInput",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "itemId": "question",
                "isBlocking": True,
                "questions": [],
            },
            "id": 1,
        }
    ) == {"turn": "turn-live", "activity": {"kind": "awaiting_input"}}
    completed_reply = events.read(
        {
            "method": "item/completed",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "completedAtMs": 1_300,
                "item": {
                    "id": "message-live",
                    "type": "agentMessage",
                    "text": "The page is ready for review.",
                },
            },
        }
    )
    completed_text = completed_reply["message"].pop("text")
    assert completed_text.endswith("The page is ready for review.")
    assert "I am checking the implementation." not in completed_text
    assert "Next I will run tests." not in completed_text
    assert completed_reply == {
        "turn": "turn-live",
        "item": {
            "id": "message-live",
            "type": "agentMessage",
            "state": "completed",
            "atMs": 1_300,
        },
        "activity": {"kind": "awaiting_input"},
        "message": {
            "item": "message-live",
            "phase": None,
            "complete": True,
        },
    }
    assert events.read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-live", "items": [], "status": "completed"},
            },
        }
    ) == {"turn": "turn-live", "completed": "completed"}
    # A committed reply is the final answer alone; a turn that never reached one
    # commits nothing on the strength of its opening.
    opening, narration, final = (
        {"type": "agentMessage", "phase": phase, "text": text}
        for phase, text in (
            ("commentary", "Checking the page now."),
            ("commentary", "Running the browser checks."),
            ("final_answer", "The page is ready for review."),
        )
    )
    assert events.final_text({"items": [opening, narration, final]}) == final["text"]
    assert events.final_text({"items": [opening, narration]}) == ""
    # A reconnect mid-turn says the opening once an item after it shows it complete,
    # and has no answer to restore yet.
    snapshot = [{"id": "opening", **opening}, {"id": "narration", **narration}]
    restored = codex_model.AppServerEvents("codex-thread", "turn-restored")
    restored.restore_turn({"items": snapshot[:1]})
    assert restored.said_opening() == ""
    restored.restore_turn({"items": snapshot})
    assert restored.said_opening() == opening["text"]
    assert restored.said_opening() == ""
    assert events.reply_so_far({"items": snapshot}) == ""
    # Narration after a tool call is never the opening, even with no message before it.
    tool = {"type": "commandExecution", "command": "pytest"}
    assert events.final_text({"items": [tool, narration, final]}) == (
        "The page is ready for review."
    )
    late = codex_model.AppServerEvents("codex-thread", "turn-late")
    late.restore_turn({"id": "turn-late", "items": [tool]})
    assert late.read(
        {
            "method": "item/completed",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-late",
                "completedAtMs": 2_000,
                "item": {"id": "narration-late", **narration},
            },
        }
    ) == {
        "turn": "turn-late",
        "item": {
            "id": "narration-late",
            "type": "agentMessage",
            "state": "completed",
            "atMs": 2_000,
        },
    }


def test_app_server_activity_throttles_stream_deltas(monkeypatch):
    fold = codex_model.TurnFold(
        "codex-thread",
        "turn-live",
        lifecycle=cleanup_model.session_record("codex-thread"),
    )
    clock = iter([10.0, 10.1, 10.3])
    updates = []
    clears = []
    take_stream_activity(monkeypatch, updates, clears)

    with monkeypatch.context() as clock_patch:
        clock_patch.setattr(codex_model.time, "monotonic", lambda: next(clock))
        for delta in ("one", " two", " three"):
            fold.absorb(
                {
                    "method": "item/agentMessage/delta",
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "turn-live",
                        "itemId": "message-live",
                        "delta": delta,
                    },
                }
            )

    assert updates == [
        ("codex-thread", "turn-live", {"kind": "replying"}),
        ("codex-thread", "turn-live", {"kind": "replying"}),
    ]
    assert clears == []


def test_app_server_activity_keeps_waiting_and_concurrent_item_evidence():
    events = codex_model.AppServerEvents("codex-thread", "turn-live")
    events.read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-live", "items": [], "status": "inProgress"},
            },
        }
    )

    def item(method, item_id, item_type, at):
        timing = "startedAtMs" if method == "item/started" else "completedAtMs"
        return events.read(
            {
                "method": method,
                "params": {
                    "threadId": "codex-thread",
                    "turnId": "turn-live",
                    timing: at,
                    "item": {
                        "id": item_id,
                        "type": item_type,
                        "command": f"run {item_id}",
                        "commandActions": [],
                        "cwd": "/work",
                        "status": "inProgress"
                        if method == "item/started"
                        else "completed",
                    },
                },
            }
        )

    first = item("item/started", "first", "commandExecution", 1_000)
    assert first["activity"] == {"kind": "tool", "detail": "Running run first"}
    second = item("item/started", "second", "commandExecution", 1_100)
    assert second["activity"] == {"kind": "tool", "detail": "Running run second"}

    approval = events.read(
        {
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "itemId": "first",
                "startedAtMs": 0,
            },
            "id": 1,
        }
    )
    assert approval["activity"] == {"kind": "awaiting_approval"}
    heartbeat = events.read(
        {
            "method": "item/commandExecution/outputDelta",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "itemId": "first",
                "delta": "still running",
            },
        }
    )
    assert heartbeat["activity"] == {"kind": "awaiting_approval"}

    active = events.read(
        {
            "method": "thread/status/changed",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "status": {"activeFlags": [], "type": "active"},
            },
        }
    )
    assert active["activity"] == {"kind": "tool", "detail": "Running run first"}
    completed = item("item/completed", "second", "commandExecution", 1_200)
    assert completed["activity"] == {"kind": "tool", "detail": "Running run first"}
    completed = item("item/completed", "first", "commandExecution", 1_300)
    assert completed["activity"] == {"kind": "working"}

    awaiting_input = events.read(
        {
            "method": "item/tool/requestUserInput",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-live",
                "itemId": "question",
                "isBlocking": True,
                "questions": [],
            },
            "id": 1,
        }
    )
    assert awaiting_input["activity"] == {"kind": "awaiting_input"}


def test_app_server_activity_reads_only_its_own_turn():
    """A fold is one turn's, and every other turn's notifications read as nothing.

    One subscription carries every turn of the task, and a turn that started
    after this one ended, or one still reporting after it, must not move this
    turn's readings. Routing a notification to its turn is the client's; the
    fold only refuses what is not its own.
    """
    events = codex_model.AppServerEvents("codex-thread", "turn-live")
    events.read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-live", "items": [], "status": "inProgress"},
            },
        }
    )

    for message in (
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-other", "items": [], "status": "inProgress"},
            },
        },
        {
            "method": "item/reasoning/summaryTextDelta",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-other",
                "itemId": "other-reasoning",
                "delta": "another turn's thought",
                "summaryIndex": 0,
            },
        },
        {
            "method": "thread/status/changed",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-other",
                "status": {"activeFlags": ["waitingOnUserInput"], "type": "active"},
            },
        },
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-other", "status": "completed", "items": []},
            },
        },
        {
            "method": "item/started",
            "params": {
                "threadId": "another-thread",
                "turnId": "turn-live",
                "startedAtMs": 1,
                "item": {
                    "id": "elsewhere",
                    "type": "commandExecution",
                    "commandActions": [],
                    "cwd": "/work",
                    "status": "inProgress",
                    "command": "ls",
                },
            },
        },
    ):
        assert events.read(message) is None
    assert events.turn_id == "turn-live"
    assert events.active_items == {}
    assert events.waiting_kind is None

    assert events.read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-live", "status": "interrupted", "items": []},
            },
        }
    ) == {"turn": "turn-live", "completed": "interrupted"}


def test_app_server_client_stays_subscribed_between_ordinary_codex_turns(
    codex_app_server, monkeypatch, request
):
    endpoint, received, observer_replies, first_turn, second_turn, closed = (
        codex_app_server
    )
    updates = []
    clears = []
    take_stream_activity(monkeypatch, updates, clears)
    observer = codex_adapter_model.TaskConnection(endpoint, "codex-thread")
    request.addfinalizer(observer.stop)

    observer.start()
    first_turn.set()
    wait_for(
        lambda: len(clears),
        lambda count: count == 2,
        failure="the first Codex turn did not clear its stream activity",
    )

    second_turn.set()
    wait_for(
        lambda: len(clears),
        lambda count: count == 3,
        failure="the second Codex turn did not clear its stream activity",
    )
    observer.stop()
    wait_for(
        closed.is_set,
        bool,
        failure="the App Server never saw the observer close its connection",
    )

    assert [message["method"] for message in received] == [
        "initialize",
        "initialized",
        "thread/resume",
    ]
    assert received[2]["params"] == {
        "threadId": "codex-thread",
        "excludeTurns": False,
    }
    assert updates == [
        ("codex-thread", "turn-live", {"kind": "working"}),
        (
            "codex-thread",
            "turn-live",
            {"kind": "tool", "detail": "Running uv run pytest tests"},
        ),
        ("codex-thread", "turn-live", {"kind": "awaiting_approval"}),
        ("codex-thread", "turn-next", {"kind": "working"}),
    ]
    assert observer_replies == []


def test_app_server_observer_connects_over_a_private_unix_socket(
    monkeypatch, request, socket_dir, app_server
):
    socket_path = socket_dir / "app-server.sock"
    received = []
    request_headers = []
    release = threading.Event()

    def handle(socket):
        request_headers.append(socket.request.headers)
        initialize = json.loads(socket.recv())
        received.append(initialize)
        socket.send(json.dumps({"id": initialize["id"], "result": {}}))
        received.append(json.loads(socket.recv()))
        resume = json.loads(socket.recv())
        received.append(resume)
        socket.send(
            json.dumps(
                {
                    "id": resume["id"],
                    "result": {
                        "thread": {
                            "id": "codex-thread",
                            "status": {"type": "idle"},
                            "turns": [],
                        }
                    },
                }
            )
        )
        release.wait(timeout=STATED_TIMEOUT)

    endpoint = app_server(handle, socket_path)
    updates = []
    clears = []
    take_stream_activity(monkeypatch, updates, clears)
    observer = codex_adapter_model.TaskConnection(endpoint, "codex-thread")
    request.addfinalizer(observer.stop)

    # `start` returns only once the observer has resumed the task, and raises
    # otherwise, so reaching here is the readiness signal.
    observer.start()
    assert updates == []
    assert clears == [("codex-thread", None)]
    observer.stop()
    assert not observer.thread.is_alive()
    release.set()

    assert [message["method"] for message in received] == [
        "initialize",
        "initialized",
        "thread/resume",
    ]
    assert "Sec-WebSocket-Extensions" not in request_headers[0]


def test_app_server_observer_restores_the_resumed_turns_waiting_kind(
    monkeypatch, request, app_server
):
    release = threading.Event()

    def handle(socket):
        initialize = json.loads(socket.recv())
        socket.send(json.dumps({"id": initialize["id"], "result": {}}))
        socket.recv()  # initialized
        resume = json.loads(socket.recv())
        socket.send(
            json.dumps(
                {
                    "id": resume["id"],
                    "result": {
                        "thread": {
                            "id": "codex-thread",
                            "status": {
                                "type": "active",
                                "activeFlags": ["waitingOnApproval"],
                            },
                            "turns": [
                                {
                                    "id": "turn-live",
                                    "status": "inProgress",
                                    "items": [],
                                }
                            ],
                        }
                    },
                }
            )
        )
        release.wait(timeout=STATED_TIMEOUT)

    updates = []
    clears = []
    take_stream_activity(monkeypatch, updates, clears)
    observer = codex_adapter_model.TaskConnection(app_server(handle), "codex-thread")
    request.addfinalizer(observer.stop)

    observer.start()
    assert updates == [("codex-thread", "turn-live", {"kind": "awaiting_approval"})]
    assert clears == []
    observer.stop()
    release.set()


def test_a_task_connection_streams_and_commits_its_delivery_reply(
    page_dir, request, app_server, task_connection
):
    """One connection carries the turn from the start that made it to its reply.

    `thread/resume` subscribes the connection that asked, for as long as it lives,
    and `turn/start` neither subscribes nor unsubscribes, so everything this turn
    says arrives on the task subscription. The owner binds the returned turn
    before replaying notifications buffered while the start response was pending.
    """
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Can you answer here?"},
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid()),
    )
    claim = service_model.page_claim(page_dir)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(page_dir, claim["id"])
    )
    assert lease
    request.addfinalizer(lease.close)

    release = threading.Event()
    completed = threading.Event()

    def handle(socket):
        initialize = json.loads(socket.recv())
        socket.send(json.dumps({"id": initialize["id"], "result": {}}))
        socket.recv()  # initialized
        for _ in range(2):
            resume = json.loads(socket.recv())
            socket.send(
                json.dumps(
                    {
                        "id": resume["id"],
                        "result": {
                            "thread": {
                                "id": "codex-thread",
                                "status": {"type": "idle"},
                                "turns": [],
                            }
                        },
                    }
                )
            )
        start = json.loads(socket.recv())
        socket.send(
            json.dumps(
                {
                    "method": "turn/started",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {
                            "id": "leaf-turn",
                            "items": [],
                            "status": "inProgress",
                        },
                    },
                }
            )
        )
        delivery = {
            "id": "delivery",
            "type": "functionCallOutput",
            "name": "leaf_delivery",
            "namespace": None,
            "output": start["params"]["toolOutput"]["output"],
        }
        socket.send(
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "leaf-turn",
                        "startedAtMs": 1,
                        "item": delivery,
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "leaf-turn",
                        "completedAtMs": 1,
                        "item": delivery,
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "leaf-turn",
                        "startedAtMs": 1,
                        "item": {
                            "id": "answer",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "",
                        },
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "item/agentMessage/delta",
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "leaf-turn",
                        "itemId": "answer",
                        "delta": "Streaming",
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "id": start["id"],
                    "result": {
                        "turn": {
                            "id": "leaf-turn",
                            "status": "inProgress",
                            "items": [],
                            "itemsView": "notLoaded",
                        }
                    },
                }
            )
        )
        release.wait(timeout=STATED_TIMEOUT)
        answer = {
            "id": "answer",
            "type": "agentMessage",
            "phase": "final_answer",
            "text": "Streaming reply",
        }
        socket.send(
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "codex-thread",
                        "turnId": "leaf-turn",
                        "completedAtMs": 2,
                        "item": answer,
                    },
                }
            )
        )
        socket.send(
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {
                            "id": "leaf-turn",
                            "status": "completed",
                            "items": [answer],
                        },
                    },
                }
            )
        )
        completed.set()

    connection = task_connection(app_server(handle))
    assert connection.start_delivery(prepared.payload)

    streamed = wait_for(
        lambda: served_thread(page_state(page_dir)["browser"])["threads"][0]["msgs"][
            -1
        ],
        lambda message: message["text"] == "Streaming",
        failure="the streamed reply did not reach the page",
    )
    assert (streamed["pending"], streamed["parent"]) == (True, comment["id"])
    assert "stream_state" not in streamed

    release.set()
    assert completed.wait(timeout=STATED_TIMEOUT), "the delivered turn never completed"
    replies, _ = wait_for(
        lambda: (
            [
                event
                for event in events_model.read_events(page_dir)
                if event["kind"] == "reply"
            ],
            read_record(page_dir / "stream.json"),
        ),
        lambda reading: bool(reading[0]) and reading[1]["reply"] is None,
        failure="the streamed reply was not committed after completion",
    )

    assert [
        (reply["parent"], reply["responds"], reply["text"], reply["attempt"])
        for reply in replies
    ] == [
        (
            comment["id"],
            comment["id"],
            "Streaming reply",
            service_model.delivery_reply_attempt(prepared.payload["id"]),
        )
    ]
    [thread] = served_thread(page_state(page_dir)["browser"])["threads"]
    assert thread["msgs"][-1]["id"] == replies[0]["id"]


def _joined_items(payload: dict, join: str) -> list[dict]:
    """A shared turn's items in the order App Server records them (codex-cli
    0.160.0): the user's follow-up ahead of the delivery Leaf's start steered in,
    or the delivery ahead of the message the user steered into Leaf's turn."""
    user = {
        "id": "follow-up",
        "type": "userMessage",
        "content": [{"type": "text", "text": "Reply: USER FOLLOW-UP"}],
    }
    opening = {
        "id": "opening",
        "type": "agentMessage",
        "phase": "commentary",
        "text": "USER FOLLOW-UP",
    }
    answer = {
        "id": "answer",
        "type": "agentMessage",
        "phase": "final_answer",
        "text": "USER FOLLOW-UP",
    }
    delivery = _delivery_item(payload)
    if join == "start-joins-follow-up":
        return [user, opening, delivery, answer]
    return [delivery, opening, user, answer]


def _offered_again(session_id: str) -> list[dict]:
    return [
        delivery_model.read_delivery(path.stem)
        for path, record in codex_model.delivery_records(session_id)
        if isinstance(record, codex_model.Offering)
    ]


@pytest.mark.parametrize("ending", ["completed", "interrupted"])
@pytest.mark.parametrize("join", ["start-joins-follow-up", "user-steers-in"])
def test_a_turn_that_shares_a_user_message_leaves_the_delivery_owed(
    page_dir, request, app_server, task_connection, join, ending
):
    """A delivery turn whose answer was also written for the user is not its reply.

    `turn/start` on a running turn steers into it and answers with its id. A
    follow-up the user queued in the Codex TUI starts just after the turn before
    it ends, while App Server still reads idle, so Leaf's idle check can pass and
    its start join the follow-up's turn; a user can also steer into Leaf's turn.
    Either way the turn's final message answers the user's message too. Leaf posts
    none of it, nor the opening of a turn the user opened, and withholds its draft
    so Stop doesn't continue the turn over the update. A completed
    turn offers the comment again as a correction; one the user interrupted leaves
    it owed and shows the turn stopped, as any turn that ends without an answer
    does.
    """
    prepared = _codex_delivery(page_dir, "Why here?")
    target = codex_model.stream_reply_target(prepared.payload)
    items = _joined_items(prepared.payload, join)
    # The task's watcher, which the Stop hook asks whether the reply will commit.
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(page_dir, "codex-thread")
    )
    assert lease
    request.addfinalizer(lease.close)
    release = threading.Event()
    completed = threading.Event()

    def send(socket, method, params):
        socket.send(
            json.dumps(
                {"method": method, "params": {"threadId": "codex-thread", **params}}
            )
        )

    def handle(socket):
        initialize = json.loads(socket.recv())
        socket.send(json.dumps({"id": initialize["id"], "result": {}}))
        socket.recv()  # initialized
        for _ in range(2):
            resume = json.loads(socket.recv())
            socket.send(
                json.dumps(
                    {
                        "id": resume["id"],
                        "result": {
                            "thread": {
                                "id": "codex-thread",
                                "status": {"type": "idle"},
                                "turns": [],
                            }
                        },
                    }
                )
            )
        start = json.loads(socket.recv())
        send(
            socket,
            "turn/started",
            {"turn": {"id": "shared-turn", "status": "inProgress", "items": []}},
        )
        for item in items:
            for state in ("started", "completed"):
                send(
                    socket,
                    f"item/{state}",
                    {"turnId": "shared-turn", f"{state}AtMs": 1, "item": item},
                )
        socket.send(
            json.dumps(
                {
                    "id": start["id"],
                    "result": {"turn": {"id": "shared-turn", "status": "inProgress"}},
                }
            )
        )
        release.wait(timeout=STATED_TIMEOUT)
        send(
            socket,
            "turn/completed",
            {"turn": {"id": "shared-turn", "status": ending, "items": items}},
        )
        completed.set()

    connection = task_connection(app_server(handle))
    assert connection.start_delivery(prepared.payload)
    wait_for(
        lambda: connection.turns.get("shared-turn"),
        lambda fold: fold is not None and fold.events.joined,
        failure="the shared turn's user message was not read",
    )
    # While the turn runs it holds the update, and the Stop hook reads the turn as
    # done with it, so it lets the turn end on its own answer.
    assert thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )
    [plan] = hook_transport_model.read_plans("codex-thread")
    assert plan.owed == []
    # A dropped connection leaves the draft withheld, and a long turn doesn't
    # age it, since nothing renews a withheld draft.
    connection.turns["shared-turn"].reply_stream.disconnect()
    stream = read_record(page_dir / "stream.json")
    stream["reply"]["updated_at"] = "2000-01-01T00:00:00+00:00"
    write_record(page_dir / "stream.json", stream)
    [plan] = hook_transport_model.read_plans("codex-thread")
    assert plan.owed == []
    release.set()
    assert completed.wait(timeout=STATED_TIMEOUT), "the shared turn never completed"
    # The fold releases the reply, then offers a completed turn's correction.
    wait_for(
        lambda: (
            thread_model.delivery_reply_reserved(
                "codex-thread", prepared.payload["id"], target
            ),
            _offered_again("codex-thread"),
        ),
        lambda reading: not reading[0] and (ending != "completed" or reading[1]),
        failure="the joined turn was not settled",
    )

    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    if join == "start-joins-follow-up":
        assert replies == []
    else:
        # Leaf's own turn opened on the delivery, so its opening was Leaf's.
        assert [(reply["text"], reply.get("ephemeral")) for reply in replies] == [
            ("USER FOLLOW-UP", True)
        ]
    draft = read_record(page_dir / "stream.json")["reply"]
    corrections = _offered_again("codex-thread")
    if ending == "interrupted":
        # Ended as any unanswered turn does: the update stays owed, shown stopped.
        assert (draft["state"], draft["text"]) == ("interrupted", "")
        assert corrections == []
        return
    assert draft is None
    [correction] = corrections
    assert correction["correction"]["delivery"] == prepared.payload["id"]
    assert delivery_model.stream_reply_target(correction) == target


def test_a_joined_turn_read_back_from_history_is_not_the_reply(page_dir):
    """A joined turn that ended while nobody read it settles the same way when
    the provider's history brings it back."""
    prepared = _codex_delivery(page_dir, "Why here?")
    target = codex_model.stream_reply_target(prepared.payload)
    terminal = {
        "id": "shared-turn",
        "status": "completed",
        "items": _joined_items(prepared.payload, "start-joins-follow-up"),
    }
    assert cleanup_model.start_session_turn(
        "codex-thread", "shared-turn", cleanup_model.session_record("codex-thread")
    )

    assert _observer()._reconcile(terminal)

    assert [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ] == []
    assert not thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )
    [correction] = _offered_again("codex-thread")
    assert correction["correction"]["delivery"] == prepared.payload["id"]


def test_a_quiet_stream_is_a_fault_only_once_its_silence_outlasts_its_bound():
    """Separate an App Server that is thinking from one that stopped delivering.

    `recv` reports every idle second the same way, so the reading that tells the two
    apart is how long the silence has run against the bound its client gave. The
    website gives one because nobody is at that task and a turn nothing will finish
    holds a user on a page that says the agent is working. The adapter gives none:
    its task is a terminal someone is sitting at, and a turn waiting on an approval
    is silent for exactly as long as they take to answer it.
    """

    class Socket:
        def recv(self, timeout):
            raise TimeoutError

    socket = Socket()
    long_ago = time.monotonic() - 3600
    assert codex_model.recv_notification(socket, time.monotonic(), 120.0) is None
    assert codex_model.recv_notification(socket, long_ago, None) is None
    with pytest.raises(TimeoutError):
        codex_model.recv_notification(socket, long_ago, 120.0)


def test_a_queued_app_server_turn_uses_its_delivery_id_for_the_final_reply(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this next"},
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid()),
    )
    client = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "codex-thread")
    pointer = {
        "id": "queued-input",
        "type": "userMessage",
        "content": [{"type": "text", "text": prepared.prompt}],
    }

    client._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "queued-turn",
                    "status": "inProgress",
                    "items": [pointer],
                },
            },
        }
    )
    assert client.turns["queued-turn"].reply_stream is not None
    client._read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "queued-turn",
                    "status": "completed",
                    "items": [
                        {
                            "id": "answer",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "The queued reply",
                        }
                    ],
                },
            },
        }
    )

    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [(reply["responds"], reply["text"]) for reply in replies] == [
        (comment["id"], "The queued reply")
    ]


def test_an_observed_queue_pointer_leaves_its_reply_to_leaf_reply(page_dir):
    """A pointer frozen for the queue names a plain `reply`, and that is what its
    agent is told to write. The observer still opens the turn it lands in, but
    binds nothing to the turn's messages, so `leaf thread reply` answers it rather than
    refusing it as the turn's."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this next"},
    )
    with service_model.PageTransaction(page_dir) as transaction:
        transaction.take_claim(
            harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
        )
        path, _, _ = codex_model.append_batch(
            "codex-thread",
            page_dir,
            transaction,
            service_model.unacknowledged(transaction.events, transaction.cursor),
        )
    queued = codex_model.offer_delivery(
        path, codex_model.read_record(path), transport="queue"
    )
    [event] = queued.payload["batches"][0]["events"]
    assert event["answer"]["kind"] == "reply"

    client = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "codex-thread")
    client._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "queued-turn",
                    "status": "inProgress",
                    "items": [
                        {
                            "id": "queued-input",
                            "type": "userMessage",
                            "content": [{"type": "text", "text": queued.prompt}],
                        }
                    ],
                },
            },
        }
    )
    assert client.turns["queued-turn"].reply_stream is None
    [workflow] = owed_answers(page_dir)
    assert workflow["stage"] == "picked_up"
    assert workflow["answer"] == {
        "kind": "reply",
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": delivered_ref(page_dir, comment["id"]),
    }

    posted = thread_model.post_reply(
        page_dir,
        {"responds": comment["id"]},
        "Answered with leaf thread reply",
        identity={"session": "codex-thread"},
    )
    assert posted["responds"] == comment["id"]


@pytest.mark.parametrize("status", ["inProgress", "completed"])
def test_reconnect_binds_a_delivery_a_followed_turn_carried_unseen(page_dir, status):
    """A turn the observer follows can name its delivery while nobody is listening.

    The observer saw the turn start, which names no delivery, and lost its
    connection before the delivery's item arrived. The resumed snapshot is the
    only place that item is ever seen, so the turn's answer is bound from it,
    whether the turn is still running or ended during the disconnect.
    """
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer across a reconnect"},
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid()),
    )
    observer = _observer()
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "leaf-turn", "items": [], "status": "inProgress"},
            },
        }
    )
    observer._disconnect_turns()

    observer._resume(
        {
            "status": {"type": "active", "activeFlags": []}
            if status == "inProgress"
            else {"type": "idle"},
            "turns": [
                {
                    "id": "leaf-turn",
                    "status": status,
                    "items": [
                        {
                            "id": "delivery",
                            "type": "functionCallOutput",
                            "name": "leaf_delivery",
                            "output": json.dumps(prepared.payload),
                        },
                        {
                            "id": "answer",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Answered across the reconnect",
                        },
                    ],
                }
            ],
        }
    )

    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Accepted,
    )
    replies = [
        (event["responds"], event["text"])
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    if status == "inProgress":
        assert observer.turns["leaf-turn"].reply_stream is not None
        assert replies == []
    else:
        assert observer.turns == {}
        assert replies == [(comment["id"], "Answered across the reconnect")]


def test_reconnect_recovers_a_completed_delivery_reply(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer during reconnect"},
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid()),
    )
    client = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "codex-thread")

    client._resume(
        {
            "turns": [
                {
                    "id": "completed-while-disconnected",
                    "status": "completed",
                    "items": [
                        {
                            "id": "delivery",
                            "type": "functionCallOutput",
                            "name": "leaf_delivery",
                            "output": json.dumps(prepared.payload),
                        },
                        {
                            "id": "answer",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Recovered reply",
                        },
                    ],
                },
                {
                    "id": "current-turn",
                    "status": "inProgress",
                    "items": [
                        {
                            "id": "current-answer",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Current",
                        }
                    ],
                },
            ]
        }
    )

    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [(reply["responds"], reply["text"]) for reply in replies] == [
        (comment["id"], "Recovered reply")
    ]
    # The recovered turn is committed and gone; the user's own running turn is
    # followed, and binds no reply.
    assert set(client.turns) == {"current-turn"}
    assert client.turns["current-turn"].reply_stream is None
    update = client.turns["current-turn"].events.read(
        {
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "codex-thread",
                "turnId": "current-turn",
                "itemId": "current-answer",
                "delta": " answer",
            },
        }
    )
    assert update["message"]["text"] == "Current answer"


def test_a_completed_stream_reply_survives_the_claim_advancing(page_dir):
    revisioning_model.activate_source(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer the first turn"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": response_reference(page_dir, comment),
    }
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "turn-1", "delivery-1", target
    )
    stream.restore(" \n")
    [initial] = page_timings(page_dir, since=None, until=datetime.now(UTC))["samples"]
    assert "first_reply" not in initial["milestones"]
    for text in ("I am checking.", "I am checking the report."):
        stream.update(
            {
                "message": {
                    "item": "answer",
                    "phase": "final_answer",
                    "text": text,
                    "complete": True,
                }
            }
        )
    [thread] = served_thread(page_state(page_dir)["browser"])["threads"]
    assert thread["msgs"][-1]["provisional"]
    assert thread["msgs"][-1]["text"] == "I am checking the report."
    [marker] = interaction_log_model.read_interactions(
        page_dir, types=("reply_stream_words",)
    )
    assert marker["input_id"] == comment["id"]
    assert marker["attempt"] == stream.attempt
    assert "text" not in marker
    [before] = page_timings(page_dir, since=None, until=datetime.now(UTC))["samples"]
    assert before["first_reply_kind"] == "stream"
    assert before["milestones"]["first_reply"]["turn"] == "turn-1"
    assert "answered" not in before["milestones"]
    assert "send_to_visible" not in before["milestones"]
    cleanup_model.close_session_turn("codex-thread", "turn-1")
    cleanup_model.prompt_turn("codex-thread", "turn-2")

    assert stream.finish("completed", "First turn reply") is None

    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [(reply["responds"], reply["text"]) for reply in replies] == [
        (comment["id"], "First turn reply")
    ]
    assert service_model.page_claim(page_dir)["turn"] == "turn-2"
    [after] = page_timings(page_dir, since=None, until=datetime.now(UTC))["samples"]
    assert after["milestones"]["first_reply"] == before["milestones"]["first_reply"]
    assert after["milestones"]["answered"]["event_id"] == replies[0]["id"]


def test_a_stream_reply_finishes_when_its_diagnostic_sink_is_unwritable(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this input"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    stream = codex_model.AppServerReplyStream(
        "codex-thread",
        "turn-1",
        "delivery-1",
        {
            "page": str(page_dir),
            "parent": comment["id"],
            "responds": comment["id"],
            "ref": response_reference(page_dir, comment),
        },
    )
    # The diagnostic file cannot be opened, while normal page writes remain valid.
    sink = page_dir / interaction_log_model.INTERACTIONS_FILE
    sink.unlink(missing_ok=True)
    sink.mkdir()
    assert stream.restore("The complete answer.")
    reply = read_record(page_dir / "stream.json")["reply"]
    assert reply["text"] == "The complete answer."
    assert reply["responds"] == comment["id"]

    assert stream.finish("completed", "The complete answer.") is None
    [answer] = thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    )
    assert answer["text"] == "The complete answer."
    assert read_record(page_dir / "stream.json")["reply"] is None


def test_an_interrupted_stream_reply_finishes_after_the_claim_advances(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer the first turn"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": response_reference(page_dir, comment),
    }
    thread_model.reserve_delivery_reply("codex-thread", "delivery-1", target)
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "turn-1", "delivery-1", target
    )
    stream.update(
        {
            "message": {
                "item": "answer",
                "phase": "final_answer",
                "text": "Partial answer",
                "complete": True,
            }
        }
    )
    cleanup_model.close_session_turn("codex-thread", "turn-1")
    cleanup_model.prompt_turn("codex-thread", "turn-2")

    assert stream.finish("interrupted") is None

    stream_state = read_record(page_dir / "stream.json")
    assert (stream_state["reply"]["text"], stream_state["reply"]["state"]) == (
        "Partial answer",
        "interrupted",
    )
    assert stream_state["reply_reservations"] == {}


def test_provider_reservation_refuses_unaddressed_competing_writes(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Move this reply too"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": response_reference(page_dir, comment),
    }
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "turn-1", "delivery-1", target
    )
    stream.update(
        {
            "message": {
                "item": "answer",
                "phase": "final_answer",
                "text": "Transcript closeout",
                "complete": True,
            }
        }
    )
    with pytest.raises(Refused) as refused:
        thread_model.post_reply(
            page_dir,
            {"parent": comment["id"], "responds": comment["id"]},
            "Anchored answer",
            identity={"agent": "Codex", "session": "codex-thread"},
        )
    assert refused_on(refused.value).code == "reserved-answer"
    assert stream.finish("completed", "Transcript closeout") is None
    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [reply["text"] for reply in replies] == ["Transcript closeout"]
    assert read_record(page_dir / "stream.json")["reply"] is None


def test_a_delivery_reserves_its_final_before_provider_execution(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this once"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": response_reference(page_dir, comment),
    }

    thread_model.reserve_delivery_reply("codex-thread", "delivery-1", target)

    with pytest.raises(Refused) as refused:
        thread_model.post_reply(
            page_dir,
            {"parent": comment["id"], "responds": comment["id"]},
            "Competing reply",
            identity={"agent": "Codex", "session": "codex-thread"},
        )
    assert refused_on(refused.value).code == "reserved-answer"

    with pytest.raises(RuntimeError, match="already reserved by another delivery"):
        thread_model.reserve_delivery_reply("codex-thread", "delivery-2", target)


def test_a_delivery_bound_final_cannot_append_after_claim_transfer(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    stream = codex_model.AppServerReplyStream(
        "codex-thread",
        "turn-1",
        "delivery-1",
        {
            "page": str(page_dir),
            "parent": comment["id"],
            "responds": comment["id"],
            "ref": response_reference(page_dir, comment),
        },
    )
    claim = service_model.page_claim(page_dir)
    record_claim(page_dir, **{**claim, "id": "successor-thread", "agent": "Successor"})

    error = stream.finish("completed", "Stale answer")

    assert isinstance(error, delivery_model.ReceiptRefused)
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )

    successor = {
        "page": str(page_dir),
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": response_reference(page_dir, comment),
    }
    thread_model.reserve_delivery_reply("successor-thread", "delivery-2", successor)
    with service_model.PageTransaction(page_dir) as page:
        assert page.stream["reply_reservations"][comment["id"]] == {
            "session": "successor-thread",
            "attempt": service_model.delivery_reply_attempt("delivery-2"),
            "turn": "turn-1",
        }


def test_a_streamed_final_rejects_invalid_source_without_stranding_the_draft(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Change this page"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": response_reference(page_dir, comment),
    }
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "turn-1", "delivery-1", target
    )
    (page_dir / "index.html").write_text("<main>unfinished")

    error = stream.finish("completed", "I made the change.")

    assert isinstance(error, Refused)
    reply = read_record(page_dir / "stream.json")["reply"]
    assert (reply["state"], reply["text"], reply["settles"]) == (
        "failed",
        "I made the change.",
        False,
    )
    [marker] = interaction_log_model.read_interactions(
        page_dir, types=("reply_stream_words",)
    )
    assert marker["input_id"] == comment["id"]
    assert marker["attempt"] == stream.attempt
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )


def test_partial_text_is_not_committed_without_a_completed_final(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    stream = codex_model.AppServerReplyStream(
        "codex-thread",
        "turn-1",
        "delivery-1",
        {
            "page": str(page_dir),
            "parent": comment["id"],
            "responds": comment["id"],
            "ref": response_reference(page_dir, comment),
        },
    )
    stream.update(
        {
            "message": {
                "item": "answer",
                "phase": "final_answer",
                "text": "Only a partial",
                "complete": False,
            }
        }
    )

    assert stream.finish("completed", "") is None

    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )
    reply = read_record(page_dir / "stream.json")["reply"]
    assert (reply["state"], reply["text"], reply["settles"]) == (
        "partial",
        "Only a partial",
        False,
    )


def test_a_stream_reply_refreshes_its_lease_without_changing_its_message_time(
    page_dir, monkeypatch
):
    created = datetime.now().astimezone()
    refreshed = created + timedelta(minutes=10)
    moments = iter((created.isoformat(), refreshed.isoformat()))
    monkeypatch.setattr(service_model, "now_iso", lambda: next(moments))
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")

    with service_model.PageTransaction(page_dir) as page:
        page.set_stream_reply(
            "codex-thread",
            "turn-1",
            {"parent": "comment", "responds": "comment"},
            service_model.delivery_reply_attempt("delivery-1"),
            None,
            "First visible",
            "active",
        )
        page.set_stream_reply(
            "codex-thread",
            "turn-1",
            {"parent": "comment", "responds": "comment"},
            service_model.delivery_reply_attempt("delivery-1"),
            "answer",
            "Now visible",
            "active",
        )
        reply = page.stream["reply"]

    [marker] = interaction_log_model.read_interactions(
        page_dir, types=("reply_stream_words",)
    )
    assert marker["input_id"] == "comment"
    assert marker["attempt"] == reply["attempt"]
    assert marker["turn"] == "turn-1"
    assert "text" not in marker
    assert reply["text"] == "Now visible"
    assert reply["ts"] == created.isoformat()
    assert reply["updated_at"] == refreshed.isoformat()
    projected = activity_model.canonical_stream_reply(
        {"claim_session": "codex-thread", "listening": True},
        (created + timedelta(minutes=16)).isoformat(),
        reply,
    )
    assert projected["state"] == "active"


def _obligations(page_dir) -> list[dict]:
    return owed_answers(page_dir)


def test_a_turn_that_ended_unseen_is_recorded_without_reopening(page_dir):
    """A delivery accepted from a snapshot names its turn and opens nothing.

    The turn took the delivery and ended while the observer's connection was
    down, and the session's turn has been closed since. Recording the pickup
    against that ended turn must not open it again, since nothing will see it
    end a second time.
    """
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1)
    )
    publish(page_dir)
    action = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan-choice",
            "action": "answer",
            "detail": {},
        },
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    )
    assert codex_model.stream_reply_target(prepared.payload) is None
    cleanup_model.close_session_turn("codex-thread")
    closed = service_model.page_claim(page_dir)

    _observer()._resume(
        {
            "status": {"type": "idle"},
            "turns": [
                {
                    "id": "ended-turn",
                    "status": "completed",
                    "items": [_delivery_item(prepared.payload)],
                }
            ],
        }
    )

    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Accepted,
    )
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["events"], pickup["turn"]) == ([action["id"]], "ended-turn")
    assert service_model.page_claim(page_dir) == closed


def test_a_reply_reservation_lapses_when_a_turn_it_does_not_name_opens(page_dir):
    """A reply reservation hands its move's answer to the turn it names, and no other.

    The observer bound the delivery's reply to its turn and then lost the
    connection with the turn still running. While that turn is the claim's, the
    turn's own messages owe the answer. Once a later turn opens without the
    App Server client taking the reservation over, nothing says those messages will be
    committed, so the move is answered with `leaf thread reply` again, and a
    client that reconnects and commits the delivery turn's final message after
    all yields to that answer.
    """
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Answer me"}
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    )
    target = codex_model.stream_reply_target(prepared.payload)
    thread_model.reserve_delivery_reply("codex-thread", prepared.payload["id"], target)
    observer = _observer()
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "delivery-turn",
                    "items": [_delivery_item(prepared.payload)],
                    "status": "inProgress",
                },
            },
        }
    )
    observer._disconnect_turns()
    [owed] = _obligations(page_dir)
    assert owed["answer"]["writer"] == "turn"

    cleanup_model.prompt_turn("codex-thread", "later-turn")

    [owed] = _obligations(page_dir)
    assert owed["answer"] == {
        "kind": "reply",
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": delivered_ref(page_dir, comment["id"]),
    }
    posted = thread_model.post_reply(
        page_dir,
        {"responds": comment["id"]},
        "Answered in the later turn",
        identity={"session": "codex-thread"},
    )
    assert posted["responds"] == comment["id"]

    observer._resume(
        {
            "status": {"type": "idle"},
            "turns": [
                {
                    "id": "delivery-turn",
                    "status": "completed",
                    "items": [
                        _delivery_item(prepared.payload),
                        {
                            "id": "answer",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "The delivery turn's final",
                        },
                    ],
                }
            ],
        }
    )
    assert [
        event["text"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ] == ["Answered in the later turn"]


def test_a_reply_reservation_lapses_when_its_turn_closes(page_dir):
    """A turn that has ended writes nothing more, so its reservation lapses with it.

    The observer bound the delivery's reply to its turn and then lost the
    connection. When the session's turn closes without an App Server client committing the
    turn's final message, nothing says one will, so the move is answered with
    `leaf thread reply` again.
    """
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Answer me"}
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    )
    target = codex_model.stream_reply_target(prepared.payload)
    thread_model.reserve_delivery_reply("codex-thread", prepared.payload["id"], target)
    observer = _observer()
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "delivery-turn",
                    "items": [_delivery_item(prepared.payload)],
                    "status": "inProgress",
                },
            },
        }
    )
    observer._disconnect_turns()
    [owed] = _obligations(page_dir)
    assert owed["answer"]["writer"] == "turn"

    cleanup_model.close_session_turn("codex-thread", "delivery-turn")

    [owed] = _obligations(page_dir)
    assert owed["answer"] == {
        "kind": "reply",
        "parent": comment["id"],
        "responds": comment["id"],
        "ref": delivered_ref(page_dir, comment["id"]),
    }
    posted = thread_model.post_reply(
        page_dir,
        {"responds": comment["id"]},
        "Answered after the turn ended",
        identity={"session": "codex-thread"},
    )
    assert posted["responds"] == comment["id"]


def test_the_prompt_hook_and_the_observer_open_one_codex_turn(page_dir, capsys):
    """Codex names each turn to its hooks and its App Server alike.

    The prompt hook opens the turn and records the acknowledged move it re-presents
    as opened in it; the observer then sees the same turn start. Both name one
    turn, so the move reads as handled by the turn running now rather than left
    behind by one the observer's opening replaced.
    """
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Handle me"}
    )
    acknowledge_through(page_dir, events_model.read_events(page_dir)[-1]["seq"])
    cleanup_model.close_session_turn("codex-thread")

    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "codex-thread",
            "turn_id": "codex-turn",
        },
    )
    capsys.readouterr()
    _observer()._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "codex-turn", "items": [], "status": "inProgress"},
            },
        }
    )

    assert service_model.page_claim(page_dir)["turn"] == "codex-turn"
    [owed] = _obligations(page_dir)
    assert (owed["stage"], owed["condition"]) == ("picked_up", None)


def test_reconnect_closes_a_completed_stream_reservation(page_dir):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "turn-complete")
    observer = _observer()
    finished = []

    class Stream:
        def finish(self, state, text):
            finished.append((state, text))

    fold = codex_model.TurnFold(
        "codex-thread",
        "turn-complete",
        lifecycle=cleanup_model.session_record("codex-thread"),
    )
    fold.reply_stream = Stream()
    observer.turns = {"turn-complete": fold}
    observer.running = "turn-complete"

    observer._resume(
        {
            "turns": [
                {
                    "id": "turn-complete",
                    "status": "completed",
                    "items": [
                        {
                            "id": "answer",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Done.",
                        }
                    ],
                }
            ]
        }
    )

    assert finished == [("completed", "Done.")]
    assert service_model.page_claim(page_dir)["turn_closed"] is not None
    assert observer.turns == {}
    assert not observer.working()


@pytest.fixture
def task_connection(request):
    """Start a real subscribed task connection, retiring it even on failure."""

    def start(endpoint):
        connection = codex_adapter_model.TaskConnection(endpoint, "codex-thread")
        request.addfinalizer(connection.stop)
        connection.start()
        return connection

    return start


def _idle_app_server(answers=None, *, status="idle"):
    """A provider that resumes repeatedly and answers delivery starts in order."""

    def handle(socket):
        remaining = iter(answers or ())
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "thread/resume":
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "thread": {
                                    "id": "codex-thread",
                                    "status": {"type": status},
                                    "turns": [],
                                }
                            },
                        }
                    )
                )
            elif method == "turn/start":
                answer = next(remaining)
                socket.send(answer(request) if callable(answer) else answer)

    return handle


def _unopenable(*_args):
    """Stand in for a page write the turn's own work left unable to open."""
    raise OSError("the page could not be opened")


def test_a_busy_codex_task_keeps_its_delivery_for_a_later_turn(
    page_dir, app_server, task_connection
):
    """A delivery waits for an idle task rather than joining the user's turn.

    `turn/start` against a running turn does not refuse. App Server steers the
    delivery into that turn instead, and says so of `turnTrigger`: "Ignored when
    this request steers an already-active turn". That turn has one final answer and
    it answers whatever the user asked, so the status is read on this connection,
    one request before the start, and a working task keeps the frozen delivery for
    the next pass.
    """
    prepared = _codex_delivery(page_dir, "Answer when idle")
    target = codex_model.stream_reply_target(prepared.payload)

    def handle(socket):
        initialize = json.loads(socket.recv())
        socket.send(json.dumps({"id": initialize["id"], "result": {}}))
        socket.recv()  # initialized
        for _ in range(2):
            resume = json.loads(socket.recv())
            socket.send(
                json.dumps(
                    {
                        "id": resume["id"],
                        "result": {
                            "thread": {
                                "id": "codex-thread",
                                "status": {"type": "active", "activeFlags": []},
                            }
                        },
                    }
                )
            )

    endpoint = app_server(handle)
    assert task_connection(endpoint).start_delivery(prepared.payload) is False
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Offering,
    )
    assert not thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )


@pytest.mark.parametrize(
    "refusal",
    [
        {"message": "the active turn cannot be steered"},
        {
            "code": -32000,
            "data": {"state": None, "allowed": [True, "needs,reply", "é"]},
        },
    ],
)
def test_a_refused_turn_gives_up_the_reply_it_reserved(
    page_dir, app_server, task_connection, refusal
):
    """A provider that refuses before executing has started nothing.

    The reply reservation is what stops any other writer answering the user while the
    provider is about to. A start that certainly did not happen gives it up, because
    until it does the user has neither an answer nor anything able to say one is
    not coming.
    """
    prepared = _codex_delivery(page_dir)
    target = codex_model.stream_reply_target(prepared.payload)
    endpoint = app_server(
        _idle_app_server(
            [
                lambda request: json.dumps(
                    {
                        "id": request["id"],
                        "error": refusal,
                    }
                ),
                lambda request: json.dumps(
                    {"id": request["id"], "result": {"turn": {"id": "retry-turn"}}}
                ),
            ]
        )
    )

    connection = task_connection(endpoint)
    with pytest.raises(codex_model.AppServerRequestRejected) as rejected:
        connection.start_delivery(prepared.payload)
    if "message" in refusal:
        assert str(rejected.value) == refusal["message"]
    else:
        assert json.loads(str(rejected.value)) == refusal

    assert not thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )

    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    assert files_model.read_json(path)["state"] == "offering"
    assert connection.start_delivery(prepared.payload)
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Accepted,
    )


def test_an_unacknowledged_turn_keeps_the_reply_it_reserved(
    page_dir, app_server, task_connection
):
    """A request whose answer never came back may have started a turn.

    Nothing here can tell, so the reply stays reserved: no other writer may answer
    for a delivery a running turn might be about to answer itself. The observer
    adopts that turn the moment it says anything, and the delivery record stays
    offered until it does.
    """
    prepared = _codex_delivery(page_dir)
    target = codex_model.stream_reply_target(prepared.payload)
    endpoint = app_server(_idle_app_server([lambda _request: "this is not json"]))

    with pytest.raises(
        codex_model.AppServerDeliveryUncertain, match="not acknowledged"
    ):
        task_connection(endpoint).start_delivery(prepared.payload)

    assert thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )


def test_a_reply_that_cannot_be_written_still_closes_its_turn(page_dir, monkeypatch):
    """The page stops saying the agent is working, however the reply went.

    `AppServerReplyStream` guards only the commit of a completed answer: setting the
    state and releasing the reservation open a page transaction of their own, and the
    turn's own work may have left that page unopenable. The turn has ended either
    way, and until its Leaf turn closes and its activity reading comes off, the
    page tells its user the agent is still working until the claim's
    fifteen-minute grace runs out.
    """
    prepared = _codex_delivery(page_dir)
    payload = prepared.payload
    target = codex_model.stream_reply_target(payload)
    thread_model.reserve_delivery_reply("codex-thread", payload["id"], target)
    admitted = cleanup_model.start_session_turn(
        "codex-thread", "leaf-turn", cleanup_model.session_record("codex-thread")
    )
    assert admitted is not None
    turn = codex_model.TurnFold(
        "codex-thread",
        "leaf-turn",
        payload["id"],
        target,
        lifecycle=admitted,
    )
    turn.open()
    codex_model.set_stream_activity(
        "codex-thread",
        "leaf-turn",
        {"kind": "working"},
        expected=cleanup_model.session_record("codex-thread"),
    )
    turn.open_reply()
    monkeypatch.setattr(codex_model.AppServerReplyStream, "_set_state", _unopenable)

    with pytest.raises(OSError, match="could not be opened"):
        turn.commit({"id": "leaf-turn", "status": "completed", "items": []})

    assert service_model.page_claim(page_dir)["turn_closed"] is not None
    assert read_record(page_dir / "stream.json")["activity"] is None
    # The reservation is released too: a reply that faulted part-written holds one
    # nothing will ever commit, and every other writer waits behind it.
    assert not thread_model.delivery_reply_reserved(
        "codex-thread", payload["id"], target
    )


def test_an_observed_turn_whose_reply_cannot_be_written_still_closes(
    page_dir, monkeypatch
):
    """The observer ends the turns it adopts the way a follower ends its own.

    A turn the observer binds is one nobody else is following — a pointer the task
    picked up, or a delivery whose adapter died mid-turn — so its ending is the only
    one that turn gets. The reply write can fault on the page the turn left behind,
    and the turn is over either way: the page stops reading working, and the reply
    reservation is released for whatever writer tells the user what happened.
    """
    prepared = _codex_delivery(page_dir)
    payload = prepared.payload
    target = codex_model.stream_reply_target(payload)
    thread_model.reserve_delivery_reply("codex-thread", payload["id"], target)
    observer = _observer()
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "leaf-turn", "items": [], "status": "inProgress"},
            },
        }
    )
    observer._read(
        {
            "method": "item/started",
            "params": {
                "threadId": "codex-thread",
                "turnId": "leaf-turn",
                "startedAtMs": 1,
                "item": {
                    "id": "delivery",
                    "type": "functionCallOutput",
                    "name": "leaf_delivery",
                    "output": json.dumps(payload),
                },
            },
        }
    )
    assert observer.turns["leaf-turn"].reply_stream is not None
    monkeypatch.setattr(codex_model.AppServerReplyStream, "_set_state", _unopenable)

    with pytest.raises(OSError, match="could not be opened"):
        observer._read(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": "leaf-turn", "status": "completed", "items": []},
                },
            }
        )

    assert observer.turns == {}
    assert service_model.page_claim(page_dir)["turn_closed"] is not None
    assert not thread_model.delivery_reply_reserved(
        "codex-thread", payload["id"], target
    )


def test_a_task_that_will_never_take_a_turn_is_reported_rather_than_waited_on(
    page_dir, app_server, task_connection
):
    """`systemError` is not a state a task comes out of by being left alone.

    Holding the delivery for an idle task that never arrives leaves the user's
    move picked up, unanswered, and unexplained for the adapter's life. Raising
    puts it in the log and on the delivery loop's retry ladder, where every other
    failure this adapter cannot fix by itself already is.
    """
    prepared = _codex_delivery(page_dir)

    def handle(socket):
        initialize = json.loads(socket.recv())
        socket.send(json.dumps({"id": initialize["id"], "result": {}}))
        socket.recv()  # initialized
        for _ in range(2):
            resume = json.loads(socket.recv())
            socket.send(
                json.dumps(
                    {
                        "id": resume["id"],
                        "result": {
                            "thread": {
                                "id": "codex-thread",
                                "status": {"type": "systemError"},
                            }
                        },
                    }
                )
            )

    endpoint = app_server(handle)
    with pytest.raises(RuntimeError, match="not taking turns: systemError"):
        task_connection(endpoint).start_delivery(prepared.payload)


def test_a_running_turn_holds_a_delivery_back_without_asking_the_task(
    codex_claimed_page, monkeypatch
):
    """The observer's own reading is what the delivery loop waits on.

    Status is only readable by opening a connection, so asking the task each pass
    would reconnect, handshake and resume once a second for as long as the user's
    turn runs. The observer is already subscribed and already folds every
    `turn/started` and `turn/completed`, so the loop reads that instead. It can
    lag, which is why it only holds a delivery back — the status that lets one
    start is still read on the starting connection.
    """
    page = codex_claimed_page
    append_carried_log_record(
        page, {"kind": "comment", "id": "later", "author": "user", "text": "and this"}
    )
    with service_model.PageTransaction(page) as transaction:
        reading = session_model.PageTick(
            page,
            transaction.status,
            [events_model.read_events(page)[-1]],
            True,
            "watching",
            False,
            None,
            transaction,
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)

    observer = _observer()
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "a-turn-the-user-started",
                    "items": [],
                    "status": "inProgress",
                },
            },
        }
    )
    monkeypatch.setattr(
        observer,
        "start_delivery",
        lambda *_: pytest.fail("the task was asked while a turn of its own ran"),
    )

    assert not codex_adapter_model._offer_queued_delivery(
        "codex", "codex-thread", observer
    )

    # The turn ends and the fold says so, without anything reconnecting to ask.
    observer._read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "a-turn-the-user-started",
                    "status": "completed",
                    "items": [],
                },
            },
        }
    )
    assert observer.working() is False


def test_an_active_task_whose_turn_is_not_named_records_no_turn(monkeypatch):
    """A turn id has to be a turn, or nothing ever clears what it was written on.

    `thread/resume` can report a task active without naming its running turn: full
    history is deprecated for paginated threads, so `turns` may not carry it. The
    word "active" used to be recorded in its place, and no `turn/completed`
    matches that, so the page's activity reading and the fold the delivery loop
    waits on both stood until the next reconnect.
    """
    observer = _observer()
    observer.started = True
    updates = []
    take_stream_activity(monkeypatch, updates, [])
    sent = []

    def send(_socket, _method, _request_id, params):
        sent.append(params)
        return {
            "thread": {
                "id": "codex-thread",
                "status": {"type": "active", "activeFlags": []},
            }
        }

    observer._send = send

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def recv(self, timeout=None):
            observer.stop_event.set()
            raise TimeoutError

    monkeypatch.setattr(codex_adapter_model, "app_server_connect", lambda _e: Socket())
    monkeypatch.setattr(
        codex_adapter_model, "app_server_handshake", lambda *_args: None
    )
    observer._connect()

    assert observer.working() is False
    assert updates == []


def test_an_app_server_failure_cleans_up_its_streams_before_retrying(
    monkeypatch, capsys
):
    """Every projection this observer put on a page comes off before it reconnects.

    A cleanup that fails is reported rather than raised: this is the top of the
    observer thread, and the connection it is going back for is what would repair
    the reading it could not take down. One turn's failure does not keep the next
    turn's reading up.
    """

    class StopAfterFailure:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _timeout):
            self.stopped = True
            return True

    observer = _observer()
    observer.stop_event = StopAfterFailure()
    cleanup = []

    class Stream:
        def disconnect(self):
            cleanup.append("stream")
            raise OSError("reply cleanup failed")

    bound = codex_model.TurnFold(
        "codex-thread",
        "bound-turn",
        lifecycle=cleanup_model.session_record("codex-thread"),
    )
    bound.reply_stream = Stream()
    observer.turns = {
        "bound-turn": bound,
        "user-turn": codex_model.TurnFold(
            "codex-thread",
            "user-turn",
            lifecycle=cleanup_model.session_record("codex-thread"),
        ),
    }
    observer.started = True
    observer._connect = lambda: (_ for _ in ()).throw(ConnectionError("offline"))

    def fail_activity_cleanup(_session, turn=None, **_scope):
        cleanup.append(("activity", turn))
        raise OSError("activity cleanup failed")

    monkeypatch.setattr(codex_model, "clear_stream_activity", fail_activity_cleanup)

    observer._run()

    assert cleanup == [
        "stream",
        ("activity", "bound-turn"),
        ("activity", "user-turn"),
    ]
    assert (
        "Codex App Server stream cleanup failed: activity cleanup failed"
        in capsys.readouterr().err
    )


def test_codex_launch_owns_one_private_app_server(tmp_path, monkeypatch):
    program = tmp_path / "fake-codex"
    log = tmp_path / "fake-codex.jsonl"
    program.write_text(
        f"""#!{sys.executable}
import json
import os
import signal
import socket
import sys

arguments = sys.argv[1:]
with open(os.environ["FAKE_CODEX_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps({{"arguments": arguments, "endpoint": os.environ.get("LEAF_CODEX_APP_SERVER")}}) + "\\n")
if arguments[:2] == ["app-server", "--listen"]:
    path = arguments[2].removeprefix("unix://")
    server = socket.socket(socket.AF_UNIX)
    server.bind(path)
    server.listen()
    signal.pause()
"""
    )
    program.chmod(0o755)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log))

    launched = CliRunner().invoke(
        cli_model.cli,
        ["codex", "launch", "--codex-path", str(program)],
    )

    assert launched.exit_code == 0, launched.output
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    server, terminal = calls
    assert server["arguments"][:2] == ["app-server", "--listen"]
    endpoint = server["arguments"][2]
    assert endpoint.startswith("unix:///")
    assert server["endpoint"] == endpoint
    assert terminal == {
        "arguments": ["--remote", endpoint],
        "endpoint": endpoint,
    }
    assert not Path(endpoint.removeprefix("unix://")).exists()


@pytest.mark.parametrize(
    "ending",
    ["sys.exit(0)", "from leaf.server import exit_serving; exit_serving(0)"],
)
def test_a_private_app_server_stops_when_its_process_exits(tmp_path, ending):
    """A page server's title request holds its App Server on a daemon thread, which
    never unwinds when the page server exits, whether by an exit or by ending itself
    at once, as it does when its service ends; the server, in a session of its own,
    would run on with no socket anyone can find."""
    program = tmp_path / "fake-codex"
    pid_file = tmp_path / "server.pid"
    program.write_text(
        f"""#!{sys.executable}
import os, signal, socket, sys
open({str(pid_file)!r}, "w").write(str(os.getpid()))
server = socket.socket(socket.AF_UNIX)
server.bind(sys.argv[3].removeprefix("unix://"))
server.listen()
signal.pause()
"""
    )
    program.chmod(0o755)
    holder = f"""
import sys, threading, time
from leaf.codex import private_app_server
ready = threading.Event()
def hold():
    with private_app_server({str(program)!r}):
        ready.set()
        time.sleep(600)
threading.Thread(target=hold, daemon=True).start()
assert ready.wait(20)
{ending}
"""
    try:
        subprocess.run(
            [sys.executable, "-c", holder], check=True, timeout=STATED_TIMEOUT
        )
        pid = int(pid_file.read_text())
        assert not psutil.pid_exists(pid)
    finally:
        if pid_file.exists() and psutil.pid_exists(pid := int(pid_file.read_text())):
            os.kill(pid, signal.SIGTERM)


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://192.0.2.1:4500",
        "wss://localhost:4500",
        "ws://[::1",
        "unix://relative.sock",
    ],
)
def test_codex_activity_rejects_nonlocal_or_invalid_app_servers(endpoint):
    with pytest.raises(Refused, match="local|valid"):
        codex_model.app_server_socket_path(endpoint)


@pytest.mark.parametrize("lost", ["start", "malformed", "stream", "restart"])
@pytest.mark.parametrize("reply_kind", ["thread", "action"])
def test_one_subscription_recovers_delivery_without_a_second_start(
    page_dir, app_server, task_connection, lost, reply_kind
):
    """Provider execution survives both acknowledgement and subscription loss.

    A real WebSocket peer executes a turn, disconnects, then returns its exact
    transcript to the same connection owner. It models the App Server boundary;
    delivery admission, pickup, streaming and reply settlement are Leaf's real code.
    """
    if reply_kind == "thread":
        prepared = _codex_delivery(page_dir)
    else:
        (page_dir / "index.html").write_text(
            PAGE.replace(
                "<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1
            )
        )
        publish(page_dir)
        append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "plan-choice",
                "action": "answer",
                "detail": {},
            },
        )
        prepared = codex_model.prepare_codex_delivery(
            page_dir,
            harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid()),
        )
        assert codex_model.stream_reply_target(prepared.payload) is None
    payload = prepared.payload
    starts = []
    connections = []
    answer = {
        "id": "answer",
        "type": "agentMessage",
        "phase": "final_answer",
        "text": "Recovered answer",
    }

    def handle(socket):
        connections.append(socket)
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "thread/resume":
                turns = (
                    []
                    if not starts
                    else [
                        {
                            "id": "provider-turn",
                            "status": "completed",
                            "items": [_delivery_item(payload), answer],
                        }
                    ]
                )
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "thread": {
                                    "id": "codex-thread",
                                    "status": {"type": "idle"},
                                    "turns": turns,
                                }
                            },
                        }
                    )
                )
            elif method == "turn/start":
                starts.append(request)
                if lost == "malformed":
                    socket.send(json.dumps({"id": request["id"], "result": {}}))
                elif lost != "start":
                    socket.send(
                        json.dumps(
                            {
                                "id": request["id"],
                                "result": {"turn": {"id": "provider-turn"}},
                            }
                        )
                    )
                if lost == "restart":
                    for _ in socket:
                        pass
                else:
                    socket.close()
                return

    endpoint = app_server(handle)
    connection = task_connection(endpoint)
    if lost in {"start", "malformed"}:
        with pytest.raises(codex_model.AppServerDeliveryUncertain):
            connection.start_delivery(payload)
    else:
        assert connection.start_delivery(payload)
        if lost == "restart":
            connection.stop()
            assert not connection.thread.is_alive()
            connection = task_connection(endpoint)
    wait_for(
        lambda: codex_model.read_task_delivery("codex-thread", payload["id"]),
        lambda record: isinstance(record, codex_model.Accepted),
        failure="reconnected transcript did not accept the delivery",
    )
    wait_for(
        lambda: len(connections) == 2 and connection.connected.is_set(),
        bool,
        failure="subscription did not finish its transcript reconciliation",
    )
    replies = wait_for(
        lambda: [
            event
            for event in events_model.read_events(page_dir)
            if event["kind"] == "reply"
        ],
        lambda replies: len(replies) == (1 if reply_kind == "thread" else 0),
        failure="reconnected transcript did not settle its reply",
    )
    assert [reply["text"] for reply in replies] == (
        ["Recovered answer"] if reply_kind == "thread" else []
    )
    assert len(starts) == 1
    assert len(connections) == 2
    assert starts[0]["params"]["clientUserMessageId"] == payload["id"]
    pickups = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert [(event["phase"], event["turn"]) for event in pickups] == [
        ("opened", "provider-turn")
    ]
    assert connection.start_delivery(payload)
    assert len(starts) == 1
    assert len(
        [
            event
            for event in events_model.read_events(page_dir)
            if event["kind"] == "reply"
        ]
    ) == (1 if reply_kind == "thread" else 0)


def test_one_subscription_commits_completion_before_the_start_response(
    page_dir, app_server, task_connection
):
    """A provider may finish while the start request is still waiting on its id."""
    prepared = _codex_delivery(page_dir)
    starts = []
    answer = {
        "id": "answer",
        "type": "agentMessage",
        "phase": "final_answer",
        "text": "Already complete",
    }

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "thread/resume":
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "thread": {
                                    "id": "codex-thread",
                                    "status": {"type": "idle"},
                                    "turns": [],
                                }
                            },
                        }
                    )
                )
            elif method == "turn/start":
                starts.append(request)
                for method, turn in (
                    (
                        "turn/started",
                        {
                            "id": "quick-turn",
                            "items": [_delivery_item(prepared.payload)],
                            "status": "inProgress",
                        },
                    ),
                    (
                        "turn/completed",
                        {"id": "quick-turn", "status": "completed", "items": [answer]},
                    ),
                ):
                    socket.send(
                        json.dumps(
                            {
                                "method": method,
                                "params": {"threadId": "codex-thread", "turn": turn},
                            }
                        )
                    )
                socket.send(
                    json.dumps(
                        {"id": request["id"], "result": {"turn": {"id": "quick-turn"}}}
                    )
                )

    connection = task_connection(app_server(handle))
    assert connection.start_delivery(prepared.payload)
    assert len(starts) == 1
    assert not connection.working()
    assert connection.turns == {}
    assert service_model.page_claim(page_dir)["turn_closed"] is not None
    assert [
        event["text"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ] == ["Already complete"]


def test_an_uncertain_start_without_a_reply_reservation_survives_adapter_restart(
    page_dir, app_server, task_connection
):
    """An action delivery has no reply reservation that could prevent a duplicate
    start."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1)
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan-choice",
            "action": "answer",
            "detail": {},
        },
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    )
    assert codex_model.stream_reply_target(prepared.payload) is None
    starts = []

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            if request.get("method") == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif request.get("method") == "thread/resume":
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "thread": {
                                    "id": "codex-thread",
                                    "status": {"type": "idle"},
                                    "turns": [],
                                }
                            },
                        }
                    )
                )
            elif request.get("method") == "thread/turns/list":
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {"data": [], "nextCursor": None},
                        }
                    )
                )
            elif request.get("method") == "turn/start":
                starts.append(request)
                socket.close()
                return

    endpoint = app_server(handle)
    connection = task_connection(endpoint)
    with pytest.raises(codex_model.AppServerDeliveryUncertain):
        connection.start_delivery(prepared.payload)
    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    with pytest.raises(codex_model.AppServerDeliveryUncertain):
        codex_model.offer_delivery(
            path, codex_model.read_record(path), transport="queue"
        )
    connection.stop()
    connection = task_connection(endpoint)
    assert connection.start_delivery(prepared.payload)
    assert len(starts) == 1
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Abandoned,
    )
    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    assert not path.exists()
    archived = path.parent / "history" / path.name
    assert files_model.read_json(archived)["state"] == "abandoned"
    assert [
        event["failure"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ] == ["delivery_unconfirmed"]
    assert not codex_records("codex-thread")
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)


def test_status_callbacks_cannot_resend_an_already_accepted_delivery(
    page_dir, app_server, task_connection
):
    """The status reader may consume the exact delivery before it returns idle."""
    prepared = _codex_delivery(page_dir)
    starts = []
    resumes = []
    answer = {
        "id": "answer",
        "type": "agentMessage",
        "phase": "final_answer",
        "text": "Accepted while checking",
    }

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "thread/resume":
                resumes.append(request)
                if len(resumes) == 2:
                    for method, turn in (
                        (
                            "turn/started",
                            {
                                "id": "earlier-turn",
                                "items": [_delivery_item(prepared.payload)],
                                "status": "inProgress",
                            },
                        ),
                        (
                            "turn/completed",
                            {
                                "id": "earlier-turn",
                                "status": "completed",
                                "items": [answer],
                            },
                        ),
                    ):
                        socket.send(
                            json.dumps(
                                {
                                    "method": method,
                                    "params": {
                                        "threadId": "codex-thread",
                                        "turn": turn,
                                    },
                                }
                            )
                        )
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "thread": {
                                    "id": "codex-thread",
                                    "status": {"type": "idle"},
                                    "turns": [],
                                }
                            },
                        }
                    )
                )
            elif method == "turn/start":
                starts.append(request)
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {"turn": {"id": "duplicate-turn"}},
                        }
                    )
                )

    connection = task_connection(app_server(handle))
    assert connection.start_delivery(prepared.payload)
    assert starts == []
    assert connection.turns == {}
    assert not connection.working()
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Accepted,
    )
    assert [
        event["text"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ] == ["Accepted while checking"]


@pytest.mark.parametrize("manual", [False, True])
def test_abandonment_recovery_releases_the_seat_and_preserves_manual_answers(
    page_dir, manual
):
    """A crash after abandonment publication resumes its full receipt, including release."""
    prepared = _codex_delivery(page_dir)
    target = codex_model.stream_reply_target(prepared.payload)
    thread_model.reserve_delivery_reply("codex-thread", prepared.payload["id"], target)
    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    record = files_model.read_json(path)
    record.update(state="abandoned", pending=list(range(len(record["batches"]))))
    cleanup_model.write_json(path, record)
    if manual:
        cleanup_model.prompt_turn("codex-thread", "manual-turn")
        thread_model.post_reply(
            page_dir,
            target,
            text="Manual answer",
            markup="",
        )
    assert codex_model.recover_codex_receipt("codex-thread")
    assert not thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )
    assert not codex_records("codex-thread")
    events = events_model.read_events(page_dir)
    replies = [event for event in events if event["kind"] == "reply"]
    assert len(replies) == 1
    assert replies[0]["text"] == (
        "Manual answer" if manual else codex_model.UNCONFIRMED_TEXT
    )
    assert acknowledged_through(page_dir) > 0
    # Late provider evidence keeps its exact delivery identity but cannot replace
    # the manual answer that won before this harness retired its unknown attempt.
    if manual:
        connection = _observer()
        connection._resume(
            {
                "turns": [
                    {
                        "id": "late-turn",
                        "status": "completed",
                        "items": [
                            _delivery_item(prepared.payload),
                            {
                                "id": "late",
                                "type": "agentMessage",
                                "phase": "final_answer",
                                "text": "Late answer",
                            },
                        ],
                    }
                ]
            }
        )
        assert [
            event["text"]
            for event in events_model.read_events(page_dir)
            if event["kind"] == "reply"
        ] == ["Manual answer"]
    _codex_delivery(page_dir, "Another input")
    assert codex_records("codex-thread")


@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("lifecycle", ["open", "closed", "newer", "resolved"])
def test_full_paginated_history_hydrates_an_accepted_delivery_omitted_from_resume(
    page_dir, app_server, task_connection, restart, lifecycle
):
    """Accepted input may be archived before completion; resume alone is not full history."""
    prepared = _codex_delivery(page_dir)
    turn_id = "hidden-turn"
    connection = _observer()
    assert connection._observe_lifecycle(turn_id)
    connection._fold(turn_id, prepared.payload["id"], follow=True)
    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    assert (path.parent / "history" / path.name).exists()
    connection._disconnect_turns()
    if lifecycle == "closed":
        cleanup_model.close_session_turn("codex-thread", turn_id)
    elif lifecycle == "newer":
        cleanup_model.prompt_turn("codex-thread", "newer-turn")
    elif lifecycle == "resolved":
        target = codex_model.stream_reply_target(prepared.payload)
        thread_model.cmd_resolve(page_dir, target["parent"])
    if restart:
        connection = _observer()
    cursors = []

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "thread/resume":
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "thread": {
                                    "status": {"type": "idle"},
                                    "turns": [
                                        {
                                            "id": turn_id,
                                            "status": "completed",
                                            "itemsView": "notLoaded",
                                            "items": [],
                                        }
                                    ],
                                }
                            },
                        }
                    )
                )
            elif method == "thread/turns/list":
                cursor = request["params"]["cursor"]
                cursors.append(cursor)
                turns = (
                    []
                    if cursor is None
                    else [
                        {
                            "id": turn_id,
                            "status": "completed",
                            "itemsView": "full",
                            "items": [
                                _delivery_item(prepared.payload),
                                {
                                    "id": "answer",
                                    "type": "agentMessage",
                                    "phase": "final_answer",
                                    "text": "Hydrated answer",
                                },
                            ],
                        }
                    ]
                )
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {
                                "data": turns,
                                "nextCursor": "older" if cursor is None else None,
                            },
                        }
                    )
                )

    endpoint = app_server(handle)
    if restart:
        connection = task_connection(endpoint)
    else:
        connection.endpoint = endpoint
        with codex_model.app_server_connect(endpoint) as socket:
            codex_model.app_server_handshake(
                socket, 0, "test", "test", connection._read
            )
            response = connection._send(
                socket,
                "thread/resume",
                1,
                {"threadId": "codex-thread", "excludeTurns": False},
            )
            connection._resume(response["thread"])
            assert connection.turns[turn_id].reply_target is not None
            connection._reconcile_history(socket)
    assert cursors == [None, "older"]
    assert [
        event["text"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ] == ["Hydrated answer"]


def test_unloaded_provider_history_cannot_abandon_an_uncertain_start(
    page_dir, app_server
):
    prepared = _codex_delivery(page_dir)
    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    record = files_model.read_json(path)
    record["state"] = "starting"
    cleanup_model.write_json(path, record)
    connection = _observer()

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            if request.get("method") == "initialize":
                result = {}
            elif request.get("method") == "thread/turns/list":
                result = {
                    "data": [{"id": "unknown", "itemsView": "notLoaded", "items": []}],
                    "nextCursor": None,
                }
            else:
                continue
            socket.send(json.dumps({"id": request["id"], "result": result}))

    with codex_model.app_server_connect(app_server(handle)) as socket:
        codex_model.app_server_handshake(socket, 0, "test", "test", connection._read)
        with pytest.raises(RuntimeError, match="full turn items"):
            connection._reconcile_history(socket)
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Offering,
    )
    assert not [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]


def test_an_unloaded_running_user_turn_retains_its_notification_fold(page_dir):
    _codex_delivery(page_dir)
    connection = _observer()
    connection._resume(
        {
            "status": {"type": "active", "activeFlags": []},
            "turns": [
                {
                    "id": "ordinary-turn",
                    "status": "inProgress",
                    "itemsView": "notLoaded",
                    "items": [],
                }
            ],
        }
    )
    assert "ordinary-turn" in connection.turns
    connection._read(
        {
            "method": "item/started",
            "params": {
                "threadId": "codex-thread",
                "turnId": "ordinary-turn",
                "startedAtMs": 100,
                "item": {
                    "id": "reasoning",
                    "type": "reasoning",
                    "summary": [],
                    "content": [],
                },
            },
        }
    )
    assert connection.turns["ordinary-turn"].events.item_started_at["reasoning"] == 100
    connection._read(
        {
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "codex-thread",
                "turnId": "ordinary-turn",
                "itemId": "approval",
                "startedAtMs": 0,
            },
            "id": 1,
        }
    )
    assert connection.turns["ordinary-turn"].events.waiting_kind == "awaiting_approval"


def test_connection_stop_waits_for_its_receiver_and_rejects_queued_commands():
    """A successor cannot own leases until the old reader and queued writers stop."""
    entered = threading.Event()
    release = threading.Event()
    stopped = threading.Event()
    connection = _observer()

    def receiver():
        entered.set()
        release.wait()
        # Exercise the real receiver-owned command drain after delayed cleanup.
        connection._run()

    connection.thread = threading.Thread(target=receiver)
    connection.thread.start()
    assert entered.wait(STATED_TIMEOUT), "the receiver thread never started"
    from concurrent.futures import Future

    result = Future()
    connection.commands.put(({"id": "queued"}, result))

    def stop():
        connection.stop()
        stopped.set()

    stopper = threading.Thread(target=stop)
    stopper.start()
    assert connection.stop_event.wait(STATED_TIMEOUT), (
        "stop never signalled its receiver"
    )
    assert not stopped.is_set()
    assert not result.done()
    release.set()
    stopper.join(timeout=STATED_TIMEOUT)
    assert stopped.is_set()
    assert not connection.thread.is_alive()
    with pytest.raises(RuntimeError, match="stopped"):
        result.result()
    with pytest.raises(RuntimeError, match="stopped"):
        connection.start_delivery({"id": "after"})


def test_full_history_restores_the_running_identity_omitted_from_resume(
    page_dir, app_server, task_connection
):
    prepared = _codex_delivery(page_dir)
    connection = _observer()
    assert connection._observe_lifecycle("hidden-running")
    connection._fold("hidden-running", prepared.payload["id"], follow=True)
    connection._disconnect_turns()

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                result = {}
            elif method == "thread/resume":
                result = {
                    "thread": {
                        "status": {"type": "active", "activeFlags": []},
                        "turns": [],
                    }
                }
            elif method == "thread/turns/list":
                result = {
                    "data": [
                        {
                            "id": "hidden-running",
                            "status": "inProgress",
                            "itemsView": "full",
                            "items": [_delivery_item(prepared.payload)],
                        }
                    ],
                    "nextCursor": None,
                }
            else:
                continue
            socket.send(json.dumps({"id": request["id"], "result": result}))

    connection = task_connection(app_server(handle))
    assert connection.working()
    assert connection.running == "hidden-running"
    assert "hidden-running" in connection.turns
    connection._read(
        {
            "method": "thread/status/changed",
            "params": {
                "threadId": "codex-thread",
                "status": {"type": "active", "activeFlags": ["waitingOnApproval"]},
            },
        }
    )
    assert connection.turns["hidden-running"].events.waiting_kind == "awaiting_approval"


def test_unloaded_running_metadata_preserves_the_disconnected_reply_draft(page_dir):
    prepared = _codex_delivery(page_dir)
    connection = _observer()
    connection._reconcile(
        {
            "id": "draft-turn",
            "status": "inProgress",
            "itemsView": "full",
            "items": [
                _delivery_item(prepared.payload),
                {
                    "id": "draft",
                    "type": "agentMessage",
                    "phase": "final_answer",
                    "text": "Retained draft",
                },
            ],
        }
    )
    connection._disconnect_turns()
    connection._resume(
        {
            "status": {"type": "active", "activeFlags": []},
            "turns": [
                {
                    "id": "draft-turn",
                    "status": "inProgress",
                    "itemsView": "notLoaded",
                    "items": [],
                }
            ],
        }
    )
    assert connection.turns["draft-turn"].events.text["draft"] == "Retained draft"
    assert read_record(page_dir / "stream.json")["reply"]["text"] == "Retained draft"


def test_archived_abandonment_recovers_a_late_final_from_paginated_history(
    page_dir, app_server, task_connection
):
    prepared = _codex_delivery(page_dir)
    # The start request may have reached the provider before its acknowledgement
    # was lost. Abandon that uncertain start, then recover its actual late final.
    assert codex_model.begin_delivery_start("codex-thread", prepared.payload["id"])
    codex_model.abandon_uncertain_delivery("codex-thread", prepared.payload)
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Abandoned,
    )
    lists = []

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                result = {}
            elif method == "thread/resume":
                result = {"thread": {"status": {"type": "idle"}, "turns": []}}
            elif method == "thread/turns/list":
                lists.append(request)
                result = {
                    "data": [
                        {
                            "id": "late-turn",
                            "status": "completed",
                            "itemsView": "full",
                            "items": [
                                _delivery_item(prepared.payload),
                                {
                                    "id": "late",
                                    "type": "agentMessage",
                                    "phase": "final_answer",
                                    "text": "Recovered late answer",
                                },
                            ],
                        }
                    ],
                    "nextCursor": None,
                }
            else:
                continue
            socket.send(json.dumps({"id": request["id"], "result": result}))

    task_connection(app_server(handle))
    assert len(lists) == 1
    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [
        codex_model.UNCONFIRMED_TEXT,
        "Recovered late answer",
    ]
    assert "failure" in replies[0] and "failure" not in replies[1]
    assert not codex_records("codex-thread")


def test_manual_answer_retires_an_unknown_start_before_the_provider_becomes_idle(
    page_dir,
):
    prepared = _codex_delivery(page_dir)
    target = codex_model.stream_reply_target(prepared.payload)
    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    record = files_model.read_json(path)
    record["state"] = "starting"
    cleanup_model.write_json(path, record)
    thread_model.reserve_delivery_reply("codex-thread", prepared.payload["id"], target)
    cleanup_model.prompt_turn("codex-thread", "manual-turn")
    thread_model.post_reply(
        page_dir,
        target,
        text="Manual winner",
        markup="",
    )
    # The watcher settles the harness attempt without contacting the provider;
    # prolonged disconnect cannot block later input behind the manual winner.
    assert codex_model.recover_codex_receipt("codex-thread")
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", prepared.payload["id"]),
        codex_model.Abandoned,
    )
    assert not codex_records("codex-thread")
    newer = _codex_delivery(page_dir, "Next input")
    assert newer.payload["id"] != prepared.payload["id"]
    assert [
        event["text"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ] == ["Manual winner"]


@pytest.mark.parametrize("existing_fold", [False, True])
def test_observer_rejects_stale_running_snapshot(existing_fold, claimed):
    cleanup_model.prompt_turn("s1", "old")
    observer = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "s1")
    if existing_fold:
        observer._read(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "s1",
                    "turn": {"id": "old", "items": [], "status": "inProgress"},
                },
            }
        )
    cleanup_model.prompt_turn("s1", "new")
    cleanup_model.close_session_turn("s1", "new")
    current = cleanup_model.session_record("s1")
    observer._resume(
        {
            "status": {"type": "active", "activeFlags": []},
            "turns": [{"id": "old", "status": "inProgress", "items": []}],
        }
    )
    assert observer.running is None
    assert cleanup_model.session_record("s1") == current


def test_observer_continues_after_a_recovered_provider_completion(claimed):
    cleanup_model.prompt_turn("s1", "old")
    observer = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "s1")
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "s1",
                "turn": {"id": "old", "items": [], "status": "inProgress"},
            },
        }
    )
    observer._resume(
        {
            "status": {"type": "idle"},
            "turns": [{"id": "old", "status": "completed", "items": []}],
        }
    )
    assert cleanup_model.session_record("s1")["turn_closed"] is not None
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "s1",
                "turn": {"id": "next", "items": [], "status": "inProgress"},
            },
        }
    )
    assert observer.running == "next"
    assert cleanup_model.session_record("s1")["turn"] == "next"


def test_provider_start_cannot_reopen_a_completed_named_turn(claimed):
    cleanup_model.prompt_turn("s1", "completed")
    cleanup_model.close_session_turn("s1", "completed")
    expected = cleanup_model.session_record("s1")
    assert cleanup_model.start_session_turn("s1", "completed", expected) is None
    assert cleanup_model.session_record("s1") == expected


def test_provider_start_accepts_its_own_synchronous_prompt(claimed):
    expected = cleanup_model.session_record("s1")
    published = cleanup_model.prompt_turn("s1", "returned-turn")
    assert (
        cleanup_model.start_session_turn("s1", "returned-turn", expected) == published
    )
    assert cleanup_model.session_record("s1") == published
    cleanup_model.prompt_turn("s1", "competing-turn")
    competing = cleanup_model.session_record("s1")
    assert cleanup_model.start_session_turn("s1", "returned-turn", expected) is None
    assert cleanup_model.session_record("s1") == competing
    cleanup_model.end_session("s1")
    cleanup_model.prompt_turn("s1", "returned-turn")
    assert cleanup_model.start_session_turn("s1", "returned-turn", expected) is None


@pytest.mark.parametrize("replacement", ["provider_notification", "prompt"])
def test_resume_metadata_cannot_replace_a_newer_observation_during_the_request(
    page_dir, app_server, replacement
):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old-turn")
    connection = _observer()
    connection._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "old-turn", "items": [], "status": "inProgress"},
            },
        }
    )

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            if request.get("method") == "initialize":
                result = {}
            elif request.get("method") == "thread/resume":
                if replacement == "provider_notification":
                    socket.send(
                        json.dumps(
                            {
                                "method": "turn/started",
                                "params": {
                                    "threadId": "codex-thread",
                                    "turn": {
                                        "id": "new-turn",
                                        "items": [],
                                        "status": "inProgress",
                                    },
                                },
                            }
                        )
                    )
                else:
                    cleanup_model.prompt_turn("codex-thread", "new-turn")
                    with service_model.PageTransaction(page_dir) as page:
                        page.set_status("waiting")
                    codex_model.set_stream_activity(
                        "codex-thread",
                        "new-turn",
                        {"kind": "tool", "detail": "New activity"},
                        expected=cleanup_model.session_record("codex-thread"),
                    )
                result = {
                    "thread": {
                        "status": {
                            "type": "active",
                            "activeFlags": ["waitingOnApproval"],
                        },
                        "turns": [
                            {
                                "id": "old-turn",
                                "status": "inProgress",
                                "itemsView": "full",
                                "items": [],
                            },
                        ],
                    }
                }
            else:
                continue
            socket.send(json.dumps({"id": request["id"], "result": result}))

    with codex_model.app_server_connect(app_server(handle)) as socket:
        codex_model.app_server_handshake(socket, 0, "test", "test", connection._read)
        thread, expected = connection._resume_task(socket, exclude_turns=False)
        winner = cleanup_model.session_record("codex-thread")
        status_before = status_and_stream(page_dir)
        connection._resume(thread, expected)
    assert cleanup_model.session_record("codex-thread") == winner
    assert winner["turn"] == "new-turn"
    assert connection.running == (
        "new-turn" if replacement == "provider_notification" else None
    )
    if replacement == "provider_notification":
        assert connection.turns["new-turn"].events.waiting_kind is None
    else:
        assert status_and_stream(page_dir) == status_before


def test_stale_live_notifications_cannot_reuse_a_fold_after_a_newer_prompt(page_dir):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old-turn")
    connection = _observer()
    connection._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "old-turn", "items": [], "status": "inProgress"},
            },
        }
    )
    cleanup_model.prompt_turn("codex-thread", "new-turn")
    winner = cleanup_model.session_record("codex-thread")
    for message in [
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "old-turn", "items": [], "status": "inProgress"},
            },
        },
        {
            "method": "item/commandExecution/requestApproval",
            "id": 1,
            "params": {
                "threadId": "codex-thread",
                "turnId": "old-turn",
                "itemId": "old-approval",
                "startedAtMs": 0,
            },
        },
    ]:
        connection._read(message)
    assert cleanup_model.session_record("codex-thread") == winner
    assert connection.turns["old-turn"].events.waiting_kind is None


def test_a_matching_live_completion_allows_the_next_turn_without_prompt_hooks(page_dir):
    _codex_delivery(page_dir)
    connection = _observer()
    for turn_id in ["first-turn", "second-turn"]:
        connection._read(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": turn_id, "items": [], "status": "inProgress"},
                },
            }
        )
        assert connection.running == turn_id
        assert cleanup_model.session_record("codex-thread")["turn"] == turn_id
        connection._read(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": turn_id, "status": "completed", "items": []},
                },
            }
        )
        assert connection.running is None
        assert cleanup_model.session_record("codex-thread")["turn_closed"] is not None


@pytest.mark.parametrize("completion", ["notification", "resume"])
def test_completion_after_stop_advances_observation_without_a_running_fold(
    page_dir, completion
):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "first-turn")
    connection = _observer()
    cleanup_model.close_session_turn("codex-thread", "first-turn")
    connection._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "first-turn", "items": [], "status": "inProgress"},
            },
        }
    )
    assert "first-turn" not in connection.turns
    terminal = {"id": "first-turn", "status": "completed", "items": []}
    if completion == "notification":
        connection._read(
            {
                "method": "turn/completed",
                "params": {"threadId": "codex-thread", "turn": terminal},
            }
        )
    else:
        connection._resume({"status": {"type": "idle"}, "turns": [terminal]})
    connection._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "second-turn", "items": [], "status": "inProgress"},
            },
        }
    )
    assert connection.running == "second-turn"
    assert cleanup_model.session_record("codex-thread")["turn"] == "second-turn"


@pytest.mark.parametrize("existing_fold", [False, True])
@pytest.mark.parametrize("replacement", ["new_prompt", "new_generation"])
def test_old_completion_cannot_close_a_newer_lifecycle(
    page_dir, existing_fold, replacement
):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old-turn")
    connection = _observer()
    if existing_fold:
        connection._read(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": "old-turn", "items": [], "status": "inProgress"},
                },
            }
        )
    if replacement == "new_generation":
        cleanup_model.end_session("codex-thread")
        cleanup_model.prompt_turn("codex-thread", "old-turn")
    else:
        cleanup_model.prompt_turn("codex-thread", "new-turn")
    winner = cleanup_model.session_record("codex-thread")
    connection._read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "old-turn", "status": "completed", "items": []},
            },
        }
    )
    assert cleanup_model.session_record("codex-thread") == winner


@pytest.mark.parametrize("cleanup", ["completion", "disconnect", "activity"])
def test_old_fold_cannot_change_activity_in_a_reused_session_generation(
    page_dir, cleanup
):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "same-turn")
    old = codex_model.TurnFold(
        "codex-thread",
        "same-turn",
        lifecycle=cleanup_model.session_record("codex-thread"),
    )
    assert old.open()
    cleanup_model.end_session("codex-thread")
    cleanup_model.prompt_turn("codex-thread", "same-turn")
    with service_model.PageTransaction(page_dir) as page:
        page.take_claim(
            harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
        )
        page.set_status("waiting")
    codex_model.set_stream_activity(
        "codex-thread",
        "same-turn",
        {"kind": "tool", "detail": "New generation activity"},
        expected=cleanup_model.session_record("codex-thread"),
    )
    winner = cleanup_model.session_record("codex-thread")
    status = status_and_stream(page_dir)
    if cleanup == "completion":
        old.commit({"id": "same-turn", "status": "completed", "items": []})
    elif cleanup == "disconnect":
        old.disconnect()
    else:
        old.absorb(
            {
                "method": "item/started",
                "params": {
                    "threadId": "codex-thread",
                    "turnId": "same-turn",
                    "startedAtMs": 10,
                    "item": {
                        "id": "old-command",
                        "type": "commandExecution",
                        "command": "old command",
                        "commandActions": [],
                        "cwd": "/work",
                        "status": "inProgress",
                    },
                },
            }
        )
    assert cleanup_model.session_record("codex-thread") == winner
    assert status_and_stream(page_dir) == status


@pytest.mark.parametrize("replacement", ["prompt", "stop"])
def test_an_old_fold_cannot_publish_working_or_tool_activity_after_its_turn(
    page_dir, replacement
):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old-turn")
    fold = codex_model.TurnFold(
        "codex-thread",
        "old-turn",
        lifecycle=cleanup_model.session_record("codex-thread"),
    )
    assert fold.open()
    if replacement == "prompt":
        cleanup_model.prompt_turn("codex-thread", "new-turn")
        with service_model.PageTransaction(page_dir) as page:
            page.set_status("waiting")
        codex_model.set_stream_activity(
            "codex-thread",
            "new-turn",
            {"kind": "tool", "detail": "New activity"},
            expected=cleanup_model.session_record("codex-thread"),
        )
    else:
        cleanup_model.close_session_turn("codex-thread", "old-turn")
        fold.clear_activity()
    status = status_and_stream(page_dir)
    epoch = cleanup_model.session_record("codex-thread")
    fold.set_activity({"kind": "working"})
    fold.absorb(
        {
            "method": "item/started",
            "params": {
                "threadId": "codex-thread",
                "turnId": "old-turn",
                "startedAtMs": 10,
                "item": {
                    "id": "old-command",
                    "type": "commandExecution",
                    "command": "old command",
                    "commandActions": [],
                    "cwd": "/work",
                    "status": "inProgress",
                },
            },
        }
    )
    assert status_and_stream(page_dir) == status
    assert cleanup_model.session_record("codex-thread") == epoch


def test_a_rejected_started_fold_cannot_publish_initial_working_activity(
    page_dir, app_server, monkeypatch
):
    _codex_delivery(page_dir)
    connection = _observer()
    path, _ = codex_model.delivery_records("codex-thread")[0]
    offered = codex_model.offer_delivery(
        path, codex_model.read_record(path), transport="app-server"
    )
    construct = connection._fold
    winner = {}

    def supersede_before_construction(turn_id, delivery_id, **scope):
        cleanup_model.end_session("codex-thread")
        cleanup_model.prompt_turn("codex-thread", turn_id)
        with service_model.PageTransaction(page_dir) as page:
            page.take_claim(
                harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
            )
            page.set_status("waiting")
        codex_model.set_stream_activity(
            "codex-thread",
            turn_id,
            {"kind": "tool", "detail": "New activity"},
            expected=cleanup_model.session_record("codex-thread"),
        )
        winner["epoch"] = cleanup_model.session_record("codex-thread")
        winner["status"] = status_and_stream(page_dir)
        return construct(turn_id, delivery_id, **scope)

    monkeypatch.setattr(connection, "_fold", supersede_before_construction)

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            if "id" not in request:
                continue
            if request["method"] == "initialize":
                result = {}
            elif request["method"] == "thread/resume":
                result = {"thread": {"status": {"type": "idle"}, "turns": []}}
            elif request["method"] == "turn/start":
                result = {"turn": {"id": "same-turn"}}
            else:
                raise AssertionError(request["method"])
            socket.send(json.dumps({"id": request["id"], "result": result}))

    with codex_model.app_server_connect(app_server(handle)) as socket:
        codex_model.app_server_handshake(socket, 0, "test", "test", connection._read)
        with pytest.raises(
            codex_model.AppServerDeliveryUncertain, match="newer session epoch"
        ):
            connection._start_delivery(socket, offered.payload)
    assert not connection.turns
    assert cleanup_model.session_record("codex-thread") == winner["epoch"]
    assert status_and_stream(page_dir) == winner["status"]


def test_fresh_resume_replaces_a_fold_from_an_earlier_session_generation(page_dir):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "same-turn")
    connection = _observer()
    connection._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "same-turn", "items": [], "status": "inProgress"},
            },
        }
    )
    old = connection.turns["same-turn"]
    cleanup_model.end_session("codex-thread")
    cleanup_model.prompt_turn("codex-thread", "same-turn")
    with service_model.PageTransaction(page_dir) as page:
        page.take_claim(
            harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
        )
        page.set_status("waiting")
    expected = cleanup_model.session_record("codex-thread")
    connection.lifecycle = expected
    connection._resume(
        {
            "status": {"type": "active", "activeFlags": []},
            "turns": [
                {
                    "id": "same-turn",
                    "status": "inProgress",
                    "itemsView": "full",
                    "items": [],
                }
            ],
        },
        expected,
    )
    assert connection.turns["same-turn"] is not old
    connection.turns["same-turn"].set_activity(
        {"kind": "tool", "detail": "New activity"}
    )
    assert service_model.read_stream(page_dir)["activity"]["detail"] == "New activity"
    connection._read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "same-turn", "status": "completed", "items": []},
            },
        }
    )
    assert cleanup_model.session_record("codex-thread")["turn_closed"] is not None


@pytest.mark.parametrize(
    "broken_source",
    ["syntax", "widget", "new-generation", "stop", "hydrated", "reacquired"],
)
def test_an_invalid_automatic_final_delivers_one_exact_correction(
    page_dir, broken_source, monkeypatch
):
    """Syntax and widget failures return to the agent, preserving the response address."""
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Change this page"}
    )
    harness = harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    prepared = codex_model.prepare_codex_delivery(page_dir, harness)
    lifecycle = cleanup_model.start_session_turn(
        "codex-thread", "original-turn", cleanup_model.session_record("codex-thread")
    )
    assert lifecycle is not None
    codex_model.accept_codex_delivery(
        "codex-thread", prepared.payload["id"], "original-turn"
    )
    fold = codex_model.TurnFold("codex-thread", "original-turn", lifecycle=lifecycle)
    fold.bind(
        prepared.payload["id"], delivery_model.stream_reply_target(prepared.payload)
    )
    original_source = (page_dir / "index.html").read_text()
    (page_dir / "index.html").write_text(
        "<main>unfinished"
        if broken_source == "syntax"
        else original_source.replace(
            "</main>", '<lf-unknown id="bad"></lf-unknown></main>'
        )
    )
    terminal = {
        "id": "original-turn",
        "status": "completed",
        "items": [
            {
                "type": "agentMessage",
                "phase": "final_answer",
                "text": "The change is done.",
            }
        ],
    }
    if broken_source == "new-generation":
        cleanup_model.end_session("codex-thread")
        with service_model.PageTransaction(page_dir) as page:
            page.take_claim(harness)
        successor = cleanup_model.start_session_turn(
            "codex-thread",
            "original-turn",
            cleanup_model.session_record("codex-thread"),
        )
        assert successor["generation"] != lifecycle["generation"]
        fold.commit(terminal)
        assert fold.correction is None
        assert cleanup_model.session_record("codex-thread") == successor
        return
    if broken_source in {"stop", "hydrated"}:
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "original-turn",
                "stop_hook_active": True,
            },
        )
        assert cleanup_model.session_record("codex-thread")["turn_closed"] is not None
    if broken_source == "hydrated":
        connection = _observer()
        terminal["items"].insert(0, _delivery_item(prepared.payload))
        assert connection._reconcile(terminal)
        records = codex_model.delivery_records("codex-thread")
        assert len(records) == 1
        correction = delivery_model.read_delivery(records[0][0].stem)
    else:
        fold.commit(terminal)
        assert fold.correction is not None
        correction = fold.correction
    assert correction["correction"]["delivery"] == prepared.payload["id"]
    assert "invalid" in correction["correction"]["diagnostic"]
    target = delivery_model.stream_reply_target(correction)
    assert target == delivery_model.stream_reply_target(prepared.payload)
    assert target["responds"] == comment["id"]
    # Duplicate completion and history hydration must retain this exact repair.
    if broken_source == "hydrated":
        assert connection._reconcile(terminal)
    else:
        fold.commit(terminal)
        assert fold.correction["id"] == correction["id"]
    assert len(codex_model.delivery_records("codex-thread")) == 1
    assert codex_model.prepare_codex_delivery(page_dir, harness).payload == correction
    (page_dir / "index.html").write_text(original_source)
    connection = _observer()
    restarted = []

    if broken_source == "reacquired":
        with service_model.PageTransaction(page_dir) as page:
            page.take_claim(harness)
            replacement = page.active_claim
        assert (
            codex_model.prepare_codex_delivery(page_dir, harness).payload == correction
        )
        assert service_model.same_claim(service_model.page_claim(page_dir), replacement)
        monkeypatch.setattr(
            connection,
            "_resume_task",
            lambda *_args, **_kwargs: (
                {"status": {"type": "idle"}},
                cleanup_model.session_record("codex-thread"),
            ),
        )
        with pytest.raises(
            delivery_model.ReceiptRefused, match="acquisition has ended"
        ):
            connection._start_delivery(object(), correction)
        assert codex_model.delivery_records("codex-thread") == []
        # The terminal refusal cannot strand the oldest offer in the hot queue.
        assert connection._start_delivery(object(), correction)
        with service_model.PageTransaction(page_dir) as page:
            assert service_model.same_claim(page.active_claim, replacement)
        return

    def start_delivery(payload):
        assert payload == correction
        restarted.append(
            codex_model.start_app_server_delivery(
                lambda *_: {"turn": {"id": "repair-turn"}}, "codex-thread", payload
            )
        )
        return True

    monkeypatch.setattr(connection, "start_delivery", start_delivery)
    assert codex_adapter_model._offer_queued_delivery(
        "codex", "codex-thread", connection
    )
    [repaired] = restarted
    codex_model.accept_codex_delivery("codex-thread", correction["id"], "repair-turn")
    repair = codex_model.TurnFold("codex-thread", "repair-turn", lifecycle=repaired)
    repair.bind(correction["id"], target)
    repair.commit(
        {
            "id": "repair-turn",
            "status": "completed",
            "items": [
                {
                    "type": "agentMessage",
                    "phase": "final_answer",
                    "text": "Corrected the source.",
                }
            ],
        }
    )
    repair.commit(
        {
            "id": "repair-turn",
            "status": "completed",
            "items": [
                {
                    "type": "agentMessage",
                    "phase": "final_answer",
                    "text": "Corrected the source.",
                }
            ],
        }
    )
    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [(event["responds"], event["text"]) for event in replies] == [
        (comment["id"], "Corrected the source.")
    ]
