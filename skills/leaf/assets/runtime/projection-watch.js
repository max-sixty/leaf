/* The one watcher of a browser reading, for chrome and packages alike.

   `watchProjection(owner, reading, paint, ready)` selects `reading(root)` from the
   semantic root and calls `paint(value)` on the microtask after it subscribes, then once
   per microtask in which that selection changes, a projection deferral starts or ends,
   or the page announces `PRESENTATION`: several in one task make one call. A selection
   shares the parts that did not move across publications (snapshot.ts), so it changes
   only when something it names does, and a publication that leaves it alone paints
   nothing. Its subscriptions pause when `owner` leaves; a return paints again only when
   one of those inputs changed while it was away, or when the departure cut short a
   paint whose returned promise had not settled (`readingPaint` in `presence.js`, the
   rule data subscriptions follow too). A paint that throws or rejects is reported once
   and keeps the subscription. A clock reading made inside `paint` repaints it when the
   displayed value changes. An optional synchronous proof predicate withholds every
   paint, including clock paints; a withheld paint stays owed, and completion wakes only
   an owed paint, so repainting cannot create a presentation feedback loop. The returned
   function permanently ends the subscription, including queued paints. Its `refresh()`
   reruns the same clock-tracked paint synchronously for mechanical changes such as
   revealing held news, or on the return when the owner is away, while retaining the
   owner's lifetime and readiness proof. `watchQuestions`, `watchQueues`,
   `watchThreads`, `watchReports` and `watchHistory` are this watcher with a reading of
   their own, so none of them states these rules again. */
import { applicationState, watchPresentation } from "./semantic-state.js";
import { projectionDeferred, watchProjectionDeferral } from "./projection/state.js";
import { PRESENTATION } from "./presentation.js";
import { watchOwner } from "./arrivals.js";
import { readingPaint } from "./presence.js";

// PRESENTATION replaces a provisional startup reading, so an owner away when the page
// announced it owes its paint again.
let presentations = 0;
document.addEventListener(PRESENTATION, () => (presentations += 1));

export function watchProjection(owner, reading, paint, ready = null) {
  const selected = applicationState.select(reading);
  // What the last paint read: its selection, by identity, and the mechanical inputs
  // beside it. A paint is owed when any of them has moved since.
  let read = null;
  const inputs = () => [selected.read(), projectionDeferred(), presentations];
  const moved = () =>
    read === null || inputs().some((input, index) => input !== read[index]);
  // Every route, including the shared clock, checks this synchronous proof.
  const draw = readingPaint(owner, () => {
    if (ready !== null && !ready()) return draw.forget();
    read = inputs();
    return paint(read[0]);
  });
  // `readingPaint` draws a key it has not drawn; the key advances when an input moves.
  let key = 0;
  let unsubscribe = null;
  let queued = false;
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
  const stopLifetime = watchOwner(owner, {
    connect() {
      const stops = [
        selected.subscribe(update),
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
    },
    disconnect() {
      unsubscribe();
      unsubscribe = null;
    },
  });
  const stop = () => {
    stopLifetime();
    draw.stop();
  };
  stop.refresh = draw.refresh;
  return stop;
}
