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
drift. Each run's `aggregate-result.json`, `report.html` and log stay under
`.tmp/guidance-ab/<time>/<arm>/`; the arms are deleted. A run passes when `claude
plugin eval` says it passed, so one that errored counts as a run that did not. The
cost is the children's and the judges', which the aggregate's `costUsd` leaves out.

The Record row it prints leaves "Tried" for the author and states the result as counts,
which the author rewrites as what the runs did.
"""

import fnmatch
import json
import subprocess
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


def select_cases(globs: tuple[str, ...]) -> list[str]:
    """The working tree's case names matching any of `globs`, or all of them."""
    cases = sorted(path.parent.name for path in (ROOT / "evals").glob("*/case.yaml"))
    for glob in globs:
        if not fnmatch.filter(cases, glob):
            raise click.BadParameter(f"no case matches {glob!r}", param_hint="CASE")
    return [c for c in cases if not globs or any(fnmatch.fnmatch(c, g) for g in globs)]


def read_run(out: Path) -> tuple[dict[str, list[bool]], float]:
    """Each case's run verdicts and the run's whole cost, from one arm's results."""
    result_file = out / "aggregate-result.json"
    if not result_file.exists():
        log = (out / "run.log").read_text().strip().splitlines()
        raise click.ClickException(
            f"{out.name} wrote no results; the end of {out / 'run.log'}:\n"
            + "\n".join(log[-20:])
        )
    result = json.loads(result_file.read_text())
    runs = {case["name"]: case["arms"]["with"] for case in result["cases"]}
    judges = sum(run["judgeCostUsd"] or 0 for rs in runs.values() for run in rs)
    return (
        {name: [run["passed"] for run in rs] for name, rs in runs.items()},
        result["costUsd"] + judges,
    )


def of(verdicts: list[bool]) -> str:
    return f"{sum(verdicts)} of {len(verdicts)}"


@click.command("guidance-ab")
@click.argument("case_globs", metavar="[CASE]...", nargs=-1)
@click.option("--base", "base_ref", help="The base ref; the merge base with main.")
@click.option("--runs", type=int, help="Runs per case; each case's own, or 3.")
def guidance_ab(case_globs: tuple[str, ...], base_ref: str | None, runs: int | None):
    """Run the eval cases matching the CASE globs, or all of them, on the base's
    guidance and the working tree's at once, and print each case's passes per arm."""
    cases = select_cases(case_globs)
    started = datetime.now().astimezone()
    out = OUT / f"{started:%Y%m%d-%H%M%S}"
    with tempfile.TemporaryDirectory(prefix="leaf-guidance-ab-") as built:
        arms = {arm: Path(built) / arm for arm in ARMS}
        commits = {
            "base": build_arm(base_ref or merge_base(), arms["base"]),
            "candidate": build_arm(None, arms["candidate"]),
        }
        click.echo(f"base       {commits['base'][:9]}")
        click.echo(f"candidate  the working tree on {commits['candidate'][:9]}")
        procs = {}
        try:
            for arm, arm_dir in arms.items():
                copy_working([f"evals/{case}" for case in cases], arm_dir)
                (out / arm).mkdir(parents=True)
                command = ["claude", "plugin", "eval", str(arm_dir), *FLAGS]
                command += ["--output-dir", str(out / arm)]
                command += ["--report", str(out / arm / "report.html")]
                command += ["--runs", str(runs)] if runs else []
                with (out / arm / "run.log").open("w") as log:
                    procs[arm] = subprocess.Popen(
                        command,
                        cwd=arm_dir,
                        env=environment(),
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
            click.echo(f"running both arms; their logs and results go under\n{out}")
            for proc in procs.values():
                proc.wait()
        finally:
            for proc in procs.values():
                if proc.poll() is None:
                    proc.kill()
    verdicts, cost = {}, 0.0
    for arm in ARMS:
        verdicts[arm], arm_cost = read_run(out / arm)
        cost += arm_cost
    width = max(map(len, cases))
    click.echo(f"\n{'case':<{width}}  {'base':<7}  candidate")
    for case in cases:
        base, candidate = (of(verdicts[arm].get(case, [])) for arm in ARMS)
        click.echo(f"{case:<{width}}  {base:<7}  {candidate}")
    click.echo(f"\ncost ${cost:.2f}")
    for arm in ARMS:
        click.echo(f"{arm} report:\nfile://{out / arm / 'report.html'}")
    named = ", ".join(f"`{case}`" for case in cases) if case_globs else "All cases"
    per_case = {len(v) for arm in ARMS for v in verdicts[arm].values()}
    times = f" ×{per_case.pop()} per arm" if len(per_case) == 1 else ""
    measured = f"{named}{times}; base at {commits['base'][:9]}, candidate the working "
    measured += "tree, run together"
    result = "; ".join(
        f"`{case}` " + " to ".join(of(verdicts[arm].get(case, [])) for arm in ARMS)
        for case in cases
    )
    click.echo(f"\n| {started:%m-%d} |  | {measured} | {result}. ${cost:.2f} |")
