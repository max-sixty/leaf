"""The `claude-code` journey: a real interactive Claude Code session with Leaf's
plugin, and the steps a user takes at its terminal.

    uv run leaf-dev journey run claude-code [--sandbox]

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

As in every Claude Code session, Leaf hands each comment to the session as it does
any input, while a line fork posts the agent's working line on it (`leaf.agents.forks`),
and the session decides who does its work: itself, or a subagent that would answer
in its place. So each delivery step's comment asks for a change to the page, which
the session makes itself, and the step tests the session's own delivery from then
on; `withdrawn`'s comment needs none, since the user takes it back at once. The fork
steps run right after `release`. Whether a message is worth a fork is the session's
call, and it does a one-step lookup itself, so both fork steps send their message
while the session runs the user's own turn, and the first asks for the work beside
it; `evals/beside-work-goes-to-a-fork` scores the instruction itself.

The steps, in order; `setup`, `release`, `answered-twice`, `mid-turn`, `escape` and
`quit` are those more than one harness takes, as `_journey.Terminal` has them:

- `setup`;
- `release`, which asks for work, and the session answers it; the step prints what
  came of its line fork.

Then the fork steps, each timed from the comment's admission to the reply, with the
line fork's own time and tokens from its record in the page's diagnostics
(`fork_outcome`):

- `fork-busy`: during the user's own turn's shell command, a question answered by
  reading the page's source: the line fork posts the agent's working line as its
  first reply, the session takes the message at its next tool boundary and starts
  it, so no prompt reminds it of the message as owed, and gives it to a subagent of
  its own, which answers it in the thread itself with `leaf thread reply` while
  Leaf's hooks hand the subagent no delivery; Claude Code then tells the session the
  subagent finished, in a turn of its own or the one running, and the session
  doesn't answer the message again;
- `fork-follow-up`: once that subagent has answered, the user's further message in
  its thread, sent during another turn of the user's, which the session gives to a
  subagent again, the same one with SendMessage or a new one, which answers it.

Then `answered-twice`: the user answers the agent's question in words, then picks the
same choice once the session has taken the words in, and the thread gets one answer.

Then the delivery steps:

- `mid-turn`: a comment sent during the user's own turn's shell command gets the
  line fork's working line as its first reply, and the turn's PostToolBatch context
  carries the exact input before another model call, rather than waiting for Stop;
- `ending`: two comments sent during a shell command, the second after the turn
  picked up the first, both enter that turn at its tool boundaries;
- `escape`, whose line says the claim's turn stayed open, since Escape runs no
  Stop hook;
- `woken`: a comment sent during a shell command waits for the running turn, and
  Escape ends that turn while the command still runs, before the turn reads the
  comment at its next tool boundary. The watch after Escape wakes for that comment
  and a turn of its own answers it; a comment sent afterwards is answered too;
- `dropped`: another prompt hook, the session's own setting, sleeps 6 s while a
  comment's wake runs its prompt hooks, and Escape lands once Leaf's has handed the
  comment over, so Claude Code drops what Leaf's hook returned. It submits the wake
  again, whose prompt hook hands the comment over anew, and a turn answers it;
- `withdrawn`: the same for an update that owes nothing, the user taking back a
  comment that had no answer yet, which must still reach a hook's context after
  Escape. A resolve of that thread would not do: it leaves the comment owed and
  reaches no hook;
- `boundary`: a comment that arrives while a wake's turn answers another, handed over
  at the tool boundary after that answer, whose other hook sleeps, and Escape then
  ends that turn with neither comment half done. Another hook before each shell
  command, the session's own setting, holds the answer until the comment is admitted,
  so where it is handed over doesn't depend on how the agent batches its calls. That
  boundary comes about a second after the comment's admission, sooner than a line
  fork usually answers, so its handing the comment over shows the session getting a
  comment without waiting for its line. The watch the wake's prompt started wakes
  the session, whose prompt names the comment as owed rather than handing it over
  again, so it is handed over once, and a turn of its own answers it;
- `deferred`: the user's own turn, told to leave Leaf's comments for later, is
  handed a comment at a tool boundary and ends on its answer with the comment
  unanswered, and no Stop hook continues it over the comment. The watch wakes a
  turn of its own whose prompt names the owed answer, and that turn answers it;
- `compacting`: a comment sent while `/compact` runs at the idle prompt wakes the
  session once the compaction ends, and a turn of its own answers it. Compaction
  runs no prompt or Stop hook, so the watch the last turn's Stop started keeps
  running through it, and Claude Code holds that watch's wake until the
  compaction is done.

Then `quit`, by `/exit`.

After each step the journey requires what every harness must hold between steps
(`_journey.Terminal.between`), with the watch as what listens for the session; and
that no Stop hook has continued a turn with input, so each turn ends on its own
answer, no delivery shows in the terminal, and Leaf put no empty wake or notice in
the conversation (`ClaudeCode.between`). Escape runs no Stop hook,
so it leaves the turn open, and the watch its prompt started, which waits while that
turn runs, still running.

Each step also prints the rows Leaf put in the conversation the user reads, a nudge
among them, and, with an Escape, whether it left the turn open; `woken`'s also says
whether a watch was running and what the page's status read. The sample keeps the
rows as each step's `shown`. The session's screen at the end of each step and Claude Code's
debug log join the run's evidence. It needs tmux, and spends a few model turns on
the host's Claude Code login, so CI does not run it.
"""

