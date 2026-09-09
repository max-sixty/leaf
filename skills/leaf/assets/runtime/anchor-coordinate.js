/* Operations on durable anchor coordinates. */

// Anchors are shallow records of primitive coordinates. Compare the complete records:
// reading only the left operand's keys made a whole-visual anchor equal the part anchor
// that extended it, but not the other way around.
export const sameAnchor = (a, b) => {
  if (a === b) return true;
  if (!a || !b) return false;
  const left = Object.keys(a).sort();
  const right = Object.keys(b).sort();
  return (
    left.length === right.length &&
    left.every((key, index) => key === right[index] && a[key] === b[key])
  );
};
