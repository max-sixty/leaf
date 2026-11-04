"""Time how fast an open Leaf page answers, on this working tree and a base.

    uv run leaf-dev bench-latency [--base [REF]]
    uv run leaf-dev bench-latency --page corpus --transition comment --runs 3

The head is this working tree, uncommitted edits included, and `--base` adds the merge
base with `main`, or REF (`leaf_dev.arms.choose_arms`). The working tree alone, with
one page and transition, takes under a minute, cheap enough to run during a change;
the full A/B takes many. Each arm builds and serves the triage board and the corpus
from this checkout's examples, and with `--base` both arms' tabs stay open in one
headless shell, taking turns within each run. Each run reloads the page, opens the
floating panel's Threads view, and times five transitions (`TRANSITIONS`): a passage
comment and a card move, each ended by a key, and an agent reply, status, and
revision, each by the arm's `leaf`. The agent
conversation has enough history to scroll, and the reply measurement follows its
latest turn in the panel's view of the thread, with the caret in the panel's field,
which is the thread's reply box.

A gesture's clock starts at its input event's timestamp; an agent write's at the first
modification of the file it writes, so the command's startup is left out. It stops at
the first frame that paints the result (an init script samples after each frame's
paint). A gesture's `sent` time is the first painted frame after its exact attempt
was admitted and that application reading was presented, and its `answered` time is
when the last byte of that POST's answer arrived, so `Sent` less `answered` is the
page waiting for its main thread and applying the reading. Who held the main thread
until the last goal is read from the long animation frames the page reports, by
script owner, with the style and layout each forced.

Requests and bytes, the primary comparison, count what the transition caused. The
browser reports each request the tab starts in any of its frames, CORS preflights
included, with the code that started it, its starter (`starter`). After each load a
run leaves the page alone for ALONE_S. The page keeps starting requests on its own,
such as its freshness read every 250 ms and its report of the reader's view, and a
request whose starter also started one while the page was alone, in any run of the
session, is the page's own. The table counts the requests the tab started from just
before the transition's input or command until the page had stayed quiet for
SETTLE_MS, less the page's own. Below the table, it says how many requests and bytes
the page started each second it was left alone. `results.json` lists each request's
URL, starter, whether it was the page's own, bytes, and when it started and ended
beside the transition's `start`, which splits the server's time from the page's.
Compare the numbers with the objectives in `notes/user-feedback-responsiveness.md`,
and read the spread and load average before a median.

`--profile` says where that time goes. Each transition runs under a V8 CPU profile and
a Chrome trace with style invalidation tracking, read over the benchmark's own window:
from the input or the write to the last frame the probe marks as painting one of its
goals. For a gesture that is Sent, so the window holds the local draw, the wait for
the POST's answer and the answer's application. After the table come,
for each page, transition and arm, when each goal was painted and each run's
main-thread tasks with the JS that dominated them, then per run: style and layout time
and how much of it script forced, the forced style recalculations and the writes that
invalidated style with the JS behind each, JS by self and inclusive time, and the
user-timing marks and measures the page made in the window, so a temporary
`performance.mark('x')` in source counts how often a path ran. With `--base`, the
arms' headline numbers follow side by side. Tracing slows the page, so read
proportions from a profiled run and durations from one without it. Each transition's
`.trace.json` (DevTools or Perfetto) and `.cpuprofile` land beside `results.json`.
"""

import json
import statistics
import subprocess
import tempfile
import time
from collections import Counter
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import dataclass, field
from functools import partial
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlsplit

import click
from playwright.sync_api import Browser, Page
from playwright.sync_api import Error as PlaywrightError

from leaf.render_checks import OUTSTANDING, wait_until_ready
from leaf_dev import ROOT
from leaf_dev.arms import (
    base_option,
    build_source,
    choose_arms,
    describe,
    environment,
    load_average,
    run_directory,
    run_leaf,
    serving,
)
from leaf_dev.browser import PANEL_THREAD, WINDOWS, go_to_threads, headless_shell
from leaf_dev.example_data import named_source
from leaf_dev.main_thread import SCRIPT as MAIN_THREAD_SCRIPT
from leaf_dev.main_thread import main_thread

OUT = ROOT / ".tmp" / "bench-latency"
RUNS = 5
SOURCES = ("triage-board", "corpus")
# The size of the window every session opens.
WINDOW_SIZE = WINDOWS["macbook"].size
# How long a transition may take before the run records it as never shown.
DEADLINE_S = 30
# How long a page must stay quiet before its traffic for a transition is read.
SETTLE_MS = 250
# How long each run leaves the page alone once it has loaded, so that the requests it
# starts on its own name the code that starts them (`Session.alone`).
ALONE_S = 2
# How many owners of the main thread to print per transition.
OWNERS = 6
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
# A scrollable conversation lets the native pinned reply row absorb arriving turns.
THREAD_TEXT = "Bench thread.\n\n" + "\n\n".join(
    f"Earlier conversation paragraph {line + 1}." for line in range(20)
)

