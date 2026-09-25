/* Leaf's one rendering loop, and the one settled reading for the page's chrome and
   geometry: nothing Leaf has queued for a rendering update is still waiting, and the
   last update produced no size change a Leaf observer heard. A reader outside the page
   waits on it after a gesture rather than guessing a number of frames.

   Leaf's rendering callbacks and size observers go through this module: `nextRender`,
   `nextFrame` and `cancelRender` in place of `requestAnimationFrame` and
   `cancelAnimationFrame`, `sizeObserver` in place of `new ResizeObserver`. The lint gate
   refuses the browser's own in the runtime and in the bundled packages, so the loop and
   the reading answer for every owner there without a list of them. Coalescing owners
   keep their own flags; this module holds the one queue behind them.

   The loop takes one animation frame and works through every queued callback in it, in
   the order they were queued. `nextRender` asked for from inside that pass runs in the
   same pass, before the frame paints: a repaint that moves the page and the boxes that
   follow the page land in one frame, where a browser frame per owner painted each
   follower a frame behind what it follows. Asked for anywhere else — an input handler,
   a ResizeObserver delivery, which comes after the frame's callbacks — it runs in the
   next frame's pass. A chain that keeps asking stops after `ROUNDS` generations and
   finishes on the next frame. Between callbacks the pass waits one microtask step, so
   what a callback queued directly — a publication's render pass — has run before the
   next callback reads the page; a longer asynchronous tail, which the browser would
   drain between its own frame callbacks, lands after it.

   `nextFrame` is for a step that must not run in the pass that asked for it: an
   animation tick, a loop that follows the page frame by frame, a pause for one frame.
   Asked for inside a pass, it runs in the next frame's; asked for outside one, it is
   `nextRender`, and no frame paints first.

   Work toward a resting state is counted; a playback loop is not. A loop through
   `nextFrame` holds the page unsettled for as long as it runs, which is right for a
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

const ROUNDS = 8;
// What the next pass runs, what the running pass is working through, and what a
// `nextFrame` asked for during a pass, which waits for the pass after it. One id space
// across the three, so `cancelRender` needs no word on which queue holds its callback.
let queued = new Map();
let running = null;
let afterPaint = new Map();
let lastId = 0;
let frame = 0;
// A counted observer delivered since the last check.
let heard = false;
let quiet = false;
let checking = false;

function request(into, callback) {
  const id = ++lastId;
  into.set(id, callback);
  if (!running && !frame) frame = requestAnimationFrame(pass);
  unsettle();
  return id;
}

/** Run `callback` in the running pass, or else in the next frame's. */
export const nextRender = (callback) => request(queued, callback);

/** Run `callback` in the next frame's pass, never in the running one. */
export const nextFrame = (callback) => request(running ? afterPaint : queued, callback);

/** Withdraw a callback `nextRender` or `nextFrame` queued. */
export function cancelRender(id) {
  queued.delete(id) || afterPaint.delete(id) || running?.delete(id);
}

async function pass(time) {
  frame = 0;
  for (let round = 0; queued.size && round < ROUNDS; round++) {
    running = queued;
    queued = new Map();
    for (const [id, callback] of running) {
      running.delete(id);
      try {
        callback(time);
      } catch (error) {
        // One owner's failure is reported as the browser reports a frame callback's,
        // and the owners after it still paint.
        reportError(error);
      }
      await null;
    }
  }
  running = null;
  for (const entry of afterPaint) queued.set(...entry);
  afterPaint = new Map();
  if (queued.size) frame = requestAnimationFrame(pass);
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
  if (queued.size || heard) {
    heard = false;
    requestAnimationFrame(afterUpdate);
    return;
  }
  checking = false;
  quiet = true;
}

// Nothing has been heard yet: the page is unsettled until its first quiet update.
unsettle();
