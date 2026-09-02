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
  cancelAnimationFrame(pending);
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

export function layoutMarginRows() {
  pending = 0;
  const column = marginColumn();
  const columnRect = column.getBoundingClientRect();
  const room = document.body.getBoundingClientRect().right;
  for (const [row, options] of rows) {
    if (!row.isConnected) {
      rows.delete(row);
      continue;
    }
    row.classList.remove("lf-docked", "lf-waiting");
    row.style.transform = "";
    options.place?.(row, columnRect);
  }
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }

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
  for (const { row, options, rect } of measured) {
    const width =
      typeof options.claim === "function"
        ? options.claim(row, rect)
        : options.claim
          ? rect.width
          : 0;
    if (!width) continue;
    reserveRail();
    const margin = parseFloat(getComputedStyle(row).marginLeft) || 0;
    const claim = Math.ceil(width + margin);
    if (claim <= claimedRail) continue;
    claimedRail = claim;
    document.documentElement.style.setProperty("--rail", `${claimedRail}px`);
  }
  const inMargin = [];
  for (const { row, options, rect, shown, hangs } of measured) {
    if (!shown) row.classList.add("lf-waiting");
    else if (!hangs || rect.right > room) {
      if (options.fallback === "hide") row.classList.add("lf-waiting");
      else row.classList.add("lf-docked");
    } else inMargin.push(row);
  }

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

  for (const el of document.querySelectorAll("[data-lf-wide]")) {
    const box = el.getBoundingClientRect();
    if (bands.some((band) => band.top < box.bottom && band.bottom > box.top))
      el.setAttribute("data-lf-yield", "r");
    else el.removeAttribute("data-lf-yield");
  }
  document.dispatchEvent(new CustomEvent("lf-margin-layout"));
}

export { scheduleMarginLayout };
