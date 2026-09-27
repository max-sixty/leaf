"""Run a selection of the suite in a checkout and read what each test did.

`leaf-dev flake` and `leaf-dev bugback` judge tests by running them; both read a run
here, the same way.

A selection is pytest node ids. `collect` expands it to the items it names and refuses
one pytest would not run: a usage error, a collection error, or a selection of
nothing. One path that does not exist makes pytest collect nothing from every path
and exit 4, and piped or summarized, that reads as a run with no failures. `present`
collects leniently instead, for a tree a mutation may have broken: it sorts items into
those that still collect, those whose module or class no longer imports (`error`),
and those that are gone (`vanished`), so one broken file costs only its own tests.

`run` runs the selection under pytest-reportlog, carrying on past collection errors,
and reads each item's outcome from that log rather than the terminal, by phase:

    failed           its call failed: the test itself went red
    error            its setup failed, its collector could not import, or its
                     worker crashed: red, but not by the test's own assertion
    teardown-failed  its call passed and its teardown failed
    passed, skipped  (an xfail is skipped; a strict xpass is failed)
    hung             unreported when the run passed `TIMEOUT` and was stopped
    not run          unreported by a run that ended early; the message says why

A message leads with the last line under `tests/` the failure passed through, which
says which arm of a test walking several routes failed.

A run takes the suite's own configuration and only the flags its caller adds, and two
flags that look harmless break it. `-p no:cacheprovider` removes the `--lf` option
`tests/conftest.py` reads, so every worker dies at collection; `-o cache_dir=…` keeps
a run out of `.pytest_cache` instead. `--basetemp` buys nothing, since pytest locks a
live run's directory, and inside a checkout it turns fixtures into payload.

Each run is `uv run --frozen pytest` in the checkout, so a checkout without an
environment gets its own from its lock, and each runs in a session of its own. A run
is stopped the way a terminal stops one, SIGINT to its process group, so pytest runs
its fixtures' teardowns and Playwright closes its browsers; whatever outlives `GRACE`
is killed. A command runs inside `stoppable()`, which turns SIGTERM and SIGINT into
that stop for every live run before it exits, so its own cleanup runs and no pytest
or browser tree outlives it. `TaskStop` sends SIGTERM and then, about a second and a
half later, SIGKILL to the whole process tree, sessions of its own included: the runs
die with the command, and only cleanup the command owed its files is lost.
"""

import json
import os
import re
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click

# A run still going after this long is stopped and its unreported items are `hung`.
# Generous: a whole browser file on a loaded machine takes minutes, not this.
TIMEOUT = 20 * 60
# How long a stopped run has for its teardowns before its process group is killed.
GRACE = 30


@dataclass(frozen=True)
class Outcome:
    result: str
    message: str = ""


# Set once the command is stopping: every run in progress stops too.
STOPPING = threading.Event()


@contextmanager
def stoppable():
    """Turn SIGTERM and SIGINT into stopping every run, then exiting 143 or 130
    through the caller's own cleanup. The runs sit in sessions of their own, so no
    signal reaches them unless it comes from here."""

    def stop(signum, frame):
        STOPPING.set()
        raise SystemExit(128 + signum)

    previous = {s: signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)


