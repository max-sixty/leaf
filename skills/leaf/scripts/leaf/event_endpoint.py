"""The browser's door onto the page event log.

Transport only: what a tab is allowed to send, how a retry is answered, and the
HTTP shape of an acceptance or a refusal. Which events the log takes, and what
they mean once it has them, is `event_contracts.append_admitted` — the one door
this endpoint shares with every other writer.
"""

from collections.abc import Callable
from pathlib import Path

from .event_contracts import (
    EventRefused,
    admitting_registry,
    append_admitted,
    browser_command_error,
)
from .event_log import AttemptConflict
from .host import claim_harness
from .leases import wait_is_live
from .registry.contract import RegistryError
from .service import PageTransaction

EventAnswer = tuple[int, dict]
StateReader = Callable[[], dict]


def event_rejection(event: dict, error: str, status: int = 400) -> EventAnswer:
    """A final answer proving that this execution appended no event."""
    body = {"ok": False, "error": error, "final": True}
    if event.get("attempt"):
        body["attempt"] = event["attempt"]
    return status, body


def _accepted_retry(
    page: PageTransaction, event: dict
) -> tuple[bool, EventAnswer | None]:
    """Read an attempted retry before mutable-state validation."""
    if "attempt" not in event:
        return False, None
    # The append gate enriches an abbreviated text anchor with its canonical
    # context. A later retry still carries the original browser payload, so compare
    # it as that same payload rather than treating server-added fields as a conflict.
    existing = next(
        (logged for logged in page.events if logged.get("attempt") == event["attempt"]),
        None,
    )
    if (
        existing
        and event.get("kind") == existing.get("kind") == "comment"
        and isinstance(event.get("anchor"), dict)
        and isinstance(existing.get("anchor"), dict)
    ):
        for field, value in existing["anchor"].items():
            event["anchor"].setdefault(field, value)
    event["author"] = "user"
    try:
        existing = page.matching_attempt(event)
    except AttemptConflict as error:
        return False, event_rejection(event, str(error), 409)
    return bool(existing), None


def accept_event(
    page_dir: Path,
    event: dict,
    state: StateReader,
    *,
    capture_anchors: bool = False,
) -> EventAnswer:
    """Validate and append one browser record, then return its current state."""
    try:
        registry = admitting_registry(page_dir, event)
    except (EventRefused, RegistryError) as error:
        return event_rejection(event, str(error))
    contracts = registry["$events"]["kinds"]
    browser_kinds = sorted(
        name for name, contract in contracts.items() if "browser" in contract
    )
    kind = event.get("kind")
    if not isinstance(kind, str) or kind not in browser_kinds:
        return event_rejection(event, f"kind must be one of {browser_kinds}")
    # The server owns the record envelope and agent identity. Removing client
    # copies before validation prevents them from entering attempt identity too.
    for field in ("id", "author", "agent", "session", "ts", "seq"):
        event.pop(field, None)
    if error := browser_command_error(contracts[kind], event):
        return event_rejection(event, f"{kind} event is invalid: {error}")
    try:
        return _execute_event(page_dir, event, state, capture_anchors)
    except Exception as error:  # noqa: BLE001 - an uncertain write is retryable
        # A fault may occur after append. Withholding `final` makes the next
        # identical request find the accepted event or execute the attempt again.
        body = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        if attempt := event.get("attempt"):
            body["attempt"] = attempt
        return 500, body


def _execute_event(
    page_dir: Path,
    event: dict,
    state: StateReader,
    capture_anchors: bool,
) -> EventAnswer:
    """Admit and append as one log transaction, then read the page back.

    `accept_event` checks the payload's declared shape before the page transaction. A
    re-vendor can replace that declaration before this transaction is acquired, so the
    door reads the admitting vocabulary again inside the lease: that reading, not this
    endpoint's, is the one allowed to append beside the page's current vocabulary.

    Every decision whose validity depends on the log stays under the append lock
    through the write. In particular, two tabs cannot both validate an undo against
    the same standing target and append after either lock is gone.
    """
    with PageTransaction(page_dir) as page:
        # Acceptance outranks mutable state validation. A retry for an accepted
        # attempt asks for its state; it does not repeat the gesture.
        accepted, rejection = _accepted_retry(page, event)
        if rejection:
            return rejection
        if not accepted:
            event["author"] = "page" if event["kind"] == "error" else "user"
            try:
                append_admitted(page, event, capture_anchors=capture_anchors)
            except (EventRefused, RegistryError) as error:
                return event_rejection(event, str(error))
            claim = page.active_claim
            # Input no carrier will pick up: the claiming session holds no wait
            # lease, and none of its turns is running, since a delivering wait
            # and the prompt hook both reopen the turn the Stop hook closed. A
            # running turn needs no nudge, because its Stop hook refuses to end
            # with the input unpicked. A closed turn gets one nudge per page, so
            # a reader ticking three boxes queues one turn or one approval
            # rather than three. The claimant's harness decides whether its
            # session can be reached at all and what to say; a harness whose
            # carrier is a process of its own has nowhere to put this and
            # answers no. It is sent under the lock, so the mark it leaves is
            # exact: a local socket accepts or refuses at once, and input after
            # a refusal tries again.
            if (
                claim
                and claim["turn_closed"]
                and claim.get("messaged_turn") != claim["turn"]
                and not wait_is_live(page_dir, claim["id"])
                and claim_harness(claim).nudge(page_dir)
            ):
                page.note_messaged_turn()
    return 200, {"ok": True, "state": state()}
