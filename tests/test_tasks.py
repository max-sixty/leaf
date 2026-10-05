"""Tasks hold work the agent owes until it ends them, a start takes a move or task in
hand, and the two queues say what is on the user and what is on the agent."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    append_carried_log_record,
    append_command,
    asks_on_you,
    publish,
    stamp,
    state_json,
)
from leaf import cli as cli_model
from leaf import event_endpoint as endpoint_model
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
            "line": None,
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
    assert "names no thread, widget or element" in missing.output
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
                    "owner": "agent",
                    "agent": "Claude",
                    "session": "task-test",
                    "subject": {"kind": "thread", "id": comment["id"]},
                    "title": "Fine",
                    **invalid,
                },
            )
    assert events_model.read_events(page_dir) == before


def test_on_you_lists_open_asks_and_questions_left_in_prose(page_dir):
    """An Ask is a task on the user, and so is an agent turn in a thread that asks in
    prose (`--awaits`), under that turn's id; answering the prose question ends it
    and hands the thread to the agent."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which colour?"},
    )
    question = written(
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
    asks = [("task", ask["id"]) for ask in asks_on_you(state)]
    assert kinds(state["queues"]["on_you"]) == asks + [("task", question["id"])]
    assert state["queues"]["on_agent"] == []
    [asked] = [task for task in state["tasks"] if task["id"] == question["id"]]
    assert (asked["owner"], asked["subject"], asked["ask"]) == (
        "user",
        {"kind": "thread", "id": comment["id"]},
        None,
    )

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
    assert question["id"] not in [task["id"] for task in state["tasks"]]
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
    asks = [("task", ask["id"]) for ask in asks_on_you(state)]
    assert [item["next_actor"] for item in state["workflows"]] == ["user"]
    assert kinds(state["queues"]["on_you"]) == asks + [("recovery", comment["id"])]

    question = written(
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
    assert kinds(state["queues"]["on_you"]) == asks + [("task", question["id"])]
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
    assert "neither an open task of yours nor a move you owe" in refused.output

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
        "line": "Waiting on the build",
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
    start = written(
        leaf("task", "start", page_dir, task["id"], "Drafting the glossary")
    )
    assert events_model.read_events(page_dir)[-1] == start
    state = state_json(page_dir)
    assert state["status"]["state"] == "waiting"
    assert (state["activity"]["kind"], state["activity"]["detail"]) == (
        "working",
        "Drafting the glossary",
    )


def test_a_waiting_declaration_puts_down_every_start_before_it(page_dir):
    """`status waiting` says what the agent wants back, and the banner shows it: every
    start written before it is put down, by a `put_down` in the log that a declaration
    with no start standing does not repeat. A started move goes back to its delivery
    stage, and a started task stays open with nothing running on it. A start after
    the declaration is in hand again."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Tighten it."},
    )
    task = written(leaf("task", "open", page_dir, "page", "Draft the plan"))
    written(leaf("task", "start", page_dir, task["id"], "Drafting the plan"))
    written(leaf("task", "start", page_dir, comment["id"], "Tightening it"))
    assert state_json(page_dir)["activity"]["kind"] == "working"

    written(leaf("status", page_dir, "waiting", "Pick a plan"))
    log = events_model.read_events(page_dir)
    assert log[-1]["kind"] == "put_down"
    written(leaf("status", page_dir, "waiting", "Pick a plan"))
    assert events_model.read_events(page_dir) == log
    state = state_json(page_dir)
    assert state["status"]["detail"] == "Pick a plan"
    assert state["activity"]["kind"] not in {"working", "stalled"}
    assert [item["stage"] for item in state["workflows"]] == ["sent"]
    [served] = state["tasks"]
    assert (served["id"], served["running"]) == (task["id"], None)

    written(leaf("task", "start", page_dir, task["id"], "Drafting the second plan"))
    state = state_json(page_dir)
    assert state["activity"]["detail"] == "Drafting the second plan"


def test_idle_refuses_over_an_open_task(page_dir):
    """Closing the page discharges no task: idle names each open one and how to end
    it, and goes through once they have ended."""
    publish(page_dir)
    task = written(leaf("task", "open", page_dir, "page", "Add a glossary"))
    refused = leaf("status", page_dir, "idle")
    assert refused.exit_code != 0
    assert f"1 open task: {task['id']} (Add a glossary)" in refused.output
    assert "leaf task end <page> <id> done" in refused.output
    written(leaf("task", "end", page_dir, task["id"], "dropped", "not needed"))
    written(leaf("status", page_dir, "idle"))


def test_a_start_on_a_widget_task_holds_the_moves_delivered_before_it(page_dir):
    """A task on a widget answers the moves on it: once started, the move the user
    made there reads Working and lets the turn that started it end over it. A move
    made after the start is not in hand."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>', 1)
    )
    publish(page_dir)
    pick = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"options": ["flag-first"]},
        },
    )
    task = written(leaf("task", "open", page_dir, "choice", "Build the chosen plan"))
    start = written(leaf("task", "start", page_dir, task["id"], "Building flag first"))
    [workflow] = state_json(page_dir)["workflows"]
    assert (workflow["input"], workflow["stage"], workflow["detail"]) == (
        pick["id"],
        "working",
        "Building flag first",
    )
    assert [held["item"] for held in workflow["started_by"]] == [task["id"]]
    assert workflow["started_by"][0]["seq"] == start["seq"]

    later = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"options": ["backfill-first"]},
        },
    )
    [workflow] = state_json(page_dir)["workflows"]
    assert (workflow["input"], workflow["stage"], workflow["started_by"]) == (
        later["id"],
        "sent",
        [],
    )


