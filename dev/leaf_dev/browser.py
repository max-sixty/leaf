"""The browser, and tabs on a served page, opened and settled the same way by every
browser check or command that reads or screenshots one."""

import hashlib
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from leaf.render_checks import wait_for_probe, wait_until_ready
from leaf.render_gate.browser import ending, launch_browser
from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf_dev import ROOT

DESKTOP = (1440, 900)
# The width of a window beside an editor.
BESIDE = (900, 900)

# Pytest browser checks and captures use native DejaVu faces on Linux.
LINUX_FONTCONFIG = ROOT / "tests/fonts.conf"
LINUX_FONTS = Path("/usr/share/fonts/truetype/dejavu")


def linux_font_fingerprint():
    """Bind the fixed fontconfig and installed font bytes to reviewed Linux images.

    CI and local Linux capture install fonts-dejavu, including its italic faces.
    An absent face is a setup error; changed font bytes require an explicitly
    reviewed rendering profile.
    """
    for family, italic in (
        ("DejaVuSans", "Oblique"),
        ("DejaVuSerif", "Italic"),
        ("DejaVuSansMono", "Oblique"),
    ):
        for style in ("", "-Bold", f"-{italic}", f"-Bold{italic}"):
            if not (LINUX_FONTS / f"{family}{style}.ttf").is_file():
                raise RuntimeError(
                    "Install fonts-dejavu before running Linux browser tests "
                    "(core alone omits UI and serif italic faces)"
                )
    # Bind only the selected faces, so unrelated installed font packages do not
    # create another rendering profile for the same UI.
    faces = {
        Path(
            subprocess.check_output(
                [
                    "fc-match",
                    "-f",
                    "%{file}",
                    f"{family}:weight={weight}:slant={slant}",
                ],
                env=os.environ | {"FONTCONFIG_FILE": str(LINUX_FONTCONFIG)},
                text=True,
            )
        )
        for family in ("system-ui", "serif", "monospace")
        for weight in ("regular", "bold")
        for slant in ("roman", "italic")
    }
    digest = hashlib.sha256(LINUX_FONTCONFIG.read_bytes())
    for path in sorted(faces):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@contextmanager
def chrome():
    """The host's browser, as the render gate launches and ends it
    (`launch_browser`, `ending`), however the block is left."""
    with sync_playwright() as playwright:
        browser, _ = launch_browser(playwright)
        with ending(browser):
            yield browser


@contextmanager
def tab(browser: Browser, viewport=DESKTOP, scheme="light", touch=False):
    """A fresh blank tab at `viewport` and in `scheme`, with reduced motion so a still
    never catches a transition midway, and under a finger (a coarse pointer, a mobile
    viewport) when `touch`. A caller listens on it before it `load`s."""
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        color_scheme=scheme,
        reduced_motion="reduce",
        has_touch=touch,
        is_mobile=touch,
    )
    try:
        page = context.new_page()
        page.set_default_timeout(15_000)
        yield page
    finally:
        context.close()


def load(page: Page, address: str) -> None:
    """Open `address` and wait until the page has settled."""
    page.goto(address)
    settle(page)


def settle(page: Page) -> None:
    """Wait until the page is ready, its fonts have loaded, and the runtime reports it
    settled."""
    wait_until_ready(page)
    page.evaluate("() => document.fonts.ready")
    wait_for_probe(page, "pageSettled")


# How long a scroller holds one position before its travel is over, counted in the
# browser's own rendering frames.
SCROLL_STILL_FRAMES = 3

SCROLL_STILL = """([selector, axis, frames]) => {
  const box = selector ? document.querySelector(selector) : document.scrollingElement;
  if (!box) return false;
  const at = axis === "x" ? box.scrollLeft : box.scrollTop;
  const held = globalThis.__lfScrollStill;
  globalThis.__lfScrollStill =
    held && held.at === at ? { at, frames: held.frames + 1 } : { at, frames: 0 };
  return globalThis.__lfScrollStill.frames >= frames;
}"""


def scroll_settled(page, scroller=None, axis="y", frames=SCROLL_STILL_FRAMES):
    """Wait for stable scroll position after the caller observes scroll initiation.

    The helper cannot distinguish a finished scroll from one not yet issued.
    Callers first observe the gesture's synchronous arrival, focus, or attribute
    change that accompanies its scroll. The quiet interval is counted in animation
    frames to span the pause between instant nested-scrollport placement and the
    outer scroller's smooth movement, rather than a machine-dependent time window.

    Each call resets its observation. Timeout reports the selected scroller and
    its last reading. `tests/AGENTS.md`, "A wait consumes a fact the system states",
    owns the caller policy."""
    page.evaluate("() => { delete globalThis.__lfScrollStill; }")
    try:
        page.wait_for_function(SCROLL_STILL, arg=[scroller, axis, frames])
    except PlaywrightTimeout:
        where = scroller or "the document"
        held = page.evaluate(
            "() => globalThis.__lfScrollStill ?? null",
        )
        raise AssertionError(
            f"{where} never held one position for {frames} frames: gave up on {held}"
        ) from None
