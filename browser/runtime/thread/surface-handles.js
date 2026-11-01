/* Access to host-registered thread surfaces, without importing the page that seats
   threads. The placement owner in surfaces.js holds each registration's lifetime;
   widgets can keep a handle before registration or across departure and return.
   Without a registration there is nothing to update, open or release. This is the
   same interface on a plain host, where no Leaf placement owner registers a surface.
   Releasing outlets is synchronous: a widget must return the host's composer before
   removing the DOM that holds it. Composed containment includes shadow stages. */
import { under } from "../shadow-tree.js";

// The placement owner writes the registrations; accessors read this same directory.
export const registrations = new Map();

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
export const threadSurface = (owner) =>
  Object.freeze({
    update() {
      const registration = registrations.get(owner);
      if (registration) updateSurface(registration);
    },
    open: (node) => registrations.get(owner)?.handle.open(node) ?? false,
  });

// A widget removes a node that may hold an outlet only through its placement's
// `onCommit`, or after this: core's composer, the one node it carries from outlet to
// outlet, leaves every outlet under `node` now, for where the next commit would put
// it once `node` is gone, so the removal cannot take the user's editor with it.
export function releaseOutlets(node) {
  for (const { outlets, composition } of registrations.values()) {
    const outlet = composition.outlet();
    if (outlets.has(outlet) && under(outlet, node)) composition.restore();
  }
}
