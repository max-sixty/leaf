"""Canonical obligations from messages, user tasks, widgets and updates.

One record contains its prompt, typed answer, completion and next actor. Its thread
and exact owning message locate frozen sources without depending on a live renderer.
A widget source owns identity; an enclosing widget (`x-encloses`) contributes only
prompt words and arrival. A `records` declaration expands a widget's bound external
input using its data contract's record list and key. Each record owns the stable
widget-and-unit identity and reads its own action coordinate; replacing that input
changes membership without changing the answers of retained records.
The inventory is complete even when a work queue hides a resolved thread or an
older prompt. A user-owned to-do publishes an obligation with explicit completion;
agent-owned to-dos stay work records.

An update the user handed over publishes a record of its own (`update_obligation`),
built by the fold that decides which updates are handed over and settled
(`workflows.handed_over`). Its next actor is the agent while it owes the update an
answer, the user once a harness handed the update back, and nobody once a reply
answered it; `response_address` derives the operation that answers it. A thread is
never an obligation itself: its messages publish them.

An agent message carrying `obligation` is a question the user answers in words:
their next message in its thread, or a reaction there whose token settles it, is its
answer. The message owns identity and prompt; its thread only locates it. A user to-do
instead ends explicitly, so discussing the task never claims the work is complete.

A record's `status` is one of four, and this module is their one producer: `open`;
`answered`, its typed answer in the record; `answered_elsewhere`, a message
obligation the agent ended `done` because the user answered on another surface, with no
answer value; and `withdrawn`, an obligation the document no longer makes or a message
obligation the agent ended `dropped`. A state-answered obligation never takes
`answered_elsewhere`: an answer given elsewhere goes into the widget's declared
state in a revision, which records the value itself."""

import hashlib
import json
from functools import partial
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import quote

from leaf.events import (
    awaits_agent,
    is_reaction,
    retractions,
    taken_back,
    unanswered_agent_turn,
)
from leaf.gesture_words import element_name
from leaf.page_memory import Slot
from leaf.projection import (
    FrozenThreadReading,
    StateProjection,
    enclosing_widgets,
    folded_value,
    markup_value,
    obligation_value,
    page_reading,
    projected_action_holders,
    state_projection,
)
from leaf.registry.contract import exhibits, matches_when
from leaf.registry.kernel import verb_writers
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


