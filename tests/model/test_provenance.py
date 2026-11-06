"""What each revision came after and what it changed (`provenance.py`): the facts a
change since a version is attributed by."""

from model_folds import leaf_page, served_reading

from leaf.passages import SourceReading
from leaf.provenance import revision_changes
from leaf.structure import SourceDocument

AGENT = {"author": "agent", "agent": "Claude", "session": "s1"}


def test_a_revision_comes_after_the_waiting_messages_answered_first_after_it():
    """Each revision comes after the messages sent before it and still waiting, of
    which it names those the agent answered first after it: two revisions made before
    one answer both name its message, two messages in a row one reply settles stand
    together, a revision made once every message was answered names none, and one made
    while a message is still owed names it."""
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
        {"kind": "comment", "text": "Who signs off?", "revision": 5},
    ]
    came_after = served_reading(documents, events)["browser"]["revision_messages"]

    def said(thread, *messages):
        return [{"thread": thread, "message": message} for message in messages]

    assert came_after == {
        "2": said("e1", "e1"),
        "3": said("e1", "e1"),
        "4": said("e3", "e3", "e4"),
        "6": said("e6", "e6"),
    }


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
    assert revision_changes(readings.__getitem__, readings, 1) == {
        "2": ["c"],
        "3": ["s"],
        "4": ["", "n"],
    }
    # Only the revisions after the one compared with are read.
    assert list(revision_changes(readings.__getitem__, readings, 3)) == ["4"]
