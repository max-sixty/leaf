"""Interaction-scoped acknowledgment lifecycle projection."""

from .events import awaits_agent, seat_root, spoken_turns
from .projection import (
    NO_RECORD,
    PageReading,
    canonical_updates,
    folded_facet,
    markup_facet,
)


def page_action_unsettled(
    coordinate: tuple,
    source: dict,
    spec: dict,
    parser,
    spk: dict,
    registry: dict,
    events: list,
) -> bool:
    """Whether authored markup still owes one standing page action an answer."""
    _widget, unit, _facet = coordinate
    if source["author"] != "user" or unit not in parser.by_id:
        return False
    authored = markup_facet(unit, spec, parser.by_id, spk, registry)
    folded = folded_facet(source, spec)
    if authored is NO_RECORD:
        return not any(
            event["kind"] == "note" and event["seq"] > source["seq"] for event in events
        )
    return authored != folded


def canonical_acknowledgments(
    claims: list,
    threads: dict,
    conversation,
    *,
    page: PageReading | None = None,
    events: list | None = None,
) -> list[dict]:
    """The unsettled reader moves and the strongest evidence held for each.

    Acknowledgment is one interaction-scoped projection over the document and
    log: append means Sent, queue acceptance means Queued, entry into an exact
    agent turn means Picked up, and a matching effective work claim means
    Active. Replies and authored state
    settle the source move, so the row disappears instead of becoming a second
    outcome surface.
    """
    if page is not None:
        events = page.events
    elif events is None:
        raise TypeError("events are required without a page reading")

    deliveries: dict[str, dict[str, dict]] = {}
    for event in events:
        if event["kind"] != "pickup":
            continue
        for event_id in event["events"]:
            deliveries.setdefault(event_id, {})[event["phase"]] = event

    effective_claims = {
        (update["target"]["kind"], update["target"]["id"]): update
        for update in canonical_updates(None, claims, threads, events)
        if update["disposition"] == "effective"
    }
    used_claims = set()

    def receipt(
        source: dict,
        target: dict,
        coordinate: list[str],
        *,
        requires_response: bool,
    ) -> dict:
        claim = effective_claims.get((target["kind"], target["id"]))
        delivery = deliveries.get(source["id"], {})
        opened = delivery.get("opened")
        queued = delivery.get("queued")
        delivery_seq = max(
            (entry["seq"] for entry in (opened, queued) if entry),
            default=source["seq"],
        )
        claim_matches = claim and (
            target["kind"] == "widget" or claim.get("event") == source["id"]
        )
        if claim_matches and claim["log_floor"] >= delivery_seq:
            phase, evidence = "active", claim
            used_claims.add(claim["id"])
        elif opened:
            phase, evidence = "picked_up", opened
        elif queued:
            phase, evidence = "queued", queued
        else:
            phase, evidence = "sent", source
        fallback = opened or queued
        return {
            "id": source["id"],
            "event": source["id"],
            "seq": source["seq"],
            "revision": source.get("revision"),
            "target": target,
            "coordinate": coordinate,
            "requires_response": requires_response,
            "phase": phase,
            "ts": evidence.get("ts"),
            "fallback_phase": (
                "picked_up" if opened else "queued" if queued else "sent"
            ),
            "fallback_ts": (fallback.get("ts") if fallback else source.get("ts")),
            "delivery_seq": fallback["seq"] if fallback else None,
            "delivery_session": fallback.get("session") if fallback else None,
            "delivery_turn": fallback.get("turn") if fallback else None,
            "detail": claim["text"] if phase == "active" else None,
            "agent": claim.get("agent") if phase == "active" else None,
            "session": claim.get("session") if phase == "active" else None,
        }

    acknowledgments = []
    clarifications = [
        (thread["root"]["seq"], seat)
        for thread in threads.values()
        if thread["root"]["author"] == "claude"
        and not thread["resolved"]
        and not awaits_agent(thread)
        and (seat := seat_root(thread))
    ]
    for thread_id, thread in threads.items():
        turns = spoken_turns(thread)
        unanswered = next(
            (message for message in reversed(turns) if message["author"] != "claude"),
            None,
        )
        if thread["resolved"] or unanswered is None:
            continue
        if any(
            message["author"] == "claude"
            and message.get("responds") == unanswered["id"]
            for message in turns
        ):
            continue
        if (thread["root"].get("response") or {}).get("kind") == "version" and any(
            seat == seat_root(thread) and root_seq > thread["root"]["seq"]
            for root_seq, seat in clarifications
        ):
            continue
        source = unanswered
        target = {"kind": "thread", "id": thread_id}
        coordinate = ["thread", thread_id]
        acknowledgments.append(
            receipt(
                source,
                target,
                coordinate,
                requires_response=True,
            )
        )
        claim = effective_claims.get(("thread", thread_id))
        claim_event = claim.get("event") if claim else None
        if claim_event and claim_event != source["id"]:
            claimed_source = next(
                (message for message in turns if message["id"] == claim_event), None
            )
            if claimed_source:
                anchor = receipt(
                    claimed_source,
                    target,
                    coordinate,
                    requires_response=False,
                )
                # The anchor holds Active beside the message that started the work.
                # Any weaker phase is a second delivery receipt on a subject whose
                # newest move already carries one.
                if anchor["phase"] == "active":
                    anchor["anchor"] = True
                    acknowledgments.append(anchor)

    # A page action stays unsettled only while the authored document still lags
    # its standing record. A recordless verb has no markup form to compare, so a
    # later version note in the log is the document's answer to that move.
    moves = []
    if page is not None:
        for coordinate, (source, spec) in page.projection.actions.items():
            widget, unit, facet = coordinate
            unsettled = page_action_unsettled(
                coordinate,
                source,
                spec,
                page.parser,
                page.spoken,
                page.registry,
                page.events,
            )
            moves.append(
                (
                    source,
                    {"kind": "widget", "id": widget},
                    [widget, unit, facet],
                    False,
                    unsettled,
                )
            )

    # Frozen widget actions are answered by the next agent turn in their
    # conversation. They have no later authored document to absorb them into.
    if conversation is not None:
        for coordinate, (source, _spec) in conversation.projection.actions.items():
            if source["author"] != "user":
                continue
            thread_id = conversation.thread_by_widget.get(source["widget"])
            thread = threads.get(thread_id)
            if not thread or thread["resolved"]:
                continue
            settled = any(
                message["kind"] == "reply"
                and message["author"] == "claude"
                and message.get("responds") == source["id"]
                for message in thread["msgs"]
            )
            moves.append(
                (
                    source,
                    {"kind": "widget", "id": source["widget"]},
                    list(coordinate),
                    True,
                    not settled,
                )
            )

    # One receipt per widget and unit, for the reader's newest move on it. A tick and
    # the Done press that followed are two facets of one unit, and each minted a line:
    # the thread showed "✓ Sent · just now" twice under one question. The later move
    # supersedes the earlier for what the reader is owed — that the press landed.
    # Units stay apart: two moved cards, two reviewed files, are two subjects with a
    # margin entry each in the margin. Chosen before a receipt is minted, so a claim is
    # spent on a move that survives rather than on one dropped here.
    newest: dict[tuple[str, str], dict] = {}
    for source, target, coordinate, _requires_response, _unsettled in moves:
        key = (target["id"], coordinate[1])
        if key not in newest or source["seq"] > newest[key]["seq"]:
            newest[key] = source
    for source, target, coordinate, requires_response, unsettled in moves:
        if unsettled and newest[(target["id"], coordinate[1])] is source:
            acknowledgments.append(
                receipt(
                    source,
                    target,
                    coordinate,
                    requires_response=requires_response,
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
                "requires_response": False,
                "phase": "active",
                "ts": claim["ts"],
                "detail": claim["text"],
                "agent": claim.get("agent"),
                "session": claim.get("session"),
            }
        )
    return sorted(acknowledgments, key=lambda item: (item["seq"], item["id"]))
