"""Mutable source, immutable revisions, and public version addresses."""

import json
import os
import re
from collections.abc import Collection
from pathlib import Path

from .locations import path_location
from .page_memory import Slot, memo
from .refusals import Refused
from .schema import REVISION_NAME, VERSION_NAME
from .state import file_stamp, replace_bytes

# The name an atomic write stages under, beside its target, for the moment before the
# rename (`replace_files` below). A reader of the directory looks past it: it is not yet
# any file the page has, and a look that counted it would see the page move twice for
# a write that moved it once.
STAGED = re.compile(r"\.leaf-[a-z0-9_]+\.tmp")


def entry_stamps(directory: Path, ignored: Collection[str]) -> list[tuple[str, object]]:
    """Each direct child of a directory by name and stamp, in name order.

    Leaves out the names in `ignored`, which each caller chooses by what its reading
    depends on, and every file an atomic write is still staging (`STAGED`), which no
    reader depends on."""
    return sorted(
        (entry.name, file_stamp(entry))
        for entry in directory.iterdir()
        if entry.name not in ignored and not STAGED.fullmatch(entry.name)
    )


VERSION_FILE = re.compile(rf"{VERSION_NAME}\.html")
REVISION_FILE = re.compile(rf"{REVISION_NAME}\.html")


def version_num(name: str) -> int:
    """A version's number is its identity; its file name only renders it. So
    everything that orders or addresses versions parses the number out rather
    than working on the name, and the names carry no zero padding — padding is
    what you add to make a string comparison come out right, and nothing here
    compares names. `v10.html` precedes `v9.html` in every ordering a string
    has, and follows it in the only one that means anything."""
    return int(VERSION_FILE.fullmatch(name).group("version"))


def version_name(version: int) -> str:
    return f"v{version}.html"


def revision_num(name: str) -> int:
    """The ordered identity carried by an immutable revision file."""
    return int(REVISION_FILE.fullmatch(name).group("revision"))


class _RevisionFiles(Slot):
    """The revision markers a page's `revisions/` holds, by order, kept under that
    directory's stamp. A marker appears by a link into the directory
    (`revision_artifact.publish_artifact`), and every entry added, removed or renamed
    there moves the stamp, so a held listing is the directory's current one. A server
    answers each of a document's few hundred module requests from this listing,
    which would otherwise be a directory scan apiece."""


def _revision_files(page_dir: Path) -> dict[int, tuple[str, ...]]:
    """Each revision's marker file names, in revision order."""
    directory = page_dir / "revisions"
    stamp = file_stamp(directory)
    if stamp is None:
        return {}
    return memo(page_dir, _RevisionFiles).get(stamp, lambda: _scan_revisions(directory))


def _scan_revisions(directory: Path) -> dict[int, tuple[str, ...]]:
    found: dict[int, list[str]] = {}
    with os.scandir(directory) as entries:
        for entry in entries:
            if REVISION_FILE.fullmatch(entry.name) and entry.is_file():
                found.setdefault(revision_num(entry.name), []).append(entry.name)
    return {revision: tuple(sorted(found[revision])) for revision in sorted(found)}


def revision_names(page_dir: Path) -> dict[int, str]:
    """Each revision's immutable marker file name, in revision order."""
    markers = _revision_files(page_dir)
    if any(len(names) > 1 for names in markers.values()):
        raise Refused("more than one immutable revision has the same order")
    return {revision: names[0] for revision, names in markers.items()}


def list_revisions(page_dir: Path) -> list[int]:
    return list(revision_names(page_dir))


def revision_path(page_dir: Path, revision: int) -> Path:
    """Resolve one ordered revision to its content-addressed immutable file."""
    revisions = page_dir / "revisions"
    names = _revision_files(page_dir).get(revision, ())
    if len(names) != 1:
        if not names:
            raise Refused(f"no revision r{revision} in {revisions}")
        raise Refused(f"more than one immutable file records revision r{revision}")
    return revisions / names[0]


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
        raise Refused(missing_revision(page_dir))
    return revision


def unfinished_publications(page_dir: Path, events: list) -> list[dict]:
    """The first admitted event naming each publication whose revision marker is
    not yet written: a publication interrupted between its prerequisite and its
    marker (`revision_artifact`), in log order."""
    published = set(list_revisions(page_dir))
    unfinished = {}
    for event in events:
        if event.get("publication") and event["revision"] not in published:
            unfinished.setdefault(event["revision"], event)
    return list(unfinished.values())


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


def version_descriptors(events: list, revisions: Collection[int]) -> list[dict]:
    """The public stamps whose note names an available immutable revision."""
    mappings = version_revisions(events)
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
    from leaf.revision_artifact import read_revision

    revision = latest_revision(page_dir)
    if revision is None:
        return None
    reading = read_revision(page_dir, revision)
    path = reading.marker
    return document_descriptor(
        revision,
        events,
        url=f"/revisions/{path.name}",
        executable=reading.manifest["executable"],
        activated_at=reading.activated_at,
    )


def document_descriptor(
    revision: int,
    events: list,
    *,
    url: str,
    executable: str,
    activated_at: str,
) -> dict:
    """One revision's live address, public stamp or draft label, and captured identity.

    Filesystem readers supply the immutable marker and capture metadata; the log
    alone determines whether this document is a stamped version or a draft.
    A client compares the executable identity with its delivered document to
    decide whether it needs a fresh document; a new public stamp alone does not.
    """
    return {
        "revision": revision,
        "version": stamped_version(events, revision),
        "url": url,
        "label": revision_label(events, revision),
        # The capture decides executable identity, independently of public stamps.
        "executable": executable,
        "activated_at": activated_at,
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
    return [
        item["version"]
        for item in version_descriptors(events, list_revisions(page_dir))
    ]


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def replace_files(files: list) -> None:
    """Durably stage every write before replacing its target."""
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
        raise Refused("two staged files resolve to the same target")
    replace_bytes(
        [
            (target, data, follow_symlink or not path.is_symlink())
            for (path, data, follow_symlink), target in zip(files, targets, strict=True)
        ]
    )
