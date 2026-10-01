"""Run one real Codex task through Leaf's App Server adapter and check what it leaves.

    uv run leaf-dev verify-codex-task

The suite drives the adapter with scripted App Server messages; this drives it with
Codex itself. It installs this working tree's plugin payload (`extract_payload`) into
a throwaway Codex home (`codex_home`), trusts the plugin's hooks there, and starts a
private App Server the way `leaf codex launch` does (`private_app_server`). The command
is then the terminal: it opens the task, types the user's turns, and posts the user's
comments to the served page as a tab would. It reads the page's log and claim in
process, and stops at the first check that fails.

The journey, in order:

- `setup`: the user asks for a page to review; the agent serves it and hands it to
  the adapter with `leaf codex start`, whose App Server its environment names;
- `idle`: a comment posted while the task is idle is answered in a turn Leaf starts;
- `mid-turn`: a comment posted while a turn the user typed is running is answered
  once, in that turn or after it;
- `restart`: with the adapter killed, the user's next turn ends with the agent having
  started it again, and a comment posted afterwards is answered.

After each step every comment posted so far has exactly one reply and a pickup, and
the page's claim names the task's last turn, closed. The claim's turn is App Server's
id for that turn, so the prompt hook and the adapter agree on one identity, and a
turn that ended stays closed. During the user's own turn the claim names that turn.

It spends a few model turns on the host's Codex login, so CI does not run it. The
task, its page and its state home live in a temporary directory, removed when every
check passes and kept, with its path printed, when one fails.
"""

import itertools
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import click
import psutil
from leaf.codex import app_server_connect, app_server_handshake, app_server_request
from leaf.codex_adapter import private_app_server
from leaf.event_log import read_events
from leaf.leases import adapter_is_live
from leaf.server import running_server
from leaf.service import page_claim

from leaf_dev import ROOT
from leaf_dev.harness import (
    PageClient,
    codex_home,
    environment,
    extract_payload,
    run_leaf,
)

