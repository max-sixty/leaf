"""Reviewed PNG expectations for one real message-delivery journey.

Images and viewport geometry live in max-sixty/leaf-assets, pinned by the existing
leaf-assets.json's thread_snapshots_revision. Tests compare current Leaf directly
against that immutable set; no historical runtime, source patch or baseline build is
involved. Fonts and antialiasing differ by OS and machine, so CI's Linux runner both
compares the images and captures the approved ones, and no developer machine has to
reproduce its rendering. A profile names the runner's OS release, architecture and
locked Chromium version, and a missing profile fails: an Ubuntu release or Chromium
upgrade requires a deliberately reviewed capture, while a font package update within
the release shows as an appearance mismatch. Elsewhere, macOS included, the journey and
its delivery assertions still run and keep their images as evidence, except in the
dark cases, whose colour scheme changes only pixels. Existing fetch-assets warms the
same cache as every other asset reader.

macOS had a profile of its own, compared locally. It was dropped once CI captured
Linux: a second profile doubled each capture and review, and its name followed one
developer's macOS version, which CI's macOS runner doesn't share. Rendering CI's Linux
profile locally in Playwright's container was declined, since developer machines
shouldn't need Docker.

    uv run pytest -n0 tests/*/test_render_thread_snapshots.py
    uv run leaf-dev thread-snapshots --help

The thread-snapshots workflow runs `capture`: the same journey and hard delivery
assertions, writing all 48 PNG images and geometry readings into the artifact it
uploads, with each run's evidence. Review its images and observations, then accept
publishes that run's profile as the whole pinned collection through
leaf_assets.stage / publish and updates the thread-expectations pin, leaving media's
revision untouched. Acceptance never occurs in normal tests. CI retains failed run
evidence. Small antialias noise is excluded by Pixelmatch's AA handling and
calibrated 0.01 perceptual tolerance; every other mismatched pixel fails, with no
whole-image allowance. Compare the padded response frame inside the window the page
shows (`shownWindow`), retaining frame shadows and the editor at the viewport foot.
Keep full captures for review. Independently compare viewport geometry so a
translated crop cannot conceal placement changes.

First insertion has an immediate words/busy/opacity observer before stabilized
screenshots. Refusal's exact feedback and native visibility are observed at mutation;
its expiry, on the advanced timer clock, precedes the restored-draft capture. Transient
notice styling is outside the pixel oracle and retains its ordinary rendered lifecycle tests. Capture
hides only editor carets, preserving draft words, focus and selection. Eight bounded
cases cover general, panel, margin, inline diff, dark and narrow appearances;
they do not claim all thread states. Existing news/storage tests remain separate.
"""

import io
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
from PIL import Image
from playwright.sync_api import Page
from pytest_image_snapshot import ImageMismatchError

from leaf_dev import ROOT, leaf_assets
from leaf_dev.thread_journey import STAGES


@dataclass(frozen=True)
class Case:
    name: str
    surface: str
    source: str = "examples/review-a-plan.html"
    viewport: tuple[int, int] = (1440, 900)
    scheme: str = "light"
    motion: str = "no-preference"


CASES = (
    Case("general", "general"),
    Case("panel", "panel"),
    Case("margin", "margin"),
    Case(
        "inline",
        "inline",
        source="tests/fixtures/pages/thread-journey-inline.html",
        motion="reduce",
    ),
    Case(
        "inline-dark",
        "inline",
        source="tests/fixtures/pages/thread-journey-inline.html",
        scheme="dark",
        motion="reduce",
    ),
    Case("margin-dark", "margin", scheme="dark", motion="reduce"),
    Case("panel-dark", "panel", scheme="dark", motion="reduce"),
    Case("panel-narrow", "panel", viewport=(390, 740)),
)


# Whether this run compares appearance: only on CI's Linux runner, which also captures
# the approved images, so a Linux developer machine isn't held to a profile it can't
# reproduce.
COMPARED = sys.platform == "linux" and os.environ.get("GITHUB_ACTIONS") == "true"


def render_profile(browser_version: str) -> str:
    """The rendering environment whose images this run can compare meaningfully."""
    release = platform.freedesktop_os_release()["VERSION_ID"]
    return f"linux-{release}-{platform.machine()}-chromium-{browser_version}"


def visible_capture(image: Image.Image, clip: dict, window: dict) -> Image.Image:
    """Keep captured pixels inside the response window, including frame halos.

    Both approved and actual images retain their full padded capture separately.
    Crop at whole pixels inside the window so no partial pixel of Leaf's chrome
    enters the response oracle. The independently compared region still owns placement.
    """
    return image.crop(
        (
            math.ceil(window["left"] - clip["x"]),
            math.ceil(window["top"] - clip["y"]),
            math.floor(window["right"] - clip["x"]),
            math.floor(window["bottom"] - clip["y"]),
        )
    )


