// Compiled from user-place.ts by build/typescript.mjs; edit that file.
/* Where the user is in what scrolls, and the one hold that keeps them there across a
   change.

   The browser's scroll anchoring keeps the reader's place through every re-render: it
   picks a node on screen before the change, the first box the scroller shows in
   document order in both Chromium and Firefox, and after the change scrolls by however
   far content above that node moved it. Leaf adds no anchoring of its own to a render,
   and turns the browser's off only on a box that must not be its anchor, as the aside
   before a sidebar page's body (layouts.css), or on a box while a motion carries it,
   since Firefox anchors on where a box is drawn (dom/box-motion.js, lf-dial.js). A render
   helps it by keeping the nodes it doesn't change, since a
   node it replaces is an anchor lost: neither engine anchors again, so whatever grew
   above moves the reader by its full height (dom/dom-children.js, `setRenderedChildren`,
   for a message's words; a module's `lfPatch` for a widget a revision edits inside). A
   revision restores the reader's landmark after anchoring as well (features/version.js), which
   also returns them where a patch moved what they read between scrollers or into a
   closed disclosure.

   Anchoring can't hold three places the user relies on, and one hold keeps each,
   once, after the change has drawn:
   - a control under the user's hands below growth on screen, as an agent's turn
     arriving just above the reply box they type in, or an action joining Page Map
     just above the row they are on, which anchoring keeps still only where its anchor
     stands below the growth: a reading from outside the tab keeps it
     (`holdUserPlace`, below);
   - for a reader whose focus is scrolled away, the reading line, a quarter of the way
     down the window the page shows, where growth starts below the box anchoring holds
     and above the line, as an edit growing the first paragraph of the message whose
     second the user reads, with the reply box they wrote in scrolled away
     (`holdUserPlace`, `readingAt`);
   - a place the change hides, as Skim folds the paragraph being read, where the node
     standing for it takes its place: the paragraph's top, or the words read where
     the paragraph began above the window (`holdPlace`, which a module takes around
     such a change, as lf-dial.js does).
   A reader who focused nothing is anchoring's to keep, by the first block in view.
   Rejected: holding the reading line for every reader, which kept a diff's line still
   as five rows joined above it but moved what it left alone: words
   above the line went out of view where anchoring kept them in it, and a drag
   selecting them ran on through the rows that joined; a pointer resting over a second
   column made that column's line the place and moved the first column's words; and a
   press inside an embedded frame, which the page hears nothing
   of, left the keep to move what it opened.
   `holdPlaceOf(node)` reads where `node` stands and returns the step that, once the
   change has drawn, scrolls it back there; `holdPlace(column, standIn)` does so for
   what stands at the reading line, or for what `standIn` names once the change hid,
   removed or rewrote it. The change itself scrolls nothing. A forced layout
   applies anchoring's correction first, so the hold pays only for what anchoring left.
   Each ends with its step, and a hold kept across tasks, as a reading's is, keeps
   nothing once a scroll was chosen since. Rejected: the hold inside every surface's
   focus hold, which had to guess whether each re-render answered the user's own input
   and whether each box followed its scroller's flow, and guessed wrong for a widget's
   own landing in a shadow tree and for Send in its editor. Rejected: one hold a
   module takes for the user's focus and their place both. A redraw holds focus once
   for each node it replaces and leaves the reader to anchoring, and a fold holds the
   place once. Around a diff's redraw, for a reader who focused nothing, the one hold
   kept the line at the reading line still as rows joined above it, which moved a
   line read higher in the window up by those rows, and it read layout once for
   every row whose control the redraw swapped. A
   revision takes no hold: after its landmark restore, the hold put back what it read
   where it stood and undid the restore, and before it, the restore undid the hold.

   The user chose this over a keeper wrapped around every re-render,
   accepting that a re-render that replaces the very element they read can move them
   by what grew above it. Rejected: that keeper, which recorded every item on screen
   under the identity it was rendered with, handed the place to a replacement drawn
   under the same identity, preferred the item under the pointer or focus, and turned
   anchoring off while it held a change spanning tasks, which three surfaces wrapped
   every render in, for a 400-line module and its corrections of the browser's own.

   The module also owns the one rule for where the user is: focus while they can see it
   where the glides under way leave it (`focusPlace`), else what is on screen
   (reading-place.js, `pageReadingBlock`). A key pressed while focus is not where they
   are lets go of it first (panel/page-keys/controller.js), so every key acts from what they
   see, and a revision reading where they are asks the same (reading-place.js,
   `capturePlace`; features/version.js). */
