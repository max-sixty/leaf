"""The updates the user has handed over: each owed update's obligation and every
unsettled update's workflow.

One fold (`handed_over`) reads which updates the user has handed over and which have
settled, and emits two readings of them, each the one home of its facts:

- An **obligation record** (`obligations.update_obligation`) for each update an
  operation answers: what is owed and by whom. Its next actor is the agent while it owes
  the update an answer, the user once a harness handed the update back, and nobody once a
  reply answered it. `obligations.response_address` derives the operation, one of:

  - `{"kind": "reply", "parent": <message>, "responds": <event>}` — a thread message, or an
    action in an answered obligation in frozen thread markup. The agent answers it with
    `leaf thread reply <answer.ref>`.
  - `{"kind": "markup", "action": <action>}` — a page action that is part of its
    widget's answered obligation and the authored markup does not yet record, answered
    by a stamped version that writes it in. An option the user added stays in the log,
    so a version that takes in a pick of it need not write it into the markup.

  Every consumer that holds the agent to something — delivery, `page state`, activity
  counts, the Stop hook, `leaf page close`, the On lists and thread attention — reads
  these records rather than deciding again. `activity.turn_obligations` decides how long
  an owed update holds the agent's turn.

- A **workflow** for each unsettled update: its delivery. `stage` says how far it has
  reached the agent (Sent, Queued, Delivered, Working, Replying), which the margin, the
  Page Map and a thread's receipt show. `obligation` names the record it serves, or is
  null for an update that owes nothing. `receipt_refs` maps each claim the update was
  delivered under to the newest `answer.ref` a pickup recorded for it
  (`delivery.record_pickup`); `activity` binds the ref the page's current claim can use
  onto the owed answer. An update no delivery has carried has no ref.

A record exists only for an update an operation names: the newest unanswered turn in an
open thread, the newest unsettled owed action on a widget's unit, an update a harness
handed back, and every input a reply answered. When the user sends two messages in a row
in a thread, the reply to the newer one answers both, so the older one publishes no
record and its workflow names the newer one's. A widget action that answers no
obligation, such as an edit to a user-owned draft or a moved card, owes nothing and
publishes none. The log goes on applying it to later readings of the document, and
`page check` makes the next version write any part of it the markup must record. Its
receipt shows until the document takes it in: on the page, until the markup records it
or a later version's note takes it in (`page_action_unsettled`); in a thread's frozen
markup, which no version rewrites, until the agent's next message in that thread or a
resolution after it. A settled page action leaves the inventory: its widget's own record
carries its ending. An unanswered turn in a thread the user resolved first publishes
none.

Whether an update needs delivering is decided apart from its workflow. Admission
records whether the update changes the user's outstanding obligations, owed answers, work
in hand and explicitly requested widget input (`attention_reading`). Delivery keeps
that decision after the workflow settles.

An action on a widget whose obligation the user is still answering, such as a pick before
its group's Done or an action before a queue is empty, has no workflow yet; the
finishing action carries the receipt. Once the obligation is answered, every action on that
widget is owed, and `obligations` decides when that is.

When a harness gives up on an update, `thread.fail_answer` writes the failure, a
reply in the thread or a failed pickup of a page action, each carrying `failure`.
The update's record then waits on the user, and its workflow stays at `answered` with
the failed response, until the user acts again or the markup records the action.
"""

from operator import itemgetter
from typing import NamedTuple

from .events import (
    conversation_turns,
    exchange,
    is_answer,
    turn_message,
    unanswered_turns,
)
from .obligations import collection, update_obligation
from .projection import (
    NO_RECORD,
    PageReading,
    generated_children,
    recorded_state,
)
from .registry.kernel import verb_writers
from .thread_context import widget_messages
from .todos import TodoReading


