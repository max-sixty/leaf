"""Canonical obligations from messages, widgets and updates.

One record contains its prompt, typed answer, completion and next actor. Its thread
and exact owning message locate thread sources without depending on a live renderer.
A widget source owns identity; the group the author declares round it contributes
only prompt words and arrival (`obligation_sources.widget_groups`). A widget that asks
owes one obligation, identified by the widget's id.
The inventory is complete even when a work queue hides a resolved thread or an
older prompt.

On the page, the user answers an obligation only through its source: a widget
through their own gestures on it, an agent message through a message of theirs in
its thread, words or a reaction. Leaf adds no control of its own, such as a generic
Done, and nothing reaches On Me unless a widget or a thread answers it (`todos` records
the decision). Any widget may ask by declaring `awaits`; content that doesn't is
asked about in a thread anchored to it. Whether a widget's obligation is answered is
the widget's own word, which its gestures carry (`gesture_answers`), so this module
reads it and keeps no rule of its own for it. The browser draws the same word in the
gesture's task, and this reading takes over once it arrives.

An update the user handed over publishes a record of its own (`update_obligation`),
built by the fold that decides which updates are handed over and settled
(`workflows.handed_over`). Its next actor is the agent while it owes the update an
answer, the user once a harness handed the update back, and nobody once a reply
answered it; `response_address` derives the operation that answers it. A thread is
never an obligation itself: its messages publish them.

An agent message carrying `obligation` asks a question the user answers in words:
their next message in its thread, words or a reaction, is its answer. The message owns identity and prompt; its thread only locates it.

That answer takes effect at once, whatever the words say, so the user can clear On Me
without waiting for the agent. Only the agent can read whether they answered, and
where they asked back or the step is still to do, its reply's `obligation` names the
question by id, as one reply can name each question the user's message answered. The
question then stands open again under the id and the words of the message that first
asked it, so a plan step naming it follows under the same title, and stands on that
reply, which On Me shows and the user's next message answers. The user chose this
over handing the question to the agent until it replied, as a widget's
does, which left On Me full until the agent had read each reply, and over asking again
under a new id, which left the plan step reading done. Asking again is the declaration
asking is, an `obligation` naming the questions, rather than a second one beside it.

A record says where it stands in the fields every record does (`standing`), and this
module is their producer for what the user owes. An open one is `waiting` on its next
actor. A `done` one ended one of two ways: answered, its typed answer in the record
(`standing.answered`), or `dropped`, an obligation the document no longer makes. A
question asked in a thread message, in words or by a widget in it, also ends when either
side resolves its thread after the message now asking it: it stays `waiting` with
nobody's move, even where a later reply reopens the thread, until a message asks it again
under its id (`question_ids`) or the resolve is taken back. That is how the agent ends
one the user answered on another surface, or that no longer applies, so the thread reads
as settled wherever it shows. The user asked for this over an agent end of its own
(`todo_end` on the question's id, read as answered elsewhere or dropped with the agent's
note), which added an ending, a line under the question and a Done row, and left threads
it ended open. A page widget's question the user answered elsewhere, as in chat, is
retired by a revision that sets its `awaits.retired` attribute: markup answers
nothing."""

import hashlib
import json
import weakref
from bisect import bisect_right
from collections.abc import Callable
from functools import partial
from math import inf

from leaf.base import standing
from leaf.base.page_memory import Slot
from leaf.base.standing import ended, is_open, on
from leaf.log.events import (
    owed_turns,
    report_settled_at,
    taken_back,
    unanswered_agent_turn,
)
from leaf.log.projection import (
    AuthoredOrders,
    StateProjection,
    ThreadMarkupReading,
    attribute_marks,
    folded_value,
    obligation_value,
    page_reading,
)
from leaf.log.thread_context import widget_messages
from leaf.source.obligation_sources import ObligationSources, obligation_sources
from leaf.source.reading import SourceReading
from leaf.source.registry.contract import matches_when
from leaf.source.registry.kernel import verb_writers


def question_ids(message: dict) -> list[str]:
    """The ids of the questions an agent message asks in words: the ones its
    `obligation` lists, each the id of the message that first asked it, or where it is
    `true`, its own."""
    asked = message["obligation"]
    return [f"message:{message['id']}"] if asked is True else asked


