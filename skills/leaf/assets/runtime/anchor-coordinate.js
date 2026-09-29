/* Operations on durable anchor coordinates. */

// Anchors are shallow records of primitive coordinates. When an emitter identifies a
// subject, source_revision and datum describe the observed rendering; identity names
// the subject across replacements. Every other field still distinguishes coordinates:
// a whole visual is not its part, and one quoted passage is not another.
export const sameAnchor = (a, b) => {
  if (a === b) return true;
  if (!a || !b) return false;
  const identified = typeof a.identity === "string" && typeof b.identity === "string";
  const keys = (anchor) =>
    Object.keys(anchor)
      .filter((key) => !identified || (key !== "source_revision" && key !== "datum"))
      .sort();
  const left = keys(a);
  const right = keys(b);
  return (
    left.length === right.length &&
    left.every((key, index) => key === right[index] && a[key] === b[key])
  );
};
