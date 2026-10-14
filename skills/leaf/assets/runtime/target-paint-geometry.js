/* Where paint over the page's targets stands: traces, visual marks, the design
 * legend, key chips, the search's mark and drawing ink.
 *
 * Read the provider's drawn SVG primitives and clone them into a caller-owned shape,
 * and stand each box in the planes of what carries its target (`paintStand`), alone or
 * in a set (`paintSet`). Each painter decides when geometry must be rebuilt and when
 * only its placement has changed; a set alone keeps state, which of its targets stand
 * near enough to be shown. */

import {
  anchorAt,
  anchorElement,
  anchorReaches,
  anchorReading,
  cutFrames,
  nameAnchor,
  scrollsWith,
} from "./css-anchors.js";
import {
  nearObserver,
  nearWindow,
  paintClips,
  scrollsContent,
  shownBox,
} from "./geometry.js";
import { hasArea, intersect } from "./rect.js";
import { move } from "./dom-move.js";
import { atLayoutPrecision, keeps, layoutPx } from "./keeps.js";

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

// A stand holds paint boxes over their targets in the planes of what carries the
// targets, through the anchored cut frames every box that follows scrolled content
// stands in (css-anchors.js). Each box that clips a target (`paintClips`) gets a frame
// cut to its band, inside the frame of the box holding it; the boxes stand in a carrier
// in the innermost. The window's cuts, a header stuck over the page's top and, for paint
// stacked above them, the auxiliary surfaces, stand in the window's plane, as a frame
// fixed where the window holds it. Each other frame is anchored to the scroller whose
// band it cuts, and each box to its own target, so it follows that target through
// layout, a transform or a sticky offset as well: a scroll anywhere around a target
// moves its box and every cut over it in the frame that scrolls, and placing it again
// after the scroll writes nothing. Boxes the same frames cut share a stand (`standIn`,
// then `standBox` for each).
//
// Where an anchor cannot position the stand (`anchoredBy`), as for a target in a native
// layer the stand is not in or a box in the chrome after the stand, every frame and box
// stands where the window holds it as measured, and the pass a scroll brings places them
// again. The stand, not the box, carries the paint's stacking (`data-lf-paint-plane`),
// since the frames it holds stack what they hold.
export function paintStand(box = null) {
  const root = document.createElement("div");
  root.className = "lf-ui lf-target-paint lf-paint-stand";
  root.setAttribute("aria-hidden", "true");
  root.style.position = "fixed";
  const carrier = document.createElement("div");
  carrier.className = "lf-paint-carrier";
  if (box) carrier.append(box);
  root.append(carrier);
  return { root, carrier, box, anchored: false, frames: [] };
}

// The box an anchor carries `el` by for a stand at `root`: its anchor box
// (css-anchors.js), where every scroll that moves `el` moves that box with it
// (`scrollsWith`), or that box's own parts where `el` draws none. Null where the anchor
// cannot position a box at `root` (`anchorReaches`).
function anchoredBy(el, root) {
  const anchor = anchorElement(el);
  if (!anchorReaches(anchor, root)) return null;
  return anchor === el ||
    (scrollsWith(el, anchor) && !scrollsContent(anchor)) ||
    scrollsWith(anchor, el)
    ? anchor
    : null;
}

const makeFrame = () => {
  const frame = document.createElement("div");
  frame.className = "lf-paint-frame";
  return frame;
};

// Stands `stand`'s frames over `placed`, anchored where `anchored` says its boxes will be
// and every frame's holder can be, else where the window holds them, and answers how its
// boxes stand (`standBox`): anchored, or written from `origin`, the client point the
// carrier's corner stands at.
function standIn(stand, placed, anchored) {
  const { levels } = placed;
  const anchors = levels.map(({ holder }) => holder && anchoredBy(holder, stand.root));
  anchored &&= levels.every(({ holder }, i) => !holder || anchors[i]);
  stand.anchored = anchored;
  stand.frames = cutFrames(
    levels.map(({ band, axes }, i) => ({
      anchor: anchored ? anchors[i] : null,
      band,
      axes,
    })),
    stand.frames,
    makeFrame,
  );
  const [outer] = stand.frames;
  if (outer && outer.parentNode !== stand.root) move(stand.root, outer, null);
  const inner = stand.frames.at(-1) ?? stand.root;
  if (stand.carrier.parentNode !== inner) move(inner, stand.carrier, null);
  const band = levels.at(-1)?.band;
  return {
    anchored,
    origin: anchored ? null : { x: band?.left ?? 0, y: band?.top ?? 0 },
  };
}

