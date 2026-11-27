"""Folds whose whole subject is the reading, not what a widget draws with it.

Each test here states one document and one log and asks what the browser would
be handed. `model_folds` owns the arrangement; `tests/AGENTS.md`'s rule that an
assertion belongs at the boundary that owns it is why these are not in
`test_render_*.py`: no renderer decides any of them, so serving a page and
opening Chromium would put a browser between the cause and the claim without
putting one in the claim.
"""

from copy import deepcopy

import model_folds as model
import pytest
from interact_support import page_packages, served_obligations, served_todos

from leaf.base import standing as standing_model

HUB = model.leaf_page(
    "command hub",
    """<h1 id="h">Atlas</h1>
<lf-test-plan id="atlas" label="Replace the parser">
  <lf-test-task id="goal-parser" status="active" talk><strong>Replace the XML parser</strong></lf-test-task>
</lf-test-plan>""",
)
# A request held against a goal and the agent's answer to it. `holds` names the
# work the thread is about, which is what a command page reads it back through.
HELD_REQUEST = (
    {
        "kind": "comment",
        "text": "Finish the hunk, then park.",
        "anchor": {"section": "goal-parser"},
        "holds": "goal-parser",
    },
    {"kind": "reply", "author": "agent", "parent": "e1", "text": "The hunk is ready."},
)


def test_summaries_replace_overlaps_and_stand_through_the_users_rewrite():
    """A summary replaces the one it overlaps whole, and the user's rewrite of a
    message it folds leaves it standing, for the agent to judge whether it still
    holds."""
    identity = {"author": "agent", "agent": "Agent", "session": "session-1"}
    messages = (
        {"kind": "comment", "text": "one"},
        {"kind": "reply", "parent": "e1", "text": "two"},
        {"kind": "reply", **identity, "parent": "e2", "text": "three"},
        {"kind": "reply", "parent": "e3", "text": "four"},
    )
    state = model.reading(
        HUB,
        (
            *messages,
            {
                "kind": "summary",
                **identity,
                "thread": "e1",
                "from": "e1",
                "through": "e2",
                "text": "First exchange.",
            },
            {
                "kind": "summary",
                **identity,
                "thread": "e1",
                "from": "e1",
                "through": "e3",
                "text": "Extended exchange.",
            },
            {"kind": "edit", "author": "user", "message": "e2", "text": "two, revised"},
        ),
    )

    thread = model.threads(state)["e1"]
    assert [summary["text"] for summary in thread["summaries"]] == [
        "Extended exchange."
    ]
    assert [message["text"] for message in thread["msgs"]] == [
        "one",
        "two, revised",
        "three",
        "four",
    ]


AGENT = {"author": "agent", "agent": "Agent", "session": "session-1"}


def test_a_message_taken_back_keeps_no_rewrite_of_it():
    """A message the user takes back while an answer stands on it keeps its place,
    saying the words it was sent with, and a rewrite made before the withdrawal, as a
    second tab may have made, no longer stands or asks for an answer."""
    log = (
        {"kind": "comment", "text": "Ship it?"},
        {"kind": "reply", **AGENT, "parent": "e1", "responds": "e1", "text": "Which?"},
        {"kind": "reply", "parent": "e2", "text": "The beta."},
        {"kind": "reply", **AGENT, "parent": "e3", "responds": "e3", "text": "OK."},
        {"kind": "edit", "message": "e3", "text": "The release."},
        {"kind": "undo", "undoes": "e3"},
    )
    state = model.reading(HUB, log)
    thread = model.threads(state)["e1"]
    taken = next(message for message in thread["msgs"] if message["id"] == "e3")
    assert (taken["text"], taken["withdrawn"]["was"]) == ("", "The beta.")
    assert "edited" not in taken
    assert thread["revisions"] == []
    assert state["workflows"] == []


