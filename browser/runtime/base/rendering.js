// @ts-check
/* Leaf's settled reading of the page's rendering, as structured renderingState for
   chrome and geometry.
   updatesSettled says no queued update is waiting and the last update produced no
   size change a counted observer heard. preparationsSettled says no registered finite
   preparation is waiting. Full rendering readiness requires both; an observer of
   intermediate paint can read updatesSettled while preparation remains pending.
   Each field is true when that axis is settled. Hidden documents read true on
   both axes because they owe no visible paint until they become visible again.
   A reader outside the page waits on those facts after a gesture rather than
   guessing a number of frames, and one inside it on `afterSettling`.

   The reading counts the page's one pass per frame and its size observers, which are
   the library's (lib/frame-pass.js): `nextRender`, `nextFrame` and `cancelRender` for
   settling work, and `sizeObserver` in place of `new ResizeObserver`. The pass tells
   this module of each callback as it is asked for and of each counted observer's
   delivery as it arrives (`observeRenderingWork`), whoever the callback or the observer
   belongs to: the runtime, a package or a page's script.
   The lint gate refuses the browser's own in the runtime, so the pass and the reading
   answer for every owner there without a list of them. In the bundled packages it
   refuses `ResizeObserver` alone: a package's settling work comes through `nextRender`
   and `nextFrame`, and its motion that may run until the user stops it calls the
   browser's frame, which the reading doesn't count. The runtime's own such motion goes
   through `nextAnimation` and `cancelAnimation` here.

   `afterScript` is for a paint that must land before anything else can happen, but only
   once, from where the script that asked for it leaves things: it runs at the microtask
   checkpoint that ends that script (an event listener, a frame callback, a task). A
   render that one step of a script invalidates and a later step invalidates again, such
   as a control replaced and the focus landing on its successor, would otherwise paint
   the moment between them and then put back what it took off, a write that changes
   nothing. A callback asked for again before it runs runs once, and one that throws is
   reported as a frame callback's failure is while the others still run. Each is a job
   of lib/queued-work.js, as the pass's callbacks are. Repeated invalidations keep the
   existing job and its first enqueue context. That identifies the callback invocation,
   not the provenance of each mutable value it may read. Steps in separate listeners of
   one event are separate scripts.

   `afterOwedFrame` is for a long task that arrives on its own, such as adopting the
   server's reading, while a frame the page asked for has not painted yet, as the one a
   gesture's task asks for to paint what the gesture drew. After a long task the browser
   may run an arriving task before that frame, which then paints the gesture's result
   only once the arriving task is done, so the task waits for the frame instead (root
   AGENTS.md, "Responsiveness"). It waits only for the one frame already asked for, and
   not at all where none is or the document draws no frames. A task that would have
   fitted before that frame then paints in the next one instead.

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
   before it asks (`rendered` in src/leaf/source/render_checks.py).

   A document nobody can see gets no rendering updates: a hidden page, and a child page
   whose frame is not on screen — scrolled away, or in an inactive tab's panel or a
   closed disclosure, which hold their frames under `content-visibility: hidden`. Every
   queued callback runs before such a document next paints, so it reads settled rather
   than waiting on an update that will not come until someone can see it. Whether the
   frame shows is `frameVisibility`'s answer (frame-visibility.js). A host may hide or
   scroll away the frame it is loading; that is why `data-lf-presented`, which such a
   host waits on before showing the frame, never waits on this reading. */

import {
  callbacksPending,
  nextFrame,
  nextRender,
  observeRenderingWork,
} from "../lib/frame-pass.js";
import { enqueueWork, runWork } from "../lib/queued-work.js";
import { frameVisibility, onFrameVisibility } from "./frame-visibility.js";

/** @import {Work} from "../lib/queued-work.js" */
/** @typedef {Work<[], unknown>} ScriptWork */
/** @typedef {"begin" | "settle" | "cancel"} PreparationPhase */
/** @typedef {(phase: PreparationPhase, identity: Readonly<object>) => void} PreparationObserver */

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

// The pass's callbacks and counted size deliveries, heard as each is asked for.
observeRenderingWork((work) => {
  if (work === "delivery") heard = true;
  unsettle();
});

/** Continuous mechanical motion, such as a playing film, does not hold resting
 * proof open. Its owner cancels this browser frame when stopped or retired.
 * @param {FrameRequestCallback} callback
 */
export const nextAnimation = (callback) => requestAnimationFrame(callback);
/** @param {number} id */
export const cancelAnimation = (id) => cancelAnimationFrame(id);

// Those waiting for the frame asked for when they asked to paint (`afterOwedFrame`).
/** @type {(() => void)[]} */
let owedFrame = [];
function paintedOwed() {
  const waiting = owedFrame;
  owedFrame = [];
  for (const painted of waiting) painted();
}

/** Resolve once the frame the page has asked for has painted, or at once where it has
 * asked for none or draws no frames.
 * @returns {Promise<void>} */
export function afterOwedFrame() {
  if (!callbacksPending() || !rendered()) return Promise.resolve();
  // A callback asked for now joins the pass the waiting callbacks run in, and a task
  // queued from a frame's callbacks runs once the frame has painted. A page at rest
  // asks for the pass's frame before the check's (`unsettle`), so that task runs before
  // the check, and the work a waiter then starts keeps the page unsettled.
  if (!owedFrame.length) nextRender(() => setTimeout(paintedOwed));
  return new Promise((painted) => owedFrame.push(painted));
}
document.addEventListener("visibilitychange", () => {
  if (!rendered()) paintedOwed();
});

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
  if (callbacksPending() || heard) {
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
    reader opened shows. Returns a function that withdraws the wait, which a page whose
    rendering never quiets would otherwise hold for as long as the page stays open.
 * @param {() => void} settled
 * @returns {() => void}
 */
export function afterSettling(settled) {
  const waiter = { settled, since: begun };
  settling.push(waiter);
  nextFrame(owed);
  return () => {
    settling = settling.filter((each) => each !== waiter);
  };
}

// Nothing has been heard yet: the page is unsettled until its first quiet update.
onFrameVisibility((visibility) => {
  if (visibility?.visible) unsettle();
  else paintedOwed();
});
unsettle();