def questions_in_words(events: list, names: dict, thread: str) -> set[str]:
    """The questions `thread`'s messages ask in words (`question_ids`), which a
    message's `obligation` names to ask one again; `names` is `events`'
    `thread_context.thread_names`."""
    return {
        question
        for event in events
        if event.get("obligation") and names.get(event["id"]) == thread
        for question in question_ids(event)
    }


def settle_by_words(record: dict, answer: dict | None) -> None:
    """Settle a message obligation from the user's message that answers it, if any."""
    if answer is not None:
        record.update(ended("done"))
        record["answer"] = {
            "value": {key: answer[key] for key in ("text", "emoji") if key in answer},
            "event": event_reference(answer),
        }


def event_reference(event: dict | None) -> dict | None:
    """The admitted gesture that supplied an answer; authored state has none."""
    if event is None:
        return None
    return {
        key: event[key] for key in ("id", "kind", "seq", "ts", "author") if key in event
    }


def collection(records: list[dict]) -> dict:
    """Select obligations from an inventory without deciding membership again."""
    return {
        "all": records,
        "user": [record for record in records if record["next_actor"] == "user"],
        "unanswered": [record for record in records if is_open(record)],
    }


def update_obligation(
    source: str,
    subject: dict,
    thread: str | None,
    message: str | None,
    *,
    next_actor: str | None,
    answer: dict | None = None,
) -> dict:
    """The record an update the user handed over publishes: `source` is the input's
    event id, `subject` the thread or widget it stands on. Open while someone owes it
    a move, done once `answer`, the reply that answered it, stands. Its prompt
    names no words of its own: a row reads its thread's or widget's name. `activity`
    adds how far the agent has got with an open one (`seen`, `line`, `workflow`)."""
    return {
        "id": f"update:{source}",
        "source": {"kind": "update", "id": source, "subject": subject},
        "thread": thread,
        "message": message,
        "prompt": {"text": None, "target": subject["id"]},
        "answer": {"value": None, "event": event_reference(answer)} if answer else None,
        "end": None,
        **(ended("done") if answer else on(next_actor)),
        "seen": answer is not None,
        "workflow": None,
    }


def response_address(record: dict) -> dict:
    """The operation that answers an update: a thread reply or a stamped page revision.
    Reply addresses use the logged event's `parent` (message) and `responds` (exact
    input), which differ for edits and widget actions in thread markup.
    """
    source = record["source"]
    if record["thread"] is None:
        return {"kind": "markup", "action": source["id"]}
    return {
        "kind": "reply",
        "parent": record["message"]
        if source["subject"]["kind"] == "thread"
        else record["thread"],
        "responds": source["id"],
    }


def replayed_attrs(rec: dict, projection: StateProjection) -> dict:
    """An element's attributes under the declared current projection: authored
    markup overlaid with every surviving value record; independent verbs coexist."""
    attrs = rec["attrs"]
    unit = attrs.get("id")
    if not unit:
        return attrs
    held = projection.desired_by_unit.get(unit, [])
    for e, spec in sorted(held, key=lambda item: item[0]["seq"]):
        if (spec.get("record") or {}).get("kind") == "value":
            attrs = {**attrs, spec["record"]["attr"]: folded_value(e, spec)}
    return attrs


def previously_requested(
    record: dict,
    projection: StateProjection,
    when: dict,
    revision: int | None,
    settled: dict,
) -> bool:
    """Registration at relevant gestures in their own immutable source basis.

    Each of the element's value writes in `revision` asks whether `when` held on
    the log's prefix through it. The fold of that prefix (`state_projection`) takes
    its floors and withdrawals from the whole log, so it admits the actions
    `projection`, the fold of the whole log in `revision`, holds in force; and it
    settles only the reports a note through the write settles (`settled`, from
    `events.report_settled_at` through `revision`). So one walk of the value writes
    at the element's unit reads every prefix by the rule `state_projection` builds
    `desired` by: a coordinate stands at its newest action in force so far, else at
    its newest report not yet settled. An attribute then reads the newest write
    standing at any of its coordinates (`replayed_attrs`), which is its newest write
    no note has settled: a newer write at a coordinate is a newer write of its
    attribute. So each attribute keeps its writes in log order, and a write reads
    each attribute `when` names from the newest of them. Surviving actions and
    reports can originate a conditional request between document revisions;
    retracted actions cannot.
    """
    unit = record["attrs"].get("id")
    writes: dict[str, list] = {}
    for coordinate, (event, spec) in projection.classified_by_unit.get(unit, ()):
        effect = spec.get("record") or {}
        if effect.get("kind") != "value" or (
            event["kind"] == "action" and event["id"] not in projection.in_force
        ):
            continue
        writes.setdefault(effect["attr"], []).append((event, spec))
        if (
            coordinate[0] != unit
            or (revision is not None and event["revision"] != revision)
            or effect["attr"] not in when
        ):
            continue
        attrs = dict(record["attrs"])
        for attr in when:
            held = writes.get(attr)
            # A report a note has settled stays settled on every longer prefix.
            while held and settled.get(held[-1][0]["id"], inf) <= event["seq"]:
                held.pop()
            if held:
                attrs[attr] = folded_value(*held[-1])
        if matches_when(attrs, when):
            return True
    return False


