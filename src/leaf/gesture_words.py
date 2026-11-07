"""What the ids a widget gesture names say, read in the gesture's own document.

A gesture is recorded as ids: the widget, the unit it folds on, the options it
picked. They are words only to whoever still holds the document. The reading is
the gesture's own document, the revision it names or the frozen message that sent
the widget, under the vocabulary that document was written in, so a later version
that reworded or removed an option does not change what the user chose. Deliveries,
the transcript, the served history and the undo offer state a gesture through this
one reading.

Done names no option: on a group whose `x-awaits.value` verb records the pick
as a set of ids, Done says that verb's state when the user pressed it, worded by the
action that set it, or by Done's own document where the pick is authored. The pick
is derived from the log before Done rather than stamped at admission, so Done keeps
resting on its widget alone, at the cost of one fold of that prefix per Done read;
an empty pick says nothing.

A child a user wrote through a `creates` verb is in no document; the action that
created it carries its words, and both readings take them from the latest such
action at or before the gesture, since an undone add frees its id for another.

Two readings of an element come out of that document. `says` is its whole words.
`name` is what the authoring contract calls it away from itself: the attribute its
entry declares with `x-name`, else a leading `<summary>`, heading, or `<strong>`,
inside a leading `<header>` or `<hgroup>` too — the rule the browser's `addressableName` reads off
the live page, read here off the document the gesture was made in.
"""

from collections.abc import Callable
from functools import cached_property
from pathlib import Path

from .events import event_document, taken_back
from .passages import SourceReading, collapse, shown_words
from .projection import (
    attribute_marks,
    frozen_thread_reading,
    markup_value,
    state_projection,
)
from .registry.contract import event_spec
from .revision_artifact import read_revision

TITLES = frozenset({"summary", "h1", "h2", "h3", "h4", "h5", "h6", "strong"})

# revision → its immutable document read under the registry captured with it.
RevisionReader = Callable[[int], SourceReading]


def revisions_on_disk(page_dir: Path) -> RevisionReader:
    return lambda revision: read_revision(page_dir, revision)


def _text(node) -> str:
    if isinstance(node, str):
        return node
    return "".join(_text(child) for child in node["content"])


def leading_title_node(node: dict) -> dict | None:
    """The element that titles `node`: its first title element, looking inside a
    leading <header> or <hgroup> and past other elements, until text intervenes."""
    for child in node["content"]:
        if isinstance(child, str):
            if child.strip():
                return None
            continue
        if child["tag"] in TITLES:
            return child
        if child["tag"] in {"header", "hgroup"}:
            return leading_title_node(child)
    return None


def leading_title(node: dict) -> str:
    title = leading_title_node(node)
    return collapse(_text(title)) if title else ""


def element_name(node: dict, registry: dict) -> str:
    """What the authoring contract calls an element away from itself: the attribute
    its entry declares with `x-name`, else its leading title, in the words the author
    wrote. The browser's `addressableName` reads the same rule off the live page;
    `tests/name_cases.json` holds both to the same cases."""
    attribute = registry.get(node["tag"], {}).get("x-name")
    declared = (node["attrs"].get(attribute) or "").strip() if attribute else ""
    return declared or leading_title(node)


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
        self.nodes = {
            node["attrs"]["id"]: node
            for content in contents
            for node in _nodes(content)
            if node["attrs"].get("id")
        }

    def name(self, node: dict) -> str:
        return element_name(node, self.registry)


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

    def _pick(self, done: dict) -> tuple[dict, list[str]] | None:
        """What the widget's `x-awaits.value` verb held when `done` answered with
        another verb: the action holding it and its ids, or `done` and the ids its
        document authored. None where that verb records no set of ids on the widget."""
        document = self._document(done)
        node = document.nodes.get(done["widget"]) if document else None
        if document is None or node is None:
            return None
        entry = document.registry.get(node["tag"], {})
        verb = (entry.get("x-awaits") or {}).get("value")
        spec = entry.get("x-state", {}).get(verb)
        if (
            verb == done["action"]
            or spec is None
            or spec["unit"] != "widget"
            or (spec.get("record") or {}).get("kind") != "attribute"
        ):
            return None
        before = self.events[: self._positions.get(done["id"], len(self.events))]
        projection = state_projection(
            before,
            document.by_id,
            document.spoken,
            document.registry,
            document.revision,
            floors=None if document.revision is not None else {},
            withdrawn=taken_back(before),
        )
        widget = done["widget"]
        held = projection.actions.get((widget, widget, verb))
        if held is not None:
            return held[0], sorted(held[0]["detail"]["value"])
        marks = attribute_marks(document.by_id, document.spoken, document.registry)
        return done, markup_value(widget, spec, document.by_id, marks)

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
        latest action creating that id at or before the gesture, shown as the
        child's `x-text-format` renders them."""
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
            self.declaration(creator)
            .get("x-state", {})
            .get(creator["action"], {})
            .get("creates")
        )
        if not creates:
            return None
        document = self._document(creator)
        assert document is not None
        entry = document.registry.get(creator["meaning"]["creates"], {})
        words = creator["detail"][creates["words"]]
        return collapse(shown_words(words, entry, added=True))

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
        spec = self.declaration(event).get("x-state", {}).get(event["action"], {})
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
