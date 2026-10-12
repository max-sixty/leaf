"""The diagnostic reader reconstructs the browser writer's transport records."""

import json

import pytest
from click.testing import CliRunner
from leaf.cli import cli
from leaf.interaction_log import (
    append_interactions,
    client_records,
    interaction_time,
    read_interactions,
)


def test_reader_reconstructs_retries_and_reports_loss_before_filtering(tmp_path):
    def row(sequence, type="keydown", **fields):
        return {
            "ts": f"2026-10-09T06:08:{40 + sequence:02d}.000Z",
            "sequence": sequence,
            "type": type,
            **fields,
        }

    complete = row(2, "input", value="a large pasted draft")
    serialized = json.dumps(complete)
    middle = len(serialized) // 2
    split = [
        row(
            2 + part,
            "interaction_part",
            partOf=2,
            part=part,
            parts=2,
            originalType="input",
            json=piece,
        )
        for part, piece in enumerate((serialized[:middle], serialized[middle:]))
    ]
    # Delivery order can differ from event order; a Beacon duplicates a batch.
    first = client_records("tab", "/api/samples/child", [row(1, key="Escape"), *split])
    append_interactions(tmp_path, first)
    append_interactions(
        tmp_path, [{**record, "received": "2026-10-09T06:10:00Z"} for record in first]
    )
    append_interactions(
        tmp_path,
        client_records(
            "tab",
            "/api/samples/child",
            [
                row(7, "command", id="text.leave"),
                row(
                    5,
                    "interaction_part",
                    partOf=4,
                    part=1,
                    parts=2,
                    originalType="paste",
                    json="incomplete",
                ),
            ],
        ),
    )
    append_interactions(tmp_path, client_records("other", "/", [row(1, key="c")]))
    append_interactions(
        tmp_path,
        [
            {
                "source": "server",
                "ts": "2026-10-09T06:08:42Z",
                "method": "POST",
                "path": "/api/event",
                "status": 200,
                "durationMs": 1,
            }
        ],
    )
    records = read_interactions(tmp_path, session="tab")
    assert [(record["type"], record["sequence"]) for record in records] == [
        ("keydown", 1),
        ("input", 2),
        ("interaction_gap", 4),
        ("interaction_incomplete", 4),
        ("interaction_gap", 6),
        ("command", 7),
    ]
    assert records[1]["value"] == complete["value"]
    assert records[1]["page"] == "/api/samples/child"
    assert records[3]["missingParts"] == [0]
    # Filtering never invents a leading gap or hides observed loss.
    filtered = read_interactions(
        tmp_path,
        session="tab",
        since=interaction_time("2026-10-08T23:08:42-07:00"),
        until=interaction_time("2026-10-08T23:08:47-07:00"),
        types=("command",),
    )
    assert [(record["type"], record["sequence"]) for record in filtered] == [
        ("interaction_gap", 4),
        ("interaction_incomplete", 4),
    ]


