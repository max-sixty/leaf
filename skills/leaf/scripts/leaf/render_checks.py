"""Named browser probes used by the render gate."""

from pathlib import Path

RENDER_VIEWPORT = {"width": 1200, "height": 900}

# The same patience Playwright gives browser waits. Keeping the server request timeout
# beside it turns a wedged preview into a useful failure rather than an unbounded evaluate.
SERVED_TIMEOUT_MS = 30_000

PROBE_ROOT = Path(__file__).with_name("render-checks")
PROBE_ROUTE = "/_leaf/render-checks/index.js"
DRIVER_SOURCE = PROBE_ROOT / "driver.js"
WINDOW_ERRORS_SOURCE = PROBE_ROOT / "init.js"
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


def _call(page, name: str, args: tuple, timeout_ms: int | None = None) -> dict:
    route = page.evaluate(
        """route => {
      const entry = document.querySelector('script[data-lf-entry]')?.dataset.lfEntry;
      return entry ? new URL(route.slice(1), new URL(entry, location.href)).href : route;
    }""",
        PROBE_ROUTE,
    )
    return {
        "route": route,
        "name": name,
        "args": list(args),
        "timeoutMs": timeout_ms
        or getattr(page, "_leaf_probe_timeout_ms", SERVED_TIMEOUT_MS),
    }


def install_driver(page) -> None:
    """Install the guarded document-side probe driver before navigation."""
    # A frame uses its containing page's initialization scripts; evaluations and
    # probe imports remain in the frame's own document.
    page = getattr(page, "page", page)
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
        # Probe readiness is independent of animation frames. A complete child
        # document in a closed disclosure or inactive tab still needs inspection,
        # but browsers suspend its requestAnimationFrame callbacks.
        page.wait_for_function(
            _PROBES_LOADED, arg=call, timeout=call["timeoutMs"], polling=100
        )
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


def wait_for_probe(page, name: str, *args, timeout_ms: int | None = None) -> None:
    """Wait until one named browser probe returns a truthy value.

    The default patience suits a reading that arrives once the page settles. A caller
    waiting on work the page is doing on its behalf states its own budget, because the
    page answers nothing at all while that work holds its main thread.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    call = _call(page, name, args, timeout_ms)
    _load_probes(page, call)
    try:
        page.wait_for_function(_PROBE, arg=call, timeout=call["timeoutMs"], polling=100)
    except PlaywrightTimeout as error:
        raise PlaywrightTimeout(
            f"Leaf wait probe {name} did not become true within {call['timeoutMs']}ms"
        ) from error


def wait_for_presentation(
    page, state: dict, replayed_events: int, *, settled: bool = False
) -> str | None:
    """Wait through the canonical post-upgrade presentation stages.

    Return the first stage that times out so callers can explain that boundary in
    their own terms. Probe loading errors still surface: a missing observer is not an
    unready page.

    `state` is the caller's own `/api/state` reading. Any process may rewrite a source
    between that read and the browser's, so the data stage is met by the reading's
    version or by any reading the server took no earlier.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    stages = [("dataApplied", (state["data"]["version"], state["taken"]))]
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
