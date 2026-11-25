"""The anchor of an agent's quote of words the page draws but its file doesn't hold.

`leaf thread create --quote` captures its anchor against the file's reading of the
version (`anchor_capture`), which holds the words the page's markup and log give it. A
page's script can draw words of its own, such as a custom element that fills itself in,
and the user can comment on them, since the browser captures a selection against the
page it draws. Where the file's reading lacks the quote, the command serves the
version, opens it in the host's browser and captures the anchor there as the user's
selection of those words would be (`render-checks/quote.js`), so the anchor is one the
drawn page resolves, as Leaf requires of every passage (root `AGENTS.md`, "Validate
once and share readings"). The browser runs before the command takes the page's lease
to write, as a message's check does (`command.message_check`), since it takes a second
or more and the user's gestures wait on that lease.

A host with no browser, a page that doesn't start, or words the drawn page doesn't
show once each leave the file's refusal standing, which says what to quote instead."""

from pathlib import Path

from leaf.render_checks import (
    PageNotReady,
    asked_again,
    evaluate_probe,
    open_render_page,
    rendered,
    start_near_work,
    wait_until_ready,
)

from ..page_snapshot import capture_page_snapshot
from ..revision_artifact import read_revision
from .command import NoBrowser, desktop_viewport, run_in_browser, user_engine
from .preview import preview_server
from .scheme import served


def drawn_anchor(
    page_dir: Path, revision: int, quote: str, section: str
) -> dict | None:
    """The anchor of `quote`, in `section` where it names one, as the browser captures
    it on `revision` as drawn, or None where the drawn page doesn't show it once or
    no browser could read the page. The page is drawn as the render check draws it,
    in the reader's window and engine where a browser has shown it to them
    (`command.desktop_viewport`, `command.user_engine`), with the work it holds back
    until the reader nears it started."""
    snapshot = capture_page_snapshot(
        page_dir, read_revision(page_dir, revision).document, revision, url="/"
    )
    viewport = desktop_viewport(page_dir).viewport
    with preview_server(page_dir, snapshot) as url:
        try:
            anchor, _ = run_in_browser(
                lambda browser: _captured(browser, url, viewport, quote, section),
                user_engine(page_dir),
            )
        except NoBrowser:
            return None
    return anchor


def _captured(
    browser, url: str, viewport: dict, quote: str, section: str
) -> dict | None:
    from playwright.sync_api import Error as PlaywrightError

    page = open_render_page(browser, viewport=viewport, reduced_motion="reduce")
    try:
        page.goto(asked_again(url))
        state = served(page, url, "/api/state").json()
        wait_until_ready(page, state, fixed_server=True)
        start_near_work(page, state, fixed_server=True)
        rendered(page)
        return evaluate_probe(page, "drawnAnchor", quote, section or None)
    except (PageNotReady, PlaywrightError):
        return None
    finally:
        page.close()
