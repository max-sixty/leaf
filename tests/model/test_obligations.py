"""One obligation inventory, its canonical values, and its presentation context."""

import json
from copy import deepcopy
from pathlib import Path

import model_folds as model
import pytest
from interact_support import (
    refused_on,
    served_obligations,
)

from leaf import obligations as obligations_model
from leaf.gesture_words import element_name
from leaf.passages import SourceReading
from leaf.projection import page_reading
from leaf.served_state.browser import browser_state
from leaf.structure import SourceDocument
from leaf.work_reading import WorkReading

OPTIONS = '<lf-options id="choice" {attrs}><lf-option id="a">A</lf-option><lf-option id="b">B</lf-option></lf-options>'


def page(attrs="choose", context=None):
    content = OPTIONS.format(attrs=attrs)
    if context:
        content = f'<lf-ask id="{context}"><h2>Which route?</h2>{content}</lf-ask>'
    return model.leaf_page("Questions", content)


def page_obligations(state, revision=1):
    """The obligations the page's document makes in view `revision`."""
    view = state["views"][str(revision)]
    return obligations_model.collection(
        [
            item
            for item in view["obligations"]
            if item["thread"] is None and item["source"]["kind"] != "update"
        ]
    )


def test_context_changes_prompt_target_without_changing_obligation_identity_or_value():
    state = model.reading(
        {1: page(), 2: page(context="evidence")},
        [
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["a"]},
            }
        ],
    )
    [item] = page_obligations(state, 2)["all"]
    assert (item["id"], item["source"]["id"]) == ("widget:choice", "choice")
    assert item["prompt"] == {"text": "Which route?", "target": "evidence"}
    assert item["answer"]["value"] == ["a"]
    assert item["status"] == "answered"
    assert state["todos"] == []


def test_a_decision_is_independent_and_survives_revision_until_restated():
    """A permission is an ordinary decision: it answers its own request, and a
    completion stamp does not ask again."""
    permit = (
        '<lf-options id="permit" choose><lf-option id="publish">Publish</lf-option>'
        '<lf-option id="hold">Keep it private</lf-option></lf-options>'
    )
    document = model.leaf_page("Permission", permit + OPTIONS.format(attrs="choose"))
    approved = {
        "kind": "action",
        "id": "approval",
        "widget": "permit",
        "action": "choose",
        "detail": {"value": ["publish"]},
    }
    state = model.reading(document, [approved])
    items = {item["id"]: item for item in page_obligations(state)["all"]}
    assert items["widget:permit"]["status"] == "answered"
    assert items["widget:permit"]["answer"]["event"]["id"] == "approval"
    assert items["widget:choice"]["status"] == "open"
    assert any(
        item["id"] == "update:approval"
        for item in state["views"]["1"]["queues"]["on_agent"]
    )

    # The stamp that records the pick in the markup settles the agent's update.
    revised = document.replace("Permission", "Permission and progress").replace(
        '<lf-option id="publish">', '<lf-option id="publish" chosen>'
    )
    stamp = {
        "kind": "note",
        "author": "agent",
        "version": 1,
        "revision": 2,
        "text": "Published the report.",
    }
    state = model.reading({1: document, 2: revised}, [approved, stamp])
    items = {item["id"]: item for item in page_obligations(state, 2)["all"]}
    assert items["widget:permit"]["status"] == "answered"
    assert state["views"]["2"]["queues"]["on_agent"] == []

    state = model.reading(document, [approved, {"kind": "undo", "undoes": "approval"}])
    items = {item["id"]: item for item in page_obligations(state)["all"]}
    assert items["widget:permit"]["status"] == "open"

    # Restating asks again, so the new version carries no pick.
    changed = document.replace('id="permit" choose', 'id="permit" choose restated')
    state = model.reading(
        {1: document, 2: changed}, [approved, {**stamp, "restated": ["permit"]}]
    )
    items = {item["id"]: item for item in page_obligations(state, 2)["all"]}
    assert items["widget:permit"]["status"] == "open"


def test_obligations_name_their_exact_owning_message_without_conflating_thread_identity():
    document = page()
    events: list[dict] = [
        {
            "kind": "note",
            "id": "stamp",
            "author": "agent",
            "version": 1,
            "text": "Ready",
        },
        {
            "kind": "comment",
            "id": "thread",
            "author": "agent",
            "text": "Choose the first route.",
            "markup": OPTIONS.format(attrs="choose").replace('id="', 'id="root-'),
        },
        {
            "kind": "reply",
            "id": "later",
            "author": "agent",
            "parent": "thread",
            "text": "Choose the later route too.",
            "markup": OPTIONS.format(attrs="choose").replace('id="', 'id="later-'),
        },
        {
            "kind": "comment",
            "id": "prompt",
            "author": "agent",
            "text": "Is this useful?",
            "obligation": True,
        },
    ]
    state = model.reading(document, events)
    inventory = {
        item["id"]: (item["thread"], item["message"])
        for item in [*page_obligations(state)["all"], *served_obligations(state)["all"]]
    }
    assert inventory == {
        "widget:choice": (None, None),
        "widget:root-choice": ("thread", "thread"),
        "widget:later-choice": ("thread", "later"),
        "message:prompt": ("prompt", "prompt"),
    }


