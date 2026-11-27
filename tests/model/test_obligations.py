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

from leaf.base import standing as standing_model
from leaf.log import obligations as obligations_model
from leaf.log.event_log import EventRefused
from leaf.log.projection import page_reading
from leaf.records.work_reading import WorkReading
from leaf.serving.served_state.browser import browser_state
from leaf.source import structure as structure_model
from leaf.source.passages import element_name
from leaf.source.reading import SourceReading
from leaf.source.structure import SourceDocument

OPTIONS = '<lf-options id="choice" {attrs}><lf-option id="a">A</lf-option><lf-option id="b">B</lf-option></lf-options>'


def page(attrs="", context=None):
    content = OPTIONS.format(attrs=attrs)
    if context:
        content = f'<lf-group id="{context}" label="Which route?"><h2 id="{context}-h">Which route?</h2>{content}</lf-group>'
    return model.leaf_page("Questions", content)


def page_obligations(state, revision=1):
    """The obligations the page's document makes in view `revision`."""
    view = state["views"][str(revision)]
    return obligations_model.collection(
        [
            item
            for item in view["obligations"]
            if item["thread"] is None
            and item["source"]["kind"] not in {"update", "todo"}
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
                "facts": {"answered": True},
            }
        ],
    )
    [item] = page_obligations(state, 2)["all"]
    assert (item["id"], item["source"]["id"]) == ("widget:choice", "choice")
    assert item["prompt"] == {
        "text": "Which route?",
        "target": "evidence",
    }
    assert item["answer"]["value"] == ["a"]
    assert standing_model.answered(item)


def test_a_decision_is_independent_and_survives_revision_until_restated():
    """A permission is an ordinary decision: it answers its own request, and a
    completion stamp does not ask again."""
    permit = (
        '<lf-options id="permit"><lf-option id="publish">Publish</lf-option>'
        '<lf-option id="hold">Keep it private</lf-option></lf-options>'
    )
    document = model.leaf_page("Permission", permit + OPTIONS.format(attrs=""))
    approved = {
        "kind": "action",
        "id": "approval",
        "widget": "permit",
        "action": "choose",
        "detail": {"value": ["publish"]},
        "facts": {"answered": True},
    }
    state = model.reading(document, [approved])
    items = {item["id"]: item for item in page_obligations(state)["all"]}
    assert standing_model.answered(items["widget:permit"])
    assert items["widget:permit"]["answer"]["event"]["id"] == "approval"
    assert items["widget:choice"]["state"] == "waiting"
    assert any(
        item["id"] == "update:approval"
        for item in state["views"]["1"]["queues"]["on_agent"]
    )

    # The stamp that records the pick in the markup settles the agent's update.
    revised = document.replace("Permission", "Permission and progress").replace(
        '<lf-option id="publish">', '<lf-option id="publish" selected>'
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
    assert standing_model.answered(items["widget:permit"])
    assert state["views"]["2"]["queues"]["on_agent"] == []

    state = model.reading(
        document,
        [
            approved,
            {"kind": "undo", "undoes": "approval", "facts": {"answered": False}},
        ],
    )
    items = {item["id"]: item for item in page_obligations(state)["all"]}
    assert items["widget:permit"]["state"] == "waiting"

    # Restating asks again, so the new version carries no pick.
    changed = document.replace('id="permit"', 'id="permit" restated')
    state = model.reading(
        {1: document, 2: changed}, [approved, {**stamp, "restated": ["permit"]}]
    )
    items = {item["id"]: item for item in page_obligations(state, 2)["all"]}
    assert items["widget:permit"]["state"] == "waiting"


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
            "text": "Choose the first route.\n\n"
            + OPTIONS.format(attrs="").replace('id="', 'id="root-'),
        },
        {
            "kind": "reply",
            "id": "later",
            "author": "agent",
            "parent": "thread",
            "text": "Choose the later route too.\n\n"
            + OPTIONS.format(attrs="").replace('id="', 'id="later-'),
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


def test_an_edit_moves_what_its_message_asks():
    """A message asks with the widgets its latest wording holds: an edit that takes a
    choice out withdraws its question, one that adds a choice asks it, and the panel
    draws each message's current HTML."""
    events: list[dict] = [
        {
            "kind": "comment",
            "id": "thread",
            "author": "agent",
            "text": "Choose a route.\n\n"
            + OPTIONS.format(attrs="").replace('id="', 'id="root-'),
        },
        {"kind": "comment", "id": "plain", "author": "agent", "text": "Which store?"},
        {
            "kind": "edit",
            "id": "withdraw",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "message": "thread",
            "text": "Withdrawn: the later thread asks instead.",
        },
        {
            "kind": "edit",
            "id": "ask",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "message": "plain",
            "text": "Which store?\n\n"
            + OPTIONS.format(attrs="").replace('id="', 'id="store-'),
        },
    ]
    state = model.reading(page(), events)
    asked = {item["id"]: item["message"] for item in served_obligations(state)["all"]}
    assert asked == {"widget:store-choice": "plain"}
    drawn = {
        message["id"]: message.get("html", False)
        for thread in model.threads(state).values()
        for message in thread["msgs"]
    }
    assert drawn == {"thread": False, "plain": True}


def test_partial_and_completed_empty_values_are_distinct_from_no_answer_and_undo_reopens():
    document = page("multiple")
    events: list[dict] = [
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": []},
            "facts": {"answered": False},
        }
    ]
    [initial] = page_obligations(model.reading(document))["all"]
    assert initial["answer"] is None
    [partial] = page_obligations(model.reading(document, events))["all"]
    assert (partial["state"], partial["answer"]["value"]) == ("waiting", [])
    events.append(
        {
            "kind": "action",
            "widget": "choice",
            "action": "answer",
            "detail": {"options": [], "picked": []},
            "facts": {"answered": True},
        }
    )
    [completed] = page_obligations(model.reading(document, events))["all"]
    assert standing_model.answered(completed)
    assert completed["answer"]["value"] == []
    assert completed["answer"]["event"]["id"] == "e2"
    events.append({"kind": "undo", "undoes": "e2", "facts": {"answered": False}})
    [reopened] = page_obligations(model.reading(document, events))["all"]
    assert (reopened["state"], reopened["answer"]["value"]) == ("waiting", [])


