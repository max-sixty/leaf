"""Score a guidance change: the cases in `evals/` on the base's guidance and on the
working tree's, run together, read into one table.

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

Both runs start at once, with the flags `claude plugin eval` needs here (`FLAGS`,
`/developing-leaf`, "Score a guidance change"), since batches an hour apart
drift. Each runs in a process group of its own, which its `claude -p` children join,
and however the runs or this command end, SIGTERM included, it stops whatever is left
in both groups, since those children bill while they run. Each run's
`aggregate-result.json`, `report.html` and log stay in a directory of their own under
`.tmp/guidance-ab/`; the arms are deleted.

A case's count on an arm is the runs `claude plugin eval` passed, and it names the runs
that errored, such as on a rate limit or a timeout, since those measured nothing about
the guidance. A run stopped early (the aggregate's `partial`) is warned about. The
cost is the children's and the judges', which the aggregate's `costUsd` leaves out.
"""

import fnmatch
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.harness import base_ref, build_arm, copy_working, environment

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

    However it ends, when every command has exited or when this process stops first
    by an error, Ctrl-C or SIGTERM, whatever is left in each command's process group
    is stopped (`stop_group`), since a command may exit before a child it started."""
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
            stop_group(proc)


def stop_group(proc: subprocess.Popen) -> None:
    """Stop every process left in `proc`'s group, whether or not `proc` itself has
    exited: SIGTERM, then SIGKILL for whatever remains after GRACE_SECONDS. The group
    ceases to exist once its last member has exited and been reaped."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        deadline = time.monotonic() + GRACE_SECONDS
        while time.monotonic() < deadline:
            # Reap the leader, whose zombie would keep the group alive.
            proc.poll()
            os.killpg(proc.pid, 0)
            time.sleep(0.1)
        os.killpg(proc.pid, signal.SIGKILL)
    # macOS answers EPERM, rather than ESRCH, for a group whose only members are
    # zombies another process will reap: an orphaned child that has already exited.
    except (ProcessLookupError, PermissionError):
        pass
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
@click.option("--base", help="The base ref; the merge base with origin/main.")
@click.option("--runs", type=int, help="Runs per case; each case's own, or 3.")
def guidance_ab(case_globs: tuple[str, ...], base: str | None, runs: int | None):
    """Score the guidance cases, base vs the working tree.

    Runs the cases in evals/ matching the CASE globs, or all of them, on the guidance
    at --base, else the merge base with origin/main, and the working tree's at once.
    Prints each case's passes per arm and the cost."""
    cases = select_cases(case_globs)
    started = datetime.now().astimezone()
    OUT.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix=f"{started:%Y%m%d-%H%M%S}-", dir=OUT))
    with tempfile.TemporaryDirectory(prefix="leaf-guidance-ab-") as built:
        arms = {arm: Path(built) / arm for arm in ARMS}
        commits = {
            "base": build_arm(base_ref(base), arms["base"]),
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
    for case, before, after in [("case", *ARMS), *rows]:
        click.echo(f"{case:<{widths[0]}}  {before:<{widths[1]}}  {after}")
    click.echo(f"\ncost ${cost:.2f}")
    for arm in ARMS:
        click.echo(f"{arm} report:\nfile://{out / arm / 'report.html'}")
