/* Where the inline thread card stands, relative to the margin cluster that opened it.

   The card follows the rules the response bar's placement follows (composing/surface.js),
   in arithmetic of its own: it chooses a spot once, holds it relative to its cluster,
   grows from the edge it holds until the visible boundary stops it, and leaves with its
   cluster on a scroll rather than closing.

   Beside the words it is about is preferred (`right`), top edge on its cluster's: the
   card's lane runs from the `target`'s right edge, or the cluster's where the thread has
   no target, to the visible edge, and the card is as wide as that lane allows up to its
   preferred measure. Within the lane it stands as far right as that width lets it, so it
   clears its cluster where the lane has room for both and covers the cluster where it
   does not: the transcript's width outranks the rail's other entries, which the card
   gives back when it closes. When the lane is under the card's minimum measure, the card
   takes that minimum with its right edge on the visible edge, crossing the reading
   column by no more than the lane's shortfall, and stands under the cluster when its
   whole height fits there (`below`), else over it when it fits there (`above`), else
   under it again. Where that crossing reaches the target, under and over are measured
   from the target and cluster together, so a user standing on the target sees it and
   its threads at once.

   Choosing its spot, the card is never shortened to make any of that true. Its height is
   capped by the boundary alone, and the spot is then clamped inside the boundary, so a
   card too tall for the room under or over its cluster slides across the controls that
   opened it rather than shrinking to spare them.

   Every result carries the `hold` it leaves: its side and width, the offsets of its top
   and foot from the cluster's top, its height, and whether its cluster has been `seen`
   in the scrollport since the card was placed. A top chosen here is the spot's own,
   before the boundary clamped it, so a card opened low in the window rises back to its
   cluster once a scroll gives it room; every other offset is where the card stood. The
   caller passes the hold back on every later placement, with the `edge` the user's
   attention is on: the foot while the reply is being drafted, the top while the thread
   is read. The card keeps its side and keeps that edge at its offset, and grows from
   it. Drafting, a new line pushes the lines above the caret up, as a chat composer
   does, so the caret's line stays under the user's hand. Reading, a turn arriving
   extends the card away from its cluster, so the words being read stay where they are
   and the card never grows across what it is about: downward beside or under the
   cluster, and upward over it, where the card holds its foot instead. Once the card
   meets the boundary the transcript, which scrolls inside the card, takes the turn
   instead. Its height is capped by the room from the held edge to the boundary's far
   edge, so from there the transcript gives up its room to further growth. Switching
   edges leaves the card where it stands, since the other edge's offset is always where
   the card last stood, and from then on the card keeps that place relative to its
   cluster; only the room the new edge opens can grow it.

   A scroll carries the held edge with its cluster, and the boundary clamps it there: the
   whole card, at its last height, stays inside the boundary for as long as the cluster
   stays inside the `scrollport`, the room the page scrolls it through, so scrolling never
   squeezes it. Once the cluster leaves the scrollport, the clamp gives by exactly as far
   as the cluster has gone, so the card leaves with it and comes back with it; `away`
   says the card has left the boundary altogether. `plane` says what a scroll carries the
   card with: the `window`, while the boundary's own edge holds it in, or the `page`,
   where it stands at its spot or at a bound that has given with its cluster. A caller
   that stands the card in that plane leaves every scroll that keeps it to the browser. Nothing about a scroll closes the
   card. The clamp gives only for a cluster `seen` since the card was placed: a card
   opened from words deep in a block whose cluster is above the window stands in the
   window until that cluster has been in it, and a caller whose window changed size
   clears `seen` for the same reason. The boundary can be smaller than the scrollport
   where pinch zoom or a phone's software keyboard hides part of the window; a cluster in
   the hidden part has not been scrolled away, so the card stays in what the user sees. A
   hold whose side or width the room no longer gives, as after a resize, gives way to a
   fresh choice, whose hold the caller keeps from then on: at another width the card's
   words reflow, so neither of its edges holds what the user was reading or writing.

   The inputs are client rectangles and lengths and the module reads no DOM, so the rule
   is arithmetic a test can state. `heightAt(width, cap)` is the one measurement: the
   card's rendered height at that width under that height cap, which the caller reads
   from the live card, leaving the card wearing both. */

import { clamp } from "./rect.js";

export function threadCardGeometry({
  cluster,
  target = null,
  boundary,
  scrollport = boundary,
  gap,
  minWidth,
  preferredWidth,
  heightAt,
  edge = "top",
  hold = null,
}) {
  const preferred = Math.min(preferredWidth, boundary.width);
  const minimum = Math.min(minWidth, preferred);
  const lane = (target ?? cluster).right + gap;
  const beside = boundary.right - lane >= minimum;
  const x = beside
    ? clamp(boundary.right - preferred, lane, cluster.right + gap)
    : boundary.right - minimum;
  const width = beside ? Math.min(preferred, boundary.right - x) : minimum;
  // The boundary holds the card in only while its cluster is inside the scrollport, once
  // the cluster has been there.
  const seen =
    Boolean(hold?.seen) ||
    (cluster.bottom > scrollport.top && cluster.top < scrollport.bottom);
  const gone = (distance) => (seen ? Math.max(0, distance) : 0);
  const head = boundary.top - gone(scrollport.top - cluster.bottom);
  const foot = boundary.bottom + gone(cluster.top - scrollport.bottom);
  // `spot` is where the card stands relative to its cluster, before the boundary clamps it.
  const holding = (placement, spot, height, kept = {}) => {
    const y = clamp(spot, head, foot - height);
    return {
      placement,
      x,
      y,
      width,
      height,
      away: y + height <= boundary.top || y >= boundary.bottom,
      plane:
        (y > spot && head === boundary.top) || (y < spot && foot === boundary.bottom)
          ? "window"
          : "page",
      hold: {
        placement,
        width,
        top: y - cluster.top,
        foot: y + height - cluster.top,
        height,
        seen,
        ...kept,
      },
    };
  };

  if (hold && (hold.placement === "right") === beside && hold.width === width) {
    // Read, a card over its cluster holds its foot, the edge toward its cluster.
    const held = edge === "top" && hold.placement === "above" ? "foot" : edge;
    const last = Math.min(hold.height, boundary.height);
    const at = cluster.top + hold[held];
    // The room from the held edge to the boundary's far edge, with the edge inside the
    // boundary as the cluster's being there would put it.
    const cap =
      held === "foot"
        ? clamp(at, boundary.top + last, boundary.bottom) - boundary.top
        : boundary.bottom - clamp(at, boundary.top, boundary.bottom - last);
    const height = heightAt(width, cap);
    return holding(hold.placement, held === "foot" ? at - height : at, height, {
      [held]: hold[held],
    });
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
  const spot = { right: cluster.top, below: under, above: over }[placement];
  return holding(placement, spot, height, { top: spot - cluster.top });
}
