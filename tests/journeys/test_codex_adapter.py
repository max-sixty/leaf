"""The Codex adapter and the delivery records it shares with Codex's hooks:
capturing a page's input, offering it through `codex queue`, an App Server turn,
or a tool or Stop hook, receipting it on each page, recovering after a restart,
and the adapter process's lifetime."""

import json
import os
import shlex
import subprocess
import sys
from xml.etree import ElementTree

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    _delivery_item,
    append_carried_log_record,
    codex_records,
    declare_idle,
    page_state,
    publish,
    release_codex_command,
    spawn_probe,
    wait_for,
)
from leaf import codex as codex_model
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import hooks as hooks_model
from leaf import machine as machine_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from model.test_codex_adapter import (
    adapter_log,
    codex_start_announcement,
    current_codex_record,
    fake_codex_cli,
)


@pytest.mark.parametrize("reclaimed", ["delivered", "another"])
def test_codex_app_server_restart_finishes_an_accepted_batch_without_starting_it_again(
    codex_claimed_page, app_server, under_codex, codex_env, tmp_path, reclaimed
):
    """The App Server twin of the queue case,
    `test_codex_restart_finishes_an_accepted_batch_without_queueing_again` in
    `tests/model/test_codex_adapter.py`. The restarted adapter reads back the turn
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
    record_path, record = current_codex_record("codex-thread")
    prepared = codex_model.offer_delivery(
        record_path, codex_model.read_record(record_path), transport="app-server"
    )
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
        shlex.join(
            [
                *LEAF_COMMAND,
                "codex",
                "start",
                str(claimed),
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
            lambda: files_model.read_json(page / "cursor.json"),
            lambda cursor: cursor == {"seq": delivered["seq"]},
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
            failure="the Codex adapter did not become live and listening",
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

        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        assert capsys.readouterr().out == ""

        hooks_model.cmd_hook(
            "codex",
            {"hook_event_name": "UserPromptSubmit", "session_id": "codex-thread"},
        )
        assert capsys.readouterr().out == ""
        assert [
            item["stage"] for item in page_state(page)["activity"]["obligations"]
        ] == ["picked_up"]
        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        reason = json.loads(capsys.readouterr().out)["reason"]
        assert "1 acknowledged user update with no answer" in reason

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
        assert files_model.read_json(page / "cursor.json") == {
            "seq": comments[-1]["seq"]
        }
        assert codex_adapter_model.adapter_is_live("codex-thread")

        for comment in comments:
            thread_model.post_reply(
                page, {"to": comment["id"], "for": comment["id"]}, "received"
            )
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
        cleanup_model.end_session("codex-thread")
        subprocess.run([*LEAF_COMMAND, "server", "stop", second], check=True)

    out, err = adapter.communicate(timeout=STATED_TIMEOUT)
    assert adapter.returncode == 0, f"{out}{err}"
