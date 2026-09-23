"""Durable one-shot requests and their terminal host receipts."""

from pathlib import Path

from .asks import quoted_in
from .event_meaning import request_unit
from .host import message_identity
from .leases import contract_writer
from .registry.contract import schema_error
from .service import PageTransaction
from .thread_context import thread_structure
from .validation.admission import logged_id, read_text_arg
from .validation.instances import reference_contract_error


def request_lifecycle(
    events: list,
    *,
    widget: str,
    document: dict,
    unit: str | None = None,
    data_revision: int | None = None,
    offered: bool = True,
) -> dict:
    """The canonical lifecycle at one request seat over this event prefix."""
    unit = widget if unit is None else unit
    receipts = {
        event["request"]: event for event in events if event["kind"] == "receipt"
    }
    attempts = []
    for event in events:
        if (
            event["kind"] != "request"
            or event["widget"] != widget
            or event["meaning"]["document"] != document
            or event["meaning"]["unit"] != unit
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
        "seat": {
            "document": document,
            "widget": widget,
            "unit": unit,
            **({"data_revision": data_revision} if data_revision is not None else {}),
            **({"offered": False} if not offered else {}),
        },
        "attempts": attempts,
        "latest": latest,
        "phase": phase,
    }


def request_lifecycles_for(
    events: list,
    elements: list[dict],
    registry: dict,
    document: dict,
    data: dict | None = None,
) -> list[dict]:
    """Displayed seats and historical record seats in one document."""
    seats = {}
    for record in elements:
        request = (registry.get(record["tag"]) or {}).get("x-request")
        if not request:
            continue
        widget = record["attrs"]["id"]
        if request.get("records"):
            if data is not None:
                for row in request_records(record, registry, data):
                    seats[widget, row["key"]] = (row["revision"], True)
            for event in events:
                if (
                    event["kind"] == "request"
                    and event["widget"] == widget
                    and event["meaning"]["document"] == document
                ):
                    seats.setdefault((widget, event["meaning"]["unit"]), (None, False))
        else:
            seats[widget, widget] = (None, True)
    return [
        request_lifecycle(
            events,
            widget=widget,
            unit=unit,
            document=document,
            data_revision=data_revision,
            offered=offered,
        )
        for (widget, unit), (data_revision, offered) in seats.items()
    ]


def request_phases(lifecycles: list[dict]) -> dict[str, str]:
    """Request holder id → phase among seats the document still offers."""
    phases = {}
    for lifecycle in lifecycles:
        if lifecycle["seat"].get("offered") is False:
            continue
        widget = lifecycle["seat"]["widget"]
        phase = lifecycle["phase"]
        if widget not in phases or phase == "ready":
            phases[widget] = phase
    return phases


def request_outcomes(events: list[dict]) -> list[dict]:
    """Every terminal request result, even after its authored seat is retired.

    Seat lifecycles answer what the current document can offer. A receipt remains
    news about a completed instruction after a later revision removes that seat,
    so browser news reads this complete log projection instead of the current
    document's latest lifecycle attempt.
    """
    requests = {event["id"]: event for event in events if event["kind"] == "request"}
    return [
        {
            "request": request["id"],
            "widget": request["widget"],
            "action": request["action"],
            "document": request["meaning"]["document"],
            "unit": request["meaning"]["unit"],
            "receipt": receipt,
        }
        for receipt in events
        if receipt["kind"] == "receipt"
        and (request := requests.get(receipt["request"])) is not None
    ]


def request_document(event: dict, page, thread):
    """The request's sender and the one document that contains its offers."""
    if record := page.by_id.get(event["widget"]):
        return record, page.lf_elements, "page"
    for fragment in thread.fragments.values():
        if record := fragment.by_id.get(event["widget"]):
            return record, fragment.lf_elements, "thread"
    return None, (), None


def request_records(record: dict, registry: dict, data: dict) -> list[dict]:
    """Rows in the exact source selection bound by one authored widget."""
    entry = registry[record["tag"]]
    binding = entry["x-data"][entry["x-request"]["records"]]
    source = record["attrs"].get(binding["source"])
    source_store = data["sources"].get(source) if source else None
    if source_store is None:
        return []
    snapshot_attr = binding.get("snapshot")
    snapshot_id = record["attrs"].get(snapshot_attr) if snapshot_attr else None
    selected = (
        source_store.get("snapshots", {}).get(snapshot_id)
        if snapshot_id
        else source_store
    )
    if selected is None or "value" not in selected:
        return []
    contract = registry["$data"]["contracts"][binding["contract"]]
    records = contract.get("records") or contract["fragments"]
    value = selected["value"]
    rows = value.get(records["items"], []) if isinstance(value, dict) else []
    return [
        {
            "key": row[records["key"]],
            "value": row,
            "revision": int(snapshot_id) if snapshot_id else selected["revision"],
        }
        for row in rows
    ]


