// Compiled from scrolling.ts by build/typescript.mjs; edit that file.
/* Scroll positions, and whose each one is.

   A box stands where the reader chose, or where layout put it. The reader chooses with
   a wheel, a key or a scrollbar, through a Leaf landing (readings/landing-scroll.js), and through
   the browser's own navigation, such as find-in-page opening a closed disclosure onto
   its match. Layout puts a box where a clamp leaves it as content shrinks, where scroll
   anchoring adjusts it, and at the offset it kept while it did not scroll. Continuity's
   shift restore (features/version.js) undoes only layout's moves, so it asks which boxes the
   reader has chosen for since its reading (`chosenSince`).

   A scroll sequence ends with `scrollend`, whoever started it, and Chromium, Firefox and
   WebKit also end one at once where layout moves the box, by anchoring or a clamp, one
   sequence for each move (measured in Chromium 156, Firefox 157 and WebKit 27). So a
   sequence of several scroll events is a glide someone drove, and a single move is a
   choice unless layout explains it: the box's extent changed while it moved
   (`watchLayout`). A script's jump in the frame of a layout change therefore reads as
   layout's, and the reader's input aimed at the box, which continuity records itself
   (features/version.js, `inputSince`), settles those. The browser's travel into hidden content,
   as find-in-page opening a fold onto its match, fires `beforematch` first, so its end
   is a choice whatever the opening did to the layout. Opening a closed `<details>`
   fires none, so a disclosure that opens without its summary's click marks the same
   travel, for its own box and those inside it. An end that leaves the box where
   its last one did, as Firefox sends after a layout move, chose nothing. A place
   keeper's write returns the reader to a place they already had (readings/reading-place.js,
   `restorePlace`; readings/user-place.js, `returnPlace`; continuity's move of the page with its
   band), so it says where it left each box (`placeKept`), and a sequence ending there
   is the keeper's. An explicit landing counts from its start (`startScroll`), even
   when instant, since layout it caused can be announced before its sequence ends.
   A sequence can end frames after its last `scroll` event, as WebKit's do, so
   continuity takes a reading at the end too. Each sequence ends once, however many
   frames a glide writes it in (arrivals.js, `watchScrollEnds`). Like that record, this
   reads the document's own scrollers, not those inside a shadow root. */

import { cancelRender, nextFrame, sizeObserver } from "../lib/frame-pass.js";
import {
  browserScrolls,
  holdScroll,
  readScrolled,
  readerScrolls,
  scrollDrawn,
  setScroll,
  startReaderScroll,
  stopWhereItStands,
  watchOwner,
  watchScrollEnds,
} from "./arrivals.js";
import { CONTROLS, LINKS, PLAIN_PRESSES, RADIOS } from "./control-selectors.js";
import { inputs } from "../base/inputs.js";
import { reducedMotion } from "./motion.js";
import { skipped } from "../lib/shadow-tree.js";

// The browser's document scrollport. Keeping the platform's root as the one page
// scroller lets fragment links, history restoration, wheel/touch input, and browser UI
// all describe the same reading position. The chrome's views still own their nested
// scrollports; scrollerFor is the shared answer when a caller may stand in either.
const nativeScroller = document.scrollingElement;
if (!(nativeScroller instanceof HTMLElement))
  throw new Error("Leaf requires an active HTML document scrollport");
export const pageScroller = nativeScroller;

// The boxes whose sequence under way Leaf started, a landing or a glide
// (`startScroll`), how many Leaf has started in each, and the boxes whose latest scroll
// followed one of the keys the browser scrolls with, which Leaf leaves to it
// (panel/navigation.js), rather than a hand (`afterBrowserScroll`). Only the inputs that set
// the browser scrolling decide which: a pointer, a wheel or a touch, or one of those
// keys. Any other key, such as Leaf's `d`, moves nothing the browser drives, so a `d`
// pressed during PageDown leaves PageDown's scroll a key's, and a second `d` waits too.
const started = new WeakSet();
const starts = new WeakMap();
const keyScrolled = new WeakSet();
const SCROLL_KEYS = new Set([
  " ",
  "PageDown",
  "PageUp",
  "ArrowDown",
  "ArrowUp",
  "Home",
  "End",
]);
let scrollKeyLast = false;
inputs.observe((event) => {
  if (event instanceof KeyboardEvent) {
    if (SCROLL_KEYS.has(event.key)) scrollKeyLast = true;
  } else if (event.type !== "input" && event.type !== "blur") scrollKeyLast = false;
  // A key is the keyboard controller's to stand a glide down for (`landForKey`).
  if (!glideIn.size || event instanceof KeyboardEvent || !aimsScroll(event)) return;
  const path = event.composedPath();
  for (const box of glideIn.keys()) if (path.includes(box)) stopGlide(box);
});
// Whether `event` asks the browser to scroll the boxes on its path: a touch, or an input
// the browser scrolls for (`scrollsFor`).
const aimsScroll = (event) => event.type === "touchstart" || scrollsFor(event);
// Whether the browser scrolls for `event`: a wheel, or one of its scroll keys pressed
// where focus rests on no control that takes that key. A control takes keys of its own,
// as Space presses a button and an arrow picks a radio or moves a caret, and a touch may
// be a tap, so none of those says a scroll will follow; read as one, Space on a button or
// a tap on one made a keep holding the reader's place across what it changed stand down.
// A link takes Enter alone, a plain press Enter and Space, and a radio its arrows
// (control-selectors.js, `LINKS`, `PLAIN_PRESSES`, `RADIOS`), so the browser scrolls
// for the rest pressed on one: read as no scroll, PageUp on a link, a radio or a
// button, or an arrow on a button, in a log entries stream into was left to the log's
// keeper, whose writes cancelled it in Firefox.
export const scrollsFor = (event) => {
  if (event.type === "wheel") return true;
  if (!(event instanceof KeyboardEvent) || !SCROLL_KEYS.has(event.key)) return false;
  const [at] = event.composedPath();
  const control = at instanceof Element ? at.closest(CONTROLS) : null;
  if (!control || control.matches(LINKS)) return true;
  if (event.key === " ") return false;
  return control.matches(
    event.key.startsWith("Arrow") ? PLAIN_PRESSES : `${PLAIN_PRESSES}, ${RADIOS}`,
  );
};
// Where each box's last sequence ended, the boxes layout has moved since, and each box's
// extent where its layout last settled. A box is watched from its first scroll, through
// its own size and its children's, where content grows, so content that grew between
// sequences doesn't make the next one layout's.
const ended = new WeakMap();
const scrollSteps = new WeakMap();
const layoutMoved = new WeakSet();
const watchedLayout = new WeakSet();
const extents = new WeakMap();
const extentOf = (box) => [box.scrollHeight, box.clientWidth, box.clientHeight];
const changedExtent = (before, after) =>
  before?.some((value, index) => value !== after[index]);
