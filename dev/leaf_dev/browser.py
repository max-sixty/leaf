"""The browser, and tabs on a served page, opened and settled the same way by every
browser check or command that reads or screenshots one."""

import os
import subprocess
import sys
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from playwright.sync_api import Browser, FrameLocator, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf.render_checks import wait_for_probe, wait_until_ready
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
    launched with Playwright's launch `options` and closed however the block is left.

    Not the host's browser that `launch_browser` finds for a user's `page check`:
    leaf-dev runs on a developer's machine or CI, where `leaf-dev setup` installs the
    shell, so it needs no discovery, and a run reads the same build on every host.
    """
    with (
        sync_playwright() as playwright,
        playwright.chromium.launch(**options) as browser,
    ):
        yield browser


@contextmanager
def headless_engine(name: str):
    """Playwright's Firefox or WebKit, for a probe of an engine-specific difference:
    readers use Leaf in both, and the suite and `headless_shell` drive Chromium. A host
    without the engine gets Playwright's own error, which names the install command."""
    with sync_playwright() as playwright, getattr(playwright, name).launch() as browser:
        yield browser


@cache
def shell_executable() -> str:
    """Ask the installed Playwright registry for its pinned headless shell.

    A subprocess works even while the caller already holds sync_playwright open.
    """
    from playwright._impl._driver import compute_driver_executable

    node, cli = compute_driver_executable()
    return subprocess.run(
        [
            node,
            "-e",
            (
                "console.log(require(process.argv[1]).registry.registry"
                ".findExecutable('chromium-headless-shell').executablePathOrDie('python'))"
            ),
            str(Path(cli).parent / "lib/coreBundle.js"),
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


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


def slow_cpu(page: Page, rate: float) -> None:
    """Run Chromium's CPU for `page` `rate` times slower, through CDP, as on a slower
    machine than this one. Set before the page navigates, the throttle holds through
    every later navigation of the page."""
    page.context.new_cdp_session(page).send(
        "Emulation.setCPUThrottlingRate", {"rate": rate}
    )


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


# The floating panel's row ends in one seat: at rest the On me mark, which counts what
# waits on the user and dots a thread with news; while a view, stance or search stands,
# its way out (`.lf-fp-exit`, with `.lf-fp-close` for a view's Close) in the same place.
ON_ME_MARK = ".lf-fp-on-user"


def panel_tab(page: Page | FrameLocator, name: str):
    """The On view's tab `name` at the foot of On and of Threads, Threads being one of
    its tabs: `On me`, `On <agent>`, `Threads` and, while a plan exists, `Plan`. Each
    but Plan says its count after its name, in `.lf-fp-count`."""
    return page.locator(".lf-fp-controls .lf-fp-filters button", has_text=name)


def threads_tab(page: Page | FrameLocator):
    """Stand On or Threads open and return the Threads tab at its foot. From the row the
    On me mark opens On, or Threads itself while nothing waits on the user but a reply
    they have not read; another view, stance or search is closed first by its exit.
    `page` may be a live sample's frame."""
    host = page.locator(".lf-floating-panel")
    if host.get_attribute("data-open") not in ("queue", "threads"):
        exit_control = page.locator(".lf-fp-exit")
        if exit_control.count():
            exit_control.click()
        page.locator(ON_ME_MARK).click()
    return panel_tab(page, "Threads")


def open_threads(page: Page | FrameLocator) -> None:
    """Open the floating panel's Threads view by pointer, as a user reaches it: from a
    thread opened over Threads by its way back, else by the Threads tab (`threads_tab`)
    unless the mark opened Threads itself. The view lists the open threads, then the
    resolved ones under a Resolved heading (`.lf-fp-ended`)."""
    host = page.locator(".lf-floating-panel")
    if host.get_attribute("data-open") == "threads":
        return
    back = page.locator(".lf-fp-controls .lf-fp-back", has_text="Threads")
    if back.count():
        back.click()
    else:
        tab = threads_tab(page)
        if host.get_attribute("data-open") != "threads":
            tab.click()
    page.locator('.lf-fp-view[data-view="threads"]:not([data-leaving])').wait_for()


def go_to_threads(page: Page, frame: FrameLocator | None = None) -> None:
    """Open the floating panel's Threads view by Go to Threads (`g` then `T`), in
    `frame`'s page where given, a live sample's. The pointer's route to Threads has
    changed between runtimes, so a driver one checkout runs against another's runtime,
    as `stills`, `bench-latency`, thread snapshots and `verify-site` do, takes this
    route, which both share."""
    within = frame or page
    # A press at the frame's top corner gives its document the keys; the page's own
    # only needs focus off any control.
    if frame:
        frame.locator("body").click(position={"x": 2, "y": 2})
    else:
        page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    within.locator('.lf-fp-view[data-view="threads"]:not([data-leaving])').wait_for()
