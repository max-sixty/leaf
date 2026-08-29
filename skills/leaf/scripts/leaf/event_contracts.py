"""Browser and CLI event contracts against page and thread state."""

from pathlib import Path

from leaf.decisions import (
    asking,
    page_awaiting_values,
    projected_action_holders,
    quoted_in,
    thread_decision_projection,
)
from leaf.events import build_threads
from leaf.files import revision_path
from leaf.passages import enclosing_ids, spoken
from leaf.projection import page_projection, state_projection
from leaf.registry.contract import json_validator, visual_parts
from leaf.structure import parse_revision
from leaf.thread_context import thread_roots, thread_structure, thread_widgets


def thread_universe(events: list, registry: dict):
    """Every widget the log's frozen markup holds, read as one document.

    id → record and id → spoken words, which is the panel's answer to a version's
    `parser.by_id`/`spoken` pair, plus the thread each widget was sent in. A
    version's element universe is one file; the panel's is every fragment the log
    carries, and the two are separate documents that happen to share a page."""
    structure = thread_structure(events)
    byid, spk = {}, {}
    for e in events:
        if markup := e.get("markup"):
            byid.update(structure.fragments[e["id"]].by_id)
            spk.update(spoken(markup, registry))
    return byid, spk, thread_widgets(structure, thread_roots(events))


def thread_state(events: list, registry: dict):
    """What the reader's gestures leave standing on the widgets an agent sent.

    Thread markup is frozen in its event: no version window bounds it and no
    retraction floor reaches it, so every action on it reads the whole
    conversation window. Both doors that must answer for such a widget read it
    here — the action gate, deciding whether a fresh press is allowed, and
    `page state`, telling a session picking the page up what the reader has
    already settled — so a decision made in the panel cannot stand at one door
    and be missing at the other."""
    byid, spk, thread_of = thread_universe(events, registry)
    projection = state_projection(events, byid, spk, registry, None, floors={})
    return projection, byid, thread_of


def detail_error(schema: dict, detail: dict):
    """The first schema complaint about an event's detail payload, or None —
    ordered so which one speaks doesn't depend on validator iteration order."""
    error = min(json_validator(schema).iter_errors(detail), key=str, default=None)
    return error.message if error else None


def event_record_error(contract: dict, event: dict, browser: bool = False):
    """The first complaint from one event kind's stored-record contract."""
    schema = contract["record"]
    instance = event
    if browser:
        # Supply the fields the server and reader add so the full record schema
        # can validate the unstamped request beside its browser assertions.
        schema = {"allOf": [schema, contract["browser"]]}
        instance = {
            **event,
            "id": "browser",
            "ts": "browser",
            "author": "page" if event.get("kind") == "error" else "user",
            "seq": 1,
        }
    return detail_error(schema, instance)


def declared_event_error(
    event: dict, tag: str, registry: dict, kind: str, channel: str
):
    """Why a known widget's verb or detail violates one declared channel."""
    entry = registry.get(tag)
    if entry is None:
        return (
            f"registry no longer declares <{tag}> for {kind} widget {event['widget']!r}"
        )
    declared = entry.get(channel, {})
    spec = declared.get(event["action"])
    if spec is None:
        return f"<{tag}> does not declare {kind} verb {event['action']!r}" + (
            f"; it declares {sorted(declared)}" if kind == "report" and declared else ""
        )
    if message := detail_error(spec["detail"], event["detail"]):
        return f"<{tag}> {kind} {event['action']!r} detail is invalid: {message}"
    return None


def declared_action_error(
    event: dict, page_by_id: dict, thread_by_id: dict, registry: dict
):
    """Why a stored action violates its sending widget's durable declaration."""
    # Page widgets come from the action's own immutable revision. Thread widgets
    # inhabit the panel's other live document. Either record answers both which
    # tag sent the action and whether it stands inside an exhibit.
    rec = page_by_id.get(event["widget"]) or thread_by_id.get(event["widget"])
    if rec is None:
        return (
            f"unknown action widget {event['widget']!r} in revision "
            f"r{event['revision']} "
            "or agent-authored thread markup"
        )
    tag = rec["tag"]
    if error := declared_event_error(event, tag, registry, "action", "x-state"):
        return error
    # The exhibit rule at the door, not only in the shipped runtime's
    # sendAction: an exhibited widget is a mention, and the log outranks the
    # document — an action taken here would replay as a decision the reader
    # made on quoted material. Any sender the key admits reaches this door.
    if quoted_in(rec, registry):
        return (
            f"<{tag}> {event['widget']!r} stands inside an exhibit (x-exhibit); "
            "quoted material takes no input"
        )
    return None


def held_comment_error(event: dict, page_by_id: dict, registry: dict):
    """Why one comment cannot hold the exact command goal it names."""
    target = event.get("holds")
    if not target:
        return None
    rec = page_by_id.get(target)
    conversation = (
        (registry.get(rec["tag"]) or {}).get("x-conversation") if rec else None
    )
    if (
        rec is None
        or not conversation
        or not conversation.get("hold")
        or not asking(rec["attrs"], conversation.get("when"))
        or event.get("anchor") != {"section": target}
    ):
        return (
            "comment holds must name its exact-section anchor on a matching "
            "x-conversation hold target"
        )
    return None


