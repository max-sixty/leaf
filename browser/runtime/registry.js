/* The vocabulary's query doors, which is how the layer stays open.

   `elementDeclarations` and `tagsDeclaring` are the general iteration doors. `stateSpecs` is
   the one traversal of every tag's `x-state`, whichever side writes each verb. New code
   that loops over tag names or repeats that traversal is a closed list in another form. CSS selectors
   follow the same rule: a list of framed widget tags is still a closed consumer. */

import { runtime } from "./context.js";
import { isElementName } from "./registry-contract.js";

// The vocabulary, vendored per page: which tags a module upgrades, and which of their
// attributes are words the page says. Empty only during the real fetch interval, when
// the already-wired chrome can legitimately be used; a failed fetch still rejects
// startup rather than becoming an empty vocabulary.
export const registry = runtime.registry;
export const tokenEntry = (name) => registry.$reactions.tokens[name];

// Ordinary keys are the authoring vocabulary: exact custom-element names and CSS
// selectors. Only exact names are widget declarations; `lf-options.selected` is
// an idiom selector, by the `$names.widget` grammar Python reads too. Every widget
// traversal goes through this owner rather than treating all vocabulary as widgets.
export const elementDeclarations = () =>
  Object.entries(registry).filter(([tag]) => isElementName(tag));

// Take in the fetched vocabulary. A verb's writer is read from `$states`
// (`registry-contract.js`), where composition stamped it.
// The layer-wide `$` declarations are frozen as they arrive, so `layerFact` hands a
// package module the registry's own value, which it can read but not write.
export function adoptRegistry(declarations) {
  for (const [name, value] of Object.entries(declarations))
    if (name.startsWith("$")) freeze(value);
  Object.assign(registry, declarations);
}

/** @param {unknown} value */
function freeze(value) {
  if (value === null || typeof value !== "object" || Object.isFrozen(value)) return;
  for (const child of Object.values(value)) freeze(child);
  Object.freeze(value);
}

let stateIndex;
/** @param {import("../types/domain.js").StateRecord} record */
const recordSlot = (record) =>
  JSON.stringify([record.kind, "attr" in record ? record.attr : null]);
function indexedState() {
  const generation = registry.$layer?.generation;
  if (typeof generation !== "string" || !generation)
    throw new Error("leaf: state vocabulary requested before registry loaded");
  if (stateIndex?.generation === generation) return stateIndex;

  const specs = [];
  for (const [tag, entry] of elementDeclarations())
    for (const [verb, spec] of Object.entries(entry["x-state"] ?? {}))
      specs.push({ tag, verb, spec });
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

export const declarationFor = (el, key) => registry[el?.localName]?.[key];

// How a tag is decided, or null where no verb decides it: `verb`, the x-state verb whose
// detail `outcome` is the decision, and `retires`, each outcome's member tags that leave
// the page under it (x-retired-when). Composition stamps it into the vocabulary as
// `$decisions` (Python's `registry.contract.stamp_decisions`), so nothing here re-derives it.
export const decisionFor = (tag) => registry.$decisions[tag] ?? null;

export const elementsDeclaring = (root, key, { direct = false } = {}) => {
  const candidates = direct ? [...root.children] : [...root.querySelectorAll("*")];
  return candidates.filter((el) => declarationFor(el, key) !== undefined);
};

// Which widgets answer a question the way the caller means it, read from what they
// declare. Nothing out here names a widget: a behaviour some widgets want is an x- key
// they carry, so the twelfth widget is covered by its declaration alone — the alternative
// keeps working perfectly on the widget it was taught and silently does nothing for the
// next one.
export const tagsDeclaring = (holds) =>
  elementDeclarations()
    .filter(([, entry]) => holds(entry))
    .map(([tag]) => tag);

// Every declared attribute holds one of the admitted values. A boolean asks whether a
// flag is present; other values compare with the attribute's text. The lint holds each
// value to the attribute's schema.
export const matchesWhen = (el, when) =>
  Object.entries(when ?? {}).every(([attr, values]) =>
    values.some((value) =>
      typeof value === "boolean"
        ? el.hasAttribute(attr) === value
        : el.getAttribute(attr) === value,
    ),
  );

// An occurrence quotes its descendants only while its declared condition holds.
export const exhibits = (el, entry) => {
  const rule = entry?.["x-exhibit"];
  return typeof rule === "object" && rule !== null
    ? matchesWhen(el, rule.when)
    : !!rule;
};
