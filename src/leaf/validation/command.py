"""Command boundary for mutable-source validation.

`page check` returns one JSON object, which the CLI prints and exits with its status
(`cli.Reported`): `status`, the exit status; `findings`, every finding as
`findings.Finding.json` gives it, the markup checks' first; and `browser`, the browser
gates `asked` for and those that `ran` (failing page code ends the check before the
render gate reads anything), in which browser or why none could, with the render
gate's margin widths and saved screens where it passed. `browser` is null where no
gate needed one.
"""

from pathlib import Path

from leaf.event_log import read_events
from leaf.files import list_revisions
from leaf.findings import Finding
from leaf.layer import payload_provenance, provenance_label, same_leaf
from leaf.leases import page_locked
from leaf.registry.contract import RegistryError
from leaf.registry.storage import layer_metadata

from .source import check_source, moved_threads, source_advice


def leaf_versions(page_dir: Path) -> list[Finding]:
    """The Leaf that vendored the page beside the one checking it, where they differ.

    Between protocol bumps an update can still break an older page (`AGENTS.md`,
    "Pages across Leaf updates"), and nothing compares the page's files with this
    Leaf's to say so. Both versions and their dates are informational; the protocol
    compatibility check owns the instruction to update the page's runtime."""
    try:
        page_leaf = layer_metadata(page_dir).get("producer", {})
    except RegistryError:
        return []  # `check_source` reports the broken layer
    this_leaf = payload_provenance()
    if same_leaf(page_leaf, this_leaf):
        return []
    return [
        Finding(
            "leaf-version",
            values={
                "vendored": provenance_label(page_leaf),
                "running": provenance_label(this_leaf),
                "page": str(page_dir),
            },
            severity="advice",
        )
    ]


def cmd_check(page_dir: Path, render: bool = False) -> dict:
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
        # re-vendor that repairs it comes first (`layer.incompatible_layer`).
        if refusal := write_refusal(page_dir):
            return reported(1, [refusal])
        events = read_events(page_dir)
        result = check_source(page_dir, events)
        active = max(list_revisions(page_dir), default=0)
        found = [
            *result.errors,
            *moved_threads(page_dir, events, active - 1, result),
            *source_advice(page_dir, result),
            *leaf_versions(page_dir),
        ]
        if result.errors:
            return reported(1, found)
        from leaf.render_gate.page_code import needs_browser

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

    browser = browser_check(
        page_dir,
        snapshot,
        page_code=runs_code,
        render=render,
    )
    return reported(browser.status, [*found, *browser.findings()], browser)
