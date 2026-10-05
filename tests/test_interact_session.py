"""Watch, ownership, hook, and server-lifetime tests."""

import fcntl
import http.client
import http.cookiejar
import json
import os
import re
import select
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from click.testing import CliRunner
from conftest import CLAUDE_IDENTITY, HOOKED_SESSIONS, LEAF_COMMAND
from interact_support import (
    COMMAND_SUBJECTS,
    COMPOSITE_TIMEOUT,
    HELD_LEASES,
    PAGE,
    PAGE_PACKAGES,
    PLUGIN_ROOT,
    STATED_TIMEOUT,
    Prose,
    _start,
    _status,
    append_carried_log_record,
    append_command,
    available_loopback_port,
    check,
    consume_pending_input,
    declare_idle,
    declare_work,
    end_work,
    fetch,
    fifo_writer,
    hold_status_read,
    install_payload,
    let_a_pick_settle_a_thread,
    owed,
    page_state,
    publish,
    record_claim,
    release_codex_command,
    release_held,
    serving,
    spawn_probe,
    stamp,
    start_server_command,
    state_json,
    take_stream_activity,
    thread_records,
    vendored_by_another_leaf,
    wait_for,
    working,
    yaml_document,
)
from leaf import activity as activity_model
from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model
from leaf import delivery as delivery_model
from leaf import event_contracts as event_contracts_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import event_meaning as event_meaning_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hook_carrier as hook_carrier_model
from leaf import hooks as hooks_model
from leaf import hosting as hosting_model
from leaf import layer as layer_model
from leaf import leases as leases_model
from leaf import machine as machine_model
from leaf import page_view as page_view_model
from leaf import presence as presence_model
from leaf import projection as projection_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf import thread_context as thread_context_model
from leaf import thread_titles
from leaf import vendoring as vendoring_model
from leaf.detached import StartRefused
from leaf.registry import contract as registry_contract
from leaf.registry import storage as registry_storage
from leaf.served_state import browser as browser_served_model
from leaf.served_state import context as read_context
from leaf.served_state import page as served_page
from leaf_dev.page_fixtures import package_selection_args
from websockets.exceptions import WebSocketException
from websockets.sync.server import serve as serve_websocket
from websockets.sync.server import unix_serve as serve_unix_websocket


def last_deliverable_seq(page_dir: Path) -> int:
    """The last event a wait can print, excluding page-owned pickup records."""
    return service_model.unacknowledged(events_model.read_events(page_dir), 0)[-1][
        "seq"
    ]


def delivered(capsys) -> tuple[dict, dict, list[dict]]:
    """Take the input a direct wait's ending woke the session for, as Claude Code's
    prompt hook hands it to the turn: frozen, confirmed, and whole."""
    return woken(capsys.readouterr().out)


def woken(output: str, session: str | None = None) -> tuple[dict, dict, list[dict]]:
    """`delivered`, for a wait whose output the test already holds, and for a
    session other than the one the test runs as."""
    assert "has new input" in output, output
    payload = consume_pending_input(session or session_model.session_harness().session)
    assert payload["format"] == delivery_model.DELIVERY_FORMAT
    assert payload["carrier"] == "hook"
    assert f"leaf delivery ack {payload['id']}" in payload["acknowledge"]
    [batch] = payload["batches"]
    return payload, batch, batch["events"]


def continued(output: str | dict) -> str:
    """What a Claude Code session's Stop hook continues the turn with. It speaks
    through the harness's non-error channel, so the user reads "Stop hook additional
    context" rather than "Stop hook error"."""
    answer = json.loads(output) if isinstance(output, str) else output
    assert "decision" not in answer, answer
    assert answer["hookSpecificOutput"]["hookEventName"] == "Stop"
    return answer["hookSpecificOutput"]["additionalContext"]


def printed(output: str) -> tuple[dict, dict, list[dict]]:
    """Read the one delivery a wait printed, for a harness whose wait is its carrier
    (a bare shell, a Codex watcher): its reader confirms it with `wait --ack`."""
    payload = json.loads(output)
    assert payload["format"] == delivery_model.DELIVERY_FORMAT
    assert payload["carrier"] == "wait"
    [batch] = payload["batches"]
    return payload, batch, batch["events"]


@pytest.fixture
def codex_loop(monkeypatch):
    """A Codex task running its own `leaf wait`/`leaf wait --ack` loop, the harness
    session whose wait prints each delivery for its reader to confirm. This process,
    and every command it spawns, carries the task's identity in place of Claude
    Code's. Call the value with a page to record the task's claim on it: a claim
    taken from here would look for a codex process above the suite and find none."""
    for name in CLAUDE_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    return lambda page: record_claim(
        page, id="codex-thread", harness="codex", agent="Codex"
    )


def codex_start_announcement(process) -> str:
    """Wait for committed CLI output before transferring the fake harness lifetime."""
    assert select.select([process.stdout], [], [], 30)[0], (
        "Codex start did not report completion"
    )
    line = process.stdout.readline()
    assert json.loads(line)["task"] == "codex-thread"
    return line


def fake_codex_cli(tmp_path: Path) -> tuple[Path, Path]:
    """A process-boundary `codex queue` implementation for adapter tests."""
    program = tmp_path / "fake-codex"
    log = tmp_path / "fake-codex.jsonl"
    program.write_text(
        f"""#!{sys.executable}
import json
import os
import sys
import time

log = os.environ["FAKE_CODEX_LOG"]
arguments = sys.argv[1:]
with open(log, "a", encoding="utf-8") as stream:
    stream.write(json.dumps(arguments, separators=(",", ":")) + "\\n")
if arguments == ["queue", "--help"]:
    if os.environ.get("FAKE_CODEX_REJECT_QUEUE"):
        print("queue unsupported", file=sys.stderr)
        sys.exit(1)
    print("Queue a message for an existing session")
    sys.exit(0)
if arguments[:1] != ["queue"]:
    print("unsupported command", file=sys.stderr)
    sys.exit(2)
expected_cwd = os.environ.get("FAKE_CODEX_EXPECT_CWD")
if expected_cwd and os.getcwd() != expected_cwd:
    print(f"unexpected cwd: {{os.getcwd()}}", file=sys.stderr)
    sys.exit(1)
waiting = os.environ.get("FAKE_CODEX_QUEUE_WAIT")
if waiting:
    with open(waiting + ".started", "w", encoding="utf-8"):
        pass
    while not os.path.exists(waiting + ".release"):
        time.sleep(0.01)
failure = os.environ.get("FAKE_CODEX_QUEUE_FAILURE_ONCE")
if failure and not os.path.exists(failure):
    with open(failure, "w", encoding="utf-8") as failed:
        failed.write("accepted, response lost")
    print("queue response lost", file=sys.stderr)
    sys.exit(1)
print("queued")
"""
    )
    program.chmod(0o755)
    return program, log


def reaper_retires(page: Path, monkeypatch) -> bool:
    """Run the real lifetime decision for three cycles, advancing its grace clock.

    The HTTP process remains real and owns its own clock. Here the same reaper reads
    the real service and claim with controlled product time, so survival is observed
    after completed decisions rather than after a scheduling allowance.
    """
    clock = SimpleNamespace(now=0, cycles=0)

    class ChecksComplete(Exception):
        pass

    def next_check(_seconds):
        clock.cycles += 1
        clock.now += schema_model.ORPHAN_GRACE_SECS + 1
        if clock.cycles == 3:
            raise ChecksComplete

    def retire(code):
        assert code == 0
        raise SystemExit(code)

    with monkeypatch.context() as controlled:
        controlled.setattr(
            server_model,
            "time",
            SimpleNamespace(monotonic=lambda: clock.now, sleep=next_check),
        )
        controlled.setattr(server_model, "os", SimpleNamespace(_exit=retire))
        try:
            server_model.stop_when_service_ends(page)
        except ChecksComplete:
            return False
        except SystemExit:
            return True
    raise AssertionError("the reaper neither completed its checks nor retired")


def freeze_events(page_dir: Path, events: list[dict]) -> dict:
    """Freeze selected page events through the harness-neutral delivery boundary."""
    with service_model.PageTransaction(page_dir) as transaction:
        stored = {event["id"]: event for event in transaction.events}
        batch = delivery_model.batch_data(
            page_dir,
            transaction,
            [stored[event["id"]] for event in events],
        )
    return delivery_model.freeze_delivery(
        [batch], carrier="wait", acknowledge=session_model.wait_acknowledgement(None)
    )


def delivery_through(page_dir: Path, seq: int) -> str:
    """Freeze the complete deliverable prefix used to arrange a received fixture."""
    events = service_model.unacknowledged(events_model.read_events(page_dir), 0)
    return freeze_events(
        page_dir, [event for event in events if event["seq"] <= int(seq)]
    )["id"]


def receive_through(page_dir: Path, seq: int) -> None:
    service_model.claim_page(page_dir)
    delivery_model.receive_delivery(delivery_through(page_dir, seq))


def test_delivery_ids_are_short_and_rerolled_under_the_store_lock(monkeypatch):
    minted = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
    widths = []
    token_hex_real = delivery_model.secrets.token_hex

    def token_hex(width):
        if width != 4:
            return token_hex_real(width)
        widths.append(width)
        return next(minted)

    monkeypatch.setattr(delivery_model.secrets, "token_hex", token_hex)
    first = delivery_model.freeze_delivery([], carrier="wait", created_at=1)
    second = delivery_model.freeze_delivery([], carrier="wait", created_at=2)

    assert widths == [4, 4, 4]
    assert (first["id"], second["id"]) == ("aaaaaaaa", "bbbbbbbb")


def test_codex_readdresses_a_collecting_record_if_its_delivery_id_collides(
    page_dir, monkeypatch
):
    minted = iter(["aaaaaaaa", "bbbbbbbb"])
    monkeypatch.setattr(codex_model, "new_delivery_id", lambda: next(minted))
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hello"}
    )
    with service_model.PageTransaction(page_dir) as transaction:
        path, _, _ = codex_model.append_batch(
            "collision-test", page_dir, transaction, transaction.events
        )
    assert path.stem == "aaaaaaaa"
    delivery_model.freeze_delivery(
        [], carrier="wait", delivery_id=path.stem, created_at=0
    )

    prepared = codex_model.offer_delivery(path, files_model.read_json(path), "queue")

    assert prepared.payload["id"] == "bbbbbbbb"
    assert prepared.record_path == path.with_name("bbbbbbbb.json")
    assert prepared.record_path.is_file()
    assert not path.exists()


def test_a_start_names_the_exact_move_and_covers_its_threads_answer(page_dir):
    """`task start` takes the id a delivery names, which for a reply in a thread is
    that reply's id, and that move reads Working. A correction the user adds keeps its
    own receipt, and the start still covers it: the thread's one reply answers both,
    so the Stop hook reads the newest input as started (`started_by`)."""
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "first", "author": "user", "text": "Use A."},
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": first["id"],
            "responds": first["id"],
            "text": "Which A?",
        },
    )
    answer = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": first["id"], "text": "A1."},
    )
    [workflow] = page_state(page_dir)["workflows"]
    assert workflow["answer"]["to"] == answer["id"]

    started = _start(page_dir, answer["id"], "Answering the comment")
    assert started.exit_code == 0, started.output
    record = json.loads(started.output.splitlines()[-1])
    assert (record["kind"], record["item"]) == ("start", answer["id"])
    [workflow] = page_state(page_dir)["workflows"]
    assert (workflow["input"], workflow["stage"], workflow["detail"]) == (
        answer["id"],
        "working",
        "Answering the comment",
    )
    # The thread's answered root is no move the agent owes.
    assert _start(page_dir, first["id"], "Still on it").exit_code != 0

    correction = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": first["id"],
            "text": "Correction: use B.",
        },
    )
    assert _start(page_dir, answer["id"], "Still on it").exit_code == 0
    workflows = page_state(page_dir)["workflows"]
    assert [(item["input"], item["stage"]) for item in workflows] == [
        (answer["id"], "working"),
        (correction["id"], "sent"),
    ]
    newest = workflows[-1]
    assert newest["answer"]["for"] == correction["id"]
    assert [start["seq"] for start in newest["started_by"]] == [
        events_model.read_events(page_dir)[-1]["seq"]
    ]


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
    assert [
        (item["input"], item["answer"], item["next_actor"])
        for item in state["workflows"]
    ] == [
        (first["id"], None, "agent"),
        (
            second["id"],
            {"kind": "reply", "to": second["id"], "for": second["id"]},
            "agent",
        ),
    ]
    assert [item["input"] for item in state["activity"]["obligations"]] == [
        second["id"]
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
    failure = thread_model.cmd_reply(
        page_dir,
        source["id"],
        "The agent's turn ended without an answer. Send it again to retry.",
        None,
        for_event=source["id"],
        failure="turn_failed",
    )

    state = page_state(page_dir)
    [workflow] = state["workflows"]
    assert (
        workflow["input"],
        workflow["stage"],
        workflow["answer"],
        workflow["next_actor"],
        workflow["condition"],
    ) == (
        source["id"],
        "answered",
        None,
        "user",
        {"kind": "failed", "operation": "response"},
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
    assert state["activity"]["obligations"] == []
    # The move is the user's to resend, so the banner counts nothing as saved for
    # the agent to pick up.
    assert set(state["activity"]["counts"].values()) == {0}
    [thread] = state["browser"]["thread"]["threads"]
    assert thread["attention"] == {
        "kind": "needs_user",
        "reason": "recovery",
        "workflow": source["id"],
    }


def test_user_resend_clears_terminal_failure_recovery(page_dir):
    publish(page_dir)
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "failed-first", "author": "user", "text": "A"},
    )
    failure = thread_model.cmd_reply(
        page_dir,
        first["id"],
        "The agent's turn ended without an answer. Send it again to retry.",
        None,
        for_event=first["id"],
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
    assert [(item["input"], item["next_actor"]) for item in state["workflows"]] == [
        (resent["id"], "agent")
    ]
    [thread] = state["browser"]["thread"]["threads"]
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
    assert (workflow["input"], workflow["answer"]["for"]) == (
        second["id"],
        second["id"],
    )
    assert [item["input"] for item in state["activity"]["obligations"]] == [
        second["id"]
    ]


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
    assert [(item["input"], item["answer"]["for"]) for item in state["workflows"]] == [
        (third["id"], third["id"])
    ]


def test_unrelated_agent_update_does_not_clear_a_standing_user_ask(page_dir):
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
            "awaits": True,
            "text": "Which option?",
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

    [thread] = page_state(page_dir)["browser"]["thread"]["threads"]
    assert thread["user_prompt"]["message"] == question["id"]
    assert thread["attention"] == {
        "kind": "needs_user",
        "reason": "ask",
        "workflow": None,
    }


def test_settling_reaction_closes_an_agent_root_ask(page_dir):
    publish(page_dir)
    question = thread_model.cmd_comment(page_dir, "", "", "", "Is forty enough?", None)
    [before] = page_state(page_dir)["browser"]["thread"]["threads"]
    assert before["user_prompt"]["message"] == question["id"]
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

    [after] = page_state(page_dir)["browser"]["thread"]["threads"]
    assert after["user_prompt"] is None
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
            "detail": {"options": ["thread-east"]},
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
    [owed] = page_state(page_dir)["workflows"]
    assert owed["answer"]["to"] == asked["id"]
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
        for item in state["browser"]["thread"]["threads"]
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
    assert (workflow["input"], workflow["next_actor"], workflow["condition"]) == (
        answered["id"],
        "user",
        {"kind": "failed", "operation": "response"},
    )
    assert state["activity"]["obligations"] == []
    [thread] = state["browser"]["thread"]["threads"]
    assert thread["attention"] == {
        "kind": "needs_user",
        "reason": "recovery",
        "workflow": answered["id"],
    }


def test_a_frozen_move_that_answers_no_ask_keeps_a_receipt_and_owes_nothing(
    page_dir,
):
    """A card moved on a board sent in a reply is a page move in another document:
    it keeps its delivery receipt, owes the agent nothing, and leaves the thread
    nobody's turn. A claim makes it Working, and the agent's next turn in the
    thread takes it in."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    registry = json.loads((page_dir / "registry.json").read_text())
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
            "detail": {"card": "card-baffle", "to": "col-doing", "rank": "0i"},
        },
    )

    def reading():
        state = page_state(page_dir)
        [thread] = state["browser"]["thread"]["threads"]
        return state, thread["attention"]

    state, attention = reading()
    [workflow] = state["workflows"]
    assert (workflow["input"], workflow["subject"], workflow["stage"]) == (
        moved["id"],
        {"kind": "widget", "id": "feeder-board"},
        "sent",
    )
    assert workflow["answer"] is None
    assert state["activity"]["obligations"] == []
    assert attention is None

    delivery = freeze_events(page_dir, [moved])
    [event] = delivery["batches"][0]["events"]
    assert "answer" not in event
    # A move that owes nothing is still on the agent once it is started, and holds
    # the board's thread while it is.
    claimed = _start(page_dir, moved["id"], "Rearranging the cards")
    assert claimed.exit_code == 0, claimed.output
    state, attention = reading()
    [workflow] = state["workflows"]
    assert workflow["stage"] == "working"
    assert attention == {
        "kind": "waiting",
        "reason": "workflow",
        "workflow": moved["id"],
    }

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
            "detail": {"card": "card-baffle", "to": "col-done", "rank": "0i"},
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
            "detail": {"card": "card-heater", "to": "col-done", "rank": "0i"},
        },
    )
    state, attention = reading()
    [workflow] = state["workflows"]
    assert (workflow["input"], workflow["stage"], workflow["answer"]) == (
        later["id"],
        "sent",
        None,
    )
    assert attention is None


def test_thread_attention_names_the_workflow_the_thread_waits_on():
    """A thread's status reads the workflows that keep it the agent's turn. An input
    a newer one covers still does, so its pickup or a reply streaming to it keeps
    reading on the thread; a frozen move that owes nothing does not, so its further
    stage never stands in for the owed reply's."""

    def workflow(id, seq, subject, stage, answer=None):
        return {
            "id": id,
            "seq": seq,
            "subject": subject,
            "stage": stage,
            "answer": answer,
            "condition": None,
            "next_actor": "agent",
        }

    thread = {"id": "root", "kind": "thread"}
    board = {"kind": "widget", "id": "board"}
    owed = {"kind": "reply", "to": "newer", "for": "newer"}
    cases = [
        (
            [
                workflow("older", 1, thread, "replying"),
                workflow("newer", 2, thread, "sent", owed),
            ],
            "older",
        ),
        (
            [
                workflow("older", 1, thread, "picked_up"),
                workflow("newer", 2, thread, "sent", owed),
            ],
            "older",
        ),
        (
            [
                workflow("newer", 1, thread, "sent", owed),
                workflow("card-move", 2, board, "picked_up"),
            ],
            "newer",
        ),
    ]
    # Only which thread the board widget stands in matters here.
    frozen = projection_model.FrozenThreadReading(None, {}, {}, {"board": "root"}, None)
    for workflows, expected in cases:
        threads = [{"id": "root", "resolved": None, "user_prompt": None}]
        browser_served_model._apply_thread_attention(
            threads,
            {"user": []},
            browser_served_model.served_workflows(workflows, frozen),
            [{"id": "t1", "title": "Rebuild", "thread": "root", "running": None}],
        )
        assert threads[0]["attention"] == {
            "kind": "waiting",
            "reason": "workflow",
            "workflow": expected,
        }
    # With no workflow holding it, an open task keeps the thread on the agent.
    threads = [{"id": "root", "resolved": None, "user_prompt": None}]
    browser_served_model._apply_thread_attention(
        threads,
        {"user": []},
        [],
        [{"id": "t1", "title": "Rebuild", "thread": "root", "running": None}],
    )
    assert threads[0]["attention"] == {
        "kind": "waiting",
        "reason": "task",
        "workflow": None,
        "task": {"id": "t1", "title": "Rebuild", "line": None},
    }


def test_served_workflows_list_the_strongest_first():
    """Every surface that shows one workflow of several shows the first, so the served
    order is the one comparator: a move handed back to the user, then work under way,
    then an uncertain one, then plain delivery by stage, then the newer input. A
    failed response is the furthest stage a move reaches."""

    def workflow(id, seq, stage, condition=None, next_actor="agent"):
        return {
            "id": id,
            "seq": seq,
            "subject": {"kind": "thread", "id": "root"},
            "stage": stage,
            "answer": None,
            "condition": condition,
            "next_actor": next_actor,
        }

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
                workflow("back", 2, "answered", failed, "user"),
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
    for workflows, expected in cases:
        served = browser_served_model.served_workflows(workflows, frozen)
        assert [item["id"] for item in served] == expected


def test_a_start_on_a_page_move_holds_that_move_and_not_a_later_one(page_dir):
    """A start on a page widget's move holds that move; a later move on the widget,
    which supersedes it, is not in hand until the agent starts it."""
    version = page_dir / "index.html"
    version.write_text(
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>', 1)
    )
    publish(page_dir)
    chosen = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"options": ["flag-first"]},
        },
    )

    result = _start(page_dir, chosen["id"], "Building the flag")

    assert result.exit_code == 0, result.output
    [workflow] = page_state(page_dir)["workflows"]
    assert (workflow["input"], workflow["subject"], workflow["stage"]) == (
        chosen["id"],
        {"kind": "widget", "id": "choice"},
        "working",
    )
    later = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"options": ["backfill-first"]},
        },
    )
    assert [
        (item["input"], item["stage"])
        for item in page_state(page_dir)["workflows"]
        if item["input"] is not None
    ] == [(later["id"], "sent")]


def test_embedded_codex_delivery_is_durable_and_idempotent(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "make this editable"},
    )
    harness = harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid())

    prompt = codex_model.prepare_codex_delivery(page_dir, harness)
    assert codex_model.prepare_codex_delivery(page_dir, harness) == prompt
    cleanup_model.open_session_turn("hosted-thread", "app-turn")
    [accepted] = codex_model.accept_codex_delivery(
        "hosted-thread", prompt.payload["id"], "app-turn"
    )

    assert prompt.prompt.startswith("```xml\n<leaf-delivery ")
    assert 'operation="delivery read"' in prompt.prompt
    assert "skill=" not in prompt.prompt
    [batch] = prompt.payload["batches"]
    assert set(batch) == {"page", "through_seq", "threads", "handling", "events"}
    assert batch["events"][0]["id"] == comment["id"]
    claim = service_model.page_claim(page_dir)
    assert {key: claim[key] for key in ("id", "harness", "pid", "agent")} == {
        "id": "hosted-thread",
        "harness": "embedded",
        "pid": os.getpid(),
        "agent": "Leaf guide",
    }
    assert (claim["turn"], claim["turn_closed"]) == ("app-turn", None)
    assert accepted == {"page": page_dir, "events": (comment["id"],)}
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}
    activity = page_state(page_dir)["activity"]
    assert activity["kind"] == "working"
    assert activity["dropped"] is False
    assert activity["counts"]["handling"] == 1
    assert activity["obligations"][0]["delivery_turn"] == claim["turn"]
    [history] = (codex_state_model.delivery_dir("hosted-thread") / "history").glob(
        "*.json"
    )
    queue = files_model.read_json(history)
    assert queue["state"] == "accepted"
    assert queue["batches"][0]["receipted"] is True
    assert delivery_model.delivery_path(history.stem).is_file()


def test_only_one_turn_reply_can_bind_the_app_server_final_message():
    """A turn binds its messages to the delivery's one `turn` answer. A plain
    `reply` is `leaf thread reply`'s even when a turn Leaf observes picks the delivery up,
    as it does a pointer queued before Leaf observed the task."""

    def payload(*answers):
        return {
            "id": "delivery-1",
            "batches": [
                {
                    "page": "/tmp/page",
                    "events": [{"answer": answer} for answer in answers],
                }
            ],
        }

    def turn(to, event):
        return {"kind": "turn", "to": to, "for": event, "attempt": "leaf-delivery-1"}

    assert codex_model.stream_reply_target(payload(turn("thread-1", "event-1"))) == {
        "page": "/tmp/page",
        "reply_to": "thread-1",
        "responds": "event-1",
    }
    assert (
        codex_model.stream_reply_target(
            payload({"kind": "reply", "to": "thread-1", "for": "event-1"})
        )
        is None
    )
    assert (
        codex_model.stream_reply_target(
            payload({"kind": "markup", "action": "event-1"})
        )
        is None
    )
    assert codex_model.stream_reply_target(
        payload(
            turn("thread-1", "event-1"),
            {"kind": "markup", "action": "event-2"},
        )
    ) == {
        "page": "/tmp/page",
        "reply_to": "thread-1",
        "responds": "event-1",
    }
    assert (
        codex_model.stream_reply_target(
            payload(turn("thread-1", "event-1"), turn("thread-2", "event-2"))
        )
        is None
    )


def test_a_completed_stream_answers_its_event_even_when_the_reply_address_differs():
    obligation = {
        "input": "widget-action",
        "seq": 1,
        "stage": "picked_up",
        "answer": {
            "kind": "turn",
            "to": "widget-owner-thread",
            "for": "widget-action",
            "attempt": "leaf-delivery-1",
        },
        "response": {
            "state": "active",
            "settles": True,
            "has_text": True,
            "session": "codex-thread",
            "turn": "leaf-turn",
            "reply_to": "widget-owner-thread",
            "responds": "widget-action",
        },
    }

    def blocking(obligation: dict, *, carried: bool) -> list[dict]:
        state = {
            "activity": {"obligations": [obligation]},
            "cursor": 1,
            "claim_turn": "leaf-turn",
        }
        return activity_model.blocking_obligations(state, carried=carried)

    assert blocking(obligation, carried=True) == []
    # Nothing is left to commit the draft once its carrier is gone.
    assert blocking(obligation, carried=False) == [obligation]
    # A plain reply is `leaf thread reply`'s to write, whatever a draft says.
    plain = {**obligation, "answer": {**obligation["answer"], "kind": "reply"}}
    assert blocking(plain, carried=True) == [plain]


def test_embedded_codex_delivery_keeps_non_obligation_events_in_the_page_batch(
    page_dir,
):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "never mind"},
    )
    resolved = append_carried_log_record(
        page_dir,
        {"kind": "resolve", "author": "user", "parent": comment["id"]},
    )

    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )

    [batch] = prepared.payload["batches"]
    assert [event["id"] for event in batch["events"]] == [
        comment["id"],
        resolved["id"],
    ]
    assert batch["through_seq"] == 2


def test_embedded_codex_delivery_keeps_steered_input_in_one_claim_turn(page_dir):
    harness = harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid())
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "make this editable"},
    )
    prepared = codex_model.prepare_codex_delivery(page_dir, harness)
    cleanup_model.open_session_turn("hosted-thread", "app-turn")
    codex_model.accept_codex_delivery(
        "hosted-thread", prepared.payload["id"], "app-turn"
    )
    first_turn = service_model.page_claim(page_dir)["turn"]

    second = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "also change the title"},
    )
    prepared = codex_model.prepare_codex_delivery(page_dir, harness)
    codex_model.accept_codex_delivery(
        "hosted-thread", prepared.payload["id"], "app-turn"
    )

    claim = service_model.page_claim(page_dir)
    state = page_state(page_dir)
    activity = state["activity"]
    interactions = {
        item["input"]: item
        for item in state["workflows"]
        if item.get("input") in {first["id"], second["id"]}
    }
    assert claim["turn"] == first_turn
    assert activity["counts"]["handling"] == 2
    assert activity["counts"]["picked_up"] == 0
    assert all(item["condition"] is None for item in interactions.values())


def test_embedded_codex_delivery_retries_the_same_immutable_pointer(page_dir):
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "make this editable"},
    )
    harness = harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid())
    first = codex_model.prepare_codex_delivery(page_dir, harness)

    second = codex_model.prepare_codex_delivery(page_dir, harness)

    assert second == first
    [(path, queue)] = codex_model.delivery_records("hosted-thread")
    payload = files_model.read_json(delivery_model.delivery_path(path.stem))
    assert queue["state"] == "offering"
    assert [event["text"] for event in payload["batches"][0]["events"]] == [
        "make this editable"
    ]


def test_embedded_codex_delivery_abandons_only_its_mutable_delivery_record(page_dir):
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    harness = harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid())
    first_prompt = codex_model.prepare_codex_delivery(page_dir, harness)
    [(first_path, _)] = codex_model.delivery_records("hosted-thread")
    first_payload = delivery_model.delivery_path(first_path.stem)

    codex_model.abandon_codex_delivery("hosted-thread", first["id"])
    thread_model.cmd_reply(
        page_dir,
        first["id"],
        "try again later",
        None,
        for_event=first["id"],
        identity={"agent": "Leaf guide", "session": "website-agent"},
    )
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    second_prompt = codex_model.prepare_codex_delivery(page_dir, harness)

    assert codex_model.delivery_records("hosted-thread")[0][1]["state"] == "offering"
    assert second_prompt != first_prompt
    assert first_payload.is_file()


def test_embedded_codex_delivery_keeps_settled_input_in_the_complete_page_batch(
    page_dir,
):
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    first = events_model.read_events(page_dir)[-1]
    thread_model.cmd_reply(
        page_dir,
        first["id"],
        "try again later",
        None,
        for_event=first["id"],
        identity={"agent": "Leaf guide", "session": "website-agent"},
    )
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )

    codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )

    [(path, _queue)] = codex_model.delivery_records("hosted-thread")
    payload = files_model.read_json(delivery_model.delivery_path(path.stem))
    delivered_events = payload["batches"][0]["events"]
    assert [event["text"] for event in delivered_events] == ["first", "second"]
    assert "answer" not in delivered_events[0]
    assert delivered_events[1]["answer"]["for"] == delivered_events[1]["id"]


def test_embedded_codex_delivery_keeps_page_actions_before_a_comment(page_dir):
    work_page = PAGE.replace(
        "<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1
    )
    (page_dir / "index.html").write_text(work_page)
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
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "change the explanation"},
    )

    codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )

    [(path, _queue)] = codex_model.delivery_records("hosted-thread")
    payload = files_model.read_json(delivery_model.delivery_path(path.stem))
    assert [event["id"] for event in payload["batches"][0]["events"]] == [
        action["id"],
        comment["id"],
    ]


@pytest.fixture
def app_server():
    """Serve an App Server stand-in for one handler, until the test ends.

    The observer under test connects over a real websocket, so a test that made its
    own server owned three things: the server, the thread serving it, and the stop
    that ends both. One of them ran that stop on the last line of the test body,
    which is the line a failing assertion never reaches — the thread then served on
    for the rest of the worker, holding its socket, under later tests that had
    nothing to do with it.

    Returns the endpoint to connect to: a loopback port, or the Unix socket path the
    caller names.
    """
    serving = []

    def serve(handle, socket_path=None) -> str:
        server = (
            serve_unix_websocket(handle, str(socket_path))
            if socket_path
            else serve_websocket(handle, "127.0.0.1", 0)
        )
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        serving.append((server, worker))
        return (
            f"unix://{socket_path}"
            if socket_path
            else f"ws://127.0.0.1:{server.socket.getsockname()[1]}"
        )

    yield serve
    for server, worker in reversed(serving):
        server.shutdown()
        worker.join(timeout=STATED_TIMEOUT)


def titling_app_server(app_server, answer: str) -> tuple[str, list[dict]]:
    """An App Server that answers each titling thread with `answer`."""
    received = []

    def handle(socket):
        for raw in socket:
            message = json.loads(raw)
            received.append(message)
            method = message.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": message["id"], "result": {}}))
            elif method == "config/read":
                servers = {"docs": {"command": "docs-server", "enabled": True}}
                config = {"config": {"mcp_servers": servers}}
                socket.send(json.dumps({"id": message["id"], "result": config}))
            elif method == "thread/start":
                thread = {"thread": {"id": "title-thread"}}
                socket.send(json.dumps({"id": message["id"], "result": thread}))
            elif method == "turn/start":
                socket.send(
                    json.dumps({"id": message["id"], "result": {"turn": {"id": "t"}}})
                )
                for notification in (
                    {
                        "method": "item/completed",
                        "params": {
                            "threadId": "title-thread",
                            "item": {"type": "agentMessage", "text": answer},
                        },
                    },
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "title-thread",
                            "turn": {"id": "t", "status": "completed"},
                        },
                    },
                ):
                    socket.send(json.dumps(notification))

    return app_server(handle), received


def test_an_app_server_turn_names_the_untitled_thread_it_answers(page_dir, app_server):
    """A turn over App Server writes its reply with its own messages, so it has no
    `--title` to name the thread with; the carrier names it beside the turn, from
    the opening message and the passage it is on, and the delivery does not ask the
    turn to."""
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Why does the export take a minute?",
            "anchor": {"section": None, "quote": "Export runs nightly"},
        },
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    [batch] = prepared.payload["batches"]
    [delivered] = batch["events"]
    assert delivered["answer"]["kind"] == "turn"
    assert not any("title" in text for text in batch["handling"].values())

    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    records = []
    thread_titles.name_untitled_threads(
        thread_titles.app_server_title(endpoint, "light-model"),
        prepared.payload,
        "hosted-thread",
        lambda event, **fields: records.append((event, fields)),
    )
    wait_for(lambda: records, bool, failure="the title was never generated")

    [(event, fields)] = records
    assert (event, fields["written"]) == ("thread_title_generated", True)
    [title] = [
        e for e in events_model.read_events(page_dir) if e["kind"] == "thread_title"
    ]
    assert (title["thread"], title["title"]) == (comment["id"], "Export speed")
    assert (title["agent"], title["session"]) == ("Leaf guide", "hosted-thread")
    [start] = [m for m in received if m.get("method") == "thread/start"]
    assert start["params"]["ephemeral"] is True
    assert start["params"]["model"] == "light-model"
    # The user's MCP servers would start with the thread and list their tools to it.
    assert start["params"]["config"]["mcp_servers"] == {"docs": {"enabled": False}}
    # Both read the page's directory, so a project's own servers are among them.
    [read] = [m for m in received if m.get("method") == "config/read"]
    assert read["params"]["cwd"] == start["params"]["cwd"]
    assert Path(start["params"]["cwd"]).resolve() == page_dir.resolve()
    [turn] = [m for m in received if m.get("method") == "turn/start"]
    [text] = turn["params"]["input"]
    assert "Why does the export take a minute?" in text["text"]
    assert "Export runs nightly" in text["text"]


def test_a_title_is_drawn_from_the_opening_message_not_the_latest(page_dir, app_server):
    """The turn answers the thread's latest message, which may be an afterthought;
    the title comes from the message that opened it."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Why is the export slow?"},
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": comment["id"],
            "text": "also, thanks",
        },
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    records = []
    thread_titles.name_untitled_threads(
        thread_titles.app_server_title(endpoint, None),
        prepared.payload,
        "hosted-thread",
        lambda event, **fields: records.append((event, fields)),
    )
    wait_for(lambda: records, bool, failure="the title was never generated")

    [turn] = [m for m in received if m.get("method") == "turn/start"]
    [text] = turn["params"]["input"]
    assert "Why is the export slow?" in text["text"]
    assert "thanks" not in text["text"]


def test_a_generated_title_yields_to_one_the_agent_wrote_first(page_dir, app_server):
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Tighten the intro"}
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    append_command(
        page_dir,
        {
            "kind": "thread_title",
            "author": "agent",
            "agent": "Leaf guide",
            "session": "hosted-thread",
            "thread": comment["id"],
            "title": "Intro",
        },
    )
    endpoint, _ = titling_app_server(app_server, '{"title": "Shorter intro"}')
    records = []
    thread_titles.name_untitled_threads(
        thread_titles.app_server_title(endpoint, None),
        prepared.payload,
        "hosted-thread",
        lambda event, **fields: records.append((event, fields)),
    )
    wait_for(lambda: records, bool, failure="the title was never generated")

    assert records[0][1]["written"] is False
    titles = [
        e["title"]
        for e in events_model.read_events(page_dir)
        if e["kind"] == "thread_title"
    ]
    assert titles == ["Intro"]


TITLING_CLAUDE = """\
#!{python}
import json, os, sys
with open(os.environ["TITLING_RECORD"], "a") as record:
    call = {{"argv": sys.argv[1:], "stdin": sys.stdin.read(), "env": dict(os.environ)}}
    record.write(json.dumps(call) + "\\n")
print(json.dumps({{
    "structured_output": {{"title": " Export speed "}},
    "duration_api_ms": 900,
    "usage": {{"input_tokens": 1100, "output_tokens": 60}},
}}))
"""


def test_a_comment_on_a_claude_code_page_is_named_as_it_arrives(
    claimed, tmp_path, monkeypatch
):
    """Claude Code's agent names a thread only when it replies, which can be minutes
    on; its page server asks Haiku for a title as the comment opening the thread
    arrives, in the claimant's voice, with none of the user's customizations, tools
    or session identity."""
    programs = tmp_path / "programs"
    programs.mkdir()
    claude = programs / "claude"
    claude.write_text(TITLING_CLAUDE.format(python=sys.executable))
    claude.chmod(0o755)
    record = tmp_path / "claude-calls.jsonl"
    monkeypatch.setenv("TITLING_RECORD", str(record))
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")
    assert stamp(claimed, "first").exit_code == 0

    status, body = endpoint_model.accept_event(
        claimed,
        {
            "kind": "comment",
            "revision": 1,
            "text": "Why does the export take a minute?",
        },
        dict,
    )
    assert status == 200, body
    titles = wait_for(
        lambda: [
            e for e in events_model.read_events(claimed) if e["kind"] == "thread_title"
        ],
        bool,
        failure="the thread was never named",
    )
    [comment] = [e for e in events_model.read_events(claimed) if e["kind"] == "comment"]
    [title] = titles
    assert (title["thread"], title["title"]) == (comment["id"], "Export speed")
    assert (title["agent"], title["session"]) == ("Claude", "s1")

    [call] = [json.loads(line) for line in record.read_text().splitlines()]
    assert "Why does the export take a minute?" in call["stdin"]
    assert "CLAUDE_CODE_SESSION_ID" not in call["env"]
    assert call["env"]["MAX_THINKING_TOKENS"] == "0"
    assert call["env"]["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"

    # The page server's output goes nowhere, so the session's log says what the
    # request did, until the session ends.
    log = leases_model.titles_log("s1")
    [line] = wait_for(
        lambda: log.read_text().splitlines() if log.exists() else [],
        bool,
        failure="the request was never logged",
    )
    logged = json.loads(line)
    assert logged["event"] == "thread_title_generated"
    assert logged["apiDurationMs"] == 900
    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "s1"})
    assert not log.exists()


def test_a_title_request_that_outlives_its_session_leaves_no_log(claimed):
    """SessionEnd removes the session's titles log, and a request still waiting on
    the model when it runs finishes after that; it writes neither the title nor a
    new log."""
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Tighten the intro"}
    )
    answered = threading.Event()

    def generate(request: str, page_dir: Path) -> dict:
        answered.wait(timeout=STATED_TIMEOUT)
        return {"title": "Intro"}

    thread_titles.name_opened_thread(generate, claimed, comment["id"], "s1")
    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "s1"})
    answered.set()
    for worker in threading.enumerate():
        if worker.name == "leaf-thread-title":
            worker.join(timeout=STATED_TIMEOUT)

    assert not leases_model.titles_log("s1").exists()
    kinds = [e["kind"] for e in events_model.read_events(claimed)]
    assert "thread_title" not in kinds


def test_both_harnesses_are_asked_for_a_title_in_the_same_words(
    page_dir, app_server, tmp_path, monkeypatch, snapshot
):
    """Claude Code's `claude -p` and an App Server carrier are sent the same system
    prompt, request and answer schema; the snapshot is that request, verbatim."""
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Why does the export take a minute?",
            "anchor": {"section": None, "quote": "Export runs nightly"},
        },
    )
    request = thread_titles.title_request(page_dir, comment["id"])

    programs = tmp_path / "programs"
    programs.mkdir()
    claude = programs / "claude"
    claude.write_text(TITLING_CLAUDE.format(python=sys.executable))
    claude.chmod(0o755)
    record = tmp_path / "claude-calls.jsonl"
    monkeypatch.setenv("TITLING_RECORD", str(record))
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")
    thread_titles.claude_code_title(request, page_dir)
    [call] = [json.loads(line) for line in record.read_text().splitlines()]
    argv = call["argv"]
    system_prompt = argv[argv.index("--system-prompt") + 1]
    schema = json.loads(argv[argv.index("--json-schema") + 1])

    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    thread_titles.app_server_title(endpoint, None)(request, page_dir)
    [start] = [m for m in received if m.get("method") == "thread/start"]
    [turn] = [m for m in received if m.get("method") == "turn/start"]
    assert start["params"]["baseInstructions"] == system_prompt
    assert turn["params"]["input"] == [{"type": "text", "text": call["stdin"]}]
    assert turn["params"]["outputSchema"] == schema

    placeholders = {system_prompt: "<system_prompt>", json.dumps(schema): "<schema>"}
    snapshot.check(
        yaml_document(
            "What Claude Code's page server runs, what it and an App Server carrier "
            "both send, and\nthe App Server's titling thread, for a thread opened "
            "on a passage.",
            {
                "command": ["claude", *(placeholders.get(a, a) for a in argv)],
                "system_prompt": Prose(system_prompt),
                "request": Prose(call["stdin"]),
                "schema": schema,
                "app_server_thread": {
                    key: start["params"][key]
                    for key in ("ephemeral", "approvalPolicy", "sandbox", "config")
                },
                "app_server_effort": turn["params"]["effort"],
            },
        )
    )


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
                        "turn": {"id": "turn-live"},
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
                        "turn": {"id": "turn-live"},
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
                        "turn": {"id": "turn-next"},
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
                        "turn": {"id": "turn-next"},
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


def codex_records(session_id: str) -> list[tuple[Path, dict]]:
    directory = codex_state_model.delivery_dir(session_id)
    return [
        (path, files_model.read_json(path)) for path in sorted(directory.glob("*.json"))
    ]


def adapter_log(session_id: str) -> str:
    return codex_adapter_model.adapter_log_path(session_id).read_text(encoding="utf-8")


def current_codex_record(session_id: str) -> tuple[Path, dict]:
    current = [
        (path, epoch)
        for path, epoch in codex_records(session_id)
        if epoch["state"] == "collecting"
    ]
    assert len(current) == 1
    return current[0]


def test_a_start_is_one_log_record_read_at_the_banner_and_the_move(
    page_dir, capsys, monkeypatch
):
    """`leaf task start` writes one record, in the log rather than the status file:
    the page's banner reads its line, and so does the receipt on the move it names,
    under the user's own words. A pickup leaves it standing, a `waiting` declaration
    puts it down, and the move's answer ends it."""
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "why?"}
    )
    assert "neither an open task nor a move you owe" in (
        _start(page_dir, "nope", "reading the traces").output
    )
    assert _start(page_dir, "c1", "").exit_code != 0

    monkeypatch.setenv("LEAF_AGENT", "Trace reader")
    started = _start(page_dir, "c1", "reading the traces")
    assert started.exit_code == 0, started.output
    record = json.loads(started.output.splitlines()[-1])
    assert (record["item"], record["text"], record["agent"]) == (
        "c1",
        "reading the traces",
        "Trace reader",
    )
    assert "work" not in (files_model.read_json(page_dir / "status.json") or {})
    live = page_state(page_dir)
    assert "claims" not in live
    [workflow] = live["workflows"]
    assert (workflow["stage"], workflow["detail"], workflow["agent"]) == (
        "working",
        "reading the traces",
        "Trace reader",
    )
    assert live["activity"]["detail"] == "reading the traces"

    # A waiting line answers nothing on the thread, but it puts the start down: the
    # move is no longer in hand until the agent starts it again.
    assert _status(page_dir, "waiting", "look at v2").exit_code == 0
    assert [item["stage"] for item in page_state(page_dir)["workflows"]] == ["sent"]
    assert _start(page_dir, "c1", "reading the traces").exit_code == 0

    # Nor does a pickup replace the start: it is a durable transport fact about the
    # exact user events.
    serving(page_dir, 1)
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
    state = page_state(page_dir)
    assert [
        (workflow["input"], workflow["stage"]) for workflow in state["workflows"]
    ] == [("c1", "working"), ("c2", "sent")]
    activity = state["activity"]
    assert (activity["counts"]["total"], activity["counts"]["active"]) == (1, 0)
    assert session_model.cmd_wait(page_dir) == 0
    delivered(capsys)
    pickup = events_model.read_events(page_dir)[-1]
    assert pickup["kind"] == "pickup"
    assert pickup["events"] == ["c1", "c2"]
    assert [
        (workflow["input"], workflow["stage"])
        for workflow in page_state(page_dir)["workflows"]
    ] == [("c1", "working"), ("c2", "picked_up")]

    # The reply that answers the thread ends the start with the moves it answers.
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            ["thread", "reply", str(page_dir), "--for", "c2", "--text", "Because."],
        )
        .exit_code
        == 0
    )
    assert page_state(page_dir)["workflows"] == []


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


def test_a_widget_task_outlives_its_seat_but_not_its_widget(page_dir):
    """A widget's `x-work` admits a task on it; once open, the task stands beside the
    widget even when a later layer of the page drops that seat, and a version that
    removes the widget itself is refused until it completes the task."""
    work_page = PAGE.replace(
        '<lf-diagram id="flow">',
        '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
        '  <lf-card id="rollout-card"><strong>Ship the rollout</strong> '
        "Check the fallback before cutover.</lf-card>\n"
        '</lf-column></lf-board>\n<lf-diagram id="flow">',
    )
    (page_dir / "index.html").write_text(work_page)
    publish(page_dir)
    opened = CliRunner().invoke(
        cli_model.cli,
        ["task", "open", str(page_dir), "rollout-card", "Check the rollout"],
    )
    assert opened.exit_code == 0, opened.output
    task = json.loads(opened.output.splitlines()[-1])

    # Replacing the prose widget with a data widget removes its x-work seat, but the
    # page-edge margin entry remains attached to the same live subject, so the task
    # survives this unrelated version.
    without_seat = re.sub(
        r'<lf-board id="rollout">.*?</lf-board>',
        '<div id="rollout"><div id="rollout-now">'
        '<lf-diagram id="rollout-card"><pre>graph LR\n  A --> B\n</pre></lf-diagram>'
        "</div></div>",
        work_page,
        count=1,
        flags=re.DOTALL,
    )
    (page_dir / "index.html").write_text(without_seat)
    changed = stamp(page_dir, "Changed presentation")
    assert changed.exit_code == 0, changed.output
    assert [item["id"] for item in state_json(page_dir)["tasks"]] == [task["id"]]

    # Removing the subject itself would remove the margin entry. Publication refuses
    # that silent loss until the version names the task it completes.
    without_target = re.sub(
        r'<lf-diagram id="rollout-card">.*?</lf-diagram>',
        "",
        without_seat,
        count=1,
        flags=re.DOTALL,
    )
    (page_dir / "index.html").write_text(without_target)
    dropped = stamp(page_dir, "Removed")
    assert dropped.exit_code == 1
    assert "would remove the target of the open task on 'rollout-card'" in (
        dropped.output
    )
    finished = stamp(page_dir, "Removed", completes=("rollout-card",))
    assert finished.exit_code == 0, finished.output
    assert state_json(page_dir)["tasks"] == []


def test_a_delivery_and_its_codex_records_go_once_their_pages_do(
    claimed, capsys, tmp_path
):
    """Readable delivery records disappear once their pages do. Other versions'
    records survive every shared-directory scan, because their sessions may
    still need them."""
    gone = tmp_path / "gone"

    def record(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        cleanup_model.write_json(path, value)
        return path

    def envelope(delivery_id, page, format=delivery_model.DELIVERY_FORMAT):
        batches = [{"page": str(page)}]
        return record(
            delivery_model.delivery_path(delivery_id),
            {"format": format, "batches": batches},
        )

    kept = envelope("0000000a", claimed)
    retired = envelope("0000000b", gone)
    unreadable = [
        envelope("0000000c", claimed, "v2"),
        record(delivery_model.delivery_path("00000012"), {"batches": []}),
        record(
            delivery_model.delivery_path("00000013"),
            {"format": delivery_model.DELIVERY_FORMAT},
        ),
    ]
    serving(claimed, 1)
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "new input"}
    )
    assert session_model.cmd_wait(claimed) == 0
    payload, _, _ = delivered(capsys)
    frozen = delivery_model.delivery_path(payload["id"])
    assert kept.exists() and frozen.exists()
    assert not retired.exists()
    assert all(path.exists() for path in unreadable)

    def task_record(delivery_id, page, **fields):
        return {
            "format": codex_model.RECORD_FORMAT,
            "state": "accepted",
            "created_at": 0,
            "transport": {"phase": "queued", "turn": None},
            "batches": [
                {
                    "page": str(page),
                    "session": "t",
                    "receipted": True,
                    "events": [{"id": "captured", "seq": 1}],
                }
            ],
            **fields,
        }

    live = record(codex_model.record_path("t", "0000000d"), task_record("d", claimed))
    stale = record(codex_model.record_path("t", "0000000e"), task_record("e", gone))
    history = live.parent / "history"
    archived_gone = record(history / "0000000f.json", task_record("f", gone))
    archived_other = record(history / "00000010.json", {"batches": []})
    archived_incomplete = record(
        history / "00000012.json", {"format": codex_model.RECORD_FORMAT}
    )
    archived_kept = record(history / "00000011.json", task_record("g", claimed))
    archived_foreign = record(
        history / "00000014.json",
        task_record("h", claimed, format="another-version"),
    )
    with cleanup_model.flocked(codex_state_model.delivery_lock_path("t")):
        assert [path for path, _ in codex_model.delivery_records("t")] == [live]
        assert not stale.exists()
        codex_model.archive_record(live, task_record("d", claimed, state="accepted"))
    assert sorted(history.iterdir()) == sorted(
        [
            history / live.name,
            archived_kept,
            archived_other,
            archived_incomplete,
            archived_foreign,
        ]
    )
    assert not archived_gone.exists()
    codex_model.retire_gone_task_records()
    assert all(
        path.exists()
        for path in (
            archived_kept,
            archived_foreign,
            archived_other,
            archived_incomplete,
        )
    )


def test_a_claimant_inside_a_turn_is_listening_between_two_waits(claimed):
    """A wait that ends to wake the session leaves no lease behind, but the turn it
    reaches, or opens, takes the input, so the banner keeps reading listening rather
    than telling the user the agent is away. Once the turn has closed, it is away."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "look at v2")
    claim = service_model.page_claim(claimed)
    with service_model.PageTransaction(claimed) as transaction:
        transaction.open_turn(claim["id"])
    assert page_state(claimed)["listening"] is False
    assert page_state(claimed)["activity"]["kind"] == "listening"

    with service_model.PageTransaction(claimed) as transaction:
        transaction.close_turn(claim["id"])
    assert page_state(claimed)["activity"]["kind"] == "away"


def test_only_a_fresh_turn_whose_hooks_take_input_reads_listening(
    claimed, codex_claimed_page
):
    """Listening between two waits rests on the open turn taking the input, which
    only hooks that carry it do, and only while the turn is plausibly running. A
    Codex task's carrier is a process of its own, so its open turn with no adapter
    lease is nobody listening; and a Claude Code turn no Stop closed, as an
    interrupted one, stops counting once nothing in it has renewed it for the
    working grace: its opening, or a status written during it."""
    now = datetime.now().astimezone()
    for page in (claimed, codex_claimed_page):
        cleanup_model.write_json(
            page / "status.json",
            {"state": "waiting", "detail": "", "ts": now.isoformat(), "after": 0},
        )
    codex = page_state(codex_claimed_page)
    # Every other clause of the rule holds, so only the carrier can read it away.
    assert codex["session_alive"] is True
    assert codex["claim_turn"] and codex["turn_closed"] is None
    assert codex["turn_opened"] and not codex["turn_takes_input"]
    assert codex["listening"] is False
    assert codex["activity"]["kind"] == "away"

    assert page_state(claimed)["activity"]["kind"] == "listening"
    claim = service_model.page_claim(claimed)

    # A stale status does not mask the open turn's own deadline: with the status
    # already quiet, listening's only remaining source is the turn, so its own
    # working-grace boundary must still be scheduled, or the browser is left
    # showing Listening past the point the turn can plausibly still be running.
    opened = (now - timedelta(minutes=1)).replace(microsecond=0)
    record_claim(claimed, **{**claim, "turn_opened": opened.isoformat()})
    cleanup_model.write_json(
        claimed / "status.json",
        {"state": "waiting", "detail": "", "ts": "2020-01-01T00:00:00+00:00"},
    )
    listening = page_state(claimed)["activity"]
    assert listening["kind"] == "listening"
    assert (
        listening["next_transition_at"]
        == (opened + activity_model.WORKING_GRACE).isoformat()
    )

    # The fresh turn is someone there under a start gone stale too, so that old work
    # reads stalled rather than away, until its task ends.
    old_start = declare_work(
        claimed, "an old task", ts="2020-01-01T00:00:00+00:00", session="s1"
    )
    assert page_state(claimed)["activity"]["kind"] == "stalled"
    ended = CliRunner().invoke(
        cli_model.cli, ["task", "end", str(claimed), old_start["item"], "done"]
    )
    assert ended.exit_code == 0, ended.output
    claim = service_model.page_claim(claimed)
    opened = now - activity_model.WORKING_GRACE - timedelta(minutes=1)
    record_claim(
        claimed, **{**claim, "turn_opened": opened.isoformat(timespec="seconds")}
    )
    cleanup_model.write_json(
        claimed / "status.json",
        {"state": "waiting", "detail": "", "ts": opened.isoformat(), "after": 0},
    )
    stale = page_state(claimed)
    assert (stale["turn_takes_input"], stale["turn_closed"]) == (True, None)
    assert stale["activity"]["kind"] == "away"

    # A status the turn writes renews it: the agent is there to have written it.
    cleanup_model.write_json(
        claimed / "status.json",
        {"state": "waiting", "detail": "", "ts": now.isoformat(), "after": 0},
    )
    assert page_state(claimed)["activity"]["kind"] == "listening"

    # A claim an older Leaf wrote, with no `turn_opened`, owes no belief either.
    lifecycle = cleanup_model.session_record("s1")
    cleanup_model.write_json(
        cleanup_model.session_file("s1", cleanup_model.SESSION_SUFFIX),
        {key: value for key, value in lifecycle.items() if key != "turn_opened"},
    )
    assert page_state(claimed)["activity"]["kind"] == "unheld"


def test_direct_delivery_progress_does_not_become_page_activity(claimed, capsys):
    """Delivery stays exact interaction evidence while page activity continues to
    describe the claimant's availability and independently declared work."""
    serving(claimed, 1)
    declare_work(claimed, "an old task", ts="2020-01-01T00:00:00+00:00")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "new input"}
    )

    assert session_model.cmd_wait(claimed) == 0
    delivered(capsys)
    activity = page_state(claimed)["activity"]
    assert activity["kind"] == "working"
    assert [item["stage"] for item in activity["obligations"]] == ["picked_up"]
    agent_state = state_json(claimed)
    agent_activity = agent_state["activity"]
    assert agent_activity["kind"] == activity["kind"]
    # The agent reading names each obligation by id; the move itself is listed once.
    [move] = owed(agent_state)
    assert agent_activity["obligations"] == [move["id"]]
    assert move["subject"] == {"kind": "thread", "id": comment["id"]}
    assert "acknowledgments" not in page_state(claimed)["browser"]
    pickup = events_model.read_events(claimed)[-1]
    claim = service_model.page_claim(claimed)
    assert (pickup["phase"], pickup["session"], pickup["turn"]) == (
        "opened",
        claim["id"],
        claim["turn"],
    )

    end_work(claimed)
    session_model.cmd_waiting(claimed, "review the answer")
    assert page_state(claimed)["activity"]["kind"] == "working"

    with service_model.PageTransaction(claimed) as transaction:
        transaction.close_turn(claim["id"])
    ended = page_state(claimed)["activity"]
    assert ended["kind"] == "away"
    assert ended["obligations"][0]["condition"] == {
        "kind": "ended",
        "operation": "work",
    }

    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, claim["id"])
    )
    assert lease
    append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": "answered",
        },
    )
    settled = page_state(claimed)["activity"]
    assert settled["kind"] == "listening"
    assert settled["obligations"] == []
    leases_model.release_lease(lease)


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


def _activity_at(page, minutes=0):
    """The page's activity as the server would read it `minutes` from now."""
    now = datetime.now().astimezone() + timedelta(minutes=minutes)
    events = events_model.read_events(page)
    return served_page.full_state(page, events, now=now.isoformat())["activity"]


def test_claude_codes_own_record_adds_what_no_hook_sees(claimed, capsys, dead_pid):
    """Claude Code publishes each session's live status in its session registry,
    dated by its last change: `idle` (or `shell`, with a background command) once no
    turn runs, `waiting` while a turn holds a dialog open, `busy` otherwise. An
    interrupt runs no Stop hook, so an `idle` newer than everything that renewed the
    turn ends it at that moment, and a `waiting` newer than the turn's stamps is
    a dialog open now. `busy` adds nothing: a background job's record keeps it
    across turn endings. Without a word from the record the hook stamps answer,
    believed
    only while something renewed the turn within the working grace, so a delivered
    move no Stop closed cannot read working forever."""
    serving(claimed, 1)
    registry = harness_model.claude_code_sessions()
    registry.mkdir(parents=True, exist_ok=True)

    live = os.getpid()

    def harness_says(status, *, pid=live, ago=0):
        cleanup_model.write_json(
            registry / f"{pid}.json",
            {
                "pid": pid,
                "sessionId": "s1",
                "status": status,
                "statusUpdatedAt": int((time.time() - ago) * 1000),
            },
        )

    session_model.cmd_waiting(claimed, "Pick a layout")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Tighten the lede."}
    )
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    delivered = json.loads(context.split("\n")[1])
    assert (
        CliRunner()
        .invoke(cli_model.cli, ["delivery", "ack", delivered["id"]])
        .exit_code
        == 0
    )

    # The stamps answer, and nothing renews this turn past the grace; `busy`, and
    # a record whose process is gone, change nothing.
    harness_says("busy")
    harness_says("waiting", pid=dead_pid)
    assert _activity_at(claimed)["kind"] == "working"
    unrenewed = _activity_at(claimed, 16)
    assert unrenewed["counts"]["handling"] == 0
    assert unrenewed["obligations"][0]["condition"] == {
        "kind": "stale",
        "operation": "work",
    }

    # A dialog in the terminal is observed work the page announces.
    harness_says("waiting")
    waiting = _activity_at(claimed)
    assert (waiting["kind"], waiting["observed_kind"]) == ("working", "awaiting_user")

    # Escape: the turn ended with no Stop hook, and the move it held reads Turn
    # ended at once.
    harness_says("idle")
    assert service_model.page_claim(claimed)["turn_closed"] is None
    assert _activity_at(claimed)["obligations"][0]["condition"] == {
        "kind": "ended",
        "operation": "work",
    }

    # The next prompt renews the turn the interrupt left open, and the move it
    # holds is handled in it again.
    harness_says("busy")
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    capsys.readouterr()
    assert _activity_at(claimed)["counts"]["handling"] == 1

    # A start the agent writes after that renews the turn, and the move it starts
    # stops being believed once the renewal grace has passed since the next
    # interrupt.
    harness_says("idle", ago=5)
    assert _start(claimed, comment["id"], "Cutting the lede").exit_code == 0
    assert _activity_at(claimed)["counts"]["active"] == 1
    harness_says("idle")
    assert _activity_at(claimed)["kind"] == "working"
    ended = _activity_at(claimed, 3)
    assert (ended["kind"], ended["dropped"]) == ("away", True)
    assert ended["obligations"][0]["condition"] == {
        "kind": "stale",
        "operation": "work",
    }

    # A status the harness has no word on is no reading at all.
    harness_says("compacting")
    assert harness_model.ClaudeCodeHarness("s1", "Claude").live_turn() is None


def test_away_asks_for_a_nudge_only_once_input_is_overdue(claimed, capsys):
    """With nothing taking input, a comment that has only just arrived is the
    session's next turn to take, and Leaf messages a Claude Code session as it
    arrives. The page asks the user to nudge the agent only once an owed move has
    stalled with the agent to act, which `counts.overdue` names: one still Sent
    past the pickup grace, or one a turn picked up and ended without answering."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "Pick a layout")

    def turn_ends():
        # The first Stop refuses to end the turn over the page's debts; the
        # repeated one lets it end.
        for repeated in (False, True):
            hooks_model.cmd_hook(
                {
                    "hook_event_name": "Stop",
                    "session_id": "s1",
                    "stop_hook_active": repeated,
                }
            )
        capsys.readouterr()

    consume_pending_input("s1")

    turn_ends()
    assert _activity_at(claimed, 3)["kind"] == "away"
    assert _activity_at(claimed, 3)["counts"]["overdue"] == 0

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Still there?"}
    )
    fresh, late = _activity_at(claimed), _activity_at(claimed, 3)
    assert (fresh["kind"], fresh["counts"]["overdue"]) == ("away", 0)
    assert (late["kind"], late["counts"]["overdue"]) == ("away", 1)

    # Picked up by the next turn. A long, silent step past the working grace
    # leaves nothing to say the turn ended, so it asks for no nudge; the turn
    # ending without answering does.
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    capsys.readouterr()
    consume_pending_input("s1")
    assert _activity_at(claimed)["counts"]["overdue"] == 0
    assert _activity_at(claimed, 16)["counts"]["overdue"] == 0
    turn_ends()
    stranded = _activity_at(claimed)
    assert (stranded["kind"], stranded["counts"]["overdue"]) == ("away", 1)


def test_a_harness_step_waiting_on_the_user_outlasts_the_working_grace():
    """An App Server observer renews its step on every event, and a wait on the
    user sends none until the user answers, so that step stands for as long as
    its observer holds the lease. A turn that completed with no final answer
    leaves the move it owed reading ended."""
    now = datetime.now().astimezone()
    old = (now - timedelta(minutes=30)).isoformat()
    present = {
        "status": {"state": "waiting", "ts": old, "detail": ""},
        "listening": True,
        "session_alive": True,
        "live_turn": None,
        "claim_session": "session-1",
        "claim_turn": "turn-1",
        "turn_opened": old,
        "turn_closed": None,
        "turn_takes_input": False,
    }
    voice = {"author": "agent", "agent": "Agent", "session": "session-1"}
    events = [
        {
            "kind": "task",
            "id": "t1",
            "seq": 1,
            "ts": old,
            "subject": {"kind": "page"},
            "title": "Revise the page",
            **voice,
        },
        {
            "kind": "start",
            "id": "s1",
            "seq": 2,
            "ts": old,
            "item": "t1",
            "text": "Revising",
            "turn": "turn-1",
            **voice,
        },
    ]
    stream = {"session": "session-1", "turn": "turn-1", "ts": old}
    waiting = activity_model.canonical_activity(
        present, [], events, now.isoformat(), {**stream, "kind": "awaiting_approval"}
    )
    assert (waiting["kind"], waiting["observed_kind"]) == (
        "working",
        "awaiting_approval",
    )
    thinking = activity_model.canonical_activity(
        present, [], events, now.isoformat(), {**stream, "kind": "thinking"}
    )
    assert (thinking["kind"], thinking["observed_kind"]) == ("stalled", None)

    workflow = {
        "id": "input-1",
        "input": "input-1",
        "seq": 1,
        "subject": {"kind": "thread", "id": "input-1"},
        "answer": {"kind": "reply", "to": "input-1", "for": "input-1"},
        "stage": "picked_up",
        "ts": now.isoformat(),
        "condition": None,
        "next_actor": "agent",
        "response": None,
    }
    reply = {"state": "partial", "session": "session-1", "responds": "input-1"}
    [ended] = activity_model.canonical_activity(
        present, [workflow], events, now.isoformat(), reply=reply
    )["workflows"]
    assert ended["condition"] == {"kind": "ended", "operation": "response"}


def test_fresh_exact_reply_supersedes_an_older_workflow_condition():
    now = datetime.now().astimezone()
    workflow = {
        "id": "input-1",
        "input": "input-1",
        "seq": 1,
        "coordinate": ["thread", "input-1"],
        "answer": {"kind": "reply", "to": "input-1", "for": "input-1"},
        "stage": "working",
        "ts": (now - timedelta(minutes=20)).isoformat(),
        "detail": "Old work",
        "agent": "Leaf guide",
        "session": "session-1",
        "activity": [],
        "condition": None,
        "next_actor": "agent",
        "response": None,
    }
    present = {
        "status": {"state": "idle", "ts": now.isoformat(), "detail": ""},
        "claim_session": "session-1",
        "claim_turn": "turn-1",
        "turn_closed": None,
        "listening": True,
        "session_alive": True,
    }
    reply = {
        "state": "active",
        "session": "session-1",
        "turn": "turn-1",
        "reply_to": "input-1",
        "responds": "input-1",
        "settles": False,
        "text": "Fresh response",
        "updated_at": now.isoformat(),
    }

    activity = activity_model.canonical_activity(
        present, [workflow], [], now.isoformat(), reply=reply
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
    with service_model.PageTransaction(claimed) as transaction:
        transaction.close_turn(old["id"])
    cleanup_model.prompt_turn("s1")
    assert service_model.claim_page(claimed)
    assert service_model.page_claim(claimed)["turn"] != old["turn"]

    [workflow] = page_state(claimed)["workflows"]
    assert workflow["stage"] == "picked_up"
    assert workflow["condition"] == {"kind": "stale", "operation": "work"}


def test_queued_input_does_not_hide_fresh_work(claimed):
    serving(claimed, 1)
    working(claimed, "Revising the heading")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )
    with service_model.PageTransaction(claimed) as transaction:
        delivery_model.record_pickup(transaction, [comment], phase="queued")

    activity = page_state(claimed)["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Revising the heading",
    )
    assert activity["counts"]["queued"] == 1
    assert activity["obligations"][0]["stage"] == "queued"


def test_newer_pending_input_does_not_reclassify_page_work(claimed):
    serving(claimed, 1)
    working(claimed, "Revising the heading")

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )

    activity = page_state(claimed)["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Revising the heading",
    )
    assert activity["counts"]["pending"] == 1
    assert activity["obligations"][0]["stage"] == "sent"


def test_queued_input_does_not_hide_live_codex_activity(claimed):
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "Comment on the page")
    claim = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, claim["id"])
    )
    assert lease
    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the checks"}
        )

    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )
    with service_model.PageTransaction(claimed) as transaction:
        delivery_model.record_pickup(transaction, [comment], phase="queued")

    activity = page_state(claimed)["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Running the checks",
    )
    assert activity["observed_kind"] == "tool"
    assert activity["counts"]["queued"] == 1
    leases_model.release_lease(lease)


def test_live_codex_activity_overlays_the_declared_page_status(claimed):
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "comment on the page")
    claim = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, claim["id"])
    )
    assert lease

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the tests"}
        )

    status = service_model.read_status(claimed)
    assert (status["state"], status["detail"]) == ("waiting", "comment on the page")
    public_presence = presence_model.presence(
        claimed, events_model.read_events(claimed)
    )
    assert "stream" not in public_presence
    assert "stream" not in public_presence["status"]
    live = page_state(claimed)
    assert "stream" not in live
    assert "stream" not in live["status"]
    activity = live["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Running the tests",
    )
    assert activity["observed_kind"] == "tool"

    session_model.cmd_waiting(claimed, "review the result")
    assert page_state(claimed)["activity"]["detail"] == "Running the tests"

    with service_model.PageTransaction(claimed) as transaction:
        transaction.clear_stream_activity("s1", "turn-live")
    returned = page_state(claimed)["activity"]
    assert (returned["kind"], returned["detail"]) == (
        "listening",
        "review the result",
    )
    leases_model.release_lease(lease)


def test_stream_activity_writes_only_new_readings(claimed, monkeypatch):
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "comment on the page")

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the tests"}
        )
    unchanged = (claimed / "status.json").read_bytes()

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the tests"}
        )
    assert (claimed / "status.json").read_bytes() == unchanged

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "thinking", "detail": "Reviewing the result"}
        )
    changed = (claimed / "status.json").read_bytes()
    assert changed != unchanged
    standing = files_model.read_json(claimed / "status.json")["stream"]["activity"]
    assert standing["detail"] == "Reviewing the result"

    renewed_at = (
        datetime.fromisoformat(standing["ts"]) + timedelta(minutes=6)
    ).isoformat()
    with monkeypatch.context() as patch:
        patch.setattr(service_model, "now_iso", lambda: renewed_at)
        with service_model.PageTransaction(claimed) as transaction:
            transaction.set_stream_activity(
                "s1",
                "turn-live",
                {"kind": "thinking", "detail": "Reviewing the result"},
            )
    assert (
        files_model.read_json(claimed / "status.json")["stream"]["activity"]["ts"]
        == renewed_at
    )


def test_a_current_declaration_keeps_the_sentence_a_live_stream_stands_beside(claimed):
    """One turn states two facts, and each answers its own question.

    The observed step proves the session is alive and moving, which is what makes a page
    working over a declaration that says otherwise. What the work *is* is the agent's to
    say, and a user waiting on an answer is owed that sentence rather than whichever
    command the transport saw most recently. So a current declaration keeps the sentence
    and its own date, and the step is reported beside it."""
    serving(claimed, 1)
    claim = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, claim["id"])
    )
    assert lease

    start = working(claimed, "Checking the rollout against staging")
    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            claim["id"],
            "turn-live",
            {"kind": "tool", "detail": "Running the tests"},
        )

    activity = page_state(claimed)["activity"]
    assert (activity["kind"], activity["detail"], activity["observed"]) == (
        "working",
        "Checking the rollout against staging",
        "Running the tests",
    )
    # The date belongs to the line, so a stream renewing every few seconds cannot
    # make an old start read as current work.
    assert activity["ts"] == start["ts"]

    # With nothing in hand, the step is all there is, and it is the sentence.
    ended = CliRunner().invoke(
        cli_model.cli, ["task", "end", str(claimed), start["item"], "done"]
    )
    assert ended.exit_code == 0, ended.output
    session_model.cmd_waiting(claimed, "which store should own it")
    waiting = page_state(claimed)["activity"]
    assert (waiting["kind"], waiting["detail"], waiting["observed"]) == (
        "working",
        "Running the tests",
        "Running the tests",
    )

    session_model.cmd_waiting(claimed, "which store should own it")

    # A newer user move has its own pending delivery; it does not reclassify current
    # page work or imply that the observed tool step belongs to that message.
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )
    quiet = page_state(claimed)["activity"]
    assert (
        quiet["kind"],
        quiet["detail"],
        quiet["observed_kind"],
        quiet["observed"],
    ) == (
        "working",
        "Running the tests",
        "tool",
        "Running the tests",
    )
    assert quiet["counts"]["pending"] == 1
    leases_model.release_lease(lease)


def test_a_malformed_old_stream_record_is_ignored(claimed):
    serving(claimed, 1)
    claim = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, claim["id"])
    )
    assert lease
    append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "new work",
        },
    )
    start = working(claimed, "Handling the new work")
    status = service_model.read_status(claimed)
    status["stream"] = {
        "activity": {
            "session": claim["id"],
            "turn": "older-turn",
            "detail": "Older streamed work",
            "ts": start["ts"],
            "after": 0,
        }
    }
    cleanup_model.write_json(claimed / "status.json", status)

    activity = page_state(claimed)["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Handling the new work",
    )
    end_work(claimed)
    session_model.cmd_waiting(claimed, "Review the result")
    without_old_stream = page_state(claimed)["activity"]
    assert (without_old_stream["kind"], without_old_stream["observed_kind"]) == (
        "listening",
        None,
    )
    leases_model.release_lease(lease)


def test_stream_work_is_scoped_to_the_live_session_and_freshness(claimed):
    serving(claimed, 1)
    claim = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, claim["id"])
    )
    assert lease
    session_model.cmd_waiting(claimed, "Review the result")
    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            claim["id"],
            "provider-turn",
            {"kind": "thinking", "detail": "Checking the result"},
        )
    assert page_state(claimed)["activity"]["observed_kind"] == "thinking"

    status = service_model.read_status(claimed)
    activity = status["stream"]["activity"]
    cleanup_model.write_json(
        claimed / "status.json",
        {**status, "stream": {"activity": {**activity, "session": "other"}}},
    )
    assert page_state(claimed)["activity"]["observed_kind"] is None

    cleanup_model.write_json(
        claimed / "status.json",
        {
            **status,
            "stream": {
                "activity": {
                    **activity,
                    "ts": "2020-01-01T00:00:00+00:00",
                }
            },
        },
    )
    stale = page_state(claimed)["activity"]
    assert (stale["kind"], stale["observed_kind"]) == ("listening", None)
    leases_model.release_lease(lease)


def test_app_server_delivery_id_reads_only_canonical_delivery_inputs():
    pointer = codex_model.delivery_pointer_prompt("aaaaaaaa")
    invalid_pointer = codex_model.delivery_pointer_prompt("../status")
    payload = {
        "format": delivery_model.DELIVERY_FORMAT,
        "id": "bbbbbbbb",
        "batches": [],
    }

    assert (
        codex_model.app_server_delivery_id(
            {
                "method": "turn/started",
                "params": {
                    "turn": {
                        "items": [
                            {
                                "type": "userMessage",
                                "content": [{"type": "text", "text": pointer}],
                            }
                        ]
                    }
                },
            }
        )
        == "aaaaaaaa"
    )
    assert (
        codex_model.app_server_delivery_id(
            {
                "method": "item/started",
                "params": {
                    "item": {
                        "type": "userMessage",
                        "content": [{"type": "text", "text": invalid_pointer}],
                    }
                },
            }
        )
        is None
    )
    assert (
        codex_model.app_server_delivery_id(
            {
                "method": "turn/started",
                "params": {
                    "turn": {
                        "items": [
                            {
                                "type": "functionCallOutput",
                                "name": "leaf_delivery",
                                "output": json.dumps(payload),
                            }
                        ]
                    }
                },
            }
        )
        == "bbbbbbbb"
    )
    assert (
        codex_model.app_server_delivery_id(
            {
                "method": "item/started",
                "params": {
                    "item": {
                        "type": "userMessage",
                        "content": [{"type": "text", "text": pointer}],
                    }
                },
            }
        )
        == "aaaaaaaa"
    )
    assert (
        codex_model.app_server_delivery_id(
            {
                "method": "turn/started",
                "params": {
                    "turn": {
                        "items": [
                            {
                                "type": "userMessage",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": pointer + "\nPlease do this.",
                                    }
                                ],
                            }
                        ]
                    }
                },
            }
        )
        is None
    )


def test_app_server_events_report_semantic_codex_progress():
    events = codex_model.AppServerEvents("codex-thread", "turn-live")

    assert events.read(
        {
            "method": "turn/started",
            "params": {"threadId": "codex-thread", "turn": {"id": "turn-live"}},
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
    # The turn's first agent message opens the reply and streams at once, even as
    # commentary; the commentary that follows it is working narration and stays private.
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
            "params": {"threadId": "codex-thread", "turnId": "turn-live"},
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
            "params": {"threadId": "codex-thread", "turn": {"id": "turn-live"}},
        }
    ) == {"turn": "turn-live", "completed": "completed"}
    # A committed reply contains the final answer; a turn that never reached one
    # commits nothing on the strength of its opening.
    opening, narration, final = (
        {"type": "agentMessage", "phase": phase, "text": text}
        for phase, text in (
            ("commentary", "Checking the page now."),
            ("commentary", "Running the browser checks."),
            ("final_answer", "The page is ready for review."),
        )
    )
    final_text = events.final_text({"items": [opening, narration, final]})
    assert final_text.endswith(final["text"])
    assert narration["text"] not in final_text
    assert events.final_text({"items": [opening, narration]}) == ""
    # A reconnect mid-turn restores the opening already on screen.
    assert events.reply_so_far({"items": [opening, narration]}) == (
        "Checking the page now."
    )
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
    monkeypatch.setattr(codex_model.time, "monotonic", lambda: next(clock))
    updates = []
    clears = []
    take_stream_activity(monkeypatch, updates, clears)

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
            "params": {"threadId": "codex-thread", "turn": {"id": "turn-live"}},
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
            "params": {"threadId": "codex-thread", "turnId": "turn-live"},
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
                "status": {"activeFlags": []},
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
            "params": {"threadId": "codex-thread", "turnId": "turn-live"},
        }
    )
    assert awaiting_input["activity"] == {"kind": "awaiting_input"}


def test_app_server_activity_reads_only_its_own_turn():
    """A fold is one turn's, and every other turn's notifications read as nothing.

    One subscription carries every turn of the task, and a turn that started
    after this one ended, or one still reporting after it, must not move this
    turn's readings. Routing a notification to its turn is the carrier's; the
    fold only refuses what is not its own.
    """
    events = codex_model.AppServerEvents("codex-thread", "turn-live")
    events.read(
        {
            "method": "turn/started",
            "params": {"threadId": "codex-thread", "turn": {"id": "turn-live"}},
        }
    )

    for message in (
        {
            "method": "turn/started",
            "params": {"threadId": "codex-thread", "turn": {"id": "turn-other"}},
        },
        {
            "method": "item/reasoning/summaryTextDelta",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-other",
                "itemId": "other-reasoning",
                "delta": "another turn's thought",
            },
        },
        {
            "method": "thread/status/changed",
            "params": {
                "threadId": "codex-thread",
                "turnId": "turn-other",
                "status": {"activeFlags": ["waitingOnUserInput"]},
            },
        },
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "turn-other", "status": "completed"},
            },
        },
        {
            "method": "item/started",
            "params": {
                "threadId": "another-thread",
                "turnId": "turn-live",
                "startedAtMs": 1,
                "item": {"id": "elsewhere", "type": "commandExecution"},
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
                "turn": {"id": "turn-live", "status": "interrupted"},
            },
        }
    ) == {"turn": "turn-live", "completed": "interrupted"}


def test_a_new_codex_carrier_observes_ordinary_turns_without_a_prior_hook(
    page_dir, app_server, under_codex, codex_env, tmp_path
):
    """Startup establishes the generation before an idle provider subscribes."""
    begin = threading.Event()
    finish = threading.Event()

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
                            "status": {"type": "idle"},
                            "turns": [],
                        }
                    },
                }
            )
        )
        if not begin.wait(timeout=STATED_TIMEOUT):
            return
        socket.send(
            json.dumps(
                {
                    "method": "turn/started",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {"id": "ordinary-turn"},
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
                        "turnId": "ordinary-turn",
                        "startedAtMs": 1000,
                        "item": {
                            "id": "ordinary-command",
                            "type": "commandExecution",
                            "command": "uv run pytest tests",
                        },
                    },
                }
            )
        )
        if not finish.wait(timeout=STATED_TIMEOUT):
            return
        socket.send(
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {"id": "ordinary-turn"},
                    },
                }
            )
        )
        for _raw in socket:
            pass

    assert cleanup_model.session_record("codex-thread") is None
    endpoint = app_server(handle)
    program, _log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page_dir, "Reviewing the page")
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(page_dir),
                "--codex-path",
                str(program),
                "--app-server",
                endpoint,
            ]
        ),
        codex_env | {"CODEX_THREAD_ID": "codex-thread"},
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        announcement = codex_start_announcement(started)
        claim = service_model.page_claim(page_dir)
        generation = claim["generation"]
        begin.set()
        observed = wait_for(
            lambda: files_model.read_json(page_dir / "status.json"),
            lambda status: (
                status.get("stream", {}).get("activity", {}).get("detail")
                == "Running uv run pytest tests"
            ),
            failure="the newly subscribed carrier did not project ordinary provider activity",
        )
        assert observed["stream"]["activity"]["turn"] == "ordinary-turn"
        current = service_model.page_claim(page_dir)
        assert current["generation"] == generation
        assert current["turn"] == "ordinary-turn"
        assert current["turn_closed"] is None
        finish.set()
        closed = wait_for(
            lambda: service_model.page_claim(page_dir),
            lambda claim: claim["turn_closed"] is not None,
            failure="the ordinary provider completion did not close the page turn",
        )
        assert (closed["generation"], closed["turn"]) == (generation, "ordinary-turn")
    finally:
        begin.set()
        finish.set()
        release_held(started)
        out, err = started.communicate(timeout=STATED_TIMEOUT)
        assert started.returncode == 0, f"{announcement}{out}{err}"
        with service_model.PageTransaction(page_dir) as page:
            page.release_claim()
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the carrier did not retire after its page was released",
    )


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
    lease = leases_model.take_lease(
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
                        "turn": {"id": "leaf-turn"},
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
        lambda: page_state(page_dir)["browser"]["thread"]["threads"][0]["msgs"][-1],
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
            files_model.read_json(page_dir / "status.json").get("stream") or {},
        ),
        lambda reading: bool(reading[0]) and "reply" not in reading[1],
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
    [thread] = page_state(page_dir)["browser"]["thread"]["threads"]
    assert thread["msgs"][-1]["id"] == replies[0]["id"]


def test_a_quiet_stream_is_a_fault_only_once_its_silence_outlasts_its_bound():
    """Separate an App Server that is thinking from one that stopped delivering.

    `recv` reports every idle second the same way, so the reading that tells the two
    apart is how long the silence has run against the bound its carrier gave. The
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
    queued = codex_model.offer_delivery(path, files_model.read_json(path), "queue")
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
    [workflow] = served_page.full_state(page_dir, events_model.read_events(page_dir))[
        "activity"
    ]["obligations"]
    assert workflow["stage"] == "picked_up"
    assert workflow["answer"] == {
        "kind": "reply",
        "to": comment["id"],
        "for": comment["id"],
    }

    posted = thread_model.cmd_reply(
        page_dir,
        None,
        "Answered with leaf thread reply",
        "",
        for_event=comment["id"],
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
            "params": {"threadId": "codex-thread", "turn": {"id": "leaf-turn"}},
        }
    )
    observer._disconnect_turns()

    observer._resume(
        {
            "status": {"type": "active" if status == "inProgress" else "idle"},
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

    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "accepted"
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
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer the first turn"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "reply_to": comment["id"],
        "responds": comment["id"],
    }
    with service_model.PageTransaction(page_dir) as page:
        page.open_turn("codex-thread", "turn-1")
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "turn-1", "delivery-1", target
    )
    with service_model.PageTransaction(page_dir) as page:
        page.close_turn("codex-thread", "turn-1")
        page.open_turn("codex-thread", "turn-2")

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


def test_an_interrupted_stream_reply_finishes_after_the_claim_advances(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer the first turn"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "reply_to": comment["id"],
        "responds": comment["id"],
    }
    thread_model.reserve_delivery_reply("codex-thread", "delivery-1", target)
    with service_model.PageTransaction(page_dir) as page:
        page.open_turn("codex-thread", "turn-1")
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
    with service_model.PageTransaction(page_dir) as page:
        page.close_turn("codex-thread", "turn-1")
        page.open_turn("codex-thread", "turn-2")

    assert stream.finish("interrupted") is None

    stream_state = files_model.read_json(page_dir / "status.json")["stream"]
    assert (stream_state["reply"]["text"], stream_state["reply"]["state"]) == (
        "Partial answer",
        "interrupted",
    )
    assert "reply_bindings" not in stream_state


def test_a_delivery_bound_final_is_the_only_plain_reply_writer(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Move this reply too"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    with service_model.PageTransaction(page_dir) as page:
        page.open_turn("codex-thread", "turn-1")
    target = {
        "page": str(page_dir),
        "reply_to": comment["id"],
        "responds": comment["id"],
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
    with pytest.raises(SystemExit, match="answered by this turn's messages"):
        thread_model.cmd_reply(
            page_dir,
            comment["id"],
            "Anchored answer",
            "",
            for_event=comment["id"],
            identity={"agent": "Codex", "session": "codex-thread"},
        )
    assert stream.finish("completed", "Transcript closeout") is None
    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [reply["text"] for reply in replies] == ["Transcript closeout"]
    assert "reply" not in (
        files_model.read_json(page_dir / "status.json").get("stream") or {}
    )


def test_a_delivery_reserves_its_final_before_provider_execution(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this once"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    target = {
        "page": str(page_dir),
        "reply_to": comment["id"],
        "responds": comment["id"],
    }

    thread_model.reserve_delivery_reply("codex-thread", "delivery-1", target)

    with pytest.raises(SystemExit, match="answered by this turn's messages"):
        thread_model.cmd_reply(
            page_dir,
            comment["id"],
            "Competing reply",
            "",
            for_event=comment["id"],
            identity={"agent": "Codex", "session": "codex-thread"},
        )

    with pytest.raises(RuntimeError, match="already bound to another delivery"):
        thread_model.reserve_delivery_reply("codex-thread", "delivery-2", target)


def test_a_delivery_bound_final_cannot_append_after_claim_transfer(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    with service_model.PageTransaction(page_dir) as page:
        page.open_turn("codex-thread", "turn-1")
    stream = codex_model.AppServerReplyStream(
        "codex-thread",
        "turn-1",
        "delivery-1",
        {
            "page": str(page_dir),
            "reply_to": comment["id"],
            "responds": comment["id"],
        },
    )
    claim = service_model.page_claim(page_dir)
    record_claim(page_dir, **{**claim, "id": "successor-thread", "agent": "Successor"})

    error = stream.finish("completed", "Stale answer")

    assert isinstance(error, RuntimeError)
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )

    successor = {
        "page": str(page_dir),
        "reply_to": comment["id"],
        "responds": comment["id"],
    }
    thread_model.reserve_delivery_reply("successor-thread", "delivery-2", successor)
    with service_model.PageTransaction(page_dir) as page:
        assert page.status["stream"]["reply_bindings"][comment["id"]] == {
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
    with service_model.PageTransaction(page_dir) as page:
        page.open_turn("codex-thread", "turn-1")
    target = {
        "page": str(page_dir),
        "reply_to": comment["id"],
        "responds": comment["id"],
    }
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "turn-1", "delivery-1", target
    )
    (page_dir / "index.html").write_text("<main>unfinished")

    error = stream.finish("completed", "I made the change.")

    assert isinstance(error, SystemExit)
    reply = files_model.read_json(page_dir / "status.json")["stream"]["reply"]
    assert (reply["state"], reply["text"], reply["settles"]) == (
        "failed",
        "I made the change.",
        False,
    )
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )


def test_partial_text_is_not_committed_without_a_completed_final(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Answer this"},
    )
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    with service_model.PageTransaction(page_dir) as page:
        page.open_turn("codex-thread", "turn-1")
    stream = codex_model.AppServerReplyStream(
        "codex-thread",
        "turn-1",
        "delivery-1",
        {
            "page": str(page_dir),
            "reply_to": comment["id"],
            "responds": comment["id"],
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
    reply = files_model.read_json(page_dir / "status.json")["stream"]["reply"]
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
            "comment",
            "comment",
            service_model.delivery_reply_attempt("delivery-1"),
            None,
            "",
            "active",
        )
        page.set_stream_reply(
            "codex-thread",
            "turn-1",
            "comment",
            "comment",
            service_model.delivery_reply_attempt("delivery-1"),
            "answer",
            "Now visible",
            "active",
        )
        reply = page.status["stream"]["reply"]

    assert reply["ts"] == created.isoformat()
    assert reply["updated_at"] == refreshed.isoformat()
    projected = activity_model.canonical_stream_reply(
        {"claim_session": "codex-thread", "listening": True},
        (created + timedelta(minutes=16)).isoformat(),
        reply,
    )
    assert projected["state"] == "active"


def _observer() -> "codex_adapter_model.TaskConnection":
    """An observer that has not connected, so a test feeds it notifications itself."""
    connection = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "codex-thread")
    connection.connected.set()
    return connection


def _delivery_item(payload: dict) -> dict:
    """The transcript item a turn carrying one App Server delivery holds."""
    return {
        "id": "delivery",
        "type": "functionCallOutput",
        "name": "leaf_delivery",
        "output": json.dumps(payload),
    }


def _obligations(page_dir) -> list[dict]:
    return served_page.full_state(page_dir, events_model.read_events(page_dir))[
        "activity"
    ]["obligations"]


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

    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "accepted"
    )
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["events"], pickup["turn"]) == ([action["id"]], "ended-turn")
    assert service_model.page_claim(page_dir) == closed


def test_a_reply_binding_lapses_when_a_turn_it_does_not_name_opens(page_dir):
    """A binding hands its move's answer to the turn it names, and to no other.

    The observer bound the delivery's reply to its turn and then lost the
    connection with the turn still running. While that turn is the claim's, the
    turn's own messages owe the answer. Once a later turn opens without the
    carrier taking the binding over, nothing says those messages will be
    committed, so the move is answered with `leaf thread reply` again, and a
    carrier that reconnects and commits the delivery turn's final message after
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
                },
            },
        }
    )
    observer._disconnect_turns()
    [owed] = _obligations(page_dir)
    assert owed["answer"]["kind"] == "turn"

    cleanup_model.prompt_turn("codex-thread", "later-turn")

    [owed] = _obligations(page_dir)
    assert owed["answer"] == {
        "kind": "reply",
        "to": comment["id"],
        "for": comment["id"],
    }
    posted = thread_model.cmd_reply(
        page_dir,
        None,
        "Answered in the later turn",
        "",
        for_event=comment["id"],
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


def test_a_reply_binding_lapses_when_its_turn_closes(page_dir):
    """A turn that has ended writes nothing more, so its binding lapses with it.

    The observer bound the delivery's reply to its turn and then lost the
    connection. When the session's turn closes without a carrier committing the
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
                },
            },
        }
    )
    observer._disconnect_turns()
    [owed] = _obligations(page_dir)
    assert owed["answer"]["kind"] == "turn"

    cleanup_model.close_session_turn("codex-thread", "delivery-turn")

    [owed] = _obligations(page_dir)
    assert owed["answer"] == {
        "kind": "reply",
        "to": comment["id"],
        "for": comment["id"],
    }
    posted = thread_model.cmd_reply(
        page_dir,
        None,
        "Answered after the turn ended",
        "",
        for_event=comment["id"],
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
    cleanup_model.write_json(
        page_dir / "cursor.json", {"seq": events_model.read_events(page_dir)[-1]["seq"]}
    )
    cleanup_model.close_session_turn("codex-thread")

    hooks_model.cmd_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "codex-thread",
            "turn_id": "codex-turn",
        }
    )
    capsys.readouterr()
    _observer()._read(
        {
            "method": "turn/started",
            "params": {"threadId": "codex-thread", "turn": {"id": "codex-turn"}},
        }
    )

    assert service_model.page_claim(page_dir)["turn"] == "codex-turn"
    [owed] = _obligations(page_dir)
    assert (owed["stage"], owed["condition"]) == ("picked_up", None)


def test_reconnect_closes_a_completed_stream_binding(page_dir):
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


def _codex_delivery(page_dir, text="Answer this"):
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": text}
    )
    return codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid()),
    )


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
    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "offering"
    )
    assert not thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )


def test_a_refused_turn_gives_up_the_seat_it_reserved(
    page_dir, app_server, task_connection
):
    """A provider that refuses before executing has started nothing.

    The reserved seat is what stops any other writer answering the user while the
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
                        "error": {"message": "the active turn cannot be steered"},
                    }
                ),
                lambda request: json.dumps(
                    {"id": request["id"], "result": {"turn": {"id": "retry-turn"}}}
                ),
            ]
        )
    )

    connection = task_connection(endpoint)
    with pytest.raises(codex_model.AppServerRequestRejected):
        connection.start_delivery(prepared.payload)

    assert not thread_model.delivery_reply_reserved(
        "codex-thread", prepared.payload["id"], target
    )

    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    assert files_model.read_json(path)["transport"]["phase"] == "app-server"
    assert connection.start_delivery(prepared.payload)
    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "accepted"
    )


def test_an_unacknowledged_turn_keeps_the_seat_it_reserved(
    page_dir, app_server, task_connection
):
    """A request whose answer never came back may have started a turn.

    Nothing here can tell, so the seat stays reserved: no other writer may answer
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

    `DeliveryReply` guards only the commit of a completed answer: setting the
    state and releasing the binding open a page transaction of their own, and the
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
    monkeypatch.setattr(thread_model.DeliveryReply, "_set_state", _unopenable)

    with pytest.raises(OSError, match="could not be opened"):
        turn.commit({"id": "leaf-turn", "status": "completed", "items": []})

    assert service_model.page_claim(page_dir)["turn_closed"] is not None
    assert (files_model.read_json(page_dir / "status.json").get("stream") or {}).get(
        "activity"
    ) is None
    # The seat goes back too: a reply that faulted part-written holds one nothing
    # will ever commit, and every other writer waits behind it.
    assert not thread_model.delivery_reply_reserved(
        "codex-thread", payload["id"], target
    )


def test_an_observed_turn_whose_reply_cannot_be_written_still_closes(
    page_dir, monkeypatch
):
    """The observer ends the turns it adopts the way a follower ends its own.

    A turn the observer binds is one nobody else is following — a pointer the task
    picked up, or a delivery whose carrier died mid-turn — so its ending is the only
    one that turn gets. The reply write can fault on the page the turn left behind,
    and the turn is over either way: the page stops reading working, and the seat
    goes back for whatever writer tells the user what happened.
    """
    prepared = _codex_delivery(page_dir)
    payload = prepared.payload
    target = codex_model.stream_reply_target(payload)
    thread_model.reserve_delivery_reply("codex-thread", payload["id"], target)
    observer = _observer()
    observer._read(
        {
            "method": "turn/started",
            "params": {"threadId": "codex-thread", "turn": {"id": "leaf-turn"}},
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
    monkeypatch.setattr(thread_model.DeliveryReply, "_set_state", _unopenable)

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
    failure this carrier cannot fix by itself already is.
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
                "turn": {"id": "a-turn-the-user-started"},
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
                "turn": {"id": "a-turn-the-user-started", "status": "completed"},
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
        return {"thread": {"id": "codex-thread", "status": {"type": "active"}}}

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
    "endpoint",
    [
        "ws://192.0.2.1:4500",
        "wss://localhost:4500",
        "ws://[::1",
        "unix://relative.sock",
    ],
)
def test_codex_activity_rejects_nonlocal_or_invalid_app_servers(endpoint):
    with pytest.raises(RuntimeError, match="local|valid"):
        codex_model.check_app_server_endpoint(endpoint)


def test_unheld_activity_drops_interaction_claims_from_the_same_reading(
    page_dir, monkeypatch
):
    """One held decision governs both the page and its interaction receipts."""
    serving(page_dir, 1)
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "new input"}
    )
    claimed = _start(page_dir, comment["id"], "reading it")
    assert claimed.exit_code == 0, claimed.output
    followup = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": comment["id"],
            "text": "one more detail",
        },
    )
    assert [
        (workflow["input"], workflow["stage"])
        for workflow in page_state(page_dir)["workflows"]
    ] == [(comment["id"], "working"), (followup["id"], "sent")]
    status = service_model.read_status(page_dir)
    cleanup_model.write_json(
        page_dir / "status.json",
        {
            **status,
            "ts": (datetime.now().astimezone() - timedelta(minutes=20)).isoformat(),
        },
    )
    monkeypatch.setattr(
        read_context,
        "now_iso",
        lambda: (datetime.now().astimezone() + timedelta(minutes=20)).isoformat(),
    )

    state = page_state(page_dir)
    activity = state["activity"]
    assert (activity["kind"], activity["held"]) == ("unheld", False)
    assert {item["input"]: item["stage"] for item in state["workflows"]} == {
        comment["id"]: "sent",
        followup["id"]: "sent",
    }
    assert all(
        (workflow["agent"], workflow["detail"]) == (None, None)
        for workflow in state["workflows"]
    )
    assert all(workflow["activity"] == [] for workflow in state["workflows"])
    assert all(
        workflow["condition"] == {"kind": "stale", "operation": "delivery"}
        for workflow in state["workflows"]
    )


def test_idle_activity_refreshes_when_its_interaction_ownership_expires(
    page_dir, monkeypatch
):
    """A Closed label still schedules the deadline that can withdraw its receipt."""
    serving(page_dir, 1)
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "new input"}
    )
    started = datetime.now().astimezone()
    declare_work(page_dir, "reading it", item=comment["id"], ts=started.isoformat())
    cleanup_model.write_json(
        page_dir / "status.json",
        {"state": "idle", "detail": "", "ts": started.isoformat(), "after": 0},
    )

    monkeypatch.setattr(
        read_context,
        "now_iso",
        lambda: (started + timedelta(minutes=14)).isoformat(),
    )
    before_state = page_state(page_dir)
    before = before_state["activity"]
    assert (before["kind"], before["held"]) == ("closed", True)
    assert before_state["workflows"][0]["stage"] == "working"
    assert before["next_transition_at"] == (started + timedelta(minutes=15)).isoformat()

    monkeypatch.setattr(
        read_context,
        "now_iso",
        lambda: (started + timedelta(minutes=15)).isoformat(),
    )
    after_state = page_state(page_dir)
    after = after_state["activity"]
    assert (after["kind"], after["held"]) == ("closed", False)
    assert after_state["workflows"][0]["stage"] == "sent"
    assert (
        after_state["workflows"][0]["agent"],
        after_state["workflows"][0]["detail"],
    ) == (
        None,
        None,
    )
    assert after["next_transition_at"] is None


def test_revendoring_can_change_x_work_while_the_target_holds_a_task(page_dir):
    """x-work admits a task on a widget; it is not the task's only later seat.

    Re-vendoring can remove that declaration while the live widget remains, because
    the page-edge margin entry continues to present the task already admitted.
    """
    work_page = PAGE.replace(
        '<lf-diagram id="flow">',
        '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
        '  <lf-card id="rollout-card"><strong>Ship the rollout</strong></lf-card>\n'
        '</lf-column></lf-board>\n<lf-diagram id="flow">',
    )
    (page_dir / "index.html").write_text(work_page)
    publish(page_dir)
    opened = CliRunner().invoke(
        cli_model.cli,
        ["task", "open", str(page_dir), "rollout-card", "Check the rollout"],
    )
    assert opened.exit_code == 0, opened.output
    card = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())[
        "lf-card"
    ]
    card.pop("x-work")
    layer = Path.cwd() / ".leaf"
    layer.mkdir()
    (layer / "registry.json").write_text(json.dumps({"lf-card": card}))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    registry = json.loads((page_dir / "registry.json").read_text())
    assert "x-work" not in registry["lf-card"]
    [task] = state_json(page_dir)["tasks"]
    assert task["subject"] == {"kind": "widget", "id": "rollout-card"}


def test_a_recordless_receipt_from_a_stale_revision_waits_for_a_later_note(page_dir):
    """A completion move can arrive from a live revision after another is active.

    A version note older than the move cannot answer it. The agent can start the move
    all the same, and the next version that records it settles the move and ends the
    start with it.
    """
    work_page = PAGE.replace(
        "<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1
    )
    (page_dir / "index.html").write_text(work_page)
    publish(page_dir)
    (page_dir / "index.html").write_text(
        work_page.replace("<title>t</title>", "<title>t · v2</title>")
    )
    advanced = stamp(page_dir, "Checked the surrounding plan")
    assert advanced.exit_code == 0, advanced.output

    # The user still has r1 open after r2 became active. That move is new work,
    # not something the earlier r2 note could already have answered.
    answer = append_command(
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
    before_state = page_state(page_dir)
    before_pickup = before_state["activity"]
    acknowledgments = before_state["workflows"]
    assert any(receipt["input"] == answer["id"] for receipt in acknowledgments)
    assert before_pickup["kind"] == "away"
    assert before_pickup["counts"]["total"] == 1
    assert [item["answer"] for item in before_pickup["obligations"]] == [
        {"kind": "markup", "action": answer["id"]}
    ]

    claim = record_claim(page_dir)
    with service_model.PageTransaction(page_dir) as transaction:
        delivery_model.record_pickup(
            transaction,
            [answer],
            session=claim["id"],
            turn=claim["turn"],
        )
    after_pickup = page_state(page_dir)["activity"]
    assert after_pickup["kind"] == "working"
    assert after_pickup["counts"]["handling"] == 1
    assert [item["input"] for item in after_pickup["obligations"]] == [answer["id"]]

    claimed = _start(page_dir, answer["id"], "checking the completed choice")
    assert claimed.exit_code == 0, claimed.output
    [working_receipt] = page_state(page_dir)["workflows"]
    assert working_receipt["stage"] == "working"
    (page_dir / "index.html").write_text(
        work_page.replace("<title>t</title>", "<title>t · v3</title>")
    )
    answered = stamp(page_dir, "Answered the completed choice")
    assert answered.exit_code == 0, answered.output

    acknowledgments = page_state(page_dir)["workflows"]
    assert not any(receipt["input"] == answer["id"] for receipt in acknowledgments)


@pytest.mark.parametrize("target", ["effort", "flag-first"])
def test_only_a_declared_widget_work_seat_is_admitted(page_dir, target):
    """A content model says what authors may put inside a widget, not whether core
    may add local chrome there. Inline prose has no block slot, and a prose option is
    itself the click target of its holder; neither becomes a seat by inference."""
    version = page_dir / "index.html"
    version.write_text(
        PAGE.replace(
            "<lf-chip>effort: low</lf-chip>",
            '<lf-chip id="effort">effort: low</lf-chip>',
        )
    )
    publish(page_dir)

    claimed = CliRunner().invoke(
        cli_model.cli,
        ["task", "open", str(page_dir), target, "Check the estimate"],
    )
    assert claimed.exit_code == 1
    assert "has no work seat" in claimed.output


def test_a_start_is_settled_by_log_order_not_a_second_precision_clock(page_dir):
    """A reply can land in the same timestamp second as the start. The reply that
    answers the move ends the start by the log alone, without asking two equal
    wall-clock strings which happened first."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    started = _start(page_dir, comment["id"], "checking")
    assert started.exit_code == 0, started.output
    start = json.loads(started.output.splitlines()[-1])

    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": "Because the retry won.",
            "ts": start["ts"],
        },
    )
    assert page_state(page_dir)["workflows"] == []


def test_each_delivered_event_says_only_what_its_own_case_asks(page_dir, capsys):
    """Shared clauses travel once, and each event names only its applicable rules:
    its kind's, then the answer it owes, and no answer's where it owes none."""
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    page_pick = {
        "kind": "action",
        "author": "user",
        "revision": 1,
        "widget": "w",
        "action": "choose",
        "detail": {"options": ["a"]},
        "meaning": {
            "scope": "page",
            "unit": "w",
            "depends": ["a", "w"],
            "answer": None,
        },
    }
    thread_pick = {
        **page_pick,
        "meaning": {**page_pick["meaning"], "scope": "thread"},
    }
    drawing = {
        "format": "leaf-drawing/2",
        "strokes": [[[0, 0], [10, 10]]],
        "viewport": [1200, 900],
        "scheme": "light",
    }
    for event in (
        {"kind": "comment", "id": "c1", "author": "user", "text": "hi"},
        {"kind": "comment", "id": "c2", "author": "user", "drawing": drawing},
        {"kind": "comment", "id": "c3", "author": "user", "text": "never mind"},
        {"kind": "resolve", "author": "user", "parent": "c3"},
        page_pick,
        thread_pick,
    ):
        append_carried_log_record(page_dir, event)

    assert session_model.cmd_wait(page_dir) == 0
    envelope, header, shown = delivered(capsys)
    handling = header["handling"]
    assert len(handling.values()) == len(set(handling.values()))
    assert shown[0]["handling"][0] in shown[1]["handling"]
    plain, drawn, closed, resolved, on_page, in_thread = (
        [handling[clause] for clause in event.get("handling", [])] for event in shown
    )
    declared = registry_storage.load_registry(page_dir)["$events"]
    [reading_a_drawing] = [
        c["text"]
        for c in declared["handling"]["comment"]
        if c.get("when") == {"required": ["drawing"]}
    ]
    replying = [c["text"] for c in declared["answering"]["reply"] if "when" not in c]
    # How receipt is confirmed is the envelope's to say once, and a hook confirms
    # it itself, so no event tells the agent to acknowledge anything. A message is
    # told its own clauses, then how to write the reply it owes.
    assert f"leaf delivery ack {envelope['id']}" in envelope["acknowledge"]
    assert not any("--ack" in text for text in handling.values())
    assert plain[-len(replying) :] == replying
    # A drawn comment is told everything a plain one is, and how to read its drawing.
    assert reading_a_drawing in drawn
    assert [clause for clause in drawn if clause != reading_a_drawing] == plain
    # A thread the user closed before capture owes nothing, so it is told nothing
    # about answering.
    assert not set(replying) & set(closed)
    assert resolved == [declared["handling"]["resolve"][0]["text"]]
    # Neither pick lands on a widget either document holds, so neither owes an
    # answer; the page's own clauses reach only the page pick.
    page_only = [
        c["text"]
        for c in declared["handling"]["action"]
        if c.get("when", {}).get("not", {}).get("required") == ["meaning"]
    ]
    assert page_only
    assert all(text in on_page and text not in in_thread for text in page_only)
    assert not set(replying) & set(on_page + in_thread)


def test_active_handling_survives_a_mutable_layer_edit(page_dir, capsys):
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    comment = {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    active = registry_contract.event_clauses(
        {
            **comment,
            "answer": {"kind": "reply"},
            "thread": {"title": None},
        },
        registry,
    )
    del registry["$events"]["handling"]
    del registry["$events"]["answering"]
    registry_path.write_text(json.dumps(registry))

    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    append_carried_log_record(page_dir, comment)

    assert session_model.cmd_wait(page_dir) == 0
    _, batch, [shown] = delivered(capsys)
    assert active and [batch["handling"][ref] for ref in shown["handling"]] == [
        c["text"] for c in active
    ]


def test_codex_delivery_carries_only_the_selected_events_handling(page_dir):
    """A later reply stays out of this delivery, including its unique clauses."""
    for event in (
        {"kind": "error", "message": "first failure"},
        {"kind": "error", "message": "second failure"},
        {"kind": "comment", "text": "first question"},
        {
            "kind": "comment",
            "text": "later drawing",
            "drawing": {
                "format": "leaf-drawing/2",
                "strokes": [[[0, 0], [1, 1]]],
                "viewport": [1200, 900],
                "scheme": "light",
            },
        },
    ):
        append_carried_log_record(page_dir, {"author": "user", **event})
    with service_model.PageTransaction(page_dir) as transaction:
        selected = transaction.events[:3]
        queued, _, _ = codex_model.append_batch(
            "handling-test", page_dir, transaction, transaction.events
        )
    payload = codex_model.offer_delivery(
        queued, files_model.read_json(queued), "queue"
    ).payload
    [batch] = payload["batches"]
    assert [event["id"] for event in batch["events"]] == [
        event["id"] for event in selected
    ]
    registry = registry_storage.active_registry(page_dir)
    digests = {digest["id"]: digest for digest in batch["threads"]}

    def case(event):
        """The event as its clauses read it: with its thread."""
        read = dict(event)
        if event["threads"]:
            read["thread"] = digests[event["threads"][0]]
        return read

    expected = [
        registry_contract.event_clauses(case(event), registry)
        for event in batch["events"]
    ]
    assert [
        [batch["handling"][ref] for ref in event["handling"]]
        for event in batch["events"]
    ] == [[clause["text"] for clause in clauses] for clauses in expected]
    assert set(batch["handling"].values()) == {
        clause["text"] for clauses in expected for clause in clauses
    }
    assert delivery_model.read_delivery(payload["id"]) == payload


def test_delivery_without_a_registry_has_no_handling(page_dir):
    (page_dir / "registry.json").unlink()
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hello"}
    )
    [batch] = freeze_events(page_dir, [comment])["batches"]
    assert batch["handling"] == {}
    assert "handling" not in batch["events"][0]


def test_codex_drops_a_record_whose_delivery_it_cannot_read(page_dir):
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hello"}
    )
    with service_model.PageTransaction(page_dir) as transaction:
        path, _, _ = codex_model.append_batch(
            "handling-test", page_dir, transaction, transaction.events
        )
    queue = files_model.read_json(path)
    payload = codex_model.offer_delivery(path, queue, "queue").payload
    payload["format"] = "leaf-delivery-v1"
    cleanup_model.write_json(delivery_model.delivery_path(payload["id"]), payload)
    with pytest.raises(RuntimeError, match="invalid envelope"):
        delivery_model.read_delivery(payload["id"])
    assert codex_model.delivery_records("handling-test") == []


def test_reopening_a_thread_reveals_its_started_move(page_dir):
    """Resolution hides a thread's moves while reopening restores an unanswered one,
    still in hand under the start that named it."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    assert _start(page_dir, comment["id"], "checking").exit_code == 0
    append_carried_log_record(
        page_dir,
        {"kind": "resolve", "author": "agent", "parent": comment["id"]},
    )
    append_carried_log_record(
        page_dir,
        {"kind": "unresolve", "author": "user", "parent": comment["id"]},
    )

    [workflow] = page_state(page_dir)["workflows"]
    assert (workflow["input"], workflow["stage"]) == (comment["id"], "working")


def test_delivery_distinguishes_thread_obligations_from_closing_answered_work(page_dir):
    """The same resolve/unresolve kinds can withdraw work or merely tidy a thread.
    Changes remain deliverable after pickup and after the work they changed ends.
    """
    publish(page_dir)

    def write(kind, **fields):
        event = append_command(page_dir, {"kind": kind, "author": "user", **fields})
        log = events_model.read_events(page_dir)
        selected = service_model.unacknowledged(log, event["seq"] - 1)
        assert selected == ([event] if event["attention"] else [])
        return event

    question = write("comment", revision=1, text="Please revise the plan.")
    assert question["attention"]
    newest = write("reply", parent=question["id"], text="Keep the launch small.")
    assert newest["attention"]
    receive_through(page_dir, newest["seq"])
    assert _start(page_dir, question["id"], "Revising").exit_code == 0
    withdrawal = write("resolve", parent=question["id"])
    assert withdrawal["attention"]
    # Repeated closure has neither an answer nor a started move left to change.
    assert not write("resolve", parent=question["id"])["attention"]
    reopened = write("unresolve", parent=question["id"])
    assert reopened["attention"]
    assert write("undo", undoes=reopened["id"])["attention"]
    assert write("unresolve", parent=question["id"])["attention"]
    answered = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": newest["id"],
            "responds": newest["id"],
            "text": "The plan is revised.",
        },
    )
    assert not write("resolve", parent=question["id"])["attention"]
    assert not write("unresolve", parent=question["id"])["attention"]
    # A task begun after the answer is separate work, with no pending response, and
    # it stands through the user closing and reopening the thread.
    opened = CliRunner().invoke(
        cli_model.cli,
        ["task", "open", str(page_dir), question["id"], "Check the change"],
    )
    assert opened.exit_code == 0, opened.output
    assert not write("resolve", parent=question["id"])["attention"]
    assert not write("unresolve", parent=question["id"])["attention"]
    assert page_state(page_dir)["activity"]["obligations"] == []
    with service_model.PageTransaction(page_dir) as page:
        page.set_status("idle", "")
    assert withdrawal in service_model.unacknowledged(
        events_model.read_events(page_dir), newest["seq"]
    )
    assert not write(
        "read", messages=[{"message": answered["id"], "version": answered["id"]}]
    )["attention"]


def test_delivery_distinguishes_composing_an_ask_from_changing_input_in_hand(page_dir):
    source = PAGE.replace(
        "<lf-options>", '<lf-options id="choice" choose multiple>'
    ).replace(
        "</section>", '<lf-draft id="draft"><pre>Blue room.</pre></lf-draft></section>'
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)

    def action(widget, verb, detail):
        return append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": verb,
                "detail": detail,
            },
        )

    composing = action("choice", "choose", {"options": ["flag-first"]})
    assert not composing["attention"]
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == []
    completed = action("choice", "answer", {})
    assert completed["attention"]
    receive_through(page_dir, completed["seq"])
    # The agent takes the answered pick on as a task on its widget.
    assert (
        CliRunner()
        .invoke(
            cli_model.cli, ["task", "open", str(page_dir), "choice", "Build the choice"]
        )
        .exit_code
        == 0
    )
    undone = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": completed["id"]}
    )
    assert undone["attention"]
    # The Ask is unfinished again, but the agent is already acting on its pick.
    changed = action("choice", "choose", {"options": ["backfill-first"]})
    assert changed["attention"]
    assert append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": changed["id"]}
    )["attention"]
    quiet = action("draft", "edit", {"text": "Green room."})
    assert not quiet["attention"]
    assert not append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": quiet["id"]}
    )["attention"]
    quiet = action("draft", "edit", {"text": "Red room."})
    assert (
        CliRunner()
        .invoke(
            cli_model.cli, ["task", "open", str(page_dir), "draft", "Edit the draft"]
        )
        .exit_code
        == 0
    )
    assert action("draft", "edit", {"text": "Orange room."})["attention"]
    selected = service_model.unacknowledged(
        events_model.read_events(page_dir), completed["seq"]
    )
    assert quiet not in selected
    assert undone in selected and changed in selected


def test_signoff_withdrawals_reports_and_errors_remain_deliverable(page_dir):
    source = PAGE.replace(
        "</head>", '<meta name="lf-review" content="sign-off"></head>'
    )
    source = source.replace('<lf-ask id="plan-choice-decision">', "<div>").replace(
        "</lf-ask>", "</div>"
    )
    source = source.replace(
        "</section>",
        '<lf-tasks id="tasks"><lf-task id="task" status="active"><strong>Check</strong></lf-task></lf-tasks></section>',
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    done = append_command(page_dir, {"kind": "done", "author": "user", "version": 1})
    undo = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": done["id"]}
    )
    report = append_command(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "revision": 1,
            "widget": "task",
            "action": "status",
            "detail": {"status": "done"},
        },
    )
    error = append_command(
        page_dir,
        {
            "kind": "error",
            "author": "page",
            "revision": 1,
            "text": "The task view failed.",
        },
    )
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == [
        done,
        undo,
        report,
        error,
    ]
    assert all(event["attention"] for event in (done, undo, report, error))
    assert page_state(page_dir)["pending"] == 2


def test_wait_prints_unacknowledged_input_without_receipt_or_pickup(
    page_dir, sessionless, capsys
):
    # A held server.lock lease is what wait's liveness probe asks for.
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "b",
            "action": "move",
            "detail": {"card": "x", "to": "y", "rank": "0i"},
            "meaning": {
                "scope": "page",
                "unit": "x",
                "depends": ["b", "x", "y"],
            },
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    payload, header, shown = printed(capsys.readouterr().out)
    assert header["page"] == str(page_dir)
    assert [e["kind"] for e in shown] == ["comment", "action"]
    assert shown[1]["detail"]["to"] == "y"
    # Printing is not acknowledgement: a detached Codex command can finish without
    # putting its output in the model's context, so wait leaves both events pending.
    assert files_model.read_json(page_dir / "cursor.json") is None
    assert page_state(page_dir)["pending"] == 2

    # An event posted between wait and acknowledgement is beyond the highest sequence
    # the model saw. Acknowledging that visible batch therefore leaves the newcomer.
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "later"}
    )
    delivered_through = shown[-1]["seq"]
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(page_dir)
    )
    delivery_model.receive_delivery(payload["id"])
    delivery_model.receive_delivery(payload["id"])  # retries are harmless
    assert files_model.read_json(page_dir / "cursor.json")["seq"] == delivered_through
    assert page_state(page_dir)["pending"] == 1

    assert session_model.cmd_wait(page_dir) == 0
    _, _, later_events = printed(capsys.readouterr().out)
    [later] = later_events
    assert later["id"] == "c2"
    receive_through(page_dir, later["seq"])
    assert page_state(page_dir)["pending"] == 0
    # Pickup is exact log evidence and does not rewrite the agent's page-wide claim.
    status = service_model.read_status(page_dir)
    assert status["state"] == "waiting"
    pickups = [e for e in events_model.read_events(page_dir) if e["kind"] == "pickup"]
    assert [e["events"] for e in pickups] == [["c1", shown[1]["id"]], ["c2"]]
    stored = [
        json.loads(line)
        for line in (page_dir / "events.jsonl").read_text().splitlines()
    ]
    assert all("seq" not in event for event in stored if event["kind"] == "pickup")
    working(page_dir, "revising the plan")
    assert page_state(page_dir)["activity"]["detail"] == "revising the plan"

    # A worker's report wakes the watcher like a user event — it is the
    # orchestrator's to fold into a version — but the user's banner count
    # deliberately leaves it out: a report is news the agent owes the page, not
    # something the user owes an answer.
    append_carried_log_record(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "widget": "t1",
            "meaning": {
                "scope": "page",
                "unit": "t1",
                "depends": ["t1"],
            },
            "action": "status",
            "detail": {"status": "review"},
            "revision": 1,
        },
    )
    assert page_state(page_dir)["pending"] == 0
    assert session_model.cmd_wait(page_dir) == 0
    _, _, shown = printed(capsys.readouterr().out)
    assert [(e["kind"], e.get("agent")) for e in shown] == [("report", "Indexer")]
    receive_through(page_dir, shown[-1]["seq"])
    assert files_model.read_json(page_dir / "cursor.json")["seq"] == shown[-1]["seq"]


@pytest.mark.parametrize("title", [None, "Workshop venue"])
def test_first_delivery_carries_thread_title_without_repeating_messages(
    page_dir, title
):
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Which space will be easier for everyone to find?",
        },
    )
    if title is not None:
        named = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "edit",
                str(page_dir),
                root["id"],
                "--title",
                title,
            ],
        )
        assert named.exit_code == 0, named.output
    waited = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert waited.exit_code == 0, waited.output
    _, header, shown = woken(waited.output)
    assert [event["id"] for event in shown] == [root["id"]]
    assert header["threads"] == [
        {
            "id": root["id"],
            "title": title,
            "anchor": None,
            "detached_from": None,
            "resolved": None,
            "elided": {"messages": 0, "actions": 0},
            "messages": [],
            "summaries": [],
            "actions": [],
        }
    ]


def test_wait_repeats_a_stable_transport_neutral_batch_until_ack(page_dir, sessionless):
    """The page and each event's sequence identify retries for any consumer of a
    wait that prints its delivery."""
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )

    first = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert first.exit_code == 0, first.output
    first_payload, header, [event] = printed(first.output)
    assert header["page"] == str(page_dir)
    assert (event["id"], event["seq"], event["text"]) == ("c1", 1, "hi")
    assert files_model.read_json(page_dir / "cursor.json") is None

    reread = CliRunner().invoke(
        cli_model.cli, ["delivery", "read", first_payload["id"]]
    )
    assert reread.exit_code == 0, reread.output
    assert json.loads(reread.output) == first_payload
    invalid = CliRunner().invoke(cli_model.cli, ["delivery", "read", "../status"])
    assert invalid.exit_code != 0
    assert "invalid delivery id" in invalid.output

    retry = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert retry.exit_code == 0, retry.output
    retry_payload, retry_batch, _ = printed(retry.output)
    assert retry_batch == header
    assert retry_payload["id"] != first_payload["id"]
    pickups = [e for e in events_model.read_events(page_dir) if e["kind"] == "pickup"]
    assert pickups == []

    # If wait output was lost or truncated, retrieving it again before ack can
    # include a newer event. The old event keeps the same page-and-seq identity
    # for the receiving task to skip.
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "later"}
    )
    grown = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert grown.exit_code == 0, grown.output
    _, grown_header, grown_events = printed(grown.output)
    assert grown_header["page"] == header["page"]
    assert grown_header["threads"][0] == header["threads"][0]
    assert [thread["id"] for thread in grown_header["threads"]] == ["c1", "c2"]
    assert grown_header["through_seq"] == 2
    assert [event["seq"] for event in grown_events] == [1, 2]


def test_thread_read_is_exact_and_paginated(page_dir):
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "selected", "author": "user", "text": "one"},
    )
    parent = root["id"]
    messages = [root]
    for author, text in (("agent", "two"), ("user", "three")):
        message = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": parent, "text": text},
        )
        messages.append(message)
        parent = message["id"]
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "neighbor", "author": "user", "text": "else"},
    )

    first = CliRunner().invoke(
        cli_model.cli,
        ["page", "state", str(page_dir), root["id"], "--limit", "2"],
    )
    assert first.exit_code == 0, first.output
    reading = json.loads(first.output)
    assert reading["thread"]["id"] == root["id"]
    assert "threads" not in reading
    assert "neighbor" not in first.output
    assert [item["message"] for item in reading["content"]] == [
        messages[0]["id"],
        messages[1]["id"],
    ]
    assert [item["author"] for item in reading["content"]] == ["user", "agent"]
    assert reading["content"][1]["parent"] == messages[0]["id"]
    [move] = owed(reading)
    assert move["answer"] == {
        "kind": "reply",
        "to": messages[2]["id"],
        "for": messages[2]["id"],
    }
    second_seq = reading["content"][1]["source"]["seq"]
    assert reading["history"]["next_after"] == second_seq

    second = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "state",
            str(page_dir),
            root["id"],
            "--after",
            str(second_seq),
            "--limit",
            "2",
        ],
    )
    assert second.exit_code == 0, second.output
    continued = json.loads(second.output)
    assert [item["message"] for item in continued["content"]] == [messages[2]["id"]]
    assert continued["content"][0]["author"] == "user"
    assert continued["content"][0]["parent"] == messages[1]["id"]
    assert continued["history"]["next_after"] is None


def test_thread_summary_is_admitted_as_one_ordered_thread_range(page_dir):
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "one"},
    )
    internal_reaction = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "token": "mark"},
    )
    second = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "text": "two"},
    )
    third = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": second["id"], "text": "three"},
    )
    neighbor = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "elsewhere"},
    )

    def summarize(
        start: str,
        end: str,
        text: str = "The first exchange.",
    ):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "summarize",
                str(page_dir),
                "--from",
                start,
                "--through",
                end,
                "--text",
                text,
            ],
        )

    reversed_range = summarize(second["id"], root["id"])
    assert reversed_range.exit_code != 0
    assert "at least two messages in thread order" in reversed_range.output

    cross_thread = summarize(root["id"], neighbor["id"])
    assert cross_thread.exit_code != 0
    assert "endpoints must name spoken turns in one thread" in cross_thread.output

    reaction = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": third["id"],
            "token": "mark",
        },
    )
    standing_reaction_range = summarize(third["id"], reaction["id"])
    assert standing_reaction_range.exit_code != 0
    assert (
        "endpoints must name spoken turns in one thread"
        in standing_reaction_range.output
    )

    append_carried_log_record(
        page_dir,
        {"kind": "undo", "author": "user", "undoes": reaction["id"]},
    )
    withdrawn_range = summarize(third["id"], reaction["id"])
    assert withdrawn_range.exit_code != 0
    assert "endpoints must name spoken turns in one thread" in withdrawn_range.output

    described = summarize(second["id"], third["id"])
    assert described.exit_code == 0, described.output
    assert json.loads(described.output)["through"] == third["id"]

    accepted = summarize(root["id"], second["id"])
    assert accepted.exit_code == 0, accepted.output
    summary = json.loads(accepted.output)
    assert {
        key: summary[key] for key in ("kind", "thread", "from", "through", "text")
    } == {
        "kind": "summary",
        "thread": root["id"],
        "from": root["id"],
        "through": second["id"],
        "text": "The first exchange.",
    }

    read = CliRunner().invoke(
        cli_model.cli,
        ["page", "state", str(page_dir), root["id"]],
    )
    assert read.exit_code == 0, read.output
    [projected] = json.loads(read.output)["thread"]["summaries"]
    assert projected["id"] == summary["id"]
    assert projected["covers"] == [
        root["id"],
        internal_reaction["id"],
        second["id"],
    ]
    browser_thread = page_state(page_dir)["browser"]["thread"]["threads"][0]
    assert [message["id"] for message in browser_thread["msgs"]] == [
        root["id"],
        internal_reaction["id"],
        second["id"],
        third["id"],
    ]
    # The agent reads the summary the user is shown, which messages it leaves in view
    # included.
    assert browser_thread["summaries"] == [projected]


@pytest.mark.parametrize("label", [None, "Previous updates"])
def test_summary_cli_can_fold_without_prose_only_when_explicit(page_dir, label):
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Fix the layout."}
    )
    reply = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "text": "Checking the label row.",
        },
    )
    command = [
        "thread",
        "summarize",
        str(page_dir),
        "--from",
        root["id"],
        "--through",
        reply["id"],
    ]
    if label is not None:
        command.extend(["--label", label])

    missing = CliRunner().invoke(cli_model.cli, command)
    assert missing.exit_code != 0
    assert "empty text" in missing.output

    result = CliRunner().invoke(cli_model.cli, [*command, "--text", ""])
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert event["text"] == ""
    if label is None:
        assert "label" not in event
    else:
        assert event["label"] == label
    read = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert read.exit_code == 0, read.output
    [agent_fold] = json.loads(read.output)["thread"]["summaries"]
    [thread] = page_state(page_dir)["browser"]["thread"]["threads"]
    [fold] = thread["summaries"]
    assert fold == agent_fold
    assert (fold["label"], fold["text"], fold["covers"]) == (
        label if label is not None else "Earlier discussion",
        "",
        [root["id"], reply["id"]],
    )
    assert [message["text"] for message in thread["msgs"]] == [
        "Fix the layout.",
        "Checking the label row.",
    ]

    # Allowing an empty summary body must not admit an empty reply.
    with pytest.raises(SystemExit, match="empty text"):
        thread_model.cmd_reply(page_dir, root["id"], "", None, for_event=root["id"])


def test_summary_hint_keeps_the_latest_spoken_exchange_outside_reactions(page_dir):
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "turn 1"},
    )
    spoken = [root]
    for number in range(2, 5):
        spoken.append(
            append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": "user" if number % 2 else "agent",
                    "parent": root["id"],
                    "text": f"turn {number}",
                },
            )
        )
    middle_reaction = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "token": "mark"},
    )
    for number in range(5, 7):
        spoken.append(
            append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": "user" if number % 2 else "agent",
                    "parent": root["id"],
                    "text": f"turn {number}",
                },
            )
        )
    trailing_reaction = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root["id"], "token": "mark"},
    )
    events = events_model.read_events(page_dir)
    latest = next(event for event in events if event["id"] == spoken[-1]["id"])

    [digest] = thread_context_model.batch_threads(
        events,
        [latest],
        page_view_model.PageView(page_dir).within,
    )

    assert digest["summary_hint"] == {
        "from": spoken[0]["id"],
        "through": spoken[3]["id"],
    }
    assert digest["summary_hint"]["through"] not in {
        middle_reaction["id"],
        trailing_reaction["id"],
    }


def test_summary_hint_does_not_cross_a_fold_of_ephemeral_updates(page_dir):
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "x" * 1000}
    )
    updates = [
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root["id"],
                "text": "Checking details.",
                "ephemeral": True,
            },
        )
        for _ in range(2)
    ]
    older = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": root["id"], "text": "y" * 1000},
    )
    for author in ("agent", "user"):
        latest = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": root["id"], "text": "Next?"},
        )
    within = page_view_model.PageView(page_dir).within
    events = events_model.read_events(page_dir)
    update_ids = {update["id"] for update in updates}
    [unfolded] = thread_context_model.batch_threads(
        [event for event in events if event["id"] not in update_ids], [latest], within
    )
    assert unfolded["summary_hint"] == {"from": root["id"], "through": older["id"]}
    [folded] = thread_context_model.batch_threads(events, [latest], within)
    assert folded["summaries"][0]["covers"] == [update["id"] for update in updates]
    assert "summary_hint" not in folded


def test_summary_hint_chooses_a_qualifying_run_over_more_short_messages(page_dir):
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "x" * 1000}
    )
    long_reply = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": root["id"], "text": "y" * 1000},
    )
    for _ in range(2):
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root["id"],
                "text": "Checking details.",
                "ephemeral": True,
            },
        )
    # Three short older messages form a longer run, but the earlier two long
    # messages are the only run that qualifies for a suggestion.
    for author in ("agent", "user", "agent", "agent", "user"):
        latest = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": author, "parent": root["id"], "text": "Next?"},
        )
    [digest] = thread_context_model.batch_threads(
        events_model.read_events(page_dir),
        [latest],
        page_view_model.PageView(page_dir).within,
    )
    assert digest["summary_hint"] == {"from": root["id"], "through": long_reply["id"]}


def test_reply_is_fenced_to_the_exact_current_obligation(page_dir):
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "first", "author": "user", "text": "Use A."},
    )
    second = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "correction",
            "author": "user",
            "parent": first["id"],
            "text": "Correction: use B.",
        },
    )

    stale = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            "--for",
            first["id"],
            "--text",
            "Used A.",
        ],
    )
    assert stale.exit_code != 0
    assert "event 'first' takes no reply" in stale.output

    current = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            "--for",
            second["id"],
            "--text",
            "Used B.",
        ],
    )
    assert current.exit_code == 0, current.output
    assert events_model.read_events(page_dir)[-1]["responds"] == second["id"]


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
            "detail": {"options": ["east"]},
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
    before = state_json(page_dir)["activity"]["obligations"]
    assert before == [chose["id"], newer["id"]]

    replied = thread_model.cmd_reply(
        page_dir,
        asked["id"],
        "East noted.",
        "",
        for_event=chose["id"],
    )
    assert replied["responds"] == chose["id"]
    after = state_json(page_dir)
    assert after["activity"]["obligations"] == [newer["id"]]
    assert owed(after)[0]["answer"] == {
        "kind": "reply",
        "to": newer["id"],
        "for": newer["id"],
    }


def test_settling_a_frozen_widget_move_does_not_revive_its_superseded_move(
    claimed, capsys
):
    page_dir = claimed
    session_model.cmd_waiting(page_dir, "")
    session = service_model.page_claim(page_dir)
    lease = leases_model.take_lease(
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
            "detail": {"options": ["east"]},
        },
    )
    selecting = state_json(page_dir)
    assert [ask["source"] for ask in selecting["asks"]] == ["regions"]
    assert selecting["activity"]["obligations"] == []
    assert selecting["workflows"] == []
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == []
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
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
    assert completed["asks"] == []
    assert completed["activity"]["obligations"] == [answered["id"]]
    cleanup_model.prompt_turn("s1")
    receive_through(page_dir, last_deliverable_seq(page_dir))
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    blocked = json.loads(capsys.readouterr().out)
    assert "decision" not in blocked
    assert "1 acknowledged user move with no answer" in continued(blocked)
    assert answered["id"] in continued(blocked)

    append_carried_log_record(
        page_dir,
        {"kind": "undo", "author": "user", "undoes": answered["id"]},
    )
    resumed = state_json(page_dir)
    assert [ask["source"] for ask in resumed["asks"]] == ["regions"]
    assert resumed["activity"]["obligations"] == []
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
    assert state_json(page_dir)["activity"]["obligations"] == [answered["id"]]

    thread_model.cmd_reply(
        page_dir,
        asked["id"],
        "East noted.",
        "",
        for_event=answered["id"],
    )
    after = state_json(page_dir)["activity"]["obligations"]
    assert after == []


def test_a_delivered_reply_carries_the_thread_it_lands_in(page_dir, capsys):
    """A reply event names the message it answers and nothing else about its
    thread, and the agent's own answers are never delivered at all — they are
    not the user's news. So a follow-up reaches a session that has compacted, or
    one picking the page up, as an id it cannot resolve, and the answer goes out
    against half a thread. The envelope carries the rest: the anchor the
    thread hangs on and the messages the lines below it do not repeat."""
    serving(page_dir, 1)
    opened = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "why forty rather than four?",
            "anchor": {"section": "s-1", "quote": "one in about 40"},
        },
    )
    answered = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": opened["id"],
            "text": "the vendor has acknowledged it without naming a date",
        },
    )
    # Acknowledged, so the opening comment is off every later batch. That and
    # the agent's own answer — which, being nobody's news, was never on one —
    # leave the envelope as the only route to what was said.
    receive_through(page_dir, 1)
    followed = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": answered["id"],
            "text": "and if their release slips?",
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, shown = delivered(capsys)
    assert [e["id"] for e in shown] == [followed["id"]]
    assert shown[0]["answer"] == {
        "kind": "reply",
        "to": followed["id"],
        "for": followed["id"],
    }
    [thread] = header["threads"]
    assert thread["id"] == opened["id"]
    assert thread["anchor"] == {"section": "s-1", "quote": "one in about 40"}
    assert thread["resolved"] is None
    assert [(m["id"], m["author"]) for m in thread["messages"]] == [
        (opened["id"], "user"),
        (answered["id"], "agent"),
    ]
    assert "without naming a date" in thread["messages"][1]["text"]

    # A new thread carries its metadata without repeating the opening message.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "separately — the rollout"},
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, fresh, _ = delivered(capsys)
    [new_thread] = fresh["threads"]
    assert new_thread["title"] is None
    assert new_thread["messages"] == []

    # The user closing a thread from the panel posts a resolve, whose only
    # pointer at the thread is the message it names.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": followed["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, closed_batch, _ = delivered(capsys)
    [closed] = closed_batch["threads"]
    assert (closed["id"], closed["resolved"]) == (opened["id"], "user")


def test_a_delivered_gesture_on_a_sent_widget_carries_its_thread(page_dir, capsys):
    """An action names a widget, and a widget an agent sent lives in frozen
    thread markup rather than in any version. Neither the id nor the option it
    chose means anything without the message that asked, so the envelope
    resolves the widget to its thread and brings the markup along. An undo
    belongs to the thread holding the gesture it takes back."""
    subjects = (
        '<lf-command id="hub"><lf-task id="goal" status="active">'
        "<strong>Goal</strong>" + COMMAND_SUBJECTS + "</lf-task></lf-command>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("</section>", subjects + "</section>")
    )
    publish(page_dir)
    serving(page_dir, 1)
    # A second thread carrying a widget of its own, so resolving the acted
    # widget to its thread is a result and not the only answer available.
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "And which region first?",
            "markup": '<lf-options id="rg" choose>'
            '<lf-option id="r-eu"><strong>EU</strong></lf-option>'
            "</lf-options>",
        },
    )
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which mitigations should I carry into the patch?",
            "markup": '<lf-options id="gm" choose>'
            '<lf-option id="m-cap"><strong>Cap retries</strong></lf-option>'
            '<lf-option id="m-alert"><strong>Alert</strong></lf-option>'
            "</lf-options>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "gm",
            "action": "choose",
            "detail": {"options": ["m-cap"]},
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, shown = delivered(capsys)
    assert [e["id"] for e in shown] == [chose["id"]]
    [thread] = header["threads"]
    assert thread["id"] == asked["id"]
    # The markup, because `m-cap` is a word only the question spells out.
    assert 'id="m-cap"' in thread["messages"][0]["markup"]
    # And the pick in words, read from that frozen message: the group is left
    # out because it only encloses the option chosen in it.
    assert shown[0]["says"] == {"m-cap": "Cap retries"}

    # Standing, so a later delivery in this thread carries what the user
    # settled. Without it the agent meets the question with no answer under it
    # and replies reopening a list they have already ticked.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": asked["id"],
            "text": "that is the list",
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, standing_batch, _ = delivered(capsys)
    [standing] = standing_batch["threads"]
    assert [
        (a["author"], a["widget"], a["action"], a["detail"])
        for a in standing["actions"]
    ] == [("user", "gm", "choose", {"options": ["m-cap"]})]

    # Taken back, and the thread stops carrying it — the log keeps the
    # gesture, and no reading of the log stands on it.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": chose["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, withdrawn_batch, _ = delivered(capsys)
    [withdrawn] = withdrawn_batch["threads"]
    assert withdrawn["id"] == asked["id"]
    assert withdrawn["actions"] == []


def test_a_delivered_gesture_says_what_the_user_chose_on_their_version(
    page_dir, capsys
):
    """A page gesture is recorded as ids, and the agent reading the batch may
    hold none of the page: it compacted, or another session wrote it. The
    envelope spells out the elements the gesture names, from the revision the
    user pressed on, so a later version that rewords an option does not
    change what they chose. A gesture naming only its widget says the whole
    widget, and an undo says what it takes back."""
    asked = PAGE.replace(
        "<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1
    )
    (page_dir / "index.html").write_text(asked)
    publish(page_dir)
    (page_dir / "index.html").write_text(
        asked.replace("Ship dark.", "Ship behind the flag, reworded.")
    )
    advanced = stamp(page_dir, "Reworded the first plan")
    assert advanced.exit_code == 0, advanced.output
    serving(page_dir, 1)

    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan-choice",
            "action": "choose",
            "detail": {"options": ["flag-first"]},
        },
    )
    answered = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 2,
            "widget": "plan-choice",
            "action": "answer",
            "detail": {},
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, _, shown = delivered(capsys)
    assert [e["id"] for e in shown] == [answered["id"]]
    assert chose["attention"] is False
    [(widget, whole)] = shown[0]["says"].items()
    assert widget == "plan-choice"
    assert "Ship behind the flag, reworded." in whole and "Backfill first" in whole

    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": chose["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, _, [undone] = delivered(capsys)
    assert undone["says"] == {
        "flag-first": "effort: low risk: med Flag first Ship dark."
    }


def test_one_action_can_belong_to_its_widget_thread_and_the_thread_it_resolves(
    page_dir, capsys
):
    """A sent widget lives in one thread and may answer another. The raw
    event is stored once, while exact selection and wait expose both semantic
    memberships without duplicating the event in a delivered batch."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    serving(page_dir, 1)
    target = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "c-target",
            "author": "user",
            "revision": 1,
            "text": "Should we replace this wording?",
        },
    )
    origin = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Here is the proposed answer.",
            "markup": '<lf-suggestion id="thread-answer" resolves="c-target">'
            "<lf-old><p>Old words.</p></lf-old>"
            "<lf-new><p>New words.</p></lf-new>"
            "</lf-suggestion>",
        },
    )
    target_seq = next(
        event["seq"]
        for event in events_model.read_events(page_dir)
        if event["id"] == target["id"]
    )
    receive_through(page_dir, target_seq)
    capsys.readouterr()
    accepted = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-answer",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, shown = delivered(capsys)
    assert [event["id"] for event in shown] == [accepted["id"]]
    assert shown[0]["threads"] == [origin["id"], target["id"]]
    assert shown[0]["answer"] == {
        "kind": "reply",
        "to": origin["id"],
        "for": accepted["id"],
    }
    assert [thread["id"] for thread in header["threads"]] == [
        origin["id"],
        target["id"],
    ]
    for thread, expected in (
        (origin["id"], [origin["id"], accepted["id"]]),
        (target["id"], [target["id"], accepted["id"]]),
    ):
        assert thread_records(page_dir, thread) == expected

    reply = thread_model.cmd_reply(
        page_dir,
        origin["id"],
        "Applied the accepted wording.",
        None,
        for_event=accepted["id"],
    )
    assert reply["parent"] == origin["id"]


def test_a_delivered_gesture_on_a_sent_widget_keeps_its_message_in_a_long_thread(
    page_dir, sessionless, capsys
):
    """A pick is meaningful only beside the message that declared its widget. Keep
    that message even when a long thread would normally elide it from the delivery
    envelope."""
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "How should I recover this branch?",
        },
    )
    parent = root["id"]
    asking_message = None
    for index in range(11):
        message = {
            "kind": "reply",
            "author": "agent",
            "parent": parent,
            "text": f"Recovery context {index}.",
        }
        if index == 2:
            message["markup"] = (
                '<lf-options id="thread-commands" choose>'
                '<lf-option id="restart"><strong>Restart</strong></lf-option>'
                '<lf-option id="park"><strong>Park</strong></lf-option>'
                "</lf-options>"
            )
        sent = append_carried_log_record(page_dir, message)
        parent = sent["id"]
        if index == 2:
            asking_message = sent
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-commands",
            "action": "choose",
            "detail": {"options": ["restart"]},
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, shown = printed(capsys.readouterr().out)
    assert [event["id"] for event in shown] == [chose["id"]]
    [thread] = header["threads"]
    assert thread["id"] == root["id"]
    carried = next(
        message
        for message in thread["messages"]
        if message["id"] == asking_message["id"]
    )
    assert 'id="thread-commands"' in carried["markup"]


# A page whose suggestion answers c1, which is the one shipped shape where the
# gesture that settles a thread is made on a widget standing outside it.
SETTLING_PAGE = PAGE.replace(
    '<lf-ask id="plan-choice-decision">',
    '<lf-suggestion id="sug-refill" resolves="c1">\n'
    "  <lf-old><p>The manual sightings log.</p></lf-old>\n"
    "  <lf-new><p>Switch the north feeder to thistle.</p></lf-new>\n"
    '</lf-suggestion>\n<lf-ask id="plan-choice-decision">',
)
SETTLING_DECISION = {
    "kind": "comment",
    "id": "c1",
    "author": "user",
    "revision": 1,
    "anchor": {"section": "plan-choice-decision"},
    "drawing": {
        "format": "leaf-drawing/2",
        "strokes": [[[-20, 74], [50, 10], [120, 74]]],
        "viewport": [1200, 900],
        "scheme": "light",
    },
}
SETTLING_ACCEPT = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "sug-refill",
    "action": "decide",
    "detail": {"outcome": "accept"},
}


def _settling_page(page_dir):
    (page_dir / "index.html").write_text(SETTLING_PAGE)
    append_carried_log_record(page_dir, dict(SETTLING_DECISION))
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    publish(page_dir)
    serving(page_dir, 1)


def test_a_page_ask_that_settles_a_thread_carries_its_thread(page_dir, capsys):
    """A gesture settles a thread through its widget's `resolves`, and the
    widget it is made on need not stand in that thread — for the one shipped
    settling verb, `lf-suggestion`'s decide, it stands on the page and in no
    thread at all. Reading the sending widget alone therefore left the gesture
    that closes a thread as the one gesture arriving with nothing behind it."""
    _settling_page(page_dir)
    receive_through(page_dir, 1)  # c1 delivered; its words are the
    capsys.readouterr()  # envelope's to carry from here
    append_command(page_dir, dict(SETTLING_ACCEPT))
    # The action door accepts this event, so the shape is the product's own.
    events = events_model.read_events(page_dir)
    assert (
        event_contracts_model.action_contract_error(
            page_view_model.PageView(page_dir),
            events[-1],
            event_meaning_model.AdmissionReadings(
                page_view_model.PageView(page_dir),
                events,
                registry_storage.require_registry(page_dir),
            ),
        )
        is None
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [t["resolved"] for t in state_json(page_dir)["threads"]] == ["user"]
    assert [t["id"] for t in header["threads"]] == ["c1"], json.dumps(header)
    message = header["threads"][0]["messages"][0]
    assert "text" not in message
    assert message["drawing"] == SETTLING_DECISION["drawing"]


def test_an_undo_of_a_page_ask_carries_the_thread_it_reopens(page_dir, capsys):
    """Withdrawing that gesture reopens the thread, so the delivery owes
    the same reading the accept did."""
    _settling_page(page_dir)
    accepted = append_command(page_dir, dict(SETTLING_ACCEPT))
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": accepted["id"]}
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [t["resolved"] for t in state_json(page_dir)["threads"]] == [None]
    assert [t["id"] for t in header["threads"]] == ["c1"], json.dumps(header)


def test_exact_thread_history_and_wait_share_indirect_resolution_events(
    page_dir, capsys
):
    """Rejecting an accepted answer, undoing that rejection, and later restating
    what the answer rested on all change the same thread without naming it
    directly. Exact history and live delivery use one Leaf-owned membership join."""
    _settling_page(page_dir)
    accepted = append_command(page_dir, dict(SETTLING_ACCEPT))
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()

    rejected = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "reject"},
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [thread["id"] for thread in header["threads"]] == ["c1"]

    rejected_seq = next(
        event["seq"]
        for event in events_model.read_events(page_dir)
        if event["id"] == rejected["id"]
    )
    receive_through(page_dir, rejected_seq)
    capsys.readouterr()
    undone = append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": rejected["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [thread["id"] for thread in header["threads"]] == ["c1"]

    restated = append_carried_log_record(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": 2,
            "text": "rewrote the suggestion",
            "restated": ["sug-refill"],
        },
    )
    assert thread_records(page_dir, "c1") == [
        "c1",
        accepted["id"],
        rejected["id"],
        undone["id"],
        restated["id"],
    ]
    assert state_json(page_dir)["threads"][0]["resolved"] is None


# One authored id for the group, so an action can name it. Its options already
# carry ids, which is what lets a floor land inside the widget rather than on it.
PICKS_PAGE = PAGE.replace("<lf-options>", '<lf-options id="picks">')


@pytest.mark.parametrize("rewritten", [True, False])
def test_a_delivery_and_page_state_agree_on_what_a_floor_took_back(
    page_dir, capsys, rewritten
):
    """An answer rests on the widget that sent it and on the ids that widget's
    detail names inside itself, so a version rewriting one of those takes the
    answer back and the question stands open again. `page state` has always read
    it that way, holding the whole page. A delivery holds the log and may not
    raise on the gate that loading a page's vendored registry is — but where an
    element sits was never the vocabulary's to answer, so it reads that much and
    agrees.

    Told otherwise the two disagree silently, and in the worst direction: the
    user watches their question reopen while the agent is told, in the same
    breath as their follow-up, that they had already answered it.

    The floor lands on the option rather than the group. Before a new reply,
    only a rewritten answer reopens the thread; the user's subsequent question
    resumes either thread, and delivery agrees with page state."""
    (page_dir / "index.html").write_text(PICKS_PAGE)
    let_a_pick_settle_a_thread(page_dir, "which")
    serving(page_dir, 1)
    opened = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "which",
            "author": "user",
            "text": "which of these?",
            "anchor": {"section": "picks"},
        },
    )
    publish(page_dir, 1)
    answered = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"options": ["flag-first"]},
        },
    )
    # Rewriting the option they picked retracts the pick: the thing they chose is
    # not the thing on the page any more. Leaving it alone is the other arm.
    note = {
        "kind": "note",
        "author": "agent",
        "version": 2,
        "revision": 2,
        "text": "rewrote the first option" if rewritten else "tidied the prose",
    }
    if rewritten:
        note["restated"] = ["flag-first"]
    append_carried_log_record(page_dir, note)
    # By seq off the log: `append_event` hands back what it was given plus an id,
    # and a seq is the line the log gave it.
    logged_seq = {e["id"]: e["seq"] for e in events_model.read_events(page_dir)}
    receive_through(page_dir, logged_seq[answered["id"]])
    [before_reply] = state_json(page_dir)["threads"]
    assert (before_reply["resolved"] is None) is rewritten
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": opened["id"],
            "text": "so which is it now?",
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    [delivered_thread] = header["threads"]
    assert delivered_thread["id"] == opened["id"]
    [standing] = state_json(page_dir)["threads"]
    assert delivered_thread["resolved"] == standing["resolved"]
    # The new spoken turn resumes either thread, regardless of its old answer.
    assert delivered_thread["resolved"] is None


def test_the_envelope_stops_growing_with_the_thread(page_dir, capsys):
    """A delivery reprints the whole thread every time, because the agent it is
    for may hold none of it. Unbounded, the header grows with the thread
    until it alone outgrows the output it prints into — and that is the one
    shape acknowledgement cannot recover from, since the ack rule's remedy for
    truncation is to rerun, and a rerun prints the same oversize header. So the
    digest keeps the message that opened the thread and the most recent, and
    says how many it dropped between."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    serving(page_dir, 1)
    markup = (
        '<lf-options id="{i}" choose>'
        + "".join(
            f'<lf-option id="{{i}}-o{n}"><strong>Option {n}</strong> '
            + "z" * 60
            + "</lf-option>"
            for n in range(3)
        )
        + "</lf-options>"
    )
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "y" * 188},
    )
    initial_thread_state_size = len(json.dumps(state_json(page_dir)["threads"]))
    parent, headers = root["id"], []
    for turn in range(30):
        agent = append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": parent,
                "text": "x" * 532,  # the shipped ship-review example's reply length
                "markup": markup.format(i=f"w{turn}"),
            },
        )
        parent = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": "user", "parent": agent["id"], "text": "ok"},
        )["id"]
        assert session_model.cmd_wait(page_dir) == 0
        _, batch, _ = delivered(capsys)
        headers.append(len(json.dumps(batch["threads"])))
        receive_through(page_dir, last_deliverable_seq(page_dir))
        capsys.readouterr()

    # Flat, not merely slower: twenty further exchanges add only the few
    # characters a longer sequence number spends. Page state likewise keeps the
    # thread itself flat; its separate element inventory grows here because
    # every reply deliberately adds a live widget contract.
    assert headers[-1] - headers[9] < 100, headers
    assert (
        len(json.dumps(state_json(page_dir)["threads"])) - initial_thread_state_size
        < 100
    )
    [thread] = batch["threads"]
    assert len(thread["messages"]) == thread_context_model.SHOWN
    assert thread["elided"]["messages"] == 52
    # The opening message survives the bound: it holds what the thread is about.
    assert thread["messages"][0]["id"] == root["id"]


def test_the_bound_keeps_the_message_a_carried_gesture_needs(page_dir, capsys):
    """A gesture names a widget, and what that widget asked lives only in the
    message that sent it: page markup is a file read away, thread markup is
    nowhere but the log. So a long thread whose question sits early would
    otherwise deliver `choose m-cap` with nothing saying what `gm` asked or what
    `m-cap` said — the defect this reading exists to fix, surviving the bound."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "revision": 1, "text": "how?"}
    )
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "text": "Which mitigations?",
            "markup": '<lf-options id="gm" choose multiple>'
            '<lf-option id="m-cap"><strong>Cap retries</strong></lf-option>'
            "</lf-options>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "gm",
            "action": "choose",
            "detail": {"options": ["m-cap"]},
        },
    )
    # Bury the question: enough later exchange that the bound would drop it.
    parent = root["id"]
    for turn in range(12):
        parent = append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "user" if turn % 2 else "agent",
                "parent": parent,
                "text": f"turn {turn}",
            },
        )["id"]
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()
    append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": parent, "text": "so, settled?"},
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, batch, _ = delivered(capsys)
    [thread] = batch["threads"]
    assert thread["elided"]["messages"] > 0, "the bound did not engage"
    assert [a["widget"] for a in thread["actions"]] == ["gm"]
    # The question survives the elision that took its neighbours.
    carrying = [m for m in thread["messages"] if m.get("markup")]
    assert [m["id"] for m in carrying] == [asked["id"]], json.dumps(thread["messages"])
    assert 'id="m-cap"' in carrying[0]["markup"]
    assert chose["id"] == thread["actions"][0]["id"]


def test_receipt_uses_an_immutable_delivery_and_advances_monotonically(page_dir):
    service_model.claim_page(page_dir)
    first = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "first"}
    )
    older = freeze_events(page_dir, [first])
    second = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "second"}
    )
    newer = freeze_events(page_dir, [first, second])
    runner = CliRunner()
    missing = runner.invoke(cli_model.cli, ["wait", "--ack", "00000000"])
    assert missing.exit_code == 1
    assert "unknown delivery" in missing.output
    combined = runner.invoke(
        cli_model.cli, ["wait", str(page_dir), "--ack", newer["id"]]
    )
    assert combined.exit_code == 2
    assert files_model.read_json(page_dir / "cursor.json") is None
    for payload in (newer, newer, older):
        assert delivery_model.receive_delivery(payload["id"]) == [page_dir]
        assert files_model.read_json(page_dir / "cursor.json") == {"seq": 2}
    pickups = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert len(pickups) == 1
    assert pickups[0]["events"] == [first["id"], second["id"]]


def test_interrupted_pickup_leaves_the_delivery_unreceived(page_dir, monkeypatch):
    service_model.claim_page(page_dir)
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Answer"}
    )
    payload = freeze_events(page_dir, [comment])

    def failed_pickup(*args, **kwargs):
        raise OSError("pickup write interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(delivery_model, "record_pickup", failed_pickup)
        with pytest.raises(OSError, match="pickup write interrupted"):
            delivery_model.receive_delivery(payload["id"])
    assert files_model.read_json(page_dir / "cursor.json") is None
    assert page_state(page_dir)["pending"] == 1
    delivery_model.receive_delivery(payload["id"])
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert pickup["events"] == [comment["id"]]
    assert pickup["phase"] == "opened"
    assert page_state(page_dir)["activity"]["obligations"][0]["stage"] == "picked_up"


def test_receipt_refuses_a_delivery_from_a_replaced_log(page_dir):
    service_model.claim_page(page_dir)
    original = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Original"}
    )
    payload = freeze_events(page_dir, [original])
    (page_dir / "events.jsonl").write_text("")
    replacement = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Replacement"}
    )
    [replacement] = events_model.read_events(page_dir)
    assert replacement["seq"] == payload["batches"][0]["through_seq"]
    with pytest.raises(RuntimeError):
        delivery_model.receive_delivery(payload["id"])
    assert files_model.read_json(page_dir / "cursor.json") is None
    assert events_model.read_events(page_dir) == [replacement]


def test_receiving_a_delivery_keeps_each_pages_response_obligation(page_dir, tmp_path):
    other = tmp_path / "other"
    shutil.copytree(page_dir, other)
    batches = []
    for page in (page_dir, other):
        service_model.claim_page(page)
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Please answer"}
        )
        with service_model.PageTransaction(page) as transaction:
            batches.append(
                delivery_model.batch_data(page, transaction, transaction.events)
            )
    payload = delivery_model.freeze_delivery(batches, carrier="wait")
    later = append_carried_log_record(
        other, {"kind": "comment", "author": "user", "text": "Later"}
    )
    assert delivery_model.receive_delivery(payload["id"]) == [page_dir, other]
    for page in (page_dir, other):
        assert files_model.read_json(page / "cursor.json") == {"seq": 1}
        obligations = page_state(page)["activity"]["obligations"]
        assert obligations[0]["stage"] == "picked_up"
    assert page_state(other)["pending"] == 1
    assert (
        service_model.unacknowledged(events_model.read_events(other), 1)[0]["id"]
        == later["id"]
    )


def test_concurrent_receipts_observe_one_session_without_nesting_page_locks(
    claimed, tmp_path, spawn
):
    """Both consumers hold disjoint page locks before observing the session.

    Each takes only the shared session lock next; it never waits for a sibling
    page. Both receipts complete and the silent sibling derives the same turn.
    """
    second = tmp_path / "second"
    silent = tmp_path / "silent"
    for page in (second, silent):
        shutil.copytree(claimed, page)
        service_model.claim_page(page)
    pages = (claimed, second, silent)
    session_id = service_model.page_claim(claimed)["id"]
    for page in pages:
        with service_model.PageTransaction(page) as transaction:
            transaction.close_turn(session_id)
    cleanup_model.prompt_turn(session_id)
    deliveries = []
    for page in pages[:2]:
        comment = append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Please answer"}
        )
        deliveries.append(freeze_events(page, [comment]))
    release = tmp_path / "release-sibling-sweeps"
    arrivals = [tmp_path / f"sweep-{number}" for number in range(2)]
    probe = """\
import time
from leaf import delivery

original_lock = delivery.flocked
def synchronized_lock(*args, **kwargs):
    Path(os.environ["ARRIVAL"]).write_text("ready", encoding="utf-8")
    release = Path(os.environ["RELEASE"])
    while not release.exists():
        time.sleep(0.01)
    return original_lock(*args, **kwargs)

delivery.flocked = synchronized_lock
delivery.receive_delivery(os.environ["DELIVERY"])
"""
    consumers = [
        spawn_probe(
            spawn,
            page,
            probe,
            DELIVERY=payload["id"],
            ARRIVAL=arrival,
            RELEASE=release,
        )
        for page, payload, arrival in zip(pages[:2], deliveries, arrivals, strict=True)
    ]
    wait_for(
        lambda: all(arrival.exists() for arrival in arrivals),
        bool,
        failure="both receipts did not reach their shared session observation",
    )
    release.write_text("continue", encoding="utf-8")
    for consumer in consumers:
        out, err = consumer.communicate(timeout=STATED_TIMEOUT)
        assert consumer.returncode == 0, out + err
    for page in pages:
        assert service_model.page_claim(page)["turn_closed"] is None
    for page in pages[:2]:
        assert files_model.read_json(page / "cursor.json") == {"seq": 1}
        [pickup] = [
            event
            for event in events_model.read_events(page)
            if event["kind"] == "pickup"
        ]
        assert pickup["phase"] == "opened"
        assert page_state(page)["activity"]["obligations"][0]["stage"] == "picked_up"
    assert files_model.read_json(silent / "cursor.json") is None


def test_receipt_checks_the_owner_after_acquiring_the_page_lock(
    page_dir, spawn, monkeypatch
):
    service_model.claim_page(page_dir)
    event = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Answer"}
    )
    payload = freeze_events(page_dir, [event])
    with service_model.PageTransaction(page_dir):
        # The command must wait behind the same lock that protects ownership changes.
        receiving = spawn_probe(
            spawn,
            page_dir,
            """
from leaf import delivery, service
original_enter = service.PageTransaction.__enter__
def entered(transaction):
    print("locking", flush=True)
    return original_enter(transaction)
service.PageTransaction.__enter__ = entered
delivery.receive_delivery(os.environ["DELIVERY"])
""",
            DELIVERY=payload["id"],
        )
        assert receiving.stdout.readline().strip() == "locking"
        record_claim(page_dir, id="successor", pid=os.getpid())
    out, err = receiving.communicate(timeout=STATED_TIMEOUT)
    assert receiving.returncode == 1, out + err
    assert "delivery no longer owns its page" in err
    assert files_model.read_json(page_dir / "cursor.json") is None
    assert not any(
        item["kind"] == "pickup" for item in events_model.read_events(page_dir)
    )
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "successor")
    assert delivery_model.receive_delivery(payload["id"]) == [page_dir]
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}


def test_a_cursor_past_the_log_holds_nothing_in_the_log_that_replaced_it(page_dir):
    """A cursor names a position in this log. Re-vendoring a page whose log is
    gone leaves the file naming a seq the new log has not reached, and reading it
    as acknowledgement would swallow every event that log will ever hold."""
    serving(page_dir, 1)
    cleanup_model.write_json(page_dir / "cursor.json", {"seq": 47})
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )

    assert page_state(page_dir)["cursor"] == 0
    assert page_state(page_dir)["pending"] == 1
    wait_result = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert wait_result.exit_code == 0, wait_result.output
    _, _, events = woken(wait_result.output)
    [event] = events
    assert (event["id"], event["seq"]) == ("c1", 1)

    # Confirming the delivered batch replaces the stale position, so the next
    # read is an ordinary one.
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}
    assert page_state(page_dir)["cursor"] == 1
    assert page_state(page_dir)["pending"] == 0


def test_ack_rearms_the_wait_after_releasing_the_cursor_transaction(
    page_dir, spawn, codex_loop
):
    serving(page_dir, 1)
    codex_loop(page_dir)
    session_model.cmd_waiting(page_dir, "answering the first comment")
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "one"}
    )
    delivery_id = delivery_through(page_dir, 1)
    acknowledging = spawn(
        [*LEAF_COMMAND, "wait", "--ack", delivery_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ,
    )
    lease_path = leases_model.waiter_lease_path(
        page_dir, harness_model.session_harness().session
    )
    wait_for(
        lambda: (leases_model.lock_is_held(lease_path), acknowledging.poll()),
        lambda reading: reading[0] or reading[1] is not None,
        failure="the acknowledgement neither rearmed the wait nor exited",
    )

    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}
    assert leases_model.lock_is_held(lease_path), (
        "acknowledgement returned without holding the next wait"
    )
    status_before_delivery = (page_dir / "status.json").read_bytes()
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c2", "author": "user", "text": "two"}
    )
    out, err = acknowledging.communicate(timeout=STATED_TIMEOUT)

    # 0 is the re-armed wait's own code for a batch on stdout, so one exit tells
    # an agent which of the two happened rather than sending it to the streams.
    assert acknowledging.returncode == 0, f"{out}{err}"
    _, header, [event] = printed(out)
    assert header["page"] == str(page_dir)
    assert (event["id"], event["seq"], event["text"]) == ("c2", 3, "two")
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}
    assert (page_dir / "status.json").read_bytes() == status_before_delivery


def test_ack_success_outlives_a_refused_rearm(page_dir, snapshot):
    """A standing watcher ends the re-arm the way it ends a bare `leaf wait`, on
    2. The acknowledgement still landed: 1 is the code that says it did not, and
    the cursor names the event the batch reached."""
    service_model.claim_page(page_dir)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )
    identity = harness_model.session_harness()
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(page_dir, identity.session)
    )
    assert lease
    with lease:
        result = CliRunner().invoke(
            cli_model.cli, ["wait", "--ack", delivery_through(page_dir, 1)]
        )

    assert result.exit_code == 2, result.output
    assert "another `leaf wait` is already active" in result.output
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}

    snapshot.check(
        yaml_document(
            "Full CLI output after acknowledgment succeeds but its next wait cannot start.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "exit": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            ),
        )
    )


def test_ack_rearm_does_not_reclaim_a_page_from_its_successor(page_dir, snapshot):
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    )
    record_claim(page_dir, id="successor", pid=os.getpid())

    result = CliRunner().invoke(
        cli_model.cli, ["wait", "--ack", delivery_through(page_dir, 1)]
    )

    assert result.exit_code == 1, result.output
    assert "delivery no longer owns its page" in result.output
    assert files_model.read_json(page_dir / "cursor.json") is None
    assert service_model.page_claim(page_dir)["id"] == "successor"

    snapshot.check(
        yaml_document(
            "Full CLI output when receipt is refused after page ownership transfers.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "exit": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            ),
        )
    )


def test_ack_rearm_keeps_the_other_pages_when_its_batch_page_transfers(
    page_dir, tmp_path, spawn, monkeypatch, codex_loop
):
    """The acknowledged page is a delivery coordinate, not the rearm's target.

    Hold its status read after the session-wide watcher selected both pages,
    then transfer that page and speak on the other one. The transfer must drop
    only its page: ending the rearm there leaves the other page silently
    unwatched until a later hook repairs it.
    """
    other = tmp_path / "second-page"
    shutil.copytree(page_dir, other)
    serving(page_dir, 1)
    serving(other, 2)
    codex_loop(page_dir)
    codex_loop(other)
    session_model.cmd_waiting(page_dir, "first page")
    session_model.cmd_waiting(other, "second page")
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "first", "author": "user", "text": "one"},
    )
    delivery_id = delivery_through(page_dir, 1)
    status_path = page_dir / "status.json"
    status = status_path.read_bytes()
    hold_status_read(status_path)
    acknowledging = spawn(
        [*LEAF_COMMAND, "wait", "--ack", delivery_id],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    writer = fifo_writer(status_path, "the rearm never selected its batch page")
    identity = harness_model.session_harness()
    lease_path = leases_model.waiter_lease_path(page_dir, identity.session)
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}
    assert leases_model.lock_is_held(lease_path)
    assert acknowledging.poll() is None

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "successor")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page_dir)
    append_carried_log_record(
        other,
        {"kind": "comment", "id": "second", "author": "user", "text": "two"},
    )
    os.write(writer, status)
    os.close(writer)

    out, err = acknowledging.communicate(timeout=STATED_TIMEOUT)
    assert acknowledging.returncode == 0, f"{out}{err}"
    _, header, [event] = printed(out)
    assert header["page"] == str(other)
    assert (event["id"], event["text"]) == ("second", "two")
    assert files_model.read_json(other / "cursor.json") is None
    assert service_model.page_claim(page_dir)["id"] == "successor"


def test_ack_rearm_reports_when_its_only_page_transfers_after_selection(
    page_dir, spawn, monkeypatch, snapshot
):
    """A successor's page is not idle when it leaves the session-wide watch.

    Hold the status read after the rearm selected its sole page, then transfer
    it. The empty watch must report the ownership change rather than describing
    the successor's live page as an ended leaf.
    """
    serving(page_dir, 1)
    service_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir, "first page")
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "first", "author": "user", "text": "one"},
    )
    delivery_id = delivery_through(page_dir, 1)
    status_path = page_dir / "status.json"
    status = status_path.read_bytes()
    hold_status_read(status_path)
    acknowledging = spawn(
        [*LEAF_COMMAND, "wait", "--ack", delivery_id],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    writer = fifo_writer(status_path, "the rearm never selected its batch page")
    identity = harness_model.session_harness()
    lease_path = leases_model.waiter_lease_path(page_dir, identity.session)
    assert files_model.read_json(page_dir / "cursor.json") == {"seq": 1}
    assert leases_model.lock_is_held(lease_path)
    assert acknowledging.poll() is None

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "successor")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page_dir)
    os.write(writer, status)
    os.close(writer)

    out, err = acknowledging.communicate(timeout=STATED_TIMEOUT)
    assert (acknowledging.returncode, out) == (2, ""), err
    assert f"stopped watching {page_dir}: this session no longer owns it" in err
    assert "the leaf ended" not in err
    assert service_model.page_claim(page_dir)["id"] == "successor"

    snapshot.check(
        yaml_document(
            "An already-running acknowledgment wait loses its page to another session.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "exit": acknowledging.returncode,
                    "stdout": out,
                    "stderr": err,
                },
            ),
        )
    )


def test_wait_preserves_the_work_in_hand_on_mid_work_output(page_dir, capsys):
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    working(page_dir, "running the browser suite")
    status_path = page_dir / "status.json"
    before = status_path.read_bytes()
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "one more thing"},
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, _, shown = delivered(capsys)
    assert [event["id"] for event in shown] == ["c1"]
    assert status_path.read_bytes() == before
    [task] = page_state(page_dir)["browser"]["tasks"]
    assert task["running"]["text"] == "running the browser suite"


def test_a_wait_watches_a_stopped_server_until_its_page_ends(
    page_dir, monkeypatch, capsys
):
    """A stopped server neither ends a `leaf wait` nor is the wait's to start
    again: the page ends the wait, by going idle or changing hands.

    A wait used to read a disabled service as a page it had lost, and end, so
    every restart, which disables the service as a stop does, had to say it was
    not a stop."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "standing",
        },
    )
    session_model.cmd_waiting(page_dir, "review the page")

    def unexpected_start(*_args, **_kwargs):
        pytest.fail("a disabled service was revived")

    monkeypatch.setattr(hosting_model, "start_server", unexpected_start)
    assert hosting_model.cmd_stop(page_dir) is False

    def unexpected_delivery(reading):
        pytest.fail(f"nothing was sent, yet {reading.page_dir} delivered")

    watch = session_model.Watch(None, pages=(page_dir,))
    try:
        assert watch.acquire()
        passed = session_model.read_watch_pass(watch, page_dir, unexpected_delivery)
    finally:
        watch.release()
    assert passed.outcome is None
    assert [reading.page_dir for reading in passed.live] == [page_dir]

    declare_idle(page_dir)
    capsys.readouterr()
    assert session_model.cmd_wait(page_dir) == 2
    assert "the leaf ended" in capsys.readouterr().err


@pytest.mark.parametrize("revival", ["refused", "died again"])
def test_a_revival_that_does_not_hold_ends_the_wait(
    page_dir, monkeypatch, capsys, revival
):
    """An enabled service whose process died gets one revival. When that does not
    bring it back, refused or dead again once it did, nothing else will, so the
    wait ends and wakes the agent with the command that serves the page."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "standing",
        },
    )
    session_model.cmd_waiting(page_dir, "review the page")

    def refused_start(*_args, **_kwargs):
        raise StartRefused("the port is taken")

    def start_that_dies(*_args, **_kwargs):
        return hosting_model.PageStart("http://127.0.0.1:1/", None, page_dir)

    monkeypatch.setattr(
        hosting_model,
        "start_server",
        refused_start if revival == "refused" else start_that_dies,
    )

    def unexpected_delivery(reading):
        pytest.fail(f"nothing was sent, yet {reading.page_dir} delivered")

    watch = session_model.Watch(None, pages=(page_dir,))
    try:
        assert watch.acquire()
        passed = session_model.read_watch_pass(watch, page_dir, unexpected_delivery)
        if revival == "died again":
            assert passed.outcome is None
            # Past the recheck interval, as the next pass five seconds on would be.
            watch._check_at.clear()
            passed = session_model.read_watch_pass(watch, page_dir, unexpected_delivery)
    finally:
        watch.release()

    assert passed.outcome == 2
    assert (
        f"{page_dir}: server is not running; restart it with "
        f"`leaf server start {page_dir}`"
    ) in capsys.readouterr().err


def test_a_page_without_a_declaration_leaves_the_sessions_wait_running(
    page_dir, tmp_path
):
    """A claimed page whose agent has declared nothing, such as a copy served
    before any `leaf status`, reads as waiting on its user: the session's wait
    passes over it and still delivers a sibling page's comment, and the copy's
    own state reads as listening. The copy sorts ahead of the page, so a pass
    that stumbled on it would end before reaching the comment."""
    publish(page_dir)
    serving(page_dir, 1)
    service_model.claim_page(page_dir)
    copy = tmp_path / "copy"
    shutil.copytree(page_dir, copy)
    (copy / schema_model.STATUS_FILE).unlink(missing_ok=True)
    serving(copy, 1)
    service_model.claim_page(copy)
    assert service_model.owned_pages(session_model.session_harness().session) == [
        copy.resolve(),
        page_dir.resolve(),
    ]
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "still there?"},
    )

    waited = CliRunner().invoke(cli_model.cli, ["wait"])

    assert waited.exit_code == 0, waited.output
    _, batch, shown = woken(waited.output)
    assert batch["page"] == str(page_dir.resolve())
    assert [event["id"] for event in shown] == [comment["id"]]
    assert page_state(copy)["activity"]["kind"] == "listening"


@pytest.mark.parametrize("wait", ["named", "session"])
def test_a_wait_on_a_page_never_served_ends_at_once(page_dir, capsys, wait):
    """A page with no service record has nothing that will serve it, so a wait
    on it ends on its first pass with the command that does, whether it was
    named or claimed earlier and found by the session's wait."""
    assert not (page_dir / "service.json").exists()
    session_model.cmd_waiting(page_dir, "review the page")
    service_model.claim_page(page_dir)

    def unexpected_delivery(reading):
        pytest.fail(f"nothing was sent, yet {reading.page_dir} delivered")

    named = page_dir if wait == "named" else None
    watch = session_model.Watch(
        harness_model.session_harness(), pages=(page_dir,) if named else ()
    )
    try:
        assert watch.acquire()
        passed = session_model.read_watch_pass(watch, named, unexpected_delivery)
    finally:
        watch.release()

    assert passed.outcome == 2
    assert f"restart it with `leaf server start {page_dir}`" in (
        capsys.readouterr().err
    )


@pytest.mark.parametrize(
    "stopped", ["during the block", "during the lease wait", "never"]
)
def test_a_stop_during_a_restart_keeps_the_service_stopped(
    page_dir, monkeypatch, stopped
):
    """`leaf server stop` while `page init` holds a service down to re-vendor it
    finds the service already disabled, and the restart must not enable it
    again after the block: the stop is the later word. Without one, the restart
    enables the service and starts it as a revival. A stop can also land while the
    restart's own stop is still waiting out the old server's lease, between two of
    its passes, and a later pass must not write the restart's mark back over it."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "standing",
        },
    )
    starts = []

    def recorded_start(page, **kwargs):
        starts.append(kwargs)
        return hosting_model.PageStart("http://127.0.0.1:1/", None, page)

    monkeypatch.setattr(hosting_model, "start_server", recorded_start)
    if stopped == "during the lease wait":
        # The old server holds its lease through the restart's first pass, and the
        # plain stop runs in the pause before the next one.
        take_lease, sleep = hosting_model.take_lease, hosting_model.time.sleep
        held = iter([True])
        monkeypatch.setattr(
            hosting_model,
            "take_lease",
            lambda path: None if next(held, False) else take_lease(path),
        )
        paused = iter([True])

        def stop_in_the_pause(seconds):
            if next(paused, False):
                hosting_model.cmd_stop(page_dir)
            sleep(seconds)

        monkeypatch.setattr(hosting_model.time, "sleep", stop_in_the_pause)
    with hosting_model.restarting_server(page_dir):
        assert not files_model.read_json(page_dir / "service.json")["enabled"]
        if stopped == "during the block":
            hosting_model.cmd_stop(page_dir)

    service = files_model.read_json(page_dir / "service.json")
    assert "restart" not in service
    if stopped == "never":
        assert service["enabled"]
        assert starts == [{"standing": True, "revive": True}]
    else:
        assert not service["enabled"]
        assert starts == []


def test_page_init_restarts_a_served_page_under_the_sessions_wait(
    page_dir, tmp_path, spawn
):
    """`page init` on a served page restarts its server itself, so the session's
    `leaf wait` carries on watching it.

    Re-vendoring a served page used to be three commands, and the first,
    `server stop`, disabled the service: a wait watching the page read that as a
    page it had lost, and ended. The comment after the re-vendor is the proof: only
    a wait still watching delivers it.
    """
    publish(page_dir)
    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    started = start_server_command(page_dir, session_id=session)
    assert started.returncode == 0, started.stderr
    url = json.loads(started.stdout)["url"]
    claim = service_model.page_claim(page_dir)
    generation = files_model.read_json(page_dir / "registry.json")["$layer"][
        "generation"
    ]
    session_model.cmd_waiting(page_dir, "review the page")
    waited = tmp_path / "wait.log"
    with waited.open("w", encoding="utf-8") as output:
        waiter = spawn(
            [*LEAF_COMMAND, "wait"],
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )
    wait_for(
        lambda: waiter.poll() is None and leases_model.wait_is_live(page_dir, session),
        bool,
        failure="the wait did not start watching the page",
    )

    revendored = subprocess.run(
        [*LEAF_COMMAND, "page", "init", str(page_dir)],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert revendored.returncode == 0, revendored.stderr
    assert (
        files_model.read_json(page_dir / "registry.json")["$layer"]["generation"]
        != generation
    )
    assert server_model.running_server(page_dir)["url"] == url
    # The restart claims nothing, so the turn the claim records is left as it was.
    assert service_model.page_claim(page_dir) == claim
    assert waiter.poll() is None, waited.read_text()

    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "text": "still there?",
        },
    )
    assert waiter.wait(timeout=STATED_TIMEOUT) == 0, waited.read_text()
    _, batch, [event] = woken(waited.read_text())
    assert batch["page"] == str(page_dir)
    assert event["text"] == "still there?"


def test_a_refused_revendor_leaves_the_running_server_alone(page_dir):
    """A re-vendor the page's log refuses is refused before the server goes down.

    A restart after the refusal would put this Leaf's server over the layer the
    page keeps, so a page vendored by another Leaf would be served by code its
    runtime does not speak. The same process answers at the same URL before and
    after, which is what `Leaf-Server`, the server's incarnation, says."""
    # A page made under a registry where lf-draft declared `decide`: the log keeps
    # a decision the incoming layer no longer speaks.
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>A decision.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "d1",
            "action": "decide",
            "detail": {"decision": "approved"},
            "meaning": {
                "scope": "page",
                "unit": "d1",
                "depends": ["d1"],
                "answer": None,
            },
        },
    )
    started = start_server_command(
        page_dir, session_id=os.environ["CLAUDE_CODE_SESSION_ID"]
    )
    assert started.returncode == 0, started.stderr
    url = json.loads(started.stdout)["url"]
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()

    def incarnation():
        with urllib.request.urlopen(state) as response:
            return response.headers["Leaf-Server"], response.headers["Leaf-Layer"]

    before = incarnation()

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 1
    assert "no longer speaks" in result.output
    assert server_model.running_server(page_dir)["url"] == url
    assert incarnation() == before


@pytest.mark.parametrize("service", ["stopped", "orphaned", "foreign"])
def test_page_init_leaves_a_service_it_cannot_restart_for_this_session(
    page_dir, service
):
    """Only an enabled service this command may restart comes back.

    A stopped service was stopped on purpose and stays stopped. A session service
    whose session has ended has nobody to come back for, so the re-vendor stops it
    and leaves it for the next `server start`. One another live session holds is
    refused before anything stops, since only that session could start it again.
    """
    publish(page_dir)
    started = start_server_command(page_dir, session_id="other")
    assert started.returncode == 0, started.stderr
    generation = files_model.read_json(page_dir / "registry.json")["$layer"][
        "generation"
    ]
    if service == "stopped":
        assert hosting_model.cmd_stop(page_dir) is True
    elif service == "orphaned":
        with service_model.PageTransaction(page_dir) as page:
            page.release_claim()

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    revendored = (
        files_model.read_json(page_dir / "registry.json")["$layer"]["generation"]
        != generation
    )
    if service == "foreign":
        assert result.exit_code == 1
        assert "served for another session" in result.output
        assert server_model.running_server(page_dir)
        assert not revendored
        return
    assert result.exit_code == 0, result.output
    assert revendored
    assert server_model.running_server(page_dir) is None
    assert not files_model.read_json(page_dir / "service.json")["enabled"]
    assert ("belonged to a session that has ended" in result.output) == (
        service == "orphaned"
    )


def test_a_watch_wakes_on_what_its_pass_read_moving(page_dir):
    """Between passes a watch follows the stamps of what the last pass read, so an
    append wakes it in a look rather than on a timer; with nothing moved it wakes
    on its timeout, for what a pass owes the clock.

    The first pass finds a page the mark before it did not know, so it returns at
    once: that mark stamped the old set."""
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()
    try:
        mark = watch.mark()
        list(watch.tick())
        assert watch.await_news(mark, timeout=STATED_TIMEOUT), (
            "the watch never woke on the page its mark had not read"
        )

        mark = watch.mark()
        list(watch.tick())
        assert not watch.await_news(mark, timeout=0.2)

        mark = watch.mark()
        list(watch.tick())
        appending = threading.Timer(
            0.2,
            append_carried_log_record,
            (page_dir, {"kind": "comment", "author": "user", "text": "hi"}),
        )
        appending.start()
        assert watch.await_news(mark, timeout=STATED_TIMEOUT), (
            "the watch never woke on the append"
        )
        appending.join()
        assert events_model.read_events(page_dir)[-1]["text"] == "hi"
    finally:
        watch.release()


def test_a_delayed_revival_cannot_cross_an_explicit_stop(page_dir, monkeypatch):
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    working(page_dir, "watching for a reply")
    entered, release = threading.Event(), threading.Event()
    real_start = hosting_model.start_server

    def delayed_start(*args, **kwargs):
        entered.set()
        assert release.wait(STATED_TIMEOUT)
        return real_start(*args, **kwargs)

    monkeypatch.setattr(hosting_model, "start_server", delayed_start)
    readings, errors = [], []
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()

    def tick():
        try:
            readings.extend(watch.tick())
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)
        finally:
            watch.release()

    reviving = threading.Thread(target=tick)
    reviving.start()
    assert entered.wait(STATED_TIMEOUT), "the watcher did not decide to revive"
    assert hosting_model.cmd_stop(page_dir) is False
    release.set()
    reviving.join(timeout=STATED_TIMEOUT)
    assert not reviving.is_alive(), "the revival never finished its tick"

    assert not reviving.is_alive()
    assert errors == []
    # The stop disabled the service, which the wait goes on watching.
    assert readings[0].watch_state == "watching"
    assert readings[0].lost is False
    assert readings[0].restarted is None
    assert files_model.read_json(page_dir / "service.json")["enabled"] is False
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_wait_restarts_a_server_that_died_under_it(
    page_dir, comment_once_served, capsys, snapshot
):
    """A page whose server died is offline in the user's browser and nowhere
    else — so `leaf wait`, the one thing positioned to notice, brings it back
    rather than exiting and leaving the discovery to the user."""

    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    comment_once_served(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    info = server_model.running_server(page_dir)
    # The revived server has to answer on the URL it published, key included:
    # the user's browser has been polling that address since it died.
    assert info
    state = urllib.parse.urlsplit(info["url"])
    assert (
        urllib.request.urlopen(state._replace(path="/api/state").geturl()).status == 200
    )
    printed = capsys.readouterr()
    assert "server had died; restarted" in printed.err
    snapshot.check(
        yaml_document(
            "A wait revives its server, reports recovery on stderr, and delivers input.\n"
            "The URL's dynamic port and access token are represented by <served-url>.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "exit": 0,
                    "stderr": printed.err.replace(info["url"], "<served-url>"),
                },
            ),
        )
    )
    # A wait claims the page it names, so what it revives is the claiming
    # session's server and dies with that session. Here the session is the
    # worker (conftest), which is what keeps a killed run from stranding this.
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "session"


def test_wait_does_not_revive_a_page_another_leaf_vendored(page_dir, capsys):
    """A server that died under a page another Leaf has since been updated past
    stays down: the wait's revival is a start like any other, served by the Leaf
    running the wait. The page reads as lost, and the refusal reaches the agent
    reading the wait with the re-vendor that brings it back."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    assert service_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir, "review the page")
    vendored_by_another_leaf(page_dir)

    # One pass first, so a revival that went through fails here rather than
    # leaving the wait below holding a live page open for input.
    watch = session_model.Watch(harness_model.session_harness(), pages=(page_dir,))
    try:
        assert watch.acquire()
        reading = next(watch.tick())
    finally:
        watch.release()
    assert reading.lost is True
    assert reading.restarted is None
    assert server_model.running_server(page_dir) is None
    refused = capsys.readouterr().err
    assert f"leaf page init {page_dir}" in refused

    assert session_model.cmd_wait(page_dir) == 2
    printed = capsys.readouterr().err
    assert f"leaf page init {page_dir}" in printed
    assert "server had died; restarted" not in printed


def test_wait_revival_cannot_take_a_page_back_after_claim_transfer(
    codex_claimed_page, under_codex, codex_env, monkeypatch
):
    """A stale wait cannot revive a server for a page it no longer owns.

    The FIFO holds the status read after the waiter selected the page but
    before it checks the dead server. Another session then claims the page. The
    old wait must leave without spawning a server under its stale ownership
    decision.
    """
    page = codex_claimed_page
    hosting_model.cmd_stop(page)
    session_model.cmd_waiting(page, "comment on the prototype")
    status_path = page / "status.json"
    hold_status_read(status_path)
    first = under_codex(
        shlex.join([*LEAF_COMMAND, "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    writer = fifo_writer(status_path, "the waiter never reached its held status read")

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page)
    os.write(
        writer,
        json.dumps(
            {
                "state": "waiting",
                "detail": "comment on the prototype",
                "ts": "t",
            }
        ).encode(),
    )
    os.close(writer)
    declare_idle(page)

    first_out, first_err = first.communicate(timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert "no longer owns it" in first_err
    assert "the leaf ended" not in first_err
    session = service_model.page_claim(page)
    assert session["id"] == "replacement"
    assert server_model.running_server(page) is None


def test_session_end_cannot_be_overtaken_by_wait_revival(claimed, spawn):
    """The session-end reaper must outrank a wait's stale live-page snapshot.

    The FIFO holds the wait after it selected the page but before it checks the
    dead server. SessionEnd then releases its claim. Releasing the stale status
    read must not let that wait put a session server back up.
    """
    page = claimed
    cleanup_model.write_json(
        page / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    session_model.cmd_waiting(page, "comment on the prototype")
    status_path = page / "status.json"
    hold_status_read(status_path)
    waiter = spawn(
        [*LEAF_COMMAND, "wait", str(page)],
        env=os.environ
        | {"CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_PID": str(os.getpid())},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    writer = fifo_writer(status_path, "the waiter never reached its held status read")

    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "s1"})
    assert files_model.read_json(page / "service.json")["enabled"] is True
    assert server_model.running_server(page) is None

    os.write(
        writer,
        json.dumps(
            {
                "state": "waiting",
                "detail": "comment on the prototype",
                "ts": "t",
            }
        ).encode(),
    )
    os.close(writer)

    out, err = waiter.communicate(timeout=STATED_TIMEOUT)
    assert waiter.returncode == 2, f"{out}{err}"
    assert "this session no longer owns it" in err
    assert service_model.page_claim(page)["released"] is not None
    assert server_model.running_server(page) is None
    # SessionEnd releases ownership only. The FIFO remains the same status path;
    # lifecycle code did not replace it with an authored idle state.
    assert status_path.is_fifo()


def test_a_revived_server_keeps_the_lifetime_it_was_serving_under(
    claimed, comment_once_served
):
    """A standing page comes back standing. The lifetime is the page's record
    rather than the reviving process's, so the restarts a page doesn't choose —
    a crash, the revival a `leaf wait` makes under it — leave it as the serve
    that started it declared, and `leaf server stop` is still the one thing that
    ends one. Read off the launch instead, a session that happened to notice the
    server was down would inherit a dashboard somebody left up for weeks, and
    take it down when it ended."""
    cleanup_model.write_json(
        claimed / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "standing",
        },
    )
    comment_once_served(claimed)
    assert session_model.cmd_wait(claimed) == 0
    # The reviving session did claim the page, so a lifetime read off this
    # launch would have said "session" — the claim is what the standing
    # record has to outrank.
    assert service_model.page_claim(claimed)["id"] == "s1"
    assert files_model.read_json(claimed / "service.json")["lifetime"] == "standing"


def test_wait_ends_when_the_leaf_does(page_dir, capsys, snapshot):
    """Idling is how a leaf ends, and it has to reach the watcher: a wait that
    held on past it left a long-running command open for a page nobody was going
    to press. The server is not
    the watcher's to end — a user is free to stay on a page the agent has
    finished with — so it is left exactly as it stands."""
    serving(page_dir, 1)
    declare_idle(page_dir)
    assert session_model.cmd_wait(page_dir) == 2
    assert server_model.running_server(page_dir)
    served = capsys.readouterr()

    # And where SessionEnd idled the page and stopped its server both, a watcher
    # still winding down must not put it straight back up. Dropping the lease is
    # what makes the server read as dead.
    leases_model.release_lease(HELD_LEASES.pop())
    assert session_model.cmd_wait(page_dir) == 2
    assert server_model.running_server(page_dir) is None
    stopped = capsys.readouterr()
    snapshot.check(
        yaml_document(
            "An idle page ends its wait whether the server is still running or stopped.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "still served": {
                        "exit": 2,
                        "stdout": served.out,
                        "stderr": served.err,
                    },
                    "server stopped": {
                        "exit": 2,
                        "stdout": stopped.out,
                        "stderr": stopped.err,
                    },
                },
            ),
        )
    )


def test_one_wait_watches_every_page_the_session_holds(
    page_dir, tmp_path, monkeypatch, capsys
):
    """A session's leaves share one watcher. The watch set is the session's own
    pages rather than the argument, so four leaves cost one command between
    them, and the line that wakes the session says which page spoke."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s9")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    leases_model.mark_hooks("s9")  # its harness runs Leaf's hooks
    second = tmp_path / "second"
    vendoring_model.cmd_init(second)
    capsys.readouterr()
    session_model.cmd_waiting(second, "")
    session_model.cmd_waiting(page_dir, "")
    serving(page_dir, 1)
    serving(second, 2)
    for d in (page_dir, second):
        assert service_model.claim_page(d)
    append_carried_log_record(
        second, {"kind": "comment", "author": "user", "text": "hi"}
    )

    assert session_model.cmd_wait() == 0
    woke = capsys.readouterr().out
    assert woke.startswith(f"{second} has new input")
    _, batch, shown = woken(woke)
    assert batch["page"] == str(second)
    assert [event["text"] for event in shown] == ["hi"]
    # The page that spoke records exact pickup; neither page's status is rewritten.
    assert files_model.read_json(second / "status.json")["state"] == "waiting"
    assert files_model.read_json(page_dir / "status.json")["state"] == "waiting"
    assert events_model.read_events(second)[-1]["kind"] == "pickup"
    assert all(e["kind"] != "pickup" for e in events_model.read_events(page_dir))

    # Idling one leaf leaves the watch to the others; idling the last ends it.
    declare_idle(second)
    declare_idle(page_dir)
    assert session_model.cmd_wait() == 2


def test_the_stop_hook_watch_wakes_the_session_only_for_input(
    claimed, monkeypatch, capsys, dead_pid
):
    """Claude Code keeps Leaf's second Stop hook running in the background and
    wakes the session only when it exits 2, so that hook is the session's watch
    between turns, and the model keeps no `leaf wait` alive. It wakes for input,
    holds input that was already pending as the turn ended until the Stop hook
    beside it has answered, and ends silently where it has nothing to do."""
    leases_model.mark_hooks("s1")  # its harness runs Leaf's hooks
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    stop = {"hook_event_name": "Stop", "session_id": "s1"}

    # Another watch holds the session's lease, or the hook names another session:
    # nothing to watch, and nothing wakes.
    lease = leases_model.take_lease(leases_model.waiter_lease_path(None, "s1"))
    assert hooks_model.cmd_watch(stop) is None
    leases_model.release_lease(lease)
    assert hooks_model.cmd_watch({**stop, "session_id": "s2"}) is None
    # Under plain `--print` Claude Code would wait on the hook, holding the turn.
    launched = harness_model.process_argv
    argv = ["claude", "-p", "hello"]
    monkeypatch.setattr(harness_model, "process_argv", lambda pid: argv)
    assert hooks_model.cmd_watch(stop) is None
    argv = ["claude", "-p", "--input-format", "stream-json"]
    assert harness_model.session_harness().watches_between_turns()
    monkeypatch.setattr(harness_model, "process_argv", launched)

    initialized = threading.Event()
    await_news = session_model.Watch.await_news

    def after_first_pass(watch, mark, *args, **kwargs):
        initialized.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_first_pass)

    def watching(outcome: list) -> threading.Thread:
        initialized.clear()
        watch = threading.Thread(
            target=lambda: outcome.append(hooks_model.cmd_watch(stop))
        )
        watch.start()
        # The lease is acquired before the initial log snapshot. A comment sent
        # after acquisition can still enter that snapshot as pre-existing input;
        # the first completed pass proves this watch can now read later arrivals.
        assert initialized.wait(STATED_TIMEOUT), (
            "the watch never completed its first pass"
        )
        assert leases_model.wait_is_live(claimed, "s1")
        return watch

    # Input pending as the turn ends is the other Stop hook's to hand to the turn
    # it continues; once that hook lets the turn end over it, the watch wakes.
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "before"}
    )
    outcome = []
    watch = watching(outcome)
    time.sleep(session_model.REVIVAL_CHECK_S / 5)
    assert outcome == []
    cleanup_model.close_session_turn("s1")
    watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive(), "the watch never woke when the turn closed"
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")
    assert not leases_model.wait_is_live(claimed, "s1")

    # Input arriving once the watch runs wakes the session at once, between turns
    # or within one, where it reaches the turn at its next tool result.
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    outcome = []
    watch = watching(outcome)
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "after"}
    )
    watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive(), "the watch never woke on the comment"
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")

    # A watch whose harness process has gone, as a retired background job's worker
    # leaves it, ends silently and lets the lease go. Input admitted while it held
    # the lease was not nudged, so it nudges that input itself.
    cleanup_model.close_session_turn("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "orphaned"}
    )
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page: nudged.append(page) or True,
    )
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    assert hooks_model.cmd_watch(stop) is None
    assert not leases_model.wait_is_live(claimed, "s1")
    assert nudged == [claimed.resolve()]
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))

    # An idle page leaves nothing to watch, and that ending wakes nobody.
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    declare_idle(claimed)
    assert hooks_model.cmd_watch(stop) is None


def test_a_watch_at_an_interrupted_ending_wakes_only_for_later_input(
    claimed, monkeypatch
):
    """A harness that says its turn was interrupted, as Pi's extension does when an
    Escape settles a run, starts the watch with that Interrupt payload. The user
    stopped the turn the pending input was handed to, so that input waits for
    their next prompt, and only input arriving after the watch starts wakes the
    session. A watch at a Stop ending wakes for the same pending input at once."""
    leases_model.mark_hooks("s1")
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    cleanup_model.prompt_turn("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "handed over"}
    )
    cleanup_model.close_session_turn("s1")

    waiting = threading.Event()
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        waiting.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)
    outcome = []
    watch = threading.Thread(
        target=lambda: outcome.append(
            hooks_model.cmd_watch({"hook_event_name": "Interrupt", "session_id": "s1"})
        )
    )
    watch.start()
    # A watch decides on its first pass; this one went on to wait for news.
    assert waiting.wait(STATED_TIMEOUT), "the watch never completed its first pass"
    assert outcome == []
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "after"}
    )
    watch.join(timeout=STATED_TIMEOUT)
    assert not watch.is_alive(), "the watch never woke on the comment"
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")

    waiting.clear()
    stop = {"hook_event_name": "Stop", "session_id": "s1"}
    assert hooks_model.cmd_watch(stop).startswith(f"{claimed} has new input")
    assert not waiting.is_set()


def test_a_page_served_mid_wait_joins_the_running_watch(
    page_dir, tmp_path, monkeypatch, capsys
):
    """The watch set is re-read every pass, so serving another leaf while the
    watcher holds needs no second command: the claim the serve makes is what
    puts the page in front of the running wait."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s10")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    leases_model.mark_hooks("s10")  # its harness runs Leaf's hooks
    serving(page_dir, 1)
    assert service_model.claim_page(page_dir)
    joined = tmp_path / "joined"
    vendoring_model.cmd_init(joined)
    capsys.readouterr()
    session_model.cmd_waiting(joined, "")
    serving(joined, 2)

    def join():
        service_model.claim_page(joined)
        append_carried_log_record(
            joined, {"kind": "comment", "author": "user", "text": "hi"}
        )

    threading.Timer(0.2, join).start()
    assert session_model.cmd_wait() == 0
    _, first, _ = delivered(capsys)
    assert first["page"] == str(joined)


def test_a_wait_holding_events_delivers_them_whatever_became_of_the_page(
    page_dir, capsys
):
    """The batch outranks the page's state: an idled leaf can still hold a
    comment the user got in before the end, and a wait that exited on the
    idle instead would strand it unread until a hook complained."""
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    declare_idle(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    _, first, _ = delivered(capsys)
    assert first["page"] == str(page_dir)


def test_wait_with_nothing_to_watch_says_so(monkeypatch, capsys, snapshot):
    """A no-argument wait in a session that holds no pages has nothing to hold
    open — exit rather than sleep forever on an empty set."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-empty")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert session_model.cmd_wait() == 2
    printed = capsys.readouterr()
    assert "nothing to watch" in printed.err
    snapshot.check(
        yaml_document(
            "An unnamed wait exits when the session owns no page.",
            {"exit": 2, "stdout": printed.out, "stderr": Prose(printed.err)},
        )
    )


def test_wait_holds_a_page_nobody_has_opened(page_dir, capsys):
    """Nothing the server can observe tells a page the user hasn't opened yet
    from one they can't reach, so the wait doesn't guess between them: over a page
    no request has ever touched it holds for the user exactly as it would for
    one reading, and reports nothing of its own."""
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    threading.Timer(
        0.2,
        lambda: append_carried_log_record(
            page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
        ),
    ).start()

    assert session_model.cmd_wait(page_dir) == 0
    output = capsys.readouterr()
    _, first, shown = woken(output.out)
    assert first["page"] == str(page_dir)
    assert [event["id"] for event in shown] == ["c1"]
    assert output.err == ""


def test_a_named_bare_shell_wait_keeps_its_directory_without_a_claim(
    page_dir, sessionless, capsys
):
    """A terminal has no session ownership to gain or lose."""
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = printed(capsys.readouterr().out)
    assert header["page"] == str(page_dir)
    assert service_model.page_claim(page_dir) is None


def test_a_bare_shell_receipt_rearms_every_page_in_its_delivery(
    page_dir, tmp_path, sessionless, spawn
):
    other = tmp_path / "other"
    shutil.copytree(page_dir, other)
    batches = []
    for index, page in enumerate((page_dir, other), 1):
        serving(page, index)
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "first"}
        )
        with service_model.PageTransaction(page) as transaction:
            batches.append(
                delivery_model.batch_data(page, transaction, transaction.events)
            )
    payload = delivery_model.freeze_delivery(batches, carrier="wait")
    watching = spawn(
        [*LEAF_COMMAND, "wait", "--ack", payload["id"]],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: (
            leases_model.lock_is_held(page_dir / "waiter.lock"),
            leases_model.lock_is_held(other / "waiter.lock"),
        ),
        all,
        failure="receipt did not rearm both standalone pages",
    )
    later = append_carried_log_record(
        other, {"kind": "comment", "author": "user", "text": "next"}
    )
    out, err = watching.communicate(timeout=STATED_TIMEOUT)
    assert watching.returncode == 0, out + err
    _, batch, [event] = printed(out)
    assert batch["page"] == str(other)
    assert event["id"] == later["id"]
    for page in (page_dir, other):
        assert service_model.page_claim(page) is None
        assert files_model.read_json(page / "cursor.json") == {"seq": 1}


def test_an_unnamed_bare_shell_wait_has_no_watch_set(page_dir, sessionless, capsys):
    """Without a harness identity or a named page, there is nothing to watch."""
    session_model.cmd_waiting(page_dir, "")
    serving(page_dir, 1)
    record_claim(page_dir, id="foreign-session")
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "foreign", "author": "user", "text": "private"},
    )

    assert session_model.cmd_wait() == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "nothing to watch" in printed.err


def test_a_harness_claim_supersedes_a_bare_shell_wait(page_dir, sessionless, spawn):
    """A page has one wait owner even when the first has no harness identity."""
    session_model.cmd_waiting(page_dir, "")
    serving(page_dir, 1)
    bare = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: leases_model.lock_is_held(page_dir / "waiter.lock"),
        bool,
        failure="the bare wait never took its lease",
    )

    harness_env = os.environ | {
        "CLAUDE_CODE_SESSION_ID": "harness-owner",
        "CLAUDE_PID": str(os.getpid()),
    }
    leases_model.mark_hooks("harness-owner")  # its harness runs Leaf's hooks
    harness = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        env=harness_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: service_model.page_claim(page_dir),
        lambda claim: bool(
            claim
            and claim["id"] == "harness-owner"
            and leases_model.lock_is_held(
                leases_model.waiter_lease_path(page_dir, claim["id"])
            )
        ),
        failure="the harness wait never claimed the page and took its lease",
    )

    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "once", "author": "user", "text": "hi"},
    )
    bare_out, bare_err = bare.communicate(timeout=STATED_TIMEOUT)
    harness_out, harness_err = harness.communicate(timeout=STATED_TIMEOUT)

    assert (bare.returncode, bare_out) == (2, ""), bare_err
    assert "no longer owns it" in bare_err
    assert harness.returncode == 0, harness_err
    _, _, shown = woken(harness_out, "harness-owner")
    assert [event["id"] for event in shown] == ["once"]


def test_codex_receipt_leaves_input_for_the_new_page_owner(page_dir):
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "accepted", "author": "user", "text": "hi"},
    )
    delivered = events_model.read_events(page_dir)[-1]
    session_model.cmd_waiting(page_dir, "successor is listening")
    successor = record_claim(page_dir, id="successor", harness="codex", agent="Codex")
    with service_model.PageTransaction(page_dir) as page:
        reading = session_model.PageTick(
            page_dir,
            page.status,
            [delivered],
            True,
            "watching",
            False,
            None,
            page,
        )
        assert codex_adapter_model.capture_batch("original", reading)
    epoch_path, epoch = current_codex_record("original")
    codex_model.offer_delivery(epoch_path, epoch, "queue")
    epoch.update(state="accepted", transport={"phase": "queued", "turn": None})
    codex_model.write_record(epoch_path, epoch)
    batch = epoch["batches"][0]

    codex_model.finish_codex_batch(epoch_path, 0, batch)
    codex_model.finish_codex_batch(epoch_path, 0, batch)

    assert files_model.read_json(page_dir / "cursor.json") is None
    assert service_model.page_claim(page_dir) == successor
    status = service_model.read_status(page_dir)
    assert (status["state"], status["detail"]) == (
        "waiting",
        "successor is listening",
    )
    pickups = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert pickups == []


def test_codex_recovery_ignores_delivery_records_from_the_previous_adapter():
    directory = codex_state_model.delivery_dir("codex-thread")
    directory.mkdir(parents=True)
    legacy = directory / "legacy-delivery.json"
    cleanup_model.write_json(
        legacy,
        {
            "format": "leaf-delivery-v1",
            "delivery_id": "legacy-delivery",
            "page": "/tmp/old-page",
            "batch_jsonl": '{"page":"/tmp/old-page"}\n',
        },
    )

    assert not codex_adapter_model._recover_receipt("codex-thread")
    assert codex_model.delivery_records("codex-thread") == []
    assert files_model.read_json(legacy)["delivery_id"] == "legacy-delivery"


@pytest.mark.parametrize("state", ["collecting", "offering"])
def test_codex_ignores_delivery_records_from_the_previous_id_vocabulary(state):
    directory = codex_state_model.delivery_dir("codex-thread")
    directory.mkdir(parents=True)
    legacy = directory / "3f2a6c1e-9b44-4f0a-8a1f-2c5d7e8b9012.json"
    cleanup_model.write_json(
        legacy,
        {
            "format": codex_model.RECORD_FORMAT,
            "state": state,
            "created_at": 0,
            "batches": [],
        },
    )

    assert codex_model.delivery_records("codex-thread") == []


def test_codex_recovers_page_receipts_in_sequence_order(codex_claimed_page):
    page = codex_claimed_page
    for event_id in ("first", "second"):
        append_carried_log_record(
            page,
            {"kind": "comment", "id": event_id, "author": "user", "text": event_id},
        )
    first, second = events_model.read_events(page)[-2:]
    directory = codex_state_model.delivery_dir("codex-thread")
    directory.mkdir(parents=True)

    def epoch(event, *, created_at):
        return {
            "format": codex_model.RECORD_FORMAT,
            "state": "accepted",
            "created_at": created_at,
            "transport": {"phase": "queued", "turn": None},
            "batches": [
                {
                    "page": str(page),
                    "session": "codex-thread",
                    "threads": [],
                    "events": [event],
                    "receipted": False,
                }
            ],
        }

    # Filename order is deliberately opposite to event order. The cursor is
    # monotonic, so taking receipt for the second batch first would hide the
    # first batch before its pickup record is written.
    cleanup_model.write_json(directory / "ffffffff.json", epoch(first, created_at=1))
    cleanup_model.write_json(directory / "aaaaaaaa.json", epoch(second, created_at=2))

    assert codex_adapter_model._recover_receipt("codex-thread")
    assert codex_adapter_model._recover_receipt("codex-thread")
    pickups = [
        event for event in events_model.read_events(page) if event["kind"] == "pickup"
    ]
    assert [pickup["events"] for pickup in pickups] == [["first"], ["second"]]


def test_a_reinitialized_page_does_not_starve_later_codex_receipts(tmp_path):
    replaced = tmp_path / "a-replaced-page"
    standing = tmp_path / "z-standing-page"
    for page, event_id in ((replaced, "old"), (standing, "standing")):
        vendoring_model.cmd_init(page)
        record_claim(page, id="codex-thread", harness="codex", agent="Codex")
        append_carried_log_record(
            page,
            {
                "kind": "comment",
                "id": event_id,
                "author": "user",
                "token": "mark",
            },
        )
        delivered = events_model.read_events(page)[-1]
        with service_model.PageTransaction(page) as transaction:
            reading = session_model.PageTick(
                page,
                transaction.status,
                [delivered],
                True,
                "watching",
                False,
                None,
                transaction,
            )
            assert codex_adapter_model.capture_batch("codex-thread", reading)
    epoch_path, epoch = current_codex_record("codex-thread")
    codex_model.offer_delivery(epoch_path, epoch, "queue")
    epoch = files_model.read_json(epoch_path)
    epoch.update(state="accepted", transport={"phase": "queued", "turn": None})
    codex_model.write_record(epoch_path, epoch)

    shutil.rmtree(replaced)
    vendoring_model.cmd_init(replaced)
    append_carried_log_record(
        replaced,
        {
            "kind": "comment",
            "id": "replacement",
            "author": "user",
            "text": "new page",
        },
    )

    assert codex_adapter_model._recover_receipt("codex-thread")
    first_pass = files_model.read_json(epoch_path)["batches"]
    assert [batch["receipted"] for batch in first_pass] == [True, False]
    assert codex_adapter_model._recover_receipt("codex-thread")

    history = epoch_path.parent / "history" / epoch_path.name
    assert all(
        batch["receipted"] for batch in files_model.read_json(history)["batches"]
    )
    assert files_model.read_json(standing / "cursor.json") == {"seq": 1}
    pickups = [
        event
        for event in events_model.read_events(standing)
        if event["kind"] == "pickup"
    ]
    assert [pickup["events"] for pickup in pickups] == [["standing"]]


def test_a_receipted_codex_batch_ignores_a_reinitialized_page_cursor(
    codex_claimed_page, tmp_path
):
    page = codex_claimed_page
    other = tmp_path / "other-page"
    vendoring_model.cmd_init(other)
    record_claim(other, id="codex-thread", harness="codex", agent="Codex")

    for target, event_id in ((page, "old"), (other, "other")):
        append_carried_log_record(
            target,
            {
                "kind": "comment",
                "id": event_id,
                "author": "user",
                "token": "mark",
            },
        )
        delivered = events_model.read_events(target)[-1]
        with service_model.PageTransaction(target) as transaction:
            reading = session_model.PageTick(
                target,
                transaction.status,
                [delivered],
                True,
                "watching",
                False,
                None,
                transaction,
            )
            assert codex_adapter_model.capture_batch("codex-thread", reading)
    epoch_path, epoch = current_codex_record("codex-thread")
    codex_model.offer_delivery(epoch_path, epoch, "queue")
    epoch = files_model.read_json(epoch_path)
    epoch.update(state="accepted", transport={"phase": "queued", "turn": None})
    codex_model.write_record(epoch_path, epoch)

    assert codex_adapter_model._recover_receipt("codex-thread")
    batches = files_model.read_json(epoch_path)["batches"]
    [received] = [batch for batch in batches if batch["receipted"]]
    [pending] = [batch for batch in batches if not batch["receipted"]]

    # Reinitializing a page path starts its cursor again. Its batch is recovery
    # history, while the other page's batch is still live transport work.
    cleanup_model.write_json(Path(received["page"]) / "cursor.json", {"seq": 0})
    assert codex_adapter_model._recover_receipt("codex-thread")
    history = epoch_path.parent / "history" / epoch_path.name
    assert files_model.read_json(history)["batches"] == [
        {**batch, "receipted": True} for batch in batches
    ]
    assert files_model.read_json(Path(pending["page"]) / "cursor.json") == {"seq": 1}
    assert codex_model.delivery_records("codex-thread") == []


def test_one_thread_delivery_starts_and_receipts_its_app_server_turn(
    codex_claimed_page, monkeypatch
):
    page = codex_claimed_page
    comment = append_carried_log_record(
        page,
        {"kind": "comment", "id": "user-message", "author": "user", "text": "hi"},
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

    started = []
    connection = _observer()

    def start_delivery(payload):
        started.append(payload)
        assert connection._observe_lifecycle("app-server-turn")
        fold = connection._fold("app-server-turn", payload["id"], follow=True)
        assert fold is not None
        return True

    monkeypatch.setattr(connection, "start_delivery", start_delivery)
    monkeypatch.setattr(
        codex_adapter_model,
        "queue_delivery",
        lambda *_: pytest.fail("the addressed delivery used the Codex queue fallback"),
    )

    assert codex_adapter_model._offer_queued_delivery(
        "codex",
        "codex-thread",
        connection,
    )
    [payload] = started
    assert payload["batches"][0]["events"][0]["id"] == comment["id"]
    assert "reply" not in payload

    # The follower's first step, which the adapter runs on its own thread: the
    # delivery is recorded against the turn that is now carrying it.

    # Accepting the delivery is the page receipt as well, so the record is complete
    # and archived by the time the turn is under way.
    assert codex_records("codex-thread") == []
    [history] = sorted(
        (codex_state_model.delivery_dir("codex-thread") / "history").glob("*.json")
    )
    recorded = files_model.read_json(history)
    assert recorded["transport"] == {"phase": "opened", "turn": "app-server-turn"}
    assert all(batch["receipted"] for batch in recorded["batches"])

    pickup = next(
        event for event in events_model.read_events(page) if event["kind"] == "pickup"
    )
    assert (pickup["phase"], pickup["turn"], pickup["events"]) == (
        "opened",
        "app-server-turn",
        [comment["id"]],
    )
    assert codex_model.delivery_records("codex-thread") == []


def test_a_connection_failure_in_the_delivery_loop_is_retried(
    codex_claimed_page, monkeypatch
):
    """The delivery loop survives every class its own connections can raise.

    A delivery opens a connection of its own inside this loop, and `websockets`
    raises `WebSocketException`, which descends from `Exception` alone. Naming the
    classes worth retrying would let a refused handshake end the adapter and strand
    every page it claims, which is the one thing a carrier exists not to do.
    """
    assert not issubclass(WebSocketException, (OSError, RuntimeError, ValueError))
    for name in CLAUDE_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    attempts = []

    def recover_receipt(session_id):
        attempts.append(session_id)
        if len(attempts) == 1:
            raise WebSocketException("the handshake was refused")
        return False

    monkeypatch.setattr(codex_adapter_model, "_recover_receipt", recover_receipt)
    monkeypatch.setattr(codex_adapter_model, "owned_pages", lambda _session: [])
    monkeypatch.setattr(codex_adapter_model, "check_queue_command", lambda _path: None)
    monkeypatch.setattr(codex_adapter_model, "retry_delay", lambda _failures: 0)

    assert codex_adapter_model.run_adapter("codex") == 0
    assert attempts == ["codex-thread", "codex-thread"]


def test_a_codex_adapter_retiring_with_no_page_leaves_only_records_a_page_needs(
    monkeypatch, tmp_path
):
    """Retiring removes readable records whose pages are gone and its own log.
    A standing page's records survive, and stable coordination files stay unheld
    for the next holder."""
    # The suite's hook marks (`isolated_session`) are not records this test makes.
    for session in HOOKED_SESSIONS:
        leases_model.hooks_path(session).unlink()
    for name in CLAUDE_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    monkeypatch.setattr(codex_adapter_model, "owned_pages", lambda _session: [])
    monkeypatch.setattr(codex_adapter_model, "check_queue_command", lambda _path: None)
    standing = tmp_path / "standing"
    standing.mkdir()
    for task, page in (("ended-task", tmp_path / "gone"), ("codex-thread", standing)):
        path = codex_model.record_path(task, "eeeeeeee")
        path.parent.mkdir(parents=True)
        codex_model.write_record(
            path,
            {
                "format": codex_model.RECORD_FORMAT,
                "state": "accepted",
                "created_at": 0,
                "transport": {"phase": "queued", "turn": None},
                "batches": [
                    {
                        "page": str(page),
                        "session": task,
                        "events": [{"id": "delivered", "seq": 1}],
                        "receipted": True,
                    }
                ],
            },
        )
    codex_adapter_model.adapter_log_path("codex-thread").write_text("started\n")

    assert codex_adapter_model.run_adapter("codex") == 0
    kept = codex_state_model.delivery_dir("codex-thread")
    assert not codex_state_model.delivery_dir("ended-task").exists()
    assert not codex_adapter_model.adapter_log_path("codex-thread").exists()
    coordination = [
        path for path in leases_model.sessions_home().iterdir() if path != kept
    ]
    assert leases_model.adapter_lease_path("codex-thread") in coordination
    assert all(
        path.is_file() and not leases_model.lock_is_held(path) for path in coordination
    )
    assert [path.name for path in kept.rglob("*.json")] == ["eeeeeeee.json"]


def test_an_uncertain_app_server_start_recovers_by_delivery_identity(
    codex_claimed_page,
    monkeypatch,
):
    page = codex_claimed_page
    comment = append_carried_log_record(
        page,
        {"kind": "comment", "id": "user-message", "author": "user", "text": "hi"},
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

    attempted = []
    observer = _observer()

    def start_delivery(payload):
        session_id = "codex-thread"
        attempted.append(payload)
        # The seat an uncertain start reserved stays reserved, because a turn
        # carrying this delivery may be running.
        thread_model.reserve_delivery_reply(
            session_id, payload["id"], codex_model.stream_reply_target(payload)
        )
        raise codex_model.AppServerDeliveryUncertain("lost acknowledgement")

    monkeypatch.setattr(observer, "start_delivery", start_delivery)
    with pytest.raises(
        codex_model.AppServerDeliveryUncertain, match="lost acknowledgement"
    ):
        codex_adapter_model._offer_queued_delivery(
            "codex",
            "codex-thread",
            observer,
        )

    [payload] = attempted
    [(path, queue)] = codex_records("codex-thread")
    assert queue["state"] == "offering"
    with pytest.raises(SystemExit, match="answered by this turn's messages"):
        thread_model.cmd_reply(
            page,
            comment["id"],
            "Competing reply",
            "",
            for_event=comment["id"],
            identity={"agent": "Codex", "session": "codex-thread"},
        )
    monkeypatch.setattr(
        codex_adapter_model,
        "queue_delivery",
        lambda *_: pytest.fail("an observed uncertain delivery entered a local queue"),
    )
    with pytest.raises(
        codex_model.AppServerDeliveryUncertain,
        match="awaiting reconciliation",
    ):
        codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)

    claim = service_model.page_claim(page)
    observer = _observer()
    observer._reconcile(
        {
            "id": "recovered-turn",
            "status": "failed",
            "items": [
                {
                    "type": "functionCallOutput",
                    "name": "leaf_delivery",
                    "output": json.dumps(payload),
                }
            ],
        }
    )

    assert observer.turns == {}
    history = path.parent / "history" / path.name
    recovered = files_model.read_json(history)
    assert recovered["state"] == "accepted"
    assert all(batch["receipted"] for batch in recovered["batches"])
    # The recovered turn had ended, so recording it opens and closes nothing.
    assert service_model.page_claim(page) == claim
    accepted = thread_model.cmd_reply(
        page,
        comment["id"],
        "Recovered outside the failed provider turn",
        "",
        for_event=comment["id"],
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    assert accepted["text"] == "Recovered outside the failed provider turn"


def test_app_server_deliveries_preserve_order_with_one_plain_reply_each(
    codex_claimed_page, monkeypatch
):
    page = codex_claimed_page
    for event_id in ("first", "second"):
        append_carried_log_record(
            page,
            {
                "kind": "comment",
                "id": event_id,
                "author": "user",
                "text": event_id,
            },
        )
    with service_model.PageTransaction(page) as transaction:
        reading = session_model.PageTick(
            page,
            transaction.status,
            events_model.read_events(page)[-2:],
            True,
            "watching",
            False,
            None,
            transaction,
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)

    started = []
    connection = _observer()

    def start_delivery(payload):
        started.append(payload)
        assert connection._observe_lifecycle("app-server-turn")
        fold = connection._fold("app-server-turn", payload["id"], follow=True)
        assert fold is not None
        return True

    monkeypatch.setattr(connection, "start_delivery", start_delivery)
    monkeypatch.setattr(
        codex_adapter_model,
        "queue_delivery",
        lambda *_: pytest.fail("an idle App Server delivery was queued"),
    )

    assert codex_adapter_model._offer_queued_delivery(
        "codex",
        "codex-thread",
        connection,
    )
    [payload] = started
    assert [event["id"] for event in payload["batches"][0]["events"]] == ["first"]
    assert [thread["id"] for thread in payload["batches"][0]["threads"]] == ["first"]
    # Frozen for App Server, the comment's reply is the turn's to write.
    assert payload["batches"][0]["events"][0]["answer"]["kind"] == "turn"

    # Accepting the first delivery receipts it, so the second comment is collected
    # into a record of its own rather than joining the one already in a turn.
    with service_model.PageTransaction(page) as transaction:
        reading = session_model.PageTick(
            page,
            transaction.status,
            service_model.unacknowledged(transaction.events, transaction.cursor),
            True,
            "watching",
            False,
            None,
            transaction,
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)
    second_path, second = current_codex_record("codex-thread")
    second_payload = codex_model.offer_delivery(
        second_path, second, "app-server"
    ).payload
    assert [
        event["id"] for batch in second_payload["batches"] for event in batch["events"]
    ] == ["second"]


def test_codex_tool_hook_delivers_into_the_running_turn_once(
    page_dir, codex_loop, capsys, monkeypatch
):
    """Hook completion offers input; its actual read proves same-turn pickup.

    The idle queue never takes an already-read pointer, and parallel tool hooks
    cannot recapture its unreceipted events or emit it twice.
    """
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    hooks_model.cmd_hook(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    assert not capsys.readouterr().out
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Keep the existing layout"},
    )
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    hooks_model.cmd_hook(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert context["hookEventName"] == "PostToolUse"
    [(path, record)] = codex_records("codex-thread")
    assert context["additionalContext"] == codex_model.delivery_pointer_prompt(
        path.stem
    )
    assert record["transport"] == {"phase": "hook", "turn": "user-turn"}
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(page_dir)
    )
    # Reading outside the owning task doesn't claim the user's input.
    monkeypatch.delenv("CODEX_THREAD_ID")
    delivery_model.cmd_delivery_read(path.stem)
    capsys.readouterr()
    assert codex_records("codex-thread")[0][1]["state"] == "offering"
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    hooks_model.cmd_hook(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    assert not capsys.readouterr().out
    assert len(codex_records("codex-thread")) == 1
    delivery_model.cmd_delivery_read(path.stem)
    assert (
        json.loads(capsys.readouterr().out)["batches"][0]["events"][0]["id"]
        == comment["id"]
    )
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["phase"], pickup["session"], pickup["turn"]) == (
        "opened",
        "codex-thread",
        "user-turn",
    )
    cleanup_model.close_session_turn("codex-thread", "user-turn")
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    assert not queued


def test_a_page_claimed_mid_turn_keeps_its_first_comment_for_the_tool_hook(
    page_dir, codex_loop, capsys, monkeypatch
):
    """Capture before the first page-bound tool hook still delivers in this turn."""
    hooks_model.cmd_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    hooks_model.cmd_hook(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    codex_loop(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Change this before finishing"},
    )
    with service_model.PageTransaction(page_dir) as page:
        reading = session_model.PageTick(
            page_dir, page.status, [comment], True, "watching", False, None, page
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    assert not queued
    hooks_model.cmd_hook(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    [(path, record)] = codex_records("codex-thread")
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ] == codex_model.delivery_pointer_prompt(path.stem)
    assert record["transport"] == {"phase": "hook", "turn": "user-turn"}
    delivery_model.cmd_delivery_read(path.stem)
    capsys.readouterr()
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["phase"], pickup["turn"], pickup["events"]) == (
        "opened",
        "user-turn",
        [comment["id"]],
    )


@pytest.mark.parametrize("ending", ["Stop", "Interrupt"])
def test_a_codex_ending_closes_a_page_claimed_before_its_first_tool_hook(
    page_dir, codex_loop, capsys, ending, monkeypatch
):
    """No step-hook completion is needed to end a page acquired mid-turn."""
    hooks_model.cmd_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    monkeypatch.setattr(
        harness_model.CodexHarness, "lifetime", lambda self: {"pid": os.getpid()}
    )
    with service_model.PageTransaction(page_dir) as page:
        page.take_claim(harness_model.session_harness())
    assert service_model.page_claim(page_dir)["turn"] == "user-turn"
    # A preview owes no watcher, so Stop may end without a carrier lease.
    (page_dir / "preview.json").write_text("{}")
    hooks_model.cmd_hook(
        {
            "hook_event_name": ending,
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    assert not capsys.readouterr().out
    assert service_model.page_claim(page_dir)["turn_closed"]
    assert service_model.page_claim(page_dir)["turn"] == "user-turn"
    assert not codex_state_model.hook_turn("codex-thread")["running"]
    hooks_model.cmd_hook(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        }
    )
    assert not capsys.readouterr().out
    assert service_model.page_claim(page_dir)["turn_closed"]
    assert service_model.page_claim(page_dir)["turn"] == "user-turn"


def test_a_late_codex_tool_hook_cannot_replace_a_newer_turn(page_dir, codex_loop):
    """An old async callback neither captures input nor reopens its ended turn."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old-turn")
    cleanup_model.open_session_turn("codex-thread", "old-turn")
    cleanup_model.close_session_turn("codex-thread", "old-turn")
    cleanup_model.close_session_turn("codex-thread", "old-turn")
    cleanup_model.prompt_turn("codex-thread", "new-turn")
    cleanup_model.open_session_turn("codex-thread", "new-turn")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "For the new turn"}
    )
    assert codex_model.offer_hook_delivery("codex-thread", "old-turn") is None
    cleanup_model.close_session_turn("codex-thread", "old-turn")
    assert service_model.page_claim(page_dir)["turn"] == "new-turn"
    assert codex_state_model.hook_turn("codex-thread")["running"]
    assert not codex_records("codex-thread")


def test_a_codex_tool_step_wins_a_queue_offer_based_on_stale_activity(
    page_dir, codex_loop, monkeypatch
):
    """Route reservation rechecks a tool renewal even within the same turn.

    A queue offer that saw stale activity pauses before taking its delivery lock;
    a fresh hook step renews the claim and offers the pointer in that interval.
    """
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    leases_model.mark_step_hook("codex-thread")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Before you finish"}
    )
    prompts = []

    def stale_activity(session_id):
        prompts.append(codex_model.offer_hook_delivery(session_id, "user-turn"))

    monkeypatch.setattr(codex_adapter_model, "step_delivery_turn", stale_activity)
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    assert prompts[0] is not None
    assert not queued
    [(path, record)] = codex_records("codex-thread")
    assert record["transport"]["phase"] == "hook"
    delivery_model.cmd_delivery_read(path.stem)
    assert not codex_records("codex-thread")
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["phase"], pickup["turn"]) == ("opened", "user-turn")


@pytest.mark.parametrize("loss", ["transfer", "remove"])
def test_a_codex_hook_read_survives_page_loss_after_offer(
    page_dir, codex_loop, capsys, tmp_path, loss
):
    """A lost batch page cannot prevent receipt of the envelope's healthy sibling."""
    sibling = tmp_path / "sibling"
    shutil.copytree(page_dir, sibling)
    codex_loop(page_dir)
    codex_loop(sibling)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    leases_model.mark_step_hook("codex-thread")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Retain this input"}
    )
    settled = append_carried_log_record(
        sibling, {"kind": "comment", "author": "user", "text": "Already settled"}
    )
    resolved = append_carried_log_record(
        sibling, {"kind": "resolve", "author": "user", "parent": settled["id"]}
    )
    cleanup_model.write_json(sibling / "cursor.json", {"seq": settled["seq"]})
    codex_model.offer_hook_delivery("codex-thread", "user-turn")
    [(path, record)] = codex_records("codex-thread")
    assert len(record["batches"]) == 2
    if loss == "transfer":
        record_claim(page_dir, id="successor", harness="codex", agent="Codex")
    else:
        shutil.rmtree(page_dir)
    delivery_model.cmd_delivery_read(path.stem)
    envelope = json.loads(capsys.readouterr().out)
    assert {
        event["id"] for batch in envelope["batches"] for event in batch["events"]
    } == {comment["id"], resolved["id"]}
    if loss == "transfer":
        assert service_model.page_claim(page_dir)["id"] == "successor"
        assert service_model.read_cursor(page_dir) == 0
        assert not any(
            event["kind"] == "pickup" for event in events_model.read_events(page_dir)
        )
    assert service_model.read_cursor(sibling) == resolved["seq"]
    assert not codex_records("codex-thread")
    [pickup] = [
        event
        for event in events_model.read_events(sibling)
        if event["kind"] == "pickup"
    ]
    assert (pickup["phase"], pickup["turn"]) == ("opened", "user-turn")


@pytest.mark.parametrize("ending", ["Stop", "Interrupt"])
def test_an_unread_codex_hook_pointer_falls_back_to_the_idle_queue(
    page_dir, codex_loop, capsys, monkeypatch, ending
):
    """A hook finishing too late never loses input or falsely records pickup."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    leases_model.mark_step_hook("codex-thread")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "One more question"}
    )
    prompt = codex_model.offer_hook_delivery("codex-thread", "user-turn")
    [(path, _)] = codex_records("codex-thread")
    lease = leases_model.take_lease(leases_model.adapter_lease_path("codex-thread"))
    assert lease
    waiter = leases_model.take_lease(
        leases_model.waiter_lease_path(page_dir, "codex-thread")
    )
    assert waiter
    try:
        hooks_model.cmd_hook(
            {
                "hook_event_name": ending,
                "session_id": "codex-thread",
                "turn_id": "user-turn",
            }
        )
        assert not capsys.readouterr().out
        assert codex_state_model.step_delivery_turn("codex-thread") is None
        # A late tool hook cannot reopen the turn or duplicate the pointer.
        hooks_model.cmd_hook(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "codex-thread",
                "turn_id": "user-turn",
            }
        )
        assert not capsys.readouterr().out
        queued = []
        monkeypatch.setattr(
            codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
        )
        assert codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
        assert [args[2] for args in queued] == [prompt]
        assert not codex_adapter_model._recover_receipt("codex-thread")
        pickups = [
            event
            for event in events_model.read_events(page_dir)
            if event["kind"] == "pickup"
        ]
        assert [(event["phase"], event["turn"]) for event in pickups] == [
            ("queued", None)
        ]
        assert not codex_adapter_model._offer_queued_delivery(
            "codex", "codex-thread", None
        )
        assert not path.exists()
    finally:
        leases_model.release_lease(lease)
        leases_model.release_lease(waiter)


def test_codex_serializes_later_input_behind_the_offered_delivery(
    codex_claimed_page, monkeypatch
):
    page = codex_claimed_page
    append_carried_log_record(
        page, {"kind": "comment", "id": "first", "author": "user", "text": "one"}
    )
    first = events_model.read_events(page)[-1]
    with service_model.PageTransaction(page) as transaction:
        reading = session_model.PageTick(
            page,
            transaction.status,
            [first],
            True,
            "watching",
            False,
            None,
            transaction,
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)
    first_path, _ = current_codex_record("codex-thread")

    queue_started = threading.Event()
    release_queue = threading.Event()

    def queue_delivery(_codex, _session, _prompt):
        queue_started.set()
        assert release_queue.wait(timeout=STATED_TIMEOUT)

    monkeypatch.setattr(codex_adapter_model, "queue_delivery", queue_delivery)
    offering = threading.Thread(
        target=lambda: codex_adapter_model._offer_queued_delivery(
            "codex", "codex-thread", None
        )
    )
    offering.start()
    assert queue_started.wait(timeout=STATED_TIMEOUT), (
        "the offer never reached the Codex queue"
    )
    assert files_model.read_json(first_path)["state"] == "offering"

    # A parallel step hook leaves the in-flight queue offer to its owner and
    # cannot capture its still-unacknowledged events into a second record.
    leases_model.mark_step_hook("codex-thread")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    assert codex_model.offer_hook_delivery("codex-thread", "user-turn") is None
    assert len(codex_records("codex-thread")) == 1

    append_carried_log_record(
        page, {"kind": "comment", "id": "second", "author": "user", "text": "two"}
    )
    release_queue.set()
    offering.join(timeout=STATED_TIMEOUT)
    assert not offering.is_alive()
    first_delivery = files_model.read_json(
        first_path.parent / "history" / first_path.name
    )
    assert first_delivery["state"] == "accepted"
    payload = files_model.read_json(delivery_model.delivery_path(first_path.stem))
    assert [
        event["id"] for batch in payload["batches"] for event in batch["events"]
    ] == ["first"]

    assert not codex_adapter_model._recover_receipt("codex-thread")
    with service_model.PageTransaction(page) as transaction:
        reading = session_model.PageTick(
            page,
            transaction.status,
            service_model.unacknowledged(transaction.events, transaction.cursor),
            True,
            "watching",
            False,
            None,
            transaction,
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)
    second_path, second_delivery = current_codex_record("codex-thread")
    assert second_path != first_path
    assert second_delivery["state"] == "collecting"
    assert [
        event["id"]
        for batch in files_model.read_json(second_path)["batches"]
        for event in batch["events"]
    ] == ["second"]


@pytest.mark.parametrize("carrier", ["hook", "app-server", "queue"])
def test_codex_acceptance_survives_interruption_before_page_receipt(
    page_dir, codex_loop, monkeypatch, carrier
):
    """Every transport commits acceptance before page IO, and recovery receipts it once."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Do not lose this"}
    )
    if carrier == "hook":
        leases_model.mark_step_hook("codex-thread")
    codex_model.offer_hook_delivery("codex-thread", "user-turn")
    [(path, _)] = codex_records("codex-thread")
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )

    def failed_pickup(*args, **kwargs):
        raise OSError("receipt storage unavailable")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(codex_model, "record_pickup", failed_pickup)
        with pytest.raises(OSError, match="receipt storage unavailable"):
            if carrier == "hook":
                delivery_model.cmd_delivery_read(path.stem)
            elif carrier == "app-server":
                observer = _observer()
                assert observer._observe_lifecycle("user-turn")
                observer._fold("user-turn", path.stem, follow=True)
            else:
                codex_adapter_model._offer_queued_delivery(
                    "codex", "codex-thread", None
                )
    accepted = files_model.read_json(path)
    assert accepted["state"] == "accepted"
    assert not accepted["batches"][0]["receipted"]
    assert service_model.read_cursor(page_dir) == 0
    assert bool(queued) == (carrier == "queue")
    assert codex_adapter_model._recover_receipt("codex-thread")
    assert not codex_adapter_model._recover_receipt("codex-thread")
    assert not codex_records("codex-thread")
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert pickup["events"] == [comment["id"]]
    assert (pickup["phase"], pickup["turn"]) == (
        ("queued", None) if carrier == "queue" else ("opened", "user-turn")
    )


def test_embedded_codex_acceptance_retries_its_unfinished_receipt(
    page_dir, monkeypatch
):
    """The hosted provider opening itself recovers acceptance without an adapter."""
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Recover this reply"}
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    cleanup_model.open_session_turn("hosted-thread", "provider-turn")

    def failed_pickup(*args, **kwargs):
        raise OSError("receipt storage unavailable")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(codex_model, "record_pickup", failed_pickup)
        with pytest.raises(OSError, match="receipt storage unavailable"):
            codex_model.open_app_server_delivery(
                page_dir,
                "hosted-thread",
                prepared.payload["id"],
                (comment["id"],),
                "provider-turn",
            )
    [(path, record)] = codex_records("hosted-thread")
    assert record["state"] == "accepted"
    assert not record["batches"][0]["receipted"]
    assert service_model.read_cursor(page_dir) == 0
    cleanup_model.close_session_turn("hosted-thread", "provider-turn")
    for _ in range(2):
        codex_model.open_app_server_delivery(
            page_dir,
            "hosted-thread",
            prepared.payload["id"],
            (comment["id"],),
            "provider-turn",
        )
    assert service_model.page_claim(page_dir)["turn_closed"]
    assert service_model.read_cursor(page_dir) == comment["seq"]
    assert not codex_records("hosted-thread")
    history = files_model.read_json(path.parent / "history" / path.name)
    assert history["transport"] == {"phase": "opened", "turn": "provider-turn"}
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["phase"], pickup["turn"], pickup["events"]) == (
        "opened",
        "provider-turn",
        [comment["id"]],
    )


def test_codex_restart_finishes_an_accepted_batch_without_queueing_again(
    codex_claimed_page, under_codex, codex_env, tmp_path
):
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    append_carried_log_record(
        page,
        {"kind": "comment", "id": "accepted", "author": "user", "text": "hi"},
    )
    delivered = events_model.read_events(page)[-1]
    session_model.cmd_waiting(page, "comment on the prototype")
    with service_model.PageTransaction(page) as transaction:
        reading = session_model.PageTick(
            page,
            transaction.status,
            [delivered],
            True,
            "watching",
            False,
            None,
            transaction,
        )
        assert codex_adapter_model.capture_batch("codex-thread", reading)
    record_path, queue = current_codex_record("codex-thread")
    codex_model.offer_delivery(record_path, queue, "queue")
    queue = files_model.read_json(record_path)
    queue.update(state="accepted", transport={"phase": "queued", "turn": None})
    codex_model.write_record(record_path, queue)
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(page),
                "--codex-path",
                str(program),
            ]
        ),
        codex_env
        | {
            "CODEX_THREAD_ID": "codex-thread",
            "FAKE_CODEX_LOG": str(log),
        },
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    release_codex_command(page, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    assert started.returncode == 0, f"{out}{err}"

    try:
        wait_for(
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": delivered["seq"]},
            failure="the accepted delivery cursor was not recovered",
        )

        assert [json.loads(line) for line in log.read_text().splitlines()] == [
            ["queue", "--help"]
        ]
    finally:
        declare_idle(page)
        with service_model.PageTransaction(page) as transaction:
            transaction.release_claim()
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after releasing its page",
    )


def test_a_later_codex_start_names_the_running_transport(
    codex_claimed_page, under_codex, codex_env, tmp_path
):
    """A later start joins the running adapter and names its transport, which is how
    the harness contracts tell the queue from App Server; one asking for an App Server
    this adapter is not on is refused rather than ignored."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page, "comment on the prototype")
    environment = codex_env | {
        "CODEX_THREAD_ID": "codex-thread",
        "FAKE_CODEX_LOG": str(log),
        "FAKE_CODEX_EXPECT_CWD": str(machine_model.state_home()),
    }

    # All three tool calls belong to one standing harness process. Three separate
    # under_codex calls would introduce three genuine task lifetimes, rather than
    # asking whether another command in this task joins its existing carrier.
    command = [
        *LEAF_COMMAND,
        "codex",
        "start",
        str(page),
        "--codex-path",
        os.path.relpath(program),
    ]
    results = tmp_path / "start-results.json"
    calls = [command, [*command, "--app-server", "unix:///tmp/elsewhere.sock"], command]
    runner = PLUGIN_ROOT / "tests" / "fixtures" / "programs" / "codex_starts.py"
    try:
        finished = tmp_path / "codex-start-finished"
        started = under_codex(
            shlex.join([sys.executable, str(runner), json.dumps(calls), str(results)]),
            environment,
            app_server=True,
            finished=finished,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        [(status, first, err), (refused, _, refusal), (joined, again, _)] = wait_for(
            lambda: files_model.read_json(results),
            lambda reading: reading is not None,
            failure="the standing Codex harness did not finish its three start commands",
        )
        assert status == 0, err
        assert json.loads(first) == {
            "task": "codex-thread",
            "app_server": None,
            "started": True,
        }
        assert refused != 0
        assert "not through App Server unix:///tmp/elsewhere.sock" in refusal
        assert joined == 0
        assert json.loads(again) == {
            "task": "codex-thread",
            "app_server": None,
            "started": False,
        }
        release_held(started)
        out, err = started.communicate(timeout=STATED_TIMEOUT)
        assert started.returncode == 0, f"{out}{err}"
    finally:
        declare_idle(page)
        with service_model.PageTransaction(page) as transaction:
            transaction.release_claim()
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after releasing its page",
    )


@pytest.mark.parametrize(
    "delivery_fault",
    [None, "retry"],
    ids=["steady", "uncertain-queue-retry"],
)
def test_codex_delivery_outlives_the_starting_command_and_acknowledges(
    codex_claimed_page, under_codex, codex_env, tmp_path, delivery_fault, capsys
):
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page, "comment on the prototype")
    environment = codex_env | {
        "CODEX_THREAD_ID": "codex-thread",
        "FAKE_CODEX_LOG": str(log),
        "FAKE_CODEX_EXPECT_CWD": str(machine_model.state_home()),
    }
    if delivery_fault == "retry":
        environment["FAKE_CODEX_QUEUE_FAILURE_ONCE"] = str(
            tmp_path / "uncertain-queue-response"
        )
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(page),
                "--codex-path",
                os.path.relpath(program),
            ]
        ),
        environment,
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # The fake Codex wrapper models one shell command, while a real task's Codex
    # ancestor remains alive. Keep that already-proven lifetime standing so this
    # test can isolate the detached carrier after its starting shell is gone.
    # Transfer the claim while that ancestor is still alive.
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        bool,
        failure="the detached Codex carrier did not start",
    )
    announcement = codex_start_announcement(started)
    claim = service_model.page_claim(page)
    before_release = cleanup_model.session_record("codex-thread")
    release_codex_command(page, started, finished)
    after_release = cleanup_model.session_record("codex-thread")
    assert service_model.page_claim(page)["generation"] == claim["generation"]
    assert after_release["generation"] == before_release["generation"]
    assert after_release["turn"] == before_release["turn"]
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    out = announcement + out
    assert started.returncode == 0, f"{out}{err}"
    assert json.loads(out)["task"] == "codex-thread"
    assert json.loads(out)["started"] is True
    try:
        wait_for(
            lambda: (
                codex_adapter_model.adapter_is_live("codex-thread"),
                page_state(page)["listening"],
            ),
            all,
            failure="the detached Codex carrier did not become live and listening",
        )

        assert service_model.page_claim(page)["turn_closed"] is None
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "hello adapter"}
        )
        comments = [events_model.read_events(page)[-1]]
        wait_for(
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": 1},
            failure=lambda: (
                "the adapter did not acknowledge its batch: "
                f"deliveries={codex_records('codex-thread')!r}; "
                f"log={adapter_log('codex-thread')!r}"
            ),
        )

        hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
        assert capsys.readouterr().out == ""

        hooks_model.cmd_hook(
            {"hook_event_name": "UserPromptSubmit", "session_id": "codex-thread"}
        )
        assert capsys.readouterr().out == ""
        assert [
            item["stage"] for item in page_state(page)["activity"]["obligations"]
        ] == ["picked_up"]
        hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
        reason = json.loads(capsys.readouterr().out)["reason"]
        assert "1 acknowledged user move with no answer" in reason

        for text in ("second click", "third click"):
            append_carried_log_record(
                page, {"kind": "comment", "author": "user", "text": text}
            )
            comments.append(events_model.read_events(page)[-1])
        wait_for(
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": comments[-1]["seq"]},
            failure="the cursor did not reach the later delivery",
        )

        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert calls[0] == ["queue", "--help"]
        queued = [call for call in calls if "--thread" in call]
        assert len(queued) == (4 if delivery_fault == "retry" else 3)
        prompts = [call[call.index("--message") + 1] for call in queued]
        assert len(set(prompts)) == 3
        unique_prompts = list(dict.fromkeys(prompts))
        assert len(unique_prompts) == 3
        payloads = []
        for prompt in unique_prompts:
            delivery = ElementTree.fromstring(prompt.splitlines()[1])
            assert delivery.tag == "leaf-delivery"
            assert delivery.attrib["operation"] == "delivery read"
            assert set(delivery.attrib) == {"operation", "id"}
            payload_path = delivery_model.delivery_path(delivery.attrib["id"])
            assert payload_path.exists()
            payload = files_model.read_json(payload_path)
            assert payload["format"] == delivery_model.DELIVERY_FORMAT
            assert all(
                set(batch) == {"page", "through_seq", "threads", "handling", "events"}
                for batch in payload["batches"]
            )
            queue_history = (
                codex_state_model.delivery_dir("codex-thread")
                / "history"
                / payload_path.name
            )
            # The page cursor is durable before the adapter records that receipt and
            # archives its queue. Wait for that second boundary instead of treating the
            # cursor's visibility as proof that the history move is already complete.
            queue = wait_for(
                lambda queue_history=queue_history: files_model.read_json(
                    queue_history
                ),
                lambda reading: reading is not None,
                failure=f"the delivery did not reach history at {queue_history}",
            )
            assert queue["state"] == "accepted"
            assert all(batch["receipted"] for batch in queue["batches"])
            payloads.append(payload)
            assert len(prompt.encode()) < 1024
        assert [
            event["id"]
            for payload in payloads
            for batch in payload["batches"]
            for event in batch["events"]
        ] == [comment["id"] for comment in comments]
        assert files_model.read_json(page / "cursor.json") == {
            "seq": comments[-1]["seq"]
        }
        assert codex_adapter_model.adapter_is_live("codex-thread")

        for comment in comments:
            thread_model.cmd_reply(
                page,
                comment["id"],
                "received",
                None,
                for_event=comment["id"],
            )
        declare_idle(page)
    finally:
        with service_model.PageTransaction(page) as transaction:
            transaction.release_claim()

    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after finishing its deliveries",
    )


def test_codex_adapter_follows_ownership_across_idle_and_server_stop(
    codex_claimed_page, codex_env, tmp_path, spawn
):
    """Status and server changes do not end a route still owned by the task."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page, "comment on the prototype")
    assert hosting_model.cmd_stop(page) is True
    checks = tmp_path / "adapter-checks.json"
    adapter = spawn_probe(
        spawn,
        page,
        """\
from leaf import codex_adapter as adapter
from leaf.files import read_json
from leaf.state import write_json
native_read = adapter.read_watch_pass
passes = 0
def completed_read(*args, **kwargs):
    global passes
    page = Path(os.environ["PAGE"])
    state = read_json(page / "status.json")["state"]
    enabled = read_json(page / "service.json")["enabled"]
    result = native_read(*args, **kwargs)
    passes += 1
    write_json(Path(os.environ["CHECKS"]), {
        "passes": passes, "state": state, "enabled": enabled,
    })
    return result
adapter.read_watch_pass = completed_read
raise SystemExit(adapter.run_adapter(os.environ["CODEX_PATH"]))
""",
        **codex_env,
        CLAUDE_CODE_SESSION_ID="",
        CLAUDE_PID="",
        CLAUDE_JOB_DIR="",
        CODEX_THREAD_ID="codex-thread",
        CODEX_PATH=program,
        FAKE_CODEX_LOG=log,
        CHECKS=checks,
    )
    try:
        waiting = wait_for(
            lambda: files_model.read_json(checks),
            lambda reading: (
                reading is not None
                and reading["passes"] >= 2
                and reading["state"] == "waiting"
                and not reading["enabled"]
            ),
            failure=lambda: (
                "the adapter never completed two reads of the stopped page"
                + (adapter.stderr.read() if adapter.poll() is not None else "")
            ),
        )
        assert codex_adapter_model.adapter_is_live("codex-thread")
        declare_idle(page)
        wait_for(
            lambda: files_model.read_json(checks),
            lambda reading: (
                reading["passes"] >= waiting["passes"] + 2
                and reading["state"] == "idle"
            ),
            failure="the adapter never completed its idle-page reads",
        )
        assert codex_adapter_model.adapter_is_live("codex-thread")
        session_model.cmd_waiting(page, "resumed review")
        asked = append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Continue this review"}
        )
        wait_for(
            lambda: events_model.read_events(page),
            lambda events: any(
                event["kind"] == "pickup" and asked["id"] in event["events"]
                for event in events
            ),
            failure="resumed feedback did not reach the existing adapter",
        )
        hooks_model.cmd_hook(
            {"hook_event_name": "SessionEnd", "session_id": "codex-thread"}
        )
        wait_for(
            lambda: codex_adapter_model.adapter_is_live("codex-thread"),
            lambda live: not live,
            failure="the adapter did not retire after ownership ended",
        )
        out, err = adapter.communicate(timeout=STATED_TIMEOUT)
        assert adapter.returncode == 0, f"{out}{err}"
        assert (
            sum(
                event["kind"] == "pickup" and asked["id"] in event["events"]
                for event in events_model.read_events(page)
            )
            == 1
        )
    finally:
        with service_model.PageTransaction(page) as transaction:
            transaction.release_claim()


def test_an_offline_sibling_does_not_stop_browser_comments_reaching_codex(
    page_dir, under_codex, codex_env, tmp_path
):
    """One unavailable leaf cannot break another page's browser-to-task path."""
    live = page_dir
    source = re.sub(r"\s*<lf-diagram.*?</lf-diagram>", "", PAGE, flags=re.DOTALL)
    (live / "index.html").write_text(source, encoding="utf-8")
    stamped = CliRunner().invoke(
        cli_model.cli,
        ["page", "stamp", str(live), "--text", "published"],
    )
    assert stamped.exit_code == 0, stamped.output
    offline = tmp_path / "a-offline-page"
    vendoring_model.cmd_init(offline)
    session_model.cmd_waiting(offline, "earlier review")
    cleanup_model.write_json(
        offline / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": False,
            "lifetime": "session",
        },
    )

    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(live, "current review")
    finished = tmp_path / "codex-start-finished"
    # Both page claims and the carrier belong to the same actual task harness.
    # A second fake Codex process would declare a replacement session lifetime.
    prepare = """\
import sys
from pathlib import Path
from leaf.hosting import start_server
from leaf.service import claim_page
live, offline = map(Path, sys.argv[1:])
claim_page(offline)
claim_page(live)
start_server(live)
"""
    started = under_codex(
        shlex.join([sys.executable, "-c", prepare, str(live), str(offline)])
        + " && "
        + shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(live),
                "--codex-path",
                str(program),
            ]
        ),
        codex_env
        | {
            "CODEX_THREAD_ID": "codex-thread",
            "FAKE_CODEX_LOG": str(log),
        },
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        bool,
        failure="the detached Codex carrier did not start",
    )
    announcement = codex_start_announcement(started)
    release_codex_command(live, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    out = announcement + out
    assert started.returncode == 0, f"{out}{err}"

    try:
        claim = service_model.page_claim(live)
        record_claim(offline, **{**claim, "page": str(offline.resolve())})
        assert set(service_model.owned_pages("codex-thread")) == {live, offline}
        service = files_model.read_json(live / "service.json")
        origin = f"http://{service['host']}:{service['port']}"
        status, body = fetch(
            f"{origin}/api/event",
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": 1,
                    "text": "Does this reach the task?",
                    "attempt": "offline_sibling_comment_1",
                }
            ).encode(),
            token=server_model.host_key(),
        )
        assert status == 200, body
        comment = json.loads(body)["state"]["events"][-1]

        wait_for(
            lambda: files_model.read_json(live / "cursor.json"),
            lambda cursor: cursor == {"seq": comment["seq"]},
            failure=lambda: (
                "the browser comment did not reach the Codex queue: "
                f"adapter_log={adapter_log('codex-thread')!r}"
            ),
        )

        calls = [json.loads(line) for line in log.read_text().splitlines()]
        [queued] = [call for call in calls if "--thread" in call]
        assert queued[queued.index("--thread") + 1] == "codex-thread"
        prompt = queued[queued.index("--message") + 1]
        delivery = ElementTree.fromstring(prompt.splitlines()[1])
        payload = files_model.read_json(
            delivery_model.delivery_path(delivery.attrib["id"])
        )
        [delivered_comment] = payload["batches"][0]["events"]
        assert (delivered_comment["id"], delivered_comment["text"]) == (
            comment["id"],
            "Does this reach the task?",
        )
    finally:
        for page in (offline, live):
            declare_idle(page)
            with service_model.PageTransaction(page) as transaction:
                transaction.release_claim()


def test_a_codex_adapter_whose_start_was_never_committed_exits(
    codex_claimed_page, spawn, codex_env, tmp_path
):
    """`leaf codex start` gives its claim back when it is interrupted, so an adapter
    it announced ready to but never committed would carry a page the start reported
    as failed. The adapter waits for the caller's acknowledgement after announcing,
    and a caller that leaves instead ends it with its leases released."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    # A live owner, so the only thing that can end this adapter is the handshake.
    caller, end = socket.socketpair()
    adapter = spawn(
        [
            *LEAF_COMMAND,
            "codex",
            "run",
            "--codex-path",
            str(program),
            "--handshake",
            str(end.fileno()),
        ],
        env=codex_env | {"CODEX_THREAD_ID": "codex-thread", "FAKE_CODEX_LOG": str(log)},
        pass_fds=(end.fileno(),),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    end.close()
    caller.settimeout(STATED_TIMEOUT)
    try:
        assert json.loads(caller.makefile("rb").readline()) == {}
        assert codex_adapter_model.adapter_is_live("codex-thread")
    finally:
        caller.close()
    assert adapter.wait(timeout=STATED_TIMEOUT) == 1
    assert not codex_adapter_model.adapter_is_live("codex-thread")
    with service_model.PageTransaction(page) as transaction:
        transaction.release_claim()


def test_codex_adapter_exits_when_delivery_retries_outlive_its_claim(
    codex_claimed_page, spawn, codex_env, tmp_path, dead_pid
):
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page, "comment on the prototype")
    adapter = spawn(
        [*LEAF_COMMAND, "codex", "run", "--codex-path", str(program)],
        env=codex_env
        | {
            "CODEX_THREAD_ID": "codex-thread",
            "FAKE_CODEX_LOG": str(log),
            "FAKE_CODEX_QUEUE_FAILURE_ONCE": str(tmp_path / "failed-queue"),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        wait_for(
            lambda: codex_adapter_model.adapter_is_live("codex-thread"),
            bool,
            failure="the Codex adapter never became live for delivery retry",
        )
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "hello adapter"}
        )
        wait_for(
            lambda: (
                codex_records("codex-thread"),
                log.read_text().splitlines() if log.exists() else [],
            ),
            lambda reading: (
                reading[0]
                and reading[0][0][1]["state"] == "offering"
                and len(reading[1]) > 1
            ),
            failure="the adapter did not reach its delivery retry",
        )

        claim = service_model.page_claim(page)
        record_claim(page, **{**claim, "pid": dead_pid})
        wait_for(
            lambda: codex_adapter_model.adapter_is_live("codex-thread"),
            lambda live: not live,
            failure="the Codex adapter outlived its page claim",
        )
        assert adapter.wait(timeout=STATED_TIMEOUT) == 0
        assert codex_records("codex-thread")[0][1]["state"] == "offering"
        assert files_model.read_json(page / "cursor.json") is None
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert len(calls) == 2
    finally:
        with service_model.PageTransaction(page) as transaction:
            transaction.release_claim()


def test_codex_adapter_keeps_transferred_input_unreceived(
    codex_claimed_page, spawn, codex_env, tmp_path
):
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page, "comment on the prototype")
    queue_wait = tmp_path / "held-queue"
    adapter = spawn(
        [*LEAF_COMMAND, "codex", "run", "--codex-path", str(program)],
        env=codex_env
        | {
            "CODEX_THREAD_ID": "codex-thread",
            "FAKE_CODEX_LOG": str(log),
            "FAKE_CODEX_QUEUE_WAIT": str(queue_wait),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        bool,
        failure="the Codex adapter never became live for the accepted receipt",
    )

    append_carried_log_record(
        page, {"kind": "comment", "author": "user", "text": "hello adapter"}
    )
    started = queue_wait.with_name(f"{queue_wait.name}.started")
    wait_for(
        started.exists,
        bool,
        failure="the accepted receipt never entered the fake Codex queue",
    )

    successor = record_claim(page, id="successor", harness="codex", agent="Codex")
    queue_wait.with_name(f"{queue_wait.name}.release").write_text("", encoding="utf-8")
    assert adapter.wait(timeout=STATED_TIMEOUT) == 0

    assert files_model.read_json(page / "cursor.json") is None
    assert page_state(page)["pending"] == 1
    assert service_model.page_claim(page) == successor
    pickups = [
        event for event in events_model.read_events(page) if event["kind"] == "pickup"
    ]
    assert pickups == []


def test_a_queued_codex_delivery_leaves_the_turn_ended_stamp_standing(
    codex_claimed_page, under_codex, codex_env, tmp_path
):
    """A direct wait's reader confirms the complete batch in its already-open turn.
    This carrier instead hands a pointer
    to Codex's durable same-task queue, which the loaded client starts and an unloaded
    task leaves standing until someone reopens it — and the adapter never reopens one.

    So the stamp the Stop hook left is still true after acceptance, and clearing it
    would put "Codex is working" over a task nobody has read the delivery in. The
    cursor advancing and the accepted delivery are what says the delivery went through:
    the assertion is that a completed queue delivery moved everything except this."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    working(page, "answering the last comment")
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(
            [*LEAF_COMMAND, "codex", "start", str(page), "--codex-path", str(program)]
        ),
        codex_env | {"CODEX_THREAD_ID": "codex-thread", "FAKE_CODEX_LOG": str(log)},
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # The fake task must still own the page while its claim moves to pytest.
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        bool,
        failure="the detached Codex carrier did not start",
    )
    announcement = codex_start_announcement(started)
    release_codex_command(page, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    out = announcement + out
    assert started.returncode == 0, f"{out}{err}"
    try:
        wait_for(
            lambda: (
                codex_adapter_model.adapter_is_live("codex-thread"),
                page_state(page)["listening"],
            ),
            all,
            failure="the detached Codex carrier did not become live and listening",
        )

        with service_model.PageTransaction(page) as transaction:
            transaction.close_turn("codex-thread")
        closed = service_model.page_claim(page)["turn_closed"]
        assert closed

        hello = append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "hello adapter"}
        )
        wait_for(
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": hello["seq"]},
            failure="the queued delivery cursor did not advance",
        )

        assert service_model.page_claim(page)["turn_closed"] == closed
        queued = page_state(page)["activity"]
        assert queued["kind"] == "working"
        assert [item["stage"] for item in queued["obligations"]] == ["queued"]

        declare_idle(page)
    finally:
        with service_model.PageTransaction(page) as transaction:
            transaction.release_claim()


def test_adding_a_page_cannot_race_the_codex_adapter_exit(
    codex_claimed_page, under_codex, codex_env, tmp_path, spawn
):
    first = codex_claimed_page
    second = tmp_path / "second-page"
    program, log = fake_codex_cli(tmp_path)
    environment = codex_env | {
        "CODEX_THREAD_ID": "codex-thread",
        "FAKE_CODEX_LOG": str(log),
    }
    session_model.cmd_waiting(first, "first page")
    start_lock = codex_adapter_model.adapter_start_lock_path("codex-thread")
    read_gate = tmp_path / "adapter-read-gate"
    os.mkfifo(read_gate)
    reading = tmp_path / "adapter-reading"
    marker = tmp_path / "adapter-final-recheck"
    probe = """\
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model

native_read_watch_pass = codex_adapter_model.read_watch_pass
native_flocked = codex_adapter_model.flocked
finishing = False

def observed_read_watch_pass(*args, **kwargs):
    global finishing
    reading = Path(os.environ["READING"])
    if not reading.exists():
        reading.write_text("reading", encoding="utf-8")
        with open(os.environ["READ_GATE"], "rb") as gate:
            gate.read(1)
    reading = native_read_watch_pass(*args, **kwargs)
    finishing = reading.outcome is not None or not reading.live
    return reading

@contextlib.contextmanager
def observed_flocked(path, **kwargs):
    if finishing and Path(path).resolve() == Path(os.environ["START_LOCK"]).resolve():
        Path(os.environ["MARKER"]).write_text("requested", encoding="utf-8")
    with native_flocked(path, **kwargs) as stream:
        yield stream

codex_adapter_model.read_watch_pass = observed_read_watch_pass
codex_adapter_model.flocked = observed_flocked
raise SystemExit(codex_adapter_model.run_adapter(os.environ["CODEX_PATH"]))
"""
    adapter = spawn_probe(
        spawn,
        first,
        probe,
        CLAUDE_CODE_SESSION_ID="",
        CLAUDE_PID="",
        CLAUDE_JOB_DIR="",
        CODEX_THREAD_ID="codex-thread",
        CODEX_PATH=program,
        START_LOCK=start_lock,
        READ_GATE=read_gate,
        READING=reading,
        MARKER=marker,
        FAKE_CODEX_LOG=log,
    )
    wait_for(
        lambda: (
            codex_adapter_model.adapter_is_live("codex-thread"),
            page_state(first)["listening"],
            reading.exists(),
        ),
        all,
        failure="the first adapter did not begin its page read",
    )

    subprocess.run([*LEAF_COMMAND, "page", "init", second], check=True)
    standing = subprocess.run(
        [*LEAF_COMMAND, "server", "start", second, "--standing"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(standing.stdout)["url"].startswith("http://127.0.0.1:")
    session_model.cmd_waiting(second, "second page")
    starter = None
    finished = tmp_path / "second-start-finished"
    starter_ready = tmp_path / "second-start-lock"
    start_program = """\
import contextlib, json, os, sys
from pathlib import Path
from leaf import codex_adapter
native_flocked = codex_adapter.flocked
@contextlib.contextmanager
def observed_flocked(path):
    if Path(path).resolve() == Path(sys.argv[3]).resolve():
        Path(sys.argv[4]).write_text("requested")
    with native_flocked(path) as held:
        yield held
codex_adapter.flocked = observed_flocked
print(json.dumps(codex_adapter.cmd_codex_start(Path(sys.argv[1]), sys.argv[2])), flush=True)
"""
    try:
        with cleanup_model.flocked(start_lock):
            declare_idle(first)
            with open(read_gate, "wb") as gate:
                gate.write(b"1")
            wait_for(
                marker.exists,
                bool,
                failure="the first adapter did not reach its final start-lock recheck",
            )
            starter = under_codex(
                shlex.join(
                    [
                        sys.executable,
                        "-c",
                        start_program,
                        str(second),
                        str(program),
                        str(start_lock),
                        str(starter_ready),
                    ]
                ),
                environment,
                finished=finished,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            wait_for(
                starter_ready.exists,
                bool,
                failure="the second start did not request the startup lock",
            )
            assert service_model.page_claim(second) is None

        announcement = codex_start_announcement(starter)
        release_codex_command(second, starter, finished)
        out, err = starter.communicate(timeout=STATED_TIMEOUT)
        out = announcement + out
        assert starter.returncode == 0, f"{out}{err}"
        wait_for(
            lambda: (
                codex_adapter_model.adapter_is_live("codex-thread"),
                page_state(second)["listening"],
            ),
            all,
            failure="the adapter exited after the second page joined its watch",
        )
    finally:
        if starter is not None and starter.poll() is None:
            starter.terminate()
            starter.wait(timeout=STATED_TIMEOUT)
        declare_idle(second)
        for page in (first, second):
            with service_model.PageTransaction(page) as transaction:
                transaction.release_claim()
        subprocess.run([*LEAF_COMMAND, "server", "stop", second], check=True)

    out, err = adapter.communicate(timeout=STATED_TIMEOUT)
    assert adapter.returncode == 0, f"{out}{err}"


def test_failed_codex_delivery_start_restores_the_previous_page_claim(
    page_dir, under_codex, codex_env, tmp_path
):
    program, log = fake_codex_cli(tmp_path)
    record_claim(page_dir, id="previous", pid=os.getpid())
    previous = service_model.page_claim(page_dir)
    failed = under_codex(
        shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(page_dir),
                "--codex-path",
                str(program),
            ]
        ),
        codex_env
        | {
            "CODEX_THREAD_ID": "codex-thread",
            "FAKE_CODEX_LOG": str(log),
            "FAKE_CODEX_REJECT_QUEUE": "1",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = failed.communicate(timeout=STATED_TIMEOUT)

    assert failed.returncode != 0, out
    assert "queue unsupported" in err
    assert service_model.page_claim(page_dir) == previous


def test_a_codex_command_claims_the_page_for_its_thread(codex_claimed_page):
    session = service_model.page_claim(codex_claimed_page)
    assert session["id"] == "codex-thread"
    assert session["agent"] == "Codex"
    assert session["harness"] == "codex"
    assert set(session) == {
        "page",
        "id",
        "agent",
        "harness",
        "pid",
        "cwd",
        "ts",
        "turn",
        "turn_opened",
        "turn_closed",
        "released",
        "generation",
        "acquisition",
    }
    assert page_state(codex_claimed_page)["agent"] == "Codex"


def test_a_codex_claim_records_the_session_not_the_shell_it_ran_through(
    tmp_path, under_codex, codex_env
):
    """The claim's pid is the one two reapers read as the session's life, and
    `$PPID` is not it: it is a fact about the shape of the command. Measured
    through `codex exec`, a bare command and an `&&` chain reported the codex
    process because the wrapping shell exec'd leaf in place, and a pipeline
        reported that shell — which exits with the command, so ownership would go
        inactive and its server would stop a second later. Here the
    shell is between the session and the command and has exited by the time this
    reads what was written, so a pid it could have recorded is one this cannot
    match."""
    page = tmp_path / "codex-page"
    env = codex_env | {"CODEX_THREAD_ID": "thread-shape"}
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=env, check=True)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    session = under_codex(shlex.join([*LEAF_COMMAND, "wait", str(page)]), env)
    assert session.wait(timeout=STATED_TIMEOUT) == 0
    assert service_model.page_claim(page)["pid"] == session.pid


def test_the_nearest_harness_runs_a_command_that_inherits_another(under_codex):
    """A command inherits the identity of every harness above it: Codex run from a
    Claude Code shell states both sessions, as this suite's Claude Code identity
    reaches the Codex it starts. The harness whose process is nearest above the
    command is the one running it, so a Codex task's command is Codex's; with no
    codex above it, the same environment is Claude Code's."""
    probe = (
        "from leaf.harness import session_harness; h = session_harness(); "
        "print(type(h).__name__, h.session)"
    )
    env = os.environ | {"CODEX_THREAD_ID": "inner-codex"}
    ran = under_codex(
        shlex.join([sys.executable, "-c", probe]),
        env,
        stdout=subprocess.PIPE,
        text=True,
    )
    out, _ = ran.communicate(timeout=STATED_TIMEOUT)
    assert ran.returncode == 0
    assert out.split() == ["CodexHarness", "inner-codex"]

    # Claude Code run from that Codex task's shell: the shell is its harness.
    inner = shlex.join([sys.executable, "-c", probe])
    ran = under_codex(
        f"CLAUDE_CODE_SESSION_ID=inner-claude CLAUDE_PID=$$ {inner}",
        env,
        stdout=subprocess.PIPE,
        text=True,
    )
    out, _ = ran.communicate(timeout=STATED_TIMEOUT)
    assert ran.returncode == 0
    assert out.split() == ["ClaudeCodeHarness", "inner-claude"]

    # With no codex above it, the same environment is Claude Code's, and a
    # process the Codex task detaches inherits only the identity chosen there.
    nearer = subprocess.run(
        [sys.executable, "-c", probe],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert nearer.returncode == 0, nearer.stderr
    assert nearer.stdout.split() == ["ClaudeCodeHarness", f"pytest-{os.getpid()}"]
    detached = (
        "from leaf.harness import detached_environment as d; "
        "print(sorted(set(d()) & {'CODEX_THREAD_ID', 'CLAUDE_CODE_SESSION_ID'}))"
    )
    ran = under_codex(
        shlex.join([sys.executable, "-c", detached]),
        env,
        stdout=subprocess.PIPE,
        text=True,
    )
    out, _ = ran.communicate(timeout=STATED_TIMEOUT)
    assert ran.returncode == 0
    assert out.strip() == "['CODEX_THREAD_ID']"


def test_a_codex_session_id_with_no_codex_above_it_is_refused(page_dir, monkeypatch):
    """A hand-built environment: CODEX_THREAD_ID states a Codex session and
    nothing running Codex is above this process, so there is no process whose
    life is that session's. Nothing to fall back on either — a pid guessed here
    is a claim that expires by itself, and every state that follows from one is
    silent, so the refusal names what it walked."""
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-nobody")
    monkeypatch.setattr(machine_model, "process_info", lambda _pid: (1, "python"))
    refused = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert refused.exit_code == 1, refused.output
    assert "no codex process runs above this one" in refused.output
    assert service_model.page_claim(page_dir) is None


def test_a_claim_records_where_the_session_is_working(page_dir, tmp_path, monkeypatch):
    """What tells one leaf from another on the drawer is the work behind it, which
    neither the title somebody wrote nor the state directory nobody chose says — so
    the claim records the directory the claiming command ran in, the same reading
    `layer_dirs` already takes cwd to be. Every seat gets it through `presence`, and a
    page nothing ever claimed says so rather than borrowing a path from somewhere."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    work = tmp_path / "api"
    work.mkdir()
    monkeypatch.chdir(work)
    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["cwd"] == str(work)
    assert presence_model.presence(page_dir, [])["session_cwd"] == str(work)
    with service_model.PageTransaction(page_dir) as page:
        page.release_claim()
    assert presence_model.presence(page_dir, [])["session_cwd"] == str(work)
    assert presence_model.presence(page_dir, [])["session_alive"] is False


def test_reinitializing_a_deleted_page_path_drops_its_old_claim(page_dir, monkeypatch):
    """A regenerated page is not the deleted page that occupied its path."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "old-session")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)

    shutil.rmtree(page_dir)
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert initialized.exit_code == 0, initialized.output

    assert service_model.page_claim(page_dir) is None
    assert service_model.owned_pages("old-session") == []


def test_a_fresh_init_does_not_delete_a_concurrently_created_pages_claim(
    tmp_path, monkeypatch, spawn
):
    """The first page creation is one serialized transition."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "concurrent-page"
    reached_layer = threading.Event()
    resume = threading.Event()
    original_composed_sheets = layer_model.composed_sheets

    def held_composed_sheets(sources):
        reached_layer.set()
        assert resume.wait(timeout=STATED_TIMEOUT), (
            "the concurrent init never released its peer"
        )
        return original_composed_sheets(sources)

    monkeypatch.setattr(layer_model, "composed_sheets", held_composed_sheets)
    executor = ThreadPoolExecutor(max_workers=1)
    first = executor.submit(vendoring_model.cmd_init, page)
    try:
        assert reached_layer.wait(timeout=STATED_TIMEOUT), (
            "the first init never reached its held read"
        )
        requested = tmp_path / "second-init-requested"
        second = spawn_probe(
            spawn,
            page,
            """\
import fcntl
native_flock = fcntl.flock
identity = Path(os.environ["PAGE"]).stat()
def observed_flock(fd, operation):
    descriptor = fd if isinstance(fd, int) else fd.fileno()
    if operation == fcntl.LOCK_EX and os.path.samestat(os.fstat(descriptor), identity):
        try:
            native_flock(fd, operation | fcntl.LOCK_NB)
        except BlockingIOError:
            Path(os.environ["REQUESTED"]).write_text("blocked")
        else:
            raise AssertionError("the overlapping init bypassed the page lease")
    return native_flock(fd, operation)
fcntl.flock = observed_flock
sys.argv = ["leaf", "page", "init", os.environ["PAGE"]]
cli_model.cli()
""",
            REQUESTED=requested,
        )
        wait_for(
            requested.exists,
            bool,
            failure="the overlapping init never attempted the held page lease",
        )
        resume.set()
        first.result(timeout=STATED_TIMEOUT)
        second_out, second_err = second.communicate(timeout=STATED_TIMEOUT)
        assert second.returncode == 0, f"{second_out}{second_err}"
        idled = subprocess.run(
            [*LEAF_COMMAND, "status", page, "idle"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert idled.returncode == 0, idled.stderr
        picked_up = subprocess.run(
            [*LEAF_COMMAND, "wait", page],
            env=os.environ
            | {
                "CLAUDE_CODE_SESSION_ID": "new-owner",
                "CLAUDE_PID": str(os.getpid()),
            },
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert picked_up.returncode == 2, picked_up.stderr
        assert service_model.page_claim(page)["id"] == "new-owner"
    finally:
        resume.set()
        executor.shutdown(wait=True, cancel_futures=True)
    assert first.done()
    assert service_model.page_claim(page)["id"] == "new-owner"


def test_the_codex_environment_defaults_the_name_but_a_worker_keeps_its_own(
    tmp_path, under_codex, codex_env
):
    """A Codex worker launched with LEAF_AGENT set keeps that voice rather than
    the harness's default name."""
    page = tmp_path / "worker-page"
    env = codex_env | {"CODEX_THREAD_ID": "thread-9", "LEAF_AGENT": "Indexer"}
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=env, check=True)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    waited = under_codex(shlex.join([*LEAF_COMMAND, "wait", str(page)]), env)
    assert waited.wait(timeout=STATED_TIMEOUT) == 0
    session = service_model.page_claim(page)
    assert session["id"] == "thread-9"
    assert session["agent"] == "Indexer" and session["harness"] == "codex"


def test_hook_remedies_follow_the_harness_not_the_display_name(
    tmp_path, under_codex, codex_env, capsys
):
    """LEAF_AGENT names the voice the banner and threads show; which
    machinery the hook prescribes (unified exec vs background tasks) keys on the
    recorded harness, so a renamed Codex worker still gets Codex remedies."""
    page = tmp_path / "worker-page"
    env = codex_env | {"CODEX_THREAD_ID": "w1", "LEAF_AGENT": "Indexer"}
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=env, check=True)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    finished = tmp_path / "codex-wait-finished"
    waited = under_codex(
        shlex.join([*LEAF_COMMAND, "wait", str(page)]), env, finished=finished
    )
    release_codex_command(page, waited, finished)
    assert waited.wait(timeout=STATED_TIMEOUT) == 0
    session_model.cmd_waiting(page, "")

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "w1"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "leaf codex start" in reason and str(page) in reason
    assert service_model.page_claim(page)["agent"] == "Indexer"


def test_stop_hook_keeps_codex_inside_the_exact_wait_session(
    codex_claimed_page, capsys
):
    page = codex_claimed_page
    session_model.cmd_waiting(page, "")
    session = service_model.page_claim(page)
    lease = leases_model.take_lease(leases_model.waiter_lease_path(page, session["id"]))
    assert lease

    # A live watcher lets Claude end its turn, but Codex must keep this one active
    # and poll the unified-exec session whose output can enter this context. The
    # lease cannot say whether that process is the initial wait or a rearmed ack,
    # so the remedy has to preserve both coordinates.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "poll the existing" in reason and "write_stdin" in reason
    assert "`leaf wait` before the first batch" in reason
    assert "rearmed `leaf wait --ack` afterward" in reason

    # The adapter's second lease proves that the watcher can deliver into a
    # later turn. With that carrier alive, this turn may end normally.
    adapter = leases_model.take_lease(leases_model.adapter_lease_path("codex-thread"))
    assert adapter
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    assert capsys.readouterr().out == ""
    adapter.close()

    # The existing one-shot escape still prevents a hook recursion.
    hooks_model.cmd_hook(
        {
            "hook_event_name": "Stop",
            "session_id": "codex-thread",
            "stop_hook_active": True,
        }
    )
    assert capsys.readouterr().out == ""

    # With no carrier, the ordinary remedy starts detached same-task delivery.
    leases_model.release_lease(lease)
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "leaf codex start" in reason and str(page) in reason

    # Pending output still has to cross context: the remedy is to poll the wait
    # already running, and nothing tells this task to start one in the background.
    # The delivery the poll yields says how this harness acknowledges it.
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    lease = leases_model.take_lease(leases_model.waiter_lease_path(page, session["id"]))
    assert lease
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "`leaf wait` before the first batch" in reason
    assert "rearmed `leaf wait --ack` afterward" in reason
    assert "background" not in reason
    acknowledge = session_model.wait_acknowledgement(
        harness_model.CodexHarness("codex-thread", "Codex")
    )("0a1b2c3d")
    assert "run `leaf wait --ack 0a1b2c3d` in unified exec" in acknowledge
    assert "background" not in acknowledge
    leases_model.release_lease(lease)

    receive_through(page, 1)
    # Answered before the page closes: an acknowledged comment with nothing
    # under it holds the turn on its own account, which is the subject of
    # test_an_acknowledged_comment_nobody_answered_holds_the_turn.
    thread_model.cmd_reply(
        page,
        events_model.read_events(page)[0]["id"],
        "so it does",
        None,
        for_event=events_model.read_events(page)[0]["id"],
    )
    declare_idle(page)
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    assert capsys.readouterr().out == ""


def test_a_codex_watcher_task_takes_the_parent_watch_obligation(
    codex_claimed_page, under_codex, codex_env, capsys
):
    """The task that blocks in wait is the claimant, not the task it wakes.

    That transfer is the bridge: the parent may finish its turn because it no
    longer owns an unattended page, while the helper's own Stop hook keeps the
    wait inside a live turn. Leaf does not need to know where that task sends the
    batch.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page, "comment on the prototype")
    watcher = under_codex(
        shlex.join([*LEAF_COMMAND, "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher" and reading[1],
        failure="the watcher task never claimed the page and entered leaf wait",
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
    assert capsys.readouterr().out == ""

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "leaf-watcher"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "Keep this turn active" in reason and "poll the existing" in reason

    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    out, err = watcher.communicate(timeout=STATED_TIMEOUT)
    assert watcher.returncode == 0, f"{out}{err}"
    _, header, [event] = printed(out)
    assert header["page"] == str(page)
    assert event["text"] == "hi"
    assert files_model.read_json(page / "cursor.json") is None


def test_a_superseded_waiter_cannot_deliver_the_new_owners_batch(
    codex_claimed_page, under_codex, codex_env
):
    """One page has one cursor owner even if two watcher tasks are started.

    The later wait takes the page's claim. The earlier wait must then leave the
    watch set rather than print the same event from a task that no longer owns
    either the page or its acknowledgement cursor.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page, "comment on the prototype")

    first = under_codex(
        shlex.join([*LEAF_COMMAND, "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher-1" and reading[1],
        failure="the first watcher never claimed the page and entered leaf wait",
    )

    second = under_codex(
        shlex.join([*LEAF_COMMAND, "wait", str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-2"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher-2" and reading[1],
        failure="the replacement watcher never claimed the page and entered leaf wait",
    )

    first_out, first_err = first.communicate(timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert second.poll() is None
    assert page_state(page)["listening"]

    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    second_out, second_err = second.communicate(timeout=STATED_TIMEOUT)

    assert second.returncode == 0, f"{second_out}{second_err}"
    _, header, [event] = printed(second_out)
    assert header["page"] == str(page)
    assert event["seq"] == 1


def test_a_claim_transfer_stops_a_waiter_already_inside_a_poll(
    codex_claimed_page, under_codex, codex_env, monkeypatch
):
    """Ownership is checked at delivery, not only at the start of a poll.

    The probe holds a normal status read after the first watcher has already
    selected its page. A second session then takes the claim and an event arrives.
    The old watcher must re-read ownership before it prints that event; otherwise
    two sessions can act as cursor owner despite the supersession check passing on
    every ordinary run.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page, "comment on the prototype")
    selected = page.parent / "waiter-selected-page"
    probe = """
import sys
from pathlib import Path
from leaf import session

read_status = session.read_status
def held_status(page):
    Path(sys.argv[2]).write_text("selected", encoding="utf-8")
    sys.stdin.readline()
    return read_status(page)

session.read_status = held_status
sys.exit(session.cmd_wait(Path(sys.argv[1])))
"""
    first = under_codex(
        shlex.join([sys.executable, "-c", probe, str(page), str(selected)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wait_for(
        selected.exists,
        bool,
        failure="the first watcher never selected its page before the transaction",
    )
    assert service_model.page_claim(page)["id"] == "leaf-watcher-1"

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    first_out, first_err = first.communicate(input="continue\n", timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    session = service_model.page_claim(page)
    assert session["id"] == "replacement"


@pytest.mark.parametrize(
    "identity_names",
    [
        pytest.param(harness_model.IDENTITY_VARIABLES, id="bare-shell"),
        pytest.param((), id="harness-session"),
    ],
)
def test_wait_lease_is_exact_and_excludes_another_wait(
    page_dir, monkeypatch, spawn, identity_names
):
    """The held lease, not a timestamp or pid, is the wait's liveness."""
    # The suite's hook marks (`isolated_session`) are not records this test makes.
    for session in HOOKED_SESSIONS:
        leases_model.hooks_path(session).unlink()
    for name in identity_names:
        monkeypatch.delenv(name, raising=False)
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "comment on the prototype")
    # A bare waiter may hold an unclaimed page; a harness waiter claims the page
    # from its prior owner before taking its session-scoped lease.
    if not identity_names:
        record_claim(page_dir, id="past-session")
    lease_path = (
        page_dir / "waiter.lock"
        if identity_names
        else leases_model.waiter_lease_path(
            page_dir, harness_model.session_harness().session
        )
    )
    first = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ,
    )
    wait_for(
        lambda: leases_model.lock_is_held(lease_path),
        bool,
        failure="the first wait never took its exact lease",
    )

    second = subprocess.run(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        env=os.environ,
        check=False,
    )
    assert second.returncode == 2
    assert "another `leaf wait` is already active" in second.stderr

    # SIGTERM unwinds the wait's application cleanup and releases its kernel lease.
    first.terminate()
    first.communicate(timeout=STATED_TIMEOUT)
    assert lease_path.exists()
    assert not leases_model.lock_is_held(lease_path)


@pytest.mark.parametrize("prepared", [False, True])
def test_a_question_about_a_lease_does_not_turn_its_taker_away(tmp_path, prepared):
    """`lock_is_held` asks with a momentary shared lock, which refuses an exclusive
    one as a lease does. A lease taken while a question is open waits the question
    out; only a lease turns a taker away."""
    path = tmp_path / "lease"
    path.touch()
    with open(path, "rb") as question:
        fcntl.flock(question, fcntl.LOCK_SH)
        assert not leases_model.lock_is_held(path)
        threading.Timer(0.05, fcntl.flock, (question, fcntl.LOCK_UN)).start()
        lease = leases_model.take_lease(
            path, prepare=(lambda held: held.flush()) if prepared else None
        )
    assert lease is not None
    assert leases_model.take_lease(path) is None
    leases_model.release_lease(lease)


def test_a_stable_lock_serializes_waiting_takers_and_retains_its_file(
    tmp_path,
):
    """Every taker coordinates on one stable inode, including across release."""
    path = tmp_path / "purpose.lock"
    entered = threading.Event()
    release = threading.Event()
    attempting = threading.Event()

    def take():
        attempting.set()
        with cleanup_model.flocked(path):
            entered.set()
            assert release.wait(STATED_TIMEOUT)

    taker = threading.Thread(target=take)
    with cleanup_model.flocked(path):
        identity = path.stat()
        taker.start()
        assert attempting.wait(STATED_TIMEOUT), (
            "the taker never attempted the held lock"
        )
        assert not entered.is_set()
    assert entered.wait(STATED_TIMEOUT), (
        "the taker never entered the lock once it was free"
    )
    assert leases_model.lock_is_held(path)
    assert leases_model.take_lease(path) is None
    release.set()
    taker.join(STATED_TIMEOUT)
    assert not taker.is_alive()
    assert os.path.samestat(identity, path.stat())
    assert not leases_model.lock_is_held(path)
    with cleanup_model.flocked(path):
        assert leases_model.lock_is_held(path)


def test_prepared_lease_metadata_precedes_exclusive_liveness(tmp_path):
    """A preparation never pairs a successor's lease with retained old metadata."""
    path = tmp_path / "prepared.lock"
    path.write_bytes(b"old")

    def prepare(held):
        assert not leases_model.lock_is_held(path)
        held.truncate(0)
        held.write(b"new")
        held.flush()
        assert not leases_model.lock_is_held(path)

    lease = leases_model.take_lease(path, prepare=prepare)
    try:
        assert leases_model.lock_is_held(path)
        assert path.read_bytes() == b"new"
    finally:
        leases_model.release_lease(lease)
    assert not leases_model.lock_is_held(path)


def test_a_crashed_lease_holder_releases_the_stable_file_for_a_successor(
    tmp_path, spawn
):
    """Process death releases liveness without deleting the coordination inode."""
    path = tmp_path / "lease"
    holder = spawn(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import sys; "
                "from leaf.leases import take_lease; "
                "lease = take_lease(Path(sys.argv[1])); "
                "assert lease is not None; print('held', flush=True); sys.stdin.read()"
            ),
            str(path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout.readline() == "held\n"
    identity = path.stat()
    assert leases_model.lock_is_held(path)
    assert leases_model.take_lease(path) is None
    holder.terminate()
    holder.communicate(timeout=STATED_TIMEOUT)
    assert not leases_model.lock_is_held(path)
    assert os.path.samestat(identity, path.stat())
    lease = leases_model.take_lease(path)
    assert lease is not None
    assert leases_model.take_lease(path) is None
    leases_model.release_lease(lease)
    assert not leases_model.lock_is_held(path)
    assert os.path.samestat(identity, path.stat())


def test_a_page_lock_is_its_directory_and_follows_a_page_made_again(
    tmp_path, monkeypatch
):
    """The page lock is the page directory, so it leaves nothing in the state home
    and ends with the page. A taker that waited on a directory deleted and made
    again at the same path locks the new one, so it excludes the next taker; a
    page gone for good raises."""
    page = tmp_path / "page"
    assert CliRunner().invoke(cli_model.cli, ["page", "init", str(page)]).exit_code == 0
    assert not (machine_model.state_home() / "page-locks").exists()

    entered = threading.Event()
    release = threading.Event()
    requested = threading.Event()
    native_flock = fcntl.flock

    def observed_flock(fd, operation):
        if threading.current_thread() is taker and not requested.is_set():
            assert os.path.samestat(os.fstat(fd), page.stat())
            with pytest.raises(BlockingIOError):
                native_flock(fd, operation | fcntl.LOCK_NB)
            requested.set()
        return native_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", observed_flock)

    def take():
        with leases_model.page_locked(page):
            entered.set()
            assert release.wait(STATED_TIMEOUT), (
                "the replacement lock was never released"
            )

    taker = threading.Thread(target=take)
    try:
        with leases_model.page_locked(page):
            taker.start()
            assert requested.wait(STATED_TIMEOUT), (
                "the taker never opened the old directory"
            )
            shutil.rmtree(page)
            page.mkdir()
        assert entered.wait(STATED_TIMEOUT), (
            "the taker never locked the replacement directory"
        )
        fd = os.open(page, os.O_RDONLY)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    finally:
        release.set()
        taker.join(STATED_TIMEOUT)
    assert not taker.is_alive(), "the taker retained the replacement directory lock"

    page.rmdir()
    with pytest.raises(FileNotFoundError), leases_model.page_locked(page):
        pass


def test_a_new_claim_cannot_borrow_the_previous_sessions_wait_lease(
    page_dir, monkeypatch
):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "first")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    first = harness_model.session_harness()
    first_turn = service_model.page_claim(page_dir)["turn"]
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(page_dir, first.session)
    )
    assert lease and page_state(page_dir)["listening"]

    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["turn"] == first_turn
    assert page_state(page_dir)["listening"]

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["turn"] != first_turn
    assert not page_state(page_dir)["listening"]
    leases_model.release_lease(lease)


def test_a_restarted_session_cannot_reopen_a_dead_claims_turn(
    page_dir, monkeypatch, dead_pid
):
    """A reused session id is provenance, not proof that its old turn resumed."""
    old = record_claim(page_dir, id="reused", pid=dead_pid, turn="old-turn")
    assert not service_model.claim_is_active(old)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "reused")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))

    assert service_model.claim_page(page_dir)
    renewed = service_model.page_claim(page_dir)
    assert renewed["id"] == "reused"
    assert renewed["turn"] != "old-turn"


def test_stop_hook_does_not_borrow_a_foreign_bare_waiter_lease(page_dir, monkeypatch):
    """A page-local lease proves only an unclaimed bare-shell watch."""
    session_model.cmd_waiting(page_dir, "")
    bare = leases_model.take_lease(page_dir / "waiter.lock")
    assert bare
    try:
        assert page_state(page_dir)["listening"]
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "harness-owner")
        monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
        assert service_model.claim_page(page_dir)
        claim = service_model.page_claim(page_dir)
        assert not leases_model.lock_is_held(
            leases_model.waiter_lease_path(page_dir, claim["id"])
        )
        assert leases_model.lock_is_held(page_dir / "waiter.lock")
        assert not page_state(page_dir)["listening"]

        with service_model.PageTransaction(page_dir) as page:
            page.release_claim()
        assert page_state(page_dir)["listening"]
    finally:
        bare.close()


def test_the_stop_hook_records_the_ending_of_the_turn_behind_a_claim(claimed, capsys):
    """A `working` claim is written by a model's turn, and a turn can end at any token
    without running anything — so nothing writes its close, and the page was left to
    find an abandoned claim by outwaiting a clock. The Stop hook is the harness
    watching that same moment, which is what these hooks are for.

    It stamps whether or not it has a nudge to make, and ahead of both of the guard's
    early returns: a turn that ends with nothing outstanding is exactly the turn that
    walks away from a `working` claim. The stamp is provenance and lands on the claim
    record rather than in status.json — what the agent said it was doing stays the
    agent's to write, which is the line SessionEnd already draws."""
    working(claimed, "reading the reconnect traces")
    assert service_model.page_claim(claimed)["turn_closed"] is None
    events = events_model.read_events(claimed)
    assert presence_model.presence(claimed, events)["turn_closed"] is None

    # A live watcher: the guard has nothing to say, and the ending is recorded anyway.
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    closed = service_model.page_claim(claimed)["turn_closed"]
    assert closed
    assert presence_model.presence(claimed, events)["turn_closed"] == closed
    # And what the agent said it was doing is untouched by the observation of it.
    [task] = page_state(claimed)["browser"]["tasks"]
    assert task["running"]["text"] == "reading the reconnect traces"

    # Re-entry after a block stands the guard down before it would speak; the stamp is
    # the turn's own and is taken on that ending too.
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    assert capsys.readouterr().out == ""
    reentered_closed = service_model.page_claim(claimed)["turn_closed"]
    assert reentered_closed >= closed

    # Another session's turn ending says nothing about a page that is not one of its
    # own — the stamp names when this claim's turn ended or it means nothing.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s2"})
    assert service_model.page_claim(claimed)["turn_closed"] == reentered_closed
    leases_model.release_lease(lease)


def test_receiving_a_batch_observes_the_session_turn_on_every_owned_page(
    claimed, tmp_path, capsys
):
    """The turn is the session's, not the delivering page's. The Stop hook closes it
    across every page the session holds, so the delivery that answers it has to reach
    the same set: a session holding two leaves would otherwise leave the sibling
    stamped through a turn that is demonstrably running, and two minutes later that
    leaf tells its own user the agent left when its turn ended.

    The sibling here never speaks — the batch is the other page's, and the wait ends
    on the first page that delivers. That is exactly the page whose stamp nothing else
    would clear."""
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    capsys.readouterr()
    working(claimed, "answering the first comment")
    working(sibling, "reading the sibling")
    serving(claimed, 1)
    serving(sibling, 2)
    assert service_model.claim_page(sibling)
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]
    assert service_model.page_claim(sibling)["turn_closed"]

    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c1", "author": "user", "text": "one"}
    )
    cleanup_model.prompt_turn("s1")
    assert session_model.cmd_wait() == 0
    delivered(capsys)
    assert service_model.page_claim(claimed)["turn_closed"] is None
    assert service_model.page_claim(sibling)["turn_closed"] is None

    # A page another session holds is not this turn's to speak for.
    others = tmp_path / "others"
    vendoring_model.cmd_init(others)
    capsys.readouterr()
    working(others, "another session's page")
    serving(others, 3)
    assert service_model.claim_page(others)
    claim = service_model.page_claim(others)
    record_claim(others, **{**claim, "id": "s2", "turn_closed": "then"})
    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c2", "author": "user", "text": "two"}
    )
    # The Stop hook delivers this one into the running turn itself.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == ["c2"]
    assert service_model.page_claim(others)["turn_closed"] == "then"
    declare_idle(sibling)
    declare_idle(others)


def test_the_prompt_hook_opens_the_turn_on_every_page_the_session_holds(
    claimed, tmp_path, capsys
):
    """A delivery is not the only observable opening, and it is not the one the
    banner sends the user to. The `quiet` banner says to nudge in the terminal;
    a user who does that answers where no batch is written, so no carrier ever
    hands one over and nothing would clear the stamp — the page would go on telling
    them to do the thing they just did.

    `UserPromptSubmit` is the literal mirror of the `Stop` branch that stamps the
    ending: same sweep over `owned_pages`, same place ahead of the early returns,
    same session scope."""
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    capsys.readouterr()
    working(claimed, "answering the first comment")
    working(sibling, "reading the sibling")
    serving(claimed, 1)
    serving(sibling, 2)
    assert service_model.claim_page(sibling)
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]
    assert service_model.page_claim(sibling)["turn_closed"]

    status_before = files_model.read_json(claimed / "status.json")
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"] is None
    assert service_model.page_claim(sibling)["turn_closed"] is None
    # Only the stamp moves: what the agent said it was doing stays the agent's.
    assert files_model.read_json(claimed / "status.json") == status_before

    # Another session's prompt says nothing about this one's pages.
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    capsys.readouterr()
    closed = service_model.page_claim(claimed)["turn_closed"]
    assert closed
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s2"})
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"] == closed
    declare_idle(sibling)


def test_a_named_wait_claim_does_not_invent_turn_entry(claimed, capsys):
    """Naming a page claims it without reopening an ended session turn.

    That ownership action does not confirm receipt of output: the batch remains
    pending, and no pickup is recorded until the actual reader confirms the
    delivery the Stop hook handed over.
    """
    working(claimed, "answering the first comment")
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]

    serving(claimed, 1)
    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c1", "author": "user", "text": "one"}
    )
    status_before = files_model.read_json(claimed / "status.json")

    assert session_model.cmd_wait(claimed) == 0
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]
    assert files_model.read_json(claimed / "status.json") == status_before
    assert files_model.read_json(claimed / "cursor.json") is None
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(claimed)
    )

    cleanup_model.prompt_turn("s1")
    # The Stop hook carries the batch into the turn it holds open, asked again
    # for the same turn or not.
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == ["c1"]
    assert service_model.page_claim(claimed)["turn_closed"] is None
    consume_pending_input("s1")

    # A batch this session never took says nothing about its turn: the successor
    # that delivers it is the one whose turn opened.
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    capsys.readouterr()
    closed = service_model.page_claim(claimed)["turn_closed"]
    assert closed
    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c2", "author": "user", "text": "two"}
    )
    with service_model.PageTransaction(claimed) as page:
        page.open_turn("s2")
    assert service_model.page_claim(claimed)["turn_closed"] == closed


def test_a_stop_that_hands_over_input_keeps_the_turn_open(claimed, capsys):
    """Input that arrives as the turn ends goes into that same turn, so the Stop
    that hands it over blocks, and the turn it hands the input to is the one still
    running: not closed, and not closed and reopened as another. The repeated Stop
    that follows with nothing new is the turn really ending."""
    session_model.cmd_waiting(claimed, "")
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "and this?"}
    )

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    envelope = json.loads(continued(answer).split("\n")[1])
    [batch] = envelope["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", envelope["id"]]).exit_code
        == 0
    )
    claim = service_model.page_claim(claimed)
    assert (claim["turn"], claim["turn_closed"]) == (session["turn"], None)
    pickup = events_model.read_events(claimed)[-1]
    assert (pickup["kind"], pickup["turn"]) == ("pickup", session["turn"])

    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed)["turn_closed"]
    leases_model.release_lease(lease)


def test_a_repeated_stop_is_held_open_only_by_the_users_input(claimed, capsys):
    """A repeated Stop takes the user's input into the turn, and nothing else. A
    page's own errors and a worker's reports arrive unpaced, so a turn that
    blocked on each would never end; they stay pending for the next turn, and go
    in with the user's move when one arrives."""
    error = append_carried_log_record(
        claimed, {"kind": "error", "author": "page", "message": "a widget threw"}
    )
    repeated = {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}

    hooks_model.cmd_hook(repeated)
    assert capsys.readouterr().out == ""
    assert files_model.read_json(claimed / "cursor.json") is None
    assert [
        event["id"]
        for event in service_model.unacknowledged(events_model.read_events(claimed), 0)
    ] == [error["id"]]

    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "is it broken?"}
    )
    cleanup_model.prompt_turn("s1")
    hooks_model.cmd_hook(repeated)
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    envelope = json.loads(continued(answer).split("\n")[1])
    [batch] = envelope["batches"]
    assert [event["id"] for event in batch["events"]] == [error["id"], comment["id"]]
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", envelope["id"]]).exit_code
        == 0
    )
    assert files_model.read_json(claimed / "cursor.json") == {
        "seq": last_deliverable_seq(claimed)
    }


def test_a_page_that_changed_hands_before_receipt_keeps_its_input(
    claimed, tmp_path, monkeypatch, capsys
):
    """The hook captures every page's input, composes the turn's context, and only
    then confirms each page. A page another session claimed in between refuses its
    receipt, and its input stays pending for the new owner; the other page, and
    the ones after the refusal, are confirmed as usual."""
    moved = tmp_path / "a-moved"  # ahead of `claimed` in the walk's path order
    shutil.copytree(claimed, moved)
    assert service_model.claim_page(moved)
    comments = {
        page: append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": f"on {page.name}"}
        )
        for page in (moved, claimed)
    }
    compose = hook_carrier_model.compose

    def compose_then_transfer(batches, attention):
        composed = compose(batches, attention)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
        assert service_model.claim_page(moved)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
        return composed

    monkeypatch.setattr(hook_carrier_model, "compose", compose_then_transfer)
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    delivery = json.loads(continued(answer).split("\n")[1])
    assert [batch["page"] for batch in delivery["batches"]] == [
        str(moved),
        str(claimed),
    ]
    # Handover never confirms input. The actual reader checks current ownership.
    refused = CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery["id"]])
    assert refused.exit_code != 0

    assert service_model.page_claim(moved)["id"] == "s2"
    assert files_model.read_json(moved / "cursor.json") is None
    assert all(e["kind"] != "pickup" for e in events_model.read_events(moved))
    assert [
        event["id"]
        for event in service_model.unacknowledged(events_model.read_events(moved), 0)
    ] == [comments[moved]["id"]]
    assert files_model.read_json(claimed / "cursor.json") is None
    assert service_model.claim_page(moved)
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery["id"]]).exit_code
        == 0
    )
    assert all(
        events_model.read_cursor(page) >= comments[page]["seq"] for page in comments
    )


def test_input_too_large_for_the_turn_goes_as_a_pointer_the_model_confirms(
    claimed, capsys
):
    """Claude Code replaces a hook context of HOOK_CONTEXT_LIMIT characters or more
    with a preview, so confirming it on handover would confirm what the model never
    read. Input that large goes as a pointer instead: the hook confirms nothing, and
    the delivery it names says how the model confirms it once it has read it."""
    comment = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "x" * hook_carrier_model.HOOK_CONTEXT_LIMIT,
        },
    )

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    reason = continued(answer)
    assert len(reason) < hook_carrier_model.HOOK_CONTEXT_LIMIT
    [delivery_id] = re.findall(r"`leaf delivery read (\w+)`", reason)
    assert files_model.read_json(claimed / "cursor.json") is None
    assert all(e["kind"] != "pickup" for e in events_model.read_events(claimed))

    pointer = delivery_model.read_delivery(delivery_id)
    assert pointer["carrier"] == "hook"
    # Confirmed with a command that only confirms: the session's watch is its
    # Stop hook, which a wait the model ran would only take the lease from.
    assert f"`leaf delivery ack {delivery_id}`" in pointer["acknowledge"]
    [batch] = pointer["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery_id]).exit_code
        == 0
    )
    assert files_model.read_json(claimed / "cursor.json") == {
        "seq": last_deliverable_seq(claimed)
    }


def test_a_wait_only_wakes_a_session_its_hooks_have_run_for(
    page_dir, monkeypatch, capsys
):
    """The wake line assumes a hook will hand the input over, which holds only
    where the harness runs Leaf's hooks for the session. Until one has run, the wait
    prints the delivery for its reader to confirm, as it does for a bare shell, so
    a session launched without the hooks still reads its input. The mark lasts for
    the session, and SessionEnd removes it."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "unhooked")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    first = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "first"}
    )

    assert session_model.cmd_wait(page_dir) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["carrier"] == "wait"
    assert f"leaf wait --ack {payload['id']}" in payload["acknowledge"]
    assert [event["id"] for event in payload["batches"][0]["events"]] == [first["id"]]
    delivery_model.receive_delivery(payload["id"])

    hooks_model.cmd_hook(
        {"hook_event_name": "UserPromptSubmit", "session_id": "unhooked"}
    )
    capsys.readouterr()
    assert leases_model.hooks_ran("unhooked")
    second = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "second"}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, _, shown = woken(capsys.readouterr().out, "unhooked")
    assert [event["id"] for event in shown] == [second["id"]]

    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "unhooked"})
    assert not leases_model.hooks_ran("unhooked")


def test_the_state_payload_carries_the_clock_its_timestamps_were_written_by(page_dir):
    """Every ts a seat dates is written here, while the user's `Date.now()` is
    another machine's opinion. The payload states the writer's clock so the reading is
    made against that one; without it a skewed laptop misreads every age on the page,
    in one direction and with nothing to give it away."""
    state = served_page.full_state(page_dir, [])
    written = datetime.fromisoformat(state["now"])
    assert abs((datetime.now().astimezone() - written).total_seconds()) < 60


def test_the_state_payload_says_when_it_was_taken(page_dir):
    """Two answers can cross on the wire, and nothing the log orders tells them apart
    when neither carries a new event. Each says when the server took it, so a tab
    keeps the later one whichever lands last."""
    first = served_page.full_state(page_dir, [])
    second = served_page.full_state(page_dir, [])
    assert first["taken"] < second["taken"]
    assert abs(time.time() - second["taken"]) < 60


def test_stop_hook_holds_a_turn_only_where_nothing_will_watch_its_page(claimed, capsys):
    """Between turns a page is either watched or idle. Under Claude Code the
    watch is Leaf's own background Stop hook, which the turn's ending starts, so a
    turn ends over a page nothing watches yet. A carrier that is a process of its
    own, as a Codex task's adapter is, has to be running before the turn may end:
    without it the page keeps saying "Codex is working" over nobody."""
    session_model.cmd_waiting(claimed, "")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    record_claim(claimed, harness="codex")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert answer["decision"] == "block"
    assert (
        "no delivery adapter" in answer["reason"] and str(claimed) in answer["reason"]
    )

    # Blocking twice in a row is how a Stop hook loops, so a block already in
    # flight stands down.
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    assert capsys.readouterr().out == ""

    # A closed page ends the turn cleanly.
    declare_idle(claimed)
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # A page a second session has since picked up is that session's to watch, so
    # s1 is no longer held to it.
    session_model.cmd_waiting(claimed, "")
    record_claim(claimed, harness="codex", id="s2")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""


def test_pages_owing_the_same_thing_carry_one_copy_of_the_protocol(
    claimed, tmp_path, capsys, snapshot
):
    """Each page states its own debt; the protocol they share is stated once.

    Every debt used to carry the whole protocol with it, so a session holding
    three pages that owed the same thing spent three copies of the same ninety
    words saying so — most of what the blocking message weighed, and all of it
    between one page's line and the next.
    """
    second = tmp_path / "second-page"
    shutil.copytree(claimed, second)
    assert service_model.claim_page(second)
    for page, comment in ((claimed, "c1"), (second, "c2")):
        append_carried_log_record(
            page,
            {"kind": "comment", "id": comment, "author": "user", "text": "look"},
        )
        receive_through(page, last_deliverable_seq(page))
        session_model.cmd_waiting(page, "")

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)

    assert str(claimed) in reason and str(second) in reason
    assert reason.count("acknowledged user move with no answer") == 2
    assert reason.count(schema_model.ANSWER_ASK_INSTRUCTION) == 1
    # The lines stand together, so the user reaches every page before the
    # first protocol rather than one page per protocol.
    assert reason.index(str(second)) < reason.index(schema_model.ANSWER_ASK_INSTRUCTION)
    snapshot.check(
        yaml_document(
            "Two pages carry distinct debts and one shared answering instruction.",
            {
                "Stop": {
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
                        "additionalContext": Prose(
                            reason.replace(str(claimed), "<first-page>").replace(
                                str(second), "<second-page>"
                            )
                        ),
                    }
                }
            },
        )
    )


def test_a_preview_owes_no_watcher_but_still_carries_its_user(claimed, capsys):
    """A developer preview is a page put up to be looked at, not handed over.

    A session inspecting a dozen slots was carrying a dozen copies of the same
    "no watcher" line into every turn, none of which named anything a user was
    waiting on. What must survive the exemption is the user: a comment left on
    a preview is as unanswered as one left anywhere else, and the clause that
    reports it runs above this one.
    """
    # A Codex task owes its pages an adapter; a Claude Code session's watch is
    # its own Stop hook, and owes nothing here.
    session_model.cmd_waiting(claimed, "")
    record_claim(claimed, harness="codex")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert "no delivery adapter" in json.loads(capsys.readouterr().out)["reason"]

    cleanup_model.write_json(
        claimed / schema_model.PREVIEW_FILE,
        {
            "kind": "example",
            "example": "triage-board",
            "checkout": "leaf",
            "interaction": "user",
            "started": "2026-09-01T10:00:00+00:00",
        },
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # Presence is the whole reading. The serve path's user raises on a preview
    # file it cannot parse, and this guard fails open by saying nothing, so a
    # user here would take every page the session holds down without a word.
    (claimed / schema_model.PREVIEW_FILE).write_text("{not json", encoding="utf-8")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    record_claim(claimed)

    append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "user", "revision": 1, "text": "is this right?"},
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert batch["page"] == str(claimed)
    assert [event["text"] for event in batch["events"]] == ["is this right?"]
    assert "no watcher" not in reason
    # Handed over, the comment is owed an answer, and a later Stop holds for it.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    consume_pending_input("s1")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    assert f"{claimed}: 1 acknowledged user move with no answer" in reason
    assert "no watcher" not in reason


def test_hook_drops_a_page_transferred_after_ownership_discovery(claimed, monkeypatch):
    """Ownership transfer before the planner's page lock belongs to the new owner."""
    session_model.cmd_waiting(claimed, "")
    discover = hook_carrier_model.owned_pages

    def transfer(session_id):
        pages = discover(session_id)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
        assert service_model.claim_page(claimed)
        return pages

    monkeypatch.setattr(hook_carrier_model, "owned_pages", transfer)
    assert hook_carrier_model.unattended_pages("s1") == []


@pytest.mark.parametrize("rewritten", [True, False])
def test_the_turn_holds_again_when_a_version_takes_the_answer_back(
    claimed, capsys, rewritten
):
    """A pick answers the question it was asked in, and a version that rewrites
    the option picked takes that answer back — so the question is open again and
    nobody has been told. This is the guard's whole subject, and it is the one
    reading that cannot load the page's vendored registry: that load is a gate,
    and the Stop hook fails open, so a raise here stands the guard down on any
    page a little older than the code and says nothing.

    Where each id sits is not the vocabulary's to answer, so the hook reads that
    much and holds the turn exactly when `page state` says the thread is open.
    The floor lands on the option rather than on the group, which is what makes
    the reading matter — a floor on the group is in the action's own name.

    The unrewritten arm is the control: the pick still stands, the thread reads
    answered, and the hook must say nothing. Without it a guard that blocked on
    every acknowledged comment would pass the other arm."""
    (claimed / "index.html").write_text(PICKS_PAGE)
    let_a_pick_settle_a_thread(claimed, "which")
    session_model.cmd_waiting(claimed, "")
    # Watched, so the guard's other clause is clear and what fires below can only
    # be this one.
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, service_model.page_claim(claimed)["id"])
    )
    assert lease
    asked = append_carried_log_record(
        claimed,
        {"kind": "comment", "id": "which", "author": "user", "text": "which of these?"},
    )
    publish(claimed, 1)
    append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"options": ["flag-first"]},
        },
    )
    note = {
        "kind": "note",
        "author": "agent",
        "version": 2,
        "revision": 2,
        "text": "rewrote the first option" if rewritten else "tidied the prose",
    }
    if rewritten:
        note["restated"] = ["flag-first"]
    append_carried_log_record(claimed, note)
    receive_through(
        claimed,
        next(
            e["seq"]
            for e in reversed(events_model.read_events(claimed))
            if e["kind"] == "action"
        ),
    )

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    printed = capsys.readouterr().out
    if rewritten:
        answer = json.loads(printed)
        assert "decision" not in answer
        assert f"--for {asked['id']}" in continued(answer)
    else:
        assert printed == ""


def test_an_acknowledged_comment_nobody_answered_holds_the_turn(claimed, capsys):
    """Acknowledging is what takes a comment off the batch, so after it no
    watcher will raise that comment again and every other gate reads the page as
    clean. The failure, from a live channel session: a comment arrived while the
    agent was mid-turn on something else, the agent acknowledged it, answered
    the person in the terminal instead of on the page, and the user was left
    with a question that nothing would ever deliver again."""
    session_model.cmd_waiting(claimed, "")
    # Watched, which is the whole of what clears the guard's other case and
    # clears nothing here.
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    assert "1 acknowledged user move with no answer" in continued(answer)
    assert asked["id"] in continued(answer)
    assert service_model.page_claim(claimed)["turn_closed"] is None
    # An id is all this can name, to a session that may no longer hold a word of
    # what was said under it, so the instruction that reaches it has to carry the
    # reading that recovers the exchange.
    assert schema_model.ANSWER_ASK_INSTRUCTION in continued(answer)
    assert f"`leaf thread reply <page> --for {asked['id']}`" in continued(answer)

    # Bound to the claimant's App Server turn, the same move is answered by that
    # turn's final message, which is what the reason names instead: `leaf thread reply`
    # refuses a bound event.
    with service_model.PageTransaction(claimed) as page:
        page.bind_delivery_reply(session["id"], asked["id"], "a1")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    assert f"your turn's final message for {asked['id']}" in reason
    assert "leaf thread reply <page>" not in reason
    with service_model.PageTransaction(claimed) as page:
        page.clear_delivery_reply_binding(session["id"], asked["id"], "a1")

    # A reply clears it, and the thread stays open behind it: closing one is the
    # user's to do, so an open thread is not an unanswered one.
    thread_model.cmd_reply(
        claimed,
        asked["id"],
        "because the fold is absolute",
        None,
        for_event=asked["id"],
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # The user's follow-up puts the decision back, and this is the case that picks
    # the reading. The browser posts a follow-up as a reply of the user's own,
    # so a gate asking whether anyone but them has *ever* spoken is answered
    # "yes" by the reply above and never fires for this thread again — the drop
    # this test is named for, one level down and just as permanent. Reading the
    # last word costs a thread that wants no answer one `leaf thread resolve`, which is
    # a question the agent is holding the context to settle; the other reading
    # costs the user their question, which nobody sees at all.
    follow = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": asked["id"],
            "text": "but why not C?",
        },
    )
    # The harness opens the follow-up turn; its Stop carries the new input, and a
    # later Stop holds for an answer to the last word.
    cleanup_model.prompt_turn("s1")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [follow["id"]]
    consume_pending_input("s1")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert f"--for {follow['id']}" in continued(capsys.readouterr().out)
    thread_model.cmd_reply(
        claimed,
        follow["id"],
        "C is slower on the hot path",
        None,
        for_event=follow["id"],
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # Closing the thread is the other way to answer for one, for the cases where
    # waiting on the user says nothing.
    moot = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "and C?"}
    )
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert moot["id"] in continued(capsys.readouterr().out)
    thread_model.cmd_resolve(claimed, moot["id"])
    capsys.readouterr()  # cmd_resolve prints the event it wrote
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # The agent's own decision holds nothing while the user has yet to answer it:
    # the last word there is the agent's. When they answer in the thread — which
    # is where the panel's reply box puts it — the decision is the agent's again, and
    # it is the last word rather than any reading of the root that says so.
    ask = append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "agent", "text": "which storage engine?"},
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    answered = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": ask["id"], "text": "sqlite"},
    )
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert f"--for {answered['id']}" in continued(capsys.readouterr().out)
    thread_model.cmd_reply(
        claimed,
        answered["id"],
        "sqlite it is",
        None,
        for_event=answered["id"],
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    leases_model.release_lease(lease)


def test_the_guard_survives_a_page_vendored_before_the_layer_moved(claimed, capsys):
    """A page directory holds the copy of the layer it was created with, and the
    stamp refuses a copy the current layer has outgrown — by design, since that
    refusal is what sends an agent to re-vendor. The Stop hook is the one user
    that must never put the question: hook registrations fail open, so a raise
    here stands the *whole* guard down, watch clause included, on any page a
    little older than the checkout, and says nothing about it. Found by running
    the guard against a real page from an earlier vendoring, where reading the
    published version to settle threads loaded that page's registry."""
    session_model.cmd_waiting(claimed, "")
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    registry = files_model.read_json(claimed / "registry.json")
    del registry["$events"]["kinds"]["action"]
    cleanup_model.write_json(claimed / "registry.json", registry)
    # Without this the test passes for the wrong reason: it has to be a page
    # whose registry the current layer really does refuse.
    with pytest.raises(registry_contract.RegistryError):
        registry_storage.load_registry(claimed)

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    assert asked["id"] in continued(answer)
    leases_model.release_lease(lease)


def test_claude_codes_hook_input_is_confirmed_only_by_its_reader(claimed, capsys):
    """Claude Code's prompt hook runs as every turn begins, including the one a
    background wait's ending opens, and its Stop hook as a turn ends; each hands
    the turn the whole pending delivery and confirms it, so the model reads no
    output and runs no acknowledgement, and the move reads Picked up at once."""
    working(claimed, "revising")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert page_state(claimed)["pending"] == 1
    # A running wait changes nothing: it only wakes the session.
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    leases_model.release_lease(lease)
    instruction, envelope = context.split("\n")[:2]
    assert "acknowledge" in instruction
    payload = json.loads(envelope)
    assert payload["carrier"] == "hook"
    assert f"leaf delivery ack {payload['id']}" in payload["acknowledge"]
    [batch] = payload["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert page_state(claimed)["pending"] == 1
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", payload["id"]]).exit_code
        == 0
    )
    assert page_state(claimed)["pending"] == 0
    pickup = events_model.read_events(claimed)[-1]
    claim = service_model.page_claim(claimed)
    assert (pickup["kind"], pickup["phase"], pickup["events"]) == (
        "pickup",
        "opened",
        [comment["id"]],
    )
    assert (pickup["session"], pickup["turn"]) == (claim["id"], claim["turn"])

    # Input that arrives as the turn ends comes back into that same turn.
    later = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "one more"}
    )
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    blocked = json.loads(capsys.readouterr().out)
    assert "decision" not in blocked
    later_delivery = json.loads(continued(blocked).split("\n")[1])
    [batch] = later_delivery["batches"]
    assert [event["id"] for event in batch["events"]] == [later["id"]]
    assert (
        CliRunner()
        .invoke(cli_model.cli, ["delivery", "ack", later_delivery["id"]])
        .exit_code
        == 0
    )
    assert page_state(claimed)["pending"] == 0


def test_page_claim_takes_a_page_without_watching_it(page_dir, monkeypatch):
    """A Claude Code session picks up a page another session served by claiming
    it, and its own Stop hook watches the page from the end of the turn: a `leaf
    wait` there would hold the lease that hook needs."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s7")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    record_claim(page_dir, id="s2")
    result = CliRunner().invoke(cli_model.cli, ["page", "claim", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert service_model.owned_pages("s7") == [page_dir.resolve()]
    assert not leases_model.wait_is_live(page_dir, "s7")


def test_a_background_job_no_worker_hosts_is_resumed_with_its_input(
    tmp_path, monkeypatch, dead_pid
):
    """A background job's daemon retires its worker about an hour after the job
    goes idle, taking the socket and the Stop hook's watch with it, while the job
    still holds its pages. Input after that reaches it only by resuming the job:
    `claude --bg --resume` claims a fresh worker for the same session and runs the
    message there as its prompt. A job a live worker still hosts is not resumed,
    since the same command would start a copy of it."""
    config = tmp_path / "claude"
    (config / "sessions").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    bin_dir, argv = tmp_path / "bin", tmp_path / "argv"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {argv}\n')
    (bin_dir / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    page = tmp_path / "page"
    job = harness_model.ClaudeCodeHarness(
        session="s9", agent="Claude", job=str(tmp_path / "job")
    )

    # The retired worker's record outlives it; its pid does not.
    record = config / "sessions" / f"{dead_pid}.json"
    cleanup_model.write_json(
        record, {"pid": dead_pid, "sessionId": "s9", "messagingSocketPath": "/gone"}
    )
    assert job.nudge(page)
    wait_for(argv.exists, bool, failure="the job was never resumed")
    wait_for(
        lambda: len(argv.read_text().splitlines()),
        lambda n: n == 4,
        failure="the resume's arguments never arrived",
    )
    assert argv.read_text().splitlines() == [
        "--bg",
        "--resume",
        "s9",
        f"leaf: {page} has new input, which arrives with this message.",
    ]

    # A job whose worker still runs is not resumed, socket or none.
    argv.unlink()
    cleanup_model.write_json(
        record, {"pid": os.getpid(), "sessionId": "s9", "messagingSocketPath": "/gone"}
    )
    assert not job.nudge(page)
    record.unlink()
    assert not harness_model.ClaudeCodeHarness(session="s9", agent="Claude").nudge(page)
    assert not argv.exists()


def test_a_user_move_no_carrier_will_pick_up_messages_its_claude_code_session(
    server, page_dir, tmp_path, monkeypatch, socket_dir, snapshot
):
    """A running turn's Stop hook carries a user move into that turn, and a live
    `leaf wait` wakes the session for one, so the move nobody picks up arrives at a Claude
    Code claim whose turn has closed with no wait lease held — a watcher that died
    after the turn ended. The server then messages that session's socket, found
    by session id in Claude Code's session registry, once per closed turn: a user
    ticking three boxes must not queue three turns or three approvals, and input
    left unacknowledged when the Stop hook failed open must not silence the next
    closed turn.

    The server sends inside the event request, and a Unix connection is queued in
    the listener's backlog before `connect` returns, so a listener with nothing to
    accept once the POST has answered was never messaged."""
    closed = "2026-09-17T09:00:00+00:00"
    publish(page_dir)
    config = tmp_path / "claude"
    (config / "sessions").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    listeners = {}
    for pid, session_id in ((4101, "s1"), (4102, "s2")):
        address = str(socket_dir / f"{pid}.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(address)
        listener.listen()
        listener.setblocking(False)
        listeners[session_id] = listener
        cleanup_model.write_json(
            config / "sessions" / f"{pid}.json",
            {"pid": pid, "sessionId": session_id, "messagingSocketPath": address},
        )
        cleanup_model.write_json(
            config / "sessions" / f"{pid}.k{pid}.key",
            {"peerToken": f"token-{session_id}"},
        )

    def react(text):
        status, body = fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "comment", "revision": 1, "text": text}).encode(),
        )
        assert status == 200, body
        return json.loads(body)["state"]["events"][-1]["seq"]

    def messages(session_id):
        try:
            peer, _ = listeners[session_id].accept()
        except BlockingIOError:
            return None
        with peer:
            peer.settimeout(STATED_TIMEOUT)
            data = b"".join(iter(lambda: peer.recv(4096), b""))
        return [json.loads(line) for line in data.decode().splitlines()]

    try:
        # A turn still running: its Stop hook carries the move.
        record_claim(page_dir)
        react("while the turn runs")
        assert messages("s1") is None

        # A live watcher delivers it.
        claim = record_claim(page_dir, turn_closed=closed)
        lease = leases_model.take_lease(
            leases_model.waiter_lease_path(page_dir, claim["id"])
        )
        assert lease
        react("while a wait holds the lease")
        leases_model.release_lease(lease)
        assert messages("s1") is None

        # Codex's detached adapter queues its own turns; the socket is Claude Code's.
        record_claim(page_dir, harness="codex", turn_closed=closed)
        react("to a Codex task")
        assert messages("s1") is None

        record_claim(page_dir, turn_closed=closed)
        react("after the watcher died")
        auth, user = messages("s1")
        assert auth == {"type": "auth", "token": "token-s1"}
        assert user["type"] == "user" and user["session_id"] == "s1"
        assert user["message"]["role"] == "user"
        assert str(page_dir.resolve()) in user["message"]["content"]
        snapshot.check(
            yaml_document(
                "A real user POST reaches the Claude Code socket after its watcher died.\n"
                "This is the complete user frame, without the separate authentication frame.",
                _interaction_prompt_evidence(page_dir, {"socket user frame": user}),
            )
        )
        assert messages("s2") is None
        react("in the same closed turn")
        assert messages("s1") is None

        # The next closed turn is messaged, whatever is still unacknowledged.
        record_claim(page_dir, turn="turn-2", turn_closed=closed)
        react("in the next closed turn")
        assert messages("s1") is not None

        # Another live session's socket is never a stand-in for the claimant's,
        # and input after a send nobody took tries again.
        record_path = config / "sessions" / "4101.json"
        record = files_model.read_json(record_path)
        record_path.unlink()
        record_claim(page_dir, turn="turn-3", turn_closed=closed)
        react("once the claimant's session has left the registry")
        assert messages("s1") is None and messages("s2") is None
        cleanup_model.write_json(record_path, record)
        react("once it is back")
        assert messages("s1") is not None

        # An interrupted turn runs no Stop hook, so only the session's own record
        # says it ended. A turn nothing has renewed for longer than the working
        # grace may still be running a long step, so it is not messaged; once the
        # record reads idle the input is, once for that ending and again for the
        # next interrupt under the same turn id.
        live = os.getpid()
        cleanup_model.write_json(
            config / "sessions" / f"{live}.k{live}.key", {"peerToken": "token-s1"}
        )
        opened = datetime.now().astimezone() - timedelta(minutes=20)
        record_claim(page_dir, turn="turn-4", turn_opened=opened.isoformat())
        cleanup_model.write_json(
            page_dir / "status.json",
            {"state": "waiting", "detail": "", "ts": opened.isoformat(), "after": 0},
        )
        # `None` leaves the record as it stands: more input after the same ending.
        # A `shell` flip is the same ending seen again; a new prompt renews the
        # turn, and the interrupt after it is a new one.
        for status, prompt, messaged in (
            ("busy", False, False),
            ("idle", False, True),
            (None, False, False),
            ("shell", False, False),
            ("busy", True, False),
            ("idle", False, True),
        ):
            if prompt:
                time.sleep(1)
                cleanup_model.prompt_turn("s1")
            if status is not None:
                time.sleep(0.01)
                cleanup_model.write_json(
                    record_path,
                    {
                        **record,
                        "pid": live,
                        "status": status,
                        "statusUpdatedAt": int(time.time() * 1000),
                    },
                )
            react(f"while the session's record reads {status}")
            assert (messages("s1") is not None) is messaged, status
    finally:
        for listener in listeners.values():
            listener.close()


def test_only_serving_or_watching_a_page_puts_the_session_under_the_guard(
    page_dir, monkeypatch, capsys
):
    """Verifying a change to the page layer means driving throwaway pages, and the
    guard must not read a handful of test fixtures as a handful of abandoned
    pages. A directory this session only built and linted was handed to nobody.
    Listening on one is what puts a user on the other end, and from there the
    guard holds the session to it."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s7")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert check(page_dir).exit_code == 0
    assert service_model.owned_pages("s7") == []
    # `page init` left the page "working", which is the state the guard blocks on —
    # but only for a page some session answers for, and none does.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s7"})
    assert capsys.readouterr().out == ""

    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)]).exit_code == 0
    assert service_model.owned_pages("s7") == [page_dir.resolve()]

    # The Stop hook carries the input the wait woke the session for into the turn.
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s7"})
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["text"] for event in batch["events"]] == ["hi"]


def test_a_claim_an_older_leaf_wrote_is_dropped_rather_than_read_or_raised_on(
    tmp_path, page_dir, monkeypatch, capsys
):
    """The claims directory is one per machine, and the worktrees writing it are
    each on their own commit, so a session routinely reads records a different
    version wrote. Found in the wild: a session held six preview pages claimed
    before #811 named a harness, merged a main that had landed it, and every
    `leaf wait` after that died in `owned_by` on `claim["harness"]` — taking the
    watcher off the unrelated page the user was actually reading.

    Stage owes nothing to what an older version wrote, so the record is not
    migrated and its old shape is never read. It is dropped where it is read,
    which leaves its page unclaimed and every other page working."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s8")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    leases_model.mark_hooks("s8")  # its harness runs Leaf's hooks
    # The walk is in path order, so a name ahead of the user's page is what
    # puts the unreadable record in front of the batch the session came for.
    stale = tmp_path / "held-preview"
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(stale)]).exit_code == 0
    )
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert service_model.claim_page(stale)
    assert service_model.claim_page(page_dir)
    assert service_model.owned_pages("s8") == [stale.resolve(), page_dir.resolve()]

    claim = service_model.page_claim(stale)
    written_before_811 = {**claim, "host": claim["harness"]}
    del written_before_811["harness"]
    cleanup_model.write_json(service_model.claim_path(stale), written_before_811)

    # The reported failure: the watcher walks every page the session holds, and
    # the record it cannot read belongs to a page the user is not on.
    waited = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert waited.exception is None, repr(waited.exception)
    assert waited.exit_code == 0, repr(waited.output)
    _, _, [event] = woken(waited.output)
    assert event["text"] == "hi"

    assert service_model.page_claim(stale) is None
    assert service_model.owned_pages("s8") == [page_dir.resolve()]

    # The same reading answers for the two records a later rename leaves behind,
    # and the Stop hook shows both: a harness name outside this version's table
    # raises in `harness.claim_harness`, which dispatches on that value rather than
    # reading it, and a record missing a field a user brackets is taken for a
    # live claim, putting its page back in front of the guard — and in front of
    # `event_endpoint`'s nudge, which brackets `turn_closed` under the append
    # lock.
    for unreadable in (
        {**claim, "harness": "some-harness-a-later-leaf-named"},
        {key: value for key, value in claim.items() if key != "generation"},
    ):
        cleanup_model.write_json(service_model.claim_path(stale), unreadable)
        hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s8"})
        assert str(stale) not in capsys.readouterr().out
        assert service_model.page_claim(stale) is None


def test_the_app_s_shared_codex_is_not_taken_for_one_session_s_lifetime(
    tmp_path, under_codex, codex_env, codex_queue
):
    """The one word that separates the two Codex shapes, and the claim each writes.

    `CodexHarness.lifetime` finds a session by walking for the nearest `codex`
    ancestor. Under the CLI that process is the session and its pid is exact.
    The ChatGPT app runs one `codex ... app-server` for the whole app and every
    thread hangs off it, so the same walk handed every session one pid
    that outlives them all: a session-managed server checks `pid_alive` and
    never sees it die, and the page stays served until the app quits. Found in
    the wild as 133 unreleased claims naming a single app-server pid, 49 of
    their servers still up, the oldest 28 hours past its thread.

    Both runs go through the real claim door under a real process of that name,
    so what is asserted is the claim leaf writes rather than a reading of the
    walk. Nothing varies between them but the word.
    """

    def claimed(name, *, app_server):
        page = tmp_path / name
        subprocess.run([*LEAF_COMMAND, "page", "init", page], env=codex_env, check=True)
        started = under_codex(
            shlex.join([*LEAF_COMMAND, "server", "start", str(page)]),
            codex_env | codex_queue | {"CODEX_THREAD_ID": name},
            app_server=app_server,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = started.communicate(timeout=STATED_TIMEOUT)
        assert started.returncode == 0, f"{out}{err}"
        claim = service_model.page_claim(page)
        subprocess.run(
            [*LEAF_COMMAND, "server", "stop", page], env=codex_env, check=True
        )
        return claim

    session = claimed("cli-thread", app_server=False)
    assert session["pid"] > 0
    assert "activity" not in session

    app = claimed("app-thread", app_server=True)
    assert "pid" not in app
    assert app["activity"] == "multiplexed"


def test_a_claim_is_active_while_the_lifetime_it_names_holds(
    tmp_path, monkeypatch, dead_pid
):
    """One reading of what makes a claim active, and every hook comes through it.

    The claims this writes have to go to a relocated home. A record left in a shared
    directory outlives the run that made it, and a constant id in one is a name every
    run answers to: an earlier version of this test wrote into the developer's own
    `~/.local/state/leaf/claims`, one unreleased claim per run under this same id and
    nothing ever sweeping them. Seventy-six had collected when one of their pids came
    round again on a live process, and the rule below read as true for a claim no run
    of this test had made. `isolated_session` supplies the home.
    """
    page = tmp_path / "page"
    page.mkdir()
    record_claim(page, id="guarded")
    assert service_model.claim_is_active(service_model.page_claim(page))
    record_claim(page, id="guarded", released=cleanup_model.now_iso())
    assert not service_model.claim_is_active(service_model.page_claim(page))
    record_claim(page, id="guarded", pid=dead_pid)
    assert not service_model.claim_is_active(service_model.page_claim(page))

    # A background job's claim names the job's record and no process at all, so the
    # pid the environment states — dead here — is nothing to this user. Claimed
    # through the real door, which asks for an initialized page.
    (page / "events.jsonl").write_bytes(b"")
    job = tmp_path / "job"
    job.mkdir()
    cleanup_model.write_json(job / "state.json", {"sessionId": "guarded"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "guarded")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    assert service_model.claim_page(page)
    assert "pid" not in service_model.page_claim(page)
    assert service_model.claim_is_active(service_model.page_claim(page))
    # Deleting the job takes its record; the directory can stay behind empty.
    (job / "state.json").unlink()
    assert not service_model.claim_is_active(service_model.page_claim(page))

    # A harness that multiplexes every session into one process states no process at
    # all, so the claim stands on when the page was last touched. Both halves of
    # that reading: the claim's own stamp carries a page nothing has written to,
    # and a file under it carries one the session or a user has since moved.
    activity = tmp_path / "activity"
    activity.mkdir()
    record_claim(
        activity,
        id="multiplexed",
        harness="codex",
        activity="multiplexed",
        ts=cleanup_model.now_iso(),
    )
    claim = service_model.page_claim(activity)
    assert "pid" not in claim
    assert service_model.claim_is_active(claim)

    stale = (
        datetime.now().astimezone()
        - timedelta(seconds=schema_model.ACTIVITY_GRACE_SECS + 60)
    ).isoformat(timespec="seconds")
    record_claim(
        activity,
        id="multiplexed",
        harness="codex",
        activity="multiplexed",
        ts=stale,
    )
    assert not service_model.claim_is_active(service_model.page_claim(activity))

    # A touch inside the grace revives the same claim, which is what keeps a page
    # the session is still writing to — or a user still commenting on — served.
    (activity / "events.jsonl").write_bytes(b"")
    assert service_model.claim_is_active(service_model.page_claim(activity))

    # A dead claim answers for its own page and no more: the session's other
    # records are still walked, and the live one is still the session's page.
    other = tmp_path / "other"
    other.mkdir()
    (other / "events.jsonl").write_bytes(b"")
    record_claim(other, id="other-guarded")
    assert service_model.owned_pages("guarded") == []
    assert service_model.owned_pages("other-guarded") == [other.resolve()]


def _registered_hook_command(event):
    """The synchronous command the installed harness runs for this event."""
    registrations = json.loads((PLUGIN_ROOT / "hooks/hooks.json").read_text())["hooks"][
        event
    ]
    [hook] = [
        hook
        for registration in registrations
        for hook in registration["hooks"]
        if not hook.get("asyncRewake")
    ]
    return hook["command"]


def test_the_registered_watch_hook_wakes_only_under_claude_code(claimed, tmp_path):
    """The background Stop registration runs the watch only under Claude Code,
    and its exit 2 with stderr is the whole wake.

    Codex runs the same `hooks.json` and ignores `asyncRewake`, so it would wait
    on the hook: the command itself gates on `$CLAUDECODE`. Driven the way a harness
    drives it, through a shell with the payload on stdin, because the wiring (the
    gate, the guard script, uv, the exit status it passes through) is the
    subject."""
    stop = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())["hooks"][
        "Stop"
    ]
    [hook] = [
        hook for entry in stop for hook in entry["hooks"] if hook.get("asyncRewake")
    ]
    base = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    base["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    leases_model.mark_hooks("s1")  # its harness runs Leaf's hooks
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    cleanup_model.close_session_turn("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )

    def run(claude_code):
        return subprocess.run(
            ["sh", "-c", hook["command"]],
            input=json.dumps({"hook_event_name": "Stop", "session_id": "s1"}),
            env=base | ({"CLAUDECODE": "1"} if claude_code else {}),
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )

    outside = run(claude_code=False)
    assert (outside.returncode, outside.stdout, outside.stderr) == (0, "", "")
    woke = run(claude_code=True)
    assert (woke.returncode, woke.stdout) == (2, ""), woke.stderr
    assert woke.stderr.startswith(f"{claimed} has new input")

    # uv and Python spend exit 2 on their own failures, so a plugin copy uv cannot
    # run must end the hook silently rather than wake the session with an error.
    broken = tmp_path / "plugin"
    (broken / "hooks" / "scripts").mkdir(parents=True)
    (broken / "pyproject.toml").write_text("not a project")
    shutil.copy(
        PLUGIN_ROOT / "hooks" / "scripts" / "loop-guard.py",
        broken / "hooks" / "scripts",
    )
    (broken / "bin").mkdir()
    shutil.copy(PLUGIN_ROOT / "bin/leaf", broken / "bin/leaf")
    base["CLAUDE_PLUGIN_ROOT"] = str(broken)
    failed = run(claude_code=True)
    assert (failed.returncode, failed.stdout, failed.stderr) == (0, "", "")


def test_the_registered_hook_answers_out_of_interact_or_says_nothing(claimed, tmp_path):
    """The harness command calls Leaf's launcher, and Leaf answers under uv.

    Exercise the exact registration, stdin, environment selection and returned
    context. Startup failure and malformed input must leave the turn alone.
    """

    def run(payload, env=None):
        return subprocess.run(
            ["/bin/sh", "-c", _registered_hook_command("Stop")],
            input=payload,
            env=(env or os.environ) | {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)},
            capture_output=True,
            text=True,
            timeout=COMPOSITE_TIMEOUT,
            check=False,
        )

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    stop = json.dumps({"hook_event_name": "Stop", "session_id": "s1"})
    answered = run(stop)
    assert answered.returncode == 0, answered.stderr
    assert answered.stdout, "nothing came back: the CLI never answered under uv"
    [batch] = json.loads(continued(answered.stdout).split("\n")[1])["batches"]
    assert [event["text"] for event in batch["events"]] == ["hi"]

    # The library answers an unowned session silently under uv as well.
    stranger = run(json.dumps({"hook_event_name": "Stop", "session_id": "s2"}))
    assert (stranger.returncode, stranger.stdout, stranger.stderr) == (0, "", "")

    # The two shapes of a leaf failure a turn must not notice: the CLI raising,
    # and no uv there to raise it.
    crashed = run("not a hook payload")
    assert (crashed.returncode, crashed.stdout, crashed.stderr) == (0, "", "")
    unresolvable = run(stop, env=os.environ | {"PATH": str(tmp_path / "no-tools")})
    assert (unresolvable.returncode, unresolvable.stdout, unresolvable.stderr) == (
        0,
        "",
        "",
    )


@pytest.mark.parametrize(
    "event,watch",
    [
        ("Stop", False),
        ("Stop", True),
        ("UserPromptSubmit", False),
        ("PostToolUse", False),
        ("Interrupt", False),
    ],
)
def test_the_registered_hook_leaves_library_execution_to_uv(event, watch, tmp_path):
    """Turn hooks need no system Python; the shell launcher owns uv.

    This plugin copy has no library, and system python3 refuses to run. A recording
    uv witnesses the selected project, application command and unchanged payload.
    Only the async watch needs a stdlib supervisor to translate its wake result.
    """
    project = tmp_path / "plugin"
    guard = project / "hooks/scripts/loop-guard.py"
    guard.parent.mkdir(parents=True)
    guard.write_bytes((PLUGIN_ROOT / "hooks/scripts/loop-guard.py").read_bytes())
    launcher = project / "bin/leaf"
    launcher.parent.mkdir()
    launcher.write_bytes((PLUGIN_ROOT / "bin/leaf").read_bytes())
    launcher.chmod(0o755)
    tools = tmp_path / "tools"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$UV_CALLED"\n/bin/cat > "$UV_INPUT"\n'
    )
    uv.chmod(0o755)
    python = tools / "python3"
    python.write_text('#!/bin/sh\nprintf called > "$PYTHON_CALLED"\nexit 99\n')
    python.chmod(0o755)
    python_called = tmp_path / "python-called"
    called, received = tmp_path / "uv-called", tmp_path / "uv-input"
    payload = json.dumps({"hook_event_name": event, "session_id": "hook-harness"})
    done = subprocess.run(
        (
            [sys.executable, "-S", str(guard), "--watch"]
            if watch
            else ["/bin/sh", "-c", _registered_hook_command(event)]
        ),
        input=payload,
        env=os.environ
        | {
            "PATH": f"{tools}:/usr/bin:/bin",
            "CLAUDECODE": "",
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PYTHON_CALLED": str(python_called),
            "UV_CALLED": str(called),
            "UV_INPUT": str(received),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert called.read_text().splitlines() == [
        "run",
        "-q",
        "--no-dev",
        "--project",
        str(project),
        "python",
        "-m",
        "leaf",
        "hook",
        *(["--watch"] if watch else []),
    ]
    assert received.read_text() == payload
    assert not python_called.exists()


def test_the_registered_session_end_releases_shared_claims_without_an_environment(
    page_dir, tmp_path
):
    """A fresh install releases another checkout's claims within harness shutdown.

    Only the launcher and standalone stdlib cleanup exist in this install. No
    package can be imported and uv refuses to run; macOS's system Python 3.9
    exercises the same entry without site packages.
    """
    project = tmp_path / "cold-plugin"
    launcher = project / "bin/leaf"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((PLUGIN_ROOT / "bin/leaf").read_bytes())
    launcher.chmod(0o755)
    program = project / "skills/leaf/scripts/leaf/state.py"
    program.parent.mkdir(parents=True)
    program.write_bytes(
        (PLUGIN_ROOT / "skills/leaf/scripts/leaf/state.py").read_bytes()
    )
    tools = tmp_path / "tools"
    tools.mkdir()
    system_python = Path("/usr/bin/python3")
    (tools / "python3").symlink_to(
        system_python if system_python.exists() else sys.executable
    )
    uv_called = tmp_path / "uv-called"
    uv = tools / "uv"
    uv.write_text('#!/bin/sh\nprintf called > "$UV_CALLED"\nexit 99\n')
    uv.chmod(0o755)

    record_claim(page_dir, id="ended-session")
    marker_files = [
        cleanup_model.session_file("ended-session", suffix)
        for suffix in (
            cleanup_model.HOOKS_SUFFIX,
            cleanup_model.STEP_HOOK_SUFFIX,
            cleanup_model.TITLES_SUFFIX,
        )
    ]
    for marker in marker_files:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("session evidence")
    claims = service_model.claim_path(page_dir).parent
    (claims / "malformed.json").write_text("{")
    (claims / "wrong-shape.json").write_text("[]")
    missing_page = tmp_path / "missing-page"
    missing_claim = {"id": "ended-session", "page": str(missing_page), "released": None}
    missing_path = service_model.claim_path(missing_page)
    cleanup_model.write_json(missing_path, missing_claim)
    foreign = page_dir.parent / "foreign-page"
    foreign.mkdir()
    (foreign / cleanup_model.EVENTS_FILE).touch()
    record_claim(foreign, id="another-session")
    foreign_claim = service_model.page_claim(foreign)

    done = subprocess.run(
        ["/bin/sh", "-c", _registered_hook_command("SessionEnd")],
        input=json.dumps(
            {"hook_event_name": "SessionEnd", "session_id": "ended-session"}
        ),
        env=os.environ
        | {
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PATH": f"{tools}:/usr/bin:/bin",
            "UV_CALLED": str(uv_called),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not uv_called.exists()
    assert service_model.page_claim(page_dir)["released"] is not None
    assert not any(marker.exists() for marker in marker_files)
    assert service_model.page_claim(foreign) == foreign_claim
    assert files_model.read_json(missing_path) == missing_claim
    assert not missing_page.exists()

    # An empty shutdown needs neither a page nor a managed environment either.
    done = subprocess.run(
        ["/bin/sh", "-c", _registered_hook_command("SessionEnd")],
        input=json.dumps({"hook_event_name": "SessionEnd", "session_id": "empty"}),
        env=os.environ
        | {
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PATH": f"{tools}:/usr/bin:/bin",
            "UV_CALLED": str(uv_called),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not uv_called.exists()

    # The console and module entry use the same cleanup in a managed runtime.
    record_claim(page_dir, id="managed-session")
    done = subprocess.run(
        [*LEAF_COMMAND, "session-end"],
        input=json.dumps(
            {"hook_event_name": "SessionEnd", "session_id": "managed-session"}
        ),
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert service_model.page_claim(page_dir)["released"] is not None


def test_a_hook_in_a_session_holding_no_page_imports_no_page_reading_or_server(
    page_dir,
):
    """A harness runs Leaf's hooks at every turn of every session the plugin is
    installed in, and most hold no page. Each waits on `import leaf.hooks`, so
    that import, and a prompt or Stop hook in a session holding nothing, loads
    neither the page servers nor page reading: markup, registry schemas, and
    anchor capture. Run in a fresh interpreter, whose `sys.modules` is the hook's."""
    record_claim(page_dir, id="another-session")
    probe = """\
import io, json, runpy, sys
imported = [sorted(sys.modules)]
cases = (
    ("UserPromptSubmit", ["hook"], None),
    ("Stop", ["hook"], None),
    ("Stop", ["hook", "--watch"], None),
    ("UserPromptSubmit", ["hook"], "provider-turn"),
    ("PostToolUse", ["hook"], "provider-turn"),
    ("Stop", ["hook"], "provider-turn"),
    ("UserPromptSubmit", ["hook"], "interrupted-turn"),
    ("Interrupt", ["hook"], "interrupted-turn"),
)
for event, args, turn_id in cases:
    sys.argv = ["leaf", *args]
    payload = {"hook_event_name": event, "session_id": "holds-nothing"}
    if turn_id:
        payload["turn_id"] = turn_id
    sys.stdin = io.StringIO(json.dumps(payload))
    runpy.run_module("leaf", run_name="__main__")
    if turn_id:
        from leaf.codex_state import hook_turn
        observed = hook_turn("holds-nothing")
        assert observed["turn"] == turn_id
        assert observed["running"] == (event not in ("Stop", "Interrupt"))
    imported.append(sorted(sys.modules))
print(json.dumps(imported))
"""
    done = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=True,
    )
    heavy = (
        "leaf.cli",
        "leaf.harness",
        "psutil",
        "click",
        "leaf.hosting",
        "uvicorn",
        "leaf.http",
        "leaf.codex",
        "leaf.delivery",
        "leaf.thread",
        "websockets",
        "leaf.hook_carrier",
        "leaf.served_state.page",
        "leaf.event_contracts",
        "leaf.anchor_capture",
        "jsonschema",
        "markdown_it",
        "turbohtml",
    )
    for loaded in json.loads(done.stdout):
        assert [module for module in heavy if module in loaded] == []


def test_waiting_written_over_an_unanswered_move_names_it(claimed, snapshot):
    """`leaf status` reads its transition back so a silent success cannot pass for a
    no-op. Canonical activity keeps showing an unanswered user move over a `waiting`
    written ahead of it, so the banner the agent believes it set is not the one the
    user sees. The readback names the move; once it has an answer the line stands
    alone."""
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    comment = events_model.read_events(claimed)[0]["id"]
    waiting = ["status", str(claimed), "waiting", "pick one"]

    early = CliRunner().invoke(cli_model.cli, waiting)
    assert early.exit_code == 0, early.output
    assert json.loads(early.stdout)["detail"] == "pick one"
    assert early.stderr.splitlines() == [
        (
            f"1 user move with no answer (`leaf thread reply <page> --for {comment}`); "
            "the page reads waiting once each has one"
        )
    ]

    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(claimed),
            "--for",
            comment,
            "--text",
            "ok",
        ],
    )
    assert replied.exit_code == 0, replied.output
    settled = CliRunner().invoke(cli_model.cli, waiting)
    assert settled.stderr == ""
    assert json.loads(settled.stdout)["state"] == "waiting"
    snapshot.check(
        yaml_document(
            "The waiting status command names unanswered work until the reply settles it.",
            _interaction_prompt_evidence(
                claimed,
                {
                    moment: {
                        "exit": result.exit_code,
                        # The status as written, less the instant it was written at.
                        "status": {
                            key: value
                            for key, value in json.loads(result.stdout).items()
                            if key != "ts"
                        },
                        "note": result.stderr,
                    }
                    for moment, result in (
                        ("before reply", early),
                        ("after reply", settled),
                    )
                },
            ),
        )
    )


def test_idle_cannot_close_a_page_over_events_nobody_read(claimed, capsys):
    """`leaf status PAGE idle` is the way out of the guard's other case, so it
    reads as the way out of this one too. The events are the user's: a page
    idled over them ends the leaf on someone still waiting for an answer, and
    from the browser that looks exactly like one that ran its course."""
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    refused = CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"])
    assert refused.exit_code == 1
    assert "1 update nobody has picked up" in refused.output
    # The claimant's harness names the remedy: Claude Code's hook carries them.
    assert "Leaf's hook puts them in your context" in refused.output
    assert service_model.read_status(claimed)["state"] != "idle"

    # `leaf wait` wakes the session at once, and the prompt hook hands the input
    # to the turn and confirms it. Reading it is not answering it, though: the
    # same user is still waiting, and now nothing will raise the comment again,
    # so idle holds until the thread has something under it.
    assert CliRunner().invoke(cli_model.cli, ["wait", str(claimed)]).exit_code == 0
    assert consume_pending_input("s1")
    refused = CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"])
    assert refused.exit_code == 1
    assert "1 acknowledged user move with no answer" in refused.output
    assert service_model.read_status(claimed)["state"] != "idle"

    comment = events_model.read_events(claimed)[0]["id"]
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                str(claimed),
                "--for",
                comment,
                "--text",
                "ok",
            ],
        )
        .exit_code
        == 0
    )
    assert (
        CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"]).exit_code
        == 0
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # A worker's report holds idle the same way: idling over one would freeze its
    # provisional state on the page forever, with nobody left to absorb it.
    append_carried_log_record(
        claimed,
        {
            "kind": "report",
            "author": "agent",
            "widget": "t1",
            "meaning": {
                "scope": "page",
                "unit": "t1",
                "depends": ["t1"],
            },
            "action": "status",
            "detail": {"status": "review"},
            "revision": 1,
        },
    )
    refused = CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"])
    assert refused.exit_code == 1
    assert "1 update nobody has picked up" in refused.output
    cleanup_model.prompt_turn("s1")
    report = str(events_model.read_events(claimed)[-1]["seq"])
    assert (
        CliRunner()
        .invoke(
            cli_model.cli, ["wait", "--ack", delivery_through(claimed, int(report))]
        )
        .exit_code
        == 2
    )
    # A report is the agent's own news, so acknowledging it is the whole of what
    # it asks for; only a user's comment owes an answer as well.
    assert (
        CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"]).exit_code
        == 0
    )


def test_idle_and_the_stop_hook_hold_the_agent_to_the_same_moves(claimed, capsys):
    """A move a carrier queued for a later turn is that turn's debt: the turn that
    queued it may end over it, and may idle the page over it. Once the later turn
    opens it, both the Stop hook and `leaf status idle` hold the agent to it."""
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "one more thing"}
    )
    [comment] = events_model.read_events(claimed)
    batch = {"events": [{"seq": comment["seq"], "id": comment["id"]}]}

    def pickup(phase: str) -> None:
        with (
            service_model.PageTransaction(claimed) as page,
            delivery_model.receive_batch(page, batch, session_id="s1") as delivered,
        ):
            delivery_model.record_pickup(page, delivered, phase=phase, session="s1")

    def idle() -> str | None:
        result = CliRunner().invoke(cli_model.cli, ["status", str(claimed), "idle"])
        return None if result.exit_code == 0 else result.output

    pickup("queued")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert "acknowledged" not in capsys.readouterr().out
    assert idle() is None

    pickup("opened")
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert "1 acknowledged user move with no answer" in capsys.readouterr().out
    assert "1 acknowledged user move with no answer" in idle()


def test_idle_cannot_race_past_an_event_arriving_after_its_pending_check(
    page_dir, spawn
):
    """The pending check and idle transition are one decision.

    A browser post serialized after the check but before the status write must
    keep the page open. Otherwise Stop sees an idle page, permits the turn to
    end, and leaves the newly appended event with no watcher to deliver it.
    """
    session_model.cmd_waiting(page_dir, "comment on the prototype")
    marker = page_dir / "status-lock-requested"
    events = open(  # noqa: SIM115 - held across the child transition
        page_dir / "events.jsonl", "a+b"
    )
    fcntl.flock(events, fcntl.LOCK_EX)
    probe = """\
from leaf import service as service_model

original_flocked = service_model.flocked
events = Path(os.environ["EVENTS"]).resolve()
marker = Path(os.environ["MARKER"])

@contextlib.contextmanager
def observed_flocked(path, **kwargs):
    if Path(path).resolve() == events:
        marker.write_text("requested", encoding="utf-8")
    with original_flocked(path, **kwargs) as stream:
        yield stream

service_model.flocked = observed_flocked
sys.argv = ["leaf", "status", os.environ["PAGE"], "idle"]
cli_model.cli()
"""
    process = spawn_probe(
        spawn,
        page_dir,
        probe,
        EVENTS=page_dir / "events.jsonl",
        MARKER=marker,
    )

    deadline = time.monotonic() + STATED_TIMEOUT
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not marker.exists():
        events.close()
        pytest.fail("the idle command never requested the held event-log lock")

    # The marker is immediately before the command's lock acquisition. In the
    # broken ordering it appears only after the empty pending read; in the fixed
    # ordering it appears before that read. Appending while this process owns the
    # lock therefore makes the old command idle and the fixed command refuse.
    events.seek(0, os.SEEK_END)
    events.write(
        (
            events_model.jsonl_line(
                {
                    "kind": "comment",
                    "id": "c1",
                    "author": "user",
                    "text": "one last thing",
                    "attention": True,
                }
            )
            + "\n"
        ).encode()
    )
    events.flush()
    os.fsync(events.fileno())
    fcntl.flock(events, fcntl.LOCK_UN)
    events.close()

    out, err = process.communicate(timeout=STATED_TIMEOUT)
    assert process.returncode == 1, f"{out}{err}"
    assert "1 update nobody has picked up" in err
    assert files_model.read_json(page_dir / "status.json")["state"] == "waiting"


def test_session_end_releases_the_page_and_its_session_server_retires(claimed):
    assert hosting_model.start_server(claimed)  # a real detached server to clean up
    session_model.cmd_waiting(claimed, "")
    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "s1"})
    wait_for(
        lambda: server_model.running_server(claimed),
        lambda running: not running,
        failure="the unclaimed session server stayed up after session end",
    )
    assert files_model.read_json(claimed / "status.json")["state"] == "waiting"
    assert files_model.read_json(claimed / "service.json")["enabled"] is True
    claim = service_model.page_claim(claimed)
    assert claim is not None
    assert claim["released"] is not None
    assert service_model.owned_pages("s1") == []


def test_a_background_jobs_server_lives_as_long_as_the_job(
    page_dir, tmp_path, monkeypatch, dead_pid
):
    """A background job runs each sitting on a worker its daemon retires between
    them, so a claim naming that worker's pid takes the page down an hour after
    every turn. The job's record is the lifetime instead: the page stays held
    and served whatever became of the process that claimed it, and retires when
    the job is deleted — which takes the record and may leave the directory."""
    job = tmp_path / "job"
    job.mkdir()
    cleanup_model.write_json(job / "state.json", {"sessionId": "bg-job"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bg-job")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    assert service_model.claim_page(page_dir)
    assert hosting_model.start_server(page_dir)
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "session"
    assert not reaper_retires(page_dir, monkeypatch)
    assert server_model.running_server(page_dir)
    assert service_model.owned_pages("bg-job") == [page_dir.resolve()]
    assert presence_model.presence(page_dir, [])["session_alive"] is True

    (job / "state.json").unlink()
    assert reaper_retires(page_dir, monkeypatch)
    wait_for(
        lambda: server_model.running_server(page_dir),
        lambda running: not running,
        failure="the background-job server stayed up after its job was deleted",
    )
    assert service_model.owned_pages("bg-job") == []
    assert presence_model.presence(page_dir, [])["session_alive"] is False


def test_a_claim_takes_the_job_lifetime_only_for_the_jobs_own_session(
    page_dir, tmp_path, monkeypatch
):
    """CLAUDE_JOB_DIR is inherited, so a session started under a background job's
    shell tool carries the job's directory while being a process of its own: its
    claim names its pid. A job record that is not there is refused, since a claim
    written on it would be over before the server it licensed came up."""
    job = tmp_path / "job"
    job.mkdir()
    cleanup_model.write_json(job / "state.json", {"sessionId": "the-job"})
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "nested")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["pid"] == os.getpid()
    assert "job" not in service_model.page_claim(page_dir)

    (job / "state.json").unlink()
    with pytest.raises(SystemExit, match="names no job record"):
        service_model.claim_page(page_dir)


def test_a_server_exits_when_its_session_is_hard_killed(
    page_dir, session_process, managed_server
):
    owner = session_process()
    server = managed_server(page_dir, "abandoned", owner.pid)
    owner.terminate()
    owner.wait(timeout=STATED_TIMEOUT)

    server.wait(timeout=STATED_TIMEOUT)
    assert server.returncode == 0, server.stderr.read()
    assert files_model.read_json(page_dir / "service.json")["enabled"] is True
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_a_live_session_can_take_over_an_existing_server(
    page_dir, session_process, managed_server
):
    first, second = session_process(), session_process()
    server = managed_server(page_dir, "first", first.pid)
    record_claim(page_dir, id="second", pid=second.pid, agent="Codex")
    first.terminate()
    first.wait(timeout=STATED_TIMEOUT)
    assert server.poll() is None

    second.terminate()
    second.wait(timeout=STATED_TIMEOUT)
    server.wait(timeout=STATED_TIMEOUT)
    assert server.returncode == 0, server.stderr.read()
    assert files_model.read_json(page_dir / "service.json")["enabled"] is True


def test_server_start_hands_the_page_to_a_process_of_its_own(page_dir):
    """The command returns and the page stays up. Two long-running commands per
    leaf was one accident: `leaf wait` has to exit, its exit being how a comment
    reaches the agent, and the server has to not exit at all — so no one process
    does both, but only the watcher is the session's to hold open. The serve gets
    a session of its own, which is also what leaves a killed background task
    costing the watcher alone."""
    started = start_server_command(page_dir)
    assert started.returncode == 0, started.stderr
    url = json.loads(started.stdout)["url"]
    assert url.startswith("http://127.0.0.1:")
    assert "server   session" in started.stderr
    info = server_model.running_server(page_dir)
    assert info and info["url"] == url
    # The child claims only after its refusal and bind checks, which is what lets
    # the loop's hooks find the session's pages without a failed start taking one.
    assert service_model.page_claim(page_dir)["id"] == "starter"
    service = files_model.read_json(page_dir / "service.json")
    assert service["lifetime"] == "session"
    assert set(service) == {
        "host",
        "bind",
        "port",
        "enabled",
        "lifetime",
        "runtime",
        "server_id",
    }
    assert service["runtime"]["path"] == str(schema_model.PLUGIN_ROOT)
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
    response = urllib.request.urlopen(state)
    assert response.status == 200
    assert response.headers["Leaf-Server"] == service["server_id"]


def test_server_start_forwards_flags_and_returns_service_output(page_dir):
    """`server start` states nothing about a serve itself. The flags go verbatim
    to the service it spawns and the account comes back from there, so the
    lifetime a flag declared and the refusal a running server earns are both that
    process's own words, carried out with its exit status."""
    standing = start_server_command(page_dir, "--standing")
    assert standing.returncode == 0, standing.stderr
    assert "server   standing" in standing.stderr
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "standing"
    assert service_model.page_claim(page_dir) is None

    refused = start_server_command(page_dir, "--host", "devbox.corp.example")
    assert refused.returncode != 0
    assert "already serving at" in refused.stderr
    assert "server stop" in refused.stderr
    # Nothing on stdout, so a caller reading the URL there reads no URL.
    assert not refused.stdout.strip()
    assert service_model.page_claim(page_dir) is None


@pytest.mark.parametrize("lifetime", ["standing", "session"])
def test_init_restarts_a_served_page_onto_the_replacement_contract(
    page_dir, spawn, monkeypatch, lifetime
):
    """Re-vendoring a served page restarts its server under the recorded lifetime
    and URL, onto the new layer, and preserves the active revision contract."""
    publish(page_dir)
    old_plugin = install_payload(page_dir.parent / "old-plugin")
    old_registry = files_model.read_json(page_dir / "registry.json")
    del old_registry["$events"]["kinds"]["comment"]["record"]["properties"]["attempt"]
    cleanup_model.write_json(page_dir / "registry.json", old_registry)
    cleanup_model.write_json(
        old_plugin / "skills" / "leaf" / "assets" / "registry.json", old_registry
    )

    if lifetime == "standing":
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
        monkeypatch.delenv("CLAUDE_PID")
    old_server = spawn(
        [
            # The old plugin's own launcher, so `SKILL_ROOT` resolves into it and
            # this server answers out of the registry there rather than the
            # checkout's.
            old_plugin / "bin" / "leaf",
            "server",
            "run",
            str(page_dir),
            *(["--standing"] if lifetime == "standing" else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = json.loads(old_server.stdout.readline())["url"]
    assert url.startswith("http://127.0.0.1:")
    assert old_server.stderr.readline().startswith(f"server   {lifetime}")
    prior_status = service_model.read_status(page_dir)
    prior_owner = service_model.page_claim(page_dir)

    endpoint = urllib.parse.urlsplit(url)._replace(path="/api/event").geturl()
    comment = {
        "kind": "comment",
        "revision": 1,
        "text": "Can the replacement route this?",
        "attempt": "replacement_route_1",
    }
    status, body = fetch(endpoint, data=json.dumps(comment).encode(), token=None)
    # Editing the mutable layer cannot change admission for captured revision r1.
    assert status == 200, body

    project_layer = page_dir.parent / ".leaf"
    project_layer.mkdir()
    (project_layer / "theme.css").write_text(":root { --accent: red; }\n")
    revendored = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert revendored.exit_code == 0, revendored.output
    assert b":root { --accent: red; }" in (page_dir / "theme.css").read_bytes()
    # The old server went down with the restart, and this checkout's came up in its
    # place at the same URL, under the lifetime and claim it had.
    old_server.wait(timeout=STATED_TIMEOUT)
    assert server_model.running_server(page_dir)["url"] == url
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == lifetime
    assert service_model.page_claim(page_dir) == prior_owner
    restored = service_model.read_status(page_dir)
    assert restored == prior_status

    status, body = fetch(endpoint, data=json.dumps(comment).encode(), token=None)
    assert status == 200, body
    events = events_model.read_events(page_dir)
    assert [event["kind"] for event in events] == ["note", "comment"]
    assert events[-1]["attempt"] == comment["attempt"]


def test_server_stop_disables_desired_state_without_signalling_a_pid(
    page_dir, monkeypatch
):
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": 41000,
            "enabled": True,
            "lifetime": "standing",
        },
    )
    (page_dir / "server.lock").write_bytes(b"")

    def unexpected_signal(*_args):
        pytest.fail("an unlocked record's pid was signalled")

    monkeypatch.setattr(os, "kill", unexpected_signal)

    assert hosting_model.cmd_stop(page_dir) is False
    assert files_model.read_json(page_dir / "service.json")["enabled"] is False


def test_server_stop_reports_a_server_that_exits_as_soon_as_it_is_disabled(
    page_dir, standing_server, monkeypatch
):
    server = standing_server(page_dir)
    write_json = hosting_model.write_json

    def write_and_wait_for_exit(path, value):
        write_json(path, value)
        if path == page_dir / "service.json" and not value["enabled"]:
            wait_for(
                lambda: leases_model.lock_is_held(page_dir / "server.lock"),
                lambda held: not held,
                failure="server did not release its lease after stop",
            )

    monkeypatch.setattr(hosting_model, "write_json", write_and_wait_for_exit)
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)


def test_session_end_cannot_release_a_page_claimed_by_its_successor(page_dir):
    serving(page_dir, 41000, "session")
    record_claim(page_dir, id="predecessor")
    record_claim(page_dir, id="successor")
    session_model.cmd_waiting(page_dir, "successor is reviewing")
    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "predecessor"})
    assert service_model.page_claim(page_dir)["id"] == "successor"
    assert service_model.claim_is_active(service_model.page_claim(page_dir))
    assert files_model.read_json(page_dir / "service.json")["enabled"] is True
    assert (
        files_model.read_json(page_dir / "status.json")["detail"]
        == "successor is reviewing"
    )
    assert server_model.running_server(page_dir)


def test_server_stop_waits_for_the_live_server_to_release_its_lease(
    page_dir, standing_server
):
    server = standing_server(page_dir)
    os.kill(server.pid, signal.SIGSTOP)
    outcomes, errors = [], []

    def stop():
        try:
            outcomes.append(hosting_model.cmd_stop(page_dir))
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)

    stopping = threading.Thread(target=stop)
    stopping.start()
    try:
        wait_for(
            lambda: files_model.read_json(page_dir / "service.json")["enabled"],
            lambda enabled: not enabled,
            failure="server stop never disabled the service",
        )
        returned_while_paused = not stopping.is_alive()
    finally:
        os.kill(server.pid, signal.SIGCONT)
    stopping.join(timeout=STATED_TIMEOUT)
    assert not stopping.is_alive(), "server stop never returned once the server resumed"
    server.wait(timeout=STATED_TIMEOUT)

    assert not returned_while_paused, "server stop returned before lock release"
    assert not stopping.is_alive(), "server stop did not cross the release barrier"
    assert errors == []
    assert outcomes == [True]
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_server_stop_closes_accepted_keep_alive_connections(page_dir, standing_server):
    server = standing_server(page_dir)
    service = files_model.read_json(page_dir / "service.json")
    connection = http.client.HTTPConnection(service["host"], service["port"])
    connection.request("GET", f"/api/state?t={server_model.host_key()}")
    response = connection.getresponse()
    assert response.status == 200
    response.read()
    accepted = connection.sock
    accepted.sendall(
        (
            f"GET /api/state?t={server_model.host_key()} HTTP/1.1\r\n"
            f"Host: {service['host']}\r\n"
        ).encode()
    )

    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)

    accepted.settimeout(STATED_TIMEOUT)
    try:
        accepted.sendall(b"\r\n")
        remainder = accepted.recv(1)
    except OSError:
        remainder = b""
    assert remainder == b""


def test_a_sessionless_server_ignores_a_stale_claim_and_requires_explicit_stop(
    page_dir, dead_pid, standing_server, monkeypatch
):
    record_claim(page_dir, id="old-session", pid=dead_pid, agent="Codex")
    server = standing_server(page_dir)
    assert not reaper_retires(page_dir, monkeypatch)
    assert server.poll() is None, "a manual server inherited the stale session claim"
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)


def test_server_run_standing_declines_the_claim_a_harness_session_offers(
    page_dir, spawn
):
    """`--standing` from inside a harness is the bare-shell statement made
    explicit: the launch declines the claim it could have made, so the server
    records the standing lifetime and the page stays nobody's — no watcher
    thread to stop it when the harness pid goes, no SessionEnd reaper. The harness is
    the suite's own session, which every command here already runs under."""
    process = spawn(
        [
            *LEAF_COMMAND,
            "server",
            "run",
            "--standing",
            str(page_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert json.loads(process.stdout.readline())["url"].startswith("http://127.0.0.1:")
    assert process.stderr.readline().strip() == "server   standing"
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "standing"
    assert service_model.page_claim(page_dir) is None


def test_server_run_temporary_uses_the_browser_harness_boundary(page_dir, spawn):
    """A temporary serve is real HTTP with process-owned lifetime and access.

    It writes neither half of durable delivery: no service for a later wait to revive,
    and no claim for this test's harness session to watch.
    """
    process = spawn(
        [*LEAF_COMMAND, "server", "run", "--temporary", str(page_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = json.loads(process.stdout.readline())["url"]
    assert url.startswith("http://127.0.0.1:")
    assert process.stderr.readline().strip() == (
        "server   temporary (stops with this command)"
    )
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
    assert urllib.request.urlopen(state).status == 200
    assert not (page_dir / "service.json").exists()
    assert service_model.page_claim(page_dir) is None

    process.send_signal(signal.SIGINT)
    _, error = process.communicate(timeout=STATED_TIMEOUT)
    assert process.returncode == 1, error
    assert error.endswith("Aborted!\n")


def test_server_run_standing_refuses_to_adopt_a_session_server(page_dir):
    """A stated lifetime contradicted by the running server is refused with the
    way out named, exactly as a stated `--host` is — not silently ignored."""
    serving(page_dir, 1, "session")
    result = CliRunner().invoke(
        cli_model.cli, ["server", "run", "--standing", str(page_dir)]
    )
    assert result.exit_code != 0
    assert "server stop" in result.output


def test_a_standing_server_outlives_a_session_that_picks_the_page_up(
    page_dir, standing_server, monkeypatch, capsys
):
    """The standing serve, the whole way round: a page kept up across sessions, and a
    session that works on it for an afternoon and goes. Picking a page up earns the
    watch obligation and nothing else, so the session's end must take down neither the
    process it didn't start nor a leaf that outlives it."""
    server = standing_server(page_dir)
    launched = server_model.running_server(page_dir)
    assert files_model.read_json(page_dir / "service.json")["lifetime"] == "standing"

    # A session picks the page up, the way `leaf wait` does.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "later")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir, "")
    # Without this the hook would skip the page for the wrong reason and the test
    # would pass with the bug in: the standing check has to be what spares it.
    assert page_dir in service_model.owned_pages("later")

    # A `server run` of its own finds this one up and reports the lifetime the
    # running server has, not the one this claiming launch would have given it.
    hosting_model.cmd_serve(page_dir)
    served = capsys.readouterr()
    assert json.loads(served.out) == {"url": launched["url"]}
    assert "server   standing" in served.err

    hooks_model.cmd_hook({"hook_event_name": "SessionEnd", "session_id": "later"})

    # The synchronous hook left the standing service enabled and live.
    assert server_model.running_server(page_dir) == launched
    assert files_model.read_json(page_dir / "status.json")["state"] == "waiting"
    assert service_model.page_claim(page_dir)["released"] is not None
    assert page_dir not in service_model.owned_pages("later")
    # Explicit stop crosses that server's release barrier before returning.
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)


def test_state_reports_whether_the_owning_session_still_exists(claimed, dead_pid):
    """The banner's one hard fact: a status.json claim outlives its session, the
    owning pid doesn't."""
    assert page_state(claimed)["session_alive"] is True
    record_claim(claimed, pid=dead_pid)
    assert page_state(claimed)["session_alive"] is False


def test_a_prompt_reopens_the_acknowledged_move_it_carries_into_the_new_turn(
    claimed, capsys
):
    """The prompt hook's reminder is delivery evidence, not only prose.

    An unanswered move acknowledged in an earlier turn enters the next turn through
    additional context. Its receipt and page activity therefore advance to that new
    turn together instead of continuing to report only the turn that ended.
    """
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "still working on it?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    continued(capsys.readouterr().out)
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    )
    assert service_model.page_claim(claimed)["turn_closed"]

    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    prompt = json.loads(capsys.readouterr().out)
    assert asked["id"] in prompt["hookSpecificOutput"]["additionalContext"]
    claim = service_model.page_claim(claimed)
    activity = page_state(claimed)["activity"]
    assert activity["kind"] == "working"
    assert activity["obligations"][0]["stage"] == "picked_up"
    assert activity["obligations"][0]["delivery_turn"] == claim["turn"]
    assert activity["obligations"][0]["condition"] is None


def test_a_settling_reaction_wakes_only_when_it_answers_the_agent(
    page_dir, sessionless, capsys
):
    serving(page_dir, 1)
    publish(page_dir)
    session_model.cmd_waiting(page_dir, "")
    question = thread_model.cmd_comment(page_dir, "", "", "", "Is forty enough?", None)
    quiet = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "token": "shorten"},
    )
    assert quiet["attention"] is False
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == []
    answer = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": question["id"], "token": "keep"},
    )
    assert answer["attention"] is True
    assert session_model.cmd_wait(page_dir) == 0
    payload, _, events = printed(capsys.readouterr().out)
    [shown] = events
    assert shown["id"] == answer["id"] and shown["token"] == "keep"
    assert "answer" not in shown
    assert page_state(page_dir)["pending"] == 1
    delivery_model.receive_delivery(payload["id"])
    assert page_state(page_dir)["pending"] == 0
    restored = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": answer["id"]}
    )
    assert restored["attention"] is True
    ordinary = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": question["id"],
            "text": "No further question.",
        },
    )
    mark = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": ordinary["id"], "token": "keep"},
    )
    assert mark["attention"] is False


def test_a_reaction_holds_no_turn_as_an_unanswered_ask(claimed, capsys):
    """A reaction is a mark, not a question: the agent answers it by acting, so an
    acknowledged one nobody replied to does not hold the turn the way a comment
    does. Nor does an `ok` the user put on the agent's answer hand the thread back
    to the agent — a reaction is not the user speaking. The user's words are."""
    session_model.cmd_waiting(claimed, "")
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "user", "revision": 1, "token": "shorten"},
    )
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    answer = thread_model.cmd_reply(
        claimed,
        asked["id"],
        "because",
        None,
        for_event=asked["id"],
    )
    append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": answer["id"], "token": "keep"},
    )
    receive_through(claimed, last_deliverable_seq(claimed))

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # Words under the answer are the user's last word, and hold the turn as ever.
    append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": answer["id"], "text": "but C?"},
    )
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    continued(capsys.readouterr().out)


def _interaction_prompt_evidence(page, value):
    """Keep complete output, replacing only run-specific identities and times."""
    events = events_model.read_events(page)
    identities = {event["id"]: f"event-{event['seq']}" for event in events}

    def stable(item):
        if isinstance(item, dict):
            return {
                key: "<time>" if key in {"ts", "created_at"} else stable(child)
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [stable(child) for child in item]
        if isinstance(item, str):
            item = item.replace(str(page), "<page>")
            for source, replacement in identities.items():
                item = item.replace(source, replacement)
            return Prose(item) if " " in item or "\n" in item else item
        return item

    return stable(value)


def test_agent_sees_the_complete_interaction_recovery(claimed, capsys, snapshot):
    """The real hook and CLI outputs, from the move's arrival through settlement:
    the Stop hook's watch wakes the session, and the prompt hook of the turn that
    opens hands the move over."""
    page = claimed
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>')
    (page / "index.html").write_text(source)
    publish(page)
    session_model.cmd_waiting(page, "")
    observations = {}

    def hook(name):
        hooks_model.cmd_hook({"hook_event_name": name, "session_id": "s1"})
        output = capsys.readouterr().out
        return json.loads(output) if output else None

    def idle():
        result = CliRunner().invoke(cli_model.cli, ["status", str(page), "idle"])
        return {"exit": result.exit_code, "output": result.output}

    # The turn ends over the page, and its Stop hook watches from here.
    assert hook("Stop") is None
    sent = append_carried_log_record(
        page,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Add the camera first.",
        },
    )
    observations["idle before pickup"] = idle()
    serving(page, 1)
    observations["the watch wakes the session"] = hooks_model.cmd_watch(
        {"hook_event_name": "Stop", "session_id": "s1"}
    )
    # The context is an instruction line, the delivery on the next, then what the
    # turn owes; shown apart so the delivery reads as data.
    context = hook("UserPromptSubmit")["hookSpecificOutput"]["additionalContext"]
    instruction, delivery, *attention = context.split("\n")
    observations["delivered at prompt"] = {
        "instruction": instruction,
        "delivery": json.loads(delivery),
        "attention": "\n".join(attention),
    }
    envelope = json.loads(delivery)
    result = CliRunner().invoke(cli_model.cli, ["delivery", "ack", envelope["id"]])
    assert result.exit_code == 0, result.output
    observations["reader confirms delivery"] = {
        "exit": result.exit_code,
        "output": result.output,
    }
    session = service_model.page_claim(page)
    lease = leases_model.take_lease(leases_model.waiter_lease_path(page, session["id"]))
    assert lease
    try:
        observations["acknowledged at stop"] = hook("Stop")
        observations["idle before answer"] = idle()
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                str(page),
                "--for",
                sent["id"],
                "--text",
                "I will add the camera first.",
            ],
        )
        assert result.exit_code == 0, result.output
        observations["answer"] = (
            json.loads(result.output)
            if result.output.startswith("{")
            else result.output
        )
        observations["answered at stop"] = hook("Stop")
    finally:
        leases_model.release_lease(lease)
    snapshot.check(
        yaml_document(
            "Complete agent-facing outputs through real hooks, wait and response commands.\n"
            "Only page paths, event/delivery identities and timestamps are normalized.\n"
            "A null hook output means the turn can end without a reminder.",
            _interaction_prompt_evidence(
                page,
                json.loads(
                    json.dumps(observations).replace(envelope["id"], "<delivery>")
                ),
            ),
        )
    )


def test_agent_sees_codex_watcher_recovery(codex_claimed_page, capsys, snapshot):
    page = codex_claimed_page
    session_model.cmd_waiting(page, "")
    observations = {}

    def hook():
        hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "codex-thread"})
        output = capsys.readouterr().out
        return json.loads(output) if output else None

    observations["no adapter"] = hook()
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(page, "codex-thread")
    )
    assert lease
    try:
        observations["direct wait still running"] = hook()
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Check this."}
        )
        observations["direct wait has input"] = hook()
        adapter = leases_model.take_lease(
            leases_model.adapter_lease_path("codex-thread")
        )
        assert adapter
        try:
            observations["adapter carries input"] = hook()
        finally:
            adapter.close()
    finally:
        leases_model.release_lease(lease)
    snapshot.check(
        yaml_document(
            "Codex Stop output: no adapter, a direct shell wait, and a live adapter.",
            _interaction_prompt_evidence(page, observations),
        )
    )


@pytest.mark.parametrize(
    ("older_texts", "suggested"),
    [
        pytest.param(["x" * 2000], False, id="one-message-is-too-few"),
        pytest.param(["x" * 1000, "x" * 999], False, id="below-character-threshold"),
        pytest.param(["x" * 1000, "x" * 1000], True, id="two-long-messages"),
        pytest.param(["Earlier detail."] * 3, False, id="three-short-messages"),
        pytest.param(["Earlier detail."] * 4, True, id="four-short-messages"),
    ],
)
def test_summary_suggestions_only_accompany_new_input(claimed, older_texts, suggested):
    publish(claimed)
    root = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": older_texts[0]}
    )
    older = [root]
    for number, text in enumerate(older_texts[1:], start=1):
        older.append(
            append_carried_log_record(
                claimed,
                {
                    "kind": "reply",
                    "author": "agent" if number % 2 else "user",
                    "parent": root["id"],
                    "text": text,
                },
            )
        )
    updates = [
        append_carried_log_record(
            claimed,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root["id"],
                "text": "Checking the rollout details." * 100,
                "ephemeral": True,
            },
        )
        for _ in range(2)
    ]
    previous = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "text": "The newest exchange stays readable." * 100,
        },
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    assert delivery_model.pending_batches("s1") == []

    current = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": root["id"],
            "text": "What do you recommend now?" * 100,
        },
    )
    payload = consume_pending_input("s1")
    [batch] = payload["batches"]
    assert [event["id"] for event in batch["events"]] == [current["id"]]
    [thread] = batch["threads"]
    assert {
        message["id"] for message in thread["messages"] if message.get("ephemeral")
    } == {update["id"] for update in updates}
    assert ("summary_hint" in thread) is suggested
    if suggested:
        assert thread["summary_hint"] == {
            "from": older[0]["id"],
            "through": older[-1]["id"],
        }
        assert previous["id"] != thread["summary_hint"]["through"]
    assert consume_pending_input("s1") is None

    # An answer clears the response obligation even when the agent leaves the
    # optional suggestion alone. It produces no separate summary delivery.
    thread_model.cmd_reply(
        claimed,
        current["id"],
        "Proceed with the rollout.",
        None,
        for_event=current["id"],
    )
    assert delivery_model.pending_batches("s1") == []
    [plan] = hook_carrier_model.read_plans("s1")
    assert not plan.owed
    assert plan.state["activity"]["obligations"] == []


def test_agent_sees_a_real_summary_suggestion(page_dir, capsys, snapshot):
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which rollout?"}
    )
    for number in range(1, 5):
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent" if number % 2 else "user",
                "parent": root["id"],
                "text": f"Rollout consideration {number}.",
            },
        )
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root["id"],
            "text": "What do you recommend now?",
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    payload, _, _ = delivered(capsys)
    envelope = json.loads(json.dumps(payload).replace(payload["id"], "<delivery>"))
    [batch] = envelope["batches"]
    assert batch["threads"][0]["summary_hint"]
    # The event carries the ask as well as the digest, so an agent that reads only
    # what is new can still choose whether to summarize the older discussion.
    [event] = batch["events"]
    assert any("summary_hint" in batch["handling"][h] for h in event["handling"])
    snapshot.check(
        yaml_document(
            "The summary hint from real thread events and the delivery a hook hands the turn.",
            _interaction_prompt_evidence(page_dir, {"delivery": envelope}),
        )
    )


def _watched(page_dir):
    """A claimed page this session watches, so only its debts reach the hooks."""
    session_model.cmd_waiting(page_dir, "")
    session = service_model.page_claim(page_dir)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(page_dir, session["id"])
    )
    assert lease
    return lease


def _stop(capsys):
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    output = capsys.readouterr().out
    return continued(output) if output else None


def _idle(page_dir):
    return CliRunner().invoke(cli_model.cli, ["status", str(page_dir), "idle"])


def test_a_move_the_turn_started_lets_that_turn_end(claimed, capsys):
    """A start on a delivered move is the agent's answer for now: the move reads
    Working, with the start's line beside it. Work longer than a few minutes goes to
    background workers whose results wake a later turn, so the turn that started the
    move may end over it. Holding that turn made agents post a reply saying only what
    the start already said. The start does not carry into the next turn, which
    answers the move or starts it again, and idling still refuses over it: closing
    the page answers nothing."""
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "sketch both?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    # A page task's start names no move, so the move is still not started.
    working(claimed, "sketching both")
    assert "1 acknowledged user move with no answer" in _stop(capsys)
    assert service_model.page_claim(claimed)["turn_closed"] is None

    assert _start(claimed, asked["id"], "sketching both").exit_code == 0
    assert _stop(capsys) is None
    assert service_model.page_claim(claimed)["turn_closed"]
    assert "1 acknowledged user move with no answer" in _idle(claimed).output

    # A worker's result wakes the next turn, whose prompt and Stop name the start
    # an earlier turn wrote, and offer starting it again only because it had one.
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    prompt = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert (
        f"your start on {asked['id']} is older than its pickup"
        in prompt["additionalContext"]
    )
    reason = _stop(capsys)
    assert f"your start on {asked['id']} is older than its pickup" in reason
    assert f"`leaf thread reply <page> --for {asked['id']}`" in reason

    assert _start(claimed, asked["id"], "the second sketch").exit_code == 0
    # A task notification reaching the turn mid-way says nothing about it either.
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    assert _stop(capsys) is None

    # A follow-up in the thread carries its answer now. The start on the message
    # that prompted the work covers it all the same, since the thread's one reply
    # answers both; written before the follow-up's pickup, it holds the turn until the
    # agent starts again.
    follow = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "and C?"},
    )
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    capsys.readouterr()
    consume_pending_input("s1")
    reason = _stop(capsys)
    assert f"`leaf thread reply <page> --for {follow['id']}`" in reason
    assert f"your start on {asked['id']} is older than its pickup" in reason
    assert _start(claimed, follow["id"], "adding C").exit_code == 0
    assert _stop(capsys) is None

    thread_model.cmd_reply(
        claimed, follow["id"], "All three are up.", None, for_event=follow["id"]
    )
    end_work(claimed)
    assert _idle(claimed).exit_code == 0
    leases_model.release_lease(lease)


def test_each_owed_move_in_a_thread_takes_a_start_of_its_own(claimed, capsys):
    """A thread's messages share one reply, but a move on an Ask frozen in one of its
    messages owes an answer of its own, so each is started on its own id. Once their
    replies settle them, a later move in the thread is offered no start in place of
    its answer."""
    assert revisioning_model.activate_source(claimed).error is None
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-options id="thread-region" choose>'
            '<lf-option id="thread-east"><strong>East</strong></lf-option>'
            "</lf-options>",
        },
    )
    for action, detail in (("choose", {"options": ["thread-east"]}), ("answer", {})):
        done = append_command(
            claimed,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "thread-region",
                "action": action,
                "detail": detail,
            },
        )
    follow = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "and West?"},
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    reason = _stop(capsys)
    assert done["id"] in reason and follow["id"] in reason
    assert _start(claimed, follow["id"], "checking West").exit_code == 0
    reason = _stop(capsys)
    assert done["id"] in reason and follow["id"] not in reason
    assert _start(claimed, done["id"], "checking East").exit_code == 0
    assert _stop(capsys) is None

    for move in (done, follow):
        thread_model.cmd_reply(
            claimed, move["id"], "East it is.", None, for_event=move["id"]
        )
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    capsys.readouterr()
    again = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "why?"},
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    reason = _stop(capsys)
    assert f"--for {again['id']}" in reason and "your start" not in reason
    leases_model.release_lease(lease)


def test_a_stop_keeps_the_turn_going_only_for_owed_input(claimed, capsys):
    """Input that arrives as a turn ends goes into that turn when it is owed an
    answer. A resolve owes none, so the turn ends and the input waits for the
    watcher to wake the next one, whose prompt hands it over: holding the turn to
    say a thread closed spent a turn on nothing."""
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    thread_model.cmd_reply(
        claimed, asked["id"], "Because.", None, for_event=asked["id"]
    )
    resolve = append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": asked["id"]}
    )
    assert _stop(capsys) is None
    assert service_model.page_claim(claimed)["turn_closed"]
    assert [
        event["id"]
        for event in service_model.unacknowledged(
            events_model.read_events(claimed),
            files_model.read_json(claimed / "cursor.json")["seq"],
        )
    ] == [resolve["id"]]

    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert resolve["id"] in context["additionalContext"]
    leases_model.release_lease(lease)


def test_the_stop_remedy_names_the_id_its_writer_takes(claimed, capsys):
    """Two consecutive user turns in one thread owe one answer, addressed to the
    newest. The Stop hook names the command that writes it, and that exact command
    is accepted: the thread's id, which is the first message's, is not what
    `--for` takes."""
    lease = _watched(claimed)
    first = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why here?"}
    )
    second = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": first["id"], "text": "and when?"},
    )
    receive_through(claimed, last_deliverable_seq(claimed))

    reason = _stop(capsys)
    [named] = re.findall(r"`leaf thread reply <page> --for ([^`]+)`", reason)
    assert named == second["id"]
    result = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", str(claimed), "--for", named, "--text", "Here, next week."],
    )
    assert result.exit_code == 0, result.output
    assert _stop(capsys) is None
    leases_model.release_lease(lease)


def test_a_page_pick_holds_the_turn_until_the_markup_records_it(claimed, capsys):
    """A pick on a page Ask is owed a version that writes it in. The delivery says
    so, the Stop hook and `idle` hold the agent to it, and the stamped version whose
    markup records the pick settles it — one rule, read by every consumer. An edit
    to a draft that asks nothing is carried by the log and owes nothing: it keeps a
    receipt that reports its delivery, which no count, Stop or `idle` reads, and the
    next version retires it without writing the edit in."""
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>').replace(
        "</section>", '<lf-draft id="note"><pre>Blue room.</pre></lf-draft></section>'
    )
    (claimed / "index.html").write_text(source)
    publish(claimed)
    lease = _watched(claimed)
    edit = append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "note",
            "action": "edit",
            "detail": {"text": "Green room."},
        },
    )
    edited = state_json(claimed)
    [receipt] = edited["workflows"]
    assert (receipt["input"], receipt["stage"], receipt["answer"]) == (
        edit["id"],
        "sent",
        None,
    )
    assert edited["activity"]["obligations"] == []
    assert edited["activity"]["counts"]["total"] == 0
    picked = append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"options": ["backfill-first"]},
        },
    )
    state = state_json(claimed)
    [workflow] = owed(state)
    assert workflow["answer"] == {"kind": "markup", "action": picked["id"]}
    assert state["activity"]["counts"]["total"] == 1

    delivery = delivery_through(claimed, last_deliverable_seq(claimed))
    [batch] = delivery_model.read_delivery(delivery)["batches"]
    [event] = batch["events"]
    assert edit["attention"] is False
    assert event["answer"] == workflow["answer"]
    told = [batch["handling"][ref] for ref in event["handling"]]
    assert any("write it in, and stamp a version" in text for text in told)
    receive_through(claimed, last_deliverable_seq(claimed))

    assert f"records action {picked['id']}" in _stop(capsys)
    refused = _idle(claimed)
    assert refused.exit_code == 1
    assert f"records action {picked['id']}" in refused.output
    # Started as the work the pick selects, it lets the turn end while that work
    # runs, and still owes the version.
    assert _start(claimed, picked["id"], "building it").exit_code == 0
    assert _stop(capsys) is None
    assert f"records action {picked['id']}" in _idle(claimed).output

    (claimed / "index.html").write_text(
        source.replace(
            '<lf-option id="backfill-first">', '<lf-option id="backfill-first" chosen>'
        )
    )
    assert stamp(claimed, "Backfill leads").exit_code == 0
    assert state_json(claimed)["workflows"] == []
    assert _stop(capsys) is None
    assert _idle(claimed).exit_code == 0
    leases_model.release_lease(lease)


@pytest.mark.parametrize("declared", ["shipped", "done-only"])
def test_a_tick_before_done_hands_nothing_to_the_agent(claimed, capsys, declared):
    """A multiple-choice Ask finishes with Done. Until then a tick is the user's
    own unfinished answer: it is not agent work, the banner does not count it as an
    update waiting, no delivery is prepared, and Stop does not
    hold the turn. Done hands the Ask over, and the answer it owes is a version.

    The tick is held because it is a move on a widget whose Ask stands open, not
    because `choose` happens to answer some other group: a layer answering the
    group only by its Done holds the tick the same way."""
    if declared == "done-only":
        registry = files_model.read_json(claimed / "registry.json")
        registry["lf-options"]["x-awaits"]["answered"] = {"answer": {}}
        cleanup_model.write_json(claimed / "registry.json", registry)
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose multiple>')
    (claimed / "index.html").write_text(source)
    publish(claimed)
    lease = _watched(claimed)
    append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"options": ["flag-first"]},
        },
    )
    ticked = state_json(claimed)
    assert [ask["source"] for ask in ticked["asks"]] == ["choice"]
    assert ticked["workflows"] == []
    assert ticked["activity"]["counts"]["total"] == 0
    assert ticked["activity"]["counts"]["pending"] == 0

    assert service_model.unacknowledged(events_model.read_events(claimed), 0) == []
    assert _stop(capsys) is None

    done = append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "answer",
            "detail": {},
        },
    )
    finished = state_json(claimed)
    assert finished["asks"] == []
    [workflow] = owed(finished)
    assert workflow["answer"] == {"kind": "markup", "action": done["id"]}
    delivery = delivery_through(claimed, done["seq"])
    [batch] = delivery_model.read_delivery(delivery)["batches"]
    assert [event["id"] for event in batch["events"]] == [done["id"]]
    leases_model.release_lease(lease)


DECK_PAGE = PAGE.replace(
    "</section>",
    """<lf-ask id="triage-decision"><h3>Which follow-ups should we keep?</h3>
  <lf-swipe-deck id="triage">
    <lf-swipe-pile id="queue" verdict="unseen">
      <lf-swipe-card id="card-a"><strong>Rolling expiry</strong></lf-swipe-card>
      <lf-swipe-card id="card-b"><strong>Bounded fallback</strong></lf-swipe-card>
      <lf-swipe-card id="card-c"><strong>Retry budget</strong></lf-swipe-card>
    </lf-swipe-pile>
    <lf-swipe-pile id="keep" verdict="keep"></lf-swipe-pile>
    <lf-swipe-pile id="pass" verdict="pass"></lf-swipe-pile>
  </lf-swipe-deck>
</lf-ask></section>""",
)


def test_a_finished_deck_owes_every_card_the_user_sorted(page_dir):
    """An Ask's answer can span units: a deck's cards are each swiped, and only the
    swipe that empties the queue answers the Ask. Before it the user is still
    answering and the agent owes nothing; once it lands, every sorted card is owed
    its place in the markup, not only the one that finished the deck."""
    (page_dir / "index.html").write_text(DECK_PAGE)
    publish(page_dir)

    def sort(card, rank):
        return append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "triage",
                "action": "swipe",
                "detail": {"card": card, "to": "keep", "rank": rank},
            },
        )

    sort("card-a", "i")
    sort("card-b", "r")
    assert state_json(page_dir)["workflows"] == []

    sort("card-c", "w")
    owed_cards = sorted(item["coordinate"][1] for item in owed(state_json(page_dir)))
    assert owed_cards == ["card-a", "card-b", "card-c"]


def test_a_deck_in_a_thread_owes_nothing_until_it_is_finished(page_dir):
    """The page's rule holds in thread markup: a swipe that leaves the queue
    standing is the user still answering, so no reply is owed and the Ask stays
    theirs."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Sort these follow-ups.",
            "markup": '<lf-swipe-deck id="triage">'
            '<lf-swipe-pile id="queue" verdict="unseen">'
            '<lf-swipe-card id="card-a"><strong>Rolling expiry</strong></lf-swipe-card>'
            '<lf-swipe-card id="card-b"><strong>Retry budget</strong></lf-swipe-card>'
            "</lf-swipe-pile>"
            '<lf-swipe-pile id="keep" verdict="keep"></lf-swipe-pile>'
            '<lf-swipe-pile id="pass" verdict="pass"></lf-swipe-pile>'
            "</lf-swipe-deck>",
        },
    )

    def sort(card, rank):
        return append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "triage",
                "action": "swipe",
                "detail": {"card": card, "to": "keep", "rank": rank},
            },
        )

    sort("card-a", "i")
    sorting = state_json(page_dir)
    assert sorting["workflows"] == []
    assert [ask["source"] for ask in sorting["asks"]] == ["triage"]

    sort("card-b", "r")
    finished = state_json(page_dir)
    assert finished["asks"] == []
    assert sorted(item["coordinate"][1] for item in owed(finished)) == [
        "card-a",
        "card-b",
    ]


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
        lambda: codex_model.delivery_record_state("codex-thread", payload["id"]),
        lambda state: state == "accepted",
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


def test_an_uncertain_start_without_a_reply_seat_survives_adapter_restart(
    page_dir, app_server, task_connection
):
    """An action delivery has no reply seat that could prevent a duplicate start."""
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
    connection.stop()
    connection = task_connection(endpoint)
    assert connection.start_delivery(prepared.payload)
    assert len(starts) == 1
    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "abandoned"
    )
    path = codex_model.record_path("codex-thread", prepared.payload["id"])
    assert not path.exists()
    archived = path.parent / "history" / path.name
    assert files_model.read_json(archived)["transport"] == {
        "phase": "starting",
        "turn": None,
    }
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
    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "accepted"
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
    record["state"] = "abandoned"
    record["transport"] = {"phase": "starting", "turn": None}
    codex_model.write_record(path, record)
    if manual:
        cleanup_model.prompt_turn("codex-thread", "manual-turn")
        thread_model.cmd_reply(
            page_dir,
            target["reply_to"],
            text="Manual answer",
            markup="",
            for_event=target["responds"],
        )
    assert codex_adapter_model._recover_receipt("codex-thread")
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
    assert codex_adapter_model.read_cursor(page_dir) > 0
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
        thread_model.cmd_resolve(page_dir, target["reply_to"])
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
    record["transport"] = {"phase": "starting", "turn": None}
    codex_model.write_record(path, record)
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
    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "offering"
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
            "status": {"type": "active"},
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
            },
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
                result = {"thread": {"status": {"type": "active"}, "turns": []}}
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
            "status": {"type": "active"},
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
    assert (
        files_model.read_json(page_dir / "status.json")["stream"]["reply"]["text"]
        == "Retained draft"
    )


def test_archived_abandonment_recovers_a_late_final_from_paginated_history(
    page_dir, app_server, task_connection
):
    prepared = _codex_delivery(page_dir)
    codex_model.abandon_uncertain_delivery("codex-thread", prepared.payload)
    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "abandoned"
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
    record["transport"] = {"phase": "starting", "turn": None}
    codex_model.write_record(path, record)
    thread_model.reserve_delivery_reply("codex-thread", prepared.payload["id"], target)
    cleanup_model.prompt_turn("codex-thread", "manual-turn")
    thread_model.cmd_reply(
        page_dir,
        target["reply_to"],
        text="Manual winner",
        markup="",
        for_event=target["responds"],
    )
    # The watcher settles the harness attempt without contacting the provider;
    # prolonged disconnect cannot block later input behind the manual winner.
    assert codex_adapter_model._recover_receipt("codex-thread")
    assert (
        codex_model.delivery_record_state("codex-thread", prepared.payload["id"])
        == "abandoned"
    )
    assert not codex_records("codex-thread")
    newer = _codex_delivery(page_dir, "Next input")
    assert newer.payload["id"] != prepared.payload["id"]
    assert [
        event["text"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ] == ["Manual winner"]


def test_session_lifecycle_is_shared_without_rewriting_page_claims(
    claimed, tmp_path, capsys
):
    """Prompts precede claims; a shared ending and a resumed ID never revive old ownership."""
    hooks_model.cmd_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "turn_id": "provider-turn",
        }
    )
    capsys.readouterr()
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    service_model.claim_page(sibling)
    before = {
        page: service_model.claim_path(page).read_bytes() for page in (claimed, sibling)
    }
    assert {service_model.page_claim(page)["turn"] for page in before} == {
        "provider-turn"
    }
    hooks_model.cmd_hook(
        {"hook_event_name": "Interrupt", "session_id": "s1", "turn_id": "provider-turn"}
    )
    assert all(service_model.page_claim(page)["turn_closed"] for page in before)
    assert {
        page: service_model.claim_path(page).read_bytes() for page in before
    } == before
    cleanup_model.end_session("s1")
    assert not any(
        service_model.claim_is_active(service_model.page_claim(page)) for page in before
    )
    hooks_model.cmd_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "turn_id": "resumed-turn",
        }
    )
    service_model.claim_page(sibling)
    assert service_model.claim_is_active(service_model.page_claim(sibling))
    assert service_model.page_claim(sibling)["turn"] == "resumed-turn"
    assert not service_model.claim_is_active(service_model.page_claim(claimed))
    assert service_model.claim_path(claimed).read_bytes() == before[claimed]
    capsys.readouterr()


def test_cold_session_end_does_not_wait_for_a_page_transaction(claimed):
    """A held page lock cannot consume the harness's three-second SessionEnd deadline.

    The transaction stays held for the whole run, so a SessionEnd that waited on it
    would never return: the suite's hang bound tells the two apart without timing
    the hook on a busy machine."""
    with service_model.PageTransaction(claimed):
        done = subprocess.run(
            [
                sys.executable,
                "-S",
                str(PLUGIN_ROOT / "skills/leaf/scripts/leaf/state.py"),
            ],
            input=json.dumps({"hook_event_name": "SessionEnd", "session_id": "s1"}),
            text=True,
            capture_output=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
        assert not service_model.claim_is_active(service_model.page_claim(claimed))


def test_a_stale_stop_cannot_plan_or_continue_a_newer_turn(claimed, capsys):
    hooks_model.cmd_hook(
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "turn_id": "old"}
    )
    hooks_model.cmd_hook(
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "turn_id": "new"}
    )
    capsys.readouterr()
    events_model.append_event(
        claimed, {"kind": "comment", "author": "user", "text": "for the new turn"}
    )
    before = events_model.read_events(claimed)
    hooks_model.cmd_hook(
        {"hook_event_name": "Stop", "session_id": "s1", "turn_id": "old"}
    )
    assert capsys.readouterr().out == ""
    assert events_model.read_events(claimed) == before
    assert service_model.page_claim(claimed)["turn"] == "new"
    assert service_model.page_claim(claimed)["turn_closed"] is None


def test_hook_snapshot_serializes_receipt_and_reply(claimed, monkeypatch):
    """Receipt/reply cannot cross between the hook's log and cursor reading."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    [batch] = delivery_model.pending_batches("s1")
    projected = hook_carrier_model.full_state
    lock_proved = threading.Event()
    errors = []
    writers = []

    def read_while_settlement_waits(page_dir, events):
        def settle():
            try:
                with open(page_dir / schema_model.EVENTS_FILE, "r+b") as held:
                    try:
                        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        lock_proved.set()
                    else:
                        errors.append(
                            "receipt could enter between hook log and cursor reads"
                        )
                        lock_proved.set()
                delivery_model.receive_one(batch, "s1")
                thread_model.cmd_reply(
                    page_dir,
                    asked["id"],
                    "Because B preserves the invariant",
                    None,
                    for_event=asked["id"],
                )
            except Exception as error:  # noqa: BLE001 - forward worker failures to assertion
                errors.append(error)

        writer = threading.Thread(target=settle, daemon=True)
        writers.append(writer)
        writer.start()
        assert lock_proved.wait(timeout=STATED_TIMEOUT), (
            "the settlement writer never tried the held lock"
        )
        return projected(page_dir, events)

    monkeypatch.setattr(hook_carrier_model, "full_state", read_while_settlement_waits)
    plans = hook_carrier_model.read_plans("s1")
    for writer in writers:
        writer.join(timeout=STATED_TIMEOUT)
        assert not writer.is_alive()
    assert not errors
    assert not plans[0].owed
    assert [event["id"] for event in plans[0].pending] == [asked["id"]]
    with service_model.PageTransaction(claimed) as page:
        assert not projected(claimed, page.events)["activity"]["obligations"]
        assert page.cursor >= asked["seq"]


def test_prompt_pickup_does_not_restamp_a_response_settled_after_planning(claimed):
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Already handled"}
    )
    [batch] = delivery_model.pending_batches("s1")
    delivery_model.receive_one(batch, "s1")
    plans = hook_carrier_model.read_plans("s1")
    assert plans[0].acknowledged
    thread_model.cmd_reply(claimed, asked["id"], "Handled", None, for_event=asked["id"])
    before = events_model.read_events(claimed)
    hook_carrier_model.pick_up_acknowledged("s1", plans)
    assert events_model.read_events(claimed) == before


@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("pending", [False, True])
def test_newer_prompt_supersedes_hook_policy_before_effects(
    claimed, monkeypatch, capsys, named, pending
):
    turn = "provider" if named else None
    cleanup_model.prompt_turn("s1", turn)
    if pending:
        append_carried_log_record(
            claimed, {"kind": "comment", "author": "user", "text": "For the new prompt"}
        )
    policy = hook_carrier_model.stop_continues
    newer = []

    def supersede(plans, *, repeated):
        newer.append(cleanup_model.prompt_turn("s1", turn))
        return policy(plans, repeated=repeated)

    monkeypatch.setattr(hook_carrier_model, "stop_continues", supersede)
    hooks_model.cmd_hook(
        {
            "hook_event_name": "Stop",
            "session_id": "s1",
            **({"turn_id": turn} if turn else {}),
        }
    )
    assert capsys.readouterr().out == ""
    assert cleanup_model.session_record("s1") == newer[0]
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(claimed)
    )
    assert events_model.read_cursor(claimed) == 0


def test_claim_rollback_tracks_acquisition_independently_of_turn(claimed):
    previous = service_model.page_claim(claimed)
    harness = harness_model.session_harness()
    with service_model.PageTransaction(claimed) as page:
        _, expected = page.take_claim(harness)
        cleanup_model.prompt_turn("s1", "provider")
        page.restore_claim(expected, previous)
        assert page.claim["acquisition"] == previous["acquisition"]
        _, first = page.take_claim(harness)
        _, successor = page.take_claim(harness)
        assert first["acquisition"] != successor["acquisition"]
        page.restore_claim(first, previous)
        assert page.claim["acquisition"] == successor["acquisition"]
        incompatible = {
            key: value for key, value in successor.items() if key != "acquisition"
        }
        cleanup_model.write_json(service_model.claim_path(claimed), incompatible)
        page.restore_claim(successor, previous)
        assert page.claim is None
        assert files_model.read_json(service_model.claim_path(claimed)) == incompatible


def test_provider_observation_cannot_replace_a_newer_prompt(claimed):
    cleanup_model.prompt_turn("s1", "old")
    cleanup_model.close_session_turn("s1", "old")
    old = cleanup_model.session_record("s1")
    cleanup_model.prompt_turn("s1", "new")
    new = cleanup_model.session_record("s1")
    assert not codex_model.TurnFold(
        "s1", "old", lifecycle=cleanup_model.session_record("s1")
    ).open()
    assert cleanup_model.session_record("s1") == new
    assert cleanup_model.start_session_turn("s1", "late-start", old) is None
    assert cleanup_model.session_record("s1") == new
    adopted = cleanup_model.start_session_turn("s1", "legitimate-start", new)
    assert adopted["turn"] == "legitimate-start"


def test_hook_publication_never_receipts_input_before_its_reader(
    claimed, tmp_path, monkeypatch, capsys
):
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    service_model.claim_page(sibling)
    capsys.readouterr()
    for page in (claimed, sibling):
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Please answer"}
        )
    # A lock taken after planning would block the former receipt loop after its
    # first write, allowing a harness timeout to discard context already receipted.
    compose = hook_carrier_model.compose
    held = service_model.PageTransaction(sibling)

    def compose_with_locked_receipt_page(batches, attention):
        message = compose(batches, attention)
        held.__enter__()
        return message

    monkeypatch.setattr(hook_carrier_model, "compose", compose_with_locked_receipt_page)
    try:
        hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
        context = continued(json.loads(capsys.readouterr().out))
        envelope = json.loads(context.split("\n")[1])
        assert len(envelope["batches"]) == 2
        assert all(events_model.read_cursor(page) == 0 for page in (claimed, sibling))
    finally:
        held.__exit__(None, None, None)
    # Discard the first output just as the harness does on timeout. A later prompt
    # publishes the same input; only its reader's exact ack advances cursors.
    monkeypatch.setattr(hook_carrier_model, "compose", compose)
    hooks_model.cmd_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    retry = json.loads(
        json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ].split("\n")[1]
    )
    assert [
        [event["id"] for event in batch["events"]] for batch in retry["batches"]
    ] == [[event["id"] for event in batch["events"]] for batch in envelope["batches"]]
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", retry["id"]]).exit_code
        == 0
    )
    assert all(events_model.read_cursor(page) > 0 for page in (claimed, sibling))


@pytest.mark.parametrize("turn_id", [None, "provider-turn"])
def test_reader_ack_refuses_a_closed_turn_without_reopening_it(
    claimed, turn_id, capsys
):
    cleanup_model.prompt_turn("s1", turn_id)
    event = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    envelope = json.loads(continued(capsys.readouterr().out).split("\n")[1])
    cleanup_model.close_session_turn("s1", turn_id)
    closed = cleanup_model.session_record("s1")
    refused = CliRunner().invoke(cli_model.cli, ["delivery", "ack", envelope["id"]])
    assert refused.exit_code != 0
    assert cleanup_model.session_record("s1") == closed
    assert events_model.read_cursor(claimed) < event["seq"]
    assert not any(e["kind"] == "pickup" for e in events_model.read_events(claimed))
    # A real subsequent harness prompt admits the same immutable input to its reader.
    cleanup_model.prompt_turn("s1", "next-provider" if turn_id else None)
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", envelope["id"]]).exit_code
        == 0
    )
    assert events_model.read_cursor(claimed) == event["seq"]


def test_reader_ack_commits_pickup_and_cursor_before_session_end(
    claimed, monkeypatch, capsys
):
    event = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "s1"})
    envelope = json.loads(continued(capsys.readouterr().out).split("\n")[1])
    attempting = threading.Event()
    ended = threading.Event()

    def end():
        attempting.set()
        cleanup_model.end_session("s1")
        ended.set()

    thread = threading.Thread(target=end)
    pickup = delivery_model.record_pickup

    def pickup_while_end_attempts(*args, **kwargs):
        thread.start()
        assert attempting.wait(STATED_TIMEOUT), (
            "the session end never attempted its lock"
        )
        # Observe the actual lock ownership, rather than relying on scheduling
        # an end call to happen before this short receipt transaction completes.
        with (
            open(cleanup_model.session_lock_path("s1"), "a+") as lock,
            pytest.raises(BlockingIOError),
        ):
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not ended.is_set()
        assert cleanup_model.session_record("s1")["ended"] is None
        return pickup(*args, **kwargs)

    monkeypatch.setattr(delivery_model, "record_pickup", pickup_while_end_attempts)
    accepted = CliRunner().invoke(cli_model.cli, ["delivery", "ack", envelope["id"]])
    thread.join(STATED_TIMEOUT)
    assert not thread.is_alive(), "the session end never finished"
    assert accepted.exit_code == 0, accepted.output
    assert ended.is_set()
    assert events_model.read_cursor(claimed) == event["seq"]
    assert (
        CliRunner().invoke(cli_model.cli, ["delivery", "ack", envelope["id"]]).exit_code
        != 0
    )


def test_no_page_stop_cannot_close_a_prompt_that_arrives_during_discovery(monkeypatch):
    newer = []

    def pages(_sid):
        newer.append(cleanup_model.prompt_turn("never-claimed"))
        return []

    monkeypatch.setattr(hooks_model, "owned_pages", pages)
    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "never-claimed"})
    assert cleanup_model.session_record("never-claimed") == newer[0]


@pytest.mark.parametrize("resumed", [False, True])
def test_first_claim_enriches_prompt_provenance_without_replacing_it(
    page_dir, monkeypatch, resumed
):
    if resumed:
        old = cleanup_model.ensure_session("before-claim", {"pid": os.getpid() + 1})
        cleanup_model.end_session("before-claim")
    before = cleanup_model.prompt_turn("before-claim", "provider")
    assert before["lifetime"] == {}
    if resumed:
        assert before["generation"] != old["generation"]
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "before-claim")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    after = cleanup_model.session_record("before-claim")
    assert (after["generation"], after["turn"], after["provider"]) == (
        before["generation"],
        "provider",
        True,
    )
    assert after["lifetime"] == {"pid": os.getpid()}


def test_closed_provider_prompt_never_reopens_its_identity(claimed, capsys):
    cleanup_model.prompt_turn("s1", "completed")
    cleanup_model.close_session_turn("s1", "completed")
    ended = cleanup_model.session_record("s1")
    hooks_model.cmd_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "turn_id": "completed",
        }
    )
    assert cleanup_model.session_record("s1") == ended
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("existing_fold", [False, True])
def test_observer_rejects_stale_running_snapshot(existing_fold, claimed):
    cleanup_model.prompt_turn("s1", "old")
    observer = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "s1")
    if existing_fold:
        observer._read(
            {
                "method": "turn/started",
                "params": {"threadId": "s1", "turn": {"id": "old"}},
            }
        )
    cleanup_model.prompt_turn("s1", "new")
    cleanup_model.close_session_turn("s1", "new")
    current = cleanup_model.session_record("s1")
    observer._resume(
        {
            "status": {"type": "active"},
            "turns": [{"id": "old", "status": "inProgress", "items": []}],
        }
    )
    assert observer.running is None
    assert cleanup_model.session_record("s1") == current


def test_observer_continues_after_a_recovered_provider_completion(claimed):
    cleanup_model.prompt_turn("s1", "old")
    observer = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "s1")
    observer._read(
        {"method": "turn/started", "params": {"threadId": "s1", "turn": {"id": "old"}}}
    )
    observer._resume(
        {
            "status": {"type": "idle"},
            "turns": [{"id": "old", "status": "completed", "items": []}],
        }
    )
    assert cleanup_model.session_record("s1")["turn_closed"] is not None
    observer._read(
        {"method": "turn/started", "params": {"threadId": "s1", "turn": {"id": "next"}}}
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
                "turn": {"id": "old-turn"},
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
                                    "turn": {"id": "new-turn"},
                                },
                            }
                        )
                    )
                else:
                    cleanup_model.prompt_turn("codex-thread", "new-turn")
                    with service_model.PageTransaction(page_dir) as page:
                        page.set_status("waiting", "New turn")
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
        status_before = service_model.PageTransaction(page_dir).status
        connection._resume(thread, expected)
    assert cleanup_model.session_record("codex-thread") == winner
    assert winner["turn"] == "new-turn"
    assert connection.running == (
        "new-turn" if replacement == "provider_notification" else None
    )
    if replacement == "provider_notification":
        assert connection.turns["new-turn"].events.waiting_kind is None
    else:
        assert service_model.PageTransaction(page_dir).status == status_before


def test_stale_live_notifications_cannot_reuse_a_fold_after_a_newer_prompt(page_dir):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old-turn")
    connection = _observer()
    connection._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "old-turn"},
            },
        }
    )
    cleanup_model.prompt_turn("codex-thread", "new-turn")
    winner = cleanup_model.session_record("codex-thread")
    for method, params in [
        ("turn/started", {"turn": {"id": "old-turn"}}),
        (
            "item/commandExecution/requestApproval",
            {"turnId": "old-turn", "itemId": "old-approval"},
        ),
    ]:
        connection._read(
            {"method": method, "params": {"threadId": "codex-thread", **params}}
        )
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
                    "turn": {"id": turn_id},
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
            "params": {"threadId": "codex-thread", "turn": {"id": "first-turn"}},
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
            "params": {"threadId": "codex-thread", "turn": {"id": "second-turn"}},
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
                "params": {"threadId": "codex-thread", "turn": {"id": "old-turn"}},
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
        page.set_status("waiting", "New generation")
    codex_model.set_stream_activity(
        "codex-thread",
        "same-turn",
        {"kind": "tool", "detail": "New generation activity"},
        expected=cleanup_model.session_record("codex-thread"),
    )
    winner = cleanup_model.session_record("codex-thread")
    status = service_model.PageTransaction(page_dir).status
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
                    },
                },
            }
        )
    assert cleanup_model.session_record("codex-thread") == winner
    assert service_model.PageTransaction(page_dir).status == status


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
            page.set_status("waiting", "New turn")
        codex_model.set_stream_activity(
            "codex-thread",
            "new-turn",
            {"kind": "tool", "detail": "New activity"},
            expected=cleanup_model.session_record("codex-thread"),
        )
    else:
        cleanup_model.close_session_turn("codex-thread", "old-turn")
        fold.clear_activity()
    status = service_model.PageTransaction(page_dir).status
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
                },
            },
        }
    )
    assert service_model.PageTransaction(page_dir).status == status
    assert cleanup_model.session_record("codex-thread") == epoch


def test_a_rejected_started_fold_cannot_publish_initial_working_activity(
    page_dir, app_server, monkeypatch
):
    _codex_delivery(page_dir)
    connection = _observer()
    path, record = codex_model.delivery_records("codex-thread")[0]
    offered = codex_model.offer_delivery(path, record, "app-server")
    codex_model.write_record(offered.record_path, record)
    construct = connection._fold
    winner = {}

    def supersede_before_construction(turn_id, delivery_id, **scope):
        cleanup_model.end_session("codex-thread")
        cleanup_model.prompt_turn("codex-thread", turn_id)
        with service_model.PageTransaction(page_dir) as page:
            page.take_claim(
                harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
            )
            page.set_status("waiting", "New generation")
        codex_model.set_stream_activity(
            "codex-thread",
            turn_id,
            {"kind": "tool", "detail": "New activity"},
            expected=cleanup_model.session_record("codex-thread"),
        )
        winner["epoch"] = cleanup_model.session_record("codex-thread")
        winner["status"] = service_model.PageTransaction(page_dir).status
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
    assert service_model.PageTransaction(page_dir).status == winner["status"]


def test_fresh_resume_replaces_a_fold_from_an_earlier_session_generation(page_dir):
    _codex_delivery(page_dir)
    cleanup_model.prompt_turn("codex-thread", "same-turn")
    connection = _observer()
    connection._read(
        {
            "method": "turn/started",
            "params": {"threadId": "codex-thread", "turn": {"id": "same-turn"}},
        }
    )
    old = connection.turns["same-turn"]
    cleanup_model.end_session("codex-thread")
    cleanup_model.prompt_turn("codex-thread", "same-turn")
    with service_model.PageTransaction(page_dir) as page:
        page.take_claim(
            harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
        )
        page.set_status("waiting", "New generation")
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
    assert (
        service_model.PageTransaction(page_dir).status["stream"]["activity"]["detail"]
        == "New activity"
    )
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