def gesture_answers(events: list, projection: StateProjection) -> dict[str, bool]:
    """Each widget's word on whether its obligation is answered: widget id → what the
    newest of these says. A gesture that carries a word, an action of the widget still
    in force or the user's undo of one, says its `answered`. A version note that
    restates what any of the widget's actions rests on, retracting it, says the
    question is open again, whichever member the retracted action named, until a later
    gesture says otherwise.

    The widget decides, in the browser, from its state as the gesture left it
    (`module-state.md`, "Declared widget state"), and the runtime sends the word on the
    gesture's event, so this reads the word and decides nothing again. An action no
    longer in force says nothing, since the state it left is gone: an undo carries the
    word for the state after it, and a retraction carries none, so the note speaks for
    it. A widget with no word is unanswered, whatever its markup holds."""
    undone = {event["undoes"] for event in events if event["kind"] == "undo"}
    resting: dict[str, list[dict]] = {}
    widget_of: dict[str, str] = {}
    said: dict[str, bool] = {}
    for event in events:
        if event["kind"] == "action":
            widget_of[event["id"]] = event["widget"]
            meaning = event.get("meaning") or {}
            for identity in {event["widget"], *meaning.get("depends", ())}:
                resting.setdefault(identity, []).append(event)
            if "answered" in event and event["id"] in projection.in_force:
                said[event["widget"]] = event["answered"]
        elif event["kind"] == "undo" and "answered" in event:
            if (widget := widget_of.get(event["undoes"])) is not None:
                said[widget] = event["answered"]
        elif event["kind"] == "note":
            for identity in event.get("restated", ()):
                for action in resting.get(identity, ()):
                    # Retracted by this note: made on an earlier version, out of force
                    # at the end, and not taken back by the user.
                    if (
                        action["revision"] < event["revision"]
                        and action["id"] not in projection.in_force
                        and action["id"] not in undone
                    ):
                        said[action["widget"]] = False
    return said


def anchors_with_agent(threads: dict, owed: list[dict]) -> list[dict]:
    """The anchors of threads the agent owes: one holding a turn the agent has
    not answered (`events.owed_turns`), or an open to-do, the work a reply there
    promised (`todos.todo_reading`). `owed` is `todos.TodoReading.owed`.

    An open obligation such a thread is about is the agent's turn rather than the user's:
    the user has said something about it and waits on the answer, so it leaves
    their list until the agent answers. A reply that promises work settles the
    message but leaves the obligation the agent's until the agent ends the to-do.
    Both hold through the user's resolve, which takes the thread off their list and
    settles nothing the agent owes, so a decision the user put off until an answer
    or other work lands stays off their list. Neither is an answer, since the
    widget's state is untouched, and the obligation stays open, its controls live.
    The browser receives the lists this leaves rather than deciding again, so On
    Me's count and `page state` cannot disagree about whose turn it is.

    Which kind of thread does not enter into it: a seat's, a quote on the obligation's
    words, a design note, or one the agent opened that the user has answered. A to-do
    the agent opened on an element is not a thread's and holds nothing: work on a
    section doesn't say whether the user's decision there waits on it."""
    promised = {
        todo["source"]["subject"]["id"]
        for todo in owed
        if todo["source"]["subject"]["kind"] == "thread"
    }
    return [
        anchor
        for identity, thread in threads.items()
        if (owed_turns(thread) or identity in promised)
        and (anchor := thread["anchor"])
        and anchor.get("section")
    ]


