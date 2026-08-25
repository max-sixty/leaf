"""Immutable version paths and filesystem change stamps."""

import re
import sys
from pathlib import Path


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


def published_versions(page_dir: Path, events: list) -> list:
    """Versions the server exposes: those whose `note` event has landed. `version
    publish` runs `version check` first, so a half-written or failing version is
    never live to an open browser — the file existing is not enough."""
    noted = {e["version"] for e in events if e["kind"] == "note"}
    return [version for version in list_versions(page_dir) if version in noted]


def latest_published(page_dir: Path, events: list) -> int:
    """The page the reader is looking at, for a message the agent makes against it — a
    comment, or a report. A version no `note` has released is a page nobody has seen, so
    there is nothing to speak about and the command says so rather than picking a file
    off disk."""
    published = published_versions(page_dir, events)
    if not published:
        sys.exit("no published version; run `leaf version publish` first")
    return published[-1]
