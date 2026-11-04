"""Measure how a page's main-thread cost grows with the page, for this checkout.

    uv run leaf-dev scaling [AXIS ...] [--sizes 32,64,128,256] [--base [REF]] [--profile]

Root `AGENTS.md`, "Responsiveness", sets the rule this checks: no cost grows faster
than the page, and an input's should hardly grow at all. For each AXIS (every one by
default) it generates a page at each size (`AXES`), serves it from this tree, and
reads the renderer's main-thread CPU, in thread ticks from `Performance.getMetrics`,
for each transition: the load until the page settles, a click on an option, a
keystroke in the page's comment field, and a wheel step down the page. An input's
cost is the mean over several, less the page's idle CPU over the same time. Beside
them stand the server's time to start answering each event the clicks posted, whose
answer carries the server's reading of the page, and that answer's size. Every run
also measures a page of BASE, whose costs are mostly the runtime's fixed work. It
prints each cost by size with the exponent of its growth above the BASE page, fitted
over the largest sizes (least squares of log growth on log size), and marks an
exponent above SUPERLINEAR, which is a step nesting one walk of the page inside
another. Fitting the cost itself would let fixed work hide that: 30 ms per click plus
20/80/320 ms of quadratic work fits 1.4 over 64-256, and its growth fits 2.0.

--base also measures the merge base with main (or REF), chosen as every A/B command
chooses its arms (`arms.choose_arms`), so a change shows its exponents beside the
base's. --profile
records a V8 CPU profile of each transition at the smallest and largest size and
lists the functions whose time grew superlinearly between them, which names the
nested walk.

CPU time rather than wall time, so a loaded host spreads the readings less than it
spreads elapsed time; each exponent still compares sizes within one run. Pages, the
profiles and `results.json` land in a run directory under `.tmp/scaling/`. The daily
suite fails growth well past linear on every axis with the same measurement
(`tests/journeys/test_scaling.py`).
"""

import json
import math
import statistics
import time
from collections.abc import Callable
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import (
    base_option,
    choose_arms,
    describe,
    run_directory,
    serving_source,
)
from leaf_dev.browser import headless_shell, settle, tab
from leaf_dev.commands.bench_latency import Profile

OUT = ROOT / ".tmp" / "scaling"
SIZES = (32, 64, 128, 256)
# The page size whose costs stand for the runtime's fixed work. Each exponent fits a
# cost's growth above it, so it is a small fraction of the sizes fitted.
BASE = 8
# An exponent above this is superlinear growth. It stands halfway between linear and
# quadratic: above BASE, linear growth fits about 1.07 over 64-256, and n log n 1.25.
SUPERLINEAR = 1.5
# How many of the largest sizes the exponent is fitted over.
FITTED = 3
# A cost that grows by less than this above BASE has no exponent: what little it grew
# is the host's noise. Milliseconds of CPU, kilobytes for the event answer's size, and
# for the server's time to answer, which is elapsed time, milliseconds.
FLOORS = {"event": 50}
FLOOR = 10
KEYS = 20
CLICKS = 4
WHEEL_STEPS = 30
# A function must take this long at the largest size to be listed as growing.
GROWTH_FLOOR_MS = 20
DEADLINE_MS = 300_000
TRANSITIONS = ("load", "click", "key", "scroll")
# The server's side of a click: how long it took to start answering each event the
# clicks posted, whose answer carries its reading of the page, and how large that was.
SERVER = ("event", "event_kb")
EVENT_POSTS = """() => performance.getEntriesByType("resource")
  .filter((entry) => new URL(entry.name).pathname.endsWith("/api/event"))
  .map((entry) => ({
    ms: entry.responseStart - entry.requestStart,
    kb: entry.encodedBodySize / 1024,
  }))"""


def ask_sections(n: int) -> str:
    """`n` sections, each a heading, a paragraph and an `lf-ask` of four options, so
    widgets, obligations on the user, headings and margin pins all grow with `n`."""
    sections = "".join(
        f'<section id="s{g}"><h2>Section {g}</h2><p>Some words about section {g}.</p>'
        f'<lf-ask id="q{g}"><h3>Question {g}</h3><lf-options id="o{g}" choose multiple>'
        + "".join(
            f'<lf-option id="o{g}-{i}"><strong>Option {i}</strong> a short description.'
            "</lf-option>"
            for i in range(1, 5)
        )
        + "</lf-options></lf-ask></section>"
        for g in range(1, n + 1)
    )
    return page("Questions", sections)