// Stands `box` over `rect` in a stand `stood` answered: anchored to `anchor`, read at
// `at` as `rect` was, or from `stood.origin`, the client point its containing frame's
// corner stands at. Without a size, `rect` is a point, the box's corner, and the box
// keeps its own size.
export function standBox(
  box,
  rect,
  stood,
  anchor,
  at = anchor?.getBoundingClientRect(),
) {
  if (stood.anchored) {
    anchorAt(box, anchor, rect, at, stood.visibility ?? "always");
    return;
  }
  Object.assign(box.style, {
    position: "",
    positionAnchor: "",
    positionVisibility: "",
    left: layoutPx(rect.left - stood.origin.x),
    top: layoutPx(rect.top - stood.origin.y),
    ...(rect.right === undefined
      ? {}
      : {
          width: layoutPx(rect.right - rect.left),
          height: layoutPx(rect.bottom - rect.top),
        }),
  });
}

// A stand over one target, its box anchored to that target where the anchor reaches.
// Answers the stand and the anchor, read as `placed` was, for what stands beside it.
export function standOver(stand, placed, borderRadius) {
  const anchor = anchoredBy(placed.surface, stand.root);
  const at = anchor?.getBoundingClientRect();
  const stood = standIn(stand, placed, Boolean(anchor));
  standBox(stand.box, placed.rect, stood, anchor, at);
  Object.assign(stand.box.style, { display: "block", borderRadius });
  return { ...stood, anchor, at };
}

