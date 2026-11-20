"""The line fork of a Claude Code session: each state a thread with waiting user
messages moves through (`forks.py`'s table), what Leaf keeps back from the session
meanwhile, and how the message reads once the line fork has posted the agent's working
line and handed the thread over."""

import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Condition, Thread
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    append_command,
    inlined,
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
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import session_runtime as session_runtime_model
from leaf import state as state_model
from leaf import thread as thread_model
from leaf import todos as todos_model
from leaf.events import build_threads
from leaf.interaction_log import read_interactions
from leaf.registry import kernel as kernel_model
from leaf.served_state.context import read_page
from leaf.served_state.reading import outside_inputs
from leaf.service import PageTransaction
from leaf.state import session_file

# What Leaf's Claude Code hooks module gives the pages follower of session s1
# (`hooks.cmd_pages`).
FOLLOWER = {"session_id": "s1"}


def take_lane():
    """Take session s1's forks lane, as its pages follower does."""
    return forks_model.take_lane("s1")


@contextmanager
def lane_held():
    """Session s1's forks lane, held through the block as its pages follower holds
    it."""
    held = take_lane()
    try:
        yield held
    finally:
        leases_model.release_lease(held)


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


def line_answer(line: str) -> str:
    """A line fork's answer: the agent's working line."""
    return json.dumps({"line": line})


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
        answer=line_answer(" checking why the poll is 2 s\n"),
        failed=None,
    )
    assert handed["outcome"] == "hand_over"
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


def test_a_line_hands_the_thread_to_the_session(
    claimed, lane, interactive, capsys, monkeypatch
):
    """Leaf posts the line fork's line, closes the line turn and nudges a session no
    watch follows, once: the page's server, waking at its next transition, sends
    nothing more. The session's next delivery hands it the message with its answer
    reference, telling it nothing more, since the session decides who does the
    work."""
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page: nudged.append(page) or True,
    )
    serving(claimed, 1)
    server = server_rows_model.RowPublisher(claimed, "fixture-server")
    state_model.close_session_turn("s1")
    asked = said(claimed, "Which Python does the project need?")
    listed = basis(claimed, asked["id"], asked["id"])
    server.refresh()
    routed = forks_model.route(
        "s1", listed, answer=line_answer("checking the Python version"), failed=None
    )
    assert routed["outcome"] == "hand_over", routed
    [line] = [
        event for event in events_model.read_events(claimed) if event["kind"] == "reply"
    ]
    assert (line["id"], line["text"], line["parent"]) == (
        routed["line"],
        "checking the Python version",
        asked["id"],
    )
    assert listed["turn"] not in state_model.open_agent_turns("s1")
    assert nudged == [claimed.resolve()]
    grace_passes(server, listed["turn"])
    server.refresh()
    assert nudged == [claimed.resolve()]
    assert clerk_model.queued("s1") == []

    handed = context(capsys, "UserPromptSubmit")
    [batch] = inlined(handed)["batches"]
    [event] = batch["events"]
    assert event["id"] == asked["id"]
    assert event["answer"]["ref"] == answer_ref(claimed, asked["id"])


def long_thread(page_dir) -> tuple[dict, list[dict]]:
    """A thread of twelve answered messages, opened before the session's lane came
    up, so none was kept back: its opening comment, and the messages after it."""
    state_model.close_session_turn("s1")
    opened = said(page_dir, "Which TTL should the quote cache use?")
    later = [thread_model.post_reply(page_dir, {"responds": opened["id"]}, "Ten.")]
    for n in range(1, 6):
        asked = said(page_dir, f"Follow-up {n}?", parent=opened["id"])
        later += [
            asked,
            thread_model.post_reply(
                page_dir, {"responds": asked["id"]}, f"Answer {n}."
            ),
        ]
    return opened, later


def asked_in(page_dir, opened: dict, text: str) -> tuple[dict, dict]:
    """The user's newest message in the thread `opened` began, kept back while the
    lane is up, and what Leaf asks the module to fork for it (`forks.ask`)."""
    newest = said(page_dir, text, parent=opened["id"])
    question = forks_model.ask("s1", basis(page_dir, opened["id"], newest["id"]), [])
    assert question is not None
    return newest, question


