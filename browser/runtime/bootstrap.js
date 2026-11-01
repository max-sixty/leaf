// The server places this script before any loadable page resource.
// It must run even when the entry module or one of its dependencies cannot load.
(() => {
  const arrived = new URL(location.href);
  // `_leaf-recovered` is the mark recovery puts on the one document it asks for, so a
  // document that comes back on the same dead release can tell that asking again is
  // not going to produce a different one. `t` is the host key a handover link carries;
  // the server has already answered it with the cookie every later request rides on,
  // so what stays in the address bar is a link the user can copy, share, or screen
  // without handing out every page on the machine. All three leave before the user
  // sees them.
  const recovered = arrived.searchParams.has("_leaf-recovered");
  const marks = ["_leaf-revision", "_leaf-recovered", "t"];
  if (marks.some((mark) => arrived.searchParams.has(mark))) {
    for (const mark of marks) arrived.searchParams.delete(mark);
    history.replaceState(history.state, "", arrived);
  }
  const script = (() => {
    const entry = document.currentScript;
    if (!(entry instanceof HTMLScriptElement))
      throw new Error("The Leaf bootstrap needs its HTML script entry");
    return entry;
  })();
  const root = document.documentElement;
  // runtime/ids.js's randomId, which this classic script cannot import: a sample
  // child served by `leaf --host` over plain HTTP has no crypto.randomUUID, nor does a
  // site build served that way.
  const randomId = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
  // A framed document places focus only while it holds input (focus.js,
  // `canPlaceFocus`). Aim cancels native mousedown focus and places its editor after
  // layout, so a trusted input enters the browsing context before those handlers run.
  if (window !== window.top) {
    const nativeWindowFocus = window.focus;
    const enterFrame = /** @param {Event} event */ (event) => {
      if (event.isTrusted && !document.hasFocus()) nativeWindowFocus.call(window);
    };
    for (const type of ["pointerdown", "keydown"])
      window.addEventListener(type, enterFrame, true);
  }
  // The sample URL grants this document its own server operations. An opaque
  // origin keeps it out of its parent's DOM and storage; native network APIs keep
  // their ordinary browser behavior. Only presentation values use the private port.
  if (root.hasAttribute("data-lf-sample")) {
    if (window.lfSampleBridge) {
      root.lfSample = window.lfSampleBridge;
      root.lfSample.install();
    } else {
      /** @type {{port: MessagePort, settings: import("./sample-protocol.js").SampleSettings} | null} */
      let connection = null;
      /** @type {PromiseWithResolvers<void>} */
      const { promise: ready, resolve: readyResolve } = Promise.withResolvers();
      /** @type {import("./sample-protocol.js").ChildMessage[]} */
      const queued = [];
      /** @type {Set<(message: import("./sample-protocol.js").ParentMessage) => void>} */
      const listeners = new Set();
      /** @param {import("./sample-protocol.js").ChildMessage} value */
      const send = (value) =>
        connection ? connection.port.postMessage(value) : queued.push(value);
      /** @type {LeafSampleBridge} */
      const bridge = {
        ready,
        get settings() {
          if (!connection) throw new Error("The sample private port is not connected");
          return connection.settings;
        },
        send,
        install() {
          const root = document.documentElement;
          window.lfRootState.setRuntimeRootAttribute(
            root,
            "data-lf-sample-block",
            bridge.settings.window ? null : "",
          );
          dress(worn);
        },
        receive: (callback) => listeners.add(callback),
        present() {
          window.lfRootState.setRuntimeRootAttribute(document.body, "inert", null);
        },
      };
      root.lfSample = bridge;
      window.lfSampleBridge = bridge;
      /** @type {LeafDress} */
      let worn = { attributes: {}, properties: {} };
      /** @param {LeafDress} [next] */
      const dress = (next = { attributes: {}, properties: {} }) => {
        const root = document.documentElement;
        window.lfRootState.wear(root, next);
        worn = next;
      };
      const sample = new URL(`${script.dataset.lfPageRoot}/`, location.origin).pathname;
      const nonce = randomId();
      /** @param {MessageEvent<import("./sample-protocol.js").SampleOffer | undefined>} event */
      const connect = (event) => {
        const port = event.ports[0];
        if (
          event.source !== window.parent ||
          event.data?.sample !== sample ||
          event.data.nonce !== nonce ||
          !port
        )
          return;
        window.removeEventListener("message", connect);
        const settings = event.data.settings;
        connection = { port, settings };
        // The bootstrap element owns diagnostic readings before the entry starts.
        script.lfDocumentPort = port;
        port.onmessage =
          /** @param {MessageEvent<import("./sample-protocol.js").ParentMessage>} event */ ({
            data,
          }) => {
            if (data.type === "dress") dress(data.detail);
            else for (const callback of listeners) callback(data);
          };
        port.postMessage({ type: "connected", nonce });
        bridge.install();
        dress(settings.dress);
        window.lfRootState.setRuntimeRootAttribute(
          root,
          "data-lf-sample-connecting",
          null,
        );
        readyResolve();
        for (const value of queued.splice(0)) port.postMessage(value);
      };
      // What the document wears, its dress and whether it stands as a block, comes in
      // the containing page's answer, which can land frames after the document could
      // first paint. Until it does the document paints nothing (base.css), so no frame
      // shows a playground's candidate undressed. Opened as a window of its own, it
      // has no containing page to answer and paints at once.
      if (window.parent !== window)
        window.lfRootState.setRuntimeRootAttribute(
          root,
          "data-lf-sample-connecting",
          "",
        );
      window.addEventListener("message", connect);
      window.parent.postMessage({ type: "leaf-sample-connect", sample, nonce }, "*");
      // A frame's own navigation never keeps its document in the page cache, so a
      // persisted pagehide is the containing page's, which takes this document and
      // its port along and brings both back together (sample.js keeps the host then).
      window.addEventListener("pagehide", (event) => {
        if (!event.persisted) send({ type: "departed" });
      });
    }
    const sampleBridge = root.lfSample;
    window.addEventListener("lf-startup-failed", () =>
      window.lfDocumentLifetime.whenActive("sample error", () =>
        sampleBridge.send({
          type: "error",
          detail: root.lfStartupException ?? {
            message:
              document.documentElement.dataset.lfStartupError ||
              "Sample could not start",
          },
        }),
      ),
    );
  }
  // A served page draws the live chrome, the floating panel, so the theme reserves its room from the first paint (`html[data-lf-live]`). An export runs the
  // runtime without them (prepaint.js).
  root.toggleAttribute("data-lf-live", true);
  const incarnation = script.dataset.lfServer;
  const layer = script.dataset.lfLayer;
  const release = script.dataset.lfRelease;
  let recovering = false;
  // What the profile says about a startup fault. A page that would not start is the one
  // reading nobody here can reproduce, so the record has to name the thing that did not
  // load. A fault the page recovers from is worth the name too, so the outcome that
  // eventually wins carries it rather than a separate record standing for it.
  /** @type {(reason: string) => void} */
  let recordStartupFault = () => {};
  let stopHoldingKeys = () => {};

  // A page key pressed before upgrade would reach a runtime that has not loaded.
  // Upgrade hands the queue to the dispatcher, whose command readiness may retain
  // keys that need private history. What is held is a run of printed keys: one
  // pressed on the page starts it, and every printed key after it
  // joins. Any other key ends the run, and so does a pointer press, which puts the user
  // somewhere the keys were not aimed at: what was held is dropped and the new press
  // keeps its own meaning. A chord never starts a run, and a modifier alone is half a
  // press, which neither starts nor ends one. After a beat the held keys are shown, so a
  // press visibly landed; a runtime that takes the run within the beat shows nothing.
  const { takesLetters } = window.lfInputs;
  const HALF_PRESSES = new Set([
    "Shift",
    "Control",
    "Alt",
    "AltGraph",
    "Meta",
    "CapsLock",
  ]);
  function holdEarlyKeys() {
    /** @type {KeyboardEvent[]} */
    const held = [];
    let taken = false;
    /** @type {((event: KeyboardEvent) => boolean) | null} */
    let ready = null;
    /** @type {(() => boolean) | null} */
    let keep = null;
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
      // After the chrome's root, which it ties with (base.css, `.lf-held-keys`).
      if (!echo.isConnected) document.documentElement.append(echo);
    };
    const letGo = () => {
      held.length = 0;
      clearTimeout(beat);
      beat = 0;
      echo.remove();
    };
    /** @param {KeyboardEvent} event */
    const queue = (event) => {
      if (event.repeat) return;
      held.push(event);
      if (taken) return;
      if (echo.isConnected) show();
      else beat ||= setTimeout(show, 150);
    };
    /** @param {KeyboardEvent} event */
    const hold = (event) => {
      if (!window.lfKeyboard.quick) return letGo();
      if (event.isComposing || HALF_PRESSES.has(event.key)) return;
      // Shift chooses which character prints; Ctrl, Alt and Meta make a chord instead.
      const printed =
        event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey;
      if (held.length || taken) {
        // The run is open, so a printed key follows the keys before it wherever it was
        // typed: a held `c` may yet open the box the rest is text for. Any other key
        // ends the run and keeps its own meaning: Enter, Backspace, Tab, an arrow or a
        // chord acts natively where focus stands, which a replay through the keyboard
        // owner cannot reproduce, and must not act ahead of keys pressed before it.
        if (!printed) {
          letGo();
          return;
        }
        queue(event);
      } else {
        // Only a printed page key starts a run. One typed into a field is the field's,
        // and Space on its own scrolls. The prepaint's `takesLetters` is also the
        // runtime's rule, so a checkbox or radio, which takes no letters,
        // holds the key as the presented page would act on it. `leaf-text` is the
        // runtime's text field; its closed root makes the host the event's origin.
        const origin = event.composedPath()[0];
        const typing = origin instanceof Element && takesLetters(origin);
        if (typing || !printed || event.key === " ") return;
        // Once the document upgrades, the dispatcher supplies readiness from
        // command declarations. Useful page keys pass immediately; only a key
        // whose input is still loading starts another ordered run.
        if (ready?.(event)) return;
        queue(event);
      }
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    const pointed = () => letGo();
    // The controller takes a run, so the notice comes down, but the hold stands until its
    // owner has pressed the last key in it: a printed key pressed meanwhile joins the
    // same run rather than running ahead of the keys pressed before it.
    /** @param {DocumentEventMap["lf-held-keys"]} event */
    const take = (event) => {
      ready = event.detail.ready;
      keep = event.detail.keep;
      clearTimeout(limit);
      if (!held.length) {
        if (!keep?.()) stopHoldingKeys();
        return;
      }
      taken = true;
      clearTimeout(beat);
      echo.remove();
      event.detail.keys = held;
      event.detail.pause = () => {
        taken = false;
        if (!keep?.()) return stopHoldingKeys();
        if (held.length) show();
      };
      event.detail.release = () => {
        taken = false;
        if (!keep?.()) stopHoldingKeys();
      };
    };
    // A page that has not upgraded by now is not loading but faulted, and a key held
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
    // The keyboard owner takes the held keys as the document upgrades and runs them through
    // its own handler (runtime/keyboard/controller.js).
    document.addEventListener("lf-held-keys", take);
  }

  // A small public-site profile separates browser upgrade from the first state
  // response and authoritative presentation. Failed module graphs report too.
  function observePublicStartup() {
    if (!release) return;
    let sent = false;
    /** @type {number | null} */
    let upgradedMs = null;
    /** @type {number | null} */
    let firstStateResponseMs = null;
    /** @type {number | null} */
    let presentedMs = null;
    /** @type {string | null} */
    let fault = null;
    /** @param {number | undefined} value */
    const rounded = (value) =>
      value !== undefined && Number.isFinite(value) && value >= 0
        ? Math.round(value)
        : null;
    const pageRoot = new URL(`${script.dataset.lfPageRoot}/`, location.origin);
    const stateUrl = new URL("api/state", pageRoot);
    /** @param {readonly PerformanceEntry[]} entries */
    const readStateResponses = (entries) => {
      for (const entry of entries) {
        if (!(entry instanceof PerformanceResourceTiming)) continue;
        const url = new URL(entry.name);
        if (
          url.origin !== stateUrl.origin ||
          url.pathname !== stateUrl.pathname ||
          entry.responseStart <= 0 ||
          entry.responseEnd <= 0
        )
          continue;
        const ended = Math.round(entry.responseEnd);
        firstStateResponseMs =
          firstStateResponseMs === null ? ended : Math.min(firstStateResponseMs, ended);
      }
    };
    // Observe completions as they arrive: the global resource timeline can fill
    // before state answers, and reading it only at presentation would lose this fact.
    const resources = new PerformanceObserver((list) => {
      readStateResponses(list.getEntries());
    });
    resources.observe({ type: "resource", buffered: true });
    const readMilestones = () => {
      if (upgradedMs === null && document.body?.hasAttribute("data-lf-upgraded"))
        upgradedMs = rounded(performance.now());
      if (presentedMs === null && document.body?.hasAttribute("data-lf-presented"))
        presentedMs = rounded(performance.now());
    };
    /** @param {"presented" | "failed" | "abandoned" | "timeout"} outcome */
    const report = (outcome) => {
      if (sent) return;
      sent = true;
      readMilestones();
      observer.disconnect();
      readStateResponses(resources.takeRecords());
      resources.disconnect();
      const navigation = performance
        .getEntriesByType("navigation")
        .find((entry) => entry instanceof PerformanceNavigationTiming);
      const paint = performance
        .getEntriesByName("first-contentful-paint", "paint")
        .at(0);
      void fetch(new URL("api/performance", pageRoot), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        keepalive: true,
        body: JSON.stringify({
          loadId: randomId(),
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
          upgradedMs,
          firstStateResponseMs,
          presentedMs,
        }),
      }).catch(() => {});
    };
    const observer = new MutationObserver(() => {
      readMilestones();
      if (presentedMs === null) return;
      observer.disconnect();
      const afterLoad = () => setTimeout(() => report("presented"));
      if (document.readyState === "complete") afterLoad();
      else window.addEventListener("load", afterLoad, { once: true });
    });
    observer.observe(document, {
      attributes: true,
      attributeFilter: ["data-lf-upgraded", "data-lf-presented"],
      childList: true,
      subtree: true,
    });
    // The prepaint's `lf-startup-failed` listener runs before this one, since the
    // prepaint runs first, so a declared failure has already named its fault by the
    // time `failed` is reported here.
    window.addEventListener("lf-startup-failed", () => report("failed"), {
      once: true,
    });
    window.addEventListener("pagehide", () => report("abandoned"), { once: true });
    setTimeout(() => {
      readMilestones();
      // A usable interface may still be waiting on a healthy state read. Its
      // eventual answer or departure closes the authoritative profile.
      if (upgradedMs === null) report("timeout");
    }, 15000);
    recordStartupFault = (reason) => {
      fault ??= reason;
    };
  }

  // `awaits` is whether a replacement server would answer this fault, which is so
  // where the page is incomplete (prepaint.js): it lacks something it needs however
  // far it gets, so the notice stands until a server that can start the page replaces
  // this one. An uncaught error in code that did load leaves nothing to wait for: the
  // same server would serve the same bytes, so if the page upgrades it has started
  // with everything it is going to get. A fault that is the page's own (`page`) is
  // answered by no server: the page holds what its author wrote, so the notice says
  // the page has a problem and waits for nothing.
  /** @param {string} reason @param {boolean} awaits @param {boolean} page */
  function recover(reason, awaits, page) {
    recordStartupFault(reason);
    stopHoldingKeys();
    if (recovering) return;
    recovering = true;
    let started = false;
    const status = document.createElement("p");
    status.className = "lf-chrome";
    status.setAttribute("data-lf-runtime", "");
    status.setAttribute("role", "status");
    status.textContent = page
      ? "Leaf couldn't start: this page has a problem its author needs to fix."
      : "Leaf couldn't start. Waiting for Leaf to update.";
    const show = () => {
      if (!started) document.body.prepend(status);
    };
    if (document.body) show();
    else document.addEventListener("DOMContentLoaded", show, { once: true });
    if (page) return;

    // The notice says the page has not started, and a page that upgrades has started,
    // so a user who is using the page would otherwise be reading that Leaf could not
    // start, over a request a second that no answer ends.
    if (!awaits) {
      const upgrade = new MutationObserver(() => {
        if (!document.body?.hasAttribute("data-lf-upgraded")) return;
        upgrade.disconnect();
        started = true;
        status.remove();
      });
      upgrade.observe(document, {
        attributes: true,
        attributeFilter: ["data-lf-upgraded"],
        childList: true,
        subtree: true,
      });
    }

    // A round carries what it learned to the end rather than acting where it learned
    // it. The round in flight when the page upgrades resolves after it, and the user
    // is then using a page this would otherwise navigate out from under them, so the
    // one place that acts is the one place that has to ask whether the page started.
    const check = async () => {
      if (started) return;
      let restart = null;
      try {
        const probe = script.getAttribute("data-lf-probe");
        if (probe === null)
          throw new Error("Startup recovery requires its delivery probe");
        const response = await fetch(probe, { cache: "no-store" });
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
        const generation = response.headers.get("Leaf-Layer");
        const currentRelease = response.headers.get("Leaf-Release");
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

  // The prepaint names each startup fault and marks the page for it (prepaint.js).
  window.addEventListener("lf-startup-fault", (event) =>
    recover(event.detail.reason, event.detail.incomplete, event.detail.page),
  );
  holdEarlyKeys();
  try {
    observePublicStartup();
  } catch {
    // Optional website diagnostics must never take startup supervision down with them.
  }
})();