function watchLayout(box) {
  if (watchedLayout.has(box)) return;
  watchedLayout.add(box);
  extents.set(box, extentOf(box));
  const root = box === pageScroller ? document.documentElement : box;
  const sizes = new WeakMap();
  // Observe skipped children too, so revealing them supplies their first reading.
  const measure = (node) =>
    skipped(node) ? null : [node.clientWidth, node.clientHeight, node.scrollHeight];
  const observer = sizeObserver(
    (entries) => {
      let changed = false;
      for (const { target } of entries) {
        const next = measure(target);
        const before = sizes.get(target);
        sizes.set(target, next);
        if (next && (!before || before.some((value, index) => value !== next[index])))
          changed = true;
      }
      if (changed) {
        if (ended.has(box) && box.scrollTop !== ended.get(box)) layoutMoved.add(box);
        else extents.set(box, extentOf(box));
      }
    },
    { counted: false },
  );
  const observe = (node) => {
    sizes.set(node, measure(node));
    observer.observe(node);
  };
  observe(root);
  if (box !== pageScroller) {
    for (const child of box.children) observe(child);
    const mutation = new MutationObserver((entries) => {
      for (const entry of entries) {
        for (const node of entry.addedNodes) if (node instanceof Element) observe(node);
        for (const node of entry.removedNodes)
          if (node instanceof Element) observer.unobserve(node);
      }
    });
    mutation.observe(box, { childList: true });
    watchOwner(box, {
      disconnect() {
        observer.disconnect();
        mutation.disconnect();
        watchedLayout.delete(box);
      },
    });
  }
}
// The page is watched from the start, so where it stands now counts as its last end.
watchLayout(pageScroller);
ended.set(pageScroller, pageScroller.scrollTop);

// A new landing or return takes the boxes from a scroll the browser drives, such as a
// wheel's or PageDown's, with the write that stops it (arrivals.js,
// `stopWhereItStands`), since no script can say where that scroll goes. A glide of
// Leaf's goes on: a landing measures from where it is headed and takes it over
// (readings/landing-scroll.js, `readingBandMoves`), so `t` pressed again while the walk still
// moves lands as typed slowly, where stopping the glide left the page where it stood
// whenever the destination was already in view there; a return stops it itself.
// Chromium can deliver one last compositor scroll after that cancellation, so the
// caller reads geometry and places the new destination once the stop is drawn
// (arrivals.js, `scrollDrawn`).
export function stopBrowserScroll(boxes) {
  const stopped = [...boxes].filter(browserScrolls);
  for (const box of stopped) stopWhereItStands(box);
  return stopped.length ? scrollDrawn() : null;
}

let choices = 0;
const chosen = new WeakMap();
const kept = new WeakMap();
// How many choices the reader has made so far, for a keeper to note with a reading.
export const scrollChoices = () => choices;
// Whether the reader chose where `box` stands after the `count`th choice.
export const chosenSince = (box, count) => (chosen.get(box) ?? 0) > count;
const chooseScroll = (box) => chosen.set(box, ++choices);
// How many moves Leaf has started in `box` (`startScroll`).
export const scrollStarts = (box) => starts.get(box) ?? 0;
// Record an explicit landing or a glide before native scroll events: an instant move
// can coincide with layout, and a new gesture can interrupt a glide before its first
// frame.
export function startScroll(box) {
  started.add(box);
  starts.set(box, (starts.get(box) ?? 0) + 1);
  chooseScroll(box);
}
// The browser's travel into hidden content, until the sequence it starts has ended,
// which is before the second frame after.
let travel = null;
document.addEventListener(
  "beforematch",
  () => {
    const mark = (travel = {});
    nextFrame(() =>
      nextFrame(() => {
        if (travel === mark) travel = null;
      }),
    );
  },
  { capture: true },
);
// Opening a closed `<details>` onto its match fires no `beforematch`. A disclosure the
// reader opens activates its summary, which dispatches a click first; one that opens
// without that, as find-in-page opens one, travels into it, until the sequence the
// travel starts has ended. That travel counts only for the disclosure and the boxes
// inside it, since Leaf itself opens disclosures too, carrying one open across a
// revision (records/carry.js) while layout moves the page around it. The opening is read from
// its `open` attribute, whose record arrives before the next rendering update, rather
// than from `toggle`, which follows in a task of its own: on a busy main thread the
// rendering update that ends the travel's sequence can run first, and that end would
// read as layout's, so continuity would put back the place the travel left.
let activated = null;
let opened = null;
document.addEventListener(
  "click",
  ({ target }) => {
    const summary = target instanceof Element ? target.closest("summary") : null;
    const disclosure = summary?.parentElement;
    if (disclosure instanceof HTMLDetailsElement && !disclosure.open)
      activated = disclosure;
  },
  { capture: true },
);
new MutationObserver((records) => {
  for (const { target, oldValue } of records) {
    if (!(target instanceof HTMLDetailsElement) || !target.open || oldValue !== null)
      continue;
    if (activated === target) {
      activated = null;
      continue;
    }
    opened = target;
    nextFrame(() =>
      nextFrame(() => {
        if (opened === target) opened = null;
      }),
    );
  }
}).observe(document, {
  subtree: true,
  attributeFilter: ["open"],
  attributeOldValue: true,
});
const eventScroller = (target) =>
  target === document ? pageScroller : target instanceof Element ? target : null;
