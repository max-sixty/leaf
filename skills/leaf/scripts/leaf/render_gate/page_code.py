"""The run plain `version check` gives a page's own code.

A page can carry code of its own: module scripts, and page widgets below `/page/`,
with whatever each imports. No static reading can say whether that
code throws, and a quick page never reaches `--render`, so a module that breaks on
its first paint used to pass the check and reach the user, and its author heard
about it only from the watcher's `error` event. The check therefore runs the exact
candidate once, wherever the page authored code: through upgrade, authoritative
presentation, and one rendering frame after it, at the render viewport in the light
scheme.

What fails it is what the runtime would report to the agent. `runtime/layer-client.js`
posts every uncaught error and unhandled rejection, and every fault the runtime
reports about the page itself, as an `error` event; that is the event `leaf wait`
delivers. The run intercepts those posts rather than reading the browser's own
channels, so the check and the watcher fail on one set, spelled the same way and
naming the same source location. The preview server is read-only, so the reports
are answered here and reach no log.

A pass is narrower than `--render`: nothing here reads layout, color schemes, print,
or replay, and code that throws only after a gesture or a timer is not reached.
"""

from leaf.render_checks import (
    RENDER_VIEWPORT,
    evaluate_probe,
    wait_for_presentation,
    wait_for_probe,
)
from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument

from .scheme import served


def authors_code(document: SourceDocument, artifact: RevisionArtifact) -> bool:
    """Whether this revision runs code its author wrote: a module script, or a page
    widget the document uses. A module a script imports is reached through that
    script, and a page widget the document never places never loads."""
    scripts = [*document.inline_scripts, *document.external_scripts]
    if any(script["attrs"].get("type") == "module" for script in scripts):
        return True
    page_widgets = [
        tag
        for tag, implementation in artifact.implementations.items()
        if implementation["owner"] == "page"
    ]
    return bool(page_widgets) and (
        document.tree.select_one(", ".join(page_widgets)) is not None
    )


def run_page_code(browser, url: str) -> list[str]:
    """Every error the served page reports while it upgrades and first presents.

    Returns the reports as the runtime words them, then any stage the page never
    reached; [] is a pass."""
    from playwright.sync_api import Error as PlaywrightError

    reports = []

    def report(route):
        event = route.request.post_data_json
        if event["kind"] != "error":
            route.continue_()
            return
        reports.append(event["text"])
        route.fulfill(status=204)

    page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme="light")
    page.route("**/api/event", report)
    try:
        page.goto(url)
        wait_for_probe(page, "upgraded")
        state = served(page, url, "/api/state").json()
        applied = sum(e["kind"] in ("action", "report") for e in state["events"])
        stage = wait_for_presentation(page, state, applied)
        if stage is not None:
            return [*reports, f"the runtime never passed its {stage} stage"]
        # A widget that paints from a rendering callback throws there, not in its
        # upgrade; once the rendering has settled, every callback it queued has run.
        wait_for_probe(page, "framePresented", evaluate_probe(page, "requestFrame"))
        wait_for_probe(page, "renderingSettled")
        # The report is posted asynchronously, and the route above answers it only
        # while this process is waiting on the page.
        wait_for_probe(page, "sendsAcked")
    except PlaywrightError as error:
        # A wait that timed out names what never arrived; any other browser error
        # is as much a failed run, and the reports already taken still stand.
        return [*reports, str(error).strip().splitlines()[0]]
    finally:
        page.close()
    return reports
