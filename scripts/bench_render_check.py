#!/usr/bin/env python3
"""Compare how long `leaf version check --render` takes, base vs HEAD, and where.

Each arm is the plugin payload at a ref, built by `eval_harness.build_arm`: BASE_REF
(default `main`) and HEAD, so commit what you want measured. For each page in PAGES
the script builds a page directory from this checkout's example with the arm's own
launcher (`page_fixtures.prepare_page`, as `preview.py` does), then runs that arm's
`bin/leaf version check <page> --render` RUNS times, alternating arms within each
round so drift in machine load falls on both. One untimed run per arm warms the
environment, Chrome and the OS file cache first.

Wall time is the child process's, launcher included. Phase times come from inside
the same child: its `PYTHONPATH` starts with `bench-render-check/`, so Python loads
that directory's `sitecustomize.py` at startup, which records through
`sys.monitoring` the start and end of each function FUNCTIONS names, so the check's
own code runs unchanged. `phases` turns those spans into rows: startup, markup validation, the plain check's page-code run, server and driver
start, browser launch, each render pass (viewport x color scheme), the once-per-
version width sweep, a confirming attempt, browser close and teardown. A second
table splits the passes by stage, and one row sums the frame waits the gate polls
for across the whole run. A third gives the CPU seconds of the leaf process and of
the driver and browser it reaped, which is what load from other processes competes
with. Rows are each arm's fastest run (`table` says why).

The report goes to stdout as Markdown, with `uptime` before and after; every
sample, trace and each arm's commit lands in `.tmp/bench-render-check/`.

Known limits:

- Three runs a page, and load from other processes still moves the fastest run. In
  two A/A runs on an 18-core Mac beside other suites, the arms' fastest walls
  differed by up to 4% at a load average near 12, and by 4.4 s of 15 at 30 to 90,
  most of it in browser close. Compare on a quiet machine, and read the phase rows,
  which say where a change landed, before the wall.
- The rows name functions in the arm's code. A ref that renames or restructures one
  shows `-` for its row and moves that time into `other`; update FUNCTIONS and
  `phases` when the gate's structure changes.
- The tracer needs Python 3.12 or newer in the arm's environment.
- Pages come from this checkout's `examples/` for both arms, so an example that
  needs something the base lacks fails there; a failing check is reported under its
  table, and its timings describe a check that stopped early.
- The page source is the stamped version, so the check reads it as the active
  revision rather than as an unstamped edit.
"""

import json
import os
import shutil
import statistics
import subprocess
import time
from functools import partial
from pathlib import Path

import click
from eval_harness import build_arm, environment, run_leaf
from page_fixtures import prepare_page, read_fixture

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".tmp" / "bench-render-check"
TRACER = Path(__file__).with_name("bench-render-check")
RUNS = 3
# The page an agent turn was measured on, a page with its own module code (so the
# plain check's page-code run happens too), and the heaviest page, the render corpus.
PAGES = ("triage-board", "data-explorer", "corpus")
FUNCTIONS = {
    "leaf/validation/command.py:cmd_check": [],
    "leaf/validation/source.py:check_source": [],
    "leaf/render_gate/command.py:page_code_check": [],
    "leaf/render_gate/command.py:render_check": [],
    "leaf/render_gate/preview.py:preview_server": [],
    "leaf/render_gate/browser.py:playwright_driver": [],
    "leaf/render_gate/browser.py:launch_browser": [],
    "leaf/render_gate/version.py:_render_version_attempt": [],
    "leaf/render_gate/scheme.py:_render_scheme": ["scheme", "viewport"],
    "leaf/render_gate/scheme.py:start_with_pre_upgrade_proof": [],
    "leaf/render_gate/readings.py:_scheme_findings": [],
    "leaf/render_gate/readings.py:sweep": [],
    "leaf/render_gate/readings.py:shrunk_label_advice": [],
    "leaf/render_checks.py:wait_for_probe": ["name"],
    "leaf/render_checks.py:one_frame": [],
    "leaf/render_checks.py:wait_until_ready": [],
    "playwright/sync_api/_generated.py:Browser.new_page": [],
    "playwright/sync_api/_generated.py:Browser.close": [],
}