def test_partial_and_completed_empty_values_are_distinct_from_no_answer_and_undo_reopens():
    document = page("choose multiple")
    events: list[dict] = [
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": []},
        }
    ]
    [initial] = page_obligations(model.reading(document))["all"]
    assert initial["answer"] is None
    [partial] = page_obligations(model.reading(document, events))["all"]
    assert (partial["status"], partial["answer"]["value"]) == ("open", [])
    events.append(
        {"kind": "action", "widget": "choice", "action": "answer", "detail": {}}
    )
    [completed] = page_obligations(model.reading(document, events))["all"]
    assert (completed["status"], completed["answer"]["value"]) == ("answered", [])
    assert completed["answer"]["event"]["id"] == "e2"
    events.append({"kind": "undo", "undoes": "e2"})
    [reopened] = page_obligations(model.reading(document, events))["all"]
    assert (reopened["status"], reopened["answer"]["value"]) == ("open", [])


def test_unrequested_widget_is_absent_but_removed_predicate_withdraws_existing_request():
    assert page_obligations(model.reading(page("")))["all"] == []
    [withdrawn] = page_obligations(model.reading({1: page(), 2: page("")}), 2)["all"]
    assert (withdrawn["status"], withdrawn["answer"], withdrawn["next_actor"]) == (
        "withdrawn",
        None,
        None,
    )
    assert (
        page_obligations(model.reading({1: page(), 2: page("restated")}), 2)["all"]
        == []
    )


def test_pinned_document_uses_unrequested_intermediate_history_for_registration():
    registry = model.model_layer()
    readings = {
        index: SourceReading(
            SourceDocument(page("choose" if index == 2 else "")), registry
        )
        for index in range(1, 5)
    }
    state, _ = browser_state(
        {3: readings[3], 4: readings[4]},
        [],
        4,
        model.UNCLAIMED,
        {"revision": 4, "version": 4},
        {3, 4},
        model.NOW,
        revisions=readings.__getitem__,
        revision_ids=set(readings),
    )
    for revision in (3, 4):
        [item] = page_obligations(state, revision)["all"]
        assert (item["id"], item["status"]) == ("widget:choice", "withdrawn")


def test_a_pinned_view_reads_its_frozen_threads_under_its_own_registry():
    """A revision captured its thread widgets under its own registry, so a view
    pinned to it classifies their decisions there. A decision whose operation that
    registry defines otherwise is none in that view: the obligation it answers stays open
    and the thread the user's, while the active view reads it answered and the
    thread waiting on the agent to pick it up."""

    def registry(attr):
        layer = deepcopy(model.model_layer())
        layer["lf-value-ask"] = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "active": {"type": "boolean"},
                "value": {"type": "boolean"},
                "chosen": {"type": "boolean"},
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
                "set": {"unit": "widget", "record": {"kind": "value", "attr": attr}}
            },
        }
        return layer

    earlier, later = registry("value"), registry("chosen")
    document = model.leaf_page("Value", '<p id="p">Notes.</p>')
    events: list[dict] = model.served_reading(
        document,
        [
            {
                "kind": "comment",
                "author": "agent",
                "text": "Ship it?",
                "markup": '<lf-value-ask id="typed" active></lf-value-ask>',
            },
            {
                "kind": "action",
                "widget": "typed",
                "action": "set",
                "detail": {"value": True},
            },
        ],
        registry=later,
    )["events"]
    parsed = SourceDocument(document)
    state, _ = browser_state(
        {1: SourceReading(parsed, earlier), 2: SourceReading(parsed, later)},
        events,
        2,
        model.UNCLAIMED,
        {"revision": 2, "version": 2},
        {1, 2},
        model.NOW,
    )

    def read(revision):
        view = state["views"][str(revision)]
        [thread] = view["thread"]["threads"]
        [item] = [
            entry
            for entry in view["obligations"]
            if entry["thread"] and entry["source"]["kind"] == "widget"
        ]
        return (
            [entry["event"]["id"] for entry in view["thread"]["projection"]["entries"]],
            (item["id"], item["status"]),
            thread["attention"],
            [item["id"] for item in view["queues"]["on_user"]],
        )

    assert read(2) == (
        [events[1]["id"]],
        ("widget:typed", "answered"),
        {"kind": "waiting", "reason": "workflow", "workflow": events[1]["id"]},
        [],
    )
    assert read(1) == (
        [],
        ("widget:typed", "open"),
        {"kind": "needs_user", "reason": "obligation", "workflow": None},
        ["widget:typed"],
    )


