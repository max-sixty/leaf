"""The run plain `page check` gives what only a browser can judge.

A page can carry code of its own: module scripts, and page widgets below `/page/`,
with whatever each imports. It can also place a widget whose body is data
(`x-content: data`): a chart's Plot expression, a diagram's Mermaid source, a diff, in
a notation only the widget's module reads. No static reading can say whether that code
throws or whether the module can read that body, and a quick page never reaches
`--render`. Without a browser run, a module that breaks on its first paint, or a chart
whose body fails, would pass the check and reach the user, and its author would hear
about it only from the watcher's `error` event. The check therefore runs the exact
candidate once, wherever the page carries either: through upgrade, authoritative
presentation, and one rendering frame after it, at the render viewport in the light
scheme.

What fails it is what the runtime would report to the agent. `runtime/layer-client.js`
posts every uncaught error and unhandled rejection, every widget that fails soft, and
every fault the runtime reports about the page itself, as an `error` event; that is
the event `leaf wait` delivers. The run intercepts those posts rather than reading the browser's own
channels, so the check and the watcher fail on one set, spelled the same way and
naming the same source location. The preview server is read-only, so the reports
are answered here and reach no log.

A failed browser run also reports failed network requests. Those readings explain a
failure; they do not decide one: optional assets and other requests that fail without a
page-code failure remain nonfatal. A pass is narrower than `--render`: nothing here
reads layout, color schemes, print, or replay, and code that throws only after a
gesture or a timer is not reached.
"""

from leaf.render_checks import (
    RENDER_VIEWPORT,
    PageNotReady,
    rendered,
    wait_for_probe,
    wait_until_ready,
)
from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument, script_kind

from .findings import Finding
from .scheme import answer_reports, served


def needs_browser(document: SourceDocument, artifact: RevisionArtifact) -> bool:
    """Whether this revision runs what only a browser can judge: a script, or a
    placed widget whose module reads what no static check has, a page widget's own
    code or a data widget's body in a notation only its module parses. A module a
    script imports is reached through that script, and a widget the document never
    places never loads."""
    scripts = [*document.inline_scripts, *document.external_scripts]
    if any(script_kind(script["attrs"]) in {"module", "classic"} for script in scripts):
        return True
    registry = artifact.registry
    judged = [
        tag
        for tag, implementation in artifact.implementations.items()
        if implementation["owner"] == "page" or registry[tag].get("x-content") == "data"
    ]
    return bool(judged) and document.tree.select_one(", ".join(judged)) is not None


def run_page_code(browser, url: str) -> list[Finding]:
    """Every error the served page reports while it upgrades and first presents.

    Returns the reports, each in the words the runtime gave it, then any stage the page
    never reached; [] is a pass."""
    from playwright.sync_api import Error as PlaywrightError

    reports = []
    page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme="light")
    answer_reports(
        page, lambda text: reports.append(Finding("page-report", values={"text": text}))
    )
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.enable")
    cdp.send("Network.enable")
    pending = {}
    frame_urls = {}
    network_errors = []

    def cdp_frame(params):
        frame = params["frame"]
        frame_urls[frame["id"]] = frame.get("url", "")

    def cdp_started(params):
        request = params["request"]
        request_id = params["requestId"]
        kind = params.get("type", "Other")
        frame_id = params.get("frameId", "<no-frame>")
        pending[request_id] = (kind, frame_id, request["url"])

    def cdp_finished(params):
        pending.pop(params["requestId"], None)

    def cdp_failed(params):
        request = pending.pop(params["requestId"], None)
        failure = params.get("errorText", "request failed")
        if request and "ERR_ABORTED" not in failure:
            kind, frame_id, failed_url = request
            network_errors.append(
                Finding(
                    "request-failed",
                    values={
                        "kind": kind,
                        "error": failure,
                        "frame": frame_urls.get(frame_id, frame_id),
                        "url": failed_url,
                    },
                )
            )

    def cdp_response(params):
        response = params["response"]
        if response["status"] >= 400:
            request = pending.get(params["requestId"])
            if request:
                kind, frame_id, failed_url = request
                frame_url = frame_urls.get(frame_id, frame_id)
            else:
                kind, frame_url, failed_url = (
                    "Other",
                    "<unknown-frame>",
                    response["url"],
                )
            network_errors.append(
                Finding(
                    "request-status",
                    values={
                        "status": response["status"],
                        "kind": kind,
                        "frame": frame_url,
                        "url": failed_url,
                    },
                )
            )

    cdp.on("Page.frameNavigated", cdp_frame)
    cdp.on("Network.requestWillBeSent", cdp_started)
    cdp.on("Network.loadingFinished", cdp_finished)
    cdp.on("Network.loadingFailed", cdp_failed)
    cdp.on("Network.responseReceived", cdp_response)
    try:
        page.goto(url)
        try:
            wait_until_ready(
                page, served(page, url, "/api/state").json(), fixed_server=True
            )
            # A widget that paints from a rendering callback throws there, not in its
            # upgrade; once the rendering has settled, every callback it queued has run.
            rendered(page)
            answering = True
        except PageNotReady as error:
            reports.append(
                Finding("not-ready", values={"stage": error.stage, "error": str(error)})
            )
            # A page that refused to start still answers, and posts why; one that
            # missed a stage may not answer at all.
            answering = error.stage == "refused"
        if answering:
            # The report is posted asynchronously, and the route above answers it only
            # while this process is waiting on the page.
            wait_for_probe(page, "sendsAcked")
    except PlaywrightError as error:
        # A wait that timed out names what never arrived; any other browser error
        # is as much a failed run, and the reports already taken still stand.
        reports.append(Finding("browser-error", values={"error": str(error).strip()}))
    finally:
        page.close()
    if reports and network_errors:
        reports.extend(network_errors)
    return reports
