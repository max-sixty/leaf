"""Diagnostics keep one host clock, exact retry identity and visible loss evidence."""

import json
import time

import pytest
from click.testing import CliRunner

from leaf.cli import cli
from leaf.interaction_log import (
    INTERACTIONS_FILE,
    admit_batch,
    append_interactions,
    client_records,
    interaction_time,
    read_interactions,
)


def observation(sequence, type="keydown", **fields):
    return {
        "observed_at": "2099-01-01T00:00:00.000Z",
        "sequence": sequence,
        "monotonic_ms": sequence * 100,
        "visibility": "visible",
        "type": type,
        **fields,
    }


def test_reader_deduplicates_and_reports_loss_before_host_time_filtering(
    tmp_path, monkeypatch
):
    def stamp(second):
        monkeypatch.setattr(
            "leaf.interaction_log.now_iso", lambda: f"2026-10-09T06:08:{second}Z"
        )

    stamp(42)
    original = client_records("tab", "/api/samples/child", [observation(1)])
    original = append_interactions(tmp_path, original)
    stamp(45)
    append_interactions(
        tmp_path, client_records("tab", "/api/samples/child", [observation(1)])
    )
    stamp(46)
    append_interactions(
        tmp_path,
        client_records("tab", "/api/samples/child", [observation(5, "command")]),
    )
    stamp(47)
    append_interactions(
        tmp_path,
        client_records("tab", "/api/samples/child", [observation(3)]),
    )
    append_interactions(tmp_path, client_records("other", "/", [observation(1)]))
    append_interactions(
        tmp_path,
        [{"source": "server", "type": "request", "ts": "2026-10-09T06:08:44Z"}],
    )
    records = read_interactions(tmp_path, session="tab")
    assert [(row["type"], row["sequence"]) for row in records] == [
        ("keydown", 1),
        ("interaction_gap", 4),
        ("command", 5),
        ("interaction_gap", 2),
        ("keydown", 3),
    ]
    assert records[0] == original[0]
    filtered = read_interactions(
        tmp_path,
        session="tab",
        since=interaction_time("2026-10-08T23:08:43-07:00"),
        until=interaction_time("2026-10-08T23:08:47-07:00"),
        types=("command",),
    )
    assert [(row["type"], row["sequence"]) for row in filtered] == [
        ("interaction_gap", 2),
        ("command", 5),
    ]
    assert filtered[0]["through"] == 4
    # Browser wall-clock skew has no effect on host-time selection.
    assert filtered[1]["observed_at"].startswith("2099")


def test_cli_queries_canonical_records_without_changing_the_log(tmp_path, monkeypatch):
    # Process inspection may be refused by the test runner's sandbox; this test
    # exercises command recording against a known launch time.
    started = time.time()
    monkeypatch.setattr("leaf.interaction_log.launched", lambda: started)
    monkeypatch.setattr(
        "leaf.interaction_log.now_iso", lambda: "2026-10-09T06:08:42.551Z"
    )
    (tmp_path / "events.jsonl").write_text("")
    rows = client_records(
        "tab", "/", [observation(1, "command", id="text.leave", binding="Escape")]
    )
    rows = append_interactions(
        tmp_path,
        [
            *rows,
            {
                "source": "developer",
                "type": "run_context",
                "purpose": "test",
                "run": "test-run",
            },
        ],
    )
    path = tmp_path / INTERACTIONS_FILE
    before = path.read_bytes()
    result = CliRunner().invoke(
        cli,
        [
            "page",
            "interactions",
            str(tmp_path),
            "--session",
            "tab",
            "--type",
            "command",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == rows[0]
    # The query changes no record; it appends only its own `leaf_command` record.
    assert path.read_bytes().startswith(before)
    recorded = read_interactions(tmp_path)
    commands = [row for row in recorded if row["type"] == "leaf_command"]
    assert len(commands) == 1
    command = commands[0]
    assert command["command"] == "page interactions"
    assert command["durationMs"] >= 0
    all_rows = CliRunner().invoke(cli, ["page", "interactions", str(tmp_path)])
    assert all_rows.exit_code == 0, all_rows.output
    assert [json.loads(line) for line in all_rows.stdout.splitlines()] == recorded
    invalid = CliRunner().invoke(
        cli, ["page", "interactions", str(tmp_path), "--since", "2026-10-09T06:08:42"]
    )
    assert invalid.exit_code == 1
    assert "require a timezone offset" in json.loads(invalid.stderr)["error"]
    assert [
        row["command"] for row in read_interactions(tmp_path, types=("leaf_command",))
    ] == ["page interactions", "page interactions", "page interactions"]


def test_required_transport_is_validated_once_and_torn_lines_are_skipped(tmp_path):
    valid = observation(
        1,
        "custom_observation",
        detail={"nested": [1, "two"]},
        target=[{}],
        nodes={"custom": 1},
    )
    session = "0" * 32
    for changed in (
        {"observed_at": 42},
        {"observed_at": "2099-01-01T00:00:00Z"},
        {"sequence": True},
        {"monotonic_ms": "4"},
        {"monotonic_ms": -1},
        {"visibility": "unknown"},
        {"type": "Click"},
    ):
        with pytest.raises(ValueError):
            admit_batch({"session": session, "entries": [{**valid, **changed}]})
    for field in ("observed_at", "sequence", "monotonic_ms", "visibility", "type"):
        entry = {k: v for k, v in valid.items() if k != field}
        with pytest.raises(ValueError):
            admit_batch({"session": session, "entries": [entry]})
    for batch in (
        {"session": "tab", "entries": [valid]},
        {"session": session, "entries": []},
        {"session": session, "entries": [valid] * 101},
        {"session": session, "entries": [valid], "page": "/"},
    ):
        with pytest.raises(ValueError):
            admit_batch(batch)
    admit_batch({"session": session, "entries": [valid]})
    [admitted] = append_interactions(tmp_path, client_records("good", "/", [valid]))
    with (tmp_path / INTERACTIONS_FILE).open("ab") as stream:
        stream.write(b'{"source": "client", "text": "\xc3\n')
    append_interactions(tmp_path, [admitted])
    assert read_interactions(tmp_path, session="good") == [admitted]


def test_command_recording_includes_output_and_excludes_help(monkeypatch):
    """Diagnostics end after the caller has its output, and help names no work."""
    from leaf import cli as cli_model

    sequence = []
    monkeypatch.setattr(
        cli_model, "_print_result", lambda result: sequence.append("output")
    )
    monkeypatch.setattr(
        "leaf.interaction_log.record_command", lambda command: sequence.append(command)
    )
    runner = CliRunner()
    assert runner.invoke(cli, ["hook", "--harness", "codex"], input="{}").exit_code == 0
    assert sequence == ["output", "hook"]
    sequence.clear()
    assert runner.invoke(cli, ["--help"]).exit_code == 0
    assert sequence == ["output", ""]
