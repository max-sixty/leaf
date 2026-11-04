"""The browser, and tabs on a served page, opened and settled the same way by every
browser check or command that reads or screenshots one."""

import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache, wraps
from pathlib import Path

import click
from playwright.sync_api import Browser, FrameLocator, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf.render_checks import rendered, wait_for_probe, wait_until_ready
from leaf_dev import ROOT

DESKTOP = (1440, 900)
PHONE = (390, 844)


@dataclass(frozen=True)
class Window:
    """A window a tab opens at: its size in CSS pixels, whether a finger drives it
    (`tab`'s `touch`), and the words a prompt uses for it."""

    size: tuple[int, int]
    description: str
    touch: bool = False


# The windows a tool opens a page in by name, as `eval --viewport large` or
# `stills --viewport phone` does. An eval author's request and a judge's instructions
# give a window's description, so rewording one changes what those agents are asked.
WINDOWS = {
    "desktop": Window((1280, 800), "a 1280px by 800px desktop content viewport"),
    "large": Window((1600, 1000), "a large 1600px by 1000px desktop content viewport"),
    "short": Window((900, 600), "a short 900px by 600px desktop window"),
    "middle": Window((900, 700), "a 900px by 700px laptop window beside other work"),
    "phone": Window(PHONE, "a 390px by 844px phone window", touch=True),
}

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


ENGINES = ("chromium", "firefox", "webkit", "ios")


def engine_option(command):
    """Give a command the engine it opens pages in (`launch`), as `--browser`."""
    return click.option(
        "--browser",
        "engine",
        type=click.Choice(ENGINES),
        default="chromium",
        help="The engine to run in: Playwright's Chromium shell, Firefox or WebKit, or "
        "Safari on an iPhone simulator through WebDriver.",
    )(command)


@contextmanager
def launch(engine: str, scheme: str = "light"):
    """The browser `engine` names, closed however the block is left: Playwright's
    Chromium shell (`headless_shell`) showing the scrollbars readers see, including
    the room a classic bar takes; Playwright's Firefox or WebKit, which readers use
    as well; or a WebDriver session on the iOS simulator's Safari in `scheme`
    (`ios_safari`), for a difference only iPhones show. A host without a Playwright
    engine gets Playwright's own error, which names the install command."""
    if engine == "ios":
        from leaf_dev.ios_safari import ios_safari

        with ios_safari(scheme) as driver:
            yield driver
    elif engine == "chromium":
        with headless_shell(ignore_default_args=["--hide-scrollbars"]) as browser:
            yield browser
    else:
        with (
            sync_playwright() as playwright,
            getattr(playwright, engine).launch() as browser,
        ):
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


def window(value: str) -> Window | tuple[int, int]:
    """The window `--viewport` names, or the size it spells as WIDTHxHEIGHT."""
    if value in WINDOWS:
        return WINDOWS[value]
    width, _, height = value.partition("x")
    if not (width.isdigit() and height.isdigit()):
        raise click.BadParameter(
            f"{value!r} is neither WIDTHxHEIGHT nor a window: {', '.join(WINDOWS)}"
        )
    return int(width), int(height)


def tab_options(command):
    """Give a command `tab`'s viewport, scheme and pointer as `--viewport`, `--scheme`
    and `--touch`. A window `--viewport` names brings its pointer unless `--touch` or
    `--no-touch` is given. `viewport` and `touch` reach the command as a size and a
    flag, each None unless given, so it can tell a default from a choice."""

    @wraps(command)
    def sized(*args, viewport, touch, **kwargs):
        if isinstance(viewport, Window):
            viewport, touch = viewport.size, viewport.touch if touch is None else touch
        return command(*args, viewport=viewport, touch=touch, **kwargs)

    sized = click.option(
        "--touch/--no-touch",
        default=None,
        help="Show the page under a finger: a coarse pointer and mobile emulation, at "
        "--viewport's size. By default as the window --viewport names sets it, "
        "and otherwise off.",
    )(sized)
    sized = click.option(
        "--scheme",
        type=click.Choice(["light", "dark"]),
        default="light",
        help="The colour scheme the page is shown in.",
    )(sized)
    named = ", ".join(
        f"{name} ({each.size[0]}x{each.size[1]}{', touch' if each.touch else ''})"
        for name, each in WINDOWS.items()
    )
    return click.option(
        "--viewport",
        metavar="WIDTHxHEIGHT|NAME",
        callback=lambda c, p, value: value and window(value),
        help=f"By default {DESKTOP[0]}x{DESKTOP[1]}. A NAME is one of the windows "
        f"{named}.",
    )(sized)


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
# waits on the user and dots a thread with news; while a stance or search stands, its
# way out (`.lf-fp-exit`) in the same place. A view's Close (`.lf-fp-exit.lf-fp-close`)
# ends a list's tabs or another view's head line instead.
ON_ME_MARK = ".lf-fp-on-user"


