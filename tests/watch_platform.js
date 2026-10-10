// Health sensors observe native paint and input delivery. A controlled product clock
// may advance Date, timers, animation callbacks and Event.timeStamp, but Chrome's
// Layout Instability records stay on its native performance clock. Save the matching
// platform once for all sensors, including when Playwright installed its clock before
// this document opened. Page work continues to use its own controlled scheduling.
(() => {
  if (window.lfWatchPlatform) return;
  const platform = window.__pwClock?.builtins ?? window;
  // Native document replacement keeps this realm and its observers, but clears
  // Window and Document listeners. Restore only the sensors' listeners before
  // the replacement parses; application listeners retain their native lifetime.
  const listeners = [];
  const listen = (target, type, callback, options) => {
    const add = target.addEventListener;
    const install = () => add.call(target, type, callback, options);
    install();
    if (target === window || target === document) listeners.push(install);
  };
  const open = Document.prototype.open;
  Document.prototype.open = function (...args) {
    const result = open.apply(this, args);
    if (this === document && result === document)
      for (const install of listeners) install();
    return result;
  };
  window.lfWatchPlatform = {
    listen,
    performance: platform.performance,
    frame: platform.requestAnimationFrame.bind(window),
    later: platform.setTimeout.bind(window),
    cancelLater: platform.clearTimeout.bind(window),
    microtask: window.queueMicrotask.bind(window),
  };
})();
