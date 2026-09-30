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

   In either plane the box stands by the edges that hold it, one per axis (`held`). On
   the axis its placement stands it beside something, that is the edge facing it; on the
   other, the edge its alignment names, the start for a centred box; and on an axis where
   the boundary shifted the box in, the edge against that boundary. Content that grows
   the box then moves only its free edges, in the layout that grows it. Stood by its
   top-left corner, a box that grows at its left or top would paint grown the wrong way
   for a frame, until the placement that follows the resize carried it back.

   Neither surface stands before the user acts, so the bundle stays off the presentation
   path and loads as soon as the page has presented, as an arrival the page answers for.
   A surface's first placement then lands in the frame that asks for it rather than
   after a fetch. */

import { afterPresentation } from "./presentation.js";
import { keeps, layoutPx as px } from "./keeps.js";
import { anchorElement, anchorName } from "./anchor-names.js";
import { shownWindow } from "./geometry.js";

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

// The edges that hold the box where the answer stands it, one per axis, with the box's
// size and its containing block's, which an inset on a right or bottom edge is measured
// from. It runs after the surface's middleware, so it reads the box as sized and shifted.
const held = {
  name: "held",
  async fn({ placement, rects, middlewareData, elements, platform }) {
    const [side, alignment] = placement.split("-");
    const aligned = (start, end) => (alignment === "end" ? end : start);
    const edges =
      side === "top" || side === "bottom"
        ? { x: aligned("left", "right"), y: side === "top" ? "bottom" : "top" }
        : { x: side === "left" ? "right" : "left", y: aligned("top", "bottom") };
    const shifted = middlewareData.shift ?? {};
    if (Math.abs(shifted.x ?? 0) >= 0.5) edges.x = shifted.x < 0 ? "right" : "left";
    if (Math.abs(shifted.y ?? 0) >= 0.5) edges.y = shifted.y < 0 ? "bottom" : "top";
    const parent = await platform.getOffsetParent(elements.floating);
    const block = parent === window ? document.documentElement : parent;
    return {
      data: {
        edges,
        width: rects.floating.width,
        height: rects.floating.height,
        block: { width: block.clientWidth, height: block.clientHeight },
      },
    };
  },
};

const INSETS = ["left", "right", "top", "bottom"];

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
  // Writes the held edges' insets and clears the free ones.
  const inset = (insets) => {
    for (const edge of INSETS)
      if (insets[edge] === undefined) floating.style.removeProperty(edge);
      else floating.style.setProperty(edge, insets[edge]);
  };
  // Each held edge's inset from the same edge of the box's containing block.
  const placedAt = ({ x, y, middlewareData }) => {
    const { edges, width, height, block } = middlewareData.held;
    floating.style.removeProperty("position-anchor");
    inset({
      [edges.x]: px(edges.x === "left" ? x : block.width - x - width),
      [edges.y]: px(edges.y === "top" ? y : block.height - y - height),
    });
  };
  // Each held edge's inset from the anchor's start edge on its axis, which `anchor()`
  // resolves as an inset on whichever side the property names. An anchor lost between
  // placements (a row withheld, a target skipped, its name taken by a revision) stands
  // the box off screen, as the rows fall back, until the placement that follows finds
  // it another.
  const anchoredAt =
    (anchor, at) =>
    ({ x, y, middlewareData }) => {
      const { edges, width, height } = middlewareData.held;
      const from = (side, length) => `calc(anchor(${side}, -9999px) + ${px(length)})`;
      floating.style.positionAnchor = anchorName(anchor);
      inset({
        [edges.x]: from("left", edges.x === "left" ? x - at.x : at.x - x - width),
        [edges.y]: from("top", edges.y === "top" ? y - at.y : at.y - y - height),
      });
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
    // `stand` then writes that answer's spot in its plane. An answer a later placement
    // superseded while it was computed is null, and writes nothing.
    async position(computePosition, reference, options, planeOf, beside) {
      const placement = epoch;
      const anchor =
        beside && CSS.supports("anchor-name", "--lf-anchor")
          ? anchorElement(beside)
          : null;
      const answer = await computePosition(reference, floating, {
        ...options,
        strategy: "fixed",
        middleware: [...options.middleware, held, anchorAt(reference, anchor)],
      });
      if (placement !== epoch) return null;
      const at = answer.middlewareData.anchorAt;
      const plane =
        at?.x !== undefined && planeOf(answer) === "page" ? "page" : "window";
      keeps(floating, "data-lf-plane", plane);
      stand = plane === "page" ? anchoredAt(anchor, at) : placedAt;
      return answer;
    },
    stand: (answer) => stand(answer),
    // Discards any placement in flight, leaving the box where it stands.
    supersede() {
      epoch += 1;
    },
    stop() {
      epoch += 1;
      stopWatching?.();
      stopWatching = null;
      watched = null;
      delete floating.dataset.lfPlane;
      for (const property of ["position-anchor", ...INSETS])
        floating.style.removeProperty(property);
    },
  };
}
