/* Move retained nodes without resetting native state where the browser supports it.
 * New nodes and nodes from another root use ordinary insertion. The return value
 * matches insertBefore, including for a fragment, so Lit can commit the node. */
export function move(parent, node, before) {
  if (
    parent.moveBefore &&
    node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true })
  )
    parent.moveBefore(node, before);
  else parent.insertBefore(node, before);
  return node;
}
