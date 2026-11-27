"""The Codex adapter and the delivery records it shares with Codex's hooks:
capturing a page's input, offering it through `codex queue`, an App Server turn,
or a tool or Stop hook, receipting it on each page, recovering after a restart,
and the adapter process's lifetime."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from xml.etree import ElementTree

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    PAGE,
    PLUGIN_ROOT,
    STATED_TIMEOUT,
    _delivery_item,
    acknowledged_through,
    append_carried_log_record,
    codex_records,
    declare_idle,
    declared,
    owed_answers,
    page_state,
    publish,
    release_codex_command,
    release_held,
    spawn_probe,
    stamp,
    wait_for,
)
from model.test_codex_adapter import (
    adapter_log,
    claim_command,
    codex_start_announcement,
    current_codex_record,
    fake_codex_cli,
)

from leaf.agents import codex as codex_model
from leaf.agents import codex_adapter as codex_adapter_model
from leaf.agents import codex_state as codex_state_model
from leaf.agents import delivery as delivery_model
from leaf.agents import thread as thread_model
from leaf.base import files as files_model
from leaf.base import leases as leases_model
from leaf.base import server as server_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.commands import codex_run as codex_run_model
from leaf.commands import hooks as hooks_model
from leaf.commands import session as session_model
from leaf.log import event_log as events_model
from leaf.records import transaction as transaction_model


@pytest.mark.parametrize("reclaimed", ["delivered", "another"])
def test_codex_app_server_restart_finishes_an_accepted_batch_without_starting_it_again(
    codex_claimed_page, app_server, under_codex, codex_env, tmp_path, reclaimed
):
    """The App Server twin of the queue case,
    `test_codex_restart_finishes_an_accepted_batch_without_queueing_again`. The
    restarted adapter reads back the turn
    that took the delivery while the page's claim still names the task's
    previous generation, before the restart claims it again, or when the restart
    claims another page first. The batch's receipt and the turn's final answer both
    land on the page all the same, so the comment is not started a second time."""
    page = codex_claimed_page
    claimed = page
    if reclaimed == "another":
        claimed = tmp_path / "another-page"
        subprocess.run(
            [*LEAF_COMMAND, "page", "init", claimed], env=codex_env, check=True
        )
    # The turn's answer is a reply, which needs a valid page to land on.
    (page / "index.html").write_text(PAGE, encoding="utf-8")
    publish(page)
    program, _log = fake_codex_cli(tmp_path)
    append_carried_log_record(
        page,
        {"kind": "comment", "id": "accepted", "author": "user", "text": "hi"},
    )
    delivered = events_model.read_events(page)[-1]
    session_model.cmd_waiting(page)
    with transaction_model.PageTransaction(page) as transaction:
        assert codex_adapter_model.capture_batch(
            "codex-thread", transaction, [delivered]
        )
    record_path, record = current_codex_record("codex-thread")
    record_2 = codex_model.read_record(record_path)
    assert isinstance(record_2, (codex_model.Collecting, codex_model.Offering))
    prepared = codex_model.offer_delivery(record_path, record_2, transport="app-server")
    record = codex_model.RECORD.read(record_path)
    assert record is not None
    record.update(
        state="opened", turn="taken", pending=list(range(len(record["batches"])))
    )
    codex_model.RECORD.write(record_path, record)
    starts = []

    def handle(socket):
        for raw in socket:
            request = json.loads(raw)
            method = request.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "thread/resume":
                turns = [
                    {
                        "id": "taken",
                        "status": "completed",
                        "items": [
                            _delivery_item(prepared.payload),
                            {
                                "id": "answer",
                                "type": "agentMessage",
                                "phase": "final_answer",
                                "text": "Answered before the restart",
                            },
                        ],
                    }
                ]
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
            elif method == "thread/turns/list":
                socket.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {"data": [], "nextCursor": None},
                        }
                    )
                )
            elif method == "turn/start":
                starts.append(request)
                socket.send(
                    json.dumps(
                        {"id": request["id"], "result": {"turn": {"id": "again"}}}
                    )
                )

    endpoint = app_server(handle)
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(claim_command(claimed, program, endpoint=endpoint)),
        codex_env | {"CODEX_THREAD_ID": "codex-thread"},
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    release_codex_command(claimed, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    assert started.returncode == 0, f"{out}{err}"

    try:
        wait_for(
            lambda: [
                event["text"]
                for event in events_model.read_events(page)
                if event["kind"] == "reply"
            ],
            lambda replies: replies == ["Answered before the restart"],
            failure="the restarted turn's answer did not reach the page",
        )
        wait_for(
            lambda: acknowledged_through(page),
            lambda cursor: cursor == delivered["seq"],
            failure="the accepted delivery cursor was not recovered",
        )
        assert starts == []
    finally:
        for held in {page, claimed}:
            declare_idle(held)
        cleanup_model.end_session("codex-thread")
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after releasing its page",
    )


def test_codex_delivery_outlives_the_starting_command_and_acknowledges(
    codex_claimed_page, under_codex, codex_env, tmp_path, capsys
):
    """Its first queue call fails after Codex may have taken the message, so the
    adapter offers the same delivery again before going on to the later ones."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page)
    environment = codex_env | {
        "CODEX_THREAD_ID": "codex-thread",
        "FAKE_CODEX_LOG": str(log),
        "FAKE_CODEX_EXPECT_CWD": str(cleanup_model.state_home()),
        "FAKE_CODEX_QUEUE_FAILURE_ONCE": str(tmp_path / "uncertain-queue-response"),
    }
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(claim_command(page, program)),
        environment,
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # The fake Codex wrapper models one shell command, while a real task's Codex
    # ancestor remains alive. Keep that already-proven lifetime in place so this
    # test can isolate the adapter after its starting shell is gone.
    # Transfer the claim while that ancestor is still alive.
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        bool,
        failure="the Codex adapter did not start",
    )
    announcement = codex_start_announcement(started)
    claim = service_model.page_claim(page)
    before_release = cleanup_model.session_record("codex-thread")
    release_codex_command(page, started, finished)
    after_release = cleanup_model.session_record("codex-thread")
    claim_record = service_model.page_claim(page)
    assert claim_record is not None
    assert claim is not None
    assert claim_record["generation"] == claim["generation"]
    assert after_release is not None
    assert before_release is not None
    assert after_release["generation"] == before_release["generation"]
    assert after_release["turn"] == before_release["turn"]
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    out = announcement + out
    assert started.returncode == 0, f"{out}{err}"
    assert json.loads(out)["session"] == "codex-thread"
    try:
        wait_for(
            lambda: (
                codex_adapter_model.adapter_is_live("codex-thread"),
                page_state(page)["listening"],
            ),
            all,
            failure="the Codex adapter did not become live and listening",
        )

        claim_record_2 = service_model.page_claim(page)
        assert claim_record_2 is not None
        assert claim_record_2["turn_closed"] is None
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "hello adapter"}
        )
        comments = [events_model.read_events(page)[-1]]
        wait_for(
            lambda: acknowledged_through(page),
            lambda cursor: cursor == comments[0]["seq"],
            failure=lambda: (
                "the adapter did not acknowledge its batch: "
                f"deliveries={codex_records('codex-thread')!r}; "
                f"log={adapter_log('codex-thread')!r}"
            ),
        )

        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        assert capsys.readouterr().out == ""

        hooks_model.cmd_hook(
            "codex",
            {"hook_event_name": "UserPromptSubmit", "session_id": "codex-thread"},
        )
        assert capsys.readouterr().out == ""
        assert [(item["state"], item["seen"]) for item in owed_answers(page)] == [
            ("waiting", True)
        ]
        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        reason = json.loads(capsys.readouterr().out)["reason"]
        assert "1 acknowledged user update with no answer" in reason

        # The blocked Stop kept this turn running. Answer the update and let the
        # turn end before testing that a later delivery starts on the same adapter.
        def answer(comment, text):
            response = next(
                key
                for key, expected in delivery_model.current_responses(
                    page, events_model.read_events(page)
                ).items()
                if expected["kind"] == "reply" and expected["parent"] == comment["id"]
            )
            thread_model.post_reply(page, {"responds": response}, text)

        answer(comments[0], "The prototype is ready.")
        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        assert capsys.readouterr().out == ""

        for text in ("second click", "third click"):
            append_carried_log_record(
                page, {"kind": "comment", "author": "user", "text": text}
            )
            comments.append(events_model.read_events(page)[-1])
        wait_for(
            lambda: acknowledged_through(page),
            lambda cursor: cursor == comments[-1]["seq"],
            failure="the cursor did not reach the later delivery",
        )

        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert calls[0] == ["queue", "--help"]
        queued = [call for call in calls if "--thread" in call]
        assert len(queued) == 4
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
            payload_path = delivery_model.DELIVERY.file(
                delivery_model.delivery_path(delivery.attrib["id"])
            )
            assert payload_path.exists()
            payload = files_model.read_json(payload_path)
            assert payload["format"] == delivery_model.DELIVERY.format
            assert all(
                set(batch)
                == {"page", "claim", "through_seq", "threads", "handling", "events"}
                for batch in payload["batches"]
            )
            queue_history = codex_model.RECORD.file(
                codex_state_model.delivery_dir("codex-thread")
                / "history"
                / f"{delivery.attrib['id']}.json"
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
            assert queue["state"] == "queued"
            assert queue["pending"] == []
            payloads.append(payload)
            assert len(prompt.encode()) < 1024
        assert [
            event["id"]
            for payload in payloads
            for batch in payload["batches"]
            for event in batch["events"]
        ] == [comment["id"] for comment in comments]
        assert acknowledged_through(page) == comments[-1]["seq"]
        assert codex_adapter_model.adapter_is_live("codex-thread")

        for comment in comments[1:]:
            answer(comment, "received")
        declare_idle(page)
    finally:
        cleanup_model.end_session("codex-thread")

    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after finishing its deliveries",
    )


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
    session_model.cmd_waiting(first)
    start_lock = codex_adapter_model.adapter_start_lock_path("codex-thread")
    read_gate = tmp_path / "adapter-read-gate"
    os.mkfifo(read_gate)
    reading = tmp_path / "adapter-reading"
    marker = tmp_path / "adapter-final-recheck"
    probe = """\
from leaf.agents import codex_state as codex_state_model
from leaf.commands import codex_run as codex_run_model

native_read_watch_pass = codex_run_model.read_watch_pass
native_flocked = codex_run_model.flocked
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

codex_run_model.read_watch_pass = observed_read_watch_pass
codex_run_model.flocked = observed_flocked
raise SystemExit(codex_run_model.run_adapter(os.environ["CODEX_PATH"]))
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
    persistent = subprocess.run(
        [*LEAF_COMMAND, "server", "start", second, "--lifetime", "persistent"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(persistent.stdout)["url"].startswith("http://127.0.0.1:")
    session_model.cmd_waiting(second)
    starter = None
    finished = tmp_path / "second-start-finished"
    starter_ready = tmp_path / "second-start-lock"
    start_program = """\
