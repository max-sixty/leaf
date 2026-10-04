"""Tasks hold work the agent owes until it ends them, a start takes a move or task in
hand, and the two queues say what is on the user and what is on the agent."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    append_carried_log_record,
    append_command,
    publish,
    stamp,
    state_json,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import tasks as tasks_model
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
        "task": {
            "id": task["id"],
            "title": "Rebuild the banner quieter",
            "running": None,
        },
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


def test_the_door_refuses_a_task_off_the_page_and_an_outcome_twice(page_dir):
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Hm."},
    )
    missing = leaf("task", "open", page_dir, "no-such-thing", "Anything")
    assert missing.exit_code != 0
    assert "names no thread or widget" in missing.output
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
    assert [item["id"] for item in state["queues"]["on_agent"]] == [warm["id"]]


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


def test_working_names_a_move_until_its_answer_and_a_task_until_its_end(page_dir):
    """`task start` takes an item on the agent's queue in hand with the banner's line:
    the user's move, by its event id, reads Working until the reply that answers it,
    and a task runs until it ends. An id that is neither is refused at the door."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Tighten it."},
    )
    refused = leaf("task", "start", page_dir, "no-such-move", "Reading it")
    assert refused.exit_code != 0
    assert "neither an open task nor a move you owe" in refused.output

    start = written(
        leaf("task", "start", page_dir, comment["id"], "Tightening the plan section")
    )
    assert (start["kind"], start["item"]) == ("start", comment["id"])
    state = state_json(page_dir)
    [workflow] = state["workflows"]
    assert (workflow["stage"], workflow["detail"]) == (
        "working",
        "Tightening the plan section",
    )
    assert state["activity"]["kind"] == "working"
    assert state["activity"]["detail"] == "Tightening the plan section"

    # The reply that answers the move ends its start: nothing is in hand.
    written(
        leaf("thread", "reply", page_dir, "--for", comment["id"], "--text", "Done.")
    )
    state = state_json(page_dir)
    assert state["workflows"] == []
    assert state["activity"]["kind"] != "working"
    again = leaf("task", "start", page_dir, comment["id"], "More")
    assert again.exit_code != 0

    # A task the agent opens on the page, for work no move asked for, runs under its
    # start's line until the task ends; the banner shows that line.
    task = written(leaf("task", "open", page_dir, "page", "Add a glossary"))
    assert task["subject"] == {"kind": "page"}
    written(leaf("task", "start", page_dir, task["id"], "Drafting the glossary"))
    state = state_json(page_dir)
    [served] = state["tasks"]
    assert served["running"]["text"] == "Drafting the glossary"
    assert state["activity"]["detail"] == "Drafting the glossary"
    [item] = state["queues"]["on_agent"]
    assert (item["kind"], item["subject"]) == ("task", {"kind": "page"})
    written(leaf("task", "end", page_dir, task["id"], "done", "the glossary section"))
    state = state_json(page_dir)
    assert state["tasks"] == []
    assert state["activity"]["kind"] != "working"


def test_a_thread_task_runs_under_its_start_line(page_dir):
    """A started task on a thread reads Working with its line in the thread's
    attention, and Task open with its title once nothing runs on it."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Rebuild it."},
    )
    task = written(leaf("task", "open", page_dir, comment["id"], "Rebuild the chart"))
    written(
        leaf("thread", "reply", page_dir, "--for", comment["id"], "--text", "On it.")
    )
    written(leaf("task", "start", page_dir, task["id"], "Waiting on the build"))
    [thread] = state_json(page_dir)["threads"]
    assert thread["attention"]["task"] == {
        "id": task["id"],
        "title": "Rebuild the chart",
        "running": "Waiting on the build",
    }


WORK_PAGE = PAGE.replace(
    '<lf-diagram id="flow">',
    '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
    '  <lf-card id="rollout-card"><strong>Ship the rollout</strong> '
    "Check the fallback before cutover.</lf-card>\n"
    '</lf-column></lf-board>\n<lf-diagram id="flow">',
)


def test_a_widget_task_needs_a_seat_and_a_completing_stamp_ends_it(page_dir):
    """A task on a page widget needs a widget that declares `x-work` or holds an
    unsettled move. A version that drops its widget without completing it is refused;
    `page stamp --completes` ends it done, citing that version."""
    (page_dir / "index.html").write_text(WORK_PAGE)
    publish(page_dir)
    no_seat = leaf("task", "open", page_dir, "flow", "Redraw the graph")
    assert no_seat.exit_code != 0
    assert "has no work seat" in no_seat.output

    task = written(leaf("task", "open", page_dir, "rollout-card", "Check the rollout"))
    assert task["subject"] == {"kind": "widget", "id": "rollout-card"}
    assert task["revision"] == 1
    written(leaf("task", "start", page_dir, task["id"], "Checking the fallback"))
    [served] = state_json(page_dir)["tasks"]
    assert served["running"]["text"] == "Checking the fallback"

    # An unrelated version leaves the task standing; one that drops its card is
    # refused unless it completes it.
    (page_dir / "index.html").write_text(
        WORK_PAGE.replace("<title>t</title>", "<title>t · v2</title>")
    )
    assert stamp(page_dir, "Elsewhere").exit_code == 0
    assert [item["id"] for item in state_json(page_dir)["tasks"]] == [task["id"]]
    (page_dir / "index.html").write_text(PAGE)
    dropped = stamp(page_dir, "Card gone")
    assert dropped.exit_code != 0
    assert "would remove the target of the open task on 'rollout-card'" in (
        dropped.output
    )
    (page_dir / "index.html").write_text(
        WORK_PAGE.replace("<title>t</title>", "<title>t · v3</title>")
    )
    done = stamp(page_dir, "Rollout checked", completes=("rollout-card",))
    assert done.exit_code == 0, done.output
    note = events_model.read_events(page_dir)[-1]
    assert note["settles"] == [{"kind": "task", "id": task["id"]}]
    assert state_json(page_dir)["tasks"] == []
    [ended] = [
        item for item in tasks_model.canonical_tasks(events_model.read_events(page_dir))
    ]
    assert (ended["state"], ended["outcome"]["detail"]) == ("done", "v3")
    (page_dir / "index.html").write_text(
        WORK_PAGE.replace("<title>t</title>", "<title>t · v4</title>")
    )
    again = stamp(page_dir, "Again", completes=("rollout-card",))
    assert again.exit_code != 0
    assert "no open task on 'rollout-card'" in again.output


def test_a_start_reopens_a_page_its_agent_closed(page_dir):
    """`idle` says the agent is done with the page, and every carrier stands down for
    it; taking work in hand there reopens the page rather than working under Closed."""
    publish(page_dir)
    written(leaf("status", page_dir, "idle"))
    assert state_json(page_dir)["activity"]["kind"] == "closed"
    task = written(leaf("task", "open", page_dir, "page", "Add a glossary"))
    written(leaf("task", "start", page_dir, task["id"], "Drafting the glossary"))
    state = state_json(page_dir)
    assert state["status"]["state"] == "waiting"
    assert (state["activity"]["kind"], state["activity"]["detail"]) == (
        "working",
        "Drafting the glossary",
    )
