"""The served thread and workflow records the runtime's Node tests build on.

Each invocation emits records exactly as `/api/state` serves them, folded here
through `model_folds.served_reading` rather than written by hand, so a Node test starts from
every field the server sends and cannot omit one the runtime relies on. `thread` and
`workflow` are one record of each, which `served.mjs` hands out for a test to change
only the fields the server sends; `gestures` holds an admitted edit, undo, refusal
and revision sequence shared across runtimes; `question_values` holds typed values
folded by Python for comparison with the browser; `readings` holds whole served readings
whose premise is the case under test. `served.mjs` reads this output directly, so its
assertions always consume this checkout's server rather than a recorded copy.
"""

import json

from interact_support import model_layer
from leaf.agent_state import queues
from leaf.event_log import EventRefused
from leaf.passages import SourceReading
from leaf.projection import StateProjection, authored_rank, question_value
from leaf.questions import collection
from leaf.structure import SourceDocument
from model_folds import leaf_page, served_reading

PAGE = leaf_page("Served records", '<h1 id="h">Steps</h1><p id="p">Two steps.</p>')


def _served(events: tuple[dict, ...]) -> dict:
    state = served_reading(PAGE, events)
    return {
        "threads": state["browser"]["thread"]["threads"],
        "workflows": state["workflows"],
    }


def build() -> dict:
    """A thread the agent answered and the user has read, which is nobody's turn, and
    the workflow of a comment still waiting for the agent to pick it up; then the
    readings named for their case."""
    records = _served(
        (
            {"kind": "comment", "text": "Is the second step right?"},
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Agent",
                "parent": "e1",
                "responds": "e1",
                "text": "Yes.",
            },
            {"kind": "read", "messages": [{"message": "e2", "version": "e2"}]},
            {"kind": "comment", "text": "And the third?"},
        )
    )
    threads = {thread["id"]: thread for thread in records["threads"]}
    workflows = {workflow["id"]: workflow for workflow in records["workflows"]}
    return {
        "question_values": question_value_cases(),
        "thread": threads["e1"],
        "workflow": workflows["e4"],
        "gestures": gesture_sequence(),
        "readings": {
            # A required approval of the exact stamped document, with no other
            # Questions. Keep the whole browser reading for local approval folds.
            "approval": served_reading(
                PAGE.replace(
                    "</head>", '<meta name="lf-review" content="sign-off"></head>'
                ),
                ({"kind": "note", "author": "agent", "version": 1, "text": "Ready"},),
            )["browser"],
            # The agent asks a question over a board it sent, and the user moves a
            # card on it without answering: the thread is the user's to answer, and
            # the move, which owes nothing, stands in it without holding it.
            "frozen move owes nothing": _served(
                (
                    {"kind": "comment", "text": "Lay the feeder work out on a board."},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e1",
                        "responds": "e1",
                        "text": "Here is the board. Which card goes first?",
                        "awaits": True,
                        "markup": model_layer()["lf-board"]["x-example"],
                    },
                    {
                        "kind": "action",
                        "widget": "feeder-board",
                        "action": "move",
                        "detail": {
                            "unit": "card-baffle",
                            "value": "col-doing",
                            "rank": "0i",
                        },
                    },
                )
            ),
            # Something of every kind on each side: an open Ask, a question left in
            # prose, a task the agent put on them, a reply that failed and a page move
            # whose pickup failed are on the user; a comment owed a reply and a task the agent has in hand are on
            # the agent.
            "queues on both sides": _queued(
                (
                    {"kind": "comment", "text": "Weekly?"},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e1",
                        "responds": "e1",
                        "text": "Weekly or daily?",
                        "awaits": True,
                    },
                    {"kind": "comment", "text": "Tighten this."},
                    {"kind": "comment", "text": "Rebuild the chart."},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e4",
                        "responds": "e4",
                        "text": "On it after CI.",
                    },
                    {
                        "kind": "task",
                        "author": "agent",
                        "owner": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "subject": {"kind": "thread", "id": "e4"},
                        "title": "Rebuild the chart",
                    },
                    {"kind": "comment", "text": "Retitle it."},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e7",
                        "responds": "e7",
                        "failure": "turn_failed",
                        "text": "No answer is coming.",
                    },
                    {
                        "kind": "action",
                        "widget": "ship",
                        "action": "choose",
                        "detail": {"value": ["ship-now"]},
                    },
                    {
                        "kind": "pickup",
                        "author": "page",
                        "events": ["e9"],
                        "phase": "failed",
                        "failure": "turn_failed",
                        "session": "served-records",
                        "turn": "turn-1",
                    },
                    {
                        "kind": "start",
                        "author": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "turn": "turn-1",
                        "item": "e6",
                        "text": "Redrawing the chart",
                    },
                    {
                        "kind": "task",
                        "author": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "owner": "user",
                        "subject": {"kind": "page"},
                        "title": "Try the build on a phone",
                    },
                ),
            ),
            # One Ask answered and one open, and a task the agent ended beside one it
            # still holds: only the answered Ask and the ended task are done.
            "done": _done(
                (
                    {
                        "kind": "action",
                        "widget": "ship",
                        "action": "choose",
                        "detail": {"value": ["ship-now"]},
                    },
                    {"kind": "comment", "text": "Rebuild the chart."},
                    {
                        "kind": "task",
                        "author": "agent",
                        "owner": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "subject": {"kind": "thread", "id": "e2"},
                        "title": "Rebuild the chart",
                    },
                    {
                        "kind": "task",
                        "author": "agent",
                        "owner": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "subject": {"kind": "thread", "id": "e2"},
                        "title": "Check the colours",
                    },
                    {
                        "kind": "task_end",
                        "author": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "task": "e4",
                        "outcome": "done",
                        "detail": "Matched the theme",
                    },
                )
            ),
        },
    }


