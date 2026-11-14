"""Forks of a Claude Code session: each state a thread with waiting user messages
moves through (`forks.py`'s table), what Leaf keeps back from the session meanwhile, and how
the message reads once a fork has posted the agent's working line and handed the
thread over."""

import hashlib
import json
import os
import re
import shlex
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Condition, Event, Thread
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    lock_contention,
    page_packages,
    serving,
    stamp,
)

from leaf import activity as activity_model
from leaf import clerk as clerk_model
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import file_changes as file_changes_model
from leaf import forks as forks_model
from leaf import harness as harness_model
from leaf import holding as holding_model
from leaf import hook_transport as hook_transport_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import page_memory as page_memory_model
from leaf import presence as presence_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import session_runtime as session_runtime_model
from leaf import state as state_model
from leaf import thread as thread_model
from leaf import todos as todos_model
from leaf.interaction_log import read_interactions
from leaf.registry import kernel as kernel_model
from leaf.served_state.context import read_page
from leaf.served_state.reading import outside_inputs
from leaf.service import PageTransaction
from leaf.state import session_file

# What Leaf's Claude Code hooks module gives the pages follower of session s1, asking
# for forks from the module this Leaf ships, by its source's digest (`hooks.cmd_pages`).
FOLLOWER = {
    "session_id": "s1",
    "forks": True,
    "module": hashlib.sha256(
        (state_model.PLUGIN_ROOT / "hooks" / "claude-code.ts").read_bytes()
    ).hexdigest(),
}


def past_the_take() -> None:
    """Wait for the clock to leave the millisecond session s1's lane was taken in,
    since a message admitted within it stays with the session (`forks.kept_back`)."""
    since = forks_model.lane_since("s1")
    assert since is not None
    while time.time() < since + 0.001:
        time.sleep(0.0005)


def take_lane():
    """Take session s1's forks lane, as its pages follower does, and wait past the
    take."""
    held = forks_model.take_lane("s1")
    past_the_take()
    return held


@pytest.fixture
def lane(claimed):
    """Session s1's forks lane, held as its pages follower holds it."""
    held = take_lane()
    yield held
    if not held.closed:
        leases_model.release_lease(held)


def said(page_dir, text: str, parent: str | None = None) -> dict:
    """The user's message, a comment opening a thread or a reply in one."""
    return append_carried_log_record(
        page_dir,
        {"kind": "reply", "parent": parent, "author": "user", "text": text}
        if parent
        else {"kind": "comment", "author": "user", "text": text},
    )


def kept_back(page_dir) -> list:
    with PageTransaction(page_dir) as page:
        return [
            (thread.thread, thread.inputs) for thread in forks_model.kept_back(page)
        ]


def deliverable(page_dir) -> list[str]:
    with PageTransaction(page_dir) as page:
        return [event["id"] for event in delivery_model.deliverable(page)]


def basis(page_dir, thread: str, *inputs: str) -> dict:
    return {"page": str(page_dir), "thread": thread, "inputs": list(inputs)}


def judged(line: str, work: str = "hand_over") -> str:
    """A fork's answer: the agent's working line, and who should do the work."""
    return json.dumps({"line": line, "work": work})


def context(capsys, event: str) -> str:
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": event, "session_id": "s1", "prompt_id": "p1"},
    )
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def forked(page_dir) -> list[str]:
    """The waiting messages the page's served reading words On it."""
    return presence_model.presence(page_dir, events_model.read_events(page_dir))[
        "forked"
    ]


def test_a_kept_back_message_gets_the_forks_working_line_and_goes_to_the_session(
    claimed, lane
):
    """A message in a thread the session hasn't received is kept back: not deliverable,
    so neither a hook nor the watch hands it over, while a fork writes the agent's
    working line, and it reads On it from the start. The line goes in as the agent's
    progress without taking the message in hand, and the thread goes to the session
    at once, still owing its answer and still reading On it until that answer."""
    asked = said(claimed, "Why a 2-second poll?")
    assert kept_back(claimed) == [(asked["id"], (asked["id"],))]
    assert deliverable(claimed) == []
    assert forked(claimed) == [asked["id"]]

    question = forks_model.ask("s1", basis(claimed, asked["id"], asked["id"]), [])
    assert question is not None
    assert question["prompt"].startswith(forks_model.LINE_OPENING)
    assert "Why a 2-second poll?" in question["prompt"]
    assert "ends where the session last sent it to the model" in question["prompt"]

    handed = forks_model.route(
        "s1",
        question["thread"],
        answer=judged(" checking why the poll is 2 s\n", "take"),
        failed=None,
    )
    # A fork that judges it could take the work still hands it over, for now, and
    # the diagnostics keep its judgment.
    assert (handed["outcome"], handed["work"]) == ("hand_over", "take")
    [line] = [
        event for event in events_model.read_events(claimed) if event["kind"] == "reply"
    ]
    assert line["id"] == handed["line"]
    assert (line["text"], line["session"], line["ephemeral"], line["parent"]) == (
        "checking why the poll is 2 s",
        "s1",
        True,
        asked["id"],
    )
    # The line is the agent's words, not the session's start: every reader but the
    # word keeps the message where its delivery is until the session takes it in hand.
    assert "start" not in line
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"]]
    assert session_file("s1", forks_model.HANDED.kind).resolve() in outside_inputs(
        claimed
    )
    with PageTransaction(claimed) as page:
        owed = delivery_model.current_responses(claimed, page.events)
    assert owed[asked["id"]]["kind"] == "reply"
    assert forked(claimed) == [asked["id"]]

    thread_model.post_reply(claimed, {"responds": asked["id"]}, "It matches the lease.")
    assert forked(claimed) == []


def taken_by_a_fork(page_dir, text: str) -> tuple[dict, dict]:
    """The user's message in a thread of its own, and what Leaf did as the line's
    fork judged its work a fork's, where the module makes forks that do it."""
    asked = said(page_dir, text)
    taken = forks_model.route(
        "s1",
        basis(page_dir, asked["id"], asked["id"]),
        answer=judged(f"looking into: {text}", "take"),
        failed=None,
        work_forks=True,
    )
    assert taken["outcome"] == "take", taken
    return asked, taken


def reading(page_dir) -> dict:
    """The page's presence and activity, as the hooks read them."""
    work = read_page(page_dir, events_model.read_events(page_dir)).work
    return {**work.presence, "activity": work.activity}


def agent_context(capsys, agent: str) -> str:
    """What a tool boundary of the agent its harness names `agent` adds to its
    context."""
    hooks_model.cmd_hook(
        "claude-code",
        {
            "hook_event_name": "PostToolBatch",
            "session_id": "s1",
            "prompt_id": "p1",
            "agent_id": agent,
        },
    )
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def answer_ref(page_dir, input_id: str) -> str:
    """The answer reference the newest pickup carrying one gave `input_id`."""
    return next(
        event["refs"][input_id]["ref"]
        for event in reversed(events_model.read_events(page_dir))
        if event["kind"] == "pickup" and input_id in event.get("refs", {})
    )


def test_a_fork_takes_work_it_judges_its_own_as_a_pickup_in_its_own_turn(
    claimed, lane, capsys
):
    """Where the module makes forks that do the work, a thread the line fork judges
    `take` goes to a fork in a turn Leaf opens for it: the log records that turn's
    pickup of the message, with the receipt and the answer reference the fork's
    delivery gives it, so every reader agrees who has it. While that turn runs the
    message is the fork's: nothing hands it to the main thread, a receipt for later
    input doesn't give it back, the main thread's prompt neither owes nor takes it
    in, and the page reads the agent at work on it."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    agent, turn = f"leaf-{asked['id']}", taken["turn"]
    assert taken["agent"] == agent
    assert turn in state_model.open_agent_turns("s1")
    assert taken["prompt"].startswith(forks_model.WORK_OPENING)
    assert "Which Python does the project need?" in taken["prompt"]
    # The fork's task offers each way it ends: an answer, one opening a to-do, or
    # the thread given back.
    assert "--todo" in taken["prompt"] and forks_model.HAND_BACK in taken["prompt"]
    [pickup] = [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"]
    assert (pickup["events"], pickup["phase"], pickup["session"], pickup["turn"]) == (
        [asked["id"]],
        "opened",
        "s1",
        turn,
    )
    assert answer_ref(claimed, asked["id"]) in taken["prompt"]
    with PageTransaction(claimed) as page:
        assert page.cursor >= asked["seq"]
    assert deliverable(claimed) == []
    [told] = clerk_model.queued("s1")
    assert agent in told and f"SendMessage {agent}" in told
    assert session_file("s1", state_model.AGENT_TURNS.kind).resolve() in outside_inputs(
        claimed
    )

    with PageTransaction(claimed) as page:
        delivery_model.record_receipt(page, page.events[-1]["seq"])
    state = reading(claimed)
    [owed] = state["activity"]["obligations"]
    assert (owed["input"], owed["stage"], owed["condition"]) == (
        asked["id"],
        "picked_up",
        None,
    )
    assert state["activity"]["kind"] == "working"
    assert activity_model.turn_obligations(state, watched=False) == []
    context(capsys, "UserPromptSubmit")
    assert [
        e["turn"] for e in events_model.read_events(claimed) if e["kind"] == "pickup"
    ] == [turn]


def test_the_fork_answers_with_its_own_reply_in_its_own_turn(
    claimed, lane, monkeypatch
):
    """The module marks the commands of the fork its harness started with the fork's
    agent id, so the fork's progress and answer, from the delivery Leaf gave it, post
    as the agent's, and its start names the fork's turn: the page reads the fork at
    work whatever the main thread's turn does, and the answer settles the message.
    As the fork's run ends its turn closes, and the main thread hears it answered."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    started = forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    assert started["outcome"] == "start"
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    ref = answer_ref(claimed, asked["id"])

    progress = thread_model.post_response(ref, "reading pyproject.toml", ephemeral=True)
    assert progress is not None
    assert (progress["start"], progress["turn"]) == (
        {"item": asked["id"]},
        taken["turn"],
    )
    state_model.close_session_turn("s1")
    activity = reading(claimed)["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "reading pyproject.toml",
    )

    answer = thread_model.post_response(ref, "Python 3.12 or later.", asks_back=False)
    assert answer is not None
    assert (answer["author"], answer["session"], answer["responds"]) == (
        "agent",
        "s1",
        asked["id"],
    )
    assert reading(claimed)["activity"]["obligations"] == []
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    ) == [{"page": str(claimed), "thread": asked["id"], "outcome": "answer"}]
    assert state_model.open_agent_turns("s1") == {}
    # The take's line, which the main thread never heard, leaves with the fork's end.
    [told] = clerk_model.queued("s1")
    assert "answered" in told, told
    # Another run of the agent ends nothing more.
    assert (
        forks_model.ended("s1", agent="agent-1", turn=None, answer="", failed=None)
        == []
    )