@pytest.mark.parametrize("value", [False, 0])
def test_false_and_zero_are_typed_answers(value):
    registry = deepcopy(model.model_layer())
    registry["lf-value-ask"] = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "active": {"type": "boolean"},
            "value": {"type": ["boolean", "integer"]},
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
    }
    document = model.leaf_page(
        "Value", '<lf-value-ask id="typed" active></lf-value-ask>'
    )
    [item] = page_obligations(
        model.reading(
            document,
            [
                {
                    "kind": "action",
                    "widget": "typed",
                    "action": "set",
                    "detail": {"value": value},
                }
            ],
            registry=registry,
        )
    )["all"]
    assert item["status"] == "answered"
    assert item["answer"]["value"] is value


def test_changed_partial_value_does_not_reuse_an_earlier_completion_event():
    events: list[dict] = [
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["a"]},
        },
        {"kind": "action", "widget": "choice", "action": "answer", "detail": {}},
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["b"]},
        },
    ]
    state = model.reading(page("choose multiple"), events)
    [item] = page_obligations(state)["all"]
    assert item["answer"] == {"value": ["b"], "event": None}


def answered_in_words(*later):
    """A user's comment, the agent's reply asking back in words, then `later`."""
    return [
        {"kind": "comment", "id": "t", "author": "user", "text": "Schedule it."},
        {
            "kind": "reply",
            "id": "asking",
            "author": "agent",
            "parent": "t",
            "responds": "t",
            "text": "Weekly or daily?",
            "obligation": True,
        },
        *later,
    ]


def test_a_question_in_a_reply_waits_on_the_user_until_their_next_message():
    """A message's obligation is answered in words: it waits on the user, titled by its
    words, until their next message in its thread, which is its answer."""
    [item] = served_obligations(model.reading(page(""), answered_in_words()))["all"]
    assert (item["id"], item["status"], item["next_actor"]) == (
        "message:asking",
        "open",
        "user",
    )
    assert item["prompt"]["text"] == "Weekly or daily?"
    state = model.reading(
        page(""),
        answered_in_words(
            {
                "kind": "reply",
                "id": "r",
                "author": "user",
                "parent": "t",
                "text": "Daily",
            }
        ),
    )
    [item] = served_obligations(state)["all"]
    assert (item["status"], item["next_actor"]) == ("answered", None)
    assert item["answer"]["value"] == {"text": "Daily"}
    assert item["answer"]["event"]["id"] == "r"
    assert lists(state) == ([], ["update:r"], [])


def test_the_agent_ends_a_question_the_user_answered_elsewhere():
    state = model.reading(
        page(""),
        answered_in_words(
            {
                "kind": "todo_end",
                "author": "agent",
                "todo": "message:asking",
                "outcome": "done",
                "detail": "answered in chat",
            }
        ),
    )
    [item] = served_obligations(state)["all"]
    assert (item["status"], item["next_actor"], item["answer"]) == (
        "answered_elsewhere",
        None,
        None,
    )
    assert item["end"]["detail"] == "answered in chat"


def test_a_frame_around_a_decision_widget_stays_one_obligation():
    [item] = page_obligations(model.reading(page(context="frame"), []))["all"]
    assert (item["id"], item["prompt"]["target"]) == ("widget:choice", "frame")


def lists(state) -> tuple[list, list, list]:
    """On me and On <agent> as served, and the open widget obligations whose next move
    is the agent's, which On <agent> lists through the update that handed them over."""
    queues = state["views"]["1"]["queues"]
    items = state["views"]["1"]["obligations"]
    return (
        sorted(item["id"] for item in queues["on_user"]),
        sorted(item["id"] for item in queues["on_agent"]),
        sorted(
            item["id"]
            for item in items
            if item["status"] == "open"
            and item["next_actor"] == "agent"
            and item["source"]["kind"] != "update"
        ),
    )


