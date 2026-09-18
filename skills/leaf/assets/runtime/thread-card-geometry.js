/* Where the inline thread card stands, relative to the margin cluster that opened it.

   The card has a preferred spot, and the visible boundary has the last word. Beside
   the cluster is preferred: in the rail, top edges aligned, as wide as the room between
   the cluster and the visible edge allows within the card's minimum and preferred
   measures (`right`). When that room is under the minimum, the card keeps its right
   edge on the visible edge, takes the room from the cluster's left edge to that edge
   within the same measures, and stands under the cluster when its whole height fits
   there (`below`), else over it when it fits there (`above`), else under it again. It
   crosses the reading column by no more than the rail's shortfall.

   The card is never shortened to make any of that true. Its height is capped by the
   boundary alone, and the spot is then clamped inside the boundary, so a card too tall
   for the room under or over its cluster slides across the controls that opened it
   rather than shrinking to spare them. The same clamp is what a scroll meets: the card
   slides with its cluster, then holds at the boundary's edge until the cluster itself
   has left, which `detached` reports for the caller to act on.

   The inputs are client rectangles and lengths and the module reads no DOM, so the rule
   is arithmetic a test can state. `heightAt(width)` is the one measurement: the card's
   rendered height at that width under the boundary's height cap, which the caller
   reads from the live card. */

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
  const room = boundary.right - cluster.right - gap;
  const beside = room >= minimum;
  const width = beside
    ? Math.min(preferred, room)
    : clamp(boundary.right - cluster.left, minimum, preferred);
  const height = heightAt(width);
  const under = cluster.bottom + gap;
  const over = cluster.top - gap - height;
  const placement = beside
    ? "right"
    : under + height <= boundary.bottom || over < boundary.top
      ? "below"
      : "above";
  const y = { right: cluster.top, below: under, above: over }[placement];
  return {
    placement,
    x: beside ? cluster.right + gap : boundary.right - width,
    y: clamp(y, boundary.top, boundary.bottom - height),
    width,
    detached: cluster.bottom <= boundary.top || cluster.top >= boundary.bottom,
  };
}