import json
import os
import shlex
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import click
import psutil

from leaf.agents.delivery import (
    DELIVERY,
    INLINE_OPENING,
    delivery_pointer_prompt,
    inline_delivery,
)
from leaf.base.harness import (
    NUDGE_WORDS,
    ClaudeCodeHarness,
    claude_code_live_turn,
    claude_code_registry,
)
from leaf.base.server import running_server
from leaf.base.service import page_claim
from leaf.base.state import turn_open
from leaf.commands.hook_transport import ATTENTION_OPENING
from leaf.log.event_log import read_events
from leaf_dev import ROOT
from leaf_dev.arms import MODELS, PageClient, claude_environment, claude_home
from leaf_dev.commands.journey._journey import (
    Isolation,
    Terminal,
    User,
    fork_summary,
    isolated,
    user_at,
)
from leaf_dev.reply_phases import (
    LEAF_WAKE,
    claude_code_debug_records,
    claude_code_records,
    ends_turn,
    instant,
    transcript_records,
)
from leaf_dev.review_scenario import (
    SLEEP,
    USER_TURN,
    activity,
    answers,
    attempt,
    picked_up,
    post,
    prepare,
    require,
)

# The user's further message in the thread of `fork-busy`'s question, sent once the
# subagent that took the question has answered it. Like that question it asks for the
# work beside the session's own, and for a card the first answer didn't rank, since a
# session that holds the answer in the subagent's report rightly gives it itself.
FOLLOW_UP = (
    "Look into this beside your own work too: which card would they ask about last, "
    "and why?"
)

# How a hook context that hands a delivery over by its pointer begins.
POINTER_OPENING = delivery_pointer_prompt("00000000").partition(" id=")[0]

# The user's own turn, which leaves a comment handed to it unanswered.
DEFERRING_TURN = USER_TURN.replace(
    "Then reply with the single word done.",
    "Leave any Leaf comment unanswered in this turn, then reply with the single "
    "word done.",
)


def claude_code_environment(place: Isolation) -> dict[str, str]:
    """The environment of an interactive Claude Code session in `place`: a home
    holding only the host's login (`arms.claude_home`), whose own
    record says onboarding is done and trusts the session's cwd and the plugin it
    adds (`--add-dir`), which Claude Code 2.1.326 asks about before the prompt, so
    the session opens at its prompt."""
    home = claude_home(place.root / "home")
    trusted = {"hasTrustDialogAccepted": True}
    (home / ".claude.json").write_text(
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "theme": "dark",
                "projects": {str(place.work): trusted, str(place.payload): trusted},
            }
        )
    )
    return claude_environment(
        home, XDG_STATE_HOME=str(place.state), TERM="tmux-256color"
    )


