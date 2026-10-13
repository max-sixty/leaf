/* The transient position of a Leaf keyboard walk, and the one walk over a flat list of
   focusable rows (`rowWalk`). Other walks' owners keep their list and motion and give
   this module only a reader for the standing destination. Owners keep that
   reading current from the source's invalidation signal — directly on paint for cheap
   lists, or through a refreshed cache for an expensive source such as the page-text
   index — so a resolved thread, answered ask, disappearing leaf, or replaced version
   cannot leave a stale denominator behind. An end of the list is news, so a landing
   briefly gives its ordinal an accent face where the walk met one: a clamped walk that
   reached the same destination twice could not move, and a cyclic walk that came round
   says so, since "1 of 5" reads the same after 5 as after nothing. Native focus traversal
   and gestures that rearrange state are not walks through a named list. */
import { scrollIntoView } from "./landing-scroll.js";
import { clampedRow } from "./keyboard/bindings.js";
import { holdStatus } from "./notifications.js";
import { repaint } from "./repaint.js";
import { focusDestination, focused } from "./focus.js";

const BOUNDARY_MS = 900;

let walking = null; // {key, noun, read, target, boundary}; never a list snapshot
let boundaryTimer = 0;

// "Thread 2 of 5", or, for a walk over several kinds that names its list in the
// qualifier, "2 of 5 waiting on you · Thread" with the kind given there instead.
export function walkPositionLabel(noun, position, total, qualifier = "") {
  if (!noun && !qualifier) throw new Error("leaf: a walk position needs a noun");
  return [noun, `${position} of ${total}`, qualifier].filter(Boolean).join(" ");
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
// `position` reads where a landing stands, by default its place among the rows. A list
// passes its own where the items it counts are narrower than the stops the walk lands
// on, as a fold's door between items is a stop and not an item, or where another walk
// over the same items already reports their position, so both say the same. A reader
// returns null for a landing it counts no item at, which shows no position.
// `landed(row)` runs after a press that moved focus to another row. `scroll: false`
// holds the page still for a list read off what is in view, such as the Page Map's
// visible markers, where scrolling to the landed row would change the list the walk
// is over. Tabs and spatial grids own cyclic policies; the page's queue walk steps by
// document position.
const STEPS = Object.freeze(["previous", "next", "first", "last"]);
const capital = (word) => word[0].toUpperCase() + word.slice(1);
export function rowWalk({
  id,
  noun,
  plural,
  rows,
  position = () => listWalkPosition(rows(), focused()),
  steps = STEPS,
  landed,
  scroll = true,
}) {
  const [up, down, home, end] = steps;
  const route = (binding, step) => ({
    id: `${id}.${step}`,
    binding,
    title: `${capital(step)} ${noun.toLowerCase()}`,
  });
  const land = (pick) => {
    const was = focused();
    const row = pick(rows());
    if (!row) return;
    focusDestination(row, "move");
    if (scroll) scrollIntoView(row, { block: "nearest" });
    beginWalk(id, noun, position);
    if (row !== was) landed?.(row);
  };
  return [
    {
      id: `${id}.walk`,
      keys: ["ArrowUp", "ArrowDown"],
      routes: [route("ArrowUp", up), route("ArrowDown", down)],
      title: `walk the ${plural}`,
      repeat: true,
      run: (binding) =>
        land((list) =>
          clampedRow(list, focused(), binding === "ArrowDown" ? 1 : -1, 0),
        ),
    },
    {
      id: `${id}.edge`,
      keys: ["Home", "End"],
      routes: [route("Home", home), route("End", end)],
      title: `${home} / ${end}`,
      // Home and End answer as they do in any list, so the shortcut bar spends its
      // slots on the walk and on what the list offers that no other list does; the
      // command reference and `aria-keyshortcuts` still name them.
      lineWhen: false,
      run: (binding) => land((list) => (binding === "Home" ? list[0] : list.at(-1))),
    },
  ];
}

// A keyboard walk has arrived. The caller still owns and announces the motion; this
// records the owner's live reading so every such walk gets one boundary treatment.
// `wrapped` is a cyclic walk's word that this step came round an end.
export function beginWalk(key, noun, read, wrapped = false) {
  const position = read();
  if (!position) {
    clearTimeout(boundaryTimer);
    boundaryTimer = 0;
    walking = null;
    return null;
  }
  walkPositionLabel(noun, position.position, position.total, position.qualifier);
  const boundary =
    wrapped || (walking?.key === key && walking.target === position.target);
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
