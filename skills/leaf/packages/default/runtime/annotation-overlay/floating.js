/* Floating UI for the page's floating surfaces: the response bar (composing/surface.js)
   and the inline thread card (margin-projection.js).

   Each places a box beside something on the page, and each leaves the browser's
   coordinate spaces to Floating UI. `computePosition` maps what the box stands against
   into the box's own positioning space: a containing block, a frame, or WebKit's
   visual-viewport offset for a fixed box under pinch zoom. `autoUpdate`
   follows every scroll container, resize, visual-viewport change, and layout shift that
   can move it. Which side a surface takes and how far it stands is stated as its
   middleware, by comment-placement.js for both.

   `floatingPlacement` is one box's lifecycle around those two calls: it watches the
   element the box stands against, re-arming when that element or its observation
   contract changes, and numbers each
   placement so an answer computed for an earlier one is dropped. A placement lands in
   the microtasks after the rendering pass that asks for it, before the frame paints.

   A fixed box stands in the plane of whatever holds it, so the scroll that moves that
   holder carries the box and a placement after it finds the same insets: the `page`'s
   where it stands beside what it is about, a `region`'s where the edge of a reading
   region it stands in holds it in, and the `window`'s where the window's edge does. The
   surface names the plane from the constraint that bound its answer (`planeOf`), not
   from where the box landed. In the page's plane the box is
   anchored (CSS anchor positioning) to the element it stands beside, with its spot
   written as insets from that anchor, so the browser carries it through every scroll
   that moves the anchor, in step with the words. A quote or shadow target can scroll
   inside that anchor; native ScrollTimeline motion layers carry those remaining axes.
   One viewport frame holds the surface's native subtree and solver coordinates. Its
   layer graph stays intact across size solves and transfers focus/caret through the
   existing focus owner only when that graph changes. The frame ignores pointer input;
   each surface's own CSS retains its interaction policy. Without the needed native
   capability, the existing observed placement path invalidates on scroll instead.
   In a region's plane the box is anchored to the region's body, the box whose edges
   bound it, which the outer scrolls carry and the region's own scroll does not. The containing frame stays fixed,
   so native focus never scrolls the page under it.

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

import { afterPresentation } from "/runtime/presentation.js";
import { keeps, layoutPx as px, atLayoutPrecision } from "/runtime/keeps.js";
import { anchorElement, anchorName } from "/runtime/anchor-names.js";
import { holdFocus } from "/runtime/focus.js";
import { shownBand } from "/runtime/geometry.js";
import { followScroll, scrollFollows, scrollMotions } from "/runtime/scroll-motion.js";
import { containingReadingRegionFor } from "/runtime/reading-regions.js";
import { upFrom } from "/runtime/shadow.js";

let floatingUiModule = null;
export const floatingUi = () =>
  (floatingUiModule ??= import("/vendor/floating-ui.esm.js"));
afterPresentation(floatingUi);

// How far the box's positioning space stands from client coordinates, read from the
// reference's rectangle in both, so any box measured with the reference can be named in
// that space. Nothing where a transform, filter, or containment between the box and the
// body makes some box other than the viewport its containing block, since an anchor
// outside that block cannot position it.
const anchorAt = (reference) => ({
  name: "anchorAt",
  async fn({ rects, elements, platform }) {
    if ((await platform.getOffsetParent(elements.floating)) !== window)
      return { data: { offset: null } };
    const client = reference.getBoundingClientRect();
    return {
      data: {
        offset: {
          x: rects.reference.x - client.left,
          y: rects.reference.y - client.top,
        },
      },
    };
  },
});

// The box whose edge holds a surface in: of the scrollers and reading regions around what
// it stands by, innermost first, the one whose box or visible band has that edge on the
// client line `at`. The window's edges and the banner's foot are none of theirs, which
// leaves the surface in the window's plane.
function holderOf({ edge, at }, context, overflowAncestors) {
  const candidates = overflowAncestors.filter(
    (source) => source instanceof Element && source !== document.scrollingElement,
  );
  for (
    let region = containingReadingRegionFor(context);
    region;
    region = upFrom(region.host) && containingReadingRegionFor(upFrom(region.host))
  )
    if (!candidates.includes(region.body)) candidates.push(region.body);
  return (
    candidates.find((box) =>
      [box.getBoundingClientRect(), shownBand(box)].some(
        (rect) => rect && Math.abs(rect[edge] - at) < 1,
      ),
    ) ?? null
  );
}

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

// The mechanical owner's last written placement, never a rectangle read back from
// its rendered box. Consumers can distinguish a native plane change from a local
// child/holder displacement without granting that displacement to the owner.
const stood = new Map();
export const floatingSelections = () => [...stood.values()];

export function floatingPlacement({ floating, update }) {
  // Native anchors carry all ancestors of their CSS box. Text inside a self-scroller
  // and targets inside a shadow host have additional scroll coordinates. Each missing
  // source/axis gets one nested compositor layer with a replacement transform. Additive
  // effects on one node compose a frame late; nested native layers compose in the same
  // scroll frame. The viewport frame remains the solver's containing block.
  let frame = floating;
  let layers = [];
  let graph = [];
  let restoreNativeFocus = null;
  function motionFrame(sources) {
    if (
      sources.length === graph.length &&
      sources.every(
        (motion, i) =>
          motion.source === graph[i].source && motion.axis === graph[i].axis,
      )
    )
      return;
    restoreNativeFocus = holdFocus(floating);
    if (frame === floating && sources.length) {
      frame = document.createElement("div");
      frame.className = "lf-ui";
      Object.assign(frame.style, {
        position: "fixed",
        display: "grid",
        width: "max-content",
        height: "max-content",
        pointerEvents: "none",
        zIndex: getComputedStyle(floating).zIndex,
      });
      floating.before(frame);
      Object.assign(floating.style, {
        position: "relative",
        left: "auto",
        right: "auto",
        top: "auto",
        bottom: "auto",
      });
    }
    if (frame === floating) return;
    // Actual graph changes transfer the native subtree through the existing focus
    // handoff. Ordinary size/layout solves keep both its ancestors and caret untouched.
    const previous = layers;
    layers = [];
    let parent = frame;
    for (let i = 0; i < sources.length; i++) {
      const layer = document.createElement("div");
      Object.assign(layer.style, {
        display: "grid",
        width: "max-content",
        height: "max-content",
        pointerEvents: "none",
      });
      parent.append(layer);
      layers.push(layer);
      parent = layer;
    }
    parent.append(floating);
    for (const layer of previous) layer.remove();
    graph = sources;
  }
  let epoch = 0;
  let watched = null;
  let observer = null;
  let tenure = Object.freeze({});
  let stopWatching = null;
  // Writes the held edges' insets and clears the free ones.
  const inset = (insets) => {
    for (const edge of INSETS)
      if (insets[edge] === undefined) frame.style.removeProperty(edge);
      else frame.style.setProperty(edge, insets[edge]);
  };
  // Each held edge's inset from the same edge of the box's containing block.
  const placedAt = ({ x, y, middlewareData }) => {
    const { edges, width, height, block } = middlewareData.held;
    frame.style.removeProperty("position-anchor");
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
      frame.style.positionAnchor = anchorName(anchor);
      inset({
        [edges.x]: from("left", edges.x === "left" ? x - at.x : at.x - x - width),
        [edges.y]: from("top", edges.y === "top" ? y - at.y : at.y - y - height),
      });
    };
  let stand = placedAt;
  let scrollAnimations = [];
  let placementProof = null;
  let stopScrollInvalidation = null;
  return {
    // `reference` is what `computePosition` receives; `element` is the node it stands
    // for; `autoUpdate` declares which mechanical changes invalidate its placement.
    watch(element, reference, autoUpdate) {
      if (element === watched && autoUpdate === observer) return;
      stopWatching?.();
      watched = element;
      observer = autoUpdate;
      tenure = Object.freeze({});
      stopWatching = autoUpdate(reference, floating, update);
    },
    holdsHome: (home) =>
      frame !== floating && frame.parentElement === home && frame.contains(floating),
    nativeAvailable: () =>
      CSS.supports("anchor-name", "--lf-anchor") && scrollFollows(),
    follows: () => placementProof?.plane === "page",
    begin: () => ++epoch,
    current: (placement) => placement === epoch,
    // Computes the answer, in the window's positioning space, and the constraint
    // `planeOf` reads as binding it: `"page"`, `"window"`, or the edge that holds it in
    // (`{edge, at}`), whose holder names the plane. `beside` is the element the box
    // stands beside in the page's plane. `stand` then writes that answer's spot in its
    // plane. An answer a later placement superseded while it was computed is null, and
    // writes nothing.
    async position(computePosition, reference, options, planeOf, beside) {
      const placement = epoch;
      const context = reference.contextNode ?? beside;
      const physical =
        context?.nodeType === Node.TEXT_NODE ? context.parentElement : context;
      const anchoring = CSS.supports("anchor-name", "--lf-anchor");
      const anchor = physical && anchoring ? anchorElement(physical) : null;
      const { getOverflowAncestors } = await floatingUi();
      if (placement !== epoch) return null;
      // Solver coordinates and native scroll origins are one measurement. A solve
      // can finish after scrolling; freezing both makes its native attachment carry
      // that intervening motion exactly once, regardless of when the solver reads.
      const client = anchor && reference.getBoundingClientRect();
      const anchorBox = anchor?.getBoundingClientRect();
      const measured = anchor
        ? {
            contextElement: reference.contextElement ?? beside,
            getBoundingClientRect: () => client,
          }
        : reference;
      const carried = new Set(anchor ? getOverflowAncestors(anchor) : []);
      // Each scroller carries the box it holds next on the way in: the next scroller, or
      // the element the reference stands in.
      const sources = context
        ? getOverflowAncestors(context).filter(
            (source) => source instanceof Element && !carried.has(source),
          )
        : [];
      const motions = sources.flatMap((source, i) =>
        scrollMotions(source, sources[i - 1] ?? physical),
      );
      const canFollow = anchor && (!motions.length || scrollFollows());
      motionFrame(canFollow ? motions : []);
      const answer = await computePosition(measured, frame, {
        ...options,
        strategy: "fixed",
        middleware: [...options.middleware, held, anchorAt(measured)],
      });
      if (placement !== epoch) return null;
      // An unchanged native graph keeps following while a solve is in flight. Retire
      // its previous effects only when this answer can replace their measurement.
      for (const animation of scrollAnimations) animation.cancel();
      scrollAnimations = [];
      const { offset } = answer.middlewareData.anchorAt;
      const wanted = planeOf(answer);
      const holder =
        anchoring && offset && physical && typeof wanted === "object"
          ? holderOf(wanted, physical, getOverflowAncestors(physical))
          : null;
      const plane =
        wanted === "page" && canFollow && offset
          ? "page"
          : holder
            ? "region"
            : "window";
      const frameAnchor =
        plane === "page" ? anchor : plane === "region" ? anchorElement(holder) : null;
      const frameBox =
        plane === "page" ? anchorBox : frameAnchor?.getBoundingClientRect();
      const at = offset && {
        x: offset.x + (frameBox?.left ?? 0),
        y: offset.y + (frameBox?.top ?? 0),
      };
      keeps(floating, "data-lf-plane", plane);
      stopScrollInvalidation?.();
      stopScrollInvalidation = null;
      if (plane !== "page") {
        // The existing compute/observe path remains the capability fallback. It also
        // hears a reference's own inner scroll when its semantic host does not move.
        const sources = context ? [...new Set(getOverflowAncestors(context))] : [];
        for (const source of sources)
          source.addEventListener("scroll", update, { passive: true });
        stopScrollInvalidation = () => {
          for (const source of sources) source.removeEventListener("scroll", update);
        };
      }
      if (plane === "page")
        scrollAnimations = motions.map((motion, i) =>
          followScroll(layers[i], motion, motion.scroll),
        );
      stand = frameAnchor ? anchoredAt(frameAnchor, at) : placedAt;
      // anchorAt proves the solver's containing block is the window. Other
      // containing blocks have no declared prediction in this selection.
      placementProof = at
        ? { subject: watched, anchor, frame: frameAnchor, plane, at }
        : null;
      return answer;
    },
    stand(answer) {
      stand(answer);
      restoreNativeFocus?.();
      restoreNativeFocus = null;
      if (!placementProof) {
        stood.delete(floating);
        tenure = Object.freeze({});
        return;
      }
      const { edges, width, height, block } = answer.middlewareData.held;
      const { subject, anchor, frame: frameAnchor, plane, at } = placementProof;
      const point = {};
      for (const [axis, start, coordinate, length, extent] of [
        ["left", "left", "x", width, block.width],
        ["top", "top", "y", height, block.height],
      ]) {
        const fromStart = edges[coordinate] === start;
        const spot = answer[coordinate];
        point[axis] = frameAnchor
          ? fromStart
            ? atLayoutPrecision(spot - at[coordinate])
            : -atLayoutPrecision(at[coordinate] - spot - length)
          : fromStart
            ? atLayoutPrecision(spot)
            : extent - atLayoutPrecision(extent - spot - length);
      }
      stood.set(
        floating,
        Object.freeze({
          floating,
          subject,
          anchor,
          frame: frameAnchor,
          plane,
          tenure,
          edges: Object.freeze({ left: edges.x, top: edges.y }),
          point: Object.freeze(point),
          size: Object.freeze({ width, height }),
        }),
      );
    },
    // Where an answer stands the box, in client coordinates, from the measurement it was
    // solved against rather than read off the box, which may not yet be laid out
    // where a scroll the browser carried it through has put it.
    clientBox(answer) {
      const { offset } = answer.middlewareData.anchorAt;
      const { width, height } = answer.middlewareData.held;
      return offset
        ? new DOMRect(answer.x - offset.x, answer.y - offset.y, width, height)
        : floating.getBoundingClientRect();
    },
    // Discards any placement in flight, leaving the box where it stands.
    supersede() {
      epoch += 1;
    },
    stop() {
      epoch += 1;
      for (const animation of scrollAnimations) animation.cancel();
      scrollAnimations = [];
      stopWatching?.();
      stopScrollInvalidation?.();
      stopScrollInvalidation = null;
      stopWatching = null;
      watched = null;
      observer = null;
      tenure = Object.freeze({});
      placementProof = null;
      stood.delete(floating);
      if (frame !== floating) {
        const restore = frame.contains(floating) && holdFocus(floating);
        if (frame.contains(floating)) frame.before(floating);
        frame.remove();
        frame = floating;
        layers = [];
        graph = [];
        floating.style.removeProperty("position");
        restore?.();
      }
      restoreNativeFocus = null;
      delete floating.dataset.lfPlane;
      for (const property of ["position-anchor", ...INSETS])
        floating.style.removeProperty(property);
    },
  };
}
