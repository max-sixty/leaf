/* One geometry owner for controls and readings that hang in the document margin.

   `margin-layout` places, packs, docks, and measures the complete host and its transient
   control labels. It never sizes the rail: the rail's width is the theme's `--rail`, a
   constant stated before anything contributes, so nothing that lands in the margin,
   settles there, or leaves it can move the readable column. A host wider than the rail
   borrows the RHS room past it and docks the complete host when it cannot fit. Below
   the margin breakpoint the complete host docks into flow. Visibility and vertical
   placement read `shownParts` and `shownBox`, not the target's raw client rect: a
   project may set `display: contents` while its rendered descendants remain usable, and
   a collapsed target has no rendered part to offer.

   Every live page may grow a page-edge margin entry — an anchored comment can arrive on one
   made entirely of prose — so the margin projection reserves the rail as it is built and
   never gives it back. The runtime states that reservation as `data-lf-rail` on the root,
   and the cascade spends it there; neither reads what is standing in the margin, because
   a row's placement depends on the strip it would be answering about. */
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { shellRight } from "./geometry.js";

const rows = new Map();
// The horizontal space a row was last docked against. A dock holds while that space and
// the row itself do. Cleared wherever a row restates itself, since its own size is the
// other half of the answer.
const dockedAgainst = new WeakMap();
const GAP = 4;
let pending = 0;
let observer = null;
let observedColumn = null;
let railReserved = false;

const marginColumn = () => document.querySelector("main") || document.body;

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

// Whether the page takes a margin strip at all; its width is the theme's `--rail`. Once
// taken, the strip is never given back. Claimed only while something stands in it, the
// strip arrived with the gesture that raised the first margin entry and left again with
// the undo, and each of those moved the readable column under the user. The cascade reads
// this attribute rather than asking whether a row is standing, because a row's own
// placement depends on the strip and a live question about it would feed the reservation
// back into itself.
export function reserveRail() {
  if (railReserved) return;
  railReserved = true;
  document.documentElement.setAttribute("data-lf-rail", "");
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

export function registerMarginRow(row, options = {}) {
  rows.set(row, options);
  dockedAgainst.delete(row);
  observeLayout();
  scheduleMarginLayout();
  return () => unregisterMarginRow(row);
}

export function updateMarginRow(row, options = {}) {
  if (!rows.has(row)) return registerMarginRow(row, options);
  rows.set(row, options);
  dockedAgainst.delete(row);
  observeLayout();
  scheduleMarginLayout();
  return () => unregisterMarginRow(row);
}

export function unregisterMarginRow(row) {
  rows.delete(row);
  row?.classList.remove("lf-docked", "lf-withheld");
  if (row) row.style.transform = "";
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }
  scheduleMarginLayout();
}

// The other half of the clear below: `add` re-serializes the class attribute whether
// or not the token is new, and the posture read leaves a row that still cannot hang
// carrying `lf-docked` from one pass into the next, so it arrives at its mark already
// wearing it. Ask before marking.
function mark(row, name) {
  if (!row.classList.contains(name)) row.classList.add(name);
}

function placeRows(columnRect) {
  const placements = [...rows].map(([row, options]) =>
    options.place?.(row, columnRect),
  );
  for (const place of placements) place?.();
}

