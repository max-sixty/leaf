// The server places this exact hashed script before any loadable page resource.
// It must run even when the entry module or one of its dependencies cannot load.
(() => {
  const arrived = new URL(location.href);
  // `_leaf-recovered` is the mark recovery puts on the one document it asks for, so a
  // document that comes back on the same dead release can tell that asking again is
  // not going to produce a different one. Both marks are the runtime's own and leave
  // the address bar before the reader sees them.
  const recovered = arrived.searchParams.has("_leaf-recovered");
  if (arrived.searchParams.has("_leaf-revision") || recovered) {
    arrived.searchParams.delete("_leaf-revision");
    arrived.searchParams.delete("_leaf-recovered");
    history.replaceState(history.state, "", arrived);
  }
  const script = document.currentScript;
  const root = document.documentElement;
  root.toggleAttribute("data-lf-live", true);
  const incarnation = script.dataset.lfServer;
  const layer = script.dataset.lfLayer;
  const release = script.dataset.lfRelease;
  const entry = new URL(script.dataset.lfEntry, location.href).href;
  const theme = new URL(script.dataset.lfTheme, location.href).href;
  let recovering = false;
  // What the profile says when startup fails. A page that never starts is the one
  // reading nobody can reproduce from a desk, so the record has to name the thing that
  // did not load rather than only that the page gave up waiting for it.
  let reportStartupFailure = () => {};

  // A small public-site profile distinguishes server delay, browser paint, and Leaf
  // presentation. It starts here so failed module graphs report too.
  function observePublicStartup() {
    if (!release) return;
    let sent = false;
    let presentedMs = null;
    const rounded = (value) =>
      Number.isFinite(value) && value >= 0 ? Math.round(value) : null;
    const report = (outcome, reason = null) => {
      if (sent) return;
      sent = true;
      observer.disconnect();
      const navigation = performance.getEntriesByType("navigation")[0];
      const paint = performance
        .getEntriesByName("first-contentful-paint", "paint")
        .at(0);
      navigator.sendBeacon(
        "/api/performance",
        JSON.stringify({
          version: 1,
          loadId: crypto.randomUUID(),
          release,
          layer,
          outcome,
          ...(reason && { reason: String(reason).slice(0, 300) }),
          navigationType: navigation?.type ?? "unknown",
          serverMs: rounded(
            navigation?.serverTiming?.find((entry) => entry.name === "leaf")?.duration,
          ),
          firstByteMs: rounded(navigation?.responseStart),
          firstContentfulPaintMs: rounded(paint?.startTime),
          presentedMs,
        }),
      );
    };
    const observer = new MutationObserver(() => {
      if (!document.body?.hasAttribute("data-lf-presented")) return;
      observer.disconnect();
      presentedMs = Math.round(performance.now());
      const afterLoad = () => setTimeout(() => report("presented"));
      if (document.readyState === "complete") afterLoad();
      else window.addEventListener("load", afterLoad, { once: true });
    });
    observer.observe(document, {
      attributes: true,
      attributeFilter: ["data-lf-presented"],
      childList: true,
      subtree: true,
    });
    window.addEventListener("pagehide", () => report("abandoned"), { once: true });
    setTimeout(() => report("timeout"), 15000);
    reportStartupFailure = (reason) => report("failed", reason);
  }

  // Reader-arranged workspaces are page geometry, so their saved shape must reach the
  // document before the module graph that builds their contents. The theme consumes
  // these provisional root facts; restoreReaderView replaces them with live state.
  try {
    const tray = localStorage.getItem("lf-tray-slot-open");
    if (tray) root.dataset.lfRestoreTray = tray;
    else if (localStorage.getItem("lf-thread-panel-open") === "1")
      root.toggleAttribute("data-lf-restore-panel", true);

    const panelWidth = parseFloat(localStorage.getItem("lf-thread-panel-width"));
    const trayWidth = parseFloat(localStorage.getItem("lf-tray-slot-width"));
    if (panelWidth)
      root.style.setProperty("--lf-thread-panel-choice", `${panelWidth}px`);
    if (trayWidth) root.style.setProperty("--lf-tray-slot-choice", `${trayWidth}px`);
  } catch {
    // A page that cannot remember still starts in the default arrangement.
  }

  function recover(reason) {
    if (recovering) return;
    recovering = true;
    reportStartupFailure(reason);
    const show = () => {
      const status = document.createElement("p");
      status.className = "lf-chrome";
      status.setAttribute("data-lf-runtime", "");
      status.setAttribute("role", "status");
      status.textContent = "Leaf couldn't start. Waiting for the server to update.";
      document.body.prepend(status);
    };
    if (document.body) show();
    else document.addEventListener("DOMContentLoaded", show, { once: true });

    const check = async () => {
      try {
        const response = await fetch(script.dataset.lfProbe, { cache: "no-store" });
        if (response.status === 404) {
          // The release this document names is gone, so nothing this document can load
          // will come back and only a newer one can start the page. Ask for it once,
          // marked, and past a cache that answered the address the reader typed. A
          // marked document that arrives still naming the dead release says something
          // between here and the source is serving a copy of it; asking again lands on
          // that same copy as fast as the network allows, so the page waits on the
          // probe at the cadence every other unstarted page waits at.
          if (release && !recovered) {
            const next = new URL(location.href);
            next.searchParams.set("_leaf-recovered", "");
            location.replace(next);
            return;
          }
        }
        const current = response.headers.get("Leaf-Server");
        let generation = response.headers.get("Leaf-Layer");
        const currentRelease = response.headers.get("Leaf-Release");
        if (!generation && response.ok) {
          try {
            generation = (await response.json())?.["$layer"]?.generation;
          } catch {
            // A non-registry probe can still identify itself through headers.
          }
        }
        if (
          (current && current !== incarnation) ||
          (generation && generation !== layer) ||
          (release && currentRelease && currentRelease !== release)
        ) {
          location.reload();
          return;
        }
      } catch {
        // The stopped server has not been replaced yet.
      }
      setTimeout(check, 1000);
    };
    void check();
  }

  window.addEventListener(
    "error",
    (event) => {
      const target = event.target;
      if (target instanceof HTMLScriptElement && target.src === entry)
        recover("entry module did not load");
      else if (target instanceof HTMLLinkElement && target.href === theme)
        recover("theme stylesheet did not load");
      else if (target === window && !document.body?.hasAttribute("data-lf-presented"))
        recover(event.message || "uncaught error before presentation");
    },
    true,
  );
  window.addEventListener("lf-startup-failed", (event) =>
    recover(event.detail?.reason || "the page reported it could not start"),
  );
  try {
    observePublicStartup();
  } catch {
    // Optional website diagnostics must never take startup supervision down with them.
  }
})();
