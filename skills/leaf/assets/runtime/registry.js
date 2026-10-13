/* The vocabulary's query doors, which is how the layer stays open.

   `elementDeclarations` and `tagsDeclaring` are the general iteration doors. `stateSpecs` is
   the one traversal of every tag's `x-state`, whichever side writes each verb. New code
   that loops over tag names or repeats that traversal is a closed list in another form. CSS selectors
   follow the same rule: a list of framed widget tags is still a closed consumer. */

import { runtime } from "./context.js";
import { isElementName } from "./registry-contract.js";
import { vocabularyFor, vocabularies } from "./widget-contexts.js";
import { readPart } from "./semantic-state.js";

// The vocabulary, vendored per page: which tags a module upgrades, and which of their
// attributes are words the page says. Empty only during the real fetch interval, when
// the already-wired chrome can legitimately be used; a failed fetch still rejects
// startup rather than becoming an empty vocabulary.
export const registry = runtime.registry;
// Shared chrome follows the viewed document; frozen content reads its node's registry.
// Each read through its part of the root (`readPart`), so a command reading it is not
// tied to every publication.
export const reactionVocabulary = readPart(
  (root) => root.document.registry.$reactions?.tokens ?? {},
);
const descriptors = readPart((root) => root.document.descriptors);

// Ordinary keys are the authoring vocabulary: exact custom-element names and CSS
// selectors. Only exact names are widget declarations; `lf-options.selected` is
// an idiom selector. This is Python's schema.WIDGET_NAME grammar. Every widget
// traversal goes through this owner rather than treating all vocabulary as widgets.
export const registryFor = (node) => vocabularyFor(node)?.declarations ?? registry;
export const elementDeclarations = (declarations = registry) =>
  Object.entries(declarations).filter(([tag]) => isElementName(tag));

// Take in the fetched vocabulary. A verb's writer is read from `$states`
// (`registry-contract.js`), where composition stamped it.
export function adoptRegistry(declarations) {
  Object.assign(registry, declarations);
}

const stateIndexes = new WeakMap();
function indexedState(declarations) {
  const stateIndex = stateIndexes.get(declarations);
  const generation = declarations.$layer?.generation;
  if (typeof generation !== "string" || !generation)
    throw new Error("leaf: state vocabulary requested before registry loaded");
  if (stateIndex?.generation === generation) return stateIndex;

  const specs = [];
  for (const [tag, entry] of elementDeclarations(declarations))
    for (const [verb, spec] of Object.entries(entry["x-state"] ?? {}))
      specs.push({ tag, verb, spec });
  const indexed = {
    generation,
    recordedWidgetSelector: [
      ...new Set(specs.filter(({ spec }) => spec.record).map(({ tag }) => tag)),
    ].join(","),
    specs,
  };
  stateIndexes.set(declarations, indexed);
  return indexed;
}

/** @param {Document | DocumentFragment | Element} scope */
export const stateSpecs = (scope = document) => indexedState(registryFor(scope)).specs;
/** @param {Document | DocumentFragment | Element} scope */
export const recordedWidgetSelector = (scope = document) =>
  indexedState(registryFor(scope)).recordedWidgetSelector;

// Shared `$` declarations follow the owner's publication. Return a copy so a package
// module can read its cross-widget vocabulary without a registry write path.
export function layerFact(owner, name) {
  const value = registryFor(owner)[name];
  return value === undefined ? undefined : structuredClone(value);
}

export const declarationFor = (el, key) => registryFor(el)[el?.localName]?.[key];
export const widgetDeclaration = (id, key) => descriptors().get(id)?.declaration[key];

// How a tag is decided, or null where no verb decides it: `verb`, the x-state verb whose
// detail `outcome` is the decision, and `retires`, each outcome's member tags that leave
// the page under it (x-retired-when). Composition stamps it into the vocabulary as
// `$decisions` (Python's `registry.contract.stamp_decisions`), so nothing here re-derives it.
export const decisionFor = (element) =>
  registryFor(element).$decisions[element.localName] ?? null;

export const elementsDeclaring = (root, key, { direct = false } = {}) => {
  const candidates = direct ? [...root.children] : [...root.querySelectorAll("*")];
  return candidates.filter((el) => declarationFor(el, key) !== undefined);
};

// Which widgets answer a question the way the caller means it, read from what they
// declare. Nothing out here names a widget: a behaviour some widgets want is an x- key
// they carry, so the twelfth widget is covered by its declaration alone — the alternative
// keeps working perfectly on the widget it was taught and silently does nothing for the
// next one.
export const tagsDeclaring = (holds, scope = null) => [
  ...new Set(
    (scope
      ? [registryFor(scope)]
      : [registry, ...vocabularies().map((context) => context.declarations)]
    ).flatMap((declarations) =>
      elementDeclarations(declarations)
        .filter(([, entry]) => holds(entry))
        .map(([tag]) => tag),
    ),
  ),
];

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
