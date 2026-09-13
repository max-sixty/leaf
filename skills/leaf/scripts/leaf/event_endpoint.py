"""Browser-event admission and transactional append."""

from collections.abc import Callable
from pathlib import Path

from .anchor_capture import capture_anchor
from .document_reading import read_document
from .event_contracts import (
    action_contract_error,
    datum_anchor_error,
    event_record_error,
    held_comment_error,
    version_response_comment_error,
    visual_anchor_error,
)
from .event_log import AttemptConflict
from .events import build_threads, undo_error
from .files import latest_revision, list_revisions, version_revisions
from .passages import active_enclosing
from .projection import (
    generated_children,
    page_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from .registry.contract import RegistryError
from .registry.reactions import reaction_tokens
from .registry.storage import load_registry
from .requests import request_contract_error
from .revision_artifact import read_artifact
from .schema import MESSAGE_KINDS
from .served_state.conversation import browser_conversation
from .service import PageTransaction
from .structure import parse_revision, revision_review_mode

EventAnswer = tuple[int, dict]
StateReader = Callable[[], dict]


def _event_registry(page_dir: Path, event: dict) -> dict | None:
    """The captured vocabulary of the document that produced an event."""
    revision = event.get("revision")
    revisions = set(list_revisions(page_dir))
    if type(revision) is not int or revision not in revisions:
        revision = latest_revision(page_dir)
    if revision is not None:
        return read_artifact(page_dir, revision).registry
    return load_registry(page_dir)


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
        self,
        page_dir: Path,
        event: dict,
        events: list,
        registry: dict,
        capture_anchors: bool = False,
    ):
        self.page_dir = page_dir
        self.event = event
        self.events = events
        self.registry = registry
        self.capture_anchors = capture_anchors

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
        document = parse_revision(self.page_dir, self.event["revision"])
        page = page_reading(
            document, self.events, self.registry, self.event["revision"]
        )
        threads = build_threads(self.events, page.within)
        document_state = read_document(page, threads)
        conversation, _reading = browser_conversation(
            self.events, self.registry, threads
        )
        unanswered = [
            *document_state.asks["unanswered"],
            *conversation["asks"]["unanswered"],
        ]
        if unanswered:
            identities = ", ".join(ask["id"] for ask in unanswered)
            return event_rejection(
                self.event,
                f"v{self.event['version']} still has unanswered Asks: {identities}",
            )
        return None

    def action_rejection(self) -> EventAnswer | None:
        if self.event["kind"] != "action":
            return None
        if error := action_contract_error(
            self.page_dir,
            self.event,
            self.events,
            self.registry,
        ):
            return event_rejection(self.event, error)
        return None

    def request_rejection(self) -> EventAnswer | None:
        if self.event["kind"] != "request":
            return None
        if error := request_contract_error(
            self.page_dir,
            self.event,
            self.events,
            self.registry,
        ):
            return event_rejection(self.event, error)
        return None

    def reaction_rejection(self) -> EventAnswer | None:
        if not self.event.get("token"):
            return None
        tokens = reaction_tokens(self.registry)
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
        page_by_id = parse_revision(self.page_dir, self.event["revision"]).by_id
        for error in (
            datum_anchor_error(self.page_dir, self.event, page_by_id, self.registry),
            held_comment_error(self.event, page_by_id, self.registry),
            version_response_comment_error(self.event, page_by_id, self.registry),
            visual_anchor_error(self.event, page_by_id, self.registry),
        ):
            if error:
                return event_rejection(self.event, error)
        if not recapture:
            return None
        document = parse_revision(self.page_dir, self.event["revision"])
        page = page_reading(
            document, self.events, self.registry, self.event["revision"]
        )
        try:
            canonical = capture_anchor(
                document,
                self.registry,
                anchor.get("quote", ""),
                anchor.get("section"),
                retirement_outcomes(page.projection.actions, self.registry),
                rewritten_bodies(page.projection.actions),
                prefix=anchor.get("prefix") if "prefix" in anchor else None,
                suffix=anchor.get("suffix") if "suffix" in anchor else None,
                additions=generated_children(
                    page.projection.desired, page.document.ids
                ),
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


def accept_event(
    page_dir: Path,
    event: dict,
    state: StateReader,
    *,
    capture_anchors: bool = False,
) -> EventAnswer:
    """Validate and append one browser record, then return its current state."""
    try:
        registry = _event_registry(page_dir, event)
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
    """Validate mutable page state and append as one log transaction.

    `accept_event` checks the payload's declared shape before the page transaction. A
    re-vendor can replace that declaration before this transaction is acquired, so an
    action's contract is deliberately read again inside the lease: this reading, not
    the admission reading, is the one allowed to append beside the page's current
    vocabulary.
    """
    # Every decision whose validity depends on the log stays under the append
    # lock through the write. In particular, two tabs cannot both validate an
    # undo against the same standing target and append after either lock is gone.
    with PageTransaction(page_dir) as page:
        # Acceptance outranks mutable state validation. A retry for an accepted
        # attempt asks for its state; it does not repeat the gesture.
        accepted, rejection = _accepted_retry(page, event)
        if rejection:
            return rejection
        if not accepted:
            events = page.events
            try:
                registry = _event_registry(page_dir, event)
            except RegistryError as error:
                return event_rejection(event, str(error))
            if registry is None:
                return event_rejection(event, "the page has no registry.json")
            validation = _TransactionValidation(
                page_dir, event, events, registry, capture_anchors
            )
            if rejection := validation.rejection():
                return rejection
            event["author"] = "page" if event["kind"] == "error" else "user"
            page.append_event(event, registry)
    return 200, {"ok": True, "state": state()}