def test_a_line_fork_reads_the_whole_of_a_long_thread(claimed):
    """A delivery to the session shows a long thread's opening and latest messages and
    leaves the middle to `leaf page state`, which a line fork can't run, so the fork's
    prompt carries every message of the thread."""
    opened, _ = long_thread(claimed)
    with lane_held():
        newest, question = asked_in(claimed, opened, "And the newest?")
    with PageTransaction(claimed) as page:
        [bounded] = delivery_model.batch_data(claimed, page, [newest])["threads"]
    assert bounded["elided"]["messages"] == 4
    assert "Follow-up 1?" not in json.dumps(bounded)
    assert "Follow-up 1?" in question["prompt"]
    assert '"messages": 0' in question["prompt"]


def summary_beside(page_dir) -> tuple[dict, list[dict], dict, dict]:
    """A long thread, the user's newest message in it kept back, and the summary fork
    Leaf asks for beside its line fork: the thread's opening, its later messages, the
    newest message, and the summary fork's `{"prompt", "basis"}`."""
    opened, later = long_thread(page_dir)
    with lane_held():
        newest, question = asked_in(page_dir, opened, "And the newest?")
    [summary] = question["beside"]
    return opened, later, newest, summary


def summarized(summary: dict, answer: dict) -> dict:
    """What Leaf did with the summary fork's `answer`."""
    outcome = forks_model.step(
        "s1",
        {
            "done": "summary",
            "do": "fork",
            "basis": {"kind": "beside", **summary["basis"]},
            "answer": json.dumps(answer),
        },
    )
    assert outcome is not None
    assert outcome.pop("log").startswith("the summary fork for thread ")
    return outcome


def summaries_written(page_dir) -> list[tuple]:
    """Each summary the page's log holds, as its range and text."""
    with PageTransaction(page_dir) as page:
        return [
            (event["from"], event["through"], event["text"])
            for event in page.events
            if event["kind"] == "summary"
        ]


def test_a_long_thread_is_summarized_by_a_fork_beside_its_line_fork(claimed):
    """A message Leaf keeps back in a thread long enough to suggest a range to
    summarize gets a second fork beside the line fork, offered that range and asked to
    choose its own and summarize it from the whole thread by the agent's guidance. Its
    answer goes in as the agent's summary, which the agent hears of as its own. That
    message's delivery leaves the suggestion out, since the fork has it, while the
    delivery of one Leaf didn't keep back still carries it."""
    _, later, newest, summary = summary_beside(claimed)
    with PageTransaction(claimed) as page:
        [forked] = delivery_model.batch_data(claimed, page, [newest])["threads"]
        [unforked] = delivery_model.batch_data(claimed, page, [later[-2]])["threads"]
    hint = unforked["summary_hint"]
    assert "summary_hint" not in forked
    assert (summary["basis"]["from"], summary["basis"]["through"]) == (
        hint["from"],
        hint["through"],
    )
    assert summary["prompt"].startswith("<leaf-summary-fork>")
    assert "Follow-up 1?" in summary["prompt"]
    assert "> Fold what compresses most" in summary["prompt"]
    assert "> A summary is what the user reads" in summary["prompt"]

    outcome = summarized(summary, {**hint, "text": "The TTL went to ten, then five."})
    assert outcome["outcome"] == "summarized"
    assert summaries_written(claimed) == [
        (hint["from"], hint["through"], "The TTL went to ten, then five.")
    ]
    with PageTransaction(claimed) as page:
        [written] = [event for event in page.events if event["kind"] == "summary"]
    assert (written["id"], written["author"]) == (outcome["summary"], "agent")
    [told] = clerk_model.queued("s1")
    assert outcome["summary"] in told and "> The TTL went to ten, then five." in told
    [noted] = read_interactions(claimed, types=("summary_fork",))
    assert noted["outcome"] == "summarized"


