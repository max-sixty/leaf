"""Bring a fresh tab on each arm to a state: the loop `leaf-dev probe` and `leaf-dev
stills` both run.

For each arm, base first (`arms.choose_arms`), `visits` serves the page from the arm,
opens a fresh tab in the run's engine (`browser.launch`), loads the page, runs the
state's input (`states.State`) and the command's own steps, settles, and hands the tab
to the command's reading. Every arm's tab and server stay open until the command is
done with them, so stills can read both arms' tabs side by side. A stage that fails
ends that arm's visit with its error, and the next arm still runs, since a run is most
often made where one version is broken.

Each visit also records what probe reports: the startup reading, long frames through
startup and through the inputs, the layout shifts, and the console's errors and
warnings. Safari on the iOS simulator answers a reading as a Playwright page does
(`ios_safari.Tab`), but takes no input, so a state with an input is refused there
before its page is built; in place of a console, an arm there reports the errors the
runtime logged to the page. A state that holds the runtime (`State.activated`) is
refused in every engine but Chromium: on 2026-11-03 Playwright 1.64's Firefox (build
1555) and WebKit (build 2370) never resolved `document.fonts.ready` while the entry
module was held, and their screenshots wait for it, and WebDriver holds no request.
"""

from collections.abc import Callable, Generator, Iterator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click
from playwright.sync_api import Page
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from leaf.event_log import read_events
from leaf.findings import Finding
from leaf.render_gate.scheme import collect_page_exceptions, console_finding
from leaf_dev import ios_safari
from leaf_dev.arms import Arm, own_source, served_page, serving_source
from leaf_dev.browser import Window, load, settle, slow_cpu, tab
from leaf_dev.main_thread import SCRIPT as MAIN_THREAD_SCRIPT
from leaf_dev.main_thread import reading as main_thread_reading
from leaf_dev.startup import layout_shifts_reading, observe_startup, startup_reading
from leaf_dev.states import State


@dataclass
class Visit:
    """One arm's visit to a state: the arm's commit, the tab it reached (a Playwright
    page, or the simulator's Safari as one), what was read there, and the stage it
    reached, with the error that stopped it there if one did."""

    commit: str
    page: Any = None
    doing: str = "build"
    error: Exception | None = None
    reading: dict = field(default_factory=dict)


def said(error: Exception) -> str:
    """An error's own words: the last line a `leaf` command printed, a WebDriver error's
    message without the documentation link Selenium appends, or any other error's first
    line. Its traceback holds the rest."""
    if isinstance(error, click.ClickException):
        words = error.format_message().strip().rsplit("\n", 1)[-1].split("; ")[0]
    elif isinstance(error, WebDriverException):
        words = error.msg or ""
    else:
        words = str(error).split("\n", 1)[0]
    return words or type(error).__name__


