/* Registry-declared widget-local placements for canonical Thread views.

   A surface owns only the DOM geometry that seats a thread. Core owns which
   threads qualify, their retained rendering, and whether a local view suppresses
   the living-margin fallback. Adapter faults release that widget's core views
   and report through the page-error channel; they cannot stop other threads
   reconciling. Core rendering faults still fail the complete state application.

   With the panel closed, an exact projected-datum comment opens in a declared widget
   Thread surface when that widget supplies a visible outlet. A local surface uses the
   canonical Thread fold and core-owned controls; only its container and layout belong
   to the widget. Closing, filtering, or lazily withholding the datum removes the claim
   and restores the living-margin fallback. Deliberate travel may reveal or hydrate the
   datum, then runs the same reconciliation path to claim it. */
let publishedRegister;

export const registerThreadSurface = (...args) => {
  if (!publishedRegister)
    throw new Error("leaf: thread surfaces are unavailable before runtime setup");
  return publishedRegister(...args);
};

export function createThreadSurfaces({
  containsAcross,
  registry,
  renderThreadSurface,
  reportPageError,
  requestReconcile,
  setChildren,
}) {
  const registrations = new Map();
  let claimed = new Set();
  let reconcileQueued = false;

  function update() {
    if (reconcileQueued) return;
    reconcileQueued = true;
    queueMicrotask(() => {
      reconcileQueued = false;
      requestReconcile();
    });
  }

  function clearOutlets(outlets) {
    for (const outlet of outlets) {
      setChildren(outlet, []);
      delete outlet.dataset.lfThreadSurface;
    }
  }

  function reportFailure({ owner }, error) {
    reportPageError(
      `thread surface ${owner.localName}#${owner.id} failed: ${error?.message ?? error}`,
    );
  }

  function clearRegistration(registration) {
    try {
      registration.adapter.begin();
      registration.adapter.end();
    } catch (error) {
      reportFailure(registration, error);
    }
    clearOutlets(registration.outlets);
    registration.outlets.clear();
  }

  publishedRegister = (owner, adapter) => {
    if (!(owner instanceof Element))
      throw new TypeError("registerThreadSurface owner must be a widget element");
    if (registry[owner.localName]?.["x-thread-surface"] !== true)
      throw new Error(
        `registerThreadSurface(${owner.localName}) requires x-thread-surface: true`,
      );
    if (
      !adapter ||
      typeof adapter !== "object" ||
      typeof adapter.begin !== "function" ||
      typeof adapter.outletFor !== "function" ||
      typeof adapter.end !== "function"
    )
      throw new TypeError(
        "registerThreadSurface adapter needs begin, outletFor, and end functions",
      );
    if (registrations.has(owner))
      throw new Error(`registerThreadSurface(${owner.localName}) registered twice`);

    const registration = { adapter, owner, outlets: new Set() };
    registrations.set(owner, registration);
    update();
    let active = true;
    return {
      update,
      unregister() {
        if (!active) return;
        active = false;
        registrations.delete(owner);
        clearRegistration(registration);
        update();
      },
    };
  };

  function render(threads, placedAt) {
    const nextClaimed = new Set();
    for (const registration of [...registrations.values()]) {
      const { adapter, owner } = registration;
      if (registrations.get(owner) !== registration) continue;
      if (!owner.isConnected) {
        registrations.delete(owner);
        clearRegistration(registration);
        continue;
      }
      const byOutlet = new Map();
      try {
        adapter.begin();
        for (const thread of threads) {
          const anchor = thread.root.anchor;
          const placement = placedAt(thread.root.id);
          if (
            !anchor?.datum ||
            anchor.section !== owner.id ||
            placement?.status !== "exact" ||
            !(placement.datumElement instanceof Element) ||
            !containsAcross(owner, placement.datumElement)
          )
            continue;
          const outlet = adapter.outletFor({ anchor, placement, thread });
          if (!(outlet instanceof Element)) continue;
          const held = byOutlet.get(outlet) ?? [];
          held.push(thread);
          byOutlet.set(outlet, held);
        }
        adapter.end();
        if (registrations.get(owner) !== registration) continue;
        // end may move or detach an outlet. Claim only the finished layout.
        for (const outlet of byOutlet.keys()) {
          if (!outlet.isConnected) byOutlet.delete(outlet);
          else if (!containsAcross(owner, outlet))
            throw new Error(
              `registerThreadSurface(${owner.localName}) returned an outlet outside its widget`,
            );
        }
      } catch (error) {
        clearOutlets(registration.outlets);
        registration.outlets.clear();
        reportFailure(registration, error);
        continue;
      }
      clearOutlets([...registration.outlets].filter((outlet) => !byOutlet.has(outlet)));
      registration.outlets = new Set(byOutlet.keys());
      for (const [outlet, localThreads] of byOutlet) {
        // Core controls seated inside a widget are a nested interaction scope, not part
        // of that widget's shortcut surface. The keyboard register stops its ancestor
        // walk here while retaining scopes declared on the Thread controls themselves.
        outlet.dataset.lfThreadSurface = "";
        renderThreadSurface(outlet, localThreads);
        for (const thread of localThreads) nextClaimed.add(thread.root.id);
      }
    }
    claimed = nextClaimed;
    return claimed;
  }

  return {
    claimed: (id) => claimed.has(id),
    focus(id) {
      for (const registration of registrations.values()) {
        const root = registration.owner.shadowRoot ?? registration.owner;
        const thread = root.querySelector(
          `.lf-conversation-thread[data-thread="${CSS.escape(id)}"]`,
        );
        if (!thread) continue;
        const summary = thread.querySelector(":scope > summary");
        const target =
          (summary && !thread.hasAttribute("open") ? summary : null) ??
          thread.querySelector("textarea:not([disabled])") ??
          summary ??
          thread;
        target.focus({ preventScroll: true });
        target.scrollIntoView({ block: "nearest" });
        return target;
      }
      return null;
    },
    render,
  };
}