@pytest.mark.parametrize("withdrawn", [False, True])
def test_the_fork_folds_the_range_it_chose(claimed, withdrawn):
    """The fork chooses what to fold, with Leaf's range as a suggestion: here it keeps
    the opening message in full and folds past the suggestion's end, up to the
    agent's last answer, and Leaf writes that range. It does so though the
    suggestion's last message no longer stands, as when the user took it back."""
    opened, later, _, summary = summary_beside(claimed)
    basis_ = summary["basis"]
    assert (basis_["from"], basis_["through"]) == (opened["id"], later[-2]["id"])
    if withdrawn:
        summary = {**summary, "basis": {**basis_, "through": "taken-back"}}
    chosen = {"from": later[0]["id"], "through": later[-1]["id"]}
    outcome = summarized(summary, {**chosen, "text": "The TTL went to ten."})
    assert outcome["outcome"] == "summarized"
    assert summaries_written(claimed) == [
        (chosen["from"], chosen["through"], "The TTL went to ten.")
    ]
    [noted] = read_interactions(claimed, types=("summary_fork",))
    assert noted["suggested"] == {
        "from": basis_["from"],
        "through": summary["basis"]["through"],
    }
    assert (noted["from"], noted["through"]) == (chosen["from"], chosen["through"])


def test_the_fork_may_fold_nothing(claimed):
    """Where nothing compresses without losing wording the current exchange turns on,
    the fork folds nothing: Leaf writes no summary and hands the agent nothing."""
    *_, summary = summary_beside(claimed)
    assert summarized(summary, {"fold": False}) == {"outcome": "declined"}
    assert summaries_written(claimed) == []
    assert clerk_model.queued("s1") == []


@pytest.mark.parametrize("shape", ["the newest message", "backwards"])
def test_a_range_leaf_cant_take_hands_the_suggestion_to_the_agent(claimed, shape):
    """Leaf takes the fork's range only where it runs forward over the thread's spoken
    messages and ends before the user's newest messages, which the main session
    answers. Otherwise it writes nothing and hands the agent the suggested range."""
    opened, later, newest, summary = summary_beside(claimed)
    chosen = {
        "the newest message": {"from": opened["id"], "through": newest["id"]},
        "backwards": {"from": later[4]["id"], "through": later[2]["id"]},
    }[shape]
    outcome = summarized(summary, {**chosen, "text": "The fork's."})
    assert outcome["outcome"] == "failed"
    assert "its range" in outcome["why"]
    assert summaries_written(claimed) == []
    [handed] = clerk_model.queued("s1")
    basis_ = summary["basis"]
    assert f"`summary_hint` of {basis_['from']} through {basis_['through']}." in handed


def test_a_failed_summary_fork_hands_the_range_to_the_agent(claimed):
    """An answer Leaf can't take writes nothing, and the agent is told the range to
    summarize, so the thread's summary still has an owner."""
    *_, summary = summary_beside(claimed)
    outcome = summarized(summary, {"summary": "Not the answer's form."})
    assert outcome["outcome"] == "failed"
    [handed] = clerk_model.queued("s1")
    basis_ = summary["basis"]
    assert f"`summary_hint` of {basis_['from']} through {basis_['through']}." in handed
    assert summaries_written(claimed) == []


@pytest.mark.parametrize("meanwhile", ["summary", "edit"])
def test_a_change_in_its_range_meanwhile_drops_the_forks_summary(claimed, meanwhile):
    """The fork summarizes the range as it read when Leaf asked, so Leaf writes nothing
    where that summary would no longer be in force by the rules that cancel any
    summary: one written in the thread since replaces it, and the user's edit of a
    message in its range cancels it."""
    _, later, _, summary = summary_beside(claimed)
    if meanwhile == "summary":
        basis_ = summary["basis"]
        thread_model.cmd_summarize(
            claimed, basis_["from"], basis_["through"], "The agent's."
        )
    else:
        append_command(
            claimed,
            {
                "kind": "edit",
                "author": "user",
                "message": later[1]["id"],
                "text": "Follow-up 1, put another way?",
            },
        )
    answer = {
        "from": summary["basis"]["from"],
        "through": summary["basis"]["through"],
        "text": "The fork's.",
    }
    assert summarized(summary, answer) == {"outcome": "dropped"}
    assert "The fork's." not in [text for *_, text in summaries_written(claimed)]
    assert clerk_model.queued("s1") == []


def reading(page_dir) -> dict:
    """The page's presence and activity, as the hooks read them."""
    work = read_page(page_dir, events_model.read_events(page_dir)).work
    return {**work.presence, "activity": work.activity}


def answer_ref(page_dir, input_id: str) -> str:
    """The answer reference the newest pickup carrying one gave `input_id`."""
    return next(
        event["refs"][input_id]["ref"]
        for event in reversed(events_model.read_events(page_dir))
        if event["kind"] == "pickup" and input_id in event.get("refs", {})
    )


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


