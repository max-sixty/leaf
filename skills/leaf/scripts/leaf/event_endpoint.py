"""Browser-event admission, retry coordination, and transactional append."""

import threading
from collections.abc import Callable
from pathlib import Path

from .anchor_capture import capture_anchor
from .event_contracts import (
    action_contract_error,
    datum_anchor_error,
    event_record_error,
    held_comment_error,
    version_response_comment_error,
    visual_anchor_error,
)
from .event_log import (
    AttemptConflict,
    AttemptExecution,
    _attempt_payload,
)
from .events import undo_error
from .files import list_revisions, revision_path, version_revisions
from .passages import active_enclosing
from .projection import (
    generated_children,
    page_projection,
    retirement_outcomes,
    rewritten_bodies,
)
from .registry.contract import RegistryError
from .registry.reactions import reaction_tokens
from .registry.storage import load_registry
from .requests import request_contract_error
from .schema import MESSAGE_KINDS
from .service import PageTransaction
from .structure import parse_revision, revision_review_mode

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


class _TransactionValidation:
    """Ordered gates against the page state held by one append transaction."""

    def __init__(
        self, page_dir: Path, event: dict, events: list, capture_anchors: bool = False
    ):
        self.page_dir = page_dir
        self.event = event
        self.events = events
        self.capture_anchors = capture_anchors
        self.vendored = None

    def registry_or_rejection(self) -> tuple[dict | None, EventAnswer | None]:
        """Read the registry once, after this transaction chose its contract."""
        if self.vendored is None:
            try:
                self.vendored = load_registry(self.page_dir)
            except RegistryError as error:
                return None, event_rejection(self.event, str(error))
            if self.vendored is None:
                return None, event_rejection(
                    self.event, "the page has no registry.json"
                )
        return self.vendored, None

    def revision_rejection(self) -> EventAnswer | None:
        if "revision" not in self.event:
            return None
        live_revisions = list_revisions(self.page_dir)
        if self.event["revision"] not in live_revisions:
            return event_rejection(
                self.event,
                f"{self.event['kind']} revision must be one of {live_revisions}",
            )
        return None

    def approval_rejection(self) -> EventAnswer | None:
        if self.event["kind"] != "done":
            return None
        mapped = version_revisions(self.events).get(self.event["version"])
        if mapped != self.event["revision"]:
            return event_rejection(
                self.event,
                f"v{self.event['version']} does not stamp revision "
                f"r{self.event['revision']}",
            )
        mode = revision_review_mode(self.page_dir, self.event["revision"])
        if mode != "sign-off":
            return event_rejection(
                self.event,
                f"v{self.event['version']} does not declare "
                '<meta name="lf-review" content="sign-off">, so it has no '
                "approval to record",
            )
        return None

    def action_rejection(self) -> EventAnswer | None:
        if self.event["kind"] != "action":
            return None
        registry, rejection = self.registry_or_rejection()
        if rejection:
            return rejection
        if error := action_contract_error(
            self.page_dir,
            self.event,
            self.events,
            registry,
        ):
            return event_rejection(self.event, error)
        return None

    def request_rejection(self) -> EventAnswer | None:
        if self.event["kind"] != "request":
            return None
        registry, rejection = self.registry_or_rejection()
        if rejection:
            return rejection
        if error := request_contract_error(
            self.page_dir,
            self.event,
            self.events,
            registry,
        ):
            return event_rejection(self.event, error)
        return None

    def reaction_rejection(self) -> EventAnswer | None:
        if not self.event.get("token"):
            return None
        registry, rejection = self.registry_or_rejection()
        if rejection:
            return rejection
        tokens = reaction_tokens(registry)
        if self.event["token"] not in tokens:
            return event_rejection(
                self.event,
                f"unknown reaction token {self.event['token']!r}; this "
                f"layer declares {sorted(tokens)}",
            )
        return None

    def anchored_comment_rejection(self) -> EventAnswer | None:
        anchor = self.event.get("anchor") or {}
        # A passage anchor a runtime resolved against the rendered page is already
        # answered: the page holds words no file reading can produce — a widget's
        # label, a module's own rendering — and an earlier runtime may spell the same
        # words in whitespace this reading collapses away. Reading it back off the
        # file would refuse both. A transport that resolves nothing (the MCP surface,
        # which renders the authored source with no runtime behind it) asks for the
        # capture instead.
        recapture = bool(self.capture_anchors and anchor) and not (
            anchor.get("datum") or anchor.get("visual") or anchor.get("part")
        )
        if self.event["kind"] != "comment":
            return None
        validates_datum = bool(anchor.get("source"))
        if not (
            recapture
            or self.event.get("holds")
            or self.event.get("response")
            or anchor.get("visual")
            or validates_datum
        ):
            return None
        registry, rejection = self.registry_or_rejection()
        if rejection:
            return rejection
        page_by_id = parse_revision(self.page_dir, self.event["revision"]).by_id
        for error in (
            datum_anchor_error(self.page_dir, self.event, page_by_id, registry),
            held_comment_error(self.event, page_by_id, registry),
            version_response_comment_error(self.event, page_by_id, registry),
            visual_anchor_error(self.event, page_by_id, registry),
        ):
            if error:
                return event_rejection(self.event, error)
        if not recapture:
            return None
        html = revision_path(self.page_dir, self.event["revision"]).read_text(
            encoding="utf-8"
        )
        projection, parser, _ = page_projection(
            html, self.events, registry, self.event["revision"]
        )
        try:
            canonical = capture_anchor(
                html,
                registry,
                anchor.get("quote", ""),
                anchor.get("section"),
                retirement_outcomes(projection.actions, registry),
                rewritten_bodies(projection.actions),
                prefix=anchor.get("prefix") if "prefix" in anchor else None,
                suffix=anchor.get("suffix") if "suffix" in anchor else None,
                additions=generated_children(projection.desired, parser.ids),
            )
        except ValueError as error:
            return event_rejection(
                self.event,
                f"comment anchor is not in the current page reading: {error}",
            )
        for field in ("quote",):
            if field in anchor and anchor[field] != canonical.get(field):
                return event_rejection(
                    self.event,
                    f"comment anchor {field} does not match the current page reading",
                )
        # Store the file-side reading, not the client's abbreviated proof. Compact
        # clients may name only quote and section; capture adds the context needed to
        # keep that passage attached when the same words occur elsewhere later.
        self.event["anchor"] = canonical
        return None

    def parent_rejection(self) -> EventAnswer | None:
        if "parent" in self.event and self.event["parent"] not in {
            event["id"] for event in self.events if event["kind"] in MESSAGE_KINDS
        }:
            return event_rejection(
                self.event, f"unknown parent {self.event['parent']!r}"
            )
        return None

    def undo_rejection(self) -> EventAnswer | None:
        if self.event["kind"] == "undo" and (
            error := undo_error(
                self.event,
                self.events,
                active_enclosing(self.page_dir),
            )
        ):
            return event_rejection(self.event, error)
        return None

    def rejection(self) -> EventAnswer | None:
        """The first failing mutable-state gate, in append-door order."""
        for check in (
            self.revision_rejection,
            self.approval_rejection,
            self.action_rejection,
            self.request_rejection,
            self.reaction_rejection,
            self.anchored_comment_rejection,
            self.parent_rejection,
            self.undo_rejection,
        ):
            if rejection := check():
                return rejection
        return None


