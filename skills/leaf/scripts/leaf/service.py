"""Page claims, serialized transactions, status, and event admission."""

import os
import secrets
from pathlib import Path

from leaf.event_log import (
    _append_event_unlocked,
    _matching_attempt,
    _parse_events,
    flocked,
    now_iso,
    read_cursor,
)
from leaf.files import read_json, write_json
from leaf.host import (
    host_identity,
    message_identity,
    pid_alive,
    session_lifetime,
    state_home,
)
from leaf.locations import page_key, paths_same
from leaf.schema import EVENTS_FILE


def claim_path(page_dir: Path) -> Path:
    """The one ownership record for a resolved page path."""
    return state_home() / "claims" / f"{page_key(page_dir)}.json"


def page_claim(page_dir: Path) -> dict | None:
    """The page's last claim, including one released or whose lifetime ended."""
    return read_json(claim_path(page_dir))


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner: the job record a background
    job's claim points at, or the process every other claim's pid names
    (`session_lifetime`). The only reading of that rule: the hooks reach it
    through `uv` rather than keeping a copy, so a host that states its lifetime a
    new way joins here alone."""
    if not claim or claim["released"] is not None:
        return False
    if "job" in claim:
        return (Path(claim["job"]) / "state.json").is_file()
    return pid_alive(claim["pid"])


def claim_records() -> list:
    """Every atomic page claim record currently on this machine."""
    directory = state_home() / "claims"
    if not directory.is_dir():
        return []
    return [claim for path in directory.glob("*.json") if (claim := read_json(path))]


class PageTransaction:
    """One page transition serialized by its append-only log."""

    def __init__(self, page_dir: Path):
        self.page_dir = page_dir.resolve()
        self._lock = None
        self._log = None
        self._events = None

    def __enter__(self):
        self._events = None
        self._lock = flocked(self.page_dir / EVENTS_FILE)
        self._log = self._lock.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._lock.__exit__(exc_type, exc, traceback)

    @property
    def claim(self) -> dict | None:
        return page_claim(self.page_dir)

    @property
    def active_claim(self) -> dict | None:
        claim = self.claim
        return claim if claim_is_active(claim) else None

    def take_claim(self, identity: dict, lifetime: dict) -> tuple[dict | None, dict]:
        previous = self.claim
        path = claim_path(self.page_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        same_open_turn = bool(
            previous
            and claim_is_active(previous)
            and previous["released"] is None
            and previous["id"] == identity["id"]
            and previous.get("turn_closed") is None
        )
        claim = {
            "page": str(self.page_dir),
            "id": identity["id"],
            "host": identity["host"],
            **lifetime,
            "agent": identity["agent"],
            "cwd": os.getcwd(),
            "ts": now_iso(),
            "released": None,
            # Opaque identity of the currently open agent turn on this page.
            # Delivery transitions name it, so an unresolved pickup from an old
            # turn cannot become "being handled" merely because a later prompt
            # opened another turn in the same session.
            "turn": previous["turn"] if same_open_turn else secrets.token_hex(8),
            # When this session's last turn ended. None until one has, and
            # cleared again when a batch delivered to this session opens the
            # next turn. See close_turn and open_turn.
            "turn_closed": None,
        }
        write_json(path, claim)
        return previous, claim

    def restore_claim(self, expected: dict, previous: dict | None) -> None:
        """Roll back one failed claim without erasing a successor's."""
        if self.claim != expected:
            return
        path = claim_path(self.page_dir)
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            write_json(path, previous)

    def owned_by(self, identity: dict | None) -> bool:
        """Whether this transaction may act for the given waiter."""
        if identity is None:
            return self.active_claim is None
        claim = self.active_claim
        return bool(
            claim and (claim["host"], claim["id"]) == (identity["host"], identity["id"])
        )

    def release_claim(self) -> None:
        claim = self.claim
        if claim and claim["released"] is None:
            write_json(claim_path(self.page_dir), {**claim, "released": now_iso()})

    def close_turn(self, session_id: str) -> None:
        """Record that the turn which could have renewed this page's claim has ended.

        A `working` claim is written by a model's turn rather than by a process,
        and a turn can end at any token without running anything — so there is no
        close to write on the way out, and a claim nobody renewed used to be
        found only by a clock fifteen minutes later. The Stop hook is the harness
        observing that same moment exactly, which is what the hooks are for.

        It lands here with the rest of the claim's provenance and not in
        status.json, the line SessionEnd already draws: what the agent said it
        was doing stays the agent's to write, and whether anything is still
        behind those words stays the page's to judge from evidence.
        """
        claim = self.claim
        if claim and claim["released"] is None and claim["id"] == session_id:
            write_json(claim_path(self.page_dir), {**claim, "turn_closed": now_iso()})

    def open_turn(self, session_id: str) -> str | None:
        """Record that a turn of this session's is running again.

        `close_turn` is stamped by the Stop hook, and until this it was stamped
        by nothing else — so the page could see a turn end but never see the
        next one begin. That is not symmetric bookkeeping for its own sake: the
        canonical activity fold stops believing a declaration left behind by a
        closed turn, and an opened delivery belongs to the current turn only by
        exact turn identity. Without an opening, a session that came back could
        be presented as one that had walked away.

        Two things observe the beginning. A prompt is one: the hook that mirrors
        the Stop hook fires with the turn already running, whoever caused it —
        including the reader who did the thing the banner told them to and
        nudged in the terminal, leaving no batch for any delivery to carry. A
        delivery is the other, and whether it is belongs to the carrier that
        makes it: the direct watcher exits into model context, so its handoff is
        the turn; the Codex adapter hands a pointer to a durable queue an
        unloaded task leaves standing, so its handoff is not, and it declines
        this.

        Nothing else about the claim moves. What the agent said it was doing
        stays the agent's to write, and the fifteen-minute grace on that claim's
        own age still catches a turn that ends without a Stop to stamp it.
        """
        claim = self.claim
        if not claim or claim["released"] is not None or claim["id"] != session_id:
            return None
        if claim.get("turn_closed") is not None:
            claim = {
                **claim,
                "turn": secrets.token_hex(8),
                "turn_closed": None,
            }
            write_json(claim_path(self.page_dir), claim)
        return claim.get("turn")

    @property
    def status(self) -> dict:
        return read_json(self.page_dir / "status.json") or {"state": "idle"}

    def set_status(
        self,
        state: str,
        detail: str,
        *,
        work: dict | None = None,
    ) -> None:
        """Write the page claim and any typed local claim it renews.

        A local line is the same sentence read at a second seat: the page's one
        line says what the agent is doing, and a typed subject says so where the
        work lives. One command writes both because they are one claim — a
        delegate reporting its subject is also the agent checking in, which is
        what keeps `working` believed across a turn boundary the session itself
        cannot write across.

        Standing work carries across every other status write, so a page-wide
        status update does not silently drop what a helper is holding.
        A new claim replaces the old claim on its semantic subject; `idle`
        clears them all with the leaf.
        """
        status = {
            "state": state,
            "detail": detail,
            "ts": now_iso(),
            # Order the agent's declaration against delivery transitions without
            # comparing wall-clock timestamps that are only precise to a second.
            "after": self.events[-1]["seq"] if self.events else 0,
        }
        claims = [] if state == "idle" else list(self.status.get("work", []))
        if work:
            identity = message_identity()
            claims = [held for held in claims if held["subject"] != work["subject"]]
            claims.append(
                {
                    "id": secrets.token_hex(4),
                    **work,
                    "detail": detail,
                    "ts": status["ts"],
                    "agent": identity.get("agent")
                    or (self.claim or {}).get("agent", "Claude"),
                    "session": identity.get("session") or (self.claim or {}).get("id"),
                }
            )
        if claims:
            status["work"] = claims
        write_json(self.page_dir / "status.json", status)

    @property
    def events(self) -> list:
        if self._events is None:
            self._log.seek(0)
            self._events = _parse_events(self._log.read())
        return self._events

    def matching_attempt(self, event: dict) -> dict | None:
        """An accepted retry, read under this transaction's log lease."""
        return _matching_attempt(self.events, event)

    def append_event(self, event: dict) -> dict:
        """Append under this transaction without re-entering its log lease."""
        if event["kind"] in {"action", "report", "request"}:
            if accepted := self.matching_attempt(event):
                return accepted
            from leaf.event_meaning import admit_widget_event
            from leaf.registry.storage import require_registry

            event = admit_widget_event(
                self.page_dir, event, self.events, require_registry(self.page_dir)
            )
        try:
            accepted, appended = _append_event_unlocked(self._log, event, self.events)
        except Exception:
            self._events = None
            raise
        if appended:
            self._events = None
        return accepted

    @property
    def cursor(self) -> int:
        return read_cursor(self.page_dir)

    def watch_state(self, identity: dict | None) -> str:
        if not self.owned_by(identity):
            return "lost"
        return "ended" if self.status["state"] == "idle" else "watching"


