"""State-home records every installed Leaf shares: their readers share one shape
boundary, and a record whose pages are gone retires whichever Leaf wrote it."""

from copy import deepcopy

from interact_support import append_carried_log_record, published

from leaf import codex as codex_model
from leaf.delivery import batch_data, freeze_delivery
from leaf.service import PageTransaction
from leaf.state import state_home, write_json


def test_live_and_archived_readers_ignore_foreign_formats_and_unknown_states(
    tmp_path, page_dir
):
    page = published(page_dir)
    event = append_carried_log_record(
        page,
        {
            "kind": "comment",
            "id": "captured",
            "author": "user",
            "text": "Please revise.",
        },
    )
    with PageTransaction(page) as transaction:
        captured = batch_data(page, transaction, [event])
    captured.update(session="concurrent-task")
    accepted = {
        "format": codex_model.RECORD.format,
        "state": "queued",
        "created_at": 1,
        "pending": [0],
        "batches": [
            {
                "page": str(page),
                "session": "concurrent-task",
                "events": [{"id": event["id"], "seq": event["seq"]}],
            }
        ],
    }
    unreadable = [
        {**accepted, "format": "another-format"},
        {**accepted, "state": "a-later-state"},
        {"format": "another-format"},
    ]
    collecting = deepcopy(accepted)
    collecting["state"] = "collecting"
    collecting.pop("pending")
    collecting["batches"] = [deepcopy(captured)]

    for index, record in enumerate(unreadable):
        identity = f"{index:08x}"
        freeze_delivery([captured], delivery_id=identity)
        live = codex_model.record_path("concurrent-task", identity)
        archived = live.parent / "history" / live.name
        archived.parent.mkdir(parents=True, exist_ok=True)
        write_json(live, record)
        write_json(archived, record)
        assert codex_model.read_task_delivery("concurrent-task", identity) is None
        assert (
            codex_model.delivery_stream_reply_target("concurrent-task", identity)
            is None
        )
        assert (
            codex_model.accept_codex_delivery("concurrent-task", identity, None) == []
        )
        assert live.exists() and archived.exists()
        gone = deepcopy(record)
        if gone.get("batches") and "page" in gone["batches"][0]:
            gone["batches"][0]["page"] = str(tmp_path / "gone")
        write_json(live, gone)
        write_json(archived, gone)

    # A record whose pages are gone goes whether this Leaf reads it or not; one
    # that names no page stays.
    assert codex_model.delivery_records("concurrent-task") == []
    assert not codex_model.recover_codex_receipt("concurrent-task")
    codex_model.retire_gone_task_records()
    pageless = {
        f"{index:08x}.json"
        for index, record in enumerate(unreadable)
        if "page" not in (record.get("batches") or [{}])[0]
    }
    assert pageless
    live = codex_model.record_path("concurrent-task", "00000000").parent
    assert {path.name for path in live.glob("*.json")} == pageless
    assert {path.name for path in live.joinpath("history").glob("*.json")} == pageless

    missing_envelope = codex_model.record_path("concurrent-task", "fffffffd")
    write_json(missing_envelope, accepted)
    assert codex_model.read_record(missing_envelope) is None

    freeze_delivery([captured], delivery_id="ffffffff")
    valid = codex_model.record_path("concurrent-task", "ffffffff")
    codex_model.write_record(
        valid, codex_model.Accepted(1, tuple(accepted["batches"]), (0,))
    )
    assert codex_model.delivery_records("concurrent-task") == [
        (valid, codex_model.read_record(valid))
    ]
    assert isinstance(
        codex_model.read_task_delivery("concurrent-task", "ffffffff"),
        codex_model.Accepted,
    )
    collecting["batches"][0]["threads"][0]["title"] = None
    current = codex_model.record_path("concurrent-task", "fffffffe")
    codex_model.write_record(
        current, codex_model.Collecting(1, (collecting["batches"][0],))
    )
    assert codex_model.read_record(current) == codex_model.Collecting(
        1, (collecting["batches"][0],)
    )


def test_a_record_of_gone_pages_retires_at_any_format(tmp_path, page_dir):
    """Freezing a delivery retires every envelope whose pages are gone."""
    page = published(page_dir)
    event = append_carried_log_record(
        page, {"kind": "comment", "id": "c", "author": "user", "text": "Hi."}
    )
    with PageTransaction(page) as transaction:
        captured = batch_data(page, transaction, [event])
    deliveries = state_home() / "deliveries"
    deliveries.mkdir(parents=True, exist_ok=True)
    envelopes = {name: deliveries / f"{name}.json" for name in ("00000001", "00000002")}
    for name, on in (("00000001", tmp_path / "gone"), ("00000002", page)):
        write_json(envelopes[name], {"format": "x", "batches": [{"page": str(on)}]})
    freeze_delivery([captured], delivery_id="00000003")
    assert not envelopes["00000001"].exists()
    assert envelopes["00000002"].exists()
