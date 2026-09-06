/* Element-target paint in Leaf's chrome layer.
 *
 * Ordinary anchors keep their CSS outlines. A declared visual widget, or a registered
 * visual part, contributes its shown box or, for SVG, painted geometry that Leaf clones
 * into chrome, so aim, margin correspondence, and persistent states cover the same
 * package drawing. The painter owns geometry caching: scroll only moves cached paint; a
 * layout, resize, source replacement, or target change rebuilds it. */

import { clippedRect, documentPoint, shownBox } from "./geometry.js";
import { el } from "./widget-elements.js";
import { aimBox } from "./composing/aim.js";
import { inChrome } from "./passages.js";

// Persistent paint for semantic visual parts. target-paint.js owns these pointer-inert
// projections and keeps every anchored state above the package drawing.
export const visualMarkLayer = el("div", "lf-ui lf-visual-marks");
visualMarkLayer.setAttribute("aria-hidden", "true");
export const targetTraceBox = el("div", "lf-ui lf-target-trace lf-target-paint");
targetTraceBox.setAttribute("aria-hidden", "true");

const SVG_NS = "http://www.w3.org/2000/svg";
const SHAPE_STROKE_ROOM = 2;
const SHAPED = "lf-shaped-mark";
const STATE_CLASSES = {
  comment: "lf-visual-mark-comment",
  reaction: "lf-visual-mark-reaction",
  pending: "lf-visual-mark-pending",
  action: "lf-visual-mark-action",
  hover: "lf-visual-mark-hover",
  focus: "lf-visual-mark-focus",
  here: "lf-visual-mark-here",
};

const paints = (shape, property) => {
  const style = getComputedStyle(shape);
  return (
    shape.checkVisibility({ opacityProperty: true, visibilityProperty: true }) &&
    style[property] !== "none" &&
    Number.parseFloat(style[`${property}Opacity`]) !== 0 &&
    (property !== "stroke" || Number.parseFloat(style.strokeWidth) > 0)
  );
};

function paintGeometry(surface) {
  if (!(surface instanceof SVGElement)) return null;
  const geometry = [surface, ...surface.querySelectorAll("*")].filter(
    (child) => child instanceof SVGGeometryElement,
  );
  const fill = geometry.filter((shape) => paints(shape, "fill"));
  const paintedStroke = geometry.filter((shape) => paints(shape, "stroke"));
  // Every painted primitive contributes to the contour. A fill-only boundary must not
  // disappear merely because a sibling decoration happens to have its own stroke.
  const outlined = new Set([...fill, ...paintedStroke]);
  const stroke = geometry.filter((shape) => outlined.has(shape));
  return fill.length || stroke.length ? { fill, stroke } : null;
}

function geometryClone(source, left, top, property) {
  const matrix = source.getScreenCTM();
  if (!matrix) return null;
  const clone = source.cloneNode(false);
  clone.removeAttribute("id");
  clone.removeAttribute("class");
  clone.removeAttribute("opacity");
  clone.removeAttribute("fill-opacity");
  clone.removeAttribute("stroke-opacity");
  clone.style.removeProperty("transform");
  clone.style.removeProperty("opacity");
  clone.style.removeProperty("fill-opacity");
  clone.style.removeProperty("stroke-opacity");
  // Percentage geometry is resolved in the source SVG's viewport. Freeze each animated
  // length before moving the primitive into the overlay's different viewport.
  for (const attribute of [...clone.attributes]) {
    const length = source[attribute.localName];
    if (
      attribute.value.includes("%") &&
      typeof SVGAnimatedLength !== "undefined" &&
      length instanceof SVGAnimatedLength
    )
      clone.setAttribute(attribute.name, String(length.animVal.value));
  }
  clone.setAttribute(
    "transform",
    `matrix(${matrix.a} ${matrix.b} ${matrix.c} ${matrix.d} ${matrix.e - left} ${matrix.f - top})`,
  );
  clone.style.setProperty("fill", property === "fill" ? "white" : "none", "important");
  clone.style.setProperty(
    "stroke",
    property === "stroke" ? "var(--lf-shape-ink)" : "none",
    "important",
  );
  clone.style.setProperty("stroke-width", "var(--lf-shape-stroke)", "important");
  clone.style.setProperty(
    "stroke-dasharray",
    "var(--lf-shape-dash, none)",
    "important",
  );
  clone.style.setProperty("stroke-linejoin", "round", "important");
  clone.style.setProperty("stroke-linecap", "round", "important");
  clone.style.setProperty("vector-effect", "non-scaling-stroke", "important");
  return clone;
}

