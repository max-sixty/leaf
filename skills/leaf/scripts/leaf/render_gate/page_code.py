"""The run plain `page check` gives what only a browser can judge.

A page can carry code of its own: module scripts, and page widgets below `/page/`,
with whatever each imports. It can also place a widget whose body is data
(`x-content: data`): a chart's Plot expression, a diagram's Mermaid source, a diff, in
a notation only the widget's module reads. No static reading can say whether that code
throws or whether the module can read that body, and a quick page never reaches
`--render`, so a module that breaks on its first paint, or a chart whose body fails,
used to pass the check and reach the user, and its author heard about it only from the
watcher's `error` event. The check therefore runs the exact candidate once, wherever
the page carries either: through upgrade, authoritative presentation, and one rendering
frame after it, at the render viewport in the light scheme. A thread message's markup
is run the same way before it is posted (`message_page`).

What fails it is what the runtime would report to the agent. `runtime/layer-client.js`
posts every uncaught error and unhandled rejection, every widget that fails soft, and
every fault the runtime reports about the page itself, as an `error` event; that is
the event `leaf wait` delivers. The run intercepts those posts rather than reading the browser's own
channels, so the check and the watcher fail on one set, spelled the same way and
naming the same source location. The preview server is read-only, so the reports
are answered here and reach no log.

A pass is narrower than `--render`: nothing here reads layout, color schemes, print,
or replay, and code that throws only after a gesture or a timer is not reached.
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

from .scheme import answer_reports, served


def needs_browser(document: SourceDocument, artifact: RevisionArtifact) -> bool:
    """Whether this revision runs what only a browser can judge: a script, a page
    widget the document uses, or a data widget it places. A module a script imports
    is reached through that script, and a widget the document never places never
    loads."""
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


def message_page(fragment: SourceDocument) -> SourceDocument:
    """A message's widget markup as a page of its own, as a sample's template is one.

    A message's widgets stand in the thread rather than the page, where one in a shut
    panel has no room to draw, so the run gives them the column that the page's own
    widgets have. The page's document stays out of it: an error here is the message's."""
    return SourceDocument(
        '<!doctype html><html lang="en"><head><title>Message</title></head>'
        f'<body><main class="layout-column">{fragment.html}</main></body></html>'
    )


def run_page_code(browser, url: str) -> list[str]:
    """Every error the served page reports while it upgrades and first presents.

    Returns the reports as the runtime words them, then any stage the page never
    reached; [] is a pass."""
    from playwright.sync_api import Error as PlaywrightError

    reports = []
    page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme="light")
    answer_reports(page, reports.append)
    try:
        page.goto(url)
        wait_until_ready(page, served(page, url, "/api/state").json())
        # A widget that paints from a rendering callback throws there, not in its
        # upgrade; once the rendering has settled, every callback it queued has run.
        rendered(page)
        # The report is posted asynchronously, and the route above answers it only
        # while this process is waiting on the page.
        wait_for_probe(page, "sendsAcked")
    except PageNotReady as error:
        return [*reports, str(error)]
    except PlaywrightError as error:
        # A wait that timed out names what never arrived; any other browser error
        # is as much a failed run, and the reports already taken still stand.
        return [*reports, str(error).strip().splitlines()[0]]
    finally:
        page.close()
    return reports
