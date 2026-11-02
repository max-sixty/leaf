/* Access to host-registered thread surfaces, without importing the page that seats
   threads. The placement owner in surfaces.js holds each registration's lifetime;
   widgets can keep a handle before registration or across departure and return.
   Without a registration there is nothing to update or release, and no opener to
   offer as a control. The opener is reactive across registration and retirement.
   A plain host has no Leaf placement owner to register a surface.
   Releasing outlets is synchronous: a widget must return the host's composer before
   removing the DOM that holds it. Composed containment includes shadow stages. */
import { under } from "../shadow-tree.js";
import { signal } from "/vendor/signals-core.js";
import { tick } from "../version-signal.js";

// The placement owner writes the registrations; accessors read this same directory.
/** @type {Map<Element, import("./surfaces.js").Registration>} */
export const registrations = new Map();
const registrationVersion = signal(0);

/** @param {Element} owner @param {import("./surfaces.js").Registration | null} registration */
export function setRegistration(owner, registration) {
  if (registration) registrations.set(owner, registration);
  else registrations.delete(owner);
  tick(registrationVersion);
}

/** @param {import("./surfaces.js").Registration} registration */
export function updateSurface(registration) {
  if (registration.reconcileQueued) return;
  registration.reconcileQueued = true;
  queueMicrotask(() => {
    registration.reconcileQueued = false;
    void registration.invalidate();
  });
}

// The registered surface of a widget declaring `x-thread-surface`, as the widget reads
// it: before the runtime has registered it, or after it left, there is nothing to update
// and nothing it can open.
/** @param {Element} owner */
export const threadSurface = (owner) =>
  Object.freeze({
    update() {
      const registration = registrations.get(owner);
      if (registration) updateSurface(registration);
    },
    get open() {
      registrationVersion.value;
      return registrations.get(owner)?.handle.open ?? null;
    },
  });

// A widget removes a node that may hold an outlet only through its placement's
// `onCommit`, or after this: core's composer, the one node it carries from outlet to
// outlet, leaves every outlet under `node` now, for where the next commit would put
// it once `node` is gone, so the removal cannot take the user's editor with it.
/** @param {Node} node */
export function releaseOutlets(node) {
  for (const { outlets, composition } of registrations.values()) {
    const outlet = composition.outlet();
    if (outlet && outlets.has(outlet) && under(outlet, node)) composition.restore();
  }
}
