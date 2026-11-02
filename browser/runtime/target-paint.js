/* Transient Aim and trace paint in Leaf's chrome layer, which every page mounts.
 *
 * Aim draws synchronously for the gesture that arms it. A trace retains its current
 * target and drawn geometry: the target trace, the quiet contour a margin control
 * draws round the content it concerns, and the stop ring, the focus ring a focused
 * stop draws round what it stands for (control-faces.js, `stop`), where neither the
 * stop nor that thing can wear it. Each box stands in a paint stand that the browser
 * moves with every scroll around its target (target-paint-geometry.js), so a scroll
 * places it again without writing, while layout and resize rebuild its shape.
 * Persistent annotations have their own optional painter. */

import { cancelRender, nextRender } from "./rendering.js";
import { el } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { move } from "./dom-move.js";
import { inChrome } from "./passages.js";
import {
  SVG_NS,
  paintGeometry,
  paintShape,
  paintStand,
  placement,
  standBox,
  standOver,
  vacate,
} from "./target-paint-geometry.js";

const aimBox = el("div", "lf-ui lf-aim");
const aimStand = paintStand(aimBox);
// What leaf.js mounts in the chrome: each box in the stand that carries it.
export const aimLayer = aimStand.root;

const aimShape = document.createElementNS(SVG_NS, "svg");
aimShape.classList.add("lf-aim-shape");
aimShape.setAttribute("aria-hidden", "true");
const aimMaskId = "lf-runtime-aim-shape-mask";
// The aim's last placement and how its box stood, which a label at its corner is
// written from (`labelAim`).
/** @type {{placed: import("./target-paint-geometry.js").Placement & {shown: import("./rect.js").Box}, stood: ReturnType<typeof standOver>} | null} */
let aimed = null;
export function clearAim() {
  aimed = null;
  vacate(aimStand);
  aimBox.style.display = "none";
  aimBox.classList.toggle("lf-shaped", false);
  aimShape.replaceChildren();
  aimBox.removeAttribute("data-for");
  delete aimStand.root.dataset.lfPaintPlane;
}

