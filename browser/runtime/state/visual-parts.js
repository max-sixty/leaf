/* Package-owned semantic parts of a rendered visual.
 *
 * A visual states one ordered inventory: the parts its nodes mark, or what the
 * element's `lfParts` says, read off the element at each reading so that a plain
 * element or another library's component states it without importing Leaf. Leaf
 * validates that inventory and derives
 * both directions it needs: a durable token resolves to the current rendered element,
 * and a rendered hit resolves to the nearest part it names. `surface` is the native
 * element whose paint Leaf should follow; it defaults to the semantic element, while a
 * package may name one descendant to exclude decorative paint from a compound part.
 * Invalid inventories throw at the read that consumes them; live readers do not
 * replace a package error with an empty inventory.
 *
 * Leaf puts the user on a part's element as it travels to the part or hands them back
 * from a comment on it. A visual whose parts are no places to stand, as the marks round
 * a chart's points are not, names `focus(id)` and takes that focus itself: Leaf calls
 * `focus(id)` as it places focus on the visual and at no other time (dom/focus.js,
 * `FocusDestination`), and the visual settles on the part, as a chart moves its
 * reading to the point even where it holds focus already.
 *
 * A visual whose parts are too many to list, such as a chart's points, answers both
 * directions itself, so neither takes longer as the visual holds more. `find(id)`
 * returns the part a token names, drawing an element for it if it must, where Leaf
 * would otherwise search the inventory, and `read()` lists only the parts a reader may
 * pick from a list, which may be none. `at(node)` names the part a node of the visual
 * stands for where no element the inventory names holds it: a hit on a drawing that draws no
 * element per part, such as a line through its data, which Leaf's aim and a pointed
 * comment ask, or the visual itself, which focus on it asks (`focusedVisualPart`),
 * where the visual holds focus on one of its parts. A chart answers with the point its
 * own aim is on, so Leaf's aim and comment land on what the chart shows the reader
 * rather than on whichever shape lies under the pointer.
 *
 * A visual that draws its parts over time (a timeline, an animation, a stepper) does not
 * hold every declared part at every moment. Its `lfParts` names `reveal(id)`, which
 * synchronously settles the visual on a state whose inventory holds that part,
 * including cancelling a pending replacement of an already visible destination. A
 * visual that finds its parts draws only those its state holds, as a chart draws no
 * point before it has room, in a shut tab, and a chart whose body reads its width may
 * draw a datum at one width and not another. In either, a declared part missing from
 * the current state stands in for the whole visual, until travel asks for it or the
 * visual draws it, rather than detaching. A label reader can name an absent part in
 * Threads without changing the visual's state.
 *
 * A visual whose `lfParts` gives no `read` marks its parts instead: each node in its
 * light tree carrying `data-lf-part="<id>"` is the part of that id, named by its
 * `aria-label` or else its words, in document order. A mark under a visual standing
 * inside the source is that visual's, by the page's declarations (`declaredVisuals`).
 * Marks and `lfParts` are read as they stand, and a reading kept from either is made
 * again once a layout change is said on the visual or inside it (lib/widget-events.js,
 * `LAYOUT`), which a visual says after it draws, a reveal that draws included, and Leaf
 * says for an element each time it sets the element's properties
 * (host/element-integration.js). A change said elsewhere leaves the reading kept, so a
 * film playing on the page doesn't make every other visual read its parts again.
 *
 * Beside each visual's count, the module keeps one of every layout change said in the
 * page (`layoutsChanged`), for a reading of what widgets draw that has no single
 * visual to ask about, such as whether a picture is a control's (readings/anchor-resolution.js)
 * or where a frame's entries stand (readings/reading-place.js). */

import { labelWords } from "../lib/words.js";
import { under, upFrom } from "../lib/shadow-tree.js";
import { LAYOUT } from "../lib/widget-events.js";
import { version } from "./kept.js";

/** @typedef {{id: string, element: Element, label: string, surface?: Element | null}} VisualPart
 * @typedef
 * {import("../../types/contract.js").WidgetDeclaration["visual"]}
 * VisualDeclaration
 * @typedef {{read?: () => Iterable<VisualPart>, reveal?: (id: string) => void,
 * label?: (id: string) => string | null | undefined,
 * find?: (id: string) => VisualPart | null | undefined,
 * at?: (node: Element) => VisualPart | null | undefined,
 * focus?: (id: string) => void}} Parts */

// Whether an element is a visual of its own, as the page declares them
// (readings/anchor-resolution.js). A document that says nothing has none.
/** @type {(element: Element) => boolean} */
let isVisual = () => false;
/** @param {(element: Element) => boolean} declared */
export const declaredVisuals = (declared) => {
  isVisual = declared;
};

// How many times an element in the page has said its layout changed, which a reader of
// what widgets draw that the page's reading doesn't hear reads (kept.js, `version`).
// The count is taken as the event starts down from the window, so it has moved before
// any listener the event reaches reads it.
const layouts = version();
export const layoutsChanged = () => layouts.read();
addEventListener(LAYOUT, () => layouts.move(), { capture: true });

