"""Canonical workflows for exact reader inputs and proactive subject work.

A workflow is one unsettled reader move the reader has handed over, and it
answers two separate questions about it. `stage` is delivery progress: how far
the move has reached the agent (Sent, Queued, Picked up, Working, Replying),
which the margin, the Page Map and a thread's receipt report for every such
move. `answer` is the obligation: the addressed operation the agent owes the
move, or null when it owes nothing. Every consumer that holds the agent to
something — delivery handling, `page state`, activity counts, the Stop hook,
`leaf status idle`, and the banner's counts — reads `answer` here rather than
deciding again what the agent owes. The rule is single: a move with an answer
blocks the agent until that answer is written, and a null answer holds nobody.

Answers are one of:

- `{"kind": "reply", "to": <message>, "for": <event>}` — a thread input, or a
  move in an answered Ask in frozen thread markup, answered by `leaf reply --for`;
- `{"kind": "version", "conversation": <thread>}` — a thread the reader opened
  as a request for change, answered by a stamped version and a resolve;
- `{"kind": "markup", "action": <action>}` — a page action that is part of its
  widget's answered Ask and the authored markup does not yet record, answered by
  a stamped version that writes it in;
- `{"kind": "receipt", "request": <request>}` — a request, answered by its one
  terminal receipt.

Two kinds of move are delivered with no answer of their own. A reader input a
newer input in the same thread covers is answered through the newest, whose one
answer settles both. A page action that answers no Ask, such as an edit to a
reader-owned draft or a moved card, owes nothing: the log carries it onto every
later version, and its receipt stands until the markup records it or a later
version takes it in (`page_action_unsettled`).

A reader move on an Ask the reader has not finished answering — a pick before
the Done its group declares, a swipe before the deck's finish — has not been
handed over yet, so it is no workflow at all: the reader is still composing the
answer, and the finishing move carries the receipt. Once the Ask is answered,
every move in its answer is owed.

A host that gives up on a move writes the failure its answer takes
(`conversation.fail_answer`): a reply carrying `failure` in the conversation, a
failed receipt, or a failed pickup of a page move. A failed receipt is the
request's own outcome and settles it; the other two leave the move a workflow
answered with a failed response, whose next actor is the reader, until the reader
moves again or the markup records the move anyway.
"""

