"""Claude Code's sandboxed commands, run outside its sandbox by Leaf's bridge."""

import os
import shutil
import socket
import subprocess

import pytest
from interact_support import ROOT, STATED_TIMEOUT

from leaf import bridge as bridge_model
from leaf import hooks as hooks_model
from leaf import service as service_model

LAUNCHER = str(ROOT / "bin" / "leaf")


@pytest.fixture
def bridged(monkeypatch):
    """A Claude Code session whose hook before a `leaf` command ran and whose
    shell is sandboxed."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bridged")
    hooks_model.cmd_hook(
        "claude-code",
        {
            "hook_event_name": "PreToolUse",
            "session_id": "bridged",
            "tool_name": "Bash",
            "tool_input": {"command": "leaf page claim page"},
        },
    )
    monkeypatch.setenv("SANDBOX_RUNTIME", "1")
    # The bridge is reached directly here, not through a proxy the host may name.
    for name in ("HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS's sandbox")
@pytest.mark.usefixtures("bridged")
def test_a_sandboxed_command_runs_outside_the_sandbox(page_dir):
    """Claude Code's sandbox refuses a command the state home, where a claim is
    written. The launcher hands the command to the bridge the hook left
    running outside it, so the claim takes. This sandbox lets a command reach
    127.0.0.1 directly, as Claude Code's does through its proxy."""
    state = os.path.realpath(os.environ["XDG_STATE_HOME"])
    profile = f'(version 1)(allow default)(deny file-write* (subpath "{state}"))'
    claimed = subprocess.run(
        ["sandbox-exec", "-p", profile, LAUNCHER, "page", "claim", str(page_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert claimed.returncode == 0, claimed.stderr
    assert service_model.page_claim(page_dir)["id"] == "bridged"


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_keeps_its_stdin_streams_and_status(page_dir):
    """The command reads the stdin it was given, and its stdout, stderr and exit
    status come back apart."""
    refused = subprocess.run(
        [LAUNCHER, "data", "set", str(page_dir), "source"],
        input="{",
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 1
    assert refused.stdout == ""
    assert "invalid JSON (Expecting property name" in refused.stderr


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_ends_though_its_stdin_never_does(spawn):
    """A harness may hand a command a stdin that never ends, and a command that
    never reads it still finishes."""
    held = spawn(
        [LAUNCHER, "--version"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert held.wait(timeout=STATED_TIMEOUT) == 0
    assert held.stdout.read().startswith("leaf ")


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_refuses_a_socket_stdin_at_once(page_dir):
    """Claude Code hands a command spanning lines a socket as its stdin that never
    closes. A bridged command given no JSON gets an empty pipe in its place, and
    refuses at once rather than waiting for the socket to end."""
    held, caller = socket.socketpair()
    with held, caller:
        refused = subprocess.run(
            [LAUNCHER, "data", "set", str(page_dir), "source"],
            stdin=held,
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
    assert refused.returncode == 1
    assert "no JSON given" in refused.stderr


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_reads_a_socket_stdin_it_names(page_dir):
    """A command that names stdin itself (`--file -`) reads it through the bridge
    even from a socket, as a Node caller's piped stdin is."""
    held, caller = socket.socketpair()
    with held, caller:
        caller.sendall(b"{")
        caller.shutdown(socket.SHUT_WR)
        read = subprocess.run(
            [LAUNCHER, "data", "set", str(page_dir), "source", "--file", "-"],
            stdin=held,
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
    assert read.returncode == 1
    assert "invalid JSON (Expecting property name" in read.stderr


def test_a_background_job_keeps_the_bridge_while_the_job_stands(
    tmp_path, monkeypatch, dead_pid
):
    """A background job's next sitting runs on a fresh worker and may run `leaf`
    from a script, before which no hook runs, so the bridge serves the job for its
    lifetime rather than the worker's, and lets it go once the job is deleted."""
    job = tmp_path / "job"
    job.mkdir()
    (job / "state.json").write_text('{"sessionId": "bg-job"}')
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bg-job")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "PreToolUse", "session_id": "bg-job"}
    )
    assert bridge_model.live_sessions()
    (job / "state.json").unlink()
    assert not bridge_model.live_sessions()


def test_a_session_that_runs_no_leaf_command_starts_no_bridge():
    """Claude Code runs Leaf's start and prompt hooks in every session, and only
    the hook before a `leaf` command starts the bridge, so a session that never
    uses Leaf keeps no process of Leaf's running."""
    for payload in (
        {"hook_event_name": "SessionStart", "source": "resume"},
        {"hook_event_name": "UserPromptSubmit", "turn_id": "t1", "prompt": "hi"},
    ):
        hooks_model.cmd_hook("claude-code", {"session_id": "unbridged", **payload})
    assert not bridge_model.bridge_path("lock").exists()


@pytest.mark.parametrize(
    "argv",
    [["--help"], ["--version"], ["--root", "--", "x"]],
)
def test_the_bridge_client_forwards_leaf_arguments_verbatim(monkeypatch, argv):
    """`bin/leaf` hands a sandboxed command's whole argv to the bridge client,
    which passes every argument after its mode to Leaf unparsed, `--` included."""
    received = []
    monkeypatch.setattr(bridge_model, "run", lambda args: received.append(args) or 7)
    monkeypatch.setattr("sys.argv", ["bridge.py", "run", *argv])
    with pytest.raises(SystemExit) as exited:
        bridge_model.main()
    assert exited.value.code == 7
    assert received == [argv]
