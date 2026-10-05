/* Where a thread lands in the scroller that shows it: the geometry every route into a
   thread shares, whichever surface draws it.

   A thread that fits lands whole. A longer one lands its reply area, Send and Resolve
   with it, or the focused control alone where the editor is too tall for both. A reply
   row pinned to its scroller's foot (the panel card's) reads as
   shown wherever the transcript stands, so a landing on it lands the thread's end
   instead. The margin card's reply stands outside its transcript scroll and a reply
   landing reveals that transcript's end directly. The row is not declared a cover of
   the transcript: the caret lives in it, and the browser's own
   caret reveal would scroll the transcript on every keystroke to clear it. A thread too
   tall to show, landed as a whole, lands its reply row where one fits, and
   otherwise stays where it is while any of it is on screen: the nearest edge of a box
   taller than the window is a jump to its top.

   A send lands the turn it adds, around the box it was sent from even once the user
   stands outside it, and a box growing under the user's keystrokes keeps its controls in
   the band and the words just above it beside it. Growth reveals the writing area
   alone; earlier turns the reader has passed stay out of view. Every box a thread or a
   seat holds answers both, whichever owner built it. The climbs cross shadow roots,
   since a widget may draw a thread inside its own tree and still be scrolled by the
   page, and the box that scrolls a thread is the reading region's (`scrollerFor`). A
   thread in a surface fixed over the page, the margin card, is shown by bringing that
   surface back first (`off-flow.js`). These landings serve thread navigation,
   sending, and editor growth. Merely entering a reply reveals its writing area
   instead (`landing.js`): a visible pinned row or a separate transcript keeps
   the turn the user was reading, even when it is not the latest one. A separate
   transcript opened for reading shows its latest turn (`showLatestTurn`). */
import { landingBand, seenRect, shownBox } from "../geometry.js";
import { focused } from "../keyboard/scopes.js";
import { scrollBehavior } from "../motion.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { scrollerFor, scrollersOf } from "../reading-regions.js";
import { renderedParent } from "../shadow.js";
import { bringBackSurfaceOf } from "../off-flow.js";
import { retainUserIntent } from "../user-intent.js";
import { scrollIntoReadingBand } from "../landing-scroll.js";
import { atScrollEnd, moveScrollerBy, scrollToEnd } from "../scrolling.js";
import { SAYS_IN, SAY_ROW } from "./selectors.js";

const replyRowOf = (held, control) => {
  const reply =
    control === held
      ? [...held.children].find((node) => node.matches(SAY_ROW))
      : control.closest(SAY_ROW);
  return reply?.parentElement === held ? reply : null;
};
// A reply row pinned to its scroller's foot (a panel card's) stands in the band
// while the thread's end lies below it, so aiming a scroll at it moves nothing: its place
// in the transcript is the thread's end.
export function replyPinned(reply) {
  if (!reply || getComputedStyle(reply).position !== "sticky") return false;
  const scroller = scrollerFor(reply);
  const floor =
    scroller.getBoundingClientRect().bottom -
    parseFloat(getComputedStyle(scroller).paddingBottom) -
    parseFloat(getComputedStyle(reply).bottom);
  return Math.abs(reply.getBoundingClientRect().bottom - floor) < 1;
}
// The common transcript is a separate reading region only when its container bounds it.
const separateTranscript = (held) => {
  const transcript = held.querySelector(":scope > .lf-thread-transcript");
  return transcript && /^(auto|scroll)$/.test(getComputedStyle(transcript).overflowY)
    ? transcript
    : null;
};

const ancestors = function* (node) {
  for (let parent = renderedParent(node); parent; parent = renderedParent(parent))
    yield parent;
};
const landingRoom = (held) => {
  let room = Infinity;
  for (const parent of ancestors(held)) {
    const band = landingBand(parent);
    if (band) room = Math.min(room, band.bottom - band.top);
  }
  return room;
};
// Whether any of the node is in front of the user (geometry.js, `seenRect`): a node in
// view inside a bounded block the page has scrolled away is not, and neither is one
// standing under the banner.
const onScreen = (node) => seenRect(node, new Map()) !== null;

