/* Reading movement: walks, scrolling, and aligning the current item without travel.
 * Alignment reads the browser's current selection/focus and the owning reading region;
 * it changes only vertical scroll, retaining focus, selection and browser history. */
import { userCaret, pageRange } from "../dom/native-selection.js";
import { cycledRow } from "../dom/keyboard/bindings.js";
import { pageCommand } from "../dom/keyboard/register.js";
import { nativeModalAdmits } from "../dom/keyboard/layer-stack.js";
import { sampleNotice } from "../host/sample-child.js";
import { scrollBehavior } from "../dom/motion.js";
import {
  SCROLL_SLACK,
  afterBrowserScroll,
  atScrollEnd,
  glideTo,
  pageScroller,
  scrollGoal,
  scrollLimit,
  stopGlide,
} from "../dom/scrolling.js";
import { landingBand, layoutWindow, shownBox, shownRect } from "../dom/geometry.js";
import { hasArea, intersect } from "../dom/rect.js";
import {
  chooseReadingRegion,
  chosenReadingRegion,
  effectiveScroller,
  regionScrollBehavior,
  shownRegionBounds,
  unconcealedReadingRegions,
  userReadingRegion,
  readingRegionFor,
  scrollersOf,
} from "../readings/reading-regions.js";
import { scrollChainOf } from "../readings/scroll-containers.js";
import {
  currentLocationOrigin,
  walkOrigin,
  heldObligation,
  heldPagePlace,
  placeOf,
  stepFrom,
} from "../records/current-target.js";
import { focused } from "../dom/focus.js";
import {
  closeDraft,
  draftAnchor,
  draftsReading,
  standsOnDraft,
} from "../records/drafts.js";
import { pageSelection } from "../annotations/composing/capture.js";
import { blockAt, inPage, layoutBox } from "../readings/passages.js";
import { readingBlock } from "../readings/reading-place.js";
import { scrollIntoView } from "../readings/landing-scroll.js";
import { drawnThreadId, THREAD } from "../records/thread/selectors.js";
import { threadIn } from "../records/thread/focus.js";
import {
  NO_OPEN_THREADS,
  THREADS_OFFLINE,
  anyOpenThread,
  readThreads,
  threadList,
  threadNamed,
} from "../records/thread/state.js";
import { threadPlace } from "../records/thread/placement.js";
import {
  byRenderedOrder,
  renderedOrder,
  under,
  closestAcross,
} from "../lib/shadow-tree.js";
import { retainUserIntent } from "../dom/user-intent.js";
import { announce, notice } from "../transport/notifications.js";
import {
  beginWalk,
  listWalkPosition,
  walkPositionLabel,
} from "../records/walk-position.js";
import { savedReadingSettled } from "../dom/keyboard/bindings.js";

/** @typedef {import("../records/thread/placement.js").PlacedAt} PlacedAt
 * @typedef {Pick<ReturnType<typeof import("../records/thread/destination.js").createThreadDestinations>, "openPageThread" | "threadAtCurrentLocation">} ThreadDestinations
 * @typedef {ReturnType<typeof import("../records/drafts.js").createWritingResume>["showDraft"]} ShowDraft
 * @typedef {import("../dom/keyboard/bindings.js").Step} Step
 * @typedef {{keys: string[], placeOf: (key: string) => Element | null, drafts: Map<string, import("../../types/domain.js").Anchor>}} Stops
 */

// The walk's stops, in the page's order (records/thread/placement.js, `threadPlace`): each
// thread that stands open or holds the user's unsent words, by its id, and each comment
// the user began and hasn't sent, by its draft's context (records/drafts.js, the drafts list),
// placed at its passage or element (`savedAt`), so the walk reaches every draft
// Threads lists. A reply or a rewrite is its thread's, whose stop opens the thread, a
// resolved one included. A comment whose subject this version no longer shows stands
// after every placed stop, as a general thread does. Read from the models rather than
// from any surface that draws them, so every route into the walk steps through the
// same list.
/** @param {PlacedAt} placedAt @param {PlacedAt} savedAt @returns {Stops} */
function walkStops(placedAt, savedAt) {
  /** @type {Map<string, Element | null>} */
  const places = new Map();
  /** @type {Stops["drafts"]} */
  const drafts = new Map();
  /** @type {Set<string>} */
  const drafted = new Set();
  for (const draft of draftsReading()) {
    const anchor = draftAnchor(draft);
    const thread = anchor ? null : threadNamed(draft.name);
    if (thread) drafted.add(thread.id);
    if (anchor) drafts.set(draft.context, anchor);
  }
  for (const thread of threadList())
    if (!thread.resolved || drafted.has(thread.id))
      places.set(thread.id, threadPlace(thread, placedAt));
  for (const [context, anchor] of drafts)
    places.set(context, threadPlace({ id: context, anchor }, savedAt));
  /** @param {string} key */
  const placeOf = (key) => places.get(key) ?? null;
  return { keys: byRenderedOrder([...places.keys()], placeOf), placeOf, drafts };
}

