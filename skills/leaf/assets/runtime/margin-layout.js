/* One geometry owner for the rows that stand in the margin or over the page.

   Every margin row lives in the chrome's margin layer and is tied to its target by anchor
   positioning, so nothing Leaf draws is inserted into the page's content and nothing it
   draws moves that content. A row stands in one of two postures (`margin-placement.js`):
   in the rail, the strip a column page reserves beside its column, or as a pin over the
   page at the top-right of its target's block. The stylesheet places each row from what
   this pass writes on it (theme.css, at .lf-margin-cluster): its posture as
   `data-lf-place`, a pin's offset past its block as `--lf-dx`, and the push packing gives
   it as `--lf-push`. Scrolling moves a row with its target on the compositor, whether the
   document scrolls or a pane does, with no pass at all.

   A row is `position: fixed`, so the viewport is its containing block and every element
   of the page is an anchor it may stand by; a wrapper that became its containing block
   (a transform, a filter, `contain`) would make every target outside it an invalid
   anchor. Rows whose targets scroll with the document stand in the root lane; each
   bounded reading region (one whose body scrolls on its own) gets a lane of its own,
   clipped with `clip-path` to what that region shows, which clips a pin's paint and
   presses without making the lane a containing block.

   An anchor name reaches only its own tree, so a target inside a shadow tree anchors
   through its host, and a `display: contents` target through its first shown part.
   `position-visibility` hides a row whose anchor its scroller has clipped away, but not
   one whose anchor is invalid (missing, `display: contents`, inside
   `content-visibility: hidden`): every position function in the stylesheet therefore
   parks the row off screen when its anchor fails, and this pass marks a row withheld,
   out of the tab order, when its target has no shown part in its region.

   Visibility reads `shownParts`, not the target's raw client rect: a project may set
   `display: contents` while its rendered descendants remain usable, and a collapsed
   target has no rendered part to offer. */
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { shellRight, shownBand, shownParts, shownRect } from "./geometry.js";
import { upFrom } from "./shadow.js";
import { scrollerFor } from "./reading-regions.js";
import { pageScroller } from "./scrolling.js";
import { packRows, pinOffset, rowPosture, stepPast } from "./margin-placement.js";

const rows = new Map();
const GAP = 4;
// The anchor name the rail hangs from: `main`'s own box.
const PAGE_ANCHOR = "--lf-page";
let pending = 0;
let observer = null;
let observedColumn = null;
let layer = null;

const marginColumn = () => document.querySelector("main") || document.body;

// Whether the margin's rail stands, as the stylesheet decided it: theme.css states the
// posture on `main` where it claims the rail, and this reads that answer rather than
// deriving one of its own from a width. It resolves a container query, so a read after a
// write forces layout, and the layout pass reads it once. So the answer is read once per
// task and reused: nothing a pass writes can change the reading, since the claim comes out
// of `main`'s room inside the shell while the container answers on the shell itself. The
// microtask that clears it runs before anything outside the pass can ask.
const readRailPosture = () => {
  const main = document.querySelector("main");
  return (
    Boolean(main) &&
    getComputedStyle(main).getPropertyValue("--lf-rail-posture").trim() === "margin"
  );
};
let railReading = null;
export const railStands = () => {
  if (railReading === null) {
    railReading = readRailPosture();
    queueMicrotask(() => (railReading = null));
  }
  return railReading;
};

const labelRect = (name, left, top, label) => ({
  name,
  rect: {
    left,
    right: left + label.width,
    top,
    bottom: top + label.height,
  },
});

const rectsOverlap = (left, right) =>
  left.left < right.right &&
  left.right > right.left &&
  left.top < right.bottom &&
  left.bottom > right.top;

