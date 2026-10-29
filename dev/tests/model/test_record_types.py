"""Schema-derived record types reach the existing storage API and stay current."""

import subprocess

from click.testing import CliRunner

from leaf.server import SERVICE
from leaf_dev import ROOT
from leaf_dev.commands import record_types


def test_record_types_follow_schema_changes(tmp_path, monkeypatch):
    output = tmp_path / "record_types.pyi"
    monkeypatch.setattr(record_types, "OUTPUT", output)
    output.write_text(record_types.generated_types())
    runner = CliRunner()
    assert runner.invoke(record_types.record_types, ["--check"]).exit_code == 0

    monkeypatch.setitem(SERVICE.schema["properties"]["port"], "type", "string")
    stale = runner.invoke(record_types.record_types, ["--check"])
    assert stale.exit_code == 1
    assert "Record types are stale" in stale.output

    # Checking reports drift without rewriting the file the developer reviews.
    assert "port: int" in output.read_text()
    changed = record_types.generated_types()
    assert "port: str" in changed
    output.write_text(changed)
    assert runner.invoke(record_types.record_types, ["--check"]).exit_code == 0


def test_generated_fields_are_checked_through_record_reads_and_writes(tmp_path):
    probe = tmp_path / "record_fields.py"
    probe.write_text(
        """\
from pathlib import Path
from leaf.record_types import ServiceRecord
from leaf.server import ACCESS, SERVICE, running_server

def valid(record: ServiceRecord, directory: Path):
    record['enabled'] = False
    record.pop('restart', None)
    SERVICE.write(directory, record)
    ACCESS.write(directory, {'token': 'key'})
    live = running_server(directory)
    if live is not None:
        address: str = live['url']
        return address
"""
    )

    def check():
        return subprocess.run(
            ["ty", "check", "--output-format", "concise", str(probe)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    valid = check()
    assert valid.returncode == 0, valid.stdout + valid.stderr
    with probe.open("a") as stream:
        stream.write(
            """
def invalid(directory: Path):
    record = SERVICE.read(directory)
    if record is not None:
        record['lifetim']
        record['port'] = '8080'
        record['lifetime'] = 'temporary'
    ACCESS.write(directory, {'token': None})
    ACCESS.write(directory, {})
"""
        )
    invalid = check()
    assert invalid.returncode != 0
    assert "error[invalid-key]" in invalid.stdout
    assert invalid.stdout.count("error[invalid-assignment]") == 2
    assert "error[invalid-argument-type]" in invalid.stdout
    assert "error[missing-typed-dict-key]" in invalid.stdout
