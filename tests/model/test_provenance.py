"""How long each message waited and what each revision changed (`provenance.py`):
the facts a change since a version is attributed by."""

from click.testing import CliRunner
from interact_support import append_command, response_reference
from model_folds import leaf_page, served_reading

from leaf import cli as cli_model
from leaf import event_log as event_log_model
from leaf.events import build_threads, taken_back
from leaf.passages import SourceReading
from leaf.provenance import message_waits, revision_changes
from leaf.revision_artifact import read_revision
from leaf.revisioning import activate_source
from leaf.structure import SourceDocument

AGENT = {"author": "agent", "agent": "Claude", "session": "s1"}


def test_each_message_waits_from_its_place_in_the_log_until_answered_or_resolved():
    """A message waits from its own seq until the agent's answer to it, two messages in
    a row one reply settles ending together; a resolution with no answer ends a wait
    at the resolution; and a message nothing has ended still waits."""
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

    def wait(turn, thread, until):
        return {
            "id": turn,
            "thread": thread,
            "message": turn,
            "from": int(turn[1:]),
            "until": until,
        }

    assert waits == [
        wait("e1", "e1", 2),
        wait("e3", "e3", 5),
        wait("e4", "e3", 5),
        wait("e6", "e6", 7),
        wait("e8", "e8", None),
    ]


def test_a_revision_records_where_in_the_log_it_went_live(page_dir):
    """Each revision records the seq of the last event before it went live, which
    orders it against the log where no event names it: a save a read activates goes
    after every event before it, so a message from a tab still showing an older
    revision waits only across revisions activated after it; and a save a reply
    publishes goes before the reply, which comes with it."""
    index = page_dir / "index.html"
    said = ["Ship dark."]

    def save(words):
        index.write_text(index.read_text().replace(said[-1], words, 1))
        said.append(words)

    def after(revision):
        return read_revision(page_dir, revision).activated_after

    first = activate_source(page_dir).revision
    save("Ship dark, behind a flag.")
    unread = activate_source(page_dir).revision
    asked = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": first,
            "text": "Which flag?",
            "anchor": {"section": "plan"},
        },
    )
    assert after(unread) < asked["seq"]
    save("Ship dark, behind the rollout flag.")
    seen = activate_source(page_dir).revision
    assert after(seen) == asked["seq"]
    events = event_log_model.read_events(page_dir)
    [waited] = message_waits(events, build_threads(events, {}), taken_back(events))
    assert waited["from"] <= after(seen) and waited["from"] > after(unread)

    save("Ship dark, behind the rollout flag, off by default.")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, asked),
            "--text",
            "The rollout flag, off by default.",
        ],
        catch_exceptions=False,
    )
    assert replied.exit_code == 0, replied.output
    [reply] = [
        event
        for event in event_log_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert "publication" in reply
    assert after(reply["revision"]) == reply["seq"] - 1


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

    def place(revision):
        return revision * 10

    assert revision_changes(readings.__getitem__, readings, 1, place) == {
        "2": {"units": ["c"], "after": 20},
        "3": {"units": ["s"], "after": 30},
        "4": {"units": ["", "n"], "after": 40},
    }
    # Only the revisions after the one compared with are read.
    assert list(revision_changes(readings.__getitem__, readings, 3, place)) == ["4"]
