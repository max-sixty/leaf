"""Measure how a page's costs grow with the page, in a browser or on the server.

    uv run leaf-dev scaling [AXIS ...] [--sizes 32,64,128,256] [--rounds N]
        [--browser firefox] [--base [REF]] [--profile]
    uv run leaf-dev scaling --server [AXIS ...] [--sizes 128,...,1600] [--rounds N]
        [--profile]

Root `AGENTS.md`, "Responsiveness", sets the rule this checks: no cost grows faster
than the page, and an input's should hardly grow at all. Each AXIS names a page in
`COLLECTIONS` that grows one of its collections with its size and holds the rest
fixed: its authored markup, the log admitted after it and the versions saved before
it. The browser measures `AXES` by default, and the server `SERVER_AXES`; either
measures any of them.

For each AXIS it generates a page at each size, serves it from this tree, and reads
the page's main-thread CPU, in Chromium in thread ticks (`chromium_metrics`), for each
of `TRANSITIONS`: the load until the page settles and its main thread goes quiet, a
click on an option, a keystroke in the page's comment field, leaving that field with
Escape, a Tab from one stop to the next, a wheel step, and an agent's revision, which
adds a paragraph under the page's title by writing the page's source, as an agent
does, and the next takes it away. Each input is one a user or agent makes, the same
at every size. A click is the mouse's own press and release at the option's centre.
A wheel step is one NOTCH, with the pointer over the page's content and the scroller
beneath it halfway down. Tab starts from the first option's control, and a page with
no option, such as a board, reads no click, Tab or `shown`, which its table names as
missing. The wheel and
Tab take RUN steps one way and RUN back, so they cross the same rows or stops at every
size. An input's cost is the mean over several, less the page's idle CPU over the same
time, which is read once the work the load leaves behind has run (`idle_rate`).
Beside them stand the server's time to start answering each event the clicks posted,
whose answer carries the server's reading of the page, that answer's size, and
`shown`: the time from a click to the first frame painted once that reading is
presented (`leaf_dev.painted`), which root `AGENTS.md` holds to BUDGET_MS on the
largest page and the table flags past it. It is an upper bound, at most a frame above
that paint, since the probe reads the page before the frame's later callbacks run;
its goal stays met once met, as the bound needs. Every run also measures a page of BASE,
whose costs are mostly the runtime's fixed work. It prints each cost by size with the
exponent of its growth above the BASE page, fitted over the largest sizes (least
squares of log growth on log size), and marks an exponent above SUPERLINEAR, which is
a step nesting one walk of the page inside another. Fitting the cost itself would let
fixed work hide that: 30 ms per click plus 20/80/320 ms of quadratic work fits 1.4
over 64-256, and its growth fits 2.0.

--rounds measures every page N times and reports each cost's lowest reading
(`lowest`). The rounds are interleaved (`interleaved`): each takes every size in turn
and every arm at each size, so a burst of load lands on one reading of each page. The
daily suite reads the browser's pages as this does (`measure_rounds`), and the
server's (`server_scaling.measure`), with the same rounds.

--server times the server's paths on each page instead, in this process with no
browser (`leaf_dev.server_scaling` names the paths and how it reads them), and names
each path that breaks the rule: growth fitting an exponent above SUPERLINEAR
(`failures`), or a click's paths together taking more than their budget at REFERENCE.
The daily `tests/journeys/test_server_scaling.py` fails the growth; the budget waits,
as the browser's do, until the pages that miss it are fixed.

--base also measures the merge base with main (or REF), chosen as every A/B command
chooses its arms (`arms.choose_arms`), so a change shows its exponents beside the
base's. --profile records a V8 CPU profile (`leaf_dev.profiles`) of each span a
transition's reading covers, and no more, at the smallest and largest size in the
first round, and lists the functions whose time over a transition's spans grew
superlinearly between them, which names the nested walk.

--browser firefox measures Playwright's Firefox, on macOS. Firefox offers no count of
its tasks, so there a transition's CPU is the page's main thread's as the OS counts it
(`ContentClock`), which is the clock Chromium's thread ticks read. Over the same
windows in Chromium on 2026-11-05, the OS's count was at most 0.7 ms per input above
the ticks. Driven alike through geckodriver that day, the Firefox 159 on this Mac read
about 10% below Playwright's build, Firefox 157, with the same functions on top.

--profile is V8's, so to name what took Firefox's time, run the command under the Gecko
profiler's variables. The browser then writes a profile of the whole run as it closes,
which <https://profiler.firefox.com> reads, and its samples' `threadCPUDelta` sum to
the OS's count. Profiling slows the page, so read proportions from it and durations
from a run without it.

    MOZ_PROFILER_STARTUP=1 MOZ_PROFILER_SHUTDOWN=$PWD/.tmp/gecko.json \\
    MOZ_PROFILER_STARTUP_FEATURES=js MOZ_PROFILER_STARTUP_FILTERS=GeckoMain,StyleThread \\
    MOZ_PROFILER_STARTUP_ENTRIES=134217728 uv run leaf-dev scaling asks --browser firefox

CPU time rather than wall time, so a loaded host spreads the readings less than it
spreads elapsed time; each exponent still compares sizes within one run. `shown` and
`event` are elapsed time, which a busy host stretches, and so does a run held to the
efficiency cores: on 2026-11-05 `taskpolicy -c utility` read a click's `shown` at 110
to 170 ms on pages the default policy showed in 30 to 35. Pages, the profiles and
`results.json` land in a run directory under `.tmp/scaling/`. The daily suite fails
growth well past linear on every axis with the same measurement, of every cost but
those its `UNHELD` names (`tests/journeys/test_scaling.py`).
"""

