/* The one watcher of a browser reading, for chrome and packages alike.

   `watchProjection(owner, paint, ready)` calls `paint()` on the microtask after it
   subscribes, then once per microtask in which a part of the page's publication that
   the last paint read has moved, a projection deferral starts or ends, or the page
   announces `PRESENTATION`: several in one task make one call. The parts a paint read
   are collected as it runs (`collectReads`, snapshot.ts): every read through a reader
   that selects its part (`readPart`, `readAsks`, a widget's controller, the runtime
   getters) subscribes the watcher to that part, and a publication that leaves every
   part it read alone paints nothing. So a paint never names its inputs, and none it
   reads can go unwatched. Only reads of the publication made synchronously count: a
   read after an `await` in an asynchronous paint, or of the document's nodes, is the
   caller's to watch, and so is a private signal such as where the user stands, which a
   paint may also write. A read of the whole root (`readApplication()`) subscribes to
   every publication, so a paint reads the parts it draws.

   Its subscriptions pause when `owner` leaves; a return paints again only when one of
   the parts it read changed while it was away, or when the departure cut short a paint
   whose returned promise had not settled (`readingPaint` in `presence.js`, the rule
   data subscriptions follow too). A paint that throws or rejects is reported once and
   keeps the subscription, to the parts it read before it threw. A clock reading made
   inside `paint` repaints it when the displayed value changes. An optional synchronous
   proof predicate withholds every paint, including clock paints; a withheld paint stays
   owed, and completion wakes only an owed paint, so repainting cannot create a
   presentation feedback loop. The returned function permanently ends the subscription,
   including queued paints. Its `refresh()` reruns the same paint synchronously for
   mechanical changes such as revealing held news, or on the return when the owner is
   away, while retaining the owner's lifetime and readiness proof. `watchAsks`,
   `watchQueues`, `watchThreads`, `watchReports`, `watchHistory` and `watchWork` are this
   watcher around a reader of their own, so none of them states these rules again. */
import { collectReads } from "../vendor/browser-runtime.js";
import { followReads, watchPresentation } from "./semantic-state.js";
import { projectionDeferred, watchProjectionDeferral } from "./projection/state.js";
import { PRESENTATION } from "./presentation.js";
import { watchOwner } from "./arrivals.js";
import { readingPaint } from "./presence.js";

// PRESENTATION replaces a provisional startup reading, so an owner away when the page
// announced it owes its paint again.
let presentations = 0;
document.addEventListener(PRESENTATION, () => (presentations += 1));

export function watchProjection(owner, paint, ready = null) {
  // What the last paint read: each part, with the value it read, and the mechanical
  // inputs beside them. A paint is owed when any of them has moved since.
  let read = null;
  let mechanical = null;
  const moved = () =>
    read === null ||
    mechanical[0] !== projectionDeferred() ||
    mechanical[1] !== presentations ||
    [...read].some(([part, value]) => part.read() !== value);
  // `readingPaint` draws a key it has not drawn; the key advances when an input moves.
  let key = 0;
  let queued = false;
  let unfollow = () => {};
  let unsubscribe = null;
  const update = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (!unsubscribe || !owner.isConnected) return;
      if (moved()) key += 1;
      draw(key);
    });
  };
  // Subscribe to the parts the last paint read, while the owner is here.
  const follow = () => {
    unfollow();
    unfollow = unsubscribe && read ? followReads(read, update) : () => {};
  };
  // Every route, including the shared clock, checks this synchronous proof.
  const draw = readingPaint(owner, () => {
    if (ready !== null && !ready()) return draw.forget();
    mechanical = [projectionDeferred(), presentations];
    const outcome = collectReads(paint);
    read = outcome.reads;
    follow();
    if ("error" in outcome) throw outcome.error;
    return outcome.value;
  });
  const stopLifetime = watchOwner(owner, {
    connect() {
      const stops = [
        watchProjectionDeferral(update),
        () => document.removeEventListener(PRESENTATION, update),
      ];
      document.addEventListener(PRESENTATION, update);
      // Ready reads may invalidate their own presentation. Only an owed paint retries,
      // so finishing a paint cannot feed another paint.
      if (ready)
        stops.push(
          watchPresentation(() => (moved() || draw.owes(key)) && ready() && update()),
        );
      unsubscribe = () => {
        for (const stop of stops) stop();
      };
      follow();
      update();
    },
    disconnect() {
      unsubscribe();
      unsubscribe = null;
      follow();
    },
  });
  const stop = () => {
    stopLifetime();
    draw.stop();
  };
  stop.refresh = draw.refresh;
  return stop;
}