export const fitsWhole = (held) => shownBox(held).height <= landingRoom(held);
// Keep a whole thread in view when it fits. A long thread reveals its reply
// area, including Send and Resolve; an oversized editor reveals only its control.
// scrollIntoView(nearest) on a card spanning both edges otherwise moves nothing, and
// so does one aimed at a pinned reply row, so a long thread with one lands its end.
export const landingTarget = (held, control) => {
  const room = landingRoom(held);
  if (shownBox(held).height <= room) return { node: held };
  const reply = replyRowOf(held, control);
  // The thread itself, landed as a whole, is not a way into its pinned reply.
  if (replyPinned(reply))
    return control === held ? { node: null } : { node: held, block: "end" };
  if (reply && shownBox(reply).height <= room) return { node: reply };
  if (control === held && onScreen(held)) return { node: null };
  return { node: control };
};

// The turn a user comes back to a thread for: its latest message, or the summary
// standing for earlier ones.
export const latestTurn = (transcript) =>
  [...transcript.querySelectorAll(":scope > :is(.lf-msg, .lf-thread-checkpoint)")].at(
    -1,
  ) ?? null;

// A separate transcript opened for reading shows its latest turn: the transcript's end,
// or that turn's head where it alone is taller than the transcript, as a long thread
// lands in the Threads list (landing.js, `threadLandingStart`). The turn carries its
// own head, so it is measured from the transcript's top.
export function showLatestTurn(transcript) {
  scrollToEnd(transcript);
  const latest = latestTurn(transcript);
  if (!latest) return;
  const over =
    transcript.getBoundingClientRect().top +
    transcript.clientTop -
    latest.getBoundingClientRect().top;
  if (over > 0) moveScrollerBy(transcript, -over);
}

export function scrollThreadIntoView(
  held,
  control,
  behavior = scrollBehavior(),
  block = "nearest",
) {
  bringBackSurfaceOf(held, behavior);
  const transcript = separateTranscript(held);
  if (transcript && control !== held && replyRowOf(held, control)) {
    scrollToEnd(transcript, behavior);
    return;
  }
  if (transcript?.contains(control)) {
    control.scrollIntoView({ behavior, block });
    return;
  }
  const target = landingTarget(held, control);
  target.node?.scrollIntoView({ behavior, block: target.block ?? block });
}

// Taken as the user sends: once the page has drawn the new turn above the box, land the
// thread around the box the user sent from, so the turn's end shows with the box, unless
// a newer gesture has taken the user away from `standing`. That is where the send left
// them: the thread or seat holding the box by default, or the page element a reply in
// the margin card hands them to (`landSent`). A box the send removed has handed the user
// on already.
// The sent turn lands without animation: fitting can change the transcript's room in
// the next update, and an in-flight pixel destination would outlive the room it named.
// The geometry owner then preserves the landed end while it fits that room.
export function sendLanding(input, standing = input.closest(SAYS_IN)) {
  const held = input.closest(SAYS_IN);
  if (!held) return () => {};
  const mayLand = retainUserIntent({
    source: standing,
    available: () => held.isConnected,
  });
  return () =>
    void whenDocumentPresented()
      .then(() => {
        if (mayLand() && input.isConnected)
          scrollThreadIntoView(held, input, "instant");
      })
      .catch(() => {});
}