@pytest.mark.parametrize(
    "log",
    [
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e2",
                    "responds": "e2",
                    "text": ".",
                },
                {"kind": "undo", "undoes": "e2"},
            ),
            id="the answered message",
        ),
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e1",
                    "responds": "e2",
                    "text": ".",
                },
                {"kind": "undo", "undoes": "e2"},
            ),
            id="the answered message, which nothing stands on",
        ),
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {"kind": "edit", "message": "e2", "text": "And the tests?"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e2",
                    "responds": "e3",
                    "text": ".",
                },
                {"kind": "undo", "undoes": "e2"},
            ),
            id="the message whose rewrite was answered",
        ),
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {"kind": "edit", "message": "e2", "text": "And the tests?"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e2",
                    "responds": "e3",
                    "text": ".",
                },
                {"kind": "undo", "undoes": "e3"},
            ),
            id="the answered rewrite",
        ),
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {"kind": "reply", "parent": "e2", "emoji": "👍"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e3",
                    "responds": "e3",
                    "text": ".",
                },
                {"kind": "undo", "undoes": "e3"},
            ),
            id="a reaction the answer stands on",
        ),
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {"kind": "reply", "parent": "e2", "text": "And the tests?"},
                {"kind": "undo", "undoes": "e3"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e2",
                    "responds": "e2",
                    "text": ".",
                },
            ),
            id="a turn taken back before the answer",
        ),
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {"kind": "edit", "message": "e2", "text": "And the tests?"},
                {"kind": "undo", "undoes": "e3"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e2",
                    "responds": "e2",
                    "text": ".",
                },
            ),
            id="a rewrite taken back before the answer",
        ),
        pytest.param(
            (
                {"kind": "reply", "parent": "e1", "text": "And the docs?"},
                {"kind": "reply", "parent": "e2", "text": "And the tests?"},
                {"kind": "edit", "message": "e3", "text": "And the build?"},
                {"kind": "undo", "undoes": "e3"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e2",
                    "responds": "e2",
                    "text": ".",
                },
            ),
            id="a rewritten turn taken back before the answer",
        ),
        pytest.param(
            (
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e1",
                    "responds": "e1",
                    "failure": "turn_failed",
                    "text": "No answer is coming.",
                },
                {"kind": "reply", "parent": "e2", "text": "Try again?"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e3",
                    "responds": "e3",
                    "text": ".",
                },
                {"kind": "undo", "undoes": "e3"},
            ),
            id="an answered retry of a failed answer",
        ),
    ],
)
def test_taking_back_a_turn_leaves_what_an_answer_settled_settled(log):
    """The agent's answer to the user's newest turn settles every turn before it, and
    taking back that turn, its rewrite, or a reaction the answer stands on leaves
    them settled, as a failed answer the settled turn came after stays answered. A
    turn taken back before the answer is no part of what it settles."""
    state = model.reading(HUB, ({"kind": "comment", "text": "Ship it?"}, *log))
    assert state["workflows"] == []


def test_taking_back_an_unanswered_retry_hands_the_failed_answer_back():
    """A retry the user takes back before any answer leaves the failed answer it
    followed theirs to act on again."""
    log = (
        {"kind": "comment", "text": "Ship it?"},
        {
            "kind": "reply",
            **AGENT,
            "parent": "e1",
            "responds": "e1",
            "failure": "turn_failed",
            "text": "No answer is coming.",
        },
        {"kind": "reply", "parent": "e2", "text": "Try again?"},
        {"kind": "undo", "undoes": "e3"},
    )
    [failed] = model.reading(HUB, log)["workflows"]
    assert failed["input"] == "e1"


def test_a_reply_taken_back_reopens_nothing():
    """A reply the user takes back keeps its place where something stands on it,
    and nothing else: the thread it had reopened is resolved again."""
    log = (
        {"kind": "comment", "text": "Ship it?"},
        {"kind": "reply", **AGENT, "parent": "e1", "responds": "e1", "text": "Done."},
        {"kind": "resolve", "parent": "e1"},
        {"kind": "reply", "parent": "e2", "text": "One more thing."},
        {
            "kind": "reply",
            **AGENT,
            "parent": "e4",
            "text": "Noted.",
            "unannounced": True,
        },
        {"kind": "undo", "undoes": "e4"},
    )
    state = model.reading(HUB, log)
    thread = model.threads(state)["e1"]
    assert [message["id"] for message in thread["msgs"]] == ["e1", "e2", "e4", "e5"]
    assert thread["resolved"]["id"] == "e3"
    assert state["workflows"] == []