def test_on_me_lists_one_row_for_each_place_the_user_answers_at():
    """A thread's reply answers every question asked in it, so they share its row, and a
    thread about a decision is one place with it, so its row rides on the decision's.
    Each record still settles by its own rule: answering the decision leaves the
    thread's questions on their own row until the user replies."""
    document = model.leaf_page(
        "Questions",
        '<p id="intro">Context.</p><section id="case"><h2>Which route?</h2>'
        + OPTIONS.format(attrs="choose")
        + "</section>",
    )

    def asked(thread, anchor, *replies):
        return [
            {
                "kind": "comment",
                "id": thread,
                "author": "user",
                "text": "Show me.",
                "anchor": {"section": anchor},
            },
            *(
                {
                    "kind": "reply",
                    "id": reply,
                    "author": "agent",
                    "parent": thread,
                    "responds": thread,
                    "text": "Try it before choosing.",
                    "obligation": True,
                }
                for reply in replies
            ),
        ]

    events: list[dict] = asked("about", "case", "r1", "r2") + asked(
        "aside", "intro", "r3"
    )

    def rows(state):
        return sorted(
            (row["id"], row["also"]) for row in state["views"]["1"]["queues"]["on_user"]
        )

    assert rows(model.reading(document, events)) == [
        ("message:r3", []),
        ("widget:choice", ["message:r1", "message:r2"]),
    ]
    chosen = {
        "kind": "action",
        "widget": "choice",
        "action": "choose",
        "detail": {"value": ["a"]},
    }
    assert rows(model.reading(document, [*events, chosen])) == [
        ("message:r1", ["message:r2"]),
        ("message:r3", []),
    ]


FRAMED = model.leaf_page(
    "Questions",
    '<p id="intro">Context.</p><section id="case">'
    '<lf-ask id="frame"><h2 id="head">Two routes</h2><div id="first">'
    + OPTIONS.format(attrs="choose")
    + "</div>"
    + OPTIONS.format(attrs="choose").replace('id="', 'id="y-')
    + OPTIONS.format(attrs="").replace('id="', 'id="shown-')
    + "</lf-ask></section>",
)


@pytest.mark.parametrize(
    ("anchor", "held"),
    [
        ({"section": "a", "quote": "A"}, ["widget:choice"]),
        ({"section": "head", "quote": "Two"}, ["widget:choice", "widget:y-choice"]),
        ({"section": "shown-a", "quote": "A"}, ["widget:choice", "widget:y-choice"]),
        ({"section": "first"}, ["widget:choice"]),
        ({"section": "case"}, ["widget:choice", "widget:y-choice"]),
        ({"section": "intro", "quote": "Context"}, []),
    ],
    ids=["option", "frame", "display-only", "part", "section", "elsewhere"],
)
def test_a_comment_on_an_obligation_is_the_agents_turn_until_the_agent_replies(
    anchor, held
):
    """The user's comment about an open obligation hands it to the agent without answering
    it: the obligation leaves On me while the comment's answer stands on On <agent>, and comes
    back once the agent replies, or once the agent ends the work its reply promised, which
    a resolution leaves standing: that is how a decision the user put off until other
    work lands stays off their list. A comment on one obligation, or on the part of the
    frame holding it, leaves its framed sibling with the user; one on the frame's
    heading, on a widget there that asks nothing or on the section holding the frame is
    about both, and one elsewhere about none."""
    comment = {
        "kind": "comment",
        "id": "c1",
        "author": "user",
        "text": "What does this mean?",
        "anchor": anchor,
    }
    items = ["widget:choice", "widget:y-choice"]
    owed = sorted(set(items) - set(held))
    assert lists(model.reading(FRAMED, [comment])) == (owed, ["update:c1"], held)
    reply = {
        "kind": "reply",
        "author": "agent",
        "parent": "c1",
        "responds": "c1",
        "text": "It means the first route.",
    }
    assert lists(model.reading(FRAMED, [comment, reply])) == (items, [], [])
    promise = {**reply, "id": "p1", "todo": "Ask again once the other work lands"}
    resolve = {"kind": "resolve", "author": "user", "parent": "c1"}
    end = {"kind": "todo_end", "author": "agent", "todo": "p1", "outcome": "done"}
    assert lists(model.reading(FRAMED, [comment, promise, resolve])) == (
        owed,
        ["p1"],
        held,
    )
    assert lists(model.reading(FRAMED, [comment, promise, resolve, end])) == (
        items,
        [],
        [],
    )


def test_a_reply_after_a_thread_obligation_is_the_agents_turn_until_the_agent_replies():
    """A widget an agent sent into a thread is the agent's turn once the user writes
    after it, and the user's again once the agent answers, or once the agent ends the
    work its answer promised. A user turn the agent still owes from before the widget
    leaves the widget with the user."""
    asked = {
        "kind": "reply",
        "id": "obligation",
        "author": "agent",
        "parent": "t",
        "text": "Which route?",
        "markup": OPTIONS.format(attrs="choose").replace('id="', 'id="t-'),
    }
    opened = {"kind": "comment", "id": "t", "author": "user", "text": "Help me pick."}
    later = {"kind": "reply", "id": "r", "author": "user", "parent": "t", "text": "C?"}
    answered = {
        "kind": "reply",
        "author": "agent",
        "parent": "t",
        "responds": "r",
        "text": "No C, sorry.",
    }
    document = page("")
    assert lists(model.reading(document, [opened, asked])) == (
        ["widget:t-choice"],
        ["update:t"],
        [],
    )
    assert lists(model.reading(document, [opened, asked, later])) == (
        [],
        ["update:r"],
        ["widget:t-choice"],
    )
    assert lists(model.reading(document, [opened, asked, later, answered])) == (
        ["widget:t-choice"],
        [],
        [],
    )
    promised = {**answered, "id": "p", "todo": "Find out whether C exists"}
    assert lists(model.reading(document, [opened, asked, later, promised])) == (
        [],
        ["p"],
        ["widget:t-choice"],
    )
    end = {"kind": "todo_end", "author": "agent", "todo": "p", "outcome": "done"}
    assert lists(model.reading(document, [opened, asked, later, promised, end])) == (
        ["widget:t-choice"],
        [],
        [],
    )


