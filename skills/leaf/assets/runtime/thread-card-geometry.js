/* Where the inline thread card stands, relative to the margin cluster that opened it.

   One rule with three postures. The card stands in the rail beside its cluster, top
   edges aligned, as wide as the room between the cluster and the visible edge allows
   within the card's minimum and preferred measures (`right`). When that room is under
   the minimum, the card keeps its right edge on the visible edge, takes the room from
   the cluster's left edge to that edge within the same measures, and stacks under the
   cluster when its whole height fits there (`below`), else on whichever side has the
   taller room, capped to it (`below` or `above`). Either way the controls that opened
   it stay uncovered, and it crosses the reading column by no more than the rail's
   shortfall. In every posture the card is clamped inside the boundary, so a scroll
   slides it with the cluster and then holds it at the boundary's edge until the cluster
   itself has left, which `detached` reports for the caller to act on.

   The inputs are client rectangles and lengths and the module reads no DOM, so the rule
   is arithmetic a test can state. `heightAt(width, maxHeight)` is the one measurement:
   the card's rendered height once it wears that width and cap, which the caller reads
   from the live card. */

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

export function threadCardGeometry({
  cluster,
  boundary,
  gap,
  minWidth,
  preferredWidth,
  heightAt,
}) {
  const preferred = Math.min(preferredWidth, boundary.width);
  const minimum = Math.min(minWidth, preferred);
  const detached = cluster.bottom <= boundary.top || cluster.top >= boundary.bottom;
  const beside = boundary.right - cluster.right - gap;
  if (beside >= minimum) {
    const width = Math.min(preferred, beside);
    const height = heightAt(width, boundary.height);
    return {
      placement: "right",
      x: cluster.right + gap,
      y: clamp(cluster.top, boundary.top, boundary.bottom - height),
      width,
      maxHeight: boundary.height,
      detached,
    };
  }
  const width = clamp(boundary.right - cluster.left, minimum, preferred);
  const below = boundary.bottom - Math.max(cluster.bottom + gap, boundary.top);
  const above = Math.min(cluster.top - gap, boundary.bottom) - boundary.top;
  const natural = heightAt(width, boundary.height);
  const placement = below >= natural || below >= above ? "below" : "above";
  const maxHeight = Math.max(0, placement === "below" ? below : above);
  const height = Math.min(natural, maxHeight);
  const y = placement === "below" ? cluster.bottom + gap : cluster.top - gap - height;
  return {
    placement,
    x: boundary.right - width,
    y: clamp(y, boundary.top, boundary.bottom - height),
    width,
    maxHeight,
    detached,
  };
}