def take_page_claim(page_dir: Path) -> tuple[dict | None, dict] | None:
    """Make the host session the page's watcher, if a host supplied one.

    `server start` and named `leaf wait` claim; authoring commands do not. A
    bare-shell serve makes no claim and therefore starts as standing.
    """
    identity = host_identity()
    if not identity:
        return None
    lifetime = session_lifetime(identity)
    with PageTransaction(page_dir) as page:
        return page.take_claim(identity, lifetime)


def claim_page(page_dir: Path) -> bool:
    return take_page_claim(page_dir) is not None


def restore_page_claim(
    page_dir: Path, transition: tuple[dict | None, dict] | None
) -> None:
    """Undo a failed startup's claim, provided no successor replaced it."""
    if transition is None:
        return
    previous, expected = transition
    with PageTransaction(page_dir) as page:
        page.restore_claim(expected, previous)


def open_session_turn(
    session_id: str, delivered: PageTransaction | None = None
) -> None:
    """Clear the turn-ended stamp on every page one session holds.

    A turn belongs to the session, not to the page whose batch opened it. The
    Stop hook stamps the ending across `owned_pages`, so an opening that clears
    only one page leaves every sibling claim stamped through a turn that is
    demonstrably running: the reader comments on one leaf, and two minutes later
    the next leaf tells its own reader the agent left when its turn ended and to
    nudge it in the terminal.

    A delivery names the page its batch came from, which is already open under
    the transaction the batch left under — clearing it there is what keeps it
    from being read between the two. A prompt names none: nothing was delivered,
    so every page the session holds is a sibling. Each sibling takes its own
    transaction, the way the Stop hook takes them, and a sibling the turn never
    touches still falls to the fifteen-minute grace on its own claim age.
    """
    if delivered is not None:
        delivered.open_turn(session_id)
    for page_dir in owned_pages(session_id):
        if delivered is not None and paths_same(page_dir, delivered.page_dir):
            continue
        try:
            with PageTransaction(page_dir) as page:
                page.open_turn(session_id)
        except FileNotFoundError:
            continue