function paintShape(host, geometry, { left, top, right, bottom }, options = {}) {
  if (!geometry) return false;
  const { maskId = "", veil = false } = options;
  const width = right - left;
  const height = bottom - top;
  const fill = veil
    ? geometry.fill.map((shape) => geometryClone(shape, left, top, "fill"))
    : [];
  const stroke = geometry.stroke.map((shape) =>
    geometryClone(shape, left, top, "stroke"),
  );
  if ([...fill, ...stroke].some((shape) => !shape)) return false;

  const paint = [];
  if (veil && fill.length) {
    const defs = document.createElementNS(SVG_NS, "defs");
    const mask = document.createElementNS(SVG_NS, "mask");
    mask.id = maskId;
    mask.setAttribute("maskUnits", "userSpaceOnUse");
    mask.setAttribute("x", "0");
    mask.setAttribute("y", "0");
    mask.setAttribute("width", String(width));
    mask.setAttribute("height", String(height));
    mask.style.maskType = "alpha";
    mask.append(...fill);
    defs.append(mask);
    const wash = document.createElementNS(SVG_NS, "rect");
    wash.setAttribute("width", String(width));
    wash.setAttribute("height", String(height));
    wash.setAttribute("fill", "var(--lf-shape-ink)");
    wash.setAttribute("fill-opacity", "0.08");
    wash.setAttribute("mask", `url(#${maskId})`);
    paint.push(defs, wash);
  }
  const outline = document.createElementNS(SVG_NS, "g");
  outline.append(...stroke);
  paint.push(outline);
  host.setAttribute("viewBox", `0 0 ${width} ${height}`);
  host.setAttribute("width", String(width));
  host.setAttribute("height", String(height));
  host.replaceChildren(...paint);
  return true;
}

function placement(surface, shaped) {
  const box = shownBox(surface);
  const pad = shaped ? SHAPE_STROKE_ROOM : 0;
  const rect = clippedRect(
    {
      left: box.left - pad,
      top: box.top - pad,
      right: box.right + pad,
      bottom: box.bottom + pad,
    },
    surface,
    new Map(),
  );
  if (!rect) return null;
  const shapeKey = [
    rect.right - rect.left,
    rect.bottom - rect.top,
    box.left - rect.left,
    box.top - rect.top,
    box.right - rect.right,
    box.bottom - rect.bottom,
  ].join(":");
  return { rect, shapeKey };
}

const aimShape = document.createElementNS(SVG_NS, "svg");
aimShape.classList.add("lf-aim-shape");
aimShape.setAttribute("aria-hidden", "true");
const aimMaskId = "lf-runtime-aim-shape-mask";
const targetTraceShape = document.createElementNS(SVG_NS, "svg");
targetTraceShape.classList.add("lf-target-trace-shape");
targetTraceShape.setAttribute("aria-hidden", "true");
let targets = new Map();
const overlays = new Map();
let traceElement = null;
let traceSurface = null;
let traceGeometry = null;
let traceShapeKey = "";
let placementFrame = 0;
let geometryFrame = 0;
let geometryDirty = false;

export function clearAim() {
  aimBox.style.display = "none";
  aimBox.classList.remove("lf-shaped");
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
  aimBox.setAttribute("data-for", element.id);
  aimBox.dataset.lfPaintPlane = inChrome(element) ? "chrome" : "page";
  const at = documentPoint(rect.left, rect.top);
  Object.assign(aimBox.style, {
    display: "block",
    left: `${at.left}px`,
    top: `${at.top}px`,
    width: `${rect.right - rect.left}px`,
    height: `${rect.bottom - rect.top}px`,
    borderRadius: getComputedStyle(surface ?? element).borderRadius,
  });
  return rect;
}

function clearTrace() {
  traceElement = null;
  traceSurface = null;
  traceGeometry = null;
  traceShapeKey = "";
  targetTraceBox.style.display = "none";
  targetTraceBox.classList.remove("lf-shaped");
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
  if (element.id) targetTraceBox.setAttribute("data-for", element.id);
  else targetTraceBox.removeAttribute("data-for");
  targetTraceBox.dataset.lfPaintPlane = inChrome(element) ? "chrome" : "page";
  const at = documentPoint(rect.left, rect.top);
  Object.assign(targetTraceBox.style, {
    display: "block",
    left: `${at.left}px`,
    top: `${at.top}px`,
    width: `${rect.right - rect.left}px`,
    height: `${rect.bottom - rect.top}px`,
    borderRadius: shaped ? "0" : getComputedStyle(surface).borderRadius,
  });
}

