"""Durable one-shot requests and their terminal host receipts."""

import json
import sys
from pathlib import Path

from .asks import quoted_in
from .host import message_identity
from .leases import contract_writer
from .registry.contract import schema_error
from .service import PageTransaction
from .structure import parse_revision
from .thread_context import thread_structure
from .validation.admission import read_text_arg
from .validation.instances import reference_contract_error


def request_lifecycle(events: list, *, widget: str, document: dict) -> dict:
    """The canonical lifecycle at one request seat over this event prefix."""
    receipts = {
        event["request"]: event for event in events if event["kind"] == "receipt"
    }
    attempts = []
    for event in events:
        if (
            event["kind"] != "request"
            or event["widget"] != widget
            or event["meaning"]["document"] != document
        ):
            continue
        attempts.append({"request": event, "receipt": receipts.get(event["id"])})
    latest = attempts[-1] if attempts else None
    phase = "ready"
    if latest and latest["receipt"] is None:
        phase = "pending"
    elif latest and latest["receipt"]["status"] == "succeeded":
        phase = "completed"
    return {
        "seat": {"document": document, "widget": widget},
        "attempts": attempts,
        "latest": latest,
        "phase": phase,
    }


def request_lifecycles_for(
    events: list, elements: list[dict], registry: dict, document: dict
) -> list[dict]:
    """Every declared request seat in one document, occupied or ready."""
    widgets = dict.fromkeys(
        record["attrs"]["id"]
        for record in elements
        if (registry.get(record["tag"]) or {}).get("x-request")
    )
    return [
        request_lifecycle(events, widget=widget, document=document)
        for widget in widgets
    ]


def request_phases(lifecycles: list[dict]) -> dict[str, str]:
    """Request holder id → canonical reader/host lifecycle phase."""
    return {lifecycle["seat"]["widget"]: lifecycle["phase"] for lifecycle in lifecycles}


def request_document(event: dict, page, thread):
    """The request's sender and the one document that contains its offers."""
    if record := page.by_id.get(event["widget"]):
        return record, page.lf_elements, "page"
    for fragment in thread.fragments.values():
        if record := fragment.by_id.get(event["widget"]):
            return record, fragment.lf_elements, "thread"
    return None, (), None


def declared_request_error(event: dict, page, thread, registry: dict) -> str | None:
    """Why a stored one-shot request violates its sending widget contract."""
    record, elements, _scope = request_document(event, page, thread)
    if record is None:
        return (
            f"unknown request widget {event['widget']!r} in revision "
            f"r{event['revision']} or agent-authored thread markup"
        )
    tag = record["tag"]
    entry = registry.get(tag)
    if entry is None:
        return (
            f"registry no longer declares <{tag}> for request widget "
            f"{event['widget']!r}"
        )
    request = entry.get("x-request", {})
    verbs = request.get("verbs", {})
    spec = verbs.get(event["action"])
    if spec is None:
        return f"<{tag}> does not declare request verb {event['action']!r}"
    if message := schema_error(spec["detail"], event["detail"]):
        return f"<{tag}> request {event['action']!r} detail is invalid: {message}"
    targets = {**page.by_id, **thread.by_id}
    for attribute in entry.get("x-refers", {}):
        target = record["attrs"].get(attribute)
        if not target:
            continue
        target_record = targets.get(target)
        if target_record is None:
            return f'<{tag}> {attribute}="{target}" names no available element'
        if error := reference_contract_error(
            record, attribute, target_record, registry
        ):
            return error
    offered = {
        candidate["attrs"][request["offers"][candidate["tag"]]]
        for candidate in elements
        if candidate["tag"] in request["offers"]
        and candidate["holder"] is record
        and candidate["parent"] == tag
        and request["offers"][candidate["tag"]] in candidate["attrs"]
    }
    if event["action"] not in offered:
        return (
            f"<{tag}> request verb {event['action']!r} is not offered by "
            f"widget {event['widget']!r}; it offers {sorted(offered)}"
        )
    for field, attribute in spec.get("bind", {}).items():
        expected = record["attrs"].get(attribute)
        if event["detail"].get(field) != expected:
            return (
                f"<{tag}> request {event['action']!r} detail `{field}` must match "
                f"its authored `{attribute}` attribute {expected!r}"
            )
    if quoted_in(record, registry):
        return (
            f"<{tag}> {event['widget']!r} stands inside an exhibit (x-exhibit); "
            "quoted material takes no input"
        )
    return None


def request_lifecycle_error(event: dict, events: list, scope: str) -> str | None:
    """Why a document seat cannot start another one-shot host lifecycle."""
    lifecycle = request_lifecycle(
        events,
        widget=event["widget"],
        document={
            "kind": scope,
            **({"revision": event["revision"]} if scope == "page" else {}),
        },
    )
    latest = lifecycle["latest"]
    if latest is None:
        return None
    request_id = latest["request"]["id"]
    if lifecycle["phase"] == "pending":
        return f"widget {event['widget']!r} already has pending request {request_id!r}"
    if lifecycle["phase"] == "completed":
        return f"widget {event['widget']!r} already completed request {request_id!r}"
    return None


def request_contract_error(
    page_dir: Path, event: dict, events: list, registry: dict
) -> str | None:
    """Why a fresh external request violates its package-owned declaration."""
    page = parse_revision(page_dir, event["revision"])
    thread = thread_structure(events)
    _record, _elements, scope = request_document(event, page, thread)
    return declared_request_error(event, page, thread, registry) or (
        request_lifecycle_error(event, events, scope)
    )


def receipt_contract_error(event: dict, events: list) -> str | None:
    """Why a terminal receipt cannot settle the request it names."""
    request_id = event["request"]
    request = next(
        (candidate for candidate in events if candidate["id"] == request_id), None
    )
    if request is None or request["kind"] != "request":
        return f"unknown request {request_id!r}"
    receipt = next(
        (
            candidate
            for candidate in events
            if candidate["kind"] == "receipt" and candidate["request"] == request_id
        ),
        None,
    )
    if receipt is not None:
        return f"request {request_id!r} already has receipt {receipt['id']!r}"
    return None


def request_lifecycles(events: list) -> list[dict]:
    """Every occupied request seat, derived with its owning document identity."""
    seats = {}
    for event in events:
        if event["kind"] != "request":
            continue
        document = event["meaning"]["document"]
        coordinate = (document["kind"], document.get("revision"), event["widget"])
        seats[coordinate] = (event["widget"], document)
    return [
        request_lifecycle(events, widget=widget, document=document)
        for widget, document in seats.values()
    ]


@contract_writer
def cmd_receipt(page_dir: Path, request: str, status: str, text) -> None:
    """Append the one terminal host outcome linked to a reader request."""
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        event = {
            "kind": "receipt",
            "author": "claude",
            **message_identity(),
            "request": request,
            "status": status,
            "text": body,
        }
        if error := receipt_contract_error(event, page.events):
            sys.exit(error)
        accepted = page.append_event(event)
    print(json.dumps(accepted, ensure_ascii=False))
