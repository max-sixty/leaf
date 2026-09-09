/* The transient position of a clamped Leaf walk. Owners keep the list and motion;
   this module keeps only a reader for the standing destination. Reading the list on
   every paint means a resolved thread, answered Ask, disappearing leaf, or replaced
   version cannot leave a stale denominator behind. Reaching the same destination
   twice means the clamped walk met its boundary; that state briefly gives the
   unchanged ordinal an accent face. Cyclic focus loops and package-owned widget walks
   keep their local feedback instead: neither has a Leaf-list boundary to report. */
import { paintHere } from "./keyboard/scopes.js";

const BOUNDARY_MS = 900;

let walking = null; // {key, noun, read, target, boundary}; never a list snapshot
let boundaryTimer = 0;

export function walkPositionLabel(noun, position, total, qualifier = "") {
  if (!noun) throw new Error("leaf: a walk position needs a noun");
  return `${noun} ${position} of ${total}${qualifier ? ` ${qualifier}` : ""}`;
}

// The common reading for a DOM or model list. `identity` is the owner's stable key;
// the current item may be a fresh projection of the same destination on a later paint.
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
    clearTimeout(boundaryTimer);
    boundaryTimer = 0;
    walking = null;
    return null;
  }
  return {
    boundary: walking.boundary,
    kind: walking.key,
    text: walkPositionLabel(
      walking.noun,
      position.position,
      position.total,
      position.qualifier,
    ),
  };
}

// A clamped walk has arrived. The caller still owns and announces the motion; this
// records the owner's live reading so every such walk gets one boundary treatment.
export function beginWalk(key, noun, read) {
  if (!key || typeof read !== "function")
    throw new Error("leaf: a walk position needs an owner and a reading");
  const position = read();
  if (!position) throw new Error("leaf: a walk position needs a destination");
  walkPositionLabel(noun, position.position, position.total, position.qualifier);
  const boundary = walking?.key === key && walking.target === position.target;
  clearTimeout(boundaryTimer);
  const arrived = {
    boundary,
    key,
    noun,
    read,
    target: position.target,
  };
  walking = arrived;
  boundaryTimer = boundary
    ? setTimeout(() => {
        if (walking !== arrived) return;
        arrived.boundary = false;
        boundaryTimer = 0;
        paintHere();
      }, BOUNDARY_MS)
    : 0;
  const standing = walkPosition();
  paintHere();
  return standing?.text ?? null;
}
