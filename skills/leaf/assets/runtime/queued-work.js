/* Synchronous callback-job lifecycles, independent of any browser scheduling queue.

   A queue creates one frozen job identity at enqueue, runs its callback inline, and
   retires it after that synchronous turn or on cancellation. Observers enrolled when
   the job was created follow that job through retirement; unsubscription affects
   future jobs only. A host which owns its own ordering binds one deferred invocation
   through bindQueuedWork. Neither a returned promise nor its asynchronous tail is
   part of that invocation's scope. Observers trace the callback invocation, not the
   origin of each mutable value it reads. This module schedules nothing and reaches no DOM,
   frame, size-observer, semantic-state, or presentation owner. */

const jobObservers = new Set();
const jobCohorts = new WeakMap();
/** Observe new callback jobs through their complete synchronous lifecycle. */
export function observeQueuedWork(observer) {
  jobObservers.add(observer);
  return () => jobObservers.delete(observer);
}
const announce = (phase, job) => {
  for (const observer of jobCohorts.get(job)) observer(phase, job);
};
export function enqueueWork(callback) {
  const job = Object.freeze({ callback });
  jobCohorts.set(job, [...jobObservers]);
  announce("enqueue", job);
  return job;
}
export function runWork(job, ...args) {
  try {
    announce("run", job);
    return job.callback(...args);
  } finally {
    announce("finish", job);
  }
}
/** Bind one deferred callback invocation; its returned async tail is independent. */
export function bindQueuedWork(callback) {
  const job = enqueueWork(callback);
  return (...args) => runWork(job, ...args);
}

/** Retire a queued invocation without running its callback. */
export const cancelWork = (job) => announce("cancel", job);
