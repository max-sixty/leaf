"""To-dos hold work the agent owes until it ends them, a start takes a move or to-do in
hand, and the two queues say what is on the user and what is on the agent."""

import json
import threading
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from interact_support import (
    FLOW_PAGE,
    PAGE,
    STATED_TIMEOUT,
    ModelPage,
    _start,
    activity_reading,
    append_carried_log_record,
    append_command,
    command_findings,
    delivered,
    freeze_events,
    obligations_on_user,
    open_todos,
    owed_answers,
    page_packages,
    page_state,
    publish,
    record_claim,
    refused_on,
    response_reference,
    served_obligations,
    served_thread,
    served_todos,
    serving,
    stamp,
    state_json,
)

from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_contracts as contracts_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import plans as plans_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import standing as standing_model
from leaf import state as state_model
from leaf import thread as thread_model
from leaf import todos as todos_model
from leaf.event_contracts import append_admitted
from leaf.findings import Rejected
from leaf.registry import storage as registry_storage
from leaf.served_state.page import full_state
from leaf.state import EVENTS_FILE
from leaf_dev.page_fixtures import package_selection_args


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
    for flags in (
        [],
        ["--done", "--todo", "Tighten"],
        ["--ephemeral", "--done"],
        # Markup with no question in it asks nothing back, so it declares nothing.
        ["--markup", '<figure id="sketch"><p>A sketch.</p></figure>'],
    ):
        result = leaf("thread", "reply", reference, "--text", "On it.", *flags)
        assert result.exit_code != 0, (flags, result.output)
    assert kinds(state_json(page_dir)["queues"]["on_agent"]) == [
        ("update", f"update:{comment['id']}")
    ]
    reply = written(leaf("thread", "reply", reference, "--text", "Done.", "--done"))
    assert "todo" not in reply
    assert state_json(page_dir)["queues"] == {"on_user": [], "on_agent": []}


def test_a_plan_arranges_todos_obligations_and_plain_steps_without_owning_them(
    page_dir,
):
    """The plan nests steps by depth and shows a named item's own state, and a
    rewrite that leaves a to-do out leaves it owed on the agent's list."""

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
    written(
        plan(
            [
                {"depth": 0, "title": "Review the change", "state": "working"},
                {"depth": 1, "title": "Check the diffs", "state": "done"},
                {"depth": 1, "title": "Draft the response", "state": "working"},
                {"depth": 2, "item": todo["id"]},
                {"depth": 1, "item": item["id"]},
                {"depth": 1, "title": "Post it", "state": "dropped"},
            ]
        )
    )
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
        "running",
        None,
        "agent",
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
    cut = goal["steps"][1]["steps"][0]
    assert cut["item"] == {"kind": "todo", "id": todo["id"]}
    assert cut["since"] == cut["running"]["ts"]

    # A question answered elsewhere reads done, and a rewrite that leaves the to-do
    # out leaves it owed.
    question = written(
        leaf("thread", "create", page_dir, "--text", "Merge?", "--obligation")
    )
    asked = f"message:{question['id']}"
    written(leaf("task", "end", page_dir, asked, "done", "--text", "In chat"))
    written(
        plan(
            [
                {"depth": 0, "title": "Review the change", "state": "done"},
                {"depth": 1, "item": asked},
            ]
        )
    )
    [goal] = state_json(page_dir)["plan"]["steps"]
    assert [
        (step["item"]["id"], step["state"], step["outcome"]) for step in goal["steps"]
    ] == [(asked, "done", "done")]
    assert ("todo", todo["id"]) in kinds(state_json(page_dir)["queues"]["on_agent"])
    outline = page_dir.parent / "plan.json"
    for steps, code in (
        ([{"depth": 1, "title": "Too deep", "state": "open"}], "plan-depth"),
        ([{"depth": 0, "item": "no-such-item"}], "unknown-plan-item"),
        (
            [{"depth": depth, "title": "Deep", "state": "open"} for depth in range(10)],
            "invalid-event",
        ),
    ):
        outline.write_text(json.dumps(steps))
        [refused] = command_findings("task", "plan", page_dir, "--file", outline)
        assert refused.code == code
    # A step close to one of the two shapes is refused at the field it gets wrong.
    outline.write_text(json.dumps([{"depth": 0, "title": "Ship", "state": "active"}]))
    [unknown] = command_findings("task", "plan", page_dir, "--file", outline)
    assert (unknown.code, unknown.values["field"]) == (
        "invalid-event",
        "/steps/0/state",
    )
    written(plan([]))
    assert state_json(page_dir)["plan"] is None