def settle_by_words(record: dict, answer: dict | None, ending: dict | None) -> None:
    """Settle a message obligation from the user's message that answers it and the
    agent's `todo_end` on its id, whichever came first. An end records no answer,
    since the user's words are not in the log; a message after an end reopens
    nothing, as the end already retired it."""
    if ending is not None and answer is not None and answer["seq"] < ending["seq"]:
        ending = None
    if ending is not None:
        record["status"] = (
            "answered_elsewhere" if ending["state"] == "done" else "withdrawn"
        )
        record["end"] = {"detail": ending["detail"], "event": event_reference(ending)}
        record["next_actor"] = None
    elif answer is not None:
        record["status"] = "answered"
        record["answer"] = {
            "value": {key: answer[key] for key in ("text", "token") if key in answer},
            "event": event_reference(answer),
        }
        record["next_actor"] = None


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
        "unanswered": [record for record in records if record["status"] == "open"],
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
    a move, `answered` once `answer`, the reply that answered it, stands. Its prompt
    names no words of its own: a row reads its thread's or widget's name."""
    return {
        "id": f"update:{source}",
        "source": {"kind": "update", "id": source, "subject": subject},
        "thread": thread,
        "message": message,
        "prompt": {"text": None, "target": subject["id"]},
        "answer": {"value": None, "event": event_reference(answer)} if answer else None,
        "status": "answered" if answer else "open",
        "end": None,
        "next_actor": next_actor,
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
    held = [
        winner
        for coordinate, winner in projection.desired.items()
        if coordinate[1] == unit
    ]
    for e, spec in sorted(held, key=lambda item: item[0]["seq"]):
        if (spec.get("record") or {}).get("kind") == "value":
            attrs = {**attrs, spec["record"]["attr"]: folded_value(e, spec)}
    return attrs


def previously_requested(
    record: dict,
    projection: StateProjection,
    when: dict,
    revision: int | None,
    events: list,
    byid: dict,
    spoken: dict,
    registry: dict,
    cache: dict,
) -> bool:
    """Registration at relevant gestures in their own immutable source basis.

    The canonical state fold reads each relevant log prefix, sharing cached prefixes
    across sources. This includes report settlement and Undo without a second replay
    rule. Surviving actions and reports can originate a conditional request between
    document revisions; retracted actions cannot.
    """
    unit = record["attrs"].get("id")
    for coordinate, (event, spec) in projection.classified.values():
        effect = spec.get("record") or {}
        if (
            coordinate[:2] != (unit, unit)
            or (event["kind"] == "action" and event["id"] not in projection.in_force)
            or (revision is not None and event["revision"] != revision)
            or effect.get("kind") != "value"
            or effect["attr"] not in when
        ):
            continue
        key = (id(projection), event["seq"])
        if key not in cache:
            cache[key] = state_projection(
                [item for item in events if item["seq"] <= event["seq"]],
                byid,
                spoken,
                registry,
                revision,
                floors=retractions(events, revision) if revision is not None else {},
                withdrawn=taken_back(events),
            )
        if matches_when(replayed_attrs(record, cache[key]), when):
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
    spk: dict,
    registry: dict,
    holders: dict[str, dict],
    unit: str | None = None,
) -> bool:
    """Whether one answering verb's declared condition holds for this widget now.

    The condition reads current state and nothing else. `empty` asks the projected
    containment the verb's position records leave; an attribute or value record reads
    through authored markup as well as the fold, so a version that honors the answer
    keeps it answered and a cleared value opens the obligation again; any other verb answers
    while one of its actions stands on the widget.
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
        value = (
            folded_value(*held)
            if held
            else markup_value(unit, spec, byid, spk, registry)
        )
        return value not in (None, "", [])
    return held is not None


