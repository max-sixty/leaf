"""Page claims, serialized transitions, and process-backed leases."""

import functools
import hashlib
import os
import secrets
from pathlib import Path

from leaf.event_log import (
    _append_event_unlocked,
    _matching_attempt,
    flocked,
    now_iso,
    read_cursor,
    read_events,
    require_cross_process_locking,
)
from leaf.events import work_claim_revision
from leaf.files import read_json, write_json
from leaf.host import (
    host_identity,
    message_identity,
    pid_alive,
    session_lifetime,
    state_home,
)

try:
    import fcntl
except ImportError:  # pragma: no cover - rejected before a lease is read or taken
    fcntl = None


def lock_is_held(path: Path) -> bool:
    """Whether an exclusive lease is held on this file.

    The kernel releases the lease on exit, crash, or reboot. A durable record
    can therefore outlive its writer without being mistaken for a live process.
    """
    require_cross_process_locking()
    try:
        with open(path, "r+b") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(probe, fcntl.LOCK_UN)
            return False
    except OSError:
        return False


def page_lock(page_dir: Path, purpose: str) -> Path:
    """A stable lock for one page, outside the page it guards.

    `page init` must reject a package input without writing into it, so
    locks that can meet init cannot live in the prospective page directory. The
    resolved path gives every process the same lock while the purpose keeps the
    contract transition independent from the page's current session claim.
    """
    locks = state_home() / "page-locks"
    locks.mkdir(exist_ok=True)
    key = hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()[:32]
    return locks / f"{key}.{purpose}.lock"


def transition_lock(page_dir: Path) -> Path:
    """Serialize service changes, re-vendoring, and contract-bearing writes."""
    return page_lock(page_dir, "transition")


def contract_writer(function):
    """Keep a CLI event's validation and append on one vendored contract."""

    @functools.wraps(function)
    def locked(page_dir: Path, *args, **kwargs):
        with flocked(transition_lock(page_dir)):
            return function(page_dir, *args, **kwargs)

    return locked


def claim_path(page_dir: Path) -> Path:
    """The one ownership record for a resolved page path."""
    return state_home() / "claims" / f"{page_key(page_dir)}.json"


def page_key(page_dir: Path) -> str:
    """A filesystem-safe identity for state held outside one page directory."""
    return hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()


def init_lock_path(page_dir: Path) -> Path:
    """The lease serializing creation before a page has its own transaction."""
    return state_home() / "init" / f"{page_key(page_dir)}.lock"


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

    def __enter__(self):
        self._lock = flocked(self.page_dir / "comments.jsonl")
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
        claim = {
            "page": str(self.page_dir),
            "id": identity["id"],
            "host": identity["host"],
            **lifetime,
            "agent": identity["agent"],
            "cwd": os.getcwd(),
            "ts": now_iso(),
            "released": None,
            # When this session's last turn ended. None until one has, and reset
            # by nothing: a claim taken again is a new record. See close_turn.
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

    @property
    def status(self) -> dict:
        return read_json(self.page_dir / "status.json") or {"state": "idle"}

    def set_status(
        self,
        state: str,
        detail: str,
        *,
        handoff: bool = False,
        work: dict | None = None,
    ) -> None:
        """Write the page claim and any typed local claim it renews.

        A local line is the same sentence read at a second seat: the page's one
        line says what the agent is doing, and a typed subject says so where the
        work lives. One command writes both because they are one claim — a
        delegate reporting its subject is also the agent checking in, which is
        what keeps `working` believed across a turn boundary the session itself
        cannot write across.

        Standing work carries across every other status write, so a handoff's
        "picking up 2 updates" does not silently drop what a helper is holding.
        A new claim replaces the old claim on its semantic subject; `idle`
        clears them all with the leaf.
        """
        status = {"state": state, "detail": detail, "ts": now_iso()}
        if handoff:
            status["handoff"] = True
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
        return read_events(self.page_dir)

    def matching_attempt(self, event: dict) -> dict | None:
        """An accepted retry, read under this transaction's log lease."""
        return _matching_attempt(self._log, event)

    def append_event(self, event: dict) -> dict:
        """Append under this transaction without re-entering its log lease."""
        return _append_event_unlocked(self._log, event)

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


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records()
        if claim_is_active(claim)
        and (session_id is None or claim["id"] == session_id)
        and (Path(claim["page"]) / "comments.jsonl").is_file()
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


def waiter_lease_path(page_dir: Path | None, session: dict | None) -> Path | None:
    """The one lease a wait holds for its watch set.

    A host wait covers every page its session owns, so its lease belongs to the
    session. Outside a host, a named page is the entire watch set and holds a
    page-local lease. An unnamed bare-shell wait has no watch set and no lease.
    """
    if session:
        return state_home() / "sessions" / f"{session['id']}.wait"
    return page_dir / "waiter.lock" if page_dir is not None else None


def take_waiter_lease(path: Path):
    """Take and return a wait lease, or None when another wait already holds it."""
    require_cross_process_locking()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = open(path, "a+b")  # noqa: SIM115 - returned and held for the wait's life
    try:
        fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        record.close()
        return None
    return record


def wait_is_live(page_dir: Path, session: dict | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session)
    return bool(lease_path and lock_is_held(lease_path))


def claim_update_sources(status: dict, events: list) -> list[dict]:
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
            source["revision"] = work_claim_revision(claim, events)
        sources.append(source)
    return sources