function placeMarginEntryLabel(control) {
  const label = control.querySelector(":scope > .lf-margin-entry-label");
  if (!label || !control.checkVisibility()) return;
  const marginEntryBox = control.getBoundingClientRect();
  const labelBox = label.getBoundingClientRect();
  const edgeAligned = Math.max(
    4,
    Math.min(marginEntryBox.right - labelBox.width, innerWidth - 4 - labelBox.width),
  );
  const cluster = control.closest(".lf-margin-cluster") ?? control.parentElement;
  const clusterMarginEntries = [
    ...(cluster?.querySelectorAll(".lf-margin-entry") ?? []),
  ]
    .filter((candidate) => candidate.checkVisibility())
    .map((candidate) => candidate.getBoundingClientRect());
  const clusterLeft = Math.min(...clusterMarginEntries.map((box) => box.left));
  const clusterRight = Math.max(...clusterMarginEntries.map((box) => box.right));
  const centered = (marginEntryBox.top + marginEntryBox.bottom - labelBox.height) / 2;
  const candidates = [
    labelRect("below", edgeAligned, marginEntryBox.bottom + 6, labelBox),
    labelRect("above", edgeAligned, marginEntryBox.top - 6 - labelBox.height, labelBox),
    labelRect("after", clusterRight + 6, centered, labelBox),
    labelRect("before", clusterLeft - 6 - labelBox.width, centered, labelBox),
  ];
  const blockers = [
    ...[...document.querySelectorAll(".lf-margin-entry")].filter(
      (candidate) => candidate !== control && candidate.checkVisibility(),
    ),
    ...document.querySelectorAll(".lf-banner, .lf-shortcut-bar"),
  ].map((candidate) => candidate.getBoundingClientRect());
  const fits = ({ rect }) =>
    rect.left >= 4 &&
    rect.right <= innerWidth - 4 &&
    rect.top >= 4 &&
    rect.bottom <= innerHeight - 4;
  const choice =
    candidates.find(
      (candidate) =>
        fits(candidate) &&
        !blockers.some((blocker) => rectsOverlap(candidate.rect, blocker)),
    ) ??
    candidates.find(fits) ??
    candidates[0];
  control.dataset.lfLabelSide = choice.name;
  label.style.setProperty(
    "--lf-label-x",
    `${choice.rect.left - marginEntryBox.left}px`,
  );
  label.style.setProperty("--lf-label-y", `${choice.rect.top - marginEntryBox.top}px`);
}

let labelPlacementFrame = 0;
export function scheduleMarginEntryLabels() {
  if (labelPlacementFrame) return;
  labelPlacementFrame = nextRender(() => {
    labelPlacementFrame = 0;
    for (const control of document.querySelectorAll(
      '.lf-margin-entry:is(:hover, :focus-visible, .lf-focus-visible):not([aria-expanded="true"])',
    ))
      placeMarginEntryLabel(control);
  });
}

// The layer's root lane, where rows whose targets scroll with the document stand, and one
// lane per bounded reading region, keyed by the box that scrolls it.
export function mountMarginLayer(root) {
  layer = { root, lanes: new Map() };
}

function laneFor(scroller) {
  if (scroller === pageScroller) return layer.root;
  let lane = layer.lanes.get(scroller);
  if (!lane) {
    lane = document.createElement("div");
    lane.className = "lf-margin-lane";
    lane.setAttribute("role", "group");
    layer.root.after(lane);
    layer.lanes.set(scroller, lane);
    scroller.addEventListener("scroll", scheduleLaneReading, { passive: true });
  }
  return lane;
}

// Anchor names are global to their tree, so one per target element, merged with whatever
// name the author gave the same box. The name stays for the element's life: rows come and
// go on the heartbeat and a name written each time would restyle the target each time.
const anchorNames = new WeakMap();
let anchorOrdinal = 0;
function nameAnchor(el, name = anchorNames.get(el) ?? `--lf-a${++anchorOrdinal}`) {
  anchorNames.set(el, name);
  const written = el.style.anchorName;
  if (written.split(",").some((part) => part.trim() === name)) return name;
  // What the author's stylesheet names this box, read only where this pass has not already
  // written: a revision patch that rewrote the style attribute has taken the name away.
  const authored = written || getComputedStyle(el).anchorName;
  el.style.anchorName =
    !authored || authored === "none" ? name : `${authored}, ${name}`;
  return name;
}

