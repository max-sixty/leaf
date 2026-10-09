/* Where putting a reply's reaction choices away hands the user back.

   The close names its candidates, the bar's field, the control the press stood the user
   on, and the list's trigger, and hands the user to the first the close leaves standing.
   Asked over happy-dom's focus and inline `display`, since it lays nothing out, gives
   `hidden` no style and draws no popover. */

import assert from "node:assert/strict";
import test from "node:test";

const { createReactionController } = await import("/runtime/reactions.js");
const { focusDestination, focused } = await import("/runtime/focus.js");

test("closing the choices hands the user to a trigger the close itself shows", () => {
  document.body.replaceChildren();
  const opener = document.createElement("button");
  const trigger = document.createElement("button");
  [opener.id, trigger.id] = ["opener", "trigger"];
  const surface = document.createElement("div");
  const palette = document.createElement("span");
  // happy-dom has no popovers; the list's showing and hiding is the platform's.
  palette.showPopover = palette.hidePopover = () => {};
  surface.append(trigger, palette);
  document.body.append(opener, surface);
  const reactions = createReactionController({
    fabAnchorAt: () => ({}),
    // Putting the bar back as the choices go takes the opener away and shows the trigger.
    showFab: () => {
      opener.style.display = "none";
      trigger.style.display = "";
    },
    foldMarginEntryOptions: () => {},
  });
  const list = reactions.registerReactSurface(surface, { palette, trigger });
  focusDestination(opener, "move");
  list.toggle();
  trigger.style.display = "none";
  focused()?.blur();
  list.close();
  // By id: a failing comparison of happy-dom nodes never finishes printing them.
  assert.equal(focused()?.id || focused()?.localName, "trigger");
});
