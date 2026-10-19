"""Approved appearance across a real message delivery journey.

Run
``uv run pytest -n0 tests/*/test_render_thread_snapshots.py``. Baselines are
reviewed PNG images pinned in leaf-assets; run evidence stays in .tmp.
``leaf-dev thread-snapshots --help`` owns snapshot review and acceptance.
"""

import pytest
from leaf_dev.commands.thread_snapshots import visible_capture
from PIL import Image
from pytest_image_snapshot import ImageMismatchError, ImageNotFoundError


def test_snapshot_comparison_saves_evidence_without_opening_a_viewer(
    image_snapshot, pytestconfig, tmp_path, monkeypatch
):
    """Verbose failures remain local evidence, with explicit missing/update semantics."""

    def viewer(*args, **kwargs):
        pytest.fail("snapshot comparison launched an external image viewer")

    monkeypatch.setattr(Image.Image, "show", viewer)
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_update", False)
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_fail_if_missing", True)
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_save_diff", True)
    monkeypatch.setattr(pytestconfig.option, "verbose", 2)
    expected = tmp_path / "expected.png"
    white = Image.new("RGB", (4, 4), "white")
    black = Image.new("RGB", (4, 4), "black")
    with pytest.raises(ImageNotFoundError, match="not found"):
        image_snapshot(white, expected)
    assert not expected.exists()
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_update", True)
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_fail_if_missing", False)
    image_snapshot(white, expected)
    accepted = expected.read_bytes()
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_update", False)
    image_snapshot(white, expected)
    with pytest.raises(ImageMismatchError) as error:
        image_snapshot(black, expected, threshold=0.01)
    message = str(error.value)
    for evidence in (
        expected.with_suffix(".new.png"),
        expected.with_suffix(".diff.png"),
    ):
        assert evidence.exists()
        assert str(evidence) in message
    assert "display diff" not in message
    assert "thread-snapshots" in message
    assert expected.read_bytes() == accepted
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_update", True)
    image_snapshot(black, expected)
    with Image.open(expected) as saved:
        assert saved.getpixel((0, 0)) == (0, 0, 0)


def test_response_pixels_exclude_chrome_but_keep_frame_and_shadow(
    image_snapshot, pytestconfig, tmp_path, monkeypatch
):
    """Chrome outside the visible band cannot fail the response appearance oracle."""
    clip = {"x": 10, "y": 10, "width": 100, "height": 100}
    window = {"left": 10, "top": 26, "right": 110, "bottom": 110}
    approved = Image.new("RGB", (100, 100), "white")
    expected = tmp_path / "expected.png"
    visible_capture(approved, clip, window).save(expected)
    accepted = expected.read_bytes()
    monkeypatch.setattr(pytestconfig.option, "image_snapshot_update", False)
    current = approved.copy()
    current.paste("black", (0, 0, 100, 16))
    image_snapshot(visible_capture(current, clip, window), expected, threshold=0.01)
    # The top frame edge, left shadow, interior words/focus, and bottom shadow
    # all remain in the oracle, including its first and last visible pixels.
    for box in ((16, 16, 30, 20), (0, 30, 4, 44), (30, 40, 44, 54), (16, 96, 30, 100)):
        changed = current.copy()
        changed.paste("black", box)
        with pytest.raises(ImageMismatchError):
            image_snapshot(
                visible_capture(changed, clip, window), expected, threshold=0.01
            )
    assert expected.read_bytes() == accepted
    assert approved.getpixel((0, 0)) == (255, 255, 255)
