// The server places this exact hashed script before any loadable page resource.
// It must run even when the entry module or one of its dependencies cannot load.
(() => {
  const arrived = new URL(location.href);
  // `_leaf-recovered` is the mark recovery puts on the one document it asks for, so a
  // document that comes back on the same dead release can tell that asking again is
  // not going to produce a different one. Both marks are the runtime's own and leave
  // the address bar before the user sees them.
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
  let stopHoldingKeys = () => {};

  // A page key pressed before the page presents would otherwise reach a runtime that has
  // not loaded, or one that has not yet read the log: `t` walks the threads the first
  // state answer brings, so until then it walks nothing. The keys wait here instead, in
  // the order pressed, until the presented page takes them. What is held is a run of
  // printed keys: one pressed on the page starts it, and every printed key after it
  // joins. Any other key ends the run, and so does a pointer press, which puts the user
  // somewhere the keys were not aimed at: what was held is dropped and the new press
  // keeps its own meaning. A modified key is the browser's, and a modifier alone is half
  // a press. After a beat the held keys are shown, so a press visibly landed; a page that
  // presents within the beat shows nothing.
  const HALF_PRESSES = new Set([
    "Shift",
    "Control",
    "Alt",
    "AltGraph",
    "Meta",
    "CapsLock",
  ]);
  function holdEarlyKeys() {
    const held = [];
    let taken = false;
    let beat = 0;
    const echo = document.createElement("p");
    echo.className = "lf-held-keys";
    echo.setAttribute("data-lf-runtime", "");
    echo.setAttribute("role", "status");
    const show = () => {
      const keys = held.map(({ key }) => {
        const badge = document.createElement("kbd");
        badge.className = "lf-key-badge";
        badge.textContent = key === " " ? "Space" : key;
        return badge;
      });
      echo.replaceChildren(
        "Page still loading —",
        ...keys,
        keys.length === 1 ? "runs when it's ready" : "run when it's ready",
      );
      if (!echo.isConnected) document.body?.append(echo);
    };
    const letGo = () => {
      held.length = 0;
      clearTimeout(beat);
      beat = 0;
      echo.remove();
    };
    const queue = (event) => {
      if (event.repeat) return;
      held.push(event);
      if (taken) return;
      if (echo.isConnected) show();
      else beat ||= setTimeout(show, 150);
    };
    const hold = (event) => {
      if (event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
      if (HALF_PRESSES.has(event.key)) return;
      const printed = event.key.length === 1;
      if (held.length || taken) {
        // The run is open, so a printed key follows the keys before it wherever it was
        // typed: a held `c` may yet open the box the rest is text for. Any other key
        // ends the run and keeps its own meaning: Enter, Backspace, Tab or an arrow acts
        // natively where focus stands, which a replay through the keyboard owner cannot
        // reproduce.
        if (!printed) {
          letGo();
          return;
        }
        queue(event);
      } else {
        // Only a printed page key starts a run. One typed into a field is the field's,
        // and Space on its own scrolls.
        const origin = event.composedPath()[0];
        const typing =
          origin instanceof Element &&
          (origin.isContentEditable || origin.matches("input, textarea, select"));
        if (typing || !printed || event.key === " ") return;
        queue(event);
      }
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    const pointed = () => letGo();
    // The page is ready, so the notice comes down, but the hold stands until the keyboard
    // owner has pressed the last key in it: a printed key pressed meanwhile joins the
    // same run rather than running ahead of the keys pressed before it.
    const take = (event) => {
      taken = true;
      clearTimeout(limit);
      clearTimeout(beat);
      echo.remove();
      event.detail.keys = held;
      event.detail.release = () => stopHoldingKeys();
    };
    // A page that has not presented by now is not loading but faulted, and a key held
    // this long is one the user has given up on: the hold ends, what it held is
    // dropped, and keys reach the runtime as they come.
    const limit = setTimeout(() => stopHoldingKeys(), 10_000);
    stopHoldingKeys = () => {
      window.removeEventListener("keydown", hold, true);
      window.removeEventListener("pointerdown", pointed, true);
      document.removeEventListener("lf-held-keys", take);
      clearTimeout(limit);
      letGo();
    };
    window.addEventListener("keydown", hold, true);
    window.addEventListener("pointerdown", pointed, true);
    // The keyboard owner takes the held keys once the page presents and runs them through
    // its own handler (runtime/keyboard/controller.js).
    document.addEventListener("lf-held-keys", take);
  }

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
    stopHoldingKeys();
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
    // so a user who is using the page would otherwise be reading that Leaf could not
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
    // it. The round in flight when the page presents resolves after it, and the user
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
          // marked, and past a cache that answered the address the user typed. A
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
  holdEarlyKeys();
  try {
    observePublicStartup();
  } catch {
    // Optional website diagnostics must never take startup supervision down with them.
  }
})();
