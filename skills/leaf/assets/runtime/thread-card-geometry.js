/* Where the inline thread card stands, relative to the margin cluster that opened it.

   The card follows the rules the response bar's placement follows (composing/surface.js),
   in arithmetic of its own: it chooses a spot once, holds it relative to its cluster,
   grows from the edge it holds until the visible boundary stops it, and leaves with its
   cluster on a scroll rather than closing.

   The card is as wide as its thread: as wide as its widest unwrapped line, floored at
   its minimum measure and capped at the `room` its spot gives. A one-line question
   takes the minimum and a paragraph the whole room, so the card is never mostly empty,
   and a turn that needs more room widens it as it arrives, from whichever edge it holds
   (below). The reply the user is writing never sizes it: the reply wraps inside
   whatever width the thread gives. The stylesheet fits the card between the minimum
   and the room (chrome.css), and this module reads the width back.

   Beside the words it is about is preferred (`right`), top edge on its cluster's: the
   card's lane runs from the `target`'s right edge, or the cluster's where the thread
   has no target, to the visible edge, and the card is as wide as that lane allows up to
   the width its thread takes. Within the lane it stands as far right as that width lets
   it, so it clears its cluster where the lane has room for both and covers the cluster
   where it does not: the transcript's width outranks the rail's other entries, which
   the card gives back when it closes. When the lane is under the card's minimum
   measure, the card takes that minimum with its right edge on the visible edge,
   crossing the reading column by no more than the lane's shortfall, and stands under
   the cluster when its whole height fits there (`below`), else over it when it fits
   there (`above`), else under it again. Where that crossing reaches the target, under
   and over are measured from the target and cluster together, so a user standing on the
   target sees it and its threads at once.

   Choosing its spot, the card is never shortened to make any of that true. Its height is
   capped by the boundary alone, and the spot is then clamped inside the boundary, so a
   card too tall for the room under or over its cluster slides across the controls that
   opened it rather than shrinking to spare them.

   Every result carries the `hold` it leaves: its side and the width its `room` gives, the
   offsets of its top and foot from the cluster's top, its height, its transcript's
   height, and whether its cluster has been `seen` in the scrollport since the card was
   placed. A top chosen here is the spot's own, before the boundary clamped it, so a
   card opened low in the window rises back to its cluster once a scroll gives it room;
   every other offset is where the card stood. The caller passes the hold back on every
   later placement, saying whether the user is `drafting` a reply in it. The card keeps
   its side and one edge at its offset, and grows from it; which edge is whichever holds
   still what the user is working in.

   - Drafting, a new line of the reply holds the top, so neither the lines the user has
     written nor the thread they are answering move: the card extends downward, as an
     editor's page does, and Send moves down a line per wrap, over the cluster too
     where the card stands above it. Only at the boundary's foot does the card rise to
     keep the reply in view, as the comment box does (composing/surface.js), and only
     once it fills the whole boundary does the transcript give up its room. The hold's
     transcript tells a new line from a turn joining the transcript, one that arrives
     or the one the user just sent; that holds the foot, with the reply row on it, so
     the box they type in stays put and the transcript rises by the turn.
   - Read, a turn arriving holds the top, so the words being read stay where they are:
     the card extends downward, beside or under its cluster. A card over its cluster
     holds its foot instead, the edge toward its cluster, so it grows upward rather
     than across what it is about.

   Otherwise, once the card meets the boundary the transcript, which scrolls inside the
   card, takes the growth instead: its height is capped by the room from the held edge
   to the boundary's far edge, so from there the transcript gives up its room to further
   growth. Switching edges leaves the card where it stands, since the other edge's
   offset is always where the card last stood, and from then on the card keeps that
   place relative to its cluster; only the room the new edge opens can grow it.

   A scroll carries the held edge with its cluster, and the boundary clamps it there: the
   whole card, at its last height, stays inside the boundary for as long as the cluster
   stays inside the `scrollport`, the room the page scrolls it through, so scrolling never
   squeezes it. Once the cluster leaves the scrollport, the clamp gives by exactly as far
   as the cluster has gone, so the card leaves with it and comes back with it; `away`
   says the card has left the boundary altogether. `plane` says what a scroll carries the
   card with: the `window`, while the boundary's own edge holds it in, or the `page`,
   where it stands at its spot or at a bound that has given with its cluster. A caller
   that stands the card in that plane, counting a reading region's edge as the page's,
   leaves to the browser every scroll that keeps it. Nothing about a scroll closes the
   card. The clamp gives only for a cluster `seen` since the card was placed: a card
   opened from words deep in a block whose cluster is above the window stands in the
   window until that cluster has been in it, and a caller whose window changed size
   clears `seen` for the same reason. The boundary can be smaller than the scrollport
   where pinch zoom or a phone's software keyboard hides part of the window; a cluster in
   the hidden part has not been scrolled away, so the card stays in what the user sees. A
   hold whose side or room the boundary no longer gives, as after a resize, gives way to
   a fresh choice, whose hold the caller keeps from then on: at another width the page's
   words reflow too, so neither of the card's edges holds what the user was reading or
   writing. A thread that widens its card in the same room keeps the hold, since the
   turn that widened it is one the held edge already answers for.

   The inputs are client rectangles and lengths and the module reads no DOM, so the rule
   is arithmetic a test can state. It takes three measurements, which the caller reads
   from the live card: `widthAt(minimum, room)`, its rendered width between those
   bounds, and at the width that gives, `heightAt(room, cap)`, its rendered height under
   that height cap, and `transcriptAt(room)`, the height of the thread's turns without
   the reply row. */

