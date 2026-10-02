"""Pytest's boundary for approved-source thread snapshots and internal capture arms.

Setup renders the explicitly approved historical source once per environment;
normal tests read its verified cache, then compare the candidate. A capture arm must name its writable evidence store;
the ordinary gate never creates expectations from the candidate.
"""

from pathlib import Path

import pytest
from pytest_image_snapshot import ImageMismatchError, _image_snapshot

from leaf_dev import ROOT


@pytest.fixture
def image_snapshot(request):
    """Compare through the dependency without launching an external image viewer.

    Verbose pytest runs retain their normal text output and saved image evidence.
    Both the candidate and historical capture arms load this fixture.
    """

    def compare(img, img_path, threshold=None):
        config = request.config
        save_diff = config.getoption("--image-snapshot-save-diff")
        try:
            return _image_snapshot(
                img,
                img_path,
                threshold=threshold,
                update_snapshots=config.getoption("--image-snapshot-update"),
                fail_if_missing=config.getoption("--image-snapshot-fail-if-missing"),
                save_diff=save_diff,
                verbose=0,
            )
        except ImageMismatchError:
            path = Path(img_path)
            evidence = (
                f" Actual: {path.with_suffix('.new' + path.suffix)}."
                f" Diff: {path.with_suffix('.diff' + path.suffix)}."
                if save_diff
                else " Use --image-snapshot-save-diff to save comparison evidence."
            )
            raise ImageMismatchError(
                f"Image does not match the snapshot stored in {path}.{evidence}"
                " Review appearance with leaf-dev thread-snapshots before accepting source."
            ) from None

    return compare


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
