"""The journey's harness readings: what a step records of each comment, the records
each harness's session gives its turn phases, and how the Claude Code journey reads
its pane."""

import json
import os
import signal
import subprocess
import sys
import time
from itertools import count

import pytest
from leaf_dev import journey, journey_claude_code, journey_pi
from leaf_dev.review_scenario import SLEEP


def at(seconds: float) -> str:
    return f"2026-10-08T09:00:{seconds:06.3f}+00:00"


def test_a_steps_comments_are_timed_from_the_log():
    """Each step keeps the comments it posted, timed from the page's log on the
    server's clock from their admission, with the turn split from the session's
    records from the opened pickup on. A permission prompt the user answered marks
    its step's comments, and the release ask's, so a reading held up by one is told
    apart from those that were not."""
    events = [
        {"kind": "comment", "id": "c1", "ts": at(0)},
        {
            "kind": "pickup",
            "id": "p1",
            "phase": "opened",
            "events": ["c1"],
            "ts": at(1),
        },
        {
            "kind": "reply",
            "author": "agent",
            "id": "r1",
            "parent": "c1",
            "responds": "c1",
            "text": "Two items block it.",
            "ts": at(9),
        },
    ]
    records = [
        {"type": "user", "message": {"content": []}, "received_at": at(0.5)},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "t", "name": "Bash", "input": {}}
                ]
            },
            "received_at": at(3),
        },
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "t"}]},
            "received_at": at(4),
        },
    ]
    terminal = journey.Terminal()
    terminal.trace = records
    session = journey.Session(
        None, None, [], "", "", {}, {}, None, records=terminal.records
    )
    user = journey.User(session, "v", lambda: events, terminal)
    user.release_reading = {
        "version": "v",
        "comment": {
            "eventIds": ["c0"],
            "sinceAdmissionMs": {"replied": 12000},
            "sinceSendMs": {},
        },
    }
    terminal.approved.append("Do you want to make this edit to index.html?")
    user.passed("release", time.monotonic())
    user.ids["mid-turn"] = "c1"
    user.sent = ["mid-turn"]
    terminal.approved.append("Do you want to proceed?")
    user.passed("mid-turn", time.monotonic() - 6)

    sample = user.sample()
    assert sample["comment"]["approved"] == [
        "Do you want to make this edit to index.html?"
    ]
    release, step = sample["steps"]
    assert release["comments"] == {}
    assert step["step"] == "mid-turn"
    assert step["approved"] == ["Do you want to proceed?"]
    # The time a prompt held the session is the step's like any other.
    assert 5.9 <= step["seconds"] <= 6.5
    reading = step["comments"]["mid-turn"]
    assert reading["approved"] == ["Do you want to proceed?"]
    assert reading["sinceAdmissionMs"]["pickedUp"] == 1000
    assert reading["sinceAdmissionMs"]["replied"] == 9000
    # The record before the pickup is no delivery; the work after it is.
    assert [phase["phase"] for phase in reading["turn"]] == [
        "delivery",
        "model",
        "tool",
        "model",
    ]
    assert reading["turn"][0] == {"phase": "delivery", "startMs": 0, "ms": 1000}
    assert terminal.approved == []
    prompted = {**sample, "target": "claude-code", "version": "old"}
    later = {
        **sample,
        "target": "claude-code",
        "comment": {**sample["comment"], "approved": []},
    }
    rows = journey.chart_rows(
        [prompted, later, {**later, "comment": sample["comment"]}]
    )
    # The latest version is chosen before rows split by prompt, so a prompted run of
    # an older version leaves the chart once a newer one runs.
    assert {row["row"] for row in rows} == {
        "Claude Code at v",
        "Claude Code after a permission prompt at v",
    }


PROMPT = """
 Bash command

   python3 -c 'import time; time.sleep(25.17)'
   Run the user's command

 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and don't ask again for python3 commands in /private/work
   3. No, and tell Claude what to do differently (esc)

 Esc to cancel · Tab to amend
"""


