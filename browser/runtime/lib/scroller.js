/* The box that scrolls a node, read from computed overflow, and a landing at its top.

   `scrollerOf(node)` is the nearest box around the node, through the shadow trees it
   stands in, whose vertical overflow the user can scroll, else the document's own
   scroller. A box a widget scrolls only sideways states `overflow-y: hidden`
   (module-scroll-and-motion.md, "Sideways scrollers"), so the walk passes it. The
   runtime's scroll ancestry starts from it off a Leaf page (scroll-containers.js).

   `landAtTop(node, behavior, past)` scrolls that box so the node's top, less its
   `scroll-margin-top`, stands at the box's band, its `scroll-padding-top`, where Leaf
   states the room its head and stuck headers take on the page, or `past` pixels above
   it. It moves nothing sideways, unlike the browser's `scrollIntoView`, and nothing
   where the node already stands within a pixel of that place, so a landing on what the
   user already sees moves nothing. `pastTop(node)` is how far the node's top stands
   above the band, as far as the reader has read past its start, which a later
   `landAtTop` returns them to. */
import { renderedParent } from "./shadow-tree.js";
import { scrollMoves } from "./scroll-range.js";

/** @param {Node | null | undefined} node @returns {Element} */
export function scrollerOf(node) {
  const page = document.scrollingElement ?? document.documentElement;
  for (
    let at = node instanceof Element ? node : (node?.parentElement ?? null);
    at;
    at = renderedParent(at)
  )
    if (at === page || /^(auto|scroll)$/u.test(getComputedStyle(at).overflowY))
      return at;
  return page;
}

/** @param {string} value */
const px = (value) => Number.parseFloat(value) || 0;

/** @param {Element} node */
export function pastTop(node) {
  const scroller = scrollerOf(node);
  const band =
    (scroller === document.scrollingElement
      ? 0
      : scroller.getBoundingClientRect().top + scroller.clientTop) +
    px(getComputedStyle(scroller).scrollPaddingTop);
  return (
    band + px(getComputedStyle(node).scrollMarginTop) - node.getBoundingClientRect().top
  );
}

/** @param {Element} node @param {ScrollBehavior} [behavior] @param {number} [past] */
export function landAtTop(node, behavior = "instant", past = 0) {
  const scroller = scrollerOf(node);
  const top = scroller.scrollTop - pastTop(node) + past;
  if (scrollMoves(scroller, { top })) scroller.scrollTo({ top, behavior });
}