def test_a_goal_counts_only_the_steps_that_ended_done(task_log):
    """A to-do that failed ended, but finished nothing, so its goal reads none done."""
    append, log = task_log
    todo = append("todo", subject={"kind": "page"}, title="Rebuild the chart")
    append("todo_end", todo=todo["id"], outcome="failed", detail="The data is gone")
    append(
        "plan",
        steps=[
            {"depth": 0, "title": "Chart the year", "state": "working"},
            {"depth": 1, "item": todo["id"]},
        ],
    )
    reading = plans_model.plan_reading(log, set(), todos_model.TodoReading(log).todos)
    assert reading is not None
    [goal] = reading["steps"]
    [step] = goal["steps"]
    assert (step["state"], step["outcome"]) == ("done", "failed")
    assert (goal["done"], goal["total"]) == (0, 1)


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
            **({"text": "Warm."} if answer_kind == "reply" else {"token": "keep"}),
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


def test_an_obligation_ends_at_the_reaction_that_settles_it(page_dir):
    """A reaction answers an obligation only when its token settles (`$reactions`): one
    that doesn't leaves the obligation on the user, and the one that does is the
    outcome the ended obligation records."""
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
        )
    )

    def react(token):
        return append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "user",
                "revision": 1,
                "parent": question["id"],
                "token": token,
            },
        )

    react("clarify")
    assert standing_model.is_open(
        next(
            item
            for item in state_json(page_dir)["obligations"]
            if item["source"]["id"] == question["id"]
        )
    )
    keep = react("keep")
    assert standing_model.answered(
        next(
            item
            for item in state_json(page_dir)["obligations"]
            if item["source"]["id"] == question["id"]
        )
    )
    served = full_state(page_dir, events_model.read_events(page_dir))
    [answered] = served_obligations(served["browser"])["all"]
    assert standing_model.answered(answered)
    assert answered["answer"]["event"]["id"] == keep["id"]


def test_a_thread_is_on_you_once_however_many_moves_it_holds_for_you(page_dir):
    """A message whose reply failed is the user's to send again, an obligation of its
    own on On Me. A question the agent then leaves in its thread is a second
    obligation there, listed ahead of it, and the thread reads as that question: `m`
    stops at a thread once (queue-walk.js)."""
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


@pytest.mark.parametrize(
    "claim, refusal",
    [("task start", "unowed-start"), ("progress reply", "superseded-reply")],
)
def test_a_claim_reaching_the_door_as_its_update_settles_is_refused(
    page_dir, monkeypatch, claim, refusal
):
    """An agent decides to take an update in hand from a delivery it read earlier, so
    the update may settle between that reading and its claim. The door reads whether
    the update is still owed under the same log lock as the append, so a claim that
    reaches the lock while the settlement holds it is refused, and the page never
    reads Working on a settled update."""
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
            todos_model.cmd_start(page_dir, comment["id"], "Tightening it")
        else:
            thread_model.post_response(reference, "Tightening it", ephemeral=True)

    refusals = []

    def run_claim():
        try:
            take_in_hand()
        except Rejected as refused:
            refusals.append(refused)

    claiming = threading.Thread(target=run_claim, name="claim")
    with service_model.PageTransaction(page_dir) as page:
        claiming.start()
        assert claim_waits.wait(STATED_TIMEOUT)
        append_admitted(
            page, {"kind": "resolve", "author": "user", "parent": comment["id"]}
        )
    claiming.join(STATED_TIMEOUT)
    assert not claiming.is_alive()

    [refused] = refusals
    assert refused.findings[0].code == refusal
    assert events_model.read_events(page_dir)[-1]["kind"] == "resolve"
    state = state_json(page_dir)
    assert state["workflows"] == []
    assert state["activity"]["state"] != "running"


