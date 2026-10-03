"""The terminal side of a real Codex task, shared by verification and evals.

App Server owns thread and turn identity. This client hears notifications from
all turns on the thread, including turns started by Leaf's adapter.
"""

import itertools
import json
import time
from collections.abc import Callable
from pathlib import Path

import click
from leaf.codex import app_server_connect, app_server_handshake, app_server_request


STEP_LIMIT = 300
QUIET = 10


class Task:
    """The task's terminal: one App Server connection that opens the task, types the
    user's turns, and hears every turn the task runs, Leaf's included, since every
    client of a thread receives what it says."""

    def __init__(
        self, endpoint: str, on_message: Callable[[dict], None] | None = None
    ) -> None:
        self.on_message = on_message
        self.socket = app_server_connect(endpoint)
        self.ids = itertools.count()
        self.thread = ""
        self.started: list[str] = []
        self.running: set[str] = set()
        self.commands: list[str] = []
        self.running_commands: dict[str, str] = {}
        self.on_final: Callable[[str], None] | None = None
        app_server_handshake(
            self.socket, next(self.ids), "verify", "Verify", self._hear
        )

    def owns(self, message: dict) -> bool:
        """Whether a notification belongs to this thread or is server-wide."""
        params = message.get("params") or {}
        source = params.get("threadId") or params.get("run", {}).get("threadId")
        return not self.thread or not source or source == self.thread

    def _hear(self, message: dict) -> None:
        if self.on_message is not None:
            self.on_message(message)
        method, params = message.get("method"), message.get("params") or {}
        if not self.owns(message):
            return
        if method == "turn/started":
            self.started.append(params["turn"]["id"])
            self.running.add(params["turn"]["id"])
        elif method == "turn/completed":
            self.running.discard(params["turn"]["id"])
        elif method in {"item/started", "item/completed"}:
            item = params["item"]
            if item["type"] == "commandExecution":
                if method == "item/started":
                    self.running_commands[item["id"]] = item["command"]
                else:
                    self.running_commands.pop(item["id"], None)
                    self.commands.append(item["command"])
            elif (
                method == "item/completed"
                and item["type"] == "agentMessage"
                and item.get("phase") == "final_answer"
                and self.on_final is not None
            ):
                self.on_final(params["turnId"])

    def request(self, method: str, params: dict) -> dict:
        return app_server_request(
            self.socket, method, next(self.ids), params, self._hear
        )

    def receive(self, seconds: float) -> None:
        """Hear at most one notification, preserving the driver's chance to act."""
        try:
            raw = self.socket.recv(timeout=seconds)
        except TimeoutError:
            return
        self._hear(json.loads(raw))

    def listen(self, seconds: float) -> None:
        """Hear whatever the task says for `seconds`."""
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            self.receive(left)

    def say(self, text: str) -> str:
        """Type one user turn and return its id."""
        started = self.request(
            "turn/start",
            {"threadId": self.thread, "input": [{"type": "text", "text": text}]},
        )
        return started["turn"]["id"]

    def settle(self, done: Callable[[], bool], what: str) -> None:
        """Hear the task until it is idle with `done` true through QUIET."""
        deadline = time.monotonic() + STEP_LIMIT
        while time.monotonic() < deadline:
            self.listen(0.5)
            if not self.running and done():
                self.listen(QUIET)
                if not self.running and done():
                    return
        raise click.ClickException(
            f"{what} within {STEP_LIMIT} s. The agent's last commands:\n"
            + "\n".join(f"  {command}" for command in self.commands[-8:])
        )


def install_plugin(task: Task, payload: Path, cwd: Path) -> None:
    """Install the payload as the task's Leaf plugin and trust its hooks, which
    Codex otherwise lists and never runs."""
    task.request(
        "plugin/install",
        {
            "pluginName": "leaf",
            "marketplacePath": str(payload / ".agents/plugins/marketplace.json"),
        },
    )
    hooks = [
        hook
        for hook in task.request("hooks/list", {"cwds": [str(cwd)]})["data"][0]["hooks"]
        if hook["pluginId"] == "leaf@leaf"
    ]
    if not hooks:
        raise click.ClickException("Codex lists no hooks for the installed Leaf plugin")
    task.request(
        "config/batchWrite",
        {
            "edits": [
                {
                    "keyPath": "hooks.state",
                    "mergeStrategy": "upsert",
                    "value": {
                        hook["key"]: {"trusted_hash": hook["currentHash"]}
                        for hook in hooks
                    },
                }
            ],
            "reloadUserConfig": True,
        },
    )
