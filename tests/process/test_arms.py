"""Scratch ownership joins native resources before their state home disappears."""

import subprocess

from leaf_dev import ROOT
from leaf_dev.arms import environment, scratch


def test_scratch_joins_detached_adapter_and_its_retirement_writes(tmp_path):
    """Only transport is replaced; lifecycle, native subscription and leases are real."""
    retired = tmp_path / "retired"
    process = None
    try:
        with scratch(ROOT) as cwd:
            process = subprocess.Popen(
                [
                    str(ROOT / ".venv/bin/python"),
                    "-c",
                    """
import sys
from pathlib import Path
from watchfiles._rust_notify import RustNotify
from leaf.state import ensure_session, flocked, session_record, state_home_path
from leaf.leases import adapter_lease_path, release_lease, take_lease
from leaf.codex_adapter import adapter_start_lock_path

session = "scratch-owned-codex"
ensure_session(session, {"chat": True})
lease = take_lease(adapter_lease_path(session))
assert lease is not None
with RustNotify([str(state_home_path() / "sessions")], False, False, 300, True, False) as changes:
    print("ready", flush=True)
    while session_record(session)["ended"] is None:
        changes.watch(0, 1, 10000, None)
with flocked(adapter_start_lock_path(session)):
    release_lease(lease)
    # An adapter retires records after releasing its live lease, while still
    # holding the startup lock. Scratch must join these final writes too.
    assert (state_home_path() / "sessions").is_dir()
    (state_home_path() / "sessions" / "retirement-write").write_text("retired")
    Path(sys.argv[1]).write_text("retired")
""",
                    str(retired),
                ],
                env=environment(XDG_STATE_HOME=str(cwd / "state")),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert process.stdout.readline() == "ready\n"
        output, errors = process.communicate(timeout=10)
        assert process.returncode == 0, errors
        assert output == ""
        assert retired.read_text() == "retired"
        assert not cwd.exists()
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)
