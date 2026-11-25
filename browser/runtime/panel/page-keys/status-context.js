/* What the page says between notices about where the keyboard has the user: the Go-to
 * filter's word while a `g` sequence holds one, a walk's position ("1 of 3 threads")
 * after a list walk, and what the stance the user is in says, its `says` or else its
 * title ("Draw"; dom/keyboard/dispatch.js, `innermostStance`).
 * The floating panel reads this signal for its empty field, where the Go-to words, or
 * a walk's position for its step's moment, take the status's place, and which takes
 * no words while a stance stands (panel/field-readings.js, `still`); its row names the
 * stance beside the stance's ✕ by `stanceWords`, read when it paints. Painted in the repaint
 * frame (dom/repaint.js), since these readings follow focus, the sequence's state and the
 * register. A walk's reading
 * also names the stop it stands on (`target`, its owner's key), so a list that shows
 * the walk's items, as On Me does, can mark the one the walk is at. */
import { signal } from "/vendor/signals-core.js";
import { setNoticeContext } from "../../transport/notifications.js";
import { walkPosition } from "../../records/walk-position.js";
import { word } from "../../dom/keyboard/bindings.js";
import { innermostStance } from "../../dom/keyboard/dispatch.js";

/** @typedef {NonNullable<ReturnType<typeof walkPosition>>} Walk
 * @typedef {{goTo: string | null, walk: Walk | null, stance: string | null}} StatusContext
 */
/** @type {StatusContext} */
const EMPTY = Object.freeze({ goTo: null, walk: null, stance: null });
const context = signal(EMPTY);
export const statusContextReading = () => context.value;
/** What a stance says of itself: its `says`, or else its title.
 * @param {import("../../dom/keyboard/bindings.js").Scope | null | undefined} scope */
export const stanceWords = (scope) =>
  (scope ? word(scope.says ?? scope.title) : null) ?? null;

/** @param {StatusContext} a @param {StatusContext} b */
const same = (a, b) =>
  a.goTo === b.goTo &&
  a.stance === b.stance &&
  a.walk?.kind === b.walk?.kind &&
  a.walk?.text === b.walk?.text &&
  a.walk?.target === b.walk?.target;

/** Read the context again, `goToStatus` the Go-to sequence's word or null. */
/** @param {() => string | null} goToStatus */
export function paintStatusContext(goToStatus) {
  const position = walkPosition();
  const goTo = goToStatus();
  const next = Object.freeze({
    goTo,
    walk: position ? Object.freeze(position) : null,
    stance: stanceWords(innermostStance()?.scope),
  });
  setNoticeContext(Boolean(goTo));
  if (!same(next, context.peek())) context.value = next;
}
