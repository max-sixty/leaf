"""Host-neutral capture and reading of immutable Leaf deliveries.

A delivery is transport-independent input: one or more complete page batches,
each preserving the page's monotonic event order. Conversation membership is
context, not a partition key, and response requirements are a snapshot of the
standing projection at capture. Response commands validate the current page
again when they write, so this snapshot never becomes settlement authority.
"""

import json
import sys
import time
import uuid
from pathlib import Path

from .events import build_threads
from .files import read_json, write_json
from .host import state_home
from .passages import active_enclosing
from .registry.contract import RegistryError, handling
from .registry.reactions import described
from .registry.storage import load_registry
from .served_state.page import full_state
from .thread_context import (
    batch_threads,
    thread_memberships,
    thread_roots,
    thread_structure,
    thread_widgets,
)

DELIVERY_FORMAT = "leaf-delivery-v1"


def delivery_path(delivery_id: str) -> Path:
    """The process-independent address of one immutable delivery."""
    try:
        parsed = uuid.UUID(delivery_id)
    except (ValueError, AttributeError) as error:
        raise ValueError(f"invalid delivery id {delivery_id!r}") from error
    if str(parsed) != delivery_id:
        raise ValueError(f"invalid delivery id {delivery_id!r}")
    return state_home() / "deliveries" / f"{delivery_id}.json"


def _registry(page_dir: Path):
    try:
        return load_registry(page_dir)
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


def batch_data(page_dir: Path, transaction, batch: list[dict]) -> dict:
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
    captured = []
    for event in batch:
        conversations = memberships.get(event["id"], [])
        entry = {
            **described(event, registry),
            "subject": _subject(event, conversations, by_id),
            "conversations": conversations,
        }
        response = responses.get(event["id"])
        if response is not None:
            entry["obligation"] = {
                "as_of_seq": through_seq,
                "response": response,
            }
        captured.append(entry)
    return {
        "page": str(page_dir),
        "through_seq": through_seq,
        "conversations": batch_threads(events, batch, within),
        "handling": handling(batch, registry),
        "events": captured,
    }


def freeze_delivery(
    batches: list[dict],
    *,
    delivery_id: str | None = None,
    created_at: float | None = None,
) -> dict:
    """Persist and return one immutable delivery envelope."""
    delivery_id = delivery_id or str(uuid.uuid4())
    payload = {
        "format": DELIVERY_FORMAT,
        "id": delivery_id,
        "created_at": created_at if created_at is not None else time.time(),
        "batches": batches,
    }
    path = delivery_path(delivery_id)
    existing = read_json(path)
    if existing is not None:
        if existing != payload:
            raise RuntimeError(
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
