/* This module owns reader travel. */
import { clampedRow } from "./keyboard/bindings.js";
import { inPanel, panelCovers, panelIsOpen } from "./conversation/panel-elements.js";
import { openThreads } from "./conversation/thread-list.js";
import { narrowed } from "./conversation/narrowing.js";
import { reducedMotion, scrollBehavior } from "./motion.js";
import { threadsBox } from "./conversation/panel-elements.js";
import { pageScroller } from "./scrolling.js";
import { effectiveScroller, readingRegionFor } from "./reading-regions.js";
import { closestAcross } from "./passages.js";
import { announce } from "./notifications.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";

const threadPosition = (activeInlineThread) => {
  const threads = openThreads({ visibleOnly: panelIsOpen() });
  const current = panelIsOpen()
    ? closestAcross(document.activeElement, ".lf-thread[data-id]")
    : threads.find(
        (thread) => thread.dataset.id === activeInlineThread()?.dataset.thread,
      );
  return listWalkPosition(threads, current, {
    identity: (thread) => thread.dataset.id,
    qualifier: panelIsOpen() && narrowed() ? "shown" : "",
  });
};

// t/T walk open threads in page order. A closed panel keeps the walk at the thread's
// inline address: a declared widget outlet first, then the thread margin element's card. A thread
// with no page address is indexed only by Threads, so that destination opens the panel.
// Once the panel is open, the walk stays in its list. Both paths are clamped, not wrapped.
export function stepThread(
  dir,
  { openPageThread, scrollToThread, activeInlineThread },
) {
  const threads = openThreads({ visibleOnly: panelIsOpen() });
  const inline = activeInlineThread();
  const current = panelIsOpen()
    ? document.activeElement?.closest?.(".lf-thread")
    : threads.find((thread) => thread.dataset.id === inline?.dataset.thread);
  const next = clampedRow(threads, current, dir);
  if (!next) return;
  if (!panelIsOpen()) {
    openPageThread(next.dataset.id, { focus: "thread" });
    announce(
      beginWalk("thread", "Thread", () => threadPosition(activeInlineThread)) ??
        walkPositionLabel("Thread", threads.indexOf(next) + 1, threads.length),
    );
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
  announce(
    beginWalk("thread", "Thread", () => threadPosition(activeInlineThread)) ??
      walkPositionLabel("Thread", threads.indexOf(next) + 1, threads.length),
  );
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
const stepScroller = () => {
  if (panelCovers()) return threadsBox;
  const region = readingRegionFor(document.activeElement);
  return region ? effectiveScroller(region) : inPanel() ? threadsBox : pageScroller;
};
export function stepReading(amount, unit) {
  const box = stepScroller();
  if (unit === "page") {
    const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
    amount *= box.clientHeight - clear;
  }
  const from = holding(box) ? glide.goal : box.scrollTop;
  glideTo(box, from + amount);
}
// One eased travel to a goal, shared by the reading-page step and the sequence's edges. The
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

// A spatial command takes the page where it is now. Stop only the travel this owner is
// driving; native paging belongs to the platform and reports its motion through scroll.
export function stopGlide(box) {
  if (glide?.box !== box) return;
  cancelAnimationFrame(glide.raf);
  glide = null;
}
