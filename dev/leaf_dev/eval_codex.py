"""Isolated, resumable Codex sessions for the shared eval harness.

The native CLI installs the payload before App Server starts; the task then trusts
its hooks. App Server persists its thread under the child's home so a later phase
resumes that exact conversation.
Its complete notifications are retained beside the normalized eval trace. The
normalization exposes actual command execution, replies, hook output, subagent
activity, and turn starts and completions; it neither invents hooks nor acknowledges
a Leaf delivery itself. Subagent activity retains the native item, which describes
activity and identity, not the private brief.
"""

import json
import shutil
import threading
import time
from collections import deque
from contextlib import ExitStack
from pathlib import Path

from websockets.exceptions import ConnectionClosed

from leaf.codex import private_app_server
from leaf_dev.codex_task import Task, trust_plugin_hooks


def records_for(message: dict, session: str, final: str) -> list[dict]:
    """Normalize one observed notification at the evidence boundary."""
    method, params = message.get("method"), message.get("params") or {}
    if method == "turn/started":
        return [
            {
                "type": "turn_started",
                "session_id": session,
                "turn_id": params["turn"]["id"],
            }
        ]
    if method == "item/commandExecution/outputDelta":
        return [
            {
                "type": "tool_output",
                "tool_use_id": params["itemId"],
                "turn_id": params["turnId"],
                "output": params["delta"],
            }
        ]
    if method in {"item/started", "item/completed"}:
        item = params["item"]
        if item["type"] == "subAgentActivity":
            return [item] if method == "item/completed" else []
        if item["type"] == "collabAgentToolCall":
            block = (
                {
                    "type": "tool_use",
                    "id": item["id"],
                    "name": item["tool"],
                    "input": {
                        "prompt": item.get("prompt"),
                        "receivers": item["receiverThreadIds"],
                    },
                }
                if method == "item/started"
                else {
                    "type": "tool_result",
                    "tool_use_id": item["id"],
                    "content": json.dumps(item["agentsStates"]),
                    "is_error": item["status"] != "completed",
                }
            )
            return [
                {
                    "type": "assistant" if method == "item/started" else "user",
                    "message": {"content": [block]},
                }
            ]
        if item["type"] == "commandExecution":
            block = (
                {
                    "type": "tool_use",
                    "id": item["id"],
                    "name": "Bash",
                    "input": {"command": item["command"]},
                }
                if method == "item/started"
                else {
                    "type": "tool_result",
                    "tool_use_id": item["id"],
                    "content": item.get("aggregatedOutput") or "",
                    "is_error": item["status"] != "completed"
                    or item.get("exitCode") != 0,
                }
            )
            return [
                {
                    "type": "assistant" if method == "item/started" else "user",
                    "message": {"content": [block]},
                }
            ]
        if item["type"] == "mcpToolCall":
            block = (
                {
                    "type": "tool_use",
                    "id": item["id"],
                    "name": f"mcp__{item['server']}__{item['tool']}",
                    "input": item["arguments"],
                }
                if method == "item/started"
                else {
                    "type": "tool_result",
                    "tool_use_id": item["id"],
                    # A result's content parts are the shape a Claude Code tool
                    # result carries, so readers of either trace read them alike.
                    "content": (item.get("result") or {}).get("content")
                    or json.dumps(item.get("result") or item.get("error")),
                    "is_error": item["status"] != "completed",
                }
            )
            return [
                {
                    "type": "assistant" if method == "item/started" else "user",
                    "message": {"content": [block]},
                }
            ]
        if item["type"] == "functionCallOutput" and method == "item/completed":
            return [
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": item["id"],
                                "tool_name": item["name"],
                                "content": item["output"],
                            }
                        ]
                    },
                }
            ]
        if item["type"] == "userMessage" and method == "item/completed":
            return [{"type": "user", "message": {"content": item["content"]}}]
        if item["type"] == "agentMessage" and method == "item/completed":
            return [
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": item["text"]}]},
                }
            ]
        if item["type"] == "fileChange":
            if method == "item/started":
                return [
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": item["id"],
                                    "name": "ApplyPatch",
                                    "input": {"changes": item["changes"]},
                                }
                            ]
                        },
                    }
                ]
            return [
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": item["id"],
                                "content": json.dumps(item["changes"]),
                                "is_error": item["status"] != "completed",
                            }
                        ]
                    },
                }
            ]
    if method == "hook/completed":
        run = params["run"]
        return [
            {
                "type": "system",
                "subtype": "hook_response",
                "hook_event": run["eventName"],
                "hook_status": run["status"],
                "output": "\n".join(entry["text"] for entry in run["entries"]),
            }
        ]
    if method == "turn/completed":
        turn = params["turn"]
        return [
            {
                "type": "result",
                "session_id": session,
                "turn_id": turn["id"],
                "is_error": turn["status"] != "completed",
                "result": final,
                "error": turn.get("error"),
            }
        ]
    return []


