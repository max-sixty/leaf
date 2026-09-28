/* Floating UI for the page's floating surfaces: the response bar (composing/surface.js)
   and the inline thread card (margin-projection.js).

   Each places a fixed box beside something on the page, and each leaves the browser's
   coordinate spaces to Floating UI. `computePosition` maps what the box stands against
   into the box's own positioning space: a containing block, a scaled ancestor, a frame,
   or WebKit's visual-viewport offset for a fixed box under pinch zoom. `autoUpdate`
   follows every scroll container, resize, visual-viewport change, and layout shift that
   can move it. Which side a surface takes and how far it stands is that surface's own
   rule, stated as its middleware.

   `floatingPlacement` is one box's lifecycle around those two calls: it watches the
   element the box stands against, re-arming when that element changes, and numbers each
   placement so an answer computed for an earlier one is dropped. A placement lands in
   the microtasks after the rendering pass that asks for it, before the frame paints.

   Neither surface stands before the user acts, so the bundle stays off the presentation
   path and loads as soon as the page has presented, as an arrival the page answers for.
   A surface's first placement then lands in the frame that asks for it rather than
   after a fetch. */

import { afterPresentation } from "./presentation.js";

let floatingUiModule = null;
export const floatingUi = () =>
  (floatingUiModule ??= import("/vendor/floating-ui.esm.js"));
afterPresentation(floatingUi);

export function floatingPlacement({ floating, update }) {
  let epoch = 0;
  let watched = null;
  let stopWatching = null;
  return {
    // `reference` is what `computePosition` receives; `element` is the node it stands
    // for, whose scroll containers and moves `autoUpdate` follows.
    watch(element, reference, autoUpdate) {
      if (element === watched) return;
      stopWatching?.();
      watched = element;
      stopWatching = autoUpdate(reference, floating, update);
    },
    begin: () => ++epoch,
    current: (placement) => placement === epoch,
    stop() {
      epoch += 1;
      stopWatching?.();
      stopWatching = null;
      watched = null;
    },
  };
}
