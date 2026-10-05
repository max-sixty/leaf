"""Isolated, resumable Codex sessions for the shared eval harness.

The real App Server runs the payload's plugin and trusted hooks. It persists its
thread under the child's home so a later phase resumes that exact conversation.
Its complete notifications are retained beside the normalized eval trace. The
normalization exposes actual command execution, replies, hook output and turn
completion; it neither invents hooks nor acknowledges a Leaf delivery itself.
"""

import json
import shutil
import sys
import threading
import time
from collections import deque
from pathlib import Path

from leaf.codex_adapter import private_app_server
from websockets.exceptions import ConnectionClosed

from leaf_dev.codex_task import Task, install_plugin


def records_for(message: dict, session: str, final: str) -> list[dict]:
    """Normalize one observed notification at the evidence boundary."""
    method, params = message.get("method"), message.get("params") or {}
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
    """

    def __init__(self, cwd, prompt, *args, stderr, limit, timed_out, dirs=(), env=None):
        from leaf_dev.arms import MODELS, codex_home, environment, now

        self.cwd, self.prompt = cwd, prompt
        self.stderr, self.timed_out = stderr, timed_out
        self.queue, self.closing = deque(), False
        self.final, self.now, self.model = "", now, MODELS["codex"]
        self.usage = None
        self.usage_baseline = None
        self.started_at = time.monotonic()
        self.deadline = threading.Timer(limit, self._give_up)
        options = {}
        values = iter(args)
        for name in values:
            if name not in {"--tools", "--plugin-dir", "--resume"}:
                raise ValueError(f"unsupported Codex eval option: {name}")
            options[name] = next(values)
        self.options = options
        home = cwd.with_name(f"{cwd.name}-home")
        home.mkdir(mode=0o700, exist_ok=True)
        config_home = home / ".codex"
        if not config_home.exists():
            codex_home(
                config_home,
                'model_reasoning_effort = "medium"\nweb_search = "disabled"\n[features]\nmemories = false\nmulti_agent = true\napps = false\n',
            )
        isolated = environment(
            HOME=str(home), CODEX_HOME=str(config_home), **(env or {})
        )
        executable = shutil.which("codex")
        if executable is None:
            raise RuntimeError("cannot find the `codex` executable on PATH")
        self.server = private_app_server(executable, env=isolated)

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
            self.queue.append({**record, "harness": "codex", "received_at": self.now()})

    def __enter__(self):
        self.stderr.write_text("")
        self.raw = self.stderr.with_suffix(".codex.jsonl").open("w")
        try:
            self.task = Task(self.server.__enter__(), self._hear)
            if payload := self.options.get("--plugin-dir"):
                install_plugin(self.task, Path(payload), self.cwd)
            params = {
                "cwd": str(self.cwd),
                "approvalPolicy": "never",
                "sandbox": "read-only"
                if self.options.get("--tools") == "Read"
                else "danger-full-access",
                "model": self.model,
            }
            if session := self.options.get("--resume"):
                params["threadId"] = session
            self.task.thread = self.task.request(
                "thread/resume" if session else "thread/start", params
            )["thread"]["id"]
            self.task.say(self.prompt)
            self.deadline.start()
            return self
        except BaseException:
            self.server.__exit__(*sys.exc_info())
            self.raw.close()
            raise

    def records(self):
        while True:
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

    def close(self):
        self.closing = True

    def _give_up(self):
        self.timed_out.touch()
        self.closing = True
        self.task.socket.close()

    def __exit__(self, *exc):
        self.deadline.cancel()
        self.task.socket.close()
        self.server.__exit__(*exc)
        self.raw.close()