def discussed_by(records: list[dict], within: dict) -> Callable[[dict], list[dict]]:
    """The reading of which obligations among `records` a thread anchored at a given
    anchor is about, as a function of the anchor.

    A section is about the innermost obligation whose widget encloses it, answered or not;
    failing one, about every obligation whose widget it encloses; failing those, about
    every obligation whose prompt target (its group, `obligation_sources.widget_groups`)
    is the innermost to enclose it. So a note on one obligation's option, or on a part
    of a group holding one obligation, leaves its sibling in the group out, while one on
    anything else in the group, such as the heading naming it where the group holds that
    heading, or on a section holding the group, is about them all. A note on a name that
    stands outside its group, as a workspace header's heading can, is about none of the
    group's obligations. `within` is the document's containment (`Passages.enclosing`).

    The records are indexed once by source, prompt target and each id enclosing
    their source, so a caller asking for every thread on the page reads each
    thread's anchor against the indexes rather than every record again.
    """
    items: dict[str, list[dict]] = {}
    grouped: dict[str, list[dict]] = {}
    enclosed: dict[str, list[dict]] = {}
    for record in records:
        items.setdefault(record["source"]["id"], []).append(record)
        grouped.setdefault(record["prompt"]["target"], []).append(record)
        for around in set(within.get(record["source"]["id"], ())):
            enclosed.setdefault(around, []).append(record)

    def about(anchor: dict) -> list[dict]:
        section = anchor["section"]
        chain = within.get(section, ())
        item = next((items[i] for i in reversed(chain) if i in items), None)
        return list(
            item
            if item is not None
            else enclosed.get(section)
            or next((grouped[i] for i in reversed(chain) if i in grouped), [])
        )

    return about


def thread_topics(threads: dict, records: list[dict], within: dict) -> dict[str, list]:
    """Each thread's id → the page obligations among `records` it is about
    (`discussed_by`), by the section its anchor names now; a thread with no section
    is about none."""
    about = discussed_by(records, within)
    return {
        identity: about(anchor)
        if (anchor := thread["anchor"]) and "section" in anchor
        else []
        for identity, thread in threads.items()
    }


def waiting_about(
    records: list[dict], threads: dict, within: dict
) -> Callable[[str], list[dict]]:
    """The records among `records` that still wait on the user's words in a thread
    about an obligation of a given widget (`thread_topics`), as a function of the
    widget: the questions the agent asked there, which an answer to that obligation
    may or may not settle. Each is its `id` and the words that asked it
    (`prompt.text`).

    The questions and their threads' topics are read once, so a batch asking for
    each of its actions reads the records once rather than once per action."""
    page = [
        record
        for record in records
        if record["thread"] is None and record["source"]["kind"] == "widget"
    ]
    asked = [
        record
        for record in records
        if record["thread"] is not None
        and record["next_actor"] == "user"
        and answered_in_words(record)
    ]
    topics = thread_topics(
        {record["thread"]: threads[record["thread"]] for record in asked}, page, within
    )
    by_widget: dict[str, list[dict]] = {}
    for record in asked:
        for widget in {about["source"]["id"] for about in topics[record["thread"]]}:
            by_widget.setdefault(widget, []).append(
                {"id": record["id"], "text": record["prompt"]["text"]}
            )

    def about(widget: str) -> list[dict]:
        return list(by_widget.get(widget, ()))

    return about


def discussed(records: list[dict], anchors: list[dict], within: dict) -> None:
    """Hand each open obligation discussed by `anchors` (`discussed_by`) to the agent."""
    about = discussed_by(records, within)
    for anchor in anchors:
        for record in about(anchor):
            if record["next_actor"] == "user":
                record["next_actor"] = "agent"


# For each earlier revision's reading and widget, the last answer to whether the widget
# asked there, keyed by the event basis it read (`_ObligationReducer.inventory`). It
# lasts as long as the reading, so a fold over an unchanged log folds that revision
# again only once its reading is gone.
_REQUESTED: "weakref.WeakKeyDictionary[SourceReading, dict[str, Slot]]" = (
    weakref.WeakKeyDictionary()
)


def _requested(reading: SourceReading, unit: str) -> Slot:
    return _REQUESTED.setdefault(reading, {}).setdefault(unit, Slot())


