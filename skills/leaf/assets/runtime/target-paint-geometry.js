/* Where paint over the page's targets stands: traces, visual marks, the design
 * legend, key chips, the search's mark and drawing ink.
 *
 * Read the provider's drawn SVG primitives and clone them into a caller-owned shape,
 * and stand each box in the planes of what carries its target (`paintStand`), alone or
 * in a set (`paintSet`). Each painter decides when geometry must be rebuilt and when
 * only its placement has changed; a set alone keeps state, which of its targets stand
 * near enough to be shown. */

import {
  anchorElement,
  anchorHolder,
  anchorName,
  anchorReading,
  inTopLayer,
  nameAnchor,
  scrollsWith,
} from "./anchor-names.js";
import { paintClips, shownBox } from "./geometry.js";
import { atLayoutPrecision, keeps, layoutPx } from "./keeps.js";
import {
  followScroll,
  scrollsContent,
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

// A stand holds paint boxes over their targets in the planes of what carries the
// targets. Each box that clips a target (`paintClips`) gets a frame cut to its band,
// inside the frame of the box holding it; the boxes stand in the innermost. The window's
// cuts, a header stuck over the page's top and, for paint stacked above them, the
// auxiliary surfaces, stand in the window's plane, as a frame fixed where the window
// holds it. A scroll anywhere around a target moves its box and every cut over it in the
// frame that scrolls, and placing it again after the scroll writes nothing.
//
// Where anchors reach (`anchoredBy`), each frame and each box are fixed and anchored to
// what holds them: a frame to the scroller whose band it cuts, which the scrolls around
// that scroller carry and its own does not, and a box to its own target, so it follows
// that target through layout, a transform or a sticky offset as well, each written as
// insets from its anchor, which no scroll changes. A frame cuts with `clip-path`, which
// clips the fixed boxes inside it without becoming their containing block, as a
// transform would. Chrome paints an anchored box in the frame of the scroll that carries
// it. Boxes the same frames cut share a stand (`standIn`, then `standBox` for each).
//
// Where an anchor does not reach what a stand holds, as a scroller inside a shadow tree,
// the stand stands whole in motion layers (scroll-motion.js): each frame absolute in the
// frame of the box holding it, with one motion layer per axis that box scrolls along,
// every length written where it stands at its scrollers' start, and with no window frame
// the stand is absolute in the document, which the root scroll carries. Chrome can paint
// a layer a frame before or after the scroll it carries, so a stand uses them only there,
// and holds one target's box, whose own timeline its layers follow. Boxes stand in a
// carrier at the innermost container's corner, written from where that corner stood.
// Without ScrollTimeline the frames stand where the scrollers stand now, and the scroll
// that moves them places them again. The stand, not the box, carries the paint's
// stacking (`data-lf-paint-plane`), since the frames and layers it holds stack what they
// hold.
export function paintStand(box = null) {
  const root = document.createElement("div");
  root.className = "lf-ui lf-target-paint lf-paint-stand";
  root.setAttribute("aria-hidden", "true");
  const carrier = document.createElement("div");
  carrier.className = "lf-paint-carrier";
  if (box) carrier.append(box);
  root.append(carrier);
  return { root, carrier, box, anchored: false, levels: [] };
}

// The box an anchor carries `el` by for a stand at `root`: its anchor box
// (anchor-names.js), where every scroll that moves `el` moves that box with it
// (`scrollsWith`), or that box's own parts where `el` draws none. An anchor positions a
// box only where it is laid out before that box, earlier in the document and outside
// the top layer; null otherwise, and where the browser has no anchors.
export function anchoredBy(el, root) {
  const anchor = anchorElement(el);
  if (!reaches(anchor, root)) return null;
  return anchor === el ||
    (scrollsWith(el, anchor) && !scrollsContent(anchor)) ||
    scrollsWith(anchor, el)
    ? anchor
    : null;
}

// Whether an anchor on `anchor`, or on the box holding a content start, positions a box
// at `root`.
function reaches(anchor, root) {
  if (!CSS.supports("anchor-name", "--lf-anchor")) return false;
  const holder = anchorHolder(anchor);
  const order = holder.compareDocumentPosition(root);
  return (
    Boolean(order & Node.DOCUMENT_POSITION_FOLLOWING) &&
    !(order & Node.DOCUMENT_POSITION_CONTAINED_BY) &&
    !inTopLayer(holder)
  );
}

// Each level's motions in a stand that stands in motion layers: the scroll of the box
// holding the level, along the axes it scrolls, carrying the box it holds next, the next
// frame's or the surface's, whose paint reaches past it by the room a shape's stroke
// takes. The window's frame carries the root's scroll where the paint stands in the page.
function levelMotions({ surface, levels, plane, pad }) {
  if (!scrollFollows(surface)) return levels.map(() => []);
  const held = [...levels.filter(({ holder }) => holder).map(({ holder }) => holder)];
  held.push(surface);
  const reach = (i) => (i === held.length - 1 ? pad : 0);
  let band = 0;
  return levels.map(({ holder }) => {
    if (!holder)
      return plane === "page"
        ? scrollMotions(surface.ownerDocument.scrollingElement, held[0], reach(0))
        : [];
    band += 1;
    return scrollMotions(holder, held[band], reach(band));
  });
}

// Whether two placements build a stand alike: anchored, or moving its layers along the
// same axes of the same scrollers.
const sameGraph = (stand, anchored, levels) =>
  stand.anchored === anchored &&
  levels.length === stand.levels.length &&
  levels.every(
    ({ motions }, i) =>
      motions.length === stand.levels[i].motions.length &&
      motions.every(
        ({ source, axis }, j) =>
          source === stand.levels[i].motions[j].source &&
          axis === stand.levels[i].motions[j].axis,
      ),
  );
const sameMotion = (a, b) =>
  a.subject === b.subject &&
  a.from === b.from &&
  a.to === b.to &&
  a.vector.x === b.vector.x &&
  a.vector.y === b.vector.y;

function rebuild(stand, anchored, levels) {
  for (const level of stand.levels)
    for (const animation of level.animations) animation.cancel();
  stand.root.replaceChildren();
  stand.anchored = anchored;
  let parent = stand.root;
  stand.levels = levels.map(({ motions }) => {
    const frame = document.createElement("div");
    frame.className = "lf-paint-frame";
    parent.append(frame);
    parent = frame;
    const layers = motions.map(() => {
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
  parent.append(stand.carrier);
}

const sized = ({ left, top, right, bottom }) => ({
  width: layoutPx(right - left),
  height: layoutPx(bottom - top),
});
// `box` written from `origin`, the client point its container's corner stood at.
const placeIn = (node, box, origin) =>
  Object.assign(node.style, {
    left: layoutPx(box.left - origin.x),
    top: layoutPx(box.top - origin.y),
    ...sized(box),
  });
// `box` written as insets from where `anchor` stood (`at`) when `box` was measured, or
// from where the window does.
const anchorBox = (node, box, anchor, at = anchor?.getBoundingClientRect()) => {
  const from = (side, length) =>
    anchor ? `calc(anchor(${side}, -9999px) + ${layoutPx(length)})` : layoutPx(length);
  Object.assign(node.style, {
    position: "fixed",
    positionAnchor: anchor ? anchorName(anchor) : "",
    positionVisibility: anchor ? "always" : "",
    left: from("left", box.left - (at?.left ?? 0)),
    top: from("top", box.top - (at?.top ?? 0)),
    ...sized(box),
  });
};
// A frame's cut on the axes its box clips, and none on the others.
const cut = ({ x, y }) => {
  const open = (clips) => (clips ? "0" : "-100000px");
  return `inset(${open(y)} ${open(x)})`;
};

// Stands `stand`'s frames over `placed`, anchored where `anchored` says its boxes will
// be and every frame's holder can be, else in motion layers, and answers how its boxes
// stand (`standBox`): anchored, or written from `origin`, the client point the carrier's
// corner stood at as `placed` was measured.
export function standIn(stand, placed, anchored) {
  const { levels, fixed } = placed;
  const anchors = levels.map(({ holder }) => holder && anchoredBy(holder, stand.root));
  anchored &&= levels.every(({ holder }, i) => !holder || anchors[i]);
  const motions = anchored ? levels.map(() => []) : levelMotions(placed);
  const graph = levels.map((level, i) => ({ ...level, motions: motions[i] }));
  if (!sameGraph(stand, anchored, graph)) rebuild(stand, anchored, graph);
  if (anchored) {
    stand.root.style.position = "fixed";
    graph.forEach(({ band, axes }, i) => {
      const { frame } = stand.levels[i];
      anchorBox(frame, band, anchors[i]);
      frame.style.clipPath = cut(axes);
    });
    return { anchored, origin: null };
  }
  // A subject that moved in its scroller, or grew, crosses the view over other scrolls.
  graph.forEach(({ motions }, i) => {
    const stood = stand.levels[i];
    motions.forEach((motion, j) => {
      if (sameMotion(motion, stood.motions[j])) return;
      stood.animations[j] = followScroll(
        stood.layers[j],
        motion,
        0,
        stood.animations[j],
      );
      stood.motions[j] = motion;
    });
  });
  stand.root.style.position = fixed ? "fixed" : "absolute";
  // Where each level's contents stand from, in client coordinates: the document's origin
  // for an absolute stand, the window's for a fixed one, then each frame's corner,
  // carried back to where its scrollers start.
  let from = fixed ? { x: 0, y: 0 } : { x: -scrollX, y: -scrollY };
  graph.forEach(({ band, axes, motions }, i) => {
    const { frame } = stand.levels[i];
    placeIn(frame, band, from);
    Object.assign(frame.style, {
      overflowX: axes.x ? "clip" : "visible",
      overflowY: axes.y ? "clip" : "visible",
    });
    const by = scrolledBy(motions);
    from = { x: band.left + by.x, y: band.top + by.y };
  });
  return { anchored, origin: from };
}

// Stands `box` over `rect` in a stand `stood` answered: anchored to `anchor`, read at
// `at` as `rect` was, or from the carrier's corner. Without a size, `rect` is a point,
// the box's corner, and the box keeps its own size.
export function standBox(
  box,
  rect,
  stood,
  anchor,
  at = anchor?.getBoundingClientRect(),
) {
  const sizes = rect.right !== undefined;
  if (stood.anchored) {
    const from = (side, length) =>
      `calc(anchor(${side}, -9999px) + ${layoutPx(length)})`;
    Object.assign(box.style, {
      position: "fixed",
      positionAnchor: anchorName(anchor),
      positionVisibility: stood.visibility ?? "always",
      left: from("left", rect.left - at.left),
      top: from("top", rect.top - at.top),
      ...(sizes ? sized(rect) : {}),
    });
    return;
  }
  Object.assign(box.style, {
    position: "",
    positionAnchor: "",
    positionVisibility: "",
    left: layoutPx(rect.left - stood.origin.x),
    top: layoutPx(rect.top - stood.origin.y),
    ...(sizes ? sized(rect) : {}),
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
// anchors-visible`); unanchored, it stands uncut in its target's layers. A box with no
// target stands where the window holds it.
//
// Only a box whose target stands within a screen of being shown, the scrollers around
// it included (`scrollMargin`), is in the document. A box out of it costs no layout,
// where boxes hidden beside the anchored ones made every layout pass revisit them all.
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
  const view = new IntersectionObserver(
    (records) => {
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
    },
    { rootMargin: "100%", scrollMargin: "600px" },
  );

  // A stand's key: the frames that cut it, each band from its holder's corner, which no
  // scroll moves, and the plane it stands in. A stand in motion layers follows its one
  // target's timelines, so it holds that target's boxes alone.
  const ids = new WeakMap();
  let idCount = 0;
  const idOf = (node) => ids.get(node) ?? (ids.set(node, ++idCount), idCount);
  const keyOf = ({ surface, fixed, levels }, anchor, plane, framed) =>
    !surface
      ? `${plane}|window`
      : [
          plane,
          framed ? "cut" : "open",
          fixed ? "fixed" : "page",
          anchor ? "anchored" : levels.length ? `own${idOf(surface)}` : "",
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
      else carrier.insertBefore(node, cursor);
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
        const placed = { surface: null, levels: [], fixed: true };
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
        if (
          bottom > -innerHeight &&
          top < 2 * innerHeight &&
          right > -innerWidth &&
          left < 2 * innerWidth
        )
          near.add(target);
      }
      const carriedBy =
        anchor === undefined
          ? anchoredBy(target, root)
          : anchor && reaches(anchor, root)
            ? anchor
            : null;
      // A box no frame cuts is carried by its anchor alone, or by its target's layers
      // standing open.
      if (!framed)
        placed = {
          ...placed,
          levels: carriedBy
            ? []
            : placed.levels.map((level) => ({
                ...level,
                axes: { x: false, y: false },
              })),
        };
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
      if (next !== stand.root) root.insertBefore(stand.root, next);
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

// A stand whose box is put away keeps no frames, layers or timelines, which would hold
// the scrollers they follow after a revision removed them.
export function vacate(stand) {
  if (stand.levels.length || stand.carrier.parentElement !== stand.root)
    rebuild(stand, false, []);
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
  for (const { band, axes } of levels)
    shown = {
      left: axes.x ? Math.max(shown.left, band.left) : shown.left,
      top: axes.y ? Math.max(shown.top, band.top) : shown.top,
      right: axes.x ? Math.min(shown.right, band.right) : shown.right,
      bottom: axes.y ? Math.min(shown.bottom, band.bottom) : shown.bottom,
    };
  return {
    rect,
    shown: shown.right > shown.left && shown.bottom > shown.top ? shown : null,
    shapeKey: `${rect.right - rect.left}:${rect.bottom - rect.top}`,
    levels,
    surface,
    pad,
    plane: cuts.plane,
    fixed: cuts.plane === "window" || Boolean(cuts.window),
  };
}
