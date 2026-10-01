"""The browser's door onto the page event log.

Transport only: what a tab is allowed to send, how a retry is answered, and the
HTTP shape of an acceptance or a refusal. Which events the log takes, and what
they mean once it has them, is `event_contracts.append_admitted` — the one door
this endpoint shares with every other writer.
"""

from collections.abc import Callable
from pathlib import Path

from .activity import takes_input
from .event_contracts import (
    EventRefused,
    admitting_registry,
    append_admitted,
    browser_command_error,
)
from .event_log import AttemptConflict
from .host import claim_harness
from .leases import wait_is_live
from .page_view import PageView
from .presence import claimant_reading
from .registry.contract import RegistryError
from .service import PageTransaction, requires_agent_attention
from .thread_titles import name_opened_thread

EventAnswer = tuple[int, dict]
StateReader = Callable[[], dict]


def event_rejection(event: dict, error: str, status: int = 400) -> EventAnswer:
    """A final answer proving that this execution appended no event."""
    body = {"ok": False, "error": error, "final": True}
    if event.get("attempt"):
        body["attempt"] = event["attempt"]
    return status, body


def event_fault(event: dict, error: str) -> EventAnswer:
    """An answer that withholds `final`: the fault may have landed either side of
    the append, so the next identical request finds the accepted event or executes
    the attempt again. The HTTP boundary writes it, as it writes every 500."""
    body = {"ok": False, "error": error}
    if event.get("attempt"):
        body["attempt"] = event["attempt"]
    return 500, body


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
) -> EventAnswer:
    """Validate and append one browser record, then return its current state."""
    try:
        # The shape check before the lease reads no log, so a sign-off checks its
        # kind against the newest vocabulary; admission inside the lease reads the
        # version's own.
        registry = admitting_registry(PageView(page_dir), event, [])
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
    # A fault raises out of here, before or after the append, and the transport's
    # one fault boundary answers it with `event_fault`.
    return _execute_event(page_dir, event, state)


def _execute_event(
    page_dir: Path,
    event: dict,
    state: StateReader,
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
    opened = None
    with PageTransaction(page_dir) as page:
        # Acceptance outranks mutable state validation. A retry for an accepted
        # attempt asks for its state; it does not repeat the gesture.
        accepted, rejection = _accepted_retry(page, event)
        if rejection:
            return rejection
        if not accepted:
            event["author"] = "page" if event["kind"] == "error" else "user"
            try:
                admitted = append_admitted(page, event)
            except EventRefused as error:
                return event_rejection(event, error.user)
            except RegistryError as error:
                return event_rejection(event, str(error))
            claim = page.active_claim
            # Input no carrier will pick up: the claimant takes no input, by the
            # activity fold's own reading (`activity.takes_input`), because its
            # turn was seen to end — closed by the Stop hook, or interrupted as
            # its host's record says — and no wait lease is held. A turn Leaf
            # only stopped believing in may still be running a long step, and a
            # running turn needs no nudge, because its Stop hook refuses to end
            # with the input unpicked. Each ending gets one nudge per page, named
            # by the claim's turn and the stamp that ended or last renewed it, so
            # a user ticking three boxes queues one turn or one approval rather
            # than three, while a turn interrupted again after a new prompt is
            # messaged again. The claimant's harness decides whether its session
            # can be reached at all and what to say; a harness whose carrier is a
            # process of its own has nowhere to put this and answers no. It is
            # sent under the lock, so the mark it leaves is exact: a local socket
            # accepts or refuses at once, and input after a refusal tries again.
            if requires_agent_attention(event):
                nudge_unwatched(page)
            if event["kind"] == "comment" and claim:
                opened = admitted["id"], claim
    # A comment opens a thread with no name, and the claimant's host names it from
    # these words while the agent is still reading them. The request reads the
    # thread under the page's lock, so it starts once the lock is given back.
    if opened and (generate := claim_harness(opened[1]).title_generator()):
        name_opened_thread(generate, page_dir, opened[0], opened[1]["id"])
    return 200, {"ok": True, "state": state()}


def nudge_unwatched(page: PageTransaction) -> None:
    """Message the claimant of a page holding input nothing will carry, once per
    ending of its turn (`session-lifetime.md`, Carriers): no wait lease is held,
    and its turn has ended, so nothing takes input by the activity fold's reading
    (`activity.takes_input`). Run under the page's lock, which makes the mark it
    leaves exact."""
    claim, page_dir = page.active_claim, page.page_dir
    if not claim or wait_is_live(page_dir, claim["id"]):
        return
    present, turn = claimant_reading(page_dir, page.events)
    stamp = claim.get("turn_closed") or claim.get("turn_opened")
    mark = f"{claim['turn']}@{stamp}"
    if (
        turn.ended is not None
        and not takes_input(present, turn)
        and claim.get("messaged_ending") != mark
        and claim_harness(claim).nudge(page_dir)
    ):
        page.note_messaged(mark)
