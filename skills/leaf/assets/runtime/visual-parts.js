/* Package-owned semantic parts of a rendered visual.
 *
 * A package declares one ordered inventory. Leaf validates that inventory and derives
 * both directions it needs: a durable token resolves to the current rendered element,
 * and a rendered hit resolves to the nearest registered part. `surface` is the native
 * element whose paint Leaf should follow; it defaults to the semantic element, while a
 * package may name one descendant to exclude decorative paint from a compound part.
 *
 * A visual that draws its parts over time (a timeline, an animation, a stepper) does not
 * hold every declared part at every moment. Its registration names `reveal(id)`, which
 * synchronously moves the visual to a state whose inventory holds that part. A declared
 * part missing from the current inventory then stands in for the whole visual until
 * travel or the render gate asks for it, rather than detaching. */

import { under, upFrom } from "./shadow.js";
import { layoutChanged } from "./widget-elements.js";

const registrations = new WeakMap();

const words = (value) =>
  String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();

/** Register the current visual-part inventory for one rendered source.
 *
 * `read` returns ordered `{id, element, label, surface?}` records. Call `update()` after
 * any rendering or geometry change, including in-place attribute or style changes; it
 * emits the same layout signal used by every other package-owned geometry change.
 * `reveal(id)`, when given, draws the state that holds declared part `id` before it
 * returns, so the next `read` includes it.
 */
export function registerVisualParts(source, read, { reveal = null } = {}) {
  if (!(source instanceof Element))
    throw new TypeError("Visual parts need an Element source");
  if (typeof read !== "function")
    throw new TypeError("Visual parts need an ordered reading function");
  if (reveal !== null && typeof reveal !== "function")
    throw new TypeError("A visual part reveal must be a function");
  if (registrations.has(source))
    throw new TypeError("A visual source may register its parts only once");
  registrations.set(source, { read, reveal });
  return { update: () => layoutChanged(source) };
}

const hasVisualParts = (source) => registrations.has(source);

/** Whether a part absent from the current inventory can still be drawn on request. */
export const revealsVisualParts = (source) =>
  Boolean(registrations.get(source)?.reveal);

/** Draw the state that holds part `id`, when the source can and does not already. */
export function revealVisualPart(source, id) {
  const reveal = registrations.get(source)?.reveal;
  if (reveal && !visualPart(source, id)) reveal(id);
  return visualPart(source, id);
}

/** Why one source's registration breaks its declaration: `declared` ids it must
 * register, and `admits`, which every registered id must pass. The current state's
 * inventory is read; a declared part it lacks is a problem only when the visual cannot
 * reveal it, and `unrevealedVisualParts` asks the reveal once nothing else needs the
 * state the page opened in. */
export function visualPartProblems(source, declared, admits = () => true) {
  if (!hasVisualParts(source)) return ["did not call registerVisualParts"];
  try {
    const ids = visualParts(source).map((part) => part.id);
    const missing = revealsVisualParts(source)
      ? []
      : [...declared].filter((id) => !ids.includes(id));
    const outside = ids.filter((id) => !admits(id));
    return [
      ...(missing.length
        ? [`did not register declared parts ${missing.join(", ")}`]
        : []),
      ...(outside.length
        ? [`registered parts its prefixes do not admit ${outside.join(", ")}`]
        : []),
    ];
  } catch (error) {
    return [String(error?.message ?? error)];
  }
}

// Reveal each declared part the current state lacks. This moves the visual off the
// state it opened in, so a caller asks it last.
export function unrevealedVisualParts(source, declared) {
  try {
    const missing = [...declared].filter((id) => !revealVisualPart(source, id));
    return missing.length
      ? [`did not reveal declared parts ${missing.join(", ")}`]
      : [];
  } catch (error) {
    return [String(error?.message ?? error)];
  }
}

export function visualParts(source) {
  const read = registrations.get(source)?.read;
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
    if (!(element instanceof Element) || element === source || !under(element, source))
      throw new TypeError(`Visual part ${id} has no descendant Element`);
    if (!label) throw new TypeError(`Visual part ${id} has no label`);
    if (!(surface instanceof Element) || !under(surface, element))
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

export function visualPartAt(source, target, admits = () => true) {
  const byElement = new Map(
    visualParts(source)
      .filter(admits)
      .map((part) => [part.element, part]),
  );
  for (let current = target; current && current !== source; current = upFrom(current)) {
    const part = byElement.get(current);
    if (part) return part;
  }
  return null;
}
