"""How long each message waited and what each revision changed (`provenance.py`):
the facts a change since a version is attributed by."""

from model_folds import leaf_page, served_reading

from leaf.passages import SourceReading
from leaf.provenance import revision_changes
from leaf.structure import SourceDocument

AGENT = {"author": "agent", "agent": "Claude", "session": "s1"}


def test_each_message_waits_from_when_it_was_sent_until_answered_or_resolved():
    """A message waits from the revision live when it was sent until the one live when
    the agent answered it, two messages in a row one reply settles ending together; a
    resolution with no answer ends a wait too, at the newest revision the log names
    after it, so a revision it can't place before or after the resolution still counts
    as made while the message waited; and a message nothing has ended still waits."""
    documents = {
        revision: leaf_page("Plan", f'<p id="p">Version {revision}.</p>')
        for revision in range(1, 7)
    }
    events = [
        {"kind": "comment", "text": "Why ship with that?", "revision": 1},
        {
            "kind": "reply",
            "parent": "e1",
            "responds": "e1",
            "text": "Fixed it.",
            "revision": 3,
            **AGENT,
        },
        {"kind": "comment", "text": "And the rollout?", "revision": 3},
        {"kind": "reply", "parent": "e3", "text": "Past 5%, I mean.", "revision": 3},
        {
            "kind": "reply",
            "parent": "e3",
            "responds": "e4",
            "text": "It waits on crash-free sessions.",
            "revision": 4,
            **AGENT,
        },
        {"kind": "comment", "text": "Is the title right?", "revision": 4},
        {"kind": "resolve", "parent": "e6"},
        {"kind": "comment", "text": "Who signs off?", "revision": 5},
    ]
    waits = served_reading(documents, events)["browser"]["message_waits"]

    def wait(turn, thread, sent, until):
        return {
            "id": turn,
            "thread": thread,
            "message": turn,
            "from": sent,
            "until": until,
        }

    assert waits == [
        wait("e1", "e1", 1, 3),
        wait("e3", "e3", 3, 4),
        wait("e4", "e3", 3, 4),
        # The log names revision 5 first after the resolution.
        wait("e6", "e6", 4, 5),
        wait("e8", "e8", 5, None),
    ]


def test_a_gesture_sends_only_the_waits_it_ends():
    """A revision's messages are a fact about its past, so however many threads wait
    across however many revisions, resolving one sends the one wait it ends."""
    documents = {
        revision: leaf_page("Plan", f'<p id="p">Version {revision}.</p>')
        for revision in range(1, 33)
    }
    comments = [
        {"kind": "comment", "text": f"Question {k}?", "revision": 1} for k in range(32)
    ]
    held = served_reading(documents, comments)["browser"]["basis"]["key"]
    resolved = served_reading(
        documents, [*comments, {"kind": "resolve", "parent": "e1"}], held=held
    )
    assert [
        change["at"]
        for change in resolved["patch"]
        if change["at"][:2] == ["browser", "message_waits"]
    ] == [["browser", "message_waits"]]
    [change] = [
        change
        for change in resolved["patch"]
        if change["at"] == ["browser", "message_waits"]
    ]
    assert [name for name, _patch in change["changed"]] == ["e1"]


def test_a_revision_changes_the_units_whose_own_words_differ():
    """A unit is an element with an id, its words those directly in it, and `""` the
    words in none: an edit inside a nested element changes that element and not the one
    holding it, an edit to words in no inner element changes the one holding them, and
    an element that comes with no words changes too."""
    body = (
        '<section id="s"><h2 id="h">Head</h2><p>Loose {0}.</p>'
        '<p id="c">Child {1}.</p></section><p>Top {2}.</p>{3}'
    )
    versions = {
        1: body.format("one", "one", "one", ""),
        2: body.format("one", "two", "one", ""),
        3: body.format("two", "two", "one", ""),
        4: body.format("two", "two", "two", '<p id="n"></p>'),
    }
    readings = {
        revision: SourceReading(SourceDocument(leaf_page("Plan", html)), None)
        for revision, html in versions.items()
    }

    def address(revision):
        return f"/revisions/r{revision}.html"

    assert revision_changes(readings.__getitem__, readings, 1, address) == {
        "2": {"units": ["c"], "url": "/revisions/r2.html"},
        "3": {"units": ["s"], "url": "/revisions/r3.html"},
        "4": {"units": ["", "n"], "url": "/revisions/r4.html"},
    }
    # Only the revisions after the one compared with are read.
    assert list(revision_changes(readings.__getitem__, readings, 3, address)) == ["4"]
