"""Measure what a Leaf page costs to load and to answer each input a user or agent
makes, in a browser or on the server, on this working tree and on a base.

    uv run leaf-dev bench [PAGE ...] [--sizes 32,64,128,256] [--input NAME ...]
        [--read cpu|paint|server ...] [--rounds N] [--base [REF]]
        [--browser firefox] [--profile]

Each PAGE names a page `COLLECTIONS` generates, which holds `n` of one collection and
a fixed amount of the rest, or an authored example or the corpus (`named_source`).
A generated page is measured at each of `--sizes` and at BASE, whose costs are mostly
the runtime's fixed work. Root `AGENTS.md`, "Responsiveness", sets the rule the sizes
check: no cost grows faster than the page, and an input's should hardly grow at all.
With no PAGE, the browser reads `AXES` and the server `SERVER_AXES`.

Each page is served from each arm: this working tree, and with `--base` the merge base
with main or REF, chosen as every A/B command chooses its arms (`arms.choose_arms`).
`INPUTS` lists the inputs in the order a pass takes them, each the same at every size,
and `--input` takes some of them. A page without what an input needs, such as an
option to click, reads none of that input, and the report names it as missing.

`--read` chooses what is read, by default `cpu` and `paint`, and in Firefox `cpu`:

- `cpu` reads the page's main-thread CPU in a tab of its own (`cpu_pass`): the load
  until the page settles and its main thread goes quiet, then each input's mean over
  several, less the page's idle CPU over the same time. Beside an input that posts
  events stand the server's time to start answering them and their answers' size.
- `paint` times each input in another tab (`paint_pass`), as many times as the CPU
  pass reads it, and reads the median: from its input event, or from an agent's first
  write to the file it changes, to the first frame that paints its result (`painted`);
  for a gesture, also to the arrival of its POST's answer (`answered`) and to the
  frame that presents the server's reading of its event (`shown`), which root
  `AGENTS.md` holds to BUDGET_MS. Each frame is timed as it is laid out, just before
  it paints (`leaf_dev.painted`). Each counts the requests and bytes it caused
  (`Traffic`).
- `server` times the server's paths on each generated page in this process, with no
  browser, on this checkout only (`measure_server`).

Each pass reads a POST its own way. The CPU pass reads it from the page's Resource
Timing, which every engine keeps and which adds no work to the main thread it times.
The paint pass reads Chrome's network data, which it takes anyway to attribute every
request in the window to its starter, and which names the POST's attempt.

Each reading is a row of its page's table, with a column for each size and arm. With
three sizes or more, each reading's growth above the BASE page is fitted over the
largest sizes (least squares of log growth on log size), and an exponent above the
reading's `limit` is marked `!`. The CPU of an input the browser answers alone, such
as a keystroke or a wheel step, and the requests and bytes an input causes shouldn't
grow at all (`held`), so above GROWING it marks a walk of the page on each input, or
the page sent whole for a change to part of it. Any other reading, and any of an input
whose result is the whole page (`Input`), may grow with the page, so above
SUPERLINEAR it marks a step nesting one walk of the page inside another. Fitting the
cost itself would let fixed work hide that: 30 ms per click plus 20/80/320 ms of
quadratic work fits 1.4 over 64-256, and its growth fits 2.0. A mark is for the
reader; nothing passes or fails on it (tests/AGENTS.md, "Results do not depend on
execution speed").

Each pass reads a page built afresh, so no input meets what another pass or round made
on the page, and a pass takes the inputs on the page's own content before those that
add threads and to-dos. --rounds measures every page N times. The rounds are
interleaved (`interleaved`): each takes every size in turn and every arm at each size,
so a burst of load lands on one reading of each page, and the table shows each
reading's lowest, since a busy host adds time to a reading and never takes it away.
Every round's readings, each paint window's requests and the pages land in a run
directory under `.tmp/bench/`, whose `results.json` also keeps the table's lowest
readings by page, size and arm (`lowest`).

--profile records a V8 CPU profile (`leaf_dev.profiles`) of each span a reading covers,
and no more, in the first round. The CPU pass's, at the smallest and largest size, list
the functions whose time over an input's spans grew between them past the input's
`limit`, which names the walk. The paint pass's, at the largest size, run under a
Chrome trace too, and say what held the main thread from the input to the last
painted goal (`attribute`). Profiling slows the page, so read proportions from a
profiled run and durations from one without.

--browser firefox measures Playwright's Firefox, on macOS, and reads only `cpu`.
Firefox offers no count of its tasks, so there an input's CPU is the page's main
thread's as the OS counts it (`ContentClock`), the clock Chromium's thread ticks read.
To name what took Firefox's time, run under the Gecko profiler's variables;
the browser writes a profile of the whole run as it closes, which
<https://profiler.firefox.com> reads, and its samples' `threadCPUDelta` sum to the
OS's count:

    MOZ_PROFILER_STARTUP=1 MOZ_PROFILER_SHUTDOWN=$PWD/.tmp/gecko.json \\
    MOZ_PROFILER_STARTUP_FEATURES=js MOZ_PROFILER_STARTUP_FILTERS=GeckoMain,StyleThread \\
    MOZ_PROFILER_STARTUP_ENTRIES=134217728 uv run leaf-dev bench asks --browser firefox

CPU time spreads less than elapsed time on a loaded host, and each exponent compares
sizes within one run. `event`, `painted`, `answered` and `shown` are elapsed time, which
a busy host stretches, and so does a run held to the efficiency cores, as
`taskpolicy -c utility` holds it. The daily CI run measures the generated pages and
charts their readings (`.github/workflows/ci.yaml`, `bench`).
"""