def test_a_widget_never_asked_is_absent_and_one_that_stops_asking_withdraws_its_request():
    assert page_obligations(model.reading(page("settled")))["all"] == []
    [withdrawn] = page_obligations(model.reading({1: page(), 2: page("settled")}), 2)[
        "all"
    ]
    assert (
        withdrawn["state"],
        withdrawn["outcome"],
        withdrawn["answer"],
        withdrawn["next_actor"],
    ) == ("done", "dropped", None, None)
    assert (
        page_obligations(model.reading({1: page(), 2: page("settled restated")}), 2)[
            "all"
        ]
        == []
    )


def test_a_widget_an_earlier_version_showed_in_an_exhibit_never_asked():
    """An exhibit shows the widgets in it rather than asking with them, in a page's
    history as in its current version, so a widget an earlier version showed leaves
    no finished obligation once a later one moves it out and settles it."""
    shown = model.leaf_page(
        "Questions",
        f'<lf-sample id="kit" label="Kit">{OPTIONS.format(attrs="")}</lf-sample>',
    )
    assert (
        page_obligations(model.reading({1: shown, 2: page("settled")}), 2)["all"] == []
    )


def test_pinned_document_uses_unrequested_intermediate_history_for_registration():
    registry = model.model_layer()
    readings = {
        index: SourceReading(
            SourceDocument(page("" if index == 2 else "settled")), registry
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
        assert (item["id"], item["state"], item["outcome"]) == (
            "widget:choice",
            "done",
            "dropped",
        )


def test_a_pinned_view_reads_its_threads_under_its_own_registry():
    """A revision captured its thread widgets under its own registry, so a view
    pinned to it classifies their decisions there. A decision whose operation that
    registry defines otherwise is none in that view: the obligation it answers stays open
    and the thread the user's, while the active view reads it answered and the
    thread waiting on the agent to pick it up."""

    def registry(attr):
        layer = deepcopy(model.model_layer())
        layer["lf-value-ask"] = {
            "attributes": {
                "properties": {
                    "active": {"type": "boolean"},
                    "value": {"type": "boolean"},
                    "chosen": {"type": "boolean"},
                },
                "required": ["id"],
            },
            "content": "none",
            "awaits": {
                "when": {"active": [True]},
                "value": "set",
            },
            "facts": {"answered": {"type": "boolean"}},
            "verbs": {
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
                "text": "Ship it?\n\n"
                + '<lf-value-ask id="typed" active></lf-value-ask>',
            },
            {
                "kind": "action",
                "widget": "typed",
                "action": "set",
                "detail": {"value": True},
                "facts": {"answered": True},
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
            (item["id"], item["state"], item["outcome"]),
            thread["attention"],
            [item["id"] for item in view["queues"]["on_user"]],
        )

    assert read(2) == (
        [events[1]["id"]],
        ("widget:typed", "done", "done"),
        f"update:{events[1]['id']}",
        [],
    )
    assert read(1) == (
        [],
        ("widget:typed", "waiting", None),
        "widget:typed",
        ["widget:typed"],
    )


@pytest.mark.parametrize("value", [False, 0])
def test_false_and_zero_are_typed_answers(value):
    registry = deepcopy(model.model_layer())
    registry["lf-value-ask"] = {
        "attributes": {
            "properties": {
                "active": {"type": "boolean"},
                "value": {"type": ["boolean", "integer"]},
            },
            "required": ["id"],
        },
        "content": "none",
        "awaits": {
            "when": {"active": [True]},
            "value": "set",
        },
        "facts": {"answered": {"type": "boolean"}},
        "verbs": {
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
                    "facts": {"answered": True},
                }
            ],
            registry=registry,
        )
    )["all"]
    assert standing_model.answered(item)
    assert item["answer"]["value"] is value


def test_changed_value_does_not_reuse_an_earlier_completion_event():
    """A pick changed after Done keeps the question answered, as the widget says, and
    the answer's gesture is the pick that changed it, never the Done before it."""
    events: list[dict] = [
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["a"]},
            "facts": {"answered": False},
        },
        {
            "kind": "action",
            "widget": "choice",
            "action": "answer",
            "detail": {"options": [], "picked": []},
            "facts": {"answered": True},
        },
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["b"]},
            "facts": {"answered": True},
        },
    ]
    state = model.reading(page("multiple"), events)
    [item] = page_obligations(state)["all"]
    assert item["answer"]["value"] == ["b"]
    assert item["answer"]["event"]["id"] == "e3"


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
    [item] = served_obligations(model.reading(page("settled"), answered_in_words()))[
        "all"
    ]
    assert (item["id"], item["state"], item["next_actor"]) == (
        "message:asking",
        "waiting",
        "user",
    )
    assert item["prompt"]["text"] == "Weekly or daily?"
    state = model.reading(
        page("settled"),
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
    assert standing_model.answered(item)
    assert item["next_actor"] is None
    assert item["answer"]["value"] == {"text": "Daily"}
    assert item["answer"]["event"]["id"] == "r"
    assert lists(state) == ([], ["update:r"], [])


def reopened(*later):
    """The question above answered by a reply that asks back, the agent's reply
    reopening it, then `later`."""
    return answered_in_words(
        {
            "kind": "reply",
            "id": "r",
            "author": "user",
            "parent": "t",
            "text": "What's the difference?",
        },
        {
            "kind": "reply",
            "id": "again",
            "author": "agent",
            "parent": "r",
            "responds": "r",
            "text": "Daily costs more. Weekly or daily?",
            "obligation": ["message:asking"],
        },
        *later,
    )


def test_a_reopened_question_keeps_its_id_and_words_and_stands_on_the_reply():
    """A question the agent reopens waits on the user again under the id and words it
    had, so a plan step naming it keeps its title, and stands on the reopening reply:
    what they said before it no longer answers it, and their next message does."""
    state = model.reading(page("settled"), reopened())
    [item] = served_obligations(state)["all"]
    assert (item["id"], item["state"], item["next_actor"]) == (
        "message:asking",
        "waiting",
        "user",
    )
    assert item["message"] == "again"
    assert item["prompt"]["text"] == "Weekly or daily?"
    assert item["answer"] is None
    assert lists(state)[0] == ["message:asking"]

    state = model.reading(
        page("settled"),
        reopened(
            {
                "kind": "reply",
                "id": "settled",
                "author": "user",
                "parent": "again",
                "text": "Weekly",
            }
        ),
    )
    [item] = served_obligations(state)["all"]
    assert item["id"] == "message:asking"
    assert standing_model.answered(item)
    assert item["answer"]["value"] == {"text": "Weekly"}


def test_a_question_asked_again_after_a_resolve_stands_until_the_next():
    """A resolve ends a question asked before it: the user's later message, which
    reopens the thread, neither answers nor restores it, while asking it again in a
    reply stands until the thread is resolved again."""
    resolved = {"kind": "resolve", "id": "first", "author": "agent", "parent": "t"}
    later = {"kind": "reply", "id": "later", "author": "user", "parent": "t"}
    again = {
        "kind": "reply",
        "id": "again",
        "author": "agent",
        "parent": "t",
        "text": "Weekly or daily, after all?",
        "obligation": ["message:asking"],
    }
    for events, actor in (
        ((resolved,), None),
        ((resolved, {**later, "text": "Fix the heading's typo too."}), None),
        ((resolved, again), "user"),
        ((resolved, again, {**resolved, "id": "second"}), None),
    ):
        state = model.reading(page("settled"), answered_in_words(*events))
        [item] = served_obligations(state)["all"]
        assert (item["state"], item["next_actor"]) == ("waiting", actor)


def test_a_served_record_says_whether_its_own_answer_stands():
    """Every reader takes `answered` from the record: the user's words answer a
    question, and a resolve that ends it is no answer of theirs."""

    def served(*later) -> dict:
        state = model.reading(page("settled"), answered_in_words(*later))
        [item] = served_obligations(state)["all"]
        return item

    words = {
        "kind": "reply",
        "id": "said",
        "author": "user",
        "parent": "asking",
        "text": "Weekly",
    }
    resolved = {"kind": "resolve", "id": "close", "author": "agent", "parent": "t"}
    assert served()["answered"] is False
    assert served(words)["answered"] is True
    closed = served(resolved)
    assert (closed["next_actor"], closed["answered"]) == (None, False)


def test_a_group_around_a_decision_widget_stays_one_obligation():
    [item] = page_obligations(model.reading(page(context="frame"), []))["all"]
    assert (item["id"], item["prompt"]["target"]) == ("widget:choice", "frame")


def lists(state) -> tuple[list, list, list]:
    """On Me and On <agent> as served, and the open widget obligations whose next move
    is the agent's, which On <agent> lists through the update that handed them over."""
    queues = state["views"]["1"]["queues"]
    items = state["views"]["1"]["obligations"]
    return (
        sorted(item["id"] for item in queues["on_user"]),
        sorted(item["id"] for item in queues["on_agent"]),
        sorted(
            item["id"]
            for item in items
            if item["state"] == "waiting"
            and item["next_actor"] == "agent"
            and item["source"]["kind"] not in {"update", "todo"}
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
        + OPTIONS.format(attrs="")
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
        "facts": {"answered": True},
    }
    assert rows(model.reading(document, [*events, chosen])) == [
        ("message:r1", ["message:r2"]),
        ("message:r3", []),
    ]


FRAMED = model.leaf_page(
    "Questions",
    '<p id="intro">Context.</p><section id="case">'
    '<lf-group id="frame" label="Two routes"><h2 id="head">Two routes</h2><div id="first">'
    + OPTIONS.format(attrs="")
    + "</div>"
    + OPTIONS.format(attrs="").replace('id="', 'id="y-')
    + OPTIONS.format(attrs="settled").replace('id="', 'id="shown-')
    + "</lf-group></section>",
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
    ids=["option", "name", "display-only", "part", "section", "elsewhere"],
)
def test_a_comment_on_an_obligation_is_the_agents_turn_until_the_agent_replies(
    anchor, held
):
    """The user's comment about an open obligation hands it to the agent without answering
    it: the obligation leaves On Me while the comment's answer stands on On <agent>, and comes
    back once the agent replies, or once the agent ends the work its reply promised. The
    user's resolve leaves both standing: that is how a decision the user put off until an
    answer or other work lands stays off their list. A comment on one obligation, or on
    the part of the group holding it, leaves its sibling in the group with the user; one
    on the heading naming the group, on a widget there that asks nothing or on the
    section holding the group is about both, and one elsewhere about none."""
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
    resolve = {"kind": "resolve", "author": "user", "parent": "c1"}
    assert lists(model.reading(FRAMED, [comment, resolve])) == (
        owed,
        ["update:c1"],
        held,
    )
    reply = {
        "kind": "reply",
        "author": "agent",
        "parent": "c1",
        "responds": "c1",
        "text": "It means the first route.",
    }
    assert lists(model.reading(FRAMED, [comment, reply])) == (items, [], [])
    promise = {**reply, "id": "p1", "todo": "Ask again once the other work lands"}
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
        "text": "Which route?\n\n" + OPTIONS.format(attrs="").replace('id="', 'id="t-'),
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
    document = page("settled")
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
        "attributes": {
            "properties": {
                "phase": {"enum": ["closed", "open"]},
                "ready": {"type": "boolean"},
            },
            "required": ["id", "phase"],
        },
        "content": "none",
        "verbs": {
            "phase": {
                "unit": "widget",
                "record": {"kind": "value", "attr": "phase"},
            },
            "answer": {
                "unit": "widget",
                "detail": {"type": "object", "additionalProperties": False},
            },
        },
        "awaits": {
            "when": {"phase": ["open"], "ready": [True]},
            "value": "answer",
        },
        "facts": {"answered": {"type": "boolean"}},
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
            # Moving the phase answers nothing; only `answer` does.
            "facts": {"answered": False},
        }
        for phase in ("open", "closed")
    ]
    assert page_obligations(model.reading(document, registry=registry))["all"] == []
    [opened] = page_obligations(model.reading(document, events[:1], registry=registry))[
        "user"
    ]
    assert opened["state"] == "waiting"
    closed = page_obligations(model.reading(document, events, registry=registry))
    [withdrawn] = closed["all"]
    assert (withdrawn["outcome"], withdrawn["answer"], closed["user"]) == (
        "dropped",
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
    assert historical["outcome"] == "dropped"
    report_registry = deepcopy(registry)
    report_registry["lf-conditional"]["verbs"]["phase"]["writer"] = "agent"
    reports = [
        {**{k: v for k, v in event.items() if k != "facts"}, "kind": "report"}
        | {"author": "agent"}
        for event in events
    ]
    [reported] = page_obligations(
        model.reading(document, reports, registry=report_registry)
    )["all"]
    assert reported["outcome"] == "dropped"
    completed = model.reading(
        document,
        [
            events[0],
            {
                "kind": "action",
                "widget": "conditional",
                "action": "answer",
                "detail": {},
                "facts": {"answered": True},
            },
        ],
        registry=registry,
    )
    assert standing_model.answered(page_obligations(completed)["all"][0])
    assert any(
        workflow["obligation"] is not None for workflow in completed["workflows"]
    )
    # A write to a widget an interactive exhibit shows is a demonstration, which
    # asks nothing then or once a later version moves the widget out.
    demonstrated = model.leaf_page(
        "Conditional",
        '<lf-sample id="demo" label="Demo" interactive>'
        '<lf-conditional id="conditional" phase="closed" ready></lf-conditional>'
        "</lf-sample>",
    )
    assert (
        page_obligations(
            model.reading({1: demonstrated, 2: not_ready}, events, registry=registry),
            2,
        )["all"]
        == []
    )
    events.append({"kind": "undo", "undoes": "e1", "facts": {"answered": False}})
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
        registry["lf-conditional"]["verbs"]["phase"]["writer"] = "agent"
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
            **({"facts": {"answered": False}} if writer == "action" else {}),
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
    assert [item["outcome"] for item in initial["all"]] == ["dropped"]
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
        assert (
            read(
                [
                    *events,
                    {"kind": "undo", "undoes": "e1", "facts": {"answered": False}},
                ]
            )["all"]
            == []
        )
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
        {1: page(), 2: page("settled")},
        [
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["a"]},
                "facts": {"answered": True},
            },
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["b"]},
                "revision": 2,
                "facts": {"answered": True},
            },
        ],
    )
    [item] = page_obligations(state, 2)["all"]
    assert standing_model.answered(item)
    assert item["answer"]["value"] == ["b"]
    assert item["answer"]["event"]["id"] == "e2"


