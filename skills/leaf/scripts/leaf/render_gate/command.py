"""Command boundary for browser-backed page validation.

The checks return findings (`findings.py`); this module and `validation/command.py`
are where they become output: lines for a reader, or the `--json` document."""

import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from leaf.findings import Finding
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
from .version import RENDER_VIEWPORTS, RenderReading, render_version


class NoBrowser(Exception):
    """No browser ran: the message says why."""


def run_in_browser(read):
    """Launch the host's browser and return what `read` finds with it, with the
    browser's name, or raise `NoBrowser`. Leaf runs without a browser, and a page
    reports its errors to its author whenever one draws it, so a host without one loses
    the early reading and not the command.

    Playwright runs on a thread of its own. Its sync API refuses a thread that already
    drives another instance or runs an event loop, and a command runs this from
    whatever process called it, such as a test harness driving its own browser."""
    with ThreadPoolExecutor(1) as pool:
        found = pool.submit(_launch, read).result()
    if isinstance(found, str):
        raise NoBrowser(found)
    return found


def not_run(gate: str, why: str) -> None:
    print(f"· {gate}: not run, {why}", file=sys.stderr)


def in_browser(gate: str, read):
    """`run_in_browser`, saying that `gate` was not run and why where no browser ran,
    and then returning None."""
    try:
        return run_in_browser(read)
    except NoBrowser as error:
        not_run(gate, str(error))
        return None


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


@dataclass(frozen=True, slots=True)
class BrowserCheck:
    """What the browser gates read of the candidate: `gates` names those asked for;
    `unavailable` says why no browser ran them, or is None where `browser` did. Page
    code that fails ends the check before the render reading, so `render` is None
    there as well as where it was not asked for, and `ran` names only the gates that
    read the page. `screens` is the directory and each
    saved screen with what it shows, for a page the render gate passed."""

    gates: list[str]
    browser: str | None = None
    unavailable: str | None = None
    page_code: list[Finding] | None = None
    render: RenderReading | None = None
    screens: tuple[Path, list[tuple[Path, str]]] | None = None

    @property
    def status(self) -> int:
        failed = (self.page_code or []) + (self.render.failures if self.render else [])
        return 1 if failed else 0

    def findings(self) -> list[Finding]:
        return [*(self.page_code or []), *(self.render.findings if self.render else [])]

    @property
    def ran(self) -> list[str]:
        return [
            gate
            for gate, reading in (
                ("page code", self.page_code),
                ("render check", self.render),
            )
            if reading is not None
        ]

    def json(self) -> dict:
        reading = {"asked": self.gates, "ran": self.ran, "browser": self.browser}
        if self.unavailable is not None:
            reading["unavailable"] = self.unavailable
        if self.render is not None:
            reading["margin_widths"] = self.render.margin_widths
        if self.screens is not None:
            into, saved = self.screens
            reading["screens"] = {
                "directory": str(into),
                "files": [{"file": shot.name, "shows": label} for shot, label in saved],
            }
        return reading


def browser_check(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    artifact: RevisionArtifact,
    *,
    page_code: bool,
    render: bool,
) -> BrowserCheck:
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
        errors = run_page_code(browser, url) if page_code else None
        if errors or not render:
            return errors, None, None
        reading = render_version(browser, url)
        if reading.failures:
            return errors, reading, None
        return errors, reading, save_screens(browser, url, reading, page_dir)

    with preview_server(
        page_dir, document, revision, transition_held=True, artifact=artifact
    ) as url:
        try:
            (errors, reading, screens), browser_name = run_in_browser(
                lambda browser: read(browser, url)
            )
        except NoBrowser as error:
            return BrowserCheck(gates, unavailable=str(error))
    return BrowserCheck(gates, browser_name, None, errors, reading, screens)


def print_browser_check(check: BrowserCheck) -> int:
    """Say what the browser gates found, for a reader, and return the status."""
    if check.unavailable is not None:
        not_run(" and ".join(check.gates), check.unavailable)
        return 0
    if check.page_code is not None and _page_code_verdict(
        check.page_code, check.browser
    ):
        return 1
    if check.render is None:
        return 0
    return _render_verdict(check.render, check.screens, check.browser)


def _page_code_verdict(errors: list[Finding], browser_name: str) -> int:
    if errors:
        print(
            f"Error: page code reported {len(errors)} error{'s' if len(errors) != 1 else ''}",
            file=sys.stderr,
        )
        for error in errors:
            print("  - " + str(error).replace("\n", "\n    "), file=sys.stderr)
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
                '(page-checkpoints.md, "Pre-handover review")'
            )
        ]
    )


def _render_verdict(reading: RenderReading, screens, browser_name: str) -> int:
    failures = reading.failures
    if failures:
        print(
            f"Error: index.html has {len(failures)} render issue{'s' if len(failures) != 1 else ''}",
            file=sys.stderr,
        )
        for f in failures:
            print("  - " + str(f).replace("\n", "\n    "), file=sys.stderr)
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


@dataclass(frozen=True, slots=True)
class WidgetQuality:
    """What `package check --render` read of the package's `widgets`: its findings
    and the browser that drew the worked examples, or why no browser could. A finding
    is advice for the widgets' author, apart from examples that could not be drawn
    (`unreadable-examples`), which leave nothing to read and fail the check."""

    widgets: int
    browser: str | None = None
    unavailable: str | None = None
    findings: tuple[Finding, ...] = ()

    @property
    def status(self) -> int:
        return 1 if any(f.severity == "error" for f in self.findings) else 0

    def json(self) -> dict:
        """The browser reading, in the shape `BrowserCheck.json` gives it."""
        ran = [] if self.unavailable is not None else ["widget quality"]
        reading = {"asked": ["widget quality"], "ran": ran, "browser": self.browser}
        if self.unavailable is not None:
            reading["unavailable"] = self.unavailable
        return reading


def widget_quality(package: Path) -> WidgetQuality:
    """Read the widget quality checks (`widget_quality`) of the package's own
    widgets in the host's browser."""
    from .widget_quality import UnreadablePage, own_tags, widget_findings

    def read(browser):
        try:
            return widget_findings(browser, package)
        except UnreadablePage as error:
            return [Finding("unreadable-examples", values={"error": str(error)})]

    widgets = len(own_tags(package))
    try:
        findings, browser_name = run_in_browser(read)
    except NoBrowser as error:
        return WidgetQuality(widgets, unavailable=str(error))
    return WidgetQuality(widgets, browser_name, findings=tuple(findings))


def print_widget_quality(check: WidgetQuality) -> int:
    """Say what the widget quality checks found, for a reader, and return the
    status."""
    from .widget_quality import CHECKS

    if check.unavailable is not None:
        not_run("widget quality", check.unavailable)
        return 0
    if check.status:
        for finding in check.findings:
            print(f"Error: {finding}", file=sys.stderr)
        return check.status
    widgets = f"{check.widgets} widget(s)"
    if not check.findings:
        print(
            f"✓ widget quality: {widgets} pass {', '.join(CHECKS)} in {check.browser}"
        )
        return 0
    print(
        f"widget quality: {len(check.findings)} finding(s) for {widgets} in "
        f"{check.browser}, advice for the widgets' author:"
    )
    for finding in check.findings:
        print(f"  · {finding}")
    return 0
