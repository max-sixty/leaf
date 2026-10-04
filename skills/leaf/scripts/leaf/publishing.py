"""Stamping public version mappings from the mutable source."""

import sys
from pathlib import Path

from leaf.files import stamped_version
from leaf.host import message_identity
from leaf.leases import contract_writer
from leaf.projection import folded_value, markup_value, page_reading
from leaf.revisioning import planned_activation, publish_checked_event
from leaf.service import PageTransaction
from leaf.tasks import open_tasks
from leaf.validation.admission import read_text_arg
from leaf.validation.source import check_source
from leaf.work import widget_tasks_without_targets


def _stamp_candidate(page_dir: Path, events: list):
    """Check the exact source and determine its revision without publishing it."""
    checked = check_source(page_dir, events, allow_transition=True)
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
    checked,
    projection,
    events: list,
    registry: dict,
    revision: int,
    completes: tuple[str, ...],
) -> list[str]:
    """The open tasks this version ends `done`: every task on each widget `completes`
    names. A version that would drop the target of an open widget task it does not
    complete is refused, since the task would stand beside nothing."""
    if len(set(completes)) != len(completes):
        sys.exit("--completes names each widget at most once")
    tasks = open_tasks(events)
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
    untargeted = widget_tasks_without_targets(
        checked.document, projection, tasks, registry, completes
    )
    if untargeted:
        widgets = ", ".join(repr(widget) for widget in untargeted)
        sys.exit(
            "refusing to stamp index.html: it would remove the target of the open "
            f"task on {widgets}; pass --completes for each widget this version "
            "completes, or end the task with `leaf task end`"
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
    completed = _completed_tasks(
        checked, projection, events, registry, revision, completes
    )
    settled_reports = _settled_reports(projection, parser, spk, registry)
    notes = [event for event in events if event["kind"] == "note"]
    version = max((event["version"] for event in notes), default=0) + 1
    event = _stamp_event(body, version, revision, parser, settled_reports, completed)
    # Stamp-specific refusals precede publication. The publisher preflights this
    # note's effects, then journals it and every anchor move before the marker.
    return publish_checked_event(page, checked, event)


@contract_writer
def cmd_stamp(page_dir: Path, text, completes: tuple[str, ...] = ()) -> dict:
    """Map the exact current source to the next public version."""
    body = read_text_arg(page_dir, text)
    with PageTransaction(page_dir) as page:
        return _stamp_locked(page_dir, page, body, completes)
