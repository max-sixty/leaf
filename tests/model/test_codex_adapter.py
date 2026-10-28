"""The Codex adapter and the delivery records it shares with Codex's hooks:
capturing a page's input, offering it through `codex queue`, an App Server turn,
or a tool or Stop hook, receipting it on each page, recovering after a restart,
and the adapter process's lifetime."""

import json
import os
import select
import shlex
import shutil
import socket
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

import pytest
from click.testing import CliRunner
from conftest import CLAUDE_IDENTITY, HOOKED_SESSIONS, LEAF_COMMAND
from interact_support import (
    PAGE,
    PLUGIN_ROOT,
    STATED_TIMEOUT,
    _observer,
    _watched,
    acknowledge_through,
    acknowledged_through,
    activity_reading,
    adapter_lease,
    append_carried_log_record,
    append_command,
    available_loopback_port,
    codex_records,
    declare_idle,
    declare_work,
    declared,
    delivered,
    delivered_ref,
    fetch,
    last_deliverable_seq,
    page_state,
    publish,
    read_record,
    receive_through,
    record_claim,
    refused_on,
    release_codex_command,
    release_held,
    serving,
    spawn_probe,
    vendored_at_another_protocol,
    wait_for,
    working,
    write_record,
)
from websockets.exceptions import WebSocketException

from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hook_transport as hook_transport_model
from leaf import hooks as hooks_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf import vendoring as vendoring_model
from leaf.refusals import Refused


def codex_start_announcement(process) -> str:
    """Wait for committed CLI output before transferring the fake harness lifetime."""
    assert select.select([process.stdout], [], [], 30)[0], (
        "Codex start did not report completion"
    )
    line = process.stdout.readline()
    assert json.loads(line)["session"] == "codex-thread"
    return line


def fake_codex_cli(tmp_path: Path) -> tuple[Path, Path]:
    """A process-boundary `codex queue` implementation for adapter tests."""
    program = tmp_path / "codex"
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


def claim_command(page, program, *, endpoint=None, launcher=LEAF_COMMAND):
    """Select the external Codex executable and transport as a real shell does."""
    return [
        "env",
        f"PATH={program.parent}{os.pathsep}{os.environ['PATH']}",
        *([f"LEAF_CODEX_APP_SERVER={endpoint}"] if endpoint is not None else []),
        *launcher,
        "page",
        "claim",
        str(page),
    ]


def test_codex_readdresses_a_collecting_record_if_its_delivery_id_collides(
    page_dir, monkeypatch
):
    minted = iter(["aaaaaaaa", "bbbbbbbb"])
    monkeypatch.setattr(codex_model, "new_delivery_id", lambda: next(minted))
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hello"}
    )
    with service_model.PageTransaction(page_dir) as transaction:
        append_batch_result = codex_model.append_batch(
            "collision-test", page_dir, transaction, transaction.events
        )
        assert append_batch_result is not None
        path, _, _ = append_batch_result
    assert path.stem == "aaaaaaaa"
    delivery_model.freeze_delivery([], delivery_id=path.stem, created_at=0)

    record_2 = codex_model.read_record(path)
    assert isinstance(record_2, (codex_model.Collecting, codex_model.Offering))
    prepared = codex_model.offer_delivery(path, record_2, transport="queue")

    assert prepared.payload["id"] == "bbbbbbbb"
    assert codex_model.record_path("collision-test", "bbbbbbbb").is_file()
    assert not path.exists()


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
    assert set(batch) == {
        "page",
        "claim",
        "through_seq",
        "threads",
        "handling",
        "events",
    }
    assert batch["events"][0]["id"] == comment["id"]
    claim = service_model.page_claim(page_dir)
    assert claim is not None
    assert {key: claim[key] for key in ("id", "harness", "pid", "agent")} == {
        "id": "hosted-thread",
        "harness": "embedded",
        "pid": os.getpid(),
        "agent": "Leaf guide",
    }
    assert claim is not None
    assert (claim["turn"], claim["turn_closed"]) == ("app-turn", None)
    assert accepted == {"page": page_dir, "events": (comment["id"],)}
    assert acknowledged_through(page_dir) == 1
    activity = activity_reading(page_dir)
    assert activity["kind"] == "working"
    assert activity["dropped"] is False
    assert activity["counts"]["handling"] == 1
    assert activity["obligations"][0]["delivery_turn"] == claim["turn"]
    [history] = (codex_state_model.delivery_dir("hosted-thread") / "history").glob(
        "*.json"
    )
    queue = files_model.read_json(history)
    assert queue["state"] == "opened"
    assert queue["pending"] == []
    assert delivery_model.delivery_path(history.stem).is_file()


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
    claim_record = service_model.page_claim(page_dir)
    assert claim_record is not None
    first_turn = claim_record["turn"]

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
    assert claim is not None
    assert claim["turn"] == first_turn
    assert activity["counts"]["handling"] == 2
    assert activity["counts"]["handling_comments"] == 2
    assert activity["counts"]["picked_up"] == 0
    assert all(item["condition"] is None for item in interactions.values())


