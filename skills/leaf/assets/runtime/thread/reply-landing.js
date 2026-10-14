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
   tall to show, landed as a whole, lands its reply row where one fits, and otherwise
   stays where it is while it is already shown (`landing-scroll.js`, `alreadyShown`):
   the nearest edge of a box taller than its room is a jump to its top.

   A send keeps the box it was sent from where the user saw it, the turn it adds drawn
   just above, even once the user stands outside the box; a box out of view lands the
   turn around it. A box growing under the user's keystrokes keeps its controls in
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
import { seenRect, stuckBox, userScrollport } from "../geometry.js";
import { focused } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { scrollerFor, scrollersOf } from "../reading-regions.js";
import { under } from "../shadow.js";
import { bringBackSurfaceOf } from "../off-flow.js";
import { retainUserIntent } from "../user-intent.js";
import { focusedInView } from "../user-place.js";
import {
  alreadyShown,
  fitsWhole,
  scrollIntoReadingBand,
  scrollIntoView,
} from "../landing-scroll.js";
import { aimedTop, atScrollEnd, moveScrollerBy, scrollToEnd } from "../scrolling.js";
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
// in the transcript is the thread's end. Pinned is the row itself stuck, which includes
// the row standing on its foot line at the thread's very end (geometry.js, `stuckBox`).
export const replyPinned = (reply) => Boolean(reply) && stuckBox(reply) === reply;
// The common transcript is a separate reading region only when its container bounds it.
// This asks the transcript the test `readingPosture` asks a region's body rather than
// asking `readingPosture`: the transcript is a registered region only in a floating
// card, and elsewhere that reading would answer for the threads list around it.
const separateTranscript = (held) => {
  const transcript = held.querySelector(":scope > .lf-thread-transcript");
  return transcript && userScrollport(getComputedStyle(transcript).overflowY)
    ? transcript
    : null;
};

// Keep a whole thread in view when it fits. A long thread reveals its reply
// area, including Send and Resolve; an oversized editor reveals only its control.
// scrollIntoView(nearest) on a card spanning both edges otherwise moves nothing, and
// so does one aimed at a pinned reply row, so a long thread with one lands its end.
export const landingTarget = (held, control) => {
  if (fitsWhole(held)) return { node: held };
  const reply = replyRowOf(held, control);
  // The thread itself, landed as a whole, is not a way into its pinned reply.
  if (replyPinned(reply))
    return control === held ? { node: null } : { node: held, block: "end" };
  if (reply && fitsWhole(reply)) return { node: reply };
  if (control === held && alreadyShown(held)) return { node: null };
  return { node: control };
};

// The turn a user comes back to a thread for: its latest message, or the summary
// standing for earlier ones.
// Whether the user has scrolled a reply row away: none of it in front of them
// (geometry.js, `seenRect`).
const onScreen = (node) => seenRect(node, new Map()) !== null;

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

function landThread(held, control, behavior, block) {
  bringBackSurfaceOf(held, behavior);
  const transcript = separateTranscript(held);
  if (transcript && control !== held && replyRowOf(held, control)) {
    scrollToEnd(transcript, behavior);
    return;
  }
  if (transcript?.contains(control)) {
    scrollIntoView(control, { behavior, block });
    return;
  }
  const target = landingTarget(held, control);
  scrollIntoView(target.node, { behavior, block: target.block ?? block });
}

// A geometry owner can fit a thread after its landing has already scrolled. Keep the
// destination through those fits under the original gesture's authority: focus alone
// cannot authorize moving a reader who has since scrolled elsewhere. Weak ownership
// follows the thread's node lifetime, and a replay never captures fresh user intent.
const landings = new WeakMap();
export function keepThreadLanding(held) {
  const landing = landings.get(held);
  if (!landing) return;
  if (!landing.mayLand()) {
    landings.delete(held);
    return;
  }
  landThread(held, landing.control, "instant", landing.block);
}

export function scrollThreadIntoView(
  held,
  control,
  behavior = scrollBehavior(),
  block = "nearest",
) {
  const mayLand = retainUserIntent({
    available: () => held.isConnected && control.isConnected && under(control, held),
  });
  landings.set(held, { control, block, mayLand });
  landThread(held, control, behavior, block);
}

