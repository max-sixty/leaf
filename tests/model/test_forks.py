"""Forks of a Claude Code session: each state a thread with waiting user messages
moves through (`forks.py`'s table), what Leaf keeps back from the session meanwhile, and how
the message reads once a fork has posted the agent's working line and handed the
thread over."""

import hashlib
import json
import os
import re
import shlex
from datetime import datetime, timedelta
from threading import Condition, Thread
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    append_command,
    page_packages,
    serving,
    stamp,
)

from leaf import activity as activity_model
from leaf import agent_state as agent_state_model
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
from leaf import revision_artifact as revision_artifact_model
from leaf import revisioning as revisioning_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import session_runtime as session_runtime_model
from leaf import state as state_model
from leaf import thread as thread_model
from leaf import todos as todos_model
from leaf.events import build_threads
from leaf.findings import Rejected
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


def take_lane():
    """Take session s1's forks lane, as its pages follower does."""
    return forks_model.take_lane("s1")


@pytest.fixture
def lane(claimed):
    """Session s1's forks lane, held as its pages follower holds it."""
    held = take_lane()
    yield held
    if not held.closed:
        leases_model.release_lease(held)


def said(page_dir, text: str, parent: str | None = None) -> dict:
    """The user's message, a comment opening a thread or a reply in one, admitted
    as the event endpoint admits it, which opens a line turn for a message it keeps
    back (`forks.kept_from_main_at_admission`)."""
    record = append_carried_log_record(
        page_dir,
        {"kind": "reply", "parent": parent, "author": "user", "text": text}
        if parent
        else {"kind": "comment", "author": "user", "text": text},
    )
    with PageTransaction(page_dir) as page:
        forks_model.kept_from_main_at_admission(page, record)
    return record


def kept_back(page_dir) -> list:
    with PageTransaction(page_dir) as page:
        return [
            (thread.thread, thread.inputs) for thread in forks_model.kept_back(page)
        ]


def deliverable(page_dir) -> list[str]:
    with PageTransaction(page_dir) as page:
        return [event["id"] for event in delivery_model.deliverable(page)]


def basis(page_dir, thread: str, *inputs: str) -> dict:
    """The thread as the follower lists it, with the turn that holds it."""
    with PageTransaction(page_dir) as page:
        turn = forks_model.page_holding(page).hold(thread).turn
    return {
        "page": str(page_dir),
        "thread": thread,
        "inputs": list(inputs),
        "turn": turn,
    }


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
    """The waiting messages the page's reading words On it, as a fork's, which its
    served workflows read as `at_work`."""
    work = read_page(page_dir, events_model.read_events(page_dir)).work
    return sorted(work.holding.forked())


def test_a_kept_back_message_gets_the_forks_working_line_and_goes_to_the_session(
    claimed, lane
):
    """A message in a thread the session hasn't received is kept back: not deliverable,
    so neither a hook nor the watch hands it over, while a fork writes the agent's
    working line, and it reads On it from the start. The line goes in as the agent's
    progress without taking the message in hand, and the thread goes to the session
    at once, still owing its answer and still reading On it until that answer."""
    def delivered() -> tuple:
        """Where the message's delivery stands, and what the page's status reads."""
        activity = reading(claimed)["activity"]
        [owed] = activity["obligations"]
        return owed["stage"], owed["condition"], activity["kind"]

    state_model.close_session_turn("s1")
    idle = reading(claimed)["activity"]["kind"]
    asked = said(claimed, "Why a 2-second poll?")
    assert kept_back(claimed) == [(asked["id"], (asked["id"],))]
    assert deliverable(claimed) == []
    assert forked(claimed) == [asked["id"]]
    # The line turn's pickup holds the message without its reaching the session.
    assert delivered() == ("sent", None, idle)

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
    assert delivered() == ("sent", None, idle)
    assert session_file("s1", state_model.AGENT_TURNS.kind).resolve() in (
        outside_inputs(claimed)
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
    in, and the page reads the agent at work on it. The fork has no agent id until
    Claude Code has started it, so the main thread hears of it only then."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    turn = taken["turn"]
    assert turn in state_model.open_agent_turns("s1")
    assert taken["prompt"].startswith(forks_model.WORK_OPENING)
    assert "Which Python does the project need?" in taken["prompt"]
    # The fork's task offers each way it ends: an answer, one opening a to-do, or
    # the thread given back.
    assert "--todo" in taken["prompt"] and forks_model.HAND_BACK in taken["prompt"]
    *_line, pickup = [
        e for e in events_model.read_events(claimed) if e["kind"] == "pickup"
    ]
    assert asked["id"] in pickup["refs"]
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
    assert clerk_model.queued("s1") == []
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
    assert {
        e["turn"] for e in events_model.read_events(claimed) if e["kind"] == "pickup"
    } == {turn}


def test_the_fork_answers_with_its_own_reply_in_its_own_turn(claimed, lane):
    """The fork's commands name its turn, so its progress and answer, from the
    delivery Leaf gave it, post as the agent's, and its start names the fork's turn:
    the page reads the fork at work whatever the main thread's turn does, and the
    answer settles the message.
    The main thread hears which fork took the thread by the agent id it reaches the
    fork by, once Leaf knows it. As the fork's run ends its turn closes, and the main
    thread hears that fork answered."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    started = forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    assert started["outcome"] == "start"
    [given] = clerk_model.queued("s1")
    assert "agent id agent-1" in given and "SendMessage agent-1." in given, given
    with state_model.acting_in(taken["turn"]):
        ref = answer_ref(claimed, asked["id"])

        progress = thread_model.post_response(
            ref, "reading pyproject.toml", ephemeral=True
        )
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

        answer = thread_model.post_response(
            ref, "Python 3.12 or later.", asks_back=False
        )
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
        assert told.startswith("Your fork agent-1 answered"), told
        # Another run of the agent ends nothing more.
        assert (
            forks_model.ended("s1", agent="agent-1", turn=None, answer="", failed=None)
            == []
        )


def test_a_to_do_the_fork_opens_stays_the_sessions_after_its_turn_ends(claimed, lane):
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
    with state_model.acting_in(taken["turn"]):
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


def test_a_forks_leaf_command_acts_in_the_turn_it_names(claimed, lane):
    """The fork's task names the turn Leaf opened for it, and tells it to begin each
    `leaf` command with `leaf --turn` and that turn, which still begins with `leaf`,
    so a permission rule allowing `leaf` commands still matches it. Such a command
    acts in the turn from the fork's first command, before Claude Code has said which
    agent it spawned, so a new fork's start is its own. The command names the turn
    for itself alone, and its diagnostics name it."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    turn = taken["turn"]
    assert f"`leaf --turn {turn} thread reply …`" in taken["prompt"]
    assert state_model.agent_turns("s1")[turn]["agent"] is None

    started = CliRunner().invoke(
        cli_model.cli,
        ["--turn", turn, "task", "start", str(claimed), asked["id"]]
        + ["--text", "reading pyproject.toml"],
    )
    assert started.exit_code == 0, started.output
    [start] = [e for e in events_model.read_events(claimed) if e["kind"] == "start"]
    assert start["turn"] == turn
    assert state_model.leaf_invocation() == "leaf"
    [command] = read_interactions(claimed, types=("leaf_command",))
    assert (command["command"], command["turn"]) == ("task start", turn)


def test_an_answer_leaf_prints_for_a_fork_names_its_turn(claimed, lane):
    """Where Leaf tells a fork's command which command answers an owed message, as
    its refusal of a message that answers nothing in a thread that owes one does,
    that command names the fork's turn, so the fork that runs it as printed answers
    in its own turn rather than taking the thread for the main thread. A command
    that names no turn is told the plain command."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    turn = taken["turn"]

    def told() -> str:
        with pytest.raises(Rejected) as refused:
            thread_model.post_reply(claimed, {"parent": asked["id"]}, "Reading it.")
        [finding] = refused.value.findings
        return finding.values["answer"]

    plain = told()
    with state_model.acting_in(turn):
        answer = told()
    assert answer == plain.replace("`leaf ", f"`leaf --turn {turn} ", 1), answer
    [command] = re.findall(r"`(leaf [^`]+)`", answer)
    ran = CliRunner().invoke(
        cli_model.cli, [*shlex.split(command)[1:], "--done", "--text", "3.12."]
    )
    assert ran.exit_code == 0, ran.output
    [reply] = [e for e in events_model.read_events(claimed) if e.get("text") == "3.12."]
    assert reply["turn"] == turn


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
    assert list(dict.fromkeys(pickup["turn"] for pickup in picked)) == [
        taken["turn"],
        claim["turn"],
    ]
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


def holders(page_dir) -> tuple[dict, dict]:
    """Who `leaf page state` says owes each answer the agent owes, on its obligation
    record, by the input it answers, and who holds each thread, by its id."""
    state = agent_state_model.cmd_page_state(page_dir)
    return (
        {
            record["id"].removeprefix("update:"): record["holder"]
            for record in state["obligations"]
            if record["holder"] is not None
        },
        {thread["id"]: thread["holder"] for thread in state["threads"]},
    )


def test_page_state_names_who_has_each_answer_and_thread(claimed, lane, capsys):
    """`leaf page state` names who holds each thread: the line fork while Leaf keeps
    it back, a fork by the agent id the main thread reaches it by, null until Claude
    Code has started it, with whether its turn runs, lapsed or closed, or the main
    thread; and on each answer the agent owes, who owes it now: its thread's line fork or
    running fork, and otherwise the main thread. So a main thread recovering what it owes
    there, as after a compaction, can tell a running fork's work, and a message a
    line fork is judging, from its own: a lapsed fork's message, and one a fork gave
    back, is the main thread's to answer."""
    asked = said(claimed, "Does the suggest service cache?")
    main = {"kind": "main"}
    line = {"kind": "line", "state": "running"}
    assert holders(claimed) == ({asked["id"]: line}, {asked["id"]: line})
    taken = forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=judged("looking into the cache", "take"),
        failed=None,
        work_forks=True,
    )
    starting = {"kind": "fork", "agent": None, "state": "running"}
    assert holders(claimed) == ({asked["id"]: starting}, {asked["id"]: starting})
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    running = {"kind": "fork", "agent": "agent-1", "state": "running"}
    assert holders(claimed) == ({asked["id"]: running}, {asked["id"]: running})

    turns = state_model.agent_turns("s1")
    long_ago = datetime.now().astimezone() - activity_model.WORKING_GRACE
    turns[taken["turn"]]["renewed"] = long_ago.isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )
    lapsed = {**running, "state": "lapsed"}
    assert holders(claimed) == ({asked["id"]: main}, {asked["id"]: lapsed})
    context(capsys, "UserPromptSubmit")
    assert holders(claimed) == ({asked["id"]: main}, {asked["id"]: main})

    other, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    forks_model.started(
        "s1", basis(claimed, other["id"], other["id"]), taken["turn"], "agent-2"
    )
    forks_model.ended("s1", agent="agent-2", turn=None, answer=None, failed="it broke")
    closed = {"kind": "fork", "agent": "agent-2", "state": "closed"}
    owed, threads = holders(claimed)
    assert (owed[other["id"]], threads[other["id"]]) == (main, closed)


