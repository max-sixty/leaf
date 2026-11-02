/* Place `node` under `parent` before `before` (`null` appends), keeping the user
 * in it. Every placement of a node that may already stand somewhere goes through here,
 * Lit's keyed and child-part insertions included; `architecture/moves` (eslint.config.mjs)
 * refuses the platform's own insertions where the source shows such a node.
 *
 * Within one composed root, `moveBefore` keeps the node's native state where the browser
 * has it: focus, a field's caret, typed text and an iframe's document. A selection with
 * an end inside the node is reset all the same, as the DOM's move algorithm resets every
 * live range there. On Leaf, `setChildLists` (dom-children.js) holds the page's
 * selection around the moves it makes and puts it back (`holdSelection`), and an editor
 * in a shadow tree records its own and puts it back as it lands (`connectedMoveCallback`,
 * as `leaf-text` does). New nodes, nodes from
 * another root, and WebKit, which lacks the API, use `insertBefore`, which blurs a focused
 * descendant to the body; an element's hold (`holdFocus`) puts the user back in it, as
 * it does when a change had dropped them from it and they have not acted since. An
 * already placed node is left alone. Text, comments and fragments, which Lit inserts
 * for every new row, hold no one. An iframe still reloads there. The return value
 * matches insertBefore, including when inserting a fragment. */
import { isElement } from "./shadow-tree.js";

// Leaf installs its focus accounting; native placement also works without a runtime.
/** @typedef {{hold: typeof import("./focus.js").holdFocus, watch: typeof import("./focus.js").watchCurrentLocationIn}} MoveFocus */
/** @type {MoveFocus | null} */
let focusOwner = null;
/** @param {MoveFocus} owner */
export const installMoveFocus = (owner) => {
  focusOwner = owner;
};
// Leaf's selection writer installs itself (native-selection.js); off Leaf a move
// leaves a selection inside a moved node reset, as the browser does.
/** @type {typeof import("./native-selection.js").holdSelection | null} */
let selectionOwner = null;
/** @param {typeof import("./native-selection.js").holdSelection} owner */
export const installMoveSelection = (owner) => {
  selectionOwner = owner;
};
// The page selection where moving `placed` would reset it, and what puts it back.
/** @param {Iterable<Node>} placed */
export const holdSelection = (placed) => selectionOwner?.(placed) ?? null;

/** @template {Node} T @param {Node & ParentNode} parent @param {T} node @param {Node | null} [before] */
export function move(parent, node, before = null) {
  if (node.parentNode === parent && (before === node || node.nextSibling === before))
    return node;
  // A retained move can enter another shadow root without a focus event. Subscribe
  // before placement, so connectedMoveCallback and the caller's next move are heard.
  if (parent.isConnected) focusOwner?.watch(parent.getRootNode());
  if (
    parent.moveBefore &&
    node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true })
  )
    parent.moveBefore(node, before);
  else {
    const restore = isElement(node) ? focusOwner?.hold(node) : null;
    parent.insertBefore(node, before);
    restore?.();
  }
  return node;
}

// Lit inserts natively off Leaf; the runtime installs its focus-preserving mover.
window.lfMove = move;
