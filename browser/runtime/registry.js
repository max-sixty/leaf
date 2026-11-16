/* The vocabulary's query doors, which is how the layer stays open.

   `elementDeclarations` and `tagsDeclaring` are the general iteration doors. `stateSpecs` is
   the one traversal of every tag's `x-state`, whichever side writes each verb. New code
   that loops over tag names or repeats that traversal is a closed list in another form. CSS selectors
   follow the same rule: a list of framed widget tags is still a closed consumer. */

import { installLanguagePaths } from "./language-paths.js";
import { runtime } from "./context.js";
import { isElementName } from "./registry-contract.js";

// The vocabulary, composed per page: which tags a module upgrades, and which of their
// attributes are words the page says. Empty only during the real fetch interval, when
// the already-wired chrome can legitimately be used; a failed fetch still rejects
// startup rather than becoming an empty vocabulary.
/** A deciding verb and the member tags each outcome retires, stamped by registry.contract.stamp_decisions.
 * @typedef {{verb: string, retires: Record<string, readonly string[]>}} Decision */
export const registry = runtime.registry;
/** @param {string} name */
export const tokenEntry = (name) => registry.$reactions?.tokens[name];

// A reading of the vocabulary, kept until its generation says the vocabulary changed,
// since a reader that asks for each command a page declares redoes it many times for
// one input.
/** @template T @param {() => T} read @returns {() => T} */
export function perVocabulary(read) {
  /** @type {{generation: string, value: T} | undefined} */
  let kept;
  return () => {
    const generation = registry.$layer?.generation;
    if (kept && kept.generation === generation) return kept.value;
    const value = read();
    if (generation) kept = { generation, value };
    return value;
  };
}

// Ordinary keys are the authoring vocabulary: exact custom-element names and CSS
// selectors. Only exact names are widget declarations; `lf-options.selected` is
// an idiom selector, by the `$names.widget` grammar Python reads too. Every widget
// traversal goes through this owner rather than treating all vocabulary as widgets.
/** @typedef {import("../types/contract.js").WidgetDeclaration} WidgetDeclaration */
/** @type {() => readonly [string, WidgetDeclaration][]} */
export const elementDeclarations = perVocabulary(() =>
  Object.entries(registry).filter(([tag]) => isElementName(tag)),
);

// Take in the fetched vocabulary. A verb's writer is read from `$states`
// (`registry-contract.js`), where composition stamped it.
// The layer-wide `$` declarations are frozen as they arrive, so `layerFact` hands a
// package module the registry's own value, which it can read but not write.
/** @param {typeof registry} declarations */
export function adoptRegistry(declarations) {
  for (const [name, value] of Object.entries(declarations))
    if (name.startsWith("$")) freeze(value);
  Object.assign(registry, declarations);
  if (declarations.$languages) installLanguagePaths(declarations.$languages.paths);
}

/** @param {unknown} value */
function freeze(value) {
  if (value === null || typeof value !== "object" || Object.isFrozen(value)) return;
  for (const child of Object.values(value)) freeze(child);
  Object.freeze(value);
}

/** @typedef {{generation: string, recordSelectors: Map<string, string>, specs: {tag: string, verb: string, spec: import("../types/domain.js").ActionSpec}[]}} StateIndex */
/** @type {StateIndex | undefined} */
let stateIndex;
/** @param {import("../types/domain.js").StateRecord} record */
const recordSlot = (record) =>
  JSON.stringify([record.kind, "attr" in record ? record.attr : null]);
function indexedState() {
  const generation = registry.$layer?.generation;
  if (typeof generation !== "string" || !generation)
    throw new Error("leaf: state vocabulary requested before registry loaded");
  if (stateIndex?.generation === generation) return stateIndex;

  /** @type {StateIndex["specs"]} */
  const specs = [];
  for (const [tag, entry] of elementDeclarations())
    for (const [verb, spec] of Object.entries(entry["x-state"] ?? {}))
      specs.push({ tag, verb, spec });
  /** @type {Map<string, Set<string>>} */
  const recordTags = new Map();
  for (const { tag, spec } of specs) {
    if (!spec.record) continue;
    const slot = recordSlot(spec.record);
    const tags = recordTags.get(slot) ?? new Set();
    tags.add(tag);
    recordTags.set(slot, tags);
  }
  const recordSelectors = new Map(
    [...recordTags].map(([slot, tags]) => [slot, [...tags].join(",")]),
  );
  stateIndex = { generation, recordSelectors, specs };
  return stateIndex;
}

