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
twice, the sizes interleaved, and the lower reading counts. Each reading is the page's
own: the suite's health sensors (`render_harness.watched`) work on the main thread at
every input, more than most inputs take, so the pages are opened without them. Each
page's costs stayed under `SUPERLINEAR` on an M5 Max at load 10, and the document and
asks pages' at CPU rate 10 too, while 100 ms of busy work at the 256 page, added to each
press, key and wheel step and scaled with the square of the page's size, failed the
click, key and scroll on the prose and document pages.
"""

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
    floors,
    measure,
    serving_collection,
)

SIZES = [BASE, 64, 128, 256]
ROUNDS = 2


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
            [measure(browser.unwatched, address, None) for address in addresses]
            for _ in range(ROUNDS)
        ]
    low = [
        {cost: min(row[cost] for row in by_size) for cost in by_size[0]}
        for by_size in zip(*rounds, strict=True)
    ]
    noise = floors(low)
    grown = {}
    # `leaf-dev scaling` reports a Tab's cost, which this doesn't hold to anything yet.
    for cost in (c for c in (*TRANSITIONS, *SERVER) if c != "tab"):
        readings = [row[cost] for row in low]
        slope = exponent(SIZES, readings, noise[cost])
        if slope is not None and slope > SUPERLINEAR:
            grown[cost] = {
                "by size": dict(zip(SIZES, readings, strict=True)),
                "exponent": slope,
            }
    assert not grown, grown
