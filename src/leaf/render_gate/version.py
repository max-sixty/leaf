"""Whole-version render attempts and retry policy."""

from dataclasses import dataclass, field, replace

from leaf.findings import Finding
from leaf.registry.contract import element_declarations
from leaf.render_checks import (
    RENDER_VIEWPORT,
    SERVED_TIMEOUT_MS,
    close_render_page,
    evaluate_probe,
)

from .readings import (
    SWEEP_WIDTHS,
    arrangement_changes,
    open_widgets,
    settle_at,
    shrunk_label_advice,
    squeezed_advice,
    sweep,
    swept_faults,
)
from .scheme import _render_page


@dataclass(frozen=True, slots=True)
class RenderReading:
    """What the browser gate read of a version: its findings, of which an `error`
    refuses it and `advice` does not.
    `arrangement` is each swept width at which the page's own arrangement is at its
    tightest before it changes, with what changes. `complete` is False when the gate
    stopped before it had read the page through, as it does at a page that cannot
    start or under a browser that fails. One of the findings then says what stopped
    it. `parts` is the parts each visual in the page offers a thread at the desktop
    window, by the visual's id (`drawnParts` in `render-checks/widgets.js`), and empty
    where the gate stopped before it read them."""

    findings: list[Finding]
    arrangement: list[tuple[int, str, str]]
    complete: bool = True
    parts: dict[str, list[dict]] = field(default_factory=dict)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.refuses]

    @property
    def advice(self) -> list[Finding]:
        return [f for f in self.findings if not f.refuses]


def _render_version_attempt(
    browser,
    url: str,
    desktop: dict,
    served_timeout_ms: int | None = None,
    *,
    implementations=None,
    declaration_sources=None,
    page_code=None,
) -> tuple[RenderReading, list]:
    """Everything wrong with a served version that only a browser can see, read on one
    page loaded at the `desktop` viewport in the light scheme: a
    console error (a widget failing soft is one, since the page reports it),
    a page error, a request that 404s,
    an upgrade module that never defines its declared element,
    a widget upgraded into a box of no usable size,
    an element showing words with no box for a mark to hang on, so a comment anchored
    there would outline nothing and the On Me walk would travel to the top of the page,
    words the user can read and can't select, a word the registry promised that never
    reached the page, a version that authors widget state the log replays over, a
    widget whose render() is relative, so a read's replay of the sender's own gesture
    moves the page again, a settled holder whose mark or still-showing slot words
    disagree with the log's decision, and an SVG paint token that does not resolve to
    valid paint; and as advice, an attribute a module left on a widget that its entry
    never declared (a file's reading sees one writer, and this is the other), and a
    drawing whose height differs from the box it showed before drawing. Then, resizing
    that loaded page through every width from 360px to 1920px (`readings.sweep`), it
    reads the geometry that moves with the window: a control clipped out of reach, a
    box cutting off its own content where no scroll reaches it, words drawn on top of
    other words, words left under Leaf's panel with every scroller at its end. There it
    also reads, as advice naming the widths it spans, the page scrolling sideways,
    content set past the column and out into the margin, a horizontal scrollbar with no
    room below what it scrolls, whether a drawing's fit to its box shrinks its labels
    past reading, and whether a table scrolls sideways with a cell in it wrapped. That
    pass reports each native flex/grid arrangement change. Console warnings and the issues Chrome's DevTools raises
    are advice wherever they are read. No failures is a pass.

    The geometry has one reading (`readings.swept_faults`), reported by the runs of
    widths each fault stands across. It reads the geometry first at the size the page
    loaded at, before the sweep or a thread opens, since a widget can lay itself out
    by the window it first met. The sweep keeps the desktop's height, so a widget that
    sizes by the window's height is read at that one height.

    One implementation with two callers — `page check --render` on the page an agent
    just wrote, and the render suite on the shipped examples
    (the tests/*/test_render_*.py modules) — so the gate and the suite hold one set of
    invariants. Returns the reading, which says whether every reading completed, and
    its ResizeObserver notices. `browser` is a live Playwright browser; nothing here
    imports playwright at module level, so the module stays importable without it."""
    from playwright.sync_api import Error as PlaywrightError

    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    opened_pages = []
    samples = []
    advice = []
    arrangement = []
    parts = []
    steps = sorted({*SWEEP_WIDTHS, desktop["width"]}, reverse=True)

    def desktop_sweep(page, registry):
        open_tags = open_widgets(registry)
        # Read the desktop viewport before the sweep changes it.
        parts.append(evaluate_probe(page, "drawnParts", element_declarations(registry)))
        samples.extend(sweep(page, [desktop["width"]], open_tags))
        widths = sweep(page, steps, open_tags)
        samples.extend(widths)
        advice.extend(shrunk_label_advice(widths))
        advice.extend(squeezed_advice(widths))
        arrangement.extend(arrangement_changes(widths))
        # Back to the desktop viewport for the readings `_render_page` takes last.
        settle_at(page, desktop["width"], desktop["height"])

    try:
        # The page is also the page-code reading's, where one is asked for, and a page
        # whose code fails is read no further.
        found, notices, complete = _render_page(
            browser,
            url,
            desktop,
            served_timeout_ms,
            opened_pages,
            then=desktop_sweep,
            implementations=implementations,
            declaration_sources=declaration_sources,
            page_code=page_code,
        )
    except PlaywrightError:
        for page in opened_pages:
            if not page.is_closed():
                close_render_page(page)
        raise
    if page_code:
        return RenderReading([], []), []
    reading = RenderReading(
        [*dict.fromkeys(found), *swept_faults(samples), *advice],
        arrangement,
        complete,
        parts[0] if parts else {},
    )
    return reading, list(dict.fromkeys(notices))


