"""Forked working lines: each state a thread with waiting user messages moves
through (`forks.py`'s table), what Leaf holds from the session meanwhile, and how
the message reads once a fork has posted the agent's working line and handed the
thread over."""

import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest
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
from leaf import delivery as delivery_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import file_changes as file_changes_model
from leaf import forks as forks_model
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


def past_the_take() -> None:
    """Wait for the clock to leave the millisecond session s1's lane was taken in,
    since a message admitted within it stays with the session (`forks.held`)."""
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


def held(page_dir) -> list:
    with PageTransaction(page_dir) as page:
        return [(thread.thread, thread.inputs) for thread in forks_model.held(page)]


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


def test_a_held_message_gets_the_forks_working_line_and_goes_to_the_session(
    claimed, lane
):
    """A message in a thread the session hasn't received is held: not deliverable,
    so neither a hook nor the watch hands it over, while a fork writes the agent's
    working line, and it reads On it from the start. The line goes in as the agent's
    progress without taking the message in hand, and the thread goes to the session
    at once, still owing its answer and still reading On it until that answer."""
    asked = said(claimed, "Why a 2-second poll?")
    assert held(claimed) == [(asked["id"], (asked["id"],))]
    assert deliverable(claimed) == []
    assert forked(claimed) == [asked["id"]]

    question = forks_model.ask("s1", basis(claimed, asked["id"], asked["id"]), [])
    assert question is not None
    assert question["prompt"].startswith(forks_model.OPENING)
    assert "Why a 2-second poll?" in question["prompt"]
    assert "ends where the session last sent it to the model" in question["prompt"]

    handed = forks_model.take(
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
    assert held(claimed) == []
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
    taken = forks_model.take(
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
    """Where the module makes forks that do the work, a thread the line's fork judges
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
    monkeypatch.setenv(state_model.AGENT_VARIABLE, "agent-1")
    ref = answer_ref(claimed, asked["id"])

    progress = thread_model.post_response(ref, "reading pyproject.toml", ephemeral=True)
    assert progress is not None
    assert progress["start"] == {"item": asked["id"], "turn": taken["turn"]}
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
    assert "answered" in clerk_model.queued("s1")[-1]
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
    fork's turn."""
    asked, taken = taken_by_a_fork(claimed, "Why is the cold start slow?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    monkeypatch.setenv(state_model.AGENT_VARIABLE, "agent-1")
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

    [ended] = forks_model.ended(
        "s1", agent="agent-1", turn=None, answer="Opened a to-do.", failed=None
    )
    assert ended["outcome"] == "answer"
    [todo] = reading(claimed)["activity"]["todos"]
    assert (todo["id"], todo["title"], todo["session"], todo["running"]) == (
        reply["id"],
        "Profile the cold start",
        "s1",
        None,
    )


def test_the_forks_leaf_commands_are_marked_to_act_in_its_turn(claimed, lane, capsys):
    """Claude Code's PreToolUse hook names the agent whose command is about to run,
    so before a `leaf` command of an agent running a turn of the session's own, the
    hook hands back the command marked with the agent's id, which is what makes it
    act in that turn; any other agent's command, and the main thread's, run as they
    came."""
    asked, taken = taken_by_a_fork(claimed, "Which Python does the project need?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    command = "cd /tmp && leaf thread reply abc:0:e1 --done --text 'Python 3.12'"

    def before(agent: str | None, tool_use: str) -> str:
        hooks_model.cmd_hook(
            "claude-code",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "prompt_id": "p1",
                "tool_name": "Bash",
                "tool_use_id": tool_use,
                "tool_input": {"command": command, "description": "Answer"},
                **({"agent_id": agent} if agent else {}),
            },
        )
        return capsys.readouterr().out

    output = json.loads(before("agent-1", "u1"))["hookSpecificOutput"]
    assert output == {
        "hookEventName": "PreToolUse",
        "updatedInput": {
            "command": f"export {state_model.AGENT_VARIABLE}=agent-1; {command}",
            "description": "Answer",
        },
    }
    assert before("agent-2", "u2") == ""
    assert before(None, "u3") == ""


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


def test_a_fork_whose_thread_was_taken_over_can_not_answer_it(
    claimed, lane, capsys, monkeypatch
):
    """A takeover revokes the fork's answer: its reply with the answer reference its
    delivery gave it is refused once the main thread holds the message, as a
    reference stops working once another session claims the page."""
    asked, _taken = taken_over(claimed, capsys)
    monkeypatch.setenv(state_model.AGENT_VARIABLE, "agent-1")
    with pytest.raises(delivery_model.ReceiptRefused, match="no longer holds"):
        thread_model.post_response(
            answer_ref(claimed, asked["id"]), "Yes.", asks_back=False
        )


def test_the_watch_wakes_the_idle_session_for_a_thread_its_fork_gave_back(
    claimed, lane, interactive, capsys, monkeypatch
):
    """While a fork holds a thread, the main thread's closed turn owes nothing, so the
    watch that follows it sleeps. As the fork's turn ends with the thread unanswered,
    the main thread owes its answer, and the watch wakes the session for it, though
    the page's log hasn't moved."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    asked, taken = taken_by_a_fork(claimed, "Does the suggest service cache?")
    forks_model.started(
        "s1", basis(claimed, asked["id"], asked["id"]), taken["turn"], "agent-1"
    )
    stop = {"hook_event_name": "Stop", "session_id": "s1", "prompt_id": "p1"}
    context(capsys, "UserPromptSubmit")
    hooks_model.cmd_hook("claude-code", stop)
    assert capsys.readouterr().out == ""
    passed = Event()
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        passed.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)
    woke: list = []
    watch = Thread(
        target=lambda: woke.append(hooks_model.cmd_watch("claude-code", stop)),
        daemon=True,
    )
    watch.start()
    assert passed.wait(STATED_TIMEOUT), f"the watch never read the pages: {woke}"
    assert woke == []

    forks_model.ended(
        "s1",
        agent="agent-1",
        turn=None,
        answer=f"{forks_model.HAND_BACK} the session is changing its startup.",
        failed=None,
    )
    watch.join(STATED_TIMEOUT)
    assert woke and woke[0].startswith(f"{claimed} has an update still owed an answer")


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
    assert held(claimed) == []
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


def test_a_fork_turn_that_ends_unanswered_gives_its_thread_to_the_main_thread(
    claimed, lane
):
    """A fork that gives the thread back, fails to start, or goes unheard for the
    working grace leaves the thread's answer owed by the main thread, as any update
    it received is, with the answer reference the fork's delivery gave it; and the
    main thread hears which fork gave which thread back, and why."""
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
            "outcome": "hand_over",
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
    assert forks_model.take(
        "s1", basis(claimed, failed["id"], failed["id"]), answer=None, failed="aborted"
    ) == {"outcome": "hand_over", "why": "the fork failed: aborted"}
    assert forks_model.take(
        "s1", basis(claimed, blank["id"], blank["id"]), answer=judged(" "), failed=None
    )["why"].startswith("the fork failed: the fork's answer doesn't fit its schema")
    assert held(claimed) == []
    assert deliverable(claimed) == [failed["id"], blank["id"]]
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )
    assert forked(claimed) == []


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
    assert held(claimed) == [(other["id"], (other["id"],))]
    assert forked(claimed) == [other["id"]]
    # No page file records the lane going down, so the presence reading names the
    # lane itself, and a tab re-reads once its cache interval passes.
    monkeypatch.setattr(presence_model, "PRESENCE_CACHE_S", 0)
    before = presence_model.presence_reading(claimed, "files")
    leases_model.release_lease(lane)
    assert held(claimed) == []
    assert deliverable(claimed) == [asked["id"], other["id"]]
    assert forked(claimed) == []
    assert presence_model.presence_reading(claimed, "files") != before


def test_without_a_lane_nothing_is_held(claimed):
    """A session without Leaf's hooks module, or any other harness, delivers as
    before."""
    asked = said(claimed, "Anyone there?")
    assert held(claimed) == []
    assert deliverable(claimed) == [asked["id"]]


def test_a_message_while_held_starts_a_fork_for_both_and_drops_the_first_answer(
    claimed, lane
):
    """A second message in a held thread keeps it held, now with both, and the fork
    asked about the first alone writes nothing: the thread's newest message carries
    its one answer."""
    first = said(claimed, "Why 30 s?")
    second = said(claimed, "Or rather, why not 20?", parent=first["id"])
    assert held(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert forks_model.ask("s1", basis(claimed, first["id"], first["id"]), []) is None

    assert forks_model.take(
        "s1",
        basis(claimed, first["id"], first["id"]),
        answer=judged("Thirty covers a cold cache."),
        failed=None,
    ) == {
        "outcome": "dropped",
        "text": "Thirty covers a cold cache.",
        "work": "hand_over",
    }
    assert held(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert not any(
        event["kind"] == "reply" and event["author"] == "agent"
        for event in events_model.read_events(claimed)
    )


def test_a_thread_the_session_owes_stays_with_it_and_a_follow_up_is_forked(
    claimed, lane, capsys
):
    """Once the session has received a thread's message, a message after it in that
    thread goes to the session too; once the agent has answered, the user's
    follow-up is held again, and its fork sees the earlier exchange."""
    asked = said(claimed, "Where does the hold live?")
    leases_model.release_lease(lane)
    assert "Where does the hold live?" in context(capsys, "UserPromptSubmit")
    lane = take_lane()
    more = said(claimed, "And who reads it?", parent=asked["id"])
    assert held(claimed) == []
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
    assert held(claimed) == [(asked["id"], (follow_up["id"],))]
    question = forks_model.ask("s1", basis(claimed, asked["id"], follow_up["id"]), [])
    assert question is not None
    assert "In `delivery.deliverable`." in question["prompt"]
    leases_model.release_lease(lane)


def test_the_session_taking_the_message_first_leaves_the_fork_nothing_to_write(
    claimed, lane, capsys
):
    """A held message the session picks up anyway, as once the bound has passed, is
    the session's: the fork's later answer writes nothing."""
    asked = said(claimed, "Which wins?")
    with PageTransaction(claimed) as page:
        [event] = [e for e in page.events if e["id"] == asked["id"]]
        delivery_model.record_pickup(page, [event], session="s1", turn="t1")
    assert held(claimed) == []
    assert forks_model.take(
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
    assert forks_model.take(
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
        assert held(claimed) == []
        assert forks_model.take(
            "s1",
            basis(claimed, asked["id"], asked["id"]),
            answer=judged("Yes."),
            failed=None,
        ) == {"outcome": "dropped", "text": "Yes.", "work": "hand_over"}
    finally:
        leases_model.release_lease(again)


def test_a_fork_the_page_has_since_left_writes_nothing_on_it(claimed, lane):
    """The hold is the claimant's: a fork of another session's conversation, as one
    returning after the page passed to a new session, neither hands the thread over
    nor answers it."""
    asked = said(claimed, "Who holds this?")
    assert (
        forks_model.take(
            "s2",
            basis(claimed, asked["id"], asked["id"]),
            answer=judged("checking who holds it"),
            failed=None,
        )["outcome"]
        == "dropped"
    )
    assert held(claimed) == [(asked["id"], (asked["id"],))]
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


def test_the_pages_follower_holds_the_lane_and_lists_held_threads(
    claimed, monkeypatch, capsys
):
    """Asked for forks, the follower is the session's lane while it runs and lists
    each page's held threads for the module. It waits on the page's subscription,
    so a message wakes it as it is admitted rather than at the next presence read.
    Stopping with a thread held, it nudges what the hold leaves, as a watch giving
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
        hooks_model.cmd_pages({"session_id": "s1", "forks": True})
    assert forks_model.lane_since("s1") is None
    listed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert listed[0][0]["forks"] == []
    assert listed[1][0]["forks"] == [
        {
            "page": str(claimed.resolve()),
            "thread": asked[0]["id"],
            "inputs": [asked[0]["id"]],
        }
    ]
    assert nudged == ["s1"]


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
        hooks_model.cmd_pages({"session_id": "s1", "forks": True})
    assert ended.value.code == os.EX_TEMPFAIL
    assert forks_model.lane_since("s1") is None
    [listed] = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert listed[0]["forks"] == []


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
        hooks_model.cmd_pages({"session_id": "s1", "forks": True})


def test_the_follower_forgets_the_bound_of_a_page_that_is_gone(claimed, monkeypatch):
    """A page that is gone holds nothing, so the follower keeps no bound of its to
    wake at: one kept past its hold would end every wait at once until the next
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
        hooks_model.cmd_pages({"session_id": "s1", "forks": True})
    assert timeouts[-1] > 0, "the follower kept a gone page's bound"


def test_the_follower_keeps_the_bound_of_a_page_it_does_not_list(
    claimed, monkeypatch, capsys
):
    """A page whose server isn't running goes unlisted, yet the follower still hands
    its held threads to the session at their bound. That hand-over nudges for itself,
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
        hooks_model.cmd_pages({"session_id": "s1", "forks": True})
    assert capsys.readouterr().out.splitlines() == ["[]"]
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
        assert held(claimed) == []
        assert deliverable(claimed) == [asked[0]["id"]]
        assert (
            forks_model.take(
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
    whether to nudge the session. It cannot be deliverable now and held later."""
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
            assert held(claimed) == [(asked["id"], (asked["id"],))]
            assert deliverable(claimed) == [before["id"]]
        finally:
            leases_model.release_lease(lane)


def test_admission_and_each_fork_say_in_the_diagnostics_why_a_message_was_held(
    claimed, monkeypatch
):
    """Whether admission held each thread message for a fork, and where it didn't,
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
        (row["type"], row.get("event"), row.get("held"), row.get("lane") is not None)
        if row["type"] == "fork_hold"
        else (row["type"], row["inputs"], row["running"])
        for row in read_interactions(claimed, types=("fork_hold", "fork_asked"))
    ]
    assert notes == [
        ("fork_hold", early, False, False),
        ("fork_hold", later, False, True),
        ("fork_hold", asked, True, True),
        ("fork_asked", [asked], ["Bash"]),
    ]
