// Compiled from surface-handles.ts by build/typescript.mjs; edit that file.
/* Access to host-registered thread surfaces, without importing the page that seats
   threads. The placement owner in surfaces.js holds each registration's lifetime;
   widgets can keep a handle before registration or across departure and return.
   Without a registration there is nothing to release, and no opener to offer as a
   control. The opener is reactive across registration and retirement.
   A plain host has no Leaf placement owner to register a surface.
   Releasing a node is synchronous: a widget must return the host's composer before
   removing the DOM that holds it. Composed containment includes shadow stages. */
import { under } from "../../lib/shadow-tree.js";
import { signal } from "/vendor/signals-core.js";
import { tick } from "../../state/version-signal.js";

// The placement owner writes the registrations; accessors read this same directory.
export const registrations = new Map();
const registrationVersion = signal(0);

export function setRegistration(owner, registration) {
  if (registration) registrations.set(owner, registration);
  else registrations.delete(owner);
  tick(registrationVersion);
}

export function updateSurface(registration) {
  if (registration.reconcileQueued) return;
  registration.reconcileQueued = true;
  queueMicrotask(() => {
    registration.reconcileQueued = false;
    void registration.invalidate();
  });
}

// The registered surface of a widget that has `threadOutlets`, as the widget reads
// it: before the runtime has registered it, or after it left, there is nothing it can
// open and nothing to release. A widget whose seats changed says so as it says any
// change in what it holds, with `lf-layout`, which asks for a thread pass
// (annotations/anchor-controls.js).
export const threadSurface = (owner) =>
  Object.freeze({
    get open() {
      registrationVersion.value;
      return registrations.get(owner)?.handle.open ?? null;
    },
    // A widget removes a node that may hold an outlet only through its placement's
    // `onCommit`, or after this: core's composer, the one node it carries from outlet
    // to outlet, leaves the widget's outlet under `node` now, for where the next
    // commit would put it once `node` is gone, so the removal cannot take the user's
    // editor with it.
    release(node) {
      const registration = registrations.get(owner);
      if (!registration) return;
      const outlet = registration.composition.outlet();
      if (outlet && registration.outlets.has(outlet) && under(outlet, node))
        registration.composition.restore();
    },
  });
