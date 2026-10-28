"""Startup and layout observations shared by local probes and site verification.

Install before navigation. Startup includes presentation's two paint frames;
layout-shift evidence continues through interactions. Neither imposes a budget.
"""

from pathlib import Path

from playwright.sync_api import Page

SCRIPT = Path(__file__).with_suffix(".js")


def observe_startup(page: Page) -> None:
    """Record one document's startup milestones, resources, and native shifts."""
    page.add_init_script(path=SCRIPT)


def startup_reading(page: Page) -> dict:
    """Drain native evidence through the initial presentation's painted frames."""
    return page.evaluate("window.__leafStartup.reading")


def layout_shifts_reading(page: Page) -> dict:
    """Read this document's native shifts through a completed rendering frame.

    The caller waits for its action's result first; this checkpoint lets the browser
    paint that result. Sources name affected nodes, not the code that moved them.
    """
    return page.evaluate("""async () => {
      await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
      return window.__leafStartup.layoutShifts();
    }""")
