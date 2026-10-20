/* What the page says between notices about where the keyboard has the user: the Go-to
 * filter's word while a `g` sequence holds one, a walk's position ("1 of 3 threads")
 * after a list walk, and the title of the stance the user stands in ("In Draw mode",
 * dispatch.js, `innermostStance`). The floating panel says the first two in its seat for
 * passing words (floating-panel.js, `passing`) and the stance in its empty page field,
 * in the agent's status's place; it registers to hear when they change, as a notice's
 * seats do. A retired walk keeps its last wording, so the seat's words do not vanish
 * under a notice that stands over them. Painted in the repaint frame (repaint.js), since
 * these readings follow focus, the sequence's state and the register. */
import { setNoticeContext } from "../notifications.js";
import { walkPosition } from "../walk-position.js";
import { word } from "./bindings.js";
import { innermostStance } from "./dispatch.js";

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
    stance: word(innermostStance()?.scope.title) ?? null,
  });
  setNoticeContext(Boolean(goTo));
  if (!same(context, before)) for (const invalidate of presenters) invalidate();
}