export function layoutMarginRows() {
  cancelRender(pending);
  pending = 0;
  // A compact page keeps every margin row in document flow. Pulling those rows out to
  // re-measure the same posture briefly shortens the document, so a browser clamps a
  // user standing at its end before the rows return. Read the current posture as one
  // batch and leave rows whose owner still says they cannot hang where they are.
  const dockedRows = [...rows].filter(
    ([row]) => row.isConnected && row.classList.contains("lf-docked"),
  );
  const staysDocked = new Set();
  if (dockedRows.length) {
    const postureColumn = marginColumn();
    const postureColumnRect = postureColumn.getBoundingClientRect();
    const postureRoom = shellRight();
    for (const [row, options] of dockedRows) {
      const anchor =
        typeof options.anchor === "function" ? options.anchor() : options.anchor;
      const shown =
        options.shown?.(anchor) ??
        (anchor instanceof Element ? anchor.checkVisibility() : row.checkVisibility());
      if (!shown) continue;
      const hangs =
        options.hangs?.(
          row,
          row.getBoundingClientRect(),
          postureColumnRect,
          postureRoom,
        ) ?? true;
      // Its owner still says it cannot hang, so the answer needs no measuring.
      if (!hangs) {
        staysDocked.add(row);
        continue;
      }
      // It hangs by its owner's reading and docked anyway, which means it did not fit
      // the horizontal space. Floating it to measure that again moves a host that may
      // hold focus, so keep the answer while its inputs hold.
      const against = dockedAgainst.get(row);
      if (
        against?.room === postureRoom &&
        against.columnLeft === postureColumnRect.left &&
        against.columnRight === postureColumnRect.right
      )
        staysDocked.add(row);
    }
  }
  for (const [row, options] of rows) {
    if (!row.isConnected) {
      rows.delete(row);
      continue;
    }
    if (staysDocked.has(row)) continue;
    if (row.classList.contains("lf-docked")) options.float?.(row);
    // `remove` re-serializes the class attribute whether or not the tokens stand, and
    // this pass runs on the heartbeat, so ask before clearing: a row that hangs in the
    // margin carries neither class and has nothing to be put back.
    if (row.classList.contains("lf-docked") || row.classList.contains("lf-withheld"))
      row.classList.remove("lf-docked", "lf-withheld");
    row.style.transform = "";
  }
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }

  // Each phase reads every row before writing any. A placement callback returns
  // its writer so target measurements never flush the previous row's changes.
  const columnRect = marginColumn().getBoundingClientRect();
  const room = shellRight();
  placeRows(columnRect);
  const measured = [...rows].map(([row, options]) => {
    const anchor =
      typeof options.anchor === "function" ? options.anchor() : options.anchor;
    const rect = row.getBoundingClientRect();
    return {
      row,
      options,
      rect,
      hangs: options.hangs?.(row, rect, columnRect, room) ?? true,
      shown:
        options.shown?.(anchor) ??
        (anchor instanceof Element ? anchor.checkVisibility() : row.checkVisibility()),
    };
  });
  const inMargin = [];
  let docked = false;
  for (const { row, options, rect, shown, hangs } of measured) {
    if (!shown) mark(row, "lf-withheld");
    // A row the posture read kept docked is measured where it stands, in flow, so its
    // own rect says it fits a rail it is not in. It takes the docked path on the reading
    // that kept it, not on a measurement of somewhere it is not standing.
    else if (!hangs || staysDocked.has(row) || rect.right > room) {
      if (options.fallback === "hide") mark(row, "lf-withheld");
      else {
        mark(row, "lf-docked");
        dockedAgainst.set(row, {
          room,
          columnLeft: columnRect.left,
          columnRight: columnRect.right,
        });
        options.dock?.(row);
        docked = true;
      }
    } else inMargin.push(row);
  }

  // Docked rows enter document flow and move every later target. Measure those
  // targets in the final flow before packing the rows that still hang beside them.
  if (docked) placeRows(marginColumn().getBoundingClientRect());

  const placed = inMargin
    .map((row) => ({
      row,
      rect: row.getBoundingClientRect(),
      hang: parseFloat(getComputedStyle(row).marginLeft) || 0,
      priority: rows.get(row)?.priority ?? 0,
    }))
    .sort((a, b) => a.priority - b.priority || a.rect.top - b.rect.top);
  // A wide block grows out of the column toward the rail, and a row hangs off the column,
  // so a row level with one would stand over it. The block's growth stops at main's right
  // gutter, which the rail's reservation is part of, so the room past the block is the
  // rail's own: the row steps out to hang off the block instead. The row moves and the
  // block does not, because nothing Leaf draws moves the page's content, and a comment
  // arriving beside a board would otherwise narrow it.
  // Docking moves targets down, never across, so the column's right edge read before
  // it still stands.
  const wide = [...marginColumn().querySelectorAll("[data-lf-space]")]
    .map((el) => el.getBoundingClientRect())
    .filter((box) => box.right > columnRect.right + 1);
  const bands = [];
  for (const { row, rect, hang } of placed) {
    let top = rect.top;
    for (const band of [...bands].sort((a, b) => a.top - b.top))
      if (top < band.bottom + GAP && top + rect.height > band.top - GAP)
        top = band.bottom + GAP;
    const push = top - rect.top;
    const reach = Math.max(
      rect.left - hang,
      ...wide
        .filter((box) => box.top < top + rect.height && box.bottom > top)
        .map((box) => box.right),
    );
    const step = Math.max(0, Math.min(reach + hang - rect.left, room - rect.right));
    if (push || step) row.style.transform = `translate(${step}px, ${push}px)`;
    bands.push({ top, bottom: top + rect.height });
  }
  document.dispatchEvent(new CustomEvent("lf-margin-layout"));
}

export { scheduleMarginLayout };
