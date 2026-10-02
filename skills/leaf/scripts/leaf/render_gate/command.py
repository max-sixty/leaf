"""Command boundary for browser-backed page validation."""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from leaf.files import latest_revision
from leaf.registry.storage import read_page_registry
from leaf.revision_artifact import RevisionArtifact, capture_artifact, read_artifact
from leaf.structure import SourceDocument

from .browser import (
    DriverNotStarted,
    browser_hint,
    driver_hint,
    launch_browser,
    playwright_driver,
)
from .page_code import message_page, places_judged_widget, run_page_code
from .preview import preview_server
from .readings import SWEEP_WIDTHS
from .screens import save_screens
from .version import RENDER_VIEWPORTS, render_version


class NoBrowser(Exception):
    """The host has no browser to run a gate in: why, and the hint that fixes it."""


def in_browser(read):
    """Launch the host's browser and return what `read` finds with it, with the
    browser's name, or raise NoBrowser where none launches. Each gate says what that
    means for it: one the author asked for fails, and the run plain `page check` and
    message markup take is skipped, since the page reports the same errors to its
    author whenever a browser draws it.

    Playwright runs on a thread of its own. Its sync API refuses a thread that already
    drives another instance or runs an event loop, and a thread command runs this from
    whatever process called it."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(_launch, read).result()


def _launch(read):
    from playwright.sync_api import Error as PlaywrightError

    try:
        with playwright_driver() as p:
            try:
                browser, browser_name = launch_browser(p)
            except PlaywrightError as error:
                raise NoBrowser(
                    f"no browser launched: {str(error).strip().splitlines()[0]}. "
                    f"{browser_hint()}"
                ) from None
            try:
                return read(browser), browser_name
            finally:
                browser.close()
    except DriverNotStarted as error:
        raise NoBrowser(
            f"Playwright's driver did not start: {error}. {driver_hint()}"
        ) from None


def _in_browser(
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
        return in_browser(lambda browser: read(browser, url))


def _code_errors(
    what: str,
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> tuple[int, str | None]:
    """Run `document` once and print every error it reports under `what`. Returns
    the status and the browser that ran it, None where the host has none."""
    try:
        errors, browser_name = _in_browser(
            run_page_code, page_dir, document, revision, artifact
        )
    except NoBrowser as reason:
        print(
            f"· {what}: not run, {reason} Its errors reach you as the page's `error` "
            "events once a browser draws it.",
            file=sys.stderr,
        )
        return 0, None
    if errors:
        print(
            f"✗ {what}: {len(errors)} error(s) the page would report to you",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1, browser_name
    return 0, browser_name


def page_code_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> int:
    """Run the page's own code once and fail on every error it reports
    (`page_code` says which run and which errors)."""
    status, browser_name = _code_errors(
        "page code", page_dir, document, revision, artifact
    )
    if browser_name and not status:
        print(
            f"✓ page code: runs through upgrade and first paint in {browser_name} "
            "with no error reported"
        )
    return status


def message_code_check(page_dir: Path, kind: str, fragment: SourceDocument) -> int:
    """Run a message's widget markup once, as a page of its own
    (`page_code.message_page`), where it places what only a browser can judge, and
    fail on every error it reports. The log freezes the markup, so this is the one
    moment its author can still fix it. Prints nothing when it passes: the thread
    command's output is the records it appends."""
    document = message_page(fragment)
    # The markup is read under the active revision's vocabulary, as the live document
    # that shows it reads it, and under the candidate's before the first activation.
    active = latest_revision(page_dir)
    if active is None:
        candidate = read_page_registry(page_dir)
        registry = candidate.registry
        declarations = candidate.declaration_sources
        widgets = candidate.widget_sources
    else:
        captured = read_artifact(page_dir, active)
        registry = captured.registry
        declarations = None
        widgets = {
            tag: implementation["path"].removeprefix("/")
            for tag, implementation in captured.implementations.items()
        }
    artifact = capture_artifact(
        page_dir,
        document,
        registry,
        declaration_sources=declarations,
        widget_sources=widgets,
    )
    if not places_judged_widget(document, artifact):
        return 0
    revision = (active or 0) + 1
    what = f"{kind} markup"
    return _code_errors(what, page_dir, document, revision, artifact)[0]


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


def render_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> int:
    """Serve candidate source to the host's browser, run the render invariants on it,
    and save the screens the pre-handover review reads."""
    try:
        ran = _in_browser(
            _read_and_shoot(page_dir), page_dir, document, revision, artifact
        )
    except NoBrowser as reason:
        print(f"✗ render check failed — {reason}", file=sys.stderr)
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
    examples that cannot be drawn leaves nothing to read, and is 1."""
    from .widget_quality import CHECKS, UnreadablePage, own_tags, widget_findings

    try:
        ran = in_browser(lambda browser: widget_findings(browser, package))
    except NoBrowser as reason:
        print(f"✗ widget quality failed — {reason}", file=sys.stderr)
        return 1
    except UnreadablePage as error:
        print(
            f"✗ widget quality failed — a page of worked examples could not be drawn: "
            f"{error}",
            file=sys.stderr,
        )
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
