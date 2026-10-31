// @ts-check
/* Leaf's one rendering loop and structured renderingState for chrome and geometry.
   updatesSettled says no queued update is waiting and the last update produced no
   size change a Leaf observer heard. preparationsSettled says no registered finite
   preparation is waiting. Full rendering readiness requires both; an observer of
   intermediate paint can read updatesSettled while preparation remains pending.
   Each field is true when that axis is settled. Hidden documents read true on
   both axes because they owe no visible paint until they become visible again.
   A reader outside the page waits on those facts after a gesture rather than
   guessing a number of frames, and one inside it on `afterSettling`.

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
   whose frame is not on screen — scrolled away, or in an inactive tab's panel or a
   closed disclosure, which hold their frames under `content-visibility: hidden`. Every
   queued callback runs before such a document next paints, so it reads settled rather
   than waiting on an update that will not come until someone can see it. Whether the
   frame shows is `frameVisibility`'s answer (frame-visibility.js). A host may hide or
   scroll away the frame it is loading; that is why `data-lf-presented`, which such a
   host waits on before showing the frame, never waits on this reading. */

import { enqueueWork, runWork, cancelWork } from "./queued-work.js";
import { frameVisibility, onFrameVisibility } from "./frame-visibility.js";

/** @import {Work} from "./queued-work.js" */
/** @typedef {Work<[number], unknown>} FrameWork */
/** @typedef {Work<[], unknown>} ScriptWork */
/** @typedef {Map<number, FrameWork>} WorkQueue */
/** @typedef {"begin" | "settle" | "cancel"} PreparationPhase */
/** @typedef {(phase: PreparationPhase, identity: Readonly<object>) => void} PreparationObserver */

const ROUNDS = 8;
// What the next pass runs, what the running pass is working through, and what a
// `nextFrame` asked for during a pass, which waits for the pass after it. One id space
// across the three, so `cancelRender` needs no word on which queue holds its callback.
/** @type {WorkQueue} */
let queued = new Map();
/** @type {WorkQueue | null} */
let running = null;
/** @type {WorkQueue} */
let afterPaint = new Map();
let lastId = 0;
let frame = 0;
// A counted observer delivered since the last check.
let heard = false;
let quiet = false;
let checking = false;
let preparations = 0;

/** @type {Set<PreparationObserver>} */
const preparationObservers = new Set();

/** Observe each finite preparation's begin and terminal settle or cancel.
 * @param {PreparationObserver} observer
 */
export function observePreparations(observer) {
  preparationObservers.add(observer);
  return () => preparationObservers.delete(observer);
}

/** Keep finite preparation pending until it commits or its owner retires. */
export function holdRendering() {
  preparations++;
  const serial = ++begun;
  pending.add(serial);
  unsettle();
  const identity = Object.freeze({});
  const observers = [...preparationObservers];
  for (const observer of observers) observer("begin", identity);
  let released = false;
  return (/** @type {Exclude<PreparationPhase, "begin">} */ phase = "settle") => {
    if (released) return;
    released = true;
    preparations--;
    pending.delete(serial);
    // Its commit owes a whole quiet update, even where a check is already waiting on
    // an update that ran before the release.
    if (updateChecking) heard = true;
    unsettle();
    for (const observer of observers) observer(phase, identity);
  };
}

/**
 * @param {WorkQueue} into
 * @param {FrameRequestCallback} callback
 */
function request(into, callback) {
  const id = ++lastId;
  into.set(id, enqueueWork(callback));
  if (!running && !frame) frame = requestAnimationFrame(pass);
  unsettle();
  return id;
}

/** Run `callback` in the running pass, or else in the next frame's.
 * @param {FrameRequestCallback} callback
 */
export const nextRender = (callback) => request(queued, callback);

/** Run `callback` in the next frame's pass, never in the running one.
 * @param {FrameRequestCallback} callback
 */
export const nextFrame = (callback) => request(running ? afterPaint : queued, callback);

/** Continuous mechanical motion, such as a playing film, does not hold resting
 * proof open. Its owner cancels this browser frame when stopped or retired.
 * @param {FrameRequestCallback} callback
 */
export const nextAnimation = (callback) => requestAnimationFrame(callback);
/** @param {number} id */
export const cancelAnimation = (id) => cancelAnimationFrame(id);

/** Withdraw a callback `nextRender` or `nextFrame` queued.
 * @param {number} id
 */