// The stop the walk stands on. A thread's is the one the origin's current location is
// in, wherever it is drawn; its target, with the thread's card beside it, is at the
// thread, not on it (records/current-target.js, `walkOrigin`). A comment's is the one whose
// box the user stands on (records/drafts.js, `standsOnDraft`), as the walk's arrival leaves
// them; in its editor, a walk key is a letter of the comment.
/** @param {Stops} stops @param {import("../records/current-target.js").WalkOrigin | null} origin */
function currentStop({ keys, drafts }, origin) {
  for (const context of drafts.keys()) if (standsOnDraft(context)) return context;
  if (origin?.kind !== "current-location") return null;
  const id = drawnThreadId(threadIn(origin.node));
  return id !== null && keys.includes(id) ? id : null;
}

// What a position names its list: by its stops' noun where they are all of one kind,
// "Thread 2 of 5" or "Draft 1 of 2", and by both kinds where it holds threads and
// drafts, "2 of 5 threads and drafts" (records/walk-position.js, `beginWalk`).
/** @param {Stops} stops */
const listNames = ({ keys, drafts }) =>
  !drafts.size
    ? { noun: "Thread", qualifier: "" }
    : drafts.size === keys.length
      ? { noun: "Draft", qualifier: "" }
      : { noun: null, qualifier: "threads and drafts" };

// Arrive at one thread a walk chose, by its id: the one arrival both the t/T walk and
// the queue walk (queue-walk.js) make. It opens the thread at its destination: a
// declared widget outlet first, then the thread margin entry's card, then the floating
// panel's view of it (records/thread/destination.js).
//
// It answers whether the user arrived, once the thread stands open. `intent` is the
// press's, retained before any wait the caller made: newer input cancels the arrival,
// and the walk then says nothing about a thread the user is not at.
/** @param {string} id @param {Pick<ThreadDestinations, "openPageThread">} destinations
 * @param {ReturnType<typeof retainUserIntent>} intent */
async function arriveAtThread(id, { openPageThread }, intent) {
  return Boolean(await openPageThread(id, { part: "thread", intent }));
}

// t/T walk the stops in page order, coming round from either end to the other
// (`cycledRow`). A thread's stop opens the thread (`arriveAtThread`). A comment's
// opens its box beside its passage or element, holding its words, and stands the user
// on the box without putting the caret in it (records/drafts.js, `showDraft`), so the next `t`
// walks on and `c` puts the caret after the words, as `c` opens a thread's reply box
// from the thread (records/thread/landing.js). A walk that put the caret in the box would type
// its next `t` there.
//
// From anywhere but a stop, the walk steps by the page walks' one rule (`stepFrom`,
// records/current-target.js): a place on the page against each stop's place. A thread at the
// user's current location, or a stop whose place holds where they are, is where they
// are without being on it, so the press arrives there, unless what the window shows
// puts them at a stop ahead of it. A general thread has no place and stands after
// every placed stop. With no stop at all, the press says so, or that the threads can't
// be had while the server is offline (dom/keyboard/AGENTS.md, "Page grammar").
/** @param {Step} dir @param {{destinations: ThreadDestinations, placedAt: PlacedAt, savedAt: PlacedAt, showDraft: ShowDraft}} dependencies */
function stepThread(dir, { destinations, placedAt, savedAt, showDraft }) {
  const stops = walkStops(placedAt, savedAt);
  const { keys, placeOf, drafts } = stops;
  if (!keys.length) {
    notice(readThreads().phase === "offline" ? THREADS_OFFLINE : NO_OPEN_THREADS);
    return;
  }
  const origin = walkOrigin();
  const current = currentStop(stops, origin);
  const targetId =
    !current &&
    origin.kind !== "enter" &&
    destinations.threadAtCurrentLocation(origin.node);
  const atTarget = targetId && keys.includes(targetId) ? targetId : null;
  const next = current
    ? cycledRow(keys, current, dir)
    : stepFrom(keys, origin, dir, placeOf, atTarget);
  if (!next) return;
  const arrival = drafts.has(next)
    ? showDraft(next)
    : arriveAtThread(next, destinations, retainUserIntent());
  // The walk reads the current destination, so begin it once the arrival has moved
  // focus, as the queue walk does; an arrival that failed registers nothing.
  const { noun, qualifier } = listNames(stops);
  /** @returns {import("../records/walk-position.js").WalkPosition | null} */
  const position = () => {
    const now = walkStops(placedAt, savedAt);
    return listWalkPosition(now.keys, currentStop(now, currentLocationOrigin()), {
      qualifier,
    });
  };
  const ready = arrival.then((arrived) => {
    if (!arrived) return;
    // The comment's box the walk stood the user on goes, as the last thread's view does
    // when the walk opens another (records/thread/destination.js).
    if (current !== null && current !== next && drafts.has(current))
      closeDraft(current);
    announce(
      beginWalk("thread", noun, position) ??
        walkPositionLabel(noun, keys.indexOf(next) + 1, keys.length, qualifier),
    );
  });
  void ready.catch(() => {});
  return ready;
}

