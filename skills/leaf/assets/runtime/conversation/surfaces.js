/* Registry-declared widget-local placements for canonical Thread views.

   A surface owns only the DOM geometry that seats a thread. Core owns which
   threads qualify, their retained rendering, and whether a local view suppresses
   the living-margin fallback. */
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
  requestReconcile,
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

  function clearRegistration(registration) {
    registration.adapter.begin();
    registration.adapter.end();
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

    const registration = { adapter, owner };
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
      if (!owner.isConnected) {
        registrations.delete(owner);
        clearRegistration(registration);
        continue;
      }
      adapter.begin();
      const byOutlet = new Map();
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
        if (!containsAcross(owner, outlet))
          throw new Error(
            `registerThreadSurface(${owner.localName}) returned an outlet outside its widget`,
          );
        // Core controls seated inside a widget are a nested interaction scope, not part
        // of that widget's shortcut surface. The keyboard register stops its ancestor
        // walk here while retaining scopes declared on the Thread controls themselves.
        outlet.dataset.lfThreadSurface = "";
        const held = byOutlet.get(outlet) ?? [];
        held.push(thread);
        byOutlet.set(outlet, held);
        nextClaimed.add(thread.root.id);
      }
      adapter.end();
      for (const [outlet, localThreads] of byOutlet)
        if (outlet.isConnected) renderThreadSurface(outlet, localThreads);
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
