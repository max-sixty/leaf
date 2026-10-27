"""Whole-version render attempts and retry policy."""

from dataclasses import dataclass, replace

from leaf.findings import Finding
from leaf.registry.contract import element_declarations
from leaf.render_checks import RENDER_VIEWPORT, SERVED_TIMEOUT_MS

from .readings import (
    SWEEP_WIDTHS,
    arrangement_changes,
    margin_changes,
    open_widgets,
    settle_at,
    shrunk_label_advice,
    squeezed_table_advice,
    sweep,
    swept_faults,
    unreserved_height_advice,
)
from .scheme import _render_scheme

PHONE_VIEWPORT = {"width": 540, "height": 720}


@dataclass(frozen=True, slots=True)
class RenderReading:
    """What the browser gate read of a version: its findings, of which an `error`
    refuses it and `advice` does not. `margin_widths` are the widths, besides the fixed
    viewports, it rendered because the page's margin content changes there.
    `arrangement` is each swept width at which the page's own arrangement is at its
    tightest before it changes, with what changes."""

    findings: list[Finding]
    margin_widths: list[int]
    arrangement: list[tuple[int, str, str]]

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def advice(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "advice"]


def _viewport_label(viewport: dict) -> str:
    return f"{viewport['width']}x{viewport['height']}"


def _findings_with_viewports(
    findings: list[tuple[Finding, str]], desktop: dict
) -> list[Finding]:
    """Name the viewports of viewport-specific findings without duplicating universal
    ones."""
    viewports_by_finding = {}
    for finding, viewport in findings:
        viewports = viewports_by_finding.setdefault(finding, [])
        if viewport not in viewports:
            viewports.append(viewport)
    # A finding at both fixed viewports is universal: the margin widths render in one
    # scheme only, so a dark finding never reaches them.
    fixed = {_viewport_label(viewport) for viewport in (desktop, PHONE_VIEWPORT)}
    return [
        finding if fixed <= set(viewports) else finding.but(viewports=tuple(viewports))
        for finding, viewports in viewports_by_finding.items()
    ]


