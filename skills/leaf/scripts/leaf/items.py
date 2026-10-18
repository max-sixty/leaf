"""Canonical items from widgets and stamped page sign-off.

One record contains its prompt, typed answer, completion and next actor. Its thread
and exact owning message locate frozen sources without depending on a live renderer.
A widget source owns identity; context wrappers contribute only prompt words and arrival.
The inventory is complete even when a work queue hides a resolved thread or an
older prompt. To-dos never stand in for these records.

A widget whose `x-awaits` declares `reply`, such as `lf-ask` holding no widget of its
own, is a question the user answers in words: their next message in the thread
whose message holds it, a reaction there whose token settles it, or on the page a
message in a thread anchored inside it. It has no x-state, so its answer is that
message's text or token. The user chose a question widget over a reply flag
(`--ask`, which Leaf had), so that only widgets, to-dos, resends and sign-off put
items on the user's list.

A record's `status` is one of four, and this module is their one producer: `open`;
`answered`, its typed answer in the record; `answered_elsewhere`, a reply-answered
item the agent ended `done` because the user answered on another surface, with no
answer value; and `withdrawn`, an item the document no longer makes or a
reply-answered item the agent ended `dropped`. A state-answered item never takes
`answered_elsewhere`: an answer given elsewhere goes into the widget's declared
state in a revision, which records the value itself."""

import hashlib
import json
from functools import partial
from typing import NamedTuple

from leaf.events import (
    approvals_in_force,
    awaits_agent,
    is_reaction,
    retractions,
    taken_back,
    unanswered_agent_turn,
)
from leaf.files import stamped_version
from leaf.gesture_words import element_name, element_text
from leaf.page_memory import Slot
from leaf.projection import (
    FrozenThreadReading,
    StateProjection,
    item_value,
    enclosing_widgets,
    folded_value,
    frozen_thread_reading,
    markup_value,
    page_reading,
    projected_action_holders,
    state_projection,
)
from leaf.registry.contract import WRITERS
from leaf.structure import review_mode
from leaf.thread_context import widget_messages


def local_item_entry(entry: dict) -> bool:
    """Whether a widget can originate an item when its predicate holds."""
    return entry.get("x-awaits") is not None


def replied(entry: dict) -> bool:
    """Whether the user's own words answer this widget's item (`x-awaits.reply`)
    rather than its state."""
    return bool((entry.get("x-awaits") or {}).get("reply"))


def encloses(entry: dict) -> bool:
    """Whether this widget frames the items inside it (`x-awaits.encloses`): its leading
    heading gives their prompt, and going to one of them lands on it."""
    return bool((entry.get("x-awaits") or {}).get("encloses"))


def holds_items(record: dict, records: list[dict], registry: dict) -> bool:
    """Whether an enclosing widget holds another that can ask, and so asks nothing
    itself: a frame around a decision widget stays one item. It reads the authored
    containment, so every revision and reading agrees on it."""
    return encloses(registry[record["tag"]]) and any(
        other is not record
        and not quoted_in(other, registry)
        and any(holder is record for holder in enclosing_widgets(other))
        for other in records
    )


