/* Place `node` under `parent` before `before` (`null` appends), keeping the user standing
 * in it. Every placement of a node that may already stand somewhere goes through here,
 * Lit's keyed and child-part insertions included; `architecture/moves` (eslint.config.mjs)
 * refuses the platform's own insertions where the source shows such a node.
 *
 * Within one composed root, `moveBefore` keeps the node's native state where the browser
 * has it: focus, a field's caret, typed text and an iframe's document. A selection in an
 * editable collapses all the same, so an editor that records its own puts it back as it
 * lands (`connectedMoveCallback`, as `leaf-text` does). New nodes, nodes from
 * another root, and engines without the API use `insertBefore`, which blurs a focused
 * descendant to the body; an element's hold (`holdFocus`) puts the user back in it, as
 * it does when a change had dropped them from it and they have not acted since. Text,
 * comments and fragments, which Lit inserts for every new row, hold no one. An iframe
 * still reloads there. The return value matches insertBefore, including when inserting
 * a fragment. */
import { holdFocus } from "./focus.js";

export function move(parent, node, before) {
  if (
    parent.moveBefore &&
    node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true })
  )
    parent.moveBefore(node, before);
  else {
    const restore = node.nodeType === Node.ELEMENT_NODE ? holdFocus(node) : null;
    parent.insertBefore(node, before);
    restore?.();
  }
  return node;
}
