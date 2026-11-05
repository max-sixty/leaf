/* Where the user is in what scrolls, and the one hold that keeps them there across a
   change.

   The browser's scroll anchoring keeps the reader's place through every re-render: it
   picks a node on screen before the change, the first box the scroller shows in
   document order in both Chromium and Firefox, and after the change scrolls by however
   far content above that node moved it. Leaf adds no anchoring of its own to a render,
   and turns the browser's off only on a box that must not be its anchor, as the aside
   before a sidebar page's body (layouts.css), or on a box while a motion carries it,
   since Firefox anchors on where a box is drawn (box-motion.js, lf-dial.js). A render
   helps it by keeping the nodes it doesn't change, since a
   node it replaces is an anchor lost: neither engine anchors again, so whatever grew
   above moves the reader by its full height (dom-children.js, `setRenderedChildren`,
   for a message's words; `x-patch: members` for a widget a revision edits inside). A
   revision restores the reader's landmark after anchoring as well (version.js), which
   also returns them where a patch moved what they read between scrollers or into a
   closed disclosure.

   Anchoring can't hold three places the user relies on, and `holdPlace` holds them,
   once, after the change has drawn:
   - a control under the user's hands below growth on screen, as an agent's turn
     arriving just above the reply box they type in, or an action joining Page Map
     just above the row they are on, which anchoring keeps still only where its anchor
     stands below the growth: a reading from outside the tab keeps it
     (`holdUserPlace`, below);
   - the reading line, a quarter of the way down the window the page shows, where
     growth starts below the box anchoring holds and above the line, as an edit growing
     the first paragraph of the message whose second the user reads, with the reply box
     they wrote in scrolled away (`holdUserPlace`, `readingAt`);
   - a place the change hides, as Skim folds the paragraph being read, where the node
     standing for it takes its place (lf-dial.js).
   `holdPlace(node, standIn)` reads where `node` stands and returns the step that,
   once the change has drawn, scrolls it, or what `standIn(node)` names once the change
   hid or removed it, back there. The change itself scrolls nothing. A forced layout
   applies anchoring's correction first, so the hold pays only for what anchoring left.
   It ends with its step, and a hold kept across tasks, as a reading's is, keeps
   nothing once a scroll was chosen since. Rejected: the hold inside every surface's
   focus hold, which had to guess whether each re-render answered the user's own input
   and whether each box followed its scroller's flow, and guessed wrong for a widget's
   own landing in a shadow tree (87px) and for Send in its editor (132px). A revision
   takes no hold: after its landmark restore, the hold put back what it read where it
   stood and undid the restore (82px off a line the restore had kept), and before it,
   the restore undid the hold.

   The user chose this on 2026-11-04 over a keeper wrapped around every re-render,
   accepting that a re-render that replaces the very element they read can move them
   by what grew above it. Rejected: that keeper, which recorded every item on screen
   under the identity it was rendered with, handed the place to a replacement drawn
   under the same identity, preferred the item under the pointer or focus, and turned
   anchoring off while it held a change spanning tasks, which three surfaces wrapped
   every render in, for a 400-line module and its corrections of the browser's own.

   The module also owns when focus marks the user's place at all (`focusedInView`),
   and whether the user has scrolled away from the control focus stands on
   (`focusScrolledAway`), for the keys that act there. */
import { seenRect, showsContents, shownWindow, stuckBox } from "./geometry.js";
import { pageScroller, placeKept, scrollChoices } from "./scrolling.js";
import { edgeAt, returnTo, scrollersOf } from "./scroll-containers.js";
import { inChrome } from "./shadow-tree.js";
import { focused, inputCount, onCurrentLocation, recentPlaceInput } from "./focus.js";
import { browserScrolls, watchScrollEnds } from "./arrivals.js";
import { pointerAt } from "./pointer.js";

// The focused control while it marks where the user is: while any of it is in front of
// them (geometry.js, `seenRect`), and it is not riding in a stuck sticky box
// or fixed box (`stuckBox`), as the floating panel is. A user who scrolled away from
// the control they stand on is reading something else, though the control keeps focus,
// and a stuck tab strip, title or reply row, like the floating panel's row, stays in
// view over whatever they scroll to, so it names no place in what it holds. A reflow
// then holds, and a landing returns them to, what they see instead. A render holding
// the box they type in (`holdUserPlace`), a reading place
// (reading-place.js, `capturePlace`), and revision continuity (version.js), for the
// region the user is working and whether a replaced reply box is scrolled back into
// view, ask this. The Threads list's resize landing (thread/landing.js) asks a question
// of its own instead: whether the focused title stands wholly where a landing puts it.
export function focusedInView() {
  const node = focused();
  return node && seenRect(node, new Map()) && !stuckBox(node) ? node : null;
}

