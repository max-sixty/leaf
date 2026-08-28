"""State projections and change readings for one served page."""

import hashlib
import json
import time
from pathlib import Path

from .asks import page_ask_projection, thread_ask_projection
from .data import read_data
from .event_log import now_iso, read_cursor, read_events
from .events import (
    action_rests_on,
    action_retracted,
    awaits_agent,
    bare_reaction,
    build_threads,
    is_reaction,
    retractions,
    seat_root,
    seats_with_agent,
    spoken_turns,
    taken_back,
    undo_error,
)
from .files import (
    STAGED,
    active_descriptor,
    file_stamp,
    latest_revision,
    list_revisions,
    read_json,
    revision_path,
    version_descriptors,
)
from .host import state_home
from .passages import enclosing_of, page_passages, spoken
from .projection import (
    StateProjection,
    canonical_updates,
    decisions,
    folded_facet,
    page_projection,
    state_projection,
)
from .registry import RegistryError, layer_generation, load_registry
from .server import running_server
from .service import (
    claim_is_active,
    claim_path,
    claim_records,
    claim_update_sources,
    page_claim,
    unacknowledged,
    wait_is_live,
)
from .structure import parse_revision
from .thread_context import thread_roots, thread_structure


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


def _browser_projection(
    projection: StateProjection,
    *,
    scope: str,
    within: dict,
    floors: dict,
) -> dict:
    """Serialize one declared projection without making the wire its authority."""
    entries = []
    for coordinate, (event, spec) in projection.classified.values():
        restated = []
        if event["kind"] == "action":
            restated = [
                identity
                for identity in action_rests_on(event, within)
                if floors.get(identity, 0) > event["revision"]
            ]
        entries.append(
            {
                "event": event,
                "coordinate": list(coordinate),
                "value": folded_facet(event, spec) if spec.get("record") else None,
                "scope": scope,
                "restated": restated,
            }
        )
    return {
        "entries": entries,
        "actions": [event["id"] for event, _spec in projection.actions.values()],
        "reports": [
            event["id"]
            for standing in projection.reports.values()
            for event, _spec in standing
        ],
        "desired": [event["id"] for event, _spec in projection.desired.values()],
    }


def _thread_projection(events: list, registry: dict):
    structure = thread_structure(events)
    roots = thread_roots(events)
    byid, spk = {}, {}
    for event in events:
        if markup := event.get("markup"):
            fragment = structure.fragments[event["id"]]
            byid.update(fragment.by_id)
            spk.update(spoken(markup, registry))
    projection = state_projection(events, byid, spk, registry, None, floors={})
    return projection, byid, spk, roots, structure


def _thread_awaits_reader(
    thread: dict,
    registry: dict,
    awaiting: dict[str, bool],
    structure,
) -> bool:
    if thread["resolved"]:
        return False
    turns = spoken_turns(thread)
    if not turns or turns[-1]["author"] != "claude":
        return False
    last = turns[-1]
    if last["kind"] == "reply":
        fragment = structure.fragments.get(last["id"])
        asks = [
            rec["attrs"].get("id")
            for rec in (fragment.lf_elements if fragment else [])
            if (registry.get(rec["tag"]) or {}).get("x-awaits") is not None
        ]
        structural = (
            any(awaiting.get(identity, False) for identity in asks) if asks else None
        )
        if structural is False or (structural is None and not last.get("awaits")):
            return False
    tokens = registry.get("$reactions", {}).get("tokens", {})
    return not any(
        is_reaction(message)
        and message["author"] == "user"
        and message.get("parent") == last["id"]
        and (tokens.get(message["token"]) or {}).get("settles")
        for message in thread["msgs"]
    )


def _browser_conversation(
    events: list, registry: dict, threads: dict
) -> tuple[dict, StateProjection]:
    settled = {identity for identity, thread in threads.items() if thread["resolved"]}
    prepared = _thread_projection(events, registry)
    projection, _byid, _spk, _roots, structure = prepared
    asks, awaiting = thread_ask_projection(events, registry, settled, prepared=prepared)
    rendered_threads = [
        {
            **thread,
            "awaits_agent": awaits_agent(thread),
            "awaits_reader": _thread_awaits_reader(
                thread, registry, awaiting, structure
            ),
            "bare_reaction": bare_reaction(thread),
            "seat": seat_root(thread),
        }
        for thread in threads.values()
    ]
    return (
        {
            "projection": _browser_projection(
                projection, scope="conversation", within={}, floors={}
            ),
            "asks": {"reader": asks, "unanswered": asks, "awaiting": awaiting},
            "threads": rendered_threads,
            "done": [event for event in events if event["kind"] == "done"],
        },
        projection,
    )


