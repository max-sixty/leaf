/* A delayed completion may move the user only while the gesture that started it
   remains their latest intent. Runtime-owned repaint and focus changes do not supersede
   that intent, including a repaint dropping focus on a container of the surface that
   began the work; a later user input, leaving the window, or focus moving anywhere else
   does.

   Intent is captured at the gesture and handed to what the work later does: `reveal`
   takes it as a required argument, so no delayed caller can take a fresh one after its
   wait. Which inputs supersede it is focus.js's count (`inputCount`), the one reading of
   the user's inputs. */
import { carriedFrom, focused, inputCount } from "./focus.js";
import { renderedUnder } from "../lib/shadow-tree.js";

// Focus a repaint took from the source and dropped on a container holding it, as a
// list takes it from a card that folds, including where that container passed it on
// before any newer input, as the Threads list passes its focus to the thread it shows
// open. Focus that went anywhere else went somewhere in particular, as a widget handing
// it on does.
/** @type {WeakMap<Element, {container: Element, intent: number}>} */
const passed = new WeakMap();
/** @param {Element} container @param {Element} target */
export const passOn = (container, target) =>
  passed.set(target, { container, intent: inputCount() });
// So is focus a hold carried from the source, or from inside it, to the node a render put
// in its place, before any newer input.
/** @param {Node | undefined} source @param {Element | null} at */
const displaced = (source, at) => {
  if (!(source instanceof Node) || !at) return false;
  const via = passed.get(at);
  const carry = carriedFrom(at);
  return (
    renderedUnder(source, at) ||
    (via?.intent === inputCount() && renderedUnder(source, via.container)) ||
    (carry?.inputs === inputCount() &&
      (carry.from === source || renderedUnder(carry.from, source)))
  );
};

// Capture before the first asynchronous step. Pass this same predicate into nested
// reveals; capturing again after a wait gives stale work a newer gesture's authority.
// Document arrival names count zero: its work began before any module loaded,
// so a reader already using that document owns it even before this call runs. A
// return to an entry's record counts the user's inputs within the entry alone
// (`count`; focus.js, `entryInputCount`), so neither a step Back or Forward nor
// leaving the window supersedes it (records/history.js, `beginRestoration`).
// The source is held weakly: an intent can be kept long after its gesture, as a reading
// place keeps one, and a source the document has since dropped can neither hold focus
// nor be what focus was carried from, so it answers nothing a held node would.
/** @typedef {{(): boolean, available: () => boolean, handoff: (move: () => unknown) => boolean}} UserIntent */
/**
 * @returns {UserIntent}
 * @param {{
 *   source?: unknown,
 *   available?: () => boolean,
 *   fallback?: Element | null,
 *   count?: () => number,
 *   since?: number,
 * }} [options]
 */
export function retainUserIntent({
  source = focused(),
  available = () => true,
  fallback = null,
  count = inputCount,
  since = count(),
} = {}) {
  const retained = since;
  let held = source instanceof Node ? new WeakRef(source) : null;
  const current = () => {
    const at = focused();
    const from = held?.deref();
    // Containment reads across shadow trees, as a thread a widget draws in its own
    // shadow root stands inside the page that holds the widget.
    const withinSource =
      from === document.body ? at === document.body : renderedUnder(at, from);
    return Boolean(
      available() &&
      retained === count() &&
      (at === document.body || at === fallback || withinSource || displaced(from, at)),
    );
  };
  // The surface the work belongs to still stands, whoever holds focus.
  current.available = available;
  // Synchronous work may already have transferred focus, as a connected widget can
  // during replacement. Keep that destination instead of running the old focus move,
  // and adopt it for subsequent continuity without renewing the input generation.
  // A delayed caller must check current() before beginning its synchronous handoff.
  current.handoff = /** @param {() => unknown} move */ (move) => {
    if (!available() || retained !== count()) return false;
    const moved = current();
    if (moved) move();
    const at = focused();
    held = at ? new WeakRef(at) : null;
    return moved && current();
  };
  return current;
}

// A nested destination may stop being available while the original gesture waits. Restrict
// that same capability; taking a new intent would authorize stale work with newer input.
// Refine a retained gesture's availability without recapturing its generation. The
// same admission guards readiness and the actual focus/scroll handoff.
/** @param {UserIntent} retained @param {() => boolean} available @returns {UserIntent} */
export function restrictUserIntent(retained, available) {
  const current = () => available() && retained();
  current.available = () => available() && retained.available();
  current.handoff = /** @param {() => unknown} move */ (move) =>
    available() && retained.handoff(move);
  return current;
}