def test_a_fork_whose_thread_was_taken_over_can_neither_answer_nor_start_it(
    claimed, lane, capsys
):
    """A takeover takes the thread from the fork, by the same rule that
    refuses it the pickup: its reply with the answer reference its delivery gave it,
    and its start on the message, are refused once the main thread holds the
    message, and write nothing."""
    asked, taken = taken_over(claimed, capsys)
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
        ran = CliRunner().invoke(cli_model.cli, ["--turn", taken["turn"], *command])
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
    asked, first = taken_over(claimed, capsys)
    ref = answer_ref(claimed, asked["id"])
    assert thread_model.post_response(ref, "Yes, for an hour.", asks_back=False)
    events = events_model.read_events(claimed)
    stale = CliRunner().invoke(
        cli_model.cli,
        ["--turn", first["turn"], "thread", "reply", ref, "--done"]
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
            cli_model.cli, ["--turn", taken["turn"], *reply, "--text", text]
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


def test_an_answer_to_an_older_choice_leaves_the_forks_newer_message_with_the_fork(
    claimed, lane, capsys
):
    """What waits in a thread is what the fold owes: an answer settles the turns it
    responds to. So the main thread answering the user's older choice in a thread
    where a fork holds the user's newer message leaves that message, and the thread,
    with the fork, which the main thread hears beside its answer, though the choice
    names no message of the thread's. The fork's answer to the message goes in and
    ends its run as an answer, after which nothing is owed."""
    activated = revisioning_model.activate_source(claimed)
    assert activated.error is None, activated.error
    asked = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "id": "widget-thread",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-options id="thread-region" choose>'
            '<lf-option id="thread-east"><strong>East</strong></lf-option>'
            "</lf-options>",
        },
    )
    for action, detail in (("choose", {"value": ["thread-east"]}), ("answer", {})):
        chosen = append_command(
            claimed,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "thread-region",
                "action": action,
                "detail": detail,
            },
        )
    context(capsys, "UserPromptSubmit")
    choice = answer_ref(claimed, chosen["id"])
    more = said(claimed, "And why East?", parent=asked["id"])
    taken = forks_model.route(
        "s1",
        basis(claimed, asked["id"], more["id"]),
        answer=judged("looking into East", "take"),
        failed=None,
        work_forks=True,
    )
    forks_model.started(
        "s1", basis(claimed, asked["id"], more["id"]), taken["turn"], "agent-1"
    )
    fork = {"kind": "fork", "agent": "agent-1", "state": "running"}
    clerk_model.heard("s1", clerk_model.queued("s1"))
    capsys.readouterr()
    assert thread_model.post_response(choice, "Recorded East.", asks_back=False)
    assert "fork agent-1 holds this thread" in capsys.readouterr().err
    assert holders(claimed)[1][asked["id"]] == fork
    ran = CliRunner().invoke(
        cli_model.cli,
        ["--turn", taken["turn"], "thread", "reply", answer_ref(claimed, more["id"])]
        + ["--done", "--text", "East is closest to the users."],
    )
    assert ran.exit_code == 0, ran.output
    [ended] = forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    )
    assert ended["outcome"] == "answer"
    assert holders(claimed)[0] == {}


