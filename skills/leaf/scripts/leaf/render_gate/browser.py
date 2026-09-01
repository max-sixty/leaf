"""The browser the user-path gates launch.

`version check --render` and `version export` both draw the page in a real
browser, and both should reach whichever one the host has. Playwright's
`channel="chrome"` finds a Google Chrome release-channel install at a fixed OS
path and nothing else, so a Chrome for Testing, a distro or Homebrew Chromium,
or a self-hosted build is invisible to it — even though every render invariant
passes on one, which is why the suite's own fixture drives the headless shell.
With no outbound network Playwright's usual answer of fetching its own browser
is gone too, and leaf does not download one.

So the host names its browser, in the namespace `host.py` already uses for
LEAF_AGENT and LEAF_SESSION_ID. The variable carries a path and nothing else:
the launch takes no other argument from the host, and the default is unchanged
where it names none.
"""

import os

VARIABLE = "LEAF_BROWSER_EXECUTABLE"


def named_executable() -> str | None:
    """The browser this host named, or None where it named none. Empty is none,
    so a caller handing a child its own environment can unname one."""
    return os.environ.get(VARIABLE) or None


def launch_browser(p):
    """The host's browser: whichever executable LEAF_BROWSER_EXECUTABLE names,
    else the installed Chrome release channel. Raises PlaywrightError, which
    each gate reports in its own words."""
    if executable := named_executable():
        return p.chromium.launch(executable_path=executable)
    return p.chromium.launch(channel="chrome")


def browser_hint() -> str:
    """The line each gate appends when the launch failed."""
    if executable := named_executable():
        return f"{VARIABLE} named {executable}."
    return f"{VARIABLE} names one if this host has no installed Chrome."
