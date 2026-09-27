"""Read what failed in a commit's `ci` runs, and whether each failure also fails where
the commit branched from `main`.

    uv run leaf-dev ci-failures [REF]
    uv run leaf-dev ci-failures --run RUN_ID

A branch may land red only when every failure also fails on its merge base with `main`
under the same CI job, with the base SHA's own run as the control
(`.claude/skills/developing-leaf/SKILL.md`, "Land a change"). This command makes that
comparison for REF (default HEAD). The branch's reading is every `ci` run GitHub holds
for REF's SHA, a pull request's included; the base's excludes pull-request runs, which
test a merge commit rather than the SHA they are filed under. A pull-request run merges
REF into `main` as it stood when the run started, so a failure `main` gained after the
merge base reads as the branch's own: the comparison errs toward blocking.

Each job's reading is its newest attempt in the newest run that reached a result, or
one still running if that is newer. A job passed or failed; a cancelled job that held a
runner stopped partway, at its timeout or by hand, and failed; a skipped job, or a
cancelled one that never got a runner (main's superseded `nightly`), has no result.

A failure is named by its canonical form where CI records one: a test by its pytest
node id, read from the junit report the job uploaded, whose artifact name carries the
job's pytest selection, run id and attempt (`RESULTS`). Every other failed step is
`step: NAME`, so a red lint, bundle check, runtime fold or website build never reads as
green, and a failed job that names no step is `job: NAME`. The steps after the first
failure run only on success, so when a job's tests fail its first failed step is theirs
and they stand in for it. Reports are cached under `.tmp/ci-failures/`. GitHub keeps
them 30 days, and a base job whose report is gone cannot place a test.

The report is a table of jobs, a table of failures with each one's outcome on both
sides, and a verdict. `clear` exits 0, noting the steps the branch's failure kept from
running. `blocked` exits 1, for each branch failure the base did not also fail: one it
passed or never had is the branch's own, and one it did not read leaves no control,
whether the base skipped it (the website steps run only for a pull request), holds no
report for it, is still running, or has no result for its job. Main holds one `nightly`
slot, so a base may have no nightly result; the verdict then prints the dispatch that
makes one. `waiting`, on a branch job still running, exits 1 too. `--run` reads one run
alone, and so does a REF already on `main`, whose merge base is itself.
"""

import io
import json
import os
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from functools import cached_property

import click

from leaf_dev import ROOT
from leaf_dev.harness import merge_base

OUT = ROOT / ".tmp" / "ci-failures"
# `gh api` fills the owner and repository from the checkout's remote.
REPO = "repos/{owner}/{repo}"
WORKFLOW = "ci.yaml"
# The pytest selection each `ci.yaml` job names its junit artifact after:
# `pytest-results-<selection>-<run id>-<attempt>`.
RESULTS = {"test": "everyday", "nightly": "nightly"}

PASSED, FAILED, RUNNING, NO_RESULT = "passed", "failed", "running", "no result"
STEP_FAILED = {"failure", "timed_out", "cancelled"}
STEP_OUTCOME = {
    "success": PASSED,
    "skipped": "skipped",
    **dict.fromkeys(STEP_FAILED, FAILED),
}
# The verdict for a branch failure, by the base's outcome for it.
BLOCKED = {
    PASSED: "only on the branch",
    "absent": "only on the branch",
    "skipped": "the base skipped",
    "unknown": "the base holds no test report for",
    RUNNING: "still running on the base",
    NO_RESULT: "with no base result",
}


def gh_api(path: str) -> bytes:
    proc = subprocess.run(
        ["gh", "api", f"{REPO}/{path}"], cwd=ROOT, capture_output=True, check=False
    )
    if proc.returncode:
        raise click.ClickException(f"gh api {path}: {proc.stderr.decode().strip()}")
    return proc.stdout


def api(path: str) -> dict:
    return json.loads(gh_api(path))