def prose_sections(n: int) -> str:
    """`n` sections of headings and paragraphs after one ask: the document grows, and
    the widgets don't."""
    ask = (
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
    return page("Prose", ask + sections)


def thread_log(n: int) -> str:
    """`n` comment threads across `prose_sections(64)`, each answered once, so the log
    and the threads grow while the document stays."""
    events = []
    for t in range(n):
        events.append(
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "id": f"c{t}",
                "text": f"A question {t} about this section?",
                "anchor": {"section": f"s{t % 64 + 1}"},
            }
        )
        events.append(
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": f"c{t}",
                "revision": 1,
                "text": f"Answer {t}.",
            }
        )
    return "".join(json.dumps(event) + "\n" for event in events)


def page(title: str, body: str) -> str:
    return (
        f'<!doctype html><html lang="en"><head><title>{title}</title></head><body>'
        f'<main><article id="document"><h1>{title}</h1>{body}</article></main>'
        "</body></html>"
    )


# Each axis: the authored page at a size, and the log admitted after it, if any.
AXES: dict[str, tuple[Callable[[int], str], Callable[[int], str] | None]] = {
    "asks": (ask_sections, None),
    "prose": (prose_sections, None),
    "threads": (lambda _: prose_sections(64), thread_log),
}


def cpu_ms(cdp) -> float:
    metrics = cdp.send("Performance.getMetrics")["metrics"]
    return next(m["value"] for m in metrics if m["name"] == "TaskDuration") * 1000


def profiler(cdp, directory: Path | None):
    """Start a V8 CPU profile of the transition `name` into `directory`, or nothing,
    and return what stops it."""

    def start(name: str):
        if directory is None:
            return lambda: None
        target = directory / f"{name}.cpuprofile"
        cdp.send("Profiler.enable")
        cdp.send("Profiler.setSamplingInterval", {"interval": 200})
        cdp.send("Profiler.start")
        return lambda: target.write_text(
            json.dumps(cdp.send("Profiler.stop")["profile"])
        )

    return start


def measure(browser, address: str, profiles: Path | None) -> dict:
    """Each transition's main-thread CPU on the page at `address`, in ms."""
    with tab(browser) as tab_page:
        # A superlinear path can hold the main thread for seconds per input on a
        # large page, which is what this measures rather than a failure.
        tab_page.set_default_timeout(DEADLINE_MS)
        cdp = tab_page.context.new_cdp_session(tab_page)
        cdp.send("Performance.enable", {"timeDomain": "threadTicks"})
        profiled = profiler(cdp, profiles)
        quiet = tab_page.wait_for_timeout

        start = cpu_ms(cdp)
        stop = profiled("load")
        tab_page.goto(address)
        settle(tab_page)
        quiet(600)
        stop()
        costs = {"load": cpu_ms(cdp) - start}
        elements = tab_page.evaluate("document.querySelectorAll('*').length")

        start = cpu_ms(cdp)
        quiet(1000)
        idle = (cpu_ms(cdp) - start) / 1000

        def per_input(name: str, count: int, act) -> float:
            start, began = cpu_ms(cdp), time.monotonic()
            stop = profiled(name)
            for _ in range(count):
                act()
            quiet(600)
            stop()
            elapsed = (time.monotonic() - began) * 1000
            return (cpu_ms(cdp) - start - idle * elapsed) / count

        option = tab_page.locator("lf-option").first

        def click():
            # Each click posts its event; the server's answer arrives before the
            # quiet that lets the page apply it.
            with tab_page.expect_response(
                lambda response: response.url.endswith("/api/event")
            ):
                option.click()
            quiet(400)

        posted = len(tab_page.evaluate(EVENT_POSTS))
        costs["click"] = per_input("click", CLICKS, click)
        posts = tab_page.evaluate(EVENT_POSTS)[posted:]
        costs["event"] = statistics.median(post["ms"] for post in posts)
        costs["event_kb"] = statistics.median(post["kb"] for post in posts)

        tab_page.locator(".lf-fp-field").first.click()
        quiet(600)
        letters = iter("abcdefghijklmnopqrstuvwxyz" * 4)

        def key():
            tab_page.keyboard.type(next(letters))
            quiet(60)

        costs["key"] = per_input("key", KEYS, key)

        tab_page.evaluate("() => { document.activeElement?.blur(); scrollTo(0, 0); }")
        tab_page.mouse.move(400, 400)
        quiet(600)
        height = tab_page.evaluate("document.scrollingElement.scrollHeight")

        def wheel():
            tab_page.mouse.wheel(0, height / WHEEL_STEPS)
            quiet(50)

        costs["scroll"] = per_input("scroll", WHEEL_STEPS, wheel)
        return {"elements": elements, **costs}


