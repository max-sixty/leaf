"""Canonical Questions from widget state, conversations and stamped page sign-off.

One record contains its prompt, typed answer, completion and next actor. A widget
source owns identity; context wrappers contribute only prompt words and arrival.
The inventory is complete even when a work queue hides a resolved thread or an
older prompt. Tasks never stand in for these records."""

from dataclasses import dataclass

from leaf.events import (
    conversation_turns,
    is_reaction,
    retractions,
    standing_approvals,
    taken_back,
)
from leaf.files import stamped_version
from leaf.gesture_words import leading_title
from leaf.projection import (
    FrozenThreadReading,
    StateProjection,
    enclosing_widgets,
    folded_value,
    frozen_thread_reading,
    markup_value,
    page_reading,
    question_value,
    state_projection,
)
from leaf.read_state import content_version
from leaf.structure import review_mode


def local_question_entry(entry: dict) -> bool:
    """Whether a widget can originate a Question when its predicate holds."""
    return entry.get("x-awaits") is not None


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


@dataclass(frozen=True)
class ThreadQuestions:
    """Prose questions and their settlement from one standing thread.

    Each record retains its source message, content version, state and settling
    event. Widget Questions have their own reading and never become prose questions.
    `prompt` selects the latest unanswered prose question unless the thread is
    closed or an open widget Question owns attention. Earlier unanswered questions
    remain available when a later one is settled; a user turn answers all that
    precede it. Consumers select these facts rather than recognizing questions
    or interpreting their answers again.
    """

    questions: list[dict]
    prompt: dict | None


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


def approval_question(document, revision: int, events: list) -> dict | None:
    """Sign-off for an exact public stamp as one canonical Question.

    Draft revisions owe none. Only a standing done event for this public version
    supplies the typed answer; an undo makes the same Question open again.
    Approval admission counts widget Questions alone, so this record cannot
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
        "prompt": {"text": f"Approve v{version}?", "target": "lf-approve"},
        "answer": {"value": True, "event": event_reference(approved)}
        if approved
        else None,
        "status": "answered" if approved else "open",
        "next_actor": None if approved else "user",
    }


def thread_questions(
    thread_id: str,
    thread: dict,
    registry: dict,
    structure,
    open_widget_threads: set[str],
    ends: dict[str, dict],
) -> ThreadQuestions:
    """Keep every prose request, selecting only the latest open prompt for work.

    A user turn or settling reaction answers preceding questions. An agent task end
    withdraws its request, whatever outcome that event reports; it invents no user
    answer. Resolving a thread suppresses attention without changing either fact.
    A message that carries a widget question poses no second prose question.
    """
    turns = conversation_turns(thread)
    user_turns = {message["id"] for message in turns if message["author"] == "user"}
    tokens = registry.get("$reactions", {}).get("tokens", {})
    questions = []
    for message in turns:
        if message["author"] != "agent":
            continue
        fragment = structure.fragments.get(message["id"])
        if any(
            local_question_entry(registry.get(rec["tag"]) or {})
            and asking(rec["attrs"], registry[rec["tag"]]["x-awaits"].get("when"))
            and not quoted_in(rec, registry)
            for rec in (fragment.lf_elements if fragment else [])
        ):
            continue
        if message["kind"] == "reply" and not message.get("awaits"):
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
        withdrawn = ending is not None and (
            answer is None or ending["seq"] < answer["seq"]
        )
        if withdrawn:
            answer = None
        questions.append(
            {
                "id": "reply:" + message["id"],
                "source": {
                    "kind": "reply",
                    "id": message["id"],
                    "version": content_version(message),
                },
                "thread": thread_id,
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
                "status": "withdrawn"
                if withdrawn
                else "answered"
                if answer is not None
                else "open",
                "next_actor": None,
            }
        )
    current = next(
        (question for question in reversed(questions) if question["status"] == "open"),
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
    return ThreadQuestions(questions, prompt)


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
    """Each x-state verb whose standing state answers this widget's local Question,
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
    keeps it answered and a cleared value opens the Question again; any other verb answers
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


def question_answered(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
    holders: dict[str, dict] | None = None,
) -> bool:
    """Whether the user's own state answers this Question: one of its answering verbs'
    conditions holds."""
    if holders is None:
        holders = projected_action_holders(projection, byid, registry)
    return any(
        verb_answers(rec, entry, verb, projection, byid, spk, registry, holders)
        for verb in answer_verbs(entry)
    )


def seat_with_agent(
    rec: dict, entry: dict, projection: StateProjection, with_agent: set[str]
) -> bool:
    """Whether this widget's own thread seat holds a thread now with the agent.

    Declaration-driven at both ends: a widget with no x-thread-seat offers no
    seat, and one whose attributes miss the predicate has none placed on this
    instance either — so an element anchor written onto some other widget reaches
    nothing here. The seat's placement asks the same question of the same
    declaration, so the cell the user can see and the request this takes off their
    list are one."""
    declaration = entry.get("x-thread-seat")
    unit = rec["attrs"].get("id")
    return bool(
        declaration
        and unit in with_agent
        and asking(replayed_attrs(rec, projection), declaration.get("when", {}))
    )


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