// Whether the user has scrolled away from the control focus stands on: a scroll has
// settled since focus arrived there, and none of the control is in front of them
// (geometry.js, `seenRect`), as when they read something else. Leaf's keys don't act at
// a control scrolled away (dispatch.js, `stack`). Only a settled scroll counts, since a
// walk focuses its stop before gliding there and a key pressed on the way is meant for
// the stop; the control is measured when asked, since what rides a scroll is placed
// again as it settles. Unlike `focusedInView`, a control in the chrome or a stuck box is
// not away: the user sees what a key there acts on, though it names no place in the page.
// Nor is a row the user scrolled out of a list of Leaf's own, such as Threads: the list
// still shows where they are, and its arrows move on from that row into view, so it is
// the list that must leave the screen.
let settledSinceArrival = false;
watchScrollEnds(() => {
  settledSinceArrival = true;
});
// A node the runtime replaced handing focus to its successor is the same place, and
// focus a change dropped to the body arrives nowhere until its owner hands it back.
onCurrentLocation((node, cause) => {
  if (cause !== "return" && cause !== "drop") settledSinceArrival = false;
});
export function focusScrolledAway() {
  if (!settledSinceArrival) return false;
  const node = focused();
  if (!node || node === document.body) return false;
  const [list] = scrollersOf(node);
  const place = list && list !== pageScroller && inChrome(list) ? list : node;
  return !seenRect(place, new Map());
}

// How far down the window the page shows (geometry.js, `shownWindow`) the reader is
// taken to read where nothing they hold marks their place.
const READING_LINE = 0.25;

// What stands at the reading line in the middle of `column`'s span across the window:
// the block holding the words nearest the line, so a gap between two paragraphs names
// one of them, else the element drawn there. A block, not the inline element the words
// stand in: an `em`'s box starts below its line's top by the line's leading, so a gist
// put where the em stood, as Skim's is, landed 2.6px under the line read. Leaf's
// chrome over the line names nothing, and neither does a box stuck over the page,
// which rides along with every scroll (geometry.js, `stuckBox`).
/** @param {Element} column */
export function readingAt(column) {
  const window = shownWindow();
  const box = column.getBoundingClientRect();
  const left = Math.max(box.left, window.left);
  const right = Math.min(box.right, window.right);
  const line = window.top + (window.bottom - window.top) * READING_LINE;
  if (right <= left) return null;
  const x = (left + right) / 2;
  const at = document.caretPositionFromPoint(x, line)?.offsetNode;
  // Words in a shadow tree answer for their host, as anything else under the line does.
  let node = at instanceof Text ? at.parentElement : document.elementFromPoint(x, line);
  while (
    node?.parentElement &&
    /^(inline|contents)$/.test(getComputedStyle(node).display)
  )
    node = node.parentElement;
  return node && !inChrome(node) && !stuckBox(node) ? node : null;
}

// Read where `node` stands and return the step that, once a change has drawn, scrolls
// it back there, or, where the change hid or removed it, the node `standIn(node)` names,
// as Skim's gist stands for the paragraph it folds. A node the change folded until
// found holds nothing, whether it is the folded block or words inside it
// (geometry.js, `showsContents`). The step says whether it moved anything.
/** @param {Element | null | undefined} node
 * @param {(node: Element) => Element | null | undefined} [standIn] */
export function holdPlace(node, standIn = () => null) {
  if (!node) return () => false;
  const top = edgeAt(node, "top");
  return () => {
    const drawn = node.isConnected && showsContents(node);
    const held = drawn ? node : standIn(node);
    if (!held?.isConnected) return false;
    const boxes = [...scrollersOf(held)].map((box) => ({ box, was: box.scrollTop }));
    returnTo(held, "top", top);
    const moved = boxes.filter(({ box, was }) => box.scrollTop !== was);
    // A place the reader had, not one they chose (scrolling.js, `placeKept`).
    placeKept(...moved.map(({ box }) => box));
    return moved.length > 0;
  };
}

