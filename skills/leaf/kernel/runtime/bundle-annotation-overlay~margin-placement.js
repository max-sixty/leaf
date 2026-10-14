import {
  visibleTargetParts
} from "./bundle-visible-target-parts.js";
import {
  pointBand,
  residencyStarted
} from "./bundle-content-layout.js";
import {
  anchorElement,
  anchorFor,
  anchorName,
  anchorReading,
  boundedBlockOf,
  carriedAnchor,
  cutFrames,
  nameAnchor,
  scrollAxes,
  scrollsWith
} from "./bundle-chrome.js";
import {
  afterPresentation,
  containingReadingRegionFor,
  effectiveScroller,
  moveScrollerBy,
  pageScroller,
  scrollLimit,
  scrollerFor,
  shownRegionBounds
} from "./bundle-presence.js";
import {
  inChrome,
  pageDocument
} from "./bundle-passage-facts.js";
import {
  LAYOUT,
  clamp,
  clippingAxes,
  overlaps,
  overlapsAcross,
  renderedChildren,
  scrollsContent,
  shellRight,
  shownBand,
  shownExtent,
  shownParts,
  shownRect,
  shownWindow,
  skipped,
  union
} from "./bundle-page-paint.js";
import {
  TAB_STOP,
  afterScript,
  atLayoutPrecision,
  cancelRender,
  keeps,
  layoutPx,
  move,
  nextRender,
  renderedParent,
  renderedUnder,
  shadowHost,
  sizeObserver,
  under,
  upFrom
} from "./bundle-sample-visibility.js";

// runtime/annotation-overlay/margin-placement.js
function rowPosture({
  railStands: railStands2,
  besideRail,
  blockRight,
  railInner,
  half,
  noted
}) {
  if (!railStands2 || !besideRail || noted) return "pin";
  return blockRight - half > railInner ? "pin" : "rail";
}
function packRows(rows2, gap, occupied = []) {
  const placed = [...occupied];
  const pushes2 = /* @__PURE__ */ new Map();
  const order = inSeatingOrder(rows2);
  for (const { key, rect, held: held2, pushed = 0 } of order) {
    const height = rect.bottom - rect.top;
    let top = rect.top + (held2 ? pushed : 0);
    const across = placed.filter((box) => overlapsAcross(box, rect)).sort((a, b) => a.top - b.top);
    for (const box of across)
      if (top < box.bottom + gap && top + height > box.top - gap)
        top = box.bottom + gap;
    pushes2.set(key, top - rect.top);
    placed.push({
      left: rect.left,
      right: rect.right,
      top,
      bottom: top + height
    });
  }
  return pushes2;
}
function arrivals(previous, rows2, pass2) {
  const next = /* @__PURE__ */ new Map();
  for (const { row, at } of rows2) {
    const first = previous.get(row) ?? previous.get(at) ?? pass2;
    next.set(row, first);
    if (at) next.set(at, first);
  }
  return next;
}
var inSeatingOrder = (rows2) => [...rows2].sort(
  (a, b) => Number(Boolean(b.held)) - Number(Boolean(a.held)) || (a.came ?? 0) - (b.came ?? 0) || a.rect.top - b.rect.top
);
function seatRows(pins, { gap, occupied = [] }) {
  const seats2 = /* @__PURE__ */ new Map();
  const seated = [...occupied];
  for (const pin of inSeatingOrder(pins)) {
    const fold = pin.folds;
    let folded2 = Boolean(fold && pin.folded);
    const foldWidth = fold && fold.seats[0].right - fold.seats[0].left;
    const foldBounds = fold && {
      ...pin.bounds,
      // Reserve the opened actions to the toggle's left. Where the whole group
      // cannot fit, keep at least its toggle inside the right edge.
      left: Math.min(
        pin.bounds.left + fold.open - foldWidth,
        pin.bounds.right - foldWidth
      )
    };
    const held2 = pin.held && {
      ...pin.held,
      left: folded2 ? pin.held.right - foldWidth : pin.held.left
    };
    const heldBounds = folded2 ? foldBounds : pin.bounds;
    let rect = held2 && inside(held2, heldBounds) ? held2 : null;
    const avoiding = [...pin.cover, ...seated];
    const lowered = (list) => [
      ...list.slice(0, pin.corner),
      slid(list[pin.corner], avoiding, gap, "down", pin.floor),
      ...list.slice(pin.corner + 1)
    ];
    if (!rect) {
      rect = pinSpot(lowered(pin.seats), avoiding, pin.bounds);
      folded2 = !rect && Boolean(fold);
      if (folded2) rect = pinSpot(lowered(fold.seats), avoiding, foldBounds);
    }
    const seatsNow = folded2 ? fold.seats : pin.seats;
    const boundsNow = folded2 ? foldBounds : pin.bounds;
    const pressed = [...pin.controls, ...seated];
    const corner = boundedHome(seatsNow[pin.corner], boundsNow);
    const aside = slid(corner, pressed, gap, "left", boundsNow.left);
    rect ??= leastCovering(seatsNow, pin.cover, pressed, boundsNow);
    if (!rect) {
      const push = packRows([{ key: pin.key, rect: corner }], gap, seated).get(pin.key);
      const below = { ...corner, top: corner.top + push, bottom: corner.bottom + push };
      const read = below.bottom <= pin.floor + gap + (corner.bottom - corner.top);
      rect = leastCovering(
        [aside, read && below].filter(Boolean),
        pin.cover,
        pressed,
        boundsNow
      ) ?? (inside(below, boundsNow) ? below : corner);
    }
    seats2.set(pin.key, { rect, folded: folded2 });
    seated.push(rect);
  }
  return seats2;
}
var inside = (rect, bounds) => rect.left >= bounds.left && rect.right <= bounds.right && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
function boundedHome(home, bounds) {
  const width = home.right - home.left;
  const height = home.bottom - home.top;
  const left = clamp(home.left, bounds.left, bounds.right - width);
  const top = clamp(home.top, bounds.top, bounds.bottom - height);
  return { left, right: left + width, top, bottom: top + height };
}
function leastCovering(seats2, cover, pressed, bounds) {
  const shared = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  let best = null;
  let least = Infinity;
  for (const seat of seats2) {
    if (!inside(seat, bounds) || pressed.some((box) => overlaps(box, seat))) continue;
    const covered = cover.reduce((sum, box) => sum + shared(box, seat), 0);
    if (covered < least) [best, least] = [seat, covered];
  }
  return best;
}
function slid(seat, boxes, gap, way, limit) {
  let rect = seat;
  for (let hit; hit = boxes.find((box) => overlaps(box, rect)); ) {
    const width = rect.right - rect.left;
    const height = rect.bottom - rect.top;
    rect = way === "left" ? { ...rect, left: hit.left - gap - width, right: hit.left - gap } : { ...rect, top: hit.bottom + gap, bottom: hit.bottom + gap + height };
    if (way === "left" ? rect.left < limit : rect.bottom > limit) return null;
  }
  return rect;
}
var pinSpot = (seats2, boxes, bounds) => seats2.find(
  (seat) => seat && inside(seat, bounds) && !boxes.some((box) => overlaps(box, seat))
) ?? null;

