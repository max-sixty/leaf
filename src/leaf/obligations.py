"""Canonical obligations from messages, widgets and updates.

One record contains its prompt, typed answer, completion and next actor. Its thread
and exact owning message locate frozen sources without depending on a live renderer.
A widget source owns identity; an enclosing widget (`x-encloses`) contributes only
prompt words and arrival. A `records` declaration expands a widget's bound external
input using its data contract's record list and key. Each record owns the stable
widget-and-unit identity and reads its own action coordinate; replacing that input
changes membership without changing the answers of retained records.
The inventory is complete even when a work queue hides a resolved thread or an
older prompt.

On the page, the user answers an obligation only through its source: a widget
through the actions its `x-awaits` declares, an agent message through a reply or
settling reaction in its thread. Leaf adds no control of its own, such as a generic
Done, and nothing reaches On Me unless a widget or a thread answers it (`todos` records
the decision). Any widget may ask by declaring `x-awaits`; content that doesn't is
asked about in a thread anchored to it.

An update the user handed over publishes a record of its own (`update_obligation`),
built by the fold that decides which updates are handed over and settled
(`workflows.handed_over`). Its next actor is the agent while it owes the update an
answer, the user once a harness handed the update back, and nobody once a reply
answered it; `response_address` derives the operation that answers it. A thread is
never an obligation itself: its messages publish them.

An agent message carrying `obligation` asks a question the user answers in words:
their next message in its thread, or a reaction there whose token settles it, is its
answer. The message owns identity and prompt; its thread only locates it.

That answer takes effect at once, whatever the words say, so the user can clear On Me
without waiting for the agent. Only the agent can read whether they answered, and
where they asked back or the step is still to do, its reply's `obligation` names the
question by id, as one reply can name each question the user's message answered. The
question then stands open again under the id and the words of the message that first
asked it, so a plan step naming it follows under the same title, and stands on that
reply, which On Me shows and the user's next message answers. The user chose this on
4 November 2026 over handing the question to the agent until it replied, as a widget's
does, which left On Me full until the agent had read each reply, and over asking again
under a new id, which left the plan step reading done. Asking again is the declaration
asking is, an `obligation` naming the questions, rather than a second one beside it.

A record says where it stands in the fields every record does (`standing`), and this
module is their producer for what the user owes. An open one is `waiting` on its next
actor. A `done` one ended one of three ways: answered, its typed answer in the record
(`standing.answered`); answered elsewhere, a question an agent message asks that the
agent ended `done` because the user answered on another surface, with its `end` and no
answer value; or `dropped`, an obligation the document no longer makes or a question an
agent message asks that the agent ended `dropped`. A page widget's obligation is never
answered elsewhere: an answer given elsewhere goes into the widget's declared state in
a revision, which records the value itself. No revision can write the state of a
widget frozen in a message, so the agent ends its question as it ends one asked in
words (`asked_in_a_message`)."""

import hashlib
import json
from bisect import bisect_right
from collections.abc import Callable
from functools import partial
from math import inf
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import quote

from leaf import standing
from leaf.events import (
    awaits_agent,
    is_reaction,
    report_settled_at,
    taken_back,
    unanswered_agent_turn,
)
from leaf.gesture_words import element_name
from leaf.page_memory import Slot
from leaf.projection import (
    AuthoredOrders,
    FrozenThreadReading,
    StateProjection,
    attribute_marks,
    enclosing_widgets,
    folded_value,
    markup_value,
    obligation_value,
    page_reading,
    projected_action_holders,
)
from leaf.registry.contract import exhibits, matches_when
from leaf.registry.kernel import verb_writers
from leaf.registry.reactions import reaction_tokens
from leaf.standing import ended, is_open, on
from leaf.thread_context import widget_messages

if TYPE_CHECKING:
    from leaf.todos import TodoReading


def local_obligation_entry(entry: dict) -> bool:
    """Whether a widget can originate an obligation when its predicate holds."""
    return entry.get("x-awaits") is not None


