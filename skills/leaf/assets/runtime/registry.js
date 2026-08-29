import { runtime } from "./context.js";

// The vocabulary, vendored per page: which tags a module upgrades, and which of their
// attributes are words the page says. Empty only during the real fetch interval, when
// the already-wired chrome can legitimately be used; a failed fetch still rejects
// startup rather than becoming an empty vocabulary.
export const registry = runtime.registry;

// The vocabulary's widgets: every entry under a tag, and never a `$` entry. Those are
// the layer's own facts, and one of them ($keys) is spelled in the x- keys' own names —
// so a sweep that picked widgets by "declares x-says" without asking the tag took it
// for a widget called $keys, and querySelectorAll refused the name. Every walk over the
// registry that means widgets goes through here.
export const widgetEntries = () =>
  Object.entries(registry).filter(([tag]) => tag.startsWith("lf-"));

// Shared `$` entries belong to the layer rather than to one widget. Return a copy so
// a package module can read its cross-widget vocabulary without a registry write path.
export function layerFact(name) {
  if (!name?.startsWith("$"))
    throw new Error(`leaf: layerFact expects a $ entry, got ${String(name)}`);
  const value = registry[name];
  return value === undefined ? undefined : structuredClone(value);
}

export const declarationFor = (el, key) => registry[el?.localName]?.[key];

export const elementsDeclaring = (root, key, { direct = false } = {}) => {
  const candidates = direct ? [...root.children] : [...root.querySelectorAll("*")];
  return candidates.filter((el) => declarationFor(el, key) !== undefined);
};

export function closestDeclaring(el, key) {
  for (let at = el; at; at = at.parentElement)
    if (declarationFor(at, key) !== undefined) return at;
  return null;
}

// Which widgets answer a question the way the caller means it, read from what they
// declare. Nothing out here names a widget: a behaviour some widgets want is an x- key
// they carry, so the twelfth widget is covered by its entry alone — the alternative
// keeps working perfectly on the widget it was taught and silently does nothing for the
// next one.
export const tagsDeclaring = (holds) =>
  widgetEntries()
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