def test_a_todo_end_names_only_a_todo():
    """`todo_end` refuses a question's obligation id with how the question ends, and
    an id that names neither a to-do nor an obligation as unknown."""
    from interact_support import ModelPage

    from leaf.records.event_contracts import EventRefused, admitted_event

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
        "outcome": "done",
    }
    for todo, code in (
        ("message:prompt", "obligation-end"),
        ("prompt", "unknown-todo"),
    ):
        with pytest.raises(EventRefused) as refused:
            admitted_event(door, events, {**command, "todo": todo})
        assert refused_on(refused.value).code == code


def test_repicking_a_withdrawn_request_records_provenance_without_reclosing_thread():
    registry = deepcopy(model.model_layer())
    registry["lf-options"]["attributes"]["properties"]["resolves"] = {"type": "string"}
    documents = {
        1: page('resolves="thread"'),
        2: page('settled resolves="thread"'),
    }
    events: list[dict] = [
        {"kind": "comment", "id": "thread", "text": "Which choice resolves this?"},
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["a"]},
            "facts": {"answered": True},
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
                "facts": {"answered": True},
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
    """A widget strictly inside an `exhibit` is a mention, read off the holder chain by
    the rule the browser's descriptors' `quoted` flag reads off the page."""
    document = SourceDocument(model.leaf_page("Exhibits", case["markup"]))
    assert {
        rec["attrs"]["id"]: structure_model.quoted_in(rec, EXHIBITS["registry"])
        for rec in document.lf_elements
    } == case["quoted"]


