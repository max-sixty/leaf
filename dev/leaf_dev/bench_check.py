"""Compare how long `leaf page check --render` takes, base vs HEAD.

    uv run leaf-dev bench-check [BASE_REF]

Each arm is the plugin payload at a ref (`leaf_dev.harness.build_pair`): BASE_REF, by
default the merge base with `main`, and HEAD, so commit what you want measured. Each
page in PAGES is built from this checkout's example by the arm's own launcher, then
checked RUNS times by that arm's `bin/leaf`, alternating arms so drift in machine load
falls on both. Wall time is the child process's, launcher included. Other processes'
load moves every run, so read the spread and the load average before the median;
`leaf-dev profile` says where a browser transition's time goes.
"""

import shutil
import statistics
import time

import click

from leaf_dev import ROOT
from leaf_dev.harness import build_pair, build_source, load_average, run_leaf

OUT = ROOT / ".tmp" / "bench-check"
RUNS = 3
# The page an agent turn was measured on, a page with its own module code, and the
# heaviest page, the render corpus.
PAGES = ("triage-board", "data-explorer", "corpus")


def spread(walls: list[float]) -> str:
    return f"{statistics.median(walls):.2f} ({min(walls):.2f}-{max(walls):.2f})"


@click.command()
@click.argument("base_ref", required=False)
def bench_check(base_ref: str | None) -> None:
    """Time `page check --render`, base vs HEAD.

    Runs `leaf page check --render` on a few examples with BASE_REF's plugin and
    HEAD's, with no model; BASE_REF defaults to the merge base with main. Prints each
    arm's median (min-max) wall seconds per page.
    """
    arms, commits = build_pair(base_ref, OUT / "arms")
    pages = {}
    for arm, arm_dir in arms.items():
        for name in PAGES:
            page = pages[arm, name] = OUT / "pages" / arm / name
            shutil.rmtree(page, ignore_errors=True)
            page.parent.mkdir(parents=True, exist_ok=True)
            build_source(
                arm_dir, OUT / "state" / arm, ROOT / "examples" / f"{name}.html", page
            )
    before = load_average()
    walls = {key: [] for key in pages}
    for run in range(RUNS):
        for name in PAGES:
            for arm, arm_dir in arms.items():
                click.echo(f"run {run + 1}/{RUNS} {name} {arm}", err=True)
                started = time.perf_counter()
                run_leaf(
                    arm_dir, OUT / "state" / arm,
                    "page", "check", str(pages[arm, name]), "--render", check=True,
                )  # fmt: skip
                walls[arm, name].append(time.perf_counter() - started)
    click.echo(f"base {commits['base'][:10]} vs head {commits['head'][:10]}")
    click.echo(f"load average {before} before, {load_average()} after")
    click.echo(f"wall seconds, median (min-max) of {RUNS} runs\n")
    click.echo("| page | base | head | change |\n|---|---:|---:|---:|")
    for name in PAGES:
        base, head = walls["base", name], walls["head", name]
        change = statistics.median(head) - statistics.median(base)
        click.echo(f"| {name} | {spread(base)} | {spread(head)} | {change:+.2f} |")