import {
  clippedPlace,
  inFront,
  layoutWindow,
  placeHolder,
  seenRect,
  showsContents,
  shownWindow,
  stuckBox,
  whenChanges,
} from "../dom/geometry.js";
import {
  chosenSince,
  pageScroller,
  placeKept,
  scrollChoices,
} from "../dom/scrolling.js";
import {
  carriersOf,
  edgeAt,
  returnTo,
  scrollersOf,
  seenAhead,
} from "./scroll-containers.js";
import { hostIn, isText, renderedParent, under, upFrom } from "../lib/shadow-tree.js";
import { inChrome } from "../base/ui-marks.js";
import { userCaret } from "../dom/native-selection.js";
import {
  declareFocusPlace,
  focused,
  onUserInput,
  recentPlaceInput,
  typesText,
} from "../dom/focus.js";
import { PRESSES } from "../dom/control-selectors.js";
import { CARRY } from "../dom/box-motion.js";
import { browserScrolls } from "../dom/arrivals.js";
import { pointerAt } from "../base/pointer.js";
import { repaint } from "../dom/repaint.js";

// The box a control stands at, where a rule names one: a thread where its reply box
// waits, a hidden stand-in where what it stands for is (features/details-shelf.js), or the On Me
// card the `m` walk rings for the stop it reached (panel/floating-panel.js). The first rule
// matching the node that names a box decides.
const standing = [];
export function standsAt(selector, at) {
  standing.push([selector, at]);
}
const boxStoodAt = (node) => {
  for (const [selector, at] of standing) {
    const box = node.matches(selector) ? at(node) : null;
    if (box) return box;
  }
  return null;
};

// The focused node while it is where the user is: while any of it, or the box it stands
// at (`standsAt`), is in front of them where the glides under way leave it
// (scroll-containers.js, `seenAhead`), or while a slide under way is still carrying
// them to it, as a key a board's card moves on is meant for the card while it slides
// from where it stood, clipped meanwhile by a board that shrank. A key pressed while a
// glide runs acts as though the glide had landed, as a step pressed then steps from
// where the glide is headed (panel/navigation.js). A walk focuses its stop before gliding
// there, so a key pressed on the way is meant for the stop. `g g` carries a control
// mid-page away, so `c` or Tab pressed as it sets off lets go of the control though it
// is still on screen, and acts from where `g g` lands (reading-place.js,
// `landingPlace`). The user chose this, as the one rule for every key
// pressed during a glide, which tests/journeys/navigation/test_reading_place.py holds
// each glide and key to. A key whose work goes to a reader that can't ask where the
// glides land, the browser's answer to Tab or PageDown or a placement, lands them first
// (dom/scrolling.js, `landGlides`). Rejected: judging a node still on
// screen as the place, which opened a comment box on the control and let the glide
// carry it off screen with focus in it, and moved Tab on from the control as though
// the glide had not run; and counting every glide that carries focus, which took the
// page back down to comment on the control. A user who scrolled away from the control they stand on is reading
// something else, though the control keeps focus, so a key they press there lets go of
// it first, and scrolling back to it doesn't make it theirs again until they click or
// Tab there: the user chose this. A control in a stuck box, as the floating
// panel's row is, is in front of them, so a key acts there, though it rides along with
// every scroll, a glide's too, and marks no place in what it stands over (dom/geometry.js,
// `stuckBox`). Its box is asked of what clips it out to that stuck box, then of the
// window and the chrome, since a sticky header reads as under the slot it stands in
// itself (`seenRect`, `headerInset`). The chrome is read where it comes to rest, as
// `seenAhead` reads it. A row
// scrolled out of a list of Leaf's own chrome, such as Threads, is still where they are
// while the list shows: its arrows move on from that row into view, so it is the list
// that must leave the screen. It reads the page as it stands, with no record of how
// focus got there.
export function focusPlace() {
  const node = focused();
  if (!node || node === document.body) return null;
  const box = boxStoodAt(node);
  if (box && seenAhead(box)) return node;
  const [list] = scrollersOf(node);
  const shown = list && list !== pageScroller && inChrome(list) ? list : node;
  if (seenAhead(shown) || slides(node)) return node;
  const stuck = stuckBox(node);
  const left =
    stuck &&
    clippedPlace(node, new Map(), undefined, renderedParent(stuck) ?? undefined);
  // The walk stops short of the window, and `inFront` cuts only its top and foot.
  return left &&
    left.left < layoutWindow().right &&
    left.right > 0 &&
    inFront(left, node, true)
    ? node
    : null;
}
declareFocusPlace(focusPlace);
// A scroll can take the control out of sight or bring it back, which changes where `c`
// goes and whether the comment box waits beside the control (annotations/composing/surface.js,
// `focusedPlace`, `restingTarget`), with no focus move to paint it. So the page is
// painted again in the frame where that changes, while the scroll still moves, as a
// trackpad's momentum carries the control back in.
whenChanges(focusPlace, () => repaint());
// Whether a finite animation moves a box holding `node`, as the slide a moved card makes
// from where it stood to where layout put it, or a floating box's part dom/box-motion.js
// carries from where it was drawn (`CARRY`), as the thread card's list travels from the
// passage a walk left to the one it reached, drawn below the window meanwhile. The
// sheen's endless one, a fade, a cut, one held paused and one on a box's pseudo-element
// bring the user nowhere.
const slides = (node) =>
  document.getAnimations().some((animation) => {
    const effect = animation.effect;
    return (
      animation.playState === "running" &&
      effect?.target != null &&
      !effect.pseudoElement &&
      effect.getComputedTiming().endTime !== Infinity &&
      effect
        .getKeyframes()
        .some((key) => "transform" in key || "translate" in key || CARRY in key) &&
      under(node, effect.target)
    );
  });