def test_summary_leaves_messages_after_its_range_visible():
    identity = {"author": "agent", "agent": "Agent", "session": "session-1"}
    state = model.reading(
        HUB,
        (
            {"kind": "comment", "text": "one"},
            {"kind": "reply", "parent": "e1", "text": "two"},
            {
                "kind": "summary",
                **identity,
                "thread": "e1",
                "from": "e1",
                "through": "e2",
                "text": "Earlier exchange.",
            },
            {"kind": "reply", "parent": "e2", "text": "new message"},
        ),
    )

    thread = model.threads(state)["e1"]
    assert thread["summaries"][0]["covers"] == ["e1", "e2"]
    assert thread["msgs"][-1]["text"] == "new message"


def progress_ends(thread: dict) -> dict:
    """What ended each progress message of a served thread, by its id."""
    return {
        message["id"]: message["completed_by"]
        for message in thread["msgs"]
        if "completed_by" in message
    }


# A live session's claim, its turn `turn-1` open.
CLAIMED = {
    **model.UNCLAIMED,
    "session_alive": True,
    "claim_session": "session-1",
    "turn": "turn-1",
    "turn_opened": model.NOW,
}


def test_a_step_the_user_wrote_after_waits_for_the_agent_s_reply():
    """The agent's next message, another step included, ends the step before it, but a
    step the user wrote after stands above their message until the agent says more
    than a step. The user's messages stay, and progress is never unread."""
    identity = {
        "author": "agent",
        "agent": "Codex",
        "session": "session-1",
        "turn": "turn-1",
    }
    messages = (
        {"kind": "comment", "text": "Check the schedule."},
        {
            "kind": "reply",
            **identity,
            "parent": "e1",
            "text": "Checking mounts.",
            "ephemeral": True,
        },
        {"kind": "reply", "parent": "e1", "text": "And the camera?"},
        {
            "kind": "reply",
            **identity,
            "parent": "e1",
            "text": "Checking the camera.",
            "ephemeral": True,
        },
    )

    def thread(events):
        state = model.served_reading(HUB, events, presence=CLAIMED)["browser"]
        return model.threads(state)["e1"]

    pending = thread(messages)
    assert progress_ends(pending) == {}
    assert pending["unread"] == {}

    answer = {"kind": "reply", **identity, "parent": "e1", "text": "Both fit."}
    completed = thread((*messages, answer))
    assert progress_ends(completed) == {"e2": "e5", "e4": "e5"}
    assert [message["text"] for message in completed["msgs"]] == [
        "Check the schedule.",
        "Checking mounts.",
        "And the camera?",
        "Checking the camera.",
        "Both fit.",
    ]
    assert completed["unread"] == {"e5": "e5"}


def test_progress_ends_survive_edits_and_explicit_summaries():
    identity = {"author": "agent", "agent": "Codex", "session": "session-1"}
    messages = (
        {"kind": "comment", "text": "Check the schedule."},
        {
            "kind": "reply",
            **identity,
            "parent": "e1",
            "text": "Checking mounts.",
            "ephemeral": True,
        },
        {
            "kind": "reply",
            **identity,
            "parent": "e1",
            "text": "Checking the camera.",
            "ephemeral": True,
        },
        {"kind": "reply", **identity, "parent": "e1", "text": "Both fit."},
    )
    corrected = model.threads(
        model.reading(
            HUB,
            (
                *messages,
                {
                    "kind": "edit",
                    **identity,
                    "message": "e2",
                    "text": "Mounts checked.",
                },
            ),
        )
    )["e1"]
    assert corrected["summaries"] == []
    assert progress_ends(corrected) == {"e2": "e3", "e3": "e4"}
    assert corrected["msgs"][1]["text"] == "Mounts checked."
    assert corrected["unread"] == {"e4": "e4"}

    explicit = model.threads(
        model.reading(
            HUB,
            (
                *messages,
                {
                    "kind": "summary",
                    **identity,
                    "thread": "e1",
                    "from": "e1",
                    "through": "e2",
                    "text": "The mounts were checked.",
                },
            ),
        )
    )["e1"]
    assert [(fold["covers"], fold["text"]) for fold in explicit["summaries"]] == [
        (["e1", "e2"], "The mounts were checked."),
    ]
    assert progress_ends(explicit) == {"e2": "e3", "e3": "e4"}
    assert explicit["unread"] == {"e4": "e4"}