// A set of paint boxes, each over a target and standing in the frames that cut it
// (`placement`), anchored to it where the anchor reaches (`anchoredBy`), the boxes the
// same frames cut sharing a stand, so no scroll writes any of them. A box not `cut`, as
// a chip hung off its target's corner wherever the room around it seats it, or ink
// still being drawn past its target's edge, stands in no frame where it is anchored,
// and hides once its target is scrolled out of sight (`position-visibility:
// anchors-visible`). A box with no target stands where the window holds it.
//
// Only a box whose target is near (geometry.js, `nearWindow`) is in the document.
// `onNear` hears where that changed, once the boxes come near are seated.
//
// `place` takes every box of the set, in paint order, each `{ node, target, rect }`:
// `rect` in client coordinates, a point for a box that keeps its own size, or a
// function of the target's placement, which is the default. `held` places paint over
// what the target holds, cut by its own band too, `anchor` names what carries the box
// where that is not the target's own anchor, `plane` the stacking its stand takes
// (`data-lf-paint-plane`), the page's unless it says otherwise, and `cut: false` that
// no frame cuts it. It reads every box's geometry and
// anchor before it writes any, and the names those anchors need before it gives any,
// since reading an author's name after a write forces the style that write
// invalidated. It answers each box's placement, null where it stands nowhere.
export function paintSet(root, { onNear = () => {} } = {}) {
  const stands = new Map(); // key → stand
  const entries = new Map(); // node → how it stands
  // Each target is watched through the box it anchors by, which a target with no box
  // of its own has in its first shown part (`anchorElement`).
  const near = new Set(); // targets
  const watched = new Map(); // target → the box watched for it
  const watching = new Map(); // box → the targets it is watched for
  const nearBy = (target) => !target || near.has(target);
  const view = nearObserver((records) => {
    const moved = new Set();
    for (const { target: box, isIntersecting } of records)
      for (const target of watching.get(box) ?? []) {
        if (isIntersecting) near.add(target);
        else near.delete(target);
        moved.add(target);
      }
    for (const stand of stands.values())
      if (stand.members.some(({ target }) => moved.has(target))) seat(stand);
    onNear();
  });

  // A stand's key: the frames that cut it, each band from its holder's corner, which no
  // scroll moves, whether they are anchored, and the plane it stands in.
  const ids = new WeakMap();
  let idCount = 0;
  const idOf = (node) => ids.get(node) ?? (ids.set(node, ++idCount), idCount);
  const keyOf = ({ surface, levels }, anchor, plane, framed) =>
    !surface
      ? `${plane}|window`
      : [
          plane,
          framed ? "cut" : "open",
          anchor ? "anchored" : "window",
          ...levels.map(({ holder, band, from, axes }) => {
            const edges = [from.left, from.top, from.left + band.right - band.left];
            return `${holder ? idOf(holder) : "window"}:${[...edges, from.top + band.bottom - band.top]}:${axes.x}${axes.y}`;
          }),
        ].join("|");

  // A stand's boxes in its carrier in order, those whose target is near, the rest out of
  // the document. Each box seated here, every near one for a pass, is written.
  function seat(stand, all = false) {
    const { carrier, members } = stand;
    const seating = new Set(
      members.filter(
        ({ node, target }) => nearBy(target) && (all || node.parentElement !== carrier),
      ),
    );
    const readings = [...seating]
      .filter(({ entry }) => entry.anchor)
      .map(({ entry }) => anchorReading(entry.anchor));
    for (const reading of readings) nameAnchor(reading);
    let cursor = carrier.firstElementChild;
    for (const member of members) {
      const { node, target, entry } = member;
      if (!nearBy(target)) {
        if (node.parentElement !== carrier) continue;
        if (cursor === node) cursor = node.nextElementSibling;
        node.remove();
        continue;
      }
      if (cursor === node) cursor = node.nextElementSibling;
      else move(carrier, node, cursor);
      if (seating.has(member))
        standBox(node, entry.rect, entry.stood, entry.anchor, entry.at);
    }
  }

  function place(items, clips = new Map()) {
    const holders = new Map();
    const targets = new Set();
    const read = items.map((item) => {
      const { node, target = null, rect, held = false, anchor, plane = "page" } = item;
      const { cut: framed = true } = item;
      if (!target) {
        const placed = { surface: null, levels: [] };
        return {
          node,
          target,
          placed,
          rect,
          plane,
          framed,
          key: keyOf(placed, null, plane),
        };
      }
      targets.add(target);
      // A target with no box of its own stands where its parts do (`shownBox`).
      let placed = placement(target, false, false, clips, held);
      const { left, top, right, bottom } = placed.rect;
      if (!(right > left && bottom > top)) return { node, target, placed: null };
      const box = typeof rect === "function" ? rect(placed) : (rect ?? placed.rect);
      // Until the observer's first answer, near is read off the box itself, so a set's
      // first paint draws what it shows.
      if (!watched.has(target)) {
        const box = anchorElement(target);
        watched.set(target, box);
        if (!watching.has(box)) {
          watching.set(box, new Set());
          view.observe(box);
        }
        watching.get(box).add(target);
        if (nearWindow(target, clips)) near.add(target);
      }
      const carriedBy =
        anchor === undefined
          ? anchoredBy(target, root)
          : anchor && anchorReaches(anchor, root)
            ? anchor
            : null;
      // A box no frame cuts is carried by its anchor alone.
      if (!framed) placed = { ...placed, levels: [] };
      // Each level's band from its holder's corner (`from`), which no scroll moves.
      for (const { holder } of placed.levels)
        if (holder && !holders.has(holder))
          holders.set(holder, holder.getBoundingClientRect());
      placed.levels = placed.levels.map((level) => {
        const at = level.holder ? holders.get(level.holder) : { left: 0, top: 0 };
        return {
          ...level,
          from: { left: level.band.left - at.left, top: level.band.top - at.top },
        };
      });
      return {
        node,
        target,
        placed,
        rect: box,
        plane,
        framed,
        anchor: carriedBy,
        at: carriedBy?.getBoundingClientRect(),
        key: keyOf(placed, carriedBy, plane, framed),
      };
    });
    for (const [target, box] of watched)
      if (!targets.has(target)) {
        watched.delete(target);
        near.delete(target);
        watching.get(box).delete(target);
        if (watching.get(box).size) continue;
        watching.delete(box);
        view.unobserve(box);
      }
    // The writes: each stand's frames, in the order its first box comes, then each box
    // in its stand.
    const stood = new Map(); // key → { stand, ... }
    let previous = null;
    for (const { placed, key, anchor, plane, framed } of read) {
      if (!placed || stood.has(key)) continue;
      const stand = stands.get(key) ?? paintStand();
      stands.set(key, stand);
      keeps(stand.root, "data-lf-paint-plane", plane);
      const next = previous ? previous.root.nextElementSibling : root.firstElementChild;
      if (next !== stand.root) move(root, stand.root, next);
      const how = standIn(stand, placed, Boolean(anchor));
      stood.set(key, {
        stand,
        ...how,
        visibility: framed ? "always" : "anchors-visible",
      });
      previous = stand;
    }
    for (const [key, stand] of stands)
      if (!stood.has(key)) {
        dropStand(stand);
        stands.delete(key);
      }
    for (const stand of stands.values()) stand.members = [];
    const placing = new Set();
    for (const { node, target, placed, key, rect, anchor, at } of read) {
      placing.add(node);
      const { stand = null, ...how } = (placed && stood.get(key)) || {};
      const entry = entries.get(node) ?? {};
      if (entry.stand !== stand) node.remove();
      Object.assign(entry, { stand, stood: how, rect, anchor, at });
      entries.set(node, entry);
      stand?.members.push({ node, target, entry });
    }
    for (const node of entries.keys())
      if (!placing.has(node)) {
        node.remove();
        entries.delete(node);
      }
    for (const stand of stands.values()) seat(stand, true);
    return read.map(({ placed }) => placed);
  }

  function clear() {
    for (const stand of stands.values()) dropStand(stand);
    for (const node of entries.keys()) node.remove();
    stands.clear();
    entries.clear();
    near.clear();
    watched.clear();
    watching.clear();
    view.disconnect();
  }

  return {
    place,
    clear,
    // Whether `target`'s boxes stand in the document, near enough to be shown.
    near: nearBy,
    // Whether `node` stands in the set, near or not.
    stands: (node) => Boolean(entries.get(node)?.stand),
  };
}

