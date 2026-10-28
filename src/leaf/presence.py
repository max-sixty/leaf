"""Page and neighboring-leaf presence readings, and the one write that follows
from them: the message to a claimant whose input nothing will carry
(`nudge_unwatched`, `nudge_interrupted`)."""

import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from .activity import (
    Turn,
    current_turn,
    declaration,
    declared_at,
    nudge_due,
    undeclared,
)
from .files import file_stamp
from .harness import claim_harness
from .leases import hooks_ran_at, lock_is_held, wait_is_live, waiter_lease_path
from .page_memory import memo
from .schema import SERVER_LOCK, UNNAMED_AGENT
from .server import running_server
from .service import (
    PageTransaction,
    acknowledged,
    claim_is_active,
    claim_records,
    page_claim,
    read_stream,
    unacknowledged,
)
from .state import now_iso, state_home

# Presence is deliberately a short-lived reading: process and lock leases can change
# without touching a page file. Readers share one observation for two seconds, while
# a changed page file invalidates it immediately.
PRESENCE_CACHE_S = 2.0
# (row-directory stamp, producer publications): the machine's, so one slot.
_candidates = ((), ())
_candidates_lock = threading.Lock()
_row_files = {}
_row_home = None


class _Neighbors:
    """One page's other-row observation; its own publication cannot invalidate it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.token = None


def neighbor_reading(page_dir: Path) -> list:
    """The page's one reading of its neighbours (`other_leaves`), which its state
    answer and its news fingerprint both take, so the two never disagree.

    Local page writes do not invalidate it. Producer writes invalidate it
    immediately; kernel lease changes have the same bounded two-second observation
    interval as the page's other live facts.
    """
    candidates = neighbor_candidates()
    own = page_dir.resolve()
    stamp = tuple((path, record) for path, record in candidates if path != own)
    now = time.monotonic()
    kept = memo(page_dir, _Neighbors)
    with kept.lock:
        if kept.token is None or kept.token[0] != stamp or now >= kept.token[1]:
            kept.token = (stamp, now + PRESENCE_CACHE_S, other_leaves(page_dir))
        return kept.token[2]


class _Presence:
    """What a page keeps of its presence between readings.

    The lock is held through a whole observation, so concurrent freshness readers on the
    page share one reading rather than racing into one parse each."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        # (page reading, wait lease and neighbours; expiry; the token given)
        self.token: tuple | None = None


def neighbor_candidates() -> tuple:
    """Serving publishers discover themselves through their disposable rows.

    Claims and directories holding idle pages are not a directory of servers.
    Every server already publishes a row, including pages outside pages/, so its
    publication is the one discovery surface. Atomic replacements move rows/'s
    stamp; readers hold the parsed envelopes until a producer changes them.
    Server leases are still checked on every observation, independent of files.
    """
    global _candidates, _row_home, _row_files
    home = state_home()
    rows = home / "rows"
    stamp = (home, file_stamp(rows))
    with _candidates_lock:
        if _row_home != rows:
            _row_files = {}
            _row_home = rows
        if _candidates[0] == stamp:
            return _candidates[1]
        # Atomic producer publications move the directory stamp. Scan only when
        # it changes; the parsed rows retain their per-file stamps between scans.
        from .server_rows import ROW

        current = set(rows.glob("*.json")) if rows.is_dir() else set()
        for path in _row_files.keys() - current:
            del _row_files[path]
        for path in current:
            key = file_stamp(path)
            if key is None:
                _row_files.pop(path, None)
            elif path not in _row_files or _row_files[path][0] != key:
                _row_files[path] = (key, *_row_reading(path, ROW))
        found = tuple(
            (page, record) for _key, page, record in _row_files.values() if page
        )
        _candidates = (stamp, found)
        return _candidates[1]


def _row_reading(path: Path, kind) -> tuple:
    """The page and current-format row, or neither when no readable row remains."""
    try:
        record = kind.read(path)
    except (OSError, ValueError):
        return None, None
    return (Path(record["page"]), record) if record else (None, None)


def other_leaves(page_dir: Path) -> list:
    """Live neighboring pages, from their own compact canonical publications.

    A closed page is not one of them. Its server stays up so the page stays
    readable, a persistent one for good, so nothing else would ever drop its row, and
    a count the user glances at to find who needs them would become a tally of
    everything that has run here. This page's own row is never in the list, so a
    user looking at a closed page still sees it.

    Each candidate costs its server lease/service and one disposable row read.
    Never open another page's log, document, or projection. A row belongs to
    the server incarnation that computed it; absent or older rows stay absent.
    Nothing else removes a row, so this scan deletes one whose server lease no
    process holds. A server that takes the lease again republishes its missing
    row within one look (`RowPublisher.refresh`).

    Each entry names its page by `page_key`, the identity the page's own state-home
    records already use, and links it by `url`. The two are separate because a page
    outlives its server: a restart may serve the same page at a new port, which
    changes where the row leads and not which page it is.
    """
    own = page_dir.resolve()
    return [entry for candidate, entry in live_leaves() if candidate != own]


