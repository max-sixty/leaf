#!/usr/bin/env python3
"""Time how fast an open Leaf page answers, for BASE_REF's runtime and HEAD's.

    uv run scripts/bench_page_latency.py [BASE_REF]

BASE_REF defaults to the merge base of HEAD and `main`. Each arm is the plugin payload
at its commit (`eval_harness.build_arm`), so commit what you want measured. Every page
is built from this checkout's example source by the arm's own launcher
(`prepare_page`), and served by that arm's `leaf server run --temporary`, so the
browser runtime and the server both come from the arm. Pages are
`examples/triage-board.html` and the corpus (`examples/corpus.html`, opened on its
Triage tab), in one headless Chrome (`launch_browser`) at 1440x900 with the Threads
panel open. The two arms' pages stay open side by side and take turns within each run.

Each of RUNS runs reloads the page and times five transitions against the objectives in
`notes/user-feedback-responsiveness.md`:

- `comment`: a passage comment sent with Mod+Enter. Painted is the first frame showing
  the message; Sent is the first frame showing its "Sent" receipt.
- `move`: a board card grabbed, moved one column left, and dropped with Enter. Painted
  is the first frame with the card set down in its new column; Sent is the first frame
  whose margin shows "Sent" for that card.
- `reply`: `leaf thread reply` on an agent thread, painted when the reply shows. The
  thread is opened first, since the panel shows only the open thread's messages.
- `status`: `leaf status <page> working "..."`, painted when the banner shows it.
- `revision`: a changed `index.html` saved, then `leaf page stamp`, presented when
  the new revision's words show after `data-lf-presented`. Install says whether the
  runtime patched the document in place or reloaded it.

A transition's clock starts at the input event's own timestamp for a gesture, and at
the first modification time of the file the command writes (`events.jsonl`,
`status.json`) or the saved `index.html` for a write. It stops at the end of the first
rendering update whose result satisfies the transition: an init script samples every
frame after its animation-frame callbacks, from a task posted there, which runs after
that frame's paint. A DOM change is therefore counted at the frame that paints it, not
when it happens. The report flags a gesture painted after 100 ms, and a receipt or a
write painted after 1 s; a receipt is timed from the input rather than from server
acceptance, which makes its objective stricter than the note's. Page time is `performance.timeOrigin + performance.now()`; file time is
the filesystem's modification stamp. Both read the machine's wall clock, which the
script assumes is shared; it prints the page-to-Python offset it observed.

Requests and bytes are the primary comparison; time is diagnostic. They count what the
page did from the gesture or write until it is quiet (`lfReadiness` null, the traffic
ledger's sends and reads all answered) and stays quiet for SETTLE_MS: the resource
entries started in that window, or every entry of the new document after a reload,
with bytes as their `transferSize`.

Limits: request bodies and the long-lived `api/news` stream carry no resource entry,
so neither is counted; the frame sampler keeps Chrome producing frames while it waits;
one headless browser on a shared machine measures load too, so read the spread and the
printed load average before a median; the gestures skip the selection and grab that
precede them. Results go to `.tmp/bench-page-latency/results.json`.
"""

import json
import os
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
from eval_harness import build_arm, environment, merge_base, run_leaf, serving
from leaf.render_gate.browser import launch_browser
from page_fixtures import prepare_page, read_fixture
from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".tmp" / "bench-page-latency"
RUNS = 5
SOURCES = ("triage-board", "corpus")
VIEWPORT = {"width": 1440, "height": 900}
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
# The objectives of notes/user-feedback-responsiveness.md, in milliseconds: a gesture's
# local result, a visible receipt, and an agent write's paint.
PAINTED_OBJECTIVE = {"comment": 100, "move": 100}
WRITE_OBJECTIVE = 1000
SENT_OBJECTIVE = 1000