def signoff_registry():
    """A checklist the user decides one step at a time, whose module says the question
    is answered once every step holds a decision."""
    registry = deepcopy(model.model_layer())
    registry["lf-signoff"] = {
        "attributes": {"required": ["id"]},
        "content": "members",
        "verbs": {
            "decide": {
                "unit": "step",
                "detail": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "string"},
                        "outcome": {"enum": ["signed", "returned"]},
                    },
                    "required": ["step", "outcome"],
                    "additionalProperties": False,
                },
            }
        },
        "awaits": {"value": "decide"},
        "facts": {"answered": {"type": "boolean"}},
    }
    registry["lf-signoff-step"] = {
        "attributes": {"required": ["id"]},
        "content": "markup",
        "owners": ["lf-signoff"],
    }
    return registry


def signoff(*steps: str, restated: tuple[str, ...] = ()) -> str:
    return model.leaf_page(
        "Release",
        '<lf-signoff id="release">'
        + "".join(
            f'<lf-signoff-step id="{step}"{" restated" if step in restated else ""}>'
            f"{step}</lf-signoff-step>"
            for step in steps
        )
        + "</lf-signoff>",
    )


def decided(step: str, answered: bool, outcome: str = "signed") -> dict:
    return {
        "kind": "action",
        "widget": "release",
        "action": "decide",
        "detail": {"step": step, "outcome": outcome},
        "facts": {"answered": answered},
    }