def live_leaves(among: set[Path] | None = None) -> list:
    """Each live page that is not closed, by its directory, with its row entry, in
    title order (`other_leaves` says what each costs and holds); only those `among`
    resolved page directories, where given, whose leases alone it then checks."""
    from .server_rows import read_row, row_path

    leaves = []
    for candidate, record in neighbor_candidates():
        if among is not None and candidate not in among:
            continue
        # A neighbour's fault stays its own. This is the one read of state some
        # other page owns: a directory deleted mid-scan (stale pages are deleted
        # and made again) or a file a disk fault corrupted would otherwise 500
        # every open page's state read on the machine, blaming the page that asked.
        try:
            info = running_server(candidate)
            if info is None:
                if not lock_is_held(candidate / SERVER_LOCK):
                    row_path(candidate).unlink(missing_ok=True)
                continue
            if record is None:
                continue
            row = read_row(candidate, info, record=record)
            if row is not None and row["activity"]["kind"] != "closed":
                leaves.append(
                    (
                        candidate,
                        {
                            **row,
                            "page_key": record["page_key"],
                            "url": info["url"],
                        },
                    )
                )
        except Exception:  # noqa: BLE001, S112 - whatever shape its fault takes
            continue
    return sorted(leaves, key=lambda leaf: leaf[1]["title"].lower())


def page_list() -> list[dict]:
    """The machine's pages and the sessions holding them, in title order, for `leaf
    page list`: each live page (`live_leaves`), and each page a claim names
    (`claim_records`), whether or not it is served, since which session holds a
    page matters most when its server is down. A page nothing claimed is found
    only while it serves.

    The counts a row carries (`on_user`, `threads`) are a serving page's; a page
    with no live row, stopped or closed, has none here, and `page state` reads it
    whole. Its title is its latest revision's."""
    from .revision_artifact import latest_title

    rows = {page.resolve(): row for page, row in live_leaves()}
    claims = {Path(claim["page"]).resolve(): claim for claim in claim_records()}
    listed = []
    for page in rows.keys() | claims.keys():
        row, claim = rows.get(page), claims.get(page)
        if row is None:
            server = running_server(page)
            row = {
                "title": latest_title(page)[1] or page.name,
                "url": server["url"] if server else None,
                "on_user": None,
                "threads": None,
            }
        listed.append(
            {
                "page": str(page),
                "title": row["title"],
                "url": row["url"],
                "on_user": row["on_user"],
                "threads": row["threads"],
                "harness": claim["harness"] if claim else None,
                "claim_session": claim["id"] if claim else None,
                "session_name": (
                    claim_harness(claim).session_name() if claim else None
                ),
                "session_cwd": claim["cwd"] if claim else None,
                "session_alive": claim_is_active(claim) if claim else None,
            }
        )
    return sorted(listed, key=lambda entry: entry["title"].lower())


def live_facts(page_dir: Path, claim: dict | None, *, process: bool = True) -> dict:
    """The presence facts no page file records, read from processes and the harness
    at this moment: whether the claimant's wait lease is held, whether its
    lifetime stands, what its harness says of its turn (`Harness.live_turn`), and
    what the harness calls the session (`Harness.session_name`), which a harness
    may still know after the session ends. File stamps cannot say when these move,
    so every cache of a presence reading keys on them, and the freshness token
    carries them."""
    active = claim if claim_is_active(claim) else None
    return {
        "listening": process
        and wait_is_live(page_dir, active["id"] if active else None),
        # None when nothing claimed the page — leaf run outside an agent harness.
        "session_alive": active is not None if claim else None,
        "live_turn": claim_harness(active).live_turn() if active else None,
        "session_name": claim_harness(claim).session_name() if claim else None,
        # Whether a nudge would start the claimant's next turn (`Harness.input_wakes`).
        "input_wakes": bool(active and claim_harness(active).input_wakes()),
    }


# The keys `live_facts` returns.
LIVE_FACTS = ("listening", "session_alive", "live_turn", "session_name", "input_wakes")


def page_agent(claim: dict | None, events: list) -> str:
    """The name the page calls its agent: the claimant's, who reads what the user
    writes; on a page no session holds now, the voice that last wrote on it, whose
    words the page shows; and `UNNAMED_AGENT` where neither names one. One name for
    the agent's side, so a page whose session ended still calls its agent what its
    messages do. A hosted copy's served state names its publication's agent instead
    (`served_state.page.read_served_page`)."""
    if claim:
        return claim["agent"]
    return next(
        (
            event["agent"]
            for event in reversed(events)
            if event["author"] == "agent" and event.get("agent")
        ),
        UNNAMED_AGENT,
    )


