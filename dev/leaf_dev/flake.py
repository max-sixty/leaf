"""Run tests as concurrent copies, so a failure that needs a loaded machine shows.

    uv run leaf-dev flake "tests/test_render_threads.py::test_x[pr-walkthrough]"

Repeating a test serially reruns it on the machine that already passes it; a browser
test that passed 20 serial runs failed twice in 18 concurrent ones. So this runs the
selection (`leaf_dev.suite`) as `COPIES` copies, `WORKERS` at a time, from the working
tree as it stands, uncommitted edits included. Don't edit the tree during a run:
browser tests then fail as navigation timeouts that read like load.

Each copy is one process (`-n0`: the copies are the concurrency) with a cache
directory of its own. The copies share every other fixed path a test writes in the
checkout, such as an export under `.tmp/`, so a failure naming one is the copies
racing there.

Prints each test's count per outcome, then every failure's message, grouped where
copies agree. Each copy's output stays under `.tmp/flake/`. Exits 0 only when every
copy of every test passed; a skip is not a pass.
"""

import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
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
    items = collect(ROOT, selection, out / "collect.log")

    def copy(n: int):
        cache = f"cache_dir={out / 'cache' / str(n)}"
        return run(ROOT, selection, items, out / f"copy-{n:02}", "-n0", "-o", cache)

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
