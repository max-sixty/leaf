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
 * travel or the render gate asks for it, rather than detaching. A label reader can
 * name an absent part in Threads without changing the visual's state. */

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
 * returns, so the next `read` includes it. `label(id)` names a part absent from the
 * current state without revealing it.
 */
export function registerVisualParts(
  source,
  read,
  { reveal = null, label = null } = {},
) {
  if (!(source instanceof Element))
    throw new TypeError("Visual parts need an Element source");
  if (typeof read !== "function")
    throw new TypeError("Visual parts need an ordered reading function");
  if (reveal !== null && typeof reveal !== "function")
    throw new TypeError("A visual part reveal must be a function");
  if (label !== null && typeof label !== "function")
    throw new TypeError("A visual part label must be a function");
  if (registrations.has(source))
    throw new TypeError("A visual source may register its parts only once");
  registrations.set(source, { read, reveal, label });
  return { update: () => layoutChanged(source) };
}

const hasVisualParts = (source) => registrations.has(source);

/** How one visual's `x-visual` declaration admits the part ids its module registers.
 *
 * `declared` is the ids authored in its `parts` attribute, which the registration must
 * be able to show; `prefixes` declares kinds rather than ids, so it names none. `rank(id)`
 * is an id's place in the declaration, which orders the visual's targets: its authored
 * token's index, 0 for any longer id one of the prefixes begins so those keep
 * registration order, and -1 for an id the declaration does not admit. Null for a
 * declaration that names no parts (`whole`, or none). Only an admitted id becomes a
 * durable coordinate; the `registered…` readers below report the whole inventory. */
export function visualPartAdmission(visual, declaration) {
  if (!declaration || typeof declaration !== "object") return null;
  const { prefixes } = declaration;
  if (prefixes)
    return {
      declared: [],
      rank: (id) => (prefixes.some((p) => id !== p && id.startsWith(p)) ? 0 : -1),
    };
  const declared =
    visual.getAttribute(declaration.parts)?.trim().split(/\s+/).filter(Boolean) ?? [];
  return { declared, rank: (id) => declared.indexOf(id) };
}

/** Whether a part absent from the current inventory can still be drawn on request. */
export const revealsVisualParts = (source) =>
  Boolean(registrations.get(source)?.reveal);

/** Draw the state that holds part `id`, when the source can and does not already. */
export function revealRegisteredVisualPart(source, id) {
  const reveal = registrations.get(source)?.reveal;
  if (reveal && !registeredVisualPart(source, id)) reveal(id);
  return registeredVisualPart(source, id);
}

/** Why one source's registration breaks its `x-visual` declaration: an authored part
 * it does not register, and under `prefixes` a registered id no prefix admits. Under
 * `parts` the module may register more than the author named; the declaration picks
 * from that inventory. The current state's inventory is read; a declared part it lacks
 * is a problem only when the visual cannot reveal it, and `unrevealedVisualParts` asks
 * the reveal once nothing else needs the state the page opened in. */
export function visualPartProblems(source, declaration) {
  const admission = visualPartAdmission(source, declaration);
  if (!admission) return [];
  if (!hasVisualParts(source)) return ["did not call registerVisualParts"];
  try {
    const ids = registeredVisualParts(source).map((part) => part.id);
    const missing = revealsVisualParts(source)
      ? []
      : admission.declared.filter((id) => !ids.includes(id));
    const outside = declaration.prefixes
      ? ids.filter((id) => admission.rank(id) < 0)
      : [];
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
export function unrevealedVisualParts(source, declaration) {
  const declared = visualPartAdmission(source, declaration)?.declared ?? [];
  try {
    const missing = declared.filter((id) => !revealRegisteredVisualPart(source, id));
    return missing.length
      ? [`did not reveal declared parts ${missing.join(", ")}`]
      : [];
  } catch (error) {
    return [String(error?.message ?? error)];
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

export const registeredVisualPart = (source, id) =>
  registeredVisualParts(source).find((part) => part.id === id) ?? null;

export const registeredVisualPartLabel = (source, id) => {
  const current = registeredVisualPart(source, id)?.label;
  if (current) return current;
  const label = registrations.get(source)?.label?.(id);
  return words(label) || null;
};

export function registeredVisualPartAt(source, target, admits = () => true) {
  const byElement = new Map(
    registeredVisualParts(source)
      .filter(admits)
      .map((part) => [part.element, part]),
  );
  for (let current = target; current && current !== source; current = upFrom(current)) {
    const part = byElement.get(current);
    if (part) return part;
  }
  return null;
}