class ClaudeCode(Terminal):
    """One interactive Claude Code session in a tmux pane, and the user at it. The
    session runs `model` in `place`'s cwd under `env` (`claude_code_environment`),
    with `place`'s payload as its plugin and `settings` added to its own."""

    def __init__(
        self, place: Isolation, env: dict, *, model: str, settings: dict | None = None
    ) -> None:
        super().__init__()
        # The session's id is chosen before it starts, so Claude Code's record of it
        # answers `approve` before the page is claimed.
        self.session = str(uuid.uuid4())
        # How many of the conversation's records the steps so far have counted, and
        # the rows Leaf put in it during the last (`between`).
        self.read = 0
        self.rows: dict[str, int] = {}
        self.pane = f"leaf-journey-claude-code-{os.getpid()}"
        self.home = place.root / "home"
        self.exited, self.kept = place.root / "exited", place.evidence / "screen.txt"
        self.debug = place.evidence / "debug.log"
        self.evidence = place.evidence
        argv = [
            "claude", "--session-id", self.session, "--model", model,
            "--plugin-dir", str(place.payload),
            *(("--settings", json.dumps(settings)) if settings else ()),
            "--strict-mcp-config", "--permission-mode", "default",
            "--add-dir", str(place.payload),
            "--allowedTools", "Bash Read Write Edit Glob Grep Skill",
            "--debug-file", str(self.debug),
        ]  # fmt: skip
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

    def press_escape(self, ended: Callable[[], bool] | None = None) -> None:
        """Press Escape until `ended` says the turn has, by default once Claude Code
        reads idle, waiting up to 5 s after each press before pressing again. A press
        after the turn ended does harm: on an idle prompt it opens Claude Code's
        rewind menu, and otherwise it interrupts the turn a watch or a nudge opened
        next, which can start before Claude Code's record reads idle."""
        ended = ended or self.idle
        for _ in range(3):
            self.tmux("send-keys", "-t", self.pane, "Escape")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if ended():
                    return
                time.sleep(0.25)
        raise click.ClickException(f"the turn went on after Escape\n{self.screen()}")

    def state(self) -> str | None:
        """The turn's state in Claude Code's own record (`claude_code_live_turn`),
        read now. Leaf's hooks and server reuse a registry listing for up to
        `REGISTRY_READ_S` (`claude_code_session_records`), longer than some states
        the journey checks last: Claude Code reads idle for about 50 ms between an
        Escape and the wake it submits again (measured at 2.1.309)."""
        turn = claude_code_live_turn(
            [
                record
                for record in claude_code_registry()
                if record.get("sessionId") == self.session
            ]
        )
        return None if turn is None else turn["state"]

    def idle(self) -> bool:
        """Whether Claude Code's own record says no turn runs."""
        return self.state() == "idle"

    def work(self, turn: str = USER_TURN) -> None:
        """Type the user's own `turn` and wait for its shell command. Escape ends a
        turn but not the command it ran, so an earlier one must be gone first or it
        would read as this one's."""
        self.until(lambda: not self.sleeping(), "an earlier turn's command still runs")
        self.say(turn)
        self.until(self.sleeping, "the user's turn did not start its command")

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
        """The transcript's records, with the requests, first outputs and Leaf's
        hooks of the debug log Claude Code writes (`--debug-file`)."""
        logged = self.debug.read_text() if self.debug.exists() else ""
        return sorted(
            claude_code_records(native_records(self.home, self.session))
            + claude_code_debug_records(logged),
            key=lambda record: instant(record["received_at"]),
        )

    def failure(self, what: str, limit: float) -> click.ClickException:
        return click.ClickException(f"{what} within {limit:.0f} s\n{self.screen()}")

    def between(
        self, page: Path, name: str, comments: dict[str, str] | None = None
    ) -> list[str]:
        """What holds between steps (`Terminal.between`), and on Claude Code besides:
        no Stop hook has continued a turn with input, which would have put the reply
        to it in place of the turn's own answer; Claude Code printed no delivery,
        whose envelope names its format; and Leaf put no empty wake or notice in the
        conversation since the last step (`leaf_rows`), whose rows the step's line
        prints and its record keeps (`passed`). The step's screen joins the
        evidence."""
        lines = super().between(page, name, comments)
        records = native_records(self.home, self.session)
        require(
            not any(
                (attachment := record.get("attachment", {})).get("hookEvent") == "Stop"
                and any(
                    content.startswith((INLINE_OPENING, POINTER_OPENING))
                    for content in attachment.get("content") or []
                )
                for record in records
            ),
            f"{name}: a Stop hook continued a turn with input",
        )
        require(
            DELIVERY.format not in self.shown(),
            f"{name}: a delivery was printed in the terminal",
        )
        self.rows = leaf_rows(records[self.read :])
        self.read = len(records)
        require(
            not {"empty", "notice"} & self.rows.keys(),
            f"{name}: Leaf put an empty wake or a notice in the conversation: "
            f"{self.rows}",
        )
        self.keep(name)
        shown = ", ".join(f"{count} {kind}" for kind, count in self.rows.items())
        return [*lines, f"shown: {shown or 'none'}"]

    def passed(
        self,
        user: User,
        page: Path,
        name: str,
        started: float,
        *comments: str,
        detail: str | None = None,
    ) -> None:
        """`Terminal.passed`, the step's record keeping as `shown` the rows Leaf put
        in the conversation during it (`between`)."""
        super().passed(user, page, name, started, *comments, detail=detail)
        user.steps[-1]["shown"] = self.rows

    def leave(self) -> None:
        """Exit with `/exit`, as the user at the pane does."""
        self.say("/exit")
        self.until(self.exited.exists, "quit: Claude Code did not exit", 60)

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
        # The session's home goes with the run, so its transcript and its
        # subagents' join the evidence, where `leaf-dev logs timeline` reads them.
        kept = self.evidence / "claude"
        for found in (self.home / ".claude" / "projects").glob(f"*/{self.session}*"):
            kept.mkdir(exist_ok=True)
            if found.is_dir():
                shutil.copytree(found, kept / found.name, dirs_exist_ok=True)
            else:
                shutil.copy(found, kept / found.name)


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
        except psutil.Error:
            continue
    return False


