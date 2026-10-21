"""The `claude-code` journey: a real interactive Claude Code session with Leaf's
plugin, and the steps a user takes at its terminal.

    uv run leaf-dev journey claude-code

The suite stands in for Claude Code around Leaf's hooks (`hooks.json`, and
`tests/claude_code_driver.mjs` for the hooks module); this runs Claude Code itself,
in its terminal interface, with this working tree's payload as its plugin
(`--plugin-dir`) under a throwaway home (`arms.claude_home`) whose only content is
the host's login. `--sandbox` runs the session's shell commands in Claude Code's sandbox, configured
as the README asks a sandboxed user to configure it.
The journey is then the user: it types into the session through a tmux pane,
presses Escape, answers its permission prompts, and sends its comments at the
journey's user end. It reads the page's log and claim in process, and stops at the
first check that fails.

The session runs in Claude Code's default permission mode, as a user's does. Every
tool is allowed, but Claude Code still asks before a command it reads as touching a
sensitive file, such as one under the plugin; the journey answers Yes and records
the prompt in the step (`ClaudeCode.approve`). Bypassing permissions instead would
change what is under test: Claude Code then holds admission's nudge, which reaches
the session as a message from another session (`crossSessionInbound`), unread.

The steps, in order:

- `setup`: the user asks for a page to review; Claude Code serves it, and a watch
  holds the session's pages once its turn ends;
- `release`: the journey's timed ask, sent while the session is idle, opens a turn
  that answers it (`journey.run_journey`);
- `mid-turn`: the working case's ask (`journey.CASES`), sent during a shell
  command, is picked up in that turn and recorded on the page; its PostToolBatch
  context carries the exact input before another model call, rather than waiting
  for Stop;
- `ending`: a comment sent during a shell command wakes the watch, and one sent
  after that pickup enters the same turn at its next tool boundary while no watch
  runs;
- `escape`: Escape during a shell command ends the turn; a comment sent afterwards
  opens a turn that answers it;
- `woken`: a comment sent during a shell command wakes the watch, and Escape ends
  that turn while the command still runs, before the turn reads the comment at its
  next tool boundary. The watch after Escape wakes for that comment and a turn of
  its own answers it; a comment sent afterwards is answered too;
- `quit`: `/exit` ends the session, so its claim on the page is inactive and its
  watch has ended.

Between steps every comment sent so far has exactly one reply and a pickup, the
page's claim names the session with its turn closed, no Stop hook has continued a
turn with input, so each turn ends on its own answer, and no delivery shows in the
terminal. Escape closes the turn and a watch runs after each turn, an interrupted
one included; Claude Code drops the prompt that watch wakes the stopped session
with, so the page nudges it.

A step with comments also prints whether the page nudged the session, and a step
with an Escape whether it left the turn open, a watch running, and what the page's
status read. The session's
screen at the end of each step and Claude Code's debug log join the run's evidence.
It needs tmux, and spends a few model turns on the host's Claude Code login, so CI
does not run it.
"""

import json
import os
import shlex
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import click
import psutil
from leaf.delivery import DELIVERY, pickup_receipts
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.hook_transport import INLINE_OPENING, POINTED_OPENING
from leaf.leases import wait_is_live
from leaf.server import running_server
from leaf.service import claim_is_active, page_claim
from leaf.state import session_record

from leaf_dev import ROOT
from leaf_dev.arms import MODELS, claude_environment, claude_home, run_leaf
from leaf_dev.commands.journey import Isolation, Terminal, User, isolated, user_at
from leaf_dev.reply_phases import claude_code_records
from leaf_dev.review_scenario import (
    REQUEST,
    SLEEP,
    USER_TURN,
    prepare,
    require,
    settled,
)


