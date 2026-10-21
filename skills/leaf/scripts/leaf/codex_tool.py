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

The agent edits a page's files with its own tools, inside the sandbox, which
refuses a write outside the task's directory and the temporary directories unless
the user's `sandbox_workspace_write.writable_roots` names it ("Agent sandboxes" in
the README). Without the pages directory there, each edit to a page under the state
home asks the user or, under `approval_policy = "never"`, fails (measured at 0.160.0
on macOS, with `apply_patch` and a shell write alike; Linux is untested). The server
declares Codex's `codex/sandbox-state-meta` capability, so each call's `_meta`
carries the calling task's sandbox, and the first call from a task whose sandbox
can't write the pages directory ends with a note giving the user that line. Codex
marks the capability experimental, so a sandbox state this server can't read gives
no note rather than failing the call.

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

ROOT = Path(__file__).resolve().parents[4]
LAUNCHER = ROOT / "bin" / "leaf"
# Seconds before Codex gives up on a call that the server ends it, so the agent
# reads the command's output and why it ended rather than Codex's timeout.
MARGIN = 10
# Seconds a command ended at its deadline has to exit before it is killed.
GRACE = 5
SANDBOX_STATE = "codex/sandbox-state-meta"

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
# The Codex threads already told their sandbox can't write the pages directory.
_told: set = set()


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


def writable_roots(sandbox: dict | None) -> list[Path] | None:
    """The directories the calling task's `sandbox` (its `_meta`'s sandbox state)
    lets it write, or None where it doesn't confine writes or can't be read."""
    try:
        file_system = sandbox["permissionProfile"]["file_system"]
        if file_system["type"] != "restricted":
            return None
        roots = []
        for entry in file_system["entries"]:
            path = entry["path"]
            if entry["access"] != "write":
                continue
            if path["type"] == "path":
                roots.append(Path(path["path"]).resolve())
            elif path["value"]["kind"] == "root":
                return None
        return roots
    except (KeyError, TypeError):
        return None


def pages_note(sandbox: dict | None) -> str | None:
    """Where the calling task's `sandbox` can't write the state home's pages
    directory, a note telling the agent so and giving the user the line that lets
    it; else None."""
    if (roots := writable_roots(sandbox)) is None:
        return None
    from leaf.state import state_home

    pages = state_home() / "pages"
    if any(pages.resolve().is_relative_to(root) for root in roots):
        return None
    config = (
        Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    )
    return (
        f"Codex's sandbox can't write {pages}, where Leaf keeps pages, so Codex "
        "will refuse your edits to a page there or ask the user to approve each "
        "one. Tell the user they can allow them by adding that directory to "
        f"`writable_roots` in the `[sandbox_workspace_write]` table of {config}, "
        f'as "Agent sandboxes" in {ROOT / "README.md"} says:\n\n'
        f'[sandbox_workspace_write]\nwritable_roots = ["{pages}"]\n'
    )


def call(request: dict, deadline: float) -> None:
    params = request["params"]
    meta = params.get("_meta", {})
    thread = meta.get("threadId")
    try:
        result = run(params["arguments"], thread, deadline)
        if thread not in _told and (note := pages_note(meta.get(SANDBOX_STATE))):
            _told.add(thread)
            result["content"].append({"type": "text", "text": note})
    except Exception as error:  # noqa: BLE001 - every failure answers the call
        result = text_result([f"{type(error).__name__}: {error}"], 1)
    send({"id": request["id"], "result": result})


def answer(request: dict) -> dict:
    method = request["method"]
    if method == "initialize":
        return {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {"tools": {}, "experimental": {SANDBOX_STATE: {}}},
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
    # `-I` leaves Leaf's package off the path; `pages_note` reads the state home
    # from it, and only when a sandbox calls.
    sys.path.insert(0, str(ROOT / "skills" / "leaf" / "scripts"))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        serve(deadline)
    finally:
        for process in list(_running):
            end(process)


if __name__ == "__main__":
    main()
