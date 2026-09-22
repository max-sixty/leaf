"""Host-neutral capture and reading of immutable Leaf deliveries.

A delivery is transport-independent input: one or more complete page batches,
each preserving the page's monotonic event order. Conversation membership is
context, not a partition key, and response requirements are a snapshot of the
standing projection at capture. Response commands validate the current page
again when they write, so this snapshot never becomes settlement authority.
Each batch carries distinct handling clause texts once, with ordered references
on the events they apply to. Clause identities belong only to that batch.
"""

import json
import re
import secrets
import sys
import time
from pathlib import Path

from .event_log import flocked
from .events import build_threads
from .files import read_json, write_json
from .machine import state_home
from .passages import active_enclosing, spoken
from .projection import frozen_thread_reading
from .registry.contract import RegistryError, event_clauses
from .registry.reactions import described
from .registry.storage import active_registry
from .revision_artifact import read_registry
from .served_state.page import full_state
from .structure import parse_revision
from .thread_context import (
    batch_threads,
    thread_memberships,
    thread_roots,
    thread_structure,
    thread_widgets,
)

DELIVERY_FORMAT = "leaf-delivery-v2"
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
    not change what the reader chose. A child a reader wrote is in no document;
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


def _response(
    event: dict,
    obligation: dict | None,
    threads: dict,
    widget_conversations: dict[str, str],
    receipted_requests: set[str],
) -> dict | None:
    """Translate current settlement evidence into an addressed operation."""
    if event["kind"] == "request" and event["id"] not in receipted_requests:
        return {"kind": "receipt", "request": event["id"]}
    if obligation is None:
        return None
    target = obligation["target"]
    if target["kind"] == "thread":
        thread = threads.get(target["id"])
        if thread and (thread["root"].get("response") or {}).get("kind") == "version":
            return {"kind": "version", "conversation": target["id"]}
        return {
            "kind": "reply",
            "to": obligation["event"],
            "for": event["id"],
        }
    if owner := widget_conversations.get(event.get("widget")):
        return {"kind": "reply", "to": owner, "for": event["id"]}
    return None


def _response_context(
    page_dir: Path, events: list[dict]
) -> tuple[dict, dict, dict, set]:
    """Derive the one current response contract shared by capture and writers."""
    within = active_enclosing(page_dir)
    roots = thread_roots(events)
    structure = thread_structure(events)
    widget_conversations = thread_widgets(structure, roots)
    threads = build_threads(events, within)
    obligations = {
        item["event"]: item
        for item in full_state(page_dir, events, layer_identity={})["activity"][
            "obligations"
        ]
        if item.get("event") is not None
    }
    receipted_requests = {
        event["request"] for event in events if event["kind"] == "receipt"
    }
    return obligations, threads, widget_conversations, receipted_requests


def current_responses(page_dir: Path, events: list[dict]) -> dict[str, dict]:
    """Map every event that still requires work to its exact response address."""
    obligations, threads, widget_conversations, receipted_requests = _response_context(
        page_dir, events
    )
    return {
        event["id"]: response
        for event in events
        if (
            response := _response(
                event,
                obligations.get(event["id"]),
                threads,
                widget_conversations,
                receipted_requests,
            )
        )
        is not None
    }


def batch_data(
    page_dir: Path,
    transaction,
    batch: list[dict],
    *,
    as_of_seq: int | None = None,
) -> dict:
    """Freeze one complete ordered page batch for every delivery carrier."""
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
    clause_ids: dict[str, str] = {}
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
        if clauses := event_clauses(event, registry):
            entry["handling"] = [
                clause_ids.setdefault(clause["text"], f"h{len(clause_ids) + 1}")
                for clause in clauses
            ]
        response = responses.get(event["id"])
        if response is not None:
            entry["obligation"] = {
                "as_of_seq": evidence_seq,
                "response": response,
            }
        captured.append(entry)
    return {
        "page": str(page_dir),
        "through_seq": through_seq,
        "conversations": batch_threads(events, batch, within),
        "handling": {identity: text for text, identity in clause_ids.items()},
        "events": captured,
    }


def freeze_delivery(
    batches: list[dict],
    *,
    delivery_id: str | None = None,
    created_at: float | None = None,
) -> dict:
    """Persist and return one immutable delivery envelope."""
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
