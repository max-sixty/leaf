/* Scroll positions, and whose each one is.

   A box stands where the reader chose, or where layout put it. The reader chooses with
   a wheel, a key or a scrollbar, through a Leaf landing (landing-scroll.js), and through
   the browser's own navigation, such as find-in-page opening a closed disclosure onto
   its match. Layout puts a box where a clamp leaves it as content shrinks, where scroll
   anchoring adjusts it, and at the offset it kept while it did not scroll. Continuity's
   shift restore (version.js) undoes only layout's moves, so it asks which boxes the
   reader has chosen for since its reading (`chosenSince`).

   A scroll sequence ends with `scrollend`, whoever started it, and Chromium, Firefox and
   WebKit also end one at once where layout moves the box, by anchoring or a clamp, one
   sequence for each move (measured in Chromium 156, Firefox 157 and WebKit 27). So a
   sequence of several scroll events is a glide someone drove, and a single move is a
   choice unless layout explains it: the box's extent changed while it moved
   (`watchLayout`). A script's jump in the frame of a layout change therefore reads as
   layout's, and the reader's input aimed at the box, which continuity records itself
   (version.js, `inputSince`), settles those. The browser's travel into hidden content,
   as find-in-page opening a fold onto its match, fires `beforematch` first, so its end
   is a choice whatever the opening did to the layout. An end that leaves the box where
   its last one did, as Firefox sends after a layout move, chose nothing. A place
   keeper's write returns the reader to a place they already had (reading-place.js,
   `restorePlace`; user-place.js, `placeKeeper`; continuity's move of the page with its
   band), so it says where it left each box (`placeKept`), and a sequence ending there
   is the keeper's. An explicit landing counts from its start (`startScroll`), even
   when instant, since layout it caused can be announced before its sequence ends.
   A sequence can end frames after its last `scroll` event, as WebKit's do, so
   continuity takes a reading at the end too. Each sequence ends once, however many
   frames a glide writes it in (arrivals.js, `watchScrollEnds`). Like that record, this
   reads the document's own scrollers, not those inside a shadow root. */

import { cancelRender, nextFrame, sizeObserver } from "./rendering.js";
import {
  browserScrolls,
  holdScroll,
  setScroll,
  watchOwner,
  watchScrollEnds,
} from "./arrivals.js";
import { inputs } from "./inputs.js";
import { reducedMotion } from "./motion.js";
import { skipped } from "./shown-box.js";

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
// (navigation.js), as the user's latest input (`afterBrowserScroll`).
/** @type {WeakSet<Element>} */
const started = new WeakSet();
/** @type {WeakMap<Element, number>} */
const starts = new WeakMap();
/** @type {WeakSet<Element>} */
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
  scrollKeyLast = event instanceof KeyboardEvent && SCROLL_KEYS.has(event.key);
});
// Where each box's last sequence ended, the boxes layout has moved since, and each box's
// extent where its layout last settled. A box is watched from its first scroll, through
// its own size and its children's, where content grows, so content that grew between
// sequences doesn't make the next one layout's.
/** @type {WeakMap<Element, number>} */
const ended = new WeakMap();
/** @type {WeakMap<Element, number>} */
const scrollSteps = new WeakMap();
/** @type {WeakSet<Element>} */
const layoutMoved = new WeakSet();
/** @type {WeakSet<Element>} */
const watchedLayout = new WeakSet();
/** @type {WeakMap<Element, number[]>} */
const extents = new WeakMap();
/** @param {Element} box */
const extentOf = (box) => [box.scrollHeight, box.clientWidth, box.clientHeight];
/** @param {number[] | undefined} before @param {number[]} after */
const changedExtent = (before, after) =>
  before?.some((value, index) => value !== after[index]);
