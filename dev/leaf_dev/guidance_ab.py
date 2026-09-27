"""Score a guidance change: the cases in `evals/` on the base's guidance and on the
working tree's, run together, read into one table and a Record row.

    uv run leaf-dev guidance-ab pin-takes-no-page-room --runs 1

Both arms are built outside the checkout, since `claude plugin eval` loads every plugin
and case below its target: an arm under `.tmp/`, or the checkout itself with arms in
its `.tmp/`, would run a second leaf. The base is the payload at `--base`, the merge
base with `main` by default. The candidate is the payload as the working tree has it,
uncommitted and untracked files included (`leaf_dev.harness.build_arm`), so it holds
exactly what the base holds and nothing else of the checkout.

Both arms get the same cases: the working tree's case directories whose names match a
CASE glob, or every case. Copying them in, rather than passing `--case`, lets several
globs select, and puts a case newer than the base on the base too.

Both runs start at once, with `evals/README.md`'s flags, since batches an hour apart
drift. Each runs in a process group of its own, which its `claude -p` children join,
and however this command stops, SIGTERM included, it stops both groups, since those
children bill while they run. Each run's `aggregate-result.json`, `report.html` and
log stay in a directory of their own under `.tmp/guidance-ab/`; the arms are deleted.

A case's count on an arm is the runs `claude plugin eval` passed, and it names the runs
that errored, such as on a rate limit or a timeout, since those measured nothing about
the guidance. A run stopped early (the aggregate's `partial`) is warned about. The
cost is the children's and the judges', which the aggregate's `costUsd` leaves out.

The Record row it prints leaves "Tried" for the author and states the result as counts,
which the author rewrites as what the runs did.
"""

import fnmatch
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.harness import build_arm, copy_working, environment, merge_base

OUT = ROOT / ".tmp" / "guidance-ab"
ARMS = ("base", "candidate")
FLAGS = (
    "--no-publish", "--ablation", "none", "--trust-plugin", "--judge-model", "opus",
    "-j", "8", "--allow-tools", "Skill", "Read",
)  # fmt: skip
# How long a stopped run's process group gets to exit before it is killed.
GRACE_SECONDS = 10


def select_cases(globs: tuple[str, ...]) -> list[str]:
    """The working tree's case names matching any of `globs`, or all of them."""
    cases = sorted(path.parent.name for path in (ROOT / "evals").glob("*/case.yaml"))
    for glob in globs:
        if not fnmatch.filter(cases, glob):
            raise click.BadParameter(f"no case matches {glob!r}", param_hint="CASE")
    return [c for c in cases if not globs or any(fnmatch.fnmatch(c, g) for g in globs)]


def run_together(runs: list[tuple[list[str], Path, Path]]) -> None:
    """Start each (command, cwd, log) at once in a session of its own and wait for all.

    If this process stops first, by an error, Ctrl-C or SIGTERM, each command still
    running has its whole process group stopped: SIGTERM, then SIGKILL after
    GRACE_SECONDS."""
    procs = []
    previous = signal.signal(signal.SIGTERM, lambda *_: sys.exit(128 + signal.SIGTERM))
    try:
        for command, cwd, log in runs:
            with log.open("w") as stream:
                procs.append(
                    subprocess.Popen(
                        command,
                        cwd=cwd,
                        env=environment(),
                        stdin=subprocess.DEVNULL,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                )
        for proc in procs:
            proc.wait()
    finally:
        signal.signal(signal.SIGTERM, previous)
        for proc in procs:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()


def read_run(out: Path) -> tuple[dict[str, list[dict]], float]:
    """Each case's runs and the run's whole cost, from one arm's results."""
    result_file = out / "aggregate-result.json"
    if not result_file.exists():
        log = (out / "run.log").read_text().strip().splitlines()
        raise click.ClickException(
            f"{out.name} wrote no results; the end of {out / 'run.log'}:\n"
            + "\n".join(log[-20:])
        )
    result = json.loads(result_file.read_text())
    if result["partial"]:
        click.echo(f"warning: {out.name} stopped early; its results are partial")
    runs = {case["name"]: case["arms"]["with"] for case in result["cases"]}
    judges = sum(run["judgeCostUsd"] or 0 for rs in runs.values() for run in rs)
    return runs, result["costUsd"] + judges


def of(runs: list[dict]) -> str:
    """A case's passes on one arm, naming the runs that errored."""
    count = f"{sum(run['passed'] for run in runs)} of {len(runs)}"
    errored = sum(run["error"] is not None for run in runs)
    return f"{count} ({errored} errored)" if errored else count


@click.command("guidance-ab")
@click.argument("case_globs", metavar="[CASE]...", nargs=-1)
@click.option("--base", "base_ref", help="The base ref; the merge base with main.")
@click.option("--runs", type=int, help="Runs per case; each case's own, or 3.")
def guidance_ab(case_globs: tuple[str, ...], base_ref: str | None, runs: int | None):
    """Run the eval cases matching the CASE globs, or all of them, on the base's
    guidance and the working tree's at once, and print each case's passes per arm."""
    cases = select_cases(case_globs)
    started = datetime.now().astimezone()
    OUT.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix=f"{started:%Y%m%d-%H%M%S}-", dir=OUT))
    with tempfile.TemporaryDirectory(prefix="leaf-guidance-ab-") as built:
        arms = {arm: Path(built) / arm for arm in ARMS}
        commits = {
            "base": build_arm(base_ref or merge_base(), arms["base"]),
            "candidate": build_arm(None, arms["candidate"]),
        }
        click.echo(f"base       {commits['base'][:9]}")
        click.echo(f"candidate  the working tree on {commits['candidate'][:9]}")
        for arm, arm_dir in arms.items():
            copy_working([f"evals/{case}" for case in cases], arm_dir)
            (out / arm).mkdir()
        click.echo(f"running both arms; their logs and results go under\n{out}")
        run_together(
            [
                (
                    ["claude", "plugin", "eval", str(arm_dir), *FLAGS]
                    + ["--output-dir", str(out / arm)]
                    + ["--report", str(out / arm / "report.html")]
                    + (["--runs", str(runs)] if runs else []),
                    arm_dir,
                    out / arm / "run.log",
                )
                for arm, arm_dir in arms.items()
            ]
        )
    results, cost = {}, 0.0
    for arm in ARMS:
        results[arm], arm_cost = read_run(out / arm)
        cost += arm_cost
    rows = [(case, *(of(results[arm].get(case, [])) for arm in ARMS)) for case in cases]
    widths = [max(len(row[i]) for row in [("case", *ARMS), *rows]) for i in range(2)]
    click.echo()
    for case, base, candidate in [("case", *ARMS), *rows]:
        click.echo(f"{case:<{widths[0]}}  {base:<{widths[1]}}  {candidate}")
    click.echo(f"\ncost ${cost:.2f}")
    for arm in ARMS:
        click.echo(f"{arm} report:\nfile://{out / arm / 'report.html'}")
    named = ", ".join(f"`{case}`" for case in cases) if case_globs else "All cases"
    per_case = {len(v) for arm in ARMS for v in results[arm].values()}
    times = f" ×{per_case.pop()} per arm" if len(per_case) == 1 else ""
    measured = f"{named}{times}; base at {commits['base'][:9]}, candidate the working "
    measured += "tree, run together"
    result = "; ".join(
        f"`{case}` {base} to {candidate}" for case, base, candidate in rows
    )
    click.echo(f"\n| {started:%m-%d} |  | {measured} | {result}. ${cost:.2f} |")
