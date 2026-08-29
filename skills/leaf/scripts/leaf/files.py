"""Mutable source and immutable revision and version paths."""

import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from .locations import path_location

# The name an atomic write stages under, beside its target, for the moment before the
# rename (`write_files` below). A reader of the directory looks past it: it is not yet
# any file the page has, and a look that counted it would see the page move twice for
# a write that moved it once.
STAGED = re.compile(r"\.[0-9a-f]{16}\.tmp")


def file_stamp(path: Path):
    """What the filesystem says a file is: which file, when it was last written,
    and how big it is. A page directory holds files that are written once and read
    on every request, so what each one says is worked out once and kept under this
    stamp, and a file rewritten since wears a different one. A path with nothing
    there stamps as None, which keeps nothing and reads every time."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_ino, stat.st_mtime_ns, stat.st_size)


VERSION_FILE = re.compile(r"v([1-9][0-9]*)\.html")
REVISION_FILE = re.compile(r"r([1-9][0-9]*)-([a-f0-9]{16})\.html")
SOURCE_FILE = "index.html"


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


def version_path(page_dir: Path, version: int) -> Path:
    return page_dir / "versions" / version_name(version)


def list_versions(page_dir: Path) -> list:
    versions_dir = page_dir / "versions"
    if not versions_dir.exists():
        return []
    return sorted(
        version_num(p.name)
        for p in versions_dir.iterdir()
        if p.is_file() and VERSION_FILE.fullmatch(p.name)
    )


def revision_num(name: str) -> int:
    """The ordered identity carried by an immutable revision file."""
    return int(REVISION_FILE.fullmatch(name).group(1))


def revision_digest(data: bytes) -> str:
    """The short content address recorded beside a revision's order."""
    return hashlib.sha256(data).hexdigest()[:16]


def revision_name(revision: int, data: bytes) -> str:
    return f"r{revision}-{revision_digest(data)}.html"


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


def latest_revision(page_dir: Path) -> int:
    revisions = list_revisions(page_dir)
    if not revisions:
        sys.exit(f"no active revision; write {page_dir / 'index.html'} first")
    return revisions[-1]


def write_revision(page_dir: Path, revision: int, data: bytes) -> Path:
    """Write one new immutable revision after its caller has validated it.

    Page transactions serialize order assignment. Refusing an existing target
    keeps a revision immutable even if a caller is accidentally repeated.
    """
    path = page_dir / "revisions" / revision_name(revision, data)
    path.parent.mkdir(exist_ok=True)
    if path.exists() or revision in list_revisions(page_dir):
        sys.exit(f"revision r{revision} already exists")
    replace_files([(path, data, False)])
    return path


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
    """The public stamps whose note and immutable copy both exist."""
    mappings = version_revisions(events)
    return [
        {
            "version": version,
            "revision": mappings[version],
            "url": f"/versions/{version_name(version)}",
        }
        for version in sorted(mappings)
        if version_path(page_dir, version).is_file()
        and mappings[version] in list_revisions(page_dir)
    ]


def active_descriptor(page_dir: Path, events: list) -> dict:
    """The exact immutable document shown at the live root."""
    revision = latest_revision(page_dir)
    path = revision_path(page_dir, revision)
    version = stamped_version(events, revision)
    previous = [
        descriptor["version"]
        for descriptor in version_descriptors(page_dir, events)
        if descriptor["revision"] <= revision
    ]
    label = (
        f"v{version}"
        if version is not None
        else (f"Draft after v{previous[-1]}" if previous else "Draft")
    )
    return {
        "revision": revision,
        "version": version,
        "url": f"/revisions/{path.name}",
        "label": label,
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
    """Stamped versions: those whose immutable file and `note` both exist."""
    noted = {e["version"] for e in events if e["kind"] == "note"}
    return [version for version in list_versions(page_dir) if version in noted]


def latest_published(page_dir: Path, events: list) -> int:
    """The newest stamped version, for callers that specifically need a stamp."""
    published = published_versions(page_dir, events)
    if not published:
        sys.exit("no stamped version; run `leaf version stamp` first")
    return published[-1]


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def replace_files(files: list) -> None:
    """Stage every (path, bytes, follow_symlink) write before replacing targets."""
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
        for (path, data, follow_symlink), target in zip(files, targets):
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
                    tmp.chmod(target.stat().st_mode & 0o777)
                except FileNotFoundError:
                    pass  # no target to preserve a mode from
        for tmp, target in staged:
            os.replace(tmp, target)
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
