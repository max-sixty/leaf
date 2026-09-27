/* The banner controls that stand in for the page's keys under a finger.

   A row declaring `touch` words is one a finger has no other way to reach (AGENTS.md,
   "Touch routes"). On a coarse pointer each such page command is an entry in the banner's
   More, and each such row of a page scope is the gesture step on the row while a scope
   holding it stands, which is how a finger leaves a mode or the chooser. The row is the
   one home: the control's words are its `touch`, it is enabled while the row is live, and
   a press makes the row's own press.

   Each paint reads the rows from the live register, building a control the first time a
   row appears and hiding one whose row has left. It runs in the standing content phase: a
   step arriving on the row changes the banner's box, which chrome layout measures next. */
import {
  BANNER_CONTROL_RANK,
  bannerControlDoor,
  dismissBannerControls,
  registerBannerControl,
  showBannerControl,
} from "../banner-shelf.js";
import { coarsePointer } from "../pointer.js";
import { el, keepsText } from "../widget-elements.js";
import { repaint } from "../repaint.js";
import { live, word } from "./bindings.js";
import { invokeRow, standing } from "./dispatch.js";
import { touchRows } from "./register.js";

coarsePointer.addEventListener("change", repaint);

const controls = new Map();

function controlFor(row, seat) {
  let button = controls.get(row);
  if (button) return button;
  button = el("button", "lf-btn");
  button.type = "button";
  button.addEventListener("click", () => {
    if (seat === "menu") {
      // A surface the press opens hands focus back to where it was opened from, and the
      // entry is about to close with its menu.
      dismissBannerControls();
      bannerControlDoor(button)?.focus({ preventScroll: true });
    }
    if (live(row)) invokeRow(row);
  });
  registerBannerControl({
    key: `command:${row.id}`,
    control: button,
    rank: seat === "menu" ? BANNER_CONTROL_RANK.commands : BANNER_CONTROL_RANK.steps,
    seat,
    present: false,
  });
  controls.set(row, button);
  return button;
}

export function paintTouchControls() {
  const { commands, steps } = touchRows();
  const shown = new Map([
    ...commands.map((row) => [row, controlFor(row, "menu")]),
    ...steps
      .filter(({ standsIn }) => standsIn.some(standing))
      .map(({ row }) => [row, controlFor(row, "gesture")]),
  ]);
  for (const [row, button] of controls) {
    const on = coarsePointer.matches && shown.has(row);
    if (on) {
      keepsText(button, word(row.touch));
      const disabled = !live(row);
      if (button.disabled !== disabled) button.disabled = disabled;
    }
    showBannerControl(button, on);
  }
}
