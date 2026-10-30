"""Lifecycle and trusted inputs for one browser color scheme."""

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from leaf.data_contracts import output_findings
from leaf.event_endpoint import event_rejection
from leaf.files import version_num
from leaf.findings import Finding
from leaf.refusals import Refused
from leaf.registry.contract import element_declarations
from leaf.registry.kernel import kinds_declaring
from leaf.render_checks import (
    HANDOVER_DEADLINE_MS,
    SERVED_TIMEOUT_MS,
    PageNotReady,
    evaluate_probe,
    install_window_errors,
    observe_output_documents,
    output_values,
    wait_for_probe,
    wait_until_ready,
)

from .readings import DevtoolsIssues, _scheme_findings, _SchemeContext, thread_findings


def served(page, url: str, path: str, timeout_ms: int | None = None):
    """A document this page's own server holds, read from out here.

    The one reader in the render gate that can be given a deadline. `page.evaluate`
    sends the driver no timeout at all — measured on playwright 1.62, an evaluate
    awaiting a fetch that never answers is still running at 200s — so a reading
    taken inside the page is a hang with nothing printed and no way to bound it
    from Python. `page.request` takes one, and shares the browser context's cookie
    jar, so it reads as the same authorized client the page is: the handover key
    rides in the URL and becomes a cookie on the first navigation."""
    timeout_ms = SERVED_TIMEOUT_MS if timeout_ms is None else timeout_ms
    return page.request.get(urljoin(url, path), timeout=timeout_ms)


def answer_reports(page, heard) -> None:
    """Answer here the events the runtime sends on its own, an error report and a
    bookkeeping event, so a reading neither writes to the page's log nor draws the
    refusal a read-only server gives the post.

    An error the page reports to its agent hands its text to `heard`. A bookkeeping
    event, such as the `read` a page sends once it has shown an agent message whole,
    is refused as final, so the page doesn't send it again. It is refused under a 200,
    because Chrome reports a failed fetch as a console error, which the gate counts
    against the page. Every other event goes through, so a page that writes without
    a gesture still draws the server's refusal."""
    bookkeeping = kinds_declaring("bookkeeping")

    def report(route):
        event = route.request.post_data_json
        if event["kind"] == "error":
            heard(event["text"])
            route.fulfill(status=204)
        elif event["kind"] in bookkeeping:
            refused = Refused("a render check records no reading")
            route.fulfill(status=200, json=event_rejection(event, refused)[1])
        else:
            route.continue_()

    page.route("**/api/event", report)


def rendered_revision(url: str, state: dict) -> int:
    """Resolve the immutable revision shown at ``url`` from the public state."""
    name = Path(urlsplit(url).path).name
    if not name:
        return state["active"]["revision"]
    version = version_num(name)
    return next(
        stamped["revision"]
        for stamped in state["versions"]
        if stamped["version"] == version
    )


def _projection_was_applied(failed_stage: str | None) -> bool:
    """Whether the readiness failure happened after authoritative presentation."""
    return failed_stage in (None, "arrived", "rendering", "pageSettled")


# How Playwright's Firefox words the warning its engine reports, as distinct from a
# script's own console call.
_FORCED_LAYOUT = (
    '[JavaScript Warning: "Layout was forced before the page was fully loaded'
)
# Where a sample's document and everything it loads are served (`http.py`).
_SAMPLE_PATH = re.compile(r"/api/samples/[0-9a-f]{32}")


def _in_frame(location: str) -> bool:
    """Whether a console location belongs to a frame's document rather than the
    page's: a sample, or a frame given its document inline, as an HTML preview is."""
    return location == "about:srcdoc" or bool(
        _SAMPLE_PATH.search(urlsplit(location).path)
    )


def console_finding(message, *, warnings: bool = True) -> Finding | None:
    """Preserve console errors and optional warnings with their browser locations.
    An error refuses the page; a warning is advice, since a library's own notice (a
    development build, a deprecation) breaks nothing a user relies on, and a widget
    failing soft reports an error.

    Console wording is diagnostic text, even when it resembles the browser's own
    failed-resource report. It cannot establish an HTTP response or its status.
    Reading console events also avoids a response callback for every resource.

    One warning is Firefox's own, from a frame: its rendering update flushes layout
    in every document of the frame tree once the page has a resize observer, as
    every Leaf page does, so a sample frame still parsing its head starts layout
    early and says "Layout was forced before the page was fully loaded"; so does
    an HTML preview's frame. No page can prevent it, so that warning is dropped
    from a frame, which also hides a frame's own script reading layout too early.
    Firefox files the warning under the script that forced layout where one did,
    so a frame is known by where its documents come from (`_in_frame`), and the
    page's own warning is kept.
    """
    said = {"text": message.text, "url": message.location["url"]}
    if (
        message.type == "warning"
        and message.text.startswith(_FORCED_LAYOUT)
        and _in_frame(said["url"])
    ):
        return None
    if message.type == "warning" and warnings:
        return Finding("console-warning", values=said, severity="advice")
    if message.type != "error":
        return None
    return Finding("console-error", values=said)