def _browser_document(
    html: str,
    events: list,
    registry: dict,
    revision: int,
    threads: dict,
    *,
    prepared: tuple | None = None,
) -> tuple[dict, StateProjection, dict, dict]:
    projection, parser, spk = prepared or page_projection(
        html, events, registry, revision
    )
    passages = page_passages(html, registry, decisions(projection.actions, registry))
    dropped = set(passages.retired) | set(passages.gone)
    reader_asks, reader_awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
    )
    unanswered_asks, unanswered_awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        set(),
    )
    within = enclosing_of(spk)
    floors = retractions(events, revision)
    return (
        {
            "revision": revision,
            "projection": _browser_projection(
                projection,
                scope="document",
                within=within,
                floors=floors,
            ),
            "asks": {
                "reader": reader_asks,
                "unanswered": unanswered_asks,
                "awaiting": reader_awaiting,
                "unanswered_awaiting": unanswered_awaiting,
            },
        },
        projection,
        within,
        floors,
    )


def _restores_desired(
    event: dict,
    coordinate: tuple,
    projection: StateProjection,
    withdrawn: set,
    within: dict,
    floors: dict,
) -> bool:
    """Whether withdrawing one action exposes another durable value there."""
    desired = projection.desired.get(coordinate)
    if desired and desired[0]["id"] != event["id"]:
        return True
    if projection.reports.get(coordinate):
        return True
    return any(
        candidate_coordinate == coordinate
        and candidate["kind"] == "action"
        and candidate["id"] != event["id"]
        and candidate["id"] not in withdrawn
        and not action_retracted(candidate, floors, within)
        for candidate_coordinate, (candidate, _spec) in projection.classified.values()
    )


def _browser_undo_candidates(
    events: list,
    within: dict,
    document_floors: dict,
    document_projection: StateProjection,
    conversation_projection: StateProjection,
) -> list[dict]:
    classified = {
        **document_projection.classified,
        **conversation_projection.classified,
    }
    candidates = []
    withdrawn = taken_back(events)
    for event in reversed(events):
        if (
            event.get("author") != "user"
            or event["kind"] == "undo"
            or event["id"] in withdrawn
        ):
            continue
        if undo_error({"undoes": event["id"]}, events, within):
            continue
        item = {"event": event}
        if event["kind"] == "action" and event["id"] in classified:
            coordinate, _entry = classified[event["id"]]
            item["coordinate"] = list(coordinate)
            if event["id"] in document_projection.classified:
                projection = document_projection
                action_within = within
                floors = document_floors
            else:
                projection = conversation_projection
                action_within = {}
                floors = {}
            item["restores_desired"] = _restores_desired(
                event,
                coordinate,
                projection,
                withdrawn,
                action_within,
                floors,
            )
        candidates.append(item)
    return candidates


def browser_state(
    documents: dict[int, str],
    events: list,
    registry: dict,
    active_revision: int,
    claims: list,
    active: dict,
    view_revisions: set[int],
) -> dict:
    """The browser's derived reading of one transaction-consistent page snapshot.

    Documents and the append-only log remain the authorities. This object is an
    ephemeral transport projection, keyed by the exact log sequence and revisions
    from which it was read.
    """
    through_seq = events[-1]["seq"] if events else 0
    active_html = documents[active_revision]
    active_projection, active_parser, active_spk = page_projection(
        active_html, events, registry, active_revision
    )
    active_within = enclosing_of(active_spk)
    threads = build_threads(events, active_within)
    conversation, conversation_projection = _browser_conversation(
        events, registry, threads
    )

    views = {}
    for revision in sorted(view_revisions):
        html = documents[revision]
        document, projection, within, floors = _browser_document(
            html,
            events,
            registry,
            revision,
            threads,
            prepared=(active_projection, active_parser, active_spk)
            if revision == active_revision
            else None,
        )
        classified = {
            **projection.classified,
            **conversation_projection.classified,
        }
        coverage = []
        for event in events:
            if event["kind"] in {"action", "report"}:
                classified_entry = classified.get(event["id"])
            elif event["kind"] == "undo":
                classified_entry = classified.get(event["undoes"])
            else:
                continue
            coverage.append(
                {
                    "event": event,
                    "coordinate": (
                        list(classified_entry[0]) if classified_entry else None
                    ),
                }
            )
        published_at = next(
            (
                event["ts"]
                for event in reversed(events)
                if event["kind"] == "note" and event["revision"] == revision
            ),
            active.get("activated_at") if active_revision == revision else None,
        )
        views[str(revision)] = {
            "basis": {"revision": revision, "through_seq": through_seq},
            "document": document,
            "updates": canonical_updates(projection, claims, threads, events),
            "undo": _browser_undo_candidates(
                events,
                within,
                floors,
                projection,
                conversation_projection,
            ),
            "coverage": coverage,
            "published_at": published_at,
        }
    return {
        "basis": {"through_seq": through_seq},
        "views": views,
        "conversation": conversation,
        "receipts": [event for event in events if event.get("attempt")],
        "version_notes": {
            str(event["version"]): event["text"]
            for event in events
            if event["kind"] == "note"
        },
    }


