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

from leaf import standing as standing_model

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


def test_summaries_replace_overlaps_and_edits_do_not_resurrect_them():
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
            {
                "kind": "edit",
                **identity,
                "message": "e3",
                "text": "three, revised",
            },
        ),
    )

    thread = model.threads(state)["e1"]
    assert thread["summaries"] == []
    assert [message["text"] for message in thread["msgs"]] == [
        "one",
        "two",
        "three, revised",
        "four",
    ]


def test_a_reaction_taken_back_retires_the_summaries_written_after_it():
    """A summary in words may report what a reaction said, wherever the reaction
    stood, so taking back one its thread held when the summary was written retires
    the summary, as rewriting a message in its range does, and taking back what it
    stood on later doesn't restore it. A reaction made after the summary leaves it
    standing when taken back."""
    identity = {"author": "agent", "agent": "Agent", "session": "session-1"}
    log = (
        {"kind": "comment", "text": "Ship it?"},
        {"kind": "reply", "parent": "e1", "token": "keep"},
        {"kind": "reply", **identity, "parent": "e1", "text": "Ready when you are."},
        {"kind": "reply", "parent": "e2", "token": "keep"},
        {"kind": "reply", **identity, "parent": "e1", "text": "Shipping."},
        {
            "kind": "summary",
            **identity,
            "thread": "e1",
            "from": "e3",
            "through": "e5",
            "text": "The user approved shipping.",
        },
        {"kind": "reply", "parent": "e5", "token": "keep"},
    )

    def summaries(*undone):
        tail = tuple({"kind": "undo", "undoes": event} for event in undone)
        state = model.reading(HUB, (*log, *tail))
        return [summary["id"] for summary in model.threads(state)["e1"]["summaries"]]

    assert summaries() == ["e6"]
    assert summaries("e7") == ["e6"]
    assert summaries("e2") == []
    assert summaries("e4", "e2") == []


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
                {"kind": "reply", "parent": "e2", "token": "keep"},
                {
                    "kind": "reply",
                    **AGENT,
                    "parent": "e3",
                    "responds": "e2",
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
        {"kind": "reply", "parent": "e4", "token": "keep"},
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
    assert thread["summaries"][0]["label"] == "Earlier discussion"
    assert thread["msgs"][-1]["text"] == "new message"


def test_folds_without_summary_prose_keep_corrected_originals():
    identity = {"author": "agent", "agent": "Agent", "session": "session-1"}
    state = model.reading(
        HUB,
        (
            {"kind": "comment", "text": "one"},
            {"kind": "reply", **identity, "parent": "e1", "text": "two"},
            {"kind": "reply", "parent": "e1", "text": "three"},
            {"kind": "reply", **identity, "parent": "e1", "text": "four"},
            {
                "kind": "summary",
                **identity,
                "thread": "e1",
                "from": "e1",
                "through": "e2",
                "label": "Previous progress messages",
                "text": "",
            },
            {
                "kind": "summary",
                **identity,
                "thread": "e1",
                "from": "e3",
                "through": "e4",
                "text": "The later exchange.",
            },
            {"kind": "edit", **identity, "message": "e2", "text": "two, revised"},
            {"kind": "edit", **identity, "message": "e4", "text": "four, revised"},
        ),
    )

    thread = model.threads(state)["e1"]
    [fold] = thread["summaries"]
    assert (fold["covers"], fold["label"], fold["text"]) == (
        ["e1", "e2"],
        "Previous progress messages",
        "",
    )
    assert [message["text"] for message in thread["msgs"]] == [
        "one",
        "two, revised",
        "three",
        "four, revised",
    ]


def test_ephemeral_updates_wait_for_an_answer_and_preserve_user_interjections():
    """An answer hides every preceding progress run, including across a user reply.
    User messages and newer progress remain, and progress is never unread."""
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
        {"kind": "reply", "parent": "e1", "text": "And the camera?"},
        {
            "kind": "reply",
            **identity,
            "parent": "e1",
            "text": "Checking the camera.",
            "ephemeral": True,
        },
    )
    pending = model.threads(model.reading(HUB, messages))["e1"]
    assert pending["summaries"] == []
    assert pending["unread"] == {}

    answer = {"kind": "reply", **identity, "parent": "e1", "text": "Both fit."}
    later_progress = {
        "kind": "reply",
        **identity,
        "parent": "e1",
        "text": "Checking the next week.",
        "ephemeral": True,
    }
    completed = model.threads(model.reading(HUB, (*messages, answer, later_progress)))[
        "e1"
    ]
    assert completed["summaries"] == []
    assert {
        message["id"]: message["completed_by"]
        for message in completed["msgs"]
        if "completed_by" in message
    } == {"e2": "e5", "e4": "e5"}
    assert [message["text"] for message in completed["msgs"]] == [
        "Check the schedule.",
        "Checking mounts.",
        "And the camera?",
        "Checking the camera.",
        "Both fit.",
        "Checking the next week.",
    ]
    assert completed["unread"] == {"e5": "e5"}


