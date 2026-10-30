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

type WorkPhase = "enqueue" | "run" | "finish" | "cancel";
type WorkIdentity = Readonly<object>;
type WorkObserver = (phase: WorkPhase, job: WorkIdentity) => void;
type Work<Args extends unknown[], Result> = Readonly<{
  callback: (...args: Args) => Result;
}>;

const jobObservers = new Set<WorkObserver>();
const jobCohorts = new WeakMap<WorkIdentity, WorkObserver[]>();
/** Observe new callback jobs through their complete synchronous lifecycle. */
export function observeQueuedWork(observer: WorkObserver) {
  jobObservers.add(observer);
  return () => jobObservers.delete(observer);
}
const announce = (phase: WorkPhase, job: WorkIdentity, observers: WorkObserver[]) => {
  for (const observer of observers) observer(phase, job);
};
export function enqueueWork<Args extends unknown[], Result>(
  callback: (...args: Args) => Result,
) {
  const job = Object.freeze({ callback });
  const observers = [...jobObservers];
  jobCohorts.set(job, observers);
  announce("enqueue", job, observers);
  return job;
}
function claim(job: WorkIdentity) {
  const observers = jobCohorts.get(job);
  jobCohorts.delete(job);
  return observers;
}
export function runWork<Args extends unknown[], Result>(
  job: Work<Args, Result>,
  ...args: Args
) {
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
/** Bind one deferred callback invocation; its returned async tail is independent. */
export function bindQueuedWork<Args extends unknown[], Result>(
  callback: (...args: Args) => Result,
) {
  const job = enqueueWork(callback);
  return (...args: Args) => runWork(job, ...args);
}

/** Retire a queued invocation without running its callback. */
export function cancelWork(job: WorkIdentity) {
  const observers = claim(job);
  if (observers) announce("cancel", job, observers);
}