def steps(cc: ClaudeCode, user: User, place: Isolation) -> None:
    """The steps after setup, as the module docstring lists them."""
    page, session = place.page, cc.session
    step = partial(cc.passed, user, page)

    def answered(*names: str) -> Callable[[], bool]:
        return lambda: all(user.answered(name) for name in names) and cc.idle()

    def closed(turn: str) -> bool:
        """Whether the page's claim has closed `turn`, or opened another after it."""
        return not turn_open(page_claim(page), turn)

    def hook_contexts(event: str, since: int = 0) -> list[str]:
        """The contexts the hooks of `event` put in the conversation from its record
        `since` on, one a hook."""
        return [
            content
            for record in native_records(cc.home, session)[since:]
            if (attachment := record.get("attachment", {})).get("hookEvent") == event
            for content in attachment.get("content") or []
        ]

    def lined(name: str) -> float:
        """Require the line fork on step `name`'s comment to have posted the agent's
        working line as the comment's first reply; the seconds to that reply."""
        fork = require(user.fork(name), f"{name}: no line fork ran on the comment")
        require(
            fork["outcome"] == "posted",
            f"{name}: the line fork posted no working line: {fork_summary(fork)}",
        )
        timings = user.end.timings()[user.ids[name]]["milestones"]
        require(
            timings["first_reply"]["event_id"] == fork["line"],
            f"{name}: the fork's working line was not the comment's first reply",
        )
        return timings["first_reply"]["elapsed_s"]

    def delivered() -> None:
        """The delivery steps, from `mid-turn` to `compacting`."""
        started = time.monotonic()
        mid_turn = cc.mid_turn(user, page)
        records = native_records(cc.home, session)
        require(
            any(
                records[position]["attachment"].get("hookEvent") == "PostToolBatch"
                for position in deliveries(records, mid_turn)
            ),
            "mid-turn: PostToolBatch did not hand the exact input to the model",
        )
        first = lined("mid-turn")
        step(
            "mid-turn",
            started,
            "mid-turn",
            detail=f"`mid-turn` had the line fork's working line after {first:.1f} s",
        )

        started = time.monotonic()
        turn = cc.user_turn(page)
        first = user.comment("first")
        cc.until(
            lambda: bool(picked_up(page, first)), "ending: `first` was not picked up"
        )
        # The watch woke for `first` and its handover is done, so nothing watches
        # until this turn ends. Its next tool boundary carries input arriving now.
        ending = user.comment("ending")
        cc.until(answered("first", "ending"), "ending: the comments were not answered")
        require(
            turn in picked_up(page, ending),
            "ending: the running turn did not pick up `ending`",
        )
        step("ending", started, "first", "ending")

        started = time.monotonic()
        stayed = cc.escape(user, page)
        step(
            "escape",
            started,
            "escape",
            detail=f"after Escape: turn {'open' if stayed else 'closed'}",
        )

        started = time.monotonic()
        turn = cc.user_turn(page)
        woken = user.comment("woken")
        # The turn reads the comment only at its next tool boundary, once its command
        # ends, so a watch that held the session's lease as the comment arrived leaves
        # it to the turn.
        time.sleep(2)
        require(
            cc.sleeping() and cc.listening() and not picked_up(page, woken),
            "woken: the comment did not wait for the running turn",
        )
        cc.press_escape(lambda: cc.idle() or closed(turn))
        # Escape runs no Stop hook, so the turn stays open, and the watch its prompt
        # started, which waited while that turn ran, may already have woken a turn of
        # its own for the comment.
        cc.until(
            lambda: cc.listening() or closed(turn), "woken: no watch after Escape", 30
        )
        escaped = (
            f"after Escape: turn {'closed' if closed(turn) else 'open'}, "
            f"{'a' if cc.listening() else 'no'} watch running, the page reads "
            f"{' and '.join(activity(page))}"
        )
        # The stopped turn never read the comment, so the watch after Escape wakes for
        # it, and a turn of its own answers it.
        cc.until(answered("woken"), "woken: the watch after Escape did not answer it")
        user.comment("after-wake")
        cc.until(
            answered("woken", "after-wake"), "woken: the comments were not answered"
        )
        step("woken", started, "woken", "after-wake", detail=escaped)

        def drop(update: str, release: Callable[[], object] = lambda: None) -> int:
            """Slow the session's other prompt and tool-batch hooks, `release` a turn
            the step holds short of the hook that hands `update` over, and press Escape
            once Leaf's hook has handed `update` over and while the other still runs, so
            Claude Code drops what Leaf's hook returned. Returns how many records the
            conversation held as Escape was pressed."""
            slow_prompt(place).touch()
            try:
                release()
                cc.until(
                    lambda: bool(picked_up(page, update)),
                    f"{update}: no hook handed it over",
                    90,
                )
            finally:
                slow_prompt(place).unlink()
            require(
                cc.state() == "busy",
                f"{update}: the slow hook ended before Escape could land",
            )
            held = len(native_records(cc.home, session))
            cc.tmux("send-keys", "-t", cc.pane, "Escape")
            return held

        def since(held: int) -> list[dict]:
            """The conversation's records from record `held` on."""
            return native_records(cc.home, session)[held:]

        started = time.monotonic()
        dropped = user.comment("dropped")
        held = drop(dropped)
        # Claude Code submits the queued wake again, and that attempt's prompt hook hands
        # the comment over anew.
        cc.until(answered("dropped"), "dropped: the comment was not answered", 120)
        require(
            bool(deliveries(since(held), dropped)),
            "dropped: no hook delivered the comment again after Escape",
        )
        step("dropped", started, "dropped")

        started = time.monotonic()
        url = require(running_server(page), "the page has no server")["url"]
        comment = post(url, "withdrawn", "Never mind, I'll check this myself.")
        taken_back = PageClient(url).post(
            {"kind": "undo", "undoes": comment, "attempt": attempt("undo")}
        )["id"]
        held = drop(taken_back)
        cc.until(
            lambda: delivery_ended(since(held), taken_back),
            "withdrawn: the take-back Escape dropped never reached the agent",
            120,
        )
        step("withdrawn", started)

        started = time.monotonic()
        # The wake's answer to `first-wake` waits before its command runs, so
        # `boundary`, sent then, reaches the turn at the tool boundary after that
        # answer. Handed over between the wake's edit and its answer, it would leave
        # `first-wake` half done as Escape lands, which the woken turn may reasonably
        # ask the user about rather than finish.
        hold, holding = answer_hold(place)
        hold.touch()
        try:
            user.comment("first-wake")
            cc.until(
                lambda: holding.exists() or user.answered("first-wake"),
                "boundary: the wake's turn did not answer its comment",
            )
            require(
                holding.exists(),
                "boundary: the wake's turn answered its comment past the answer hold",
            )
            boundary = user.comment("boundary")
            escaped = drop(boundary, release=hold.unlink)
        finally:
            hold.unlink(missing_ok=True)
            holding.unlink(missing_ok=True)
        cc.until(
            answered("first-wake", "boundary"),
            "boundary: the comment Escape kept was not answered",
            150,
        )
        # Escape during a tool boundary's hooks keeps that boundary's context, so the
        # comment is in the conversation once and the woken turn only names it as owed.
        records = native_records(cc.home, session)
        handed = deliveries(records, boundary)
        require(
            len(handed) == 1,
            f"boundary: the comment Escape kept was handed over {len(handed)} times",
        )
        require(
            records[handed[0]]["attachment"].get("hookEvent") == "PostToolBatch",
            "boundary: the comment reached the turn by a prompt, not a tool boundary",
        )
        require(
            any(
                ATTENTION_OPENING in content and boundary in content
                for content in hook_contexts("UserPromptSubmit", escaped)
            ),
            "boundary: no prompt after Escape named the comment as owed",
        )
        step("boundary", started, "first-wake", "boundary")

        started = time.monotonic()
        before = len(native_records(cc.home, session))
        turn = cc.user_turn(page, DEFERRING_TURN)
        deferred = user.comment("deferred")
        cc.until(lambda: closed(turn), "deferred: the user's turn did not end")
        require(
            not user.answered("deferred"),
            "deferred: the user's turn answered the comment it was told to leave",
        )
        cc.until(
            answered("deferred"), "deferred: the comment the turn left was not answered"
        )

        require(
            not any(
                ATTENTION_OPENING in content
                for content in hook_contexts("Stop", before)
            ),
            "deferred: a Stop hook continued the user's turn over the owed comment",
        )
        require(
            any(
                ATTENTION_OPENING in content and deferred in content
                for content in hook_contexts("UserPromptSubmit")
            ),
            "deferred: no prompt of a later turn named the owed comment",
        )
        step("deferred", started, "deferred")

        def compacting() -> bool:
            return "Compacting conversation" in cc.screen()

        started = time.monotonic()
        cc.say("/compact")
        cc.until(compacting, "compacting: the compaction did not start", 30)
        user.comment("compacting")
        require(compacting(), "compacting: the compaction ended before the comment")
        cc.until(answered("compacting"), "compacting: the comment was not answered")
        step("compacting", started, "compacting")

    def tool_uses(records: list[dict], name: str) -> list[dict]:
        """The calls of tool `name` in a transcript's `records`, each with when it was
        made (`at`), in order."""
        return [
            {**part, "at": record["timestamp"]}
            for record in records
            if record.get("type") == "assistant"
            for part in record["message"]["content"]
            if isinstance(part, dict)
            and part.get("type") == "tool_use"
            and part.get("name") == name
        ]

    def subagents() -> dict[str, dict]:
        """The session's subagents by agent id, each its record of how it was spawned
        (`meta`) and its transcript's records, as Claude Code keeps them beside the
        session's transcript (`<session>/subagents/agent-<id>.jsonl`)."""
        [path] = (cc.home / ".claude" / "projects").glob(f"*/{session}.jsonl")
        kept = path.with_suffix("") / "subagents"
        return {
            meta.name.removesuffix(".meta.json").removeprefix("agent-"): {
                "meta": json.loads(meta.read_text()),
                "records": transcript_records(
                    meta.with_name(meta.name.removesuffix(".meta.json") + ".jsonl")
                ),
            }
            for meta in (sorted(kept.glob("*.meta.json")) if kept.exists() else [])
        }

    def answered_by(agent: dict, reference: str) -> bool:
        """Whether the subagent `agent` (`subagents`) ran a `leaf thread reply` to
        `reference`."""
        return any(
            "thread reply" in command and reference in command
            for call in tool_uses(agent["records"], "Bash")
            if isinstance(command := call["input"].get("command"), str)
        )

    def references(update: str) -> list[str]:
        """The `answer.ref`s the deliveries in the session's transcript gave `update`."""
        records = native_records(cc.home, session)
        return [
            event["answer"]["ref"]
            for position in deliveries(records, update)
            for content in records[position]["attachment"].get("content") or []
            if (inline := inline_delivery(content)) is not None
            for batch in inline[0]["batches"]
            for event in batch["events"]
            if event["id"] == update and "ref" in event.get("answer", {})
        ]

    def delegated(name: str, update: str, started: float) -> tuple[str, dict]:
        """Require that the line fork posted its line on `update`, that a delivery
        handed the message to the session, and that the session gave it to a fork of
        its conversation, which answered it there itself while Leaf's hooks handed it
        no delivery.
        Returns that subagent's id and its record (`subagents`)."""
        cc.until(
            lambda: bool(answers(page, update)) and cc.idle(),
            f"{name}: nobody answered the message",
            240,
        )
        line_fork = require(
            next(
                (
                    record
                    for record in reversed(user.forks() if user.forks else [])
                    if update in record["inputs"]
                ),
                None,
            ),
            f"{name}: no line fork ran on the message",
        )
        require(
            line_fork["outcome"] == "posted",
            f"{name}: the line fork posted no working line: {fork_summary(line_fork)}",
        )
        refs = require(references(update), f"{name}: no delivery handed it over")
        workers = {
            agent: kept
            for agent, kept in subagents().items()
            if any(answered_by(kept, ref) for ref in refs)
        }
        [(agent, worker)] = require(
            list(workers.items()),
            f"{name}: no subagent answered it; subagents: "
            f"{[kept['meta'].get('agentType') for kept in subagents().values()]}",
        )
        # A fork of the session's conversation, as the reference asks, rather than a
        # fresh subagent of another type.
        require(
            worker["meta"].get("agentType") == "fork",
            f"{name}: a {worker['meta'].get('agentType')} subagent answered it, not a "
            "fork of the session",
        )
        require(
            not any(
                "thread reply" in call["input"].get("command", "")
                and any(ref in call["input"].get("command", "") for ref in refs)
                for call in tool_uses(native_records(cc.home, session), "Bash")
            ),
            f"{name}: the session answered the message itself as well",
        )
        # A subagent's tool boundary carries nothing of the session's input
        # (`state.worker_tool_batch`), so its transcript holds no delivery.
        require(
            not any(
                inline_delivery(content) is not None
                for record in worker["records"]
                for content in (record.get("attachment") or {}).get("content") or []
            ),
            f"{name}: a Leaf hook handed the subagent a delivery",
        )
        replies = answers(page, update)
        require(len(replies) == 1, f"{name}: the message has {len(replies)} answers")
        # The session started the message as it handed it on, so no turn's end left
        # it owed, and no prompt reminded the session of it (`session.left_owed`).
        require(
            not any(
                "with no answer" in content and any(ref in content for ref in refs)
                for content in hook_contexts("UserPromptSubmit")
            ),
            f"{name}: Leaf reminded the session of the message as owed, so it never "
            "started it",
        )
        return agent, worker

    def forked() -> None:
        """The fork steps, `fork-busy` and `fork-follow-up`."""
        url = require(running_server(page), "the page has no server")["url"]

        # `fork-busy`
        started = time.monotonic()
        cc.user_turn(page)
        asked = user.comment("fork-busy")
        agent, worker = delegated("fork-busy", asked, started)
        sent = instant(next(e["ts"] for e in read_events(page) if e["id"] == asked))
        [reply] = answers(page, asked)

        def woken(since: float) -> list[dict]:
            """The session's turns started after `since`, as Claude Code recorded
            each start."""
            return [
                record
                for record in claude_code_records(native_records(cc.home, session))
                if record["type"] == "turn_start"
                and instant(record["received_at"]) > since
            ]

        def notified() -> bool:
            """Whether Claude Code told the session that its subagent finished: a
            notice that starts a turn of an idle session, or joins the one running."""
            return any(
                f"<task-id>{agent}</task-id>" in json.dumps(record)
                for record in native_records(cc.home, session)
                if record.get("type") == "user"
                or (record.get("attachment") or {}).get("type") == "queued_command"
            )

        # Claude Code tells the session as its subagent's run ends, and the session
        # doesn't answer the message again.
        cc.settle(
            notified,
            "fork-busy: Claude Code never told the session its subagent finished",
        )
        woke = any(t.get("origin") == "task_notification" for t in woken(sent))
        events = {event["id"]: event for event in read_events(page)}
        line_fork = next(
            record
            for record in reversed(user.forks() if user.forks else [])
            if asked in record["inputs"]
        )

        def after(event_id: str) -> float:
            return instant(events[event_id]["ts"]) - sent

        # Named, so what holds between steps requires the message answered once
        # from this step on.
        step(
            "fork-busy",
            started,
            "fork-busy",
            detail=(
                f"`fork-busy`: the line fork's working line came "
                f"{after(line_fork['line']):.1f} s after the message, and the "
                f"session's {worker['meta'].get('agentType')} subagent {agent} "
                f"answered it at {after(reply['id']):.1f} s; Claude Code's notice of "
                "its end "
                + ("started a turn" if woke else "joined a running turn")
                + f": {reply['text'][:200]!r}"
            ),
        )

        # `fork-follow-up`: the thread's next message goes to a subagent again, the
        # same one or a new one, as the session judges.
        started = time.monotonic()
        cc.user_turn(page)
        more = PageClient(url).post(
            {
                "kind": "reply",
                "parent": asked,
                "attempt": attempt("fork-follow-up"),
                "text": FOLLOW_UP,
            }
        )["id"]
        again, _ = delegated("fork-follow-up", more, started)
        if again == agent:
            # The session reaches its subagent by the id or the name it spawned it
            # with.
            addresses = {agent, f"agent-{agent}", worker["meta"].get("name")} - {None}
            require(
                any(
                    call["input"].get("to") in addresses
                    for call in tool_uses(
                        native_records(cc.home, session), "SendMessage"
                    )
                ),
                f"fork-follow-up: {agent} answered it, but the session sent nothing "
                "to it",
            )
        events = {event["id"]: event for event in read_events(page)}
        [reply] = answers(page, more)
        step(
            "fork-follow-up",
            started,
            detail=(
                "`fork-follow-up`: the session passed the message on to "
                + (
                    f"{agent}, the thread's subagent"
                    if again == agent
                    else f"a new subagent {again}"
                )
                + ", which answered it "
                f"{instant(reply['ts']) - instant(events[more]['ts']):.1f} s after "
                f"it was sent: {reply['text'][:200]!r}"
            ),
        )

    started = time.monotonic()
    cc.release(user)
    fork = require(user.fork("release"), "release: no line fork ran on the ask")
    step("release", started, "release", detail=f"`release`: {fork_summary(fork)}")
    forked()

    started = time.monotonic()
    detail = cc.answered_twice(user, page)
    step("answered-twice", started, detail=detail)

    delivered()

    started = time.monotonic()
    cc.quit(page)
    user.passed("quit", started)