/** @param {Element} box */
function watchLayout(box) {
  if (watchedLayout.has(box)) return;
  watchedLayout.add(box);
  extents.set(box, extentOf(box));
  const root = box === pageScroller ? document.documentElement : box;
  /** @type {WeakMap<Element, number[] | null>} */
  const sizes = new WeakMap();
  // Observe skipped children too, so revealing them supplies their first reading.
  /** @param {Element} node */
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
  /** @param {Element} node */
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

// A new landing or return takes over a glide at once, even if its target is already
// visible, and a scroll the browser drives, such as a wheel's, with an instant write.
// Chromium can deliver one last compositor scroll after that cancellation, so its
// rendering update must finish before the caller reads geometry and places the new
// destination. Two callbacks enclose that whole update.
/** @param {Iterable<Element>} boxes */
export function stopScroll(boxes) {
  const all = [...boxes];
  const stopped = all.filter(browserScrolls);
  for (const box of all) stopGlide(box);
  if (!stopped.length) return null;
  for (const box of stopped)
    setScroll(box, {
      left: box.scrollLeft,
      top: box.scrollTop,
      behavior: "instant",
    });
  return new Promise(
    /** @param {(value?: void) => void} resolve */ (resolve) =>
      nextFrame(() => nextFrame(() => resolve(undefined))),
  );
}

let choices = 0;
/** @type {WeakMap<Element, number>} */
const chosen = new WeakMap();
/** @type {WeakMap<Element, number>} */
const kept = new WeakMap();
// How many choices the reader has made so far, for a keeper to note with a reading.
export const scrollChoices = () => choices;
// Whether the reader chose where `box` stands after the `count`th choice.
/** @param {Element} box @param {number} count */
export const chosenSince = (box, count) => (chosen.get(box) ?? 0) > count;
/** @param {Element} box */
const chooseScroll = (box) => chosen.set(box, ++choices);
// Record an explicit landing or a glide before native scroll events: an instant move
// can coincide with layout, and a new gesture can interrupt a glide before its first
// frame.
/** @param {Element} box */
export function startScroll(box) {
  started.add(box);
  starts.set(box, (starts.get(box) ?? 0) + 1);
  chooseScroll(box);
}
// The browser's travel into hidden content, until the sequence it starts has ended,
// which is before the second frame after.
/** @type {object | null} */
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
/** @param {EventTarget | null} target */
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
/** @param {Element[]} boxes */
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
    (ended.get(box) !== box.scrollTop &&
      !layoutMoved.has(box) &&
      !changedExtent(extents.get(box), extent));
  if (chosenHere && kept.get(box) !== box.scrollTop) chooseScroll(box);
  ended.set(box, box.scrollTop);
  layoutMoved.delete(box);
  extents.set(box, extent);
  kept.delete(box);
});

// Boxes whose content is drawn away from where its layout stands it. A send's stream
// (box-motion.js) draws a scroller's content where it stood, below where its layout now
// stands it, and the browser counts that drawing in the box's scroll height while the
// content rides (`contentRides`, false when the ride ends). Meanwhile the box's height
// is read from its layout each time it is asked, so its end stays where its layout puts
// it, content arriving mid-ride included, and a landing at the end doesn't chase the
// ride.
/** @type {WeakSet<Element>} */
const riding = new WeakSet();
/** @param {Element} box @param {boolean} rides */
export const contentRides = (box, rides) =>
  rides ? riding.add(box) : riding.delete(box);
// A box's scroll height as its layout gives it: from where its children stand, which
// offsets read without any transform, and its own end padding. A child placed against
// something other than the box leaves the browser's reading.
/** @param {Element} box */
function laidOutHeight(box) {
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
  const padding = Number.parseFloat(getComputedStyle(box).paddingBottom);
  return Math.min(box.scrollHeight, end + padding);
}
// The furthest a box scrolls down: its scroll height less what its scrollport shows.
/** @param {Element} box */
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
/** @param {Element} box @param {number} [top] */
export const atScrollEnd = (box, top = box.scrollTop) =>
  scrollLimit(box) - top <= SCROLL_SLACK;