def test_page_state_names_who_has_each_answer_and_thread(claimed, lane):
    """`leaf page state` names who holds each thread, the line fork while Leaf keeps
    it back and otherwise the main thread, and on each answer the agent owes, who
    owes it now. So a main thread recovering what it owes there, as after a
    compaction, can tell a message a line fork is judging from its own, and a
    message whose line turn lapsed is its own to answer."""
    asked = said(claimed, "Does the suggest service cache?")
    main = {"kind": "main"}
    line = {"kind": "line"}
    assert holders(claimed) == ({asked["id"]: line}, {asked["id"]: line})
    opened_long_ago(basis(claimed, asked["id"])["turn"], activity_model.STARTING_GRACE)
    assert holders(claimed) == ({asked["id"]: main}, {asked["id"]: main})


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
        answer=line_answer("on it"),
        failed=None,
    )
    assert first["id"] in context(capsys, "UserPromptSubmit")
    return first


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
        answer=line_answer("checking the versions"),
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
        answer=line_answer("checking the Python version"),
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
    session with a line turn open and its lane up reads the page's log alone."""
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


# What a command acting as the main session hears beside its result where a line
# turn holds its thread (`fork-holds-thread`).
LINE_HOLDS = "a line fork holds this thread"


def test_the_main_threads_answer_to_a_kept_back_message_takes_its_thread(
    claimed, lane, capsys
):
    """The main thread is sovereign: its answer to a message a line turn holds goes
    in, saying beside it that a line fork holds the thread, and takes the thread at
    once, since the answer names the turn that posted it. So the line fork's line,
    coming after it, writes nothing there."""
    asked = said(claimed, "Does the suggest service cache?")
    listed = basis(claimed, asked["id"], asked["id"])
    capsys.readouterr()
    answer = thread_model.post_reply(
        claimed, {"responds": asked["id"]}, "Yes, for an hour."
    )
    assert LINE_HOLDS in capsys.readouterr().err
    claim = service_model.page_claim(claimed)
    assert answer is not None and claim is not None
    assert answer["turn"] == claim["turn"]
    assert kept_back(claimed) == []
    routed = forks_model.route(
        "s1", listed, answer=line_answer("checking the cache"), failed=None
    )
    assert "line" not in routed, routed
    assert [
        event["text"]
        for event in events_model.read_events(claimed)
        if event["kind"] == "reply"
    ] == ["Yes, for an hour."]


def test_a_message_beside_a_kept_back_one_leaves_the_line_turn_holding_the_thread(
    claimed, lane, capsys
):
    """Only an answer, which responds to a message, takes a thread. A message of the
    main session's own in a thread a line turn holds responds to nothing, so the line
    turn still holds the thread, which the message says beside its result."""
    asked = said(claimed, "Which Python does it need?")
    capsys.readouterr()
    thread_model.post_reply(claimed, {"parent": asked["id"]}, "Reading pyproject.toml.")
    assert LINE_HOLDS in capsys.readouterr().err
    assert kept_back(claimed) == [(asked["id"], (asked["id"],))]


def test_a_command_from_outside_the_session_hears_of_the_line_fork_holding_the_thread(
    claimed, lane, capsys, monkeypatch
):
    """A command acting as the main session hears of the line fork that holds its
    thread whoever runs it, a terminal outside the session included, whose commands
    name no session."""
    asked = said(claimed, "Does the suggest service cache?")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    capsys.readouterr()
    assert todos_model.cmd_start(claimed, asked["id"], "checking the cache")
    beside = capsys.readouterr().err
    assert LINE_HOLDS in beside, beside


def test_a_start_on_a_to_do_in_a_kept_back_thread_hears_of_the_line_fork(
    claimed, lane, capsys
):
    """A to-do attached to a thread stands in that thread, so a start on it in the
    main session's name, as on one of the thread's messages, hears of the line fork
    that holds the thread."""
    asked = said(claimed, "Does the suggest service cache?")
    todo = todos_model.cmd_create(claimed, asked["id"], "Check the cache config")
    capsys.readouterr()
    assert todos_model.cmd_start(claimed, todo["id"], "checking the config")
    beside = capsys.readouterr().err
    assert LINE_HOLDS in beside, beside


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
    assert LINE_HOLDS in beside, beside
    handed = forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=line_answer("reading the poll code"),
        failed=None,
    )
    assert handed["outcome"] == "hand_over"
    assert LINE_HOLDS not in capsys.readouterr().err


