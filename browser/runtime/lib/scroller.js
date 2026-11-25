/* The box that scrolls a node, read from computed overflow: the nearest box around it,
   through the shadow trees it stands in, whose vertical overflow the user can scroll,
   else the document's own scroller. A box a widget scrolls only sideways states
   `overflow-y: hidden` (module-scroll-and-motion.md, "Sideways scrollers"), so the walk
   passes it. The runtime's scroll ancestry starts from it off a Leaf page
   (scroll-containers.js); a widget reads it for the box a drag or a follow scrolls. */
import { renderedParent } from "./shadow-tree.js";

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