def presence_with_activity(
    page_dir: Path,
    events: list,
    *,
    process: bool = True,
) -> tuple[dict, dict | None]:
    """Gather public presence and server-only live activity as separate values.

    The public reading says what a seat showing this page may know: the agent's
    claim, everything the directory holds that can answer for it, and where that
    agent is working. Keeping private activity records out of that dictionary makes
    them unavailable to every browser-facing consumer by construction.

    `full_state` spreads it into the page's own state answer, so the runtime's one
    claim-against-proof judgment reads these fields. The server's row publication
    carries only the compact presentation fields derived from these facts. A captured
    host publication without a process keeps durable acknowledgement and pending
    input, while omitting claimant, watcher, turn and live activity facts, and the
    declaration its log holds: whoever answers a hosted copy is the host's agent,
    which has declared nothing, and which its served state names
    (`served_state.page.read_served_page`)."""
    status = declaration(events) if process else undeclared()
    claim = page_claim(page_dir) if process else None
    active = claim if claim_is_active(claim) else None
    # What the wait owner has acknowledged after the complete batch reached its
    # next durable consumer. An action past this seq has not reached that point,
    # which lets the runtime carry it forward onto versions written without it.
    cursor = acknowledged(events)
    reading = {
        "status": status,
        **live_facts(page_dir, claim, process=process),
        "cursor": cursor,
        # The user's number, not the watcher's: their own messages the agent
        # hasn't taken in. Reports ride the same cursor but are the agent's debt,
        # so the panel never tells a user that a worker's news is waiting on them.
        "pending": sum(
            1 for e in unacknowledged(events, cursor) if e["author"] == "user"
        ),
        # The page's agent, by the name every label naming the agent's side reads
        # (`page_agent`). Harness-specific facts stay out of this reading: it is what
        # a browser seat may know, and the browser has never had a use for which
        # program is running the agent.
        "agent": page_agent(claim, events),
        # Which session the turn-closed evidence belongs to. Thread updates carry
        # their posting session too, so a claim another session wrote — the page
        # task's, while a Codex watcher task holds the page — is not declared
        # abandoned because the claimant's turn ended under it.
        "claim_session": claim["id"] if claim else None,
        # Opaque identity of the claiming session's current turn on this page.
        # An opened delivery names this value; equality, rather than timestamps,
        # is what says that exact update is in the turn running now.
        "claim_turn": claim["turn"] if claim else None,
        # When the claiming session's current turn closed, or None while it is open.
        # A `working` claim older than this is one that no later turn renewed
        # across the boundary — the same judgment the runtime's grace
        # makes, available at the moment it becomes true instead of a quarter of
        # an hour after it.
        "turn_closed": claim["turn_closed"] if claim else None,
        # When that turn opened, and whether an open turn of this session's takes
        # new input before it ends (`Harness.turn_takes_input`).
        "turn_opened": claim["turn_opened"] if claim else None,
        # When the claimant's harness last ran a Leaf hook for the session, which an
        # open turn's tool steps keep moving (`activity.claimant_turn`). Not a live
        # fact the freshness token carries: it changes no reading until the turn's
        # renewal grace would lapse, and the activity's next transition asks again
        # then.
        "turn_seen": hooks_ran_at(active["id"]) if active else None,
        "turn_takes_input": bool(active and claim_harness(active).turn_takes_input()),
        # Where the claimant is working (claim_page), for All pages' hover: what
        # tells one leaf from another is the work behind it, and neither the title
        # nor the page directory says which that is. It outlives the session that
        # wrote it, as every other fact in this record does — a page All pages
        # calls unheld came out of somewhere, and that is still where it came from.
        # None for a page nothing ever claimed, which is the honest nothing.
        "session_cwd": claim.get("cwd") if claim else None,
    }
    return reading, read_stream(page_dir) if process else None


def claimant_reading(page_dir: Path, events: list) -> tuple[dict, Turn]:
    """The page's presence and its claimant's turn, read the way the activity fold
    reads them (`activity.current_turn`), for a writer that asks outside a state
    read."""
    present, stream = presence_with_activity(page_dir, events)
    turn, _ = current_turn(
        present,
        declared_at(present, events),
        (stream or {}).get("activity"),
        datetime.fromisoformat(now_iso()),
    )
    return present, turn


def presence(page_dir: Path, events: list) -> dict:
    """Return the public presence projection without private activity evidence."""
    reading, _ = presence_with_activity(page_dir, events)
    return reading


