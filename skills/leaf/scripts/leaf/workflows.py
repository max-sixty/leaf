"""Canonical workflows for exact user inputs and proactive subject work.

A workflow is one unsettled user move the user has handed over, and it
answers two separate questions about it. `stage` is delivery progress: how far
the move has reached the agent (Sent, Queued, Picked up, Working, Replying),
which the margin, the Page Map and a thread's receipt report for every such
move. `answer` is the obligation: the addressed operation the agent owes the
move, or null when it owes nothing. Every consumer that holds the agent to
something — delivery handling, `page state`, activity counts, the Stop hook,
`leaf status idle`, and the banner's counts — reads `answer` here rather than
deciding again what the agent owes. The rule is single: a move with an answer
is owed until that answer is written, and a null answer holds nobody. How long
an owed move holds the agent's turn is `activity.turn_obligations`'s to say.

Answers are one of:

- `{"kind": "reply", "to": <message>, "for": <event>}` — a thread input, or a
  move in an answered Ask in frozen thread markup, answered by `leaf thread reply --for`;
- `{"kind": "turn", "to", "for", "attempt": <reply attempt>}` — the same reply
  once it is bound to the claimant's App Server turn, which writes it with its own
  opening and final messages. The binding lives in the page's stream status, so
  `activity` routes the answer while the binding stands
  (`activity.reply_binding_stands`), and a delivery frozen for App Server routes it
  ahead of the binding; `leaf thread reply` refuses every writer but that attempt;
- `{"kind": "markup", "action": <action>}` — a page action that is part of its
  widget's answered Ask and the authored markup does not yet record, answered by
  a stamped version that writes it in.

Two kinds of move have workflows with no answer of their own. A user input a
newer input in the same thread covers is answered through the newest, whose one
answer settles both. A widget move that answers no Ask, such as an edit to a
user-owned draft or a moved card, owes nothing: the log carries it onto later
readings of its document, and `page check` holds the next version to any part
of it that version must write. Its receipt stands until that document takes it
in: on the page, until the markup records it or a later version supersedes it
(`page_action_unsettled`); in frozen thread markup, which no version rewrites,
until the agent's next spoken turn in that thread or a resolution after it.
Delivery is separate from workflows. Admission records whether a user's move
changes outstanding Asks, pending answers, work in hand or approval; carriers keep
that decision even after these workflows settle.

A user move on a widget whose own Ask the user has not finished answering — a
pick before the Done its group declares, a swipe before the deck's queue is empty —
has not been handed over yet, so it is no workflow at all: the user is still
composing the answer, and the finishing move carries the receipt. Once the Ask is
answered, every move on that widget is owed (`asks.part_of_ask`).

A harness that gives up on a move writes the failure its answer takes
(`thread.fail_answer`), each carrying `failure`: a reply in the
thread, or a failed pickup of a page move. Either leaves the move a workflow
answered with a failed response, whose next actor is the user, until the user
moves again or the markup records the move anyway.
"""

from .asks import ask_answered, part_of_ask, thread_ask_readings, thread_awaits_user
from .document_reading import read_document
from .events import (
    build_threads,
    conversation_turns,
    standing_approvals,
    unanswered_turns,
)
from .projection import (
    NO_RECORD,
    PageReading,
    recorded_state,
)
from .tasks import item_starts, open_tasks


def admission_workflows(readings) -> tuple[list[dict], dict]:
    """The workflows one admission reads, beside the threads they were folded from:
    the page's newest revision and the frozen thread document, over the log as it
    stands."""
    page = (
        readings.page(readings.view.revisions[-1]) if readings.view.revisions else None
    )
    threads = build_threads(readings.events, page.within if page is not None else {})
    workflows = canonical_workflows(
        threads, readings.thread, page=page, events=readings.events
    )
    return workflows, threads