import contextlib, json, os, sys
from pathlib import Path
from leaf.agents import codex_adapter
from leaf.pages.hosting import cmd_claim
native_flocked = codex_adapter.flocked
@contextlib.contextmanager
def observed_flocked(path):
    if Path(path).resolve() == Path(sys.argv[3]).resolve():
        Path(sys.argv[4]).write_text("requested")
    with native_flocked(path) as held:
        yield held
codex_adapter.flocked = observed_flocked
os.environ["PATH"] = str(Path(sys.argv[2]).parent) + os.pathsep + os.environ["PATH"]
print(json.dumps(cmd_claim(Path(sys.argv[1]))), flush=True)
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
        cleanup_model.end_session("codex-thread")
        subprocess.run([*LEAF_COMMAND, "server", "stop", second], check=True)

    out, err = adapter.communicate(timeout=STATED_TIMEOUT)
    assert adapter.returncode == 0, f"{out}{err}"


import socket
import threading

import pytest
from click.testing import CliRunner
from conftest import CLAUDE_IDENTITY
from interact_support import (
    _observer,
    acknowledge_through,
    activity_reading,
    available_loopback_port,
    fetch,
    read_record,
    record_claim,
    refused_on,
    vendored_at_another_protocol,
    working,
    write_record,
)
from model.test_codex_adapter import spawn_codex_adapter
from websockets.exceptions import WebSocketException

