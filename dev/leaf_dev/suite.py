"""Run a selection of the suite in a checkout and read what each test did.

`leaf-dev flake` and `leaf-dev bugback` run tests here; `leaf-dev ci-failures` reads
CI's reports with the same `read_junit`.

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
    # No path in the message, so `flake`'s copies that ended alike group as one.
    missing = Outcome("not run", f"not in the report (pytest exited {status})")
    # A module that did not import is reported under its path.
    return {
        item: outcomes.get(item) or outcomes.get(item.partition("::")[0], missing)
        for item in items
    }


def read_junit(report: Path) -> dict[str, Outcome]:
    """Each test's outcome in a junit report, by pytest node id. The suite has no test
    classes, so a case's dotted `classname` is its module's path; a collection error
    has none, and is keyed by its module's path."""
    outcomes: dict[str, Outcome] = {}
    for case in ET.parse(report).iter("testcase"):
        classname, name = case.get("classname", ""), case.get("name", "")
        nodeid = (
            f"{classname.replace('.', '/')}.py::{XDIST_GROUP.sub('', name)}"
            if classname
            else f"{name.replace('.', '/')}.py"
        )
        if bad := [e for e in case if e.tag in ("failure", "error")]:
            result = "failed" if bad[0].tag == "failure" else "error"
            outcome = Outcome(result, message(bad[0]))
        elif case.find("skipped") is not None:
            outcome = Outcome("skipped")
        else:
            outcome = Outcome("passed")
        # A failed call's teardown error comes as a second case; the call's reading
        # stands, and the error replaces only a pass or a skip.
        if nodeid not in outcomes or outcomes[nodeid].result in ("passed", "skipped"):
            outcomes[nodeid] = outcome
    return outcomes


def message(failure: ET.Element) -> str:
    """A failure's message, after the last line under `tests/` its traceback names.
    pytest writes that path absolute when the test has changed directory."""
    places = re.findall(
        r"(?:^|/)(tests/\S+?\.py:\d+):", failure.text or "", re.MULTILINE
    )
    text = failure.get("message", "")
    return f"{places[-1]}: {text}" if places else text
