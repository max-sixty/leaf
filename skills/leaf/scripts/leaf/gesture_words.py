"""What the ids a widget gesture names say, read in the gesture's own document.

A gesture is recorded as ids: the widget, the unit it folds on, the options it
picked. They are words only to whoever still holds the document. The reading is
the gesture's own document, the revision it names or the frozen message that sent
the widget, under the vocabulary that document was written in, so a later version
that reworded or removed an option does not change what the user chose. Deliveries
and the transcript both state a gesture through this one reading.
"""

from pathlib import Path

from .passages import spoken
from .projection import frozen_thread_reading
from .revision_artifact import read_registry
from .structure import parse_revision


class GestureWords:
    """Readings of each document a page's gestures name, parsed once per document.

    `registry` is the active one, which frozen thread markup reads under for the
    page's whole lifetime; a page revision keeps the registry captured with it."""

    def __init__(self, page_dir: Path, events: list, registry: dict):
        self.page_dir = page_dir
        self.events = events
        self.registry = registry
        self.by_id = {event["id"]: event for event in events}
        self._readings: dict[int | None, dict] = {}

    def _reading(self, document: dict) -> dict:
        revision = document.get("revision")
        if revision not in self._readings:
            self._readings[revision] = (
                frozen_thread_reading(self.events, self.registry).spoken
                if document["kind"] == "thread"
                else spoken(
                    parse_revision(self.page_dir, revision),
                    read_registry(self.page_dir, revision),
                )
            )
        return self._readings[revision]

    def says(self, event: dict) -> dict[str, str]:
        """id → what it says, for the elements one gesture names.

        An undo names its gesture's elements. A child a user wrote is in no
        document; the event's own detail carries its words. An element that only
        encloses another named one is left out: its words repeat theirs, and a list
        would otherwise travel whole with every row pressed in it."""
        if event["kind"] == "undo":
            event = self.by_id.get(event["undoes"], event)
        meaning = event.get("meaning")
        if meaning is None:
            return {}
        said = self._reading(meaning["document"])
        named = {
            identity: said[identity]
            for identity in meaning.get("depends", [event["widget"]])
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