from leaf.base.refusals import Refused
from leaf.commands import cli as cli_model
from leaf.pages import hosting as hosting_model
from leaf.pages import vendoring as vendoring_model


def test_a_new_codex_adapter_observes_ordinary_turns_without_a_prior_hook(
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
                        "turn": {
                            "id": "ordinary-turn",
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
                        "turnId": "ordinary-turn",
                        "startedAtMs": 1000,
                        "item": {
                            "id": "ordinary-command",
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
        if not finish.wait(timeout=STATED_TIMEOUT):
            return
        socket.send(
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "codex-thread",
                        "turn": {
                            "id": "ordinary-turn",
                            "items": [],
                            "status": "completed",
                        },
                    },
                }
            )
        )
        for _raw in socket:
            pass

    assert cleanup_model.session_record("codex-thread") is None
    endpoint = app_server(handle)
    program, _log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page_dir)
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(claim_command(page_dir, program, endpoint=endpoint)),
        codex_env | {"CODEX_THREAD_ID": "codex-thread"},
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        announcement = codex_start_announcement(started)
        claim = service_model.page_claim(page_dir)
        assert claim is not None
        generation = claim["generation"]
        begin.set()
        observed = wait_for(
            lambda: read_record(page_dir / "stream.json"),
            lambda stream: (
                stream is not None
                and (stream["activity"] or {}).get("detail")
                == "Running uv run pytest tests"
            ),
            failure="the newly subscribed adapter did not project ordinary provider activity",
        )
        assert observed["activity"]["turn"] == "ordinary-turn"
        current = service_model.page_claim(page_dir)
        assert current is not None
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
        cleanup_model.end_session("codex-thread")
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the adapter did not retire after its page was released",
    )


def test_codex_retires_a_receipt_on_a_page_its_leaf_cannot_write(codex_claimed_page):
    """A Codex receipt on a page vendored at another protocol retires its batch, as
    one whose page went or changed hands does, rather than failing every retry: the
    input stays unpicked on the page, so a Leaf that can write it delivers it again
    once `leaf page init` re-vendors the page."""
    page = codex_claimed_page
    append_carried_log_record(
        page, {"kind": "comment", "id": "asked", "author": "user", "text": "Why?"}
    )
    (event,) = events_model.read_events(page)[-1:]
    with transaction_model.PageTransaction(page) as transaction:
        batch = delivery_model.batch_data(page, transaction, [event])
    delivery_model.freeze_delivery([batch], delivery_id="bbbbbbbbbbbbbbbb")
    directory = codex_state_model.delivery_dir("codex-thread")
    directory.mkdir(parents=True)
    codex_model.RECORD.write(
        directory / "bbbbbbbbbbbbbbbb.json",
        {
            "state": "queued",
            "created_at": 1,
            "pending": [0],
            "batches": [
                {
                    "page": str(page),
                    "session": "codex-thread",
                    "threads": [],
                    "events": [event],
                }
            ],
        },
    )
    vendored_at_another_protocol(page)

    assert codex_model.recover_codex_receipt("codex-thread")
    assert not codex_model.recover_codex_receipt("codex-thread")
    assert not [
        recorded
        for recorded in events_model.read_events(page)
        if recorded["kind"] == "pickup"
    ]
    assert acknowledged_through(page) < event["seq"]


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
            "state": "queued",
            "created_at": created_at,
            "pending": [0],
            "batches": [
                {
                    "page": str(page),
                    "session": "codex-thread",
                    "threads": [],
                    "events": [event],
                }
            ],
        }

    # Filename order is deliberately opposite to event order. The cursor is
    # monotonic, so taking receipt for the second batch first would hide the
    # first batch before its pickup record is written.
    for identity, event in (("ffffffffffffffff", first), ("aaaaaaaaaaaaaaaa", second)):
        with transaction_model.PageTransaction(page) as transaction:
            batch = delivery_model.batch_data(page, transaction, [event])
        delivery_model.freeze_delivery([batch], delivery_id=identity)
    codex_model.RECORD.write(
        directory / "ffffffffffffffff.json", epoch(first, created_at=1)
    )
    codex_model.RECORD.write(
        directory / "aaaaaaaaaaaaaaaa.json", epoch(second, created_at=2)
    )

    acknowledge_through(page, second["seq"])
    assert codex_model.recover_codex_receipt("codex-thread")
    assert codex_model.recover_codex_receipt("codex-thread")
    pickups = [
        event for event in events_model.read_events(page) if event["kind"] == "pickup"
    ]
    assert [pickup["events"] for pickup in pickups] == [["first"], ["second"]]