// How far down the window the page shows (dom/geometry.js, `shownWindow`) the reader is
// taken to read where nothing they hold marks their place.
const READING_LINE = 0.25;
export const readingLine = () => {
  const window = shownWindow();
  return window.top + (window.bottom - window.top) * READING_LINE;
};

// What stands at the reading line in the middle of `column`'s span across the window:
// a range over the letter of the words nearest the line, so a gap between two
// paragraphs names one of them, else the element drawn there. The words, not the block
// holding them: anchoring holds words inside a tall block that grows above them, and
// the block's top moves by what grew. Leaf's chrome over the line names nothing, and
// neither does a box stuck over the page, which rides along with every scroll
// (dom/geometry.js, `stuckBox`).
export function readingAt(column) {
  const window = shownWindow();
  const box = column.getBoundingClientRect();
  const left = Math.max(box.left, window.left);
  const right = Math.min(box.right, window.right);
  const line = readingLine();
  if (right <= left) return null;
  const x = (left + right) / 2;
  // The document answers for words in a shadow tree with their host, which can be a
  // tall block whose top moves by what grows above them, so each open tree under the
  // line is asked for its own, as anchoring reaches into them.
  const shadowRoots = [];
  let reading = document.elementFromPoint(x, line);
  while (reading?.shadowRoot) {
    shadowRoots.push(reading.shadowRoot);
    const inner = reading.shadowRoot.elementFromPoint(x, line);
    if (!inner || inner === reading) break;
    reading = inner;
  }
  const caret = document.caretPositionFromPoint(x, line, { shadowRoots });
  const text = caret?.offsetNode;
  if (caret && text instanceof Text && text.length) {
    const at = Math.min(caret.offset, text.length - 1);
    reading = document.createRange();
    reading.setStart(text, at);
    reading.setEnd(text, at + 1);
  }
  const holder = reading && placeHolder(reading);
  return holder && !inChrome(holder) && !stuckBox(holder) ? reading : null;
}

// Put `held`'s top at `top` (scroll-containers.js, `returnTo`), and say whether that
// moved anything.
function returnPlace(held, top) {
  const boxes = [...scrollersOf(placeHolder(held))].map((box) => ({
    box,
    was: box.scrollTop,
  }));
  returnTo(held, "top", top);
  const moved = boxes.filter(({ box, was }) => box.scrollTop !== was);
  // A place the reader had, not one they chose (dom/scrolling.js, `placeKept`).
  placeKept(...moved.map(({ box }) => box));
  return moved.length > 0;
}
// Whether a change left `box` in the page and drawn with what it holds. A node folded
// until found holds nothing, whether it is the folded block or a box inside it
// (dom/geometry.js, `showsContents`).
const stillDrawn = (box) => Boolean(box?.isConnected && showsContents(box));

// Whether the words a range was made over are still the ones it holds, and drawn:
// words a change rewrote left the range, which the browser moved to their parent, and
// words it hid have no box, though every box around them may still draw, as when the
// change hides an element that has no box of its own. An element holds no words to
// lose.
const keepsWords = (node) => {
  if (!(node instanceof Range)) return () => true;
  const words = node.startContainer;
  return () => node.startContainer === words && node.getClientRects().length > 0;
};

// Read where `node`, an element or words a range holds (`readingAt`), stands and
// return the step that, once a change has drawn, scrolls it back there. A node the
// change hid, removed or rewrote holds nothing. The step says whether it moved
// anything.
export function holdPlaceOf(node) {
  const holder = node && placeHolder(node);
  if (!node || !holder) return () => false;
  const kept = keepsWords(node);
  const top = edgeAt(node, "top");
  return () => (kept() && stillDrawn(holder) ? returnPlace(node, top) : false);
}

