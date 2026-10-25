"""Reviewed PNG expectations for one real message-delivery journey.

Images and viewport geometry live in max-sixty/leaf-assets, pinned by the existing
leaf-assets.json's thread_snapshots_revision. Tests compare current Leaf directly
against that immutable set;
no historical runtime, source patch or baseline build is involved. Fonts and
antialiasing differ by OS, so each OS compares against its own profile, named by the
OS version, architecture and locked Chromium version. A missing profile fails, so
browser upgrades require deliberately reviewed captures. Appearance is compared on
macOS and Linux. `capture --linux` renders CI's Linux profile on any machine, in
Playwright's image for the locked version: Ubuntu 24.04 on x86_64, as CI's runner is.
The image runs as x86_64 because an arm64 render rounds colours differently across
whole regions. On Apple Silicon that needs Rosetta (Colima's `--vz-rosetta`, or Docker
Desktop's Rosetta setting), since Chromium's GPU process crashes under QEMU. Elsewhere
the journey and its delivery assertions still run and keep their images as evidence,
except in the dark cases, whose colour scheme changes only pixels.
Existing fetch-assets warms the same cache as every other asset reader.

    uv run pytest -n0 tests/*/test_render_thread_snapshots.py
    uv run leaf-dev thread-snapshots capture [--linux]
    uv run leaf-dev thread-snapshots accept .tmp/thread-snapshots/captures/<run>

Capture runs the same journey and hard delivery assertions, writing all 48 PNG images and
geometry readings to a new evidence folder. Review its actual images and observations,
then accept replaces that profile within the pinned collection, publishes through
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

import hashlib
import io
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.metadata import version
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


# The platforms whose appearance is reviewed and compared.
COMPARED = sys.platform in ("darwin", "linux")


def render_profile(browser_version: str) -> str:
    """The rendering environment whose images this run can compare meaningfully."""
    system = (
        f"darwin-{platform.mac_ver()[0]}"
        if sys.platform == "darwin"
        else f"linux-{platform.freedesktop_os_release()['VERSION_ID']}"
    )
    return f"{system}-{platform.machine()}-chromium-{browser_version}"


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


def expected_store() -> Path:
    """The immutable PNG tree selected by this checkout's reviewed expectations."""
    return (
        leaf_assets.pinned_assets(revision_key="thread_snapshots_revision")
        / ASSET_DIRECTORY
    )


@click.group()
def thread_snapshots():
    """Capture, review and publish current Leaf's thread appearance."""


def capture_command(store: str) -> list[str]:
    """The pytest arguments that capture every case into `store`."""
    return [
        "pytest",
        "-n0",
        "-q",
        "--image-snapshot-update",
        "--thread-snapshot-store",
        store,
        "tests/journeys/test_render_thread_snapshots.py::test_message_delivery_appearance_and_first_frame",
    ]


# CI's runner is ubuntu-24.04 on x86_64 with Playwright's browsers and fonts-dejavu
# (`leaf-dev setup`); the image matches its OS release and browser build.
LINUX_PLATFORM = "linux/amd64"
LINUX_BOOTSTRAP = """set -euo pipefail
export DEBIAN_FRONTEND=noninteractive PATH="$HOME/.local/bin:$PATH"
apt-get update -qq
apt-get install -y -qq fonts-dejavu git >/dev/null
curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
apt-get install -y -qq nodejs >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
mkdir -p /work
tar -xf - -C /work
cd /work
git init -q
git add -A
git -c user.name=capture -c user.email=capture@localhost commit -qm capture
corepack enable
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 pnpm install --frozen-lockfile --reporter=silent
uv run --frozen leaf-dev fetch-assets
exec uv run --frozen "$@"
"""


def working_tree_tar() -> bytes:
    """The checkout as it stands, tracked and untracked files alike, minus ignored ones."""
    names = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for name in filter(None, names):
            path = ROOT / os.fsdecode(name)
            if path.is_symlink() or path.exists():
                tar.add(path, arcname=os.fsdecode(name), recursive=False)
    return archive.getvalue()


def linux_capture(directory: Path) -> subprocess.CompletedProcess:
    """Run the capture in Playwright's image for the locked version, on CI's platform."""
    runs = ROOT / ".tmp/thread-snapshots/runs"
    runs.mkdir(parents=True, exist_ok=True)
    image = f"mcr.microsoft.com/playwright/python:v{version('playwright')}-noble"
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--platform",
            LINUX_PLATFORM,
            "--ipc=host",
            "-v",
            f"{directory}:/capture",
            "-v",
            f"{runs}:/work/.tmp/thread-snapshots/runs",
            image,
            "bash",
            "-c",
            LINUX_BOOTSTRAP,
            "bootstrap",
            *capture_command("/capture"),
        ],
        input=working_tree_tar(),
        check=False,
    )


@thread_snapshots.command("capture")
@click.option(
    "--linux",
    is_flag=True,
    help="Capture CI's Linux profile in a container (needs Docker running x86_64).",
)
def capture(linux: bool):
    """Run all delivery assertions and capture current appearance for review."""
    if not (linux or COMPARED):
        raise click.ClickException(
            "thread appearance is captured on macOS or Linux; pass --linux"
        )
    directory = ROOT / ".tmp/thread-snapshots/captures" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    result = (
        linux_capture(directory)
        if linux
        else subprocess.run(
            [sys.executable, "-m", *capture_command(str(directory))],
            cwd=ROOT,
            check=False,
        )
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
    """Publish a complete, reviewed capture and update the expectations pin."""
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
    # Preserve this runtime's other reviewed profiles, never the asset head's.
    baseline = expected_store()
    collection = {
        path.relative_to(baseline).as_posix(): path.read_bytes()
        for path in baseline.rglob("*")
        if path.is_file() and path.relative_to(baseline).parts[0] != profile
    }
    collection.update({f"{profile}/{name}": data for name, data in files.items()})
    with tempfile.TemporaryDirectory(prefix="leaf-thread-images-") as staging:
        checkout = leaf_assets.stage(
            ASSET_DIRECTORY,
            collection,
            Path(staging),
            replace_tree=True,
            revision_key="thread_snapshots_revision",
        )
        revision = leaf_assets.publish(
            checkout, f"Accept reviewed thread appearance for {profile}"
        )
    click.echo(f"Accepted {len(files) // 2} thread images: {revision}")
    click.echo(
        "Validate with uv run pytest -n0 tests/*/test_render_thread_snapshots.py"
    )
