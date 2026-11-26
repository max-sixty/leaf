"""The browser check a thread message's markup runs before it posts (`message_check`),
which each thread write takes from its command (`thread.MessageCheck`).

A message's markup is run as plain `page check` runs a page (`page_code.py`),
wherever it places a widget only a browser can judge
(`browser_judged.places_judged_widget`). Nothing else draws it before the user opens
its thread, so posting is the one moment its author can fix it before the user sees
it, since its author may never have run `--render`. A message with no such widget
waits on no browser.

The thread commands import this module even for a message of plain text, and a write
runs the check only on a message holding HTML (`thread.drawn_markup`), so the module
imports the browser run only where that markup places such a widget."""

from pathlib import Path

import turbohtml

from leaf.base.files import latest_revision
from leaf.base.findings import Rejected, note
from leaf.records.markup_checks.markup import repair_errors
from leaf.source.browser_judged import places_judged_widget
from leaf.source.capture_refusals import ArtifactError
from leaf.source.revision_artifact import capture_artifact
from leaf.source.structure import SourceDocument, element_attrs, script_kind
from leaf.source.vocabulary import read_page_registry


def message_page(markup: str) -> SourceDocument:
    """A message's markup as a page of its own, as a sample's template is one.

    A message's widgets stand in its thread rather than the page, where a chart in a
    shut panel has no room to draw, so the run gives them the column the page's own
    widgets have. The page's document stays out of it, so an error here is the
    message's. A thread inserts markup through `template.innerHTML`, which never runs
    a script in it, so the page leaves out every script a browser would run: the run is
    for the widgets the markup places (`browser_judged.places_judged_widget`), and a
    script there would refuse a message for code the user never runs, or change what
    the run reads."""
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


def message_check(page_dir: Path, kind: str, markup: str) -> None:
    """Run a message's markup once, as a page of its own (`message_page`), where it
    places a widget only a browser can judge, and refuse it on every error that run
    reports, as plain `page check` fails a page. Takes the page's current layer, the
    one the thread will draw the message with. Where the host has no browser, or the
    browser fails before it reads the message, the message posts unrun, and reports
    any failure when its thread draws.

    A caller runs it before it takes the page lease to admit the message, since a
    browser run takes about a second. The run's capture holds the lease only while
    it reads the log (`page_snapshot.capture_page_snapshot`)."""
    if repair_errors(SourceDocument(markup, fragment=True)):
        # Markup the HTML parser repairs, such as a widget a `<pre>` closed along
        # with the paragraph Markdown drew around it, is the markup gate's to
        # refuse, showing the HTML Markdown drew, where a run would report only
        # the widget the repair emptied.
        return
    layer = read_page_registry(page_dir)
    if layer is None:
        return
    document = message_page(markup)
    try:
        artifact = capture_artifact(
            page_dir,
            document,
            layer.registry,
            declaration_sources=layer.declaration_sources,
            widget_sources=layer.widget_sources,
        )
    except ArtifactError:
        # Markup that names what no page may load, such as the theme's stylesheet,
        # is the markup gate's to refuse, in its own words, under the page lease.
        return
    if not places_judged_widget(document, artifact):
        return
    from leaf.pages.page_snapshot import capture_page_snapshot
    from leaf.pages.render_gate.command import browser_check

    revision = (latest_revision(page_dir) or 0) + 1
    snapshot = capture_page_snapshot(
        page_dir, document, revision, url="/", artifact=artifact
    )
    ran = browser_check(page_dir, snapshot, page_code=True, render=False)
    # What explains a failure without deciding one, such as a request that failed,
    # and a run the browser couldn't finish, which posts the message as a host with
    # no browser does, go beside the result.
    note(*(f for f in ran.findings() if not f.refuses))
    if ran.status:
        raise Rejected(
            [f for f in ran.findings() if f.refuses],
            f"the HTML in the {kind} doesn't draw",
        )