def version_response_comment_error(event: dict, page_by_id: dict, registry: dict):
    """Why a comment cannot require the authored response it names."""
    response = event.get("response")
    if not response:
        return None
    anchor = event.get("anchor")
    target = anchor.get("section") if isinstance(anchor, dict) else None
    rec = page_by_id.get(target)
    conversation = (
        (registry.get(rec["tag"]) or {}).get("x-conversation") if rec else None
    )
    if (
        rec is None
        or not conversation
        or conversation.get("response") != response
        or not asking(rec["attrs"], conversation.get("when"))
        or anchor != {"section": target}
    ):
        return (
            "comment response must match its exact-section x-conversation "
            "response target"
        )
    return None


def visual_anchor_error(event: dict, page_by_id: dict, registry: dict):
    """Why a semantic visual coordinate is not authored on its section."""
    anchor = event.get("anchor") or {}
    visual = anchor.get("visual")
    if not visual:
        return None
    if anchor.get("quote") or anchor.get("datum"):
        return (
            f"visual anchor {visual!r} names a box rather than a passage, "
            "so it cannot also carry a quote or a datum"
        )
    section = anchor["section"]
    available = visual_parts(page_by_id.get(section) or {}, registry)
    if visual not in available:
        return (
            f"visual anchor {visual!r} is not declared on section {section!r}; "
            f"known: {list(available)}"
        )
    return None


def action_contract_error(page_dir: Path, event: dict, events: list, registry: dict):
    """Why a fresh action violates its declaration or current applicability.

    Eligibility is derived inside the append transaction from the action's
    authored document and the standing log. A browser evaluates the same
    declaration for honest controls, but its possibly stale reading never
    authorizes this boundary.
    """
    revision = event["revision"]
    page = parse_revision(page_dir, revision)
    # One reading of the panel's document for the whole door: the id universe the
    # declaration is looked up in and the projection the requirement is judged
    # against are the same frozen fragments, and parsing them twice was two
    # readings that could only ever agree.
    thread_projection, thread_by_id, _threads = thread_state(events, registry)
    if error := declared_action_error(event, page.by_id, thread_by_id, registry):
        return error
    page_rec = page.by_id.get(event["widget"])
    rec = page_rec or thread_by_id[event["widget"]]
    tag = rec["tag"]
    spec = registry[tag]["x-state"][event["action"]]
    requirement = spec.get("requires")
    if not requirement:
        return None

    # Imported here because request admission uses this module's schema helper.
    # The transaction still has one canonical lifecycle reading; the local import
    # only keeps that dependency from becoming an import cycle.
    from leaf.requests import request_lifecycles_for, request_phases

    if page_rec:
        html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        projection, parser, spk = page_projection(html, events, registry, revision)
        byid = parser.by_id
        current = parser.by_id[event["widget"]]
        # This door asks whether the request is answered, not whether it is the
        # reader's to deal with: a conversation standing in the widget's seat
        # takes it off their list without answering it, and refusing their pick
        # over their own remark would refuse them the answer they were asked for.
        awaiting_values = page_awaiting_values(
            html,
            parser,
            projection,
            spk,
            registry,
            request_phases=request_phases(
                request_lifecycles_for(
                    events,
                    parser.lf_elements,
                    registry,
                    {"kind": "page", "revision": revision},
                )
            ),
        )
    else:
        # Thread markup is frozen in the log: it has no version retraction floor
        # and its actions read the whole conversation window.
        projection, byid = thread_projection, thread_by_id
        current = byid[event["widget"]]
        page_html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        threads = build_threads(events, enclosing_ids(page_html))
        settled = {root for root, value in threads.items() if value["resolved"]}
        _, awaiting_values = thread_decision_projection(
            events,
            registry,
            settled,
            request_phases=request_phases(
                request_lifecycles_for(
                    events,
                    list(thread_by_id.values()),
                    registry,
                    {"kind": "thread"},
                )
            ),
        )

    holders = projected_action_holders(projection, byid, registry)
    target = (
        current
        if requirement["target"] == "self"
        else holders.get(current["attrs"]["id"], current["holder"])
    )
    target_id = target["attrs"]["id"]
    awaiting = awaiting_values.get(target_id, False)
    if awaiting != requirement["awaiting"]:
        return (
            f"<{tag}> {event['widget']!r} action {event['action']!r} is "
            f"unavailable: {requirement['target']} {target_id!r} is "
            f"{'still ' if awaiting else 'no longer '}awaiting the reader"
        )
    return None


def report_contract_error(event: dict, page_by_id: dict, registry: dict):
    """Why a structurally complete report violates its widget's declaration —
    the CLI door's mirror of the POST door's action_contract_error. Page markup
    only, never a reply's: a report has to be answerable, and thread markup is
    frozen in the log, so no version could ever absorb or overrule one made
    there."""
    rec = page_by_id.get(event["widget"])
    tag = rec["tag"] if rec else None
    if tag is None:
        return (
            f"unknown report widget {event['widget']!r} in revision "
            f"r{event['revision']} — "
            "reports name page widgets only; thread markup is frozen, so no "
            "version could ever answer a report made there"
        )
    return declared_event_error(event, tag, registry, "report", "x-report")