def test_a_line_turn_ends_with_its_session(claimed, lane):
    """A line fork runs inside its session's harness instance, so its line turn ends
    with the session: `leaf page state` says the main thread holds the thread the
    line turn kept back, and the message, which its `held` pickup never took in, is
    input for whoever holds the page next, as the fold's and the page's readings
    agree."""
    asked = said(claimed, "Does the suggest service cache?")
    turn = basis(claimed, asked["id"])["turn"]
    state_model.end_session("s1")
    assert turn not in state_model.open_agent_turns("s1")
    _owed, threads = holders(claimed)
    assert threads[asked["id"]] == {"kind": "main"}
    assert deliverable(claimed) == [asked["id"]]
    with PageTransaction(claimed) as page:
        assert not forks_model.page_holding(page).live
        unfolded = delivery_model.deliverable(page, received=False)
    assert [event["id"] for event in unfolded] == [asked["id"]]


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


def test_the_watch_wakes_the_idle_session_for_a_thread_its_line_fork_handed_over(
    claimed, lane, interactive, capsys, monkeypatch
):
    """While a line turn holds a thread, the main thread's closed turn owes nothing,
    so the watch that follows it sleeps through the user's message. As the line turn
    ends, here by a failed line fork, which writes nothing in the page's log, the
    message is the main thread's input: the watch wakes the session for it, and the
    woken turn's prompt carries the message."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    context(capsys, "UserPromptSubmit")
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "prompt_id": "p1"},
    )
    assert capsys.readouterr().out == ""
    watching = Watching(monkeypatch)
    asked = said(claimed, "Does the suggest service cache?")
    watching.settle()
    assert watching.woke == []

    events = events_model.read_events(claimed)
    forks_model.route(
        "s1", basis(claimed, asked["id"], asked["id"]), answer=None, failed="aborted"
    )
    assert events_model.read_events(claimed) == events
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


def pointer_in(text: str) -> str | None:
    """The delivery a hook's context points at, if it points at one."""
    return next(iter(re.findall(r'<leaf-delivery id="([0-9a-f]+)"', text)), None)


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
        answer=line_answer("reading the config"),
        failed=None,
    )
    assert handed["outcome"] == "hand_over", handed
    pointer = pointer_in(context(capsys, "UserPromptSubmit"))
    assert pointer is not None
    acked = CliRunner().invoke(cli_model.cli, ["delivery", "ack", pointer])
    assert acked.exit_code == 0, acked.output
    assert "earlier turn" not in acked.output + capsys.readouterr().err


def test_a_page_reads_only_the_line_turns_it_needs(claimed, lane):
    """What a page's reading carries of its session's line turns is the turns still
    running, the only ones that may hold a thread: neither a closed turn, its own or
    another page's, nor one that lapsed, as one whose step never reached the page does.
    A turn of an earlier generation of the session leaves the record as the next
    opens."""
    asked = said(claimed, "Which Python does it need?")
    kept = basis(claimed, asked["id"])["turn"]
    elsewhere = state_model.open_agent_turn("s1")
    lost = state_model.open_agent_turn("s1")
    assert elsewhere is not None and lost is not None
    state_model.close_agent_turns("s1", turn=elsewhere)
    opened_long_ago(lost, activity_model.STARTING_GRACE)
    assert {kept, elsewhere, lost} <= set(state_model.agent_turns("s1"))

    def served() -> set[str]:
        return set(
            presence_model.presence(claimed, events_model.read_events(claimed))[
                "agent_turns"
            ]
        )

    assert served() == {kept}
    forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=line_answer("checking"),
        failed=None,
    )
    assert kept not in state_model.open_agent_turns("s1")
    assert served() == set()

    turns = state_model.agent_turns("s1")
    turns["earlier"] = {**turns[kept], "closed": None, "generation": "an earlier one"}
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )
    assert state_model.open_agent_turn("s1") is not None
    assert "earlier" not in state_model.agent_turns("s1")


