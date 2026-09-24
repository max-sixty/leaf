"""Host-neutral capture and reading of immutable Leaf deliveries.

A delivery is transport-independent input: one or more complete page batches,
each preserving the page's monotonic event order. Conversation membership is
context, not a partition key, and response requirements are a snapshot of the
standing projection at capture. Response commands validate the current page
again when they write, so this snapshot never becomes settlement authority.
Receipt validates the current receiver and captured event identities under the
page transaction before advancing its cursor. Pickup records host acceptance or
turn entry separately; neither settles the user's response requirement.
Each batch carries distinct handling clause texts once, with ordered references
on the events they apply to. Clause identities belong only to that batch.
"""

import json
import re
import secrets
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .event_contracts import append_admitted
from .event_log import flocked
from .files import read_json, write_json
from .machine import state_home
from .passages import active_enclosing, spoken
from .projection import frozen_thread_reading
from .registry.contract import RegistryError, event_clauses
from .registry.reactions import described
from .registry.storage import active_registry
from .revision_artifact import read_registry
from .schema import CURSOR_FILE
from .served_state.page import full_state
from .service import PageTransaction, requires_agent_attention
from .structure import parse_revision
from .thread_context import (
    batch_threads,
    thread_memberships,
    thread_roots,
    thread_structure,
    thread_widgets,
)

DELIVERY_FORMAT = "leaf-delivery-v2"
# The routes that carry a delivery to an agent: `leaf wait`'s output, a pointer
# queued with `codex queue`, and a turn Leaf starts over Codex App Server.
CARRIERS = ("wait", "queue", "app-server")
DELIVERY_ID = re.compile(r"[0-9a-f]{8}")
_BATCH_FIELDS = (
    "page",
    "through_seq",
    "conversations",
    "handling",
    "events",
)


class DeliveryIdConflict(RuntimeError):
    """A delivery identity already belongs to different immutable input."""


def new_delivery_id() -> str:
    """Mint one candidate in the agent-facing delivery-id vocabulary."""
    return secrets.token_hex(4)


def validate_delivery_id(delivery_id: str) -> str:
    """Return one delivery id after validating its complete wire form."""
    if not isinstance(delivery_id, str) or DELIVERY_ID.fullmatch(delivery_id) is None:
        raise ValueError(f"invalid delivery id {delivery_id!r}")
    return delivery_id


def delivery_path(delivery_id: str) -> Path:
    """The process-independent address of one immutable delivery."""
    validate_delivery_id(delivery_id)
    return state_home() / "deliveries" / f"{delivery_id}.json"


def _delivery_lock_path() -> Path:
    """Serialize machine-wide delivery identity selection and creation."""
    return state_home() / "deliveries.lock"


def _registry(page_dir: Path):
    try:
        return active_registry(page_dir)
    except RegistryError:
        return None


def _subject(event: dict, conversations: list[str], by_id: dict[str, dict]) -> dict:
    """Name what one event changes without using prose as an identifier."""
    if event["kind"] in {"action", "request", "report"}:
        return {"kind": "widget", "id": event["widget"]}
    if event["kind"] == "undo":
        original = by_id.get(event["undoes"])
        if original is not None:
            return _subject(original, conversations, by_id)
    if conversations:
        return {"kind": "conversation", "id": conversations[0]}
    return {"kind": "page"}


def _says(event: dict, by_id: dict[str, dict], reading) -> dict[str, str]:
    """The words of the elements one widget gesture names, id → what it says.

    A gesture is recorded as ids: the widget, the unit it folds on, the options
    it picked. They are words only to whoever still holds the document, and an
    agent meeting the batch after a compaction, or from another session, holds
    none of it. The reading is the gesture's own document, the revision it
    names or the frozen message that sent the widget, under the vocabulary that
    document was written in, so a later version that reworded an option does
    not change what the user chose. A child a user wrote is in no document;
    the event's own detail carries its words. An element that only encloses
    another named one is left out: its words repeat theirs, and a list would
    otherwise travel whole with every row pressed in it.
    """
    if event["kind"] == "undo":
        event = by_id.get(event["undoes"], event)
    meaning = event.get("meaning")
    if meaning is None:
        return {}
    said = reading(meaning["document"])
    named = {
        identity: said[identity]
        for identity in meaning.get("depends", [event["widget"]])
        if identity in said
    }
    enclosing = {outer for element in named.values() for outer in element.within[:-1]}
    return {
        identity: element.words
        for identity, element in named.items()
        if element.words and identity not in enclosing
    }