class EventEndpoint:
    """The browser's one write door for a served page.

    A generated HTTP handler class owns one endpoint, so concurrent request handlers
    share active attempt executions while separate page servers share nothing. The
    accepted-state reader stays request-local because it belongs to the transport's
    publication view, not to event validation or storage.
    """

    def __init__(self, page_dir: Path, capture_anchors: bool = False):
        self.page_dir = page_dir
        # Set by a transport whose comment anchors reach the door unresolved, so the
        # passage they name is captured against the page under the append lease.
        self.capture_anchors = capture_anchors
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
        # Every decision whose validity depends on the log stays under the append
        # lock through the write. In particular, two tabs cannot both validate an
        # undo against the same standing target and append after either lock is gone.
        with PageTransaction(self.page_dir) as page:
            # Acceptance outranks mutable state validation. A retry for an accepted
            # attempt asks for its state; it does not repeat the gesture.
            accepted, rejection = _accepted_retry(page, event)
            if rejection:
                return rejection
            if not accepted:
                events = page.events
                validation = _TransactionValidation(
                    self.page_dir, event, events, self.capture_anchors
                )
                if rejection := validation.rejection():
                    return rejection
                event["author"] = "page" if event["kind"] == "error" else "user"
                page.append_event(event)
        return 200, {"ok": True, "state": state()}