def test_the_widgets_word_on_each_gesture_answers_or_reopens_its_question():
    """The checklist says on each decision whether its question is answered, and the
    server reads that word rather than deciding again: the last step's decision
    answers it, undoing a decision reopens it as the undo says, and a version that
    restates a decided step asks again, since the decision it retracts carried the
    word and no gesture says otherwise."""
    registry = signoff_registry()
    two = signoff("notes", "rollback")

    def standing(documents, events, revision=1):
        [item] = page_obligations(
            model.reading(documents, events, registry=registry), revision
        )["all"]
        return standing_model.answered(item)

    assert not standing(two, [decided("notes", False)])
    both = [decided("notes", False), decided("rollback", True)]
    assert standing(two, both)
    assert not standing(
        two, [*both, {"kind": "undo", "undoes": "e2", "facts": {"answered": False}}]
    )
    # An undo that leaves an answer standing says so, and keeps it answered.
    third = [*both, decided("notes", True, "returned")]
    assert standing(
        two, [*third, {"kind": "undo", "undoes": "e3", "facts": {"answered": True}}]
    )
    restated = {1: two, 2: signoff("notes", "rollback", restated=("rollback",))}
    stamp = {
        "kind": "note",
        "author": "agent",
        "version": 1,
        "revision": 2,
        "text": "Rewrote the rollback step.",
        "restated": ["rollback"],
    }
    assert not standing(restated, [*both, stamp], 2)


