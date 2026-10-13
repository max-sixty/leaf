/* An abort signal as a promise, for work that races its own cancellation
   (`Promise.race([work, aborted(signal)])`). The platform offers the signal's event and
   `throwIfAborted`, but nothing to await. */

/** Resolves, with nothing, once `signal` aborts; at once if it already has. */
export const aborted = (signal) => {
  const { promise, resolve } = Promise.withResolvers();
  if (signal.aborted) resolve();
  else signal.addEventListener("abort", () => resolve(), { once: true });
  return promise;
};
