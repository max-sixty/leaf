/* @noformat Generated TypeScript; edit the .ts owner. */
const jobObservers = /* @__PURE__ */ new Set();
const jobCohorts = /* @__PURE__ */ new WeakMap();
function observeQueuedWork(observer) {
  jobObservers.add(observer);
  return () => jobObservers.delete(observer);
}
const announce = (phase, job, observers) => {
  for (const observer of observers) observer(phase, job);
};
function enqueueWork(callback) {
  const job = Object.freeze({ callback });
  const observers = [...jobObservers];
  jobCohorts.set(job, observers);
  announce("enqueue", job, observers);
  return job;
}
function claim(job) {
  const observers = jobCohorts.get(job);
  jobCohorts.delete(job);
  return observers;
}
function runWork(job, ...args) {
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
function bindQueuedWork(callback) {
  const job = enqueueWork(callback);
  return (...args) => runWork(job, ...args);
}
function cancelWork(job) {
  const observers = claim(job);
  if (observers) announce("cancel", job, observers);
}
export {
  bindQueuedWork,
  cancelWork,
  enqueueWork,
  observeQueuedWork,
  runWork
};
