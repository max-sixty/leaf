"""Initial histories for disposable samples, read from their captured parent.

A template's holder is the markup it is written in: its parent page's document, or
the frozen markup of a message in that page's log. A template imports live parent
thread closures with `data-sample-threads`, or names an inert JSON script in its
holder with `data-sample-events`. The latter is an array of ordinary event
commands, admitted against the child's initial document and vocabulary before
allocation. It never writes the parent log. Source validation, message admission
and allocation use this same construction. Fixtures are history, not a second
state store: subsequent gestures use the ordinary log.
"""

import json
from copy import deepcopy
from pathlib import Path

from .anchor_capture import capture_anchor
from .data_contracts import data_document_errors, initial_data_document_readings
from .event_contracts import admitted_event, command_error
from .event_log import EventRefused
from .event_meaning import AdmissionReadings
from .findings import Finding, Rejected
from .page_view import InitialPageView
from .projection import generated_children, retirement_outcomes, rewritten_bodies
from .registry.kernel import kernel_event_kinds
from .registry.schema import aware_instant
from .state import now_iso
from .structure import SourceDocument
from .thread_context import sample_events, thread_names, thread_structure
from .validation.admission import message_markup_errors
from .validation.markup import text_media_errors


def _non_json_number(value: str):
    raise ValueError(f"{value} is not a JSON number")


def _refused(code: str, reference: str, **values) -> Rejected:
    """The refusal of a sample's history, as the one finding that says why:
    `reference` is the script its template names, and `values` what was read there."""
    return Rejected([Finding(code, values={"reference": reference, **values})])


def _fixture_anchor(anchor: dict, readings: AdmissionReadings) -> dict:
    """Capture an authored target in the child's current page or frozen markup.

    Browser admission receives targets already captured in a rendered document.
    A fixture has no such observation, so the existing file-side capture proves
    its section and passage against the same current projection instead.
    """
    page = readings.page(1)
    document, projection = page.document, page.projection
    section = anchor.get("section") or ""
    thread = readings.thread
    created_in_thread = {
        child["id"]: owner
        for owner, children in generated_children(
            thread.projection.desired, thread.structure.ids
        ).items()
        for child in children
    }
    target = created_in_thread.get(section, section)
    if target in thread.structure.ids:
        document = next(
            fragment
            for fragment in thread.structure.fragments.values()
            if target in fragment.ids
        )
        projection = thread.projection
    captured = capture_anchor(
        document,
        readings.registry,
        # A datum's displayed words come from its module, not authored text.
        # Its section is still captured here; admission checks its data binding.
        "" if "datum" in anchor else anchor.get("quote", ""),
        section,
        retirement_outcomes(projection.actions),
        rewritten_bodies(projection.actions),
        anchor.get("visual"),
        additions=generated_children(projection.desired, document.ids),
    )
    # File capture proves a unique passage and derives its context, including absent
    # neighbours. Supplied context or uncertainty cannot override that observation.
    authored = {
        key: value
        for key, value in anchor.items()
        if key not in {"prefix", "suffix", "detached"}
    }
    return {**authored, **captured}