// runtime/annotation-overlay/margin-layout.js
var rows = /* @__PURE__ */ new Map();
var anchors = /* @__PURE__ */ new WeakMap();
var targetBox = (target) => shownParts(target)[0] ?? target;
var observedGeometry = /* @__PURE__ */ new Set();
var geometryObservation = 0;
var wantedGeometry = /* @__PURE__ */ new Set();
function watchGeometry(geometry) {
  wantedGeometry = geometry;
  if (geometryObservation) return;
  if (geometry.size === observedGeometry.size && [...geometry].every((node) => observedGeometry.has(node)))
    return;
  geometryObservation = nextRender(() => {
    geometryObservation = 0;
    for (const node of observedGeometry)
      if (!wantedGeometry.has(node)) layer.sizes.unobserve(node);
    for (const node of wantedGeometry)
      if (!observedGeometry.has(node)) layer.sizes.observe(node);
    observedGeometry = wantedGeometry;
  });
}
var GAP = 4;
var THREAD_CARD = "lf-margin-preview";
var HELD = `:hover, :focus-within, [data-lf-options-expanded], :has([aria-controls="${THREAD_CARD}"][aria-expanded="true"])`;
var pending = 0;
var observer = null;
var observedColumn = null;
var layer = null;
var carriers = /* @__PURE__ */ new Map();
var carrierAxes = /* @__PURE__ */ new WeakMap();
function carrierFor(anchor, axes, run) {
  let held2 = carriers.get(anchor);
  if (!held2) carriers.set(anchor, held2 = { xy: [], y: [] });
  if (!held2[axes][run]) {
    const carrier = document.createElement("div");
    carrier.className = "lf-ui lf-margin-carrier";
    carrierAxes.set(carrier, axes);
    held2[axes][run] = carrier;
  }
  return held2[axes][run];
}
var isCarrier = (node) => node?.classList.contains("lf-margin-carrier");
var laidOutScrollX = 0;
var standsBy = /* @__PURE__ */ new WeakMap();
function scrollSources(node) {
  const sources = [];
  for (let at = renderedParent(node); at && at !== pageScroller; at = renderedParent(at)) {
    if (scrollsContent(at)) sources.push(at);
  }
  return sources;
}
var stuckOrFixed = (node) => {
  for (let at = node; at instanceof Element; at = renderedParent(at))
    if (/^(sticky|fixed)$/.test(getComputedStyle(at).position)) return true;
  return false;
};
function carrierAnchor(subject, sources, scroller) {
  const inner = sources[0] ?? (scroller === pageScroller ? null : scroller);
  const own = () => anchorElement(targetBox(subject));
  if (!inner) return stuckOrFixed(subject) ? own() : null;
  if (!scrollsWith(subject, inner)) return own();
  return carriedAnchor(inner) ?? own();
}
var marginColumn = () => pageDocument() || document.body;
var railStands = (main) => (main.getAttribute("data-lf-margin") ?? "").split(" ").includes("rail");
var railBeside = (scroller) => {
  if (scroller === pageScroller) return true;
  const block = boundedBlockOf(scroller);
  return Boolean(block) && scrollerFor(upFrom(block)) === pageScroller;
};
var railMeasureRow = document.createElement("div");
railMeasureRow.className = "lf-margin-cluster";
railMeasureRow.dataset.lfPlace = "rail";
railMeasureRow.inert = true;
railMeasureRow.setAttribute("aria-hidden", "true");
railMeasureRow.style.visibility = "hidden";
var railMeasureEntry = document.createElement("button");
railMeasureEntry.className = "lf-margin-entry";
railMeasureEntry.type = "button";
railMeasureEntry.dataset.lfBehavior = "disclosure";
railMeasureRow.append(railMeasureEntry);
function restingRail() {
  for (const row2 of layer.root.parentElement.querySelectorAll(
    '.lf-margin-cluster[data-lf-place="rail"]'
  )) {
    if (!row2.checkVisibility()) continue;
    const children = [...row2.children].filter((child) => child.checkVisibility());
    if (children.length === 1 && children[0].matches(".lf-margin-entry"))
      return { entry: children[0].offsetWidth, row: row2.getBoundingClientRect().width };
  }
  const projection = layer.root.parentElement.cloneNode(false);
  projection.hidden = false;
  projection.inert = true;
  projection.setAttribute("aria-hidden", "true");
  const lane = layer.root.cloneNode(false);
  lane.append(railMeasureRow);
  projection.append(lane);
  layer.root.parentElement.after(projection);
  const entry = railMeasureEntry.offsetWidth;
  const row = railMeasureRow.getBoundingClientRect().width;
  projection.remove();
  return { entry, row };
}
function marginSpot(target, point = null) {
  for (const [row, options] of rows)
    if (options.anchor?.() === target && (options.point?.() ?? null) === point && row.checkVisibility()) {
      const { left: left2, right } = row.getBoundingClientRect();
      return { left: left2, right };
    }
  const main = marginColumn();
  if (!layer || !railStands(main) || !railBeside(scrollerFor(target))) return null;
  const hang = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--rail-hang")
  ) || 0;
  const left = main.getBoundingClientRect().right + hang;
  return { left, right: left + restingRail().row };
}
function syncMarginResidency(changed) {
  paintPins();
  if (changed) scheduleMarginLayout();
}
function paintPins() {
  if (!residencyStarted()) return;
  const main = pageDocument();
  layer?.root.closest(".lf-chrome").toggleAttribute("data-lf-pins", !main || !railStands(main));
}
var labelRect = (name, left, top, label) => ({
  name,
  rect: {
    left,
    right: left + label.width,
    top,
    bottom: top + label.height
  }
});
function placeMarginEntryLabel(control) {
  const label = control.querySelector(":scope > .lf-margin-entry-label");
  if (!label || !control.checkVisibility()) {
    keeps(control, "data-lf-label-side", null);
    return;
  }
  const marginEntryBox = control.getBoundingClientRect();
  const labelBox = label.getBoundingClientRect();
  const room = shownWindow({ gap: 4 });
  const edgeAligned = Math.max(
    room.left,
    Math.min(marginEntryBox.right - labelBox.width, room.right - labelBox.width)
  );
  const cluster = control.closest(".lf-margin-cluster") ?? control.parentElement;
  const clusterMarginEntries = [
    ...cluster?.querySelectorAll(".lf-margin-entry") ?? []
  ].filter((candidate) => candidate.checkVisibility()).map((candidate) => candidate.getBoundingClientRect());
  const clusterLeft = Math.min(...clusterMarginEntries.map((box) => box.left));
  const clusterRight = Math.max(...clusterMarginEntries.map((box) => box.right));
  const centered = (marginEntryBox.top + marginEntryBox.bottom - labelBox.height) / 2;
  const candidates = [
    labelRect("below", edgeAligned, marginEntryBox.bottom + 6, labelBox),
    labelRect("above", edgeAligned, marginEntryBox.top - 6 - labelBox.height, labelBox),
    labelRect("after", clusterRight + 6, centered, labelBox),
    labelRect("before", clusterLeft - 6 - labelBox.width, centered, labelBox)
  ];
  const blockers = [
    ...document.querySelectorAll(".lf-margin-projection .lf-margin-entry")
  ].filter((candidate) => candidate !== control && candidate.checkVisibility()).map((candidate) => candidate.getBoundingClientRect());
  const fits = ({ rect }) => rect.left >= room.left && rect.right <= room.right && rect.top >= room.top && rect.bottom <= room.bottom;
  const choice = candidates.find(
    (candidate) => fits(candidate) && !blockers.some((blocker) => overlaps(candidate.rect, blocker))
  ) ?? candidates.find(fits) ?? candidates[0];
  setStyle(
    label,
    "--lf-label-x",
    layoutPx(choice.rect.left - marginEntryBox.left - control.clientLeft)
  );
  setStyle(
    label,
    "--lf-label-y",
    layoutPx(choice.rect.top - marginEntryBox.top - control.clientTop)
  );
  keeps(control, "data-lf-label-side", choice.name);
}
var REVEALS_LABEL = ':is(:hover, [data-lf-focus]):not([aria-expanded="true"]), [data-lf-held-word]';
function heldLabelBoxes(row) {
  return [...row.querySelectorAll(".lf-margin-entry[data-lf-label-side]")].filter((control) => control.matches(REVEALS_LABEL)).map(
    (control) => control.querySelector(":scope > .lf-margin-entry-label").getBoundingClientRect()
  );
}
var labelPlacementFrame = 0;
function scheduleMarginEntryLabels() {
  if (labelPlacementFrame) return;
  labelPlacementFrame = nextRender(() => {
    labelPlacementFrame = 0;
    for (const control of document.querySelectorAll(
      `.lf-margin-projection .lf-margin-entry:is(${REVEALS_LABEL}, [data-lf-label-side])`
    )) {
      if (control.matches(REVEALS_LABEL)) placeMarginEntryLabel(control);
      else keeps(control, "data-lf-label-side", null);
    }
  });
}
function mountMarginLayer(root) {
  layer = { root, lanes: /* @__PURE__ */ new Map(), sizes: sizeObserver(layoutMarginRows) };
  paintPins();
  hearTargetChanges(document);
}
var heard = /* @__PURE__ */ new WeakSet();
function hearTargetChanges(root) {
  if (heard.has(root)) return;
  heard.add(root);
  root.addEventListener(LAYOUT, scheduleMarginLayout);
  root.addEventListener("slotchange", scheduleMarginLayout);
  new MutationObserver((records) => {
    if (records.some(
      (record) => !inChrome(record.target) && (record.type === "attributes" || record.type === "childList" && wantedGeometry.has(record.target))
    ))
      afterScript(layoutMarginRows);
    const moved = records.flatMap((record) => [...record.removedNodes, ...record.addedNodes]).filter((node) => node instanceof Element);
    for (const [row, options] of rows) {
      const target = options.anchor();
      const anchor = anchors.get(row);
      if (!moved.some((node) => under(target, node) || under(anchor, node))) continue;
      if (!target?.isConnected || anchor && !anchor.isConnected)
        row.classList.toggle("lf-withheld", true);
      scheduleMarginLayout();
    }
  }).observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class", "hidden", "open"]
  });
  root.addEventListener(
    "scroll",
    (event) => {
      const source = event.target === document ? pageScroller : event.target;
      if (!(source instanceof Element)) return;
      scrolled.add(source);
      scheduleScrollReading();
    },
    { capture: true, passive: true }
  );
}
var laneFrames = /* @__PURE__ */ new Map();
var makeLaneFrame = () => {
  const frame = document.createElement("div");
  frame.className = "lf-margin-lane";
  return frame;
};
function laneFor(scroller) {
  if (scroller === pageScroller) return layer.root;
  let lane = layer.lanes.get(scroller);
  if (!lane) {
    lane = makeLaneFrame();
    layer.root.after(lane);
    layer.lanes.set(scroller, lane);
    laneFrames.set(lane, [lane]);
    layer.sizes.observe(scroller);
  }
  return lane;
}
var EVERYWHERE = {
  left: -Infinity,
  top: -Infinity,
  right: Infinity,
  bottom: Infinity
};
function clippedBand(el, rect, bands, stop = pageScroller) {
  let { left, top, right, bottom } = rect;
  for (let at = renderedParent(el); at && at !== pageScroller && at !== stop; at = renderedParent(at)) {
    let band = bands.get(at);
    if (band === void 0) bands.set(at, band = shownBand(at));
    if (!band) continue;
    left = Math.max(left, band.left);
    top = Math.max(top, band.top);
    right = Math.min(right, band.right);
    bottom = Math.min(bottom, band.bottom);
  }
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}
function reach(anchor, box, main, reaches) {
  let right = box.right;
  for (let el = renderedParent(anchor); el && el !== main; el = renderedParent(el)) {
    let edge = reaches.get(el);
    if (edge === void 0) {
      const b = el.getBoundingClientRect();
      edge = {
        right: b.right,
        clip: getComputedStyle(el).overflowX === "visible" ? null : b.left + el.clientLeft + el.clientWidth
      };
      reaches.set(el, edge);
    }
    if (edge.clip !== null) right = Math.min(right, edge.clip);
    right = Math.max(right, edge.right);
  }
  return right;
}
function partsOf(target) {
  return shownParts(target).flatMap((part) => [...part.getClientRects()]).filter((box) => box.width && box.height);
}
var OPAQUE = "img, svg, canvas, video, iframe, object, embed";
function controlsIn(host) {
  const found = [];
  const visit = (el) => {
    for (const node of renderedChildren(el)) {
      if (node.nodeType !== Node.ELEMENT_NODE) continue;
      if (node.matches(TAB_STOP)) found.push(node);
      visit(node);
    }
  };
  visit(host);
  return found;
}
function coverIn(root, band, target, bands, stop) {
  const cover = [];
  const controls = [];
  const meets = (box) => box.bottom > band.top && box.top < band.bottom;
  const visit = (el) => {
    for (const node of renderedChildren(el)) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.data.trim()) continue;
        const words = document.createRange();
        words.selectNodeContents(node);
        for (const box2 of words.getClientRects()) {
          if (!meets(box2)) continue;
          const shown = clippedBand(node, box2, bands, stop);
          if (shown && shown.right - shown.left > 1 && shown.bottom - shown.top > 1)
            cover.push(shown);
        }
        continue;
      }
      if (node.nodeType !== Node.ELEMENT_NODE || node.closest(".lf-chrome")) continue;
      const box = node.getBoundingClientRect();
      const boxless = !box.width && !box.height;
      if (!boxless && !meets(box)) continue;
      const holds = node !== target && renderedUnder(target, node);
      const control = node.matches(TAB_STOP);
      if (!boxless && !holds && (node.shadowRoot || node.matches(OPAQUE) || control) && node.checkVisibility()) {
        const shown = clippedBand(node, box, bands, stop);
        if (shown) cover.push(shown);
        if (shown && control) controls.push(shown);
        for (const inner of node.shadowRoot ? controlsIn(node) : []) {
          if (!inner.checkVisibility()) continue;
          const part = clippedBand(inner, inner.getBoundingClientRect(), bands, stop);
          if (part) controls.push(part);
        }
        continue;
      }
      if (node instanceof SVGElement) continue;
      if (node.localName === "details" && !node.open) {
        const summary = node.querySelector(":scope > summary");
        if (summary) visit({ childNodes: [summary] });
        continue;
      }
      visit(node);
    }
  };
  visit(root);
  return { cover, controls };
}
function contentBox(scroller) {
  const box = scroller.getBoundingClientRect();
  const left = box.left + scroller.clientLeft - scroller.scrollLeft;
  const top = box.top + scroller.clientTop - scroller.scrollTop;
  return {
    left,
    top,
    right: left + Math.max(scroller.scrollWidth, scroller.clientWidth),
    bottom: top + Math.max(scroller.scrollHeight, scroller.clientHeight)
  };
}
var seats = /* @__PURE__ */ new WeakMap();
var folded = /* @__PURE__ */ new WeakSet();
var standsFolded = (row) => folded.has(row);
function standFolded(row, fold, on) {
  if (folded.has(row) === on) return;
  if (on) folded.add(row);
  else folded.delete(row);
  fold?.changed();
}
function pinSeating(rows2, { bands, shell, pinInset }) {
  const main = marginColumn();
  const rootBounds = /^(hidden|clip)$/.test(getComputedStyle(pageScroller).overflowY) ? shownWindow({ viewport: "layout" }) : { top: pageScroller.getBoundingClientRect().top };
  const pins = [];
  for (const entry of rows2) {
    const { read } = entry;
    if (read.place !== "pin") {
      seats.delete(read.row);
      standFolded(read.row, read.options.fold, false);
      continue;
    }
    const { target, point, row } = read;
    const home = entry.rect;
    const height = home.bottom - home.top;
    const width = home.right - home.left;
    const fold = read.options.fold?.able() ? read.options.fold : null;
    if (!fold) standFolded(row, read.options.fold, false);
    entry.fold = fold;
    const style = fold && getComputedStyle(row);
    const across = (count) => count * height + (count - 1) * parseFloat(style.columnGap) + parseFloat(style.paddingRight);
    const wide = fold ? across(2) : width;
    const parts = partsOf(point ?? target);
    const box = parts.length ? {
      right: Math.max(...parts.map((part) => part.right)),
      top: Math.min(...parts.map((part) => part.top))
    } : { right: home.right, top: home.top };
    const around = height + GAP;
    const band = {
      top: Math.min(home.top, box.top) - around,
      bottom: Math.max(home.bottom, ...parts.map((part) => part.bottom)) + around
    };
    const stop = read.scroller;
    const { cover, controls } = coverIn(
      stop === pageScroller ? main : stop,
      band,
      target,
      bands,
      stop
    );
    const end = parts.at(-1);
    const inline = !point && end && target instanceof HTMLElement && getComputedStyle(target).display.startsWith("inline");
    const floor = Math.max(home.bottom, ...parts.map((part) => part.bottom));
    const foot = parts.length ? Math.max(...parts.map((part) => part.bottom)) : home.bottom;
    const under2 = {
      left: Math.min(home.left, ...parts.map((part) => part.left)),
      right: home.right,
      top: foot + GAP,
      bottom: foot + GAP + height
    };
    const belowClear = !cover.some((box2) => overlaps(box2, under2));
    const seatsAt = (size) => [
      {
        left: box.right + GAP,
        right: box.right + GAP + size,
        top: box.top,
        bottom: box.top + height
      },
      ...inline ? [
        {
          left: end.right + GAP,
          right: end.right + GAP + size,
          top: end.top,
          bottom: end.top + height
        }
      ] : [],
      { ...home, left: home.right - size },
      {
        left: home.right - size,
        right: home.right,
        top: box.top - GAP - height,
        bottom: box.top - GAP
      },
      ...belowClear ? [{ ...under2, left: home.right - size }] : []
    ];
    const within = stop === pageScroller ? rootBounds : contentBox(stop);
    const clipped = clippedBand(target, EVERYWHERE, bands, stop);
    pins.push({
      key: entry,
      held: entry.holding ?? null,
      came: entry.came,
      seats: seatsAt(wide),
      corner: inline ? 2 : 1,
      floor,
      cover,
      controls,
      folds: fold && { seats: seatsAt(across(1)), open: across(fold.controls()) },
      folded: folded.has(row),
      bounds: {
        left: Math.max(within?.left ?? 0, clipped?.left ?? 0) + pinInset,
        right: Math.min(within?.right ?? shell, clipped?.right ?? shell) - pinInset,
        top: Math.max(within?.top ?? -Infinity, clipped?.top ?? -Infinity),
        bottom: Math.min(within?.bottom ?? Infinity, clipped?.bottom ?? Infinity)
      }
    });
  }
  const byEntry = new Map(pins.map((pin) => [pin.key, pin]));
  return (entry, occupied) => {
    const pin = byEntry.get(entry);
    const { rect, folded: on } = seatRows([pin], { gap: GAP, occupied }).get(entry);
    entry.visualLeft = on && entry.fold.open() ? rect.right - (entry.rect.right - entry.rect.left) : rect.left;
    entry.rect = rect;
    if (entry.fold) standFolded(entry.read.row, entry.fold, on);
    const attached = targetBox(entry.read.target).getBoundingClientRect();
    seats.set(entry.read.row, {
      top: rect.top - attached.top,
      right: attached.right - rect.right
    });
  };
}
function scheduleMarginLayout() {
  if (pending) return;
  pending = nextRender(layoutMarginRows);
}
function observeLayout() {
  const column = marginColumn();
  if (!observer) {
    observer = sizeObserver(layoutMarginRows);
    observer.observe(document.body);
  }
  if (observedColumn === column) return;
  if (observedColumn) observer.unobserve(observedColumn);
  observedColumn = column;
  observer.observe(observedColumn);
}
function registerMarginRow(row, options = {}) {
  rows.set(row, options);
  observeLayout();
  scheduleMarginLayout();
}
function unregisterMarginRow(row) {
  rows.delete(row);
  anchors.delete(row);
  if (row) {
    row.classList.toggle("lf-withheld", false);
    row.removeAttribute("data-lf-place");
    for (const property of ["--lf-margin-x", "--lf-margin-y"])
      setStyle(row, property, null);
    pushes.delete(row);
    folded.delete(row);
  }
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }
  scheduleMarginLayout();
}
function setStyle(row, property, value) {
  if (value === null) row.style.removeProperty(property);
  else row.style.setProperty(property, value);
}
function targetShown(target, extent, stands, bands) {
  const shown = (part) => part.checkVisibility() && clippedBand(part, part.getBoundingClientRect(), bands);
  if (!visibleTargetParts(target).some(shown)) return false;
  if (!clippedBand(target, extent, bands)) return false;
  if (!stands) return true;
  const view = clippedBand(target, EVERYWHERE, bands);
  return stands.top >= view.top - 1 && (stands.right === void 0 || stands.right <= view.right + 1);
}
var pushes = /* @__PURE__ */ new Map();
var pass = 0;
var came = /* @__PURE__ */ new Map();
var scrolled = /* @__PURE__ */ new Set();
var scrollReading = 0;
function scheduleScrollReading() {
  if (scrollReading) return;
  scrollReading = nextRender(() => {
    scrollReading = 0;
    const boxes = [...scrolled];
    scrolled.clear();
    if (boxes.includes(pageScroller) && scrollX !== laidOutScrollX && [...carriers.values()].some((held2) => held2.y.length)) {
      scheduleMarginLayout();
      return;
    }
    const bands = /* @__PURE__ */ new Map();
    for (const [row, options] of rows) {
      const target = options.anchor();
      if (!target?.isConnected) continue;
      const moving = boxes.some((box) => {
        for (let at = target; at; at = renderedParent(at)) if (at === box) return true;
        return false;
      });
      if (!moving) continue;
      if (!row.classList.contains("lf-withheld") && boxes.every((box) => box === pageScroller))
        continue;
      const extent = shownExtent(target);
      const by = standsBy.get(row);
      const stands = row.classList.contains("lf-withheld") || !extent || !by ? null : row.dataset.lfPlace === "pin" ? { top: extent.top + by.top, right: extent.right + by.right } : { top: extent.top + by.top };
      if (targetShown(target, extent, stands, bands) === row.classList.contains("lf-withheld")) {
        scheduleMarginLayout();
        return;
      }
    }
  });
}
function layoutMarginRows() {
  cancelRender(pending);
  pending = 0;
  if (!layer) return;
  pass += 1;
  laidOutScrollX = scrollX;
  const present = [];
  const main = marginColumn();
  const columnRect = main.getBoundingClientRect();
  const columnHeight = main.scrollHeight;
  const shell = shellRight();
  const stands = railStands(main);
  const rootStyle = getComputedStyle(document.documentElement);
  const hang = parseFloat(rootStyle.getPropertyValue("--rail-hang")) || 0;
  const pinInset = parseFloat(rootStyle.getPropertyValue("--pin-inset")) || 0;
  const railInner = columnRect.right + hang;
  let railEntry;
  const railEntrySize = () => railEntry ??= layer.root.parentElement.querySelector(
    '.lf-margin-cluster:not([data-lf-place="pin"]) .lf-margin-entry:not([hidden])'
  )?.offsetWidth || restingRail().entry;
  const notes = [...main.querySelectorAll("aside.sidenote")].filter((note) => !skipped(note)).map((note) => note.getBoundingClientRect()).filter((note) => note.width && note.left >= columnRect.right - 1);
  const bands = /* @__PURE__ */ new Map();
  const reaches = /* @__PURE__ */ new Map();
  const reads = [];
  const geometry = /* @__PURE__ */ new Set();
  const parents = /* @__PURE__ */ new Set();
  function observeGeometry(target) {
    for (let at = target; at && at !== pageScroller; at = renderedParent(at)) {
      if (at instanceof Element) {
        geometry.add(at);
        const root = at.getRootNode();
        if (shadowHost(root)) hearTargetChanges(root);
      }
      const parent = at.parentNode;
      if (!parent || parents.has(parent)) continue;
      parents.add(parent);
      for (const sibling of parent.children ?? [])
        if (!inChrome(sibling)) geometry.add(sibling);
    }
  }
  const carrierNames = /* @__PURE__ */ new Map();
  for (const [row, options] of rows) {
    const target = options.anchor();
    if (!target?.isConnected) {
      present.push({ row, at: null });
      reads.push({ row, options, lane: layer.root, shown: false });
      continue;
    }
    if (skipped(target)) {
      present.push({ row, at: null });
      const home = row.parentElement ?? layer.root;
      reads.push({
        row,
        options,
        lane: isCarrier(home) ? home.parentElement : home,
        home,
        shown: false
      });
      continue;
    }
    const anchor = targetBox(target);
    anchors.set(row, anchor);
    const point = options.point?.() ?? null;
    observeGeometry(point ?? target);
    present.push({ row, at: point ?? target });
    const scroller = scrollerFor(target);
    const rootLane = scroller === pageScroller;
    const box = anchor.getBoundingClientRect();
    const whole = shownExtent(target);
    const extent = whole && clippedBand(target, whole, bands, scroller);
    const top = extent && point ? pointBand(extent, point).top : extent?.top;
    const level = point ? top : box.top;
    const besideRail = railBeside(scroller);
    const size = stands && besideRail ? railEntrySize() : 0;
    const place = rowPosture({
      railStands: stands,
      besideRail,
      blockRight: reach(anchor, box, main, reaches),
      railInner,
      half: size / 2,
      noted: notes.some((note) => note.top < level + size && note.bottom > level)
    });
    const shown = targetShown(target, extent, place === "pin" ? null : { top }, bands);
    reads.push({
      row,
      options,
      target,
      point,
      anchor,
      whole,
      scroller,
      lane: rootLane ? layer.root : null,
      shown,
      place,
      box,
      extent,
      top
    });
  }
  came = arrivals(came, present, pass);
  for (const { row, target, shown, place } of reads) {
    row.classList.toggle("lf-withheld", !shown);
    if (!target) continue;
    if (row.dataset.lfPlace !== place) {
      pushes.delete(row);
      row.dataset.lfPlace = place;
    }
  }
  const placed = reads.filter((read) => read.shown).map((read) => {
    const box = read.row.getBoundingClientRect();
    return {
      key: read.row,
      rect: {
        left: read.place === "pin" ? read.extent.right - pinInset - box.width : railInner,
        right: read.place === "pin" ? read.extent.right - pinInset : railInner + box.width,
        top: read.top,
        bottom: read.top + box.height
      },
      // Held where it stands, which a row has only once it has stood in its posture:
      // one that has just come, or just changed posture, takes its place as any other.
      held: pushes.has(read.row) && read.row.matches(HELD),
      came: came.get(read.row),
      pushed: pushes.get(read.row),
      read
    };
  });
  for (const entry of placed) {
    const seat = seats.get(entry.read.row);
    if (entry.read.place !== "pin" || !seat || !entry.held) continue;
    const heldBox = targetBox(entry.read.target).getBoundingClientRect();
    const width = entry.rect.right - entry.rect.left;
    const height = entry.rect.bottom - entry.rect.top;
    entry.holding = {
      left: heldBox.right - seat.right - width,
      right: heldBox.right - seat.right,
      top: heldBox.top + seat.top,
      bottom: heldBox.top + seat.top + height
    };
  }
  const seatPin = pinSeating(placed, { bands, shell, pinInset });
  const occupied = [];
  const packed = /* @__PURE__ */ new Map();
  for (const entry of inSeatingOrder(placed)) {
    if (entry.read.place === "rail") {
      entry.step = Math.min(0, shell - entry.rect.right);
      const rect = {
        ...entry.rect,
        left: entry.rect.left + entry.step,
        right: entry.rect.right + entry.step
      };
      const push = packRows([{ ...entry, rect }], GAP, occupied).get(entry.key);
      packed.set(entry.key, push);
      occupied.push({ ...rect, top: rect.top + push, bottom: rect.bottom + push });
    } else {
      seatPin(entry, occupied);
      packed.set(entry.key, 0);
      occupied.push(entry.rect);
    }
    if (entry.held) occupied.push(...heldLabelBoxes(entry.read.row));
  }
  for (const read of reads) {
    if (!read.target) continue;
    const subject = read.point ?? read.target;
    read.carrier = carrierAnchor(subject, scrollSources(subject), read.scroller);
    read.carrierBox = read.carrier?.getBoundingClientRect();
    read.lane = read.scroller === pageScroller ? layer.root : null;
    if (read.carrier && !carrierNames.has(read.carrier))
      carrierNames.set(read.carrier, anchorReading(read.carrier));
  }
  const regions = /* @__PURE__ */ new Map();
  const ring = 6;
  for (const read of reads)
    if (read.scroller && read.scroller !== pageScroller && !regions.has(read.scroller)) {
      const holders = [read.scroller, ...scrollSources(read.scroller)];
      const rail = stands && railBeside(read.scroller);
      const levels = holders.map((holder, i) => {
        const band = clippedBand(
          holder,
          shownBand(holder) ?? holder.getBoundingClientRect(),
          bands,
          holders[i + 1]
        );
        const anchor = anchorElement(holder);
        const axes = i ? clippingAxes(getComputedStyle(holder)) : { x: true, y: true };
        return {
          anchor,
          reading: anchorReading(anchor),
          at: anchor.getBoundingClientRect(),
          band: !band ? null : i ? band : {
            ...band,
            left: band.left - ring,
            right: (rail ? shell : band.right) + ring
          },
          axes: rail ? { ...axes, x: false } : axes
        };
      }).reverse();
      if (rail) levels.at(-1).axes = { x: true, y: true };
      regions.set(read.scroller, levels);
    }
  watchGeometry(geometry);
  for (const read of reads) read.lane ??= laneFor(read.scroller);
  const byLane = /* @__PURE__ */ new Map();
  for (const read of [...reads].sort(
    (a, b) => (a.options.order ?? 0) - (b.options.order ?? 0)
  ))
    byLane.set(read.lane, [...byLane.get(read.lane) ?? [], read]);
  for (const [scroller, lane] of layer.lanes) {
    const levels = regions.get(scroller);
    if (!levels) continue;
    for (const { reading } of levels) nameAnchor(reading);
    const hidden = { left: 0, top: 0, right: 0, bottom: 0 };
    laneFrames.set(
      lane,
      cutFrames(
        levels.map((level) => ({ ...level, band: level.band ?? hidden })),
        laneFrames.get(lane),
        makeLaneFrame
      )
    );
  }
  let lastLane = layer.root;
  for (const [lane, members] of byLane) {
    if (lane !== layer.root) {
      const [root] = laneFrames.get(lane);
      if (lastLane.nextElementSibling !== root)
        move(lastLane.parentNode, root, lastLane.nextSibling);
      lastLane = root;
    }
    const cursors = /* @__PURE__ */ new Map([[lane, lane.firstElementChild]]);
    const runs = /* @__PURE__ */ new Map();
    let previous = null;
    for (const read of members) {
      const { row } = read;
      if (read.target) {
        const axes = read.place === "rail" ? "y" : "xy";
        if (!read.carrier) read.home = lane;
        else if (previous?.carrier === read.carrier && previous.axes === axes)
          read.home = previous.home;
        else {
          const key = carrierFor(read.carrier, axes, 0);
          const run = runs.get(key) ?? 0;
          runs.set(key, run + 1);
          read.home = carrierFor(read.carrier, axes, run);
        }
        read.axes = axes;
      }
      previous = read;
      const home = read.home ?? lane;
      if (home !== lane && !cursors.has(home)) {
        let at = cursors.get(lane);
        if (at && at.parentElement !== lane) at = null;
        if (at === home) cursors.set(lane, home.nextElementSibling);
        else move(lane, home, at);
        cursors.set(home, home.firstElementChild);
      }
      let before = cursors.get(home);
      if (before && before.parentElement !== home) before = null;
      if (before === row) {
        cursors.set(home, row.nextElementSibling);
        continue;
      }
      move(home, row, before);
      cursors.set(home, before);
    }
  }
  for (const [anchor, held2] of carriers) {
    for (const axes of ["xy", "y"])
      held2[axes] = held2[axes].filter((carrier) => {
        if (carrier.isConnected && carrier.childElementCount) return true;
        carrier.remove();
        return false;
      });
    if (!held2.xy.length && !held2.y.length) carriers.delete(anchor);
  }
  for (const [scroller, lane] of layer.lanes)
    if (!byLane.has(lane)) {
      laneFrames.get(lane)[0].remove();
      laneFrames.delete(lane);
      layer.lanes.delete(scroller);
      layer.sizes.unobserve(scroller);
    }
  for (const row of pushes.keys()) if (!packed.has(row)) pushes.delete(row);
  for (const { key: row, rect, read, visualLeft, step = 0 } of placed) {
    const push = packed.get(row) ?? 0;
    pushes.set(row, push);
    if (read.place === "pin")
      row.classList.toggle(
        "lf-withheld",
        !targetShown(
          read.target,
          read.extent,
          { top: rect.top + push, right: rect.right },
          bands
        )
      );
    const left = (visualLeft ?? rect.left) + step;
    const top = rect.top + push;
    standsBy.set(row, {
      top: top - read.whole.top,
      right: rect.right - read.whole.right
    });
    if (isCarrier(read.home)) {
      const carrier = read.home;
      const from = (side, at) => `calc(anchor(${side}, -9999px) - ${layoutPx(at)})`;
      const reading = carrierNames.get(read.carrier);
      if (reading.write) {
        nameAnchor(reading);
        reading.write = null;
      }
      setStyle(carrier, "position-anchor", reading.name);
      setStyle(carrier, "top", from("top", read.carrierBox.top));
      setStyle(
        carrier,
        "left",
        carrierAxes.get(carrier) === "xy" ? from("left", read.carrierBox.left) : "0px"
      );
      setStyle(row, "--lf-margin-x", layoutPx(left));
      setStyle(row, "--lf-margin-y", layoutPx(top));
      continue;
    }
    setStyle(row, "--lf-margin-x", layoutPx(left + scrollX));
    setStyle(row, "--lf-margin-y", layoutPx(top + scrollY));
  }
  document.dispatchEvent(
    new CustomEvent("lf-margin-layout", {
      detail: { column: columnRect, height: columnHeight }
    })
  );
}

