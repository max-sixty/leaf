/* Package-owned semantic parts of a rendered visual.
 *
 * A package declares one ordered inventory. Leaf validates that inventory and derives
 * both directions it needs: a durable token resolves to the current rendered element,
 * and a rendered hit resolves to the nearest registered part. `surface` is the native
 * element whose paint Leaf should follow; it defaults to the semantic element, while a
 * package may name one descendant to exclude decorative paint from a compound part. */

import { layoutChanged } from "./widget-elements.js";

const registrations = new WeakMap();

const parentAcross = (element) =>
  element?.parentElement ?? element?.getRootNode()?.host ?? null;

const containsAcross = (ancestor, node) => {
  for (let current = node; current; current = current.getRootNode()?.host ?? null)
    if (ancestor.contains(current)) return true;
  return false;
};

const words = (value) =>
  String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();

/** Register the current visual-part inventory for one rendered source.
 *
 * `read` returns ordered `{id, element, label, surface?}` records. Call `update()` after
 * any rendering or geometry change, including in-place attribute or style changes; it
 * emits the same layout signal used by every other package-owned geometry change.
 */
export function registerVisualParts(source, read) {
  if (!(source instanceof Element))
    throw new TypeError("Visual parts need an Element source");
  if (typeof read !== "function")
    throw new TypeError("Visual parts need an ordered reading function");
  if (registrations.has(source))
    throw new TypeError("A visual source may register its parts only once");
  registrations.set(source, read);
  return { update: () => layoutChanged(source) };
}

export const hasVisualParts = (source) => registrations.has(source);

export function visualPartProblems(source, declared) {
  if (!hasVisualParts(source)) return ["did not call registerVisualParts"];
  try {
    const ids = new Set(visualParts(source).map((part) => part.id));
    const missing = [...declared].filter((id) => !ids.has(id));
    return missing.length
      ? [`did not register declared parts ${missing.join(", ")}`]
      : [];
  } catch (error) {
    return [String(error?.message ?? error)];
  }
}

export function visualParts(source) {
  const read = registrations.get(source);
  if (!read) return [];
  const seenIds = new Set();
  const seenElements = new Set();
  const seenSurfaces = new Set();
  return [...read()].map((part, index) => {
    const number = index + 1;
    const id = words(part?.id);
    const element = part?.element;
    const label = words(part?.label);
    const surface = part?.surface ?? element;
    if (!id || /\s/.test(id))
      throw new TypeError(`Visual part ${number} has no single-token id`);
    if (
      !(element instanceof Element) ||
      element === source ||
      !containsAcross(source, element)
    )
      throw new TypeError(`Visual part ${id} has no descendant Element`);
    if (!label) throw new TypeError(`Visual part ${id} has no label`);
    if (!(surface instanceof Element) || !containsAcross(element, surface))
      throw new TypeError(`Visual part ${id} has no descendant Element surface`);
    if (seenIds.has(id))
      throw new TypeError(`A visual source registered part ${id} twice`);
    if (seenElements.has(element))
      throw new TypeError("A visual source registered one element as two parts");
    if (seenSurfaces.has(surface))
      throw new TypeError("A visual source registered one surface for two parts");
    seenIds.add(id);
    seenElements.add(element);
    seenSurfaces.add(surface);
    return { id, element, label, surface };
  });
}

export const visualPart = (source, id) =>
  visualParts(source).find((part) => part.id === id) ?? null;

export function visualPartAt(source, target) {
  const byElement = new Map(visualParts(source).map((part) => [part.element, part]));
  for (
    let current = target;
    current && current !== source;
    current = parentAcross(current)
  ) {
    const part = byElement.get(current);
    if (part) return part;
  }
  return null;
}