def initial_sample_events(
    page_dir: Path,
    parent: SourceDocument,
    parent_events: list,
    holder: SourceDocument,
    template: dict,
    registry: dict,
    contracts: dict,
) -> list[dict]:
    """Construct the child's admitted log without mutating any captured input.

    `parent` is the document `parent_events` is the log of, and `holder` the markup
    declaring `template`: `parent` itself, or one of its log's messages."""
    attrs = template["attrs"]
    reference = attrs.get("data-sample-events")
    if "data-sample-events" not in attrs:
        selected = set(attrs.get("data-sample-threads", "").split())
        return [
            {**event, "seq": seq}
            for seq, event in enumerate(
                sample_events(parent, parent_events, selected), 1
            )
        ]
    if "data-sample-threads" in attrs:
        raise Rejected([Finding("sample-source-both")])
    scripts = [
        script
        for script in [
            *holder.authoring.inline_scripts,
            *holder.authoring.external_scripts,
        ]
        if script["attrs"].get("id") == reference
    ]
    if not reference or len(scripts) != 1:
        raise _refused("sample-script", reference)
    script = scripts[0]
    if (
        script["attrs"].get("type", "").strip().lower() != "application/json"
        or "src" in script["attrs"]
    ):
        raise _refused("sample-script-type", reference)
    try:
        commands = json.loads(script["body"], parse_constant=_non_json_number)
    except ValueError as error:
        reason = error.msg if isinstance(error, json.JSONDecodeError) else str(error)
        raise _refused("sample-json", reference, error=reason) from error
    if not isinstance(commands, list) or any(
        not isinstance(item, dict) for item in commands
    ):
        raise _refused("sample-array", reference)
    child = template["document"]
    view = InitialPageView(child, registry, contracts)
    events = []
    kinds = kernel_event_kinds()
    constructed_at = now_iso()
    for seq, command in enumerate(commands, 1):
        try:
            event = deepcopy(command)
            if "publication" in event:
                raise _refused("fixture-publication", reference, event=seq)
            kind = event.get("kind")
            if not isinstance(kind, str) or kind not in kinds:
                raise _refused(
                    "fixture-kind", reference, event=seq, kinds=sorted(kinds)
                )
            spec = kinds[kind]["record"]
            event.setdefault("id", f"{seq:08x}")
            event.setdefault("ts", constructed_at)
            event.setdefault("author", "user")
            event["seq"] = seq
            if "revision" in spec["properties"]:
                event["revision"] = 1
            if error := command_error(event, kinds):
                raise _refused(
                    "fixture-event",
                    reference,
                    event=seq,
                    findings=[error.json(text=False)],
                )
            if aware_instant(event["ts"]) is None:
                raise _refused("fixture-ts", reference, event=seq)
            if any(logged["id"] == event["id"] for logged in events):
                raise _refused(
                    "fixture-id-repeated", reference, event=seq, id=event["id"]
                )
            if event["id"] in child.ids | thread_structure(events).ids:
                raise _refused("fixture-id-taken", reference, event=seq, id=event["id"])
            if event.get("anchor"):
                event["anchor"] = _fixture_anchor(
                    event["anchor"], AdmissionReadings(view, events, registry)
                )
            if "text" in event and (
                errors := text_media_errors(event["text"], page_dir)
            ):
                raise _refused(
                    "fixture-media",
                    reference,
                    event=seq,
                    findings=[found.json(text=False) for found in errors],
                )
            if "markup" in event:
                fragment = SourceDocument(event["markup"])
                readings = initial_data_document_readings(child, events, registry)
                readings.append(
                    (fragment.lf_elements, f"incoming {kind} markup", registry)
                )
                if errors := message_markup_errors(
                    page_dir,
                    fragment,
                    events,
                    registry,
                    child,
                    set(),
                    data_document_errors(readings),
                    contracts,
                    event["id"]
                    if kind == "comment"
                    else thread_names(events).get(event.get("parent")),
                ):
                    raise _refused(
                        "fixture-markup",
                        reference,
                        event=seq,
                        kind=kind,
                        findings=[found.json(text=False) for found in errors],
                    )
                if collision := fragment.ids & (
                    {logged["id"] for logged in events} | {event["id"]}
                ):
                    raise _refused(
                        "fixture-ids-taken", reference, event=seq, ids=sorted(collision)
                    )
            events.append(admitted_event(view, events, event))
        except EventRefused as error:
            raise _refused(
                "fixture-event",
                reference,
                event=seq,
                findings=[found.json(text=False) for found in error.findings],
            ) from error
        except ValueError as error:
            # The anchor capture's own refusal, in its words.
            raise _refused(
                "fixture-refused", reference, event=seq, error=str(error)
            ) from error
    return events