document.addEventListener(
  "scroll",
  ({ target }) => {
    const box = eventScroller(target);
    if (!box) return;
    if (skipped(box)) return;
    watchLayout(box);
    scrollSteps.set(box, (scrollSteps.get(box) ?? 0) + 1);
    if (scrollKeyLast) keyScrolled.add(box);
    else keyScrolled.delete(box);
  },
  {
    capture: true,
    passive: true,
  },
);
// The scroll an input sets off in `box`, the one box it moves (`scrollsFor`;
// readings/scroll-containers.js, `inputScroller`), is the reader's from the input: the browser
// applies it a frame or more later, Firefox each wheel's and key's, and the box's first
// scroll event comes later still. Read from that event, it was nobody's meanwhile, so a
// step pressed just after PageDown didn't wait for it (`afterBrowserScroll`), and a
// keeper that wrote a log's end as entries streamed in took the box from a wheel or
// PageUp aimed up it, every time in Firefox. So the input starts the box's sequence
// (arrivals.js, `startReaderScroll`), says whether a key set it going, as each of its
// scroll events does, and records which way it heads the box and where it found it
// (`readerScroll`).
const UP_KEYS = new Set(["PageUp", "ArrowUp", "Home"]);
// The ways an input heads a box, each ranking above the one before: a scroll heads the
// way the furthest-ranked of its inputs does.
const HEADINGS = ["down", "across", "up"];

const asked = new WeakMap();
export function aimScroll(box, event) {
  if (scrollKeyLast) keyScrolled.add(box);
  else keyScrolled.delete(box);
  const was = readerScrolls(box) ? asked.get(box) : undefined;
  const { top } = startReaderScroll(box);
  // A wheel heads down or up where it moves that way more than across, as a trackpad's
  // scroll down does though it drifts across a little. The keeper's write of the end
  // then costs the reader that drift, and holding the end for it would leave a log
  // entries stream into unfollowed through every such scroll.
  let heads = "across";
  if (event instanceof WheelEvent) {
    const across = Math.abs(event.deltaX);
    if (event.deltaY > across) heads = "down";
    else if (-event.deltaY > across) heads = "up";
  } else if (event instanceof KeyboardEvent) {
    const shifted = event.key === " " && event.shiftKey;
    heads = UP_KEYS.has(event.key) || shifted ? "up" : "down";
  }
  if (was && HEADINGS.indexOf(was.heads) >= HEADINGS.indexOf(heads)) return;
  const fromEnd = scrollLimit(box) - top;
  const leaf = starts.get(box) ?? 0;
  asked.set(box, was ? { ...was, heads } : { heads, top, fromEnd, starts: leaf });
}
// The scroll the reader's input has asked the browser for in `box` while it runs
// (`aimScroll`), though the box may not have moved yet: which way it heads the box, down
// to its end, up, which takes the reader from it, or across, which leaves them at it;
// where its first input found the box (arrivals.js, `startReaderScroll`), from its top
// and from its end; and how many moves Leaf had started in the box then
// (`startScroll`). Null where no such scroll runs. A writer that would put the box at
// its end asks this first, as its keeper does (`followEnd`): its write would cancel a
// scroll up or across, a wheel across a log's long lines as surely as one up it, and
// takes a reader heading down where they were going.
export const readerScroll = (box) => (readerScrolls(box) && asked.get(box)) || null;
// Whether `box` has moved toward its lower end (`down`) or its upper one since its last
// scroll sequence ended, layout aside. A wheel's sequence ends only when its gesture
// does, and the browser may scroll before the page hears the wheel, as it does for
// macOS's precise wheels, so the event that takes a box to its end finds it there.
export function carriedToward(box, down) {
  const from = ended.get(box);
  if (from === undefined || layoutMoved.has(box)) return false;
  return down
    ? box.scrollTop > from + SCROLL_SLACK
    : box.scrollTop < from - SCROLL_SLACK;
}
export function placeKept(...boxes) {
  for (const box of boxes) kept.set(box, box.scrollTop);
}
watchScrollEnds((box) => {
  if (box.getRootNode() !== document) return;
  const leafStarted = started.delete(box);
  if (skipped(box)) {
    scrollSteps.delete(box);
    layoutMoved.delete(box);
    return;
  }
  watchLayout(box);
  const extent = extentOf(box);
  const repeated = (scrollSteps.get(box) ?? 0) > 1;
  scrollSteps.delete(box);
  const chosenHere =
    leafStarted ||
    repeated ||
    travel !== null ||
    opened?.contains(box) ||
    (ended.get(box) !== box.scrollTop &&
      !layoutMoved.has(box) &&
      !changedExtent(extents.get(box), extent));
  if (chosenHere && kept.get(box) !== box.scrollTop) chooseScroll(box);
  ended.set(box, box.scrollTop);
  layoutMoved.delete(box);
  extents.set(box, extent);
  kept.delete(box);
});

// Boxes whose content is drawn away from where its layout stands it. A stream a send
// or news joins (box-motion.js) draws a scroller's content where it stood, below where
// its layout now stands it, and the browser counts that drawing in the box's scroll
// height while the content rides (`contentRides`, false when the ride ends). Meanwhile the box's height
// is read from its layout each time it is asked, so its end stays where its layout puts
// it, content arriving mid-ride included, and a landing at the end doesn't chase the
// ride.
const riding = new WeakSet();
export const contentRides = (box, rides) =>
  rides ? riding.add(box) : riding.delete(box);
