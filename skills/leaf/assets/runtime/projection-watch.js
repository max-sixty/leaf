/* One lifetime-bound subscription to a complete browser projection.

   `lf-actions` is the runtime's broad invalidation signal, not a package contract.
   Semantic APIs supply `read`: actions, updates, requests, and Asks all share
   this lifecycle without exposing the event or copying its cleanup rules. Clock
   readings made by the callback also refresh when their displayed value changes. */
import { clocked } from "./presence.js";

export function watchProjection(owner, read) {
  if (!(owner instanceof Element))
    throw new TypeError("A projection watcher needs an Element owner");
  if (typeof read !== "function")
    throw new TypeError("A projection watcher needs a reading function");
  const paint = clocked(owner, read);
  const update = () => {
    if (!owner.isConnected) {
      document.removeEventListener("lf-actions", update);
      paint.stop();
      return;
    }
    paint();
  };
  document.addEventListener("lf-actions", update);
  update();
  return () => {
    document.removeEventListener("lf-actions", update);
    paint.stop();
  };
}
