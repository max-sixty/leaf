"""Run a selection of the suite in a checkout and read what each test did.

`leaf-dev suite flake` and `leaf-dev suite bugback` run tests here, each in a `checkout` of a
`snapshot` of the working tree, and `leaf-dev suite profile` reads a run's junit report
through `junit_cases`.

`collect` expands a selection of pytest node ids to the items it names and refuses one
pytest would not run whole: piped or summarized, a selection that collects nothing
reads as a run with no failures. `run` runs it with pytest's `--junitxml` and reads
each item's outcome from that report rather than the terminal: `passed`, `failed` (its
call failed), `error` (its setup or teardown failed, its module did not import, or its
worker crashed: red, but not by the test's own assertion), `skipped`, or `not run`
when the report does not name it. A failure's message leads with the last line under `tests/` it passed
through, which says which arm of a test walking several routes failed.

Each run is `uv run --frozen pytest` in the checkout, in this command's process group,
so a terminal's Ctrl-C reaches pytest as it would a pytest run by hand, and the
command waits for its teardowns before its own cleanup. Pass only the flags a caller
needs: `-p no:cacheprovider` removes the `--lf` option `tests/conftest.py` reads, so
use `-o cache_dir=…` to keep a run out of `.pytest_cache`.
"""

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import copy_working

# xdist's `loadgroup` appends `@<group>` to the node id of a test in an xdist_group.
XDIST_GROUP = re.compile(r"@[^@\]]+$")


@dataclass(frozen=True)
class Outcome:
    result: str
    message: str = ""


def pytest(root: Path, *args: str, out: Path) -> int:
    """Run the pytest of the checkout `root` there, its terminal output to `out`, and
    return its exit status."""
    # The caller's own `uv run` names its environment, which is not a scratch
    # checkout's; uv would warn about it on every run and use the checkout's anyway.
    # `FORCE_COLOR` would color the report's tracebacks despite `--color=no`.
    drop = {"VIRTUAL_ENV", "FORCE_COLOR"}
    env = {k: v for k, v in os.environ.items() if k not in drop}
    with out.open("w") as stream:
        proc = subprocess.Popen(
            ["uv", "run", "--frozen", "pytest", "--color=no", *args],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        try:
            return proc.wait()
        except KeyboardInterrupt:
            # The Ctrl-C reached pytest too; let it finish its teardowns.
            proc.wait()
            raise


def clone(source: Path, dest: Path, *options: str) -> None:
    """Clone `source` into `dest` for a command to remove when it ends. The clone
    starts no background git work, which would go on writing into it after the
    command began removing it: no maintenance after a commit (a commit graph, under
    git 2.56) and no file-system monitor."""
    subprocess.run(
        ["git", "clone", "-q", *options, "-c", "maintenance.auto=false"]
        + ["-c", "core.fsmonitor=false", source, dest],
        check=True,
    )


def snapshot(dest: Path) -> None:
    """Make `dest` a clone of this repository whose HEAD is a commit of the working
    tree as it stands, uncommitted edits included (`arms.copy_working`), for the
    checkouts a command runs the suite in (`checkout`). A run in one sees no edit made
    after the snapshot, and git there can compare or restore its paths against
    another commit."""
    clone(ROOT, dest, "--no-checkout")
    copy_working((".",), dest)
    subprocess.run(["git", "-C", dest, "add", "--all"], check=True)
    subprocess.run(
        [
            "git", "-C", dest, "-c", "core.hooksPath=/dev/null",
            "-c", "commit.gpgsign=false", "-c", "user.name=Leaf snapshot",
            "-c", "user.email=snapshot@localhost",
            "commit", "-q", "--allow-empty", "-m", "Working tree snapshot",
        ],
        check=True,
    )  # fmt: skip


def checkout(snapshot: Path, dest: Path) -> None:
    """Make `dest` a checkout of `snapshot` the suite can run in: a clone, with each of
    this working tree's installed Node dependency directories (`node_modules`), which
    git does not hold and the tests read, linked in as shared inputs."""
    clone(snapshot, dest)
    ignored = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "-z", "--others", "--ignored"]
        + ["--directory", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    for name in ignored:
        if (dependency := Path(name.rstrip("/"))).name == "node_modules":
            (dest / dependency).symlink_to(ROOT / dependency, target_is_directory=True)


def collect(root: Path, selection: tuple[str, ...], out: Path) -> list[str]:
    """The node ids of the items `selection` names in `root`, refusing a selection
    pytest would not run whole."""
    status = pytest(root, "--collect-only", "-q", "-n0", *selection, out=out)
    items = [
        line
        for line in out.read_text().splitlines()
        if (path := line.partition("::")[0]).endswith(".py") and " " not in path
    ]
    if status != 0 or not items:
        raise click.ClickException(
            f"pytest will not run {' '.join(selection)} (exit {status}):\n"
            f"{out.read_text()[-2000:]}"
        )
    return items


def run(
    root: Path, selection: tuple[str, ...], items: list[str], out: Path, *args: str
) -> dict[str, Outcome]:
    """Run `selection` in `root` and return each of `items`' outcome. `out` names the
    run: its terminal output is `out.log` and its report `out.xml`."""
    report = out.with_suffix(".xml")
    status = pytest(
        root, f"--junitxml={report}", *args, *selection, out=out.with_suffix(".log")
    )
    outcomes = read_junit(report) if report.exists() else {}
    # No path in the message, so `suite flake`'s copies that ended alike group as one.
    missing = Outcome("not run", f"not in the report (pytest exited {status})")
    # A module that did not import is reported under its path.
    return {
        item: outcomes.get(item) or outcomes.get(item.partition("::")[0], missing)
        for item in items
    }


def junit_cases(report: Path) -> dict[str, list[ET.Element]]:
    """Each test in a junit report, by pytest node id, with its cases in report
    order: one, or two where a failed call's teardown also failed. The suite has no
    test classes, so a case's dotted `classname` is its module's path; a collection
    error has none, and is keyed by its module's path."""
    tests: dict[str, list[ET.Element]] = {}
    for case in ET.parse(report).iter("testcase"):
        classname, name = case.get("classname", ""), case.get("name", "")
        nodeid = (
            f"{classname.replace('.', '/')}.py::{XDIST_GROUP.sub('', name)}"
            if classname
            else f"{name.replace('.', '/')}.py"
        )
        tests.setdefault(nodeid, []).append(case)
    return tests


def read_junit(report: Path) -> dict[str, Outcome]:
    """Each test's outcome in a junit report, by pytest node id (`junit_cases`)."""
    return {nodeid: outcome(cases) for nodeid, cases in junit_cases(report).items()}


def outcome(cases: list[ET.Element]) -> Outcome:
    """One test's outcome from its cases. Of a failed call and its teardown's error,
    the call's reading stands; an error replaces only a pass or a skip."""
    reading = Outcome("passed")
    for case in cases:
        if reading.result not in ("passed", "skipped"):
            break
        if bad := [e for e in case if e.tag in ("failure", "error")]:
            result = "failed" if bad[0].tag == "failure" else "error"
            reading = Outcome(result, message(bad[0]))
        elif case.find("skipped") is not None:
            reading = Outcome("skipped")
        else:
            reading = Outcome("passed")
    return reading


def message(failure: ET.Element) -> str:
    """A failure's message, after the last line under `tests/` its traceback names.
    pytest writes that path absolute when the test has changed directory."""
    places = re.findall(
        r"(?:^|/)(tests/\S+?\.py:\d+):", failure.text or "", re.MULTILINE
    )
    text = failure.get("message", "")
    return f"{places[-1]}: {text}" if places else text