// Taken as the user sends, before the send draws anything; the step it returns is taken
// once the send has left the user `standing`: on the conversation's card or title
// (`landSent`), or on the seat holding a persistent box. The box the user sent from is
// under their aim, so one they saw whole stays where it stood with its new turn drawn
// above it, as a render holds the box they type in (`holdBox`). Rejected: landing the
// thread there, which aimed at the thread's foot while it fitted and at the row's once it
// did not, so the box stepped by the line between them. A row pinned to its scroller's
// foot, or below a separate transcript, stands still by itself and its turn lands at
// the transcript's end; a box out of view lands the thread around it. Nothing lands once
// a newer gesture has taken the user away from `standing`, and a box the send removed
// has handed the user on already.
// The sent turn lands without animation: fitting can change the transcript's room in
// the next update, and an in-flight pixel destination would outlive the room it named.
// The geometry owner then preserves the landed end while it fits that room.
export function sendLanding(input) {
  const held = input.closest(SAYS_IN);
  if (!held) return () => {};
  const reply = replyRowOf(held, input);
  const stood =
    reply && !replyPinned(reply) && !separateTranscript(held) && alreadyShown(reply)
      ? standingTop(reply)
      : null;
  return (standing = held) => {
    const mayLand = retainUserIntent({
      source: standing,
      available: () => held.isConnected,
    });
    void whenDocumentPresented()
      .then(() => {
        if (!mayLand() || !input.isConnected) return;
        if (stood !== null && held.contains(reply)) returnTo(reply, stood);
        else scrollThreadIntoView(held, input, "instant");
      })
      .catch(() => {});
  };
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
// earlier turns back into view on the first keystroke in an already-visible reply. It
// follows the area's foot into the band rather than asking whether the area is already
// shown (landing-scroll.js, `alreadyShown`): a row seen whole but growing into the
// band's clearance moves with each keystroke, where waiting until it passed under the
// chrome would jump it by a line and the clearance at once.
const revealWritingArea = (held, input, reply) => {
  bringBackSurfaceOf(held, "instant");
  const target = reply && fitsWhole(reply) ? reply : input;
  scrollIntoReadingBand(target, target, "nearest", "instant");
};
// A rewrite opening in its message shows the message whole, its head with Cancel and
// Save above the words, where the band holds it, and otherwise the line its caret stands
// on, where the next key types. A reply row pinned at the scroller's foot covers what
// stands behind it, so the box's foot clears it too.
export function revealEditor(message, caretLine) {
  const held = message.closest(SAYS_IN);
  if (!held) return;
  bringBackSurfaceOf(held, "instant");
  const target = fitsWhole(message) ? message : caretLine;
  scrollIntoReadingBand(target, target, "nearest", "instant");
  const reply = replyRowOf(held, held);
  if (!replyPinned(reply)) return;
  const margin = parseFloat(getComputedStyle(message).scrollMarginBlockEnd) || 0;
  const over =
    target.getBoundingClientRect().bottom + margin - reply.getBoundingClientRect().top;
  if (over > 0) moveScrollerBy(scrollerFor(reply), over);
}
export function followBoxGrowth(input) {
  const held = input.closest(SAYS_IN);
  if (!held) return;
  const reply = replyRowOf(held, input);
  // A box standing in the transcript rather than its reply row, as a rewrite stands in
  // its message, keeps its caret in view itself: aimed at the whole box, a landing here
  // pulled a long one's top into view on every key.
  if (!reply) return;
  // A separate transcript gives up height rather than being covered by the editor.
  // A reader at its tail keeps the turn beside the growing box; someone reading back
  // keeps their own offset. The editor's before-edit reading precedes its layout.
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
// The editor's place before its own edit: a pinned row's height, or a separate
// transcript's tail and room. Arrival also reads its initial place.
export function readBoxPlace(input) {
  const held = input.closest(SAYS_IN);
  const reply = held && replyRowOf(held, input);
  // A box in the transcript has no row to hold nor a tail to keep beside it.
  if (!reply) return;
  // The edit may be the one that takes a natural row to its sticky floor.
  rowHeights.set(input, reply.getBoundingClientRect().height);
  const transcript = separateTranscript(held);
  if (transcript)
    transcriptPlaces.set(input, {
      transcript,
      height: transcript.clientHeight,
      atTail: atScrollEnd(transcript),
    });
}

// Where `node` stands on screen, read as though each box scrolling it stood where Leaf
// last aimed it (scrolling.js, `aimedTop`): a hold read after a hold then carries no
// rounding of the first, and a box held send after send keeps its pixel.
const standingTop = (node) => {
  let top = node.getBoundingClientRect().top;
  for (const box of scrollersOf(node)) top += box.scrollTop - aimedTop(box);
  return top;
};
// Put `node` back where it stood (`standingTop`). The box scrolling it takes the move
// first and the boxes around it whatever it cannot: a bounded block not yet full grows
// in the page instead.
function returnTo(node, top) {
  for (const box of scrollersOf(node)) {
    const moved = standingTop(node) - top;
    if (Math.abs(moved) < 0.5) return;
    moveScrollerBy(box, moved);
  }
}

// A render that inserts above the control the user stands on, such as an edit growing a
// turn above the box they are writing in, moves it by what it inserted; an agent's turn
// arriving there waits behind its thread's notice instead (held-news.js). `holdBox`
// reads where the focused control stands and returns the step that puts it back, so
// news moves no control under the user's hands. Only one in view is under their hands
// (user-place.js, `focusedInView`). A control the render replaced, or one that left the
// thread view it stood in, as a reply going on where its thread now stands does
// (replies.js, `releaseReplies`), has nothing to hold.
export function holdBox(control) {
  const held = control?.closest?.(SAYS_IN);
  if (!held || control !== focusedInView()) return () => {};
  const top = standingTop(control);
  return () => {
    if (focused() !== control || !control.isConnected || !held.contains(control))
      return;
    returnTo(control, top);
  };
}