def obligation_answered(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
    holders: dict[str, dict] | None = None,
) -> bool:
    """Whether the user's own state answers this obligation: one of its answering verbs'
    conditions holds."""
    if holders is None:
        holders = projected_action_holders(projection, byid, registry)
    return any(
        verb_answers(rec, entry, verb, projection, byid, spk, registry, holders)
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
    again, so On me's count and `page state` cannot disagree about whose turn it is.

    Which kind of thread does not enter into it: a seat's, a quote on the obligation's
    words, a design note, or one the agent opened that the user has answered. A to-do
    the agent opened on an element is not a thread's and holds nothing: work on a
    section doesn't say whether the user's decision there waits on it."""
    promised = {
        todo["subject"]["id"] for todo in owed if todo["subject"]["kind"] == "thread"
    }
    return [
        anchor
        for identity, thread in threads.items()
        if (awaits_agent(thread) or identity in promised)
        and (anchor := thread["anchor"])
        and anchor.get("section")
    ]


def discussed_by(anchor: dict, records: list[dict], within: dict) -> list[dict]:
    """The obligations among `records` a thread anchored at `anchor` is about.

    A section is about the innermost obligation whose widget encloses it, answered or not;
    failing one, about every obligation whose widget it encloses; failing those, about
    every obligation whose prompt target (its enclosing widget) is the innermost to
    enclose it. So a note on one obligation's option, or on a part of a frame holding
    one obligation, leaves its framed sibling out, while one on the frame's heading or on
    a section holding the frame is about them all. `within` is the document's
    containment (`Passages.enclosing`). A datum identity narrows an owning widget's
    record obligations to the exact case being discussed.
    """
    section = anchor["section"]
    chain = within.get(section, ())
    items: dict[str, list[dict]] = {}
    framed: dict[str, list[dict]] = {}
    for record in records:
        items.setdefault(record["source"]["id"], []).append(record)
        framed.setdefault(record["prompt"]["target"], []).append(record)
    item = next((items[i] for i in reversed(chain) if i in items), None)
    about = (
        item
        if item is not None
        else [
            record
            for record in records
            if section in within.get(record["source"]["id"], ())
        ]
        or next((framed[i] for i in reversed(chain) if i in framed), [])
    )
    datum = anchor.get("identity", anchor.get("datum"))
    return [
        record
        for record in about
        if datum is None
        or record["source"]["id"] != section
        or "unit" not in record["source"]
        or record["source"]["unit"] == datum
    ]


def thread_topics(threads: dict, records: list[dict], within: dict) -> dict[str, list]:
    """Each thread's id → the page obligations among `records` it is about
    (`discussed_by`), by the section its anchor names now; a thread with no section
    is about none."""
    return {
        identity: discussed_by(anchor, records, within)
        if (anchor := thread["anchor"]) and "section" in anchor
        else []
        for identity, thread in threads.items()
    }


def waiting_about(
    widget: str, records: list[dict], threads: dict, within: dict
) -> list[dict]:
    """The records among `records` that still wait on the user's words in a thread
    about an obligation of `widget` (`thread_topics`): the questions the agent asked
    there, which an answer to that obligation may or may not settle. Each is its `id`
    and the words that asked it (`prompt.text`)."""
    page = [
        record
        for record in records
        if record["thread"] is None and record["source"]["kind"] == "widget"
    ]
    asked = [
        record
        for record in records
        if record["thread"] is not None
        and record["status"] == "open"
        and record["next_actor"] == "user"
        and answered_in_words(record)
    ]
    topics = thread_topics(
        {record["thread"]: threads[record["thread"]] for record in asked}, page, within
    )
    return [
        {"id": record["id"], "text": record["prompt"]["text"]}
        for record in asked
        if any(about["source"]["id"] == widget for about in topics[record["thread"]])
    ]


def discussed(records: list[dict], anchors: list[dict], within: dict) -> None:
    """Hand each open obligation discussed by `anchors` (`discussed_by`) to the agent."""
    for anchor in anchors:
        for record in discussed_by(anchor, records, within):
            if record["next_actor"] == "user":
                record["next_actor"] = "agent"


def quoted_in(rec: dict, registry: dict) -> bool:
    """Inside an element the registry marks x-exhibit, a widget is a mention
    rather than a use, and asks nothing.

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
            spk,
            registry,
            projected_action_holders(projection, byid, registry),
            unit,
        )
    )


