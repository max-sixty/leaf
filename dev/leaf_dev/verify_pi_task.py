"""Run a real Pi session with Leaf's extension and check what it leaves.

    uv run leaf-dev verify-pi-task

The suite drives Leaf's Pi extension (`hooks/pi.ts`) with a stand-in for Pi
(`tests/pi_driver.mjs`); this drives it with Pi itself, the version `dev/pi/` pins.
It installs this working tree's payload as a Pi package into a throwaway Pi home
(`pi_home`), whose only login is the host's Codex login, and runs Pi in RPC mode.
The command is then the terminal: it types the user's turns on Pi's stdin, presses
Escape as Pi's own terminal does (`clear_queue`, then `abort`), and posts the user's
comments to the served page as a tab would. It reads the page's log and claim in
process, and stops at the first check that fails.

The journey, in order:

- `setup`: the user asks for a page to review; Pi serves it, and as the run settles
  the extension starts watching the session's pages;
- `idle`: a comment posted while Pi is idle starts a run that answers it;
- `mid-turn`: a comment posted during a shell command is steered into that run and
  answered before it settles, with no run after it;
- `escape`: Escape during a shell command closes the turn and leaves Pi idle, and a
  comment posted afterwards starts a run that answers it;
- `quit`: closing Pi's stdin ends the session, so its claim on the page is inactive
  and its watch has ended.

Between steps every comment posted so far has exactly one reply and a pickup, the
page's claim names Pi's session with its turn closed, and the watch is running.

It spends a few model turns on the host's Codex login, so CI does not run it. The
session, its page and its state home live in a temporary directory, removed when every
check passes and kept, with its path printed, when one fails.
"""

import itertools
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

import click
from leaf.event_log import read_events
from leaf.leases import wait_is_live
from leaf.server import running_server
from leaf.service import claim_is_active, page_claim
from leaf.state import session_record

from leaf_dev import ROOT
from leaf_dev.arms import MODELS, environment, extract_payload, pi_home, run_leaf
from leaf_dev.codex_task import QUIET, STEP_LIMIT
from leaf_dev.review_scenario import (
    REQUEST,
    answers,
    comment_id,
    post,
    prepare,
    require,
    settled,
)

PI_PROJECT = ROOT / "dev" / "pi"
# Pi's provider for a ChatGPT login, running the model the Codex evals run.
MODEL = f"openai-codex/{MODELS['codex']}"
USER_TURN = (
    "Run `sleep 20` in the shell. Then, in a separate tool call, run "
    "`printf 'verified\\n'`. Then reply with the single word done."
)


class Pi:
    """One Pi session in RPC mode, and the terminal typing into it. Pi reports every
    run the session makes on stdout, including those Leaf's extension starts."""

    def __init__(self, executable: Path, cwd: Path, log: Path) -> None:
        with log.open("w") as stderr:
            self.process = subprocess.Popen(
                [executable, "--mode", "rpc", "--no-context-files", "--model", MODEL],
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
            )
        # Pi's records split only on LF, as a binary pipe's lines do.
        self.records: queue.Queue[dict] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.ids = itertools.count()
        # Whether a run is going, from `agent_start` until it settles, and how many
        # have settled.
        self.running = False
        self.settled = 0
        self.commands: list[str] = []
        self.running_commands: dict[str, str] = {}
        self.session = self.request("get_state")["sessionId"]

    def _read(self) -> None:
        for line in self.process.stdout:
            self.records.put(json.loads(line))

    def _hear(self, record: dict) -> None:
        kind = record["type"]
        if kind == "agent_start":
            self.running = True
        elif kind == "agent_settled":
            self.running = False
            self.settled += 1
        elif kind == "tool_execution_start" and record["toolName"] == "bash":
            self.running_commands[record["toolCallId"]] = record["args"]["command"]
        elif kind == "tool_execution_end" and (
            command := self.running_commands.pop(record["toolCallId"], None)
        ):
            self.commands.append(command)

    def receive(self, seconds: float) -> dict | None:
        """Hear at most one record."""
        try:
            record = self.records.get(timeout=seconds)
        except queue.Empty:
            require(self.process.poll() is None, "Pi exited")
            return None
        self._hear(record)
        return record

    def listen(self, seconds: float) -> None:
        """Hear whatever Pi says for `seconds`."""
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            self.receive(left)

    def request(self, command: str, **fields) -> dict | None:
        """Send one command and return its response's data."""
        sent = f"verify-{next(self.ids)}"
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

    def await_command(self, text: str) -> None:
        """Hear Pi until a shell command containing `text` is running."""
        deadline = time.monotonic() + STEP_LIMIT
        while not any(text in command for command in self.running_commands.values()):
            self.listen(0.5)
            require(
                time.monotonic() < deadline and self.running,
                f"the user's run did not start `{text}`",
            )

    def settle(self, done: Callable[[], bool], what: str) -> None:
        """Hear Pi until it is idle with `done` true through QUIET."""
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