// The hold a module takes around a change of its own that hides what the reader reads,
// as a fold does. It reads what stands at the reading line in `column` (`readingAt`)
// and where each box drawn around it began, and its step puts those words back where
// they stood. Where the change hid, removed or rewrote them, `standIn` names the node
// that stands for them, as Skim's gist stands for the paragraph it folds. That node
// lands where the outermost box the change hid began, so a gist's first line stands
// where its paragraph's first line stood. A box that began above the window would take
// the stand-in out of sight with its top, so there the stand-in lands where the words
// stood, as it does for words rewritten in a box the change left drawn. Where `standIn`
// names nothing, the nearest box around the words that the change left drawn goes back
// where it began, as a disclosure the change closed over the words does, unless it
// began above the window: the change may have taken what lay between its top and the
// reader. `standIn` is asked of the element that held the words, or, for words a
// widget drew in its own tree, of what stands for them in `column`'s tree, the widget.
export function holdPlace(column, standIn) {
  const reading = readingAt(column);
  const holder = reading && placeHolder(reading);
  if (!reading || !holder) return () => false;
  const kept = keepsWords(reading);
  const read = edgeAt(reading, "top");
  const shown = shownWindow().top;
  const asked = hostIn(holder, column.getRootNode()) ?? holder;
  // A box with no box of its own, as one that is `display: contents`, began nowhere.
  const around = [];
  for (let box = holder; box; box = upFrom(box))
    if (stillDrawn(box)) around.push({ box, top: edgeAt(box, "top") });
  return () => {
    const left = around.findIndex(({ box }) => stillDrawn(box));
    if (left === 0 && kept()) return returnPlace(reading, read);
    // The outermost box the change hid, where it hid one, and the nearest it left.
    const hid = around[left - 1];
    const stays = around[left];
    const named = standIn?.(asked);
    if (named?.isConnected)
      return returnPlace(named, hid && hid.top >= shown ? hid.top : read);
    return stays && stays.top >= shown ? returnPlace(stays.box, stays.top) : false;
  };
}

// The user's place across a change that arrives from outside the tab, a reading the
// server took with the agent's news in it, taken once where that reading is applied and
// kept once the page shows it, every renderer and the data its widgets read included
// (host/state-application.js), or across a change a surface makes with no reading behind it,
// as a widget's own contribution joining Page Map once its work finishes
// (panel/page-map-dialog.js). The place is what the user last named: the control under a
// resting pointer, which rests on nothing once it has left the window (base/pointer.js), or
// the control holding focus, whichever input came last, and then the other (dom/focus.js,
// `recentPlaceInput`). A field the user types in comes first wherever the pointer
// rests, since typing may grow a field but never moves it (browser/AGENTS.md), and the
// pointer names a control a press acts on, never the page's background
// (dom/control-selectors.js, `PRESSES`). Either names a place while any of it is shown and
// it rides in a scroller, not stuck there, as a Page Map row or a message in a margin
// card's transcript does, and a search field in a dialog's fixed head does not. A
// container the user is on stands at the box a rule names for it (`standsAt`), as a
// thread they sent from waits at its reply box, unless the caret a click on its words
// left lies outside that box (`caretPlace`). A user whose focus is scrolled away
// reads something else, so what stands at the reading line in its column comes last
// (`readingAt`). The keep puts back the first of these the change moved, so a pointer
// resting on a rail of its own, which nothing here moves, leaves the reading line to be
// kept; a place the change left still keeps the scroller it rides in, so a later one
// there, below news that joined between them, moves nothing. An action joining above a
// place inside the window, past the first box anchoring holds, would push it down. Read
// after the whole presentation, a box Leaf positions, as Send in its editor or a diff
// line's Comment, stands where its own layout put it, and is kept like any other. A
// control the change replaced, or one focus left, has nothing to keep.
//
// The keep yields to any scroll since the reading in a box whose scroll moves the
// place, the page included for a place in a box Leaf anchors to its words
// (`carriersOf`): a scroll the user or a landing chose and ended (dom/scrolling.js,
// `chosenSince`), one the browser is still running, as a smooth scroll or a wheel's
// glide, or has yet to start for the reader's input (dom/arrivals.js, `browserScrolls`), so
// it never overrides a scroll under way. A scroll in another box leaves the place to be
// kept: a landing in another pane made the keep give up a focused control the change
// then moved. It yields
// to the user's own act since too, a press or a key anywhere but in the field held
// (dom/focus.js, `onUserInput`), whose result is its own to place: a disclosure the user
// opened while a diff waited on its syntax grammar moved 140px when the keep put the
// line read back. Words typed into the field held
// grow it where it stands, and leave it kept; focus leaving a place it named leaves
// nothing of that place to keep. The user's own gesture draws its result in its own task and
// places it there, so nothing here holds against it. Where the boxes scrolling the
// place can't take all of a move, as on a page shorter than its window, it moves by the
// rest.
//
// A limit: the keep waits for the whole presentation, so a presenter whose paint
// resolves frames after the reading arrived, as a diff waiting on a syntax grammar's
// download does, lets the frames between show the move before the keep puts it back,
// and a scroll the user's own act chooses in them, as typing keeps its caret in view,
// ends the keep.
// The box a named control stands for, where it names a place: shown, riding in a
// scroller and not stuck there. Null where it names none.
const placeOf = (node) => {
  if (!node || node === document.body) return null;
  const box = boxStoodAt(node);
  const place = box && seenRect(box, new Map()) ? box : node;
  if (!seenRect(place, new Map())) return null;
  const [scroller] = scrollersOf(place);
  return scroller && !stuckBox(place, scroller) ? place : null;
};
// The caret a click on a focused container's words left (`userCaret`), where it
// stands in their text outside the box the container stands at, else null. A message
// the user clicked in a thread is where they stand, though the thread waits at its reply
// box, and so is an age or a formula in the message, whose words a shadow root draws. A
// caret in the box, or in a field the user types in, is the box's or field's, since
// typing and a send rewrite the words there.
const caretWords = (node) => {
  const at = userCaret();
  const box = boxStoodAt(node);
  return at &&
    isText(at.node) &&
    at.node.length &&
    under(at.node, node) &&
    !(box && under(at.node, box))
    ? at
    : null;
};
// Where the user on `node` stands: on the words a click there left the caret in, else at
// the box `node` stands at, as a user on a thread, where a send leaves them, waits at its
// reply box, else on `node` itself.
export const standingAt = (node) =>
  caretWords(node)?.element ?? boxStoodAt(node) ?? node;
