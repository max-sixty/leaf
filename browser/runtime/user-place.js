/* Where the user is in what scrolls, and the one hold that keeps them there across a
   change.

   The browser's scroll anchoring keeps the reader's place through every re-render: it
   picks a node on screen before the change, the first box the scroller shows in
   document order in both Chromium and Firefox, and after the change scrolls by however
   far content above that node moved it. Leaf adds no anchoring of its own to a render,
   and turns the browser's off only on a box that must not be its anchor, as the aside
   before a sidebar page's body (layouts.css), or while a motion carries a box's content
   (box-motion.js). A render helps it by keeping the nodes it doesn't change, since a
   node it replaces is an anchor lost: neither engine anchors again, so whatever grew
   above moves the reader by its full height (dom-children.js, `setRenderedChildren`,
   for a message's words; `x-patch: members` for a widget a revision edits inside). A
   revision restores the reader's landmark after anchoring as well (version.js), which
   also returns them where a patch moved what they read between scrollers or into a
   closed disclosure.

   Anchoring can't hold three places the user relies on, and `holdPlace` holds them,
   once, in the task that makes the change:
   - a control under the user's hands below growth on screen, as an agent's turn
     arriving just above the reply box they type in, which anchoring keeps still only
     where its anchor stands below the growth (reply-landing.js, `holdBox`);
   - the reading line, a quarter of the way down the window the page shows, where
     growth starts below the box anchoring holds and above the line, as an edit growing
     the first paragraph of the message whose second the user reads, with the reply box
     they wrote in scrolled away (`holdBox`, `readingAt`);
   - a place the change hides, as Skim folds the paragraph being read, where the node
     standing for it takes its place (lf-dial.js).
   `holdPlace(node, standIn)` reads where `node` stands and returns the step that,
   once the change has drawn, scrolls it, or what `standIn(node)` names once the change
   hid or removed it, back there. The change itself scrolls nothing. A forced layout
   applies anchoring's correction first, so the hold pays only for what anchoring left.
   It ends with its step, so a scroll the user makes after is never fought. A revision
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
import { seenRect, shownWindow, stuckBox } from "./geometry.js";
import { pageScroller, placeKept } from "./scrolling.js";
import { edgeAt, returnTo, scrollersOf } from "./scroll-containers.js";
import { inChrome } from "./shadow-tree.js";
import { focused, onCurrentLocation } from "./focus.js";
import { watchScrollEnds } from "./arrivals.js";

// The focused control while it marks where the user is: while any of it is in front of
// them (geometry.js, `seenRect`), and it is not riding in a stuck sticky box
// or fixed box (`stuckBox`), as the floating panel is. A user who scrolled away from
// the control they stand on is reading something else, though the control keeps focus,
// and a stuck tab strip, title or reply row, like the floating panel's row, stays in
// view over whatever they scroll to, so it names no place in what it holds. A reflow
// then holds, and a landing returns them to, what they see instead. A render holding
// the box they type in (reply-landing.js, `holdBox`), a reading place
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
// the element holding the words nearest the line, so a gap between two paragraphs
// names one of them, else the element drawn there. Leaf's chrome over the line names
// nothing, and neither does a box stuck over the page, which rides along with every
// scroll (geometry.js, `stuckBox`).
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
  const node =
    at instanceof Text ? at.parentElement : document.elementFromPoint(x, line);
  return node && !inChrome(node) && !stuckBox(node) ? node : null;
}

// Read where `node` stands and return the step that, once a change has drawn, scrolls
// it back there, or, where the change hid or removed it, the node `standIn(node)` names,
// as Skim's gist stands for the paragraph it folds. A node folded until found keeps a
// box of no height, which holds nothing.
/** @param {Element | null | undefined} node
 * @param {(node: Element) => Element | null | undefined} [standIn] */
export function holdPlace(node, standIn = () => null) {
  if (!node) return () => {};
  const top = edgeAt(node, "top");
  return () => {
    const drawn = node.isConnected && node.getBoundingClientRect().height > 0;
    const held = drawn ? node : standIn(node);
    if (!held?.isConnected) return;
    const boxes = [...scrollersOf(held)].map((box) => ({ box, was: box.scrollTop }));
    returnTo(held, "top", top);
    // A place the reader had, not one they chose (scrolling.js, `placeKept`).
    placeKept(
      ...boxes.filter(({ box, was }) => box.scrollTop !== was).map(({ box }) => box),
    );
  };
}