def obligation_reading(readings) -> dict:
    """The outstanding Asks, answers and work in hand a gesture can change.

    Delivery progress, receipt-only moves and presentation are absent. Work in hand,
    a move the agent started or a task it opened on a thread or widget, also holds the
    standing widget inputs on its subject, even while an Ask is being composed:
    changing a pick under ongoing work changes that work before Done. Admission
    compares this reading on either side of the append and stores the result.
    """
    page = (
        readings.page(readings.view.revisions[-1]) if readings.view.revisions else None
    )
    thread = readings.thread
    events = readings.events
    workflows, threads = admission_workflows(readings)
    thread_asks = thread_ask_readings(
        events,
        readings.registry,
        {identity for identity, held in threads.items() if held["resolved"]},
        reading=thread,
    )
    open_ask_threads = {ask["thread"] for ask in thread_asks["user"]}
    prompts = {}
    for identity, held in threads.items():
        _awaiting, prompt = thread_awaits_user(
            identity,
            held,
            readings.registry,
            thread_asks["awaiting"],
            thread.structure,
            open_ask_threads,
        )
        if prompt is not None:
            prompts[identity] = prompt["message"]
    in_hand = [
        (item["id"], item["subject"])
        for item in workflows
        if item["stage"] == "working"
    ] + [
        (task["id"], task["subject"])
        for task in open_tasks(events)
        if task["subject"]["kind"] != "page"
    ]
    inputs = [
        source
        for projection in ([page.projection] if page is not None else [])
        + [thread.projection]
        for source, _spec in projection.actions.values()
        if source["author"] == "user"
    ]
    return {
        "asks": {
            "page": [
                ask["id"] for ask in read_document(page, threads).asks["unanswered"]
            ]
            if page is not None
            else [],
            "thread": [ask["id"] for ask in thread_asks["unanswered"]],
            "prompts": prompts,
        },
        "answers": [item["answer"] for item in workflows if item["answer"] is not None],
        "work": [
            {
                "id": identity,
                "inputs": [
                    source["id"]
                    for source in inputs
                    if subject == {"kind": "widget", "id": source["widget"]}
                    or subject
                    == {
                        "kind": "thread",
                        "id": thread.thread_by_widget.get(source["widget"]),
                    }
                ],
            }
            for identity, subject in in_hand
        ],
        "approvals": [event["id"] for event in standing_approvals(events)],
    }


def page_action_unsettled(
    coordinate: tuple,
    source: dict,
    spec: dict,
    page: PageReading,
    *,
    owed: bool,
) -> bool:
    """Whether one standing page action is still unsettled.

    An owed move — part of an answered Ask — settles when the authored markup
    records it. The note of a later version settles the rest: a verb with no
    authored record form, whose note is the document's answer to it, and a move
    that owed nothing, which that version has taken in whether or not its markup
    records it. The version must follow the move in the log and supersede the
    revision it was made on; a note stamped over the very revision the user
    acted on was written before the move reached anyone.
    """
    _widget, unit, _verb = coordinate
    byid = page.document.by_id
    if unit not in byid:
        return False
    document = (byid, page.spoken)
    reading = recorded_state(
        coordinate, source, spec, document, document, page.registry, page.projection
    )
    recorded = reading is not NO_RECORD and reading[0] == reading[1]
    if owed and reading is not NO_RECORD:
        return not recorded
    versioned = any(
        event["kind"] == "note"
        and event["seq"] > source["seq"]
        and event["revision"] > source["revision"]
        for event in page.events
    )
    return not versioned and not recorded