ASK_PAGE = leaf_page(
    "Served queues",
    '<lf-ask id="pick-ask"><h2>Which one?</h2><lf-options id="pick" choose>'
    '<lf-option id="one">One</lf-option><lf-option id="two">Two</lf-option>'
    "</lf-options></lf-ask>"
    '<lf-ask id="ship-ask"><h2>Ship it?</h2><lf-options id="ship" choose>'
    '<lf-option id="ship-now">Now</lf-option><lf-option id="ship-later">Later</lf-option>'
    "</lf-options></lf-ask>",
)


def _done(events: tuple[dict, ...]) -> dict:
    """The reading the browser selects what is done from, as it is handed it: the
    ended explicit tasks and the canonical Question inventory."""
    state = served_reading(ASK_PAGE, events)
    return {
        "tasks": state["browser"]["ended_tasks"],
        "questions": collection(
            state["browser"]["views"]["1"]["document"]["questions"]["all"]
            + state["browser"]["thread"]["questions"]["all"]
        ),
    }


def _queued(events: tuple[dict, ...]) -> dict:
    """The readings `agent_state.queues` selects from, as the browser is handed
    them, and the two queues Python selects from them."""
    state = served_reading(ASK_PAGE, events)
    served = {
        "threads": state["browser"]["thread"]["threads"],
        "workflows": state["workflows"],
        "tasks": state["browser"]["tasks"],
        "questions": collection(
            state["browser"]["views"]["1"]["document"]["questions"]["all"]
            + state["browser"]["thread"]["questions"]["all"]
        ),
    }
    return {**served, "queues": queues(**served)}


