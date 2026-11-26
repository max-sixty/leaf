"""The run plain `page check` gives what only a browser can judge.

Wherever a page carries what only a browser can judge (`browser_judged`, which says
what that is and why), the check runs the exact candidate once: through upgrade,
authoritative presentation, and one rendering frame after it, in the light scheme, at
the render viewport, or with `--render` on the render check's page, at its desktop
window (`PageCode`).

A thread message takes the same run before it posts, where
`browser_judged.places_judged_widget` selects its markup (`messages.py`).

What fails it is what the runtime would report to the agent. `runtime/transport/layer-client.js`
posts every uncaught error and unhandled rejection, every widget that fails soft, and
every fault the runtime reports about the page itself, as an `error` event; that is
the event `leaf wait` delivers. It first writes the same words to the console after
`leaf: `, and the run reads them there rather than the browser's own error channels,
so the check and the watcher fail on the same reports, spelled the same way and naming
the same source location; past the twenty a load the runtime posts, the check reads
on. The console line, not the post, because Firefox, which the check draws in for a
reader who uses it (`browser.launch_browser`), hands the run no post's body. The
preview server is read-only, so the posts are answered here and reach no log
(`scheme.answer_reports`).

A failed browser run also reports failed network requests. Those readings explain a
failure; they do not decide one: optional assets and other requests that fail without a
page-code failure remain nonfatal. A pass is narrower than `--render`: nothing here
reads layout, color schemes, print, or replay, and code that throws only after a
gesture or a timer is not reached.
"""

from urllib.parse import parse_qsl, quote_plus, urlsplit, urlunsplit

from leaf.base.findings import Finding
from leaf.pages.render_gate.scheme import answer_reports, served, unready_finding
from leaf.source.render_checks import (
    ADDRESS_MARKS,
    RENDER_VIEWPORT,
    PageNotReady,
    asked_again,
    open_render_page,
    rendered,
    start_near_work,
    wait_for_probe,
    wait_until_ready,
)

# How `runtime/transport/layer-client.js` `reportPageError` opens the console line it writes for
# each report, ahead of the words it posts.
REPORTED = "leaf: "


class PageCode:
    """The page-code reading of one browser page, from before its navigation: every
    error the runtime reports, and the requests that failed while it ran. A page opened
    for it alone (`run_page_code`) or the render check's page (`version._render_page`)
    takes it, so `page check --render` loads the page once for both."""

    def __init__(self, page):
        self.reports = []
        heard = set()

        def console(message):
            # Every report, as `reportPageError` writes it before posting it; the
            # runtime posts each words once a load, so they are read once here too.
            if message.type == "error" and message.text.startswith(REPORTED):
                text = message.text.removeprefix(REPORTED)
                if text not in heard:
                    heard.add(text)
                    self.reports.append(Finding("page-report", values={"text": text}))

        page.on("console", console)
        answer_reports(page)
        self.network_errors = _failed_requests(page)

    def findings(self, page, unready: PageNotReady | None = None) -> list[Finding]:
        """The reports, each in the words the runtime gave it, then the stage the page
        never reached (`unready`), and where any of those failed it, the requests that
        failed; [] is a pass. Read once the page is ready, or has missed a stage."""
        # A page that refused to start still answers, and posts why; one that missed a
        # stage may not answer at all. The report is posted asynchronously, and the
        # route answers it, and the console line reaches this process, only while it
        # is waiting on the page, so the stage joins the reports once that wait ends.
        try:
            if unready is None or unready.stage == "refused":
                wait_for_probe(page, "sendsAcked")
        finally:
            if unready is not None:
                self.reports.append(unready_finding(unready))
        if not self.reports:
            return []
        return [*self.reports, *self.network_errors]


def _failed_requests(page) -> list[Finding]:
    """The requests of `page` that fail or answer an error status from now on, filled
    in as they do, each with its resource type and the address of the frame that made
    it (`frame_address`). A request the page itself abandons, as a navigation does, is
    not a failure: Chromium names it `net::ERR_ABORTED`, Firefox `NS_BINDING_ABORTED`."""
    from playwright.sync_api import Error as PlaywrightError

    network_errors = []

    def frame_of(request) -> str:
        # Read as the failure arrives: a `Frame` follows its navigations, so read
        # later it would name the document the frame went on to, not the one that
        # made the request.
        try:
            return frame_address(request.frame.url)
        except PlaywrightError:
            # A service worker's request belongs to no frame.
            return "<no-frame>"

    def failed(request):
        failure = request.failure or "request failed"
        if "ERR_ABORTED" in failure or "NS_BINDING_ABORTED" in failure:
            return
        network_errors.append(
            Finding(
                "request-failed",
                values={
                    "kind": request.resource_type,
                    "error": failure,
                    "frame": frame_of(request),
                    "url": request.url,
                },
            )
        )

    def answered(response):
        if response.status < 400:
            return
        request = response.request
        network_errors.append(
            Finding(
                "request-status",
                values={
                    "status": response.status,
                    "kind": request.resource_type,
                    "frame": frame_of(request),
                    "url": request.url,
                },
            )
        )

    page.on("requestfailed", failed)
    page.on("response", answered)
    return network_errors


def frame_address(url: str) -> str:
    """A document's address as the user sees it: without the marks the bootstrap takes
    off the address bar as the document starts (`ADDRESS_MARKS`). A request can fail
    before that rewrite reaches this process, and the same document stays named the
    same whichever comes first, so the query left is spelled as the bootstrap's
    `URLSearchParams` spells it."""
    # `urlsplit` drops an empty fragment's `#`, which the browser keeps.
    document, hash_mark, fragment = url.partition("#")
    parts = urlsplit(document)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    if not any(name in ADDRESS_MARKS for name, _ in pairs):
        return url
    query = "&".join(
        f"{_form_encoded(name)}={_form_encoded(value)}"
        for name, value in pairs
        if name not in ADDRESS_MARKS
    )
    return urlunsplit(parts._replace(query=query)) + hash_mark + fragment


def _form_encoded(text: str) -> str:
    """`text` as the WHATWG form serializer writes it, which keeps only ASCII
    alphanumerics and `*-._`, where Python's quoting also keeps `~` and drops `*`."""
    return quote_plus(text, safe="*").replace("~", "%7E")


def run_page_code(browser, url: str) -> list[Finding]:
    """Every error the served page reports while it upgrades and first presents, in a
    page of its own.

    Returns the reports, each in the words the runtime gave it, then any stage the page
    never reached; [] is a pass."""
    from playwright.sync_api import Error as PlaywrightError

    page = open_render_page(browser, viewport=RENDER_VIEWPORT, color_scheme="light")
    code = PageCode(page)
    try:
        page.goto(asked_again(url))
        unready = None
        try:
            state = served(page, url, "/api/state").json()
            wait_until_ready(page, state, fixed_server=True)
            start_near_work(page, state, fixed_server=True)
            # A widget that paints from a rendering callback throws there, not in its
            # upgrade; once the rendering has settled, every callback it queued has run.
            rendered(page)
        except PageNotReady as error:
            unready = error
        return code.findings(page, unready)
    except PlaywrightError as error:
        # A wait that timed out names what never arrived; any other browser error
        # is as much a failed run, and the reports already taken still stand.
        browser_error = Finding("browser-error", values={"error": str(error).strip()})
        return [*code.reports, browser_error, *code.network_errors]
    finally:
        page.close()