PROBE = Path(__file__).with_suffix(".js")
# The page is still ready, read as `wait_until_ready` reads it, and every trip its
# ledger counts has ended (`__leafBench.quiet`).
QUIET = (
    f"() => ({OUTSTANDING})({{held: null, through: null}}) === 'ready'"
    " && window.__leafBench.quiet()"
)

# What --profile traces, and how it reads the trace.
CATEGORIES = [
    "blink.user_timing",
    "devtools.timeline",
    "disabled-by-default-devtools.timeline",
    "disabled-by-default-devtools.timeline.invalidationTracking",
    "disabled-by-default-devtools.timeline.stack",
]
# Trace events that run script: style or layout nested inside one of these was forced.
SCRIPT_EVENTS = {
    "FunctionCall",
    "EventDispatch",
    "TimerFire",
    "FireAnimationFrame",
    "v8.callFunction",
    "EvaluateScript",
    "RunMicrotasks",
}
RENDER_EVENTS = {
    "UpdateLayoutTree": "style",
    "Layout": "layout",
    "Paint": "paint",
    "Commit": "commit",
}
# Frames that say nothing about which runtime code ran: the sampler's own states.
OPAQUE = (
    "(root)",
    "(program)",
    "(idle)",
    "(garbage collector)",
)
# The shortest main-thread task --profile lists, and how many entries each list keeps.
TASK_MIN_MS = 2
TOP = 12


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
class Request:
    """A request the tab started, as the browser reported it: the code that started it
    (`starter`), and when it started and ended, in epoch milliseconds."""

    url: str
    starter: str
    start: float
    # Seconds the browser's clock for request events stands behind the epoch.
    offset: float
    # The attempt an event POST carries, which `answered` looks for.
    attempt: str | None = None
    bytes: int = 0
    end: float | None = None
    failed: bool = False


def starter(initiator: dict, url: str) -> str:
    """What started the request for `url`, as the browser's initiator names it: the
    function that called `fetch` or set a source, with its script's file name and
    position. A request no script was running for when it started, such as one the
    parser makes, a preflight, or the image of an element a script made and left,
    has no stack, and is named by the kind of initiator and its own file name, so it
    stands only for requests for that file. File names leave out the path, which names
    the page's revision, so a starter keeps its name across revisions and the live
    samples that load the same runtime."""
    for frame in (initiator.get("stack") or {}).get("callFrames", ()):
        return (
            f"{frame['functionName'] or '(anonymous)'} {file_name(frame['url'])}"
            f":{frame['lineNumber'] + 1}:{frame['columnNumber'] + 1}"
        )
    return f"{initiator['type']} {file_name(url)}"


