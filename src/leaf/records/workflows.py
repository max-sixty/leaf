"""The updates the user has handed over: each owed update's obligation and every
unsettled update's workflow.

One fold (`handed_over`) reads which updates the user has handed over and which have
settled, and emits two readings of them, each the one home of its facts:

- An **obligation record** (`obligations.update_obligation`) for each update an
  operation answers: what is owed and by whom. Its next actor is the agent while it owes
  the update an answer, the user once a harness handed the update back, and nobody once a
  reply answered it. `obligations.response_address` derives the operation, one of:

  - `{"kind": "reply", "parent": <message>, "responds": <event>}` — a thread message, or an
    action in an answered obligation in thread markup. The agent answers it with
    `leaf thread reply <answer.ref>`.
  - `{"kind": "markup", "action": <action>}` — a page action that is part of its
    widget's answered obligation and the authored markup does not yet record, answered
    by a stamped version that writes it in. An option the user added stays in the log,
    so a version that takes in a pick of it need not write it into the markup.

  Every consumer that holds the agent to something — delivery, `page state`, activity
  counts, the Stop hook, `leaf page close`, the On lists and thread attention — reads
  these records rather than deciding again. `activity.turn_obligations` decides how long
  an owed update holds the agent's turn.

- A **workflow** for each unsettled update: its delivery, the evidence of how far it
  has reached the agent. `pickup` is the furthest a harness has carried it, `queued` or
  `opened` into a turn, and `held_by` the start in force on it; `activity` reads them
  with the claim and serves where it stands (`standing`), which the margin, the Page
  Map and a thread's receipt show. `obligation` names the record it serves, or is
  null for an update that owes nothing. `receipt_refs` maps each claim the update was
  delivered under to the newest `answer.ref` a pickup recorded for it
  (`delivery.record_pickup`); `activity` binds the ref the page's current claim can use
  onto the owed answer. An update no delivery has carried has no ref.

A record exists only for an update an operation names: the newest input the agent owes
an answer in a thread, the newest unsettled owed page action on a widget's unit, an
update a harness handed back, and every input a reply answered. A thread's waiting
inputs are the user's turns there (`events.owed_turns`) and the user's newest owed
action on each unit of a widget a message there sent, such as a message and a pick after
it. They wait side by side in the thread's history (`events.settle`) and owe one reply,
since two would say the same thing twice. That reply is addressed to the newest and
settles them all, so each older input publishes no record, and its workflow names the
newest input's record. A widget action that answers no obligation, such as an edit to a
user-owned draft or a moved card, owes nothing and publishes none. The log goes on
applying it to later readings of the document, and `page check` makes the next version
write any part of it the markup must record. Its receipt shows until the document takes
it in: on the page, until the markup records it or a later version's note takes it in
(`page_action_unsettled`); in thread markup, which no version rewrites, until the
agent's next message in that thread or a resolution after it. A settled page action
leaves the inventory: its widget's own record carries its ending. A turn or an owed
action the user's resolve closed over keeps its record and its workflow, since that
resolve settles nothing the agent owes; a closing that answers for the thread, such as
the agent's own resolve, leaves none (`events.owed_turns`). An update handed back waits
on the user, so closing the thread over it retires it.

Whether an update needs delivering is decided apart from its workflow. Admission
records whether the update changes the user's outstanding obligations, owed answers, work
in hand and explicitly requested widget input (`attention_reading`). Delivery keeps
that decision after the workflow settles.

An action on a widget whose obligation the user is still answering, such as a pick before
its group's Done or an action before a queue is empty, has no workflow yet; the
finishing action carries the receipt. Once the obligation is answered, every action on that
widget is owed, and `obligations` decides when that is.

When a harness gives up on an update, `thread.fail_answer` writes the failure, a reply
in the thread or a failed pickup of a page action, each carrying `failure`. The update's
record then waits on the user, and its workflow keeps the failed response
(`handed_back`), until the user acts again or the markup records the action. A failure
in a thread settles every input waiting there with the update, and each of them keeps a
handed-back workflow naming the update's record.
"""

from bisect import bisect_right
from itertools import accumulate
from operator import itemgetter
from typing import NamedTuple

