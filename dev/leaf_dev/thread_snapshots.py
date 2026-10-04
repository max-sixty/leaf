"""Reviewed PNG expectations for one real message-delivery journey.

Images and viewport geometry live in max-sixty/leaf-assets, pinned by the existing
leaf-assets.json. Tests compare current Leaf directly against that immutable set;
no historical runtime, source patch or baseline build is involved. Each rendering
profile names the OS, architecture and locked Chromium version. Linux also binds
the shared native fontconfig and installed DejaVu font bytes. Missing profiles
fail: browser upgrades require deliberately reviewed captures, including the Linux
CI profile. Existing fetch-assets warms the same cache as every other asset reader.

    uv run pytest -n0 tests/test_render_thread_snapshots.py
    uv run leaf-dev thread-snapshots capture
    uv run leaf-dev thread-snapshots accept .tmp/thread-snapshots/captures/<run>

Capture runs the same journey and hard delivery assertions, writing all 42 PNG images and
geometry readings to a new evidence folder. Review its actual images and observations,
then accept publishes that profile through leaf_assets.stage / publish and updates
the ordinary asset pin. Acceptance never occurs in normal tests. CI retains failed
run evidence. Small antialias noise is excluded by Pixelmatch's AA handling and
calibrated 0.01 perceptual tolerance; every other mismatched pixel fails, with no
whole-image allowance. Independently compare viewport geometry so a translated crop
cannot conceal placement changes.

First insertion has an immediate words/busy/opacity observer before stabilized
screenshots. Refusal's exact feedback and native visibility are observed at mutation;
its real expiry precedes the restored-draft capture. Transient notice styling is
outside the pixel oracle and retains its ordinary rendered lifecycle tests. Capture
hides only editor carets, preserving draft words, focus and selection. Seven bounded
cases cover general, panel, margin, inline diff, dark and narrow appearances;
they do not claim all thread states. Existing news/storage tests remain separate.
"""

import hashlib
import io
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
from PIL import Image
from playwright.sync_api import Page
from pytest_image_snapshot import ImageMismatchError

from leaf_dev import ROOT, leaf_assets
from leaf_dev.browser import linux_font_fingerprint
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
    Case("margin-dark", "margin", scheme="dark", motion="reduce"),
    Case("panel-dark", "panel", scheme="dark", motion="reduce"),
    Case("panel-narrow", "panel", viewport=(390, 740)),
)


def render_profile(browser_version: str) -> str:
    """The rendering environment whose images this run can compare meaningfully."""
    system = platform.system().lower()
    version = (
        platform.mac_ver()[0]
        if system == "darwin"
        else platform.freedesktop_os_release()["VERSION_ID"]
    )
    fonts = f"-fonts-{linux_font_fingerprint()}" if system == "linux" else ""
    return f"{system}-{version}-{platform.machine()}-chromium-{browser_version}{fonts}"


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
        self.profile = render_profile(browser_version)
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
        with hidden_editor_carets(page):
            png = page.screenshot(
                caret="hide", scale="css", clip=clip, animations="disabled"
            )
        actual = self.output / f"{stage}.actual.png"
        actual.write_bytes(png)
        baseline = self.store / self.profile / f"{self.case.name}-{stage}.png"
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
        expected = baseline if self.updating else self.output / f"{stage}.expected.png"
        expected.parent.mkdir(parents=True, exist_ok=True)
        if not self.updating and baseline.is_file():
            shutil.copyfile(baseline, expected)
        self.observations[stage] = reading
        try:
            # Pixelmatch ignores antialias edges and small perceptual color changes.
            # Every remaining mismatch fails; there is no whole-image allowance.
            self.compare(Image.open(io.BytesIO(png)), expected, threshold=0.01)
        except ImageMismatchError:
            self.failures.append(
                f"{stage}: appearance changed\n"
                f"Expected: {expected}\nActual: {actual}\n"
                f"Diff: {expected.with_suffix('.diff.png')}"
            )

    def finish(self) -> None:
        """Report every changed checkpoint together after the journey completes."""
        assert not self.failures, (
            "\n".join(self.failures)
            + f"\nReadings: {self.output / 'observations.json'}\nEvidence: {self.output}"
        )


ASSET_DIRECTORY = "tests/thread-snapshots"


def expected_store() -> Path:
    """The immutable PNG tree every checkout's ordinary asset pin governs."""
    return leaf_assets.pinned_assets() / ASSET_DIRECTORY


@click.group("thread-snapshots")
def thread_snapshots():
    """Capture, review and publish current Leaf's thread appearance."""


@thread_snapshots.command("capture")
def capture():
    """Run all delivery assertions and capture current appearance for review."""
    directory = ROOT / ".tmp/thread-snapshots/captures" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-n0",
            "-q",
            "--image-snapshot-update",
            "--thread-snapshot-store",
            str(directory),
            "tests/test_render_thread_snapshots.py::test_message_delivery_appearance_and_first_frame",
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        raise click.ClickException(
            f"capture assertions failed; review evidence in {directory}"
        )
    (profile,) = (path.name for path in directory.iterdir() if path.is_dir())
    files = capture_files(directory, profile)

    (directory / "capture.json").write_text(
        json.dumps(
            {
                "profile": profile,
                "sha256": {
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in files.items()
                },
            },
            indent=2,
        )
        + "\n"
    )
    click.echo(
        f"Review captures: {directory}\nAccept: uv run leaf-dev thread-snapshots accept {directory}"
    )


def capture_files(directory: Path, profile: str) -> dict[str, bytes]:
    """Require every named checkpoint and its independently read geometry."""
    files = {}
    for case in CASES:
        for stage in STAGES:
            for suffix in ("png", "json"):
                name = f"{case.name}-{stage}.{suffix}"
                path = directory / profile / name
                if not path.is_file():
                    raise click.ClickException(f"missing capture: {path}")
                files[name] = path.read_bytes()
    return files


@thread_snapshots.command("accept")
@click.argument(
    "directory", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
def accept(directory: Path):
    """Publish a complete, reviewed capture and update Leaf's immutable asset pin."""
    marker = directory / "capture.json"
    if not marker.is_file():
        raise click.ClickException(f"not a successful capture: {directory}")
    captured = json.loads(marker.read_text())
    profile = captured["profile"]
    files = capture_files(directory, profile)
    if captured["sha256"] != {
        name: hashlib.sha256(data).hexdigest() for name, data in files.items()
    }:
        raise click.ClickException(
            f"capture changed after its assertions passed: {directory}"
        )
    with tempfile.TemporaryDirectory(prefix="leaf-thread-images-") as staging:
        checkout = leaf_assets.stage(
            f"{ASSET_DIRECTORY}/{profile}", files, Path(staging)
        )
        revision = leaf_assets.publish(
            checkout, f"Accept reviewed thread appearance for {profile}"
        )
    click.echo(f"Accepted {len(files) // 2} thread images: {revision}")
    click.echo("Validate with uv run pytest -n0 tests/test_render_thread_snapshots.py")
