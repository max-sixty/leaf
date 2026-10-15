"""Claude Code's sandboxed commands, run outside its sandbox by Leaf's bridge."""

import os
import shutil
import subprocess

import pytest
from interact_support import ROOT
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
def test_a_bridged_command_keeps_its_stdin_streams_and_status(tmp_path):
    """The command reads the stdin it was given, and its stdout, stderr and exit
    status come back apart."""
    refused = subprocess.run(
        [LAUNCHER, "data", "set", str(tmp_path), "source"],
        input="{",
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 1
    assert refused.stdout == ""
    assert "invalid JSON (Expecting property name" in refused.stderr


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_ends_though_its_stdin_never_does():
    """A harness may hand a command a stdin that never ends, and a command that
    never reads it still finishes."""
    held = subprocess.Popen(
        [LAUNCHER, "--version"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert held.wait(timeout=30) == 0
        assert held.stdout.read().startswith("leaf ")
    finally:
        held.stdin.close()
        held.stdout.close()


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