def _render_version_attempt(
    browser,
    url: str,
    desktop: dict,
    served_timeout_ms: int | None = None,
    *,
    implementations=None,
    declaration_sources=None,
) -> tuple[RenderReading, list, bool]:
    """Everything wrong with a served version that only a browser can see: a
    console warning or error (a widget failing soft is one, since the page reports it),
    a page error, an issue Chrome's DevTools raises, a request that 404s,
    an upgrade module that never defines its declared element, an x-thread-seat whose module
    placed no matching page host, a widget upgraded into a box of no usable size,
    an element showing words with no box for a mark to hang on, so a comment anchored
    there would outline nothing and the On me walk would travel to the top of the page,
    words the user can read and can't select — each in both color schemes at the
    `desktop` viewport and a phone's, because the dark theme and responsive layout are
    real CSS nobody otherwise renders — plus, in one scheme at
    each viewport, a word the registry promised that never reached
    the page (a declaration is scheme-blind), an attribute a module left on a
    widget that its entry never declared (a file's reading sees one writer, and this is
    the other), a version that authors widget state the log replays over, a widget whose
    render() is relative, so a read's replay of the sender's own gesture moves the
    page again (none of the three is CSS), a settled holder whose mark or
    still-showing slot words disagree with the log's decision (read once: the palettes carry no
    geometry between them), and an SVG paint token that does not resolve to valid paint
    in that scheme. Once per version, on the settled desktop page in the light scheme,
    it reads, as advice, whether a widget declaring x-height drew at a height its first
    paint did not hold; and then, resizing that loaded page through every width from
    360px to 1920px (`readings.sweep`), the geometry that moves with the window: the
    page scrolling sideways, content set past the column and out into the margin, a
    horizontal scrollbar with no room below what it scrolls, a control clipped out of
    reach, a box cutting off its own content where no scroll reaches it, words drawn on
    top of other words. There it also reads, as advice naming
    the widths it spans, whether a drawing's fit to its box shrinks its labels past
    reading, and whether a table scrolls sideways with a cell in it wrapped. That pass
    also finds each width where the page's margin content changes (a sidebar,
    contents map or note first standing in the margin), and the gate renders the page
    there too, in the light scheme: what stands in the margin is layout, which the
    scheme does not change. No failures is a pass.

    The geometry has one reading (`readings.swept_faults`), reported by the runs of
    widths each fault stands across, and every render adds its samples to it. Each
    render reads the geometry first at the size it loaded at, before it opens a
    thread: a widget can lay itself out by the window it first met, and a page's own
    rules can lay it out differently in the dark scheme. The light phone render then
    sweeps down from 540px at its own 720px height, which the desktop's need not
    share, since a widget can size by the window's height (a file editor clips its body
    at 60vh, a trace stage fills the window): a short window can cut off what a tall
    one shows, and a page's own rules can do the reverse.

    One implementation with two callers — `page check --render` on the page an agent
    just wrote, and the render suite on the shipped examples
    (the tests/*/test_render_*.py modules) — so the gate and the suite hold one set of
    invariants. Returns the reading, ResizeObserver notices, and whether every reading
    completed. `browser` is a live Playwright browser; nothing here imports
    playwright at module level, so the module stays importable without it."""
    from playwright.sync_api import Error as PlaywrightError

    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    opened_pages = []
    failures = []
    notices = []
    completed = []
    samples = []
    advice = []
    changes = []
    arrangement = []
    phone = PHONE_VIEWPORT
    fixed = {desktop["width"], phone["width"]}
    steps = sorted({*SWEEP_WIDTHS, *fixed}, reverse=True)

    def sample(page, registry):
        samples.extend(
            sweep(page, [page.viewport_size["width"]], open_widgets(registry))
        )

    def desktop_sweep(page, registry):
        # First, at the first paint's viewport, which the sweep then leaves.
        advice.extend(unreserved_height_advice(page, element_declarations(registry)))
        sample(page, registry)
        widths = sweep(page, steps, open_widgets(registry))
        samples.extend(widths)
        advice.extend(shrunk_label_advice(widths))
        advice.extend(squeezed_table_advice(widths))
        arrangement.extend(arrangement_changes(widths))
        changes.extend(
            width
            for width in margin_changes(page, widths, desktop["height"])
            if width not in fixed
        )
        # Back to the desktop viewport for the readings `_render_scheme` takes last.
        settle_at(page, desktop["width"], desktop["height"])

    def phone_sweep(page, registry):
        # From the phone's own width, so the first sample is the page as it loaded.
        narrow = [width for width in steps if width <= phone["width"]]
        samples.extend(sweep(page, narrow, open_widgets(registry)))
        settle_at(page, phone["width"], phone["height"])

    def render(viewport, scheme, then):
        viewport_label = _viewport_label(viewport)
        found, found_notices, complete = _render_scheme(
            browser,
            url,
            scheme,
            viewport,
            served_timeout_ms,
            opened_pages,
            then=then,
            implementations=implementations,
            declaration_sources=declaration_sources,
        )
        failures.extend((finding, viewport_label) for finding in found)
        notices.extend((notice, viewport_label) for notice in found_notices)
        completed.append(complete)

    try:
        render(desktop, "light", desktop_sweep)
        render(desktop, "dark", sample)
        render(phone, "light", phone_sweep)
        render(phone, "dark", sample)
        for width in changes:
            render({"width": width, "height": desktop["height"]}, "light", sample)
    except PlaywrightError:
        for page in opened_pages:
            if not page.is_closed():
                page.close()
        raise
    reading = RenderReading(
        [*_findings_with_viewports(failures, desktop), *swept_faults(samples), *advice],
        changes,
        arrangement,
    )
    return reading, _findings_with_viewports(notices, desktop), all(completed)


def render_version(
    browser,
    url: str,
    served_timeout_ms: int | None = None,
    desktop: dict = RENDER_VIEWPORT,
    *,
    implementations=None,
    declaration_sources=None,
) -> RenderReading:
    """Read a version at the `desktop` window and a phone's, confirming a complete
    attempt that reports a ResizeObserver loop notice. Advice is the first attempt's:
    it refuses nothing, so a confirmation has nothing to say about it.

    Chrome can emit the notice once under load, while a layout feedback loop emits it
    on every rendering. The unit here is the whole color-scheme and viewport gate,
    including its replay probes: a notice is ignored only when a later
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
                browser,
                url,
                desktop,
                served_timeout_ms=served_timeout_ms,
                implementations=implementations,
                declaration_sources=declaration_sources,
            )
        except PlaywrightError as error:
            failure = Finding("gate-failed", values={"error": str(error).strip()})
            return RenderReading([failure], [], []), [], False

    first, notices, complete = attempt()
    retain(first.failures)

    def reading():
        # Advice and the other readings are the first attempt's; failures accumulate.
        return replace(first, findings=[*failures, *first.advice])

    if not complete:
        retain(notices)
        return reading()
    if not notices:
        return reading()

    confirming, confirming_notices, complete = attempt()
    retain(confirming.failures)
    if not complete:
        retain(
            notice.but(values={"confirmation": "incomplete"})
            for notice in [*notices, *confirming_notices]
        )
        return reading()
    failures.extend(
        notice.but(values={"confirmation": "recurred"}) for notice in confirming_notices
    )
    return reading()
