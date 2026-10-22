"""The browser the render gate launches.

`page check --render` draws the page in a real browser, and should reach
whichever one the host has. Playwright's
`channel="chrome"` finds a Google Chrome release-channel install at a fixed OS
path and nothing else, so a Chrome for Testing, a distro or Homebrew Chromium,
or a self-hosted build is invisible to it — even though every render invariant
passes on one, which is why the suite's own fixture drives the headless shell.
With no outbound network Playwright's usual answer of fetching its own browser
is gone too, and leaf does not download one.

So the host names its browser, and where it has named none, leaf asks the host
where its programs are before it guesses. Three readings, in order:

- an environment variable, which is a direct statement. LEAF_BROWSER_EXECUTABLE
  is the name in the namespace `harness.py` already uses for LEAF_AGENT and
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
"""

import os
import shutil

from leaf.machine import sandbox_remedy

VARIABLE = "LEAF_BROWSER_EXECUTABLE"
VARIABLES = (VARIABLE, "CHROME_PATH", "CHROME_BIN")

# Chrome first, so discovery reaching a host that also has a Chrome would land
# where the channel already does.
COMMANDS = (
    "google-chrome",
    "google-chrome-stable",
    "chrome",
    "chromium",
    "chromium-browser",
)


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


def launch_browser(p, **options):
    """The host's browser, and what to call it in a message that reports
    success: whichever executable a browser variable names, else the installed
    Chrome release channel, else the first browser on PATH, launched with
    Playwright's launch `options`. Raises PlaywrightError, which the gate reports
    in its own words.

    A host that named an executable, or whose channel missed, never ran Chrome,
    so naming Chrome there would be the same false claim the failure messages
    stopped making."""
    # Imported where a browser is about to launch, here and in the gate,
    # rather than at module top: playwright.sync_api is half of what a `leaf`
    # command spends importing, and most commands never open a browser.
    from playwright.sync_api import Error as PlaywrightError

    if named := named_executable():
        _, executable = named
        return p.chromium.launch(executable_path=executable, **options), executable
    try:
        return p.chromium.launch(channel="chrome", **options), "Chrome"
    except PlaywrightError:
        # Only after the channel has missed, so discovery adds hosts rather than
        # moving any that work today.
        if executable := discovered_executable():
            return p.chromium.launch(executable_path=executable, **options), executable
        raise


def browser_hint() -> str:
    """The line the gate appends when the launch failed.

    Inside an agent's sandbox the browser is not what is missing: Claude Code's
    macOS sandbox refuses Chrome the Mach service its processes meet at, and Codex's
    ends it as it starts, so the line says where to run the check instead."""
    if remedy := sandbox_remedy():
        return f"The browser cannot start here: {remedy}."
    if named := named_executable():
        name, executable = named
        return f"{name} named {executable}."
    if executable := discovered_executable():
        return (
            f"Neither an installed Chrome nor {executable}, the browser on PATH, "
            "launched."
        )
    return (
        f"No installed Chrome launched and none of {', '.join(COMMANDS)} is on "
        f"PATH; {' or '.join(VARIABLES)} names a browser."
    )