/** @param {Element} box @param {ScrollBehavior} behavior */
export const scrollToEnd = (box, behavior = "instant") => {
  if (glides(box, behavior)) return glideTo(box, scrollLimit(box));
  stopGlide(box);
  setScroll(box, { top: scrollLimit(box), behavior: "instant" });
};
// Whether a move asked for with `behavior` glides: a smooth one, or an `auto` one in a
// box whose own `scroll-behavior` asks for smooth motion, which the browser would
// otherwise answer with its own slow smooth scroll.
/** @param {Element} box @param {ScrollBehavior} behavior */
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
/** @type {WeakMap<Element, {aim: number, at: number}>} */
const aims = new WeakMap();
/** @param {Element} box @param {number} top */
export const moveScrollerBy = (box, top) => {
  const aim = box.scrollTop + top;
  if (Math.abs(top) >= 0.5) setScroll(box, { top: aim, behavior: "instant" });
  if (Math.abs(aim - box.scrollTop) < 1) aims.set(box, { aim, at: box.scrollTop });
  else aims.delete(box);
};
// Where Leaf last aimed `box`, while it stands where that move left it, else its offset.
// A move that landed a pixel or more off was cut off by the box's range, and names no
// position the box stands at.
/** @param {Element} box */
export const aimedTop = (box) => {
  const kept = aims.get(box);
  return kept?.at === box.scrollTop ? kept.aim : box.scrollTop;
};

// How much of a move a box can make from where it stands: a box at its end moves no
// further, whatever it is asked.
/** @param {Element} box @param {number} top */
export const reachable = (box, top) =>
  Math.max(-box.scrollTop, Math.min(scrollLimit(box) - box.scrollTop, top));

// A glide moves a box to a goal at the pace of the browser's own paging keys, and every
// smooth vertical motion Leaf makes is one: the reading-page keys (navigation.js,
// `stepAlong`), the go-to sequence's edges, and every landing (landing-scroll.js), such
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
// motion has brought the box. A glide stands down the moment the box moves under any
// later hand, such as a wheel, and a return takes the box from it (`stopScroll`).
const SCROLL_MS = 140;
/** @typedef {{goal: number, wrote: number | null, raf: ReturnType<typeof nextFrame>, release: () => void}} Glide */
// The glide under way in each box, which holds the box's scroll sequence open from its
// press to its end, so every frame it writes makes one scroll (arrivals.js,
// `holdScroll`).
/** @type {Map<Element, Glide>} */
const glideIn = new Map();
// A spatial command takes the page where it is now, so it stops a glide in the box even
// where it moves nothing itself.
/** @param {Element} box */
export function stopGlide(box) {
  const glide = glideIn.get(box);
  if (!glide) return;
  cancelRender(glide.raf);
  glideIn.delete(box);
  glide.release();
}
// A glide's claim on its box: it holds only while the box is where the glide last wrote
// it. The tick asks before every write, and a press asks the same question before
// trusting the goal — the user can take the box between frames, and a press landing in
// that gap otherwise measures from a goal the box has already left. A glide taking over
// the browser's motion holds the box through whatever that motion does until the
// glide's own write first moves it (`glideTo`).
/** @param {Element} box */
const holding = (box) => {
  const glide = glideIn.get(box);
  return glide && (glide.wrote === null || Math.abs(box.scrollTop - glide.wrote) <= 1)
    ? glide
    : null;
};
// Where `box` is headed: the goal of the glide holding it, else where it stands.
/** @param {Element} box */
export const scrollGoal = (box) =>
  Math.max(0, Math.min(scrollLimit(box), holding(box)?.goal ?? box.scrollTop));
