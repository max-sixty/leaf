"""Harness-neutral capture, reading, and receipt of immutable Leaf deliveries.

A delivery is transport-independent input: one or more complete page batches,
each preserving the page's monotonic event order. Thread membership is
context, not a partition key, and response requirements are a snapshot of the
standing projection at capture. Response commands validate the current page
again when they write, so this snapshot never becomes settlement authority.
Receipt validates the current receiver and captured event identities under the
page transaction before advancing its cursor. Pickup records harness acceptance or
turn entry separately; neither settles the user's response requirement.
Each batch carries distinct handling clause texts once, with ordered references
on the events they apply to. Clause identities belong only to that batch.

The envelope names who confirms receipt through `acknowledge`. A hook confirms
what it hands over inline; a pointer reader explicitly confirms a complete
reading through its session's harness. `turn_replies` assigns final custody to the
provider turn.
An answer's `writer` guides initial handling at capture; the current binding alone
controls final custody when writing. It is separate from the semantic operation:
reply and markup requirements retain their meaning on every transport.

Freeze emits an exact `answer.ref`, qualified by delivery, page batch and input.
The immutable envelope is the only address store. Direct authors and provider
finals resolve it through `response_address` before the rich durable reply writer
rechecks the captured logical owner, exact input and standing obligation under the
page lock. An address may be forwarded to a worker without changing its own
author identity; another session's claim supersedes its authorization even after
release or end. The owning session's process restart preserves it.

"""

import json
import re
import secrets
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from .files import read_json
from .harness import claim_harness, session_harness
from .machine import state_home
from .schema import CURSOR_FILE
from .service import (
    PageTransaction,
    owned_pages,
    requires_agent_attention,
    unacknowledged,
)
from .state import (
    flocked,
    open_session_turn,
    session_lock_path,
    session_record,
    write_json,
)

DELIVERY_FORMAT = "leaf-delivery-v5"
DELIVERY_ID = re.compile(r"[0-9a-f]{8}")
_BATCH_FIELDS = (
    "page",
    "claim",
    "through_seq",
    "threads",
    "handling",
    "events",
)


class DeliveryIdConflict(RuntimeError):
    """A delivery identity already belongs to different immutable input."""


def new_delivery_id() -> str:
    """Mint one candidate in the agent-facing delivery-id vocabulary."""
    return secrets.token_hex(4)


def delivery_pointer_prompt(delivery_id: str) -> str:
    """The immutable input pointer shared by queued input and hook reminders."""
    delivery = ElementTree.Element(
        "leaf-delivery", {"id": delivery_id, "operation": "delivery read"}
    )
    pointer = ElementTree.tostring(delivery, encoding="unicode")
    return f"```xml\n{pointer}\n```"


def validate_delivery_id(delivery_id: str) -> str:
    """Return one delivery id after validating its complete wire form."""
    if not isinstance(delivery_id, str) or DELIVERY_ID.fullmatch(delivery_id) is None:
        raise ValueError(f"invalid delivery id {delivery_id!r}")
    return delivery_id


def delivery_path(delivery_id: str) -> Path:
    """The process-independent address of one immutable delivery."""
    validate_delivery_id(delivery_id)
    return state_home() / "deliveries" / f"{delivery_id}.json"


def pages_gone(batches: list[dict]) -> bool:
    """Whether every page these captured batches came from is gone.

    Nothing can answer a delivery once its pages are, so a record of one — the
    envelope here, a Codex task's record of it — is removed by whoever next
    enumerates its directory. Pages are usually deleted from outside leaf, with a
    worktree or a scratch directory, so no leaf process sees the moment."""
    return bool(batches) and not any(Path(batch["page"]).is_dir() for batch in batches)


def retire_if_gone(path: Path, record_format: str) -> None:
    """Remove a readable record once every page it names is gone.

    Other installed versions share these directories. A format or shape this
    version cannot read may still belong to one of their live sessions."""
    try:
        record = read_json(path)
    except ValueError:
        return
    batches = record.get("batches") if isinstance(record, dict) else None
    if (
        not isinstance(record, dict)
        or record.get("format") != record_format
        or not isinstance(batches, list)
        or any(
            not isinstance(batch, dict) or not isinstance(batch.get("page"), str)
            for batch in batches
        )
    ):
        return
    if pages_gone(batches):
        path.unlink(missing_ok=True)