def test_the_users_rewrite_of_a_message_a_fork_holds_goes_to_the_fork(claimed, lane):
    """A user's rewrite of their message waits in its thread as a turn of its own,
    held as the thread's other messages are: by the running fork that took the
    thread, whose tool boundary carries it, rather than by the main thread."""
    asked, taken = taken_by_a_fork(claimed, "Does the suggest service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    edit = append_command(
        claimed,
        {
            "kind": "edit",
            "author": "user",
            "message": asked["id"],
            "text": "Does the autocomplete service cache?",
        },
    )
    fork = {"kind": "fork", "agent": "agent-1", "state": "running"}
    assert holders(claimed)[0][edit["id"]] == fork
    assert edit["id"] not in deliverable(claimed)
    with PageTransaction(claimed) as page:
        carried = holding_model.to_carry(forks_model.page_holding(page), taken["turn"])
    assert [event["id"] for event in carried] == [edit["id"]]


def taken_in_by_the_main_thread(page_dir, capsys, monkeypatch) -> dict:
    """The user's message in a thread of its own, which its line fork handed to the
    main thread and the main thread's prompt took in, on a page served and watched,
    with the session's transcript showing whatever a hook handed over."""
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir)
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "entered_context",
        lambda self, payload: {e["id"] for e in events_model.read_events(page_dir)},
    )
    first = said(page_dir, "What is the poll interval?")
    forks_model.route(
        "s1",
        basis(page_dir, first["id"], first["id"]),
        answer=judged("on it"),
        failed=None,
    )
    assert first["id"] in context(capsys, "UserPromptSubmit")
    return first


def answered_at_a_tool_boundary(page_dir, capsys, message: dict) -> None:
    """The main thread taking `message` in at a tool boundary, answering it, and
    ending its turn."""
    assert message["text"] in context(capsys, "PostToolBatch")
    assert thread_model.post_response(
        answer_ref(page_dir, message["id"]), "It matches the lease.", asks_back=False
    )
    context(capsys, "PostToolBatch")
    context(capsys, "Stop")


def test_input_the_main_thread_took_in_past_a_message_a_fork_holds_is_received_once(
    claimed, lane, interactive, capsys, monkeypatch
):
    """A message a running fork holds without having picked it up, the further one
    in a thread it answered, doesn't keep the main thread's later input from its
    receipt either: that input isn't handed over again once the main thread's turn
    ends, nor wakes the session again, while the fork carries the message."""
    first = taken_in_by_the_main_thread(claimed, capsys, monkeypatch)
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    with state_model.acting_in(taken["turn"]):
        assert thread_model.post_response(
            answer_ref(claimed, asked["id"]), "3.12 or later.", asks_back=False
        )
    more = said(claimed, "And 3.14?", parent=asked["id"])
    follow = said(claimed, "And the lease?", parent=first["id"])
    answered_at_a_tool_boundary(claimed, capsys, follow)
    assert deliverable(claimed) == []
    with PageTransaction(claimed) as page:
        carried = holding_model.to_carry(forks_model.page_holding(page), taken["turn"])
    assert [event["id"] for event in carried] == [more["id"]]


def test_a_kept_back_thread_the_cursor_passed_goes_to_the_main_thread_once(
    claimed, lane, interactive, capsys, monkeypatch
):
    """The page keeps one cursor, and a receipt passes what the main thread doesn't
    await as well as what it took in: a kept-back thread doesn't keep the main
    thread's later input from its receipt, to be handed over again once its turn
    ends. The cursor passing the kept-back messages hands them to nobody: they stay
    kept back. Once the line fork hands the thread over, its waiting messages go to
    the busy main thread together at its next tool boundary, since the line turn's
    `held` pickup took nothing in; once taken in, nothing in the thread is input
    there again."""
    first = taken_in_by_the_main_thread(claimed, capsys, monkeypatch)
    one = said(claimed, "Which Python does the project need?")
    two = said(claimed, "And which uv?", parent=one["id"])
    follow = said(claimed, "And the lease?", parent=first["id"])
    assert kept_back(claimed) == [(one["id"], (one["id"], two["id"]))]
    assert follow["text"] in context(capsys, "PostToolBatch")
    context(capsys, "PostToolBatch")
    with PageTransaction(claimed) as page:
        assert page.cursor >= two["seq"]
    assert deliverable(claimed) == []
    assert kept_back(claimed) == [(one["id"], (one["id"], two["id"]))]

    forks_model.route(
        "s1",
        basis(claimed, one["id"], one["id"], two["id"]),
        answer=judged("checking the versions"),
        failed=None,
    )
    handed = context(capsys, "PostToolBatch")
    assert one["text"] in handed and two["text"] in handed
    assert not hook_transport_model.new_input("s1")


def test_a_prompt_while_a_message_is_kept_back_leaves_it_to_the_line_fork(
    claimed, lane, interactive, capsys, monkeypatch
):
    """A prompt that reaches the session while Leaf keeps a message back, typed or
    a wake for other input, neither shows it nor takes it for the main thread,
    though the cursor has passed it: the line fork still holds it and posts its
    line, and the main thread's next tool boundary takes it in once the line fork
    hands it over."""
    taken_in_by_the_main_thread(claimed, capsys, monkeypatch)
    context(capsys, "Stop")
    kept = said(claimed, "Which Python does the project need?")
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt_id": "p2"},
    )
    assert kept["text"] not in capsys.readouterr().out
    assert kept_back(claimed) == [(kept["id"], (kept["id"],))]
    claim = service_model.page_claim(claimed)
    assert claim is not None
    assert not [
        event
        for event in events_model.read_events(claimed)
        if event["kind"] == "pickup"
        and kept["id"] in event["events"]
        and event["turn"] == claim["turn"]
    ]
    routed = forks_model.route(
        "s1",
        basis(claimed, kept["id"], kept["id"]),
        answer=judged("checking the Python version"),
        failed=None,
    )
    assert routed["outcome"] == "hand_over"
    assert kept["text"] in context(capsys, "PostToolBatch")


def test_a_quiet_tool_boundary_of_a_session_with_forks_reads_no_holding(
    claimed, lane, interactive, capsys, monkeypatch
):
    """Claude Code runs the tool-boundary hook after every batch of tool calls, and
    who holds each thread costs a walk of the page's threads, about 50 ms on a page
    of 41,000 events. A boundary with no input past the cursor and none the cursor
    passed that no pickup took in has nothing that reading could change, so a
    session with an agent's turn open and its lane up reads the page's log alone."""
    taken_in_by_the_main_thread(claimed, capsys, monkeypatch)
    state_model.open_agent_turn("s1")
    context(capsys, "PostToolBatch")

    def unread(*args, **kwargs):
        raise AssertionError("the quiet tool boundary read who holds each thread")

    monkeypatch.setattr(holding_model, "rounds", unread)
    assert context(capsys, "PostToolBatch") == ""


def test_a_kept_back_message_in_a_thread_the_user_resolved_is_no_input(
    claimed, lane, interactive, capsys, monkeypatch
):
    """A message the cursor passed while Leaf kept it back, in a thread the user
    resolved before the line fork answered, is owed nobody: once the main thread's
    tool boundary has taken in the resolution, nothing on the page is input
    there."""
    first = taken_in_by_the_main_thread(claimed, capsys, monkeypatch)
    kept = said(claimed, "Which Python does the project need?")
    follow = said(claimed, "And the lease?", parent=first["id"])
    assert follow["text"] in context(capsys, "PostToolBatch")
    context(capsys, "PostToolBatch")
    append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": kept["id"]}
    )
    assert kept_back(claimed) == []
    context(capsys, "PostToolBatch")
    assert not hook_transport_model.new_input("s1")


