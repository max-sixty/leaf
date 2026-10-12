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
  const { changed, holders } = document.documentElement.lfInitial.residency();
  watchHolders(holders);
  if (changed) layoutChanged(pageDocument());
  readFinished?.(changed);
  if (changed) repaintPage();
}
export function scheduleResidency() {
  if (residencyOpen) residencyPending ||= nextRender(residencyPass);
}
// The same read also says how far each breakout's holder stands in from the column
// (prepaint.js, `indents`), and two later causes move that without moving the column,
// each read where it happens, before the frame paints it. A breakout a revision or a
// widget inserts, or one a holder reveals (a panel losing `hidden`, a disclosure
// opening), is read in the microtask its arrival queues, whether it arrived in a task,
// in a frame's pass after the margin pass ran, or in a ResizeObserver callback. A
// holder a class or a style pads anew changes width, which the holder's resize reports
// after layout and before paint; a change of its height alone moves no edge and is not
// read. Neither waits for the margin pass, which reads at most once a frame and would
// leave the breakout one frame off; this reading moves only the breakouts, so it
// needs no such bound. A holder that moves without changing width, as one positioned
// or translated, keeps its reading until the next pass.
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
}
function readIndents() {
  const { changed, holders } = document.documentElement.lfInitial.indents();
  watchHolders(holders);
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