def test_a_thread_todo_runs_under_its_start_line(page_dir):
    """A thread waits on a started to-do by its id, and the to-do's record carries the
    line its start runs under."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Rebuild it."},
    )
    todo = written(
        leaf(
            "thread",
            "reply",
            response_reference(page_dir, comment["id"]),
            "--text",
            "On it.",
            "--todo",
            "Rebuild the chart",
        )
    )
    written(
        leaf("task", "start", page_dir, todo["id"], "--text", "Waiting on the build")
    )
    state = state_json(page_dir)
    [thread] = state["threads"]
    assert thread["attention"] == todo["id"]
    [record] = open_todos(state)
    assert (record["id"], record["line"]["text"]) == (
        todo["id"],
        "Waiting on the build",
    )


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


@pytest.mark.parametrize("outcome", ["done", "failed", "dropped"])
def test_only_the_latest_starting_session_can_complete_agent_work(task_log, outcome):
    """Log order transfers authority for every outcome, even while work is put down."""
    append, log = task_log
    todo = append("todo", session="opener", subject={"kind": "page"}, title="Plan")
    for session in ("older", "newer"):
        latest = append("start", session=session, item=todo["id"], text="Working")
    append("status", session="newer", state="waiting")
    assert todos_model.TodoReading(log).owed[0]["line"] is None

    for session in ("older", "opener", "third", None):
        with pytest.raises(events_model.EventRefused) as refused:
            append("todo_end", session=session, todo=todo["id"], outcome=outcome)
        finding = refused_on(refused.value)
        assert (finding.code, finding.values) == (
            "todo-execution",
            {
                "todo": todo["id"],
                "start": latest["id"],
                "session": "newer",
                "kind": "todo_end",
            },
        )
    completed = append("todo_end", session="newer", todo=todo["id"], outcome=outcome)
    [ended] = todos_model.TodoReading(log).todos
    assert (ended["state"], ended["outcome"]) == ("done", outcome)
    assert ended["end"]["event"]["id"] == completed["id"]


def test_explicit_starts_transfer_completion_authority_back_and_between_tasks(task_log):
    """A session can retake work; a start on another item transfers only that item."""
    append, log = task_log
    todos = [
        append("todo", subject={"kind": "page"}, title=title)
        for title in ("Plan", "Glossary")
    ]
    for session in ("older", "newer", "older"):
        append("start", session=session, item=todos[0]["id"], text="Working")
    append("start", session="newer", item=todos[1]["id"], text="Other work")
    with pytest.raises(events_model.EventRefused) as refused:
        append("todo_end", session="newer", todo=todos[0]["id"], outcome="done")
    assert refused_on(refused.value).code == "todo-execution"
    for todo, session in zip(todos, ("older", "newer"), strict=True):
        append("todo_end", session=session, todo=todo["id"], outcome="done")
    assert todos_model.TodoReading(log).owed == []


def test_unstarted_and_anonymously_started_tasks_remain_completable(task_log):
    """Opening creates no session ownership; an anonymous start is a real start."""
    append, log = task_log
    unstarted = append("todo", session="opener", subject={"kind": "page"}, title="Plan")
    append("todo_end", session="another", todo=unstarted["id"], outcome="done")
    anonymous = append("todo", subject={"kind": "page"}, title="Glossary")
    latest = append("start", item=anonymous["id"], text="Working")
    with pytest.raises(events_model.EventRefused) as refused:
        append("todo_end", session="identified", todo=anonymous["id"], outcome="done")
    assert refused_on(refused.value).values == {
        "todo": anonymous["id"],
        "start": latest["id"],
        "session": None,
        "kind": "todo_end",
    }
    append("todo_end", todo=anonymous["id"], outcome="done")
    assert todos_model.TodoReading(log).owed == []


def test_delayed_completion_keeps_its_session_authority_after_claim_and_turn_changes(
    page_dir,
):
    """A later turn and a different watcher do not make a posting session obsolete."""
    publish(page_dir)
    todo = written(
        leaf("task", "create", page_dir, "page", "--title", "Draft the plan")
    )
    record_claim(page_dir, id=todo["session"], turn="earlier-turn")
    start = written(
        leaf("task", "start", page_dir, todo["id"], "--text", "Drafting the plan")
    )
    assert start["turn"] == "earlier-turn"

    record_claim(page_dir, id=todo["session"], turn="later-turn")
    continued = written(
        leaf("task", "start", page_dir, todo["id"], "--text", "Continuing the plan")
    )
    assert continued["turn"] == "later-turn"
    # Claims govern who watches the page; completion comes from the poster's voice.
    record_claim(page_dir, id="another-watcher", turn="watcher-turn")
    completed = written(leaf("task", "end", page_dir, todo["id"], "done"))
    assert completed["session"] == continued["session"] == start["session"]
    assert open_todos(state_json(page_dir)) == []


WORK_PAGE = FLOW_PAGE.replace(
    '<lf-diagram id="flow">',
    '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
    '  <lf-card id="rollout-card"><strong>Ship the rollout</strong> '
    "Check the fallback before cutover.</lf-card>\n"
    '</lf-column></lf-board>\n<lf-diagram id="flow">',
)


def test_a_widget_todo_needs_a_seat_and_a_completing_stamp_ends_it(page_dir):
    """A to-do on a page widget needs a widget that declares `x-work` or holds an
    unsettled move. Dropping its widget leaves it open; `page stamp --completes`
    ends it done, citing that version."""
    (page_dir / "index.html").write_text(WORK_PAGE)
    publish(page_dir)
    [no_seat] = command_findings(
        "task", "create", page_dir, "flow", "--title", "Redraw the graph"
    )
    assert no_seat.code == "no-work-seat"

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
    [ended] = todos_model.TodoReading(events_model.read_events(page_dir)).todos
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


def test_a_stale_completing_stamp_refuses_before_publishing_or_settling_work(page_dir):
    """A stamp uses the same authority rule for every task it completes, atomically."""
    source = page_dir / "index.html"
    source.write_text(WORK_PAGE)
    publish(page_dir)
    todos = [
        written(leaf("task", "create", page_dir, "rollout-card", "--title", title))
        for title in ("Check fallback", "Check rollout")
    ]
    for todo in todos:
        written(
            leaf("task", "start", page_dir, todo["id"], "--text", "Checking rollout")
        )
    continued = append_command(
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
    before = events_model.read_events(page_dir)
    revisions = files_model.list_revisions(page_dir)
    [refused] = command_findings(
        "page",
        "stamp",
        page_dir,
        "--text",
        "Checks complete",
        "--completes",
        "rollout-card",
    )
    assert refused.code == "todo-execution"
    assert refused.values == {
        "todo": todos[-1]["id"],
        "start": continued["id"],
        "session": "newer",
        "kind": "note",
    }
    assert events_model.read_events(page_dir) == before
    assert files_model.list_revisions(page_dir) == revisions
    assert len(todos_model.TodoReading(before).owed) == 2

    append_command(
        page_dir,
        {
            "kind": "start",
            "author": "agent",
            "session": todos[-1]["session"],
            "item": todos[-1]["id"],
            "text": "Retaking the checks",
        },
    )
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
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>', 1)
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


def test_a_decision_ends_through_its_state_and_the_agent_ends_a_question(page_dir):
    """A decision widget's obligation follows its state. The agent ends a question `done`
    when the user answered it elsewhere and `dropped` when it no longer applies;
    neither invents the user's answer, and `failed` says nothing about an obligation."""
    asking(page_dir)
    [item] = obligations_on_user(state_json(page_dir))
    asked = []
    for text, words in (("Which colour?", "Warm or cool?"), ("Which font?", "Serif?")):
        comment = append_carried_log_record(
            page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": text},
        )
        question = written(
            leaf(
                "thread",
                "reply",
                response_reference(page_dir, comment["id"]),
                "--text",
                words,
                "--obligation",
            )
        )
        asked.append(f"message:{question['id']}")
    answered_elsewhere, dropped = asked
    [refused] = command_findings(
        "task", "end", page_dir, item["id"], "dropped", "--text", "Decided in chat"
    )
    assert refused.code == "widget-obligation"
    [refused] = command_findings(
        "task", "end", page_dir, answered_elsewhere, "failed", "--text", "No reply"
    )
    assert refused.code == "failed-question"
    assert [item["id"] for item in state_json(page_dir)["queues"]["on_user"]] == [
        item["id"],
        *asked,
    ]

    written(
        leaf(
            "task",
            "end",
            page_dir,
            answered_elsewhere,
            "done",
            "--text",
            "Warm, in chat",
        )
    )
    written(
        leaf("task", "end", page_dir, dropped, "dropped", "--text", "Font is fixed")
    )
    state = state_json(page_dir)
    assert [item["id"] for item in state["queues"]["on_user"]] == [item["id"]]
    assert [thread["attention"] for thread in state["threads"]] == [None, None]
    refused = leaf("task", "end", page_dir, dropped, "done", "--text", "Asked again")
    assert refused.exit_code != 0
    assert f"obligation {dropped!r} is already withdrawn" in refused.output

    served = full_state(page_dir, events_model.read_events(page_dir))
    assert served_todos(served["browser"]) == []
    ended = {
        record["id"]: (
            record["state"],
            record["outcome"],
            record["answer"],
            record["end"]["detail"],
            record["end"]["event"]["author"],
        )
        for record in served_obligations(served["browser"])["all"]
    }
    assert ended == {
        answered_elsewhere: ("done", "done", None, "Warm, in chat", "agent"),
        dropped: ("done", "dropped", None, "Font is fixed", "agent"),
    }
    [view] = served["browser"]["views"].values()
    records = {record["id"]: record for record in view["obligations"]}
    done = {
        item["id"]: (
            records[item["id"]]["outcome"],
            records[item["id"]]["end"]["detail"],
            records[item["id"]]["end"]["event"]["ts"] is not None,
        )
        for item in view["queues"]["done"]
        if item["kind"] == "message"
    }
    assert done == {
        answered_elsewhere: ("done", "Warm, in chat", True),
        dropped: ("dropped", "Font is fixed", True),
    }

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
    [answered] = command_findings("task", "end", page_dir, item["id"], "done")
    assert answered.code == "widget-obligation"


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
    no revision can write a frozen widget's state. The delivery of their words names
    the choice in `waiting`, and the agent's `done` end takes it off On Me."""
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
            "Which store should own sessions?",
            "--markup",
            '<lf-options id="store" choose>'
            '<lf-option id="store-account"><strong>Account store</strong></lf-option>'
            '<lf-option id="store-own"><strong>Their own store</strong></lf-option>'
            "</lf-options>",
        )
    )
    said = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "Account."},
    )
    [delivered_words] = freeze_events(page_dir, [said])["batches"][0]["events"]
    assert delivered_words["waiting"] == [
        {"id": "widget:store", "text": "Which store should own sessions?"}
    ]
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

    written(leaf("task", "end", page_dir, "widget:store", "done", "--text", "In words"))
    state = state_json(page_dir)
    assert "widget:store" not in [item["id"] for item in state["queues"]["on_user"]]
    [record] = [item for item in state["obligations"] if item["id"] == "widget:store"]
    # Answered elsewhere: done, with the agent's end and no answer of the user's.
    assert (record["state"], record["outcome"], record["answer"]) == (
        "done",
        "done",
        None,
    )
    assert record["end"]["detail"] == "In words"


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
    version.write_text(
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>', 1)
    )
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
        "waiting": 1,
        "blocked": 0,
        "unseen": 1,
    }
    assert service_model.claim_page(page_dir)
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
            ],
        )
        .exit_code
        == 0
    )
    assert page_state(page_dir)["workflows"] == []