// runtime/annotation-overlay/floating.js
var floatingUiModule = null;
var floatingUi = () => floatingUiModule ??= import("/vendor/floating-ui.esm.js");
afterPresentation(floatingUi);
async function positioningScale({ elements, platform, strategy }) {
  const unit = await platform.convertOffsetParentRelativeRectToViewportRelativeRect({
    elements,
    offsetParent: await platform.getOffsetParent(elements.floating),
    strategy,
    rect: { x: 0, y: 0, width: 1, height: 1 }
  });
  return { x: unit.width, y: unit.height };
}
var anchorAt = (reference) => ({
  name: "anchorAt",
  async fn(state) {
    const { rects, elements, platform } = state;
    if (await platform.getOffsetParent(elements.floating) !== window)
      return { data: { offset: null } };
    const client = reference.getBoundingClientRect();
    const scale = await positioningScale(state);
    return {
      data: {
        scale,
        offset: {
          x: rects.reference.x - client.left / scale.x,
          y: rects.reference.y - client.top / scale.y
        }
      }
    };
  }
});
function holderOf({ edge, at }, context, overflowAncestors) {
  const candidates = overflowAncestors.filter(
    (source) => source instanceof Element && source !== document.scrollingElement
  );
  for (let region = containingReadingRegionFor(context); region; region = upFrom(region.host) && containingReadingRegionFor(upFrom(region.host)))
    if (!candidates.includes(region.body)) candidates.push(region.body);
  return candidates.find(
    (box) => [box.getBoundingClientRect(), shownBand(box)].some(
      (rect) => rect && Math.abs(rect[edge] - at) < 1
    )
  ) ?? null;
}
var held = {
  name: "held",
  async fn(state) {
    const { placement, rects, middlewareData, elements, platform } = state;
    const [side, alignment] = placement.split("-");
    const aligned = (start, end) => alignment === "end" ? end : start;
    const edges = side === "top" || side === "bottom" ? { x: aligned("left", "right"), y: side === "top" ? "bottom" : "top" } : { x: side === "left" ? "right" : "left", y: aligned("top", "bottom") };
    edges.y = middlewareData.hold?.edge ?? edges.y;
    edges.x = middlewareData.hold?.inline ?? edges.x;
    const shifted = middlewareData.shift ?? {};
    if (Math.abs(shifted.x ?? 0) >= 0.5) edges.x = shifted.x < 0 ? "right" : "left";
    if (Math.abs(shifted.y ?? 0) >= 0.5) edges.y = shifted.y < 0 ? "bottom" : "top";
    const parent = await platform.getOffsetParent(elements.floating);
    const block = parent === window ? document.documentElement : parent;
    const scale = await positioningScale(state);
    const blockScale = parent === window ? { x: 1, y: 1 } : await platform.getScale(parent);
    return {
      data: {
        edges,
        width: rects.floating.width,
        height: rects.floating.height,
        block: {
          width: block.clientWidth * blockScale.x / scale.x,
          height: block.clientHeight * blockScale.y / scale.y
        }
      }
    };
  }
};
var INSETS = ["left", "right", "top", "bottom"];
var stood = /* @__PURE__ */ new Map();
var floatingSelections = () => [...stood.values()];
var physicalContext = (context) => context instanceof Element ? context : context?.parentElement;
function floatingGeometry(contexts) {
  const anchors2 = /* @__PURE__ */ new Map();
  for (const context of contexts) {
    const anchor = anchorFor(context);
    if (anchor) anchors2.set(anchor, anchor.getBoundingClientRect());
  }
  return { anchors: anchors2 };
}
function floatingPlacement({ floating, update }) {
  let epoch = 0;
  let watched = null;
  let observer2 = null;
  let tenure = Object.freeze({});
  let stopWatching = null;
  let lastAnchorStand = null;
  const inset = (insets) => {
    for (const edge of INSETS)
      if (insets[edge] === void 0) floating.style.removeProperty(edge);
      else floating.style.setProperty(edge, insets[edge]);
  };
  const placedAt = ({ x, y, middlewareData }) => {
    lastAnchorStand = null;
    const { edges, width, height, block } = middlewareData.held;
    floating.style.removeProperty("position-anchor");
    inset({
      [edges.x]: layoutPx(edges.x === "left" ? x : block.width - x - width),
      [edges.y]: layoutPx(edges.y === "top" ? y : block.height - y - height)
    });
  };
  const anchoredAt = (anchor, at) => ({ x, y, middlewareData }) => {
    const { edges, width, height, block } = middlewareData.held;
    const lengthX = atLayoutPrecision(
      edges.x === "left" ? x - at.x : at.x - x - width
    );
    const lengthY = atLayoutPrecision(
      edges.y === "top" ? y - at.y : at.y - y - height
    );
    if (lastAnchorStand?.anchor === anchor && lastAnchorStand.edgeX === edges.x && lastAnchorStand.edgeY === edges.y && lastAnchorStand.lengthX === lengthX && lastAnchorStand.lengthY === lengthY)
      return;
    const from = (side, length, fallback) => `calc(anchor(${side}, ${layoutPx(fallback)}) + ${layoutPx(length)})`;
    floating.style.positionAnchor = anchorName(anchor);
    inset({
      [edges.x]: from(
        "left",
        lengthX,
        edges.x === "left" ? at.x : block.width - at.x
      ),
      [edges.y]: from("top", lengthY, edges.y === "top" ? at.y : block.height - at.y)
    });
    lastAnchorStand = {
      anchor,
      edgeX: edges.x,
      edgeY: edges.y,
      lengthX,
      lengthY
    };
  };
  let stand = placedAt;
  let placementProof = null;
  let stopScrollInvalidation = null;
  return {
    // `reference` is what `computePosition` receives; `element` is the node it stands
    // for; `autoUpdate` declares which mechanical changes invalidate its placement.
    watch(element, reference, autoUpdate) {
      if (element === watched && autoUpdate === observer2) return;
      stopWatching?.();
      watched = element;
      observer2 = autoUpdate;
      tenure = Object.freeze({});
      const stopGeometry = autoUpdate(reference, floating, update);
      let visible = visibleTargetParts(element).length > 0;
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
          childList: parts
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
    current: (placement) => placement === epoch,
    // Computes the answer, in the window's positioning space, and the constraint
    // `planeOf` reads as binding it: `"page"`, `"window"`, or the edge that holds it in
    // (`{edge, at}`), whose holder names the plane. `beside` is the element the box
    // stands beside in the page's plane. `stand` then writes that answer's spot in its
    // plane. An answer a later placement superseded while it was computed is null, and
    // writes nothing.
    async position(computePosition, reference, options, planeOf, beside) {
      const placement = epoch;
      const context = reference.contextNode ?? beside;
      const physical = physicalContext(context);
      const anchor = anchorFor(context);
      const client = reference.getBoundingClientRect();
      const geometry = reference.geometry ?? floatingGeometry([context]);
      const anchorBox = geometry.anchors.get(anchor);
      const { getOverflowAncestors } = await floatingUi();
      if (placement !== epoch) return null;
      const measured = {
        contextElement: reference.contextElement ?? beside,
        getBoundingClientRect: () => client
      };
      const answer = await computePosition(measured, floating, {
        ...options,
        strategy: "fixed",
        middleware: [...options.middleware, held, anchorAt(measured)]
      });
      if (placement !== epoch) return null;
      const { offset, scale } = answer.middlewareData.anchorAt;
      const wanted = planeOf(answer);
      const holder = offset && physical && typeof wanted === "object" ? holderOf(wanted, physical, getOverflowAncestors(physical)) : null;
      const plane = wanted === "page" && anchorBox && offset ? "page" : holder ? "region" : "window";
      const frameAnchor = plane === "page" ? anchor : plane === "region" ? anchorElement(holder) : null;
      const frameBox = plane === "page" ? anchorBox : frameAnchor?.getBoundingClientRect();
      const at = offset && {
        x: offset.x + (frameBox?.left ?? 0) / scale.x,
        y: offset.y + (frameBox?.top ?? 0) / scale.y
      };
      keeps(floating, "data-lf-plane", plane);
      stopScrollInvalidation?.();
      stopScrollInvalidation = null;
      if (plane !== "page") {
        const sources = context ? [...new Set(getOverflowAncestors(context))] : [];
        for (const source of sources)
          source.addEventListener("scroll", update, { passive: true });
        stopScrollInvalidation = () => {
          for (const source of sources) source.removeEventListener("scroll", update);
        };
      }
      stand = frameAnchor ? anchoredAt(frameAnchor, at) : placedAt;
      placementProof = at ? {
        subject: watched,
        anchor,
        frame: frameAnchor,
        plane,
        at
      } : null;
      return answer;
    },
    stand(answer) {
      stand(answer);
      if (!placementProof) {
        stood.delete(floating);
        tenure = Object.freeze({});
        return;
      }
      const { edges, width, height, block } = answer.middlewareData.held;
      const { offset, scale } = answer.middlewareData.anchorAt;
      const { subject, anchor, frame: frameAnchor, plane, at } = placementProof;
      const point = {};
      for (const [axis, start, coordinate, length, extent] of [
        ["left", "left", "x", width, block.width],
        ["top", "top", "y", height, block.height]
      ]) {
        const fromStart = edges[coordinate] === start;
        const spot = answer[coordinate];
        point[axis] = frameAnchor ? fromStart ? atLayoutPrecision(spot - at[coordinate]) : -atLayoutPrecision(at[coordinate] - spot - length) : fromStart ? atLayoutPrecision(spot) : extent - atLayoutPrecision(extent - spot - length);
        point[axis] = (point[axis] - (frameAnchor ? 0 : offset[coordinate])) * scale[coordinate];
      }
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
          size: Object.freeze({ width: width * scale.x, height: height * scale.y })
        })
      );
    },
    // Where an answer stands the box, in client coordinates, from the measurement it was
    // solved against rather than read off the box, which may not yet be laid out
    // where a scroll the browser carried it through has put it.
    clientBox(answer) {
      const { offset, scale } = answer.middlewareData.anchorAt;
      const { width, height } = answer.middlewareData.held;
      return offset ? new DOMRect(
        (answer.x - offset.x) * scale.x,
        (answer.y - offset.y) * scale.y,
        width * scale.x,
        height * scale.y
      ) : floating.getBoundingClientRect();
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
      observer2 = null;
      tenure = Object.freeze({});
      placementProof = null;
      stood.delete(floating);
      delete floating.dataset.lfPlane;
      for (const property of ["position-anchor", ...INSETS])
        floating.style.removeProperty(property);
    }
  };
}