// The box a row anchors to. An anchor name reaches only its own tree, so a target inside
// a shadow tree anchors through its host; a shape inside an SVG drawing has no CSS box of
// its own, so it anchors through the drawing; a `display: contents` target through its
// first shown part. Where the anchor is not the target, the row still stands level with
// the target's top, through `--lf-inset`.
function anchorElement(target) {
  let el = target;
  for (let root = el.getRootNode(); root instanceof ShadowRoot; root = el.getRootNode())
    el = root.host;
  while (el instanceof SVGElement && el.ownerSVGElement) el = el.ownerSVGElement;
  if (el !== target) return el;
  const [part] = shownParts(target);
  return part && part !== target ? part : target;
}

// How far right the figure a target belongs to reaches: the target's own box, or the
// furthest of the boxes holding it inside `main`, so a card in a board grown past the
// rail stands its comment on the board as a figure does. Read off the boxes rather than
// the declared widths, so a block an agent widened with its own CSS counts too.
function reach(anchor, box, main, reaches) {
  let right = box.right;
  for (let el = anchor.parentElement; el && el !== main; el = el.parentElement) {
    let edge = reaches.get(el);
    if (edge === undefined) reaches.set(el, (edge = el.getBoundingClientRect().right));
    right = Math.max(right, edge);
  }
  return right;
}

// What the page leaves free past a block's right edge: the nearest frame's inline-end
// padding, or, for a block standing in `main`, the room to the shell's edge. Only the
// nearest frame counts: climbing past a grid cell with no padding to the pane beyond
// would put a left cell's pin over the right cell's content.
function roomBeside(anchor, box, main, shell, frames) {
  for (let el = anchor.parentElement; el && el !== main; el = el.parentElement) {
    let frame = frames.get(el);
    if (frame === undefined) {
      frame =
        getComputedStyle(el).getPropertyValue("--lf-block-frame").trim() === "1"
          ? el
          : null;
      frames.set(el, frame);
    }
    if (!frame) continue;
    const edge = frame.getBoundingClientRect();
    return Math.max(0, edge.left + frame.clientLeft + frame.clientWidth - box.right);
  }
  return shell - box.right;
}

function scheduleMarginLayout() {
  if (pending) return;
  pending = nextRender(layoutMarginRows);
}

function observeLayout() {
  const column = marginColumn();
  if (!observer) {
    observer = sizeObserver(scheduleMarginLayout);
    observer.observe(document.body);
  }
  if (observedColumn === column) return;
  if (observedColumn) observer.unobserve(observedColumn);
  observedColumn = column;
  observer.observe(observedColumn);
}

// Each row states its target (`anchor`), its place among the others in the layer
// (`order`), its packing priority, and how to move it between lanes without dropping the
// focus it holds (`move`).
export function registerMarginRow(row, options = {}) {
  rows.set(row, options);
  observeLayout();
  scheduleMarginLayout();
  return () => unregisterMarginRow(row);
}

export const updateMarginRow = registerMarginRow;

export function unregisterMarginRow(row) {
  rows.delete(row);
  if (row) {
    row.classList.remove("lf-withheld");
    row.removeAttribute("data-lf-place");
    for (const property of [
      "--lf-dx",
      "--lf-inset",
      "--lf-push",
      "--lf-step",
      "position-anchor",
    ])
      row.style.removeProperty(property);
    pushes.delete(row);
    steps.delete(row);
  }
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }
  scheduleMarginLayout();
}

// `add` and `remove` re-serialize the class attribute whether or not the token changes,
// and this pass runs on the heartbeat, so ask before marking.
function mark(row, name, on) {
  if (row.classList.contains(name) !== on) row.classList.toggle(name, on);
}

function setStyle(row, property, value) {
  if (value === null) {
    if (row.style.getPropertyValue(property)) row.style.removeProperty(property);
  } else if (row.style.getPropertyValue(property) !== value)
    row.style.setProperty(property, value);
}

const shownTop = (target) =>
  Math.min(...shownParts(target).map((part) => part.getBoundingClientRect().top));