def encloses(entry: dict) -> bool:
    """Whether this widget frames the obligations inside it (`x-encloses`): its leading
    heading gives their prompt, and going to one of them lands on it."""
    return bool(entry.get("x-encloses"))


def end_question(record: dict, ending: dict) -> None:
    """Retire a question asked in a thread message that the agent ended with
    `todo_end`: `done` where the user answered it on another surface, `dropped`
    where it no longer applies. An end records no answer value."""
    record.update(ended("done" if ending["outcome"] == "done" else "dropped"))
    record["end"] = {"detail": ending["detail"], "event": event_reference(ending)}


def ended_as(record: dict) -> str:
    """How a done obligation ended, in a refusal's words."""
    if record["outcome"] == "dropped":
        return "withdrawn"
    return "answered" if record["end"] is None else "answered elsewhere"


def question_ids(message: dict) -> list[str]:
    """The ids of the questions an agent message asks in words: the ones its
    `obligation` lists, each the id of the message that first asked it, or where it is
    `true`, its own."""
    asked = message["obligation"]
    return [f"message:{message['id']}"] if asked is True else asked


def settle_by_words(
    record: dict, asked: int, answer: dict | None, ending: dict | None
) -> None:
    """Settle a message obligation from the user's message that answers it and the
    agent's `todo_end` on its id, whichever came first, where the message now asking
    it stands at seq `asked`, so a reopening outlasts an end before it. An end records
    no answer, since the user's words are not in the log; the user's message after an
    end reopens nothing, as the end already retired it."""
    if ending is not None and (
        ending["seq"] < asked or (answer is not None and answer["seq"] < ending["seq"])
    ):
        ending = None
    if ending is not None:
        end_question(record, ending)
    elif answer is not None:
        record.update(ended("done"))
        record["answer"] = {
            "value": {key: answer[key] for key in ("text", "token") if key in answer},
            "event": event_reference(answer),
        }


class ObligationRegistration(NamedTuple):
    """Compact registration inputs and the last event-dependent registration.

    No parser records or holder chains survive here. The last dynamic answer uses
    the canonical state fold and is keyed by its complete historical event basis.
    """

    tag: str
    asking: bool
    restated: bool
    triggers: frozenset[str]
    requested: Slot


def obligation_registrations(
    document, registry: dict
) -> dict[str, ObligationRegistration]:
    """Compact immutable registration inputs, separate from a revision's parse."""
    return {
        unit: ObligationRegistration(
            record["tag"],
            matches_when(record["attrs"], declaration.get("when")),
            "restated" in record["attrs"],
            frozenset(
                verb
                for verb, spec in registry[record["tag"]].get("x-state", {}).items()
                if (spec.get("record") or {}).get("kind") == "value"
                and spec["record"]["attr"] in declaration.get("when", {})
            ),
            Slot(),
        )
        for unit, record in document.by_id.items()
        if (declaration := registry.get(record["tag"], {}).get("x-awaits")) is not None
    }


def settles(reaction: dict, turn: str, tokens: dict) -> bool:
    """Whether a message is the user's reaction on the agent's `turn` with a token
    the registry declares `settles` (`$reactions`), which answers the question that
    turn asks as a reply would. `tokens` is `$reactions.tokens`."""
    return (
        is_reaction(reaction)
        and reaction["author"] == "user"
        and reaction.get("parent") == turn
        and bool((tokens.get(reaction["token"]) or {}).get("settles"))
    )


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
    input), which differ for edits and widget actions in frozen markup.
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


def answer_verbs(entry: dict) -> dict:
    """Each x-state verb whose current state answers this widget's local obligation,
    mapped to the condition that state has to meet (x-awaits.answered)."""
    return (entry.get("x-awaits") or {}).get("answered") or {}


