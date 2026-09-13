"""Named browser probes used by the render and export gates."""

from pathlib import Path

RENDER_VIEWPORT = {"width": 1200, "height": 900}

# The same patience Playwright gives browser waits. Keeping the server request timeout
# beside it turns a wedged preview into a useful failure rather than an unbounded evaluate.
SERVED_TIMEOUT_MS = 30_000

PROBE_ROOT = Path(__file__).with_name("render-checks")
PROBE_ROUTE = "/_leaf/render-checks/index.js"
STANDALONE_ROUTE = "/_leaf/render-checks/standalone.js"
STANDALONE_SOURCE = PROBE_ROOT / "standalone.js"
DRIVER_SOURCE = PROBE_ROOT / "driver.js"
WINDOW_ERRORS_SOURCE = PROBE_ROOT / "init.js"
STANDALONE_FILE_ROUTE = "file:///_leaf/render-checks/standalone.js"
PROBE_SOURCES = {
    f"/_leaf/render-checks/{source.name}": source
    for source in sorted(PROBE_ROOT.glob("*.js"))
    if source != DRIVER_SOURCE
}

_DRIVER_PRESENT = "() => Boolean(globalThis.__leafRenderDriver)"
_START_PROBES = "call => globalThis.__leafRenderDriver.start(call)"
_PROBES_LOADED = "call => globalThis.__leafRenderDriver.loaded(call)"
_PROBE = "call => globalThis.__leafRenderDriver.call(call)"
_THEME_READY = "() => globalThis.__leafRenderDriver.themeReady()"
_PRE_UPGRADE_FINDINGS = "() => globalThis.__leafRenderDriver.preUpgradeFindings()"


def _call(page, name: str, args: tuple) -> dict:
    route = PROBE_ROUTE
    if page.url.startswith("file:"):
        if not getattr(page, "_leaf_standalone_probes_prepared", False):
            raise ValueError(
                "prepare_standalone_probes must run before file navigation"
            )
        route = STANDALONE_FILE_ROUTE
    else:
        route = page.evaluate(
            """route => {
          const entry = document.querySelector('script[data-lf-entry]')?.dataset.lfEntry;
          return entry ? new URL(route.slice(1), new URL(entry, location.href)).href : route;
        }""",
            route,
        )
    return {
        "route": route,
        "name": name,
        "args": list(args),
        "timeoutMs": getattr(page, "_leaf_probe_timeout_ms", SERVED_TIMEOUT_MS),
    }


def prepare_standalone_probes(page) -> None:
    """Expose the import-free probe module before a standalone file navigates.

    Exported files retain the page's CSP, which correctly refuses every script. The
    probe is test instrumentation rather than part of the copy, so a Playwright page
    created with ``bypass_csp=True`` routes one synthetic file URL to the real module.
    """
    if getattr(page, "_leaf_standalone_probes_prepared", False):
        return
    install_driver(page)
    page.route(
        STANDALONE_FILE_ROUTE,
        lambda route: route.fulfill(
            status=200,
            content_type="text/javascript; charset=utf-8",
            body=STANDALONE_SOURCE.read_bytes(),
        ),
    )
    page._leaf_standalone_probes_prepared = True


def install_driver(page) -> None:
    """Install the guarded document-side probe driver before navigation."""
    if getattr(page, "_leaf_render_driver_installed", False):
        return
    page.add_init_script(path=DRIVER_SOURCE)
    page._leaf_render_driver_installed = True


def _ensure_driver(page) -> None:
    """Make the driver available to callers that received an open page."""
    install_driver(page)
    if not page.evaluate(_DRIVER_PRESENT):
        page.evaluate(DRIVER_SOURCE.read_text(encoding="utf-8"))


def _load_probes(page, call: dict) -> None:
    """Start the module load and observe its result from a bounded driver wait."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    _ensure_driver(page)
    page.evaluate(_START_PROBES, call)
    try:
        page.wait_for_function(_PROBES_LOADED, arg=call, timeout=call["timeoutMs"])
    except PlaywrightTimeout as error:
        raise PlaywrightError(
            f"Leaf browser probes did not load from {call['route']} within "
            f"{call['timeoutMs']}ms"
        ) from error


def evaluate_probe(page, name: str, *args):
    """Invoke one named export from the browser probe module."""
    call = _call(page, name, args)
    _load_probes(page, call)
    return page.evaluate(_PROBE, call)


def wait_for_probe(page, name: str, *args) -> None:
    """Wait until one named browser probe returns a truthy value."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    call = _call(page, name, args)
    _load_probes(page, call)
    try:
        page.wait_for_function(_PROBE, arg=call, timeout=call["timeoutMs"])
    except PlaywrightTimeout as error:
        raise PlaywrightTimeout(
            f"Leaf wait probe {name} did not become true within {call['timeoutMs']}ms"
        ) from error


def wait_for_presentation(
    page, data_revision: int, replayed_events: int, *, settled: bool = False
) -> str | None:
    """Wait through the canonical post-upgrade presentation stages.

    Return the first stage that times out so callers can explain that boundary in
    their own terms. Probe loading errors still surface: a missing observer is not an
    unready page.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    stages = [("dataApplied", (data_revision,))]
    if replayed_events:
        stages.append(("logApplied", (replayed_events,)))
    stages.append(("currentPresented", ()))
    if settled:
        stages.append(("pageSettled", ()))
    for name, args in stages:
        try:
            wait_for_probe(page, name, *args)
        except PlaywrightTimeout:
            return name
    return None


def wait_for_theme(page) -> None:
    """Wait until the authored document's theme stylesheet is readable."""
    _ensure_driver(page)
    page.wait_for_function(_THEME_READY)


def pre_upgrade_findings(page) -> list[str]:
    """Read authored structure before the held Leaf entry is released."""
    _ensure_driver(page)
    return page.evaluate(_PRE_UPGRADE_FINDINGS)


def install_window_errors(page) -> None:
    """Install the pre-navigation error channel shared by the gate and suite."""
    install_driver(page)
    page.add_init_script(path=WINDOW_ERRORS_SOURCE)