def render_version(
    browser,
    url: str,
    served_timeout_ms: int | None = None,
    desktop: dict = RENDER_VIEWPORT,
    *,
    implementations=None,
    declaration_sources=None,
    page_code: list | None = None,
) -> RenderReading:
    """Read a version at the `desktop` window, confirming a complete attempt that
    reports a ResizeObserver loop notice. Advice is the first attempt's:
    it refuses nothing, so a confirmation has nothing to say about it.

    `page_code`, where given, is a list the first attempt's page fills with its
    page-code reading (`page_code.PageCode`); where that fails the page, the reading
    stops there and holds nothing.

    Chrome can emit the notice once under load, while a layout feedback loop emits it
    on every rendering. The unit here is the whole gate, including its replay probes: a
    notice fails the check only when a later complete attempt repeats it, and is
    ignored when that attempt is clean. Ordinary failures from both attempts are
    retained. A notice no complete attempt confirms or pardons is dropped: the attempt
    that didn't complete holds what stopped it, either a finding the browser couldn't
    read the page by, which leaves the reading unread, or the page's own failure, which
    stands.
    """
    served_timeout_ms = (
        SERVED_TIMEOUT_MS if served_timeout_ms is None else served_timeout_ms
    )
    from playwright.sync_api import Error as PlaywrightError

    failures = []

    def retain(found):
        failures.extend(failure for failure in found if failure not in failures)

    def attempt(page_code=None):
        try:
            return _render_version_attempt(
                browser,
                url,
                desktop,
                served_timeout_ms=served_timeout_ms,
                implementations=implementations,
                declaration_sources=declaration_sources,
                page_code=page_code,
            )
        except PlaywrightError as error:
            failure = Finding("gate-failed", values={"error": str(error).strip()})
            return RenderReading([failure], [], complete=False), []

    first, notices = attempt(page_code)
    if page_code:
        return first
    retain(first.failures)

    def reading():
        # Advice and the other readings are the first attempt's; failures accumulate.
        return replace(first, findings=[*failures, *first.advice])

    if not (first.complete and notices):
        return reading()

    confirming, confirming_notices = attempt()
    # What stopped the confirming attempt, as a crashed browser, stands in its place.
    retain(f for f in confirming.findings if f.refuses or f.unread)
    if not confirming.complete:
        return reading()
    failures.extend(
        notice.but(values={"confirmation": "recurred"}) for notice in confirming_notices
    )
    return reading()
