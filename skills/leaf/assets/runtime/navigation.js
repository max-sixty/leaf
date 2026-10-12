/* Reading movement: walks, scrolling, and aligning the current item without travel.
 * Alignment reads the browser's current selection/focus and the owning reading region;
 * it changes only vertical scroll, retaining focus, selection and browser history. */
import { cancelRender, nextFrame } from "./rendering.js";
import { scrollGlides } from "./arrivals.js";
import { cycledRow } from "./keyboard/bindings.js";
import { coveringAuxiliarySurface, pageCommand } from "./keyboard/register.js";
import { nativeModalAdmits } from "./keyboard/layer-stack.js";
import { sampleNotice } from "./sample-child.js";
import { reducedMotion, scrollBehavior } from "./motion.js";
import { atScrollEnd, pageScroller, scrollLimit } from "./scrolling.js";
import { landingBand, shownRect } from "./geometry.js";
import { intersect } from "./rect.js";
import {
  effectiveScroller,
  userReadingRegion,
  readingRegionFor,
  scrollChainOf,
  scrollersOf,
} from "./reading-regions.js";
import { walkOrigin, heldQuestion, placeOf, stepFrom } from "./standing-target.js";
import { focused, standingIn } from "./focus.js";
import { bannerStanding } from "./banner-toolbar.js";
import { pageSelection } from "./composing/capture.js";
import { blockAt, closestAcross, pageRange } from "./passages.js";
import { readingBlock } from "./reading-place.js";
import { scrollIntoReadingBand, scrollIntoView } from "./landing-scroll.js";
import { THREAD } from "./thread/selectors.js";
import { under } from "./shadow.js";
import { retainUserIntent } from "./user-intent.js";
import { announce } from "./notifications.js";
import { focusThread } from "./thread/focus.js";
import { landWalkedThread } from "./thread/landing.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";

// The walk's reading supplies both its destinations and their visible scope. In the
// panel they are the cards its list walks (`walkRows`), which may show resolved threads
// too; only the closed-panel page walk promises open threads.
const threadWalk = (panelIsOpen, { threadsBox, openThreadsInPageOrder }) => {
  const inPanel = panelIsOpen();
  return {
    threads: inPanel
      ? threadsBox.walkRows().flatMap(({ thread }) => thread ?? [])
      : openThreadsInPageOrder(),
    scope: inPanel ? "shown" : "open",
  };
};

// The walk's place: the list thread holding focus, or the thread the user is at from
// its target (`threadHere`), in the list or beside the page.
const currentThread = (threads, threadHere) => {
  const held = threadHere();
  const id = held?.dataset.id ?? held?.dataset.thread;
  return threads.find((thread) => thread.dataset.id === id);
};

const threadPosition = (threadHere, panelIsOpen, narrowing, list) => {
  const { threads, scope } = threadWalk(panelIsOpen, list);
  const current = currentThread(threads, threadHere);
  return listWalkPosition(threads, current, {
    identity: (thread) => thread.dataset.id,
    qualifier: panelIsOpen() && narrowing.narrowed() ? scope : "",
  });
};

// Arrive at one thread a walk chose, `next` its list card: the one arrival both
// the t/T walk and the queue walk (queue-walk.js) make. With the panel shut it opens the
// thread at its inline destination: a declared widget outlet first, then the thread
// margin entry's card; a thread with no page destination is indexed only by Threads, so
// that destination opens the panel.
//
// With the panel open, both halves of the press go where they were pointed. The list
// lands the thread off the focus it is about to take, so a press on a walk of one
// thread, which names the thread the user already stands on, moves no focus and gives the
// list nothing to land: the press lands that thread itself. The page half travels either
// way, and keeps the panel the walk is in: it moves the page only where moving it shows
// the passage better beside the panel (anchor-travel.js, `arrive`).
//
// It answers whether the user arrived, once the thread stands open. `intent` is the
// press's, retained before any wait the caller made: newer input cancels the arrival,
// and the walk then says nothing about a thread the user is not at.
async function arriveAtThread(next, destinations, panelIsOpen, threadsBox, intent) {
  const { openPageThread, scrollToThread } = destinations;
  if (!panelIsOpen())
    return Boolean(await openPageThread(next.dataset.id, { part: "thread", intent }));
  if (!intent()) return false;
  threadsBox.revealNavigation(next.dataset.id);
  const standing = next.contains(focused(document));
  focusThread(next, "move");
  if (standing) landWalkedThread(next, threadsBox);
  scrollToThread(next.dataset.id, { keep: true });
  return true;
}

