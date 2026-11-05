"""No server path on a generated page grows faster than the page.

Root `AGENTS.md`, "Responsiveness", holds the server to the page's size as it holds
the browser: computing a reading, which admitting an event does too, grows no faster
than the page times its logarithm. This times each server path
`leaf_dev.server_scaling` names on each collection's pages up to 1,600, in process,
and fails what `server_scaling.failures` says grew faster. The rule's 100 ms for a
click's paths (`server_scaling.over_budget`) is reported by `leaf-dev scaling
--server`, not asserted here, until the pages that miss it are fixed.
`uv run leaf-dev scaling --server AXIS --profile` names the function that grew.
"""

import pytest

from leaf_dev.commands.scaling import BASE, COLLECTIONS, SERVER_AXES, SERVER_SIZES
from leaf_dev.server_scaling import failures, measure


@pytest.mark.parametrize("axis", SERVER_AXES)
def test_no_server_path_grows_faster_than_the_page(axis, tmp_path):
    collection = COLLECTIONS[axis]
    rows, _profiles = measure(collection, [BASE, *SERVER_SIZES], tmp_path)
    assert not failures(rows), failures(rows)
