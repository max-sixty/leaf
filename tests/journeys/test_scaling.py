"""No cost of a generated page grows faster than the page.

Root `AGENTS.md`, "Responsiveness", holds every cost to the page's size: an input's work
never grows faster than the page, and loading or applying a reading grows no faster than
n log n. A step that walks one of the page's collections for each member of another
breaks it, and reads as linear in its own code. This measures each page `leaf-dev
scaling` generates at three sizes and its fixed-work page, as that command does, and
fails a cost other than a Tab's whose growth above the fixed work fits an exponent
past `SUPERLINEAR`.
`uv run leaf-dev scaling AXIS --profile` names the function that grew.

A busy runner adds time to a reading and never takes it away, so each size is measured
twice, the sizes interleaved, and the lower reading counts. On a host at load 50, three
such pairs of every cost on every axis stayed under `SUPERLINEAR`, and 100 ms per input
of added quadratic work failed most of them.

Each run also writes the readings it takes at `CHARTED` sections, the lower of each
pair, to `READINGS` in github-action-benchmark's `customSmallerIsBetter` form, and the
daily run charts them (`.github/workflows/ci.yaml`, `scaling-chart`): a change that
slows pages of every size alike passes the growth test, and the chart shows it.
"""

import json
from contextlib import ExitStack

import pytest

from leaf_dev import ROOT
from leaf_dev.commands.scaling import (
    AXES,
    BASE,
    SERVER,
    SUPERLINEAR,
    TRANSITIONS,
    exponent,
    measure,
    serving_collection,
)

SIZES = [BASE, 64, 128, 256]
ROUNDS = 2
# The size of the largest real pages, whose readings CI charts each day.
CHARTED = 64
READINGS = ROOT / ".tmp" / "test-results" / "scaling"


@pytest.mark.parametrize("axis", sorted(AXES))
def test_no_cost_grows_faster_than_the_page(axis, tmp_path, browser):
    with ExitStack() as serving:
        addresses = [
            serving.enter_context(
                serving_collection(ROOT, AXES[axis], n, tmp_path / str(n))
            )
            for n in SIZES
        ]
        rounds = [
            [measure(browser, address, None) for address in addresses]
            for _ in range(ROUNDS)
        ]
    # Each size's lower reading of each cost.
    lowest = [
        {cost: min(row[cost] for row in by_size) for cost in (*TRANSITIONS, *SERVER)}
        for by_size in zip(*rounds, strict=True)
    ]
    READINGS.mkdir(parents=True, exist_ok=True)
    (READINGS / f"{axis}.json").write_text(
        json.dumps(
            [
                {
                    "name": f"{axis}: {cost}",
                    "unit": "KB" if cost == "event_kb" else "ms",
                    "value": round(reading, 2),
                }
                for cost, reading in lowest[SIZES.index(CHARTED)].items()
            ]
        )
    )
    grown = {}
    # `leaf-dev scaling` reports a Tab's cost, which this doesn't hold to anything yet.
    for cost in (c for c in (*TRANSITIONS, *SERVER) if c != "tab"):
        readings = [at_size[cost] for at_size in lowest]
        slope = exponent(cost, SIZES, readings)
        if slope is not None and slope > SUPERLINEAR:
            grown[cost] = {
                "by size": dict(zip(SIZES, readings, strict=True)),
                "exponent": slope,
            }
    assert not grown, grown
