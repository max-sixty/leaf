/* Native banner controls derived from the page's command declarations.
 * `touch` names a control a finger needs; the same control serves a mouse. Page commands
 * stand behind More, and the innermost active scope supplies gesture steps on the row.
 * Words, availability and activation all come from the same row as keyboard dispatch.
 */
import {
  BANNER_CONTROL_RANK,
  bannerStanding,
  bannerControlDoor,
  dismissBannerControls,
  registerBannerControl,
  restoreBannerStanding,
  showBannerControls,
} from "../banner-toolbar.js";
import { el } from "../widget-elements.js";
import { keepsText } from "../keeps.js";
import { live, word } from "./bindings.js";
import { invokePress, standing } from "./dispatch.js";
import { touchPresses } from "./register.js";
import { keys } from "./scopes.js";
import { focusDestination, closeLayer } from "../focus.js";

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
  // A step acts on what the user stands on, so its press leaves them standing there
  // rather than moving focus onto the banner, as Done on the task they stand at reads.
  if (seat === "gesture")
    button.addEventListener("mousedown", (event) => event.preventDefault());
  button.addEventListener("click", () => {
    const { press: current } = controls.get(press.id);
    if (seat === "menu") {
      // A surface the press opens hands focus back to where it was opened from, and the
      // entry is about to close with its menu.
      const held = bannerStanding();
      closeLayer(dismissBannerControls, () => {
        if (current.row.retainStanding) restoreBannerStanding(held);
        else {
          const door = bannerControlDoor(button);
          if (door) focusDestination(door, "return");
        }
      });
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
  // An exact focused button owns its native activation before a surrounding scope's
  // Enter meaning. The semantic press still runs only through the click adapter above.
  keys(button, "Banner controls", [
    {
      id: press.id,
      keys: ["Enter", " "],
      title: () => word(controls.get(press.id).press.words),
      control: button,
    },
  ]);
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
    const on = shown.has(id);
    if (on) {
      keepsText(button, word(press.words));
      const disabled = !live(press.row);
      if (button.disabled !== disabled) button.disabled = disabled;
    }
    presence.push([button, on]);
  }
  showBannerControls(presence);
}
