/* One geometry owner for the rows that stand in the margin or over the page.

   Every margin row lives in the chrome's margin layer and is tied to its target by anchor
   positioning, so nothing Leaf draws is inserted into the page's content and nothing it
   draws moves that content. A row stands in one of two postures (`margin-placement.js`):
   in the rail, the strip a column page reserves beside its column, or as a pin over the
   page at the top-right of its target's block. The stylesheet places each row from what
   this pass writes on it (theme.css, at .lf-margin-cluster): its posture as
   `data-lf-place`, and the push packing gives it as `--lf-push`. Scrolling moves a row with its target on the compositor, whether the
   document scrolls or a pane does, with no pass at all.

   The layer is a static, zero-height block. A positioned wrapper would become every row's
   containing block, and a row can only anchor to what stands inside its containing block,
   so every target outside it would be an invalid anchor. Rows whose targets scroll with
   the document stand in the root lane; each
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
import { shellRight, shownBand, shownParts } from "./geometry.js";
import { under, upFrom } from "./shadow.js";
import { scrollerFor } from "./reading-regions.js";
import { pageScroller } from "./scrolling.js";
import { packRows, rowPosture } from "./margin-placement.js";

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
// lane per bounded reading region, keyed by the box that scrolls it. A scroll anywhere
// but the document's may take a target out of view or bring it back, so it is heard once,
// here, rather than per lane: a table or a board scrolled sideways is no lane of its own.
export function mountMarginLayer(root) {
  layer = { root, lanes: new Map(), sizes: sizeObserver(scheduleMarginLayout) };
  document.addEventListener(
    "scroll",
    (event) => {
      if (event.target === document || !(event.target instanceof Element)) return;
      scrolled.add(event.target);
      scheduleScrollReading();
    },
    { capture: true, passive: true },
  );
}

function laneFor(scroller) {
  if (scroller === pageScroller) return layer.root;
  let lane = layer.lanes.get(scroller);
  if (!lane) {
    lane = document.createElement("div");
    lane.className = "lf-margin-lane";
    layer.root.parentElement.append(lane);
    layer.lanes.set(scroller, lane);
    layer.sizes.observe(scroller);
  }
  return lane;
}

// Anchor names are global to their tree, so one per target element, merged with whatever
// name the author gave the same box. The name stays for the element's life: rows come and
// go on the heartbeat and a name written each time would restyle the target each time.
// The pass reads what a box is named before it writes any name (`anchorReading`), since
// reading the author's name is a style read.
const anchorNames = new WeakMap();
let anchorOrdinal = 0;
function anchorReading(el, name = anchorNames.get(el) ?? `--lf-a${++anchorOrdinal}`) {
  anchorNames.set(el, name);
  const written = el.style.anchorName;
  if (written.split(",").some((part) => part.trim() === name)) return { el, name };
  // What the author's stylesheet names this box, read only where this pass has not already
  // written: a revision patch that rewrote the style attribute has taken the name away.
  const authored = written || getComputedStyle(el).anchorName;
  return {
    el,
    name,
    write: !authored || authored === "none" ? name : `${authored}, ${name}`,
  };
}
function nameAnchor({ el, name, write }) {
  if (write) el.style.anchorName = write;
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

// The part of a box its scrollers show, short of the document's own: each scroller's band
// between the box and the document cuts it. The window does not count, since a row
// scrolled off it is still the user's to walk to. `bands` caches each box's band for one
// reading.
function clippedBand(el, rect, bands) {
  let { left, top, right, bottom } = rect;
  for (let at = upFrom(el); at && at !== pageScroller; at = upFrom(at)) {
    let band = bands.get(at);
    if (band === undefined) bands.set(at, (band = shownBand(at)));
    if (!band) continue;
    left = Math.max(left, band.left);
    top = Math.max(top, band.top);
    right = Math.min(right, band.right);
    bottom = Math.min(bottom, band.bottom);
  }
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}

// How far right the figure a target belongs to reaches: the furthest of its own box and
// the boxes holding it inside `main`, so a card in a board grown past the rail stands its
// comment on the board as a figure does. Read off the boxes rather than the declared
// widths, so a block an agent widened with its own CSS counts too. A scroller cuts what
// it holds to what it shows: a cell far along a wide table is not a figure past the rail.
function reach(anchor, box, main, reaches) {
  let right = box.right;
  for (let el = anchor.parentElement; el && el !== main; el = el.parentElement) {
    let edge = reaches.get(el);
    if (edge === undefined) {
      const b = el.getBoundingClientRect();
      edge = {
        right: b.right,
        clip:
          getComputedStyle(el).overflowX === "visible"
            ? null
            : b.left + el.clientLeft + el.clientWidth,
      };
      reaches.set(el, edge);
    }
    if (edge.clip !== null) right = Math.min(right, edge.clip);
    right = Math.max(right, edge.right);
  }
  return right;
}

// The page's own controls in a pin's block, which the pin may not stand on: a pin at a
// card's top-right would otherwise take the presses meant for the card's grip. Anything
// the keyboard can reach is a control, so a package need declare nothing.
const CONTROLS =
  'button, a[href], input, select, textarea, summary, [contenteditable], [tabindex]:not([tabindex="-1"])';
function controlsIn(anchor) {
  return [...anchor.querySelectorAll(CONTROLS)]
    .filter((control) => control.checkVisibility())
    .map((control) => control.getBoundingClientRect())
    .filter((box) => box.width && box.height);
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
    row.removeAttribute("data-lf-parked");
    for (const property of ["--lf-inset", "--lf-push", "--lf-step", "position-anchor"])
      row.style.removeProperty(property);
    pushes.delete(row);
    steps.delete(row);
    parked.delete(row);
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

// Whether a row has somewhere to stand: its target renders, its scrollers leave some of it
// in view — the pane that scrolls it, or a table or board it has been scrolled sideways
// out of — and the point the row stands at is inside that view. That is the target's top
// line, since a row standing above a pane's top would be clipped by its lane and still
// take the keyboard, and for a pin the target's right edge too: a card half past a
// board's edge would stand its pin outside the board, beside nothing and past the page.
function targetShown(target, anchor, inset, pin, bands) {
  if (!shownParts(target).some((part) => part.checkVisibility())) return false;
  const box = anchor.getBoundingClientRect();
  const view = clippedBand(anchor, box, bands);
  const line = box.top + inset;
  return (
    Boolean(view) &&
    line >= view.top - 1 &&
    line < view.bottom &&
    (!pin || box.right <= view.right + 1)
  );
}

const pushes = new Map();
const steps = new Map();
const clips = new WeakMap();
// A row whose anchor the browser would not take — one behind an author's `anchor-scope`,
// say — stands at its fallback off screen. The pass finds it there once and
// withholds it for as long as it anchors to the same box, rather than finding it again on
// every heartbeat. `data-lf-parked` says so for the render gate.
const parked = new WeakMap();

// A scroll inside anything but the document moves its rows on the compositor. What it can
// change is which of them still have somewhere to stand, so only rows under a box that
// scrolled are read again, once a frame, and a row that changes answer brings the whole
// pass, which places it.
const scrolled = new Set();
let scrollReading = 0;
function scheduleScrollReading() {
  if (scrollReading) return;
  scrollReading = nextRender(() => {
    scrollReading = 0;
    const boxes = [...scrolled];
    scrolled.clear();
    const bands = new Map();
    for (const [row, options] of rows) {
      const target = options.anchor();
      if (!target?.isConnected || parked.has(row)) continue;
      const anchor = anchorElement(target);
      if (!boxes.some((box) => under(anchor, box))) continue;
      const inset =
        anchor === target ? 0 : shownTop(target) - anchor.getBoundingClientRect().top;
      if (
        targetShown(target, anchor, inset, row.dataset.lfPlace === "pin", bands) ===
        row.classList.contains("lf-withheld")
      ) {
        scheduleMarginLayout();
        return;
      }
    }
  });
}

export function layoutMarginRows() {
  cancelRender(pending);
  pending = 0;
  if (!layer) return;
  const main = marginColumn();
  const page = anchorReading(main, PAGE_ANCHOR);
  const columnRect = main.getBoundingClientRect();
  const shell = shellRight();
  const stands = railStands();
  const rootStyle = getComputedStyle(document.documentElement);
  const hang = parseFloat(rootStyle.getPropertyValue("--rail-hang")) || 0;
  const pinInset = parseFloat(rootStyle.getPropertyValue("--pin-inset")) || 0;
  const railInner = columnRect.right + hang;
  const entry = layer.root.parentElement.querySelector(
    ".lf-margin-entry:not([hidden])",
  );
  const size = entry?.offsetWidth || 32;

  // Every read before any write: a write between two reads forces a layout per row.
  const bands = new Map();
  const reaches = new Map();
  const reads = [];
  for (const [row, options] of rows) {
    const target = options.anchor();
    if (!target?.isConnected) {
      reads.push({ row, options, lane: layer.root, shown: false });
      continue;
    }
    const anchor = anchorElement(target);
    if (parked.has(row) && parked.get(row) !== anchor) parked.delete(row);
    const scroller = scrollerFor(target);
    const rootLane = scroller === pageScroller;
    const box = anchor.getBoundingClientRect();
    const inset = anchor === target ? 0 : shownTop(target) - box.top;
    const place = rowPosture({
      railStands: stands,
      rootLane,
      blockRight: reach(anchor, box, main, reaches),
      railInner,
      half: size / 2,
    });
    const shown =
      !parked.has(row) && targetShown(target, anchor, inset, place === "pin", bands);
    reads.push({
      row,
      options,
      anchor,
      naming: anchorReading(anchor),
      scroller,
      lane: rootLane ? layer.root : null,
      shown,
      place,
      inset,
      edge: box.right,
      controls: place === "pin" && shown ? controlsIn(anchor) : [],
    });
  }
  // What each lane's region shows, cut by the scrollers around it but not by the window,
  // so a pane below the fold is clipped where its own edges will be when it arrives.
  const regions = new Map();
  for (const read of reads)
    if (read.scroller && read.scroller !== pageScroller && !regions.has(read.scroller))
      regions.set(
        read.scroller,
        clippedBand(
          read.scroller,
          shownBand(read.scroller) ?? read.scroller.getBoundingClientRect(),
          bands,
        ),
      );

  nameAnchor(page);
  // Lanes, in the order the rows are given, moving only what is out of place; each lane
  // after the last, so the tab order runs the lanes as the rows run.
  for (const read of reads) read.lane ??= laneFor(read.scroller);
  const byLane = new Map();
  for (const read of [...reads].sort(
    (a, b) => (a.options.order ?? 0) - (b.options.order ?? 0),
  ))
    byLane.set(read.lane, [...(byLane.get(read.lane) ?? []), read]);
  let lastLane = layer.root;
  for (const [lane, members] of byLane) {
    if (lane !== layer.root) {
      if (lastLane.nextElementSibling !== lane) lastLane.after(lane);
      lastLane = lane;
    }
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
      layer.sizes.unobserve(scroller);
    }

  // A withheld row is anchored too, so that when its target comes into view it has only
  // to show.
  for (const { row, naming, shown, place, inset } of reads) {
    mark(row, "lf-withheld", !shown);
    if (!naming) continue;
    setStyle(row, "position-anchor", nameAnchor(naming));
    setStyle(row, "--lf-inset", inset ? `${inset}px` : null);
    if (row.dataset.lfPlace !== place) row.dataset.lfPlace = place;
  }

  // Packing reads where each row stands with no push, then writes every push together. A
  // pin stands `--pin-inset` inside its block's right edge, which is read here, so where
  // it will stand across is worked out rather than read back.
  const placed = reads
    .filter((read) => read.shown)
    .map((read) => {
      const box = read.row.getBoundingClientRect();
      const push = pushes.get(read.row) ?? 0;
      const step = steps.get(read.row) ?? 0;
      return {
        key: read.row,
        // At its off-screen fallback: the browser did not take the anchor.
        stranded: box.bottom + scrollY < -1000,
        rect: {
          left:
            read.place === "pin" ? read.edge - pinInset - box.width : box.left - step,
          right: read.place === "pin" ? read.edge - pinInset : box.right - step,
          top: box.top - push,
          bottom: box.bottom - push,
        },
        priority: read.options.priority ?? 0,
        read,
      };
    });
  for (const { key: row, stranded, read } of placed)
    if (stranded) {
      parked.set(row, read.anchor);
      row.setAttribute("data-lf-parked", "");
      mark(row, "lf-withheld", true);
    } else if (row.hasAttribute("data-lf-parked"))
      row.removeAttribute("data-lf-parked");
  const standing = placed.filter(({ stranded }) => !stranded);
  const packed = packRows(
    standing,
    GAP,
    standing.flatMap(({ read }) => read.controls ?? []),
  );
  for (const { key: row, rect, read } of standing) {
    const push = packed.get(row) ?? 0;
    pushes.set(row, push);
    setStyle(row, "--lf-push", push ? `${push}px` : null);
    // A rail row wider than the rail, unfolded or holding more than its resting budget,
    // steps back from the shell's edge rather than widening the page.
    const step = read.place === "rail" ? Math.min(0, shell - rect.right) : 0;
    steps.set(row, step);
    setStyle(row, "--lf-step", step ? `${step}px` : null);
  }

  // Each lane shows its region's rows only inside what that region shows, with room for a
  // focus ring. The clip is in the lane's own coordinates, so it is taken again whenever
  // the pass runs, which a resize of the region's box also brings.
  for (const [scroller, lane] of layer.lanes) {
    const region = regions.get(scroller);
    const at = lane.getBoundingClientRect();
    const ring = 6;
    const clip = region
      ? `polygon(${[
          [region.left - ring, region.top],
          [region.right + ring, region.top],
          [region.right + ring, region.bottom],
          [region.left - ring, region.bottom],
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
