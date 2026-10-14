"""Canonical asks from widget state, conversations and stamped page sign-off.

One record contains its prompt, typed answer, completion and next actor. Its thread
and exact owning message locate frozen sources without depending on a live renderer.
A widget source owns identity; context wrappers contribute only prompt words and arrival.
The inventory is complete even when a work queue hides a resolved thread or an
older prompt. To-dos never stand in for these records.

A record's `status` is one of four, and this module is their one producer: `open`;
`answered`, its typed answer in the record; `answered_elsewhere`, a prose ask the
agent ended `done` because the user answered on another surface, with no answer
value; and `withdrawn`, a widget ask the document no longer makes or a prose ask
the agent ended `dropped`. Widget asks never take `answered_elsewhere`: an answer
given elsewhere goes into the widget's declared state in a revision, which records
the value itself."""

import hashlib
import json
from dataclasses import dataclass
from functools import partial
from typing import NamedTuple

from leaf.events import (
    awaits_agent,
    conversation_turns,
    is_reaction,
    retractions,
    standing_approvals,
    taken_back,
    unanswered_agent_turn,
)
from leaf.files import stamped_version
from leaf.gesture_words import element_name
from leaf.page_memory import Slot
from leaf.projection import (
    FrozenThreadReading,
    StateProjection,
    ask_value,
    enclosing_widgets,
    folded_value,
    markup_value,
    page_reading,
    projected_action_holders,
    state_projection,
)
from leaf.read_state import content_version
from leaf.registry.contract import WRITERS
from leaf.structure import review_mode
from leaf.thread_context import widget_messages


def local_ask_entry(entry: dict) -> bool:
    """Whether a widget can originate an ask when its predicate holds."""
    return entry.get("x-awaits") is not None


class AskRegistration(NamedTuple):
    """Compact registration inputs and the last event-dependent registration.

    No parser records or holder chains survive here. The last dynamic answer uses
    the canonical state fold and is keyed by its complete historical event basis.
    """

    tag: str
    asking: bool
    restated: bool
    triggers: frozenset[str]
    requested: Slot


