/* Runtime ownership for attributes and inline styles on the document roots.

   Authored revisions may replace html and body attributes in place while the live
   runtime keeps the same elements. A runtime writer registers each value it sets, so
   version activation can replace only the authored share without inferring ownership
   from names or serialized values. Each door writes only what changes the root: a
   restated value on `html` or `body` restyles the whole document all the same. */

// Root geometry exists before the module graph. Adopt the initial writers and
// ownership registries rather than starting a later set of root facts.
export const setRuntimeRootAttribute = (...args) =>
  document.documentElement.lfInitial.setRuntimeRootAttribute(...args);
export const setRuntimeRootStyle = (...args) =>
  document.documentElement.lfInitial.setRuntimeRootStyle(...args);
export const removeRuntimeRootStyle = (...args) =>
  document.documentElement.lfInitial.removeRuntimeRootStyle(...args);

export const runtimeRootState = (root) => ({
  attributes: document.documentElement.lfInitial.runtimeRootAttributes(root),
  styles: document.documentElement.lfInitial.runtimeRootStyles(root),
});
