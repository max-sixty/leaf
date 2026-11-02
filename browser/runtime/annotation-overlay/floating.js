/* Floating UI for the page's floating surfaces: the response bar (composing/surface.js)
   and the inline thread card (thread-preview.js).

   Each places a box beside something on the page, and each leaves the browser's
   coordinate spaces to Floating UI. `computePosition` maps what the box stands against
   into the box's own positioning space: a containing block, a frame, or WebKit's
   visual-viewport offset for a fixed box under pinch zoom. `autoUpdate`
   follows every scroll container, resize, visual-viewport change, and layout shift that
   can move it. Which side a surface takes and how far it stands is stated as its
   middleware, by comment-placement.js for both.

   `floatingPlacement` is one box's lifecycle around those two calls: it watches the
   element the box stands against, re-arming when that element or its observation
   contract changes, including attribute-driven visibility changes in its composed
   ancestry, and numbers each placement so an earlier answer is dropped. A placement lands in
   the microtasks after the rendering pass that asks for it, before the frame paints.

   A fixed box stands in the plane of whatever holds it, so the scroll that moves that
   holder carries the box and a placement after it finds the same insets: the `page`'s
   where it stands beside what it is about, a `region`'s where the edge of a reading
   region it stands in holds it in, and the `window`'s where the window's edge does. The
   surface names the plane from the constraint that bound its answer (`planeOf`), not
   from where the box landed. In the page's plane the box is
   anchored (CSS anchor positioning) to the element it stands beside, with its spot
   written as insets from that anchor, so the browser carries it through every scroll
   that moves the anchor, in step with the words, as every box that follows scrolled
   content is carried (css-anchors.js). Words standing directly in a box that scrolls
   them anchor to the nearest element beside them in that box, or to the start of what
   it holds, which the same scroll carries (`anchorFor`), and words in a widget's shadow
   tree to their own element, which the document names through a part. The surface is
   not cut at a scroller's edge, since it reaches past the words it is about, so it
   stands in no frame. In a region's plane the box is anchored to the region's body, the
   box whose edges bound it, which the outer scrolls carry and the region's own scroll
   does not. In the region's and the window's planes the answer depends on where the
   words stand inside what holds the box in, so each scroll around them solves it again.
   The box stays fixed, so native focus never scrolls the page under it.
   Unlike the margin's rows and Copy, the surface stays over the sticky headers a page
   declares rather than passing under them (css-anchors.js, `headerLevels`): it is where
   the user is writing or reading a reply, and words scrolled under a stuck toolbar
   would take the editor with them, out of reach until the user scrolled back.

   In either plane the box stands by the edges that hold it, one per axis (`held`). On
   the axis its placement stands it beside something, that is the edge facing it; on the
   other, the edge its alignment names, the start for a centred box, or the edge the
   surface keeps still of its own accord (a `hold` middleware's `edge`); and on an axis
   where the boundary shifted the box in, the edge against that boundary. Content that
   grows the box then moves only its free edges, in the layout that grows it. Stood by
   its top-left corner, a box that grows at its left or top would paint grown the wrong
   way for a frame, until the placement that follows the resize carried it back. A `hold`
   that carries an inline offset names that axis's edge too (`inline`).

   Neither surface stands before the user acts, so the bundle stays off the presentation
   path and loads as soon as the page has presented, as an arrival the page answers for.
   A surface's first placement then lands in the frame that asks for it rather than
   after a fetch. */

import { afterPresentation } from "../presentation.js";
import { visibleTargetParts } from "../visible-target-parts.js";
import { keeps, layoutPx as px, atLayoutPrecision } from "../keeps.js";
import { anchorBox, anchorElement, anchorFor, anchorName } from "../css-anchors.js";
import { shownBand } from "../geometry.js";
import { containingReadingRegionFor } from "../reading-regions.js";
import { upFrom, renderedParent } from "../shadow.js";

/** @typedef {import("@floating-ui/dom").MiddlewareState} MiddlewareState */
/** @typedef {import("@floating-ui/dom").ComputePositionReturn} Position */
/** @typedef {import("@floating-ui/dom").Side} Side */
/** @typedef {{x: number, y: number}} Point */
/** @typedef {{edge: Side, at: number}} HoldingEdge */
/** @typedef {"page" | "window" | "region"} Plane */
/** @typedef {import("@floating-ui/dom").VirtualElement & {
 * contextNode?: Node | null, geometry?: ReturnType<typeof floatingGeometry>
 * }} FloatingReference */
