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

The envelope names the carrier that brings it into an agent's context, and the
two facts that differ by carrier are stated once for the whole delivery rather
than per event. `acknowledge` says who confirms receipt: the reader of a `leaf
wait`, in the way its harness runs that command, or nobody, where the carrier
confirmed it itself. And a carrier whose turn speaks for the delivery, App Server,
turns the one thread reply the delivery owes into a `turn` answer, which that
turn's own messages write; every other carrier leaves it a `reply` for `leaf
reply`. Each event's `answer` is that same address, so its `answering` clauses
follow from the answer rather than from the carrier.
"""

import json
import re
import secrets
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .event_contracts import append_admitted
from .event_log import flocked
from .files import read_json, write_json
from .gesture_words import GestureWords
from .machine import state_home
from .passages import active_enclosing
from .registry.contract import RegistryError, event_clauses
from .registry.reactions import described
from .registry.storage import active_registry
from .schema import CURSOR_FILE
from .served_state.page import full_state
from .service import (
    PageTransaction,
    delivery_reply_attempt,
    requires_agent_attention,
)
from .thread_context import (
    batch_threads,
    thread_memberships,
    thread_roots,
    thread_structure,
    thread_widgets,
)

DELIVERY_FORMAT = "leaf-delivery-v3"
# The routes that carry a delivery to an agent: `leaf wait`'s output, a pointer
# queued with `codex queue`, and a turn Leaf starts over Codex App Server.
CARRIERS = ("wait", "queue", "app-server")
# The one carrier whose turn writes the delivery's thread reply with its own
# messages.
TURN_CARRIER = "app-server"
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


def batch_data(page_dir: Path, transaction, batch: list[dict]) -> dict:
    """Capture one complete ordered page batch, less what `freeze_delivery` writes
    for its carrier: the route of a thread reply, and the `handling` that follows
    from it."""
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
    words = GestureWords(page_dir, events, registry)

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
        if registry is not None and (says := words.says(event)):
            entry["says"] = says
        if (answer := responses.get(event["id"])) is not None:
            entry["answer"] = answer
        captured.append(entry)
    return {
        "page": str(page_dir),
        "through_seq": max(event["seq"] for event in batch),
        "conversations": batch_threads(events, batch, within),
        "events": captured,
    }


def carried_answer(answer: dict, carrier: str, delivery_id: str) -> dict:
    """The answer one captured event owes once `carrier` delivers it.

    A plain reply delivered into a turn of its own is that turn's to write, with
    its opening and final messages, under the reply attempt the delivery names; the
    same reply reaching an agent any other way stays `leaf reply`'s. Every other
    answer is the same on every carrier."""
    if answer["kind"] == "reply" and carrier == TURN_CARRIER:
        return {
            **answer,
            "kind": "turn",
            "attempt": delivery_reply_attempt(delivery_id),
        }
    return answer


def handled(batch: dict, carrier: str, delivery_id: str) -> dict:
    """One captured batch as `carrier` delivers it: each answer routed for that
    carrier, and the `handling` its page's layer gives each event.

    A clause's `when` reads the event, the answer it owes, and its thread's
    digest, so each event is told only its own case and the answer it owes. The
    answer's route is a fact of the freeze, not of the capture: a Codex record
    collects batches before it knows which transport will offer it, and only the
    freeze does."""
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
            if key not in {"handling", "answer"}
        }
        owed = (
            {"answer": carried_answer(event["answer"], carrier, delivery_id)}
            if "answer" in event
            else {}
        )
        digest = next(
            (digests[c] for c in event["conversations"] if c in digests), None
        )
        read = {**entry, **owed}
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
    acknowledge: Callable[[str], str] | None = None,
    delivery_id: str | None = None,
    created_at: float | None = None,
) -> dict:
    """Persist and return one immutable delivery envelope, as the `carrier` that
    will deliver it hands it over.

    `acknowledge` writes, for the delivery's id, what the reader does to confirm
    it: a `leaf wait`'s reader acknowledges, in the way its harness runs the
    command, and every other carrier confirms receipt itself, so its envelope says
    `null`."""
    if carrier not in CARRIERS:
        raise ValueError(f"unknown delivery carrier {carrier!r}")
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
            "carrier": carrier,
            "acknowledge": acknowledge(delivery_id) if acknowledge else None,
            "batches": [
                {field: batch[field] for field in _BATCH_FIELDS}
                for batch in (handled(batch, carrier, delivery_id) for batch in batches)
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