def _retire_gone_deliveries() -> None:
    """Remove readable envelopes whose pages are all gone.

    Envelopes are read one id at a time, so the only enumeration of them is here,
    under the lock every new one is written under."""
    for path in (state_home() / "deliveries").glob("*.json"):
        retire_if_gone(path, DELIVERY_FORMAT)


def _delivery_lock_path() -> Path:
    """Serialize machine-wide delivery identity selection and creation."""
    return state_home() / "deliveries.lock"


def _registry(page_dir: Path):
    from .registry.contract import RegistryError
    from .registry.storage import active_registry

    try:
        return active_registry(page_dir)
    except RegistryError:
        return None


def _subject(event: dict, threads: list[str], by_id: dict[str, dict]) -> dict:
    """Name what one event changes without using prose as an identifier."""
    if event["kind"] in {"action", "report"}:
        return {"kind": "widget", "id": event["widget"]}
    if event["kind"] == "undo":
        original = by_id.get(event["undoes"])
        if original is not None:
            return _subject(original, threads, by_id)
    if threads:
        return {"kind": "thread", "id": threads[0]}
    return {"kind": "page"}


def current_responses(page_dir: Path, events: list[dict]) -> dict[str, dict]:
    """Map every event that owns an answer to its exact response address.

    The address is the workflow's `answer`, so a delivery, a writer's refusal and
    the Stop hook name the same operation. An input a newer one in its thread covers
    owns none; the newest carries the thread's one answer.
    """
    from .served_state.work import live_work

    return {
        item["input"]: item["answer"]
        for item in live_work(page_dir, events).obligations
    }


def batch_data(
    page_dir: Path, transaction, batch: list[dict], *, responses: dict | None = None
) -> dict:
    """Capture one complete ordered page batch, less what `freeze_delivery` writes
    for its transport: the address of a thread reply, and the `handling` that follows
    from it."""
    from .gesture_words import GestureWords, revisions_on_disk
    from .registry.reactions import described
    from .revision_artifact import active_enclosing
    from .thread_context import (
        batch_threads,
        thread_memberships,
        thread_names,
        thread_structure,
        thread_widgets,
    )

    registry = _registry(page_dir)
    events = transaction.events
    within = active_enclosing(page_dir)
    names = thread_names(events)
    memberships = thread_memberships(
        events,
        names,
        thread_widgets(thread_structure(events), names),
        within,
    )
    if responses is None:
        responses = current_responses(page_dir, events)
    by_id = {event["id"]: event for event in events}
    words = GestureWords(events, registry, revisions_on_disk(page_dir))

    captured = []
    for event in batch:
        threads = memberships.get(event["id"], [])
        entry = {
            **described(event, registry),
            "subject": _subject(event, threads, by_id),
            "threads": threads,
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
        "claim": transaction.delivery_owner,
        "through_seq": max(event["seq"] for event in batch),
        "threads": batch_threads(events, batch, within),
        "events": captured,
    }


def response_addresses(payload: dict) -> Iterator[dict]:
    """Read each address exactly as its immutable envelope captured it."""
    for batch in payload["batches"]:
        for event in batch["events"]:
            if (answer := event.get("answer")) is not None:
                yield {
                    **answer,
                    "page": batch["page"],
                    "claim": batch["claim"],
                    "input": {"id": event["id"], "seq": event["seq"]},
                }


def response_address(reference: str) -> dict:
    """Resolve only a complete reference emitted by an immutable delivery.

    Page-local event ids are not addresses. The delivery and batch qualify them;
    consumers use the captured destination rather than interpreting the id again.
    The writer rechecks the captured event against the page log under its lock.
    """
    payload = read_delivery(reference.partition(":")[0])
    for address in response_addresses(payload):
        if address["ref"] == reference:
            return address
    sys.exit(f"unknown response reference {reference!r}")


