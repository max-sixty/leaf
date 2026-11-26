"""Lifecycle and trusted inputs for the page the render gate reads."""

import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from leaf.agents.presence import live_servers
from leaf.base.files import version_num
from leaf.base.findings import Finding
from leaf.base.refusals import Refused
from leaf.base.server import page_origin
from leaf.serving.event_endpoint import event_rejection
from leaf.source.registry.kernel import kinds_declaring
from leaf.source.render_checks import (
    SERVED_TIMEOUT_MS,
    PageNotReady,
)

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