// The caret a click on a focused container's words leaves (`caretWords`), where it lies
// in what the container shows: the letter after it, which the keep holds as it holds
// words at the reading line, so the message stays as a message above it grows or an
// answer joins below it, and the box moves.
const caretPlace = (node) => {
  const caret = caretWords(node)?.letter;
  if (!caret) return null;
  const holder = placeHolder(caret);
  if (!holder || !seenRect(caret, new Map())) return null;
  const [scroller] = scrollersOf(holder);
  return scroller && !stuckBox(holder, scroller) ? caret : null;
};
// The element under a pointer resting over the window, where one does.
const pointed = () => {
  const { x, y } = pointerAt();
  const window = shownWindow();
  if (x < window.left || x > window.right || y < window.top || y > window.bottom)
    return null;
  return document.elementFromPoint(x, y)?.closest(PRESSES) ?? null;
};
export function holdUserPlace() {
  const node = focused();
  const pointer = pointed();
  const first = recentPlaceInput() === "pointer" && !typesText(node);
  const named = first ? [pointer, node] : [node, pointer];
  const field = typesText(node) ? node : null;
  const places = [];
  for (const candidate of named) {
    const place =
      (candidate === node && node && node !== document.body && !field
        ? caretPlace(node)
        : null) ?? placeOf(candidate);
    if (place && !places.some((each) => each.place === place))
      places.push({ place, focus: candidate === node });
  }
  if (node && node !== document.body && !places.some(({ focus }) => focus)) {
    const reading = readingAt(node);
    if (reading) places.push({ place: reading, focus: false });
  }
  if (!places.length) return () => {};
  const choices = scrollChoices();
  let acted = false;
  const unwatch = onUserInput((event) => {
    if (event.type === "pointerdown" || event.type === "touchstart") acted = true;
    else if (event.type === "keydown" && !(field && focused() === field)) acted = true;
  });
  const holds = places.map(({ place, focus }) => ({
    place,
    focus,
    hold: holdPlaceOf(place),
  }));
  return () => {
    unwatch();
    if (acted) return;
    const still = new Set();
    for (const { place, focus, hold } of holds) {
      const holder = placeHolder(place);
      const carriers = [...carriersOf(holder)];
      if (carriers.some((box) => browserScrolls(box) || chosenSince(box, choices)))
        return;
      const [scroller] = scrollersOf(holder);
      if ((focus && focused() !== node) || still.has(scroller)) continue;
      if (hold()) return;
      still.add(scroller);
    }
  };
}