import cProfile
import ctypes
import gc
import itertools
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import time
from collections import Counter
from collections.abc import (
    Callable,
    Container,
    Generator,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from contextlib import contextmanager, nullcontext, suppress
from dataclasses import asdict, dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch
from urllib.parse import urlsplit

import click
import psutil
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from leaf.source.data import PUBLICATION, source_file
from leaf.source.render_checks import OUTSTANDING, wait_until_ready
from leaf_dev import ROOT
from leaf_dev.arms import (
    Arm,
    ServedPage,
    base_option,
    choose_arms,
    describe,
    environment,
    load_average,
    run_directory,
    served_page,
    serving_source,
)
from leaf_dev.browser import (
    PANEL_THREAD,
    chromium_metrics,
    engine_option,
    go_to_threads,
    headless_shell,
    launch,
    load,
    tab,
)
from leaf_dev.example_data import data_file, named_source
from leaf_dev.main_thread import SCRIPT as MAIN_THREAD
from leaf_dev.main_thread import main_thread
from leaf_dev.painted import SCRIPT as PAINTED
from leaf_dev.profiles import Profile, cpu_profile

OUT = ROOT / ".tmp" / "bench"
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
# reading's growth above it, so it is a small fraction of the sizes fitted.
BASE = 8
# An exponent above this is superlinear growth. It stands halfway between linear and
# quadratic: above BASE, linear growth fits about 1.07 over 64-256, and n log n 1.25.
SUPERLINEAR = 1.5
# An exponent above this, halfway between constant and linear, is growth, where a
# reading shouldn't grow with the page at all (`held`).
GROWING = 0.5
# How many of the largest sizes the exponent is fitted over.
FITTED = 3
# Where a reading grows by less than its floor above BASE, what little it grew is the
# host's noise, and its exponent leaves that size out. A floor is a share of the BASE
# page's load CPU from the same run. A slower machine slows that reading as much as
# every other, so it fits the same sizes to the same exponent. Where the BASE page
# loads in about 200 ms, the shares put a floor near 10 ms of CPU and near 50 ms of
# elapsed time. Sizes and counts no machine's speed changes have
# floors of their own.
FLOOR_SHARES = {"cpu": 0.05, "elapsed": 0.25}
COUNT_FLOORS = {"KB": 10, "requests": 1}
# A held reading's floor is this share of its own reading on the BASE page, as a server
# path's is its own (`server_floors`), and a held count's is at least one. A
# keystroke's CPU is a few ms, less than the load's share, so a floor from the load
# would hide its doubling, and a POST's 4 KB answer growing to 20 KB stays under the
# fixed 10 KB.
HELD_FLOOR_SHARE = 0.25
# Root `AGENTS.md`, "Responsiveness": a gesture shows the server's reading within this
# many ms on the largest page.
BUDGET_MS = 100
# How long any one wait may take: a superlinear path can hold the main thread for
# seconds per input on a large page, which is what this measures rather than a
# failure.
DEADLINE_MS = 300_000
# A notch of a mouse wheel, which Chromium and Firefox here both scroll 100 px.
NOTCH = 100
# How far the pointer moves at each step of a hover, about a line of the page's text.
LINE = 24
# A wheel, a hover or Tab takes RUN steps one way and then as many back, so it stays
# among the same few rows or stops at every size, the smallest page's included.
RUN = 4
WAYS = (1,) * RUN + (-1,) * RUN
# A half second in which the page's main thread spends under this is quiet; two in a
# row end the load (`cpu_pass`), or QUIET_TRIES half seconds on a host too busy for
# two.
QUIET_MS = 5
QUIET_TRIES = 20
# How long the page's ledger must stay quiet before a paint window closes, and how
# long each paint pass leaves the page alone once it has loaded, so the requests it
# starts on its own name the code that starts them (`Traffic`).
SETTLE_MS = 250
ALONE_S = 2
# A function must take this long at the largest size to be listed as growing.
GROWTH_FLOOR_MS = 20
THREAD_TEXT = "Bench thread.\n\n" + "\n\n".join(
    f"Earlier conversation paragraph {line + 1}." for line in range(20)
)
# The steps each of `side_documents`' sources holds, two lines a step: a few percent of
# a 4 MB document, long enough that a walk of every document's rows on each tab
# opened shows at 256, and short enough to keep the daily run to minutes.
DOCUMENT_STEPS = 1024
# A word every line of `steps` holds, which `matches` searches for.
WORD = "value"
# What the inputs on `side_documents`' pages need: its tab list and first document,
# bound to a source, by the ids the page gives them, which the inputs find the other
# tabs and documents by.
DOCUMENTS = "#docs #d0[source]"

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
# The passage a comment selects, brought into view: the `nth` paragraph drawn after the
# page's title, past any a comment's editor holds, or the title where none is.
PASSAGE = """(nth) => {
  const title = document.querySelector("h1");
  const passage = [...document.querySelectorAll("p")].filter(
    (p) =>
      title.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING &&
      !p.closest("[contenteditable]") &&
      p.checkVisibility(),
  )[nth] ?? title;
  passage.scrollIntoView({ block: "nearest" });
  const box = passage.getBoundingClientRect();
  return [box.x, box.y];
}"""
# The centre of the control of the tab whose panel is `panel`, brought into view.
TAB_CONTROL = """(panel) => {
  const control = document.querySelector(`[role=tab][aria-controls="${panel}"]`);
  control.scrollIntoView({ block: "nearest" });
  const box = control.getBoundingClientRect();
  return [box.x + box.width / 2, box.y + box.height / 2];
}"""
# The centre of the element `selector` names, or null where none shows yet.
CENTRE = """(selector) => {
  const node = document.querySelector(selector);
  if (!node?.checkVisibility()) return null;
  const box = node.getBoundingClientRect();
  return [box.x + box.width / 2, box.y + box.height / 2];
}"""
# The centres of the page's first two tab controls, the first brought into view.
TAB_CENTRES = """() => {
  const controls = [...document.querySelectorAll("[role=tab]")].slice(0, 2);
  controls[0].scrollIntoView({ block: "nearest" });
  return controls.map((control) => {
    const box = control.getBoundingClientRect();
    return [box.x + box.width / 2, box.y + box.height / 2];
  });
}"""
# The leaf, the menu's tab at the On view's foot, which the leaf may have opened on
# another, its Annotations, and Capture area's row there.
MENU_ROWS = (
    ".lf-fp-leaf",
    ".lf-fp-controls .lf-fp-filters > button:first-child",
    '.lf-fp-item[data-lf-row="group:annotate"]',
    '.lf-fp-item[data-lf-row="command:capture.region.open"]',
)
# The number of the document `side_documents` shows, in the tab open now.
SHOWN_DOCUMENT = """() => Number(document
  .querySelector('#docs [role=tab][aria-selected="true"]')
  .getAttribute("aria-controls").slice(1))"""
# Whether document `d`'s first line shows in its syntax colour.
COLOURED = """(d) => {
  const row = document.querySelector(`#d${d} .lf-text-document-run > div`);
  if (!row?.checkVisibility()) return false;
  for (const [name, highlight] of CSS.highlights)
    if (name.startsWith("lf-token-"))
      for (const range of highlight) if (range.startContainer === row.firstChild) return true;
  return false;
}"""
# How tall the run of a text document's lines at a point stands.
RUN_HEIGHT = """([x, y]) => document.elementFromPoint(x, y)
  .closest(".lf-text-document-run").getBoundingClientRect().height"""
# The target of the margin row whose thread card is open.
OPEN_ROW = """() => document
  .querySelector('[aria-controls="lf-margin-preview"][aria-expanded="true"]')
  ?.closest("[data-lf-margin-for]")?.dataset.lfMarginFor"""
# The first card not in its board's first column, and the column left of it.
MOVABLE = """() => {
  for (const card of document.querySelectorAll("lf-card")) {
    const left = card.parentElement.previousElementSibling;
    if (left?.matches("lf-column")) return [card.id, left.id];
  }
  return null;
}"""
EVENT_POSTS = """() => performance.getEntriesByType("resource")
  .filter((entry) => new URL(entry.name).pathname.endsWith("/api/event"))
  .map((entry) => ({
    ms: entry.responseStart - entry.requestStart,
    kb: entry.encodedBodySize / 1024,
  }))"""
# The page is still ready, read as `wait_until_ready` reads it, and every trip its
# ledger counts has ended (`__leafBench.quiet`).
TRIPS_ENDED = (
    f"() => ({OUTSTANDING})({{held: null, through: null}}) === 'ready'"
    " && window.__leafBench.quiet()"
)
# How long `page_process` spins a page's main thread to find its process, how many
# times it tries, and the spin, which ends by the page's own clock and is named so a
# profile of the page shows it.
SPIN_MS = 30
SPIN_TRIES = 10
SPIN = """function benchSpin(ms) {
  const end = performance.now() + ms;
  while (performance.now() < end);
}"""
# `proc_pidinfo`'s flavors for a process's threads and one thread's times, in
# `sys/proc_info.h`.
PROC_PIDLISTTHREADS = 6
PROC_PIDTHREADINFO = 5
# What --profile's trace records, and how `attribute` reads it.
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
# The shortest main-thread task a paint profile lists, how many entries each list
# keeps, and how many owners of the main thread the report prints for each input.
TASK_MIN_MS = 2
TOP = 12
OWNERS = 6


def ask(g: int, options: int = 4) -> str:
    """Section `g`: a heading, a paragraph and a question section of `options` options."""
    return (
        f'<section id="s{g}"><h2>Section {g}</h2><p>Some words about section {g}.</p>'
        f'<lf-group id="q{g}" label="Question {g}"><h3 id="q{g}-h">Question {g}</h3><lf-options id="o{g}" multiple>'
        + "".join(
            f'<lf-option id="o{g}-{i}" label="Option {i}"><strong>Option {i}</strong> a short description.'
            "</lf-option>"
            for i in range(1, options + 1)
        )
        + "</lf-options></lf-group></section>"
    )


# One file's patch, sixteen lines with four changed, which `lf-diff` draws with a
# comment control on each line.
PATCH = (
    '<lf-diff id="patch"><pre>\n'
    "diff --git a/steps.py b/steps.py\n--- a/steps.py\n+++ b/steps.py\n"
    "@@ -1,16 +1,16 @@\n"
    + "".join(
        f"-step_{g} = {g}\n+step_{g} = {g} + 1\n"
        if g % 4 == 3
        else f" step_{g} = {g}\n"
        for g in range(16)
    )
    + "</pre></lf-diff>"
)


def ask_sections(n: int) -> str:
    """`PATCH`, then `n` sections, each an `ask`, so widgets, obligations on the user,
    headings and margin pins all grow with `n`. A comment box opened on a line of the
    patch stands in the page's flow, so opening it moves every section and pin below."""
    return page("Questions", PATCH + "".join(ask(g) for g in range(1, n + 1)))


def board_sections(boards: int, cards: int, done: int = 0) -> str:
    """`boards` sections, each an `lf-board` of `cards` cards to do and `done` done."""

    def column(b: int, name: str, count: int) -> str:
        return (
            f'<lf-column id="b{b}-{name}" label="{name.title()}">'
            + "".join(
                f'<lf-card id="b{b}-{name}{j}" label="Card {j}"><strong>Card {j}</strong> of board {b}.</lf-card>'
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


def draft_sections(n: int) -> str:
    """`n` sections, each a heading and a question asking for an edit of a required
    `lf-draft` of a few Markdown blocks, so drafts, obligations on the user and
    headings grow with `n`."""
    return page(
        "Drafts",
        "".join(
            f'<section id="s{g}"><h2>Draft {g}</h2>'
            f'<lf-group id="q{g}" label="Edit release note {g}?">'
            f'<lf-draft id="d{g}" required><pre>\n'
            f"Release note {g}: adds `--dry-run` to every mutating command.\n\n"
            f"- Prints each change step {g} would make.\n"
            "- Writes nothing.\n\n"
            f"See **section {g}** for the flags it takes.</pre></lf-draft>"
            "</lf-group></section>"
            for g in range(1, n + 1)
        ),
    )


def call_diff(g: int) -> dict:
    """Call diff `g`, CallDiff's native JSON for one entry point whose call tree keeps
    two calls and changes a third, removed with its callee and added with another, at
    lines of `PATCH`'s `steps.py`."""

    def call(name: str, status: str, line: int, *children: dict) -> dict:
        return {
            "key": name,
            "label": f"{name}()",
            "status": status,
            "kind": "call",
            "file": "steps.py",
            "line": line,
            "children": list(children),
        }

    tree = call(
        f"run_{g}",
        "same",
        1,
        call("step_1", "same", 2),
        call("step_3", "removed", 4, call("step_2", "removed", 3)),
        call("step_3", "added", 4, call("step_5", "added", 6)),
        call("step_8", "same", 9),
    )
    return {
        "mode": "diff",
        "from": "HEAD~",
        "to": "HEAD",
        "trees": [{"entry": f"run_{g}", "tree": tree}],
    }


def call_diff_sections(n: int) -> str:
    """`PATCH`, then `n` sections, each a heading and an `lf-call-diff` of its own
    source (`call_diff`) linked to the patch: call diffs and headings grow with `n`."""
    return page(
        "Call diffs",
        PATCH
        + "".join(
            f'<section id="s{g}"><h2>Calls {g}</h2>'
            f'<lf-call-diff id="cd{g}" source="c{g}" diff="patch"></lf-call-diff>'
            "</section>"
            for g in range(1, n + 1)
        ),
    )


def prose_sections(n: int, track: str = "") -> str:
    """`n` sections of headings and paragraphs after one ask: the document grows, and
    the widgets don't. `track` is what a sidebar beside it holds, if anything."""
    question = (
        '<lf-group id="q0" label="Question"><h3 id="q0-h">Question</h3><lf-options id="o0" multiple>'
        '<lf-option id="o0-1">One</lf-option><lf-option id="o0-2">Two</lf-option>'
        "</lf-options></lf-group>"
    )
    sections = "".join(
        f'<section id="s{g}"><h2>Section {g}</h2>'
        f"<p>Some words about section {g}, enough for a line or two of reading.</p>"
        f'<p>Another paragraph in section {g} with a <a href="#s1">link</a>.</p>'
        "</section>"
        for g in range(1, n + 1)
    )
    return page("Prose", question + sections, track)


def contents_sections(n: int) -> str:
    """`prose_sections(n)` beside a track holding an `lf-toc`: a row, a marker and a
    heading the reading position follows for each of the `n` sections, so the map's
    fitting and the reading position grow with the outline."""
    return prose_sections(n, track='<lf-toc id="contents"></lf-toc>')


def steps(count: int, name: str = "") -> str:
    """`count` steps of Python, two lines each, every line naming `WORD`, and each
    step's comment naming the file it stands in, `name`."""
    return "".join(
        f'def step_{g}(value):  # {name}step {g}\n    return value * {g} + "{g}"\n'
        for g in range(count)
    )


def document_lines(n: int) -> str:
    """One ask and a text document of `n` × 64 lines of Python, written in its `<pre>`:
    the document's text grows, and the widgets don't."""
    question = (
        '<lf-group id="q0" label="Question"><h3 id="q0-h">Question</h3><lf-options id="o0" multiple>'
        '<lf-option id="o0-1">One</lf-option><lf-option id="o0-2">Two</lf-option>'
        "</lf-options></lf-group>"
    )
    document = (
        '<lf-text-document id="listing" label="steps.py">'
        f'<pre><code class="language-python">{steps(n * 32)}</code></pre>'
        "</lf-text-document>"
    )
    return page("Document", question + document)


def documents(n: int) -> int:
    """How many documents `side_documents(n)` holds: the one shown, one in a closed
    tab for each eight of `n`, and one more, so the BASE page has the two closed tabs
    `reveal` opens and 256 holds about thirty."""
    return 2 + n // 8


def side_documents(n: int) -> str:
    """A page of a side list of tabs, each holding a text document bound to a
    source of its own (`document_sources`), the first tab's shown and the rest closed.
    The documents grow in number and each stays as long, so a cost that grows with
    the documents the page holds, such as every source sent on a write to one
    (`data`), grows with `n`, and one that grows with the length of the document
    opened stays level and shows only beside another arm. The text is Python, whose
    syntax colour paints most words, as the colour a tab keeps is what `browse`
    reads."""
    tabs = "".join(
        f'<lf-tab id="t{d}" label="Document {d}"><lf-text-document id="d{d}" '
        f'source="s{d}" label="document_{d}.py" class="language-python"></lf-text-document>'
        "</lf-tab>"
        for d in range(documents(n))
    )
    return page("Documents", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')


def side_asks(n: int) -> str:
    """A side list of `n` tabs, each holding one section's ask, so each tab marks the
    state of the obligation its panel holds. A click on an option redraws every tab's
    mark, so the CPU of that click reads what counting each panel's obligations costs
    (#5722)."""
    tabs = "".join(
        f'<lf-tab id="t{g}" label="Tab {g}">{ask(g)}</lf-tab>' for g in range(1, n + 1)
    )
    return page("Asks", f'<lf-tabs id="tabs" list="side">{tabs}</lf-tabs>')


def document_text(d: int, first: str | None = None) -> str:
    """Document `d`'s text: DOCUMENT_STEPS steps, with its first line `first` where
    given, as an agent's write changes one line of it."""
    text = steps(DOCUMENT_STEPS, f"document {d}, ")
    if first is None:
        return text
    return first + text[text.index("\n") :]


def document_sources(n: int) -> dict[str, str]:
    """Each source `side_documents(n)` binds, by name, with its document's text."""
    return {f"s{d}": document_text(d) for d in range(documents(n))}


def table_rows(n: int) -> str:
    """One ask and a table of `n` rows of four cells, one of them code, as the largest
    real pages' tables are: the table's cells grow, and the widgets and headings don't."""
    question = (
        '<lf-group id="q0" label="Question"><h3 id="q0-h">Question</h3><lf-options id="o0" multiple>'
        '<lf-option id="o0-1">One</lf-option><lf-option id="o0-2">Two</lf-option>'
        "</lf-options></lf-group>"
    )
    rows = "".join(
        f"<tr><td>Row {r}</td><td><code>branch-{r}</code></td><td>{r} days</td>"
        f"<td>Some words about row {r}.</td></tr>"
        for r in range(n)
    )
    table = (
        "<table><thead><tr><th>Row</th><th>Branch</th><th>Age</th><th>Note</th></tr>"
        f"</thead><tbody>{rows}</tbody></table>"
    )
    return page("Rows", question + table)


def page(title: str, body: str, track: str = "") -> str:
    """A page of `body` under its title, beside a sidebar's track holding `track` if
    there is one."""
    article = f'<article id="document"><h1>{title}</h1>{body}</article>'
    main = (
        '<main class="layout-sidebar"><aside><div class="layout-track">'
        f'{track}</div></aside><div class="layout-column">{article}</div></main>'
        if track
        else f"<main>{article}</main>"
    )
    return (
        f'<!doctype html><html lang="en"><head><title>{title}</title></head><body>'
        f"{main}</body></html>"
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
        # Each ask takes several options, so a pick leaves it open until Done.
        "answered": False,
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


# The user's comment on the words of `ask_sections`' first paragraph, which the page
# paints as a passage mark: a highlight range, where a comment on a whole section
# outlines its element.
PASSAGE_COMMENT = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "id": "c-passage",
    "text": "Why these words?",
    "anchor": {"section": "s1", "quote": "Some words about section 1."},
}


def passage_comment(t: int) -> dict:
    """The user's comment on the words of section `t` of `prose_sections`, a passage
    mark like `PASSAGE_COMMENT`."""
    return {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "id": f"p{t}",
        "text": f"Why these words in section {t}?",
        "anchor": {"section": f"s{t}", "quote": f"Some words about section {t},"},
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
        "session": "bench",
        "thread": "c0",
        "from": f"m{m - 3}",
        "through": f"m{m}",
        "text": f"Messages {m - 3} to {m}, in a line.",
    }
    return [message, summary]


class Collection(NamedTuple):
    """A page that holds `n` of one collection and a fixed amount of the rest: its
    authored markup, the events its log holds after it, how many versions of the
    page are saved before the log, and the value of each source it binds."""

    authored: Callable[[int], str]
    log: Callable[[int], list[dict]] = lambda _: []
    versions: Callable[[int], int] = lambda _: 1
    data: Callable[[int], Mapping[str, object]] = lambda _: {}

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


# Every page `leaf-dev bench` generates, by the collection that grows with `n`.
COLLECTIONS: dict[str, Collection] = {
    "asks": Collection(ask_sections),
    # The same with one passage mark, whose style every input may restyle page-wide.
    "asks-marked": Collection(ask_sections, lambda _: [PASSAGE_COMMENT]),
    "document": Collection(document_lines),
    "prose": Collection(prose_sections),
    # The same with a passage mark in every section.
    "passages": Collection(
        prose_sections, lambda n: [passage_comment(t) for t in range(1, n + 1)]
    ),
    "rows": Collection(table_rows),
    # Prose beside a reading map of its sections.
    "contents": Collection(contents_sections),
    "documents": Collection(side_documents, data=document_sources),
    "asktabs": Collection(side_asks),
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
    "drafts": Collection(draft_sections),
    "calldiffs": Collection(
        call_diff_sections,
        data=lambda n: {f"c{g}": call_diff(g) for g in range(1, n + 1)},
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
# The pages the browser reads by default; any other page is one more name here.
AXES = ("asks", "document", "prose", "rows", "threads")


@dataclass
class Request:
    """A request a paint tab started, as the browser reported it: the code that started
    it (`starter`), and when it started and ended, in epoch milliseconds."""

    url: str
    starter: str
    start: float
    # Seconds the browser's clock for request events stands behind the epoch.
    offset: float
    # The attempt an event POST carries, which `Traffic.answered` looks for.
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
class Traffic:
    """Every request one page's paint tabs started, in every frame, across the rounds,
    and when each tab left the page alone.

    The page keeps starting requests on its own, such as its freshness read every
    250 ms and its report of the reader's view. A request whose starter also started
    one while the page was left alone, in any round, is the page's own, and `split`
    counts each window's requests less those."""

    requests: dict[str, Request] = field(default_factory=dict)
    alone_spans: list[tuple[float, float]] = field(default_factory=list)

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
        its starter."""
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
            "starters": dict(Counter(request.starter for request in seen)),
        }

    def split(self, windows: list[dict]) -> None:
        """Split each window's requests into the ones its input caused and the page's
        own. A window's `requests` and `bytes` count the caused ones, `own_requests`
        and `own_bytes` the rest, and `entries` lists each.

        A starter the page uses both on its own and for an input counts as the page's
        own in every window once the page has used it alone, as `readState` would be
        if the page's 2 s clock read state while alone, which it does only to retry or
        repair a read or when an activity's next transition falls due."""
        starters = set(self.left_alone()["starters"])
        for window in windows:
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


@dataclass
class BenchPage:
    """A page one arm serves for one pass, and what its inputs make on it as the pass
    goes: the agent's thread and the page's to-do, and the serial numbers that keep
    each input's words unique."""

    served: ServedPage
    thread: str = ""
    task: str = ""
    serials: Iterator[int] = field(default_factory=lambda: itertools.count(1))

    @property
    def directory(self) -> str:
        return str(self.served.directory)

    def serial(self) -> str:
        return f"{next(self.serials):03d}"

    def leaf(self, *args: str) -> str:
        """The arm's `leaf` with `args`, refusing a failed command; its output."""
        return self.served.leaf(*args).stdout

    def delivery(self) -> dict:
        """What `leaf wait` hands the agent, unacknowledged. A delivery too long for
        one output comes in parts, whose texts join into the whole, read part by part
        as its `next` commands say; a page seeded with many events delivers them all
        with its first question."""
        part = json.loads(self.leaf("wait", self.directory))
        if "part" not in part:
            return part
        texts = [part["text"]]
        while part["next"]:
            number = str(part["part"] + 1)
            part = json.loads(
                self.leaf("delivery", "read", part["id"], "--part", number)
            )
            texts.append(part["text"])
        return json.loads("".join(texts))

    def written(self, *args: str, file: Path | None = None) -> float:
        """Run the arm's `leaf` with `args` and return when it first changed `file`,
        by default the page's log, in epoch milliseconds: the write itself, whatever
        the command spent starting up before it."""
        file = file or self.served.directory / "events.jsonl"
        command = [str(self.served.arm / "bin" / "leaf"), *args]
        before = file.stat().st_mtime_ns
        process = subprocess.Popen(
            command,
            env=environment(XDG_STATE_HOME=str(self.served.state)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        while True:
            exited = process.poll() is not None
            written = file.stat().st_mtime_ns
            if written != before or exited:
                break
            time.sleep(0.0005)
        output, _ = process.communicate()
        if process.returncode or written == before:
            raise click.ClickException(
                f"leaf {' '.join(args)} exited {process.returncode}, "
                f"{'unchanged' if written == before else 'changed'} {file.name}:\n"
                f"{output}"
            )
        return written / 1e6


@dataclass
class Tab:
    """A tab open on a bench page for one pass, the index of the input's sample in it,
    and what the input's preparation chose for the sample: its words and its target."""

    page: Page
    bench: BenchPage
    sample: int = 0
    words: str = ""
    target: dict = field(default_factory=dict)

    def quiet(self, ms: float) -> None:
        self.page.wait_for_timeout(ms)


# What an input's preparation returns: the goals a paint pass waits for, each a
# painted fact (`leaf_dev.painted`) and its argument by the reading it times.
Goals = dict[str, tuple[str, object]]


class Input(NamedTuple):
    """An input a user or agent makes on a page.

    `ready` brings the page to where the input starts, outside every window read, and
    returns the goals that mark its result painted; `act` makes the input and returns
    when it started, in epoch milliseconds, where that is an agent's write, or None
    for a gesture, whose own input event the time counts from. The CPU pass reads the
    mean of `count`, with `ready` before each where `each`, each in its own window,
    and otherwise once before a window over them all and a quiet after them; it waits
    for the input's painted goals where it has them, for the POST's answer where they
    include the server's reading of its event (`delivered`), and then `after` ms. The
    paint pass times it `count` times, each after `ready`, where it `paints`, and a
    page reads the input only where it holds `needs`. `leave` follows each `ready` once
    the windows after it end, to take back a mode `ready` entered, so the inputs after
    it meet the page as they would without it. An `agent` input is an agent's write,
    which reaches the page only in the server's reading. A `whole` input's result is
    made of the whole page, as a revision's new document or a search's count of its
    matches is, so what it costs may grow with the page (`held`)."""

    act: Callable[[Tab], float | None]
    count: int = 1
    ready: Callable[[Tab], Goals] = lambda _: {}
    leave: Callable[[Tab], None] = lambda _: None
    each: bool = True
    paints: bool = False
    after: float = 0
    needs: str = ""
    agent: bool = False
    whole: bool = False


def aim_at_option(tab: Tab) -> Goals:
    """Rest the mouse over the first option's centre, in view, since a locator's click
    first runs its actionability checks on the page's main thread."""
    option = tab.page.locator("lf-option").first
    option.scroll_into_view_if_needed()
    box = option.bounding_box()
    assert box is not None
    tab.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    tab.quiet(600)
    return {"shown": ("delivered", {"kind": "action"})}


def press(tab: Tab) -> None:
    tab.page.mouse.down()
    tab.page.mouse.up()


def enter_field(tab: Tab) -> Goals:
    tab.page.locator(".lf-fp-field").first.click()
    tab.quiet(600)
    return {}


def type_letter(tab: Tab) -> None:
    tab.page.keyboard.type("abcdefghijklmnopqrstuvwxyz"[tab.sample % 26])


def leave_field(tab: Tab) -> None:
    """Escape takes the caret out of the field and keeps its draft, the keys' words."""
    tab.page.keyboard.press("Escape")


def open_editor(tab: Tab) -> Goals:
    """Click the first draft's prose, which opens its editor with the caret there."""
    tab.page.locator("lf-draft .lf-markdown-body p").first.click()
    tab.page.locator("lf-draft .lf-draft-edit").first.wait_for()
    tab.quiet(600)
    return {}


def discard_edit(tab: Tab) -> None:
    """Escape throws the editor's words away and closes it, leaving no edit behind."""
    tab.page.keyboard.press("Escape")


def aim_at_root(tab: Tab) -> Goals:
    """Rest the mouse over the first call diff's root, whose press folds or opens it."""
    root = tab.page.locator("lf-call-diff .lf-call-group-summary").first
    root.scroll_into_view_if_needed()
    box = root.bounding_box()
    assert box is not None
    tab.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    tab.quiet(600)
    return {}


def focus_option(tab: Tab) -> Goals:
    """Focus the first option's control, from which Tab crosses the same stops at every
    size: its ask's other controls and, after a short ask, the first link or listing."""
    tab.page.locator(".lf-pick").first.focus()
    tab.quiet(600)
    return {}


def tab_step(tab: Tab) -> None:
    way = WAYS[tab.sample % len(WAYS)]
    tab.page.keyboard.press("Tab" if way > 0 else "Shift+Tab")


def walk_step(tab: Tab) -> None:
    """Step the On Me walk to the next question waiting on the user, or back, from
    where `halfway` left the reader, so every size walks the same few questions."""
    way = WAYS[tab.sample % len(WAYS)]
    tab.page.keyboard.press("m" if way > 0 else "Shift+m")


def halfway(tab: Tab) -> Goals:
    x, y = tab.page.evaluate(HALFWAY, RUN * NOTCH)
    tab.target = {"x": x, "y": y}
    tab.page.mouse.move(x, y)
    tab.quiet(600)
    return {}


def wheel_step(tab: Tab) -> None:
    tab.page.mouse.wheel(0, NOTCH * WAYS[tab.sample % len(WAYS)])


def hover_step(tab: Tab) -> None:
    """Move the pointer a LINE down or up the page's text from where `halfway` left
    it, as a reader's hand drifts over what they read."""
    lines = sum(WAYS[: tab.sample % len(WAYS) + 1])
    tab.page.mouse.move(tab.target["x"], tab.target["y"] + LINE * lines)


def hold_alt(tab: Tab) -> None:
    """Hold ⌥ down, which arms the page under the pointer, or let it up."""
    if tab.sample % 2:
        tab.page.keyboard.up("Alt")
    else:
        tab.page.keyboard.down("Alt")


def design_key(tab: Tab) -> None:
    """Enter Design mode, or leave it."""
    tab.page.keyboard.press("l")


def draw_key(tab: Tab) -> None:
    """Enter Draw mode, or leave it."""
    tab.page.keyboard.press("w")


def enter_design(tab: Tab) -> Goals:
    """Leave nothing focused, rest the pointer on the first tab control, in view, with
    its centre and the second's noted (`TAB_CENTRES`), and enter Design mode."""
    tab.page.evaluate("() => document.activeElement?.blur()")
    centres = tab.page.evaluate(TAB_CENTRES)
    tab.target = {"centres": centres}
    tab.page.mouse.move(*centres[0])
    design_key(tab)
    tab.quiet(600)
    return {}


def inspect_step(tab: Tab) -> None:
    """Move the pointer onto the other of the two tab controls, each a part Design mode
    names inside the tabs widget, as #4781's reader moved between its side tabs."""
    tab.page.mouse.move(*tab.target["centres"][(tab.sample + 1) % 2])


def open_picker(tab: Tab) -> Goals:
    """Enter Design mode as `enter_design` does, open the target picker (`s`), and stand
    its walk on the last hint in view: on `side_documents`' pages, the last tab the side
    list shows, a part Design mode names inside the tabs widget."""
    enter_design(tab)
    tab.page.keyboard.press("s")
    tab.page.keyboard.press("Shift+Tab")
    tab.quiet(600)
    return {}


def pick_step(tab: Tab) -> None:
    """Walk the picker's hints up from the last and back (`WAYS`), each step announcing
    the hint it reaches, as #4781's reader heard the side tabs."""
    way = WAYS[tab.sample % len(WAYS)]
    tab.page.keyboard.press("Shift+Tab" if way > 0 else "Tab")


def leave_picker(tab: Tab) -> None:
    """Close the target picker, then leave Design mode."""
    tab.page.keyboard.press("Escape")
    design_key(tab)


def leave_composer(tab: Tab) -> None:
    """Close the comment a press in Design mode opened, which holds no words and so
    leaves no draft, then leave Design mode."""
    tab.page.keyboard.press("Escape")
    tab.page.keyboard.press("Escape")


def open_annotations(tab: Tab) -> Goals:
    """Rest the pointer halfway down the page (`halfway`), then open the leaf's menu at
    Annotations, so the next press chooses Capture area. The page finds each row
    (`CENTRE`), as it finds everything on `side_documents`' pages."""
    halfway(tab)
    *doors, row = MENU_ROWS
    for door in doors:
        tab.page.mouse.click(*until(tab.page, CENTRE, f"{door} never showed", door))
    tab.target["row"] = until(tab.page, CENTRE, "Capture area never showed", row)
    tab.quiet(600)
    return {}


def capture_toggle(tab: Tab) -> None:
    """Choose Capture area from the menu `open_annotations` opened, or leave it."""
    if tab.sample % 2:
        tab.page.keyboard.press("Escape")
    else:
        tab.page.mouse.click(*tab.target["row"])


def aim_at_title(tab: Tab) -> Goals:
    title = tab.page.locator("h1").first
    title.scroll_into_view_if_needed()
    box = title.bounding_box()
    assert box is not None
    tab.page.mouse.move(box["x"] + 8, box["y"] + box["height"] / 2)
    tab.quiet(600)
    return {}


def triple_click(tab: Tab) -> None:
    """Select the title's line, as a user does to comment on it."""
    for clicks in (1, 2, 3):
        tab.page.mouse.down(click_count=clicks)
        tab.page.mouse.up(click_count=clicks)


def write_comment(tab: Tab, nth: int = 0) -> Goals:
    """Select the start of the `nth` passage (`PASSAGE`), open its comment and write
    it. A selection an earlier input left, such as `select`'s of the title, goes
    first, since its comment control can stand over the passage and take the drag."""
    tab.words = f"Bench comment {tab.bench.serial()}."
    tab.page.evaluate("() => getSelection().removeAllRanges()")
    until(
        tab.page,
        "() => !document.querySelector('.lf-fab-input')?.checkVisibility()",
        "the earlier selection's comment control never went",
    )
    x, y = tab.page.evaluate(PASSAGE, nth)
    tab.page.mouse.move(x + 2, y + 10)
    tab.page.mouse.down()
    tab.page.mouse.move(x + 200, y + 10, steps=8)
    tab.page.mouse.up()
    until(
        tab.page,
        "() => (CSS.highlights.get('lf-pending')?.size ?? 0) > 0",
        "the selection was never marked",
    )
    tab.page.locator(".lf-fab-input").click()
    tab.page.locator(".lf-composer leaf-text").focus()
    tab.page.keyboard.insert_text(tab.words)
    return {
        "painted": ("message", tab.words),
        "shown": ("delivered", {"kind": "comment"}),
    }


def open_draft(tab: Tab) -> Goals:
    """Open a comment on the third passage holding words that fill the box's least
    width, so each key `draft` types widens the box, as each key of a long first line
    does (placement-rules.json, `size-width`)."""
    write_comment(tab, nth=2)
    tab.page.keyboard.insert_text(" Its words fill the least width ")
    tab.quiet(600)
    return {}


def drop_draft(tab: Tab) -> None:
    """Take the draft's words out and close its box, so it leaves no draft behind."""
    tab.page.keyboard.press("ControlOrMeta+a")
    tab.page.keyboard.press("Backspace")
    tab.page.keyboard.press("Escape")


def aim_at_line(tab: Tab) -> Goals:
    """Put away the comment box an earlier sample opened, and rest the mouse over the
    comment control of one of `PATCH`'s lines, another line each sample."""
    tab.page.keyboard.press("Escape")
    until(
        tab.page,
        "() => !document.getElementById('patch').shadowRoot.querySelector('.lf-fab-bar')",
        "the diff's comment box never closed",
    )
    tab.page.mouse.move(4, 4)
    control = tab.page.locator("#patch .lf-diff-line-comment").nth(2 + 3 * tab.sample)
    control.scroll_into_view_if_needed()
    box = control.bounding_box()
    assert box is not None
    tab.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    tab.quiet(600)
    return {"painted": ("composer", "patch")}


def send(tab: Tab) -> None:
    tab.page.keyboard.press("ControlOrMeta+Enter")


def aim_at_resolve(tab: Tab) -> Goals:
    """Send a comment as `comment` does, on the next passage so that its row is its
    thread's alone, wait for the page to take in the server's reading of it, and rest
    the mouse over Resolve in its thread's card. Resolving takes the thread's row out
    of the margin, so the row's leaving marks it painted. A card an earlier input left
    open is put away first, since it can stand over the passage."""
    for _ in range(2):
        tab.page.keyboard.press("Escape")
    tab.page.mouse.move(4, 4)
    ended(tab.page)
    write_comment(tab, nth=1)
    send(tab)
    resolve = tab.page.locator(".lf-margin-preview .lf-resolve")
    resolve.wait_for(state="visible")
    ended(tab.page)
    target = until(tab.page, OPEN_ROW, "the thread's card names no row")
    box = resolve.bounding_box()
    assert box is not None
    tab.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    tab.quiet(400)
    return {
        "painted": ("rowLeft", target),
        "shown": ("delivered", {"kind": "resolve"}),
    }


def lift_card(tab: Tab) -> Goals:
    """Lift the first card that can move left (`MOVABLE`) by its grip's keys, and aim
    it at the column left of it."""
    found = tab.page.evaluate(MOVABLE)
    if found is None:
        raise click.ClickException("no card on the page has a column left of it")
    card, to = found
    tab.page.locator(f"#{card} .lf-grip").focus()
    tab.page.keyboard.press("Enter")
    tab.page.keyboard.press("ArrowLeft")
    return {
        "painted": ("card", {"card": card, "to": to}),
        "shown": ("delivered", {"kind": "action", "unit": card}),
    }


def drop_card(tab: Tab) -> None:
    tab.page.keyboard.press("Enter")


def ask_agent(tab: Tab) -> Goals:
    """The user's turn in the agent's thread, which the agent's reply answers, while
    the user follows the conversation's tail in the floating panel's view of it.

    The user asks first because the panel shows at once only news that answers the
    user's last turn; any other reply waits behind New reply (primary-reader.js,
    `answersAtOnce`). The agent answers as an agent does, through the delivery `leaf
    wait` prints. The thread is a general one, made at the first reply, and long
    enough to scroll, so the panel's pinned reply row takes each arriving turn."""
    if not tab.bench.thread:
        created = tab.bench.leaf(
            "thread",
            "create",
            "--title",
            "Bench thread",
            tab.bench.directory,
            "--text",
            THREAD_TEXT,
        )
        tab.bench.thread = json.loads(created)["id"]
        told(tab.page)
    serial = tab.bench.serial()
    question, tab.words = f"Bench question {serial}.", f"Bench reply {serial}."
    opened = "selector => document.querySelector(selector)?.checkVisibility()"
    message = f'{PANEL_THREAD}[data-lf-thread="{tab.bench.thread}"] .lf-msg'
    if not tab.page.evaluate(opened, message):
        go_to_threads(tab.page)
        tab.page.locator(f'.lf-fp-thread[data-lf-key="{tab.bench.thread}"]').click()
        until(tab.page, opened, "the agent thread never opened", message)
    # The panel's field is the open thread's reply box.
    tab.page.locator(".lf-fp-field leaf-text").focus()
    tab.page.keyboard.insert_text(question)
    tab.page.keyboard.press("ControlOrMeta+Enter")
    until(
        tab.page,
        "([selector, words]) => [...document.querySelectorAll(selector)]"
        ".some(node => node.textContent.includes(words) && node.checkVisibility())",
        "the user's turn never showed",
        [message, question],
    )
    tab.target = {
        "ref": next(
            event["answer"]["ref"]
            for batch in tab.bench.delivery()["batches"]
            for event in batch["events"]
            if event.get("text") == question
        )
    }
    ended(tab.page)
    return {"painted": ("message", tab.words)}


def agent_reply(tab: Tab) -> float:
    return tab.bench.written(
        "thread", "reply", tab.target["ref"], "--done", "--text", tab.words
    )


def name_status(tab: Tab) -> Goals:
    """The next line of the page's own to-do, made at the first status."""
    if not tab.bench.task:
        created = tab.bench.leaf(
            "task", "create", tab.bench.directory, "page", "--title", "Bench task"
        )
        tab.bench.task = json.loads(created)["id"]
        told(tab.page)
    tab.words = f"Bench status {tab.bench.serial()}"
    return {"painted": ("status", tab.words)}


def agent_status(tab: Tab) -> float:
    return tab.bench.written(
        "task", "start", tab.bench.directory, tab.bench.task, "--text", tab.words
    )


def name_revision(tab: Tab) -> Goals:
    """The paragraph the next revision adds under the page's title, and the revision
    it makes."""
    tab.words = f"Bench revision {tab.bench.serial()}."
    tab.target = {"id": f"bench-revision-{tab.words.split()[-1].rstrip('.')}"}
    revision = tab.page.evaluate("() => window.__leafBench.revision()") + 1
    return {
        "painted": (
            "revision",
            {"revision": revision, **tab.target, "words": tab.words},
        )
    }


def agent_revision(tab: Tab) -> float:
    """Write the page's source with one more paragraph under its title, as an agent
    writes the page; its server makes each valid save the next revision."""
    source = tab.bench.served.directory / "index.html"
    markup = source.read_text(encoding="utf-8")
    paragraph = f'<p id="{tab.target["id"]}">{tab.words}</p>'
    source.write_text(markup.replace("</h1>", f"</h1>{paragraph}", 1), "utf-8")
    return source.stat().st_mtime_ns / 1e6


def agent_stamp(tab: Tab) -> float:
    """The same revision, stamped as soon as it is saved, as an agent publishes a
    record's checkpoint (`leaf page stamp`). Whichever of the save and the stamp the
    tab reads first makes the revision."""
    saved = agent_revision(tab)
    tab.bench.leaf("page", "stamp", tab.bench.directory, "--text", tab.words)
    return saved


def first_line(d: int) -> str:
    """Document `d`'s first row (`side_documents`), which a tab's opening draws."""
    return f"#d{d} .lf-text-document-run > div"


def aim_at_tab(tab: Tab) -> Goals:
    """Rest the mouse over the control of the second tab at the first sample and the
    third at the next, each never opened. The page finds the control
    (`TAB_CONTROL`), as it finds everything on `side_documents`' pages, since a
    Playwright locator walks every element of a page for each query."""
    d = tab.sample + 1
    tab.page.mouse.move(*tab.page.evaluate(TAB_CONTROL, f"t{d}"))
    tab.quiet(600)
    return {"painted": ("shows", [first_line(d), ""])}


def open_tabs(tab: Tab) -> Goals:
    """Put away page search where an earlier input left it open, then open every
    closed tab in turn, as a reader looks through the documents, each once the last
    has drawn and coloured its lines in view (`COLOURED`), and ending on the last;
    then rest the mouse over its listing halfway down (`halfway`), and read how tall
    a run of its lines stands (`RUN_HEIGHT`), which a step scrolls."""
    if tab.page.evaluate("() => window.__leafBench.met('searching')"):
        tab.page.keyboard.press("Escape")
    count = tab.page.evaluate(
        "() => document.querySelectorAll('#docs [role=tab]').length"
    )
    for d in range(1, count):
        tab.page.mouse.click(*tab.page.evaluate(TAB_CONTROL, f"t{d}"))
        until(tab.page, COLOURED, "an opened tab's lines were never coloured", d)
    ended(tab.page)
    halfway(tab)
    tab.target["run"] = tab.page.evaluate(
        RUN_HEIGHT, [tab.target["x"], tab.target["y"]]
    )
    return {}


def run_step(tab: Tab) -> None:
    """Turn the wheel a run's height down or up the listing, so each step draws and
    colours a run its last didn't."""
    tab.page.mouse.wheel(0, tab.target["run"] * WAYS[tab.sample % len(WAYS)])


def name_change(tab: Tab) -> Goals:
    """The first line of the document shown, which the agent's next write changes,
    and the file the write reads its source's new value from."""
    d = tab.page.evaluate(SHOWN_DOCUMENT)
    tab.words = f"# Bench change {tab.bench.serial()}"
    value = tab.bench.served.directory.parent / f"s{d}.json"
    value.write_text(json.dumps(document_text(d, tab.words)), encoding="utf-8")
    tab.target = {"source": f"s{d}", "value": str(value)}
    return {"painted": ("shows", [first_line(d), tab.words])}


def agent_data(tab: Tab) -> float:
    """Set the shown document's source to its text with the first line changed
    (`leaf data set`), as an agent rewrites a file a page shows."""
    source = tab.target["source"]
    return tab.bench.written(
        "data", "set", tab.bench.directory, source, "--file", tab.target["value"],
        file=PUBLICATION.file(source_file(tab.bench.served.directory, source)),
    )  # fmt: skip


def aim_at_search(tab: Tab) -> Goals:
    """Leave nothing focused, so `/` opens page search."""
    tab.page.evaluate("() => document.activeElement?.blur()")
    tab.quiet(400)
    return {"painted": ("searching", None)}


def open_search(tab: Tab) -> None:
    tab.page.keyboard.press("/")


def empty_search(tab: Tab) -> Goals:
    """Open page search where it isn't open, and empty its field."""
    if not tab.page.evaluate("() => window.__leafBench.met('searching')"):
        aim_at_search(tab)
        open_search(tab)
        until(
            tab.page, "() => window.__leafBench.met('searching')", "search never opened"
        )
    tab.page.keyboard.press("ControlOrMeta+a")
    tab.page.keyboard.press("Backspace")
    tab.quiet(600)
    return {"painted": ("searched", WORD)}


def search_word(tab: Tab) -> None:
    tab.page.keyboard.insert_text(WORD)


# Every input, in the order a pass takes them. Those that open the panel's views or
# add threads and to-dos to the page come after those on the page's own content, and
# a selection after any revision, which the runtime holds back while the user's
# selection stands beside what it changes. Design mode, Draw mode and Capture area are
# each entered and left with the pointer resting on the page's content, or on the
# menu row that chose the area, before any input adds a mark or opens a tab. Those
# that open tabs come after every input on the document first shown, and a search
# before `browse`, since each tab `browse` opens keeps its colour, which every later
# input would meet.
INPUTS: dict[str, Input] = {
    "click": Input(
        press,
        4,
        aim_at_option,
        each=False,
        paints=True,
        after=400,
        needs="lf-option",
    ),
    "key": Input(type_letter, 20, enter_field, each=False, after=60),
    "leave": Input(leave_field, 4, enter_field, after=200),
    "edit": Input(
        type_letter,
        20,
        open_editor,
        leave=discard_edit,
        each=False,
        after=60,
        needs="lf-draft",
    ),
    "tab": Input(tab_step, 16, focus_option, each=False, after=100, needs="lf-option"),
    "walk": Input(walk_step, 8, halfway, each=False, after=300, needs="lf-option"),
    "scroll": Input(wheel_step, 32, halfway, each=False, after=50),
    "hover": Input(hover_step, 32, halfway, each=False, after=50),
    "aim": Input(hold_alt, 8, halfway, each=False, after=100),
    "design": Input(design_key, 2, halfway, each=False, after=400),
    "inspect": Input(
        inspect_step,
        16,
        enter_design,
        leave=design_key,
        each=False,
        after=50,
        needs="[role=tab]",
    ),
    "pick": Input(
        pick_step,
        16,
        open_picker,
        leave=leave_picker,
        each=False,
        after=100,
        needs="[role=tab]",
    ),
    "part": Input(
        press, 4, enter_design, leave=leave_composer, after=400, needs="[role=tab]"
    ),
    "draw": Input(draw_key, 2, halfway, each=False, after=400),
    "capture": Input(capture_toggle, 2, open_annotations, each=False, after=400),
    "data": Input(
        agent_data,
        2,
        name_change,
        paints=True,
        after=600,
        needs=DOCUMENTS,
        agent=True,
    ),
    "revision": Input(
        agent_revision,
        2,
        name_revision,
        paints=True,
        after=600,
        needs="h1",
        agent=True,
        whole=True,
    ),
    "stamp": Input(
        agent_stamp,
        ready=name_revision,
        paints=True,
        after=600,
        needs="h1",
        agent=True,
        whole=True,
    ),
    "select": Input(triple_click, 4, aim_at_title, each=False, after=400, needs="h1"),
    "draft": Input(
        type_letter, 20, open_draft, leave=drop_draft, each=False, after=60, needs="h1"
    ),
    "open": Input(press, 4, aim_at_line, paints=True, after=400, needs="#patch"),
    "fold": Input(press, 4, aim_at_root, each=False, after=100, needs="lf-call-diff"),
    "comment": Input(send, ready=write_comment, paints=True, after=400, needs="h1"),
    "resolve": Input(press, ready=aim_at_resolve, paints=True, after=400, needs="h1"),
    "move": Input(drop_card, ready=lift_card, paints=True, after=400, needs="lf-card"),
    "reply": Input(agent_reply, ready=ask_agent, paints=True, after=300, agent=True),
    "status": Input(
        agent_status, ready=name_status, paints=True, after=300, agent=True
    ),
    "reveal": Input(press, 2, aim_at_tab, paints=True, after=600, needs=DOCUMENTS),
    "search": Input(
        open_search, ready=aim_at_search, after=400, needs="lf-text-document"
    ),
    "matches": Input(
        search_word,
        ready=empty_search,
        after=400,
        needs="lf-text-document",
        whole=True,
    ),
    "browse": Input(run_step, 16, open_tabs, each=False, after=300, needs=DOCUMENTS),
}


def until(page: Page, script: str, what: str, arg=None):
    """Poll a page reading until it is truthy, across a reload that may interrupt it."""
    deadline = time.monotonic() + DEADLINE_MS / 1000
    failure = None
    while True:
        try:
            if value := page.evaluate(script, arg):
                return value
        except PlaywrightError as error:
            failure = error  # Usually the document was replaced mid-read.
        if time.monotonic() > deadline:
            last = f" (last read failed: {failure.message})" if failure else ""
            raise click.ClickException(f"{page.url}: {what} within the deadline{last}")
        time.sleep(0.02)


def ended(page: Page) -> None:
    """Wait until the page is ready, as every reader outside it waits
    (`wait_until_ready`), then until every trip its ledger counts has ended and they
    have stayed ended for SETTLE_MS."""
    wait_until_ready(page)
    deadline = time.monotonic() + DEADLINE_MS / 1000
    while time.monotonic() < deadline:
        until(page, TRIPS_ENDED, "the page's trips never ended")
        time.sleep(SETTLE_MS / 1000)
        if page.evaluate(TRIPS_ENDED):
            return
    raise click.ClickException(f"{page.url}: the page's trips never stayed ended")


def told(page: Page) -> None:
    """Wait until the page has taken in what its server now holds, as after an
    agent's command that made the thread or to-do an input then uses, so that taking
    it in falls outside the input's window."""
    origin = urlsplit(page.url)
    state = page.request.get(f"{origin.scheme}://{origin.netloc}/api/state")
    wait_until_ready(page, state.json(), through="state")
    ended(page)


def holds(tab: Tab, name: str) -> bool:
    """Whether the page holds what input `name` needs, asked of the document itself,
    since a Playwright locator walks every element of a large page for each query."""
    needs = INPUTS[name].needs
    return not needs or tab.page.evaluate("(s) => !!document.querySelector(s)", needs)


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

    The spins cost the page CPU, so `cpu_pass` confirms the process (`confirm`) between
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
    """What profiles the next span named `name` into `directory` (`cpu_profile`) for
    the life of a block, each span to a file of its own (`name-1.cpuprofile`, ...),
    or nothing where there is no directory."""
    if directory is None:
        return lambda _: nullcontext()
    spans = Counter()

    def profiled(name: str):
        spans[name] += 1
        return cpu_profile(page, directory / f"{name}-{spans[name]}.cpuprofile")

    return profiled


def cpu_pass(
    browser, bench: BenchPage, inputs: Sequence[str], profiles: Path | None
) -> tuple[int, dict[str, float], list[str]]:
    """The page's main-thread CPU for its load and each of `inputs`, each read over the
    span a profile into `profiles` covers, with the elements the loaded page holds and
    the inputs it lacks."""
    engine = browser.browser_type.name
    with tab(browser) as page, main_thread_clock(engine, page) as clock:
        page.set_default_timeout(DEADLINE_MS)
        profiled = profiling(page, profiles)
        current = Tab(page, bench)

        def timed(name: str, act) -> tuple[float, float]:
            """`act`'s main-thread CPU and elapsed time, in ms."""
            with profiled(name):
                start, began = clock(), time.monotonic()
                act()
                return clock() - start, (time.monotonic() - began) * 1000

        def idle_rate() -> float:
            """Wait for two quiet half seconds in a row, or QUIET_TRIES, and return
            the page's CPU per ms over the last two: what it spends with no input
            once the work a load leaves behind has run, such as the view checks the
            runtime reads after the page settles, which walk what the page draws."""
            spent: list[float] = []
            while len(spent) < 2 or (
                max(spent[-2:]) >= QUIET_MS and len(spent) < QUIET_TRIES
            ):
                start = clock()
                current.quiet(500)
                spent.append(clock() - start)
            return sum(spent[-2:]) / 1000

        # The event answers are read off resource timing, whose buffer holds 250
        # entries by default, and the runtime's own modules fill it before any click.
        page.add_init_script("performance.setResourceTimingBufferSize(100_000)")
        page.add_init_script(path=PAINTED)
        idle = 0.0

        def loaded() -> None:
            nonlocal idle
            load(page, bench.served.address)
            idle = idle_rate()

        readings = {"load cpu": timed("load", loaded)[0]}
        if isinstance(clock, ContentClock):
            clock.confirm()
        elements = page.evaluate("document.querySelectorAll('*').length")
        missing = []
        for name in inputs:
            if holds(current, name):
                readings |= per_input(current, name, timed, idle)
            else:
                missing.append(name)
    return elements, readings, missing


def per_input(tab: Tab, name: str, timed, idle: float) -> dict[str, float]:
    """Input `name`'s mean CPU over its count, less the page's idle CPU over the time
    read (`Input`), and where it posts, the median time the server took to start
    answering and the answers' size. A short window meets fewer of the page's own
    periodic tasks, which the idle rate leaves out."""
    each, page = INPUTS[name], tab.page
    goals: Goals = {}

    def one() -> None:
        if any(fact == "delivered" for fact, _ in goals.values()):
            with page.expect_response(lambda r: r.url.endswith("/api/event")):
                each.act(tab)
        else:
            each.act(tab)
        for fact, arg in goals.values():
            if fact != "delivered":
                page.wait_for_function(
                    "([fact, arg]) => window.__leafBench.met(fact, arg)",
                    arg=[fact, arg],
                )
        tab.quiet(each.after)
        tab.sample += 1

    def run(samples: int, after: float) -> None:
        for _ in range(samples):
            one()
        tab.quiet(after)

    tab.sample = 0
    if not each.each:
        goals = each.ready(tab)
    spent, posts = 0.0, []
    for samples, after in [(1, 0)] * each.count if each.each else [(each.count, 600)]:
        if each.each:
            goals = each.ready(tab)
        posted = len(page.evaluate(EVENT_POSTS))
        cpu, elapsed = timed(name, partial(run, samples, after))
        spent += cpu - idle * elapsed
        posts += page.evaluate(EVENT_POSTS)[posted:]
        if each.each:
            each.leave(tab)
    if not each.each:
        each.leave(tab)
    readings = {f"{name} cpu": spent / each.count}
    if posts:
        readings[f"{name} event"] = statistics.median(post["ms"] for post in posts)
        readings[f"{name} event KB"] = statistics.median(post["kb"] for post in posts)
    return readings


def paint_pass(
    browser,
    bench: BenchPage,
    traffic: Traffic,
    inputs: Sequence[str],
    profiles: Path | None,
) -> tuple[list[dict], list[str]]:
    """Each of `inputs` that `paints`, timed `count` times to each goal's first
    painted frame (`measure`), each a window of `Traffic`'s, profiled into `profiles`
    where given, and the inputs the page lacks."""
    with tab(browser) as page:
        page.set_default_timeout(DEADLINE_MS)
        page.context.add_init_script(path=MAIN_THREAD)
        page.context.add_init_script(path=PAINTED)
        # The browser's own account of each request, in every frame of the tab, with
        # the code that started it.
        network = page.context.new_cdp_session(page)
        network.on("Network.requestWillBeSent", traffic.started)
        network.on("Network.loadingFinished", traffic.ended)
        network.on("Network.loadingFailed", traffic.ended)
        network.send("Network.enable")
        load(page, bench.served.address)
        ended(page)
        traffic.alone()
        current = Tab(page, bench)
        windows, missing = [], []
        for name in inputs:
            each = INPUTS[name]
            if not each.paints:
                continue
            if not holds(current, name):
                missing.append(name)
                continue
            for sample in range(each.count):
                current.sample = sample
                goals = each.ready(current)
                windows.append(measure(current, traffic, name, goals, profiles))
                each.leave(current)
        # Playwright delivers the browser's reports only while it talks to the page.
        page.evaluate("0")
    return windows, missing


def measure(
    tab: Tab, traffic: Traffic, name: str, goals: Goals, profiles: Path | None
) -> dict:
    """Arm the frame sampler for `goals`, make input `name`, and read when the frame
    that first painted each goal was laid out, the long frames up to the last, and the
    trips the input caused."""
    page = tab.page
    page.evaluate(
        "goals => window.__leafBench.arm(goals)",
        [
            {"name": goal, "fact": fact, "arg": arg}
            for goal, (fact, arg) in goals.items()
        ],
    )
    try:
        with traced(page, profiles, name) if profiles else nullcontext() as recorded:
            # On the clock the browser reports requests by, and before a command's
            # startup, whose requests it can cause before its write.
            opened = time.time() * 1000
            start = INPUTS[name].act(tab) or until(
                page, "() => window.__leafBench.input()", "no input seen"
            )
            watch = until(
                page,
                "() => { const w = window.__leafBench.watch();"
                " return w.goals.every(g => g.at !== null) && w; }",
                f"{name} was never shown",
            )
        ended(page)
        trips = page.evaluate("() => window.__leafBench.traffic()")
        frames = page.evaluate("() => window.__leafBench.frames()")
    finally:
        page.evaluate("() => window.__leafBench.disarm()")
    end = max(goal["at"] for goal in watch["goals"])
    # The gesture's own POST: the attempt the probe bound its `delivered` goal to.
    answered = next(
        (
            at
            for goal in watch["goals"]
            if goal.get("attempt") and (at := traffic.answered(goal["attempt"]))
        ),
        None,
    )
    return {
        "input": name,
        "start": start,
        "opened": opened,
        "closed": time.time() * 1000,
        **{goal["name"]: goal["at"] - start for goal in watch["goals"]},
        **({"answered": answered - start} if answered else {}),
        **main_thread(frames, start, end),
        **trips,
        **(
            {"profiled": attribute(*recorded, start, watch["goals"])}
            if recorded
            else {}
        ),
    }


@contextmanager
def traced(page: Page, directory: Path, name: str):
    """Trace and profile `page` into `directory` for the life of the block, and yield a
    list that then holds the trace's path and the CPU profile."""
    run = len(list(directory.glob(f"paint-{name}-*.trace.json"))) + 1
    trace = directory / f"paint-{name}-{run}.trace.json"
    profile = directory / f"paint-{name}-{run}.cpuprofile"
    browser = page.context.browser
    assert browser is not None
    recorded = []
    # The trace starts first: a profile started before it can hold no samples in the
    # window the trace's marks bound.
    browser.start_tracing(page=page, path=str(trace), categories=CATEGORIES)
    try:
        with cpu_profile(page, profile):
            yield recorded
    finally:
        browser.stop_tracing()
    recorded.extend((trace, Profile(profile)))


def milliseconds(us: float) -> float:
    return round(us / 1000, 1)


def stack_label(frames: list, depth: int = 3) -> str:
    return " < ".join(
        f"{f.get('functionName') or '(anon)'}:{f.get('lineNumber')}"
        for f in frames[:depth]
    )


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
    """What the main thread did in a paint window: from the input's start, `began` in
    epoch milliseconds, to the frame the probe marked as painting its last goal."""
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
    """Where each profiled paint window's time went, run by run and then per run."""
    for number, run in enumerate(runs, 1):
        painted = ", ".join(
            f"{name} {milliseconds(at)}" for name, at in run["marks"].items()
        )
        click.echo(f"run {number}: ms from input to each painted goal: {painted}")
        for at, duration, paths in run["tasks"]:
            click.echo(
                f"  {milliseconds(at):7.1f} ms  task {milliseconds(duration):6.1f} ms"
                f"  {' | '.join(paths)}"
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
            f"    {per_run(runs, spent):6.1f}  {recalcs[(where, count)]:4}"
            f"  {count or '?':>5}  {where}"
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


def owners(windows: list[dict]) -> list[str]:
    """The owners of the main thread's long frames, by mean script time per window."""
    spent: dict[str, list[float]] = {}
    for window in windows:
        for owner, (ms, forced) in window["owners"].items():
            each = spent.setdefault(owner, [0.0, 0.0])
            each[0] += ms
            each[1] += forced
    ranked = sorted(spent.items(), key=lambda item: -item[1][0])
    render = sum(w["render"] for w in windows) / len(windows)
    return [
        f"    {ms / len(windows):6.0f} {forced / len(windows):6.0f}  {owner}"
        for owner, (ms, forced) in ranked[:OWNERS]
    ] + [f"    {render:6.0f}         style, layout and paint after scripts"]


def held(reading: str, readings: Container[str]) -> bool:
    """Whether `reading`, one of a page's `readings`, is one root `AGENTS.md`,
    "Responsiveness", holds to what its input changes and what the window shows, so
    that it doesn't grow with the page: the requests and bytes an input causes, and
    the main-thread CPU of one the browser answers alone. An input that posted events
    on the page, which its `event` reading shows, or an agent's write, brings the
    server's reading of the page, and applying that may grow as computing it may. A
    `whole` input's result is made of the page, so any of its readings may grow. A
    reading names its input first, as `click event KB` does, the size of the answer
    to the click's POST."""
    words = reading.split()
    name, measure = words[0], words[-1]
    each = INPUTS.get(name)
    if each is None or each.whole:
        return False
    if measure in COUNT_FLOORS:
        return True
    return measure == "cpu" and not each.agent and f"{name} event" not in readings


def limit(reading: str, readings: Container[str]) -> float:
    """The exponent above which `reading`, one of a page's `readings`, grows faster
    than root `AGENTS.md`, "Responsiveness", allows."""
    return GROWING if held(reading, readings) else SUPERLINEAR


def floor(reading: str, base: dict[str, float], readings: Container[str]) -> float:
    """`reading`'s noise floor (`exponent`), from `base`, the BASE page's readings of
    the same run: a share of its own for a held one, at least one of a count, a fixed
    floor for any other size or count, and a share of the load's CPU for a time.
    Without the load's CPU, a time has no floor, and so no exponent."""
    measure = reading.rsplit(" ", 1)[-1]
    if held(reading, readings):
        own = HELD_FLOOR_SHARE * base[reading]
        return max(own, 1) if measure in COUNT_FLOORS else own
    if measure in COUNT_FLOORS:
        return COUNT_FLOORS[measure]
    share = FLOOR_SHARES["cpu" if measure == "cpu" else "elapsed"]
    return share * base["load cpu"] if "load cpu" in base else math.inf


def exponent(
    sizes: list[int], costs: list[float], floor: float, fitted: int = FITTED
) -> float | None:
    """The least-squares slope of log growth on log size over the `fitted` largest
    sizes, where a cost's growth is what it adds to its cost at the first size,
    BASE. A size whose growth is under `floor` is left out, its growth the host's
    noise, and so is one that didn't grow, which a held reading's floor lets through
    where the input cost nothing on the BASE page. With fewer than all but one of the
    fitted sizes left, or fewer than two, there is no exponent: the two largest of
    four server sizes stand 1.56 apart, and a slope across them reads a loaded host's
    noise as growth."""
    fixed = costs[0]
    pairs = [
        (math.log(n), math.log(c - fixed))
        for n, c in list(zip(sizes, costs, strict=True))[-fitted:]
        if c - fixed >= floor and c > fixed
    ]
    if len(pairs) < max(2, fitted - 1):
        return None
    return statistics.linear_regression(*zip(*pairs, strict=True)).slope


def interleaved[K](rounds: int, keys: Sequence[K]) -> Iterator[tuple[int, K]]:
    """Each round's number and each of `keys` once in it, for `rounds` rounds, the
    keys in order and then reversed in alternate rounds. A burst of load on the host
    lands on one reading of each key rather than on every reading of one, and no
    key always follows the same one, whose leftovers it would meet."""
    for number in range(rounds):
        for key in keys[:: 1 if number % 2 == 0 else -1]:
            yield number, key


def lowest[K: Hashable](readings: Iterable[tuple[K, dict[str, float]]]):
    """Each key's lowest reading of each cost, from `readings`, the rounds' readings
    by key. A busy host adds time to a reading and never takes it away, so the lowest
    is the nearest the host lets a reading come to the work alone."""
    least: dict[K, dict[str, float]] = {}
    for key, taken in readings:
        kept = least.setdefault(key, {})
        for cost, value in taken.items():
            kept[cost] = min(kept.get(cost, math.inf), value)
    return least


def label(reading: str) -> str:
    return (
        reading
        if reading.endswith(("KB", "requests", "elements", "events"))
        else f"{reading} ms"
    )


def table(
    title: str,
    columns: list[tuple[str, dict[str, float]]],
    readings: Sequence[str],
    fits: Sequence[tuple[str, dict[str, float | None], Container[str]]],
) -> str:
    """Each of `readings` a line under its label, with its value in each of `columns`,
    then its exponent in each of `fits`, marked `!` above its `limit` among the
    readings that fit's arm read."""
    width = max((len(label(reading)) for reading in readings), default=0) + 1
    lines = [
        title,
        " " * width + "".join(f"{head:>11}" for head, *_ in [*columns, *fits]),
    ]
    for reading in readings:
        cells = [
            f"{values[reading]:>11.1f}" if reading in values else f"{'-':>11}"
            for _, values in columns
        ]
        for _, slopes, read in fits:
            slope = slopes.get(reading)
            mark = "!" if slope is not None and slope > limit(reading, read) else " "
            cells.append(f"{'-' if slope is None else f'{slope:.2f}':>10}{mark}")
        lines.append(f"{label(reading):<{width}}" + "".join(cells))
    return "\n".join(lines)


def growth(
    before: dict[str, float], after: dict[str, float], ratio: float, bound: float
) -> list[str]:
    """The functions whose inclusive ms grew with an exponent above `bound` from
    `before` to `after`, profiles of the smallest and largest page, whose sizes stand
    at `ratio`."""
    grown = []
    for name, ms in after.items():
        if ms < GROWTH_FLOOR_MS or name.startswith(("(root)", "(program)", "(idle)")):
            continue
        was = before.get(name, 0)
        slope = math.log(ms / was) / math.log(ratio) if was else math.inf
        if slope > bound:
            grown.append((ms, was, slope, name))
    return [
        f"  {was:8.0f} -> {ms:8.0f} ms  exponent {slope:5.2f}  {name}"
        for ms, was, slope, name in sorted(grown, reverse=True)[:12]
    ]


def report_growth(
    title: str, profiles: dict, ratio: float, readings: Container[str] = ()
) -> None:
    """Echo the functions that grew past the `limit` of what was profiled in each of
    `profiles`, a pair of inclusive ms by function (smallest page, largest) by what
    was profiled, on a page of `readings`."""
    for name, (before, after) in profiles.items():
        bound = limit(f"{name} cpu", readings)
        if lines := growth(before, after, ratio, bound):
            click.echo(f"{title} {name}: functions growing with exponent over {bound}")
            click.echo("\n".join(lines) + "\n")


def inclusive_ms(directory: Path, name: str) -> dict[str, float]:
    """Each function's inclusive ms over every span of `name` profiled into
    `directory` (`profiling`)."""
    _own, inclusive = Profile(
        *sorted(directory.glob(f"{name}-*.cpuprofile"))
    ).functions()
    return {function: us / 1000 for function, us in inclusive.items()}


@dataclass
class Record:
    """One round's readings of one page at one size from one arm, with the elements
    the loaded page held, the inputs it lacked, and the paint pass's windows and what
    the page started while left alone."""

    page: str
    size: int | None
    arm: str
    round: int
    engine: str
    elements: int = 0
    readings: dict[str, float] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    windows: list[dict] = field(default_factory=list)
    alone: dict = field(default_factory=dict)


@contextmanager
def serving(name: str, n: int | None, arm_dir: Path, scratch: Path):
    """Serve page `name` from `arm_dir`, built under `scratch`, and yield it. A
    generated page of size `n` is written as an authored source with its earlier
    versions where its collection keeps them, and its log admitted after its own
    history (`serving_source`)."""
    seed = None
    if n is None:
        source = named_source(name)
    else:
        *earlier, authored = COLLECTIONS[name].sources(n)
        source = scratch / "source" / "page.html"
        (source.parent / "versions").mkdir(parents=True)
        source.write_text(authored)
        for version, markup in enumerate(earlier, 1):
            (source.parent / "versions" / f"page.v{version}.html").write_text(markup)
        if values := COLLECTIONS[name].data(n):
            data_file(source).write_text(json.dumps(values))
        if events := COLLECTIONS[name].log(n):
            # Not the source's stem, which would make it the page's own history.
            seed = scratch / "seed.jsonl"
            seed.write_text("".join(json.dumps(event) + "\n" for event in events))
    with serving_source(arm_dir, source, scratch / "page", seed):
        yield BenchPage(served_page.get())


def measure_page(
    browser,
    arms: dict[str, Arm],
    name: str,
    sizes: list[int],
    inputs: Sequence[str],
    reads: set[str],
    rounds: int,
    run: Path,
    profile: bool,
) -> list[Record]:
    """Every round's record of page `name` at each of `sizes`, or once for an authored
    page, from each arm. Each pass of each round reads a page of its own, built afresh
    under `run`, so no input meets what another pass or round made on it. The paint
    pass's windows become readings once every round's traffic is in (`Traffic.split`).
    With `profile`, the first round profiles the CPU pass at the smallest and the
    largest size and the paint pass at the largest, so where there are more rounds,
    the lowest reading is one the profiler didn't slow."""
    sized: list[int | None] = (
        [*sorted({BASE, *sizes})] if name in COLLECTIONS else [None]
    )
    keys = [(n, arm) for n in sized for arm in arms]
    traffic = {key: Traffic() for key in keys}
    records = []
    for number, (n, arm) in interleaved(rounds, keys):
        record = Record(name, n, arm, number, browser.browser_type.name)
        page_dir = run / f"{name}-{arm}-{n}"
        profiles = page_dir if profile and number == 0 else None
        build = partial(serving, name, n, arms[arm].directory)
        if "cpu" in reads:
            ends = n in (sized[0], sized[-1])
            with build(page_dir / f"cpu-{number}") as bench:
                record.elements, record.readings, record.missing = cpu_pass(
                    browser, bench, inputs, profiles if ends else None
                )
        if "paint" in reads:
            last = n == sized[-1]
            with build(page_dir / f"paint-{number}") as bench:
                record.windows, missing = paint_pass(
                    browser, bench, traffic[n, arm], inputs, profiles if last else None
                )
            record.missing = list(dict.fromkeys([*record.missing, *missing]))
        records.append(record)
    for (n, arm), seen in traffic.items() if "paint" in reads else ():
        own = [r for r in records if (r.size, r.arm) == (n, arm)]
        seen.split([window for r in own for window in r.windows])
        for record in own:
            record.alone = seen.left_alone()
            for name in dict.fromkeys(window["input"] for window in record.windows):
                taken = [w for w in record.windows if w["input"] == name]
                for measure in ("painted", "answered", "shown", "requests"):
                    if values := [w[measure] for w in taken if measure in w]:
                        record.readings[f"{name} {measure}"] = statistics.median(values)
                kb = statistics.median(w["bytes"] for w in taken) / 1000
                record.readings[f"{name} KB"] = kb
    return records


def report(records: list[Record], arms: dict[str, Arm], run: Path, profile: bool):
    """Echo one page's table, each reading's lowest over the rounds by size and arm,
    with each arm's exponents where there are sizes to fit, then what the readings
    leave out, and with `profile` where the time went."""
    name, engine = records[0].page, records[0].engine
    sizes = sorted({r.size for r in records}, key=lambda n: n or 0)
    least = lowest(((r.size, r.arm), r.readings) for r in records)
    for r in records:
        least[r.size, r.arm]["elements"] = r.elements
    readings = list(dict.fromkeys(r for values in least.values() for r in values))
    readings.sort(key=lambda reading: reading != "elements")
    if not any(r.elements for r in records):
        readings.remove("elements")
    columns = [
        (
            " ".join(str(part) for part in (n, len(arms) > 1 and arm) if part) or arm,
            least[n, arm],
        )
        for n in sizes
        for arm in arms
    ]
    # Each arm's readings at any size, which decide what its limits are (`held`).
    seen = {arm: {r for n in sizes for r in least[n, arm]} for arm in arms}
    fits = [
        (
            "exponent" if len(arms) == 1 else f"{arm} exp",
            {
                reading: exponent(
                    [n or 0 for n in sizes],
                    [least[n, arm][reading] for n in sizes],
                    floor(reading, least[sizes[0], arm], seen[arm]),
                )
                for reading in readings
                if reading != "elements"
                and all(reading in least[n, arm] for n in sizes)
            },
            seen[arm],
        )
        for arm in arms
        if len(sizes) > 2
    ]
    rounds = 1 + max(r.round for r in records)
    title = f"{name} ({engine}), lowest of {rounds} rounds"
    click.echo(table(title, columns, readings, fits))
    if missing := sorted({m for r in records for m in r.missing}):
        click.echo(
            f"  missing, with nothing on the page they need: {', '.join(missing)}"
        )
    for arm in arms:
        if over := [
            f"{reading.split()[0]} {value:.0f}"
            for reading, value in least[sizes[-1], arm].items()
            if reading.endswith(" shown") and value > BUDGET_MS
        ]:
            click.echo(
                f"  {arm} shows the server's reading in over {BUDGET_MS} ms at "
                f"{sizes[-1] or name}: {', '.join(over)}"
            )
    painted = list(dict.fromkeys(w["input"] for r in records for w in r.windows))
    for each in painted:
        taken = [w for r in records for w in r.windows if w["input"] == each]
        if reloads := sum(w["install"] == "reload" for w in taken):
            click.echo(
                f"  {each} reloaded the page in {reloads} of {len(taken)} windows"
            )
    if painted:
        click.echo("  requests the page started on its own, per second left alone:")
        for r in records:
            if r.round == 0:
                click.echo(
                    f"    {r.size or name} {r.arm}: {r.alone['requests']:.1f} "
                    f"requests, {r.alone['bytes'] / 1000:.1f} KB"
                )
        click.echo(
            "  main thread in long frames to the last painted goal at the largest "
            "size, mean ms per window:\n    script forced  owner"
        )
    for each in painted:
        for arm in arms:
            taken = [
                w
                for r in records
                if (r.size, r.arm) == (sizes[-1], arm)
                for w in r.windows
                if w["input"] == each
            ]
            if any(w["owners"] or w["render"] for w in taken):
                click.echo(f"  {each} {arm}\n" + "\n".join(owners(taken)))
    click.echo()
    if not profile:
        return
    if len(sizes) > 1:
        timed = ["load", *(r.split()[0] for r in readings if r.endswith(" cpu"))]
        for arm in arms:
            ends = [run / f"{name}-{arm}-{n}" for n in (sizes[0], sizes[-1])]
            report_growth(
                f"{name} ({arm})",
                {
                    each: tuple(inclusive_ms(end, each) for end in ends)
                    for each in timed
                },
                (sizes[-1] or 1) / (sizes[0] or 1),
                seen[arm],
            )
    for each in painted:
        by_arm = {
            arm: [
                w["profiled"]
                for r in records
                if r.arm == arm
                for w in r.windows
                if w["input"] == each and "profiled" in w
            ]
            for arm in arms
        }
        for arm, runs in by_arm.items():
            click.echo(f"\n=== {name} {each} {arm} ===")
            show_profile(runs)
        show_marks(by_arm)


# The `server` read times the server's paths on the generated pages, in this process:
# `server_pages` makes one collection's page (`COLLECTIONS`) at each size in a scratch
# directory, with its versions activated in turn and then its log, and
# `measure_server` reads the CPU each path takes on each page, least of
# `SERVER_ROUNDS`:
#
# - `state`: the served state a page server answers each read with
#   (`PageStateService.page_state`), read after an append has changed the log, or
#   with nothing changed on a page with no log;
# - `append`: admitting one more event like the log's last, where it has one, in the
#   transaction every writer takes (`event_contracts.append_admitted`);
# - `delivery`: what `leaf wait` hands the agent of everything no receipt has passed,
#   captured, frozen and read (`delivery.batch_data`);
# - `agent`: `leaf page state` for the page;
# - `thread`: `leaf page state` for the log's first thread, where it has one;
# - `activate`: making a changed source the next revision (`activate_source`).
#
# It runs this checkout's `leaf`, with `XDG_STATE_HOME` in the scratch directory for
# the duration. A page server keeps a page's readings between
# requests (`page_memory`), and so does this process, so each path is timed as a
# server takes it again, with the readings of what didn't change kept. A `leaf`
# command starts with none kept, so `agent`, `thread` and a hook's `delivery` cost a
# command more than these, by the page's parse and the imports.
SERVER_PATHS = ("state", "append", "delivery", "agent", "thread", "activate")
# A click's paths: admitting its event and computing the reading the server answers
# with. Root `AGENTS.md`, "Responsiveness", puts that reading on screen within
# `BUDGET_MS`, so the two together take no more at `REFERENCE` (`over_budget`); it
# holds the agent's paths only to growing no faster than the page. Admission reads
# the page as a reading does, so on the `events` page both may grow with the log.
CLICK = ("append", "state")
SERVER_ROUNDS = 3
# How many of the largest sizes an exponent is fitted over: 256 to 1,600, a ratio of
# 6.25. Over three, a ratio of 3.1, a host at load 50 fitted linear costs past 1.5.
SERVER_FITTED = 4


def server_floors(rows: list[dict]) -> dict[str, float]:
    """Each path's noise floor (`exponent`) in `rows`, one run's readings by
    size from BASE: the path's own reading on the BASE page, a reading of the same run,
    as the browser's floors are shares of its load (`floor`). A path's own
    fixed cost sets the floor, so a cheap path's growth isn't judged against a dearer
    one's fixed work."""
    return {path: rows[0][path] for path in SERVER_PATHS if path in rows[0]}


def server_pages(
    collection: Collection, sizes: list[int], directory: Path
) -> dict[int, Path]:
    """Make `collection`'s page at each of `sizes` under `directory`: each version
    activated in turn, then its sources' values, then the log. Where a page's versions
    begin with a smaller page's, they are activated once, on a page each size copies
    before its values and log are written, so the pages of every size together
    activate each version once."""
    from leaf.pages.vendoring import cmd_init
    from leaf.records.page_data import cmd_data_set
    from leaf.records.revisioning import activate_source
    from leaf_dev.page_fixtures import DEFAULT_PACKAGES

    # The packages the browser's bench builds the same pages with
    # (`page_fixtures.source_packages`), so a collection may use any of their widgets.
    packages = tuple(json.loads(DEFAULT_PACKAGES.read_text(encoding="utf-8")))

    pages = {}
    versions, built = directory, []
    for n in sorted(sizes):
        sources = collection.sources(n)
        if not built or sources[: len(built)] != built:
            versions, built = directory / f"{n}-versions", []
            versions.mkdir(parents=True)
        for source in sources[len(built) :]:
            (versions / "index.html").write_text(source)
            if not built:
                cmd_init(versions, packages)
            activation = activate_source(versions)
            assert activation.error is None, activation.error
            built.append(source)
        pages[n] = shutil.copytree(versions, directory / str(n), symlinks=True)
        for source, value in collection.data(n).items():
            cmd_data_set(pages[n], source, value)
        write_log(pages[n], collection.log(n))
    return pages


def write_log(page: Path, commands: list[dict]) -> None:
    """Append `commands` to `page`'s log as admission records them: the first and
    last of each `shape` through `append_admitted`, the rest `renamed` from the
    first. A copy renames only the ids and words its command names, so a field
    admission derives from the document, such as the authored cards a move lies
    among, has to be the same for every command of a shape. The last one is
    checked against its copy, and a collection that breaks this fails here.

    Admitting each of thousands of events through `append_admitted` costs a fold of
    the log apiece, which is the cost the `events` collection measures, so it would
    cost the square of the log to build one. Admission derives the same fields for
    events that differ only in the ids and numbers they name, so a copy of what it
    made of the first stands for the rest."""
    from leaf.log.event_log import jsonl_line, new_event_id, read_events
    from leaf.records.event_contracts import append_admitted
    from leaf.records.transaction import PageTransaction

    admitted: dict[str, tuple[dict, dict]] = {}
    last = {shape(command): index for index, command in enumerate(commands)}
    events = read_events(page)
    copies: list[str] = []

    def flush() -> None:
        with (page / "events.jsonl").open("a", encoding="utf-8") as log:
            log.writelines(copies)
        copies.clear()

    def admit(command: dict) -> dict:
        flush()
        with PageTransaction(page) as transaction:
            record, _ = append_admitted(transaction, command)
        events.append(record)
        return record

    for index, command in enumerate(commands):
        key = shape(command)
        if key not in admitted:
            admitted[key] = (command, admit(command))
            continue
        template, record = admitted[key]
        copy = renamed(record, names(template, command))
        copy.pop("seq")
        if index == last[key]:
            made = admit(command)
            if _unstamped(made) != _unstamped(copy):
                raise ValueError(
                    f"admission made {made} of {command}, and its copy {copy}"
                )
            continue
        copy["id"] = command.get("id") or new_event_id(events)
        events.append(copy)
        copies.append(jsonl_line(copy) + "\n")
    flush()


def _unstamped(record: dict) -> dict:
    """`record` without what the append lease stamps on it."""
    return {
        key: value for key, value in record.items() if key not in ("id", "ts", "seq")
    }


def shape(command: dict) -> str:
    """What `command` is with its ids and numbers left out."""
    return json.dumps(_numbers_out(command), sort_keys=True)


def _numbers_out(value):
    if isinstance(value, dict):
        return {key: _numbers_out(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_numbers_out(item) for item in value]
    return re.sub(r"\d+", "#", value) if isinstance(value, str) else value


def _strings(value, path: tuple = ()) -> Iterator[tuple[tuple, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, (*path, index))
    elif isinstance(value, str):
        yield path, value


def names(template: dict, command: dict) -> dict[str, str]:
    """Each string `template` holds and what `command`, of the same shape, holds in
    its place."""
    theirs = dict(_strings(command))
    renames: dict[str, str] = {}
    for path, string in _strings(template):
        if renames.setdefault(string, theirs[path]) != theirs[path]:
            raise ValueError(f"{string!r} in {template} names two things in {command}")
    return renames


def renamed(value, renames: dict[str, str]):
    if isinstance(value, dict):
        return {key: renamed(item, renames) for key, item in value.items()}
    if isinstance(value, list):
        return [renamed(item, renames) for item in value]
    return renames.get(value, value) if isinstance(value, str) else value


def cpu_ms(run: Callable[[], object]) -> float:
    """The CPU `run` takes, in ms, with the collector run before it and held off
    during it, as `timeit` holds it: a collection costs what every page this
    process has read holds, not what the call does."""
    gc.collect()
    gc.disable()
    try:
        started = time.process_time()
        run()
        return (time.process_time() - started) * 1000
    finally:
        gc.enable()


def server_paths(page: Path, events: list[dict]) -> dict[str, Callable[[], object]]:
    """Each of `SERVER_PATHS` on `page`, whose log `events` built, as a call;
    `append` only where the log holds an event to send again, and `thread` only where
    it opens one."""
    from leaf.agents.delivery import (
        batch_data,
        deliverable,
        delivery_reading,
        freeze_delivery,
    )
    from leaf.commands.agent_state import cmd_page_state
    from leaf.records.event_contracts import append_admitted
    from leaf.records.revisioning import activate_source
    from leaf.records.transaction import PageTransaction
    from leaf.serving.served_state.service import PageStateService

    source = page / "index.html"
    authored = source.read_text()
    saves = iter(range(1, 1_000_000))

    def delivery():
        with PageTransaction(page) as transaction:
            if batch := deliverable(transaction):
                delivery_reading(
                    freeze_delivery([batch_data(page, transaction, batch)])
                )

    def activate():
        source.write_text(authored.replace("</h1>", f", saved {next(saves)}</h1>", 1))
        activation = activate_source(page)
        assert activation.error is None, activation.error

    calls = {
        "state": lambda: PageStateService(page).page_state(),
        "delivery": delivery,
        "agent": lambda: cmd_page_state(page),
        "activate": activate,
    }
    if events:
        # The event is sent again without the id its writer gave it, so admission
        # gives each time its own.
        again = {key: value for key, value in events[-1].items() if key != "id"}

        def append():
            with PageTransaction(page) as transaction:
                append_admitted(transaction, again)

        calls["append"] = append
    if thread := next((e["id"] for e in events if e["kind"] == "comment"), None):
        calls["thread"] = lambda: cmd_page_state(page, thread)
    return calls


def function_times(call: Callable[[], object]) -> dict[str, float]:
    """Inclusive ms per function of one profiled `call`."""
    profile = cProfile.Profile()
    profile.runcall(call)
    return {
        entry.code
        if isinstance(entry.code, str)
        else f"{entry.code.co_name} ({Path(entry.code.co_filename).name}:"
        f"{entry.code.co_firstlineno})": entry.totaltime * 1000
        for entry in profile.getstats()
    }


def measure_server(
    collection: Collection,
    sizes: list[int],
    directory: Path,
    profile: bool = False,
    rounds: int = SERVER_ROUNDS,
) -> tuple[list[dict], dict[str, tuple[dict, dict]]]:
    """Each path's least CPU over `rounds` on `collection`'s page at each of `sizes`,
    built under `directory`, in ms, beside the events its log holds; with
    `profile`, the function times of one more run of each path on the smallest
    page and the largest, in the order the rounds take them.

    The rounds are interleaved (`interleaved`, `lowest`). In each a page
    appends first, as a click does before its reading, and its versions come after
    every round, since a new one leaves the appended events on an earlier
    revision."""
    from leaf.log.event_log import read_events

    # The pages' claims, deliveries and presence stay out of the machine's own.
    state = directory / "state"
    state.mkdir(parents=True, exist_ok=True)
    with patch.dict(os.environ, XDG_STATE_HOME=str(state)):
        pages = server_pages(collection, sizes, directory)
        held = {n: len(read_events(pages[n])) for n in sizes}
        calls = {n: server_paths(pages[n], collection.log(n)) for n in sizes}
        order = (("append", "state", "delivery", "agent", "thread"), ("activate",))

        def timed(paths: tuple[str, ...], n: int) -> dict[str, float]:
            return {path: cpu_ms(calls[n][path]) for path in paths if path in calls[n]}

        appended, activated = (
            lowest((n, timed(paths, n)) for _, n in interleaved(rounds, sizes))
            for paths in order
        )
        profiled: dict[str, list[dict]] = {}
        if profile:
            for n in (sizes[0], sizes[-1]):
                for paths in order:
                    for path in paths:
                        if path in calls[n]:
                            profiled.setdefault(path, []).append(
                                function_times(calls[n][path])
                            )
        rows = []
        for n in sizes:
            readings = {**appended[n], **activated[n]}
            rows.append(
                {
                    "n": n,
                    "events": held[n],
                    **{
                        path: readings[path]
                        for path in SERVER_PATHS
                        if path in readings
                    },
                }
            )
    return rows, {path: (before, after) for path, (before, after) in profiled.items()}


def over_budget(rows: list[dict]) -> str | None:
    """Why a click's paths together take more than `BUDGET_MS` at `REFERENCE` in
    `rows`, or None: on a page with no log, or where `rows` has no `REFERENCE`, there
    is no click to time."""
    at = next((row for row in rows if row["n"] == REFERENCE), None)
    if at is None or not all(path in at for path in CLICK):
        return None
    click = sum(at[path] for path in CLICK)
    if click <= BUDGET_MS:
        return None
    return (
        f"{' + '.join(CLICK)} take {click:.0f} ms at {REFERENCE}, over {BUDGET_MS} ms"
    )


def bench_server(
    pages: Sequence[str], sizes: list[int], rounds: int | None, profile: bool, run: Path
) -> dict:
    """Time each server path on each generated page in this process
    (`measure_server`), echo each page's table, and return the rows."""
    rounds = rounds or SERVER_ROUNDS
    click.echo(f"Server paths of this checkout, least CPU of {rounds} rounds\n")
    results = {}
    for name in pages:
        rows, profiles = measure_server(
            COLLECTIONS[name], sizes, run / name, profile, rounds
        )
        results[name] = rows
        paths = [path for path in SERVER_PATHS if path in rows[0]]
        noise = server_floors(rows)
        sized = [row["n"] for row in rows]
        fits = {
            path: exponent(
                sized, [row[path] for row in rows], noise[path], SERVER_FITTED
            )
            for path in paths
        }
        columns = [(str(row["n"]), row) for row in rows]
        click.echo(
            table(name, columns, ["events", *paths], [("exponent", fits, paths)])
        )
        if why := over_budget(rows):
            click.echo(f"  click: {why}")
        click.echo()
        if profile:
            report_growth(name, profiles, sizes[-1] / sizes[0])
    return results


@click.command()
@click.argument("pages", nargs=-1)
@click.option(
    "--sizes",
    help="Comma-separated sizes of a generated page, each measured beside the page "
    f"of BASE [default: {','.join(map(str, SIZES))}, or for the server "
    f"{','.join(map(str, SERVER_SIZES))}].",
)
@click.option(
    "--input",
    "chosen_inputs",
    multiple=True,
    type=click.Choice(list(INPUTS)),
    help="Make only this input; repeat for more [default: every input].",
)
@click.option(
    "--read",
    "reads",
    multiple=True,
    type=click.Choice(["cpu", "paint", "server"]),
    help="Read only this; repeat for more [default: cpu and paint].",
)
@click.option(
    "--rounds",
    type=click.IntRange(1),
    help="Measure every page this many times, interleaved, and report each reading's "
    "lowest [default: 1, or for the server 3].",
)
@engine_option
@base_option()
@click.option("--profile", is_flag=True, help="Profile each reading's spans.")
def bench(
    pages: tuple[str, ...],
    sizes: str | None,
    chosen_inputs: tuple[str, ...],
    reads: tuple[str, ...],
    rounds: int | None,
    engine: str,
    base: str | None,
    profile: bool,
) -> None:
    """Measure what a page costs to load and to answer each input."""
    # Firefox reads only CPU: the paint pass reads Chrome's DevTools protocol.
    chosen = set(reads or (("cpu", "paint") if engine == "chromium" else ("cpu",)))
    authored = [name for name in pages if name not in COLLECTIONS]
    for name in authored:
        try:
            named_source(name)
        except ValueError as error:
            raise click.BadParameter(
                f"{error}; or a generated page: {', '.join(COLLECTIONS)}",
                param_hint="PAGE",
            ) from error
    if engine not in ("chromium", "firefox"):
        raise click.UsageError(
            "--browser: this reads Chromium's and Firefox's CPU only"
        )
    if engine == "firefox" and "paint" in chosen:
        raise click.UsageError(
            "--browser firefox reads only cpu: the paint pass reads Chrome's DevTools "
            "protocol"
        )
    if engine == "firefox" and profile:
        raise click.UsageError(
            "--profile is V8's; this module's header says how to profile Firefox"
        )
    if "server" in chosen and (base is not None or authored):
        raise click.UsageError(
            "--read server measures this checkout's generated pages only"
        )
    inputs = [name for name in INPUTS if not chosen_inputs or name in chosen_inputs]
    if "paint" in chosen and not any(INPUTS[name].paints for name in inputs):
        if reads:
            raise click.UsageError(
                "--read paint: none of the inputs paints a result; those that do are "
                + ", ".join(name for name, each in INPUTS.items() if each.paints)
            )
        chosen.discard("paint")
    run = run_directory(OUT)
    results: dict = {"lowest": [], "records": []}

    def write() -> None:
        """Keep what the run has read so far, so a failed page leaves the others."""
        (run / "results.json").write_text(json.dumps(results, indent=1, default=str))

    if browser_reads := chosen & {"cpu", "paint"}:
        arms = choose_arms(base, run)
        click.echo(f"{describe(arms)}, load average {load_average()}\n")
        sized = [int(n) for n in sizes.split(",")] if sizes else list(SIZES)
        with headless_shell() if engine == "chromium" else launch(engine) as browser:
            for name in pages or AXES:
                records = measure_page(
                    browser, arms, name, sized, inputs, browser_reads, rounds or 1, run,
                    profile,
                )  # fmt: skip
                report(records, arms, run, profile)
                results["lowest"] += [
                    {"page": name, "size": n, "arm": arm, "readings": readings}
                    for (n, arm), readings in lowest(
                        ((r.size, r.arm), r.readings) for r in records
                    ).items()
                ]
                # A profile's attribution stays in the report and its files.
                results["records"] += [
                    asdict(replace(r, windows=[
                        {key: value for key, value in w.items() if key != "profiled"}
                        for w in r.windows
                    ]))
                    for r in records
                ]  # fmt: skip
                write()
    if "server" in chosen:
        sized = sorted({BASE, *(map(int, sizes.split(",")) if sizes else SERVER_SIZES)})
        results["server"] = bench_server(
            pages or SERVER_AXES, sized, rounds, profile, run
        )
        write()
    click.echo(
        f"load average {load_average()} after; results in {run.relative_to(ROOT)}"
    )
