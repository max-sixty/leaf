"""How long each of the user's messages waited, as places in the log, and where each
revision stands among them (`provenance.py`, `revisioning.py`): what a version says
it was saved after."""

from click.testing import CliRunner
from interact_support import append_command, response_reference
from model_folds import leaf_page, served_reading

from leaf import cli as cli_model
from leaf import event_log as event_log_model
from leaf.revisioning import activate_source
from model.interact_contract.test_thread_resolution import (
    ASKED,
    CLOSED,
    PICKED,
    SETTLED,
)

AGENT = {"author": "agent", "agent": "Claude", "session": "s1"}
PAGE = {
    revision: leaf_page("Plan", f'<p id="p">Version {revision}.</p>')
    for revision in (1, 2)
}


def wait(turn, start, until, *, message=None, thread=None, words):
    message = message or turn
    return {
        "id": f"{turn}:{start}",
        "thread": thread or message,
        "message": message,
        "words": words,
        "from": start,
        "until": until,
    }


def test_each_message_waits_from_its_place_in_the_log_until_answered_or_closed():
    """A message waits from its own place in the log until the agent's answer to it,
    and a rewrite of it waits as a turn of its own with the words it then had, one
    answer ending both. A resolution ends a wait where it stands, and the undo that
    takes it back starts a new one at the undo rather than reopening the old, so a
    revision saved while the thread stood resolved came after nothing it held."""
    events = [
        {"kind": "comment", "text": "Make it **blue**\nfor the header", "revision": 1},
        {"kind": "edit", "message": "e1", "text": "Actually make it red"},
        {"kind": "reply", "parent": "e1", "responds": "e2", "text": "Red.", **AGENT},
        {"kind": "comment", "text": "Why ship with that?", "revision": 1},
        {"kind": "resolve", "parent": "e4"},
        {"kind": "undo", "undoes": "e5"},
    ]
    assert served_reading(PAGE, events)["browser"]["message_waits"] == [
        wait("e1", 1, 3, words="Make it blue"),
        wait("e2", 2, 3, message="e1", words="Actually make it red"),
        wait("e4", 4, 5, words="Why ship with that?"),
        wait("e4", 6, None, words="Why ship with that?"),
    ]


def test_a_wait_ends_while_anything_still_closes_its_thread():
    """Accepting a suggestion answers the thread that asked for it as a resolution
    would, so the thread's message stops waiting there (`events.build_threads`).
    Taking the accept back while the user's own resolution stands leaves the thread
    closed, and taking back a reopening closes it again where the undo stands."""

    def waits(*events):
        return served_reading(SETTLED, [ASKED, *events])["browser"]["message_waits"]

    asked = "cameras are flaky"
    assert waits(PICKED) == [wait("e1", 1, 2, words=asked)]
    assert waits(PICKED, CLOSED, {"kind": "undo", "undoes": "e2"}) == [
        wait("e1", 1, 2, words=asked)
    ]
    assert waits(
        CLOSED, {"kind": "unresolve", "parent": "e1"}, {"kind": "undo", "undoes": "e3"}
    ) == [wait("e1", 1, 2, words=asked), wait("e1", 3, 4, words=asked)]


def test_a_revision_takes_its_place_in_the_log_from_the_event_naming_its_bundle(
    page_dir,
):
    """A save a read activates appends an `activation` naming its bundle, after every
    event before it, however old a revision a message names; a save a reply publishes
    takes the reply's place, the end of the wait it answers."""
    index = page_dir / "index.html"
    said = ["Ship dark."]

    def save(words):
        index.write_text(index.read_text().replace(said[-1], words, 1))
        said.append(words)

    def place(revision):
        [named] = [
            event
            for event in event_log_model.read_events(page_dir)
            if event.get("publication") and event["revision"] == revision
        ]
        return named["seq"]

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
    assert place(unread) < asked["seq"]
    save("Ship dark, behind the rollout flag.")
    assert place(activate_source(page_dir).revision) > asked["seq"]

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
    assert place(reply["revision"]) == reply["seq"]


def test_a_gesture_sends_only_the_waits_it_ends():
    """Waits are places in the log no later event moves, so however many threads wait
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
    [change] = [
        change
        for change in resolved["patch"]
        if change["at"][:2] == ["browser", "message_waits"]
    ]
    assert change["at"] == ["browser", "message_waits"]
    assert [name for name, _patch in change["changed"]] == ["e1:1"]
