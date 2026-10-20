/* What the page says between notices about where the keyboard has the user: the Go-to
 * filter's word while a `g` sequence holds one, a walk's position ("1 of 3 threads")
 * after a list walk, or the stance the user stands in ("In Draw mode",
 * touch-controls.js), which the agent's status yields to for as long as it holds. The
 * floating panel says it in its seat for passing words (floating-panel.js, `passing`),
 * which registers to hear when it changes, as a notice's seats do. A retired walk keeps
 * its last wording, so the seat's words do not vanish under a notice that stands over
 * them. Painted in the repaint frame (repaint.js), after the touch controls, since these
 * readings follow focus, the sequence's state and the register. */
import { setNoticeContext } from "../notifications.js";
import { walkPosition } from "../walk-position.js";
import { stanceReading } from "./touch-controls.js";

const EMPTY = Object.freeze({ goTo: null, walk: null, stance: null });
let context = EMPTY;
let lastWalk = null;
const presenters = new Set();

export const statusContextReading = () => context;
export function registerStatusContextPresentation(invalidate) {
  presenters.add(invalidate);
}

const shownWalk = ({ walk }) => (walk?.shown ? walk : null);
const same = (a, b) =>
  a.goTo === b.goTo &&
  a.stance === b.stance &&
  shownWalk(a)?.text === shownWalk(b)?.text &&
  shownWalk(a)?.boundary === shownWalk(b)?.boundary;

/** Read the context again, `goToStatus` the Go-to sequence's word or null. */
export function paintStatusContext(goToStatus) {
  const position = walkPosition();
  const goTo = goToStatus();
  if (position)
    lastWalk = Object.freeze({
      kind: position.kind,
      text: position.text,
      boundary: position.boundary,
    });
  const before = context;
  context = Object.freeze({
    goTo,
    walk: lastWalk ? Object.freeze({ ...lastWalk, shown: Boolean(position) }) : null,
    stance: stanceReading(),
  });
  setNoticeContext(Boolean(goTo));
  if (!same(context, before)) for (const invalidate of presenters) invalidate();
}