def ask_registrations(document, registry: dict) -> dict[str, AskRegistration]:
    """Compact immutable registration inputs, separate from a revision's parse."""
    return {
        unit: AskRegistration(
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
    the registry declares `settles` (`$reactions`), which answers the ask that
    turn asks as a reply would. `tokens` is `$reactions.tokens`."""
    return (
        is_reaction(reaction)
        and reaction["author"] == "user"
        and reaction.get("parent") == turn
        and bool((tokens.get(reaction["token"]) or {}).get("settles"))
    )


@dataclass(frozen=True)
class ThreadAsks:
    """Prose asks and their settlement from one standing thread.

    Each record retains its source message, content version, state and settling
    event. Widget asks have their own reading and never become prose asks.
    `prompt` selects the latest unanswered prose ask unless the thread is
    closed or an open widget ask owns attention. Earlier unanswered asks
    remain available when a later one is settled; a user turn answers all that
    precede it. Consumers select these facts rather than recognizing asks
    or interpreting their answers again.
    """

    asks: list[dict]
    prompt: dict | None


def event_reference(event: dict | None) -> dict | None:
    """The admitted gesture that supplied an answer; authored state has none."""
    if event is None:
        return None
    return {
        key: event[key] for key in ("id", "kind", "seq", "ts", "author") if key in event
    }


def approval_blocking(records: list[dict]) -> list[dict]:
    """The asks that keep a version from being approved: each open widget
    ask someone still owes, on the page or in a widget an agent sent. The append
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


def approval_ask(document, revision: int, events: list) -> dict | None:
    """Sign-off for an exact public stamp as one canonical ask.

    Draft revisions owe none. Only a standing done event for this public version
    supplies the typed answer; an undo makes the same ask open again.
    Approval admission counts widget asks alone, so this record cannot
    block its own answer.
    """
    version = stamped_version(events, revision)
    if version is None or review_mode(document) != "sign-off":
        return None
    approved = next(
        (
            event
            for event in reversed(standing_approvals(events))
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


def thread_asks(
    thread_id: str,
    thread: dict,
    registry: dict,
    reading: FrozenThreadReading,
    open_widget_threads: set[str],
    ends: dict[str, dict],
) -> ThreadAsks:
    """Keep every prose request, selecting only the latest open prompt for work.

    A user turn or settling reaction answers preceding asks. An agent's `todo_end`
    before any answer retires the request: `done` records it `answered_elsewhere`,
    the user having answered on another surface, and `dropped` records it
    `withdrawn`. Either keeps `answer` null, since the user's words are not in the
    log, and carries the end's detail and event as `end`. Resolving a thread
    suppresses attention without changing any of these facts. A message that
    carries a widget ask poses no second prose ask.
    """
    turns = conversation_turns(thread)
    user_turns = {message["id"] for message in turns if message["author"] == "user"}
    tokens = registry.get("$reactions", {}).get("tokens", {})
    asks = []
    for message in turns:
        if message["author"] != "agent":
            continue
        fragment = reading.structure.fragments.get(message["id"])
        vocabulary = (
            reading.registry_for_message(message["id"]) if fragment else registry
        )
        if any(
            local_ask_entry(vocabulary.get(rec["tag"]) or {})
            and asking(rec["attrs"], vocabulary[rec["tag"]]["x-awaits"].get("when"))
            and not quoted_in(rec, vocabulary)
            for rec in (fragment.lf_elements if fragment else [])
        ):
            continue
        if message["kind"] == "reply" and not message.get("ask"):
            continue
        answer = next(
            (
                entry
                for entry in thread["msgs"]
                if entry["seq"] > message["seq"]
                and (entry["id"] in user_turns or settles(entry, message["id"], tokens))
            ),
            None,
        )
        ending = ends.get("reply:" + message["id"])
        if ending is not None and answer is not None and answer["seq"] < ending["seq"]:
            ending = None
        if ending is not None:
            answer = None
            status = "answered_elsewhere" if ending["state"] == "done" else "withdrawn"
        else:
            status = "open" if answer is None else "answered"
        asks.append(
            {
                "id": "reply:" + message["id"],
                "source": {
                    "kind": "reply",
                    "id": message["id"],
                    "version": content_version(message),
                },
                "thread": thread_id,
                "message": message["id"],
                "prompt": {
                    "text": message.get("text") or None,
                    "target": message["id"],
                },
                "answer": {
                    "value": {
                        key: answer[key] for key in ("text", "token") if key in answer
                    },
                    "event": event_reference(answer),
                }
                if answer is not None
                else None,
                "status": status,
                "end": {"detail": ending["detail"], "event": event_reference(ending)}
                if ending is not None
                else None,
                "next_actor": None,
            }
        )
    current = next(
        (ask for ask in reversed(asks) if ask["status"] == "open"),
        None,
    )
    prompt = None
    if (
        current is not None
        and not thread["resolved"]
        and thread_id not in open_widget_threads
    ):
        current["next_actor"] = "user"
        prompt = {
            "message": current["source"]["id"],
            "version": current["source"]["version"],
        }
    return ThreadAsks(asks, prompt)


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
    """An element's attributes under the declared standing projection: authored
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
            or (event["kind"] == "action" and event["id"] not in projection.standing)
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
    """Each x-state verb whose standing state answers this widget's local ask,
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

    The condition reads standing state and nothing else. `empty` asks the projected
    containment the verb's position records leave; an attribute or value record reads
    through authored markup as well as the fold, so a version that honors the answer
    keeps it answered and a cleared value opens the ask again; any other verb answers
    while one of its actions stands on the widget.
    """
    condition = answer_verbs(entry)[verb]
    if not asking(replayed_attrs(rec, projection), condition.get("when")):
        return False
    if empty := condition.get("empty"):
        return container_empty(rec, empty, byid, registry, holders)
    # A condition without `empty` names a widget-unit verb (registry validation), so
    # its standing action is the one at the widget's own coordinate for the verb.
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


def ask_answered(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
    holders: dict[str, dict] | None = None,
) -> bool:
    """Whether the user's own state answers this ask: one of its answering verbs'
    conditions holds."""
    if holders is None:
        holders = projected_action_holders(projection, byid, registry)
    return any(
        verb_answers(rec, entry, verb, projection, byid, spk, registry, holders)
        for verb in answer_verbs(entry)
    )


def sections_with_agent(threads: dict) -> set[str]:
    """The sections anchoring an open thread whose next word is the agent's.

    An open ask such a thread is about is the agent's turn rather than the user's:
    the user has said something about it and waits on the reply, so it leaves
    their list until the agent answers. That is not an answer, since the widget's
    state is untouched, and the ask stays open, its controls live. The browser
    receives the lists this leaves rather than deciding again, so the banner's
    count and `page state` cannot disagree about whose turn it is.

    Which kind of thread does not enter into it: a seat's, a quote on the ask's
    words, a design note, or one the agent opened that the user has answered."""
    return {
        anchor["section"]
        for thread in threads.values()
        if awaits_agent(thread)
        and (anchor := thread["anchor"])
        and anchor.get("section")
    }


def discussed(records: list[dict], sections: set[str], within: dict) -> None:
    """Hand each open ask a thread anchored on `sections` is about to the agent.

    A section is about the innermost ask whose widget encloses it, answered or not;
    failing one, about every ask whose prompt target (its framing
    x-ask-context) is the innermost to enclose it. So a note on one ask's
    option leaves its framed sibling with the user, and one on the frame's heading
    is about them all. `within` is the document's containment (`Passages.enclosing`).
    """
    asks = {record["source"]["id"]: record for record in records}
    framed: dict[str, list[dict]] = {}
    for record in records:
        framed.setdefault(record["prompt"]["target"], []).append(record)
    for section in sections:
        chain = within.get(section, ())
        ask = next((asks[i] for i in reversed(chain) if i in asks), None)
        about = (
            [ask]
            if ask is not None
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
    """Whether an action of `verb`, standing in `projection`, answers its widget's
    ask: the instance asks or retains an earlier registration, and the verb's
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


class _AskReducer:
    """One page or frozen-thread ask fold over a shared state projection."""

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
            for node in nodes(document.content)
            if node["attrs"].get("id")
        }
        self.records = [record for record in elements if self._is_declared(record)]
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
        return local_ask_entry(self.registry.get(record["tag"]) or {})

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
        return ask_answered(
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
        nearest `x-ask-context` holder enclosing it, or the source itself."""
        holder = self._holder(record)
        while holder:
            if (self.registry.get(holder["tag"]) or {}).get("x-ask-context"):
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
                    registration = old.inventory.asks.get(unit)
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
            value_verb = entry["x-awaits"]["value"]
            spec = entry["x-state"][value_verb]
            value, has_content = ask_value(
                unit,
                value_verb,
                spec,
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
            text = (
                element_name(self.nodes[surface["attrs"]["id"]], self.registry) or None
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


def page_ask_readings(
    source,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    threads: dict,
    within: dict,
    *,
    settled_away: set[str] | None = None,
    prior=None,
    revision: int | None = None,
    events: list = (),
) -> dict:
    """Asks in one document basis; a discussion changes attention, not answer:
    an ask a thread with the agent is about is the agent's (`sections_with_agent`)."""
    reducer = _AskReducer(
        source, projection, byid, spk, registry, dropped, revision, events
    )
    records = reducer.inventory(settled_away or set(), prior)
    discussed(records, sections_with_agent(threads), within)
    return collection(records)


def thread_ask_readings(
    events: list,
    threads: dict,
    *,
    reading: FrozenThreadReading,
) -> dict:
    """Read frozen asks under each message's admitted publication.

    Closing a thread retains its inventory with no next actor. While it is open,
    a user turn after the message that asks hands the ask to the agent until the
    agent answers that turn, as a thread anchored on a page ask does
    (`sections_with_agent`)."""
    records = []
    for publication in reading.publications.values():
        reducer = _AskReducer(
            publication.structure,
            publication.projection,
            publication.structure.by_id,
            publication.spoken,
            publication.registry,
            set(),
            events=events,
        )
        records.extend(reducer.inventory(set()))
    # Publication groups share a vocabulary, not a position in the conversation.
    # Preserve message and authored widget order when composing their inventories.
    order = {widget: index for index, widget in enumerate(reading.by_id)}
    records.sort(key=lambda record: order[record["source"]["id"]])
    message_by_widget = widget_messages(reading.structure)
    for record in records:
        source = record["source"]["id"]
        record["thread"] = reading.thread_by_widget[source]
        record["message"] = message_by_widget[source]
        if record["next_actor"] is None:
            continue
        thread = threads[record["thread"]]
        owed = unanswered_agent_turn(thread)
        if thread["resolved"]:
            record["next_actor"] = None
        elif owed is not None and owed["seq"] > next(
            message["seq"]
            for message in thread["msgs"]
            if message["id"] == record["message"]
        ):
            record["next_actor"] = "agent"
    return collection(records)