@pytest.mark.parametrize("ownership_transferred", [False, True])
def test_embedded_codex_delivery_retries_the_same_immutable_pointer(
    page_dir, ownership_transferred
):
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "make this editable"},
    )
    harness = harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid())
    first = codex_model.prepare_codex_delivery(page_dir, harness)

    if ownership_transferred:
        with service_model.PageTransaction(page_dir) as page:
            page.take_claim(
                harness_model.EmbeddedHarness("successor", "Successor", os.getpid())
            )
            successor = page.active_claim
        with pytest.raises(delivery_model.ReceiptRefused, match="no longer owns"):
            codex_model.prepare_codex_delivery(page_dir, harness)
        assert service_model.same_claim(service_model.page_claim(page_dir), successor)
        assert delivery_model.read_delivery(first.payload["id"]) == first.payload
        return

    second = codex_model.prepare_codex_delivery(page_dir, harness)

    assert second == first
    [(path, queue)] = codex_model.delivery_records("hosted-thread")
    payload = files_model.read_json(delivery_model.delivery_path(path.stem))
    assert queue.state == "offering"
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
    thread_model.post_reply(
        page_dir,
        {"parent": first["id"], "responds": first["id"]},
        "try again later",
        identity={"agent": "Leaf guide", "session": "website-agent"},
    )
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    second_prompt = codex_model.prepare_codex_delivery(page_dir, harness)

    assert codex_model.delivery_records("hosted-thread")[0][1].state == "offering"
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
    thread_model.post_reply(
        page_dir,
        {"parent": first["id"], "responds": first["id"]},
        "try again later",
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
    assert delivered_events[1]["answer"]["responds"] == delivered_events[1]["id"]


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

    def envelope(delivery_id, page, format=delivery_model.DELIVERY.format):
        batch = {
            "page": str(page),
            "claim": None,
            "through_seq": 1,
            "threads": [],
            "handling": {},
            "events": [],
        }
        return record(
            delivery_model.delivery_path(delivery_id),
            {
                "format": format,
                "id": delivery_id,
                "created_at": 0,
                "acknowledge": None,
                "batches": [batch],
            },
        )

    kept = envelope("0000000a", claimed)
    retired = envelope("0000000b", gone)
    unreadable = [
        envelope("0000000c", claimed, "v2"),
        record(delivery_model.delivery_path("00000012"), {"batches": []}),
        record(
            delivery_model.delivery_path("00000013"),
            {"format": delivery_model.DELIVERY.format},
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
            "format": codex_model.RECORD.format,
            "state": "queued",
            "created_at": 0,
            "pending": [],
            "batches": [
                {
                    "page": str(page),
                    "session": "t",
                    "events": [{"id": "captured", "seq": 1}],
                }
            ],
            **fields,
        }

    for identity, page in (
        ("0000000d", claimed),
        ("0000000e", gone),
        ("0000000f", gone),
        ("00000011", claimed),
    ):
        envelope(identity, page)
    live = record(codex_model.record_path("t", "0000000d"), task_record("d", claimed))
    stale = record(codex_model.record_path("t", "0000000e"), task_record("e", gone))
    history = live.parent / "history"
    archived_gone = record(history / "0000000f.json", task_record("f", gone))
    archived_other = record(history / "00000010.json", {"batches": []})
    archived_incomplete = record(
        history / "00000012.json", {"format": codex_model.RECORD.format}
    )
    archived_kept = record(history / "00000011.json", task_record("g", claimed))
    archived_foreign = record(
        history / "00000014.json",
        task_record("h", claimed, format="another-version"),
    )
    with cleanup_model.flocked(codex_state_model.delivery_lock_path("t")):
        assert codex_model.delivery_records("t") == []
        assert not stale.exists()
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


def test_codex_drops_a_record_whose_delivery_it_cannot_read(page_dir):
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hello"}
    )
    with service_model.PageTransaction(page_dir) as transaction:
        append_batch_result_2 = codex_model.append_batch(
            "handling-test", page_dir, transaction, transaction.events
        )
        assert append_batch_result_2 is not None
        path, _, _ = append_batch_result_2
    record_3 = codex_model.read_record(path)
    assert isinstance(record_3, (codex_model.Collecting, codex_model.Offering))
    payload = codex_model.offer_delivery(path, record_3, transport="queue").payload
    payload["format"] = "leaf-delivery-v1"
    cleanup_model.write_json(delivery_model.delivery_path(payload["id"]), payload)
    with pytest.raises(Refused, match="written by another Leaf"):
        delivery_model.read_delivery(payload["id"])
    assert codex_model.delivery_records("handling-test") == []


def test_codex_receipt_leaves_input_for_the_new_page_owner(page_dir):
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "accepted", "author": "user", "text": "hi"},
    )
    delivered = events_model.read_events(page_dir)[-1]
    session_model.cmd_waiting(page_dir)
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
    record_4 = codex_model.read_record(epoch_path)
    assert isinstance(record_4, (codex_model.Collecting, codex_model.Offering))
    codex_model.offer_delivery(epoch_path, record_4, transport="queue")
    epoch = files_model.read_json(epoch_path)
    epoch.update(state="queued", pending=list(range(len(epoch["batches"]))))
    cleanup_model.write_json(epoch_path, epoch)
    batch = epoch["batches"][0]

    codex_model.finish_codex_batch(
        epoch_path, 0, batch, codex_model.Accepted(0, (batch,), (0,))
    )
    codex_model.finish_codex_batch(
        epoch_path, 0, batch, codex_model.Accepted(0, (batch,), (0,))
    )

    assert acknowledged_through(page_dir) == 0
    assert service_model.page_claim(page_dir) == successor
    assert declared(page_dir)["state"] == "waiting"
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

    assert not codex_model.recover_codex_receipt("codex-thread")
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
            "format": codex_model.RECORD.format,
            "state": state,
            "created_at": 0,
            "batches": [],
        },
    )

    assert codex_model.delivery_records("codex-thread") == []


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


@pytest.mark.parametrize(
    ("leaving", "confirmed"),
    [("restart", True), ("transfer", False), ("end", False)],
)
def test_a_codex_receipt_holds_while_the_claim_still_names_its_session(
    page_dir, codex_loop, leaving, confirmed
):
    """A restart's new generation leaves the claim naming an older one of the same
    session, and the receipt still lands. Another session's claim or the session's
    end lets the page go, and the batch retires without advancing the cursor."""
    codex_loop(page_dir)
    event = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Taken"}
    )
    directory = codex_state_model.delivery_dir("codex-thread")
    directory.mkdir(parents=True)
    cleanup_model.write_json(
        directory / "aaaaaaaa.json",
        {
            "format": codex_model.RECORD.format,
            "state": "queued",
            "created_at": 1,
            "pending": [0],
            "batches": [
                {
                    "page": str(page_dir),
                    "session": "codex-thread",
                    "threads": [],
                    "events": [event],
                }
            ],
        },
    )
    with service_model.PageTransaction(page_dir) as transaction:
        batch = delivery_model.batch_data(page_dir, transaction, [event])
    delivery_model.freeze_delivery([batch], delivery_id="aaaaaaaa")
    if leaving == "restart":
        cleanup_model.ensure_session("codex-thread", {"pid": os.getppid()})
    elif leaving == "transfer":
        record_claim(page_dir, id="successor", harness="codex", agent="Codex")
    else:
        cleanup_model.end_session("codex-thread")
    with service_model.PageTransaction(page_dir) as page:
        assert page.active_claim is None or leaving == "transfer"

    assert codex_model.recover_codex_receipt("codex-thread")
    assert not codex_records("codex-thread")
    assert acknowledged_through(page_dir) == (event["seq"] if confirmed else 0)
    assert [
        pickup["events"]
        for pickup in events_model.read_events(page_dir)
        if pickup["kind"] == "pickup"
    ] == ([[event["id"]]] if confirmed else [])


def test_a_reinitialized_page_does_not_starve_later_codex_receipts(tmp_path):
    replaced = tmp_path / "a-replaced-page"
    kept = tmp_path / "z-kept-page"
    for page, event_id in ((replaced, "old"), (kept, "kept")):
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
    record_5 = codex_model.read_record(epoch_path)
    assert isinstance(record_5, (codex_model.Collecting, codex_model.Offering))
    codex_model.offer_delivery(epoch_path, record_5, transport="queue")
    epoch = files_model.read_json(epoch_path)
    epoch.update(state="queued", pending=list(range(len(epoch["batches"]))))
    cleanup_model.write_json(epoch_path, epoch)

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

    assert codex_model.recover_codex_receipt("codex-thread")
    assert files_model.read_json(epoch_path)["pending"] == [1]
    assert codex_model.recover_codex_receipt("codex-thread")

    history = epoch_path.parent / "history" / epoch_path.name
    assert files_model.read_json(history)["pending"] == []
    assert acknowledged_through(kept) == 1
    pickups = [
        event for event in events_model.read_events(kept) if event["kind"] == "pickup"
    ]
    assert [pickup["events"] for pickup in pickups] == [["kept"]]


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
    assert (recorded["state"], recorded["turn"]) == ("opened", "app-server-turn")
    assert recorded["pending"] == []

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