def test_revendoring_can_change_x_work_while_the_target_holds_a_todo(page_dir):
    """x-work admits a task on a widget; it is not the task's only later seat.

    Re-vendoring can remove that declaration while the live widget remains, because
    the page-edge margin entry continues to present the task already admitted.
    """
    work_page = PAGE.replace(
        "</section>",
        '<lf-board id="rollout"><lf-column id="rollout-now" label="Now">\n'
        '  <lf-card id="rollout-card"><strong>Ship the rollout</strong></lf-card>\n'
        "</lf-column></lf-board>\n</section>",
    )
    (page_dir / "index.html").write_text(work_page)
    publish(page_dir)
    opened = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "create",
            str(page_dir),
            "rollout-card",
            "--title",
            "Check the rollout",
        ],
    )
    assert opened.exit_code == 0, opened.output
    card = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())[
        "lf-card"
    ]
    card.pop("x-work")
    layer = Path.cwd() / ".leaf"
    layer.mkdir()
    (layer / "registry.json").write_text(json.dumps({"lf-card": card}))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    registry = registry_storage.load_registry(page_dir)
    assert "x-work" not in registry["lf-card"]
    [todo] = open_todos(state_json(page_dir))
    assert todo["source"]["subject"] == {"kind": "widget", "id": "rollout-card"}