def test_a_to_do_the_fork_opens_stays_the_sessions_after_its_turn_ends(
    claimed, lane, monkeypatch
):
    """A fork that finds the work bigger than an answer opens a to-do with its reply
    (`leaf thread reply --todo`), from the delivery Leaf gave it. The reply answers
    the message, and the to-do is the session's: it stays open, on the session's
    page, after the fork's run ends, while the fork's start on it lapses with the
    fork's turn. The main thread hears that the fork answered and opened the to-do,
    by its text, which it now owes, rather than that the thread owes nothing."""
    asked, taken = taken_by_a_fork(claimed, "Why is the cold start slow?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    reply = thread_model.post_response(
        answer_ref(claimed, asked["id"]),
        "That needs a profile of the start; I've put it on the list.",
        todo="Profile the cold start",
    )
    assert reply is not None
    assert (reply["session"], reply["todo"]) == ("s1", "Profile the cold start")
    todos_model.cmd_start(claimed, reply["id"], "profiling the cold start")
    activity = reading(claimed)["activity"]
    assert activity["obligations"] == []
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "profiling the cold start",
    )

    clerk_model.heard("s1", clerk_model.queued("s1"))
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Opened a to-do.", failed=None
    ) == [
        {
            "page": str(claimed),
            "thread": asked["id"],
            "outcome": "todo",
            "todos": [reply["id"]],
        }
    ]
    [told] = clerk_model.queued("s1")
    assert "answered" in told and "“Profile the cold start”" in told
    assert "which you now owe" in told and "owes nothing" not in told
    [todo] = reading(claimed)["activity"]["todos"]
    assert (todo["id"], todo["title"], todo["session"], todo["running"]) == (
        reply["id"],
        "Profile the cold start",
        "s1",
        None,
    )


def test_the_forks_leaf_commands_are_marked_to_act_in_its_turn(claimed, lane, capsys):
    """Claude Code's PreToolUse hook names the agent whose command is about to run,
    so before a command that begins with `leaf` from an agent running a turn of the
    session's own, the hook hands back the command with the agent's id after its
    leading `leaf`, which still begins with `leaf`, so a permission rule allowing
    `leaf` commands still matches it, and the command then acts in the agent's turn.
    A command that runs no `leaf`, another agent's, and the main thread's run as they
    came."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    uses = iter(range(100))

    def before(command: str, agent: str | None = "agent-1") -> str | None:
        hooks_model.cmd_hook(
            "claude-code",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "prompt_id": "p1",
                "tool_name": "Bash",
                "tool_use_id": f"u{next(uses)}",
                "tool_input": {"command": command, "description": "Answer"},
                **({"agent_id": agent} if agent else {}),
            },
        )
        out = capsys.readouterr().out
        if not out:
            return None
        output = json.loads(out)["hookSpecificOutput"]
        assert output["updatedInput"]["description"] == "Answer"
        return output["updatedInput"]["command"]

    reply = "thread reply abc:0:e1 --done --text 'Python 3.12'"
    assert before(f"leaf {reply}") == f"leaf --agent-id agent-1 {reply}"
    assert (
        before(f"/plugin/bin/leaf {reply}")
        == f"/plugin/bin/leaf --agent-id agent-1 {reply}"
    )
    assert before("ls docs") is None
    assert before(f"leaf {reply}", "agent-2") is None
    assert before(f"leaf {reply}", None) is None

    started = CliRunner().invoke(
        cli_model.cli,
        [
            "--agent-id",
            "agent-1",
            "task",
            "start",
            str(claimed),
            asked["id"],
            "--text",
            "reading pyproject.toml",
        ],
    )
    assert started.exit_code == 0, started.output
    [start] = [e for e in events_model.read_events(claimed) if e["kind"] == "start"]
    assert start["turn"] == taken["turn"]
    # The command names the agent for itself alone, and its diagnostics name it.
    assert state_model.AGENT_ID_VARIABLE not in os.environ
    [command] = read_interactions(claimed, types=("leaf_command",))
    assert (command["command"], command["agent"]) == ("task start", "agent-1")


def taken_over(claimed, capsys) -> tuple[dict, dict]:
    """A message a fork took, whose turn then went unheard for the working grace,
    so the main thread's prompt took it in."""
    asked, taken = taken_by_a_fork(claimed, "Does the suggest service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    turns = state_model.agent_turns("s1")
    long_ago = datetime.now().astimezone() - activity_model.WORKING_GRACE
    turns[taken["turn"]]["renewed"] = long_ago.isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )
    context(capsys, "UserPromptSubmit")
    claim = service_model.page_claim(claimed)
    assert claim is not None
    picked = [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"]
    assert [pickup["turn"] for pickup in picked] == [taken["turn"], claim["turn"]]
    return asked, taken


def test_the_newest_pickup_holds_a_thread_so_a_lapsed_fork_takes_nothing_back(
    claimed, lane, capsys
):
    """The turn whose pickup of a thread is newest holds it, whichever agent's it is.
    Once the main thread's prompt has taken a lapsed fork's message in, the fork's
    turn, renewed at its next boundary, takes nothing back, and a further message in
    the thread goes to the main thread."""
    asked, taken = taken_over(claimed, capsys)
    assert agent_context(capsys, "agent-1") == ""
    assert taken["turn"] in state_model.open_agent_turns("s1")
    more = said(claimed, "And the autocomplete service?", parent=asked["id"])
    assert more["id"] in deliverable(claimed)
    assert agent_context(capsys, "agent-1") == ""


def test_a_fork_whose_thread_was_taken_over_can_neither_answer_nor_start_it(
    claimed, lane, capsys
):
    """A takeover takes the thread from the fork, by the same rule that
    refuses it the pickup: its reply with the answer reference its delivery gave it,
    and its start on the message, are refused once the main thread holds the
    message, and write nothing."""
    asked, _taken = taken_over(claimed, capsys)
    events = events_model.read_events(claimed)
    for command in (
        [
            "thread",
            "reply",
            answer_ref(claimed, asked["id"]),
            "--done",
            "--text",
            "Yes",
        ],
        ["task", "start", str(claimed), asked["id"], "--text", "checking the cache"],
    ):
        ran = CliRunner().invoke(cli_model.cli, ["--agent-id", "agent-1", *command])
        assert ran.exit_code != 0, command
        assert "no longer holds" in ran.output, ran.output
    assert events_model.read_events(claimed) == events


def test_a_fork_repeats_its_own_answer_but_not_one_another_turn_gave(
    claimed, lane, capsys
):
    """An answered message is held by the turn that answered it. A fork whose thread
    the main thread took over and answered is refused, though its delivery's answer
    reference is the one the main thread used, rather than handed the main thread's
    answer as the repeat of its own, which its end would then report as the fork's.
    A fork that repeats its own reply gets its own record back."""
    asked, _taken = taken_over(claimed, capsys)
    ref = answer_ref(claimed, asked["id"])
    assert thread_model.post_response(ref, "Yes, for an hour.", asks_back=False)
    events = events_model.read_events(claimed)
    stale = CliRunner().invoke(
        cli_model.cli,
        ["--agent-id", "agent-1", "thread", "reply", ref, "--done"]
        + ["--text", "No, it never caches."],
    )
    assert stale.exit_code != 0
    assert "no longer holds" in stale.output, stale.output
    assert events_model.read_events(claimed) == events

    other, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    forks_model.started(
        "s1", basis(claimed, other["id"], other["id"]), taken["turn"], "agent-2"
    )
    reply = ["thread", "reply", answer_ref(claimed, other["id"]), "--done"]
    for text in ("Python 3.12 or later.", "3.12 or later."):
        ran = CliRunner().invoke(
            cli_model.cli, ["--agent-id", "agent-2", *reply, "--text", text]
        )
        assert ran.exit_code == 0, ran.output
    answers = [
        event["text"]
        for event in events_model.read_events(claimed)
        if event["kind"] == "reply"
        and event.get("responds") == other["id"]
        and not event.get("ephemeral")
    ]
    assert answers == ["Python 3.12 or later."]


def test_the_main_thread_answering_over_a_running_fork_takes_its_thread(
    claimed, lane, monkeypatch
):
    """The main thread is sovereign: its answer to a message a running fork holds
    takes the thread over at once, with whatever answer reference it uses, since
    the answer names the turn that posted it. The fork's later reply with that
    reference is refused rather than handed the main thread's answer as the repeat
    of its own, and so are its start on the message and a message of its own in
    the thread that answers nothing. Its end reports the thread
    taken over, which the main thread isn't told of, and the thread's next message
    goes to a new fork rather than to that one, resumed."""
    asked, taken = taken_by_a_fork(claimed, "Does the suggest service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    ref = answer_ref(claimed, asked["id"])
    answer = thread_model.post_response(ref, "Yes, for an hour.", asks_back=False)
    claim = service_model.page_claim(claimed)
    assert answer is not None and claim is not None
    assert answer["turn"] == claim["turn"]
    events = events_model.read_events(claimed)
    for command in (
        ["thread", "reply", ref, "--done", "--text", "No, it never caches."],
        ["task", "start", str(claimed), asked["id"], "--text", "checking the cache"],
    ):
        ran = CliRunner().invoke(cli_model.cli, ["--agent-id", "agent-1", *command])
        assert ran.exit_code != 0, command
        assert "no longer holds" in ran.output, ran.output
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    with pytest.raises(delivery_model.ReceiptRefused, match="no longer holds"):
        thread_model.post_reply(
            claimed, {"parent": asked["id"]}, "No, it never caches.", todo="Check it"
        )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    assert events_model.read_events(claimed) == events

    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    ) == [
        {
            "page": str(claimed),
            "thread": asked["id"],
            "outcome": "taken_over",
            "why": "the main thread took the thread",
        }
    ]
    assert clerk_model.queued("s1") == []
    more = said(claimed, "And the autocomplete service?", parent=asked["id"])
    assert "resume" not in taken_again(claimed, asked["id"], more)


def test_a_forks_end_reports_only_what_its_own_turn_wrote(claimed, lane, monkeypatch):
    """The end of a fork's run says the fork answered, and names the to-dos it
    opened, only by what its own turn wrote: a to-do the main thread opened on the
    thread meanwhile is the main thread's, so the fork's answer is reported as an
    answer, and the thread, owing that to-do, isn't said to owe nothing."""
    asked, taken = taken_by_a_fork(claimed, "Why is the cold start slow?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    created = CliRunner().invoke(
        cli_model.cli,
        ["task", "create", str(claimed), asked["id"], "--title", "Profile it"],
    )
    assert created.exit_code == 0, created.output
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    assert thread_model.post_response(
        answer_ref(claimed, asked["id"]), "The cache starts cold.", asks_back=False
    )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    ) == [{"page": str(claimed), "thread": asked["id"], "outcome": "answer"}]
    [told] = clerk_model.queued("s1")
    assert "answered" in told
    assert "Profile it" not in told and "owes nothing" not in told