def test_a_step_toward_no_owed_answer_ends_with_the_turn_that_wrote_it():
    """A step the thread owes no answer before, as one after a pick the agent
    answers on the page, stands while the turn that wrote it runs and ends with it.
    A step after a message still owed stands past its turn, as the line a line
    fork writes for the session does, even once the session ends, until the agent
    next speaks there."""
    agent = {"author": "agent", "agent": "Claude", "session": "session-1"}
    answered = (
        {"kind": "comment", "text": "Which fork writes the summary?"},
        {
            **agent,
            "kind": "reply",
            "parent": "e1",
            "responds": "e1",
            "text": "Its own.",
        },
        {
            **agent,
            "kind": "reply",
            "parent": "e1",
            "text": "Recording your pick on the page.",
            "ephemeral": True,
            "turn": "turn-1",
        },
    )

    def ends(events, presence):
        state = model.served_reading(HUB, events, presence=presence)["browser"]
        return progress_ends(model.threads(state)["e1"])

    assert ends(answered, CLAIMED) == {}
    assert ends(answered, {**CLAIMED, "turn_closed": model.NOW}) == {"e3": None}
    # A later turn of the main thread never brings it back.
    assert ends(answered, {**CLAIMED, "turn": "turn-2"}) == {"e3": None}
    owed = (*answered, {"kind": "reply", "parent": "e1", "text": "And the title?"})
    assert ends(owed, {**CLAIMED, "turn_closed": model.NOW}) == {"e3": None}

    line = (
        *owed,
        {
            **agent,
            "kind": "reply",
            "parent": "e4",
            "text": "Checking where titles come from.",
            "ephemeral": True,
            "turn": "turn-1",
        },
    )
    assert ends(line, {**CLAIMED, "turn_closed": model.NOW}) == {"e3": None}
    ended = {**CLAIMED, "turn_closed": model.NOW, "session_alive": False}
    assert ends(line, ended) == {"e3": None}


def test_the_agent_s_emoji_ends_a_step_and_another_thread_s_message_none():
    """The agent's emoji is its next message, so it ends the step before it and is
    unread as words are; a message in another thread ends nothing here."""
    agent = {"author": "agent", "agent": "Codex", "session": "session-1"}
    reply = {"kind": "reply", **agent, "parent": "e1"}
    messages = (
        {"kind": "comment", "text": "Check the schedule."},
        {**reply, "text": "Checking mounts.", "ephemeral": True},
        {**reply, "emoji": "👍"},
        {
            **reply,
            "text": "Connection failed.",
            "failure": "unavailable",
            "responds": "e1",
        },
        {**reply, "text": "Retrying.", "ephemeral": True},
        {"kind": "comment", "text": "A separate question."},
        {**reply, "parent": "e6", "text": "A separate answer."},
    )
    pending = model.threads(model.reading(HUB, messages))["e1"]
    # The failure hands the update back to the user, so no turn holds the retry up.
    assert progress_ends(pending) == {"e2": "e3", "e5": None}
    assert pending["unread"] == {"e3": "e3", "e4": "e4"}

    completed = (*messages, {**reply, "text": "Both mounts fit."})
    thread = model.threads(model.reading(HUB, completed))["e1"]
    assert thread["unread"] == {"e3": "e3", "e4": "e4", "e8": "e8"}
    assert progress_ends(thread) == {"e2": "e3", "e5": "e8"}

    revised = model.threads(
        model.reading(
            HUB,
            (
                *completed,
                {"kind": "read", "messages": [{"message": "e8", "version": "e8"}]},
                {"kind": "edit", **agent, "message": "e8", "text": "Only one fits."},
            ),
        )
    )["e1"]
    assert revised["unread"] == {"e3": "e3", "e4": "e4", "e8": "e10"}


