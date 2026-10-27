/* Reading movement: walks, scrolling, and aligning the current item without travel.
 * Alignment reads the browser's current selection/focus and the owning reading region;
 * it changes only vertical scroll, retaining focus, selection and browser history. */
import { cancelRender, nextFrame } from "./rendering.js";
import { scrollGlides } from "./arrivals.js";
import { cycledRow } from "./keyboard/bindings.js";
import { pageCommand } from "./keyboard/register.js";
import { nativeModalAdmits } from "./keyboard/layer-stack.js";
import { sampleNotice } from "./sample-child.js";
import { reducedMotion, scrollBehavior } from "./motion.js";
import { atScrollEnd, scrollLimit } from "./scrolling.js";
import { landingBand, shownRect } from "./geometry.js";
import { intersect } from "./rect.js";
import {
  effectiveScroller,
  userReadingRegion,
  readingRegionFor,
  scrollChainOf,
  scrollersOf,
} from "./reading-regions.js";
import {
  currentLocationOrigin,
  walkOrigin,
  heldObligation,
  heldPagePlace,
  placeOf,
  stepFrom,
} from "./current-target.js";
import { focused } from "./focus.js";
import { pageSelection } from "./composing/capture.js";
import { blockAt, closestAcross, pageRange } from "./passages.js";
import { readingBlock } from "./reading-place.js";
import { scrollIntoReadingBand, scrollIntoView } from "./landing-scroll.js";
import { drawnThreadId, THREAD } from "./thread/selectors.js";
import { threadIn } from "./thread/focus.js";
import { threadList } from "./thread/state.js";
import { inPageOrder } from "./thread/placement.js";
import { under } from "./shadow.js";
import { retainUserIntent } from "./user-intent.js";
import { announce } from "./notifications.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";
import { savedReadingSettled } from "./keyboard/bindings.js";

// The walk's threads: the open ones, in the page's order (thread/placement.js), read
// from the thread model rather than from any surface that draws them, so every route
// into the walk steps through the same list. Each is named by its id.
const openThreads = (placedAt) =>
  inPageOrder(
    threadList().filter((thread) => !thread.resolved),
    placedAt,
  ).map((thread) => thread.id);

// The thread the walk stands on: the one the origin's current location is in,
// wherever it is drawn. Its target, with the thread's card beside it, is at the thread,
// not on it (current-target.js, `walkOrigin`).
const currentThread = (threads, origin) => {
  const id =
    origin?.kind === "current-location" ? drawnThreadId(threadIn(origin.node)) : null;
  return threads.includes(id) ? id : null;
};

const threadPosition = (placedAt) => {
  const threads = openThreads(placedAt);
  return listWalkPosition(threads, currentThread(threads, currentLocationOrigin()));
};

// Arrive at one thread a walk chose, by its id: the one arrival both the t/T walk and
// the queue walk (queue-walk.js) make. It opens the thread at its destination: a
// declared widget outlet first, then the thread margin entry's card, then the floating
// panel's view of it (thread/destination.js).
//
// It answers whether the user arrived, once the thread stands open. `intent` is the
// press's, retained before any wait the caller made: newer input cancels the arrival,
// and the walk then says nothing about a thread the user is not at.
async function arriveAtThread(id, { openPageThread }, intent) {
  return Boolean(await openPageThread(id, { part: "thread", intent }));
}

// t/T walk the open threads in page order, coming round from either end to the other
// (`cycledRow`).
//
// From anywhere but a thread, the walk steps by the page walks' one rule (`stepFrom`,
// current-target.js): a place on the page against each thread's place (`threadPlace`).
// A thread at the user's current location, or whose place holds where they are, is
// where they are without being in it, so the press opens it. A general thread has no
// place and stands after every placed one.
function stepThread(dir, destinations, placedAt) {
  const { threadAtCurrentLocation, threadPlace } = destinations;
  const threads = openThreads(placedAt);
  const origin = walkOrigin();
  const current = currentThread(threads, origin);
  const targetId =
    !current && origin.kind !== "enter" && threadAtCurrentLocation(origin.node);
  const atTarget = targetId && threads.includes(targetId) ? targetId : null;
  const next = current
    ? cycledRow(threads, current, dir)
    : (atTarget ?? stepFrom(threads, origin, dir, threadPlace));
  if (!next) return;
  // The walk reads the current destination, so begin it once the arrival has moved
  // focus, as the queue walk does; an arrival that failed registers nothing.
  const ready = arriveAtThread(next, destinations, retainUserIntent()).then(
    (arrived) => {
      if (!arrived) return;
      announce(
        beginWalk("thread", "Thread", () => threadPosition(placedAt)) ??
          walkPositionLabel("Thread", threads.indexOf(next) + 1, threads.length),
      );
    },
  );
  void ready.catch(() => {});
  return ready;
}

// Put the comment the user is on against one edge of its list. This is
// placement inside the panel, not travel to the passage the comment is about, so it
// moves only the thread scroller and keeps the card's focus. Native scroll placement
// reads the list's declared scroll-padding, its focus-ring room, from the same authority
// the t/T walk uses.
export function placeThreadEdge(thread, edge) {
  scrollIntoView(thread, { behavior: scrollBehavior(), block: edge });
}

