/* This module owns reader travel. */
import { clampedRow } from "./keyboard/bindings.js";
import {
  inPanel as panelFocusIsInside,
  panelWouldCover,
} from "./conversation/panel-elements.js";
import { openThreads } from "./conversation/thread-list.js";
import { narrowed, threadSearchActive } from "./conversation/narrowing.js";
import { coveringAuxiliarySurface, pageCommand } from "./keyboard/register.js";
import { reducedMotion, scrollBehavior } from "./motion.js";
import { threadsBox } from "./conversation/panel-elements.js";
import { pageScroller } from "./scrolling.js";
import { landingInsets } from "./geometry.js";
import { effectiveScroller, readingRegionFor } from "./reading-regions.js";
import { closestAcross } from "./passages.js";
import { announce } from "./notifications.js";
import { focusThread } from "./conversation/focus.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";

const walkableThreads = (panelIsOpen) =>
  (panelIsOpen() ? threadsBox.navigationThreads() : null) ??
  openThreads({ visibleOnly: panelIsOpen() });

const threadPosition = (activeInlineThread, panelIsOpen) => {
  const threads = walkableThreads(panelIsOpen);
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

// t/T walk open threads. A closed panel walks them in page order, at each thread's
// inline destination: a declared widget outlet first, then the thread margin entry's card. A
// thread with no page destination is indexed only by Threads, so that destination opens the panel.
// Once the panel is open, the walk stays in its list, in whichever order the list shows.
// Both paths are clamped, not wrapped.
function stepThread(
  dir,
  { openPageThread, scrollToThread, activeInlineThread },
  panelIsOpen,
) {
  const threads = walkableThreads(panelIsOpen);
  const inline = activeInlineThread();
  const current = panelIsOpen()
    ? document.activeElement?.closest?.(".lf-thread")
    : threads.find((thread) => thread.dataset.id === inline?.dataset.thread);
  const next = clampedRow(threads, current, dir);
  if (!next) return;
  if (!panelIsOpen()) {
    openPageThread(next.dataset.id, { focus: "thread" });
    announce(
      beginWalk("thread", "Thread", () =>
        threadPosition(activeInlineThread, panelIsOpen),
      ) ?? walkPositionLabel("Thread", threads.indexOf(next) + 1, threads.length),
    );
    return;
  }
  // Both halves of the press go where they were pointed. The list lands the thread off
  // the focus it is about to take, so a press at either end of the walk, which names the
  // thread the reader already stands on, moves no focus and gives the list nothing to
  // land: the press lands that thread itself. The page half travels either way.
  threadsBox.revealNavigation(next.dataset.id);
  const standing = next.contains(document.activeElement);
  focusThread(next, { preventScroll: true });
  if (standing) next.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
  scrollToThread(next.dataset.id);
  announce(
    beginWalk("thread", "Thread", () =>
      threadPosition(activeInlineThread, panelIsOpen),
    ) ?? walkPositionLabel("Thread", threads.indexOf(next) + 1, threads.length),
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
// They move the region the reader is reading. The thread list is that region when
// focus stands on its frame; a nested region keeps its own scrollport. Scrolling a
// region the reader is not in reads to them as the key doing nothing, and then the
// document is somewhere else when they look back at it.
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
const seenScroller = (coveringAuxiliaryScroller) =>
  coveringAuxiliaryScroller() ?? pageScroller;
// Reading-page keys follow the region the reader is working in. Focus can put them in a
// panel or anchored conversation beside the page. Inside a covering surface the focused
// region still wins; its own scrollport may be nested in that surface. The covering
// scrollport catches focus with no region, such as a blurred stop.
const stepScroller = (coveringAuxiliaryScroller) => {
  const covering = coveringAuxiliaryScroller();
  const region = readingRegionFor(document.activeElement);
  if (covering && !coveringAuxiliarySurface()?.contains(region?.host)) return covering;
  return effectiveScroller(region);
};
function stepReading(amount, unit, coveringAuxiliaryScroller) {
  const box = stepScroller(coveringAuxiliaryScroller);
  if (unit === "page") {
    amount *= box.clientHeight - landingInsets(box).top;
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

export function createNavigation({
  panelIsOpen,
  coveringAuxiliaryScroller,
  threadDestinations,
}) {
  const panelCovers = () => panelIsOpen() && panelWouldCover();
  const inPanel = () => panelFocusIsInside(panelIsOpen);
  const move = (amount, unit) => stepReading(amount, unit, coveringAuxiliaryScroller);
  const walkThreads = (dir) => stepThread(dir, threadDestinations, panelIsOpen);

  // Travel's own page keys. All three remain reachable inside a covering auxiliary
  // surface: the surface replaces the page the reader is reading rather than ending the
  // reading, and t/T follows whichever surface is presenting the threads.
  pageCommand({
    id: "thread.walk",
    // A walk's letter names its category; Shift reverses it. The page's walks therefore
    // share one compact, repeatable grammar.
    keys: ["t", "Shift+t"],
    routes: [
      { id: "thread.next", binding: "t", does: "Next open thread" },
      { id: "thread.previous", binding: "Shift+t", does: "Previous open thread" },
    ],
    does: "Next / previous open thread",
    line: "threads",
    covering: true,
    // Once textual search owns the panel, n/N are the canonical walk there. Keep t/T as
    // the page's open-thread walk without leaving two spellings for the same panel action.
    when: () =>
      openThreads({ visibleOnly: panelIsOpen() }).length > 0 &&
      (!coveringAuxiliarySurface() || inPanel()) &&
      !(threadSearchActive() && inPanel()),
    repeat: true,
    // The walk moves the reader laterally: it is the surface it reaches through, rather
    // than the walk, that Escape takes off. In the panel it moves focus from card to
    // card and the standing scope lets go of whichever one they end on, back to the
    // list. With the panel shut it stands them on a thread a widget seats on the page,
    // or opens the margin's conversation view for a thread with no seat, and that view
    // is what the Page Map's own step dismisses.
    run: (binding) => walkThreads(binding === "t" ? 1 : -1),
  });
  pageCommand({
    id: "page.move",
    keys: ["d", "u"],
    routes: [
      {
        id: "page.down",
        binding: "d",
        does: "Move 60% of a page down",
        line: "page down",
      },
      { id: "page.up", binding: "u", does: "Move 60% of a page up", line: "page up" },
    ],
    does: "Move 60% of a page down or up",
    line: "page down / up",
    covering: true,
    repeat: true,
    run: (binding) => move(binding === "d" ? 0.6 : -0.6, "page"),
  });
  pageCommand({
    id: "scroll.move",
    keys: ["j", "k"],
    routes: [
      {
        id: "scroll.down",
        binding: "j",
        does: "Scroll down a little",
        line: "scroll down",
      },
      { id: "scroll.up", binding: "k", does: "Scroll up a little", line: "scroll up" },
    ],
    does: "Scroll down or up a little",
    line: "scroll down / up",
    covering: true,
    repeat: true,
    run: (binding) => move(binding === "j" ? 60 : -60, "pixel"),
  });

  return {
    panelCovers,
    seenScroller: () => seenScroller(coveringAuxiliaryScroller),
    stepReading: move,
    stepThread: walkThreads,
  };
}