// A box's scroll height as its layout gives it: from where its children stand, which
// offsets read without any transform, and what follows them in its flow, its `::after`
// and its own end padding. A child placed against something other than the box leaves
// the browser's reading. It is the height of what the box holds, so a box taller than
// its content reads its content's height.
export function laidOutHeight(box) {
  let end = 0;
  for (const child of box.children) {
    if (!child.checkVisibility()) continue;
    if (!(child instanceof HTMLElement) || child.offsetParent !== box)
      return box.scrollHeight;
    end = Math.max(
      end,
      child.offsetTop +
        child.offsetHeight +
        Number.parseFloat(getComputedStyle(child).marginBottom),
    );
  }
  const after = getComputedStyle(box, "::after");
  const tail =
    after.content === "none" ||
    after.position === "absolute" ||
    after.position === "fixed"
      ? 0
      : Number.parseFloat(after.blockSize) || 0;
  const padding = Number.parseFloat(getComputedStyle(box).paddingBottom);
  return Math.min(box.scrollHeight, end + tail + padding);
}
// The furthest a box scrolls down: its scroll height less what its scrollport shows.
export const scrollLimit = (box) =>
  Math.max(
    0,
    (riding.has(box) ? laidOutHeight(box) : box.scrollHeight) - box.clientHeight,
  );

// How far short of a scroll edge a box still stands at it: fractional layout and scaled
// displays leave the browser a pixel short of where a scroll was aimed.
export const SCROLL_SLACK = 2;
// The end is a reading destination, rather than the pixel offset it occupies before
// a box is resized. `top` asks the same of a position the box is headed to.
export const atScrollEnd = (box, top = box.scrollTop) =>
  scrollLimit(box) - top <= SCROLL_SLACK;
// A glide under way to the end takes the box to the end as it now stands: a move there,
// instant or not, leaves a glide already headed there alone and turns one whose end has
// moved toward the new end. Owners that keep a box at its end, such as a card's keeper
// and a send's landing (`followEnd`, reply-landing.js), move it there at every fit, and
// a glide following an answer into sight (thread-card.js, `#fitAnswer`) runs through
// those fits.
export const scrollToEnd = (box, behavior = "instant") => {
  const glide = holding(box);
  if (glide?.end && glide.goal === scrollLimit(box)) return;
  if (glides(box, behavior) || glide?.end) return glideTo(box, scrollLimit(box));
  stopGlide(box);
  setScroll(box, { top: scrollLimit(box), behavior: "instant" });
};
// Whether a move asked for with `behavior` glides: a smooth one, or an `auto` one in a
// box whose own `scroll-behavior` asks for smooth motion, which the browser would
// otherwise answer with its own slow smooth scroll.
export const glides = (box, behavior) =>
  behavior === "smooth" ||
  (behavior === "auto" && getComputedStyle(box).scrollBehavior === "smooth");

// Apply a relative movement to the scroller the caller resolved. Keeping the box explicit
// lets document reading continuity and anchor travel share the operation without either
// owning the other's default destination. A move of less than a pixel is none: written,
// it would still stop a smooth scroll under way in the box.
//
// A box stores a whole-pixel offset, rounding a fractional one (Chromium to the nearest,
// WebKit down: measured in both, at device pixel ratios 1 and 2), and words stand at
// fractions of a pixel. So an instant move lands less than a pixel off its aim,
// and the box remembers its aim while it stands where the move left it (`aimedTop`).
// A place read there, and a keeper's next correction, start from the aim: started
// from where the box landed, each move's rounding would add to the last, and a line
// would creep across the screen revision by revision, or frame by frame of a fold.
const aims = new WeakMap();
export const moveScrollerBy = (box, top) => {
  const aim = box.scrollTop + top;
  setScroll(box, { top: aim, behavior: "instant" });
  if (Math.abs(aim - box.scrollTop) < 1) aims.set(box, { aim, at: box.scrollTop });
  else aims.delete(box);
};
// Where Leaf last aimed `box`, while it stands where that move left it, else its offset.
// A move that landed a pixel or more off was cut off by the box's range, and names no
// position the box stands at.
export const aimedTop = (box) => {
  const kept = aims.get(box);
  return kept?.at === box.scrollTop ? kept.aim : box.scrollTop;
};

// How much of a move a box can make from where it stands, or from `from`: a box at its
// end moves no further, whatever it is asked.
export const reachable = (box, top, from = box.scrollTop) =>
  Math.max(-from, Math.min(scrollLimit(box) - from, top));

// A glide moves a box to a goal at the pace of the browser's own paging keys, and every
// smooth vertical motion Leaf makes is one: the reading-page keys (panel/navigation.js,
// `stepAlong`), the go-to sequence's edges, and every landing (readings/landing-scroll.js), such
// as the ones `m`, `t`, a link and Back set off. Native paging is a quick glide — PageDown covers a
// page in ~150ms in Chromium and Firefox, and Space and the arrows ride the same
// animator — but JS cannot ask for that animator. A script's smooth scroll is slower by
// design and has no dial: Chromium lengthens it with the distance (~450ms for a page,
// ~850ms for three), and Firefox's spring settles in ~550ms, either one past the 300ms
// that motion the user waits on may take (browser/AGENTS.md). So the runtime drives
// the glide itself, as keyboard-scrolling extensions such as Vimium do: SCROLL_MS of
// easing out, each write `instant` rather than `auto` since a page is free to set
// `scroll-behavior: smooth` on the box it scrolls and a glide built from smooth writes
// would never land; a move asked for as `auto` in such a box glides (`glides`). A landing moves each box it scrolls
// with a glide of its own, all in step. Under reduced motion the glide is a jump, the
// answer the rest of the runtime's motion already gives (scrollBehavior()).
//
// Leaf's keys pressed while the page still moves add up as if each motion had landed,
// as every engine's paging keys do with their own presses in quick succession. A step
// measures from where the box is headed (`scrollGoal`), the goal of the glide under way,
// and a new glide in a box takes over the one there, so `m u` typed quickly ends where
// it ends typed slowly. A key the browser answers, Space or PageDown, scrolls the box
// to a destination no script can read, so a step pressed during that scroll waits for
// it to land and moves on from there (`afterBrowserScroll`). A scroll the user's hand
// drives, a wheel's or a touch's momentum, has no destination, so a step takes the box
// from it at once, as the browser's own keys do, and so does a landing, whose
// destination is a place rather than a distance; either moves on from wherever that
// motion has brought the box. A glide stands down when the reader aims a scroll at its
// box (`aimsScroll`), even one that moves nothing: a wheel or a touch takes the box
// where it stands, and a key the browser scrolls for lands the glide first
// (`landForKey`), so PageDown pressed as `d` sets off pages on from where `d` lands, as
// typed slowly, and Home takes the page back to the top though `d` hasn't moved it.
// Stopped where it stood, the glide left PageDown paging from the page mid-way. It
// stands down too the moment the box moves under any other hand, such as a scrollbar's
// drag, and a return takes the box from it (records/history.js). A clamp's move is no hand's, as
// the box's end comes up past where the glide put it, so the glide goes on from there
// (`holding`). A landing's glide asks the landing at each frame where the box now goes,
// so a destination layout moves still lands where the landing puts it (`aimed`). A
// placement that glides the box on past that destination, as a card opening under its
// passage does to make its room, reads its distance again at each frame from there
// (`glideBy`), until the next placement or landing takes the glide.
//
// Scroll anchoring stays off in a box while a glide moves it (`holdBox`), so the glide
// is the one thing moving the box besides a clamp and a hand. Content that grows or
// shrinks above what the reader sees then moves under the moving box, and a landing's
// glide finds its destination where that left it at the next frame. With anchoring on,
// a glide had to tell anchoring's move from a hand's by how far the box's scroll height
// changed, which two changes partly cancelling defeat: a second step pressed on the
// merge film at phone width redraws the film's parts and the steps by different
// amounts, and the glide took anchoring's move for a hand's and stopped with the film
// out of view. A glide toward a distance, as `d`'s, lands at the same offset either way.
// browser/AGENTS.md ("What the reader reads stays put") states this exception to
// keeping anchoring on.
const SCROLL_MS = 140;

