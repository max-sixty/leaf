/* What the page says between notices about where the keyboard has the user: the Go-to
 * filter's word while a `g` sequence holds one, a walk's position ("1 of 3 threads")
 * after a list walk, and the title of the stance the user stands in ("In Draw mode",
 * dispatch.js, `innermostStance`). The floating panel says the first two in its seat for
 * passing words (floating-panel.js, `passing`) and the stance in its empty page field,
 * in the agent's status's place. Its reads subscribe to their signal. A retired walk
 * keeps its last wording, so the seat's words do not vanish
 * under a notice that stands over them. Painted in the repaint frame (repaint.js), since
 * these readings follow focus, the sequence's state and the register. A walk's reading
 * also names the stop it stands on (`target`, its owner's key), so a list that shows
 * the walk's items, as On me does, can mark the one the walk is at. */
import { signal } from "/vendor/browser-runtime.js";
import { setNoticeContext } from "../notifications.js";
import { walkPosition } from "../walk-position.js";
import { word } from "./bindings.js";
import { innermostStance } from "./dispatch.js";

const EMPTY = Object.freeze({ goTo: null, walk: null, stance: null });
const context = signal(EMPTY);
let lastWalk = null;
export const statusContextReading = () => context.value;

const shownWalk = ({ walk }) => (walk?.shown ? walk : null);
const same = (a, b) =>
  a.goTo === b.goTo &&
  a.stance === b.stance &&
  shownWalk(a)?.text === shownWalk(b)?.text &&
  shownWalk(a)?.target === shownWalk(b)?.target &&
  shownWalk(a)?.boundary === shownWalk(b)?.boundary;

/** Read the context again, `goToStatus` the Go-to sequence's word or null. */
export function paintStatusContext(goToStatus) {
  const position = walkPosition();
  const goTo = goToStatus();
  if (position)
    lastWalk = Object.freeze({
      kind: position.kind,
      target: position.target,
      text: position.text,
      boundary: position.boundary,
    });
  const next = Object.freeze({
    goTo,
    walk: lastWalk ? Object.freeze({ ...lastWalk, shown: Boolean(position) }) : null,
    stance: word(innermostStance()?.scope.title) ?? null,
  });
  setNoticeContext(Boolean(goTo));
  if (!same(next, context.peek())) context.value = next;
}
