"""Interaction-scoped acknowledgment lifecycle projection."""

from .events import spoken_turns
from .projection import NO_RECORD, canonical_updates, folded_facet, markup_facet


def page_action_unsettled(
    coordinate: tuple,
    source: dict,
    spec: dict,
    parser,
    spk: dict,
    registry: dict,
) -> bool:
    """Whether authored markup still owes one standing page action an answer."""
    _widget, unit, _facet = coordinate
    if source["author"] != "user" or unit not in parser.by_id:
        return False
    authored = markup_facet(unit, spec, parser.by_id, spk, registry)
    folded = folded_facet(source, spec)
    return authored is NO_RECORD or authored != folded


def canonical_acknowledgments(
    events: list,
    claims: list,
    threads: dict,
    projection,
    parser,
    spk: dict,
    conversation,
    registry: dict,
) -> list[dict]:
    """The unsettled reader moves and the strongest evidence held for each.

    Acknowledgment is one interaction-scoped projection over the document and
    log: append means Sent, a page-owned pickup record means Picked up, and a
    matching effective work claim means Active. Replies and authored state
    settle the source move, so the row disappears instead of becoming a second
    outcome surface.
    """
    pickups = {}
    for event in events:
        if event["kind"] != "pickup":
            continue
        for event_id in event["events"]:
            pickups.setdefault(event_id, event)

    effective_claims = {
        (update["target"]["kind"], update["target"]["id"]): update
        for update in canonical_updates(None, claims, threads, events)
        if update["disposition"] == "effective"
    }
    used_claims = set()

    def receipt(source: dict, target: dict, coordinate: list[str]) -> dict:
        claim = effective_claims.get((target["kind"], target["id"]))
        pickup = pickups.get(source["id"])
        if claim and claim["log_floor"] >= source["seq"]:
            phase, evidence = "active", claim
            used_claims.add(claim["id"])
        elif pickup:
            phase, evidence = "picked_up", pickup
        else:
            phase, evidence = "sent", source
        return {
            "id": source["id"],
            "event": source["id"],
            "seq": source["seq"],
            "revision": source.get("revision"),
            "target": target,
            "coordinate": coordinate,
            "phase": phase,
            "ts": evidence["ts"],
            "fallback_phase": "picked_up" if pickup else "sent",
            "fallback_ts": pickup["ts"] if pickup else source["ts"],
            "detail": claim["text"] if phase == "active" else None,
            "agent": claim.get("agent") if phase == "active" else None,
            "session": claim.get("session") if phase == "active" else None,
        }

    acknowledgments = []
    for thread_id, thread in threads.items():
        turns = spoken_turns(thread)
        if thread["resolved"] or not turns or turns[-1]["author"] != "user":
            continue
        source = turns[-1]
        acknowledgments.append(
            receipt(
                source,
                {"kind": "thread", "id": thread_id},
                ["thread", thread_id],
            )
        )

    # A page action stays unsettled only while the authored document still lags
    # its standing record. Verbs without a record stay until their widget is
    # retired by a later document.
    for coordinate, (source, spec) in projection.actions.items():
        widget, unit, facet = coordinate
        if not page_action_unsettled(coordinate, source, spec, parser, spk, registry):
            continue
        acknowledgments.append(
            receipt(
                source,
                {"kind": "widget", "id": widget},
                [widget, unit, facet],
            )
        )

    # Frozen widget actions are answered by the next agent turn in their
    # conversation. They have no later authored document to absorb them into.
    for coordinate, (source, _spec) in conversation.projection.actions.items():
        if source["author"] != "user":
            continue
        thread_id = conversation.thread_by_widget.get(source["widget"])
        thread = threads.get(thread_id)
        if not thread or thread["resolved"]:
            continue
        if any(
            message["kind"] == "reply"
            and message["author"] == "claude"
            and message["seq"] > source["seq"]
            for message in thread["msgs"]
        ):
            continue
        acknowledgments.append(
            receipt(
                source,
                {"kind": "widget", "id": source["widget"]},
                list(coordinate),
            )
        )

    # Keep an explicit claim visible even when there was no preceding reader
    # gesture to grow from. This preserves the useful part of `status --on`
    # without inventing pickup evidence.
    for claim in effective_claims.values():
        if claim["id"] in used_claims:
            continue
        target = claim["target"]
        acknowledgments.append(
            {
                "id": f"claim:{claim['id']}",
                "event": None,
                "seq": claim["log_floor"],
                "revision": claim.get("revision"),
                "target": target,
                "coordinate": [target["kind"], target["id"]],
                "phase": "active",
                "ts": claim["ts"],
                "detail": claim["text"],
                "agent": claim.get("agent"),
                "session": claim.get("session"),
            }
        )
    return sorted(acknowledgments, key=lambda item: (item["seq"], item["id"]))
