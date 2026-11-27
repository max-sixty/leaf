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
   stays where it is while any of it is in front of the user (dom/geometry.js, `seenRect`):
   the nearest edge of a box taller than its room is a jump to its top, which a landing
   that takes the user somewhere makes (`readings/landing-scroll.js`, `alreadyShown`) and one
   that follows them into a thread they see doesn't.

   A send moves the box it was sent from, once the user saw it, by no more than the turn
   it adds above it, and no lower than the line typing keeps it within, even once the
   user is outside the box; a box out of view lands the turn around it
   (`sendLanding`). A box growing under the user's keystrokes keeps its controls in
   the band and the words just above it beside it. Growth reveals the writing area
   alone; earlier turns the reader has passed stay out of view. Every box a thread or a
   seat holds answers both, whichever owner built it. The climbs cross shadow roots,
   since a widget may draw a thread inside its own tree and still be scrolled by the
   page, and the box that scrolls a thread is the reading region's (`scrollerFor`). A
   thread in a surface fixed over the page, the margin card, is shown by bringing that
   surface back first (`readings/off-flow.js`). These landings serve thread navigation,
   sending, and editor growth. Merely entering a reply reveals its writing area
   instead (`landing.js`): a visible pinned row or a separate transcript keeps
   the turn the user was reading, even when it is not the latest one. A thread opened
   for reading, on a card or in the panel's view, shows its first unread turn, else
   its latest (`showReturnTurn`). */
import { setScroll } from "../../dom/arrivals.js";
import {
  seenRect,
  showsContents,
  slotTop,
  stuckBox,
  userScrollport,
} from "../../dom/geometry.js";
import { scrollBehavior } from "../../dom/motion.js";
import { whenDocumentPresented } from "../../state/semantic-state.js";
import { scrollerFor } from "../../readings/reading-regions.js";
import { edgeAt, returnTo } from "../../readings/scroll-containers.js";
import { under } from "../../lib/shadow-tree.js";
import { bringBackSurfaceOf } from "../../readings/off-flow.js";
import { retainUserIntent } from "../../dom/user-intent.js";
import { standsAt } from "../../readings/user-place.js";
import {
  alreadyShown,
  fitsWhole,
  keepInBand,
  scrollIntoView,
} from "../../readings/landing-scroll.js";
import { moveScrollerBy, scrollToEnd } from "../../dom/scrolling.js";
import { SAY_BOX, SAY_ROW, THREAD } from "./selectors.js";
import type { ThreadReading } from "../../base/held-place.js";
import type { ThreadRecord } from "./thread-card.js";

const replyRowOf = (held: Element, control: Element) => {
  const reply =
    control === held
      ? [...held.children].find((node) => node.matches(SAY_ROW))
      : control.closest(SAY_ROW);
  return reply?.parentElement === held ? reply : null;
};
// A reply row pinned to its scroller's foot (a panel card's) stands in the band
// while the thread's end lies below it, so aiming a scroll at it moves nothing: its place
// in the transcript is the thread's end. Pinned is the row itself stuck, which includes
// the row standing on its foot line at the thread's very end (dom/geometry.js, `stuckBox`).
export const pinnedReply = (reply: Element | null | undefined) =>
  reply != null && stuckBox(reply) === reply ? reply : null;
// The common transcript is a separate reading region only when its container bounds it.
// This asks the transcript the test `regionScrollBehavior` asks a region's body rather than
// asking `regionScrollBehavior`: the transcript is a registered region only in a floating
// card, and elsewhere that reading would answer for the threads list around it.
const separateTranscript = (held: Element) => {
  const transcript = held.querySelector(":scope > .lf-thread-transcript");
  return transcript && userScrollport(getComputedStyle(transcript).overflowY)
    ? transcript
    : null;
};

// Keep a whole thread in view when it fits. A long thread reveals its reply
// area, including Send and Resolve; an oversized editor reveals only its control.
// scrollIntoView(nearest) on a card spanning both edges otherwise moves nothing, and
// so does one aimed at a pinned reply row, so a long thread with one lands its end.
// A control inside the thread that the user already sees stays where it is, as a
// summary's Show or Hide does: bringing the rest of the thread into view would carry
// it from under their aim (browser/AGENTS.md, "The page holds still under the user's aim"). A reply row pinned to its
// scroller's foot stays put whatever lands, so its landing still shows the thread's end.
const landingTarget = (
  held: Element,
  control: Element,
): { node: Element | null; block?: ScrollLogicalPosition } => {
  const reply = replyRowOf(held, control);
  if (control !== held && !pinnedReply(reply) && alreadyShown(control))
    return { node: null };
  if (fitsWhole(held)) return { node: held };
  // The thread itself, landed as a whole, is not a way into its pinned reply.
  if (pinnedReply(reply))
    return control === held ? { node: null } : { node: held, block: "end" };
  if (reply && fitsWhole(reply)) return { node: reply };
  if (control === held && seenRect(held, new Map())) return { node: null };
  return { node: control };
};

