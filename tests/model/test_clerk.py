"""Leaf's clerk: the question a turn-end fork is asked, the answer it must give, and
what Leaf writes from that answer and tells the agent at its next step."""

import json

import pytest
from interact_support import append_carried_log_record

from leaf import clerk as clerk_model
from leaf import event_log as events_model
from leaf import hooks as hooks_model
from leaf.agent_state import cmd_page_state
from leaf.refusals import Refused


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


def reply(page, *titles: str) -> str:
    return json.dumps(
        {
            "asks": [
                {"page": str(page), "title": title, "quote": title} for title in titles
            ]
        }
    )


def test_the_clerk_adds_what_the_reply_left_and_the_next_step_hears_it(claimed, capsys):
    """Each ask the fork names lands On me as the agent's own to-do, with nothing
    marking the fork, and the next tool boundary tells the agent each one, once. An
    ask On me already holds isn't added again, and one ended is shown to the next fork
    as settled."""
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
        reply(page, "Choose the retry limit: 3 or 5?", "Open a PR for this branch?"),
        question["basis"],
    )["wrote"]
    on_me = [
        record["prompt"]["text"]
        for record in cmd_page_state(claimed)["obligations"]
        if record["source"]["kind"] == "todo"
    ]
    assert on_me == ["Choose the retry limit: 3 or 5?", "Open a PR for this branch?"]
    assert {(record["author"], record["session"]) for record in wrote} == {
        ("agent", "s1")
    }
    assert not any("by" in record for record in wrote)

    context = hook(capsys, "PostToolBatch")
    assert f'Leaf put "Choose the retry limit: 3 or 5?" On me on {page}' in context
    assert f"leaf task end {page} {wrote[1]['id']} dropped" in context
    assert hook(capsys, "PostToolBatch") == ""

    again = clerk_model.take_answer(
        "s1", reply(page, "Choose the retry limit: 3 or 5?"), question["basis"]
    )
    assert again["wrote"] == []

    # The agent, keeping its say over the record, ends one as not the user's.
    append_carried_log_record(
        claimed,
        {
            "kind": "todo_end",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "todo": wrote[1]["id"],
            "outcome": "dropped",
        },
    )
    assert (
        "don't add these again:\n- Open a PR for this branch? (dropped)"
        in (asked()["prompt"])
    )


def test_the_clerk_drops_an_answer_once_another_turn_opened(claimed, capsys):
    """The user spoke since the fork read the turn, so what it found may be what they
    are answering now."""
    hook(capsys, "UserPromptSubmit")
    question = asked()
    hook(capsys, "UserPromptSubmit", "p2")
    before = len(events_model.read_events(claimed))
    dropped = clerk_model.take_answer(
        "s1", reply(claimed.resolve(), "Pick one?"), question["basis"]
    )
    assert "dropped" in dropped
    assert len(events_model.read_events(claimed)) == before
    assert clerk_model.queued("s1") == []


@pytest.mark.parametrize(
    "text",
    [
        "Nothing to report.",
        '{"asks": [], "extra": 1}',
        '{"asks": [{"page": "p", "title": "x"}]}',
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
    assert clerk_model.read_answer('```json\n{"asks": []}\n```') == {"asks": []}
