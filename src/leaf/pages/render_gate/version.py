"""Whole-version render attempts, the reading of the page each loads (`_render_page`),
and the retry policy."""

from dataclasses import dataclass, field, replace
from urllib.parse import urlsplit

from leaf.base.findings import Finding
from leaf.pages.render_gate.page_code import PageCode
from leaf.pages.render_gate.readings import (
    SWEEP_WIDTHS,
    DevtoolsIssues,
    _page_findings,
    _PageContext,
    arrangement_changes,
    drawn_height_advice,
    open_widgets,
    settle_at,
    shrunk_label_advice,
    squeezed_advice,
    sweep,
    swept_faults,
    thread_findings,
)
from leaf.pages.render_gate.scheme import (
    answer_reports,
    collect_page_exceptions,
    console_finding,
    rendered_revision,
    served,
    stand_in_other_leaves,
    unready_finding,
    window_finding,
)
from leaf.source.data_contracts import output_findings
from leaf.source.registry.contract import element_declarations
from leaf.source.render_checks import (
    RENDER_VIEWPORT,
    SERVED_TIMEOUT_MS,
    PageNotReady,
    asked_again,
    close_render_page,
    evaluate_probe,
    install_window_errors,
    observe_output_documents,
    open_render_page,
    output_values,
    rendered,
    start_near_work,
    wait_for_probe,
    wait_until_ready,
)


@dataclass(frozen=True, slots=True)
class RenderReading:
    """What the browser gate read of a version: its findings, of which an `error`
    refuses it and `advice` does not.
    `arrangement` is each swept width at which the page's own arrangement is at its
    tightest before it changes, with what changes. `complete` is False when the gate
    stopped before it had read the page through, as it does at a page that cannot
    start or under a browser that fails. One of the findings then says what stopped
    it. `visuals` is what each visual in the page draws at the desktop window, by the
    visual's id (`drawnVisuals` in `render-checks/widgets.js`), and empty where the
    gate stopped before it read them."""

    findings: list[Finding]
    arrangement: list[tuple[int, str, str]]
    complete: bool = True
    visuals: dict[str, dict] = field(default_factory=dict)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.refuses]

    @property
    def advice(self) -> list[Finding]:
        return [f for f in self.findings if not f.refuses]


def _projection_was_applied(failed_stage: str | None) -> bool:
    """Whether the readiness failure happened after authoritative presentation."""
    return failed_stage in (None, "arrived", "rendering", "pageSettled")


