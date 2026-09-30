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
from .screens import save_screens
from .version import RENDER_VIEWPORTS, render_version


def in_browser(gate: str, read):
    """Launch the host's browser and return what `read` finds with it, with the
    browser's name. A browser is part of the gate: where none launches, it reports
    that and returns None."""
    from playwright.sync_api import Error as PlaywrightError

    try:
        with playwright_driver() as p:
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
                return read(browser), browser_name
            finally:
                browser.close()
    except DriverNotStarted as error:
        print(
            f"✗ {gate} failed — Playwright's driver did not start: {error}. "
            f"{driver_hint()}",
            file=sys.stderr,
        )
        return None


def _in_browser(
    gate: str,
    read,
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> tuple[list[str], str] | None:
    """Serve the candidate source and return what `read` finds there (`in_browser`)."""
    with preview_server(
        page_dir, document, revision, transition_held=True, artifact=artifact
    ) as url:
        return in_browser(gate, lambda browser: read(browser, url))


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


def _read_and_shoot(page_dir: Path):
    """The gate's reading, and, for a page it passes, the screens the author reads."""

    def read(browser, url: str):
        reading = render_version(browser, url)
        if reading.failures:
            return reading, None
        return reading, save_screens(browser, url, reading, page_dir)

    return read


def _screen_lines(screens) -> list[str]:
    """One line per run of screens that show the same thing, under their directory."""
    into, saved = screens
    runs = []
    for shot, label in saved:
        if runs and runs[-1][1] == label:
            runs[-1][0].append(shot.name)
        else:
            runs.append(([shot.name], label))
    return [f"  screens to read before handing the page over, in {into}:"] + [
        f"    {names[0]}{' … ' + names[-1] if len(names) > 1 else ''}: {label}"
        for names, label in runs
    ]


def render_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> int:
    """Serve candidate source to the host's browser, run the render invariants on it,
    and save the screens the pre-handover review reads."""
    ran = _in_browser(
        "render check",
        _read_and_shoot(page_dir),
        page_dir,
        document,
        revision,
        artifact,
    )
    if ran is None:
        return 1
    (reading, screens), browser_name = ran
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
    margins = (
        ", light at "
        + ", ".join(f"{width}px" for width in reading.margin_widths)
        + " where its margin content changes"
        if reading.margin_widths
        else ""
    )
    print(
        f"✓ index.html: renders clean in {browser_name}, light and dark at "
        f"{viewport_names}{margins} — no "
        "console errors or DevTools issues, every widget takes space, no words on top of other words, code that reads "
        "against the block it is on, nothing past the "
        f"column, no sideways scroll from {SWEEP_WIDTHS[0]}px to {SWEEP_WIDTHS[-1]}px wide"
    )
    for line in reading.advice:
        print(f"  · {line}")
    for line in _screen_lines(screens):
        print(line)
    return 0


def widget_quality_report(package: Path) -> int:
    """Print what the widget quality checks find in the package's own widgets
    (`widget_quality`). A finding is advice and leaves the status 0; a page of worked
    examples that never presents leaves nothing to read, and is 1."""
    from .widget_quality import CHECKS, UnreadablePage, own_tags, widget_findings

    try:
        ran = in_browser(
            "widget quality", lambda browser: widget_findings(browser, package)
        )
    except UnreadablePage as error:
        print(
            f"✗ widget quality failed — a page of worked examples never presented: "
            f"{error}",
            file=sys.stderr,
        )
        return 1
    if ran is None:
        return 1
    findings, browser_name = ran
    widgets = f"{len(own_tags(package))} widget(s)"
    if not findings:
        print(f"✓ widget quality: {widgets} pass {', '.join(CHECKS)} in {browser_name}")
        return 0
    print(
        f"widget quality: {len(findings)} finding(s) for {widgets} in {browser_name}, "
        "advice for the widgets' author:"
    )
    for finding in findings:
        print(f"  · {finding}")
    return 0
