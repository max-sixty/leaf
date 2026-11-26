"""To-dos hold work the agent owes until it ends them, a start takes a move or to-do in
hand, and the two queues say what is on the user and what is on the agent."""

import json
import threading

import pytest
from click.testing import CliRunner, Result
from interact_support import (
    FLOW_PAGE,
    PAGE,
    PAGE_GROUP,
    STATED_TIMEOUT,
    ModelPage,
    _start,
    activity_reading,
    append_carried_log_record,
    append_command,
    command_findings,
    command_notes,
    delivered,
    freeze_events,
    obligations_on_user,
    open_todos,
    owed_answers,
    page_state,
    publish,
    record_claim,
    response_reference,
    served_obligations,
    served_thread,
    served_todos,
    serving,
    stamp,
    state_json,
)

from leaf.agents import delivery as delivery_model
from leaf.agents import thread as thread_model
from leaf.base import service as service_model
from leaf.base import standing as standing_model
from leaf.base import state as state_model
from leaf.base.findings import Rejected
from leaf.base.state import EVENTS_FILE
from leaf.commands import cli as cli_model
from leaf.commands import session as session_model
from leaf.commands import tasks as tasks_model
from leaf.log import event_log as events_model
from leaf.records import event_contracts as contracts_model
from leaf.records import plans as plans_model
from leaf.records import todos as todos_model
from leaf.records import transaction as transaction_model
from leaf.records.event_contracts import append_admitted
from leaf.serving import event_endpoint as endpoint_model
from leaf.serving.served_state.page import full_state


def leaf(*args):
    return CliRunner().invoke(cli_model.cli, [str(arg) for arg in args])


def written(result) -> dict:
    assert result.exit_code == 0, result.output
    return json.loads(result.output.splitlines()[-1])


def kinds(items) -> list:
    return [(item["kind"], item["id"]) for item in items]


def test_page_state_tracks_both_lists_until_they_are_settled(page_dir):
    """Discovery reads the user's actual queue, a widget's obligation and a message's
    alike, and keeps agent work after On Me reaches zero."""
    asking(page_dir)
    [item] = state_json(page_dir)["queues"]["on_user"]
    mine = written(
        leaf("task", "create", page_dir, "page", "--title", "Finish the plan")
    )
    question = written(
        leaf(
            "thread",
            "create",
            page_dir,
            "--text",
            "Merge or abandon?",
            "--obligation",
            "--title",
            "Agent thread",
        )
    )
    queue = state_json(page_dir)
    assert kinds(queue["queues"]["on_user"]) == [
        ("widget", item["id"]),
        ("message", f"message:{question['id']}"),
    ]
    assert kinds(queue["queues"]["on_agent"]) == [("todo", mine["id"])]
    assert queue["source"]["live"] is True

    # An invalid save preserves the last valid document's obligations and reports
    # the source error beside them rather than implying the user owes nothing.
    source = (page_dir / "index.html").read_text()
    (page_dir / "index.html").write_text(source.replace('id="choice"', 'id="plan"'))
    invalid = state_json(page_dir)
    assert invalid["source"]["error"] is not None
    assert invalid["queues"]["on_user"] == queue["queues"]["on_user"]
    (page_dir / "index.html").write_text(source)

    answer = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": question["id"],
            "text": "Merge.",
        },
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["flag-first"]},
        },
    )
    queue = state_json(page_dir)
    assert queue["queues"]["on_user"] == []
    assert ("update", f"update:{answer['id']}") in kinds(queue["queues"]["on_agent"])
    assert ("todo", mine["id"]) in kinds(queue["queues"]["on_agent"])
    written(leaf("task", "end", page_dir, mine["id"], "done"))
    assert ("todo", mine["id"]) not in kinds(state_json(page_dir)["queues"]["on_agent"])


def test_a_todo_holds_its_thread_on_the_agent_past_reply_and_resolve(page_dir):
    """A reply that promises work answers the comment and, with `--todo`, opens that
    work on its thread under the reply's id in the same write. Resolving the thread
    closes it, but the to-do stays on the agent's queue until the agent ends it: the
    work a reply promised is no longer owed nowhere."""
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
    assert kinds(state["queues"]["on_agent"]) == [("update", f"update:{comment['id']}")]

    todo = written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, comment["id"]),
            "--text",
            "Building it now.",
            "--todo",
            "Rebuild the banner quieter",
            "--title",
            "Thread title",
        )
    )
    assert (todo["kind"], todo["todo"]) == ("reply", "Rebuild the banner quieter")
    state = state_json(page_dir)
    [item] = open_todos(state)
    assert (item["id"], item["source"]["subject"]) == (
        todo["id"],
        {"kind": "thread", "id": comment["id"]},
    )
    assert kinds(state["queues"]["on_agent"]) == [("todo", todo["id"])]
    assert state["queues"]["on_user"] == []
    assert state["threads"][0]["attention"] == todo["id"]

    append_command(
        page_dir,
        {"kind": "resolve", "author": "user", "parent": comment["id"]},
    )
    # Resolving closes the thread for the user; the to-do stays the agent's, and the
    # panel names it from its served record.
    state = state_json(page_dir)
    assert state["threads"][0]["attention"] is None
    assert kinds(state["queues"]["on_agent"]) == [("todo", todo["id"])]
    served = full_state(page_dir, events_model.read_events(page_dir))
    assert [item["prompt"]["text"] for item in served_todos(served["browser"])] == [
        "Rebuild the banner quieter"
    ]
    thread = leaf("page", "state", page_dir, comment["id"])
    assert thread.exit_code == 0, thread.output
    assert [item["id"] for item in open_todos(json.loads(thread.output))] == [
        todo["id"]
    ]

    end = written(
        leaf("task", "end", page_dir, todo["id"], "done", "--text", "version 2")
    )
    assert (end["todo"], end["outcome"], end["detail"]) == (
        todo["id"],
        "done",
        "version 2",
    )
    state = state_json(page_dir)
    assert state["queues"]["on_agent"] == []
    assert open_todos(state) == []
    # The browser is served the ended task beside the open ones, for the On panel's
    # Done list, with its outcome.
    served = full_state(page_dir, events_model.read_events(page_dir))
    [ended] = served_todos(served["browser"])
    assert (ended["id"], ended["state"], ended["outcome"], ended["end"]["detail"]) == (
        todo["id"],
        "done",
        "done",
        "version 2",
    )


