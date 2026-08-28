"""Stamping immutable public versions from the mutable source."""

import json
import sys
from pathlib import Path

from leaf.event_log import append_event
from leaf.files import (
    replace_files,
    revision_path,
    stamped_version,
    version_path,
)
from leaf.host import message_identity
from leaf.projection import folded_facet, markup_facet, page_projection
from leaf.revisioning import activate_source
from leaf.service import PageTransaction, contract_writer
from leaf.validation import read_text_arg
from leaf.work import (
    standing_work_claims,
    widget_work_without_seats,
    work_claim_revision,
)


def _stamp_locked(page_dir: Path, page, body: str, completes: tuple[str, ...]) -> dict:
    events = page.events
    activation = activate_source(page_dir, events, allow_transition=True)
    if activation.error or activation.revision is None:
        detail = activation.error or "index.html produced no revision"
        sys.exit(f"refusing to stamp index.html: {detail}")

    revision = activation.revision
    created_revision = revision_path(page_dir, revision) if activation.created else None
    created_version = None
    committed = False
    try:
        if existing := stamped_version(events, revision):
            sys.exit(f"revision r{revision} is already stamped as v{existing}")

        checked = activation.check
        registry = checked.registry
        if registry is None:
            sys.exit("refusing to stamp index.html: the page has no registry.json")
        projection, parser, spk = page_projection(
            checked.html, events, registry, revision
        )

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
            widget
            for widget in completed
            if revision <= work_claim_revision(widget_work[widget], events)
        )
        if not_later:
            sys.exit(
                f"revision r{revision} is not later than the active widget work claim for "
                + ", ".join(repr(widget) for widget in not_later)
            )
        unseated = widget_work_without_seats(
            checked.html,
            parser,
            projection,
            events,
            page.status,
            registry,
            completed,
        )
        if unseated:
            widgets = ", ".join(repr(widget) for widget in unseated)
            sys.exit(
                "refusing to stamp index.html: it would remove the local seat "
                f"for active work on {widgets}; pass --completes for each widget "
                "this version completes"
            )

        settled_reports = []
        for (_widget, unit, _facet), reports in projection.reports.items():
            last, spec = reports[-1]
            if unit in parser.overruled or markup_facet(
                unit, spec, parser.by_id, spk, registry
            ) == folded_facet(last, spec):
                settled_reports.extend(report["id"] for report, _ in reports)

        notes = [event for event in events if event["kind"] == "note"]
        version = max((event["version"] for event in notes), default=0) + 1
        created_version = version_path(page_dir, version)
        # A crash before the note may leave an unnoted file. The note is the
        # commit marker, so that orphan is safe to regenerate under this lease.
        created_version.unlink(missing_ok=True)
        replace_files([(created_version, checked.data, False)])

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
            *(
                {"kind": "report", "id": identity}
                for identity in sorted(settled_reports)
            ),
            *({"kind": "work", "id": identity} for identity in sorted(completed)),
        ]
        if settlements:
            event["settles"] = settlements
        accepted = append_event(page, event)
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
