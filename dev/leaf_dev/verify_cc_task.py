"""Run a real interactive Claude Code session with Leaf's plugin and check what it
leaves.

    uv run leaf-dev verify-cc-task [--hooks-module]

The suite stands in for Claude Code around Leaf's hooks (`hooks.json`, and
`tests/claude_code_driver.mjs` for the hooks module); this runs Claude Code itself,
in its terminal interface, with this working tree's payload as its plugin
(`--plugin-dir`) under a throwaway home (`arms.claude_home`) whose only content is
the host's login. `--hooks-module` turns the plugin's `hooks_module` option on, so
Leaf's hooks module keeps the watch in place of `hooks.json`'s background Stop hook.
The command is then the user: it types into the session through a tmux pane,
presses Escape, and posts comments to the served page as a tab would. It reads the
page's log and claim in process, and stops at the first check that fails.

The journey, in order:

- `setup`: the user asks for a page to review; Claude Code serves it, and a watch
  holds the session's pages once its turn ends;
- `idle`: a comment posted while the session is idle opens a turn that answers it;
- `mid-turn`: a comment posted during a shell command is picked up in that turn;
- `escape`: Escape during a shell command ends the turn; a comment posted
  afterwards opens a turn that answers it;
- `woken`: a comment posted during a shell command wakes the watch, and Escape
  ends that turn while the command still runs, before the turn reads the comment;
  a comment posted afterwards is answered, and so is the first, carried by the
  next prompt;
- `quit`: `/exit` ends the session, so its claim on the page is inactive and its
  watch has ended.

Between steps every comment posted so far has exactly one reply and a pickup, and
the page's claim names the session with its turn closed. With the hooks module,
Escape closes the turn and a watch runs after each turn, an interrupted one
included. Without it, what follows an Escape is reported rather than required: the
watch from before goes on only if it has not woken, and otherwise admission's nudge
carries the next comment.

Each step prints when the session picked its comments up and answered them,
counted from the post, and whether the page nudged the session; a step with an
Escape also prints whether it left the turn open, a watch running, and what the
page's banner read. That is the reading that compares the two carriers.

It needs tmux, and spends a few model turns on the host's Claude Code login, so CI
does not run it. The session's screen at the end of each step, Claude Code's debug
log and the page's log stay in a run directory under `.tmp/verify-cc/`. The session's home, page and state
home live in a temporary directory, removed when every check passes and kept, with
its path printed, when one fails.
"""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import click
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.leases import wait_is_live
from leaf.server import running_server
from leaf.service import claim_is_active, page_claim
from leaf.state import session_record

from leaf_dev import ROOT
from leaf_dev.arms import (
    MODELS,
    claude_environment,
    claude_home,
    extract_payload,
    run_directory,
    run_leaf,
)
from leaf_dev.codex_task import STEP_LIMIT
from leaf_dev.review_scenario import (
    REQUEST,
    answers,
    comment_id,
    post,
    prepare,
    require,
    settled,
)

# A command no other process on the host runs, so its process says the user's turn
# is in its shell step.
SLEEP = "time.sleep(25.17)"
USER_TURN = (
    f"Run `python3 -c 'import time; {SLEEP}'` with the Bash tool in the foreground. "
    "Then, in a separate tool call, run `printf 'verified\\n'`. Then reply with the "
    "single word done."
)