def verb_answers(
    rec: dict,
    entry: dict,
    verb: str,
    projection: StateProjection,
    byid: dict,
    marks: dict,
    registry: dict,
    holders: dict[str, dict],
    unit: str | None = None,
) -> bool:
    """Whether one answering verb's declared condition holds for this widget now.

    The condition reads current state and nothing else. `empty` asks the projected
    containment the verb's position records leave; an attribute or value record reads
    through authored markup (`marks`, the document's `projection.attribute_marks`) as
    well as the fold, so a version that honors the answer keeps it answered and a
    cleared value opens the obligation again; any other verb answers while one of its
    actions stands on the widget.
    """
    condition = answer_verbs(entry)[verb]
    if not matches_when(replayed_attrs(rec, projection), condition.get("when")):
        return False
    if empty := condition.get("empty"):
        return container_empty(rec, empty, byid, registry, holders)
    # A record obligation supplies its datum unit; ordinary obligations read the
    # widget coordinate. Both use the same action fold.
    owner = rec["attrs"].get("id")
    unit = unit if unit is not None else owner
    held = projection.actions.get((owner, unit, verb))
    if "detail" in condition:
        return held is not None and all(
            key in held[0]["detail"] and held[0]["detail"][key] == value
            for key, value in condition["detail"].items()
        )
    spec = entry["x-state"][verb]
    record = spec.get("record")
    if record and record["kind"] in ("attribute", "value"):
        value = folded_value(*held) if held else markup_value(unit, spec, byid, marks)
        return value not in (None, "", [])
    return held is not None


def obligation_answered(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    marks: dict,
    registry: dict,
    holders: dict[str, dict] | None = None,
) -> bool:
    """Whether the user's own state answers this obligation: one of its answering verbs'
    conditions holds."""
    if holders is None:
        holders = projected_action_holders(projection, byid, registry)
    return any(
        verb_answers(rec, entry, verb, projection, byid, marks, registry, holders)
        for verb in answer_verbs(entry)
    )