def test_a_running_forks_tool_boundary_carries_a_rewrite_as_logged(
    claimed, lane, capsys
):
    """A fork's tool boundary hands it the user's further message and their rewrite
    of it as every delivery hands them over: the message in the words it was sent
    with, and the rewrite beside it with the words it replaced, not the thread's
    reading of the message, which carries the rewrite's words."""
    asked, taken = taken_by_a_fork(claimed, "Does the suggest service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    more = said(claimed, "And the autocomplet service?", parent=asked["id"])
    append_command(
        claimed,
        {
            "kind": "edit",
            "author": "user",
            "message": more["id"],
            "text": "And the autocomplete service?",
        },
    )
    _opening, envelope = agent_context(capsys, "agent-1").split("\n", 1)
    [batch] = json.loads(envelope)["batches"]
    assert [
        (event["kind"], event["text"], event.get("was"), "edited" in event)
        for event in batch["events"]
    ] == [
        ("reply", "And the autocomplet service?", None, False),
        (
            "edit",
            "And the autocomplete service?",
            "And the autocomplet service?",
            False,
        ),
    ]


def test_the_hooks_read_a_thread_a_version_reopened_as_the_fold_does(
    claimed, monkeypatch
):
    """A thread a widget's answer closed, which a later version takes back through
    an element containing the widget, waits again: the hooks build the page's
    threads with its containment, as the fold does, so both read the same message
    waiting."""
    events = events_model.read_events(claimed)
    seq = events[-1]["seq"] if events else 0
    ts = "2026-11-14T00:00:00+00:00"
    logged = [
        {"kind": "comment", "id": "contained-c1", "author": "user"}
        | {"text": "Tighten this section?"},
        {"kind": "action", "id": "contained-a1", "author": "user", "revision": 1}
        | {"widget": "w1", "action": "answer", "detail": {}}
        | {"meaning": {"unit": "w1", "answer": "contained-c1", "depends": ["sec1"]}},
        {"kind": "note", "id": "contained-n1", "author": "agent", "revision": 2}
        | {"restated": ["sec1"], "text": "Rewrote the section."},
    ]
    with (claimed / "events.jsonl").open("a", encoding="utf-8") as log:
        for offset, event in enumerate(logged, 1):
            log.write(json.dumps({**event, "seq": seq + offset, "ts": ts}) + "\n")
    monkeypatch.setattr(
        revision_artifact_model, "active_enclosing", lambda page_dir: {"sec1": ["w1"]}
    )
    with PageTransaction(claimed) as page:
        held = forks_model.page_holding(page)
    assert [event["id"] for event in held.found.waiting["contained-c1"]] == [
        "contained-c1"
    ]


def test_a_running_fork_carries_nothing_of_a_thread_the_user_resolved(claimed, lane):
    """A further message in a thread a running fork holds, which the user then
    resolved, is owed nobody, so the fork's tool boundary doesn't carry it."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does it need?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    said(claimed, "And 3.14?", parent=asked["id"])
    append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": asked["id"]}
    )
    with PageTransaction(claimed) as page:
        assert (
            holding_model.to_carry(forks_model.page_holding(page), taken["turn"]) == []
        )


def test_the_main_thread_answering_over_a_running_fork_takes_its_thread(
    claimed, lane, capsys
):
    """The main thread is sovereign: its answer to a message a running fork holds
    takes the thread over at once, with whatever answer reference it uses, since
    the answer names the turn that posted it. A command acting as the main thread
    goes through on the fork's thread and says beside its result which fork it
    acted beside, by its agent id once Claude Code has started it, and, for an
    answer, that it took the thread and how to stop the fork. The fork's later
    reply with that reference is refused rather than handed the main thread's answer
    as the repeat of its own, and so are its start on the message and a message of
    its own in the thread that answers nothing. Its end reports the thread
    taken over, which the main thread isn't told of, and the thread's next message
    goes to a new fork rather than to that one, resumed."""
    asked, taken = taken_by_a_fork(claimed, "Does the suggest service cache?")
    capsys.readouterr()
    assert todos_model.cmd_start(claimed, asked["id"], "checking the cache")
    beside = capsys.readouterr().err
    assert "a fork Leaf is starting holds this thread" in beside, beside
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    ref = answer_ref(claimed, asked["id"])
    answer = thread_model.post_response(ref, "Yes, for an hour.", asks_back=False)
    took = capsys.readouterr().err
    assert "fork agent-1 held this thread" in took, took
    assert "to stop the fork, SendMessage agent-1" in took, took
    claim = service_model.page_claim(claimed)
    assert answer is not None and claim is not None
    assert answer["turn"] == claim["turn"]
    events = events_model.read_events(claimed)
    for command in (
        ["thread", "reply", ref, "--done", "--text", "No, it never caches."],
        ["task", "start", str(claimed), asked["id"], "--text", "checking the cache"],
    ):
        ran = CliRunner().invoke(cli_model.cli, ["--turn", taken["turn"], *command])
        assert ran.exit_code != 0, command
        assert "no longer holds" in ran.output, ran.output
    with state_model.acting_in(taken["turn"]):
        with pytest.raises(delivery_model.ReceiptRefused, match="no longer holds"):
            thread_model.post_reply(
                claimed,
                {"parent": asked["id"]},
                "No, it never caches.",
                todo="Check it",
            )
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


def held_by_a_running_fork(page_dir, text: str) -> tuple[dict, str]:
    """The user's message in a thread a fork took and is still running in, and what
    a command acting as the main session hears it is told beside its result."""
    asked, taken = taken_by_a_fork(page_dir, text)
    forks_model.started(
        "s1", basis(page_dir, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    return asked, "fork agent-1 holds this thread"


def test_a_message_beside_a_forks_answer_leaves_the_fork_holding_the_thread(
    claimed, lane, capsys
):
    """Only an answer, which responds to a message, takes a thread. A message of the
    main session's own in a thread a running fork has answered responds to nothing,
    so the fork still holds the thread, which the message says beside its result
    rather than that it took it."""
    asked, holds = held_by_a_running_fork(claimed, "Which Python does it need?")
    turn = state_model.agent_turn_of("s1", "agent-1")
    assert turn is not None
    ran = CliRunner().invoke(
        cli_model.cli,
        ["--turn", turn, "thread", "reply", answer_ref(claimed, asked["id"])]
        + ["--done", "--text", "Python 3.12 or later."],
    )
    assert ran.exit_code == 0, ran.output
    capsys.readouterr()
    thread_model.post_reply(claimed, {"parent": asked["id"]}, "3.13 works too.")
    beside = capsys.readouterr().err
    assert holds in beside and "took the thread" not in beside, beside


def test_a_command_from_outside_the_session_hears_of_the_fork_holding_the_thread(
    claimed, lane, capsys, monkeypatch
):
    """A command acting as the main session hears of the fork that holds its thread
    whoever runs it, a terminal outside the session included, whose commands name no
    session."""
    asked, holds = held_by_a_running_fork(claimed, "Does the suggest service cache?")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    capsys.readouterr()
    assert todos_model.cmd_start(claimed, asked["id"], "checking the cache")
    beside = capsys.readouterr().err
    assert holds in beside, beside


def test_a_start_on_a_to_do_in_a_forks_thread_hears_of_the_fork(claimed, lane, capsys):
    """A to-do attached to a thread stands in that thread, so a start on it in the
    main session's name, as on one of the thread's messages, hears of the running
    fork that holds the thread."""
    asked, holds = held_by_a_running_fork(claimed, "Does the suggest service cache?")
    todo = todos_model.cmd_create(claimed, asked["id"], "Check the cache config")
    capsys.readouterr()
    assert todos_model.cmd_start(claimed, todo["id"], "checking the config")
    beside = capsys.readouterr().err
    assert holds in beside, beside


def test_only_a_commands_own_write_hears_of_the_line_fork_holding_its_thread(
    claimed, lane, capsys
):
    """While Leaf keeps a thread back, a command acting as the main session hears of
    the line fork that holds it, and Leaf's own post of the line fork's working
    message, in the claimant's name, says nothing beside it."""
    asked = said(claimed, "Why a 2-second poll?")
    capsys.readouterr()
    assert todos_model.cmd_start(claimed, asked["id"], "reading the poll")
    beside = capsys.readouterr().err
    assert "a line fork holds this thread" in beside, beside
    handed = forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=judged("reading the poll code"),
        failed=None,
    )
    assert handed["outcome"] == "hand_over"
    assert "fork-holds-thread" not in capsys.readouterr().err


