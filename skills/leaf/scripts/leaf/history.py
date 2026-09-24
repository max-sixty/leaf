"""The page's history as rows, newest first: who moved, what they did, to what.

A row is one logged event with everything a reader of it needs that the log alone
does not say outright, derived here once: the thread it belongs to and that
thread's current title, whether a later `undo` took it back, and for a widget
gesture the words its ids had in the gesture's own document (`GestureWords`), under
the declaration that document gave the widget. A later version rewording or
removing an option therefore leaves the row as the user made it, and a retired
widget's rows read as they did before it retired.

What a row names on the page the user is reading now — the section a comment sits
in, the widget a row links to — stays with the page, which holds those places;
this reading carries their ids and anchors.

Bookkeeping stays out: `read`, `pickup`, `summary`, `conversation_title`, `error`,
and `undo`, which marks the gesture it took back instead of standing as its own row.

`history` is a served reading only a page that renders it pays for: the state
carries it when the page's markup holds a widget whose entry declares `x-history`.
"""

from .events import taken_back
from .gesture_words import GestureWords
from .thread_context import thread_roots

# The newest rows a reading carries.
LIMIT = 50

THREAD_KINDS = frozenset({"reply", "edit", "resolve", "unresolve"})
SHOWN = THREAD_KINDS | {
    "comment",
    "action",
    "report",
    "request",
    "receipt",
    "note",
    "done",
}


def wants_history(documents, registry_for) -> bool:
    """Whether any of these (revision, document) pairs holds a widget declaring
    `x-history` in its own registry."""
    return any(
        registry_for(revision).get(record["tag"], {}).get("x-history")
        for revision, document in documents
        for record in document.lf_elements
    )


def _gesture(event: dict, words: GestureWords) -> dict:
    """What an action did, in its record form's terms and its own document's words."""
    spec = words.declaration(event).get("x-state", {}).get(event["action"], {})
    record = spec.get("record") or {}
    detail = event["detail"]
    if record.get("kind") == "attribute":
        chosen = detail.get(record["value"])
        chosen = chosen if isinstance(chosen, list) else [chosen] if chosen else []
        return {"form": "choice", "chosen": [words.name(event, i) for i in chosen]}
    if record.get("kind") == "position":
        return {
            "form": "move",
            "unit": words.name(event, detail[spec["unit"]]),
            "to": words.name(event, detail[record["value"]]),
        }
    if record.get("kind") == "body":
        return {"form": "edit"}
    if creates := spec.get("creates"):
        return {"form": "add", "words": detail[creates["words"]]}
    return {"form": "verb", "verb": event["action"]}


def _report(event: dict, words: GestureWords) -> dict:
    spec = words.declaration(event).get("x-state", {}).get(event["action"], {})
    record = spec.get("record") or {}
    value = event["detail"].get(record["value"]) if record.get("value") else None
    return {
        "widget": event["widget"],
        "value": value if value is not None else event["action"],
        "excerpt": event["detail"][spec["update"]] if spec.get("update") else None,
    }


def history(events: list, threads: dict, words: GestureWords) -> list[dict]:
    """The newest `LIMIT` rows, newest first."""
    by_id = {event["id"]: event for event in events}
    roots = thread_roots(events)
    withdrawn = taken_back(events)

    def thread_of(message_id: str | None) -> dict | None:
        root_id = roots.get(message_id)
        root = by_id.get(root_id)
        if root is None or root["kind"] != "comment":
            return None
        thread = threads.get(root_id)
        opening = thread["root"] if thread else root
        return {
            "id": root_id,
            "title": thread["title"] if thread else None,
            "opening": opening.get("text") or "",
        }

    rows = []
    for event in reversed(events):
        if len(rows) == LIMIT:
            break
        kind = event["kind"]
        if kind not in SHOWN:
            continue
        row = {
            "id": event["id"],
            "ts": event["ts"],
            "kind": kind,
            "author": event["author"],
            "agent": event.get("agent"),
            "undone": event["id"] in withdrawn,
        }
        if kind == "comment":
            row["anchor"] = event.get("anchor")
            row["about"] = event.get("about")
            if event.get("token"):
                row["token"] = event["token"]
            else:
                row["thread"] = thread_of(event["id"])
                row["holds"] = event.get("holds")
                row["drawing"] = bool(event.get("drawing"))
                row["excerpt"] = event.get("text")
        elif kind == "reply":
            row["thread"] = thread_of(event["id"])
            if event.get("token"):
                row["token"] = event["token"]
            else:
                row["excerpt"] = event.get("text")
        elif kind == "edit":
            row["thread"] = thread_of(event["message"])
        elif kind in {"resolve", "unresolve"}:
            row["thread"] = thread_of(event["parent"])
        elif kind == "action":
            row["widget"] = event["widget"]
            row["gesture"] = _gesture(event, words)
        elif kind == "report":
            row.update(_report(event, words))
        elif kind == "request":
            row["widget"] = event["widget"]
            row["operation"] = words.operation(event)
        elif kind == "receipt":
            request = by_id.get(event["request"])
            row["widget"] = request["widget"] if request else None
            row["operation"] = words.operation(request) if request else "request"
            row["status"] = event["status"]
            row["excerpt"] = event.get("text")
        elif kind == "note":
            row["version"] = event["version"]
            row["excerpt"] = event["text"]
        else:
            row["version"] = event["version"]
        rows.append(row)
    return rows