def test_restating_a_step_decided_before_the_last_asks_again():
    """The newest gesture's word said the checklist was answered, but a version that
    restates a step decided earlier withdraws that step's decision, so the checklist
    asks again until a later gesture says otherwise. Which member the restatement
    names doesn't matter, only that it withdrew one of the widget's decisions."""
    registry = signoff_registry()
    both = [decided("rollback", False), decided("notes", True)]
    restated = {
        1: signoff("notes", "rollback"),
        2: signoff("notes", "rollback", restated=("rollback",)),
    }
    stamp = {
        "kind": "note",
        "author": "agent",
        "version": 1,
        "revision": 2,
        "text": "Rewrote the rollback step.",
        "restated": ["rollback"],
    }

    def standing(events):
        [item] = page_obligations(
            model.reading(restated, events, registry=registry), 2
        )["all"]
        return standing_model.answered(item)

    assert standing(both)
    assert not standing([*both, stamp])
    assert standing([*both, stamp, {**decided("rollback", True), "revision": 2}])


def test_a_view_of_an_earlier_version_reads_no_later_restatement():
    """A note a later version wrote retracts nothing a view of an earlier one holds,
    as the fold reads it: picks on revisions 1 and 2 and a revision-3 note restating
    the group leave revision 1's view answered, and revision 3's asking again."""
    restated = model.leaf_page(
        "Questions",
        '<lf-options id="choice" restated><lf-option id="a">A</lf-option>'
        '<lf-option id="b">B</lf-option></lf-options>',
    )

    def pick(value, revision):
        return {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": [value]},
            "revision": revision,
            "facts": {"answered": True},
        }

    def note(version, revision, **restating):
        return {
            "kind": "note",
            "author": "agent",
            "version": version,
            "revision": revision,
            "text": "A version.",
            **restating,
        }

    events = [
        pick("a", 1),
        note(1, 2),
        pick("b", 2),
        note(2, 3, restated=["choice"]),
    ]
    documents = {1: page(), 2: page(), 3: restated}
    for revision, answered in ((1, True), (3, False)):
        [item] = page_obligations(
            model.reading(documents, events, view_revision=revision), revision
        )["all"]
        assert standing_model.answered(item) is answered, revision