// A stand whose box is put away keeps no frames, which would hold the scrollers they are
// anchored to after a revision removed them.
export function vacate(stand) {
  if (!stand.frames.length && stand.carrier.parentElement === stand.root) return;
  stand.frames = cutFrames([], stand.frames, makeFrame);
  move(stand.root, stand.carrier, null);
}

export function dropStand(stand) {
  vacate(stand);
  stand.root.remove();
}

// Where a paint box stands over `surface`, and what cuts it, for paint stacked
// `aboveSurfaces` (`data-lf-paint-plane`) or under them: `rect` is the box, the
// surface's own with room for a shape's stroke, and `shown` the part of it no cut hides,
// null where the cuts hide all of it. `shapeKey` changes where a shape drawn in the box
// must be drawn again. `levels` are the frames that cut it, outermost first, each with
// the box `holder` whose band it is, none for the window's. `clips` is the clip walk's
// cache, shared by a pass that places many. Paint over what `surface` holds (`held`), as
// words standing in it, is cut by its own band as well.
export function placement(
  surface,
  shaped,
  aboveSurfaces,
  clips = new Map(),
  held = false,
) {
  const box = shownBox(surface);
  const pad = shaped ? SHAPE_STROKE_ROOM : 0;
  const rect = {
    left: box.left - pad,
    top: box.top - pad,
    right: box.right + pad,
    bottom: box.bottom + pad,
  };
  const cuts = paintClips(surface, rect, clips, aboveSurfaces, held);
  const levels = [];
  if (cuts.window)
    levels.push({ band: cuts.window, axes: { x: true, y: true }, holder: null });
  for (const { box: holder, band, axes } of cuts.bands)
    levels.push({ band, axes, holder });
  let shown = rect;
  for (const { band, axes } of levels) shown = intersect(shown, band, axes);
  return {
    rect,
    shown: hasArea(shown) ? shown : null,
    shapeKey: `${rect.right - rect.left}:${rect.bottom - rect.top}`,
    levels,
    surface,
    plane: cuts.plane,
  };
}
