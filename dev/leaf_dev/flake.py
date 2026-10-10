"""Run tests as concurrent copies, so a failure that needs a loaded machine shows.

    uv run leaf-dev flake "tests/test_render_threads.py::test_x[pr-walkthrough]"

Repeating a test serially reruns it on the machine that already passes it; a browser
test that passed 20 serial runs failed twice in 18 concurrent ones. So this runs the
selection (`leaf_dev.suite`) as `COPIES` copies, `WORKERS` at a time, from the working
tree as it stands, uncommitted edits included, captured once before collection.
Each copy runs in a private checkout of that snapshot, so fixed output paths and
later edits to the source checkout cannot change another copy's result. Installed
Node dependencies are shared as inputs; generated test output belongs to its copy.
Each copy is one process (`-n0`: the copies are the concurrency).

Prints each test's count per outcome, then every failure's message, grouped where
copies agree. Each copy's output stays under `.tmp/flake/`. Exits 0 only when every
copy of every test passed; a skip is not a pass.
"""

import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import copy_working
from leaf_dev.suite import collect, run

COPIES = 18
WORKERS = 6
# A message is printed to this many lines; the log keeps all of it.
LINES = 12
OUT = ROOT / ".tmp" / "flake"
RESULTS = ("passed", "failed", "error", "skipped", "not run")


@click.command()
@click.argument("selection", nargs=-1, required=True)
def flake(selection: tuple[str, ...]) -> None:
    """Run tests as concurrent copies to surface load flakes.

    Runs SELECTION, pytest node ids from the working tree, as 18 copies six at a
    time, and prints each test's count per outcome and every failure's message; each
    copy's output stays under .tmp/flake/. Exits 1 unless every copy of every test
    passed.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-")
    out = Path(tempfile.mkdtemp(prefix=stamp, dir=OUT))
    with tempfile.TemporaryDirectory(prefix="leaf-flake-") as directory:
        scratch = Path(directory)
        snapshot = scratch / "snapshot"
        subprocess.run(
            ["git", "clone", "-q", "--no-checkout", ROOT, snapshot], check=True
        )
        copy_working((".",), snapshot)
        subprocess.run(["git", "-C", snapshot, "add", "--all"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                snapshot,
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=Leaf flake",
                "-c",
                "user.email=flake@localhost",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "Candidate snapshot",
            ],
            check=True,
        )
        ignored = subprocess.check_output(
            [
                "git",
                "-C",
                ROOT,
                "ls-files",
                "-z",
                "--others",
                "--ignored",
                "--directory",
                "--exclude-standard",
            ],
            text=True,
        ).split("\0")
        dependencies = [
            Path(p.rstrip("/"))
            for p in ignored
            if Path(p.rstrip("/")).name == "node_modules"
        ]

        def checkout(target: Path):
            subprocess.run(["git", "clone", "-q", snapshot, target], check=True)
            for dependency in dependencies:
                (target / dependency).symlink_to(
                    ROOT / dependency, target_is_directory=True
                )

        collection = scratch / "collection"
        checkout(collection)
        items = collect(collection, selection, out / "collect.log")
        shutil.rmtree(collection)

        def copy(n: int):
            target = scratch / f"copy-{n:02}"
            checkout(target)
            try:
                return run(target, selection, items, out / target.name, "-n0")
            finally:
                shutil.rmtree(target)

        pool = ThreadPoolExecutor(WORKERS)
        try:
            copies = list(pool.map(copy, range(1, COPIES + 1)))
        finally:
            # On Ctrl-C, start no more copies; the running ones stop with it.
            pool.shutdown(cancel_futures=True)

    click.echo(f"| test | {' | '.join(RESULTS)} |\n|---|{'---|' * len(RESULTS)}")
    for item in items:
        counts = Counter(c[item].result for c in copies)
        click.echo(f"| `{item}` | {' | '.join(str(counts[r]) for r in RESULTS)} |")
    for item in items:
        messages = defaultdict(list)
        for n, c in enumerate(copies, 1):
            if c[item].result not in ("passed", "skipped"):
                messages[c[item].result, c[item].message].append(n)
        if messages:
            click.echo(f"\n`{item}`:")
        for (result, message), ns in messages.items():
            lines = message.splitlines()
            text = "\n    ".join(lines[:LINES] + ["…"] * (len(lines) > LINES))
            click.echo(f"- copies {', '.join(map(str, ns))} ({result}): {text}")
    click.echo(f"\nlogs: {out.relative_to(ROOT)}/")
    green = all(c[item].result == "passed" for c in copies for item in items)
    raise SystemExit(0 if green else 1)