// The aim stands over `surface`, the element itself where nothing draws it for it, as a
// comment's mark does (anchor-paint.js), so an SVG element's aim and its comment both
// take its contour.
/** @param {Element | null} element @param {Element | null} [surface] */
export function paintAim(element, surface) {
  if (!element) {
    clearAim();
    return null;
  }
  surface ??= element;
  const geometry = surface && paintGeometry(surface);
  const placed = element && placement(surface, Boolean(geometry), inChrome(element));
  if (!placed?.shown) {
    clearAim();
    return null;
  }
  const shaped = paintShape(aimShape, geometry, placed.rect, {
    maskId: aimMaskId,
    veil: true,
  });
  aimBox.classList.toggle("lf-shaped", shaped);
  if (!shaped) aimShape.replaceChildren();
  keeps(aimBox, "data-for", element.id);
  keeps(aimStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
  const stood = standOver(
    aimStand,
    placed,
    shaped ? "0" : getComputedStyle(surface).borderRadius,
  );
  aimed = { placed: { ...placed, shown: placed.shown }, stood };
  return placed.shown;
}

// Stands `node`, a label naming what the aim outlines, at the box's top-left corner:
// above it where the window and the frames cutting the box leave room, inside it
// otherwise, and inside the corner of what shows where a cut hides the box's own. It
// stands in the plane the scrolls carry that corner in: with the box, anchored as the
// box is, or where a cut hides the box's corner, in the frame of the box that cuts it,
// which the scroll that cuts the box does not carry. So a scroll carries it with what
// it names, and it moves only when a placement crosses a cut.
/** @param {HTMLElement} node */
export function labelAim(node) {
  if (!aimed) return;
  const {
    placed: { rect, shown, levels },
    stood,
  } = aimed;
  const above = shown.top - node.offsetHeight - stood.room;
  // The frames cut the label too, so the room above is what every band leaves.
  const room = Math.max(
    0,
    ...levels.filter(({ axes }) => axes.y).map(({ band }) => band.top),
  );
  const cutTop = shown.top > rect.top;
  const at = {
    left: Math.max(2, shown.left),
    top: !cutTop && above >= room ? above : shown.top + 2,
  };
  // The level whose band is the edge that cut the corner, the top's before the left's.
  const cut = cutTop
    ? aimStand.frames.findLast(
        ({ level: { axes, band } }) => axes.y && band.top === shown.top,
      )
    : shown.left > rect.left
      ? aimStand.frames.findLast(
          ({ level: { axes, band } }) => axes.x && band.left === shown.left,
        )
      : undefined;
  if (cut) {
    const {
      frame,
      level: { band },
    } = cut;
    if (node.parentElement !== frame) move(frame, node, null);
    standBox(node, at, { anchored: false, origin: { x: band.left, y: band.top } });
    return;
  }
  if (node.parentElement !== aimStand.carrier) move(aimStand.carrier, node, null);
  standBox(node, at, stood, stood.anchor, stood.at);
}

// One trace: a box drawn round one target at a time, in the target's contour where it
// is a drawn shape, standing in the planes of what carries it.
/** @param {string} className */
function createTrace(className) {
  const box = el("div", `lf-ui ${className}`);
  const stand = paintStand(box);
  const shape = document.createElementNS(SVG_NS, "svg");
  shape.classList.add(`${className}-shape`);
  shape.setAttribute("aria-hidden", "true");
  /** @type {Element | null} */
  let traced = null;
  /** @type {Element | null} */
  let tracedSurface = null;
  /** @type {ReturnType<typeof paintGeometry>} */
  let tracedGeometry = null;
  let shapeKeyDrawn = "";
  let placementFrame = 0;
  let geometryFrame = 0;
  let geometryDirty = false;

  function clear() {
    traced = null;
    tracedSurface = null;
    tracedGeometry = null;
    shapeKeyDrawn = "";
    vacate(stand);
    box.style.display = "none";
    box.classList.toggle("lf-shaped", false);
    shape.replaceChildren();
    box.removeAttribute("data-for");
    delete stand.root.dataset.lfPaintPlane;
  }

  function draw(element = traced, surface = tracedSurface, rebuildGeometry = true) {
    if (
      !(element instanceof Element) ||
      !(surface instanceof Element) ||
      !element.isConnected ||
      !surface.isConnected
    ) {
      clear();
      return;
    }
    const changed = element !== traced || surface !== tracedSurface;
    const geometry =
      changed || rebuildGeometry ? paintGeometry(surface) : tracedGeometry;
    const placed = placement(surface, Boolean(geometry), inChrome(element));
    traced = element;
    tracedSurface = surface;
    tracedGeometry = geometry;
    if (!placed.shown) {
      box.style.display = "none";
      return;
    }
    const { rect, shapeKey } = placed;
    let shaped = Boolean(geometry);
    if (shaped && (changed || rebuildGeometry || shapeKey !== shapeKeyDrawn))
      shaped = paintShape(shape, geometry, rect);
    if (!shaped) shape.replaceChildren();
    shapeKeyDrawn = shaped ? shapeKey : "";
    box.classList.toggle("lf-shaped", shaped);
    keeps(box, "data-for", element.id || null);
    keeps(stand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
    standOver(stand, placed, shaped ? "0" : getComputedStyle(surface).borderRadius);
  }

  return {
    layer: stand.root,
    /** @param {Element | null} element @param {Element | null} [surface] */
    paint(element, surface = element) {
      if (!element) {
        clear();
        return;
      }
      const rebuild = geometryDirty || element !== traced || surface !== tracedSurface;
      if (geometryDirty) {
        if (geometryFrame) cancelRender(geometryFrame);
        if (placementFrame) cancelRender(placementFrame);
        geometryFrame = placementFrame = 0;
        geometryDirty = false;
      }
      draw(element, surface, rebuild);
    },
    shifted() {
      if (placementFrame || geometryFrame || !traced) return;
      placementFrame = nextRender(() => {
        placementFrame = 0;
        if (traced) draw(traced, tracedSurface, false);
      });
    },
    geometryChanged() {
      geometryDirty = true;
      if (placementFrame) cancelRender(placementFrame);
      placementFrame = 0;
      if (geometryFrame || !traced) return;
      geometryFrame = nextRender(() => {
        geometryFrame = 0;
        if (!geometryDirty) return;
        geometryDirty = false;
        if (traced) draw(traced, tracedSurface, true);
      });
    },
    mount() {
      box.append(shape);
    },
  };
}

const targetTrace = createTrace("lf-target-trace");
const stopRing = createTrace("lf-stop-ring");
// What leaf.js mounts in the chrome: each box in the stand that carries it.
export const targetTraceLayer = targetTrace.layer;
export const stopRingLayer = stopRing.layer;
export const paintTrace = targetTrace.paint;
export const paintStopRing = stopRing.paint;

export function shifted() {
  targetTrace.shifted();
  stopRing.shifted();
}

export function geometryChanged() {
  targetTrace.geometryChanged();
  stopRing.geometryChanged();
}

// The transient shapes are mounted into their boxes from leaf.js.
export function mountTargetPaint() {
  aimBox.append(aimShape);
  targetTrace.mount();
  stopRing.mount();
}
