/* Where the reader is standing, painted: the ring on the Ask they are in, the mark on
   the passage of the comment they are in, the focused box's hint, and the line saying what
   the next press does from there. One repaint, because it is one question — every reading
   is of the focus and the open-Ask list, and every signal that moves either (a focus
   move, an answer taken, a poll, a widget's own state) moves them all.

   The frame that carries this paint is the register's (scopes.js: paintHere), which is
   where every module that declares keys asks for it; leaf.js registers this painting
   into that frame as its first boot step. */
import { markHere } from "./asks/view.js";
import { paintStanding } from "./anchors.js";
import { renderLine } from "./keyboard/keyline.js";
import { syncLayout } from "./chrome-layout.js";
import { paintAddresses } from "./keyboard/address.js";
import { paintTargets } from "./composing/targets.js";
import { paintCoreControls } from "./keyboard/page.js";
import { paintInputs } from "./composing/input.js";

// Everything a move of the reader's standing repaints, in the order the geometry demands.
export function paintStandingChrome() {
  markHere();
  paintStanding();
  // The key line is geometry for every address and target painted around it. Render
  // its new words first, then let chrome-layout.js place that resulting
  // box before any consumer reads it. ResizeObserver remains the door for font, window,
  // and other size changes; state-driven content changes complete in this frame rather
  // than leaving placement and hints one observer frame behind.
  renderLine();
  syncLayout();
  // The chips are where the reader can go, beside the ring saying where they are and the
  // line saying what the next press does — one paint, because a chip repainted by its
  // own door alone went stale on the door it did not
  // have: a poll that retires an Ask moves the list under an armed window, and only the
  // panel's own render was calling the chip pass.
  paintAddresses();
  paintTargets();
  paintCoreControls();
  paintInputs();
}