def read_results(artifact: int) -> dict[str, str]:
    """Each test's outcome in one uploaded junit report, keyed by pytest node id. The
    suite has no test classes, so a case's dotted `classname` is its module's path."""
    report = OUT / f"{artifact}.xml"
    if not report.exists():
        with zipfile.ZipFile(
            io.BytesIO(gh_api(f"actions/artifacts/{artifact}/zip"))
        ) as z:
            (member,) = z.namelist()
            OUT.mkdir(parents=True, exist_ok=True)
            partial = report.with_suffix(f".{os.getpid()}")
            partial.write_bytes(z.read(member))
            partial.replace(report)
    outcomes: dict[str, str] = {}
    for case in ET.parse(report).iter("testcase"):
        test = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name')}"
        if case.find("failure") is not None or case.find("error") is not None:
            outcomes[test] = FAILED
        elif outcomes.get(test) != FAILED:
            outcomes[test] = "skipped" if case.find("skipped") is not None else PASSED
    return outcomes


def job_state(job: dict) -> str:
    if job["status"] != "completed":
        return RUNNING
    if job["conclusion"] == "success":
        return PASSED
    if job["conclusion"] in ("failure", "timed_out") or (
        job["conclusion"] == "cancelled" and job["runner_id"]
    ):
        return FAILED
    return NO_RESULT


@dataclass(frozen=True)
class Job:
    """One job's latest attempt in one run."""

    name: str
    run: int
    state: str
    steps: tuple[tuple[str, str], ...]  # (name, conclusion), in order
    results: int | None  # the junit artifact uploaded during the job

    @cached_property
    def tests(self) -> dict[str, str]:
        return read_results(self.results) if self.results else {}

    @cached_property
    def failures(self) -> tuple[str, ...]:
        if self.state != FAILED:
            return ()
        tests = [test for test, outcome in self.tests.items() if outcome == FAILED]
        steps = [f"step: {name}" for name, c in self.steps if c in STEP_FAILED]
        return tuple(tests + steps[1 if tests else 0 :]) or (f"job: {self.name}",)

    @cached_property
    def unchecked(self) -> tuple[str, ...]:
        """The steps the job skipped after its first failure."""
        failed = [i for i, (_, c) in enumerate(self.steps) if c in STEP_FAILED]
        after = self.steps[failed[0] + 1 :] if failed else ()
        return tuple(
            name for name, c in after if c == "skipped" and not name.startswith("Post ")
        )

    def outcome(self, failure: str) -> str:
        """What this job read for a failure named by another reading."""
        if self.state not in (PASSED, FAILED):
            return self.state
        if failure in self.failures:
            return FAILED
        if failure.startswith("step: "):
            return STEP_OUTCOME.get(dict(self.steps).get(failure[6:]), "absent")
        if failure.startswith("job: "):
            return self.state
        if self.results:
            return self.tests.get(failure, "absent")
        return PASSED if self.state == PASSED else "unknown"


