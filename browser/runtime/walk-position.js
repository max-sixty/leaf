/* Leaf's presentation of a declared keyboard walk, and the walk over a flat list
   of focusable rows (`rowWalk`). Walk owners keep their list and motion; the portable
   declaration holds their live position reader. Native focus traversal and gestures
   that rearrange state are not walks through a named list. */
import { scrollIntoView } from "./landing-scroll.js";
import { clampedRow } from "./keyboard/bindings.js";
import { holdStatus } from "./notifications.js";
import { repaint } from "./repaint.js";
import { focusDestination, focused } from "./focus.js";

import { WALK, beginWalk, listWalkPosition } from "./walk-declaration.js";
export {
  beginWalk,
  listWalkPosition,
  walkPosition,
  walkPositionLabel,
} from "./walk-declaration.js";

// A gesture's new position holds the status line against arriving news. Reading the
// same declaration on an ordinary repaint does not restart that hold.
window.addEventListener(WALK, () => {
  holdStatus(900);
  repaint();
});

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
// is over. A walk that comes round at its ends steps with `cycledRow`
// (keyboard/bindings.js); the page's queue walk steps by document position.
/** @type {readonly [string, string, string, string]} */
const STEPS = Object.freeze(["previous", "next", "first", "last"]);
/** @param {string} word */
const capital = (word) => word.slice(0, 1).toUpperCase() + word.slice(1);
/** @param {{
 *   id: string,
 *   noun: string,
 *   plural: string,
 *   rows: () => HTMLElement[],
 *   position?: () => ReturnType<typeof listWalkPosition>,
 *   steps?: readonly [string, string, string, string],
 *   landed?: (row: HTMLElement) => void,
 *   scroll?: boolean,
 * }} walk */
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
  /** @param {string} binding @param {string} step */
  const route = (binding, step) => ({
    id: `${id}.${step}`,
    binding,
    title: `${capital(step)} ${noun.toLowerCase()}`,
  });
  /** @param {(rows: HTMLElement[]) => HTMLElement | undefined} pick */
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
      travels: scroll,
      runKey: /** @param {string} binding */ (binding) =>
        land((list) =>
          clampedRow(list, focused(), binding === "ArrowDown" ? 1 : -1, 0),
        ),
    },
    {
      id: `${id}.edge`,
      keys: ["Home", "End"],
      routes: [route("Home", home), route("End", end)],
      title: `${home} / ${end}`,
      travels: scroll,
      runKey: /** @param {string} binding */ (binding) =>
        land((list) => (binding === "Home" ? list[0] : list.at(-1))),
    },
  ];
}
