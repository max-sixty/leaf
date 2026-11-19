/* A walk's owner declares its live position after arriving, independently of the
   host's status UI. The reader stays authoritative as its list changes; a different
   current target retires the declaration. Leaf hears `lf-walk` to present it, while
   another host can read the same position without importing page services. */
export const WALK = "lf-walk";

/** @typedef {{target: unknown, position: number, total: number, qualifier: string}} WalkPosition */
/** @type {{key: string, noun: string | null, read: () => WalkPosition | null, target: unknown} | null} */
let walking = null; // {key, noun, read, target}; never a list snapshot

// "Thread 2 of 5"; for a walk over several kinds, which names its list in the
// qualifier, "2 of 5 waiting on me"; and for a list on screen, "2 of 14".
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
  };
}

// A keyboard walk has arrived. The caller still owns and announces the motion; this
// records the owner's live reading so every such walk says its position the same way.
// The position says what the screen doesn't. A walk that carries the user across the
// page names its list (`noun`, or for a list of several kinds the reading's
// `qualifier`), "Thread 2 of 5", since the rest of that list is out of view, unless
// the panel already names it, as it does a comparison's changes. A walk inside a list
// on screen, such as a tab strip or the Page Map, passes no noun and says only its
// place, "2 of 14", since the user sees which list it is but perhaps not where it
// ends. A walk over a list wholly in view, such as a question's options or a reaction
// bar, declares no walk at all: the ring already shows where it stands, and the walk
// the user came by, such as On Me's, goes on saying where they are. A walk over
// several kinds never names the kind of the item the user stands on, which is in
// front of them. The owner may announce fuller words than the panel shows, since a
// listener sees no list.
/** @param {string} key @param {string | null} noun @param {() => WalkPosition | null} read */
export function beginWalk(key, noun, read) {
  const position = read();
  if (!position) {
    walking = null;
    return null;
  }
  walking = { key, noun, read, target: position.target };
  const shown = walkPosition();
  window.dispatchEvent(new Event(WALK));
  return shown?.text ?? null;
}
