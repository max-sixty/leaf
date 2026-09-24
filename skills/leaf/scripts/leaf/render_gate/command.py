"""Command boundary for browser-backed page validation."""

import sys
from pathlib import Path

from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument

from .browser import (
    DriverNotStarted,
    browser_hint,
    driver_hint,
    launch_browser,
    playwright_driver,
)
from .page_code import run_page_code
from .preview import preview_server
from .readings import SWEEP_WIDTHS
from .version import RENDER_VIEWPORTS, render_version


def _in_browser(
    gate: str,
    read,
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> tuple[list[str], str] | None:
    """Serve the candidate source to the host's browser and return what `read`
    finds there, with the browser's name. A browser is part of each gate that
    calls this: where none launches, it reports that and returns None."""
    from playwright.sync_api import Error as PlaywrightError

    try:
        with (
            preview_server(
                page_dir,
                document,
                revision,
                transition_held=True,
                artifact=artifact,
            ) as url,
            playwright_driver() as p,
        ):
            try:
                browser, browser_name = launch_browser(p)
            except PlaywrightError as error:
                print(
                    f"✗ {gate} failed — no browser launched: "
                    f"{str(error).strip().splitlines()[0]}. {browser_hint()}",
                    file=sys.stderr,
                )
                return None
            try:
                return read(browser, url), browser_name
            finally:
                browser.close()
    except DriverNotStarted as error:
        print(
            f"✗ {gate} failed — Playwright's driver did not start: {error}. "
            f"{driver_hint()}",
            file=sys.stderr,
        )
        return None


def page_code_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> int:
    """Run the page's own code once and fail on every error it reports
    (`page_code` says which run and which errors)."""
    ran = _in_browser(
        "page code check", run_page_code, page_dir, document, revision, artifact
    )
    if ran is None:
        return 1
    errors, browser_name = ran
    if errors:
        print(
            f"✗ page code: {len(errors)} error(s) the page would report to you",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(
        f"✓ page code: runs through upgrade and first paint in {browser_name} "
        "with no error reported"
    )
    return 0


def render_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> int:
    """Serve candidate source to the host's browser and run the render
    invariants on it."""
    ran = _in_browser(
        "render check", render_version, page_dir, document, revision, artifact
    )
    if ran is None:
        return 1
    reading, browser_name = ran
    if reading.failures:
        print(
            f"✗ index.html: renders broken — {len(reading.failures)} issue(s)",
            file=sys.stderr,
        )
        for f in reading.failures:
            print(f"  - {f}", file=sys.stderr)
        for line in reading.advice:
            print(f"  · {line}", file=sys.stderr)
        return 1
    viewport_names = " and ".join(
        f"{viewport['width']}x{viewport['height']}" for viewport in RENDER_VIEWPORTS
    )
    print(
        f"✓ index.html: renders clean in {browser_name}, light and dark at "
        f"{viewport_names} — no "
        "console errors, every widget takes space, no words on top of other words, code that reads "
        "against the block it is on, boxes showing the inset they draw, nothing past the "
        f"column, no sideways scroll from {SWEEP_WIDTHS[0]}px to {SWEEP_WIDTHS[-1]}px wide"
    )
    for line in reading.advice:
        print(f"  · {line}")
    return 0
