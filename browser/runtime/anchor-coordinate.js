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