def canonical_workflows(
    threads: dict,
    thread_reading,
    *,
    page: PageReading | None = None,
    events: list | None = None,
) -> list[dict]:
    """The unsettled user inputs and strongest evidence held for each.

    A standing start (`tasks.item_starts`) holds a move it names, and a start running
    on an open task over a widget holds that widget's moves delivered before it, as
    the work the task answers. A `put_down` in the log, which `leaf status waiting`
    and `idle` write, ends every start before it, so the moves they named are no
    longer in hand. The workflow names the start holding it as `held_by`,
    which `activity` takes off before serving.

    This is one interaction-scoped projection over the document and log: append
    means Sent, queue acceptance means Queued, entry into an exact agent turn
    means Picked up, and a `start` naming the move means Working
    (`tasks.item_starts`). Replies
    and authored state settle the source move, so the workflow disappears instead
    of becoming a second outcome surface; a failed response instead keeps an
    answered workflow whose next actor is the user. Consecutive inputs retain distinct
    workflows even though the thread's single response obligation is
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

    starts = item_starts(events)
    widget_starts: dict[str, list[dict]] = {}
    for task in open_tasks(events):
        if task["running"] and task["subject"]["kind"] == "widget":
            widget_starts.setdefault(task["subject"]["id"], []).append(task["running"])

    def delivered_at(source: dict) -> int:
        delivery = deliveries.get(source["id"], {})
        return max(
            (
                entry["seq"]
                for entry in (delivery.get("opened"), delivery.get("queued"))
                if entry
            ),
            default=source["seq"],
        )

    def holding(source: dict, target: dict, delivered: int) -> dict | None:
        """The start that holds this move: its own, or the newest start on a task over
        its widget written once the move was delivered."""
        if source["id"] in starts:
            return starts[source["id"]]
        if target["kind"] != "widget":
            return None
        return max(
            (
                start
                for start in widget_starts.get(target["id"], [])
                if start["seq"] >= delivered
            ),
            key=lambda start: start["seq"],
            default=None,
        )

    def workflow(
        source: dict,
        target: dict,
        coordinate: list[str],
        *,
        answer: dict | None,
        covering: list[dict],
    ) -> dict:
        """One move's workflow. `covering` are the starts that take it in hand for the
        turn that wrote them, which is how the Stop hook tells a move the open turn
        has started (`activity.started_in_turn`): the one holding it, and in a thread
        every start on an input the thread's one reply answers."""
        delivery = deliveries.get(source["id"], {})
        opened = delivery.get("opened")
        queued = delivery.get("queued")
        start = holding(source, target, delivered_at(source))
        if start:
            stage, evidence = "working", start
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
            "detail": start["text"] if start else None,
            "agent": start.get("agent") if start else None,
            "session": start.get("session") if start else None,
            "activity": (
                [
                    {
                        "kind": "working",
                        "detail": start["text"],
                        "ts": start["ts"],
                        "session": start.get("session"),
                        "turn": start.get("turn"),
                    }
                ]
                if start
                else []
            ),
            "condition": None,
            "next_actor": "agent",
            "response": None,
            "held_by": start,
            "started_by": [
                {
                    "item": held["item"],
                    "session": held.get("session"),
                    "turn": held.get("turn"),
                    "seq": held["seq"],
                }
                for held in covering
            ],
        }

    def failed(source: dict, target: dict, coordinate: list[str], record: dict) -> dict:
        """The move a harness failure record returned to the user: answered, with a
        failed response, and the user's to send again."""
        returned = workflow(source, target, coordinate, answer=None, covering=[])
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
                "next_actor": "user",
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
    for thread_id, thread in threads.items():
        turns = conversation_turns(thread)
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
            workflows.append(failed(source, target, coordinate, response))
        unanswered_inputs = unanswered_turns(thread)
        if not unanswered_inputs:
            continue
        # Every exact input keeps its own transport/work evidence. The response
        # contract deliberately coalesces consecutive user turns onto the newest
        # address, so only that workflow carries the answer.
        response_address = unanswered_inputs[-1]
        covering = [
            starts[source["id"]]
            for source in unanswered_inputs
            if source["id"] in starts
        ]
        answer = {
            "kind": "reply",
            "to": response_address["id"],
            "for": response_address["id"],
        }
        for source in unanswered_inputs:
            workflows.append(
                workflow(
                    source,
                    target,
                    coordinate,
                    answer=answer if source is response_address else None,
                    covering=covering,
                )
            )

    # Every widget move the user has handed over keeps its delivery receipt until
    # it settles, whether the widget stands in the page or was frozen into thread
    # markup, and only a move in an answered Ask is owed an answer. A move on an Ask
    # the user is still answering has not been handed over, so it has no receipt
    # until the finishing move carries one. The two documents differ only in what
    # settles a move and which operation answers an owed one.
    def page_move(coordinate: tuple, source: dict, spec: dict, owed: bool):
        unsettled = page_action_unsettled(
            coordinate,
            source,
            spec,
            page,
            owed=owed,
        )
        return unsettled, {"kind": "markup", "action": source["id"]} if owed else None

    def thread_move(_coordinate: tuple, source: dict, _spec: dict, owed: bool):
        # No later authored document absorbs frozen markup, so the thread's next
        # spoken agent turn is what settles a move there: the reply addressed to an
        # owed move, and for a move that owes nothing any agent turn after it, which
        # has taken the move in as a later version takes in a page move. A reaction
        # is no turn, and a harness's failure reply says no answer is coming rather
        # than answering. The resolution standing over the thread settles the moves
        # made before it, and the answer that resolved it; a move made after it is
        # delivered like any other and keeps its receipt.
        thread_id = thread_reading.thread_by_widget.get(source["widget"])
        thread = threads.get(thread_id)
        if not thread or (
            thread["resolved"] and thread["resolved"]["seq"] >= source["seq"]
        ):
            return False, None
        settled = any(
            message["author"] == "agent"
            and not message.get("failure")
            and (
                message.get("responds") == source["id"]
                if owed
                else message["seq"] > source["seq"]
            )
            for message in conversation_turns(thread)
        )
        return not settled, (
            {"kind": "reply", "to": thread_id, "for": source["id"]} if owed else None
        )

    documents = []
    if page is not None:
        documents.append((page.projection, page.document.by_id, page.spoken, page_move))
    if thread_reading is not None:
        documents.append(
            (
                thread_reading.projection,
                thread_reading.by_id,
                thread_reading.spoken,
                thread_move,
            )
        )
    moves = []
    for projection, by_id, spoken, settlement in documents:
        for coordinate, (source, spec) in projection.actions.items():
            if source["author"] != "user":
                continue
            # The projection admits only actions whose widget the markup holds
            # and whose tag declares the verb.
            record = by_id[source["widget"]]
            entry = page.registry[record["tag"]]
            owed = part_of_ask(record, entry)
            if owed and not ask_answered(
                record, entry, projection, by_id, spoken, page.registry
            ):
                continue
            unsettled, answer = settlement(coordinate, source, spec, owed)
            moves.append(
                (
                    source,
                    {"kind": "widget", "id": source["widget"]},
                    list(coordinate),
                    unsettled,
                    answer,
                )
            )

    # One receipt per widget and unit, for the user's newest move on it. A tick and
    # the Done press that followed are two verbs on one unit, and each minted a line:
    # the thread showed "✓ Sent · just now" twice under one question. The later move
    # supersedes the earlier for what the user is owed — that the press landed.
    # Units stay apart: two moved cards, two reviewed files, are two subjects with a
    # margin entry each in the margin.
    newest: dict[tuple[str, str], dict] = {}
    for source, target, coordinate, _unsettled, _answer in moves:
        key = (target["id"], coordinate[1])
        if key not in newest or source["seq"] > newest[key]["seq"]:
            newest[key] = source
    # A harness that gave up on an owed move recorded the failure its answer takes — a
    # failed pickup for a page move, a failure reply for a frozen one — which hands
    # the move back to the user until the move settles or a newer move replaces it.
    for source, target, coordinate, unsettled, answer in moves:
        if not unsettled or newest[(target["id"], coordinate[1])] is not source:
            continue
        if answer is not None and (
            gave_up := deliveries.get(source["id"], {}).get("failed")
            or failed_responses.get(source["id"])
        ):
            workflows.append(failed(source, target, coordinate, gave_up))
        else:
            workflows.append(
                workflow(
                    source,
                    target,
                    coordinate,
                    answer=answer,
                    covering=[held]
                    if (held := holding(source, target, delivered_at(source)))
                    else [],
                )
            )

    return sorted(workflows, key=lambda item: (item["seq"], item["id"]))