def file_name(url: str) -> str:
    return urlsplit(url).path.rsplit("/", 1)[-1]


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
    # Under --profile, the directory each transition's trace and CPU profile land in,
    # and what `attribute` read from them, by transition in run order.
    profiled: Path | None = None
    attributed: dict[str, list[dict]] = field(default_factory=dict)
    # Every request the tab started, in every frame, by the browser's id for it.
    requests: dict[str, Request] = field(default_factory=dict)
    # When the page was left alone (`alone`), in epoch milliseconds.
    alone_spans: list[tuple[float, float]] = field(default_factory=list)
    # Each transition's result, which `split` completes with its requests.
    windows: list[dict] = field(default_factory=list)

    def started(self, event: dict) -> None:
        """Record a request the browser is about to send. A redirect sends the same
        request again, which keeps its first start."""
        url = event["request"]["url"]
        if event["requestId"] in self.requests or not url.startswith("http"):
            return
        body = event["request"].get("postData")
        self.requests[event["requestId"]] = Request(
            url,
            starter(event["initiator"], url),
            event["wallTime"] * 1000,
            event["wallTime"] - event["timestamp"],
            json.loads(body).get("attempt")
            if body and url.endswith("/api/event")
            else None,
        )

    def ended(self, event: dict) -> None:
        """Record when a request's last byte arrived, or it failed, and its bytes."""
        if request := self.requests.get(event["requestId"]):
            request.end = (event["timestamp"] + request.offset) * 1000
            request.bytes = event.get("encodedDataLength", 0)
            request.failed = "errorText" in event

    def answered(self, attempt: str) -> float | None:
        """When the last byte of the answer to the event POST of `attempt` arrived. A
        retry answers the same attempt; its later answer stands."""
        ends = [
            request.end
            for request in self.requests.values()
            if request.attempt == attempt and request.end and not request.failed
        ]
        return max(ends, default=None)

    def alone(self) -> None:
        """Leave the page alone for ALONE_S, so each request it starts on its own names
        its starter (`split`)."""
        began = time.time() * 1000
        time.sleep(ALONE_S)
        self.alone_spans.append((began, time.time() * 1000))

    def left_alone(self) -> dict:
        """What the page started while left alone: for how long, and per second its
        requests, their bytes and their starters."""
        seconds = sum(ended - began for began, ended in self.alone_spans) / 1000
        seen = [
            request
            for request in self.requests.values()
            if any(began <= request.start < ended for began, ended in self.alone_spans)
        ]
        return {
            "seconds": seconds,
            "requests": len(seen) / seconds,
            "bytes": sum(request.bytes for request in seen) / seconds,
            "starters": Counter(request.starter for request in seen),
        }

    def split(self) -> None:
        """Split each window's requests into the ones the transition caused and the
        page's own, which came from a starter the page also started a request from
        while left alone in any of the session's runs. A window's `requests` and
        `bytes` count the caused ones, and `own_requests` and `own_bytes` the rest.

        A starter the page uses both on its own and for a transition counts as the
        page's own in every window once the page has used it alone, as `readState`
        would be if the page's 2 s clock read state while alone, which it does only to
        retry or repair a read or when an activity's next transition falls due.
        `results.json` lists the starters seen alone."""
        # Playwright delivers the browser's reports only while it talks to the page.
        self.page.evaluate("0")
        starters = set(self.left_alone()["starters"])
        for window in self.windows:
            inside = [
                request
                for request in self.requests.values()
                if window["opened"] <= request.start < window["closed"]
            ]
            caused = [request for request in inside if request.starter not in starters]
            own = [request for request in inside if request.starter in starters]
            window.update(
                requests=len(caused),
                bytes=sum(request.bytes for request in caused),
                own_requests=len(own),
                own_bytes=sum(request.bytes for request in own),
                entries=[
                    {
                        "url": request.url,
                        "starter": request.starter,
                        "own": request.starter in starters,
                        "bytes": request.bytes,
                        "start": request.start,
                        "end": request.end,
                    }
                    for request in inside
                ],
            )

    def command(self, *args: str) -> list[str]:
        return [str(self.arm_dir / "bin" / "leaf"), *args]

    def open(self) -> None:
        """Load a fresh document on the passage, with the floating panel's Threads
        view open.

        Through `about:blank`, since a load of the URL the tab already shows is only
        a scroll to its fragment."""
        self.page.goto("about:blank")
        self.page.goto(self.url, wait_until="commit")
        self.settle()
        self.threads()
        self.settle()
        self.alone()

    def threads(self) -> None:
        """Open the floating panel's Threads view, listing every thread."""
        go_to_threads(self.page)

    def settle(self) -> None:
        """Wait until the page is ready, as every reader outside it waits
        (`wait_until_ready`), then until it is quiet (`QUIET`) and has stayed quiet for
        SETTLE_MS, so the traffic read next counts each trip the ledger counts."""
        wait_until_ready(self.page)
        deadline = time.monotonic() + DEADLINE_S
        while time.monotonic() < deadline:
            until(self.page, QUIET, "the page never settled")
            time.sleep(SETTLE_MS / 1000)
            if self.page.evaluate(QUIET):
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
            with (
                self.profiling(transition, self.profiled)
                if self.profiled
                else nullcontext()
            ) as recorded:
                # On the clock the browser reports requests by, and before a
                # command's startup, whose requests it can cause before its write.
                opened = time.time() * 1000
                start = act()
                watch = until(
                    self.page,
                    "() => { const w = window.__leafBench.watch();"
                    " return w.goals.every(g => g.at !== null) && w; }",
                    f"{self.arm} {transition} was never shown",
                )
            self.settle()
            traffic = self.page.evaluate("() => window.__leafBench.traffic()")
            frames = self.page.evaluate("() => window.__leafBench.frames()")
        finally:
            self.page.evaluate("() => window.__leafBench.disarm()")
        if recorded:
            runs = self.attributed.setdefault(transition, [])
            runs.append(attribute(*recorded, start, watch["goals"]))
        end = max(goal["at"] for goal in watch["goals"])
        # The gesture's own POST: the attempt the probe bound its `delivered` goal to.
        answered = next(
            (
                at
                for goal in watch["goals"]
                if goal.get("attempt") and (at := self.answered(goal["attempt"]))
            ),
            None,
        )
        window = {
            "page": self.source,
            "arm": self.arm,
            "transition": transition,
            "start": start,
            "opened": opened,
            "closed": time.time() * 1000,
            **{goal["name"]: goal["at"] - start for goal in watch["goals"]},
            **({"answered": answered - start} if answered else {}),
            **main_thread(frames, start, end),
            **traffic,
        }
        self.windows.append(window)
        return window

    @contextmanager
    def profiling(self, transition: str, directory: Path):
        """Profile and trace the page into `directory` for the life of the block, and
        yield a list that then holds the trace's path and the CPU profile."""
        run = len(self.attributed.get(transition, ())) + 1
        name = f"{self.arm}-{self.source}-{transition}-{run}"
        trace = directory / f"{name}.trace.json"
        browser = self.page.context.browser
        assert browser is not None  # `served` opens a context of a launched browser
        cdp = self.page.context.new_cdp_session(self.page)
        cdp.send("Profiler.enable")
        cdp.send("Profiler.setSamplingInterval", {"interval": 100})
        browser.start_tracing(page=self.page, path=str(trace), categories=CATEGORIES)
        cdp.send("Profiler.start")
        recorded = []
        try:
            yield recorded
        finally:
            profile = cdp.send("Profiler.stop")["profile"]
            browser.stop_tracing()
            cdp.detach()
        (directory / f"{name}.cpuprofile").write_text(json.dumps(profile))
        recorded.extend((trace, Profile(profile)))

    def gesture(self, transition: str, goals: dict, press) -> dict:
        def act():
            press()
            return until(self.page, "() => window.__leafBench.input()", "no input seen")

        return self.measure(transition, goals, act)

    def comment(self, run: int) -> dict:
        words = f"Bench comment {run + 1}."
        box = self.page.locator(f"#{PASSAGE}").bounding_box()
        assert box is not None
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
            {
                "painted": ("message", words),
                "sent": ("delivered", {"kind": "comment"}),
            },
            lambda: self.page.keyboard.press("ControlOrMeta+Enter"),
        )

    def move(self, run: int) -> dict:
        card, to = MOVES[run]
        self.page.locator(f"#{card} > .lf-grip").focus()
        self.page.keyboard.press("Enter")
        self.page.keyboard.press("ArrowLeft")
        return self.gesture(
            "move",
            {
                "painted": ("card", {"card": card, "to": to}),
                "sent": ("delivered", {"kind": "action", "unit": card}),
            },
            lambda: self.page.keyboard.press("Enter"),
        )

    def written(self, path: str, *args: str):
        """The start of a command that writes the page file `path`."""
        env = environment(XDG_STATE_HOME=str(self.state))
        return lambda: first_write(self.page_dir / path, self.command(*args), env)

    def reply(self, run: int) -> dict:
        """The agent's answer to the user's turn, while the user follows the
        scrollable conversation's tail in the floating panel's view of the thread.

        The user asks first because the panel shows at once only news that answers
        the user's last turn; any other reply waits behind New reply
        (primary-reader.js, `answersAtOnce`). The agent answers as an agent does,
        through the delivery `leaf wait` prints."""
        words = f"Bench reply {run + 1}."
        question = f"Bench question {run + 1}."
        opened = "selector => document.querySelector(selector)?.checkVisibility()"
        message = f"{PANEL_THREAD} .lf-msg"
        if not self.page.evaluate(opened, message):
            self.threads()
            self.page.locator(f'.lf-fp-thread[data-lf-key="{self.thread}"]').click()
            until(self.page, opened, "the agent thread never opened", message)
        # The panel's field is the open thread's reply box.
        self.page.locator(".lf-fp-field leaf-text").focus()
        self.page.keyboard.insert_text(question)
        self.page.keyboard.press("ControlOrMeta+Enter")
        until(
            self.page,
            "([selector, words]) => [...document.querySelectorAll(selector)]"
            ".some(node => node.textContent.includes(words) && node.checkVisibility())",
            "the user's turn never showed",
            [message, question],
        )
        delivery = run_leaf(
            self.arm_dir, self.state, "wait", str(self.page_dir), check=True
        )
        ref = next(
            event["answer"]["ref"]
            for batch in json.loads(delivery.stdout)["batches"]
            for event in batch["events"]
            if event.get("text") == question
        )
        self.settle()
        act = self.written(
            "events.jsonl", "thread", "reply", ref, "--done", "--text", words
        )
        return self.measure("reply", {"painted": ("message", words)}, act)

    def status(self, run: int) -> dict:
        detail = f"Bench status {run + 1}"
        act = self.written(
            "events.jsonl",
            "task",
            "start",
            str(self.page_dir),
            self.task,
            "--text",
            detail,
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
def served(
    browser: Browser,
    arm: str,
    arm_dir: Path,
    source: str,
    scratch: Path,
    profiled: Path | None = None,
):
    """Build `source` into a page with `arm_dir`'s launcher, serve it, and open a tab,
    profiling each transition into `profiled` where given."""
    state = scratch / f"{arm}-{source}-state"
    page_dir = scratch / f"{arm}-{source}" / "page"
    build_source(arm_dir, state, named_source(source), page_dir)
    leaf = partial(run_leaf, arm_dir, state, check=True)
    thread = json.loads(
        leaf(
            "thread", "create", str(page_dir), "--section", PASSAGE, "--quote", QUOTE,
            "--text", THREAD_TEXT,
        ).stdout
    )["id"]  # fmt: skip
    # The status transition starts this task, the page's own item, with a new line.
    task = json.loads(
        leaf("task", "create", str(page_dir), "page", "--title", "Bench task").stdout
    )["id"]
    with serving(arm_dir, state, page_dir) as address:
        width, height = WINDOW_SIZE
        context = browser.new_context(viewport={"width": width, "height": height})
        try:
            context.add_init_script(path=MAIN_THREAD_SCRIPT)
            context.add_init_script(path=PROBE)
            page = context.new_page()
            page.goto(address)  # The token sets the page cookie; later loads drop it.
            origin = address.split("?", 1)[0]
            url = f"{origin}#{PASSAGE}"
            session = Session(
                arm, source, arm_dir, state, page_dir, page, url, thread, task, profiled
            )
            # The browser's own account of each request, in every frame of the tab,
            # with the code that started it.
            network = context.new_cdp_session(page)
            network.on("Network.requestWillBeSent", session.started)
            network.on("Network.loadingFinished", session.ended)
            network.on("Network.loadingFailed", session.ended)
            network.send("Network.enable")
            yield session
        finally:
            context.close()


def milliseconds(us: float) -> float:
    return round(us / 1000, 1)


def stack_label(frames: list, depth: int = 3) -> str:
    return " < ".join(
        f"{f.get('functionName') or '(anon)'}:{f.get('lineNumber')}"
        for f in frames[:depth]
    )


class Profile:
    """One CPU profile: each sample's time and the chain of frames above it."""

    def __init__(self, profile: dict):
        nodes = {n["id"]: n for n in profile["nodes"]}
        parent = {c: n["id"] for n in profile["nodes"] for c in n.get("children", ())}

        def label(node_id):
            frame = nodes[node_id]["callFrame"]
            where = frame["url"].rsplit("/", 1)[-1]
            return (
                f"{frame['functionName'] or '(anon)'} {where}:{frame['lineNumber'] + 1}"
            )

        self.samples = []  # (timestamp µs, duration µs, frames leaf-first)
        at = profile["startTime"]
        deltas = profile["timeDeltas"]
        for sample, (delta, following) in zip(
            profile["samples"], pairwise([*deltas, 0]), strict=True
        ):
            at += delta
            chain, node_id = [], sample
            while node_id is not None:
                chain.append(label(node_id))
                node_id = parent.get(node_id)
            self.samples.append((at, following, chain))

    def dominant(self, lo: float, hi: float, count: int = 2) -> list:
        """The runtime call paths holding most samples between lo and hi."""
        paths = Counter()
        for at, _, chain in self.samples:
            if lo <= at < hi:
                named = [f for f in reversed(chain) if not f.startswith(OPAQUE)]
                paths[" > ".join(named[:3]) or chain[0]] += 1
        return [path for path, _ in paths.most_common(count)]

    def functions(self, lo: float, hi: float) -> tuple[Counter, Counter]:
        own, inclusive = Counter(), Counter()
        for at, duration, chain in self.samples:
            if lo <= at < hi and not chain[0].startswith(OPAQUE[:3]):
                own[chain[0]] += duration
                for frame in set(chain) - {"(root) :0"}:
                    inclusive[frame] += duration
        return own, inclusive


def renderer_main(events: list) -> list:
    names = {
        (e["pid"], e["tid"]): e["args"]["name"]
        for e in events
        if e.get("ph") == "M" and e.get("name") == "thread_name"
    }
    busy = Counter()
    for e in events:
        if e.get("ph") == "X" and names.get((e["pid"], e["tid"])) == "CrRendererMain":
            busy[(e["pid"], e["tid"])] += e.get("dur", 0)
    thread = busy.most_common(1)[0][0]
    return sorted(
        (e for e in events if (e.get("pid"), e.get("tid")) == thread),
        key=lambda e: (e["ts"], -e.get("dur", 0)),
    )


def attribute(trace: Path, profile: Profile, began: float, goals: list[dict]) -> dict:
    """What the main thread did in the benchmark's window: from the transition's start,
    `began` in epoch milliseconds, to the frame the probe marked as painting its last
    goal."""
    everything = json.loads(trace.read_text())
    everything = (
        everything["traceEvents"] if isinstance(everything, dict) else everything
    )
    marks = {
        e["name"].removeprefix("lf-bench:"): e["ts"]
        for e in everything
        if e.get("name", "").startswith("lf-bench:")
    }
    # A goal's `at` and its mark name the same frame, one in epoch milliseconds and
    # one in the trace's microseconds, which places the start on the trace's clock.
    start = marks[goals[0]["name"]] + (began - goals[0]["at"]) * 1000
    end = max(marks.values())
    events = [e for e in renderer_main(everything) if e["ts"] <= end]
    spans = [e for e in events if e.get("ph") == "X"]

    # A task or a render step can straddle either end; only its part inside counts.
    def inside(e):
        return min(e["ts"] + e.get("dur", 0), end) - max(e["ts"], start)

    tasks = [
        (
            max(e["ts"], start) - start,
            inside(e),
            profile.dominant(max(e["ts"], start), min(e["ts"] + e["dur"], end)),
        )
        for e in spans
        if e["name"] == "RunTask" and inside(e) >= TASK_MIN_MS * 1000
    ]
    render, forced, recalcs, recalc_time = Counter(), Counter(), Counter(), Counter()
    open_spans = []  # (name, end) of the spans enclosing the current one
    for e in spans:
        while open_spans and open_spans[-1][1] <= e["ts"]:
            open_spans.pop()
        kind = RENDER_EVENTS.get(e["name"])
        if (
            kind
            and e["ts"] >= start
            and not any(RENDER_EVENTS.get(n) == kind for n, _ in open_spans)
        ):
            render[kind] += inside(e)
            if any(n in SCRIPT_EVENTS for n, _ in open_spans):
                forced[kind] += inside(e)
                if kind == "style":
                    args = e.get("args", {})
                    frames = (args.get("beginData") or {}).get("stackTrace") or []
                    count = args.get("elementCount") or (args.get("endData") or {}).get(
                        "elementCount"
                    )
                    site = (stack_label(frames, 4), count)
                    recalcs[site] += 1
                    recalc_time[site] += inside(e)
        open_spans.append((e["name"], e["ts"] + e.get("dur", 0)))
    # Marks (instant events) and measures (async begin events) the page made.
    user_timing = Counter(
        e["name"]
        for e in events
        if e["ts"] >= start
        and "blink.user_timing" in e.get("cat", "")
        and e.get("ph") in ("R", "I", "i", "b")
        and not e["name"].startswith("lf-bench:")
    )
    invalidations = Counter()
    for e in events:
        if e["ts"] < start or "nvalidation" not in e.get("name", ""):
            continue
        data = e.get("args", {}).get("data", {})
        cause = (
            data.get("reason")
            or data.get("changedAttribute")
            or data.get("changedClass")
            or data.get("changedPseudo")
            or data.get("changedId")
            or ""
        )
        where = stack_label(data.get("stackTrace") or [])
        invalidations[(e["name"], cause, data.get("nodeName", ""), where)] += 1
    own, inclusive = profile.functions(start, end)
    return {
        "window": end - start,
        "marks": {name: at - start for name, at in marks.items()},
        "tasks": tasks,
        "render": render,
        "forced": forced,
        "recalcs": recalcs,
        "recalc_time": recalc_time,
        "invalidations": invalidations,
        "user_timing": user_timing,
        "own": own,
        "inclusive": inclusive,
    }


def per_run(runs: list, value) -> float:
    return milliseconds(value / len(runs))


def total(runs: list, key: str) -> Counter:
    return sum((run[key] for run in runs), Counter())


def show_profile(runs: list) -> None:
    for number, run in enumerate(runs, 1):
        painted = ", ".join(
            f"{name} {milliseconds(at)}" for name, at in run["marks"].items()
        )
        click.echo(f"run {number}: ms from input to each painted goal: {painted}")
        for at, duration, paths in run["tasks"]:
            click.echo(
                f"  {milliseconds(at):7.1f} ms  task {milliseconds(duration):6.1f} ms  {' | '.join(paths)}"
            )

    render, forced = total(runs, "render"), total(runs, "forced")
    click.echo(f"\nper run, over {len(runs)} runs")
    click.echo(
        "  render ms: "
        + ", ".join(
            f"{k} {per_run(runs, v)} (forced {per_run(runs, forced[k])})"
            for k, v in render.most_common()
        )
    )
    click.echo("  forced style recalculations (ms, count, elements, forced by):")
    recalcs = total(runs, "recalcs")
    for (where, count), spent in total(runs, "recalc_time").most_common(TOP):
        click.echo(
            f"    {per_run(runs, spent):6.1f}  {recalcs[(where, count)]:4}  {count or '?':>5}  {where}"
        )
    click.echo("  style invalidations (count, event, cause, node, written by):")
    for (event, cause, node, where), n in total(runs, "invalidations").most_common(TOP):
        click.echo(f"    {n:4}  {event} | {cause} | {node} | {where}")
    for key, title in (("own", "self"), ("inclusive", "inclusive")):
        click.echo(f"  JS by {title} ms:")
        for frame, value in total(runs, key).most_common(TOP):
            click.echo(f"    {per_run(runs, value):7.1f}  {frame}")


def show_marks(arms: dict[str, list]) -> None:
    """User-timing marks and measures in the window: the count each run made, per arm."""
    names = sorted(
        {n for runs in arms.values() for r in runs for n in r["user_timing"]}
    )
    click.echo("\nuser-timing marks and measures in the window (count per run):")
    if not names:
        click.echo("  none")
    for name in names:
        counts = "   ".join(
            f"{arm} {','.join(str(r['user_timing'][name]) for r in runs)}"
            for arm, runs in arms.items()
        )
        click.echo(f"  {name}: {counts}")


def compare_profiles(arms: dict[str, list]) -> None:
    """The arms' headline numbers in columns."""
    click.echo("\nside by side, per run:")
    click.echo(f"  {'':22}" + "".join(f"{arm:>16}" for arm in arms))

    def line(label, value):
        click.echo(
            f"  {label:22}" + "".join(f"{value(runs):>16}" for runs in arms.values())
        )

    line(
        "window ms (median)",
        lambda rs: milliseconds(statistics.median(r["window"] for r in rs)),
    )
    for kind in RENDER_EVENTS.values():
        line(
            f"{kind} ms (forced)",
            lambda rs, kind=kind: (
                f"{per_run(rs, total(rs, 'render')[kind])}"
                f" ({per_run(rs, total(rs, 'forced')[kind])})"
            ),
        )


def spread(values: list[float]) -> str:
    if not values:
        return ""
    return f"{statistics.median(values):.0f} [{min(values):.0f}-{max(values):.0f}]"


def row(source: str, transition: str, arm: str, runs: list[dict]) -> str:
    painted = spread([r["painted"] for r in runs])
    answered = spread([r["answered"] for r in runs if "answered" in r])
    sent = spread([r["sent"] for r in runs if "sent" in r])
    requests = statistics.median(r["requests"] for r in runs)
    kb = statistics.median(r["bytes"] for r in runs) / 1000
    installs = ", ".join(sorted({r["install"] for r in runs}))
    return (
        f"{source:13} {transition:10} {arm:4} {painted:>16} {answered:>14} {sent:>16} "
        f"{requests:>8.0f} {kb:>7.1f}  {installs if transition == 'revision' else ''}"
    )


def owners(runs: list[dict]) -> list[str]:
    """The owners of the main thread's long frames, by mean script time per run."""
    total: dict[str, list[float]] = {}
    for run in runs:
        for owner, (ms, forced) in run["owners"].items():
            spent = total.setdefault(owner, [0.0, 0.0])
            spent[0] += ms
            spent[1] += forced
    ranked = sorted(total.items(), key=lambda item: -item[1][0])
    render = sum(r["render"] for r in runs) / len(runs)
    return [
        f"    {ms / len(runs):6.0f} {forced / len(runs):6.0f}  {owner}"
        for owner, (ms, forced) in ranked[:OWNERS]
    ] + [f"    {render:6.0f}         style, layout and paint after scripts"]


@click.command()
@base_option()
@click.option(
    "--page",
    "pages",
    multiple=True,
    type=click.Choice(SOURCES),
    help="Time only this page; repeat for more. Default: all.",
)
@click.option(
    "--transition",
    "transitions",
    multiple=True,
    type=click.Choice(TRANSITIONS),
    help="Time only this transition; repeat for more. Default: all.",
)
@click.option(
    "--runs",
    default=RUNS,
    show_default=True,
    # Each run moves its own card (`MOVES`).
    type=click.IntRange(1, len(MOVES)),
    help="Runs per arm.",
)
@click.option(
    "--profile",
    is_flag=True,
    help="Also profile and trace each transition, and say where its time went.",
)
def bench_latency(
    base: str | None,
    pages: tuple[str, ...],
    transitions: tuple[str, ...],
    runs: int,
    profile: bool,
) -> None:
    """Time an open page's answers on this working tree, and on a base with --base.

    Times a page's answer to a gesture, an agent write, and a revision, on two
    pages, with this working tree's runtime and with --base the base's, taking
    turns. Prints a table of median [min-max] milliseconds to the painted frame, to
    the gesture's POST answer, and to the painted frame of the server's reading
    (Sent), with the requests and bytes each caused, then who held the main thread
    in that time. Every run lands in .tmp/bench-latency/.

    --profile runs each transition under a CPU profiler and a Chrome trace, and
    after the table says where its time went: the main-thread tasks up to the last
    painted goal, forced style and layout and the writes that invalidated style, JS
    by function, and the user-timing marks the page made, so a temporary
    `performance.mark('x')` in the source counts how often a path ran. Tracing slows
    the page, so read proportions from a profiled run and durations from one without.

    To check a change as you make it, narrow it, for example
    `--page corpus --transition comment --runs 3`.
    """
    pages = pages or SOURCES
    transitions = transitions or TRANSITIONS
    out = run_directory(OUT)
    load_before = load_average()
    results = []
    # Under --profile, what each run's trace and profile held, by page, transition
    # and arm.
    attributed: dict[tuple[str, str, str], list[dict]] = {}
    # What each page started on its own while left alone, by page and arm.
    alone: dict[tuple[str, str], dict] = {}
    with tempfile.TemporaryDirectory(prefix="leaf-bench-") as built:
        scratch = Path(built)
        arms = choose_arms(base, scratch)
        with headless_shell() as browser:
            for source in pages:
                with ExitStack() as stack:
                    sessions = [
                        stack.enter_context(
                            served(
                                browser,
                                arm,
                                version.directory,
                                source,
                                scratch,
                                out if profile else None,
                            )
                        )
                        for arm, version in arms.items()
                    ]
                    for run in range(runs):
                        # Alternate which arm goes first, so neither always meets
                        # the machine the other just loaded.
                        for session in sessions[:: 1 if run % 2 == 0 else -1]:
                            session.open()
                            for transition in transitions:
                                result = getattr(session, transition)(run)
                                result["run"] = run
                                results.append(result)
                                click.echo(
                                    f"{source} {session.arm} run {run + 1} "
                                    f"{transition}: {result['painted']:.0f} ms",
                                    err=True,
                                )
                    for session in sessions:
                        session.split()
                        alone[(source, session.arm)] = session.left_alone()
                        for transition, by in session.attributed.items():
                            attributed[(source, transition, session.arm)] = by
            chrome = browser.version
    commits = {arm: arms[arm].commit for arm in arms}
    (out / "results.json").write_text(
        json.dumps(
            {
                "commits": commits,
                "alone": [
                    {"page": source, "arm": arm, **rate}
                    for (source, arm), rate in alone.items()
                ],
                "results": results,
            },
            indent=1,
        )
    )
    click.echo(
        f"{describe(arms)}, {runs} runs, Chrome {chrome}, "
        f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}\n"
        f"load average {load_before} before, {load_average()} after\n"
        "times are median [min-max] ms from input or write to the painted frame"
        f"{', under the profiler, which slows the page' if profile else ''}\n"
        f"{'page':13} {'transition':10} {'arm':4} {'painted':>16} {'answered':>14} "
        f"{'Sent':>16} {'requests':>8} {'KB':>7}  install"
    )
    selected = [
        (source, transition, arm, by)
        for source in pages
        for transition in transitions
        for arm in arms
        if (
            by := [
                r
                for r in results
                if (r["page"], r["transition"], r["arm"]) == (source, transition, arm)
            ]
        )
    ]
    for source, transition, arm, by in selected:
        click.echo(row(source, transition, arm, by))
    click.echo(
        "\nrequests the page started on its own, per second left alone"
        " (left out of every transition's count):"
    )
    for (source, arm), rate in alone.items():
        click.echo(
            f"  {source:13} {arm:4} {rate['requests']:5.1f} requests"
            f" {rate['bytes'] / 1000:7.1f} KB"
        )
    click.echo(
        "\nmain thread in long frames to the last painted goal, mean ms per run:"
        "\n    script forced  owner"
    )
    for source, transition, arm, by in selected:
        # A transition with no long frame held the main thread for none of its time.
        if any(r["owners"] or r["render"] for r in by):
            click.echo(f"  {source} {transition} {arm}")
            for line in owners(by):
                click.echo(line)
    for source in pages if profile else ():
        for transition in transitions:
            by_arm = {arm: attributed[(source, transition, arm)] for arm in arms}
            for arm, by in by_arm.items():
                click.echo(f"\n=== {source} {transition} {arm} ===")
                show_profile(by)
            if len(by_arm) > 1:
                compare_profiles(by_arm)
            show_marks(by_arm)
    click.echo(f"details: {out / 'results.json'}")