def run_jobs(run: dict) -> list[Job]:
    artifacts = {
        a["name"]: a["id"]
        for a in api(f"actions/runs/{run['id']}/artifacts?per_page=100")["artifacts"]
        if not a["expired"]
    }
    return [
        Job(
            name=job["name"],
            run=run["id"],
            state=job_state(job),
            steps=tuple((s["name"], s["conclusion"]) for s in job["steps"]),
            results=artifacts.get(
                f"pytest-results-{RESULTS[job['name']]}-{run['id']}-{job['run_attempt']}"
            )
            if job["name"] in RESULTS
            else None,
        )
        for job in api(f"actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
    ]


def reading(sha: str, *, pull_requests: bool) -> dict[str, Job]:
    """Each job's reading across the `ci` runs for `sha` (module docstring)."""
    runs = api(f"actions/workflows/{WORKFLOW}/runs?head_sha={sha}&per_page=100")
    chosen: dict[str, Job] = {}
    for run in sorted(
        runs["workflow_runs"], key=lambda r: r["created_at"], reverse=True
    ):
        if run["event"] == "pull_request" and not pull_requests:
            continue
        for job in run_jobs(run):
            held = chosen.get(job.name)
            if held is None or (held.state == NO_RESULT and job.state != NO_RESULT):
                chosen[job.name] = job
    return chosen


def rev_parse(ref: str) -> str:
    proc = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        raise click.BadParameter(f"{ref!r} names no commit", param_hint="REF")
    return proc.stdout.strip()


def table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    return "\n".join(
        f"| {' | '.join(row)} |" for row in [header, ("---",) * len(header), *rows]
    )


def cell(job: Job | None) -> str:
    return f"{job.state} · run {job.run}" if job else NO_RESULT


def report_alone(title: str, jobs: dict[str, Job]) -> None:
    click.echo(
        f"{title}\n\n{table(('job', 'result'), [(n, cell(j)) for n, j in jobs.items()])}"
    )
    failures = [(name, f) for name, job in jobs.items() for f in job.failures]
    if failures:
        click.echo(f"\n{table(('job', 'failure'), failures)}")


def compare(sha: str, base: str, branch: dict[str, Job], based: dict[str, Job]) -> bool:
    """Print the comparison; return whether the branch may land."""
    names = list(dict.fromkeys([*branch, *based]))
    click.echo(f"branch {sha[:9]} vs base {base[:9]}, its merge base with main\n")
    jobs = [(n, cell(branch.get(n)), cell(based.get(n))) for n in names]
    click.echo(table(("job", "branch", "base"), jobs))

    # Each branch failure the base did not also fail, by what the base read instead:
    # passed or absent makes it the branch's own; anything else leaves it uncontrolled.
    rows, unmatched, unchecked = [], {}, []
    for name, job in branch.items():
        if job.state not in (PASSED, FAILED):
            continue
        control = based.get(name)
        extra = control.failures if control else ()
        for failure in dict.fromkeys([*job.failures, *extra]):
            there = control.outcome(failure) if control else NO_RESULT
            rows.append((name, failure, job.outcome(failure), there))
            if failure in job.failures and there != FAILED:
                unmatched.setdefault(BLOCKED[there], []).append(failure)
        unchecked += [f"{name}: {step}" for step in job.unchecked]
    if rows:
        click.echo(f"\n{table(('job', 'failure', 'branch', 'base'), rows)}")

    running = [name for name, job in branch.items() if job.state == RUNNING]
    click.echo()
    for verdict, failures in unmatched.items():
        n = f"{len(failures)} failure{'' if len(failures) == 1 else 's'}"
        click.echo(f"blocked: {n} {verdict}")
    if BLOCKED[NO_RESULT] in unmatched:
        ref = f"ci-base-{base[:9]}"
        click.echo(
            "\nRun ci on the base, then read again:\n\n"
            f"```\ngit push origin {base}:refs/heads/{ref}\ngh workflow run ci --ref {ref}\n```"
        )
    if running:
        click.echo(f"waiting: {', '.join(running)} still running on the branch")
    if unmatched or running:
        return False
    if not rows:
        click.echo("clear: no failures")
        return True
    click.echo("clear: every failure also fails on the base")
    if unchecked:
        click.echo(
            f"unchecked, skipped after the branch's failure: {'; '.join(unchecked)}"
        )
    return True


@click.command("ci-failures")
@click.argument("ref", default="HEAD")
@click.option("--run", "run_id", type=int, help="Read this one run instead.")
def ci_failures(ref: str, run_id: int | None) -> None:
    """Compare the `ci` failures at REF (default HEAD) with its merge base's.

    Exits 0 when every failure on the branch also fails on the base, and 1 when one
    does not, whether it passed there or the base never read it, or while a branch
    job is still running."""
    if run_id:
        run = api(f"actions/runs/{run_id}")
        title = (
            f"run {run_id}: {run['event']} {run['head_branch']} {run['head_sha'][:9]}"
        )
        report_alone(title, {job.name: job for job in run_jobs(run)})
        return
    sha, base = rev_parse(ref), merge_base(ref)
    branch = reading(sha, pull_requests=True)
    if not branch:
        raise click.ClickException(f"no ci run for {sha[:9]}; CI runs pushed commits")
    if base == sha:
        report_alone(f"{sha[:9]} is on main", branch)
        return
    if not compare(sha, base, branch, reading(base, pull_requests=False)):
        raise SystemExit(1)
