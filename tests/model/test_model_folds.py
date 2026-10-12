"""Folds whose whole subject is the reading, not what a widget draws with it.

Each test here states one document and one log and asks what the browser would
be handed. `model_folds` owns the arrangement; `tests/AGENTS.md`'s rule that an
assertion belongs at the boundary that owns it is why these are not in
`test_render_*.py`: no renderer decides any of them, so serving a page and
opening Chromium would put a browser between the cause and the claim without
putting one in the claim.
"""

import model_folds as model
from interact_support import page_packages

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
    """Only marked progress folds, including one-message runs split by the user."""
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
    assert pending["unread"] == [{"message": "e4", "version": "e4"}]

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
    assert [
        (fold["covers"], fold["label"], fold["text"], fold["trigger"])
        for fold in completed["summaries"]
    ] == [
        (["e2"], "Previous progress messages", "", "e5"),
        (["e4"], "Previous progress messages", "", "e5"),
    ]
    assert [message["text"] for message in completed["msgs"]] == [
        "Check the schedule.",
        "Checking mounts.",
        "And the camera?",
        "Checking the camera.",
        "Both fit.",
        "Checking the next week.",
    ]
    assert completed["unread"] == [
        {"message": "e5", "version": "e5"},
        {"message": "e6", "version": "e6"},
    ]


def test_explicit_summaries_own_progress_overlap_and_progress_edits_keep_the_fold():
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
    assert [fold["covers"] for fold in corrected["summaries"]] == [["e2", "e3"]]
    assert corrected["msgs"][1]["text"] == "Mounts checked."
    assert corrected["unread"] == [{"message": "e4", "version": "e4"}]

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
        (["e3"], ""),
    ]
    assert explicit["unread"] == [{"message": "e4", "version": "e4"}]


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
    assert pending["unread"] == [
        {"message": identity, "version": identity} for identity in ("e2", "e4", "e5")
    ]

    completed = (*messages, {**reply, "text": "Both mounts fit."})
    thread = model.threads(model.reading(HUB, completed))["e1"]
    assert thread["unread"] == [
        {"message": identity, "version": identity} for identity in ("e4", "e8")
    ]
    assert [fold["trigger"] for fold in thread["summaries"]] == ["e8", "e8"]

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
    assert revised["unread"] == [
        {"message": "e4", "version": "e4"},
        {"message": "e8", "version": "e10"},
    ]


def test_a_decision_on_any_message_settles_the_thread_it_belongs_to():
    """A user resolves the message in front of them, which is rarely the first.

    `resolve` names a parent, and the parent a user has under the pointer is
    whichever message they are reading — an agent's reply, usually, since that is
    what closes a question. A fold that took the parent for the root would leave
    every thread resolved on a reply standing open: the panel would keep asking,
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
    assert [message["agent"] for message in thread["msgs"]] == [None, "Agent", "Codex"]
    assert thread["root"]["agent"] is None
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
    nothing, so it leaves the thread the user's to answer, and no card reads it as
    work the agent is holding. The thread's own unanswered input is the contrast:
    it stands in its thread and holds it."""
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
                "ask": True,
                "markup": board,
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
        (workflow["id"], workflow["thread"], workflow["holds_thread"])
        for workflow in state["workflows"]
    ] == [("e4", "e4", True), ("e3", "e1", False)]
    threads = model.threads(state)
    assert threads["e1"]["attention"] == {
        "kind": "needs_user",
        "reason": "ask",
        "workflow": None,
    }
    assert threads["e4"]["attention"] == {
        "kind": "waiting",
        "reason": "workflow",
        "workflow": "e4",
    }


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