def current_responses(page_dir: Path, events: list[dict]) -> dict[str, dict]:
    """Map every event that owns an answer to its exact response address.

    The address is the workflow's `answer`, so a delivery, a writer's refusal and
    the Stop hook name the same operation. An input a newer one in its thread covers
    owns none; the newest carries the thread's one answer.
    """
    return {
        item["input"]: item["answer"]
        for item in full_state(page_dir, events, layer_identity={})["activity"][
            "obligations"
        ]
    }


def batch_data(
    page_dir: Path,
    transaction,
    batch: list[dict],
    *,
    as_of_seq: int | None = None,
) -> dict:
    """Capture one complete ordered page batch, less the `handling` that
    `freeze_delivery` writes for its carrier."""
    registry = _registry(page_dir)
    events = transaction.events
    within = active_enclosing(page_dir)
    roots = thread_roots(events)
    structure = thread_structure(events)
    widget_conversations = thread_widgets(structure, roots)
    memberships = thread_memberships(
        events,
        roots,
        widget_conversations,
        within,
    )
    responses = current_responses(page_dir, events)
    by_id = {event["id"]: event for event in events}
    through_seq = max(event["seq"] for event in batch)
    evidence_seq = through_seq if as_of_seq is None else as_of_seq
    readings: dict[int | None, dict] = {}

    def reading(document: dict) -> dict:
        """What one gesture's document says, read once for the whole batch. A
        page revision keeps the registry captured with it; frozen thread markup
        lives for the page's whole lifetime and reads under the active one."""
        revision = document.get("revision")
        if revision not in readings:
            readings[revision] = (
                frozen_thread_reading(events, registry).spoken
                if document["kind"] == "thread"
                else spoken(
                    parse_revision(page_dir, revision),
                    read_registry(page_dir, revision),
                )
            )
        return readings[revision]

    captured = []
    for event in batch:
        conversations = memberships.get(event["id"], [])
        entry = {
            **described(event, registry),
            "subject": _subject(event, conversations, by_id),
            "conversations": conversations,
        }
        # The browser's retry key: the log keeps it to recognise a resent post, and
        # the agent has no use for it.
        entry.pop("attempt", None)
        # What an element says is a registry's word, and a page whose active layer
        # does not read is not read for its words at all.
        if registry is not None and (says := _says(event, by_id, reading)):
            entry["says"] = says
        response = responses.get(event["id"])
        obligation = (
            {"as_of_seq": evidence_seq, "response": response}
            if response is not None
            else None
        )
        if obligation is not None:
            entry["obligation"] = obligation
        captured.append(entry)
    return {
        "page": str(page_dir),
        "through_seq": through_seq,
        "conversations": batch_threads(events, batch, within),
        "events": captured,
    }


def handled(batch: dict, carrier: str) -> dict:
    """One captured batch with the `handling` its page's layer gives `carrier`.

    The envelope's shape is every carrier's, but its handling is not: a clause's
    `when` reads the carrier beside the event, and the event's thread digest, so
    each carrier's agent is told only its own route (who acknowledges, and whether
    the final message is the reply) rather than every route with a condition
    naming its own. That makes handling a fact of the freeze, not of the capture:
    a Codex record collects batches before it knows which transport will offer
    it, and only the freeze does."""
    if carrier not in CARRIERS:
        raise ValueError(f"unknown delivery carrier {carrier!r}")
    registry = _registry(Path(batch["page"]))
    # A clause asking the agent to act on a thread (name it, summarize it) rides the
    # event and reads the thread's digest, so the event says only what applies to
    # its own thread: a reader skimming a batch for what is new reads its events and
    # can skip the digest.
    digests = {thread["id"]: thread for thread in batch["conversations"]}
    clause_ids: dict[str, str] = {}
    events = []
    for event in batch["events"]:
        entry = {
            key: value
            for key, value in event.items()
            if key not in {"handling", "obligation"}
        }
        owed = {"obligation": event["obligation"]} if "obligation" in event else {}
        digest = next(
            (digests[c] for c in event["conversations"] if c in digests), None
        )
        read = {**entry, **owed, "carrier": carrier}
        if digest is not None:
            read["conversation"] = digest
        clauses = event_clauses(read, registry)
        refs = [
            clause_ids.setdefault(clause["text"], f"h{len(clause_ids) + 1}")
            for clause in clauses
        ]
        events.append({**entry, **({"handling": refs} if refs else {}), **owed})
    return {
        **batch,
        "handling": {identity: text for text, identity in clause_ids.items()},
        "events": events,
    }


