/* Package-owned semantic parts of a rendered visual.
 *
 * A package declares one ordered inventory. Leaf validates that inventory and derives
 * both directions it needs: a durable token resolves to the current rendered element,
 * and a rendered hit resolves to the nearest registered part. `surface` is the native
 * element whose paint Leaf should follow; it defaults to the semantic element, while a
 * package may name one descendant to exclude decorative paint from a compound part.
 * Invalid inventories throw at the read that consumes them; live readers do not
 * replace a package error with an empty inventory.
 *
 * Leaf puts the user on a part's element as it travels to the part or hands them back
 * from a comment on it. A visual whose parts are no places to stand, as the marks round
 * a chart's points are not, names `focus(id)` and takes that focus itself: Leaf calls
 * `focus(id)` as it places focus on the visual and at no other time (focus.js,
 * `FocusDestination`), and the visual settles on the part, as a chart moves its
 * reading to the point even where it holds focus already.
 *
 * A visual whose parts are too many to list, such as a chart's points, answers both
 * directions itself, so neither takes longer as the visual holds more. `find(id)`
 * returns the part a token names, drawing an element for it if it must, where Leaf
 * would otherwise search the inventory, and `read()` lists only the parts a reader may
 * pick from a list, which may be none. `at(node)` names the part a node of the visual
 * stands for where no registered element holds it: a hit on a drawing that draws no
 * element per part, such as a line through its data, which Leaf's aim and a pointed
 * comment ask, or the visual itself, which focus on it asks (`focusedVisualPart`),
 * where the visual holds focus on one of its parts. A chart answers with the point its
 * own aim is on, so Leaf's aim and comment land on what the chart shows the reader
 * rather than on whichever shape lies under the pointer.
 *
 * A visual that draws its parts over time (a timeline, an animation, a stepper) does not
 * hold every declared part at every moment. Its registration names `reveal(id)`, which
 * synchronously settles the visual on a state whose inventory holds that part,
 * including cancelling a pending replacement of an already visible destination. A
 * visual that finds its parts draws only those its state holds, as a chart draws no
 * point before it has room, in a shut tab, and a chart whose body reads its width may
 * draw a datum at one width and not another. In either, a declared part missing from
 * the current state stands in for the whole visual, until travel asks for it or the
 * visual draws it, rather than detaching. A label reader can name an absent part in
 * Threads without changing the visual's state.
 *
 * A reading of a visual's inventory reads its version (kept.js, `version`), so a
 * reading kept from it is made again after the visual's `update()`, which a reveal that
 * draws calls too, or a registration for a source it found none for. */

import { labelWords } from "./words.js";
import { under, upFrom } from "./shadow-tree.js";
import { layoutChanged } from "./widget-upgrade.js";
import { version } from "./kept.js";

/** @typedef {{id: string, element: Element, label: string, surface?: Element | null}} VisualPart
 * @typedef
 * {import("../types/contract.js").WidgetDeclaration["visual"]}
 * VisualDeclaration
 * @typedef {{read: () => Iterable<VisualPart>, reveal: ((id: string) => void) | null,
 * label: ((id: string) => string | null | undefined) | null,
 * find: ((id: string) => VisualPart | null | undefined) | null,
 * at: ((node: Element) => VisualPart | null | undefined) | null,
 * focus: ((id: string) => void) | null, drawn: import("./kept.js").Version}} Registration
 * @typedef {{reveal?: Registration["reveal"], label?: Registration["label"],
 * find?: Registration["find"], at?: Registration["at"],
 * focus?: Registration["focus"]}} RegistrationOptions */
/** @type {WeakMap<Element, Registration>} */
const registrations = new WeakMap();
// How many sources have registered, which a reading of a source with none reads.
const registered = version();

/** Register the current visual-part inventory for one rendered source.
 *
 * `read` returns ordered `{id, element, label, surface?}` records. Call `update()`
 * after any rendering or geometry change, including in-place attribute or style
 * changes; it emits the same layout signal used by every other package-owned geometry
 * change. `reveal(id)`, when given, settles the state that holds declared part `id`
 * before it returns, so the next `read` includes it and pending work cannot retire it.
 * It is called for visible destinations too. `label(id)` names a part absent from the
 * current state without revealing it. `find(id)`, when given, returns the record for
 * part `id` in the current state, or null, in place of a search of `read()`.
 * `at(node)`, when given, returns the record for the part a node of the visual stands
 * for where no element `read()` registers holds it, or null. `focus(id)`, when given,
 * settles the visual on part `id` as Leaf places focus on the visual for it.
 */
/** @param {Element} source @param {() => Iterable<VisualPart>} read
 * @param {RegistrationOptions} [options] */
export function registerVisualParts(
  source,
  read,
  { reveal = null, label = null, find = null, at = null, focus = null } = {},
) {
  if (registrations.has(source))
    throw new TypeError("A visual source may register its parts only once");
  // How many times the source has said its inventory may have changed.
  const drawn = version();
  registrations.set(source, {
    read,
    reveal,
    label,
    find,
    at,
    focus,
    drawn,
  });
  registered.move();
  return {
    update: () => {
      drawn.move();
      layoutChanged(source);
    },
  };
}

/** The part ids admitted by a whole-inventory opt-in or generated-id prefixes.
 * Registered inventory order is also the order of the visual's targets. */