def test_question_lifecycle_selects_current_prompt_and_preserves_first_settlement():
    """Only the latest question is on the user; a settled later question uncovers
    an older one, and a reply after a task end does not change that end."""
    events = []

    def add(kind, identity, author="agent", **fields):
        events.append({"kind": kind, "id": identity, "author": author, **fields})
        return model.reading(HUB, events)

    add("comment", "first", text="Which route?")
    add("reply", "checking", parent="first", text="Checking.")
    add("reply", "progress", parent="first", text="Still checking.", ephemeral=True)
    state = add("reply", "second", parent="first", text="Which colour?", ask=True)
    assert model.threads(state)["first"]["user_prompt"] == {
        "message": "second",
        "version": "second",
    }
    assert state["todos"] == []
    assert [question["id"] for question in state["thread"]["asks"]["all"]] == [
        "reply:first",
        "reply:second",
    ]
    assert [question["id"] for question in state["thread"]["asks"]["user"]] == [
        "reply:second"
    ]
    state = add("reply", "reaction", "user", parent="second", token="keep")
    assert model.threads(state)["first"]["user_prompt"] == {
        "message": "first",
        "version": "first",
    }
    assert [question["id"] for question in state["thread"]["asks"]["user"]] == [
        "reply:first"
    ]
    assert state["thread"]["asks"]["all"][1]["answer"]["event"]["id"] == "reaction"
    state = add(
        "todo_end",
        "end",
        todo="reply:first",
        outcome="dropped",
        detail="Asked elsewhere",
    )
    assert model.threads(state)["first"]["user_prompt"] is None
    state = add("reply", "answer", "user", parent="first", text="Route A")
    first, second = state["thread"]["asks"]["all"]
    assert (first["status"], first["answer"]) == ("withdrawn", None)
    assert (second["status"], second["answer"]["event"]["id"]) == (
        "answered",
        "reaction",
    )
    state = add("reply", "third", parent="first", text="Which size?", ask=True)
    state = add("resolve", "close", "user", parent="first")
    assert state["todos"] == []
    assert model.threads(state)["first"]["user_prompt"] is None
    state = add("unresolve", "reopen", "user", parent="first")
    assert [question["id"] for question in state["thread"]["asks"]["user"]] == [
        "reply:third"
    ]
    assert model.threads(state)["first"]["user_prompt"] == {
        "message": "third",
        "version": "third",
    }


def test_frozen_ask_attention_comes_from_its_widget_without_a_prose_task():
    """Frozen widgets have no independent thread seat: their user and unanswered
    lists agree, and later prose or reactions cannot retire the widget Ask."""
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
    assert thread["user_prompt"] is None
    assert thread["attention"] == {
        "kind": "needs_user",
        "reason": "ask",
        "workflow": None,
    }
    assert state["todos"] == []
    [question] = state["thread"]["asks"]["all"]
    assert question["id"] == "widget:routes"
    assert question["next_actor"] == "user"
    events.append(
        {
            "kind": "action",
            "widget": "routes",
            "action": "choose",
            "detail": {"value": ["route-a"]},
        }
    )
    state = model.reading(HUB, events)
    assert model.threads(state)["e1"]["user_prompt"] is None
    assert state["todos"] == []
    assert state["ended_todos"] == []
    [question] = state["thread"]["asks"]["all"]
    assert (question["status"], question["answer"]["value"]) == (
        "answered",
        ["route-a"],
    )


