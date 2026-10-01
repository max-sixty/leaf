/* Surfaces fixed over the page and placed beside what they are about: the thread card by
   its margin cluster, the comment box by its target. A scroll carries each away with what
   it stands by while the user may still stand in it, and none of the browser's own
   reveals can bring it back: a focus, a caret, or `scrollIntoView` scrolls the control's
   ancestors, and the surface is fixed over all of them. So each surface declares while
   it floats and how it is brought back, and the runtime brings it back where the browser
   would have revealed an ordinary control:

   - a landing in it (`bringBackSurfaceOf`), which `scrollThreadIntoView` makes for every
     thread and the comment box makes when `c` enters it;
   - an edit in it, as a browser brings a field back into view for the caret: the words
     typed, deleted, or pasted into a box it holds;
   - focus moving from one of its controls to another, as sequential navigation reveals
     the control it reaches. Only a move within it: focus arriving from outside is a
     landing, or a node the runtime replaced handing focus to its successor, which is
     no move of the user's.

   Each asks what the browser asks of an ordinary control: whether the window shows all of
   it, below the banner and above the bottom bar. A surface waiting hidden for room to
   stand says so (`away`), since its hidden box measures wherever it was left. A surface half under the banner is as
   unseen there as one scrolled off altogether. What a scroller inside the surface hides
   is the browser's to reveal, so the control is measured within the surface's own box.

   A surface hears no keys of its own. A key reaches it only as what the keyboard makes
   of it, so a page key such as `g` or `j` acts around a surface the user still stands
   in, and one that lands in it or edits in it brings it back by doing so. What does not
   act there, a scroll or a turn arriving, leaves the surface where the page put it. */
import { shownWindow } from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { under } from "./shadow.js";

const surfaces = new Map();

// A pixel's slack, so a card the boundary holds flush under the banner reads as shown.
const unseen = (node, surface) => {
  const box = node.getBoundingClientRect();
  const bounds = surface.getBoundingClientRect();
  const shown = shownWindow();
  return (
    Math.max(box.top, bounds.top) < shown.top - 1 ||
    Math.min(box.bottom, bounds.bottom) > shown.bottom + 1
  );
};

function follow(surface, node, behavior) {
  const { floats, away, bringBack } = surfaces.get(surface);
  if (floats() && (away() || unseen(node, surface))) bringBack(behavior);
}

export function declareOffFlowSurface(
  surface,
  { floats = () => true, away = () => false, bringBack },
) {
  surfaces.set(surface, { floats, away, bringBack });
  surface.addEventListener(
    "beforeinput",
    (event) => follow(surface, event.target, scrollBehavior()),
    { capture: true },
  );
  surface.addEventListener("focusin", (event) => {
    if (event.relatedTarget && under(event.relatedTarget, surface))
      follow(surface, event.target, scrollBehavior());
  });
}

// Bring back the surface holding `node`, where the window does not show all of it; a
// node in flow needs nothing.
export function bringBackSurfaceOf(node, behavior = scrollBehavior()) {
  for (const surface of surfaces.keys())
    if (under(node, surface)) follow(surface, node, behavior);
}
