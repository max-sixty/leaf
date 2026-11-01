/* One geometry owner for the rows that stand in the margin or over the page.

   Every margin row lives in the chrome's margin layer, in document coordinates, so
   nothing Leaf draws is inserted into the page's content and nothing it
   draws moves that content. A row stands in one of two postures (`margin-placement.js`):
   in the rail, the strip beside `main` where the room there holds one, or as a pin over the
   page by its target, on the first seat touching it that covers no words, controls or
   media, and where none does, over the target itself (`pinSeating`). Hiding annotations
   reveals what a pin covers. User-held controls retain their seat.
   The stylesheet places each row from what this pass writes on it
   (annotation-theme.css, at .lf-margin-cluster): its posture as `data-lf-place`, its
   seat as `--lf-margin-x` and `--lf-margin-y`, including the push rail packing gives it.
   Rows take their final places once, in one shared held-and-arrival order. Each posture's
   solver avoids the final rectangles and held labels already placed. A pin's chosen
   seat is its final place: no second packing pass can translate it into words or
   controls.
   These measured coordinates keep their full layout precision in custom properties;
   ordinary length serialization would round distant document positions before comparing
   them. Scrolling moves a row with its target in the frame that scrolls it, whether the
   document scrolls or a pane does, with no pass at all.
   Mutation checkpoints and resize deliveries settle placement before native paint;
   deferring that pass to the next frame would show a row at its stale seat after its
   target changed.

   Rows follow scrolled content as every such box does (css-anchors.js): the root lane is
   a zero-size box at the document origin, so the root scroll carries its rows; a row
   whose target scrolls inside a box short of the document, or stands under a sticky,
   fixed or absolute box, stands in a carrier anchored to what that box's scroll carries
   beside the target, or to the target itself, so the browser carries it through those
   scrolls and offsets too (`carrierFor`); and a bounded region's lane is a frame
   anchored to the region's scroller and cut at its edge, inside one such frame for each
   scroller around it. A row passes under the sticky headers and footers a page declares
   over its target, as the target's words do: its carrier stands in frames cut where
   they stand (css-anchors.js, `headerLevels`), one run of them for each run of rows
   the same headers cut, so a pin whose target scrolls under a stuck toolbar takes none
   of the toolbar's presses. Remeasuring after a scroll writes the same insets.
   Layout owners announce same-size view rearrangements with `lf-layout`; resize
   observation covers the target's layout siblings and ancestors, including a bounded
   region whose outer height stayed fixed. Geometric reflow, rather than scroll, is what
   chooses a seat again.
   No row names a CSS anchor of its own: such dependencies made unrelated editor and
   chrome reads lay out every margin row again, even with unchanged page content. A
   carrier is one anchor for every row its scroller holds.
   Rows whose targets scroll with
   the document stand in the root lane; each
   bounded reading region (one whose body scrolls on its own) gets a lane of its own,
   cut to what that region shows, and across to the rail for a bounded block in the
   column's flow. A target or its rendered part leaving
   withholds the row before the next paint; layout withholds it when its region hides it.

   A control carries its label as a native descendant. This owner chooses its place
   before CSS reveals it and clears that readiness while the label is inactive, so a
   later reveal reads the room afresh. Label offsets use the control's padding box,
   the containing block for absolute descendants, rather than its border-box origin.

   Visibility reads `shownParts`, not the target's raw client rect: a project may set
   `display: contents` while its rendered descendants remain usable, and a collapsed
   target has no rendered part to offer. */
import { TAB_STOP } from "../control-selectors.js";
import { afterScript, cancelRender, nextRender, sizeObserver } from "../rendering.js";
import {
  clippedContents,
  clippedRect,
  scrollsContent,
  shellRight,
  shownBand,
  shownExtent,
  shownParts,
  shownWindow,
} from "../geometry.js";
import { skipped } from "../shown-box.js";
import {
  renderedChildren,
  renderedParent,
  renderedUnder,
  shadowHost,
  under,
  upFrom,
} from "../shadow.js";
import { scrollerFor } from "../reading-regions.js";
import { boundedBlockOf } from "../bounds.js";
import { pageScroller } from "../scrolling.js";
import { layoutBox } from "../passages.js";
import {
  arrivals,
  inSeatingOrder,
  packRows,
  rowPlacement,
  seatRows,
  seatsBy,
} from "./margin-placement.js";
import { clamp, clippingAxes, overlaps, union } from "../rect.js";
import { passageBoxes, targetRange, targetSegments } from "../resolved-target.js";
import { proseRect, railStands } from "../content-layout.js";
import { keeps, layoutPx } from "../keeps.js";
import { move } from "../dom-move.js";
import { coarsePointer, hoveringPointer } from "../pointer.js";
import { LAYOUT } from "../widget-upgrade.js";
import { inChrome } from "../passages.js";
import { visibleTargetParts } from "../visible-target-parts.js";
import {
  anchorBox,
  anchorFor,
  anchorElement,
  anchorReading,
  carriedAnchor,
  cutFrames,
  headerLevels,
  nameAnchor,
  scrollsWith,
} from "../css-anchors.js";

const rows = new Map();
// A contents target's first shown part can leave while its declaration remains.
// Withhold its row at the mutation checkpoint, before another frame can paint it.
const anchors = new WeakMap();
const targetBox = (target) => shownParts(target)[0] ?? target;
let observedGeometry = new Set();
let geometryObservation = 0;
let wantedGeometry = new Set();

function watchGeometry(geometry) {
  wantedGeometry = geometry;
  if (geometryObservation) return;
  if (
    geometry.size === observedGeometry.size &&
    [...geometry].every((node) => observedGeometry.has(node))
  )
    return;
  // Observing a new ancestor during a resize delivery gives it an initial delivery
  // below that cycle's depth, which the browser reports as an undelivered resize.
  // Register before the next resize cycle; this pass already placed its new rows.
  geometryObservation = nextRender(() => {
    geometryObservation = 0;
    for (const node of observedGeometry)
      if (!wantedGeometry.has(node)) layer.sizes.unobserve(node);
    for (const node of wantedGeometry)
      if (!observedGeometry.has(node)) layer.sizes.observe(node);
    observedGeometry = wantedGeometry;
  });
}
const GAP = 4;
// The id of the thread card a margin row opens (thread-preview.js).
export const THREAD_CARD = "lf-margin-preview";
// A row the user holds, which packing seats before every other (`packRows`): one under
// the pointer, with focus in it, with an entry a finger holds to read (held-word.js),
// with its options open, or whose entry has the thread
// card open, as that entry's disclosure relation says (margin-projection.js,
// `syncReadingRelation`). Opening options can move focus before the next layout pass;
// the open face itself keeps its controls reachable. The card stands relative to its
// row (thread-preview.js), so a seated row whose target moves into it would
// otherwise push the row down and the card the user is reading with it.
// `optionsOpen` includes ordinary inline peers; only a requested expansion holds a seat.
const HELD = `:hover, :focus-within, :has([data-lf-held-word]), [data-lf-options-expanded], :has([aria-controls="${THREAD_CARD}"][aria-expanded="true"])`;
let pending = 0;
let observer = null;
let observedColumn = null;
let layer = null;