def test_an_answer_says_what_it_leaves_the_thread_with(page_dir):
    """An answer declares whether it delivers (`--done`) or promises work
    (`--todo`), not both, unless its markup asks back; progress declares none. A
    refused answer leaves the comment owed."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Tighten it."},
    )
    reference = response_reference(page_dir, comment["id"])
    for text, flags in (
        ("On it.", []),
        ("On it.", ["--done", "--todo", "Tighten"]),
        # A blank to-do promises nothing, so it settles nothing either.
        ("On it.", ["--todo", "   "]),
        ("On it.", ["--ephemeral", "--done"]),
        # HTML with no question in it asks nothing back, so it declares nothing.
        ('On it.\n\n<figure id="sketch"><p>A sketch.</p></figure>', []),
    ):
        result = leaf(
            "thread",
            "reply",
            reference,
            "--text",
            text,
            *flags,
            "--title",
            "Thread title",
        )
        assert result.exit_code != 0, (flags, result.output)
    assert kinds(state_json(page_dir)["queues"]["on_agent"]) == [
        ("update", f"update:{comment['id']}")
    ]
    reply = written(
        leaf(
            "thread",
            "reply",
            reference,
            "--text",
            "Done.",
            "--done",
            "--title",
            "Thread title",
        )
    )
    assert "todo" not in reply
    assert state_json(page_dir)["queues"] == {"on_user": [], "on_agent": []}


def titles(page_dir) -> dict[str, str]:
    """Each to-do on the page by its id, with its title."""
    return {
        record["id"]: record["prompt"]["text"]
        for record in state_json(page_dir)["obligations"]
        if record["source"]["kind"] == "todo"
    }


def test_a_plan_reads_each_steps_state_from_the_records_it_arranges(page_dir):
    """The plan nests steps by depth and writes no standing: a step shows its to-do's
    or obligation's own, a heading that of the records under it, and a `todo` step
    opens the to-do the plan then names. A step follows its to-do's start and end, and
    the end says where the result is, so the plan follows the work without a rewrite,
    and a rewrite that leaves a to-do out leaves it owed on the agent's list."""

    def plan(steps) -> Result:
        return CliRunner().invoke(
            cli_model.cli, ["task", "plan", str(page_dir)], input=json.dumps(steps)
        )

    asking(page_dir)
    [item] = state_json(page_dir)["obligations"]
    todo = written(
        leaf("task", "create", page_dir, "page", "--title", "Cut to two lines")
    )
    written(
        leaf("task", "start", page_dir, todo["id"], "--text", "Cutting the example")
    )
    record = written(
        plan(
            [
                {"depth": 0, "title": "Review the change"},
                {"depth": 1, "todo": "Check the diffs"},
                {"depth": 1, "title": "Draft the response"},
                {"depth": 2, "item": todo["id"]},
                {"depth": 1, "item": item["id"]},
                {"depth": 1, "todo": "Post it"},
            ]
        )
    )
    checking, posting = [
        step["item"]
        for step in record["steps"]
        if "item" in step and step["item"] not in (todo["id"], item["id"])
    ]
    opened = titles(page_dir)
    assert (opened[checking], opened[posting]) == ("Check the diffs", "Post it")
    written(leaf("task", "end", page_dir, checking, "done", "--text", "In PR #12"))
    written(leaf("task", "end", page_dir, posting, "dropped", "--text", "Not needed"))
    [goal] = state_json(page_dir)["plan"]["steps"]

    def shape(step):
        return (
            step["title"],
            step["state"],
            step["outcome"],
            step["next_actor"],
            step["done"],
            step["total"],
            [shape(child) for child in step["steps"]],
        )

    assert shape(goal) == (
        "Review the change",
        "waiting",
        None,
        "user",
        1,
        3,
        [
            ("Check the diffs", "done", "done", None, 0, 0, []),
            (
                "Draft the response",
                "running",
                None,
                "agent",
                0,
                1,
                [("Cut to two lines", "running", None, "agent", 0, 0, [])],
            ),
            (item["prompt"]["text"], "waiting", None, "user", 0, 0, []),
            ("Post it", "done", "dropped", None, 0, 0, []),
        ],
    )
    assert goal["steps"][0]["detail"] == "In PR #12"
    cut = goal["steps"][1]["steps"][0]
    assert cut["item"] == {"kind": "todo", "id": todo["id"]}
    assert cut["since"] == cut["running"]["ts"]

    # Once the start is put down and the to-do ends, the heading over it reads done
    # with no rewrite; the question waiting on the user keeps the goal on the user.
    written(leaf("page", "open", page_dir))
    [goal] = state_json(page_dir)["plan"]["steps"]
    assert (goal["next_actor"], goal["steps"][1]["state"]) == ("user", "waiting")
    written(leaf("task", "end", page_dir, todo["id"], "done", "--text", "Cut"))
    [goal] = state_json(page_dir)["plan"]["steps"]
    assert (goal["next_actor"], goal["steps"][1]["outcome"]) == ("user", "done")

    # A question whose thread the agent resolved, as it does once the user answers
    # elsewhere, reads done, and a rewrite that leaves the to-do out leaves it owed.
    question = written(
        leaf(
            "thread",
            "create",
            page_dir,
            "--text",
            "Merge?",
            "--obligation",
            "--title",
            "Agent thread",
        )
    )
    asked = f"message:{question['id']}"
    written(leaf("thread", "resolve", page_dir, question["id"]))
    left = written(leaf("task", "create", page_dir, "page", "--title", "Tidy up"))
    written(
        plan([{"depth": 0, "title": "Review the change"}, {"depth": 1, "item": asked}])
    )
    [goal] = state_json(page_dir)["plan"]["steps"]
    assert (goal["state"], goal["outcome"]) == ("done", "done")
    assert [
        (step["item"]["id"], step["state"], step["outcome"]) for step in goal["steps"]
    ] == [(asked, "done", "done")]
    assert ("todo", left["id"]) in kinds(state_json(page_dir)["queues"]["on_agent"])
    outline = page_dir.parent / "plan.json"
    # A step that skips a level reads one level below the step before it, so the plan
    # is written and the command says where the step went.
    outline.write_text(json.dumps([{"depth": 1, "item": left["id"]}]))
    [skipped] = command_notes("task", "plan", page_dir, "--file", outline)
    assert (skipped.code, skipped.severity) == ("plan-depth", "advice")
    [step] = state_json(page_dir)["plan"]["steps"]
    assert (step["title"], step["steps"]) == ("Tidy up", [])
    todos_before = len(titles(page_dir))
    for steps, code in (
        ([{"depth": 0, "item": "no-such-item"}], "unknown-plan-item"),
        (
            [{"depth": 0, "todo": "Opens nothing"}, {"depth": 0, "title": "Alone"}],
            "plan-empty-heading",
        ),
        (
            [{"depth": depth, "title": "Deep"} for depth in range(9)]
            + [{"depth": 9, "item": left["id"]}],
            "invalid-event",
        ),
    ):
        outline.write_text(json.dumps(steps))
        [refused] = command_findings("task", "plan", page_dir, "--file", outline)
        assert refused.code == code
    # A refused plan opens none of its to-dos.
    assert len(titles(page_dir)) == todos_before
    # A step close to one of the shapes is refused for the field it gets wrong.
    outline.write_text(
        json.dumps(
            [
                {"depth": 0, "title": "Ship", "state": "working"},
                {"depth": 1, "todo": "X"},
            ]
        )
    )
    [unknown] = command_findings("task", "plan", page_dir, "--file", outline)
    assert (unknown.code, unknown.values["field"]) == ("invalid-event", "/steps/0")
    assert "'state' was unexpected" in unknown.values["error"]
    written(plan([]))
    assert state_json(page_dir)["plan"] is None


def test_a_goal_counts_only_the_steps_that_ended_done(task_log):
    """A to-do that failed ended, but finished nothing, so its goal reads none done
    and failed, as it does where the failed to-do stands deeper under a step that
    finished."""
    append, log = task_log
    todo = append("todo", subject={"kind": "page"}, title="Rebuild the chart")
    append("todo_end", todo=todo["id"], outcome="failed", detail="The data is gone")
    published = append("todo", subject={"kind": "page"}, title="Publish the chart")
    append("todo_end", todo=published["id"], outcome="done", detail="On the site")

    def goal_of(steps):
        append("plan", steps=steps)
        reading = plans_model.plan_reading(
            log, set(), todos_model.TodoReading(log).todos
        )
        assert reading is not None
        [goal] = reading["steps"]
        return goal

    goal = goal_of(
        [{"depth": 0, "title": "Chart the year"}, {"depth": 1, "item": todo["id"]}]
    )
    [step] = goal["steps"]
    assert (step["state"], step["outcome"]) == ("done", "failed")
    assert (goal["outcome"], goal["done"], goal["total"]) == ("failed", 0, 1)
    goal = goal_of(
        [
            {"depth": 0, "title": "Chart the year"},
            {"depth": 1, "item": published["id"]},
            {"depth": 2, "item": todo["id"]},
        ]
    )
    assert (goal["outcome"], goal["done"], goal["total"]) == ("failed", 1, 1)


def test_a_plan_step_may_name_an_update_the_agent_owes(page_dir):
    """An update the user handed over is an obligation on the agent's list, so a step
    naming its id is admitted and reads where that update stands."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Quieter."},
    )
    owed = f"update:{comment['id']}"
    written(
        CliRunner().invoke(
            cli_model.cli,
            ["task", "plan", str(page_dir)],
            input=json.dumps([{"depth": 0, "item": owed}]),
        )
    )
    [step] = state_json(page_dir)["plan"]["steps"]
    assert step["item"] == {"kind": "obligation", "id": owed}
    assert (step["next_actor"], step["state"]) == ("agent", "waiting")


def test_a_plan_step_reads_its_todo_stopped_once_the_turn_that_started_it_ends(
    claimed,
):
    """A step naming a to-do stands where the to-do does: the start its turn left,
    seen to end, reads blocked and stopped, under the line it last said."""
    todo = written(leaf("task", "create", claimed, "page", "--title", "Cut it"))
    written(leaf("task", "start", claimed, todo["id"], "--text", "Cutting it"))
    written(
        CliRunner().invoke(
            cli_model.cli,
            ["task", "plan", str(claimed)],
            input=json.dumps([{"depth": 0, "item": todo["id"]}]),
        )
    )
    claim = service_model.page_claim(claimed)
    assert claim is not None
    state_model.close_session_turn(claim["id"])
    [step] = state_json(claimed)["plan"]["steps"]
    assert (step["next_actor"], step["state"], step["reason"]) == (
        "agent",
        "blocked",
        "stopped",
    )
    assert step["running"]["text"] == "Cutting it"


def test_a_long_todo_or_plan_step_title_is_fitted_rather_than_refused(page_dir):
    """A long title breaks nothing, so a to-do's or a plan step's is fitted as a
    thread's is, and the command says what it was cut to, rather than refusing the
    reply or plan it rides on."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Hm."},
    )
    words = "Check the snapshot diffs " * 5
    fitted = thread_model.fit_title(words)
    assert len(" ".join(words.split())) > len(fitted)

    def cut(result) -> dict:
        record = written(result)
        assert "title-fitted" in {finding["code"] for finding in record.pop("findings")}
        return record

    created = cut(leaf("task", "create", page_dir, "page", "--title", words))
    assert created["title"] == fitted
    answered = cut(
        leaf(
            "thread",
            "reply",
            page_dir,
            comment["id"],
            "--text",
            "On it.",
            "--todo",
            words,
            "--title",
            "Thread title",
        )
    )
    assert answered["todo"] == fitted
    outline = page_dir.parent / "plan.json"
    outline.write_text(
        json.dumps([{"depth": 0, "title": words}, {"depth": 1, "todo": words}])
    )
    planned = cut(leaf("task", "plan", page_dir, "--file", outline))
    heading, step = planned["steps"]
    assert heading["title"] == fitted
    assert titles(page_dir)[step["item"]] == fitted


