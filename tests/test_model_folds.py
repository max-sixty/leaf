"""Folds whose whole subject is the reading, not what a widget draws with it.

Each test here states one document and one log and asks what the browser would
be handed. `model_folds` owns the arrangement; `tests/AGENTS.md`'s rule that an
assertion belongs at the boundary that owns it is why these are not in
`test_render_*.py`: no renderer decides any of them, so serving a page and
opening Chromium would put a browser between the cause and the claim without
putting one in the claim.
"""

import model_folds as model

HUB = model.leaf_page(
    "command hub",
    """<h1 id="h">Atlas</h1>
<lf-command id="atlas" label="Replace the parser">
  <lf-task id="goal-parser" status="active" talk><strong>Replace the XML parser</strong></lf-task>
</lf-command>""",
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

# One draft, three revisions of it. The user rewrote the authored words in r1;
# r2 rewrote them again and said so; r3 is an unrelated edit on r2's words.
DRAFT = """<h1 id="t">Journey</h1>
<lf-draft id="draft-ops"{attrs}><pre>
    {text}
</pre></lf-draft>"""
AUTHORED = "Run the migration before deploying."
USER_EDIT = "Run the migration before deploying. It takes about a minute."
CORRECTED = "Run the migration after deploying — it needs the new column."


def test_summaries_replace_overlaps_and_edits_do_not_resurrect_them():
    messages = (
        {"kind": "comment", "text": "one"},
        {"kind": "reply", "parent": "e1", "text": "two"},
        {"kind": "reply", "parent": "e2", "text": "three"},
        {"kind": "reply", "parent": "e3", "text": "four"},
    )
    identity = {"author": "agent", "agent": "Agent", "session": "session-1"}
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
            {"kind": "reply", "parent": "e1", "text": "two"},
            {"kind": "reply", "parent": "e1", "text": "three"},
            {"kind": "reply", "parent": "e1", "text": "four"},
            {
                "kind": "summary",
                **identity,
                "thread": "e1",
                "from": "e1",
                "through": "e2",
                "label": "Previous updates",
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
        "Previous updates",
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
        (["e2"], "Previous updates", "", "e5"),
        (["e4"], "Previous updates", "", "e5"),
    ]
    assert [message["text"] for message in completed["msgs"]] == [
        "Check the schedule.",
        "Checking mounts.",
        "And the camera?",
        "Checking the camera.",
        "Both fit.",
        "Checking the next week.",
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


def test_a_decision_on_any_message_settles_the_thread_it_belongs_to():
    """A user resolves the message in front of them, which is rarely the first.

    `resolve` names a parent, and the parent a user has under the pointer is
    whichever message they are reading — an agent's reply, usually, since that is
    what closes a question. A fold that took the parent for the root would leave
    every thread resolved on a reply standing open: the panel would keep asking,
    and a command page reading the thread's `holds` would go on calling settled
    work outstanding.
    """
    registry = model.model_layer("command-hub")
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


def test_a_retraction_outlives_the_version_that_made_it():
    """`restated` belongs to the version that rewrote the words, and to no other.

    v3 has nothing to declare, because it is not the one taking anything back. So
    the retraction cannot live in the markup, or v3's silence would read as "carry
    the decision" and hand the user's edit straight back — the same resurrection
    one version later and just as quiet. The note records it in the log instead,
    where it is a fact with a revision on it that every later revision inherits.
    """
    revisions = {
        1: model.leaf_page("draft", DRAFT.format(text=AUTHORED, attrs="")),
        2: model.leaf_page("draft", DRAFT.format(text=CORRECTED, attrs=" restated")),
        3: model.leaf_page("draft", DRAFT.format(text=CORRECTED, attrs="")),
    }
    log = (
        {
            "kind": "action",
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": USER_EDIT},
        },
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": 2,
            "text": "rewrote the draft",
            "restated": ["draft-ops"],
        },
        {
            "kind": "note",
            "author": "agent",
            "version": 3,
            "revision": 3,
            "text": "unrelated copy edits",
        },
    )

    def standing(revision):
        state = model.reading(revisions, log, revision=revision)
        return model.projected(state, revision)["desired"]

    # r1 is the anchor: the edit is a standing decision on the words it was made
    # against, or the two readings below say nothing about retraction.
    assert standing(1) == ["e1"]
    assert standing(2) == []
    # The version that says nothing inherits it.
    assert standing(3) == []


def test_every_served_agent_record_carries_the_name_it_is_shown_under():
    """An agent command run outside a host session writes no `agent`, and the
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
                "awaits": True,
                "markup": board,
            },
            {
                "kind": "action",
                "widget": "feeder-board",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-doing", "rank": "0i"},
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


def test_the_runtime_tests_build_on_the_records_the_server_serves():
    """`served_records.json` is this fold's output, so a Node test built on it carries
    every field the server sends; a change to the served shape fails here until the
    file is rewritten."""
    import served_records

    assert served_records.RECORDS.read_text() == served_records.serialized(), (
        "the served thread or workflow changed — rerun `uv run tests/served_records.py`"
    )


def test_each_served_action_says_whether_it_still_stands():
    """The browser withdraws the action on top of a coordinate before the log does,
    and shows the next one that stands. Whether an older action stands is this fold's
    reading, so the wire carries it: an undo ends one, and the one beneath survives."""
    page = model.leaf_page("draft", DRAFT.format(text=AUTHORED, attrs=""))
    edit = {"kind": "action", "widget": "draft-ops", "action": "edit"}
    state = model.reading(
        page,
        (
            {**edit, "detail": {"text": USER_EDIT}},
            {**edit, "detail": {"text": CORRECTED}},
            {**edit, "detail": {"text": AUTHORED}},
            {"kind": "undo", "undoes": "e3"},
        ),
    )
    projection = model.projected(state, 1)
    assert {
        entry["event"]["id"]: entry["stands"] for entry in projection["entries"]
    } == {"e1": True, "e2": True, "e3": False}
    assert projection["actions"] == ["e2"]
