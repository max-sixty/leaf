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
 * synchronously settles the visual on a state whose inventory holds that part,
 * including cancelling a pending replacement of an already visible destination. A declared
 * part missing from the current inventory then stands in for the whole visual until
 * travel asks for it, rather than detaching. A label reader can
 * name an absent part in Threads without changing the visual's state. */

import { exceptionText } from "./layer-client.js";
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
 * `reveal(id)`, when given, settles the state that holds declared part `id` before it
 * returns, so the next `read` includes it and pending work cannot retire it. It is
 * called for visible destinations too. `label(id)` names a part absent from the
 * current state without revealing it.
 */
export function registerVisualParts(
  source,
  read,
  { reveal = null, label = null } = {},
) {
  if (registrations.has(source))
    throw new TypeError("A visual source may register its parts only once");
  registrations.set(source, { read, reveal, label });
  return { update: () => layoutChanged(source) };
}

const hasVisualParts = (source) => registrations.has(source);

/** The part ids admitted by a whole-inventory opt-in or generated-id prefixes.
 * Registered inventory order is also the order of the visual's targets. */
export function visualPartAdmission(visual, declaration) {
  if (!declaration || typeof declaration !== "object") return null;
  const { prefixes } = declaration;
  if (prefixes)
    return (id) => prefixes.some((prefix) => id !== prefix && id.startsWith(prefix));
  return visual.hasAttribute(declaration.parts) ? () => true : null;
}

/** Whether a part absent from the current inventory can still be drawn on request. */
export const revealsVisualParts = (source) =>
  Boolean(registrations.get(source)?.reveal);

/** Settle the requested part, even while old pixels await a replacement. */
export function revealRegisteredVisualPart(source, id) {
  const reveal = registrations.get(source)?.reveal;
  if (reveal) reveal(id);
  return registeredVisualPart(source, id);
}

/** Invalid registrations or ids outside a provider's declared prefixes. */
export function visualPartProblems(source, declaration) {
  if (!declaration || typeof declaration !== "object") return [];
  if (!hasVisualParts(source)) return [{ kind: "unregistered" }];
  try {
    const parts = registeredVisualParts(source);
    const admission = visualPartAdmission(source, declaration);
    const outside = declaration.prefixes
      ? parts.filter((part) => !admission(part.id)).map((part) => part.id)
      : [];
    return outside.length ? [{ kind: "unadmitted-parts", parts: outside }] : [];
  } catch (error) {
    return [{ kind: "unreadable", error: exceptionText(error) }];
  }
}

export function registeredVisualParts(source) {
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

// An invalid package inventory is reported by visualPartProblems at page check.
// The live page can still upgrade and expose its other controls for that reading.
export function usableVisualParts(source) {
  try {
    return registeredVisualParts(source);
  } catch {
    return [];
  }
}

export const registeredVisualPart = (source, id) =>
  registeredVisualParts(source).find((part) => part.id === id) ?? null;

export const registeredVisualPartLabel = (source, id) => {
  const current = registeredVisualPart(source, id)?.label;
  if (current) return current;
  const label = registrations.get(source)?.label?.(id);
  return words(label) || null;
};

export function usableVisualPartAt(source, target, admits = () => true) {
  const byElement = new Map(
    usableVisualParts(source)
      .filter(admits)
      .map((part) => [part.element, part]),
  );
  for (let current = target; current && current !== source; current = upFrom(current)) {
    const part = byElement.get(current);
    if (part) return part;
  }
  return null;
}