// The glide under way in each box, which holds the box's scroll sequence open from its
// press to its end, so every frame it writes makes one scroll (arrivals.js,
// `holdScroll`).
const glideIn = new Map();
// Land every glide under way at its goal at once, for a key's work that measures the
// page where it stands and can't ask where the glides are headed: the browser's scroll
// for a key such as PageDown and its focus navigation for Tab (`landForKey`), a
// placement Floating UI solves, as the comment box's beside its target
// (annotations/composing/surface.js), and the Go-to map, which labels only a still scene
// (panel/page-keys/go-to-sequence.js). Landed first, that work reads the page as the same keys
// typed slowly leave it. What Leaf reads and moves itself asks where the glides land
// instead, the user's place (readings/scroll-containers.js, `seenAhead`) and its reveals
// (readings/landing-scroll.js, `readingBandMoves`), because a box the page carries by anchoring,
// as a thread card, takes a scroll only at the next frame: with every key landing the
// glides first, the card a walk had focused read as off screen, and `c` or `d` pressed
// as `t` set off let go of it. A glide a hand has taken the box from leaves it where the
// hand did.
export const landGlides = () => {
  for (const box of [...glideIn.keys()]) landGlide(box);
};
// The glides a key the browser answers would act on, landed before it does: every one
// for Tab, and those on its path for a key the browser scrolls for (`scrollsFor`). The
// keyboard controller asks once its let-go has read where they were headed, since
// landed first, a card a walk had focused would read as off screen (above).
export function landForKey(event) {
  if (!glideIn.size) return;
  if (event.key === "Tab") return landGlides();
  if (!scrollsFor(event)) return;
  const path = event.composedPath();
  for (const box of [...glideIn.keys()]) {
    if (!path.includes(box)) continue;
    landGlide(box);
    // The landing's write reads as the box placed, which hid the scroll the key has
    // just asked the browser for (`aimScroll`) from the next step, so `d` pressed after
    // PageDown glided against it rather than waiting for it (`afterBrowserScroll`).
    if (readerScrolls(box)) startReaderScroll(box);
  }
}
function landGlide(box) {
  const glide = holding(box);
  if (glide) setScroll(box, { top: aimed(box, glide), behavior: "instant" });
  stopGlide(box);
}
// A spatial command takes the page where it is now, so it stops a glide in the box even
// where it moves nothing itself. A glide stops itself `landed` where its last write left
// the box where it stood (arrivals.js, `holdScroll`).
export function stopGlide(box, landed = false) {
  const glide = glideIn.get(box);
  if (!glide) return;
  cancelRender(glide.raf);
  glideIn.delete(box);
  glide.release(landed);
}
// A glide's claim on its box: it holds while the box stands where the glide last wrote
// it, or where a clamp has moved it since, back to the end its scroll height gives once
// that end no longer reaches where the glide put it. Any other move is a hand's, such
// as the browser's scroll to an element a script focuses, since anchoring moves no box a
// glide holds (`holdBox`). A hand's scroll back to exactly the end a shrink left in the
// frame of the shrink reads as the clamp's. The tick asks
// before every write, and a press asks the same question before trusting the goal —
// the user can take the box between frames, and a press landing in that gap otherwise
// measures from a goal the box has already left. A glide taking over the browser's
// motion holds the box through whatever that motion does until the glide's own write
// first moves it (`glideTo`).
const holding = (box) => {
  const glide = glideIn.get(box);
  if (!glide || glide.wrote === null) return glide ?? null;
  const moved = box.scrollTop - glide.wrote;
  const end = box.scrollHeight - box.clientHeight;
  const clamped = moved < 0 && Math.abs(box.scrollTop - end) <= 1;
  return Math.abs(moved) <= 1 || clamped ? glide : null;
};
// What a glide holds in its box from its press to its end: the box's scroll sequence
// (arrivals.js, `holdScroll`), and scroll anchoring off (see the header). An animation
// holds `overflow-anchor`, as box-motion.js holds it for a ride, so the hold writes
// nothing to the author's markup and ends with the glide.
function holdBox(box) {
  const scroll = holdScroll(box);
  const none = { overflowAnchor: "none" };
  const anchoring = box.animate([none, none], {
    duration: SCROLL_MS,
    iterations: Infinity,
  });
  // Cancelling is the release, which rejects `finished`.
  anchoring.finished.catch(() => {});
  return (landed) => {
    anchoring.cancel();
    scroll(landed);
  };
}
// Whether a glide of Leaf's holds `box`, though it may stand at its goal.
export const gliding = (box) => holding(box) !== null;
// Where `box` is headed: the goal of the glide holding it, else where it stands.
export const scrollGoal = (box) =>
  Math.max(0, Math.min(scrollLimit(box), holding(box)?.goal ?? box.scrollTop));