def leaf_rows(records: list[dict]) -> dict[str, int]:
    """How many rows of each kind Leaf put in the conversation the user reads, among
    native `records`: a wake (`hooks.json`'s background Stop hook, a task
    notification whose summary the registration names), a nudge through session
    messaging, a notice the hooks module logged, and a hook's error. A wake or
    nudge that no context of Leaf's prompt or tool-boundary hooks follows before the
    next one, or the user's next prompt, also counts as `empty`: a turn opened with
    nothing for it, such as input another turn had already taken. Leaf's are the
    session's only hooks to put context there: a delivery, a reminder, or a line
    telling the session of work it owes. A row counts whether or not the hooks
    module draws it."""
    rows: dict[str, int] = {}
    opened = False

    def count(kind: str) -> None:
        rows[kind] = rows.get(kind, 0) + 1

    def close() -> None:
        nonlocal opened
        if opened:
            count("empty")
        opened = False

    for record in records:
        origin = record.get("origin") or {}
        attachment = record.get("attachment") or {}
        # A wake or nudge arriving while a turn runs joins it as a queued command.
        content = (
            attachment["prompt"]
            if attachment.get("type") == "queued_command"
            else record.get("message", {}).get("content", record.get("content"))
        )
        text = json.dumps(content) if not isinstance(content, str) else content
        kind = (
            "Stop hook wake"
            if f"<summary>{LEAF_WAKE}</summary>" in text
            else "nudge"
            if NUDGE_WORDS in text
            else None
        )
        if kind is not None and (
            record.get("type") == "user" or attachment.get("type") == "queued_command"
        ):
            close()
            count(kind)
            opened = True
        elif record.get("type") == "user" and origin.get("kind") == "composer":
            close()
        elif record.get("type") == "system" and str(record.get("content")).startswith(
            "leaf:"
        ):
            count("notice")
        elif attachment.get("type") in (
            "hook_non_blocking_error",
            "hook_blocking_error",
        ):
            count("hook error")
        elif (
            attachment.get("type") == "hook_additional_context"
            and attachment.get("hookEvent") in ("UserPromptSubmit", "PostToolBatch")
            and any(str(part).strip() for part in attachment.get("content") or [])
        ):
            opened = False
    close()
    return rows


