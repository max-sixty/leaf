"""`leaf-dev timeline` answers who did what to a message: which fork's turn answered
it, what Leaf refused or denied that fork, why no fork lane took a message, and
where each of the session's agent turns stands now."""

from datetime import datetime, timedelta

from click.testing import CliRunner

from leaf import state
from leaf.event_log import append_event
from leaf.interaction_log import append_interactions
from leaf_dev.cli import cli


def at(minute: int, second: int = 0) -> str:
    return f"2026-10-14T12:{minute:02d}:{second:02d}+00:00"


def test_timeline_names_the_forks_turns_refusals_and_why_no_lane_took_a_message(
    tmp_path,
):
    state.prompt_turn("s1", "p1")
    running = state.open_agent_turn("s1")
    closed = state.open_agent_turn("s1")
    lapsed = state.open_agent_turn("s1")
    assert running and closed and lapsed
    state.name_agent_turn("s1", running, "agent-1")
    state.name_agent_turn("s1", closed, "agent-2")
    state.close_agent_turns("s1", turn=closed)
    turns = state.agent_turns("s1")
    long_ago = datetime.now().astimezone() - timedelta(hours=1)
    turns[lapsed]["renewed"] = long_ago.isoformat()
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
            "id": "taken",
            "ts": at(1, 2),
            "author": "agent",
            "events": ["c1"],
            "phase": "opened",
            "session": "s1",
            "turn": running,
        },
        {
            "kind": "reply",
            "id": "r1",
            "ts": at(1, 20),
            "author": "agent",
            "parent": "c1",
            "responds": "c1",
            "session": "s1",
            "turn": running,
            "text": "Python 3.12.",
        },
        said("c2", 2),
        said("c3", 3),
        said("c4", 4),
    ]:
        append_event(tmp_path, event)

    def follower(minute: int, *, forks: bool, current: bool) -> dict:
        return {
            "ts": at(minute, 30),
            "source": "cli",
            "type": "follower",
            "session": "s1",
            "module": "abcdef0123456789",
            "forks": forks,
            "current": current,
        }

    def admitted(identity: str, minute: int, *, lane: float | None) -> dict:
        return {
            "ts": at(minute),
            "source": "cli",
            "type": "fork_admission",
            "session": "s1",
            "event": identity,
            "kept_back": lane is not None,
            "held_by": None,
            "lane": lane,
        }

    fork = {"source": "cli", "session": "s1", "thread": "c1", "inputs": ["c1"]}
    append_interactions(
        tmp_path,
        [
            admitted("c0", 0, lane=None),
            follower(0, forks=True, current=True),
            admitted("c1", 1, lane=1.0),
            {
                **fork,
                "ts": at(1, 1),
                "type": "fork_outcome",
                "outcome": "take",
                "agent": "leaf-c1",
                "turn": running,
            },
            {
                **fork,
                "ts": at(1, 3),
                "type": "fork_outcome",
                "step": "start",
                "outcome": "start",
                "agent": "leaf-c1",
                "agentId": "agent-1",
                "turn": running,
            },
            {
                "ts": at(1, 5),
                "source": "cli",
                "type": "command_denied",
                "session": "s1",
                "agent": "agent-1",
                "command": "cd /tmp && leaf thread reply ref --text 3.12",
                "reason": "Run each `leaf` command as a Bash call of its own",
            },
            {
                "ts": at(1, 10),
                "source": "cli",
                "type": "leaf_command",
                "command": "thread reply",
                "started": at(1, 9),
                "durationMs": 300.0,
                "session": "s1",
                "agent": "agent-1",
                "refused": "this agent's turn no longer holds c1",
            },
            follower(1, forks=False, current=True),
            admitted("c2", 2, lane=None),
            follower(2, forks=True, current=False),
            admitted("c3", 3, lane=None),
            follower(3, forks=True, current=True),
            admitted("c4", 4, lane=None),
        ],
    )

    result = CliRunner().invoke(
        cli, ["timeline", str(tmp_path), "--until", "2026-10-14T13:00:00Z"]
    )
    assert result.exit_code == 0, result.output
    out = result.output
    # Which fork's turn answered, and what Leaf refused or denied it.
    assert f"answer to c1 in leaf-c1's turn {running[:8]}" in out
    assert "leaf thread reply (300 ms) by leaf-c1 refused: this agent's turn" in out
    assert "denied leaf-c1's `cd /tmp && leaf thread reply ref --text 3.12`" in out
    # Why admission found no fork lane, each cause told apart.
    assert "c0 not kept back: no fork lane: no pages follower noted" in out
    assert "c2 not kept back: no fork lane: the hooks module has forks off" in out
    assert (
        "c3 not kept back: no fork lane: the session's hooks module (abcdef01)" in out
    )
    assert "c4 not kept back: no fork lane: the follower from " in out
    assert "pages follower keeps threads back for line forks" in out
    # Each agent turn of the session as it stands now.
    shown = [line.strip() for line in out.splitlines() if "agent turn " in line]
    assert len(shown) == 3, out
    assert shown[0].startswith(f"agent turn {running[:8]} of agent-1 on c1: opened ")
    assert shown[0].endswith(", running")
    assert shown[1].startswith(f"agent turn {closed[:8]} of agent-2 on no thread here")
    assert ", closed " in shown[1]
    assert shown[2].startswith(f"agent turn {lapsed[:8]} of an agent not yet named")
    assert shown[2].endswith(", lapsed")