// Put the comment the user is on against one edge of its list. This is
// placement inside the panel, not travel to the passage the comment is about, so it
// moves only the thread scroller and keeps the card's focus. Native scroll placement
// reads the list's declared scroll-padding, its focus-ring room, from the same authority
// the t/T walk uses.
/** @param {Element | null} thread @param {ScrollLogicalPosition} edge */
export function placeThreadEdge(thread, edge) {
  scrollIntoView(thread, { behavior: scrollBehavior(), block: edge });
}

// j/k take small pixel steps; d/u move 60% of the visible reading page; Go-to's `g g`
// and `g G` take an unbounded step, which `glideTo` stops at the box's edge. All follow
// the active region and glide (dom/scrolling.js, `glideTo`). A press steps from where the
// box is headed (`scrollGoal`), so presses made while the page still moves, whether
// after another step, after a landing such as `m`'s, or after the browser's own Space
// or PageDown (`afterBrowserScroll`), add up as if each had landed. At a region's edge
// they follow its CSS scroll chain (`scrollChainOf`, `stepAlong`), stopping at the
// same task or modal boundary as native input, so a floating thread's turns, once
// spent, hand the step to the document, and a sample's to its containing page, as the
// wheel does. Space, Home/End and PageUp/Down stay the browser's own keys.
//
// They move the region the user is reading. A view the floating panel opens is that
// region when focus stands in it; a nested region keeps its own scrollport. Scrolling a
// region the user is not in reads to them as the key doing nothing, and then the
// document is somewhere else when they look back at it.
//
// The page the step measures is the visible part of the scroller's landing band.
// The document's box lends its bottom edge to the floating panel's row, and its
// scroll-padding — read exactly so by scrollToElement — is where the box already says
// how much of itself stands covered, so a reading-page step is 60% of what is left
// rather than 60% of the box, which is the answer the user wants — a step that landed
// them under the panel would be a step onto words they cannot read.
//
// Reading-page keys follow the region the user is working in (`userReadingRegion`), so
// `d` after a click in a pane scrolls that pane as PageDown does. Focus can put them in
// a panel or anchored thread beside the page. Focus on a region's
// apparatus follows its actual containing scrollport within the region while that
// box overflows; otherwise the region's reading body takes the step. The step then
// walks that box's scroll chain (`stepAlong`), where a box outside the visible band
// passes it on as a spent one does, so a floating thread scrolled off screen still
// pages its document. Neither changes which region the user is reading.
//
// With no region named the page takes the step, and a step down the page can't take goes
// to the largest region that can (`regionForStep`). A full-height workspace keeps the
// page still, or gives it only the height of a header or footer beside `main`, so on a
// fresh load the keys would otherwise run out on the page while its panes held everything
// to read. Vimium makes the same hand-off on a page whose scrolling element doesn't
// scroll, by visible area too. Of panes the same size the one with the most to scroll
// goes first, since the shorter is soon spent, and then the first in reading order, so
// the answer depends on the page rather than on which registered first.
//
// A step up chooses only where the window holds all of `main`, top and bottom
// (`mainFits`), as a workspace whose log opens at its newest entry needs: on a page that
// doesn't scroll, or one that scrolls only by a footer after `main`. Where `main` runs
// past the window, `k` at the page's top has nothing to read above it, and a log in view
// it moved would stop following its newest entry.
//
// The step names the region it chose, so a walk goes on from there, but the page stays
// ahead of it in both directions until the user acts (`chosenReadingRegion`). The page
// carries the pane, so the reader sees the text move by each step either way, and `k`
// returns the page's own scroll rather than leaving it behind a pane it can't pass. On a
// long page, a `j` at its end that moved a log leaves the next `k` to the page.
//
// Only a step the page can't take with none named chooses. Choosing ranks the regions by
// their boxes clipped to the window, which no region shows more of, and measures what a
// region shows only down to the first box smaller than the most a region has shown, so
// the regions off screen are passed over by their boxes alone.
/** @param {Element} box @param {import("../dom/geometry.js").ClipCache} clips */
const readingStep = (box, clips) => {
  const shown = shownRect(box, clips);
  const band = shown && landingBand(box);
  if (!shown || !band) return null;
  const { top, bottom } = intersect(shown, band, { y: true });
  return bottom > top ? { box, height: bottom - top } : null;
};
/** @param {ReturnType<typeof userReadingRegion>} region */
const stepStart = (region) => {
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
// Whether a box has room the way a step goes, from where it is headed.
/** @param {Element} box @param {number} amount */
const takesStep = (box, amount) => {
  const goal = scrollGoal(box);
  return amount > 0 ? !atScrollEnd(box, goal) : goal > 0;
};
// The area of the box an element shows as (`shownBox`, the box `shownRect` clips) within
// `view`, in whole pixels as the ranking counts it, or 0 where none of it is there.
/** @param {Element} element @param {import("../base/box.js").Box} view */
const areaWithin = (element, view) => {
  const within = intersect(shownBox(element), view);
  return hasArea(within)
    ? Math.round(within.right - within.left) * Math.round(within.bottom - within.top)
    : 0;
};
/** @param {number} amount */
const regionForStep = (amount) => {
  /** @type {ReturnType<typeof userReadingRegion>} */
  let most;
  let mostArea = 0;
  let mostRange = 0;
  const view = layoutWindow();
  const sized = unconcealedReadingRegions()
    .map((region) => ({ region, box: areaWithin(region.body, view) }))
    .sort((a, b) => b.box - a.box);
  for (const { region, box } of sized) {
    // A region shows no more than its box within the window, so no smaller box can.
    if (!box || box < mostArea) break;
    const { host, body } = region;
    const bounds =
      takesStep(body, amount) &&
      regionScrollBehavior(region) === "bounded" &&
      inPage(host) &&
      nativeModalAdmits(body) &&
      shownRegionBounds(region);
    if (!bounds) continue;
    // In whole pixels, so equal tracks tie whatever their rounding.
    const area =
      Math.round(bounds.right - bounds.left) * Math.round(bounds.bottom - bounds.top);
    const range = scrollLimit(body);
    const ahead = most
      ? area - mostArea || range - mostRange || renderedOrder(most.host, host)
      : 1;
    if (ahead > 0) [most, mostArea, mostRange] = [region, area, range];
  }
  return most;
};
// Whether the window holds all of `main`, top and bottom, or of the page where it has
// none.
const mainFits = () => {
  const { top, bottom } = (layoutBox() ?? pageScroller).getBoundingClientRect();
  const view = layoutWindow();
  return top >= view.top - SCROLL_SLACK && bottom <= view.bottom + SCROLL_SLACK;
};
/** @param {number} amount @param {"page" | "pixel"} unit */
const stepReading = (amount, unit) => {
  const named = userReadingRegion();
  const chosen = chosenReadingRegion();
  if (named && named.id !== chosen?.id)
    return stepAlong(stepStart(named), amount, unit);
  if (takesStep(pageScroller, amount)) return stepAlong(pageScroller, amount, unit);
  const choosing = !chosen && (amount > 0 || mainFits());
  const region = chosen ?? (choosing ? regionForStep(amount) : undefined);
  if (region && !chosen) chooseReadingRegion(region);
  stepAlong(region ? region.body : pageScroller, amount, unit);
};
// The step walks the chain from `from` to the first box that shows and can take it. A
// box that contains its overscroll, or one an open modal leaves outside, ends the walk.
// A sample's chain runs on past its document into the containing page, as the wheel's
// does, so a chain spent without either boundary passes the step on, and the
// containing page's navigation takes it up from the frame; outside a sample the notice
// goes nowhere.
/** @param {Element} from @param {number} amount @param {"page" | "pixel"} unit */
function stepAlong(from, amount, unit) {
  const clips = new Map();
  for (const box of scrollChainOf(from)) {
    if (!nativeModalAdmits(box)) return;
    if (afterBrowserScroll(box, () => stepAlong(from, amount, unit))) return;
    const step = readingStep(box, clips);
    if (step && takesStep(box, amount)) {
      glideTo(box, scrollGoal(box) + (unit === "page" ? amount * step.height : amount));
      return;
    }
    if (getComputedStyle(box).overscrollBehaviorY !== "auto") return;
  }
  sampleNotice({ type: "step", detail: { amount, unit } });
}

/** @param {{threadDestinations: ThreadDestinations, placedAt: PlacedAt, savedAt: PlacedAt, showDraft: ShowDraft}} dependencies */
export function createNavigation({ threadDestinations, placedAt, savedAt, showDraft }) {
  const currentItem = () => {
    // The place the floating panel holds while the user is in it is the same current location,
    // read without moving focus merely to paint whether its row is available.
    const at = heldPagePlace() ?? focused();
    const item = heldObligation(at);
    if (item && under(at, item)) return item;
    const thread = closestAcross(at, THREAD);
    if (thread) return thread;
    const region = readingRegionFor(at) ?? userReadingRegion();
    /** @param {Node | null | undefined} node */
    const inReading = (node) => !region || under(node ?? null, region.body);
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
    // Else the block the caret stands in, while it is in the reading region.
    const caret = userCaret()?.element;
    return (inReading(caret) && blockAt(placeOf(caret))) || readingBlock(region);
  };
  // Like page scrolling, alignment stays offered at the edge of its useful range.
  // Resolve the current reading only when invoked, not on every controls repaint.
  /** @satisfies {import("../dom/keyboard/bindings.js").Command} */
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
      scrollIntoView(item, {
        block: "start",
        behavior: scrollBehavior(),
        sideways: false,
      });
    },
  };
  const move = stepReading;

  // Travel's own page keys.
  pageCommand({
    id: "thread.walk",
    // A walk needs a visible destination, not the complete saved inventory: local
    // sends, and the drafts the document was served with, are usable destinations while
    // the first reading is still loading.
    ready: () => savedReadingSettled() || anyOpenThread() || draftsReading().length > 0,
    touch: false,
    // A walk's letter names its category; Shift reverses it. The page's walks therefore
    // share one compact, repeatable grammar.
    keys: ["t", "Shift+t"],
    routes: [
      {
        id: "thread.next",
        binding: "t",
        title: "Next thread or draft",
      },
      {
        id: "thread.previous",
        binding: "Shift+t",
        title: "Previous thread or draft",
      },
    ],
    title: "threads and drafts",
    repeat: true,
    travels: true,
    // The walk moves the user laterally: it is the surface it reaches through, rather
    // than the walk, that Escape takes off. It stands them on a thread a widget seats on
    // the page, or opens the margin's thread view, or the floating panel's, for a thread
    // with no seat, and that view's own step dismisses it, as a comment's box does.
    runKey: (binding) =>
      stepThread(binding === "t" ? 1 : -1, {
        destinations: threadDestinations,
        placedAt,
        savedAt,
        showDraft,
      }),
  });
  // A sample's spent step arrives at its frame (host/sample.js). It goes on only while the
  // user is still in that frame: one that lands after they have left was not theirs to
  // finish. The child's scripts are the page author's, like the page's own, so the
  // frame's word is trusted as a page script's would be.
  document.addEventListener("lf-sample-step", (event) => {
    const frame = event.composedPath()[0];
    if (frame instanceof Element && focused() === frame)
      stepAlong(frame, event.detail.amount, event.detail.unit);
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
    runKey: (binding) => move(binding === "d" ? 0.6 : -0.6, "page"),
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
    runKey: (binding) => move(binding === "j" ? 60 : -60, "pixel"),
  });

  // The queue walk's way onto one thread it names by id: the t/T walk's own arrival,
  // whatever list the thread is in.
  /** @param {string} id @param {string | null} message @returns {Promise<boolean>} */
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
  };
}
