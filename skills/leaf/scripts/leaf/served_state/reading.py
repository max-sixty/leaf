"""Filesystem change readings for a served page."""

import hashlib
from pathlib import Path

from ..files import STAGED, file_stamp
from ..interaction_log import INTERACTIONS_FILE
from ..schema import DATA_DIR, EVENTS_FILE, VIEWED_FILE
from ..service import claim_path

# Diagnostic writes cannot move application state. The server writes `viewed.json`
# while a visible tab holds the news stream and `interactions.jsonl` for every request
# it answers; counting either would make a read say it changed itself.
UNWATCHED = frozenset({VIEWED_FILE, INTERACTIONS_FILE})


def page_reading(page_dir: Path) -> str:
    """A short token naming this reading of the page.

    Every direct child of the page directory except diagnostics, rather than the files
    a state response is known to read. The known-list is unmaintainable in the way
    that does not fail loudly: leave one out and the page simply stops hearing news,
    with nothing red to say so. The authored `page/` tree is also stamped recursively:
    changing a module dependency or stylesheet is a candidate revision even when the
    HTML stays unchanged. So is `data/`, whose value files another process may rewrite
    in place. Other directories are stamped without descending — a new
    revision moves `revisions/`, a stamp moves `events.jsonl`, and the
    vendored layer cannot change under a served page at all, since re-vendoring restarts
    the server.

    Stat stamps rather than contents: the question is only whether anything moved, and
    the answer has to be cheap enough to ask many times a second. Activation keys on
    the same stamps (`source_readings`), so a file source validation reads that could
    change without moving it would leave a save unactivated; `media/` is stamped
    without descending because its filenames are content-addressed.

    A stamp taken while a file is being written in place is not a state that file was
    ever at: the kernel puts the new modification time on the inode before the write
    lands, so a stat crossing an append to the log can pair that time with the size
    before it. `page_state` takes its reading inside the page transaction, under the
    log's own lease, so a state answer never names one. The news stream stats without
    the lease, which is what keeps a look cheap, so its word can — and the look after
    it, naming the settled reading, is what puts the tab right.
    """
    stamps = _page_stamps(page_dir)
    stamps.append(("", file_stamp(claim_path(page_dir))))
    return _token(stamps)


# What a page has accumulated rather than what its author wrote: the log, and the
# revisions activation writes from the source.
HISTORY = frozenset({EVENTS_FILE, "revisions"})


def source_readings(page_dir: Path) -> tuple[str, str]:
    """The page's reading split in two: its source, and its history.

    The same stamps `page_reading` takes, less the claim, which says who is
    listening rather than what the page is. History is `HISTORY`; source is every
    other stamp, so a file nothing names here counts as source and moves the
    activation it could change.
    """
    stamps = _page_stamps(page_dir)
    return (
        _token([stamp for stamp in stamps if stamp[0] not in HISTORY]),
        _token([stamp for stamp in stamps if stamp[0] in HISTORY]),
    )


def _page_stamps(page_dir: Path) -> list[tuple[str, object]]:
    stamps = sorted(
        (entry.name, file_stamp(entry))
        for entry in page_dir.iterdir()
        if entry.name not in UNWATCHED and not STAGED.fullmatch(entry.name)
    )
    stamps.extend(
        (entry.relative_to(page_dir).as_posix(), file_stamp(entry))
        for tree in ("page", DATA_DIR)
        for entry in sorted((page_dir / tree).rglob("*"))
        if entry.is_file() and not STAGED.fullmatch(entry.name)
    )
    return stamps


def _token(stamps: list) -> str:
    return hashlib.sha256(repr(stamps).encode()).hexdigest()[:16]