// runtime/annotation-overlay/comment-placement.js
function commentAttachment({
  target,
  point = null,
  passage = null,
  boundary = null
}) {
  if (!target) {
    const element2 = document.documentElement;
    const extent2 = boundary ?? commentBoundary();
    return {
      element: element2,
      contextNode: element2,
      geometry: floatingGeometry([element2]),
      clear: null,
      extent: extent2,
      row: extent2.top,
      lastRow: extent2.top,
      column: null,
      margin: null,
      region: null,
      scroller: effectiveScroller(element2)
    };
  }
  if (!visibleTargetParts(target).length) return null;
  const margin = marginSpot(target, point);
  const context = point ?? passage?.contextNode ?? target;
  const element = point ?? target;
  const geometry = floatingGeometry([element, context]);
  const clips = /* @__PURE__ */ new Map();
  const shown = union(
    shownParts(target).map((part) => shownRect(part, clips)).filter(Boolean)
  );
  const whole = shownExtent(target) ?? target.getBoundingClientRect();
  const extent = point ? pointBand(whole, point) : whole;
  const clear = point ? extent : shown ?? whole;
  const region = containingReadingRegionFor(element);
  return {
    element,
    contextNode: context,
    geometry,
    clear,
    extent,
    row: (passage?.attachment ?? extent).top,
    lastRow: passage?.attachment ? passage.attachment.top : extent.bottom,
    column: passage?.attachment?.left ?? null,
    margin,
    region,
    scroller: effectiveScroller(region ?? element)
  };
}
function commentReference(place, reference) {
  return {
    contextElement: place.element,
    contextNode: place.contextNode,
    geometry: place.geometry,
    getBoundingClientRect: () => reference
  };
}
var COMMENT_GAP = 8;
var LEAST_HEIGHT = 96;
function commentBoundary({ region = null, right = Infinity } = {}) {
  const shown = (within) => shownWindow({ within, gap: COMMENT_GAP });
  const bounds = region && shownRegionBounds(region);
  const inRegion = bounds && shown(bounds);
  if (inRegion && Math.ceil(inRegion.width) >= Math.ceil(cardMinimum()) && inRegion.height >= LEAST_HEIGHT) {
    const whole = region.body.getBoundingClientRect();
    return Object.assign(inRegion, {
      inRegion: bounds,
      key: [
        whole.width,
        whole.height,
        window.visualViewport.width,
        window.visualViewport.height
      ]
    });
  }
  const shell = shown({ right: Math.min(shellRight(), right) });
  return Object.assign(shell, {
    inRegion: null,
    key: [shell.left, shell.top, shell.right, shell.bottom]
  });
}
var vertical = (side) => side === "top" || side === "bottom";
function roomTravel(side, scroller) {
  const projection = scrollAxes(scroller).y.y;
  const direction = side === "top" ? -1 : 1;
  const localDirection = direction * Math.sign(projection);
  const local = localDirection < 0 ? scroller.scrollTop : Math.max(0, scrollLimit(scroller) - scroller.scrollTop);
  return { projection, direction, available: local * Math.abs(projection) };
}
function reachableRoom(side, extent, boundary, scroller) {
  const shown = side === "top" ? extent.top - boundary.top - COMMENT_GAP : boundary.bottom - extent.bottom - COMMENT_GAP;
  const { available: travel } = roomTravel(side, scroller);
  return {
    shown,
    reachable: Math.max(
      0,
      Math.min(boundary.height - extent.height - COMMENT_GAP, shown + travel)
    )
  };
}
function makeRoom(side, clear, extent, height, boundary, scroller) {
  if (extent.height + COMMENT_GAP + height > boundary.height) return false;
  const overflow = side === "top" ? boundary.top - (clear.top - COMMENT_GAP - height) : clear.bottom + COMMENT_GAP + height - boundary.bottom;
  const { available: travel, projection, direction } = roomTravel(side, scroller);
  const movement = Math.max(0, Math.min(overflow, travel));
  if (movement <= 0.5) return false;
  const before = scroller.scrollTop;
  moveScrollerBy(scroller, direction * movement / projection);
  return Math.abs((scroller.scrollTop - before) * projection) > 0.5;
}
function commentSide({ clear, extent, boundary, width, scroller, coarse }) {
  const fits = (room) => Math.ceil(room) >= Math.ceil(width);
  if (fits(boundary.right - clear.right - COMMENT_GAP)) return "right";
  if (fits(clear.left - boundary.left - COMMENT_GAP)) return "left";
  const below = reachableRoom("bottom", extent, boundary, scroller);
  const above = reachableRoom("top", extent, boundary, scroller);
  const fitsBelow = below.shown >= LEAST_HEIGHT;
  const fitsAbove = above.shown >= LEAST_HEIGHT;
  if (fitsBelow !== fitsAbove) return fitsBelow ? "bottom" : "top";
  if (coarse && below.reachable >= LEAST_HEIGHT) return "bottom";
  return below.reachable > above.reachable || below.reachable === above.reachable && below.shown > above.shown ? "bottom" : "top";
}
var rootLength = (name) => parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
var cardMinimum = () => rootLength("--thread-card-min");
var cardMeasure = () => rootLength("--thread-card");
function commentPlacement() {
  let side = null;
  let inline = null;
  let input = null;
  let pending2 = null;
  let carriedInline = null;
  let initialHold = null;
  let quoted = false;
  let moved = false;
  let held2 = null;
  let reading = null;
  let edge = "top";
  let pressHeld = null;
  let pressAnswered = null;
  const forget = () => {
    side = null;
    inline = null;
    input = null;
    pending2 = null;
    carriedInline = null;
    initialHold = null;
    moved = false;
    held2 = null;
    reading = null;
    edge = "top";
    pressHeld = null;
    pressAnswered = null;
  };
  const line = (clear, row) => quoted ? row : side === "bottom" ? clear?.bottom ?? row : side === "top" ? clear?.top ?? row : row;
  return {
    get side() {
      return side;
    },
    // Mechanical handoff between the editor's transparent frame and its sent card.
    capture() {
      return { side, boundary: input?.slice(1, 5) ?? null, moved };
    },
    adopt(frame) {
      forget();
      pending2 = frame;
    },
    forget,
    // Which edge this placement holds, `top` or `foot`, from what the caller reports:
    // the transcript's extent, whether the user is drafting, the latest turn
    // (`{ key, author }`), the draft's words, and, while it is the user's latest
    // input, their press in the surface (`{ input, moved }`: which input it was, and
    // whether what it changed stands above the spot pressed). `fresh` and `hold` are
    // `choose`'s.
    holding({
      fresh,
      hold,
      transcript,
      drafting,
      latest = null,
      draftText = "",
      pressed = null
    }) {
      if (hold) held2 = { ...hold, transcript };
      if (fresh) held2 = null;
      const turned = held2 && Math.abs(transcript - held2.transcript) > 0.5;
      const own = Boolean(pressed) && pressAnswered?.input === pressed.input;
      const answered = own && Math.abs(transcript - pressAnswered.transcript) <= 0.5;
      if (!pressed || turned && own && !answered) pressHeld = null;
      else if (turned && !own && side !== "top") {
        pressHeld = pressed.moved ? "foot" : "top";
        pressAnswered = { input: pressed.input, transcript };
      }
      const newDraft = drafting && !held2?.drafting;
      const continuedDraft = drafting && draftText && draftText !== held2?.draftText;
      const keepReplyLine = Boolean(
        latest && !newDraft && !continuedDraft && (held2?.replyTurn && held2.replyTurn === latest.key || turned && (drafting || held2?.drafting && latest.author === "user"))
      );
      reading = {
        transcript,
        drafting,
        replyTurn: keepReplyLine ? latest.key : null,
        draftText
      };
      edge = hold ? "top" : pressHeld ?? (keepReplyLine || !drafting && side === "top" ? "foot" : "top");
      return edge;
    },
    // The edge a change the user did not make would hold, read before it is drawn: a
    // turn joining while they read releases a hold on their own reply's line, so it
    // holds the foot only where the surface stands above what it is about; any other
    // change keeps the edge held now.
    edgeFor: (turn) => turn ? side === "top" ? "foot" : "top" : edge,
    // The held edge's offset for `options`' `hold`, and the height between the held
    // top and foot, which caps a held surface no shorter than it last stood.
    heldAt: (edge2) => held2 && { [edge2]: held2[edge2] },
    heldHeight: () => held2 ? held2.foot - held2.top : 0,
    scrolled() {
      input = null;
    },
    line,
    choose({
      clear,
      extent = clear,
      boundary,
      row = clear?.top ?? boundary.top,
      column = null,
      scroller,
      coarse
    }) {
      quoted = column !== null;
      const unanchored = !clear;
      extent ??= boundary;
      const key = [Number(unanchored), ...boundary.key, extent.left, extent.right];
      const frame = pending2;
      pending2 = null;
      const adopted = frame?.placement.boundary && key.slice(1, 5).every(
        (value, index) => Math.abs(value - frame.placement.boundary[index]) <= 0.5
      );
      if (adopted) {
        ({ side, moved } = frame.placement);
        if (side !== "left" || moved)
          carriedInline = frame.box.left - (column ?? clear?.left ?? boundary.left);
        const top = frame.box.top - line(clear, row);
        initialHold = { top, foot: top + frame.box.height };
      } else if (input && key.some((value, index) => Math.abs(value - input[index]) > 0.5)) {
        forget();
      }
      input = key;
      const fresh = side === null;
      side ??= unanchored ? "bottom" : commentSide({
        clear,
        extent,
        boundary,
        width: cardMinimum(),
        scroller,
        coarse
      });
      return {
        side,
        fresh,
        ...initialHold ? { hold: initialHold } : {}
      };
    },
    options(ui, {
      clear,
      row,
      lastRow = row,
      column = null,
      margin = null,
      boundary,
      fit,
      hold = null
    }) {
      const minimumWidth = cardMinimum();
      const across = vertical(side);
      const unanchored = !clear;
      clear ??= new DOMRect(boundary.left, boundary.top, minimumWidth, 0);
      const past = (scale) => side === "right" && margin && margin.right > clear.right + 0.5 && boundary.right - margin.right - COMMENT_GAP >= cardMeasure() * scale.x ? margin.right : null;
      const box = new DOMRect(
        clear.left,
        clear.top,
        (past({ x: 1 }) ?? clear.right) - clear.left,
        clear.height
      );
      const inlineStart = unanchored ? boundary.left : clamp(
        column ?? box.right - minimumWidth,
        boundary.left,
        boundary.right - Math.min(minimumWidth, boundary.width)
      );
      const overflow = { boundary: [], rootBoundary: boundary, padding: 0 };
      let heldIn = false;
      const attachment = ui.limitShift(() => ({
        mainAxis: !across,
        crossAxis: across
      }));
      const scaled = {
        name: "scaled",
        async fn(state) {
          const { rects } = state;
          const scale = await positioningScale(state);
          const right = past(scale) ?? clear.right;
          if (box.right !== right) {
            box.width = right - box.left;
            return { reset: { rects: true } };
          }
          return {
            data: {
              scale,
              column: rects.reference.x + (inlineStart - box.left) / scale.x,
              attachmentInline: rects.reference.x + ((column ?? clear.left) - box.left) / scale.x,
              line: column !== null ? rects.reference.y + (row - box.top) / scale.y : side === "bottom" ? rects.reference.y + rects.reference.height : side === "top" ? rects.reference.y : rects.reference.y + (row - box.top) / scale.y,
              last: rects.reference.y + (lastRow - box.top) / scale.y
            }
          };
        }
      };
      const measure = (state) => state.middlewareData.scaled;
      const spot = held2 ?? initialHold;
      const heldEdge = hold ? hold() : spot && (side === "top" ? { foot: spot.foot } : { top: spot.top });
      const holding = (heldEdge || carriedInline !== null) && {
        name: "hold",
        fn(state) {
          const edge2 = !across && heldEdge;
          const data = {
            edge: heldEdge && ("foot" in heldEdge ? "bottom" : "top"),
            inline: carriedInline !== null ? "left" : null
          };
          const { line: line2, attachmentInline, scale } = measure(state);
          const position = {};
          if (carriedInline !== null)
            position.x = attachmentInline + carriedInline / scale.x;
          if (edge2)
            position.y = "foot" in edge2 ? line2 + edge2.foot / scale.y - state.rects.floating.height : line2 + edge2.top / scale.y;
          const spot2 = { x: state.x, y: state.y, ...position };
          return { ...position, data: { ...data, spot: spot2 } };
        }
      };
      const size = ui.size({
        ...overflow,
        apply(state) {
          const { scale } = measure(state);
          const lane = carriedInline !== null ? boundary.right - (column ?? clear.left) - carriedInline : across ? boundary.right - (inlineStart + (inline ?? 0) * scale.x) : side === "right" ? boundary.right - box.right - COMMENT_GAP : clear.left - boundary.left - COMMENT_GAP;
          fit({
            side,
            width: Math.max(
              Math.min(minimumWidth, boundary.width) / scale.x,
              Math.min(state.availableWidth, lane / scale.x)
            ),
            height: state.availableHeight,
            scale
          });
        }
      });
      const sizing = heldEdge ? {
        ...size,
        fn(state) {
          const { shift, ...middlewareData } = state.middlewareData;
          const foot = "foot" in heldEdge;
          return size.fn({
            ...state,
            placement: across ? `${foot ? "top" : "bottom"}-start` : `${side}-${foot ? "end" : "start"}`,
            middlewareData
          });
        }
      } : size;
      const middleware = [
        scaled,
        ui.offset((state) => {
          const { scale } = measure(state);
          const edge2 = across && heldEdge;
          const top = edge2 && measure(state).line - state.rects.reference.y + ("foot" in edge2 ? edge2.foot / scale.y - state.rects.floating.height : edge2.top / scale.y);
          return {
            mainAxis: edge2 ? side === "top" ? -top - state.rects.floating.height : top - state.rects.reference.height : COMMENT_GAP / (across ? scale.y : scale.x),
            crossAxis: across ? measure(state).column - state.rects.reference.x + (inline ?? 0) : (row - COMMENT_GAP - box.top) / scale.y
          };
        }),
        holding,
        heldEdge && sizing,
        ui.shift({
          ...overflow,
          mainAxis: true,
          crossAxis: true,
          limiter: {
            ...attachment,
            fn(state) {
              if (unanchored) {
                heldIn = true;
                return { x: state.x, y: state.y };
              }
              const limited = across ? attachment.fn(state) : {
                x: state.x,
                y: clamp(
                  state.y,
                  measure(state).line - state.rects.floating.height,
                  measure(state).last
                )
              };
              if (moved)
                for (const axis of ["x", "y"]) {
                  const own = state.middlewareData.hold.spot[axis];
                  limited[axis] = clamp(
                    state[axis],
                    Math.min(limited[axis], own),
                    Math.max(limited[axis], own)
                  );
                }
              heldIn = Math.abs(limited.y - state.y) < 0.5;
              return limited;
            }
          }
        }),
        !heldEdge && sizing
      ].filter(Boolean);
      return {
        reference: box,
        placement: `${side}-start`,
        middleware,
        plane: ({ middlewareData }) => {
          if (unanchored) return "window";
          const shift = middlewareData.shift?.y ?? 0;
          if (!heldIn || Math.abs(shift) < 0.5) return "page";
          return shift > 0 ? { edge: "top", at: boundary.top - COMMENT_GAP } : { edge: "bottom", at: boundary.bottom + COMMENT_GAP };
        }
      };
    },
    landed({ x, y, middlewareData }) {
      initialHold = null;
      const { scale, column, attachmentInline, line: line2 } = middlewareData.scaled;
      if (vertical(side)) inline ??= x - column;
      else if (side !== "left") carriedInline ??= (x - attachmentInline) * scale.x;
      const top = (y - (middlewareData.shift?.y ?? 0) - line2) * scale.y;
      const spot = { top, foot: top + middlewareData.held.height * scale.y };
      held2 = { ...spot, ...reading };
      return { scale };
    }
  };
}

export {
  THREAD_CARD,
  marginColumn,
  marginSpot,
  syncMarginResidency,
  scheduleMarginEntryLabels,
  mountMarginLayer,
  standsFolded,
  scheduleMarginLayout,
  registerMarginRow,
  unregisterMarginRow,
  layoutMarginRows,
  floatingUi,
  floatingSelections,
  floatingPlacement,
  commentAttachment,
  commentReference,
  COMMENT_GAP,
  commentBoundary,
  makeRoom,
  cardMinimum,
  cardMeasure,
  commentPlacement
};
