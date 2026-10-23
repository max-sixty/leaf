import {
  marks,
  resolveAnchor,
  targetSegments
} from "./bundle-chrome.js";
import {
  inChrome,
  layoutBox,
  pageDocument,
  pageText
} from "./bundle-passage-facts.js";
import {
  afterScript,
  clamp,
  drawn,
  layoutChanged,
  nextFrame,
  nextRender,
  repaintPage,
  shownParts,
  sizeObserver,
  under,
  upFrom
} from "./bundle-page-paint.js";
import {
  createSignal,
  flush,
  untrack
} from "./bundle-vendor~browser-runtime.js";

// runtime/page-controls.js
var EMPTY = Object.freeze([]);
var PAGE_CONTROL_RANK = Object.freeze({
  session: 10,
  preview: 20,
  layer: 30,
  share: 35,
  leaves: 40,
  latest: 50,
  map: 70,
  // The page's commands reached by pointer here (touch-controls.js), among themselves
  // in the register's order.
  commands: 75,
  blanket: 80,
  versions: 90,
  keyboard: 95,
  // The way out of the stance the user stands in.
  exit: 120
});
var GROUPS = Object.freeze(["page", "navigate", "annotate", "about", "keys"]);
var rows = /* @__PURE__ */ new Map();
var sequence = 0;
var [revision, setRevision] = createSignal(0, { ownedWrite: true });
var read = (value) => typeof value === "function" ? value() : value;
function registerPageControl(row) {
  if (!row.key || !Number.isFinite(row.rank) || !row.label || !row.group)
    throw new TypeError(
      `Page control ${row.key} needs a key, a numeric rank, a label and a group`
    );
  if (rows.has(row.key)) throw new TypeError(`Page control ${row.key} is registered`);
  rows.set(row.key, Object.freeze({ ...row, sequence: sequence++ }));
  pageControlsChanged();
}
function pageControls() {
  revision();
  return [...rows.values()].sort((a, b) => a.rank - b.rank || a.sequence - b.sequence).filter((row) => read(row.offered) ?? true).map((row) => {
    const group = read(row.group);
    if (!GROUPS.includes(group))
      throw new TypeError(
        `Page control ${row.key} is in group ${group}, not one of ${GROUPS.join(", ")}`
      );
    return Object.freeze({
      key: row.key,
      label: read(row.label),
      value: read(row.value) ?? "",
      title: read(row.title) ?? "",
      shortcut: read(row.shortcut) ?? EMPTY,
      group,
      copies: read(row.copies) ?? "",
      urgent: read(row.urgent) ?? null,
      exit: Boolean(row.exit),
      disabled: Boolean(read(row.disabled)),
      press: row.press ?? null
    });
  });
}
var pageControlsChanged = () => afterScript(tell);
function tell() {
  flush(() => setRevision(untrack(revision) + 1));
}

// runtime/content-layout.js
var residencyOpen = false;
var readFinished = null;
var residencyPending = 0;
var residencyRead = -1;
function residencyPass(time) {
  residencyPending = 0;
  if (time === residencyRead) {
    residencyPending = nextFrame(residencyPass);
    return;
  }
  residencyRead = time;
  readResidency();
}
var headSizes = null;
var watchedHead = null;
function watchHead() {
  const header = document.documentElement.lfInitial.layoutBox()?.querySelector(":scope > header") ?? null;
  if (header === watchedHead) return;
  headSizes ??= sizeObserver(() => scheduleResidency());
  if (watchedHead) headSizes.unobserve(watchedHead);
  if (header) headSizes.observe(header);
  watchedHead = header;
}
function readResidency() {
  const { changed } = document.documentElement.lfInitial.residency();
  watchHead();
  if (changed) layoutChanged(pageDocument());
  readFinished?.(changed);
  if (!changed) return;
  repaintPage();
  pageControlsChanged();
}
var railStands = (main = layoutBox()) => (main?.getAttribute("data-lf-margin") ?? "").split(" ").includes("rail");
function scheduleResidency() {
  if (residencyOpen) residencyPending ||= nextRender(residencyPass);
}
function settleResidency() {
  if (residencyOpen) readResidency();
}
var ROOM = marks["x-space"].paint;
var BREAKOUT = `[${ROOM}]`;
var bringsBreakout = (node) => node.nodeType === Node.ELEMENT_NODE && (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
function readBreakouts() {
  const { changed } = document.documentElement.lfInitial.breakouts();
  if (!changed) return;
  layoutChanged(pageDocument());
  repaintPage();
}
var mayChangeResidency = (node) => node.matches(
  'body > main > *, body > main > [data-lf-views="parts"] > *, [data-lf-views-flow="page"] > *'
);
function openResidency({ onRead }) {
  readFinished = onRead;
  residencyOpen = true;
  document.addEventListener("toggle", scheduleResidency, { capture: true });
  window.addEventListener("resize", scheduleResidency);
  const main = pageDocument();
  if (main)
    new MutationObserver((records) => {
      if (records.some(
        (record) => record.type === "attributes" && record.attributeName === "hidden" && mayChangeResidency(record.target)
      ))
        readResidency();
      else if (records.some(
        (record) => record.type === "attributes" ? bringsBreakout(record.target) : [...record.addedNodes].some(bringsBreakout)
      ))
        readBreakouts();
    }).observe(main, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: [ROOM, "hidden", "open"]
    });
  readResidency();
}