/** @typedef {{subject: Element | null, anchor: ReturnType<typeof anchorFor>,
 * frame: ReturnType<typeof anchorFor>, plane: Plane, at: Point}} PlacementProof */
/** @typedef {{floating: HTMLElement, subject: Element | null,
 * anchor: ReturnType<typeof anchorFor>, frame: ReturnType<typeof anchorFor>,
 * plane: Plane, tenure: object, edges: {left: "left" | "right", top: "top" | "bottom"},
 * point: {left: number, top: number}, size: {width: number, height: number}}} FloatingSelection */

/** @type {Promise<typeof import("/vendor/floating-ui.esm.js")> | null} */
let floatingUiModule = null;
export const floatingUi = () =>
  (floatingUiModule ??= import("/vendor/floating-ui.esm.js"));
afterPresentation(floatingUi);

// Ask the solver's platform how one positioning pixel reaches the viewport. A Window
// offset parent can still be scaled by CSS zoom; getScale(Window) cannot describe it.
/** @param {Pick<MiddlewareState, "elements" | "platform" | "strategy">} state */
export async function positioningScale({ elements, platform, strategy }) {
  const unit = await platform.convertOffsetParentRelativeRectToViewportRelativeRect({
    elements,
    offsetParent: await platform.getOffsetParent(elements.floating),
    strategy,
    rect: { x: 0, y: 0, width: 1, height: 1 },
  });
  return { x: unit.width, y: unit.height };
}

// How far the box's positioning space stands from client coordinates, read from the
// reference's rectangle in both, so any box measured with the reference can be named in
// that space. Nothing where a transform, filter, or containment between the box and the
// body makes some box other than the viewport its containing block, since an anchor
// outside that block cannot position it.
/** @param {import("@floating-ui/dom").ReferenceElement} reference @returns {import("@floating-ui/dom").Middleware} */
const anchorAt = (reference) => ({
  name: "anchorAt",
  async fn(state) {
    const { rects, elements, platform } = state;
    if ((await platform.getOffsetParent(elements.floating)) !== window)
      return { data: { offset: null } };
    const client = reference.getBoundingClientRect();
    const scale = await positioningScale(state);
    return {
      data: {
        scale,
        offset: {
          x: rects.reference.x - client.left / scale.x,
          y: rects.reference.y - client.top / scale.y,
        },
      },
    };
  },
});

