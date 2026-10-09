/* Transient Aim and target-trace paint in Leaf's chrome layer.
 *
 * Aim draws synchronously for the gesture that arms it. A trace retains its current
 * target and drawn geometry. Each box stands in a paint stand that the browser moves
 * with every scroll around its target (target-paint-geometry.js), so a scroll places
 * it again without writing, while layout and resize rebuild its shape. Persistent
 * annotations have their own optional painter. */

import { cancelRender, nextRender } from "./rendering.js";
import { el } from "./widget-elements.js";
import { keeps } from "./keeps.js";
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

const targetTraceBox = el("div", "lf-ui lf-target-trace");
const aimBox = el("div", "lf-ui lf-aim");
const traceStand = paintStand(targetTraceBox);
const aimStand = paintStand(aimBox);
// What leaf.js mounts in the chrome: each box in the stand that carries it.
export const targetTraceLayer = traceStand.root;
export const aimLayer = aimStand.root;

const aimShape = document.createElementNS(SVG_NS, "svg");
aimShape.classList.add("lf-aim-shape");
aimShape.setAttribute("aria-hidden", "true");
const aimMaskId = "lf-runtime-aim-shape-mask";
const targetTraceShape = document.createElementNS(SVG_NS, "svg");
targetTraceShape.classList.add("lf-target-trace-shape");
targetTraceShape.setAttribute("aria-hidden", "true");
// The aim's last placement and how its box stood, which a label at its corner is
// written from (`labelAim`).
let aimPlaced = null;
let aimStood = null;
let traceElement = null;
let traceSurface = null;
let traceGeometry = null;
let traceShapeKey = "";
let placementFrame = 0;
let geometryFrame = 0;
let geometryDirty = false;

export function clearAim() {
  aimPlaced = aimStood = null;
  vacate(aimStand);
  aimBox.style.display = "none";
  aimBox.classList.toggle("lf-shaped", false);
  aimShape.replaceChildren();
  aimBox.removeAttribute("data-for");
  delete aimStand.root.dataset.lfPaintPlane;
}

export function paintAim(element, surface = null) {
  const geometry = surface ? paintGeometry(surface) : null;
  const placed =
    element && placement(surface ?? element, Boolean(geometry), inChrome(element));
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
  aimStood = standOver(
    aimStand,
    placed,
    getComputedStyle(surface ?? element).borderRadius,
  );
  aimPlaced = placed;
  return placed.shown;
}

// Stands `node`, a label naming what the aim outlines, at the box's top-left corner:
// above it where the window and the frames cutting the box leave room, inside it
// otherwise, and inside the corner of what shows where a cut hides the box's own. It
// stands in the plane the scrolls carry that corner in: with the box, anchored as the
// box is, or where a cut hides the box's corner, in the frame of the box that cuts it,
// which the scroll that cuts the box does not carry. So a scroll carries it with what
// it names, and it moves only when a placement crosses a cut.
export function labelAim(node) {
  if (!aimPlaced) return;
  const { rect, shown, levels } = aimPlaced;
  const above = shown.top - node.offsetHeight - 2;
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
  const index = cutTop
    ? levels.findLastIndex(({ axes, band }) => axes.y && band.top === shown.top)
    : shown.left > rect.left
      ? levels.findLastIndex(({ axes, band }) => axes.x && band.left === shown.left)
      : -1;
  if (index >= 0) {
    const home = aimStand.levels[index].frame;
    if (node.parentElement !== home) home.append(node);
    const { band } = levels[index];
    standBox(node, at, { anchored: false, origin: { x: band.left, y: band.top } });
    return;
  }
  if (node.parentElement !== aimStand.carrier) aimStand.carrier.append(node);
  standBox(node, at, aimStood, aimStood.anchor, aimStood.at);
}

function clearTrace() {
  traceElement = null;
  traceSurface = null;
  traceGeometry = null;
  traceShapeKey = "";
  vacate(traceStand);
  targetTraceBox.style.display = "none";
  targetTraceBox.classList.toggle("lf-shaped", false);
  targetTraceShape.replaceChildren();
  targetTraceBox.removeAttribute("data-for");
  delete traceStand.root.dataset.lfPaintPlane;
}

function drawTrace(
  element = traceElement,
  surface = traceSurface,
  rebuildGeometry = true,
) {
  if (
    !(element instanceof Element) ||
    !(surface instanceof Element) ||
    !element.isConnected ||
    !surface.isConnected
  ) {
    clearTrace();
    return;
  }
  const changed = element !== traceElement || surface !== traceSurface;
  const geometry = changed || rebuildGeometry ? paintGeometry(surface) : traceGeometry;
  const placed = placement(surface, Boolean(geometry), inChrome(element));
  traceElement = element;
  traceSurface = surface;
  traceGeometry = geometry;
  if (!placed.shown) {
    targetTraceBox.style.display = "none";
    return;
  }
  const { rect, shapeKey } = placed;
  let shaped = Boolean(geometry);
  if (shaped && (changed || rebuildGeometry || shapeKey !== traceShapeKey))
    shaped = paintShape(targetTraceShape, geometry, rect);
  if (!shaped) targetTraceShape.replaceChildren();
  traceShapeKey = shaped ? shapeKey : "";
  targetTraceBox.classList.toggle("lf-shaped", shaped);
  keeps(targetTraceBox, "data-for", element.id || null);
  keeps(traceStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
  standOver(traceStand, placed, shaped ? "0" : getComputedStyle(surface).borderRadius);
}

export function paintTrace(element, surface = element) {
  if (!element) {
    clearTrace();
    return;
  }
  const rebuild = geometryDirty || element !== traceElement || surface !== traceSurface;
  if (geometryDirty) {
    if (geometryFrame) cancelRender(geometryFrame);
    if (placementFrame) cancelRender(placementFrame);
    geometryFrame = placementFrame = 0;
    geometryDirty = false;
  }
  drawTrace(element, surface, rebuild);
}

export function shifted() {
  if (placementFrame || geometryFrame || !traceElement) return;
  placementFrame = nextRender(() => {
    placementFrame = 0;
    if (traceElement) drawTrace(traceElement, traceSurface, false);
  });
}

export function geometryChanged() {
  geometryDirty = true;
  if (placementFrame) cancelRender(placementFrame);
  placementFrame = 0;
  if (geometryFrame || !traceElement) return;
  geometryFrame = nextRender(() => {
    geometryFrame = 0;
    if (!geometryDirty) return;
    geometryDirty = false;
    if (traceElement) drawTrace(traceElement, traceSurface, true);
  });
}

// The transient shapes are mounted into their boxes from leaf.js.
export function mountTargetPaint() {
  aimBox.append(aimShape);
  targetTraceBox.append(targetTraceShape);
}
