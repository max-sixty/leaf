"""Command boundary for mutable-source validation.

`page check` returns one JSON object, which the CLI prints and exits with its status
(`cli.Reported`): `status`, the exit status; `findings`, every finding as
`findings.Finding.json` gives it, the markup checks' first; and `browser`, the browser
gates `asked` for and those that `ran` (failing page code ends the check before the
render gate reads anything), in which browser or why none could, with the render
gate's margin widths and saved screens even when it reports findings. `browser` is
null where no gate needed one. The agent's render check leaves its reading for the
page's server (`render_gate.handover_pass`), which runs the same check without its
screens (`check_page`) and keeps its own reading.
"""

from pathlib import Path

from leaf.event_log import read_events
from leaf.files import list_revisions
from leaf.leases import page_locked
from leaf.registry.contract import RegistryError
from leaf.registry.storage import layer_record, selected

from .source import check_source, moved_threads, source_advice


def cmd_check(page_dir: Path, render: bool = False) -> dict:
    """`page check` as the agent runs it, whose render check leaves a reading of every
    finding it reported, since the agent has read them all."""
    report, read = check_page(page_dir, render)
    if read is not None:
        from leaf.render_gate.handover_pass import remember_reading

        remember_reading(page_dir, *read)
    return report


def check_page(page_dir: Path, render: bool = False, *, screens: bool = True):
    """`page check`'s report, and where a render check ran, the digest of the version it
    read with what the browser read (`render_gate.command.BrowserCheck`), else None.
    Freezes the checked source before running slow, read-only browser work."""
    from leaf.event_contracts import write_refusal

    def reported(status, findings, browser=None):
        return {
            "status": status,
            "findings": [f.json() for f in findings],
            "browser": browser.json() if browser else None,
        }

    with page_locked(page_dir):
        # A page this Leaf can neither serve nor write passes no check of its source: the
        # repair it names comes first (`layer.incompatible_layer`).
        if refusal := write_refusal(page_dir):
            return reported(1, [refusal]), None
        # Nor does one whose layer can't be composed to serve it. The check composes
        # it here because reading the page needs only its vocabulary
        # (`layer.LayerVocabulary`).
        if (record := layer_record(page_dir)) is not None:
            try:
                selected(record, page_dir)
            except RegistryError as error:
                return reported(1, list(error.findings)), None
        events = read_events(page_dir)
        result = check_source(page_dir, events)
        active = max(list_revisions(page_dir), default=0)
        found = [
            *result.errors,
            *moved_threads(page_dir, events, active - 1, result),
            *source_advice(page_dir, result),
        ]
        if result.errors:
            return reported(1, found), None
        from leaf.render_gate.page_code import needs_browser

        assert result.artifact is not None
        runs_code = needs_browser(result.document, result.artifact)
        if not (runs_code or render):
            return reported(0, found), None
        from leaf.page_snapshot import capture_page_snapshot

        snapshot = capture_page_snapshot(
            page_dir,
            result.document,
            result.revision.candidate,
            url="/",
            artifact=result.artifact,
        ).through(events[-1]["seq"] if events else 0)

    from leaf.render_gate.command import browser_check

    browser = browser_check(
        page_dir,
        snapshot,
        page_code=runs_code,
        render=render,
        screens=screens,
    )
    report = reported(browser.status, [*found, *browser.findings()], browser)
    return report, (result.artifact.digest, browser) if render else None
