/* The banner controls that stand in for the page's keys under a finger.

   A press declaring `touch` words, a row's or one route's of a routed row, is one a finger
   has no other way to make (AGENTS.md, "Touch routes"). On a coarse pointer each such
   press of a page command is an entry in the banner's More, and a page scope's are the
   gesture steps on the row while it is the innermost standing scope that has any: how a
   finger leaves a mode or the picker, or walks search matches. One scope's steps stand
   at a time, since a phone's row has room for one interaction's. The row is the one home: the control's
   words are its `touch`, it is enabled while the row is live, and a tap makes the press.

   Each paint reads the presses from the live register, building a control the first time
   one appears and hiding one whose row has left. It runs in the standing content phase: a
   step arriving on the row changes the banner's box, which chrome layout measures next. */
import {
  BANNER_CONTROL_RANK,
  bannerStanding,
  bannerControlDoor,
  dismissBannerControls,
  registerBannerControl,
  restoreBannerStanding,
  showBannerControls,
} from "../banner-toolbar.js";
import { coarsePointer } from "../pointer.js";
import { el } from "../widget-elements.js";
import { keepsText } from "../keeps.js";
import { repaint } from "../repaint.js";
import { live, word } from "./bindings.js";
import { invokePress, standing } from "./dispatch.js";
import { touchPresses } from "./register.js";

coarsePointer.addEventListener("change", repaint);

// Each press's control, by the command it invokes, beside the press as last read.
const controls = new Map();

function place(press, seat) {
  const held = controls.get(press.id);
  if (held) {
    held.press = press;
    return press.id;
  }
  const button = el("button", "lf-btn");
  button.type = "button";
  button.addEventListener("click", () => {
    const { press: current } = controls.get(press.id);
    if (seat === "menu") {
      // A surface the press opens hands focus back to where it was opened from, and the
      // entry is about to close with its menu.
      const held = bannerStanding();
      dismissBannerControls();
      if (current.row.retainStanding) restoreBannerStanding(held);
      else bannerControlDoor(button)?.focus({ preventScroll: true });
    }
    if (live(current.row)) invokePress(current);
  });
  registerBannerControl({
    key: `command:${press.id}`,
    control: button,
    rank: seat === "menu" ? BANNER_CONTROL_RANK.commands : BANNER_CONTROL_RANK.steps,
    seat,
    present: false,
  });
  controls.set(press.id, { press, button });
  return press.id;
}

export function paintTouchControls() {
  const { commands, steps } = touchPresses();
  // Every step is placed before any is shown, so the row orders them as they are declared
  // rather than by which the user happened to reach first.
  for (const { presses } of steps) for (const press of presses) place(press, "gesture");
  const innermost = steps.find(({ scope }) => standing(scope));
  const shown = new Set([
    ...commands.map((press) => place(press, "menu")),
    ...(innermost?.presses.map((press) => press.id) ?? []),
  ]);
  const presence = [];
  for (const [id, { press, button }] of controls) {
    const on = coarsePointer.matches && shown.has(id);
    if (on) {
      keepsText(button, word(press.words));
      const disabled = !live(press.row);
      if (button.disabled !== disabled) button.disabled = disabled;
    }
    presence.push([button, on]);
  }
  showBannerControls(presence);
}
