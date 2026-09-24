"""Stamping public version mappings from the mutable source."""

import sys
from pathlib import Path

from leaf.event_contracts import append_admitted
from leaf.files import (
    revision_path,
    stamped_version,
)
from leaf.host import message_identity
from leaf.leases import contract_writer
from leaf.projection import folded_value, markup_value, page_reading
from leaf.revisioning import activate_checked_source
from leaf.service import PageTransaction
from leaf.validation.admission import read_text_arg
from leaf.validation.source import check_source
from leaf.work import standing_work_claims, widget_work_without_targets


def _stamp_activation(page_dir: Path, events: list):
    """Check the exact source against the standing log, then activate it."""
    checked = check_source(page_dir, events, allow_transition=True)
    if checked.errors:
        sys.exit(f"refusing to stamp index.html: {'; '.join(checked.errors)}")
    return checked, activate_checked_source(page_dir, checked)


def _stamp_reading(events: list, checked, revision: int):
    if existing := stamped_version(events, revision):
        sys.exit(f"revision r{revision} is already stamped as v{existing}")
    registry = checked.registry
    if registry is None:
        sys.exit("refusing to stamp index.html: the page has no registry.json")
    page = page_reading(checked.document, events, registry, revision)
    return registry, page.projection, page.document, page.spoken


def _completed_work(
    checked,
    parser,
    projection,
    events: list,
    page,
    registry: dict,
    revision: int,
    completes: tuple[str, ...],
) -> set[str]:
    if len(set(completes)) != len(completes):
        sys.exit("--completes names each widget at most once")
    completed = set(completes)
    widget_work = {
        claim["subject"]["id"]: claim
        for claim in standing_work_claims(page.status, events)
        if claim["subject"]["kind"] == "widget"
    }
    unearned = sorted(completed - widget_work.keys())
    if unearned:
        sys.exit(
            "no active widget work claim for "
            + ", ".join(repr(widget) for widget in unearned)
        )
    not_later = sorted(
        widget for widget in completed if revision <= widget_work[widget]["revision"]
    )
    if not_later:
        sys.exit(
            f"revision r{revision} is not later than the active widget work claim for "
            + ", ".join(repr(widget) for widget in not_later)
        )
    untargeted = widget_work_without_targets(
        checked.document,
        projection,
        events,
        page.status,
        registry,
        completed,
    )
    if untargeted:
        widgets = ", ".join(repr(widget) for widget in untargeted)
        sys.exit(
            "refusing to stamp index.html: it would remove the local target "
            f"for active work on {widgets}; pass --completes for each widget "
            "this version completes"
        )
    return completed


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
    completed: set[str],
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
        *({"kind": "work", "id": identity} for identity in sorted(completed)),
    ]
    if settlements:
        event["settles"] = settlements
    return event


def _stamp_locked(page_dir: Path, page, body: str, completes: tuple[str, ...]) -> dict:
    events = page.events
    checked, activation = _stamp_activation(page_dir, events)
    revision = activation.revision
    created_revision = revision_path(page_dir, revision) if activation.created else None
    committed = False
    try:
        registry, projection, parser, spk = _stamp_reading(events, checked, revision)

        completed = _completed_work(
            checked,
            parser,
            projection,
            events,
            page,
            registry,
            revision,
            completes,
        )
        settled_reports = _settled_reports(projection, parser, spk, registry)

        notes = [event for event in events if event["kind"] == "note"]
        version = max((event["version"] for event in notes), default=0) + 1
        event = _stamp_event(
            body, version, revision, parser, settled_reports, completed
        )
        accepted = append_admitted(page, event)
        committed = True
        return accepted
    finally:
        if not committed and created_revision is not None:
            created_revision.unlink(missing_ok=True)


@contract_writer
def cmd_stamp(page_dir: Path, text, completes: tuple[str, ...] = ()) -> dict:
    """Map the exact current source to the next public version."""
    body = read_text_arg(page_dir, text)
    with PageTransaction(page_dir) as page:
        return _stamp_locked(page_dir, page, body, completes)
