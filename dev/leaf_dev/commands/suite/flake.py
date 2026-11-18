"""Run tests as concurrent copies, so a failure that needs a loaded machine shows.

    uv run leaf-dev suite flake "tests/browser/threads/test_layout.py::test_x[pr-walkthrough]"

Repeating a test serially reruns it on the machine that already passes it; a browser
test that passed 20 serial runs failed twice in 18 concurrent ones. So this runs the
selection (`_runs`) as `--copies` copies, `--workers` at a time, from the working
tree as it stands, uncommitted edits included, captured once before collection.
Each copy runs in a private checkout of that snapshot, so fixed output paths and
later edits to the source checkout cannot change another copy's result. Installed
Node dependencies are shared as inputs; generated test output belongs to its copy.
Each copy is one process (`-n0`: the copies are the concurrency).

The copies are load that exists only to compete for the machine, so on macOS each one
runs in the background band (`taskpolicy -b`), which gives it only the CPU and disk the
machine's other work leaves, on the efficiency cores. The copies still compete with
each other, `--workers` at a time, and with the `--load` busy loops beside them, which
run in the same band and end with this command, since each spins only while its parent
is this command. A copy's demand for CPU comes and goes, so copies alone starve a test
less steadily than loops do. Beside other runs or other
sessions' work, a run takes longer rather than slowing them, though the band shares out
CPU and disk, not memory. A slower copy reports the same result, because the suite's
results don't depend on execution speed (`tests/AGENTS.md`, "Results do not depend on
execution speed").

A load flake that a slower CI runner shows and this machine doesn't can need a slower
CPU rather than more copies: `--cpu-throttle RATE` passes the suite's own option, which
slows every Chromium page the browser fixtures open (`tests/AGENTS.md`, "Races").

Prints each test's count per outcome, then every failure's message, grouped where
copies agree. Each copy's output stays under `.tmp/flake/`. Exits 0 only when every
copy of every test passed; a skip is not a pass.
"""

import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import run_directory
from leaf_dev.commands.suite._runs import checkout, collect, run, snapshot

BACKGROUND = ("taskpolicy", "-b") if sys.platform == "darwin" else ()
# A busy loop that spins while this command is its parent, so one this command
# can't end, as after a SIGKILL, ends itself.
SPIN = "import os\nparent = os.getppid()\nwhile os.getppid() == parent:\n    pass"
# A message is printed to this many lines; the log keeps all of it.
LINES = 12
OUT = ROOT / ".tmp" / "flake"
RESULTS = ("passed", "failed", "error", "skipped", "not run")


@click.command()
@click.argument("selection", nargs=-1, required=True)
@click.option(
    "--copies",
    type=click.IntRange(min=1),
    default=18,
    show_default=True,
    help="How many copies of the selection to run.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=6,
    show_default=True,
    help="How many copies run at once.",
)
@click.option(
    "--load",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="How many busy loops run beside the copies.",
)
@click.option(
    "--cpu-throttle",
    "throttle",
    type=click.FloatRange(min=1),
    help="Slow every Chromium page the tests open this many times.",
)
def flake(
    selection: tuple[str, ...],
    copies: int,
    workers: int,
    load: int,
    throttle: float | None,
) -> None:
    """Run tests as concurrent copies to surface load flakes.

    Runs SELECTION, pytest node ids from the working tree, as concurrent copies, and
    prints each test's count per outcome and every failure's message; each copy's
    output stays under .tmp/flake/. On macOS the copies run at background priority.
    Exits 1 unless every copy of every test passed.
    """
    out = run_directory(OUT)
    with tempfile.TemporaryDirectory(prefix="leaf-flake-") as directory:
        scratch = Path(directory)
        candidate = scratch / "snapshot"
        snapshot(candidate)
        options = ("-n0", *((f"--cpu-throttle={throttle}",) if throttle else ()))
        collection = scratch / "collection"
        checkout(candidate, collection)
        items = collect(collection, selection, out / "collect.log")
        shutil.rmtree(collection)

        def copy(n: int):
            target = scratch / f"copy-{n:02}"
            checkout(candidate, target)
            try:
                return run(
                    target,
                    selection,
                    items,
                    out / target.name,
                    *options,
                    under=BACKGROUND,
                )
            finally:
                shutil.rmtree(target)

        loops = [
            subprocess.Popen([*BACKGROUND, sys.executable, "-c", SPIN])
            for _ in range(load)
        ]
        pool = ThreadPoolExecutor(workers)
        try:
            results = list(pool.map(copy, range(1, copies + 1)))
        finally:
            # On Ctrl-C, start no more copies; the running ones stop with it.
            pool.shutdown(cancel_futures=True)
            for loop in loops:
                loop.terminate()
                loop.wait()

    click.echo(f"| test | {' | '.join(RESULTS)} |\n|---|{'---|' * len(RESULTS)}")
    for item in items:
        counts = Counter(c[item].result for c in results)
        click.echo(f"| `{item}` | {' | '.join(str(counts[r]) for r in RESULTS)} |")
    for item in items:
        messages = defaultdict(list)
        for n, c in enumerate(results, 1):
            if c[item].result not in ("passed", "skipped"):
                messages[c[item].result, c[item].message].append(n)
        if messages:
            click.echo(f"\n`{item}`:")
        for (result, message), ns in messages.items():
            lines = message.splitlines()
            text = "\n    ".join(lines[:LINES] + ["…"] * (len(lines) > LINES))
            click.echo(f"- copies {', '.join(map(str, ns))} ({result}): {text}")
    click.echo(f"\nlogs: {out.relative_to(ROOT)}/")
    green = all(c[item].result == "passed" for c in results for item in items)
    raise SystemExit(0 if green else 1)
