"""Reading a thread: `leaf thread read`, its summaries and the summary hint, and the
resolution events exact history and a wait share."""

from interact_support import (
    SETTLING_ACCEPT,
    _settling_page,
    append_carried_log_record,
    append_command,
    delivered,
    last_deliverable_seq,
    receive_through,
    state_json,
    thread_records,
)
from leaf import event_log as events_model
from leaf import session as session_model


def test_exact_thread_history_and_wait_share_indirect_resolution_events(
    page_dir, capsys
):
    """Rejecting an accepted answer, undoing that rejection, and later restating
    what the answer rested on all change the same thread without naming it
    directly. Exact history and live delivery use one Leaf-owned membership join."""
    _settling_page(page_dir)
    accepted = append_command(page_dir, dict(SETTLING_ACCEPT))
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()

    rejected = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "reject"},
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [thread["id"] for thread in header["threads"]] == ["c1"]

    rejected_seq = next(
        event["seq"]
        for event in events_model.read_events(page_dir)
        if event["id"] == rejected["id"]
    )
    receive_through(page_dir, rejected_seq)
    capsys.readouterr()
    undone = append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": rejected["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [thread["id"] for thread in header["threads"]] == ["c1"]

    restated = append_carried_log_record(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": 2,
            "text": "rewrote the suggestion",
            "restated": ["sug-refill"],
        },
    )
    assert thread_records(page_dir, "c1") == [
        "c1",
        accepted["id"],
        rejected["id"],
        undone["id"],
        restated["id"],
    ]
    assert state_json(page_dir)["threads"][0]["resolved"] is None
