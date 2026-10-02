"""Pytest's boundary for approved-source thread snapshots and internal capture arms.

Setup renders the explicitly approved historical source once per environment;
normal tests read its verified cache, then compare the candidate. A capture arm must name its writable evidence store;
the ordinary gate never creates expectations from the candidate.
"""

from pathlib import Path

import pytest

from leaf_dev import ROOT


def pytest_addoption(parser):
    parser.addoption(
        "--thread-snapshot-store",
        type=Path,
        help="Explicit PNG evidence store for a source arm; ordinarily use the approved source",
    )


def pytest_configure(config):
    # The dependency's missing flag is unconditional, including update mode.
    config.option.image_snapshot_fail_if_missing = not config.getoption(
        "--image-snapshot-update"
    )


@pytest.fixture
def thread_expected_store(browser, pytestconfig):
    store = pytestconfig.getoption("--thread-snapshot-store")
    if store:
        return store if store.is_absolute() else ROOT / store
    if pytestconfig.getoption("--image-snapshot-update"):
        raise pytest.UsageError(
            "Accept reviewed source with leaf-dev thread-snapshots accept"
        )
    from leaf_dev.thread_snapshot_source import approved_store

    return approved_store(browser.version)
