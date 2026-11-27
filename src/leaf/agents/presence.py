"""Page and neighboring-leaf presence readings, and the page's work folded with its
presence (`read_work`)."""

import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from leaf.base.files import file_stamp, latest_revision, list_revisions
from leaf.base.harness import claim_harness
from leaf.base.leases import lock_is_held, wait_is_live, waiter_lease_path
from leaf.base.page_memory import memo
from leaf.base.rows import ROW, read_row, row_path
from leaf.base.schema import SERVER_LOCK, UNNAMED_AGENT
from leaf.base.server import running_server
from leaf.base.service import claim_is_active, claim_records, page_claim, read_stream
from leaf.base.state import now_iso, state_home
from leaf.records.activity import (
    Turn,
    current_turn,
    declaration,
    declared_at,
    undeclared,
)
from leaf.records.transaction import (
    PageTransaction,
    acknowledged,
    owned_pages,
    unacknowledged,
)
from leaf.source.revision_artifact import latest_title, read_revision

if TYPE_CHECKING:
    from leaf.records.work_state import WorkState

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
    """The page's reading of its neighbours (`other_leaves`), which `/api/pages`
    answers and the news names by its `pages_reading`. Nothing the page's own state
    or reading holds takes it, so a neighbour's change moves only this list, and a
    tab reads this page's state again for its own changes alone.

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


def pages_reading(pages: list) -> str | None:
    """The token naming a list of other pages (`neighbor_reading`), which the news
    answer carries beside the page's own reading, or None while the list is empty, so
    a tab with no neighbour asks for no list."""
    if not pages:
        return None
    return hashlib.sha256(
        json.dumps(pages, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


class _Presence:
    """What a page keeps of its presence between readings.

    The lock is held through a whole observation, so concurrent freshness readers on the
    page share one reading rather than racing into one parse each."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        # (page reading and wait lease; expiry; the token given)
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
        current = set(ROW.glob(rows)) if rows.is_dir() else set()
        for path in _row_files.keys() - current:
            del _row_files[path]
        for path in current:
            key = file_stamp(ROW.file(path))
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


def live_servers(among: set[Path] | None = None):
    """Each page a row names whose server holds its lease, by its directory, with
    its row record and running service (`server.running_server`); only those
    `among` resolved page directories, where given, whose leases alone it then
    checks. Every such server serves with this state home's key
    (`server.host_key`). The row of a page whose lease no process holds is deleted
    here (`other_leaves`)."""
    for candidate, record in neighbor_candidates():
        if among is not None and candidate not in among:
            continue
        # A neighbour's fault stays its own. This is the one read of state some
        # other page owns: a directory deleted mid-scan (stale pages are deleted
        # and made again) or a file a disk fault corrupted would otherwise 500
        # every open page's state read on the machine, blaming the page that asked.
        try:
            info = running_server(candidate)
            if info is None and not lock_is_held(candidate / SERVER_LOCK):
                ROW.remove(row_path(candidate))
        except Exception:
            continue
        if info is not None:
            yield candidate, record, info


def started_in(session: str) -> set[Path]:
    """The pages whose rows name `session` as the one whose shell started their
    server for no session (`server_rows`), whether or not that server still runs:
    `live_leaves` takes only the live ones, and deletes the rest's rows."""
    return {
        page
        for page, record in neighbor_candidates()
        if record["started_in"] == session
    }


def live_leaves(among: set[Path] | None = None) -> list:
    """Each live page that is not closed, by its directory, with its row entry, in
    title order (`other_leaves` says what each costs and holds); only those `among`
    resolved page directories, where given, whose leases alone it then checks."""
    leaves = []
    for candidate, record, info in live_servers(among):
        try:
            row = read_row(candidate, info, record=record)
            if row is not None and row["activity"]["presence"] != "closed":
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
        except Exception:
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
                    harness.session_name()
                    if (harness := claim_harness(claim))
                    else None
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
    harness = claim_harness(active)
    return {
        "listening": process
        and wait_is_live(page_dir, active["id"] if active else None),
        # None when nothing claimed the page — leaf run outside an agent harness.
        "session_alive": active is not None if claim else None,
        "live_turn": harness.live_turn() if harness else None,
        "session_name": (
            named.session_name() if (named := claim_harness(claim)) else None
        ),
        # Whether a nudge would start the claimant's next turn (`Harness.input_wakes`).
        "input_wakes": bool(harness and harness.input_wakes()),
    }