def test_a_session_that_ended_names_its_forks_threads_and_hands_nothing_on(
    claimed, lane
):
    """A session that has ended still names the fork that held each thread in
    `leaf page state`, but holds nothing for delivery: the message its fork picked
    up is no input for it, as the fold's and the page's readings agree."""
    asked, _holds = held_by_a_running_fork(claimed, "Does the suggest service cache?")
    state_model.end_session("s1")
    _owed, threads = holders(claimed)
    assert threads[asked["id"]]["kind"] == "fork"
    assert deliverable(claimed) == []
    with PageTransaction(claimed) as page:
        assert not forks_model.page_holding(page).live
        assert delivery_model.deliverable(page, received=False) == []


def test_a_waiting_messages_pickup_holds_its_thread_over_an_older_messages_newer():
    """A thread's holder is the turn whose pickup of one of its waiting messages is
    newest, even where another turn picked up an older message of the thread later,
    as a late acknowledgement does: the turn that took the waiting messages holds
    them."""
    events = [
        {"kind": "comment", "id": "c1", "author": "user", "seq": 1},
        {
            "kind": "reply",
            "id": "a1",
            "author": "agent",
            "parent": "c1",
            "responds": "c1",
            "turn": "t0",
            "seq": 2,
        },
        {"kind": "reply", "id": "u2", "author": "user", "parent": "a1", "seq": 3},
        *(
            {
                "kind": "pickup",
                "id": f"p{seq}",
                "phase": "opened",
                "session": "s1",
                "turn": turn,
                "events": [input_id],
                "seq": seq,
            }
            for seq, turn, input_id in ((4, "waiting", "u2"), (5, "older", "c1"))
        ),
    ]
    held = holding_model.reading(
        events,
        "s1",
        {},
        set(),
        live=True,
        found=holding_model.rounds(events, build_threads(events, {})),
    ).hold("c1")
    assert (held.turn, held.picked) == ("waiting", True)


def test_a_forks_end_reports_only_what_its_own_turn_wrote(claimed, lane):
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
    with state_model.acting_in(taken["turn"]):
        assert thread_model.post_response(
            answer_ref(claimed, asked["id"]), "The cache starts cold.", asks_back=False
        )
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


def fork_ends(page_dir, asked: dict, agent: str, **reply) -> str:
    """The fork `agent`'s reply to `asked` from its own turn, with `reply`'s options,
    and then the end of its run; what `forks.ended` judged of the thread."""
    turn = state_model.agent_turn_of("s1", agent)
    assert turn is not None
    with state_model.acting_in(turn):
        assert thread_model.post_response(
            answer_ref(page_dir, asked["id"]), f"An answer to: {asked['text']}", **reply
        )
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

    answered = fork_ends(claimed, asked, "agent-1", asks_back=False)
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
    assert fork_ends(claimed, later, "agent-2", todo=todo) == "todo"
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

    assert fork_ends(claimed, asked, "agent-1", asks_back=False) == ("answer")
    assert nudged == []

    todo = "Profile the warm start"
    assert fork_ends(claimed, later, "agent-2", todo=todo) == "todo"
    [(page, owed)] = nudged
    assert page == claimed.resolve()
    assert any("“Profile the warm start”" in line for line in owed)

    fork_ends(claimed, last, "agent-3", todo="Profile the build")
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
    fork's turn, and the main thread is handed none of it meanwhile. The fork's
    reading names each next command with the fork's turn, its acknowledgement among
    them, so the fork that runs them as printed acts in its turn."""
    asked, taken = taken_by_a_fork(claimed, "Does the autocomplete service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    more = said(claimed, "Here is its config:\n" + "cache: warm\n" * 2400, asked["id"])
    pointer = agent_context(capsys, "agent-1")
    [delivery] = re.findall(r'<leaf-delivery id="([0-9a-f]+)"', pointer)
    assert agent_context(capsys, "agent-1") == ""
    assert deliverable(claimed) == []

    commands = [f"leaf --turn {taken['turn']} delivery read {delivery}"]
    while commands[-1]:
        read = CliRunner().invoke(cli_model.cli, shlex.split(commands[-1])[1:])
        assert read.exit_code == 0, read.output
        reading = json.loads(read.stdout)
        commands.append(reading.get("next"))
    assert len(commands) > 2
    assert all(c.startswith(f"leaf --turn {taken['turn']} ") for c in commands[:-1])
    [ack] = re.findall(r"`(leaf [^`]+)`", reading["acknowledge"])
    assert ack == f"leaf --turn {taken['turn']} delivery ack {delivery}"
    acked = CliRunner().invoke(cli_model.cli, shlex.split(ack)[1:])
    assert acked.exit_code == 0, acked.output
    pickup = [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"][-1]
    assert (pickup["events"], pickup["turn"]) == ([more["id"]], taken["turn"])
    assert deliverable(claimed) == []
    assert agent_context(capsys, "agent-1") == ""


def answered_by_a_fork(page_dir, text: str, agent: str) -> dict:
    """The user's message in a thread of its own, which a fork the module spawned as
    `agent` took, answered from its own turn, and ended; the message."""
    asked, taken = taken_by_a_fork(page_dir, text)
    forks_model.started(
        "s1", basis(page_dir, asked["id"], asked["id"]), taken["turn"], agent
    )
    with state_model.acting_in(taken["turn"]):
        assert thread_model.post_response(
            answer_ref(page_dir, asked["id"]), f"The answer to: {text}", asks_back=False
        )
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


def test_a_follow_up_after_the_forks_run_goes_to_that_fork_again(claimed, lane):
    """The user's further message in a thread a fork answered, once the fork's run
    has ended, goes to the same fork in a new turn of its own, which Leaf opens,
    names with the fork's agent id and records the pickup in, so the fork works the
    thread however many messages it gets; the main thread hears which fork has the
    thread, by that id, once the module confirms it resumed the fork; a turn's
    agent never changes once named. Leaf's message resuming it carries the delivery,
    names the new turn its commands name in place of the one its transcript names,
    and tells the fork to read the page's state, which its transcript lacks. A
    command naming the earlier turn is refused, and a late end of that turn leaves
    the new one running. The fork's answer from the new turn is its own, and the
    turn's end reports it."""
    asked = answered_by_a_fork(claimed, "Which Python?", "agent-1")
    more = said(claimed, "And which uv?", parent=asked["id"])
    taken = taken_again(claimed, asked["id"], more)
    assert taken["resume"] == "agent-1"
    assert state_model.agent_turn_of("s1", "agent-1") == taken["turn"]
    assert clerk_model.queued("s1") == []
    forks_model.started(
        "s1", basis(claimed, asked["id"], more["id"]), taken["turn"], "agent-1"
    )
    [given] = clerk_model.queued("s1")
    assert "SendMessage agent-1." in given, given
    assert forks_model.started(
        "s1", basis(claimed, asked["id"], more["id"]), taken["turn"], "agent-2"
    )["outcome"] == ("dropped")
    [earlier] = set(state_model.agent_turns("s1")) - {taken["turn"]}
    stale = CliRunner().invoke(
        cli_model.cli,
        ["--turn", earlier, "thread", "reply", answer_ref(claimed, more["id"])]
        + ["--done", "--text", "uv 0.9 or later."],
    )
    assert f"turn {earlier} is not an open agent turn" in stale.output, stale.output
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
    assert f"`leaf --turn {taken['turn']} page state {claimed}`" in resume
    assert "--todo" in resume and forks_model.HAND_BACK in resume

    with state_model.acting_in(taken["turn"]):
        answer = thread_model.post_response(
            answer_ref(claimed, more["id"]), "uv 0.9 or later.", asks_back=False
        )
        assert answer is not None and answer["responds"] == more["id"]
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    ) == [{"page": str(claimed), "thread": asked["id"], "outcome": "answer"}]
    assert state_model.open_agent_turns("s1") == {}


