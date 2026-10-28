"""The readings that name one served view of a page, and the inputs they stamp.

A served reading is the page's file stamp (`page_reading`, or a snapshot's own)
followed by a fingerprint of who is present (`presence.presence_fingerprint`), which
moves on its own clock. `/api/state` answers with one, finite `/api/news` reads name
one without rebuilding state, and the browser compares them whole. `join_reading`
builds that form; nothing else spells it.

A page's inputs are declared once, here: `page_input` says which paths inside the
page directory count, `page_roots` names the directories whose notifications report
them, and `outside_inputs` names the files outside it. No other module keeps a list
of them: a reader that keys on the page's files, such as
`presence.presence_reading`, keys on `page_reading`. The stamps below cover exactly
those inputs, and every native subscription that wakes on a page's changes
(`file_changes.page_changes`, `session.Watch`) subscribes `page_roots` and accepts
exactly them, so a write that moves a page's reading wakes each of its watchers and
a write its watchers ignore moves no reading. The one asymmetry is a watcher's
looseness: it wakes for any write to an entry of a directory the reading stamps
without descending, since adding or removing one moves that directory's stamp, and
the read that wake prompts finds nothing moved for an entry rewritten in place.
"""

import hashlib
from pathlib import Path

from ..file_bindings import bound_paths
from ..files import STAGED, entry_stamps, file_stamp
from ..schema import (
    DATA_DIR,
    INTERACTIONS_FILE,
    PAGE_PROCESS_FILES,
    SESSION_FILES,
    USER_VIEWS_FILE,
    USER_VIEWS_LOCK,
)
from ..service import claim_path, page_claim
from ..state import EVENTS_FILE, SESSION_SUFFIX, flocked, session_file

# Diagnostic writes cannot move application state. The server writes
# `user-views.json` as a tab reports its view and `observations.jsonl` for every
# request it answers; counting either would make a read say it changed itself, and
# waking on either would rouse every watcher of a page a tab is merely looking at.
UNWATCHED = frozenset({INTERACTIONS_FILE, USER_VIEWS_FILE, USER_VIEWS_LOCK})
# The page's trees stamped file by file: the authored `page/` tree and `data/`.
TREES = ("page", DATA_DIR)


def page_input(page_dir: Path, path: Path) -> bool:
    """Whether a write at `path` inside or above the page directory is a page input.

    The directory itself and its ancestors count, since replacing one replaces the
    page. Inside it: each direct child but the diagnostics (`UNWATCHED`); every file
    in `TREES`; and each entry of another directory, whose stamp moves when one is
    added or removed. A file an atomic write is still staging (`STAGED`) is not one:
    the rename that publishes it is."""
    if path == page_dir or path in page_dir.parents:
        return True
    try:
        parts = path.relative_to(page_dir).parts
    except ValueError:
        return False
    if STAGED.fullmatch(path.name):
        return False
    if len(parts) == 1:
        return parts[0] not in UNWATCHED
    return parts[0] in TREES or len(parts) == 2


def page_roots(page_dir: Path) -> dict[Path, bool]:
    """The directories whose notifications report every `page_input`, each with
    whether its whole tree counts.

    The page's parent reports the page directory being replaced, and the page
    directory its direct children. Each other directory among them reports the
    entries whose arrival or removal moves its stamp, and each of `TREES` every
    file beneath it. Nothing deeper is an input, so what each revision in
    `revisions/` holds and the page's package copies go unwatched. The roots follow
    the page's direct subdirectories as they stand: one created later is reported
    by the page directory, and the owner's next subscription takes it in."""
    roots = {page_dir.parent: False, page_dir: False}
    try:
        entries = list(page_dir.iterdir())
    except FileNotFoundError:
        return roots
    for entry in entries:
        if entry.is_dir() and not STAGED.fullmatch(entry.name):
            roots[entry] = entry.name in TREES
    return roots


def outside_inputs(page_dir: Path) -> set[Path]:
    """The files outside the page directory its reading stamps: the claim, its
    claimant session's lifecycle, and each bound file. A watcher subscribes to these
    by path, and follows a new set when the claim or the grants change."""
    return {path for _name, path in _outside(page_dir)}


def _outside(page_dir: Path) -> list[tuple[str, Path]]:
    named = [("$claim", claim_path(page_dir))]
    claim = page_claim(page_dir)
    if claim:
        # Turn openings/closings and SessionEnd are shared session publications,
        # not rewrites of every page claim. They change each claimed page's state.
        named.append(("$session", session_file(claim["id"], SESSION_SUFFIX).resolve()))
    return named + _bound(page_dir)