// The box whose edge holds a surface in: of the scrollers and reading regions around what
// it stands by, innermost first, the one whose box or visible band has that edge on the
// client line `at`. The window's edges and its head room are none of theirs, which
// leaves the surface in the window's plane.
/** @param {HoldingEdge} holding @param {Element} context @param {ReturnType<typeof import("@floating-ui/dom").getOverflowAncestors>} overflowAncestors */
function holderOf({ edge, at }, context, overflowAncestors) {
  const candidates = overflowAncestors.filter(
    /** @returns {source is Element} */
    (source) => source instanceof Element && source !== document.scrollingElement,
  );
  /** @type {ReturnType<typeof containingReadingRegionFor> | null} */
  let region = containingReadingRegionFor(context);
  while (region) {
    if (!candidates.includes(region.body)) candidates.push(region.body);
    region = upFrom(region.host) && containingReadingRegionFor(upFrom(region.host));
  }
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
// A surface middleware named `hold` that keeps a block edge still reports it as `edge`,
// and one that carries an inline offset its inline edge as `inline`; an edge the
// boundary shifted the box against outranks either.
/** @type {import("@floating-ui/dom").Middleware} */
const held = {
  name: "held",
  async fn(state) {
    const { placement, rects, middlewareData, elements, platform } = state;
    const [side, alignment] = placement.split("-");
    /** @template {string} T @param {T} start @param {T} end */
    const aligned = (start, end) => (alignment === "end" ? end : start);
    /** @type {{x: "left" | "right", y: "top" | "bottom"}} */
    const edges =
      side === "top" || side === "bottom"
        ? { x: aligned("left", "right"), y: side === "top" ? "bottom" : "top" }
        : { x: side === "left" ? "right" : "left", y: aligned("top", "bottom") };
    edges.y = middlewareData.hold?.edge ?? edges.y;
    edges.x = middlewareData.hold?.inline ?? edges.x;
    const shiftX = middlewareData.shift?.x ?? 0;
    const shiftY = middlewareData.shift?.y ?? 0;
    if (Math.abs(shiftX) >= 0.5) edges.x = shiftX < 0 ? "right" : "left";
    if (Math.abs(shiftY) >= 0.5) edges.y = shiftY < 0 ? "bottom" : "top";
    const parent = await platform.getOffsetParent(elements.floating);
    const block = parent instanceof Element ? parent : document.documentElement;
    // Client dimensions belong to the block's CSS pixels, except the standards-mode
    // root's viewport pixels. Cross through the platform's viewport conversion so
    // a surface zoomed relative to an element block keeps the same positioning units.
    const scale = await positioningScale(state);
    const blockScale =
      parent === window ? { x: 1, y: 1 } : await platform.getScale(parent);
    return {
      data: {
        edges,
        width: rects.floating.width,
        height: rects.floating.height,
        block: {
          width: (block.clientWidth * blockScale.x) / scale.x,
          height: (block.clientHeight * blockScale.y) / scale.y,
        },
      },
    };
  },
};

/** @type {readonly Side[]} */
const INSETS = ["left", "right", "top", "bottom"];

// The mechanical owner's last written placement in viewport pixels, relative to
// its frame, never a rectangle read back from its rendered box. Consumers can
// distinguish a native plane change from a local child/holder displacement
// without granting that displacement to the owner.
/** @type {Map<HTMLElement, FloatingSelection>} */
const stood = new Map();
export const floatingSelections = () => [...stood.values()];
// The edges that hold a placed box where its placement stood it, as box-motion.js reads
// them (`held`), or null for a box no placement stands.
/** @param {HTMLElement} floating */
export const heldEdges = (floating) => {
  const edges = stood.get(floating)?.edges;
  return edges ? { x: edges.left, y: edges.top } : null;
};

/** @param {Node | null | undefined} context */
const physicalContext = (context) =>
  context instanceof Element ? context : context?.parentElement;

// A surface anchors to `context` (css-anchors.js, `anchorFor`). A presenter can retain
// this reading beside its reference rectangle before a module load: the anchor boxes
// must describe the same geometry as that rectangle.
/** @param {readonly (Node | null | undefined)[]} contexts */
export function floatingGeometry(contexts) {
  const anchors = new Map();
  for (const context of contexts) {
    const anchor = anchorFor(context ?? null);
    if (anchor) anchors.set(anchor, anchorBox(anchor));
  }
  return { anchors };
}

/** @param {{floating: HTMLElement, update: () => void}} options */
export function floatingPlacement({ floating, update }) {
  let epoch = 0;
  /** @type {Element | null} */
  let watched = null;
  /** @type {object | null} */
  let observer = null;
  let tenure = Object.freeze({});
  /** @type {(() => void) | null} */
  let stopWatching = null;
  /** @type {{anchor: import("../css-anchors.js").Anchor, edgeX: "left" | "right", edgeY: "top" | "bottom", lengthX: number, lengthY: number} | null} */
  let lastAnchorStand = null;
  // Writes the held edges' insets and clears the free ones.
  /** @param {Partial<Record<Side, string>>} insets */
  const inset = (insets) => {
    for (const edge of INSETS)
      if (insets[edge] === undefined) floating.style.removeProperty(edge);
      else floating.style.setProperty(edge, insets[edge]);
  };
  // Each held edge's inset from the same edge of the box's containing block.
  /** @param {Position} answer */
  const placedAt = ({ x, y, middlewareData }) => {
    lastAnchorStand = null;
    const { edges, width, height, block } = middlewareData.held;
    floating.style.removeProperty("position-anchor");
    inset({
      [edges.x]: px(edges.x === "left" ? x : block.width - x - width),
      [edges.y]: px(edges.y === "top" ? y : block.height - y - height),
    });
  };
  // Each held edge's inset from the anchor's start edge on its axis, which `anchor()`
  // resolves as an inset on whichever side the property names. An anchor lost between
  // placements retains the last solved spot until its owner repositions or withdraws
  // the box. Replacing a target must not send an active editor off screen between
  // the native anchor disappearing and the next asynchronous solve.
  /** @param {import("../css-anchors.js").Anchor} anchor @param {Point} at */
  const anchoredAt =
    (anchor, at) =>
    /** @param {Position} answer */
    ({ x, y, middlewareData }) => {
      const { edges, width, height, block } = middlewareData.held;
      const lengthX = atLayoutPrecision(
        edges.x === "left" ? x - at.x : at.x - x - width,
      );
      const lengthY = atLayoutPrecision(
        edges.y === "top" ? y - at.y : at.y - y - height,
      );
      // Scrolling carries the anchor itself. Re-solving an unchanged offset must
      // not write a new fallback position and repaint the page's highlights.
      if (
        lastAnchorStand &&
        lastAnchorStand.anchor === anchor &&
        lastAnchorStand.edgeX === edges.x &&
        lastAnchorStand.edgeY === edges.y &&
        lastAnchorStand.lengthX === lengthX &&
        lastAnchorStand.lengthY === lengthY
      )
        return;
      /** @param {"left" | "top"} side @param {number} length @param {number} fallback */
      const from = (side, length, fallback) =>
        `calc(anchor(${side}, ${px(fallback)}) + ${px(length)})`;
      floating.style.positionAnchor = anchorName(anchor);
      inset({
        [edges.x]: from(
          "left",
          lengthX,
          edges.x === "left" ? at.x : block.width - at.x,
        ),
        [edges.y]: from("top", lengthY, edges.y === "top" ? at.y : block.height - at.y),
      });
      lastAnchorStand = {
        anchor,
        edgeX: edges.x,
        edgeY: edges.y,
        lengthX,
        lengthY,
      };
    };
  let stand = placedAt;
  /** @type {PlacementProof | null} */
  let placementProof = null;
  /** @type {(() => void) | null} */
  let stopScrollInvalidation = null;
  return {
    // `reference` is what `computePosition` receives; `element` is the node it stands
    // for; `autoUpdate` declares which mechanical changes invalidate its placement.
    /** @template {import("@floating-ui/dom").ReferenceElement} R
     * @param {Element} element @param {R} reference
     * @param {(reference: R, floating: HTMLElement, update: () => void) => () => void} autoUpdate */
    watch(element, reference, autoUpdate) {
      if (element === watched && autoUpdate === observer) return;
      stopWatching?.();
      watched = element;
      observer = autoUpdate;
      tenure = Object.freeze({});
      const stopGeometry = autoUpdate(reference, floating, update);
      // Visibility can change without moving or resizing a box. Observe the subject's
      // composed ancestry alongside Floating UI's geometry watch, including while the
      // surface is withheld. A `display: contents` subject has no box of its own, so its
      // descendants supply both the visibility reading and the mutations that change it.
      // Only a changed visibility reading invalidates placement.
      let visible = visibleTargetParts(element).length > 0;
      /** @type {boolean | null} */
      let observesParts = null;
      const visibility = new MutationObserver(() => {
        observeVisibility();
        const next = visibleTargetParts(element).length > 0;
        if (next === visible) return;
        visible = next;
        update();
      });
      const observeVisibility = () => {
        const parts = getComputedStyle(element).display === "contents";
        if (parts === observesParts) return;
        visibility.disconnect();
        visibility.observe(element, {
          attributes: true,
          subtree: parts,
          childList: parts,
        });
        for (let at = renderedParent(element); at; at = renderedParent(at))
          if (at instanceof Element) visibility.observe(at, { attributes: true });
        observesParts = parts;
      };
      observeVisibility();
      stopWatching = () => {
        visibility.disconnect();
        stopGeometry();
      };
    },
    follows: () => placementProof?.plane === "page",
    begin: () => ++epoch,
    /** @param {number} placement */
    current: (placement) => placement === epoch,
    // Computes the answer, in the window's positioning space, and the constraint
    // `planeOf` reads as binding it: `"page"`, `"window"`, or the edge that holds it in
    // (`{edge, at}`), whose holder names the plane. `beside` is the element the box
    // stands beside in the page's plane. `stand` then writes that answer's spot in its
    // plane. An answer a later placement superseded while it was computed is null, and
    // writes nothing.
    /** @param {typeof import("@floating-ui/dom").computePosition} computePosition
     * @param {FloatingReference} reference
     * @param {Partial<import("@floating-ui/dom").ComputePositionConfig> & {middleware: import("@floating-ui/dom").Middleware[]}} options
     * @param {(answer: Position) => "page" | "window" | HoldingEdge} planeOf
     * @param {Element} beside */
    async position(computePosition, reference, options, planeOf, beside) {
      const placement = epoch;
      const context = reference.contextNode ?? beside;
      const physical = physicalContext(context);
      const anchor = anchorFor(context ?? null);
      const client = reference.getBoundingClientRect();
      const geometry = reference.geometry ?? floatingGeometry([context]);
      const anchorStood = geometry.anchors.get(anchor);
      const { getOverflowAncestors } = await floatingUi();
      if (placement !== epoch) return null;
      // Solver coordinates and the anchor's box are one reading. Capturing it before
      // asynchronous solving keeps the placement consistent, regardless of when the
      // solver reads. Retain the synthetic rectangle itself: placement middleware can
      // refine it and request remeasurement without reading live DOM again.
      const measured = {
        contextElement: reference.contextElement ?? beside,
        getBoundingClientRect: () => client,
      };
      const answer = await computePosition(measured, floating, {
        ...options,
        strategy: "fixed",
        middleware: [...options.middleware, held, anchorAt(measured)],
      });
      if (placement !== epoch) return null;
      const { offset, scale } = answer.middlewareData.anchorAt;
      const wanted = planeOf(answer);
      const holder =
        offset && physical && typeof wanted === "object"
          ? holderOf(wanted, physical, getOverflowAncestors(physical))
          : null;
      const plane =
        wanted === "page" && anchorStood && offset
          ? "page"
          : holder
            ? "region"
            : "window";
      const frameAnchor =
        plane === "page" ? anchor : holder ? anchorElement(holder) : null;
      const frameBox =
        plane === "page" ? anchorStood : frameAnchor && anchorBox(frameAnchor);
      const at = offset && {
        x: offset.x + (frameBox?.left ?? 0) / scale.x,
        y: offset.y + (frameBox?.top ?? 0) / scale.y,
      };
      keeps(floating, "data-lf-plane", plane);
      stopScrollInvalidation?.();
      stopScrollInvalidation = null;
      if (plane !== "page") {
        // Off the page's plane the answer depends on where the words stand in what holds
        // the box in, so every scroll around them solves it again, a scroll inside the
        // tree of a reference whose host does not move included.
        const sources = context ? [...new Set(getOverflowAncestors(context))] : [];
        for (const source of sources)
          source.addEventListener("scroll", update, { passive: true });
        stopScrollInvalidation = () => {
          for (const source of sources) source.removeEventListener("scroll", update);
        };
      }
      stand = frameAnchor ? anchoredAt(frameAnchor, at) : placedAt;
      // anchorAt proves the solver's containing block is the window. Other
      // containing blocks have no declared prediction in this selection.
      placementProof = at
        ? {
            subject: watched,
            anchor,
            frame: frameAnchor,
            plane,
            at,
          }
        : null;
      return answer;
    },
    /** @param {Position} answer */
    stand(answer) {
      /** @param {Position} answer */
      stand(answer);
      if (!placementProof) {
        stood.delete(floating);
        tenure = Object.freeze({});
        return;
      }
      const { edges, width, height, block } = answer.middlewareData.held;
      const { offset, scale } = answer.middlewareData.anchorAt;
      const { subject, anchor, frame: frameAnchor, plane, at } = placementProof;
      /** @param {"x" | "y"} coordinate @param {"left" | "top"} start
       * @param {number} length @param {number} extent */
      const axisPoint = (coordinate, start, length, extent) => {
        const fromStart = edges[coordinate] === start;
        const spot = answer[coordinate];
        const point = frameAnchor
          ? fromStart
            ? atLayoutPrecision(spot - at[coordinate])
            : -atLayoutPrecision(at[coordinate] - spot - length)
          : fromStart
            ? atLayoutPrecision(spot)
            : extent - atLayoutPrecision(extent - spot - length);
        return (point - (frameAnchor ? 0 : offset[coordinate])) * scale[coordinate];
      };
      const point = {
        left: axisPoint("x", "left", width, block.width),
        top: axisPoint("y", "top", height, block.height),
      };
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
          size: Object.freeze({ width: width * scale.x, height: height * scale.y }),
        }),
      );
    },
    // Where an answer stands the box, in client coordinates, from the measurement it was
    // solved against rather than read off the box, which may not yet be laid out
    // where a scroll the browser carried it through has put it.
    /** @param {Position} answer */
    clientBox(answer) {
      const { offset, scale } = answer.middlewareData.anchorAt;
      const { width, height } = answer.middlewareData.held;
      return offset
        ? new DOMRect(
            (answer.x - offset.x) * scale.x,
            (answer.y - offset.y) * scale.y,
            width * scale.x,
            height * scale.y,
          )
        : floating.getBoundingClientRect();
    },
    // Discards any placement in flight, leaving the box where it stands.
    supersede() {
      epoch += 1;
    },
    stop() {
      epoch += 1;
      lastAnchorStand = null;
      stopWatching?.();
      stopScrollInvalidation?.();
      stopScrollInvalidation = null;
      stopWatching = null;
      watched = null;
      observer = null;
      tenure = Object.freeze({});
      placementProof = null;
      stood.delete(floating);
      delete floating.dataset.lfPlane;
      for (const property of ["position-anchor", ...INSETS])
        floating.style.removeProperty(property);
    },
  };
}
