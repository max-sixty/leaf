/* Place `node` under `parent` before `before` (`null` appends), keeping the user standing
 * in it. Every retained-node mover goes through here: Lit's keyed and child-part
 * insertions, Sortable, `setChildren`, and the board.
 *
 * Within one composed root, `moveBefore` keeps the node's native state where the browser
 * has it: focus, caret, typed text and an iframe's document. New nodes, nodes from
 * another root, and engines without the API use `insertBefore`, which blurs a focused
 * descendant to the body; the user's place and caret are held across it (`holdFocus`).
 * An iframe still reloads there. The return value matches insertBefore, including when
 * inserting a fragment. */
import { holdFocus } from "./focus.js";

export function move(parent, node, before) {
  if (
    parent.moveBefore &&
    node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true })
  )
    parent.moveBefore(node, before);
  else {
    const restore = holdFocus(node);
    parent.insertBefore(node, before);
    restore?.();
  }
  return node;
}
