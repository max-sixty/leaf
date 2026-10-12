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
// preferences; data-lf-margin and the shell's --lf-column-shift publish their geometry.
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
  const { changed, breakouts, holders } = document.documentElement.lfInitial.residency();
  watchHolders(holders);
  watchMoves(breakouts);
  if (changed) layoutChanged(pageDocument());
  readFinished?.(changed);
  if (changed) repaintPage();
}
export function scheduleResidency() {
  if (residencyOpen) residencyPending ||= nextRender(residencyPass);
}
// The same read also says how far the block each breakout is laid out in stands in
// from the column (prepaint.js, `indents`), which later changes move without moving the
// column. Whatever moves a block moves its breakout, so every breakout is watched for
// moving sideways, an edge moving outward, and being drawn at all (`watchMoves`),
// whatever caused it: a holder's margin, a class that reveals it, the page's own
// script. That report comes after the rendering update that moved it has painted, so
// the causes Leaf itself and a revision produce are read sooner, before the frame
// paints them. A
// breakout a revision or a widget inserts, or one a holder reveals (a panel losing
// `hidden`, a disclosure opening), is read in the microtask its arrival queues, whether
// it arrived in a task, in a frame's pass after the margin pass ran, or in a
// ResizeObserver callback. A holder a class or a style pads anew changes width, which
// the holder's resize reports after layout and before paint; a change of its height
// alone moves no edge and is not read. Neither waits for the margin pass, which reads
// at most once a frame and would leave the breakout one frame off; this reading moves
// only the breakouts, so it needs no such bound. What none of these reports, a block
// whose edge moves inward while the other stays and its holder keeps its width, as a
// grid track a sibling's content takes from, keeps its reading until the next pass.
const BREAKOUT = '[data-lf-space]:not([data-lf-space="column"])';
const bringsBreakout = (node) =>
  node.nodeType === Node.ELEMENT_NODE &&
  (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
// The one record of the holders a reading measured, kept only to watch them: each with
// the width it last reported, and the breakouts the reading found in it, held weakly.
// A reading replaces the record with exactly the holders it measured. A removal alone
// moves no breakout that stays, so it drops, without a reading and in the microtask it
// queues, each holder no longer connected or no longer holding one of its breakouts,
// before a removed box could report its zero width. Nothing removed stays held: a
// removed holder held a removed breakout, so that removal drops it, and a breakout is
// never held but through a WeakRef.
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
    const refs = breakouts.map((breakout) => new WeakRef(breakout));
    if (watched.has(holder)) watched.get(holder).breakouts = refs;
    else {
      watched.set(holder, { width, breakouts: refs });
      holderSizes.observe(holder);
    }
  }
}
// A breakout moved elsewhere arrives there too, and that arrival takes a reading, so a
// breakout still connected is still its holder's.
function releaseHolders() {
  for (const [holder, { breakouts }] of watched)
    if (
      !holder.isConnected ||
      !breakouts.some((breakout) => breakout.deref()?.isConnected)
    )
      unwatch(holder);
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
// are watched as well. An observer's root
// is fixed when it is made, so a breakout found elsewhere across is watched anew, from
// what it reports first: a ratio that is not the one its root was cut for, such as one
// a scrolling ancestor clips, is where its watch starts. The record is replaced by
// exactly the breakouts each reading answers for, and a removal drops the disconnected
// ones (`releaseHolders`), so a removed breakout is held by nothing here.
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
  for (const breakout of moves.keys()) if (!answered.has(breakout)) unwatchMove(breakout);
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