def anchors_with_agent(threads: dict, owed: list[dict]) -> list[dict]:
    """The anchors of threads the agent owes: an open one whose next word is
    the agent's, or one holding an open to-do, the work a reply there promised
    (`todos.todo_reading`). `owed` is `todos.TodoReading.owed`.

    An open obligation such a thread is about is the agent's turn rather than the user's:
    the user has said something about it and waits on the answer, so it leaves
    their list until the agent answers. A reply that promises work settles the
    message but leaves the obligation the agent's until the agent ends the to-do,
    through a resolution too, so a decision the user put off until other work lands
    stays off their list. Neither is an answer, since the widget's state is untouched,
    and the obligation stays open, its controls live. The browser receives the lists this leaves rather than deciding
    again, so On Me's count and `page state` cannot disagree about whose turn it is.

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
        if (awaits_agent(thread) or identity in promised)
        and (anchor := thread["anchor"])
        and anchor.get("section")
    ]


def discussed_by(records: list[dict], within: dict) -> Callable[[dict], list[dict]]:
    """The reading of which obligations among `records` a thread anchored at a given
    anchor is about, as a function of the anchor.

    A section is about the innermost obligation whose widget encloses it, answered or not;
    failing one, about every obligation whose widget it encloses; failing those, about
    every obligation whose prompt target (its enclosing widget) is the innermost to
    enclose it. So a note on one obligation's option, or on a part of a frame holding
    one obligation, leaves its framed sibling out, while one on the frame's heading or on
    a section holding the frame is about them all. `within` is the document's
    containment (`Passages.enclosing`). A datum identity narrows an owning widget's
    record obligations to the exact case being discussed.

    The records are indexed once by source, prompt target and each id enclosing
    their source, so a caller asking for every thread on the page reads each
    thread's anchor against the indexes rather than every record again.
    """
    items: dict[str, list[dict]] = {}
    framed: dict[str, list[dict]] = {}
    enclosed: dict[str, list[dict]] = {}
    for record in records:
        items.setdefault(record["source"]["id"], []).append(record)
        framed.setdefault(record["prompt"]["target"], []).append(record)
        for around in set(within.get(record["source"]["id"], ())):
            enclosed.setdefault(around, []).append(record)

    def about(anchor: dict) -> list[dict]:
        section = anchor["section"]
        chain = within.get(section, ())
        item = next((items[i] for i in reversed(chain) if i in items), None)
        held = (
            item
            if item is not None
            else enclosed.get(section)
            or next((framed[i] for i in reversed(chain) if i in framed), [])
        )
        datum = anchor.get("identity", anchor.get("datum"))
        return [
            record
            for record in held
            if datum is None
            or record["source"]["id"] != section
            or "unit" not in record["source"]
            or record["source"]["unit"] == datum
        ]

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


def shown_in(rec: dict, registry: dict) -> bool:
    """Inside an element whose tag declares x-exhibit, a widget is shown rather than
    asked, so it puts nothing on the user's list, whether or not the declaration's
    condition holds there. The condition decides only whether it also takes no input
    (`quoted_in`): a widget in an interactive `lf-sample` records its actions in the
    page's log and Undo as a demonstration, and a page's On Me holds only what the page
    itself asks. Same holder-chain walk as `quoted_in`."""
    return any(
        bool(registry.get(node["tag"], {}).get("x-exhibit"))
        for node in enclosing_widgets(rec)
    )


def quoted_in(rec: dict, registry: dict) -> bool:
    """Inside an element the registry marks x-exhibit where its condition holds, a
    widget is a mention rather than a use: it takes no input and asks nothing.

    The holder chain answers it, which is the walk `enclosing_slot` makes and the
    one `quotedBy` makes over the DOM for a descriptor's own `quoted` flag. Asked of
    `spoken` instead, containment became a question about the page's words: the
    reading that says what stands around one widget walks every character of the
    version to do it, so an action POST on a 90KB page spent forty milliseconds
    finding out what a single id sat in. It reads a record rather than an id for the
    same reason `quotedBy` takes an element — an element the author left unnamed
    stands where it stands."""
    return any(
        exhibits(node["attrs"], registry.get(node["tag"], {}))
        for node in enclosing_widgets(rec)
    )


def container_empty(
    owner: dict,
    empty: dict,
    byid: dict,
    registry: dict,
    holders: dict[str, dict],
) -> bool:
    """Whether the one member container `empty` names inside `owner` holds no
    vocabulary members under the projected holder relation.

    A predicate over the same containment the position records change, so undoing
    or superseding one moves the arrangement and the answer in one operation.
    """

    def holder(record: dict):
        unit = record["attrs"].get("id")
        return holders.get(unit, record.get("holder"))

    def inside(record: dict, ancestor: dict) -> bool:
        seen = set()
        while record is not None and id(record) not in seen:
            if record is ancestor:
                return True
            seen.add(id(record))
            record = holder(record)
        return False

    containers = [
        record
        for record in byid.values()
        if record["tag"] == empty["within"]
        and inside(record, owner)
        and matches_when(record["attrs"], empty["when"])
    ]
    if len(containers) != 1:
        return False
    container = containers[0]
    return not any(
        record is not container
        and record["tag"] in registry
        and holder(record) is container
        for record in byid.values()
    )


def answering_action(
    rec: dict,
    entry: dict,
    verb: str,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
    *,
    registered: bool = False,
    unit: str | None = None,
) -> bool:
    """Whether an action of `verb`, in force in `projection`, answers its widget's
    obligation: the instance asks or retains an earlier registration, and the verb's
    own condition holds with it in place. Editable answers retain user provenance
    after the author suppresses the request. Admission stamps `meaning.answer` on
    exactly these."""
    awaits = entry.get("x-awaits") or {}
    return (
        verb in answer_verbs(entry)
        and (
            registered
            or matches_when(replayed_attrs(rec, projection), awaits.get("when"))
        )
        and verb_answers(
            rec,
            entry,
            verb,
            projection,
            byid,
            attribute_marks(byid, spk, registry),
            registry,
            projected_action_holders(projection, byid, registry),
            unit,
        )
    )


class ObligationSources(NamedTuple):
    """The widgets one document declares that can ask the user, read under one
    vocabulary.

    `asking` holds each declared widget, with whether it stands inside an exhibit
    (`shown_in`).
    `nodes` maps each id to its authoring node, whose words name an obligation's
    prompt.

    These depend on the document and the vocabulary alone, and finding them is most
    of the cost of reading a page's obligations. A stored revision's reading
    therefore holds them across requests (`passages.SourceReading`), and each reading
    against the log, such as admission's before and after an event, reads only what
    the log decides."""

    asking: tuple[tuple[dict, bool], ...]
    nodes: dict[str, dict]


def obligation_sources(source, registry: dict) -> ObligationSources:
    """Read `ObligationSources` from a page document or a frozen thread's structure,
    whose fragments each hold one message's markup."""
    documents = (
        list(source.fragments.values()) if hasattr(source, "fragments") else [source]
    )

    def nodes(content):
        for node in content:
            if isinstance(node, dict):
                yield node
                yield from nodes(node["content"])

    declared = [
        record
        for document in documents
        for record in document.lf_elements
        if local_obligation_entry(registry.get(record["tag"]) or {})
    ]
    return ObligationSources(
        tuple((record, shown_in(record, registry)) for record in declared),
        {
            node["attrs"]["id"]: node
            for document in documents
            for node in nodes(document.authoring.content)
            if node["attrs"].get("id")
        },
    )


