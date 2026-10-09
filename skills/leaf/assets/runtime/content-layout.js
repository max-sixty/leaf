/* Authored sidebar, sidenote and contents-outline residency after initial parsing.
   The initial coordinator owns the one computed residency reading, used before first
   paint and adopted here after upgrade. This owner schedules later reads and informs
   annotation geometry and reading-region discovery when that composition changes.
   Imports are inert; boot opens it once for every interactive document. */
import { nextFrame, nextRender } from "./rendering.js";
import { repaintPage } from "./repaint.js";
import { layoutChanged } from "./widget-elements.js";
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
  const changed = document.documentElement.lfInitial.residency();
  if (changed) layoutChanged(document.querySelector("main"));
  readFinished?.(changed);
  if (changed) repaintPage();
}
export function scheduleResidency() {
  if (residencyOpen) residencyPending ||= nextRender(residencyPass);
}
export function openResidency({ onRead }) {
  readFinished = onRead;
  residencyOpen = true;
  document.addEventListener("toggle", scheduleResidency, { capture: true });
  window.addEventListener("resize", scheduleResidency);
  readResidency();
}

export const residencyStarted = () => residencyOpen;