def test_a_codex_adapter_retiring_with_no_page_leaves_only_records_a_page_needs(
    monkeypatch, tmp_path
):
    """Retiring removes readable records whose pages are gone and its own log.
    A persistent page's records survive, and stable coordination files stay unheld
    for the next holder."""
    # The suite's hook marks (`isolated_session`) are not records this test makes.
    for session in HOOKED_SESSIONS:
        cleanup_model.session_file(session, cleanup_model.HOOKS_SUFFIX).unlink()
    for name in CLAUDE_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    monkeypatch.setattr(codex_adapter_model, "owned_pages", lambda _session: [])
    monkeypatch.setattr(codex_adapter_model, "check_queue_command", lambda _path: None)
    persistent = tmp_path / "persistent"
    persistent.mkdir()
    for task, page, identity in (
        ("ended-task", tmp_path / "gone", "dddddddd"),
        ("codex-thread", persistent, "eeeeeeee"),
    ):
        delivery_model.delivery_path(identity).parent.mkdir(parents=True, exist_ok=True)
        delivery_model.DELIVERY.write(
            delivery_model.delivery_path(identity),
            {
                "id": identity,
                "created_at": 0,
                "acknowledge": None,
                "batches": [
                    {
                        "page": str(page),
                        "claim": None,
                        "through_seq": 1,
                        "threads": [],
                        "handling": {},
                        "events": [],
                    }
                ],
            },
        )
        path = codex_model.record_path(task, identity)
        path.parent.mkdir(parents=True)
        cleanup_model.write_json(
            path,
            {
                "format": codex_model.RECORD.format,
                "state": "queued",
                "created_at": 0,
                "pending": [],
                "batches": [
                    {
                        "page": str(page),
                        "session": task,
                        "events": [{"id": "delivered", "seq": 1}],
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
        path for path in cleanup_model.sessions_home().iterdir() if path != kept
    ]
    assert leases_model.adapter_lease_path("codex-thread") in coordination
    assert all(
        path.is_file() and not leases_model.lock_is_held(path) for path in coordination
    )
    assert [path.name for path in kept.rglob("*.json")] == ["eeeeeeee.json"]


def test_an_adapter_observer_that_cannot_start_releases_its_leases(monkeypatch):
    """Acquisition failure keeps the original error and releases both listening proofs."""
    harness = harness_model.CodexHarness(session="codex-thread", agent="Codex")
    monkeypatch.setattr(codex_adapter_model, "session_harness", lambda: harness)

    def refuse_start(_thread):
        raise OSError("no thread resources")

    monkeypatch.setattr(threading.Thread, "start", refuse_start)
    with pytest.raises(OSError, match="no thread resources"):
        codex_adapter_model.run_adapter("codex", app_server="ws://127.0.0.1:1")
    assert not leases_model.adapter_is_live(harness.session)
    assert not leases_model.wait_is_live(None, harness.session)


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
    assert payload["batches"][0]["events"][0]["answer"]["writer"] == "turn"

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


@pytest.mark.parametrize("delivery_hook", ["PostToolUse", "Stop"])
def test_codex_tool_hook_delivers_into_the_running_turn_once(
    page_dir, codex_loop, capsys, monkeypatch, delivery_hook
):
    """Hook completion offers input; its actual read proves same-turn pickup.

    The idle queue never takes an already-read pointer, and parallel tool hooks
    cannot recapture its unreceipted events or emit it twice.
    """
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
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
        "codex",
        {
            "hook_event_name": delivery_hook,
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    output = json.loads(capsys.readouterr().out)
    context = (
        output["reason"]
        if delivery_hook == "Stop"
        else output["hookSpecificOutput"]["additionalContext"]
    )
    [(path, record)] = codex_records("codex-thread")
    assert len(context.splitlines()) == 1
    envelope = json.loads(context)
    assert envelope == delivery_model.cmd_delivery_read(path.stem)
    assert envelope["acknowledge"] == delivery_model.pointer_acknowledgement(path.stem)
    assert envelope["batches"][0]["events"][0]["id"] == comment["id"]
    assert (record["state"], record["turn"]) == ("hook", "user-turn")
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(page_dir)
    )
    # Reading outside the owning task doesn't claim the user's input.
    monkeypatch.delenv("CODEX_THREAD_ID")
    delivery_model.cmd_delivery_read(path.stem)
    assert codex_records("codex-thread")[0][1]["state"] == "hook"
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    assert not capsys.readouterr().out
    assert len(codex_records("codex-thread")) == 1
    delivery_model.cmd_delivery_ack(path.stem)
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


@pytest.mark.parametrize("app_server", ["unix:///app-server.sock", None])
def test_a_codex_stop_leaves_late_input_to_an_app_server_adapters_own_turn(
    page_dir, codex_loop, capsys, monkeypatch, app_server
):
    """While an adapter that starts turns over App Server runs, a comment that
    arrives as the turn ends is not handed into it: continuing the turn would have
    the agent write one more message after the answer the turn had written. The turn
    ends, and the adapter starts the comment's own turn, which adds no message to
    the user's conversation. A queue adapter's turn would open on a pointer Codex
    shows as the user's own message, so there Stop hands the comment into the
    ending turn and the adapter queues nothing. A task that waits with `leaf wait`
    has nothing to open a later turn, so its Stop hands the comment over too
    (`test_codex_tool_hook_delivers_into_the_running_turn_once`)."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    waiter = _watched(page_dir)
    adapter = adapter_lease("codex-thread", app_server)
    leases_model.mark_hooks("codex-thread")
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )
    try:
        comment = append_carried_log_record(
            page_dir, {"kind": "comment", "author": "user", "text": "And the footer?"}
        )
        # The adapter's watch collects it as it arrives, and holds it back while
        # the running turn's hooks may still offer it.
        with service_model.PageTransaction(page_dir) as transaction:
            codex_model.append_batch("codex-thread", page_dir, transaction, [comment])
        assert not codex_adapter_model._offer_queued_delivery(
            "codex", "codex-thread", None
        )
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "user-turn",
            },
        )
        if app_server is not None:
            assert capsys.readouterr().out == ""
            turn_record = cleanup_model.session_record("codex-thread")
            assert turn_record is not None
            assert turn_record["turn_closed"]
            assert acknowledged_through(page_dir) < comment["seq"]
            # Collected and unoffered, for the adapter's own start.
            [(_, record)] = codex_records("codex-thread")
            assert record["state"] == "collecting"
            return
        answer = json.loads(capsys.readouterr().out)
        assert answer["decision"] == "block"
        envelope = json.loads(answer["reason"])
        assert [event["id"] for event in envelope["batches"][0]["events"]] == [
            comment["id"]
        ]
        turn_record_2 = cleanup_model.session_record("codex-thread")
        assert turn_record_2 is not None
        assert not turn_record_2["turn_closed"]
        assert not codex_adapter_model._offer_queued_delivery(
            "codex", "codex-thread", None
        )
        delivery_model.cmd_delivery_ack(envelope["id"])
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
        assert not queued
    finally:
        adapter.close()
        leases_model.release_lease(waiter)


@pytest.mark.parametrize("delivery_hook", ["PostToolUse", "Stop"])
def test_codex_hook_keeps_oversized_input_whole_for_its_reader(
    page_dir, codex_loop, capsys, delivery_hook
):
    """Codex's native preview must never replace a complete delivery in context."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    text = "Long input\n" + "漢" * 4000
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": text}
    )
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": delivery_hook,
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    output = json.loads(capsys.readouterr().out)
    context = (
        output["reason"]
        if delivery_hook == "Stop"
        else output["hookSpecificOutput"]["additionalContext"]
    )
    [(path, record)] = codex_records("codex-thread")
    assert record["state"] == "hook"
    assert context == delivery_model.delivery_pointer_prompt(path.stem)
    assert acknowledged_through(page_dir) == 0
    reading = delivery_model.cmd_delivery_read(path.stem)
    assert reading["batches"][0]["events"][0]["text"] == text
    delivery_model.cmd_delivery_ack(path.stem)
    assert not codex_records("codex-thread")


@pytest.mark.parametrize("delivery_hook", ["PostToolUse", "Stop"])
def test_codex_hooks_leave_collected_input_after_ownership_transfers(
    page_dir, codex_loop, capsys, delivery_hook
):
    """A collecting delivery stays inactive after its task loses its last page."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "active")
    event = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Keep the decision"}
    )
    with service_model.PageTransaction(page_dir) as tx:
        codex_model.append_batch("codex-thread", page_dir, tx, [event])
    record_claim(page_dir, id="successor", harness="codex", agent="Codex")
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": delivery_hook,
            "session_id": "codex-thread",
            "turn_id": "active",
        },
    )
    assert not capsys.readouterr().out
    assert codex_records("codex-thread")[0][1]["state"] == "collecting"
    turn_record_3 = cleanup_model.session_record("codex-thread")
    assert turn_record_3 is not None
    assert bool(turn_record_3["turn_closed"]) == (delivery_hook == "Stop")


@pytest.mark.parametrize("acknowledge", ["receive_delivery", "cmd_delivery_ack"])
def test_codex_hook_pointer_read_cannot_move_its_offer_to_a_newer_turn(
    page_dir, codex_loop, capsys, acknowledge
):
    """Receipt proves the reserved turn, rather than whichever turn reads later."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "offered")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Keep the decision"}
    )
    hooks_model.cmd_hook(
        "codex",
        {"hook_event_name": "Stop", "session_id": "codex-thread", "turn_id": "offered"},
    )
    capsys.readouterr()
    [(path, _)] = codex_records("codex-thread")
    cleanup_model.prompt_turn("codex-thread", "newer")
    delivery_model.cmd_delivery_read(path.stem)
    with pytest.raises(delivery_model.ReceiptRefused, match="receiving turn"):
        getattr(delivery_model, acknowledge)(path.stem)
    assert codex_records("codex-thread")[0][1]["state"] == "hook"
    assert not any(e["kind"] == "pickup" for e in events_model.read_events(page_dir))


