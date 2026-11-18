/* A walk's owner declares its live position after arriving, independently of the
   host's status UI. The reader stays authoritative as its list changes; a different
   current target retires the declaration. Leaf hears `lf-walk` to present it, while
   another host can read the same position without importing page services.

   The owner declares facts, and the host decides what to show: what one stop is
   (`noun`), where the walk stands (`read`), the elements a list on screen stands in
   (`list`), and whether the words standing in the page's field name the list
   (`named`). Leaf's panel then says only what the screen doesn't
   (walk-position.js, `walkWords`), and a listener hears the whole position, which
   `beginWalk` returns for the owner to announce, since a listener sees no list. The
   user asked for this over each owner choosing what the panel shows, which no owner
   could choose right where the panel's own words already named the list. */
export const WALK = "lf-walk";

/** @typedef {{target: unknown, position: number, total: number, qualifier: string}} WalkPosition
 * @typedef {{list?: (() => readonly (Element | null | undefined)[]) | null, named?: boolean}} WalkFacts
 * @typedef {{key: string, noun: string | null, read: () => WalkPosition | null,
 *   target: unknown, list: WalkFacts["list"], named: boolean}} Walking */
/** @type {Walking | null} */
let walking = null; // never a list snapshot

// "Thread 2 of 5"; for a walk over several kinds, which names its list in the
// qualifier, "2 of 5 waiting on me".
/** @param {string | null} noun @param {number} position @param {number} total @param {string} [qualifier] */
export function walkPositionLabel(noun, position, total, qualifier = "") {
  return [noun, `${position} of ${total}`, qualifier].filter(Boolean).join(" ");
}

// The common reading for a DOM or model list. `identity` is the owner's stable key;
// the current item may be a fresh projection of the same destination on a later paint.
/** @template T @param {readonly T[]} items @param {T | null | undefined} current
 * @param {{identity?: (item: T) => unknown, qualifier?: string}} [options]
 * @returns {WalkPosition | null} */
export function listWalkPosition(
  items,
  current,
  { identity = (item) => item, qualifier = "" } = {},
) {
  if (!current) return null;
  const target = identity(current);
  const index = items.findIndex((item) => identity(item) === target);
  if (index < 0) return null;
  return { target, position: index + 1, total: items.length, qualifier };
}

export function walkPosition() {
  if (!walking) return null;
  const position = walking.read();
  if (!position || position.target !== walking.target) {
    walking = null;
    return null;
  }
  return {
    kind: walking.key,
    target: position.target,
    position: position.position,
    total: position.total,
    text: walkPositionLabel(
      walking.noun,
      position.position,
      position.total,
      position.qualifier,
    ),
    place: walkPositionLabel(null, position.position, position.total),
    list: Boolean(walking.list),
    named: walking.named,
  };
}

// A keyboard walk has arrived. The caller still owns and announces the motion; this
// records the owner's live reading so every such walk says its position the same way,
// and returns the whole position for the owner's announcement, "Change 2 of 5 since
// v2". `noun` names one stop, or is null for a list of several kinds, which the
// reading's qualifier names, as "2 of 5 waiting on me" does; such a walk never names
// the kind of the stop the user stands on, which is in front of them. A walk within a
// list on screen, such as a tab strip, a question's options or a chart's points, gives
// `list`, the elements the list stands in: its first and last stops, or one element
// holding it. `named` says the words standing in the page's field name the list, as a
// comparison's "5 changes since v2" names its changes.
//
// The host may decline to present a step, as Leaf does where the whole list stands in
// view and the ring already shows the place (walk-position.js): the walk the user came
// by, such as On Me's, then goes on standing.
/** @param {string} key @param {string | null} noun @param {() => WalkPosition | null} read
 * @param {WalkFacts} [facts] */
export function beginWalk(key, noun, read, { list = null, named = false } = {}) {
  const position = read();
  if (!position) {
    walking = null;
    return null;
  }
  const before = walking;
  walking = { key, noun, read, list, named, target: position.target };
  const words = walkPosition()?.text ?? null;
  if (!window.dispatchEvent(new CustomEvent(WALK, { cancelable: true, detail: list })))
    walking = before;
  return words;
}
