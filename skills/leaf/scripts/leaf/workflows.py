"""Canonical workflows for exact user inputs and proactive subject work.

A workflow is one update the user has handed over that has not yet settled.
`stage` says how far it has reached the agent (Sent, Queued, Picked up, Working,
Replying), which the margin, the Page Map and a thread's receipt show. `answer` is
what the agent owes it: an addressed operation, or null for nothing. Every consumer
that holds the agent to something — delivery, `page state`, activity counts, the
Stop hook, `leaf status idle`, and the banner's counts — reads `answer` here rather
than deciding again. An update with an answer is owed until that answer is written.
`activity.turn_obligations` decides how long an owed update holds the agent's turn.

Answers are one of:

- `{"kind": "reply", "to": <message>, "for": <event>}` — a thread message, or an
  action in an answered ask in frozen thread markup. The agent answers it with
  `leaf response reply <answer.ref>`. While a turn has reserved the reply
  (`delivery`'s header), `activity` adds `writer: "turn"` and the reservation's
  attempt.
- `{"kind": "markup", "action": <action>}` — a page action that is part of its
  widget's answered ask and the authored markup does not yet record, answered by
  a stamped version that writes it in. An option the user added stays in the log,
  so a version that takes in a pick of it need not write it into the markup.

`receipt_refs` maps each claim the update was delivered under to the newest
`answer.ref` a pickup recorded for it (`delivery.record_pickup`), and `activity`
sets the answer's `ref` from the page's current claim. An update no delivery has
carried has no ref.

Some workflows carry no answer. When the user sends two messages in a row in a
thread, the older one's workflow has a null answer, and the reply to the newer one
answers both. A widget action that answers no ask, such as an edit to a user-owned
draft or a moved card, owes nothing. The log goes on applying it to later readings
of the document, and `page check` makes the next version write any part of it the
markup must record. Its receipt shows until the document takes it in: on the page,
until the markup records it or a later version's note takes it in
(`page_action_unsettled`);
in a thread's frozen markup, which no version rewrites, until the agent's next
message in that thread or a resolution after it.

Whether an update needs delivering is decided apart from its workflow. Admission
records whether the update changes the user's outstanding asks, owed answers, work
in hand or approvals (`obligation_reading`), and delivery keeps that decision after
the workflow settles.

An action on a widget whose ask the user is still answering, such as a pick before
its group's Done or an action before a queue is empty, has no workflow yet; the
finishing action carries the receipt. Once the ask is answered, every action on that
widget is owed, and `asks` decides when that is.

When a harness gives up on an update, `thread.fail_answer` writes the failure, a
reply in the thread or a failed pickup of a page action, each carrying `failure`.
The workflow then stays, answered with a failed response and waiting on the user,
until the user acts again or the markup records the action.
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
    generated_children,
    recorded_state,
)
from .todos import (
    TodoReading,
)


def obligation_reading(readings) -> dict:
    """The outstanding asks and to-dos on the user, answers and work in hand a gesture
    can change.

    Delivery progress, receipt-only updates and presentation are absent. Work in hand,
    an update the agent started or a to-do it opened on a thread or widget, also holds the
    widget inputs in force on its subject, even while an ask is being composed:
    changing a pick under ongoing work changes that work before Done. Admission
    compares this reading on either side of the append and stores the result.
    """
    work = readings.work
    page = work.page
    thread = work.thread
    workflows = work.workflows
    thread_asks = work.widget_asks
    prompts = work.prompts
    in_hand = [
        (item["id"], item["subject"])
        for item in workflows
        if item["stage"] == "working"
    ] + [
        (todo["id"], todo["subject"])
        for todo in work.log.owed
        if todo["subject"]["kind"] != "page"
    ]
    inputs = [
        source
        for projection in ([page.projection] if page is not None else [])
        + [thread.projection]
        for source, _spec in projection.actions.values()
        if source["author"] == "user"
    ]
    return {
        "on_user": {
            "page": [
                ask["id"]
                for ask in work.document.asks["unanswered"]
                if ask["next_actor"] is not None
            ]
            if page is not None
            else [],
            "thread": [
                ask["id"]
                for ask in thread_asks["unanswered"]
                if ask["next_actor"] is not None
            ],
            "prompts": {
                identity: prompt["message"] for identity, prompt in prompts.items()
            },
            # The to-dos the agent put on the user, which their Done ends.
            "todos": [
                todo["id"]
                for todo in work.log.todos
                if todo["owner"] == "user" and todo["state"] == "open"
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
    """Whether one page action in force is still unsettled.

    An owed action — part of an answered ask — settles when the authored markup
    records it. The note of a later version settles the rest: a verb with no
    authored record form, whose note is the document's answer to it, and an action
    that owed nothing, which that version has taken in whether or not its markup
    records it. The version must follow the action in the log and supersede the
    revision it was made on; a note stamped over the very revision the user
    acted on was written before the action reached anyone.

    An option the user added stands in its group from the log, where the user put
    it, and no version has to write it in. So a pick naming one names an element
    the markup need not hold: the markup records the authored part of the pick, and
    a later version's note takes in the part only the log holds.
    """
    widget, unit, _verb = coordinate
    byid = page.document.by_id
    if unit not in byid:
        return False
    document = (byid, page.spoken)
    reading = recorded_state(
        coordinate, source, spec, document, document, page.registry, page.projection
    )
    versioned = any(
        event["kind"] == "note"
        and event["seq"] > source["seq"]
        and event["revision"] > source["revision"]
        for event in page.events
    )
    if reading is NO_RECORD:
        return not versioned
    shown, left = reading
    logged = False
    if spec["record"]["kind"] == "attribute":
        added = {
            child["id"]
            for child in generated_children(page.projection.desired, set(byid)).get(
                widget, []
            )
        }
        logged = any(identity in added for identity in left)
        left = [identity for identity in left if identity not in added]
    recorded = shown == left
    if owed:
        return not recorded or (logged and not versioned)
    return not versioned and not recorded


def canonical_workflows(
    threads: dict,
    thread_reading,
    *,
    page: PageReading | None = None,
    events: list | None = None,
    todo_reading: TodoReading | None = None,
    asks: dict,
) -> list[dict]:
    """The unsettled user inputs and strongest evidence held for each.

    A start in force (`todos.item_starts`) holds an update it names, and a start running
    on an open to-do over a widget holds that widget's actions delivered before it, as
    the work the to-do answers. A `put_down` in the log, which `leaf status waiting`
    and `idle` write, ends every start before it, so the updates they named are no
    longer in hand. The workflow names the start holding it as `held_by`,
    which `activity` takes off before serving.

    This is one interaction-scoped projection over the document and log: append
    means Sent, queue acceptance means Queued, entry into an exact agent turn
    means Picked up, and a `start` naming the update means Working
    (`todos.item_starts`). Replies
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
    # The newest `answer.ref` receipts recorded for each input (`record_pickup`)
    # under each claim its deliveries were captured under.
    refs: dict[str, dict[str | None, str]] = {}
    for event in events:
        if event["kind"] != "pickup":
            continue
        for event_id in event["events"]:
            deliveries.setdefault(event_id, {})[event["phase"]] = event
        for event_id, ref in event.get("refs", {}).items():
            refs.setdefault(event_id, {})[ref["claim"]] = ref["ref"]

    log = todo_reading or TodoReading(events)
    starts = log.starts
    widget_starts: dict[str, list[dict]] = {}
    for todo in log.owed:
        if todo["running"] and todo["subject"]["kind"] == "widget":
            widget_starts.setdefault(todo["subject"]["id"], []).append(todo["running"])

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
        """The start that holds this update: its own, or the newest start on a to-do over
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
            "receipt_refs": refs.get(source["id"], {}),
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
    # markup, and only an action in an answered ask is owed an answer. An action on an
    # ask the user is still answering has not been handed over, so it has no receipt
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
        # than answering. The resolution in force on the thread settles the actions
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

    ask_by_source = {
        ask["source"]["id"]: ask
        for ask in asks["all"]
        if ask["source"]["kind"] == "widget"
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
            ask = ask_by_source.get(source["widget"])
            if ask is not None and ask["status"] == "open":
                continue
            owed = ask is not None and ask["status"] == "answered"
            unsettled, answer = settlement(coordinate, source, spec, owed)
            actions.append(
                (
                    source,
                    {"kind": "widget", "id": source["widget"]},
                    list(coordinate),
                    unsettled,
                    answer,
                    settlement is page_action,
                )
            )

    # One receipt per widget and unit, for the user's newest action on it. A tick and
    # the Done press that followed are two verbs on one unit, and each minted a line:
    # the thread showed "✓ Sent · just now" twice under one question. The later action
    # supersedes the earlier for what the user is owed — that the press landed. In
    # frozen thread markup the reply answering the newest answers them all. On the page
    # each still settles by its own record: Done hands the tick over rather than
    # replacing it, so the version that takes in the Done still writes the pick, and the
    # receipt stands until every action on the unit has settled.
    # Units stay apart: two moved cards, two reviewed files, are two subjects with a
    # margin entry each in the margin.
    newest: dict[tuple[str, str], tuple] = {}
    for action in actions:
        source, target, coordinate = action[:3]
        key = (target["id"], coordinate[1])
        if key not in newest or source["seq"] > newest[key][0]["seq"]:
            newest[key] = action
    pending = {
        (target["id"], coordinate[1])
        for source, target, coordinate, unsettled, _answer, on_page in actions
        if unsettled and (on_page or newest[(target["id"], coordinate[1])][0] is source)
    }
    # A harness that gave up on an owed action recorded the failure its answer takes — a
    # failed pickup for a page action, a failure reply for a frozen one — which hands
    # the action back to the user until the action settles or a newer action replaces it.
    for source, target, coordinate, _unsettled, answer, _on_page in actions:
        key = (target["id"], coordinate[1])
        if key not in pending or newest[key][0] is not source:
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
