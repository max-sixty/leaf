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
  sizeObserver,
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
  const { changed, breakouts, holders } = document.documentElement.lfInitial.residency();
  watchHolders(holders);
  watchMoves(breakouts);
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
var BREAKOUT = '[data-lf-space]:not([data-lf-space="column"])';
var bringsBreakout = (node) => node.nodeType === Node.ELEMENT_NODE && (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
var watched = /* @__PURE__ */ new Map();
var holderSizes = sizeObserver((entries) => {
  let widened = false;
  for (const { target, contentBoxSize } of entries) {
    const holder = watched.get(target);
    if (!holder) continue;
    const width = contentBoxSize[0].inlineSize;
    if (Math.abs(width - holder.width) > 0.5) widened = true;
    holder.width = width;
  }
  if (widened) readIndents();
});
var unwatch = (holder) => {
  watched.delete(holder);
  holderSizes.unobserve(holder);
};
function watchHolders(holders) {
  for (const holder of watched.keys()) if (!holders.has(holder)) unwatch(holder);
  for (const [holder, { width, breakouts }] of holders) {
    if (watched.has(holder)) watched.get(holder).breakouts = breakouts;
    else {
      watched.set(holder, { width, breakouts });
      holderSizes.observe(holder);
    }
  }
}
function releaseHolders() {
  for (const [holder, record] of watched) {
    record.breakouts = record.breakouts.filter((breakout) => breakout.isConnected);
    if (!holder.isConnected || !record.breakouts.length) unwatch(holder);
  }
  for (const breakout of moves.keys()) if (!breakout.isConnected) unwatchMove(breakout);
}
var moves = /* @__PURE__ */ new Map();
var AROUND = 1e6;
var unwatchMove = (breakout) => {
  moves.get(breakout).observer.disconnect();
  moves.delete(breakout);
};
var movePending = false;
var moved = () => {
  if (movePending) return;
  movePending = true;
  queueMicrotask(() => {
    movePending = false;
    readIndents();
  });
};
function observeMove(breakout, watch, threshold, settled = false) {
  const { root, left, right } = watch;
  let first = !settled;
  watch.observer?.disconnect();
  watch.observer = new IntersectionObserver(
    (entries) => {
      const ratio = entries.at(-1).intersectionRatio;
      const start = first;
      first = false;
      if (ratio === threshold) return;
      if (start && ratio > 0) observeMove(breakout, watch, ratio, true);
      else moved();
    },
    {
      root,
      rootMargin: `${AROUND}px ${right}px ${AROUND}px ${left}px`,
      threshold: threshold ? [0, threshold] : [0]
    }
  );
  watch.observer.observe(breakout);
}
function watchMoves(breakouts) {
  const answered = new Set(breakouts);
  for (const breakout of moves.keys())
    if (!answered.has(breakout)) unwatchMove(breakout);
  const root = pageDocument();
  if (!root) return;
  let frame = null;
  for (const breakout of breakouts) {
    let left = AROUND;
    let right = AROUND;
    if (breakout.checkVisibility()) {
      const box = breakout.getBoundingClientRect();
      frame ??= root.getBoundingClientRect();
      left = Math.ceil(frame.left - box.left);
      right = Math.ceil(box.right - frame.right);
    }
    const watch = moves.get(breakout);
    if (watch?.root === root && watch.left === left && watch.right === right) continue;
    const next = { root, left, right, observer: watch?.observer };
    moves.set(breakout, next);
    observeMove(breakout, next, left === AROUND ? 0 : 1);
  }
}
function readIndents() {
  const { changed, breakouts, holders } = document.documentElement.lfInitial.indents();
  watchHolders(holders);
  watchMoves(breakouts);
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
      else if (records.some((record) => [...record.removedNodes].some(bringsBreakout)))
        releaseHolders();
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
