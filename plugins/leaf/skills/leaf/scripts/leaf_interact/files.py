"""Immutable version paths and filesystem change stamps."""

import ctypes
import json
import os
import re
import secrets
import sys
from pathlib import Path
from typing import NamedTuple


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
    located_targets = [_path_location(target) for target in targets]
    if any(
        left == right
        for index, left in enumerate(located_targets)
        for right in located_targets[index + 1 :]
    ):
        sys.exit("two customization files resolve to the same target")
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


class _Location(NamedTuple):
    """A path in the one form containment can be read off without touching disk.

    `lineage` is the filesystem identity — `samefile`'s own pair — of the deepest
    existing ancestor and of every ancestor above it, deepest first; `tail` is
    the components below that ancestor which don't exist yet, case-folded where
    the volume ignores case. Two of these answer every question below by
    comparison alone.

    That is the whole point of the form. The callers are set intersections: every
    layer source against every other, every source against every vendored
    destination — 786 containment tests over the shipped layer's thirty-six
    distinct paths. Asked path-by-path, each test re-resolved both paths and
    stat'd its way up both ancestor chains, so `page init` spent two thirds of
    itself on some 37,000 `stat` calls. Canonicalising each path once leaves the
    syscalls proportional to the paths rather than to the tests, which halves
    `page init` and takes two thirds off its system time."""

    lineage: tuple
    tail: tuple


def _path_location(path: Path) -> _Location:
    """Read a path into the form above."""
    ancestor = path.resolve()
    tail = []
    while True:
        try:
            identity = ancestor.stat()
        except (FileNotFoundError, NotADirectoryError):
            tail.append(ancestor.name)
            ancestor = ancestor.parent
            continue
        break
    lineage = [(identity.st_dev, identity.st_ino)]
    # The ancestors of a path that resolved all exist, so a failure here is the
    # filesystem moving under the command and belongs to whoever called it.
    for parent in ancestor.parents:
        above = parent.stat()
        lineage.append((above.st_dev, above.st_ino))
    # Only a tail can be case-folded, so a path that exists never pays for the
    # volume probe — which is every path the set intersections compare.
    if tail and not _filesystem_case_sensitive(ancestor):
        tail = [part.casefold() for part in tail]
    return _Location(tuple(lineage), tuple(reversed(tail)))


def _filesystem_case_sensitive(path: Path) -> bool:
    """Whether new names on path's filesystem distinguish letter case."""
    if sys.platform != "darwin":
        return os.path.normcase("A") != os.path.normcase("a")

    # Darwin exposes this per volume rather than through normcase: APFS can be
    # mounted either way, and normcase leaves names unchanged in both cases.
    class AttrList(ctypes.Structure):
        _fields_ = [
            ("bitmapcount", ctypes.c_uint16),
            ("reserved", ctypes.c_uint16),
            ("commonattr", ctypes.c_uint32),
            ("volattr", ctypes.c_uint32),
            ("dirattr", ctypes.c_uint32),
            ("fileattr", ctypes.c_uint32),
            ("forkattr", ctypes.c_uint32),
        ]

    class VolumeCapabilities(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_uint32),
            ("capabilities", ctypes.c_uint32 * 4),
            ("valid", ctypes.c_uint32 * 4),
        ]

    attr_vol_info = 0x80000000
    attr_vol_capabilities = 0x00020000
    case_sensitive = 0x00000100
    attributes = AttrList(5, 0, 0, attr_vol_info | attr_vol_capabilities, 0, 0, 0)
    result = VolumeCapabilities()
    getattrlist = ctypes.CDLL(None, use_errno=True).getattrlist
    getattrlist.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(AttrList),
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_ulong,
    ]
    getattrlist.restype = ctypes.c_int
    if getattrlist(
        os.fsencode(path),
        ctypes.byref(attributes),
        ctypes.byref(result),
        ctypes.sizeof(result),
        0,
    ):
        return True
    if not result.valid[0] & case_sensitive:
        return True
    return bool(result.capabilities[0] & case_sensitive)


def location_is_within(here: _Location, there: _Location) -> bool:
    """The one implementation of containment; everything below reads it.

    An existing `there` is reached by finding its identity among `here`'s
    ancestors. One that doesn't exist yet is reached only from the same deepest
    existing ancestor, with its tail as a prefix — which is also why folding each
    tail by its own volume above is safe: tails are compared only when the two
    ancestors are one inode, and so one volume."""
    if not there.tail:
        return there.lineage[0] in here.lineage
    return (
        here.lineage[0] == there.lineage[0]
        and here.tail[: len(there.tail)] == there.tail
    )


def locations_overlap(left: _Location, right: _Location) -> bool:
    return location_is_within(left, right) or location_is_within(right, left)


def located(paths) -> list:
    """Each path beside its location, for a caller about to compare it many times."""
    return [(path, _path_location(path)) for path in paths]


def path_is_within(path: Path, root: Path) -> bool:
    """Filesystem-aware containment, including not-yet-created descendants."""
    return location_is_within(_path_location(path), _path_location(root))


def paths_same(left: Path, right: Path) -> bool:
    # Containment both ways is equality of the canonical form: neither path can
    # be a strict ancestor of the other and still contain it.
    return _path_location(left) == _path_location(right)
