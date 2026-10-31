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


def reply(page, *titles: str, passage: str = "") -> str:
    return json.dumps(
        {
            "asks": [
                {
                    "page": str(page),
                    "kind": "question",
                    "title": title,
                    "text": f"{title}: which would you like?",
                    "passage": passage,
                    "quote": title,
                }
                for title in titles
            ]
        }
    )


def test_the_clerk_asks_what_the_reply_left_and_the_next_step_hears_it(claimed, capsys):
    """Each ask the fork names opens a thread of its own on the page, the agent's
    message asking the whole question with nothing marking the fork, and lands On me
    until the user answers; the next tool boundary tells the agent each one and its
    words, once. A question the agent already asked isn't asked again, and a question
    the agent withdrew stays withdrawn: the next fork is shown it as settled, and Leaf
    doesn't ask it again."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    question = asked()
    assert str(page) in question["prompt"]
    assert (
        "On me, what the page lists as waiting on the user:\n(none)"
        in question["prompt"]
    )

    # A thread the agent opened to tell rather than ask holds no ask, whatever its
    # title.
    append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "revision": 1,
            "title": "The retry limit",
            "text": "The suite retries each flaky test.",
        },
    )
    wrote = clerk_model.take_answer(
        "s1", reply(page, "The retry limit", "A PR for this branch"), question["basis"]
    )["wrote"]
    assert [
        (record["kind"], record["title"], record["text"], record["obligation"])
        for record in wrote
    ] == [
        ("comment", "The retry limit", "The retry limit: which would you like?", True),
        (
            "comment",
            "A PR for this branch",
            "A PR for this branch: which would you like?",
            True,
        ),
    ]
    assert {(record["author"], record["session"]) for record in wrote} == {
        ("agent", "s1")
    }
    assert not any("anchor" in record or "by" in record for record in wrote)
    on_me = cmd_page_state(claimed)["queues"]["on_user"]
    assert [row["id"] for row in on_me] == [
        f"message:{record['id']}" for record in wrote
    ]

    context = hook(capsys, "PostToolBatch")
    assert (
        f'Leaf asked the user "The retry limit" On me, in a new thread on {page} as a '
        "whole," in context
    )
    assert "> The retry limit: which would you like?" in context
    assert f"leaf task end {page} message:{wrote[1]['id']} dropped" in context
    assert hook(capsys, "PostToolBatch") == ""

    again = clerk_model.take_answer(
        "s1", reply(page, "The retry limit"), question["basis"]
    )
    assert again["wrote"] == []

    # The agent, keeping its say over the record, withdraws one as not the user's.
    append_carried_log_record(
        claimed,
        {
            "kind": "todo_end",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "todo": f"message:{wrote[1]['id']}",
            "outcome": "dropped",
        },
    )
    question = asked()
    assert (
        "don't ask these again:\n- A PR for this branch: which would you like? (dropped)"
        in question["prompt"]
    )
    reasked = clerk_model.take_answer(
        "s1", reply(page, "A PR for this branch"), question["basis"]
    )
    assert reasked["wrote"] == []


def test_an_ask_about_a_passage_stands_on_it_or_else_on_the_page(claimed, capsys):
    """An ask about one passage opens its thread on the page's words the fork names,
    as `thread create --quote` would. Words the page doesn't show leave the ask on the
    page as a whole rather than unasked, since the fork has no next attempt, and the
    agent hears where each went."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    basis = asked()["basis"]
    answer = json.loads(reply(page, "Where the cutoff lives", "The retry budget"))
    answer["asks"][0]["passage"] = "The cutoff lives in"
    answer["asks"][1]["passage"] = "the retry budget"
    wrote = clerk_model.take_answer("s1", json.dumps(answer), basis)["wrote"]
    assert [record.get("anchor", {}).get("quote") for record in wrote] == [
        "The cutoff lives in",
        None,
    ]
    assert all(record["obligation"] for record in wrote)
    context = hook(capsys, "PostToolBatch")
    assert f'in a new thread on the words "The cutoff lives in" in {page},' in context
    assert f'"The retry budget" On me, in a new thread on {page} as a whole,' in context


def test_a_step_goes_on_me_as_a_todo_titled_as_the_action(claimed, capsys):
    """A step the user takes and confirms with Done goes On me as the agent's to-do on
    the user, on the element holding the passage it concerns or else on the page, and
    the agent hears its id. A step the agent already put on the user isn't put there
    again, open or ended."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    basis = asked()["basis"]

    def step(title, passage=""):
        return {
            "page": str(page),
            "kind": "step",
            "title": title,
            "text": "",
            "passage": passage,
            "quote": title,
        }

    answer = {
        "asks": [
            step("Run the backfill job on staging", "The cutoff lives in"),
            step("Run /reload-plugins in this Claude session"),
        ]
    }
    wrote = clerk_model.take_answer("s1", json.dumps(answer), basis)["wrote"]
    assert [
        (record["kind"], record["owner"], record["subject"]) for record in wrote
    ] == [
        ("todo", "user", {"kind": "element", "id": "plan"}),
        ("todo", "user", {"kind": "page"}),
    ]
    assert {(record["author"], record["session"]) for record in wrote} == {
        ("agent", "s1")
    }
    on_me = cmd_page_state(claimed)["queues"]["on_user"]
    assert [row["id"] for row in on_me] == [record["id"] for record in wrote]
    context = hook(capsys, "PostToolBatch")
    assert (
        f'Leaf put the step "Run /reload-plugins in this Claude session" On me as your '
        f"to-do {wrote[1]['id']} on the user, on {page} as a whole." in context
    )
    assert f"leaf task end {page} {wrote[0]['id']} dropped" in context

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
    again = clerk_model.take_answer("s1", json.dumps(answer), asked()["basis"])
    assert again["wrote"] == []


def test_a_message_naming_missing_media_writes_none_of_the_answer(claimed):
    """A message is checked as `thread create` checks one, and every message before
    the first is written, so a refused one leaves the page as the fork found it."""
    page = claimed.resolve()
    answer = json.loads(reply(page, "The retry limit", "The chart"))
    answer["asks"][1]["text"] = "Does ![the chart](/media/0123456789abcdef.png) read?"
    before = len(events_model.read_events(claimed))
    with pytest.raises(Refused):
        clerk_model.take_answer("s1", json.dumps(answer), clerk_model.basis("s1"))
    assert len(events_model.read_events(claimed)) == before


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
        '{"asks": [{"page": "p", "kind": "question", "title": "x", "text": "", '
        '"passage": "", "quote": ""}]}',
    ],
)
def test_an_answer_outside_the_schema_writes_nothing(text):
    with pytest.raises(Refused):
        clerk_model.read_answer(text)


def test_a_long_title_is_cut_at_a_word_to_fit_a_thread():
    """A model can't count characters, so a title past a thread's limit is cut rather
    than refusing the answer and the asks it found."""
    words = "Choose " + "the retry limit " * 8 + "for the suite?"
    title = clerk_model._title(words)
    assert len(title) <= clerk_model.TITLE_LIMIT
    assert title.endswith("…") and words.startswith(title[:-1] + " ")


def test_a_fenced_answer_is_read():
    assert clerk_model.read_answer('```json\n{"asks": []}\n```') == {"asks": []}
