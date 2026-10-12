"""Command boundary for browser-backed page validation."""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument

from .browser import (
    DriverNotStarted,
    browser_hint,
    driver_hint,
    ending,
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
    browser's name. Where none launches, say that `gate` was not run and why, and
    return None: Leaf runs without a browser, and a page reports its errors to its
    author whenever one draws it, so a host without one loses the early reading and
    not the command.

    Playwright runs on a thread of its own. Its sync API refuses a thread that already
    drives another instance or runs an event loop, and a command runs this from
    whatever process called it, such as a test harness driving its own browser."""
    with ThreadPoolExecutor(1) as pool:
        found = pool.submit(_launch, read).result()
    if isinstance(found, str):
        print(f"· {gate}: not run, {found}", file=sys.stderr)
        return None
    return found


def _launch(read):
    """What `read` finds, with the browser's name, or why no browser ran it."""
    from playwright.sync_api import Error as PlaywrightError

    try:
        with playwright_driver() as p:
            try:
                browser, browser_name = launch_browser(p)
            except PlaywrightError as error:
                return (
                    f"no browser launched: {str(error).strip().splitlines()[0]}. "
                    f"{browser_hint()}"
                )
            with ending(browser):
                return read(browser), browser_name
    except DriverNotStarted as error:
        return f"Playwright's driver did not start: {error}. {driver_hint()}"


def browser_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
    *,
    page_code: bool,
    render: bool,
) -> int:
    """Serve the candidate source once and, in one browser, run the page's own code
    (`page_code` says which run and which errors fail it), then the render invariants,
    saving the screens the pre-handover review reads for a page they pass. Page code
    that fails ends the check before the render reading."""
    gates = [
        gate
        for gate, wanted in (("page code", page_code), ("render check", render))
        if wanted
    ]

    def read(browser, url: str):
        errors = run_page_code(browser, url) if page_code else []
        if errors or not render:
            return errors, None
        reading = render_version(browser, url)
        if reading.failures:
            return errors, (reading, None)
        return errors, (reading, save_screens(browser, url, reading, page_dir))

    with preview_server(
        page_dir, document, revision, transition_held=True, artifact=artifact
    ) as url:
        ran = in_browser(" and ".join(gates), lambda browser: read(browser, url))
    if ran is None:
        return 0
    (errors, rendered), browser_name = ran
    if page_code and _page_code_verdict(errors, browser_name):
        return 1
    return _render_verdict(*rendered, browser_name) if rendered else 0


def _page_code_verdict(errors: list[str], browser_name: str) -> int:
    if errors:
        print(
            f"Error: page code reported {len(errors)} error{'s' if len(errors) != 1 else ''}",
            file=sys.stderr,
        )
        for error in errors:
            print("  - " + error.replace("\n", "\n    "), file=sys.stderr)
        return 1
    print(f"✓ page code: no errors in {browser_name}")
    return 0


def _screen_lines(screens) -> list[str]:
    """One line per run of screens that show the same thing, under their directory."""
    into, saved = screens
    runs = []
    for shot, label in saved:
        if runs and runs[-1][1] == label:
            runs[-1][0].append(shot.name)
        else:
            runs.append(([shot.name], label))
    return (
        [f"  screens to read before handing the page over, in {into}:"]
        + [
            f"    {names[0]}{' … ' + names[-1] if len(names) > 1 else ''}: {label}"
            for names, label in runs
        ]
        + [
            (
                "  before handover, have a subagent with only the user's request and "
                "these screens read the page as the user would "
                '(page-authoring.md, "Pre-handover review")'
            )
        ]
    )


def _render_verdict(reading, screens, browser_name: str) -> int:
    if reading.failures:
        print(
            f"Error: index.html has {len(reading.failures)} render issue{'s' if len(reading.failures) != 1 else ''}",
            file=sys.stderr,
        )
        for f in reading.failures:
            print("  - " + f.replace("\n", "\n    "), file=sys.stderr)
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
        f"✓ index.html: render checks passed in {browser_name}, light and dark at "
        f"{viewport_names}{margins}; widths {SWEEP_WIDTHS[0]}–{SWEEP_WIDTHS[-1]}px"
    )
    for line in reading.advice:
        print(f"  · {line}")
    for line in _screen_lines(screens):
        print(line)
    return 0


def widget_quality_report(package: Path) -> int:
    """Print what the widget quality checks find in the package's own widgets
    (`widget_quality`). A finding is advice and leaves the status 0; a page of worked
    examples that cannot be drawn leaves nothing to read, and is 1."""
    from .widget_quality import CHECKS, UnreadablePage, own_tags, widget_findings

    try:
        ran = in_browser(
            "widget quality", lambda browser: widget_findings(browser, package)
        )
    except UnreadablePage as error:
        print(
            f"Error: widget examples could not be drawn: {error}",
            file=sys.stderr,
        )
        return 1
    if ran is None:
        return 0
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