class ObligationSources(NamedTuple):
    """The widgets one document declares that can ask the user, read under one
    vocabulary.

    `asking` holds each declared widget, with whether it stands inside an exhibit
    (`quoted_in`).
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
        tuple((record, quoted_in(record, registry)) for record in declared),
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
        events: list = (),
        data: dict | None = None,
    ):
        self.projection = projection
        self.byid = byid
        self.spk = spk
        self.registry = registry
        self.revision = revision
        self.events = events
        self.data = data or {"sources": {}}
        self.nodes = sources.nodes
        self.records = [record for record, _quoted in sources.asking]
        self.positioned_holders = projected_action_holders(projection, byid, registry)

        self.exists: dict[int, bool] = {}
        self.local: dict[int, bool] = {}
        for record, quoted in sources.asking:
            unit = record["attrs"].get("id")
            self.exists[id(record)] = not ((unit and unit in dropped) or quoted)
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
            self.spk,
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
                    self.spk,
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
                self.spk,
                self.registry,
                self.projection,
                answered=answered,
                unit=unit,
            )
            held = self.projection.actions.get((owner, unit, verb))
            status = (
                "answered"
                if answered
                else "open"
                if self.local[id(record)]
                else "withdrawn"
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
                    "status": status,
                    "end": None,
                    "next_actor": "user" if status == "open" else None,
                }
            )
        return result

    def inventory(self, settled_away: set[str], prior=None) -> list:
        """Every present source remains identifiable after completion or withdrawal."""
        records = []
        history_projections = {}
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
                self.events,
                old.document.by_id,
                old.spoken,
                old.registry,
                history_projections,
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
                    self.events,
                    self.byid,
                    self.spk,
                    self.registry,
                    history_projections,
                )
                or any(
                    coordinate[0] == unit and "answer" in (held[0].get("meaning") or {})
                    for coordinate, held in self.projection.actions.items()
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
            status = (
                "answered"
                if answered
                else "open"
                if self.local[id(record)]
                else "withdrawn"
            )
            value_verb = entry["x-awaits"]["value"]
            value, has_content = obligation_value(
                unit,
                value_verb,
                entry["x-state"][value_verb],
                self.byid,
                self.spk,
                self.registry,
                self.projection,
                answered=answered,
            )
            latest_value_seq = max(
                (
                    held[0]["seq"]
                    for coordinate, held in self.projection.actions.items()
                    if coordinate[0] == unit and coordinate[2] == value_verb
                ),
                default=0,
            )
            provenance = max(
                (
                    held[0]
                    for coordinate, held in self.projection.actions.items()
                    if coordinate[0] == unit
                    and held[0]["seq"] >= latest_value_seq
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
                    "status": status,
                    "end": None,
                    "next_actor": "user" if status == "open" else None,
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
    events: list = (),
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
    records.extend(
        {
            "id": f"message:{message['id']}",
            "source": {"kind": "message", "id": message["id"]},
            "thread": identity,
            "message": message["id"],
            "prompt": {"text": message["text"], "target": None},
            "answer": None,
            "status": "open",
            "end": None,
            "next_actor": "user",
        }
        for identity, thread in threads.items()
        for message in thread["msgs"]
        if message.get("obligation")
    )
    tokens = registry.get("$reactions", {}).get("tokens", {})
    for record in records:
        thread = threads[record["thread"]]
        in_words = answered_in_words(record)
        asked = next(
            message["seq"]
            for message in thread["msgs"]
            if message["id"] == record["message"]
        )
        if record["status"] == "open" and in_words:
            answer = next(
                (
                    message
                    for message in thread["msgs"]
                    if message["seq"] > asked
                    and message["author"] == "user"
                    and (
                        settles(message, record["message"], tokens)
                        if is_reaction(message)
                        else not message.get("ephemeral")
                    )
                ),
                None,
            )
            settle_by_words(record, answer, log.ends.get(record["id"]))
        if record["next_actor"] is None:
            continue
        owed = unanswered_agent_turn(thread)
        if thread["resolved"]:
            record["next_actor"] = None
        # Only the user's words answer a question asked in words, so a turn the agent
        # owes after it, such as one a user's edit up the thread opens, leaves it theirs.
        elif not in_words and (
            (owed is not None and owed["seq"] > asked)
            or any(
                todo["seq"] > asked
                for todo in log.owed
                if todo["subject"] == {"kind": "thread", "id": record["thread"]}
            )
        ):
            record["next_actor"] = "agent"
    return collection(records)


def answered_in_words(record: dict) -> bool:
    """Whether a conversational answer, or agent ending, can settle this source: an
    agent message's obligation."""
    return record["source"]["kind"] == "message"


def user_task_obligations(
    log: "TodoReading", reading: FrozenThreadReading
) -> list[dict]:
    """User tasks in the canonical inventory, retaining their explicit completion.

    The to-do fold alone decides their outcome. Discussion, thread resolution and
    page edits never complete the action the user was asked to perform.
    """
    events = {event["id"]: event for event in log.events}
    records = []
    for todo in log.todos:
        if todo["owner"] != "user":
            continue
        subject, outcome = todo["subject"], todo["outcome"]
        ended = todo["state"] != "open"
        records.append(
            {
                "id": todo["id"],
                "source": {"kind": "todo", "id": todo["id"], "subject": subject},
                "thread": reading.subject_thread(subject),
                "message": None,
                "prompt": {
                    "text": todo["title"],
                    "target": subject["id"]
                    if subject["kind"] in {"widget", "element"}
                    else None,
                },
                "answer": {
                    "value": todo["state"],
                    "event": event_reference(events[outcome["id"]]),
                }
                if ended and todo["state"] != "dropped"
                else None,
                "status": "withdrawn"
                if todo["state"] == "dropped"
                else "answered"
                if ended
                else "open",
                "end": {"detail": outcome["detail"], "event": event_reference(outcome)}
                if ended
                else None,
                "next_actor": None if ended else "user",
            }
        )
    return records
