/* Floating UI for the page's floating surfaces: the response bar (annotations/composing/surface.js)
   and the inline thread card (thread-preview.js).

   Each places a box beside something on the page, and each leaves the browser's
   coordinate spaces to Floating UI. `computePosition` maps what the box stands against
   into the box's own positioning space: a containing block, a frame, or WebKit's
   visual-viewport offset for a fixed box under pinch zoom. `autoUpdate` follows every
   resize and layout shift that can move it, and `floatingPlacement` every scroll
   (below). Which side a surface takes and how far it stands is stated as its
   middleware, by comment-placement.js for both.

   `floatingPlacement` is one box's lifecycle around those two calls: it watches the
   element the box stands against, re-arming when that element or its observation
   contract changes, including attribute-driven visibility changes in its composed
   ancestry, and numbers each placement so an earlier answer is dropped. A placement lands in
   the microtasks after the rendering pass that asks for it, before the frame paints.

   A fixed box stands in the plane of whatever holds it, so the scroll that moves that
   holder carries the box and a placement after it finds the same insets: the `page`'s
   where it stands beside what it is about, a `region`'s where the edge of a box around
   it, such as a reading region it stands in, holds it in, and the `window`'s where the
   window's edge does. The surface names the plane from the constraint that bound its
   answer (`planeOf`), the holding box included, not from where the box landed. In the
   page's plane the box is anchored (CSS anchor positioning) to the element it stands
   beside, with its spot written as insets from that anchor, so the browser carries it
   through every scroll that moves the anchor, in step with the words, as every box that
   follows scrolled content is carried (dom/css-anchors.js). Words standing directly in a box that scrolls
   them anchor to the nearest element beside them in that box, or to the start of what
   it holds, which the same scroll carries (`anchorFor`), and words in a widget's shadow
   tree to their own element, which the document names through a part. The surface is
   not cut at a scroller's edge, since it reaches past the words it is about, so it
   stands in no frame. In a region's plane the box is anchored to the box whose edge
   holds it, which the outer scrolls carry and that box's own scroll does not. Each
   scroll around the words solves the box again, whichever surface it is: the
   placement listens to every scroller around the element it watches, and once an
   answer stands the box beside the words, around them, one inside the tree of a
   reference whose host does not move included (`watch`). In
   the page's plane the answer writes nothing until an edge takes the box in; in the
   region's and the window's planes it moves the box as the words move inside the box
   that holds it in. Rejected: holding a box in by CSS alone, its inset clamped between
   the window's edge and its anchor's (`clamp()` over `anchor()`). Chromium 159 solves
   that at every frame, but Firefox 159 solves it once and then carries the box by the
   scroll, as it does any anchored box, and WebKit 27.2 does the same under the wheel,
   so there a box beside a tall element rode off the window's top.
   The box stays fixed, so native focus never scrolls the page under it.
   Unlike the margin's rows and Copy, the surface stays over the sticky headers a page
   declares rather than passing under them (dom/css-anchors.js, `headerLevels`): it is where
   the user is writing or reading a reply, and words scrolled under a stuck toolbar
   would take the editor with them, out of reach until the user scrolled back.

   In either plane the box stands by the edges that hold it, one per axis (`held`). On
   the axis its placement stands it beside something, that is the edge facing it; on the
   other, the edge its alignment names, the start for a centred box, or the edge the
   surface names (a `hold` middleware's `edge`): the one it keeps still, or its foot
   where it keeps a line between its edges (comment-placement.js); and on an axis
   where the boundary shifted the box in, the edge against that boundary. Content that
   grows the box then moves only its free edges, in the layout that grows it. Stood by
   its top-left corner, a box that grows at its left or top would paint grown the wrong
   way for a frame, until the placement that follows the resize carried it back. A `hold`
   that carries an inline offset names that axis's edge too (`inline`).

   Neither surface stands before the user acts, so the bundle stays off the presentation
   path and loads as soon as the page has presented, as an arrival the page answers for.
   A surface's first placement then lands in the frame that asks for it rather than
   after a fetch.

   The root's scroll padding keeps a landing clear of the chrome (base.css). Chromium
   and WebKit apply it to a caret reveal in an editor these surfaces hold too, carrying
   the reveal through the box's anchor and moving the document beneath an editor already
   in view. So while the user is in a `leaf-text` inside a box standing in a plane,
   the root says so (`data-lf-floating-editor`, base.css), and is read again
   as the user moves and as a box takes or leaves its plane (`readFloatingEditor`). The
   root is the scroller the padding belongs to; a `:has()` on it matches its argument
   against the whole document at each write. */

