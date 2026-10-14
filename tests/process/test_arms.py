"""Scratch ownership joins native resources before their state home disappears."""

import json
import os
import subprocess

import pytest
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


@pytest.mark.parametrize("permissions", [None, "judge"])
def test_codex_accepts_native_instruction_context_without_starting_a_model(
    tmp_path, monkeypatch, permissions
):
    """Use the installed native server; suppress only the model turn request."""
    from leaf_dev.codex_task import Task
    from leaf_dev.eval_codex import CodexChild

    monkeypatch.setenv(
        "PATH", f"{ROOT / 'node_modules/.bin'}{os.pathsep}{os.environ['PATH']}"
    )
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    calls, prompts = [], []
    request = Task.request

    def observe(task, method, params):
        calls.append((method, params))
        return request(task, method, params)

    monkeypatch.setattr(Task, "request", observe)
    monkeypatch.setattr(
        Task, "say", lambda task, prompt, schema: prompts.append(prompt)
    )
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    if permissions:
        from leaf_dev.arms import codex_home

        home = cwd.with_name(f"{cwd.name}-home")
        home.mkdir()
        codex_home(
            home / ".codex",
            'default_permissions = "judge"\n'
            '[permissions.judge.filesystem]\n":minimal" = "read"\n'
            f'{json.dumps(str(cwd) + "/**")} = "write"\n',
        )
    context = "Instructions from /arm/instructions.md:\n\nAuthor with native context."
    with CodexChild(
        cwd,
        "Write a page",
        "--append-system-prompt",
        context,
        stderr=tmp_path / "err.txt",
        limit=10,
        timed_out=tmp_path / "timed-out",
        env={"XDG_STATE_HOME": str(tmp_path / "state")},
        permissions=permissions,
    ) as child:
        assert child.task.thread
    assert prompts == ["Write a page"]
    assert calls[0][0] == "thread/start"
    assert calls[0][1]["developerInstructions"] == context
    assert ("sandbox" not in calls[0][1]) is bool(permissions)