def test_an_uncertain_app_server_start_recovers_by_delivery_identity(
    codex_claimed_page,
    monkeypatch,
):
    page = codex_claimed_page
    comment = append_carried_log_record(
        page,
        {"kind": "comment", "id": "user-message", "author": "user", "text": "hi"},
    )
    with transaction_model.PageTransaction(page) as transaction:
        assert codex_adapter_model.capture_batch(
            "codex-thread", transaction, [events_model.read_events(page)[-1]]
        )

    attempted = []
    observer = _observer()

    def start_delivery(payload):
        session_id = "codex-thread"
        attempted.append(payload)
        # The reply an uncertain start reserved stays reserved, because a turn
        # carrying this delivery may be running.
        stream_reply_target_result = codex_model.stream_reply_target(payload)
        assert stream_reply_target_result is not None
        thread_model.reserve_delivery_reply(
            session_id, payload["id"], stream_reply_target_result
        )
        raise codex_model.AppServerDeliveryUncertain("lost acknowledgement")

    monkeypatch.setattr(observer, "start_delivery", start_delivery)
    with pytest.raises(
        codex_model.AppServerDeliveryUncertain, match="lost acknowledgement"
    ):
        codex_adapter_model.offer_queued_delivery(
            "codex",
            "codex-thread",
            observer,
        )

    [payload] = attempted
    [(path, queue)] = codex_records("codex-thread")
    assert queue["state"] == "offering"
    with pytest.raises(Refused) as refused:
        thread_model.post_reply(
            page,
            {"parent": comment["id"], "responds": comment["id"]},
            "Competing reply",
            identity={"agent": "Codex", "session": "codex-thread"},
        )
    assert refused_on(refused.value).code == "reserved-answer"
    monkeypatch.setattr(
        codex_adapter_model,
        "queue_delivery",
        lambda *_: pytest.fail("an observed uncertain delivery entered a local queue"),
    )
    with pytest.raises(
        codex_model.AppServerDeliveryUncertain,
        match="awaiting reconciliation",
    ):
        codex_adapter_model.offer_queued_delivery("codex", "codex-thread", None)

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
    history = codex_model.RECORD.file(path.parent / "history" / path.name)
    recovered = files_model.read_json(history)
    assert recovered["state"] == "opened"
    assert recovered["pending"] == []
    # The recovered turn had ended, so recording it opens and closes nothing.
    assert service_model.page_claim(page) == claim
    accepted = thread_model.post_reply(
        page,
        {"parent": comment["id"], "responds": comment["id"]},
        "Recovered outside the failed provider turn",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    assert accepted["text"] == "Recovered outside the failed provider turn"


def test_a_connection_failure_in_the_delivery_loop_is_retried(
    codex_claimed_page, monkeypatch
):
    """The delivery loop survives every class its own connections can raise.

    A delivery opens a connection of its own inside this loop, and `websockets`
    raises `WebSocketException`, which descends from `Exception` alone. Naming the
    classes worth retrying would let a refused handshake end the adapter and strand
    every page it claims, which is the one thing an adapter exists not to do.
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

    monkeypatch.setattr(codex_model, "recover_codex_receipt", recover_receipt)
    monkeypatch.setattr(codex_run_model, "owned_pages", lambda _session: [])
    monkeypatch.setattr(codex_run_model, "check_queue_command", lambda _path: None)
    monkeypatch.setattr(codex_run_model, "retry_delay", lambda _failures: 0)

    assert codex_run_model.run_adapter("codex") == 0
    assert attempts == ["codex-thread", "codex-thread"]


def test_a_clean_delivery_pass_starts_the_retry_ladder_again(
    codex_claimed_page, monkeypatch
):
    """A failure after a pass that raised nothing waits as a first failure does.

    An ordinary idle pass recovers and offers nothing; it still ends a run of
    failures, so errors spread over a long session each retry after a second
    (`retry_delay`) rather than climbing toward its half-minute ceiling.
    """
    for name in CLAUDE_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    attempts = []
    delays = []

    def recover_receipt(_session_id):
        attempts.append(len(attempts))
        if len(attempts) in (1, 3):
            raise WebSocketException("the handshake was refused")
        return False

    def owned(_session):
        return [] if len(attempts) >= 4 else [codex_claimed_page]

    monkeypatch.setattr(codex_model, "recover_codex_receipt", recover_receipt)
    monkeypatch.setattr(codex_run_model, "owned_pages", owned)
    monkeypatch.setattr(codex_run_model, "check_queue_command", lambda _path: None)
    monkeypatch.setattr(codex_run_model, "offer_queued_delivery", lambda *_args: False)
    monkeypatch.setattr(
        codex_run_model,
        "read_watch_pass",
        lambda *_args, **_kwargs: SimpleNamespace(delivered=True),
    )
    monkeypatch.setattr(
        codex_run_model,
        "retry_delay",
        lambda failures: delays.append(failures) or 0,
    )

    assert codex_run_model.run_adapter("codex") == 0
    assert delays == [1, 1]


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
    with transaction_model.PageTransaction(page) as transaction:
        assert codex_adapter_model.capture_batch(
            "codex-thread", transaction, events_model.read_events(page)[-2:]
        )

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

    assert codex_adapter_model.offer_queued_delivery(
        "codex",
        "codex-thread",
        connection,
    )
    [payload] = started
    assert [event["id"] for event in payload["batches"][0]["events"]] == ["first"]
    assert [thread["id"] for thread in payload["batches"][0]["threads"]] == ["first"]
    assert "reply" not in payload
    # Frozen for App Server, the comment's reply is the turn's to write.
    assert payload["batches"][0]["events"][0]["answer"]["writer"] == "turn"

    # Accepting the delivery is the page receipt as well, so the record is complete
    # and archived by the time the turn is under way.
    assert codex_records("codex-thread") == []
    [history] = sorted(
        (codex_state_model.delivery_dir("codex-thread") / "history").glob("*.json")
    )
    recorded = files_model.read_json(history)
    assert (recorded["state"], recorded["turn"]) == ("opened", "app-server-turn")
    assert recorded["pending"] == []
    pickup = next(
        event for event in events_model.read_events(page) if event["kind"] == "pickup"
    )
    assert (pickup["phase"], pickup["turn"], pickup["events"]) == (
        "opened",
        "app-server-turn",
        ["first"],
    )
    assert codex_model.delivery_records("codex-thread") == []

    # Accepting the first delivery receipts it, so the second comment is collected
    # into a record of its own rather than joining the one already in a turn.
    with transaction_model.PageTransaction(page) as transaction:
        assert codex_adapter_model.capture_batch(
            "codex-thread",
            transaction,
            transaction_model.unacknowledged(transaction.events, transaction.cursor),
        )
    second_path, _ = current_codex_record("codex-thread")
    record_6 = codex_model.read_record(second_path)
    assert isinstance(record_6, (codex_model.Collecting, codex_model.Offering))
    second_payload = codex_model.offer_delivery(
        second_path, record_6, transport="app-server"
    ).payload
    assert [
        event["id"] for batch in second_payload["batches"] for event in batch["events"]
    ] == ["second"]


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
    session_model.cmd_waiting(page)
    with transaction_model.PageTransaction(page) as transaction:
        assert codex_adapter_model.capture_batch(
            "codex-thread", transaction, [delivered]
        )
    record_path, queue = current_codex_record("codex-thread")
    record_7 = codex_model.read_record(record_path)
    assert isinstance(record_7, (codex_model.Collecting, codex_model.Offering))
    codex_model.offer_delivery(record_path, record_7, transport="queue")
    queue = codex_model.RECORD.read(record_path)
    assert queue is not None
    queue.update(state="queued", pending=list(range(len(queue["batches"]))))
    codex_model.RECORD.write(record_path, queue)
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(claim_command(page, program)),
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
            lambda: acknowledged_through(page),
            lambda cursor: cursor == delivered["seq"],
            failure="the accepted delivery cursor was not recovered",
        )

        assert [json.loads(line) for line in log.read_text().splitlines()] == [
            ["queue", "--help"]
        ]
    finally:
        declare_idle(page)
        cleanup_model.end_session("codex-thread")
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after releasing its page",
    )


def test_codex_adapter_follows_ownership_across_idle_and_server_stop(
    codex_claimed_page, codex_env, tmp_path, spawn
):
    """Status and server changes do not end a route still owned by the task."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page)
    assert hosting_model.cmd_stop(page) is True
    checks = tmp_path / "adapter-checks.json"
    adapter = spawn_probe(
        spawn,
        page,
        """\
from leaf.commands import codex_run as adapter
from leaf.records.activity import declaration
from leaf.log.event_log import read_events
from leaf.base.files import read_json
from leaf.base.server import SERVICE
from leaf.base.state import write_json
native_read = adapter.read_watch_pass
passes = 0
def completed_read(*args, **kwargs):
    global passes
    page = Path(os.environ["PAGE"])
    state = declaration(read_events(page))["state"]
    enabled = read_json(SERVICE.file(page / "service.json"))["enabled"]
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
        session_model.cmd_waiting(page)
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
        cleanup_model.end_harness_instance("codex-thread")
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
        cleanup_model.end_session("codex-thread")


def test_a_later_claim_preserves_the_running_transport(
    codex_claimed_page, under_codex, codex_env, tmp_path
):
    """A later claim joins the running adapter; one asking for an App Server
    this adapter is not on is refused rather than ignored."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page)
    environment = codex_env | {
        "CODEX_THREAD_ID": "codex-thread",
        "FAKE_CODEX_LOG": str(log),
        "FAKE_CODEX_EXPECT_CWD": str(cleanup_model.state_home()),
    }

    # All three tool calls belong to one persistent harness process. Three separate
    # under_codex calls would introduce three genuine task lifetimes, rather than
    # asking whether another command in this task joins its existing adapter.
    # This transport test uses CLI lifetime; desktop persisted-chat ownership has
    # its own tests (`model/test_session_lifecycle.py`, `model/test_claims.py`).
    command = claim_command(page, program)
    results = tmp_path / "start-results.json"
    calls = [
        command,
        claim_command(page, program, endpoint="unix:///tmp/elsewhere.sock"),
        command,
    ]
    runner = PLUGIN_ROOT / "tests" / "fixtures" / "programs" / "codex_starts.py"
    try:
        finished = tmp_path / "codex-start-finished"
        started = under_codex(
            shlex.join([sys.executable, str(runner), json.dumps(calls), str(results)]),
            environment,
            app_server=False,
            finished=finished,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        [(status, first, err), (refused, refusal, _), (joined, again, _)] = wait_for(
            lambda: files_model.read_json(results),
            lambda reading: reading is not None,
            failure="the persistent Codex harness did not finish its three start commands",
        )
        assert status == 0, err
        assert json.loads(first) == {"session": "codex-thread"}
        assert refused != 0
        assert (
            "not through App Server unix:///tmp/elsewhere.sock"
            in json.loads(refusal)["error"]
        )
        assert joined == 0
        assert json.loads(again) == {"session": "codex-thread"}
        release_held(started)
        out, err = started.communicate(timeout=STATED_TIMEOUT)
        assert started.returncode == 0, f"{out}{err}"
    finally:
        declare_idle(page)
        cleanup_model.end_session("codex-thread")
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("codex-thread"),
        lambda live: not live,
        failure="the Codex adapter stayed live after releasing its page",
    )


def test_an_offline_sibling_does_not_stop_browser_comments_reaching_codex(
    page_dir, under_codex, codex_env, tmp_path
):
    """One unavailable leaf cannot break another page's browser-to-task path."""
    live = page_dir
    (live / "index.html").write_text(PAGE, encoding="utf-8")
    stamped = CliRunner().invoke(
        cli_model.cli,
        ["page", "stamp", str(live), "--text", "published"],
    )
    assert stamped.exit_code == 0, stamped.output
    offline = tmp_path / "a-offline-page"
    vendoring_model.cmd_init(offline)
    session_model.cmd_waiting(offline)
    write_record(
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
    session_model.cmd_waiting(live)
    finished = tmp_path / "codex-start-finished"
    # Both page claims and the adapter belong to the same actual task harness.
    # A second fake Codex process would declare a replacement session lifetime.
    prepare = """\
import sys
from pathlib import Path
from leaf.base.harness import session_harness
from leaf.pages.hosting import start_server
from leaf.records.transaction import claim_page
live, offline = map(Path, sys.argv[1:])
claim_page(offline)
claim_page(live)
start_server(live, harness=session_harness())
"""
    started = under_codex(
        shlex.join([sys.executable, "-c", prepare, str(live), str(offline)])
        + " && "
        + shlex.join(claim_command(live, program)),
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
        failure="the Codex adapter did not start",
    )
    announcement = codex_start_announcement(started)
    release_codex_command(live, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    out = announcement + out
    assert started.returncode == 0, f"{out}{err}"

    try:
        claim = service_model.page_claim(live)
        assert claim is not None
        record_claim(offline, **{**claim, "page": str(offline.resolve())})
        assert set(transaction_model.owned_pages("codex-thread")) == {live, offline}
        service = read_record(live / "service.json")
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
            lambda: acknowledged_through(live),
            lambda cursor: cursor == comment["seq"],
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
            delivery_model.DELIVERY.file(
                delivery_model.delivery_path(delivery.attrib["id"])
            )
        )
        [delivered_comment] = payload["batches"][0]["events"]
        assert (delivered_comment["id"], delivered_comment["text"]) == (
            comment["id"],
            "Does this reach the task?",
        )
    finally:
        for page in (offline, live):
            declare_idle(page)
        cleanup_model.end_session("codex-thread")


def test_codex_adapter_exits_when_delivery_retries_outlive_its_claim(
    codex_claimed_page, spawn, codex_env, tmp_path, dead_pid
):
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page)
    adapter = spawn_codex_adapter(
        spawn,
        program,
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
        assert claim is not None
        record_claim(page, **{**claim, "pid": dead_pid})
        wait_for(
            lambda: codex_adapter_model.adapter_is_live("codex-thread"),
            lambda live: not live,
            failure="the Codex adapter outlived its page claim",
        )
        assert adapter.wait(timeout=STATED_TIMEOUT) == 0
        assert codex_records("codex-thread")[0][1]["state"] == "offering"
        assert acknowledged_through(page) == 0
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert len(calls) == 2
    finally:
        cleanup_model.end_session("codex-thread")


def test_a_codex_adapter_whose_start_was_never_committed_exits(
    codex_claimed_page, spawn, codex_env, tmp_path
):
    """`leaf page claim` gives its claim back when it is interrupted, so an adapter
    it announced ready to but never committed would carry a page the start reported
    as failed. The adapter waits for the caller's acknowledgement after announcing,
    and a caller that leaves instead ends it with its leases released."""
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
    cleanup_model.end_session("codex-thread")


def test_a_queued_codex_delivery_leaves_the_turn_ended_stamp_in_place(
    codex_claimed_page, under_codex, codex_env, tmp_path
):
    """A direct wait's reader confirms the complete batch in its already-open turn.
    This adapter instead hands a pointer
    to Codex's durable same-task queue, which the loaded client starts and an unloaded
    task leaves waiting until someone reopens it — and the adapter never reopens one.

    So the stamp the Stop hook left is still true after acceptance, and clearing it
    would put "Codex is working" over a task nobody has read the delivery in. The
    cursor advancing and the accepted delivery are what says the delivery went through:
    the assertion is that a completed queue delivery moved everything except this."""
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    working(page, "answering the last comment")
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join(claim_command(page, program)),
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
        failure="the Codex adapter did not start",
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
            failure="the Codex adapter did not become live and listening",
        )

        cleanup_model.close_session_turn("codex-thread")
        claim_record_10 = service_model.page_claim(page)
        assert claim_record_10 is not None
        closed = claim_record_10["turn_closed"]
        assert closed

        hello = append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "hello adapter"}
        )
        wait_for(
            lambda: acknowledged_through(page),
            lambda cursor: cursor == hello["seq"],
            failure="the queued delivery cursor did not advance",
        )

        claim_record_11 = service_model.page_claim(page)
        assert claim_record_11 is not None
        assert claim_record_11["turn_closed"] == closed
        queued = activity_reading(page)
        assert queued["state"] == "running"
        assert [item["queued"] for item in queued["obligations"]] == [True]

        declare_idle(page)
    finally:
        cleanup_model.end_session("codex-thread")