def test_a_thread_whose_fork_cannot_be_resumed_goes_to_the_main_thread(claimed, lane):
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

    earlier = answered_by_a_fork(claimed, "Which region?", "agent-2")
    turns = state_model.agent_turns("s1")
    for entry in turns.values():
        entry["generation"] = "an earlier generation"
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )
    later = said(claimed, "And staging?", parent=earlier["id"])
    assert "resume" not in taken_again(claimed, earlier["id"], later)

    lost = answered_by_a_fork(claimed, "Which shard?", "agent-3")
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


def test_one_fork_works_a_thread_while_its_turn_runs(claimed, lane, capsys):
    """A thread a running fork turn took is never kept back for a second fork. The
    user's message after the fork answered, while its turn still runs, is that
    fork's: the main thread isn't given it, and the fork's next tool boundary
    carries it. One that arrives in the fork's last moments, which its run never
    carries, goes to the main thread as the run ends, even where a receipt passed
    the log meanwhile, rather than to the same fork resumed, since Leaf decides
    whether to keep a message back only as it admits it, as the user accepted on
    2026-11-15. A resumed fork whose message the user took back still holds the
    thread's next one; a thread the main thread took over by answering, while the
    fork still runs, gives its next message to the main thread; and a thread a
    running fork took by answering a message in it gives its next message to that
    fork."""
    zone, running = taken_by_a_fork(claimed, "Which zone?")
    forks_model.started(
        "s1", basis(claimed, zone["id"], zone["id"]), running["turn"], "agent-5"
    )
    clerk_model.heard("s1", clerk_model.queued("s1"))
    with state_model.acting_in(running["turn"]):
        assert thread_model.post_response(
            answer_ref(claimed, zone["id"]), "us-east-1b.", asks_back=False
        )
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

    with state_model.acting_in(running["turn"]):
        assert thread_model.post_response(
            answer_ref(claimed, soon["id"]), "us-east-1c.", asks_back=False
        )
    late = said(claimed, "And the third?", parent=zone["id"])
    assert kept_back(claimed) == []
    # Another fork's take records a receipt, which passes the message the running
    # fork holds.
    taken_by_a_fork(claimed, "Which shard is hot?")
    assert late["id"] not in deliverable(claimed)
    forks_model.ended("s1", agent="agent-5", turn=None, answer="Done.", failed=None)
    assert kept_back(claimed) == []
    assert late["id"] in deliverable(claimed)
    assert late["text"] in context(capsys, "PostToolBatch")

    region = answered_by_a_fork(claimed, "Which region now?", "agent-6")
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

    # A message no line turn holds, admitted with no follower up, which the running
    # fork may answer.
    leases_model.release_lease(lane)
    elsewhere = said(claimed, "Which region is that shard in?")
    again = take_lane()
    try:
        with state_model.acting_in(kept["turn"]):
            assert thread_model.post_reply(
                claimed, {"responds": elsewhere["id"]}, "eu-west."
            )
        after = said(claimed, "And its replica's?", parent=elsewhere["id"])
        assert kept_back(claimed) == []
        assert after["id"] in agent_context(capsys, "agent-7")
    finally:
        leases_model.release_lease(again)


def lapse(turn: str) -> None:
    """Leave the agent turn `turn` unrenewed for the working grace."""
    turns = state_model.agent_turns("s1")
    long_ago = datetime.now().astimezone() - activity_model.WORKING_GRACE
    turns[turn]["renewed"] = long_ago.isoformat()
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
        held = forks_model.page_holding(page).of(more["id"])
    assert (held.turn, held.picked) == (claim["turn"], True)

    late = CliRunner().invoke(
        cli_model.cli, ["--turn", taken["turn"], "delivery", "ack", stale]
    )
    assert late.exit_code != 0
    assert "no longer holds" in late.output
    with PageTransaction(claimed) as page:
        assert forks_model.page_holding(page).of(more["id"]) == held


def test_a_handed_over_message_acknowledged_by_pointer_is_no_repeat(
    claimed, lane, capsys
):
    """A kept-back message the line fork hands over, too large for the hook, reaches
    the main thread by pointer, and its acknowledgement says nothing of an earlier
    turn having picked it up: the line turn's pickup at admission did no work the
    main thread could repeat."""
    asked = said(claimed, "Here is the config:\n" + "cache: warm\n" * 1200)
    handed = forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=judged("reading the config"),
        failed=None,
    )
    assert handed["outcome"] == "hand_over", handed
    pointer = pointer_in(context(capsys, "UserPromptSubmit"))
    assert pointer is not None
    acked = CliRunner().invoke(cli_model.cli, ["delivery", "ack", pointer])
    assert acked.exit_code == 0, acked.output
    assert "earlier turn" not in acked.output + capsys.readouterr().err


