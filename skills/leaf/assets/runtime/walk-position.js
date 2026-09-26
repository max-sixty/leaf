/* The transient position of a Leaf keyboard walk, and the one walk over a flat list of
   focusable rows (`rowWalk`). Other walks' owners keep their list and motion and give
   this module only a reader for the standing destination. Owners keep that
   reading current from the source's invalidation signal — directly on paint for cheap
   lists, or through a refreshed cache for an expensive source such as the page-text
   index — so a resolved thread, answered Ask, disappearing leaf, or replaced version
   cannot leave a stale denominator behind. Reaching the same destination twice means
   the walk could not move; that state briefly gives the unchanged ordinal an accent
   face. Both clamped and cyclic semantic walks use this reading. Native focus traversal
   and gestures that rearrange state are not walks through a named list. */
import { clampedRow } from "./keyboard/bindings.js";
import { holdStatus } from "./notifications.js";
import { repaint } from "./repaint.js";

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

// The walk over a flat list of focusable rows, declared once for every list that has
// one: ArrowUp and ArrowDown step and clamp, Home and End land on the ends, and every
// landing reports its position. It returns the two register rows, `<id>.walk` and
// `<id>.edge`, for the owner's own scope; `id` is also the walk's position key and the
// prefix of each route. `steps` names the four routes and their words, in the order
// ArrowUp, ArrowDown, Home, End, for a list whose ends have a meaning of their own.
// `landed(row)` runs after a press that moved focus to another row. Tabs and spatial
// grids own cyclic policies; the Page Map and the page's Ask walk keep their own
// placement readings.
const STEPS = Object.freeze(["previous", "next", "first", "last"]);
const capital = (word) => word[0].toUpperCase() + word.slice(1);
export function rowWalk({ id, noun, plural, rows, steps = STEPS, landed }) {
  const [up, down, home, end] = steps;
  const route = (binding, step) => ({
    id: `${id}.${step}`,
    binding,
    does: `${capital(step)} ${noun.toLowerCase()}`,
  });
  const land = (pick) => {
    const was = document.activeElement;
    const row = pick(rows());
    if (!row) return;
    row.focus();
    beginWalk(id, noun, () => listWalkPosition(rows(), document.activeElement));
    if (row !== was) landed?.(row);
  };
  return [
    {
      id: `${id}.walk`,
      keys: ["ArrowUp", "ArrowDown"],
      routes: [route("ArrowUp", up), route("ArrowDown", down)],
      does: `Walk the ${plural}`,
      line: `walk the ${plural}`,
      repeat: true,
      run: (binding) =>
        land((list) =>
          clampedRow(list, document.activeElement, binding === "ArrowDown" ? 1 : -1, 0),
        ),
    },
    {
      id: `${id}.edge`,
      keys: ["Home", "End"],
      routes: [route("Home", home), route("End", end)],
      does: `${capital(home)} / ${end} ${noun.toLowerCase()}`,
      line: `${home} / ${end}`,
      run: (binding) => land((list) => (binding === "Home" ? list[0] : list.at(-1))),
    },
  ];
}

// A keyboard walk has arrived. The caller still owns and announces the motion; this
// records the owner's live reading so every such walk gets one boundary treatment.
export function beginWalk(key, noun, read) {
  if (!key || typeof read !== "function")
    throw new Error("leaf: a walk position needs an owner and a reading");
  const position = read();
  if (!position) {
    clearTimeout(boundaryTimer);
    boundaryTimer = 0;
    walking = null;
    return null;
  }
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
  holdStatus(BOUNDARY_MS);
  boundaryTimer = boundary
    ? setTimeout(() => {
        if (walking !== arrived) return;
        arrived.boundary = false;
        boundaryTimer = 0;
        repaint();
      }, BOUNDARY_MS)
    : 0;
  const standing = walkPosition();
  repaint();
  return standing?.text ?? null;
}
