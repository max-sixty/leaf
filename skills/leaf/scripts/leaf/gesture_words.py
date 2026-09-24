"""What the ids a widget gesture names say, read in the gesture's own document.

A gesture is recorded as ids: the widget, the unit it folds on, the options it
picked. They are words only to whoever still holds the document. The reading is
the gesture's own document, the revision it names or the frozen message that sent
the widget, under the vocabulary that document was written in, so a later version
that reworded or removed an option does not change what the user chose. Deliveries,
the transcript, and the served history state a gesture through this one reading.

Two readings of an element come out of that document. `says` is its whole words.
`name` is what the authoring contract calls it away from itself: the attribute its
entry declares with `x-name`, else a leading `<summary>`, heading, or `<strong>`,
inside a leading `<header>` too — the rule the browser's `addressableName` reads off
the live page, read here off the document the gesture was made in.
"""

from collections.abc import Callable
from pathlib import Path

from .events import event_document
from .passages import collapse, spoken
from .projection import frozen_thread_reading
from .revision_artifact import read_registry
from .structure import SourceDocument, parse_revision
from .thread_context import thread_structure

TITLES = frozenset({"summary", "h1", "h2", "h3", "h4", "h5", "h6", "strong"})

# revision → its immutable source and the registry captured with it.
RevisionReader = Callable[[int], tuple[SourceDocument, dict]]


def revisions_on_disk(page_dir: Path) -> RevisionReader:
    return lambda revision: (
        parse_revision(page_dir, revision),
        read_registry(page_dir, revision),
    )


def _text(node) -> str:
    if isinstance(node, str):
        return node
    return "".join(_text(child) for child in node["content"])


def _leading_title(node: dict) -> str:
    for child in node["content"]:
        if isinstance(child, str):
            if child.strip():
                return ""
            continue
        if child["tag"] in TITLES:
            return collapse(_text(child))
        if child["tag"] == "header":
            return _leading_title(child)
    return ""


def _nodes(content: list):
    for node in content:
        if not isinstance(node, str):
            yield node
            yield from _nodes(node["content"])


class _Document:
    """One document a gesture names: its words, its element nodes, its vocabulary."""

    def __init__(self, contents: list[list], spoken_reading: dict, registry: dict):
        self.spoken = spoken_reading
        self.registry = registry
        self.nodes = {
            node["attrs"]["id"]: node
            for content in contents
            for node in _nodes(content)
            if node["attrs"].get("id")
        }

    def name(self, node: dict) -> str:
        attribute = self.registry.get(node["tag"], {}).get("x-name")
        declared = (node["attrs"].get(attribute) or "").strip() if attribute else ""
        return declared or _leading_title(node)


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

    def _document(self, event: dict) -> _Document | None:
        if event.get("meaning") is None:
            return None
        document = event_document(event)
        revision = document.get("revision")
        if revision not in self._documents:
            if document["kind"] == "thread":
                structure = thread_structure(self.events)
                self._documents[revision] = _Document(
                    [fragment.content for fragment in structure.fragments.values()],
                    frozen_thread_reading(self.events, self.registry).spoken,
                    self.registry,
                )
            else:
                source, registry = self.revisions(revision)
                self._documents[revision] = _Document(
                    [source.content], spoken(source, registry), registry
                )
        return self._documents[revision]

    def says(self, event: dict) -> dict[str, str]:
        """id → what it says, for the elements one gesture names.

        An undo names its gesture's elements. A child a user wrote is in no
        document; the event's own detail carries its words. An element that only
        encloses another named one is left out: its words repeat theirs, and a list
        would otherwise travel whole with every row pressed in it."""
        if event["kind"] == "undo":
            event = self.by_id.get(event["undoes"], event)
        document = self._document(event)
        if document is None:
            return {}
        said = document.spoken
        named = {
            identity: said[identity]
            for identity in event["meaning"].get("depends", [event["widget"]])
            if identity in said
        }
        enclosing = {
            outer for element in named.values() for outer in element.within[:-1]
        }
        return {
            identity: element.words
            for identity, element in named.items()
            if element.words and identity not in enclosing
        }

    def declaration(self, event: dict) -> dict:
        """The registry entry the gesture's widget had in its own document."""
        document = self._document(event)
        node = document.nodes.get(event["widget"]) if document else None
        return document.registry.get(node["tag"], {}) if node else {}

    def name(self, event: dict, identity: str) -> str:
        """What the gesture's document calls one element it names: its title, else
        its words, else the id itself."""
        document = self._document(event)
        if document is None:
            return identity
        node = document.nodes.get(identity)
        return (
            (document.name(node) if node else "")
            or (said.words if (said := document.spoken.get(identity)) else "")
            or identity
        )

    def operation(self, request: dict) -> str:
        """What a request's holder calls the operation asked of it: the name of the
        offered child whose attribute carries the verb, else the verb itself."""
        document = self._document(request)
        holder = document.nodes.get(request["widget"]) if document else None
        if holder is not None:
            offers = (
                document.registry.get(holder["tag"], {})
                .get("x-request", {})
                .get("offers", {})
            )
            for child in holder["content"]:
                if isinstance(child, str) or child["tag"] not in offers:
                    continue
                offered = child["attrs"].get(offers[child["tag"]]) == request["action"]
                if offered and (words := document.name(child)):
                    return words
        return request["action"].replace("-", " ")
