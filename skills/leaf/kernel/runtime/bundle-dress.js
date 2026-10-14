// runtime/dress.js
var dresses = /* @__PURE__ */ new WeakMap();
var children = /* @__PURE__ */ new WeakMap();
function registerSampleDress(frame, send) {
  children.set(frame, send);
  return () => children.delete(frame);
}
var wear = (...args) => document.documentElement.lfInitial.wear(...args);
function dressFor(frame) {
  for (let node = frame.parentElement; node; node = node.parentElement)
    if (dresses.has(node)) return dresses.get(node);
  return null;
}
function dressSamples(owner, dress) {
  dresses.set(owner, dress);
  for (const frame of owner.querySelectorAll("iframe[data-lf-contained]")) {
    if (dressFor(frame) === dress) children.get(frame)?.(dress);
  }
}

export {
  registerSampleDress,
  wear,
  dressFor,
  dressSamples
};