def started_fork(page_dir, text: str, agent: str) -> dict:
    """The user's message in a thread of its own, which a fork the module spawned as
    `agent` took; the message."""
    asked, taken = taken_by_a_fork(page_dir, text)
    forks_model.started(
        "s1", basis(page_dir, asked["id"], asked["id"]), taken["turn"], agent
    )
    return asked


def fork_ends(page_dir, monkeypatch, asked: dict, agent: str, **reply) -> str:
    """The fork `agent`'s reply to `asked` from its own turn, with `reply`'s options,
    and then the end of its run; what `forks.ended` judged of the thread."""
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, agent)
    assert thread_model.post_response(
        answer_ref(page_dir, asked["id"]), f"An answer to: {asked['text']}", **reply
    )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    [ended] = forks_model.ended(
        "s1", agent=agent, turn=None, answer="Done.", failed=None
    )
    return ended["outcome"]


def main_thread_opens_a_to_do(page_dir, thread: str) -> None:
    """A to-do the main thread opens on `thread`, as its own `leaf task create`."""
    created = CliRunner().invoke(
        cli_model.cli,
        ["task", "create", str(page_dir), thread, "--title", "Profile it"],
    )
    assert created.exit_code == 0, created.output


class Watching:
    """The watch session s1's Stop hook starts, run in a thread, and its passes over
    the pages, each of which begins as the watch marks the reading it starts from
    (`Watch.mark`) and ends as it waits for news. It waits as long as the test runs,
    so it wakes only for a write it follows, never at its periodic recheck."""

    def __init__(self, monkeypatch):
        self.woke: list = []
        # The watch and the reading each pass began from, and how many have ended.
        self.began: list[tuple[session_model.Watch, tuple]] = []
        self.ended = 0
        self.passed = Condition()
        mark, await_news = session_model.Watch.mark, session_model.Watch.await_news

        def marking(watch):
            marked = mark(watch)
            with self.passed:
                self.began.append((watch, marked[1]))
            return marked

        def awaiting(watch, marked, timeout=None):
            with self.passed:
                self.ended = len(self.began)
                self.passed.notify_all()
            return await_news(watch, marked, 100 * STATED_TIMEOUT)

        monkeypatch.setattr(session_model.Watch, "mark", marking)
        monkeypatch.setattr(session_model.Watch, "await_news", awaiting)
        stop = {"hook_event_name": "Stop", "session_id": "s1", "prompt_id": "p1"}
        self.thread = Thread(
            target=lambda: self.woke.append(hooks_model.cmd_watch("claude-code", stop)),
            daemon=True,
        )
        self.thread.start()
        self.settle()

    def settle(self) -> None:
        """Wait until the watch has read the pages as they stand now and waits for
        news, so only a later write it follows can wake it; or until it has woken
        the session."""

        def settled() -> bool:
            if not self.thread.is_alive():
                return True
            if not self.began or self.ended < len(self.began):
                return False
            watch, began = self.began[-1]
            return watch.reading() == began

        with self.passed:
            assert self.passed.wait_for(settled, STATED_TIMEOUT), (
                f"the watch never read the pages as they stand: {self.woke}"
            )


def test_the_watch_wakes_the_idle_session_for_a_thread_its_fork_gave_back(
    claimed, lane, interactive, capsys, monkeypatch
):
    """While a fork holds a thread, the main thread's closed turn owes nothing, so the
    watch that follows it sleeps. As the fork's turn ends with the thread unanswered,
    the user's message is the main thread's input again: the watch wakes the session
    for it, though the page's log hasn't moved, and the woken turn's prompt carries
    the message itself beside why the fork gave it back."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    started_fork(claimed, "Does the suggest service cache?", "agent-1")
    context(capsys, "UserPromptSubmit")
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "prompt_id": "p1"},
    )
    assert capsys.readouterr().out == ""
    watching = Watching(monkeypatch)
    assert watching.woke == []

    forks_model.ended(
        "s1",
        agent="agent-1",
        turn=None,
        answer=f"{forks_model.HAND_BACK} the session is changing its startup.",
        failed=None,
    )
    watching.thread.join(STATED_TIMEOUT)
    assert watching.woke == [session_model.wake_line(claimed, "input")]
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt_id": "p2"},
    )
    prompt = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "Does the suggest service cache?" in prompt, prompt
    assert "the session is changing its startup" in prompt, prompt


def test_the_watch_wakes_the_idle_session_for_a_to_do_its_fork_opened(
    claimed, lane, interactive, capsys, monkeypatch
):
    """A fork's answer leaves the idle session nothing new to do, so the watch that
    follows its closed turn sleeps through it, even on a thread holding a to-do the
    main thread opened. A to-do the fork opened is work the main thread now owes, so
    the watch wakes the session as the fork's line about it is queued, though the
    page hasn't moved since the fork's turn closed, and the woken turn's prompt
    carries that line."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    asked = started_fork(claimed, "Why is the cold start slow?", "agent-1")
    later = started_fork(claimed, "Why is the warm start slow?", "agent-2")
    context(capsys, "UserPromptSubmit")
    main_thread_opens_a_to_do(claimed, asked["id"])
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "prompt_id": "p1"},
    )
    assert capsys.readouterr().out == ""
    watching = Watching(monkeypatch)
    assert watching.woke == []

    answered = fork_ends(claimed, monkeypatch, asked, "agent-1", asks_back=False)
    assert answered == "answer"
    watching.settle()
    assert watching.woke == []

    # The watch reads the pages once the fork's turn has closed, before its line is
    # queued, so only the line can wake it.
    close = forks_model.close_agent_turns

    def closed_and_read(*args, **kwargs):
        closed = close(*args, **kwargs)
        watching.settle()
        return closed

    monkeypatch.setattr(forks_model, "close_agent_turns", closed_and_read)
    todo = "Profile the warm start"
    assert fork_ends(claimed, monkeypatch, later, "agent-2", todo=todo) == "todo"
    watching.thread.join(STATED_TIMEOUT)
    assert watching.woke == [session_model.wake_line(claimed, "told")]
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt_id": "p2"},
    )
    told = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "“Profile the warm start”" in told and "which you now owe" in told
    assert clerk_model.waking("s1") == []


def test_a_to_do_its_fork_opened_nudges_a_session_no_watch_follows_once(
    claimed, lane, interactive, capsys, monkeypatch
):
    """With no watch following the session's closed turn, the end of a fork's run
    nudges the session for a to-do the fork opened, once Leaf has queued the line
    the woken turn's prompt carries, and once for that ending of the session's turn,
    however many forks open to-dos before its next turn. A fork's answer nudges
    nothing, even on a thread holding a to-do the main thread opened."""
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page: nudged.append((page, clerk_model.waking("s1"))) or True,
    )
    asked = started_fork(claimed, "Why is the cold start slow?", "agent-1")
    later = started_fork(claimed, "Why is the warm start slow?", "agent-2")
    last = started_fork(claimed, "Why is the build slow?", "agent-3")
    context(capsys, "UserPromptSubmit")
    main_thread_opens_a_to_do(claimed, asked["id"])
    state_model.close_session_turn("s1")

    assert fork_ends(claimed, monkeypatch, asked, "agent-1", asks_back=False) == (
        "answer"
    )
    assert nudged == []

    todo = "Profile the warm start"
    assert fork_ends(claimed, monkeypatch, later, "agent-2", todo=todo) == "todo"
    [(page, owed)] = nudged
    assert page == claimed.resolve()
    assert any("“Profile the warm start”" in line for line in owed)

    fork_ends(claimed, monkeypatch, last, "agent-3", todo="Profile the build")
    assert len(nudged) == 1