// Run `then` once the scroll a key has the browser drive in `box`, as Space's and
// PageDown's are, has ended, and say whether it waits. The steps waiting on one box run
// in the order pressed, and none of them runs if Leaf moves the box meanwhile.
/** @type {WeakMap<Element, {starts: number, steps: (() => void)[]}>} */
const waiting = new WeakMap();
/** @param {Element} box @param {() => void} then */
export function afterBrowserScroll(box, then) {
  if (!keyScrolled.has(box) || !browserScrolls(box)) return false;
  const queued = waiting.get(box);
  if (queued) {
    queued.steps.push(then);
    return true;
  }
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
// The goal is clamped here, so a step pressed on at the foot banks no debt for u to press
// back through, and an edge may be asked for as the height it cannot exceed. Motion the
// browser drives in the box at the press, or that the glide this replaces had yet to
// take, is this glide's to take over. Otherwise the glide holds the box from the press,
// and a hand that moves it before the glide's first frame wins. A glide with nothing to
// move or take over is none.
/** @param {Element} box @param {number} top */
export function glideTo(box, top) {
  const replaced = glideIn.get(box);
  const takesOver = replaced ? replaced.wrote === null : browserScrolls(box);
  const goal = Math.max(0, Math.min(scrollLimit(box), top));
  if (!replaced && !takesOver && Math.abs(goal - box.scrollTop) < 0.5) return;
  startScroll(box);
  if (reducedMotion()) {
    stopGlide(box);
    setScroll(box, { top: goal, behavior: "instant" });
    return;
  }
  cancelRender(replaced?.raf);
  let start = box.scrollTop;
  const t0 = performance.now();
  /** @param {number} now */
  const tick = (now) => {
    const current = holding(box);
    if (!current) {
      stopGlide(box); // the box moved under another hand; theirs wins
      return;
    }
    if (reducedMotion()) {
      setScroll(box, { top: current.goal, behavior: "instant" });
      stopGlide(box);
      return;
    }
    // Floored as well as capped: a rAF timestamp is its frame's start, which can precede
    // the press that scheduled the tick, and an unfloored t walks the ease out past the
    // start — to a write the box clamps, which the next tick then read as another hand.
    const t = Math.max(0, Math.min(1, (now - t0) / SCROLL_MS));
    // Until the glide taking over the browser's motion has moved the box, it starts from
    // wherever that motion has taken it, read at each frame rather than at the press:
    // Firefox's smooth scroll runs on ahead of a busy page, whose next frame is the first
    // to say where the box is, and a write that leaves the box where the page last saw
    // it doesn't stop that scroll.
    if (current.wrote === null) start = box.scrollTop;
    setScroll(box, {
      top: goal - (goal - start) * (1 - t) ** 3,
      behavior: "instant",
    });
    // Where the write left the box, not what it asked for: the box clamps at its ends
    // and snaps to pixels, and the claim the next tick tests is about the box.
    if (current.wrote !== null || box.scrollTop !== start)
      current.wrote = box.scrollTop;
    if (t < 1) current.raf = nextFrame(tick);
    else stopGlide(box);
  };
  glideIn.set(box, {
    goal,
    wrote: takesOver ? null : box.scrollTop,
    raf: nextFrame(tick),
    release: replaced?.release ?? holdScroll(box),
  });
}

// A box standing on its foot beside a field that writes into it, as a thread's view in
// the panel stands on its field and a card's transcript on its reply box, keeps what
// stands at its foot as the field takes room from it or gives it back: the box gives way
// at its top, so the message the user is answering stays beside their words. A reading
// in which what the box holds changed size too keeps nothing, leaving that change to the
// code that places it, a reply drawn or a send. Where the foot stood is read at each of
// the box's scrolls and readings, before the next change of its room. Read when that
// change is answered, by a keystroke's handler or a card's fit, it was read too late
// wherever the room had already changed, which Firefox showed for a draft from another
// tab or a resized window. The exception is the clamp a growth makes at the box's end,
// whose scroll can arrive before the reading that answers the growth. `atEnd` keeps the
// foot only while it is the box's end: a card read back keeps its reader's offset
// (thread-preview.js, `measureThreadCard`). `kept` hears each move the keeper makes.
/** @param {HTMLElement} box @param {{atEnd?: boolean, kept?: () => void}} [options]
 * @returns {() => void} */
export function keepFoot(box, { atEnd = false, kept } = {}) {
  /** @type {{room: number, top: number, end: boolean} | null} */
  let foot = null;
  const observer = sizeObserver((entries) => {
    const room = box.clientHeight;
    if (
      foot &&
      room !== foot.room &&
      (!atEnd || foot.end) &&
      entries.every(({ target }) => target === box)
    ) {
      moveScrollerBy(box, foot.top + foot.room - room - box.scrollTop);
      kept?.();
    }
    foot = { room, top: box.scrollTop, end: atScrollEnd(box) };
  });
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
  const scrolled = () => {
    if (
      !foot ||
      (box.clientHeight > foot.room && box.scrollTop < foot.top && atScrollEnd(box))
    )
      return;
    foot.top = box.scrollTop;
    foot.end = atScrollEnd(box);
  };
  box.addEventListener("scroll", scrolled, { passive: true });
  return () => {
    observer.disconnect();
    children.disconnect();
    box.removeEventListener("scroll", scrolled);
  };
}