import ctypes
import json
import math
import statistics
import time
from collections import Counter
from collections.abc import (
    Callable,
    Generator,
    Hashable,
    Iterable,
    Iterator,
    Sequence,
)
from contextlib import ExitStack, contextmanager, nullcontext, suppress
from functools import partial
from itertools import cycle
from pathlib import Path
from typing import NamedTuple

import click
import psutil
from playwright.sync_api import Page

from leaf_dev import ROOT
from leaf_dev.arms import (
    Arm,
    ServedPage,
    base_option,
    choose_arms,
    describe,
    run_directory,
    served_page,
    serving_source,
)
from leaf_dev.browser import (
    chromium_metrics,
    engine_option,
    headless_shell,
    launch,
    settle,
    tab,
)
from leaf_dev.painted import SCRIPT as PAINTED
from leaf_dev.profiles import Profile, cpu_profile

OUT = ROOT / ".tmp" / "scaling"
SIZES = (32, 64, 128, 256)
# A server path takes a browser input's time on a page several times the size, so
# the server's pages reach further in the same time.
SERVER_SIZES = (128, 256, 512, 1024, 1600)
SERVER_AXES = (
    "widgets",
    "boards",
    "cards",
    "options",
    "threads",
    "messages",
    "events",
    "revisions",
    "batch",
)
# The page size a server path is held to its budget at: the size the browser's
# inputs are held to theirs at, where a click shows the server's reading.
REFERENCE = 512
# The page size whose costs stand for the runtime's fixed work. Each exponent fits a
# cost's growth above it, so it is a small fraction of the sizes fitted.
BASE = 8
# An exponent above this is superlinear growth. It stands halfway between linear and
# quadratic: above BASE, linear growth fits about 1.07 over 64-256, and n log n 1.25.
SUPERLINEAR = 1.5
# How many of the largest sizes the exponent is fitted over.
FITTED = 3
# Where a cost grows by less than its floor above BASE, what little it grew is the
# host's noise, and its exponent leaves that size out. A floor is a share of a reading
# from the same run, the BASE page's load for the browser's costs (`floors`). A slower
# machine slows that reading as much as every cost, so it fits the same sizes to the
# same exponent. With the BASE page loading in 150-210 ms on an unloaded M5 Max, the
# shares put a floor near 10 ms of CPU, and near 50 ms for the server's time to answer
# and the time until a click shows its reading, which are elapsed time. The event
# answer's size is in kilobytes, which no machine's speed changes.
FLOOR_SHARE = 0.05
FLOOR_SHARES = {"event": 0.25, "shown": 0.25}
KB_FLOOR = 10
# Root `AGENTS.md`, "Responsiveness": a click shows the server's reading within this
# many ms on the largest page.
BUDGET_MS = 100
KEYS = 20
CLICKS = 4
LEAVES = 4
TABS = 16
WHEEL_STEPS = 32
# An agent's revision adds a paragraph under the page's title, and the next takes it
# away again.
REVISIONS = 2
REVISED = '<p id="revised">The agent adds this paragraph in a revision.</p>'
# A notch of a mouse wheel, which Chromium and Firefox here both scroll 100 px.
NOTCH = 100
# A wheel or Tab takes RUN steps one way and then as many back, so it stays among the
# same few rows or stops at every size, the smallest page's included.
RUN = 4
WAYS = (1,) * RUN + (-1,) * RUN
# A half second in which the page's main thread spends under this is quiet; two in a
# row end the load (`idle_rate`), or QUIET_TRIES half seconds on a host too busy for
# two.
QUIET_MS = 5
QUIET_TRIES = 20
# A function must take this long at the largest size to be listed as growing.
GROWTH_FLOOR_MS = 20
DEADLINE_MS = 300_000
# How long `page_process` spins a page's main thread to find its process, how many
# times it tries, and the spin, which ends by the page's own clock and is named so a
# profile of the page shows it.
SPIN_MS = 30
SPIN_TRIES = 10
SPIN = """function scalingSpin(ms) {
  const end = performance.now() + ms;
  while (performance.now() < end);
}"""
# `proc_pidinfo`'s flavors for a process's threads and one thread's times, in
# `sys/proc_info.h`.
PROC_PIDLISTTHREADS = 6
PROC_PIDTHREADINFO = 5
# What `measure` does to a page, in the order it does them.
TRANSITIONS = ("load", "click", "key", "leave", "tab", "scroll", "revision", "shown")
# Each cost `measure` reads, under its label in the table: each transition's
# main-thread CPU but `shown`'s; for the clicks, how long the server took to start
# answering each event they posted, whose answer carries its reading of the page, and
# how large that was; and how long from a click until the page showed that reading.
COLUMNS = {
    **{
        transition: f"{transition} ms"
        for transition in TRANSITIONS
        if transition != "shown"
    },
    "event": "event ms",
    "event_kb": "event KB",
    "shown": "shown ms",
}
# A click's goal for `painted.js`: the server's reading of its event, presented.
SHOWN = [{"name": "shown", "fact": "delivered", "arg": {"kind": "action"}}]
EVENT_POSTS = """() => performance.getEntriesByType("resource")
  .filter((entry) => new URL(entry.name).pathname.endsWith("/api/event"))
  .map((entry) => ({
    ms: entry.responseStart - entry.requestStart,
    kb: entry.encodedBodySize / 1024,
  }))"""