def journey(pi: Pi, page: Path) -> None:
    def check(posted: list[str]) -> dict:
        claim = settled(page, pi.session, posted)
        require(
            wait_is_live(None, pi.session),
            "no watch holds the session's pages between runs",
        )
        return claim

    def step(name: str, started: float) -> None:
        click.echo(f"{name}: passed in {time.monotonic() - started:.0f} s")

    started = time.monotonic()
    pi.say(REQUEST)
    pi.settle(
        lambda: running_server(page) is not None and wait_is_live(None, pi.session),
        "the setup run did not serve the page and start the watch",
    )
    turn = check([])["turn"]
    step("setup", started)

    started = time.monotonic()
    post(page, "idle")
    pi.settle(lambda: bool(answers(page, "idle")), "comment `idle` was not answered")
    check(["idle"])
    step("idle", started)

    started = time.monotonic()
    before = pi.settled
    pi.say(USER_TURN)
    pi.await_command("sleep 20")
    claim = page_claim(page)
    require(
        claim["turn"] != turn and claim["turn_closed"] is None,
        "the claim does not hold the user's run open",
    )
    turn = claim["turn"]
    post(page, "mid-turn")
    deadline = time.monotonic() + STEP_LIMIT
    while pi.running:
        pi.listen(0.5)
        require(time.monotonic() < deadline, "the user's run did not settle")
    require(
        bool(answers(page, "mid-turn")),
        "the user's run settled without answering the comment posted during it",
    )
    posted = comment_id(page, "mid-turn")
    require(
        any(
            event["kind"] == "pickup"
            and event["phase"] == "opened"
            and event["turn"] == turn
            and posted in event["events"]
            for event in read_events(page)
        ),
        f"the comment was not delivered into the user's turn {turn}",
    )
    pi.settle(lambda: True, "the session did not settle")
    require(
        pi.settled == before + 1,
        "the comment posted during the user's run started another run",
    )
    check(["idle", "mid-turn"])
    step("mid-turn", started)

    started = time.monotonic()
    pi.say(USER_TURN)
    pi.await_command("sleep 20")
    pi.escape()
    require(not pi.running, "the run went on after Escape")
    before = pi.settled
    pi.listen(QUIET)
    require(
        pi.settled == before and not pi.running,
        "Pi started a run after Escape with no new input",
    )
    check(["idle", "mid-turn"])
    post(page, "escape")
    pi.settle(
        lambda: bool(answers(page, "escape")), "comment `escape` was not answered"
    )
    check(["idle", "mid-turn", "escape"])
    step("escape", started)

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
    step("quit", started)


@click.command()
def verify_pi_task() -> None:
    """Run a Pi session with Leaf's extension and check what it carries."""
    subprocess.run(
        ["npm", "ci", "--prefix", str(PI_PROJECT), "--silent"],
        check=True,
    )
    executable = PI_PROJECT / "node_modules" / ".bin" / "pi"
    # Outside any repository, so the session loads no project instructions.
    root = Path(tempfile.mkdtemp(prefix="leaf-verify-pi-"))
    state, work = root / "state", root / "work"
    work.mkdir()
    page = work / "page"
    payload = root / "plugin"
    extract_payload(payload)
    home = pi_home(root / "pi-home")
    # This process reads the page and claim in the state home the session writes,
    # and every child inherits the throwaway Pi home, never the session running this.
    inherited = dict(os.environ)
    isolated = environment(
        XDG_STATE_HOME=str(state),
        PI_CODING_AGENT_DIR=str(home),
        PI_SKIP_VERSION_CHECK="1",
        PI_TELEMETRY="0",
    )
    os.environ.clear()
    os.environ.update(isolated)
    passed = False
    try:
        prepare(ROOT, state, page)
        subprocess.run(
            [executable, "install", str(payload)], check=True, capture_output=True
        )
        pi = Pi(executable, work, root / "pi.log")
        try:
            journey(pi, page)
        finally:
            # A failed step leaves Pi running. Quitting lets the extension stop its
            # watch, which a killed Pi would leave behind.
            if not pi.process.stdin.closed:
                pi.process.stdin.close()
            try:
                pi.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pi.process.kill()
            run_leaf(ROOT, state, "server", "stop", str(page))
        passed = True
    finally:
        os.environ.clear()
        os.environ.update(inherited)
        if passed:
            shutil.rmtree(root)
        else:
            click.echo(f"Kept the session, its page and its state home in {root}")
    click.echo("Every check passed.")