// j/k take small pixel steps; d/u move 60% of the visible reading page. Both follow
// the active region and share one glide, so mixed or repeated presses add up from
// the pending goal. At a region's edge they follow its CSS scroll chain
// (`scrollChainOf`, `stepAlong`), stopping at the same task or modal boundary as
// native input, so a floating thread's turns, once spent, hand the step to the
// document, and a sample's to its containing page, as the wheel does. Space,
// Home/End and PageUp/Down stay the browser's own keys.
//
// They move the region the user is reading. A view the floating panel opens is that
// region when focus stands in it; a nested region keeps its own scrollport. Scrolling a
// region the user is not in reads to them as the key doing nothing, and then the
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
// moment the box moves under another hand — a wheel, a centering — because the user's
// own gesture outranks a key's. Under reduced motion the step is a jump, the answer the
// rest of the runtime's motion already gives (scrollBehavior()).
//
// The page the step measures is the visible part of the scroller's landing band.
// The document's box lends its bottom edge to the floating panel's row, and its
// scroll-padding — read exactly so by scrollToElement — is where the box already says
// how much of itself stands covered, so a reading-page step is 60% of what is left
// rather than 60% of the box, which is the answer the user wants — a step that landed
// them under the panel would be a step onto words they cannot read.
const SCROLL_MS = 140;
let glide = null; // {box, goal, wrote, raf}
// A glide is one scroll however many frames write it (arrivals.js, `scrolling`).
const setGlide = (next) => {
  glide = next;
  scrollGlides(Boolean(next));
};
// The glide's claim on the box: it holds only while the box is where the glide last
// wrote it. The tick asks before every write, and a press asks the same question before
// trusting the goal — the user can take the box between frames, and a press landing
// in that gap otherwise measures from a goal the box has already left.
const holding = (box) =>
  glide?.box === box && Math.abs(box.scrollTop - glide.wrote) <= 1;
