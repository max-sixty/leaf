"""Command boundary for mutable-source validation."""

import sys
from contextlib import nullcontext
from pathlib import Path

from leaf.event_log import flocked, read_events
from leaf.files import list_revisions
from leaf.leases import transition_lock
from leaf.revision_artifact import read_artifact

from .source import check_source


def cmd_check(
    page_dir: Path,
    render: bool = False,
    *,
    transition_held: bool = False,
    events_override: list | None = None,
) -> int:
    """Check the mutable source without activating or stamping it."""
    with nullcontext() if transition_held else flocked(transition_lock(page_dir)):
        return _check(page_dir, render, events_override)


def _check(page_dir: Path, render: bool, events_override: list | None) -> int:
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
        "✓ index.html: parses, widgets, authored modules, and theme validate, "
        "protected ids and decisions carried over, nothing overflows the "
        f"{result.column}px column",
        # Ahead of any browser gate's stderr, which a piped reader gets unbuffered.
        flush=True,
    )
    for line in result.advice:
        print(f"  · {line}")
    from leaf.render_gate.page_code import authors_code

    runs_code = authors_code(result.document, result.artifact)
    if not (runs_code or render):
        return 0
    from leaf.render_gate.command import page_code_check, render_check

    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else 0
    revision = active
    if not active or read_artifact(page_dir, active).digest != result.artifact.digest:
        revision = active + 1
    candidate = (page_dir, result.document, revision, result.artifact)
    if runs_code and page_code_check(*candidate):
        return 1
    return render_check(*candidate) if render else 0