def settle_by_words(record: dict, answer: dict | None, ending: dict | None) -> None:
    """Settle a reply-answered item from the user's message that answers it and the
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


class ItemRegistration(NamedTuple):
    """Compact registration inputs and the last event-dependent registration.

    No parser records or holder chains survive here. The last dynamic answer uses
    the canonical state fold and is keyed by its complete historical event basis.
    """

    tag: str
    asking: bool
    restated: bool
    triggers: frozenset[str]
    requested: Slot


def item_registrations(document, registry: dict) -> dict[str, ItemRegistration]:
    """Compact immutable registration inputs, separate from a revision's parse."""
    return {
        unit: ItemRegistration(
            record["tag"],
            asking(record["attrs"], declaration.get("when")),
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


def approval_blocking(records: list[dict]) -> list[dict]:
    """The items that keep a version from being approved: each open widget
    item someone still owes, on the page or in a widget an agent sent. The append
    door refuses a sign-off while one stands, and the browser view serves their ids
    so the approve control says the same."""
    return [
        record
        for record in records
        if record["source"]["kind"] == "widget"
        and record["status"] == "open"
        and record["next_actor"] is not None
    ]


def collection(records: list[dict]) -> dict:
    """Select obligations from an inventory without deciding membership again."""
    return {
        "all": records,
        "user": [record for record in records if record["next_actor"] == "user"],
        "unanswered": [record for record in records if record["status"] == "open"],
    }


def approval_item(document, revision: int, events: list) -> dict | None:
    """Sign-off for an exact public stamp as one canonical item.

    Draft revisions owe none. Only a done event in force for this public version
    supplies the typed answer; an undo makes the same item open again.
    Approval admission counts widget items alone, so this record cannot
    block its own answer.
    """
    version = stamped_version(events, revision)
    if version is None or review_mode(document) != "sign-off":
        return None
    approved = next(
        (
            event
            for event in reversed(approvals_in_force(events))
            if event["version"] == version
        ),
        None,
    )
    return {
        "id": f"approval:v{version}",
        "source": {"kind": "approval", "version": version},
        "thread": None,
        "message": None,
        "prompt": {"text": f"Approve v{version}?", "target": "lf-approve"},
        "answer": {"value": True, "event": event_reference(approved)}
        if approved
        else None,
        "status": "answered" if approved else "open",
        "end": None,
        "next_actor": None if approved else "user",
    }


def asking(attrs: dict, when: dict) -> bool:
    """Every attribute `when` names holds one of the values that ask, a flag's
    two values being its presence and its absence."""
    return all(
        any(
            (attr in attrs) == value
            if isinstance(value, bool)
            else attrs.get(attr) == value
            for value in values
        )
        for attr, values in (when or {}).items()
    )


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
        if asking(replayed_attrs(record, cache[key]), when):
            return True
    return False


def answer_verbs(entry: dict) -> dict:
    """Each x-state verb whose current state answers this widget's local item,
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
) -> bool:
    """Whether one answering verb's declared condition holds for this widget now.

    The condition reads current state and nothing else. `empty` asks the projected
    containment the verb's position records leave; an attribute or value record reads
    through authored markup as well as the fold, so a version that honors the answer
    keeps it answered and a cleared value opens the item again; any other verb answers
    while one of its actions stands on the widget.
    """
    condition = answer_verbs(entry)[verb]
    if not asking(replayed_attrs(rec, projection), condition.get("when")):
        return False
    if empty := condition.get("empty"):
        return container_empty(rec, empty, byid, registry, holders)
    # A condition without `empty` names a widget-unit verb (registry validation), so
    # its action in force is the one at the widget's own coordinate for the verb.
    unit = rec["attrs"].get("id")
    held = projection.actions.get((unit, unit, verb))
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


def item_answered(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
    holders: dict[str, dict] | None = None,
) -> bool:
    """Whether the user's own state answers this item: one of its answering verbs'
    conditions holds."""
    if holders is None:
        holders = projected_action_holders(projection, byid, registry)
    return any(
        verb_answers(rec, entry, verb, projection, byid, spk, registry, holders)
        for verb in answer_verbs(entry)
    )


def sections_with_agent(threads: dict) -> set[str]:
    """The sections anchoring an open thread whose next word is the agent's.

    An open item such a thread is about is the agent's turn rather than the user's:
    the user has said something about it and waits on the reply, so it leaves
    their list until the agent answers. That is not an answer, since the widget's
    state is untouched, and the item stays open, its controls live. The browser
    receives the lists this leaves rather than deciding again, so the banner's
    count and `page state` cannot disagree about whose turn it is.

    Which kind of thread does not enter into it: a seat's, a quote on the item's
    words, a design note, or one the agent opened that the user has answered."""
    return {
        anchor["section"]
        for thread in threads.values()
        if awaits_agent(thread)
        and (anchor := thread["anchor"])
        and anchor.get("section")
    }


def discussed(records: list[dict], sections: set[str], within: dict) -> None:
    """Hand each open item a thread anchored on `sections` is about to the agent.

    A section is about the innermost item whose widget encloses it, answered or not;
    failing one, about every item whose prompt target (its framing
    enclosing widget) is the innermost to enclose it. So a note on one item's
    option leaves its framed sibling with the user, and one on the frame's heading
    is about them all. `within` is the document's containment (`Passages.enclosing`).
    """
    items = {record["source"]["id"]: record for record in records}
    framed: dict[str, list[dict]] = {}
    for record in records:
        framed.setdefault(record["prompt"]["target"], []).append(record)
    for section in sections:
        chain = within.get(section, ())
        item = next((items[i] for i in reversed(chain) if i in items), None)
        about = (
            [item]
            if item is not None
            else next((framed[i] for i in reversed(chain) if i in framed), [])
        )
        for record in about:
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
        (registry.get(node["tag"]) or {}).get("x-exhibit")
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
        and asking(record["attrs"], empty["when"])
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
) -> bool:
    """Whether an action of `verb`, in force in `projection`, answers its widget's
    item: the instance asks or retains an earlier registration, and the verb's
    own condition holds with it in place. Editable answers retain user provenance
    after the author suppresses the request. Admission stamps `meaning.answer` on
    exactly these."""
    awaits = entry.get("x-awaits") or {}
    return (
        verb in answer_verbs(entry)
        and (registered or asking(replayed_attrs(rec, projection), awaits.get("when")))
        and verb_answers(
            rec,
            entry,
            verb,
            projection,
            byid,
            spk,
            registry,
            projected_action_holders(projection, byid, registry),
        )
    )


class _ItemReducer:
    """One page or frozen-thread item fold over a shared state projection."""

    def __init__(
        self,
        source,
        projection,
        byid,
        spk,
        registry: dict,
        dropped: set,
        revision: int | None = None,
        events: list = (),
    ):
        self.projection = projection
        self.byid = byid
        self.spk = spk
        self.registry = registry
        self.revision = revision
        self.events = events
        documents = (
            list(source.fragments.values())
            if hasattr(source, "fragments")
            else [source]
        )
        elements = [record for document in documents for record in document.lf_elements]

        def nodes(content):
            for node in content:
                if isinstance(node, dict):
                    yield node
                    yield from nodes(node["content"])

        self.nodes = {
            node["attrs"]["id"]: node
            for document in documents
            for node in nodes(document.authoring.content)
            if node["attrs"].get("id")
        }
        self.records = [record for record in elements if self._is_declared(record)]
        self.yielded = {
            id(record)
            for record in self.records
            if holds_items(record, self.records, registry)
        }
        self.positioned_holders = projected_action_holders(projection, byid, registry)

        self.exists: dict[int, bool] = {}
        self.local: dict[int, bool] = {}
        for record in self.records:
            unit = record["attrs"].get("id")
            self.exists[id(record)] = not (
                (unit and unit in dropped) or quoted_in(record, registry)
            )
            self.local[id(record)] = self.exists[id(record)] and self._local(record)

    def _entry(self, record):
        return self.registry[record["tag"]]

    def _is_declared(self, record):
        return local_item_entry(self.registry.get(record["tag"]) or {})

    def _declaration(self, record):
        return self._entry(record).get("x-awaits", {})

    def _local(self, record):
        return asking(
            replayed_attrs(record, self.projection),
            self._declaration(record).get("when"),
        )

    def _holder(self, record):
        unit = record["attrs"].get("id")
        return self.positioned_holders.get(unit, record.get("holder"))

    def _answered(self, record):
        return item_answered(
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
        nearest enclosing widget (`x-awaits.encloses`) holding it, or the source
        itself."""
        holder = self._holder(record)
        while holder:
            if encloses(self.registry.get(holder["tag"]) or {}):
                return holder
            holder = self._holder(holder)
        return record

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
            if event["kind"] in WRITERS:
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
            if event["kind"] in WRITERS or event["kind"] == "note"
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
            if id(record) in self.yielded:
                continue
            unit = record["attrs"].get("id")
            answered = self._answered(record)
            if not self.exists[id(record)] and not (unit in settled_away and answered):
                continue
            registered = (
                self.local[id(record)]
                or asking(record["attrs"], self._declaration(record).get("when"))
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
            surface = self._surface(record)
            entry = self._entry(record)
            status = (
                "answered"
                if answered
                else "open"
                if self.local[id(record)]
                else "withdrawn"
            )
            # A reply-answered item has no state; its reading settles it from the
            # conversation (`settle_by_words`).
            value_verb = entry["x-awaits"].get("value")
            value, has_content = (
                item_value(
                    unit,
                    value_verb,
                    entry["x-state"][value_verb],
                    self.byid,
                    self.spk,
                    self.registry,
                    self.projection,
                    answered=answered,
                )
                if value_verb
                else (None, False)
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
            # A question with no title of its own, such as an lf-ask in a reply, is
            # named by its words.
            node = self.nodes[surface["attrs"]["id"]]
            text = (
                element_name(node, self.registry)
                or (element_text(node) if replied(entry) else "")
                or None
            )
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


def page_item_readings(
    source,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    threads: dict,
    within: dict,
    ends: dict,
    *,
    settled_away: set[str] | None = None,
    prior=None,
    revision: int | None = None,
    events: list = (),
) -> dict:
    """Items in one document basis; a discussion changes attention, not answer:
    an item a thread with the agent is about is the agent's (`sections_with_agent`).
    A reply-answered item is the exception, since a message about it is its answer:
    the first user message in a thread opened inside it, after the stamped version
    that last restated it (`$restated`), so a rewritten question is asked again.
    `ends` holds the agent's `todo_end` on each id."""
    reducer = _ItemReducer(
        source, projection, byid, spk, registry, dropped, revision, events
    )
    records = reducer.inventory(settled_away or set(), prior)
    restated = {
        named: event["seq"]
        for event in events
        if event["kind"] == "note"
        and (revision is None or event["revision"] <= revision)
        for named in event.get("restated", [])
    }
    for record in records:
        unit = record["source"]["id"]
        if record["status"] != "open" or not replied(registry[record["source"]["tag"]]):
            continue
        # The thread's opening anchor, not where it was moved since: a later move
        # or detach doesn't unsay what the user wrote about the question.
        answer = min(
            (
                message
                for thread in threads.values()
                if (anchor := thread["root"].get("anchor"))
                and (section := anchor.get("section"))
                and (section == unit or unit in within.get(section, ()))
                for message in thread["msgs"]
                if message["author"] == "user"
                and not is_reaction(message)
                and not message.get("ephemeral")
                and message["seq"] > restated.get(unit, 0)
            ),
            key=lambda message: message["seq"],
            default=None,
        )
        settle_by_words(record, answer, ends.get(record["id"]))
    discussed(records, sections_with_agent(threads), within)
    return collection(records)


def thread_item_readings(
    events: list,
    registry: dict,
    threads: dict,
    ends: dict,
    *,
    reading: FrozenThreadReading | None = None,
) -> dict:
    """Frozen widget items retain inventory when their containing thread closes,
    with no next actor. While the thread is open, a user turn after the message
    that asks hands the item to the agent until the agent answers that turn, as a
    thread anchored on a page item does (`sections_with_agent`). That turn instead
    answers a reply-answered item, as does a reaction on the message whose token
    settles it; `ends` holds the agent's `todo_end` on each id."""
    reading = reading or frozen_thread_reading(events, registry)
    reducer = _ItemReducer(
        reading.structure,
        reading.projection,
        reading.by_id,
        reading.spoken,
        registry,
        set(),
        events=events,
    )
    records = reducer.inventory(set())
    message_by_widget = widget_messages(reading.structure)
    tokens = registry.get("$reactions", {}).get("tokens", {})
    for record in records:
        source = record["source"]["id"]
        record["thread"] = reading.thread_by_widget[source]
        record["message"] = message_by_widget[source]
        thread = threads[record["thread"]]
        in_words = replied(registry[record["source"]["tag"]])
        if record["status"] == "open" and in_words:
            asked = next(
                message["seq"]
                for message in thread["msgs"]
                if message["id"] == record["message"]
            )
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
            settle_by_words(record, answer, ends.get(record["id"]))
        if record["next_actor"] is None:
            continue
        owed = unanswered_agent_turn(thread)
        if thread["resolved"]:
            record["next_actor"] = None
        # Only the user's words answer a question asked in words, so a turn the agent
        # owes after it, such as one a user's edit up the thread opens, leaves it theirs.
        elif (
            not in_words
            and owed is not None
            and owed["seq"]
            > next(
                message["seq"]
                for message in thread["msgs"]
                if message["id"] == record["message"]
            )
        ):
            record["next_actor"] = "agent"
    return collection(records)