def slow_prompt(place: Isolation) -> Path:
    """The file whose presence holds the session's other prompt hook for 6 s."""
    return place.root / "slow-prompt"


def answer_hold(place: Isolation) -> tuple[Path, Path]:
    """The file whose presence holds the session's answer to a comment, a `leaf
    thread reply`, in its other hook before the command runs, and the file that hook
    makes once it holds one."""
    return place.root / "hold-answer", place.root / "answer-held"


def native_records(home: Path, session: str) -> list[dict]:
    """The native session record, including hook context attachments
    (`reply_phases.transcript_records`)."""
    [path] = (home / ".claude" / "projects").glob(f"*/{session}.jsonl")
    return transcript_records(path)


def deliveries(records: list[dict], update: str) -> list[int]:
    """The positions in `records` of the inline deliveries a hook put in the
    conversation that carry `update`: a reminder naming it carries nothing."""
    return [
        position
        for position, record in enumerate(records)
        if (attachment := record.get("attachment", {})).get("type")
        == "hook_additional_context"
        and any(
            event["id"] == update
            for content in attachment.get("content") or []
            if (inline := inline_delivery(content)) is not None
            for batch in inline[0]["batches"]
            for event in batch["events"]
        )
    ]


def delivery_ended(records: list[dict], update: str) -> bool:
    """Whether the turn a hook delivered `update` to has ended: whether the
    transcript (`records`) holds a record that ends a turn after the last delivery
    carrying `update`.

    An update that owes no answer leaves no reply to wait for, so the journey waits
    for the transcript's turn end, which the transcript orders after the delivery
    itself. An idle reading of Claude Code's record carries no such order: the
    Escape that dropped the first delivery wrote one just before the wake was
    submitted again."""
    found = deliveries(records, update)
    return bool(found) and any(ends_turn(record) for record in records[found[-1] :])


