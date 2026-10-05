"""Tasks hold work the agent owes until it ends them, and the two queues say what is
on the user and what is on the agent."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    append_command,
    publish,
    state_json,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.served_state.page import full_state


def leaf(*args):
    return CliRunner().invoke(cli_model.cli, [str(arg) for arg in args])


def written(result) -> dict:
    assert result.exit_code == 0, result.output
    return json.loads(result.output.splitlines()[-1])


def kinds(items) -> list:
    return [(item["kind"], item["id"]) for item in items]


def test_a_task_holds_its_thread_on_the_agent_past_reply_and_resolve(page_dir):
    """The reply that answers a comment settles it, and resolving the thread closes
    it, but a task the agent opened on it stays on the agent's queue until the agent
    ends it: the work a reply promised is no longer owed nowhere."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Make the banner quieter.",
        },
    )
    state = state_json(page_dir)
    assert kinds(state["queues"]["on_agent"]) == [("answer", comment["id"])]

    task = written(
        leaf("task", "open", page_dir, comment["id"], "Rebuild the banner quieter")
    )
    assert task["subject"] == {"kind": "thread", "id": comment["id"]}
    written(
        leaf(
            "thread",
            "reply",
            page_dir,
            "--for",
            comment["id"],
            "--text",
            "Building it now.",
        )
    )
    state = state_json(page_dir)
    assert kinds(state["queues"]["on_agent"]) == [("task", task["id"])]
    assert state["queues"]["on_you"] == []
    assert state["threads"][0]["attention"] == {
        "kind": "waiting",
        "reason": "task",
        "workflow": None,
        "task": {"id": task["id"], "title": "Rebuild the banner quieter"},
    }
    assert [item["id"] for item in state["tasks"]] == [task["id"]]

    append_command(
        page_dir,
        {"kind": "resolve", "author": "user", "parent": comment["id"]},
    )
    # Resolving closes the thread for the user; the task stays the agent's, and the
    # banner names it from the served `tasks`.
    state = state_json(page_dir)
    assert state["threads"][0]["attention"] is None
    assert kinds(state["queues"]["on_agent"]) == [("task", task["id"])]
    served = full_state(page_dir, events_model.read_events(page_dir))
    assert [item["title"] for item in served["browser"]["tasks"]] == [
        "Rebuild the banner quieter"
    ]
    thread = leaf("page", "state", page_dir, comment["id"])
    assert thread.exit_code == 0, thread.output
    assert [item["id"] for item in json.loads(thread.output)["tasks"]] == [task["id"]]

    end = written(leaf("task", "end", page_dir, task["id"], "done", "version 2"))
    assert (end["task"], end["outcome"], end["detail"]) == (
        task["id"],
        "done",
        "version 2",
    )
    state = state_json(page_dir)
    assert state["queues"]["on_agent"] == []
    assert state["tasks"] == []
    # The browser is served the ended task beside the open ones, for the Queue panel's
    # Done list, with its outcome.
    served = full_state(page_dir, events_model.read_events(page_dir))
    assert served["browser"]["tasks"] == []
    [ended] = served["browser"]["ended_tasks"]
    assert (ended["id"], ended["state"], ended["outcome"]["detail"]) == (
        task["id"],
        "done",
        "version 2",
    )


def test_the_door_refuses_a_task_off_the_page_and_an_outcome_twice(page_dir):
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Hm."},
    )
    missing = leaf("task", "open", page_dir, "no-such-thing", "Anything")
    assert missing.exit_code != 0
    assert "names no thread" in missing.output
    unknown = leaf("task", "end", page_dir, "no-such-task", "done")
    assert unknown.exit_code != 0
    assert "unknown task" in unknown.output

    task = written(leaf("task", "open", page_dir, comment["id"], "Look into it"))
    written(leaf("task", "end", page_dir, task["id"], "dropped", "not needed"))
    again = leaf("task", "end", page_dir, task["id"], "done")
    assert again.exit_code != 0
    assert "already ended (dropped)" in again.output

    append_command(
        page_dir,
        {"kind": "resolve", "author": "user", "parent": comment["id"]},
    )
    resolved = leaf("task", "open", page_dir, comment["id"], "After the close")
    assert resolved.exit_code != 0
    assert "is resolved; reopen it" in resolved.output

    before = events_model.read_events(page_dir)
    for invalid in (
        {"author": "user"},
        {"title": "Two\nlines"},
        {"title": "x" * 81},
        {"subject": {"kind": "thread", "id": "no-such-thread"}},
        {"subject": {"kind": "widget", "id": "s-1"}},
    ):
        with pytest.raises(events_model.EventRefused):
            append_command(
                page_dir,
                {
                    "kind": "task",
                    "author": "agent",
                    "agent": "Claude",
                    "session": "task-test",
                    "subject": {"kind": "thread", "id": comment["id"]},
                    "title": "Fine",
                    **invalid,
                },
            )
    assert events_model.read_events(page_dir) == before


def test_on_you_lists_open_asks_and_questions_left_in_prose(page_dir):
    """An Ask is on the user, and so is a thread whose agent turn asks in prose
    (`--awaits`); answering the prose question hands the thread to the agent."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which colour?"},
    )
    written(
        leaf(
            "thread",
            "reply",
            page_dir,
            "--for",
            comment["id"],
            "--text",
            "Warm or cool?",
            "--awaits",
        )
    )
    state = state_json(page_dir)
    asks = [("ask", ask["id"]) for ask in state["asks"]]
    assert kinds(state["queues"]["on_you"]) == asks + [("question", comment["id"])]
    assert state["queues"]["on_agent"] == []

    warm = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": comment["id"],
            "text": "Warm.",
        },
    )
    state = state_json(page_dir)
    assert kinds(state["queues"]["on_you"]) == asks
    assert [item["kind"] for item in state["queues"]["on_agent"]] == ["answer"]

    # Answered, then claimed again: work the agent says is under way, with nothing
    # owed, stays on its side until the claim's next reply.
    written(
        leaf("thread", "reply", page_dir, "--for", warm["id"], "--text", "Warm it is.")
    )
    claimed = leaf("status", page_dir, "working", "Recolouring", "--on", comment["id"])
    assert claimed.exit_code == 0, claimed.output
    state = state_json(page_dir)
    assert [item["kind"] for item in state["queues"]["on_agent"]] == ["work"]
    assert state["queues"]["on_agent"][0]["detail"] == "Recolouring"


def test_a_thread_is_on_you_once_however_many_moves_it_holds_for_you(page_dir):
    """A thread whose reply failed is one item on the user, named by the thread, and a
    question the agent then leaves in it makes it that question rather than a second
    item: `a` stops at a thread once."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Retitle it."},
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "failure": "turn_failed",
            "text": "No answer is coming.",
        },
    )
    state = state_json(page_dir)
    asks = [("ask", ask["id"]) for ask in state["asks"]]
    assert [item["next_actor"] for item in state["workflows"]] == ["user"]
    assert kinds(state["queues"]["on_you"]) == asks + [("recovery", comment["id"])]

    written(
        leaf(
            "thread",
            "reply",
            page_dir,
            comment["id"],
            "--text",
            "Short or long title?",
            "--awaits",
        )
    )
    state = state_json(page_dir)
    assert [item["next_actor"] for item in state["workflows"]] == ["user"]
    assert kinds(state["queues"]["on_you"]) == asks + [("question", comment["id"])]
    assert state["queues"]["on_agent"] == []
