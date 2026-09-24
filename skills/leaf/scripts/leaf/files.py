"""Mutable source, immutable revisions, and public version addresses."""

import hashlib
import json
import os
import re
import secrets
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from stat import S_ISDIR, S_ISREG
from typing import TypeVar

from .locations import path_location

# The name an atomic write stages under, beside its target, for the moment before the
# rename (`replace_files` below). A reader of the directory looks past it: it is not yet
# any file the page has, and a look that counted it would see the page move twice for
# a write that moved it once.
STAGED = re.compile(r"\.[0-9a-f]{16}\.tmp")


# The clock a filesystem stamps a write's modification time from. Linux reads the
# kernel's coarse clock, CLOCK_REALTIME_COARSE, which Python does not name: it moves
# once a jiffy (1–10ms by kernel build), so every write inside one tick carries the same
# time, nanosecond fields notwithstanding — measured on a 6.8 kernel, 94% of back-to-back
# rewrites of one file kept the time the write before set. APFS reads the fine clock,
# and no two of 20,000 back-to-back rewrites shared a time.
WRITE_CLOCK = 5 if sys.platform == "linux" else time.CLOCK_REALTIME


def file_stamp(path: Path):
    """What the filesystem says a file or directory is: which one, when it was last
    written, and how big it is. A page directory holds files that are written once and
    read on every request, so what each one says is worked out once and kept under this
    stamp, and one rewritten since wears a different one. A path with nothing there
    stamps as None, which keeps nothing and reads every time.

    Every freshness key in leaf is built from these stamps — the page's reading that
    `leaf wait`, the news stream and activation follow, neighbour discovery, and the
    caches of parsed files — so this is where a stamp is made exact. The time alone
    cannot be: a second write inside the tick of `WRITE_CLOCK` that stamped the first,
    to the same size, leaves it unmoved — a data file rewritten in place, an entry
    added beside a removed one, an atomic replace whose staging file reused the inode
    the one before it freed. A later write can share a time only with one that clock
    has not yet moved past, so a stamp whose time is not older than that clock's
    reading before the stat also carries what the path holds (git's rule for a racily
    clean index entry): a file's bytes, or a directory's entries and their inodes.
    That costs a read of what was written in the current tick and nothing after it.
    The stamp taken once the tick has passed drops that part, so a follower that
    looked inside the tick reads once more, then settles."""
    looked = time.clock_gettime_ns(WRITE_CLOCK)
    try:
        stat = path.stat()
        stamp = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
        if stat.st_mtime_ns >= looked:
            stamp += (_contents(path, stat.st_mode),)
    except OSError:
        return None
    return stamp


def _contents(path: Path, mode: int) -> bytes | None:
    """A digest of what a regular file holds, or of which entries a directory holds.
    Anything else — a FIFO, a socket — holds nothing a read could name without
    waiting on its writer."""
    if S_ISDIR(mode):
        with os.scandir(path) as entries:
            held = repr(
                sorted((entry.name, entry.inode()) for entry in entries)
            ).encode()
    elif S_ISREG(mode):
        held = path.read_bytes()
    else:
        return None
    return hashlib.blake2b(held, digest_size=16).digest()


# How often a reader waiting on a page looks for news: the browser's news stream,
# `leaf events --follow`, and `leaf wait`. The look is a re-stat rather than an
# in-process signal because an append does not have to come from the reader's process —
# `leaf reply` and every other command write these same files from outside a server,
# and a follower has no server at all — so one mechanism covers a browser's POST and an
# agent's command alike. Measured at 70us a look of the whole page, 0.14% of a core per
# open tab, against the full state read and log parse a timed poll cost every two
# seconds whether or not anything had happened.
LOOK_S = 0.05


Reading = TypeVar("Reading")


def next_reading(
    look: Callable[[], Reading], seen: Reading, timeout: float | None = None
) -> Reading:
    """The first reading `look` gives that differs from `seen`, looking every
    `LOOK_S` — the one wait a synchronous follower of page files makes. With
    `timeout`, the reading at that many seconds is returned whether or not it moved,
    for a follower that also owes something to the clock rather than the files.

    `look` is a stamp, never the content: the follower reads what moved only once
    this says something did, so a quiet page costs stat calls and nothing more."""
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        reading = look()
        if reading != seen:
            return reading
        if deadline is not None and time.monotonic() >= deadline:
            return reading
        time.sleep(LOOK_S)


VERSION_FILE = re.compile(r"v([1-9][0-9]*)\.html")
REVISION_FILE = re.compile(r"r([1-9][0-9]*)-([a-f0-9]{16})\.html")


def version_num(name: str) -> int:
    """A version's number is its identity; its file name only renders it. So
    everything that orders or addresses versions parses the number out rather
    than working on the name, and the names carry no zero padding — padding is
    what you add to make a string comparison come out right, and nothing here
    compares names. `v10.html` precedes `v9.html` in every ordering a string
    has, and follows it in the only one that means anything."""
    return int(VERSION_FILE.fullmatch(name).group(1))


def version_name(version: int) -> str:
    return f"v{version}.html"


def revision_num(name: str) -> int:
    """The ordered identity carried by an immutable revision file."""
    return int(REVISION_FILE.fullmatch(name).group(1))


def list_revisions(page_dir: Path) -> list[int]:
    revisions_dir = page_dir / "revisions"
    if not revisions_dir.exists():
        return []
    revisions = sorted(
        revision_num(path.name)
        for path in revisions_dir.iterdir()
        if path.is_file() and REVISION_FILE.fullmatch(path.name)
    )
    if len(revisions) != len(set(revisions)):
        sys.exit("more than one immutable revision has the same order")
    return revisions


