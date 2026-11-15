"""The `pi` journey: a real Pi session with Leaf's extension, and the steps a user
takes at its terminal.

    uv run leaf-dev journey run pi

The suite drives Leaf's Pi extension (`hooks/pi.ts`) with a stand-in for Pi
(`tests/pi_driver.mjs`); this drives it with Pi itself, the version the root
`package.json` pins.
It installs this working tree's payload as a Pi package into a throwaway Pi home
(`pi_home`), whose only login is the host's Codex login, and runs Pi in RPC mode.
The journey is then the terminal: it types the user's turns on Pi's stdin, presses
Escape as Pi's own terminal does (`clear_queue`, then `abort`), and sends the
user's comments at the journey's user end. It reads the page's log and claim in
process, and stops at the first check that fails.

The steps, in order; all but `held-escape` are those more than one harness takes,
as `journey.Terminal` has them:

- `setup`, the extension watching the session's pages as the run settles;
- `release`;
- `mid-turn`;
- `escape`, whose abort closes the claim's turn;
- `held-escape`: a comment held during a shell command is not received before
  Escape, then enters a fresh run and is answered automatically;
- `quit`, by closing Pi's stdin.

After each step the journey requires what every harness must hold between steps
(`journey.Terminal.between`), with the watch as what listens for Pi's session. Pi's
stderr joins the run's evidence. It spends a few model turns on the host's Codex
login, so CI does not run it.
"""

import itertools
import json
import os
import queue
import subprocess
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import MODELS, environment, now, pi_home
from leaf_dev.commands.journey.run import (
    STEP_LIMIT,
    Isolation,
    Terminal,
    User,
    isolated,
    user_at,
)
from leaf_dev.review_scenario import SLEEP, USER_TURN, picked_up, prepare, require

PI = ROOT / "node_modules" / ".bin" / "pi"
# Pi's provider for a ChatGPT login, running the model the Codex evals run.
MODEL = f"openai-codex/{MODELS['codex']}"


class Pi(Terminal):
    """One Pi session in RPC mode, and the terminal typing into it. Pi reports every
    run the session makes on stdout, including those Leaf's extension starts."""

    def __init__(self, executable: Path, cwd: Path, log: Path) -> None:
        super().__init__()
        native_env = dict(os.environ)
        observer = ROOT / "dev" / "leaf_dev" / "pi_watch_observer.mjs"
        native_env["NODE_OPTIONS"] = (
            native_env.get("NODE_OPTIONS", "")
            + f" --import {json.dumps(str(observer))}"
        ).strip()
        with log.open("w") as stderr:
            self.process = subprocess.Popen(
                [executable, "--mode", "rpc", "--no-context-files", "--model", MODEL],
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                env=native_env,
            )
        # Pi's records split only on LF, as a binary pipe's lines do.
        self.heard: queue.Queue[dict] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.ids = itertools.count()
        # Whether a run is going, from `agent_start` until it settles.
        self.running = False
        self.closed_watches = 0
        # The output of the response the next `turn_end` closes.
        self.output_tokens: int | None = None
        state = require(self.request("get_state"), "Pi returned no state")
        self.session = state["sessionId"]

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.heard.put(json.loads(line))

    def _hear(self, record: dict) -> None:
        kind = record["type"]
        if kind == "leaf_watch_closed" and record["code"] == 0:
            self.closed_watches += 1
        elif kind == "agent_start":
            self.running = True
            self.trace.append({"type": "turn_start", "received_at": now()})
        elif kind == "agent_settled":
            self.running = False
            self.trace.append({"type": "turn_end", "received_at": now()})
        elif kind == "tool_execution_start":
            if record["toolName"] == "bash":
                self.running_commands[record["toolCallId"]] = record["args"]["command"]
            call = {
                "type": "tool_use",
                "id": record["toolCallId"],
                "name": record["toolName"],
                "input": record["args"],
            }
            self.trace.append(
                {
                    "type": "assistant",
                    "message": {"content": [call]},
                    "received_at": now(),
                }
            )
        elif kind == "message_start" and record["message"]["role"] == "assistant":
            # Pi starts an assistant message on the stream's first event.
            self.trace.append({"type": "first_output", "received_at": now()})
        elif kind == "message_end" and record["message"]["role"] == "assistant":
            self.output_tokens = record["message"]["usage"]["output"]
        elif kind == "turn_end":
            # One assistant response and the tool calls it started have finished.
            self.trace.append(
                {
                    "type": "model_response",
                    "outputTokens": self.output_tokens,
                    "received_at": now(),
                }
            )
            self.output_tokens = None
        elif kind == "tool_execution_end":
            if command := self.running_commands.pop(record["toolCallId"], None):
                self.commands.append(command)
            result = {"type": "tool_result", "tool_use_id": record["toolCallId"]}
            self.trace.append(
                {"type": "user", "message": {"content": [result]}, "received_at": now()}
            )

    def receive(self, seconds: float) -> dict | None:
        """Hear at most one record."""
        try:
            record = self.heard.get(timeout=seconds)
        except queue.Empty:
            require(self.process.poll() is None, "Pi exited")
            return None
        self._hear(record)
        return record

    def hear(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            self.receive(left)

    def idle(self) -> bool:
        return not self.running

    def request(self, command: str, **fields) -> dict | None:
        """Send one command and return its response's data."""
        sent = f"journey-{next(self.ids)}"
        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps({"id": sent, "type": command, **fields}).encode() + b"\n"
        )
        self.process.stdin.flush()
        deadline = time.monotonic() + STEP_LIMIT
        while time.monotonic() < deadline:
            record = self.receive(0.5)
            if record and record["type"] == "response" and record.get("id") == sent:
                require(record["success"], f"Pi refused `{command}`: {record}")
                return record.get("data")
        raise click.ClickException(f"Pi did not answer `{command}`")

    def work(self, turn: str = USER_TURN) -> None:
        self.say(turn)
        self.await_command(SLEEP, "the user's run did not start its command")

    def say(self, text: str) -> None:
        """Type one user turn into an idle session."""
        started = self.request("prompt", message=text)
        assert started is not None
        require(
            started["disposition"] == "started", f"Pi did not start a run: {started}"
        )

    def press_escape(self) -> None:
        """Press Escape as Pi's terminal does: clear the queued messages, then abort
        the run, which answers once the session is idle."""
        self.request("clear_queue")
        self.request("abort")

    def leave(self) -> None:
        """Close Pi's stdin, as quitting its terminal does."""
        assert self.process.stdin is not None
        self.process.stdin.close()
        try:
            self.process.wait(timeout=STEP_LIMIT)
        except subprocess.TimeoutExpired:
            raise click.ClickException(
                "Pi did not exit when its stdin closed"
            ) from None


