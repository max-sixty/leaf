/* Floating UI for the page's floating surfaces: the response bar (composing/surface.js)
   and the inline thread card (margin-projection.js).

   Each places a box beside something on the page, and each leaves the browser's
   coordinate spaces to Floating UI. `computePosition` maps what the box stands against
   into the box's own positioning space: a containing block, a frame, or WebKit's
   visual-viewport offset for a fixed box under pinch zoom. `autoUpdate`
   follows every scroll container, resize, visual-viewport change, and layout shift that
   can move it. Which side a surface takes and how far it stands is that surface's own
   rule, stated as its middleware.

   `floatingPlacement` is one box's lifecycle around those two calls: it watches the
   element the box stands against, re-arming when that element changes, and numbers each
   placement so an answer computed for an earlier one is dropped. A placement lands in
   the microtasks after the rendering pass that asks for it, before the frame paints.

   A box stands in the plane a scroll carries it with, which is the surface's answer to
   name: the `page`'s, where it stands beside what it is about, or the `window`'s, where
   the visible boundary holds it in. The box is absolutely positioned in the first and
   fixed in the second (`data-lf-plane`), so, under no transformed ancestor, the
   compositor carries it through every scroll that keeps its plane, in step with the
   words, and a placement that follows that scroll writes nothing. Placed in script from the window's plane, the box trailed
   the words by a frame through every scroll. `position` places the box in its present
   plane and, where the answer names the other one, places it again there.

   Neither surface stands before the user acts, so the bundle stays off the presentation
   path and loads as soon as the page has presented, as an arrival the page answers for.
   A surface's first placement then lands in the frame that asks for it rather than
   after a fetch. */

import { afterPresentation } from "./presentation.js";
import { keeps } from "./widget-elements.js";

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
    // `planeOf` reads the plane from Floating UI's answer.
    async position(computePosition, reference, options, planeOf) {
      const at = (plane) => {
        keeps(floating, "data-lf-plane", plane);
        return computePosition(reference, floating, {
          ...options,
          strategy: plane === "window" ? "fixed" : "absolute",
        });
      };
      const plane = floating.dataset.lfPlane ?? "page";
      const answer = await at(plane);
      const wanted = planeOf(answer);
      return wanted && wanted !== plane ? at(wanted) : answer;
    },
    stop() {
      epoch += 1;
      stopWatching?.();
      stopWatching = null;
      watched = null;
      delete floating.dataset.lfPlane;
    },
  };
}