# Leave nothing focused, put the scroller under the window's centre halfway down, less
# half of `band`: the page, then any scroller inside it there, as a text document's
# listing is; and return the centre. The generated pages' article fills the window,
# so the centre is over the page's content.
HALFWAY = """(band) => {
  document.activeElement?.blur();
  const [x, y] = [innerWidth / 2, innerHeight / 2];
  const page = document.scrollingElement;
  const halfway = (scroller) => {
    scroller.scrollTop = (scroller.scrollHeight - scroller.clientHeight - band) / 2;
  };
  halfway(page);
  let under = document.elementFromPoint(x, y);
  while (under && under !== page && !(under.scrollHeight > under.clientHeight &&
      /auto|scroll/.test(getComputedStyle(under).overflowY)))
    under = under.parentElement;
  if (under && under !== page) halfway(under);
  return [x, y];
}"""


def ask(g: int, options: int = 4) -> str:
    """Section `g`: a heading, a paragraph and an `lf-ask` of `options` options."""
    return (
        f'<section id="s{g}"><h2>Section {g}</h2><p>Some words about section {g}.</p>'
        f'<lf-ask id="q{g}"><h3>Question {g}</h3><lf-options id="o{g}" choose multiple>'
        + "".join(
            f'<lf-option id="o{g}-{i}"><strong>Option {i}</strong> a short description.'
            "</lf-option>"
            for i in range(1, options + 1)
        )
        + "</lf-options></lf-ask></section>"
    )


def ask_sections(n: int) -> str:
    """`n` sections, each an `ask`, so widgets, obligations on the user, headings and
    margin pins all grow with `n`."""
    return page("Questions", "".join(ask(g) for g in range(1, n + 1)))


def board_sections(boards: int, cards: int, done: int = 0) -> str:
    """`boards` sections, each an `lf-board` of `cards` cards to do and `done` done."""

    def column(b: int, name: str, count: int) -> str:
        return (
            f'<lf-column id="b{b}-{name}" label="{name.title()}">'
            + "".join(
                f'<lf-card id="b{b}-{name}{j}"><strong>Card {j}</strong> of board {b}.'
                "</lf-card>"
                for j in range(1, count + 1)
            )
            + "</lf-column>"
        )

    return page(
        "Boards",
        "".join(
            f'<section id="s{b}"><h2>Board {b}</h2><lf-board id="b{b}">'
            + column(b, "todo", cards)
            + column(b, "done", done)
            + "</lf-board></section>"
            for b in range(1, boards + 1)
        ),
    )


def prose_sections(n: int) -> str:
    """`n` sections of headings and paragraphs after one ask: the document grows, and
    the widgets don't."""
    question = (
        '<lf-ask id="q0"><h3>Question</h3><lf-options id="o0" choose multiple>'
        '<lf-option id="o0-1">One</lf-option><lf-option id="o0-2">Two</lf-option>'
        "</lf-options></lf-ask>"
    )
    sections = "".join(
        f'<section id="s{g}"><h2>Section {g}</h2>'
        f"<p>Some words about section {g}, enough for a line or two of reading.</p>"
        f'<p>Another paragraph in section {g} with a <a href="#s1">link</a>.</p>'
        "</section>"
        for g in range(1, n + 1)
    )
    return page("Prose", question + sections)


def document_lines(n: int) -> str:
    """One ask and a text document of `n` × 64 lines of Python, written in its `<pre>`:
    the document's text grows, and the widgets don't."""
    question = (
        '<lf-ask id="q0"><h3>Question</h3><lf-options id="o0" choose multiple>'
        '<lf-option id="o0-1">One</lf-option><lf-option id="o0-2">Two</lf-option>'
        "</lf-options></lf-ask>"
    )
    lines = "".join(
        f'def step_{g}(value):  # step {g}\n    return value * {g} + "{g}"\n'
        for g in range(n * 32)
    )
    document = (
        '<lf-text-document id="listing" label="steps.py" language="python">'
        f"<pre>{lines}</pre></lf-text-document>"
    )
    return page("Document", question + document)


def page(title: str, body: str) -> str:
    return (
        f'<!doctype html><html lang="en"><head><title>{title}</title></head><body>'
        f'<main><article id="document"><h1>{title}</h1>{body}</article></main>'
        "</body></html>"
    )


def pick(g: int, *options: int, revision: int = 1) -> dict:
    """The user choosing `options` in section `g`'s ask."""
    return {
        "kind": "action",
        "author": "user",
        "revision": revision,
        "widget": f"o{g}",
        "action": "choose",
        "detail": {"value": [f"o{g}-{i}" for i in options]},
    }


def move(b: int, j: int, k: int) -> dict:
    """The user moving card `j` of board `b` to its Done column, to the `k`th place
    there, since ranks order a column as strings do."""
    return {
        "kind": "action",
        "author": "user",
        "revision": 1,
        "widget": f"b{b}",
        "action": "move",
        "detail": {"unit": f"b{b}-todo{j}", "value": f"b{b}-done", "rank": f"{k:05d}i"},
    }


def comment(t: int) -> dict:
    """The user opening thread `t` on one of `prose_sections(64)`."""
    return {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "id": f"c{t}",
        "text": f"A question {t} about this section?",
        "anchor": {"section": f"s{t % 64 + 1}"},
    }


def answer(t: int) -> dict:
    """The agent answering thread `t`."""
    return {
        "kind": "reply",
        "author": "agent",
        "agent": "Codex",
        "parent": f"c{t}",
        "revision": 1,
        "text": f"Answer {t}.",
    }


