"""Receiving a delivery: the immutable delivery a receipt confirms, the cursor it
advances, `wait --ack` re-arming the watch, and the pointer a reader confirms only
once it has read it."""

import json
import os
import shutil
import subprocess

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    STATED_TIMEOUT,
    _interaction_prompt_evidence,
    append_carried_log_record,
    delivery_through,
    fifo_writer,
    freeze_events,
    hold_status_read,
    page_state,
    printed,
    record_claim,
    serving,
    spawn_probe,
    wait_for,
    woken,
    yaml_document,
)
from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model


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
    with pytest.raises(delivery_model.ReceiptRefused):
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
    payload = delivery_model.freeze_delivery(batches)
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
    cleanup_model.close_session_turn(session_id)
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
    assert service_model.claim_page(page_dir)
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
    """A persistent watcher ends the re-arm the way it ends a bare `leaf wait`, on
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
    assert "the page closed" not in err
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


@pytest.mark.parametrize("acknowledge", ["receive_delivery", "cmd_delivery_ack"])
def test_an_explicit_acknowledgement_cannot_reopen_a_known_provider_turn(
    claimed, capsys, acknowledge
):
    """The explicit consumer route preserves provider lifecycle authority."""
    cleanup_model.prompt_turn("s1", "provider-turn")
    cleanup_model.close_session_turn("s1", "provider-turn")
    ended = cleanup_model.session_record("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Later input"}
    )
    serving(claimed, 1)
    assert session_model.cmd_wait(claimed) == 0
    payload, _, _ = printed(capsys.readouterr().out)
    with pytest.raises(delivery_model.ReceiptRefused, match="turn has ended"):
        getattr(delivery_model, acknowledge)(payload["id"])
    assert cleanup_model.session_record("s1") == ended
    assert page_state(claimed)["pending"] == 1


def test_reading_a_pointer_never_confirms_unread_input(claimed, monkeypatch, capsys):
    """Both failed output and a successful read leave receipt to the reader."""
    event = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    with service_model.PageTransaction(claimed) as page:
        payload = delivery_model.freeze_delivery(
            [delivery_model.batch_data(claimed, page, [event])]
        )
    import builtins

    def broken_print(*args, **kwargs):
        raise BrokenPipeError("consumer disappeared")

    with monkeypatch.context() as broken:
        broken.setattr(builtins, "print", broken_print)
        with pytest.raises(BrokenPipeError):
            delivery_model.cmd_delivery_read(payload["id"])
    assert events_model.read_cursor(claimed) < event["seq"]
    delivery_model.cmd_delivery_read(payload["id"])
    output = json.loads(capsys.readouterr().out)
    assert events_model.read_cursor(claimed) < event["seq"]
    assert not delivery_model.pickup_receipts(
        events_model.read_events(claimed), phase="opened"
    )
    assert f"leaf delivery ack {payload['id']}" in output["acknowledge"]
    delivery_model.cmd_delivery_ack(payload["id"])
    delivery_model.cmd_delivery_ack(payload["id"])
    assert events_model.read_cursor(claimed) == event["seq"]
    assert (
        len(
            delivery_model.pickup_receipts(
                events_model.read_events(claimed), phase="opened"
            )
        )
        == 1
    )


@pytest.mark.parametrize("transport", ["pointer", "wait"])
def test_a_large_pointer_read_is_bounded_and_losslessly_paged(
    claimed, capsys, transport
):
    """One huge message and escaped Unicode still fit the reader's output budget."""
    event = append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "user", "text": ("A\\B\n🪴" * 9000)},
    )
    with service_model.PageTransaction(claimed) as page:
        payload = delivery_model.freeze_delivery(
            [delivery_model.batch_data(claimed, page, [event])]
        )
    if transport == "pointer":
        delivery_model.cmd_delivery_read(payload["id"])
        output = capsys.readouterr().out
    else:
        with service_model.PageTransaction(claimed) as page:
            reading = session_model.PageTick(
                claimed, page.status, [event], True, "watching", False, None, page
            )
            output = session_model.delivery_json(reading, None)
        payload = delivery_model.read_delivery(json.loads(output)["id"])
    assert len(output.encode("utf-8")) <= 24000
    first = json.loads(output)
    parts = [first["text"]]
    assert first["part"] == 1 and first["parts"] > 1
    assert first["acknowledge"] is None
    for part in range(2, first["parts"] + 1):
        delivery_model.cmd_delivery_read(payload["id"], part=part)
        output = capsys.readouterr().out
        assert len(output.encode("utf-8")) <= 24000
        reading = json.loads(output)
        parts.append(reading["text"])
    reconstructed = json.loads("".join(parts))
    assert reconstructed["batches"] == payload["batches"]
    assert reading["next"] is None
    assert (
        f"leaf delivery ack {payload['id']}"
        if transport == "pointer"
        else f"leaf wait --ack {payload['id']}"
    ) in reading["acknowledge"]
    assert events_model.read_cursor(claimed) == 0
    delivery_model.cmd_delivery_ack(payload["id"])
    assert events_model.read_cursor(claimed) == event["seq"]


@pytest.mark.parametrize("harness_name", ["claude-code", "pi", "codex"])
def test_explicit_pointer_confirmation_refuses_a_transferred_page(
    page_dir, monkeypatch, harness_name
):
    """An explicit acknowledgement cannot report success after ownership transfer."""
    event = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    owner = harness_model.EmbeddedHarness("reader", "Codex", os.getpid())
    prepared = codex_model.prepare_codex_delivery(page_dir, owner)
    cleanup_model.start_session_turn(
        "reader", "reader-turn", cleanup_model.session_record("reader")
    )
    if harness_name == "codex":
        # Queue/provider acceptance is already durable; this reader still needs
        # to attest entry into its current turn under current ownership.
        codex_model.accept_codex_delivery(
            "reader", prepared.payload["id"], "reader-turn"
        )
    with service_model.PageTransaction(page_dir) as page:
        page.take_claim(
            harness_model.EmbeddedHarness("successor", "Codex", os.getpid())
        )
    before = events_model.read_events(page_dir)
    cursor = events_model.read_cursor(page_dir)
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    variable = {
        "claude-code": "CLAUDE_CODE_SESSION_ID",
        "pi": "PI_SESSION_ID",
        "codex": "LEAF_SESSION_ID",
    }[harness_name]
    monkeypatch.setenv(variable, "reader")
    result = CliRunner().invoke(
        cli_model.cli, ["delivery", "ack", prepared.payload["id"]]
    )
    assert result.exit_code == 1, result.output
    assert "no longer owns" in result.output
    assert events_model.read_cursor(page_dir) == cursor
    assert events_model.read_events(page_dir) == before
    assert service_model.page_claim(page_dir)["id"] == "successor"
    assert event["id"] in {record["id"] for record in before}
