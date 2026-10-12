/* The one watcher of a complete browser reading, for chrome and packages alike.

   `watchProjection(owner, read, ready)` calls `read` on the microtask after it subscribes,
   then once per microtask in which the semantic epoch advances, a projection deferral
   starts or ends, or the page announces `PRESENTATION`: several in one task make one
   call. Those are the reading's inputs. Its subscriptions pause when `owner` leaves; a
   return reads again only when an input changed while it was away, or when the
   departure cut short a paint whose returned promise had not settled (`readingPaint`
   in `arrivals.js`, the rule data subscriptions follow too), so a failed reading is
   not reported twice. A clock reading made inside `read` repaints it when the
   displayed value changes. An optional synchronous proof predicate withholds every
   paint, including clock paints; a withheld reading stays owed, and completion wakes
   only an owed reading, so repainting cannot create a presentation feedback loop. The
   returned function permanently ends the subscription, including queued paints. Its
   `refresh()` reruns the same clock-tracked reading synchronously for mechanical
   changes such as revealing held news, or on the return when the owner is away,
   while retaining the owner's lifetime and readiness proof. `watchQuestions`, `watchReports`, and `watchHistory` are this
   watcher with a reading of their own, so none of them states these rules again. */
import { readApplication, watchSemantic, watchPresentation } from "./semantic-state.js";
import { projectionDeferred, watchProjectionDeferral } from "./projection/state.js";
import { PRESENTATION } from "./presentation.js";
import { readingPaint, watchOwner } from "./arrivals.js";

// PRESENTATION replaces a provisional startup reading, so an owner away when the page
// announced it owes its reading again.
let presentations = 0;
document.addEventListener(PRESENTATION, () => (presentations += 1));
// A reading's inputs: each one's value, which keys the reading, and how to hear it
// change. Deferral changes the reading without publishing an epoch.
const INPUTS = [
  { value: () => readApplication().semanticEpoch, watch: watchSemantic },
  { value: projectionDeferred, watch: watchProjectionDeferral },
  {
    value: () => presentations,
    watch(heard) {
      document.addEventListener(PRESENTATION, heard);
      return () => document.removeEventListener(PRESENTATION, heard);
    },
  },
];
const inputs = () => INPUTS.map(({ value }) => value()).join(" ");

export function watchProjection(owner, read, ready = null) {
  if (!(owner instanceof Element))
    throw new TypeError("A projection watcher needs an Element owner");
  if (typeof read !== "function")
    throw new TypeError("A projection watcher needs a reading function");
  // Every route, including the shared clock, checks this synchronous proof.
  const paint = readingPaint(owner, () =>
    ready !== null && !ready() ? paint.forget() : read(),
  );
  let unsubscribe = null;
  let queued = false;
  const update = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (unsubscribe && owner.isConnected) paint(inputs());
    });
  };
  const stopLifetime = watchOwner(owner, {
    connect() {
      const stops = INPUTS.map(({ watch }) => watch(update));
      // Ready reads may invalidate their own presentation. Only an owed reading
      // retries, so finishing a paint cannot feed another paint.
      if (ready)
        stops.push(
          watchPresentation(() => paint.owes(inputs()) && ready() && update()),
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
    paint.stop();
  };
  stop.refresh = paint.refresh;
  return stop;
}