def test_a_recordless_receipt_from_a_stale_revision_waits_for_a_later_note(page_dir):
    """A completion move can arrive from a live revision after another is active.

    A version note older than the move cannot answer it. The agent can start the move
    all the same, and the next version that records it settles the move and ends the
    start with it.
    """
    work_page = PAGE.replace(
        "<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1
    )
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
        "waiting": 1,
        "blocked": 0,
        "unseen": 1,
    }
    assert [item["answer"] for item in owed_answers(page_dir)] == [
        {"kind": "markup", "action": answer["id"]}
    ]

    claim = record_claim(page_dir)
    with service_model.PageTransaction(page_dir) as transaction:
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


@pytest.mark.parametrize("target", ["effort", "flag-first"])
def test_only_a_declared_widget_work_seat_is_admitted(page_dir, target):
    """A content model says what authors may put inside a widget, not whether core
    may add local chrome there. Inline prose has no block slot, and a prose option is
    itself the click target of its holder; neither becomes a seat by inference."""
    version = page_dir / "index.html"
    version.write_text(
        PAGE.replace(
            '<small class="tag">effort: low</small>',
            '<lf-gloss id="effort" tip="A short task.">effort: low</lf-gloss>',
        )
    )
    publish(page_dir)

    [claimed] = command_findings(
        "task", "create", page_dir, target, "--title", "Check the estimate"
    )
    assert claimed.code == "no-work-seat"


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
def test_explicit_message_obligations_need_no_markup(page_dir, route):
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
    message = written(leaf(*command, "--obligation", "--text", "Which environment?"))
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
    assert "markup" not in message
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
            "token": "keep",
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
        assert kept["root"]["withdrawn"]["was"] == "keep"
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
    root = written(leaf("thread", "create", page_dir, "--text", "Status"))
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
