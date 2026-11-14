"""The served thread and workflow records the runtime's Node tests build on.

Each invocation emits records exactly as `/api/state` serves them, folded here
through `model_folds.served_reading` rather than written by hand, so a Node test starts from
every field the server sends and cannot omit one the runtime relies on. `thread`,
`workflow` and `activity` are one record of each, and `state` a whole answer, which `served.mjs` hands out for a
test to change only the fields the server sends; `gestures` holds an admitted edit, undo, refusal
and revision sequence shared across runtimes; `tails` holds answers that complete a
reading the browser holds, each beside that reading and the whole answer;
`obligation_values` holds typed values
folded by Python for comparison with the browser; `state_definitions` holds the
operation definitions Python records, for the browser's comparison of them; `readings`
holds served readings whose premise is the case under test, each its threads, workflows
and obligation records. `served.mjs` reads this output directly, so its
assertions always consume this checkout's server rather than a recorded copy.
"""

import json
from pathlib import Path

from interact_support import model_layer
from model_folds import NOW, UNCLAIMED, leaf_page, served_answer, served_reading

from leaf.event_log import EventRefused
from leaf.passages import SourceReading
from leaf.projection import (
    AuthoredOrders,
    StateProjection,
    attribute_marks,
    authored_rank,
    obligation_value,
)
from leaf.registry.contract import state_definition
from leaf.structure import SourceDocument

PAGE = leaf_page("Served records", '<h1 id="h">Steps</h1><p id="p">Two steps.</p>')


def _served(events: tuple[dict, ...]) -> dict:
    """The threads, workflows and obligation records one log's reading serves, so a
    thread's `attention`, the id of the record that speaks for it, joins its record."""
    state = served_reading(PAGE, events)
    [view] = state["browser"]["views"].values()
    return {
        "threads": view["thread"]["threads"],
        "workflows": state["workflows"],
        "obligations": view["obligations"],
    }


# A question the agent asked in a thread of its own, about the page.
QUESTION = {
    "kind": "comment",
    "author": "agent",
    "agent": "Agent",
    "session": "served-records",
    "text": "Can you try the build on a phone, and reply once it opens?",
    "obligation": True,
}

# Something of every kind on each list: a widget obligation, a question, a reply that
# failed and a page action whose pickup failed are on On Me; a comment owed a reply and
# a to-do the agent has in hand are on On <agent>.
BOTH_SIDES = (
    {"kind": "comment", "text": "Weekly?"},
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "parent": "e1",
        "responds": "e1",
        "text": "Weekly or daily?",
        "obligation": True,
    },
    {"kind": "comment", "text": "Tighten this."},
    {"kind": "comment", "text": "Rebuild the chart."},
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "session": "served-records",
        "parent": "e4",
        "responds": "e4",
        "text": "On it after CI.",
        "todo": "Rebuild the chart",
    },
    {"kind": "comment", "text": "Retitle it."},
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "parent": "e6",
        "responds": "e6",
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
        "events": ["e8"],
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
        "item": "e5",
        "text": "Redrawing the chart",
    },
)


SUGGESTION_PAGE = leaf_page(
    "Suggested change",
    '<lf-suggestion id="sug-refill" resolves="e1">'
    '<lf-old><p id="refill-rule">Refill every morning.</p></lf-old>'
    "<lf-new><p>Refill when half-empty.</p></lf-new>"
    "</lf-suggestion>",
)
SUGGESTED = (
    {"kind": "comment", "text": "Refill less often?"},
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "parent": "e1",
        "responds": "e1",
        "text": "Suggested a rule above.",
    },
)


REWRITTEN_TWICE = (
    {"kind": "comment", "text": "Chart 2024."},
    {"kind": "edit", "message": "e1", "text": "Chart 2025."},
    {"kind": "edit", "message": "e1", "text": "Chart 2026."},
)

# A reaction the agent answered, and the user's own reaction on that answer.
ANSWERED_REACTION = (
    {"kind": "comment", "token": "change"},
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "parent": "e1",
        "text": "Which part?",
    },
    {"kind": "reply", "parent": "e2", "token": "keep"},
)

# A reply the user sent in a thread, and the agent's answer to it.
ANSWERED_REPLY = (
    {"kind": "comment", "text": "Too long?"},
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "parent": "e1",
        "text": "Which part?",
    },
    {"kind": "reply", "parent": "e2", "text": "The rollout section."},
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "parent": "e3",
        "text": "Cutting it.",
    },
)


