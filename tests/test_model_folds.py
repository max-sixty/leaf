"""Folds whose whole subject is the reading, not what a widget draws with it.

Each test here states one document and one log and asks what the browser would
be handed. `model_folds` owns the arrangement; `tests/CLAUDE.md`'s rule that an
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

# One draft, three revisions of it. The reader rewrote the authored words in r1;
# r2 rewrote them again and said so; r3 is an unrelated edit on r2's words.
DRAFT = """<h1 id="t">Journey</h1>
<lf-draft id="draft-ops"{attrs}><pre>
    {text}
</pre></lf-draft>"""
AUTHORED = "Run the migration before deploying."
READER_EDIT = "Run the migration before deploying. It takes about a minute."
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
                "conversation": "e1",
                "from": "e1",
                "through": "e2",
                "text": "First exchange.",
            },
            {
                "kind": "summary",
                **identity,
                "conversation": "e1",
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
                "conversation": "e1",
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


def test_a_decision_on_any_message_settles_the_thread_it_belongs_to():
    """A reader resolves the message in front of them, which is rarely the first.

    `resolve` names a parent, and the parent a reader has under the pointer is
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
    assert not resolved["awaits_agent"]


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
            "detail": {"text": READER_EDIT},
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
