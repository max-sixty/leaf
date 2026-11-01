"""Capture, reading, and receipt of Leaf deliveries, for every harness.

A delivery hands the agent the user's updates from one or more pages.
`freeze_delivery` writes it once as an immutable envelope with one batch per page,
its events in log order. Each event's `answer` is what the agent owed it at capture,
and `leaf thread reply` checks the page again when it writes, so a stale
`answer` settles nothing. Each batch lists each distinct handling clause once, under an id
its events refer to; the ids mean nothing outside that batch.

Receipt (`receive_batch`) checks, under the page transaction, that the receiver
still owns the page and the events are the ones captured, then advances the page's
acknowledgement cursor with a `receipt` event (`record_receipt`). The pickup it
records (`record_pickup`) says a harness accepted the delivery or a turn opened it,
and answers nothing. The two are separate events because neither implies the other:
a failed or queued pickup confirms no receipt, a receipt whose inputs were already
picked up, or that the harness gave up on, records no opened pickup, and an opened
pickup a Claude Code hook handed over is not yet a receipt. The envelope's
`acknowledge` says who confirms receipt: the hooks confirm their inline input, while
the agent confirms Codex hook input and a pointer it read with `leaf delivery ack`.

A Pi hook's context is in the session once the hook returns, so the hook records
the receipt as it hands the delivery over. Claude Code reads a hook's output only
once the hook exits, and drops it if Escape lands first, so its hook records only
the opened pickup, which the page shows as Delivered at once. The receipt follows
once Claude Code's own record, its transcript, shows the handover in the model's
context (`confirm_entered`, `Harness.commits_hook_context`), which every later
hook checks first. Until then the input is not
deliverable while its turn runs; once that turn reads ended, or a dropped prompt
is submitted again as a new turn, what the transcript does not show is input
again (`deliverable`), and that prompt, a waking watch or the server's nudge
brings it back.

A reply reservation lets a Codex App Server turn's final message become the reply
to one delivered update. Freezing with `turn_replies` marks each reply answer
`writer: "turn"`, and the harness reserves the reply's address before it starts the
turn (`thread.reserve_delivery_reply`). The page's stream lists open reservations
under `reply_reservations` (`service.STREAM`), and session-lifetime.md says when one is
released. While a reservation is open, no other delivery can reserve the address,
the turn's final message commits as the reply, and failure receipts and other
turns' finals are refused or write nothing. A `leaf thread reply` still commits at
once, so its refusals reach the agent while it can still fix them, and the turn's
final then yields to it. `writer` is only the hint captured at freeze; the open
reservation decides who writes.

`freeze_delivery` gives each owed answer an `answer.ref` naming its delivery, batch
and input, and only the envelope holds what a ref points to. Receipt copies each
batch's refs into the page log (`record_pickup`'s `refs`), so a reader of the page
alone, such as a refusal naming the update a thread owes, can name the ref. An
update no delivery has carried has no ref. `leaf thread reply` and a turn's final
both resolve a ref with `response_address`, and `thread.post_reply` then checks,
under the page lock, that the claim the batch was captured under still owns the
page and the input is still owed. The agent may pass a ref to a worker, which
writes as the same author. Once another session claims the page, the ref stops
working, even after that session releases or ends; a restart of the owning
session's process keeps it working. An update still owed then reaches the new
owner in its next delivery, with a ref of its own (`deliverable`).
"""

import re
import secrets
import time
from collections.abc import Callable, Generator, Iterable, Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from .event_log import jsonl_line
from .harness import session_harness
from .interaction_log import acting_on
from .refusals import Refused
from .registry.kernel import verb_writers
from .service import (
    PageTransaction,
    may_receive,
    requires_agent_attention,
    unacknowledged,
)
from .state import (
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    open_session_turn,
    retire_if_gone,
    session_lock_path,
    session_record,
    state_home,
    turn_closed,
)

