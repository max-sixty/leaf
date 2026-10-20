"""The MCP server Leaf's Codex plugin declares, whose one tool, `run`, runs a `leaf`
command outside Codex's sandbox.

Codex's sandbox refuses what a `leaf` command needs: writes to the state home, a
port the user's browser reaches, Chrome for render checks. Unlike Claude Code's, it
leaves a command no road out to a bridge (`bridge.py`): with network off it names
no proxy, and a direct connection to 127.0.0.1 or a Unix socket is refused
(measured at codex-cli 0.160.0). A plugin's MCP server is Codex's own child,
outside the sandbox, so `.codex-plugin/plugin.json` declares this one, and a
sandboxed refusal names its tool (`machine.sandbox_remedy`).

Codex starts a plugin's MCP servers with every session, whether or not it calls
them (measured at 0.160.0: `initialize` and `tools/list` arrive in a session that
calls no tool), so every Codex session with Leaf installed pays this program's
start. It is therefore a standalone stdlib program on the system's Python, as
`state.py`'s SessionEnd entry is, speaking MCP's stdio transport (one JSON-RPC
message per line) itself: it starts in about 20 ms and 17 MB, where the MCP SDK's
imports alone took 0.3 s and 74 MB. The `leaf` command it runs goes through this
install's launcher, so it runs this tree, and the launcher's `uv` is paid only by
a call.

The manifest also declares `default_tools_approval_mode = "approve"`, which Codex
honors from a plugin (measured: the same call under `approval_policy = "never"`
fails as needing approval without it), so a call asks the user nothing; a user's
`[plugins."leaf@leaf".mcp_servers.leaf]` overrides it. A call runs `leaf` with
the user's own access, as Leaf's hooks already do.

Codex starts the server with a short list of variables (PATH, HOME and the like)
plus those the manifest's `env_vars` names, the ones a `leaf` command reads from
its harness: the state home, Codex's home and App Server endpoint, a launch's
session and voice, and the browser. A shell command learns its Codex thread from
`CODEX_THREAD_ID`, which Codex sets in its shell alone, so each call passes on the
thread its request's `_meta` names. The call states its working directory, since
the server's own is the plugin's root, and its stdin, since the server's is the
transport.

Each call runs on a thread of its own, so a command that outlives Codex's tool
timeout, such as a `leaf wait` that finds no input, holds up no later call, and a
cancellation Codex sends ends its process group."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[4] / "bin" / "leaf"

TOOL = {
    "name": "run",
    "description": (
        "Run a `leaf` command outside Codex's sandbox, which refuses what Leaf "
        "needs. Returns its stdout, its stderr and, when it fails, its exit status."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": 'The words after `leaf`, such as ["server", "start", "<page>"].',
            },
            "cwd": {
                "type": "string",
                "description": "The absolute directory to run in: your working directory.",
            },
            "stdin": {
                "type": "string",
                "description": "Text to pipe to the command, as a heredoc would.",
            },
        },
        "required": ["args", "cwd"],
    },
}

_write = threading.Lock()
_running: dict = {}


def send(message: dict) -> None:
    with _write:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        sys.stdout.flush()


def run(request: dict) -> dict:
    """The tool's result for one `tools/call` request."""
    arguments = request["params"]["arguments"]
    cwd = arguments["cwd"]
    if not os.path.isabs(cwd):
        return text_result([f"cwd must be an absolute directory, not {cwd!r}"], 2)
    environment = dict(os.environ)
    if thread := request["params"].get("_meta", {}).get("threadId"):
        environment["CODEX_THREAD_ID"] = thread
    stdin = arguments.get("stdin")
    process = subprocess.Popen(
        [str(LAUNCHER), *arguments["args"]],
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    _running[request["id"]] = process
    try:
        stdout, stderr = process.communicate(stdin)
    finally:
        del _running[request["id"]]
    return text_result([stdout, stderr], process.returncode)


def text_result(texts: list, status: int) -> dict:
    content = [{"type": "text", "text": text} for text in texts if text]
    if status:
        content.append({"type": "text", "text": f"exit status {status}"})
    return {"content": content, "isError": bool(status)}


def call(request: dict) -> None:
    try:
        result = run(request)
    except OSError as error:
        result = text_result([str(error)], 1)
    send({"id": request["id"], "result": result})


def answer(request: dict) -> dict:
    method = request["method"]
    if method == "initialize":
        return {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "leaf", "version": "0"},
        }
    if method == "tools/list":
        return {"tools": [TOOL]}
    if method == "ping":
        return {}
    raise LookupError(method)


def main() -> None:
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            if request.get("method") == "notifications/cancelled":
                process = _running.get(request["params"]["requestId"])
                if process is not None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGTERM)
            continue
        if request.get("method") == "tools/call":
            threading.Thread(target=call, args=(request,), daemon=True).start()
            continue
        try:
            send({"id": request["id"], "result": answer(request)})
        except LookupError:
            send(
                {
                    "id": request["id"],
                    "error": {
                        "code": -32601,
                        "message": f"no method {request['method']}",
                    },
                }
            )


if __name__ == "__main__":
    main()