class ClaudeCode(Terminal):
    """One interactive Claude Code session in a tmux pane, and the user at it."""

    def __init__(self, place: Isolation, argv: list[str], env: dict) -> None:
        super().__init__()
        self.pane = f"leaf-journey-claude-code-{os.getpid()}"
        self.home = place.root / "home"
        self.exited, self.kept = place.root / "exited", place.evidence / "screen.txt"
        self.session: str | None = None
        # The environment's values reach the pane through tmux, so no file holds
        # them; the script names them, and drops whatever else the tmux server's
        # own environment adds.
        script = place.root / "claude.sh"
        script.write_text(
            f"cd {shlex.quote(str(place.work))}\n"
            # Claude Code reads its directory from the shell's PWD.
            f"keep=' {' '.join(env)} PWD '\n"
            "for name in $(compgen -e); do\n"
            '  [[ $keep == *" $name "* ]] || unset "$name" 2> /dev/null\n'
            "done\n"
            f"{shlex.join(argv)} 2> {shlex.quote(str(place.evidence / 'stderr.txt'))}\n"
            f"echo $? > {shlex.quote(str(self.exited))}\n"
        )
        assignments = [arg for item in env.items() for arg in ("-e", "=".join(item))]
        self.tmux("new-session", "-d", "-s", self.pane, "-x", "200", "-y", "50",
                  "-c", str(place.work), *assignments,
                  f"bash {shlex.quote(str(script))}")  # fmt: skip
        try:
            self.until(
                lambda: "? for shortcuts" in self.screen() or "❯" in self.screen(),
                "Claude Code did not start",
            )
        except BaseException:
            self.close()
            raise

    def tmux(self, *args: str) -> str:
        return subprocess.run(
            ["tmux", *args], capture_output=True, text=True, check=False
        ).stdout

    def screen(self) -> str:
        return self.tmux("capture-pane", "-p", "-t", self.pane)

    def shown(self) -> str:
        """All the pane still holds, its history included."""
        return self.tmux("capture-pane", "-p", "-S", "-", "-t", self.pane)

    def keep(self, label: str) -> None:
        """Add the pane's screen to the evidence. Claude Code clears what scrolls
        off, so each step keeps its own."""
        if shown := self.shown():
            with self.kept.open("a") as kept:
                kept.write(f"──── {label} ────\n{shown}\n")

    def say(self, text: str) -> None:
        """Type one prompt and send it. An Escape puts the interrupted prompt back in
        the box, so the user clears what it holds first (Ctrl+U)."""
        boxes = [line for line in self.screen().splitlines() if line.startswith("❯")]
        if boxes and boxes[-1].removeprefix("❯").strip():
            self.tmux("send-keys", "-t", self.pane, "C-u")
        self.tmux("send-keys", "-t", self.pane, "-l", text)
        time.sleep(0.5)
        self.tmux("send-keys", "-t", self.pane, "Enter")

    def escape(self, ended: Callable[[], bool]) -> None:
        """Press Escape until `ended` says the turn has, waiting up to 5 s after
        each press before pressing again. A press after the turn ended does harm:
        on an idle prompt it opens Claude Code's rewind menu, and otherwise it
        interrupts the turn a watch or a nudge opened next, which can start before
        Claude Code's record reads idle."""
        for _ in range(3):
            self.tmux("send-keys", "-t", self.pane, "Escape")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if ended():
                    return
                time.sleep(0.25)
        raise click.ClickException(f"the turn went on after Escape\n{self.screen()}")

    def state(self) -> str | None:
        """The turn's state in Claude Code's own record (`live_turn`)."""
        turn = ClaudeCodeHarness(session=self.session, agent="Claude").live_turn()
        return None if turn is None else turn["state"]

    def idle(self) -> bool:
        """Whether Claude Code's own record says no turn runs."""
        return self.state() == "idle"

    def sleeping(self) -> bool:
        """Whether the user's turn is in its shell step: whether the pane's own
        processes, and no other journey's, run its command."""
        pane = self.tmux("display-message", "-p", "-t", self.pane, "#{pane_pid}")
        return runs(int(pane), SLEEP)

    def hear(self, seconds: float) -> None:
        require(not self.exited.exists(), f"Claude Code exited\n{self.screen()}")
        self.approve()
        time.sleep(seconds)

    def records(self) -> list[dict]:
        if self.session is None:
            return []
        return claude_code_records(native_records(self.home, self.session))

    def failure(self, what: str, limit: float) -> click.ClickException:
        return click.ClickException(f"{what} within {limit:.0f} s\n{self.screen()}")

    def approve(self) -> None:
        """Answer the dialog a turn holds open, which Claude Code's record reports
        as `waiting`, with its first option, as the user at the pane does, and record
        the question the screen shows. The record does not say which dialog it is;
        in this journey it is a permission prompt, whose first option is Yes, and a
        step's printed `approved` line would show any other."""
        if self.state() != "waiting":
            return
        screen = self.screen()
        self.tmux("send-keys", "-t", self.pane, "Enter")
        deadline = time.monotonic() + 10
        while self.state() == "waiting" and time.monotonic() < deadline:
            time.sleep(0.1)
        self.approved.append(asked(screen))

    def close(self) -> None:
        self.tmux("kill-session", "-t", self.pane)


