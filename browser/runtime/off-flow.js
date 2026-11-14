/* Surfaces fixed over the page and placed beside what they are about: the thread card by
   its margin cluster, the comment box by its target. A scroll carries each away with what
   it stands by while the user may still be in it, and none of the browser's own
   reveals can bring it back: a focus, a caret, or `scrollIntoView` scrolls the control's
   ancestors, and the surface is fixed over all of them. So each surface declares while
   it floats and how it is brought back, and the runtime brings it back where the browser
   would have revealed an ordinary control:

   - a landing in it (`bringBackSurfaceOf`), which `scrollThreadIntoView` makes for every
     thread and the comment box makes when `c` enters it;
   - an edit in it, as a browser brings a field back into view for the caret: the words
     typed, deleted, or pasted into a box it holds;
   - Tab reaching one of its controls, or focus moving from one of its controls to
     another, as sequential navigation reveals the control it reaches. Left unrevealed,
     the next key would let go of a control the user can't see (keyboard/controller.js)
     and land them where Tab reaches it again. Focus otherwise arriving from outside is
     a landing, and a return (focus.js, `onCurrentLocation`), such as a node the runtime
     replaced handing focus to its successor, is no move of the user's. Nor is a press:
     the pointer found the control where it stands, so a click into a card's reply
     leaves the page, and the box under the pointer, still. The first word typed
     there is an edit, which brings the card back if the window doesn't show the box.

   Each asks what the browser asks of an ordinary control: whether the user sees all of
   it (geometry.js, `seenRect`), clear of the room the floating panel takes. A surface
   waiting hidden for room to stand says so (`away`), since its hidden box measures
   wherever it was left. A surface half under the panel is as unseen there as one
   scrolled off altogether. What a scroller inside the surface hides is the browser's
   to reveal, so the control is measured within the surface's own box. A surface the
   user doesn't see is left to a glide that will bring it into the window
   (scroll-containers.js, `glideGap`), as though it had landed, and one that stops short
   of the window or carries it past is brought back: a `c` pressed while
   `t` glides the page to the card it focused writes in the card and lets it arrive,
   where bringing the card back stopped the page over 350 px short of the walk's
   landing.

   A surface hears no keys of its own. A key reaches it only as what the keyboard makes
   of it, so a page key such as `g` or `j` acts around a surface the user is still
   in, and one that lands in it or edits in it brings it back by doing so. What does not
   act there, a scroll or a turn arriving, leaves the surface where the page put it. */
import { seenRect } from "./geometry.js";
import { glideGap } from "./scroll-containers.js";
import { scrollBehavior } from "./motion.js";
import { under } from "./shadow.js";
import { onCurrentLocation } from "./focus.js";
import { isElement } from "./shadow-tree.js";

/** @typedef {{surface: Element, floats: () => boolean, away: () => boolean,
 * bringBack: (behavior: ScrollBehavior) => unknown}} OffFlowSurface */
/** @type {Map<Element, OffFlowSurface>} */
const surfaces = new Map();

// A pixel's slack, so a card the boundary holds flush at the room's edge reads as shown.
/** @param {Element} node @param {Element} surface */
const unseen = (node, surface) => {
  const box = node.getBoundingClientRect();
  const bounds = surface.getBoundingClientRect();
  const seen = seenRect(surface, new Map());
  return (
    (!seen ||
      Math.max(box.top, bounds.top) < seen.top - 1 ||
      Math.min(box.bottom, bounds.bottom) > seen.bottom + 1) &&
    glideGap(surface)?.after !== 0
  );
};

/** @param {OffFlowSurface} reading @param {Element} node @param {ScrollBehavior} behavior */
function follow({ surface, floats, away, bringBack }, node, behavior) {
  if (floats() && (away() || unseen(node, surface))) bringBack(behavior);
}

/** @param {Element} surface @param {Omit<OffFlowSurface, "surface" | "floats" | "away"> &
 * {floats?: () => boolean, away?: () => boolean}} reading */
export function declareOffFlowSurface(
  surface,
  { floats = () => true, away = () => false, bringBack },
) {
  const reading = { surface, floats, away, bringBack };
  surfaces.set(surface, reading);
  surface.addEventListener(
    "lf-before-edit",
    (event) => {
      if (isElement(event.target)) follow(reading, event.target, scrollBehavior());
    },
    { capture: true },
  );
}
// A Tab reaching a surface, or a move within it, a widget's shadow tree inside it
// included.
onCurrentLocation((node, cause, left) => {
  if (!node || cause === "return" || cause === "press") return;
  for (const reading of surfaces.values()) {
    const { surface } = reading;
    if (under(node, surface) && (cause === "step" || under(left, surface)))
      follow(reading, node, scrollBehavior());
  }
});

// Bring back the surface holding `node`, where the window does not show all of it; a
// node in flow needs nothing.
/** @param {Element} node @param {ScrollBehavior} [behavior] */
export function bringBackSurfaceOf(node, behavior = scrollBehavior()) {
  for (const reading of surfaces.values())
    if (under(node, reading.surface)) follow(reading, node, behavior);
}