_INTEGER = {"type": "integer"}
_STRINGS = {"type": "array", "items": STRING}
# Where a thread stands, as the comment, reply or reanchor that last placed it says.
_ANCHOR = {
    "anyOf": [
        {"$ref": "leaf:event/comment#/properties/anchor"},
        {"$ref": "leaf:event/reply#/properties/anchor"},
        {"$ref": "leaf:event/reanchor#/properties/anchor"},
    ]
}
# Widget gestures, unfolded (`thread_context.ACTION_FIELDS`).
_GESTURES = {
    "type": "array",
    "items": object_schema(
        {
            "id": STRING,
            "seq": _INTEGER,
            "author": STRING,
            "widget": STRING,
            "action": STRING,
            "detail": {"type": "object"},
        }
    ),
}
_THREAD_DIGEST = object_schema(
    {
        "id": described("The thread's id, which the batch's events name.", STRING),
        "title": described(
            "Null until the thread is named.", {"type": ["string", "null"]}
        ),
        "anchor": described("Where the thread stands on the page.", _ANCHOR),
        "detached_from": described(
            "The anchor a detached thread last had, or null.", _ANCHOR
        ),
        "resolved": described(
            "Who closed the thread, or null while it is open.",
            {"type": ["string", "null"]},
        ),
        "elided": described(
            "How many messages and gestures a long thread leaves out of "
            "`messages` and `actions`.",
            object_schema({"messages": _INTEGER, "actions": _INTEGER}),
        ),
        "messages": described(
            "Its earlier messages (`thread_context.MESSAGE_FIELDS`), less the "
            "batch's own events: the first and the latest of a long thread.",
            {
                "type": "array",
                "items": object_schema(
                    {
                        "id": described("The message's event id.", STRING),
                        "seq": described("Its event's place in the log.", _INTEGER),
                        "author": STRING,
                    },
                    {
                        "agent": described(
                            "The name an agent's message is shown under.", STRING
                        ),
                        "text": STRING,
                        "ephemeral": described(
                            "Marks a one-line progress reply, which answers nothing.",
                            {"const": True},
                        ),
                        "token": described(
                            "A reaction's word, in place of `text`.", STRING
                        ),
                        "markup": described(
                            "The HTML an agent's message holds, such as a widget it "
                            "sent.",
                            STRING,
                        ),
                        "drawing": {"$ref": "leaf:event/comment#/properties/drawing"},
                        "suggestion": described(
                            "True where the comment is a suggestion.",
                            {"type": "boolean"},
                        ),
                        "edited": described(
                            "The user's latest rewrite, and the words it replaced.",
                            object_schema(
                                {
                                    "id": STRING,
                                    "seq": _INTEGER,
                                    "ts": STRING,
                                    "was": STRING,
                                }
                            ),
                        ),
                    },
                ),
            },
        ),
        "summaries": described(
            "The thread's summaries in force (`events.active_summaries`).",
            {
                "type": "array",
                "items": object_schema(
                    {
                        "id": STRING,
                        "seq": _INTEGER,
                        "from": described(
                            "The first message the summary folds.", STRING
                        ),
                        "through": described("The last message it folds.", STRING),
                        "covers": described(
                            "Every message it folds, in thread order.", _STRINGS
                        ),
                        "text": described(
                            "The summary's Markdown, empty for a fold that only "
                            "hides the messages.",
                            STRING,
                        ),
                        "label": described(
                            "What the folded run reads as in the thread.", STRING
                        ),
                    },
                    {
                        "trigger": described(
                            "The agent reply whose arrival folded earlier progress "
                            "messages.",
                            STRING,
                        )
                    },
                ),
            },
        ),
        "actions": described(
            "Gestures in force on widgets sent in the thread, other than the "
            "batch's own (`thread_context.ACTION_FIELDS`).",
            _GESTURES,
        ),
    },
    {
        "summary_hint": described(
            "An earlier run of messages worth summarizing, from its first message "
            "through its last.",
            object_schema({"from": STRING, "through": STRING}),
        )
    },
)
_ANSWER = {
    "anyOf": [
        described(
            "A thread reply under `parent` answering the input `responds`, written "
            "by the agent or, for a Codex App Server turn, by the turn's final "
            "message.",
            object_schema(
                {
                    "kind": {"const": "reply"},
                    "parent": STRING,
                    "responds": STRING,
                    "ref": described(
                        "The delivery reference identifying this answer.", STRING
                    ),
                    "writer": described(
                        "Who is to write the reply when the delivery was frozen: the "
                        "agent, or the final message of the turn carrying it.",
                        {"enum": ["agent", "turn"]},
                    ),
                }
            ),
        ),
        described(
            "A stamped page revision recording the widget action `action`.",
            object_schema(
                {
                    "kind": {"const": "markup"},
                    "action": STRING,
                    "ref": described(
                        "The delivery reference identifying this answer.", STRING
                    ),
                }
            ),
        ),
    ]
}
_DELIVERED_EVENT = {
    "$ref": "leaf:event",
    **object_schema(
        {
            "subject": described(
                "What the event changes.",
                {
                    "anyOf": [
                        object_schema(
                            {"kind": {"enum": ["thread", "widget"]}, "id": STRING}
                        ),
                        object_schema({"kind": {"const": "page"}}),
                    ]
                },
            ),
            "threads": described("Every thread the event belongs to.", _STRINGS),
        },
        {
            "says": described(
                "The words of each element the gesture names, by id, as the page "
                "it was made on wrote them.",
                {"type": "object", "additionalProperties": STRING},
            ),
            "names": described(
                "The name of each element in `says`, by id, in the gesture's own "
                "document: its declared name or leading title, else its words.",
                {"type": "object", "additionalProperties": STRING},
            ),
            "was": described(
                "On the user's rewrite of their own message, the words it replaced.",
                STRING,
            ),
            "suggestion": described(
                "A comment's own flag; beside an edit's `was`, true where the "
                "rewritten message is a suggestion, so its new text is the exact "
                "replacement it proposes.",
                {"type": "boolean"},
            ),
            "unsent": described(
                "On the user's message or edit about a widget, one their thread is "
                "anchored in or was sent in, the work they had made there without "
                "sending it (`$state.unsent`), as it stood when they wrote: what "
                "the widget showed them (`thread_context.unsent_at_messages`). "
                "Absent where none stood.",
                _GESTURES,
            ),
            "waiting": described(
                "The agent's questions the input may have answered though it "
                "answers them by no rule: on a widget action, those still waiting "
                "on the user's words in a thread about that widget's obligations "
                "(`obligations.waiting_about`); on the user's message in a thread, "
                "those still waiting on a pick on a widget frozen there "
                "(`obligations.waiting_in_thread`). Each is the obligation's `id` "
                "and the `text` that asked it.",
                {
                    "type": "array",
                    "items": object_schema(
                        {"id": STRING, "text": {"type": ["string", "null"]}}
                    ),
                },
            ),
            "answer": described(
                "The response the event owed at capture "
                "(`obligations.response_address`); absent where it owes none.",
                _ANSWER,
            ),
            "handling": described(
                "Ids of the batch's `handling` clauses that apply, in reading order.",
                _STRINGS,
            ),
        },
    ),
}
_BATCH = object_schema(
    {
        "page": described("The page directory.", STRING),
        "claim": described(
            "The session that owned the page at capture.",
            {"type": ["string", "null"]},
        ),
        "through_seq": described(
            "The log position the batch was captured through; a correction keeps its "
            "original batch's.",
            _INTEGER,
        ),
        "threads": described(
            "The threads the batch's events land in, each with its messages other "
            "than the batch's own (`thread_context.batch_threads`). A `when` clause "
            "reads an event's as its `thread`.",
            {"type": "array", "items": _THREAD_DIGEST},
        ),
        "handling": described(
            "Each clause's text once, by an id only this batch's events use.",
            {"type": "object", "additionalProperties": STRING},
        ),
        "events": described(
            "In log order, each the logged record less the browser's `attempt`, with "
            "what the delivery reads of it (`batch_data`, `handled`).",
            {"type": "array", "items": _DELIVERED_EVENT},
        ),
    }
)
DELIVERY = Record(
    "delivery",
    described(
        "The immutable envelope `leaf delivery read` prints "
        "(`references/event-batches.md`), in the state home's "
        "`deliveries/<id>.json`: the updates that need the agent's attention, one batch per page. Registry "
        "`when` clauses read its events, with an event's thread digest as `thread` "
        "(`registry.contract.event_clauses`).",
        object_schema(
            {
                "id": described(
                    "The delivery id, eight hex characters, which the agent's pointer "
                    "names.",
                    STRING,
                ),
                "created_at": described(
                    "When it was first collected, in seconds since the epoch.",
                    {"type": "number"},
                ),
                "acknowledge": described(
                    "How the reader confirms receipt, or null where the harness did.",
                    {"type": ["string", "null"]},
                ),
                "batches": described(
                    "One per page.", {"type": "array", "items": _BATCH}
                ),
            },
            {
                "correction": described(
                    "Asks again for one answer whose Codex turn final Leaf refused to "
                    "post (`codex.prepare_reply_correction`).",
                    object_schema(
                        {
                            "delivery": described(
                                "The delivery whose answer was refused.", STRING
                            ),
                            "turn": described(
                                "The turn whose final was refused.", STRING
                            ),
                            "claim": described(
                                "The claim the refused final was written under.",
                                object_schema(
                                    {
                                        "id": described(
                                            "The claimant session.", STRING
                                        ),
                                        "generation": described(
                                            "The session generation the claim named.",
                                            STRING,
                                        ),
                                        "acquisition": described(
                                            "The claim's own identity.", STRING
                                        ),
                                    }
                                ),
                            ),
                            "diagnostic": described("Why Leaf refused it.", STRING),
                            "instruction": described(
                                "What the agent is to do: fix the failure and answer the "
                                "same input again.",
                                STRING,
                            ),
                        }
                    ),
                )
            },
        ),
    ),
    since=15,
)
DELIVERY_ID = re.compile(r"[0-9a-f]{8}")


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