import { clamp } from "./rect.js";

export function threadCardGeometry({
  cluster,
  target = null,
  boundary,
  scrollport = boundary,
  gap,
  minWidth,
  preferredWidth,
  widthAt,
  heightAt,
  transcriptAt,
  drafting = false,
  hold = null,
}) {
  const measure = Math.min(preferredWidth, boundary.width);
  const minimum = Math.min(minWidth, measure);
  const lane = (target ?? cluster).right + gap;
  const beside = boundary.right - lane >= minimum;
  const room = beside ? Math.min(measure, boundary.right - lane) : minimum;
  const width = widthAt(minimum, room);
  const x = beside
    ? clamp(boundary.right - width, lane, cluster.right + gap)
    : boundary.right - minimum;
  // The boundary holds the card in only while its cluster is inside the scrollport, once
  // the cluster has been there.
  const seen =
    Boolean(hold?.seen) ||
    (cluster.bottom > scrollport.top && cluster.top < scrollport.bottom);
  const gone = (distance) => (seen ? Math.max(0, distance) : 0);
  const head = boundary.top - gone(scrollport.top - cluster.bottom);
  const foot = boundary.bottom + gone(cluster.top - scrollport.bottom);
  // `spot` is where the card stands relative to its cluster, before the boundary clamps it.
  const holding = (placement, spot, height, transcript, kept = {}) => {
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
        room,
        top: y - cluster.top,
        foot: y + height - cluster.top,
        height,
        seen,
        transcript,
        ...kept,
      },
    };
  };

  if (hold && (hold.placement === "right") === beside && hold.room === room) {
    const transcript = transcriptAt(room);
    const turned = Math.abs(transcript - hold.transcript) > 0.5;
    const held = drafting
      ? turned
        ? "foot"
        : "top"
      : hold.placement === "above"
        ? "foot"
        : "top";
    const last = Math.min(hold.height, boundary.height);
    const at = cluster.top + hold[held];
    // The room from the held edge to the boundary's far edge, with the edge inside the
    // boundary as the cluster's being there would put it. A card whose reply is growing
    // may rise off its top at the boundary's foot, so it has the whole boundary.
    const cap =
      held === "foot"
        ? clamp(at, boundary.top + last, boundary.bottom) - boundary.top
        : drafting
          ? boundary.height
          : boundary.bottom - clamp(at, boundary.top, boundary.bottom - last);
    const height = heightAt(room, cap);
    return holding(
      hold.placement,
      held === "foot" ? at - height : at,
      height,
      transcript,
      { [held]: hold[held] },
    );
  }
  const height = heightAt(room, boundary.height);
  const clears = !beside && target && x < target.right ? [cluster, target] : [cluster];
  const under = Math.max(...clears.map((box) => box.bottom)) + gap;
  const over = Math.min(...clears.map((box) => box.top)) - gap - height;
  const placement = beside
    ? "right"
    : under + height <= boundary.bottom || over < boundary.top
      ? "below"
      : "above";
  const spot = { right: cluster.top, below: under, above: over }[placement];
  return holding(placement, spot, height, transcriptAt(room), {
    top: spot - cluster.top,
  });
}