// A row whose target scrolls inside a box short of the document stands in a carrier: a
// fixed box anchored to an element that box's scroll carries (`carriedAnchor`), so the
// browser moves the row with every scroll around its target, in the frame that scrolls
// it. Where a sticky, fixed or absolute box stands between the target and that scroll,
// or a sticky or fixed box holds a target only the document scrolls, the carrier is
// anchored to the target itself (`carrierAnchor`). Rows share carriers by anchor and
// axis set, never one per row: an anchor every row named made each layout pass revisit
// every target. A rail row moves with the column, not with its region's sideways
// scroll, so its carrier follows its anchor's block axis alone and stands across the
// page where the window holds it. A box follows only its default anchor through a
// scroll, not a second anchor `anchor()` names, so the column cannot carry it across;
// the document scrolls sideways only by script (`overflow-x: hidden`, base.css), and
// the pass that scroll brings places it again.
// A carrier holds one run of consecutive rows, so rows keep document order across
// carriers; a second run on the same anchor takes a second carrier. Carriers are kept
// by what holds them, a lane or the frames a header cuts, so a row never takes over a
// carrier another holder's withheld row keeps.
const carriers = new Map(); // holder → anchor → its carriers by axes
const carrierAxes = new WeakMap();
function carrierFor(holder, anchor, axes, run) {
  let byAnchor = carriers.get(holder);
  if (!byAnchor) carriers.set(holder, (byAnchor = new Map()));
  let held = byAnchor.get(anchor);
  if (!held) byAnchor.set(anchor, (held = { xy: [], y: [] }));
  if (!held[axes][run]) {
    const carrier = document.createElement("div");
    carrier.className = "lf-ui lf-margin-carrier";
    carrierAxes.set(carrier, axes);
    held[axes][run] = carrier;
  }
  return held[axes][run];
}
const isCarrier = (node) => node?.classList.contains("lf-margin-carrier");
// Each run of rows the same headers cut stands in one chain of frames cut where those
// headers stand (`headerLevels`), keyed by the lane and the cuts, its innermost frame
// holding the run's carriers.
const ids = new WeakMap();
let idCount = 0;
const idOf = (node) => ids.get(node) ?? (ids.set(node, ++idCount), idCount);
const cutFramesByKey = new Map(); // lane id + cut key → innermost frame of each run
const chains = new WeakMap(); // innermost frame → its chain, outermost first
const outerFrame = new WeakMap(); // innermost frame → outermost
const makeCutFrame = () => {
  const frame = document.createElement("div");
  frame.className = "lf-margin-cut";
  return frame;
};
function cutRun(lane, read, run) {
  const key = `${idOf(lane)}|${read.cutKey}`;
  let held = cutFramesByKey.get(key);
  if (!held) cutFramesByKey.set(key, (held = []));
  const chain = cutFrames(read.cuts, chains.get(held[run]) ?? [], makeCutFrame);
  const inner = chain.at(-1);
  if (held[run] && held[run] !== inner) chains.delete(held[run]);
  held[run] = inner;
  chains.set(inner, chain);
  outerFrame.set(inner, chain[0]);
  return inner;
}
// The lane a box of the margin stands in: itself, or the lane holding its frames.
const laneOf = (box) => {
  for (let at = box; at; at = at.parentElement)
    if (at === layer.root || at.classList.contains("lf-margin-lane")) return at;
  return layer.root;
};
// The page's sideways scroll as the last pass placed rows.
let laidOutScrollX = 0;
// Where the scroll reading finds a row standing, as offsets from its target's shown
// extent, which every scroll around the target moves with it as it moves the row.
const standsBy = new WeakMap();

// Every actual scrollport, including an inner table and a shadow root's scroller.
// Reading-region identity decides the clip lane, not which ancestors can move words.
function scrollSources(node) {
  const sources = [];
  for (
    let at = renderedParent(node);
    at && at !== pageScroller;
    at = renderedParent(at)
  ) {
    if (scrollsContent(at)) sources.push(at);
  }
  return sources;
}

