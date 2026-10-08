"""The journey's harness readings: what a step records of each comment, and the
records each harness's session gives its turn phases."""

import json
from itertools import count

from leaf_dev import journey, journey_claude_code, journey_pi


def at(seconds: float) -> str:
    return f"2026-10-08T09:00:{seconds:06.3f}+00:00"


def test_a_steps_comments_are_timed_from_the_log_and_the_page():
    """Each step keeps the comments it sent, timed on the page server's clock from
    their admission and on the page's from their send, with the turn split from the
    session's records from the opened pickup on; a permission prompt the user
    answered is named in its step and not counted in its time."""
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
    shown = []

    class Page:
        def evaluate(self, script, arg=None):
            assert script == "window.__leafVerifier.replyShownAt"
            shown.append(arg)
            return 1_000_000 + 9_500

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
        None, Page(), [], "", "", {}, {}, None, records=terminal.records
    )
    user = journey.User(session, "v", lambda: events, terminal)
    profile = journey.AgentProfile()
    profile.ask_count = 1
    profile.visible_reply_started_ms = 1_000_000
    profile.acknowledged = [0.04]
    profile.event_ids = ["c1"]
    user.ids["mid-turn"], user.profiles["mid-turn"] = "c1", profile
    user.sent = ["mid-turn"]
    terminal.approved.append({"prompt": "Do you want to proceed?", "seconds": 5})
    user.passed("mid-turn", journey.time.monotonic() - 6)
    user.release_reading = {"version": "v", "comment": {"eventIds": ["c0"]}}

    sample = user.sample()
    [step] = sample["steps"]
    assert step["step"] == "mid-turn"
    assert step["approved"] == ["Do you want to proceed?"]
    assert 0.9 <= step["seconds"] <= 1.5
    reading = step["comments"]["mid-turn"]
    assert reading["sinceAdmissionMs"]["pickedUp"] == 1000
    assert reading["sinceAdmissionMs"]["replied"] == 9000
    assert reading["sinceSendMs"]["responseVisible"] == 9500
    assert shown == [{"thread": "c1", "id": "r1", "ts": at(9)}]
    # The record before the pickup is no delivery; the work after it is.
    assert [phase["phase"] for phase in reading["turn"]] == [
        "delivery",
        "model",
        "tool",
        "model",
    ]
    assert reading["turn"][0] == {"phase": "delivery", "startMs": 0, "ms": 1000}
    assert terminal.approved == []


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
    """Pi reports its runs and tool calls as RPC events; the journey keeps them as
    the records `turn_phases` reads, and tracks the shell commands running."""
    seconds = count(2)
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
