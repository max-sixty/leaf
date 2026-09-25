/* The one settled reading for the page's chrome and geometry: nothing Leaf has queued
   for a rendering update is still waiting, and the last update produced no size change a
   Leaf observer heard. A reader outside the page waits on it after a gesture rather
   than guessing a number of frames.

   Leaf's rendering callbacks and size observers go through this module: `nextRender`
   and `cancelRender` in place of `requestAnimationFrame` and `cancelAnimationFrame`,
   `sizeObserver` in place of `new ResizeObserver`. The lint gate refuses the browser's
   own in the runtime and in the bundled packages, so the reading answers for every owner
   there without a list of them. Coalescing owners keep their own queues; this module
   only counts what they put in the browser's.

   Work toward a resting state is counted; a playback loop is not. A loop through
   `nextRender` holds the page unsettled for as long as it runs, which is right for a
   glide that lands in a moment and wrong for a film that plays until the user stops it,
   so a page's own playback schedules with the browser directly.

   A rendering update runs animation-frame callbacks, then style and layout, then
   ResizeObserver delivery, then paint. A reading taken inside a callback precedes the
   observers its own update will deliver, so the check runs as a task queued from a
   callback, after that update is over. It finds the rendering settled when no counted
   callback is pending and no counted observer has delivered since the previous check:
   one quiet update. A counted request or delivery unsettles it synchronously, so a
   reader asking straight after an input handler that queued work reads false.

   What the reading cannot see is work an owner holds in a timer or a promise before it
   asks for a rendering update, an IntersectionObserver delivery (a task after the
   update, which may land after the check), what vendored bundles schedule for
   themselves, and a layout change no counted callback or observer takes part in. A
   reader outside the page that caused such a change lets one rendering update pass
   before it asks (`rendered` in tests/render_harness.py).

   A document nobody can see gets no rendering updates: a hidden page, and a child page
   whose frame is not rendered — an inactive tab's panel and a closed disclosure hold
   their frames under `content-visibility: hidden`. Every queued callback runs before
   such a document next paints, so it reads settled rather than waiting on an update
   that will not come until someone can see it. A cross-origin host's frame cannot be
   read from inside, and a host may hide or scroll away the frame it is loading; that is
   why `data-lf-presented`, which such a host waits on before showing the frame, never
   waits on this reading. */

const pending = new Set();
// A counted observer delivered since the last check.
let heard = false;
let quiet = false;
let checking = false;

/** `requestAnimationFrame`, counted by the settled reading. */
export function nextRender(callback) {
  const id = requestAnimationFrame((time) => {
    pending.delete(id);
    callback(time);
  });
  pending.add(id);
  unsettle();
  return id;
}

/** `cancelAnimationFrame` for a callback `nextRender` queued. */
export function cancelRender(id) {
  pending.delete(id);
  cancelAnimationFrame(id);
}

/** A `ResizeObserver` whose deliveries the settled reading counts. */
export function sizeObserver(callback) {
  return new ResizeObserver((entries, observer) => {
    heard = true;
    unsettle();
    callback(entries, observer);
  });
}

export const renderingSettled = () => quiet || !rendered();

function rendered() {
  if (document.hidden) return false;
  for (let view = window; view.frameElement; view = view.parent)
    if (!view.frameElement.checkVisibility()) return false;
  return true;
}

function unsettle() {
  quiet = false;
  if (checking) return;
  checking = true;
  requestAnimationFrame(afterUpdate);
}

const afterUpdate = () => setTimeout(check);

function check() {
  if (pending.size || heard) {
    heard = false;
    requestAnimationFrame(afterUpdate);
    return;
  }
  checking = false;
  quiet = true;
}

// Nothing has been heard yet: the page is unsettled until its first quiet update.
unsettle();
