/* Authored sidebar, sidenote and contents-outline residency after initial parsing.
   The initial coordinator owns the one computed residency reading, used before first
   paint and adopted here after upgrade. This owner schedules later reads and informs
   annotation geometry and reading-region discovery when that composition changes.
   Imports are inert; boot opens it once for every interactive document. */
import { nextFrame, nextRender } from "./rendering.js";
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
  const { changed } = document.documentElement.lfInitial.residency();
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
// and whether the page arranged the box the breakout is in (prepaint.js, `indents`).
// A breakout a revision or a widget inserts, or one a holder reveals (a panel losing
// `hidden`, a disclosure opening), is read in the microtask its arrival queues. A
// holder a class or a script moves or pads anew keeps its reading until the next pass.
const BREAKOUT = "[data-lf-space]";
const bringsBreakout = (node) =>
  node.nodeType === Node.ELEMENT_NODE &&
  (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
function readIndents() {
  const { changed } = document.documentElement.lfInitial.indents();
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
    }).observe(main, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-lf-space", "hidden", "open"],
    });
  readResidency();
}

export const residencyStarted = () => residencyOpen;