def test_a_command_naming_a_turn_that_is_not_open_acts_as_nobody(
    claimed, lane, capsys, monkeypatch
):
    """A command naming a fork's turn that has ended, as a fork's command run late
    does, is refused, whatever it is: its reply, its start, its acknowledgement, a
    to-do or a thread of its own each say the turn isn't open, rather than acting
    with the main thread's authority. So is one naming the main thread's turn, a
    turn the session never opened, or any turn where no session runs it."""
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
    reply = ["thread", "reply", ref, "--done", "--text", "Yes, for a minute."]
    claim = service_model.page_claim(claimed)
    assert claim is not None
    for turn, command in (
        (taken["turn"], reply),
        (taken["turn"], ["task", "start", str(claimed), asked["id"], "--text", "x"]),
        (taken["turn"], ["delivery", "ack", ref.partition(":")[0]]),
        (taken["turn"], ["task", "create", str(claimed), "page", "--title", "Check"]),
        (taken["turn"], ["thread", "create", str(claimed), "--text", "A minute."]),
        (claim["turn"], reply),
        ("0123456789abcdef", reply),
    ):
        ran = CliRunner().invoke(cli_model.cli, ["--turn", turn, *command])
        assert ran.exit_code != 0, command
        assert f"turn {turn} is not an open agent turn" in ran.output, ran.output
    assert events_model.read_events(claimed) == events
    # Each one's record in the page says it was refused.
    commands = read_interactions(claimed, types=("leaf_command",))
    assert len(commands) == 7
    assert all("is not an open agent turn" in c["refused"] for c in commands)

    other, running = taken_by_a_fork(claimed, "Which Python does it need?")
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    ran = CliRunner().invoke(
        cli_model.cli,
        ["--turn", running["turn"], "thread", "reply", answer_ref(claimed, other["id"])]
        + ["--done", "--text", "3.12."],
    )
    assert f"turn {running['turn']} is not an open agent turn" in ran.output
    assert not [
        e for e in events_model.read_events(claimed) if e.get("text") == "3.12."
    ]


def test_a_fork_that_answered_is_reported_however_its_thread_moves_on(
    claimed, lane, capsys
):
    """The end of a fork's run is judged by the messages its turn picked up itself.
    A fork that answered is reported as answering though the user writes again
    before its run ends, and the message its run never carried goes to the main
    thread as the run ends; and one whose turn lapsed and lost its thread to the main
    thread's pickup is reported as taken over, with no line telling the main thread
    it was given a thread it took itself."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    with state_model.acting_in(taken["turn"]):
        thread_model.post_response(
            answer_ref(claimed, asked["id"]), "Python 3.12 or later.", asks_back=False
        )
    uv = said(claimed, "And which uv?", parent=asked["id"])
    clerk_model.heard("s1", clerk_model.queued("s1"))
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Answered.", failed=None
    ) == [{"page": str(claimed), "thread": asked["id"], "outcome": "answer"}]
    [told] = clerk_model.queued("s1")
    assert "answered" in told and "written there since" in told
    assert kept_back(claimed) == []
    assert uv["id"] in deliverable(claimed)

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


def test_a_fork_cannot_start_on_a_to_do_in_a_thread_another_turn_took(claimed, lane):
    """A to-do on a thread stands in that thread, so a fork whose thread the main
    thread took over by answering can't start on the main thread's to-do there, as it
    can't start on the thread's message."""
    asked, _holds = held_by_a_running_fork(claimed, "Does the suggest service cache?")
    turn = state_model.agent_turn_of("s1", "agent-1")
    assert turn is not None
    assert thread_model.post_response(
        answer_ref(claimed, asked["id"]), "Yes, for an hour.", asks_back=False
    )
    main_thread_opens_a_to_do(claimed, asked["id"])
    [todo] = todos_model.TodoReading(events_model.read_events(claimed)).owed
    ran = CliRunner().invoke(
        cli_model.cli,
        ["--turn", turn, "task", "start", str(claimed), todo["id"]]
        + ["--text", "profiling it"],
    )
    assert ran.exit_code != 0
    assert "no longer holds" in ran.output, ran.output


def test_a_fork_ending_on_a_thread_the_user_resolved_hands_nothing_back(
    claimed, lane, capsys
):
    """A message waiting in a thread the user resolved is owed nobody, so a fork
    whose run ends on it hands nothing back: its work on the thread ends as
    `resolved`, the main thread hears of no thread given back, and its next prompt
    brings only the resolution."""
    asked, _holds = held_by_a_running_fork(claimed, "Which Python does it need?")
    resolved = append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": asked["id"]}
    )
    assert forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Nothing to answer.", failed=None
    ) == [{"page": str(claimed), "thread": asked["id"], "outcome": "resolved"}]
    assert [
        (row["thread"], row["inputs"])
        for row in read_interactions(claimed, types=("fork_outcome",))
        if row.get("step") == "end"
    ] == [(asked["id"], [asked["id"]])]
    assert clerk_model.queued("s1") == []
    _opening, envelope = context(capsys, "UserPromptSubmit").split("\n", 1)
    [batch] = json.loads(envelope)["batches"]
    assert [event["id"] for event in batch["events"]] == [resolved["id"]]


def test_a_page_reads_only_the_agent_turns_it_needs(claimed, lane):
    """What a page's reading carries of its session's agent turns grows with the page,
    not with how long the session has run: each turn still open, and each one its
    log names, whose holder page state names, but not a closed turn of another page's.
    A turn of an earlier generation of the session leaves the record as the next
    opens."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does it need?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    elsewhere = state_model.open_agent_turn("s1")
    assert elsewhere is not None
    state_model.close_agent_turns("s1", turn=elsewhere)

    def served() -> set[str]:
        return set(
            presence_model.presence(claimed, events_model.read_events(claimed))[
                "agent_turns"
            ]
        )

    assert served() == {taken["turn"]}
    forks_model.ended("s1", agent="agent-1", turn=None, answer="Done.", failed=None)
    assert served() == {taken["turn"]}

    turns = state_model.agent_turns("s1")
    turns["earlier"] = {**turns[elsewhere], "generation": "an earlier one"}
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )
    assert state_model.open_agent_turn("s1") is not None
    assert "earlier" not in state_model.agent_turns("s1")
    assert {taken["turn"], elsewhere} <= set(state_model.agent_turns("s1"))


def opened_long_ago(turn: str, by: timedelta) -> None:
    """Move the session's agent turn `turn` back by `by`, its opening and its last
    renewal both, as a turn nothing has touched since then reads."""
    turns = state_model.agent_turns("s1")
    for key in ("opened", "renewed"):
        turns[turn][key] = (datetime.fromisoformat(turns[turn][key]) - by).isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )


