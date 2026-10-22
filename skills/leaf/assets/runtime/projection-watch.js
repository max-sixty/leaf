/* The watcher of the page's readings, for chrome and packages alike.

   `watchProjection(owner, paint, ready)` follows the native render graph and the
   values that paint reads through native Solid reactions: selected application parts,
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
   `refresh()` starts a commit immediately for mechanical changes, such as revealing
   held news, and returns its completion. Focus and measurement use `afterRender` in
   that same commit. A refresh while away owes the return a paint; before the first
   paint it starts that one. Post-render reads are tracked too; superseded or departed
   owners run no remaining callbacks. */
import {
  renderCommit,
  createPresentationFlow,
  watchReaction,
  createSignal,
  flush,
  untracked,
} from "/vendor/browser-runtime.js";
import { watchPresentation } from "./semantic-state.js";
import { PRESENTATION } from "./presentation.js";
import { watchOwner } from "./arrivals.js";
import { readingPaint } from "./presence.js";
import { bindQueuedWork } from "./queued-work.js";
const projections = createPresentationFlow(bindQueuedWork);

// PRESENTATION replaces a provisional startup reading, so an owner away when the page
// announced it owes its paint again.
const [presentations, setPresentations] = createSignal(0, { ownedWrite: true });
document.addEventListener(PRESENTATION, () =>
  flush(() => setPresentations((value) => value + 1)),
);

export function watchProjection(owner, paint, ready = null) {
  // Reactions follow each synchronous render stretch. Native effects coalesce the
  // invalidations; the commit tracks post-render reads under this same lifetime.
  let key = 0;
  let following = [];
  let connected = false;
  let task = null;
  const update = () => {
    if (!task) return;
    void task.enqueue(() => {
      if (connected && owner.isConnected) return draw(key);
    });
  };
  const draw = readingPaint(owner, () => {
    if (ready !== null && !untracked(ready)) return draw.forget();
    for (const stop of following) stop();
    const generation = (following = []);
    const run = (callback) => {
      let outcome;
      const stop = watchReaction(
        () => {
          try {
            outcome = { value: callback() };
          } catch (error) {
            outcome = { error };
          }
        },
        () => {
          key += 1;
          update();
        },
      );
      if (connected && following === generation) generation.push(stop);
      else stop();
      if ("error" in outcome) throw outcome.error;
      return outcome.value;
    };
    return renderCommit(
      () => {
        presentations();
        return paint();
      },
      {
        run,
        bind: bindQueuedWork,
        current: () => connected && owner.isConnected && following === generation,
      },
    ).ready;
  });
  let stopProof = null;
  const stopLifetime = watchOwner(owner, {
    connect() {
      connected = true;
      task = projections.task();
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
      for (const stop of following) stop();
      following = [];
      task?.disconnect();
      task = null;
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