# Installed before every document. `arm` stores the goals in sessionStorage, so a
# revision that reloads the page goes on being sampled in the document that replaces it.
PROBE = """
(() => {
  const WATCH = "leaf-bench-watch";
  performance.setResourceTimingBufferSize(1000000);
  const documentId = crypto.randomUUID();
  const clock = () => performance.timeOrigin + performance.now();
  let input = null;
  addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Enter") input = performance.timeOrigin + event.timeStamp;
    },
    true,
  );
  const shown = (node) => Boolean(node?.checkVisibility());
  const messages = (words) =>
    [...document.querySelectorAll(".lf-msg, .lf-page-thread-msg")].filter(
      (node) => node.textContent.includes(words) && shown(node),
    );
  const saysSent = (node) => node.textContent.trim() === "Sent" && shown(node);
  const facts = {
    message: (words) => messages(words).length > 0,
    sent: (words) =>
      messages(words).some((message) =>
        [
          ...(message.closest(".lf-thread, .lf-page-thread") ?? message)
            .querySelectorAll(".lf-msg-sending"),
        ].some(saysSent),
      ),
    card: ({ card, to }) => {
      const node = document.getElementById(card);
      return node?.parentElement?.id === to && !node.classList.contains("lf-lift") &&
        shown(node);
    },
    cardSent: (card) =>
      [
        ...document.querySelectorAll(
          `leaf-margin-cluster[data-lf-margin-for="${card}"] .lf-margin-entry-label-word`,
        ),
      ].some(saysSent),
    status: (detail) => {
      const node = document.querySelector(".lf-status-text");
      return shown(node) && node.textContent.includes(detail);
    },
    revision: ({ revision, id, words }) => {
      const node = document.getElementById(id);
      return (
        Number(document.querySelector('meta[name="lf-revision"]')?.content) >= revision &&
        document.body.hasAttribute("data-lf-presented") &&
        shown(node) &&
        node.textContent.includes(words)
      );
    },
  };
  const watched = () => JSON.parse(sessionStorage.getItem(WATCH) ?? "null");
  let sampling = false;
  function sample() {
    if (sampling) return;
    sampling = true;
    const frame = () =>
      requestAnimationFrame(() => {
        const channel = new MessageChannel();
        channel.port1.onmessage = () => {
          const watch = watched();
          if (!watch) return (sampling = false);
          const at = clock();
          let open = false;
          for (const goal of watch.goals) {
            if (goal.at !== null) continue;
            let met = false;
            try {
              met = facts[goal.fact](goal.arg);
            } catch {}
            if (met) {
              goal.at = at;
              // Where a trace of the page finds this frame (profile_page.py).
              performance.mark(`lf-bench:${goal.name}`);
            } else open = true;
          }
          sessionStorage.setItem(WATCH, JSON.stringify(watch));
          if (open) frame();
          else sampling = false;
        };
        channel.port2.postMessage(null);
      });
    frame();
  }
  const ledger = () =>
    JSON.parse(document.documentElement.dataset.lfTraffic ?? '{"sends":0,"asked":0}');
  const resources = (entries) => ({
    requests: entries.length,
    bytes: entries.reduce((total, entry) => total + entry.transferSize, 0),
  });
  Object.defineProperty(window, "__leafBench", {
    value: Object.freeze({
      arm(goals) {
        input = null;
        const watch = {
          goals: goals.map((goal) => ({ ...goal, at: null })),
          document: documentId,
          since: performance.now(),
          ledger: ledger(),
        };
        sessionStorage.setItem(WATCH, JSON.stringify(watch));
        sample();
      },
      watch: watched,
      disarm: () => sessionStorage.removeItem(WATCH),
      input: () => input,
      clock,
      revision: () => Number(document.querySelector('meta[name="lf-revision"]')?.content),
      quiet() {
        const ready =
          document.querySelector("script[data-lf-entry]")?.lfReadiness?.() === null;
        const trips = ledger();
        return (
          ready &&
          trips.acked === trips.sends &&
          trips.heard === trips.asked &&
          !trips.pending?.length
        );
      },
      // What the page did since `arm`: in this document the resource entries started
      // since then, and after a reload everything the new document loaded.
      traffic() {
        const watch = watched();
        const now = ledger();
        if (watch.document === documentId)
          return {
            install: "in place",
            sends: now.sends - watch.ledger.sends,
            asked: now.asked - watch.ledger.asked,
            ...resources(
              performance
                .getEntriesByType("resource")
                .filter((entry) => entry.startTime >= watch.since),
            ),
          };
        return {
          install: "reload",
          sends: now.sends,
          asked: now.asked,
          ...resources([
            ...performance.getEntriesByType("navigation"),
            ...performance.getEntriesByType("resource"),
          ]),
        };
      },
    }),
  });
  if (watched()) sample();
})();
"""


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

    def identity():
        stat = path.stat()
        return stat.st_ino, stat.st_mtime_ns, stat.st_size

    before = identity()
    process = subprocess.Popen(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    written = None
    while written is None:
        exited = process.poll() is not None
        if identity() != before:
            written = path.stat().st_mtime_ns / 1e6
        elif exited:
            break
        else:
            time.sleep(0.0005)
    output, _ = process.communicate()
    if process.returncode or written is None:
        raise click.ClickException(
            f"{' '.join(command[1:])} exited {process.returncode} "
            f"{'without writing ' + path.name if written is None else ''}:\n{output}"
        )
    return written


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
    # What runs around a transition, from just before it starts until its first goal
    # is painted: nothing here, a profiler in `profile_page.py`.
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
        opened = f"() => document.querySelector('{thread} .lf-msg')?.checkVisibility()"
        if not self.page.evaluate(opened):
            self.page.locator(f"{thread} .lf-thread-summary").click()
            until(self.page, opened, "the agent thread never opened")
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
            "status.json", "status", str(self.page_dir), "working", detail
        )
        return self.measure("status", {"painted": ("status", detail)}, act)

    def revision(self, run: int) -> dict:
        words = f"Bench revision {run + 1}."
        index = self.page_dir / "index.html"
        html = index.read_text(encoding="utf-8")
        if html.count(LEDE_END) != 1:
            raise click.ClickException(f"{index} does not hold {LEDE_END!r} once")
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
    leaf = partial(run_leaf, arm_dir, state, check=True)
    prepare_page(page_dir, read_fixture(ROOT / "examples" / f"{source}.html"), leaf)
    thread = json.loads(
        leaf(
            "thread", "open", str(page_dir), "--section", PASSAGE, "--quote", QUOTE,
            "--text", "Bench thread.", "--json",
        ).stdout
    )["id"]  # fmt: skip
    with serving(arm_dir, state, page_dir) as address:
        context = browser.new_context(viewport=VIEWPORT)
        try:
            context.add_init_script(script=PROBE)
            page = context.new_page()
            page.goto(address)  # The token sets the page cookie; later loads drop it.
            origin = address.split("?", 1)[0]
            url = f"{origin}#{PASSAGE}"
            yield Session(arm, source, arm_dir, state, page_dir, page, url, thread)
        finally:
            context.close()


