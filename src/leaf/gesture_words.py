"""What the ids a widget gesture names say, read in the gesture's own document.

A gesture is recorded as ids: the widget, the unit it folds on, the options it
picked. They are words only to whoever still holds the document. The reading is
the gesture's own document, the revision it names or the frozen message that sent
the widget, under the vocabulary that document was written in, so a later version
that reworded or removed an option does not change what the user chose. Deliveries,
the transcript, the served history and the undo offer state a gesture through this
one reading.

Done names no option: on a group whose `state.awaits.value` verb records the pick
as a set of ids, Done says that verb's state when the user pressed it, worded by the
action that set it, or by Done's own document where the pick is authored. The pick
is derived from the log before Done rather than stamped at admission, so Done keeps
resting on its widget alone; one walk of the log serves every Done of a document.
An empty pick says nothing.

A child a user wrote through a `creates` verb is in no document; the action that
created it carries its words, and both readings take them from the latest such
action at or before the gesture, since an undone add frees its id for another.

Two readings of an element come out of that document. `says` is its whole words.
`name` is what the authoring contract calls it away from itself: a widget's `label`
attribute (the registry's `$attributes`), else its leading title, and plain markup's
caption: a disclosure's `<summary>`, an `<hgroup>`'s heading, or the heading a section
or article opens with (`leading_title_node`). It is the rule the browser's
`addressableName` reads off the live page, read here off the document the gesture was
made in.
"""

from collections.abc import Callable
from functools import cached_property
from pathlib import Path

from .events import InForce, event_document
from .passages import SourceReading, collapse, created_words, enclosing_of
from .projection import (
    attribute_marks,
    frozen_thread_reading,
    markup_value,
    state_projection,
)
from .registry.contract import (
    NAME_ATTRIBUTE,
    declared_fact,
    event_spec,
    is_element_name,
)
from .revision_artifact import read_revision

HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
WIDGET_TITLES = HEADINGS | {"summary", "strong"}
SECTIONS = frozenset({"section", "article"})

# revision → its immutable document read under the registry captured with it.
RevisionReader = Callable[[int], SourceReading]


def revisions_on_disk(page_dir: Path) -> RevisionReader:
    return lambda revision: read_revision(page_dir, revision)


def _text(node) -> str:
    if isinstance(node, str):
        return node
    return "".join(_text(child) for child in node["content"])


def _registered(node: dict, registry: dict) -> bool:
    return is_element_name(node["tag"]) and node["tag"] in registry


def leading_title_node(node: dict, registry: dict) -> dict | None:
    """The element that titles `node`. A widget the registry registers, such as an
    option or a card, is titled by its first heading, summary or `<strong>`, looking
    inside a leading <header> or <hgroup> and past other elements, until text
    intervenes. Plain markup is titled by the caption HTML gives it: a disclosure by
    its first <summary>, an <hgroup> by its heading, and a section or article by the
    heading it opens with, alone or in an <hgroup>. No other element is titled by a
    heading inside it, and a bold line in plain markup is how it looks, not what it is
    called."""
    if _registered(node, registry):
        return _widget_title(node)
    return _opening_title(node)


def _widget_title(node: dict) -> dict | None:
    for child in node["content"]:
        if isinstance(child, str):
            if child.strip():
                return None
            continue
        if child["tag"] in WIDGET_TITLES:
            return child
        if child["tag"] in {"header", "hgroup"}:
            return _widget_title(child)
    return None


def _opening_title(node: dict) -> dict | None:
    elements = [child for child in node["content"] if not isinstance(child, str)]
    if node["tag"] == "details":
        return next((child for child in elements if child["tag"] == "summary"), None)
    if node["tag"] == "hgroup":
        return next((child for child in elements if child["tag"] in HEADINGS), None)
    if node["tag"] not in SECTIONS:
        return None
    first = next((child for child in node["content"] if not _blank(child)), None)
    if first is None or isinstance(first, str):
        return None
    if first["tag"] == "hgroup":
        return _opening_title(first)
    return first if first["tag"] in HEADINGS else None


def _blank(node) -> bool:
    return isinstance(node, str) and not node.strip()


def element_name(node: dict, registry: dict) -> str:
    """What the authoring contract calls an element away from itself: a widget's
    `label` attribute (`contract.NAME_ATTRIBUTE`), else its leading title, in the
    words the author wrote. The browser's `addressableName` reads the same rule off
    the live page; `tests/name_cases.json` holds both to the same cases."""
    if _registered(node, registry):
        declared = (node["attrs"].get(NAME_ATTRIBUTE) or "").strip()
        if declared:
            return declared
    title = leading_title_node(node, registry)
    return collapse(_text(title)) if title else ""