@pytest.mark.parametrize(
    ("delivery_hook", "prior_step"),
    [("PostToolUse", True), ("Stop", True), ("Stop", False)],
)
def test_codex_resume_without_input_delivers_in_its_first_hook(
    page_dir, codex_loop, capsys, monkeypatch, tmp_path, delivery_hook, prior_step
):
    """Native turn starts cover resumes that produce no UserPromptSubmit hook.

    The watcher reads that start before reserving the queue, even while the
    resumed turn's first command is running or its first boundary is Stop. Late
    old callbacks and transcript lag cannot replace that provider identity or
    reopen a closed one.
    """
    codex_loop(page_dir)
    source = tmp_path / "rollout.jsonl"
    source.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "codex-thread"}}) + "\n"
    )

    def append(kind, turn, *, partial=False):
        line = json.dumps(
            {
                "type": "event_msg",
                "timestamp": cleanup_model.now_iso(),
                "payload": {"type": kind, "turn_id": turn},
            }
        )
        with source.open("a") as stream:
            stream.write(line if partial else line + "\n")

    append("task_started", "prior")
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "codex-thread",
            "turn_id": "prior",
            "transcript_path": str(source),
        },
    )
    capsys.readouterr()
    if prior_step:
        leases_model.mark_hooks("codex-thread")
    with source.open("a") as stream:
        stream.write(
            json.dumps({"type": "response_item", "payload": {"output": "x" * 150_000}})
            + "\n"
        )
    append("turn_aborted", "prior")
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "Interrupt",
            "session_id": "codex-thread",
            "turn_id": "prior",
        },
    )
    capsys.readouterr()
    append("task_started", "resumed", partial=True)
    before = cleanup_model.session_record("codex-thread")
    assert codex_state_model.sync_transcript_turn("codex-thread") == before
    with source.open("a") as stream:
        stream.write("\n")
    # Hooks start cold in separate processes; their ordering proof must also
    # work without the resident adapter's earlier source reading.
    codex_state_model.transcript_turns.cache_clear()
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Keep the earlier decision",
        },
    )
    monkeypatch.setattr(
        codex_adapter_model,
        "queue_delivery",
        lambda *_: pytest.fail("resumed turn was queued"),
    )
    if prior_step:
        assert not codex_adapter_model._offer_queued_delivery(
            "codex", "codex-thread", None
        )
        turn_record_4 = cleanup_model.session_record("codex-thread")
        assert turn_record_4 is not None
        assert turn_record_4["turn"] == "resumed"
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "prior",
        },
    )
    assert not capsys.readouterr().out
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": delivery_hook,
            "session_id": "codex-thread",
            "turn_id": "resumed",
        },
    )
    offer = json.loads(capsys.readouterr().out)
    [(path, _)] = codex_records("codex-thread")
    context = json.dumps(
        delivery_model.cmd_delivery_read(path.stem),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if delivery_hook == "Stop":
        assert offer == {"decision": "block", "reason": context}
    else:
        assert offer["hookSpecificOutput"]["additionalContext"] == context
    turn_record_5 = cleanup_model.session_record("codex-thread")
    assert turn_record_5 is not None
    assert turn_record_5["turn_closed"] is None
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    delivery_model.cmd_delivery_read(path.stem)
    delivery_model.cmd_delivery_ack(path.stem)
    [pickup] = [e for e in events_model.read_events(page_dir) if e["kind"] == "pickup"]
    assert (pickup["phase"], pickup["turn"], pickup["events"]) == (
        "opened",
        "resumed",
        [comment["id"]],
    )
    append("task_complete", "prior")
    sync_transcript_turn_result = codex_state_model.sync_transcript_turn("codex-thread")
    assert sync_transcript_turn_result is not None
    assert sync_transcript_turn_result["turn_closed"] is None
    append("task_complete", "resumed")
    codex_state_model.transcript_turns.cache_clear()
    closed = codex_state_model.sync_transcript_turn("codex-thread")
    assert closed is not None
    assert closed["turn_closed"] is not None
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "resumed",
        },
    )
    assert cleanup_model.session_record("codex-thread") == closed
    # A newer prompt can precede its native transcript append.
    newest = cleanup_model.prompt_turn("codex-thread", "newest")
    codex_state_model.transcript_turns.cache_clear()
    assert codex_state_model.sync_transcript_turn("codex-thread") == newest
    foreign = tmp_path / "other.jsonl"
    foreign.write_text(source.read_text().replace('"codex-thread"', '"other-session"'))
    assert codex_state_model.sync_transcript_turn("codex-thread", foreign) == newest
    # Replacing the source with an earlier prefix is another lagging reading,
    # rather than proof that the new prompt ended or moved backwards.
    source.write_text("\n".join(source.read_text().splitlines()[:2]) + "\n")
    assert codex_state_model.sync_transcript_turn("codex-thread") == newest


def test_codex_tool_hook_reads_a_quiet_page_without_the_page_model(
    page_dir, codex_loop
):
    """Codex runs its tool hook after every tool call, so where the task's page holds
    no new input the hook reads the claim, the log and the delivery records without
    importing the page model and its validators, which cost about 70 ms of CPU a
    call (measured on macOS). Input to deliver may import them, as may the status
    check each renewal interval (`hook_transport.status_check_due`), which this
    session made a moment ago."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    cleanup_model.session_file(
        "codex-thread", cleanup_model.STATUS_CHECKED_SUFFIX
    ).touch()
    program = """
