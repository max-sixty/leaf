/* Playwright's document-side driver for Leaf's browser probes.
 *
 * The driver is an init script rather than page-authored code. It starts the probe
 * module without awaiting it, exposes bounded polling facts to Playwright, and keeps
 * every probe invocation synchronous so a stopped page cannot strand Python inside
 * `evaluate`. The pre-upgrade readings live here as well: they must run while the
 * Leaf entry is held, before the probe module and runtime exist, and a probe that
 * compares against them reads what they kept through `firstBoxes`. So do the rendering
 * waits, which hold on any page the driver runs in, a published capture that serves no
 * probes among them, and cost no module load. */
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

  let requestedFrame = 0;
  let presentedFrame = 0;

  // Ask the compositor for a rendering turn without handing page.evaluate a Promise
  // whose settlement depends on that turn. Playwright polls the synchronous fact
  // below, so its own deadline still runs when a stopped compositor never calls us
  // back. The turn counts as presented in a task queued from its animation-frame
  // callback, so it is the whole update: its layout, and the ResizeObserver deliveries
  // and loop notice that follow the callbacks.
  const requestFrame = () => {
    const requested = ++requestedFrame;
    requestAnimationFrame(() =>
      setTimeout(() => {
        presentedFrame = Math.max(presentedFrame, requested);
      }),
    );
    return requested;
  };
  const framePresented = (requested) => presentedFrame >= requested;

  // The runtime's settled reading for chrome and geometry (runtime/rendering.js):
  // nothing it queued for a rendering update is waiting and its last update was quiet.
  const renderingSettled = () => {
    const settled = document.querySelector("script[data-lf-entry]")?.lfRenderingSettled;
    if (!settled) throw new Error("this document has no Leaf rendering reading");
    return settled();
  };

  const themeReady = () =>
    [...document.styleSheets].some((sheet) => sheet.href?.endsWith("/theme.css"));

  // Each authored widget's border box as the page first paints it: the whole authored
  // document laid out under the theme, with the prepaint's `data-lf-interactive` on
  // the root and nothing upgraded. The element is kept, so a reading taken once the
  // page presents measures the same node (`changedBoxes` in widgets.js).
  let firstBoxes = Object.freeze([]);

  const preUpgradeFindings = () => {
    firstBoxes = Object.freeze(
      [...document.querySelectorAll("body > main *")]
        .filter((element) => element.localName.startsWith("lf-"))
        .map((element) => {
          const { width, height } = element.getBoundingClientRect();
          return Object.freeze({ element, width, height });
        }),
    );
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
    requestFrame,
    framePresented,
    renderingSettled,
    themeReady,
    preUpgradeFindings,
    firstBoxes: () => firstBoxes,
  });
})();