def group_name(group: dict, nodes: dict[str, dict]) -> str:
    """The name the author gives a group, as ARIA reads it: the words of the elements
    its `aria-labelledby` names, read from `nodes`, its document's elements by id; else
    its `aria-label`; else a fieldset's legend, its first `<legend>` child; empty where
    the author named nothing."""
    attrs = group["attrs"]
    named = [
        nodes[i] for i in (attrs.get("aria-labelledby") or "").split() if i in nodes
    ]
    if words := collapse(" ".join(_text(node) for node in named)):
        return words
    if words := collapse(attrs.get("aria-label") or ""):
        return words
    if group["tag"] == "fieldset":
        legend = next(
            (
                child
                for child in group["content"]
                if not isinstance(child, str) and child["tag"] == "legend"
            ),
            None,
        )
        if legend:
            return collapse(_text(legend))
    return ""


def _nodes(content: list):
    for node in content:
        if not isinstance(node, str):
            yield node
            yield from _nodes(node["content"])


class _Document:
    """One document a gesture names: its words, its element nodes, its vocabulary."""

    def __init__(
        self,
        contents: list[list],
        spoken_reading: dict,
        registry: dict,
        by_id: dict,
        revision: int | None,
    ):
        self.spoken = spoken_reading
        self.registry = registry
        self.by_id = by_id
        self.revision = revision
        # Done id → the action holding its pick (`GestureWords._held`).
        self.held: dict[str, dict | None] | None = None
        self.nodes = {
            node["attrs"]["id"]: node
            for content in contents
            for node in _nodes(content)
            if node["attrs"].get("id")
        }

    def name(self, node: dict) -> str:
        return element_name(node, self.registry)

    @cached_property
    def marks(self) -> dict:
        return attribute_marks(self.by_id, self.spoken, self.registry)