// t/T walk threads. A closed panel walks open threads in page order; once the panel is
// open, the walk stays in its list, in whichever order the list shows. Both paths come
// round from either end to the other (`cycledRow`).
//
// From a place at no thread, the walk steps by the page walks' one rule (`stepFrom`,
// standing-target.js): a place on the page against each thread's place as the list
// sorts it (`threadPlace`), and a list row that is no thread, such as a withdrawn
// thread's notice, against the cards beside it. A thread whose place holds the user's is
// where they are without the thread open, so the press opens it. A general thread has
// no place and stands after every placed one; in the panel's Recent order every thread
// is reached from the list's ends.
function stepThread(dir, destinations, panelIsOpen, narrowing, list) {
  const { threadsBox } = list;
  const { threadHere, threadAtStanding, threadPlace } = destinations;
  const { threads } = threadWalk(panelIsOpen, list);
  const current = currentThread(threads, threadHere);
  const targetId = !current && threadAtStanding();
  const atTarget = targetId && threads.find((thread) => thread.dataset.id === targetId);
  // Focus on a list row the walk does not count, such as a withdrawn thread's notice.
  const atRow = panelIsOpen() && focused() !== threadsBox && standingIn(threadsBox);
  const { row: next, wrapped } = current
    ? cycledRow(threads, current, dir)
    : atTarget
      ? { row: atTarget, wrapped: false }
      : atRow
        ? stepFrom(threads, focused(), dir, (thread) => thread)
        : stepFrom(
            threads,
            !panelIsOpen() || narrowing.listedInPageOrder() ? walkOrigin() : null,
            dir,
            (thread) => threadPlace(thread.dataset.id),
          );
  if (!next) return;
  // The walk reads the standing destination, so begin it once the arrival has moved
  // focus, as the queue walk does; an arrival that failed registers nothing.
  const ready = arriveAtThread(
    next,
    destinations,
    panelIsOpen,
    threadsBox,
    retainUserIntent(),
  ).then((arrived) => {
    if (!arrived) return;
    announce(
      beginWalk(
        "thread",
        "Thread",
        () => threadPosition(threadHere, panelIsOpen, narrowing, list),
        wrapped,
      ) ?? walkPositionLabel("Thread", threads.indexOf(next) + 1, threads.length),
    );
  });
  void ready.catch(() => {});
  return ready;
}

// Put the comment the user is standing on against one edge of its list. This is
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
// They move the region the user is reading. The thread list is that region when
// focus stands on its frame; a nested region keeps its own scrollport. Scrolling a
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
// The document's box lends its top edge to the fixed banner and its bottom edge to the
// bottom bar, and its scroll-padding — read exactly so by scrollToElement — is where the
// box already says how much of itself stands covered, so a reading-page step is 60% of
// what is left rather than 60% of the box, which is the answer the user wants — a step
// that landed them under the banner would be a step onto words they cannot read.
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
// The visible box used by page-edge navigation. A covering panel replaces the page;
// beside it, the document keeps its own top and bottom.
const seenScroller = (coveringAuxiliaryScroller) =>
  coveringAuxiliaryScroller() ?? pageScroller;
