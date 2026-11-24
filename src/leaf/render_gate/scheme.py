"""Lifecycle and trusted inputs for the page the render gate reads."""

import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from leaf.data_contracts import output_findings
from leaf.event_endpoint import event_rejection
from leaf.files import version_num
from leaf.findings import Finding
from leaf.presence import live_servers
from leaf.refusals import Refused
from leaf.registry.contract import element_declarations
from leaf.registry.kernel import kinds_declaring
from leaf.render_checks import (
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
from leaf.server import page_origin

from .readings import DevtoolsIssues, _page_findings, _PageContext, thread_findings

# What a frame of another live Leaf page shows during a check (`stand_in_other_leaves`).
OTHER_LEAF = "<!doctype html><p>Another Leaf page, checked on its own.</p>"


def stand_in_other_leaves(target) -> None:
    """Answer a frame of each other live Leaf page on this machine with a stand-in
    in `target`, a page or a browser context.

    A page may frame another live Leaf page (validation.md, "Delivery policy"),
    whose faults are its own check's. The gate's browser holds no key for that page,
    and its server refuses the gate's origin as a framer, so the frame would report
    a refusal the framing page's author can't fix by editing it. Only a child
    frame's navigation stands in: a script, stylesheet, image or fetch the page
    loads from that server is one of the page's own dependencies and reaches the
    server as it would. A frame of any other address, a mistyped port included,
    loads and fails as it would."""
    origins = sorted(
        {
            page_origin(service["host"], service["port"])
            for *_, service in live_servers()
        }
    )

    def frame_or_fallback(route) -> None:
        request = route.request
        if request.is_navigation_request() and request.frame.parent_frame is not None:
            route.fulfill(content_type="text/html", body=OTHER_LEAF)
        else:
            route.fallback()

    if origins:
        target.route(
            re.compile(f"^(?:{'|'.join(map(re.escape, origins))})/"),
            frame_or_fallback,
        )


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


def answer_reports(page) -> None:
    """Answer here the events the runtime sends on its own, an error report and a
    bookkeeping event, so a reading neither writes to the page's log nor draws the
    refusal a read-only server gives the post. The reading takes a report's words from
    the console instead (`page_code.PageCode`).

    An error report is answered with no content. A bookkeeping event, such as the
    `read` a page sends once it has shown an agent message whole, is refused as final,
    so the page doesn't send it again. It is refused under a 200, because Chrome
    reports a failed fetch as a console error, which the gate counts against the page.
    Every other event goes through, so a page that writes without a gesture still
    draws the server's refusal. Firefox hands the route no post's body over WebDriver
    BiDi, so there every post is refused here, under a 200 as well, since a refusal
    from the server would read as a failed request beside the page's real reports.
    Firefox puts no failed fetch in its console, so a page there that writes without
    a gesture goes unreported either way."""
    bookkeeping = kinds_declaring("bookkeeping")

    refused = Refused("a render check records no reading")

    def report(route):
        event = route.request.post_data_json
        if event is None or event["kind"] in bookkeeping:
            route.fulfill(status=200, json=event_rejection(event or {}, refused)[1])
        elif event["kind"] == "error":
            route.fulfill(status=204)
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
        return Finding("console-warning", values=said)
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


def unready_finding(error: PageNotReady) -> Finding:
    """A page that never got ready, as a finding: the stage it never reached, and the
    words `render_checks.wait_until_ready` raised with, which are the page's own
    reason where the page declared it cannot start."""
    return Finding("not-ready", values={"stage": error.stage, "error": str(error)})


def collect_page_exceptions(page, errors: list[Finding]) -> None:
    """Collect native exceptions from every document, as findings."""
    page.on("pageerror", lambda error: errors.append(exception_finding(error)))


def collect_page_errors(page, errors: list[Finding], *, warnings: bool = False) -> None:
    """Collect the page's console errors, and its warnings with `warnings`, and its
    native exceptions, from every document, as findings (`console_finding`)."""

    def heard(message):
        if (error := console_finding(message, warnings=warnings)) is not None:
            errors.append(error)

    page.on("console", heard)
    collect_page_exceptions(page, errors)


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

    from .page_code import PageCode

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
        return explained(finding)

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
