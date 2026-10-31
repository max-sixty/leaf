"""Document-scoped browser projection and undo readings."""

from ..delivery import opened_input_ids
from ..document_reading import DocumentReading
from ..events import UndoReading, action_retracted
from ..gesture_words import GestureWords
from ..projection import StateProjection
from ..registry.kernel import kinds_declaring
from .wire import browser_projection


def browser_document(document: DocumentReading, revision: int) -> dict:
    return {
        "revision": revision,
        "projection": browser_projection(
            document.projection,
            scope="document",
            within=document.within,
            floors=document.floors,
        ),
    }


def browser_undo_candidates(
    events: list,
    document: DocumentReading,
    thread_projection: StateProjection,
    *,
    undo_reading: UndoReading,
    words: GestureWords,
) -> list[dict]:
    """The user's gestures this document can take back, newest first.

    This is the one undo list: `z` takes its first entry and a widget's Undo offers
    the entries naming that widget, so the browser applies no rule of its own. Beyond
    what the append door refuses (`UndoReading`), an entry must paint something on
    this document. An action stands where its widget and verb are in this document's
    projection or the frozen thread
    markup's, and a page action no longer stands once a later revision restated what
    it rests on. A decision carried from an earlier revision is otherwise as
    undoable as one made on this one; where this revision's markup places its unit,
    the door refuses it (`absorbed`).

    `z` takes back the user's newest gesture or nothing, so the head carries
    `newest` only when it is that gesture: the newest of the user's events that
    is neither bookkeeping, an undo, nor already withdrawn. A reply sent after a
    resolve ends the walk rather than letting `z` reach past it, and so does a
    gesture this document no longer paints. Every entry stays on the list for the
    exact control that names it.

    The head carries `gesture`, what an action did in its own document's words
    (`GestureWords.gesture`), so `z` names what it takes in every tab and after a
    reload. Only the head pays for that reading: an exact control names the
    gesture it shows, and the browser words the other kinds from what it already
    holds (undo.js).

    An entry the agent has picked up carries `picked_up`: a delivery handed it into
    an agent's turn (`delivery.opened_input_ids`, the Delivered stage `workflows`
    reads). `z` shows such a gesture before it takes it back, wherever it stands,
    since the agent may have acted on it (undo.js)."""
    candidates = []
    picked_up = opened_input_ids(events)
    withdrawn = undo_reading.withdrawn
    bookkeeping = kinds_declaring("bookkeeping")
    newest = next(
        (
            event["id"]
            for event in reversed(events)
            if event.get("author") == "user"
            and event["kind"] != "undo"
            and event["kind"] not in bookkeeping
            and event["id"] not in withdrawn
        ),
        None,
    )
    for event in reversed(events):
        if (
            event.get("author") != "user"
            or event["kind"] == "undo"
            or event["id"] in withdrawn
        ):
            continue
        if undo_reading.error({"undoes": event["id"]}):
            continue
        item: dict = {"event": event}
        if event["id"] in picked_up:
            item["picked_up"] = True
        if event["kind"] == "action":
            if event["id"] in document.projection.classified:
                if action_retracted(event, document.floors, document.within):
                    continue
                coordinate, _entry = document.projection.classified[event["id"]]
            elif event["id"] in thread_projection.classified:
                coordinate, _entry = thread_projection.classified[event["id"]]
            else:
                continue
            item["coordinate"] = list(coordinate)
        candidates.append(item)
    if candidates and candidates[0]["event"]["id"] == newest:
        head = candidates[0]
        head["newest"] = True
        if head["event"]["kind"] == "action":
            head["gesture"] = words.gesture(head["event"])
    return candidates