def test_the_door_refuses_a_todo_off_the_page_and_an_outcome_twice(page_dir):
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Hm."},
    )
    [missing] = command_findings(
        "task", "create", page_dir, "no-such-thing", "--title", "Anything"
    )
    assert missing.code == "unknown-subject"
    [unknown] = command_findings("task", "end", page_dir, "no-such-task", "done")
    assert unknown.code == "unknown-todo"
    threaded = written(
        leaf("task", "create", page_dir, comment["id"], "--title", "Look into it")
    )
    assert threaded["subject"] == {"kind": "thread", "id": comment["id"]}

    todo = written(leaf("task", "create", page_dir, "page", "--title", "Look into it"))
    written(
        leaf("task", "end", page_dir, todo["id"], "dropped", "--text", "not needed")
    )
    again = leaf("task", "end", page_dir, todo["id"], "done")
    assert again.exit_code != 0
    assert "already ended (dropped)" in again.output

    before = events_model.read_events(page_dir)
    for invalid in (
        {"author": "user"},
        {"title": "Two\nlines"},
        {"title": "x" * 81},
        {"subject": {"kind": "thread", "id": "missing-thread"}},
        {"subject": {"kind": "widget", "id": "s-1"}},
    ):
        with pytest.raises(events_model.EventRefused):
            append_command(
                page_dir,
                {
                    "kind": "todo",
                    "author": "agent",
                    "agent": "Claude",
                    "session": "task-test",
                    "subject": {"kind": "page"},
                    "title": "Fine",
                    **invalid,
                },
            )
    assert events_model.read_events(page_dir) == before


@pytest.mark.parametrize("answer_kind", ["reply", "reaction"])
def test_an_opening_obligation_retains_its_answer_in_the_obligation_inventory(
    page_dir, answer_kind
):
    """A question opening a thread retains its answer across edits and updates."""
    publish(page_dir)
    question = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which colour?",
            "obligation": True,
        },
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "message": question["id"],
            "text": "Warm or cool?",
        },
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": question["id"],
            "text": "Still checking.",
            "ephemeral": True,
        },
    )
    served = full_state(page_dir, events_model.read_events(page_dir))
    assert [
        entry["source"]["id"] for entry in served_obligations(served["browser"])["user"]
    ] == [question["id"]]
    answer = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": question["id"],
            **({"text": "Warm."} if answer_kind == "reply" else {"emoji": "👍"}),
        },
    )
    served = full_state(page_dir, events_model.read_events(page_dir))
    assert served_todos(served["browser"]) == []
    [ended] = served_obligations(served["browser"])["all"]
    assert standing_model.answered(ended)
    assert (ended["source"]["id"], ended["answer"]["event"]["id"]) == (
        question["id"],
        answer["id"],
    )
    if answer_kind == "reaction":
        append_command(
            page_dir, {"kind": "undo", "author": "user", "undoes": answer["id"]}
        )
        served = full_state(page_dir, events_model.read_events(page_dir))
        assert [
            entry["source"]["id"]
            for entry in served_obligations(served["browser"])["user"]
        ] == [question["id"]]
        assert served_todos(served["browser"]) == []


def test_an_obligation_ends_at_the_reaction_after_it(page_dir):
    """A reaction is the user's next message, so whatever its emoji it answers the
    question before it, and it is the outcome the ended obligation records."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which colour?"},
    )
    question = written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, comment["id"]),
            "--text",
            "Warm or cool?",
            "--obligation",
            "--title",
            "Thread title",
        )
    )
    reaction = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": question["id"],
            "emoji": "🤔",
        },
    )
    served = full_state(page_dir, events_model.read_events(page_dir))
    [answered] = served_obligations(served["browser"])["all"]
    assert standing_model.answered(answered)
    assert answered["answer"]["event"]["id"] == reaction["id"]


def test_a_thread_is_on_you_once_however_many_moves_it_holds_for_you(page_dir):
    """A message whose reply failed is the user's to send again, an obligation of its
    own on On Me. A question the agent then leaves in its thread is a second
    obligation there, listed ahead of it, and the thread reads as that question: `m`
    stops at a thread once (panel/queue-walk.js)."""
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
    items = [("widget", item["id"]) for item in obligations_on_user(state)]
    resend = ("update", f"update:{comment['id']}")
    assert [item["obligation"] for item in state["workflows"]] == [resend[1]]
    assert kinds(state["queues"]["on_user"]) == items + [resend]

    question = written(
        leaf(
            "thread",
            "reply",
            page_dir,
            comment["id"],
            "--text",
            "Short or long title?",
            "--obligation",
            "--title",
            "Thread title",
        )
    )
    state = state_json(page_dir)
    assert [item["obligation"] for item in state["workflows"]] == [resend[1]]
    assert kinds(state["queues"]["on_user"]) == items + [
        ("message", f"message:{question['id']}"),
        resend,
    ]
    assert state["queues"]["on_agent"] == []
    [thread] = state["threads"]
    assert thread["attention"] == f"message:{question['id']}"


def test_working_names_a_move_until_its_answer_and_a_todo_until_its_end(page_dir):
    """`task start` takes an item on the agent's queue in hand with the status's line:
    the user's move, by its event id, reads Working until the reply that answers it,
    and a to-do runs until it ends. An id that is neither is refused at the door."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Tighten it."},
    )
    [refused] = command_findings(
        "task", "start", page_dir, "no-such-move", "--text", "Reading it"
    )
    assert refused.code == "unowed-start"

    start = written(
        leaf(
            "task",
            "start",
            page_dir,
            comment["id"],
            "--text",
            "Tightening the plan section",
        )
    )
    assert (start["kind"], start["item"]) == ("start", comment["id"])
    state = state_json(page_dir)
    [workflow] = state["workflows"]
    assert (workflow["state"], workflow["detail"]) == (
        "running",
        "Tightening the plan section",
    )
    assert state["activity"]["state"] == "running"
    assert state["activity"]["detail"] == "Tightening the plan section"

    # The reply that answers the move ends its start: nothing is in hand.
    written(
        leaf(
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, comment["id"]),
            "--text",
            "Done.",
            "--title",
            "Thread title",
        )
    )
    state = state_json(page_dir)
    assert state["workflows"] == []
    assert state["activity"]["state"] != "running"
    again = leaf("task", "start", page_dir, comment["id"], "--text", "More")
    assert again.exit_code != 0

    # A to-do the agent opens on the page, for work no move asked for, runs under its
    # start's line until the to-do ends; the panel's status shows that line.
    todo = written(
        leaf("task", "create", page_dir, "page", "--title", "Add a glossary")
    )
    assert todo["subject"] == {"kind": "page"}
    written(
        leaf("task", "start", page_dir, todo["id"], "--text", "Drafting the glossary")
    )
    state = state_json(page_dir)
    [served] = open_todos(state)
    assert served["line"]["text"] == "Drafting the glossary"
    assert state["activity"]["detail"] == "Drafting the glossary"
    [item] = state["queues"]["on_agent"]
    assert (item["kind"], item["subject"]) == ("todo", {"kind": "page"})
    written(
        leaf(
            "task",
            "end",
            page_dir,
            todo["id"],
            "done",
            "--text",
            "the glossary section",
        )
    )
    state = state_json(page_dir)
    assert open_todos(state) == []
    assert state["activity"]["state"] != "running"


