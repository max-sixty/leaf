"""The browser, and tabs on a served page, opened and settled the same way by every
command that reads or screenshots one."""

from contextlib import contextmanager

from leaf.render_checks import wait_for_probe, wait_until_ready
from leaf.render_gate.browser import launch_browser
from playwright.sync_api import Browser, Page, sync_playwright

DESKTOP = (1440, 900)
# The width of a window beside an editor.
BESIDE = (900, 900)


@contextmanager
def chrome():
    """The host's browser, as the render gate launches it (`launch_browser`), closed
    however the block is left."""
    with sync_playwright() as playwright:
        browser, _ = launch_browser(playwright)
        try:
            yield browser
        finally:
            browser.close()


@contextmanager
def tab(browser: Browser, viewport=DESKTOP, scheme="light", touch=False):
    """A fresh blank tab at `viewport` and in `scheme`, with reduced motion so a still
    never catches a transition midway, and under a finger (a coarse pointer, a mobile
    viewport) when `touch`. A caller listens on it before it `load`s."""
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        color_scheme=scheme,
        reduced_motion="reduce",
        has_touch=touch,
        is_mobile=touch,
    )
    try:
        page = context.new_page()
        page.set_default_timeout(15_000)
        yield page
    finally:
        context.close()


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