// Whether the user has scrolled a reply row away: none of it in front of them
// (dom/geometry.js, `seenRect`).
const onScreen = (node: Element) => seenRect(node, new Map()) !== null;

// The turn a user comes back to a thread for: the first message they have not read,
// named by the thread's `unread`, else its latest message shown, or the summary
// standing for earlier ones. Landing past an unread start would leave the user reading
// below a message they never saw begin, which read tracking (read.js) then rightly
// keeps unread while every reply after it reads. A closed summary hides the unread
// message behind its checkpoint, which stands before the messages it covers
// (transcript.js), so the user starts at that summary, and Next unread or `g u` opens
// it. Rejected: opening the summary on arrival, which would undo the fold the agent
// wrote for every reader who comes back.
const returnTurn = (transcript: Element, unread: string | null) => {
  const turns = [
    ...transcript.querySelectorAll(":scope > :is(.lf-msg, .lf-thread-checkpoint)"),
  ];
  let start = unread
    ? (turns.find((node) => node.getAttribute("data-lf-message") === unread) ?? null)
    : null;
  while (start && !showsContents(start)) start = start.previousElementSibling;
  return start ?? turns.findLast((node) => showsContents(node)) ?? null;
};

// Where a box scrolling a transcript starts showing its turns: where its first turn's
// head stands at rest, below the focus-ring room the box keeps over them. A turn
// landed in that room would start where read tracking sees nothing of it
// (dom/geometry.js, `seenRect`), and never read.
const headLine = (scroller: Element) =>
  scroller.getBoundingClientRect().top + scroller.clientTop + slotTop(scroller);

// Where the user has read a thread's view to: the turn standing at the top of the box
// scrolling its transcript (`headLine`), a message by the message it draws or a
// summary's fold by its summary, of the turns the transcript shows, and how far below
// that line it starts. A message a closed fold holds is no turn the user read to.
// `showReading` stands that turn there again in a new drawing of the thread, so its
// lines come back where they stood though turns above them grew, folded or arrived
// since. History keeps it for each entry (records/history.js), the panel's
// hold of where the user stepped in from, and a revision's handoff of the panel's view
// (panel/floating-panel.js, `captureCurrentLocation`). A card holding its transcript through
// one placement keeps the offset it reads and writes within that fit instead
// (thread-preview.js), since the drawing it measures stays the same.
export function readingIn(held: Element): ThreadReading | null {
  const transcript = held.querySelector(".lf-thread-transcript");
  if (!transcript) return null;
  const line = headLine(scrollerFor(transcript));
  const turns = transcript.querySelectorAll(
    ":scope > :is(.lf-msg[data-lf-message], .lf-thread-checkpoint[data-lf-summary-id])",
  );
  for (const turn of turns) {
    if (!showsContents(turn)) continue;
    const { top, bottom } = turn.getBoundingClientRect();
    if (bottom <= line) continue;
    const message = turn.getAttribute("data-lf-message");
    const summary = turn.getAttribute("data-lf-summary-id");
    if (message) return { message, offset: top - line };
    if (summary) return { summary, offset: top - line };
  }
  return null;
}
export function showReading(held: Element, reading: ThreadReading) {
  const transcript = held.querySelector(".lf-thread-transcript");
  const turn = transcript?.querySelector(
    "message" in reading
      ? `:scope > .lf-msg[data-lf-message="${CSS.escape(reading.message)}"]`
      : `:scope > .lf-thread-checkpoint[data-lf-summary-id="${CSS.escape(reading.summary)}"]`,
  );
  const { offset } = reading;
  if (!transcript || !turn || !showsContents(turn)) return;
  const scroller = scrollerFor(transcript);
  moveScrollerBy(
    scroller,
    turn.getBoundingClientRect().top - headLine(scroller) - offset,
  );
}

