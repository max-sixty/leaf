// Compiled from walk-position.ts by build/typescript.mjs; edit that file.
/* Where a keyboard walk stands, what Leaf's panel says of it, and the walk over a flat
   list of focusable rows (`rowWalk`). Walk owners keep their list and motion. Native
   focus traversal and gestures that rearrange state are not walks through a named list.

   The owner says facts, and the panel decides what to show: what one stop is (`noun`),
   where the walk stands, the stops that bound a list on screen (`list`), and, for a
   list of Leaf's own, the fact where the user stands whose list it walks (`about`), as
   a comparison's changes are the comparison's. Leaf's panel then says only what the
   screen doesn't, each surface by the words it already shows (`walkWords`), and a
   listener hears the whole position, which the owner announces, since a listener sees
   no list. The user asked for this over each owner choosing what the panel shows, which
   no owner could choose right where the panel's own words already named the list. A
   position names its list wherever it says one, a list on screen's included, "Tab 2 of
   14": the panel stands apart from the list, beside words of the page's own such as "1
   of 31 pages real", so a bare "2 of 14" doesn't say what it counts.

   A walk of Leaf's own gives a reader of its live position (`beginWalk`), which stays
   authoritative as its list changes, and a different current target retires it. So
   the walk stands where it landed after its step's moment, as On Me's ring and the
   place before an open thread's Reply show.

   A package widget's walk says each step's place with an `lf-walk` event (`WALK`,
   lib/widget-events.js) on the stop the step landed on, so a widget calls nothing of
   Leaf's and a page without Leaf hears nothing. The event carries a place and no
   reader, so Leaf can't tell when a list that changed has made the place wrong. The
   place therefore stands for its step's moment alone (transport/notifications.js, `answerStep`),
   which is as long as the page's field says any step. So a widget's place before an
   open thread's Reply goes with the moment, where a walk of Leaf's own stands. Within
   the moment, the place ends as soon as the user is no longer at it:

   - when the user steps again;
   - when its stop leaves the page, as when a redraw replaces it;
   - when focus leaves the stop, once the stop or something inside it has held focus,
     as a tab holds it, and a diff's hunk;
   - when the widget says the user has left the stop without stepping, with an
     `lf-walk` on the same stop that carries no place. A chart's points take no focus,
     so only the chart knows that its pointer has taken the reader to another point.

   Each of these ends the place sooner, and none keeps it past the moment. Rejected:
   the place standing while focus stays on the stop. Leaf can't tell when the list has
   changed under a place, and a chart keeps focus while its reading moves, so such a
   place could stand wrong for as long as the user stayed. The moment bounds it. */
import { effect, untracked } from "/vendor/signals-core.js";
import { capitalized } from "../lib/words.js";
import { watchOwner } from "../dom/arrivals.js";
import { alreadyShown, scrollIntoView } from "../readings/landing-scroll.js";
import { clampedRow } from "../dom/keyboard/bindings.js";
import { answerStep, answeringStep, gesture } from "../transport/notifications.js";
import { afterScript } from "../base/rendering.js";
import { repaint } from "../dom/repaint.js";
import {
  currentLocationIn,
  focusDestination,
  focused,
  onCurrentLocation,
} from "../dom/focus.js";
import { renderedUnder } from "../lib/shadow-tree.js";
import { WALK } from "../lib/widget-events.js";

let walking = null;

// "Thread 2 of 5"; for a walk over several kinds, which names its list in the
// qualifier, "2 of 5 waiting on me".
export function walkPositionLabel(noun, position, total, qualifier = "") {
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
    about: walking.about,
  };
}

// The place a widget's latest step said (the `WALK` listener), while it stands: the
// stop it was said on, whether the user's focus has been on that stop or inside it
// since, and what stops the watch on the stop.
let said = null;
function endSaid() {
  const ended = said;
  if (!ended) return;
  said = null;
  ended.unwatch();
  if (walking !== ended.walk) return;
  walking = null;
  repaint();
}

// A step's walk takes the panel's seat for a notice's moment (transport/notifications.js,
// `answerStep`), and the panel's leaf answers the step, one landing where the last did
// included. Reading the same walk on an ordinary repaint does neither again. A step
// within a list standing whole in view (`ends`, its first and last stops) is declined:
// the ring shows its place among stops the user sees, so the seat would only repeat it,
// and the walk the user came by, such as On Me's, goes on standing. A place a widget
// said doesn't: it was the last step's, which this step has left. Whole is measured
// at the step, before a landing that scrolls, so a list running past the window's edge
// says its place even where the landing brings the rest into view, and by each end's
// own box, since whether the user sees it doesn't hang on the room its ring would take.
function stepTo(walk, ends) {
  endSaid();
  if (ends?.length && ends.every((end) => end && alreadyShown(end, { ringed: false })))
    return;
  walking = walk;
  answerStep();
  gesture("walk");
  repaint();
}

