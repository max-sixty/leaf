/* This module owns reader travel and scroller selection. */
import { clampedRow } from "./keyboard/bindings.js";
import { shownRect } from "./geometry.js";
import { BANNER_CLEAR, commentOnTarget } from "./composing/surface.js";
import { scrollToElement, scrollToThread } from "./anchors.js";
import { inPanel, panelCovers, panelIsOpen } from "./chrome-layout.js";
import { openThreads } from "./conversation/reconcile.js";
import { reducedMotion, scrollBehavior } from "./motion.js";
import { threadsBox } from "./conversation/panel.js";
import { pageScroller } from "./scrolling.js";
import { inChrome } from "./passages.js";
import { activeInlineThread, openPageThread } from "./living-margin.js";

// Where a comment about this item is written: the composer, on the item, which is what a
// click through the ⌥ aim already opens. It reached for the widget's own conversation seat
// first for a while, on the reasoning that a widget holding a box for its conversation
// should not be given a second one. That was the wrong shape. `commentOnTarget` writes
// `{section: item.id}`, which is exactly the anchor `renderConversations` collects into
// that seat — so the words land in the same conversation by either route, and the seat was
// buying a focus landing at the price of five separate questions: escaping an
// author-written id into a selector, whether the box can take focus at all (a settled
// group's seat is inside `hidden="until-found"` and silently swallowed the press), which
// box when the seat holds several threads, what design mode files, and where the reader
// was already standing. One route answers all five by not asking them.
//
// The scroll is for the standing that has gone stale — an address or a Tab leaves the item
// on screen, but focus outlives the scroll that put it there, and a box about something
// off screen is a box about nothing the reader can see.
export function commentOnItem(item) {
  // Only where the item is not already in front of the reader. Travelling every time moved
  // the page under someone who could see the thing perfectly well: Tab leaves an item at an
  // edge (`block: nearest`), so centring took the page a third of a viewport with nothing on
  // screen to explain it — on the route this press exists for, and where the ⌥ aim it is the
  // twin of moves nothing at all. The travel is for the standing that has gone stale, focus
  // outliving the scroll that put it there: a box about something off screen is a box about
  // nothing the reader can see.
  //
  // What the page shows of it, which is the reading the aim's own paint takes
  // (`refreshAim`) — this being its keyboard twin, the two decide "is this in front of the
  // reader" the same way or they are not twins. An unclipped box alone is the box the item
  // would have: an item scrolled out of a board's sideways scroller still reports one
  // inside the window, so a gate reading that called it showing and opened the box on
  // something off screen, which the unconditional travel it replaced never did. Any part
  // showing is enough, which is also what keeps a box taller than the window from jumping
  // to its top under a reader halfway down it.
  //
  // A collapsed ancestor zeroes its descendants' boxes, so a thing inside a shut
  // disclosure is never showing and takes the travel, `reveal` with it. Standing on the
  // summary itself is the one motion this drops: the disclosure stays shut and the box
  // opens on it where it is, rather than springing it open and reflowing the page under
  // the reader who was looking at it.
  //
  // Instant, and before the box is measured. Placing reads the item's box, so that has to
  // be the box the item keeps; and opening focuses the textarea, whose scroll-into-view
  // cancels a glide already under way — which is what left the item flush against an edge
  // rather than framed, and is not `openComposer`'s to give up, three other presses opening
  // that box against a passage they have not moved.
  const seen = shownRect(item, new Map());
  if (!seen || seen.bottom <= BANNER_CLEAR) scrollToElement(item, "instant");
  commentOnTarget({ anchor: { section: item.id }, element: item });
}
// t/T walk open threads in page order. A closed panel keeps the walk at the thread's
// inline address: a declared widget outlet first, then the Thread Button's card. A thread
// with no page address is indexed only by Threads, so that destination opens the panel.
// Once the panel is open, the walk stays in its list. Both paths are clamped, not wrapped.
export function stepThread(dir) {
  const threads = openThreads();
  const inline = activeInlineThread();
  const current = panelIsOpen()
    ? document.activeElement?.closest?.(".lf-thread")
    : threads.find((thread) => thread.dataset.id === inline?.dataset.thread);
  const next = clampedRow(threads, current, dir);
  if (!next) return;
  if (!panelIsOpen()) {
    openPageThread(next.dataset.id, { focus: "thread" });
    return;
  }
  // Landing the thread is the list's, off the focus it is about to take. A press at
  // either end of the walk is the exception the list cannot answer: it names the thread
  // the reader already stands on, so no focus moves and nothing fires, while the page
  // half of the press still travels. Both halves therefore go where they were pointed.
  const standing = next === document.activeElement;
  next.focus({ preventScroll: true });
  if (standing) next.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
  scrollToThread(next.dataset.id);
}

// Put the comment the reader is standing on against one edge of its list. This is
// placement inside the panel, not travel to the passage the comment is about, so it
// moves only the thread scroller and keeps the card's focus. Native scroll placement
// reads the list's declared scroll-padding, including its sticky heading and focus-ring
// room, from the same authority the t/T walk uses.
export function placeThreadEdge(thread, edge) {
  thread.scrollIntoView({ behavior: scrollBehavior(), block: edge });
}