export function cancelRender(id) {
  for (const queue of [queued, afterPaint, running]) {
    const job = queue?.get(id);
    if (!job) continue;
    queue?.delete(id);
    cancelWork(job);
    return;
  }
}

/** @param {number} time */
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

/** @type {Map<() => unknown, ScriptWork>} */
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
/** @param {() => unknown} callback */
export function afterScript(callback) {
  if (!owedThisScript.size) queueMicrotask(settleScript);
  if (!owedThisScript.has(callback))
    owedThisScript.set(callback, enqueueWork(callback));
}

// An observation started during delivery can request an initial notification at the
// same depth the browser just delivered, even when no box changed. Install those
// subscriptions before the next frame's layout. Owners still change state and paint
// synchronously; only the new sensor waits. Counted sensors keep readiness pending.
let deliveringSizes = 0;
/** A `ResizeObserver` whose deliveries the settled reading counts, unless it watches
 * boxes that may move for as long as the page plays, which `counted: false` says.
 * @param {ResizeObserverCallback} callback
 * @param {{counted?: boolean | undefined}} [options]
 */
export function sizeObserver(callback, { counted = true } = {}) {
  /** @type {Map<Element, ResizeObserverOptions | undefined>} */
  const pending = new Map();
  /** @type {number | null} */
  let installation = null;
  const observer = new ResizeObserver((entries, observer) => {
    if (counted) {
      heard = true;
      unsettle();
    }
    deliveringSizes++;
    try {
      callback(entries, observer);
    } finally {
      deliveringSizes--;
    }
  });
  const observe = observer.observe.bind(observer);
  const unobserve = observer.unobserve.bind(observer);
  const disconnect = observer.disconnect.bind(observer);
  const install = () => {
    installation = null;
    for (const [target, options] of pending) observe(target, options);
    pending.clear();
  };
  const retireInstallation = () => {
    if (pending.size || installation === null) return;
    (counted ? cancelRender : cancelAnimation)(installation);
    installation = null;
  };
  observer.observe = (target, options) => {
    if (!deliveringSizes) {
      pending.delete(target);
      retireInstallation();
      return observe(target, options);
    }
    pending.set(target, options);
    if (installation === null)
      installation = (counted ? nextRender : nextAnimation)(install);
  };
  observer.unobserve = (target) => {
    pending.delete(target);
    retireInstallation();
    unobserve(target);
  };
  observer.disconnect = () => {
    pending.clear();
    retireInstallation();
    disconnect();
  };
  return observer;
}

export const renderingState = () => {
  const visible = rendered();
  return {
    updatesSettled: quiet || !visible,
    preparationsSettled: preparations === 0 || !visible,
  };
};

const rendered = () => !document.hidden && frameVisibility()?.visible !== false;

function unsettle() {
  quiet = false;
  if (checking) return;
  checking = true;
  requestAnimationFrame(afterUpdate);
}

// Whether an update has run whose check has not.
let updateChecking = false;
const afterUpdate = () => {
  updateChecking = true;
  setTimeout(check);
};

function check() {
  updateChecking = false;
  if (queued.size || heard) {
    heard = false;
    requestAnimationFrame(afterUpdate);
    return;
  }
  checking = false;
  quiet = true;
  // A preparation's release unsettles the reading again, so a waiter it holds drains
  // at the check after that release.
  const waiting = settling;
  settling = [];
  for (const waiter of waiting)
    if ([...pending].some((serial) => serial > waiter.since)) settling.push(waiter);
    else waiter.settled();
}

// Those waiting for the rendering begun when they asked to settle (`afterSettling`),
// each with the last preparation begun before it asked; the preparations not yet
// released, by the order they began in.
/** @type {{settled: () => void, since: number}[]} */
let settling = [];
let begun = 0;
/** @type {Set<number>} */
const pending = new Set();
const owed = () => {};

/** Call `settled` once the rendering that work begun now sets going has settled: a
    counted update runs after this moment, then one is quiet, and every finite
    preparation begun since has landed. A preparation already waiting is someone
    else's. A gesture's rendering is the work its input sets going until then, its
    answers to that input included, such as a widget preparing what a disclosure the
    reader opened shows.
 * @param {() => void} settled
 */
export function afterSettling(settled) {
  settling.push({ settled, since: begun });
  nextFrame(owed);
}

// Nothing has been heard yet: the page is unsettled until its first quiet update.
onFrameVisibility(
  (/** @type {NonNullable<ReturnType<typeof frameVisibility>>} */ visibility) => {
    if (visibility.visible) unsettle();
  },
);
unsettle();