def test_a_decision_on_any_message_settles_the_thread_it_belongs_to():
    """A user resolves the message in front of them, which is rarely the first.

    `resolve` names a parent, and the parent a user has under the pointer is
    whichever message they are reading — an agent's reply, usually, since that is
    what closes a question. A fold that took the parent for the root would leave
    every thread resolved on a reply left open: the panel would keep asking,
    and a command page reading the thread's `holds` would go on calling settled
    work outstanding.
    """
    registry = model.model_layer(page_packages()[0])
    open_thread = model.threads(model.reading(HUB, HELD_REQUEST, registry=registry))
    # The contrast: without it a fold that resolved every thread would pass below.
    assert open_thread["e1"]["resolved"] is None

    resolved = model.threads(
        model.reading(
            HUB, (*HELD_REQUEST, {"kind": "resolve", "parent": "e2"}), registry=registry
        )
    )["e1"]
    assert resolved["resolved"] is not None, "a resolve on the reply left it open"
    assert resolved["resolved"]["parent"] == "e2"
    assert resolved["attention"] is None


def test_every_served_agent_record_carries_the_name_it_is_shown_under():
    """An agent command run outside a harness session writes no `agent`, and the
    reading names it `Agent` wherever it reaches the browser: a thread's messages,
    its root, the event that closed it, and the activity feed's rows. A named
    session keeps its own name, and a user's record carries none."""
    page = model.leaf_page(
        "Route", '<h1 id="h">Route</h1><lf-activity id="feed"></lf-activity>'
    )
    state = model.reading(
        page,
        (
            {"kind": "comment", "text": "Which way?", "anchor": {"section": "h"}},
            {"kind": "reply", "author": "agent", "parent": "e1", "text": "North."},
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "session": "s-1",
                "parent": "e2",
                "text": "Or south.",
            },
            {"kind": "resolve", "author": "agent", "parent": "e1"},
        ),
    )

    thread = model.threads(state)["e1"]
    assert [message.get("agent") for message in thread["msgs"]] == [
        None,
        "Agent",
        "Codex",
    ]
    assert "agent" not in thread["root"]
    assert thread["resolved"]["agent"] == "Agent"
    assert [(row["id"], row["agent"]) for row in state["history"]] == [
        ("e4", "Agent"),
        ("e3", "Codex"),
        ("e2", "Agent"),
        ("e1", None),
    ]


def test_a_thread_move_that_owes_nothing_stands_in_its_thread_without_holding_it():
    """A card moved on a board the agent sent in a reply is served in that reply's
    thread, so every surface of the thread shows its receipt; but the move owes
    nothing and publishes no obligation, so it leaves the thread the user's to answer,
    and no card reads it as work the agent is holding. The thread's own unanswered
    input is the contrast: it publishes the obligation that holds its thread."""
    board = model.model_layer()["lf-board"]["example"]
    state = model.reading(
        HUB,
        (
            {"kind": "comment", "text": "Lay the feeder work out on a board."},
            {
                "kind": "reply",
                "author": "agent",
                "parent": "e1",
                "responds": "e1",
                "text": "Here is the board. Which card goes first?\n\n" + board,
                "obligation": True,
            },
            {
                "kind": "action",
                "widget": "feeder-board",
                "action": "move",
                "detail": {"unit": "card-baffle", "value": "col-doing", "rank": "0i"},
            },
            {"kind": "comment", "text": "And the heater?"},
        ),
    )

    assert [
        (workflow["id"], workflow["thread"], workflow["obligation"])
        for workflow in state["workflows"]
    ] == [("e4", "e4", "update:e4"), ("e3", "e1", None)]
    threads = model.threads(state)
    assert threads["e1"]["attention"] == "message:e2"
    assert threads["e4"]["attention"] == "update:e4"