import json, sys
from leaf.hooks import cmd_hook

cmd_hook(
    "codex",
    {"hook_event_name": "PostToolUse", "session_id": "codex-thread", "turn_id": "user-turn"},
)
heavy = ("jsonschema", "markdown_it", "turbohtml")
print(json.dumps(sorted(name for name in heavy if name in sys.modules)))
"""

    def hook():
        done = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            check=True,
            timeout=STATED_TIMEOUT,
        )
        *offered, imported = done.stdout.splitlines()
        return offered, json.loads(imported)

    assert hook() == ([], [])
    # The same process does reach the page: a comment is offered to the turn.
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Keep the existing layout"},
    )
    [offer], _ = hook()
    assert json.loads(offer)["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


def test_codex_tool_hook_reminds_the_task_of_a_status_line_left_standing(
    page_dir, codex_loop, capsys
):
    """Codex's tool hook carries the same reminder Claude Code's tool batches do
    (`hook_transport.status_reminders`) when the task's working line has stood a
    renewal interval."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    stood = datetime.now().astimezone() - timedelta(minutes=3)
    declare_work(
        page_dir,
        "reading the traces",
        ts=stood.isoformat(timespec="seconds"),
        session="codex-thread",
        turn="user-turn",
    )
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    output = json.loads(capsys.readouterr().out)
    assert (
        '"reading the traces" for 3 min'
        in (output["hookSpecificOutput"]["additionalContext"])
    )


def test_a_page_claimed_mid_turn_keeps_its_first_comment_for_the_tool_hook(
    page_dir, codex_loop, capsys, monkeypatch
):
    """Capture before the first page-bound tool hook still delivers in this turn."""
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
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
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    [(path, record)] = codex_records("codex-thread")
    assert json.loads(
        json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    ) == delivery_model.cmd_delivery_read(path.stem)
    assert (record["state"], record["turn"]) == ("hook", "user-turn")
    delivery_model.cmd_delivery_read(path.stem)
    delivery_model.cmd_delivery_ack(path.stem)
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


def _comment_before_the_first_tool_step(
    page_dir, codex_loop, monkeypatch, tmp_path, observed
):
    """A comment captured while a queue adapter's task runs a turn whose first tool
    step hasn't come, with the pointers the adapter has queued and a function that
    appends a turn's start or end to the task's Codex transcript.

    `observed` is how Leaf learned the turn started: its prompt hook, or, where no
    hook has run yet since an earlier instance ended, as when the desktop app has
    unloaded an idle chat (`state.end_harness_instance`), Codex's transcript, which
    that earlier instance's hooks named."""
    codex_loop(page_dir)
    source = tmp_path / "rollout.jsonl"
    source.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "codex-thread"}}) + "\n"
    )

    def append(kind: str, turn: str) -> None:
        line = {
            "type": "event_msg",
            "timestamp": cleanup_model.now_iso(),
            "payload": {"type": kind, "turn_id": turn},
        }
        with source.open("a") as stream:
            stream.write(json.dumps(line) + "\n")

    def prompt(turn: str) -> None:
        append("task_started", turn)
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "codex-thread",
                "turn_id": turn,
                "transcript_path": str(source),
            },
        )

    if observed == "prompt":
        prompt("user-turn")
    else:
        prompt("earlier-turn")
        append("task_complete", "earlier-turn")
        codex_state_model.sync_transcript_turn("codex-thread")
        cleanup_model.session_file("codex-thread", cleanup_model.HOOKS_SUFFIX).unlink()
        append("task_started", "user-turn")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Rename the column"}
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
    turn_record_6 = cleanup_model.session_record("codex-thread")
    assert turn_record_6 is not None
    assert turn_record_6["turn"] == "user-turn"
    assert not queued
    return comment, queued, append


@pytest.mark.parametrize(
    ("observed", "boundary"),
    [("prompt", "PostToolUse"), ("prompt", "Stop"), ("transcript", "PostToolUse")],
)
def test_a_comment_before_a_turns_first_tool_step_enters_that_turn(
    page_dir, codex_loop, capsys, monkeypatch, tmp_path, observed, boundary
):
    """On the queue route the adapter leaves a running turn's input to its hooks
    from the turn's start, so a comment that arrives before the first tool step
    enters at that step, or at Stop in a turn that runs none, rather than opening
    a turn of its own on a message in the user's name. That holds where the
    transcript shows the turn before its prompt hook has run."""
    lease = adapter_lease("codex-thread", None)
    try:
        comment, queued, _ = _comment_before_the_first_tool_step(
            page_dir, codex_loop, monkeypatch, tmp_path, observed
        )
        capsys.readouterr()
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": boundary,
                "session_id": "codex-thread",
                "turn_id": "user-turn",
            },
        )
        [(path, record)] = codex_records("codex-thread")
        assert (record["state"], record["turn"]) == ("hook", "user-turn")
        assert capsys.readouterr().out
        delivery_model.cmd_delivery_ack(path.stem)
        assert not codex_adapter_model._offer_queued_delivery(
            "codex", "codex-thread", None
        )
        assert not queued
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
    finally:
        leases_model.release_lease(lease)


def test_a_comment_left_to_a_turn_whose_hooks_never_run_is_queued_as_it_ends(
    page_dir, codex_loop, monkeypatch, tmp_path
):
    """A turn whose hooks never run still ends in Codex's transcript, which the
    queue adapter reads, so the comment it held back is queued then, when a
    pointer queued at once would have opened its own turn too."""
    comment, queued, append = _comment_before_the_first_tool_step(
        page_dir, codex_loop, monkeypatch, tmp_path, "transcript"
    )
    append("task_complete", "user-turn")
    assert codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    [(_, _, pointer)] = queued
    assert "<leaf-delivery " in pointer
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["phase"], pickup["events"]) == ("queued", [comment["id"]])


@pytest.mark.parametrize("ending", ["Stop", "Interrupt"])
def test_a_codex_ending_closes_a_page_claimed_before_its_first_tool_hook(
    page_dir, codex_loop, capsys, ending, monkeypatch
):
    """No step-hook completion is needed to end a page acquired mid-turn."""
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    monkeypatch.setattr(
        harness_model.CodexHarness, "lifetime", lambda self: {"pid": os.getpid()}
    )
    with service_model.PageTransaction(page_dir) as page:
        page.take_claim(harness_model.session_harness())
    claim_record_2 = service_model.page_claim(page_dir)
    assert claim_record_2 is not None
    assert claim_record_2["turn"] == "user-turn"
    # A preview owes no watcher, so Stop may end without a watcher lease.
    (page_dir / "preview.json").write_text("{}")
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": ending,
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    assert not capsys.readouterr().out
    claim_record_3 = service_model.page_claim(page_dir)
    assert claim_record_3 is not None
    assert claim_record_3["turn_closed"]
    claim_record_4 = service_model.page_claim(page_dir)
    assert claim_record_4 is not None
    assert claim_record_4["turn"] == "user-turn"
    hook_turn_result = codex_state_model.hook_turn("codex-thread")
    assert hook_turn_result is not None
    assert not hook_turn_result["running"]
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "codex-thread",
            "turn_id": "user-turn",
        },
    )
    assert not capsys.readouterr().out
    claim_record_5 = service_model.page_claim(page_dir)
    assert claim_record_5 is not None
    assert claim_record_5["turn_closed"]
    claim_record_6 = service_model.page_claim(page_dir)
    assert claim_record_6 is not None
    assert claim_record_6["turn"] == "user-turn"


