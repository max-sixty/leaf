"""Named browser probes used by the render and export gates."""

from pathlib import Path

RENDER_VIEWPORT = {"width": 1200, "height": 900}

# The same patience Playwright gives browser waits. Keeping the server request timeout
# beside it turns a wedged preview into a useful failure rather than an unbounded evaluate.
SERVED_TIMEOUT_MS = 30_000

PROBE_ROUTE = "/_leaf/render-checks.js"
PROBE_SOURCE = Path(__file__).with_name("render-checks.js")
STANDALONE_ROUTE = "/_leaf/render-checks-standalone.js"
STANDALONE_SOURCE = Path(__file__).with_name("render-checks-standalone.js")
WINDOW_ERRORS_SOURCE = Path(__file__).with_name("render-checks-init.js")
STANDALONE_FILE_ROUTE = "file:///_leaf/render-checks-standalone.js"

_PROBE_CACHE = "__leafRenderChecks"
_LOAD_PROBES = f"""async (call) => {{
  if (globalThis.{_PROBE_CACHE}?.route !== call.route) {{
    let timer;
    try {{
      const probes = await Promise.race([
        import(call.route),
        new Promise((_, reject) => {{
          timer = setTimeout(
            () => reject(new Error(
              `Leaf browser probes did not load from ${{call.route}} ` +
              `within ${{call.timeoutMs}}ms`
            )),
            call.timeoutMs,
          );
        }}),
      ]);
      globalThis.{_PROBE_CACHE} = {{route: call.route, probes}};
    }} finally {{
      clearTimeout(timer);
    }}
  }}
}}"""
_INVOKE_PROBE = f"""async (call) => {{
  await ({_LOAD_PROBES})(call);
  const probes = globalThis.{_PROBE_CACHE}.probes;
  const probe = probes[call.name];
  if (typeof probe !== "function")
    throw new TypeError(`unknown Leaf browser probe ${{call.name}}`);
  return probe(...call.args);
}}"""
_POLL_PROBE = f"""(call) => {{
  const probe = globalThis.{_PROBE_CACHE}?.probes?.[call.name];
  if (typeof probe !== "function")
    throw new TypeError(`unknown Leaf browser probe ${{call.name}}`);
  const result = probe(...call.args);
  if (result && typeof result.then === "function")
    throw new TypeError(
      `Leaf wait probe ${{call.name}} must be synchronous; ` +
      `publish a synchronous readiness fact instead`
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


def evaluate_probe(page, name: str, *args):
    """Invoke one named export from the browser probe module."""
    return page.evaluate(_INVOKE_PROBE, _call(page, name, args))


def wait_for_probe(page, name: str, *args) -> None:
    """Wait until one named browser probe returns a truthy value."""
    call = _call(page, name, args)
    page.evaluate(_LOAD_PROBES, call)
    page.wait_for_function(_POLL_PROBE, arg=call)


def install_window_errors(page) -> None:
    """Install the pre-navigation error channel shared by the gate and suite."""
    page.add_init_script(path=WINDOW_ERRORS_SOURCE)