def exchange(m: int) -> list[dict]:
    """Message `m` after thread 0's comment: the agent's answer, which asks the user
    a question in turn, or the user's reply, which asks one back; and after each
    fourth, the agent's summary of the four."""
    if m % 2:
        message = {
            **answer(0),
            "id": f"m{m}",
            "text": f"Answer {m}, and a question: which way?",
            "obligation": True,
        }
    else:
        message = {
            "kind": "reply",
            "author": "user",
            "id": f"m{m}",
            "parent": "c0",
            "text": f"This way. Why {m}?",
        }
    if m % 4:
        return [message]
    summary = {
        "kind": "summary",
        "author": "agent",
        "agent": "Codex",
        "session": "scaling",
        "thread": "c0",
        "from": f"m{m - 3}",
        "through": f"m{m}",
        "text": f"Messages {m - 3} to {m}, in a line.",
    }
    return [message, summary]


class Collection(NamedTuple):
    """A page that holds `n` of one collection and a fixed amount of the rest: its
    authored markup, the events its log holds after it, and how many versions of
    the page are saved before the log."""

    authored: Callable[[int], str]
    log: Callable[[int], list[dict]] = lambda _: []
    versions: Callable[[int], int] = lambda _: 1

    def sources(self, n: int) -> list[str]:
        """Each saved version's markup, oldest first: the authored page, its heading
        numbered where there are several."""
        authored, versions = self.authored(n), self.versions(n)
        if versions == 1:
            return [authored]
        return [
            authored.replace("</h1>", f", version {version}</h1>", 1)
            for version in range(1, versions + 1)
        ]


# Every page `leaf-dev scaling` generates, by the collection that grows with `n`.
COLLECTIONS: dict[str, Collection] = {
    "asks": Collection(ask_sections),
    "document": Collection(document_lines),
    "prose": Collection(prose_sections),
    "widgets": Collection(
        ask_sections, lambda n: [pick(g, g % 4 + 1) for g in range(1, n + 1)]
    ),
    "boards": Collection(
        lambda n: board_sections(n, 3),
        lambda n: [move(b, 1, 1) for b in range(1, n + 1)],
    ),
    # A move records the authored cards it lies among, here the n done already.
    "cards": Collection(
        lambda n: board_sections(1, n, done=n),
        lambda n: [move(1, j, j) for j in range(1, n + 1)],
    ),
    "options": Collection(
        lambda n: page("Options", ask(1, options=n)),
        lambda n: [pick(1, *range(1, n + 1))],
    ),
    "threads": Collection(
        lambda _: prose_sections(64),
        lambda n: [event for t in range(n) for event in (comment(t), answer(t))],
    ),
    "messages": Collection(
        lambda _: prose_sections(64),
        lambda n: [comment(0), *(e for m in range(1, n) for e in exchange(m))],
    ),
    "events": Collection(
        lambda _: ask_sections(16),
        lambda n: [pick(k % 16 + 1, k % 4 + 1) for k in range(n)],
    ),
    "revisions": Collection(
        lambda _: ask_sections(16),
        lambda n: [pick(1, 1, revision=n)],
        lambda n: n,
    ),
    "batch": Collection(
        lambda _: prose_sections(64), lambda n: list(map(comment, range(n)))
    ),
}
# The pages the browser measures; any other collection is one more name here.
AXES = {name: COLLECTIONS[name] for name in ("asks", "document", "prose", "threads")}


@contextmanager
def main_thread_clock(engine: str, page: Page) -> Generator[Callable[[], float]]:
    """Yield what reads the blank `page`'s main-thread CPU so far, in ms, when called:
    in Chromium the renderer's own count of its tasks, in thread ticks
    (`chromium_metrics`), and in Firefox the OS's count (`ContentClock`)."""
    if engine == "chromium":
        with chromium_metrics(page, ticks=True) as metrics:
            yield lambda: metrics()["TaskDuration"] * 1000
    else:
        yield ContentClock(page)


class ThreadTimes(ctypes.Structure):
    """libproc's `proc_threadinfo`, whose first two fields are a thread's CPU in ns."""

    _fields_ = [
        ("user", ctypes.c_uint64),
        ("system", ctypes.c_uint64),
        ("rest", ctypes.c_char * 96),
    ]


def main_thread_ms(pid: int) -> float:
    """The main thread's CPU so far in process `pid`, in ms, as macOS counts it, or 0
    where the process has gone. A process lists its main thread first."""
    info = ctypes.CDLL("/usr/lib/libproc.dylib").proc_pidinfo
    thread, times = ctypes.c_uint64(), ThreadTimes()
    listed = info(pid, PROC_PIDLISTTHREADS, ctypes.c_uint64(0), ctypes.byref(thread), 8)
    read = listed > 0 and info(
        pid, PROC_PIDTHREADINFO, thread, ctypes.byref(times), ctypes.sizeof(times)
    )
    return (times.user + times.system) / 1e6 if read else 0


def content_main_threads() -> dict[int, float]:
    """Each Firefox content process's main-thread CPU so far, in ms, by pid."""
    times = {}
    for child in psutil.Process().children(recursive=True):
        # A process a closed page leaves behind may have gone by now.
        with suppress(psutil.Error):
            if child.cmdline()[-1:] == ["tab"]:
                times[child.pid] = main_thread_ms(child.pid)
    return times


def page_process(page: Page) -> int:
    """The Firefox content process `page`'s main thread runs in.

    Nothing says which content process holds a page, and Firefox runs others beside
    it, such as its built-in extensions', so the page identifies its own. Each try
    spins the page's main thread for SPIN_MS, then leaves it for as long. The page's
    process gains CPU while the page spins and stops when it stops, where a process
    busy throughout gains alike in both, so each process's contrast is its rise during
    the spin less its rise after. The page's must be at least half the spin, and at
    least twice any other's; a try on a host too busy to give it that is tried again,
    up to SPIN_TRIES."""
    contrasts = {}
    for _ in range(SPIN_TRIES):
        ahead = content_main_threads()
        page.evaluate(SPIN, SPIN_MS)
        spun = content_main_threads()
        time.sleep(SPIN_MS / 1000)
        after = content_main_threads()
        contrasts = {
            pid: 2 * spun[pid] - ms - after.get(pid, spun[pid])
            for pid, ms in ahead.items()
            if pid in spun
        }
        first, *rest = sorted(contrasts.values(), reverse=True)
        if first >= SPIN_MS / 2 and first >= 2 * max(rest, default=0):
            return max(contrasts, key=contrasts.__getitem__)
    raise RuntimeError(
        f"No content process followed the page's spins in {SPIN_TRIES} tries (the "
        f"last's contrasts, in ms by process: {contrasts}), so the clock can't tell "
        "which holds the page. Run it again on a quieter host."
    )


