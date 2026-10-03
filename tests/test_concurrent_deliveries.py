"""Task record readers share one shape boundary across installed Leaf versions."""

from copy import deepcopy

from leaf import codex as codex_model
from leaf import codex_adapter as adapter_model
from leaf.session_cleanup import write_json


def test_live_and_archived_readers_ignore_records_with_missing_fields(tmp_path):
    page = tmp_path / "page"
    page.mkdir()
    accepted = {
        "format": codex_model.RECORD_FORMAT,
        "state": "accepted",
        "created_at": 1,
        "transport": {"phase": "queued", "turn": None},
        "batches": [
            {
                "page": str(page),
                "session": "concurrent-task",
                "receipted": True,
                "events": [{"id": "captured", "seq": 1}],
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
    for field in accepted["transport"]:
        record = deepcopy(accepted)
        del record["transport"][field]
        unreadable.append(record)
    collecting = deepcopy(accepted)
    collecting["state"] = "collecting"
    collecting.pop("transport")
    collecting["batches"][0].update(
        through_seq=1, threads=[{"id": "thread", "title": "Title"}]
    )
    collecting["batches"][0]["events"][0].update(
        kind="comment",
        threads=["thread"],
        answer={"kind": "reply", "to": "thread", "for": "captured"},
    )
    for field in ("through_seq", "threads"):
        record = deepcopy(collecting)
        del record["batches"][0][field]
        unreadable.append(record)
    record = deepcopy(collecting)
    del record["batches"][0]["events"][0]["threads"]
    unreadable.append(record)
    record = deepcopy(collecting)
    del record["batches"][0]["events"][0]["kind"]
    unreadable.append(record)
    for field in ("id", "title"):
        record = deepcopy(collecting)
        record["batches"][0]["threads"][0][field] = []
        unreadable.append(record)
    record = deepcopy(collecting)
    record["batches"][0]["events"][0]["threads"] = [[]]
    unreadable.append(record)
    for answer in (
        {"kind": []},
        {"kind": "reply", "for": "captured"},
        {"kind": "reply", "to": "thread"},
        {"kind": "reply", "to": "thread", "for": []},
        {"kind": "turn", "to": "thread", "for": "captured"},
        {"kind": "markup"},
    ):
        record = deepcopy(collecting)
        record["batches"][0]["events"][0]["answer"] = answer
        unreadable.append(record)

    for index, record in enumerate(unreadable):
        identity = f"{index:08x}"
        live = codex_model.record_path("concurrent-task", identity)
        archived = live.parent / "history" / live.name
        archived.parent.mkdir(parents=True, exist_ok=True)
        write_json(live, record)
        write_json(archived, record)
        assert codex_model.delivery_record_state("concurrent-task", identity) is None
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

    assert codex_model.delivery_records("concurrent-task") == []
    assert not adapter_model._recover_receipt("concurrent-task")
    codex_model.retire_gone_task_records()
    assert len(
        list(
            codex_model.record_path("concurrent-task", "00000000").parent.glob("*.json")
        )
    ) == len(unreadable)
    assert len(
        list(
            codex_model.record_path("concurrent-task", "00000000")
            .parent.joinpath("history")
            .glob("*.json")
        )
    ) == len(unreadable)

    valid = codex_model.record_path("concurrent-task", "ffffffff")
    write_json(valid, accepted)
    assert codex_model.delivery_records("concurrent-task") == [(valid, accepted)]
    assert (
        codex_model.delivery_record_state("concurrent-task", "ffffffff") == "accepted"
    )
    collecting["batches"][0]["threads"][0]["title"] = None
    current = codex_model.record_path("concurrent-task", "fffffffe")
    write_json(current, collecting)
    assert codex_model.read_record(current) == collecting