class _ObligationReducer:
    """One page or thread-markup obligation fold over a shared state projection."""

    def __init__(
        self,
        sources: ObligationSources,
        projection,
        byid,
        spk,
        registry: dict,
        dropped: set,
        revision: int | None = None,
        events: list | None = None,
    ):
        self.projection = projection
        self.byid = byid
        self.spk = spk
        self.marks = attribute_marks(byid, spk, registry)
        self.orders = AuthoredOrders(byid, registry)
        self.registry = registry
        self.revision = revision
        self.events = [] if events is None else events
        self.prompts = sources.prompts
        self.records = [record for record, _shown in sources.asking]
        self.answers = gesture_answers(self.events, projection)

        self.exists: dict[int, bool] = {}
        self.local: dict[int, bool] = {}
        for record, shown in sources.asking:
            unit = record["attrs"].get("id")
            self.exists[id(record)] = not ((unit and unit in dropped) or shown)
            self.local[id(record)] = self.exists[id(record)] and self._local(record)

    def _entry(self, record):
        return self.registry[record["tag"]]

    def _declaration(self, record):
        return self._entry(record).get("awaits", {})

    def _local(self, record):
        return matches_when(
            replayed_attrs(record, self.projection),
            self._declaration(record).get("when"),
        )

    def _answered(self, record):
        return self.answers.get(record["attrs"].get("id"), False)

    def inventory(self, settled_away: set[str], prior=None) -> list:
        """Every present source remains identifiable after completion or withdrawal."""
        records = []
        settled_at = {}
        history_readings = {}
        history_keys = {}
        # Only writers in the exact historical revision can originate a request
        # there (`previously_requested`). Other log entries need no historical parse.
        written = {}
        for event in self.events:
            if event["kind"] in verb_writers():
                written.setdefault((event["revision"], event["widget"]), set()).add(
                    event["action"]
                )

        def settled(revision):
            """The seq each report is first settled at through `revision`."""
            if revision not in settled_at:
                settled_at[revision] = report_settled_at(self.events, revision)
            return settled_at[revision]

        def historical_request(old_revision, old, unit):
            previous = old.document.by_id[unit]
            declaration = old.registry[previous["tag"]]["awaits"]
            if old_revision not in history_readings:
                history_readings[old_revision] = page_reading(
                    old, self.events, old_revision
                )
            basis = history_readings[old_revision]
            return previously_requested(
                previous,
                basis.projection,
                declaration.get("when", {}),
                old_revision,
                settled(old_revision),
            )

        # A historical fold reads writers and notes through its revision, plus
        # withdrawals from the complete log. Later page gestures and conversation
        # updates cannot change it. Hash the complete event contents, since test
        # readings and regenerated logs may reuse identities with different values.
        state_events = [
            event
            for event in self.events
            if event["kind"] in verb_writers() or event["kind"] == "note"
        ]
        withdrawals = sorted(taken_back(self.events))
        earlier = []
        remaining = iter(prior()) if prior is not None else iter(())

        # Each earlier revision's registrations, asked of its reading once per read.
        def history():
            yield from earlier
            for old_revision, old in remaining:
                earlier.append((old_revision, old, old.inventory.items))
                yield earlier[-1]

        for record in self.records:
            unit = record["attrs"].get("id")
            owned = self.projection.actions_by_owner.get(unit, {})
            answered = self._answered(record)
            if not self.exists[id(record)] and not (unit in settled_away and answered):
                continue
            registered = (
                self.local[id(record)]
                or matches_when(record["attrs"], self._declaration(record).get("when"))
                or previously_requested(
                    record,
                    self.projection,
                    self._declaration(record).get("when", {}),
                    self.revision,
                    settled(self.revision),
                )
                or any(
                    "answer" in (held[0].get("meaning") or {})
                    for held in owned.values()
                )
            )
            if (
                not registered
                and "restated" not in record["attrs"]
                and prior is not None
            ):
                for old_revision, old, registrations in history():
                    registration = registrations.get(unit)
                    if registration is None or registration.tag != record["tag"]:
                        break
                    if registration.asking:
                        registered = True
                        break
                    if registration.triggers & written.get((old_revision, unit), set()):
                        if old_revision not in history_keys:
                            history_keys[old_revision] = hashlib.sha256(
                                json.dumps(
                                    (
                                        [
                                            event
                                            for event in state_events
                                            if event["revision"] <= old_revision
                                        ],
                                        withdrawals,
                                    ),
                                    sort_keys=True,
                                ).encode()
                            ).digest()
                        if _requested(old, unit).get(
                            history_keys[old_revision],
                            partial(historical_request, old_revision, old, unit),
                        ):
                            registered = True
                            break
                    if registration.restated:
                        break
            if not registered:
                continue
            entry = self._entry(record)
            stands = (
                ended("done")
                if answered
                else on("user")
                if self.local[id(record)]
                else ended("dropped")
            )
            value_verb = entry["awaits"]["value"]
            value, has_content = obligation_value(
                unit,
                value_verb,
                entry["verbs"][value_verb],
                self.byid,
                self.marks,
                self.orders,
                self.projection,
                answered=answered,
            )
            latest_value_seq = max(
                (
                    held[0]["seq"]
                    for coordinate, held in owned.items()
                    if coordinate[2] == value_verb
                ),
                default=0,
            )
            provenance = max(
                (
                    held[0]
                    for held in owned.values()
                    if held[0]["seq"] >= latest_value_seq
                    and "answer" in (held[0].get("meaning") or {})
                ),
                key=lambda event: event["seq"],
                default=None,
            )
            records.append(
                {
                    "id": "widget:" + unit,
                    "source": {"kind": "widget", "id": unit, "tag": record["tag"]},
                    "thread": None,
                    "message": None,
                    "prompt": dict(self.prompts[unit]),
                    "answer": {"value": value, "event": event_reference(provenance)}
                    if has_content
                    else None,
                    "end": None,
                    **stands,
                }
            )
        return records