def test_codex_serializes_later_input_behind_the_offered_delivery(
    codex_claimed_page, monkeypatch
):
    page = codex_claimed_page
    append_carried_log_record(
        page, {"kind": "comment", "id": "first", "author": "user", "text": "one"}
    )
    first = events_model.read_events(page)[-1]
    with transaction_model.PageTransaction(page) as transaction:
        assert codex_adapter_model.capture_batch("codex-thread", transaction, [first])
    first_path, _ = current_codex_record("codex-thread")

    queue_started = threading.Event()
    release_queue = threading.Event()

    def queue_delivery(_codex, _session, _prompt):
        queue_started.set()
        assert release_queue.wait(timeout=STATED_TIMEOUT)

    monkeypatch.setattr(codex_adapter_model, "queue_delivery", queue_delivery)
    offering = threading.Thread(
        target=lambda: codex_adapter_model.offer_queued_delivery(
            "codex", "codex-thread", None
        )
    )
    offering.start()
    assert queue_started.wait(timeout=STATED_TIMEOUT), (
        "the offer never reached the Codex queue"
    )
    assert (
        files_model.read_json(codex_model.RECORD.file(first_path))["state"]
        == "offering"
    )

    # A parallel step hook leaves the in-flight queue offer to its owner and
    # cannot capture its still-unacknowledged events into a second record.
    leases_model.mark_hooks("codex-thread")
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    prompt, _ = codex_model.offer_hook_delivery(
        "codex-thread", cleanup_model.session_record("codex-thread")
    )
    assert prompt is None
    assert len(codex_records("codex-thread")) == 1

    append_carried_log_record(
        page, {"kind": "comment", "id": "second", "author": "user", "text": "two"}
    )
    release_queue.set()
    offering.join(timeout=STATED_TIMEOUT)
    assert not offering.is_alive()
    first_delivery = files_model.read_json(
        codex_model.RECORD.file(first_path.parent / "history" / first_path.name)
    )
    assert first_delivery["state"] == "queued"
    payload = files_model.read_json(
        delivery_model.DELIVERY.file(delivery_model.delivery_path(first_path.stem))
    )
    assert [
        event["id"] for batch in payload["batches"] for event in batch["events"]
    ] == ["first"]

    assert not codex_model.recover_codex_receipt("codex-thread")
    with transaction_model.PageTransaction(page) as transaction:
        assert codex_adapter_model.capture_batch(
            "codex-thread",
            transaction,
            transaction_model.unacknowledged(transaction.events, transaction.cursor),
        )
    second_path, second_delivery = current_codex_record("codex-thread")
    assert second_path != first_path
    assert second_delivery["state"] == "collecting"
    assert [
        event["id"]
        for batch in files_model.read_json(codex_model.RECORD.file(second_path))[
            "batches"
        ]
        for event in batch["events"]
    ] == ["second"]


