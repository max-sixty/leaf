/* What an element wears: attributes and custom properties written as one set, so
 * a later set removes what the earlier one had and the next does not. The early
 * coordinator owns the writer (prepaint.js, `wear`), which a sample child's bootstrap
 * dresses its root with before modules load.
 *
 * An element can also dress the sample children under it (sample.js): each child's
 * root wears its frame's nearest dressed ancestor's set, so a candidate that restyles
 * a whole page keys on that child's root and never on the page holding the frame. A
 * child takes its dress in its bootstrap, before it paints, reset children included,
 * and a new dress reaches every child already present. */

/** @type {WeakMap<Element, LeafDress>} */
const dresses = new WeakMap();
/** @type {WeakMap<Element, (dress: LeafDress) => void>} */
const children = new WeakMap();
/** @param {HTMLIFrameElement} frame @param {(dress: LeafDress) => void} send */
export function registerSampleDress(frame, send) {
  children.set(frame, send);
  return () => children.delete(frame);
}

/** Apply one appearance to an element and its sample descendants. Replacing it
 * removes earlier attributes and properties absent from the new appearance. */
/** @param {HTMLElement} owner @param {LeafDress} dress */
export function wear(owner, dress) {
  window.lfRootState.wear(owner, dress);
  dresses.set(owner, dress);
  for (const frame of owner.querySelectorAll("iframe[data-lf-contained]")) {
    if (dressFor(frame) === dress) children.get(frame)?.(dress);
  }
}

/** @param {Element} frame */
export function dressFor(frame) {
  for (let node = frame.parentElement; node; node = node.parentElement)
    if (dresses.has(node)) return dresses.get(node);
  return null;
}