@contextmanager
def hidden_editor_carets(page: Page):
    """Hide native carets inside closed editor roots during a Chromium capture.

    Playwright's caret='hide' walks open roots only. Chromium's inspector exposes
    the closed CodeMirror root, so use its DOM API for the same capture-only CSS
    operation; restore that property and retain active focus/selection.
    """
    session = page.context.new_cdp_session(page)
    changed = []

    def visit(node, closed=False):
        closed |= node.get("shadowRootType") == "closed"
        attrs = node.get("attributes", [])
        attrs = dict(zip(attrs[::2], attrs[1::2], strict=True))
        if closed and attrs.get("contenteditable") == "true":
            identity = session.send("DOM.resolveNode", {"nodeId": node["nodeId"]})[
                "object"
            ]["objectId"]
            previous = session.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": identity,
                    "returnByValue": True,
                    "functionDeclaration": """function() {
                    const previous = [this.style.getPropertyValue('caret-color'),
                        this.style.getPropertyPriority('caret-color'), this.hasAttribute('style')];
                    this.style.setProperty('caret-color', 'transparent', 'important');
                    return previous;
                }""",
                },
            )["result"]["value"]
            changed.append((identity, previous))
        for child in (*node.get("children", []), *node.get("shadowRoots", [])):
            visit(child, closed)

    try:
        visit(session.send("DOM.getDocument", {"depth": -1, "pierce": True})["root"])
        yield
    finally:
        for identity, previous in reversed(changed):
            session.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": identity,
                    "arguments": [{"value": previous}],
                    "functionDeclaration": """function([value, priority, hadStyle]) {
                    this.style.setProperty('caret-color', value, priority);
                    if (!hadStyle && this.style.length === 0) this.removeAttribute('style');
                }""",
                },
            )
        session.detach()


class SnapshotRun:
    """Compare one case's captures using the store Path resolved by pytest."""

    def __init__(
        self, browser_version, case, compare, *, output, store: Path, updating=False
    ):
        self.browser_version = browser_version
        self.case = case
        self.compare = compare
        self.output = Path(output) / case.name
        self.output.mkdir(parents=True, exist_ok=True)
        self.store = store
        self.updating = updating
        self.failures = []
        self.observations = {}

    def capture(self, stage: str, page: Page, reading: dict) -> None:
        """Compare held appearance after the independently observed insertion instant."""
        # Capture the thread's own restored/delivery region. Finite notice feedback
        # has its independent mutation observation and expires before this capture.
        region = reading["region"]
        viewport = page.viewport_size
        left, top = max(0, region["x"] - 16), max(0, region["y"] - 16)
        clip = {
            "x": left,
            "y": top,
            "width": min(viewport["width"], region["x"] + region["width"] + 16) - left,
            "height": min(viewport["height"], region["y"] + region["height"] + 16)
            - top,
        }
        window = page.evaluate(
            """async clip => {
              const {shownWindow} = await window.__lfWidgetApi();
              return {left: clip.x, top: Math.max(clip.y, shownWindow().top),
                right: clip.x + clip.width, bottom: clip.y + clip.height};
            }""",
            clip,
        )
        with hidden_editor_carets(page):
            png = page.screenshot(
                caret="hide", scale="css", clip=clip, animations="disabled"
            )
        actual = self.output / f"{stage}.actual.png"
        actual.write_bytes(png)
        self.observations[stage] = reading | {
            "capture_clip": clip,
            "capture_window": window,
        }
        if not COMPARED:
            return
        profile = render_profile(self.browser_version)
        baseline = self.store / profile / f"{self.case.name}-{stage}.png"
        geometry = baseline.with_suffix(".json")
        if self.updating:
            geometry.parent.mkdir(parents=True, exist_ok=True)
            geometry.write_text(json.dumps(reading["region"], indent=2) + "\n")
        elif not geometry.is_file():
            self.failures.append(f"{stage}: missing approved geometry: {geometry}")
        elif json.loads(geometry.read_text()) != reading["region"]:
            self.failures.append(
                f"{stage}: thread geometry changed: expected {geometry.read_text().strip()}, "
                f"actual {reading['region']}"
            )
        expected = self.output / f"{stage}.expected.png"
        if not self.updating and baseline.is_file():
            shutil.copyfile(baseline, expected)
        # A profile without this case's images still runs the whole journey, so a
        # new case's first run leaves every stage's actual image for review.
        if not self.updating and not baseline.is_file():
            self.failures.append(f"{stage}: missing approved image: {baseline}")
            return
        if self.updating:
            baseline.parent.mkdir(parents=True, exist_ok=True)
            self.compare(Image.open(io.BytesIO(png)), baseline, threshold=0.01)
            return
        compared_actual = self.output / f"{stage}.compared.actual.png"
        compared_expected = self.output / f"{stage}.compared.expected.png"
        current = visible_capture(Image.open(io.BytesIO(png)), clip, window)
        current.save(compared_actual)
        with Image.open(expected) as approved:
            visible_capture(approved, clip, window).save(compared_expected)
        try:
            # Pixelmatch ignores antialias edges and small perceptual color changes.
            # Every remaining mismatch fails; there is no whole-image allowance.
            self.compare(current, compared_expected, threshold=0.01)
        except ImageMismatchError:
            self.failures.append(
                f"{stage}: appearance changed\n"
                f"Expected: {compared_expected}\nActual: {compared_actual}\n"
                f"Diff: {compared_expected.with_suffix('.diff.png')}\n"
                f"Full captures: {expected}, {actual}"
            )

    def finish(self) -> None:
        """Report every changed checkpoint together after the journey completes."""
        assert not self.failures, (
            "\n".join(self.failures)
            + f"\nReadings: {self.output / 'observations.json'}\nEvidence: {self.output}"
        )