def asked(screen: str) -> str:
    """The question a dialog on `screen` asks, for the record: Claude Code's
    permission prompts ask "Do you want to …?", "proceed" for a command, "make this
    edit to" or "create" a file for Edit and Write."""
    lines = [line.strip() for line in screen.splitlines()]
    return next(
        (line for line in reversed(lines) if line.startswith("Do you want to ")),
        "a dialog",
    )


def runs(pid: int, command: str) -> bool:
    """Whether a descendant of process `pid` runs a command line containing
    `command`."""
    for child in psutil.Process(pid).children(recursive=True):
        try:
            if command in " ".join(child.cmdline()):
                return True
        except psutil.NoSuchProcess:
            continue
    return False


def steps(cc: ClaudeCode, user: User, place: Isolation) -> None:
    """The steps after setup, as the module docstring lists them."""
    page, sent = place.page, []

    def activity() -> str:
        """What the page's status reads: its canonical activity's kind."""
        served = run_leaf(ROOT, place.state, "page", "state", str(page), check=True)
        return json.loads(served.stdout)["activity"]["kind"]

    def user_turn(name: str) -> None:
        """Type the user's own turn and wait for its shell command. Escape ends a
        turn but not the command it ran, so an earlier one must be gone first or it
        would read as this one's."""
        cc.until(
            lambda: not cc.sleeping(), f"{name}: an earlier turn's command still runs"
        )
        cc.say(USER_TURN)
        cc.until(cc.sleeping, f"{name}: the user's turn did not start its command")

    def answered(*names: str) -> Callable[[], bool]:
        return lambda: all(user.answered(name) for name in names) and cc.idle()

    def watched() -> bool:
        return wait_is_live(None, cc.session)

    def nudged() -> object:
        return page_claim(page).get("messaged_ending")

    def step(
        name: str,
        started: float,
        *names: str,
        before: object = None,
        escaped: str | None = None,
    ) -> None:
        sent.extend(names)
        settled(page, cc.session, {name: user.ids[name] for name in sent})
        # A watch follows every turn, so no Stop hook continued one with input,
        # which would have put the reply to it in place of the turn's own answer,
        # and Claude Code printed no delivery, whose envelope names its format.
        require(
            not any(
                (attachment := record.get("attachment", {})).get("hookEvent") == "Stop"
                and any(
                    content.startswith((INLINE_OPENING, POINTED_OPENING))
                    for content in attachment.get("content") or []
                )
                for record in native_records(cc.home, cc.session)
            ),
            f"{name}: a Stop hook continued a turn with input",
        )
        require(
            DELIVERY.format not in cc.shown(),
            f"{name}: a delivery was printed in the terminal",
        )
        # The turn that answers ends with a watch running.
        cc.until(watched, f"{name}: no watch holds the session's pages", 60)
        details = [escaped] if escaped else []
        if names:
            details.append("nudged" if nudged() != before else "not nudged")
        user.passed(name, started, *details)
        cc.keep(name)

    def closed(turn: str) -> bool:
        """Whether the page's claim has closed `turn`, or opened another after it."""
        claim = page_claim(page)
        return claim["turn_closed"] is not None or claim["turn"] != turn

    def escape(turn: str) -> None:
        """Press Escape on `turn` until Claude Code is idle or the claim has moved
        past it."""
        cc.escape(lambda: cc.idle() or closed(turn))

    def after_escape(name: str, turn: str) -> str:
        """What an Escape that ended `turn` left. The watch after Escape may already
        have woken a turn of its own, which opens only once `turn` has closed."""
        cc.until(lambda: closed(turn), f"{name}: Escape left the turn open", 30)
        cc.until(
            lambda: watched() or page_claim(page)["turn"] != turn,
            f"{name}: no watch after Escape",
            30,
        )
        return (
            f"after Escape: turn {'closed' if closed(turn) else 'open'}, "
            f"{'a' if watched() else 'no'} watch running, the page reads "
            f"{activity()}"
        )

    started = time.monotonic()
    before = nudged()
    user.release()
    cc.until(cc.idle, "release: the turn that answered did not end")
    step("release", started, "release", before=before)

    started = time.monotonic()
    user_turn("mid-turn")
    turn = page_claim(page)["turn"]
    before = nudged()
    mid_turn = user.ask_while_working()
    cc.until(answered("mid-turn"), "mid-turn: the comment was not answered")
    user.require_recorded()
    require(
        any(
            event["turn"] == turn
            for event in pickup_receipts(
                read_events(page), phase="opened", input_id=mid_turn
            )
        ),
        f"mid-turn: the comment was not picked up in the user's turn {turn}",
    )
    require(
        any(
            event["id"] == mid_turn
            for record in native_records(cc.home, cc.session)
            if (attachment := record.get("attachment", {})).get("hookEvent")
            == "PostToolBatch"
            for content in attachment["content"]
            if content.startswith(INLINE_OPENING + "\n")
            for batch in json.loads(content.split("\n")[1])["batches"]
            for event in batch["events"]
        ),
        "mid-turn: PostToolBatch did not hand the exact input to the model",
    )
    step("mid-turn", started, "mid-turn", before=before)

    started = time.monotonic()
    user_turn("ending")
    turn = page_claim(page)["turn"]
    before = nudged()
    first = user.comment("first")
    cc.until(
        lambda: bool(
            pickup_receipts(read_events(page), phase="opened", input_id=first)
        ),
        "ending: `first` was not picked up",
    )
    # The watch woke for `first` and its handover is done, so nothing watches
    # until this turn ends. Its next tool boundary carries input arriving now.
    ending = user.comment("ending")
    cc.until(answered("first", "ending"), "ending: the comments were not answered")
    picked = [
        event["turn"]
        for event in pickup_receipts(read_events(page), phase="opened", input_id=ending)
    ]
    require(
        turn in picked,
        "ending: the running turn did not pick up `ending`",
    )
    step("ending", started, "first", "ending", before=before)

    started = time.monotonic()
    user_turn("escape")
    turn = page_claim(page)["turn"]
    escape(turn)
    escaped = after_escape("escape", turn)
    before = nudged()
    user.comment("escape")
    cc.until(answered("escape"), "escape: the comment was not answered")
    step("escape", started, "escape", before=before, escaped=escaped)

    started = time.monotonic()
    user_turn("woken")
    turn = page_claim(page)["turn"]
    woken = user.comment("woken")
    # The watch wakes on the comment, which the turn reads only at its next tool
    # boundary, once its command ends.
    cc.until(lambda: not watched(), "woken: the watch did not wake on the comment", 60)
    require(
        cc.sleeping()
        and not pickup_receipts(read_events(page), phase="opened", input_id=woken),
        "woken: the turn read the comment before Escape",
    )
    before = nudged()
    escape(turn)
    escaped = after_escape("woken", turn)
    # The stopped turn never read the comment, so the watch after Escape wakes for
    # it, and a turn of its own answers it.
    cc.until(answered("woken"), "woken: the watch after Escape did not answer it")
    user.comment("after-wake")
    cc.until(answered("woken", "after-wake"), "woken: the comments were not answered")
    step("woken", started, "woken", "after-wake", before=before, escaped=escaped)

    started = time.monotonic()
    cc.say("/exit")
    cc.until(cc.exited.exists, "quit: Claude Code did not exit", 60)
    require(
        session_record(cc.session)["ended"] is not None,
        "quit: the session ended without Leaf's SessionEnd",
    )
    require(
        not claim_is_active(page_claim(page)),
        "quit: the ended session's claim on the page is still active",
    )
    require(not watched(), "quit: the ended session's watch still runs")
    user.passed("quit", started)


