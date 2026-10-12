"""Where the Python suite's time goes: recorded during a run, read back after it.

Loaded as a pytest plugin (`-p leaf_dev.suite_profile`, as CI's `test` job loads it),
it gives every test one junit property, `profile`: JSON holding the seconds each
phase took (`setup`, `call`, `teardown`), under `cpu` the CPU seconds the worker and
every process it started used meanwhile, and, under `playwright`, the seconds and
calls the test spent in Playwright's sync API, keyed `"<method> from <caller>"`, the
caller being the first frame outside Playwright. That sync API runs its event loop in
a second greenlet and switches to it for every call, so a sampling profiler, which
reads only the running stack, sees a wait on the browser as an idle event loop with
the waiting test off the stack. Timing each call where the test makes it keeps that
attribution. A call made from a handler's greenlet overlaps the main greenlet's wait
and is not counted.

`cpu` is the measure `tests/AGENTS.md` costs the suite in: the CPU seconds the kernel
charged the worker's cgroup during the test. CI's `test` job delegates a cgroup to the
suite in `SUITE_PROFILE_CGROUP`, and each worker moves into one of its own there before
its first test, so the browsers, driver, servers and commands it starts are charged to
it, including a process that outlives its parent, as a server `leaf server start`
detaches or a closed browser's renderers do. A process serving several tests, such as
a pooled browser, charges each for what it does during it. Without `SUITE_PROFILE_CGROUP`, as on macOS, which
has no cgroups, tests carry no `cpu` and the report ranks by worker time. Summing a
worker's process tree instead lost or recounted a process's CPU whenever it exited,
since only a parent that reaps a child takes over its CPU.

`leaf-dev suite-profile DIR` reads one run's results from DIR and prints where its
CPU and worker time went: the junit report's phases, CPU, files and Playwright calls; py-spy's
sampled stacks (`stacks.txt`), for the suite's own Python by function; and `sa`'s
table of CPU by command (`cpu-by-command.txt`), for the browsers and servers no
Python stack shows. Accounting names a process after the last of its threads to
exit, so Chrome's processes appear under thread names such as `ThreadPoolForeg`, a
Python process that watches files as `notify-rs inoti`, and py-spy as `ctrl-c`. CI writes all three and puts this command's output in the job's
summary.
"""

import json
import os
import re
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import click
import pytest

from leaf_dev import ROOT

PLAYWRIGHT_DIR = f"{os.sep}playwright{os.sep}"
PHASES = ("setup", "call", "teardown")
# py-spy's raw format: one stack per line, `;`-separated frames and its sample count,
# rooted at its process and that process's ancestors, `process PID:"COMMAND LINE"`.
# A command line can hold `;` and newlines, so a record runs to the count that ends
# a line before the next record or the end.
STACK = re.compile(
    r'^(?P<stack>process \d+:".*?) (?P<samples>\d+)$(?=\nprocess \d+:"|\n?\Z)',
    re.MULTILINE | re.DOTALL,
)
PROCESS = re.compile(r'process (\d+):"([^"]*)"')
FRAME = re.compile(r"\S+ \([^()]*:\d+\)")

# The running test's Playwright tally, (method from caller) -> [seconds, calls], or
# None outside a test.
_calls: dict[str, list] | None = None
_phases = pytest.StashKey[dict[str, float]]()


def pytest_configure(config):
    import greenlet
    import playwright
    from playwright._impl._sync_base import SyncBase

    sync = SyncBase._sync

    def timed(self, coro):
        __tracebackhide__ = True
        if _calls is None or greenlet.getcurrent().parent is not None:
            return sync(self, coro)
        start = time.perf_counter()
        try:
            return sync(self, coro)
        finally:
            tally = _calls.setdefault(f"{_method(coro)} from {_caller()}", [0.0, 0])
            tally[0] += time.perf_counter() - start
            tally[1] += 1

    # Playwright attributes each call, in its traces and protocol metadata, to the
    # first frame outside its own package. Filing the wrapper's code under that
    # package keeps the attribution on the caller rather than on this module.
    timed.__code__ = timed.__code__.replace(
        co_filename=str(Path(playwright.__file__).parent / "_suite_profile.py")
    )
    SyncBase._sync = timed


def _method(coro):
    return getattr(coro, "__qualname__", type(coro).__name__)


def _caller():
    frame = sys._getframe(2)
    while frame is not None and PLAYWRIGHT_DIR in frame.f_code.co_filename:
        frame = frame.f_back
    if frame is None:
        return "?"
    path = Path(frame.f_code.co_filename)
    place = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name
    return f"{place}:{frame.f_code.co_qualname}"


# This worker's cgroup, made on its first test under the one CI delegates in
# `SUITE_PROFILE_CGROUP`.
_cgroup: Path | None = None
_cpu = pytest.StashKey[float | None]()


