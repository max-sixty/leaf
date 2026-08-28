"""Page and neighboring-leaf presence readings."""

import hashlib
import json
from pathlib import Path

from .event_log import read_cursor, read_events
from .files import latest_revision, list_revisions, read_json
from .host import state_home
from .leases import wait_is_live
from .server import running_server
from .service import (
    claim_is_active,
    claim_records,
    claim_update_sources,
    page_claim,
    unacknowledged,
)
from .structure import parse_revision


def other_leaves(page_dir: Path) -> list:
    """The machine's other live leaves, for the banner's panel: each page
    whose server is up, as a title, its handover URL, and the same presence
    facts the page ships about itself — so a row there and the banner above it
    are the one judgment reading the one shape.

    Candidates are the conventional pages/ home and every claim record, which
    is what finds a page served from a session's scratch directory. Released
    and dead claims stay useful here as provenance. Liveness is the held
    server.lock lease, the same answer `running_server` gives everything else,
    and the URL is the one in durable service state, key included. The title is the
    active revision's — the document that page's own root URL answers with —
    read the way `transcript` reads it.

    The whole scan runs on every /api/state; what it reads of each neighbour is
    kept per file, so a state read costs the scan and the presence reads rather than a
    parse of every live neighbour's page (`parse_version`)."""
    candidates = []
    pages = state_home() / "pages"
    if pages.is_dir():
        candidates += (d for d in pages.iterdir() if d.is_dir())
    candidates += (Path(claim["page"]) for claim in claim_records())
    others = []
    seen = {page_dir.resolve()}
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        # A neighbour's fault stays its own. This is the one read of state some
        # other page owns: a directory deleted mid-scan (stale pages are deleted
        # and made again) or a log a disk fault corrupted would otherwise 500
        # every open page's state read on the machine, blaming the page that asked.
        try:
            info = running_server(candidate)
            if not info:
                continue
            events = read_events(candidate)
            if not list_revisions(candidate):
                continue
            revision = latest_revision(candidate)
            parser = parse_revision(candidate, revision)
            present = presence(candidate, events)
        except Exception:  # noqa: BLE001, S112 - whatever shape its fault takes
            continue
        others.append(
            {
                "title": parser.title.strip() or candidate.name,
                "url": info["url"],
                **present,
            }
        )
    return sorted(others, key=lambda entry: entry["title"].lower())


def presence(page_dir: Path, events: list) -> dict:
    """What a seat showing this page says about it: the agent's claim, everything
    the directory holds that can answer for it, and where that agent is working.
    One gatherer for every such seat — `full_state` spreads it into the page's own
    state answer, and `other_leaves` attaches it to each entry — so the runtime's one
    claim-against-proof judgment reads the same fields whichever page it judges,
    and the tray's account of a neighbour is the account this page gives of
    itself."""
    # A file that isn't there stands in as its whole record, so every read below
    # indexes rather than asking twice whether the field arrived.
    stored_status = read_json(page_dir / "status.json") or {
        "state": "idle",
        "detail": "",
        "ts": None,
    }
    status = {key: value for key, value in stored_status.items() if key != "work"}
    claim = page_claim(page_dir)
    active = claim if claim_is_active(claim) else None
    # What the wait owner has acknowledged after the complete batch reached its
    # next durable consumer. An action past this seq has not reached that point,
    # which lets the runtime carry it forward onto versions written without it.
    cursor = read_cursor(page_dir)
    return {
        "status": status,
        "claims": claim_update_sources(stored_status, events),
        "listening": wait_is_live(page_dir, active),
        "cursor": cursor,
        # The reader's number, not the watcher's: their own messages the agent
        # hasn't taken in. Reports ride the same cursor but are the agent's debt,
        # so the banner never tells a reader that a worker's news is waiting on them.
        "pending": sum(
            1 for e in unacknowledged(events, cursor) if e["author"] == "user"
        ),
        "agent": claim.get("agent", "Claude") if claim else "Claude",
        # The claimant's host program, for behavior that keys on it — the display
        # name above is anyone's to choose, so nothing may dispatch on it.
        "host": claim.get("host") if claim else None,
        # None when nothing claimed the page — interact.py run outside an agent host.
        "session_alive": active is not None if claim else None,
        # Which session the turn-closed evidence belongs to. Thread updates carry
        # their posting session too, so a delegate is not declared abandoned merely
        # because the orchestrator's turn ended under it.
        "claim_session": claim.get("id") if claim else None,
        # When the claiming session's last turn ended, or None while none has.
        # A `working` claim older than this is one that no turn and no delegate
        # renewed across the boundary — the same judgment the runtime's grace
        # makes, available at the moment it becomes true instead of a quarter of
        # an hour after it. Read with .get like the rest of the claim's fields,
        # since a record written before this existed is still a valid claim.
        "turn_closed": claim.get("turn_closed") if claim else None,
        # When a browser last held the page open (the server bumps viewed.json,
        # throttled, while a tab's news stream stands), or None for a page nobody
        # has ever opened — which used to be indistinguishable from one the user
        # studied and left.
        "viewed": (read_json(page_dir / "viewed.json") or {"t": None})["t"],
        # Where the claimant is working (claim_page), for the tray's hover: what
        # tells one leaf from another is the work behind it, and neither the title
        # nor the page directory says which that is. It outlives the session that
        # wrote it, as every other fact in this record does — a page the tray
        # calls unheld came out of somewhere, and that is still where it came from.
        # None for a page nothing ever claimed, which is the honest nothing.
        "session_cwd": claim.get("cwd") if claim else None,
    }


def presence_fingerprint(listening: bool, session_alive, others: list) -> str:
    """The half of a reading that file stamps cannot supply, from the facts a state
    already carries: the lease, the claimant's life, and the neighbours as the tray
    shows them. A neighbour's `viewed` is left out, since it moves every half minute
    that tab stays open and changes nothing this page shows."""
    facts = (
        listening,
        session_alive,
        [{k: v for k, v in other.items() if k != "viewed"} for other in others],
    )
    return hashlib.sha256(
        json.dumps(facts, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


def presence_reading(page_dir: Path) -> str:
    """`presence_fingerprint` read fresh, for a stream between states. The three facts
    are read the way `presence` and `full_state` read them, so the stream and the
    state it prompts name the same reading."""
    claim = page_claim(page_dir)
    active = claim if claim_is_active(claim) else None
    return presence_fingerprint(
        wait_is_live(page_dir, active),
        active is not None if claim else None,
        other_leaves(page_dir),
    )
