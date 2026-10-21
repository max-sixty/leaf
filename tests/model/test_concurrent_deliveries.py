"""State-home records every installed Leaf shares: their readers share one shape
boundary, and a record whose pages are gone retires whichever Leaf wrote it."""

from copy import deepcopy

from interact_support import append_carried_log_record, published
from leaf import codex as codex_model
from leaf import presence as presence_model
from leaf.delivery import batch_data, freeze_delivery
from leaf.leases import release_lease, take_lease
from leaf.schema import SERVER_LOCK
from leaf.server_rows import row_path
from leaf.service import PageTransaction
from leaf.state import state_home, write_json


def test_live_and_archived_readers_ignore_records_with_missing_fields(
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
    unreadable = []
    for field in accepted:
        record = deepcopy(accepted)
        del record[field]
        unreadable.append(record)
    for field in accepted["batches"][0]:
        record = deepcopy(accepted)
        del record["batches"][0][field]
        unreadable.append(record)
    # A state this Leaf does not know, or one whose own fields are missing.
    for state in ("hook", "opened", "a-later-state"):
        unreadable.append({**accepted, "state": state})
    collecting = deepcopy(accepted)
    collecting["state"] = "collecting"
    collecting.pop("pending")
    collecting["batches"] = [deepcopy(captured)]
    # Fields only a collecting record, or one kind of answer, requires.
    for field in ("through_seq", "threads"):
        record = deepcopy(collecting)
        del record["batches"][0][field]
        unreadable.append(record)
    for field in ("threads", "kind"):
        record = deepcopy(collecting)
        del record["batches"][0]["events"][0][field]
        unreadable.append(record)
    for answer in (
        {"kind": "reply", "responds": "captured"},
        {"kind": "reply", "parent": "thread"},
        {"kind": "markup"},
    ):
        record = deepcopy(collecting)
        record["batches"][0]["events"][0]["answer"] = answer
        unreadable.append(record)

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
    write_json(valid, accepted)
    assert codex_model.delivery_records("concurrent-task") == [
        (valid, codex_model.read_record(valid))
    ]
    assert isinstance(
        codex_model.read_task_delivery("concurrent-task", "ffffffff"),
        codex_model.Accepted,
    )
    collecting["batches"][0]["threads"][0]["title"] = None
    current = codex_model.record_path("concurrent-task", "fffffffe")
    write_json(current, collecting)
    assert codex_model.read_record(current) == codex_model.Collecting(
        1, (collecting["batches"][0],)
    )


def test_a_record_of_gone_pages_retires_at_any_format(tmp_path, page_dir):
    """Freezing a delivery retires every envelope whose pages are gone, and reading
    the neighbours every row whose page no server holds, though this Leaf reads
    neither format."""
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

    held = take_lease(page / SERVER_LOCK)
    unheld = tmp_path / "unheld"
    unheld.mkdir()
    for served in (page, unheld):
        row_path(served).parent.mkdir(parents=True, exist_ok=True)
        write_json(row_path(served), {"format": "x", "page": str(served)})
    try:
        assert presence_model.other_leaves(tmp_path / "observer") == []
        assert row_path(page).exists()
        assert not row_path(unheld).exists()
    finally:
        release_lease(held)
