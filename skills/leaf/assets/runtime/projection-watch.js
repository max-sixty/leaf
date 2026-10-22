/* The watcher of the page's readings, for chrome and packages alike.

   `watchProjection(owner, paint, ready)` draws on the next microtask and follows the
   values that paint reads through native Preact effects: selected application parts,
   widget controllers and outside readings such as the shared clock, document changes
   and PRESENTATION. Several changes in one task owe one paint. Reads after an await
   need their own owner; mechanical focus reads are untracked so restoring focus cannot
   subscribe a paint to its own output.

   Effects live only while the owner is connected. A return paints once to reestablish
   dependencies and reflect anything that moved while it was away. A paint that throws
   or rejects is reported once and retains its dependencies, allowing changed input to
   recover it. An optional synchronous proof withholds even clock paints; completion
   wakes only an owed paint, avoiding a presentation feedback loop.

   The returned function permanently ends the watcher, including queued paints.
   `refresh()` draws synchronously for mechanical changes, such as revealing held news,
   while retaining the owner's lifetime and proof. A refresh while away owes the return
   a paint; before the first paint it draws that one at once. */
import { effect, outsideReading, untracked } from "/vendor/browser-runtime.js";
import { watchPresentation } from "./semantic-state.js";
import { PRESENTATION } from "./presentation.js";
import { watchOwner } from "./arrivals.js";
import { readingPaint } from "./presence.js";

// PRESENTATION replaces a provisional startup reading, so an owner away when the page
// announced it owes its paint again.
let presentations = 0;
const heard = new Set();
document.addEventListener(PRESENTATION, () => {
  presentations += 1;
  const round = {};
  for (const moved of [...heard]) moved(round);
});
const presented = outsideReading(
  () => presentations,
  (moved) => {
    heard.add(moved);
    return () => heard.delete(moved);
  },
);

export function watchProjection(owner, paint, ready = null) {
  // An effect follows the last paint. Its next run marks that paint stale; only the
  // queued draw reads again, preserving the owner's microtask and readiness boundary.
  let key = 0;
  let queued = false;
  let following = null;
  let connected = false;
  const update = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (connected && owner.isConnected) draw(key);
    });
  };
  const draw = readingPaint(owner, () => {
    if (ready !== null && !untracked(ready)) return draw.forget();
    following?.();
    let first = true;
    let outcome;
    following = effect(() => {
      if (!first) {
        key += 1;
        update();
        return;
      }
      first = false;
      // Keep the effect alive after a failed paint, so a later input can recover it.
      try {
        presented.read();
        outcome = { value: paint() };
      } catch (error) {
        outcome = { error };
      }
    });
    if (!connected) {
      following();
      following = null;
    }
    if ("error" in outcome) throw outcome.error;
    return outcome.value;
  });
  let stopProof = null;
  const stopLifetime = watchOwner(owner, {
    connect() {
      connected = true;
      // Ready reads may invalidate their own presentation. Only an owed paint retries,
      // so finishing a paint cannot feed another paint.
      if (ready)
        stopProof = watchPresentation(() => draw.owes(key) && ready() && update());
      draw.forget();
      update();
    },
    disconnect() {
      connected = false;
      stopProof?.();
      stopProof = null;
      following?.();
      following = null;
    },
  });
  const stop = () => {
    stopLifetime();
    draw.stop();
  };
  // A refresh before the first paint is that paint, drawn now.
  stop.refresh = () =>
    draw.owes(key) && owner.isConnected ? draw(key) : draw.refresh();
  return stop;
}
