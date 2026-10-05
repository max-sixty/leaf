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
    from leaf_dev import leaf_assets
    from leaf_dev.thread_snapshots import accept, capture_files, render_profile

    profile = render_profile(browser.version)
    directory = tmp_path / "capture"
    shutil.copytree(thread_expected_store / profile, directory / profile)
    files = capture_files(directory, profile)
    runner = CliRunner()
    published = []
    monkeypatch.setattr(
        leaf_assets, "stage", lambda *args: published.append(args) or tmp_path
    )
    monkeypatch.setattr(
        leaf_assets, "publish", lambda *args: "reviewed-assets-revision"
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
    assert published[0][1] == files
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


def test_a_ci_run_assembles_into_the_capture_its_cases_completed(
    thread_expected_store, tmp_path
):
    """A CI run's evidence becomes the same reviewable capture `capture` writes, and
    only once every case passed its delivery assertions."""
    import click
    from leaf_dev.thread_journey import STAGES
    from leaf_dev.thread_snapshots import COMPLETE, assemble, capture_files

    profile = next(path.name for path in thread_expected_store.iterdir())

    def attempt(number):
        return (
            tmp_path
            / f"evidence/pytest-results-test-7-{number}/thread-snapshots/runs/uid"
        )

    for case in CASES:
        evidence = attempt(2) / case.name
        evidence.mkdir(parents=True)
        readings = {}
        for stage in STAGES:
            approved = thread_expected_store / profile / f"{case.name}-{stage}"
            shutil.copyfile(
                approved.with_suffix(".png"), evidence / f"{stage}.actual.png"
            )
            readings[stage] = {
                "region": json.loads(approved.with_suffix(".json").read_text())
            }
        (evidence / "observations.json").write_text(json.dumps(readings))
        (evidence / COMPLETE).write_text(profile)
    # A re-run's later attempt is the one that stands, and a run of the same
    # attempt-1 cases does not make the choice ambiguous.
    shutil.copytree(attempt(2), attempt(1))
    for png in attempt(1).glob("*/*.png"):
        png.write_bytes(b"an earlier attempt")
    directory = assemble(tmp_path / "evidence", tmp_path / "captures")
    assert capture_files(directory, profile) == capture_files(
        thread_expected_store, profile
    )
    for number in (1, 2):
        (attempt(number) / CASES[0].name / COMPLETE).unlink()
    with pytest.raises(click.ClickException, match="no attempt"):
        assemble(tmp_path / "evidence", tmp_path / "captures")
