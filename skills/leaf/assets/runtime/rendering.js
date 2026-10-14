/* Leaf's one rendering loop and structured renderingState for chrome and geometry.
   updatesSettled says no queued update is waiting and the last update produced no
   size change a Leaf observer heard. preparationsSettled says no registered finite
   preparation is waiting. Full rendering readiness requires both; an observer of
   intermediate paint can read updatesSettled while preparation remains pending.
   Each field is true when that axis is settled. Hidden documents read true on
   both axes because they owe no visible paint until they become visible again.
   A reader outside the page waits on those facts after a gesture rather than
   guessing a number of frames, and one inside it on `afterSettling`, as a sample's
   child does to say which of its heights a gesture caused (sample-child.js).

   Leaf's rendering callbacks and size observers go through this module: `nextRender`,
   `nextFrame` and `cancelRender` for settling work, `nextAnimation` and
   `cancelAnimation` for continuous mechanical motion, and `sizeObserver` in place
   of `new ResizeObserver`. The lint gate
   refuses the browser's own in the runtime and in the bundled packages, so the loop and
   the reading answer for every owner there without a list of them. Coalescing owners
   keep their own flags; this module holds the one queue behind them.

   The neutral `queued-work.js` home binds a callback's one deferred invocation to that same lifecycle,
   for host schedules which own their own order rather than using this frame queue.
   Its `observeQueuedWork` exposes each queued callback's lifecycle to tracing owners.
   Its frozen identity is announced at enqueue, immediately before and after its
   synchronous turn, or on cancellation. The enqueue-time observer cohort follows
   that job to completion even if unsubscribed meanwhile; unsubscription affects new
   jobs. Observers can carry a scheduling context across this coalesced queue without
   changing callbacks, their execution order, or the pass's microtask checkpoint.
   An async callback's returned tail is not part of its synchronous rendering turn.

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

   `afterScript` is for a paint that must land before anything else can happen, but only
   once, from where the script that asked for it leaves things: it runs at the microtask
   checkpoint that ends that script (an event listener, a frame callback, a task). A
   render that one step of a script invalidates and a later step invalidates again, such
   as a control replaced and the focus landing on its successor, would otherwise paint
   the moment between them and then put back what it took off, a write that changes
   nothing. A callback asked for again before it runs runs once, and one that throws is
   reported as a frame callback's failure is while the others still run. Repeated
   invalidations keep the existing job and its first enqueue context. That identifies
   the callback invocation, not the provenance of each mutable value it may read.
   Steps in
   separate listeners of one event are separate scripts.

   `nextFrame` is for a step that must not run in the pass that asked for it: an
   animation tick, a loop that follows the page frame by frame, a pause for one frame.
   Asked for inside a pass, it runs in the next frame's; asked for outside one, it is
   `nextRender`, and no frame paints first.

   Work toward a resting state is counted; a playback loop is not. A loop through
   `nextFrame` holds the page unsettled for as long as it runs, which is right for a
   glide that lands in a moment and wrong for a film that plays until the user stops it,
   so playback uses nextAnimation/cancelAnimation, which schedule with the browser
   without entering the counted queue.

   A rendering update runs animation-frame callbacks, then style and layout, then
   ResizeObserver delivery, then paint. A reading taken inside a callback precedes the
   observers its own update will deliver, so the check runs as a task queued from a
   callback, after that update is over. It finds the rendering settled when no counted
   callback is pending and no counted observer has delivered since the previous check:
   one quiet update. A counted request or delivery unsettles it synchronously, so a
   reader asking straight after an input handler that queued work reads false.

   Finite asynchronous preparation registers a `holdRendering` until it commits or its
   owner retires. A live sample whose first document departs before presentation
   waits for its next document or Reset. Registration unsettles synchronously; release requires a final quiet
   update, including the preparation's DOM writes and observer deliveries. Its opaque
   frozen identity is announced to `observePreparations` at registration and once on
   settlement or cancellation. The registration-time observer cohort follows that hold
   to retirement even if unsubscribed meanwhile. Capable work owns one hold per producer,
   independently of whether an aggregate semantic presentation has already failed or
   been superseded. Reconnecting work registers a new hold and observation identity.
   A held local
   edit is not rendering work: it defers a semantic reading until the gesture ends.

   What the reading cannot see is unregistered work an owner holds in a timer or a
   promise before it asks for a rendering update, an IntersectionObserver delivery (a task after the
   update, which may land after the check), what vendored bundles schedule for
   themselves, and a layout change no counted callback or observer takes part in. A
   reader outside the page that caused such a change lets one rendering update pass
   before it asks (`rendered` in scripts/leaf/render_checks.py).

   A document nobody can see gets no rendering updates: a hidden page, and a child page
   whose frame is not rendered — an inactive tab's panel and a closed disclosure hold
   their frames under `content-visibility: hidden`. Every queued callback runs before
   such a document next paints, so it reads settled rather than waiting on an update
   that will not come until someone can see it. A sample's host publishes whether its
   frame is visible across the isolated document boundary; the child never reads the
   host's DOM to decide whether it can paint. A host may hide or scroll away the frame
   it is loading; that is
   why `data-lf-presented`, which such a host waits on before showing the frame, never
   waits on this reading. A native implicit-root observer supplies whether the sample
   intersects the containing viewports; its host supplies only admission through
   tab visibility, inertness and modal reach, never a cached clipping rectangle. */

