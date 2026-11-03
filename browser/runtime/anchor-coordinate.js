// @ts-check
/* Operations on durable anchor coordinates. */

// Anchors are shallow records of primitive coordinates. When an emitter identifies a
// subject, source_revision and datum describe the observed rendering; identity names
// the subject across replacements. Every other field still distinguishes coordinates:
// a whole visual is not its part, and one quoted passage is not another.
//
// `anchorKey` is that identity as one string, the primitive fields in key order, so
// whatever keys a record by its anchor agrees with `sameAnchor`. Null keys as the empty
// record.
const RENDERING = new Set(["source_revision", "datum"]);
const PRIMITIVE = new Set(["string", "number", "boolean"]);
/** @typedef {Readonly<Record<string, unknown>>} Anchor */

/** @param {Anchor | null | undefined} anchor */
export const anchorKey = (anchor) => {
  const identified = typeof anchor?.identity === "string";
  return JSON.stringify(
    Object.entries(anchor ?? {})
      .filter(
        ([key, value]) =>
          PRIMITIVE.has(typeof value) && !(identified && RENDERING.has(key)),
      )
      .sort(([left], [right]) => left.localeCompare(right)),
  );
};

/** @param {Anchor | null | undefined} a @param {Anchor | null | undefined} b */
export const sameAnchor = (a, b) =>
  a === b || (Boolean(a) && Boolean(b) && anchorKey(a) === anchorKey(b));

// A URL fragment names an element by its id, `#<id>`, or a part of a widget by the
// widget's id and a key the widget answers (`addressedElements`), `#<id>:<key>`, as
// `#build-log:3-5` names lines 3 to 5 of a code block. Resolution reads the whole
// fragment as an id first (anchor-resolution.js, `fragmentAddress`), so an authored id
// holding a colon keeps its link. A widget's id is split at the fragment's first colon,
// and `fragmentUrl` percent-encodes any colon in the id; the key is the rest, decoded
// once, so a key may hold colons and slashes of its own.
//
// Rejected: a query parameter beside the fragment, as a thread's link is
// (`?thread=<id>`). A link in a reply must stay in the document, and only a change of
// fragment does. Also rejected: a separator HTML forbids in an id, such as a space,
// which spells `#items%20b/3` in every link an agent writes.
/** @param {string} raw */
const decoded = (raw) => {
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
};

/** @param {string} fragment */
export const fragmentId = (fragment) => decoded(fragment.slice(1));

/** The widget id and key a fragment spells as `#<id>:<key>`, or null.
 * @param {string} fragment @returns {{id: string, key: string} | null} */
export function fragmentKey(fragment) {
  const raw = fragment.slice(1);
  const at = raw.indexOf(":");
  if (at < 1 || at === raw.length - 1) return null;
  return { id: decoded(raw.slice(0, at)), key: decoded(raw.slice(at + 1)) };
}

/** This page's URL with a fragment naming `element`, or the part of it `key` names.
 * The URL parser encodes what a fragment can't hold; escaping `%` first keeps a key
 * that holds one, such as a diagram's `node:Line%20Item`, from decoding to another.
 * @param {Element} element @param {string | null} [key] */
export function fragmentUrl(element, key = null) {
  const id = encodeURIComponent(element.id);
  const part = key === null ? "" : `:${key.replaceAll("%", "%25")}`;
  return new URL(`#${id}${part}`, location.href).href;
}