// A box growing or shrinking under the user's own keystrokes keeps two things: its
// controls in the band, and the words just above it where they stood beside it. A row in
// flow grows downward, so the words above stay put and only its foot can leave the band,
// which the landing brings back. A pinned row keeps its foot and grows upward: into the
// room between it and the words above it first (the panel card's, standing at the list's
// foot), then over those words, so the transcript moves by the part of the growth that
// now covers them. A row that shrinks uncovers words and moves none. The cover is read now
// and the row's growth from its height, since only the user's words change a row's
// height: a scroll or a reply arriving between keystrokes moves the cover and must not be
// paid for.
const rowHeights = new WeakMap();
const transcriptPlaces = new WeakMap();
const covered = (reply) =>
  (reply.previousElementSibling?.getBoundingClientRect().bottom ?? -Infinity) -
  reply.getBoundingClientRect().top;
// Editing reveals only the writing area. Revealing the whole thread here would pull
// earlier turns back into view on the first keystroke in an already-visible reply.
const revealWritingArea = (held, input, reply) => {
  bringBackSurfaceOf(held, "instant");
  const target = reply && shownBox(reply).height <= landingRoom(held) ? reply : input;
  scrollIntoReadingBand(target, target, "nearest", "instant");
};
export function followBoxGrowth(input) {
  const held = input.closest(SAYS_IN);
  if (!held) return;
  const reply = replyRowOf(held, input);
  // A separate transcript gives up height rather than being covered by the editor.
  // A reader at its tail keeps the turn beside the growing box; someone reading back
  // keeps their own offset. The beforeinput reading precedes the editor's layout.
  const transcript = separateTranscript(held);
  if (transcript) {
    const place = transcriptPlaces.get(input);
    if (
      place?.transcript === transcript &&
      place.atTail &&
      transcript.clientHeight < place.height
    )
      scrollToEnd(transcript);
    transcriptPlaces.delete(input);
    if (!onScreen(reply)) revealWritingArea(held, input, reply);
    return;
  }
  if (!replyPinned(reply)) return revealWritingArea(held, input, reply);
  const height = reply.getBoundingClientRect().height;
  const grew = height - (rowHeights.get(input) ?? height);
  rowHeights.set(input, height);
  const by = Math.max(0, Math.min(grew, covered(reply)));
  if (by) scrollerFor(reply).scrollBy({ top: by, behavior: "instant" });
  // A row pins only at its scroller's foot, so one the user scrolled past is brought back.
  if (!onScreen(reply)) revealWritingArea(held, input, reply);
}
// The editor's place before its own edit, and on arrival for a first edit delivered
// without beforeinput: a pinned row's height, or a separate transcript's tail and room.
export function readBoxPlace(input) {
  const held = input.closest(SAYS_IN);
  const reply = held && replyRowOf(held, input);
  // The edit may be the one that takes a natural row to its sticky floor.
  if (reply) rowHeights.set(input, reply.getBoundingClientRect().height);
  const transcript = held && separateTranscript(held);
  if (transcript)
    transcriptPlaces.set(input, {
      transcript,
      height: transcript.clientHeight,
      atTail: atScrollEnd(transcript),
    });
}

// A render that inserts above the control the user stands on, such as an edit growing a
// turn above the box they are writing in, moves it by what it inserted; an agent's turn
// arriving there waits behind its thread's notice instead (held-news.js). `holdBox`
// reads where the focused control stands and returns the step that puts it back, so
// news moves no control under the user's hands. Only one on screen is under their hands: a user who
// has scrolled away from it is reading something else, which the news must not move. A
// pinned row stands still by itself, and a control the render replaced has nothing to
// hold. The box scrolling the control takes the move first and the boxes around it
// whatever it cannot: a bounded block not yet full grows in the page instead.
export function holdBox(control) {
  const held = control?.closest?.(SAYS_IN);
  if (!held || replyPinned(replyRowOf(held, control)) || !onScreen(control))
    return () => {};
  const top = control.getBoundingClientRect().top;
  return () => {
    if (focused() !== control || !control.isConnected) return;
    for (const box of scrollersOf(control)) {
      const moved = control.getBoundingClientRect().top - top;
      if (Math.abs(moved) < 1) return;
      box.scrollBy({ top: moved, behavior: "instant" });
    }
  };
}
