"""Response-time queries keep exact inputs, edits, missing evidence and clock bounds."""

import json
import os
from datetime import datetime

from click.testing import CliRunner

from leaf import interaction_log
from leaf.event_log import append_event
from leaf.interaction_log import append_interactions, client_records
from leaf_dev.cli import cli


def test_query_keeps_input_identity_and_missing_observations(tmp_path, monkeypatch):
    original_context = interaction_log.session_context

    def context(session, claim=None):
        if session == "session":
            return {
                "harness": "claude-code",
                "turn": "turn-one",
                "provider": False,
                "cwd": "/workspace/leaf",
                "transcript_path": "/logs/claude-session.jsonl",
            }
        if session == "successor":
            return {
                "harness": "codex",
                "turn": "native-codex-turn",
                "provider": True,
                "cwd": None,
                "transcript_path": None,
            }
        return original_context(session, claim)

    monkeypatch.setattr(interaction_log, "session_context", context)

    def event(kind, identity, second, **fields):
        return {
            "kind": kind,
            "id": identity,
            "ts": f"2026-10-14T12:00:{second:02d}+00:00",
            "author": "agent",
            "attention": False,
            **fields,
        }

    for row in [
        event("comment", "first", 0, author="user", attention=True, text="Measure it."),
        event("reply", "answer1", 2, parent="first", responds="first"),
        event(
            "reply",
            "second",
            3,
            author="user",
            attention=True,
            parent="answer1",
            text="Again.",
        ),
        event(
            "edit",
            "edited",
            4,
            author="user",
            attention=True,
            message="second",
            base="second",
            text="With the new version.",
        ),
        event(
            "pickup", "queued", 5, events=["edited"], phase="queued", session="session"
        ),
        event(
            "pickup",
            "opened",
            7,
            events=["edited"],
            phase="opened",
            session="session",
            turn="earlier-turn",
        ),
        event(
            "reply",
            "progress",
            9,
            parent="first",
            ephemeral=True,
            start={"item": "edited", "turn": "turn-one"},
            agent="Claude",
            session="session",
        ),
        event("reply", "unlinked", 10, parent="first", text="Other news."),
        event(
            "reply",
            "third",
            11,
            author="user",
            attention=True,
            parent="answer1",
            text="One more.",
        ),
        event(
            "reply",
            "failed",
            12,
            parent="first",
            responds="third",
            failure="startup_failed",
        ),
        event("comment", "reaction", 13, author="user", token="keep"),
        event(
            "pickup",
            "delivery-failed",
            14,
            events=["second"],
            phase="failed",
            session="failed-session",
            failure="startup_failed",
        ),
        event(
            "reply",
            "answer2",
            20,
            parent="first",
            responds="edited",
            session="successor",
            turn="native-codex-turn",
        ),
        event(
            "edit",
            "quiet-edit",
            21,
            author="user",
            message="first",
            base="first",
            text="Reworded without another request.",
        ),
        event("reply", "outside", 40, parent="first", responds="third"),
    ]:
        append_event(tmp_path, row)
    append_interactions(
        tmp_path,
        [
            {
                "ts": "2026-10-14T12:00:06+00:00",
                "source": "cli",
                "type": "fork_reply",
                "session": "session",
                "thread": "first",
                "inputs": ["second"],
                "outcome": "hand_over",
                "why": "it asks for a measurement",
                "elapsedMs": 2100.0,
            }
        ],
    )
    args = [
        "logs",
        "response-times",
        str(tmp_path),
        "--since",
        "2026-10-14T12:00:00Z",
        "--until",
        "2026-10-14T12:00:30Z",
    ]
    result = CliRunner().invoke(cli, [*args, "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    rows = {row["input_id"]: row for row in report["samples"]}
    # The fork that handed the message over decided its edit too, and the update
    # read Delivered from its opened pickup to the agent's first words.
    assert rows["edited"]["fork"] == {
        "outcome": "hand_over",
        "elapsed_s": 2.1,
        "why": "it asks for a measurement",
    }
    assert rows["first"]["fork"] is None
    assert report["summary"]["fork_hand_over"]["inputs"] == 2
    assert report["summary"]["fork_hand_over"]["p50_s"] == 5
    assert report["summary"]["delivered"]["p50_s"] == 2
    assert set(rows) == {"first", "second", "edited", "third"}
    assert rows["first"]["superseded_by_edit"] == "quiet-edit"
    assert rows["second"]["superseded_by_edit"] == "edited"
    assert set(rows["second"]["milestones"]) == {"failure"}
    assert rows["second"]["milestones"]["failure"]["elapsed_s"] == 11
    assert report["summary"]["failure"]["observed"] == 2
    assert rows["edited"]["message_id"] == "second"
    assert {
        name: value["elapsed_s"] for name, value in rows["edited"]["milestones"].items()
    } == {
        "queued": 1,
        "opened": 3,
        "started": 5,
        "progress": 5,
        "first_reply": 5,
        "answered": 16,
    }
    assert rows["edited"]["first_reply_kind"] == "progress"
    agents = rows["edited"]["agent_sessions"]
    assert set(agents) == {"queued", "opened", "progress", "answer2"}
    assert agents["queued"] == {
        "session": "session",
        "turn": None,
        "harness": "claude-code",
        "turn_provider": None,
        "cwd": "/workspace/leaf",
        "transcript_path": "/logs/claude-session.jsonl",
    }
    assert rows["second"]["agent_sessions"]["delivery-failed"]["harness"] is None
    assert agents["progress"] == {
        "session": "session",
        "turn": "turn-one",
        "harness": "claude-code",
        "turn_provider": "leaf",
        "cwd": "/workspace/leaf",
        "transcript_path": "/logs/claude-session.jsonl",
    }
    assert agents["opened"] == {
        **agents["progress"],
        "turn": "earlier-turn",
        "turn_provider": None,
    }
    assert agents["answer2"] == {
        "session": "successor",
        "turn": "native-codex-turn",
        "harness": "codex",
        "turn_provider": "native",
        "cwd": None,
        "transcript_path": None,
    }
    assert rows["edited"]["milestones"]["progress"]["turn"] == "turn-one"
    assert rows["edited"]["milestones"]["answered"]["turn"] == "native-codex-turn"
    assert rows["edited"]["milestones"]["first_reply"]["turn_provider"] == "leaf"
    assert rows["third"]["milestones"]["failure"]["elapsed_s"] == 1
    assert "first_reply" not in rows["third"]["milestones"]
    assert rows["third"]["observed_for_s"] == 19
    assert report["pages"][0]["unlinked_agent_replies"] == ["unlinked"]
    assert report["summary"]["first_reply"] == {
        "inputs": 4,
        "observed": 2,
        "missing": 2,
        "clock_errors": 0,
        "p50_s": 3.5,
        "p90_s": 4.7,
        "p95_s": 4.85,
        "max_s": 5,
        "total_s": 7,
    }
    human = CliRunner().invoke(cli, args)
    assert human.exit_code == 0, human.output
    assert "4 user message versions" in human.output
    assert "Unlinked agent replies: 1" in human.output


def test_query_reports_clock_errors_and_requires_qualified_timestamps(tmp_path):
    for row in [
        {
            "id": "input",
            "kind": "comment",
            "author": "user",
            "attention": True,
            "ts": "2026-10-14T12:00:05Z",
            "attempt": "send-input",
        },
        {
            "id": "reply",
            "kind": "reply",
            "author": "agent",
            "parent": "input",
            "responds": "input",
            "ts": "2026-10-14T12:00:04Z",
        },
    ]:
        append_event(tmp_path, row)
    append_interactions(
        tmp_path,
        [
            {
                **row,
                "source": "client",
                "session": "origin",
                "page": "/",
                "ts": "2026-10-14T12:00:06Z",
                "visibility": "visible",
                "observed_at": "2026-10-14T12:00:06Z",
            }
            for row in [
                {
                    "type": "event_submit",
                    "sequence": 1,
                    "monotonic_ms": 10,
                    "attempt": "send-input",
                },
                {
                    "type": "reply_visible",
                    "sequence": 2,
                    "monotonic_ms": 5,
                    "reply_id": "reply",
                    "presentation_kind": "message_words",
                    "reply_kind": "answer",
                    "surface": "panel",
                },
            ]
        ],
    )
    result = CliRunner().invoke(
        cli,
        [
            "logs",
            "response-times",
            str(tmp_path),
            "--until",
            "2026-10-14T12:00:30Z",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)["summary"]
    assert summary["send_to_visible"] == summary["first_reply"]
    assert summary["first_reply"] == {
        "inputs": 1,
        "observed": 0,
        "missing": 0,
        "clock_errors": 1,
        "p50_s": None,
        "p90_s": None,
        "p95_s": None,
        "max_s": None,
        "total_s": 0,
    }
    invalid = CliRunner().invoke(
        cli, ["logs", "response-times", str(tmp_path), "--since", "2026-10-14T12:00:00"]
    )
    assert invalid.exit_code != 0
    assert "timezone" in invalid.output


def test_query_joins_one_browser_clock_and_selects_declared_purpose(
    tmp_path, monkeypatch
):
    """Unrelated tabs, hidden words and clock skew cannot shorten a response."""

    def at(second):
        return f"2026-10-14T12:00:{second:02d}Z"

    for row in [
        {
            "id": "one",
            "kind": "comment",
            "author": "user",
            "attention": True,
            "ts": at(1),
            "attempt": "send-one",
        },
        {
            "id": "two",
            "kind": "comment",
            "author": "user",
            "attention": True,
            "ts": at(5),
            "attempt": "send-two",
        },
        {
            "id": "three",
            "kind": "comment",
            "author": "user",
            "attention": True,
            "ts": at(15),
        },
        {
            "id": "progress",
            "kind": "reply",
            "author": "agent",
            "ephemeral": True,
            "parent": "one",
            "start": {"item": "one"},
            "ts": at(9),
        },
        {
            "id": "answer",
            "kind": "reply",
            "author": "agent",
            "parent": "one",
            "responds": "one",
            "attempt": "answer-attempt",
            "ts": at(25),
        },
    ]:
        append_event(tmp_path, row)
    append_interactions(
        tmp_path,
        [
            {
                "source": "developer",
                "type": "run_context",
                "ts": at(2),
                "purpose": "user-review",
                "run": "preview-before-test",
            },
            {
                "source": "developer",
                "type": "run_context",
                "ts": at(2),
                "purpose": "test",
                "run": "test-run",
            },
            {
                "source": "developer",
                "type": "run_context",
                "ts": at(10),
                "purpose": "user-review",
                "run": "review-run",
            },
            {
                "source": "server",
                "type": "reply_stream_words",
                "ts": at(8),
                "input_id": "one",
                "parent": "one",
                "attempt": "answer-attempt",
                "session": "model-session",
                "turn": "stream-turn",
                "agent": "Codex",
                "context": None,
            },
        ],
    )
    monkeypatch.setattr("leaf.interaction_log.now_iso", lambda: at(20))

    def row(sequence, type, monotonic_ms, **fields):
        return {
            "type": type,
            "sequence": sequence,
            "monotonic_ms": monotonic_ms,
            "visibility": "visible",
            "observed_at": "2099-01-01T00:00:00Z",
            **fields,
        }

    visible = {
        "presentation_kind": "message_words",
        "reply_kind": "progress",
        "surface": "panel",
    }
    records = [
        row(1, "event_submit", 1000, attempt="send-one"),
        row(2, "event_submit", 1100, attempt="send-two"),
        row(
            3,
            "reply_visible",
            1300,
            input_id="two",
            reply_id=None,
            presentation_kind="status_words",
            reply_kind="work",
            surface="panel",
        ),
        row(
            4,
            "reply_visible",
            1400,
            reply_id="progress",
            **visible,
            visibility="hidden",
        ),
        row(
            5,
            "reply_visible",
            1500,
            reply_id="stream:answer-attempt",
            attempt="answer-attempt",
            **visible,
        ),
        row(6, "reply_visible", 1600, reply_id="progress", **visible),
        row(7, "event_submit", 1700, attempt="send-one"),
        row(
            8,
            "reply_visible",
            2000,
            input_id="two",
            reply_id=None,
            presentation_kind="working_words",
            reply_kind="work",
            surface="panel",
        ),
    ]
    append_interactions(tmp_path, client_records("origin", "/", records[4:]))
    append_interactions(tmp_path, client_records("origin", "/", records[:4]))
    append_interactions(tmp_path, client_records("origin", "/", records[4:5]))
    # Another viewer has no matching submission on its own clock; sample paths
    # cannot collide with the containing page's event identities either.
    append_interactions(
        tmp_path,
        client_records(
            "viewer",
            "/",
            [
                row(1, "reply_visible", 10, reply_id="progress", **visible),
            ],
        ),
    )
    append_interactions(
        tmp_path,
        client_records(
            "origin",
            "/api/samples/child",
            [
                row(9, "reply_visible", 1200, reply_id="progress", **visible),
            ],
        ),
    )
    args = ["logs", "response-times", str(tmp_path), "--until", at(30), "--json"]
    pending = CliRunner().invoke(
        cli, ["logs", "response-times", str(tmp_path), "--until", at(22), "--json"]
    )
    assert pending.exit_code == 0, pending.output
    [streamed] = [
        row for row in json.loads(pending.output)["samples"] if row["input_id"] == "one"
    ]
    assert streamed["first_reply_kind"] == "stream"
    assert "answered" not in streamed["milestones"]
    assert streamed["milestones"]["send_to_visible"]["elapsed_s"] == 0.5
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    rows = {row["input_id"]: row for row in report["samples"]}
    assert rows["one"]["provenance"] is None
    assert rows["two"]["provenance"]["purpose"] == "test"
    assert rows["three"]["provenance"]["purpose"] == "user-review"
    assert rows["one"]["milestones"]["send_to_visible"]["elapsed_s"] == 0.5
    assert rows["two"]["milestones"]["send_to_visible"]["elapsed_s"] == 0.2
    assert rows["two"]["milestones"]["send_to_visible"]["surface"] == "panel"
    assert "send_to_visible" not in rows["three"]["milestones"]
    assert report["summary"]["send_to_visible"]["missing"] == 1
    selected = CliRunner().invoke(cli, [*args, "--exclude-purpose", "test"])
    assert selected.exit_code == 0, selected.output
    filtered = json.loads(selected.output)
    assert {row["input_id"] for row in filtered["samples"]} == {"one", "three"}
    assert filtered["selection"]["excluded_inputs"] == 1


def test_query_times_titles_and_publications_for_the_inputs_awaiting_them(tmp_path):
    """A thread's first title times each input admitted while it had none, whether
    the page server or the agent's own answer named it; one admitted later has none.
    An answer times the publication of the revision it stands on where the page
    published that revision after the input."""

    def at(second):
        return f"2026-10-14T12:00:{second:02d}Z"

    def user(kind, identity, second, **fields):
        return {
            "kind": kind,
            "id": identity,
            "author": "user",
            "attention": True,
            "ts": at(second),
            "revision": 1,
            **fields,
        }

    def agent(kind, identity, second, **fields):
        return {
            "kind": kind,
            "id": identity,
            "author": "agent",
            "ts": at(second),
            **fields,
        }

    for row in [
        user("comment", "asked", 0, text="Is it recorded?"),
        agent("thread_title", "named", 2, thread="asked", title="Release record"),
        user("reply", "again", 3, parent="asked", text="And the notes?"),
        user("comment", "change", 4, text="Record it on the board."),
        agent(
            "reply",
            "changed",
            10,
            parent="change",
            responds="change",
            title="Board change",
            revision=2,
            text="Recorded.",
        ),
        agent("reply", "said", 11, parent="asked", responds="asked", revision=1),
    ]:
        append_event(tmp_path, row)
    revisions = tmp_path / "revisions"
    revisions.mkdir()
    for revision, published in ((1, "2026-10-14T11:59:00Z"), (2, at(8))):
        marker = revisions / f"r{revision}-{revision:016x}.html"
        marker.write_text("<main></main>")
        stamp = datetime.fromisoformat(published).timestamp()
        os.utime(marker, (stamp, stamp))
    result = CliRunner().invoke(
        cli, ["logs", "response-times", str(tmp_path), "--until", at(30), "--json"]
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    rows = {row["input_id"]: row for row in report["samples"]}
    milestones = {
        input_id: {
            name: rows[input_id]["milestones"][name]["elapsed_s"]
            for name in ("titled", "published")
            if name in rows[input_id]["milestones"]
        }
        for input_id in rows
    }
    assert milestones == {
        "asked": {"titled": 2},
        "again": {},
        "change": {"titled": 6, "published": 4},
    }
    assert rows["change"]["milestones"]["published"]["revision"] == 2
    assert report["summary"]["titled"]["observed"] == 2
    assert report["summary"]["published"]["observed"] == 1
