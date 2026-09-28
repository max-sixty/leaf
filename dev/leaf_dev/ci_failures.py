"""Say whether a branch may land with a red `ci`: every failure also fails on its base.

    uv run leaf-dev ci-failures [REF]

REF (default HEAD) is compared with its merge base with the local `main`, the base
SHA's own `ci` runs as the control (`.claude/skills/developing-leaf/SKILL.md`, "Land a
change"). For each SHA, a job's reading is its latest attempt in the newest run that
did not skip it. A job's failures are the pytest node ids in the junit report it
uploads as `pytest-results-<job>-<run id>-<attempt>` (`.github/workflows/ci.yaml`).

`clear` (exit 0) when every branch job that failed failed only with pytest ids that
also fail in the base's same job. Anything else — a failed step with no pytest ids, a
missing report, a cancelled or still-running job, no base result — is `not clear`
(exit 1), and each such job is listed with its links. A REF on `main` is its own merge
base, so every failed job is listed.
"""

import io
import json
import subprocess
import zipfile

import click

from leaf_dev import ROOT
from leaf_dev.harness import merge_base
from leaf_dev.suite import read_junit

OUT = ROOT / ".tmp" / "ci-failures"
# `gh api` fills the owner and repository from the checkout's remote.
REPO = "repos/{owner}/{repo}"


def gh_api(path: str) -> bytes:
    proc = subprocess.run(
        ["gh", "api", f"{REPO}/{path}"], cwd=ROOT, capture_output=True, check=False
    )
    if proc.returncode:
        raise click.ClickException(f"gh api {path}: {proc.stderr.decode().strip()}")
    return proc.stdout


def api(path: str) -> dict:
    return json.loads(gh_api(path))


def jobs(sha: str) -> dict[str, dict]:
    """Each `ci` job's latest attempt in the newest run for `sha` that did not skip
    it, by name."""
    runs = api(f"actions/workflows/ci.yaml/runs?head_sha={sha}&per_page=100")
    chosen: dict[str, dict] = {}
    for run in sorted(
        runs["workflow_runs"], key=lambda r: r["created_at"], reverse=True
    ):
        for job in api(f"actions/runs/{run['id']}/jobs?per_page=100")["jobs"]:
            if job["conclusion"] != "skipped":
                chosen.setdefault(job["name"], job)
    return chosen


def failures(job: dict | None) -> set[str]:
    """The pytest ids a failed job's report names as failing, or none."""
    if not job or job["conclusion"] != "failure":
        return set()
    name = f"pytest-results-{job['name']}-{job['run_id']}-{job['run_attempt']}"
    listed = api(f"actions/runs/{job['run_id']}/artifacts?name={name}")["artifacts"]
    live = [a["id"] for a in listed if not a["expired"]]
    if not live:
        return set()
    report = OUT / f"{live[0]}.xml"
    if not report.exists():
        with zipfile.ZipFile(
            io.BytesIO(gh_api(f"actions/artifacts/{live[0]}/zip"))
        ) as z:
            OUT.mkdir(parents=True, exist_ok=True)
            report.write_bytes(z.read(z.namelist()[0]))
    return {
        test
        for test, outcome in read_junit(report).items()
        if outcome.result in ("failed", "error")
    }


def state(job: dict | None) -> str:
    if job is None:
        return "no result"
    reading = job["conclusion"] or job["status"]
    if reading == "cancelled" and not job["runner_id"]:
        # A newer commit replaced it in the queue (running-tend's SKILL.md).
        reading = "cancelled before a runner"
    return f"{reading} {job['html_url']}"


@click.command("ci-failures")
@click.argument("ref", default="HEAD")
def ci_failures(ref: str) -> None:
    """Compare the `ci` failures at REF (default HEAD) with its merge base's.

    Exits 0 when every branch job that failed failed only with pytest ids that also
    fail on the base under the same job; 1 otherwise, listing the jobs to read."""
    proc = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        raise click.BadParameter(f"{ref!r} names no commit", param_hint="REF")
    sha, base = proc.stdout.strip(), merge_base(ref)
    branch = jobs(sha)
    if not branch:
        raise click.ClickException(f"no ci run for {sha[:9]}")
    based = jobs(base) if base != sha else {}
    click.echo(
        f"branch {sha[:9]} vs base {base[:9]}"
        if base != sha
        else f"{sha[:9]} is on main: no base to compare"
    )
    unclear = False
    for name, job in branch.items():
        if job["conclusion"] == "success":
            continue
        control = based.get(name)
        ids, controlled = failures(job), failures(control)
        if ids and ids <= controlled:
            click.echo(f"\n{name}: all {len(ids)} failing tests also fail on the base")
            # The steps after the failed one run only on success.
            steps = job["steps"]
            first = next(i for i, s in enumerate(steps) if s["conclusion"] == "failure")
            unchecked = [
                s["name"]
                for s in steps[first + 1 :]
                if s["conclusion"] == "skipped" and not s["name"].startswith("Post ")
            ]
            if unchecked:
                click.echo(f"  not run on the branch: {'; '.join(unchecked)}")
            continue
        unclear = True
        click.echo(f"\n{name}\n  branch: {state(job)}")
        if base != sha:
            click.echo(f"  base: {state(control)}")
        for test in sorted(ids - controlled):
            click.echo(f"  {test}")
        if not ids and job["conclusion"] == "failure":
            click.echo("  no failing pytest ids: read the log")
        if (
            name == "nightly"
            and base != sha
            and (control is None or control["conclusion"] not in ("success", "failure"))
        ):
            click.echo(
                f"  run nightly on the base: git push origin {base}:refs/heads/"
                f"ci-base-{base[:9]} && gh workflow run ci --ref ci-base-{base[:9]}"
            )
    click.echo("\nnot clear: read the jobs above" if unclear else "\nclear")
    raise SystemExit(1 if unclear else 0)
