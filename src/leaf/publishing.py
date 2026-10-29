"""Stamping public version mappings from the mutable source.

A stamp of the source in place checks it before taking the page transaction, so
a state read that activates the same save meanwhile never waits on that check,
and holds the transaction only to confirm and publish. Under it the stamp
compares the page's source and history readings with those it took before
checking (`served_state.reading.source_readings`, the readings activation keys
on). A write that lands during the check moves a reading, so equal readings mean
the check read what the transaction now holds; when one moved, the stamp checks
again (`_stamp_in_place`).

An authored replacement supplies HTML and its complete page-owned resource tree.
Installing, validating, stamping and restoring a refused replacement share the
page transaction, so automatic HTTP activation cannot publish an intermediate
combination, and its check runs under that transaction. A source digest refuses
a replacement prepared against other inputs.
"""

import hashlib
import json
from pathlib import Path

from leaf.event_log import read_events
from leaf.files import stamped_version
from leaf.leases import contract_writer
from leaf.projection import folded_value, markup_value, page_reading
from leaf.refusals import Refused
from leaf.revisioning import (
    hold_published,
    planned_activation,
    publish_checked_event,
)
from leaf.served_state.reading import source_readings
from leaf.service import PageTransaction
from leaf.todos import TodoReading
from leaf.validation.admission import checked_text
from leaf.validation.source import check_source

# How many checks a stamp in place runs outside the page transaction before it
# checks under it, so a page written faster than it checks still gets a stamp.
UNLOCKED_CHECKS = 2


def authored_files(source: Path, companions: Path) -> dict[str, bytes]:
    """Read present mutable authored inputs, keyed inside a page directory.

    A missing source remains identifiable so an agent can read and repair it.
    Publication validates that the replacement has a complete, valid document.
    """
    try:
        document = {"index.html": source.read_bytes()}
    except FileNotFoundError:
        document = {}
    return {
        **document,
        **{
            "page/" + path.relative_to(companions).as_posix(): path.read_bytes()
            for path in sorted(companions.rglob("*"))
            if path.is_file()
        },
    }


def authored_digest(files: dict[str, bytes]) -> str:
    """Identify the exact HTML and companion paths and bytes a writer read."""
    manifest = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
    }
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def write_authored_files(
    page: Path, incoming: dict[str, bytes], previous: dict[str, bytes]
) -> None:
    """Replace mutable authoring inputs; captured revisions remain untouched.

    The publication caller holds a page transaction. Removing empty directories
    permits a module file to replace a directory of modules, and the reverse.
    """
    for name in previous.keys() - incoming.keys():
        (page / name).unlink()
    directories = (path for path in (page / "page").rglob("*") if path.is_dir())
    for directory in sorted(
        directories, key=lambda path: len(path.parts), reverse=True
    ):
        if not any(directory.iterdir()):
            directory.rmdir()
    for name, data in incoming.items():
        if previous.get(name) != data:
            target = page / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def _stamp_reading(events: list, checked, revision: int):
    if existing := stamped_version(events, revision):
        raise Refused(f"revision r{revision} is already stamped as v{existing}")
    registry = checked.registry
    if registry is None:
        raise Refused("refusing to stamp index.html: the page has no registry.json")
    page = page_reading(checked.reading, events, revision)
    return registry, page.projection, page.document, page.spoken


def _completed_tasks(
    events: list,
    revision: int,
    completes: tuple[str, ...],
) -> list[str]:
    """End only the open widget to-dos explicitly named by ``completes``.

    Removing a target leaves its to-do open on the agent's list; a page edit does not
    establish that the to-do is complete.
    """
    if len(set(completes)) != len(completes):
        raise Refused("--completes names each widget at most once")
    todos = TodoReading(events).owed
    on_widgets = [todo for todo in todos if todo["subject"]["kind"] == "widget"]
    unearned = sorted(set(completes) - {todo["subject"]["id"] for todo in on_widgets})
    if unearned:
        # An author who has just recorded a user's answer on a widget, such as a
        # playground's submitted settings, reaches for --completes to finish it; the
        # version that records an answer takes it in by itself.
        mine = "; ".join(
            f"{todo['id']} on {todo['subject'].get('id') or todo['subject']['kind']}"
            f" ({todo['title']})"
            for todo in todos
        )
        raise Refused(
            "no open to-do on "
            + ", ".join(repr(widget) for widget in unearned)
            + ": --completes ends the agent's own to-dos opened on a widget, and "
            + (f"the open ones are {mine}" if todos else "none is open")
            + ". A user's answer on a widget needs no --completes: the version that"
            " records it takes it in; end a to-do on the page with `leaf task end`"
        )
    completed = [todo for todo in on_widgets if todo["subject"]["id"] in completes]
    not_later = sorted(
        {todo["subject"]["id"] for todo in completed if revision <= todo["revision"]}
    )
    if not_later:
        raise Refused(
            f"revision r{revision} is not later than the open to-do on "
            + ", ".join(repr(widget) for widget in not_later)
        )
    return sorted(todo["id"] for todo in completed)