export const stateSpecs = () => indexedState().specs;
/** @param {import("../types/domain.js").StateRecord} record */
export const recordedWidgetSelector = (record) =>
  indexedState().recordSelectors.get(recordSlot(record)) ?? "";

// Shared `$` declarations belong to the layer rather than to one widget. Each is frozen
// on adoption, so a package module reads its cross-widget vocabulary without a registry
// write path, and a reader called per element copies nothing.
/** @param {string} name */
export const layerFact = (name) => registry[name];

/** @template {keyof WidgetDeclaration} K @param {Element | null | undefined} el @param {K} key @returns {WidgetDeclaration[K] | undefined} */
export const declarationFor = (el, key) =>
  el ? registry[el.localName]?.[key] : undefined;

// How a tag is decided, or null where no verb decides it: `verb`, the x-state verb whose
// detail `outcome` is the decision, and `retires`, each outcome's member tags that leave
// the page under it (the verb's `retires`). Composition stamps it into the vocabulary as
// `$decisions` (Python's `registry.contract.stamp_decisions`), so nothing here re-derives it.
/** @param {string} tag @returns {Decision | null} */
export const decisionFor = (tag) => registry.$decisions[tag] ?? null;

// The widgets at or under `root` whose declaration `holds` answers for, in document
// order. The browser matches their tags, so a root holding a long document of plain
// rows, as a tab set's panel can, costs a native match of each row rather than a
// script's look at it. The match costs more for each tag it names: on #4781's page,
// every declared tag took 0.4 s over the 30 panels where the few declaring `x-awaits`
// took 0.05 s, so a question about some widgets names only theirs.
/** @param {Document | DocumentFragment | Element} root @param {(entry: WidgetDeclaration) => unknown} [holds] */
export const declaredElements = (root, holds = () => true) => {
  const tags = tagsDeclaring(holds);
  if (!tags.length) return [];
  const selector = tags.join(",");
  const found = [...root.querySelectorAll(selector)];
  if (root instanceof Element && root.matches(selector)) found.unshift(root);
  return found;
};

/** @param {Document | DocumentFragment | Element} root @param {keyof WidgetDeclaration} key @param {{direct?: boolean}} [options] */
export const elementsDeclaring = (root, key, { direct = false } = {}) =>
  direct
    ? [...root.children].filter((el) => declarationFor(el, key) !== undefined)
    : declaredElements(root, (entry) => entry[key] !== undefined).filter(
        (el) => el !== root,
      );

// Which widgets answer a question the way the caller means it, read from what they
// declare. Nothing out here names a widget: a behaviour some widgets want is an x- key
// they carry, so the twelfth widget is covered by its declaration alone — the alternative
// keeps working perfectly on the widget it was taught and silently does nothing for the
// next one.
/** @param {(entry: WidgetDeclaration, tag: string) => unknown} holds */
export const tagsDeclaring = (holds) =>
  elementDeclarations()
    .filter(([tag, entry]) => holds(entry, tag))
    .map(([tag]) => tag);

// Whether a module upgrades a tag. Composition derives `$modules` from the files it
// composes (Python's `registry.contract.MODULES`): a module at `widgets/<tag>.js` is
// what makes a tag an upgraded widget, and no declaration says so.
/** @param {string} tag @returns {boolean} */
export const upgrades = (tag) => Object.hasOwn(registry.$modules ?? {}, tag);

// Every declared attribute holds one of the admitted values. A boolean asks whether a
// flag is present; other values compare with the attribute's text. The lint holds each
// value to the attribute's schema.
/** @param {Element} el @param {Record<string, readonly (string | boolean)[]> | null | undefined} when */
export const matchesWhen = (el, when) =>
  Object.entries(when ?? {}).every(([attr, values]) =>
    values.some((value) =>
      typeof value === "boolean"
        ? el.hasAttribute(attr) === value
        : el.getAttribute(attr) === value,
    ),
  );

// An occurrence quotes its descendants only while its declared condition holds.
/** @param {Element} el @param {WidgetDeclaration | null | undefined} entry */
export const exhibits = (el, entry) => {
  const rule = entry?.["x-exhibit"];
  return typeof rule === "object" && rule !== null
    ? matchesWhen(el, rule.when)
    : !!rule;
};