def page_obligation_readings(
    sources: ObligationSources,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    threads: dict,
    within: dict,
    owed: list[dict],
    *,
    settled_away: set[str] | None = None,
    prior=None,
    revision: int | None = None,
    events: list | None = None,
) -> dict:
    """Obligations in one document basis; a discussion changes attention, not answer:
    an obligation a thread with the agent is about is the agent's (`anchors_with_agent`).
    `owed` is the work the agent's replies promised (`todos.TodoReading.owed`)."""
    reducer = _ObligationReducer(
        sources, projection, byid, spk, registry, dropped, revision, events
    )
    records = reducer.inventory(settled_away or set(), prior)
    discussed(records, anchors_with_agent(threads, owed), within)
    return collection(records)


def thread_obligation_readings(
    events: list,
    registry: dict,
    threads: dict,
    owed: list[dict],
    *,
    reading: ThreadMarkupReading,
) -> dict:
    """Message and thread widget obligations retain inventory when their thread closes,
    with no next actor. While the thread is open, a user turn after the message
    that asks hands the obligation to the agent until the agent answers that turn, and
    until the work a reply after it promised ends, as a thread anchored on a page
    obligation does (`anchors_with_agent`). That turn instead answers a message
    obligation, whether it says words or an emoji. `owed` is
    the work replies promised (`todos.TodoReading.owed`)."""
    reducer = _ObligationReducer(
        obligation_sources(reading.structure, registry),
        reading.projection,
        reading.by_id,
        reading.spoken,
        registry,
        set(),
        events=events,
    )
    records = reducer.inventory(set())
    message_by_widget = widget_messages(reading.structure)
    for record in records:
        source = record["source"]["id"]
        record["thread"] = reading.thread_by_widget[source]
        record["message"] = message_by_widget[source]
    # A question keeps the id and words of its first message, and stands on its
    # newest, which the user's next message answers.
    first: dict[str, str] = {}
    newest: dict[str, tuple[str, dict]] = {}
    for identity, thread in threads.items():
        for message in thread["msgs"]:
            if message.get("obligation"):
                for question in question_ids(message):
                    first.setdefault(question, message["text"])
                    newest[question] = (identity, message)
    records.extend(
        {
            "id": question,
            "source": {"kind": "message", "id": question.removeprefix("message:")},
            "thread": identity,
            "message": message["id"],
            "prompt": {"text": first[question], "target": None},
            "answer": None,
            "end": None,
            **on("user"),
        }
        for question, (identity, message) in newest.items()
    )
    # The newest open to-do on each thread.
    newest_todo: dict[str, int] = {}
    for todo in owed:
        subject = todo["source"]["subject"]
        if subject["kind"] == "thread":
            newest_todo[subject["id"]] = max(
                newest_todo.get(subject["id"], 0), todo["seq"]
            )
    readings: dict[str, ThreadAnswers] = {}
    for record in records:
        thread = threads[record["thread"]]
        if record["thread"] not in readings:
            readings[record["thread"]] = ThreadAnswers(thread)
        answers = readings[record["thread"]]
        in_words = answered_in_words(record)
        asked = answers.seq(record["message"])
        # The first closing in force after the message now asking ends the question,
        # however the thread reopened since: a later message neither answers it nor
        # brings it back.
        closed = min(
            (
                place
                for closing in thread["closings"]
                if (place := closing.get("seq", inf)) > asked
            ),
            default=None,
        )
        if is_open(record) and in_words:
            answer = answers.first_answer(record["message"])
            if closed is None or (answer is not None and answer["seq"] < closed):
                settle_by_words(record, answer)
        if record["next_actor"] is None:
            continue
        turn = answers.owed
        if closed is not None:
            record["next_actor"] = None
        # Only the user's message answers a question asked in words, so a turn the
        # agent owes after it, such as one a user's edit up the thread opens, leaves it
        # theirs.
        elif not in_words and (
            (turn is not None and turn["seq"] > asked)
            or newest_todo.get(record["thread"], 0) > asked
        ):
            record["next_actor"] = "agent"
    return collection(records)