def declared_request_error(
    event: dict, page, thread, registry: dict, data: dict | None = None
) -> str | None:
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
        if candidate["tag"] in request.get("offers", {})
        and candidate["holder"] is record
        and candidate["parent"] == tag
        and request["offers"][candidate["tag"]] in candidate["attrs"]
    }
    if request.get("records"):
        offered = set(verbs)
    if event["action"] not in offered:
        return (
            f"<{tag}> request verb {event['action']!r} is not offered by "
            f"widget {event['widget']!r}; it offers {sorted(offered)}"
        )
    if request.get("records"):
        if data is None:
            return None
        unit_field = spec["unit"]
        unit = event["detail"][unit_field]
        rows = request_records(record, registry, data)
        row = next((row for row in rows if row["key"] == unit), None)
        if row is None:
            return f"<{tag}> request unit {unit!r} is not in its displayed data"
        if event.get("data_revision") != row["revision"]:
            return f"<{tag}> request unit {unit!r} names a stale data revision"
        values = row["value"]
    else:
        if "data_revision" in event:
            return f"<{tag}> authored request cannot name a data revision"
        values = record["attrs"]
    for field, attribute in spec.get("bind", {}).items():
        expected = values.get(attribute)
        if event["detail"].get(field) != expected:
            return (
                f"<{tag}> request {event['action']!r} detail `{field}` must match "
                f"its {'record' if request.get('records') else 'authored'} "
                f"`{attribute}` {'field' if request.get('records') else 'attribute'} "
                f"{expected!r}"
            )
    if quoted_in(record, registry):
        return (
            f"<{tag}> {event['widget']!r} stands inside an exhibit (x-exhibit); "
            "quoted material takes no input"
        )
    return None


def request_lifecycle_error(
    event: dict, events: list, scope: str, registry: dict, record: dict
) -> str | None:
    """Why a document seat cannot start another one-shot host lifecycle."""
    lifecycle = request_lifecycle(
        events,
        widget=event["widget"],
        unit=request_unit(
            event, registry[record["tag"]]["x-request"]["verbs"][event["action"]]
        ),
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
    view, event: dict, events: list, registry: dict
) -> str | None:
    """Why a fresh external request violates its package-owned declaration."""
    page = view.document(event["revision"])
    thread = thread_structure(events)
    record, _elements, scope = request_document(event, page, thread)
    return declared_request_error(event, page, thread, registry, view.data) or (
        request_lifecycle_error(event, events, scope, registry, record)
    )


def receipt_contract_error(view, event: dict, events: list) -> str | None:
    """Why a terminal receipt cannot settle the request it names.

    A misdirected id is named as what the log holds it as and sent to the writer that
    takes it, as every writer's refusal does, beside the requests still open to
    receipt — an agent that was handed no request has nothing else to go looking for.
    """
    request_id = event["request"]
    request = next(
        (candidate for candidate in events if candidate["id"] == request_id), None
    )
    if request is None or request["kind"] != "request":
        responses = view.responses(events)
        open_requests = [
            response["request"]
            for response in responses.values()
            if response["kind"] == "receipt"
        ]
        held = logged_id(events, request_id, responses)
        named = (
            f"{request_id!r} is not a request; {held}"
            if held
            else f"unknown request {request_id!r}"
        )
        waiting = (
            "open requests: " + ", ".join(repr(open_id) for open_id in open_requests)
            if open_requests
            else "this page has no open request to receipt"
        )
        return f"{named}; {waiting}"
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
        unit = event["meaning"]["unit"]
        coordinate = (document["kind"], document.get("revision"), event["widget"], unit)
        seats[coordinate] = (event["widget"], document, unit)
    return [
        request_lifecycle(events, widget=widget, document=document, unit=unit)
        for widget, document, unit in seats.values()
    ]


def receipt_event(
    request: str,
    status: str,
    text: str,
    identity: dict,
    failure: str | None = None,
) -> dict:
    """The one terminal outcome of a request, before the door admits it.

    Every receipt writer builds its event here. `failure` is the host's code for a
    request it gave up on; an agent's own outcome, succeeded or failed, omits it.
    """
    return {
        "kind": "receipt",
        "author": "agent",
        **identity,
        "request": request,
        "status": status,
        "text": text,
        **({"failure": failure} if failure is not None else {}),
    }


@contract_writer
def cmd_receipt(page_dir: Path, request: str, status: str, text) -> dict:
    """Append the agent's terminal outcome for a user request."""
    # The door reads this module's request and receipt contracts, so the writer
    # beside them reaches it here rather than at import.
    from leaf.event_contracts import append_admitted

    body = read_text_arg(page_dir, text)
    with PageTransaction(page_dir) as page:
        return append_admitted(
            page, receipt_event(request, status, body, message_identity())
        )