// What a row for `subject` stands in a carrier anchored to, or null for a row the root
// lane's document coordinates carry: the subject's own box where something between it
// and its innermost scroller is sticky, fixed or absolute, else what that scroller's
// scroll carries beside it. A row in a bounded region always has a carrier, since its
// lane is a frame the region's scroll does not carry. The document's scroll carries an
// absolute box with everything else, so there only a sticky or fixed one parts a row
// from the root lane.
const stuckOrFixed = (node) => {
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

// The margin follows `main` or, on a page without one, the body.
export const marginColumn = () => layoutBox() || document.body;

// Where the rows `scroller` scrolls stand: the bounded blocks around them, innermost
// first, each by the box that scrolls it (`blocks`), and the box whose flow holds the
// outermost (`flow`). A bounded block scrolls inside the box around it as a paragraph
// does, so the flow is the first box out that is not one: the page, or a pane.
export const flowOf = (scroller) => {
  const blocks = [];
  for (let block; (block = boundedBlockOf(scroller));) {
    blocks.push(scroller);
    scroller = scrollerFor(upFrom(block));
  }
  return { blocks, flow: scroller };
};
// The rail lies beside the column, so it stands beside the rows of what flows in the
// column: the document's own, and a bounded block's. A pane is not in that flow, so its
// rows pin wherever it stands.
const railBeside = (scroller) => flowOf(scroller).flow === pageScroller;
// Prospective placement measures the same primitive a first contribution will draw.
// The native cascade resolves the entry's aim floor and the row's focus clearance,
// including package or author overrides. No existing entry, cached size, or parsed
// token expression can supply that allocation on a page's first comment.
const railMeasureRow = document.createElement("div");
railMeasureRow.className = "lf-margin-cluster";
railMeasureRow.dataset.lfPlace = "rail";
railMeasureRow.inert = true;
railMeasureRow.setAttribute("aria-hidden", "true");
railMeasureRow.style.visibility = "hidden";
const railMeasureEntry = document.createElement("button");
railMeasureEntry.className = "lf-margin-entry";
railMeasureEntry.type = "button";
railMeasureEntry.dataset.lfBehavior = "disclosure";
railMeasureRow.append(railMeasureEntry);
function restingRail() {
  // A live single-entry row is already the native primitive we need. Multi-entry
  // clusters allocate a different width, so they cannot stand in for a new row.
  for (const row of layer.root.parentElement.querySelectorAll(
    '.lf-margin-cluster[data-lf-place="rail"]',
  )) {
    if (!row.checkVisibility()) continue;
    const children = [...row.children].filter((child) => child.checkVisibility());
    if (children.length === 1 && children[0].matches(".lf-margin-entry"))
      return { entry: children[0].offsetWidth, row: row.getBoundingClientRect().width };
  }
  // Append and remove within this synchronous read, so the measuring primitive
  // never paints or enters the keyboard route. Chrome mutations do not invalidate
  // the page targets observed below.
  // With no contributions the real projection is hidden. Its shallow clone keeps
  // the same styling ancestry while measuring outside that hidden subtree.
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

// Where across the page the margin row for a comment on `target` stands, at `point`
// inside it if a pointing gesture named one (pointed-place.js), or by the `passage` it
// quotes (a range), each of which stands a row of its own: the row standing there
// now where one is shown, else where a rail row would stand at rest, `--rail-hang` off
// `main`'s edge and one entry wide, and nothing where the rail does not stand beside
// `target`, whose rows are pins placed as they come. comment-placement.js keeps this
// row clear when the full preferred message width fits beyond it; otherwise the
// message takes priority over marker clearance.
export function marginSpot(target, point = null, passage = null) {
  for (const [row, options] of rows)
    if (
      options.anchor?.() === target &&
      (options.point?.() ?? null) === point &&
      samePassage(options.passage?.() ?? null, passage) &&
      row.checkVisibility()
    ) {
      const { left, right } = row.getBoundingClientRect();
      return { left, right };
    }
  const main = marginColumn();
  if (!layer || !railStands(main) || !railBeside(scrollerFor(target))) return null;
  const hang =
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--rail-hang"),
    ) || 0;
  const left = proseRect(main).right + hang;
  return { left, right: left + restingRail().row };
}

// The boxes of the words a row's comments quote, where it stands by a passage rather
// than a pointed row (none otherwise): the subject both the layout pass and a scroll's
// reading of visibility measure.
function quotedBoxes(options) {
  if (options.point?.()) return [];
  return passageBoxes(options.passage?.() ?? null);
}

// Whether a row's passage (a resolved anchor, or none) is the range `words` (or none).
function samePassage(passage, words) {
  const range = passage && targetRange(passage);
  if (!range || !words) return !passage && !words;
  return (
    range.startContainer === words.startContainer &&
    range.startOffset === words.startOffset &&
    range.endContainer === words.endContainer &&
    range.endOffset === words.endOffset
  );
}

export function syncMarginContentLayout(changed) {
  if (changed) scheduleMarginLayout();
}

const labelRect = (name, left, top, label) => ({
  name,
  rect: {
    left,
    right: left + label.width,
    top,
    bottom: top + label.height,
  },
});

function placeMarginEntryLabel(control) {
  const label = control.querySelector(":scope > .lf-margin-entry-label");
  if (!label || !control.checkVisibility()) {
    keeps(control, "data-lf-label-side", null);
    return;
  }
  const marginEntryBox = control.getBoundingClientRect();
  const labelBox = label.getBoundingClientRect();
  // The window the page shows, over the floating panel's room (geometry.js).
  const room = shownWindow({ gap: 4 });
  const edgeAligned = Math.max(
    room.left,
    Math.min(marginEntryBox.right - labelBox.width, room.right - labelBox.width),
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
  const [below, above, after, before] = [
    labelRect("below", edgeAligned, marginEntryBox.bottom + 6, labelBox),
    labelRect("above", edgeAligned, marginEntryBox.top - 6 - labelBox.height, labelBox),
    labelRect("after", clusterRight + 6, centered, labelBox),
    labelRect("before", clusterLeft - 6 - labelBox.width, centered, labelBox),
  ];
  // A finger holding the entry to read its label covers what lies below it.
  const candidates = coarsePointer.matches
    ? [above, before, after, below]
    : [below, above, after, before];
  const blockers = [
    ...document.querySelectorAll(".lf-margin-projection .lf-margin-entry"),
  ]
    .filter((candidate) => candidate !== control && candidate.checkVisibility())
    .map((candidate) => candidate.getBoundingClientRect());
  const fits = ({ rect }) =>
    rect.left >= room.left &&
    rect.right <= room.right &&
    rect.top >= room.top &&
    rect.bottom <= room.bottom;
  const choice =
    candidates.find(
      (candidate) =>
        fits(candidate) &&
        !blockers.some((blocker) => overlaps(candidate.rect, blocker)),
    ) ??
    candidates.find(fits) ??
    candidates[0];
  setStyle(
    label,
    "--lf-label-x",
    layoutPx(choice.rect.left - marginEntryBox.left - control.clientLeft),
  );
  setStyle(
    label,
    "--lf-label-y",
    layoutPx(choice.rect.top - marginEntryBox.top - control.clientTop),
  );
  keeps(control, "data-lf-label-side", choice.name);
}

// What reveals a margin entry's label, as the theme's rules for it say: a press held on
// it (held-word.js), the selected obligation, and focus or hover where the pointer
// really hovers. Elsewhere a tap leaves the entry hovered and focused, so only the
// keyboard's focus reveals a label on an unselected entry.
const revealsLabel = () =>
  '[data-lf-kinds~="on-me"][data-lf-target-selected], ' +
  (hoveringPointer.matches
    ? ':is(:hover, [data-lf-focus]):not([aria-expanded="true"]), [data-lf-held-word]'
    : '[data-lf-focus]:focus-visible:not([aria-expanded="true"]), [data-lf-held-word]');
// Only a label this owner has placed and its control currently reveals paints a
// footprint. Placement consumers read that same native geometry when the user holds
// the control, so an arriving row does not make its existing label change sides.
function heldLabelBoxes(row) {
  return [...row.querySelectorAll(".lf-margin-entry[data-lf-label-side]")]
    .filter((control) => control.matches(revealsLabel()))
    .map((control) =>
      control.querySelector(":scope > .lf-margin-entry-label").getBoundingClientRect(),
    );
}
let labelPlacementFrame = 0;
export function scheduleMarginEntryLabels() {
  if (labelPlacementFrame) return;
  labelPlacementFrame = nextRender(() => {
    labelPlacementFrame = 0;
    for (const control of document.querySelectorAll(
      `.lf-margin-projection .lf-margin-entry:is(${revealsLabel()}, [data-lf-label-side])`,
    )) {
      if (control.matches(revealsLabel())) placeMarginEntryLabel(control);
      else keeps(control, "data-lf-label-side", null);
    }
  });
}

// The layer's root lane, where rows whose targets scroll with the document stand, and one
// lane per bounded reading region, keyed by the box that scrolls it. A scroll anywhere
// but the document's may take a target out of view or bring it back, so it is heard once,
// here, rather than per lane: a table or a board scrolled sideways is no lane of its own.
export function mountMarginLayer(root) {
  layer = { root, lanes: new Map(), sizes: sizeObserver(layoutMarginRows) };
  hearTargetChanges(document);
}

// Neither scroll events nor mutation records leave their shadow tree, so a target
// inside one is heard on each tree holding it as well as on the document.
const heard = new WeakSet();
function hearTargetChanges(root) {
  if (heard.has(root)) return;
  heard.add(root);
  root.addEventListener(LAYOUT, scheduleMarginLayout);
  root.addEventListener("slotchange", scheduleMarginLayout);
  // Resize delivery follows layout. A target or its anchored part removed by a widget
  // would therefore paint the row's fallback before the next layout pass withheld it.
  // Child-list changes in the measured layout can move a target without resizing it,
  // including when native scroll anchoring preserves its viewport position.
  // Hear those changes and target moves at their mutation checkpoint, before paint;
  // a remove-and-reinsert in one batch is a move, not a departure.
  new MutationObserver((records) => {
    if (
      records.some(
        (record) =>
          !inChrome(record.target) &&
          (record.type === "attributes" ||
            (record.type === "childList" && wantedGeometry.has(record.target))),
      )
    )
      afterScript(layoutMarginRows);
    const moved = records
      .flatMap((record) => [...record.removedNodes, ...record.addedNodes])
      .filter((node) => node instanceof Element);
    for (const [row, options] of rows) {
      const target = options.anchor();
      const anchor = anchors.get(row);
      if (!moved.some((node) => under(target, node) || under(anchor, node))) continue;
      if (!target?.isConnected || (anchor && !anchor.isConnected))
        row.classList.toggle("lf-withheld", true);
      scheduleMarginLayout();
    }
  }).observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class", "hidden", "open"],
  });
  root.addEventListener(
    "scroll",
    (event) => {
      const source = event.target === document ? pageScroller : event.target;
      if (!(source instanceof Element)) return;
      scrolled.add(source);
      scheduleScrollReading();
    },
    { capture: true, passive: true },
  );
}