def panel_tab(page: Page | FrameLocator, name: str):
    """The On view's tab `name` at the foot of the menu, On and Threads, each one of
    its tabs: `Menu`, `On me`, `On <agent>`, `Threads` and, while a plan exists,
    `Plan`. Each but Menu and Plan says its count after its name, in `.lf-fp-count`."""
    return page.locator(".lf-fp-controls .lf-fp-filters button", has_text=name)


def threads_tab(page: Page | FrameLocator):
    """Stand On or Threads open and return the Threads tab at its foot. From the row the
    On me mark opens On, or Threads itself while nothing waits on the user but a reply
    they have not read; another view, stance or search is closed first by its exit.
    Leave an empty comment field by pressing the page first where writing hides the
    mark. `page` may be a live sample's frame."""
    # A stance's exit becomes the mark in the repaint frame. Read the controls only
    # after the previous input has rendered, before choosing a pointer route.
    rendered(
        page.locator("html").element_handle().owner_frame(), facts=("updatesSettled",)
    )
    host = page.locator(".lf-floating-panel")
    if host.get_attribute("data-open") not in ("queue", "threads"):
        exit_control = page.locator(".lf-fp-exit")
        if exit_control.count():
            exit_control.click()
        mark = page.locator(ON_ME_MARK)
        if not mark.is_visible():
            # Writing hides the quick seat. Leave the field by pressing the page,
            # as a pointer user does before reaching On me.
            page.locator("html").click(position={"x": 0, "y": 0})
        mark.click()
    return panel_tab(page, "Threads")


def open_threads(page: Page | FrameLocator) -> None:
    """Open the floating panel's Threads view by pointer, as a user reaches it: from a
    thread opened over Threads by its way back, else by the Threads tab (`threads_tab`)
    unless the mark opened Threads itself. The view lists the open threads, then the
    resolved ones folded under a Resolved heading (`show_resolved`)."""
    host = page.locator(".lf-floating-panel")
    if host.get_attribute("data-open") == "threads":
        return
    back = page.get_by_role("button", name="Back to Threads")
    if back.count():
        back.click()
    else:
        tab = threads_tab(page)
        if host.get_attribute("data-open") != "threads":
            tab.click()
    page.locator('.lf-fp-view[data-view="threads"]:not([data-leaving])').wait_for()


def show_resolved(page: Page | FrameLocator):
    """Unfold the resolved threads in the open Threads, which stand folded under their
    Resolved heading (`.lf-fp-settled`) until the user presses it, and return their
    rows."""
    threads = page.locator('.lf-fp-view[data-view="threads"]:not([data-leaving])')
    heading = threads.locator(".lf-fp-settled")
    if heading.get_attribute("aria-expanded") != "true":
        heading.click()
    return threads.locator(".lf-fp-thread[data-resolved]")


def go_to_threads(page: Page, frame: FrameLocator | None = None) -> None:
    """Open the floating panel's Threads view by Go to Threads (`g` then `T`), in
    `frame`'s page where given, a live sample's. The pointer's route to Threads has
    changed between runtimes, so a driver one checkout runs against another's runtime,
    as `stills`, `bench-latency`, thread snapshots and `verify-site` do, takes this
    route, which both share."""
    within = frame or page
    # Completing `g T` again closes the view (keyboard/go-to-sequence.js).
    if within.locator(".lf-floating-panel").get_attribute("data-open") == "threads":
        return
    # A press at the frame's top corner gives its document the keys; the page's own
    # only needs focus off any control.
    if frame:
        frame.locator("body").click(position={"x": 2, "y": 2})
    else:
        page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    within.locator('.lf-fp-view[data-view="threads"]:not([data-leaving])').wait_for()