def exponent(cost: str, sizes: list[int], costs: list[float]) -> float | None:
    """The least-squares slope of log growth on log size over the largest sizes,
    where a cost's growth is what it adds to its cost at the first size, BASE; None
    for growth under the cost's floor."""
    fixed = costs[0]
    if costs[-1] - fixed < FLOORS.get(cost, FLOOR):
        return None
    pairs = [
        (math.log(n), math.log(c - fixed))
        for n, c in list(zip(sizes, costs, strict=True))[-FITTED:]
        if c > fixed
    ]
    if len(pairs) < 2:
        return None
    mean_x = sum(x for x, _ in pairs) / len(pairs)
    mean_y = sum(y for _, y in pairs) / len(pairs)
    spread = sum((x - mean_x) ** 2 for x, _ in pairs)
    return sum((x - mean_x) * (y - mean_y) for x, y in pairs) / spread


COLUMNS = (*(f"{t} ms" for t in TRANSITIONS), "event ms", "event KB")


def table(axis: str, arm: str, rows: list[dict]) -> str:
    sizes = [row["n"] for row in rows]
    lines = [
        f"{axis} ({arm})",
        f"{'n':>6} {'elements':>9}" + "".join(f" {name:>10}" for name in COLUMNS),
    ]
    for row in rows:
        lines.append(
            f"{row['n']:>6} {row['elements']:>9}"
            + "".join(f" {row[t]:>10.1f}" for t in (*TRANSITIONS, *SERVER))
        )
    cells = []
    for transition in (*TRANSITIONS, *SERVER):
        slope = exponent(transition, sizes, [row[transition] for row in rows])
        mark = "!" if slope is not None and slope > SUPERLINEAR else " "
        cells.append(f" {'-' if slope is None else f'{slope:.2f}':>9}{mark}")
    lines.append(f"{'exponent':>16}" + "".join(cells))
    return "\n".join(lines)


def function_times(path: Path) -> dict[str, float]:
    """Inclusive ms per function in a CPU profile, each sample counted once per
    function on its stack."""
    times: dict[str, float] = {}
    for _, duration, chain in Profile(json.loads(path.read_text())).samples:
        for name in set(chain):
            times[name] = times.get(name, 0) + duration / 1000
    return times


def growth(small: Path, large: Path, ratio: float) -> list[str]:
    """The functions whose time grew superlinearly from `small` to `large`."""
    before, after = function_times(small), function_times(large)
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


@click.command()
@click.argument("axes", nargs=-1, type=click.Choice(sorted(AXES)))
@click.option(
    "--sizes",
    default=",".join(map(str, SIZES)),
    show_default=True,
    help="Comma-separated page sizes, measured beside the page of BASE.",
)
@base_option()
@click.option("--profile", is_flag=True, help="Profile the smallest and largest size.")
def scaling(axes: tuple[str, ...], sizes: str, base: str | None, profile: bool) -> None:
    sized = sorted({BASE, *(int(size) for size in sizes.split(","))})
    run = run_directory(OUT)
    arms = choose_arms(base, run)
    click.echo(describe(arms) + "\n")
    results: dict[str, dict[str, list[dict]]] = {}
    with headless_shell() as browser:
        for axis in axes or tuple(AXES):
            authored, log = AXES[axis]
            for arm, chosen in arms.items():
                rows = []
                for n in sized:
                    scratch = run / f"{axis}-{arm}-{n}"
                    scratch.mkdir(parents=True)
                    source = scratch / f"{axis}{n}.html"
                    source.write_text(authored(n))
                    seed = None
                    if log is not None:
                        seed = scratch / "seed.jsonl"
                        seed.write_text(log(n))
                    profiles = (
                        scratch if profile and n in (sized[0], sized[-1]) else None
                    )
                    with serving_source(
                        chosen.directory, source, scratch / "page", seed
                    ) as address:
                        rows.append({"n": n, **measure(browser, address, profiles)})
                results.setdefault(axis, {})[arm] = rows
                click.echo(table(axis, arm, rows) + "\n")
                if profile:
                    first, last = (
                        run / f"{axis}-{arm}-{n}" for n in (sized[0], sized[-1])
                    )
                    for transition in TRANSITIONS:
                        lines = growth(
                            first / f"{transition}.cpuprofile",
                            last / f"{transition}.cpuprofile",
                            sized[-1] / sized[0],
                        )
                        if lines:
                            click.echo(
                                f"{axis} ({arm}) {transition}: superlinear functions"
                            )
                            click.echo("\n".join(lines) + "\n")
    (run / "results.json").write_text(json.dumps(results, indent=1))
    click.echo(f"Results in {run.relative_to(ROOT)}")