class ContentClock:
    """What reads `page`'s main-thread CPU so far, in ms, when called, in Firefox, which
    offers no count of its own: the thread's CPU as the OS counts it (this module's
    header), in the content process the page names (`page_process`) as the clock is
    made, while the page is still blank. While it is blank, each read returns 0 and
    takes the process's reading again, so the load counts from the read that starts
    it. The reading never falls, and holds its last value once the process has gone.

    The spins cost the page CPU, so `measure` confirms the process (`confirm`) between
    the load's last reading and the first input's first, outside every window it
    reads."""

    def __init__(self, page: Page):
        self.page = page
        self.holder = page_process(page)
        self.start = 0.0
        self.last = 0.0

    def __call__(self) -> float:
        if self.page.url == "about:blank":
            self.start = main_thread_ms(self.holder)
            return 0
        self.last = max(self.last, main_thread_ms(self.holder) - self.start)
        return self.last

    def confirm(self) -> None:
        """Raise unless the loaded page still names the process this clock reads."""
        now = page_process(self.page)
        if now != self.holder:
            raise RuntimeError(
                f"The page's spins pointed to content process {self.holder} while it "
                f"was blank and to {now} once it loaded. Either the page moved or a "
                "busy process misled one of them, so the clock can't tell which "
                "process holds the page. Run it again."
            )


def profiling(page: Page, directory: Path | None):
    """What profiles the next span of a transition `name` into `directory`
    (`cpu_profile`) for the life of a block, each span to a file of its own
    (`name-1.cpuprofile`, ...), or nothing where there is no directory."""
    if directory is None:
        return lambda _: nullcontext()
    spans = Counter()

    def profiled(name: str):
        spans[name] += 1
        return cpu_profile(page, directory / f"{name}-{spans[name]}.cpuprofile")

    return profiled


