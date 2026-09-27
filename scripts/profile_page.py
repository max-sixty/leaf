#!/usr/bin/env python3
"""Attribute one transition's time on an open Leaf page, for this checkout.

    uv run scripts/profile_page.py SOURCE TRANSITION

`bench_page_latency.py` says how long a transition takes; this says where the time
goes. It serves `examples/SOURCE.html` from this checkout's runtime and server exactly
as the benchmark does (`bench_page_latency.served`), runs TRANSITION (`comment`,
`move`, `reply`, `status` or `revision`) RUNS times on a freshly loaded page, and
records each from just before it starts until its result is painted: a V8 CPU profile
sampled every 100 µs and a Chrome trace with style invalidation tracking.

The clock starts at the last keydown the trace holds for a gesture, and at the start
of the recording for a write, and runs to the painted frame; work after that frame
delays nothing the user is waiting on. The report, per run and then summed over runs:

- the main-thread tasks in that window, each with the JS that dominated it;
- style and layout, and how much of each script forced synchronously (a read of
  geometry, selection, or computed style after a write), with the element count of
  each forced style recalculation and the JS that forced it;
- the writes that invalidated style, by node and cause, with the JS that made them;
- JS functions by self and by inclusive time.

Invalidation tracking and stack capture slow the page, so read proportions and counts
here and durations from the benchmark. Each run's `.trace.json` opens in Chrome
DevTools' Performance panel or Perfetto, and its `.cpuprofile` in DevTools, under
`.tmp/profile-page/`. For time spent in the server, profile
`PageStateService(page_dir).page_state()` in-process with cProfile.
"""

import json
import statistics
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import bench_page_latency as bench
import click
from leaf.render_gate.browser import launch_browser
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".tmp" / "profile-page"
RUNS = 3
TRANSITIONS = ("comment", "move", "reply", "status", "revision")
CATEGORIES = [
    "blink.user_timing",
    "devtools.timeline",
    "disabled-by-default-devtools.timeline",
    "disabled-by-default-devtools.timeline.invalidationTracking",
    "disabled-by-default-devtools.timeline.stack",
]
# Trace events that run script: style or layout nested inside one of these was forced.
SCRIPT = {
    "FunctionCall",
    "EventDispatch",
    "TimerFire",
    "FireAnimationFrame",
    "v8.callFunction",
    "EvaluateScript",
    "RunMicrotasks",
}
RENDER = {
    "UpdateLayoutTree": "style",
    "Layout": "layout",
    "Paint": "paint",
    "Commit": "commit",
}
# Frames that say nothing about which runtime code ran: the sampler's own states and
# the bundle's module wrappers.
OPAQUE = (
    "(root)",
    "(program)",
    "(idle)",
    "(garbage collector)",
    "(anon) browser-runtime",
    "l browser-runtime",
)
# A main-thread task's trace event, by Chrome version.
TASKS = {"RunTask", "ThreadControllerImpl::RunTask"}
TASK_MIN_MS = 2
TOP = 12


def ms(us: float) -> float:
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
        for sample, delta, following in zip(
            profile["samples"], deltas, deltas[1:] + [0]
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


def main_thread(events: list) -> list:
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


def attribute(trace: Path, profile: Profile) -> dict:
    """What the main thread did from the input (or the recording's start) to the frame
    the benchmark's probe marked as painting the transition's first goal."""
    everything = json.loads(trace.read_text())
    everything = (
        everything["traceEvents"] if isinstance(everything, dict) else everything
    )
    end = min(e["ts"] for e in everything if e.get("name", "").startswith("lf-bench:"))
    events = [e for e in main_thread(everything) if e["ts"] <= end]
    spans = [e for e in events if e.get("ph") == "X"]
    keys = [
        e["ts"]
        for e in spans
        if e["name"] == "EventDispatch"
        and e["args"].get("data", {}).get("type") == "keydown"
    ]
    start = keys[-1] if keys else spans[0]["ts"]

    # A task or a render step can straddle either end; only its part inside counts.
    inside = lambda e: min(e["ts"] + e.get("dur", 0), end) - max(e["ts"], start)
    tasks = [
        (
            max(e["ts"], start) - start,
            inside(e),
            profile.dominant(max(e["ts"], start), min(e["ts"] + e["dur"], end)),
        )
        for e in spans
        if e["name"] in TASKS and inside(e) >= TASK_MIN_MS * 1000
    ]
    render, forced, recalcs = Counter(), Counter(), Counter()
    open_spans = []  # (name, end) of the spans enclosing the current one
    for e in spans:
        while open_spans and open_spans[-1][1] <= e["ts"]:
            open_spans.pop()
        kind = RENDER.get(e["name"])
        if (
            kind
            and e["ts"] >= start
            and not any(RENDER.get(n) == kind for n, _ in open_spans)
        ):
            render[kind] += inside(e)
            if any(n in SCRIPT for n, _ in open_spans):
                forced[kind] += inside(e)
                if kind == "style":
                    args = e.get("args", {})
                    frames = (args.get("beginData") or {}).get("stackTrace") or []
                    count = args.get("elementCount") or (args.get("endData") or {}).get(
                        "elementCount"
                    )
                    recalcs[(stack_label(frames, 4), count)] += 1
        open_spans.append((e["name"], e["ts"] + e.get("dur", 0)))
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
        "tasks": tasks,
        "render": render,
        "forced": forced,
        "recalcs": recalcs,
        "invalidations": invalidations,
        "own": own,
        "inclusive": inclusive,
    }


