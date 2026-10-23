// runtime/dress.js
var dresses = /* @__PURE__ */ new WeakMap();
var children = /* @__PURE__ */ new WeakMap();
function registerSampleDress(frame, send) {
  children.set(frame, send);
  return () => children.delete(frame);
}
function wear(owner, dress) {
  document.documentElement.lfInitial.wear(owner, dress);
  dresses.set(owner, dress);
  for (const frame of owner.querySelectorAll("iframe[data-lf-contained]")) {
    if (dressFor(frame) === dress) children.get(frame)?.(dress);
  }
}
function dressFor(frame) {
  for (let node = frame.parentElement; node; node = node.parentElement)
    if (dresses.has(node)) return dresses.get(node);
  return null;
}

export {
  registerSampleDress,
  wear,
  dressFor
};
