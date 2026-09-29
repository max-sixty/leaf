/* Runtime ownership for attributes and inline styles on the document roots.

   Authored revisions may replace html and body attributes in place while the live
   runtime keeps the same elements. A runtime writer registers each value it sets, so
   version activation can replace only the authored share without inferring ownership
   from names or serialized values. Each door writes only what changes the root: a
   restated value on `html` or `body` restyles the whole document all the same. */

import { keeps } from "./keeps.js";

const runtimeAttributes = new WeakMap();
const runtimeStyles = new WeakMap();

function register(owners, root, name) {
  let names = owners.get(root);
  if (!names) {
    names = new Set();
    owners.set(root, names);
  }
  names.add(name);
}

export function setRuntimeRootAttribute(root, name, value) {
  register(runtimeAttributes, root, name);
  keeps(root, name, value);
}

export function setRuntimeRootStyle(root, property, value, priority = "") {
  register(runtimeStyles, root, property);
  if (
    root.style.getPropertyValue(property) !== value ||
    root.style.getPropertyPriority(property) !== priority
  )
    root.style.setProperty(property, value, priority);
}

export function removeRuntimeRootStyle(root, property) {
  runtimeStyles.get(root)?.delete(property);
  if (root.style.getPropertyValue(property)) root.style.removeProperty(property);
}

export const runtimeRootState = (root) => ({
  attributes: new Set(runtimeAttributes.get(root) ?? []),
  styles: new Set(runtimeStyles.get(root) ?? []),
});