// A thread opened for reading shows the turn the user comes back for: the end of the
// box scrolling its transcript where that turn is still in view there, or else that
// turn's head at the box's top. The box is the transcript itself on a card and the
// view around it in the panel. The turn carries its own head, so it is measured from
// the box's top.
export function showReturnTurn(transcript: Element, thread: ThreadRecord | null) {
  const scroller = scrollerFor(transcript);
  scrollToEnd(scroller);
  const unread = thread?.unread[0]?.message;
  const start = thread?.msgs.find((message) => message.id === unread)?.key;
  const turn = returnTurn(transcript, start ?? null);
  if (!turn) return;
  const over = headLine(scroller) - turn.getBoundingClientRect().top;
  // A turn only a little taller than its room still shows its head at the end.
  // Keep its trailing reference and metadata there; align to the head only when
  // scrolling to the end would hide that head altogether.
  const headHeight = turn.firstElementChild?.getBoundingClientRect().height ?? 0;
  if (over > headHeight) moveScrollerBy(scroller, -over);
}

function landThread(
  held: Element,
  control: Element,
  behavior: ScrollBehavior,
  block: ScrollLogicalPosition,
) {
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
const landings: WeakMap<
  Element,
  {
    control: Element;
    block: ScrollLogicalPosition;
    mayLand: ReturnType<typeof retainUserIntent>;
  }
> = new WeakMap();
export function keepThreadLanding(held: Element | null) {
  if (!held) return;
  const landing = landings.get(held);
  if (!landing) return;
  if (!landing.mayLand()) {
    landings.delete(held);
    return;
  }
  landThread(held, landing.control, "instant", landing.block);
}

export function scrollThreadIntoView(
  held: Element,
  control: Element,
  behavior: ScrollBehavior = scrollBehavior(),
  block: ScrollLogicalPosition = "nearest",
) {
  const mayLand = retainUserIntent({
    available: () => held.isConnected && control.isConnected && under(control, held),
  });
  landings.set(held, { control, block, mayLand });
  landThread(held, control, behavior, block);
}

// Taken as the user sends, before the send draws anything; the step it returns is taken
// once the send has left the user on the thread (landing.js, `landSent`). The box the
// user sent from was under their aim, and Send and the caret stood at its foot. In flow,
// its new turn grows the thread just above it, so the box goes down by what the turn
// adds, less what the emptied box gives back, as an append region lets it
// (`browser/AGENTS.md`, "The page holds still under the user's aim"), until its foot
// meets the band's foot, the line typing keeps it within (`revealWritingArea`); a foot
// already past that line stays where it stood.
// Rejected: landing the thread around the box, which aimed at the thread's foot and its
// focus ring's room while the thread fitted and at the row's foot once it did not, so
// the box stepped by the line between them; and holding the box where it stood, which
// carried every turn above it up by the new one even with room below. A row pinned to
// its scroller's foot, or below a separate transcript, stands still by itself and its
// turn lands at the transcript's end; a box out of view lands the thread around it.
// Nothing lands once a newer gesture has taken the user away from where the send left
// them, and a box the send removed has handed the user on already.
// The sent turn lands without animation: fitting can change the transcript's room in
// the next update, and an in-flight pixel destination would outlive the room it named.
// The geometry owner then preserves the landed end while it fits that room. A floating
// box presents the send itself, its content riding from where it stood to where the
// landing left it (dom/box-motion.js, "send"), so the landing stays one instant scroll.
export function sendLanding(input: Element) {
  const held = input.closest(THREAD);
  if (!held) return () => {};
  const reply = replyRowOf(held, input);
  // The row's foot on screen, and below the top of the thread it grows in.
  const read = (row: Element) => ({
    foot: edgeAt(row, "bottom"),
    within: row.getBoundingClientRect().bottom - held.getBoundingClientRect().top,
  });
  const stood =
    reply && !pinnedReply(reply) && !separateTranscript(held) && alreadyShown(reply)
      ? { row: reply, ...read(reply) }
      : null;
  return () => {
    const mayLand = retainUserIntent({ available: () => held.isConnected });
    void whenDocumentPresented()
      .then(() => {
        if (!mayLand() || !input.isConnected) return;
        if (stood === null || !held.contains(stood.row))
          return scrollThreadIntoView(held, input, "instant");
        const reply = stood.row;
        // Where the send's own growth takes the foot, whatever scrolled meanwhile.
        returnTo(reply, "bottom", stood.foot + read(reply).within - stood.within);
        revealWritingArea(held, input, reply);
        if (edgeAt(reply, "bottom") < stood.foot) returnTo(reply, "bottom", stood.foot);
      })
      .catch(() => {});
  };
}

// A box growing or shrinking under the user's own keystrokes keeps two things: its
// controls in the band, and the words just above it where they were beside it. A row in
// flow grows downward, so the words above stay put and only its foot can leave the band,
// which the landing brings back. A pinned row keeps its foot and grows upward: into the
// room between it and the words above it first (the panel card's, standing at the list's
// foot), then over those words, so the transcript moves by the part of the growth that
// now covers them. A row that shrinks uncovers words and moves none. The cover is read now
// and the row's growth from its height, since only the user's words change a row's
// height: a scroll or a reply arriving between keystrokes moves the cover and must not be
// paid for.
const rowHeights = new WeakMap<Element, number>();
const covered = (reply: Element) =>
  (reply.previousElementSibling?.getBoundingClientRect().bottom ?? -Infinity) -
  reply.getBoundingClientRect().top;
// Editing reveals only the writing area. Revealing the whole thread here would pull
// earlier turns back into view on the first keystroke in an already-visible reply. It
// follows the area's foot into the band rather than asking whether the area is already
// shown (readings/landing-scroll.js, `keepInBand`).
const revealWritingArea = (held: Element, input: Element, reply: Element | null) => {
  bringBackSurfaceOf(held, "instant");
  keepInBand(reply && fitsWhole(reply) ? reply : input);
};
// A rewrite opening in its message shows the message whole, its head with Cancel and
// Save above the words, where the band holds it, and otherwise the line its caret stands
// on, where the next key types. A reply row pinned at the scroller's foot covers what
// stands behind it, so the box's foot clears it too.
export function revealEditor(message: Element, caretLine: Element) {
  const held = message.closest(THREAD);
  if (!held) return;
  bringBackSurfaceOf(held, "instant");
  const target = fitsWhole(message) ? message : caretLine;
  scrollIntoView(target, { block: "nearest", behavior: "instant" });
  const reply = replyRowOf(held, held);
  const pinned = pinnedReply(reply);
  if (!pinned) return;
  const margin = parseFloat(getComputedStyle(message).scrollMarginBlockEnd) || 0;
  const over =
    target.getBoundingClientRect().bottom + margin - pinned.getBoundingClientRect().top;
  if (over > 0) moveScrollerBy(scrollerFor(pinned), over);
}
export function followBoxGrowth(input: Element) {
  const held = input.closest(THREAD);
  if (!held) return;
  const reply = replyRowOf(held, input);
  // A box standing in the transcript rather than its reply row, as a rewrite stands in
  // its message, keeps its caret in view itself: aimed at the whole box, a landing here
  // pulled a long one's top into view on every key.
  if (!reply) return;
  // A separate transcript gives up height rather than being covered by the editor, and
  // keeps the words at its end beside the box itself (dom/scrolling.js, `followEnd`).
  if (separateTranscript(held)) {
    if (!onScreen(reply)) revealWritingArea(held, input, reply);
    return;
  }
  if (!pinnedReply(reply)) return revealWritingArea(held, input, reply);
  const height = reply.getBoundingClientRect().height;
  const grew = height - (rowHeights.get(input) ?? height);
  rowHeights.set(input, height);
  const by = Math.max(0, Math.min(grew, covered(reply)));
  if (by) {
    const box = scrollerFor(reply);
    setScroll(box, { top: box.scrollTop + by });
  }
  // A row pins only at its scroller's foot, so one the user scrolled past is brought back.
  if (!onScreen(reply)) revealWritingArea(held, input, reply);
}
// The editor's place before its own edit: a pinned row's height. Arrival also reads
// its initial place.
export function readBoxPlace(input: Element) {
  const held = input.closest(THREAD);
  const reply = held && replyRowOf(held, input);
  // A box in the transcript has no row to hold.
  if (!reply) return;
  // The edit may be the one that takes a natural row to its sticky floor.
  rowHeights.set(input, reply.getBoundingClientRect().height);
}

// A render that inserts above the control the user is on, such as an agent's turn
// arriving in the thread they are writing in (held-news.js), keeps that control where it
// stood, as every reading from outside the tab does (readings/user-place.js,
// `holdUserPlace`). A user on the
// thread itself, where a send leaves them, waits at its reply box, so the box is what
// stays still while it is shown, as a chat's composer does, and what stands above it
// moves up by the turn; a message they stand on stays and the box below it moves down.
standsAt(THREAD, (thread) => thread.querySelector(SAY_BOX));
