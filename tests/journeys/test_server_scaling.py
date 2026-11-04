"""No server path on a generated page grows faster than the page or passes its budget.

Root `AGENTS.md`, "Responsiveness", holds the server to the page's size as it holds
the browser: the server's reading of a click is on screen within 100 ms, also once the
session's log holds 1,024 events, and computing a reading, which admitting an event
does too, grows no faster than the page times its logarithm. This times each server path
`leaf_dev.server_scaling` names on each collection's pages up to 1,600, in process,
and fails what `server_scaling.failures` says breaks that rule.
`uv run leaf-dev scaling --server AXIS --profile` names the function that grew.
"""

import pytest

from leaf_dev.commands.scaling import BASE, COLLECTIONS, SERVER_AXES, SERVER_SIZES
from leaf_dev.server_scaling import failures, measure


@pytest.mark.parametrize("axis", SERVER_AXES)
def test_no_server_path_grows_faster_than_the_page(axis, tmp_path):
    collection = COLLECTIONS[axis]
    rows, _profiles = measure(collection, [BASE, *SERVER_SIZES], tmp_path)
    assert not failures(collection, rows), failures(collection, rows)