@pytest.mark.parametrize("late", ["notification", "snapshot", "start"])
def test_completed_codex_predecessor_cannot_become_current_again(
    page_dir, codex_loop, late
):
    """Terminal provider identity survives disposal of the observer's live fold."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "setup")
    observer = _observer()
    for turn in ("setup", "idle"):
        observer._read(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": turn, "items": [], "status": "inProgress"},
                },
            }
        )
        observer._read(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": turn, "status": "completed", "items": []},
                },
            }
        )
    ended = cleanup_model.session_record("codex-thread")
    assert ended is not None
    assert ended["turn"] == "idle" and ended["turn_closed"] is not None
    if late == "notification":
        observer._read(
            {
                "method": "item/commandExecution/outputDelta",
                "params": {
                    "threadId": "codex-thread",
                    "turnId": "setup",
                    "itemId": "late",
                    "delta": "background output",
                },
            }
        )
    elif late == "start":
        observer._read(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": "setup", "items": [], "status": "inProgress"},
                },
            }
        )
    else:
        observer._resume(
            {
                "status": {"type": "active", "activeFlags": []},
                "turns": [{"id": "setup", "status": "inProgress", "items": []}],
            },
            observer.lifecycle,
        )
    assert cleanup_model.session_record("codex-thread") == ended
    assert observer.running is None
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "resumed-new-identity",
                    "items": [],
                    "status": "inProgress",
                },
            },
        }
    )
    assert observer.running == "resumed-new-identity"
    assert (
        cleanup_model.session_record("codex-thread")["turn"] == "resumed-new-identity"
    )


@pytest.mark.parametrize(
    "source",
    ["closed-lifecycle", "unloaded-snapshot", "unknown-output"],
)
def test_codex_observer_does_not_invent_a_turn_from_historical_evidence(
    page_dir, codex_loop, source
):
    """Only a live start or exact delivery can introduce an observed turn."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "current")
    cleanup_model.close_session_turn("codex-thread", "current")
    observer = _observer()
    ended = cleanup_model.session_record("codex-thread")
    if source == "closed-lifecycle":
        observer._read(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": "current", "items": [], "status": "inProgress"},
                },
            }
        )
    elif source == "unknown-output":
        observer._read(
            {
                "method": "item/commandExecution/outputDelta",
                "params": {
                    "threadId": "codex-thread",
                    "turnId": "unknown-old",
                    "itemId": "late",
                    "delta": "background output",
                },
            }
        )
    else:
        terminal = {
            "id": "historical",
            "status": "interrupted",
            "items": [],
            "itemsView": "notLoaded",
        }
        running = {"id": "historical", "status": "inProgress", "items": []}
        observer._reconcile(terminal)
        observer._reconcile(running)
    assert cleanup_model.session_record("codex-thread") == ended
    assert observer.running is None
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "resumed-new-identity",
                    "items": [],
                    "status": "inProgress",
                },
            },
        }
    )
    assert observer.running == "resumed-new-identity"
    assert (
        cleanup_model.session_record("codex-thread")["turn"] == "resumed-new-identity"
    )


def test_superseded_unfinished_codex_fold_cannot_reopen_on_late_output(
    page_dir, codex_loop
):
    """A fold kept for historical recovery cannot restore its earlier live epoch."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old")
    observer = _observer()
    for turn in ("old", "new"):
        observer._read(
            {
                "method": "turn/started",
                "params": {
                    "threadId": "codex-thread",
                    "turn": {"id": turn, "items": [], "status": "inProgress"},
                },
            }
        )
    # The old completion was missed; its fold remains until history is hydrated.
    observer._read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {"id": "new", "status": "completed", "items": []},
            },
        }
    )
    ended = cleanup_model.session_record("codex-thread")
    assert "old" in observer.turns
    observer._read(
        {
            "method": "item/commandExecution/outputDelta",
            "params": {
                "threadId": "codex-thread",
                "turnId": "old",
                "itemId": "late",
                "delta": "background output",
            },
        }
    )
    assert cleanup_model.session_record("codex-thread") == ended
    assert observer.running is None


def test_a_late_codex_tool_hook_cannot_replace_a_newer_turn(page_dir, codex_loop):
    """An old async callback neither captures input nor reopens its ended turn."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "old-turn")
    old = cleanup_model.open_session_turn("codex-thread", "old-turn")
    cleanup_model.close_session_turn("codex-thread", "old-turn")
    cleanup_model.close_session_turn("codex-thread", "old-turn")
    cleanup_model.prompt_turn("codex-thread", "new-turn")
    cleanup_model.open_session_turn("codex-thread", "new-turn")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "For the new turn"}
    )
    assert codex_model.offer_hook_delivery("codex-thread", old) == (None, old)
    cleanup_model.close_session_turn("codex-thread", "old-turn")
    claim_record_7 = service_model.page_claim(page_dir)
    assert claim_record_7 is not None
    assert claim_record_7["turn"] == "new-turn"
    hook_turn_result_2 = codex_state_model.hook_turn("codex-thread")
    assert hook_turn_result_2 is not None
    assert hook_turn_result_2["running"]
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
    leases_model.mark_hooks("codex-thread")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Before you finish"}
    )
    prompts = []

    def stale_activity(session_id):
        prompt, _ = codex_model.offer_hook_delivery(
            session_id, cleanup_model.session_record(session_id)
        )
        prompts.append(prompt)

    monkeypatch.setattr(codex_adapter_model, "delivery_turn", stale_activity)
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    assert prompts[0] is not None
    assert not queued
    [(path, record)] = codex_records("codex-thread")
    assert record["state"] == "hook"
    delivery_model.cmd_delivery_read(path.stem)
    delivery_model.cmd_delivery_ack(path.stem)
    assert not codex_records("codex-thread")
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert (pickup["phase"], pickup["turn"]) == ("opened", "user-turn")