import { afterPresentation } from "../../readings/presentation.js";
import { visibleTargetParts } from "../../readings/visible-target-parts.js";
import { keeps, layoutPx as px, atLayoutPrecision } from "../../lib/keeps.js";
import { focused, onCurrentLocation } from "../../dom/focus.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "../../base/page-paint.js";
import {
  anchorBox,
  anchorElement,
  anchorFor,
  anchorName,
} from "../../dom/css-anchors.js";
import { renderedParent } from "../../lib/shadow-tree.js";

/** @typedef {import("@floating-ui/dom").MiddlewareState} MiddlewareState */
/** @typedef {import("@floating-ui/dom").ComputePositionReturn} Position */
/** @typedef {import("@floating-ui/dom").Side} Side */
/** @typedef {{x: number, y: number}} Point */
/** @typedef {"page" | "window" | "region"} Plane */
/** @typedef {import("@floating-ui/dom").VirtualElement & {
 * contextNode?: Node | null, geometry?: ReturnType<typeof floatingGeometry>
 * }} FloatingReference */
/** @typedef {{subject: Element | null, anchor: ReturnType<typeof anchorFor>,
 * frame: ReturnType<typeof anchorFor>, plane: Plane, at: Point}} PlacementProof */
/** @typedef {import("../../dom/box-motion.js").Held} Held */
/** @typedef {import("../../dom/box-motion.js").Stood} Stood */
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

// The edges that hold the box where the answer stands it, one per axis, with the box's
// size. It runs after the surface's middleware, so it reads the box as sized and shifted.
// A surface middleware named `hold` names the block edge to stand the box by as `edge`,
// and one that carries an inline offset its inline edge as `inline`; an edge the
// boundary shifted the box against outranks either.
/** @type {import("@floating-ui/dom").Middleware} */
const held = {
  name: "held",
  fn(state) {
    const { placement, rects, middlewareData } = state;
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
    return {
      data: { edges, width: rects.floating.width, height: rects.floating.height },
    };
  },
};

// An inset on a right or bottom edge that stands that edge `end` positioning pixels from
// the containing block's start. It is measured by the block's own size (`100%`), which
// layout holds to its fraction where a script reads it only to a whole pixel
// (`clientWidth`), as a window at a zoom such as 110% leaves it.
/** @param {number} end */
const fromFar = (end) => `calc(100% - ${px(end)})`;

/** @type {readonly Side[]} */
const INSETS = ["left", "right", "top", "bottom"];

// The mechanical owner's last written placement in viewport pixels, relative to
// its frame, never a rectangle read back from its rendered box. Consumers can
// distinguish a native plane change from a local child/holder displacement
// without granting that displacement to the owner.
/** @type {Map<HTMLElement, FloatingSelection>} */
const stood = new Map();
export const floatingSelections = () => [...stood.values()];

// Whether the user is in an editor a floating box holds, said on the root (header).
function readFloatingEditor() {
  const editing = focused()?.closest("[data-lf-plane] leaf-text");
  keeps(
    document.documentElement,
    RUNTIME_PAINT_ATTRIBUTE.floatingEditor,
    editing ? "" : null,
  );
}
onCurrentLocation(readFloatingEditor);

