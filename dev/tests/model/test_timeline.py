"""`leaf-dev logs timeline` answers who did what to a message: which line turn held it,
what came of its line fork, why no fork lane took a message, and where each of the
session's line turns stands now."""

from datetime import datetime, timedelta

from click.testing import CliRunner

from leaf import state
from leaf.event_log import append_event
from leaf.interaction_log import append_interactions
from leaf_dev.cli import cli


def at(minute: int, second: int = 0) -> str:
    return f"2026-10-14T12:{minute:02d}:{second:02d}+00:00"


def test_timeline_names_the_line_turns_outcomes_and_why_no_lane_took_a_message(
    tmp_path,
):
    state.prompt_turn("s1", "p1")
    running = state.open_agent_turn("s1")
    closed = state.open_agent_turn("s1")
    lapsed = state.open_agent_turn("s1")
    assert running and closed and lapsed
    state.close_agent_turns("s1", turn=closed)
    turns = state.agent_turns("s1")
    long_ago = datetime.now().astimezone() - timedelta(hours=1)
    turns[lapsed]["opened"] = long_ago.isoformat()
    state.AGENT_TURNS.write(
        state.session_file("s1", state.AGENT_TURNS.kind), {"turns": turns}
    )

    def said(identity: str, minute: int) -> dict:
        return {
            "kind": "comment",
            "id": identity,
            "ts": at(minute),
            "author": "user",
            "attention": True,
            "text": f"Message {identity}",
        }

    for event in [
        said("c0", 0),
        said("c1", 1),
        {
            "kind": "pickup",
            "id": "held",
            "ts": at(1, 0),
            "author": "agent",
            "events": ["c1"],
            "phase": "held",
            "session": "s1",
            "turn": running,
        },
        {
            "kind": "reply",
            "id": "line",
            "ts": at(1, 2),
            "author": "agent",
            "parent": "c1",
            "responds": "c1",
            "ephemeral": True,
            "session": "s1",
            "turn": running,
            "text": "checking the lease",
        },
        said("c3", 3),
    ]:
        append_event(tmp_path, event)

    def follower(minute: int) -> dict:
        return {
            "ts": at(minute, 30),
            "source": "cli",
            "type": "follower",
            "session": "s1",
        }

    def admitted(identity: str, minute: int, *, lane: bool) -> dict:
        return {
            "ts": at(minute),
            "source": "cli",
            "type": "fork_admission",
            "session": "s1",
            "event": identity,
            "kept_back": lane,
            "held_by": None,
            "lane": lane,
        }

    append_interactions(
        tmp_path,
        [
            admitted("c0", 0, lane=False),
            follower(0),
            admitted("c1", 1, lane=True),
            {
                "ts": at(1, 2),
                "source": "cli",
                "type": "fork_outcome",
                "session": "s1",
                "thread": "c1",
                "inputs": ["c1"],
                "outcome": "hand_over",
                "text": "checking the lease",
                "line": "line",
                "elapsedMs": 1500.0,
            },
            admitted("c3", 3, lane=False),
        ],
    )

    result = CliRunner().invoke(
        cli, ["logs", "timeline", str(tmp_path), "--until", "2026-10-14T13:00:00Z"]
    )
    assert result.exit_code == 0, result.output
    out = result.output
    # Which line turn held the message, and what came of its line fork.
    assert f"pickup held of c1 in turn {running[:8]}" in out
    assert "hand_over in 1.5 s: line “checking the lease”" in out
    # Why admission found no fork lane, each cause told apart.
    assert "c0 not kept back: no fork lane: no pages follower noted" in out
    assert "c3 not kept back: no fork lane: the follower from " in out
    assert "pages follower keeps threads back for line forks" in out
    # Each line turn of the session as it stands now.
    shown = [
        line.strip()
        for line in out.splitlines()
        if "line turn " in line and ": opened " in line
    ]
    assert len(shown) == 3, out
    assert shown[0].startswith(f"line turn {lapsed[:8]} on no thread here: opened ")
    assert shown[0].endswith(", lapsed")
    assert shown[1].startswith(f"line turn {running[:8]} on c1: opened ")
    assert shown[1].endswith(", running")
    assert shown[2].startswith(f"line turn {closed[:8]} on no thread here")
    assert ", closed " in shown[2]