from leaf.base import standing
from leaf.log.events import (
    conversation_turns,
    exchange,
    is_answer,
    owed_turns,
    settle,
    turn_message,
    widget_messages,
)
from leaf.log.obligations import collection, update_obligation
from leaf.log.projection import (
    NO_RECORD,
    AuthoredOrders,
    PageReading,
    attribute_marks,
    generated_children,
    recorded_state,
)
from leaf.records.todos import TodoReading
from leaf.source.registry.kernel import verb_writers


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
    `unsent` records what the user is still working on and hasn't sent, so its input
    is never part of work in hand.
    """
    work = readings.work
    page = work.page
    thread = work.thread
    workflows = work.workflows
    in_hand = [
        (item["id"], item["subject"])
        for item in workflows
        if item["held_by"] is not None
    ] + [
        (todo["id"], todo["source"]["subject"])
        for todo in work.log.owed
        if todo["source"]["subject"]["kind"] != "page"
    ]
    inputs = [
        (source, spec)
        for projection in ([page.projection] if page is not None else [])
        + [thread.projection]
        for source, spec in projection.actions.values()
        if source["author"] == "user" and not spec.get("unsent")
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


class PageSettlement:
    """What settles the page's actions, read once for all the actions in force one
    reading weighs, so each action costs what it touches rather than the page: the
    document's `(by_id, attribute_marks, AuthoredOrders)`, the children each owner's
    creating actions supply, each position owner's placements (`recorded_state`), and
    the newest revision a version's note stamped after each point in the log."""

    def __init__(self, page: PageReading):
        self.page = page
        byid = page.document.by_id
        self.markup = (
            byid,
            attribute_marks(byid, page.spoken, page.registry),
            AuthoredOrders(byid, page.registry),
        )
        self.added = {
            owner: {child["id"] for child in children}
            for owner, children in generated_children(
                page.projection.desired, set(byid)
            ).items()
        }
        self.placements: dict = {}
        notes = sorted(
            (event["seq"], event["revision"])
            for event in page.events
            if event["kind"] == "note"
        )
        self._note_seqs = [seq for seq, _revision in notes]
        # The greatest revision any note from each position on stamped.
        self._newest_after = list(
            accumulate(reversed([revision for _seq, revision in notes]), max)
        )[::-1]

    def versioned(self, source: dict) -> bool:
        """Whether a version's note follows `source` in the log and stamps a revision
        after the one it was made on."""
        later = bisect_right(self._note_seqs, source["seq"])
        return (
            later < len(self._note_seqs)
            and self._newest_after[later] > source["revision"]
        )