class ThreadAnswers:
    """What answers the questions one thread asks, read once for every obligation
    in it: where each message stands, the user's messages, and the turn the agent
    owes (`unanswered_agent_turn`)."""

    def __init__(self, thread: dict):
        self.messages = thread["msgs"]
        self.position = {message["id"]: i for i, message in enumerate(self.messages)}
        # A message the user deleted or took back says nothing left to answer.
        self.said = [
            i
            for i, message in enumerate(self.messages)
            if message["author"] == "user"
            and bool(message.get("text") or message.get("emoji"))
            and not message.get("ephemeral")
        ]
        self.owed = unanswered_agent_turn(thread)

    def seq(self, message: str) -> int:
        return self.messages[self.position[message]]["seq"]

    def first_answer(self, message: str) -> dict | None:
        """The user's first message after `message`, which answers it."""
        later = bisect_right(self.said, self.position[message])
        return self.messages[self.said[later]] if later < len(self.said) else None


def settled_by_message(records: list[dict]) -> dict[str, list[dict]]:
    """The questions asked in words that each of the user's messages answered, by the
    message's id, each its `id` and the words that asked it. A message answers them
    whatever it says, so these are what the agent reads it against."""
    settled: dict[str, list[dict]] = {}
    for record in records:
        if answered_in_words(record) and standing.answered(record):
            settled.setdefault(record["answer"]["event"]["id"], []).append(
                {"id": record["id"], "text": record["prompt"]["text"]}
            )
    return settled


def answered_in_words(record: dict) -> bool:
    """Whether a conversational answer can settle this source: an agent message's
    obligation."""
    return record["source"]["kind"] == "message"


def waiting_in_thread(
    records: list[dict], threads: dict
) -> Callable[[str, int], list[dict]]:
    """The agent's questions that widgets in a thread asked before a seq and that
    still wait on the user's pick, as a function of the thread and that seq: the
    user's words there may or may not answer them. Each is its `id` and the words
    that asked it: its prompt, the name of the group the message writes round the
    widget or else the widget's own (`obligation_sources.obligation_sources`), else the
    message holding it.

    The open questions are grouped by thread once, so a batch asking for each of
    the user's words reads the records once rather than once per message."""
    asked: dict[str, list[tuple[int, dict]]] = {}
    messages: dict[str, dict[str, dict]] = {}
    for record in records:
        if record["source"]["kind"] != "widget" or not is_open(record):
            continue
        # One a resolve ended waits on nobody.
        if (thread := record["thread"]) is None or record["next_actor"] is None:
            continue
        if thread not in messages:
            messages[thread] = {m["id"]: m for m in threads[thread]["msgs"]}
        message = messages[thread][record["message"]]
        asked.setdefault(thread, []).append(
            (
                message["seq"],
                {
                    "id": record["id"],
                    "text": record["prompt"]["text"] or message["text"],
                },
            )
        )

    def waiting(thread: str, before: int) -> list[dict]:
        return [question for seq, question in asked.get(thread, ()) if seq < before]

    return waiting