def question_value_cases():
    """Shared typed-value fixtures: Python's projection reader supplies expected output.

    These isolate the state boundary from event admission, pairing authored markup
    with its browser initial state and standing value actions. Both runtimes fold
    the same operation specs; no Question-specific store participates.
    """
    cases = []

    def add(
        name,
        record=None,
        *,
        unit="widget",
        body="",
        attrs="",
        initial=None,
        actions=(),
        answered=False,
    ):
        spec = {"unit": unit, **({"record": record} if record else {})}
        markup = f'<lf-value id="owner" {attrs}>{body}</lf-value>'
        registry = {"lf-value": {"x-state": {"set": spec}}}
        source = SourceReading(SourceDocument(markup), registry)
        held = {}
        entries = []
        for seq, (part, detail) in enumerate(actions, 1):
            event = {
                "kind": "action",
                "meaning": {},
                "id": f"e{seq}",
                "seq": seq,
                "widget": "owner",
                "action": "set",
                "detail": detail,
            }
            coordinate = ("owner", part, "set")
            held[coordinate] = (event, spec)
            entries.append(
                {
                    "e": event,
                    "unit": part,
                    "spec": spec,
                    "coordinate": json.dumps(coordinate, separators=(",", ":")),
                }
            )
        projection = StateProjection(held, {}, held, {}, {}, frozenset(), frozenset())
        value, present = question_value(
            "owner",
            "set",
            spec,
            source.document.by_id,
            source.spoken,
            registry,
            projection,
            answered=answered,
        )
        state = {"value": initial}
        if unit != "widget":
            state["units"] = {}
            if record and record["kind"] == "position":
                state["ranks"] = {
                    part: authored_rank(index)
                    for parts in initial.values()
                    for index, part in enumerate(parts)
                }
        cases.append(
            {
                "name": name,
                "spec": spec,
                "authored": state,
                "entries": entries,
                "answered": answered,
                "expected": {"value": value, "present": present},
            }
        )

    attribute = {"kind": "attribute", "attr": "chosen"}
    add("attribute authored empty", attribute, initial=[])
    add("attribute completed empty", attribute, initial=[], answered=True)
    add(
        "attribute sorted action",
        attribute,
        body='<lf-part id="a">A</lf-part><lf-part id="b">B</lf-part>',
        initial=[],
        actions=[("owner", {"value": ["b", "a"]})],
    )
    value = {"kind": "value", "attr": "value"}
    add("value absent despite completion", value, initial=None, answered=True)
    for scalar in (False, 0, ""):
        add(
            f"value action {scalar!r}",
            value,
            initial=None,
            actions=[("owner", {"value": scalar})],
        )
    add(
        "body exact source",
        {"kind": "body"},
        body="<pre>  user words\n</pre>",
        initial="  user words\n",
    )
    add("body completed empty", {"kind": "body"}, initial="", answered=True)
    add("custom undo despite completion", initial=None, answered=True)
    add("custom empty action", initial=None, actions=[("owner", {})])
    add(
        "custom structured action",
        initial=None,
        actions=[("owner", {"outcome": "accept", "text": "Ready"})],
    )
    for kind in ("attribute", "value", "body", "custom"):
        record = (
            attribute
            if kind == "attribute"
            else value
            if kind == "value"
            else {"kind": "body"}
            if kind == "body"
            else None
        )
        detail = (
            {"value": ["b", "a"]}
            if kind == "attribute"
            else {"value": " source "}
            if kind != "custom"
            else {"text": "detail"}
        )
        add(
            f"member {kind}",
            record,
            unit="part",
            initial={},
            body='<lf-part id="a">A</lf-part><lf-part id="b">B</lf-part>',
            actions=[("b", detail), ("a", detail)],
        )
    add(
        "position complete containers",
        {"kind": "position", "within": "lf-container"},
        unit="part",
        initial={"left": ["a"], "right": []},
        body='<lf-container id="left"><lf-part id="a">A</lf-part></lf-container><lf-container id="right"></lf-container>',
        actions=[("a", {"value": "right", "rank": "1"})],
    )
    return cases


def gesture_sequence() -> dict:
    """One real log through edits, undo, a refused duplicate, and two revisions.

    The duplicate undo represents a second tab winning the race: the first tab
    may still draw its pending undo when the log reveals the other's. Retraction
    then replaces the surviving edit, and the next revision must carry that fact.
    """
    authored = {1: "Authored words.", 2: "Rewritten words.", 3: "Rewritten words."}
    documents = {
        revision: leaf_page(
            "Gesture sequence",
            f'<lf-draft id="draft-ops"{(" restated" if revision == 2 else "")}>'
            f"<pre>{value}</pre></lf-draft>",
        )
        for revision, value in authored.items()
    }
    edits = ("First edit.", "Second edit.", "Authored words.")
    commands = [
        {
            "kind": "action",
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"value": value},
            "attempt": f"sequence-edit-{index:03}",
        }
        for index, value in enumerate(edits, 1)
    ]
    withdrawal = {"kind": "undo", "undoes": "e3", "attempt": "sequence-undo-003"}
    commands.append(withdrawal)
    commands.extend(
        {
            "kind": "note",
            "author": "agent",
            "version": revision - 1,
            "revision": revision,
            "text": "Rewrote the draft" if revision == 2 else "Unrelated edit",
            **({"restated": ["draft-ops"]} if revision == 2 else {}),
        }
        for revision in (2, 3)
    )
    states = [
        served_reading(
            {rev: source for rev, source in documents.items() if rev <= revision},
            commands[:through],
        )
        for through, revision in (
            (0, 1),
            (1, 1),
            (2, 1),
            (3, 1),
            (4, 1),
            (5, 2),
            (6, 3),
        )
    ]
    states.append(served_reading(documents, commands, view_revision=1))
    duplicate = {**withdrawal, "attempt": "sequence-duplicate-undo"}
    try:
        served_reading({1: documents[1]}, [*commands[:4], duplicate])
    except EventRefused as error:
        assert "already been taken back" in str(error), str(error)
    else:
        raise AssertionError("The duplicate undo must be refused")
    return {
        "declaration": model_layer()["lf-draft"],
        "authored": authored,
        "commands": commands,
        "states": states,
        "refused": duplicate,
    }


def serialized() -> str:
    return json.dumps(build(), indent=2) + "\n"


if __name__ == "__main__":
    print(serialized(), end="")
