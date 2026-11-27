"""Command boundary for browser-backed page validation.

The checks return findings (`findings.py`); this module and `validation/command.py`
are where they become the JSON document `page check` and `package check` print."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path

from leaf.base.findings import Finding
from leaf.pages.page_snapshot import PageSnapshot
from leaf.pages.render_gate.browser import browser_hint, launch_browser
from leaf.pages.render_gate.page_code import run_page_code
from leaf.pages.render_gate.preview import preview_server
from leaf.pages.render_gate.scheme import unready_finding
from leaf.pages.render_gate.screens import save_screens
from leaf.pages.render_gate.version import RenderReading, render_version
from leaf.serving.user_views import read_user_views
from leaf.source.render_checks import RENDER_VIEWPORT, PageNotReady

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
    fixed = RENDER_VIEWPORT["width"], RENDER_VIEWPORT["height"]
    if _pinned():
        return Desktop(*fixed, f"fixed, pinned by {PIN_VARIABLE}")
    view = _reader_view(page_dir)
    if view is None:
        # An author who knows the user's window but reads only "fixed" can go looking
        # for a way to set it, so the words say it follows the user once they open the
        # page.
        return Desktop(
            *fixed,
            "fixed, since no browser has shown the page in a day; once the user"
            " opens it, the check reads their window",
        )
    window = view["viewport"]
    return Desktop(round(window["width"]), round(window["height"]), "the user's window")


def user_engine(page_dir: Path) -> str:
    """`firefox` where the browser that last reported viewing the page is Firefox,
    so the check draws the page with the engine its reader does
    (`browser.launch_browser`), and `chromium` otherwise: for a reader in Chrome or
    Safari, for a page no browser has shown in the last day, and for a caller that
    pins the check (`PIN_VARIABLE`). A Firefox names itself `Firefox/` after a
    `Gecko/` token in its user agent; Firefox on iOS, a WebKit, names itself `FxiOS`."""
    if _pinned():
        return "chromium"
    view = _reader_view(page_dir)
    if view is None:
        return "chromium"
    agent = view["identity"]["browser"]["user_agent"]
    return "firefox" if "Gecko/" in agent and "Firefox/" in agent else "chromium"


def _reader_view(page_dir: Path) -> dict | None:
    """The view of the browser that last reported showing the page to its reader, or
    None where none has in the last day. A browser a script drives says so
    (`navigator.webdriver`) and is passed over: an agent that opened the live page in
    a headless Chromium while its reader's Firefox tab stood hidden, and so silent,
    would otherwise have the check draw in Chromium at the agent's window."""
    views = read_user_views(page_dir, None)["sessions"]
    return next((v for v in views if not v["identity"]["browser"]["webdriver"]), None)


def _pinned() -> bool:
    """Whether the caller pins what the check reads to the fixed window in Chromium."""
    pin = os.environ.get(PIN_VARIABLE)
    if pin not in (None, "", "fixed"):
        raise ValueError(f"{PIN_VARIABLE} takes only 'fixed', not {pin!r}")
    return pin == "fixed"


class NoBrowser(Exception):
    """No browser ran: the message says why."""


def run_in_browser(read, engine: str = "chromium"):
    """Launch the host's browser, for `engine` where the host has it
    (`browser.launch_browser`), and return what `read` finds with it, with the
    browser's name, or raise `NoBrowser`. Leaf runs without a browser, and a page
    reports its errors to its author whenever one draws it, so a host without one loses
    the early reading and not the command.

    Playwright runs on a thread of its own. Its sync API refuses a thread that already
    drives another instance or runs an event loop, and a command runs this from
    whatever process called it, such as a test harness driving its own browser."""
    with ThreadPoolExecutor(1) as pool:
        found = pool.submit(_launch, read, engine).result()
    if isinstance(found, str):
        raise NoBrowser(found)
    return found