@pytest.mark.parametrize("claim", ["task start", "progress reply"])
def test_a_claim_reaching_the_door_as_its_update_settles_takes_nothing_in_hand(
    page_dir, monkeypatch, capsys, claim
):
    """An agent decides to take an update in hand from a delivery it read earlier, so
    the update may settle between that reading and its claim. The door reads whether
    the update is still owed under the same log lock as the append, so a claim that
    reaches the lock while the settlement holds it takes nothing in hand, and the page
    never reads Working on a settled update. A bare start is refused; progress still
    posts in the thread, with a note of what the log now holds the update as."""
    publish(page_dir)
    comment = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Tighten it."},
    )
    reference = response_reference(page_dir, comment["id"])
    claim_waits = threading.Event()
    take_lock = state_model.acquire

    def acquire(f, path, deadline):
        if threading.current_thread().name == "claim" and path.name == EVENTS_FILE:
            claim_waits.set()
        take_lock(f, path, deadline)

    monkeypatch.setattr(state_model, "acquire", acquire)

    def take_in_hand():
        if claim == "task start":
            tasks_model.cmd_start(page_dir, comment["id"], "Tightening it")
        else:
            thread_model.post_response(reference, "Tightening it", ephemeral=True)

    refusals = []

    def run_claim():
        try:
            take_in_hand()
        except Rejected as refused:
            refusals.append(refused)

    claiming = threading.Thread(target=run_claim, name="claim")
    with transaction_model.PageTransaction(page_dir) as page:
        claiming.start()
        assert claim_waits.wait(STATED_TIMEOUT)
        # Another session's resolve answers for the thread; the user's own would
        # leave the update owed.
        append_admitted(
            page, {"kind": "resolve", "author": "agent", "parent": comment["id"]}
        )
    claiming.join(STATED_TIMEOUT)
    assert not claiming.is_alive()

    last = events_model.read_events(page_dir)[-1]
    if claim == "task start":
        [refused] = refusals
        assert refused.findings[0].code == "unowed-start"
        assert last["kind"] == "resolve"
    else:
        assert refusals == []
        assert (last["kind"], last["ephemeral"], "start" in last) == (
            "reply",
            True,
            False,
        )
        noted = json.loads(capsys.readouterr().err.splitlines()[-1])
        assert noted["code"] == "superseded-progress"
        assert "resolved the thread" in noted["text"]
    state = state_json(page_dir)
    assert state["workflows"] == []
    assert state["activity"]["state"] != "running"


@pytest.mark.parametrize(
    "start", ["task start", "progress on the reference", "progress on the to-do"]
)
def test_a_thread_todo_runs_under_its_start_line(page_dir, capsys, start):
    """A thread waits on a started to-do by its id, and the to-do's record carries the
    line its start runs under. Progress posted where the work was promised starts it as
    `leaf task start` does: on the reference whose answer opened the to-do, as a
    worker briefed with that reference posts it, or on the to-do's own message."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Rebuild it."},
    )
    reference = response_reference(page_dir, comment["id"])
    todo = written(
        leaf(
            "thread",
            "reply",
            reference,
            "--text",
            "On it.",
            "--todo",
            "Rebuild the chart",
            "--title",
            "Thread title",
        )
    )
    line = ("--text", "Waiting on the build")
    if start == "task start":
        written(leaf("task", "start", page_dir, todo["id"], *line))
    else:
        address = (
            (reference,)
            if start == "progress on the reference"
            else (page_dir, todo["id"])
        )
        capsys.readouterr()
        progress = written(leaf("thread", "reply", *address, "--ephemeral", *line))
        assert progress["start"] == {"item": todo["id"]}
        assert "superseded-progress" not in capsys.readouterr().err
    state = state_json(page_dir)
    [thread] = state["threads"]
    assert thread["attention"] == todo["id"]
    [record] = open_todos(state)
    assert (record["id"], record["line"]["text"]) == (
        todo["id"],
        "Waiting on the build",
    )


def test_a_todo_waits_on_what_the_agent_named_until_it_takes_the_work_up(page_dir):
    """A to-do may name what its work waits on, opened by a reply or by `task
    create`, and carries it until a start takes the work up: a start that lapses or
    is put down later leaves it a to-do still to do, not waiting again, and an ended
    one, or the plan step naming it, waits on nothing. Only a to-do
    waits on something, and words too long to stand in a status are fitted rather
    than refused."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Wait for it."},
    )
    reference = response_reference(page_dir, comment["id"])
    lone = leaf(
        "thread",
        "reply",
        reference,
        "--text",
        "Held.",
        "--done",
        "--waiting-on",
        "Whose Words",
        "--title",
        "Thread title",
    )
    assert lone.exit_code != 0, lone.output
    held = written(
        leaf(
            "thread",
            "reply",
            reference,
            "--text",
            "Held.",
            "--todo",
            "Take up the card's top line",
            "--waiting-on",
            "Whose Words",
            "--title",
            "Thread title",
        )
    )
    created = written(
        leaf(
            "task",
            "create",
            page_dir,
            "page",
            "--title",
            "Merge the change",
            "--waiting-on",
            "its review by the release team and then CI",
        )
    )

    def waits() -> dict:
        return {
            record["id"]: record["waiting_on"]
            for record in open_todos(state_json(page_dir))
        }

    assert waits() == {
        held["id"]: "Whose Words",
        created["id"]: "its review by the release…",
    }
    # A plan step naming one says what it waits on, as the to-do does.
    written(
        CliRunner().invoke(
            cli_model.cli,
            ["task", "plan", str(page_dir)],
            input=json.dumps(
                [{"depth": 0, "item": held["id"]}, {"depth": 0, "item": created["id"]}]
            ),
        )
    )

    def steps() -> dict:
        return {
            step["item"]["id"]: (step["state"], step["waiting_on"])
            for step in state_json(page_dir)["plan"]["steps"]
        }

    assert steps() == {
        held["id"]: ("waiting", "Whose Words"),
        created["id"]: ("waiting", "its review by the release…"),
    }

    written(leaf("task", "start", page_dir, held["id"], "--text", "Building it"))
    written(leaf("page", "open", page_dir))
    assert waits() == {
        held["id"]: None,
        created["id"]: "its review by the release…",
    }

    written(leaf("task", "end", page_dir, held["id"], "done"))
    written(leaf("task", "end", page_dir, created["id"], "dropped"))
    state = state_json(page_dir)
    assert {
        record["id"]: (record["state"], record["waiting_on"])
        for record in state["obligations"]
        if record["source"]["kind"] == "todo"
    } == {held["id"]: ("done", None), created["id"]: ("done", None)}
    assert steps() == {held["id"]: ("done", None), created["id"]: ("done", None)}


@pytest.fixture
def task_log():
    """Real admission on literal markup, with equal timestamps and explicit voices."""
    page = ModelPage(PAGE)
    log = []

    def append(kind, *, session=None, **fields):
        event = contracts_model.admitted_event(
            page,
            log,
            {
                "kind": kind,
                "id": f"e{len(log) + 1}",
                "seq": len(log) + 1,
                "ts": "2026-10-12T12:00:00+00:00",
                "author": "agent",
                **({"session": session} if session is not None else {}),
                **fields,
            },
        )
        log.append(event)
        return event

    return append, log


def test_any_agent_session_can_end_a_todo_another_started(task_log):
    """A start says who is at work, not who may end the to-do: a session that
    neither opened nor started it ends it."""
    append, log = task_log
    todo = append("todo", session="opener", subject={"kind": "page"}, title="Plan")
    append("start", session="worker", item=todo["id"], text="Working")
    completed = append("todo_end", session="third", todo=todo["id"], outcome="failed")
    [ended] = todos_model.TodoReading(log).todos
    assert (ended["state"], ended["outcome"]) == ("done", "failed")
    assert ended["end"]["event"]["id"] == completed["id"]


WORK_PAGE = FLOW_PAGE.replace(
    '<lf-diagram id="flow">',
    '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
    '  <lf-card id="rollout-card" label="Ship the rollout"><strong>Ship the rollout</strong> '
    "Check the fallback before cutover.</lf-card>\n"
    '</lf-column></lf-board>\n<lf-diagram id="flow">',
)


