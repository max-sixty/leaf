"""Safari on an iOS simulator, for a probe of an iPhone-only difference.

Playwright's WebKit is a desktop build and differs from iOS WebKit beyond its version:
on 2026-10-26 iOS 26.1 listed adopted stylesheets in `document.styleSheets` and
Playwright's WebKit 26.6 did not, which unstyled Leaf's chrome on iPhones alone.
Playwright drives no iOS browser, so this drives the simulator's Safari through
safaridriver, Apple's WebDriver server, with Selenium as its client.

The simulator shares the Mac's loopback, so a page served here opens at its own
address. A booted iPhone simulator is used and left running; otherwise the newest
runtime's first iPhone boots for the run and shuts down after it. The host needs Xcode
with an iOS runtime (`xcodebuild -downloadPlatform iOS`).
"""

import json
import re
import subprocess
import time
from contextlib import contextmanager

import click
from selenium import webdriver
from selenium.common.exceptions import JavascriptException

from leaf.render_checks import HANDOVER_DEADLINE_MS, OUTSTANDING, UNREADY, PageNotReady

# The bound on one script, as `SERVED_TIMEOUT_MS` bounds one Playwright probe.
SCRIPT_TIMEOUT_S = 120


def simctl(*args: str) -> str:
    return subprocess.run(
        ["xcrun", "simctl", *args], check=True, capture_output=True, text=True
    ).stdout


def iphone() -> tuple[str, bool]:
    """A booted iPhone simulator's udid, else the newest runtime's first iPhone's, and
    whether it was already booted."""
    devices = json.loads(simctl("list", "devices", "available", "-j"))["devices"]
    phones = [
        (tuple(map(int, re.findall(r"\d+", runtime))), device)
        for runtime, listed in devices.items()
        if ".iOS-" in runtime
        for device in listed
        if "iPhone" in device["deviceTypeIdentifier"]
    ]
    if not phones:
        raise click.ClickException(
            "no iPhone simulator; install an iOS runtime with "
            "`xcodebuild -downloadPlatform iOS`"
        )
    for _, device in phones:
        if device["state"] == "Booted":
            return device["udid"], True
    return max(phones, key=lambda phone: phone[0])[1]["udid"], False


@contextmanager
def ios_safari(scheme: str = "light"):
    """A WebDriver session on an iPhone simulator's Safari, in `scheme`, closed however
    the block is left."""
    udid, booted = iphone()
    try:
        # Boots the device unless it is up, and returns once it has finished booting.
        simctl("bootstatus", udid, "-b")
        simctl("ui", udid, "appearance", scheme)
        options = webdriver.SafariOptions()
        options.set_capability("platformName", "iOS")
        options.set_capability("safari:useSimulator", True)
        options.set_capability("safari:deviceUDID", udid)
        # Under the default strategy, which waits for the page's load, navigating to a
        # Leaf page never returned (2026-10-26); `load` waits on readiness instead.
        options.set_capability("pageLoadStrategy", "none")
        driver = webdriver.Safari(options=options)
        try:
            driver.set_script_timeout(SCRIPT_TIMEOUT_S)
            yield driver
        finally:
            driver.quit()
    finally:
        if not booted:
            simctl("shutdown", udid)


def evaluate(driver, expression: str, arg=None):
    """What `expression` gives in the page, awaited, as Playwright's `evaluate` takes it:
    a function is called with `arg`. The expression is part of the script WebDriver
    runs rather than a string the page evaluates, so a page's CSP doesn't refuse it."""
    answer = driver.execute_async_script(
        "const [arg, done] = arguments;"
        f"Promise.resolve().then(() => {{ const v = ({expression}\n);"
        " return typeof v === 'function' ? v(arg) : v; })"
        ".then(value => done({value: value ?? null}),"
        " error => done({error: String(error?.stack ?? error)}));",
        arg,
    )
    if "error" in answer:
        raise JavascriptException(answer["error"])
    return answer["value"]


# Finite motion has run its course and the fonts have loaded: what a reading after
# `settle` relies on, short of the render driver, which only Playwright installs.
SETTLED = """async () => {
  await document.fonts.ready;
  const finite = document.getAnimations()
    .filter(played => played.effect?.getComputedTiming().endTime !== Infinity);
  await Promise.all(finite.map(played => played.finished.catch(() => {})));
}"""


def load(driver, address: str, leaf: bool = True) -> None:
    """Open `address` and wait for the new document: a Leaf page until it states it is
    ready (`pageReadiness`) and has settled, any other page until it has loaded."""
    # The old document answers until the new one commits, and a second arm's server
    # can take the first one's port, so the old document is marked as left.
    driver.execute_script("window.__leafProbeLeft = true")
    driver.get(address)
    deadline = time.monotonic() + HANDOVER_DEADLINE_MS / 1000
    stage = (
        f"({OUTSTANDING})({{held: null, through: null}})"
        if leaf
        else "document.readyState === 'complete' ? 'ready' : 'started'"
    )
    stage_now = f"() => window.__leafProbeLeft ? 'started' : {stage}"
    while (reached := evaluate(driver, stage_now)) != "ready":
        if time.monotonic() > deadline:
            words = UNREADY[reached] if leaf else "the page never loaded"
            raise PageNotReady(reached, f"{words} within {HANDOVER_DEADLINE_MS}ms")
        time.sleep(0.1)
    if leaf:
        evaluate(driver, SETTLED)