// Read `read` with each of `boxes` that a glide is moving at its goal, as the page will
// stand once the glides under way land, though none has (arrivals.js, `readScrolled`).
// Only a box a glide holds is written, so no scroll the browser drives is stopped and
// the write's events fold into those the glide sends every frame.
export const whereGlidesLand = (boxes, read) =>
  readScrolled(
    [...boxes].flatMap((box) => {
      const goal = scrollGoal(box);
      return holding(box) && goal !== box.scrollTop ? [[box, goal]] : [];
    }),
    read,
  );
// Whether `box` stands at its end with no glide taking it away. A glide a press has just
// started may not have moved the box yet, since its first frame can write where the box
// already stands. A keeper that read that box as following its end would put it back
// there and stop the glide, and the press would do nothing.
const followsEnd = (box) => atScrollEnd(box) && atScrollEnd(box, scrollGoal(box));
// Run `then` once the scroll a key has the browser drive in `box`, as Space's and
// PageDown's are, has ended, and say whether it waits. A step pressed while others wait
// on the box joins them, so they run in the order pressed, and none of them runs if Leaf
// moves the box meanwhile.
const waiting = new WeakMap();
export function afterBrowserScroll(box, then) {
  const queued = waiting.get(box);
  if (queued) {
    queued.steps.push(then);
    return true;
  }
  if (!keyScrolled.has(box) || !browserScrolls(box)) return false;
  const wait = { starts: starts.get(box) ?? 0, steps: [then] };
  waiting.set(box, wait);
  const stop = watchScrollEnds((ended) => {
    if (ended !== box) return;
    stop();
    waiting.delete(box);
    if ((starts.get(box) ?? 0) === wait.starts) for (const step of wait.steps) step();
  });
  return true;
}
// A glide's goal as its landing and its placement now read it. Its base is where a
// landing puts the box from the page as it stands, with its destination where layout has
// moved it, its alignment and its band, or the offset a glide toward a distance asked
// for; the base stays where it was while the landing no longer finds its destination.
// The landing reads the page with the box at the base, where its own destination puts
// it, so a nearest landing doesn't take a placement's distance for its own. A
// placement's distance (`glideBy`), read with the box at the base, takes the goal on
// from there; once its placement has ended it asks nothing more. The glide asks at each
// frame and as a key lands it. Anything else that reads the goal between frames, as a
// step pressed on does, reads the last frame's.
function aimed(box, glide) {
  glide.goal = goalAt(box, glide.base);
  const top = glide.aim?.();
  if (top !== null && top !== undefined) glide.base = goalAt(box, top);
  const from = goalAt(box, glide.base);
  const further = glide.by ? readScrolled([[box, from]], glide.by) : 0;
  if (further === null) glide.by = null;
  glide.goal = goalAt(box, from + (further ?? 0));
  return glide.goal;
}
// Give the glide under way in `box`, where one holds it, to the landing whose `aim` says
// where the box now goes, as a landing takes every box that scrolls its destination
// (readings/landing-scroll.js, `scrollIntoView`). The landing's destination is the whole goal.
export function steerGlide(box, aim) {
  const glide = holding(box);
  if (!glide) return;
  glide.aim = aim;
  glide.by = null;
}
// Glide `box` on by the distance `by` reads with the box at the glide's base, read again
// at each frame (`aimed`), as a card makes its room under or over its passage. It takes
// the place of any placement before it in the glide under way, and with none under way
// glides from where the box stands, where `by`, read there, asks for a move. `by`
// returns null once its placement has ended, as when its card closes.
export function glideBy(box, by) {
  if (!holding(box)) {
    const further = by();
    if (!further) return;
    const base = goalAt(box, box.scrollTop);
    glideTo(box, box.scrollTop + further);
    const started = holding(box);
    if (started) started.base = base;
  }
  const glide = holding(box);
  if (!glide) return;
  glide.by = by;
  aimed(box, glide);
}
// A glide's goal for `top`, clamped to the box and at whole pixels (`glideTo`).
const goalAt = (box, top) => {
  const limit = scrollLimit(box);
  return top >= limit ? limit : Math.max(0, Math.min(limit, Math.round(top)));
};
// The goal is clamped here, so a step pressed on at the foot banks no debt for u to press
// back through, and an edge may be asked for as the height it cannot exceed. The goal and
// every write are whole pixels, where the box stands, since a write within a pixel of
// where the box stands moves nothing (arrivals.js, `setScroll`): a fractional goal would
// leave the box on whichever pixel the glide's last frame reached, and a step back from
// there, such as `u` after `d`, would stop a pixel short of the edge. A goal at the end
// stays the end, which `scrollToEnd` and a glide's `end` compare with `scrollLimit`
// exactly. Motion the
// browser drives in the box at the press, or that the glide this replaces had yet to
// take, is this glide's to take over, and stops where the box stands. Otherwise the
// glide holds the box from the press, and a hand that moves it before the glide's first
// frame wins. A glide with nothing to move or take over is none.
//
// Each frame covers the eased share of the way left, from where the glide last had the
// box before the box rounded it to a pixel, so a short glide moves from its first
// frames. Where layout has moved the box since, the glide goes on from where layout
// left it, and still lands on time. Until a glide taking over the browser's motion has
// moved the box, it eases from wherever that motion has taken the box, read at each
// frame rather than at the press: Firefox's smooth scroll runs on ahead of a busy page,
// whose next frame is the first to say where the stop left the box. A landing passes
// `aim`, which reads where it now puts the box, and its glide heads there (`aimed`).
export function glideTo(box, top, aim = null) {
  const replaced = glideIn.get(box);
  const takesOver = replaced ? replaced.wrote === null : browserScrolls(box);
  const goal = goalAt(box, top);
  if (!replaced && !takesOver && Math.abs(goal - box.scrollTop) < 0.5) return;
  startScroll(box);
  if (takesOver) stopWhereItStands(box);
  if (reducedMotion()) {
    stopGlide(box);
    setScroll(box, { top: goal, behavior: "instant" });
    return;
  }
  cancelRender(replaced?.raf);
  const t0 = performance.now();
  // Where the glide has the box, and how far through the glide its last frame was.
  let at = box.scrollTop;
  let was = 0;
  const tick = (now) => {
    const current = holding(box);
    if (!current) {
      stopGlide(box); // the box moved under another hand; theirs wins
      return;
    }
    if (reducedMotion()) {
      setScroll(box, { top: aimed(box, current), behavior: "instant" });
      stopGlide(box);
      return;
    }
    if (current.wrote === null) [at, was] = [box.scrollTop, 0];
    else if (box.scrollTop !== current.wrote) at = box.scrollTop;
    const goal = aimed(box, current);
    // Floored as well as capped: a rAF timestamp is its frame's start, which can precede
    // the press that scheduled the tick, and an unfloored t walks the ease out past the
    // start — to a write the box clamps, which the next tick then read as another hand.
    const t = Math.max(was, Math.min(1, (now - t0) / SCROLL_MS));
    at = goal - (goal - at) * ((1 - t) / (1 - was)) ** 3;
    was = t;
    const from = box.scrollTop;
    setScroll(box, { top: Math.round(at), behavior: "instant" });
    // Where the write left the box, not what it asked for: the box clamps at its ends
    // and snaps to pixels, and the claim the next tick tests is about the box.
    if (current.wrote !== null || box.scrollTop !== from) current.wrote = box.scrollTop;
    if (t < 1) current.raf = nextFrame(tick);
    else stopGlide(box, box.scrollTop === from);
  };
  glideIn.set(box, {
    goal,
    base: goal,
    end: goal === scrollLimit(box),
    wrote: takesOver ? null : box.scrollTop,
    aim,
    by: null,
    raf: nextFrame(tick),
    release: replaced?.release ?? holdBox(box),
  });
}