def test_cli_reads_keys_commands_focus_and_requests_without_changing_the_log(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("TZ", "UTC")
    import time

    time.tzset()
    try:
        (tmp_path / "events.jsonl").write_text("")
        rows = client_records(
            "tab",
            "/",
            [
                {
                    "ts": "2026-10-09T06:08:42.551Z",
                    "sequence": 1,
                    "type": "keydown",
                    "key": "Escape",
                    "target": [
                        "leaf-text[name=reply]",
                        "div",
                        "aside#lf-margin-preview",
                    ],
                    "nodes": [76, 77, 57],
                },
                {
                    "ts": "2026-10-09T06:08:42.552Z",
                    "sequence": 2,
                    "type": "command",
                    "id": "text.leave",
                    "binding": "Escape",
                },
                {
                    "ts": "2026-10-09T06:08:42.553Z",
                    "sequence": 3,
                    "type": "focusin",
                    "target": ["div", "aside#lf-margin-preview"],
                    "nodes": [70, 57],
                },
            ],
        )
        append_interactions(
            tmp_path,
            [
                *rows,
                {
                    "source": "server",
                    "ts": "2026-10-09T06:08:42.554Z",
                    "method": "POST",
                    "path": "/api/event",
                    "status": 400,
                    "durationMs": 1.5,
                },
            ],
        )
        path = tmp_path / "interactions.jsonl"
        before = path.read_bytes()
        result = CliRunner().invoke(cli, ["page", "interactions", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert (
            result.output
            == """2026-10-09T06:08:42.551+00:00 tab / #1 keydown key="Escape" target="leaf-text[name=reply] < aside#lf-margin-preview" node=76
2026-10-09T06:08:42.552+00:00 tab / #2 command id="text.leave" binding="Escape"
2026-10-09T06:08:42.553+00:00 tab / #3 focusin target="div < aside#lf-margin-preview" node=70
2026-10-09T06:08:42.554+00:00 server POST /api/event → 400 (1.5 ms)
"""
        )
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
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == rows[1]
        assert path.read_bytes() == before
        result = CliRunner().invoke(
            cli,
            ["page", "interactions", str(tmp_path), "--since", "2026-10-09T06:08:42"],
        )
        assert result.exit_code == 1
        assert "require a timezone offset" in result.output
    finally:
        monkeypatch.undo()
        time.tzset()


def test_invalid_transport_is_refused_and_a_torn_line_is_skipped(tmp_path):
    malformed = [
        {"type": "interaction_part", "sequence": 1},
        {"type": "keydown", "sequence": 2, "ts": 42},
        {"type": "focusin", "sequence": 3, "target": [{}]},
    ]
    for entry in malformed:
        with pytest.raises((TypeError, ValueError)):
            client_records("bad", "/", [entry])
    # Arbitrary diagnostic payloads remain open; only interpreted fields are typed.
    valid = client_records(
        "good", "/", [{"type": "custom_observation", "detail": {"nested": [1, "two"]}}]
    )[0]
    append_interactions(tmp_path, [valid])
    # A crash can tear an append mid-line; the reader skips it and reads on.
    with (tmp_path / "interactions.jsonl").open("a") as stream:
        stream.write('{"source": "client", "sess\n')
    append_interactions(tmp_path, [valid])
    (tmp_path / "events.jsonl").write_text("")
    result = CliRunner().invoke(
        cli, ["page", "interactions", str(tmp_path), "--session", "good", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert [json.loads(line) for line in result.output.splitlines()] == [valid] * 2


def test_a_split_record_that_joins_into_no_entry_is_marked_not_read(tmp_path):
    """Ingress checks each part's coordinates and that its `json` is a string, not
    what the parts join into, so a group that joins into no entry is marked and
    every other row still reads."""
    broken = client_records(
        "tab",
        "/",
        [
            {
                "type": "interaction_part",
                "sequence": 1,
                "partOf": 1,
                "part": 0,
                "parts": 1,
                "originalType": "input",
                "json": "{not json",
            },
            {"type": "keydown", "sequence": 2},
        ],
    )
    append_interactions(tmp_path, broken)
    records = read_interactions(tmp_path, session="tab")
    assert [(row["type"], row["sequence"]) for row in records] == [
        ("interaction_unreadable", 1),
        ("keydown", 2),
    ]
    assert records[0]["originalType"] == "input"

    # Parts that join into a valid entry other than the one they name are marked too.
    mislabelled = client_records(
        "tab",
        "/",
        [
            {
                "type": "interaction_part",
                "sequence": 3,
                "partOf": 3,
                "part": 0,
                "parts": 1,
                "originalType": "input",
                "json": json.dumps({"type": "command", "sequence": 9}),
            },
        ],
    )
    append_interactions(tmp_path, mislabelled)
    records = read_interactions(tmp_path, session="tab")
    assert [(row["type"], row["sequence"]) for row in records][-1] == (
        "interaction_unreadable",
        3,
    )