export function paintTrace(element, surface = element) {
  if (!element) {
    clearTrace();
    return;
  }
  drawTrace(element, surface, element !== traceElement || surface !== traceSurface);
}

function syncStates() {
  for (const [element, { overlay }] of overlays) {
    const states = targets.get(element)?.states ?? new Set();
    for (const [state, className] of Object.entries(STATE_CLASSES))
      overlay.classList.toggle(className, states.has(state));
  }
}

function paintTargets(rebuildGeometry = true) {
  for (const element of [...overlays.keys()])
    if (!targets.has(element)) {
      element.classList.remove(SHAPED);
      overlays.get(element).overlay.remove();
      overlays.delete(element);
    }

  for (const [element, target] of targets) {
    let record = overlays.get(element);
    const geometry =
      rebuildGeometry || !record ? paintGeometry(target.surface) : record.geometry;
    const placed = placement(target.surface, Boolean(geometry));
    if (!placed) {
      element.classList.remove(SHAPED);
      if (record) {
        record.geometry = geometry;
        record.shapeKey = "";
        record.overlay.style.display = "none";
      }
      continue;
    }
    if (!record) {
      const overlay = el("div", "lf-ui lf-visual-mark lf-target-paint");
      const shape = document.createElementNS(SVG_NS, "svg");
      shape.classList.add("lf-visual-mark-shape");
      overlay.append(shape);
      visualMarkLayer.append(overlay);
      record = { overlay, shape, geometry: null, shapeKey: "" };
      overlays.set(element, record);
    }
    const { overlay, shape } = record;
    const { rect, shapeKey } = placed;
    element.classList.add(SHAPED);
    overlay.classList.toggle("lf-shaped", Boolean(geometry));
    if (
      rebuildGeometry ||
      record.geometry !== geometry ||
      record.shapeKey !== shapeKey
    ) {
      if (geometry) paintShape(shape, geometry, rect);
      else shape.replaceChildren();
      record.geometry = geometry;
      record.shapeKey = shapeKey;
    }
    overlay.dataset.lfPaintPlane = inChrome(element) ? "chrome" : "page";
    const at = documentPoint(rect.left, rect.top);
    Object.assign(overlay.style, {
      display: "block",
      left: `${at.left}px`,
      top: `${at.top}px`,
      width: `${rect.right - rect.left}px`,
      height: `${rect.bottom - rect.top}px`,
      borderRadius: geometry ? "0" : getComputedStyle(target.surface).borderRadius,
    });
  }
  syncStates();
}

export function setTargets(next) {
  const nextTargets = new Map(
    [...next]
      .filter((target) => target.states?.size)
      .map((target) => [target.element, target]),
  );
  const identitiesChanged =
    nextTargets.size !== targets.size ||
    [...nextTargets].some(
      ([element, target]) => targets.get(element)?.surface !== target.surface,
    );
  targets = nextTargets;
  const traceNeedsGeometry = geometryDirty;
  const rebuild = identitiesChanged || traceNeedsGeometry;
  if (rebuild && geometryFrame) cancelAnimationFrame(geometryFrame);
  if (rebuild && placementFrame) cancelAnimationFrame(placementFrame);
  if (rebuild) geometryFrame = placementFrame = 0;
  geometryDirty = false;
  paintTargets(rebuild);
  if (traceElement) drawTrace(traceElement, traceSurface, traceNeedsGeometry);
}

export function shifted() {
  if (placementFrame || geometryFrame || (!targets.size && !traceElement)) return;
  placementFrame = requestAnimationFrame(() => {
    placementFrame = 0;
    paintTargets(false);
    if (traceElement) drawTrace(traceElement, traceSurface, false);
  });
}

export function geometryChanged() {
  geometryDirty = true;
  if (placementFrame) cancelAnimationFrame(placementFrame);
  placementFrame = 0;
  if (geometryFrame || (!targets.size && !traceElement)) return;
  geometryFrame = requestAnimationFrame(() => {
    geometryFrame = 0;
    if (!geometryDirty) return;
    geometryDirty = false;
    paintTargets(true);
    if (traceElement) drawTrace(traceElement, traceSurface, true);
  });
}

// The shapes into the aim's and the margin's boxes; mounted from chrome.js.
export function mountTargetPaint() {
  aimBox.append(aimShape);
  targetTraceBox.append(targetTraceShape);
}