def _bound(page_dir: Path) -> list[tuple[str, Path]]:
    # Files a page binds for editing live outside it, so each is stamped by path.
    return [(f"$file:{name}", path) for name, path in bound_paths(page_dir).items()]


def join_reading(files: str, presence: str) -> str:
    """The served reading of one view: its file stamp, then its presence.

    Both halves are hex digests, so the dot is the only one in the reading."""
    return f"{files}.{presence}"


def page_reading(page_dir: Path) -> str:
    """A short token naming this reading of the page, taken under the log's lease.

    A stamp taken while a file is being written in place is not a state that file was
    ever at: the kernel puts the new modification time on the inode before the write
    lands, so a stat crossing an append to the log can pair that time with the size
    before it. Every append holds the log's lease, so a reading taken under it never
    names one. The lease costs one lock per look, and a look waits out a transaction
    in progress, whose end is what it would report anyway. A caller already inside
    the page's transaction takes `held_page_reading`, since the lease is not
    reentrant.
    """
    with flocked(page_dir / EVENTS_FILE):
        return held_page_reading(page_dir)


def held_page_reading(page_dir: Path) -> str:
    """`page_reading` for a caller that holds the log's lease.

    Every page input (`page_input`, `outside_inputs`), rather than the files a state
    response is known to read. The known-list is unmaintainable in the way that does
    not fail loudly: leave one out and the page simply stops hearing news, with
    nothing red to say so. The authored `page/` tree is stamped recursively: changing
    a module dependency or stylesheet is a candidate revision even when the HTML stays
    unchanged. So is `data/`, whose publication files `leaf data set` replaces
    atomically. Other directories are stamped without descending — a new revision
    moves `revisions/`, a stamp moves `events.jsonl`, and the layer cannot change
    under a served page at all: the server composes it once (`layer.selected_layer`),
    and `page init`, which rewrites the record and the page's package copies,
    restarts the server.

    Stat stamps rather than contents: the question is only whether anything moved, and
    the answer has to be cheap enough to ask many times a second. Activation keys on
    the same stamps (`source_readings`), so a file source validation reads that could
    change without moving it would leave a save unactivated; `media/` is stamped
    without descending because its filenames are content-addressed. The state answer
    also carries each bound file's stamp (`file_bindings.binding_stamps`), naming
    which binding moved.
    """
    stamps = _page_stamps(page_dir)
    stamps.extend((name, file_stamp(path)) for name, path in _outside(page_dir))
    return _token(stamps)


def record_reading(page_dir: Path) -> str:
    """Name durable page inputs with the same file stamps as live readings.

    Claim, lease, stream and browser observations belong to a serving process.
    A dormant publication excludes them, while bound external files still change
    what its canonical state answers.
    """
    stamps = [
        stamp for stamp in _page_stamps(page_dir) if stamp[0] not in PAGE_PROCESS_FILES
    ]
    stamps.extend((name, file_stamp(path)) for name, path in _bound(page_dir))
    return _token(stamps)


# What a page has accumulated rather than what its author wrote: the log, and the
# revisions activation writes from the source.
HISTORY = frozenset({EVENTS_FILE, "revisions"})


def source_readings(page_dir: Path) -> tuple[str, str]:
    """The page's reading split in two: its source, and its history.

    The same stamps `page_reading` takes, less the claim and the session files
    (`SESSION_FILES`). History is `HISTORY`; source is every other stamp, so a file
    nothing names here counts as source and moves the activation it could change.
    Leaving the session out is what lets a harness stream a turn or a wait take its
    lease without the next state read validating the whole page again; declaring a
    status and acknowledging a delivery append to the log, which is history.
    """
    stamps = [
        stamp for stamp in _page_stamps(page_dir) if stamp[0] not in SESSION_FILES
    ]
    return (
        _token([stamp for stamp in stamps if stamp[0] not in HISTORY]),
        _token([stamp for stamp in stamps if stamp[0] in HISTORY]),
    )


def _page_stamps(page_dir: Path) -> list[tuple[str, object]]:
    stamps = entry_stamps(page_dir, UNWATCHED)
    stamps.extend(
        (entry.relative_to(page_dir).as_posix(), file_stamp(entry))
        for tree in TREES
        for entry in sorted((page_dir / tree).rglob("*"))
        if entry.is_file() and not STAGED.fullmatch(entry.name)
    )
    return stamps


def _token(stamps: list) -> str:
    return hashlib.sha256(repr(stamps).encode()).hexdigest()[:16]
