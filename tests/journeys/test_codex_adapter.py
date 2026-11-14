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
    owed_answers,
    page_state,
    publish,
    release_codex_command,
    release_held,
    spawn_probe,
    wait_for,
)
from model.test_codex_adapter import (
    adapter_log,
    claim_command,
    codex_start_announcement,
    current_codex_record,
    fake_codex_cli,
)

from leaf import codex as codex_model
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import hooks as hooks_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model


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
    record_path, record = current_codex_record("codex-thread")
    record_2 = codex_model.read_record(record_path)
    assert isinstance(record_2, (codex_model.Collecting, codex_model.Offering))
    prepared = codex_model.offer_delivery(record_path, record_2, transport="app-server")
    record = files_model.read_json(record_path)
    record.update(
        state="opened", turn="taken", pending=list(range(len(record["batches"])))
    )
    cleanup_model.write_json(record_path, record)
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
            payload_path = delivery_model.delivery_path(delivery.attrib["id"])
            assert payload_path.exists()
            payload = files_model.read_json(payload_path)
            assert payload["format"] == delivery_model.DELIVERY.format
            assert all(
                set(batch)
                == {"page", "claim", "through_seq", "threads", "handling", "events"}
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
from leaf import codex_adapter
from leaf.service import cmd_claim
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


def test_selecting_a_checkout_replaces_the_sessions_delivery_runtime(
    codex_claimed_page, under_codex, codex_env, tmp_path
):
    """The previous adapter retires, and its successor queues the page's input.

    Two real Python package locations model installed Leaf and a selected checkout;
    the fake external Codex endpoint records the delivery instead of opening a turn.
    """
    foreign = tmp_path / "installed"
    for name in ("src", "browser", "packages", "skills"):
        shutil.copytree(PLUGIN_ROOT / name, foreign / name)
    launcher = foreign / "bin/leaf"
    launcher.parent.mkdir()
    launcher.write_text(
        "#!/bin/sh\n"
        f"export PYTHONPATH={shlex.quote(str(foreign / 'src'))}\n"
        f'exec {shlex.quote(sys.executable)} -m leaf "$@"\n'
    )
    launcher.chmod(0o755)
    program, log = fake_codex_cli(tmp_path)
    results = tmp_path / "starts.json"
    first = claim_command(codex_claimed_page, program, launcher=[str(launcher)])
    select_runtime = (
        "from pathlib import Path; from leaf.session_runtime import select_launcher; "
        f"select_launcher('codex-thread', Path({str(PLUGIN_ROOT / 'bin/leaf')!r}))"
    )
    calls = [
        first,
        [sys.executable, "-c", select_runtime],
        claim_command(codex_claimed_page, program),
    ]
    runner = PLUGIN_ROOT / "tests/fixtures/programs/codex_starts.py"
    task = under_codex(
        shlex.join([sys.executable, str(runner), json.dumps(calls), str(results)]),
        codex_env | {"CODEX_THREAD_ID": "codex-thread", "FAKE_CODEX_LOG": str(log)},
        app_server=False,
        finished=tmp_path / "finished",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        outcomes = wait_for(
            lambda: files_model.read_json(results),
            lambda value: value is not None,
            failure="delivery runtime replacement did not finish",
        )
        assert all(status == 0 for status, _out, _err in outcomes), outcomes
        adapter_2 = codex_adapter_model.running_adapter("codex-thread")
        assert adapter_2 is not None
        assert adapter_2["launcher"] == str(PLUGIN_ROOT / "bin/leaf")
        append_carried_log_record(
            codex_claimed_page,
            {
                "kind": "comment",
                "author": "user",
                "text": "Review with the selected checkout",
            },
        )
        wait_for(
            lambda: log.read_text(),
            lambda text: '"--message"' in text,
            failure="the replacement adapter did not queue the pending input",
        )
    finally:
        release_held(task)
        task.communicate(timeout=STATED_TIMEOUT)
        cleanup_model.end_session("codex-thread")
        wait_for(
            lambda: codex_adapter_model.adapter_is_live("codex-thread"),
            lambda live: not live,
            failure="the replaced delivery runtime did not end",
        )


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

from leaf import cli as cli_model
from leaf import hosting as hosting_model
from leaf import server as server_model
from leaf import vendoring as vendoring_model
from leaf.refusals import Refused


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
    with service_model.PageTransaction(page) as transaction:
        batch = delivery_model.batch_data(page, transaction, [event])
    delivery_model.freeze_delivery([batch], delivery_id="bbbbbbbb")
    directory = codex_state_model.delivery_dir("codex-thread")
    directory.mkdir(parents=True)
    cleanup_model.write_json(
        directory / "bbbbbbbb.json",
        {
            "format": codex_model.RECORD.format,
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
            "format": codex_model.RECORD.format,
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
    for identity, event in (("ffffffff", first), ("aaaaaaaa", second)):
        with service_model.PageTransaction(page) as transaction:
            batch = delivery_model.batch_data(page, transaction, [event])
        delivery_model.freeze_delivery([batch], delivery_id=identity)
    cleanup_model.write_json(directory / "ffffffff.json", epoch(first, created_at=1))
    cleanup_model.write_json(directory / "aaaaaaaa.json", epoch(second, created_at=2))

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
        codex_adapter_model._offer_queued_delivery(
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
    monkeypatch.setattr(codex_adapter_model, "owned_pages", lambda _session: [])
    monkeypatch.setattr(codex_adapter_model, "check_queue_command", lambda _path: None)
    monkeypatch.setattr(codex_adapter_model, "retry_delay", lambda _failures: 0)

    assert codex_adapter_model.run_adapter("codex") == 0
    assert attempts == ["codex-thread", "codex-thread"]


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
    record_7 = codex_model.read_record(record_path)
    assert isinstance(record_7, (codex_model.Collecting, codex_model.Offering))
    codex_model.offer_delivery(record_path, record_7, transport="queue")
    queue = files_model.read_json(record_path)
    queue.update(state="queued", pending=list(range(len(queue["batches"]))))
    cleanup_model.write_json(record_path, queue)
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
from leaf import codex_adapter as adapter
from leaf.activity import declaration
from leaf.event_log import read_events
from leaf.files import read_json
from leaf.state import write_json
native_read = adapter.read_watch_pass
passes = 0
def completed_read(*args, **kwargs):
    global passes
    page = Path(os.environ["PAGE"])
    state = declaration(read_events(page))["state"]
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
    # This transport test uses CLI lifetime; desktop persisted-chat ownership is
    # exercised independently by the detached preview journey.
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
        [(status, first, err), (refused, _, refusal), (joined, again, _)] = wait_for(
            lambda: files_model.read_json(results),
            lambda reading: reading is not None,
            failure="the persistent Codex harness did not finish its three start commands",
        )
        assert status == 0, err
        assert json.loads(first) == {"session": "codex-thread"}
        assert refused != 0
        assert "not through App Server unix:///tmp/elsewhere.sock" in refusal
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
from leaf.harness import session_harness
from leaf.hosting import start_server
from leaf.service import claim_page
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
        assert set(service_model.owned_pages("codex-thread")) == {live, offline}
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