def test_a_start_line_is_one_sentence(page_dir):
    publish(page_dir)
    task = written(leaf("task", "open", page_dir, "page", "Add a glossary"))
    for line in ("", "   ", "two\nlines"):
        refused = leaf("task", "start", page_dir, task["id"], line)
        assert refused.exit_code != 0
        assert "names the work and its subject in one sentence" in refused.output


def asking(page_dir):
    """Publish the fixture page with its Ask's widget named, so the Ask is open."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>', 1)
    )
    publish(page_dir)


def done(page_dir, task: str) -> tuple[int, dict]:
    """The user's Done on `task`, posted as the Queue panel posts it."""
    return endpoint_model.accept_event(
        page_dir, {"kind": "task_end", "task": task, "outcome": "done"}, dict
    )


def test_a_task_on_the_user_stands_on_any_element_until_their_done(page_dir):
    """`--on user` puts a task on the user's queue, about any element of the page by
    its id, and their Done ends it: an event the agent hears of, on the one door."""
    publish(page_dir)
    task = written(
        leaf("task", "open", page_dir, "plan", "Is the plan enough?", "--on", "user")
    )
    assert (task["owner"], task["subject"]) == (
        "user",
        {"kind": "element", "id": "plan"},
    )
    state = state_json(page_dir)
    asks = [("task", ask["id"]) for ask in asks_on_you(state)]
    assert kinds(state["queues"]["on_you"]) == asks + [("task", task["id"])]
    assert state["queues"]["on_agent"] == []
    assert [item["owner"] for item in state["tasks"] if item["id"] == task["id"]] == [
        "user"
    ]

    status, answer = done(page_dir, task["id"])
    assert status == 200, answer
    end = events_model.read_events(page_dir)[-1]
    assert (end["kind"], end["author"], end["task"], end["attention"]) == (
        "task_end",
        "user",
        task["id"],
        True,
    )
    state = state_json(page_dir)
    assert kinds(state["queues"]["on_you"]) == asks
    assert task["id"] not in [item["id"] for item in state["tasks"]]
    served = full_state(page_dir, events_model.read_events(page_dir))
    [ended] = [
        item for item in served["browser"]["ended_tasks"] if item["id"] == task["id"]
    ]
    assert (ended["state"], ended["outcome"]["author"]) == ("done", "user")
    assert done(page_dir, task["id"])[0] == 400

    # Done is a gesture the user can take back, which puts the task on them again.
    status, answer = endpoint_model.accept_event(
        page_dir, {"kind": "undo", "undoes": end["id"]}, dict
    )
    assert status == 200, answer
    state = state_json(page_dir)
    assert kinds(state["queues"]["on_you"]) == asks + [("task", task["id"])]
    assert done(page_dir, task["id"])[0] == 200


def test_a_task_on_the_user_about_a_thread_is_theirs_until_they_reply(page_dir):
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Rollback?"},
    )
    written(
        leaf("thread", "reply", page_dir, "--for", comment["id"], "--text", "Read it.")
    )
    task = written(
        leaf("task", "open", page_dir, comment["id"], "Is it enough?", "--on", "user")
    )
    state = state_json(page_dir)
    assert state["threads"][0]["attention"]["kind"] == "needs_user"
    assert ("task", task["id"]) in kinds(state["queues"]["on_you"])

    reply = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": comment["id"],
            "text": "Yes.",
        },
    )
    state = state_json(page_dir)
    assert task["id"] not in [item["id"] for item in state["tasks"]]
    assert [item["id"] for item in state["queues"]["on_agent"]] == [reply["id"]]
    served = full_state(page_dir, events_model.read_events(page_dir))
    [ended] = [
        item for item in served["browser"]["ended_tasks"] if item["id"] == task["id"]
    ]
    assert (ended["state"], ended["outcome"]["id"]) == ("done", reply["id"])


def test_the_user_ends_only_their_own_task_and_not_an_asks(page_dir):
    """Done ends a task on the user. The agent's task stays the agent's to end, and
    an Ask's task ends when its widget answers it."""
    asking(page_dir)
    mine = written(leaf("task", "open", page_dir, "page", "Add a glossary"))
    [ask] = asks_on_you(state_json(page_dir))
    for task in (mine["id"], ask["id"]):
        status, answer = done(page_dir, task)
        assert status == 400, answer
    refused = leaf("task", "start", page_dir, ask["id"], "Answering it myself")
    assert refused.exit_code != 0
    assert state_json(page_dir)["tasks"][-1]["id"] == mine["id"]


def test_the_agent_ends_an_asks_task_and_a_questions(page_dir):
    """The agent may end any task: dropping an Ask's task retires the Ask, and ending
    a question's takes its thread off the user, each listed as ended."""
    asking(page_dir)
    [ask] = asks_on_you(state_json(page_dir))
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which colour?"},
    )
    question = written(
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
    written(leaf("task", "end", page_dir, ask["id"], "dropped", "Decided in chat"))
    written(leaf("task", "end", page_dir, question["id"], "done", "Asked in chat"))
    state = state_json(page_dir)
    assert state["queues"]["on_you"] == []
    assert state["tasks"] == []
    assert state["threads"][0]["attention"] is None
    served = full_state(page_dir, events_model.read_events(page_dir))
    ended = {item["id"]: item for item in served["browser"]["ended_tasks"]}
    ended.update(
        {
            item["id"]: item
            for item in served["browser"]["views"]["1"]["document"]["ended_tasks"]
        }
    )
    assert (ended[ask["id"]]["state"], ended[ask["id"]]["ask"]["widget"]) == (
        "dropped",
        ask["widget"],
    )
    assert ended[question["id"]]["state"] == "done"
    again = leaf("task", "end", page_dir, ask["id"], "done")
    assert "has already ended" in again.output
