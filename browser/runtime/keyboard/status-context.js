/* What the page says between notices about where the keyboard has the user: the Go-to
 * filter's word while a `g` sequence holds one, a walk's position ("1 of 3 threads")
 * after a list walk, and what the stance the user is in says, its `says` or else its
 * title ("In Draw mode", "To-do · Try the build"; dispatch.js, `innermostStance`).
 * The floating panel reads this signal for its empty field, where a stance heads the
 * current walk or Go-to words in the page status's place (floating-panel.js,
 * `fieldReading`). A retired walk's retained reading has
 * `shown: false` and is not displayed. Painted in the repaint frame (repaint.js), since
 * these readings follow focus, the sequence's state and the register. A walk's reading
 * also names the stop it stands on (`target`, its owner's key), so a list that shows
 * the walk's items, as On me does, can mark the one the walk is at. */
import { signal } from "/runtime/framework.js";
import { setNoticeContext } from "../notifications.js";
import { walkPosition } from "../walk-position.js";
import { word } from "./bindings.js";
import { innermostStance } from "./dispatch.js";

/** @typedef {NonNullable<ReturnType<typeof walkPosition>>} Walk
 * @typedef {{goTo: string | null, walk: (Walk & {shown: boolean}) | null, stance: string | null}} StatusContext
 */
/** @type {StatusContext} */
const EMPTY = Object.freeze({ goTo: null, walk: null, stance: null });
const context = signal(EMPTY);
/** @type {Walk | null} */
let lastWalk = null;
export const statusContextReading = () => context.value;
/** @param {import("./bindings.js").Scope | null | undefined} scope */
const stanceWords = (scope) => (scope ? word(scope.says ?? scope.title) : null) ?? null;

/** @param {StatusContext} context */
const shownWalk = ({ walk }) => (walk?.shown ? walk : null);
/** @param {StatusContext} a @param {StatusContext} b */
const same = (a, b) =>
  a.goTo === b.goTo &&
  a.stance === b.stance &&
  shownWalk(a)?.text === shownWalk(b)?.text &&
  shownWalk(a)?.target === shownWalk(b)?.target;

/** Read the context again, `goToStatus` the Go-to sequence's word or null. */
/** @param {() => string | null} goToStatus */
export function paintStatusContext(goToStatus) {
  const position = walkPosition();
  const goTo = goToStatus();
  if (position)
    lastWalk = Object.freeze({
      kind: position.kind,
      target: position.target,
      position: position.position,
      total: position.total,
      text: position.text,
    });
  const next = Object.freeze({
    goTo,
    walk: lastWalk ? Object.freeze({ ...lastWalk, shown: Boolean(position) }) : null,
    stance: stanceWords(innermostStance()?.scope),
  });
  setNoticeContext(Boolean(goTo));
  if (!same(next, context.peek())) context.value = next;
}