@contextmanager
def answering(browser, *, sandbox: bool) -> Generator[tuple[User, Callable]]:
    """The user at the page an interactive Claude Code session serves, once it has,
    and the steps that follow."""
    require(shutil.which("tmux") is not None, "the claude-code journey drives tmux")

    with isolated("claude-code", claude_code_environment) as place:
        prepare(ROOT, place.state, place.page)
        # Another plugin's prompt hook, slower than Leaf's while the `dropped` steps
        # ask it to be, so an Escape can land after Leaf's hook has handed an
        # update over and before Claude Code reads its output.
        slow = shlex.quote(str(slow_prompt(place)))
        hooks: dict[str, list[dict]] = {
            event: [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"if [ -e {slow} ]; then sleep 6; fi",
                            "timeout": 20,
                        }
                    ]
                }
            ]
            for event in ("UserPromptSubmit", "PostToolBatch")
        }
        # And its hook before each shell command, which holds the session's answer to
        # a comment while the `boundary` step asks it to (`answer_hold`). A progress
        # line, `leaf thread reply --ephemeral`, is no answer, but one command may
        # post the progress line, make the edit and answer, so the hook holds a
        # command that runs `thread reply` more often than it passes `--ephemeral`.
        hold, held = (shlex.quote(str(path)) for path in answer_hold(place))
        hooks["PreToolUse"] = [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            f"[ -e {hold} ] || exit 0; "
                            "command=$(jq -r .tool_input.command); "
                            'replies=$(printf %s "$command" '
                            "| grep -o 'thread reply' | wc -l); "
                            'progress=$(printf %s "$command" '
                            "| grep -o -e --ephemeral | wc -l); "
                            f'[ "$replies" -gt "$progress" ] || exit 0; '
                            f"touch {held}; while [ -e {hold} ]; do sleep 0.1; done"
                        ),
                        "timeout": 120,
                    }
                ],
            }
        ]
        settings: dict[str, object] = {"hooks": hooks}
        if sandbox:
            # The README's settings ("Agent sandboxes"), which let Leaf's sandboxed
            # commands reach the bridge its hooks keep outside the sandbox.
            settings["sandbox"] = {
                "enabled": True,
                "failIfUnavailable": True,
                "network": {"allowedDomains": ["127.0.0.1"]},
            }
        cc = ClaudeCode(
            place,
            dict(os.environ),
            model=MODELS[ClaudeCodeHarness.name],
            settings=settings,
        )
        try:
            started = time.monotonic()
            cc.setup(place.page)
            with user_at(browser, place, cc, started) as user:
                yield (
                    user,
                    lambda: steps(cc, user, place),
                )
        finally:
            # A failed step's screen; once Claude Code exits there is none.
            cc.keep("end")
            cc.close()
