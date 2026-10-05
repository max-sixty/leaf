// Health sensors observe native paint and input delivery. A controlled product clock
// may advance Date, timers, animation callbacks and Event.timeStamp, but Chrome's
// Layout Instability records stay on its native performance clock. Save the matching
// platform once for all sensors, including when Playwright installed its clock before
// this document opened. Page work continues to use its own controlled scheduling.
(() => {
  if (window.lfWatchPlatform) return;
  const platform = window.__pwClock?.builtins ?? window;
  window.lfWatchPlatform = {
    performance: platform.performance,
    frame: platform.requestAnimationFrame.bind(window),
    later: platform.setTimeout.bind(window),
    cancelLater: platform.clearTimeout.bind(window),
    microtask: window.queueMicrotask.bind(window),
  };
})();