@pytest.mark.parametrize(
    "question",
    [
        "Do you want to proceed?",
        "Do you want to make this edit to index.html?",
        "Do you want to create notes.md?",
    ],
)
def test_a_permission_prompt_is_read_from_its_question_and_options(question):
    """Claude Code's prompts for a command, an edit and a new file share one shape,
    the question above "1. Yes" and "Esc to cancel"; the question alone, as the
    agent's own words may ask it, is not a prompt."""
    screen = PROMPT.replace("Do you want to proceed?", question)
    assert journey_claude_code.permission_prompt(screen) == question
    asked = f"⏺ {question} I can make the change once you say so.\n\n❯ \n"
    assert journey_claude_code.permission_prompt(asked) is None
    assert journey_claude_code.permission_prompt("❯ Try again\n") is None


def test_the_users_command_is_found_only_among_the_panes_own_processes():
    """Journeys run side by side run the same command; each finds only its own, among
    its pane's descendants, so another journey's command is not this one's turn."""
    command = [sys.executable, "-c", f"import time; {SLEEP}"]
    # Each in a process group of its own, which the test ends whole.
    pane = subprocess.Popen(
        ["sh", "-c", f"{subprocess.list2cmdline(command)}; true"],
        start_new_session=True,
    )
    other = subprocess.Popen(command, start_new_session=True)
    neighbour = subprocess.Popen(["sh", "-c", "sleep 30; true"], start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while not journey_claude_code.runs(pane.pid, SLEEP):
            assert time.monotonic() < deadline, "the pane's command never ran"
            time.sleep(0.1)
        assert not journey_claude_code.runs(neighbour.pid, SLEEP)
    finally:
        for process in (pane, other, neighbour):
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def test_claude_codes_transcript_gives_tool_and_turn_records(tmp_path):
    """Claude Code's transcript stamps each record as it writes it, and a prompt's
    content may be a bare string; the journey reads both, and nothing else."""
    session = "6f1c"
    path = tmp_path / ".claude" / "projects" / "-private-work" / f"{session}.jsonl"
    path.parent.mkdir(parents=True)
    lines = [
        {"type": "user", "timestamp": at(1), "message": {"content": "Serve it."}},
        {"type": "attachment", "timestamp": at(1.5), "attachment": {}},
        {
            "type": "assistant",
            "timestamp": at(2),
            "message": {
                "content": [
                    {"type": "tool_use", "id": "b", "name": "Bash", "input": {}}
                ]
            },
        },
        {"type": "system", "timestamp": at(2.5), "subtype": "stop_hook_summary"},
    ]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert journey_claude_code.transcript(tmp_path, session) == [
        {
            "type": "user",
            "message": {"content": [{"type": "text", "text": "Serve it."}]},
            "received_at": at(1),
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "b", "name": "Bash", "input": {}}
                ]
            },
            "received_at": at(2),
        },
    ]


def test_pis_events_give_the_turn_phases(monkeypatch):
    """Pi reports its runs and tool calls as RPC events; the journey keeps its tool
    calls as the records `turn_phases` reads, and tracks the shell commands
    running."""
    seconds = count(3)
    monkeypatch.setattr(journey_pi, "now", lambda: at(next(seconds)))
    pi = journey_pi.Pi.__new__(journey_pi.Pi)
    journey.Terminal.__init__(pi)
    pi.running, pi.settled, pi.closed_watches = False, 0, 0
    for event in (
        {"type": "agent_start"},
        {
            "type": "tool_execution_start",
            "toolCallId": "s",
            "toolName": "bash",
            "args": {"command": "sleep 1"},
        },
        {"type": "tool_execution_end", "toolCallId": "s"},
        {"type": "leaf_watch_closed", "code": 0},
        {"type": "agent_settled"},
    ):
        pi._hear(event)
    assert pi.commands == ["sleep 1"] and pi.running_commands == {}
    assert (pi.settled, pi.closed_watches, pi.idle()) == (1, 1, True)
    phases = journey.turn_phases(pi.records(), at(0), at(2), at(6))
    assert phases == [
        {"phase": "delivery", "startMs": 0, "ms": 2000},
        {"phase": "model", "startMs": 2000, "ms": 1000},
        {"phase": "tool", "startMs": 3000, "ms": 1000, "calls": ["sleep 1"]},
        {"phase": "model", "startMs": 4000, "ms": 2000},
    ]
