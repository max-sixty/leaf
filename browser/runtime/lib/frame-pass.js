// @ts-check
/* One pass per animation frame for every rendering callback on a page, and the size
   observer that goes with it. Any document can load it.

   A host's runtime, each widget's module and a page's own script schedule through this
   module, and so through the one queue it holds: `nextRender`, `nextFrame` and
   `cancelRender` for callbacks, and `sizeObserver` in place of `new ResizeObserver`.

   The pass takes one animation frame and works through every queued callback in it, in
   the order they were queued. `nextRender` asked for from inside that pass runs in the
   same pass, before the frame paints: a repaint that moves the page and the boxes that
   follow the page land in one frame, where a browser frame per owner painted each
   follower a frame behind what it follows. Asked for anywhere else, such as an input
   handler or a ResizeObserver delivery, which comes after the frame's callbacks, it
   runs in the next frame's pass. A chain that keeps asking stops after `ROUNDS`
   generations and finishes on the next frame. Between callbacks the pass waits one
   microtask step, so what a callback queued directly, such as a publication's render
   pass, has run before the next callback reads the page; a longer asynchronous tail,
   which the browser would drain between its own frame callbacks, lands after it.

   `nextFrame` is for a step that must not run in the pass that asked for it: an
   animation tick, a loop that follows the page frame by frame, a pause for one frame.
   Asked for inside a pass, it runs in the next frame's; asked for outside one, it is
   `nextRender`, and no frame paints first.

   Each queued callback is a job of queued-work.js, whose observers hear it queued, run
   and cancelled. An async callback's returned tail is not part of its turn in the pass.

   A host that waits for the page to come to rest hears this work as it is asked for
   (`observeRenderingWork`) and asks whether any callback still waits
   (`callbacksPending`), as Leaf's settled reading does (base/rendering.js). What it hears is
   work toward a resting state. Motion that may run until the user stops it, such as
   playback, calls the browser's `requestAnimationFrame` instead, and an observer of
   boxes that may move for as long as the page plays says `counted: false`. */

import { enqueueWork, runWork, cancelWork } from "./queued-work.js";

/** @import {Work} from "./queued-work.js" */
/** @typedef {Work<[number], unknown>} FrameWork */
/** @typedef {Map<number, FrameWork>} WorkQueue */
/** `"request"` as a callback joins a queue, and `"delivery"` as a counted size observer
 * delivers.
 * @typedef {(work: "request" | "delivery") => void} RenderingWorkObserver */

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

/** @type {Set<RenderingWorkObserver>} */
const observers = new Set();
/** Hear rendering work as it is asked for: a callback as it joins a queue, before
 * `nextRender` or `nextFrame` returns, and a counted size observer's delivery before
 * its callback runs. Returns a function that ends the hearing.
 * @param {RenderingWorkObserver} observer
 */
export function observeRenderingWork(observer) {
  observers.add(observer);
  return () => observers.delete(observer);
}
/** @param {"request" | "delivery"} work */
function announce(work) {
  for (const observer of observers) observer(work);
}

/** Whether a callback waits for a pass to run it, the running pass included. */
export const callbacksPending = () =>
  queued.size > 0 || afterPaint.size > 0 || Boolean(running?.size);

/**
 * @param {WorkQueue} into
 * @param {FrameRequestCallback} callback
 */
function request(into, callback) {
  const id = ++lastId;
  into.set(id, enqueueWork(callback));
  if (!running && !frame) frame = requestAnimationFrame(pass);
  announce("request");
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

/** Withdraw a callback `nextRender` or `nextFrame` queued.
 * @param {number | null | undefined} id
 */
export function cancelRender(id) {
  if (id == null) return;
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

// An observation started during delivery can request an initial notification at the
// same depth the browser just delivered, even when no box changed. Install those
// subscriptions before the next frame's layout. Owners still change state and paint
// synchronously; only the new sensor waits. A counted sensor's wait is a callback in
// the pass, so a host hears it; an uncounted one's is the browser's own frame.
let deliveringSizes = 0;
/** A `ResizeObserver` whose deliveries a host waiting for the page to rest hears
 * (`observeRenderingWork`), unless it watches boxes that may move for as long as the
 * page plays, which `counted: false` says.
 * @param {ResizeObserverCallback} callback
 * @param {{counted?: boolean | undefined}} [options]
 */
export function sizeObserver(callback, { counted = true } = {}) {
  /** @type {Map<Element, ResizeObserverOptions | undefined>} */
  const pending = new Map();
  /** @type {number | null} */
  let installation = null;
  const observer = new ResizeObserver((entries, observer) => {
    if (counted) announce("delivery");
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
    if (counted) cancelRender(installation);
    else cancelAnimationFrame(installation);
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
      installation = counted ? nextRender(install) : requestAnimationFrame(install);
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
