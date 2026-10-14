"""The browser, and tabs on a served page, opened and settled the same way by every
browser check or command that reads or screenshots one."""

import os
import subprocess
import sys
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from leaf.render_checks import wait_for_probe, wait_until_ready
from leaf.render_gate.browser import ending
from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf_dev import ROOT

DESKTOP = (1440, 900)
# The width of a window beside an editor.
BESIDE = (900, 900)

# The fixed fontconfig that lays text out in DejaVu faces on Linux (`use_linux_fonts`).
LINUX_FONTCONFIG = ROOT / "tests/fonts.conf"
LINUX_FONTS = Path("/usr/share/fonts/truetype/dejavu")


def require_linux_fonts():
    """Refuse a Linux browser run without the faces the fixed fontconfig names.

    CI and local Linux runs install fonts-dejavu, including its italic faces, so
    every Linux run lays text out in the same faces. An absent face is a setup error.
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


def use_linux_fonts():
    """On Linux, lay text out in the DejaVu faces the fixed fontconfig names, in every
    browser and leaf this process starts from here on; elsewhere the host's faces
    serve. The suite does this for its whole run, and so does a command whose readings
    the suite asserts (`leaf-dev pins`), so the two measure the same text."""
    if sys.platform == "linux":
        require_linux_fonts()
        os.environ["FONTCONFIG_FILE"] = str(LINUX_FONTCONFIG)


@contextmanager
def headless_shell(**options):
    """Playwright's pinned Chromium headless shell, the build the suite drives,
    launched with Playwright's launch `options` and ended as the render gate ends its
    browser (`ending`), however the block is left.

    Not the host's browser that `launch_browser` finds for a user's `page check`:
    leaf-dev runs on a developer's machine or CI, where `leaf-dev setup` installs the
    shell, so it needs no discovery, and a run reads the same build on every host.
    Installed Chrome also costs more per launch (`shell_executable` says how much).
    """
    with (
        sync_playwright() as playwright,
        ending(playwright.chromium.launch(**options)) as browser,
    ):
        yield browser


@cache
def shell_executable() -> str:
    """The pinned headless shell's executable, which leaf-dev and the suite name as
    the host's browser (LEAF_BROWSER_EXECUTABLE) for every `leaf` they run, so each
    `page check` that runs a page's code or takes `--render` draws with the build
    `headless_shell` drives. Left unnamed, each would launch installed Google Chrome
    afresh: about three seconds apiece against the shell's 0.3 (measured over the
    suite in #1488), and on macOS each new profile leaves a key in Chrome's keychain
    group that every later Chrome launch makes `secd` read back, so that cost grows
    with every launch.

    Playwright reports where its full Chromium build would be whether or not that
    build is installed, and `leaf-dev setup` installs the shell alone. Both sit under
    one registry root at one build number, so the shell's path follows from
    Chromium's; where a developer installed the full build instead, that is the
    browser to hand over. The `chromium-<build>` directory is found by name rather
    than by depth, because macOS nests the executable inside an app bundle and Linux
    does not.

    Asked in a subprocess because the answer is a path and the question is not free:
    a second `sync_playwright()` raises in a process that already holds one open."""
    read = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from playwright.sync_api import sync_playwright\n"
                "with sync_playwright() as p: print(p.chromium.executable_path)"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    chromium = Path(read.stdout.strip())
    versioned = next(
        (p for p in chromium.parents if p.name.startswith("chromium-")), None
    )
    if versioned is None:
        raise RuntimeError(f"{chromium} is not under a Playwright chromium build")
    root, build = versioned.parent, versioned.name.rsplit("-", 1)[1]
    shell = root / f"chromium_headless_shell-{build}"
    shell_executables = sorted(shell.glob("*/chrome-headless-shell*")) + sorted(
        shell.glob("*/headless_shell")
    )
    executable = next(
        (str(c) for c in (*shell_executables, chromium) if c.is_file()), None
    )
    if executable is None:
        raise RuntimeError(
            f"no Playwright Chromium under {root}; run `uv run playwright install "
            "chromium --only-shell`"
        )
    return executable


@contextmanager
def tab(
    browser: Browser,
    viewport=DESKTOP,
    scheme="light",
    touch=False,
    *,
    motion="reduce",
    scale=1,
):
    """A fresh blank tab at `viewport` and in `scheme`, with reduced motion so a still
    never catches a transition midway (pass motion="no-preference" for a journey),
    and under a finger (a coarse pointer, a mobile
    viewport) when `touch`, drawing `scale` device pixels to a CSS pixel. A caller
    listens on it before it `load`s."""
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        device_scale_factor=scale,
        color_scheme=scheme,
        reduced_motion=motion,
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
    its last reading. `tests/AGENTS.md`, "Waits",
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
