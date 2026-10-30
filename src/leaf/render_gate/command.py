"""Command boundary for browser-backed page validation.

The checks return findings (`findings.py`); this module and `validation/command.py`
are where they become the JSON document `page check` and `package check` print."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from leaf.findings import Finding
from leaf.render_checks import RENDER_VIEWPORT
from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument
from leaf.user_views import read_user_views

from .browser import browser_hint, launch_browser
from .page_code import run_page_code
from .preview import preview_server
from .screens import save_screens
from .version import RenderReading, render_version

# Set to `fixed` by a caller whose verdicts must not depend on who viewed the page: the
# suite, CI, evals and leaf-dev's children (`leaf_dev.arms.environment`).
PIN_VARIABLE = "LEAF_RENDER_VIEWPORT"


@dataclass(frozen=True, slots=True)
class Desktop:
    """The desktop window the render check reads at, and why that one."""

    width: int
    height: int
    source: str

    @property
    def viewport(self) -> dict:
        return {"width": self.width, "height": self.height}

    def json(self) -> dict:
        return {"width": self.width, "height": self.height, "from": self.source}


def desktop_viewport(page_dir: Path) -> Desktop:
    """The window of the browser that last reported viewing the page, so the check
    reads the page as its reader sees it, or the fixed laptop window
    (`render_checks.RENDER_VIEWPORT`) when no browser has reported in the last day or
    the caller pins it with `LEAF_RENDER_VIEWPORT=fixed`.

    The window is the report's layout viewport, not its `shown_window`: the gate
    draws Leaf's own panel into that viewport, as the user's browser did, so the panel
    takes its own room again. A day is how long the page keeps a report
    (`user_views.RETAIN_FOR`); a reader's window size changes rarely, so any report
    the page still keeps is a better guess than the fixed window."""
    pin = os.environ.get(PIN_VARIABLE)
    if pin not in (None, "", "fixed"):
        raise ValueError(f"{PIN_VARIABLE} takes only 'fixed', not {pin!r}")
    fixed = RENDER_VIEWPORT["width"], RENDER_VIEWPORT["height"]
    if pin == "fixed":
        return Desktop(*fixed, f"fixed, pinned by {PIN_VARIABLE}")
    views = read_user_views(page_dir, None)["sessions"]
    if not views:
        # Authors who knew the user's window but read only "fixed" went looking for a
        # way to set it; the words say it follows the user once they open the page.
        return Desktop(
            *fixed,
            "fixed, since no browser has shown the page in a day; once the user"
            " opens it, the check reads their window",
        )
    window = views[0]["viewport"]
    return Desktop(round(window["width"]), round(window["height"]), "the user's window")


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


def _launch(read):
    """What `read` finds, with the browser's name, or why no browser ran it."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    with ExitStack() as stack:
        try:
            p = stack.enter_context(sync_playwright())
        except Exception as error:  # noqa: BLE001 - Playwright raises bare Exception on driver EOF
            return f"Playwright's driver did not start: {error}"
        try:
            browser, browser_name = launch_browser(p)
        except PlaywrightError as error:
            return (
                f"no browser launched: {str(error).strip().splitlines()[0]}. "
                f"{browser_hint()}"
            )
        with browser:
            return read(browser), browser_name


@dataclass(frozen=True, slots=True)
class BrowserCheck:
    """What the browser gates read of the candidate: `gates` names those asked for;
    `unavailable` says why no browser ran them, or is None where `browser` did. Page
    code that fails ends the check before the render reading, so `render` is None
    there as well as where it was not asked for, and `ran` names only the gates that
    read the page. `screens` is the directory and each
    saved screen with what it shows, for a page the render gate passed. `desktop` is
    the window the render check reads the desktop at, where it was asked for."""

    gates: list[str]
    browser: str | None = None
    unavailable: str | None = None
    page_code: list[Finding] | None = None
    render: RenderReading | None = None
    screens: tuple[Path, list[tuple[Path, str]]] | None = None
    desktop: Desktop | None = None

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
            reading["desktop"] = self.desktop.json()
        if self.screens is not None:
            into, saved = self.screens
            reading["screens"] = {
                "directory": str(into),
                "files": [{"file": shot.name, "shows": label} for shot, label in saved],
                "next": (
                    'before handover, follow page-checkpoints.md, "Pre-handover review"'
                ),
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
    (`page_code` says which run and which errors fail it), then the render invariants
    at the desktop window `desktop_viewport` chooses and a phone's, saving the screens
    the pre-handover review reads for a page they pass. Page code that fails ends the
    check before the render reading."""
    gates = [
        gate
        for gate, wanted in (("page code", page_code), ("render check", render))
        if wanted
    ]
    desktop = desktop_viewport(page_dir) if render else None

    def read(browser, url: str):
        errors = run_page_code(browser, url) if page_code else None
        if errors or not render:
            return errors, None, None
        reading = render_version(
            browser,
            url,
            desktop=desktop.viewport,
            implementations=artifact.implementations,
            declaration_sources=artifact.declaration_sources,
        )
        if reading.failures:
            return errors, reading, None
        screens = save_screens(browser, url, reading, page_dir, desktop.viewport)
        return errors, reading, screens

    with preview_server(
        page_dir, document, revision, transition_held=True, artifact=artifact
    ) as url:
        try:
            (errors, reading, screens), browser_name = run_in_browser(
                lambda browser: read(browser, url)
            )
        except NoBrowser as error:
            return BrowserCheck(gates, unavailable=str(error), desktop=desktop)
    return BrowserCheck(
        gates, browser_name, None, errors, reading, screens, desktop=desktop
    )


def message_check(page_dir: Path, kind: str, markup: str) -> None:
    """Run a message's markup once, as a page of its own (`page_code.message_page`),
    where it places a widget only a browser can judge, and refuse it on every error
    that run reports, as plain `page check` refuses a page. Takes the page's current
    layer, the one the thread will draw the message with. Where the host has no
    browser the message posts unrun, and reports any failure when its thread draws."""
    from leaf.files import latest_revision
    from leaf.findings import Rejected
    from leaf.registry.storage import read_page_registry
    from leaf.revision_artifact import ArtifactError, capture_artifact

    from .page_code import message_page, places_judged_widget

    layer = read_page_registry(page_dir)
    if layer is None:
        return
    document = message_page(markup)
    try:
        artifact = capture_artifact(
            page_dir,
            document,
            layer.registry,
            declaration_sources=layer.declaration_sources,
            widget_sources=layer.widget_sources,
        )
    except ArtifactError:
        # Markup that names what no page may load, such as the theme's stylesheet,
        # is the markup gate's to refuse, in its own words, under the page lease.
        return
    if not places_judged_widget(document, artifact):
        return
    revision = (latest_revision(page_dir) or 0) + 1
    ran = browser_check(
        page_dir, document, revision, artifact, page_code=True, render=False
    )
    if ran.status:
        raise Rejected(ran.findings(), f"{kind} markup doesn't draw")


@dataclass(frozen=True, slots=True)
class WidgetQuality:
    """What `package check --render` read of the package's `widgets`: its findings
    and the browser that drew the worked examples, or why no browser could. A finding
    is advice for the widgets' author, apart from invalid output contracts and examples
    that could not be drawn (`unreadable-examples`), which fail the check."""

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
