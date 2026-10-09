"""Stamping public version mappings from the mutable source.

An authored replacement supplies HTML and its complete page-owned resource tree.
Installing, validating, stamping and restoring a refused replacement share the
page transaction, so automatic HTTP activation cannot publish an intermediate
combination. A source digest refuses a replacement prepared against other inputs.
"""

import hashlib
import json
import sys
from pathlib import Path

from leaf.files import stamped_version
from leaf.harness import message_identity
from leaf.leases import contract_writer
from leaf.projection import folded_value, markup_value, page_reading
from leaf.revisioning import planned_activation, publish_checked_event
from leaf.service import PageTransaction
from leaf.tasks import owed_tasks
from leaf.validation.admission import read_text_arg
from leaf.validation.source import check_source


def authored_files(source: Path, companions: Path) -> dict[str, bytes]:
    """Read complete mutable authored inputs, keyed inside a page directory."""
    return {
        "index.html": source.read_bytes(),
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


def _stamp_candidate(page_dir: Path, events: list):
    """Check the exact source and determine its revision without publishing it."""
    checked = check_source(page_dir, events)
    if checked.errors:
        sys.exit(f"refusing to stamp index.html: {'; '.join(checked.errors)}")
    return checked, planned_activation(page_dir, checked)


def _stamp_reading(events: list, checked, revision: int):
    if existing := stamped_version(events, revision):
        sys.exit(f"revision r{revision} is already stamped as v{existing}")
    registry = checked.registry
    if registry is None:
        sys.exit("refusing to stamp index.html: the page has no registry.json")
    page = page_reading(checked.reading, events, revision)
    return registry, page.projection, page.document, page.spoken


def _completed_tasks(
    events: list,
    revision: int,
    completes: tuple[str, ...],
) -> list[str]:
    """End only the open widget tasks explicitly named by ``completes``.

    Removing a target leaves its task open in the queue; a page edit does not
    establish that the task is complete.
    """
    if len(set(completes)) != len(completes):
        sys.exit("--completes names each widget at most once")
    tasks = owed_tasks(events)
    on_widgets = [task for task in tasks if task["subject"]["kind"] == "widget"]
    unearned = sorted(set(completes) - {task["subject"]["id"] for task in on_widgets})
    if unearned:
        sys.exit("no open task on " + ", ".join(repr(widget) for widget in unearned))
    completed = [task for task in on_widgets if task["subject"]["id"] in completes]
    not_later = sorted(
        {task["subject"]["id"] for task in completed if revision <= task["revision"]}
    )
    if not_later:
        sys.exit(
            f"revision r{revision} is not later than the open task on "
            + ", ".join(repr(widget) for widget in not_later)
        )
    return sorted(task["id"] for task in completed)


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
        **message_identity(),
        "version": version,
        "revision": revision,
        "text": body,
    }
    if parser.restated:
        event["restated"] = sorted(parser.restated)
    settlements = [
        *({"kind": "report", "id": identity} for identity in sorted(settled_reports)),
        *({"kind": "task", "id": identity} for identity in completed),
    ]
    if settlements:
        event["settles"] = settlements
    return event


def _stamp_locked(page_dir: Path, page, body: str, completes: tuple[str, ...]) -> dict:
    events = page.events
    checked, activation = _stamp_candidate(page_dir, events)
    revision = activation.revision
    registry, projection, parser, spk = _stamp_reading(events, checked, revision)
    completed = _completed_tasks(events, revision, completes)
    settled_reports = _settled_reports(projection, parser, spk, registry)
    notes = [event for event in events if event["kind"] == "note"]
    version = max((event["version"] for event in notes), default=0) + 1
    event = _stamp_event(body, version, revision, parser, settled_reports, completed)
    # Stamp-specific refusals precede publication. The publisher preflights this
    # note's effects, then journals it and every anchor move before the marker.
    return publish_checked_event(page, checked, event)


@contract_writer
def cmd_stamp(
    page_dir: Path,
    text,
    completes: tuple[str, ...] = (),
    *,
    from_directory: Path | None = None,
    if_source: str | None = None,
) -> dict:
    """Map the exact current source to the next public version."""
    body = read_text_arg(page_dir, text)
    if (from_directory is None) != (if_source is None):
        sys.exit("--from-directory and --if-source are used together")
    incoming = (
        authored_files(from_directory / "index.html", from_directory / "page")
        if from_directory is not None
        else None
    )
    with PageTransaction(page_dir) as page:
        if incoming is None:
            return _stamp_locked(page_dir, page, body, completes)
        previous = authored_files(page_dir / "index.html", page_dir / "page")
        if authored_digest(previous) != if_source:
            sys.exit("authored inputs changed; reconcile them before retrying")
        try:
            write_authored_files(page_dir, incoming, previous)
            return _stamp_locked(page_dir, page, body, completes)
        except BaseException:
            write_authored_files(
                page_dir,
                previous,
                authored_files(page_dir / "index.html", page_dir / "page"),
            )
            raise
