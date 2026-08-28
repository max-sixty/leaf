"""Whole-version render attempts and retry policy."""

from leaf.render_checks import SERVED_TIMEOUT_MS

from .scheme import _render_scheme, recurring_resize_observer_error


def _render_version_attempt(
    browser, url: str, served_timeout_ms: int | None = None
) -> tuple[list, list, bool]:
    """Everything wrong with a served version that only a browser can see: a
    console or page error, a request that 404s, a fail-soft error box, an upgrade
    module that never defines its declared element, an x-conversation whose module
    placed no matching page host, a widget upgraded into a box of no usable size,
    an element showing words with no box for a mark to hang on, so a comment anchored
    there would outline nothing and the ask walk would travel to the top of the page,
    the page scrolling sideways, content set past the column and out into the margin,
    a drawing scrolling beside an empty margin the page had room in,
    a table that scrolls sideways with a cell in it wrapped,
    words the user can read and can't select, words drawn on top of other words, code
    coloured in an ink the reader cannot tell from the code around it — each
    in both color schemes, because the dark theme is real CSS nobody otherwise
    renders — plus, in one scheme, a word the registry promised that never reached
    the page (a declaration is scheme-blind), an attribute a module left standing on a
    widget that its entry never declared (a file's reading sees one writer, and this is
    the other), a version that authors widget state the log replays over, a widget whose
    applyAction is relative, so a read's replay of the sender's own gesture moves the
    page again (none of the three is CSS), a settled holder whose mark or still-showing
    slot words disagree with the log's decision (read once, on the premise the
    trapped-margin reading shares: the palettes carry no geometry between them), a box
    drawing one inset and showing another, and, on paper, words the page drops that
    it says on screen, or draws over each other (print is scheme-blind). Returns human-readable failures; [] is a pass.

    One implementation with two callers — `version check --render` on the page an agent
    just wrote, and the render suite on the shipped examples
    (the tests/test_render_*.py modules) — so the gate and the suite hold one set of
    invariants. Returns ordinary failures, ResizeObserver notices, and whether every
    reading completed. `browser` is a live Playwright browser; nothing here imports
    playwright at module level, so the module stays importable without it."""
    from playwright.sync_api import Error as PlaywrightError

    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    opened_pages = []

    try:
        light, light_notices, light_complete = _render_scheme(
            browser, url, "light", served_timeout_ms, opened_pages
        )
        dark, dark_notices, dark_complete = _render_scheme(
            browser, url, "dark", served_timeout_ms, opened_pages
        )
    except PlaywrightError:
        for page in opened_pages:
            if not page.is_closed():
                page.close()
        raise
    return (
        [*light, *dark],
        [*light_notices, *dark_notices],
        light_complete and dark_complete,
    )


def render_version(browser, url: str, served_timeout_ms: int | None = None) -> list:
    """Read a version, confirming a complete attempt that reports a ResizeObserver
    loop notice.

    Chrome can emit the notice once under load, while a layout feedback loop emits it
    on every rendering. The unit here is the whole light-and-dark gate, including its
    print and replay probes: a notice is ignored only when a later complete attempt is
    clean. Ordinary failures from both attempts are retained, and an incomplete
    confirmation cannot pardon the notice that prompted it.
    """
    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    from playwright.sync_api import Error as PlaywrightError

    failures = []

    def retain(found):
        failures.extend(failure for failure in found if failure not in failures)

    def attempt():
        try:
            return _render_version_attempt(
                browser, url, served_timeout_ms=served_timeout_ms
            )
        except PlaywrightError as error:
            return (
                [
                    "the browser gate failed while running its probe module: "
                    + str(error).strip().splitlines()[0]
                ],
                [],
                False,
            )

    found, notices, complete = attempt()
    retain(found)
    if not complete:
        retain(notices)
        return failures
    if not notices:
        return failures

    found, confirming_notices, complete = attempt()
    retain(found)
    if not complete:
        for notice in [*notices, *confirming_notices]:
            retain([f"{notice} (the confirming render attempt did not complete)"])
        return failures
    if confirming_notices:
        failures.append(recurring_resize_observer_error("render attempt"))
    return failures