def test_gesture_sequence_keeps_surviving_edits_and_durable_retractions():
    from served_records import gesture_sequence

    sequence = gesture_sequence()
    assert sequence["states"][4]["revision_labels"] == {"1": "Draft"}
    assert sequence["states"][5]["revision_labels"] == {"1": "Draft", "2": "v1"}
    assert sequence["states"][6]["revision_labels"] == {
        "1": "Draft",
        "2": "v1",
        "3": "v2",
    }
    projections = [
        model.projected(
            state["browser"], 1 if index == 7 else state["active"]["revision"]
        )
        for index, state in enumerate(sequence["states"])
    ]
    assert [projection["desired"] for projection in projections] == [
        [],
        ["e1"],
        ["e2"],
        ["e3"],
        ["e2"],
        [],
        [],
        ["e2"],
    ]
    assert {
        entry["event"]["id"]: entry["stands"] for entry in projections[4]["entries"]
    } == {"e1": True, "e2": True, "e3": False}
    assert [projection["actions"] for projection in projections] == [
        [],
        ["e1"],
        ["e2"],
        ["e3"],
        ["e2"],
        [],
        [],
        ["e2"],
    ]


def test_questions_settle_one_by_one():
    """Each question in a thread waits on the user until a message of theirs after it
    answers it, words or a reaction, or a resolve after it ends it; the thread's head
    marks the latest."""
    events = []

    def add(kind, identity, author="agent", **fields):
        events.append({"kind": kind, "id": identity, "author": author, **fields})
        return model.reading(HUB, events)

    add("comment", "first", text="Route?", obligation=True)
    add("reply", "checking", parent="first", text="Checking.")
    add("reply", "progress", parent="first", text="Still checking.", ephemeral=True)
    state = add("reply", "second", parent="first", text="Hue?", obligation=True)
    assert served_todos(state) == []
    assert [item["id"] for item in served_obligations(state)["user"]] == [
        "message:first",
        "message:second",
    ]
    # A reaction is the user's next message, so it answers every question before it.
    state = add("reply", "reaction", "user", parent="second", emoji="👍")
    assert served_obligations(state)["user"] == []
    first, second = served_obligations(state)["all"]
    assert standing_model.answered(first) and standing_model.answered(second)
    assert first["answer"]["value"] == {"emoji": "👍"}
    assert second["answer"]["event"]["id"] == "reaction"
    # A resolve ends the questions asked before it, and a reopening brings back
    # none of them; taking the resolve back does.
    state = add("reply", "third", parent="first", text="Size?", obligation=True)
    state = add("resolve", "close", "user", parent="first")
    assert served_todos(state) == []
    assert served_obligations(state)["user"] == []
    state = add("unresolve", "reopen", "user", parent="first")
    assert served_obligations(state)["user"] == []
    state = add("undo", "back", "user", undoes="close")
    assert [item["id"] for item in served_obligations(state)["user"]] == [
        "message:third"
    ]
    # A deleted message has no words, so the question it answered waits again.
    state = add("reply", "size", "user", parent="first", text="Medium")
    assert served_obligations(state)["user"] == []
    state = add("edit", "unsaid", "user", message="size", text="")
    assert [item["id"] for item in served_obligations(state)["user"]] == [
        "message:third"
    ]


def test_thread_widget_obligation_attention_comes_from_its_widget_without_a_prose_task():
    """Thread widgets have no independent thread seat: their user and unanswered
    lists agree, and later prose cannot retire the widget obligation."""
    events = [
        {
            "kind": "comment",
            "author": "agent",
            "text": "Choose a route.\n\n"
            + '<lf-options id="routes"><lf-option id="route-a">A</lf-option><lf-option id="route-b">B</lf-option></lf-options>',
        },
        {"kind": "reply", "author": "agent", "parent": "e1", "text": "Still checking."},
    ]
    state = model.reading(HUB, events)
    thread = model.threads(state)["e1"]
    assert thread["attention"] == "widget:routes"
    assert served_todos(state) == []
    [item] = served_obligations(state)["all"]
    assert item["id"] == "widget:routes"
    assert item["next_actor"] == "user"
    events.append(
        {
            "kind": "action",
            "widget": "routes",
            "action": "choose",
            "detail": {"value": ["route-a"]},
            "answered": True,
        }
    )
    state = model.reading(HUB, events)
    assert served_todos(state) == []
    [item] = served_obligations(state)["all"]
    assert standing_model.answered(item)
    assert item["answer"]["value"] == ["route-a"]


