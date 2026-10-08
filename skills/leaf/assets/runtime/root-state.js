/* Runtime ownership for attributes and inline styles on the document roots.

   Authored revisions may replace html and body attributes in place while the live
   runtime keeps the same elements. A runtime writer registers each value it sets, so
   version activation can replace only the authored share without inferring ownership
   from names or serialized values. Each door writes only what changes the root: a
   restated value on `html` or `body` restyles the whole document all the same. */

import { keeps } from "./keeps.js";

const runtimeAttributes = new WeakMap();

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

// Root styles also exist before the module graph (initial margin placement).
// Adopt that writer and ownership registry rather than starting a later one.
export const setRuntimeRootStyle = (...args) =>
  document.documentElement.lfInitial.setRuntimeRootStyle(...args);
export const removeRuntimeRootStyle = (...args) =>
  document.documentElement.lfInitial.removeRuntimeRootStyle(...args);

export const runtimeRootState = (root) => ({
  attributes: new Set(runtimeAttributes.get(root) ?? []),
  styles: document.documentElement.lfInitial.runtimeRootStyles(root),
});