def _retire_gone_deliveries() -> None:
    """Remove envelopes whose pages are all gone, whichever Leaf froze them.

    Envelopes are read one id at a time, so the only enumeration of them is here,
    under the lock every new one is written under."""
    for path in (state_home() / "deliveries").glob("*.json"):
        retire_if_gone(path)


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
    if event["kind"] in verb_writers():
        return {"kind": "widget", "id": event["widget"]}
    if event["kind"] == "undo":
        original = by_id.get(event["undoes"])
        if original is not None:
            return _subject(original, threads, by_id)
    if threads:
        return {"kind": "thread", "id": threads[0]}
    return {"kind": "page"}


def current_responses(
    page_dir: Path, events: list[dict], reading=None
) -> dict[str, dict]:
    """Map every event that owns an answer to its exact response address.

    The address is the owed answer `activity` derives from the input's obligation
    record (`obligations.response_address`), so a delivery, a writer's refusal and
    the Stop hook name the same operation. An input a newer one in its thread covers
    publishes no record and owns none; the newest carries the thread's one answer.
    """
    from .served_state.context import read_page

    reading = reading or read_page(page_dir, events)
    return {item["input"]: item["answer"] for item in reading.work.obligations}


def _users_words_in_a_thread(event: dict) -> bool:
    """The user's reply in words, which may answer a widget frozen up its thread."""
    return (
        event["kind"] == "reply"
        and event.get("author") == "user"
        and "token" not in event
    )