def opened_long_ago(turn: str, by: timedelta) -> None:
    """Move the opening of the session's line turn `turn` back by `by`."""
    turns = state_model.agent_turns("s1")
    opened = datetime.fromisoformat(turns[turn]["opened"]) - by
    turns[turn]["opened"] = opened.isoformat()
    state_model.AGENT_TURNS.write(
        session_file("s1", state_model.AGENT_TURNS.kind), {"turns": turns}
    )


def grace_passes(server, turn: str) -> None:
    """The line turn `turn`'s grace passes, for its stamps and for the page's server
    `server`, which wakes at the moment its last row named (`server_rows`)."""
    opened_long_ago(turn, activity_model.STARTING_GRACE)
    server.transition -= activity_model.STARTING_GRACE.total_seconds()


def test_a_line_turn_that_has_ended_holds_nothing(claimed, lane):
    """A line turn that has ended keeps nothing: right after its line fork hands the
    thread over, `leaf page state` says the main thread holds the thread and owes
    its answer, though the session's record still holds the turn."""
    asked = said(claimed, "Which Python?")
    line_turn = basis(claimed, asked["id"])["turn"]
    assert holders(claimed)[1][asked["id"]] == {"kind": "line"}
    assert (
        forks_model.route(
            "s1",
            basis(claimed, asked["id"], asked["id"]),
            answer=line_answer("checking"),
            failed=None,
        )["outcome"]
        == "hand_over"
    )
    assert line_turn in state_model.agent_turns("s1")
    main = {"kind": "main"}
    owed, threads = holders(claimed)
    assert (owed[asked["id"]], threads[asked["id"]]) == (main, main)


def test_a_line_turn_that_ended_leaves_the_record_and_its_thread_reads_as_before(
    claimed, lane, capsys
):
    """Opening a turn drops the line turns that have closed or lapsed, so the
    session's record holds the line turns still running rather than one for every
    message Leaf kept back. A thread such a line turn held reads as the main thread's as it
    did while the entry stood: its message is the main thread's input, `leaf page
    state` says the main thread owes its answer, and the main thread's prompt takes
    it in."""
    handed = said(claimed, "Which Python?")
    assert (
        forks_model.route(
            "s1",
            basis(claimed, handed["id"], handed["id"]),
            answer=line_answer("checking"),
            failed=None,
        )["outcome"]
        == "hand_over"
    )
    lapsed = said(claimed, "Which uv?")
    opened_long_ago(basis(claimed, lapsed["id"])["turn"], activity_model.STARTING_GRACE)
    ended = {handed["id"], lapsed["id"]}
    main = {"kind": "main"}
    assert deliverable(claimed) == [handed["id"], lapsed["id"]]
    assert {
        i: h for i, h in holders(claimed)[0].items() if i in ended
    } == dict.fromkeys(ended, main)

    third = said(claimed, "Which Node?")
    assert set(state_model.agent_turns("s1")) == {basis(claimed, third["id"])["turn"]}
    assert deliverable(claimed) == [handed["id"], lapsed["id"]]
    assert {
        i: h for i, h in holders(claimed)[0].items() if i in ended
    } == dict.fromkeys(ended, main)
    taken = context(capsys, "UserPromptSubmit")
    assert handed["text"] in taken and lapsed["text"] in taken
    assert third["text"] not in taken
    assert deliverable(claimed) == []


def test_the_reading_changes_when_a_line_turn_lapses(claimed, lane):
    """The served reading says it next changes when a running line turn lapses, a
    `STARTING_GRACE` after its opening, when the message it holds becomes the main
    thread's."""
    asked = said(claimed, "Which Python does the project need?")
    turn = basis(claimed, asked["id"])["turn"]
    opened = datetime.fromisoformat(state_model.agent_turns("s1")[turn]["opened"])
    due = datetime.fromisoformat(reading(claimed)["activity"]["next_transition_at"])
    assert due - opened == activity_model.STARTING_GRACE