def test_a_take_the_module_never_names_lets_its_thread_go_within_30_s(claimed, lane):
    """A turn Leaf passed to a fork the module never names, as when the step that
    took the thread timed out or the module was reloaded, has lost its agent. It
    counts for `STARTING_GRACE` from its opening, and then lapses: the thread is the
    main thread's again."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    opened_long_ago(taken["turn"], activity_model.STARTING_GRACE)
    owed, threads = holders(claimed)
    assert (owed[asked["id"]], threads[asked["id"]]["state"]) == (
        {"kind": "main"},
        "lapsed",
    )
    assert deliverable(claimed) == [asked["id"]]
    # Nor does any page that never named the lost turn read it.
    claim = service_model.page_claim(claimed)
    assert claim is not None
    assert taken["turn"] not in state_model.agent_turn_stamps(claim, [])


@pytest.mark.parametrize("confirmed", [False, True])
def test_a_resumed_take_counts_for_30_s_until_its_start_is_confirmed(
    claimed, lane, confirmed
):
    """A fork Leaf resumes is named as its line turn passes to it, but the turn counts
    only for `STARTING_GRACE` until the module confirms the resume
    (`forks.started`), so a resume whose step timed out leaves the thread to the main
    thread within 30 s; once confirmed, the turn counts for the working grace."""
    asked = answered_by_a_fork(claimed, "Which Python?", "agent-1")
    more = said(claimed, "And which uv?", parent=asked["id"])
    taken = taken_again(claimed, asked["id"], more)
    if confirmed:
        forks_model.started(
            "s1", basis(claimed, asked["id"], more["id"]), taken["turn"], "agent-1"
        )
    opened_long_ago(taken["turn"], activity_model.STARTING_GRACE)
    _owed, threads = holders(claimed)
    assert threads[asked["id"]]["state"] == ("running" if confirmed else "lapsed")
    assert deliverable(claimed) == ([] if confirmed else [more["id"]])


def test_the_reading_changes_when_a_turn_whose_start_is_unconfirmed_lapses(
    claimed, lane
):
    """The served reading says it next changes when a turn whose start nothing has
    confirmed lapses, 30 s after its opening, rather than at the working
    grace."""
    _asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    opened = datetime.fromisoformat(
        state_model.agent_turns("s1")[taken["turn"]]["opened"]
    )
    due = datetime.fromisoformat(reading(claimed)["activity"]["next_transition_at"])
    assert due - opened == activity_model.STARTING_GRACE


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
    gave = clerk_model.queued("s1")[-1]
    assert gave.startswith(f"Your fork agent-1 gave thread {asked['id']}"), gave

    unstarted, given = taken_by_a_fork(claimed, "How many shards does staging have?")
    [failed] = forks_model.ended(
        "s1", agent=None, turn=given["turn"], answer=None, failed="it did not start"
    )
    assert failed["why"] == "the fork failed: it did not start"
    # A fork that never started has no agent id to name.
    gave = clerk_model.queued("s1")[-1]
    assert gave.startswith(f"Your fork gave thread {unstarted['id']}"), gave

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


def test_a_hold_ends_as_its_line_turn_lapses(claimed, lane):
    """However the line fork fares, its turn lapses a `STARTING_GRACE` after it
    opened, since nothing renews a line turn, and the message is the main thread's."""
    asked = said(claimed, "Is the bound from the newest message?")
    assert kept_back(claimed) == [(asked["id"], (asked["id"],))]
    assert deliverable(claimed) == []
    turns = state_model.agent_turns("s1")
    long_ago = (datetime.now().astimezone() - activity_model.STARTING_GRACE).isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind),
        {
            "turns": {
                turn: {**entry, "opened": long_ago, "renewed": long_ago}
                for turn, entry in turns.items()
            }
        },
    )
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"]]
    assert forked(claimed) == []


def test_without_a_lane_nothing_is_kept_back(claimed):
    """A session without Leaf's hooks module, or any other harness, delivers as
    before."""
    asked = said(claimed, "Anyone there?")
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"]]


def test_a_message_while_kept_back_joins_the_line_turn_and_goes_where_it_goes(
    claimed, lane
):
    """A second message in a kept-back thread is the line turn's too, as any running
    turn's thread's further messages are: the follower lists the thread with both
    under the one turn, so the module asks no second line fork, as the user accepted
    on 2026-11-15. The line the first message's line fork writes goes in nowhere,
    since the thread's newest message carries its one answer, so the line turn ends
    and the thread goes to the main thread with both messages and no line."""
    first = said(claimed, "Why 30 s?")
    line_turn = basis(claimed, first["id"])["turn"]
    second = said(claimed, "Or rather, why not 20?", parent=first["id"])
    assert kept_back(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert basis(claimed, first["id"])["turn"] == line_turn
    assert deliverable(claimed) == []

    routed = forks_model.route(
        "s1",
        basis(claimed, first["id"], first["id"]),
        answer=judged("checking why 30 s", "take"),
        failed=None,
        work_forks=True,
    )
    assert (routed["outcome"], "line" in routed) == ("hand_over", False), routed
    assert line_turn not in state_model.open_agent_turns("s1")
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [first["id"], second["id"]]
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
    leases_model.release_lease(lane)
    asked = said(claimed, "Where does the hold live?")
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
    """A kept-back message the session picks up once its line turn has lapsed is the
    session's: the line fork's later answer writes nothing."""
    asked = said(claimed, "Which wins?")
    listed = basis(claimed, asked["id"], asked["id"])
    lapse(listed["turn"])
    with PageTransaction(claimed) as page:
        [event] = [e for e in page.events if e["id"] == asked["id"]]
        delivery_model.record_pickup(page, [event], session="s1", turn="t1")
    assert kept_back(claimed) == []
    assert forks_model.route(
        "s1",
        listed,
        answer=judged("The fork."),
        failed=None,
    ) == {"outcome": "dropped", "text": "The fork.", "work": "hand_over"}


def test_a_hold_ending_while_the_reply_goes_in_leaves_the_thread_to_the_session(
    claimed, lane, monkeypatch
):
    """The line goes in acting in its line turn, checked under the lock its append
    takes, so the line turn lapsing and the session taking the thread while the line
    is on its way in leaves the thread wholly to the session, which a delivery
    prepared then would otherwise tell to answer it again."""
    asked = said(claimed, "Is the fence inside the append?")
    checked = thread_model.checked_text

    line_turn = basis(claimed, asked["id"])["turn"]

    def lapses_meanwhile(page_dir, text):
        lapse(line_turn)
        with PageTransaction(claimed) as page:
            [event] = [e for e in page.events if e["id"] == asked["id"]]
            delivery_model.record_pickup(page, [event], session="s1", turn="t1")
        return checked(page_dir, text)

    monkeypatch.setattr(thread_model, "checked_text", lapses_meanwhile)
    assert forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=judged("Yes."),
        failed=None,
    ) == {"outcome": "dropped", "text": "Yes.", "work": "hand_over"}
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )


def test_a_line_fork_answering_after_the_lane_went_down_still_routes_its_thread(
    claimed, lane
):
    """The lane only tells admission that a follower will list the line turn; the
    line fork runs in the module, so the follower exiting after listing it leaves the
    line turn holding the thread, and the line fork's answer still posts its line and
    hands the thread over."""
    asked = said(claimed, "Still held after a restart?")
    leases_model.release_lease(lane)
    assert deliverable(claimed) == []
    routed = forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=judged("checking the restart"),
        failed=None,
    )
    assert routed["outcome"] == "hand_over", routed
    assert "line" in routed
    assert deliverable(claimed) == [asked["id"]]


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
    Stopping with a thread kept back ends nothing: the line fork runs in the
    module."""
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
        asked.append(said(claimed, "Is anyone forking?"))
        assert waiting([(heard, generation)], STATED_TIMEOUT), (
            "the message woke nothing"
        )
        return True

    monkeypatch.setattr(file_changes_model, "wait", wait)
    with pytest.raises(Stopped):
        hooks_model.cmd_pages(FOLLOWER)
    assert not forks_model.lane_up("s1")
    listed = [
        json.loads(line)["pages"] for line in capsys.readouterr().out.splitlines()
    ]
    assert listed[0][0]["kept_back"] == []
    assert listed[1][0]["kept_back"] == [
        {
            "page": str(claimed.resolve()),
            "thread": asked[0]["id"],
            "inputs": [asked[0]["id"]],
            "turn": basis(claimed, asked[0]["id"])["turn"],
        }
    ]
    assert nudged == []


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
        assert not forks_model.lane_up("s1"), "the follower took the lane"
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
    assert not forks_model.lane_up("s1")
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
            bool(row.get("lane")),
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