def revision_path(page_dir: Path, revision: int) -> Path:
    """Resolve one ordered revision to its content-addressed immutable file."""
    matches = sorted((page_dir / "revisions").glob(f"r{revision}-*.html"))
    matches = [path for path in matches if REVISION_FILE.fullmatch(path.name)]
    if len(matches) != 1:
        if not matches:
            sys.exit(f"no revision r{revision} in {page_dir / 'revisions'}")
        sys.exit(f"more than one immutable file records revision r{revision}")
    return matches[0]


def latest_revision(page_dir: Path) -> int | None:
    """The newest valid revision, or None on a page with none yet."""
    revisions = list_revisions(page_dir)
    return revisions[-1] if revisions else None


def missing_revision(page_dir: Path) -> str:
    return f"no active revision; write {page_dir / 'index.html'} first"


def require_revision(page_dir: Path) -> int:
    """The newest valid revision; a command that needs one stops without it."""
    revision = latest_revision(page_dir)
    if revision is None:
        sys.exit(missing_revision(page_dir))
    return revision


def version_revisions(events: list) -> dict[int, int]:
    """Public version number to the exact revision each note stamped."""
    return {
        event["version"]: event["revision"]
        for event in events
        if event["kind"] == "note"
    }


def stamped_version(events: list, revision: int) -> int | None:
    """The public stamp on a revision, if it has one."""
    return next(
        (
            event["version"]
            for event in events
            if event["kind"] == "note" and event["revision"] == revision
        ),
        None,
    )


def version_descriptors(page_dir: Path, events: list) -> list[dict]:
    """The public stamps whose note names an existing immutable revision."""
    mappings = version_revisions(events)
    revisions = set(list_revisions(page_dir))
    return [
        {
            "version": version,
            "revision": mappings[version],
            "url": f"/versions/{version_name(version)}",
        }
        for version in sorted(mappings)
        if mappings[version] in revisions
    ]


def active_descriptor(page_dir: Path, events: list) -> dict | None:
    """The exact immutable document shown at the live root, or None before one."""
    from leaf.revision_artifact import read_manifest

    revision = latest_revision(page_dir)
    if revision is None:
        return None
    path = revision_path(page_dir, revision)
    version = stamped_version(events, revision)
    label = f"v{version}" if version is not None else revision_label(events, revision)
    return {
        "revision": revision,
        "version": version,
        "url": f"/revisions/{path.name}",
        "label": label,
        # This revision's identity as executable code, decided when it was
        # captured. A reader already holding a document compares it with the
        # digest that document's own delivery stamped, and needs a fresh document
        # only when the two differ. Read once here, so every consumer of the
        # active revision works from one reading of it.
        "executable": read_manifest(page_dir, revision).get("executable"),
        "activated_at": datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).isoformat(),
    }


def revision_label(events: list, revision: int) -> str:
    """A working revision named in the public vocabulary available at that point."""
    if version := stamped_version(events, revision):
        return f"v{version}"
    earlier = [
        event["version"]
        for event in events
        if event["kind"] == "note" and event["revision"] < revision
    ]
    return f"Draft after v{max(earlier)}" if earlier else "Draft"


def published_versions(page_dir: Path, events: list) -> list:
    """Public versions whose stamp and mapped immutable revision both exist."""
    return [item["version"] for item in version_descriptors(page_dir, events)]


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def fsync_parents(paths) -> None:
    """Make these files' directory entries durable, not just their contents.

    A create or a rename is a directory write, and it survives a crash only once
    the directory itself is synced, so every writer that adds or replaces a page
    or package member ends with this.
    """
    for parent in {path.parent for path in paths}:
        fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def replace_files(files: list) -> None:
    """Durably stage every write before replacing its target."""
    staged = []
    targets = [
        path.resolve() if follow_symlink and path.is_symlink() else path
        for path, _, follow_symlink in files
    ]
    located_targets = [path_location(target) for target in targets]
    if any(
        left == right
        for index, left in enumerate(located_targets)
        for right in located_targets[index + 1 :]
    ):
        sys.exit("two staged files resolve to the same target")
    try:
        for (path, data, follow_symlink), target in zip(files, targets, strict=True):
            for _ in range(100):
                tmp = target.with_name(f".{secrets.token_hex(8)}.tmp")
                try:
                    fd = os.open(
                        tmp,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_BINARY", 0),
                        0o666,
                    )
                    break
                except FileExistsError:
                    continue
            else:  # pragma: no cover - 64 random bits collided 100 times
                raise FileExistsError(f"could not reserve a temp file beside {target}")
            staged.append((tmp, target))
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                if follow_symlink or not path.is_symlink():
                    try:
                        os.fchmod(stream.fileno(), target.stat().st_mode & 0o777)
                    except FileNotFoundError:
                        pass  # no target to preserve a mode from
                stream.flush()
                os.fsync(stream.fileno())
        for tmp, target in staged:
            os.replace(tmp, target)
        fsync_parents(targets)
    finally:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)


def json_bytes(obj, *, indent=None) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=indent) + "\n").encode()


def write_json(path: Path, obj) -> None:
    # Atomic: the serve process reads these files while the CLI commands write them;
    # a torn cursor or status would make the page report false state. Each writer
    # stages through an exclusively created name so simultaneous writers cannot
    # replace one another's temp file.
    replace_files([(path, json_bytes(obj), False)])