def test_serving_preserves_a_direct_codex_wait(
    codex_claimed_page, under_codex, codex_env, codex_queue
):
    """An active direct watcher keeps its lease instead of being replaced.

    The queue is deliberately unavailable: a successful handoff must use the
    real wait already watching this task. Stop still keeps that turn open.
    """
    page = codex_claimed_page
    stamp(page)
    program = """
import json, subprocess, sys, time
from pathlib import Path
from leaf.base.leases import wait_is_live, adapter_is_live
from leaf.records.transaction import PageTransaction, claim_page
from leaf.commands.session import cmd_waiting, set_status
page = Path(sys.argv[1])
claim_page(page)
cmd_waiting(page)
watch = subprocess.Popen([sys.executable, "-m", "leaf", "wait", str(page)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    deadline = time.monotonic() + 30
    while not wait_is_live(page, "codex-thread"):
        assert watch.poll() is None, watch.communicate()
        assert time.monotonic() < deadline, "the direct wait never took its lease"
        time.sleep(0.01)
    for command in ("start", "run"):
        served = subprocess.run([sys.executable, "-m", "leaf", "server", command, str(page)],
                                capture_output=True, text=True)
        assert served.returncode == 0, served.stderr
        assert json.loads(served.stdout)["url"]
        assert watch.poll() is None
        assert not adapter_is_live("codex-thread")
    stopped = subprocess.run([sys.executable, "-m", "leaf", "hook", "--harness", "codex"],
                             input=json.dumps({"hook_event_name": "Stop", "session_id": "codex-thread"}),
                             capture_output=True, text=True)
    assert stopped.returncode == 0, stopped.stderr
    reason = json.loads(stopped.stdout)["reason"]
    assert "leaf wait" in reason and "no delivery adapter" not in reason
finally:
    with PageTransaction(page) as held:
        set_status(held, "idle")
    output, errors = watch.communicate(timeout=30)
    assert watch.returncode == 2, (output, errors)
"""
    task = under_codex(
        shlex.join([sys.executable, "-c", program, str(page)]),
        codex_env
        | codex_queue
        | {"CODEX_THREAD_ID": "codex-thread", "PREVIEW_QUEUE_AVAILABLE": "False"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"


def test_serving_adopts_existing_pages_and_joins_one_codex_delivery(
    codex_claimed_page, tmp_path, under_codex, codex_env, codex_queue
):
    """A revived handoff connects once, including a reused foreground server.

    The first server already exists with no adapter. Two public starts and a
    foreground reuse must retain one adapter and leave Stop nothing to repair.
    """
    first = codex_claimed_page
    second = tmp_path / "sibling"
    shutil.copytree(first, second)
    server_model.SERVICE.remove(second / "service.json")
    ready, done = tmp_path / "ready.json", tmp_path / "done"
    program = """
import json, subprocess, sys, time
from pathlib import Path
from leaf.pages.hosting import cmd_stop
from leaf.base.leases import adapter_lease_path
from leaf.base.state import end_session, write_json
pages = list(map(Path, sys.argv[1:3]))
ready, done = map(Path, sys.argv[3:])
lease = adapter_lease_path("codex-thread")
try:
    identities = []
    for command, page in (("start", pages[0]), ("start", pages[1]), ("run", pages[0])):
        result = subprocess.run(
            [sys.executable, "-m", "leaf", "server", command, str(page)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["url"]
        identities.append(lease.stat().st_ino)
    stopped = subprocess.run(
        [sys.executable, "-m", "leaf", "hook", "--harness", "codex"],
        input=json.dumps({"hook_event_name": "Stop", "session_id": "codex-thread"}),
        capture_output=True, text=True,
    )
    assert stopped.returncode == 0, stopped.stderr
    assert not stopped.stdout, stopped.stdout
    write_json(ready, identities)
    while not done.exists():
        time.sleep(0.01)
finally:
    for page in pages:
        cmd_stop(page)
    end_session("codex-thread")
"""
    task = under_codex(
        shlex.join(
            [
                sys.executable,
                "-c",
                program,
                str(first),
                str(second),
                str(ready),
                str(done),
            ]
        ),
        codex_env | codex_queue | {"CODEX_THREAD_ID": "codex-thread"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for(
            ready.exists,
            bool,
            failure="the shared delivery handoff did not finish",
        )
        assert len(set(json.loads(ready.read_text()))) == 1
        assert leases_model.wait_is_live(first, "codex-thread")
        assert leases_model.wait_is_live(second, "codex-thread")
        assert codex_adapter_model.adapter_is_live("codex-thread")
    finally:
        done.touch()
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"


# A page's idle declaration matters only once delivery connects, so a refused
# delivery runs from a busy page alone.
@pytest.mark.parametrize(
    ("initially_idle", "delivery_available"),
    [(False, True), (True, True), (False, False), (False, "missing")],
)
@pytest.mark.parametrize("handoff", ["preview", "start", "run"])
def test_serving_connects_codex_feedback_before_handing_over_its_url(
    page_dir,
    tmp_path,
    under_codex,
    codex_env,
    codex_queue,
    delivery_available,
    handoff,
    initially_idle,
):
    """HTTP feedback reaches the current task without a second `page claim`.

    The detached adapter, claim and page server are real. Only the external Codex
    CLI is replaced: its queue boundary acknowledges and records the submitted
    task and delivery pointer instead of starting a model turn.
    """
    stamp(page_dir)
    if initially_idle:
        declare_idle(page_dir)
    queued = Path(codex_queue["PREVIEW_QUEUE_RECORD"])
    ready = tmp_path / "ready.json"
    done = tmp_path / "done"
    program = """
import json
import subprocess
import sys
import time
from pathlib import Path
from leaf.base.service import page_claim
from leaf.base.state import end_session, write_json
from leaf.base.harness import session_harness
from leaf.pages.hosting import cmd_stop, preparing_delivery
from leaf_dev.commands.preview import PreviewService

page, ready, done = map(Path, sys.argv[1:4])
handoff = sys.argv[4]
preview = PreviewService(page, True)
foreground = None
try:
    if handoff == "preview":
        with preview.starting() as url:
            pass
        started = (url, preview.reading(url))
        # Joining the current adapter preserves the preview's acquisition.
        with preparing_delivery(session_harness()):
            pass
        assert page_claim(page)["acquisition"] == preview.claim["acquisition"]
        assert not preview.ended
    elif handoff == "start":
        result = subprocess.run(
            [sys.executable, "-m", "leaf", "server", "start", str(page)],
            capture_output=True, text=True,
        )
        if result.returncode:
            sys.exit(result.stdout + result.stderr)
        started = (json.loads(result.stdout)["url"], result.stderr)
    else:
        foreground = subprocess.Popen(
            [sys.executable, "-m", "leaf", "server", "run", str(page)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        line = foreground.stdout.readline()
        announced = json.loads(line) if line else {}
        if "url" not in announced:
            output, errors = foreground.communicate(timeout=30)
            sys.exit(line + output + errors)
        started = (announced["url"], "")
    write_json(ready, started)
    while not done.exists():
        time.sleep(0.01)
finally:
    if handoff == "preview":
        preview.stop()
    else:
        cmd_stop(page)
    if foreground is not None:
        foreground.communicate(timeout=30)
    if ready.exists():
        end_session(session_harness().session)
"""
    delivery_env = (
        codex_env
        | codex_queue
        | {
            "CODEX_THREAD_ID": "preview-thread",
            "PREVIEW_QUEUE_AVAILABLE": str(delivery_available),
        }
    )
    if delivery_available == "missing":
        delivery_env["PATH"] = str(tmp_path / "no-codex")
    task = under_codex(
        shlex.join(
            [
                sys.executable,
                "-c",
                program,
                str(page_dir),
                str(ready),
                str(done),
                handoff,
            ]
        ),
        delivery_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if delivery_available is not True:
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
        assert task.returncode != 0, f"{output}{errors}"
        expected = (
            "cannot find the `codex` executable"
            if delivery_available == "missing"
            else "queue unsupported"
        )
        assert expected in errors
        if handoff != "preview":
            assert "Traceback" not in errors
        assert not ready.exists()
        assert service_model.page_claim(page_dir) is None
        assert server_model.running_server(page_dir) is None
        assert not codex_adapter_model.adapter_is_live("preview-thread")
        return
    try:
        wait_for(
            ready.exists,
            bool,
            failure="the user preview never handed over its URL",
        )
        url, _ = json.loads(ready.read_text())
        claim = service_model.page_claim(page_dir)
        assert claim is not None
        assert claim["id"] == "preview-thread"
        assert claim["pid"] == task.pid, (
            "detached child replaced its launching harness lifetime"
        )
        assert codex_adapter_model.adapter_is_live("preview-thread")
        if initially_idle:
            assert declared(page_dir)["state"] == "idle"
            session_model.cmd_waiting(page_dir)
        endpoint = urlsplit(url)._replace(path="/api/event").geturl()
        status, body = fetch(
            endpoint,
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": 1,
                    "text": "Please revise this candidate",
                    "attempt": "preview_feedback",
                }
            ).encode(),
            token=None,
        )
        assert status == 200, body
        wait_for(
            queued.exists,
            bool,
            failure="the preview's feedback did not reach Codex",
        )
        arguments = json.loads(queued.read_text())
        assert arguments[:4] == ["queue", "--thread", "preview-thread", "--message"]
        assert 'operation="delivery read"' in arguments[-1]
    finally:
        done.touch()
        output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"
    wait_for(
        lambda: codex_adapter_model.adapter_is_live("preview-thread"),
        lambda live: not live,
        failure="the task's delivery adapter outlived its preview",
    )
