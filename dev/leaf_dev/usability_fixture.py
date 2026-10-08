"""Seed usability scenarios under the evaluated arm's own Leaf package.

The evaluator installs this developer module beside the selected arm and invokes
it in that arm's isolated state home. Fixtures cross real admission, response and
receipt boundaries; they do not write a synthetic event log.
"""

import json
import sys
from pathlib import Path

from leaf import event_endpoint
from leaf.delivery import batch_data, freeze_delivery, receive_batch, record_pickup
from leaf.event_contracts import append_admitted
from leaf.service import PageTransaction, unacknowledged
from leaf.thread import post_response


def admit(directory: str, event: str) -> None:
    status, body = event_endpoint.accept_event(Path(directory), json.loads(event), dict)
    assert status == 200, body


def answer(directory: str, event_id: str, text: str) -> None:
    page = Path(directory)
    with PageTransaction(page) as transaction:
        event = next(e for e in transaction.events if e["id"] == event_id)
        batch = batch_data(page, transaction, [event])
    payload = freeze_delivery([batch])
    post_response(payload["batches"][0]["events"][0]["answer"]["ref"], text)


def history(directory: str, fixture: str) -> None:
    """Admit and acknowledge the conversation under one transaction lease."""
    texts, anchor, revision = json.loads(fixture)
    page_dir = Path(directory)
    with PageTransaction(page_dir) as page:
        first = append_admitted(
            page,
            {
                "kind": "comment",
                "author": "user",
                "revision": revision,
                "anchor": anchor,
                "text": texts[0],
            },
        )
        latest = first
        for n, text in enumerate(texts[1:]):
            latest = append_admitted(
                page,
                {
                    "kind": "reply",
                    "author": "agent" if n % 2 == 0 else "user",
                    "parent": latest["id"],
                    "text": text,
                    "revision": revision,
                },
            )
        append_admitted(
            page, {"kind": "resolve", "author": "user", "parent": first["id"]}
        )
        batch = batch_data(page_dir, page, unacknowledged(page.events, page.cursor))
        claim = page.active_claim
        session = claim["id"] if claim else None
        with receive_batch(page, batch, session_id=session) as events:
            record_pickup(page, events, session=session)


if __name__ == "__main__":
    action, *args = sys.argv[1:]
    {"admit": admit, "answer": answer, "history": history}[action](*args)
