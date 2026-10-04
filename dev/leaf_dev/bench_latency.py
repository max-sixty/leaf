"""Time how fast an open Leaf page answers, for BASE_REF's runtime and HEAD's.

    uv run leaf-dev bench-latency [BASE_REF]

BASE_REF defaults to the merge base with `main`; each arm is the plugin payload at its
commit (`leaf_dev.harness.build_pair`), so commit what you want measured. Each arm
builds and serves the triage board and the corpus from this checkout's examples, and
both arms' tabs stay open in one headless Chrome, taking turns within each run. Each
run reloads the page, opens the Threads panel, and times five transitions
(`TRANSITIONS`): a passage comment and a card move, each ended by a key, and an agent
reply, status, and revision, each by the arm's `leaf`.

A gesture's clock starts at its input event's timestamp; an agent write's at the first
modification of the file it writes, so the command's startup is left out. It stops at
the first frame that paints the result (an init script samples after each frame's
paint), and a gesture's "Sent" receipt is timed the same way. Requests and bytes, the
primary comparison, are the resource entries the page started from then until it has
stayed quiet for SETTLE_MS, or the whole new document after a reload; request bodies
carry no entry. Completed finite freshness reads do, while an open SSE connection does
not. Compare the numbers with the objectives in
`notes/user-feedback-responsiveness.md`, and read the spread and load average before
a median. `leaf-dev profile` drives the same transitions (`served`) under a profiler.
"""

import json
import statistics
import subprocess
import tempfile
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import click
from playwright.sync_api import Browser, Page
from playwright.sync_api import Error as PlaywrightError

from leaf_dev import ROOT
from leaf_dev.browser import DESKTOP, chrome
from leaf_dev.harness import (
    build_pair,
    build_source,
    environment,
    load_average,
    run_directory,
    run_leaf,
    serving,
)

OUT = ROOT / ".tmp" / "bench-latency"
RUNS = 5
SOURCES = ("triage-board", "corpus")
# How long a transition may take before the run records it as never shown.
DEADLINE_S = 30
# How long a page must stay quiet before its traffic for a transition is read.
SETTLE_MS = 250
# The triage content both sources carry: the passage the comment and the agent thread
# stand on, and the cards each run moves one column left (the corpus keeps their ids).
PASSAGE = "triage-lede"
QUOTE = "It is the only release blocker."
LEDE_END = "Move a card if you would ship differently."
MOVES = (
    ("card-tz", "col-blocking"),
    ("card-export", "col-blocking"),
    ("card-retry", "col-blocking"),
    ("card-logout", "col-next"),
    ("card-avatar", "col-next"),
)
TRANSITIONS = ("comment", "move", "reply", "status", "revision")

PROBE = Path(__file__).with_suffix(".js")


def until(page: Page, script: str, what: str, arg=None):
    """Poll a page reading until it is truthy, across a reload that may interrupt it."""
    deadline = time.monotonic() + DEADLINE_S
    failure = None
    while True:
        try:
            if value := page.evaluate(script, arg):
                return value
        except PlaywrightError as error:
            failure = error  # Usually the document was replaced mid-read.
        if time.monotonic() > deadline:
            last = f" (last read failed: {failure.message})" if failure else ""
            raise click.ClickException(f"{page.url}: {what} within {DEADLINE_S}s{last}")
        time.sleep(0.02)


