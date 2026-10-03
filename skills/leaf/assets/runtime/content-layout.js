/* Authored sidebar, sidenote and contents-outline residency.
   The upgraded document and its computed layout are the sole input. The selected
   annotation view declares whether its rail occupies right-side room, and receives
   every completed reading; it owns all annotation paint and geometry. Imports are
   inert. Boot opens this owner once, after upgrade, for live documents. */
import { nextFrame, nextRender } from "./rendering.js";
import { skipped } from "./geometry.js";
import { keeps } from "./keeps.js";
import { repaintPage } from "./repaint.js";
// The postures a margin resident may take besides the rail: the side each stands on and
// the token holding the room it needs there beyond `main`'s box. The stylesheet says
// which element takes which, in order of preference (`--lf-resident`, theme.css, at
// aside.sidebar), so the media and Layout conditions on each are the stylesheet's own.
const POSTURES = {
  sidebar: ["left", "--sidebar"],
  map: ["left", "--map"],
  note: ["right", "--note"],
};

// One computed reading seats the rail first without moving the column, then each
// authored resident on its preferred side, or in flow when there is no room. The
// column's actual CSS offset is removed before measuring, including RTL, so its
// last written shift cannot feed the next decision. Theme's --lf-resident declares
// posture preferences; data-lf-margin and --lf-shift publish their geometry.
// Read at most once per frame after widgets upgrade. Every completed read notifies
// the selected annotation owner, including an unchanged or missing column; only a
// changed reading repaints page geometry. Imports never start this document owner.
let residencyOpen = false;
let annotationRoom = false;
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
  const changed = settleResidency();
  readFinished(changed);
  if (changed) repaintPage();
}
export function scheduleResidency() {
  if (residencyOpen) residencyPending ||= nextRender(residencyPass);
}
export function openResidency({ rail, onRead }) {
  annotationRoom = rail;
  readFinished = onRead;
  residencyOpen = true;
  document.addEventListener("toggle", scheduleResidency, { capture: true });
  readResidency();
}

export const residencyStarted = () => residencyOpen;

function settleResidency() {
  const main = document.querySelector("main");
  if (!main) return false;
  const style = getComputedStyle(main);
  const need = (token) => parseFloat(style.getPropertyValue(token)) || 0;
  // The offset the column stands at, which is the written shift only where the Layout
  // applies it: page CSS may override the offset, and under `dir="rtl"` it is `right`.
  const shifted =
    style.position === "relative"
      ? parseFloat(style.left) || -parseFloat(style.right) || 0
      : 0;
  const written = parseFloat(main.style.getPropertyValue("--lf-shift")) || 0;
  const column = main.getBoundingClientRect();
  const shell = document.body.getBoundingClientRect();
  const room = {
    left: column.left - shifted - shell.left,
    right: shell.right - column.right + shifted,
  };
  const taken = { left: 0, right: 0 };
  const standing = [];
  if (
    annotationRoom &&
    document.body.getAttribute("data-rail") !== "none" &&
    room.right >= need("--rail")
  ) {
    standing.push("rail");
    taken.right = need("--rail");
  }
  const declared = new Map();
  // A resident a box around it hides (a closed disclosure, a tab not chosen) needs no
  // room. One the page hides itself stays a resident, since a page may hide it until it
  // stands in the margin. One in skipped content is asked nothing (`skipped`).
  for (const aside of main.querySelectorAll("aside")) {
    if (skipped(aside)) continue;
    const own = getComputedStyle(aside);
    const hiddenItself =
      own.display === "none" && aside.parentElement.checkVisibility();
    if (!aside.checkVisibility() && !hiddenItself) continue;
    const postures = own
      .getPropertyValue("--lf-resident")
      .split(" ")
      .filter((posture) => posture in POSTURES);
    if (postures.length) declared.set(postures.join(" "), postures);
  }
  const side = (postures) => POSTURES[postures[0]][0];
  for (const postures of [...declared.values()].sort(
    (a, b) => (side(a) === "left" ? 0 : 1) - (side(b) === "left" ? 0 : 1),
  ))
    for (const posture of postures) {
      const [at, token] = POSTURES[posture];
      const wants = { ...taken, [at]: Math.max(taken[at], need(token)) };
      if (wants.left + wants.right > room.left + room.right + 0.5) continue;
      standing.push(posture);
      Object.assign(taken, wants);
      break;
    }
  const shift = Math.round(
    taken.left > room.left
      ? taken.left - room.left
      : taken.right > room.right
        ? room.right - taken.right
        : 0,
  );
  const tokens = standing.join(" ");
  const changed =
    (main.getAttribute("data-lf-margin") ?? "") !== tokens || shift !== written;
  if (!changed) return false;
  keeps(main, "data-lf-margin", tokens || null);
  if (shift !== written) {
    if (shift) main.style.setProperty("--lf-shift", `${shift}px`);
    else main.style.removeProperty("--lf-shift");
  }
  return true;
}
