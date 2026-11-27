"""JavaScript programs used by browser tests, checked as ordinary source files.

Modules are copied into a served fixture with ``browser_source``. A probe file
is an expression returning named callbacks, or a factory consuming another
file's callbacks through ``using``. ``browser_function`` evaluates the sources
in the same call as its selected callback, without installing page globals
(`leaf_dev.browser.page_function`). Playwright passes the callback's inputs
through its normal argument channel. Small case-specific expressions stay beside
their Python assertions.
"""

from functools import cache
from pathlib import Path

from leaf_dev.browser import page_function

SOURCE_ROOT = Path(__file__).with_name("page_scripts")


@cache
def browser_source(name: str) -> str:
    """Read a test-owned JavaScript file relative to ``tests/page_scripts``."""
    return (SOURCE_ROOT / name).read_text(encoding="utf-8")


def browser_function(name: str, function: str, *, using: str | None = None) -> str:
    """Select a callback without changing Playwright's Page/Locator call shape."""
    return page_function(
        browser_source(name),
        function,
        helpers=browser_source(using) if using else None,
    )