def window_finding(error: dict) -> Finding:
    """An error a window raised with no exception behind it (`install_window_errors`)."""
    code = "resize-loop" if error["resizeLoop"] else "window-error"
    return Finding(code, values={"text": error["text"]})


def exception_finding(error) -> Finding:
    """A native page exception, retaining the browser's throw site as well as the
    exception's message.

    Native page errors cover every document in a tab. Their stacks identify the
    failing call even when separate frames throw the same message; engines that
    supply frames alone still need the message beside them.
    """
    message, stack = str(error), error.stack
    if stack:
        message = stack if message in stack else f"{message}\n{stack}"
    return Finding("page-exception", values={"text": message})


def collect_page_exceptions(page, errors: list[Finding]) -> None:
    """Collect native exceptions from every document, as findings."""
    page.on("pageerror", lambda error: errors.append(exception_finding(error)))


def collect_page_errors(page, errors: list[Finding]) -> None:
    """Collect the page's console errors and native exceptions, from every document,
    as findings."""

    def heard(message):
        if (error := console_finding(message, warnings=False)) is not None:
            errors.append(error)

    page.on("console", heard)
    collect_page_exceptions(page, errors)


def _render_scheme(
    browser,
    url,
    scheme,
    viewport,
    served_timeout_ms,
    opened_pages,
    then=None,
    implementations=None,
    declaration_sources=None,
):
    """Read and report the browser gate for one color scheme and viewport: the
    findings that refuse the version, the ResizeObserver loop notices its retry
    policy judges (`version.render_version`), and whether every reading completed.

    `then`, when given, is handed the settled page and its registry after every reading
    here, for additional version-level readings before the page closes."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page = browser.new_page(viewport=viewport, color_scheme=scheme)
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
        page.close()
        return (
            [finding.but(scheme=scheme) for finding in found],
            [notice.but(scheme=scheme) for notice in notices],
            complete,
        )

    def explained(code, **values):
        # The named wait says what never arrived; the console diagnostics collected
        # above explain why, including when the document itself was refused.
        console = [problem.json(text=False) for problem in [*errors, *resize_notices]]
        return ended([Finding(code, values={**values, "console": console})])

    def probe_failure(error):
        return explained("probe-failed", error=str(error).strip())

    page.on("console", console_message)
    collect_page_exceptions(page, errors)
    # The runtime writes each report to the console too, which is where this reading
    # takes it.
    answer_reports(page, lambda text: None)
    devtools = DevtoolsIssues(page)
    install_window_errors(page, window_error)
    try:
        observe_output_documents(page)
        page.goto(url)
        wait_for_probe(page, "runtimeStarted")
    except PlaywrightTimeout:
        return explained("no-runtime")
    except PlaywrightError as error:
        return probe_failure(error)
    # Every reading below is of a settled page. The widget layer writes half the
    # document, so a box measured while it is still drawing belongs to no version of
    # the page — which is the stamp `page export` waits on for the same reason.
    # Upgrade and readiness below are one handover, so they share its deadline: the
    # upgrade is most of a heavy page's handover, and a probe's patience is not.
    handover_ends = time.monotonic() + HANDOVER_DEADLINE_MS / 1000

    def handover_left() -> int:
        # At least 1ms: Playwright reads a zero timeout as none.
        return max(1, round((handover_ends - time.monotonic()) * 1000))

    try:
        wait_for_probe(page, "upgraded", timeout_ms=handover_left())
    except PlaywrightTimeout:
        return explained("never-upgraded")
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
        # $keys spells its members in the x- keys' own names, and a sweep over
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
        return ended([*errors, *resize_notices, stopped])
    # Every reading below is of a page at rest, and the upgrade stamp above is
    # one part of that. The first read runs beside upgrade, but its answer may still
    # be pending when the stamp lands; a gate reading there sees the authored board,
    # the unanswered question and the body the user has since rewritten — a page
    # nobody is shown. The page's readiness against the reading taken above is the
    # answer to that, and the frame the log lands in is the first frame of whatever
    # the replay set moving, a replay past the presentation boundary moving rather than
    # teleporting, which `pageSettled` then waits out. Both waits are taken in both
    # schemes, because every reading below has boxes or words in it. The windows open
    # under load alone, which is how one page passed at a desk and reported words
    # drawn over words under a full suite.
    try:
        wait_until_ready(page, state, timeout_ms=handover_left())
    except PageNotReady as error:
        failed_stage = error.stage
        unsettled = [
            Finding("not-ready", values={"stage": error.stage, "error": str(error)})
        ]
    else:
        try:
            wait_for_probe(page, "pageSettled")
            failed_stage, unsettled = None, []
        except PlaywrightTimeout:
            failed_stage = "pageSettled"
            moving = evaluate_probe(page, "moving")
            unsettled = [Finding("never-settled", values={"moving": moving})]
    errors.extend(
        Finding.read(finding) for finding in evaluate_probe(page, "startupLayoutShifts")
    )
    replayed = _projection_was_applied(failed_stage)
    context = _SchemeContext(
        page=page,
        light=scheme == "light",
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
    found = _scheme_findings(context)
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