def test_a_summary_leaves_the_question_it_folds_on_the_users_list():
    """A summary over a question the user owes answers nothing, so the question stays
    on the user's list under the message that asked it."""
    state = model.reading(
        HUB,
        (
            {
                "kind": "comment",
                "author": "agent",
                "text": "Which route?",
                "obligation": True,
            },
            {"kind": "reply", "author": "agent", "parent": "e1", "text": "Checking."},
            {
                "kind": "reply",
                "author": "agent",
                "parent": "e1",
                "text": "Found one lead.",
            },
            {
                "kind": "summary",
                "author": "agent",
                "agent": "Codex",
                "session": "summary-session",
                "thread": "e1",
                "from": "e1",
                "through": "e2",
                "text": "Asked route; checking.",
            },
        ),
    )
    thread = model.threads(state)["e1"]
    [owed] = served_obligations(state)["user"]
    assert owed["message"] == "e1"
    [summary] = thread["summaries"]
    assert summary["covers"] == ["e1", "e2"]


def test_an_answer_sends_a_held_reading_only_what_changed():
    """A browser that names the reading it holds is sent what changed since, however
    many threads the page holds: a pick changes its widget's record and history, and
    nothing of any thread (`served_state.tail`, and `tests/runtime/state-tail.test.mjs`
    for the whole answer it completes to)."""
    page = model.leaf_page(
        "Tail",
        '<p id="p">One.</p><lf-group id="ask" label="Which?"><h2 id="ask-h">Which?</h2>'
        '<lf-options id="pick"><lf-option id="one">One</lf-option>'
        '<lf-option id="two">Two</lf-option></lf-options></lf-group>',
    )
    pick = {
        "kind": "action",
        "widget": "pick",
        "action": "choose",
        "detail": {"value": ["one"]},
        "answered": True,
        "attempt": "tail-pick-attempt-01",
    }

    def answer(threads: int) -> dict:
        log = [
            message
            for at in range(threads)
            for message in (
                {"kind": "comment", "text": f"Why {at}?"},
                {
                    "kind": "reply",
                    "author": "agent",
                    "parent": f"e{2 * at + 1}",
                    "text": "So.",
                },
            )
        ]
        held = model.served_reading(page, log)["browser"]["basis"]["key"]
        return model.served_reading(page, [*log, pick], held=held)

    few, many = answer(2), answer(40)
    assert [change["at"] for change in few["patch"]] == [
        change["at"] for change in many["patch"]
    ]
    [picked] = many["events"]
    assert picked["attempt"] == "tail-pick-attempt-01"
    changed = {tuple(change["at"]): change for change in many["patch"]}
    assert ("browser", "views", "1", "thread", "threads") not in changed
    # The pick answers its widget's question and owes the agent an update.
    obligations = changed[("browser", "views", "1", "obligations")]
    assert [name for name, _ in obligations["changed"]] == ["widget:pick"]
    assert [item["id"] for item in obligations["items"]] == [f"update:{picked['id']}"]


def test_a_reply_sends_its_message_and_what_it_changed_of_its_thread():
    """However long the thread a reply joins, its answer carries the new message and
    the fields of the thread it changed, and none of the thread's other messages
    (`served_state.tail`)."""
    page = model.leaf_page("Tail", '<p id="p">One.</p>')

    def thread_change(replies: int) -> list:
        log = [
            {"kind": "comment", "text": "Why?"},
            *(
                {"kind": "reply", "parent": "e1", "text": f"And {at}?"}
                if at % 2
                else {"kind": "reply", "author": "agent", "parent": "e1", "text": "So."}
                for at in range(replies)
            ),
        ]
        held = model.served_reading(page, log)["browser"]["basis"]["key"]
        reply = {"kind": "reply", "parent": "e1", "text": "Thanks."}
        tail = model.served_reading(page, [*log, reply], held=held)
        [threads] = [
            change
            for change in tail["patch"]
            if change["at"] == ["browser", "views", "1", "thread", "threads"]
        ]
        assert set(threads) == {"at", "by", "changed"}
        [[name, changes]] = threads["changed"]
        assert name == "e1"
        return changes

    short, long = thread_change(4), thread_change(40)
    assert [change["at"] for change in short] == [change["at"] for change in long]
    [messages] = [change for change in long if change["at"] == ["msgs"]]
    assert set(messages) == {"at", "by", "items", "after"}
    assert [message["text"] for message in messages["items"]] == ["Thanks."]