def test_a_widget_todo_stands_on_any_live_widget_and_a_completing_stamp_ends_it(
    page_dir,
):
    """A to-do stands on any live widget on the page, as on any other element.
    Dropping its widget leaves it open; `page stamp --completes` ends it done, citing
    that version."""
    (page_dir / "index.html").write_text(WORK_PAGE)
    publish(page_dir)
    drawing = written(
        leaf("task", "create", page_dir, "flow", "--title", "Redraw the graph")
    )
    assert drawing["subject"] == {"kind": "widget", "id": "flow"}
    written(leaf("task", "end", page_dir, drawing["id"], "dropped", "--text", "No"))

    todo = written(
        leaf("task", "create", page_dir, "rollout-card", "--title", "Check the rollout")
    )
    assert todo["subject"] == {"kind": "widget", "id": "rollout-card"}
    assert todo["revision"] == 1
    written(
        leaf("task", "start", page_dir, todo["id"], "--text", "Checking the fallback")
    )
    [served] = open_todos(state_json(page_dir))
    assert served["line"]["text"] == "Checking the fallback"

    # An unrelated version and one that drops its card both leave the to-do open.
    (page_dir / "index.html").write_text(
        WORK_PAGE.replace("<title>t</title>", "<title>t · v2</title>")
    )
    assert stamp(page_dir, "Elsewhere").exit_code == 0
    assert [item["id"] for item in open_todos(state_json(page_dir))] == [todo["id"]]
    (page_dir / "index.html").write_text(FLOW_PAGE)
    dropped = stamp(page_dir, "Card gone")
    assert dropped.exit_code == 0, dropped.output
    assert [item["id"] for item in open_todos(state_json(page_dir))] == [todo["id"]]
    (page_dir / "index.html").write_text(
        FLOW_PAGE.replace("<title>t</title>", "<title>t · v3</title>")
    )
    done = stamp(page_dir, "Rollout checked", completes=("rollout-card",))
    assert done.exit_code == 0, done.output
    note = events_model.read_events(page_dir)[-1]
    assert note["settles"] == [{"kind": "todo", "id": todo["id"]}]
    assert open_todos(state_json(page_dir)) == []
    ended = {
        item["id"]: item
        for item in todos_model.TodoReading(events_model.read_events(page_dir)).todos
    }[todo["id"]]
    assert (ended["state"], ended["outcome"], ended["end"]["detail"]) == (
        "done",
        "done",
        "v4",
    )
    (page_dir / "index.html").write_text(
        WORK_PAGE.replace("<title>t</title>", "<title>t · v4</title>")
    )
    again = stamp(page_dir, "Again", completes=("rollout-card",))
    assert again.exit_code != 0
    assert "no open to-do on 'rollout-card'" in again.output
    # The refusal says what --completes is for, so an author who reached for it to
    # finish a user's answer on the widget stamps again without it.
    assert "none is open" in again.output
    assert "needs no --completes" in again.output


def test_a_completing_stamp_ends_todos_another_session_started(page_dir):
    """A stamp's `--completes` ends every open to-do on its widget, whichever
    session last started each."""
    source = page_dir / "index.html"
    source.write_text(WORK_PAGE)
    publish(page_dir)
    todos = [
        written(leaf("task", "create", page_dir, "rollout-card", "--title", title))
        for title in ("Check fallback", "Check rollout")
    ]
    append_command(
        page_dir,
        {
            "kind": "start",
            "author": "agent",
            "session": "newer",
            "item": todos[-1]["id"],
            "text": "Continuing the checks",
        },
    )
    source.write_text(WORK_PAGE.replace("<title>t</title>", "<title>Checked</title>"))
    completed = stamp(page_dir, "Checks complete", completes=("rollout-card",))
    assert completed.exit_code == 0, completed.output
    assert open_todos(state_json(page_dir)) == []
    note = events_model.read_events(page_dir)[-1]
    assert {settled["id"] for settled in note["settles"]} == {
        todo["id"] for todo in todos
    }


def test_a_waiting_declaration_puts_down_every_start_before_it(page_dir):
    """`page open` leaves feedback available without an obligation: every
    start written before it is put down, by the `status` event the declaration
    writes. A started move goes back to where its delivery stands, and a started
    to-do stays open, waiting with no line. A start after the declaration is in hand
    again."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Tighten it."},
    )
    todo = written(
        leaf("task", "create", page_dir, "page", "--title", "Draft the plan")
    )
    written(leaf("task", "start", page_dir, todo["id"], "--text", "Drafting the plan"))
    written(leaf("task", "start", page_dir, comment["id"], "--text", "Tightening it"))
    assert state_json(page_dir)["activity"]["state"] == "running"

    written(leaf("page", "open", page_dir))
    # The declaration is the agent's own word: it asks the agent for nothing.
    declaration = events_model.read_events(page_dir)[-1]
    assert (declaration["kind"], declaration["attention"]) == ("status", False)
    state = state_json(page_dir)
    assert state["queues"]["on_user"] == []
    assert state["activity"]["state"] not in {"running", "blocked"}
    assert [(item["state"], item["seen"]) for item in state["workflows"]] == [
        ("waiting", False)
    ]
    [served] = open_todos(state)
    assert (served["id"], served["state"], served["line"]) == (
        todo["id"],
        "waiting",
        None,
    )

    written(
        leaf(
            "task", "start", page_dir, todo["id"], "--text", "Drafting the second plan"
        )
    )
    state = state_json(page_dir)
    assert state["activity"]["detail"] == "Drafting the second plan"


def test_work_taken_in_hand_reopens_an_idle_page(page_dir):
    """`idle` says the agent is done with the page, so every watcher stands down; a
    start after it says the agent is back. The page reads waiting from that start
    on, with no declaration written for it, since one would put the start down."""
    publish(page_dir)
    written(leaf("page", "close", page_dir))
    assert state_json(page_dir)["status"]["state"] == "idle"
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "One more."},
    )

    start = written(
        leaf("task", "start", page_dir, comment["id"], "--text", "Looking again")
    )
    assert events_model.read_events(page_dir)[-1]["id"] == start["id"]
    state = state_json(page_dir)
    assert (state["status"]["state"], state["status"]["ts"]) == ("waiting", start["ts"])
    assert state["activity"]["detail"] == "Looking again"


def test_idle_refuses_over_an_open_todo(page_dir):
    """Closing the page discharges no to-do: idle names each open one and how to end
    it, and goes through once they have ended."""
    publish(page_dir)
    todo = written(
        leaf("task", "create", page_dir, "page", "--title", "Add a glossary")
    )
    refused = leaf("page", "close", page_dir)
    assert refused.exit_code != 0
    assert f"1 open to-do: {todo['id']} (Add a glossary)" in refused.output
    assert "leaf task end <page> <id> done" in refused.output
    written(
        leaf("task", "end", page_dir, todo["id"], "dropped", "--text", "not needed")
    )
    written(leaf("page", "close", page_dir))


def test_a_start_on_a_widget_todo_holds_the_moves_delivered_before_it(page_dir):
    """A to-do on a widget answers the moves on it: once started, the move the user
    made there reads Working and lets the turn that started it end over it. A move
    made after the start is not in hand."""
    (page_dir / "index.html").write_text(
        PAGE.replace(PAGE_GROUP, '<lf-options id="choice">', 1)
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
            "detail": {"value": ["flag-first"]},
        },
    )
    todo = written(
        leaf("task", "create", page_dir, "choice", "--title", "Build the chosen plan")
    )
    start = written(
        leaf("task", "start", page_dir, todo["id"], "--text", "Building flag first")
    )
    [workflow] = state_json(page_dir)["workflows"]
    assert (workflow["input"], workflow["state"], workflow["detail"]) == (
        pick["id"],
        "running",
        "Building flag first",
    )
    assert [held["item"] for held in workflow["started_by"]] == [todo["id"]]
    assert workflow["started_by"][0]["seq"] == start["seq"]

    later = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["backfill-first"]},
        },
    )
    [workflow] = state_json(page_dir)["workflows"]
    assert (workflow["input"], workflow["state"], workflow["started_by"]) == (
        later["id"],
        "waiting",
        [],
    )


def test_a_start_line_is_one_sentence(page_dir):
    publish(page_dir)
    todo = written(
        leaf("task", "create", page_dir, "page", "--title", "Add a glossary")
    )
    for line in ("", "   ", "two\nlines"):
        refused = leaf("task", "start", page_dir, todo["id"], "--text", line)
        assert refused.exit_code != 0
        assert "start event is invalid" in refused.output


def asking(page_dir):
    """Publish the fixture page with its obligation's widget named, so the obligation is open."""
    (page_dir / "index.html").write_text(
        PAGE.replace(PAGE_GROUP, '<lf-options id="choice">', 1)
    )
    publish(page_dir)