def run_check(arm: Path, state: Path, page: Path, trace: Path) -> dict:
    """One `version check --render` by the arm's launcher, traced."""
    env = environment(
        XDG_STATE_HOME=str(state),
        LEAF_BENCH_TRACE=str(trace),
        LEAF_BENCH_FUNCTIONS=json.dumps(FUNCTIONS),
        PYTHONPATH=os.pathsep.join(
            filter(None, [str(TRACER), os.environ.get("PYTHONPATH")])
        ),
    )
    trace.unlink(missing_ok=True)
    spawned = time.time()
    started = time.perf_counter()
    proc = subprocess.run(
        [str(arm / "bin/leaf"), "version", "check", str(page), "--render"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    wall = time.perf_counter() - started
    if not trace.exists():
        raise click.ClickException(
            f"{arm.name} wrote no trace for {page.name}; the tracer needs Python "
            f"3.12+:\n{proc.stderr}"
        )
    return {
        "spawned": spawned,
        "wall": wall,
        "exit": proc.returncode,
        "stderr": proc.stderr,
        "trace": json.loads(trace.read_text(encoding="utf-8")),
    }


def phases(sample: dict) -> tuple[dict[str, float], ...]:
    """The run's phase rows, its render passes split by stage, and its CPU time.

    Only main-thread spans count, since the preview server's threads run work of
    their own (the corpus validates its samples there) beside the main thread's
    waits. A row is missing when its function never ran in this arm."""
    spans = [span for span in sample["trace"]["spans"] if span["main"]]

    def inside(span, outer):
        return outer["start"] <= span["start"] <= span["end"] <= outer["end"]

    def named(fn, *, part=None, within=None):
        return [
            span
            for span in spans
            if span["fn"].endswith(f":{fn}")
            and (part is None or span["part"] == part)
            and (within is None or inside(span, within))
        ]

    def total(found):
        return sum(span["end"] - span["start"] for span in found)

    rows = {}
    if check := named("cmd_check"):
        rows["startup: uv, Python, imports"] = check[0]["start"] - sample["spawned"]
    rows["markup validation"] = total(named("check_source"))
    if code := named("page_code_check"):
        rows["page code run (own browser)"] = total(code)
    stages = {}
    render = next(iter(named("render_check")), None)
    attempts = named("_render_version_attempt")
    if render and attempts:
        rows["server and driver start"] = total(
            named("preview_server", part=0, within=render)
            + named("playwright_driver", part=0, within=render)
        )
        rows["browser launch"] = total(named("launch_browser", within=render))
        passes = named("_render_scheme", within=attempts[0])
        once = [
            span
            for fn in ("sweep", "shrunk_label_advice")
            for span in named(fn, within=attempts[0])
        ]
        for scheme in passes:
            viewport = scheme["args"]["viewport"]
            size = f"{viewport['width']}x{viewport['height']}"
            rows[f"pass {size} {scheme['args']['scheme']}"] = total([scheme]) - total(
                [span for span in once if inside(span, scheme)]
            )
        rows["once: width sweep, advice"] = total(once)
        rows["confirming attempt"] = total(attempts[1:])
        rows["browser close"] = total(named("Browser.close", within=render))
        rows["driver and server stop"] = total(
            named("playwright_driver", part=1, within=render)
            + named("preview_server", part=1, within=render)
        )

        def in_passes(fn, name=None):
            return total(
                [
                    span
                    for scheme in passes
                    for span in named(fn, within=scheme)
                    if name is None or span["args"]["name"] == name
                ]
            )

        stages = {
            "new page": in_passes("Browser.new_page"),
            "load with entry held": in_passes("start_with_pre_upgrade_proof"),
            "runtime start": in_passes("wait_for_probe", "runtimeStarted"),
            "widget upgrade": in_passes("wait_for_probe", "upgraded"),
            "ready and settled": in_passes("wait_until_ready")
            + in_passes("wait_for_probe", "pageSettled"),
            "readings": in_passes("_scheme_findings"),
            "all frame waits (one_frame), whole run": total(
                named("one_frame", within=render)
            ),
        }
    rows["other"] = sample["wall"] - sum(rows.values())
    cpu = {
        "leaf process": sample["trace"]["cpu"]["self"],
        "Playwright driver and browser": sample["trace"]["cpu"]["children"],
    }
    return rows, stages, cpu


def table(title: str, samples: dict[str, list[dict]], index: int) -> list[str]:
    """One Markdown table of each arm's fastest run, and the change.

    The fastest run rather than the median: under other processes' load a run only
    gets slower, and in an A/A run of this script on a loaded Mac the arms' medians
    differed by up to 19% where their fastest runs differed by 4% at most. Rows are
    one run's, so they sum to its wall time."""
    fastest = {arm: min(runs, key=lambda s: s["wall"]) for arm, runs in samples.items()}
    readings = {arm: phases(sample)[index] for arm, sample in fastest.items()}
    lines = [f"| {title} | base | head | change |", "|---|---:|---:|---:|"]
    if index == 0:
        cells = [
            f"{fastest[arm]['wall']:.2f} "
            f"({statistics.median(s['wall'] for s in runs):.2f} / "
            f"{max(s['wall'] for s in runs):.2f})"
            for arm, runs in samples.items()
        ]
        change = fastest["head"]["wall"] - fastest["base"]["wall"]
        lines.append(
            f"| **wall** (median / slowest) | {cells[0]} | {cells[1]} | {change:+.2f} |"
        )
    for label in dict.fromkeys([*readings["base"], *readings["head"]]):
        base, head = (readings[arm].get(label) for arm in ("base", "head"))
        cells = ["-" if value is None else f"{value:.2f}" for value in (base, head)]
        change = "-" if None in (base, head) else f"{head - base:+.2f}"
        lines.append(f"| {label} | {cells[0]} | {cells[1]} | {change} |")
    return lines


def uptime() -> str:
    return subprocess.run(
        ["uptime"], capture_output=True, text=True, check=True
    ).stdout.strip()


@click.command()
@click.argument("base_ref", default="main")
def main(base_ref: str) -> None:
    """Time RUNS render checks of each page in PAGES: BASE_REF's plugin against HEAD's."""
    refs = {"base": base_ref, "head": "HEAD"}
    arms = {arm: OUT / "arms" / arm for arm in refs}
    commits = {arm: build_arm(ref, arms[arm]) for arm, ref in refs.items()}
    states = {arm: OUT / "state" / arm for arm in refs}
    pages = {}
    for arm in refs:
        states[arm].mkdir(parents=True, exist_ok=True)
        for name in PAGES:
            page = pages[arm, name] = OUT / "pages" / arm / name
            if page.exists():
                shutil.rmtree(page)
            page.parent.mkdir(parents=True, exist_ok=True)
            prepare_page(
                page,
                read_fixture(ROOT / "examples" / f"{name}.html"),
                partial(run_leaf, arms[arm], states[arm], check=True),
            )
    traces = OUT / "traces"
    traces.mkdir(exist_ok=True)
    before = uptime()
    for arm in refs:
        run_check(arms[arm], states[arm], pages[arm, PAGES[0]], traces / "warm.json")
    samples = {name: {arm: [] for arm in refs} for name in PAGES}
    for i in range(RUNS):
        for name in PAGES:
            for arm in refs:
                click.echo(f"run {i + 1}/{RUNS} {name} {arm}", err=True)
                samples[name][arm].append(
                    run_check(
                        arms[arm],
                        states[arm],
                        pages[arm, name],
                        traces / f"{arm}-{name}-{i + 1}.json",
                    )
                )
    after = uptime()
    (OUT / "results.json").write_text(
        json.dumps(
            {"commits": commits, "uptime": [before, after], "samples": samples},
            indent=1,
        )
    )
    click.echo(f"base {base_ref} {commits['base'][:10]}, head {commits['head'][:10]}")
    click.echo(f"uptime before: {before}\nuptime after:  {after}")
    click.echo(f"seconds, each arm's fastest of {RUNS} runs")
    for name in PAGES:
        click.echo(f"\n### {name}\n")
        click.echo("\n".join(table("phase", samples[name], 0)))
        for index, title in ((1, "render passes, summed"), (2, "CPU")):
            click.echo()
            click.echo("\n".join(table(title, samples[name], index)))
        for arm, runs in samples[name].items():
            if failed := [s for s in runs if s["exit"]]:
                first = next(
                    (line for line in failed[0]["stderr"].splitlines() if line), ""
                )
                click.echo(
                    f"\n{arm}: the check exited {failed[0]['exit']} in "
                    f"{len(failed)}/{len(runs)} runs: {first}"
                )
    click.echo(f"\ndetails: {OUT}/results.json")


if __name__ == "__main__":
    main()