@contextmanager
def visits(
    browser,
    arms: dict[str, Arm],
    state: State,
    source: Path | str,
    scratch: Path,
    *,
    window: Window,
    scheme: str,
    read: Callable[[str, Visit], None],
    motion: str = "reduce",
    scale: int = 1,
    log: Path | None = None,
    authored: bool = False,
    steps: Sequence[tuple[str, Callable[[Page], object]]] = (),
    run: Callable[[Page], object] | None = None,
    record: Callable[[Page, str], AbstractContextManager] | None = None,
    throttle: float | None = None,
) -> Generator[Iterator[tuple[str, Visit]]]:
    """Yield an iterator of each arm's visit to `state`, which visits the arm as the
    caller reaches it, so a caller reads every arm only by draining it. Every tab stays
    open until the block ends.

    `source` is an authored page, served from the arm (its own copy when `authored`,
    `own_source`, with `log`'s events admitted), or a URL, opened as it is. The tab
    opens in `window` and `scheme`, at `scale` device pixels to a CSS pixel and with
    `motion`, unless `browser` is the simulator's Safari. After the state's input,
    each of `steps` runs, then `run`, whose return is the reading's `result`, and once
    the page has settled, `read(arm, visit)`. `record(page, arm)` wraps the tab's
    visit, as a recording does; `throttle` slows Chromium's CPU from before the page
    loads."""
    ios = isinstance(browser, WebDriver)
    leaf = not isinstance(source, str)
    inputs = [*([(state.name, state.drive)] if state.drive else []), *steps]
    refusal = None
    if ios and (inputs or run):
        refusal = (
            "Safari on the iOS simulator takes no input: its taps never reach "
            "pointerup or click"
        )
    elif not state.activated and (ios or browser.browser_type.name != "chromium"):
        refusal = (
            "only Chromium shows a page whose runtime is held: Firefox and WebKit "
            "wait for the page to load, and WebDriver can't hold a request"
        )

    def visit_arm(held: ExitStack, arm: str, version: Arm) -> Visit:
        visit = Visit(version.commit)
        reading = visit.reading
        if refusal:
            visit.doing, visit.error = "open", click.ClickException(refusal)
            return visit
        served = None
        try:
            if isinstance(source, str):
                address = source
            else:
                page_source = own_source(version, source) if authored else source
                address = held.enter_context(
                    serving_source(version.directory, page_source, scratch / arm, log)
                )
            visit.doing = "open"
            if ios:
                served = served_page.get() if leaf else None
                visit.page = ios_safari.Tab(browser)
                visit.doing = "load"
                ios_safari.load(browser, address, leaf=leaf)
                read(arm, visit)
                return visit
            visit.page = page = held.enter_context(
                tab(browser, window, scheme, motion=motion, scale=scale)
            )
            with record(page, arm) if record else nullcontext():
                reading["console"] = console_findings(page)
                page.add_init_script(path=MAIN_THREAD_SCRIPT)
                observe_startup(page)
                if throttle:
                    slow_cpu(page, throttle)
                visit.doing = "load"
                if not leaf:
                    page.goto(address)
                elif state.activated:
                    load(page, address)
                    reading["startup"] = startup_reading(page)
                else:
                    held.callback(hold_runtime(page, address))
                reading["main_thread"] = {"startup": main_thread_reading(page)}
                try:
                    for label, act in inputs:
                        visit.doing = label
                        act(page)
                    if run:
                        visit.doing = "journey"
                        returned = run(page)
                    visit.doing = "settle"
                    if leaf and state.activated:
                        settle(page)
                    if run:
                        reading["result"] = returned
                finally:
                    if not page.is_closed():
                        if inputs or run:
                            reading["main_thread"]["interaction"] = main_thread_reading(
                                page
                            )
                        reading["layout_shifts"] = layout_shifts_reading(page)
                read(arm, visit)
        except Exception as error:
            visit.error = error
        finally:
            if ios and served:
                reading["errors"] = logged_errors(served.directory)
        return visit

    with ExitStack() as held:
        yield ((arm, visit_arm(held, arm, version)) for arm, version in arms.items())


def hold_runtime(page: Page, address: str) -> Callable[[], None]:
    """Open `address` with the runtime's entry module held in flight, once the authored
    layout has painted in its fonts, and return what releases the held requests."""
    held = []
    # Playwright marks its handler with an attribute, which a bound builtin can't take.
    page.route("**/leaf.js", lambda route: held.append(route))
    page.goto(address, wait_until="commit")
    # A visible node can precede the render-blocking stylesheet.
    page.wait_for_function("""() => performance.getEntriesByType('paint')
        .some(entry => entry.name === 'first-contentful-paint')""")
    page.evaluate("() => document.fonts.ready")

    def release() -> None:
        for route in held:
            route.abort()

    return release


def logged_errors(directory: Path) -> list[str]:
    """The errors the runtime logged to the page served from `directory`
    (`reportPageError`), which an arm reports where its browser's console is out of
    reach."""
    return [
        event["text"] for event in read_events(directory) if event["kind"] == "error"
    ]


def console_findings(page) -> list[Finding]:
    """The console errors and warnings and the uncaught exceptions of every document
    in the page, collected from here on. Warnings carry the browser's own diagnostics,
    such as Firefox's note that a `document.write` forced a reparse."""
    found = []

    def heard(message):
        if (finding := console_finding(message)) is not None:
            found.append(finding)

    page.on("console", heard)
    collect_page_exceptions(page, found)
    return found
