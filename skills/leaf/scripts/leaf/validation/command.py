"""Command boundary for mutable-source validation."""

import sys
from pathlib import Path

from leaf.event_log import read_events
from leaf.files import list_revisions
from leaf.layer import payload_provenance, provenance_label, same_leaf
from leaf.leases import page_locked
from leaf.registry.contract import RegistryError
from leaf.registry.storage import layer_metadata
from leaf.revision_artifact import read_revision

from .source import check_source


def cmd_check(page_dir: Path, render: bool = False) -> int:
    """Check the mutable source without activating or stamping it."""
    with page_locked(page_dir):
        return _check(page_dir, render)


def leaf_versions(page_dir: Path) -> list[str]:
    """The Leaf that vendored the page beside the one checking it, where they differ.

    Between protocol bumps an update can still break an older page (`AGENTS.md`,
    "Pages across Leaf updates"), and nothing compares the page's files with this
    Leaf's to say so. Both versions and their dates let the agent judge whether a
    page that misbehaves wants re-vendoring."""
    try:
        page_leaf = layer_metadata(page_dir).get("producer", {})
    except RegistryError:
        return []  # `check_source` reports the broken layer
    this_leaf = payload_provenance()
    if same_leaf(page_leaf, this_leaf):
        return []
    return [
        (
            f"Leaf {provenance_label(page_leaf)} vendored this page; this is Leaf "
            f"{provenance_label(this_leaf)}. If the page misbehaves, "
            f"`leaf page init {page_dir}` re-vendors it."
        )
    ]


def _check(page_dir: Path, render: bool) -> int:
    events = read_events(page_dir)
    result = check_source(page_dir, events)
    advice = [*result.advice, *leaf_versions(page_dir)]
    if result.errors:
        print(
            f"Error: index.html has {len(result.errors)} validation issue{'s' if len(result.errors) != 1 else ''}",
            file=sys.stderr,
        )
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        for line in advice:
            print(f"  · {line}", file=sys.stderr)
        return 1
    print(
        "✓ index.html: valid",
        # Ahead of any browser gate's stderr, which a piped reader gets unbuffered.
        flush=True,
    )
    for line in advice:
        print(f"  · {line}")
    from leaf.render_gate.page_code import needs_browser

    runs_code = needs_browser(result.document, result.artifact)
    if not (runs_code or render):
        return 0
    from leaf.render_gate.command import browser_check

    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else 0
    revision = active
    if not active or read_revision(page_dir, active).digest != result.artifact.digest:
        revision = active + 1
    return browser_check(
        page_dir,
        result.document,
        revision,
        result.artifact,
        page_code=runs_code,
        render=render,
    )