def conditional_registry():
    """A value write can originate a request between document revisions."""
    registry = deepcopy(model.model_layer())
    registry["lf-conditional"] = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "phase": {"enum": ["closed", "open"]},
            "ready": {"type": "boolean"},
        },
        "required": ["id", "phase"],
        "additionalProperties": False,
        "x-content": "none",
        "x-state": {
            "phase": {"unit": "widget", "record": {"kind": "value", "attr": "phase"}},
            "answer": {
                "unit": "widget",
                "detail": {"type": "object", "additionalProperties": False},
            },
        },
        "x-awaits": {
            "when": {"phase": ["open"], "ready": [True]},
            "value": "answer",
            "answered": {"answer": {}},
        },
    }
    return registry


def test_conditional_request_retains_registration_between_value_actions():
    registry = conditional_registry()
    document = model.leaf_page(
        "Conditional",
        '<lf-conditional id="conditional" phase="closed" ready></lf-conditional>',
    )
    events: list[dict] = [
        {
            "kind": "action",
            "widget": "conditional",
            "action": "phase",
            "detail": {"value": phase},
        }
        for phase in ("open", "closed")
    ]
    assert page_obligations(model.reading(document, registry=registry))["all"] == []
    [opened] = page_obligations(model.reading(document, events[:1], registry=registry))[
        "user"
    ]
    assert opened["status"] == "open"
    closed = page_obligations(model.reading(document, events, registry=registry))
    [withdrawn] = closed["all"]
    assert (withdrawn["status"], withdrawn["answer"], closed["user"]) == (
        "withdrawn",
        None,
        [],
    )
    not_ready = document.replace(" ready", "")
    assert (
        page_obligations(
            model.reading({1: not_ready, 2: document}, events, registry=registry), 2
        )["all"]
        == []
    )
    [historical] = page_obligations(
        model.reading({1: document, 2: not_ready}, events, registry=registry), 2
    )["all"]
    assert historical["status"] == "withdrawn"
    report_registry = deepcopy(registry)
    report_registry["lf-conditional"]["x-state"]["phase"]["writer"] = "agent"
    reports = [{**event, "kind": "report", "author": "agent"} for event in events]
    [reported] = page_obligations(
        model.reading(document, reports, registry=report_registry)
    )["all"]
    assert reported["status"] == "withdrawn"
    completed = model.reading(
        document,
        [
            events[0],
            {
                "kind": "action",
                "widget": "conditional",
                "action": "answer",
                "detail": {},
            },
        ],
        registry=registry,
    )
    assert page_obligations(completed)["all"][0]["status"] == "answered"
    assert any(
        workflow["obligation"] is not None for workflow in completed["workflows"]
    )
    events.append({"kind": "undo", "undoes": "e1"})
    assert (
        page_obligations(model.reading(document, events, registry=registry))["all"]
        == []
    )


