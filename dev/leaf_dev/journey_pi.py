"""The `pi` journey: a real Pi session with Leaf's extension, and the steps a user
takes at its terminal.

    uv run leaf-dev journey pi

The suite drives Leaf's Pi extension (`hooks/pi.ts`) with a stand-in for Pi
(`tests/pi_driver.mjs`); this drives it with Pi itself, the version `dev/pi/` pins.
It installs this working tree's payload as a Pi package into a throwaway Pi home
(`pi_home`), whose only login is the host's Codex login, and runs Pi in RPC mode.
The journey is then the terminal: it types the user's turns on Pi's stdin, presses
Escape as Pi's own terminal does (`clear_queue`, then `abort`), and after the
release ask posts the user's comments to the served page as a tab would. It reads the
page's log and claim in process, and stops at the first check that fails.

The steps, in order:

- `setup`: the user asks for a page to review; Pi serves it, and as the run settles
  the extension starts watching the session's pages;
- `release`: the journey's timed ask, sent while Pi is idle, starts a run that
  answers it (`journey.run_journey`);
- `mid-turn`: a comment sent during a shell command is delivered into that run and
  answered before it settles, with no run after it, and the claim holds the run's
  turn open while it goes;
- `escape`: Escape during a shell command closes the turn and leaves Pi idle, and a
  comment sent afterwards starts a run that answers it;
- `held-escape`: a comment held during a shell command is not received before
  Escape, then enters a fresh run and is answered automatically;
- `quit`: closing Pi's stdin ends the session, so its claim on the page is inactive
  and its watch has ended.

Between steps every comment sent so far has exactly one reply and a pickup, the
page's claim names Pi's session with its turn closed, and the watch is running. Pi's
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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import click
from leaf.delivery import pickup_receipts
from leaf.event_log import read_events
from leaf.leases import wait_is_live
from leaf.server import running_server
from leaf.service import claim_is_active, page_claim
from leaf.state import session_record

from leaf_dev import ROOT
from leaf_dev.arms import MODELS, environment, now, pi_home
from leaf_dev.journey import (
    QUIET,
    STEP_LIMIT,
    Isolation,
    Terminal,
    User,
    isolated,
    user_at,
)
from leaf_dev.review_scenario import (
    REQUEST,
    SLEEP,
    USER_TURN,
    prepare,
    require,
    settled,
)

PI_PROJECT = ROOT / "dev" / "pi"
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
        # Whether a run is going, from `agent_start` until it settles, and how many
        # have settled.
        self.running = False
        self.settled = 0
        self.closed_watches = 0
        self.session = self.request("get_state")["sessionId"]

    def _read(self) -> None:
        for line in self.process.stdout:
            self.heard.put(json.loads(line))

    def _hear(self, record: dict) -> None:
        kind = record["type"]
        if kind == "leaf_watch_closed" and record["code"] == 0:
            self.closed_watches += 1
        elif kind == "agent_start":
            self.running = True
        elif kind == "agent_settled":
            self.running = False
            self.settled += 1
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

    def say(self, text: str) -> None:
        """Type one user turn into an idle session."""
        started = self.request("prompt", message=text)
        require(
            started["disposition"] == "started", f"Pi did not start a run: {started}"
        )

    def escape(self) -> None:
        """Press Escape as Pi's terminal does: clear the queued messages, then abort
        the run, which answers once the session is idle."""
        self.request("clear_queue")
        self.request("abort")


def steps(pi: Pi, user: User, page: Path) -> None:
    """The steps after setup, as the module docstring lists them."""
    sent: list[str] = []

    def check() -> dict:
        claim = settled(page, pi.session, {name: user.ids[name] for name in sent})
        require(
            wait_is_live(None, pi.session),
            "no watch holds the session's pages between runs",
        )
        return claim

    started = time.monotonic()
    user.release()
    pi.settle(lambda: True, "the run that answered `release` did not settle")
    sent.append("release")
    turn = check()["turn"]
    user.passed("release", started)

    started = time.monotonic()
    before = pi.settled
    pi.say(USER_TURN)
    pi.await_command(SLEEP, "the user's run did not start its command")
    claim = page_claim(page)
    require(
        claim["turn"] != turn and claim["turn_closed"] is None,
        "the claim does not hold the user's run open",
    )
    turn = claim["turn"]
    mid_turn = user.comment("mid-turn")
    pi.until(pi.idle, "the user's run did not settle")
    require(
        user.answered("mid-turn"),
        "the user's run settled without answering the comment sent during it",
    )
    require(
        any(
            event["turn"] == turn
            for event in pickup_receipts(
                read_events(page), phase="opened", input_id=mid_turn
            )
        ),
        f"the comment was not delivered into the user's turn {turn}",
    )
    pi.settle(lambda: True, "the session did not settle")
    require(
        pi.settled == before + 1,
        "the comment sent during the user's run started another run",
    )
    sent.append("mid-turn")
    check()
    user.passed("mid-turn", started)

    started = time.monotonic()
    pi.say(USER_TURN)
    pi.await_command(SLEEP, "the user's run did not start its command")
    pi.escape()
    require(not pi.running, "the run went on after Escape")
    before = pi.settled
    pi.hear(QUIET)
    require(
        pi.settled == before and not pi.running,
        "Pi started a run after Escape with no new input",
    )
    check()
    user.comment("escape")
    pi.settle(lambda: user.answered("escape"), "`escape` was not answered")
    sent.append("escape")
    check()
    user.passed("escape", started)

    started = time.monotonic()
    pi.say(USER_TURN)
    pi.await_command(SLEEP, "the user's run did not start its command")
    interrupted_turn = page_claim(page)["turn"]
    closed_watches = pi.closed_watches
    held = user.comment("held-escape")
    # Pi's watch hears during the tool, but `turn_end` has not put that input
    # into context yet. Escape clears the queued handoff, so the replacement
    # watch must deliver it into a fresh run, not mistake a log look for pickup.
    pi.until(
        lambda: not wait_is_live(None, pi.session),
        "the watch did not hear held input",
    )
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
        not pickup_receipts(read_events(page), phase="opened", input_id=held),
        "the held input already entered the run before Escape",
    )
    pi.escape()
    pi.settle(
        lambda: user.answered("held-escape"),
        "held input was stranded after Escape",
    )
    require(
        any(
            event["turn"] != interrupted_turn
            for event in pickup_receipts(
                read_events(page), phase="opened", input_id=held
            )
        ),
        "held input did not enter a fresh turn after Escape",
    )
    sent.append("held-escape")
    check()
    user.passed("held-escape", started)

    started = time.monotonic()
    pi.process.stdin.close()
    try:
        pi.process.wait(timeout=STEP_LIMIT)
    except subprocess.TimeoutExpired:
        raise click.ClickException("Pi did not exit when its stdin closed") from None
    require(
        session_record(pi.session)["ended"] is not None,
        "Pi's session ended without Leaf's SessionEnd",
    )
    require(
        not claim_is_active(page_claim(page)),
        "the ended session's claim on the page is still active",
    )
    require(not wait_is_live(None, pi.session), "the ended session's watch still runs")
    user.passed("quit", started)


@contextmanager
def answering(browser) -> Iterator[tuple[User, Callable]]:
    """The user at the page a Pi session serves, once it has, and the steps that
    follow."""
    subprocess.run(
        ["npm", "ci", "--prefix", str(PI_PROJECT), "--silent"],
        check=True,
    )
    executable = PI_PROJECT / "node_modules" / ".bin" / "pi"

    def isolated_environment(place: Isolation) -> dict[str, str]:
        return environment(
            XDG_STATE_HOME=str(place.state),
            PI_CODING_AGENT_DIR=str(pi_home(place.root / "pi-home")),
            PI_SKIP_VERSION_CHECK="1",
            PI_TELEMETRY="0",
        )

    with isolated("pi", isolated_environment) as place:
        prepare(ROOT, place.state, place.page)
        subprocess.run(
            [executable, "install", str(place.payload)], check=True, capture_output=True
        )
        pi = Pi(executable, place.work, place.evidence / "pi.log")
        try:
            started = time.monotonic()
            pi.say(REQUEST)
            pi.settle(
                lambda: (
                    running_server(place.page) is not None
                    and wait_is_live(None, pi.session)
                ),
                "the setup run did not serve the page and start the watch",
            )
            settled(place.page, pi.session, {})
            with user_at(browser, place, pi, started) as user:
                yield user, lambda: steps(pi, user, place.page)
        finally:
            # A failed step leaves Pi running. Quitting lets the extension stop its
            # watch, which a killed Pi would leave behind.
            if not pi.process.stdin.closed:
                pi.process.stdin.close()
            try:
                pi.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pi.process.kill()
