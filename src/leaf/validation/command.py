"""Command boundary for mutable-source validation.

`page check` returns one JSON object, which the CLI prints and exits with its status
(`cli.Reported`): `status`, the exit status; `findings`, every finding as
`findings.Finding.json` gives it, the markup checks' first; and `browser`, the browser
gates `asked` for and those that `ran` (failing page code ends the check before the
render gate reads anything), in which browser or why none could, with the render
gate's margin widths and saved screens even when it reports findings. `browser` is
null where no gate needed one. A render check leaves its reading for the page's server
and stamp (`render_gate.handover_pass`), which runs one without its `screens`.
"""

from pathlib import Path

from leaf.event_log import read_events
from leaf.files import list_revisions
from leaf.leases import page_locked
from leaf.registry.contract import RegistryError
from leaf.registry.storage import layer_record, selected

from .source import check_source, moved_threads, source_advice


def cmd_check(page_dir: Path, render: bool = False, *, screens: bool = True) -> dict:
    """Freeze the checked source before running slow, read-only browser work."""
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
            return reported(1, [refusal])
        # Nor does one whose layer can't be composed to serve it. The check composes
        # it here because reading the page needs only its vocabulary
        # (`layer.LayerVocabulary`).
        if (record := layer_record(page_dir)) is not None:
            try:
                selected(record, page_dir)
            except RegistryError as error:
                return reported(1, list(error.findings))
        events = read_events(page_dir)
        result = check_source(page_dir, events)
        active = max(list_revisions(page_dir), default=0)
        found = [
            *result.errors,
            *moved_threads(page_dir, events, active - 1, result),
            *source_advice(page_dir, result),
        ]
        if result.errors:
            return reported(1, found)
        from leaf.render_gate.page_code import needs_browser

        assert result.artifact is not None
        runs_code = needs_browser(result.document, result.artifact)
        if not (runs_code or render):
            return reported(0, found)
        from leaf.page_snapshot import capture_page_snapshot

        snapshot = capture_page_snapshot(
            page_dir,
            result.document,
            result.revision.candidate,
            url="/",
            artifact=result.artifact,
        ).through(events[-1]["seq"] if events else 0)

    from leaf.render_gate.command import browser_check
    from leaf.render_gate.handover_pass import remember_reading

    browser = browser_check(
        page_dir,
        snapshot,
        page_code=runs_code,
        render=render,
        screens=screens,
    )
    if render:
        remember_reading(page_dir, result.artifact.digest, browser)
    return reported(browser.status, [*found, *browser.findings()], browser)
