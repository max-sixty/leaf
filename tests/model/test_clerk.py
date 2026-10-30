"""Leaf's clerk: the question a turn-end fork is asked, the answer it must give, and
what Leaf writes from that answer and tells the agent at its next step."""

import json

import pytest
from interact_support import activity_reading, append_carried_log_record, declare_work

from leaf import clerk as clerk_model
from leaf import event_log as events_model
from leaf import hooks as hooks_model
from leaf.activity import declaration
from leaf.agent_state import cmd_page_state
from leaf.refusals import Refused

LINE = "Waiting on your pick of the retry limit"


def hook(capsys, event: str, prompt_id: str = "p1") -> str:
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": event, "session_id": "s1", "prompt_id": prompt_id},
    )
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def asked() -> dict:
    question = clerk_model.question("s1")
    assert question is not None
    return question


def reply(page, *, items=(), missed=()) -> str:
    return json.dumps(
        {
            "status": {str(page): LINE},
            "on_me": [
                {"page": str(page), "title": title, "kind": kind, "quote": title}
                for title, kind in items
            ],
            "missed": list(missed),
        }
    )


def test_the_clerk_writes_what_the_reply_left_and_the_next_step_hears_it(
    claimed, capsys
):
    """A fork's asks and calls land On me as to-dos marked as Leaf's, its line becomes
    the open page's status, and the next tool boundary tells the agent each thing Leaf
    wrote and each step it missed, once. A to-do the user drops is shown to the next
    fork as settled, so it isn't added again."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    question = asked()
    assert str(page) in question["prompt"]
    assert (
        "On me, what the page lists as waiting on the user:\n(none)"
        in question["prompt"]
    )

    wrote = clerk_model.take_answer(
        "s1",
        reply(
            page,
            items=[
                ("Choose the retry limit: 3 or 5?", "ask"),
                ("Keep the guard?", "call"),
            ],
            missed=[f"{page} is still open, though its work is done."],
        ),
        question["basis"],
    )["wrote"]
    assert [record["kind"] for record in wrote] == ["todo", "todo", "status"]
    on_me = [
        record
        for record in cmd_page_state(claimed)["obligations"]
        if record["source"]["kind"] == "todo"
    ]
    assert [
        (record["prompt"]["text"], record["source"].get("by")) for record in on_me
    ] == [
        ("Choose the retry limit: 3 or 5?", "leaf"),
        ("Keep the guard?", "leaf"),
    ]
    assert declaration(events_model.read_events(claimed)) == {
        "state": "waiting",
        "ts": wrote[-1]["ts"],
        "text": LINE,
    }
    reading = activity_reading(claimed)
    assert (reading["kind"], reading["detail"]) == ("listening", LINE)

    context = hook(capsys, "PostToolBatch")
    assert 'Leaf added "Choose the retry limit: 3 or 5?" to On me' in context
    assert "Leaf set the status on" in context
    assert "is still open, though its work is done." in context
    assert hook(capsys, "PostToolBatch") == ""

    # The same answer again finds the ask On me and the line shown.
    again = clerk_model.take_answer(
        "s1",
        reply(page, items=[("Choose the retry limit: 3 or 5?", "ask")]),
        question["basis"],
    )
    assert again["wrote"] == []

    append_carried_log_record(
        claimed,
        {
            "kind": "todo_end",
            "author": "user",
            "todo": wrote[1]["id"],
            "outcome": "dropped",
        },
    )
    assert (
        "don't add these again:\n- to-do: Keep the guard? (dropped)"
        in asked()["prompt"]
    )


def test_the_clerk_drops_an_answer_once_another_turn_opened(claimed, capsys):
    """The user spoke since the fork read the turn, so what it found may be what they
    are answering now."""
    hook(capsys, "UserPromptSubmit")
    question = asked()
    hook(capsys, "UserPromptSubmit", "p2")
    before = len(events_model.read_events(claimed))
    dropped = clerk_model.take_answer(
        "s1", reply(claimed.resolve(), items=[("Pick one?", "ask")]), question["basis"]
    )
    assert "dropped" in dropped
    assert len(events_model.read_events(claimed)) == before
    assert clerk_model.queued("s1") == []


def test_the_clerk_leaves_a_line_the_agent_wrote_on_work_in_hand(claimed, capsys):
    """A start holding an item says what the agent does; the fork's line doesn't
    replace it or put the work down."""
    hook(capsys, "UserPromptSubmit")
    declare_work(claimed, "running the suite", session="s1")
    question = asked()
    wrote = clerk_model.take_answer("s1", reply(claimed.resolve()), question["basis"])
    assert wrote["wrote"] == []
    assert activity_reading(claimed)["detail"] == "running the suite"


@pytest.mark.parametrize(
    "text",
    [
        "Nothing to report.",
        '{"status": {}, "on_me": [], "missed": [], "extra": 1}',
        '{"status": {}, "on_me": [{"page": "p", "title": "x", "kind": "maybe", "quote": ""}], "missed": []}',
    ],
)
def test_an_answer_outside_the_schema_writes_nothing(text):
    with pytest.raises(Refused):
        clerk_model.read_answer(text)


def test_a_long_title_is_cut_at_a_word_to_fit_a_to_do():
    """A model can't count characters, so a title past a to-do's limit is cut rather
    than refusing the answer and the asks it found."""
    words = "Choose " + "the retry limit " * 8 + "for the suite?"
    title = clerk_model._title(words)
    assert len(title) <= clerk_model.TITLE_LIMIT
    assert title.endswith("…") and words.startswith(title[:-1] + " ")


def test_a_fenced_answer_is_read():
    assert clerk_model.read_answer(
        '```json\n{"status": {}, "on_me": [], "missed": []}\n```'
    )