def done(page_dir, todo: str) -> tuple[int, dict]:
    """A Done on `todo` posted to the browser's door, which takes none."""
    return endpoint_model.accept_event(
        page_dir, {"kind": "todo_end", "todo": todo, "outcome": "done"}
    )


def test_the_browser_ends_no_todo_or_obligation_outright(page_dir):
    """The browser can't end a to-do or an obligation outright: a to-do is the agent's
    to end, and an obligation ends only through its source, a widget's own controls
    or a reply in its thread."""
    asking(page_dir)
    mine = written(
        leaf("task", "create", page_dir, "page", "--title", "Add a glossary")
    )
    [item] = obligations_on_user(state_json(page_dir))
    for todo in (mine["id"], item["id"]):
        status, answer = done(page_dir, todo)
        assert status == 400, answer
    refused = leaf(
        "task", "start", page_dir, item["id"], "--text", "Answering it myself"
    )
    assert refused.exit_code != 0
    assert open_todos(state_json(page_dir))[-1]["id"] == mine["id"]


def test_a_decision_ends_through_its_state_and_a_question_with_its_thread(page_dir):
    """A decision widget's obligation follows its state, and a question asked in a
    thread leaves On Me when the agent resolves its thread, as it does once the user
    answered elsewhere, without inventing their answer or listing it under Done, and
    a later reply in the thread doesn't bring it back. `task end` names only to-dos,
    and refuses either obligation with how it ends."""
    asking(page_dir)
    [item] = obligations_on_user(state_json(page_dir))
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which colour?"},
    )
    question = written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, comment["id"]),
            "--text",
            "Warm or cool?",
            "--obligation",
            "--title",
            "Thread title",
        )
    )
    asked = f"message:{question['id']}"
    for identity, message in ((item["id"], None), (asked, question["id"])):
        [refused] = command_findings(
            "task", "end", page_dir, identity, "done", "--text", "In chat"
        )
        assert (refused.code, refused.values["message"]) == ("obligation-end", message)
    assert kinds(state_json(page_dir)["queues"]["on_user"]) == [
        ("widget", item["id"]),
        ("message", asked),
    ]

    written(leaf("thread", "resolve", page_dir, question["id"]))
    # A later reply reopens the thread and brings back nothing the resolve ended.
    written(leaf("thread", "reply", page_dir, question["id"], "--text", "Warm it is."))
    state = state_json(page_dir)
    assert kinds(state["queues"]["on_user"]) == [("widget", item["id"])]
    [record] = [record for record in state["obligations"] if record["id"] == asked]
    assert (record["state"], record["answer"], record["next_actor"]) == (
        "waiting",
        None,
        None,
    )
    served = full_state(page_dir, events_model.read_events(page_dir))
    [view] = served["browser"]["views"].values()
    assert asked not in [row["id"] for row in view["queues"]["done"]]


def test_a_reply_clears_a_question_until_the_agent_reopens_it(page_dir):
    """The user's reply takes a step off On Me at once, whatever it says, and its
    delivery names the step in `settled`. Where the reply only asked back, the agent's
    `--obligation <id>` returns the same item to On Me, and a plan step naming it follows, until
    their next reply answers it."""

    def on_me():
        return kinds(state_json(page_dir)["queues"]["on_user"])

    def step_state():
        [goal] = state_json(page_dir)["plan"]["steps"]
        return goal["state"]

    publish(page_dir)
    asked = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Is it ready?"},
    )
    question = written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, asked["id"]),
            "--obligation",
            "--text",
            "Can you try the build on your phone?",
            "--title",
            "Thread title",
        )
    )
    item = f"message:{question['id']}"
    written(
        CliRunner().invoke(
            cli_model.cli,
            ["task", "plan", str(page_dir)],
            input=json.dumps([{"depth": 0, "item": item}]),
        )
    )
    assert on_me() == [("message", item)]
    assert step_state() == "waiting"

    said = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": question["id"],
            "text": "Where do I get it?",
        },
    )
    assert on_me() == []
    assert step_state() == "done"
    [batch] = freeze_events(page_dir, [said])["batches"]
    [delivered] = batch["events"]
    assert delivered["settled"] == [
        {"id": item, "text": "Can you try the build on your phone?"}
    ]
    assert any(
        "--obligation <id>" in batch["handling"][clause]
        for clause in delivered["handling"]
    )

    again = written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, said["id"]),
            "--obligation",
            item,
            "--text",
            "It is at /builds. Reply once it opens.",
        )
    )
    assert on_me() == [("message", item)]
    assert step_state() == "waiting"
    [record] = [r for r in state_json(page_dir)["obligations"] if r["id"] == item]
    assert record["message"] == again["id"]
    assert record["prompt"]["text"] == "Can you try the build on your phone?"

    append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": again["id"],
            "text": "It opens.",
        },
    )
    assert on_me() == []
    assert step_state() == "done"


def test_one_reply_reopens_each_question_the_users_message_answered(page_dir):
    """The user's message answers every question before it in its thread, so the
    agent's reply can reopen each that still stands, and they wait on the user
    again together."""
    publish(page_dir)
    root = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Ready?"},
    )
    first = written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, root["id"]),
            "--obligation",
            "--text",
            "Can you try the build?",
            "--title",
            "Thread title",
        )
    )
    second = written(
        leaf(
            "thread",
            "reply",
            page_dir,
            first["id"],
            "--obligation",
            "--text",
            "And the docs preview?",
        )
    )
    said = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": second["id"], "text": "Where?"},
    )
    asked = [f"message:{first['id']}", f"message:{second['id']}"]
    [delivered] = freeze_events(page_dir, [said])["batches"][0]["events"]
    assert [question["id"] for question in delivered["settled"]] == asked
    written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, said["id"]),
            *[flag for question in asked for flag in ("--obligation", question)],
            "--text",
            "Both are under /previews. Can you try them?",
        )
    )
    state = state_json(page_dir)
    records = {record["id"]: record for record in state["obligations"]}
    assert [(records[q]["state"], records[q]["next_actor"]) for q in asked] == [
        ("waiting", "user"),
        ("waiting", "user"),
    ]
    # One reply answers both, so they share the thread's row on On Me.
    assert len(state["queues"]["on_user"]) == 1


def test_obligation_names_a_question_its_own_thread_asks(page_dir):
    """`--obligation <id>` takes the id a question keeps, from its own thread: a message
    that asked a question again has no id of its own to name, and neither has another
    thread's question, so the writer learns at once rather than putting nothing back on
    On Me. A message asks a new question or asks named ones again, so it can't do both."""

    def asked_in_a_thread(text):
        root = append_command(
            page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Ready?"},
        )
        return root, written(
            leaf(
                "thread",
                "reply",
                response_reference(page_dir, root["id"]),
                "--obligation",
                "--text",
                text,
                "--title",
                "Thread title",
            )
        )

    publish(page_dir)
    _, elsewhere = asked_in_a_thread("Which store?")
    _, here = asked_in_a_thread("Which queue?")
    said = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": here["id"], "text": "What for?"},
    )
    reference = response_reference(page_dir, said["id"])
    [refused] = command_findings(
        "thread",
        "reply",
        reference,
        "--obligation",
        f"message:{elsewhere['id']}",
        "--text",
        "Which store?",
    )
    assert refused.code == "unasked-obligation"
    both = leaf(
        "thread",
        "reply",
        reference,
        "--obligation",
        "--obligation",
        f"message:{here['id']}",
        "--text",
        "Which queue?",
    )
    assert both.exit_code != 0
    assert "not both" in both.output
    again = written(
        leaf(
            "thread",
            "reply",
            reference,
            "--obligation",
            f"message:{here['id']}",
            "--text",
            "For sessions. Which queue?",
        )
    )
    [refused] = command_findings(
        "thread",
        "reply",
        page_dir,
        again["id"],
        "--obligation",
        f"message:{again['id']}",
        "--text",
        "Which queue, still?",
    )
    assert refused.code == "unasked-obligation"


