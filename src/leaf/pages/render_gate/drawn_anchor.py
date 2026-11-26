"""What the drawn page says of a thread's target where the page's files can't say it.

`leaf thread create` reads its target from files: a quote from the file's reading of
the version (`anchor_capture`), which holds the words the page's markup and log give
it, and a visual's part from the page's render reading (`render_reading`), which holds
what each visual drew when a render check last read the page. Either can miss. A page's
script can draw words of its own, such as a custom element that fills itself in, and
the user can comment on them, since the browser captures a selection against the page
it draws. And no render check may have read the version the page shows, as right after
a save.

Where the files miss, the command serves the version, opens it in the host's browser
and reads the target there. For a quote, it captures the anchor as the user's selection
of those words would be captured (`render-checks/quote.js`), so the anchor is one the
drawn page resolves, as Leaf requires of every passage (root `AGENTS.md`, "Validate
once and share readings"). For a part, it reads what each visual draws, as the render
check does (`drawnVisuals` in `render-checks/widgets.js`), which
`anchor_capture.drawn_part` checks the part against. The browser runs before the
command takes the page's lease to write, as a message's check does
(`messages.message_check`), since it takes a second or more and the user's gestures wait
on that lease.

A host with no browser, a page that doesn't start, or words the drawn page doesn't
show once each leave the file's refusal of a quote standing, which says what to quote
instead. Where no browser reads the page, a part goes unchecked, and the command says
so."""

from pathlib import Path

from leaf.pages.page_snapshot import capture_page_snapshot
from leaf.pages.render_gate.command import (
    NoBrowser,
    desktop_viewport,
    run_in_browser,
    user_engine,
)
from leaf.pages.render_gate.preview import preview_server
from leaf.pages.render_gate.scheme import served
from leaf.source.anchor_capture import Drawing
from leaf.source.registry.contract import element_declarations
from leaf.source.render_checks import (
    PageNotReady,
    asked_again,
    evaluate_probe,
    open_render_page,
    rendered,
    start_near_work,
    wait_until_ready,
)
from leaf.source.revision_artifact import read_revision

# How a message names the drawing `drawn_visuals` makes (`anchor_capture.Drawing`).
DRAWN_NOW = "when Leaf drew the page just now"


def drawn_anchor(
    page_dir: Path, revision: int, quote: str, section: str
) -> dict | None:
    """The anchor of `quote`, in `section` where it names one, as the browser captures
    it on `revision` as drawn, or None where the drawn page doesn't show it once or
    no browser could read the page."""
    return _drawn(
        page_dir,
        revision,
        lambda page, _url: evaluate_probe(page, "drawnAnchor", quote, section or None),
    )


def drawn_visuals(page_dir: Path, revision: int) -> Drawing:
    """What each visual draws in `revision`, by the visual's id, as the render check
    reads it, or none where no browser could read the page."""
    return Drawing(_drawn(page_dir, revision, _visuals), DRAWN_NOW)


def _visuals(page, url: str) -> dict[str, dict]:
    registry = served(page, url, "/registry.json").json()
    return evaluate_probe(page, "drawnVisuals", element_declarations(registry))


def _drawn(page_dir: Path, revision: int, read):
    """What `read`, given the open page and its URL, finds on `revision` as drawn, or
    None where no browser could read the page. The page is drawn as the render check
    draws it, in the reader's window and engine where a browser has shown it to them
    (`command.desktop_viewport`, `command.user_engine`), with the work it holds back
    until the reader nears it started."""
    snapshot = capture_page_snapshot(
        page_dir, read_revision(page_dir, revision).document, revision, url="/"
    )
    viewport = desktop_viewport(page_dir).viewport
    with preview_server(page_dir, snapshot) as url:
        try:
            found, _ = run_in_browser(
                lambda browser: _read(browser, url, viewport, read),
                user_engine(page_dir),
            )
        except NoBrowser:
            return None
    return found


def _read(browser, url: str, viewport: dict, read):
    from playwright.sync_api import Error as PlaywrightError

    page = open_render_page(browser, viewport=viewport, reduced_motion="reduce")
    try:
        page.goto(asked_again(url))
        state = served(page, url, "/api/state").json()
        wait_until_ready(page, state, fixed_server=True)
        start_near_work(page, state, fixed_server=True)
        rendered(page)
        return read(page, url)
    except (PageNotReady, PlaywrightError):
        return None
    finally:
        page.close()