@pytest.mark.parametrize("loss", ["transfer", "remove"])
def test_a_codex_hook_read_survives_page_loss_after_offer(
    page_dir, codex_loop, tmp_path, loss
):
    """A lost batch page cannot prevent receipt of the envelope's healthy sibling."""
    sibling = tmp_path / "sibling"
    shutil.copytree(page_dir, sibling)
    codex_loop(page_dir)
    codex_loop(sibling)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    leases_model.mark_hooks("codex-thread")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Retain this input"}
    )
    settled = append_carried_log_record(
        sibling, {"kind": "comment", "author": "user", "text": "Already settled"}
    )
    resolved = append_carried_log_record(
        sibling, {"kind": "resolve", "author": "user", "parent": settled["id"]}
    )
    acknowledge_through(sibling, settled["seq"])
    codex_model.offer_hook_delivery(
        "codex-thread", cleanup_model.session_record("codex-thread")
    )
    [(path, record)] = codex_records("codex-thread")
    assert len(record["batches"]) == 2
    if loss == "transfer":
        record_claim(page_dir, id="successor", harness="codex", agent="Codex")
    else:
        shutil.rmtree(page_dir)
    envelope = delivery_model.cmd_delivery_read(path.stem)
    with pytest.raises(delivery_model.ReceiptRefused, match="no longer owns"):
        delivery_model.cmd_delivery_ack(path.stem)
    assert {
        event["id"] for batch in envelope["batches"] for event in batch["events"]
    } == {comment["id"], resolved["id"]}
    if loss == "transfer":
        claim_record_8 = service_model.page_claim(page_dir)
        assert claim_record_8 is not None
        assert claim_record_8["id"] == "successor"
        assert acknowledged_through(page_dir) == 0
        assert not any(
            event["kind"] == "pickup" for event in events_model.read_events(page_dir)
        )
    assert acknowledged_through(sibling) == resolved["seq"]
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
    leases_model.mark_hooks("codex-thread")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "One more question"}
    )
    prompt, _ = codex_model.offer_hook_delivery(
        "codex-thread", cleanup_model.session_record("codex-thread")
    )
    [(path, _)] = codex_records("codex-thread")
    lease = adapter_lease("codex-thread", None)
    lease_path = leases_model.waiter_lease_path(page_dir, "codex-thread")
    assert lease_path is not None
    waiter = leases_model.take_wait_lease(lease_path)
    assert waiter
    try:
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": ending,
                "session_id": "codex-thread",
                "turn_id": "user-turn",
            },
        )
        assert not capsys.readouterr().out
        assert codex_state_model.delivery_turn("codex-thread") is None
        # A late tool hook cannot reopen the turn or duplicate the pointer.
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "PostToolUse",
                "session_id": "codex-thread",
                "turn_id": "user-turn",
            },
        )
        assert not capsys.readouterr().out
        queued = []
        monkeypatch.setattr(
            codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
        )
        assert codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
        assert prompt is not None
        assert json.loads(prompt) == delivery_model.cmd_delivery_read(path.stem)
        assert [args[2] for args in queued] == [
            delivery_model.delivery_pointer_prompt(path.stem)
        ]
        assert not codex_model.recover_codex_receipt("codex-thread")
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


@pytest.mark.parametrize("wake", ["ok", "failed", "terminal"])
def test_desktop_wake_follows_queue_acceptance_without_resending(
    page_dir, codex_loop, monkeypatch, capsys, wake
):
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Wake the chat"}
    )
    codex_model.offer_hook_delivery(
        "codex-thread", cleanup_model.session_record("codex-thread")
    )
    [(path, _)] = codex_records("codex-thread")
    cleanup_model.close_session_turn("codex-thread", "user-turn")
    queued, opened = [], []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv(
        "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
        "codex_exec" if wake == "terminal" else "Codex Desktop",
    )

    def open_app(arguments, **kwargs):
        # A failed wake must leave the accepted delivery intact, so the next
        # adapter pass cannot send its pointer a second time.
        record = files_model.read_json(path.parent / "history" / path.name)
        assert record["state"] == "queued"
        opened.append(arguments)
        if wake == "failed":
            raise subprocess.CalledProcessError(1, arguments)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(subprocess, "run", open_app)
    assert codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    assert len(queued) == 1
    assert opened == (
        []
        if wake == "terminal"
        else [["open", "-g", "codex://threads/wake/codex-thread"]]
    )
    assert ("input remains queued" in capsys.readouterr().err) == (wake == "failed")


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
    leases_model.mark_hooks("codex-thread")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
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
        first_path.parent / "history" / first_path.name
    )
    assert first_delivery["state"] == "queued"
    payload = files_model.read_json(delivery_model.delivery_path(first_path.stem))
    assert [
        event["id"] for batch in payload["batches"] for event in batch["events"]
    ] == ["first"]

    assert not codex_model.recover_codex_receipt("codex-thread")
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


def _queued_with_lost_acceptance(page_dir, monkeypatch) -> tuple[Path, dict, list]:
    """A comment the queue adapter handed to `codex queue`, then failed before
    recording that the queue accepted it, as an adapter that dies or a state write
    that fails in that gap leaves it; with the delivery's record and the pointers
    queued so far."""
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Name the release"}
    )
    codex_model.offer_hook_delivery(
        "codex-thread", cleanup_model.session_record("codex-thread")
    )
    [(path, _)] = codex_records("codex-thread")
    cleanup_model.close_session_turn("codex-thread", "user-turn")
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )

    def lost_acceptance(*args, **kwargs):
        raise OSError("state home unavailable")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(
            codex_adapter_model, "accept_codex_delivery", lost_acceptance
        )
        with pytest.raises(OSError, match="state home unavailable"):
            codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    return path, comment, queued


def _ack_in(turn: str, delivery_id: str, capsys) -> list[dict]:
    """Acknowledge a delivery in a turn of its own, as a queued turn opening on its
    pointer does, and return the notes the ack printed."""
    cleanup_model.prompt_turn("codex-thread", turn)
    cleanup_model.open_session_turn("codex-thread", turn)
    capsys.readouterr()
    delivery_model.cmd_delivery_ack(delivery_id)
    notes = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    cleanup_model.close_session_turn("codex-thread", turn)
    return notes


@pytest.mark.parametrize("answered", [True, False])
def test_a_codex_delivery_queued_twice_tells_its_second_turn_it_repeats(
    page_dir, codex_loop, monkeypatch, capsys, answered
):
    """`codex queue` takes no message id, so the adapter's retry queues the same
    pointer again and Codex runs a turn for each. The second turn's ack says an
    earlier turn already picked the delivery up, and names what its updates still
    owe, so that turn repeats no work."""
    codex_loop(page_dir)
    path, comment, queued = _queued_with_lost_acceptance(page_dir, monkeypatch)
    assert codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    pointer = delivery_model.delivery_pointer_prompt(path.stem)
    assert [args[2] for args in queued] == [pointer, pointer]

    assert _ack_in("first-queued-turn", path.stem, capsys) == []
    owed = f"`leaf thread reply {delivered_ref(page_dir, comment['id'])}`"
    if answered:
        thread_model.post_reply(
            page_dir, {"parent": comment["id"], "responds": comment["id"]}, "Named it."
        )
    [repeat] = _ack_in("second-queued-turn", path.stem, capsys)
    assert repeat["code"] == "delivery-repeated"
    assert repeat["values"]["turns"] == ["first-queued-turn"]
    assert repeat["values"]["answers"] == ([] if answered else [owed])


