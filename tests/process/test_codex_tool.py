"""Codex's sandboxed agent runs `leaf` through the `run` tool of the MCP server
Leaf's Codex plugin declares (`codex_tool.py`), which Codex starts outside its
sandbox."""

import json
import subprocess
import sys

import pytest
from interact_support import ROOT

SERVER = ROOT / "skills" / "leaf" / "scripts" / "leaf" / "codex_tool.py"

# Stands in for Leaf behind the plugin's launcher, which runs a host's launcher in
# its place: it says where it ran, for which thread, with which words and stdin.
HOST_LAUNCHER = """#!/bin/sh
if [ "$1" = wait ]; then exec sleep 600; fi
printf '%s|%s|%s|%s' "$PWD" "$CODEX_THREAD_ID" "$*" "$(cat)"
echo refused >&2
exit 3
"""


@pytest.fixture
def server(tmp_path, monkeypatch):
    """The MCP server as Codex starts it, after the handshake, with a stand-in
    for Leaf behind the launcher."""
    launcher = tmp_path / "host-leaf"
    launcher.write_text(HOST_LAUNCHER)
    launcher.chmod(0o700)
    monkeypatch.setenv("LEAF_HOST_LAUNCHER", str(launcher))
    process = subprocess.Popen(
        [sys.executable, "-I", str(SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        session = Session(process)
        assert session.request(
            0, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}}
        )["capabilities"] == {"tools": {}}
        session.send({"method": "notifications/initialized"})
        yield session
    finally:
        process.kill()
        process.wait()
        process.stdin.close()
        process.stdout.close()


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

    def call(self, id: int, arguments: dict) -> None:
        self.send(
            {
                "id": id,
                "method": "tools/call",
                "params": {
                    "name": "run",
                    "arguments": arguments,
                    "_meta": {"threadId": "codex-thread"},
                },
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
            {"type": "text", "text": f"{tmp_path}|codex-thread|page claim page|text"},
            {"type": "text", "text": "refused\n"},
            {"type": "text", "text": "exit status 3"},
        ],
        "isError": True,
    }


def test_a_call_that_hangs_holds_up_no_other_and_ends_when_cancelled(server, tmp_path):
    """A command that outlives Codex's tool timeout, such as a `leaf wait` that
    finds no input, leaves later calls answered, and Codex's cancellation ends it
    rather than leaving it holding the session's wait."""
    server.call(1, {"args": ["wait"], "cwd": str(tmp_path)})
    server.call(2, {"args": ["page", "check"], "cwd": str(tmp_path)})
    assert server.receive()["id"] == 2
    server.send({"method": "notifications/cancelled", "params": {"requestId": 1}})
    ended = server.receive()
    assert ended["id"] == 1
    assert ended["result"]["isError"]
