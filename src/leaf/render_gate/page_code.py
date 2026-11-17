"""The run plain `page check` gives what only a browser can judge.

A page can carry code of its own: module scripts, and page widgets below `/page/`,
with whatever each imports. It can also place a widget whose module reads content the
static check only proves exists: a body of data (`content: data`), such as a chart's
Plot expression, a diagram's Mermaid source or a diff, in a notation only the widget's
module reads, or page media an attribute names, such as a screenshot pair whose two
widths have to match. No static reading can say whether that code throws or whether
the module can read that content, and a quick page never reaches `--render`. Without a
browser run, a module that breaks on its first paint, or a chart whose body fails,
would pass the check and reach the user, and its author would hear about it only from
the watcher's `error` event. The check therefore runs the exact candidate once,
wherever the page carries any of these: through upgrade, authoritative presentation,
and one rendering frame after it, in the light scheme, at the render viewport, or with
`--render` on the render check's page, at its desktop window (`PageCode`).

A thread message's markup is run the same way before it posts (`message_page`,
`command.message_check`), wherever it places one of those widgets. Nothing else draws
it before the user opens its thread, and the log freezes it, so posting is the one
moment its author can still fix it. In the `widgets-draw-as-written` evals, 5 of 6
Codex thread messages holding a Mermaid sequence diagram didn't draw (a `;` in a
loop label or note ends the statement), and their authors never ran `--render`. A
message with no such widget waits on no browser.

What fails it is what the runtime would report to the agent. `runtime/layer-client.js`
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

import turbohtml

from leaf.findings import Finding
from leaf.render_checks import (
    RENDER_VIEWPORT,
    PageNotReady,
    asked_again,
    rendered,
    start_near_work,
    wait_for_probe,
    wait_until_ready,
)
from leaf.revision_artifact import RevisionArtifact
from leaf.schema import MEDIA_DIR
from leaf.structure import SourceDocument, element_attrs, script_kind

from ..registry.contract import declared_fact
from .scheme import answer_reports, served


def needs_browser(document: SourceDocument, artifact: RevisionArtifact) -> bool:
    """Whether this revision runs what only a browser can judge: a script, or a
    placed widget whose module reads what no static check has, a page widget's own
    code, a data widget's body in a notation only its module parses, or the page
    media its attributes name. A module a script imports is reached through that
    script, and a widget the document never places never loads."""
    scripts = [
        *document.authoring.inline_scripts,
        *document.authoring.external_scripts,
    ]
    if any(script_kind(script["attrs"]) in {"module", "classic"} for script in scripts):
        return True
    return places_judged_widget(document, artifact)


def places_judged_widget(document: SourceDocument, artifact: RevisionArtifact) -> bool:
    """Whether the document places a widget whose module reads what no static check
    has: a page widget's own code, a data widget's body, or the page media its
    attributes name. A widget the document never places never loads."""
    registry = artifact.registry
    implementations = artifact.implementations
    return any(
        implementations[record["tag"]]["owner"] == "page"
        or declared_fact(registry[record["tag"]], "content") == "data"
        or any(
            isinstance(value, str) and value.startswith(f"/{MEDIA_DIR}/")
            for value in record["attrs"].values()
        )
        for record in document.lf_elements
        if record["tag"] in implementations
    )


def message_page(markup: str) -> SourceDocument:
    """A message's markup as a page of its own, as a sample's template is one.

    A message's widgets stand in its thread rather than the page, where a chart in a
    shut panel has no room to draw, so the run gives them the column the page's own
    widgets have. The page's document stays out of it, so an error here is the
    message's. A thread inserts markup through `template.innerHTML`, which never runs
    a script in it, so the page leaves out every script a browser would run: the run is
    for the widgets the markup places (`places_judged_widget`), and a script there would
    refuse a message for code the user never runs, or change what the run reads."""
    source = (
        '<!doctype html><html lang="en"><head><title>Message</title></head>'
        f'<body><main class="layout-column">{markup}</main></body></html>'
    )
    tree = turbohtml.parse(source, scripting=True, source_locations=True)
    for script in reversed(tree.find_all("script")):
        location = script.source_location
        if location is None or script_kind(element_attrs(script)) == "data":
            continue
        end = (location.end_tag or location.start_tag).end_offset
        source = source[: location.start_tag.start_offset] + source[end:]
    return SourceDocument(source)


# How `runtime/layer-client.js` `reportPageError` opens the console line it writes for
# each report, ahead of the words it posts.
REPORTED = "leaf: "


class PageCode:
    """The page-code reading of one browser page, from before its navigation: every
    error the runtime reports, and the requests that failed while it ran. A page opened
    for it alone (`run_page_code`) or the render check's page (`scheme._render_page`)
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
        reports = self.reports
        if unready is not None:
            reports.append(
                Finding(
                    "not-ready", values={"stage": unready.stage, "error": str(unready)}
                )
            )
        # A page that refused to start still answers, and posts why; one that missed a
        # stage may not answer at all. The report is posted asynchronously, and the
        # route answers it, and the console line reaches this process, only while it
        # is waiting on the page.
        if unready is None or unready.stage == "refused":
            wait_for_probe(page, "sendsAcked")
        return [*reports, *self.network_errors] if reports else []


def _failed_requests(page) -> list[Finding]:
    """The requests of `page` that fail or answer an error status from now on, filled
    in as they do, each with its resource type and the address of the frame that made
    it, which the bootstrap rewrites before any request it makes, taking off its marks
    (`asked_again`) and the host key. A request the page itself abandons, as a
    navigation does, is not a failure: Chromium names it `net::ERR_ABORTED`, Firefox
    `NS_BINDING_ABORTED`."""
    from playwright.sync_api import Error as PlaywrightError

    network_errors = []

    def frame_of(request) -> str:
        try:
            return request.frame.url
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


def run_page_code(browser, url: str) -> list[Finding]:
    """Every error the served page reports while it upgrades and first presents, in a
    page of its own.

    Returns the reports, each in the words the runtime gave it, then any stage the page
    never reached; [] is a pass."""
    from playwright.sync_api import Error as PlaywrightError

    page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme="light")
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
