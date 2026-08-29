"""Filesystem path identity, containment, and overlap."""

import ctypes
import hashlib
import os
import sys
from pathlib import Path
from typing import NamedTuple


class PathLocation(NamedTuple):
    """A path in the one form containment can be read off without touching disk.

    `lineage` is the filesystem identity — `samefile`'s own pair — of the deepest
    existing ancestor and of every ancestor above it, deepest first; `tail` is
    the components below that ancestor which don't exist yet, case-folded where
    the volume ignores case. Two of these answer every question below by
    comparison alone.

    That is the whole point of the form. The callers are set intersections: every
    package input against every other, every input against every vendored
    destination — 786 containment tests over the shipped layer's thirty-six
    distinct paths. Asked path-by-path, each test re-resolved both paths and
    stat'd its way up both ancestor chains, so `page init` spent two thirds of
    itself on some 37,000 `stat` calls. Canonicalising each path once leaves the
    syscalls proportional to the paths rather than to the tests, which halves
    `page init` and takes two thirds off its system time."""

    lineage: tuple
    tail: tuple


def page_key(page_dir: Path) -> str:
    """A filesystem-safe identity for state held outside one page directory."""
    return hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()


def path_location(path: Path) -> PathLocation:
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
    return PathLocation(tuple(lineage), tuple(reversed(tail)))


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


def location_is_within(here: PathLocation, there: PathLocation) -> bool:
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


def locations_overlap(left: PathLocation, right: PathLocation) -> bool:
    return location_is_within(left, right) or location_is_within(right, left)


def located(paths) -> list:
    """Each path beside its location, for a caller about to compare it many times."""
    return [(path, path_location(path)) for path in paths]


def path_is_within(path: Path, root: Path) -> bool:
    """Filesystem-aware containment, including not-yet-created descendants."""
    return location_is_within(path_location(path), path_location(root))


def paths_same(left: Path, right: Path) -> bool:
    # Containment both ways is equality of the canonical form: neither path can
    # be a strict ancestor of the other and still contain it.
    return path_location(left) == path_location(right)
