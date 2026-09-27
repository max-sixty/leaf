/* Playwright's document-side driver for Leaf's browser probes.
 *
 * The driver is an init script rather than page-authored code. It starts the probe
 * module without awaiting it, exposes bounded polling facts to Playwright, and keeps
 * every probe invocation synchronous so a stopped page cannot strand Python inside
 * `evaluate`. The pre-upgrade readings live here as well: they must run while the
 * Leaf entry is held, before the probe module and runtime exist. */
(() => {
  if (globalThis.__leafRenderDriver) return;

  let loading = null;

  // The probe module is served beside the page's Leaf entry, so a page served under a
  // revision path loads that revision's probes.
  const resolve = (route) => {
    const entry = document.querySelector("script[data-lf-entry]")?.dataset.lfEntry;
    return entry ? new URL(route.slice(1), new URL(entry, location.href)).href : route;
  };

  // Start this document's probe load if it has not begun, and say whether the module
  // has arrived. A load that failed throws its error from here.
  const load = (route) => {
    const href = resolve(route);
    if (loading?.route !== href) {
      const current = { route: href, probes: null, error: null };
      loading = current;
      import(href).then(
        (probes) => {
          if (loading === current) current.probes = probes;
        },
        (error) => {
          if (loading === current)
            current.error = {
              name: error?.name ?? "Error",
              message: error?.message ?? String(error),
            };
        },
      );
    }
    if (loading.error) {
      const error = new Error(
        `Leaf browser probes failed to load from ${href}: ${loading.error.message}`,
      );
      error.name = loading.error.name;
      throw error;
    }
    return loading.probes !== null;
  };

  const call = (request) => {
    const probe = loading?.probes?.[request.name];
    if (typeof probe !== "function")
      throw new TypeError(`unknown Leaf browser probe ${request.name}`);
    const result = probe(...request.args);
    if (result && typeof result.then === "function")
      throw new TypeError(
        `Leaf browser probe ${request.name} must be synchronous; ` +
          "publish a synchronous reading or readiness fact instead",
      );
    return result;
  };

  const themeReady = () =>
    [...document.styleSheets].some((sheet) => sheet.href?.endsWith("/theme.css"));

  const preUpgradeFindings = () => {
    const main = document.querySelectorAll("body > main");
    const custom = [...document.querySelectorAll("*")]
      .map((element) => element.localName)
      .filter((tag) => tag.includes("-"));
    const upgraded = [...new Set(custom)].filter((tag) => customElements.get(tag));
    const painted = ["lf-upgraded", "lf-applied", "lf-presented"].filter((name) =>
      document.body.hasAttribute(`data-${name}`),
    );
    const box = main[0]?.getBoundingClientRect();
    return [
      ...(main.length === 1
        ? []
        : [`authored document has ${main.length} direct main elements`]),
      ...(upgraded.length
        ? [`widgets upgraded before Leaf entry ran: ${upgraded.join(", ")}`]
        : []),
      ...(painted.length
        ? [`runtime readiness appeared before Leaf entry ran: ${painted.join(", ")}`]
        : []),
      ...(!box || box.width <= 0 || box.height <= 0
        ? ["authored main has no measurable pre-upgrade layout"]
        : []),
    ];
  };

  globalThis.__leafRenderDriver = Object.freeze({
    load,
    call,
    themeReady,
    preUpgradeFindings,
  });
})();
