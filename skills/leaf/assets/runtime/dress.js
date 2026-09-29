/* What an element wears: attributes and custom properties written as one set, so
 * a later set removes what the earlier one had and the next does not.
 *
 * An element can also dress the sample children under it (sample.js): each child's
 * root wears its frame's nearest dressed ancestor's set, so a candidate that restyles
 * a whole page keys on that child's root and never on the page holding the frame. A
 * child takes its dress in its bootstrap, before it paints, reset children included,
 * and a new dress reaches every child already standing. */
import { keeps } from "./keeps.js";

const worn = new WeakMap();
const dresses = new WeakMap();

export function wear(element, dress) {
  const previous = worn.get(element);
  for (const name of Object.keys(previous?.attributes ?? {}))
    if (!Object.hasOwn(dress.attributes, name)) element.removeAttribute(name);
  for (const name of Object.keys(previous?.properties ?? {}))
    if (!Object.hasOwn(dress.properties, name)) element.style.removeProperty(name);
  for (const [name, value] of Object.entries(dress.attributes))
    keeps(element, name, value);
  for (const [name, value] of Object.entries(dress.properties))
    element.style.setProperty(name, value);
  worn.set(element, dress);
}

export function dressFor(frame) {
  for (let node = frame.parentElement; node; node = node.parentElement)
    if (dresses.has(node)) return dresses.get(node);
  return null;
}

export function dressSamples(owner, dress) {
  dresses.set(owner, dress);
  for (const frame of owner.querySelectorAll("iframe[data-lf-contained]")) {
    const root = frame.contentDocument?.documentElement;
    if (root && dressFor(frame) === dress) wear(root, dress);
  }
}
