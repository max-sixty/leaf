/* Leaf's presentation of a declared keyboard walk, and the walk over a flat list
   of focusable rows (`rowWalk`). Walk owners keep their list and motion; the portable
   declaration holds their live position reader. Native focus traversal and gestures
   that rearrange state are not walks through a named list. */
import { capitalized } from "./lib/words.js";
import { alreadyShown, scrollIntoView } from "./landing-scroll.js";
import { clampedRow } from "./keyboard/bindings.js";
import { answerStep, gesture } from "./notifications.js";
import { afterScript } from "./rendering.js";
import { repaint } from "./repaint.js";
import { focusDestination, focused } from "./focus.js";

import { WALK, beginWalk, listWalkPosition } from "./walk-declaration.js";
export {
  beginWalk,
  listWalkPosition,
  walkPosition,
  walkPositionLabel,
} from "./walk-declaration.js";

// A gesture's new position takes the panel's seat for a notice's moment
// (notifications.js, `answerStep`), and the panel's leaf answers the step, one landing
// where the last did included. Reading the same declaration on an ordinary repaint does
// neither again. A step within a list standing whole in view is declined: the ring
// shows its place among stops the user sees, so the seat would only repeat it, and the
// walk the user came by goes on standing (walk-declaration.js, `beginWalk`). Whole is
// measured at the step, before a landing that scrolls, so a list running past the
// window's edge says its place even where the landing brings the rest into view, and
// by each end's own box, since whether the user sees it doesn't hang on the room its
// ring would take.
window.addEventListener(WALK, (event) => {
  /** @type {import("./walk-declaration.js").WalkFacts["list"]} */
  const declared = /** @type {CustomEvent} */ (event).detail;
  const list = declared?.();
  if (
    list?.length &&
    list.every((stop) => stop && alreadyShown(stop, { ringed: false }))
  )
    return event.preventDefault();
  answerStep();
  gesture("walk");
  repaint();
});

// What a surface of the panel says of a walk's step, which the walk's owner declared
// (walk-declaration.js, `beginWalk`): its place alone where the surface's own words say
// the fact the list is about (`says`), as the page field's "5 changes since v2 · 1 of 5"
// does, and else the whole position, "Thread 2 of 5", "Tab 2 of 14", since the panel
// stands apart from the list it counts.
/** @param {NonNullable<ReturnType<typeof import("./walk-declaration.js").walkPosition>>} walk
 * @param {ReadonlySet<string>} says */
export const walkWords = (walk, says) =>
  walk.about !== null && says.has(walk.about) ? walk.place : walk.text;

// The walk over a flat list of focusable rows, declared once for every list that has
// one: ArrowUp and ArrowDown step and clamp, Home and End land on the ends, and a
// landing reports its position. It returns the two register rows, `<id>.walk` and
// `<id>.edge`, for the owner's own scope; `id` is also the walk's position key and the
// prefix of each route, and `noun` names its steps ("Next entry"). `steps` names the
// four routes and their words, in the order ArrowUp, ArrowDown, Home, End, for a list
// whose ends have a meaning of their own. The rows are a list on screen, which its
// first and last rows bound (walk-declaration.js, `beginWalk`), so a landing shows its
// position, "Entry 3 of 14", or nothing where the whole list stands in view. `position`
// reads where a landing stands, by default its place among the rows. A list passes
// its own where the items it counts are narrower than the stops the walk lands on, as
// a fold's door between items is a stop and not an item, or where another walk over
// the same items already reports their position, so both say the same. A reader
// returns null for a landing it counts no item at, which shows no position and ends
// any walk standing, as a list in the panel's own view does, whose rows name their
// places to a screen reader themselves.
// `landed(row)` runs after a press that moved focus to another row. `scroll: false`
// holds the page still for a list read off what is in view, such as the margin's
// visible markers, where scrolling to the landed row would change the list the walk
// is over. A walk that comes round at its ends steps with `cycledRow`
// (keyboard/bindings.js); the page's queue walk steps by document position.
/** @type {readonly [string, string, string, string]} */
const STEPS = Object.freeze(["previous", "next", "first", "last"]);
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
  const ends = () => {
    const all = rows();
    return [all[0], all.at(-1)];
  };
  /** @param {string} binding @param {string} step */
  const route = (binding, step) => ({
    id: `${id}.${step}`,
    binding,
    title: `${capitalized(step)} ${noun.toLowerCase()}`,
  });
  /** @param {(rows: HTMLElement[]) => HTMLElement | undefined} pick */
  const land = (pick) => {
    const was = focused();
    const row = pick(rows());
    if (!row) return;
    focusDestination(row, "move");
    // After the focus paint this move queued, since a landing measures the box wearing
    // the row's ring, which that paint marks (focus.js, `ringBox`).
    if (scroll) afterScript(() => scrollIntoView(row, { block: "nearest" }));
    beginWalk(id, noun, position, { list: ends });
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