def pytest(root: Path, *args: str, out: Path, env: dict | None = None) -> int | None:
    """Run the pytest of the checkout `root` there, its terminal output to `out`;
    return its exit status, or None when it passed `TIMEOUT` or the command is
    stopping. `env` adds to this process's environment."""
    # The caller's own `uv run` names its environment, which is not a scratch
    # checkout's; uv would warn about it on every run and use the checkout's anyway.
    base = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    deadline = time.monotonic() + TIMEOUT
    with out.open("w") as stream:
        proc = subprocess.Popen(
            ["uv", "run", "--frozen", "pytest", "--color=no", *args],
            cwd=root,
            env={**base, **(env or {})},
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            while not STOPPING.is_set() and time.monotonic() < deadline:
                try:
                    return proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            return None
        finally:
            stop(proc)


def stop(proc: subprocess.Popen) -> None:
    """End a run and everything in its process group: SIGINT, then after `GRACE`,
    SIGKILL, which also takes any process a finished run left behind."""
    if proc.poll() is None:
        signal_group(proc.pid, signal.SIGINT)
        try:
            proc.wait(GRACE)
        except subprocess.TimeoutExpired:
            pass
    signal_group(proc.pid, signal.SIGKILL)
    proc.wait()


def signal_group(pgid: int, signum: int) -> None:
    try:
        os.killpg(pgid, signum)
    except ProcessLookupError:
        pass


def read_log(log: Path) -> list[dict]:
    return (
        [json.loads(line) for line in log.read_text().splitlines()]
        if log.exists()
        else []
    )


def collect_errors(records: list[dict], root: Path) -> dict[str, str]:
    """Each collector that failed, by node id, with its message."""
    return {
        r["nodeid"]: crash(r["longrepr"], root)
        for r in records
        if r["$report_type"] == "CollectReport" and r["outcome"] == "failed"
    }


def listed(out: Path) -> list[str]:
    """The node ids a `--collect-only -q` run printed, one a line."""
    return [
        line
        for line in out.read_text().splitlines()
        if (path := line.partition("::")[0]).endswith(".py") and " " not in path
    ]


def collect(root: Path, selection: tuple[str, ...], out: Path) -> list[str]:
    """The node ids of the items `selection` names in `root`, refusing a selection
    pytest would not run whole."""
    status = pytest(root, "--collect-only", "-q", "-n0", *selection, out=out)
    items = listed(out)
    if status != 0 or not items:
        raise click.ClickException(
            f"pytest will not run {' '.join(selection)} (exit {status}):\n"
            f"{out.read_text()[-2000:]}"
        )
    return items


def present(
    root: Path, items: list[str], out: Path
) -> tuple[list[str], dict[str, Outcome]]:
    """Which of `items` still collect in `root`, and the outcome of each that does
    not: `error` where its module or class fails to collect, `vanished` where it is
    gone, or `not run`, for all of them, where pytest cannot start at all."""
    files = sorted({item.partition("::")[0] for item in items})
    existing = [f for f in files if (root / f).exists()]
    log = out.with_suffix(".jsonl")
    status = (
        pytest(
            root,
            "--collect-only",
            "-q",
            "-n0",
            "--continue-on-collection-errors",
            f"--report-log={log}",
            *existing,
            out=out.with_suffix(".log"),
        )
        if existing
        else 5
    )
    if status not in (0, 1, 2, 5):
        why = f"collection exited {status}; see {out.with_suffix('.log')}"
        return [], {item: Outcome("not run", why) for item in items}
    found = set(listed(out.with_suffix(".log"))) if existing else set()
    errors = collect_errors(read_log(log), root)
    kept, lost = [], {}
    for item in items:
        broken = [
            m for n, m in errors.items() if item == n or item.startswith(n + "::")
        ]
        if item in found:
            kept.append(item)
        elif broken:
            lost[item] = Outcome("error", broken[0])
        else:
            lost[item] = Outcome("vanished", "no longer collected")
    return kept, lost


def run(
    root: Path,
    selection: tuple[str, ...],
    items: list[str],
    out: Path,
    *args: str,
    env: dict | None = None,
) -> dict[str, Outcome]:
    """Run `selection` in `root` and return each of `items`' outcome. `out` names
    the run: its terminal output is `out.log` and its report log `out.jsonl`."""
    log = out.with_suffix(".jsonl")
    status = pytest(
        root,
        f"--report-log={log}",
        "--continue-on-collection-errors",
        *args,
        *selection,
        out=out.with_suffix(".log"),
        env=env,
    )
    records = read_log(log)
    reports = [r for r in records if r["$report_type"] == "TestReport"]
    errors = collect_errors(records, root)

    def unreported(item: str) -> Outcome:
        broken = [
            m for n, m in errors.items() if item == n or item.startswith(n + "::")
        ]
        if broken:
            return Outcome("error", broken[0])
        if status is None:
            return Outcome("hung", f"stopped after {TIMEOUT}s")
        return Outcome("not run", f"pytest exited {status}; see {out.with_suffix('.log')}")  # fmt: skip

    return {
        item: outcome([r for r in reports if r["nodeid"] == item], root)
        or unreported(item)
        for item in items
    }


def outcome(reports: list[dict], root: Path) -> Outcome | None:
    """One item's outcome from its reports, one per phase it reached; None when it
    has none."""
    phases = {r["when"]: r for r in reports}
    # `???` is xdist's report for a worker that crashed under the item.
    if broken := next((r for r in reports if r["when"] in ("setup", "???") and r["outcome"] == "failed"), None):  # fmt: skip
        return Outcome("error", crash(broken["longrepr"], root))
    call = phases.get("call")
    if call and call["outcome"] == "failed":
        return Outcome("failed", crash(call["longrepr"], root))
    teardown = phases.get("teardown")
    if call and call["outcome"] == "passed":
        if teardown and teardown["outcome"] == "failed":
            return Outcome("teardown-failed", crash(teardown["longrepr"], root))
        return Outcome("passed")
    skipped = any(r["outcome"] == "skipped" for r in reports)
    return Outcome("skipped") if skipped else None


def crash(longrepr, root: Path) -> str:
    """What a failure report leads with: the exception's message, after the last
    line under `tests/` it passed through; or, for a report pytest keeps only as
    text, its last line, without the terminal colors a collection error keeps."""
    if not (isinstance(longrepr, dict) and longrepr.get("reprcrash")):
        return re.sub(r"\x1b\[[0-9;]*m", "", str(longrepr)).strip().splitlines()[-1]
    root = root.resolve()
    # pytest writes a path relative to its own cwd, the run's root, where it can.
    places = [
        f"{path.relative_to(root)}:{where['lineno']}"
        for entry in longrepr["reprtraceback"]["reprentries"]
        if (where := entry["data"].get("reprfileloc"))
        and (path := (root / where["path"]).resolve()).is_relative_to(root / "tests")
    ]
    message = longrepr["reprcrash"]["message"]
    return f"{places[-1]}: {message}" if places else message
