/* Surfaces fixed over the page and placed beside what they are about: the thread card by
   its margin cluster, the comment box by its target. A scroll carries each away with what
   it stands by while the user may still stand in it, and none of the browser's own
   reveals can bring it back: a focus, a caret, or `scrollIntoView` scrolls the control's
   ancestors, and the surface is fixed over all of them. So each surface declares when it
   is away and how it is brought back, and the runtime brings it back where the browser
   would have revealed an ordinary control:

   - a landing in it (`bringBackSurfaceOf`), which `scrollThreadIntoView` makes for every
     thread and the comment box makes when `c` enters it;
   - a key taken at the user's focus in it, as a browser brings a focused field back for
     typing: one a scope rooted in the surface answers or claims, such as the letters and
     editing keys of a box in it or the thread's `Enter`, or one nothing takes, which the
     platform takes at focus (Tab, a press on a button). A key a scope outside the surface
     answers or claims acts around it: `g` opens Go-to over the window the user scrolled
     to, any key while Go-to stands is Go-to's, and `j` scrolls on from there. A page
     command that lands in the surface brings it back by that landing. A shortcut the
     browser or the system takes, a modifier on its own, and Escape, which puts the
     surface away, leave the page where it is.

   What does not act, a scroll or a turn arriving, leaves the surface away. */
import { pressRoot } from "./keyboard/dispatch.js";
import { scrollBehavior } from "./motion.js";
import { under } from "./shadow.js";

const surfaces = new Map();
const PASSED_BY = ["Control", "Meta", "Alt", "Shift", "Escape"];

export function declareOffFlowSurface(surface, { away, bringBack }) {
  surfaces.set(surface, { away, bringBack });
  surface.addEventListener(
    "keydown",
    (event) => {
      if (
        !away() ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        PASSED_BY.includes(event.key)
      )
        return;
      const answeredBy = pressRoot(event);
      if (!answeredBy || under(answeredBy, surface)) bringBack(scrollBehavior());
    },
    { capture: true },
  );
}

// Bring back the surface holding `node`, where it is away; a node in flow needs nothing.
export function bringBackSurfaceOf(node, behavior = scrollBehavior()) {
  for (const [surface, { away, bringBack }] of surfaces)
    if (under(node, surface) && away()) bringBack(behavior);
}
