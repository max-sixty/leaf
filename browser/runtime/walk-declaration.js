/* A walk's owner declares its live position after arriving, independently of the
   host's status UI. The reader stays authoritative as its list changes; a different
   current target retires the declaration. Leaf hears `lf-walk` to present it, while
   another host can read the same position without importing page services. */
export const WALK = "lf-walk";

/** @typedef {{target: unknown, position: number, total: number, qualifier: string}} WalkPosition */
/** @type {{key: string, noun: string | null, read: () => WalkPosition | null, target: unknown} | null} */
let walking = null; // {key, noun, read, target}; never a list snapshot

// "Thread 2 of 5", or, for a walk over several kinds that names its list in the
// qualifier, "2 of 5 waiting on me · Thread" with the kind given there instead.
/** @param {string | null} noun @param {number} position @param {number} total @param {string} [qualifier] */
export function walkPositionLabel(noun, position, total, qualifier = "") {
  if (!noun && !qualifier) throw new Error("leaf: a walk position needs a noun");
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
/** @param {string} key @param {string | null} noun @param {() => WalkPosition | null} read */
export function beginWalk(key, noun, read) {
  const position = read();
  if (!position) {
    walking = null;
    return null;
  }
  walkPositionLabel(noun, position.position, position.total, position.qualifier);
  walking = { key, noun, read, target: position.target };
  const shown = walkPosition();
  window.dispatchEvent(new Event(WALK));
  return shown?.text ?? null;
}