def page_action_unsettled(
    coordinate: tuple,
    source: dict,
    spec: dict,
    settlement: PageSettlement,
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
    page = settlement.page
    byid = settlement.markup[0]
    if widget not in byid or (
        (spec.get("record") or spec.get("creates")) and unit not in byid
    ):
        return False
    reading = recorded_state(
        coordinate,
        source,
        spec,
        settlement.markup,
        page.projection,
        settlement.placements,
    )
    versioned = settlement.versioned(source)
    if reading is NO_RECORD:
        return not versioned
    shown, left = reading
    logged = False
    if spec["record"]["kind"] == "attribute":
        added = settlement.added.get(widget, set())
        logged = any(identity in added for identity in left)
        left = [identity for identity in left if identity not in added]
    recorded = shown == left
    if owed:
        return not recorded or (logged and not versioned)
    return not versioned and not recorded


class _Walk(NamedTuple):
    """One thread's history walked (`events.settle`): the place each input last
    entered its waiting list, the inputs still waiting, each by its position in the
    walk's order, and each agent turn that settled some."""

    places: dict[str, int]
    waiting: dict[str, int]
    settlements: list


class Handover(NamedTuple):
    """The updates the user has handed over: `records`, the obligation each owed or
    answered update publishes (`obligations.collection`), `workflows`, every
    unsettled update's delivery, each naming the record it serves, and `newest`, the
    place of each thread's newest standing input, answered or not (`events.settle`):
    a write to the thread at a reference goes in only at that place or after it
    (`thread.post_reply`)."""

    records: dict
    workflows: list[dict]
    newest: dict[str, int]


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

    This is one interaction-scoped projection over the document and log: a harness
    queue's acceptance is its `queued` pickup, entry into an exact agent turn its
    `opened` one, and a `start` naming the update holds it (`todos.item_starts`).
    Replies and authored state settle the source update, so the workflow disappears
    instead of becoming a second outcome surface; a failed response instead keeps a
    handed-back workflow, whose record waits on the user. A thread's waiting inputs,
    its turns and its owed widget actions, retain distinct workflows even though the
    thread's single response obligation is addressed to the newest one, whose record
    each of them names.
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
        subject = todo["source"]["subject"]
        if todo["line"] and subject["kind"] == "widget":
            widget_starts.setdefault(subject["id"], []).append(todo["line"])

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
        """One update's workflow. `covering` are the starts that take it in hand, from
        which `activity.in_hand` tells whether a start holds it now: the one holding
        it, and in a thread every start on an input the thread's one reply answers."""
        delivery = deliveries.get(source["id"], {})
        opened = delivery.get("opened")
        queued = delivery.get("queued")
        start = holding(source, target, delivered_at(source))
        pickup = opened or queued
        return {
            "id": source["id"],
            "input": source["id"],
            "message": turn_message(source) if target["kind"] == "thread" else None,
            "seq": source["seq"],
            "revision": source.get("revision"),
            "subject": target,
            "coordinate": coordinate,
            "obligation": obligation,
            "pickup": "opened" if opened else "queued" if queued else None,
            "ts": (pickup or source).get("ts"),
            "delivery_seq": pickup["seq"] if pickup else None,
            "delivery_session": pickup.get("session") if pickup else None,
            "delivery_turn": pickup.get("turn") if pickup else None,
            "receipt_refs": refs.get(source["id"], {}),
            "detail": start["text"] if start else None,
            "detail_seq": start["seq"] if start else None,
            "agent": start.get("agent") if start else None,
            "session": start.get("session") if start else None,
            "response": None,
            "handed_back": False,
            "held_by": start,
            "started_by": [
                {
                    "item": held["item"],
                    "session": held.get("session"),
                    "turn": held.get("turn"),
                    "seq": held["seq"],
                    "ts": held["ts"],
                }
                for held in covering
            ],
        }

    def failed(
        source: dict, target: dict, coordinate: list[str], record: dict, obligation: str
    ) -> dict:
        """The update a harness failure record returned to the user, with the failed
        response, serving the record that is now the user's to send again."""
        returned = workflow(
            source, target, coordinate, obligation=obligation, covering=[]
        )
        returned.update(
            {
                "ts": record["ts"],
                "detail": None,
                "detail_seq": None,
                "agent": record.get("agent"),
                "session": record.get("session"),
                "response": {
                    "id": record["id"],
                    "attempt": record.get("attempt"),
                    "state": "failed",
                },
                "handed_back": True,
                "held_by": None,
            }
        )
        return returned

    by_id = {event["id"]: event for event in events}

    # Each thread's history walked (`events.settle`).
    walks: dict[str, _Walk] = {}

    def walk(thread_id: str) -> _Walk:
        if thread_id not in walks:
            thread = threads[thread_id]
            settled = settle(thread)
            walks[thread_id] = _Walk(
                settled.places,
                {turn["id"]: at for at, turn in enumerate(settled.waiting)},
                settled.settlements,
            )
        return walks[thread_id]

    # Every widget action the user has handed over keeps its delivery receipt until
    # it settles, whether the widget stands in the page or in thread
    # markup, and only an action in an answered obligation is owed an answer. An action on an
    # obligation the user is still answering has not been handed over, so it has no receipt
    # until the finishing action carries one. The two documents differ only in what
    # settles an action and which operation answers an owed one.
    page_settlement: PageSettlement | None = None

    def page_action(coordinate: tuple, source: dict, spec: dict, owed: bool):
        nonlocal page_settlement
        assert page is not None
        if page_settlement is None:
            page_settlement = PageSettlement(page)
        return page_action_unsettled(
            coordinate, source, spec, page_settlement, owed=owed
        )

    # Each thread's newest agent turn, which takes in the actions there that owe
    # nothing.
    newest_turn: dict[str, int] = {}

    def thread_action(_coordinate: tuple, source: dict, _spec: dict, owed: bool):
        # No later authored document absorbs thread markup, so the thread's agent
        # turns settle an action there. An owed action waits in the thread's history
        # beside the user's turns, and the answer that settles them settles it
        # (`events.settle`). An action that owes nothing is taken in by any agent turn
        # after it, as a later version takes in a page action; a reaction is no turn,
        # and a harness's failure reply says no answer is coming rather than
        # answering. The closing in force on the thread takes in the actions made
        # before it that owe nothing. An owed one it settles only where it answers
        # for the thread (`events.owed_turns`): the user's own resolve leaves it owed,
        # as it leaves a message. An action that comes into force after the closing
        # is delivered like any other and keeps its receipt.
        thread_id = thread_reading.thread_by_widget.get(source["widget"])
        thread = threads.get(thread_id)
        if not thread:
            return False
        if owed:
            walked = walk(thread_id)
            closing = thread["answered_by"]
            return source["id"] in walked.waiting and not (
                closing and closing["seq"] >= walked.places[source["id"]]
            )
        closing = thread["resolved"]
        if closing and closing["seq"] >= source["seq"]:
            return False
        if thread_id not in newest_turn:
            newest_turn[thread_id] = max(
                (
                    message["seq"]
                    for message in conversation_turns(thread)
                    if message["author"] == "agent" and not message.get("failure")
                ),
                default=0,
            )
        return newest_turn[thread_id] <= source["seq"]

    holding_message = (
        widget_messages(thread_reading.structure) if thread_reading is not None else {}
    )
    obligation_by_source = {
        item["source"]["id"]: item
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
            # Work the user hasn't sent is no update (`$verbs.unsent`).
            if source["author"] != "user" or spec.get("unsent"):
                continue
            item = obligation_by_source.get(source["widget"])
            if item is not None and standing.is_open(item):
                continue
            owed = item is not None and standing.answered(item)
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
    # the Done press that follows are two verbs on one unit, and each would mint a
    # line, showing "✓ Sent · just now" twice under one question. The later action
    # supersedes the earlier for what the user is owed — that the press landed. In
    # thread markup the answer that settles the newest settles them all. On the page
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
    workflows = []
    # Each thread's owed actions in its markup, by thread, each with the place it
    # came into force; the ones still waiting on the agent join the user's turns
    # waiting there.
    owed_in: dict[str, dict[str, tuple]] = {}
    waiting_in: dict[str, list[tuple]] = {}
    for source, target, coordinate, unsettled, owed, on_page in actions:
        key = (target["id"], coordinate[1])
        if newest[key][0] is not source:
            continue
        if owed and not on_page:
            thread_id = thread_reading.thread_by_widget[target["id"]]
            entry = (source, target, coordinate, walk(thread_id).places[source["id"]])
            owed_in.setdefault(thread_id, {})[source["id"]] = entry
            if unsettled:
                waiting_in.setdefault(thread_id, []).append(entry)
            continue
        if key not in pending:
            continue
        # A harness that gave up on an owed page action recorded a failed pickup,
        # which hands the action back to the user until a version settles it or a
        # newer action replaces it. An owed page action publishes its record, which a
        # version answers.
        gave_up = owed and (
            deliveries.get(source["id"], {}).get("failed")
            or failed_responses.get(source["id"])
        )
        obligation = (
            publish(
                update_obligation(
                    source["id"],
                    target,
                    None,
                    None,
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

    newest: dict[str, int] = {}
    for thread_id, thread in threads.items():
        turns = exchange(thread)
        target = {"kind": "thread", "id": thread_id}
        coordinate = ["thread", thread_id]
        walked = walk(thread_id)
        owed_here = owed_in.get(thread_id, {})
        # The inputs a failure reply can hand back: the user's turns still standing
        # and their owed actions on widgets sent here.
        inputs = {
            **{
                turn["id"]: (turn, target, coordinate)
                for turn in turns
                if turn["author"] != "agent"
            },
            **{
                identity: (source, on, at)
                for identity, (source, on, at, _place) in owed_here.items()
            },
        }
        if inputs:
            newest[thread_id] = max(walked.places[identity] for identity in inputs)
        # A failure reply gives up on the input it names and settles every input
        # waiting before it (`events.settle`), so it hands them back to the user as
        # one, on one record. It stands until the user acts in the thread again by
        # anything that still stands, a turn or an owed action, or the agent writes
        # at a reference there since, whatever became of it. It waits on the user, so closing
        # the thread over it retires it. One that fails in a thread already closed
        # still stands: the user's resolve left the request owed, and nothing else
        # would tell them no answer is coming.
        superseded = max(
            [
                turn["seq"]
                for turn in thread["turns"]
                if turn["author"] == "agent" and turn.get("responds")
            ]
            + [turn["seq"] for turn in turns if turn["author"] != "agent"]
            + [place for *_entry, place in owed_here.values()]
            + ([thread["resolved"]["seq"]] if thread["resolved"] else []),
            default=0,
        )
        for each in walked.settlements:
            response = each.answer
            if (
                not response.get("failure")
                or superseded > response["seq"]
                or response["responds"] not in inputs
            ):
                continue
            named, subject, _at = inputs[response["responds"]]
            handed_back = publish(
                update_obligation(
                    named["id"],
                    subject,
                    thread_id,
                    turn_message(named)
                    if subject["kind"] == "thread"
                    else holding_message[subject["id"]],
                    next_actor="user",
                )
            )
            for identity in dict.fromkeys(turn["id"] for turn in each.turns):
                if identity in inputs:
                    source, on, at = inputs[identity]
                    workflows.append(failed(source, on, at, response, handed_back))
        # The user's turns the agent owes and their owed actions on widgets sent
        # here wait as one batch. Every exact input keeps its own transport/work
        # evidence, and the response contract coalesces the batch onto the newest
        # input's address, so only that input publishes a record, and each workflow
        # names it. The newest is the one `settle` holds last, which an answer to it
        # settles with the rest. The record's workflow carries every start on the
        # batch, which `activity.in_hand` reads.
        order = walk(thread_id).waiting
        waiting = sorted(
            [
                (source, target, coordinate, source["seq"])
                for source in owed_turns(thread)
            ]
            + waiting_in.get(thread_id, []),
            key=lambda entry: order[entry[0]["id"]],
        )
        if not waiting:
            continue
        address, subject, _coordinate, _place = waiting[-1]
        owed = publish(
            update_obligation(
                address["id"],
                subject,
                thread_id,
                turn_message(address)
                if subject["kind"] == "thread"
                else holding_message[subject["id"]],
                next_actor="agent",
            )
        )
        starts_on = {
            source["id"]: held
            for source, on, _at, _place in waiting
            if (held := holding(source, on, delivered_at(source)))
        }
        for source, on, at, _place in waiting:
            workflows.append(
                workflow(
                    source,
                    on,
                    at,
                    obligation=owed,
                    covering=list(starts_on.values())
                    if source is address
                    else [starts_on[source["id"]]]
                    if source["id"] in starts_on
                    else [],
                )
            )

    # Every input a reply answered keeps its record, answered by its first answer in
    # the log, in the thread that answer stands in, whether or not the thread is
    # resolved: the agent's list's Done. An input handed back since holds its open
    # record instead. A reply that promises the work rather than delivering it (its
    # `todo`) is no answer to list as done: the to-do it opens is what the request is
    # still owed, and that record lands in Done when the agent ends it.
    thread_of = {
        message["id"]: thread_id
        for thread_id, thread in threads.items()
        for message in thread["msgs"]
    }
    for reply in events:
        if (
            not is_answer(reply)
            or "todo" in reply
            or reply["id"] not in thread_of
            or f"update:{reply['responds']}" in records
        ):
            continue
        source = by_id[reply["responds"]]
        thread_id = thread_of[reply["id"]]
        on_widget = source["kind"] in verb_writers()
        publish(
            update_obligation(
                source["id"],
                {"kind": "widget", "id": source["widget"]}
                if on_widget
                else {"kind": "thread", "id": thread_id},
                thread_id,
                holding_message.get(source["widget"])
                if on_widget
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
        newest,
    )
