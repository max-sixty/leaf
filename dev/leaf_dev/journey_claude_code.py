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
  that answers it (`journey.run_journey`); with `--case working` it is sent during
  the user's own turn's shell command, which answers it;
- `mid-turn`: a comment sent during a shell command is picked up in that turn;
  its PostToolBatch context carries the exact input before another model call,
  rather than waiting for Stop;
- `ending`: two comments sent during a shell command, the second after the turn
  picked up the first, both enter that turn at its tool boundaries;
- `escape`: Escape during a shell command ends the turn; a comment sent afterwards
  opens a turn that answers it;
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
  compaction is done;
- `quit`: `/exit` ends the session, so its claim on the page is inactive and its
  watch has ended.

Between steps every comment sent so far has exactly one reply and a pickup, the
page's claim names the session with its turn closed, no Stop hook has continued a
turn with input, so each turn ends on its own answer, no delivery shows in the
terminal, and Leaf put no empty wake or notice in the conversation (`leaf_rows`).
Escape runs no Stop hook, so it leaves the turn open, and the watch its prompt
started, which waits while that turn runs, still running.

Each step also prints the rows Leaf put in the conversation the user reads, a nudge
among them, and, with an Escape, whether it left the turn open, a
watch running, and what the page's status read; the sample keeps the rows as each
step's `shown`. The session's screen at the end of each step and Claude Code's
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
from pathlib import Path

import click
import psutil

from leaf.delivery import DELIVERY, delivery_pointer_prompt, pickup_receipts
from leaf.event_log import read_events
from leaf.harness import (
    ClaudeCodeHarness,
    claude_code_live_turn,
    claude_code_registry,
)
from leaf.hook_transport import ATTENTION_OPENING, INLINE_OPENING
from leaf.leases import wait_is_live
from leaf.server import running_server
from leaf.service import claim_is_active, page_claim
from leaf.state import session_live, session_record, turn_open
from leaf_dev import ROOT
from leaf_dev.arms import (
    MODELS,
    PageClient,
    claude_environment,
    claude_home,
    run_leaf,
)
from leaf_dev.commands.journey import Isolation, Terminal, User, isolated, user_at
from leaf_dev.reply_phases import (
    claude_code_debug_records,
    claude_code_records,
    ends_turn,
    instant,
    transcript_records,
)
from leaf_dev.review_scenario import (
    REQUEST,
    SLEEP,
    USER_TURN,
    attempt,
    post,
    prepare,
    require,
    settled,
)

# How a hook context that hands a delivery over by its pointer begins.
POINTER_OPENING = delivery_pointer_prompt("00000000").partition(" id=")[0]

# The user's own turn, which leaves a comment handed to it unanswered.
DEFERRING_TURN = USER_TURN.replace(
    "Then reply with the single word done.",
    "Leave any Leaf comment unanswered in this turn, then reply with the single "
    "word done.",
)


