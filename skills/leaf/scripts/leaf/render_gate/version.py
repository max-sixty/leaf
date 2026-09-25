"""Whole-version render attempts and retry policy."""

from dataclasses import dataclass

from leaf.render_checks import RENDER_VIEWPORT, SERVED_TIMEOUT_MS

from .readings import (
    alignment_advice,
    margin_cover_advice,
    stacking_advice,
    sweep,
    swept_overflow,
)
from .scheme import _render_scheme

RENDER_VIEWPORTS = (
    RENDER_VIEWPORT,
    {"width": 540, "height": 720},
)


@dataclass(frozen=True, slots=True)
class RenderReading:
    """What the browser gate read of a version: a failure refuses it, advice does not."""

    failures: list[str]
    advice: list[str]


def _viewport_label(viewport: dict) -> str:
    return f"{viewport['width']}x{viewport['height']}"


def _findings_with_viewports(findings: list[tuple[str, str]]) -> list[str]:
    """Identify viewport-specific findings without duplicating universal ones."""
    viewports_by_finding = {}
    for finding, viewport in findings:
        viewports = viewports_by_finding.setdefault(finding, [])
        if viewport not in viewports:
            viewports.append(viewport)
    every_viewport = [_viewport_label(viewport) for viewport in RENDER_VIEWPORTS]
    return [
        (
            finding
            if viewports == every_viewport
            else f"{finding} (at {', '.join(viewports)})"
        )
        for finding, viewports in viewports_by_finding.items()
    ]


def _render_version_attempt(
    browser, url: str, served_timeout_ms: int | None = None
) -> tuple[list, list, bool, list]:
    """Everything wrong with a served version that only a browser can see: a
    console warning or error, a page error, a request that 404s, a fail-soft error box,
    an upgrade module that never defines its declared element, an x-conversation whose module
    placed no matching page host, a widget upgraded into a box of no usable size,
    an element showing words with no box for a mark to hang on, so a comment anchored
    there would outline nothing and the Ask walk would travel to the top of the page,
    the page scrolling sideways, content set past the column and out into the margin,
    a drawing scrolling beside an empty margin the page had room in,
    a table that scrolls sideways with a cell in it wrapped,
    words the user can read and can't select, words drawn on top of other words, code
    coloured in an ink the user cannot tell from the code around it — each
    in both color schemes at wide and compact viewports, because the dark theme and
    responsive layout are real CSS nobody otherwise renders — plus, in one scheme at
    each viewport, a word the registry promised that never reached
    the page (a declaration is scheme-blind), an attribute a module left standing on a
    widget that its entry never declared (a file's reading sees one writer, and this is
    the other), a version that authors widget state the log replays over, a widget whose
    renderState is relative, so a read's replay of the sender's own gesture moves the
    page again (none of the three is CSS), a settled holder whose mark or still-showing
    slot words disagree with the log's decision (read once, on the premise the
    trapped-margin reading shares: the palettes carry no geometry between them), an SVG
    paint token that does not resolve to valid paint in that scheme, a box drawing one inset
    and showing another, and, on paper, words the page drops that it says on screen, or
    draws over each other (print is scheme-blind). Once per version, on the settled
    desktop page in the light scheme, it reads two things more: whether the page's grids
    stand on shared vertical lines, which is advice, and then, resizing that loaded page
    through every width from 360px to 1200px, the sideways readings again: a version
    holds at each of them, not only at the two it renders. The same sweep says in what
    window each track template stacks, which is advice where that window is a desktop
    one. Returns the failures and
    the advice; no failures is a pass.

    One implementation with two callers — `version check --render` on the page an agent
    just wrote, and the render suite on the shipped examples
    (the tests/test_render_*.py modules) — so the gate and the suite hold one set of
    invariants. Returns ordinary failures, ResizeObserver notices, whether every
    reading completed, and advice. `browser` is a live Playwright browser; nothing here imports
    playwright at module level, so the module stays importable without it."""
    from playwright.sync_api import Error as PlaywrightError

    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    opened_pages = []
    failures = []
    notices = []
    completed = []
    swept = []
    advice = []

    def once(page):
        # Advice first, at the viewport it is about; the sweep then resizes the page.
        advice.extend(alignment_advice(page))
        advice.extend(margin_cover_advice(page))
        widths = sweep(page, RENDER_VIEWPORTS)
        swept.extend(swept_overflow(widths, RENDER_VIEWPORTS))
        advice.extend(stacking_advice(widths))

    try:
        for viewport in RENDER_VIEWPORTS:
            viewport_label = _viewport_label(viewport)
            for scheme in ("light", "dark"):
                first = viewport is RENDER_VIEWPORTS[0] and scheme == "light"
                found, found_notices, complete = _render_scheme(
                    browser,
                    url,
                    scheme,
                    viewport,
                    served_timeout_ms,
                    opened_pages,
                    then=once if first else None,
                )
                failures.extend((finding, viewport_label) for finding in found)
                notices.extend((notice, viewport_label) for notice in found_notices)
                completed.append(complete)
    except PlaywrightError:
        for page in opened_pages:
            if not page.is_closed():
                page.close()
        raise
    return (
        _findings_with_viewports(failures) + swept,
        _findings_with_viewports(notices),
        all(completed),
        advice,
    )


def render_version(
    browser, url: str, served_timeout_ms: int | None = None
) -> RenderReading:
    """Read a version, confirming a complete attempt that reports a ResizeObserver
    loop notice. Advice is the first attempt's: it refuses nothing, so a
    confirmation has nothing to say about it.

    Chrome can emit the notice once under load, while a layout feedback loop emits it
    on every rendering. The unit here is the whole color-scheme and viewport gate,
    including its print and replay probes: a notice is ignored only when a later
    complete attempt is clean. Ordinary failures from both attempts are retained, and
    an incomplete confirmation cannot pardon the notice that prompted it.
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
                [],
            )

    found, notices, complete, advice = attempt()
    retain(found)
    if not complete:
        retain(notices)
        return RenderReading(failures, advice)
    if not notices:
        return RenderReading(failures, advice)

    found, confirming_notices, complete, _advice = attempt()
    retain(found)
    if not complete:
        for notice in [*notices, *confirming_notices]:
            retain([f"{notice} (the confirming render attempt did not complete)"])
        return RenderReading(failures, advice)
    if confirming_notices:
        failures.extend(
            f"{notice} (recurred on the confirming render attempt)"
            for notice in confirming_notices
        )
    return RenderReading(failures, advice)
