import {
  KINDS,
  annotationItems,
  clearContributionControls,
  contributionHost,
  contributionItemKey,
  contributionReceipts,
  contributionSource,
  entryControls,
  spokenSubject,
  versionBtn,
  visibleContributionEntryLabel
} from "./bundle-contribution-model.js";
import {
  BANNER_CONTROL_RANK,
  bannerControlDoor,
  placeKeeper,
  registerBannerControl,
  retainUserIntent,
  rowWalk,
  scrollIntoView,
  showBannerControl
} from "./bundle-user-intent.js";
import {
  anchorAt,
  anchorElement,
  anchorReaches,
  anchorReading,
  cutFrames,
  nameAnchor,
  scrollsWith
} from "./bundle-chrome.js";
import {
  blockAt,
  inChrome,
  says
} from "./bundle-passage-facts.js";
import {
  closeControl,
  closeNativeLayer,
  coarsePointer,
  el,
  hasArea,
  iconTemplate,
  intersect,
  keys,
  nearObserver,
  nearWindow,
  paintClips,
  paintKeys,
  pressIsKeyboardActivation,
  scrollsContent,
  searchField,
  showNativeLayer,
  shownBox
} from "./bundle-page-paint.js";
import {
  atLayoutPrecision,
  cancelRender,
  closeLayer,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  keeps,
  keepsHidden,
  keepsText,
  layoutPx,
  move,
  nextRender,
  openLayer,
  openerOf
} from "./bundle-sample-visibility.js";
import {
  html,
  nothing,
  render,
  repeat
} from "./bundle-queued-work.js";
import {
  __export
} from "./bundle-__export.js";

// runtime/target-paint.js
var target_paint_exports = {};
__export(target_paint_exports, {
  aimLayer: () => aimLayer,
  clearAim: () => clearAim,
  geometryChanged: () => geometryChanged,
  labelAim: () => labelAim,
  mountTargetPaint: () => mountTargetPaint,
  paintAim: () => paintAim,
  paintTrace: () => paintTrace,
  shifted: () => shifted,
  targetTraceLayer: () => targetTraceLayer
});