// A bounded region's lane is the innermost of the frames its region is cut by
// (`cutFrames`), each a lane box too, so the lane holding the pointer or focus rises
// through every frame around it (annotation-chrome.css).
const laneFrames = new Map(); // lane → its frames, outermost first, itself last
const makeLaneFrame = () => {
  const frame = document.createElement("div");
  frame.className = "lf-margin-lane";
  return frame;
};
function laneFor(scroller) {
  if (scroller === pageScroller) return layer.root;
  let lane = layer.lanes.get(scroller);
  if (!lane) {
    lane = makeLaneFrame();
    // Keep every materialized lane beside the root margin layer, before the native
    // foreground whose key chips may anchor to these rows.
    layer.root.after(lane);
    layer.lanes.set(scroller, lane);
    laneFrames.set(lane, [lane]);
    layer.sizes.observe(scroller);
  }
  return lane;
}

const EVERYWHERE = {
  left: -Infinity,
  top: -Infinity,
  right: Infinity,
  bottom: Infinity,
};

// How far right the figure a target belongs to reaches: the furthest of its own box and
// the boxes holding it inside `main`, so a card in a board grown past the rail stands its
// comment on the board as a figure does. Read off the boxes rather than the declared
// widths, so a block an agent widened with its own CSS counts too. A scroller cuts what
// it holds to what it shows: a cell far along a wide table is not a figure past the rail.
function reach(anchor, box, main, reaches) {
  let right = box.right;
  for (let el = renderedParent(anchor); el && el !== main; el = renderedParent(el)) {
    let edge = reaches.get(el);
    if (edge === undefined) {
      const b = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      // Named document tracks include free margins; a subgrid carrying those
      // tracks is the page's flow, not a figure extending into its rail. The
      // target's own box and ordinary framed ancestors still count in full.
      const tracks =
        style.gridTemplateColumns.includes("prose-start") ||
        (style.gridTemplateColumns.startsWith("subgrid") &&
          style.gridColumnStart === "full");
      edge = {
        right: tracks ? -Infinity : b.right,
        clip:
          style.overflowX === "visible"
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

// The boxes a pin's target is drawn in: one per line for a run of text, so the room at the
// end of the line it ends on is seen as room rather than as part of its extent.
function partsOf(target) {
  return shownParts(target)
    .flatMap((part) => [...part.getClientRects()])
    .filter((box) => box.width && box.height);
}

// What a pin keeps off across a band of the page (`cover`): every run of words, as far
// as the boxes holding it show it (a word clipped to nothing for a screen reader alone,
// as `.lf-quiet` is, covers nothing), each box that paints what no text node says (an
// image, a drawing, a widget's shadow tree), and every control, which `controls` also
// lists, since a pin with no clear seat may stand over words but not over a control a
// press would then miss. A box's fill, rule or shadow is not cover: a pin over the empty
// part of a card hides nothing. The target, and a box that holds it, are not ones to
// avoid, since the pin stands on them. The walk leaves any subtree whose box misses the
// band, so a long page costs what lies near the target.
//
// Anything the keyboard can reach is a control, so a package need declare nothing.
// Every covered box counts as the part its own scrollers show, short of the one that
// scrolls the pin (`stop`): a pin can take no press from a control nobody can see, as a
// pane body's options scrolled behind the pane's footer, but a control scrolled with the
// pin counts whole, so the pane's scroll never moves the pin's seat.
//
// It also answers whether another block stands at a seat (`beside`): a shown box that
// is not the target's, does not hold it, and is not a run of words, since an inline
// box spans the empty ends of its lines and its words are cover already. A pin in a
// neighbour's box reads as the neighbour's even over its empty padding, as a card's pin
// in the gap between board columns reads as the next column's card (`seatsBy`). Only
// the boxes a seat meets are read further, so the walk costs one rect per element.
const OPAQUE = "img, svg, canvas, video, iframe, object, embed";

// Every control that paints inside a shadow host: the rendered tree beneath it, through
// its shadow trees and whatever their slots are assigned, forwarded slots included.
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
  const boxes = [];
  const meets = (box) => box.bottom > band.top && box.top < band.bottom;
  const visit = (el) => {
    for (const node of renderedChildren(el)) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.data.trim()) continue;
        const words = document.createRange();
        words.selectNodeContents(node);
        for (const box of words.getClientRects()) {
          if (!meets(box)) continue;
          const shown = clippedContents(box, renderedParent(node), bands, stop);
          if (shown && shown.right - shown.left > 1 && shown.bottom - shown.top > 1)
            cover.push(shown);
        }
        continue;
      }
      if (node.nodeType !== Node.ELEMENT_NODE || node.closest(".lf-chrome")) continue;
      if (skipped(node)) continue;
      const box = node.getBoundingClientRect();
      const boxless = !box.width && !box.height;
      if (!boxless && !meets(box)) continue;
      const holds = node !== target && renderedUnder(target, node);
      if (!boxless && !holds && node !== target) boxes.push({ node, box });
      const control = node.matches(TAB_STOP);
      if (
        !boxless &&
        !holds &&
        (node.shadowRoot || node.matches(OPAQUE) || control) &&
        node.checkVisibility()
      ) {
        const shown = clippedRect(box, node, bands, stop);
        if (shown) cover.push(shown);
        if (shown && control) controls.push(shown);
        // A widget's own buttons stand in its shadow tree, or are slotted into it, out
        // of the walk's reach.
        for (const inner of node.shadowRoot ? controlsIn(node) : []) {
          if (!inner.checkVisibility()) continue;
          const part = clippedRect(inner.getBoundingClientRect(), inner, bands, stop);
          if (part) controls.push(part);
        }
        continue;
      }
      if (node instanceof SVGElement) continue;
      // The container can draw its own box while skipping its children, including
      // bare text which has no element to ask `skipped` of on the next step.
      if (getComputedStyle(node).contentVisibility === "hidden") continue;
      // A closed disclosure draws only its summary; reading the rest would force its
      // skipped content's layout (`skipped`).
      if (node.localName === "details" && !node.open) {
        const summary = node.querySelector(":scope > summary");
        if (summary) visit({ childNodes: [summary] });
        continue;
      }
      visit(node);
    }
  };
  visit(root);
  const beside = (seat) =>
    boxes.some(({ node, box }) => {
      if (!overlaps(box, seat) || getComputedStyle(node).display === "inline")
        return false;
      if (renderedUnder(node, target) || !node.checkVisibility()) return false;
      const shown = clippedRect(box, node, bands, stop);
      return Boolean(shown) && overlaps(shown, seat);
    });
  return { cover, controls, beside };
}

// The whole content a scroller scrolls, wherever it is scrolled to: a pin in a pane is
// seated inside it, so its seat is the same at every scroll.
function contentBox(scroller) {
  const box = scroller.getBoundingClientRect();
  const left = box.left + scroller.clientLeft - scroller.scrollLeft;
  const top = box.top + scroller.clientTop - scroller.scrollTop;
  return {
    left,
    top,
    right: left + Math.max(scroller.scrollWidth, scroller.clientWidth),
    bottom: top + Math.max(scroller.scrollHeight, scroller.clientHeight),
  };
}

// Each pin's seat, measured from the box it anchors to, as the last pass took it: a pin
// under the pointer or holding focus keeps it (`seatRows`), and a scroll inside a pane
// reads it to say whether the pin still stands inside what the pane shows.
const seats = new WeakMap();

