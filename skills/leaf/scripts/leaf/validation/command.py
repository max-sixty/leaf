"""Command boundary for mutable-source validation.

`page check` prints its findings for a reader, or with `--json` one JSON object on
stdout: `status`, the exit status; `findings`, every finding as
`render_gate.findings.Finding.json` gives it, the markup checks' first; and `browser`,
the browser gates `asked` for and those that `ran` (failing page code ends the check
before the render gate reads anything), in which browser or why none could, with the
render gate's margin widths and saved screens where it passed. `browser` is null where
no gate needed one.
"""

import json
import sys
from pathlib import Path

from leaf.event_log import read_events
from leaf.files import list_revisions
from leaf.layer import payload_provenance, provenance_label, same_leaf
from leaf.leases import page_locked
from leaf.registry.contract import RegistryError
from leaf.registry.storage import layer_metadata
from leaf.render_gate.findings import Finding
from leaf.revision_artifact import read_revision

from .source import check_source


def cmd_check(page_dir: Path, render: bool = False, as_json: bool = False) -> int:
    """Check the mutable source without activating or stamping it."""
    with page_locked(page_dir):
        return _check(page_dir, render, as_json)


def leaf_versions(page_dir: Path) -> list[Finding]:
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


def _check(page_dir: Path, render: bool, as_json: bool) -> int:
    events = read_events(page_dir)
    result = check_source(page_dir, events)
    errors = [Finding("markup", values={"text": error}) for error in result.errors]
    advice = [
        *(
            Finding("markup", values={"text": line}, severity="advice")
            for line in result.advice
        ),
        *leaf_versions(page_dir),
    ]

    def reported(status, browser=None):
        print(
            json.dumps(
                {
                    "status": status,
                    "findings": [
                        f.json()
                        for f in [
                            *errors,
                            *advice,
                            *(browser.findings() if browser else []),
                        ]
                    ],
                    "browser": browser.json() if browser else None,
                },
                ensure_ascii=False,
            )
        )
        return status

    if errors:
        if as_json:
            return reported(1)
        print(
            f"Error: index.html has {len(errors)} validation issue{'s' if len(errors) != 1 else ''}",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        for line in advice:
            print(f"  · {line}", file=sys.stderr)
        return 1
    if not as_json:
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
        return reported(0) if as_json else 0
    from leaf.render_gate.command import browser_check, print_browser_check

    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else 0
    revision = active
    if not active or read_revision(page_dir, active).digest != result.artifact.digest:
        revision = active + 1
    browser = browser_check(
        page_dir,
        result.document,
        revision,
        result.artifact,
        page_code=runs_code,
        render=render,
    )
    if as_json:
        return reported(browser.status, browser)
    return print_browser_check(browser)
