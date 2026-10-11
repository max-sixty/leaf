/* Move retained nodes without resetting native state where the browser supports it.
 * New nodes and nodes from another root use ordinary insertion. The return value
 * matches insertBefore, including for a fragment, so Lit can commit the node.
 * Read platform methods through prototypes: named form controls shadow methods. */
export function move(parent, node, before) {
  const moveBefore = Object.getPrototypeOf(parent).moveBefore;
  if (
    typeof moveBefore === "function" &&
    Node.prototype.getRootNode.call(node, { composed: true }) ===
      Node.prototype.getRootNode.call(parent, { composed: true })
  )
    moveBefore.call(parent, node, before);
  else Node.prototype.insertBefore.call(parent, node, before);
  return node;
}