def worker_cpu() -> float | None:
    """CPU seconds this worker's cgroup has used, or None without
    `SUITE_PROFILE_CGROUP`. The first call makes the cgroup and moves the worker into
    it, so every process the worker starts after that is charged to it."""
    global _cgroup
    if (parent := os.environ.get("SUITE_PROFILE_CGROUP")) is None:
        return None
    if _cgroup is None:
        _cgroup = Path(parent) / str(os.getpid())
        _cgroup.mkdir()
        (_cgroup / "cgroup.procs").write_text(str(os.getpid()))
        # A suite a test runs makes its cgroups inside this one, which still counts them.
        os.environ["SUITE_PROFILE_CGROUP"] = str(_cgroup)
    stat = dict(
        line.split() for line in (_cgroup / "cpu.stat").read_text().splitlines()
    )
    return int(stat["usage_usec"]) / 1e6


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item):
    global _calls
    _calls = {}
    item.stash[_cpu] = worker_cpu()
    try:
        return (yield)
    finally:
        _calls = None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    phases = item.stash.setdefault(_phases, {})
    phases[call.when] = round(report.duration, 3)
    if call.when == "teardown":
        playwright = {
            key: [round(seconds, 3), calls]
            for key, (seconds, calls) in sorted((_calls or {}).items())
        }
        profile = {**phases, "playwright": playwright}
        if (start := item.stash[_cpu]) is not None:
            profile["cpu"] = round(worker_cpu() - start, 3)
        report.user_properties.append(("profile", json.dumps(profile)))
    return report


@click.command()
@click.argument(
    "directory", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--rate",
    type=float,
    envvar="PY_SPY_RATE",
    help="py-spy's samples per second in `stacks.txt` (CI's `PY_SPY_RATE`).",
)
@click.option("--top", default=20, show_default=True, help="Rows per table.")
def suite_profile(directory: Path, rate: float | None, top: int) -> None:
    """Print where one suite run's CPU and worker time went, from the results in DIRECTORY:
    `results.xml` with this module's `profile` properties, and, where present,
    py-spy's `stacks.txt` and `sa`'s `cpu-by-command.txt`. CI's `test` job uploads
    all three as its `pytest-results-*` artifact."""
    cases = read_cases(directory / "results.xml")
    report_cases(cases, top)
    if (stacks := directory / "stacks.txt").exists():
        if rate is None:
            raise click.UsageError(
                "stacks.txt needs --rate, the rate py-spy sampled at"
            )
        report_stacks(stacks, rate, top)
    if (cpu := directory / "cpu-by-command.txt").exists():
        lines = cpu.read_text().splitlines()
        section("CPU by command (sa: calls, real and CPU minutes)")
        click.echo("\n".join(lines[: top + 1]))


def read_cases(report: Path) -> list[dict]:
    """Each test case's file, seconds and profile. A failed call whose teardown also
    failed is reported as two cases, the profile on the second; they are one test
    here. A case without a profile, a collection error, has none."""
    cases = {}
    for case in ET.parse(report).iter("testcase"):
        key = (case.get("classname", ""), case.get("name", ""))
        entry = cases.setdefault(
            key,
            {"file": key[0].replace(".", "/") + ".py", "seconds": 0.0, "profile": None},
        )
        entry["seconds"] += float(case.get("time", 0))
        if (prop := case.find("properties/property[@name='profile']")) is not None:
            entry["profile"] = json.loads(prop.get("value"))
    return list(cases.values())