def presence_fingerprint(present: dict, others: list) -> str:
    """The half of a reading that file stamps cannot supply, from the facts a state
    already carries: its `live_facts`, and the neighbours as All pages shows them."""
    facts = ([present[key] for key in LIVE_FACTS], others)
    return hashlib.sha256(
        json.dumps(facts, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


def presence_reading(page_dir: Path, files: str) -> str:
    """The presence token shared by readers for one bounded freshness interval.

    It keys on `files`, the page's own reading (`served_state.reading`), which
    names every page input, and on the claimant's wait lease, the one input of
    presence outside them. A move in either invalidates it immediately; process
    and lock leases are refreshed when the interval expires. The three facts are
    read the way `presence` and `full_state` read them, so a freshness answer and
    the state it prompts name the same reading once the bounded cache interval has
    elapsed.
    """
    claim = page_claim(page_dir)
    # A harness wait lease lives outside the page, and its lock state has no file
    # stamp of its own: `live_facts` checks it on every refresh, while its stamp
    # here invalidates the token when the lease is first created or removed. An
    # unclaimed page's lease is in the page directory, so `files` covers it.
    lease = file_stamp(waiter_lease_path(None, claim["id"])) if claim else None
    neighbors = neighbor_reading(page_dir)
    stamp = (files, lease, neighbors)
    now = time.monotonic()
    kept = memo(page_dir, _Presence)
    with kept.lock:
        held = kept.token
        if held and held[0] == stamp and now < held[1]:
            return held[2]

        # Keep the lock while observing the neighbours. Concurrent freshness reads
        # then share one complete reading instead of racing into one each; the
        # lock and pid checks remain part of this fresh observation.
        reading = presence_fingerprint(live_facts(page_dir, claim), neighbors)
        kept.token = (stamp, now + PRESENCE_CACHE_S, reading)
        return reading


def nudge_unwatched(page: PageTransaction) -> None:
    """Message the claimant of a page holding input nothing will carry, once per
    ending of its turn.

    Nothing carries it when no wait lease is held and the activity fold reads a
    nudge as due (`activity.nudge_due`): the claimant takes no input, because its
    turn was seen to end, closed by the Stop hook or interrupted as its harness's
    record says. Each ending gets one nudge per page, named by the claim's turn
    and the stamp that ended or last renewed it, so a user ticking three boxes queues
    one turn or one approval rather than three, while a turn interrupted again after
    a new prompt is messaged again. The claimant's harness decides whether its
    session can be reached at all and what to say; a harness whose watcher is a
    process of its own has nowhere to put this and answers no.

    Admission calls it, and so does a watch giving up its lease, and the page's
    server once it reads a turn interrupted (`nudge_interrupted`). It runs under the
    page's lock, so the mark it leaves is exact: a local socket accepts or refuses at
    once, and input after a refusal tries again."""
    claim, page_dir = page.active_claim, page.page_dir
    if not claim or wait_is_live(page_dir, claim["id"]):
        return
    present, turn = claimant_reading(page_dir, page.events)
    mark = turn_ending(claim)
    if (
        nudge_due(present, turn)
        and claim.get("messaged_ending") != mark
        and claim_harness(claim).nudge(page_dir)
    ):
        page.note_messaged(mark)


def turn_ending(claim: dict) -> str:
    """The ending of the claimant's turn a message to its session answers: the
    turn's id and its close stamp, or for an interrupted turn its last opening
    (`PageTransaction.note_messaged`)."""
    return f"{claim['turn']}@{claim['turn_closed'] or claim['turn_opened']}"


def nudge_interrupted(page_dir: Path) -> None:
    """Message the claimant whose turn was interrupted, as Escape ends one, for the
    input that turn left on the page (`nudge_unwatched`): what arrived while it ran
    and its tool boundaries had not yet taken, and what its hooks handed over that
    its harness's record does not show reached the model (`delivery.deliverable`),
    as when Escape landed while another prompt hook still ran and Claude Code
    dropped the prompt with Leaf's context.

    No hook runs on an interrupt, so nothing on the page moves when one happens;
    the page's server reads it from the harness's own record, among the live facts
    it looks at every presence interval (`server_rows`), and calls this when they
    change. Claude Code's prompt hook starts a watch that holds the lease through
    its turn and wakes for what an interrupt leaves, so this sends only where no
    watch runs: after a turn whose prompt came before the session held any page,
    whose watch ended at once, or once a watch has failed. A watch that wakes the
    session marks the ending it woke it for (`session.woke_after`), so the moment
    between its lease going and the woken turn starting sends nothing more. A turn
    a Stop hook closed is left alone: that hook starts the watch that wakes for
    what the turn left."""
    from .delivery import deliverable
    from .session import wake_inputs

    with PageTransaction(page_dir) as page:
        claim = page.active_claim
        if (
            claim is not None
            and claim["turn_closed"] is None
            and wake_inputs(page, deliverable(page))
        ):
            nudge_unwatched(page)
