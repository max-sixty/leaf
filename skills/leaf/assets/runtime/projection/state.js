/* The desired projection installed by presentation and whether rendering it deferred.
   This record may advance while a widget still shows its previous state. The
   presentation instance owns the separate DOM commit proof; consumers that narrate or
   release work must obtain that proof from the instance. Presentation is the sole
   writer of this shared semantic reading. */

let current = {
  actions: new Map(),
  reports: new Map(),
  classified: new Map(),
  desired: new Map(),
};
let deferred = false;

export const currentProjection = () => current;
export const projectionDeferred = () => deferred;

// Presentation is the sole writer. Install the projection and its deferred status as
// one reading so asynchronous consumers cannot observe a projection from one pass and
// the completion status from another.
export function installProjection(next, { deferred: nextDeferred = false } = {}) {
  current = next;
  deferred = nextDeferred;
}
