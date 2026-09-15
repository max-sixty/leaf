"""The browser the user-path gates launch.

`version check --render` and `version export` both draw the page in a real
browser, and both should reach whichever one the host has. Playwright's
`channel="chrome"` finds a Google Chrome release-channel install at a fixed OS
path and nothing else, so a Chrome for Testing, a distro or Homebrew Chromium,
or a self-hosted build is invisible to it — even though every render invariant
passes on one, which is why the suite's own fixture drives the headless shell.
With no outbound network Playwright's usual answer of fetching its own browser
is gone too, and leaf does not download one.

So the host names its browser, and where it has named none, leaf asks the host
where its programs are before it guesses. Three readings, in order:

- an environment variable, which is a direct statement. LEAF_BROWSER_EXECUTABLE
  is the name in the namespace `host.py` already uses for LEAF_AGENT and
  LEAF_SESSION_ID, and it stays first; CHROME_PATH (chrome-launcher, and so
  Lighthouse) and CHROME_BIN (karma-chrome-launcher) predate Playwright and mean
  the same thing, so a host that already set one for another tool has named this
  browser too. Playwright's own `launch()` reads no such variable —
  PLAYWRIGHT_BROWSERS_PATH is a download root — which is why a Playwright-based
  tool has to pick a name, and why picking names that already exist costs
  nothing;
- the installed Chrome release channel, unchanged and still ahead of discovery,
  so a host with both a Chrome and a distro Chromium keeps getting the Chrome it
  gets today;
- `PATH`, which is the host's own statement of where its programs are. A
  hardcoded candidate list is not: it needs an entry per distribution and can
  never name a `/nix/store/<hash>-chromium-*/bin/chromium`.

The variables carry a path and nothing else: the launch takes no other argument
from the host.

Under every one of those readings sits Playwright's driver, a Node process that
leaf neither names nor sees. Where that process ends at startup no launch is
reached at all, so `playwright_driver()` reports it beside the failures above
rather than through them.
"""

import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

VARIABLE = "LEAF_BROWSER_EXECUTABLE"
VARIABLES = (VARIABLE, "CHROME_PATH", "CHROME_BIN")

# Playwright runs its driver under Node, and reads this for the executable. It is
# not leaf's namespace, but it is the only knob over the process whose failure
# `playwright_driver()` reports, so the message that reports one names it.
DRIVER_VARIABLE = "PLAYWRIGHT_NODEJS_PATH"

# Chrome first, so discovery reaching a host that also has a Chrome would land
# where the channel already does.
COMMANDS = (
    "google-chrome",
    "google-chrome-stable",
    "chrome",
    "chromium",
    "chromium-browser",
)

# `bake()` ends in `root.getHTML({ serializableShadowRoots: true })`, which
# Chromium grew in 125. Every widget draws into a shadow root, so below this a
# copy is not partial, it is impossible.
EXPORT_FLOOR = 125


def named_executable() -> tuple[str, str] | None:
    """The variable this host set and the path it carries, or None where it set
    none. Empty is none, so a caller handing a child its own environment can
    unname one — with three names read, unnaming means clearing all three, which
    is what `VARIABLES` is public for."""
    for name in VARIABLES:
        if value := os.environ.get(name):
            return name, value
    return None


def discovered_executable() -> str | None:
    """The first browser command on the host's PATH, or None where PATH holds
    none of them."""
    for command in COMMANDS:
        if found := shutil.which(command):
            return found
    return None


class DriverNotStarted(Exception):
    """Playwright's driver ended before it answered the connection, so no browser
    was ever asked for. Carries that connection's own first line, which each gate
    reports in its own words as it does a failed launch."""


def driver_node() -> str:
    """The Node that Playwright runs its driver under: whichever DRIVER_VARIABLE
    names, else the one bundled in the installed wheel.

    Both readings are Playwright's, made here from the package's own location
    rather than through `playwright._impl._driver`: this runs only on the path
    where the driver already failed, and a private that moved would put the
    traceback back."""
    if named := os.environ.get(DRIVER_VARIABLE):
        return named
    import playwright

    return str(Path(playwright.__file__).parent / "driver" / "node")