// How many times a layout change has been said on each visual a reading has asked
// about, or inside it: the elements an `lf-layout` event passes on its way out.
/** @type {WeakMap<Element, import("./kept.js").Version>} */
const drawings = new WeakMap();
document.addEventListener(LAYOUT, (event) => {
  for (const node of event.composedPath())
    if (node instanceof Element) drawings.get(node)?.move();
});

// The parts a source's nodes mark, less those under a visual standing inside it.
/** @param {Element} source @returns {VisualPart[]} */
const markedParts = (source) =>
  [...source.querySelectorAll("[data-lf-part]")].flatMap((element) => {
    for (let at = element.parentElement; at && at !== source; at = at.parentElement)
      if (isVisual(at)) return [];
    const id = element.getAttribute("data-lf-part") ?? "";
    const label = element.getAttribute("aria-label") ?? element.textContent;
    return [{ id, element, label }];
  });

/** What a source's `lfParts` says, read as each reading asks, so a reading kept from it
 * is made again once the visual says its layout changed.
 *
 * `read()` returns ordered `{id, element, label, surface?}` records, where the
 * source's marks don't say them. `reveal(id)` settles the state that holds declared
 * part `id` before it returns, so the next `read` includes it and pending work cannot
 * retire it. It is called for visible destinations too. `label(id)` names a part
 * absent from the current state without revealing it. `find(id)` returns the record
 * for part `id` in the current state, or null, in place of a search of `read()`.
 * `at(node)` returns the record for the part a node of the visual stands for where no
 * element `read()` gives holds it, or null. `focus(id)` settles the visual on part
 * `id` as Leaf places focus on the visual for it. */
/** @param {Element} source @returns {Parts | undefined} */
const partsOf = (source) => {
  let drawn = drawings.get(source);
  if (!drawn) drawings.set(source, (drawn = version()));
  drawn.read();
  return source.lfParts;
};

/** The part ids a visual's declared prefixes admit. The inventory's order is also the
 * order of the visual's targets. */
/** @param {VisualDeclaration | null} declaration */
export function visualPartAdmission(declaration) {
  if (!declaration || typeof declaration !== "object") return null;
  return (/** @type {string} */ id) =>
    declaration.prefixes.some((prefix) => id !== prefix && id.startsWith(prefix));
}

/** Whether a part absent from the current state may still be drawn: on request, or
 * once the visual can. */
/** @param {Element} source */
export const drawsAbsentParts = (source) => {
  const parts = partsOf(source);
  return Boolean(parts?.reveal || parts?.find);
};

/** Settle the requested part, even while old pixels await a replacement. */
/** @param {Element} source @param {string} id */
export function revealRegisteredVisualPart(source, id) {
  partsOf(source)?.reveal?.(id);
  return registeredVisualPart(source, id);
}

/** Invalid records, or ids outside a provider's declared prefixes. A visual that
 * offers no part has none: with marks, an empty inventory is a state its drawing can
 * be in, and the picture is then one target. */
/** @param {Element} source @param {VisualDeclaration | null} declaration */
export function visualPartProblems(source, declaration) {
  const admits = visualPartAdmission(declaration);
  if (!admits) return [];
  const outside = registeredVisualParts(source)
    .filter((part) => !admits(part.id))
    .map((part) => part.id);
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

/** The source's inventory, each record checked: what its `lfParts` reads, or the parts
 * it marks. */
/** @param {Element} source */
export function registeredVisualParts(source) {
  const read = partsOf(source)?.read ?? (() => markedParts(source));
  const seenIds = new Set();
  const seenElements = new Set();
  const seenSurfaces = new Set();
  return [...read()].map((given, index) => {
    const part = checkedPart(source, given, index + 1);
    const { id, element, surface } = part;
    if (seenIds.has(id)) throw new TypeError(`A visual source names part ${id} twice`);
    if (seenElements.has(element))
      throw new TypeError("A visual source names one element as two parts");
    if (seenSurfaces.has(surface))
      throw new TypeError("A visual source names one surface for two parts");
    seenIds.add(id);
    seenElements.add(element);
    seenSurfaces.add(surface);
    return part;
  });
}

/** @param {Element} source @param {string} id */
export function registeredVisualPart(source, id) {
  const find = partsOf(source)?.find;
  if (!find)
    return registeredVisualParts(source).find((part) => part.id === id) ?? null;
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
  const label = partsOf(source)?.label?.(id);
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
 * @returns {Element | {element: Element, settle: () => void} | null} */
export function visualPartFocus(source, id) {
  const part = registeredVisualPart(source, id);
  const focus = partsOf(source)?.focus;
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
  const named = partsOf(source)?.at?.(node);
  if (!named) return null;
  const part = checkedPart(source, named, "at the hit");
  return admits(part) ? part : null;
}