def test_markup_alone_answers_no_question():
    """A pick the version writes into the markup, with no gesture to carry the
    widget's word, leaves the question asking."""
    [item] = page_obligations(
        model.reading(
            model.leaf_page(
                "Questions",
                '<lf-options id="choice"><lf-option id="a" selected>A</lf-option>'
                '<lf-option id="b">B</lf-option></lf-options>',
            )
        )
    )["all"]
    assert not standing_model.answered(item)
    assert item["next_actor"] == "user"


def checklist(*options: str, restated: tuple[str, ...] = ()) -> str:
    """A page whose question is a checklist, an `lf-options multiple` of `options`."""
    return model.leaf_page(
        "Questions",
        '<lf-options id="choice" multiple>'
        + "".join(
            f'<lf-option id="{option}"{" restated" if option in restated else ""}>'
            f"{option.upper()}</lf-option>"
            for option in options
        )
        + "</lf-options>",
    )


def chose(*picked: str) -> dict:
    return {
        "kind": "action",
        "widget": "choice",
        "action": "choose",
        "detail": {"value": list(picked)},
        "facts": {"answered": False},
    }


def done(options: list[str], picked: list[str]) -> dict:
    """The checklist's Done, which names the set it says is whole."""
    return {
        "kind": "action",
        "widget": "choice",
        "action": "answer",
        "detail": {"options": options, "picked": picked},
        "facts": {"answered": True},
    }


