"""Tests scheduled by the measured cost of their boundary."""

import os
import shutil
import subprocess

from interact_support import (
    STATED_TIMEOUT,
    acknowledged_through,
    append_carried_log_record,
    delivery_through,
    freeze_events,
    held_selection,
    owed_answers,
    printed,
    serving,
    spawn_probe,
    wait_for,
)

from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model


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
    claim_record = service_model.page_claim(claimed)
    assert claim_record is not None
    session_id = claim_record["id"]
    cleanup_model.close_session_turn(session_id)
    cleanup_model.prompt_turn(session_id)
    deliveries = []
    for page in pages[:2]:
        comment = append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Please answer"}
        )
        deliveries.append(freeze_events(page, [comment]))
    arrivals = [tmp_path / f"sweep-{number}" for number in range(2)]
    probe = """\
import sys
from leaf import delivery

original_lock = delivery.flocked
def synchronized_lock(*args, **kwargs):
    Path(os.environ["ARRIVAL"]).write_text("ready", encoding="utf-8")
    if not sys.stdin.readline():
        raise SystemExit(0)
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
            stdin=subprocess.PIPE,
        )
        for page, payload, arrival in zip(pages[:2], deliveries, arrivals, strict=True)
    ]
    wait_for(
        lambda: all(arrival.exists() for arrival in arrivals),
        bool,
        failure="both receipts did not reach their shared session observation",
    )
    for consumer in consumers:
        consumer.stdin.write("continue\n")
        consumer.stdin.flush()
    for consumer in consumers:
        out, err = consumer.communicate(timeout=STATED_TIMEOUT)
        assert consumer.returncode == 0, out + err
    for page in pages:
        claim_record_2 = service_model.page_claim(page)
        assert claim_record_2 is not None
        assert claim_record_2["turn_closed"] is None
    for page in pages[:2]:
        assert acknowledged_through(page) == 1
        [pickup] = [
            event
            for event in events_model.read_events(page)
            if event["kind"] == "pickup"
        ]
        assert pickup["phase"] == "opened"
        assert (owed_answers(page)[0]["state"], owed_answers(page)[0]["seen"]) == (
            "waiting",
            True,
        )
    assert acknowledged_through(silent) == 0


def test_ack_rearm_keeps_the_other_pages_when_its_batch_page_transfers(
    page_dir, tmp_path, spawn, monkeypatch, codex_loop
):
    """The acknowledged page is a delivery coordinate, not the next wait's target.

    Hold its read after the session-wide watcher selected both pages, then
    transfer that page and speak on the other one. The transfer must drop
    only its page: ending the wait there leaves the other page silently
    unwatched until a later hook repairs it.
    """
    other = tmp_path / "second-page"
    shutil.copytree(page_dir, other)
    serving(page_dir, 1)
    serving(other, 2)
    codex_loop(page_dir)
    codex_loop(other)
    session_model.cmd_waiting(page_dir)
    session_model.cmd_waiting(other)
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "first", "author": "user", "text": "one"},
    )
    delivery_model.cmd_delivery_ack(delivery_through(page_dir, first["seq"]))
    selected = tmp_path / "selected"
    waiting = spawn(
        held_selection(selected, page_dir, "wait"),
        env=os.environ,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(selected.exists, bool, failure="the rearm never selected its batch page")
    identity = harness_model.session_harness()
    assert identity is not None
    lease_path = leases_model.waiter_lease_path(page_dir, identity.session)
    assert acknowledged_through(page_dir) == first["seq"]
    assert lease_path is not None
    assert leases_model.lock_is_held(lease_path)
    assert waiting.poll() is None

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "successor")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page_dir)
    append_carried_log_record(
        other,
        {"kind": "comment", "id": "second", "author": "user", "text": "two"},
    )

    out, err = waiting.communicate(input="continue\n", timeout=STATED_TIMEOUT)
    assert waiting.returncode == 0, f"{out}{err}"
    _, header, [event] = printed(out)
    assert header["page"] == str(other)
    assert (event["id"], event["text"]) == ("second", "two")
    assert acknowledged_through(other) == 0
    claim_record_4 = service_model.page_claim(page_dir)
    assert claim_record_4 is not None
    assert claim_record_4["id"] == "successor"
