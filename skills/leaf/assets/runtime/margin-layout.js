/* One geometry owner for controls and readings that hang in the document margin. */
const rows = new Map();
const GAP = 4;
let pending = 0;
let observer = null;
let observedColumn = null;
let claimedRail = 0;
let railReserved = false;

export const marginColumn = () => document.querySelector("main") || document.body;

// Whether the page takes a margin strip at all, as distinct from how wide the strip is.
// The width is `--rail` below and only ever grows; this says the page has taken the
// strip, and once taken it is never given back. Claimed only while something stands in
// it, the strip arrived with the gesture that raised the first Button and left again
// with the undo, and each of those moved the readable column under the reader. The
// cascade reads this attribute rather than asking whether a row is standing, because a
// row's own placement depends on the strip and a live question about it would feed the
// reservation back into itself.
export function reserveRail() {
  if (railReserved) return;
  railReserved = true;
  document.documentElement.setAttribute("data-lf-rail", "");
}

function scheduleMarginLayout() {
  if (pending) return;
  pending = requestAnimationFrame(layoutMarginRows);
}

function observeLayout() {
  const column = marginColumn();
  if (!observer) {
    observer = new ResizeObserver(scheduleMarginLayout);
    observer.observe(document.body);
  }
  if (observedColumn === column) return;
  if (observedColumn) observer.unobserve(observedColumn);
  observedColumn = column;
  observer.observe(observedColumn);
}

export function registerMarginRow(row, options = {}) {
  rows.set(row, options);
  observeLayout();
  scheduleMarginLayout();
  return () => unregisterMarginRow(row);
}

export function updateMarginRow(row, options = {}) {
  if (!rows.has(row)) return registerMarginRow(row, options);
  rows.set(row, options);
  observeLayout();
  scheduleMarginLayout();
  return () => unregisterMarginRow(row);
}

export function unregisterMarginRow(row) {
  rows.delete(row);
  row?.classList.remove("lf-docked", "lf-waiting");
  if (row) row.style.transform = "";
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
    for (const el of document.querySelectorAll("[data-lf-wide][data-lf-yield]"))
      el.removeAttribute("data-lf-yield");
  }
  scheduleMarginLayout();
}

function placeRows(columnRect) {
  const placements = [...rows].map(([row, options]) =>
    options.place?.(row, columnRect),
  );
  for (const place of placements) place?.();
}

export function layoutMarginRows() {
  cancelAnimationFrame(pending);
  pending = 0;
  // A compact page keeps every margin row in document flow. Pulling those rows out to
  // re-measure the same posture briefly shortens the document, so a browser clamps a
  // reader standing at its end before the rows return. Read the current posture as one
  // batch and leave rows whose owner still says they cannot hang where they are.
  const dockedRows = [...rows].filter(
    ([row]) => row.isConnected && row.classList.contains("lf-docked"),
  );
  const staysDocked = new Set();
  if (dockedRows.length) {
    const postureColumnRect = marginColumn().getBoundingClientRect();
    const postureRoom = document.body.getBoundingClientRect().right;
    for (const [row, options] of dockedRows) {
      const anchor =
        typeof options.anchor === "function" ? options.anchor() : options.anchor;
      const shown =
        options.shown?.(anchor) ??
        (anchor instanceof Element ? anchor.checkVisibility() : row.checkVisibility());
      if (
        shown &&
        !(
          options.hangs?.(
            row,
            row.getBoundingClientRect(),
            postureColumnRect,
            postureRoom,
          ) ?? true
        )
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
    if (row.classList.contains("lf-docked") || row.classList.contains("lf-waiting"))
      row.classList.remove("lf-docked", "lf-waiting");
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
  const room = document.body.getBoundingClientRect().right;
  placeRows(columnRect);
  const measured = [...rows].map(([row, options]) => {
    const anchor =
      typeof options.anchor === "function" ? options.anchor() : options.anchor;
    const rect = row.getBoundingClientRect();
    const width =
      typeof options.claim === "function"
        ? options.claim(row, rect)
        : options.claim
          ? rect.width
          : 0;
    const claim = width
      ? Math.ceil(width + (parseFloat(getComputedStyle(row).marginLeft) || 0))
      : 0;
    return {
      row,
      options,
      rect,
      claim,
      hangs: options.hangs?.(row, rect, columnRect, room) ?? true,
      shown:
        options.shown?.(anchor) ??
        (anchor instanceof Element ? anchor.checkVisibility() : row.checkVisibility()),
    };
  });
  const claim = Math.max(0, ...measured.map(({ claim }) => claim));
  if (claim) {
    reserveRail();
    if (claim > claimedRail) {
      claimedRail = claim;
      document.documentElement.style.setProperty("--rail", `${claimedRail}px`);
    }
  }
  const inMargin = [];
  let docked = false;
  for (const { row, options, rect, shown, hangs } of measured) {
    if (!shown) row.classList.add("lf-waiting");
    else if (!hangs || rect.right > room) {
      if (options.fallback === "hide") row.classList.add("lf-waiting");
      else {
        row.classList.add("lf-docked");
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
      priority: rows.get(row)?.priority ?? 0,
    }))
    .sort((a, b) => a.priority - b.priority || a.rect.top - b.rect.top);
  const bands = [];
  for (const { row, rect } of placed) {
    let top = rect.top;
    for (const band of [...bands].sort((a, b) => a.top - b.top))
      if (top < band.bottom + GAP && top + rect.height > band.top - GAP)
        top = band.bottom + GAP;
    const push = top - rect.top;
    if (push) row.style.transform = `translateY(${push}px)`;
    bands.push({ top, bottom: top + rect.height });
  }

  const wide = [...document.querySelectorAll("[data-lf-wide]")].map((el) => {
    const box = el.getBoundingClientRect();
    return {
      el,
      yieldRight: bands.some((band) => band.top < box.bottom && band.bottom > box.top),
    };
  });
  for (const { el, yieldRight } of wide) {
    if (yieldRight) {
      if (el.getAttribute("data-lf-yield") !== "r")
        el.setAttribute("data-lf-yield", "r");
    } else if (el.hasAttribute("data-lf-yield")) el.removeAttribute("data-lf-yield");
  }
  document.dispatchEvent(new CustomEvent("lf-margin-layout"));
}

export { scheduleMarginLayout };