// Watch the size of a box and of each child it holds, as children come and go: what
// changes a scroller's room, its end or what it holds.
function watchHeld(box, changed) {
  const observer = sizeObserver(changed);
  observer.observe(box);
  for (const child of box.children) observer.observe(child);
  const children = new MutationObserver((records) => {
    for (const { addedNodes, removedNodes } of records) {
      for (const node of addedNodes)
        if (node instanceof Element) observer.observe(node);
      for (const node of removedNodes)
        if (node instanceof Element) observer.unobserve(node);
    }
  });
  children.observe(box, { childList: true });
  return () => {
    observer.disconnect();
    children.disconnect();
  };
}

// A box standing on its foot beside a field that writes into it, as a thread's view in
// the panel stands on its field, keeps what stands at its foot as the field takes room
// from it or gives it back: the box gives way at its top, so the message the user is
// answering stays beside their words. A reading in which what the box holds changed size
// too keeps nothing, leaving that change to the code that places it, a reply drawn or a
// send. Where the foot stood is read at each of the box's scrolls and readings, before
// the next change of its room. Read when that change is answered, by a keystroke's
// handler, it was read too late wherever the room had already changed, which Firefox
// showed for a draft from another tab or a resized window. The exception is the clamp a
// growth makes at the box's end, whose scroll can arrive before the reading that answers
// the growth. While a scroll the reader's input asked of the box runs (arrivals.js,
// `readerScrolls`), the box owes the move, and makes it from wherever that scroll took
// the box once it ends: made at once, it cancelled the scroll in Firefox, which applies
// a wheel's a frame or more after the wheel. A scroll that took the box to an edge, as
// Home takes it to its top, leaves the reader there, and a move Leaf starts in the box
// meanwhile (`startScroll`), as `g g` does, takes it somewhere of its own: either
// cancels the debt, which paid after it took the reader back down from the top.
export function keepFoot(box) {
  let foot = null;
  // The move the box owes, and how many moves Leaf had started in it when it began to.
  let owed = null;
  const stopWatching = watchHeld(box, (entries) => {
    const room = box.clientHeight;
    if (foot && room !== foot.room && entries.every(({ target }) => target === box)) {
      const by = foot.top + foot.room - room - box.scrollTop;
      if (readerScrolls(box))
        owed = {
          by: (owed?.by ?? 0) + by,
          starts: owed?.starts ?? starts.get(box) ?? 0,
        };
      else moveScrollerBy(box, by);
    }
    foot = { room, top: box.scrollTop };
  });
  const stopEnds = watchScrollEnds((ended) => {
    if (ended !== box || !owed) return;
    const { by, starts: since } = owed;
    owed = null;
    const atEdge = box.scrollTop <= SCROLL_SLACK || atScrollEnd(box);
    if (!atEdge && (starts.get(box) ?? 0) === since) moveScrollerBy(box, by);
    foot = { room: box.clientHeight, top: box.scrollTop };
  });
  const scrolled = () => {
    if (
      !foot ||
      (box.clientHeight > foot.room && box.scrollTop < foot.top && atScrollEnd(box))
    )
      return;
    foot.top = box.scrollTop;
  };
  box.addEventListener("scroll", scrolled, { passive: true });
  return () => {
    stopWatching();
    stopEnds();
    box.removeEventListener("scroll", scrolled);
  };
}

