/* The vocabulary's query doors, which is how the layer stays open.

   `elementDeclarations` and `tagsDeclaring` are the general iteration doors. `stateSpecs` is
   the one traversal of every tag's `x-state`, whichever side writes each verb. New code
   that loops over tag names or repeats that traversal is a closed list in another form. CSS selectors
   follow the same rule: a list of framed widget tags is still a closed consumer. */

import { runtime } from "./context.js";

// The vocabulary, vendored per page: which tags a module upgrades, and which of their
// attributes are words the page says. Empty only during the real fetch interval, when
// the already-wired chrome can legitimately be used; a failed fetch still rejects
// startup rather than becoming an empty vocabulary.
export const registry = runtime.registry;
export const tokenEntry = (name) => registry.$reactions.tokens[name];

// The vocabulary's element declarations: every declaration under a tag, and never a `$`
// declaration. Those are
// the layer's own facts, and one of them ($keys) is spelled in the x- keys' own names —
// so a sweep that picked widgets by "declares x-says" without asking the tag took it
// for a widget called $keys, and querySelectorAll refused the name. Every walk over the
// registry that means element declarations goes through here.
export const elementDeclarations = () =>
  Object.entries(registry).filter(([tag]) => tag.startsWith("lf-"));

// Take in the fetched vocabulary. A verb's writer is resolved here, once: `agent` where
// its declaration says so, else `user`, the rule Python's `registry.contract.verb_writer`
// states. Every browser reading, a widget descriptor's captured declaration included,
// then reads `spec.writer` as one of the two sides rather than restating the default.
export function adoptRegistry(declarations) {
  Object.assign(registry, declarations);
  for (const [, entry] of elementDeclarations())
    for (const spec of Object.values(entry["x-state"] ?? {})) spec.writer ??= "user";
}

let stateIndex;
function indexedState() {
  const generation = registry.$layer?.generation;
  if (typeof generation !== "string" || !generation)
    throw new Error("leaf: state vocabulary requested before registry loaded");
  if (stateIndex?.generation === generation) return stateIndex;

  const specs = [];
  for (const [tag, entry] of elementDeclarations())
    for (const [verb, spec] of Object.entries(entry["x-state"] ?? {}))
      specs.push({ tag, verb, spec });
  stateIndex = {
    generation,
    recordedWidgetSelector: [
      ...new Set(specs.filter(({ spec }) => spec.record).map(({ tag }) => tag)),
    ].join(","),
    specs,
  };
  return stateIndex;
}

export const stateSpecs = () => indexedState().specs;
export const recordedWidgetSelector = () => indexedState().recordedWidgetSelector;

// Shared `$` declarations belong to the layer rather than to one widget. Return a copy so
// a package module can read its cross-widget vocabulary without a registry write path.
export function layerFact(name) {
  if (!name?.startsWith("$"))
    throw new Error(`leaf: layerFact expects a $ declaration, got ${String(name)}`);
  const value = registry[name];
  return value === undefined ? undefined : structuredClone(value);
}

export const declarationFor = (el, key) => registry[el?.localName]?.[key];

// The x-state verb whose detail `outcome` decides which of a tag's retirable members
// leave the page (x-retired-when), the same reserved field Python's `deciding_verb`
// reads.
export const decidingVerb = (tag) =>
  Object.entries(registry[tag]?.["x-state"] ?? {}).find(
    ([, spec]) => "outcome" in (spec.detail?.properties ?? {}),
  )?.[0] ?? null;

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
