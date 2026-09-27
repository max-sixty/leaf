/* Where the inline thread card stands, relative to the margin cluster that opened it.

   The card has a preferred spot, and the visible boundary has the last word. Beside
   the cluster is preferred: in the rail, top edges aligned, as wide as the room between
   the cluster and the visible edge allows within the card's minimum and preferred
   measures (`right`). When that room is under the minimum, the card keeps its right
   edge on the visible edge, takes the room from the cluster's left edge to that edge
   within the same measures, and stands under the cluster when its whole height fits
   there (`below`), else over it when it fits there (`above`), else under it again. It
   crosses the reading column by no more than the rail's shortfall. Where that crossing
   reaches the `target` the card is about, under and over are measured from the target
   and cluster together, so a user standing on the target sees it and its threads at
   once.

   Choosing its spot, the card is never shortened to make any of that true. Its height
   is capped by the boundary alone, and the spot is then clamped inside the boundary, so a card too tall
   for the room under or over its cluster slides across the controls that opened it
   rather than shrinking to spare them. The same clamp is what a scroll meets: the card
   slides with its cluster, then holds at the boundary's edge until the cluster itself
   has left, which `detached` reports for the caller to act on.

   Every result carries the `hold` it leaves: its side, its foot's offset from the
   cluster's top, and its height. While the card's reply is being drafted the caller
   passes back the hold of where the card stood when drafting began (`held`), and the
   card keeps that side and that foot instead of choosing again. The reply editor is
   pinned to the card's foot, so holding the foot holds the editor and the caret's line
   in it: a new line pushes the lines above the caret up, as a chat composer does,
   whichever side the card is on. Holding the top instead would move the caret down a
   line per keystroke, and choosing afresh flips a card whose grown height no longer fits
   over its cluster to under it, the editor jumping by the card's height. So a held card
   extends upward from its foot, over its cluster if it stands under it, until it meets
   the boundary's head. Its height is capped by the room above the foot, so from there the
   transcript, which scrolls inside the card, gives up its room to further growth.
   Typing, an arriving turn, a send, and a refusal all grow the card this way, so none
   of them moves the editor. The foot moves only with its cluster, as a scroll carries
   it, and the boundary clamps it there: never past the boundary's foot, and never so
   high that the room above it is less than the height the card was held at. A held side
   the room no longer allows, after a resize carries the cluster into or out of the
   rail's room, gives way to a fresh choice, whose hold the caller keeps from then on.

   The inputs are client rectangles and lengths and the module reads no DOM, so the rule
   is arithmetic a test can state. `heightAt(width, cap)` is the one measurement: the
   card's rendered height at that width under that height cap, which the caller reads
   from the live card, leaving the card wearing both. */

import { clamp } from "./rect.js";

export function threadCardGeometry({
  cluster,
  target = null,
  boundary,
  gap,
  minWidth,
  preferredWidth,
  heightAt,
  held = null,
}) {
  const preferred = Math.min(preferredWidth, boundary.width);
  const minimum = Math.min(minWidth, preferred);
  const room = boundary.right - cluster.right - gap;
  const beside = room >= minimum;
  const width = beside
    ? Math.min(preferred, room)
    : clamp(boundary.right - cluster.left, minimum, preferred);
  const x = beside ? cluster.right + gap : boundary.right - width;
  const detached = cluster.bottom <= boundary.top || cluster.top >= boundary.bottom;
  if (held && (held.placement === "right") === beside) {
    const foot = clamp(
      cluster.top + held.foot,
      boundary.top + Math.min(held.height, boundary.height),
      boundary.bottom,
    );
    const height = heightAt(width, foot - boundary.top);
    const y = foot - height;
    return { placement: held.placement, x, y, width, height, detached, hold: held };
  }
  const height = heightAt(width, boundary.height);
  const clears = !beside && target && x < target.right ? [cluster, target] : [cluster];
  const under = Math.max(...clears.map((box) => box.bottom)) + gap;
  const over = Math.min(...clears.map((box) => box.top)) - gap - height;
  const placement = beside
    ? "right"
    : under + height <= boundary.bottom || over < boundary.top
      ? "below"
      : "above";
  const y = clamp(
    { right: cluster.top, below: under, above: over }[placement],
    boundary.top,
    boundary.bottom - height,
  );
  const hold = { placement, foot: y + height - cluster.top, height };
  return { placement, x, y, width, height, detached, hold };
}
