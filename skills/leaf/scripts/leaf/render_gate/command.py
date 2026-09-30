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


def _in_browser(
    gate: str,
    read,
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> tuple[list[str], str] | None:
    """Serve the candidate source to the host's browser and return what `read`
    finds there, with the browser's name. A browser is part of the gate: where none
    launches, it reports that and returns None.

    Playwright runs on a thread of its own. Its sync API refuses a thread that already
    drives another instance or runs an event loop, and a thread command runs this from
    whatever process called it."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(
            _browse, gate, read, page_dir, document, revision, artifact
        ).result()


def _browse(
    gate: str,
    read,
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> tuple[list[str], str] | None:
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


def _code_errors(
    what: str,
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> str | None:
    """Run `document` once and print every error it reports under `what`; the
    browser's name where it reports none."""
    ran = _in_browser(
        f"{what} check", run_page_code, page_dir, document, revision, artifact
    )
    if ran is None:
        return None
    errors, browser_name = ran
    if errors:
        print(
            f"✗ {what}: {len(errors)} error(s) the page would report to you",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return None
    return browser_name


def page_code_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
) -> int:
    """Run the page's own code once and fail on every error it reports
    (`page_code` says which run and which errors)."""
    browser_name = _code_errors("page code", page_dir, document, revision, artifact)
    if browser_name is None:
        return 1
    print(
        f"✓ page code: runs through upgrade and first paint in {browser_name} "
        "with no error reported"
    )
    return 0


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
    return 0 if _code_errors(what, page_dir, document, revision, artifact) else 1


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
