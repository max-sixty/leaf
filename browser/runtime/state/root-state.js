// Compiled from root-state.ts by build/typescript.mjs; edit that file.
/* Runtime ownership for attributes and inline styles on the document roots.

   Authored revisions may replace html and body attributes in place while the live
   runtime keeps the same elements. A runtime writer registers each value it sets, so
   version activation can replace only the authored share without inferring ownership
   from names or serialized values. Each door writes only what changes the root: a
   restated value on `html` or `body` restyles the whole document all the same.

   In Chromium, a custom property that changes on `html` restyles every element, since
   every element inherits it, unless it is registered as non-inheriting. So a value only
   the root reads, or one that changes with the user's input, is written as the plain
   property it sets, and a custom property only for a token the page's
   CSS inherits that changes as rarely as its source, such as a page tab strip's
   height (dom/root-headers.js). */

// Bootstrap dresses sample roots before the module graph. Share those writers and
// ownership registries with later runtime changes.
export const setRuntimeRootAttribute = (...args) =>
  window.lfRootState.setRuntimeRootAttribute(...args);
export const setRuntimeRootStyle = (...args) =>
  window.lfRootState.setRuntimeRootStyle(...args);
export const removeRuntimeRootStyle = (...args) =>
  window.lfRootState.removeRuntimeRootStyle(...args);

export const runtimeRootState = (root) => ({
  attributes: window.lfRootState.attributes(root),
  styles: window.lfRootState.styles(root),
});