// A box that follows its end, as a margin card's transcript and a block bounded at its
// end (readings/bounds.js) do, keeps a reader who stands at its end there through whatever
// changes its size or what it holds: its room, as the reply box beside a card's
// transcript takes height or gives it back, or the card refits; an entry drawn at its
// end; an entry growing after it is drawn, as a picture in it loads. A reader who
// scrolled back keeps their offset. Whether the reader stands at the end is read at each
// scroll, against the end as the box stood after its last change, since by the time a
// change is seen its end has already moved past them, and a scroll whose event arrives
// between the change and its size reading reached the end the reader saw. A box moved
// back from where that reading stood it, or headed back by a glide that has yet to move
// it, as a press of u starts one up a log a stream feeds, stays where it was sent: a
// keeper that read only the box's offset put that log back at its end and stopped the
// glide, so the press did nothing. A glide headed to the end stands the reader there
// from its start, as a thread's glide to follow an answer does (thread-card.js,
// `#fitAnswer`): read from the offset, a picture loading under the glide left the
// reader short of the new end. A wheel or key heading the box up, or across a log's
// long lines, takes it from the keeper at the input (`readerScroll`): the browser applies
// that scroll a frame or more later, Firefox each wheel's and key's, and the keeper's
// write of the end in between cancelled every one, a horizontal wheel's too. So the
// keeper writes nothing until that scroll ends, and then, at its first reading of the
// drawn box, puts a reader who stood at the end and whom the scroll left there at the
// end that moved meanwhile, as an input a handler prevented leaves them; a reader the
// scroll took away stays where it took them, and so does one Leaf moved meanwhile, as
// `g g` does. Layout moves the box meanwhile too, as a log emptied and refilled is
// clamped to its top, and no reading tells its moves from the reader's: a reading
// before the scroll's own event can find the box already moved. So the input says.
// Across, the reader moves the box up or down by nothing, so every such move is
// layout's. Up, they stayed where the box stands where the input found it, from its top
// or, where layout carried it up with entries a log lost, from its end. A reader
// heading down still stands at the end, and the keeper's write takes them where they
// were going, so a log a reader wheels down at its end keeps following its entries
// through the wheel. Layout may carry the box the other way in the change itself, as
// Chromium's scroll anchoring did by 58px as a shorter window shrank a card's
// transcript, and that reader still stands at the end. A box the browser doesn't draw,
// as in a hidden tab or a shut disclosure, is read only once it is drawn again: its
// layout says nothing meanwhile of where its reader stands, and reading it makes the
// browser lay out what it skips (readings/bounds.js). A change that
// leaves the end where it stood asks nothing, and one that leaves the reader at the new
// end writes nothing, since no scroll write that moves nothing is made (arrivals.js,
// `setScroll`): in Firefox, a card that put its transcript back at an end it already
// stood at flattened the rubber band of every flick into it. Whenever the end moves
// under a reader who stood at it, the box first asks `yields`, with how it stood before
// the change (its scroll height and end), whether another placer places this end, as
// the thread places an answer to the user's turn (thread-card.js, `placesEnd`); a
// bounded log has none. It asks even where layout has already carried the reader to the
// new end, as Chromium's scroll anchoring does when the node it holds still stands
// below the growth, such as the end of an answer whose picture loads.
//
// The keeper reads the box at each of its size readings. An owner that sees what the box
// holds change asks it to read the box at once (`check`), as readings/bounds.js does for a log:
// text grows a box without resizing any box a size observer reports, as text appended
// to a `<pre>` log does, and a log emptied and refilled in two steps is clamped to its
// top in between, which only a reading at that moment sees as the reader still at its
// end. The keeper says whether its reader stands at the end (`standsAtEnd`), by the test
// it follows by or at the end as the box now stands, but not while an input heads the
// box up or across, as a revision asks of a bounded log to record its place (readings/bounds.js,
// `followingItsEnd`): a place recorded at the end then put the log back there and
// cancelled the wheel.
export function followEnd(box, yields = () => false) {
  let stood = null;
  const stand = ({ extent, limit }) => {
    const top = box.scrollTop;
    const goal = holding(box)?.goal ?? top;
    stood = { top, extent, limit, end: limit - goal <= SCROLL_SLACK };
  };
  const extentNow = () => ({ extent: box.scrollHeight, limit: scrollLimit(box) });
  const drawn = () => box.checkVisibility({ contentVisibilityAuto: true });
  // Whether the reader stands at the end where the last reading found them, neither
  // moved back since, before that scroll's event, nor headed back by a glide.
  const atStoodEnd = () => {
    if (!stood?.end) return false;
    const back = stood.top - SCROLL_SLACK;
    return box.scrollTop >= back && (holding(box)?.goal ?? box.scrollTop) >= back;
  };
  // Whether the reader's input heads the box up or across (`readerScroll`).
  const leaving = () => (readerScroll(box)?.heads ?? "down") !== "down";
  // The reader's scroll the keeper holds the end back for, with whether the reader stood
  // at the end as it began, kept past the scroll's end until a reading of the drawn box
  // settles it.
  let held = null;
  const holds = () => {
    const asked = readerScroll(box);
    if (!stood || !asked || asked.heads === "down") return false;
    held = { ...asked, end: held?.end ?? stood.end };
    return true;
  };
  // Whether the reader's scroll left them at the end the keeper held back (the header).
  const stayed = ({ end, starts: since, heads, top, fromEnd }) =>
    end &&
    (starts.get(box) ?? 0) === since &&
    (heads === "across" ||
      box.scrollTop === top ||
      Math.abs(scrollLimit(box) - box.scrollTop - fromEnd) < 1);
  const check = () => {
    if (!drawn()) return;
    if (!holds()) {
      const scroll = held;
      held = null;
      if (scroll && stood) {
        if (stayed(scroll) && !yields(stood)) scrollToEnd(box);
      } else if (
        stood &&
        scrollLimit(box) !== stood.limit &&
        atStoodEnd() &&
        !yields(stood)
      )
        scrollToEnd(box);
    }
    stand(extentNow());
  };
  const stopWatching = watchHeld(box, check);
  const scrolled = () => {
    if (drawn()) stand(stood ?? extentNow());
  };
  const stopEnds = watchScrollEnds((ended) => {
    if (ended === box) check();
  });
  // Where the box stands as the keeper starts is its first reading. Left to the first
  // scroll event or size reading, it took in whatever changed before that: an entry
  // appended to a log just opened at its end left the reader short of it for good.
  if (drawn()) stand(extentNow());
  box.addEventListener("scroll", scrolled, { passive: true });
  return {
    stop: () => {
      stopWatching();
      stopEnds();
      box.removeEventListener("scroll", scrolled);
    },
    check,
    standsAtEnd: () => !leaving() && (atStoodEnd() || followsEnd(box)),
  };
}