class _ObligationReducer:
    """One page or frozen-thread obligation fold over a shared state projection."""

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
        data: dict | None = None,
    ):
        self.projection = projection
        self.byid = byid
        self.spk = spk
        self.marks = attribute_marks(byid, spk, registry)
        self.orders = AuthoredOrders(byid, registry)
        self.registry = registry
        self.revision = revision
        self.events = [] if events is None else events
        self.data = data or {"sources": {}}
        self.nodes = sources.nodes
        self.records = [record for record, _shown in sources.asking]
        self.positioned_holders = projected_action_holders(projection, byid, registry)

        self.exists: dict[int, bool] = {}
        self.local: dict[int, bool] = {}
        for record, shown in sources.asking:
            unit = record["attrs"].get("id")
            self.exists[id(record)] = not ((unit and unit in dropped) or shown)
            self.local[id(record)] = self.exists[id(record)] and self._local(record)

    def _entry(self, record):
        return self.registry[record["tag"]]

    def _declaration(self, record):
        return self._entry(record).get("x-awaits", {})

    def _local(self, record):
        return matches_when(
            replayed_attrs(record, self.projection),
            self._declaration(record).get("when"),
        )

    def _holder(self, record):
        unit = record["attrs"].get("id")
        return self.positioned_holders.get(unit, record.get("holder"))

    def _answered(self, record):
        return obligation_answered(
            record,
            self._entry(record),
            self.projection,
            self.byid,
            self.marks,
            self.registry,
            self.positioned_holders,
        )

    def _surface(self, record):
        """The reading and arrival region the user is sent to for this source: the
        nearest enclosing widget (`x-encloses`) holding it, or the source
        itself."""
        holder = self._holder(record)
        while holder:
            if encloses(self.registry.get(holder["tag"]) or {}):
                return holder
            holder = self._holder(holder)
        return record

    def _record_inventory(self, record: dict) -> list[dict]:
        """One obligation per current bound record, identified independently of order.

        A source's records declaration owns its item list and key; the obligation
        adds only prompt words and the answer condition. Replaced or removed data
        therefore cannot leave phantom obligations behind.
        """
        owner = record["attrs"]["id"]
        entry = self._entry(record)
        declaration = entry["x-awaits"]
        records = declaration["records"]
        binding = entry["x-data"][records["input"]]
        source = self.data["sources"].get(record["attrs"].get(binding["source"]))
        if (
            not source
            or "value" not in source
            or source["contract"] != binding["contract"]
        ):
            return []
        contract = self.registry["$data"]["contracts"][binding["contract"]]["records"]
        value = source["value"]
        items = value.get(contract["items"]) if isinstance(value, dict) else None
        result = []
        for datum in items or []:
            unit = datum[contract["key"]]
            answered = any(
                verb_answers(
                    record,
                    entry,
                    verb,
                    self.projection,
                    self.byid,
                    self.marks,
                    self.registry,
                    self.positioned_holders,
                    unit,
                )
                for verb in answer_verbs(entry)
            )
            verb = declaration["value"]
            value, present = obligation_value(
                owner,
                verb,
                entry["x-state"][verb],
                self.byid,
                self.marks,
                self.orders,
                self.projection,
                answered=answered,
                unit=unit,
            )
            held = self.projection.actions.get((owner, unit, verb))
            stands = (
                ended("done")
                if answered
                else on("user")
                if self.local[id(record)]
                else ended("dropped")
            )
            result.append(
                {
                    "id": f"widget:{quote(owner, safe='')}:{quote(unit, safe='')}",
                    "source": {
                        "kind": "widget",
                        "id": owner,
                        "tag": record["tag"],
                        "unit": unit,
                    },
                    "thread": None,
                    "message": None,
                    "prompt": {
                        "text": datum[records["label"]],
                        "target": self._surface(record)["attrs"]["id"],
                    },
                    "answer": {
                        "value": value,
                        "event": event_reference(held[0]) if held else None,
                    }
                    if present
                    else None,
                    "end": None,
                    **stands,
                }
            )
        return result

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
            declaration = old.registry[previous["tag"]]["x-awaits"]
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

        def history():
            yield from earlier
            for previous in remaining:
                earlier.append(previous)
                yield previous

        for record in self.records:
            unit = record["attrs"].get("id")
            owned = self.projection.actions_by_owner.get(unit, {})
            record_units = self._declaration(record).get("records")
            answered = False if record_units else self._answered(record)
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
                for old_revision, old in history():
                    registration = old.inventory.items.get(unit)
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
                        if registration.requested.get(
                            history_keys[old_revision],
                            partial(historical_request, old_revision, old, unit),
                        ):
                            registered = True
                            break
                    if registration.restated:
                        break
            if not registered:
                continue
            if record_units:
                records.extend(self._record_inventory(record))
                continue
            surface = self._surface(record)
            entry = self._entry(record)
            stands = (
                ended("done")
                if answered
                else on("user")
                if self.local[id(record)]
                else ended("dropped")
            )
            value_verb = entry["x-awaits"]["value"]
            value, has_content = obligation_value(
                unit,
                value_verb,
                entry["x-state"][value_verb],
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
            text = element_name(self.nodes[surface["attrs"]["id"]], self.registry)
            records.append(
                {
                    "id": "widget:" + unit,
                    "source": {"kind": "widget", "id": unit, "tag": record["tag"]},
                    "thread": None,
                    "message": None,
                    "prompt": {"text": text, "target": surface["attrs"]["id"]},
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
    log: "TodoReading",
    *,
    settled_away: set[str] | None = None,
    prior=None,
    revision: int | None = None,
    events: list | None = None,
    data: dict | None = None,
) -> dict:
    """Obligations in one document basis; a discussion changes attention, not answer:
    an obligation a thread with the agent is about is the agent's (`anchors_with_agent`).
    `log` is the page's `todos.TodoReading`: its `owed` holds the work the agent's
    replies promised."""
    reducer = _ObligationReducer(
        sources, projection, byid, spk, registry, dropped, revision, events, data
    )
    records = reducer.inventory(settled_away or set(), prior)
    discussed(records, anchors_with_agent(threads, log.owed), within)
    return collection(records)


def thread_obligation_readings(
    events: list,
    registry: dict,
    threads: dict,
    log: "TodoReading",
    *,
    reading: FrozenThreadReading,
    data: dict | None = None,
) -> dict:
    """Message and frozen widget obligations retain inventory when their thread closes,
    with no next actor. While the thread is open, a user turn after the message
    that asks hands the obligation to the agent until the agent answers that turn, and
    until the work a reply after it promised ends, as a thread anchored on a page
    obligation does (`anchors_with_agent`). That turn instead answers a message
    obligation, as does a reaction on the message whose token settles it; `log` is the
    page's `todos.TodoReading`, whose `ends` hold the agent's `todo_end` on each id."""
    reducer = _ObligationReducer(
        obligation_sources(reading.structure, registry),
        reading.projection,
        reading.by_id,
        reading.spoken,
        registry,
        set(),
        events=events,
        data=data,
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
    tokens = reaction_tokens(registry)
    # The newest open to-do on each thread.
    newest_todo: dict[str, int] = {}
    for todo in log.owed:
        subject = todo["source"]["subject"]
        if subject["kind"] == "thread":
            newest_todo[subject["id"]] = max(
                newest_todo.get(subject["id"], 0), todo["seq"]
            )
    readings: dict[str, ThreadAnswers] = {}
    for record in records:
        thread = threads[record["thread"]]
        if record["thread"] not in readings:
            readings[record["thread"]] = ThreadAnswers(thread, tokens)
        answers = readings[record["thread"]]
        in_words = answered_in_words(record)
        asked = answers.seq(record["message"])
        if is_open(record) and in_words:
            answer = answers.first_answer(record["message"])
            settle_by_words(record, asked, answer, log.ends.get(record["id"]))
        # No revision can write a frozen widget's state, so an answer in words
        # retires its question through the agent's end, as for a question in words.
        elif is_open(record) and (ending := log.ends.get(record["id"])):
            end_question(record, ending)
        if record["next_actor"] is None:
            continue
        owed = answers.owed
        if thread["resolved"]:
            record["next_actor"] = None
        # Only the user's words answer a question asked in words, so a turn the agent
        # owes after it, such as one a user's edit up the thread opens, leaves it theirs.
        elif not in_words and (
            (owed is not None and owed["seq"] > asked)
            or newest_todo.get(record["thread"], 0) > asked
        ):
            record["next_actor"] = "agent"
    return collection(records)


class ThreadAnswers:
    """What answers the questions one thread asks, read once for every obligation
    in it: where each message stands, the user's messages in words, each message's
    first reaction whose token settles it (`settles`), and the turn the agent owes
    (`unanswered_agent_turn`)."""

    def __init__(self, thread: dict, tokens: dict):
        self.messages = thread["msgs"]
        self.position = {message["id"]: i for i, message in enumerate(self.messages)}
        # A message the user deleted has no words left to answer.
        self.words = [
            i
            for i, message in enumerate(self.messages)
            if message["author"] == "user"
            and not is_reaction(message)
            and bool(message.get("text"))
            and not message.get("ephemeral")
        ]
        self.settling: dict[str, int] = {}
        for i, message in enumerate(self.messages):
            parent = message.get("parent")
            if parent is not None and settles(message, parent, tokens):
                self.settling.setdefault(parent, i)
        self.owed = unanswered_agent_turn(thread)

    def seq(self, message: str) -> int:
        return self.messages[self.position[message]]["seq"]

    def first_answer(self, message: str) -> dict | None:
        """The first message after `message` that answers it: the user's words, or
        their reaction on it whose token settles it."""
        at = self.position[message]
        later = bisect_right(self.words, at)
        found = [i for i in (self.settling.get(message),) if i is not None]
        if later < len(self.words):
            found.append(self.words[later])
        return self.messages[min(found)] if found else None


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
    """Whether a conversational answer, or agent ending, can settle this source: an
    agent message's obligation."""
    return record["source"]["kind"] == "message"


def asked_in_a_message(record: dict) -> bool:
    """Whether the agent ends this obligation with `todo_end` when the user answers
    it elsewhere: a question an agent message asks, in words or by a widget frozen
    in it. A page widget's answer goes into its state in a revision instead."""
    return (
        record["source"]["kind"] in {"message", "widget"}
        and record["message"] is not None
    )


def waiting_in_thread(
    records: list[dict], threads: dict
) -> Callable[[str, int], list[dict]]:
    """The agent's questions frozen as widgets in a thread, asked before a seq, that
    still wait on the user's pick, as a function of the thread and that seq: the
    user's words there may or may not answer them. Each is its `id` and the words
    that asked it: the widget's framing heading, else the message holding it.

    The open questions are grouped by thread once, so a batch asking for each of
    the user's words reads the records once rather than once per message."""
    asked: dict[str, list[tuple[int, dict]]] = {}
    messages: dict[str, dict[str, dict]] = {}
    for record in records:
        if record["source"]["kind"] != "widget" or not is_open(record):
            continue
        if (thread := record["thread"]) is None:
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
