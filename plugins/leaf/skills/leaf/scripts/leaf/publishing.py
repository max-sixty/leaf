"""Version publication and event-log settlement."""

import json
import sys
from pathlib import Path

from leaf.checking import cmd_check
from leaf.events import append_event, standing_work_claims, work_claim_version
from leaf.files import version_name, version_path
from leaf.projection import folded_facet, markup_facet, page_projection
from leaf.registry import load_registry
from leaf.service import PageTransaction, contract_writer, message_identity
from leaf.validation import read_text_arg
from leaf.work import widget_work_without_seats


@contract_writer
def cmd_publish(
    page_dir: Path, version: int, text, completes: tuple[str, ...] = ()
) -> None:
    name = version_name(version)
    path = version_path(page_dir, version)
    if not path.is_file():
        sys.exit(
            f"no v{version}.html in {page_dir / 'versions'}; write the version file first"
        )
    body = read_text_arg(text)
    # Validation, projection, and append share the contract transition held by
    # the decorator and this page transaction. A report therefore lands either
    # before the note and may be answered by it, or after it on the new version.
    with PageTransaction(page_dir) as page:
        events = page.events
        if (
            cmd_check(
                page_dir,
                version,
                transition_held=True,
                events_override=events,
            )
            != 0
        ):
            sys.exit(
                f"refusing to publish {name}: leaf version check failed (issues above)"
            )
        html = path.read_text(encoding="utf-8")
        registry = load_registry(page_dir)
        projection, parser, spk = page_projection(html, events, registry, version)
        retracts = sorted(parser.restated)
        byid = parser.by_id
        if len(set(completes)) != len(completes):
            sys.exit("--completes names each widget at most once")
        completed = set(completes)
        widget_work = {
            claim["subject"]["id"]: claim
            for claim in standing_work_claims(
                page.status, events, include_resolved=True
            )
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
            if version <= work_claim_version(widget_work[widget], events)
        )
        if not_later:
            sys.exit(
                f"v{version} is not later than the active widget work claim for "
                + ", ".join(repr(widget) for widget in not_later)
            )
        unseated = widget_work_without_seats(
            html, parser, projection, events, page.status, registry, completed
        )
        if unseated:
            widgets = ", ".join(repr(widget) for widget in unseated)
            sys.exit(
                f"refusing to publish {name}: it would remove the local seat "
                f"for active work on {widgets}; pass --completes for each widget "
                "this version completes"
            )
        settled_reports = []
        for (_widget, unit, _facet), reports in projection.reports.items():
            last, spec = reports[-1]
            if unit in parser.overruled or markup_facet(
                unit, spec, byid, spk, registry
            ) == folded_facet(last, spec):
                settled_reports.extend(report["id"] for report, _ in reports)
        event = {
            "kind": "note",
            "author": "claude",
            **message_identity(),
            "version": version,
            "text": body,
        }
        if retracts:
            event["restated"] = retracts
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
    print(json.dumps(accepted, ensure_ascii=False))