def driver_hint() -> str:
    """The line each gate appends when the driver never started.

    The two hosts this reaches are a glibc older than the bundled Node needs and a
    DRIVER_VARIABLE naming a Node older than the driver bundle needs. The first
    fails in the loader naming the binary, the second inside the bundle naming
    nothing, and neither says which Node ran or what chooses it — so the hint says
    both."""
    node = driver_node()
    if os.environ.get(DRIVER_VARIABLE):
        return f"{DRIVER_VARIABLE} named {node}."
    return f"Playwright ran its bundled {node}; {DRIVER_VARIABLE} names another."


@contextmanager
def playwright_driver():
    """Playwright, with a driver that never started raised as DriverNotStarted
    rather than as a Playwright private.

    `sync_playwright().__enter__` returns `self._playwright`, which the connection
    callback assigns. A driver that exits at startup never runs that callback, so
    the context entry dies on an AttributeError naming that attribute while the
    real cause sits on the connection's init task — printed afterwards, out of
    order, as asyncio's `Task exception was never retrieved`. Reading that task is
    what both names the cause and keeps the second traceback from being printed at
    all."""
    from playwright.sync_api import sync_playwright

    manager = sync_playwright()
    try:
        try:
            playwright = manager.start()
        except AttributeError as error:
            raise DriverNotStarted(_driver_failure(manager)) from error
        yield playwright
    finally:
        manager.__exit__()


def _driver_failure(manager) -> str:
    """Why the connection ended, in one line.

    The reason is an exception on the connection's init task, reachable only
    through Playwright privates. Every reading is optional here and a plain
    sentence stands in for a missing one, because this runs on the path whose
    whole point is that an attribute error stops being what the reader sees."""
    task = getattr(getattr(manager, "_connection", None), "_init_task", None)
    if task is None or not task.done() or task.cancelled():
        return "the driver ended before answering"
    error = task.exception()
    if error is None:
        return "the driver ended before answering"
    return str(error).strip().splitlines()[0]


def launch_browser(p):
    """The host's browser, and what to call it in a message that reports
    success: whichever executable a browser variable names, else the installed
    Chrome release channel, else the first browser on PATH. Raises
    PlaywrightError, which each gate reports in its own words.

    A host that named an executable, or whose channel missed, never ran Chrome,
    so naming Chrome there would be the same false claim the failure messages
    stopped making."""
    # Imported where a browser is about to launch, here and in the other gates,
    # rather than at module top: playwright.sync_api is half of what a `leaf`
    # command spends importing, and most commands never open a browser.
    from playwright.sync_api import Error as PlaywrightError

    if named := named_executable():
        _, executable = named
        return p.chromium.launch(executable_path=executable), executable
    try:
        return p.chromium.launch(channel="chrome"), "Chrome"
    except PlaywrightError:
        # Only after the channel has missed, so discovery adds hosts rather than
        # moving any that work today.
        if executable := discovered_executable():
            return p.chromium.launch(executable_path=executable), executable
        raise


def browser_hint() -> str:
    """The line each gate appends when the launch failed."""
    if named := named_executable():
        name, executable = named
        return f"{name} named {executable}."
    if executable := discovered_executable():
        return (
            f"Neither an installed Chrome nor {executable}, the browser on PATH, "
            "launched."
        )
    return (
        f"This host has no installed Chrome and none of {', '.join(COMMANDS)} on "
        f"PATH; {' or '.join(VARIABLES)} names one."
    )


def below_export_floor(browser) -> str | None:
    """The version this browser reports where it is too old to copy a page, else
    None.

    The render gate never bakes, so an older browser passes `--render` and then
    fails export inside the probe with `root.getHTML is not a function` — which
    reads as a broken probe module rather than as the host's browser being too
    old. Discovery makes that more reachable, since a distribution's `chromium`
    can be any age. A version that does not start with a number is not refused:
    an unreadable reading is not evidence of an old browser."""
    version = browser.version
    major = re.match(r"\d+", version)
    if major and int(major.group()) < EXPORT_FLOOR:
        return version
    return None
