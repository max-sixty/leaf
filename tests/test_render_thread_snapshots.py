"""Approved appearance across a real message delivery journey.

Run
``uv run pytest -n0 tests/test_render_thread_snapshots.py``. Baselines are
reviewed PNG images pinned in leaf-assets; run evidence stays in .tmp.
``leaf-dev thread-snapshots --help`` owns snapshot review and acceptance.
"""

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone

import pytest
from leaf import event_log
from leaf.served_state import context as served_context
from leaf_dev import ROOT
from leaf_dev.thread_journey import NEXT_WORDS, WORDS, delivery_journey
from leaf_dev.thread_snapshots import CASES, SnapshotRun
from PIL import Image
from pytest_image_snapshot import ImageMismatchError, ImageNotFoundError
from render_harness import consume_browser_errors, leaf_page, open_page


@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux's fixed native font contract"
)
def test_linux_browser_resolves_the_profile_fonts(browser, serve):
    """Native UI, serif and mono styles all use the faces bound into the profile."""
    faces = {
        "system-ui": ("DejaVu Sans", "DejaVuSans", "Oblique"),
        "serif": ("DejaVu Serif", "DejaVuSerif", "Italic"),
        "monospace": ("DejaVu Sans Mono", "DejaVuSansMono", "Oblique"),
    }
    styles = (
        ("normal", "normal"),
        ("bold", "normal"),
        ("normal", "italic"),
        ("bold", "italic"),
    )
    readings = {
        f"{name}-{weight}-{style}": (
            family,
            base
            + ("-" if weight == "bold" or style == "italic" else "")
            + ("Bold" if weight == "bold" else "")
            + (italic if style == "italic" else ""),
        )
        for name, (family, base, italic) in faces.items()
        for weight, style in styles
    }
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Font contract",
                "".join(
                    f'<p id="{name}">Native Leaf words 0123</p>' for name in readings
                ),
                head="<style>"
                + "".join(
                    f"#{name}-{weight}-{style} {{ font-family: {name}; "
                    f"font-weight: {weight}; font-style: {style}; }}"
                    for name in faces
                    for weight, style in styles
                )
                + "</style>",
            )
        ),
    )
    session = page.context.new_cdp_session(page)
    session.send("DOM.enable")
    session.send("CSS.enable")
    root = session.send("DOM.getDocument")["root"]["nodeId"]
    for name, (family, postscript) in readings.items():
        node = session.send(
            "DOM.querySelector", {"nodeId": root, "selector": f"#{name}"}
        )["nodeId"]
        fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
        assert {font["familyName"] for font in fonts} == {family}, (
            fonts,
            page.locator(f"#{name}").evaluate(
                "node => getComputedStyle(node).fontFamily"
            ),
        )
        assert all(not font["isCustomFont"] for font in fonts), fonts
        assert {font["postScriptName"] for font in fonts} == {postscript}, fonts
    session.detach()


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


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_message_delivery_appearance_and_first_frame(
    browser, serve, image_snapshot, request, case, monkeypatch, thread_expected_store
):
    """One journey supplies both the contract observations and reviewed pixels."""
    now = datetime(2026, 9, 7, 18, tzinfo=timezone.utc)
    monkeypatch.setattr(event_log, "now_iso", lambda: now.isoformat())
    monkeypatch.setattr(served_context, "now_iso", lambda: now.isoformat())
    context = browser.new_context(
        viewport={"width": case.viewport[0], "height": case.viewport[1]},
        color_scheme=case.scheme,
        reduced_motion=case.motion,
        device_scale_factor=1,
        locale="en-US",
        timezone_id="UTC",
    )
    context.clock.set_fixed_time(now)
    page = open_page(browser, serve(ROOT / case.source), context=context)
    page.evaluate("() => document.fonts.ready")
    run = SnapshotRun(
        browser.version,
        case,
        image_snapshot,
        output=ROOT
        / ".tmp/thread-snapshots/runs"
        / request.getfixturevalue("testrun_uid"),
        store=thread_expected_store,
        updating=request.config.getoption("--image-snapshot-update"),
    )
    try:
        observed = delivery_journey(page, case.surface, run.capture)
        admitted = [
            event
            for event in event_log.read_events(serve.page_dir)
            if event.get("text") == WORDS
        ]
        assert len(admitted) == 1, f"expected one admitted send, got {admitted!r}"
        assert {
            key: admitted[0].get(key) for key in ("kind", "parent", "anchor")
        } == observed["drafted"]["intent"]
        assert {
            stage: {key: reading[key] for key in ("draft", "messages_added", "pending")}
            for stage, reading in observed.items()
        } == {
            "drafted": {"draft": WORDS, "messages_added": 0, "pending": 0},
            "pending": {"draft": "", "messages_added": 1, "pending": 1},
            "refused": {"draft": WORDS, "messages_added": 0, "pending": 0},
            "retry-pending": {"draft": "", "messages_added": 1, "pending": 1},
            "newer-draft-pending": {
                "draft": NEXT_WORDS,
                "messages_added": 1,
                "pending": 1,
            },
            "accepted": {"draft": NEXT_WORDS, "messages_added": 1, "pending": 0},
        }
        assert observed["accepted"]["opacity"] == 1
        for stage in ("newer-draft-pending", "accepted"):
            assert observed[stage]["focused"]
            assert observed[stage]["caret"] == [len(NEXT_WORDS) - 3] * 2
        consume_browser_errors(page, "400")
        run.finish()
    finally:
        (run.output / "observations.json").write_text(
            json.dumps(run.observations, indent=2) + "\n", encoding="utf-8"
        )


