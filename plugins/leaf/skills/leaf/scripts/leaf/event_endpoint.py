"""Browser-event admission, retry coordination, and transactional append."""

import threading
from collections.abc import Callable
from pathlib import Path

from .event_log import (
    AttemptConflict,
    AttemptExecution,
    _attempt_payload,
    append_event,
)
from .events import undo_error
from .files import list_revisions, version_revisions
from .passages import active_enclosing
from .registry import RegistryError, load_registry, reaction_tokens
from .schema import MESSAGE_KINDS
from .service import PageTransaction
from .structure import parse_revision, revision_review_mode
from .validation import (
    action_contract_error,
    event_record_error,
    held_comment_error,
    version_response_comment_error,
    visual_anchor_error,
)

EventAnswer = tuple[int, dict]
StateReader = Callable[[], dict]


def event_rejection(event: dict, error: str, status: int = 400) -> EventAnswer:
    """A final answer proving that this execution appended no event."""
    body = {"ok": False, "error": error, "final": True}
    if event.get("attempt"):
        body["attempt"] = event["attempt"]
    return status, body


class EventEndpoint:
    """The browser's one write door for a served page.

    A generated HTTP handler class owns one endpoint, so concurrent request handlers
    share active attempt executions while separate page servers share nothing. The
    accepted-state reader stays request-local because it belongs to the transport's
    publication view, not to event validation or storage.
    """

    def __init__(self, page_dir: Path):
        self.page_dir = page_dir
        self._attempts: dict[str, AttemptExecution] = {}
        self._attempts_lock = threading.Lock()

    def accept(self, event: dict, state: StateReader) -> EventAnswer:
        """Validate one browser record, coordinate its attempt, and execute it."""
        try:
            registry = load_registry(self.page_dir)
        except RegistryError as error:
            return event_rejection(event, str(error))
        if registry is None:
            return event_rejection(event, "the page has no registry.json")
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
        if error := event_record_error(contracts[kind], event, browser=True):
            return event_rejection(event, f"{kind} event is invalid: {error}")
        return self._coordinate(event, state)

    def _coordinate(self, event: dict, state: StateReader) -> EventAnswer:
        """Run one copy of an attempt and share its outcome with concurrent copies."""
        attempt = event.get("attempt")
        if not attempt:
            return self._execute(event, state)
        payload = _attempt_payload(event)
        with self._attempts_lock:
            execution = self._attempts.get(attempt)
            if execution is None:
                execution = AttemptExecution(payload)
                self._attempts[attempt] = execution
                owner = True
            else:
                owner = False
                if execution.payload != payload:
                    return event_rejection(
                        event,
                        f"attempt {attempt!r} already belongs to another event",
                        409,
                    )
        if not owner:
            execution.done.wait()
            return execution.result
        try:
            result = self._execute(event, state)
        except Exception as error:  # noqa: BLE001 - every waiter needs an outcome
            # A fault may occur after append. Withholding `final` makes the next
            # identical request find the accepted event or execute the attempt again.
            result = (
                500,
                {
                    "ok": False,
                    "attempt": attempt,
                    "error": f"{type(error).__name__}: {error}",
                },
            )
        finally:
            execution.result = result
            execution.done.set()
            # Waiters retain the execution object. Acceptance is durable in the log;
            # every other outcome must be evaluated again if it is posted later.
            with self._attempts_lock:
                if self._attempts.get(attempt) is execution:
                    del self._attempts[attempt]
        return result

    def _execute(self, event: dict, state: StateReader) -> EventAnswer:
        """Validate mutable page state and append as one log transaction.

        `accept` checks the payload's declared shape before attempt coordination. A
        re-vendor can replace that declaration before this transaction is acquired,
        so an action's contract is deliberately read again inside the lease: this
        reading, not the admission reading, is the one allowed to append beside the
        page's current vocabulary.
        """
        kind = event["kind"]
        # Every decision whose validity depends on the log stays under the append
        # lock through the write. In particular, two tabs cannot both validate an
        # undo against the same standing target and append after either lock is gone.
        accepted = False
        with PageTransaction(self.page_dir) as page:
            # Acceptance outranks mutable state validation. A retry for an accepted
            # attempt asks for its state; it does not repeat the gesture.
            if "attempt" in event:
                event["author"] = "user"
                try:
                    existing = page.matching_attempt(event)
                except AttemptConflict as error:
                    return event_rejection(event, str(error), 409)
                if existing:
                    accepted = True
            if not accepted:
                events = page.events
                if "revision" in event:
                    live_revisions = list_revisions(self.page_dir)
                    if event["revision"] not in live_revisions:
                        return event_rejection(
                            event,
                            f"{kind} revision must be one of {live_revisions}",
                        )
                if kind == "done":
                    mapped = version_revisions(events).get(event["version"])
                    if mapped != event["revision"]:
                        return event_rejection(
                            event,
                            f"v{event['version']} does not stamp revision "
                            f"r{event['revision']}",
                        )
                    mode = revision_review_mode(self.page_dir, event["revision"])
                    if mode != "sign-off":
                        return event_rejection(
                            event,
                            f"v{event['version']} does not declare "
                            '<meta name="lf-review" content="sign-off">, so it has no '
                            "approval to record",
                        )
                # Not the static admission read in `accept`: re-vendoring and this
                # transaction have now chosen an order, so only this registry can
                # authorize what will be appended under the same lease. Read once, by
                # the three checks that ask for it.
                vendored = None

                def registry_or_rejection():
                    nonlocal vendored
                    if vendored is None:
                        try:
                            vendored = load_registry(self.page_dir)
                        except RegistryError as error:
                            return None, event_rejection(event, str(error))
                        if vendored is None:
                            return None, event_rejection(
                                event, "the page has no registry.json"
                            )
                    return vendored, None

                if kind == "action":
                    registry, rejection = registry_or_rejection()
                    if rejection:
                        return rejection
                    if error := action_contract_error(
                        self.page_dir,
                        event,
                        events,
                        registry,
                    ):
                        return event_rejection(event, error)
                if event.get("token"):
                    # Against the vocabulary vendored under this lease, the way
                    # an action's verb is: a token the layer does not declare has
                    # no glyph to paint and no meaning for `leaf wait` to print.
                    registry, rejection = registry_or_rejection()
                    if rejection:
                        return rejection
                    tokens = reaction_tokens(registry)
                    if event["token"] not in tokens:
                        return event_rejection(
                            event,
                            f"unknown reaction token {event['token']!r}; this "
                            f"layer declares {sorted(tokens)}",
                        )
                anchor = event.get("anchor") or {}
                if kind == "comment" and (
                    event.get("holds") or event.get("response") or anchor.get("visual")
                ):
                    registry, rejection = registry_or_rejection()
                    if rejection:
                        return rejection
                    page_by_id = parse_revision(self.page_dir, event["revision"]).by_id
                    for error in (
                        held_comment_error(event, page_by_id, registry),
                        version_response_comment_error(event, page_by_id, registry),
                        visual_anchor_error(event, page_by_id, registry),
                    ):
                        if error:
                            return event_rejection(event, error)
                if "parent" in event and event["parent"] not in {
                    e["id"] for e in events if e["kind"] in MESSAGE_KINDS
                }:
                    return event_rejection(event, f"unknown parent {event['parent']!r}")
                if kind == "undo" and (
                    error := undo_error(event, events, active_enclosing(self.page_dir))
                ):
                    return event_rejection(event, error)
                event["author"] = "page" if kind == "error" else "user"
                append_event(page, event)
        return 200, {"ok": True, "state": state()}
