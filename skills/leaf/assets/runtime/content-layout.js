/* Authored sidebar, sidenote and contents-outline residency after initial parsing.
   The initial coordinator owns the one computed residency reading, used before first
   paint and adopted here after upgrade. This owner schedules later reads and informs
   annotation geometry and reading-region discovery when that composition changes.
   Imports are inert; boot opens it once for every interactive document. */
import { nextFrame, nextRender, sizeObserver } from "./rendering.js";
import { repaintPage } from "./repaint.js";
import { layoutChanged } from "./widget-elements.js";
import { pageDocument } from "./passages.js";
// One computed reading seats the rail first without moving the column, then each
// authored resident on its preferred side, or in flow when there is no room. The
// column's runtime grid offset is removed before measuring, including RTL, while an
// authored offset remains part of its room. --lf-resident (layouts.css) declares posture
// preferences; data-lf-margin and the shell's --lf-column-shift publish their geometry,
// and data-lf-beside whether a sidebar page's track stands beside its body.
// Read at most once per frame after widgets upgrade. Every completed read notifies
// the selected annotation owner, including an unchanged or missing column; only a
// changed reading repaints page geometry. Imports never start this document owner.
let residencyOpen = false;
let readFinished = null;
let residencyPending = 0;
let residencyRead = -1;
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
  const { changed, breakouts, holders } =
    document.documentElement.lfInitial.residency();
  watchHolders(holders);
  watchMoves(breakouts);
  if (changed) layoutChanged(pageDocument());
  readFinished?.(changed);
  if (changed) repaintPage();
}
export function scheduleResidency() {
  if (residencyOpen) residencyPending ||= nextRender(residencyPass);
}
// A revision returns the reader to their place once its document stands, and where that
// place is depends on the residents' postures: a sidebar page's track that a revision
// replaced is not yet marked beside its body, so its block would not yet scroll and the
// place would land in the page. The revision reads them first (version.js, `land`); a
// scheduled pass still follows.
export function settleResidency() {
  if (residencyOpen) readResidency();
}
// The same read also says how far each breakout's holder stands in from the column,
// and whether the page arranged the box the breakout is in (prepaint.js, `indents`),
// which later changes alter without moving the column. Whatever moves a holder moves
// its breakout, so every breakout is watched for moving sideways, an edge moving
// outward, and being drawn at all (`watchMoves`), whatever caused it: a holder's
// margin, a class that reveals it, the page's own script. That report comes after the
// rendering update that moved it has painted, so the causes Leaf itself and a revision
// produce are read sooner, before the frame paints them. A breakout a revision or a
// widget inserts, or one a holder reveals (a panel losing `hidden`, a disclosure
// opening), is read in the microtask its arrival queues, whether it arrived in a task,
// in a frame's pass after the margin pass ran, or in a ResizeObserver callback. A
// holder a class or a style pads anew changes width, which the holder's resize reports
// after layout and before paint; a change of its height alone moves no edge and is not
// read. Neither waits for the margin pass, which reads at most once a frame and would
// leave the breakout one frame off; this reading moves only the breakouts, so it needs
// no such bound. A holder that changes how it arranges what it holds, from a block to a
// grid, say, while nothing in it moves or resizes, keeps its reading until the next
// pass.
const BREAKOUT = "[data-lf-space]";
const bringsBreakout = (node) =>
  node.nodeType === Node.ELEMENT_NODE &&
  (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
// The two records of what a reading answered for, kept only to watch it: the holders
// it measured, each with the width it last reported and the breakouts the reading found
// in it, and the breakouts, each with its move watch (`moves`, below). A reading
// replaces both with exactly what it read. A removal alone moves no breakout that
// stays, so it drops, without a reading and in the microtask it queues, each holder no
// longer connected or no longer holding one of its breakouts, before a removed box
// could report its zero width, and each breakout no longer connected. That is how
// nothing removed stays held: both records hold what they watch, and a removal from
// `main` releases it.
const watched = new Map();
const holderSizes = sizeObserver((entries) => {
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
const unwatch = (holder) => {
  watched.delete(holder);
  holderSizes.unobserve(holder);
};
// A holder is observed from the width the reading measured, so its first report is a
// change only if one came after that reading.
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
// A breakout moved elsewhere arrives there too, and that arrival takes a reading, so a
// breakout still connected is still its holder's.
function releaseHolders() {
  for (const [holder, record] of watched) {
    record.breakouts = record.breakouts.filter((breakout) => breakout.isConnected);
    if (!holder.isConnected || !record.breakouts.length) unwatch(holder);
  }
  for (const breakout of moves.keys()) if (!breakout.isConnected) unwatchMove(breakout);
}
// Each breakout a reading answers for, watched by an IntersectionObserver of its own
// rooted at `main`, whose root is cut to the extent across that the breakout had once
// the reading was written, and reaches a million pixels above and below it, so
// scrolling, and growth above the breakout, change nothing it sees. Moving sideways, or
// an edge moving outward, by a pixel or more takes some of the breakout outside that
// root, and a breakout not drawn is watched across the whole root, so drawing it brings
// it in; either changes the ratio the observer reports, which takes a reading. An edge
// moving inward leaves the breakout inside its root, which is why the holders' sizes
// are watched as well. An observer's root is fixed when it is made, so a breakout
// found elsewhere across is watched anew, from
// what it reports first: a ratio that is not the one its root was cut for, such as one
// a scrolling ancestor clips, is where its watch starts.
const moves = new Map();
const AROUND = 1e6;
const unwatchMove = (breakout) => {
  moves.get(breakout).observer.disconnect();
  moves.delete(breakout);
};
let movePending = false;
const moved = () => {
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
      threshold: threshold ? [0, threshold] : [0],
    },
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
    // How far the root reaches past `main` on each side, cut to the breakout's extent
    // to the whole pixel outside it.
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
export function openResidency({ onRead }) {
  readFinished = onRead;
  residencyOpen = true;
  document.addEventListener("toggle", scheduleResidency, { capture: true });
  window.addEventListener("resize", scheduleResidency);
  const main = pageDocument();
  if (main)
    new MutationObserver((records) => {
      if (
        records.some((record) =>
          record.type === "attributes"
            ? bringsBreakout(record.target)
            : [...record.addedNodes].some(bringsBreakout),
        )
      )
        readIndents();
      else if (records.some((record) => [...record.removedNodes].some(bringsBreakout)))
        releaseHolders();
    }).observe(main, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-lf-space", "hidden", "open"],
    });
  readResidency();
}

export const residencyStarted = () => residencyOpen;
