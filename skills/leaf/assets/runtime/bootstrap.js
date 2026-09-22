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
  // What the profile says about a startup fault. A page that would not start is the one
  // reading nobody here can reproduce, so the record has to name the thing that did not
  // load. A fault the page recovers from is worth the name too, so the outcome that
  // eventually wins carries it rather than a separate record standing for it.
  let recordStartupFault = () => {};

  // A small public-site profile distinguishes server delay, browser paint, and Leaf
  // presentation. It starts here so failed module graphs report too.
  function observePublicStartup() {
    if (!release) return;
    let sent = false;
    let presentedMs = null;
    let fault = null;
    const rounded = (value) =>
      Number.isFinite(value) && value >= 0 ? Math.round(value) : null;
    const report = (outcome) => {
      if (sent) return;
      sent = true;
      observer.disconnect();
      const navigation = performance.getEntriesByType("navigation")[0];
      const paint = performance
        .getEntriesByName("first-contentful-paint", "paint")
        .at(0);
      navigator.sendBeacon(
        new URL(
          "api/performance",
          new URL(`${script.dataset.lfPageRoot}/`, location.origin),
        ),
        JSON.stringify({
          version: 1,
          loadId: crypto.randomUUID(),
          release,
          layer,
          outcome,
          ...(fault && { reason: String(fault).slice(0, 300) }),
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
    // The supervisor's own `lf-startup-failed` listener is registered before this
    // function runs, so a declared failure has already named its fault by the time
    // `failed` is reported here.
    window.addEventListener("lf-startup-failed", () => report("failed"), {
      once: true,
    });
    window.addEventListener("pagehide", () => report("abandoned"), { once: true });
    setTimeout(() => report("timeout"), 15000);
    recordStartupFault = (reason) => {
      fault ??= reason;
    };
  }

  // Reader-arranged workspaces are page geometry, so their saved shape must reach the
  // document before the module graph that builds their contents. The theme consumes
  // these provisional root facts; restoreReaderView replaces them with live state.
  try {
    const scope = root.hasAttribute("data-lf-contained") ? location.pathname : "";
    const tray = localStorage.getItem(scope + "lf-tray-slot-open");
    if (tray) root.dataset.lfRestoreTray = tray;
    else if (localStorage.getItem(scope + "lf-thread-panel-open") === "1")
      root.toggleAttribute("data-lf-restore-panel", true);

    const panelWidth = parseFloat(
      localStorage.getItem(scope + "lf-thread-panel-width"),
    );
    const trayWidth = parseFloat(localStorage.getItem(scope + "lf-tray-slot-width"));
    if (panelWidth)
      root.style.setProperty("--lf-thread-panel-choice", `${panelWidth}px`);
    if (trayWidth) root.style.setProperty("--lf-tray-slot-choice", `${trayWidth}px`);
  } catch {
    // A page that cannot remember still starts in the default arrangement.
  }

  // `awaits` is whether a replacement server would answer this fault. A resource the
  // page needs and does not have — its entry module, its theme — leaves it incomplete
  // however far it gets, and a page that declares it cannot start says so itself; both
  // wait, and the notice stands until a server that can start the page replaces this
  // one. An uncaught error in code that did load leaves nothing to wait for: the same
  // server would serve the same bytes, so if the page presents it has started with
  // everything it is going to get.
  function recover(reason, awaits = true) {
    root.dataset.lfStartupError = reason;
    recordStartupFault(reason);
    if (recovering) return;
    recovering = true;
    let started = false;
    const status = document.createElement("p");
    status.className = "lf-chrome";
    status.setAttribute("data-lf-runtime", "");
    status.setAttribute("role", "status");
    status.textContent = "Leaf couldn't start. Waiting for the server to update.";
    const show = () => {
      if (!started) document.body.prepend(status);
    };
    if (document.body) show();
    else document.addEventListener("DOMContentLoaded", show, { once: true });

    // The notice says the page has not started, and a page that presents has started,
    // so a reader who is using the page would otherwise be reading that Leaf could not
    // start, over a request a second that no answer ends.
    if (!awaits) {
      const presentation = new MutationObserver(() => {
        if (!document.body?.hasAttribute("data-lf-presented")) return;
        presentation.disconnect();
        started = true;
        status.remove();
      });
      presentation.observe(document, {
        attributes: true,
        attributeFilter: ["data-lf-presented"],
        childList: true,
        subtree: true,
      });
    }

    // A round carries what it learned to the end rather than acting where it learned
    // it. The round in flight when the page presents resolves after it, and the reader
    // is then using a page this would otherwise navigate out from under them, so the
    // one place that acts is the one place that has to ask whether the page started.
    const check = async () => {
      if (started) return;
      let restart = null;
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
            restart = () => location.replace(next);
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
          restart ??= () => location.reload();
        }
      } catch {
        // The stopped server has not been replaced yet.
      }
      if (started) return;
      if (restart) restart();
      else setTimeout(check, 1000);
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
        // A browser that treats the script as another origin gives "Script error." and
        // nothing else, so the file and line ride along: between them they are enough
        // to find the fault in a build nobody here can run.
        recover(
          `${event.message || "uncaught error"} (${event.filename || "?"}:${event.lineno ?? "?"})`,
          false,
        );
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