def stream_reply_target(payload: dict) -> dict | None:
    """The sole reply whose final text belongs to this delivery's provider turn."""
    targets = [
        {
            "page": address["page"],
            "reply_to": address["to"],
            "responds": address["for"],
            "ref": address["ref"],
        }
        for address in response_addresses(payload)
        if address.get("writer") == "turn"
    ]
    return targets[0] if len(targets) == 1 else None


def handled(
    batch: dict,
    delivery_id: str,
    batch_index: int,
    *,
    turn_replies: bool,
    preserve_refs: bool = False,
) -> dict:
    """One captured batch with exact references, writer custody and handling.

    A clause's `when` reads the event, the answer it owes, and its thread's
    digest, so each event is told only its own case and the answer it owes. The
    answer's address is a fact of the freeze, not of the capture: a Codex record
    collects batches before it knows which transport will offer it, and only the
    freeze does."""
    from .registry.contract import event_clauses

    registry = _registry(Path(batch["page"]))
    # A clause asking the agent to act on a thread (name it, summarize it) rides the
    # event and reads the thread's digest, so the event says only what applies to
    # its own thread: a reader skimming a batch for what is new reads its events and
    # can skip the digest.
    digests = {thread["id"]: thread for thread in batch["threads"]}
    clause_ids: dict[str, str] = {}
    events = []
    for event in batch["events"]:
        entry = {
            key: value
            for key, value in event.items()
            if key not in {"handling", "answer"}
        }
        owed = (
            {
                "answer": {
                    **event["answer"],
                    "ref": event["answer"]["ref"]
                    if preserve_refs
                    else f"{delivery_id}:{batch_index}:{event['id']}",
                    **(
                        {
                            "writer": "turn"
                            if turn_replies
                            else event["answer"].get("writer", "agent")
                        }
                        if event["answer"]["kind"] == "reply"
                        else {}
                    ),
                }
            }
            if "answer" in event
            else {}
        )
        digest = next((digests[c] for c in event["threads"] if c in digests), None)
        read = {**entry, **owed}
        if digest is not None:
            read["thread"] = digest
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
    acknowledge: Callable[[str], str] | None = None,
    turn_replies: bool = False,
    delivery_id: str | None = None,
    created_at: float | None = None,
    correction: dict | None = None,
) -> dict:
    """Persist and return one immutable delivery envelope, as its transport hands
    it over.

    `acknowledge` supplies the delivery-specific instruction for reader
    confirmation after the complete envelope reaches context. When the harness
    establishes receipt directly, omit it and the envelope records `null`.
    `turn_replies` is set where the turn the delivery opens writes its thread
    reply with its own messages."""
    lock = _delivery_lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        _retire_gone_deliveries()
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
            "acknowledge": acknowledge(delivery_id) if acknowledge else None,
            **({"correction": correction} if correction is not None else {}),
            "batches": [
                {field: batch[field] for field in _BATCH_FIELDS}
                for batch in (
                    handled(
                        batch,
                        delivery_id,
                        index,
                        turn_replies=turn_replies,
                        preserve_refs=correction is not None,
                    )
                    for index, batch in enumerate(batches)
                )
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


def readable_delivery(payload, delivery_id: str) -> bool:
    """Whether this immutable identity has the envelope this version consumes."""
    if isinstance(payload, dict) and "correction" in payload:
        correction = payload["correction"]
        if not isinstance(correction, dict):
            return False
        claim = correction.get("claim")
        if not isinstance(claim, dict) or any(
            not isinstance(claim.get(key), str) or not claim[key]
            for key in ("id", "generation", "acquisition")
        ):
            return False
    return bool(
        isinstance(payload, dict)
        and payload.get("format") == DELIVERY_FORMAT
        and payload.get("id") == delivery_id
    )


def read_delivery(delivery_id: str) -> dict:
    try:
        path = delivery_path(delivery_id)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    payload = read_json(path)
    if payload is None:
        sys.exit(f"unknown delivery {delivery_id!r}")
    if not readable_delivery(payload, delivery_id):
        raise RuntimeError(f"delivery {delivery_id!r} has an invalid envelope")
    return payload


# Bound each CLI reading in bytes, including JSON escaping and instructions. A
# single event may exceed this budget, so page the immutable serialized text
# rather than dropping fields or changing the captured batch boundaries.
READ_BYTES = 24000
READ_CHARS = 3500


def pointer_acknowledgement(delivery_id: str) -> str:
    return (
        "After every part of this delivery is in context, confirm complete receipt "
        f"with `leaf delivery ack {delivery_id}` before handling its input. "
        "If any output is missing, reread that part before confirming."
    )


def delivery_reading(payload: dict, *, part: int = 1) -> dict:
    """Render bounded reader input, leaving its captured facts and refs immutable.

    The stored envelope's acknowledger belongs to its original transport. A CLI
    reader instead attests complete receipt explicitly, even when the original
    transport could establish entry itself. Large readings expose lossless text
    parts with a next command; only the last offers confirmation.
    """
    reading = {
        **payload,
        "acknowledge": payload["acknowledge"] or pointer_acknowledgement(payload["id"]),
    }
    serialized = json.dumps(reading, indent=2, ensure_ascii=False)
    if len(serialized.encode("utf-8")) + 1 <= READ_BYTES:
        if part != 1:
            raise ValueError("this delivery has only one part")
        return reading
    count = (len(serialized) + READ_CHARS - 1) // READ_CHARS
    if not 1 <= part <= count:
        raise ValueError(f"delivery part must be between 1 and {count}")
    return {
        "id": payload["id"],
        "part": part,
        "parts": count,
        "text": serialized[(part - 1) * READ_CHARS : part * READ_CHARS],
        "next": (
            f"leaf delivery read {payload['id']} --part {part + 1}"
            if part < count
            else None
        ),
        "acknowledge": reading["acknowledge"] if part == count else None,
    }


def cmd_delivery_read(delivery_id: str, *, part: int = 1) -> None:
    """Print bounded immutable input without changing receipt or ownership."""
    print(
        json.dumps(
            delivery_reading(read_delivery(delivery_id), part=part),
            indent=2,
            ensure_ascii=False,
        )
    )


def cmd_delivery_ack(delivery_id: str) -> None:
    """Accept the reader's attestation that every part reached its context."""
    receive_delivery(delivery_id)


def pickup_receipts(
    events: list[dict],
    *,
    phase: Literal["queued", "opened", "failed"] | None,
    input_id: str | None = None,
) -> list[dict]:
    """Select admitted receipts for an explicit transport reading, in log order.

    Keep each complete receipt: its exact input batch, session, turn and timestamp
    belong together. Queued transport acceptance and failed delivery do not prove
    context entry; readers checking pickup must request ``opened``. This reading
    establishes transport evidence only, never work or a successful response.
    ``phase=None`` selects every transport milestone recorded for the input.
    """
    return [
        event
        for event in events
        if event["kind"] == "pickup"
        and (phase is None or event["phase"] == phase)
        and (input_id is None or input_id in event["events"])
    ]


def opened_input_ids(events: list[dict]) -> set[str]:
    """The exact attention inputs recorded as entering a harness's context."""
    return {
        input_id
        for receipt in pickup_receipts(events, phase="opened")
        for input_id in receipt["events"]
    }


def record_pickup(
    page: PageTransaction,
    events: list[dict],
    *,
    phase: str = "opened",
    session: str | None = None,
    turn: str | None = None,
    failure: str | None = None,
) -> dict | None:
    """Durably record one delivery transition for exact attention-bearing inputs.

    ``queued`` means Codex's durable same-task queue accepted the batch;
    ``opened``, which the page shows as Picked up, means the batch is in the
    harness's context for the session: written into the conversation its model
    reads at its next step, whether or not that step has come. A batch the harness
    holds to add later, as a queue or a steer waiting behind a running tool, is not
    opened until it is added. ``failed`` means the harness
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
    wanted = [event["id"] for event in events if requires_agent_attention(event)]
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
    from .event_contracts import append_admitted

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

    Every transport confirms here once its durable consumer accepts input.
    The body records pickup and turn entry before this advances the cursor, so
    interruption leaves input available for retry. Work remains separate.
    Current ownership authorizes the write, not capture-time ownership: the
    page is still the receiver's (`service.claim_names_session`), even between a
    restart's new generation and its claim, and an old envelope can be confirmed
    after ownership returns to its receiver. A receiver with no session takes
    receipt only while no session holds the page.
    """
    # The page is already locked; keep lifecycle admission valid through pickup
    # and cursor commit. SessionEnd cannot cross between those writes.
    with (
        flocked(session_lock_path(session_id), deadline=page.deadline)
        if session_id
        else nullcontext()
    ):
        if (
            page.active_claim is not None
            if session_id is None
            else page.claim_of(session_id) is None
        ):
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


def receive_delivery(delivery_id: str) -> list[Path]:
    """Confirm a reader's complete input and record its entry into that turn.

    Both explicit acknowledgement commands prove the consumer is running even
    if its prompt hook failed. The canonical opener preserves known provider
    lifecycle authority. Pointer receipt also retains its origin's reservation,
    including the exact turn a Codex hook offered it to. Automatic hook and
    provider receipts observe an already-open turn through `receive` instead.
    """
    payload = read_delivery(delivery_id)
    harness = session_harness()
    if harness:
        open_session_turn(harness.session)
        if payload["acknowledge"] is None:
            return harness.receive_pointer(payload)
    return receive(payload, harness.session if harness else None)


def receive(payload: dict, session_id: str | None) -> list[Path]:
    """Confirm one complete delivery and record its entry into `session_id`'s turn.

    Each page uses its own transaction. Interrupted multi-page receipt can be
    retried against the same immutable bounds; no receipt transfers ownership.
    Each receipt observes the current session turn under page→session locks;
    concurrent receipts never nest transactions across pages.
    """
    pages = [receive_one(batch, session_id) for batch in payload["batches"]]
    return pages


def receive_held(
    payload: dict, session_id: str, *, deadline: float | None = None
) -> list[Path]:
    """Confirm each batch of a delivery its hook handed to `session_id`'s open
    turn, where the session still holds the batch's page.

    The hook has already handed the delivery over, so a page that changed hands
    or went, or a turn that ended, refuses only its own batch: that input stays
    pending, and a later delivery carries it. So does a batch whose locks are still
    held at `deadline`, for a hook that must exit by then for its handover to
    stand."""
    pages = []
    for batch in payload["batches"]:
        try:
            pages.append(receive_one(batch, session_id, deadline=deadline))
        except (FileNotFoundError, ReceiptRefused, TimeoutError):
            continue
    return pages


def receive_one(
    batch: dict, session_id: str | None, *, deadline: float | None = None
) -> Path:
    """Confirm one consumer-read batch under its current page ownership."""
    page_dir = Path(batch["page"])
    with (
        PageTransaction(page_dir, deadline=deadline) as page,
        receive_batch(page, batch, session_id=session_id) as events,
    ):
        turn = None
        if session_id:
            observed = session_record(session_id)
            if observed["turn_closed"] is not None:
                raise ReceiptRefused("the receiving provider turn has ended")
            # Receipt observes the consumer turn. The explicit acknowledgement
            # boundary can open an unnamed turn; hooks and providers cannot.
            turn = observed["turn"]
        record_pickup(page, events, session=session_id, turn=turn)
    return page_dir


def pending_batches(session_id: str) -> list[dict]:
    """Every page's pending input for a session whose hooks carry it, one batch
    per page, captured under that page's transaction and not yet confirmed.

    Receipt is a separate step, taken once those batches are handed over:
    it rechecks ownership and the captured events, and anything appended between
    the two readings stays pending, above the cursor it advances."""
    batches = []
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if not (
                    claim
                    and claim["id"] == session_id
                    and claim_harness(claim).hooks_carry()
                ):
                    continue
                if batch := unacknowledged(page.events, page.cursor):
                    batches.append(batch_data(page_dir, page, batch))
        except FileNotFoundError:
            continue
    return batches
