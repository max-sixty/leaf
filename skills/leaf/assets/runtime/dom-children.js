/* Retained DOM child reconciliation. */

const detach = (node) => node.remove();

// Make `parent`'s children `nodes`, in order, without moving a node already in place.
// Removing stale nodes first leaves each following survivor exactly one place forward.
export function setChildren(parent, nodes, remove = detach) {
  const keep = new Set(nodes);
  for (const child of [...parent.childNodes]) if (!keep.has(child)) remove(child);
  let cursor = parent.firstChild;
  for (const node of nodes) {
    if (node === cursor) cursor = cursor.nextSibling;
    else parent.insertBefore(node, cursor);
  }
}