def test_the_agent_ends_a_choice_the_user_answered_in_words(page_dir):
    """A choice sent in a reply stays the user's after they answer it in words, since
    no revision can write a thread widget's state. The delivery of their words names
    the choice in `waiting`, and the agent's resolve of the thread takes it off On Me."""
    asking(page_dir)
    asked = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which store?"},
    )
    written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, asked["id"]),
            "--text",
            "Which store should own sessions?\n\n"
            '<lf-options id="store">'
            '<lf-option id="store-account" label="Account store"><strong>Account store</strong></lf-option>'
            '<lf-option id="store-own" label="Their own store"><strong>Their own store</strong></lf-option>'
            "</lf-options>",
            "--title",
            "Thread title",
        )
    )
    said = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "Account."},
    )
    [delivered_words] = freeze_events(page_dir, [said])["batches"][0]["events"]
    [waiting] = delivered_words["waiting"]
    assert waiting["id"] == "widget:store"
    assert waiting["text"].startswith("Which store should own sessions?")
    written(
        leaf(
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, said["id"]),
            "--text",
            "Sessions stay in the account store.",
        )
    )
    on_user = [item["id"] for item in state_json(page_dir)["queues"]["on_user"]]
    assert "widget:store" in on_user

    written(leaf("thread", "resolve", page_dir, "store"))
    state = state_json(page_dir)
    assert "widget:store" not in [item["id"] for item in state["queues"]["on_user"]]
    [record] = [item for item in state["obligations"] if item["id"] == "widget:store"]
    assert (record["state"], record["next_actor"], record["answer"]) == (
        "waiting",
        None,
        None,
    )
    # The user's next words there are delivered with no question waiting on them.
    later = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "Thanks."},
    )
    [delivered_later] = freeze_events(page_dir, [later])["batches"][0]["events"]
    assert not delivered_later.get("waiting")


def test_a_start_names_the_exact_move_and_covers_its_threads_answer(page_dir):
    """`task start` takes the id a delivery names, which for a reply in a thread is
    that reply's id, and that move reads Working. A correction the user adds keeps its
    own receipt, and the start still covers it: the thread's one reply answers both,
    so the Stop hook reads the newest input as started (`started_by`)."""
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "first", "author": "user", "text": "Use A."},
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": first["id"],
            "responds": first["id"],
            "text": "Which A?",
        },
    )
    answer = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": first["id"], "text": "A1."},
    )
    [workflow] = owed_answers(page_dir)
    assert workflow["answer"]["parent"] == answer["id"]

    started = _start(page_dir, answer["id"], "Answering the comment")
    assert started.exit_code == 0, started.output
    record = json.loads(started.output.splitlines()[-1])
    assert (record["kind"], record["item"]) == ("start", answer["id"])
    [workflow] = page_state(page_dir)["workflows"]
    assert (workflow["input"], workflow["state"], workflow["detail"]) == (
        answer["id"],
        "running",
        "Answering the comment",
    )
    # The thread's answered root is no move the agent owes.
    assert _start(page_dir, first["id"], "Still on it").exit_code != 0

    correction = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": first["id"],
            "text": "Correction: use B.",
        },
    )
    assert _start(page_dir, answer["id"], "Still on it").exit_code == 0
    workflows = page_state(page_dir)["workflows"]
    assert [(item["input"], item["state"]) for item in workflows] == [
        (answer["id"], "running"),
        (correction["id"], "waiting"),
    ]
    newest = workflows[-1]
    assert newest["obligation"] == f"update:{correction['id']}"
    assert [start["seq"] for start in newest["started_by"]] == [
        events_model.read_events(page_dir)[-1]["seq"]
    ]


def test_a_start_on_a_page_move_holds_that_move_and_not_a_later_one(page_dir):
    """A start on a page widget's move holds that move; a later move on the widget,
    which supersedes it, is not in hand until the agent starts it."""
    version = page_dir / "index.html"
    version.write_text(PAGE.replace(PAGE_GROUP, '<lf-options id="choice">', 1))
    publish(page_dir)
    chosen = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["flag-first"]},
        },
    )

    result = _start(page_dir, chosen["id"], "Building the flag")

    assert result.exit_code == 0, result.output
    [workflow] = page_state(page_dir)["workflows"]
    assert (workflow["input"], workflow["subject"], workflow["state"]) == (
        chosen["id"],
        {"kind": "widget", "id": "choice"},
        "running",
    )
    later = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["backfill-first"]},
        },
    )
    assert [
        (item["input"], item["state"], item["seen"])
        for item in page_state(page_dir)["workflows"]
        if item["input"] is not None
    ] == [(later["id"], "waiting", False)]


def test_a_start_is_one_log_record_read_at_the_status_and_the_move(
    page_dir, capsys, monkeypatch
):
    """`leaf task start` writes one record, in the log rather than the status file:
    the page's status reads its line, and so does the receipt on the move it names,
    under the user's own words. A pickup leaves it running, a `waiting` declaration
    puts it down, and the move's answer ends it."""
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "why?"}
    )
    [unowed] = command_findings(
        "task", "start", page_dir, "nope", "--text", "reading the traces"
    )
    assert unowed.code == "unowed-start"
    assert _start(page_dir, "c1", "").exit_code != 0

    monkeypatch.setenv("LEAF_AGENT", "Trace reader")
    started = _start(page_dir, "c1", "reading the traces")
    assert started.exit_code == 0, started.output
    record = json.loads(started.output.splitlines()[-1])
    assert (record["item"], record["text"], record["agent"]) == (
        "c1",
        "reading the traces",
        "Trace reader",
    )
    live = page_state(page_dir)
    assert "claims" not in live
    [workflow] = live["workflows"]
    assert (workflow["state"], workflow["detail"], workflow["agent"]) == (
        "running",
        "reading the traces",
        "Trace reader",
    )
    assert live["activity"]["detail"] == "reading the traces"

    # A waiting line answers nothing on the thread, but it puts the start down: the
    # move is no longer in hand until the agent starts it again.
    assert leaf("page", "open", page_dir).exit_code == 0
    assert [
        (item["state"], item["seen"]) for item in page_state(page_dir)["workflows"]
    ] == [("waiting", False)]
    assert _start(page_dir, "c1", "reading the traces").exit_code == 0

    # Nor does a pickup replace the start: it is a durable transport fact about the
    # exact user events.
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "c2",
            "author": "user",
            "parent": "c1",
            "text": "and this?",
        },
    )
    state = page_state(page_dir)
    assert [
        (workflow["input"], workflow["state"], workflow["seen"])
        for workflow in state["workflows"]
    ] == [("c1", "running", True), ("c2", "waiting", False)]
    # The thread owes one answer, the newest input's, which no turn has taken in.
    assert state["activity"]["counts"] == {
        "running": 0,
        "waiting": 0,
        "blocked": 0,
        "unseen": 1,
    }
    assert transaction_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    delivered(capsys)
    *_, pickup = (
        e for e in events_model.read_events(page_dir) if e["kind"] == "pickup"
    )
    assert pickup["kind"] == "pickup"
    assert pickup["events"] == ["c1", "c2"]
    assert [
        (workflow["input"], workflow["state"], workflow["seen"])
        for workflow in page_state(page_dir)["workflows"]
    ] == [("c1", "running", True), ("c2", "waiting", True)]

    # The reply that answers the thread ends the start with the moves it answers.
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, "c2"),
                "--text",
                "Because.",
                "--title",
                "Thread title",
            ],
        )
        .exit_code
        == 0
    )
    assert page_state(page_dir)["workflows"] == []


def test_a_recordless_receipt_from_a_stale_revision_waits_for_a_later_note(page_dir):
    """A completion move can arrive from a live revision after another is active.

    A version note older than the move cannot answer it. The agent can start the move
    all the same, and the next version that records it settles the move and ends the
    start with it.
    """
    work_page = PAGE.replace(PAGE_GROUP, '<lf-options id="plan-choice" multiple>', 1)
    (page_dir / "index.html").write_text(work_page)
    publish(page_dir)
    (page_dir / "index.html").write_text(
        work_page.replace("<title>t</title>", "<title>t · v2</title>")
    )
    advanced = stamp(page_dir, "Checked the surrounding plan")
    assert advanced.exit_code == 0, advanced.output

    # The user still has r1 open after r2 became active. That move is new work,
    # not something the earlier r2 note could already have answered.
    answer = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan-choice",
            "action": "answer",
            "detail": {},
        },
    )
    before_state = page_state(page_dir)
    before_pickup = before_state["activity"]
    acknowledgments = before_state["workflows"]
    assert any(receipt["input"] == answer["id"] for receipt in acknowledgments)
    assert before_pickup["presence"] == "away"
    assert before_pickup["counts"] == {
        "running": 0,
        "waiting": 0,
        "blocked": 0,
        "unseen": 1,
    }
    assert [item["answer"] for item in owed_answers(page_dir)] == [
        {"kind": "markup", "action": answer["id"]}
    ]

    claim = record_claim(page_dir)
    with transaction_model.PageTransaction(page_dir) as transaction:
        delivery_model.record_pickup(
            transaction,
            [answer],
            session=claim["id"],
            turn=claim["turn"],
        )
    after_pickup = activity_reading(page_dir)
    assert after_pickup["state"] == "running"
    assert [item["handling"] for item in after_pickup["obligations"]] == [True]
    assert [item["input"] for item in owed_answers(page_dir)] == [answer["id"]]

    claimed = _start(page_dir, answer["id"], "checking the completed choice")
    assert claimed.exit_code == 0, claimed.output
    [working_receipt] = page_state(page_dir)["workflows"]
    assert working_receipt["state"] == "running"
    (page_dir / "index.html").write_text(
        work_page.replace("<title>t</title>", "<title>t · v3</title>")
    )
    answered = stamp(page_dir, "Answered the completed choice")
    assert answered.exit_code == 0, answered.output

    acknowledgments = page_state(page_dir)["workflows"]
    assert not any(receipt["input"] == answer["id"] for receipt in acknowledgments)


