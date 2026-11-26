"""Command boundary for mutable-source validation.

`page check` returns one JSON object, which the CLI prints and exits with its status
(`cli.Reported`): `status`, the exit status; `findings`, every finding as
`findings.Finding.json` gives it, the markup checks' first; and `browser`, the browser
gates `asked` for and those that `ran` (failing page code ends the check before the
render gate reads anything), in which browser or why none could, with the render
gate's margin widths and saved screens even when it reports findings, unless the page
was not ready for them. `browser` is null where no gate needed one. The agent's render
check leaves its reading (`render_reading`) for `page state` and for the page's server
(`handover_pass`), which runs the same check without its screens
(`check_page`) and keeps its own reading. Beside the source's own findings it names
the drafts a Leaf of another version left in the page directory
(`other_version_drafts`).
"""

from pathlib import Path

from leaf.base.files import list_revisions
from leaf.base.findings import Finding
from leaf.base.leases import page_locked
from leaf.base.schema import DRAFTS_FILE
from leaf.log.event_log import read_events
from leaf.records.authored_checks.source import (
    check_source,
    moved_threads,
    source_advice,
)
from leaf.serving.handover_pass import remember_reading
from leaf.source.browser_judged import needs_browser
from leaf.source.layer import selected_layer
from leaf.source.registry.contract import RegistryError
from leaf.source.registry.storage import layer_record


def cmd_check(page_dir: Path, render: bool = False) -> dict:
    """`page check` as the agent runs it, whose render check leaves a reading of every
    finding it reported, since the agent has read them all."""
    report, read = check_page(page_dir, render)
    if read is not None:
        remember_reading(page_dir, *read)
    return report


def other_version_drafts(page_dir: Path) -> list[Finding]:
    """A note naming each drafts store a Leaf of another shape of it kept in the page
    directory, which this Leaf reads none of (`state.Record.others`): the user's
    unsent words, which only the user can say are no longer wanted. The page's other
    records of other shapes are disposable, so `page check` names none of them."""
    from leaf.serving.drafts import DRAFTS

    return [
        Finding(
            "other-version-drafts", values={"page": str(page_dir), "file": str(file)}
        )
        for file in DRAFTS.others(page_dir / DRAFTS_FILE)
    ]


def check_page(page_dir: Path, render: bool = False, *, screens: bool = True):
    """`page check`'s report, and where a render check ran, the digest of the version it
    read and the version of the data it read it with (`data.data_version`), with what
    the browser read (`render_gate.command.BrowserCheck`), else None. Freezes the
    checked source and data before running slow, read-only browser work."""

    def reported(status, findings, browser=None):
        return {
            "status": status,
            "findings": [f.json() for f in findings],
            "browser": browser.json() if browser else None,
        }

    with page_locked(page_dir):
        # A page this Leaf can neither serve nor write (`layer_record`), or whose
        # layer can't be composed to serve it, passes no check of its source: the
        # repair it names comes first. The check composes the layer here because
        # reading the page needs only its vocabulary (`layer.LayerVocabulary`).
        try:
            if (record := layer_record(page_dir)) is not None:
                selected_layer(record, page_dir)
        except RegistryError as error:
            return reported(1, list(error.findings)), None
        events = read_events(page_dir)
        result = check_source(page_dir, events)
        active = max(list_revisions(page_dir), default=0)
        found = [
            *result.errors,
            *moved_threads(page_dir, events, active - 1, result),
            *source_advice(page_dir, result),
            *other_version_drafts(page_dir),
        ]
        if result.errors:
            return reported(1, found), None
        assert result.artifact is not None
        runs_code = needs_browser(result.document, result.artifact)
        if not (runs_code or render):
            return reported(0, found), None
        from leaf.pages.page_snapshot import capture_page_snapshot

        snapshot = capture_page_snapshot(
            page_dir,
            result.document,
            result.revision.candidate,
            url="/",
            artifact=result.artifact,
        ).through(events[-1]["seq"] if events else 0)

    from leaf.pages.render_gate.command import browser_check

    browser = browser_check(
        page_dir,
        snapshot,
        page_code=runs_code,
        render=render,
        screens=screens,
    )
    report = reported(browser.status, [*found, *browser.findings()], browser)
    read = (result.artifact.digest, snapshot.context.data["version"], browser)
    return report, read if render else None