// j/k take small pixel steps; d/u move 60% of the visible reading page. Both follow
// the active region and share one glide, so mixed or repeated presses add up from
// the pending goal. Space, Home/End and PageUp/Down stay the browser's own keys.
//
// They move the region the reader is reading, which is the thread list wherever the
// reader stands in the panel or the panel covers the page. Scrolling a region the
// reader is not in reads to them as the key doing nothing, and then the document is
// somewhere else when they look back at it.
//
// The step moves at the pace of the browser's own paging keys. Native paging is a quick
// glide — PageDown covers a page here in ~140ms, and Space and the arrows ride the same
// animator — but that animator is the compositor's and JS cannot ask for it, while
// scrollTo's smooth takes three times as long over the same distance and has no dial,
// which is what read as gradual when the step rode it. So the runtime drives the step
// itself: SCROLL_MS of easing out, each write `instant` rather than `auto` since a page is
// free to set `scroll-behavior: smooth` on the box it scrolls (moveScrollerBy says the
// same) and
// a glide built from smooth writes would never land. A press mid-flight retargets from
// the goal, so quick presses add their full distances; the goal is clamped, so pressing on
// at the foot banks no debt for u to press back through; and the step stands down the
// moment the box moves under another hand — a wheel, a centering — because the reader's
// own gesture outranks a key's. Under reduced motion the step is a jump, the answer the
// rest of the runtime's motion already gives (scrollBehavior()).
//
// The page the step measures is the one the reader can see. The document's box lends its
// top edge to the fixed banner, and scroll-padding-top — declared on that scroller, read
// exactly so by scrollToElement — is where the box already says how much of itself stands
// covered. The thread list says the same thing about itself: a stuck run heading covers
// its top, so a reading-page step there is 60% of what is left rather than 60% of the
// box, which is the answer the reader wants — a step that landed them under the heading
// would be a step onto words they cannot read.
const SCROLL_MS = 140;
let glide = null; // {box, goal, wrote, raf}
// The glide's claim on the box: it holds only while the box is where the glide last
// wrote it. The tick asks before every write, and a press asks the same question before
// trusting the goal — the reader can take the box between frames, and a press landing
// in that gap otherwise measures from a goal the box has already left.
const holding = (box) =>
  glide?.box === box && Math.abs(box.scrollTop - glide.wrote) <= 1;
// The visible box used by page-edge navigation. A covering panel replaces the page;
// beside it, the document keeps its own top and bottom.
export const seenScroller = () => (panelCovers() ? threadsBox : pageScroller);
// Reading-page keys follow the region the reader is working in. Focus can put them in a
// panel beside the page; a covering panel remains the only visible region even when
// focus is still on the banner control that opened it.
const stepScroller = () => (inPanel() || panelCovers() ? threadsBox : pageScroller);
// Which box scrolls a given element, for anything that has to name its scroller rather
// than search for one. The document's for everything the document holds — and the
// panel's own list for a widget an agent put in a reply, which is scrolled by that and
// by nothing else. A drag naming the wrong one sits at the edge waiting for a scroll
// that never comes.
export const scrollerFor = (el) => (inChrome(el) ? threadsBox : pageScroller);
export function stepReading(amount, unit) {
  const box = stepScroller();
  if (unit === "page") {
    const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
    amount *= box.clientHeight - clear;
  }
  const from = holding(box) ? glide.goal : box.scrollTop;
  glideTo(box, from + amount);
}
// One eased travel to a goal, shared by the reading-page step and the chord's edges. The
// goal is clamped here, so a step pressed on at the foot banks no debt for u to press
// back through, and an edge may be asked for as the height it cannot exceed.
export function glideTo(box, goal) {
  goal = Math.max(0, Math.min(box.scrollHeight - box.clientHeight, goal));
  if (reducedMotion()) {
    box.scrollTo({ top: goal, behavior: "instant" });
    return;
  }
  cancelAnimationFrame(glide?.raf);
  const start = box.scrollTop;
  const t0 = performance.now();
  const tick = (now) => {
    if (!holding(box)) {
      glide = null; // the box moved under another hand; theirs wins
      return;
    }
    if (reducedMotion()) {
      box.scrollTo({ top: goal, behavior: "instant" });
      glide = null;
      return;
    }
    // Floored as well as capped: a rAF timestamp is its frame's start, which can precede
    // the press that scheduled the tick, and an unfloored t walks the ease out past the
    // start — to a write the box clamps, which the next tick then read as another hand.
    const t = Math.max(0, Math.min(1, (now - t0) / SCROLL_MS));
    box.scrollTo({
      top: goal - (goal - start) * (1 - t) ** 3,
      behavior: "instant",
    });
    // Where the write left the box, not what it asked for: the box clamps at its ends
    // and snaps to pixels, and the claim the next tick tests is about the box.
    glide.wrote = box.scrollTop;
    if (t < 1) glide.raf = requestAnimationFrame(tick);
    else glide = null;
  };
  glide = { box, goal, wrote: start, raf: requestAnimationFrame(tick) };
}
