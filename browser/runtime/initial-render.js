/* Parser delivery renders each package's retained view before the first paint.
   A module reads the same view and returns its template from its live render;
   later markup initializes it on demand. Source copies and original node routes
   belong to the early coordinator (prepaint.js). */
const coordinator = (node) =>
  node.ownerDocument?.documentElement?.lfInitial ?? document.documentElement.lfInitial;

export const initialRender = (host) => coordinator(host).paint(host);
export const initialOrigin = (node) => coordinator(node).origin(node) ?? node;
export const initialParent = (node) => coordinator(node).parent(node);
export const authoredBody = (host) => coordinator(host).authoredBody(host);
export const initialSource = (node) => coordinator(node).reading(node);
export const restoreInitialSource = (root) => coordinator(root).restoreSource(root);
// What the author wrote: the early coordinator restores original widget sources
// before copying and takes off its marks and delivery's placeholders (version.js).
export const unmarkedCopy = (node) => coordinator(node).authoredCopy(node);
export const fragmentId = (fragment) =>
  document.documentElement.lfInitial.fragmentId(fragment);