import { enqueueWork, runWork, cancelWork } from "./queued-work.js";
import { onSampleVisibility, sampleVisibility } from "./sample-visibility.js";

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
let preparations = 0;

const preparationObservers = new Set();

/** Observe each finite preparation's begin and terminal settle or cancel. */
export function observePreparations(observer) {
  preparationObservers.add(observer);
  return () => preparationObservers.delete(observer);
}

/** Keep finite preparation pending until it commits or its owner retires. */
export function holdRendering() {
  preparations++;
  unsettle();
  const identity = Object.freeze({});
  const observers = [...preparationObservers];
  for (const observer of observers) observer("begin", identity);
  let released = false;
  return (phase = "settle") => {
    if (released) return;
    released = true;
    preparations--;
    unsettle();
    for (const observer of observers) observer(phase, identity);
  };
}

function request(into, callback) {
  const id = ++lastId;
  into.set(id, enqueueWork(callback));
  if (!running && !frame) frame = requestAnimationFrame(pass);
  unsettle();
  return id;
}

/** Run `callback` in the running pass, or else in the next frame's. */
export const nextRender = (callback) => request(queued, callback);

/** Run `callback` in the next frame's pass, never in the running one. */
export const nextFrame = (callback) => request(running ? afterPaint : queued, callback);

/** Continuous mechanical motion, such as a playing film, does not hold resting
 * proof open. Its owner cancels this browser frame when stopped or retired. */
export const nextAnimation = (callback) => requestAnimationFrame(callback);
export const cancelAnimation = (id) => cancelAnimationFrame(id);

/** Withdraw a callback `nextRender` or `nextFrame` queued. */
export function cancelRender(id) {
  for (const queue of [queued, afterPaint, running]) {
    const job = queue?.get(id);
    if (!job) continue;
    queue.delete(id);
    cancelWork(job);
    return;
  }
}

async function pass(time) {
  frame = 0;
  for (let round = 0; queued.size && round < ROUNDS; round++) {
    running = queued;
    queued = new Map();
    for (const [id, job] of running) {
      running.delete(id);
      try {
        runWork(job, time);
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

const owedThisScript = new Map();
function settleScript() {
  // A callback asked for while the others run is visited too: a Map's iteration reaches
  // what joins it before the end.
  for (const [callback, job] of owedThisScript) {
    owedThisScript.delete(callback);
    try {
      runWork(job);
    } catch (error) {
      reportError(error);
    }
  }
}
export function afterScript(callback) {
  if (!owedThisScript.size) queueMicrotask(settleScript);
  if (!owedThisScript.has(callback))
    owedThisScript.set(callback, enqueueWork(callback));
}

/** A `ResizeObserver` whose deliveries the settled reading counts, unless it watches
 * boxes that may move for as long as the page plays, which `counted: false` says. */
export function sizeObserver(callback, { counted = true } = {}) {
  return new ResizeObserver((entries, observer) => {
    if (counted) {
      heard = true;
      unsettle();
    }
    callback(entries, observer);
  });
}

export const renderingState = () => {
  const visible = rendered();
  return {
    updatesSettled: quiet || !visible,
    preparationsSettled: preparations === 0 || !visible,
  };
};

function rendered() {
  if (document.hidden) return false;
  const sample = sampleVisibility();
  if (sample) return sample.visible;
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
  // A preparation's release unsettles the reading again, so its last check drains.
  if (preparations) return;
  const settled = settling;
  settling = [];
  for (const callback of settled) callback();
}

// Those waiting for the rendering begun when they asked to settle (`afterSettling`).
let settling = [];
const owed = () => {};

/** Call `settled` once the rendering that work begun now sets going has settled: a
    counted update runs after this moment, and then one is quiet with no finite
    preparation waiting, the whole of `renderingState`. A gesture's rendering is the
    work its input sets going until then, its answers to that input included, such as a
    widget preparing what a disclosure the reader opened shows. */
export function afterSettling(settled) {
  settling.push(settled);
  nextFrame(owed);
}

// Nothing has been heard yet: the page is unsettled until its first quiet update.
onSampleVisibility(() => {
  if (sampleVisibility()?.visible) unsettle();
});
unsettle();
