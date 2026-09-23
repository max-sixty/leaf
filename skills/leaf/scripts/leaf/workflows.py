"""Canonical workflows for exact reader inputs and proactive subject work."""

from .asks import ask_completion
from .events import awaits_agent, seat_root, spoken_turns
from .projection import (
    NO_RECORD,
    PageReading,
    canonical_updates,
    folded_facet,
    markup_facet,
)


def thread_response_batch(turns: list[dict]) -> tuple[list[dict], dict | None]:
    """Return the consecutive reader-input batch and its response address.

    A thread exposes one response obligation, addressed by its newest reader
    input. Before that address is answered every unresponded input retains its
    own workflow. Answering the newest address settles the batch; answering an
    older address removes only that input while the newer address remains owed.
    Independent widget Asks use their own settlement fold and never enter here.
    """
    floor = -1
    newest_before = None
    for index, message in enumerate(turns):
        if message["author"] != "agent":
            newest_before = message
        elif (
            newest_before is not None and message.get("responds") == newest_before["id"]
        ):
            # Answering the batch's newest address settles every reader input
            # accumulated through it. A later reader input starts a fresh batch.
            floor = index
            newest_before = None
    standing = turns[floor + 1 :]
    newest = next(
        (message for message in reversed(standing) if message["author"] != "agent"),
        None,
    )
    if newest is None:
        return [], None
    responses = {
        message.get("responds")
        for message in standing
        if message["author"] == "agent" and message.get("responds")
    }
    if newest["id"] in responses:
        return [], None
    return (
        [
            message
            for message in standing
            if message["author"] != "agent" and message["id"] not in responses
        ],
        newest,
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


def canonical_workflows(
    claims: list,
    threads: dict,
    conversation,
    *,
    page: PageReading | None = None,
    events: list | None = None,
) -> list[dict]:
    """The unsettled reader inputs and strongest evidence held for each.

    This is one interaction-scoped projection over the document and log: append
    means Sent, queue acceptance means Queued, entry into an exact agent turn
    means Picked up, and a matching effective work claim means Working. Replies
    and authored state settle the source move, so the workflow disappears instead
    of becoming a second outcome surface. Consecutive inputs retain distinct
    workflows even though the conversation's single response obligation is
    addressed to the newest one.
    """
    if page is not None:
        events = page.events
    elif events is None:
        raise TypeError("events are required without a page reading")

    deliveries: dict[str, dict[str, dict]] = {}
    responses = {
        event["responds"]: event
        for event in events
        if event["kind"] == "reply"
        and event["author"] == "agent"
        and event.get("responds")
    }
    failed_responses = {
        input_id: response
        for input_id, response in responses.items()
        if response.get("failure")
    }
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
    interaction_claims = {
        claim["event"]: claim for claim in claims if claim.get("scope") == "interaction"
    }
    used_targets = set()

    def workflow(
        source: dict,
        target: dict,
        coordinate: list[str],
        *,
        requires_response: bool,
    ) -> dict:
        claim = interaction_claims.get(source["id"]) or effective_claims.get(
            (target["kind"], target["id"])
        )
        delivery = deliveries.get(source["id"], {})
        opened = delivery.get("opened")
        queued = delivery.get("queued")
        delivery_seq = max(
            (entry["seq"] for entry in (opened, queued) if entry),
            default=source["seq"],
        )
        claim_matches = (
            claim
            and claim["target"] == target
            and (
                claim.get("scope") == "interaction"
                or target["kind"] == "widget"
                or claim.get("event") == source["id"]
            )
        )
        if claim_matches and (
            claim.get("event") == source["id"] or claim["log_floor"] >= delivery_seq
        ):
            stage, evidence = "working", claim
            used_targets.add((target["kind"], target["id"]))
        elif opened:
            stage, evidence = "picked_up", opened
        elif queued:
            stage, evidence = "queued", queued
        else:
            stage, evidence = "sent", source
        fallback = opened or queued
        return {
            "id": source["id"],
            "input": source["id"],
            "seq": source["seq"],
            "revision": source.get("revision"),
            "subject": target,
            "coordinate": coordinate,
            "requires_response": requires_response,
            "stage": stage,
            "ts": evidence.get("ts"),
            "fallback_stage": (
                "picked_up" if opened else "queued" if queued else "sent"
            ),
            "fallback_ts": (fallback.get("ts") if fallback else source.get("ts")),
            "delivery_seq": fallback["seq"] if fallback else None,
            "delivery_session": fallback.get("session") if fallback else None,
            "delivery_turn": fallback.get("turn") if fallback else None,
            "detail": claim["text"] if stage == "working" else None,
            "agent": claim.get("agent") if stage == "working" else None,
            "session": claim.get("session") if stage == "working" else None,
            "activity": (
                [
                    {
                        "kind": "working",
                        "detail": claim["text"],
                        "ts": claim["ts"],
                        "session": claim.get("session"),
                        "turn": claim.get("turn"),
                    }
                ]
                if stage == "working"
                else []
            ),
            "condition": None,
            "next_actor": "agent",
            "response": None,
        }

    workflows = []
    clarifications = [
        (thread["root"]["seq"], seat)
        for thread in threads.values()
        if thread["root"]["author"] == "agent"
        and not thread["resolved"]
        and not awaits_agent(thread)
        and (seat := seat_root(thread))
    ]
    for thread_id, thread in threads.items():
        turns = spoken_turns(thread)
        unanswered_inputs, response_address = thread_response_batch(turns)
        if thread["resolved"]:
            continue
        target = {"kind": "thread", "id": thread_id}
        coordinate = ["thread", thread_id]
        turns_by_id = {message["id"]: message for message in turns}
        for input_id, response in failed_responses.items():
            source = turns_by_id.get(input_id)
            if source is None or any(
                message["author"] != "agent" and message["seq"] > response["seq"]
                for message in turns
            ):
                continue
            failed = workflow(
                source,
                target,
                coordinate,
                requires_response=False,
            )
            failed.update(
                {
                    "stage": "answered",
                    "ts": response["ts"],
                    "detail": None,
                    "agent": response.get("agent"),
                    "session": response.get("session"),
                    "activity": [
                        {
                            "kind": "response",
                            "detail": None,
                            "ts": response["ts"],
                            "session": response.get("session"),
                            "turn": response.get("turn"),
                        }
                    ],
                    "condition": {"kind": "failed", "operation": "response"},
                    "next_actor": "reader",
                }
            )
            workflows.append(failed)
        if response_address is None:
            continue
        if (thread["root"].get("response") or {}).get("kind") == "version" and any(
            seat == seat_root(thread) and root_seq > thread["root"]["seq"]
            for root_seq, seat in clarifications
        ):
            continue
        # Every exact input keeps its own transport/work evidence. The response
        # contract deliberately coalesces consecutive reader turns onto the newest
        # address, so only that workflow is a stop obligation.
        for source in unanswered_inputs:
            workflows.append(
                workflow(
                    source,
                    target,
                    coordinate,
                    requires_response=source is response_address,
                )
            )
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
                page.document,
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
    # conversation, once the reader's declared completion gesture stands. They
    # have no later authored document to absorb them into.
    if conversation is not None:
        for coordinate, (source, _spec) in conversation.projection.actions.items():
            if source["author"] != "user":
                continue
            thread_id = conversation.thread_by_widget.get(source["widget"])
            thread = threads.get(thread_id)
            if not thread or thread["resolved"]:
                continue
            record = conversation.by_id[source["widget"]]
            completed = ask_completion(
                record, page.registry[record["tag"]], conversation.projection
            )
            settled = any(
                message["kind"] == "reply"
                and message["author"] == "agent"
                and message.get("responds") == source["id"]
                for message in thread["msgs"]
            )
            moves.append(
                (
                    source,
                    {"kind": "widget", "id": source["widget"]},
                    list(coordinate),
                    completed is not False,
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
            workflows.append(
                workflow(
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
        target = claim["target"]
        if (target["kind"], target["id"]) in used_targets:
            continue
        workflows.append(
            {
                "id": f"claim:{claim['id']}",
                "input": None,
                "seq": claim["log_floor"],
                "revision": claim.get("revision"),
                "subject": target,
                "coordinate": [target["kind"], target["id"]],
                "requires_response": False,
                "stage": "working",
                "ts": claim["ts"],
                "detail": claim["text"],
                "agent": claim.get("agent"),
                "session": claim.get("session"),
                "activity": [
                    {
                        "kind": "working",
                        "detail": claim["text"],
                        "ts": claim["ts"],
                        "session": claim.get("session"),
                        "turn": claim.get("turn"),
                    }
                ],
                "condition": None,
                "next_actor": "agent",
                "response": None,
            }
        )
    return sorted(workflows, key=lambda item: (item["seq"], item["id"]))