def test_progress_completion_survives_edits_and_explicit_summaries():
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
    assert corrected["msgs"][1]["completed_by"] == "e4"
    assert corrected["msgs"][2]["completed_by"] == "e4"
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
    assert explicit["msgs"][1]["completed_by"] == "e4"
    assert explicit["msgs"][2]["completed_by"] == "e4"
    assert explicit["unread"] == {"e4": "e4"}


def test_only_a_main_reply_in_the_same_thread_supersedes_progress():
    agent = {"author": "agent", "agent": "Codex", "session": "session-1"}
    reply = {"kind": "reply", **agent, "parent": "e1"}
    messages = (
        {"kind": "comment", "text": "Check the schedule."},
        {**reply, "text": "Checking mounts.", "ephemeral": True},
        {**reply, "token": "keep"},
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
    assert pending["summaries"] == []
    assert pending["unread"] == {"e4": "e4"}

    completed = (*messages, {**reply, "text": "Both mounts fit."})
    thread = model.threads(model.reading(HUB, completed))["e1"]
    assert thread["unread"] == {"e4": "e4", "e8": "e8"}
    assert thread["summaries"] == []
    assert {
        message["id"]: message["completed_by"]
        for message in thread["msgs"]
        if "completed_by" in message
    } == {"e2": "e8", "e5": "e8"}

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
    assert revised["unread"] == {"e4": "e4", "e8": "e10"}


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


def test_a_frozen_move_that_owes_nothing_stands_in_its_thread_without_holding_it():
    """A card moved on a board the agent sent in a reply is served in that reply's
    thread, so every surface of the thread shows its receipt; but the move owes
    nothing and publishes no obligation, so it leaves the thread the user's to answer,
    and no card reads it as work the agent is holding. The thread's own unanswered
    input is the contrast: it publishes the obligation that holds its thread."""
    board = model.model_layer()["lf-board"]["x-example"]
    state = model.reading(
        HUB,
        (
            {"kind": "comment", "text": "Lay the feeder work out on a board."},
            {
                "kind": "reply",
                "author": "agent",
                "parent": "e1",
                "responds": "e1",
                "text": "Here is the board. Which card goes first?",
                "markup": board,
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


def test_questions_settle_one_by_one_and_an_end_outlasts_a_later_reply():
    """Each question in a thread waits on the user until a message or settling
    reaction after it answers it; the thread's head marks the latest. A reply after
    the agent ended a question does not change that end."""
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
    state = add("reply", "reaction", "user", parent="second", token="keep")
    assert [item["id"] for item in served_obligations(state)["user"]] == [
        "message:first"
    ]
    assert served_obligations(state)["all"][1]["answer"]["event"]["id"] == "reaction"
    state = add(
        "todo_end",
        "end",
        todo="message:first",
        outcome="dropped",
        detail="Asked elsewhere",
    )
    assert served_obligations(state)["user"] == []
    state = add("reply", "answer", "user", parent="first", text="Route A")
    first, second = served_obligations(state)["all"]
    assert (first["outcome"], first["answer"]) == ("dropped", None)
    assert standing_model.answered(second)
    assert second["answer"]["event"]["id"] == "reaction"
    state = add("reply", "third", parent="first", text="Size?", obligation=True)
    state = add("resolve", "close", "user", parent="first")
    assert served_todos(state) == []
    assert served_obligations(state)["user"] == []
    state = add("unresolve", "reopen", "user", parent="first")
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


def test_frozen_obligation_attention_comes_from_its_widget_without_a_prose_task():
    """Frozen widgets have no independent thread seat: their user and unanswered
    lists agree, and later prose or reactions cannot retire the widget obligation."""
    events = [
        {
            "kind": "comment",
            "author": "agent",
            "text": "Choose a route.",
            "markup": '<lf-options id="routes" choose><lf-option id="route-a">A</lf-option><lf-option id="route-b">B</lf-option></lf-options>',
        },
        {"kind": "reply", "author": "agent", "parent": "e1", "text": "Still checking."},
        {"kind": "reply", "parent": "e1", "token": "keep"},
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
        }
    )
    state = model.reading(HUB, events)
    assert served_todos(state) == []
    [item] = served_obligations(state)["all"]
    assert standing_model.answered(item)
    assert item["answer"]["value"] == ["route-a"]


def test_summary_protects_the_unanswered_obligation_after_later_agent_messages():
    """A summary cannot hide the question the user owes merely because a newer
    agent message is the last turn. Protection selects the canonical prompt."""
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
    assert summary["protected"] == ["e1"]


def test_an_answer_sends_a_held_reading_only_what_changed():
    """A browser that names the reading it holds is sent what changed since, however
    many threads the page holds: a pick changes its widget's record and history, and
    nothing of any thread (`served_state.tail`, and `tests/runtime/state-tail.test.mjs`
    for the whole answer it completes to)."""
    page = model.leaf_page(
        "Tail",
        '<p id="p">One.</p><lf-ask id="ask"><h2>Which?</h2>'
        '<lf-options id="pick" choose><lf-option id="one">One</lf-option>'
        '<lf-option id="two">Two</lf-option></lf-options></lf-ask>',
    )
    pick = {
        "kind": "action",
        "widget": "pick",
        "action": "choose",
        "detail": {"value": ["one"]},
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


def test_an_answer_to_a_reading_the_server_does_not_remember_is_whole():
    """A key the server never named, or named so many readings ago that it has
    forgotten it, gets the whole answer (`served_state.tail.REMEMBERED`)."""
    from leaf.served_state.tail import REMEMBERED

    page = model.leaf_page("Tail", '<p id="p">One.</p>')
    log = [{"kind": "comment", "text": "Why?"}]
    held = model.served_reading(page, log)["browser"]["basis"]["key"]
    for at in range(REMEMBERED):
        model.served_reading(page, [*log, {"kind": "comment", "text": f"And {at}?"}])
    for key in (held, "not a key"):
        whole = model.served_reading(page, log, held=key)
        assert "since" not in whole, key
        assert [event["id"] for event in whole["events"]] == ["e1"], key


def test_one_pages_answers_leave_another_readings_remembered(monkeypatch):
    """A process serving several pages, or a page and its live samples, remembers each
    page's readings apart, so one page's answers never push out the reading another
    page's tab holds (`served_state.tail.PAGES`)."""
    from leaf.served_state import tail

    monkeypatch.setattr(tail, "REMEMBERED", 1)
    page = model.leaf_page("Tail", '<p id="p">One.</p>')
    log = [{"kind": "comment", "text": "Why?"}]
    first = model.served_reading(page, log)
    later = model.served_reading(page, [*log, {"kind": "comment", "text": "And?"}])
    held = tail.answer(deepcopy(first), None, "page")["browser"]["basis"]["key"]
    tail.answer(deepcopy(later), None, "sample")
    assert "since" in tail.answer(deepcopy(later), held, "page")


def test_revision_labels_name_each_draft_after_the_newest_earlier_stamp():
    from leaf.files import revision_labels

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