def test_a_start_is_settled_by_log_order_not_a_second_precision_clock(page_dir):
    """A reply can land in the same timestamp second as the start. The reply that
    answers the move ends the start by the log alone, without asking two equal
    wall-clock strings which happened first."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    started = _start(page_dir, comment["id"], "checking")
    assert started.exit_code == 0, started.output
    start = json.loads(started.output.splitlines()[-1])

    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": "Because the retry won.",
            "ts": start["ts"],
        },
    )
    assert page_state(page_dir)["workflows"] == []


def test_reopening_a_thread_reveals_its_started_move(page_dir):
    """Resolution hides a thread's moves while reopening restores an unanswered one,
    still in hand under the start that named it."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    assert _start(page_dir, comment["id"], "checking").exit_code == 0
    append_carried_log_record(
        page_dir,
        {"kind": "resolve", "author": "agent", "parent": comment["id"]},
    )
    append_carried_log_record(
        page_dir,
        {"kind": "unresolve", "author": "user", "parent": comment["id"]},
    )

    [workflow] = page_state(page_dir)["workflows"]
    assert (workflow["input"], workflow["state"]) == (comment["id"], "running")


def test_a_put_down_start_holds_no_input_in_hand(page_dir):
    """A `waiting` declaration puts down the start before it, so admission no longer
    counts the started move as work in hand: a later edit on its widget stays quiet,
    as it did before the start, and wakes nobody."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</section>",
            '<lf-draft id="draft"><pre>Blue room.</pre></lf-draft></section>',
        )
    )
    publish(page_dir)

    def edit(text):
        return append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "draft",
                "action": "edit",
                "detail": {"value": text},
            },
        )

    first = edit("Green room.")
    assert not first["attention"]
    assert _start(page_dir, first["id"], "Reading the draft").exit_code == 0
    declared = CliRunner().invoke(cli_model.cli, ["page", "open", str(page_dir)])
    assert declared.exit_code == 0, declared.output
    [workflow] = page_state(page_dir)["workflows"]
    assert (workflow["input"], workflow["state"], workflow["seen"]) == (
        first["id"],
        "waiting",
        False,
    )
    assert not edit("Red room.")["attention"]


def test_the_input_a_reply_answers_moves_to_its_lists_done():
    """A reply moves the record of the input it answers from On <agent> to its Done,
    answered by the input's first answer in the log, whichever thread that answer
    stands in. The log can hold a second answer to the same input, which adds no row.
    Done reads the answer's instant as Leaf reads any timestamp it admits, a `z`
    suffix included."""
    from model_folds import leaf_page, served_reading

    reading = served_reading(
        leaf_page("Review", "<h1>Review</h1>"),
        (
            {"kind": "comment", "text": "Q"},
            {"kind": "comment", "text": "Another"},
            *(
                {
                    "kind": "reply",
                    "author": "agent",
                    "agent": "Agent",
                    "parent": parent,
                    "responds": "e1",
                    "text": text,
                    "ts": ts,
                }
                for parent, text, ts in (
                    ("e2", "First answer", "2026-10-13T10:00:00z"),
                    ("e1", "Second answer", "2026-10-13T11:00:00+00:00"),
                )
            ),
        ),
    )
    [view] = reading["browser"]["views"].values()
    records = {item["id"]: item for item in view["obligations"]}
    done = [
        (
            item["owner"],
            item["kind"],
            item["id"],
            item["thread"],
            records[item["id"]]["answer"]["event"]["id"],
            records[item["id"]]["answer"]["event"]["ts"],
        )
        for item in view["queues"]["done"]
    ]
    assert done == [
        ("agent", "update", "update:e1", "e2", "e3", "2026-10-13T10:00:00z")
    ]
    assert [item["id"] for item in view["queues"]["on_agent"]] == ["update:e2"]


@pytest.mark.parametrize("route", ["open", "proactive", "addressed"])
def test_explicit_message_obligations_need_no_html(page_dir, route):
    """Every author route atomically sends the question and registers On Me."""
    publish(page_dir)
    if route == "open":
        command = ["thread", "create", page_dir]
        thread = None
    else:
        root = append_carried_log_record(
            page_dir,
            {
                "kind": "comment",
                "author": "user" if route == "addressed" else "agent",
                "revision": 1,
                "text": "Release notes",
            },
        )
        thread = root["id"]
        command = (
            ["thread", "reply", response_reference(page_dir, thread)]
            if route == "addressed"
            else ["thread", "reply", page_dir, thread]
        )
    message = written(
        leaf(
            *command,
            *("--title", "Release environment"),
            *("--obligation", "--text", "Which environment?"),
        )
    )
    identity = f"message:{message['id']}"
    state = state_json(page_dir)
    [item] = [item for item in state["obligations"] if item["id"] == identity]
    assert item["source"] == {"kind": "message", "id": message["id"]}
    assert (item["thread"], item["message"], item["prompt"]) == (
        thread or message["id"],
        message["id"],
        {"text": "Which environment?", "target": None},
    )
    assert ("message", identity) in kinds(state["queues"]["on_user"])
    assert "html" not in message
    answer = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": thread or message["id"],
            "text": "Staging.",
        },
    )
    [item] = [
        item for item in state_json(page_dir)["obligations"] if item["id"] == identity
    ]
    assert standing_model.answered(item)
    assert item["answer"] == {
        "value": {"text": "Staging."},
        "event": {key: answer[key] for key in ("id", "kind", "seq", "ts", "author")},
    }


@pytest.mark.parametrize("attach_first", [True, False])
def test_thread_task_preserves_its_reaction_root(page_dir, attach_first):
    """A task keeps the thread a reaction opened when the user takes the reaction
    back, its place reading Deleted, and cannot attach after Undo removed it."""
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "emoji": "👍",
            "anchor": {"section": "plan"},
        },
    )
    task = {
        "kind": "todo",
        "author": "agent",
        "subject": {"kind": "thread", "id": root["id"]},
        "title": "Check on a phone",
    }
    undo = {"kind": "undo", "author": "user", "undoes": root["id"]}
    if attach_first:
        opened = append_command(page_dir, task)
        append_command(page_dir, undo)
        [kept] = [
            thread
            for thread in served_thread(
                full_state(page_dir, events_model.read_events(page_dir))["browser"]
            )["threads"]
            if thread["id"] == root["id"]
        ]
        assert kept["root"]["withdrawn"]["was"] == "👍"
        # The thread stays a thread, so the agent may attach more work to it.
        append_command(page_dir, {**task, "title": "Check on a tablet"})
        assert opened["id"] in {
            item["id"] for item in state_json(page_dir)["queues"]["on_agent"]
        }
    else:
        append_command(page_dir, undo)
        with pytest.raises(events_model.EventRefused, match="thread"):
            append_command(page_dir, task)


def test_obligations_are_not_progress_or_user_authored(page_dir):
    """The admission boundary prevents unanswerable requests on non-agent messages."""
    publish(page_dir)
    root = written(
        leaf(
            "thread", "create", page_dir, "--text", "Status", "--title", "Agent thread"
        )
    )
    before = events_model.read_events(page_dir)
    for extra in (
        {"author": "user"},
        {"ephemeral": True},
        {"todo": "Work"},
        {"failure": "failed", "responds": root["id"]},
    ):
        with pytest.raises(events_model.EventRefused):
            append_command(
                page_dir,
                {
                    "kind": "reply",
                    "author": "agent",
                    "parent": root["id"],
                    "text": "Question?",
                    "obligation": True,
                    **extra,
                },
            )
    assert events_model.read_events(page_dir) == before
