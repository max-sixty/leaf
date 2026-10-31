// @ts-check
/* Synchronous callback-job lifecycles, independent of any browser scheduling queue.

   A queue creates one frozen job identity at enqueue, runs its callback inline, and
   retires it after that synchronous turn or on cancellation. Running or cancelling
   claims the job before calling observers, so their reentry cannot invoke it twice.
   Observers enrolled when the job was created follow it through retirement; unsubscription affects
   future jobs only. A host which owns its own ordering binds one deferred invocation
   through bindQueuedWork. Neither a returned promise nor its asynchronous tail is
   part of that invocation's scope. Observers trace the callback invocation, not the
   origin of each mutable value it reads. This module schedules nothing and reaches no DOM,
   frame, size-observer, semantic-state, or presentation owner. */

/** @typedef {"enqueue" | "run" | "finish" | "cancel"} WorkPhase */
/** @typedef {Readonly<object>} WorkIdentity */
/** @typedef {(phase: WorkPhase, job: WorkIdentity) => void} WorkObserver */
/**
 * @template {unknown[]} Args
 * @template Result
 * @typedef {Readonly<{callback: (...args: Args) => Result}>} Work
 */

/** @type {Set<WorkObserver>} */
const jobObservers = new Set();
/** @type {WeakMap<WorkIdentity, WorkObserver[]>} */
const jobCohorts = new WeakMap();
/** Observe new callback jobs through their complete synchronous lifecycle.
 * @param {WorkObserver} observer
 */
export function observeQueuedWork(observer) {
  jobObservers.add(observer);
  return () => jobObservers.delete(observer);
}
/**
 * @param {WorkPhase} phase
 * @param {WorkIdentity} job
 * @param {WorkObserver[]} observers
 */
const announce = (phase, job, observers) => {
  for (const observer of observers) observer(phase, job);
};
/**
 * @template {unknown[]} Args
 * @template Result
 * @param {(...args: Args) => Result} callback
 */
export function enqueueWork(callback) {
  const job = Object.freeze({ callback });
  const observers = [...jobObservers];
  jobCohorts.set(job, observers);
  announce("enqueue", job, observers);
  return job;
}
/** @param {WorkIdentity} job */
function claim(job) {
  const observers = jobCohorts.get(job);
  jobCohorts.delete(job);
  return observers;
}
/**
 * @template {unknown[]} Args
 * @template Result
 * @param {Work<Args, Result>} job
 * @param {Args} args
 */
export function runWork(job, ...args) {
  const observers = claim(job);
  if (!observers) return;
  const callback = job.callback;
  try {
    announce("run", job, observers);
    return callback(...args);
  } finally {
    announce("finish", job, observers);
  }
}
/** Bind one deferred callback invocation; its returned async tail is independent.
 * @template {unknown[]} Args
 * @template Result
 * @param {(...args: Args) => Result} callback
 */
export function bindQueuedWork(callback) {
  const job = enqueueWork(callback);
  return (/** @type {Args} */ ...args) => runWork(job, ...args);
}

/** Retire a queued invocation without running its callback.
 * @param {WorkIdentity} job
 */
export function cancelWork(job) {
  const observers = claim(job);
  if (observers) announce("cancel", job, observers);
}