// The rows the last pass stood folded (`seatRows`). This is the one reading of it: the
// projection presents a row folded by asking `standsFolded`, and a row's `fold.changed`
// tells it to ask again.
const folded = new WeakSet();
export const standsFolded = (row) => folded.has(row);

// Where `part` of `row`, or the row itself, is painted. A carried row's own box reads a
// frame late after a scroll (`scheduleScrollReading`), so it is read where the row's
// target now stands, by the offsets the last pass seated the row at (`standsBy`): the
// place the browser moved it to in the frame that scrolled it. Any other row's box is
// where it is painted.
export function paintedBox(part, row) {
  const box = part.getBoundingClientRect();
  const by = standsBy.get(row);
  const target = by && isCarrier(row.parentElement) ? rows.get(row)?.anchor() : null;
  if (!target?.isConnected || skipped(target)) return box;
  const whole = shownExtent(target);
  if (!whole) return box;
  const own = part === row ? box : row.getBoundingClientRect();
  const across = row.dataset.lfPlace === "pin" ? whole.right + by.right - own.right : 0;
  return new DOMRect(
    box.x + across,
    box.y + whole.top + by.top - own.top,
    box.width,
    box.height,
  );
}

function standFolded(row, fold, on) {
  if (folded.has(row) === on) return;
  if (on) folded.add(row);
  else folded.delete(row);
  fold?.changed();
}