/** @param {Element} visual @param {VisualDeclaration | null} declaration */
export function visualPartAdmission(visual, declaration) {
  if (!declaration || typeof declaration !== "object") return null;
  if ("prefixes" in declaration)
    return (/** @type {string} */ id) =>
      declaration.prefixes.some((prefix) => id !== prefix && id.startsWith(prefix));
  return visual.hasAttribute(declaration.parts) ? () => true : null;
}

/** Whether a part absent from the current state may still be drawn: on request, or
 * once the visual can. */
/** @param {Element} source */
export const drawsAbsentParts = (source) => {
  const registration = registrations.get(source);
  return Boolean(registration?.reveal || registration?.find);
};

/** Settle the requested part, even while old pixels await a replacement. */
/** @param {Element} source @param {string} id */
export function revealRegisteredVisualPart(source, id) {
  const reveal = registrations.get(source)?.reveal;
  if (reveal) reveal(id);
  return registeredVisualPart(source, id);
}

/** Invalid registrations or ids outside a provider's declared prefixes. */
/** @param {Element} source @param {VisualDeclaration | null} declaration */
export function visualPartProblems(source, declaration) {
  if (!declaration || typeof declaration !== "object") return [];
  if (!registrations.has(source)) return [{ kind: "unregistered" }];
  const parts = registeredVisualParts(source);
  const admission = visualPartAdmission(source, declaration);
  const outside =
    "prefixes" in declaration && admission
      ? parts.filter((part) => !admission(part.id)).map((part) => part.id)
      : [];
  return outside.length ? [{ kind: "unadmitted-parts", parts: outside }] : [];
}

// One record as Leaf reads it, its label in the words a label reads and its surface
// named, or a TypeError saying which rule it breaks.
/** @param {Element} source @param {VisualPart} part @param {string | number} number */
function checkedPart(source, part, number) {
  const id = part.id;
  const element = part.element;
  const label = labelWords(part.label);
  const surface = part.surface ?? element;
  if (typeof id !== "string" || !id || /\s/.test(id))
    throw new TypeError(`Visual part ${number} has no single-token id`);
  if (!(element instanceof Element) || element === source || !under(element, source))
    throw new TypeError(`Visual part ${id} has no descendant Element`);
  if (!label) throw new TypeError(`Visual part ${id} has no label`);
  if (!(surface instanceof Element) || !under(surface, element))
    throw new TypeError(`Visual part ${id} has no descendant Element surface`);
  return { id, element, label, surface };
}

/** @param {Element} source */
export function registeredVisualParts(source) {
  const registration = registrations.get(source);
  (registration?.drawn ?? registered).read();
  if (!registration) return [];
  const { read } = registration;
  const seenIds = new Set();
  const seenElements = new Set();
  const seenSurfaces = new Set();
  return [...read()].map((given, index) => {
    const part = checkedPart(source, given, index + 1);
    const { id, element, surface } = part;
    if (seenIds.has(id))
      throw new TypeError(`A visual source registered part ${id} twice`);
    if (seenElements.has(element))
      throw new TypeError("A visual source registered one element as two parts");
    if (seenSurfaces.has(surface))
      throw new TypeError("A visual source registered one surface for two parts");
    seenIds.add(id);
    seenElements.add(element);
    seenSurfaces.add(surface);
    return part;
  });
}

/** @param {Element} source @param {string} id */
export function registeredVisualPart(source, id) {
  const registration = registrations.get(source);
  const find = registration?.find;
  if (!find)
    return registeredVisualParts(source).find((part) => part.id === id) ?? null;
  registration.drawn.read();
  const found = find(id);
  if (!found) return null;
  const part = checkedPart(source, found, id);
  if (part.id !== id) throw new TypeError(`A visual source found ${part.id} for ${id}`);
  return part;
}

/** @param {Element} source @param {string} id */
export const registeredVisualPartLabel = (source, id) => {
  const current = registeredVisualPart(source, id)?.label;
  if (current) return current;
  const label = registrations.get(source)?.label?.(id);
  return labelWords(label) || null;
};

/** @param {Element} source @param {Element | null} target @param {(part: VisualPart) => boolean} [admits] */
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
  return target && target !== source ? namedAt(source, target, admits) : null;
}

/** Where Leaf puts the user for part `id`: its element, or the visual itself, settled
 * on the part by its `focus(id)` as focus is placed there.
 * @param {Element} source @param {string} id
 * @returns {import("./focus.js").FocusDestination | null} */
export function visualPartFocus(source, id) {
  const part = registeredVisualPart(source, id);
  const focus = registrations.get(source)?.focus;
  if (!part || !focus) return part?.element ?? null;
  return { element: source, settle: () => focus(id) };
}

/** The part a visual holding focus stands on, as a chart's keys put the reader on a
 * point: what `at` names for the visual itself. */
/** @param {Element} source @param {(part: VisualPart) => boolean} [admits] */
export const focusedVisualPart = (source, admits = () => true) =>
  namedAt(source, source, admits);

/** @param {Element} source @param {Element} node
 * @param {(part: VisualPart) => boolean} admits */
function namedAt(source, node, admits) {
  const named = registrations.get(source)?.at?.(node);
  if (!named) return null;
  const part = checkedPart(source, named, "at the hit");
  return admits(part) ? part : null;
}