def measure(browser, served: ServedPage, profiles: Path | None = None) -> dict:
    """Each of `COLUMNS` on the page `served`, with the elements the loaded page
    holds."""
    engine = browser.browser_type.name
    with tab(browser) as tab_page, main_thread_clock(engine, tab_page) as clock:
        # A superlinear path can hold the main thread for seconds per input on a
        # large page, which is what this measures rather than a failure.
        tab_page.set_default_timeout(DEADLINE_MS)
        profiled = profiling(tab_page, profiles)
        quiet = tab_page.wait_for_timeout

        def timed(name: str, act) -> tuple[float, float]:
            """`act`'s main-thread CPU and elapsed time, in ms, read over the span a
            profile of `name` covers, so the two leave out the same setup."""
            with profiled(name):
                start, began = clock(), time.monotonic()
                act()
                return clock() - start, (time.monotonic() - began) * 1000

        def idle_rate() -> float:
            """Wait for two quiet half seconds in a row, or QUIET_TRIES, and return
            the page's CPU per ms over the last two: what it spends with no input
            once the work a load leaves behind has run, such as the view checks the
            runtime reads after the page settles, which walk the whole page."""
            spent: list[float] = []
            while len(spent) < 2 or (
                max(spent[-2:]) >= QUIET_MS and len(spent) < QUIET_TRIES
            ):
                start = clock()
                quiet(500)
                spent.append(clock() - start)
            return sum(spent[-2:]) / 1000

        # The event answers are read off resource timing, whose buffer holds 250
        # entries by default, and the runtime's own modules fill it before any click.
        tab_page.add_init_script("performance.setResourceTimingBufferSize(100_000)")
        tab_page.add_init_script(path=PAINTED)
        idle = 0.0

        def load() -> None:
            nonlocal idle
            tab_page.goto(served.address)
            settle(tab_page)
            idle = idle_rate()

        costs = {"load": timed("load", load)[0]}
        if isinstance(clock, ContentClock):
            clock.confirm()
        elements = tab_page.evaluate("document.querySelectorAll('*').length")

        def per_input(name: str, count: int, act, ready=None) -> float:
            """The mean of `count` of `act`'s CPU, less the page's idle CPU over the
            time read: one window over them all and a quiet after them, or, where
            `ready` brings the page to where each input starts, a window over each,
            from `act` to its end, with `ready` outside it. A short window meets
            fewer of the page's own periodic tasks, which the idle rate leaves out."""

            def run(inputs: int, after: int) -> None:
                for _ in range(inputs):
                    act()
                quiet(after)

            spent = 0.0
            for inputs, after in [(count, 600)] if ready is None else [(1, 0)] * count:
                if ready is not None:
                    ready()
                cpu, elapsed = timed(name, partial(run, inputs, after))
                spent += cpu - idle * elapsed
            return spent / count

        def aim_at_option() -> None:
            """Rest the mouse over the first option's centre, in view, before its
            clicks begin, since a locator's click first runs its actionability checks
            on the page's main thread."""
            option = tab_page.locator("lf-option").first
            option.scroll_into_view_if_needed()
            box = option.bounding_box()
            assert box is not None
            tab_page.mouse.move(
                box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            )
            quiet(600)

        # A page with no option, such as a board, has no target for a click, the
        # Tab's first stop or a click's reading, so it reads none of them.
        options = tab_page.locator("lf-option").count() > 0
        if options:
            aim_at_option()

            def click():
                # Each click posts its event; the server's answer arrives before the
                # quiet that lets the page apply it.
                with tab_page.expect_response(
                    lambda response: response.url.endswith("/api/event")
                ):
                    tab_page.mouse.down()
                    tab_page.mouse.up()
                quiet(400)

            posted = len(tab_page.evaluate(EVENT_POSTS))
            costs["click"] = per_input("click", CLICKS, click)
            posts = tab_page.evaluate(EVENT_POSTS)[posted:]
            costs["event"] = statistics.median(post["ms"] for post in posts)
            costs["event_kb"] = statistics.median(post["kb"] for post in posts)

        field = tab_page.locator(".lf-fp-field").first
        field.click()
        quiet(600)
        letters = iter("abcdefghijklmnopqrstuvwxyz" * 4)

        def key():
            tab_page.keyboard.type(next(letters))
            quiet(60)

        costs["key"] = per_input("key", KEYS, key)

        # Escape takes the caret out of the field and keeps its draft, the keys'
        # words; each leave starts from a click back into it. On 2026-11-05 a leave
        # and an entry each finished within 50 ms at 256 sections.
        def enter():
            field.click()
            quiet(200)

        def leave():
            tab_page.keyboard.press("Escape")
            quiet(200)

        costs["leave"] = per_input("leave", LEAVES, leave, enter)

        if options:
            # From the first option's control, across the same stops at every size:
            # its ask's other controls and, after a short ask, the first link or
            # listing.
            tab_page.locator("lf-option-control").first.focus()
            quiet(600)
            ways = cycle(WAYS)

            def step():
                tab_page.keyboard.press("Tab" if next(ways) > 0 else "Shift+Tab")
                quiet(100)

            costs["tab"] = per_input("tab", TABS, step)

        tab_page.mouse.move(*tab_page.evaluate(HALFWAY, RUN * NOTCH))
        quiet(600)
        ways = cycle(WAYS)

        def wheel():
            tab_page.mouse.wheel(0, NOTCH * next(ways))
            quiet(50)

        costs["scroll"] = per_input("scroll", WHEEL_STEPS, wheel)

        # Written as an agent writes the page, whose server makes each valid save the
        # next revision, which the tab applies in place.
        source = served.directory / "index.html"
        authored = source.read_text(encoding="utf-8")
        revised = authored.replace("</h1>", f"</h1>{REVISED}", 1)
        writes = cycle(((revised, "attached"), (authored, "detached")))

        def revise():
            markup, state = next(writes)
            source.write_text(markup, encoding="utf-8")
            tab_page.wait_for_selector("#revised", state=state)
            quiet(300)

        costs["revision"] = per_input("revision", REVISIONS, revise)
        if options:
            # Clicks of its own, after every CPU reading: sampling for its goal costs
            # the page's main thread each frame, and arming it loads the runtime's
            # diagnostics, which no reading after it should count.
            aim_at_option()

            def click_until_shown() -> None:
                tab_page.mouse.down()
                tab_page.mouse.up()
                tab_page.wait_for_function(
                    "() => window.__leafBench.watch().goals.every(g => g.at !== null)"
                )

            def shown() -> float:
                """From a click to the first frame painted once the server's reading
                of its event is presented (`painted.js`), in ms."""
                tab_page.evaluate("goals => window.__leafBench.arm(goals)", SHOWN)
                timed("shown", click_until_shown)
                ms = tab_page.evaluate(
                    "() => window.__leafBench.watch().goals[0].at"
                    " - window.__leafBench.input()"
                )
                tab_page.evaluate("() => window.__leafBench.disarm()")
                quiet(200)
                return ms

            costs["shown"] = statistics.median(shown() for _ in range(CLICKS))
        return {"elements": elements, **costs}


def floors(rows: list[dict]) -> dict[str, float]:
    """Each browser cost's noise floor in `rows`, one run's readings by size from BASE,
    for each of `COLUMNS` they read."""
    unit = rows[0]["load"]
    return {
        cost: KB_FLOOR
        if cost == "event_kb"
        else FLOOR_SHARES.get(cost, FLOOR_SHARE) * unit
        for cost in COLUMNS
        if cost in rows[0]
    }


def exponent(
    sizes: list[int], costs: list[float], floor: float, fitted: int = FITTED
) -> float | None:
    """The least-squares slope of log growth on log size over the `fitted` largest
    sizes, where a cost's growth is what it adds to its cost at the first size,
    BASE. A size whose growth is under `floor` is left out, its growth the host's
    noise. With fewer than all but one of the fitted sizes left, or fewer than two,
    there is no exponent: the two largest of four server sizes stand 1.56 apart, and
    a slope across them reads a loaded host's noise as growth."""
    fixed = costs[0]
    pairs = [
        (math.log(n), math.log(c - fixed))
        for n, c in list(zip(sizes, costs, strict=True))[-fitted:]
        if c - fixed >= floor
    ]
    if len(pairs) < max(2, fitted - 1):
        return None
    mean_x = sum(x for x, _ in pairs) / len(pairs)
    mean_y = sum(y for _, y in pairs) / len(pairs)
    spread = sum((x - mean_x) ** 2 for x, _ in pairs)
    return sum((x - mean_x) * (y - mean_y) for x, y in pairs) / spread