// A keyboard walk of Leaf's own has arrived. The caller still owns and announces the
// motion; this records the owner's live reading so every such walk says its position
// the same way, and returns the whole position for the owner's announcement, "Change 2
// of 5 since v2". `noun` names one stop, or is null for a list of several kinds, which
// the reading's qualifier names, as "2 of 5 waiting on me" does; such a walk never
// names the kind of the stop the user stands on, which is in front of them. A walk
// within a list on screen, such as a list's rows, gives `list`, its first and last
// stops, so a step within a list standing whole in view is declined (`stepTo`); a list
// whose stops all stand in view whenever it can be walked, as Go-to's hints do,
// declares no walk. `about` names the fact where the user stands whose list the walk
// is over (panel/floating-panel.js, `standing`), as "comparison" does for its changes.
export function beginWalk(key, noun, read, { list = null, about = null } = {}) {
  const position = read();
  if (!position) {
    walking = null;
    return null;
  }
  stepTo({ key, noun, read, about, target: position.target }, list?.());
  return walkPositionLabel(noun, position.position, position.total, position.qualifier);
}

// A widget's step says where it landed, on the stop it landed on. The place has no
// reader to retire it, so what ends it is the header's list. A widget that says the user
// has left some other stop ends nothing, since the place it speaks of has already gone.
addEventListener(WALK, (event) => {
  const [stop] = event.composedPath();
  if (!(stop instanceof Element)) return;
  if (!event.detail) {
    if (said?.stop === stop) endSaid();
    return;
  }
  const { noun, position, total, list } = event.detail;
  const place = { target: stop, position, total, qualifier: "" };
  const walk = { key: "said", noun, read: () => place, about: null, target: stop };
  stepTo(walk, list);
  if (walking === walk)
    said = {
      walk,
      stop,
      held: currentLocationIn(stop),
      unwatch: watchOwner(stop, { disconnect: endSaid }),
    };
});
// Focus leaving a stop that has held it is the user leaving the place said there. A
// widget may say its place before it moves focus to the stop, so the stop counts as
// holding focus from whenever focus reaches it. A stop that never holds focus, as a
// chart's drawing never does, is its widget's to end. A drop is a change taking the
// focused node away, not the user leaving it, so it ends nothing here. A stop the
// change removed ends its place through the watch on the stop.
onCurrentLocation((node, cause) => {
  if (!said || cause === "drop") return;
  if (renderedUnder(node, said.stop)) said.held = true;
  else if (said.held) endSaid();
});
effect(() => {
  if (!answeringStep()) untracked(endSaid);
});

// What a surface of the panel says of a walk's step, which the walk's owner declared
// (`beginWalk`): its place alone where the surface's own words say the fact the list
// is about (`says`), as the page field's "5 changes since v2 · 1 of 5" does, and else
// the whole position, "Thread 2 of 5", "Tab 2 of 14", since the panel stands apart from
// the list it counts.
export const walkWords = (walk, says) =>
  walk.about !== null && says.has(walk.about) ? walk.place : walk.text;

// The walk over a flat list of focusable rows, declared once for every list that has
// one: ArrowUp and ArrowDown step and clamp, Home and End land on the ends, and a
// landing reports its position. It returns the two register rows, `<id>.walk` and
// `<id>.edge`, for the owner's own scope; `id` is also the walk's position key and the
// prefix of each route, and `noun` names its steps ("Next entry"). `steps` names the
// four routes and their words, in the order ArrowUp, ArrowDown, Home, End, for a list
// whose ends have a meaning of their own. The rows are a list on screen, which its
// first and last rows bound (`beginWalk`), so a landing shows its position, "Entry 3 of
// 14", or nothing where the whole list stands in view. `position` reads where a landing
// stands, by default its place among the rows. A list passes its own where the items
// it counts are narrower than the stops the walk lands on, as a fold's door between
// items is a stop and not an item, or where another walk over the same items already
// reports their position, so both say the same. A reader returns null for a landing it
// counts no item at, which shows no position and ends any walk standing, as a list in
// the panel's own view does, whose rows name their places to a screen reader
// themselves.
// `landed(row)` runs after a press that moved focus to another row. `scroll: false`
// holds the page still for a list read off what is in view, such as the margin's
// visible markers, where scrolling to the landed row would change the list the walk
// is over. A walk that comes round at its ends steps with `cycledRow`
// (dom/keyboard/bindings.js); the page's queue walk steps by document position.
const STEPS = Object.freeze(["previous", "next", "first", "last"]);
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
  const route = (binding, step) => ({
    id: `${id}.${step}`,
    binding,
    title: `${capitalized(step)} ${noun.toLowerCase()}`,
  });
  const land = (pick) => {
    const was = focused();
    const row = pick(rows());
    if (!row) return;
    focusDestination(row, "move");
    // After the focus paint this move queued, since a landing measures the box wearing
    // the row's ring, which that paint marks (dom/focus.js, `ringBox`).
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
      runKey: (binding) =>
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
      runKey: (binding) => land((list) => (binding === "Home" ? list[0] : list.at(-1))),
    },
  ];
}
