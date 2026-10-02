"""JavaScript programs used by browser tests, checked as ordinary source files.

Modules are copied into a served fixture with ``browser_source``. A probe file
is an expression returning named callbacks, or a factory consuming another
file's callbacks through ``using``. ``browser_function`` evaluates the sources
in the same call as its selected callback, without installing page globals.
Playwright passes the callback's inputs through its normal argument channel.
Small case-specific expressions stay beside their Python assertions.
"""

import json
from functools import cache
from pathlib import Path

SOURCE_ROOT = Path(__file__).with_name("browser")


@cache
def browser_source(name: str) -> str:
    """Read a test-owned JavaScript file relative to ``tests/browser``."""
    return (SOURCE_ROOT / name).read_text(encoding="utf-8")


def browser_function(name: str, function: str, *, using: str | None = None) -> str:
    """Select a callback without changing Playwright's Page/Locator call shape."""
    if using is None:
        declaration = f"const callbacks = {browser_source(name)}\n"
    else:
        declaration = (
            f"const factory = {browser_source(name)}\n"
            f"const helpers = {browser_source(using)}\n"
            "const callbacks = factory(helpers);\n"
        )
    return (
        f"(...args) => {{ {declaration}"
        f"return callbacks[{json.dumps(function)}](...args); }}"
    )