@pytest.mark.parametrize("writer", ["action", "report"])
def test_historical_conditional_registration_reuses_work_and_tracks_event_changes(
    monkeypatch, writer
):
    """Retries keep completed history work, while changed facts get a fresh fold.

    The same admitted event identities can occur in a regenerated log with changed
    payloads. Withdrawals and stamped transitions also change historical readings;
    later comments and a new active document do not.
    """
    registry = conditional_registry()
    if writer == "report":
        registry["lf-conditional"]["x-state"]["phase"]["writer"] = "agent"
    document = model.leaf_page(
        "Conditional",
        '<lf-conditional id="conditional" phase="closed" ready></lf-conditional>',
    )
    readings = {
        revision: SourceReading(SourceDocument(document), registry)
        for revision in (1, 2)
    }
    events: list[dict] = [
        {
            "kind": writer,
            "author": "agent" if writer == "report" else "user",
            "widget": "conditional",
            "action": "phase",
            "detail": {"value": phase},
        }
        for phase in ("open", "closed")
    ]
    historical = []
    collecting = False
    native = obligations_model.previously_requested

    def counted(*args, **kwargs):
        if collecting and args[3] == 1:
            historical.append(args[3])
        return native(*args, **kwargs)

    monkeypatch.setattr(obligations_model, "previously_requested", counted)

    def read(commands):
        """Admit a fresh log, then fold it against the same immutable readings."""
        nonlocal collecting
        door = model.ModelPage(
            documents={
                revision: reading.document for revision, reading in readings.items()
            },
            registry=registry,
        )
        log = []
        for seq, command in enumerate(commands, 1):
            stamped = {"id": f"e{seq}", "seq": seq, "ts": model.NOW, "author": "user"}
            if command["kind"] != "undo":
                stamped["revision"] = 1
            log.append(model.admitted_event(door, log, {**stamped, **command}))
        active = max(readings)
        page = page_reading(
            readings[active],
            log,
            active,
            revisions=readings,
            revision_reader=readings.__getitem__,
        )
        collecting = True
        try:
            return WorkReading(log, registry, page).document.items
        finally:
            collecting = False

    initial = read(events)
    assert [item["status"] for item in initial["all"]] == ["withdrawn"]
    assert len(historical) == 1
    assert read(events) == initial
    assert len(historical) == 1
    with_comment = [*events, {"kind": "comment", "text": "Keep investigating."}]
    assert read(with_comment) == initial
    readings[3] = SourceReading(SourceDocument(document), registry)
    assert read(with_comment) == initial
    assert len(historical) == 1

    changed = deepcopy(events)
    changed[0]["detail"]["value"] = "closed"
    assert read(changed)["all"] == []
    assert len(historical) == 2
    assert read(events) == initial
    assert len(historical) == 3

    if writer == "action":
        # Undo removes the gesture; a same-revision note preserves its registration.
        assert read([*events, {"kind": "undo", "undoes": "e1"}])["all"] == []
        assert len(historical) == 4
        assert (
            read(
                [
                    *events,
                    {
                        "kind": "note",
                        "author": "agent",
                        "version": 1,
                        "text": "Reconsidered.",
                        "restated": ["conditional"],
                    },
                ]
            )
            == initial
        )
        assert len(historical) == 5
    else:
        # A settled report still records that its prefix requested an answer.
        settled = [
            *events,
            {
                "kind": "note",
                "author": "agent",
                "version": 1,
                "text": "Absorbed.",
                "settles": [{"kind": "report", "id": "e1"}],
            },
        ]
        assert read(settled) == initial
        assert len(historical) == 4
        assert read(settled) == initial
        assert len(historical) == 4


def test_settled_request_repicks_keep_the_new_user_gesture_as_provenance():
    state = model.reading(
        {1: page(), 2: page("choose settled")},
        [
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["a"]},
            },
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["b"]},
                "revision": 2,
            },
        ],
    )
    [item] = page_obligations(state, 2)["all"]
    assert item["status"] == "answered"
    assert item["answer"]["value"] == ["b"]
    assert item["answer"]["event"]["id"] == "e2"


def test_todo_validation_does_not_rewrite_obligation_identity_and_refuses_bare_source():
    from interact_support import ModelPage

    from leaf.event_contracts import EventRefused, admitted_event

    document = page()
    door = ModelPage(
        documents={1: SourceDocument(document)}, registry=model.model_layer()
    )
    events: list[dict] = [
        admitted_event(
            door,
            [],
            {
                "kind": "comment",
                "id": "prompt",
                "seq": 1,
                "ts": model.NOW,
                "author": "agent",
                "revision": 1,
                "text": "Which path?",
                "obligation": True,
            },
        )
    ]
    command = {
        "kind": "todo_end",
        "id": "end",
        "author": "agent",
        "todo": "message:prompt",
        "outcome": "dropped",
    }
    admitted = admitted_event(door, events, command)
    assert command["todo"] == admitted["todo"] == "message:prompt"
    with pytest.raises(EventRefused) as refused:
        admitted_event(door, events, {**command, "todo": "prompt"})
    assert refused_on(refused.value).code == "unknown-todo"


@pytest.mark.parametrize("state", ["answered", "withdrawn"])
def test_user_work_can_stand_on_a_source_after_its_obligation_ends(state):
    documents = page() if state == "answered" else {1: page(), 2: page("")}
    events: list[dict] = (
        [
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["a"]},
            }
        ]
        if state == "answered"
        else []
    )
    events.append(
        {
            "kind": "todo",
            "author": "agent",
            "owner": "user",
            "title": "Check rollout numbers",
            "subject": {"kind": "widget", "id": "choice"},
        }
    )
    reading = model.reading(documents, events)
    revision = 1 if state == "answered" else 2
    assert page_obligations(reading, revision)["all"][0]["status"] == state
    assert reading["todos"][0]["title"] == "Check rollout numbers"


