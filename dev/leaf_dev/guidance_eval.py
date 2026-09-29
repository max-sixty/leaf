"""Score a guidance change: `claude plugin eval` on the cases in `evals/`, run at once on
the base's payload and the working tree's, read into one table.

    uv run leaf-dev guidance-eval pin-takes-no-page-room --runs 1

Both arms are built outside the checkout, since `claude plugin eval` loads every plugin
and case below its target. Both get the working tree's case directories matching a
CASE glob, or every case, so a case newer than the base runs on the base too. Each
arm's `aggregate-result.json`, `report.html` and log stay under `.tmp/guidance-eval/`.
"""

import fnmatch
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.harness import base_ref, build_arm, copy_working, environment

OUT = ROOT / ".tmp" / "guidance-eval"
ARMS = ("base", "candidate")
# `/developing-leaf`, "Score a guidance change", says why each is needed.
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


def read_run(out: Path) -> tuple[dict[str, list[dict]], float]:
    """Each case's runs and the run's whole cost, judges included, from one arm."""
    result_file = out / "aggregate-result.json"
    if not result_file.exists():
        raise click.ClickException(
            f"{out.name} wrote no results; see {out / 'run.log'}"
        )
    result = json.loads(result_file.read_text())
    runs = {case["name"]: case["arms"]["with"] for case in result["cases"]}
    judges = sum(run["judgeCostUsd"] or 0 for rs in runs.values() for run in rs)
    return runs, result["costUsd"] + judges


def of(runs: list[dict]) -> str:
    """A case's passes on one arm, naming the runs that errored (a rate limit or a
    timeout), since those measured nothing about the guidance."""
    count = f"{sum(run['passed'] for run in runs)} of {len(runs)}"
    errored = sum(run["error"] is not None for run in runs)
    return f"{count} ({errored} errored)" if errored else count


@click.command("guidance-eval")
@click.argument("case_globs", metavar="[CASE]...", nargs=-1)
@click.option("--base", help="The base ref; the merge base with main.")
@click.option("--runs", type=int, help="Runs per case; each case's own, or 3.")
def guidance_eval(case_globs: tuple[str, ...], base: str | None, runs: int | None):
    """Score the guidance cases, base vs the working tree.

    Runs the cases in evals/ matching the CASE globs, or all of them, on the guidance
    at --base, else the merge base with main, and the working tree's at once.
    Prints each case's passes per arm and the cost."""
    cases = select_cases(case_globs)
    started = datetime.now().astimezone()
    OUT.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix=f"{started:%Y%m%d-%H%M%S}-", dir=OUT))
    with tempfile.TemporaryDirectory(prefix="leaf-guidance-eval-") as built:
        arms = {arm: Path(built) / arm for arm in ARMS}
        commits = {
            "base": build_arm(base_ref(base), arms["base"]),
            "candidate": build_arm(None, arms["candidate"]),
        }
        click.echo(f"base       {commits['base'][:9]}")
        click.echo(f"candidate  the working tree on {commits['candidate'][:9]}")
        click.echo(f"running both arms; their logs and results go under\n{out}")
        procs = []
        for arm, arm_dir in arms.items():
            copy_working([f"evals/{case}" for case in cases], arm_dir)
            (out / arm).mkdir()
            with (out / arm / "run.log").open("w") as log:
                procs.append(
                    subprocess.Popen(
                        ["claude", "plugin", "eval", str(arm_dir), *FLAGS]
                        + ["--output-dir", str(out / arm)]
                        + ["--report", str(out / arm / "report.html")]
                        + (["--runs", str(runs)] if runs else []),
                        cwd=arm_dir,
                        env=environment(),
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                )
        for proc in procs:
            proc.wait()
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
