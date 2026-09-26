"""Document-scoped browser projection and undo readings."""

from ..document_reading import DocumentReading, read_document
from ..events import UndoReading, action_retracted
from ..projection import PageReading, StateProjection
from .wire import browser_projection


def browser_document(
    page: PageReading,
    threads: dict,
    data: dict,
) -> tuple[dict, DocumentReading]:
    document = read_document(page, threads, data)
    return (
        {
            "revision": page.revision,
            "projection": browser_projection(
                document.projection,
                scope="document",
                within=document.within,
                floors=document.floors,
            ),
            "requests": document.requests,
            # The complete Ask reading of this revision under the same transaction.
            # The browser draws its tray, walk, and banner count
            # from these lists rather than folding the declarations a second time.
            "asks": document.asks,
        },
        document,
    )


def browser_undo_candidates(
    events: list,
    document: DocumentReading,
    thread_projection: StateProjection,
    *,
    undo_reading: UndoReading,
    stamp: int | None,
) -> list[dict]:
    """The user's gestures this document can take back, newest first.

    This is the one undo list: `z` takes its first entry and a widget's Undo offers
    the entries naming that widget, so the browser applies no rule of its own. Beyond
    what the append door refuses (`UndoReading`), an entry must paint something on
    this document. An approval stands only on the stamp it approved. An action stands
    where its widget and verb are in this document's projection or the frozen thread
    markup's, and a page action no longer stands once a later revision restated what
    it rests on. A decision carried from an earlier revision is otherwise as
    undoable as one made on this one; where this revision's markup places its unit,
    the door refuses it (`absorbed`)."""
    candidates = []
    withdrawn = undo_reading.withdrawn
    for event in reversed(events):
        if (
            event.get("author") != "user"
            or event["kind"] == "undo"
            or event["id"] in withdrawn
        ):
            continue
        if undo_reading.error({"undoes": event["id"]}):
            continue
        if event["kind"] == "done" and event["version"] != stamp:
            continue
        item = {"event": event}
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
    return candidates
