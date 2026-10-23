"""The MCP server Leaf's Codex plugin declares, whose one tool, `run`, runs a `leaf`
command outside Codex's sandbox.

The browser-tab handoff is owned by `skills/leaf/references/harness-codex.md`.
`notes/codex-integration.md` records the separate MCP App panel option.

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
start and keeps it running. It is therefore a standalone stdlib program on the
system's Python, as `state.py`'s SessionEnd entry is, speaking MCP's stdio
transport (one JSON-RPC message per line) itself: it answers `tools/list` about
20 ms after it starts and holds 17 MB, where the MCP SDK's imports alone took
0.3 s and 74 MB. The `leaf` command it runs goes through this install's launcher,
so it runs this tree, and the launcher's `uv` is paid only by a call.

A call runs `leaf` with the user's own access and the arguments the agent chooses,
which can run a package's scripts, so Codex asks the user before the first one,
offering to allow the tool for the session or always (measured at 0.160.0, with
no approval mode declared). The manifest declares none; a plugin can, and Codex
honors `default_tools_approval_mode = "approve"` from a plugin's manifest as from
the user's `[plugins."leaf@leaf".mcp_servers.leaf]`.

Codex starts the server with a short list of variables (PATH, HOME and the like)
plus those the manifest's `env_vars` names, the ones a `leaf` command reads from
its harness or host. A shell command learns its Codex thread from
`CODEX_THREAD_ID`, which Codex sets in its shell alone, so each call passes on the
thread its request's `_meta` names. The call states its working directory, since
the server's own is the plugin's root, and its stdin, since the server's is the
transport.

Each call runs on a thread of its own, so a long command holds up no other. Codex
gives up on a call after the manifest's `tool_timeout_sec` and cancels nothing
(measured at 0.160.0), so the server ends a call's process group shortly before
then, and a `leaf wait` that finds no input returns what it printed rather than
holding the session's wait unseen. A user who sets a shorter timeout for the server
in their own config is not heard: Codex then gives up first, and the command still
ends at the manifest's deadline. The server ends every call's group as it exits,
whether Codex closes its stdin or signals it.

Codex starts the server once per session and never again: once it exits, every
later call fails with "Transport closed" (measured at 0.160.0). So the server
answers every request, a failing one with its error, and exits only when Codex
stops it."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

# This isolated script starts before the managed package exists.
ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "bin" / "leaf"
# Seconds before Codex gives up on a call that the server ends it, so the agent
# reads the command's output and why it ended rather than Codex's timeout.
MARGIN = 10
# Seconds a command ended at its deadline has to exit before it is killed.
GRACE = 5

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
_running: set = set()


def send(message: dict) -> None:
    with _write:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        sys.stdout.flush()


def run(arguments: dict, thread: str | None, deadline: float) -> dict:
    """The tool's result for one call's `arguments`, run for Codex's `thread`."""
    words, cwd = arguments["args"], arguments["cwd"]
    if not (isinstance(words, list) and all(isinstance(w, str) for w in words)):
        return text_result([f"args must be a list of strings, not {words!r}"], 2)
    if not os.path.isabs(cwd):
        return text_result([f"cwd must be an absolute directory, not {cwd!r}"], 2)
    environment = dict(os.environ)
    if thread:
        environment["CODEX_THREAD_ID"] = thread
    stdin = arguments.get("stdin")
    process = subprocess.Popen(
        [str(LAUNCHER), *words],
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    _running.add(process)
    try:
        try:
            stdout, stderr = process.communicate(stdin, timeout=deadline)
        except subprocess.TimeoutExpired:
            end(process)
            try:
                stdout, stderr = process.communicate(timeout=GRACE)
            except subprocess.TimeoutExpired:
                end(process, signal.SIGKILL)
                stdout, stderr = process.communicate()
            stderr += f"leaf ended this command after {deadline:g} s, before Codex's tool timeout\n"
    finally:
        _running.discard(process)
    return text_result([stdout, stderr], process.returncode)


def end(process: subprocess.Popen, signal_number: int = signal.SIGTERM) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal_number)


def text_result(texts: list, status: int) -> dict:
    content = [{"type": "text", "text": text} for text in texts if text]
    if status:
        content.append({"type": "text", "text": f"exit status {status}"})
    return {"content": content, "isError": bool(status)}


def call(request: dict, deadline: float) -> None:
    params = request["params"]
    meta = params.get("_meta", {})
    thread = meta.get("threadId")
    try:
        result = run(params["arguments"], thread, deadline)
    except Exception as error:  # noqa: BLE001 - every failure answers the call
        result = text_result([f"{type(error).__name__}: {error}"], 1)
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


def serve(deadline: float) -> None:
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        if request.get("method") == "tools/call":
            threading.Thread(target=call, args=(request, deadline), daemon=True).start()
            continue
        try:
            send({"id": request["id"], "result": answer(request)})
        except Exception as error:  # noqa: BLE001 - every request is answered
            code = -32601 if isinstance(error, LookupError) else -32603
            send({"id": request["id"], "error": {"code": code, "message": repr(error)}})


def main() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    deadline = manifest["mcpServers"]["leaf"]["tool_timeout_sec"] - MARGIN
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        serve(deadline)
    finally:
        for process in list(_running):
            end(process)


if __name__ == "__main__":
    main()