def batch_data(
    page_dir: Path, transaction, batch: list[dict], *, responses: dict | None = None
) -> dict:
    """Capture one complete ordered page batch, less what `freeze_delivery` writes
    for its transport: the address of a thread reply, and the `handling` that follows
    from it."""
    from .events import build_threads
    from .gesture_words import GestureWords, revisions_on_disk
    from .obligations import waiting_about, waiting_in_thread
    from .registry.contract import event_spec
    from .revision_artifact import active_enclosing
    from .served_state.context import read_page
    from .thread_context import (
        batch_threads,
        thread_memberships,
        thread_names,
        thread_structure,
        thread_widgets,
        unsent_at_messages,
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
    # The obligations are read only where an event can carry `waiting`: an action,
    # or the user's reply on a page whose agent messages carry markup that may ask.
    reads_obligations = any(event["kind"] == "action" for event in batch) or (
        any(map(_users_words_in_a_thread, batch))
        and any(
            event.get("markup") and event.get("author") == "agent" for event in events
        )
    )
    reading = (
        read_page(page_dir, events) if responses is None or reads_obligations else None
    )
    if responses is None:
        responses = current_responses(page_dir, events, reading)
    if reads_obligations:
        assert reading is not None
    durable = (
        reading.work.durable if reading is not None and reads_obligations else None
    )
    revisions = {
        revision["id"]: revision
        for thread in build_threads(events, within).values()
        for revision in thread["revisions"]
    }
    by_id = {event["id"]: event for event in events}
    words = GestureWords(events, registry, revisions_on_disk(page_dir))

    def records_unsent(action: dict) -> bool:
        # Which verbs record unsent work is the vocabulary's word, as `says` is, and
        # the word of the document the user acted in.
        spec = event_spec(words.declaration(action), action)
        return bool(spec and spec.get("unsent"))

    unsent = (
        {}
        if registry is None
        else unsent_at_messages(events, batch, within, records_unsent)
    )

    captured = []
    for event in batch:
        threads = memberships.get(event["id"], [])
        entry = {
            **event,
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
            entry["names"] = {
                identity: words.name(event, identity) for identity in says
            }
        if revision := revisions.get(event["id"]):
            # The thread's digest already reads the new wording; the agent answering
            # a revision needs to see what it replaced, and whether those words are a
            # suggestion's exact replacement text.
            entry["was"] = revision["was"]
            if by_id[revision["message"]].get("suggestion"):
                entry["suggestion"] = True
        if work := unsent.get(event["id"]):
            entry["unsent"] = work
        if (answer := responses.get(event["id"])) is not None:
            entry["answer"] = answer
        if durable is not None and (
            waiting := waiting_about(
                event["widget"],
                durable.all_obligations["all"],
                durable.threads,
                durable.within,
            )
            if event["kind"] == "action"
            else [
                question
                for thread in threads
                for question in waiting_in_thread(
                    thread,
                    event["seq"],
                    durable.all_obligations["all"],
                    durable.threads,
                )
            ]
            if _users_words_in_a_thread(event)
            else None
        ):
            entry["waiting"] = waiting
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


def batch_refs(batch: dict) -> dict[str, dict]:
    """The `answer.ref` one frozen envelope batch gives each input it owes an
    answer, by input id, with the claim the batch was captured under, which is the
    only owner `post_reply` lets write at it."""
    return {
        event["id"]: {"ref": event["answer"]["ref"], "claim": batch["claim"]}
        for event in batch["events"]
        if "answer" in event
    }


def reads_reference(reference: str) -> bool:
    """Whether this Leaf reads the delivery that emitted `reference`. It may not
    read one another Leaf wrote (`state.Record`), so the update it owes an answer
    has no usable reference and is delivered again (`unreferenced`)."""
    return stored_delivery(reference.partition(":")[0]) is not None


def response_address(reference: str) -> dict:
    """Resolve only a complete reference emitted by an immutable delivery.

    Page-local event ids are not addresses. The delivery and batch qualify them;
    consumers use the captured destination rather than interpreting the id again.
    The writer rechecks the captured event against the page log under its lock.
    """
    payload = read_delivery(reference.partition(":")[0])
    for address in response_addresses(payload):
        if address["ref"] == reference:
            acting_on(Path(address["page"]))
            return address
    raise Refused(f"unknown response reference {reference!r}")


def stream_reply_target(payload: dict) -> dict | None:
    """The delivery's sole turn-written reply address, including its capture fences."""
    targets = [
        address
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
    """One captured batch with exact references, writer hints and handling.

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
    batches: Iterable[dict],
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
                if not path.exists():
                    break
        else:
            path = delivery_path(delivery_id)
        payload = {
            "id": delivery_id,
            "created_at": created_at if created_at is not None else time.time(),
            "acknowledge": acknowledge(delivery_id) if acknowledge else None,
            **({"correction": correction} if correction is not None else {}),
            "batches": [
                {field: batch[field] for field in _BATCH["properties"]}
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
        if path.exists():
            if DELIVERY.read(path) != payload:
                raise DeliveryIdConflict(
                    f"delivery {delivery_id!r} already exists with other data"
                )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            DELIVERY.write(path, payload)
        return DELIVERY.stored(payload)


def stored_delivery(delivery_id: str) -> dict | None:
    """The envelope with this id, or None where this Leaf reads none. An envelope
    names its `format` to whoever reads it (`references/event-batches.md`)."""
    payload = DELIVERY.read(delivery_path(delivery_id))
    return DELIVERY.stored(payload) if payload is not None else None


def read_delivery(delivery_id: str) -> dict:
    """The envelope with this id, refusing an id with none this Leaf reads."""
    try:
        path = delivery_path(delivery_id)
    except ValueError as error:
        raise Refused(str(error)) from error
    payload = stored_delivery(delivery_id)
    if payload is None and path.exists():
        raise Refused(
            f"delivery {delivery_id!r} was written by another Leaf, in a form this "
            f"one does not read ({DELIVERY.format!r}). The updates it carried that "
            "still owe an answer come again in the page's next delivery."
        )
    if payload is None:
        raise Refused(f"unknown delivery {delivery_id!r}")
    return payload


def acting_on_delivery(payload: dict) -> None:
    """Note each page the delivery `payload` carries input from as one the running
    command acts on (`interaction_log.acting_on`)."""
    for batch in payload["batches"]:
        acting_on(Path(batch["page"]))


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


def reader_envelope(payload: dict) -> dict:
    """The complete frozen input with its explicit reader receipt instruction."""
    return {
        **payload,
        "acknowledge": payload["acknowledge"] or pointer_acknowledgement(payload["id"]),
    }


def delivery_reading(payload: dict, *, part: int = 1) -> dict:
    """Render bounded reader input, leaving its captured facts and refs immutable.

    The stored envelope's acknowledger belongs to its original transport. A CLI
    reader instead attests complete receipt explicitly, even when the original
    transport could establish entry itself. Large readings expose lossless text
    parts with a next command; only the last offers confirmation.
    """
    reading = reader_envelope(payload)
    serialized = jsonl_line(reading)
    if len(serialized.encode("utf-8")) + 1 <= READ_BYTES:
        if part != 1:
            raise Refused("this delivery has only one part")
        return reading
    count = (len(serialized) + READ_CHARS - 1) // READ_CHARS
    if not 1 <= part <= count:
        raise Refused(f"delivery part must be between 1 and {count}")
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


def cmd_delivery_read(delivery_id: str, *, part: int = 1) -> dict:
    """Bounded immutable input, read without changing receipt or ownership."""
    payload = read_delivery(delivery_id)
    acting_on_delivery(payload)
    return delivery_reading(payload, part=part)


def cmd_delivery_ack(delivery_id: str) -> None:
    """Accept the reader's attestation that every part reached its context. A
    page the delivery names that has gone refuses it in the system's own words. A
    delivery an earlier turn already picked up is noted as a repeat
    (`earlier_pickup`)."""
    try:
        receive_delivery(delivery_id)
    except FileNotFoundError as error:
        raise Refused(str(error)) from error
    harness = session_harness()
    if harness and (
        repeat := earlier_pickup(read_delivery(delivery_id), harness.session)
    ):
        from .findings import note

        note(repeat)


def earlier_pickup(payload: dict, session_id: str):
    """The note saying that an earlier turn of `session_id` already picked up the
    delivery `payload`, or None where none did.

    `codex queue` takes no message id, so a failure after it returns and before
    Leaf records the acceptance queues the same pointer again, and Codex runs a
    turn for each (`codex_adapter._offer_queued_delivery`). The page log's opened
    pickups name the turns that took the delivery, and the note names them with
    the answers its updates still owe, read from the page rather than the
    agent's memory, so the turn acknowledging it again repeats no work and still
    answers what the earlier turn left owed."""
    from .activity import answer_command
    from .findings import Finding
    from .served_state.context import read_page

    record = session_record(session_id)
    assert record is not None
    turn = record["turn"]
    turns, answers = set(), []
    for batch in payload["batches"]:
        page_dir = Path(batch["page"])
        inputs = {event["id"] for event in batch["events"]}
        with PageTransaction(page_dir) as page:
            earlier = {
                receipt["turn"]
                for receipt in pickup_receipts(page.events, phase="opened")
                if receipt["session"] == session_id
                and receipt["turn"] != turn
                and inputs.intersection(receipt["events"])
            }
            if not earlier:
                continue
            turns |= earlier
            answers += [
                answer_command(item["answer"], page_dir)
                for item in read_page(page_dir, page.events).work.obligations
                if item["input"] in inputs
            ]
    if not turns:
        return None
    return Finding(
        "delivery-repeated",
        values={
            "delivery": payload["id"],
            "turns": sorted(turns, key=str),
            "answers": answers,
        },
        severity="advice",
    )


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


def reminded(events: list[dict], input_id: str) -> bool:
    """Whether a prompt has named `input_id` to the agent since its newest
    delivery: an opened pickup without its `answer.ref`, which the prompt hook
    records as it re-presents an update already received and still owed
    (`hook_transport.pick_up_acknowledged`), after the newest pickup that carried
    one."""
    delivered = named = 0
    for pickup in pickup_receipts(events, phase="opened", input_id=input_id):
        if input_id in pickup.get("refs", {}):
            delivered = pickup["seq"]
        else:
            named = pickup["seq"]
    return named > delivered


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
    refs: dict[str, dict] | None = None,
) -> dict | None:
    """Durably record one delivery transition for exact attention-bearing inputs.

    ``queued`` means Codex's durable same-task queue accepted the batch;
    ``opened``, which the page shows as Delivered, means the batch was handed into
    the harness's context for the session: written into the conversation its model
    reads at its next step, whether or not that step has come, or, for a hook whose
    output the harness may still drop, handed over pending the receipt the turn's
    the harness's record shows in the model's context (`confirm_entered`). A batch
    the harness holds to add later, as
    a queue or a steer waiting behind a running tool, is not opened until it is
    added. ``failed`` means the harness
    gave up on the updates with the named ``failure`` and no answer is coming.
    Queued and opened are transport evidence, not authored work claims. A queued
    transition may therefore be followed by an opened transition for the same
    events, while a retry of the same transition appends nothing.

    ``refs`` are the `answer.ref`s the receipt's envelope batch gave the inputs it
    owes, each with the claim the batch was captured under (`batch_refs`), which
    the record keeps for the inputs it names, so the page's workflows can name each
    owed input's ref to the owner who can use it (`activity._receipt_bindings`). A
    transition that carries no envelope, such as the prompt re-presenting debt an
    earlier receipt recorded, passes none.
    """
    claim = page.claim
    if session is None and claim:
        session = claim["id"]
    if phase == "opened" and turn is None and claim and claim["id"] == session:
        turn = claim["turn"]
    wanted = [event["id"] for event in events if requires_agent_attention(event)]
    pickups = [event for event in page.events if event["kind"] == "pickup"]
    picked = {
        (event_id, event["phase"], event["session"], event["turn"])
        for event in pickups
        for event_id in event["events"]
    }
    # The newest ref recorded for each input under each claim, the one `workflows`
    # binds.
    referenced = {
        (event_id, ref["claim"]): ref["ref"]
        for event in pickups
        for event_id, ref in event.get("refs", {}).items()
    }
    refs = refs or {}

    def usable(event_id: str) -> bool:
        held = referenced.get((event_id, refs[event_id]["claim"]))
        return held is not None and reads_reference(held)

    # A transition already on record is recorded again only to give an input a ref
    # its claim can use, as when a delivery hands the page's owner debt an older
    # receipt, or an earlier owner's, left without one (`unreferenced`), and the
    # prompt has already re-presented it. Otherwise that debt stays deliverable.
    fresh = list(
        dict.fromkeys(
            event_id
            for event_id in wanted
            if (event_id, phase, session, turn) not in picked
            or (event_id in refs and not usable(event_id))
        )
    )
    if not fresh:
        return None
    carried = {event_id: refs[event_id] for event_id in fresh if event_id in refs}
    from .event_contracts import append_admitted

    record, _ = append_admitted(
        page,
        {
            "kind": "pickup",
            "author": "page",
            "events": fresh,
            "phase": phase,
            "session": session,
            "turn": turn,
            **({"failure": failure} if failure is not None else {}),
            **({"refs": carried} if carried else {}),
        },
    )
    return record


def deliverable(
    page: PageTransaction,
    obligations: list[dict] | None = None,
    *,
    received: bool = True,
) -> list[dict]:
    """The input a session of this Leaf may hand the page's owner, in log order: what
    the cursor has not passed, less what a hook handed into the owner's turn that is
    still open, pending the receipt its harness's record confirms
    (`awaiting_receipt`), and
    each update the cursor has passed that still owes an answer the owner holds no
    usable `answer.ref` for (`unreferenced`, which reads `obligations` where the
    caller has already folded the page).

    A handover the harness's record never showed in the model's context is input
    again once its turn reads ended: Escape while Claude Code still ran a prompt hook
    dropped the prompt, Leaf's context with it, so the update reached no model.

    The second kind is how a page that changed hands reaches its new owner: an
    update the previous owner received but did not answer advanced the cursor, and
    its ref names the previous claim, which `post_reply` refuses. So every transport
    hands it to the new owner as it hands new input, and the receipt records the
    owner's ref, after which it is no longer deliverable.

    None on a page whose log this Leaf may not write
    (`event_contracts.write_refusal`), where `receive_batch` refuses its receipt.
    Handed over anyway, it stayed pending, so a watch woke its session on every pass
    and a Codex watch opened a turn for it each time. Its session's hooks and
    commands renew such a page's layer before they read it (`vendoring.renew_layer`),
    so input waits here only on a page whose renewal was refused, and the hooks name
    why (`hook_transport.remedies`).

    Which updates are owed is the page's fold, whose page model costs about 70 ms
    of CPU to import. Codex's tool hook runs after every tool call, so it passes
    `received=False` and hands over only what the cursor has not passed, answered
    without loading the page's layer where nothing is pending; the adapter, or the
    Stop hook where no adapter runs, hands over the rest
    (`harness.CodexHarness.offer_at_step`)."""
    pending = unacknowledged(page.events, page.cursor)
    if pending and (held := awaiting_receipt(page)):
        pending = [event for event in pending if event["id"] not in held]
    owed = unreferenced(page, obligations) if received else []
    if not pending and not owed:
        return []
    from .event_contracts import write_refusal

    if write_refusal(page.page_dir):
        return []
    return sorted([*owed, *pending], key=lambda event: event["seq"])


def handed_into_turn(events: list[dict], session: str, turn: str) -> list[str]:
    """The inputs a hook handed into `session`'s turn `turn`, by its opened pickups
    (`record_pickup`). A prompt Escape dropped is submitted again as a turn of its
    own (`ClaudeCodeHarness.hook_payload`), so what was handed into the dropped one
    is no longer awaited."""
    return [
        event_id
        for pickup in pickup_receipts(events, phase="opened")
        if (pickup["session"], pickup["turn"]) == (session, turn)
        for event_id in pickup["events"]
    ]


def awaiting_receipt(page: PageTransaction) -> set[str]:
    """The updates past the page's cursor that a hook handed into its owner's open
    turn (`handed_into_turn`), whose receipt waits for the harness's record of the
    model's context (`confirm_entered`). Empty once the turn reads ended, closed by
    a Stop hook or interrupted as its harness's record says
    (`activity.claimant_turn`): what that record still lacks reached no model."""
    claim = page.active_claim
    if claim is None or turn_closed(claim):
        return set()
    seqs = {event["id"]: event["seq"] for event in page.events}
    handed = {
        event_id
        for event_id in handed_into_turn(page.events, claim["id"], claim["turn"])
        if seqs[event_id] > page.cursor
    }
    if not handed:
        return set()
    from .presence import claimant_reading

    _, turn = claimant_reading(page.page_dir, page.events)
    return handed if turn.ended is None else set()


def confirm_entered(harness, payload: dict) -> None:
    """Record the receipt of what this session's hooks handed over inline and its
    harness's record, named in hook `payload`, shows in the model's context
    (`Harness.entered_context`), on every page the session holds: the receipt of
    the pending input before the first update that record does not show
    (`record_receipt`), since the cursor passes every input before the position it
    moves to. On a Claude Code that names no turn, an update handed into a prompt
    Escape dropped still awaits its receipt when a later tool boundary's handover
    reaches the model (`ClaudeCodeHarness.hook_payload`), and it stays input. Every
    hook of a harness whose hooks don't commit their context runs this before it
    reads the page, so the prompt a nudge wakes after an interrupt confirms what the
    interrupted turn read before it hands anything over."""
    from .service import owned_pages

    entered = harness.entered_context(payload)
    if not entered:
        return
    for page_dir in owned_pages(harness.session):
        try:
            with (
                PageTransaction(page_dir) as page,
                flocked(session_lock_path(harness.session), deadline=page.deadline),
            ):
                if page.claim_of(harness.session) is None:
                    continue
                shown = {
                    event_id
                    for pickup in pickup_receipts(page.events, phase="opened")
                    if pickup["session"] == harness.session
                    for event_id in pickup["events"]
                    if event_id in entered
                }
                through = page.cursor
                for event in unacknowledged(page.events, page.cursor):
                    if event["id"] not in shown:
                        break
                    through = event["seq"]
                record_receipt(page, through)
        except FileNotFoundError:
            continue


def unreferenced(
    page: PageTransaction, obligations: list[dict] | None = None
) -> list[dict]:
    """The updates the page's cursor has passed that still owe an answer its owner
    holds no usable `answer.ref` for: received under another session's claim before
    the page changed hands, received while they owed nothing, or referenced by a
    delivery this Leaf cannot read (`reads_reference`). `obligations` is the
    page's fold where the caller has one; otherwise this folds the page."""
    if obligations is None:
        from .served_state.context import read_page

        obligations = read_page(page.page_dir, page.events).work.obligations
    by_id = {event["id"]: event for event in page.events}
    cursor = page.cursor
    return [
        by_id[item["input"]]
        for item in obligations
        if item["seq"] <= cursor
        and ("ref" not in item["answer"] or not reads_reference(item["answer"]["ref"]))
    ]


class ReceiptRefused(Refused):
    """Captured input no longer belongs to this receiver or page log, or sits on a
    page whose log this Leaf may not write."""


@contextmanager
def receive_batch(
    page: PageTransaction,
    batch: dict,
    *,
    session_id: str | None,
    confirm: bool = True,
) -> Generator[list[dict]]:
    """Commit receipt after the consumer records its durable pickup evidence.

    Every transport confirms here once its durable consumer accepts input.
    The body records pickup and turn entry before this records the receipt, so
    interruption leaves input available for retry. Work remains separate. A hook
    whose harness may still drop its output hands the batch over without the
    receipt (`confirm`), which follows the harness's record (`confirm_entered`).
    Current ownership authorizes the write, not capture-time ownership: the
    page is still the receiver's (`service.claim_names_session`), even between a
    restart's new generation and its claim, and an old envelope can be confirmed
    after ownership returns to its receiver. A receiver with no session takes
    receipt only while no session holds the page. Nor does one take it on a page
    at another protocol (`event_contracts.write_refusal`): its body could
    record no pickup there, and every transport retires a refused receipt rather
    than retrying it, leaving the input for a Leaf that can write the page.
    """
    from .event_contracts import write_refusal

    # The page is already locked; keep lifecycle admission valid through pickup
    # and receipt. SessionEnd cannot cross between those writes.
    with (
        flocked(session_lock_path(session_id), deadline=page.deadline)
        if session_id
        else nullcontext()
    ):
        if not may_receive(page.claim, session_id):
            raise ReceiptRefused(f"delivery no longer owns its page: {page.page_dir}")
        if refusal := write_refusal(page.page_dir):
            raise ReceiptRefused(str(refusal))
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
        if confirm:
            record_receipt(page, max(expected))


def record_receipt(page: PageTransaction, through: int) -> None:
    """Confirm receipt of the page's input through seq `through`, under the
    caller's page transaction: a `receipt` event, which moves the acknowledgement
    cursor (`service.acknowledged`) and nothing else. A position the cursor has
    already passed writes nothing, so the cursor only moves forward and a retried
    receipt appends nothing."""
    if through <= page.cursor:
        return
    from .event_contracts import append_admitted

    append_admitted(page, {"kind": "receipt", "author": "page", "through": through})


def receive_delivery(delivery_id: str) -> list[Path]:
    """Confirm a reader's complete input and record its entry into that turn.

    The explicit acknowledgement command, `leaf delivery ack`, proves the
    consumer is running even if its prompt hook failed. The canonical opener preserves known provider
    lifecycle authority. Pointer receipt also retains its origin's reservation,
    including the exact turn a Codex hook offered it to. Automatic hook and
    provider receipts observe an already-open turn through `receive` instead.
    """
    payload = read_delivery(delivery_id)
    acting_on_delivery(payload)
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
    payload: dict,
    session_id: str,
    expected: dict,
    *,
    deadline: float | None = None,
    confirm: bool = True,
) -> list[dict]:
    """Record each batch of a delivery its hook is handing to `session_id`'s open
    turn, the lifecycle `expected` it planned under, as opened in it, and return
    the batches it recorded. `confirm` also records the receipt, where the harness
    has the context once the hook returns (`Harness.commits_hook_context`).

    A refusal is the batch's own: a page that changed hands or went, a turn that
    ended or was replaced, a log this Leaf may not write
    (`layer.incompatible_layer`), or locks still held at `deadline`, for a hook
    that must exit by then for its handover to stand. The other batches are still
    recorded, and the hook hands only those over (`hook_transport.carry_turn`)."""
    recorded = []
    for batch in payload["batches"]:
        try:
            receive_one(
                batch,
                session_id,
                deadline=deadline,
                expected=expected,
                confirm=confirm,
            )
        except (FileNotFoundError, Refused, TimeoutError):
            continue
        recorded.append(batch)
    return recorded


def receive_one(
    batch: dict,
    session_id: str | None,
    *,
    deadline: float | None = None,
    expected: dict | None = None,
    confirm: bool = True,
) -> Path:
    """Confirm one consumer-read batch under its current page ownership, into the
    session lifecycle `expected` where the caller names one; `confirm` as
    `receive_batch` takes it."""
    page_dir = Path(batch["page"])
    with (
        PageTransaction(page_dir, deadline=deadline) as page,
        receive_batch(page, batch, session_id=session_id, confirm=confirm) as events,
    ):
        turn = None
        if session_id:
            observed = session_record(session_id)
            assert observed is not None
            if turn_closed(observed):
                raise ReceiptRefused("the receiving provider turn has ended")
            if expected is not None and observed != expected:
                raise ReceiptRefused("the receiving turn has been replaced")
            # Receipt observes the consumer turn. The explicit acknowledgement
            # boundary can open an unnamed turn; hooks and providers cannot.
            turn = observed["turn"]
        record_pickup(
            page, events, session=session_id, turn=turn, refs=batch_refs(batch)
        )
    return page_dir