from .asks import answers_ask, ask_answered
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
    *,
    owed: bool,
) -> bool:
    """Whether one standing page action is still unsettled.

    An owed move — part of an answered Ask — settles when the authored markup
    records it. The note of a later version settles the rest: a verb with no
    authored record form, whose note is the document's answer to it, and a move
    that owed nothing, which that version has taken in whether or not its markup
    records it. The version must follow the move in the log and supersede the
    revision it was made on; a note stamped over the very revision the reader
    acted on was written before the move reached anyone.
    """
    _widget, unit, _facet = coordinate
    if source["author"] != "user" or unit not in parser.by_id:
        return False
    authored = markup_facet(unit, spec, parser.by_id, spk, registry)
    if owed and authored is not NO_RECORD:
        return authored != folded_facet(source, spec)
    versioned = any(
        event["kind"] == "note"
        and event["seq"] > source["seq"]
        and event["revision"] > source["revision"]
        for event in events
    )
    return not versioned and (
        authored is NO_RECORD or authored != folded_facet(source, spec)
    )


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
        answer: dict | None,
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
            "answer": answer,
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

    def failed(source: dict, target: dict, coordinate: list[str], record: dict) -> dict:
        """The move a host failure record returned to the reader: answered, with a
        failed response, and the reader's to send again."""
        returned = workflow(source, target, coordinate, answer=None)
        returned.update(
            {
                "stage": "answered",
                "ts": record["ts"],
                "detail": None,
                "agent": record.get("agent"),
                "session": record.get("session"),
                "activity": [
                    {
                        "kind": "response",
                        "detail": None,
                        "ts": record["ts"],
                        "session": record.get("session"),
                        "turn": record.get("turn"),
                    }
                ],
                "condition": {"kind": "failed", "operation": "response"},
                "next_actor": "reader",
                "response": {
                    "id": record["id"],
                    "attempt": record.get("attempt"),
                    "state": "failed",
                    "responds": source["id"],
                },
            }
        )
        return returned

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
        target = {"kind": "conversation", "id": thread_id}
        coordinate = ["conversation", thread_id]
        turns_by_id = {message["id"]: message for message in turns}
        for input_id, response in failed_responses.items():
            source = turns_by_id.get(input_id)
            if source is None or any(
                message["author"] != "agent" and message["seq"] > response["seq"]
                for message in turns
            ):
                continue
            workflows.append(failed(source, target, coordinate, response))
        if response_address is None:
            continue
        if (thread["root"].get("response") or {}).get("kind") == "version" and any(
            seat == seat_root(thread) and root_seq > thread["root"]["seq"]
            for root_seq, seat in clarifications
        ):
            continue
        # Every exact input keeps its own transport/work evidence. The response
        # contract deliberately coalesces consecutive reader turns onto the newest
        # address, so only that workflow carries the answer.
        answer = (
            {"kind": "version", "conversation": thread_id}
            if (thread["root"].get("response") or {}).get("kind") == "version"
            else {
                "kind": "reply",
                "to": response_address["id"],
                "for": response_address["id"],
            }
        )
        for source in unanswered_inputs:
            workflows.append(
                workflow(
                    source,
                    target,
                    coordinate,
                    answer=answer if source is response_address else None,
                )
            )
    # Every page action the reader has handed over keeps its delivery receipt until
    # it settles (`page_action_unsettled`); only a move in an answered Ask is owed an
    # answer. A move on an Ask the reader is still answering has not been handed
    # over, so it has no receipt until the finishing move carries one.
    moves = []
    if page is not None:
        for coordinate, (source, spec) in page.projection.actions.items():
            widget, unit, facet = coordinate
            record = page.document.by_id.get(widget)
            if record is None:
                continue
            entry = page.registry.get(record["tag"], {})
            owed = answers_ask(record, entry, source["action"])
            if owed and not ask_answered(
                record,
                entry,
                page.projection,
                page.document.by_id,
                page.spoken,
                page.registry,
            ):
                continue
            unsettled = page_action_unsettled(
                coordinate,
                source,
                spec,
                page.document,
                page.spoken,
                page.registry,
                page.events,
                owed=owed,
            )
            moves.append(
                (
                    source,
                    {"kind": "widget", "id": widget},
                    [widget, unit, facet],
                    unsettled,
                    {"kind": "markup", "action": source["id"]} if owed else None,
                )
            )

    # Frozen widget actions answer an Ask in their conversation, under the same
    # rule as the page's: owed once the reader has answered it, and answered by the
    # next agent turn there, since no later authored document absorbs them.
    if conversation is not None:
        for coordinate, (source, _spec) in conversation.projection.actions.items():
            if source["author"] != "user":
                continue
            thread_id = conversation.thread_by_widget.get(source["widget"])
            thread = threads.get(thread_id)
            if not thread or thread["resolved"]:
                continue
            record = conversation.by_id[source["widget"]]
            entry = page.registry.get(record["tag"], {})
            if not answers_ask(record, entry, source["action"]) or not ask_answered(
                record,
                entry,
                conversation.projection,
                conversation.by_id,
                conversation.spoken,
                page.registry,
            ):
                continue
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
                    not settled,
                    {"kind": "reply", "to": thread_id, "for": source["id"]},
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
    for source, target, coordinate, _unsettled, _answer in moves:
        key = (target["id"], coordinate[1])
        if key not in newest or source["seq"] > newest[key]["seq"]:
            newest[key] = source
    # A host that gave up on an owed page move recorded a failed pickup, which hands
    # the move back to the reader until the markup records it or a newer move
    # replaces it.
    for source, target, coordinate, unsettled, answer in moves:
        if not unsettled or newest[(target["id"], coordinate[1])] is not source:
            continue
        if answer is not None and (
            gave_up := deliveries.get(source["id"], {}).get("failed")
        ):
            workflows.append(failed(source, target, coordinate, gave_up))
        else:
            workflows.append(workflow(source, target, coordinate, answer=answer))

    # A request is owed its one terminal receipt whatever became of the seat that
    # offered it, so it reads from the log alone.
    receipted = {event["request"] for event in events if event["kind"] == "receipt"}
    for source in events:
        if source["kind"] == "request" and source["id"] not in receipted:
            workflows.append(
                workflow(
                    source,
                    {"kind": "widget", "id": source["widget"]},
                    ["request", source["id"]],
                    answer={"kind": "receipt", "request": source["id"]},
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
                "answer": None,
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