def told(answered: bool, revision: int = 2) -> dict:
    """A tab's word on the checklist, worked out again as a version reached it."""
    return {
        "kind": "facts",
        "widget": "choice",
        "revision": revision,
        "facts": {"answered": answered},
    }


def test_a_checklist_given_a_step_asks_again_once_a_tab_says_so_with_its_picks_kept():
    """A version that gives a checklist a step leaves its Done in force, so the page
    keeps the Done's word until a tab showing the version works the checklist out
    again. Done answered the steps it was pressed on, so the tab says the question is
    open, and On Me asks it again with the steps the user decided still picked."""
    documents = {1: checklist("a", "b"), 2: checklist("a", "b", "c")}
    pressed = [chose("a"), done(["a", "b"], ["a"])]

    def read(*later):
        state = model.reading(documents, [*pressed, *later])
        [item] = page_obligations(state, 2)["all"]
        return item, state["views"]["2"]["facts"].get("choice")

    item, kept = read()
    assert (standing_model.answered(item), kept) == (True, {"answered": True})
    item, kept = read(told(False))
    assert (item["state"], item["next_actor"], kept) == (
        "waiting",
        "user",
        {"answered": False},
    )
    assert item["answer"]["value"] == ["a"]


def test_tabs_that_work_out_the_same_word_leave_one_event():
    """Every tab showing the version works the checklist out after the same reading
    and says what differs from what the page keeps. The page admits the first word and
    refuses the same word again, which changes nothing, so two tabs agree in one event.
    A word on a widget the page doesn't hold is refused too, and so is one worked out
    on a version older than the newest."""
    documents = {1: checklist("a", "b"), 2: checklist("a", "b", "c")}
    said = [chose("a"), done(["a", "b"], ["a"]), told(False)]
    with pytest.raises(EventRefused) as again:
        model.reading(documents, [*said, told(False)])
    assert refused_on(again.value).code == "unchanged-facts"
    with pytest.raises(EventRefused) as stranger:
        model.reading(documents, [*said, {**told(True), "widget": "nobody"}])
    assert refused_on(stranger.value).code == "unknown-sender"
    with pytest.raises(EventRefused) as older:
        model.reading(documents, [*said, told(True, revision=1)])
    assert refused_on(older.value).code == "stale-facts"


def test_restating_a_picked_step_after_done_asks_again_with_the_other_picks_kept():
    """A version that restates a step the user picked takes back the picks that named
    it and changes the checklist's state with no word from it, so the word its Done
    said lapses and the question asks again, the pick before it standing. The
    checklist says the same when a tab works it out (lf-options' `answered`), so no
    tab's word answers it again."""
    documents = {1: checklist("a", "b"), 2: checklist("a", "b", restated=("b",))}
    stamp = {
        "kind": "note",
        "author": "agent",
        "version": 1,
        "revision": 2,
        "text": "Rewrote step b.",
        "restated": ["b"],
    }
    state = model.reading(
        documents, [chose("a"), chose("a", "b"), done(["a", "b"], ["a", "b"]), stamp]
    )
    [item] = page_obligations(state, 2)["all"]
    assert (item["state"], item["next_actor"]) == ("waiting", "user")
    assert item["answer"]["value"] == ["a"]
    assert "choice" not in state["views"]["2"]["facts"]