// A surface anchors to `context` (dom/css-anchors.js, `anchorFor`). A presenter can retain
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
  /** @type {{anchor: import("../../dom/css-anchors.js").Anchor, edgeX: "left" | "right", edgeY: "top" | "bottom", lengthX: number, lengthY: number} | null} */
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
    const { edges, width, height } = middlewareData.held;
    floating.style.removeProperty("position-anchor");
    inset({
      [edges.x]: edges.x === "left" ? px(x) : fromFar(x + width),
      [edges.y]: edges.y === "top" ? px(y) : fromFar(y + height),
    });
  };
  // Each held edge's inset from the anchor's start edge on its axis, which `anchor()`
  // resolves as an inset on whichever side the property names. An anchor lost between
  // placements retains the last solved spot until its owner repositions or withdraws
  // the box. Replacing a target must not send an active editor off screen between
  // the native anchor disappearing and the next asynchronous solve.
  /** @param {import("../../dom/css-anchors.js").Anchor} anchor @param {Point} at */
  const anchoredAt =
    (anchor, at) =>
    /** @param {Position} answer */
    ({ x, y, middlewareData }) => {
      const { edges, width, height } = middlewareData.held;
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
      /** @param {"left" | "top"} side @param {number} length @param {string} fallback */
      const from = (side, length, fallback) =>
        `calc(anchor(${side}, ${fallback}) + ${px(length)})`;
      floating.style.positionAnchor = anchorName(anchor);
      inset({
        [edges.x]: from("left", lengthX, edges.x === "left" ? px(at.x) : fromFar(at.x)),
        [edges.y]: from("top", lengthY, edges.y === "top" ? px(at.y) : fromFar(at.y)),
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
  // What holds the box where its last placement stood it (`held`), and the size it
  // stood at, in positioning pixels. We could consider, in future, keeping `stood` for a
  // placement with no proof too, so `held` reads its edges rather than this copy, and
  // having box-motion hand the placement the size it last read, so one place holds the
  // box's old size: the two differ where a reading takes a resize no placement answers,
  // as while the grip carries a card.
  /** @type {Held | null} */
  let holding = null;
  /** @type {{width: number, height: number} | null} */
  let stoodSize = null;
  // Each answer's placement of the box at the size it last stood at, where the answer
  // stands it at another (`position`).
  /** @type {WeakMap<Position, Position>} */
  const atStoodSize = new WeakMap();
  // The scrollers around the element the box is watched against, or around the words
  // the last answer stood it beside, each of whose scrolls solves it again.
  /** @type {{context: Node | null, stop: () => void} | null} */
  let scrolls = null;
  /** @param {Node | null} context
   * @param {typeof import("@floating-ui/dom").getOverflowAncestors} overflowAncestors */
  const hearScrolls = (context, overflowAncestors) => {
    if (scrolls?.context === context) return;
    scrolls?.stop();
    const sources = context ? [...new Set(overflowAncestors(context))] : [];
    for (const source of sources)
      source.addEventListener("scroll", update, { passive: true });
    scrolls = {
      context,
      stop: () => {
        for (const source of sources) source.removeEventListener("scroll", update);
      },
    };
  };
  // Where an answer stands the box, in client coordinates, from the measurement it was
  // solved against rather than read off the box, which may not yet be laid out where a
  // scroll the browser carried it through has put it, or, just taken into its anchor's
  // plane, where that anchor stands.
  /** @param {Position} answer */
  function clientBox(answer) {
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
  }
  return {
    // `reference` is what `computePosition` receives; `element` is the node it stands
    // for; `autoUpdate` declares which other mechanical changes invalidate its
    // placement. Scrolls are this placement's own: each scroller around `element`
    // solves the box again from the watch on, a box no placement has stood yet
    // included, and each placement listens around the words it stood the box beside.
    /** @template {import("@floating-ui/dom").ReferenceElement} R
     * @param {Element} element @param {R} reference
     * @param {(reference: R, floating: HTMLElement, update: () => void, options: {ancestorScroll: false}) => () => void} autoUpdate
     * @param {typeof import("@floating-ui/dom").getOverflowAncestors} overflowAncestors */
    watch(element, reference, autoUpdate, overflowAncestors) {
      if (element === watched && autoUpdate === observer) return;
      stopWatching?.();
      watched = element;
      observer = autoUpdate;
      tenure = Object.freeze({});
      hearScrolls(element, overflowAncestors);
      const stopGeometry = autoUpdate(reference, floating, update, {
        ancestorScroll: false,
      });
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
    // `planeOf` reads as binding it: `"page"`, `"window"`, or the box whose edge holds it
    // in, which names the region's plane. `beside` is the element the box stands beside
    // in the page's plane. `stand` then writes that answer's spot in its plane. An
    // answer a later placement superseded while it was computed is null, and writes
    // nothing.
    /** @param {typeof import("@floating-ui/dom").computePosition} computePosition
     * @param {FloatingReference} reference
     * @param {Partial<import("@floating-ui/dom").ComputePositionConfig> & {middleware: import("@floating-ui/dom").Middleware[]}} options
     * @param {(answer: Position) => "page" | "window" | Element} planeOf
     * @param {Element} beside */
    async position(computePosition, reference, options, planeOf, beside) {
      const placement = epoch;
      const context = reference.contextNode ?? beside;
      const anchor = anchorFor(context);
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
      const holder = offset && wanted instanceof Element ? wanted : null;
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
      readFloatingEditor();
      hearScrolls(context, getOverflowAncestors);
      stand = frameAnchor ? anchoredAt(frameAnchor, at) : placedAt;
      // anchorAt proves the solver's containing block is the window. Other
      // containing blocks have no declared prediction in this selection.
      placementProof = at
        ? { subject: watched, anchor, frame: frameAnchor, plane, at }
        : null;
      // The box changed size since it last stood: the same placement is solved for it
      // at that size too, which its motion takes as where the box would have stood had
      // it kept its size (dom/box-motion.js, `placed`). It is solved after the surface has
      // read its answer (`planeOf`), from the room its middleware keeps from the last
      // solve, and without sizing, which writes the box's size. It names itself to that
      // middleware (`stood`), which then answers for the box as it stood.
      const { width, height } = answer.middlewareData.held;
      if (
        stoodSize &&
        (Math.abs(width - stoodSize.width) >= 0.5 ||
          Math.abs(height - stoodSize.height) >= 0.5)
      ) {
        const size = stoodSize;
        const before = await computePosition(measured, floating, {
          ...options,
          strategy: "fixed",
          // Floating UI lays this over its own platform, which measures the box by it.
          platform: /** @type {import("@floating-ui/dom").Platform} */ (
            /** @type {unknown} */ ({ getDimensions: () => size })
          ),
          middleware: [
            { name: "stood", fn: () => ({}) },
            ...options.middleware.filter(
              (middleware) => middleware && middleware.name !== "size",
            ),
            held,
            anchorAt(measured),
          ],
        });
        if (placement !== epoch) return null;
        atStoodSize.set(answer, before);
      }
      return answer;
    },
    // Writes the answer's spot in its plane, and returns how far that moved the box, by
    // the answer's own measure (`clientBox`), and, where the box changed size since it
    // last stood, how far the edges that would have held it at that size move to where
    // they would have stood it (`position`), measured from the same box.
    /** @param {Position} answer @returns {Stood} */
    stand(answer) {
      const from = floating.getBoundingClientRect();
      stand(answer);
      const to = clientBox(answer);
      const before = atStoodSize.get(answer);
      const kept = before?.middlewareData.anchorAt.offset && clientBox(before);
      /** @type {Held | undefined} */
      const keptEdges = before?.middlewareData.held.edges;
      const moved = {
        x: to.left - from.left,
        y: to.top - from.top,
        kept:
          kept && keptEdges
            ? {
                edges: keptEdges,
                x: kept[keptEdges.x] - from[keptEdges.x],
                y: kept[keptEdges.y] - from[keptEdges.y],
              }
            : null,
      };
      const { edges, width, height } = answer.middlewareData.held;
      holding = { ...edges };
      stoodSize = { width, height };
      if (!placementProof) {
        stood.delete(floating);
        tenure = Object.freeze({});
        return moved;
      }
      const { offset, scale } = answer.middlewareData.anchorAt;
      const { subject, anchor, frame: frameAnchor, plane, at } = placementProof;
      /** @param {"x" | "y"} coordinate @param {"left" | "top"} start
       * @param {number} length */
      const axisPoint = (coordinate, start, length) => {
        const fromStart = edges[coordinate] === start;
        const spot = answer[coordinate];
        const point = frameAnchor
          ? fromStart
            ? atLayoutPrecision(spot - at[coordinate])
            : -atLayoutPrecision(at[coordinate] - spot - length)
          : atLayoutPrecision(fromStart ? spot : spot + length);
        return (point - (frameAnchor ? 0 : offset[coordinate])) * scale[coordinate];
      };
      const point = {
        left: axisPoint("x", "left", width),
        top: axisPoint("y", "top", height),
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
      return moved;
    },
    clientBox,
    // How far the box's client rectangle stands from where its last placement stands it
    // now, measured at the edges that hold it from its anchor's box read now. Chrome
    // reports an anchored box's rectangle from before a scroll for up to two frames
    // after it, while it paints where the scroll carried it, so a rectangle read in the
    // task that scrolled lags by the scroll; subtracting this places it where it paints.
    // Nothing for a box no anchor holds.
    lag() {
      const selection = stood.get(floating);
      if (!selection?.frame) return { x: 0, y: 0 };
      const frame = anchorBox(selection.frame);
      const box = floating.getBoundingClientRect();
      const { edges, point } = selection;
      return {
        x: box[edges.left] - (frame.left + point.left),
        y: box[edges.top] - (frame.top + point.top),
      };
    },
    // What holds the box where its last placement stood it, as dom/box-motion.js reads it:
    // the edges its spot is written from; null while no placement stands it.
    held: () => holding,
    // Whether the box has changed size since its last placement stood it, read in its
    // own layout pixels, which round to whole ones. Until the placement that follows
    // the change lands, its rectangle is where the layout that resized it left it,
    // which can reach past the room the placement keeps it in.
    resized: () =>
      stoodSize !== null &&
      (Math.abs(floating.offsetWidth - stoodSize.width) >= 1 ||
        Math.abs(floating.offsetHeight - stoodSize.height) >= 1),
    // Discards any placement in flight, leaving the box where it stands.
    supersede() {
      epoch += 1;
    },
    stop() {
      epoch += 1;
      // The last placement's writer holds the element it anchored to.
      stand = placedAt;
      lastAnchorStand = null;
      stopWatching?.();
      scrolls?.stop();
      scrolls = null;
      stopWatching = null;
      watched = null;
      observer = null;
      tenure = Object.freeze({});
      placementProof = null;
      holding = null;
      stoodSize = null;
      stood.delete(floating);
      delete floating.dataset.lfPlane;
      readFloatingEditor();
      for (const property of ["position-anchor", ...INSETS])
        floating.style.removeProperty(property);
    },
  };
}