def test_a_failed_fork_gives_the_thread_to_the_session_bare(claimed, lane):
    """A fork that failed, or whose answer isn't the line Leaf asked for, hands the
    thread over with no line, and the message reads as its delivery stands."""
    failed = said(claimed, "And the lane?")
    blank = said(claimed, "What does the follower print?")
    assert forks_model.route(
        "s1", basis(claimed, failed["id"], failed["id"]), answer=None, failed="aborted"
    ) == {"outcome": "hand_over", "why": "the fork failed: aborted"}
    assert forks_model.route(
        "s1",
        basis(claimed, blank["id"], blank["id"]),
        answer=line_answer(" "),
        failed=None,
    )["why"].startswith("the fork failed: the fork's answer doesn't fit its schema")
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [failed["id"], blank["id"]]
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )
    assert forked(claimed) == []


def test_a_hold_ends_as_its_line_turn_lapses(claimed, lane):
    """However the line fork fares, its turn lapses a `STARTING_GRACE` after it
    opened, since nothing renews a line turn, and the message is the main thread's."""
    asked = said(claimed, "Is the bound from the newest message?")
    assert kept_back(claimed) == [(asked["id"], (asked["id"],))]
    assert deliverable(claimed) == []
    opened_long_ago(basis(claimed, asked["id"])["turn"], activity_model.STARTING_GRACE)
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"]]
    assert forked(claimed) == []


def test_without_a_lane_nothing_is_kept_back(claimed):
    """A session without Leaf's hooks module, or any other harness, delivers as
    before."""
    asked = said(claimed, "Anyone there?")
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"]]


def test_a_message_while_kept_back_gives_a_new_line_fork_both(claimed, lane):
    """A second message while the line fork writes about the first, as a quick
    correction, closes that line turn and opens a new one holding both, which the
    follower lists, so the module asks a new line fork about both, and the page's
    diagnostics say the turn it replaced held the thread. The first line fork's
    answer, about the first alone, drops; the new one's line goes in, and it hands
    both to the session."""
    first = said(claimed, "Why 30 s?")
    earlier = basis(claimed, first["id"], first["id"])
    second = said(claimed, "Or rather, why not 20?", parent=first["id"])
    later = basis(claimed, first["id"], first["id"], second["id"])
    assert later["turn"] != earlier["turn"]
    assert earlier["turn"] not in state_model.open_agent_turns("s1")
    assert kept_back(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert deliverable(claimed) == []
    [note] = [
        row
        for row in read_interactions(claimed, types=("fork_admission",))
        if row["event"] == second["id"]
    ]
    assert (note["kept_back"], note["held_by"]) == (True, earlier["turn"])

    assert (
        forks_model.route(
            "s1",
            earlier,
            answer=line_answer("checking why 30 s"),
            failed=None,
        )["outcome"]
        == "dropped"
    )
    question = forks_model.ask("s1", later, [])
    assert question is not None
    assert "Why 30 s?" in question["prompt"] and "why not 20?" in question["prompt"]
    taken = forks_model.route(
        "s1",
        later,
        answer=line_answer("weighing 20 s against 30 s"),
        failed=None,
    )
    assert taken["outcome"] == "hand_over", taken
    lines = [
        event
        for event in events_model.read_events(claimed)
        if event["kind"] == "reply" and event["author"] == "agent"
    ]
    assert [line["text"] for line in lines] == ["weighing 20 s against 30 s"]
    assert deliverable(claimed) == [first["id"], second["id"]]


def test_a_rewrite_while_kept_back_gives_a_new_line_fork_the_new_words(claimed, lane):
    """The user's rewrite of their message while the line fork writes about it joins
    the thread's waiting turns as a further message does, though it is no message:
    it replaces the line turn, the new line fork is asked with the rewritten words,
    and its line hands the thread over, while the first fork's answer drops."""
    first = said(claimed, "Why 30 s?")
    earlier = basis(claimed, first["id"], first["id"])
    edit = append_carried_log_record(
        claimed,
        {"kind": "edit", "author": "user", "message": first["id"], "text": "Why 40 s?"},
    )
    with PageTransaction(claimed) as page:
        assert forks_model.kept_from_main_at_admission(page, edit)
    [(thread, inputs)] = kept_back(claimed)
    later = basis(claimed, thread, *inputs)
    assert later["turn"] != earlier["turn"]
    assert earlier["turn"] not in state_model.open_agent_turns("s1")
    assert deliverable(claimed) == []

    stale = forks_model.route(
        "s1", earlier, answer=line_answer("checking 30 s"), failed=None
    )
    assert stale["outcome"] == "dropped"
    question = forks_model.ask("s1", later, [])
    assert question is not None and "Why 40 s?" in question["prompt"]
    taken = forks_model.route(
        "s1",
        later,
        answer=line_answer("checking 40 s"),
        failed=None,
    )
    assert taken["outcome"] == "hand_over", taken
    assert edit["id"] in deliverable(claimed)


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


def test_a_lapsing_line_turn_wakes_the_session_and_its_late_answer_writes_nothing(
    claimed, lane, interactive, monkeypatch
):
    """A message whose line turn lapsed is the main thread's, however its line fork
    fares. Nothing writes as a line turn lapses, so the page's server, waking at the
    moment its fold names, nudges the session for the message where no watch follows
    it, as once the watch its Stop hook started has failed. The nudge needs no answer
    from the line fork, and its late answer then posts no line, takes nothing and
    wakes no one again, though the lapsed turn was never closed."""
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page: nudged.append(page) or True,
    )
    serving(claimed, 1)
    server = server_rows_model.RowPublisher(claimed, "fixture-server")
    state_model.close_session_turn("s1")
    asked = said(claimed, "Which wins?")
    listed = basis(claimed, asked["id"], asked["id"])
    server.refresh()
    assert nudged == []
    grace_passes(server, listed["turn"])
    assert listed["turn"] in state_model.open_agent_turns("s1")
    assert kept_back(claimed) == []
    assert deliverable(claimed) == [asked["id"]]
    server.refresh()
    assert nudged == [claimed.resolve()]
    assert forks_model.route(
        "s1",
        listed,
        answer=line_answer("The fork."),
        failed=None,
    ) == {
        "outcome": "dropped",
        "why": "its line turn no longer runs",
        "text": "The fork.",
    }
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )
    assert deliverable(claimed) == [asked["id"]]
    assert clerk_model.queued("s1") == []
    assert nudged == [claimed.resolve()]