def build() -> dict:
    """A thread the agent answered and the user has read, which is nobody's turn,
    the workflow of a comment still waiting for the agent to pick it up, and the
    activity of a page a session holds; then the readings named for their case."""
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
        "obligation_values": obligation_value_cases(),
        "thread": threads["e1"],
        "workflow": workflows["e4"],
        # The whole answer for a page with an empty log.
        "state": served_answer(PAGE),
        # The page-wide activity of a page a live session holds, owing nothing.
        "activity": served_reading(PAGE, presence=HELD)["activity"],
        "gestures": gesture_sequence(),
        "tails": tail_cases(),
        "obligation_row": _served_obligation_row(),
        "state_definitions": state_definition_cases(),
        "readings": {
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
                        "markup": model_layer()["lf-board"]["x-example"],
                        "obligation": True,
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
            # The user rewrote their comment twice, then took the second rewrite back.
            **{
                name: _served(REWRITTEN_TWICE + tail)
                for name, tail in (
                    ("rewritten twice", ()),
                    (
                        "rewritten twice, the last taken back",
                        ({"kind": "undo", "undoes": "e3"},),
                    ),
                )
            },
            # The user took an answered reply back, which keeps its place.
            **{
                name: _served(ANSWERED_REPLY + tail)
                for name, tail in (
                    ("a reply answered", ()),
                    (
                        "a reply answered, taken back",
                        ({"kind": "undo", "undoes": "e3"},),
                    ),
                )
            },
            # The user took both reactions back: the answered one keeps its place.
            **{
                name: _served(ANSWERED_REACTION + tail)
                for name, tail in (
                    ("a reaction answered", ()),
                    (
                        "a reaction answered, both reactions taken back",
                        (
                            {"kind": "undo", "undoes": "e3"},
                            {"kind": "undo", "undoes": "e1"},
                        ),
                    ),
                )
            },
            # A reaction the agent attached a to-do to, then taken back.
            **{
                name: _served(
                    (
                        {"kind": "comment", "token": "change"},
                        {
                            "kind": "todo",
                            "author": "agent",
                            "agent": "Agent",
                            "session": "served-records",
                            "subject": {"kind": "thread", "id": "e1"},
                            "title": "Rework the passage",
                        },
                        *tail,
                    )
                )
                for name, tail in (
                    ("a reaction holding a to-do", ()),
                    (
                        "a reaction holding a to-do taken back",
                        ({"kind": "undo", "undoes": "e1"},),
                    ),
                )
            },
            # A reaction the user marked with another, the first taken back, then both.
            **{
                name: _served(
                    (
                        {"kind": "comment", "token": "change"},
                        {"kind": "reply", "parent": "e1", "token": "keep"},
                        {"kind": "undo", "undoes": "e1"},
                        *tail,
                    )
                )
                for name, tail in (
                    ("a reaction on a reaction taken back", ()),
                    (
                        "a reaction on a reaction, both taken back",
                        ({"kind": "undo", "undoes": "e2"},),
                    ),
                )
            },
            # The agent asked the user a question, the only thing On Me holds.
            "question": served_answer(PAGE, (QUESTION,)),
            "queues on both sides": served_reading(
                OBLIGATION_PAGE,
                BOTH_SIDES,
            ),
            # Two to-dos the agent holds on a page it is working on: a start running
            # on one went quiet past the working grace, and the other's is current.
            "quiet start": served_reading(
                OBLIGATION_PAGE,
                (
                    *(
                        {
                            "kind": "todo",
                            "author": "agent",
                            "agent": "Agent",
                            "session": "served-records",
                            "subject": {"kind": "page"},
                            "title": title,
                        }
                        for title in ("Rebuild the chart", "Check the colours")
                    ),
                    *(
                        {
                            "kind": "start",
                            "author": "agent",
                            "agent": "Agent",
                            "session": "served-records",
                            "turn": "turn-1",
                            "item": item,
                            "text": text,
                            "ts": ts,
                        }
                        for item, text, ts in (
                            ("e1", "Redrawing the chart", QUIET),
                            ("e2", "Comparing the palette", NOW),
                        )
                    ),
                ),
                presence=HELD,
            ),
            # The user asked for a change in a thread, and the agent answered with a
            # page suggestion whose acceptance closes that thread.
            "suggestion closes a thread": served_reading(SUGGESTION_PAGE, SUGGESTED),
            # The same page once the user accepted the suggestion.
            "suggestion accepted": served_reading(
                SUGGESTION_PAGE,
                (
                    *SUGGESTED,
                    {
                        "kind": "action",
                        "widget": "sug-refill",
                        "action": "decide",
                        "detail": {"outcome": "accept"},
                    },
                ),
            ),
            # One obligation answered and one open, and a to-do the agent ended beside one it
            # still holds: only the answered obligation and the ended to-do are done.
            "done": served_reading(
                OBLIGATION_PAGE,
                (
                    {
                        "kind": "action",
                        "widget": "ship",
                        "action": "choose",
                        "detail": {"value": ["ship-now"]},
                    },
                    {"kind": "comment", "text": "Rebuild the chart."},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "parent": "e2",
                        "responds": "e2",
                        "text": "Rebuilding it.",
                        "todo": "Rebuild the chart",
                    },
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "parent": "e2",
                        "text": "And checking the colours.",
                        "todo": "Check the colours",
                    },
                    {
                        "kind": "todo_end",
                        "author": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "todo": "e4",
                        "outcome": "done",
                        "detail": "Matched the theme",
                    },
                ),
            ),
        },
    }


