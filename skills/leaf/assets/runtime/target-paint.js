/* Transient Aim and target-trace paint in Leaf's chrome layer.
 *
 * Aim draws synchronously for the gesture that arms it. A trace retains its current
 * target and drawn geometry: scrolling moves cached paint, while layout and resize
 * rebuild its shape. Persistent annotations have their own optional painter. */

import { cancelRender, nextRender } from "./rendering.js";
import { el } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { inChrome } from "./passages.js";
import {
  SVG_NS,
  paintGeometry,
  paintShape,
  placement,
  standOver,
} from "./target-paint-geometry.js";

export const targetTraceBox = el("div", "lf-ui lf-target-trace lf-target-paint");
targetTraceBox.setAttribute("aria-hidden", "true");
export const aimBox = el("div", "lf-ui lf-aim lf-target-paint");
aimBox.setAttribute("aria-hidden", "true");

const aimShape = document.createElementNS(SVG_NS, "svg");
aimShape.classList.add("lf-aim-shape");
aimShape.setAttribute("aria-hidden", "true");
const aimMaskId = "lf-runtime-aim-shape-mask";
const targetTraceShape = document.createElementNS(SVG_NS, "svg");
targetTraceShape.classList.add("lf-target-trace-shape");
targetTraceShape.setAttribute("aria-hidden", "true");
let traceElement = null;
let traceSurface = null;
let traceGeometry = null;
let traceShapeKey = "";
let placementFrame = 0;
let geometryFrame = 0;
let geometryDirty = false;

export function clearAim() {
  aimBox.style.display = "none";
  aimBox.classList.toggle("lf-shaped", false);
  aimShape.replaceChildren();
  aimBox.removeAttribute("data-for");
  delete aimBox.dataset.lfPaintPlane;
}

export function paintAim(element, surface = null) {
  const geometry = surface ? paintGeometry(surface) : null;
  const placed = element && placement(surface ?? element, Boolean(geometry));
  if (!placed) {
    clearAim();
    return null;
  }
  const { rect } = placed;
  const shaped = paintShape(aimShape, geometry, rect, {
    maskId: aimMaskId,
    veil: true,
  });
  aimBox.classList.toggle("lf-shaped", shaped);
  if (!shaped) aimShape.replaceChildren();
  keeps(aimBox, "data-for", element.id);
  keeps(aimBox, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
  standOver(aimBox, rect, getComputedStyle(surface ?? element).borderRadius);
  return rect;
}

function clearTrace() {
  traceElement = null;
  traceSurface = null;
  traceGeometry = null;
  traceShapeKey = "";
  targetTraceBox.style.display = "none";
  targetTraceBox.classList.toggle("lf-shaped", false);
  targetTraceShape.replaceChildren();
  targetTraceBox.removeAttribute("data-for");
  delete targetTraceBox.dataset.lfPaintPlane;
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
  const placed = placement(surface, Boolean(geometry));
  traceElement = element;
  traceSurface = surface;
  traceGeometry = geometry;
  if (!placed) {
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
  keeps(targetTraceBox, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
  standOver(
    targetTraceBox,
    rect,
    shaped ? "0" : getComputedStyle(surface).borderRadius,
  );
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
