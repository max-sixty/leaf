import {
  resolveAnchor,
  targetSegments
} from "./bundle-chrome.js";
import {
  inChrome,
  pageDocument,
  pageText
} from "./bundle-passage-facts.js";
import {
  clamp,
  layoutChanged,
  repaintPage
} from "./bundle-page-paint.js";
import {
  nextFrame,
  nextRender,
  under,
  upFrom
} from "./bundle-sample-visibility.js";

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
function readResidency() {
  const { changed } = document.documentElement.lfInitial.residency();
  if (changed) layoutChanged(pageDocument());
  readFinished?.(changed);
  if (changed) repaintPage();
}
function scheduleResidency() {
  if (residencyOpen) residencyPending ||= nextRender(residencyPass);
}
function settleResidency() {
  if (residencyOpen) readResidency();
}
var BREAKOUT = "[data-lf-space]";
var bringsBreakout = (node) => node.nodeType === Node.ELEMENT_NODE && (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
function readIndents() {
  const { changed } = document.documentElement.lfInitial.indents();
  if (!changed) return;
  layoutChanged(pageDocument());
  repaintPage();
}
function openResidency({ onRead }) {
  readFinished = onRead;
  residencyOpen = true;
  document.addEventListener("toggle", scheduleResidency, { capture: true });
  window.addEventListener("resize", scheduleResidency);
  const main = pageDocument();
  if (main)
    new MutationObserver((records) => {
      if (records.some(
        (record) => record.type === "attributes" ? bringsBreakout(record.target) : [...record.addedNodes].some(bringsBreakout)
      ))
        readIndents();
    }).observe(main, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-lf-space", "hidden", "open"]
    });
  readResidency();
}
var residencyStarted = () => residencyOpen;

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
      if (drawn(before)) return false;
  return true;
}
var drawn = (node) => node.nodeType === Node.TEXT_NODE ? Boolean(node.data.trim()) && Boolean(node.parentElement?.checkVisibility()) : node.nodeType === Node.ELEMENT_NODE && !inChrome(node) && node.checkVisibility() && [...node.getClientRects()].some((box) => box.width && box.height);
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

export {
  pointInto,
  livePoint,
  commitPoint,
  placePoints,
  pointBand,
  scheduleResidency,
  settleResidency,
  openResidency,
  residencyStarted
};
