"""Approved thread appearance from an explicit, reviewed historical source.

The expectation is tests/snapshots/thread-source.json plus thread-source.patch, a
small text patch against a durable public main ancestor. Generated browser bundles
are rebuilt from approved build inputs and the JavaScript lock; no minified vendor
output is duplicated in the patch. Both arms use the same
browser/OS, so no PNG, platform-specific golden catalogue or external upload is
needed. The approved source runs its own Python server and browser runtime;
thread_snapshot_source owns extraction and caching. This is an explicit source
snapshot: merging a candidate never advances the reviewed baseline automatically.

The one real delivery journey supplies held-state appearance and delivery
assertions. pytest-image-snapshot compares pixels using Pixelmatch's antialias
handling and 0.01 perceptual tolerance. Three unchanged seven-case repeats
showed only two-level corner raster noise; this threshold excludes that noise
while detecting the measured seventeen-level ink change. There is
no whole-image allowance for mismatched pixels. Capture the
thread's region and its independently compared viewport geometry, so a translated
crop cannot hide bad placement. Refusal feedback is checked by visible words and
captured where it stands inside the thread region. The real notice must expire
before manual retry, so later checkpoints do not depend on capture speed. First insertion runs with normal
motion and its own observer; stable screenshots use the dependency's animation
settling, after that proof. They do not claim to capture the insertion instant.

    uv run leaf-dev thread-snapshots prepare
    uv run pytest -n0 tests/test_render_thread_snapshots.py
    uv run leaf-dev thread-snapshots accept

Appearance failures name their stage and expected/actual/diff paths; geometry
failures show both rectangles. Every case retains its images and observations.json;
CI retains the same folders. Review those images and summarize the changed
checkpoints before accepting. Acceptance changes the ordinary text source pin/patch;
prepare and re-run the test, then commit them with the intentional UI change. Missing source,
failed generation and changed cached bytes fail instead of silently accepting.
Setup co-renders the approved source; ordinary tests read its verified cache only.
Artifacts under .tmp/thread-snapshots are disposable evidence, never Git goldens.
Both arms share the browser, so a regression in a browser upgrade itself is outside
this oracle. A changed driver incompatible with old source requires refreshing the
approved source; do not add selector fallbacks.
"""

import io
import json
import platform
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
from PIL import Image
from playwright.sync_api import Page
from pytest_image_snapshot import ImageMismatchError

from leaf_dev import ROOT


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
    return f"{system}-{version}-{platform.machine()}-chromium-{browser_version}"


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
    """One case's captures, compared by the installed pytest image-snapshot fixture."""

    def __init__(
        self, browser_version, case, compare, *, output, store=None, updating=False
    ):
        self.profile = render_profile(browser_version)
        self.case = case
        self.compare = compare
        self.output = Path(output) / case.name
        self.output.mkdir(parents=True, exist_ok=True)
        if updating and store is None:
            raise ValueError("snapshot acceptance requires --thread-snapshot-store")
        self.store = (
            (Path(store) if Path(store).is_absolute() else ROOT / store)
            if store
            else None
        )
        if self.store is None:
            raise ValueError("source approval must provide an expected store")
        self.updating = updating
        self.failures = []
        self.observations = {}

    def capture(self, stage: str, page: Page, reading: dict) -> None:
        """Compare held appearance after the independently observed insertion instant."""
        # Capture the thread's own region, including feedback where it stands in it.
        # The journey holds visible refusal, then awaits real expiry before retry.
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
        if stage == "refused":
            notice = page.locator(".lf-notice")
            assert notice.is_visible() and notice.inner_text().startswith(
                "Couldn't send"
            ), "refusal feedback expired or changed during the capture"
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


@click.group("thread-snapshots")
def thread_snapshots():
    """Review and accept thread appearance as a squash-safe source snapshot."""


@thread_snapshots.command("prepare")
def prepare():
    """Materialize the approved cache during setup, with the gate's locked browser."""
    from playwright.sync_api import sync_playwright

    from leaf_dev.browser import headless_shell
    from leaf_dev.thread_snapshot_source import prepare_store

    with sync_playwright() as playwright, headless_shell(playwright) as browser:
        store = prepare_store(browser.version)
    click.echo(f"Prepared approved thread snapshots: {store}")


@thread_snapshots.command("accept")
def accept():
    """Accept current tracked source after reviewing the ordinary test's evidence."""
    from leaf_dev.thread_snapshot_source import PATCH, PIN, accept_source

    accept_source()
    click.echo(f"Accepted source: {PIN}\nPatch: {PATCH}")
    click.echo(
        "Prepare with uv run leaf-dev thread-snapshots prepare; then validate with uv run pytest -n0 tests/test_render_thread_snapshots.py"
    )