def clock_offset(page: Page) -> float:
    """How far the page's clock sits from Python's, in milliseconds."""
    before = time.time() * 1000
    page_time = page.evaluate("() => window.__leafBench.clock()")
    after = time.time() * 1000
    return page_time - (before + after) / 2


def spread(values: list[float]) -> str:
    if not values:
        return "never shown"
    return f"{statistics.median(values):.0f} [{min(values):.0f}-{max(values):.0f}]"


def report(results: list[dict], header: str) -> tuple[str, list[str]]:
    rows = [
        (
            f"{'page':13} {'transition':10} {'arm':4} {'painted ms':>16} "
            f"{'Sent ms':>16} {'requests':>8} {'KB':>7}  install"
        )
    ]
    misses = []
    for source in SOURCES:
        for transition in TRANSITIONS:
            for arm in ("base", "head"):
                runs = [
                    r
                    for r in results
                    if (r["page"], r["transition"], r["arm"])
                    == (source, transition, arm)
                ]
                if not runs:
                    continue
                painted = [r["painted"] for r in runs]
                sent = [r["sent"] for r in runs if "sent" in r]
                installs = sorted({r["install"] for r in runs})
                rows.append(
                    f"{source:13} {transition:10} {arm:4} {spread(painted):>16} "
                    f"{spread(sent) if sent else '':>16} "
                    f"{statistics.median(r['requests'] for r in runs):>8.0f} "
                    f"{statistics.median(r['bytes'] for r in runs) / 1000:>7.1f}  "
                    f"{', '.join(installs) if transition == 'revision' else ''}"
                )
                limit = PAINTED_OBJECTIVE.get(transition, WRITE_OBJECTIVE)
                for name, values, objective in (
                    ("painted", painted, limit),
                    ("Sent", sent, SENT_OBJECTIVE),
                ):
                    over = sum(value > objective for value in values)
                    if over:
                        misses.append(
                            f"{source} {transition} {arm}: {name} over {objective} ms "
                            f"in {over} of {len(values)} runs "
                            f"(median {statistics.median(values):.0f} ms)"
                        )
    return "\n".join([header, *rows]), misses


@click.command()
@click.argument("base_ref", required=False)
def main(base_ref: str | None) -> None:
    """Time an open page's transitions, RUNS times, for BASE_REF's runtime and HEAD's."""
    if base_ref is None:
        base_ref = merge_base()
    load_before = os.getloadavg()
    results = []
    offsets = []
    with tempfile.TemporaryDirectory(prefix="leaf-bench-") as built:
        scratch = Path(built)
        arms = {"base": scratch / "base", "head": scratch / "head"}
        commits = {
            "base": build_arm(base_ref, arms["base"]),
            "head": build_arm("HEAD", arms["head"]),
        }
        with sync_playwright() as playwright:
            browser, _ = launch_browser(playwright)
            try:
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
                                offsets.append(clock_offset(session.page))
                                for transition in TRANSITIONS:
                                    result = getattr(session, transition)(run)
                                    results.append({**result, "run": run})
                                    click.echo(
                                        f"{source} {session.arm} run {run + 1} "
                                        f"{transition}: {result['painted']:.0f} ms",
                                        err=True,
                                    )
                chrome = browser.version
            finally:
                browser.close()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(
        json.dumps({"commits": commits, "results": results}, indent=1)
    )
    load_after = os.getloadavg()
    header = (
        f"base {commits['base'][:10]} vs head {commits['head'][:10]}, {RUNS} runs, "
        f"Chrome {chrome}, {VIEWPORT['width']}x{VIEWPORT['height']}\n"
        f"load average {' '.join(f'{v:.1f}' for v in load_before)} before, "
        f"{' '.join(f'{v:.1f}' for v in load_after)} after; page clock within "
        f"{max(abs(o) for o in offsets):.1f} ms of Python's\n"
        "times are median [min-max] from input or write to the painted frame"
    )
    table, misses = report(results, header)
    click.echo(table)
    for miss in misses:
        click.echo(f"objective missed: {miss}")
    click.echo(f"details: {OUT / 'results.json'}")


if __name__ == "__main__":
    main()