def attention_reading(readings) -> dict:
    """The obligations, requests and work in hand a gesture can change.

    Delivery progress, receipt-only updates and presentation are absent. Work in hand,
    an update the agent started or a to-do it opened on a thread or widget, also holds the
    widget inputs in force on its subject, even while an obligation is being composed:
    changing a pick under ongoing work changes that work before Done. Admission
    compares this reading on either side of the append and stores the result.
    A verb's explicit attention declaration includes its current input without
    inventing an obligation. Replacing or undoing that input changes this reading
    even when a version's note has settled its delivery workflow. A verb declaring
    `attention: false` records what the user is still working on and hasn't sent, so
    its input is never part of work in hand.
    """
    work = readings.work
    page = work.page
    thread = work.thread
    workflows = work.workflows
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
        (source, spec)
        for projection in ([page.projection] if page is not None else [])
        + [thread.projection]
        for source, spec in projection.actions.values()
        if source["author"] == "user" and spec.get("attention") is not False
    ]
    return {
        "requests": [source["id"] for source, spec in inputs if spec.get("attention")],
        "on_user": [
            item["id"]
            for item in work.all_obligations["unanswered"]
            if item["next_actor"] is not None
        ],
        # The updates the agent owes an answer, by their records.
        "answers": [
            record["id"]
            for record in work.updates["all"]
            if record["next_actor"] == "agent"
        ],
        "work": [
            {
                "id": identity,
                "inputs": [
                    source["id"]
                    for source, _spec in inputs
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
    }


def agent_inputs(work) -> set[str]:
    """The inputs whose next move is the agent's, of `work` (a `WorkReading`): every
    unsettled update but those handed back to the user. A start may take one in hand,
    and a message among them may wake a hook."""
    records = {record["id"]: record for record in work.updates["all"]}
    return {
        item["input"]
        for item in work.workflows
        if item["obligation"] is None
        or records[item["obligation"]]["next_actor"] != "user"
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

    An owed action — part of an answered obligation — settles when the authored markup
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
    if widget not in byid or (
        (spec.get("record") or spec.get("creates")) and unit not in byid
    ):
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


class Handover(NamedTuple):
    """The updates the user has handed over: `records`, the obligation each owed or
    answered update publishes (`obligations.collection`), and `workflows`, every
    unsettled update's delivery, each naming the record it serves."""

    records: dict
    workflows: list[dict]


def handed_over(
    threads: dict,
    thread_reading,
    *,
    page: PageReading | None,
    events: list,
    todo_reading: TodoReading,
    items: dict,
) -> Handover:
    """The unsettled user inputs and strongest evidence held for each, and the record
    each owed or answered input publishes.

    A start in force (`todos.item_starts`) holds an update it names, and a start running
    on an open to-do over a widget holds that widget's actions delivered before it, as
    the work the to-do answers. A `status` declaration in the log, which `leaf page open` and `leaf page close` write, ends every start before it, so the updates they named
    are no longer in hand. The workflow names the start holding it as `held_by`,
    which `activity` takes off before serving.

    This is one interaction-scoped projection over the document and log: append
    means Sent, queue acceptance means Queued, entry into an exact agent turn
    means Delivered (stage `picked_up`), and a `start` naming the update means Working
    (`todos.item_starts`). Replies
    and authored state settle the source update, so the workflow disappears instead
    of becoming a second outcome surface; a failed response instead keeps an
    answered workflow, whose record waits on the user. Consecutive inputs retain
    distinct workflows even though the thread's single response obligation is
    addressed to the newest one, whose record each of them names.
    """
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

    log = todo_reading
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
            key=itemgetter("seq"),
            default=None,
        )

    records: dict[str, dict] = {}

    def publish(record: dict) -> str:
        records[record["id"]] = record
        return record["id"]

    def workflow(
        source: dict,
        target: dict,
        coordinate: list[str],
        *,
        obligation: str | None,
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
            "message": turn_message(source) if target["kind"] == "thread" else None,
            "seq": source["seq"],
            "revision": source.get("revision"),
            "subject": target,
            "coordinate": coordinate,
            "obligation": obligation,
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
            "detail_seq": start["seq"] if start else None,
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

    def failed(
        source: dict, target: dict, coordinate: list[str], record: dict, obligation: str
    ) -> dict:
        """The update a harness failure record returned to the user: answered, with a
        failed response, serving the record that is now the user's to send again."""
        returned = workflow(
            source, target, coordinate, obligation=obligation, covering=[]
        )
        returned.update(
            {
                "stage": "answered",
                "ts": record["ts"],
                "detail": None,
                "detail_seq": None,
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
                "response": {
                    "id": record["id"],
                    "attempt": record.get("attempt"),
                    "state": "failed",
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
            handed_back = publish(
                update_obligation(
                    source["id"],
                    target,
                    thread_id,
                    turn_message(source),
                    next_actor="user",
                )
            )
            workflows.append(failed(source, target, coordinate, response, handed_back))
        unanswered_inputs = unanswered_turns(thread)
        if not unanswered_inputs:
            continue
        # Every exact input keeps its own transport/work evidence. The response
        # contract deliberately coalesces consecutive user turns onto the newest
        # address, so only that input publishes a record, and each workflow names it.
        response_address = unanswered_inputs[-1]
        covering = [
            starts[source["id"]]
            for source in unanswered_inputs
            if source["id"] in starts
        ]
        owed = publish(
            update_obligation(
                response_address["id"],
                target,
                thread_id,
                turn_message(response_address),
                next_actor="agent",
            )
        )
        for source in unanswered_inputs:
            workflows.append(
                workflow(
                    source,
                    target,
                    coordinate,
                    obligation=owed,
                    covering=covering,
                )
            )

    # Every widget action the user has handed over keeps its delivery receipt until
    # it settles, whether the widget stands in the page or was frozen into thread
    # markup, and only an action in an answered obligation is owed an answer. An action on an
    # obligation the user is still answering has not been handed over, so it has no receipt
    # until the finishing action carries one. The two documents differ only in what
    # settles an action and which operation answers an owed one.
    def page_action(coordinate: tuple, source: dict, spec: dict, owed: bool):
        assert page is not None
        return page_action_unsettled(
            coordinate,
            source,
            spec,
            page,
            owed=owed,
        )

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
            return False
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
        return not settled

    holding_message = (
        widget_messages(thread_reading.structure) if thread_reading is not None else {}
    )
    obligation_by_source = {
        (item["source"]["id"], item["source"].get("unit")): item
        for item in items["all"]
        if item["source"]["kind"] == "widget"
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
            # Work the user hasn't sent is no update (`$state.attention`).
            if source["author"] != "user" or spec.get("attention") is False:
                continue
            item = obligation_by_source.get(
                (source["widget"], coordinate[1])
            ) or obligation_by_source.get((source["widget"], None))
            if item is not None and item["status"] == "open":
                continue
            owed = item is not None and item["status"] == "answered"
            actions.append(
                (
                    source,
                    {"kind": "widget", "id": source["widget"]},
                    list(coordinate),
                    settlement(coordinate, source, spec, owed),
                    owed,
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
        for source, target, coordinate, unsettled, _owed, on_page in actions
        if unsettled and (on_page or newest[(target["id"], coordinate[1])][0] is source)
    }
    # A harness that gave up on an owed action recorded the failure its answer takes — a
    # failed pickup for a page action, a failure reply for a frozen one — which hands
    # the action back to the user until the action settles or a newer action replaces it.
    # An owed action publishes its record: a frozen one stands in the thread whose
    # message holds its widget, a page one in none.
    for source, target, coordinate, _unsettled, owed, on_page in actions:
        key = (target["id"], coordinate[1])
        if key not in pending or newest[key][0] is not source:
            continue
        gave_up = owed and (
            deliveries.get(source["id"], {}).get("failed")
            or failed_responses.get(source["id"])
        )
        obligation = (
            publish(
                update_obligation(
                    source["id"],
                    target,
                    None if on_page else thread_reading.thread_by_widget[target["id"]],
                    None if on_page else holding_message[target["id"]],
                    next_actor="user" if gave_up else "agent",
                )
            )
            if owed
            else None
        )
        if gave_up:
            assert obligation is not None
            workflows.append(failed(source, target, coordinate, gave_up, obligation))
        else:
            workflows.append(
                workflow(
                    source,
                    target,
                    coordinate,
                    obligation=obligation,
                    covering=[held]
                    if (held := holding(source, target, delivered_at(source)))
                    else [],
                )
            )

    # Every input a reply answered keeps its record, answered by its first answer in
    # the log, in the thread that answer stands in, whether or not the thread is
    # resolved: the agent's list's Done. An input handed back since holds its open
    # record instead.
    by_id = {event["id"]: event for event in events}
    thread_of = {
        message["id"]: thread_id
        for thread_id, thread in threads.items()
        for message in thread["msgs"]
    }
    for reply in events:
        if (
            not is_answer(reply)
            or reply["id"] not in thread_of
            or f"update:{reply['responds']}" in records
        ):
            continue
        source = by_id[reply["responds"]]
        thread_id = thread_of[reply["id"]]
        frozen = source["kind"] in verb_writers()
        publish(
            update_obligation(
                source["id"],
                {"kind": "widget", "id": source["widget"]}
                if frozen
                else {"kind": "thread", "id": thread_id},
                thread_id,
                holding_message.get(source["widget"])
                if frozen
                else turn_message(source),
                next_actor=None,
                answer=reply,
            )
        )

    return Handover(
        collection(
            sorted(
                records.values(),
                key=lambda record: by_id[record["source"]["id"]]["seq"],
            )
        ),
        sorted(workflows, key=lambda item: (item["seq"], item["id"])),
    )