// The user's place across a change that arrives from outside the tab, a reading the
// server took with the agent's news in it, taken once where that reading is applied and
// kept once the page shows it, every renderer and the data its widgets read included
// (state-application.js), or across a change a surface makes with no reading behind it,
// as a widget's own contribution joining Page Map once its work finishes
// (page-map-dialog.js). The place is what the user last named: the control under a
// resting pointer, which rests on nothing once it has left the window (pointer.js), or
// the control holding focus, whichever input came last, and then the other (focus.js,
// `recentPlaceInput`). Either names a place while any of it is shown and it rides in a
// scroller, not stuck there, as a Page Map row or a message in a margin card's
// transcript does, and a search field in a dialog's fixed head does not. A container
// the user is on stands at the box a rule names for it (`standsAt`), as a thread they
// sent from waits at its reply box. A user whose focus is scrolled away reads something
// else, so what stands at the reading line in its column comes last (`readingAt`). The
// keep puts back the first of these the change moved, so a pointer resting on a rail of
// its own, which nothing here moves, leaves the reading line to be kept; a place the
// change left still keeps the scroller it rides in, so a later one there, below news
// that joined between them, moves nothing. An action joining above a place inside the
// window, past the first box anchoring holds, would push it down. Read after the whole
// presentation, a box Leaf positions, as Send in its editor or a diff line's Comment,
// stands where its own layout put it, and is kept like any other. A control the change
// replaced, or one focus left, has nothing to keep.
//
// The keep yields to any scroll since the reading: a scroll the user or a landing chose
// and ended (scrolling.js, `scrollChoices`), one the browser is still running, as a
// smooth scroll or a wheel's glide (arrivals.js, `browserScrolls`), and any input
// (focus.js, `inputCount`), so it never overrides a scroll under way. The user's own
// gesture draws its result in its own task and places it there, so nothing here holds
// against it. Where the boxes scrolling the place can't take all of a move, as on a
// page shorter than its window, it moves by the rest.
//
// A limit, for presenters a page or package adds: the keep waits for the whole
// presentation, so one whose paint resolves frames after the reading arrived lets the
// frames between show the move before the keep puts it back. Leaf's own present a
// reading's change in the frame it arrives in, measured on 4 November 2026 for news in
// a thread, an edit, a reply with a code block or a diagram, and a diff's new data.
/** @type {[string, (node: Element) => Element | null][]} */
const standing = [];
/** @param {string} selector @param {(node: Element) => Element | null} at */
export function standsAt(selector, at) {
  standing.push([selector, at]);
}
// The box a named control stands for, where it names a place: shown, riding in a
// scroller and not stuck there. Null where it names none.
/** @param {Element | null | undefined} node @returns {Element | null} */
const placeOf = (node) => {
  if (!node || node === document.body) return null;
  const box = standing.find(([selector]) => node.matches(selector))?.[1](node);
  const place = box && seenRect(box, new Map()) ? box : node;
  if (!seenRect(place, new Map())) return null;
  const [scroller] = scrollersOf(place);
  return scroller && !stuckBox(place, scroller) ? place : null;
};
// The element under a pointer resting over the window, where one does.
const pointed = () => {
  const { x, y } = pointerAt();
  const window = shownWindow();
  if (x < window.left || x > window.right || y < window.top || y > window.bottom)
    return null;
  return document.elementFromPoint(x, y);
};
export function holdUserPlace() {
  const node = focused();
  const pointer = pointed();
  const named = recentPlaceInput() === "pointer" ? [pointer, node] : [node, pointer];
  /** @type {{place: Element, focus: boolean}[]} */
  const places = [];
  for (const candidate of named) {
    const place = placeOf(candidate);
    if (place && !places.some((each) => each.place === place))
      places.push({ place, focus: candidate === node });
  }
  if (node && node !== document.body && !places.some(({ focus }) => focus)) {
    const reading = readingAt(node);
    if (reading) places.push({ place: reading, focus: false });
  }
  if (!places.length) return () => {};
  const choices = scrollChoices();
  const inputs = inputCount();
  const holds = places.map(({ place, focus }) => ({
    place,
    focus,
    hold: holdPlace(place),
  }));
  return () => {
    if (scrollChoices() !== choices || inputCount() !== inputs) return;
    const still = new Set();
    for (const { place, focus, hold } of holds) {
      const boxes = [...scrollersOf(place)];
      if (boxes.some(browserScrolls)) return;
      if ((focus && focused() !== node) || still.has(boxes[0])) continue;
      if (hold()) return;
      still.add(boxes[0]);
    }
  };
}
