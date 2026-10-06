/* The one watcher of a complete browser reading, for chrome and packages alike.

   `watchProjection(owner, read)` calls `read` on the microtask after it subscribes,
   then once per microtask in which the semantic epoch advances, a projection deferral
   starts or ends, or the page announces `PRESENTATION`: several in one task make one
   call. Its subscriptions pause when `owner` leaves; returning reads the latest
   projection even when its semantic epoch is unchanged. A clock reading made inside
   `read` repaints it when the displayed value changes. The returned function permanently
   ends the subscription, including queued paints. `watchAsks`, `watchUpdates`, and `watchHistory` are this watcher
   with a reading of their own, so none of them states these rules again. */
import { clocked } from "./presence.js";
import { watchSemantic } from "./semantic-state.js";
import { watchProjectionDeferral } from "./projection/state.js";
import { PRESENTATION } from "./presentation.js";
import { watchOwner } from "./arrivals.js";

export function watchProjection(owner, read) {
  if (!(owner instanceof Element))
    throw new TypeError("A projection watcher needs an Element owner");
  if (typeof read !== "function")
    throw new TypeError("A projection watcher needs a reading function");
  let active = null;
  let disconnect;
  return watchOwner(owner, {
    connect() {
      const paint = clocked(owner, read);
      active = paint;
      let queued = false;
      const update = () => {
        if (queued) return;
        queued = true;
        queueMicrotask(() => {
          queued = false;
          if (active === paint && owner.isConnected) paint();
        });
      };
      const stop = watchSemantic(update);
      // Deferral changes the reading without publishing an epoch; PRESENTATION is
      // the mechanical readiness edge when the complete first reading becomes drawable.
      const stopDeferral = watchProjectionDeferral(update);
      document.addEventListener(PRESENTATION, update);
      disconnect = () => {
        active = null;
        stop();
        stopDeferral();
        document.removeEventListener(PRESENTATION, update);
        paint.stop();
      };
    },
    disconnect: () => disconnect(),
  });
}
