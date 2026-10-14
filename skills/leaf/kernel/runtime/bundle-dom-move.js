import {
  holdFocus,
  watchStandingIn
} from "./bundle-sample-visibility.js";

// runtime/dom-move.js
function move(parent, node, before) {
  if (parent.isConnected) watchStandingIn(parent.getRootNode());
  if (parent.moveBefore && node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true }))
    parent.moveBefore(node, before);
  else {
    const restore = node.nodeType === Node.ELEMENT_NODE ? holdFocus(node) : null;
    parent.insertBefore(node, before);
    restore?.();
  }
  return node;
}

export {
  move
};
