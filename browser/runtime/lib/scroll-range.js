// Compiled from scroll-range.ts by build/typescript.mjs; edit that file.
/* The positions a box's scroll can take, and whether a write would move it.

   A scroll write that leaves its box where it stands still does something, which
   nobody asked for: it stops a scroll the browser drives there, and in Firefox it
   cancels the rubber band of a flick into an edge, which runs after the box's scroll
   has ended, so a writer putting a box back at its end at every scroll's end would
   flatten each flick's band. So a writer that may name the position its box already
   holds, as one that restores an offset or follows another box does, asks
   `scrollMoves` first and writes only where it answers yes:

       if (scrollMoves(box, at)) box.scrollTo({ ...at, behavior: "instant" });

   Leaf's own writer asks it too (dom/arrivals.js, `setScroll`). */
// The positions a box's scroll takes on each axis, as the browser clamps a write: from
// zero to the side where the box's content flows from, the negative one where that is
// the bottom or right edge (`scrollsBack`). Off zero, where the box stands says which;
// at zero on an axis whose side the style leaves open, both sides, so no move is lost.
export function scrollRange(box) {
  const { scrollTop: top, scrollLeft: left } = box;
  const down = Math.max(box.scrollHeight - box.clientHeight, 0);
  const across = Math.max(box.scrollWidth - box.clientWidth, 0);
  const back =
    (top === 0 && down) || (left === 0 && across)
      ? scrollsBack(box)
      : { top: false, left: false };
  const reach = (at, span, side) =>
    at > 0 || (at === 0 && side === false)
      ? [0, span]
      : at < 0 || side
        ? [-span, 0]
        : [-span, span];
  return { top: reach(top, down, back.top), left: reach(left, across, back.left) };
}
// Whether each axis of a box scrolls on the negative side of zero, or null where its
// style leaves that open. A box scrolls from where its content's flow starts, so one
// whose flow starts at the bottom or right edge scrolls back from zero. Writing mode and
// direction place the inline and block starts, and a flex container's main and cross
// starts follow its direction and wrap. No API reports a box's scroll range (Firefox's
// own `scrollTopMin` aside), and a box standing at zero shows nothing of its side, so the
// side is read from the style that decides it; Chromium and Firefox agree on every
// combination of those (tests/browser/test_scroll_writes.py).
//
// The page scrolls from its principal flow, which no flex flow of the root's reverses:
// the root's writing mode and direction, or the body's where the page takes them from
// it. Which one applies turns on containment, content visibility, a hidden body or a
// frameset, and the engines differ on some of those, so where the root and the body
// agree that is the side, and where they don't it is open.
function scrollsBack(box) {
  const page = box.ownerDocument;
  if (box !== page.scrollingElement) return flowsBack(getComputedStyle(box), true);
  const root = flowsBack(getComputedStyle(box), false);
  if (!page.body) return root;
  const body = flowsBack(getComputedStyle(page.body), false);
  return {
    top: root.top === body.top ? root.top : null,
    left: root.left === body.left ? root.left : null,
  };
}
// Whether each axis of a box with `style` starts its flow at the bottom or right edge,
// counting its flex flow where `flex` asks.
function flowsBack(style, flex) {
  const { writingMode, direction, display, flexDirection, flexWrap } = style;
  const vertical = writingMode !== "horizontal-tb";
  // Whether the inline axis starts at its bottom or right end, and the block axis.
  let inline = (writingMode === "sideways-lr") !== (direction === "rtl");
  let block = writingMode === "vertical-rl" || writingMode === "sideways-rl";
  if (flex && display.endsWith("flex")) {
    const reversed = flexDirection.endsWith("-reverse");
    const wrapped = flexWrap === "wrap-reverse";
    if (flexDirection.startsWith("column"))
      [block, inline] = [block !== reversed, inline !== wrapped];
    else [inline, block] = [inline !== reversed, block !== wrapped];
  }
  return vertical ? { top: inline, left: block } : { top: block, left: inline };
}
// Whether a write to `top` and `left` takes the box a pixel or more from where it
// stands, once the browser clamps it to the box's range. Where the box stands is read to
// the pixel: its scroll size is a whole number of pixels, so an end read from it stands
// up to a pixel short of the browser's own.
export const scrollMoves = (box, { top, left }) => {
  const range = scrollRange(box);
  const along = (to, at, [low, high]) =>
    to !== undefined && Math.abs(Math.min(Math.max(to, low), high) - at) >= 1;
  return (
    along(top, box.scrollTop, range.top) || along(left, box.scrollLeft, range.left)
  );
};