def steps(pi: Pi, user: User, page: Path) -> None:
    """The steps after setup, as the module docstring lists them, each sending a
    comment of its own name."""

    def step(name: str, started: float) -> None:
        pi.passed(user, page, name, started, name)

    started = time.monotonic()
    pi.release(user)
    step("release", started)

    started = time.monotonic()
    pi.mid_turn(user, page)
    step("mid-turn", started)

    started = time.monotonic()
    require(not pi.escape(user, page), "escape: Pi's abort left the claim's turn open")
    step("escape", started)

    started = time.monotonic()
    interrupted_turn = pi.user_turn(page)
    closed_watches = pi.closed_watches
    held = user.comment("held-escape")
    # Pi's watch hears during the tool, but `turn_end` has not put that input
    # into context yet. Escape clears the queued handoff, so the replacement
    # watch must deliver it into a fresh run, not mistake a log look for pickup.
    pi.until(lambda: not pi.listening(), "the watch did not hear held input")
    pi.until(
        lambda: pi.closed_watches != closed_watches,
        "Leaf did not complete the held-input watch notification",
    )
    require(
        pi.running
        and any(SLEEP in command for command in pi.running_commands.values()),
        "the held-input tool ended before Escape",
    )
    require(
        not picked_up(page, held),
        "the held input already entered the run before Escape",
    )
    pi.press_escape()
    pi.settle(
        lambda: user.answered("held-escape"),
        "held input was stranded after Escape",
    )
    require(
        any(turn != interrupted_turn for turn in picked_up(page, held)),
        "held input did not enter a fresh turn after Escape",
    )
    step("held-escape", started)

    started = time.monotonic()
    pi.quit(page)
    user.passed("quit", started)


@contextmanager
def answering(browser) -> Generator[tuple[User, Callable]]:
    """The user at the page a Pi session serves, once it has, and the steps that
    follow."""

    def isolated_environment(place: Isolation) -> dict[str, str]:
        env = environment(
            XDG_STATE_HOME=str(place.state),
            PI_CODING_AGENT_DIR=str(pi_home(place.root / "pi-home")),
            PI_SKIP_VERSION_CHECK="1",
            PI_TELEMETRY="0",
        )
        # The page server titles a thread through the `pi` on PATH.
        return {**env, "PATH": f"{PI.parent}{os.pathsep}{env['PATH']}"}

    with isolated("pi", isolated_environment) as place:
        prepare(ROOT, place.state, place.page)
        subprocess.run(
            [PI, "install", str(place.payload)], check=True, capture_output=True
        )
        pi = Pi(PI, place.work, place.evidence / "pi.log")
        try:
            started = time.monotonic()
            pi.setup(place.page)
            with user_at(browser, place, pi, started) as user:
                yield user, lambda: steps(pi, user, place.page)
        finally:
            # A failed step leaves Pi running. Quitting lets the extension stop its
            # watch, which a killed Pi would leave behind.
            assert pi.process.stdin is not None
            if not pi.process.stdin.closed:
                pi.process.stdin.close()
            try:
                pi.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pi.process.kill()
