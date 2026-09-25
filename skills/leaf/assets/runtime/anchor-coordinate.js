/* Operations on durable anchor coordinates. */

// Anchors are shallow records of primitive coordinates. For a declared keyed record,
// source_revision says which value was observed, while section/source/datum name the
// target across replacements. Every other field still distinguishes coordinates:
// a whole visual is not its part, and one quoted passage is not another.
export const sameAnchor = (a, b) => {
  if (a === b) return true;
  if (!a || !b) return false;
  const keyed = a.keyed === true && b.keyed === true;
  const keys = (anchor) =>
    Object.keys(anchor)
      .filter((key) => !keyed || key !== "source_revision")
      .sort();
  const left = keys(a);
  const right = keys(b);
  return (
    left.length === right.length &&
    left.every((key, index) => key === right[index] && a[key] === b[key])
  );
};