def freeze_delivery(
    batches: list[dict],
    *,
    carrier: str,
    delivery_id: str | None = None,
    created_at: float | None = None,
) -> dict:
    """Persist and return one immutable delivery envelope, handled for the
    `carrier` that will deliver it."""
    batches = [handled(batch, carrier) for batch in batches]
    lock = _delivery_lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        if delivery_id is None:
            while True:
                delivery_id = new_delivery_id()
                path = delivery_path(delivery_id)
                if read_json(path) is None:
                    break
        else:
            path = delivery_path(delivery_id)
        payload = {
            "format": DELIVERY_FORMAT,
            "id": delivery_id,
            "created_at": created_at if created_at is not None else time.time(),
            "batches": [
                {field: batch[field] for field in _BATCH_FIELDS} for batch in batches
            ],
        }
        existing = read_json(path)
        if existing is not None:
            if existing != payload:
                raise DeliveryIdConflict(
                    f"delivery {delivery_id!r} already exists with other data"
                )
            return existing
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, payload)
        return payload


def read_delivery(delivery_id: str) -> dict:
    try:
        path = delivery_path(delivery_id)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    payload = read_json(path)
    if payload is None:
        sys.exit(f"unknown delivery {delivery_id!r}")
    if payload.get("format") != DELIVERY_FORMAT or payload.get("id") != delivery_id:
        raise RuntimeError(f"delivery {delivery_id!r} has an invalid envelope")
    return payload


def cmd_delivery_read(delivery_id: str) -> None:
    print(json.dumps(read_delivery(delivery_id), indent=2, ensure_ascii=False))


def record_pickup(
    page: PageTransaction,
    events: list[dict],
    *,
    phase: str = "opened",
    session: str | None = None,
    turn: str | None = None,
    failure: str | None = None,
) -> dict | None:
    """Durably record one delivery transition for exact user moves.

    ``queued`` means Codex's durable same-task queue accepted the batch;
    ``opened`` means the batch entered an agent turn; ``failed`` means the host
    gave up on the moves with the named ``failure`` and no answer is coming.
    Queued and opened are transport evidence, not authored work claims. A queued
    transition may therefore be followed by an opened transition for the same
    events, while a retry of the same transition appends nothing.
    """
    if phase not in {"queued", "opened", "failed"}:
        raise ValueError(f"unknown pickup phase {phase!r}")
    claim = page.claim
    if session is None and claim:
        session = claim.get("id")
    if phase == "opened" and turn is None and claim and claim.get("id") == session:
        turn = claim.get("turn")
    wanted = [
        event["id"]
        for event in events
        if event.get("author") == "user" and requires_agent_attention(event)
    ]
    picked = {
        (event_id, event["phase"], event["session"], event["turn"])
        for event in page.events
        if event["kind"] == "pickup"
        for event_id in event["events"]
    }
    fresh = list(
        dict.fromkeys(
            event_id
            for event_id in wanted
            if (event_id, phase, session, turn) not in picked
        )
    )
    if not fresh:
        return None
    return append_admitted(
        page,
        {
            "kind": "pickup",
            "author": "page",
            "events": fresh,
            "phase": phase,
            "session": session,
            "turn": turn,
            **({"failure": failure} if failure is not None else {}),
        },
    )


class ReceiptRefused(RuntimeError):
    """Captured input no longer belongs to this receiver or page log."""


@contextmanager
def receive_batch(
    page: PageTransaction, batch: dict, *, session_id: str | None
) -> Iterator[list[dict]]:
    """Commit receipt after the consumer records its durable pickup evidence.

    All carriers use this boundary after their durable consumer accepts input.
    The body records pickup and turn entry before this advances the cursor, so
    interruption leaves input available for retry. Work remains separate.
    Current ownership authorizes the write, not capture-time ownership;
    an old envelope can be confirmed after ownership returns to its receiver.
    """
    claim = page.active_claim
    if (claim["id"] if claim else None) != session_id:
        raise ReceiptRefused(f"delivery no longer owns its page: {page.page_dir}")
    expected = {event["seq"]: event["id"] for event in batch["events"]}
    delivered = {event["seq"]: event for event in page.events}
    if not expected or any(
        seq not in delivered or delivered[seq]["id"] != event_id
        for seq, event_id in expected.items()
    ):
        raise ReceiptRefused(
            f"delivery no longer matches its page log: {page.page_dir}"
        )
    yield [delivered[seq] for seq in expected]
    if max(expected) > page.cursor:
        write_json(page.page_dir / CURSOR_FILE, {"seq": max(expected)})
