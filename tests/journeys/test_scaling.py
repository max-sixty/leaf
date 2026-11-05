"""No cost of a generated page grows faster than the page.

Root `AGENTS.md`, "Responsiveness", holds every cost to the page's size: an input's work
never grows faster than the page, and loading or applying a reading grows no faster than
n log n. A step that walks one of the page's collections for each member of another
breaks it, and reads as linear in its own code. This measures each page `leaf-dev
scaling` generates at three sizes and its fixed-work page, as that command does
(`scaling.measure_rounds`), and fails a cost outside `UNHELD` whose growth above the
fixed work fits an exponent past `SUPERLINEAR` (`scaling.failures`).
`uv run leaf-dev scaling AXIS --profile` names the function that grew.

A busy runner adds time to a reading and never takes it away, so each size is measured
twice, the sizes interleaved, and the lower reading counts (`scaling.lowest`). Each
reading is the page's own: the suite's health sensors (`render_harness.watched`) work
on the main thread at every input, more than most inputs take, so the pages are
opened without them. Each page's costs stayed under `SUPERLINEAR` on an M5 Max at
load 10, and the document and asks pages' at CPU rate 10 too, while 100 ms of busy
work at the 256 page, added to each press, key and wheel step and scaled with the
square of the page's size, failed the click, key and scroll on the prose and
document pages.

Each run also writes the readings it takes at `CHARTED` sections, the lower of each
pair, to `READINGS` in github-action-benchmark's `customSmallerIsBetter` form, and the
daily run charts them (`.github/workflows/ci.yaml`, `scaling-chart`): a change that
slows pages of every size alike passes the growth test, and the chart shows it.
"""

import json

import pytest

from leaf_dev import ROOT
from leaf_dev.arms import choose_arms
from leaf_dev.commands.scaling import (
    AXES,
    BASE,
    COLUMNS,
    failures,
    floors,
    measure_rounds,
)

SIZES = [BASE, 64, 128, 256]
ROUNDS = 2
# The size of the largest real pages, whose readings CI charts each day.
CHARTED = 64
READINGS = ROOT / ".tmp" / "test-results" / "scaling"
# The costs `leaf-dev scaling` reports and CI charts that this holds to no growth.
UNHELD = (
    # Tab's, which this doesn't hold to anything yet.
    "tab",
    # A revision's, which grows with the margin's rows as the runtime places them
    # today: on asks it fit 1.29 on 2026-11-05, and a largest reading 34% higher, a
    # runner's usual spread, fits 1.51.
    "revision",
    # `shown`, elapsed time, which a shared runner's load stretches as CPU time it
    # doesn't.
    "shown",
)


@pytest.mark.parametrize("axis", sorted(AXES))
def test_no_cost_grows_faster_than_the_page(axis, tmp_path, browser):
    # The suite's watches instrument every timer, write and input on a watched page,
    # which multiplied a keystroke's cost here tenfold and more; this measures the
    # page a user gets, as `leaf-dev scaling` does.
    (rows,) = measure_rounds(
        browser.unwatched,
        choose_arms(None, tmp_path),
        AXES[axis],
        SIZES,
        ROUNDS,
        tmp_path,
    ).values()
    costs = [cost for cost in COLUMNS if cost in rows[0]]
    READINGS.mkdir(parents=True, exist_ok=True)
    (READINGS / f"{axis}.json").write_text(
        json.dumps(
            [
                {
                    "name": f"{axis}: {cost}",
                    "unit": "KB" if cost == "event_kb" else "ms",
                    "value": round(rows[SIZES.index(CHARTED)][cost], 2),
                }
                for cost in costs
            ]
        )
    )
    held = {cost: floor for cost, floor in floors(rows).items() if cost not in UNHELD}
    failed = failures(rows, held)
    assert not failed, failed
