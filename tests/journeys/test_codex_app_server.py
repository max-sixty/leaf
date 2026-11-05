"""Tests scheduled by the measured cost of their boundary."""

import pytest
from interact_support import (
    _observer,
    append_carried_log_record,
)

from leaf import codex_adapter as codex_adapter_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf import session as session_model


def test_a_running_turn_holds_a_delivery_back_without_asking_the_task(
    codex_claimed_page, monkeypatch
):
    """The observer's own reading is what the delivery loop waits on.

    Status is only readable by opening a connection, so asking the task each pass
    would reconnect, handshake and resume once a second for as long as the user's
    turn runs. The observer is already subscribed and already folds every
    `turn/started` and `turn/completed`, so the loop reads that instead. It can
    lag, which is why it only holds a delivery back — the status that lets one
    start is still read on the starting connection.
    """
    page = codex_claimed_page
    append_carried_log_record(
        page, {"kind": "comment", "id": "later", "author": "user", "text": "and this"}
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

    observer = _observer()
    observer._read(
        {
            "method": "turn/started",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "a-turn-the-user-started",
                    "items": [],
                    "status": "inProgress",
                },
            },
        }
    )
    monkeypatch.setattr(
        observer,
        "start_delivery",
        lambda *_: pytest.fail("the task was asked while a turn of its own ran"),
    )

    assert not codex_adapter_model._offer_queued_delivery(
        "codex", "codex-thread", observer
    )

    # The turn ends and the fold says so, without anything reconnecting to ask.
    observer._read(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "codex-thread",
                "turn": {
                    "id": "a-turn-the-user-started",
                    "status": "completed",
                    "items": [],
                },
            },
        }
    )
    assert observer.working() is False