def _settled_reports(projection, parser, spk: dict, registry: dict) -> list[str]:
    settled = []
    for (_widget, unit, _verb), reports in projection.reports.items():
        last, spec = reports[-1]
        if unit in parser.overruled or markup_value(
            unit, spec, parser.by_id, spk, registry
        ) == folded_value(last, spec):
            settled.extend(report["id"] for report, _ in reports)
    return settled


def _stamp_event(
    body: str,
    version: int,
    revision: int,
    parser,
    settled_reports: list[str],
    completed: list[str],
) -> dict:
    event = {
        "kind": "note",
        "author": "agent",
        "version": version,
        "revision": revision,
        "text": body,
    }
    if parser.restated:
        event["restated"] = sorted(parser.restated)
    settlements = [
        *({"kind": "report", "id": identity} for identity in sorted(settled_reports)),
        *({"kind": "todo", "id": identity} for identity in completed),
    ]
    if settlements:
        event["settles"] = settlements
    return event


def _checked(page_dir: Path, events: list | None = None) -> tuple[tuple, object]:
    """Check the source, with the source and history readings taken before the
    check (`source_readings`), the readings activation keys its answer on."""
    readings = source_readings(page_dir)
    return readings, check_source(
        page_dir, read_events(page_dir) if events is None else events
    )


def _stamp_locked(
    page_dir: Path, page, readings, checked, body: str, completes: tuple[str, ...]
) -> dict:
    """Map `checked`, a check of what `page`'s transaction holds, to a version.
    `readings` are those taken before that check."""
    if checked.errors:
        raise Refused(
            f"refusing to stamp index.html: {'; '.join(map(str, checked.errors))}"
        )
    events = page.events
    activation = planned_activation(page_dir, checked)
    revision = activation.revision
    assert revision is not None
    registry, projection, parser, spk = _stamp_reading(events, checked, revision)
    completed = _completed_tasks(events, revision, completes)
    settled_reports = _settled_reports(projection, parser, spk, registry)
    notes = [event for event in events if event["kind"] == "note"]
    version = max((event["version"] for event in notes), default=0) + 1
    event = _stamp_event(body, version, revision, parser, settled_reports, completed)
    # Stamp-specific refusals precede publication. The publisher admits this
    # note and every anchor move it requires before the revision marker.
    accepted = publish_checked_event(page, checked, event)
    source, _history = readings
    hold_published(page_dir, source, activation)
    return accepted


def _stamp_in_place(page_dir: Path, body: str, completes: tuple[str, ...]) -> dict:
    """Check the source outside the transaction, then publish under it if nothing
    moved. The page's own activation of the save usually lands during the first
    check, so a second one runs outside it too; the last checks under it."""
    for _ in range(UNLOCKED_CHECKS):
        readings, checked = _checked(page_dir)
        with PageTransaction(page_dir) as page:
            if source_readings(page_dir) == readings:
                return _stamp_locked(page_dir, page, readings, checked, body, completes)
    with PageTransaction(page_dir) as page:
        readings, checked = _checked(page_dir, page.events)
        return _stamp_locked(page_dir, page, readings, checked, body, completes)


@contract_writer
def cmd_stamp(
    page_dir: Path,
    text,
    completes: tuple[str, ...] = (),
    *,
    replace: tuple[Path, str] | None = None,
) -> dict:
    """Map the exact current source to the next public version. `replace`, a
    candidate directory and the authored digest it was prepared against, first
    swaps in the candidate's index.html and page/ tree, refusing if the source
    no longer has that digest."""
    body = checked_text(page_dir, text)
    if replace is None:
        return _stamp_in_place(page_dir, body, completes)
    candidate, digest = replace
    incoming = authored_files(candidate / "index.html", candidate / "page")
    with PageTransaction(page_dir) as page:
        previous = authored_files(page_dir / "index.html", page_dir / "page")
        if authored_digest(previous) != digest:
            raise Refused("authored inputs changed; reconcile them before retrying")
        try:
            write_authored_files(page_dir, incoming, previous)
            readings, checked = _checked(page_dir, page.events)
            return _stamp_locked(page_dir, page, readings, checked, body, completes)
        except BaseException:
            write_authored_files(
                page_dir,
                previous,
                authored_files(page_dir / "index.html", page_dir / "page"),
            )
            raise
