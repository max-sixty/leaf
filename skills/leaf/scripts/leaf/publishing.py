"""Stamping immutable public versions from the mutable source."""

import json
import sys
from pathlib import Path

from leaf.files import (
    replace_files,
    revision_path,
    stamped_version,
    version_path,
)
from leaf.host import message_identity
from leaf.leases import contract_writer
from leaf.projection import folded_facet, markup_facet, page_projection
from leaf.revisioning import activate_source
from leaf.service import PageTransaction
from leaf.validation.admission import read_text_arg
from leaf.work import standing_work_claims, widget_work_without_targets


def _stamp_activation(page_dir: Path, events: list):
    activation = activate_source(page_dir, events, allow_transition=True)
    if activation.error or activation.revision is None:
        detail = activation.error or "index.html produced no revision"
        sys.exit(f"refusing to stamp index.html: {detail}")
    return activation


def _stamp_reading(events: list, activation):
    revision = activation.revision
    if existing := stamped_version(events, revision):
        sys.exit(f"revision r{revision} is already stamped as v{existing}")
    checked = activation.check
    registry = checked.registry
    if registry is None:
        sys.exit("refusing to stamp index.html: the page has no registry.json")
    projection, parser, spk = page_projection(checked.html, events, registry, revision)
    return checked, registry, projection, parser, spk


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
        checked.html,
        parser,
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
    for (_widget, unit, _facet), reports in projection.reports.items():
        last, spec = reports[-1]
        if unit in parser.overruled or markup_facet(
            unit, spec, parser.by_id, spk, registry
        ) == folded_facet(last, spec):
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
        "author": "claude",
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
    activation = _stamp_activation(page_dir, events)
    revision = activation.revision
    created_revision = revision_path(page_dir, revision) if activation.created else None
    created_version = None
    committed = False
    try:
        checked, registry, projection, parser, spk = _stamp_reading(events, activation)

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
        created_version = version_path(page_dir, version)
        # A crash before the note may leave an unnoted file. The note is the
        # commit marker, so that orphan is safe to regenerate under this lease.
        created_version.unlink(missing_ok=True)
        replace_files([(created_version, checked.data, False)])

        event = _stamp_event(
            body, version, revision, parser, settled_reports, completed
        )
        accepted = page.append_event(event)
        committed = True
        return accepted
    finally:
        if not committed:
            if created_version is not None:
                created_version.unlink(missing_ok=True)
            if created_revision is not None:
                created_revision.unlink(missing_ok=True)


@contract_writer
def cmd_stamp(page_dir: Path, text, completes: tuple[str, ...] = ()) -> None:
    """Stamp the exact current source as the next immutable public version."""
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        accepted = _stamp_locked(page_dir, page, body, completes)
    print(json.dumps(accepted, ensure_ascii=False))