ASSET_DIRECTORY = "tests/thread-snapshots"
# What .github/workflows/thread-snapshots.yaml uploads: `.tmp/thread-snapshots`, the
# capture beside its runs' evidence.
ARTIFACT = "thread-snapshots"
CAPTURE = ROOT / ".tmp/thread-snapshots/capture"


def expected_store() -> Path:
    """The immutable PNG tree selected by this checkout's reviewed expectations."""
    return (
        leaf_assets.pinned_assets(revision_key="thread_snapshots_revision")
        / ASSET_DIRECTORY
    )


@click.group()
def thread_snapshots():
    """Capture, review and publish current Leaf's thread appearance.

    \b
    CI's Linux runner captures it, for a pushed branch checked out here:
      gh workflow run thread-snapshots.yaml --ref <branch>
      gh run list --workflow thread-snapshots.yaml --branch <branch>
      gh run download <run> --name thread-snapshots --dir .tmp/thread-snapshots/<run>
      uv run leaf-dev thread-snapshots accept <run>
    """


@thread_snapshots.command("capture")
def capture():
    """Run all delivery assertions and capture current appearance for review.

    The thread-snapshots workflow runs this on CI's Linux runner, the only place
    appearance is compared.
    """
    if not COMPARED:
        raise click.ClickException(
            "thread appearance is captured on CI's Linux runner: "
            "gh workflow run thread-snapshots.yaml --ref <pushed branch>"
        )
    CAPTURE.mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-n0",
            "-q",
            "--image-snapshot-update",
            "--thread-snapshot-store",
            str(CAPTURE),
            "tests/journeys/test_render_thread_snapshots.py::test_message_delivery_appearance_and_first_frame",
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        raise click.ClickException(
            f"capture assertions failed; review evidence in {CAPTURE.parent}"
        )
    (profile,) = (path.name for path in CAPTURE.iterdir() if path.is_dir())
    capture_files(CAPTURE, profile)
    (CAPTURE / "capture.json").write_text(json.dumps({"profile": profile}) + "\n")
    click.echo(f"Captured {profile} in {CAPTURE}")


def capture_files(directory: Path, profile: str) -> dict[str, bytes]:
    """Require every named checkpoint and its independently read geometry."""
    files = {}
    for case in CASES:
        for stage in STAGES:
            for suffix in ("png", "json"):
                name = f"{case.name}-{stage}.{suffix}"
                path = directory / profile / name
                if not path.is_file():
                    raise click.ClickException(f"missing capture: {profile}/{name}")
                files[name] = path.read_bytes()
    return files


def run_source(run: str) -> dict:
    """The event that started workflow run `run` and the commit it checked out."""
    result = subprocess.run(
        ["gh", "run", "view", run, "--json", "event,headSha"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise click.ClickException(f"could not read run {run}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def download_artifact(run: str, into: Path) -> None:
    """Download the thread-snapshots artifact of workflow run `run` into `into`."""
    command = ["gh", "run", "download", run, "--name", ARTIFACT, "--dir", str(into)]
    if subprocess.run(command, cwd=ROOT, check=False).returncode:
        raise click.ClickException(
            f"could not download run {run}'s {ARTIFACT} artifact; see gh's message above"
        )


@thread_snapshots.command("accept")
@click.argument("run")
def accept(run: str):
    """Publish the reviewed capture of thread-snapshots workflow RUN and pin it.

    The run must be a dispatch on this checkout's HEAD, so the pin moves with the
    code whose appearance it holds.
    """
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    source = run_source(run)
    if (source["event"], source["headSha"]) != ("workflow_dispatch", head):
        raise click.ClickException(
            f"run {run} is a {source['event']} run of {source['headSha']}; accept a "
            f"workflow_dispatch run of HEAD ({head})"
        )
    with tempfile.TemporaryDirectory(prefix="leaf-thread-capture-") as download:
        download_artifact(run, Path(download))
        directory = Path(download) / CAPTURE.name
        marker = directory / "capture.json"
        if not marker.is_file():
            raise click.ClickException(
                f"run {run} made no successful capture; its artifact holds the evidence"
            )
        profile = json.loads(marker.read_text())["profile"]
        files = capture_files(directory, profile)
    with tempfile.TemporaryDirectory(prefix="leaf-thread-images-") as staging:
        checkout = leaf_assets.stage(
            ASSET_DIRECTORY,
            {f"{profile}/{name}": data for name, data in files.items()},
            Path(staging),
            replace_tree=True,
            revision_key="thread_snapshots_revision",
        )
        revision = leaf_assets.publish(
            checkout,
            f"Accept reviewed thread appearance for {profile} (run {run}, {head})",
        )
    click.echo(f"Accepted {len(files) // 2} thread images: {revision}")