def test_after_is_what_each_gesture_leaves_the_thread_as_the_log_reads_it():
    """While a gesture the user sent is unanswered, the browser draws its thread, and
    the asks in it, as the log will read them once it lands, and only the log
    knows what a gesture leaves standing: a reply answers prose and leaves a widget ask, a
    rewrite answers nothing, a reopening brings back what the resolution suppressed,
    a `keep` reaction settles the question it marks and taking it back reopens that
    question, and nothing the user says
    recovers a pick whose answer failed. Each served
    `after[kind]` is checked against the reading of the log with that gesture
    appended: its attention, the waiting one's workflow aside, and the asks the
    user owes in the thread. Each ask it owes is one the served lists already carry,
    on Questions, held or done, so the browser places it rather than building it."""
    asked = {"kind": "comment", "text": "Chart the year."}
    prose = {
        "kind": "reply",
        "author": "agent",
        "parent": "e1",
        "text": "Which year?",
        "ask": True,
    }
    ask = {
        "kind": "reply",
        "author": "agent",
        "parent": "e1",
        "text": "Pick one.",
        "markup": '<lf-options id="years" choose><lf-option id="y24">2024</lf-option><lf-option id="y25">2025</lf-option></lf-options>',
    }
    pick = {
        "kind": "action",
        "widget": "years",
        "action": "choose",
        "detail": {"value": ["y25"]},
    }
    # The harness gave up answering the user's pick, which is theirs to send again
    # whatever they say beside it.
    failed = {
        "kind": "reply",
        "author": "agent",
        "parent": "e2",
        "responds": "e3",
        "failure": "turn_failed",
        "text": "No answer is coming.",
    }
    resolve = {"kind": "resolve", "parent": "e1"}
    done = {"kind": "reply", "author": "agent", "parent": "e1", "text": "Done."}
    cases = {
        "plain": (asked, done),
        "prose question": (asked, prose),
        "Ask in the thread": (asked, ask),
        "prose beside an Ask": (asked, ask, {**prose, "parent": "e2"}),
        "resolved over a prose question": (asked, prose, resolve),
        "resolved over an Ask": (asked, ask, resolve),
        "failed answer to a pick": (asked, ask, pick, failed),
        "resolved after a failed pick": (asked, ask, pick, failed, resolve),
        "prose settled by a reaction": (
            asked,
            prose,
            {"kind": "reply", "parent": "e2", "token": "keep"},
        ),
        # The agent at work on the comment: the thread waits on that work, which
        # outranks a send beside it, as the log will say.
        "at work on the comment": (
            asked,
            {
                "kind": "start",
                "author": "agent",
                "agent": "Agent",
                "session": "s",
                "turn": "t",
                "item": "e1",
                "text": "Charting",
            },
        ),
    }
    gestures = {
        "reply": {"kind": "reply", "parent": "e1", "text": "2025."},
        "edit": {"kind": "edit", "message": "e1", "text": "Chart 2025."},
        "resolve": {"kind": "resolve", "parent": "e1"},
        "unresolve": {"kind": "unresolve", "parent": "e1"},
        # A reaction whose token settles the question the user owes.
        "react": {"kind": "reply", "token": "keep"},
        # Taking back the newest such reaction the thread holds.
        "unreact": {"kind": "undo"},
    }

    def owed(state):
        return [
            question["id"]
            for question in state["thread"]["asks"]["user"]
            if question["thread"] == "e1"
        ]

    for name, events in cases.items():
        served = model.reading(HUB, events)
        thread = model.threads(served)["e1"]
        lists = served["views"]["1"]["queues"]
        carried = {
            item["id"] for side in ("questions", "held", "done") for item in lists[side]
        }
        for kind, gesture in gestures.items():
            after = thread["after"][kind]
            assert after is None or set(after["owed"]) <= carried, (name, kind)
            if (kind == "resolve") == bool(thread["resolved"]) and kind in {
                "resolve",
                "unresolve",
            }:
                assert after is None, (name, kind)
                continue
            if kind == "react":
                if thread["user_prompt"] is None:
                    assert after is None, (name, kind)
                    continue
                gesture = {**gesture, "parent": thread["user_prompt"]["message"]}
            named = {}
            if kind == "unreact":
                reaction = next(
                    (
                        message
                        for message in reversed(thread["msgs"])
                        if message["author"] == "user"
                        and message.get("token") == "keep"
                        and message.get("parent")
                        in {
                            turn["id"]
                            for turn in thread["msgs"]
                            if turn["author"] == "agent"
                        }
                    ),
                    None,
                )
                if reaction is None:
                    assert after is None, (name, kind)
                    continue
                named = {"undoes": reaction["id"]}
                gesture = {**gesture, **named}
            state = model.reading(HUB, (*events, gesture))
            attention = model.threads(state)["e1"]["attention"]
            # A wait on the gesture itself names no workflow: the browser draws its
            # own send there. A wait on any other names it as the log does.
            if attention is not None and attention["workflow"] == f"e{len(events) + 1}":
                attention = {**attention, "workflow": None}
            assert after == {"attention": attention, "owed": owed(state), **named}, (
                name,
                kind,
            )


def test_summary_protects_the_unanswered_question_after_later_agent_messages():
    """A summary cannot hide the question the user owes merely because a newer
    agent message is the last turn. Protection selects the canonical prompt."""
    state = model.reading(
        HUB,
        (
            {"kind": "comment", "author": "agent", "text": "Which route?"},
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
    assert thread["user_prompt"] == {"message": "e1", "version": "e1"}
    [summary] = thread["summaries"]
    assert summary["covers"] == ["e1", "e2"]
    assert summary["protected"] == ["e1"]