// runtime/target-paint-geometry.js
var SVG_NS = "http://www.w3.org/2000/svg";
var SHAPE_STROKE_ROOM = 2;
var paints = (shape, property) => {
  const style = getComputedStyle(shape);
  return shape.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && style[property] !== "none" && Number.parseFloat(style[`${property}Opacity`]) !== 0 && (property !== "stroke" || Number.parseFloat(style.strokeWidth) > 0);
};
function paintGeometry(surface) {
  if (!(surface instanceof SVGElement)) return null;
  const geometry = [surface, ...surface.querySelectorAll("*")].filter(
    (child) => child instanceof SVGGeometryElement
  );
  const fill = geometry.filter((shape) => paints(shape, "fill"));
  const paintedStroke = geometry.filter((shape) => paints(shape, "stroke"));
  const outlined = /* @__PURE__ */ new Set([...fill, ...paintedStroke]);
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
  for (const attribute of [...clone.attributes]) {
    const length = source[attribute.localName];
    if (attribute.value.includes("%") && typeof SVGAnimatedLength !== "undefined" && length instanceof SVGAnimatedLength)
      clone.setAttribute(attribute.name, String(length.animVal.value));
  }
  clone.setAttribute(
    "transform",
    `matrix(${matrix.a} ${matrix.b} ${matrix.c} ${matrix.d} ${atLayoutPrecision(matrix.e - left)} ${atLayoutPrecision(matrix.f - top)})`
  );
  clone.style.setProperty("fill", property === "fill" ? "white" : "none", "important");
  clone.style.setProperty(
    "stroke",
    property === "stroke" ? "var(--lf-shape-ink)" : "none",
    "important"
  );
  clone.style.setProperty("stroke-width", "var(--lf-shape-stroke)", "important");
  clone.style.setProperty(
    "stroke-dasharray",
    "var(--lf-shape-dash, none)",
    "important"
  );
  clone.style.setProperty("stroke-linejoin", "round", "important");
  clone.style.setProperty("stroke-linecap", "round", "important");
  clone.style.setProperty("vector-effect", "non-scaling-stroke", "important");
  return clone;
}
function paintShape(host, geometry, { left, top, right, bottom }, options = {}) {
  if (!geometry) return false;
  const { maskId = "", veil = false } = options;
  const width = atLayoutPrecision(right - left);
  const height = atLayoutPrecision(bottom - top);
  const fill = veil ? geometry.fill.map((shape) => geometryClone(shape, left, top, "fill")) : [];
  const stroke = geometry.stroke.map(
    (shape) => geometryClone(shape, left, top, "stroke")
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
  const held = host.children;
  if (paint.length !== held.length || paint.some((node, index) => !node.isEqualNode(held[index])))
    host.replaceChildren(...paint);
  return true;
}
function paintStand(box = null) {
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
function anchoredBy(el2, root) {
  const anchor = anchorElement(el2);
  if (!anchorReaches(anchor, root)) return null;
  return anchor === el2 || scrollsWith(el2, anchor) && !scrollsContent(anchor) || scrollsWith(anchor, el2) ? anchor : null;
}
var makeFrame = () => {
  const frame = document.createElement("div");
  frame.className = "lf-paint-frame";
  return frame;
};
function standIn(stand, placed, anchored) {
  const { levels } = placed;
  const anchors = levels.map(({ holder }) => holder && anchoredBy(holder, stand.root));
  anchored &&= levels.every(({ holder }, i) => !holder || anchors[i]);
  stand.anchored = anchored;
  stand.frames = cutFrames(
    levels.map(({ band: band2, axes }, i) => ({
      anchor: anchored ? anchors[i] : null,
      band: band2,
      axes
    })),
    stand.frames,
    makeFrame
  );
  const [outer] = stand.frames;
  if (outer && outer.parentNode !== stand.root) move(stand.root, outer, null);
  const inner = stand.frames.at(-1) ?? stand.root;
  if (stand.carrier.parentNode !== inner) move(inner, stand.carrier, null);
  const band = levels.at(-1)?.band;
  return {
    anchored,
    origin: anchored ? null : { x: band?.left ?? 0, y: band?.top ?? 0 }
  };
}
function standBox(box, rect, stood, anchor, at = anchor?.getBoundingClientRect()) {
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
    ...rect.right === void 0 ? {} : {
      width: layoutPx(rect.right - rect.left),
      height: layoutPx(rect.bottom - rect.top)
    }
  });
}
function standOver(stand, placed, borderRadius) {
  const anchor = anchoredBy(placed.surface, stand.root);
  const at = anchor?.getBoundingClientRect();
  const stood = standIn(stand, placed, Boolean(anchor));
  standBox(stand.box, placed.rect, stood, anchor, at);
  Object.assign(stand.box.style, { display: "block", borderRadius });
  return { ...stood, anchor, at };
}
function paintSet(root, { onNear = () => {
} } = {}) {
  const stands = /* @__PURE__ */ new Map();
  const entries = /* @__PURE__ */ new Map();
  const near = /* @__PURE__ */ new Set();
  const watched = /* @__PURE__ */ new Map();
  const watching = /* @__PURE__ */ new Map();
  const nearBy = (target) => !target || near.has(target);
  const view = nearObserver((records) => {
    const moved = /* @__PURE__ */ new Set();
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
  const ids = /* @__PURE__ */ new WeakMap();
  let idCount = 0;
  const idOf = (node) => ids.get(node) ?? (ids.set(node, ++idCount), idCount);
  const keyOf = ({ surface, levels }, anchor, plane, framed) => !surface ? `${plane}|window` : [
    plane,
    framed ? "cut" : "open",
    anchor ? "anchored" : "window",
    ...levels.map(({ holder, band, from, axes }) => {
      const edges = [from.left, from.top, from.left + band.right - band.left];
      return `${holder ? idOf(holder) : "window"}:${[...edges, from.top + band.bottom - band.top]}:${axes.x}${axes.y}`;
    })
  ].join("|");
  function seat(stand, all = false) {
    const { carrier, members } = stand;
    const seating = new Set(
      members.filter(
        ({ node, target }) => nearBy(target) && (all || node.parentElement !== carrier)
      )
    );
    const readings = [...seating].filter(({ entry }) => entry.anchor).map(({ entry }) => anchorReading(entry.anchor));
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
  function place2(items, clips = /* @__PURE__ */ new Map()) {
    const holders = /* @__PURE__ */ new Map();
    const targets = /* @__PURE__ */ new Set();
    const read = items.map((item) => {
      const { node, target = null, rect, held = false, anchor, plane = "page" } = item;
      const { cut: framed = true } = item;
      if (!target) {
        const placed2 = { surface: null, levels: [] };
        return {
          node,
          target,
          placed: placed2,
          rect,
          plane,
          framed,
          key: keyOf(placed2, null, plane)
        };
      }
      targets.add(target);
      let placed = placement(target, false, false, clips, held);
      const { left, top, right, bottom } = placed.rect;
      if (!(right > left && bottom > top)) return { node, target, placed: null };
      const box = typeof rect === "function" ? rect(placed) : rect ?? placed.rect;
      if (!watched.has(target)) {
        const box2 = anchorElement(target);
        watched.set(target, box2);
        if (!watching.has(box2)) {
          watching.set(box2, /* @__PURE__ */ new Set());
          view.observe(box2);
        }
        watching.get(box2).add(target);
        if (nearWindow(target, clips)) near.add(target);
      }
      const carriedBy = anchor === void 0 ? anchoredBy(target, root) : anchor && anchorReaches(anchor, root) ? anchor : null;
      if (!framed) placed = { ...placed, levels: [] };
      for (const { holder } of placed.levels)
        if (holder && !holders.has(holder))
          holders.set(holder, holder.getBoundingClientRect());
      placed.levels = placed.levels.map((level) => {
        const at = level.holder ? holders.get(level.holder) : { left: 0, top: 0 };
        return {
          ...level,
          from: { left: level.band.left - at.left, top: level.band.top - at.top }
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
        key: keyOf(placed, carriedBy, plane, framed)
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
    const stood = /* @__PURE__ */ new Map();
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
        visibility: framed ? "always" : "anchors-visible"
      });
      previous = stand;
    }
    for (const [key, stand] of stands)
      if (!stood.has(key)) {
        dropStand(stand);
        stands.delete(key);
      }
    for (const stand of stands.values()) stand.members = [];
    const placing = /* @__PURE__ */ new Set();
    for (const { node, target, placed, key, rect, anchor, at } of read) {
      placing.add(node);
      const { stand = null, ...how } = placed && stood.get(key) || {};
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
    place: place2,
    clear,
    // Whether `target`'s boxes stand in the document, near enough to be shown.
    near: nearBy,
    // Whether `node` stands in the set, near or not.
    stands: (node) => Boolean(entries.get(node)?.stand)
  };
}
function vacate(stand) {
  if (!stand.frames.length && stand.carrier.parentElement === stand.root) return;
  stand.frames = cutFrames([], stand.frames, makeFrame);
  move(stand.root, stand.carrier, null);
}
function dropStand(stand) {
  vacate(stand);
  stand.root.remove();
}
function placement(surface, shaped, aboveSurfaces, clips = /* @__PURE__ */ new Map(), held = false) {
  const box = shownBox(surface);
  const pad = shaped ? SHAPE_STROKE_ROOM : 0;
  const rect = {
    left: box.left - pad,
    top: box.top - pad,
    right: box.right + pad,
    bottom: box.bottom + pad
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
    plane: cuts.plane
  };
}

// runtime/target-paint.js
var targetTraceBox = el("div", "lf-ui lf-target-trace");
var aimBox = el("div", "lf-ui lf-aim");
var traceStand = paintStand(targetTraceBox);
var aimStand = paintStand(aimBox);
var targetTraceLayer = traceStand.root;
var aimLayer = aimStand.root;
var aimShape = document.createElementNS(SVG_NS, "svg");
aimShape.classList.add("lf-aim-shape");
aimShape.setAttribute("aria-hidden", "true");
var aimMaskId = "lf-runtime-aim-shape-mask";
var targetTraceShape = document.createElementNS(SVG_NS, "svg");
targetTraceShape.classList.add("lf-target-trace-shape");
targetTraceShape.setAttribute("aria-hidden", "true");
var aimPlaced = null;
var aimStood = null;
var traceElement = null;
var traceSurface = null;
var traceGeometry = null;
var traceShapeKey = "";
var placementFrame = 0;
var geometryFrame = 0;
var geometryDirty = false;
function clearAim() {
  aimPlaced = aimStood = null;
  vacate(aimStand);
  aimBox.style.display = "none";
  aimBox.classList.toggle("lf-shaped", false);
  aimShape.replaceChildren();
  aimBox.removeAttribute("data-for");
  delete aimStand.root.dataset.lfPaintPlane;
}
function paintAim(element, surface = null) {
  const geometry = surface ? paintGeometry(surface) : null;
  const placed = element && placement(surface ?? element, Boolean(geometry), inChrome(element));
  if (!placed?.shown) {
    clearAim();
    return null;
  }
  const shaped = paintShape(aimShape, geometry, placed.rect, {
    maskId: aimMaskId,
    veil: true
  });
  aimBox.classList.toggle("lf-shaped", shaped);
  if (!shaped) aimShape.replaceChildren();
  keeps(aimBox, "data-for", element.id);
  keeps(aimStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
  aimStood = standOver(
    aimStand,
    placed,
    getComputedStyle(surface ?? element).borderRadius
  );
  aimPlaced = placed;
  return placed.shown;
}
function labelAim(node) {
  if (!aimPlaced) return;
  const { rect, shown, levels } = aimPlaced;
  const above = shown.top - node.offsetHeight - 2;
  const room = Math.max(
    0,
    ...levels.filter(({ axes }) => axes.y).map(({ band }) => band.top)
  );
  const cutTop = shown.top > rect.top;
  const at = {
    left: Math.max(2, shown.left),
    top: !cutTop && above >= room ? above : shown.top + 2
  };
  const index = cutTop ? levels.findLastIndex(({ axes, band }) => axes.y && band.top === shown.top) : shown.left > rect.left ? levels.findLastIndex(({ axes, band }) => axes.x && band.left === shown.left) : -1;
  if (index >= 0) {
    const home = aimStand.frames[index];
    if (node.parentElement !== home) move(home, node, null);
    const { band } = levels[index];
    standBox(node, at, { anchored: false, origin: { x: band.left, y: band.top } });
    return;
  }
  if (node.parentElement !== aimStand.carrier) move(aimStand.carrier, node, null);
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
function drawTrace(element = traceElement, surface = traceSurface, rebuildGeometry = true) {
  if (!(element instanceof Element) || !(surface instanceof Element) || !element.isConnected || !surface.isConnected) {
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
function paintTrace(element, surface = element) {
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
function shifted() {
  if (placementFrame || geometryFrame || !traceElement) return;
  placementFrame = nextRender(() => {
    placementFrame = 0;
    if (traceElement) drawTrace(traceElement, traceSurface, false);
  });
}
function geometryChanged() {
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
function mountTargetPaint() {
  aimBox.append(aimShape);
  targetTraceBox.append(targetTraceShape);
}

// runtime/margin-map-model.js
var dialogItemKey = (entry, item) => JSON.stringify(["item", entry.key, contributionItemKey(item)]);
function dialogControlKey(entry, offered, record) {
  return JSON.stringify(["control", entry.key, offered.key, record.key]);
}
var dialogControlId = (entry, offered, record) => `lf-page-map-entry-${encodeURIComponent(dialogControlKey(entry, offered, record))}`;
function marginMapGroups(entries, faceFor, searchTextByKey) {
  return Object.freeze(
    entries.map((entry) => {
      const controls = entryControls(entry);
      const items = annotationItems(entry);
      const actions = [
        ...items.map((item) => {
          const face = faceFor(item);
          const visibleLabel = item.text || entry.title;
          return {
            kind: "item",
            key: dialogItemKey(entry, item),
            entry,
            item,
            icon: face.icon,
            label: `Open ${face.label.toLowerCase()}: ${spokenSubject(visibleLabel)}`,
            visibleLabel,
            // Producers add context only when it carries another fact. Version
            // comparisons do: their pair is provenance, separate from the account.
            context: item.mapContext,
            receipt: item.workflowReceipt,
            awaitsUser: Boolean(item.userAttention)
          };
        }),
        ...controls.map(({ offered, record, receipt }) => ({
          kind: "control",
          key: dialogControlKey(entry, offered, record),
          id: dialogControlId(entry, offered, record),
          entry,
          offered,
          record,
          icon: record.icon,
          glyph: record.glyph,
          label: record.accessibleLabel,
          visibleLabel: visibleContributionEntryLabel(record),
          context: record.context,
          receipt,
          awaitsUser: false
        }))
      ];
      const search = [
        entry.title,
        ...actions.flatMap(({ visibleLabel, context }) => [visibleLabel, context]),
        searchTextByKey.get(entry.key)
      ].filter(Boolean).join(" ").toLocaleLowerCase();
      return Object.freeze({
        key: entry.key,
        entry,
        controls: Object.freeze(controls),
        actions: Object.freeze(actions.map(Object.freeze)),
        search
      });
    })
  );
}

// runtime/page-map-dialog.js
var mapButton = el("button", "lf-btn lf-page-map-toggle", "Map");
var mapCount = 0;
mapButton.type = "button";
mapButton.title = "Open Page Map";
registerBannerControl({
  key: "map",
  control: mapButton,
  rank: BANNER_CONTROL_RANK.map,
  present: false,
  row: {
    label: "Page Map",
    value: () => String(mapCount),
    group: "keys"
  }
});
var dialog = document.createElement("dialog");
dialog.className = "lf-ui lf-page-map-dialog";
dialog.setAttribute("aria-label", "Page Map");
dialog.setAttribute("aria-modal", "true");
var dialogHead = el("div", "lf-page-map-head");
dialogHead.append(el("strong", "", "Page Map"));
var dialogClose = closeControl({
  name: "Close Page Map",
  title: "Close Page Map (Esc)"
});
dialogHead.append(dialogClose);
var dialogSearch = searchField("lf-page-map-search", {
  name: "page-map-search",
  label: "Find an action, status, or location in Page Map",
  placeholder: "Find an action, status, or location"
});
var dialogList = el("div", "lf-page-map-list");
var place = placeKeeper(dialogList, {
  items: ".lf-page-map-action",
  identity: (row) => row.dataset.lfMapKey,
  active: () => dialog.open
});
var dialogEmpty = el(
  "p",
  "lf-page-map-empty",
  "No matching actions, statuses, or locations"
);
dialogEmpty.hidden = true;
dialogEmpty.setAttribute("role", "status");
dialog.append(dialogHead, dialogSearch, dialogList, dialogEmpty);
var mapRows = () => [...dialogList.querySelectorAll("button.lf-page-map-action")].filter(
  (row) => row.checkVisibility()
);
function createPageMapDialog({
  inventory,
  activeInAnnotations,
  releaseAnnotations,
  annotationFocus
}) {
  const { targetFor } = inventory;
  let entries = [];
  let groups = [];
  let target = null;
  let trackedOffers = /* @__PURE__ */ new Set();
  const pageMapIsActive = () => dialog.open || Boolean(activeInAnnotations?.());
  function activateItem(item, entry) {
    releaseAnnotations?.(entry);
    const destination = annotationFocus?.(entry);
    closeLayer(
      leavePageMap,
      () => !destination && targetFor(entry)?.isConnected ? focusDestination(targetFor(entry), "move") : handBack(destination, pageMapInvoker(), bannerControlDoor(versionBtn))
    );
    inventory.activate(item);
  }
  function pageMapDialogContains(candidate, node) {
    return dialog.open && target === candidate && dialog.contains(node);
  }
  const sheetFace = ({ icon, glyph, visibleLabel, context }) => html`${icon ? iconTemplate(icon, "lf-margin-kind") : html`<span class="lf-margin-kind">${glyph}</span>`}<span class="lf-page-map-action-label"
        ><span class="lf-page-map-action-label-word">${visibleLabel}</span>${context ? html`<span class="lf-page-map-action-context">${context}</span>` : nothing}</span
      >`;
  function activateSheetControl(event, action) {
    const { offered, record } = action;
    if (record.behavior === "status" || record.disabled) return;
    const control = event.currentTarget;
    const relation = record.relation;
    if (relation?.kind === "entries") {
      const currentIntent = retainUserIntent({ available: () => dialog.open });
      contributionSource(offered).registration.activate(record.key, {
        origin: control,
        surface: "map",
        input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer"
      });
      nextRender(() => {
        if (!currentIntent()) return;
        const revealed = relation.keys.map(
          (key) => contributionSource(offered).registration.control(key, "map", true)
        ).find((candidate) => candidate?.checkVisibility());
        focusDestination(revealed ?? control, "move");
      });
      return;
    }
    const returnTo = openerOf(dialog);
    closeLayer(
      () => closeNativeLayer(dialog),
      () => handBack(returnTo)
    );
    contributionSource(offered).registration.activate(record.key, {
      origin: control,
      surface: "map",
      input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer"
    });
  }
  const sheetHost = (action, actions) => contributionHost(contributionSource(action.offered), "map", action.record, {
    accessibleLabel: [action.record.accessibleLabel, action.record.context].filter(Boolean).join(", "),
    relatedControlIds: relatedControlIds(action, actions)
  });
  const sheetItemTemplate = (action) => html`
    <button
      type="button"
      class="lf-page-map-action"
      data-lf-map-key=${action.key}
      data-lf-map-item=${action.item.id}
      aria-label=${[action.label, action.context].filter(Boolean).join(", ")}
      ${contributionReceipts(action.receipt, action.awaitsUser)}
      @click=${() => activateItem(action.item, action.entry)}
    >
      ${sheetFace(action)}
    </button>
  `;
  function relatedControlIds(action, actions) {
    if (action.record.relation?.kind !== "entries") return [];
    const related = new Set(action.record.relation.keys);
    const ids = actions.filter(
      (candidate) => candidate.kind === "control" && candidate.offered === action.offered && related.has(candidate.record.key)
    ).map(({ id }) => id);
    return ids;
  }
  const sheetControlTemplate = (action, actions) => {
    const body = sheetFace(action);
    if (action.record.behavior === "status")
      return html`<span
        id=${action.id}
        class="lf-page-map-action"
        data-lf-map-key=${action.key}
        data-lf-map-margin-entry=${action.key}
        ${sheetHost(action, actions)}
        ${contributionReceipts(action.receipt, action.awaitsUser)}
        >${body}</span
      >`;
    return html`<button
      id=${action.id}
      type="button"
      class="lf-page-map-action"
      data-lf-map-key=${action.key}
      data-lf-map-margin-entry=${action.key}
      ${sheetHost(action, actions)}
      ${contributionReceipts(action.receipt, action.awaitsUser)}
      @click=${(event) => activateSheetControl(event, action)}
    >
      ${body}
    </button>`;
  };
  const sheetGroupTemplate = (group, query) => html`
    <section
      class="lf-page-map-group"
      data-lf-map-group=${group.key}
      ?hidden=${Boolean(query) && !group.search.includes(query)}
    >
      <h3>${group.entry.title}</h3>
      <div class="lf-page-map-actions">
        ${repeat(
    group.actions,
    ({ key }) => key,
    (action) => action.kind === "item" ? sheetItemTemplate(action) : sheetControlTemplate(action, group.actions)
  )}
      </div>
    </section>
  `;
  function renderSheet() {
    const restoreFocus = holdFocus(dialog);
    place.around(() => presentSheet());
    restoreFocus?.(dialogSearch);
  }
  function presentSheet() {
    const query = dialogSearch.value.trim().toLocaleLowerCase();
    const searchTextByKey = new Map(
      entries.map((entry) => {
        const passage = blockAt(targetFor(entry));
        return [entry.key, passage ? says(passage) : ""];
      })
    );
    groups = marginMapGroups(entries, (item) => KINDS[item.kind], searchTextByKey);
    render(
      html`${repeat(
        groups,
        ({ key }) => key,
        (group) => sheetGroupTemplate(group, query)
      )}`,
      dialogList
    );
    const liveOffers = new Set(
      groups.flatMap(({ entry }) => entry.offers.map(contributionSource))
    );
    for (const offered of trackedOffers)
      if (!liveOffers.has(offered))
        clearContributionControls(offered, "map", /* @__PURE__ */ new Set());
    for (const group of groups) {
      for (const offered of group.entry.offers)
        clearContributionControls(
          contributionSource(offered),
          "map",
          new Set(
            group.controls.filter((candidate) => candidate.offered === offered).map(({ record }) => record.key)
          )
        );
    }
    trackedOffers = liveOffers;
    const shown = groups.filter(
      (group) => !query || group.search.includes(query)
    ).length;
    keepsText(
      dialogEmpty,
      query ? "No matching actions, statuses, or locations" : "No margin controls, status indicators, or locations yet"
    );
    keepsHidden(dialogEmpty, shown !== 0);
  }
  function pageMapInvoker() {
    return bannerControlDoor(mapButton) ?? mapButton;
  }
  function renderPageMapDialog(nextEntries) {
    entries = nextEntries;
    const label = `Map (${entries.length})`;
    mapCount = entries.length;
    showBannerControl(mapButton, entries.length > 0);
    keepsText(mapButton, label);
    if (dialog.open) renderSheet();
  }
  function openPageMap(entry = null, { invoker = null, focusSpill = false } = {}) {
    const openedFrom = invoker ?? focused();
    target = entry ? targetFor(entry) : null;
    if (!dialog.open) {
      openLayer(dialog, openedFrom);
      dialogSearch.value = "";
    }
    renderSheet();
    if (!dialog.open) showNativeLayer(dialog);
    const index = entry ? entries.findIndex((candidate) => candidate.key === entry.key) : -1;
    const group = index < 0 ? null : dialogList.children[index];
    if (group) {
      const listBox = dialogList.getBoundingClientRect();
      const groupBox = group.getBoundingClientRect();
      if (groupBox.top < listBox.top)
        dialogList.scrollTop -= listBox.top - groupBox.top;
      else if (groupBox.bottom > listBox.bottom)
        dialogList.scrollTop += groupBox.bottom - listBox.bottom;
    }
    const spilled = focusSpill ? openedFrom?.lfFirstSpilledOption : null;
    const spilledAction = focusSpill ? groups[index]?.actions.find(
      (action) => action.kind === "control" && action.record.key === spilled?.record?.key && action.record.owner === spilled?.record?.owner || action.kind === "item" && spilled?.choice?.items.some(
        (item) => contributionItemKey(action.item) === contributionItemKey(item)
      )
    ) : null;
    const destination = focusSpill ? spilledAction && group?.querySelector(`[data-lf-map-key="${CSS.escape(spilledAction.key)}"]`) : group?.querySelector(".lf-page-map-action");
    focusDestination(
      destination ?? (coarsePointer.matches ? mapRows()[0] ?? dialogClose : dialogSearch),
      "move"
    );
    paintKeys();
  }
  const enterPageMap = () => openPageMap();
  function leavePageMap() {
    if (!dialog.open) return;
    closeLayer(() => closeNativeLayer(dialog));
  }
  function cancelPageMap() {
    const returnTo = openerOf(dialog);
    closeLayer(leavePageMap, () => handBack(returnTo));
  }
  const mapHasEntries = () => entries.length > 0;
  function mount(root) {
    dialogSearch.addEventListener("input", renderSheet);
    keys(
      dialog,
      "In the Page Map",
      rowWalk({ id: "map", noun: "Entry", plural: "entries", rows: mapRows }),
      mapHasEntries
    );
    mapButton.onclick = enterPageMap;
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      cancelPageMap();
    });
    dialog.addEventListener("close", () => {
      if (dialog.open) return;
      target = null;
      paintKeys();
    });
    dialogClose.onclick = cancelPageMap;
    root.append(dialog);
    dialogSearch.updateComplete.then(declareSearchKeys);
  }
  function declareSearchKeys() {
    const hasRows = () => mapRows().length > 0;
    keys(
      dialogSearch.input,
      "In the Page Map's search",
      [
        {
          id: "map.search.enter",
          keys: ["ArrowDown"],
          description: "Go from the search to the first entry",
          title: "to the entries",
          when: hasRows,
          run: () => {
            const row = mapRows()[0];
            focusDestination(row, "move");
            scrollIntoView(row, { block: "nearest" });
          }
        },
        {
          id: "map.search.open",
          keys: ["Enter"],
          description: "Open the first matching entry",
          title: "open first",
          when: hasRows,
          run: () => mapRows()[0].click()
        }
      ],
      mapHasEntries
    );
  }
  return {
    pageMapIsActive,
    pageMapDialogContains,
    renderPageMapDialog,
    openPageMap,
    enterPageMap,
    leavePageMap,
    mount
  };
}

export {
  SVG_NS,
  paintGeometry,
  paintShape,
  paintStand,
  standOver,
  paintSet,
  dropStand,
  placement,
  targetTraceLayer,
  aimLayer,
  paintTrace,
  mountTargetPaint,
  target_paint_exports,
  mapButton,
  createPageMapDialog
};
