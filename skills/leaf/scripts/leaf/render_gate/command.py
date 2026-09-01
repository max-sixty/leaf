"""Command boundary for browser-backed page validation."""

import sys
from pathlib import Path

from .browser import browser_hint, launch_browser, launched_name
from .preview import preview_server
from .version import render_version


def render_check(
    page_dir: Path,
    source: bytes,
    revision: int,
    *,
    preview=None,
    render=None,
    transition_held: bool = False,
) -> int:
    """Serve candidate source to the host's browser and run the render
    invariants on it.

    Playwright is the gate's own extra, not the payload's: declaring it in
    `pyproject.toml` would put its wheel in every `server run`, `leaf wait`, and
    `version stamp`, so the import happens here and its absence names the
    invocation that supplies it. A browser is part of this gate: if it cannot
    launch, the gate fails."""
    preview = preview_server if preview is None else preview
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
    with (
        preview(page_dir, source, revision, transition_held=transition_held) as url,
        sync_playwright() as p,
    ):
        try:
            browser = launch_browser(p)
        except PlaywrightError as error:
            print(
                "✗ render check failed — no browser launched: "
                f"{str(error).strip().splitlines()[0]}. {browser_hint()}",
                file=sys.stderr,
            )
            return 1
        try:
            failures = render(browser, url)
        finally:
            browser.close()
    if failures:
        print(
            f"✗ index.html: renders broken — {len(failures)} issue(s)",
            file=sys.stderr,
        )
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        f"✓ index.html: renders clean in {launched_name()}, light and dark — no "
        "console errors, every widget takes space, no words on top of other words, code that reads "
        "against the block it is on, boxes showing the inset they draw, nothing past the "
        "column, no sideways scroll"
    )
    return 0