def _render_page(
    browser,
    url,
    viewport,
    served_timeout_ms,
    opened_pages,
    then=None,
    implementations=None,
    declaration_sources=None,
    page_code=None,
):
    """Read and report the browser gate on one page at `viewport` in the light scheme:
    the findings that refuse the version, the ResizeObserver loop notices its retry
    policy judges (`version.render_version`), and whether every reading completed.

    `then`, when given, is handed the settled page and its registry after every reading
    here, for additional version-level readings before the page closes. `page_code`,
    when given, is a list this page's page-code reading (`page_code.PageCode`) fills
    once the page is ready; where it fails the page, nothing more is read."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page = open_render_page(browser, viewport=viewport, color_scheme="light")
    stand_in_other_leaves(page)
    opened_pages.append(page)
    page._leaf_probe_timeout_ms = served_timeout_ms
    errors = []
    resize_notices = []

    def served_here(path):
        return served(page, url, path, timeout_ms=served_timeout_ms)

    def console_message(message):
        if (problem := console_finding(message)) is not None:
            errors.append(problem)

    def window_error(error):
        problem = window_finding(error)
        (resize_notices if problem.code == "resize-loop" else errors).append(problem)

    def ended(found, notices=(), complete=False):
        # An attempt that stops early says why with a finding that fails the check or
        # leaves the page unread, which `render_version` keeps in place of a notice it
        # can't confirm.
        assert complete or any(f.refuses or f.unread for f in found), found
        close_render_page(page)
        return list(found), list(notices), complete

    def explained(code, **values):
        # The named wait says what never arrived; the console diagnostics collected
        # above explain why, including when the document itself was refused.
        console = [problem.json(text=False) for problem in [*errors, *resize_notices]]
        return ended([Finding(code, values={**values, "console": console})])

    def probe_failure(error):
        return explained("probe-failed", error=str(error).strip())

    def never_ready(error, finding):
        # Where this page takes the page-code reading, a page that never got ready
        # fails it, and the version is read no further.
        if code is not None and page_code is not None:
            page_code.extend(code.findings(page, error))
            return ended([], complete=True)
        # A page that declared it cannot start never started, whichever wait read the
        # declaration: a widget module that fails to link declares it just after the
        # runtime's chrome stands, so either wait may be the one to see it.
        return explained("no-runtime" if error.stage == "refused" else finding)

    page.on("console", console_message)
    collect_page_exceptions(page, errors)
    # The runtime writes each report to the console too, which is where this reading
    # takes it, unless it is the page-code reading's too.
    code = PageCode(page) if page_code is not None else None
    if code is None:
        answer_reports(page)
    devtools = DevtoolsIssues(page)
    install_window_errors(page, window_error)
    try:
        observe_output_documents(page)
        page.goto(asked_again(url))
        wait_for_probe(page, "runtimeStarted", fixed_server=True)
    except PageNotReady as error:
        return never_ready(error, "no-runtime")
    except PlaywrightTimeout:
        return explained("no-runtime")
    except PlaywrightError as error:
        return probe_failure(error)
    # Every reading below is of a settled page. The widget layer writes half the
    # document, so a box measured while it is still drawing belongs to no version of
    # the page — which is the stamp `page export` waits on for the same reason.
    # Upgrade and readiness below are one handover, so each waits as a handover does
    # (`wait_until_ready`): the upgrade is most of a heavy page's handover, and a
    # probe's patience is not. A page that declares it cannot start, as one whose widget
    # module failed to load does, upgrades nothing more, and nothing replaces the
    # preview server that would reload it, so the declaration ends each wait as well.
    try:
        wait_until_ready(page, through="upgraded", fixed_server=True)
    except PageNotReady as error:
        return never_ready(error, "never-upgraded")
    except PlaywrightError as error:
        return probe_failure(error)
    # The served documents every reading below is asked against, read once each
    # (`served` says why they are read from out here rather than fetched inside
    # the page). The readings get data rather than fetching it, so most of them
    # are plain synchronous DOM walks with nothing in them to await or hang in.
    try:
        registry = served_here("/registry.json").json()
        # The readings in the page consume element declarations, so they are handed
        # only those:
        # $keys spells its members in a declaration's own keys, and a sweep over
        # every declaration took it for a widget called $keys.
        declarations = element_declarations(registry)
        visual_provider_problems = evaluate_probe(
            page, "invalidVisualProviders", declarations
        )
        if visual_provider_problems:
            # The inventory is the boundary every runtime visual reading trusts. Once
            # it is invalid, the settled-page probes have no valid page to inspect.
            # What the console already said stays: another widget's failure is a
            # fault of its own, and a presentation the inventory broke is one the
            # user would see.
            return ended(
                [*errors, *map(Finding.read, visual_provider_problems)],
                resize_notices,
                complete=True,
            )
        state = served_here("/api/state").json()
        markup = served_here(urlsplit(url).path).text()
        # Every replay check is bounded by immutable revision.
        # A stamped URL resolves through the stamp map; an exact source preview
        # uses the synthetic active revision exposed only by its preview server.
        here = rendered_revision(url, state)
    except PlaywrightTimeout as e:
        # The first line only: the rest is playwright's call log, which says
        # nothing about the page that a reader of this failure needs.
        stopped = Finding("server-stopped", values={"error": str(e).splitlines()[0]})
        return ended([*errors, stopped])
    # Every reading below is of a page at rest, and the upgrade stamp above is
    # one part of that. The first read runs beside upgrade, but its answer may still
    # be pending when the stamp lands; a gate reading there sees the authored board,
    # the unanswered question and the body the user has since rewritten — a page
    # nobody is shown. The page's readiness against the reading taken above is the
    # answer to that, and the frame the log lands in is the first frame of whatever
    # the replay set moving, a replay past the presentation boundary moving rather than
    # teleporting, which `pageSettled` then waits out. Every reading below has boxes
    # or words in it. The windows open
    # under load alone, which is how one page passed at a desk and reported words
    # drawn over words under a full suite. The readings take in every document the
    # page can show, so work it holds until the reader nears it starts first.
    unready = None
    try:
        wait_until_ready(page, state, fixed_server=True)
        start_near_work(page, state, fixed_server=True)
    except PageNotReady as error:
        unready = error
    if code is not None and page_code is not None:
        if unready is None:
            # As `run_page_code` reads it: a widget that paints from a rendering
            # callback throws there, so every callback it queued has run first.
            rendered(page)
        page_code.extend(code.findings(page, unready))
        if page_code:
            return ended([], complete=True)
    if unready is not None:
        failed_stage = unready.stage
        unsettled = [unready_finding(unready)]
    else:
        try:
            wait_for_probe(page, "pageSettled")
            failed_stage, unsettled = None, []
        except PlaywrightTimeout:
            failed_stage = "pageSettled"
            moving = evaluate_probe(page, "moving")
            unsettled = [Finding("never-settled", values={"moving": moving})]
    replayed = _projection_was_applied(failed_stage)
    context = _PageContext(
        page=page,
        errors=errors,
        registry=registry,
        declarations=declarations,
        state=state,
        markup=markup,
        here=here,
        replayed=replayed,
        unsettled=unsettled,
        devtools=devtools,
    )
    found = _page_findings(context)
    if then is not None:
        then(page, registry)
    # Last, because opening a thread changes what the page shows `then`.
    heard = len(errors)
    found += thread_findings(context, found)
    found += errors[heard:]
    found += output_findings(
        output_values(page), registry, implementations, declaration_sources
    )
    return ended(found, resize_notices, complete=True)


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
    visuals = []
    steps = sorted({*SWEEP_WIDTHS, desktop["width"]}, reverse=True)

    def desktop_sweep(page, registry):
        open_tags = open_widgets(registry)
        # Read the desktop viewport before the sweep changes it.
        visuals.append(
            evaluate_probe(page, "drawnVisuals", element_declarations(registry))
        )
        advice.extend(drawn_height_advice(page))
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
        visuals[0] if visuals else {},
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