def native_records(home: Path, session: str) -> list[dict]:
    """The native session record, including hook context attachments."""
    [path] = (home / ".claude" / "projects").glob(f"*/{session}.jsonl")
    return [json.loads(line) for line in path.read_text().splitlines()]


@contextmanager
def answering(browser, *, sandbox: bool) -> Iterator[tuple[User, Callable]]:
    """The user at the page an interactive Claude Code session serves, once it has,
    and the steps that follow."""
    require(shutil.which("tmux") is not None, "the claude-code journey drives tmux")

    def environment(place: Isolation) -> dict[str, str]:
        home = claude_home(place.root / "home")
        (home / ".claude.json").write_text(
            json.dumps(
                {
                    "hasCompletedOnboarding": True,
                    "theme": "dark",
                    "projects": {str(place.work): {"hasTrustDialogAccepted": True}},
                }
            )
        )
        return claude_environment(
            home, XDG_STATE_HOME=str(place.state), TERM="tmux-256color"
        )

    with isolated("claude-code", environment) as place:
        prepare(ROOT, place.state, place.page)
        settings = {}
        if sandbox:
            # The README's settings ("Agent sandboxes"), which let Leaf's sandboxed
            # commands reach the bridge its hooks keep outside the sandbox.
            settings["sandbox"] = {
                "enabled": True,
                "failIfUnavailable": True,
                "network": {"allowedDomains": ["127.0.0.1"]},
            }
        # The session's id is the journey's from the start, so Claude Code's record
        # of it answers `approve` before the page is claimed.
        session = str(uuid.uuid4())
        argv = [
            "claude", "--session-id", session, "--model", MODELS[ClaudeCodeHarness.name],
            "--plugin-dir", str(place.payload), "--settings", json.dumps(settings),
            "--strict-mcp-config", "--permission-mode", "default",
            "--add-dir", str(place.payload),
            "--allowedTools", "Bash Read Write Edit Glob Grep Skill",
            "--debug-file", str(place.evidence / "debug.log"),
        ]  # fmt: skip
        cc = ClaudeCode(place, argv, dict(os.environ))
        cc.session = session
        try:
            started = time.monotonic()
            cc.say(REQUEST)
            cc.until(
                lambda: page_claim(place.page) is not None,
                "setup: the page was not claimed",
            )
            require(
                page_claim(place.page)["id"] == session,
                "setup: the page's claim names another session",
            )
            cc.until(
                lambda: (
                    running_server(place.page) is not None
                    and cc.idle()
                    and wait_is_live(None, cc.session)
                ),
                "setup: the page was not served with the session idle and a watch "
                "running",
            )
            settled(place.page, cc.session, {})
            require(
                DELIVERY.format not in cc.shown(),
                "setup: a delivery was printed in the terminal",
            )
            cc.keep("setup")
            with user_at(browser, place, cc, started) as user:
                yield user, lambda: steps(cc, user, place)
        finally:
            # A failed step's screen; once Claude Code exits there is none.
            cc.keep("end")
            cc.close()