class ClaudeCode(Terminal):
    """One interactive Claude Code session in a tmux pane, and the user at it."""

    def __init__(self, place: Isolation, argv: list[str], env: dict) -> None:
        super().__init__()
        self.pane = f"leaf-journey-claude-code-{os.getpid()}"
        self.home = place.root / "home"
        self.exited, self.kept = place.root / "exited", place.evidence / "screen.txt"
        self.debug = place.evidence / "debug.log"
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
        if self.session is None:
            return []
        logged = self.debug.read_text() if self.debug.exists() else ""
        return sorted(
            claude_code_records(native_records(self.home, self.session))
            + claude_code_debug_records(logged),
            key=lambda record: instant(record["received_at"]),
        )

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
    session = require(cc.session, "the session has no id")
    # The native records the steps so far have counted (`leaf_rows`).
    read: list[dict] = []

    def activity() -> str:
        """What the page's status reads: its canonical activity's kind."""
        served = run_leaf(ROOT, place.state, "page", "state", str(page), check=True)
        return json.loads(served.stdout)["activity"]["kind"]

    def answered(*names: str) -> Callable[[], bool]:
        return lambda: all(user.answered(name) for name in names) and cc.idle()

    def watched() -> bool:
        return wait_is_live(None, cc.session)

    def step(
        name: str,
        started: float,
        *names: str,
        escaped: str | None = None,
    ) -> None:
        sent.extend(names)
        settled(page, session, {name: user.ids[name] for name in sent})
        # A watch follows every turn, so no Stop hook continued one with input,
        # which would have put the reply to it in place of the turn's own answer,
        # and Claude Code printed no delivery, whose envelope names its format.
        require(
            not any(
                (attachment := record.get("attachment", {})).get("hookEvent") == "Stop"
                and any(
                    content.startswith((INLINE_OPENING, POINTER_OPENING))
                    for content in attachment.get("content") or []
                )
                for record in native_records(cc.home, session)
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
        records = native_records(cc.home, session)
        rows = leaf_rows(records[len(read) :])
        read[:] = records
        require(
            not {"empty", "notice"} & rows.keys(),
            f"{name}: Leaf put an empty wake or a notice in the conversation: {rows}",
        )
        details.append(
            "shown: "
            + (", ".join(f"{count} {kind}" for kind, count in rows.items()) or "none")
        )
        user.passed(name, started, *details)
        user.steps[-1]["shown"] = rows
        cc.keep(name)

    def closed(turn: str) -> bool:
        """Whether the page's claim has closed `turn`, or opened another after it."""
        return not turn_open(page_claim(page), turn)

    def escape(turn: str) -> None:
        """Press Escape on `turn` until Claude Code is idle or the claim has moved
        past it."""
        cc.escape(lambda: cc.idle() or closed(turn))

    def after_escape(name: str, turn: str) -> str:
        """What an Escape that ended `turn` left: the turn open, since Escape runs no
        Stop hook, and a watch running, which may already have woken a turn of its
        own."""
        cc.until(
            lambda: (
                watched()
                or require(page_claim(page), "the page has no claim")["turn"] != turn
            ),
            f"{name}: no watch after Escape",
            30,
        )
        return (
            f"after Escape: turn {'closed' if closed(turn) else 'open'}, "
            f"{'a' if watched() else 'no'} watch running, the page reads "
            f"{activity()}"
        )

    started = time.monotonic()
    user.release()
    cc.until(cc.idle, "release: the turn that answered did not end")
    step("release", started, "release")
    started = time.monotonic()
    cc.work()
    turn = require(page_claim(page), "the page has no claim")["turn"]
    mid_turn = user.comment("mid-turn")
    cc.until(answered("mid-turn"), "mid-turn: the comment was not answered")
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
    cc.work()
    turn = require(page_claim(page), "the page has no claim")["turn"]
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
    step("ending", started, "first", "ending")

    started = time.monotonic()
    cc.work()
    turn = require(page_claim(page), "the page has no claim")["turn"]
    escape(turn)
    escaped = after_escape("escape", turn)
    user.comment("escape")
    cc.until(answered("escape"), "escape: the comment was not answered")
    step("escape", started, "escape", escaped=escaped)

    started = time.monotonic()
    cc.work()
    turn = require(page_claim(page), "the page has no claim")["turn"]
    woken = user.comment("woken")
    # The turn reads the comment only at its next tool boundary, once its command
    # ends, so a watch that held the session's lease as the comment arrived leaves
    # it to the turn.
    time.sleep(2)
    require(
        cc.sleeping()
        and watched()
        and not pickup_receipts(read_events(page), phase="opened", input_id=woken),
        "woken: the comment did not wait for the running turn",
    )
    escape(turn)
    escaped = after_escape("woken", turn)
    # The stopped turn never read the comment, so the watch after Escape wakes for
    # it, and a turn of its own answers it.
    cc.until(answered("woken"), "woken: the watch after Escape did not answer it")
    user.comment("after-wake")
    cc.until(answered("woken", "after-wake"), "woken: the comments were not answered")
    step("woken", started, "woken", "after-wake", escaped=escaped)

    def drop(update: str) -> int:
        """Slow the session's other prompt and tool-batch hooks, and press Escape
        once Leaf's hook has handed `update` over and while the other still runs, so
        Claude Code drops what Leaf's hook returned. Returns how many records the
        conversation held as Escape was pressed."""
        slow_prompt(place).touch()
        try:
            cc.until(
                lambda: bool(
                    pickup_receipts(read_events(page), phase="opened", input_id=update)
                ),
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
    resolve = PageClient(url).post(
        {"kind": "resolve", "parent": comment, "attempt": attempt("resolve")}
    )
    resolved = next(
        event["id"]
        for event in resolve["events"]
        if event.get("attempt") == attempt("resolve")
    )
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
        lambda: bool(
            pickup_receipts(read_events(page), phase="opened", input_id=first)
        ),
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
    cc.work(DEFERRING_TURN)
    turn = require(page_claim(page), "the page has no claim")["turn"]
    deferred = user.comment("deferred")
    cc.until(lambda: closed(turn), "deferred: the user's turn did not end")
    require(
        not user.answered("deferred"),
        "deferred: the user's turn answered the comment it was told to leave",
    )
    cc.until(
        answered("deferred"), "deferred: the comment the turn left was not answered"
    )

    def hook_contexts(event: str) -> list[str]:
        return [
            content
            for record in native_records(cc.home, session)
            if (attachment := record.get("attachment", {})).get("hookEvent") == event
            for content in attachment.get("content") or []
        ]

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

    started = time.monotonic()
    cc.say("/exit")
    cc.until(cc.exited.exists, "quit: Claude Code did not exit", 60)
    require(
        not session_live(session_record(session)),
        "quit: the session ended without Leaf's SessionEnd",
    )
    require(
        not claim_is_active(page_claim(page)),
        "quit: the ended session's claim on the page is still active",
    )
    require(not watched(), "quit: the ended session's watch still runs")
    user.passed("quit", started)


def leaf_rows(records: list[dict]) -> dict[str, int]:
    """How many rows of each kind Leaf put in the conversation the user reads, among
    native `records`: a wake (`hooks.json`'s background Stop hook, a task
    notification whose summary the registration names), a nudge through session
    messaging, a notice the hooks module logged, and a hook's error. A wake or
    nudge no hook delivery or reminder follows before the next one, or the user's
    next prompt, also counts as `empty`: a turn opened for input another turn had
    already taken. A row counts whether or not the hooks module draws it."""
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
            if "<summary>Leaf: new input</summary>" in text
            else "nudge"
            # The words of `ClaudeCodeHarness.nudge`.
            if "has new input, which arrives with this message." in text
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
        elif attachment.get("type") == "hook_additional_context" and any(
            str(part).startswith((INLINE_OPENING, POINTER_OPENING))
            or ATTENTION_OPENING in str(part)
            for part in attachment.get("content") or []
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
def answering(browser, *, sandbox: bool) -> Generator[tuple[User, Callable]]:
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
                require(page_claim(place.page), "the page has no claim")["id"]
                == session,
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
