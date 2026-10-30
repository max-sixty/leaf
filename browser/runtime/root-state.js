/* Runtime ownership for attributes and inline styles on the document roots.

   Authored revisions may replace html and body attributes in place while the live
   runtime keeps the same elements. A runtime writer registers each value it sets, so
   version activation can replace only the authored share without inferring ownership
   from names or serialized values. Each door writes only what changes the root: a
   restated value on `html` or `body` restyles the whole document all the same. */

// Bootstrap dresses sample roots before the module graph. Share those writers and
// ownership registries with later runtime changes.
/** @type {LeafRootState["setRuntimeRootAttribute"]} */
export const setRuntimeRootAttribute = (...args) =>
  document.documentElement.lfRootState.setRuntimeRootAttribute(...args);
/** @type {LeafRootState["setRuntimeRootStyle"]} */
export const setRuntimeRootStyle = (...args) =>
  document.documentElement.lfRootState.setRuntimeRootStyle(...args);
/** @type {LeafRootState["removeRuntimeRootStyle"]} */
export const removeRuntimeRootStyle = (...args) =>
  document.documentElement.lfRootState.removeRuntimeRootStyle(...args);

export const runtimeRootState = (root) => ({
  attributes: document.documentElement.lfRootState.attributes(root),
  styles: document.documentElement.lfRootState.styles(root),
});
