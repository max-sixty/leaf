/* Playwright's document-side driver for Leaf's browser probes.
 *
 * The driver is an init script rather than page-authored code. It starts the probe
 * module without awaiting it, exposes bounded polling facts to Playwright, and keeps
 * every probe invocation synchronous so a stopped page cannot strand Python inside
 * `evaluate`. Rendering waits hold on every document the driver runs in and
 * require no probe module load. */
(() => {
  if (globalThis.__leafRenderDriver) return;

  let loading = null;
  // The platform records visible movement from parsing through the first settled
  // presentation. Later interactive checks have their own gesture observations.
  const startupShifts = [];
  const shiftObserver = new PerformanceObserver((list) => {
    startupShifts.push(...list.getEntries());
  });
  if (PerformanceObserver.supportedEntryTypes.includes("layout-shift"))
    shiftObserver.observe({ type: "layout-shift", buffered: true });
  const startupLayoutShifts = () => {
    startupShifts.push(...shiftObserver.takeRecords());
    shiftObserver.disconnect();
    return startupShifts.filter((entry) => !entry.hadRecentInput);
  };

  // The probe module is served beside the page's Leaf entry, so a page served under a
  // revision path loads that revision's probes.
  const resolve = (route) => {
    const entry = /** @type {HTMLScriptElement | null} */ (
      document.querySelector("script[data-lf-entry]")
    )?.dataset.lfEntry;
    return entry ? new URL(route.slice(1), new URL(entry, location.href)).href : route;
  };

  // Start this document's probe load if it has not begun, and say whether the module
  // has arrived. A failed load throws its error from here.
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
          if (loading === current) current.error = { reason: error };
        },
      );
    }
    // No runtime formatter can load when the probe module itself failed. Preserve
    // the native import exception, whose stack names the actual failing module.
    if (loading.error) throw loading.error.reason;
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
  // back. The turn counts as presented in a task queued from an IntersectionObserver
  // the animation-frame callback starts, so it is the whole update: its layout, the
  // ResizeObserver deliveries and loop notice that follow the callbacks, and the
  // update's IntersectionObserver deliveries, which Chrome and Firefox run in a task of
  // their own after a task queued from the animation frame itself. Observed from the
  // animation frame, the new observer's first notice is computed in that same update
  // and delivered with every other observer's.
  const requestFrame = () => {
    const requested = ++requestedFrame;
    requestAnimationFrame(() => {
      const delivered = new IntersectionObserver(() => {
        delivered.disconnect();
        setTimeout(() => {
          presentedFrame = Math.max(presentedFrame, requested);
        });
      });
      delivered.observe(document.documentElement);
    });
    return requested;
  };
  const framePresented = (requested) => presentedFrame >= requested;

  // The runtime's rendering facts for chrome and geometry (runtime/rendering.js).
  // Readers select quiet updates or require every preparation to have landed too.
  const renderingState = () => {
    const read = /** @type {HTMLScriptElement | null} */ (
      document.querySelector("script[data-lf-entry]")
    )?.lfRenderingState;
    if (!read) throw new Error("this document has no Leaf rendering reading");
    return read();
  };

  // Widget-quality comparison holds the entry while these authored boxes are laid
  // out. Retain the actual nodes so the final reading compares the same instances.
  let firstBoxes = [];
  const captureFirstBoxes = () => {
    firstBoxes = [...document.querySelectorAll("body > main *")]
      .filter((element) => element.localName.startsWith("lf-"))
      .map((element) => {
        const { width, height } = element.getBoundingClientRect();
        return { element, width, height };
      });
  };

  globalThis.__leafRenderDriver = Object.freeze({
    load,
    call,
    requestFrame,
    framePresented,
    renderingState,
    startupLayoutShifts,
    captureFirstBoxes,
    firstBoxes: () => firstBoxes,
  });
})();
