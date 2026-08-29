"""Command boundary for browser-backed page validation."""

import sys
from pathlib import Path

from leaf.files import version_name

from .preview import preview_server, preview_source_server
from .version import render_version


def render_check(
    page_dir: Path,
    version: int | None = None,
    *,
    source: bytes | None = None,
    revision: int | None = None,
    preview=None,
    render=None,
    transition_held: bool = False,
) -> int:
    """Serve the page directory to the machine's installed Chrome and run the
    render invariants on this version.

    Playwright is the gate's own extra, not the payload's: declaring it in
    `pyproject.toml` would put its wheel in every `server run`, `leaf wait`, and
    `version stamp`, so the import happens here and its absence names the
    invocation that supplies it. Chrome is part of this gate: if it cannot
    launch, the gate fails."""
    if source is not None and revision is None:
        raise ValueError("a source preview needs its candidate revision")
    preview = (
        (preview_source_server if source is not None else preview_server)
        if preview is None
        else preview
    )
    render = render_version if render is None else render
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "version check --render needs Playwright; run it as\n"
            "  leaf version check <page> --render\n"
            "or, from a checkout,\n"
            "  bin/leaf version check <page> --render",
            file=sys.stderr,
        )
        return 1
    name = "index.html" if source is not None else version_name(version)
    preview_args = (
        (page_dir, source, revision) if source is not None else (page_dir, version)
    )
    with (
        preview(*preview_args, transition_held=transition_held) as url,
        sync_playwright() as p,
    ):
        try:
            browser = p.chromium.launch(channel="chrome")
        except PlaywrightError as error:
            print(
                "✗ render check failed — Chrome did not launch: "
                + str(error).strip().splitlines()[0],
                file=sys.stderr,
            )
            return 1
        try:
            failures = render(browser, url)
        finally:
            browser.close()
    if failures:
        print(f"✗ {name}: renders broken — {len(failures)} issue(s)", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        f"✓ {name}: renders clean in Chrome, light and dark — no console errors, "
        "every widget takes space, no words on top of other words, code that reads "
        "against the block it is on, boxes showing the inset they draw, nothing past the "
        "column, no sideways scroll"
    )
    return 0