def test_a_follow_up_in_the_thread_reaches_the_fork_at_its_tool_boundary(
    claimed, lane, capsys
):
    """The user's further message in a thread a fork's running turn took is the
    fork's: the main thread is neither handed it nor woken for it, and the fork's next
    tool boundary carries it, once, recorded in the fork's turn. A worker running no
    turn of the session's is handed nothing."""
    asked, taken = taken_by_a_fork(claimed, "Does the autocomplete service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    more = said(claimed, "And the suggest service?", parent=asked["id"])
    assert kept_back(claimed) == []
    assert deliverable(claimed) == []
    assert context(capsys, "PostToolBatch") == ""

    opening, envelope = agent_context(capsys, "agent-1").split("\n", 1)
    assert opening == hook_transport_model.INLINE_OPENING
    [batch] = json.loads(envelope)["batches"]
    assert [event["id"] for event in batch["events"]] == [more["id"]]
    pickup = [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"][-1]
    assert (pickup["events"], pickup["turn"]) == ([more["id"]], taken["turn"])
    assert agent_context(capsys, "agent-1") == ""
    assert agent_context(capsys, "agent-2") == ""
    assert deliverable(claimed) == []


def test_a_follow_up_too_large_for_the_hook_reaches_the_fork_by_pointer(
    claimed, lane, capsys
):
    """A follow-up too large for the hook's context goes to the fork by pointer, as the
    main thread's does, and once: the fork's own acknowledgement records it into the
    fork's turn, and the main thread is handed none of it meanwhile."""
    asked, taken = taken_by_a_fork(claimed, "Does the autocomplete service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    more = said(claimed, "Here is its config:\n" + "cache: warm\n" * 1200, asked["id"])
    pointer = agent_context(capsys, "agent-1")
    [delivery] = re.findall(r'<leaf-delivery id="([0-9a-f]+)"', pointer)
    assert agent_context(capsys, "agent-1") == ""
    assert deliverable(claimed) == []

    acked = CliRunner().invoke(
        cli_model.cli, ["--agent-id", "agent-1", "delivery", "ack", delivery]
    )
    assert acked.exit_code == 0, acked.output
    pickup = [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"][-1]
    assert (pickup["events"], pickup["turn"]) == ([more["id"]], taken["turn"])
    assert deliverable(claimed) == []
    assert agent_context(capsys, "agent-1") == ""


def answered_by_a_fork(page_dir, monkeypatch, text: str, agent: str) -> dict:
    """The user's message in a thread of its own, which a fork the module spawned as
    `agent` took, answered from its own turn, and ended; the message."""
    asked, taken = taken_by_a_fork(page_dir, text)
    forks_model.started(
        "s1", basis(page_dir, asked["id"], asked["id"]), taken["turn"], agent
    )
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, agent)
    assert thread_model.post_response(
        answer_ref(page_dir, asked["id"]), f"The answer to: {text}", asks_back=False
    )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    forks_model.ended("s1", agent=agent, turn=None, answer="Answered.", failed=None)
    clerk_model.heard("s1", clerk_model.queued("s1"))
    return asked


def taken_again(page_dir, thread: str, more: dict) -> dict:
    """What Leaf did as the line fork judged the work of the user's message `more`
    in `thread` a fork's."""
    assert kept_back(page_dir) == [(thread, (more["id"],))]
    taken = forks_model.route(
        "s1",
        basis(page_dir, thread, more["id"]),
        answer=judged("looking into it", "take"),
        failed=None,
        work_forks=True,
    )
    assert taken["outcome"] == "take", taken
    return taken


def test_a_follow_up_after_the_forks_run_goes_to_that_fork_again(
    claimed, lane, monkeypatch
):
    """The user's further message in a thread a fork answered, once the fork's run
    has ended, goes to the same fork in a new turn of its own, which Leaf opens,
    names with the fork's agent id and records the pickup in, so the fork works the
    thread however many messages it gets. Leaf's
    message resuming it carries the delivery and tells the fork to read the page's
    state, which its transcript lacks. A late end of the fork's earlier turn leaves
    the new one running. The fork's answer from that turn is its own, and the turn's
    end reports it."""
    asked = answered_by_a_fork(claimed, monkeypatch, "Which Python?", "agent-1")
    more = said(claimed, "And which uv?", parent=asked["id"])
    taken = taken_again(claimed, asked["id"], more)
    assert taken["resume"] == "agent-1"
    assert state_model.agent_turn_of("s1", "agent-1") == taken["turn"]
    # A late end of the fork's earlier turn leaves the new one running.
    [earlier] = set(state_model.agent_turns("s1")) - {taken["turn"]}
    assert (
        forks_model.ended(
            "s1", agent="agent-1", turn=earlier, answer=None, failed="it timed out"
        )
        == []
    )
    assert state_model.agent_turn_of("s1", "agent-1") == taken["turn"]
    pickup = [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"][-1]
    assert (pickup["events"], pickup["turn"]) == ([more["id"]], taken["turn"])
    resume = taken["prompt"]
    assert resume.startswith(forks_model.WORK_OPENING)
    assert "And which uv?" in resume and answer_ref(claimed, more["id"]) in resume
    assert f"`leaf page state {claimed}`" in resume
    assert "--todo" in resume and forks_model.HAND_BACK in resume

    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    answer = thread_model.post_response(
        answer_ref(claimed, more["id"]), "uv 0.9 or later.", asks_back=False
    )
    assert answer is not None and answer["responds"] == more["id"]
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    ) == [{"page": str(claimed), "thread": asked["id"], "outcome": "answer"}]
    assert state_model.open_agent_turns("s1") == {}


def test_a_thread_whose_fork_cannot_be_resumed_goes_to_the_main_thread(
    claimed, lane, monkeypatch
):
    """A thread whose last answer the main thread gave goes to a new fork, even
    where the main thread answered a message the fork gave back with the fork's own
    answer reference, before any pickup of its own, since the answer names the turn
    that posted it; and so does one whose fork ran in an earlier generation of the
    session, which ended with it. Where the module can't resume the fork, it ends
    the turn Leaf opened, which gives the thread to the main thread rather than to a
    new fork, and the old fork's commands act in no turn."""
    asked, given = taken_by_a_fork(claimed, "Does the suggest service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), given["turn"], "agent-1"
    )
    forks_model.ended(
        "s1",
        agent="agent-1",
        turn=None,
        answer=f"{forks_model.HAND_BACK} the session is changing it.",
        failed=None,
    )
    assert thread_model.post_response(
        answer_ref(claimed, asked["id"]), "Yes, for an hour.", asks_back=False
    )
    more = said(claimed, "And the autocomplete service?", parent=asked["id"])
    assert "resume" not in taken_again(claimed, asked["id"], more)

    earlier = answered_by_a_fork(claimed, monkeypatch, "Which region?", "agent-2")
    turns = state_model.agent_turns("s1")
    for entry in turns.values():
        entry["generation"] = "an earlier generation"
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )
    later = said(claimed, "And staging?", parent=earlier["id"])
    assert "resume" not in taken_again(claimed, earlier["id"], later)

    lost = answered_by_a_fork(claimed, monkeypatch, "Which shard?", "agent-3")
    again = said(claimed, "And its replica?", parent=lost["id"])
    taken = taken_again(claimed, lost["id"], again)
    assert taken["resume"] == "agent-3"
    [failed] = forks_model.ended(
        "s1",
        agent=None,
        turn=taken["turn"],
        answer=None,
        failed="the fork could not be resumed: no transcript",
    )
    assert (failed["thread"], failed["outcome"]) == (lost["id"], "hand_back")
    owed = activity_model.turn_obligations(reading(claimed), watched=False)
    assert again["id"] in {item["input"] for item in owed}
    assert state_model.agent_turn_of("s1", "agent-3") is None


def test_one_fork_works_a_thread_while_its_turn_runs(
    claimed, lane, capsys, monkeypatch
):
    """A thread a running fork turn took is never kept back for a second fork. The
    user's message after the fork answered, while its turn still runs, is that
    fork's: the main thread isn't given it, and the fork's next tool boundary
    carries it. One that arrives as the fork's run ends goes to the same fork,
    resumed, even where a receipt passed the log meanwhile. A resumed fork whose
    message the user took back still holds the thread's next one; a thread the main
    thread took over by answering, while the fork still runs, gives its next message
    to the main thread; and a thread a running fork took by answering a message in it
    gives its next message to that fork."""
    zone, running = taken_by_a_fork(claimed, "Which zone?")
    forks_model.started(
        "s1", basis(claimed, zone["id"], zone["id"]), running["turn"], "agent-5"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-5")
    assert thread_model.post_response(
        answer_ref(claimed, zone["id"]), "us-east-1b.", asks_back=False
    )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    status, admitted = endpoint_model.accept_event(
        claimed,
        {"kind": "reply", "parent": zone["id"], "revision": 1, "text": "Replica's?"},
    )
    assert status == 200, admitted
    soon = admitted["event"]
    [note] = [
        row
        for row in read_interactions(claimed, types=("fork_admission",))
        if row["event"] == soon["id"]
    ]
    assert (note["kept_back"], note["held_by"]) == (False, running["turn"])
    assert kept_back(claimed) == []
    assert deliverable(claimed) == []
    _opening, envelope = agent_context(capsys, "agent-5").split("\n", 1)
    [batch] = json.loads(envelope)["batches"]
    assert [event["id"] for event in batch["events"]] == [soon["id"]]
    pickup = [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"][-1]
    assert (pickup["events"], pickup["turn"]) == ([soon["id"]], running["turn"])

    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-5")
    assert thread_model.post_response(
        answer_ref(claimed, soon["id"]), "us-east-1c.", asks_back=False
    )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    late = said(claimed, "And the third?", parent=zone["id"])
    assert kept_back(claimed) == []
    # Another fork's take records a receipt, which passes nothing no turn took in.
    taken_by_a_fork(claimed, "Which shard is hot?")
    forks_model.ended("s1", agent="agent-5", turn=None, answer="Done.", failed=None)
    assert taken_again(claimed, zone["id"], late)["resume"] == "agent-5"

    region = answered_by_a_fork(claimed, monkeypatch, "Which region now?", "agent-6")
    first = said(claimed, "And its zones?", parent=region["id"])
    resumed = taken_again(claimed, region["id"], first)
    assert resumed["resume"] == "agent-6"
    forks_model.started(
        "s1", basis(claimed, region["id"], first["id"]), resumed["turn"], "agent-6"
    )
    append_carried_log_record(
        claimed, {"kind": "undo", "author": "user", "undoes": first["id"]}
    )
    instead = said(claimed, "And its subnets?", parent=region["id"])
    assert kept_back(claimed) == []
    assert instead["id"] not in deliverable(claimed)
    assert instead["id"] in agent_context(capsys, "agent-6")

    shard, kept = taken_by_a_fork(claimed, "Which shard?")
    forks_model.started(
        "s1", basis(claimed, shard["id"], shard["id"]), kept["turn"], "agent-7"
    )
    assert thread_model.post_response(
        answer_ref(claimed, shard["id"]), "Shard 4.", asks_back=False
    )
    next_one = said(claimed, "And its replica?", parent=shard["id"])
    assert kept_back(claimed) == []
    assert next_one["id"] in deliverable(claimed)
    assert agent_context(capsys, "agent-7") == ""

    elsewhere = said(claimed, "Which region is that shard in?")
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-7")
    assert thread_model.post_reply(claimed, {"responds": elsewhere["id"]}, "eu-west.")
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    after = said(claimed, "And its replica's?", parent=elsewhere["id"])
    assert kept_back(claimed) == []
    assert after["id"] in agent_context(capsys, "agent-7")


def lapse(turn: str) -> None:
    """Leave the agent turn `turn` unrenewed for the working grace."""
    turns = state_model.agent_turns("s1")
    long_ago = datetime.now().astimezone() - activity_model.WORKING_GRACE
    turns[turn]["renewed"] = long_ago.isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )


def close_turn_at(turn: str, moment: datetime) -> None:
    """Stamp the closed agent turn `turn` as closing at `moment`."""
    turns = state_model.agent_turns("s1")
    turns[turn]["closed"] = moment.isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )


def pointer_in(text: str) -> str | None:
    """The delivery a hook's context points at, if it points at one."""
    return next(iter(re.findall(r'<leaf-delivery id="([0-9a-f]+)"', text)), None)


def test_a_late_acknowledgement_does_not_take_a_thread_back(claimed, lane, capsys):
    """Where a pickup is recorded, an agent's turn may take only messages it holds or
    nobody does. A fork handed a follow-up by pointer whose turn lapses before it
    acknowledges it loses the thread to the main thread's pickup, and its late
    acknowledgement is refused, records nothing, and leaves the thread the main
    thread's."""
    asked, taken = taken_by_a_fork(claimed, "Does the autocomplete service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    more = said(claimed, "Here is its config:\n" + "cache: warm\n" * 1200, asked["id"])
    stale = pointer_in(agent_context(capsys, "agent-1"))
    assert stale is not None
    lapse(taken["turn"])
    handed = context(capsys, "UserPromptSubmit")
    if main_pointer := pointer_in(handed):
        acked = CliRunner().invoke(cli_model.cli, ["delivery", "ack", main_pointer])
        assert acked.exit_code == 0, acked.output
    claim = service_model.page_claim(claimed)
    assert claim is not None
    with PageTransaction(claimed) as page:
        held = holding_model.holding_turns(page.events, "s1", set())
    assert held[more["id"]] == claim["turn"]

    late = CliRunner().invoke(
        cli_model.cli, ["--agent-id", "agent-1", "delivery", "ack", stale]
    )
    assert late.exit_code != 0
    assert "no longer holds" in late.output
    with PageTransaction(claimed) as page:
        assert holding_model.holding_turns(page.events, "s1", set()) == held


def test_a_command_marked_with_an_ended_fork_acts_as_nobody(claimed, lane, capsys):
    """A command marked with a fork whose turn has ended, as one marked while it ran
    can arrive late, is refused, whatever it is: its reply, its start, its
    acknowledgement, a to-do or a thread of its own each say the fork's turn has
    ended, rather than acting with the main thread's authority."""
    asked, taken = taken_by_a_fork(claimed, "Does the autocomplete service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    forks_model.ended(
        "s1",
        agent="agent-1",
        turn=None,
        answer=f"{forks_model.HAND_BACK} the session is changing it.",
        failed=None,
    )
    context(capsys, "UserPromptSubmit")
    ref = answer_ref(claimed, asked["id"])
    events = events_model.read_events(claimed)
    for command in (
        ["thread", "reply", ref, "--done", "--text", "Yes, for a minute."],
        ["task", "start", str(claimed), asked["id"], "--text", "checking the cache"],
        ["delivery", "ack", ref.partition(":")[0]],
        ["task", "create", str(claimed), "page", "--title", "Check the cache"],
        ["thread", "create", str(claimed), "--text", "The cache holds a minute."],
    ):
        ran = CliRunner().invoke(cli_model.cli, ["--agent-id", "agent-1", *command])
        assert ran.exit_code != 0, command
        assert "agent-1's turn has ended" in ran.output, ran.output
    assert events_model.read_events(claimed) == events


def test_a_fork_that_answered_is_reported_however_its_thread_moves_on(
    claimed, lane, capsys, monkeypatch
):
    """The end of a fork's run is judged by the messages its turn picked up itself.
    A fork that answered is reported as answering though the user writes again
    before its run ends, and the message its run never carried goes to the main
    thread saying so; and one whose turn lapsed and lost its thread to the main
    thread's pickup is reported as taken over, with no line telling the main thread
    it was given a thread it took itself."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    thread_model.post_response(
        answer_ref(claimed, asked["id"]), "Python 3.12 or later.", asks_back=False
    )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    uv = said(claimed, "And which uv?", parent=asked["id"])
    clerk_model.heard("s1", clerk_model.queued("s1"))
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    ) == [{"page": str(claimed), "thread": asked["id"], "outcome": "answer"}]
    # The run ended once the further message's bound had passed.
    close_turn_at(
        taken["turn"],
        datetime.fromisoformat(uv["ts"]) + timedelta(seconds=forks_model.BOUND_S),
    )
    [told] = clerk_model.queued("s1")
    assert "answered" in told and "written there since" in told
    assert forks_model.look("s1", claimed, now=float("inf")) == []
    [uncarried] = [
        row
        for row in read_interactions(claimed, types=("fork_outcome",))
        if row.get("outcome") == "hand_over"
    ]
    assert uncarried["why"] == "its fork's turn ended before carrying it"

    other, kept = taken_by_a_fork(claimed, "How many shards does staging have?")
    forks_model.started(
        "s1", basis(claimed, other["id"], other["id"]), kept["turn"], "agent-2"
    )
    lapse(kept["turn"])
    context(capsys, "UserPromptSubmit")
    clerk_model.heard("s1", clerk_model.queued("s1"))
    assert forks_model.ended(
        "s1", agent="agent-2", turn=None, answer="", failed=None
    ) == [
        {
            "page": str(claimed),
            "thread": other["id"],
            "outcome": "taken_over",
            "why": "the main thread took the thread",
        }
    ]
    assert clerk_model.queued("s1") == []
    joins = [
        row["outcome"]
        for row in read_interactions(claimed, types=("fork_outcome",))
        if row.get("step") == "end"
    ]
    assert joins == ["answer", "taken_over"]


def test_a_message_a_line_fork_was_asked_about_is_noted_as_unanswered(
    claimed, lane, monkeypatch
):
    """A message the user writes in a fork's thread after the fork's turn ended, or
    so late in the turn that its bound still ran as the turn ended, goes to a line
    fork: where that gives no answer within the bound, the page's diagnostics say
    so, not that the fork's turn left the message."""

    def answered_by(agent: str, question: str) -> tuple[dict, dict]:
        asked, taken = taken_by_a_fork(claimed, question)
        forks_model.started(
            "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], agent
        )
        monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, agent)
        thread_model.post_response(
            answer_ref(claimed, asked["id"]), "Yes, for a minute.", asks_back=False
        )
        monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
        return asked, taken

    asked, taken = answered_by("agent-1", "Does the suggest service cache?")
    forks_model.ended("s1", agent="agent-1", turn=None, answer="Done.", failed=None)
    # The user writes a minute after the turn closed.
    close_turn_at(taken["turn"], datetime.now().astimezone() - timedelta(minutes=1))
    after = said(claimed, "And for how long?", parent=asked["id"])

    other, last = answered_by("agent-2", "Does the search service cache?")
    late = said(claimed, "And who clears it?", parent=other["id"])
    forks_model.ended("s1", agent="agent-2", turn=None, answer="Done.", failed=None)
    # The turn closed a second after the user wrote.
    close_turn_at(
        last["turn"], datetime.fromisoformat(late["ts"]) + timedelta(seconds=1)
    )

    assert forks_model.look("s1", claimed, now=float("inf")) == []
    handed = {
        tuple(row["inputs"]): row["why"]
        for row in read_interactions(claimed, types=("fork_outcome",))
        if row.get("outcome") == "hand_over"
    }
    unanswered = f"no answer within {forks_model.BOUND_S:g} s"
    assert handed == {(after["id"],): unanswered, (late["id"],): unanswered}


def hook_answer(capsys, command: str, agent: str, tool_use: str) -> dict | None:
    """What Claude Code's PreToolUse hook answers for `agent`'s Bash call, its
    `hookSpecificOutput`, or None where it leaves the call as it came."""
    hooks_model.cmd_hook(
        "claude-code",
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "prompt_id": "p1",
            "tool_name": "Bash",
            "tool_use_id": tool_use,
            "tool_input": {"command": command},
            "agent_id": agent,
        },
    )
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"] if out else None


def test_an_ended_forks_later_command_stays_its_own_and_is_refused(
    claimed, lane, capsys
):
    """The mark follows the agent, not its turn: once a fork's turn has ended and the
    main thread holds its message, the fork's next `leaf` command, as a resumed or
    late one, is still marked as the fork's, and so refused, rather than settling the
    main thread's message with the main thread's authority. A subagent the session
    ran no turn for, such as one of the main thread's own workers, acts as it did."""
    asked, taken = taken_by_a_fork(claimed, "Does the autocomplete service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    forks_model.ended(
        "s1",
        agent="agent-1",
        turn=None,
        answer=f"{forks_model.HAND_BACK} the session is changing it.",
        failed=None,
    )
    context(capsys, "UserPromptSubmit")
    reply = f"leaf thread reply {answer_ref(claimed, asked['id'])} --done --text Yes"
    answer = hook_answer(capsys, reply, "agent-1", "u1")
    assert answer is not None
    marked = answer["updatedInput"]["command"]
    assert marked == reply.replace("leaf ", "leaf --agent-id agent-1 ", 1)
    ran = CliRunner().invoke(cli_model.cli, shlex.split(marked)[1:])
    assert ran.exit_code != 0
    assert "agent-1's turn has ended" in ran.output
    # Its record in the page says it was refused, not answered.
    [command] = read_interactions(claimed, types=("leaf_command",))
    assert "agent-1's turn has ended" in command["refused"]
    assert hook_answer(capsys, reply, "agent-9", "u2") is None

    # A fork that runs on after Leaf failed to record its start: the module's end
    # of its turn names it, so its command is the fork's, and refused.
    other, unnamed = taken_by_a_fork(claimed, "How many shards does staging have?")
    forks_model.ended(
        "s1",
        agent="agent-2",
        turn=unnamed["turn"],
        answer=None,
        failed="Leaf's step failed: exited with code 1",
    )
    late = f"leaf thread reply {answer_ref(claimed, other['id'])} --done --text Two"
    answer = hook_answer(capsys, late, "agent-2", "u3")
    assert answer is not None
    ran = CliRunner().invoke(
        cli_model.cli, shlex.split(answer["updatedInput"]["command"])[1:]
    )
    assert "agent-2's turn has ended" in ran.output, ran.output


def test_a_forks_leaf_command_must_lead_its_bash_call(claimed, lane, capsys):
    """Leaf marks a fork's `leaf` command only where it leads the Bash call, since a
    mark spliced in elsewhere could land in quoted text. A known fork's call with
    `leaf` anywhere else may act as the main thread's, so the hook denies it, saying
    to run each `leaf` command on its own: after another command or a keyword, in a
    command substitution however it starts, quoted, run by a relative path, in a
    string `bash -c` runs or in a here-document, and where the word only names
    `leaf`, as a reply's text or a search may. A call whose only `leaf` leads it is
    marked; one with no `leaf` word goes on as it came, and so does any call of a
    subagent the session ran no turn for."""
    asked, taken = taken_by_a_fork(claimed, "Does the autocomplete service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    reply = f"leaf thread reply {answer_ref(claimed, asked['id'])} --done --text Yes"
    for index, command in enumerate(
        (
            f"cd /tmp && {reply}",
            f"{reply} && leaf page state p",
            f"if true; then {reply}; fi",
            f'echo "$(true; {reply})"',
            f"echo `{reply}`",
            f"timeout 30 {reply}",
            "'leaf' page state p",
            "bash -c 'leaf page state p'",
            "cd bin && ./leaf page state p",
            "cat <<EOF\n$(leaf page state p)\nEOF",
            "bash <<'EOF'\nleaf page state p\nEOF",
            reply.replace("--text Yes", '--text "Run \\`leaf page state\\` to see"'),
            "grep leaf notes.md",
        )
    ):
        answer = hook_answer(capsys, command, "agent-1", f"denied-{index}")
        assert answer is not None and answer["permissionDecision"] == "deny", command
        assert "beginning with `leaf`" in answer["permissionDecisionReason"]
    for index, command in enumerate(
        (
            "grep -rn leaf_words src/leaf",
            "git diff src/leaf",
            "cat ~/.local/state/leaf/pages/p/index.html",
            "uv run leaf-dev timeline p",
            'echo "Leaf\'s page"',
        )
    ):
        assert hook_answer(capsys, command, "agent-1", f"passed-{index}") is None, (
            command
        )
    for index, command in enumerate(
        (
            reply,
            f"/plugin/bin/{reply}",
            reply.replace("--text Yes", "--file reply.md"),
        )
    ):
        marked = hook_answer(capsys, command, "agent-1", f"marked-{index}")
        assert marked is not None and "updatedInput" in marked, command
        assert marked["updatedInput"]["command"] == command.replace(
            "leaf ", "leaf --agent-id agent-1 ", 1
        )
    assert hook_answer(capsys, f"cd /tmp && {reply}", "agent-9", "unknown") is None


def test_a_forks_leaf_command_waits_until_leaf_knows_its_agent(
    claimed, lane, capsys, monkeypatch
):
    """A fork runs before Leaf hears which agent runs the turn it opened for it,
    which stays unnamed until then. Meanwhile the `leaf` command of an agent running
    no turn of the session is denied with the instruction to run it again, rather
    than acting as the main thread's, as a new fork's would. Once Leaf knows the
    agent, its command is marked as its own; with no turn awaiting its agent, a
    worker's command runs as it came. A resumed fork, whose agent Leaf knows, runs
    its new turn from the start, so its command is marked at once."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    reply = f"leaf thread reply {answer_ref(claimed, asked['id'])} --done --text 3.12"
    waiting = hook_answer(capsys, reply, "agent-1", "spawning")
    assert waiting is not None and waiting["permissionDecision"] == "deny"
    assert "run the same command again" in waiting["permissionDecisionReason"]
    # The command never runs, so the page notes the denial in its place.
    [denied] = read_interactions(claimed, types=("command_denied",))
    assert (denied["session"], denied["agent"], denied["command"]) == (
        "s1",
        "agent-1",
        reply,
    )
    assert denied["reason"] == waiting["permissionDecisionReason"]
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    marked = hook_answer(capsys, reply, "agent-1", "spawned")
    assert marked is not None
    assert marked["updatedInput"]["command"] == reply.replace(
        "leaf ", "leaf --agent-id agent-1 ", 1
    )
    assert hook_answer(capsys, reply, "agent-9", "worker") is None

    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    assert thread_model.post_response(
        answer_ref(claimed, asked["id"]), "3.12 or later.", asks_back=False
    )
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    forks_model.ended("s1", agent="agent-1", turn=None, answer="Done.", failed=None)
    more = said(claimed, "And which uv?", parent=asked["id"])
    again = taken_again(claimed, asked["id"], more)
    later = f"leaf thread reply {answer_ref(claimed, more['id'])} --done --text 0.9"
    resumed = hook_answer(capsys, later, "agent-1", "resumed")
    assert resumed is not None and "updatedInput" in resumed
    # A turn's agent never changes once named.
    assert forks_model.started(
        "s1", basis(claimed, asked["id"], more["id"]), again["turn"], "agent-2"
    )["outcome"] == ("dropped")
    assert state_model.agent_turn_of("s1", "agent-1") == again["turn"]

    # While another fork starts, a fork that runs its turn goes on as it did, and a
    # turn left unnamed stops holding workers back once it lapses.
    _other, pending = taken_by_a_fork(claimed, "Which region is staging in?")
    running = hook_answer(capsys, later, "agent-1", "running")
    assert running is not None and "updatedInput" in running
    worker = hook_answer(capsys, "leaf page state p", "agent-9", "worker-waits")
    assert worker is not None and worker["permissionDecision"] == "deny"
    lapse(pending["turn"])
    assert hook_answer(capsys, "leaf page state p", "agent-9", "worker-runs") is None


def test_a_fork_turn_that_ends_unanswered_gives_its_thread_to_the_main_thread(
    claimed, lane
):
    """A fork that gives the thread back, fails to start, or goes unheard for the
    working grace leaves the thread's answer owed by the main thread, under the
    answer reference the fork's delivery gave it until the main thread's next
    delivery hands the message over; and the main thread hears which fork gave which
    thread back, and why."""
    asked, taken = taken_by_a_fork(claimed, "Does the suggest service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    assert forks_model.ended(
        "s1",
        agent="agent-1",
        turn=None,
        answer=f"{forks_model.HAND_BACK} the session is changing its startup.",
        failed=None,
    ) == [
        {
            "page": str(claimed),
            "thread": asked["id"],
            "outcome": "hand_back",
            "why": "the session is changing its startup.",
        }
    ]
    [owed] = activity_model.turn_obligations(reading(claimed), watched=False)
    assert owed["input"] == asked["id"]
    assert owed["answer"]["ref"] == answer_ref(claimed, asked["id"])
    assert "gave thread" in clerk_model.queued("s1")[-1]

    unstarted, given = taken_by_a_fork(claimed, "How many shards does staging have?")
    [failed] = forks_model.ended(
        "s1", agent=None, turn=given["turn"], answer=None, failed="it did not start"
    )
    assert failed["why"] == "the fork failed: it did not start"

    quiet, kept = taken_by_a_fork(claimed, "Which region is staging in?")
    owing = {
        item["input"]
        for item in activity_model.turn_obligations(reading(claimed), watched=False)
    }
    assert owing == {asked["id"], unstarted["id"]}
    turns = state_model.agent_turns("s1")
    long_ago = datetime.now().astimezone() - activity_model.WORKING_GRACE
    turns[kept["turn"]]["renewed"] = long_ago.isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )
    owing = {
        item["input"]
        for item in activity_model.turn_obligations(reading(claimed), watched=False)
    }
    assert quiet["id"] in owing


def test_a_failed_fork_gives_the_thread_to_the_session_bare(claimed, lane):
    """A fork that failed, or whose answer isn't the line and judgment Leaf asked
    for, hands the thread over with no line, and the message reads as its delivery
    stands."""
    failed = said(claimed, "And the lane?")
    blank = said(claimed, "What does the follower print?")
    assert forks_model.route(
        "s1", basis(claimed, failed["id"], failed["id"]), answer=None, failed="aborted"
    ) == {"outcome": "hand_over", "why": "the fork failed: aborted"}
    assert forks_model.route(
        "s1", basis(claimed, blank["id"], blank["id"]), answer=judged(" "), failed=None
    )["why"].startswith("the fork failed: the fork's answer doesn't fit its schema")
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [failed["id"], blank["id"]]
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )
    assert forked(claimed) == []


def test_a_thread_a_fork_gave_back_goes_to_the_main_thread_once(claimed, lane):
    """A thread a fork gave back is the main thread's input, and so is the further
    message the user wrote while the fork ran, which its turn held and never carried:
    the main thread's next delivery hands over each of them once."""
    asked, taken = taken_by_a_fork(claimed, "Stop editing the header.")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    more = said(claimed, "And keep the old layout.", parent=asked["id"])
    assert deliverable(claimed) == []
    forks_model.ended(
        "s1",
        agent="agent-1",
        turn=None,
        answer=f"{forks_model.HAND_BACK} the header is the session's to change.",
        failed=None,
    )
    assert deliverable(claimed) == [asked["id"], more["id"]]


def test_a_hold_ends_with_its_bound_or_its_lane(claimed, lane, monkeypatch):
    """However the fork fares, the lane hands the messages to the session once
    `BOUND_S` has passed since the newest of them, nudging a session no watch
    follows as admission would have; and they are deliverable once the follower
    holding the lane exits."""
    nudged = []
    monkeypatch.setattr(
        presence_model, "nudge_unwatched", lambda page: nudged.append(page.page_dir)
    )
    asked = said(claimed, "Is the bound from the newest message?")
    admitted = datetime.fromisoformat(asked["ts"]).timestamp()
    [still] = forks_model.look("s1", claimed, now=admitted + forks_model.BOUND_S - 1)
    assert still.thread == asked["id"]
    assert deliverable(claimed) == []
    assert forks_model.look("s1", claimed, now=admitted + forks_model.BOUND_S) == []
    assert deliverable(claimed) == [asked["id"]]
    assert nudged == [claimed.resolve()]

    other = said(claimed, "And without a lane?")
    assert kept_back(claimed) == [(other["id"], (other["id"],))]
    assert forked(claimed) == [other["id"]]
    # No page file records the lane going down, so the presence reading names the
    # lane itself, and a tab re-reads once its cache interval passes.
    monkeypatch.setattr(presence_model, "PRESENCE_CACHE_S", 0)
    before = presence_model.presence_reading(claimed, "files")
    leases_model.release_lease(lane)
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"], other["id"]]
    assert forked(claimed) == []
    assert presence_model.presence_reading(claimed, "files") != before


def test_without_a_lane_nothing_is_kept_back(claimed):
    """A session without Leaf's hooks module, or any other harness, delivers as
    before."""
    asked = said(claimed, "Anyone there?")
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"]]


def test_a_message_while_kept_back_starts_a_fork_for_both_and_drops_the_first_answer(
    claimed, lane
):
    """A second message in a kept-back thread keeps it back, now with both, and the line fork
    asked about the first alone writes nothing: the thread's newest message carries
    its one answer."""
    first = said(claimed, "Why 30 s?")
    second = said(claimed, "Or rather, why not 20?", parent=first["id"])
    assert kept_back(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert forks_model.ask("s1", basis(claimed, first["id"], first["id"]), []) is None

    assert forks_model.route(
        "s1",
        basis(claimed, first["id"], first["id"]),
        answer=judged("Thirty covers a cold cache."),
        failed=None,
    ) == {
        "outcome": "dropped",
        "text": "Thirty covers a cold cache.",
        "work": "hand_over",
    }
    assert kept_back(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert not any(
        event["kind"] == "reply" and event["author"] == "agent"
        for event in events_model.read_events(claimed)
    )


def test_a_thread_the_session_owes_stays_with_it_and_a_follow_up_is_forked(
    claimed, lane, capsys
):
    """Once the session has received a thread's message, a message after it in that
    thread goes to the session too; once the agent has answered, the user's
    follow-up is kept back again, and its line fork sees the earlier exchange."""
    asked = said(claimed, "Where does the hold live?")
    leases_model.release_lease(lane)
    assert "Where does the hold live?" in context(capsys, "UserPromptSubmit")
    lane = take_lane()
    more = said(claimed, "And who reads it?", parent=asked["id"])
    assert kept_back(claimed) == []
    assert more["id"] in deliverable(claimed)
    leases_model.release_lease(lane)

    context(capsys, "PostToolBatch")
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    capsys.readouterr()
    thread_model.post_reply(
        claimed, {"responds": more["id"]}, "In `delivery.deliverable`."
    )
    lane = take_lane()
    follow_up = said(claimed, "Thanks. Does the watch read it too?", parent=asked["id"])
    assert kept_back(claimed) == [(asked["id"], (follow_up["id"],))]
    question = forks_model.ask("s1", basis(claimed, asked["id"], follow_up["id"]), [])
    assert question is not None
    assert "In `delivery.deliverable`." in question["prompt"]
    leases_model.release_lease(lane)


def test_the_session_taking_the_message_first_leaves_the_fork_nothing_to_write(
    claimed, lane, capsys
):
    """A kept-back message the session picks up anyway, as once the bound has passed, is
    the session's: the fork's later answer writes nothing."""
    asked = said(claimed, "Which wins?")
    with PageTransaction(claimed) as page:
        [event] = [e for e in page.events if e["id"] == asked["id"]]
        delivery_model.record_pickup(page, [event], session="s1", turn="t1")
    assert kept_back(claimed) == []
    assert forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=judged("The fork."),
        failed=None,
    ) == {"outcome": "dropped", "text": "The fork.", "work": "hand_over"}


def test_a_hold_ending_while_the_reply_goes_in_leaves_the_thread_to_the_session(
    claimed, lane, monkeypatch
):
    """The reply is fenced to the hold under the lock its append takes, so the lane
    handing the thread over while the reply is on its way in leaves it wholly to the
    session, which a delivery prepared then would otherwise tell to answer it
    again."""
    asked = said(claimed, "Is the fence inside the append?")
    checked = thread_model.checked_text

    def bound_passes(page_dir, text):
        forks_model.look("s1", claimed, now=float("inf"))
        return checked(page_dir, text)

    monkeypatch.setattr(thread_model, "checked_text", bound_passes)
    assert forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=judged("Yes."),
        failed=None,
    ) == {"outcome": "dropped", "text": "Yes.", "work": "hand_over"}
    assert deliverable(claimed) == [asked["id"]]
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )


def test_a_thread_the_lane_going_down_gave_over_stays_with_the_session(claimed, lane):
    """A lane holds only what arrived while it ran: once it goes down, the next lane
    leaves its threads to the session, and the old fork's reply writes nothing,
    since a delivery may already be telling the session to answer them."""
    asked = said(claimed, "Still held after a restart?")
    leases_model.release_lease(lane)
    assert deliverable(claimed) == [asked["id"]]
    again = take_lane()
    try:
        assert kept_back(claimed) == []
        assert forks_model.route(
            "s1",
            basis(claimed, asked["id"], asked["id"]),
            answer=judged("Yes."),
            failed=None,
        ) == {"outcome": "dropped", "text": "Yes.", "work": "hand_over"}
    finally:
        leases_model.release_lease(again)


def test_a_fork_the_page_has_since_left_writes_nothing_on_it(claimed, lane):
    """Keeping back is the claimant's: a fork of another session's conversation, as one
    returning after the page passed to a new session, neither hands the thread over
    nor answers it."""
    asked = said(claimed, "Who holds this?")
    assert (
        forks_model.route(
            "s2",
            basis(claimed, asked["id"], asked["id"]),
            answer=judged("checking who holds it"),
            failed=None,
        )["outcome"]
        == "dropped"
    )
    assert kept_back(claimed) == [(asked["id"], (asked["id"],))]
    assert not session_file("s2", forks_model.HANDED.kind).exists()


def test_the_running_tool_reaches_the_prompt(claimed, lane):
    """Mid-turn, the session's last request predates the call it is running, so the
    fork's prompt names that call."""
    asked = said(claimed, "What are you running?")
    question = forks_model.ask(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        [{"tool": "Bash", "input": {"command": "pytest -x", "description": "tests"}}],
    )
    assert question is not None
    assert 'Bash command: "pytest -x" description: "tests"' in question["prompt"]


def test_the_pages_follower_holds_the_lane_and_lists_kept_back_threads(
    claimed, monkeypatch, capsys
):
    """Asked for forks, the follower is the session's lane while it runs and lists
    each page's kept-back threads for the module. It waits on the page's subscription,
    so a message wakes it as it is admitted rather than at the next presence read.
    Stopping with a thread kept back, it nudges what it kept back, as a watch giving
    up its lease does."""
    serving(claimed, 1)
    server_rows_model.RowPublisher(claimed, "fixture-server").refresh()
    nudged = []
    monkeypatch.setattr(session_model, "nudge_pending", nudged.append)
    asked = []
    waiting = file_changes_model.wait

    class Stopped(Exception):
        pass

    def wait(marks, _timeout):
        # A subscription a pass makes wakes those made before it once, and the
        # follower looks again.
        if waiting(marks, 0):
            return True
        if asked:
            raise Stopped
        heard, generation = file_changes_model.page_changes(claimed.resolve())
        assert heard in [changes for changes, _generation in marks]
        # Notifications of the fixture's own writes may still arrive.
        while waiting([(heard, generation)], 0.2):
            generation = heard.mark()
        past_the_take()
        asked.append(said(claimed, "Is anyone forking?"))
        assert waiting([(heard, generation)], STATED_TIMEOUT), (
            "the message woke nothing"
        )
        return True

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages(FOLLOWER)
    assert forks_model.lane_since("s1") is None
    listed = [
        json.loads(line)["pages"] for line in capsys.readouterr().out.splitlines()
    ]
    assert listed[0][0]["kept_back"] == []
    assert listed[1][0]["kept_back"] == [
        {
            "page": str(claimed.resolve()),
            "thread": asked[0]["id"],
            "inputs": [asked[0]["id"]],
        }
    ]
    assert nudged == ["s1"]


def test_a_follower_for_another_copies_module_keeps_nothing_back(
    claimed, monkeypatch, capsys
):
    """The session keeps the hooks module it loaded while its hooks run a newer
    Leaf, and that module may read kept-back threads by an older contract, so a
    follower whose module's source, as it loaded, isn't this Leaf's takes no lane
    and keeps nothing back: the session's messages reach it as they would without
    forks. It notes that verdict once in the page, however often it reads, so the
    page says why no message had a lane."""
    older = (state_model.PLUGIN_ROOT / "hooks" / "claude-code.ts").read_bytes()
    stale = hashlib.sha256(older + b"\n// an older contract\n").hexdigest()
    serving(claimed, 1)
    server_rows_model.RowPublisher(claimed, "fixture-server").refresh()

    class Stopped(Exception):
        pass

    waited = []

    def wait(_marks, _timeout):
        assert forks_model.lane_since("s1") is None, "the follower took the lane"
        if waited:
            raise Stopped
        waited.append(True)

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages({**FOLLOWER, "module": stale})
    [listed] = [
        json.loads(line)["pages"] for line in capsys.readouterr().out.splitlines()
    ]
    assert "kept_back" not in listed[0]
    [noted] = read_interactions(claimed, types=("follower",))
    assert (noted["session"], noted["module"], noted["forks"], noted["current"]) == (
        "s1",
        stale,
        True,
        False,
    )


@pytest.mark.parametrize("moved", ["selected", "protocol", "removed"])
def test_the_follower_ends_once_the_sessions_delivery_runs_another_leaf(
    claimed, monkeypatch, capsys, moved
):
    """A follower runs as long as its session, while the session's hooks hand
    themselves to whichever Leaf delivers for it now: another copy or checkout, its
    own checkout moved past a protocol bump, or another Leaf once its own is removed. The newer Leaf takes the old
    follower's lane for no one's, so the follower then ends, giving up the lane, with
    EX_TEMPFAIL for the module to start it again under that Leaf."""
    serving(claimed, 1)
    server_rows_model.RowPublisher(claimed, "fixture-server").refresh()
    monkeypatch.setattr(presence_model, "PRESENCE_CACHE_S", 0.0)
    waited = []

    def wait(_marks, _timeout):
        waited.append(True)
        return True

    monkeypatch.setattr(file_changes_model, "wait", wait)
    if moved == "selected":
        own = session_runtime_model.own_launcher()
        monkeypatch.setattr(
            session_runtime_model,
            "delivering_launcher",
            lambda _sid: own.with_name("other") if waited else own,
        )
    elif moved == "protocol":
        monkeypatch.setattr(
            kernel_model,
            "installed_protocol",
            lambda: kernel_model.kernel_protocol() + len(waited),
        )
    else:
        own = session_runtime_model.own_launcher()
        monkeypatch.setattr(
            session_runtime_model,
            "own_launcher",
            lambda: own.with_name("removed") if waited else own,
        )
    with pytest.raises(SystemExit) as ended:
        hooks_model.cmd_pages(FOLLOWER)
    assert ended.value.code == os.EX_TEMPFAIL
    assert forks_model.lane_since("s1") is None
    [listed] = [
        json.loads(line)["pages"] for line in capsys.readouterr().out.splitlines()
    ]
    assert listed[0]["kept_back"] == []


def test_the_follower_keeps_open_the_subscription_of_every_page_it_holds(
    claimed, initialized_page, tmp_path, monkeypatch
):
    """Each page's subscription lives in the page's memory, and a process keeps
    the memories of only its most recent pages unless something holds them. The
    follower holds those of every page it waits on, since with more pages than
    that it would otherwise close its own subscriptions and wake at once, pass
    after pass."""
    for n in range(page_memory_model.PageMemories.LIMIT):
        service_model.claim_page(
            initialized_page(tmp_path / f"more-{n}", page_packages())
        )

    class Stopped(Exception):
        pass

    def wait(marks, _timeout):
        assert len(marks) > page_memory_model.PageMemories.LIMIT
        assert not any(changes.closed for changes, _generation in marks)
        raise Stopped

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages(FOLLOWER)


def test_the_follower_forgets_the_bound_of_a_page_that_is_gone(claimed, monkeypatch):
    """A page that is gone holds nothing, so the follower keeps no bound of its to
    wake at: one kept past its bound would end every wait at once until the next
    presence read."""
    monkeypatch.setattr(session_model, "nudge_pending", lambda _sid: None)
    later = 0.0
    monkeypatch.setattr(
        hooks_model,
        "time",
        SimpleNamespace(
            time=lambda: time.time() + later,
            monotonic=time.monotonic,
            sleep=time.sleep,
        ),
    )
    asked = []
    timeouts = []

    class Stopped(Exception):
        pass

    def wait(_marks, timeout):
        nonlocal later
        timeouts.append(timeout)
        if not asked:
            past_the_take()
            asked.append(said(claimed, "Still there?"))
        elif len(timeouts) == 2:
            shutil.rmtree(claimed)
            later = forks_model.BOUND_S + 1
        else:
            raise Stopped
        return True

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages(FOLLOWER)
    assert timeouts[-1] > 0, "the follower kept a gone page's bound"


def test_the_follower_keeps_the_bound_of_a_page_it_does_not_list(
    claimed, monkeypatch, capsys
):
    """A page whose server isn't running goes unlisted, yet the follower still hands
    its kept-back threads to the session at their bound. That hand-over nudges for itself,
    so a follower that then exits holding nothing sends no nudge of its own, which
    could wake a session its Stop hook's watch is about to wake."""
    monkeypatch.setattr(forks_model, "BOUND_S", 0.0)
    nudged = []
    monkeypatch.setattr(session_model, "nudge_pending", nudged.append)
    asked = []

    class Stopped(Exception):
        pass

    def wait(_marks, _timeout):
        if asked:
            raise Stopped
        past_the_take()
        asked.append(said(claimed, "Is anyone serving this?"))
        return True

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages(FOLLOWER)
    assert json.loads(capsys.readouterr().out) == {"pages": [], "completions": []}
    assert forks_model.handed_inputs("s1", claimed) == {asked[0]["id"]}
    assert nudged == []


def test_a_lane_counts_from_when_it_took_the_name(claimed, lane, monkeypatch):
    """A follower writes its lease before renaming it into place, and a message can
    arrive, and the earlier lane go down, in between: the new lane counts from the
    rename, so it leaves that message to the session and the earlier fork's reply
    writes nothing, even when the filesystem clock trails the admission clock."""
    replace = os.replace
    stat = Path.stat
    lane_path = forks_model.lane_path("s1")
    asked = []

    def coarse_clock(path, *args, **kwargs):
        result = stat(path, *args, **kwargs)
        if path == lane_path:
            return os.stat_result((*result[:9], 0))
        return result

    def publish(staged, path):
        monkeypatch.setattr(os, "replace", replace)
        asked.append(said(claimed, "Arrived while the next follower started?"))
        leases_model.release_lease(lane)
        replace(staged, path)

    monkeypatch.setattr(os, "replace", publish)
    monkeypatch.setattr(Path, "stat", coarse_clock)
    again = forks_model.take_lane("s1")
    try:
        assert kept_back(claimed) == []
        assert deliverable(claimed) == [asked[0]["id"]]
        assert (
            forks_model.route(
                "s1",
                basis(claimed, asked[0]["id"], asked[0]["id"]),
                answer=judged("Yes."),
                failed=None,
            )["outcome"]
            == "dropped"
        )
    finally:
        leases_model.release_lease(again)


def test_admission_waits_for_the_lane_cutoff_to_be_published(claimed, monkeypatch):
    """An event admitted after the cutoff waits for publication before deciding
    whether to nudge the session. It cannot be deliverable now and kept back later."""
    assert stamp(claimed).exit_code == 0
    before = said(claimed, "Before the lane started")
    write = forks_model.LANE_START.write
    publishing, release = Event(), Event()
    sampled = []
    nudged = []

    def publish(path, value):
        sampled.append(value["since"])
        publishing.set()
        assert release.wait(STATED_TIMEOUT)
        return write(path, value)

    monkeypatch.setattr(forks_model.LANE_START, "write", publish)
    monkeypatch.setattr(
        endpoint_model, "nudge_unwatched", lambda page: nudged.append(page.page_dir)
    )
    monkeypatch.setattr(
        endpoint_model,
        "claim_harness",
        lambda _claim: SimpleNamespace(title_generator=lambda: None),
    )
    blocked = lock_contention(monkeypatch, forks_model.lane_lock_path("s1"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        taking = executor.submit(forks_model.take_lane, "s1")
        try:
            assert publishing.wait(STATED_TIMEOUT)
            after_cutoff = (
                datetime.fromtimestamp(sampled[0] + 0.002)
                .astimezone()
                .isoformat(timespec="milliseconds")
            )
            monkeypatch.setattr(events_model, "now_iso", lambda: after_cutoff)
            admitting = executor.submit(
                endpoint_model.accept_event,
                claimed,
                {"kind": "comment", "revision": 1, "text": "During publication"},
            )
            assert blocked.wait(STATED_TIMEOUT), (
                "admission did not wait for publication"
            )
        finally:
            release.set()
        lane = taking.result(timeout=STATED_TIMEOUT)
        try:
            status, answer = admitting.result(timeout=STATED_TIMEOUT)
            assert status == 200, answer
            [asked] = [
                event
                for event in events_model.read_events(claimed)
                if event.get("text") == "During publication"
            ]
            assert nudged == []
            assert kept_back(claimed) == [(asked["id"], (asked["id"],))]
            assert deliverable(claimed) == [before["id"]]
        finally:
            leases_model.release_lease(lane)


def test_admission_and_each_fork_say_in_the_diagnostics_why_a_message_was_kept_back(
    claimed, monkeypatch
):
    """Whether admission kept each thread message back for a line fork, and where it didn't,
    whether the session's lane was up, goes in the page's diagnostics, as does each
    fork Leaf asks for, so a message no fork took up, or whose fork never answered,
    says why."""
    assert stamp(claimed).exit_code == 0
    monkeypatch.setattr(
        endpoint_model,
        "claim_harness",
        lambda _claim: SimpleNamespace(title_generator=lambda: None),
    )

    def admit(text: str, parent: str | None = None) -> str:
        status, answer = endpoint_model.accept_event(
            claimed,
            {"kind": "reply", "parent": parent, "revision": 1, "text": text}
            if parent
            else {"kind": "comment", "revision": 1, "text": text},
        )
        assert status == 200, answer
        return answer["event"]["id"]

    early = admit("Before the lane")
    lane = take_lane()
    try:
        later = admit("After the lane, in a thread the session has", parent=early)
        asked = admit("A thread of its own")
        assert forks_model.ask(
            "s1", basis(claimed, asked, asked), [{"tool": "Bash", "input": {}}]
        )
    finally:
        leases_model.release_lease(lane)
    notes = [
        (
            row["type"],
            row.get("event"),
            row.get("kept_back"),
            row.get("lane") is not None,
        )
        if row["type"] == "fork_admission"
        else (row["type"], row["inputs"], row["running"])
        for row in read_interactions(claimed, types=("fork_admission", "fork_asked"))
    ]
    assert notes == [
        ("fork_admission", early, False, False),
        ("fork_admission", later, False, True),
        ("fork_admission", asked, True, True),
        ("fork_asked", [asked], ["Bash"]),
    ]
