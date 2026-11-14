"""The `claude-code` journey: a real interactive Claude Code session with Leaf's
plugin, and the steps a user takes at its terminal.

    uv run leaf-dev journey claude-code [--forks | --fork-work]

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

A fork of the conversation answers a thread message the session hasn't received
(`leaf.forks`), and would answer the delivery steps' questions in the session's
place, so by default the session runs with forks off (`LEAF_FORK_REPLIES=off`).
`--forks` turns them on, and runs the fork steps in place of the delivery steps.

The steps, in order; `setup`, `release`, `mid-turn`, `escape` and `quit` are those
more than one harness takes, as `journey.Terminal` has them:

- `setup`;
- `release`, which asks for work, so with `--forks` a fork hands it over and the
  session answers it as before.

Then the delivery steps:

- `mid-turn`, whose PostToolBatch context carries the exact input before another
  model call, rather than waiting for Stop;
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
- `withdrawn`: the same for an update that owes nothing, a resolve of a thread whose
  comment had no answer yet, which must still reach a hook's context after Escape;
- `boundary`: a comment that arrives while a wake's turn runs, handed over at a tool
  boundary whose other hook sleeps, and Escape then ends that turn. The watch the
  wake's prompt started wakes the session, whose prompt names the boundary's comment
  as owed rather than handing it over again, so it is handed over once, and a turn
  answers both comments;
- `deferred`: the user's own turn, told to leave Leaf's comments for later, is
  handed a comment at a tool boundary and ends on its answer with the comment
  unanswered, and no Stop hook continues it over the comment. The watch wakes a
  turn of its own whose prompt names the owed answer, and that turn answers it;
- `compacting`: a comment sent while `/compact` runs at the idle prompt wakes the
  session once the compaction ends, and a turn of its own answers it. Compaction
  runs no prompt or Stop hook, so the watch the last turn's Stop started keeps
  running through it, and Claude Code holds that watch's wake until the
  compaction is done.

Or, with `--forks`, the fork steps, each timed from the comment's admission to the
reply, with the fork's own time and tokens from its record in the page's
diagnostics (`fork_outcome`):

- `fork-idle`: with the session idle, a question the conversation already answers
  gets the agent's working line from a fork as its first reply, and the session
  wakes for it and answers it;
- `fork-work`: a request for a change to the page, sent during the user's own
  turn's shell command, gets the fork's working line before the command ends, and
  the session picks it up and answers it in that turn or the next.

With `--fork-work` (`LEAF_FORK_WORK=on`), `fork-idle`'s question goes to a fork that
does the work: the line fork judges it a fork's, and a fork spawned from the
conversation, in a turn of its own that picked the comment up, answers it in the
thread itself with `leaf thread reply` while the session stays idle. Then
`fork-follow-up`: a question a fork takes and looks up in the page's source, and the
user's further message in its thread sent as the fork starts, which the fork's next
tool boundary hands it: the fork's turn picks it up and the fork answers it, while the
session stays idle. Then `fork-resume`: once that fork's run has ended, a further
message in its thread goes to the same fork, which Claude Code resumes under the same
agent id in a new turn of its own that picks the message up and answers it, while the
session stays idle; the session then wakes for Claude Code's notice that the resumed
fork finished, and doesn't answer the message again. Then `fork-todo`: a question a
fork takes, whose rest the user leaves as work for later, which the fork answers with
a to-do on the thread (`--todo`), ending its turn as `todo`; Leaf's wake for that
to-do starts a turn of the idle session, whose prompt hook hands it the line naming
the to-do, and the session does the work and ends the to-do or leaves it open on its
list, as it judges. `fork-work` then checks
that the session's next turn didn't answer the forks' questions again.

Then `quit`, by `/exit`.

After each step the journey requires what every harness must hold between steps
(`journey.Terminal.between`), with the watch as what listens for the session; and
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
from datetime import datetime
from functools import partial
from pathlib import Path

import click
import psutil

from leaf.delivery import DELIVERY, delivery_pointer_prompt
from leaf.event_log import read_events
from leaf.harness import (
    NUDGE_WORDS,
    ClaudeCodeHarness,
    claude_code_live_turn,
    claude_code_registry,
)
from leaf.hook_transport import ATTENTION_OPENING, INLINE_OPENING
from leaf.server import running_server
from leaf.service import page_claim
from leaf.state import turn_open
from leaf.todos import TodoReading
from leaf_dev import ROOT
from leaf_dev.arms import MODELS, PageClient, claude_environment, claude_home
from leaf_dev.commands.journey import (
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
    claimed,
    picked_up,
    post,
    prepare,
    require,
)

# The user's further message in the thread of `fork-lookup`'s question, sent as the
# fork that took the question starts.
FOLLOW_UP = "And how many of them mention the migration?"
# The user's next message in that thread, sent once the fork's run has ended.
RESUMED = "Which of those cards has the longest text?"

# How a hook context that hands a delivery over by its pointer begins.
POINTER_OPENING = delivery_pointer_prompt("00000000").partition(" id=")[0]

# The user's own turn, which leaves a comment handed to it unanswered.
DEFERRING_TURN = USER_TURN.replace(
    "Then reply with the single word done.",
    "Leave any Leaf comment unanswered in this turn, then reply with the single "
    "word done.",
)


def claude_code_environment(place: Isolation, **extra: str) -> dict[str, str]:
    """The environment of an interactive Claude Code session in `place`, `extra`
    added: a home holding only the host's login (`arms.claude_home`), whose own
    record says onboarding is done and trusts the session's cwd, so the session
    opens at its prompt."""
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
        home, XDG_STATE_HOME=str(place.state), TERM="tmux-256color", **extra
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
        # subagents' join the evidence, where `leaf-dev timeline` reads them.
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


def steps(
    cc: ClaudeCode,
    user: User,
    place: Isolation,
    *,
    forks: bool,
    fork_work: bool = False,
) -> None:
    """The steps after setup, as the module docstring lists them: with `forks` the
    fork steps, else the delivery steps."""
    page, session = place.page, cc.session
    step = partial(cc.passed, user, page)

    def answered(*names: str) -> Callable[[], bool]:
        return lambda: all(user.answered(name) for name in names) and cc.idle()

    def closed(turn: str) -> bool:
        """Whether the page's claim has closed `turn`, or opened another after it."""
        return not turn_open(page_claim(page), turn)

    def hook_contexts(event: str) -> list[str]:
        """The contexts the hooks of `event` put in the conversation, one a hook."""
        return [
            content
            for record in native_records(cc.home, session)
            if (attachment := record.get("attachment", {})).get("hookEvent") == event
            for content in attachment.get("content") or []
        ]

    def delivered() -> None:
        """The delivery steps, from `mid-turn` to `compacting`."""
        started = time.monotonic()
        mid_turn = cc.mid_turn(user, page)
        require(
            any(
                event["id"] == mid_turn
                for record in native_records(cc.home, session)
                if (attachment := record.get("attachment", {})).get("hookEvent")
                == "PostToolBatch"
                for content in attachment["content"]
                if content.startswith(INLINE_OPENING + "\n")
                for batch in json.loads(content.split("\n")[1])["batches"]
                for event in batch["events"]
            ),
            "mid-turn: PostToolBatch did not hand the exact input to the model",
        )
        step("mid-turn", started, "mid-turn")

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
            f"{activity(page)}"
        )
        # The stopped turn never read the comment, so the watch after Escape wakes for
        # it, and a turn of its own answers it.
        cc.until(answered("woken"), "woken: the watch after Escape did not answer it")
        user.comment("after-wake")
        cc.until(
            answered("woken", "after-wake"), "woken: the comments were not answered"
        )
        step("woken", started, "woken", "after-wake", detail=escaped)

        def drop(update: str) -> int:
            """Slow the session's other prompt and tool-batch hooks, and press Escape
            once Leaf's hook has handed `update` over and while the other still runs, so
            Claude Code drops what Leaf's hook returned. Returns how many records the
            conversation held as Escape was pressed."""
            slow_prompt(place).touch()
            try:
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
        resolved = PageClient(url).post(
            {"kind": "resolve", "parent": comment, "attempt": attempt("resolve")}
        )["id"]
        held = drop(resolved)
        cc.until(
            lambda: delivery_ended(since(held), resolved),
            "withdrawn: the resolve Escape dropped never reached the agent",
            120,
        )
        step("withdrawn", started)

        started = time.monotonic()
        first = user.comment("first-wake")
        cc.until(
            lambda: bool(picked_up(page, first)),
            "boundary: the wake was not handed its comment",
        )
        boundary = user.comment("boundary")
        drop(boundary)
        cc.until(
            answered("first-wake", "boundary"),
            "boundary: the comment Escape dropped was not answered",
            150,
        )
        # Escape during a tool boundary's hooks keeps that boundary's context, so the
        # comment is in the conversation once and the woken turn only names it as owed.
        handed = deliveries(native_records(cc.home, session), boundary)
        require(
            len(handed) == 1,
            f"boundary: the comment Escape kept was handed over {len(handed)} times",
        )
        step("boundary", started, "first-wake", "boundary")

        started = time.monotonic()
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
            not any(ATTENTION_OPENING in content for content in hook_contexts("Stop")),
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

    def forked() -> None:
        """The fork steps, `fork-idle` and `fork-work`."""

        def picked(name: str) -> list[str]:
            """The turns that picked up step `name`'s comment."""
            return picked_up(page, user.ids[name])

        def forked_work(started: float) -> None:
            """`fork-idle` with forks that do the work: its fork judges the question a
            fork's and posts the agent's working line, and a fork it spawns, in a
            turn of its own that picked the comment up, answers it in the thread with
            `leaf thread reply`, while the session stays idle."""
            comment = user.ids["fork-idle"]
            cc.until(
                lambda: user.answered("fork-idle"),
                "fork-idle: no fork answered it",
            )

            def records() -> list[dict]:
                return [
                    record
                    for record in (user.forks() if user.forks else [])
                    if comment in record["inputs"]
                ]

            taken = require(
                next((r for r in records() if r["outcome"] == "take"), None),
                f"fork-idle: no fork took the work: {[fork_summary(r) for r in records()]}",
            )
            cc.until(
                lambda: any(r.get("step") == "end" for r in records()),
                "fork-idle: the turn of the fork that took the work never ended",
                60,
            )
            run_end = next(r for r in records() if r.get("step") == "end")
            require(
                run_end["outcome"] in ("answer", "todo"),
                f"fork-idle: the fork gave the thread back: {fork_summary(run_end)}",
            )
            require(
                picked_up(page, comment) == [taken["turn"]],
                "fork-idle: a turn other than the fork's picked the comment up: "
                f"{picked_up(page, comment)}",
            )
            [reply] = require(
                answers(page, comment), "fork-idle: the comment has no answer"
            )
            # Nothing wakes the idle session for a comment its fork answered: it
            # takes the comment in, settled, with the clerk's line, at its next turn.
            require(cc.idle(), "fork-idle: the session woke for its fork's answer")
            timings = user.end.timings()[user.ids["fork-idle"]]["milestones"]
            require(
                timings["first_reply"]["event_id"] == taken["line"],
                "fork-idle: the fork's working line was not the comment's first reply",
            )
            step(
                "fork-idle",
                started,
                detail=(
                    f"`fork-idle` had its first reply after "
                    f"{timings['first_reply']['elapsed_s']:.1f} s, and the fork "
                    f"{taken['agent']} answered it in its own turn, which ended after "
                    f"{run_end['elapsedMs'] / 1000:.1f} s: {reply['text'][:200]!r}"
                ),
            )

        def followed_up(started: float) -> tuple[str, dict]:
            """`fork-follow-up`: the user's further message in the thread of a
            question a fork took, sent as the fork starts, reaches the fork at its
            next tool boundary, in the fork's own turn, and the fork answers it while
            the session stays idle. Returns the question's id and the fork's take."""
            # Posted apart from the user's timed comments, whose timing reads each one's
            # own answer: the fork's answers the further message, which settles both.
            url = require(running_server(page), "the page has no server")["url"]
            asked = post(url, "fork-lookup")

            def records() -> list[dict]:
                return [
                    record
                    for record in (user.forks() if user.forks else [])
                    if asked in record["inputs"]
                ]

            cc.until(
                lambda: any(record["outcome"] == "take" for record in records()),
                "fork-follow-up: no fork took the question",
                60,
            )
            taken = next(record for record in records() if record["outcome"] == "take")
            more = PageClient(url).post(
                {
                    "kind": "reply",
                    "parent": asked,
                    "attempt": attempt("fork-follow-up"),
                    "text": FOLLOW_UP,
                }
            )["id"]
            cc.until(
                lambda: bool(answers(page, more)) and cc.idle(),
                "fork-follow-up: nobody answered the further message",
                150,
            )
            require(
                picked_up(page, asked) == [taken["turn"]]
                and picked_up(page, more) == [taken["turn"]],
                "fork-follow-up: a turn other than the fork's picked the thread up: "
                f"{picked_up(page, asked)}, {picked_up(page, more)}",
            )
            events = {event["id"]: event for event in read_events(page)}
            [reply] = answers(page, more)
            after = (
                datetime.fromisoformat(reply["ts"])
                - datetime.fromisoformat(events[more]["ts"])
            ).total_seconds()
            step(
                "fork-follow-up",
                started,
                detail=(
                    f"`fork-follow-up`: {taken['agent']} took the question, its turn "
                    f"picked up the further message, and it answered that "
                    f"{after:.1f} s after it was sent: {reply['text'][:200]!r}"
                ),
            )
            return asked, taken

        def resumed(started: float, asked: str, first: dict) -> None:
            """`fork-resume`: once the run of the fork that answered `asked`'s thread
            has ended, the user's next message there goes to the same fork, resumed
            under its agent id in a new turn that picks the message up and answers
            it while the session stays idle. The session's turn for Claude Code's
            notice that the fork finished doesn't answer it again."""
            url = require(running_server(page), "the page has no server")["url"]

            def records(input_id: str) -> list[dict]:
                return [
                    record
                    for record in (user.forks() if user.forks else [])
                    if input_id in record["inputs"]
                ]

            def decided(input_id: str) -> dict | None:
                return next(
                    (
                        record
                        for record in records(input_id)
                        if record["outcome"] in ("take", "hand_over", "dropped")
                    ),
                    None,
                )

            def agent_of(turn: str) -> str | None:
                return next(
                    (
                        record["agentId"]
                        for record in (user.forks() if user.forks else [])
                        if record.get("step") == "start" and record["turn"] == turn
                    ),
                    None,
                )

            cc.settle(
                lambda: any(r.get("step") == "end" for r in records(asked)),
                "fork-resume: the fork that answered the thread never ended its run",
            )
            agent = require(
                agent_of(first["turn"]), "fork-resume: the first fork never started"
            )
            again = PageClient(url).post(
                {
                    "kind": "reply",
                    "parent": asked,
                    "attempt": attempt("fork-resume"),
                    "text": RESUMED,
                }
            )["id"]
            cc.until(lambda: decided(again), "fork-resume: no fork decided on it", 60)
            taken = require(decided(again), "fork-resume: no fork decided on it")
            require(
                taken["outcome"] == "take" and taken.get("resume") == agent,
                f"fork-resume: the message did not go back to {agent}: "
                f"{fork_summary(taken)}",
            )
            sent = instant(next(e["ts"] for e in read_events(page) if e["id"] == again))

            def woken() -> list[dict]:
                """The session's turns since the message was sent, as Claude Code
                recorded each start."""
                return [
                    record
                    for record in claude_code_records(native_records(cc.home, session))
                    if record["type"] == "turn_start"
                    and instant(record["received_at"]) > sent
                ]

            # The resumed run's end starts a turn on the session, for Claude Code's
            # notice of it, which must come after the answer and leave it the only one.
            cc.settle(
                lambda: (
                    any(r.get("step") == "end" for r in records(again))
                    and any(t.get("origin") == "task_notification" for t in woken())
                ),
                "fork-resume: the session never took Claude Code's notice that the "
                "resumed fork finished",
            )
            run_end = next(r for r in records(again) if r.get("step") == "end")
            replies = require(
                answers(page, again), "fork-resume: nobody answered the message"
            )
            require(
                instant(woken()[0]["received_at"]) > instant(replies[0]["ts"]),
                "fork-resume: the session started a turn before the fork answered",
            )
            require(
                picked_up(page, again) == [taken["turn"]],
                "fork-resume: a turn other than the resumed fork's picked the message "
                f"up: {picked_up(page, again)}",
            )
            require(
                len(replies) == 1,
                f"fork-resume: the message has {len(replies)} answers",
            )
            events = {event["id"]: event for event in read_events(page)}

            def after(event_id: str) -> float:
                return (
                    datetime.fromisoformat(events[event_id]["ts"])
                    - datetime.fromisoformat(events[again]["ts"])
                ).total_seconds()

            step(
                "fork-resume",
                started,
                detail=(
                    f"`fork-resume`: {agent}'s working line came "
                    f"{after(taken['line']):.1f} s after the message was sent, and its "
                    f"answer from a new turn at {after(replies[0]['id']):.1f} s; the "
                    f"resumed run took {run_end['elapsedMs'] / 1000:.1f} s: "
                    f"{replies[0]['text'][:200]!r}"
                ),
            )

        def opened_todo(started: float) -> None:
            """`fork-todo`: a question a fork takes, whose rest the user leaves for
            later, gets the fork's answer with a to-do on the thread, from the fork's
            own turn. The fork's end wakes the idle session for the to-do (no notice
            of Claude Code's does, since a spawned fork's first run sends none), and
            the woken turn's prompt hook hands it the line naming the to-do. When to
            do the work is the session's call: it ends the to-do done, or leaves it
            open on its list."""
            comment = user.comment("fork-todo")

            def records() -> list[dict]:
                return [
                    record
                    for record in (user.forks() if user.forks else [])
                    if comment in record["inputs"]
                ]

            cc.until(
                lambda: any(
                    r["outcome"] in ("take", "hand_over", "dropped") for r in records()
                ),
                "fork-todo: no fork decided on it",
                60,
            )
            taken = require(
                next((r for r in records() if r["outcome"] == "take"), None),
                f"fork-todo: no fork took it: {[fork_summary(r) for r in records()]}",
            )
            cc.until(
                lambda: any(r.get("step") == "end" for r in records()),
                "fork-todo: the turn of the fork that took it never ended",
                180,
            )
            run_end = next(r for r in records() if r.get("step") == "end")
            require(
                run_end["outcome"] == "todo",
                f"fork-todo: the fork opened no to-do: {fork_summary(run_end)}",
            )
            [todo] = run_end["todos"]
            replies = require(answers(page, comment), "fork-todo: nobody answered it")
            require(
                replies[0].get("turn") == taken["turn"] and replies[0].get("todo"),
                "fork-todo: the first answer was not the fork's, with the to-do",
            )
            ended_at = instant(run_end["ts"])

            def woken() -> list[dict]:
                """The session's turns since the fork's run ended, as Claude Code
                recorded each start."""
                return [
                    record
                    for record in claude_code_records(native_records(cc.home, session))
                    if record["type"] == "turn_start"
                    and instant(record["received_at"]) > ended_at
                ]

            def done() -> dict | None:
                return TodoReading(read_events(page)).ends.get(todo)

            def told() -> bool:
                return any(
                    todo in context for context in hook_contexts("UserPromptSubmit")
                )

            cc.until(lambda: bool(woken()), "fork-todo: nothing woke the session", 60)
            first = woken()[0]
            require(
                first.get("origin") == "leaf_wake",
                f"fork-todo: the session's first turn after the fork's end began "
                f"with {first.get('origin')}, not Leaf's wake",
            )
            # When the session does the work is its own call; Leaf owes it the
            # line, and the to-do stays on the agent until the session ends it.
            cc.settle(
                told, "fork-todo: no prompt hook handed the session the line naming it"
            )
            require(
                picked_up(page, comment) == [taken["turn"]],
                "fork-todo: a turn other than the fork's picked the question up: "
                f"{picked_up(page, comment)}",
            )
            outcome = done()
            require(
                outcome is None or outcome["state"] == "done",
                f"fork-todo: the session ended the to-do {outcome and outcome['state']}",
            )
            if outcome is None:
                require(
                    any(t["id"] == todo for t in TodoReading(read_events(page)).owed),
                    "fork-todo: the to-do is neither open nor done",
                )
            timings = user.end.timings()[comment]["milestones"]
            scheduled = (
                "left the to-do open for later"
                if outcome is None
                else "ended the to-do done "
                + str(
                    round(
                        next(
                            instant(e["ts"])
                            for e in read_events(page)
                            if e["kind"] == "todo_end" and e["todo"] == todo
                        )
                        - ended_at
                    )
                )
                + " s after the fork's end"
            )
            # Named, so what holds between steps requires the question answered once,
            # by the fork, from this step on.
            step(
                "fork-todo",
                started,
                "fork-todo",
                detail=(
                    f"`fork-todo`: {taken['agent']}'s working line came "
                    f"{timings['first_reply']['elapsed_s']:.1f} s after the comment, "
                    f"and its answer, opening the to-do “{replies[0]['todo']}”, from "
                    f"its own turn, which ended after "
                    f"{run_end['elapsedMs'] / 1000:.1f} s. Leaf woke the session "
                    f"{instant(first['received_at']) - ended_at:.1f} s after that, "
                    f"its prompt hook handed it the line, and it {scheduled}; the "
                    f"thread has {len(replies)} answer(s)"
                ),
            )

        def lined(name: str) -> float:
            """Require the fork on step `name`'s comment to have posted the agent's
            working line, as the comment's first reply, and handed the comment over;
            the seconds to that reply."""
            fork = require(user.fork(name), f"{name}: no fork decided on the comment")
            require(
                fork["outcome"] == "hand_over" and "line" in fork,
                f"{name}: the fork posted no working line: {fork_summary(fork)}",
            )
            timings = user.end.timings()[user.ids[name]]["milestones"]
            require(
                timings["first_reply"]["event_id"] == fork["line"],
                f"{name}: the fork's working line was not the comment's first reply",
            )
            return timings["first_reply"]["elapsed_s"]

        started = time.monotonic()
        user.comment("fork-idle")
        if fork_work:
            forked_work(started)
            asked, taken = followed_up(time.monotonic())
            resumed(time.monotonic(), asked, taken)
            opened_todo(time.monotonic())
        else:
            cc.until(answered("fork-idle"), "fork-idle: the session did not answer it")
            first = lined("fork-idle")
            require(
                bool(picked("fork-idle")), "fork-idle: no turn picked the comment up"
            )
            step(
                "fork-idle",
                started,
                "fork-idle",
                detail=f"`fork-idle` had its first reply after {first:.1f} s",
            )

        started = time.monotonic()
        turn = cc.user_turn(page)
        user.comment("fork-work")
        cc.until(
            lambda: user.fork("fork-work") or not cc.sleeping(),
            "fork-work: no fork decided on the comment",
        )
        require(
            user.fork("fork-work"),
            "fork-work: the user's command ended before a fork decided on the comment",
        )
        cc.until(answered("fork-work"), "fork-work: the session did not answer it")
        first = lined("fork-work")
        # The session's turn once it answered, which is the user's own or the next.
        last = claimed(page)["turn"]
        took = picked("fork-work")
        require(
            bool(took) and took[0] in (turn, last),
            "fork-work: neither the user's turn nor the next picked the request up",
        )
        where = "the user's turn" if took[0] == turn else "the next turn"
        if fork_work:
            require(
                len(answers(page, user.ids["fork-idle"])) == 1,
                "fork-idle: the session answered again the comment its fork answered",
            )
        step(
            "fork-work",
            started,
            "fork-work",
            detail=f"`fork-work` had its first reply after {first:.1f} s, in {where}",
        )

    started = time.monotonic()
    cc.release(user)
    fork = user.fork("release")
    step(
        "release",
        started,
        "release",
        detail=None if fork is None else f"`release`: {fork_summary(fork)}",
    )
    if forks:
        forked()
    else:
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
            if content.startswith(INLINE_OPENING + "\n")
            for batch in json.loads(content.split("\n")[1])["batches"]
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
def answering(
    browser, *, sandbox: bool, forks: bool, fork_work: bool = False
) -> Generator[tuple[User, Callable]]:
    """The user at the page an interactive Claude Code session serves, once it has,
    and the steps that follow: with `forks`, forks of its conversation answer the
    user's thread messages, and with `fork_work` a fork does the work of one the
    line fork judges a fork's."""
    require(shutil.which("tmux") is not None, "the claude-code journey drives tmux")

    environment = partial(
        claude_code_environment,
        **({} if forks else {"LEAF_FORK_REPLIES": "off"}),
        **({"LEAF_FORK_WORK": "on"} if fork_work else {}),
    )
    with isolated("claude-code", environment) as place:
        prepare(ROOT, place.state, place.page)
        # Another plugin's prompt hook, slower than Leaf's while the `dropped` steps
        # ask it to be, so an Escape can land after Leaf's hook has handed an
        # update over and before Claude Code reads its output.
        slow = shlex.quote(str(slow_prompt(place)))
        settings: dict[str, object] = {
            "hooks": {
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
        }
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
                    lambda: steps(cc, user, place, forks=forks, fork_work=fork_work),
                )
        finally:
            # A failed step's screen; once Claude Code exits there is none.
            cc.keep("end")
            cc.close()