// Prepares every pin's seats and what they must keep off, then supplies its posture
// solver to the shared seating order. Each pin avoids the final rows and held labels
// already placed, and writes its final seat into the entry's rect. The walk crosses the
// shadow hosts holding the target, so their words and controls bound its seat just as
// the document's do.
//
// A pin's seats, in the order it takes them, all touch its target (`seatRows`): just
// outside the target's top-right corner; for a run of text or a quoted passage, whose
// corner is its own words' rather than the block's, just after its last word, where a
// reader finishes it (each of these two only where no other block stands level with
// it, since a pin in a neighbour's box reads as the neighbour's, `seatsBy`); just
// inside the corner, on the
// target itself, or further down its right edge; then just above that inside seat,
// which keeps the inset from the window's edge, so a target as wide as the window
// still has room above it (a run of words' hangs off its top-right corner instead,
// where the pin's pointed foot meets it); and last just below its bottom-right
// corner, at the same inset, where nothing stands level with it under the target.
// Above and below come last because a pin there can read as the neighbouring block's,
// and above stands outside what a pane shows when the pane is scrolled to its target.
// Below is the one seat clear beside a full-width figure or keypad that sits right
// under a paragraph. A quoted passage's pin then tries the same seats by the block
// holding it, so it covers words only where the block's do too.
//
// A row that can fold (its `fold.able()`, margin-projection.js) is seated at both sizes,
// which are worked out rather than read, since only the one it stands at is drawn:
// unfolded its face is two controls, folded one, and opened `fold.controls()`, each a
// square the row's height, beside the gaps and the focus ring's room the row keeps.
function pinSeating(rows, { bands, shell, pinInset }) {
  const main = marginColumn();
  // A scrollable document can reveal seats beyond the viewport, but none above its own
  // top. A root whose overflow prevents user scrolling cannot, so its window bounds the
  // seats.
  const rootBounds = /^(hidden|clip)$/.test(getComputedStyle(pageScroller).overflowY)
    ? shownWindow({ viewport: "layout" })
    : { top: pageScroller.getBoundingClientRect().top };
  const pins = [];
  for (const entry of rows) {
    const { read } = entry;
    if (read.place !== "pin") {
      seats.delete(read.row);
      standFolded(read.row, read.options.fold, false);
      continue;
    }
    const { target, point, words, row } = read;
    const home = entry.rect;
    const height = home.bottom - home.top;
    const width = home.right - home.left;
    const fold = read.options.fold?.able() ? read.options.fold : null;
    if (!fold) standFolded(row, read.options.fold, false);
    entry.fold = fold;
    const style = fold && getComputedStyle(row);
    const across = (count) =>
      count * height +
      (count - 1) * parseFloat(style.columnGap) +
      parseFloat(style.paddingRight);
    const wide = fold ? across(2) : width;
    // A pin level with a pointed row keeps to that row, as a pin keeps to its target;
    // the row's boxes are read wherever it is drawn, a widget's shadow tree included,
    // since the walk below reads the room around the target, which is the document's.
    const parts = words ?? partsOf(point ?? target);
    // A passage's pin falls back to its block's own seats, which cover nothing more
    // often than the words' do, before it stands over words: the passage's highlight
    // already says which words it is about.
    const blockParts = words && read.block ? partsOf(target) : [];
    const block = blockParts.length > 0 && {
      parts: blockParts,
      home: {
        left: read.block.right - pinInset - width,
        right: read.block.right - pinInset,
        top: read.block.top,
        bottom: read.block.top + height,
      },
    };
    const spans = [home, ...parts, ...(block ? [block.home, ...block.parts] : [])];
    const around = height + GAP;
    const band = {
      top: Math.min(...spans.map((box) => box.top)) - around,
      bottom: Math.max(...spans.map((box) => box.bottom)) + around,
    };
    // Only what scrolls with the pin is read: in a pane, the pane's own content. The pane's
    // header, standing still above it, would enter the band as the pane scrolled the
    // target up to it, and seat the pin differently at that scroll.
    const stop = read.scroller;
    const room = coverIn(
      stop === pageScroller ? main : stop,
      band,
      target,
      bands,
      stop,
    );
    const { cover, controls } = room;
    const end = parts.at(-1);
    const inline =
      Boolean(words) ||
      (!point &&
        end &&
        target instanceof HTMLElement &&
        getComputedStyle(target).display.startsWith("inline"));
    const floor = Math.max(home.bottom, ...parts.map((part) => part.bottom));
    // Only those wholly within half the scroller's height of the words, so the pin is on
    // screen whenever its words stand mid-screen, though they are deep in a long
    // paragraph or pane.
    const reach = (stop === pageScroller ? innerHeight : stop.clientHeight) / 2;
    const near = (seat) =>
      seat.top >= Math.min(...parts.map((part) => part.top)) - reach &&
      seat.bottom <= Math.max(...parts.map((part) => part.bottom)) + reach;
    const seatsAt = (size) => [
      ...seatsBy(parts, home, inline, Boolean(words), room, size, GAP),
      ...(block
        ? seatsBy(block.parts, block.home, false, false, room, size, GAP).filter(
            (seat) => seat && near(seat),
          )
        : []),
    ];
    /** @type {{left?: number, right?: number, top: number, bottom?: number}} */
    const within = stop === pageScroller ? rootBounds : contentBox(stop);
    // A board or table can clip the target across without owning its reading region.
    // Seat only in the room it shows; otherwise the seat can leave the scroller and
    // targetShown withholds an otherwise reachable action.
    const clipped = clippedRect(EVERYWHERE, target, bands, stop);
    pins.push({
      key: entry,
      held: entry.holding ?? null,
      came: entry.came,
      seats: seatsAt(wide),
      corner: inline ? 2 : 1,
      floor,
      // A passage's own words count twice, so a pin with no clear seat covers its
      // neighbours' words before the ones it is about.
      cover: words ? [...cover, ...words] : cover,
      controls,
      folds: fold && { seats: seatsAt(across(1)), open: across(fold.controls()) },
      folded: folded.has(row),
      bounds: {
        left: Math.max(within?.left ?? 0, clipped?.left ?? 0) + pinInset,
        right: Math.min(within?.right ?? shell, clipped?.right ?? shell) - pinInset,
        top: Math.max(within?.top ?? -Infinity, clipped?.top ?? -Infinity),
        bottom: Math.min(within?.bottom ?? Infinity, clipped?.bottom ?? Infinity),
      },
    });
  }
  const byEntry = new Map(pins.map((pin) => [pin.key, pin]));
  return (entry, occupied) => {
    const pin = byEntry.get(entry);
    const { rect, folded: on } = seatRows([pin], { gap: GAP, occupied }).get(entry);
    // An open folded row is wider than its one-control seat. Keep the toggle at
    // that seat's right edge while the options spread to its left. Whether it stands
    // open is the face the fold presents (`fold.open()`), not the one the row wears
    // now: a row this pass folds was drawn with its peers inline.
    entry.visualLeft =
      on && entry.fold.open()
        ? rect.right - (entry.rect.right - entry.rect.left)
        : rect.left;
    entry.rect = rect;
    if (entry.fold) standFolded(entry.read.row, entry.fold, on);
    const attached = targetBox(entry.read.target).getBoundingClientRect();
    seats.set(entry.read.row, {
      top: rect.top - attached.top,
      right: attached.right - rect.right,
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

// Each row states its target (`anchor`), the row inside it it stands level with, if any
// (`point`, pointed-place.js), and its place among the others in the layer (`order`).
export function registerMarginRow(row, options = {}) {
  rows.set(row, options);
  observeLayout();
  scheduleMarginLayout();
}

export function unregisterMarginRow(row) {
  // The projection discards this host. Clear retained references without
  // repainting a face that will leave the document in the same turn.
  rows.delete(row);
  anchors.delete(row);
  pushes.delete(row);
  folded.delete(row);
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }
  scheduleMarginLayout();
}

// A style property written, or removed for null. The platform makes no write of a
// value the property already holds (keeps.js).
function setStyle(row, property, value) {
  if (value === null) row.style.removeProperty(property);
  else row.style.setProperty(property, value);
}

// Whether a row has somewhere to stand: its target renders, its scrollers leave some of
// it in view — the pane that scrolls it, a table or board it has been scrolled sideways
// out of, or a scroller inside the shadow tree it anchors through, which can take the
// target away while the host it anchors through still shows — and the row itself stands
// inside what those scrollers show. `stands` is where the row stands: a rail row's top is
// its target's, and a pin's is its seat, which may lie above or beside its target. Its top
// line counts, since a row standing above a pane's top would be clipped by its lane and
// still take the keyboard, and for a pin its right edge too: a card half past a board's
// edge would stand its pin outside the board, beside nothing and past the page. A pin not
// yet seated passes `stands` null, and is asked again once it is. `extent` is what shows
// of the target, or of the passage a row quotes, and none where its scrollers show none.
function targetShown(target, extent, stands, bands) {
  const shown = (part) =>
    part.checkVisibility() &&
    clippedRect(part.getBoundingClientRect(), part, bands, pageScroller);
  if (!visibleTargetParts(target).some(shown)) return false;
  if (!extent || !clippedRect(extent, target, bands, pageScroller)) return false;
  if (!stands) return true;
  const view = clippedRect(EVERYWHERE, target, bands, pageScroller);
  return (
    stands.top >= view.top - 1 &&
    (stands.right === undefined || stands.right <= view.right + 1)
  );
}

const pushes = new Map();
// The layout pass each row came at (`arrivals`). One shared order seats held rows
// first, then earlier arrivals, across both postures. Each row takes the room left
// by final rectangles already seated: news moves nothing already seated.
let pass = 0;
let came = new Map();
// A scroll inside anything but the document moves its rows in the frame that scrolls
// them. What it can change is which of them still have somewhere to stand, so only rows
// under a box that scrolled are read again, once a frame, and a row that changes answer
// brings the whole pass, which places it, scrollers inside shadow trees included.
const scrolled = new Set();
let scrollReading = 0;
function scheduleScrollReading() {
  if (scrollReading) return;
  scrollReading = nextRender(() => {
    scrollReading = 0;
    const boxes = [...scrolled];
    scrolled.clear();
    if (
      boxes.includes(pageScroller) &&
      scrollX !== laidOutScrollX &&
      [...carriers.values()].some((byAnchor) =>
        [...byAnchor.values()].some((held) => held.y.length),
      )
    ) {
      scheduleMarginLayout();
      return;
    }
    const bands = new Map();
    for (const [row, options] of rows) {
      const target = options.anchor();
      if (!target?.isConnected) continue;
      const moving = boxes.some((box) => {
        for (let at = target; at; at = renderedParent(at)) if (at === box) return true;
        return false;
      });
      if (!moving) continue;
      // The document carries ordinary rows and their lanes together.
      if (
        !row.classList.contains("lf-withheld") &&
        boxes.every((box) => box === pageScroller)
      )
        continue;
      const whole = shownExtent(target);
      const words = quotedBoxes(options);
      // The row's own box is not read: a carried row's box is read a frame late
      // after a scroll, which is not where it is painted.
      const by = standsBy.get(row);
      const stands =
        row.classList.contains("lf-withheld") || !whole || !by
          ? null
          : row.dataset.lfPlace === "pin"
            ? { top: whole.top + by.top, right: whole.right + by.right }
            : { top: whole.top + by.top };
      if (
        targetShown(target, words.length ? union(words) : whole, stands, bands) ===
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
  pass += 1;
  laidOutScrollX = scrollX;
  const present = [];
  const main = marginColumn();
  const columnRect = proseRect(main);
  const columnHeight = main.scrollHeight;
  const shell = shellRight();
  const stands = railStands(main);
  const rootStyle = getComputedStyle(document.documentElement);
  const hang = parseFloat(rootStyle.getPropertyValue("--rail-hang")) || 0;
  const pinInset = parseFloat(rootStyle.getPropertyValue("--pin-inset")) || 0;
  const railInner = columnRect.right + hang;
  // The half that decides rail or pin is a rail marker's: a pin's entries are smaller.
  // Read once a row could stand in the rail, since every other row pins whatever the
  // size, and with no rail entry live the reading inserts and removes a measuring
  // clone, which restyles the whole document (`restingRail`).
  let railEntry;
  const railEntrySize = () =>
    (railEntry ??=
      layer.root.parentElement.querySelector(
        '.lf-margin-cluster:not([data-lf-place="pin"]) .lf-margin-entry:not([hidden])',
      )?.offsetWidth || restingRail().entry);
  // The notes hanging in the margin the rail stands in (layouts.css, layout-note): a
  // marker level with one would be drawn over it.
  const notes = [...main.querySelectorAll(".layout-note > aside")]
    .filter((note) => !skipped(note))
    .map((note) => note.getBoundingClientRect())
    .filter((note) => note.width && note.left >= columnRect.right - 1);

  // Every read before any write: a write between two reads forces a layout per row.
  const bands = new Map();
  const reaches = new Map();
  const reads = [];
  const geometry = new Set();
  const parents = new Set();
  function observeGeometry(target) {
    for (let at = target; at && at !== pageScroller; at = renderedParent(at)) {
      if (at instanceof Element) {
        geometry.add(at);
        // Scroll and slot changes stay in their shadow tree. A slotted target's
        // own root is the document; the rendered walk reaches the roots that
        // actually move and clip it, and re-arms them after a slot or parent move.
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
  const carrierNames = new Map();
  const cutClips = new Map();
  for (const [row, options] of rows) {
    const target = options.anchor();
    if (!target?.isConnected) {
      present.push({ row, at: null });
      reads.push({ row, options, lane: layer.root, shown: false });
      continue;
    }
    // A target in skipped content — a tab not chosen, a closed disclosure — has nowhere
    // to stand, and every reading below would force that content's style and layout to
    // say so (`skipped`). Withheld like a target that has gone, it is anchored by the
    // pass that runs once it is drawn, and keeps the lane it stands in meanwhile, so a
    // tab switch does not move the rows of a reading region's hidden panels between
    // lanes.
    if (skipped(target)) {
      present.push({ row, at: null });
      const home = row.parentElement ?? layer.root;
      const container = isCarrier(home) ? home.parentElement : home;
      reads.push({
        row,
        options,
        lane: laneOf(container),
        container,
        home,
        shown: false,
      });
      continue;
    }
    const anchor = targetBox(target);
    anchors.set(row, anchor);
    // Level with the row a gesture pointed into, where the row's comment has one
    // (pointed-place.js), or with the first line of the passage its comments quote;
    // otherwise level with the target's top.
    const point = options.point?.() ?? null;
    const words = quotedBoxes(options);
    const passageNode = words.length
      ? targetSegments(options.passage?.())[0]?.node
      : null;
    observeGeometry(point ?? target);
    present.push({
      row,
      at: point ?? passageNode ?? target,
    });
    const scroller = scrollerFor(target);
    const rootLane = scroller === pageScroller;
    const box = anchor.getBoundingClientRect();
    const whole = shownExtent(target);
    // A passage's row is about its words, so it stands within what shows of them and
    // is withheld once they are scrolled away, though the rest of the target shows.
    const block = whole && clippedRect(whole, target, bands, scroller);
    const extent = words.length
      ? whole && clippedRect(union(words), target, bands, scroller)
      : block;
    const line = point?.getBoundingClientRect() ?? words[0];
    const top =
      extent && line ? clamp(line.top, extent.top, extent.bottom) : extent?.top;
    const level = line ? top : box.top;
    const besideRail = railBeside(scroller);
    const size = stands && besideRail ? railEntrySize() : 0;
    const place = rowPlacement({
      railStands: stands,
      besideRail,
      blockRight: reach(anchor, box, main, reaches),
      railInner,
      half: size / 2,
      noted: notes.some((note) => note.top < level + size && note.bottom > level),
    });
    const shown = targetShown(target, extent, place === "pin" ? null : { top }, bands);
    reads.push({
      row,
      options,
      target,
      point,
      words: words.length ? words : null,
      passageNode,
      block,
      anchor,
      whole,
      scroller,
      lane: rootLane ? layer.root : null,
      shown,
      place,
      box,
      extent,
      top,
    });
  }
  came = arrivals(came, present, pass);
  // Posture determines row size. Write every posture before measuring those sizes;
  // every coordinate is then written together after packing.
  for (const { row, target, shown, place } of reads) {
    row.classList.toggle("lf-withheld", !shown);
    if (!target) continue;
    if (row.dataset.lfPlace !== place) {
      // A push in one posture says nothing of where the row stands in the other.
      pushes.delete(row);
      row.dataset.lfPlace = place;
    }
  }

  // Packing reads every row's size, then writes all coordinates together. Position
  // comes directly from the target reading, independently of the row's previous spot.
  /**
   * A shown row as packing reads it; seating adds where a held pin stands, how far a
   * rail row steps back, and whether a pin found no seat (`pinSeating`).
   * @typedef {{
   *   key: Element,
   *   rect: {left: number, right: number, top: number, bottom: number},
   *   held: boolean,
   *   came: any,
   *   pushed: any,
   *   read: any,
   *   holding?: {left: number, right: number, top: number, bottom: number},
   *   step?: number,
   *   unseated?: boolean,
   *   visualLeft?: number,
   * }} PlacedRow
   */
  /** @type {PlacedRow[]} */
  const placed = reads
    .filter((read) => read.shown)
    .map((read) => {
      const box = read.row.getBoundingClientRect();
      return {
        key: read.row,
        rect: {
          left:
            read.place === "pin" ? read.extent.right - pinInset - box.width : railInner,
          right:
            read.place === "pin" ? read.extent.right - pinInset : railInner + box.width,
          top: read.top,
          bottom: read.top + box.height,
        },
        // Held where it stands, which a row has only once it has stood in its posture:
        // one that has just come, or just changed posture, takes its place as any other.
        held: pushes.has(read.row) && read.row.matches(HELD),
        came: came.get(read.row),
        pushed: pushes.get(read.row),
        read,
      };
    });
  // Read retained pin footprints once for their posture solver. The shared seating
  // order retains held rows before either posture takes any remaining room.
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
      bottom: heldBox.top + seat.top + height,
    };
  }
  const seatPin = pinSeating(placed, { bands, shell, pinInset });
  const occupied = [];
  const packed = new Map();
  // One held-and-arrival order owns both postures. A posture solver produces its final
  // rectangle once; later rows avoid it rather than translating an earlier clear seat.
  for (const entry of inSeatingOrder(placed)) {
    if (entry.read.place === "rail") {
      // A widened rail steps back from the shell before collision solving, so the
      // occupied rectangle is exactly the one the stylesheet will paint.
      entry.step = Math.min(0, shell - entry.rect.right);
      const rect = {
        ...entry.rect,
        left: entry.rect.left + entry.step,
        right: entry.rect.right + entry.step,
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
    read.carrier =
      (read.passageNode && anchorFor(read.passageNode)) ??
      carrierAnchor(subject, scrollSources(subject), read.scroller);
    // The headers over the target cut its row, in frames the document's own scroll
    // does not carry, so a row they cut stands in a carrier the document's scroll does.
    read.cuts = headerLevels(subject, cutClips);
    read.cutKey = read.cuts
      .map(({ anchor, band, at }) =>
        anchor
          ? `${idOf(anchor)}:${band.top - at.top}:${band.bottom - at.top}`
          : `window:${band.top}:${band.bottom}`,
      )
      .join("|");
    if (read.cuts.length)
      read.carrier ??= carriedAnchor(pageScroller) ?? anchorElement(targetBox(subject));
    read.carrierBox = read.carrier && anchorBox(read.carrier);
    read.lane = read.scroller === pageScroller ? layer.root : null;
    if (read.carrier && !carrierNames.has(read.carrier))
      carrierNames.set(read.carrier, anchorReading(read.carrier));
  }
  // The frames each lane's region is cut by: one per scroller around it, outermost
  // first, then the region's own, each cut to what its box shows short of the next
  // scroller out but not by the window, so a pane below the fold is cut where its own
  // edges will be when it arrives. The region's frame reaches a focus ring past its
  // sides, and across to the rail where the rail stands beside it.
  const regions = new Map();
  const ring = 6;
  for (const read of reads)
    if (
      read.scroller &&
      read.scroller !== pageScroller &&
      !regions.has(read.scroller)
    ) {
      const holders = [read.scroller, ...scrollSources(read.scroller)];
      const rail = stands && railBeside(read.scroller);
      const levels = holders
        .map((holder, i) => {
          const band = clippedRect(
            shownBand(holder) ?? holder.getBoundingClientRect(),
            holder,
            bands,
            holders[i + 1] ?? pageScroller,
          );
          const anchor = anchorElement(holder);
          const axes = i
            ? clippingAxes(getComputedStyle(holder))
            : { x: true, y: true };
          return {
            anchor,
            reading: anchorReading(anchor),
            at: anchorBox(anchor),
            band: !band
              ? null
              : i
                ? band
                : {
                    ...band,
                    left: band.left - ring,
                    right: (rail ? shell : band.right) + ring,
                  },
            axes: rail ? { ...axes, x: false } : axes,
          };
        })
        .reverse();
      if (rail) levels.at(-1).axes = { x: true, y: true };
      regions.set(read.scroller, levels);
    }
  watchGeometry(geometry);

  // Lanes, in the order the rows are given, moving only what is out of place; each lane
  // after the last, so the tab order runs the lanes as the rows run.
  for (const read of reads) read.lane ??= laneFor(read.scroller);
  const byLane = new Map();
  for (const read of [...reads].sort(
    (a, b) => (a.options.order ?? 0) - (b.options.order ?? 0),
  ))
    byLane.set(read.lane, [...(byLane.get(read.lane) ?? []), read]);
  // Each lane stands in its frames, which a region cut to nothing leaves empty.
  for (const [scroller, lane] of layer.lanes) {
    const levels = regions.get(scroller);
    if (!levels) continue;
    const hidden = { left: 0, top: 0, right: 0, bottom: 0 };
    laneFrames.set(
      lane,
      cutFrames(
        levels.map((level) => ({ ...level, band: level.band ?? hidden })),
        laneFrames.get(lane),
        makeLaneFrame,
      ),
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
    // Each home's next place: the lane's own, each run of header frames', which stands
    // in the lane where its run of rows comes, and each carrier's, which stands in the
    // lane or those frames where its run comes.
    const cursors = new Map([[lane, lane.firstElementChild]]);
    // A row can leave this lane for a cut or carrier before we reach the next
    // row in it. Advance its cursor while the departing row still has a sibling.
    const place = (holder, node, before) => {
      const oldHome = node.parentElement;
      if (oldHome && cursors.get(oldHome) === node)
        cursors.set(oldHome, node.nextElementSibling);
      move(holder, node, before);
    };
    const runs = new Map();
    const cutRuns = new Map();
    // A withheld row keeps its carrier and frames where they stand, so a shown row
    // allocating a run takes the next one they leave free, keeping document order.
    const kept = new Set(
      members
        .filter((read) => !read.target)
        .flatMap(({ home, container }) => [home, container])
        .filter(Boolean),
    );
    let previous = null;
    for (const read of members) {
      const { row } = read;
      if (read.target) {
        if (!read.cutKey) read.container = lane;
        else if (previous?.cutKey === read.cutKey && previous.container !== lane)
          read.container = previous.container;
        else {
          const held = cutFramesByKey.get(`${idOf(lane)}|${read.cutKey}`) ?? [];
          let run = cutRuns.get(read.cutKey) ?? 0;
          while (kept.has(held[run])) run += 1;
          cutRuns.set(read.cutKey, run + 1);
          read.container = cutRun(lane, read, run);
        }
        const axes = read.place === "rail" ? "y" : "xy";
        if (!read.carrier) read.home = lane;
        else if (
          previous?.carrier === read.carrier &&
          previous.axes === axes &&
          previous.container === read.container
        )
          read.home = previous.home;
        else {
          const key = carrierFor(read.container, read.carrier, axes, 0);
          let run = runs.get(key) ?? 0;
          while (kept.has(carrierFor(read.container, read.carrier, axes, run)))
            run += 1;
          runs.set(key, run + 1);
          read.home = carrierFor(read.container, read.carrier, axes, run);
        }
        read.axes = axes;
      }
      previous = read;
      const container = read.container ?? lane;
      const home = read.home ?? lane;
      // Each box takes its place in the one holding it at that box's cursor.
      const seat = (holder, box, outer = box) => {
        if (cursors.has(box)) return;
        let at = cursors.get(holder);
        if (at && at.parentElement !== holder) at = null;
        if (at === outer) cursors.set(holder, outer.nextElementSibling);
        else place(holder, outer, at);
        cursors.set(box, box.firstElementChild);
      };
      if (container !== lane) seat(lane, container, outerFrame.get(container));
      if (home !== container) seat(container, home);
      let before = cursors.get(home);
      // A row this pass moved to another home no longer marks a place in this one.
      if (before && before.parentElement !== home) before = null;
      if (before === row) {
        cursors.set(home, row.nextElementSibling);
        continue;
      }
      place(home, row, before);
      cursors.set(home, before);
    }
  }
  for (const [holder, byAnchor] of carriers) {
    for (const [anchor, held] of byAnchor) {
      for (const axes of ["xy", "y"])
        held[axes] = held[axes].filter((carrier) => {
          if (carrier.isConnected && carrier.childElementCount) return true;
          carrier.remove();
          return false;
        });
      if (!held.xy.length && !held.y.length) byAnchor.delete(anchor);
    }
    if (!byAnchor.size) carriers.delete(holder);
  }
  for (const [key, held] of cutFramesByKey) {
    const kept = held.filter((inner) => inner.isConnected && inner.childElementCount);
    for (const inner of held)
      if (!kept.includes(inner)) {
        outerFrame.get(inner)?.remove();
        outerFrame.delete(inner);
        chains.delete(inner);
      }
    if (kept.length) cutFramesByKey.set(key, kept);
    else cutFramesByKey.delete(key);
  }
  for (const [scroller, lane] of layer.lanes)
    if (!byLane.has(lane)) {
      laneFrames.get(lane)[0].remove();
      laneFrames.delete(lane);
      layer.lanes.delete(scroller);
      layer.sizes.unobserve(scroller);
    }

  // A push says where a seated row stands, so a row that no longer stands has none.
  for (const row of pushes.keys()) if (!packed.has(row)) pushes.delete(row);
  for (const { key: row, rect, read, visualLeft, step = 0 } of placed) {
    const push = packed.get(row) ?? 0;
    pushes.set(row, push);
    // A pin seated beside its target can stand outside what its pane shows though the
    // target is inside it, so a seated pin is withheld by where it stands.
    if (read.place === "pin")
      row.classList.toggle(
        "lf-withheld",
        !targetShown(
          read.target,
          read.extent,
          { top: rect.top + push, right: rect.right },
          bands,
        ),
      );
    const left = (visualLeft ?? rect.left) + step;
    const top = rect.top + push;
    standsBy.set(row, {
      top: top - read.whole.top,
      right: rect.right - read.whole.right,
    });
    if (isCarrier(read.home)) {
      // The carrier stands at the window's origin as this pass measured its anchor,
      // so the row's spot is its client coordinates.
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
        carrierAxes.get(carrier) === "xy" ? from("left", read.carrierBox.left) : "0px",
      );
      setStyle(row, "--lf-margin-x", layoutPx(left));
      setStyle(row, "--lf-margin-y", layoutPx(top));
      continue;
    }
    setStyle(row, "--lf-margin-x", layoutPx(left + scrollX));
    setStyle(row, "--lf-margin-y", layoutPx(top + scrollY));
  }

  // With the column's box and height as the pass read them, so a listener measuring
  // against the column need not read it again.
  document.dispatchEvent(
    new CustomEvent("lf-margin-layout", {
      detail: { column: columnRect, height: columnHeight },
    }),
  );
}

export { scheduleMarginLayout };
