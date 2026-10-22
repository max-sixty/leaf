// runtime/dom-move.js
var focus = null;
function preserveMoveFocus(capabilities) {
  focus = capabilities;
}
function move(parent, node, before) {
  if (node.parentNode === parent && (before === node || node.nextSibling === before))
    return node;
  if (parent.isConnected) focus?.watchStandingIn(parent.getRootNode());
  if (parent.moveBefore && node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true }))
    parent.moveBefore(node, before);
  else {
    const restore = node.nodeType === Node.ELEMENT_NODE ? focus?.holdFocus(node) : null;
    parent.insertBefore(node, before);
    restore?.();
  }
  return node;
}
document.documentElement.lfInitial.move = move;

export {
  preserveMoveFocus,
  move
};