def report_cases(cases: list[dict], top: int) -> None:
    total = sum(c["seconds"] for c in cases)
    profiled = [c["profile"] for c in cases if c["profile"]]
    phases = {p: sum(prof.get(p, 0) for prof in profiled) for p in PHASES}
    waits = sum(s for prof in profiled for s, _ in prof["playwright"].values())
    # A run whose tests carry no CPU, without a cgroup, ranks by worker time instead.
    timed = bool(profiled) and all("cpu" in prof for prof in profiled)
    cpu = sum(prof["cpu"] for prof in profiled) if timed else None
    section(
        f"{len(cases)} tests, {minutes(total)} worker-minutes"
        + (f", {minutes(cpu)} CPU-minutes in the workers' cgroups" if timed else "")
    )
    if profiled:
        click.echo(
            "  ".join(f"{p} {minutes(s)}" for p, s in phases.items())
            + f"  in Playwright {minutes(waits)} ({share(waits, total)})"
        )
    else:
        click.echo(
            "No test carries a `profile` property: the run did not load this plugin."
        )

    by_file = defaultdict(list)
    for case in cases:
        by_file[case["file"]].append(case)
    rows = []
    for name, group in by_file.items():
        seconds = sum(c["seconds"] for c in group)
        profiles = [c["profile"] for c in group if c["profile"]]
        used = sum(p["cpu"] for p in profiles) if timed else 0.0
        setup = sum(p.get("setup", 0) for p in profiles)
        waited = sum(s for p in profiles for s, _ in p["playwright"].values())
        median = statistics.median(c["seconds"] for c in group)
        rows.append(
            (
                used,
                seconds,
                name,
                len(group),
                median,
                share(setup, seconds),
                share(waited, seconds),
            )
        )
    section("By file" + (", most CPU first" if timed else ""))
    table(
        ("CPU min", "minutes", "tests", "median s", "setup", "Playwright", "file"),
        [
            (minutes(c) if timed else "-", minutes(s), n, f"{m:.1f}", su, pw, name)
            for c, s, name, n, m, su, pw in sorted(rows, reverse=True)[:top]
        ],
    )
    if not profiled:
        return

    methods, callers = Counter(), Counter()
    counts = Counter()
    for prof in profiled:
        for key, (seconds, calls) in prof["playwright"].items():
            method = key.split(" from ", 1)[0]
            methods[method] += seconds
            counts[method] += calls
            callers[key] += seconds
    section("Playwright by method")
    table(
        ("minutes", "calls", "ms/call", "method"),
        [
            (minutes(s), counts[m], f"{1000 * s / counts[m]:.0f}", m)
            for m, s in methods.most_common(top)
        ],
    )
    section("Playwright by method and caller")
    table(
        ("minutes", "method from caller"),
        [(minutes(s), key) for key, s in callers.most_common(top)],
    )


def report_stacks(path: Path, rate: float, top: int) -> None:
    """The suite's own Python in py-spy's samples of the test protocol: inclusive
    minutes by function, and the innermost frame each sample was in. The protocol's
    stack is off the thread while Playwright's event loop runs, so these minutes
    and the report's Playwright minutes add up to the tests' time.

    Then the Python processes the tests started, by command. A test waiting on one
    shows only the wait, and its work runs in the child. py-spy samples every
    thread of a process, idle ones included, so these are thread-minutes, a measure
    of how long and how widely each command ran rather than of its CPU."""
    inclusive, innermost = Counter(), Counter()
    inside = 0
    runners = set()  # pytest's own processes: the workers and their ancestors
    children = defaultdict(Counter)  # pid -> command -> samples
    for record in STACK.finditer(path.read_text(errors="replace")):
        processes = PROCESS.findall(record["stack"])
        frames = [f for f in record["stack"].split(";") if FRAME.fullmatch(f)]
        samples = int(record["samples"])
        if not any(f.startswith("pytest_runtest_protocol ") for f in frames):
            pid, command = processes[-1]
            children[pid][_command(command)] += samples
            continue
        runners.update(pid for pid, _ in processes)
        inside += samples
        for frame in set(frames):
            if not _harness_frame(frame):
                inclusive[frame] += samples
        innermost[frames[-1]] += samples
    section(
        f"Sampled stacks: {minutes(inside / rate)} minutes of the test "
        "protocol outside Playwright"
    )
    table(
        ("minutes", "inclusive, by function"),
        [(minutes(n / rate), f) for f, n in inclusive.most_common(top)],
    )
    section("Innermost frame")
    table(
        ("minutes", "innermost frame"),
        [(minutes(n / rate), f) for f, n in innermost.most_common(top)],
    )
    commands = Counter()
    for pid, counts in children.items():
        if pid not in runners:
            commands.update(counts)
    section("Python processes the tests started")
    table(
        ("thread-minutes", "command"),
        [(minutes(n / rate), c) for c, n in commands.most_common(top)],
    )


def _command(line: str) -> str:
    """A command line without its paths: the program's name and the words before its
    first path argument, so every run of one command groups together. py-spy records
    some processes with an empty line."""
    if not line.split():
        return "(no command line)"
    program, *words = line.split()
    kept = [Path(program).name]
    for word in words:
        if "/" in word:
            break
        kept.append(word)
    return " ".join(kept)[:100]


def _harness_frame(frame: str) -> bool:
    """A frame of pytest, its plugins, the worker's transport and bootstrap, or the
    click machinery under an in-process command, which every such stack passes through and so says nothing about where a test spends its time."""
    where = frame.rpartition(" (")[2]
    return where.startswith(
        ("_pytest/", "pluggy/", "xdist/", "execnet/", "pytest/", "click/", "<string>:")
    )


def section(title: str) -> None:
    click.echo(f"\n{title}")


def table(header: tuple, rows: list[tuple]) -> None:
    widths = [
        max(len(str(r[i])) for r in (header, *rows)) for i in range(len(header) - 1)
    ]
    for row in (header, *rows):
        cells = [str(c).rjust(w) for c, w in zip(row, widths, strict=False)]
        click.echo("  ".join((*cells, str(row[-1]))))


def minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}"


def share(part: float, whole: float) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"