// Reading-page keys follow the region the user is working in (`userReadingRegion`), so
// `d` after a click in a pane scrolls that pane as PageDown does. Focus can put them in
// a panel or anchored thread beside the page. Focus on a region's
// apparatus follows its actual containing scrollport within the region while that
// box overflows; otherwise the region's reading body takes the step. The step then
// walks that box's scroll chain (`stepAlong`), where a box outside the visible band
// passes it on as a spent one does, so a floating thread scrolled off screen still
// pages its document. Neither changes which region the user is reading.
const readingStep = (box, clips) => {
  const shown = shownRect(box, clips);
  const band = shown && landingBand(box);
  if (!band) return null;
  const { top, bottom } = intersect(shown, band, { y: true });
  return bottom > top ? { box, height: bottom - top } : null;
};
const stepStart = () => {
  const region = userReadingRegion();
  const at = focused();
  if (region && under(at, region.host) && !under(at, region.body)) {
    const containing = scrollersOf(at).next().value;
    if (
      containing &&
      under(containing, region.host) &&
      containing.scrollHeight > containing.clientHeight &&
      readingStep(containing, new Map())
    )
      return containing;
  }
  return effectiveScroller(region);
};
const stepReading = (amount, unit) => stepAlong(stepStart(), amount, unit);
// The step walks the chain from `from` to the first box that shows and can take it. A
// box that contains its overscroll, or one an open modal leaves outside, ends the walk.
// A sample's chain runs on past its document into the containing page, as the wheel's
// does, so a chain spent without either boundary passes the step on, and the
// containing page's navigation takes it up from the frame; outside a sample the notice
// goes nowhere.
function stepAlong(from, amount, unit) {
  const clips = new Map();
  for (const box of scrollChainOf(from)) {
    if (!nativeModalAdmits(box)) return;
    const step = readingStep(box, clips);
    const canMove = amount > 0 ? !atScrollEnd(box) : box.scrollTop > 0;
    if (step && canMove) {
      const distance = unit === "page" ? amount * step.height : amount;
      const from = holding(box) ? glide.goal : box.scrollTop;
      glideTo(box, from + distance);
      return;
    }
    if (getComputedStyle(box).overscrollBehaviorY !== "auto") return;
  }
  sampleNotice("step", { amount, unit });
}
// One eased travel to a goal, shared by the reading-page step and the sequence's edges. The
// goal is clamped here, so a step pressed on at the foot banks no debt for u to press
// back through, and an edge may be asked for as the height it cannot exceed.
export function glideTo(box, goal) {
  goal = Math.max(0, Math.min(scrollLimit(box), goal));
  if (reducedMotion()) {
    box.scrollTo({ top: goal, behavior: "instant" });
    return;
  }
  cancelRender(glide?.raf);
  const start = box.scrollTop;
  const t0 = performance.now();
  const tick = (now) => {
    if (!holding(box)) {
      setGlide(null); // the box moved under another hand; theirs wins
      return;
    }
    if (reducedMotion()) {
      box.scrollTo({ top: goal, behavior: "instant" });
      setGlide(null);
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
    if (t < 1) glide.raf = nextFrame(tick);
    else setGlide(null);
  };
  setGlide({ box, goal, wrote: start, raf: nextFrame(tick) });
}

// A spatial command takes the page where it is now. Stop only the travel this owner is
// driving; native paging belongs to the platform and reports its motion through scroll.
export function stopGlide(box) {
  if (glide?.box !== box) return;
  cancelRender(glide.raf);
  setGlide(null);
}

export function createNavigation({ threadDestinations, placedAt }) {
  const currentItem = () => {
    // The place the floating panel holds while the user is in it is the same current location,
    // read without moving focus merely to paint whether its row is available.
    const at = heldPagePlace() ?? focused();
    const item = heldObligation(at);
    if (item && under(at, item)) return item;
    const thread = closestAcross(at, THREAD);
    if (thread) return thread;
    const region = readingRegionFor(at) ?? userReadingRegion();
    const inReading = (node) => !region || under(node, region.body);
    const place = placeOf(at);
    const focusedItem = blockAt(place) ?? place;
    if (
      focusedItem &&
      inReading(focusedItem) &&
      place !== region?.host &&
      place !== region?.body
    )
      return focusedItem;
    const selection = pageSelection();
    const start = selection && pageRange(selection).startContainer;
    if (start && inReading(start)) return blockAt(start);
    const caret = getSelection()?.focusNode;
    return (inReading(caret) && blockAt(placeOf(caret))) || readingBlock(region);
  };
  // Like page scrolling, alignment stays offered at the edge of its useful range.
  // Resolve the current reading only when invoked, not on every controls repaint.
  const alignTop = {
    id: "reading.align.top",
    keys: ["z"],
    title: "Align current item at top",
    touch: "Align current item at top",
    menu: "keys",
    retainCurrentLocation: true,
    travels: true,
    run: () => {
      const item = currentItem();
      if (!item) return;
      for (const box of scrollersOf(item)) stopGlide(box);
      scrollIntoReadingBand(item, item, "start", scrollBehavior());
    },
  };
  const move = stepReading;
  const walkThreads = (dir) => stepThread(dir, threadDestinations, placedAt);

  // Travel's own page keys.
  pageCommand({
    id: "thread.walk",
    // A walk needs a visible destination, not the complete saved inventory: local
    // sends are usable destinations while the first reading is still loading.
    ready: () => savedReadingSettled() || openThreads(placedAt).length > 0,
    touch: false,
    // A walk's letter names its category; Shift reverses it. The page's walks therefore
    // share one compact, repeatable grammar.
    keys: ["t", "Shift+t"],
    routes: [
      {
        id: "thread.next",
        binding: "t",
        title: "Next open thread",
      },
      {
        id: "thread.previous",
        binding: "Shift+t",
        title: "Previous open thread",
      },
    ],
    title: "threads",
    when: () => openThreads(placedAt).length > 0,
    repeat: true,
    travels: true,
    // The walk moves the user laterally: it is the surface it reaches through, rather
    // than the walk, that Escape takes off. It stands them on a thread a widget seats on
    // the page, or opens the margin's thread view, or the floating panel's, for a thread
    // with no seat, and that view's own step dismisses it.
    run: (binding) => walkThreads(binding === "t" ? 1 : -1),
  });
  // A sample's spent step arrives at its frame (sample.js). It goes on only while the
  // user is still in that frame: one that lands after they have left was not theirs to
  // finish. The child's scripts are the page author's, like the page's own, so the
  // frame's word is trusted as a page script's would be.
  document.addEventListener("lf-sample-step", (event) => {
    const frame = event.composedPath()[0];
    if (focused() === frame) stepAlong(frame, event.detail.amount, event.detail.unit);
  });
  pageCommand({
    id: "page.move",
    touch: false,
    keys: ["d", "u"],
    routes: [
      {
        id: "page.down",
        binding: "d",
        title: "page down",
      },
      {
        id: "page.up",
        binding: "u",
        title: "page up",
      },
    ],
    title: "page down / up",
    repeat: true,
    travels: true,
    run: (binding) => move(binding === "d" ? 0.6 : -0.6, "page"),
  });
  pageCommand({
    id: "scroll.move",
    touch: false,
    keys: ["j", "k"],
    routes: [
      {
        id: "scroll.down",
        binding: "j",
        title: "scroll down",
      },
      {
        id: "scroll.up",
        binding: "k",
        title: "scroll up",
      },
    ],
    title: "scroll down / up",
    repeat: true,
    travels: true,
    run: (binding) => move(binding === "j" ? 60 : -60, "pixel"),
  });

  // The queue walk's way onto one thread it names by id: the t/T walk's own arrival,
  // whatever list the thread is in.
  const arriveAtThreadById = (id, message = null) =>
    message
      ? threadDestinations
          .openPageThread(message, { part: "message", intent: retainUserIntent() })
          .then(Boolean)
      : arriveAtThread(id, threadDestinations, retainUserIntent());

  return {
    alignTop,
    arriveAtThread: arriveAtThreadById,
    stepReading: move,
    stepThread: walkThreads,
  };
}
