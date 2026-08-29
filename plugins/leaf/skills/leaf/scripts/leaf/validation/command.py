"""Command boundary for mutable-source validation."""

import sys
from pathlib import Path

from leaf.event_log import flocked, read_events
from leaf.files import list_revisions, revision_path
from leaf.leases import transition_lock

from .source import check_source


def cmd_check(
    page_dir: Path,
    render: bool = False,
    *,
    transition_held: bool = False,
    events_override: list | None = None,
) -> int:
    """Check the mutable source without activating or stamping it."""
    if not transition_held:
        with flocked(transition_lock(page_dir)):
            return cmd_check(
                page_dir,
                render,
                transition_held=True,
                events_override=events_override,
            )
    events = read_events(page_dir) if events_override is None else events_override
    result = check_source(page_dir, events)
    if result.errors:
        print(f"✗ index.html: {len(result.errors)} issue(s)", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        for line in result.advice:
            print(f"  · {line}", file=sys.stderr)
        return 1
    print(
        "✓ index.html: parses, widgets validate, one module script + theme link, "
        "protected ids and decisions carried over, nothing overflows the "
        f"{result.column}px column"
    )
    for line in result.advice:
        print(f"  · {line}")
    if render:
        from leaf.render_gate.command import render_check

        revisions = list_revisions(page_dir)
        active = revisions[-1] if revisions else 0
        revision = active
        if not active or revision_path(page_dir, active).read_bytes() != result.data:
            revision = active + 1
        return render_check(
            page_dir,
            source=result.data,
            revision=revision,
            transition_held=True,
        )
    return 0