// Reading-page keys follow the region the user is working in (`userReadingRegion`), so
// `d` after a click in a pane scrolls that pane as PageDown does. Focus can put them in
// a panel or anchored thread beside the page. Inside a covering surface the user's
// region still wins where it is in that surface; its own scrollport may be nested
// there. The covering scrollport catches everything else. Focus on a region's
// apparatus follows its actual containing scrollport within the region while that
// box overflows; otherwise the region's reading body takes the step. A preferred box
// outside the visible band yields to its nearest visible enclosing region. Neither
// fallback changes which region the user is reading.
const readingStep = (box, clips) => {
  const shown = shownRect(box, clips);
  const band = shown && landingBand(box);
  if (!band) return null;
  const { top, bottom } = intersect(shown, band, { y: true });
  return bottom > top ? { box, height: bottom - top } : null;
};
const stepScroller = (coveringAuxiliaryScroller) => {
  const covering = coveringAuxiliaryScroller();
  const region = userReadingRegion();
  const preferred =
    covering && !(region && under(region.host, coveringAuxiliarySurface()))
      ? covering
      : effectiveScroller(region);
  const clips = new Map();
  const at = focused();
  if (region && under(at, region.host) && !under(at, region.body)) {
    const containing = scrollersOf(at).next().value;
    if (
      containing &&
      under(containing, region.host) &&
      containing.scrollHeight > containing.clientHeight &&
      (!covering || under(containing, coveringAuxiliarySurface()))
    ) {
      const step = readingStep(containing, clips);
      if (step) return step;
    }
  }
  const step = readingStep(preferred, clips);
  if (step) return step;
  for (const box of scrollersOf(preferred)) {
    if (box === preferred) continue;
    const step = readingStep(box, clips);
    if (step) return step;
  }
  return null;
};
function stepReading(amount, unit, coveringAuxiliaryScroller) {
  const first = stepScroller(coveringAuxiliaryScroller);
  if (first) stepAlong(first.box, amount, unit, first);
}
// The step walks the chain from `from` to the first box that can take it. A box that
// contains its overscroll, or one a standing modal leaves outside, ends the walk. A
// sample's chain runs on past its document into the containing page, as the wheel's
// does, so a chain spent without either boundary passes the step on, and the
// containing page's navigation takes it up from the frame; outside a sample the notice
// goes nowhere.
function stepAlong(from, amount, unit, first = null) {
  const clips = new Map();
  for (const box of scrollChainOf(from)) {
    if (!nativeModalAdmits(box)) return;
    const step = box === first?.box ? first : readingStep(box, clips);
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

export function createNavigation({
  panelElements: { threadsBox, inPanel: panelFocusIsInside },
  threadCards,
  openThreadsInPageOrder,
  panelIsOpen,
  narrowing,
  coveringAuxiliaryScroller,
  threadDestinations,
}) {
  const currentItem = () => {
    const at = bannerStanding()?.focus?.deref() ?? focused();
    // More's retained node is the same browser standing, read without moving focus
    // merely to paint whether its control is available.
    const question = heldQuestion(at);
    if (question && under(at, question)) return question;
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
  const alignTop = {
    id: "reading.align.top",
    keys: ["z"],
    title: "Align current item at top",
    description:
      "Align the current reading item at the top, keeping focus and selection",
    touch: "Align current item at top",
    menu: "navigate",
    retainStanding: true,
    covering: true,
    when: () => Boolean(currentItem()),
    run: () => {
      const item = currentItem();
      if (!item) return;
      for (const box of scrollersOf(item)) stopGlide(box);
      scrollIntoReadingBand(item, item, "start", scrollBehavior());
    },
  };
  const inPanel = () => panelFocusIsInside(panelIsOpen);
  const threadList = { threadsBox, openThreadsInPageOrder };
  const move = (amount, unit) => stepReading(amount, unit, coveringAuxiliaryScroller);
  const walkThreads = (dir) =>
    stepThread(dir, threadDestinations, panelIsOpen, narrowing, threadList);

  // Travel's own page keys. All three remain reachable inside a covering auxiliary
  // surface: the surface replaces the page the user is reading rather than ending the
  // reading, and t/T follows whichever surface is presenting the threads.
  pageCommand({
    id: "thread.walk",
    touch: false,
    // A walk's letter names its category; Shift reverses it. The page's walks therefore
    // share one compact, repeatable grammar.
    keys: ["t", "Shift+t"],
    routes: [
      {
        id: "thread.next",
        binding: "t",
        title: () => `Next ${threadWalk(panelIsOpen, threadList).scope} thread`,
      },
      {
        id: "thread.previous",
        binding: "Shift+t",
        title: () => `Previous ${threadWalk(panelIsOpen, threadList).scope} thread`,
      },
    ],
    title: "threads",
    covering: true,
    // Once textual search owns the panel, n/N are the canonical walk there. Keep t/T
    // in other contexts without leaving two spellings for the same panel search action.
    when: () =>
      threadWalk(panelIsOpen, threadList).threads.length > 0 &&
      (!coveringAuxiliarySurface() || inPanel()) &&
      !(narrowing.threadSearchActive() && inPanel()),
    repeat: true,
    // The walk moves the user laterally: it is the surface it reaches through, rather
    // than the walk, that Escape takes off. In the panel it moves focus from card to
    // card, and the panel's own rungs clear its narrowing and close it from whichever
    // one they end on. With the panel shut it stands them on a thread a widget seats on the page,
    // or opens the margin's thread view for a thread with no seat, and that view
    // is what the Page Map's own step dismisses.
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
        description: "Move 60% of a page down",
        title: "page down",
      },
      {
        id: "page.up",
        binding: "u",
        description: "Move 60% of a page up",
        title: "page up",
      },
    ],
    title: "page down / up",
    covering: true,
    repeat: true,
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
        description: "Scroll down a little",
        title: "scroll down",
      },
      {
        id: "scroll.up",
        binding: "k",
        description: "Scroll up a little",
        title: "scroll up",
      },
    ],
    title: "scroll down / up",
    covering: true,
    repeat: true,
    run: (binding) => move(binding === "j" ? 60 : -60, "pixel"),
  });

  // The queue walk's way onto one thread it names by id: the t/T walk's own arrival, at
  // the thread's list card. A narrowing that hides the card is cleared first, as it is
  // for a Question seated in a thread (questions/view.js, `materializeQuestion`), since the queue
  // walk goes to what is on the user whatever the list shows.
  async function arriveAtThreadById(id) {
    const intent = retainUserIntent();
    const card = () =>
      (panelIsOpen() ? threadCards() : openThreadsInPageOrder()).find(
        (thread) => thread.dataset.id === id,
      );
    if (panelIsOpen() && card()?.hidden) await narrowing.revealThread(id);
    const next = card();
    if (!next) return false;
    return arriveAtThread(next, threadDestinations, panelIsOpen, threadsBox, intent);
  }

  return {
    alignTop,
    arriveAtThread: arriveAtThreadById,
    seenScroller: () => seenScroller(coveringAuxiliaryScroller),
    stepReading: move,
    stepThread: walkThreads,
    // Where the thread walk stands, which the panel's arrows report as `t` does.
    threadPosition: () =>
      threadPosition(threadDestinations.threadHere, panelIsOpen, narrowing, threadList),
  };
}