class GestureWords:
    """Readings of each document a page's gestures name, parsed once per document.

    `registry` is the active one, which frozen thread markup reads under for the
    page's whole lifetime; a page revision keeps the registry captured with it."""

    def __init__(self, events: list, registry: dict, revisions: RevisionReader):
        self.events = events
        self.registry = registry
        self.revisions = revisions
        self.by_id = {event["id"]: event for event in events}
        self._documents: dict[int | None, _Document] = {}
        self._voices: dict[str, tuple[dict, list]] = {}

    def _document(self, event: dict) -> _Document | None:
        if event.get("meaning") is None:
            return None
        document = event_document(event)
        revision = document.get("revision")
        if revision not in self._documents:
            if document["kind"] == "thread":
                reading = frozen_thread_reading(self.events, self.registry)
                self._documents[revision] = _Document(
                    [
                        fragment.authoring.content
                        for fragment in reading.structure.fragments.values()
                    ],
                    reading.spoken,
                    self.registry,
                    reading.structure.by_id,
                    None,
                )
            else:
                assert revision is not None
                reading = self.revisions(revision)
                self._documents[revision] = _Document(
                    [reading.document.authoring.content],
                    reading.spoken,
                    reading.registry,
                    reading.document.by_id,
                    revision,
                )
        return self._documents[revision]

    def _voice(self, event: dict) -> tuple[dict, list]:
        """The gesture whose document words `event`, and the ids it names there.

        An undo names its gesture's elements, and Done on a group its pick."""
        if event["kind"] == "undo":
            event = self.by_id.get(event["undoes"], event)
        if event["id"] not in self._voices:
            meaning = event.get("meaning") or {}
            pick = self._pick(event) if "answer" in meaning else None
            self._voices[event["id"]] = pick or (
                event,
                meaning.get("depends") or [event.get("widget")],
            )
        return self._voices[event["id"]]

    def _value_verb(self, event: dict) -> str | None:
        """The widget's `state.awaits.value` verb where `event` answers through another
        verb and that one records a set of ids on the widget, in `event`'s document."""
        if "answer" not in (event.get("meaning") or {}):
            return None
        entry = self.declaration(event)
        verb = (declared_fact(entry, "state.awaits") or {}).get("value")
        spec = declared_fact(entry, "state.verbs", {}).get(verb)
        if (
            verb == event["action"]
            or spec is None
            or spec["unit"] != "widget"
            or (spec.get("record") or {}).get("kind") != "attribute"
        ):
            return None
        return verb

    def _held(self, document: _Document) -> dict[str, dict | None]:
        """Done id → the action holding its value verb's state just before it, for
        each Done this document answers in.

        One walk of the log serves every Done of the document, as `InForce` reads
        what each event changed: the fold of the document classifies the actions,
        then undos withdraw and the document's version notes restate where they
        fall. A frozen thread folds without floors, as `frozen_thread_reading`
        does."""
        if document.held is None:
            classified = state_projection(
                self.events,
                document.by_id,
                document.spoken,
                document.registry,
                document.revision,
                floors={},
                withdrawn=set(),
            ).classified
            in_force = InForce(enclosing_of(document.spoken))
            document.held = {}
            for event in self.events:
                if event["kind"] == "undo":
                    in_force.withdraw(event["undoes"])
                elif event["kind"] == "note":
                    if document.revision is not None and (
                        event["revision"] <= document.revision
                    ):
                        in_force.restate(event)
                elif event["kind"] == "action" and event["id"] in classified:
                    if self._document(event) is document and (
                        verb := self._value_verb(event)
                    ):
                        widget = event["widget"]
                        document.held[event["id"]] = in_force.winner(
                            (widget, widget, verb)
                        )
                    in_force.admit(event)
        return document.held

    def _pick(self, done: dict) -> tuple[dict, list] | None:
        """What the widget's `state.awaits.value` verb held when `done` answered with
        another verb: the action holding it and its ids, or `done` and the ids its
        document authored. None where `_value_verb` names no such verb."""
        verb = self._value_verb(done)
        document = self._document(done)
        if verb is None or document is None:
            return None
        held = self._held(document).get(done["id"])
        if held is not None:
            return held, sorted(held["detail"]["value"])
        spec = document.registry[document.nodes[done["widget"]]["tag"]]["state"][
            "verbs"
        ][verb]
        return done, markup_value(done["widget"], spec, document.by_id, document.marks)

    @cached_property
    def _creations(self) -> dict[str, list[tuple[int, dict]]]:
        """id → (log position, action) for each `creates` action that wrote a child
        with that id, in log order. An undone add frees its id for a later one."""
        creations: dict[str, list[tuple[int, dict]]] = {}
        for position, event in enumerate(self.events):
            meaning = event.get("meaning") or {}
            if event["kind"] == "action" and "creates" in meaning:
                creations.setdefault(meaning["unit"], []).append((position, event))
        return creations

    @cached_property
    def _positions(self) -> dict[str, int]:
        return {event["id"]: position for position, event in enumerate(self.events)}

    def _created(self, gesture: dict, identity: str) -> str | None:
        """The words a user-written child had when `gesture` named it: those of the
        latest action creating that id at or before the gesture, as the child
        shows them (`created_words`)."""
        at = self._positions.get(gesture["id"], len(self.events))
        creators = [
            event
            for position, event in self._creations.get(identity, ())
            if position <= at
        ]
        if not creators:
            return None
        creator = creators[-1]
        # Admission stored the child's tag; only the name of the detail field that
        # carries its words is left to the creator's declaration.
        creates = (
            declared_fact(self.declaration(creator), "state.verbs", {})
            .get(creator["action"], {})
            .get("creates")
        )
        if not creates:
            return None
        return collapse(created_words(creator["detail"][creates["words"]]))

    def says(self, event: dict) -> dict[str, str]:
        """id → what it says, for the elements one gesture names.

        An undo names its gesture's elements, and Done on a group its pick
        (`_voice`). A child a user wrote says the words its creating action gave
        it, and its sender encloses it. An element that only encloses another named
        one is left out: its words repeat theirs, and a list would otherwise travel
        whole with every row pressed in it."""
        event, depends = self._voice(event)
        document = self._document(event)
        if document is None:
            return {}
        said = document.spoken
        named = {identity: said[identity] for identity in depends if identity in said}
        written = {
            identity: words
            for identity in depends
            if identity not in said and (words := self._created(event, identity))
        }
        enclosing = {
            outer for element in named.values() for outer in element.within[:-1]
        }
        if written:
            enclosing.add(event["widget"])
        return {
            **{
                identity: element.words
                for identity, element in named.items()
                if element.words and identity not in enclosing
            },
            **written,
        }

    def gesture(self, event: dict) -> dict:
        """What an action did, in its record form's terms and its own document's
        words: the reading a history row and an undo offer both carry."""
        spec = declared_fact(self.declaration(event), "state.verbs", {}).get(
            event["action"], {}
        )
        record = spec.get("record") or {}
        detail = event["detail"]
        if record.get("kind") == "attribute":
            return {
                "form": "choice",
                "chosen": [self.name(event, i) for i in detail["value"]],
            }
        if record.get("kind") == "position":
            return {
                "form": "move",
                "unit": self.name(event, detail[spec["unit"]]),
                "to": self.name(event, detail["value"]),
            }
        if record.get("kind") == "body":
            return {"form": "edit"}
        if spec.get("creates"):
            return {"form": "add", "words": self.name(event, detail[spec["unit"]])}
        return {"form": "verb", "verb": event["action"]}

    def declaration(self, event: dict) -> dict:
        """The registry entry the gesture's widget had in its own document."""
        document = self._document(event)
        node = document.nodes.get(event["widget"]) if document else None
        return document.registry.get(node["tag"], {}) if document and node else {}

    def records_unsent(self, action: dict) -> bool:
        """Whether the action's verb records work the user hasn't sent
        (`$state.unsent`), as the document they acted in declared it, so a later
        version redeclaring the verb leaves earlier actions as they were."""
        spec = event_spec(self.declaration(action), action)
        return bool(spec and spec.get("unsent"))

    def name(self, event: dict, identity: str) -> str:
        """What the gesture's document calls one element it names: its title, else
        its words, else the words a user wrote it with, else the id itself."""
        event, _ = self._voice(event)
        document = self._document(event)
        if document is None:
            return identity
        node = document.nodes.get(identity)
        return (
            (document.name(node) if node else "")
            or (said.words if (said := document.spoken.get(identity)) else "")
            or self._created(event, identity)
            or identity
        )