def test_repicking_a_withdrawn_request_records_provenance_without_reclosing_thread():
    registry = deepcopy(model.model_layer())
    registry["lf-options"]["properties"]["resolves"] = {"type": "string"}
    documents = {
        1: page('choose resolves="thread"'),
        2: page('choose settled resolves="thread"'),
    }
    events: list[dict] = [
        {"kind": "comment", "id": "thread", "text": "Which choice resolves this?"},
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["a"]},
        },
    ]
    closed = model.reading(documents, events, registry=registry)
    assert model.threads(closed)["thread"]["resolved"]
    events.extend(
        [
            {"kind": "unresolve", "parent": "thread"},
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["b"]},
                "revision": 2,
            },
        ]
    )
    reading = model.reading(documents, events, registry=registry)
    assert not model.threads(reading)["thread"]["resolved"]
    answer = page_obligations(reading, 2)["all"][0]["answer"]
    assert answer["value"] == ["b"]
    assert answer["event"]["id"] == "e4"


def _element(content: list, id: str) -> dict | None:
    for node in content:
        if isinstance(node, str):
            continue
        if node["attrs"].get("id") == id:
            return node
        if found := _element(node["content"], id):
            return found
    return None


@pytest.mark.parametrize(
    "case",
    json.loads((Path(__file__).parents[1].joinpath("name_cases.json")).read_text()),
    ids=lambda case: case["id"],
)
def test_an_element_is_named_as_the_browser_names_it(case):
    """An obligation's prompt is its element's name, read off the document by the rule
    the browser's `addressableName` reads off the live page."""
    document = SourceDocument(model.leaf_page("Names", case["markup"]))
    node = _element(document.authoring.content, "it")
    assert node is not None
    assert element_name(node, case.get("registry", {})) == case["name"]


EXHIBITS = json.loads(
    Path(__file__).parents[1].joinpath("exhibit_cases.json").read_text()
)


@pytest.mark.parametrize("case", EXHIBITS["cases"], ids=lambda case: case["id"])
def test_a_widget_is_quoted_where_the_browser_fences_it(case):
    """A widget strictly inside an x-exhibit is a mention, read off the holder chain by
    the rule the browser's `quoted` and its descriptors' `quoted` flag read off the
    page."""
    document = SourceDocument(model.leaf_page("Exhibits", case["markup"]))
    assert {
        rec["attrs"]["id"]: obligations_model.quoted_in(rec, EXHIBITS["registry"])
        for rec in document.lf_elements
    } == case["quoted"]


def test_data_record_obligations_follow_approval_undo_and_source_membership():
    """A review owes each current case, independent of ordering and sibling answers."""
    registry = model.model_layer("visual-review")
    source = json.loads(
        (
            Path(__file__).parents[2]
            / "examples/developer/visual-review-gallery.data.json"
        ).read_text()
    )["gallery-visual-run"]
    cases = source["cases"][:2]
    source["cases"] = cases
    document = model.leaf_page(
        "Review",
        '<lf-visual-review id="review" source="gallery-visual-run"></lf-visual-review>',
    )

    def read(events=(), chosen=None):
        value = {**source, "cases": cases if chosen is None else chosen}
        return model.reading(
            document,
            events,
            registry=registry,
            data={
                "version": "test",
                "sources": {
                    "gallery-visual-run": {
                        "contract": "visual-run",
                        "revision": "test",
                        "run": "test",
                        "updated": model.NOW,
                        "value": value,
                    }
                },
            },
        )

    before = page_obligations(read())["all"]
    assert [item["source"]["unit"] for item in before] == [case["id"] for case in cases]
    assert [item["prompt"] for item in before] == [
        {"text": case["title"], "target": "review"} for case in cases
    ]
    assert all(
        item["status"] == "open" and item["next_actor"] == "user" for item in before
    )
    approval = {
        "kind": "action",
        "id": "approve",
        "widget": "review",
        "action": "review",
        "detail": {"case": cases[0]["id"], "approved": True},
    }
    state = read([approval])
    [written] = model.projected(state, 1)["entries"]
    assert written["event"]["meaning"]["unit"] == cases[0]["id"]
    assert "answer" in written["event"]["meaning"]
    approved, untouched = page_obligations(state)["all"]
    assert approved["status"] == "answered"
    assert approved["answer"]["value"] == approval["detail"]
    assert untouched["status"] == "open"
    assert any(
        item["id"] == "update:approve" for item in state["views"]["1"]["obligations"]
    )
    unchecked = {
        **approval,
        "id": "uncheck",
        "detail": {**approval["detail"], "approved": False},
    }
    assert page_obligations(read([approval, unchecked]))["all"][0]["status"] == "open"
    assert (
        page_obligations(read([approval, {"kind": "undo", "undoes": "approve"}]))["all"]
        == before
    )
    reordered = page_obligations(read([approval], list(reversed(cases))))["all"]
    assert [item["id"] for item in reordered] == list(
        reversed([item["id"] for item in before])
    )
    assert [item["status"] for item in reordered] == ["open", "answered"]
    [remaining] = page_obligations(read([approval], cases[1:]))["all"]
    assert remaining == untouched