class ClaudeCode:
    """One interactive Claude Code session in a tmux pane, and the user at it."""

    def __init__(
        self, root: Path, run: Path, cwd: Path, argv: list[str], env: dict
    ) -> None:
        self.pane = f"leaf-verify-cc-{os.getpid()}"
        self.exited, self.kept = root / "exited", run / "screen.txt"
        self.session: str | None = None
        # The environment's values reach the pane through tmux, so no file holds
        # them; the script names them, and drops whatever else the tmux server's
        # own environment adds.
        script = root / "claude.sh"
        script.write_text(
            f"cd {shlex.quote(str(cwd))}\n"
            # Claude Code reads its directory from the shell's PWD.
            f"keep=' {' '.join(env)} PWD '\n"
            "for name in $(compgen -e); do\n"
            '  [[ $keep == *" $name "* ]] || unset "$name" 2> /dev/null\n'
            "done\n"
            f"{shlex.join(argv)} 2> {shlex.quote(str(run / 'stderr.txt'))}\n"
            f"echo $? > {shlex.quote(str(self.exited))}\n"
        )
        assignments = [arg for item in env.items() for arg in ("-e", "=".join(item))]
        self.tmux("new-session", "-d", "-s", self.pane, "-x", "200", "-y", "50",
                  "-c", str(cwd), *assignments, f"bash {shlex.quote(str(script))}")  # fmt: skip
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

    def keep(self, label: str) -> None:
        """Add the pane's screen to the evidence. Claude Code clears what scrolls
        off, so each step keeps its own."""
        if shown := self.tmux("capture-pane", "-p", "-S", "-", "-t", self.pane):
            with self.kept.open("a") as kept:
                kept.write(f"──── {label} ────\n{shown}\n")

    def say(self, text: str) -> None:
        """Type one prompt and send it."""
        self.tmux("send-keys", "-t", self.pane, "-l", text)
        time.sleep(0.5)
        self.tmux("send-keys", "-t", self.pane, "Enter")

    def escape(self) -> None:
        """Press Escape until the turn has ended. A second press on an idle prompt
        opens Claude Code's rewind menu, so each waits to see the first land."""
        for _ in range(3):
            self.tmux("send-keys", "-t", self.pane, "Escape")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if self.idle():
                    return
                time.sleep(0.25)
        raise click.ClickException(f"the turn went on after Escape\n{self.screen()}")

    def idle(self) -> bool:
        """Whether Claude Code's own record says no turn runs."""
        turn = ClaudeCodeHarness(session=self.session, agent="Claude").live_turn()
        return turn is not None and turn["state"] == "idle"

    def sleeping(self) -> bool:
        """Whether the user's turn is in its shell step."""
        return (
            subprocess.run(
                ["pgrep", "-f", SLEEP.replace("(", r"\(").replace(")", r"\)")],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )

    def until(
        self, done: Callable[[], object], what: str, limit: float = STEP_LIMIT
    ) -> None:
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            if done():
                return
            require(not self.exited.exists(), f"Claude Code exited\n{self.screen()}")
            time.sleep(0.5)
        raise click.ClickException(f"{what} within {limit:.0f} s\n{self.screen()}")

    def close(self) -> None:
        self.tmux("kill-session", "-t", self.pane)


def moment(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


def timings(page: Path, step: str) -> str:
    """When the session picked a step's comment up and answered it, counted from
    the post."""
    events = read_events(page)
    posted = comment_id(page, step)
    sent = moment(next(e["ts"] for e in events if e["id"] == posted))
    picked = next(
        moment(e["ts"])
        for e in events
        if e["kind"] == "pickup" and posted in e["events"]
    )
    [reply] = answers(page, step)
    return (
        f"`{step}` picked up after {(picked - sent).total_seconds():.1f} s, "
        f"answered after {(moment(reply['ts']) - sent).total_seconds():.0f} s"
    )


def journey(cc: ClaudeCode, page: Path, state: Path, module: bool) -> None:
    posted: list[str] = []

    def activity() -> str:
        """What the page's banner reads: its canonical activity's kind."""
        served = run_leaf(ROOT, state, "page", "state", str(page), check=True)
        return json.loads(served.stdout)["activity"]["kind"]

    def answered(*steps: str) -> Callable[[], bool]:
        return lambda: all(answers(page, step) for step in steps) and cc.idle()

    def watched() -> bool:
        return wait_is_live(None, cc.session)

    def nudged() -> object:
        return page_claim(page).get("messaged_ending")

    def step(
        name: str,
        started: float,
        *steps: str,
        before: object = None,
        escaped: str | None = None,
    ) -> None:
        posted.extend(steps)
        settled(page, cc.session, posted)
        # The turn that answers ends with a watch running, under either carrier.
        cc.until(watched, f"{name}: no watch holds the session's pages", 60)
        details = [escaped] if escaped else []
        details += [timings(page, posted_step) for posted_step in steps]
        if steps:
            details.append("nudged" if nudged() != before else "not nudged")
        click.echo(
            f"{name}: passed in {time.monotonic() - started:.0f} s"
            + "".join(f"\n  {detail}" for detail in details)
        )
        cc.keep(name)

    def after_escape(name: str) -> str:
        """What an Escape left: required with the hooks module, reported without."""
        cc.until(
            lambda: page_claim(page)["turn_closed"] is not None or not module,
            f"{name}: Escape left the turn open",
            30,
        )
        if module:
            cc.until(watched, f"{name}: no watch after Escape", 30)
        closed = page_claim(page)["turn_closed"] is not None
        return (
            f"after Escape: turn {'closed' if closed else 'open'}, "
            f"{'a' if watched() else 'no'} watch running, the page reads "
            f"{activity()}"
        )

    started = time.monotonic()
    cc.say(REQUEST)
    cc.until(lambda: page_claim(page) is not None, "setup: the page was not claimed")
    cc.session = page_claim(page)["id"]
    cc.until(
        lambda: running_server(page) is not None and cc.idle() and watched(),
        "setup: the page was not served with the session idle and a watch running",
    )
    step("setup", started)

    started = time.monotonic()
    before = nudged()
    post(page, "idle")
    cc.until(answered("idle"), "idle: the comment was not answered")
    step("idle", started, "idle", before=before)

    started = time.monotonic()
    cc.say(USER_TURN)
    cc.until(cc.sleeping, "mid-turn: the user's turn did not start its command")
    turn = page_claim(page)["turn"]
    before = nudged()
    post(page, "mid-turn")
    cc.until(answered("mid-turn"), "mid-turn: the comment was not answered")
    require(
        any(
            event["kind"] == "pickup"
            and event["turn"] == turn
            and comment_id(page, "mid-turn") in event["events"]
            for event in read_events(page)
        ),
        f"mid-turn: the comment was not picked up in the user's turn {turn}",
    )
    step("mid-turn", started, "mid-turn", before=before)

    started = time.monotonic()
    cc.say(USER_TURN)
    cc.until(cc.sleeping, "escape: the user's turn did not start its command")
    cc.escape()
    escaped = after_escape("escape")
    before = nudged()
    post(page, "escape")
    cc.until(answered("escape"), "escape: the comment was not answered")
    step("escape", started, "escape", before=before, escaped=escaped)

    started = time.monotonic()
    cc.say(USER_TURN)
    cc.until(cc.sleeping, "woken: the user's turn did not start its command")
    turn = page_claim(page)["turn"]
    post(page, "woken")

    def pickups() -> list[dict]:
        posted_id = comment_id(page, "woken")
        return [
            event
            for event in read_events(page)
            if event["kind"] == "pickup" and posted_id in event["events"]
        ]

    # The watch has woken, and the hooks module has handed the comment to the turn,
    # which reads it only once its command ends.
    cc.until(
        lambda: not watched() and (pickups() or not module),
        "woken: the watch did not wake on the comment",
        60,
    )
    require(cc.sleeping(), "woken: the command ended before Escape")
    cc.escape()
    escaped = after_escape("woken")
    first = pickups()[:1]
    escaped += ", the comment was first picked up in " + (
        "the stopped turn" if first and first[0]["turn"] == turn else "a later turn"
    )
    before = nudged()
    post(page, "after-wake")
    cc.until(
        lambda: answers(page, "after-wake") and cc.idle(),
        "woken: the comment after Escape was not answered",
    )
    if not answers(page, "woken"):
        # The comment the stopped turn was handed waits for the user's next prompt.
        cc.say("Carry on with the review.")
        cc.until(answered("woken"), "woken: the next prompt did not answer it")
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
    click.echo(f"quit: passed in {time.monotonic() - started:.0f} s")


@click.command()
@click.option(
    "--hooks-module",
    is_flag=True,
    help="Turn the plugin's `hooks_module` option on.",
)
def verify_cc_task(hooks_module: bool) -> None:
    """Run an interactive Claude Code session with Leaf's plugin and check what it
    carries."""
    require(shutil.which("tmux") is not None, "verify-cc-task drives tmux")
    run = run_directory(ROOT / ".tmp" / "verify-cc")
    # Outside any repository, so the session loads no project instructions. Claude
    # Code records trust by the resolved path.
    root = Path(tempfile.mkdtemp(prefix="leaf-verify-cc-")).resolve()
    state, work, payload = root / "state", root / "work", root / "plugin"
    work.mkdir()
    page = work / "page"
    extract_payload(payload)
    home = claude_home(root / "home")
    (home / ".claude.json").write_text(
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "theme": "dark",
                "projects": {str(work): {"hasTrustDialogAccepted": True}},
            }
        )
    )
    settings = {
        "pluginConfigs": {"leaf@inline": {"options": {"hooks_module": hooks_module}}}
    }
    argv = [
        "claude", "--model", MODELS["cc"], "--plugin-dir", str(payload),
        "--settings", json.dumps(settings), "--strict-mcp-config",
        "--permission-mode", "default", "--add-dir", str(payload),
        "--allowedTools", "Bash Read Write Edit Glob Grep Skill",
        "--debug-file", str(run / "debug.log"),
    ]  # fmt: skip
    # This process reads the page, claim and Claude Code's session record under the
    # home and state home the session writes, and every child inherits them, never
    # the session running this.
    inherited = dict(os.environ)
    isolated = claude_environment(home, XDG_STATE_HOME=str(state), TERM="tmux-256color")
    os.environ.clear()
    os.environ.update(isolated)
    passed = False
    try:
        prepare(ROOT, state, page)
        cc = ClaudeCode(root, run, work, argv, isolated)
        try:
            journey(cc, page, state, hooks_module)
        finally:
            # A failed step's screen; once Claude Code exits there is none.
            cc.keep("end")
            cc.close()
            run_leaf(ROOT, state, "server", "stop", str(page))
            shutil.copy(page / "events.jsonl", run / "events.jsonl")
        passed = True
    finally:
        os.environ.clear()
        os.environ.update(inherited)
        if passed:
            shutil.rmtree(root)
        else:
            click.echo(f"Kept the session, its page and its state home in {root}")
        click.echo(f"The session's screen, debug log and page log are in {run}")
    click.echo("Every check passed.")
