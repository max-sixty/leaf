"""Canonical workflows for exact user inputs and proactive subject work.

A workflow is one unsettled update the user has handed over, and it
answers two separate questions about it. `stage` is delivery progress: how far
the update has reached the agent (Sent, Queued, Picked up, Working, Replying),
which the margin, the Page Map and a thread's receipt report for every such
update. `answer` is the obligation: the addressed operation the agent owes the
update, or null when it owes nothing. Every consumer that holds the agent to
something — delivery handling, `page state`, activity counts, the Stop hook,
`leaf status idle`, and the banner's counts — reads `answer` here rather than
deciding again what the agent owes. The rule is single: an update with an answer
is owed until that answer is written, and a null answer holds nobody. How long
an owed update holds the agent's turn is `activity.turn_obligations`'s to say.

Answers are one of:

- `{"kind": "reply", "to": <message>, "for": <event>}` — a thread message, or an
  action in an answered Question in frozen thread markup, answered through its exact delivery reference by `leaf response reply`;
  Final-message custody is independent of the operation: `activity` adds
  `writer: "turn"` and its attempt while the provider's reply binding stands.
  Delivery captures the same writer policy ahead of that binding, and emits an
  exact response reference. Direct commands and provider finals resolve that
  reference through the same rich reply writer; only the bound attempt may
  commit while its provider owns the final.
- `{"kind": "markup", "action": <action>}` — a page action that is part of its
  widget's answered Question and the authored markup does not yet record, answered by
  a stamped version that writes it in.

Two kinds of update have workflows with no answer of their own. An update a
newer one in the same thread covers is answered through the newest, whose one
answer settles both. A widget action that answers no Question, such as an edit to a
user-owned draft or a moved card, owes nothing: the log carries it onto later
readings of its document, and `page check` holds the next version to any part
of it that version must write. Its receipt stands until that document takes it
in: on the page, until the markup records it or a later version supersedes it
(`page_action_unsettled`); in frozen thread markup, which no version rewrites,
until the agent's next spoken turn in that thread or a resolution after it.
Delivery is separate from workflows. Admission records whether a user's update
changes outstanding Questions, pending answers, work in hand or approval; delivery keeps
that decision even after these workflows settle.

A user action on a widget whose own Question the user has not finished answering — a
pick before the Done its group declares, an action before a queue is empty —
has not been handed over yet, so it is no workflow at all: the user is still
composing the answer, and the finishing action carries the receipt. Once the Question is
answered, every action on that widget is owed; canonical Questions own that reading.

A harness that gives up on an update writes the failure its answer takes
(`thread.fail_answer`), each carrying `failure`: a reply in the
thread, or a failed pickup of a page action. Either leaves the update a workflow
answered with a failed response, whose next actor is the user, until the user
acts again or the markup records the action anyway.
"""

from .events import (
    conversation_turns,
    exchange,
    turn_message,
    unanswered_turns,
)
from .projection import (
    NO_RECORD,
    PageReading,
    recorded_state,
)
from .tasks import (
    TaskReading,
)