def _launch(read, engine):
    """What `read` finds, with the browser's name, or why no browser ran it."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    with ExitStack() as stack:
        try:
            p = stack.enter_context(sync_playwright())
        except Exception as error:
            # Playwright raises bare Exception on driver EOF.
            return f"Playwright's driver did not start: {error}"
        try:
            browser, browser_name = launch_browser(p, engine)
        except PlaywrightError as error:
            return (
                f"no browser launched: {str(error).strip().splitlines()[0]}. "
                f"{browser_hint()}"
            )
        with browser:
            return read(browser), browser_name


@dataclass(frozen=True, slots=True)
class BrowserCheck:
    """What the browser gates read of the candidate: `gates` names those asked for,
    and `browser` the browser that ran them. Where none could, each gate's reading is
    the one finding that says why (`no-browser`), so a host with no browser reads as
    one whose browser crashed (`findings.Finding.unread`). Page code that fails ends
    the check before the render reading, so `render` is None there as well as where
    it was not asked for, and `ran` names only the gates that read the page.
    `screens` is the directory and each saved screen with what it shows, including
    when the render gate found failures, and None where the page was not ready for
    them (`browser_check`). `desktop` is the window the render check reads the desktop
    at, where it was asked for."""

    gates: list[str]
    browser: str | None = None
    page_code: list[Finding] | None = None
    render: RenderReading | None = None
    screens: tuple[Path, list[tuple[Path, str]]] | None = None
    desktop: Desktop | None = None

    @property
    def status(self) -> int:
        return 1 if any(f.refuses for f in self.findings()) else 0

    def findings(self) -> list[Finding]:
        # A browser none could launch is each gate's reading, and said once.
        return list(
            dict.fromkeys(
                [
                    *(self.page_code or []),
                    *(self.render.findings if self.render else []),
                ]
            )
        )

    @property
    def ran(self) -> list[str]:
        """The gates that read the page: each that ran, less one whose browser could
        not read it (`findings.Finding.unread`), which is as unread as a gate no
        browser ran."""
        return [
            gate
            for gate, found in (
                ("page code", self.page_code),
                ("render check", self.render.findings if self.render else None),
            )
            if found is not None and not any(f.unread for f in found)
        ]

    def json(self) -> dict:
        reading = {"asked": self.gates, "ran": self.ran, "browser": self.browser}
        if self.render is not None:
            assert self.desktop is not None
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
    snapshot: PageSnapshot,
    *,
    page_code: bool,
    render: bool,
    screens: bool = True,
) -> BrowserCheck:
    """Serve the candidate source once and, in one browser, the one `user_engine`
    chooses, run the page's own code (`page_code` says which run and which errors fail
    it), then the render invariants at the desktop window `desktop_viewport` chooses,
    saving the screens
    the author reads where `screens` asks, including when there are findings. Page code
    that fails ends the check before the render reading.

    A screen is taken of a ready page. A render reading that stopped early
    (`RenderReading.complete`), or that reported the page never got ready
    (`not-ready`), ends the check before the screens, since the page would be no
    readier for them and the check would only wait for it again. A page that is not
    ready when opened for a screen, as one whose module fails only on a phone, fails
    the check: the reading gains a `not-ready` finding that says which screens, and
    no screens are saved."""
    artifact = snapshot.artifact(snapshot.active_revision())
    gates = [
        gate
        for gate, wanted in (("page code", page_code), ("render check", render))
        if wanted
    ]
    desktop = desktop_viewport(page_dir) if render else None

    def read(browser, url: str):
        if not render:
            return run_page_code(browser, url) if page_code else None, None, None
        assert desktop is not None
        # The render's page takes the page-code reading, so the page loads once for
        # both.
        errors = [] if page_code else None
        reading = render_version(
            browser,
            url,
            desktop=desktop.viewport,
            implementations=artifact.implementations,
            declaration_sources=artifact.declaration_sources,
            page_code=errors,
        )
        if errors:
            return errors, None, None
        saved = None
        ready = reading.complete and not any(
            found.code == "not-ready" for found in reading.findings
        )
        if screens and ready:
            try:
                saved = save_screens(browser, url, reading, page_dir, desktop.viewport)
            except PageNotReady as error:
                reading = replace(
                    reading, findings=[*reading.findings, unready_finding(error)]
                )
        return errors, reading, saved

    with preview_server(page_dir, snapshot) as url:
        try:
            (errors, reading, saved), browser_name = run_in_browser(
                lambda browser: read(browser, url), user_engine(page_dir)
            )
        except NoBrowser as error:
            missed = [Finding("no-browser", values={"error": str(error)})]
            return BrowserCheck(
                gates,
                page_code=missed if page_code else None,
                render=RenderReading(missed, [], complete=False) if render else None,
                desktop=desktop,
            )
    return BrowserCheck(gates, browser_name, errors, reading, saved, desktop=desktop)


@dataclass(frozen=True, slots=True)
class WidgetQuality:
    """What `package check --render` read of the package's `widgets`: its findings
    and the browser that drew the worked examples. A finding is advice for the
    widgets' author, apart from invalid output contracts and examples the page could
    not draw (`unreadable-examples`), which fail the check, and a browser that couldn't
    read them (`findings.Finding.unread`), which leaves the gate unrun."""

    widgets: int
    browser: str | None = None
    findings: tuple[Finding, ...] = ()

    @property
    def status(self) -> int:
        return 1 if any(f.refuses for f in self.findings) else 0

    def json(self) -> dict:
        """The browser reading, in the shape `BrowserCheck.json` gives it."""
        unread = any(f.unread for f in self.findings)
        ran = [] if unread else ["widget quality"]
        return {"asked": ["widget quality"], "ran": ran, "browser": self.browser}


def widget_quality(package: Path) -> WidgetQuality:
    """Read the widget quality checks (`widget_quality`) of the package's own
    widgets in the host's browser."""
    from playwright.sync_api import Error as PlaywrightError

    from leaf.pages.render_gate.widget_quality import (
        UnreadablePage,
        own_tags,
        widget_findings,
    )

    def read(browser):
        try:
            return widget_findings(browser, package)
        except UnreadablePage as error:
            return [Finding("unreadable-examples", values={"error": str(error)})]
        except PlaywrightError as error:
            return [Finding("browser-error", values={"error": str(error).strip()})]

    widgets = len(own_tags(package))
    try:
        findings, browser_name = run_in_browser(read)
    except NoBrowser as error:
        return WidgetQuality(
            widgets, findings=(Finding("no-browser", values={"error": str(error)}),)
        )
    return WidgetQuality(widgets, browser_name, findings=tuple(findings))
