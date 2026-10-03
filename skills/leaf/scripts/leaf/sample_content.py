"""Initial histories for disposable samples, read from their captured parent.

A template imports live parent thread closures with `data-sample-threads`, or
names a parent-local inert JSON script with `data-sample-events`. The latter is
an array of ordinary event commands, admitted against the child's initial
document and vocabulary before allocation. It never writes the parent log.
Source validation and allocation use this same construction. Fixtures are
history, not a second state store: subsequent gestures use the ordinary log.
"""

import json
from copy import deepcopy
from pathlib import Path

from .anchor_capture import capture_anchor
from .data_contracts import data_document_errors, initial_data_document_readings
from .event_contracts import admitted_event, command_record_schema
from .event_meaning import AdmissionReadings
from .page_view import InitialPageView
from .projection import generated_children, retirement_outcomes, rewritten_bodies
from .registry.schema import aware_instant, schema_error
from .state import now_iso
from .structure import SourceDocument
from .thread_context import sample_events, thread_structure
from .validation.admission import message_markup_error
from .validation.markup import text_media_errors


def _non_json_number(value: str):
    raise ValueError(f"{value} is not a JSON number")


def _fixture_anchor(anchor: dict, readings: AdmissionReadings) -> dict:
    """Capture an authored target in the child's current page or frozen markup.

    Browser admission receives targets already captured in a rendered document.
    A fixture has no such observation, so the existing file-side capture proves
    its section and passage against the same standing projection instead.
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
    # Context is derived by capture, including the absence of a neighbour at a
    # document edge. A supplied stale prefix or suffix cannot override that proof.
    authored = {
        key: value for key, value in anchor.items() if key not in {"prefix", "suffix"}
    }
    return {**authored, **captured}


def initial_sample_events(
    page_dir: Path,
    parent: SourceDocument,
    parent_events: list,
    template: dict,
    registry: dict,
    contracts: dict,
) -> list[dict]:
    """Construct the child's admitted log without mutating any captured input."""
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
        raise ValueError(
            "use either data-sample-events or data-sample-threads, not both"
        )
    scripts = [
        script
        for script in [*parent.inline_scripts, *parent.external_scripts]
        if script["attrs"].get("id") == reference
    ]
    if not reference or len(scripts) != 1:
        raise ValueError(
            f"data-sample-events {reference!r} must name one script in its parent document"
        )
    script = scripts[0]
    if (
        script["attrs"].get("type", "").strip().lower() != "application/json"
        or "src" in script["attrs"]
    ):
        raise ValueError(
            f"data-sample-events {reference!r} needs an inline application/json script"
        )
    try:
        commands = json.loads(script["body"], parse_constant=_non_json_number)
    except ValueError as error:
        reason = error.msg if isinstance(error, json.JSONDecodeError) else str(error)
        raise ValueError(
            f"data-sample-events {reference!r}: invalid JSON: {reason}"
        ) from error
    if not isinstance(commands, list) or any(
        not isinstance(item, dict) for item in commands
    ):
        raise ValueError(
            f"data-sample-events {reference!r} must contain an array of event objects"
        )
    child = template["document"]
    view = InitialPageView(child, registry, contracts)
    events = []
    kinds = registry["$events"]["kinds"]
    constructed_at = now_iso()
    for seq, command in enumerate(commands, 1):
        try:
            event = deepcopy(command)
            kind = event.get("kind")
            if not isinstance(kind, str) or kind not in kinds:
                raise ValueError(f"kind must be one of {sorted(kinds)}")
            spec = kinds[kind]["record"]
            event.setdefault("id", f"{seq:08x}")
            event.setdefault("ts", constructed_at)
            event.setdefault("author", "user")
            event["seq"] = seq
            if "revision" in spec["properties"]:
                event["revision"] = 1
            # Commands carry no server-derived meaning; validate their remaining
            # shape before admission reads any kind-specific fields.
            if error := schema_error(command_record_schema(kinds[kind]), event):
                raise ValueError(f"{kind} event is invalid: {error}")
            if aware_instant(event["ts"]) is None:
                raise ValueError("ts must be an ISO timestamp with a time zone")
            if any(logged["id"] == event["id"] for logged in events):
                raise ValueError(f"event id {event['id']!r} already exists")
            if event["id"] in child.ids | thread_structure(events).ids:
                raise ValueError(
                    f"event id {event['id']!r} is already a document or message widget id"
                )
            if event.get("anchor"):
                event["anchor"] = _fixture_anchor(
                    event["anchor"], AdmissionReadings(view, events, registry)
                )
            if "text" in event and (
                errors := text_media_errors(event["text"], page_dir)
            ):
                raise ValueError("; ".join(errors))
            if "markup" in event:
                fragment = SourceDocument(event["markup"])
                readings = initial_data_document_readings(
                    child.lf_elements, events, registry
                )
                readings.append(
                    (fragment.lf_elements, f"incoming {kind} markup", registry)
                )
                if error := message_markup_error(
                    page_dir,
                    kind,
                    fragment,
                    events,
                    registry,
                    child,
                    set(),
                    data_document_errors(readings, contracts),
                ):
                    raise ValueError(error)
                if collision := fragment.ids & (
                    {logged["id"] for logged in events} | {event["id"]}
                ):
                    raise ValueError(
                        f"message widget ids already taken by events: {sorted(collision)}"
                    )
            events.append(admitted_event(view, events, event))
        except ValueError as error:
            raise ValueError(
                f"data-sample-events {reference!r}, event {seq}: {error}"
            ) from error
    return events
