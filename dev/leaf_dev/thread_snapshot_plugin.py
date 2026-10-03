"""Current Leaf compares directly against PNG images pinned in leaf-assets.

Only the explicit capture command writes a separate evidence store. Ordinary
comparisons cannot update the immutable asset checkout or silently accept missing
images. Verbose failures save evidence without launching an external image viewer.
"""

from pathlib import Path

import pytest
from pytest_image_snapshot import ImageMismatchError, _image_snapshot

from leaf_dev import ROOT


@pytest.fixture
def image_snapshot(request):
    """Compare through the dependency without launching an external image viewer.

    Verbose pytest runs retain their normal text output and saved image evidence.
    Current comparisons and explicit captures load this fixture.
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
                " Review evidence, then use leaf-dev thread-snapshots capture and accept."
            ) from None

    return compare


def pytest_addoption(parser):
    parser.addoption(
        "--thread-snapshot-store",
        type=Path,
        help="Writable PNG store for an explicit capture; ordinary tests use pinned leaf-assets",
    )


def pytest_configure(config):
    # The dependency's missing flag is unconditional, including update mode.
    config.option.image_snapshot_fail_if_missing = not config.getoption(
        "--image-snapshot-update"
    )


@pytest.fixture
def thread_expected_store(pytestconfig):
    store = pytestconfig.getoption("--thread-snapshot-store")
    if store:
        return store if store.is_absolute() else ROOT / store
    if pytestconfig.getoption("--image-snapshot-update"):
        raise pytest.UsageError(
            "Use leaf-dev thread-snapshots capture before accepting reviewed images"
        )
    from leaf_dev.thread_snapshots import expected_store

    return expected_store()