def test_a_queued_turn_that_acks_before_the_retry_takes_the_delivery_once(
    page_dir, codex_loop, monkeypatch, capsys
):
    """A turn that opens on the first pointer and acknowledges it before the
    adapter retries proves the queue took it, so the ack accepts the delivery and
    the adapter queues nothing more."""
    codex_loop(page_dir)
    path, comment, queued = _queued_with_lost_acceptance(page_dir, monkeypatch)

    assert _ack_in("queued-turn", path.stem, capsys) == []
    assert not codex_adapter_model._offer_queued_delivery("codex", "codex-thread", None)
    assert len(queued) == 1
    pickups = [
        (event["phase"], event["turn"], event["events"])
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert pickups == [
        ("queued", None, [comment["id"]]),
        ("opened", "queued-turn", [comment["id"]]),
    ]


@pytest.mark.parametrize("transport", ["hook", "app-server", "queue"])
def test_codex_acceptance_survives_interruption_before_page_receipt(
    page_dir, codex_loop, monkeypatch, transport
):
    """Every transport commits acceptance before page IO, and recovery receipts it once."""
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "user-turn")
    cleanup_model.open_session_turn("codex-thread", "user-turn")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Do not lose this"}
    )
    if transport == "hook":
        leases_model.mark_hooks("codex-thread")
    codex_model.offer_hook_delivery(
        "codex-thread", cleanup_model.session_record("codex-thread")
    )
    [(path, _)] = codex_records("codex-thread")
    if transport == "queue":
        cleanup_model.close_session_turn("codex-thread", "user-turn")
    queued = []
    monkeypatch.setattr(
        codex_adapter_model, "queue_delivery", lambda *args: queued.append(args)
    )

    def failed_pickup(*args, **kwargs):
        raise OSError("receipt storage unavailable")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(codex_model, "record_pickup", failed_pickup)
        with pytest.raises(OSError, match="receipt storage unavailable"):
            if transport == "hook":
                delivery_model.cmd_delivery_read(path.stem)
                delivery_model.cmd_delivery_ack(path.stem)
            elif transport == "app-server":
                observer = _observer()
                assert observer._observe_lifecycle("user-turn")
                observer._fold("user-turn", path.stem, follow=True)
            else:
                codex_adapter_model._offer_queued_delivery(
                    "codex", "codex-thread", None
                )
    accepted = files_model.read_json(path)
    assert accepted["state"] == ("queued" if transport == "queue" else "opened")
    assert accepted["pending"] == [0]
    assert acknowledged_through(page_dir) == 0
    assert bool(queued) == (transport == "queue")
    with monkeypatch.context() as interrupted:
        interrupted.setattr(codex_model, "_receipt_completed", failed_pickup)
        with pytest.raises(OSError, match="receipt storage unavailable"):
            codex_model.recover_codex_receipt("codex-thread")
    assert acknowledged_through(page_dir) == comment["seq"]
    assert files_model.read_json(path)["pending"] == [0]
    rename = Path.replace

    def failed_archive(source, destination):
        if source == path:
            raise OSError("archive storage unavailable")
        return rename(source, destination)

    with monkeypatch.context() as interrupted:
        interrupted.setattr(Path, "replace", failed_archive)
        with pytest.raises(OSError, match="archive storage unavailable"):
            codex_model.recover_codex_receipt("codex-thread")
    assert files_model.read_json(path)["pending"] == []
    assert not codex_model.recover_codex_receipt("codex-thread")
    assert (path.parent / "history" / path.name).is_file()
    assert not codex_records("codex-thread")
    [pickup] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert pickup["events"] == [comment["id"]]
    assert (pickup["phase"], pickup["turn"]) == (
        ("queued", None) if transport == "queue" else ("opened", "user-turn")
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
    assert record["state"] == "opened"
    assert record["pending"] == [0]
    assert acknowledged_through(page_dir) == 0
    cleanup_model.close_session_turn("hosted-thread", "provider-turn")
    for _ in range(2):
        codex_model.open_app_server_delivery(
            page_dir,
            "hosted-thread",
            prepared.payload["id"],
            (comment["id"],),
            "provider-turn",
        )
    claim_record_9 = service_model.page_claim(page_dir)
    assert claim_record_9 is not None
    assert claim_record_9["turn_closed"]
    assert acknowledged_through(page_dir) == comment["seq"]
    assert not codex_records("hosted-thread")
    history = files_model.read_json(path.parent / "history" / path.name)
    assert (history["state"], history["turn"]) == ("opened", "provider-turn")
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


def spawn_codex_adapter(spawn, program, **options) -> subprocess.Popen:
    """Run `leaf codex run` as `leaf page claim` does, accepting its announcement,
    so the adapter returns holding its leases with its start committed."""
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
        pass_fds=(end.fileno(),),
        **options,
    )
    end.close()
    caller.settimeout(STATED_TIMEOUT)
    with caller, caller.makefile("rb") as reader:
        assert json.loads(reader.readline()) == {}
        caller.sendall(b"\n")
        assert json.loads(reader.readline()) == {}
    return adapter


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


def test_codex_adapter_keeps_transferred_input_unreceived(
    codex_claimed_page, spawn, codex_env, tmp_path
):
    page = codex_claimed_page
    program, log = fake_codex_cli(tmp_path)
    session_model.cmd_waiting(page)
    queue_wait = tmp_path / "held-queue"
    adapter = spawn_codex_adapter(
        spawn,
        program,
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

    assert acknowledged_through(page) == 0
    assert page_state(page)["pending"] == 1
    assert service_model.page_claim(page) == successor
    pickups = [
        event for event in events_model.read_events(page) if event["kind"] == "pickup"
    ]
    assert pickups == []


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
        assert queued["kind"] == "working"
        assert [item["stage"] for item in queued["obligations"]] == ["queued"]

        declare_idle(page)
    finally:
        cleanup_model.end_session("codex-thread")


def test_failed_codex_delivery_start_restores_the_previous_page_claim(
    page_dir, under_codex, codex_env, tmp_path
):
    program, log = fake_codex_cli(tmp_path)
    record_claim(page_dir, id="previous", pid=os.getpid())
    previous = service_model.page_claim(page_dir)
    failed = under_codex(
        shlex.join(claim_command(page_dir, program)),
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


@pytest.mark.parametrize("pending", [False, True])
def test_a_codex_stop_cannot_adopt_a_prompt_renewed_during_its_policy(
    page_dir, codex_loop, monkeypatch, capsys, pending
):
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "provider")
    waiter = _watched(page_dir)
    adapter = adapter_lease("codex-thread", None)
    if pending:
        append_carried_log_record(
            page_dir,
            {"kind": "comment", "author": "user", "text": "For the new prompt"},
        )
    policy = hook_transport_model.stop_continues
    newer = []

    def supersede(plans, handing, **policy_input):
        newer.append(cleanup_model.prompt_turn("codex-thread", "provider"))
        return policy(plans, handing, **policy_input)

    monkeypatch.setattr(hook_transport_model, "stop_continues", supersede)
    try:
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "provider",
            },
        )
        assert capsys.readouterr().out == ""
        assert cleanup_model.session_record("codex-thread") == newer[0]
        assert not codex_records("codex-thread")
        assert acknowledged_through(page_dir) == 0
    finally:
        adapter.close()
        leases_model.release_lease(waiter)


def test_a_codex_stop_keeps_the_revision_returned_by_its_offer(
    page_dir, codex_loop, monkeypatch, capsys
):
    """A prompt can renew the same provider id after an offer returns no pointer.
    That Stop still belongs to the offer's exact revision, never the newest one.
    Stop offers where no App Server adapter runs, as for a task that waits itself.
    """
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "provider")
    waiter = _watched(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "An old unanswered move"},
    )
    receive_through(page_dir, last_deliverable_seq(page_dir))
    cleanup_model.prompt_turn("codex-thread", "provider")
    offering = codex_model.offer_hook_delivery
    newer = []

    def renew_after_offer(*args, **kwargs):
        result = offering(*args, **kwargs)
        newer.append(cleanup_model.prompt_turn("codex-thread", "provider"))
        return result

    monkeypatch.setattr(codex_model, "offer_hook_delivery", renew_after_offer)
    try:
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "provider",
            },
        )
        assert capsys.readouterr().out == ""
        assert cleanup_model.session_record("codex-thread") == newer[0]
        assert not codex_records("codex-thread")
    finally:
        leases_model.release_lease(waiter)
