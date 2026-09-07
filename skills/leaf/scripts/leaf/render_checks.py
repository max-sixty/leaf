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
WINDOW_ERRORS_SOURCE = PROBE_ROOT / "init.js"
STANDALONE_FILE_ROUTE = "file:///_leaf/render-checks/standalone.js"
PROBE_SOURCES = {
    f"/_leaf/render-checks/{source.name}": source
    for source in sorted(PROBE_ROOT.glob("*.js"))
}

_PROBE_CACHE = "__leafRenderChecks"
_START_PROBES = f"""(call) => {{
  if (globalThis.{_PROBE_CACHE}?.route === call.route) return;
  const loading = {{route: call.route, probes: null, error: null}};
  globalThis.{_PROBE_CACHE} = loading;
  import(call.route).then(
    (probes) => {{
      if (globalThis.{_PROBE_CACHE} === loading) loading.probes = probes;
    }},
    (error) => {{
      if (globalThis.{_PROBE_CACHE} === loading)
        loading.error = {{
          name: error?.name ?? "Error",
          message: error?.message ?? String(error),
        }};
    }},
  );
}}"""
_PROBES_LOADED = f"""(call) => {{
  const loading = globalThis.{_PROBE_CACHE};
  if (loading?.route !== call.route) return false;
  if (loading.error) {{
    const error = new Error(
      `Leaf browser probes failed to load from ${{call.route}}: ` +
      loading.error.message
    );
    error.name = loading.error.name;
    throw error;
  }}
  return loading.probes !== null;
}}"""
_PROBE = f"""(call) => {{
  const probe = globalThis.{_PROBE_CACHE}?.probes?.[call.name];
  if (typeof probe !== "function")
    throw new TypeError(`unknown Leaf browser probe ${{call.name}}`);
  const result = probe(...call.args);
  if (result && typeof result.then === "function")
    throw new TypeError(
      `Leaf browser probe ${{call.name}} must be synchronous; ` +
      `publish a synchronous reading or readiness fact instead`
    );
  return result;
}}"""


def _call(page, name: str, args: tuple) -> dict:
    route = PROBE_ROUTE
    if page.url.startswith("file:"):
        if not getattr(page, "_leaf_standalone_probes_prepared", False):
            raise ValueError(
                "prepare_standalone_probes must run before file navigation"
            )
        route = STANDALONE_FILE_ROUTE
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
    page.route(
        STANDALONE_FILE_ROUTE,
        lambda route: route.fulfill(
            status=200,
            content_type="text/javascript; charset=utf-8",
            body=STANDALONE_SOURCE.read_bytes(),
        ),
    )
    page._leaf_standalone_probes_prepared = True


def _load_probes(page, call: dict) -> None:
    """Start the module load and observe its result from a bounded driver wait."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

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


def install_window_errors(page) -> None:
    """Install the pre-navigation error channel shared by the gate and suite."""
    page.add_init_script(path=WINDOW_ERRORS_SOURCE)