# How long one step may take, and how long it has to stay settled before its
# checks count: a second reply lands after the turn that wrote the first.
STEP_LIMIT = 300
QUIET = 10
PROMPT = (
    "I wrote a Leaf page at ./page. Serve it so I can review it in my browser, "
    "and handle the comments I leave on it."
)
USER_TURN = "Run `sleep 20` in the shell, then reply with the single word done."
RESTART_TURN = "Reply with the single word OK."
COMMENTS = {
    "idle": ("triage-lede", "Which of these items actually blocks the release?"),
    "mid-turn": ("triage-why", "Is the migration the only blocker, or the first?"),
    "restart": ("triage-lede", "Anything else I should check before we ship?"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise click.ClickException(message)


class Task:
    """The task's terminal: one App Server connection that opens the task, types the
    user's turns, and hears every turn the task runs, Leaf's included, since every
    client of a thread receives what it says."""

    def __init__(self, endpoint: str) -> None:
        self.socket = app_server_connect(endpoint)
        self.ids = itertools.count()
        self.thread = ""
        self.started: list[str] = []
        self.running: set[str] = set()
        self.commands: list[str] = []
        app_server_handshake(
            self.socket, next(self.ids), "verify", "Verify", self._hear
        )

    def _hear(self, message: dict) -> None:
        method, params = message.get("method"), message.get("params") or {}
        if method == "turn/started":
            self.started.append(params["turn"]["id"])
            self.running.add(params["turn"]["id"])
        elif method == "turn/completed":
            self.running.discard(params["turn"]["id"])
        elif (
            method == "item/completed" and params["item"]["type"] == "commandExecution"
        ):
            self.commands.append(params["item"]["command"])

    def request(self, method: str, params: dict) -> dict:
        return app_server_request(
            self.socket, method, next(self.ids), params, self._hear
        )

    def listen(self, seconds: float) -> None:
        """Hear whatever the task says for `seconds`."""
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            try:
                raw = self.socket.recv(timeout=left)
            except TimeoutError:
                return
            self._hear(json.loads(raw))

    def say(self, text: str) -> str:
        """Type one user turn and return its id."""
        started = self.request(
            "turn/start",
            {"threadId": self.thread, "input": [{"type": "text", "text": text}]},
        )
        return started["turn"]["id"]

    def settle(self, done: Callable[[], bool], what: str) -> None:
        """Hear the task until it is idle with `done` true, and still is QUIET
        seconds later."""
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
    require(bool(hooks), "Codex lists no hooks for the installed Leaf plugin")
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


def adapter_processes(endpoint: str) -> list[psutil.Process]:
    """The detached adapters carrying delivery over this App Server."""
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if endpoint in (cmdline := process.info["cmdline"] or [])
        and "--app-server" in cmdline
    ]


def attempt(step: str) -> str:
    """The retry key a step's comment is posted under, as long as the log requires."""
    return f"verify-codex-task-{step}"


def comment_id(page: Path, step: str) -> str:
    return next(
        event["id"]
        for event in read_events(page)
        if event["kind"] == "comment" and event.get("attempt") == attempt(step)
    )


def answers(page: Path, step: str) -> list[dict]:
    """The replies that answer one posted comment; a failure receipt is not one."""
    posted = comment_id(page, step)
    return [
        event
        for event in read_events(page)
        if event["kind"] == "reply"
        and event.get("responds") == posted
        and "failure" not in event
    ]


def check(page: Path, task: Task, posted: list[str]) -> None:
    """What holds between steps: each comment answered once and picked up, and the
    claim naming the task's last turn, closed."""
    events = read_events(page)
    for step in posted:
        replies = answers(page, step)
        require(
            len(replies) == 1,
            f"comment `{step}` has {len(replies)} replies, not one",
        )
        posted_id = comment_id(page, step)
        require(
            any(
                event["kind"] == "pickup" and posted_id in event["events"]
                for event in events
            ),
            f"comment `{step}` has a reply but no pickup",
        )
    claim = page_claim(page)
    require(claim is not None, "the page has no claim")
    require(
        claim["id"] == task.thread,
        f"the page is claimed by {claim['id']}, not the task {task.thread}",
    )
    require(
        claim["turn"] == task.started[-1],
        f"the claim names turn {claim['turn']}, not the task's last turn "
        f"{task.started[-1]}",
    )
    require(
        claim["turn_closed"] is not None,
        f"turn {claim['turn']} has ended, but the claim holds it open",
    )


def post(page: Path, step: str) -> None:
    """Post a step's comment as the page's tab does."""
    section, text = COMMENTS[step]
    client = PageClient(running_server(page)["url"])
    client.post(
        {
            "kind": "comment",
            "revision": client.state()["active"]["revision"],
            "attempt": attempt(step),
            "text": text,
            "anchor": {"section": section},
        }
    )


def journey(task: Task, page: Path, endpoint: str) -> None:
    def step(name: str, started: float) -> None:
        click.echo(f"{name}: passed in {time.monotonic() - started:.0f} s")

    started = time.monotonic()
    task.say(PROMPT)
    task.settle(
        lambda: adapter_is_live(task.thread) and running_server(page) is not None,
        "the setup turn did not serve the page and start the adapter",
    )
    require(
        bool(adapter_processes(endpoint)),
        "the adapter is carrying delivery over the queue, not this App Server",
    )
    check(page, task, [])
    step("setup", started)

    started = time.monotonic()
    post(page, "idle")
    task.settle(lambda: bool(answers(page, "idle")), "comment `idle` was not answered")
    check(page, task, ["idle"])
    step("idle", started)

    started = time.monotonic()
    user_turn = task.say(USER_TURN)
    post(page, "mid-turn")
    named, deadline = False, time.monotonic() + STEP_LIMIT
    while (
        user_turn in task.running or user_turn not in task.started
    ) and time.monotonic() < deadline:
        task.listen(0.5)
        named = named or page_claim(page)["turn"] == user_turn
    require(named, f"the claim never named the user's turn {user_turn} while it ran")
    task.settle(
        lambda: bool(answers(page, "mid-turn")),
        "comment `mid-turn` was not answered",
    )
    check(page, task, ["idle", "mid-turn"])
    step("mid-turn", started)

    started = time.monotonic()
    for process in adapter_processes(endpoint):
        process.kill()
        process.wait(10)
    require(
        not adapter_is_live(task.thread), "the killed adapter still holds its lease"
    )
    task.say(RESTART_TURN)
    task.settle(
        lambda: adapter_is_live(task.thread),
        "the agent did not start the adapter again",
    )
    check(page, task, ["idle", "mid-turn"])
    post(page, "restart")
    task.settle(
        lambda: bool(answers(page, "restart")),
        "comment `restart` was not answered",
    )
    check(page, task, ["idle", "mid-turn", "restart"])
    step("restart", started)


@click.command()
def verify_codex_task() -> None:
    """Run one Codex task through Leaf's App Server adapter and check what it wrote.

    Spends a few model turns on the host's Codex login. The task and its page live in
    a temporary directory, removed when every check passes and kept, with its path
    printed, when one fails.
    """
    codex = shutil.which("codex")
    if codex is None:
        raise click.ClickException("cannot find the `codex` executable on PATH")
    # Outside any repository, so the task loads no project instructions or skills.
    root = Path(tempfile.mkdtemp(prefix="leaf-verify-codex-"))
    state, work = root / "state", root / "work"
    work.mkdir()
    page = work / "page"
    payload = root / "plugin"
    extract_payload(payload)
    home = codex_home(root / "codex-home")
    # This process reads the page and claim in the state home the task writes, and
    # every child inherits the throwaway Codex home, never the session running this.
    isolated = environment(XDG_STATE_HOME=str(state), CODEX_HOME=str(home))
    os.environ.clear()
    os.environ.update(isolated)
    run_leaf(ROOT, state, "page", "init", str(page), check=True)
    shutil.copy(ROOT / "examples" / "triage-board.html", page / "index.html")
    run_leaf(
        ROOT,
        state,
        "version",
        "stamp",
        str(page),
        "--text",
        "Release triage for review.",
        check=True,
    )
    passed = False
    try:
        with private_app_server(codex) as endpoint:
            task = Task(endpoint)
            try:
                install_plugin(task, payload, work)
                task.thread = task.request(
                    "thread/start",
                    {
                        "cwd": str(work),
                        "approvalPolicy": "never",
                        "sandbox": "danger-full-access",
                    },
                )["thread"]["id"]
                journey(task, page, endpoint)
                passed = True
            finally:
                task.socket.close()
                for process in adapter_processes(endpoint):
                    process.kill()
                run_leaf(ROOT, state, "server", "stop", str(page))
    finally:
        if passed:
            shutil.rmtree(root)
        else:
            click.echo(f"Kept the task, its page and its state home in {root}")
    click.echo("Every check passed.")