def failures(
    rows: list[dict], noise: dict[str, float], fitted: int = FITTED
) -> dict[str, dict]:
    """Each cost in `noise` whose growth in `rows`, by size, above the first size and
    its floor there fits an exponent past SUPERLINEAR, which root `AGENTS.md`,
    "Responsiveness", rules out, with its readings and why."""
    sizes = [row["n"] for row in rows]
    failed = {}
    for cost, floor in noise.items():
        readings = [row[cost] for row in rows]
        slope = exponent(sizes, readings, floor, fitted)
        if slope is not None and slope > SUPERLINEAR:
            failed[cost] = {
                "by size": dict(zip(sizes, readings, strict=True)),
                "exponent": slope,
                "why": f"growth fits exponent {slope:.2f}, past {SUPERLINEAR}",
            }
    return failed


def interleaved[K](rounds: int, keys: Sequence[K]) -> Iterator[tuple[int, K]]:
    """Each round's number and each of `keys` once in it, for `rounds` rounds, the
    keys in order and then reversed in alternate rounds. A burst of load on the host
    lands on one reading of each key rather than on every reading of one, and no
    key always follows the same one, whose leftovers it would meet."""
    for number in range(rounds):
        for key in keys[:: 1 if number % 2 == 0 else -1]:
            yield number, key


def lowest[K: Hashable](
    rounds: int, keys: Sequence[K], read: Callable[[K, int], dict]
) -> dict[K, dict]:
    """Each key's lowest reading of each cost over `rounds` interleaved rounds
    (`interleaved`), where `read` takes the key and the round's number and returns
    its readings. A busy host adds time to a reading and never takes it away, so
    the lowest is the nearest the host lets a reading come to the work alone."""
    readings: dict[K, list[dict]] = {key: [] for key in keys}
    for number, key in interleaved(rounds, keys):
        readings[key].append(read(key, number))
    return {
        key: {cost: min(each[cost] for each in taken) for cost in taken[0]}
        for key, taken in readings.items()
    }


def table(
    title: str,
    rows: list[dict],
    count: str,
    costs: dict[str, str],
    noise: dict[str, float],
    fitted: int = FITTED,
) -> str:
    """`rows` by size, with the `count` each page held and each of `costs` under its
    label, then each cost's exponent over the `fitted` largest sizes above its floor
    in `noise`, marked `!` above SUPERLINEAR."""
    sizes = [row["n"] for row in rows]
    lines = [
        title,
        f"{'n':>6} {count:>9}" + "".join(f" {label:>10}" for label in costs.values()),
    ]
    for row in rows:
        lines.append(
            f"{row['n']:>6} {row[count]:>9}"
            + "".join(f" {row[cost]:>10.1f}" for cost in costs)
        )
    cells = []
    for cost in costs:
        slope = exponent(sizes, [row[cost] for row in rows], noise[cost], fitted)
        mark = "!" if slope is not None and slope > SUPERLINEAR else " "
        cells.append(f" {'-' if slope is None else f'{slope:.2f}':>9}{mark}")
    lines.append(f"{'exponent':>16}" + "".join(cells))
    return "\n".join(lines)


def growth(
    before: dict[str, float], after: dict[str, float], ratio: float
) -> list[str]:
    """The functions whose inclusive ms grew superlinearly from `before` to `after`,
    profiles of the smallest and largest page, whose sizes stand at `ratio`."""
    grown = []
    for name, ms in after.items():
        if ms < GROWTH_FLOOR_MS or name.startswith(("(root)", "(program)", "(idle)")):
            continue
        was = before.get(name, 0)
        slope = math.log(ms / was) / math.log(ratio) if was else math.inf
        if slope > SUPERLINEAR:
            grown.append((ms, was, slope, name))
    return [
        f"  {was:8.0f} -> {ms:8.0f} ms  exponent {slope:5.2f}  {name}"
        for ms, was, slope, name in sorted(grown, reverse=True)[:12]
    ]


@contextmanager
def serving_collection(arm: Path, collection: Collection, n: int, scratch: Path):
    """Write `collection`'s page of size `n` as an authored source under `scratch`,
    its earlier versions where a fixture keeps them, serve it from `arm` with its log
    admitted (`serving_source`), and yield the page it serves."""
    *earlier, authored = collection.sources(n)
    source = scratch / "source" / "page.html"
    (source.parent / "versions").mkdir(parents=True)
    source.write_text(authored)
    for version, markup in enumerate(earlier, 1):
        (source.parent / "versions" / f"page.v{version}.html").write_text(markup)
    seed = None
    if events := collection.log(n):
        # Not the source's stem, which would make it the page's own history.
        seed = scratch / "seed.jsonl"
        seed.write_text("".join(json.dumps(event) + "\n" for event in events))
    with serving_source(arm, source, scratch / "page", seed):
        yield served_page.get()


def report_growth(title: str, profiles: dict, ratio: float) -> None:
    """Echo the functions that grew superlinearly in each of `profiles`, a pair of
    inclusive ms by function (smallest page, largest) by what was profiled."""
    for name, (before, after) in profiles.items():
        if lines := growth(before, after, ratio):
            click.echo(f"{title} {name}: superlinear functions")
            click.echo("\n".join(lines) + "\n")


def inclusive_ms(directory: Path, transition: str) -> dict[str, float]:
    """Each function's inclusive ms over every span of `transition` profiled into
    `directory` (`profiling`)."""
    spans = sorted(directory.glob(f"{transition}-*.cpuprofile"))
    _own, inclusive = Profile(*spans).functions()
    return {name: us / 1000 for name, us in inclusive.items()}