// Whether a target shows any part of itself: it renders, and no box between it and the
// document's scroller clips it away, whether that is the pane that scrolls it or a table
// it has been scrolled sideways out of. The window itself does not count: a row scrolled
// off it is still the user's to walk to.
function targetShown(target, anchor, bands) {
  if (!shownParts(target).some((part) => part.checkVisibility())) return false;
  let { left, top, right, bottom } = anchor.getBoundingClientRect();
  for (let el = upFrom(anchor); el && el !== pageScroller; el = upFrom(el)) {
    let band = bands.get(el);
    if (band === undefined) bands.set(el, (band = shownBand(el)));
    if (!band) continue;
    left = Math.max(left, band.left);
    top = Math.max(top, band.top);
    right = Math.min(right, band.right);
    bottom = Math.min(bottom, band.bottom);
    if (right <= left || bottom <= top) return false;
  }
  return true;
}

const pushes = new Map();
const steps = new Map();
const clips = new WeakMap();

// A scroll inside a bounded region moves its rows on the compositor. What it can change
// is which of them the region still shows, so only that is read again, once a frame.
let laneReading = 0;
function scheduleLaneReading() {
  if (laneReading) return;
  laneReading = nextRender(() => {
    laneReading = 0;
    const bands = new Map();
    for (const [row, options] of rows) {
      const target = options.anchor();
      if (!target?.isConnected || scrollerFor(target) === pageScroller) continue;
      mark(row, "lf-withheld", !targetShown(target, anchorElement(target), bands));
    }
  });
}

// LOOK PASS (temporary): the open visual candidates, chosen on the root for stills.
const look = () => ({
  pin: document.documentElement.dataset.lfLookPin ?? "room",
  wide: document.documentElement.dataset.lfLookWide === "b4" ? "step" : "pin",
});