// runtime/pointed-place.js
var points = /* @__PURE__ */ new Map();
var handed = /* @__PURE__ */ new Map();
var WITHIN_A_LINE = /^(inline|contents$)/;
function pointInto(target, node) {
  let at = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement ?? null;
  if (!target || target instanceof SVGElement || !at || !under(at, target)) return null;
  let line = null;
  for (; at && at !== target; at = upFrom(at)) {
    if (at instanceof SVGElement) continue;
    const display = getComputedStyle(at).display;
    if (display === "table-row") {
      line = at;
      break;
    }
    if (display === "table-cell") line = null;
    else if (!line && !WITHIN_A_LINE.test(display)) line = at;
  }
  return line && !opens(target, line) ? line : null;
}
function opens(target, line) {
  for (let at = line; at && at !== target; at = upFrom(at))
    for (let before = at.previousSibling; before; before = before.previousSibling)
      if (drawn2(before)) return false;
  return true;
}
var drawn2 = (node) => node.nodeType === Node.TEXT_NODE ? Boolean(node.data.trim()) && Boolean(node.parentElement?.checkVisibility()) : node.nodeType === Node.ELEMENT_NODE && !inChrome(node) && node.checkVisibility() && [...node.getClientRects()].some((box) => box.width && box.height);
function livePoint(target, point) {
  return target && point?.isConnected && point !== target && under(point, target) && point.getClientRects().length ? point : null;
}
function commitPoint(key, element, passage) {
  handed.set(key, { element, passage });
}
function placePoints(threads, known) {
  const text = pageText();
  for (const [key, { element, passage }] of handed) {
    if (!known.has(key)) continue;
    handed.delete(key);
    const beside = [...points.values()].find(
      (held) => held.element === element && element.isConnected
    );
    points.set(key, { element, passage, row: beside?.row ?? key, readFor: null });
  }
  const placed = /* @__PURE__ */ new Map();
  for (const { key, target } of threads) {
    const point = points.get(key);
    if (!point) continue;
    let element = livePoint(target, point.element);
    if (!element && point.passage && point.readFor !== text) {
      point.readFor = text;
      const found = resolveAnchor(point.passage);
      element = livePoint(target, pointInto(target, targetSegments(found)[0]?.node));
      if (element) point.element = element;
    }
    if (element)
      placed.set(key, { element, row: point.row, words: point.passage?.quote ?? null });
  }
  if (known.size) {
    for (const store of [points, handed])
      for (const key of store.keys()) if (!known.has(key)) store.delete(key);
  }
  return placed;
}
function pointBand(box, point) {
  const row = point.getBoundingClientRect();
  const top = clamp(row.top, box.top, box.bottom);
  const bottom = clamp(row.bottom, top, box.bottom);
  const { left, right } = box;
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}

// runtime/visible-target-parts.js
function visibleTargetParts(target) {
  const parts = shownParts(target).filter(drawn);
  return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}

export {
  pointInto,
  livePoint,
  commitPoint,
  placePoints,
  pointBand,
  PAGE_CONTROL_RANK,
  registerPageControl,
  pageControls,
  pageControlsChanged,
  railStands,
  scheduleResidency,
  settleResidency,
  openResidency,
  visibleTargetParts
};
