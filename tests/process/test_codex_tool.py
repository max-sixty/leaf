"""Codex's sandboxed agent runs `leaf` through the `run` tool of the MCP server
Leaf's Codex plugin declares (`codex_tool.py`), which Codex starts outside its
sandbox."""

import json
import os
import shutil
import subprocess
import sys
import time

import pytest
from interact_support import ROOT, STATED_TIMEOUT

SERVER = ROOT / "src" / "leaf" / "codex_tool.py"

# Stands in for Leaf behind the plugin's launcher, which runs a host's launcher in
# its place: it says where it ran, for which thread, with which words and stdin.
HOST_LAUNCHER = """#!/bin/sh
if [ "$1" = wait ]; then echo $$ > wait.pid; exec sleep 600; fi
printf '%s|%s|%s|%s|%s' "$PWD" "$CODEX_THREAD_ID" "$*" "$(cat)" "$CODEX_INTERNAL_ORIGINATOR_OVERRIDE"
echo refused >&2
exit 3
"""


@pytest.fixture
def server(tmp_path, monkeypatch, spawn):
    """The MCP server as Codex starts it, after the handshake, with a stand-in
    for Leaf behind the launcher."""
    launcher = tmp_path / "host-leaf"
    launcher.write_text(HOST_LAUNCHER)
    launcher.chmod(0o700)
    monkeypatch.setenv("LEAF_HOST_LAUNCHER", str(launcher))
    monkeypatch.setenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "Codex Desktop")
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    # MCP inherits its platform defaults plus the plugin's declared variables.
    # HOME and PATH are the only platform defaults this stand-in needs.
    forwarded = {"HOME", "PATH", *manifest["mcpServers"]["leaf"]["env_vars"]}
    # `spawn` ends it as Codex does, by closing the stdin it reads.
    process = spawn(
        [sys.executable, "-I", str(SERVER)],
        env={key: value for key, value in os.environ.items() if key in forwarded},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    session = Session(process)
    assert session.request(
        0, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}}
    )["capabilities"] == {"tools": {}}
    session.send({"method": "notifications/initialized"})
    return session


class Session:
    def __init__(self, process):
        self.process = process

    def send(self, message: dict) -> None:
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        self.process.stdin.flush()

    def receive(self) -> dict:
        return json.loads(self.process.stdout.readline())

    def request(self, id: int, method: str, params: dict) -> dict:
        self.send({"id": id, "method": method, "params": params})
        answer = self.receive()
        assert answer["id"] == id
        return answer["result"]

    def call(
        self,
        id: int,
        arguments: dict,
        thread: str = "codex-thread",
    ) -> None:
        meta = {"threadId": thread}
        self.send(
            {
                "id": id,
                "method": "tools/call",
                "params": {"name": "run", "arguments": arguments, "_meta": meta},
            }
        )


def test_a_call_runs_leaf_where_and_for_whom_codex_says(server, tmp_path):
    """Codex states the thread only in the call's `_meta`, and the server's own
    directory and stdin are not the agent's, so the call carries each to the
    command. Its output and exit status come back apart."""
    server.call(
        1, {"args": ["page", "claim", "page"], "cwd": str(tmp_path), "stdin": "text"}
    )
    answer = server.receive()
    assert answer["id"] == 1
    assert answer["result"] == {
        "content": [
            {
                "type": "text",
                "text": f"{tmp_path}|codex-thread|page claim page|text|Codex Desktop",
            },
            {"type": "text", "text": "refused\n"},
            {"type": "text", "text": "exit status 3"},
        ],
        "isError": True,
    }


def test_a_call_that_hangs_holds_up_no_other_and_ends_with_the_server(server, tmp_path):
    """A command that runs on, such as a `leaf wait` that finds no input, leaves
    later calls answered, and ends when Codex closes the server rather than holding
    the session's wait after it."""
    server.call(1, {"args": ["wait"], "cwd": str(tmp_path)})
    server.call(2, {"args": ["page", "check"], "cwd": str(tmp_path)})
    assert server.receive()["id"] == 2
    waiting = _written_pid(tmp_path / "wait.pid")
    server.process.stdin.close()
    server.process.wait(timeout=STATED_TIMEOUT)
    deadline = time.monotonic() + STATED_TIMEOUT
    while _alive(waiting):
        assert time.monotonic() < deadline, "the call's command outlived the server"
        time.sleep(0.05)


def test_a_call_ends_before_codex_gives_up_on_it(tmp_path, monkeypatch):
    """Codex abandons a call at its timeout and cancels nothing, so the server
    ends the command first and says so with whatever it printed."""
    from leaf import codex_tool

    launcher = tmp_path / "host-leaf"
    launcher.write_text(HOST_LAUNCHER)
    launcher.chmod(0o700)
    monkeypatch.setenv("LEAF_HOST_LAUNCHER", str(launcher))
    ended = codex_tool.run({"args": ["wait"], "cwd": str(tmp_path)}, None, 0.5)
    assert ended["isError"]
    assert "leaf ended this command after 0.5 s" in ended["content"][0]["text"]
    assert not _alive(int((tmp_path / "wait.pid").read_text()))


def _written_pid(path) -> int:
    deadline = time.monotonic() + STATED_TIMEOUT
    while not (text := path.read_text() if path.exists() else ""):
        assert time.monotonic() < deadline, f"nothing wrote {path}"
        time.sleep(0.05)
    return int(text)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS's sandbox")
def test_a_codex_sandbox_refusal_names_the_tool(tmp_path, monkeypatch):
    """Where Codex's sandbox refuses a `leaf` command what it needs, the refusal
    tells the agent to rerun it with the tool. The sandbox refuses writes to uv's
    cache too, which the launcher must not need there."""
    monkeypatch.setenv("CODEX_SANDBOX", "seatbelt")
    page = tmp_path / "page"
    uv_cache = subprocess.run(
        ["uv", "cache", "dir"], capture_output=True, text=True, check=True
    ).stdout.strip()
    profile = (
        "(version 1)(allow default)(deny file-write*"
        f' (subpath "{os.path.realpath(tmp_path)}")'
        f' (subpath "{os.path.realpath(uv_cache)}"))'
    )
    refused = subprocess.run(
        ["sandbox-exec", "-p", profile, ROOT / "bin" / "leaf", "page", "init", page],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 1
    assert "rerun it with the `run` tool of the `leaf` MCP server" in refused.stderr
