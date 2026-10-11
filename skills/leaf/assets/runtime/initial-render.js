/* The package-owned synchronous drawing delivery starts before the first paint.
   A module adopts that same drawing, or produces it for later markup. Source copies
   and original node routes belong to the early coordinator (prepaint.js). */
import { vocabularyFor } from "./widget-contexts.js";
const coordinator = (node) =>
  node.ownerDocument?.documentElement?.lfInitial ?? document.documentElement.lfInitial;

export const initialRender = (host) =>
  coordinator(host).paint(host, vocabularyFor(host).revision);
export const initialOrigin = (node) => coordinator(node).origin(node) ?? node;
export const initialParent = (node) => coordinator(node).parent(node);
export const initialSource = (node) => coordinator(node).reading(node);
export const restoreInitialSource = (root) => coordinator(root).restoreSource(root);