@contextmanager
def recorded(session, browser, name: str, runs: list):
    """Profile and trace the page for the life of the block, then attribute it."""
    cdp = session.page.context.new_cdp_session(session.page)
    cdp.send("Profiler.enable")
    cdp.send("Profiler.setSamplingInterval", {"interval": 100})
    trace = OUT / f"{name}.trace.json"
    browser.start_tracing(page=session.page, path=str(trace), categories=CATEGORIES)
    cdp.send("Profiler.start")
    try:
        yield
    finally:
        profile = cdp.send("Profiler.stop")["profile"]
        browser.stop_tracing()
        cdp.detach()
    (OUT / f"{name}.cpuprofile").write_text(json.dumps(profile))
    runs.append(attribute(trace, Profile(profile)))


def show(runs: list) -> None:
    for number, run in enumerate(runs, 1):
        click.echo(
            f"run {number}: {ms(run['window'])} ms from input to the painted frame"
        )
        for at, duration, paths in run["tasks"]:
            click.echo(
                f"  {ms(at):7.1f} ms  task {ms(duration):6.1f} ms  {' | '.join(paths)}"
            )
    total = lambda key: sum((run[key] for run in runs), Counter())
    per_run = lambda value: ms(value / len(runs))
    render, forced = total("render"), total("forced")
    click.echo(f"\nper run, over {len(runs)} runs")
    click.echo(
        "  render ms: "
        + ", ".join(
            f"{k} {per_run(v)} (forced {per_run(forced[k])})"
            for k, v in render.most_common()
        )
    )
    click.echo("  forced style recalculations (count, elements, forced by):")
    for (where, count), n in total("recalcs").most_common(TOP):
        click.echo(f"    {n:4}  {count or '?':>5}  {where}")
    click.echo("  style invalidations (count, event, cause, node, written by):")
    for (event, cause, node, where), n in total("invalidations").most_common(TOP):
        click.echo(f"    {n:4}  {event} | {cause} | {node} | {where}")
    for key, title in (("own", "self"), ("inclusive", "inclusive")):
        click.echo(f"  JS by {title} ms:")
        for frame, value in total(key).most_common(TOP):
            click.echo(f"    {per_run(value):7.1f}  {frame}")


@click.command()
@click.argument("source", type=click.Choice(bench.SOURCES))
@click.argument("transition", type=click.Choice(TRANSITIONS))
def main(source: str, transition: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = []
    with (
        tempfile.TemporaryDirectory(prefix="leaf-profile-") as scratch,
        sync_playwright() as playwright,
    ):
        browser, _ = launch_browser(playwright)
        with bench.served(browser, "head", ROOT, source, Path(scratch)) as session:
            for run in range(RUNS):
                session.open()
                name = f"{source}-{transition}-{run + 1}"
                session.recording = lambda name=name: recorded(
                    session, browser, name, runs
                )
                getattr(session, transition)(run)
        browser.close()
    show(runs)
    click.echo(
        f"\nwindows: {statistics.median(ms(r['window']) for r in runs)} ms median; files in {OUT}"
    )


if __name__ == "__main__":
    main()