@click.command()
@click.argument("axes", nargs=-1, type=click.Choice(sorted(COLLECTIONS)))
@click.option(
    "--server",
    is_flag=True,
    help="Time the server's paths in this process, without a browser.",
)
@click.option(
    "--sizes",
    help="Comma-separated page sizes, measured beside the page of BASE "
    f"[default: {','.join(map(str, SIZES))}, or with --server "
    f"{','.join(map(str, SERVER_SIZES))}].",
)
@click.option(
    "--rounds",
    type=click.IntRange(1),
    help="Measure every page this many times, interleaved, and report each cost's "
    "lowest reading [default: 1, or with --server 3].",
)
@engine_option
@base_option()
@click.option("--profile", is_flag=True, help="Profile the smallest and largest size.")
def scaling(
    axes: tuple[str, ...],
    server: bool,
    sizes: str | None,
    rounds: int | None,
    engine: str,
    base: str | None,
    profile: bool,
) -> None:
    chosen_sizes = sizes.split(",") if sizes else SERVER_SIZES if server else SIZES
    sized = sorted({BASE, *map(int, chosen_sizes)})
    run = run_directory(OUT)
    if server:
        if base is not None:
            raise click.UsageError("--server measures this checkout only")
        scale_server(axes or SERVER_AXES, sized, rounds, profile, run)
        return
    if engine not in ("chromium", "firefox"):
        raise click.UsageError(
            "--browser: this reads Chromium's and Firefox's CPU only"
        )
    if profile and engine != "chromium":
        raise click.UsageError("--profile is V8's; this module's header says Firefox's")
    arms = choose_arms(base, run)
    click.echo(describe(arms) + "\n")
    results: dict[str, dict[str, list[dict]]] = {}
    ends = (sized[0], sized[-1])
    with headless_shell() if engine == "chromium" else launch(engine) as browser:
        for axis in axes or tuple(AXES):
            by_arm = measure_rounds(
                browser,
                arms,
                COLLECTIONS[axis],
                sized,
                rounds or 1,
                run / axis,
                profile,
            )
            results[axis] = by_arm
            for arm, rows in by_arm.items():
                title = f"{axis} ({arm}, {engine})"
                read = {
                    cost: label for cost, label in COLUMNS.items() if cost in rows[0]
                }
                click.echo(table(title, rows, "elements", read, floors(rows)))
                if missing := [cost for cost in COLUMNS if cost not in read]:
                    click.echo(
                        f"  missing, with no option to aim at: {', '.join(missing)}"
                    )
                if (largest := rows[-1]).get("shown", 0) > BUDGET_MS:
                    click.echo(
                        f"  shown: {largest['shown']:.0f} ms at {largest['n']}, "
                        f"over {BUDGET_MS} ms"
                    )
                click.echo()
                if profile:
                    report_growth(
                        f"{axis} ({arm})",
                        {
                            transition: tuple(
                                inclusive_ms(run / axis / f"{arm}-{n}", transition)
                                for n in ends
                            )
                            for transition in TRANSITIONS
                        },
                        sized[-1] / sized[0],
                    )
    (run / "results.json").write_text(json.dumps(results, indent=1))
    click.echo(f"Results in {run.relative_to(ROOT)}")


def measure_rounds(
    browser,
    arms: dict[str, Arm],
    collection: Collection,
    sizes: list[int],
    rounds: int,
    directory: Path,
    profile: bool = False,
) -> dict[str, list[dict]]:
    """Each arm's rows, by size, of the lowest of each cost `measure` reads over
    `rounds` (`lowest`) on `collection`'s page at each of `sizes`, each served from
    its arm under `directory` throughout, each round taking every size in turn and
    each arm at each. With `profile`, the first round profiles the smallest and the
    largest page into their directories, so where there are more rounds, the lowest
    reading is one the profiler didn't slow."""
    with ExitStack() as serving:
        pages = {
            (n, arm): serving.enter_context(
                serving_collection(
                    chosen.directory, collection, n, directory / f"{arm}-{n}"
                )
            )
            for n in sizes
            for arm, chosen in arms.items()
        }

        def read(key: tuple[int, str], number: int) -> dict:
            n, arm = key
            profiled = profile and number == 0 and n in (sizes[0], sizes[-1])
            scratch = directory / f"{arm}-{n}" if profiled else None
            return measure(browser, pages[key], scratch)

        readings = lowest(rounds, list(pages), read)
    engine = browser.browser_type.name
    return {
        arm: [{"n": n, "engine": engine, **readings[n, arm]} for n in sizes]
        for arm in arms
    }


def scale_server(
    axes: Iterable[str], sizes: list[int], rounds: int | None, profile: bool, run: Path
):
    """Time each server path on each axis's pages in this process, as `--server`
    does (`leaf_dev.server_scaling`), and name each path that breaks the rule
    (`failures`)."""
    from leaf_dev.server_scaling import FITTED, PATHS, RUNS, measure, over_budget
    from leaf_dev.server_scaling import floors as path_floors

    rounds = rounds or RUNS
    click.echo(f"Server paths of this checkout, least CPU of {rounds} runs\n")
    results = {}
    for axis in axes:
        rows, profiles = measure(COLLECTIONS[axis], sizes, run / axis, profile, rounds)
        results[axis] = rows
        paths = {path: f"{path} ms" for path in PATHS if path in rows[0]}
        noise = path_floors(rows)
        click.echo(table(axis, rows, "events", paths, noise, FITTED))
        for path, failure in failures(rows, noise, FITTED).items():
            click.echo(f"  {path}: {failure['why']}")
        if why := over_budget(rows):
            click.echo(f"  click: {why}")
        click.echo()
        if profile:
            report_growth(axis, profiles, sizes[-1] / sizes[0])
    (run / "results.json").write_text(json.dumps(results, indent=1))
    click.echo(f"Results in {run.relative_to(ROOT)}")