def first_write(path: Path, command: list[str], env: dict) -> float:
    """Run `command` and return when it first changed `path`, in epoch milliseconds.

    The modification stamp of the first change the file shows is the write itself,
    whatever the command spent starting up before it."""
    before = path.stat().st_mtime_ns
    process = subprocess.Popen(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    while True:
        exited = process.poll() is not None
        written = path.stat().st_mtime_ns
        if written != before or exited:
            break
        time.sleep(0.0005)
    output, _ = process.communicate()
    if process.returncode or written == before:
        raise click.ClickException(
            f"{' '.join(command[1:])} exited {process.returncode}, "
            f"{'unchanged' if written == before else 'changed'} {path.name}:\n{output}"
        )
    return written / 1e6


@dataclass
class Session:
    """One arm's page, its server, and the tab open on it."""

    arm: str
    source: str
    arm_dir: Path
    state: Path
    page_dir: Path
    page: Page
    url: str
    thread: str
    task: str
    # What runs around a transition, from just before it starts until its first goal
    # is painted: nothing here, a profiler in `leaf-dev profile`.
    recording: Callable[[], AbstractContextManager] = nullcontext

    def command(self, *args: str) -> list[str]:
        return [str(self.arm_dir / "bin" / "leaf"), *args]

    def open(self) -> None:
        """Load a fresh document on the passage, with the Threads panel open.

        Through `about:blank`, since a load of the URL the tab already shows is only
        a scroll to its fragment."""
        self.page.goto("about:blank")
        self.page.goto(self.url, wait_until="commit")
        self.settle()
        panel = (
            "() => Boolean(document.querySelector('.lf-thread-panel')"
            "?.checkVisibility())"
        )
        if not self.page.evaluate(panel):
            self.page.locator(".lf-threads-toggle").click()
            until(self.page, panel, "the Threads panel never opened")
        self.settle()

    def settle(self) -> None:
        """Wait until the page is quiet and has stayed quiet for SETTLE_MS."""
        quiet = "() => window.__leafBench.quiet()"
        deadline = time.monotonic() + DEADLINE_S
        while time.monotonic() < deadline:
            until(self.page, quiet, "the page never settled")
            time.sleep(SETTLE_MS / 1000)
            if self.page.evaluate(quiet):
                return
        raise click.ClickException(f"{self.page.url}: the page never stayed quiet")

    def measure(self, transition: str, goals: dict, act) -> dict:
        """Arm the frame sampler for `goals`, act, and read when each was painted.

        `act` returns the transition's start in epoch milliseconds."""
        self.page.evaluate(
            "goals => window.__leafBench.arm(goals)",
            [
                {"name": name, "fact": fact, "arg": arg}
                for name, (fact, arg) in goals.items()
            ],
        )
        try:
            with self.recording():
                start = act()
                until(
                    self.page,
                    "() => window.__leafBench.watch().goals[0].at !== null",
                    f"{self.arm} {transition} was never shown",
                )
            watch = until(
                self.page,
                "() => { const w = window.__leafBench.watch();"
                " return w.goals.every(g => g.at !== null) && w; }",
                f"{self.arm} {transition} was never shown",
            )
            self.settle()
            traffic = self.page.evaluate("() => window.__leafBench.traffic()")
        finally:
            self.page.evaluate("() => window.__leafBench.disarm()")
        return {
            "page": self.source,
            "arm": self.arm,
            "transition": transition,
            **{goal["name"]: goal["at"] - start for goal in watch["goals"]},
            **traffic,
        }

    def gesture(self, transition: str, goals: dict, press) -> dict:
        def act():
            press()
            return until(self.page, "() => window.__leafBench.input()", "no input seen")

        return self.measure(transition, goals, act)

    def comment(self, run: int) -> dict:
        words = f"Bench comment {run + 1}."
        box = self.page.locator(f"#{PASSAGE}").bounding_box()
        y = box["y"] + 10
        self.page.mouse.move(box["x"] + 2, y)
        self.page.mouse.down()
        self.page.mouse.move(box["x"] + 200, y, steps=8)
        self.page.mouse.up()
        until(
            self.page,
            "() => (CSS.highlights.get('lf-pending')?.size ?? 0) > 0",
            "the selection was never marked",
        )
        self.page.locator(".lf-fab-input").click()
        field = self.page.locator(".lf-composer leaf-text")
        field.focus()
        self.page.keyboard.insert_text(words)
        return self.gesture(
            "comment",
            {"painted": ("message", words), "sent": ("sent", words)},
            lambda: self.page.keyboard.press("ControlOrMeta+Enter"),
        )

    def move(self, run: int) -> dict:
        card, to = MOVES[run]
        self.page.locator(f"#{card} > .lf-grip").focus()
        self.page.keyboard.press("Enter")
        self.page.keyboard.press("ArrowLeft")
        return self.gesture(
            "move",
            {"painted": ("card", {"card": card, "to": to}), "sent": ("cardSent", card)},
            lambda: self.page.keyboard.press("Enter"),
        )

    def written(self, path: str, *args: str):
        """The start of a command that writes the page file `path`."""
        env = environment(XDG_STATE_HOME=str(self.state))
        return lambda: first_write(self.page_dir / path, self.command(*args), env)

    def reply(self, run: int) -> dict:
        """A reply to the agent thread, which is opened first: the panel shows the
        messages of the thread the user has open and one row for each other."""
        words = f"Bench reply {run + 1}."
        thread = f'.lf-thread[data-id="{self.thread}"]'
        message = f"{thread} .lf-msg"
        opened = "selector => document.querySelector(selector)?.checkVisibility()"
        if not self.page.evaluate(opened, message):
            self.page.locator(f"{thread} .lf-thread-summary").click()
            until(self.page, opened, "the agent thread never opened", message)
        self.settle()
        act = self.written(
            "events.jsonl",
            *("thread", "reply", str(self.page_dir)),
            *(self.thread, "--text", words),
        )
        return self.measure("reply", {"painted": ("message", words)}, act)

    def status(self, run: int) -> dict:
        detail = f"Bench status {run + 1}"
        act = self.written(
            "events.jsonl", "task", "start", str(self.page_dir), self.task, detail
        )
        return self.measure("status", {"painted": ("status", detail)}, act)

    def revision(self, run: int) -> dict:
        words = f"Bench revision {run + 1}."
        index = self.page_dir / "index.html"
        html = index.read_text(encoding="utf-8")
        revision = self.page.evaluate("() => window.__leafBench.revision()") + 1

        def act():
            index.write_text(html.replace(LEDE_END, f"{LEDE_END} {words}"), "utf-8")
            saved = index.stat().st_mtime_ns / 1e6
            run_leaf(
                self.arm_dir, self.state, "page", "stamp", str(self.page_dir),
                "--text", words, check=True,
            )  # fmt: skip
            return saved

        goal = {"revision": revision, "id": PASSAGE, "words": words}
        return self.measure("revision", {"painted": ("revision", goal)}, act)


@contextmanager
def served(browser: Browser, arm: str, arm_dir: Path, source: str, scratch: Path):
    """Build `source` into a page with `arm_dir`'s launcher, serve it, and open a tab."""
    state = scratch / f"{arm}-{source}-state"
    page_dir = scratch / f"{arm}-{source}" / "page"
    build_source(arm_dir, state, ROOT / "examples" / f"{source}.html", page_dir)
    leaf = partial(run_leaf, arm_dir, state, check=True)
    thread = json.loads(
        leaf(
            "thread", "open", str(page_dir), "--section", PASSAGE, "--quote", QUOTE,
            "--text", "Bench thread.",
        ).stdout
    )["id"]  # fmt: skip
    # The status transition starts this task, the page's own item, with a new line.
    task = json.loads(leaf("task", "open", str(page_dir), "page", "Bench task").stdout)[
        "id"
    ]
    with serving(arm_dir, state, page_dir) as address:
        context = browser.new_context(
            viewport={"width": DESKTOP[0], "height": DESKTOP[1]}
        )
        try:
            context.add_init_script(path=PROBE)
            page = context.new_page()
            page.goto(address)  # The token sets the page cookie; later loads drop it.
            origin = address.split("?", 1)[0]
            url = f"{origin}#{PASSAGE}"
            yield Session(
                arm, source, arm_dir, state, page_dir, page, url, thread, task
            )
        finally:
            context.close()


def spread(values: list[float]) -> str:
    if not values:
        return ""
    return f"{statistics.median(values):.0f} [{min(values):.0f}-{max(values):.0f}]"


def row(source: str, transition: str, arm: str, runs: list[dict]) -> str:
    painted = spread([r["painted"] for r in runs])
    sent = spread([r["sent"] for r in runs if "sent" in r])
    requests = statistics.median(r["requests"] for r in runs)
    kb = statistics.median(r["bytes"] for r in runs) / 1000
    installs = ", ".join(sorted({r["install"] for r in runs}))
    return (
        f"{source:13} {transition:10} {arm:4} {painted:>16} {sent:>16} "
        f"{requests:>8.0f} {kb:>7.1f}  {installs if transition == 'revision' else ''}"
    )


@click.command()
@click.argument("base_ref", required=False)
def bench_latency(base_ref: str | None) -> None:
    """Time an open page's answers, base vs HEAD.

    Times a page's answer to a gesture, an agent write, and a revision, on two
    pages, taking turns between BASE_REF's runtime and HEAD's; BASE_REF defaults to
    the merge base with main. Prints a table of median [min-max] milliseconds
    to the painted frame, with the requests and bytes each caused; every run lands
    in .tmp/bench-latency/.
    """
    out = run_directory(OUT)
    load_before = load_average()
    results = []
    with tempfile.TemporaryDirectory(prefix="leaf-bench-") as built:
        scratch = Path(built)
        arms, commits = build_pair(base_ref, scratch)
        with chrome() as browser:
            for source in SOURCES:
                with ExitStack() as stack:
                    sessions = [
                        stack.enter_context(
                            served(browser, arm, arm_dir, source, scratch)
                        )
                        for arm, arm_dir in arms.items()
                    ]
                    for run in range(RUNS):
                        # Alternate which arm goes first, so neither always meets
                        # the machine the other just loaded.
                        for session in sessions[:: 1 if run % 2 == 0 else -1]:
                            session.open()
                            for transition in TRANSITIONS:
                                result = getattr(session, transition)(run)
                                results.append({**result, "run": run})
                                click.echo(
                                    f"{source} {session.arm} run {run + 1} "
                                    f"{transition}: {result['painted']:.0f} ms",
                                    err=True,
                                )
            version = browser.version
    (out / "results.json").write_text(
        json.dumps({"commits": commits, "results": results}, indent=1)
    )
    click.echo(
        f"base {commits['base'][:10]} vs head {commits['head'][:10]}, {RUNS} runs, "
        f"Chrome {version}, {DESKTOP[0]}x{DESKTOP[1]}\n"
        f"load average {load_before} before, {load_average()} after\n"
        "times are median [min-max] from input or write to the painted frame\n"
        f"{'page':13} {'transition':10} {'arm':4} {'painted ms':>16} "
        f"{'Sent ms':>16} {'requests':>8} {'KB':>7}  install"
    )
    for source in SOURCES:
        for transition in TRANSITIONS:
            for arm in arms:
                runs = [
                    r
                    for r in results
                    if (r["page"], r["transition"], r["arm"])
                    == (source, transition, arm)
                ]
                click.echo(row(source, transition, arm, runs))
    click.echo(f"details: {out / 'results.json'}")
