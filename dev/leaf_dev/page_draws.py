"""Grade an authored page by whether every widget it places draws.

A Promptfoo `python` assertion for short authoring cases, measuring what plain
`page check` would catch if it ran every page in a browser (TODO.md, "Decide what
plain `page check` runs in a browser"). It serves the final page's source as `page
check` does and runs `render_gate.page_code.run_page_code` on it, whether or not
`needs_browser` would have asked for that run. Where an agent message carries
markup, it then opens each such thread, as a reader would, so the widgets posted
there draw too. A failure is what the runtime reports to the agent as an `error`
event, the report `leaf wait` would deliver, intercepted before it reaches the log.

The assertion passes when nothing reported. Its metadata says, for the page and
for its thread messages, which widgets were placed and what each drawing reported;
whether plain `page check` would have run the page in a browser; which drawing
failures the executor's final `--render` read, console errors the runtime doesn't
report included; and which page check runs during authoring reported a drawing
failure. A run's rates by widget kind read from `results.json`.

It reads the page with this checkout's Leaf, so it grades the candidate arm.
"""

import re
from pathlib import Path

from leaf.event_log import read_events
from leaf.render_checks import (
    RENDER_VIEWPORT,
    PageNotReady,
    evaluate_probe,
    rendered,
    wait_for_probe,
    wait_until_ready,
)
from leaf.render_gate.command import NoBrowser, run_in_browser
from leaf.render_gate.page_code import needs_browser, run_page_code
from leaf.render_gate.preview import preview_server
from leaf.render_gate.scheme import answer_reports, served
from leaf.structure import SourceDocument
from leaf.validation.source import check_source

# What a drawing failure is called in `page check`'s output, however an author
# reformatted it (`jq -c` drops the spaces): the page's own code reporting
# (`page_code`), or a console error or uncaught exception the render check read.
DRAW_FAILURE = re.compile(r'"code":\s*"(page-report|console-error|page-exception)"')


def draw(browser, url: str, *, threads: bool) -> dict:
    """What plain `page check`'s own run reports for the page (`run_page_code`),
    then, where `threads`, what the page reports while each thread holding markup
    is drawn."""
    found = {"page": [str(f) for f in run_page_code(browser, url)], "threads": {}}
    if threads:
        found["threads"] = draw_threads(browser, url)
    return found


def draw_threads(browser, url: str) -> dict[str, list[str]]:
    """Each thread holding markup, opened in turn where a reader would find it, as
    the render check opens them (`readings.thread_findings`), with what the page
    reported while it drew; a failure to open them at all is keyed `unopened`."""
    from playwright.sync_api import Error as PlaywrightError

    reports, found = [], {}
    page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme="light")
    answer_reports(page, reports.append)
    try:
        page.goto(url)
        state = served(page, url, "/api/state").json()
        wait_until_ready(page, state, fixed_server=True)
        rendered(page)
        wait_for_probe(page, "sendsAcked")
        for thread in evaluate_probe(page, "threadsHoldingMarkup"):
            reports.clear()
            evaluate_probe(page, "openThreadToCheck", thread)
            wait_for_probe(page, "threadOpening", thread)
            if not evaluate_probe(page, "threadOpening", thread)["shown"]:
                reports.append(f"thread {thread} never drew")
            rendered(page)
            wait_for_probe(page, "sendsAcked")
            found[thread] = reports[:]
    except (PageNotReady, PlaywrightError) as error:
        found["unopened"] = [*reports, str(error).strip()]
    finally:
        page.close()
    return found


def placed(page_dir: Path) -> dict:
    """Each drawing the page asks for, with the widgets in it: the page, and each
    agent message carrying markup, keyed by its thread."""
    events = read_events(page_dir)
    result = check_source(page_dir, events)
    if result.errors:
        return {"refused": [str(error) for error in result.errors]}
    roots = {}
    for event in events:
        if event.get("kind") in {"comment", "reply"}:
            roots[event["id"]] = roots.get(event.get("parent"), event["id"])
    messages = {}
    for event in events:
        if event.get("kind") in {"comment", "reply"} and event.get("markup"):
            tags = [r["tag"] for r in SourceDocument(event["markup"]).lf_elements]
            thread = messages.setdefault(roots[event["id"]], [])
            thread.extend(tag for tag in tags if tag not in thread)
    return {
        "result": result,
        "page": sorted({r["tag"] for r in result.document.lf_elements}),
        "messages": messages,
        "needs_browser": needs_browser(result.document, result.artifact),
    }


def session_reports(check_log: list[dict]) -> list[dict]:
    """The calls of the author's own page checks that reported a drawing failure."""
    return [
        entry["input"]
        for entry in check_log
        if "output" in entry and DRAW_FAILURE.search(entry["output"])
    ]


def get_assert(output: str, context: dict) -> dict:
    response = context["providerResponse"]
    if response.get("error"):
        return unscored(response["error"])
    metadata = response["metadata"]
    page_dir = Path(metadata["work"]) / "page"
    if not (page_dir / "index.html").is_file():
        return unscored("the author wrote no index.html")
    widgets = placed(page_dir)
    if "refused" in widgets:
        return unscored(f"page check refuses the final source: {widgets['refused']}")
    result = widgets.pop("result")
    try:
        with preview_server(
            page_dir,
            result.document,
            result.revision.candidate,
            artifact=result.artifact,
        ) as url:
            found, browser = run_in_browser(
                lambda browser: draw(browser, url, threads=bool(widgets["messages"]))
            )
    except NoBrowser as error:
        return unscored(f"no browser: {error}")
    failed = [*found["page"], *(r for rs in found["threads"].values() for r in rs)]
    passed = not failed
    return {
        "pass": passed,
        "score": float(passed),
        "reason": "every widget drew" if passed else "; ".join(failed),
        "metadata": {
            "page_draws": {
                **widgets,
                "browser": browser,
                "reports": found,
                # The executor's own final `--render`, which also reads console
                # errors the runtime doesn't report to the agent.
                "final_render": sorted(
                    set(DRAW_FAILURE.findall(metadata["check_output"]["render"]))
                ),
                "session_reports": session_reports(metadata["check_log"]),
            }
        },
    }


def unscored(reason: str) -> dict:
    return {"pass": False, "score": 0.0, "reason": f"unscored: {reason}"}
