/* Surfaces fixed over the page and placed beside what they are about: the thread card by
   its margin cluster, the comment box by its target. A scroll carries each away with what
   it stands by while the user may still stand in it, and none of the browser's own
   reveals can bring it back: a focus, a caret, or `scrollIntoView` scrolls the control's
   ancestors, and the surface is fixed over all of them. So each surface declares when it
   is away and how it is brought back, and the runtime brings it back where the browser
   would have revealed an ordinary control:

   - a landing in it (`bringBackSurfaceOf`), which `scrollThreadIntoView` makes for every
     thread and the comment box makes when `c` enters it;
   - an edit in it, as a browser brings a field back into view for the caret: the words
     typed, deleted, or pasted into a box it holds;
   - focus moving from one of its controls to another, as sequential navigation reveals
     the control it reaches. Only a move within it: focus arriving from outside is a
     landing, or a node the runtime replaced handing focus to its successor, which is
     no move of the user's.

   A surface hears no keys of its own. A key reaches it only as what the keyboard makes
   of it, so a page key such as `g` or `j` acts around a surface the user still stands
   in, and one that lands in it or edits in it brings it back by doing so. What does not
   act there, a scroll or a turn arriving, leaves the surface away. */
import { scrollBehavior } from "./motion.js";
import { under } from "./shadow.js";

const surfaces = new Map();

export function declareOffFlowSurface(surface, { away, bringBack }) {
  surfaces.set(surface, { away, bringBack });
  const follow = () => {
    if (away()) bringBack(scrollBehavior());
  };
  surface.addEventListener("beforeinput", follow, { capture: true });
  surface.addEventListener("focusin", (event) => {
    if (event.relatedTarget && under(event.relatedTarget, surface)) follow();
  });
}

// Bring back the surface holding `node`, where it is away; a node in flow needs nothing.
export function bringBackSurfaceOf(node, behavior = scrollBehavior()) {
  for (const [surface, { away, bringBack }] of surfaces)
    if (under(node, surface) && away()) bringBack(behavior);
}
