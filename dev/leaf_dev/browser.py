"""The browser, and tabs on a served page, opened and settled the same way by every
browser check or command that reads or screenshots one.

A check on a page of millions of elements finds its controls as
notes/browser-support.md, "Walking every element of a page of millions in Chromium",
says."""

import json
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

import click
from playwright.sync_api import (
    Browser,
    FrameLocator,
    Locator,
    Page,
    expect,
    sync_playwright,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf.source.render_checks import (
    one_frame,
    open_render_context,
    open_render_page,
    rendered,
    wait_for_probe,
    wait_until_ready,
)
from leaf_dev import ROOT


@dataclass(frozen=True)
class Window:
    """A window a tab opens in (`tab`): its size in CSS pixels, whether a finger
    drives it, with a coarse pointer and mobile emulation, and the words a prompt
    uses for it, which only a window a tool names (`WINDOWS`) has."""

    size: tuple[int, int]
    touch: bool = False
    description: str = ""


# The windows a tool opens a page in by name, as `eval run --viewport large` or
# `stills --viewport phone` does. `tab`, and stills and probe for a state that names
# no window of its own (`states.State`), open `macbook` unless told another. An eval
# author's request and a judge's instructions give a window's description, which
# states its size, so a change to either changes what those agents are asked.
WINDOWS = {
    "macbook": Window(
        (1440, 900), description="a 1440px by 900px MacBook content viewport"
    ),
    "desktop": Window(
        (1280, 800), description="a 1280px by 800px desktop content viewport"
    ),
    "large": Window(
        (1600, 1000), description="a large 1600px by 1000px desktop content viewport"
    ),
    "short": Window((900, 600), description="a short 900px by 600px desktop window"),
    "middle": Window(
        (900, 700), description="a 900px by 700px laptop window beside other work"
    ),
    "phone": Window(
        (390, 844), touch=True, description="a 390px by 844px phone window"
    ),
}

# The fixed fontconfig that lays text out in DejaVu faces on Linux
# (`linux_font_environment`).
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


def linux_font_environment() -> dict[str, str]:
    """The environment that lays text out in the DejaVu faces the fixed fontconfig
    names, in every browser and leaf a process holding it starts; empty off Linux,
    where the host's faces serve. The suite runs under it, and so does a command whose
    readings the suite asserts (`leaf-dev placement pins`), so the two measure the same
    text."""
    if sys.platform != "linux":
        return {}
    require_linux_fonts()
    return {"FONTCONFIG_FILE": str(LINUX_FONTCONFIG)}


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

# Firefox's own smooth scroll reads the host's reduced-motion setting, which a
# context's `reduced_motion` emulates only for the page's media queries. On a host
# that asks for reduced motion, every smooth scroll lands in one step while the page
# reads no preference, and a test that needs a scroll under way never has one. So
# Firefox answers no preference, as the page's context does.
#
# Bounce-tracking protection classifies a host the tab passed through without user
# activation, after the host stored state, as a tracker, and logs a console warning on
# the page then showing. Tests serve every page from 127.0.0.1 and navigate by script,
# so any test can trip it, and the browser fixtures fail a test on that warning as on
# one the page raised. Mode 0 (`nsIBounceTrackingProtection.MODE_DISABLED`) leaves the
# feature off.
FIREFOX_PREFS = {
    "ui.prefersReducedMotion": 0,
    "privacy.bounceTrackingProtection.mode": 0,
}


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
    Chromium shell (`headless_shell`'s build) showing the scrollbars readers see,
    including the room a classic bar takes; Playwright's Firefox or WebKit, which
    readers use as well; or a WebDriver session on the iOS simulator's Safari in
    `scheme` (`ios_safari`), for a difference only iPhones show. A host without a
    Playwright engine gets Playwright's own error, which names the install command.

    The Chromium shell keeps an overlay scrollbar shown after a scroll, as `screenshot`
    requires, by disabling Chromium's `ScrollbarAnimations` feature, which Chromium
    keeps so that web platform tests' screenshots can't flake on their timing."""
    if engine == "ios":
        from leaf_dev.ios_safari import ios_safari

        with ios_safari(scheme) as driver:
            yield driver
    elif engine == "chromium":
        with sync_playwright() as playwright:
            # Chromium keeps only the last of a repeated switch, so ours extends the
            # --disable-features Playwright passes, read from a shell it launched
            # (CDP reads the command line only under --enable-automation).
            with playwright.chromium.launch(args=["--enable-automation"]) as plain:
                features = next(
                    switch
                    for switch in plain.new_browser_cdp_session().send(
                        "Browser.getBrowserCommandLine"
                    )["arguments"]
                    if switch.startswith("--disable-features=")
                )
            with playwright.chromium.launch(
                ignore_default_args=["--hide-scrollbars", features],
                args=[f"{features},ScrollbarAnimations"],
            ) as browser:
                yield browser
    else:
        with (
            sync_playwright() as playwright,
            getattr(playwright, engine).launch(
                **({"firefox_user_prefs": FIREFOX_PREFS} if engine == "firefox" else {})
            ) as browser,
        ):
            yield browser


def shell_executable() -> str:
    """The installed Playwright registry's pinned headless shell."""
    return playwright_executable("chromium-headless-shell")


@cache
def playwright_executable(name: str) -> str:
    """Ask the installed Playwright registry for its pinned build of browser `name`.

    `leaf-dev setup` installs only Python Playwright's builds, and Node's Playwright
    pins its own, which can be a different build. A Node tool that must see what
    Python sees launches this path (`evals/ui-review-detection/provider.mjs`).
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
                ".findExecutable(process.argv[2]).executablePathOrDie('python'))"
            ),
            str(Path(cli).parent / "lib/coreBundle.js"),
            name,
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


@contextmanager
def tab(
    browser: Browser,
    window: Window = WINDOWS["macbook"],
    scheme="light",
    *,
    motion="reduce",
    scale=1,
):
    """A fresh blank tab in `window` and `scheme`, with reduced motion so a still
    never catches a transition midway (pass motion="no-preference" for a journey),
    drawing `scale` device pixels to a CSS pixel. It keeps where a mouse last moved over
    it (`POINTER`), for `settle`. A caller listens on it before it `load`s."""
    width, height = window.size
    context = open_render_context(
        browser,
        viewport={"width": width, "height": height},
        device_scale_factor=scale,
        color_scheme=scheme,
        reduced_motion=motion,
        has_touch=window.touch,
        is_mobile=window.touch,
    )
    context.add_init_script(POINTER)
    try:
        yield open_render_page(context)
    finally:
        context.close()


def parse_window(value: str) -> Window:
    """The window `--viewport` names, or one under a mouse at the size it spells as
    WIDTHxHEIGHT."""
    if value in WINDOWS:
        return WINDOWS[value]
    width, _, height = value.partition("x")
    if not (width.isdigit() and height.isdigit()):
        raise click.BadParameter(
            f"{value!r} is neither WIDTHxHEIGHT nor a window: {', '.join(WINDOWS)}"
        )
    return Window((int(width), int(height)))


def tab_options(command):
    """Give a command `tab`'s window and scheme as `--viewport`, `--touch` and
    `--scheme`. The command receives `viewport`, the window `--viewport` gives, and
    `touch`, the pointer `--touch` or `--no-touch` gives, each None unless given, and
    opens each tab in the window `chosen_window` makes of them."""
    command = click.option(
        "--touch/--no-touch",
        default=None,
        help="Show the page under a finger (a coarse pointer and mobile emulation), "
        "or under a mouse with --no-touch, in place of the window's own pointer.",
    )(command)
    command = click.option(
        "--scheme",
        type=click.Choice(["light", "dark"]),
        default="light",
        help="The colour scheme the page is shown in.",
    )(command)
    named = ", ".join(
        f"{name} ({each.size[0]}x{each.size[1]}{', touch' if each.touch else ''})"
        for name, each in WINDOWS.items()
    )
    return click.option(
        "--viewport",
        metavar="WIDTHxHEIGHT|NAME",
        callback=lambda c, p, value: value and parse_window(value),
        help="By default the state's own window, macbook unless it names another. "
        f"A NAME is one of the windows {named}; a WIDTHxHEIGHT window has a mouse.",
    )(command)


def chosen_window(own: Window, viewport: Window | None, touch: bool | None) -> Window:
    """The window a tab opens in when its command (`tab_options`) would open `own`:
    the window `--viewport` gave, if any, in its place, and under a finger or a mouse
    where `--touch` or `--no-touch` says so."""
    window = viewport or own
    return window if touch is None else replace(window, touch=touch)


# The style `screenshot` adds to the page and its open shadow roots for the shot.
HELD = """:root { caret-animation: manual; }
@supports not (caret-animation: manual) {
  * { caret-color: transparent !important; }
}"""


def screenshot(page) -> bytes:
    """The PNG of `page`'s viewport, a tab brought to a state.

    A capture holds each animation the browser draws of its own accord in one state,
    so two captures of one state draw it alike whenever each is taken, however loaded
    the host:

    - A caret is drawn steadily where the engine can stop its blink, as Chromium can
      (`caret-animation: manual`), and hidden where it can't: Playwright's WebKit
      (build 2370) fades it in and out, and its Firefox (build 1555) draws none.
      Both declarations are inherited, so they reach the caret inside Leaf's text
      field, whose closed shadow root takes the caret's colour from its host
      (`runtime/annotations/composing/text-field.js`).
    - An overlay scrollbar, such as a Mac's, starts to fade half a second after its
      box scrolls. The Chromium shell `launch` opens keeps it shown until the pointer
      passes over it and leaves, as a reader sees it while scrolling; Playwright's
      Firefox and WebKit draw no overlay bar, `headless_shell` draws no bar at all, and
      a classic bar never fades.

    The page's own motion is the page's, and follows the tab's `motion`. A `tab`
    reduces it unless told otherwise, so Leaf's runtime and theme play none; probe
    shows what a user sees unless told to reduce it, so a probe shot can catch that
    motion at any point. `visits` also waits for a Leaf page whose runtime runs to
    settle, so no smooth scroll or finite transition is under way.

    Safari on the iOS simulator takes no input, so it draws no caret or scrollbar to
    hold."""
    if isinstance(page, Page):
        return page.screenshot(caret="initial", style=HELD)
    return page.screenshot()


@contextmanager
def chromium_metrics(page: Page, *, ticks: bool = False):
    """Read Chromium's counts of `page`'s renderer work for the life of the block:
    yield what returns them by name when called, from CDP's `Performance.getMetrics`,
    such as `LayoutCount`, `RecalcStyleCount`, `Nodes` and `TaskDuration`, the
    main thread's time in its tasks in seconds. With `ticks` its times are thread
    ticks, the CPU the thread spent, rather than wall time."""
    session = page.context.new_cdp_session(page)
    session.send("Performance.enable", {"timeDomain": "threadTicks"} if ticks else {})
    try:
        yield lambda: {
            metric["name"]: metric["value"]
            for metric in session.send("Performance.getMetrics")["metrics"]
        }
    finally:
        session.detach()


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
    """Wait until the page is ready, its fonts have loaded, the runtime reports it
    settled, and its hover is on the element under the pointer (`catch_up_hover`).

    Readiness is read once the page has heard what could start more work: the input
    before this, and then the motion `pageSettled` waits out. A scroll that brings a
    live sample near starts it in the next rendering update, as the sample's observer
    reports, so each read waits for that update first (runtime/base/rendering.js)."""
    one_frame(page)
    wait_until_ready(page)
    page.evaluate("() => document.fonts.ready")
    wait_for_probe(page, "pageSettled")
    one_frame(page)
    wait_until_ready(page)
    if catch_up_hover(page):
        settle(page)


# The range of the first run of `words` in the text under `root`, across text nodes
# as a passage may run, or null where the text holds none: a JavaScript function's
# source, which a page script embeds as `({QUOTE_RANGE})(root, words)`.
QUOTE_RANGE = """(root, words) => {
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let text = "";
  for (let node = walk.nextNode(); node; node = walk.nextNode()) {
    nodes.push([node, text.length]);
    text += node.data;
  }
  const start = text.indexOf(words);
  if (start < 0) return null;
  const at = (offset) => {
    const [node, base] = nodes.findLast(([, base]) => base <= offset);
    return [node, offset - base];
  };
  const range = document.createRange();
  range.setStart(...at(start));
  range.setEnd(...at(start + words.length));
  return range;
}"""

# Where a mouse was last over a `tab`'s document, in its viewport, and which of its
# buttons it held. A native drag sends no `pointerup`; it ends in `dragend` where it
# drops, with no button held. Its `pointercancel` can read (0, 0) in Chromium and the
# button still held in Firefox, and WebKit can send none.
POINTER = """for (const type of ["pointermove", "pointerdown", "pointerup", "dragend"])
  addEventListener(type, (event) => {
    if ((event.pointerType ?? "mouse") === "mouse")
      globalThis.__lfPointer = {
        x: event.clientX, y: event.clientY, buttons: event.buttons,
      };
  }, {capture: true, passive: true});"""

# Whether the document's hover ends at the element under a resting mouse, or no mouse
# rests here. Both are read in the document's own tree, where a shadow host stands for
# everything its shadow root draws. Read inside a shadow root they can disagree:
# Firefox can hover a radio button's host but not the slot under the pointer.
# A held button keeps the hover where the press began, and a mouse over a child frame
# moves where this document can't follow it. A subtree hidden under the pointer keeps
# its hover after the hover moves on, so only drawn elements count: Chromium can
# leave `.lf-fp-opened` hovered once the panel's view closes under a press, through
# every later move.
HOVER_CAUGHT_UP = """() => {
  const at = globalThis.__lfPointer;
  if (!at || at.buttons) return true;
  const hovered = [...document.querySelectorAll(":hover")]
    .filter((node) => node.checkVisibility())
    .at(-1);
  if (hovered instanceof HTMLIFrameElement) return true;
  const under = document.elementFromPoint(at.x, at.y);
  // A hovered label also hovers the control it labels, which is no hover still to move.
  return !under || under === hovered || under.control === hovered;
}"""


def catch_up_hover(page: Page) -> bool:
    """Wait until the hover is on the element under a resting pointer, and say whether
    it had to move there.

    Content that scrolls under a resting pointer keeps the old element hovered until
    the engine hit-tests again on a timer of its own, dispatching `pointerover` as the
    hover moves. In Playwright's Firefox (build 1555) and WebKit (build 2370) that
    can take around 100 ms, and in its Chromium about a frame, though on a loaded host
    sometimes longer than the rest of `settle`, so a capture taken first can draw the
    button a state's driver pressed still hovered. The page may answer
    `pointerover`, so `settle` settles again after a hover moved.

    Moving the pointer to where it already is would move the hover at once, but every
    engine dispatches `pointermove` for the move, which a page answers as it would a
    hand: the merge film closes the details its Inspect button opened. WebKit also
    dispatches `pointermove` itself, about 100 ms after the scroll, which this wait
    doesn't cover; a state whose driver presses and then scrolls can see a WebKit
    capture change with it."""
    if page.evaluate(HOVER_CAUGHT_UP):
        return False
    try:
        page.wait_for_function(HOVER_CAUGHT_UP)
    except PlaywrightTimeout:
        at = page.evaluate("() => globalThis.__lfPointer")
        raise AssertionError(
            f"the hover never reached the element under the pointer at {at}"
        ) from None
    return True


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


def scroll_settled(page, scroller=None, axis="y"):
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
        page.wait_for_function(SCROLL_STILL, arg=[scroller, axis, SCROLL_STILL_FRAMES])
    except PlaywrightTimeout:
        where = scroller or "the document"
        held = page.evaluate(
            "() => globalThis.__lfScrollStill ?? null",
        )
        raise AssertionError(
            f"{where} never held one position for {SCROLL_STILL_FRAMES} frames: gave up on {held}"
        ) from None


# The floating panel's row ends in the leaf, which counts what waits on the user
# on a badge over its corner (`.lf-fp-badge`) and dots a thread with news, and opens the On view on the tab those
# marks point at (panel/floating-panel.js, `leafOpens`). While a stance or search stands, its
# way out (`.lf-fp-row > .lf-fp-exit`) stands before it. A view's Close
# (`.lf-fp-exit.lf-fp-close`) ends a list's tabs or another view's head line instead.
LEAF = ".lf-fp-leaf"

# The floating panel (runtime/panel/floating-panel.js) is Leaf's one chrome: a row of the
# field and the leaf, with a view opened above it, the leaf's menu among them. Its state
# stands on its host as attributes: `data-lf-open` names the open view (menu, versions,
# group, errors, threads, thread, queue, leaves) and `data-lf-rest="mark"` the panel
# folded to the leaf.
PANEL = ".lf-floating-panel"

# The words in the panel's one seat for what passes, such as a notice or a walk's
# position (panel/floating-panel.js, `passing`): the leaf's peek while it shows one over an
# open view, else an error standing over the field's words (annotations/composing/input.js), else
# the empty field's placeholder.
PANEL_SAYS = """() => {
  const peek = document.querySelector('.lf-fp-peek');
  if (peek?.hasAttribute('data-lf-shown')) return peek.textContent.trim();
  const cover = document.querySelector('.lf-fp-field .lf-compose-error:not([hidden])');
  if (cover) return cover.textContent.trim();
  return document.querySelector('.lf-fp-field leaf-text')?.getAttribute('placeholder')
    ?? '';
}"""


def panel_view(name: str) -> str:
    """The selector of the panel's `name` view (`data-lf-open`'s values, above) that
    stands open. A view put away keeps its node, marked `data-lf-leaving`, until its
    exit motion ends, so this never matches one: a selector that did would find two
    views mid-switch, or a view already on its way out."""
    return f'.lf-fp-view[data-lf-route="{name}"]:not([data-lf-leaving])'


# A view of one thread, which names the thread it shows by id in `data-lf-thread`.
PANEL_THREAD = panel_view("thread")


def text_field(
    scope: Page | Locator | FrameLocator,
    name: str | re.Pattern[str] | None = None,
    *,
    exact: bool | None = None,
):
    """Leaf's text field (`leaf-text`) in `scope` that a role query names `name`, matched
    as `get_by_role` matches it. Its one textbox stands in a closed shadow root no
    locator reaches, so this finds the group around it (text-field.js), among Leaf's
    text fields alone, since other groups can carry the same words."""
    return scope.get_by_role("group", name=name, exact=exact).and_(
        scope.locator("leaf-text")
    )


def page_function(source: str, function: str, *, helpers: str | None = None) -> str:
    """A function for `page.evaluate` that calls `function` of the callbacks `source`
    returns, in the same call, so nothing is installed as a page global. `source` is a
    JavaScript expression returning named callbacks or, with `helpers`, a factory that
    takes the callbacks `helpers` returns. Playwright passes the arguments as usual."""
    if helpers is None:
        declaration = f"const callbacks = {source}\n"
    else:
        declaration = (
            f"const factory = {source}\n"
            f"const helpers = {helpers}\n"
            "const callbacks = factory(helpers);\n"
        )
    return (
        f"(...args) => {{ {declaration}"
        f"return callbacks[{json.dumps(function)}](...args); }}"
    )


# A JavaScript expression for the page's own check API (runtime/check-api.js), imported
# from the page's entry, so it reads the runtime that page runs, each arm's its own, and
# works on a page the harness doesn't watch, which has no `window.__lfCheckApi`
# (tests/render_harness.py, the sensors).
CHECK_API = """import(new URL('runtime/check-api.js', new URL(
  document.querySelector('script[data-lf-entry]').dataset.lfEntry, location.href)).href)"""


def choose_threads_in_panel(page: Page, on: bool = True) -> None:
    """Have this tab open threads about a passage in the panel, or with `on` false
    beside their passages, as for a user who chose that on an earlier visit
    (records/thread/threads-in-panel.js): the choice stored for the tab and read again, which
    says nothing in the panel's field, as a reload doesn't."""
    page.evaluate(
        f"""async (on) => {{
          const api = await {CHECK_API};
          api.tabStore.set(api.THREADS_IN_PANEL_KEY, on ? "panel" : null);
          api.restoreThreadsInPanel();
        }}""",
        on,
    )


def panel_tab(page: Page | FrameLocator, name: str):
    """The On view's tab `name` at the foot of the menu, On and Threads, each one of
    its tabs: `Menu`, `On Me`, `On <agent>`, `Threads` and, while a plan exists,
    `Plan`. Each but Menu and Plan says its count after its name, in `.lf-fp-count`."""
    return page.locator(".lf-fp-controls .lf-fp-filters button", has_text=name)


def unfold(page: Page | FrameLocator, press=None):
    """Unfold a panel folded to the leaf, by `.` or where focus landed on a place its
    row alone would hide (panel/floating-panel.js, `giveWay`), with a press on the leaf, which
    then opens no view. `press` presses a control, a click by default."""
    host = page.locator(PANEL)
    if host.get_attribute("data-lf-rest") == "mark":
        (press or (lambda control: control.click()))(page.locator(LEAF))
        expect(host).to_have_attribute("data-lf-rest", "row")


def on_tab(page: Page | FrameLocator, name: str):
    """Stand the On view open and return its tab `name` (`panel_tab`). A folded panel is
    unfolded first (`unfold`). From the row the leaf opens the view on the tab its marks
    point at; another view, stance or search is closed first by its exit. `page` may be
    a live sample's frame."""
    # A stance's exit goes in the repaint frame. Read the controls only after the
    # previous input has rendered, before choosing a pointer route.
    rendered(
        page.locator("html").element_handle().owner_frame(), facts=("updatesSettled",)
    )
    host = page.locator(PANEL)
    unfold(page)
    if host.get_attribute("data-lf-open") not in ("menu", "queue", "threads"):
        exit_control = page.locator(".lf-fp-exit")
        if exit_control.count():
            exit_control.click()
        page.locator(LEAF).click()
    return panel_tab(page, name)


def open_menu(page: Page | FrameLocator, press=None):
    """Open the leaf's menu by pointer, as a user reaches it from whatever the panel
    shows, and return the menu's view. The leaf unfolds a folded panel; a list over the
    menu goes back to it; otherwise the leaf opens the On view on the tab its marks
    point at, unless the view stands already, and the Menu tab turns the view to the
    menu. A press on the leaf that put away a view the On view led to, as a thread
    opened from Threads, opens the view with the next. `press` presses a control, a
    click by default."""
    press = press or (lambda control: control.click())
    host = page.locator(PANEL)
    leaf = page.locator(LEAF)
    on_view = re.compile("^(menu|queue|threads)$")
    unfold(page, press)
    if host.get_attribute("data-lf-open") != "menu":
        back = page.locator(".lf-fp-head").get_by_role(
            "button", name="Back to Menu", exact=True
        )
        if back.count():
            press(back)
        else:
            if not on_view.match(host.get_attribute("data-lf-open") or ""):
                press(leaf)
                if host.get_attribute("data-lf-open") is None:
                    press(leaf)
                expect(host).to_have_attribute("data-lf-open", on_view)
            if host.get_attribute("data-lf-open") != "menu":
                press(panel_tab(page, "Menu"))
    menu = page.locator(panel_view("menu"))
    menu.wait_for()
    return menu


def threads_tab(page: Page | FrameLocator):
    """Stand the On view open and return the Threads tab at its foot (`on_tab`)."""
    return on_tab(page, "Threads")


def open_on_me(page: Page | FrameLocator):
    """Open On Me by pointer, as a user reaches it: the leaf, which opens the On view on
    On Me while anything waits on the user, then On Me's tab where it opened on another,
    and return the view."""
    tab = on_tab(page, "On Me")
    if page.locator(PANEL).get_attribute("data-lf-open") != "queue" or (
        tab.get_attribute("aria-pressed") != "true"
    ):
        tab.click()
    view = page.locator(panel_view("queue"))
    view.wait_for()
    return view


def open_threads(page: Page | FrameLocator) -> None:
    """Open the floating panel's Threads view by pointer, as a user reaches it: from a
    thread opened over Threads by its way back, else by the Threads tab (`threads_tab`)
    unless the leaf opened Threads itself. The view lists the open threads, then the
    resolved ones folded under a Resolved heading (`show_resolved`)."""
    host = page.locator(PANEL)
    if host.get_attribute("data-lf-open") == "threads":
        return
    back = page.get_by_role("button", name="Back to Threads")
    if back.count():
        back.click()
    else:
        tab = threads_tab(page)
        if host.get_attribute("data-lf-open") != "threads":
            tab.click()
    page.locator(panel_view("threads")).wait_for()


def show_resolved(page: Page | FrameLocator):
    """Unfold the resolved threads in the open Threads, which stand folded under their
    Resolved heading (`.lf-fp-settled`) until the user presses it, and return their
    rows."""
    threads = page.locator(panel_view("threads"))
    heading = threads.locator(".lf-fp-settled")
    if heading.get_attribute("aria-expanded") != "true":
        heading.click()
    return threads.locator(".lf-fp-thread[data-lf-resolved]")


def show_done(page: Page | FrameLocator):
    """Unfold what left the open On list, On Me's or the agent's, which stands folded
    under its Done band (`.lf-fp-settled`) until the user presses it, and return its
    items."""
    view = page.locator('.lf-fp-view[data-lf-route="queue"]:not([data-lf-leaving])')
    heading = view.locator(".lf-fp-settled")
    if heading.get_attribute("aria-expanded") != "true":
        heading.click()
    return view.locator(
        ".lf-rows-group:has(> .lf-rows-head > .lf-fp-settled) > .lf-fp-on-item"
    )


def go_to_threads(page: Page, frame: FrameLocator | None = None) -> None:
    """Open the floating panel's Threads view by Go to Threads (`g` then `T`), in
    `frame`'s page where given, a live sample's. The pointer's route to Threads has
    changed between runtimes, so a driver one checkout runs against another's runtime,
    as `stills`, `bench` and `site verify` do, takes this
    route, which both share."""
    within = frame or page
    # Completing `g T` again closes the view (panel/page-keys/go-to-sequence.js).
    if within.locator(PANEL).get_attribute("data-lf-open") == "threads":
        return
    # A press at the frame's top corner gives its document the keys; the page's own
    # only needs focus off any control.
    if frame:
        frame.locator("body").click(position={"x": 2, "y": 2})
    else:
        page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    within.locator(panel_view("threads")).wait_for()
