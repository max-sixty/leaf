/* What an element wears: attributes and custom properties written as one set, so
 * a later set removes what the earlier one had and the next does not. The early
 * coordinator owns the writer (prepaint.js, `wear`), which a sample child's bootstrap
 * dresses its root with before modules load.
 *
 * An element can also dress the sample children under it (sample.js): each child's
 * root wears its frame's nearest dressed ancestor's set, so a candidate that restyles
 * a whole page keys on that child's root and never on the page holding the frame. A
 * child takes its dress in its bootstrap, before it paints, reset children included,
 * and a new dress reaches every child already standing. */

const dresses = new WeakMap();
const children = new WeakMap();
export function registerSampleDress(frame, send) {
  children.set(frame, send);
  return () => children.delete(frame);
}

export const wear = (...args) => document.documentElement.lfInitial.wear(...args);

export function dressFor(frame) {
  for (let node = frame.parentElement; node; node = node.parentElement)
    if (dresses.has(node)) return dresses.get(node);
  return null;
}

export function dressSamples(owner, dress) {
  dresses.set(owner, dress);
  for (const frame of owner.querySelectorAll("iframe[data-lf-contained]")) {
    if (dressFor(frame) === dress) children.get(frame)?.(dress);
  }
}
