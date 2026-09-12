/* One lifetime-bound subscription to a complete browser projection.

   The application publisher is the one semantic invalidation source. Semantic APIs
   supply `read`: updates, history, and Asks share this lifetime without copying its
   cleanup rules. Clock
   readings made by the callback also refresh when their displayed value changes. */
import { clocked } from "./presence.js";
import { watchSemantic } from "./semantic-state.js";
import { PRESENTATION } from "./presentation.js";

export function watchProjection(owner, read) {
  if (!(owner instanceof Element))
    throw new TypeError("A projection watcher needs an Element owner");
  if (typeof read !== "function")
    throw new TypeError("A projection watcher needs a reading function");
  const paint = clocked(owner, read);
  let queued = false;
  const update = () => {
    if (!owner.isConnected) {
      paint.stop();
      return;
    }
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (owner.isConnected) paint();
    });
  };
  const stop = watchSemantic(update);
  // The publisher can have its complete first reading before the page is drawable.
  // Presentation is only that mechanical readiness edge; later semantic changes come
  // exclusively from the publisher subscription above.
  document.addEventListener(PRESENTATION, update);
  return () => {
    stop();
    document.removeEventListener(PRESENTATION, update);
    paint.stop();
  };
}
