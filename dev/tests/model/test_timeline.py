"""`leaf-dev logs timeline` answers who did what to a message: what Leaf asked its
line fork, what came of it, and whether a pages follower ran."""

from click.testing import CliRunner

from leaf.log.event_log import append_event
from leaf.log.interaction_log import append_interactions
from leaf_dev.cli import cli

DROPPED = "the agent spoke in the thread, or a turn joined its round, first"


def at(minute: int, second: int = 0) -> str:
    return f"2026-10-14T12:{minute:02d}:{second:02d}+00:00"


def test_timeline_names_what_came_of_each_line_fork(tmp_path):
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
            "kind": "reply",
            "id": "line",
            "ts": at(1, 2),
            "author": "agent",
            "parent": "c1",
            "responds": "c1",
            "ephemeral": True,
            "session": "s1",
            "turn": "t1",
            "text": "checking the lease",
        },
        said("c2", 2),
    ]:
        append_event(tmp_path, event)

    def asked(thread: str, minute: int, running: list[str]) -> dict:
        return {
            "ts": at(minute),
            "source": "cli",
            "type": "fork_asked",
            "session": "s1",
            "thread": thread,
            "inputs": [thread],
            "running": running,
        }

    def came(thread: str, minute: int, second: int, **outcome) -> dict:
        return {
            "ts": at(minute, second),
            "source": "cli",
            "type": "fork_outcome",
            "session": "s1",
            "thread": thread,
            "inputs": [thread],
            "running": [],
            **outcome,
        }

    append_interactions(
        tmp_path,
        [
            {"ts": at(0, 30), "source": "cli", "type": "follower", "session": "s1"},
            asked("c1", 1, ["Bash"]),
            came(
                "c1",
                1,
                2,
                outcome="posted",
                text="checking the lease",
                line="line",
                elapsedMs=1500.0,
            ),
            asked("c2", 2, []),
            came(
                "c2",
                2,
                3,
                outcome="dropped",
                why=DROPPED,
                text="renaming the lease",
                elapsedMs=2500.0,
            ),
        ],
    )

    result = CliRunner().invoke(
        cli, ["logs", "timeline", str(tmp_path), "--until", "2026-10-14T13:00:00Z"]
    )
    assert result.exit_code == 0, result.output
    out = result.output
    # What Leaf asked each line fork, and what came of it: the line it posted, or why
    # its line went in nowhere, with the line it wrote.
    assert "asked for c1 (session running Bash)" in out
    assert "posted in 1.5 s: line “checking the lease”" in out
    assert "fork's working line in turn t1: “checking the lease”" in out
    assert "asked for c2 (session running nothing)" in out
    assert f"dropped in 2.5 s: {DROPPED}; line “renaming the lease”" in out
    # Whether a pages follower ran, which lists the line forks.
    assert "pages follower lists line forks" in out
    # Each message's line says what its line fork did, and the posted line is its
    # first words.
    assert "c0 comment  no fork · first words —" in out
    assert "c1 comment  fork posted 1.5s · first words 2.0s (progress)" in out
    assert "c2 comment  fork dropped 2.5s (the agent spoke in the thread" in out
