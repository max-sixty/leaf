/* @noformat Generated TypeScript; edit the .ts owner. */
import { enqueueWork, runWork, cancelWork } from "./queued-work.js";
import { frameVisibility, onFrameVisibility } from "./frame-visibility.js";
const ROUNDS = 8;
let queued = /* @__PURE__ */ new Map();
let running = null;
let afterPaint = /* @__PURE__ */ new Map();
let lastId = 0;
let frame = 0;
let heard = false;
let quiet = false;
let checking = false;
let preparations = 0;
const preparationObservers = /* @__PURE__ */ new Set();
function observePreparations(observer) {
  preparationObservers.add(observer);
  return () => preparationObservers.delete(observer);
}
function holdRendering() {
  preparations++;
  const serial = ++begun;
  pending.add(serial);
  unsettle();
  const identity = Object.freeze({});
  const observers = [...preparationObservers];
  for (const observer of observers) observer("begin", identity);
  let released = false;
  return (phase = "settle") => {
    if (released) return;
    released = true;
    preparations--;
    pending.delete(serial);
    if (updateChecking) heard = true;
    unsettle();
    for (const observer of observers) observer(phase, identity);
  };
}
function request(into, callback) {
  const id = ++lastId;
  into.set(id, enqueueWork(callback));
  if (!running && !frame) frame = requestAnimationFrame(pass);
  unsettle();
  return id;
}
const nextRender = (callback) => request(queued, callback);
const nextFrame = (callback) => request(running ? afterPaint : queued, callback);
const nextAnimation = (callback) => requestAnimationFrame(callback);
const cancelAnimation = (id) => cancelAnimationFrame(id);
function cancelRender(id) {
  for (const queue of [queued, afterPaint, running]) {
    const job = queue?.get(id);
    if (!job) continue;
    queue?.delete(id);
    cancelWork(job);
    return;
  }
}
async function pass(time) {
  frame = 0;
  for (let round = 0; queued.size && round < ROUNDS; round++) {
    running = queued;
    queued = /* @__PURE__ */ new Map();
    for (const [id, job] of running) {
      running.delete(id);
      try {
        runWork(job, time);
      } catch (error) {
        reportError(error);
      }
      await null;
    }
  }
  running = null;
  for (const entry of afterPaint) queued.set(...entry);
  afterPaint = /* @__PURE__ */ new Map();
  if (queued.size) frame = requestAnimationFrame(pass);
}
const owedThisScript = /* @__PURE__ */ new Map();
function settleScript() {
  for (const [callback, job] of owedThisScript) {
    owedThisScript.delete(callback);
    try {
      runWork(job);
    } catch (error) {
      reportError(error);
    }
  }
}
function afterScript(callback) {
  if (!owedThisScript.size) queueMicrotask(settleScript);
  if (!owedThisScript.has(callback))
    owedThisScript.set(callback, enqueueWork(callback));
}
let deliveringSizes = 0;
function sizeObserver(callback, { counted = true } = {}) {
  const pending2 = /* @__PURE__ */ new Map();
  let installation = null;
  const observer = new ResizeObserver((entries, observer2) => {
    if (counted) {
      heard = true;
      unsettle();
    }
    deliveringSizes++;
    try {
      callback(entries, observer2);
    } finally {
      deliveringSizes--;
    }
  });
  const observe = observer.observe.bind(observer);
  const unobserve = observer.unobserve.bind(observer);
  const disconnect = observer.disconnect.bind(observer);
  const install = () => {
    installation = null;
    for (const [target, options] of pending2) observe(target, options);
    pending2.clear();
  };
  const retireInstallation = () => {
    if (pending2.size || installation === null) return;
    (counted ? cancelRender : cancelAnimation)(installation);
    installation = null;
  };
  observer.observe = (target, options) => {
    if (!deliveringSizes) {
      pending2.delete(target);
      retireInstallation();
      return observe(target, options);
    }
    pending2.set(target, options);
    if (installation === null)
      installation = (counted ? nextRender : nextAnimation)(install);
  };
  observer.unobserve = (target) => {
    pending2.delete(target);
    retireInstallation();
    unobserve(target);
  };
  observer.disconnect = () => {
    pending2.clear();
    retireInstallation();
    disconnect();
  };
  return observer;
}
const renderingState = () => {
  const visible = rendered();
  return {
    updatesSettled: quiet || !visible,
    preparationsSettled: preparations === 0 || !visible
  };
};
const rendered = () => !document.hidden && frameVisibility()?.visible !== false;
function unsettle() {
  quiet = false;
  if (checking) return;
  checking = true;
  requestAnimationFrame(afterUpdate);
}
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
  const waiting = settling;
  settling = [];
  for (const waiter of waiting)
    if ([...pending].some((serial) => serial > waiter.since)) settling.push(waiter);
    else waiter.settled();
}
let settling = [];
let begun = 0;
const pending = /* @__PURE__ */ new Set();
const owed = () => {
};
function afterSettling(settled) {
  settling.push({ settled, since: begun });
  nextFrame(owed);
}
onFrameVisibility((visibility) => {
  if (visibility.visible) unsettle();
});
unsettle();
export {
  afterScript,
  afterSettling,
  cancelAnimation,
  cancelRender,
  holdRendering,
  nextAnimation,
  nextFrame,
  nextRender,
  observePreparations,
  renderingState,
  sizeObserver
};
