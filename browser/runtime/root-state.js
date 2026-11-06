/* Runtime ownership for attributes and inline styles on the document roots.

   Authored revisions may replace html and body attributes in place while the live
   runtime keeps the same elements. A runtime writer registers each value it sets, so
   version activation can replace only the authored share without inferring ownership
   from names or serialized values. Each door writes only what changes the root: a
   restated value on `html` or `body` restyles the whole document all the same.

   A custom property that changes on `html` or `body` restyles every element in
   Chromium, registered and non-inheriting or not, since the comment marks' universal
   `::highlight()` rules (annotation-marks.css) give every element highlight styles
   that Chromium recomputes below an element whose custom properties change. So a
   value only the root reads, or one that changes with the user's input, is written as
   the plain property it sets, as the floating panel's band is
   (floating-panel.js, `followBox`), and a custom property only for a token the page's
   CSS inherits that changes as rarely as its source, such as a page tab strip's
   height (root-headers.js). */

// Bootstrap dresses sample roots before the module graph. Share those writers and
// ownership registries with later runtime changes.
/** @type {LeafRootState["setRuntimeRootAttribute"]} */
export const setRuntimeRootAttribute = (...args) =>
  window.lfRootState.setRuntimeRootAttribute(...args);
/** @type {LeafRootState["setRuntimeRootStyle"]} */
export const setRuntimeRootStyle = (...args) =>
  window.lfRootState.setRuntimeRootStyle(...args);
/** @type {LeafRootState["removeRuntimeRootStyle"]} */
export const removeRuntimeRootStyle = (...args) =>
  window.lfRootState.removeRuntimeRootStyle(...args);

/** @param {HTMLElement} root */
export const runtimeRootState = (root) => ({
  attributes: window.lfRootState.attributes(root),
  styles: window.lfRootState.styles(root),
});