def test_a_data_write_sends_a_held_reading_only_the_source_it_wrote():
    """However many sources a page holds, a write to one sends that source's new value
    and fields and nothing of any other source, and a rerun that writes the same value
    again sends its run and not the value (`served_state.tail`)."""
    page = model.leaf_page("Tail", '<p id="p">One.</p>')

    def changes(sources: int, rewritten: str) -> dict:
        texts = {f"s{at}": ("first", f"Line of {at}.\n" * 200) for at in range(sources)}
        before = model.served_data(texts, "text-document")
        held = model.served_reading(page, data=before)["browser"]["basis"]["key"]
        after = model.served_data(
            {**texts, "s1": ("second", rewritten)}, "text-document"
        )
        tail = model.served_reading(page, data=after, held=held)
        return {tuple(change["at"]): change.get("value") for change in tail["patch"]}

    few, many = changes(2, "A new line.\n"), changes(30, "A new line.\n")
    assert few.keys() == many.keys()
    assert {at[:3] for at in many if at[0] == "data"} == {
        ("data", "version"),
        ("data", "sources", "s1"),
    }
    assert many[("data", "sources", "s1", "value")] == "A new line.\n"
    rerun = changes(30, "Line of 1.\n" * 200)
    assert ("data", "sources", "s1", "run") in rerun
    assert ("data", "sources", "s1", "value") not in rerun


def test_an_answer_to_a_reading_the_server_does_not_remember_is_whole():
    """A key the server never named, or named so many readings ago that it has
    forgotten it, gets the whole answer (`served_state.tail.REMEMBERED`)."""
    from leaf.serving.served_state.tail import REMEMBERED

    page = model.leaf_page("Tail", '<p id="p">One.</p>')
    log = [{"kind": "comment", "text": "Why?"}]
    held = model.served_reading(page, log)["browser"]["basis"]["key"]
    for at in range(REMEMBERED):
        model.served_reading(page, [*log, {"kind": "comment", "text": f"And {at}?"}])
    for key in (held, "not a key"):
        whole = model.served_reading(page, log, held=key)
        assert "since" not in whole, key
        assert [event["id"] for event in whole["events"]] == ["e1"], key


def test_a_pages_memory_keeps_the_readings_its_tabs_hold(tmp_path, monkeypatch):
    """Each page's readings are remembered in its memory (`page_memory`), so one page's
    answers, such as a live sample's or another page's on a multiplexed server, never
    push out the reading another page's tab holds. A page whose memory the process
    dropped answers whole, and patches again from that answer."""
    from leaf.base import page_memory
    from leaf.serving.served_state import tail

    monkeypatch.setattr(tail, "REMEMBERED", 1)
    html = model.leaf_page("Tail", '<p id="p">One.</p>')
    log = [{"kind": "comment", "text": "Why?"}]
    first = model.served_reading(html, log)
    later = model.served_reading(html, [*log, {"kind": "comment", "text": "And?"}])
    page, sample = tmp_path / "page", tmp_path / "sample"

    def key(answer: dict) -> str:
        return answer["browser"]["basis"]["key"]

    held = key(tail.answer(deepcopy(first), None, page))
    tail.answer(deepcopy(later), None, sample)
    assert "since" in tail.answer(deepcopy(later), held, page)

    held = key(tail.answer(deepcopy(first), None, page))
    for n in range(page_memory.PageMemories.LIMIT):
        page_memory.memory_of(tmp_path / f"other-{n}")
    whole = tail.answer(deepcopy(later), held, page)
    assert "since" not in whole
    assert "since" in tail.answer(deepcopy(first), key(whole), page)


def test_revision_labels_name_each_draft_after_the_newest_earlier_stamp():
    from leaf.base.files import revision_labels

    events = [
        {"kind": "note", "revision": 2, "version": 1},
        {"kind": "note", "revision": 5, "version": 2},
        {"kind": "activation", "revision": 6},
    ]
    assert revision_labels(events, range(1, 7)) == {
        1: "Draft",
        2: "v1",
        3: "Draft after v1",
        4: "Draft after v1",
        5: "v2",
        6: "Draft after v2",
    }