def obligation_reading(readings) -> dict:
    """The outstanding Questions and explicit tasks on the user, answers and work in hand a
    gesture can change.

    Delivery progress, receipt-only updates and presentation are absent. Work in hand,
    an update the agent started or a task it opened on a thread or widget, also holds the
    standing widget inputs on its subject, even while a Question is being composed:
    changing a pick under ongoing work changes that work before Done. Admission
    compares this reading on either side of the append and stores the result.
    """
    work = readings.work
    page = work.page
    thread = work.thread
    workflows = work.workflows
    thread_questions = work.widget_questions
    prompts = work.prompts
    in_hand = [
        (item["id"], item["subject"])
        for item in workflows
        if item["stage"] == "working"
    ] + [
        (task["id"], task["subject"])
        for task in work.log.owed
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
        "questions": {
            "page": [
                question["id"]
                for question in work.document.questions["unanswered"]
                if question["next_actor"] is not None
            ]
            if page is not None
            else [],
            "thread": [
                question["id"]
                for question in thread_questions["unanswered"]
                if question["next_actor"] is not None
            ],
            "prompts": {
                identity: prompt["message"] for identity, prompt in prompts.items()
            },
            # The tasks the agent put on the user, which their Done ends.
            "tasks": [
                task["id"]
                for task in work.log.tasks
                if task["owner"] == "user" and task["state"] == "open"
            ],
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
        "approvals": [event["id"] for event in work.approvals],
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

    An owed action — part of an answered Question — settles when the authored markup
    records it. The note of a later version settles the rest: a verb with no
    authored record form, whose note is the document's answer to it, and an action
    that owed nothing, which that version has taken in whether or not its markup
    records it. The version must follow the action in the log and supersede the
    revision it was made on; a note stamped over the very revision the user
    acted on was written before the action reached anyone.
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
    task_reading: TaskReading | None = None,
    questions: dict,
) -> list[dict]:
    """The unsettled user inputs and strongest evidence held for each.

    A standing start (`tasks.item_starts`) holds an update it names, and a start running
    on an open task over a widget holds that widget's actions delivered before it, as
    the work the task answers. A `put_down` in the log, which `leaf status waiting`
    and `idle` write, ends every start before it, so the updates they named are no
    longer in hand. The workflow names the start holding it as `held_by`,
    which `activity` takes off before serving.

    This is one interaction-scoped projection over the document and log: append
    means Sent, queue acceptance means Queued, entry into an exact agent turn
    means Picked up, and a `start` naming the update means Working
    (`tasks.item_starts`). Replies
    and authored state settle the source update, so the workflow disappears instead
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

    log = task_reading or TaskReading(events)
    starts = log.starts
    widget_starts: dict[str, list[dict]] = {}
    for task in log.owed:
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
        """The start that holds this update: its own, or the newest start on a task over
        its widget written once the update was delivered."""
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
        """One update's workflow. `covering` are the starts that take it in hand for the
        turn that wrote them, which is how the Stop hook tells an update the open turn
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
            # The message a thread input is said in, which shows its delivery: its
            # own, or for a revision the message it rewrote (`events.turn_message`).
            "message": turn_message(source) if target["kind"] == "thread" else None,
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
        """The update a harness failure record returned to the user: answered, with a
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
        turns = exchange(thread)
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
            "to": turn_message(response_address),
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

    # Every widget action the user has handed over keeps its delivery receipt until
    # it settles, whether the widget stands in the page or was frozen into thread
    # markup, and only an action in an answered Question is owed an answer. An action on a
    # Question the user is still answering has not been handed over, so it has no receipt
    # until the finishing action carries one. The two documents differ only in what
    # settles an action and which operation answers an owed one.
    def page_action(coordinate: tuple, source: dict, spec: dict, owed: bool):
        unsettled = page_action_unsettled(
            coordinate,
            source,
            spec,
            page,
            owed=owed,
        )
        return unsettled, {"kind": "markup", "action": source["id"]} if owed else None

    def thread_action(_coordinate: tuple, source: dict, _spec: dict, owed: bool):
        # No later authored document absorbs frozen markup, so the thread's next
        # spoken agent turn is what settles an action there: the reply addressed to an
        # owed action, and for an action that owes nothing any agent turn after it, which
        # has taken the action in as a later version takes in a page action. A reaction
        # is no turn, and a harness's failure reply says no answer is coming rather
        # than answering. The resolution standing over the thread settles the actions
        # made before it, and the answer that resolved it; an action made after it is
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

    question_by_source = {
        question["source"]["id"]: question
        for question in questions["all"]
        if question["source"]["kind"] == "widget"
    }
    documents = []
    if page is not None:
        documents.append((page.projection, page_action))
    if thread_reading is not None:
        documents.append(
            (
                thread_reading.projection,
                thread_action,
            )
        )
    actions = []
    for projection, settlement in documents:
        for coordinate, (source, spec) in projection.actions.items():
            if source["author"] != "user":
                continue
            question = question_by_source.get(source["widget"])
            if question is not None and question["status"] == "open":
                continue
            owed = question is not None and question["status"] == "answered"
            unsettled, answer = settlement(coordinate, source, spec, owed)
            actions.append(
                (
                    source,
                    {"kind": "widget", "id": source["widget"]},
                    list(coordinate),
                    unsettled,
                    answer,
                )
            )

    # One receipt per widget and unit, for the user's newest action on it. A tick and
    # the Done press that followed are two verbs on one unit, and each minted a line:
    # the thread showed "✓ Sent · just now" twice under one question. The later action
    # supersedes the earlier for what the user is owed — that the press landed.
    # Units stay apart: two moved cards, two reviewed files, are two subjects with a
    # margin entry each in the margin.
    newest: dict[tuple[str, str], dict] = {}
    for source, target, coordinate, _unsettled, _answer in actions:
        key = (target["id"], coordinate[1])
        if key not in newest or source["seq"] > newest[key]["seq"]:
            newest[key] = source
    # A harness that gave up on an owed action recorded the failure its answer takes — a
    # failed pickup for a page action, a failure reply for a frozen one — which hands
    # the action back to the user until the action settles or a newer action replaces it.
    for source, target, coordinate, unsettled, answer in actions:
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
