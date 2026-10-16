// runtime/initial-render.js
var coordinator = (node) => node.ownerDocument?.documentElement?.lfInitial ?? document.documentElement.lfInitial;
var initialRender = (host) => coordinator(host).paint(host);
var initialOrigin = (node) => coordinator(node).origin(node) ?? node;
var initialParent = (node) => coordinator(node).parent(node);
var initialSource = (node) => coordinator(node).reading(node);
var restoreInitialSource = (root) => coordinator(root).restoreSource(root);
var unmarkedCopy = (node) => coordinator(node).authoredCopy(node);
var fragmentId = (fragment) => document.documentElement.lfInitial.fragmentId(fragment);

export {
  initialRender,
  initialOrigin,
  initialParent,
  initialSource,
  restoreInitialSource,
  unmarkedCopy,
  fragmentId
};