def test_accept_publishes_only_a_successful_unchanged_capture(
    browser, thread_expected_store, tmp_path, monkeypatch
):
    """Publication consumes reviewed bytes; a partial or changed capture cannot publish."""
    from click.testing import CliRunner
    from leaf_dev import leaf_assets, thread_snapshots
    from leaf_dev.thread_snapshots import accept, capture_files, render_profile

    profile = render_profile(browser.version)
    directory = tmp_path / "capture"
    shutil.copytree(thread_expected_store / profile, directory / profile)
    files = capture_files(directory, profile)
    baseline = tmp_path / "reviewed-expectations"
    shutil.copytree(thread_expected_store, baseline)
    (baseline / "another-profile").mkdir()
    retained = baseline / "another-profile/checkpoint.png"
    retained.write_bytes(b"this runtime's reviewed other profile")
    (baseline / profile / "obsolete.png").write_bytes(b"superseded checkpoint")
    monkeypatch.setattr(thread_snapshots, "expected_store", lambda: baseline)
    runner = CliRunner()
    published = []
    accepted_pins = []
    monkeypatch.setattr(
        leaf_assets,
        "stage",
        lambda *args, **kwargs: published.append((args, kwargs)) or tmp_path,
    )
    monkeypatch.setattr(
        leaf_assets,
        "publish",
        lambda *args, **kwargs: (
            accepted_pins.append(kwargs) or "reviewed-assets-revision"
        ),
    )
    assert runner.invoke(accept, [str(directory)]).exit_code != 0
    assert published == []
    (directory / "capture.json").write_text(
        json.dumps(
            {
                "profile": profile,
                "sha256": {
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in files.items()
                },
            }
        )
    )
    result = runner.invoke(accept, [str(directory)])
    assert result.exit_code == 0, result.output
    staged, options = published[0]
    assert staged[0] == "tests/thread-snapshots"
    assert {
        name.removeprefix(f"{profile}/"): data
        for name, data in staged[1].items()
        if name.startswith(f"{profile}/")
    } == files
    assert staged[1]["another-profile/checkpoint.png"] == retained.read_bytes()
    assert f"{profile}/obsolete.png" not in staged[1]
    assert {
        name: data
        for name, data in staged[1].items()
        if not name.startswith(f"{profile}/")
    } == {
        path.relative_to(baseline).as_posix(): path.read_bytes()
        for path in baseline.rglob("*")
        if path.is_file() and path.relative_to(baseline).parts[0] != profile
    }
    assert options == {"replace_tree": True}
    assert accepted_pins == [{"revision_key": "thread_snapshots_revision"}]
    published.clear()
    image = next((directory / profile).glob("*.png"))
    image.write_bytes(image.read_bytes() + b"changed")
    result = runner.invoke(accept, [str(directory)])
    assert result.exit_code != 0 and "changed after" in result.output
    assert published == []
    image.unlink()
    result = runner.invoke(accept, [str(directory)])
    assert result.exit_code != 0 and "missing capture" in result.output
    assert published == []
