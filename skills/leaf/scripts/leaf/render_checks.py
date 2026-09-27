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


# The page's own readiness reading (`pageReadiness` in runtime/presentation.js), read
# off the entry script so a bundled entry answers too. A page whose entry has not run
# yet has no reading, and starting is the first stage it owes. `answering` is the one
# stage read from out here: a page too busy to say which stage it is at.
_READINESS = """({held, through}) => {
  const readiness = document.querySelector('script[data-lf-entry]')?.lfReadiness;
  return readiness ? readiness(held, through ?? undefined) : 'started';
}"""
_READY = f"asked => ({_READINESS})(asked) === null"
_OUTSTANDING = f"asked => ({_READINESS})(asked) ?? 'ready'"
# How a failure words each stage `pageReadiness` names. `state` fails only against an
# answer the caller holds.
_UNREADY = {
    "answering": "the page stopped answering",
    "started": "the runtime never started",
    "upgraded": "the widget layer never finished upgrading",
    "log": "the runtime never finished replaying the log",
    "state": "the runtime never applied the state the server held (reading {reading})",
    "presented": "the runtime never presented the page after applying its current state",
    "arrived": "work the page deferred past presentation never landed",
    "rendering": "the page's rendering never settled",
}
# How long a page that has missed its deadline gets to say which stage it is at.
_STAGE_READ_MS = 5_000


class PageNotReady(TimeoutError):
    """A page that never stated one of its readiness facts; `stage` names which."""

    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def wait_until_ready(
    page,
    state: dict | None = None,
    *,
    through: str | None = None,
    timeout_ms: int | None = None,
) -> None:
    """Wait until the page says a reader outside it may read its final boxes and press
    its keys, or raise `PageNotReady` naming the first fact it never stated.

    Every reader outside the page waits here rather than combining the runtime's
    stamps itself: the stages, and their order, are the runtime's (`pageReadiness`).
    `state` is an `/api/state` answer the caller already holds, and asks the page to
    have applied all of it: log, data, status, versions and presence. The server may
    move on between the caller's read and the page's, so an answer the server took
    later meets it as well. `through` names the last stage the caller needs, for a
    caller that wants the answer taken in while the page is still mid-gesture. Finite
    animation is not readiness; the render gate asks `pageSettled` for that on its own.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    asked = {
        "held": (
            None
            if state is None
            else {"reading": state["reading"], "taken": state["taken"]}
        ),
        "through": through,
    }
    timeout_ms = timeout_ms or getattr(
        page, "_leaf_probe_timeout_ms", SERVED_TIMEOUT_MS
    )
    try:
        page.wait_for_function(_READY, arg=asked, timeout=timeout_ms)
    except PlaywrightTimeout:
        pass
    else:
        return
    # Read the stage through a bounded wait too, since `evaluate` takes no deadline: a
    # page whose own code holds its main thread answers neither.
    try:
        stage = page.wait_for_function(
            _OUTSTANDING, arg=asked, timeout=_STAGE_READ_MS
        ).json_value()
    except PlaywrightTimeout:
        stage = "answering"
    if stage == "ready":
        return
    words = _UNREADY[stage].format_map(asked["held"] or {})
    raise PageNotReady(stage, f"{words} within {timeout_ms}ms")


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