def projected_action_holders(
    projection: StateProjection, byid: dict, registry: dict
) -> dict[str, dict]:
    """Unit id → its enclosing vocabulary widget after standing position records
    no later revision has absorbed; an absorbed move leaves its unit where the
    markup has it."""
    holders = {}
    for (_owner, unit, _verb), (event, spec) in projection.desired.items():
        record = spec.get("record") or {}
        if record.get("kind") != "position" or event["id"] in projection.absorbed:
            continue
        target = byid.get(event["detail"]["value"])
        unit_rec = byid.get(unit)
        if target and unit_rec:
            holder = target if target["tag"] in registry else target.get("holder")
            permitted = (registry.get(unit_rec["tag"]) or {}).get("x-owners", [])
            if holder and holder["tag"] in permitted:
                holders[unit] = holder
    return holders


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
    Question: the instance asks or retains an earlier registration, and the verb's
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


class _QuestionReducer:
    """One page or frozen-thread Question fold over a shared state projection."""

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
        return local_question_entry(self.registry.get(record["tag"]) or {})

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
        return question_answered(
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
        nearest `x-question-context` holder enclosing it, or the source itself."""
        holder = self._holder(record)
        while holder:
            if (self.registry.get(holder["tag"]) or {}).get("x-question-context"):
                return holder
            holder = self._holder(holder)
        return record

    def inventory(
        self, settled_away: set[str], with_agent: set[str], prior=None
    ) -> list:
        """Every present source remains identifiable after completion or withdrawal."""
        records = []
        history_projections = {}
        history_readings = {}
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
                    previous = old.document.by_id.get(unit)
                    if previous is None or previous["tag"] != record["tag"]:
                        break
                    declaration = old.registry.get(previous["tag"], {}).get("x-awaits")
                    if declaration is None:
                        break
                    if asking(previous["attrs"], declaration.get("when")):
                        registered = True
                        break
                    dynamic = any(
                        (spec.get("record") or {}).get("kind") == "value"
                        and spec["record"]["attr"] in declaration.get("when", {})
                        for spec in old.registry[previous["tag"]]
                        .get("x-state", {})
                        .values()
                    )
                    if dynamic:
                        if old_revision not in history_readings:
                            history_readings[old_revision] = page_reading(
                                old, self.events, old_revision
                            )
                        basis = history_readings[old_revision]
                        if previously_requested(
                            previous,
                            basis.projection,
                            declaration.get("when", {}),
                            old_revision,
                            self.events,
                            old.document.by_id,
                            old.spoken,
                            old.registry,
                            history_projections,
                        ):
                            registered = True
                            break
                    if "restated" in previous["attrs"]:
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
            value, has_content = question_value(
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
            node = self.nodes.get(surface["attrs"]["id"])
            text = leading_title(node) if node is not None else None
            if not text and surface is record:
                attr = entry.get("x-name")
                text = record["attrs"].get(attr) if attr else None
            records.append(
                {
                    "id": "widget:" + unit,
                    "source": {"kind": "widget", "id": unit, "tag": record["tag"]},
                    "thread": None,
                    "prompt": {"text": text, "target": surface["attrs"]["id"]},
                    "answer": {"value": value, "event": event_reference(provenance)}
                    if has_content
                    else None,
                    "status": status,
                    "next_actor": (
                        "agent"
                        if seat_with_agent(record, entry, self.projection, with_agent)
                        else "user"
                    )
                    if status == "open"
                    else None,
                }
            )
        return records


def page_question_readings(
    source,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    with_agent: set[str],
    *,
    settled_away: set[str] | None = None,
    prior=None,
    revision: int | None = None,
    events: list = (),
) -> dict:
    """Questions in one document basis; a discussion changes attention, not answer."""
    reducer = _QuestionReducer(
        source, projection, byid, spk, registry, dropped, revision, events
    )
    return collection(reducer.inventory(settled_away or set(), with_agent, prior))


def thread_question_readings(
    events: list,
    registry: dict,
    settled: set,
    *,
    reading: FrozenThreadReading | None = None,
) -> dict:
    """Frozen widget Questions retain inventory when their containing thread closes."""
    reading = reading or frozen_thread_reading(events, registry)
    reducer = _QuestionReducer(
        reading.structure,
        reading.projection,
        reading.by_id,
        reading.spoken,
        registry,
        set(),
        events=events,
    )
    records = reducer.inventory(set(), set())
    for record in records:
        record["thread"] = reading.thread_by_widget[record["source"]["id"]]
        if record["thread"] in settled:
            record["next_actor"] = None
    return collection(records)
