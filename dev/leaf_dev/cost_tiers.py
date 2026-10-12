"""The tier each test's measured cost puts it in, recorded from CI's runs.

A test runs in the later of the tier its marks name and the tier its cost names,
unless a `landing` mark pins it to every run (`tests/conftest.py`, `run_tier`).
`tests/cost_tiers.json` records the second for every test whose cost puts it past the
first tier, by file and then by the rest of its id, whatever its marks say, so a
mark removed or added later meets its test's measured cost. Cost is the seconds the
test took, setup and teardown included, on CI's runner under three workers; a test
under `LANDING_LIMIT` runs on every run, one under `MAIN_LIMIT` on each push to main,
and any other only in the daily run. Both limits sit at joints in the suite's costs,
as a push run of 2026-10-11 that reached every test measured them: opening a page
costs about three seconds, and 2,416 of 6,022 tests took less, 23 worker-minutes
between them; the 696 tests over eight seconds took 53% of the run.

`leaf-dev cost-tiers DIR` rewrites the record from one run's junit report, so a test
that becomes cheaper joins an earlier tier at the next refresh, and a new test runs
in its marked tier until a refresh measures it. Only a test that passed is measured;
one that failed, was skipped or did not run keeps its recorded tier, since a
failure's time measures the failure, and a hung test would otherwise move off main
exactly when it breaks. Only tests the suite collects now are recorded, so a report
older than a rename or a deletion leaves no entry behind.
"""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import click

from leaf_dev import ROOT

RECORD = ROOT / "tests" / "cost_tiers.json"
TIERS = ("main", "nightly")
LANDING_LIMIT = 3.0
MAIN_LIMIT = 8.0
# The junit property `tests/conftest.py` gives every test: its `recorded_id`.
PROPERTY = "recorded_id"


def recorded() -> dict[str, str]:
    """Each measured test's id and the tier its cost puts it past the first."""
    return {
        f"{path}::{name}": tier
        for path, tests in json.loads(RECORD.read_text()).items()
        for name, tier in tests.items()
    }


def recorded_id(item) -> str:
    """The id a test is recorded under: its node id, without the `@group` suffix
    xdist's `loadgroup` gives a grouped test, so one id holds across schedulers."""
    if group := item.get_closest_marker("xdist_group"):
        name = group.kwargs.get("name") or group.args[0]
        return item.nodeid.removesuffix(f"@{name}")
    return item.nodeid


def cost_tier(seconds: float) -> str | None:
    if seconds < LANDING_LIMIT:
        return None
    return "main" if seconds < MAIN_LIMIT else "nightly"


def later(*tiers: str | None) -> str | None:
    return max((t for t in tiers if t), key=TIERS.index, default=None)


@click.command()
@click.argument(
    "directory", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
def cost_tiers(directory: Path) -> None:
    """Rewrite `tests/cost_tiers.json` from the junit report in DIRECTORY, a
    `pytest-results-*` artifact of CI's `test` job. The daily run measures every test:

        gh run download RUN -p 'pytest-results-*' -D .tmp/tiers
        uv run leaf-dev cost-tiers .tmp/tiers/*/test-results

    Prints each test whose tier moved, with the seconds behind the move."""
    measured = {}
    for case in ET.parse(directory / "results.xml").iter("testcase"):
        prop = case.find(f"properties/property[@name='{PROPERTY}']")
        if prop is None:
            continue
        test = measured.setdefault(prop.get("value"), {"seconds": 0.0, "passed": True})
        test["seconds"] += float(case.get("time", 0))
        test["passed"] &= not any(
            child.tag in ("failure", "error", "skipped") for child in case
        )
    if not measured:
        raise click.UsageError(
            f"{directory / 'results.xml'} holds no `{PROPERTY}` property: "
            "the run predates cost tiers"
        )
    before = recorded()
    collected = _collected()
    after = {name: tier for name, tier in before.items() if name in collected}
    for name, test in measured.items():
        if name not in collected or not test["passed"]:
            continue
        if tier := cost_tier(test["seconds"]):
            after[name] = tier
        else:
            after.pop(name, None)
    grouped = defaultdict(dict)
    for name, tier in sorted(after.items()):
        path, _, rest = name.partition("::")
        grouped[path][rest] = tier
    RECORD.write_text(json.dumps(grouped, indent=1) + "\n")
    for name in sorted(before.keys() | after.keys()):
        old, new = before.get(name), after.get(name)
        if old != new:
            seconds = (
                f"{measured[name]['seconds']:.1f}s" if name in measured else "gone"
            )
            click.echo(f"{old or 'first'} -> {new or 'first'}  {seconds}  {name}")
    click.echo(f"{len(measured)} tests measured; {len(after)} past the first tier")


def _collected() -> set[str]:
    """Every test id the suite collects, in every tier."""
    collection = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q", "-n0"]
        + ["--run-nightly"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if collection.returncode:
        raise click.ClickException(f"collecting the suite failed:\n{collection.stdout}")
    return {line for line in collection.stdout.splitlines() if "::" in line}