export function layoutMarginRows() {
  cancelRender(pending);
  pending = 0;
  if (!layer) return;
  const main = marginColumn();
  nameAnchor(main, PAGE_ANCHOR);
  const columnRect = main.getBoundingClientRect();
  const shell = shellRight();
  const stands = railStands();
  const { pin, wide } = look();
  const rootStyle = getComputedStyle(document.documentElement);
  const hang = parseFloat(rootStyle.getPropertyValue("--rail-hang")) || 0;
  const railInner = columnRect.right + hang;
  const entry = layer.root.parentElement.querySelector(
    ".lf-margin-entry:not([hidden])",
  );
  const size = entry?.offsetWidth || 32;

  // Every read before any write: a write between two reads forces a layout per row.
  const frames = new Map();
  const bands = new Map();
  const reaches = new Map();
  const bounds = new Map();
  const reads = [];
  for (const [row, options] of rows) {
    const target = options.anchor();
    if (!target?.isConnected) {
      reads.push({ row, options, lane: layer.root, shown: false });
      continue;
    }
    const anchor = anchorElement(target);
    const scroller = scrollerFor(target);
    const rootLane = scroller === pageScroller;
    if (!rootLane && !bounds.has(scroller))
      bounds.set(scroller, shownRect(scroller, new Map()));
    const shown = targetShown(target, anchor, bands);
    const box = anchor.getBoundingClientRect();
    const inset = anchor === target ? 0 : shownTop(target) - box.top;
    const place = rowPosture({
      railStands: stands,
      rootLane,
      blockRight: reach(anchor, box, main, reaches),
      railInner,
      half: size / 2,
      wide,
    });
    reads.push({
      row,
      options,
      anchor,
      scroller,
      lane: rootLane ? layer.root : null,
      shown,
      place,
      inset,
      edge: box.right,
      room: place === "pin" ? roomBeside(anchor, box, main, shell, frames) : 0,
    });
  }

  // Lanes, in the order the rows are given, moving only what is out of place.
  for (const read of reads) read.lane ??= laneFor(read.scroller);
  const byLane = new Map();
  for (const read of [...reads].sort(
    (a, b) => (a.options.order ?? 0) - (b.options.order ?? 0),
  ))
    byLane.set(read.lane, [...(byLane.get(read.lane) ?? []), read]);
  for (const [lane, members] of byLane) {
    let before = lane.firstElementChild;
    for (const { row, options } of members) {
      if (before === row) {
        before = row.nextElementSibling;
        continue;
      }
      const into = () => lane.insertBefore(row, before);
      if (options.move) options.move(into);
      else into();
    }
  }
  for (const [scroller, lane] of layer.lanes)
    if (!byLane.has(lane)) {
      lane.remove();
      layer.lanes.delete(scroller);
      scroller.removeEventListener("scroll", scheduleLaneReading);
    }

  for (const { row, anchor, shown, place, inset } of reads) {
    mark(row, "lf-withheld", !shown);
    if (!shown) continue;
    setStyle(row, "position-anchor", nameAnchor(anchor));
    setStyle(row, "--lf-inset", inset ? `${inset}px` : null);
    if (row.dataset.lfPlace !== place) row.dataset.lfPlace = place;
    if (place !== "pin") setStyle(row, "--lf-dx", null);
  }

  // Packing reads where each row stands with no push, then writes every push together. A
  // pin's offset takes its own width, which is read here, so where the pin will stand
  // across is worked out rather than read back.
  const placed = reads
    .filter((read) => read.shown)
    .map((read) => {
      const box = read.row.getBoundingClientRect();
      const push = pushes.get(read.row) ?? 0;
      const step = steps.get(read.row) ?? 0;
      const dx =
        read.place === "pin" ? pinOffset({ room: read.room, size: box.width, pin }) : 0;
      return {
        key: read.row,
        rect: {
          left: read.place === "pin" ? read.edge + dx - box.width : box.left - step,
          right: read.place === "pin" ? read.edge + dx : box.right - step,
          top: box.top - push,
          bottom: box.bottom - push,
        },
        priority: read.options.priority ?? 0,
        dx,
        read,
      };
    });
  const packed = packRows(placed, GAP);
  const grown =
    wide === "step"
      ? [...main.querySelectorAll("[data-lf-space]")]
          .map((el) => el.getBoundingClientRect())
          .filter((box) => box.right > columnRect.right + 1)
      : [];
  for (const { key: row, rect, read, dx } of placed) {
    if (read.place === "pin") setStyle(row, "--lf-dx", `${dx}px`);
    const push = packed.get(row) ?? 0;
    pushes.set(row, push);
    setStyle(row, "--lf-push", push ? `${push}px` : null);
    // A rail row wider than the rail, unfolded or holding more than its resting budget,
    // steps back from the shell's edge rather than widening the page.
    const step =
      read.place === "rail"
        ? Math.min(
            grown.length
              ? stepPast({
                  left: rect.left,
                  width: rect.right - rect.left,
                  hang,
                  top: rect.top + push,
                  height: rect.bottom - rect.top,
                  wide: grown,
                  shellRight: shell,
                })
              : 0,
            shell - rect.right,
          )
        : 0;
    steps.set(row, step);
    setStyle(row, "--lf-step", step ? `${step}px` : null);
  }

  // Each lane shows its region's rows only inside what that region shows, with room for a
  // focus ring. The clip is in the lane's own coordinates, so it is taken again whenever
  // the pass runs: the region may have moved or changed size.
  for (const [scroller, lane] of layer.lanes) {
    const shownBounds = bounds.get(scroller) ?? shownRect(scroller, new Map());
    const at = lane.getBoundingClientRect();
    const ring = 6;
    const clip = shownBounds
      ? `polygon(${[
          [shownBounds.left - ring, shownBounds.top],
          [shownBounds.right + ring, shownBounds.top],
          [shownBounds.right + ring, shownBounds.bottom],
          [shownBounds.left - ring, shownBounds.bottom],
        ]
          .map(([x, y]) => `${x - at.left}px ${y - at.top}px`)
          .join(", ")})`
      : "polygon(0 0)";
    if (clips.get(lane) !== clip) {
      lane.style.clipPath = clip;
      clips.set(lane, clip);
    }
  }
  document.dispatchEvent(new CustomEvent("lf-margin-layout"));
}

export { scheduleMarginLayout };