# A page the agent's live session holds while it works, and a moment past the grace
# a start's line stays current for (`activity.WORKING_GRACE`).
HELD = {
    **UNCLAIMED,
    "status": {"state": "working", "ts": NOW},
    "listening": True,
    "session_alive": True,
    "claim_session": "served-records",
    "turn": "turn-1",
}
QUIET = "2026-09-19T11:30:00+00:00"

OBLIGATION_PAGE = leaf_page(
    "Served queues",
    '<lf-ask id="pick-ask"><h2>Which one?</h2><lf-options id="pick" choose>'
    '<lf-option id="one">One</lf-option><lf-option id="two">Two</lf-option>'
    "</lf-options></lf-ask>"
    '<lf-ask id="ship-ask"><h2>Ship it?</h2><lf-options id="ship" choose>'
    '<lf-option id="ship-now">Now</lf-option><lf-option id="ship-later">Later</lf-option>'
    "</lf-options></lf-ask>",
)


def _served_obligation_row() -> dict:
    """One obligation's row as On Me lists it (`served_state.queues`)."""
    state = served_reading(OBLIGATION_PAGE, BOTH_SIDES)
    return next(
        row
        for row in state["browser"]["views"]["1"]["queues"]["on_user"]
        if row["kind"] == "widget"
    )