class CodexChild:
    """A private App Server that remains reachable between user turns.

    `close` ends observation after an active turn completes; `limit` bounds the
    entire session, including its idle delivery waits. The production detached
    adapter may open further turns until the driver closes this session.

    Its turns take Leaf's App Server transport: the private server below sets
    `LEAF_CODEX_APP_SERVER` (`private_app_server`). The queue transport the desktop
    app and IDE use runs under `leaf-dev journey codex-queue`.
    """

    transport = "app-server"

    def __init__(
        self,
        cwd,
        prompt,
        *args,
        stderr,
        limit,
        timed_out,
        dirs=(),
        env=None,
        model=None,
    ):
        from leaf_dev.arms import MODELS, codex_home, environment, now, private_program

        self.cwd, self.prompt = cwd, prompt
        self.stderr, self.timed_out = stderr, timed_out
        self.queue, self.outbox, self.closing = deque(), deque(), False
        self.final, self.now, self.model = "", now, model or MODELS["codex"]
        self.usage = None
        self.usage_baseline = None
        self.started_at = time.monotonic()
        self.deadline = threading.Timer(limit, self._give_up)
        options = {}
        values = iter(args)
        for name in values:
            if name not in {
                "--tools",
                "--plugin-dir",
                "--resume",
                "--json-schema",
                "--append-system-prompt",
            }:
                raise ValueError(f"unsupported Codex eval option: {name}")
            options[name] = next(values)
        self.options = options
        # Claude Code's `--json-schema`, which App Server takes as the turn's
        # `outputSchema`; the result then carries the answer as `structured_output`,
        # as Claude Code's does.
        schema = options.get("--json-schema")
        self.schema = json.loads(schema) if schema else None
        home = cwd.with_name(f"{cwd.name}-home")
        home.mkdir(mode=0o700, exist_ok=True)
        temporary = cwd / "tmp"
        temporary.mkdir(exist_ok=True)
        config_home = home / ".codex"
        self.native_sessions = config_home / "sessions"
        if not config_home.exists():
            codex_home(
                config_home,
                'model_reasoning_effort = "medium"\nweb_search = "disabled"\n[features]\nmemories = false\nmulti_agent = true\napps = false\n',
            )
        self.env = environment(
            HOME=str(home),
            CODEX_HOME=str(config_home),
            TMPDIR=str(temporary),
            TMPPREFIX=str(temporary / "zsh"),
            **(env or {}),
        )
        executable = shutil.which("codex")
        if executable is None:
            raise RuntimeError("cannot find the `codex` executable on PATH")
        self.executable = Path(executable)
        self.sandbox = (
            "read-only"
            if self.options.get("--tools") == "Read"
            else "danger-full-access"
        )
        isolated = (
            self.executable
            if self.sandbox == "read-only"
            else private_program(self.executable, home, cwd, *dirs)
        )
        self.server = private_app_server(str(isolated), env=self.env, cwd=str(cwd))

    def _hear(self, message):
        self.raw.write(json.dumps(message) + "\n")
        self.raw.flush()
        params = message.get("params") or {}
        session = getattr(getattr(self, "task", None), "thread", "")
        if session and not self.task.owns(message):
            return
        if message.get("method") == "turn/started":
            self.final = ""
            self.usage = None
            self.usage_baseline = None
            self.started_at = time.monotonic()
        elif message.get("method") == "thread/tokenUsage/updated":
            last = params["tokenUsage"]["last"]
            total = params["tokenUsage"]["total"]
            if self.usage_baseline is None:
                self.usage_baseline = {
                    key: total[key] - last[key]
                    for key in ("inputTokens", "outputTokens")
                }
            self.usage = {
                key: total[key] - self.usage_baseline[key]
                for key in ("inputTokens", "outputTokens")
            }
        if message.get("method") == "item/completed":
            item = params["item"]
            if item["type"] == "agentMessage" and item.get("phase") == "final_answer":
                self.final = item["text"]
        for record in records_for(message, session, self.final):
            if record["type"] == "result":
                record["num_turns"] = 1
                record["duration_ms"] = int((time.monotonic() - self.started_at) * 1000)
                if self.usage is not None:
                    record["usage"] = {
                        "input_tokens": self.usage["inputTokens"],
                        "output_tokens": self.usage["outputTokens"],
                    }
                if self.schema is not None and not record["is_error"]:
                    record["structured_output"] = json.loads(self.final)
            self.queue.append({**record, "harness": "codex", "received_at": self.now()})

    def __enter__(self):
        from leaf_dev.arms import install_codex_plugin

        self.resources = ExitStack()
        try:
            self.raw = self.resources.enter_context(
                self.stderr.with_suffix(".codex.jsonl").open("w")
            )
            payload = self.options.get("--plugin-dir")
            with self.stderr.open("w") as output:
                if payload:
                    install_codex_plugin(
                        self.executable,
                        Path(payload),
                        cwd=self.cwd,
                        env=self.env,
                        output=output,
                    )
            self.task = Task(self.resources.enter_context(self.server)[0], self._hear)
            self.resources.callback(self.task.socket.close)
            if payload:
                trust_plugin_hooks(self.task, self.cwd)
            params = {
                "cwd": str(self.cwd),
                "approvalPolicy": "never",
                "sandbox": self.sandbox,
                "model": self.model,
            }
            if session := self.options.get("--resume"):
                params["threadId"] = session
            if instructions := self.options.get("--append-system-prompt"):
                params["developerInstructions"] = instructions
            self.task.thread = self.task.request(
                "thread/resume" if session else "thread/start", params
            )["thread"]["id"]
            self.task.say(self.prompt, self.schema)
            self.deadline.start()
            return self
        except BaseException:
            self.resources.close()
            raise

    def records(self):
        while True:
            while self.outbox:
                self.task.say(self.outbox.popleft())
            while self.queue:
                yield self.queue.popleft()
            if self.closing and not self.task.running:
                return
            try:
                self.task.receive(0.5)
            except ConnectionClosed:
                if self.closing:
                    return
                raise

    def send(self, text):
        """Send the user's next chat message as a turn of the same thread. The
        thread reading `records` owns the socket, so it starts the turn."""
        self.outbox.append(text)

    def close(self):
        self.closing = True

    def abort(self):
        self._give_up()

    def _give_up(self):
        self.timed_out.touch()
        self.closing = True
        self.task.socket.close()

    def __exit__(self, *exc):
        self.deadline.cancel()
        self.deadline.join()
        self.resources.__exit__(*exc)
