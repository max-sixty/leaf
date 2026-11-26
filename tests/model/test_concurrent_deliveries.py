"""State-home records every installed Leaf shares: their readers share one shape
boundary, and a record of this Leaf's shape whose pages are gone retires."""

from copy import deepcopy

from interact_support import append_carried_log_record, published

from leaf.agents import codex as codex_model
from leaf.agents.delivery import batch_data, freeze_delivery
from leaf.base.state import write_json
from leaf.records.transaction import PageTransaction


def test_live_and_archived_readers_ignore_other_shapes_and_unknown_states(
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
    accepted: dict = {
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

    def another_shape(path):
        """Where a Leaf of another `RECORD` shape keeps the record `path` names."""
        return path.with_name(f"{path.stem}@999{path.suffix}")

    # Each record this Leaf reads none of, by the file it is in: another shape's,
    # and one of this shape in a state this Leaf doesn't know.
    unreadable = [
        (another_shape, {**accepted, "format": "leaf-codex-delivery/999"}),
        (codex_model.RECORD.file, {**accepted, "state": "a-later-state"}),
    ]
    collecting: dict = deepcopy(accepted)
    collecting["state"] = "collecting"
    collecting.pop("pending")
    collecting["batches"] = [deepcopy(captured)]

    for index, (file, record) in enumerate(unreadable):
        identity = f"{index:016x}"
        freeze_delivery([captured], delivery_id=identity)
        live = codex_model.record_path("concurrent-task", identity)
        archived = live.parent / "history" / live.name
        archived.parent.mkdir(parents=True, exist_ok=True)
        live, archived = file(live), file(archived)
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
        gone: dict = deepcopy(record)
        gone["batches"][0]["page"] = str(tmp_path / "gone")
        write_json(live, gone)
        write_json(archived, gone)

    # A record of this shape whose pages are gone goes though this Leaf reads none
    # of it; another shape's stays as its Leaf left it.
    directory = codex_model.delivery_dir("concurrent-task")
    other = another_shape(directory / "0000000000000000.json")
    held = {
        path: path.read_bytes() for path in (other, directory / "history" / other.name)
    }
    assert codex_model.delivery_records("concurrent-task") == []
    assert not codex_model.recover_codex_receipt("concurrent-task")
    codex_model.retire_gone_task_records()
    assert set(directory.rglob("*.json")) == set(held)
    assert {path: path.read_bytes() for path in held} == held

    missing_envelope = codex_model.record_path("concurrent-task", "fffffffffffffffd")
    write_json(codex_model.RECORD.file(missing_envelope), accepted)
    assert codex_model.read_record(missing_envelope) is None

    freeze_delivery([captured], delivery_id="ffffffffffffffff")
    valid = codex_model.record_path("concurrent-task", "ffffffffffffffff")
    codex_model.write_record(
        valid, codex_model.Accepted(1, tuple(accepted["batches"]), (0,))
    )
    assert codex_model.delivery_records("concurrent-task") == [
        (valid, codex_model.read_record(valid))
    ]
    assert isinstance(
        codex_model.read_task_delivery("concurrent-task", "ffffffffffffffff"),
        codex_model.Accepted,
    )
    collecting["batches"][0]["threads"][0]["title"] = None
    current = codex_model.record_path("concurrent-task", "fffffffffffffffe")
    codex_model.write_record(
        current, codex_model.Collecting(1, (collecting["batches"][0],))
    )
    assert codex_model.read_record(current) == codex_model.Collecting(
        1, (collecting["batches"][0],)
    )
