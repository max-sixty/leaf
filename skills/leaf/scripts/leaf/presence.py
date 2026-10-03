"""Page and neighboring-leaf presence readings."""

import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from .activity import Turn, current_turn
from .event_log import read_cursor
from .files import (
    entry_stamps,
    file_stamp,
    read_json,
)
from .host import claim_harness
from .leases import wait_is_live, waiter_lease_path
from .machine import state_home
from .page_memory import memo
from .schema import (
    INTERACTIONS_FILE,
    UNNAMED_AGENT,
    USER_VIEWS_FILE,
    USER_VIEWS_LOCK,
    VIEWED_FILE,
    WAITER_LOCK,
)
from .server import running_server
from .service import (
    claim_is_active,
    claim_path,
    claim_records,
    claim_update_sources,
    page_claim,
    read_status,
    unacknowledged,
)
from .state import now_iso

# Presence is deliberately a short-lived reading: process and lock leases can change
# without touching a page file. Readers share one observation for two seconds, while
# a changed page file invalidates it immediately.
PRESENCE_CACHE_S = 2.0
# (state-home stamp, resolved candidate pages): the machine's, so one slot.
_candidates = ((), ())
_candidates_lock = threading.Lock()


class _Presence:
    """What a page keeps of its presence between readings.

    The lock is held through a whole observation, so concurrent freshness readers on the
    page share one reading rather than racing into one parse each."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        # (page-file stamp, expiry, the token `presence_reading` gave)
        self.token: tuple | None = None


def _page_stamp(page_dir: Path, claim: dict | None = None) -> tuple:
    """The mutable files whose changes can alter a page presence reading.

    `viewed.json` counts here, where the page's own reading leaves it out: whether a
    tab is looking is part of what presence reports."""
    entries = tuple(
        entry_stamps(page_dir, {INTERACTIONS_FILE, USER_VIEWS_FILE, USER_VIEWS_LOCK})
    )
    claim_stamp = file_stamp(claim_path(page_dir))
    if claim and claim.get("id"):
        # A host wait lease is outside the page, and its lock state has no file
        # stamp of its own. Its boolean is checked below on every cache refresh;
        # including the file here still invalidates a page when the lease is first
        # created or removed.
        lease_stamp = file_stamp(waiter_lease_path(None, claim["id"]))
    else:
        lease_stamp = file_stamp(page_dir / WAITER_LOCK)
    return entries + (("$claim", claim_stamp), ("$wait", lease_stamp))


def neighbor_candidates() -> tuple:
    """Every page on this machine that could be serving: the conventional pages/
    home and every claim record, which is what finds a page served from a
    session's scratch directory. Released and dead claims stay useful here as
    provenance.

    The set moves when an entry in one of those two directories does, or when a
    page it holds is deleted, which for a claimed scratch page moves neither. So
    it is read again only then: keyed on the two stamps, the way `leaf wait` keys
    its ownership set on the claims directory's, and on each held page still
    being there, so the read drops a deleted page from the candidates after its
    deletion. Whether each page is serving is the caller's question, asked fresh
    every time."""
    global _candidates
    home = state_home()
    claims, pages = home / "claims", home / "pages"
    stamp = (home, file_stamp(claims), file_stamp(pages))
    with _candidates_lock:
        if _candidates[0] == stamp and all(page.is_dir() for page in _candidates[1]):
            return _candidates[1]
        found = [d for d in pages.iterdir() if d.is_dir()] if pages.is_dir() else []
        found += (Path(claim["page"]) for claim in claim_records())
        resolved = dict.fromkeys(
            page for page in (path.resolve() for path in found) if page.is_dir()
        )
        # Keyed on the stamp taken before the read, so an entry written during it
        # moves the stamp and the next call reads again.
        _candidates = (stamp, tuple(resolved))
        return _candidates[1]


def other_leaves(page_dir: Path) -> list:
    """Live neighboring pages, from their own compact canonical publications.

    Each candidate costs its server lease/service and one disposable row read.
    Never open another page's log, document, or projection. A row belongs to
    the server incarnation that computed it; absent or older rows stay absent.
    """
    from .server_rows import read_row

    others = []
    own = page_dir.resolve()
    for candidate in neighbor_candidates():
        if candidate == own:
            continue
        # A neighbour's fault stays its own. This is the one read of state some
        # other page owns: a directory deleted mid-scan (stale pages are deleted
        # and made again) or a file a disk fault corrupted would otherwise 500
        # every open page's state read on the machine, blaming the page that asked.
        try:
            info = running_server(candidate)
            if info is None:
                continue
            row = read_row(candidate, info)
            if row is not None:
                others.append({**row, "url": info["url"]})
        except Exception:  # noqa: BLE001, S112 - whatever shape its fault takes
            continue
    return sorted(others, key=lambda entry: entry["title"].lower())


def live_facts(page_dir: Path, claim: dict | None) -> dict:
    """The presence facts no page file records, read from processes and the host
    at this moment: whether the claimant's wait lease is held, whether its
    lifetime stands, and what its host says of its turn (`Harness.live_turn`).
    File stamps cannot say when these move, so every cache of a presence reading
    keys on them, and the freshness token carries them."""
    active = claim if claim_is_active(claim) else None
    return {
        "listening": wait_is_live(page_dir, active["id"] if active else None),
        # None when nothing claimed the page — leaf run outside an agent host.
        "session_alive": active is not None if claim else None,
        "live_turn": claim_harness(active).live_turn() if active else None,
    }


def presence_with_activity(
    page_dir: Path,
    events: list,
) -> tuple[dict, dict | None]:
    """Gather public presence and server-only live activity as separate values.

    The public reading says what a seat showing this page may know: the agent's
    claim, everything the directory holds that can answer for it, and where that
    agent is working. Keeping private activity records out of that dictionary makes
    them unavailable to every browser-facing consumer by construction.

    `full_state` spreads it into the page's own state answer, so the runtime's one
    claim-against-proof judgment reads these fields. The server's row publication
    carries only the compact presentation fields derived from these facts."""
    stored_status = read_status(page_dir)
    status = {
        key: value
        for key, value in stored_status.items()
        if key not in {"work", "stream"}
    }
    status.setdefault("after", 0)
    claim = page_claim(page_dir)
    active = claim if claim_is_active(claim) else None
    # What the wait owner has acknowledged after the complete batch reached its
    # next durable consumer. An action past this seq has not reached that point,
    # which lets the runtime carry it forward onto versions written without it.
    cursor = read_cursor(page_dir)
    reading = {
        "status": status,
        "claims": claim_update_sources(stored_status),
        **live_facts(page_dir, claim),
        "cursor": cursor,
        # The user's number, not the watcher's: their own messages the agent
        # hasn't taken in. Reports ride the same cursor but are the agent's debt,
        # so the banner never tells a user that a worker's news is waiting on them.
        "pending": sum(
            1 for e in unacknowledged(events, cursor) if e["author"] == "user"
        ),
        # The claimant's chosen display name. Harness-specific facts stay out of
        # this reading: it is what a browser seat may know, and the browser has
        # never had a use for which program is running the agent.
        "agent": claim["agent"] if claim else UNNAMED_AGENT,
        # Which session the turn-closed evidence belongs to. Thread updates carry
        # their posting session too, so a claim another session wrote — the page
        # task's, while a Codex watcher task holds the page — is not declared
        # abandoned because the claimant's turn ended under it.
        "claim_session": claim.get("id") if claim else None,
        # Opaque identity of the claiming session's current turn on this page.
        # An opened delivery names this value; equality, rather than timestamps,
        # is what says that exact user move is in the turn running now.
        "claim_turn": claim.get("turn") if claim else None,
        # When the claiming session's last turn ended, or None while none has.
        # A `working` claim older than this is one that no later turn renewed
        # across the boundary — the same judgment the runtime's grace
        # makes, available at the moment it becomes true instead of a quarter of
        # an hour after it. Read with .get like the rest of the claim's fields,
        # since a record written before this existed is still a valid claim.
        "turn_closed": claim.get("turn_closed") if claim else None,
        # When that turn opened, and whether an open turn of this session's takes
        # new input before it ends: its hooks carry input, so the Stop hook hands
        # over what arrives. The banner reads such a turn as listening between two
        # waits; a session whose carrier is a process it runs has no such turn.
        "turn_opened": claim.get("turn_opened") if claim else None,
        "turn_takes_input": bool(active and claim_harness(active).hooks_carry()),
        # When a browser last had the page visible (the server bumps viewed.json,
        # throttled, while a visible tab asks for news), or None for a page
        # nobody has ever viewed — which used to be indistinguishable from one the
        # user studied and left. Hidden tabs stop their freshness reads, so this records
        # user attention rather than tab lifetime.
        "viewed": (read_json(page_dir / VIEWED_FILE) or {"t": None})["t"],
        # Where the claimant is working (claim_page), for the drawer's hover: what
        # tells one leaf from another is the work behind it, and neither the title
        # nor the page directory says which that is. It outlives the session that
        # wrote it, as every other fact in this record does — a page the drawer
        # calls unheld came out of somewhere, and that is still where it came from.
        # None for a page nothing ever claimed, which is the honest nothing.
        "session_cwd": claim.get("cwd") if claim else None,
    }
    return reading, stored_status.get("stream")


def claimant_reading(page_dir: Path, events: list) -> tuple[dict, Turn]:
    """The page's presence and its claimant's turn, read the way the activity fold
    reads them (`activity.current_turn`), for a writer that asks outside a state
    read."""
    present, stream = presence_with_activity(page_dir, events)
    turn, _ = current_turn(
        present, (stream or {}).get("activity"), datetime.fromisoformat(now_iso())
    )
    return present, turn


def presence(page_dir: Path, events: list) -> dict:
    """Return the public presence projection without private activity evidence."""
    reading, _ = presence_with_activity(page_dir, events)
    return reading


def presence_fingerprint(present: dict, others: list) -> str:
    """The half of a reading that file stamps cannot supply, from the facts a state
    already carries: its `live_facts`, and the neighbours as the drawer shows them."""
    facts = (
        [present[key] for key in ("listening", "session_alive", "live_turn")],
        others,
    )
    return hashlib.sha256(
        json.dumps(facts, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


def presence_reading(page_dir: Path) -> str:
    """The presence token shared by readers for one bounded freshness interval.

    Page-file stamps invalidate it immediately; process and lock leases are refreshed
    when the interval expires. The three facts are read the way `presence` and
    `full_state` read them, so a freshness answer and the state it prompts name the same
    reading once the bounded cache interval has elapsed.
    """
    claim = page_claim(page_dir)
    stamp = _page_stamp(page_dir, claim)
    now = time.monotonic()
    kept = memo(page_dir, _Presence)
    with kept.lock:
        held = kept.token
        if held and held[0] == stamp and now < held[1]:
            return held[2]

        # Keep the lock while observing the neighbours. Concurrent freshness reads
        # then share one complete reading instead of racing into one each; the
        # lock and pid checks remain part of this fresh observation.
        reading = presence_fingerprint(
            live_facts(page_dir, claim), other_leaves(page_dir)
        )
        kept.token = (stamp, now + PRESENCE_CACHE_S, reading)
        return reading
