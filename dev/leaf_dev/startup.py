"""Development startup observations shared by local probes and site verification.

Install before navigation. Read after presentation: the recorder includes its two
paint frames, with native layout-shift attribution and no stability budget.
"""

from pathlib import Path

from playwright.sync_api import Page

SCRIPT = Path(__file__).with_suffix(".js")


def observe_startup(page: Page) -> None:
    """Record one document's milestones, resources, and initial native shifts."""
    page.add_init_script(path=SCRIPT)


def startup_reading(page: Page) -> dict:
    """Drain native evidence through the initial presentation's painted frames."""
    return page.evaluate("window.__leafStartup.reading")
