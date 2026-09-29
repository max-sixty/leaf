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

   A fixed box stands in the plane a scroll carries it with, which is the surface's
   answer to name: the `page`'s, where it stands beside what it is about, or the
   `window`'s, where the visible boundary holds it in. In the page's plane the box is
   anchored (CSS anchor positioning) to the element it stands beside, with its spot
   written as insets from that anchor, so the browser carries it through every scroll
   that moves the anchor, in step with the words, and a placement that follows that
   scroll finds the same insets and writes nothing. The box stays fixed either way, so
   what lands inside it, a scroll into view or a focus, never scrolls the page under
   it.

   Neither surface stands before the user acts, so the bundle stays off the presentation
   path and loads as soon as the page has presented, as an arrival the page answers for.
   A surface's first placement then lands in the frame that asks for it rather than
   after a fetch. */

import { afterPresentation } from "./presentation.js";
import { keeps } from "./keeps.js";
import { anchorElement, anchorName } from "./anchor-names.js";
import { shownWindow } from "./geometry.js";

// Insets at the browser's layout precision, so one spot written twice reads the same.
const px = (value) => `${Math.round(value * 64) / 64}px`;

let floatingUiModule = null;
export const floatingUi = () =>
  (floatingUiModule ??= import("/vendor/floating-ui.esm.js"));
afterPresentation(floatingUi);

// Where `anchor` stands in the box's positioning space, from the reference's rectangle
// there and both boxes' client rectangles. Nothing where a transform, filter, or
// containment between the box and the body makes some box other than the viewport its
// containing block, since an anchor outside that block cannot position it.
const anchorAt = (reference, anchor) => ({
  name: "anchorAt",
  async fn({ rects, elements, platform }) {
    if (!anchor || (await platform.getOffsetParent(elements.floating)) !== window)
      return {};
    const client = reference.getBoundingClientRect();
    const box = anchor.getBoundingClientRect();
    return {
      data: {
        x: rects.reference.x + box.left - client.left,
        y: rects.reference.y + box.top - client.top,
      },
    };
  },
});

// Whether a box spanning `top` to `bottom` stands against an edge of the window the page
// shows (geometry.js, `shownWindow`), `gap` inside it, rather than against a reading
// region's edge the page carries.
export function heldByWindow(top, bottom, gap) {
  const shown = shownWindow({ gap });
  return Math.abs(top - shown.top) < 0.5 || Math.abs(bottom - shown.bottom) < 0.5;
}

export function floatingPlacement({ floating, update }) {
  let epoch = 0;
  let watched = null;
  let stopWatching = null;
  const placedAt = (x, y) => {
    floating.style.removeProperty("position-anchor");
    floating.style.left = px(x);
    floating.style.top = px(y);
  };
  // An anchor lost between placements (a row withheld, a target skipped, its name taken
  // by a revision) stands the box off screen, as the rows fall back, until the placement
  // that follows finds it another.
  const anchoredAt = (anchor, at) => (x, y) => {
    floating.style.positionAnchor = anchorName(anchor);
    floating.style.left = `calc(anchor(left, -9999px) + ${px(x - at.x)})`;
    floating.style.top = `calc(anchor(top, -9999px) + ${px(y - at.y)})`;
  };
  let stand = placedAt;
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
    // Computes the answer, in the window's positioning space, and the plane `planeOf`
    // reads from it; `beside` is the element the box stands beside in the page's plane.
    // `stand` then writes a spot in that answer's plane.
    async position(computePosition, reference, options, planeOf, beside) {
      const anchor =
        beside && CSS.supports("anchor-name", "--lf-anchor")
          ? anchorElement(beside)
          : null;
      const answer = await computePosition(reference, floating, {
        ...options,
        strategy: "fixed",
        middleware: [...options.middleware, anchorAt(reference, anchor)],
      });
      const at = answer.middlewareData.anchorAt;
      const plane =
        at?.x !== undefined && planeOf(answer) === "page" ? "page" : "window";
      keeps(floating, "data-lf-plane", plane);
      stand = plane === "page" ? anchoredAt(anchor, at) : placedAt;
      return answer;
    },
    stand: (x, y) => stand(x, y),
    stop() {
      epoch += 1;
      stopWatching?.();
      stopWatching = null;
      watched = null;
      delete floating.dataset.lfPlane;
      for (const property of ["position-anchor", "left", "top"])
        floating.style.removeProperty(property);
    },
  };
}