def test_a_line_fork_step_repeated_after_its_hand_over_changes_nothing(claimed, lane):
    """A line fork's answer closes the line turn as it hands the thread over, and each
    step of a line fork acts only while its line turn runs. So a step a module
    reloaded mid-fork repeats for the same thread, its question or a second answer,
    posts no second line, and the thread stays the main thread's."""
    asked = said(claimed, "Which Python?")
    listed = basis(claimed, asked["id"], asked["id"])
    taken = forks_model.route("s1", listed, answer=line_answer("looking"), failed=None)
    assert taken["outcome"] == "hand_over", taken
    events = events_model.read_events(claimed)

    assert forks_model.ask("s1", listed, []) is None
    assert forks_model.route("s1", listed, answer=line_answer("again"), failed=None)[
        "outcome"
    ] == ("dropped")
    assert [e for e in events_model.read_events(claimed) if e["kind"] == "reply"] == [
        e for e in events if e["kind"] == "reply"
    ]
    assert deliverable(claimed) == [asked["id"]]


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

    def lapses_meanwhile(page_dir, text, **options):
        opened_long_ago(line_turn, activity_model.STARTING_GRACE)
        with PageTransaction(claimed) as page:
            [event] = [e for e in page.events if e["id"] == asked["id"]]
            delivery_model.record_pickup(page, [event], session="s1", turn="t1")
        return checked(page_dir, text, **options)

    monkeypatch.setattr(thread_model, "checked_text", lapses_meanwhile)
    assert forks_model.route(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=line_answer("Yes."),
        failed=None,
    ) == {"outcome": "dropped", "text": "Yes."}
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
        answer=line_answer("checking the restart"),
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
            answer=line_answer("checking who holds it"),
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
    """The follower is the session's lane while it runs and lists a report for each
    kept-back thread for the module. It waits on the page's subscription,
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
    listed = [json.loads(line)["do"] for line in capsys.readouterr().out.splitlines()]
    turn = basis(claimed, asked[0]["id"])["turn"]
    assert listed[0] == []
    assert listed[1] == [
        {
            "id": f"line:{turn}",
            "do": "report",
            "basis": {
                "kind": "line",
                "thread": {
                    "page": str(claimed.resolve()),
                    "thread": asked[0]["id"],
                    "inputs": [asked[0]["id"]],
                    "turn": turn,
                },
            },
        }
    ]
    assert nudged == []


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
    [listed] = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert listed["do"] == []


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
