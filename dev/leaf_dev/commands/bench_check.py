"""Compare how long `leaf page check --render` takes, base vs this working tree.

    uv run leaf-dev bench-check [--base REF]

The base is the merge base with `main` unless `--base` names another commit, and the
head is this working tree, uncommitted edits included (`leaf_dev.arms.choose_arms`).
Each page in PAGES is built from this checkout's example by the arm's own launcher,
then checked RUNS times by that arm's `bin/leaf`, alternating arms so drift in machine
load falls on both. Wall time is the child process's, launcher included. Other
processes' load moves every run, so read the spread and the load average before the
median; `leaf-dev profile` says where a browser transition's time goes.

Each invocation builds its base, pages, and state in a unique run directory under
`.tmp/bench-check/` and prints that directory.
"""

import statistics
import time

import click

from leaf_dev import ROOT
from leaf_dev.arms import (
    base_option,
    build_source,
    choose_arms,
    describe,
    load_average,
    run_directory,
    run_leaf,
)
from leaf_dev.commands.distribution import current_kernel
from leaf_dev.example_data import named_source

OUT = ROOT / ".tmp" / "bench-check"
RUNS = 3
# The page an agent turn was measured on, a page with its own module code, and the
# heaviest page, the render corpus.
PAGES = ("triage-board", "data-explorer", "corpus")


def spread(walls: list[float]) -> str:
    return f"{statistics.median(walls):.2f} ({min(walls):.2f}-{max(walls):.2f})"


@click.command()
@base_option(paired=True)
def bench_check(base: str) -> None:
    """Time `page check --render`, base vs this working tree.

    Runs `leaf page check --render` on a few examples with the base's plugin and
    this working tree's, with no model. Prints each arm's median (min-max) wall
    seconds per page.
    """
    out = run_directory(OUT)
    arms = choose_arms(base, out)
    pages = {}
    for arm, version in arms.items():
        current_kernel(version.directory)
        for name in PAGES:
            page = pages[arm, name] = out / "pages" / arm / name
            page.parent.mkdir(parents=True, exist_ok=True)
            build_source(
                version.directory, out / "state" / arm, named_source(name), page
            )
    before = load_average()
    walls = {key: [] for key in pages}
    for run in range(RUNS):
        for name in PAGES:
            for arm, version in arms.items():
                click.echo(f"run {run + 1}/{RUNS} {name} {arm}", err=True)
                started = time.perf_counter()
                run_leaf(
                    version.directory, out / "state" / arm,
                    "page", "check", str(pages[arm, name]), "--render", check=True,
                )  # fmt: skip
                walls[arm, name].append(time.perf_counter() - started)
    click.echo(describe(arms))
    click.echo(f"load average {before} before, {load_average()} after")
    click.echo(f"wall seconds, median (min-max) of {RUNS} runs\n")
    click.echo("| page | base | head | change |\n|---|---:|---:|---:|")
    for name in PAGES:
        base_walls, head_walls = walls["base", name], walls["head", name]
        change = statistics.median(head_walls) - statistics.median(base_walls)
        click.echo(
            f"| {name} | {spread(base_walls)} | {spread(head_walls)} | {change:+.2f} |"
        )
    click.echo(f"files in {out}")