def close_session_turn(session_id: str) -> bool:
    """Stamp the end of a turn across every page one session still holds."""
    pages = owned_pages(session_id)
    for page_dir in pages:
        try:
            with PageTransaction(page_dir) as page:
                page.close_turn(session_id)
        except FileNotFoundError:
            continue
    return bool(pages)


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records()
        if claim_is_active(claim)
        and (session_id is None or claim["id"] == session_id)
        and (Path(claim["page"]) / EVENTS_FILE).is_file()
    }
    return sorted(pages, key=str)


def unacknowledged(events: list, cursor: int) -> list:
    """The events past the acknowledgement cursor that the page's watcher owes a
    reading: the user's own, and workers' reports — a report moves the page the
    way a user's action does, and the watcher is the one who can absorb it into
    a version. One cursor and one predicate for the whole batch, so `leaf
    wait`'s output, the Stop hook's count, and the idle gate cannot disagree
    about what is still owed. The reader's banner counts only the user half
    (full_state's `pending`): a report is news the agent owes the page, not
    something the reader owes an answer. A session that reports to a page it
    also watches reads its own report back once — rare enough (workers report,
    the watcher publishes) that a session-keyed carve-out would cost a second,
    parameterized predicate for no failure anyone has hit."""
    return [
        e
        for e in events
        if e["seq"] > cursor
        # The user's own, a worker's report, and the page reporting itself
        # broken — the last is the agent's debt exactly as a report is.
        and (
            e["author"] == "user"
            or e["kind"] in ("report", "error")
            or (e["author"] == "page" and e["kind"] == "action")
        )
    ]


def claim_update_sources(status: dict) -> list[dict]:
    """The status store's work claims at their public boundary.

    `status.json` remains the small replace-in-place store its transient claims
    need. The browser and `page state` receive typed source envelopes instead, so
    every downstream consumer reads the same target and lifecycle vocabulary.
    """
    sources = []
    for claim in status.get("work", []):
        target = claim["subject"]
        source = {
            "id": claim.get("id")
            or f"claim:{target['kind']}:{target['id']}:{claim['after']}",
            "target": target,
            "source": "claim",
            "action": "working",
            "detail": {"text": claim["detail"]},
            "text": claim["detail"],
            "ts": claim["ts"],
            "log_floor": claim["after"],
            "agent": claim.get("agent"),
            "session": claim.get("session"),
        }
        if target["kind"] == "widget":
            source["revision"] = claim["revision"]
        sources.append(source)
    return sources
