"""Run tests as concurrent copies, so a failure that needs a loaded machine shows.

    uv run leaf-dev flake "tests/test_render_threads.py::test_x[pr-walkthrough]"

Repeating a test serially reruns it on the machine that already passes it. A browser
test that passed 20 serial runs failed twice in 18 concurrent ones, by a different
mechanism each time: both were timing facts only a busy machine exposes. So this
runs the selection (`leaf_dev.suite`) as `COPIES` copies, `WORKERS` at a time, from
the working tree as it stands, uncommitted edits included.

Each copy is one process (`-n0`: the copies are the concurrency) with a cache
directory of its own, so the copies neither race on `.pytest_cache` nor replace
the `--lf` record of the checkout's own runs. The selection is collected first,
and one pytest would not run is refused rather than reported green.

The copies share everything else a test writes at a fixed path in the checkout,
such as a preview test's export under `.tmp/`, so two copies racing there fail the
way a load flake does; a failure message naming such a path is that race.

It prints a Markdown table of each test's passes, failures (anything `suite` reports
other than passed or skipped), and skips, then every failure's message, grouped
where copies agree, since the message is what names the mechanism and it differs run
to run. Each copy's terminal output and report log stay under `.tmp/flake/`. It
exits 0 only when every copy of every test passed, so a test that only skips is not
reported green.

An edit to the tree while the copies run voids them: browser tests then fail as
navigation timeouts that read like load. The tree, untracked files included, is read
before and after, and a run it changed under is reported void.
"""

import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.suite import collect, run, stoppable

COPIES = 18
WORKERS = 6
# A message is printed to this many lines; the log keeps all of it.
LINES = 12
OUT = ROOT / ".tmp" / "flake"


def tree_state() -> str:
    """The tree the working tree would commit as, untracked files included, written
    through a copy of the index so the checkout's own is untouched."""

    def git(*args: str, env: dict | None = None) -> str:
        return subprocess.run(
            ["git", "-C", ROOT, *args],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        ).stdout.strip()

    with tempfile.TemporaryDirectory() as scratch:
        index = Path(scratch) / "index"
        shutil.copy(ROOT / git("rev-parse", "--git-path", "index"), index)
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        git("add", "-A", env=env)
        return git("write-tree", env=env)


@click.command()
@click.argument("selection", nargs=-1, required=True)
def flake(selection: tuple[str, ...]) -> None:
    """Run tests as concurrent copies to surface load flakes.

    Runs SELECTION, pytest node ids from the working tree, as 18 copies six at a
    time, and prints each test's passes, failures and skips and every failure's
    message; each copy's output stays under .tmp/flake/. Exits 1 unless every copy
    of every test passed.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-")
    out = Path(tempfile.mkdtemp(prefix=stamp, dir=OUT))
    with stoppable():
        items = collect(ROOT, selection, out / "collect.log")
        before = tree_state()

        def copy(n: int):
            cache = f"cache_dir={out / 'cache' / str(n)}"
            return run(ROOT, selection, items, out / f"copy-{n:02}", "-n0", "-o", cache)

        with ThreadPoolExecutor(WORKERS) as pool:
            copies = list(pool.map(copy, range(1, COPIES + 1)))
        void = tree_state() != before

    def count(item: str, *results: str) -> int:
        return sum(c[item].result in results for c in copies)

    click.echo("| test | passed | failed | skipped |\n|---|---|---|---|")
    for item in items:
        passed, skipped = count(item, "passed"), count(item, "skipped")
        failed = COPIES - passed - skipped
        click.echo(f"| `{item}` | {passed} | {failed} | {skipped} |")
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
    if void:
        click.echo("void: the working tree changed while the copies ran")
    green = all(c[item].result == "passed" for c in copies for item in items)
    raise SystemExit(0 if green and not void else 1)