def obligation_value_cases():
    """Shared typed-value fixtures: Python's projection reader supplies expected output.

    These isolate the state boundary from event admission, pairing authored markup
    with its browser initial state and value actions in force. Both runtimes fold
    the same operation specs; no obligation-specific store participates.
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
        selected_unit=None,
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
        value, present = obligation_value(
            "owner",
            "set",
            spec,
            source.document.by_id,
            attribute_marks(source.document.by_id, source.spoken, registry),
            AuthoredOrders(source.document.by_id, registry),
            projection,
            answered=answered,
            unit=selected_unit,
        )
        state = {"value": initial}
        if unit != "widget":
            state["units"] = {}
            if record and record["kind"] == "position":
                state["ranks"] = {
                    part: authored_rank(index)
                    for parts in (initial or {}).values()
                    for index, part in enumerate(parts)
                }
        cases.append(
            {
                "name": name,
                "spec": spec,
                "authored": state,
                "entries": entries,
                "answered": answered,
                **({"unit": selected_unit} if selected_unit is not None else {}),
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
    for selected_unit in ("a", "b", "missing"):
        add(
            f"selected custom unit {selected_unit}",
            unit="part",
            initial={},
            selected_unit=selected_unit,
            actions=[("a", {"approved": True}), ("b", {"approved": False})],
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
    commands: list[dict] = [
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
        assert error.findings[0].code == "withdrawn-gesture", str(error)
    else:
        raise AssertionError("The duplicate undo must be refused")
    layer = model_layer()
    return {
        "declaration": layer["lf-draft"],
        "stamped": layer["$states"]["lf-draft"],
        "authored": authored,
        "commands": commands,
        "states": states,
        "refused": duplicate,
    }


TAIL_PAGE = leaf_page(
    "Served tails",
    '<p id="p">Two questions.</p>'
    '<lf-ask id="kinds-ask"><h2>Which kinds?</h2><lf-options id="kinds" choose multiple>'
    '<lf-option id="red">Red</lf-option><lf-option id="blue">Blue</lf-option>'
    "</lf-options></lf-ask>"
    '<lf-ask id="ship-ask"><h2>Ship it?</h2><lf-options id="ship" choose>'
    '<lf-option id="now">Now</lf-option><lf-option id="later">Later</lf-option>'
    "</lf-options></lf-ask>",
)
# Picks, a comment and its answer, an undo of an older pick, which withdraws a held
# projection entry and drops it from the undo list, and a pickup, which marks held
# undo entries picked up.
TAIL_LOG = (
    {
        "kind": "action",
        "widget": "kinds",
        "action": "choose",
        "detail": {"value": ["red"]},
        "attempt": "tail-attempt-0001",
    },
    {
        "kind": "action",
        "widget": "kinds",
        "action": "choose",
        "detail": {"value": ["red", "blue"]},
        "attempt": "tail-attempt-0002",
    },
    {"kind": "comment", "text": "Why both?", "attempt": "tail-attempt-0003"},
    {
        "kind": "action",
        "widget": "ship",
        "action": "choose",
        "detail": {"value": ["now"]},
        "attempt": "tail-attempt-0004",
    },
    {"kind": "undo", "undoes": "e2", "attempt": "tail-attempt-0005"},
    {
        "kind": "pickup",
        "author": "page",
        "events": ["e1", "e3", "e4"],
        "phase": "opened",
        "session": "served-records",
        "turn": "turn-1",
    },
    {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "session": "served-records",
        "parent": "e3",
        "responds": "e3",
        "text": "Red alone, then.",
    },
    {
        "kind": "action",
        "widget": "kinds",
        "action": "answer",
        "detail": {},
        "attempt": "tail-attempt-0008",
    },
)


def tail_cases() -> list[dict]:
    """Answers that complete a reading the browser holds, each beside that reading and
    the whole answer at the same position, for the browser's completion to be held to
    (`served_state.tail`). One changes only what the page's claim reads, with nothing
    logged between, and the last is a reply that joins a long thread, which changes
    that thread from within."""
    # A thread the agent and the user have gone back and forth in, and one more reply.
    exchange = (
        *TAIL_LOG[:3],
        *(
            {"kind": "reply", "parent": "e3", "text": f"And {at}?"}
            if at % 2
            else {
                "kind": "reply",
                "author": "agent",
                "parent": "e3",
                "text": f"So {at}.",
            }
            for at in range(6)
        ),
        {"kind": "reply", "parent": "e3", "text": "Thanks."},
    )
    cases = []
    for name, log, held, through, presence in (
        ("a pick after a pick", TAIL_LOG, 1, 2, UNCLAIMED),
        ("an undo of an older pick", TAIL_LOG, 4, 5, UNCLAIMED),
        ("a pickup", TAIL_LOG, 5, 6, UNCLAIMED),
        ("several events at once", TAIL_LOG, 2, len(TAIL_LOG), UNCLAIMED),
        ("nothing new", TAIL_LOG, len(TAIL_LOG), len(TAIL_LOG), UNCLAIMED),
        ("a session claims the page", TAIL_LOG, 3, 3, HELD),
        (
            "a reply to a long thread",
            exchange,
            len(exchange) - 1,
            len(exchange),
            UNCLAIMED,
        ),
    ):
        reading = served_reading(TAIL_PAGE, log[:held])
        key = reading["browser"]["basis"]["key"]
        tail = served_reading(TAIL_PAGE, log[:through], presence=presence, held=key)
        assert "since" in tail, name
        whole = served_reading(TAIL_PAGE, log[:through], presence=presence)
        cases.append({"name": name, "held": reading, "tail": tail, "whole": whole})
    # A widget's value set twice to values a careless patch confuses: `false` then
    # `0`, which Python's own equality takes for the same value; an empty list then a
    # list of one empty string; and an object that gains a field named `__proto__`,
    # which assigning would make the object's prototype rather than its field.
    registry = {
        **model_layer(),
        "lf-value-ask": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "active": {"type": "boolean"},
                "value": {
                    "type": ["boolean", "integer", "array", "object"],
                    "items": {"type": "string"},
                },
            },
            "required": ["id"],
            "additionalProperties": False,
            "x-content": "none",
            "x-awaits": {
                "when": {"active": [True]},
                "value": "set",
                "answered": {"set": {}},
            },
            "x-state": {
                "set": {"unit": "widget", "record": {"kind": "value", "attr": "value"}}
            },
        },
    }
    typed = leaf_page("Typed", '<lf-value-ask id="typed" active></lf-value-ask>')
    for name, values in (
        ("false, then 0", (False, 0)),
        ('[], then [""]', ([], [""])),
        ("{}, then __proto__", ({}, {"__proto__": {"n": 1}})),
    ):
        sets = [
            {
                "kind": "action",
                "widget": "typed",
                "action": "set",
                "detail": {"value": value},
            }
            for value in values
        ]
        reading = served_reading(typed, sets[:1], registry=registry)
        key = reading["browser"]["basis"]["key"]
        tail = served_reading(typed, sets, registry=registry, held=key)
        assert "since" in tail, name
        whole = served_reading(typed, sets, registry=registry)
        cases.append({"name": name, "held": reading, "tail": tail, "whole": whole})
    return cases


def state_definition_cases() -> list[dict]:
    """`state_definition_cases.json`, each pair of detail schemas as the definitions
    Python records, so the browser's comparison is held to the same verdicts."""
    cases = json.loads(
        Path(__file__).with_name("state_definition_cases.json").read_text()
    )
    return [
        {
            "id": case["id"],
            "definitions": [
                state_definition(
                    "lf-local", {}, {"unit": "widget", "detail": case[key]}
                )
                for key in ("before", "after")
            ],
            "same": case["same"],
        }
        for case in cases
    ]


def serialized() -> str:
    return json.dumps(build(), indent=2) + "\n"


if __name__ == "__main__":
    print(serialized(), end="")