# The keys `live_facts` returns.
LIVE_FACTS = (
    "listening",
    "session_alive",
    "live_turn",
    "session_name",
    "input_wakes",
)


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

    `read_served_page` spreads it into the page's own state answer, so the runtime's one
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
        # is what says that exact update is in the turn running now. It and the
        # stamps below keep the session record's names, so `state.turn_open` and
        # `state.turn_closed` read this state as they read a claim.
        "turn": claim["turn"] if claim else None,
        # When the claiming session's current turn closed, or None while it is open.
        # A `working` claim older than this is one that no later turn renewed
        # across the boundary — the same judgment the runtime's grace
        # makes, available at the moment it becomes true instead of a quarter of
        # an hour after it.
        "turn_closed": claim["turn_closed"] if claim else None,
        # When that turn opened, and whether an open turn of this session's takes
        # new input before it ends (`Harness.turn_takes_input`).
        "turn_opened": claim["turn_opened"] if claim else None,
        "turn_takes_input": bool(
            (harness := claim_harness(active)) and harness.turn_takes_input()
        ),
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


def read_work(page_dir: Path, events: list) -> "WorkState":
    """The page's work as the served state folds it (`work_state.work_state`,
    `served_state.context.PageRead.work`): the log over the live revision, with the
    claim's presence and live activity, for a transport or command that reads no
    other part of the served page. The fold loads here, so a reader of presence
    alone, such as `leaf page list`, loads none of it."""
    from leaf.records.work_state import work_state

    revision = latest_revision(page_dir)
    source = read_revision(page_dir, revision) if revision is not None else None
    revisions = frozenset(list_revisions(page_dir))
    present, live_stream = presence_with_activity(page_dir, events)
    return work_state(
        events,
        source,
        revision,
        present,
        now_iso(),
        live_stream,
        revisions=revisions,
        revision_reader=lambda number: read_revision(page_dir, number),
    )


def session_turn_running(session_id: str) -> bool:
    """Whether a page `session_id` holds reads that session's turn as running
    (`claimant_reading`), each page read under its own transaction."""
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                present, turn = claimant_reading(page_dir, page.events)
                if present["claim_session"] == session_id and turn.running:
                    return True
        except FileNotFoundError:
            continue
    return False


def presence(page_dir: Path, events: list) -> dict:
    """Return the public presence projection without private activity evidence."""
    reading, _ = presence_with_activity(page_dir, events)
    return reading


def presence_fingerprint(present: dict) -> str:
    """The half of a reading that file stamps cannot supply, from the facts a state
    already carries: its `live_facts`."""
    facts = [present[key] for key in LIVE_FACTS]
    return hashlib.sha256(
        json.dumps(facts, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


def presence_reading(page_dir: Path, files: str) -> str:
    """The presence token shared by readers for one bounded freshness interval.

    It keys on `files`, the page's own reading (`page_inputs.page_reading`), which
    names every page input, and on the claimant's wait lease, the one input of
    presence outside them. A move in either invalidates it immediately; process
    and lock leases are refreshed when the interval expires. The facts are read
    the way `presence` and `read_served_page` read them, so a freshness answer and the
    state it prompts name the same reading once the bounded cache interval has
    elapsed.
    """
    claim = page_claim(page_dir)
    # A harness wait lease lives outside the page, and its lock state has no file
    # stamp of its own: `live_facts` checks it on every refresh, while its stamp
    # here invalidates the token when the lease is first created or removed. An
    # unclaimed page's lease is in the page directory, so `files` covers it.
    lease_path = waiter_lease_path(None, claim["id"]) if claim else None
    lease = file_stamp(lease_path) if lease_path is not None else None
    stamp = (files, lease)
    now = time.monotonic()
    kept = memo(page_dir, _Presence)
    with kept.lock:
        held = kept.token
        if held and held[0] == stamp and now < held[1]:
            return held[2]

        # Keep the lock while observing. Concurrent freshness reads then share one
        # complete reading instead of racing into one each; the lock and pid checks
        # remain part of this fresh observation.
        reading = presence_fingerprint(live_facts(page_dir, claim))
        kept.token = (stamp, now + PRESENCE_CACHE_S, reading)
        return reading


def turn_ending(claim: dict) -> str:
    """The ending of the claimant's turn a message to its session answers: the
    turn's id and its close stamp, or for an interrupted turn its last opening
    (`PageTransaction.note_messaged`)."""
    return f"{claim['turn']}@{claim['turn_closed'] or claim['turn_opened']}"