def test_data_record_feedback_hands_only_its_obligation_to_the_agent():
    registry = model.model_layer("visual-review")
    source = json.loads(
        (
            Path(__file__).parents[2]
            / "examples/developer/visual-review-gallery.data.json"
        ).read_text()
    )["gallery-visual-run"]
    cases = source["cases"][:2]
    source["cases"] = cases
    document = model.leaf_page(
        "Review",
        '<lf-visual-review id="review" source="gallery-visual-run"></lf-visual-review>',
    )
    data = {
        "version": "test",
        "sources": {
            "gallery-visual-run": {
                "contract": "visual-run",
                "revision": "test",
                "run": "test",
                "updated": model.NOW,
                "value": source,
            }
        },
    }
    comment = {
        "kind": "comment",
        "id": "feedback",
        "text": "Please improve this case",
        "anchor": {
            "section": "review",
            "datum": cases[0]["id"],
            "identity": cases[0]["id"],
            "source": "gallery-visual-run",
            "source_revision": "0" * 16,
        },
    }

    def read(events):
        return page_obligations(
            model.reading(document, events, registry=registry, data=data)
        )["all"]

    items = read([comment])
    assert [item["next_actor"] for item in items] == ["agent", "user"]
    assert all(item["status"] == "open" and item["answer"] is None for item in items)
    reply = {
        "kind": "reply",
        "author": "agent",
        "parent": "feedback",
        "responds": "feedback",
        "text": "Updated.",
    }
    assert [item["next_actor"] for item in read([comment, reply])] == ["user", "user"]


def test_data_record_requests_keep_conditional_registration_and_framed_arrival():
    registry = deepcopy(model.model_layer("visual-review"))
    entry = registry["lf-visual-review"]
    entry["properties"]["choose"] = {"type": "boolean"}
    entry["x-awaits"]["when"] = {"choose": [True]}
    source = json.loads(
        (
            Path(__file__).parents[2]
            / "examples/developer/visual-review-gallery.data.json"
        ).read_text()
    )["gallery-visual-run"]
    source["cases"] = source["cases"][:1]
    data = {
        "version": "test",
        "sources": {
            "gallery-visual-run": {
                "contract": "visual-run",
                "revision": "0" * 16,
                "run": "test",
                "updated": model.NOW,
                "value": source,
            }
        },
    }

    def document(attrs):
        return model.leaf_page(
            "Review",
            f'<lf-ask id="frame"><h2>Review this</h2><lf-visual-review id="review" source="gallery-visual-run" {attrs}></lf-visual-review></lf-ask>',
        )

    assert (
        page_obligations(model.reading(document(""), registry=registry, data=data))[
            "all"
        ]
        == []
    )
    [asked] = page_obligations(
        model.reading(document("choose"), registry=registry, data=data)
    )["all"]
    assert asked["prompt"]["target"] == "frame"
    state = model.reading(
        {1: document("choose"), 2: document("")}, registry=registry, data=data
    )
    [withdrawn] = page_obligations(state, 2)["all"]
    assert withdrawn["id"] == asked["id"]
    assert withdrawn["status"] == "withdrawn"


def test_record_obligations_validate_input_and_label_at_their_boundaries():
    from leaf.data_contracts import payload_error
    from leaf.registry.contract import RegistryError
    from leaf.registry.validation import validate_registry

    registry = deepcopy(model.model_layer("visual-review"))
    entry = registry["lf-visual-review"]
    entry["x-awaits"]["records"]["input"] = "missing"
    with pytest.raises(RegistryError, match=r"x-awaits\.records"):
        validate_registry(registry, "test")
    entry["x-awaits"]["records"]["input"] = "run"
    entry["x-awaits"]["records"]["label"] = "missing"
    source = json.loads(
        (
            Path(__file__).parents[2]
            / "examples/developer/visual-review-gallery.data.json"
        ).read_text()
    )["gallery-visual-run"]
    value_2 = payload_error("run", "visual-run", source, registry)
    assert value_2 is not None
    assert "obligation label 'missing'" in value_2
    entry["x-awaits"]["records"]["label"] = "title"
    assert payload_error("run", "visual-run", source, registry) is None
    entry["x-awaits"]["answered"]["review"]["detail"] = {"approved": "yes"}
    with pytest.raises(RegistryError, match="detail condition"):
        validate_registry(registry, "test")
