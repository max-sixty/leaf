/* The one watcher of the page's readings, for chrome and packages alike.

   `watchProjection(owner, paint, ready)` calls `paint()` on the microtask after it
   subscribes, then once per microtask in which something the last paint read has
   moved: several in one task make one call. What a paint reads is collected as it runs
   (`collectReads`, snapshot.ts), into one record: every part of the publication it
   reads through a reader that selects its part (`readPart`, `readAsks`, a widget's
   controller, the runtime getters), and every reading of something outside the
   publication (`outsideReading`): the time it shows (`clockValue`, `ago`), whether a
   drag holds the projection back, and how many times the page has announced
   `PRESENTATION`. Every paint reads the last two, since a paint may draw from nodes
   they decide. The watcher follows each entry by the same rule, and a change that
   moves none of them paints nothing. So a paint never names its inputs, and none it
   reads can go unwatched. Only reads made synchronously count: a read after an `await`
   in an asynchronous paint, or of the document's nodes, is the caller's to watch, and
   so is a private signal such as where the user stands, which a paint may also write.
   A read of the whole root (`readApplication()`) throws, so a paint reads the parts it
   draws.

   Its subscriptions pause when `owner` leaves; a return paints again only when
   something it read changed while it was away, or when the departure cut short a paint
   whose returned promise had not settled (`readingPaint` in `presence.js`, the rule
   data subscriptions follow too). A paint that throws or rejects is reported once and
   keeps its subscriptions, to what it read before it threw. An optional synchronous
   proof predicate withholds every paint, including clock paints; a withheld paint stays
   owed, and completion wakes only an owed paint, so repainting cannot create a
   presentation feedback loop. The returned function permanently ends the subscription,
   including queued paints. Its `refresh()` reruns the same paint synchronously for
   mechanical changes such as revealing held news, or on the return when the owner is
   away, while retaining the owner's lifetime and readiness proof; before the first
   paint it draws that one at once. A reading has no watcher of its own: a paint calls
   its reader (`readAsks`, `readQueues`, `readThreads`, `readWork`, `reportSequence`,
   `readHistory`), and one watcher serves a paint that reads several. */
import { collectReads, outsideReading } from "../vendor/browser-runtime.js";
import { watchPresentation } from "./semantic-state.js";
import { projectionDeferred, watchProjectionDeferral } from "./projection/state.js";
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
const deferral = outsideReading(projectionDeferred, watchProjectionDeferral);
const presented = outsideReading(
  () => presentations,
  (moved) => {
    heard.add(moved);
    return () => heard.delete(moved);
  },
);

export function watchProjection(owner, paint, ready = null) {
  // What the last paint read, each entry with the value it read. A paint is owed when
  // any of them has moved since.
  let read = null;
  const moved = () =>
    read === null || [...read].some(([reading, value]) => reading.read() !== value);
  // `readingPaint` draws a key it has not drawn; the key advances when an input moves.
  let key = 0;
  let queued = false;
  let subscribed = [];
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
  // Follow what the last paint read, while the owner is here. A subscriber hears its
  // value at once, which differs from the value read only where the paint itself, or
  // the time since, moved it.
  const follow = () => {
    for (const stop of subscribed) stop();
    subscribed =
      unsubscribe && read
        ? [...read].map(([reading, value]) =>
            reading.subscribe((now) => now !== value && update()),
          )
        : [];
  };
  // Every route, including the shared clock, checks this synchronous proof.
  const draw = readingPaint(owner, () => {
    if (ready !== null && !ready()) return draw.forget();
    const outcome = collectReads(() => {
      presented.read();
      deferral.read();
      return paint();
    });
    read = outcome.reads;
    follow();
    if ("error" in outcome) throw outcome.error;
    return outcome.value;
  });
  const stopLifetime = watchOwner(owner, {
    connect() {
      const stops = [];
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
  // A refresh before the first paint is that paint, drawn now.
  stop.refresh = () =>
    draw.owes(key) && owner.isConnected ? draw(key) : draw.refresh();
  return stop;
}
