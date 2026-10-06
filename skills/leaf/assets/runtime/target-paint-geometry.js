/* Shared geometry for transient target traces and persistent visual marks.
 *
 * Read the provider's drawn SVG primitives and clone them into a caller-owned shape.
 * These operations hold no targets, nodes, caches or scheduled work; each painter
 * decides when geometry must be rebuilt and when only its placement has changed. */

import { paintClips, shownBox } from "./geometry.js";
import { atLayoutPrecision, keeps, layoutPx } from "./keeps.js";
import {
  followScroll,
  scrollFollows,
  scrollMotions,
  scrolledBy,
} from "./scroll-motion.js";

export const SVG_NS = "http://www.w3.org/2000/svg";
const SHAPE_STROKE_ROOM = 2;

const paints = (shape, property) => {
  const style = getComputedStyle(shape);
  return (
    shape.checkVisibility({ opacityProperty: true, visibilityProperty: true }) &&
    style[property] !== "none" &&
    Number.parseFloat(style[`${property}Opacity`]) !== 0 &&
    (property !== "stroke" || Number.parseFloat(style.strokeWidth) > 0)
  );
};

export function paintGeometry(surface) {
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
    `matrix(${matrix.a} ${matrix.b} ${matrix.c} ${matrix.d} ${atLayoutPrecision(matrix.e - left)} ${atLayoutPrecision(matrix.f - top)})`,
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

export function paintShape(host, geometry, { left, top, right, bottom }, options = {}) {
  if (!geometry) return false;
  const { maskId = "", veil = false } = options;
  const width = atLayoutPrecision(right - left);
  const height = atLayoutPrecision(bottom - top);
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
  keeps(host, "viewBox", `0 0 ${width} ${height}`);
  keeps(host, "width", width);
  keeps(host, "height", height);
  // A repaint of geometry that has not moved clones the shapes it already holds.
  const held = host.children;
  if (
    paint.length !== held.length ||
    paint.some((node, index) => !node.isEqualNode(held[index]))
  )
    host.replaceChildren(...paint);
  return true;
}

// A stand holds one paint box over its target in the planes of what carries the target.
// Each box that clips the target (`paintClips`) gets a frame cut to its band, standing in
// the plane of the box that holds it, with one motion layer per axis it scrolls along
// (scroll-motion.js); the paint box stands in the innermost. A scroll anywhere around
// the target then moves the box and every cut over it in the frame that scrolls, and
// placing it again after the scroll writes nothing, since every length is written where
// it stands at its scrollers' start. The window's cuts, a header stuck over the page's
// top and, for paint stacked above them, the auxiliary surfaces, stand in the window's
// plane, as a fixed frame round the page's motion; with neither, the stand is absolute in the document, which the root
// scroll carries. Without ScrollTimeline the frames stand where the scrollers stand now,
// and the scroll that moves them places them again. The stand, not the box, carries the
// paint's stacking (`data-lf-paint-plane`), since the frames and layers it holds stack
// what they hold.
export function paintStand(box) {
  const root = document.createElement("div");
  root.className = "lf-ui lf-target-paint lf-paint-stand";
  root.setAttribute("aria-hidden", "true");
  root.append(box);
  return { root, box, levels: [] };
}

// Whether two placements move a stand's layers along the same axes of the same scrollers.
const sameGraph = (levels, stood) =>
  levels.length === stood.length &&
  levels.every(
    ({ motions }, i) =>
      motions.length === stood[i].motions.length &&
      motions.every(
        ({ source, axis }, j) =>
          source === stood[i].motions[j].source && axis === stood[i].motions[j].axis,
      ),
  );
const sameMotion = (a, b) =>
  a.subject === b.subject &&
  a.from === b.from &&
  a.to === b.to &&
  a.vector.x === b.vector.x &&
  a.vector.y === b.vector.y;

function rebuild(stand, levels) {
  for (const level of stand.levels)
    for (const animation of level.animations) animation.cancel();
  stand.root.replaceChildren();
  let parent = stand.root;
  stand.levels = levels.map(({ motions }) => {
    const frame = document.createElement("div");
    frame.className = "lf-paint-frame";
    parent.append(frame);
    parent = frame;
    const layers = motions.map((motion) => {
      const layer = document.createElement("div");
      layer.className = "lf-paint-motion";
      parent.append(layer);
      parent = layer;
      return layer;
    });
    return {
      frame,
      layers,
      motions,
      animations: motions.map((motion, i) => followScroll(layers[i], motion, 0)),
    };
  });
  parent.append(stand.box);
}

const placeBox = (node, { left, top, right, bottom }, from) =>
  Object.assign(node.style, {
    left: layoutPx(left - from.x),
    top: layoutPx(top - from.y),
    width: layoutPx(right - left),
    height: layoutPx(bottom - top),
  });

export function standOver(stand, placed, borderRadius) {
  const { levels, fixed } = placed;
  if (!sameGraph(levels, stand.levels)) rebuild(stand, levels);
  // A subject that moved in its scroller, or grew, crosses the view over other scrolls.
  levels.forEach(({ motions }, i) => {
    const stood = stand.levels[i];
    motions.forEach((motion, j) => {
      if (sameMotion(motion, stood.motions[j])) return;
      stood.animations[j].cancel();
      stood.animations[j] = followScroll(stood.layers[j], motion, 0);
      stood.motions[j] = motion;
    });
  });
  stand.root.style.position = fixed ? "fixed" : "absolute";
  // Where each level's contents stand from, in client coordinates: the document's origin
  // for an absolute stand, the window's for a fixed one, then each frame's corner,
  // carried back to where its scrollers start.
  let from = fixed ? { x: 0, y: 0 } : { x: -scrollX, y: -scrollY };
  levels.forEach(({ band, axes, motions }, i) => {
    const { frame } = stand.levels[i];
    placeBox(frame, band, from);
    Object.assign(frame.style, {
      overflowX: axes.x ? "clip" : "visible",
      overflowY: axes.y ? "clip" : "visible",
    });
    const by = scrolledBy(motions);
    from = { x: band.left + by.x, y: band.top + by.y };
  });
  placeBox(stand.box, placed.rect, from);
  Object.assign(stand.box.style, { display: "block", borderRadius });
}

// A stand whose box is put away keeps no frames, layers or timelines, which would hold
// the scrollers they follow after a revision removed them.
export function vacate(stand) {
  if (stand.levels.length || stand.box.parentElement !== stand.root) rebuild(stand, []);
}

export function dropStand(stand) {
  vacate(stand);
  stand.root.remove();
}

// Where a paint box stands over `surface`, and what cuts it, or null where the cuts hide
// all of it, for paint stacked `aboveSurfaces` (`data-lf-paint-plane`) or under them: `rect` is the box, the surface's own with room for a shape's stroke, and
// `shown` the part of it no cut hides. `shapeKey` changes where a shape drawn in the box
// must be drawn again.
export function placement(surface, shaped, aboveSurfaces) {
  const box = shownBox(surface);
  const pad = shaped ? SHAPE_STROKE_ROOM : 0;
  const rect = {
    left: box.left - pad,
    top: box.top - pad,
    right: box.right + pad,
    bottom: box.bottom + pad,
  };
  const clips = paintClips(surface, rect, new Map(), aboveSurfaces);
  const follows = scrollFollows(surface);
  // Each level's motion follows the box it holds next: the next frame's, or the surface,
  // whose paint reaches past it by the room a shape's stroke takes.
  const held = [...clips.bands.map(({ box: holder }) => holder), surface];
  const reach = (i) => (i === clips.bands.length ? pad : 0);
  const levels = [];
  if (clips.window)
    levels.push({
      band: clips.window,
      axes: { x: true, y: true },
      motions:
        clips.plane === "page" && follows
          ? scrollMotions(surface.ownerDocument.scrollingElement, held[0], reach(0))
          : [],
    });
  clips.bands.forEach(({ box: holder, band, axes }, i) =>
    levels.push({
      band,
      axes,
      motions: follows ? scrollMotions(holder, held[i + 1], reach(i + 1)) : [],
    }),
  );
  let shown = rect;
  for (const { band, axes } of levels)
    shown = {
      left: axes.x ? Math.max(shown.left, band.left) : shown.left,
      top: axes.y ? Math.max(shown.top, band.top) : shown.top,
      right: axes.x ? Math.min(shown.right, band.right) : shown.right,
      bottom: axes.y ? Math.min(shown.bottom, band.bottom) : shown.bottom,
    };
  if (!(shown.right > shown.left && shown.bottom > shown.top)) return null;
  return {
    rect,
    shown,
    shapeKey: `${rect.right - rect.left}:${rect.bottom - rect.top}`,
    levels,
    fixed: clips.plane === "window" || Boolean(clips.window),
  };
}