def project_browser_state(
    page_dir: Path,
    events: list,
    view_revision: int | None,
    active: dict | None,
    claims: list,
    source_overrides: dict[int, str] | None = None,
    *,
    include_active_view: bool = True,
) -> dict | None:
    """Project only the documents one browser reading can consume.

    A normal state needs the revision the tab is showing and the active revision it
    may activate next. Older comparison bases are projected on demand at the tab's
    exact log boundary, rather than making every state poll parse every immutable
    revision the page has ever had.
    """
    if active is None:
        return None
    active_revision = active["revision"]
    requested_revision = view_revision or active_revision
    revisions = set(list_revisions(page_dir)) | set(source_overrides or {})
    if requested_revision not in revisions:
        raise ValueError(f"unknown view revision r{requested_revision}")
    wanted = {requested_revision, active_revision}
    documents = {}
    for revision in sorted(wanted):
        if source_overrides and revision in source_overrides:
            documents[revision] = source_overrides[revision]
        else:
            documents[revision] = revision_path(page_dir, revision).read_text(
                encoding="utf-8"
            )
    try:
        registry = load_registry(page_dir)
    except RegistryError:
        return None
    if registry is None:
        return None
    return browser_state(
        documents,
        events,
        registry,
        active_revision,
        claims,
        active,
        wanted if include_active_view else {requested_revision},
    )


def full_state(
    page_dir: Path,
    events: list,
    _versions: list | None = None,
    layer: str | None = None,
    source_error: str | None = None,
    view_revision: int | None = None,
    active_override: dict | None = None,
    source_overrides: dict[int, str] | None = None,
) -> dict:
    if active_override is not None:
        active = active_override
    else:
        try:
            active = active_descriptor(page_dir, events)
        except SystemExit:
            active = None
    present = presence(page_dir, events)
    browser = project_browser_state(
        page_dir,
        events,
        view_revision,
        active,
        present["claims"],
        source_overrides,
    )
    return {
        "layer": layer or layer_generation(page_dir),
        # The clock every timestamp below was written by. A seat dating one reads
        # `Date.now()`, which is the reader's own machine: a laptop an hour out
        # calls a claim made this minute an hour stale, on every seat at once, and
        # neither side can tell from the timestamp alone. Sent so the reading is
        # against the writer's clock rather than the reader's.
        "now": now_iso(),
        # The moment this answer was taken, for a tab holding two. Answers cross — two
        # sockets, one held by a proxy or a test while a later one lands, a POST's
        # answer beside a read — and the log's sequence and the data's revision order
        # everything in a state but the reading, which is a hash with no order of its
        # own. Stamped inside the page transaction every served answer is built under,
        # so the order of these is the order the answers were taken in, whichever
        # order they land. The wall clock rather than a counter: a counter starts over
        # with the server, and a tab open across that restart would refuse every
        # answer until the count caught up.
        "taken": time.time(),
        "active": active,
        "versions": version_descriptors(page_dir, events),
        "source_error": source_error,
        "data": read_data(page_dir),
        **present,
        "browser": browser,
        # As logged: a message's text is Markdown the page's vendored runtime renders,
        # and its markup is the fragment the CLI gate validated. The wire adds nothing,
        # so the only vocabulary a page's frozen layer has to keep speaking is the
        # log's own, which $events already stamps.
        "events": events,
    }


# The one thing a reading must not be built from. The server writes `viewed.json` for
# as long as a tab holds the page open, so counting it would make the page's own
# presence change the page's token: a stream asking "has anything changed?" would be
# told yes, by its own listener.
UNWATCHED = frozenset({"viewed.json"})


def page_reading(page_dir: Path) -> str:
    """A short token naming this reading of the page.

    Every direct child of the page directory, rather than the files a state response is
    known to read. The known-list is unmaintainable in the way that does not fail
    loudly: leave one out and the page simply stops hearing about that kind of news,
    with nothing red to say so. Directories are stamped without descending, which is
    enough — a new version file moves `versions/`, and the vendored layer cannot change
    under a served page at all, since re-vendoring restarts the server.

    Stat stamps rather than contents: the question is only whether anything moved, and
    the answer has to be cheap enough to ask many times a second.
    """
    stamps = sorted(
        (entry.name, file_stamp(entry))
        for entry in page_dir.iterdir()
        if entry.name not in UNWATCHED and not STAGED.fullmatch(entry.name)
    )
    stamps.append(("", file_stamp(claim_path(page_dir))))
    return hashlib.sha256(repr(stamps).encode()).hexdigest()[:16]


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
