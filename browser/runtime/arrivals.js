/* Elements of one kind, held while they stand in the page, and the stages they stand in.

   Some of the runtime's paint belongs to an element for as long as it stands, whoever
   put it there: an external link's mark and note, and the bounded block that is a
   reading region. What produces those elements is open-ended (the served document, a
   revision patched in, a thread's message, any widget's render), so no list of
   producers can call each owner. `watchArrivals(selector, attributes, { arrive, leave })`
   watches for them instead:

   - `arrive(el)` runs for each match present when the watch starts and each one added
     since, however deep in what was added, shadow stages included. It runs again when
     a watched attribute changes, and when the nodes beside the element change: its own
     children, or a sibling added or removed next to it. That is where an owner's paint
     stands (a link's mark inside it, its note after it), so a render that keeps the
     element and drops the paint hands the element back to be painted again. `arrive`
     is therefore idempotent, and cheap for an element whose paint still stands.
   - `leave(el)` runs once for an element that has arrived and no longer stands or
     matches. Mutation records describe intermediate moves: an element removed and added
     back in one batch has not left, so leaving is decided once the batch is read, from
     where the element stands then.

   `arriveBatch(elements)` may replace `arrive` where an owner must read all matching
   elements before writing any of them. Each initial stage and mutation delivery is
   one batch; an explicit offer is a batch of one. `watchArrivals` returns `offer(el)`,
   which decides one element at once rather than at the next mutation delivery. It
   first reads the mutations already made as a batch, so a decision made now never
   runs ahead of a departure made before it.

   An element's connection lifetime is one such watch over the elements a subscription
   stands on, which can be any element: `watchOwner(owner, {connect, disconnect})`
   connects while the owner stands and
   disconnects once a batch shows it gone, so a move within one batch keeps it. A new
   owner connects through `offer`, and a batch decides its departures before its
   arrivals, so whatever left before an owner connects has released first: a revision
   evicts a replaced widget before its replacement connects, and a registration only
   one element may hold passes from one to the other. A connection also ends the
   batch, so an element removed before it and put back after it leaves and returns.
   The runtime's own subscriptions (data, projections, widget controllers) and
   LeafElement rendering hold it directly.
   Widgets hold it through `whileConnected`, for resources, and `frameFor`, for
   scheduled paints, which `widget-api.js` exports in its place.

   Present means in the document, the page's body and the chrome after it alike, or in
   a declared shadow stage whose host is connected. No observer crosses a shadow boundary on its own, so shadow-stage.js, the
   one door a stage is built through, hands each one it fills to `watchArrivalsIn`. No
   scroll or scroll end crosses one either, so this module hears the document's and
   every stage's, and those of any other tree a module enrolls (`hearScrollsIn`).
   This module is the stages' one registry (`liveStages`), held weakly: a stage outlives
   its widget only as garbage. A stage built while its host was detached arrives with the
   host. */
import { isElement, shadowHost, under } from "./shadow-tree.js";
import { cancelRender, nextFrame, nextRender } from "./rendering.js";

/** The elements a watch holds: whether `is` one, and every one `within` a tree.
 * @typedef {{is: (el: Element) => boolean, within: (root: Element | ShadowRoot) => Iterable<Element>}} Kind
 * @typedef {{kind: Kind, attributes: string[], observer: MutationObserver, offerMany: (elements: Iterable<Element>) => void}} ArrivalWatch
 * @typedef {{connect(): void, disconnect(): void}} Connection */
/** @type {Set<ArrivalWatch>} */
const watches = new Set();
/** @type {Set<WeakRef<ShadowRoot>>} */
const stageRefs = new Set();
// Each stage by its host, closed ones included, which no host answers through
// `shadowRoot`.
/** @type {WeakMap<Element, ShadowRoot>} */
const hostStages = new WeakMap();
/** @param {Element} host */
export const stageOf = (host) => hostStages.get(host) ?? null;
/** @type {WeakMap<Element, Set<Connection>>} */
const owners = new WeakMap();
/** @type {((element: Element) => void) | undefined} */
let offerOwner;

/** @param {Element} element @param {keyof Connection} method */
function notifyOwners(element, method) {
  for (const subscription of owners.get(element) ?? []) {
    try {
      subscription[method]();
    } catch (error) {
      // A failed owner reports through the window's error channel while the
      // remaining owners in this arrival batch still receive their transition.
      queueMicrotask(() => {
        throw error;
      });
    }
  }
}
// The one watch every owner shares, made on first use. It is made here, not in the
// first owner's call, whose scope its callbacks would otherwise keep alive.
const ownerWatch = () =>
  (offerOwner ??= watchKind(ownerKind, [], {
    arrive: (element) => notifyOwners(element, "connect"),
    leave: (element) => notifyOwners(element, "disconnect"),
  }));

// Independent subscriptions share their element's connection lifetime. The arrival
// batch decides whether it actually left, so an in-document move retains them.
/** @param {Element} owner @param {Partial<Connection>} lifecycle */
export function watchOwner(owner, lifecycle) {
  let connected = false;
  const subscriptions = owners.get(owner) ?? new Set();
  owners.set(owner, subscriptions);
  const subscription = {
    connect() {
      if (connected || !owner.isConnected) return;
      connected = true;
      try {
        lifecycle.connect?.();
      } catch (error) {
        subscriptions.delete(subscription);
        subscription.disconnect();
        throw error;
      }
    },
    disconnect() {
      if (!connected) return;
      connected = false;
      lifecycle.disconnect?.();
    },
  };
  const offer = ownerWatch();
  // A synchronous connection can begin and end before the first arrival batch.
  // Offer the owner before setup so that batch still knows its resources must leave.
  if (owner.isConnected) offer(owner);
  subscriptions.add(subscription);
  const stop = () => {
    subscriptions.delete(subscription);
    subscription.disconnect();
  };
  subscription.connect();
  return stop;
}

/** Start mechanical resources for each connection, abort their listeners and run
 * the optional returned cleanup when the owner leaves. Register once: moves within
 * an arrival batch retain the same scope, and the returned stop retires it. */
/** @param {Element} owner @param {(signal: AbortSignal) => (() => void) | void} start */
export function whileConnected(owner, start) {
  let disconnect = () => {};
  return watchOwner(owner, {
    connect() {
      const controller = new AbortController();
      /** @type {(() => void) | void} */
      let cleanup;
      // Install disposal before setup, so a failed start releases its signal too.
      disconnect = () => {
        controller.abort();
        cleanup?.();
      };
      cleanup = start(controller.signal);
    },
    disconnect() {
      disconnect();
    },
  });
}

/** One coalesced nextRender callback while the owner stands. A departure cancels
 * pending work; the callback also checks connection before the arrival batch runs.
 * A return permits fresh scheduling, without replaying the cancelled callback. */
/** @param {Element} owner @param {() => void} run */
export function frameFor(owner, run) {
  let frame = 0;
  watchOwner(owner, {
    disconnect() {
      cancelRender(frame);
      frame = 0;
    },
  });
  return () => {
    if (frame || !owner.isConnected) return;
    frame = nextRender(() => {
      frame = 0;
      if (owner.isConnected) run();
    });
  };
}

export function liveStages() {
  const live = [];
  for (const ref of stageRefs) {
    const root = ref.deref();
    if (root) live.push(root);
    else stageRefs.delete(ref);
  }
  return live;
}

/** @param {Node} root @returns {root is ShadowRoot} */
export const isStage = (root) => {
  const host = shadowHost(root);
  return host !== null && hostStages.get(host) === root;
};

/** @param {Element} el */
const stands = (el) => {
  const root = el.getRootNode();
  return root === document || (isStage(root) && root.host.isConnected);
};

// An owner (`watchOwner`) can be any element, so finding the owners in what a mutation
// added visits every element there, and offers only the owners.
/** @type {Kind} */
const ownerKind = {
  is: (el) => owners.has(el),
  *within(root) {
    for (const el of root.querySelectorAll("*")) if (owners.has(el)) yield el;
  },
};

// Every match in what a record names, the stages inside it included.
/** @param {Node | null} node @param {Kind} kind @returns {Generator<Element>} */
function* matching(node, kind) {
  if (!isElement(node)) return;
  if (kind.is(node)) yield node;
  yield* kind.within(node);
  for (const stage of liveStages())
    if (under(stage.host, node)) yield* kind.within(stage);
}

/**
 * @param {string} selector
 * @param {string[]} attributes
 * @param {Watcher} watcher Each arrival goes to `arriveBatch` where there is one, else to `arrive`.
 */
export const watchArrivals = (selector, attributes, watcher) =>
  watchKind(
    {
      is: (el) => el.matches(selector),
      within: (root) => root.querySelectorAll(selector),
    },
    attributes,
    watcher,
  );

/**
 * @typedef {{
 *   leave: (element: Element) => void,
 * } & ({arrive: (element: Element) => void, arriveBatch?: never}
 * | {arrive?: never, arriveBatch: (elements: Element[]) => void})} Watcher
 * @param {Kind} kind @param {string[]} attributes @param {Watcher} watcher
 */
function watchKind(kind, attributes, { arrive, arriveBatch, leave }) {
  const arrived = new WeakSet();
  // Every departure a batch shows is decided before any arrival in it.
  /** @param {Iterable<Element>} elements */
  const offerMany = (elements) => {
    const present = [];
    for (const el of elements) {
      if (stands(el) && kind.is(el)) present.push(el);
      else if (arrived.delete(el)) leave(el);
    }
    if (!arriveBatch) for (const el of present) offer(el);
    else if (present.length) {
      for (const el of present) arrived.add(el);
      arriveBatch(present);
    }
  };
  /** @param {Element} el */
  const offer = (el) => {
    if (stands(el) && kind.is(el)) {
      arrived.add(el);
      if (arriveBatch) arriveBatch([el]);
      else arrive(el);
    } else if (arrived.delete(el)) leave(el);
  };
  /** @param {Node | null} node */
  const beside = (node) =>
    isElement(node) && (arrived.has(node) || kind.is(node)) ? [node] : [];
  /** @param {MutationRecord[]} records */
  const read = (records) => {
    /** @type {Set<Element>} */
    const offered = new Set();
    for (const record of records) {
      if (record.type === "attributes") {
        if (isElement(record.target)) offered.add(record.target);
        continue;
      }
      for (const el of [
        ...beside(record.target),
        ...beside(record.previousSibling),
        ...beside(record.nextSibling),
      ])
        offered.add(el);
      for (const node of record.addedNodes)
        for (const el of matching(node, kind)) offered.add(el);
      for (const node of record.removedNodes)
        for (const el of matching(node, kind)) if (arrived.has(el)) offered.add(el);
    }
    offerMany(offered);
  };
  const observer = new MutationObserver(read);
  const watch = { kind, attributes, observer, offerMany };
  watches.add(watch);
  for (const root of [document.documentElement, ...liveStages()]) enroll(watch, root);
  return (/** @type {Element} */ el) => {
    read(observer.takeRecords());
    offer(el);
  };
}

/** @param {ArrivalWatch} watch @param {Element | ShadowRoot} root */
function enroll({ kind, attributes, observer, offerMany }, root) {
  observer.observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: attributes,
  });
  offerMany(kind.within(root));
}

/** @param {ShadowRoot} stage */
export function watchArrivalsIn(stage) {
  if (hostStages.get(stage.host) === stage) return;
  hostStages.set(stage.host, stage);
  stageRefs.add(new WeakRef(stage));
  for (const watch of watches) enroll(watch, stage);
  hearScrollsIn(stage);
}

// Every scroll in the page, a stage's included: `scroll` and `scrollend` are not
// composed, so a scroller inside a shadow stage reaches no listener outside it. Each
// tree hears its own scrollers for every listener, through one listener of its own that
// holds nothing but the tree, and only its own, since one slotted into it from the
// document reaches the document too. The document and every stage are heard from the
// start; a module placing paint against the scrollers of another shadow tree, as the
// margin does, enrolls that tree (`hearScrollsIn`). Listeners receive the scroller
// itself. Leaf's instant scroll writes announce their completed position here too: a
// write in resize delivery paints before the browser sends its scroll event, so
// dependent paint cannot wait on that event.
/** @type {Set<(box: Element | null) => void>} */
const scrollListeners = new Set();
const SCROLL = { capture: true, passive: true };
/** @param {Element | null} box */
function announceScroll(box) {
  if (box) {
    heardAt.set(box, standing(box));
    inSequence(box);
  }
  for (const listener of scrollListeners) listener(box);
}
// Complete a scroll write and publish the position that will paint. Native scroll
// events arrive too late for writes in an animation frame or resize delivery.
//
// An instant write that would leave the box where it stands writes nothing, so a writer
// may restate a position as often as it likes, as `keeps` lets one restate a DOM value.
// The write's only effect would be one nobody asked for: it stops the scroll the browser
// drives, and in Firefox it cancels the rubber band of a flick into an edge, which runs
// after the box's scroll has ended (a margin card that put its transcript back at its
// end at every scroll's end flattened each flick's band). Stopping a scroll is a write
// of its own (`stopWhereItStands`). Where the box stands is read to the pixel: its
// scroll size is a whole number of pixels, so an end read from it stands up to a pixel
// short of the browser's own, as 314 did of Firefox's 314.25 at a 2x display.
/** @param {Element} box @param {ScrollToOptions} options */
export function setScroll(box, options) {
  const { scrollTop, scrollLeft } = box;
  const { behavior = "instant" } = options;
  if (behavior === "instant" && !moves(box, options)) return;
  box.scrollTo({ ...options, behavior });
  if (behavior !== "instant") return;
  placed.set(box, { top: box.scrollTop, left: box.scrollLeft });
  if (box.scrollTop !== scrollTop || box.scrollLeft !== scrollLeft) announceScroll(box);
}
// Stop the scroll the browser drives in a box, leaving the box where it stands, as a
// landing does before it places its destination (scrolling.js, `stopScroll`) and a glide
// before it takes over a wheel's motion (`glideTo`). It is the one scroll write meant to
// move nothing, which the write watch knows by this name (tests/write_watch.js,
// `EXPECTED_SCROLLS`). An instant write alone stops too little: no instant write, even
// one that moves the box, stops the smooth scroll a key such as PageDown sets off, in
// Chromium or Firefox, and Firefox doesn't stop any smooth scroll for a write of the
// position the page last saw (Chromium 158 and Firefox 159). So a `m` pressed as
// PageDown moved the page lost its landing to PageDown. A smooth write takes the box
// from whatever moves it, in both, and the instant one after ends that write's own
// motion where the box stands.
/** @param {Element} box */
export function stopWhereItStands(box) {
  const at = { top: box.scrollTop, left: box.scrollLeft };
  box.scrollTo({ ...at, behavior: "smooth" });
  box.scrollTo({ ...at, behavior: "instant" });
  placed.set(box, at);
  heardAt.set(box, standing(box));
}
// Whether a write to `top` and `left` takes the box a pixel or more from where it
// stands, once the browser clamps it to the box's range.
/** @param {Element} box @param {ScrollToOptions} options */
const moves = (box, { top, left }) => {
  const range = scrollRange(box);
  /** @param {number | undefined} to @param {number} at @param {[number, number]} reach */
  const along = (to, at, [low, high]) =>
    to !== undefined && Math.abs(Math.min(Math.max(to, low), high) - at) >= 1;
  return (
    along(top, box.scrollTop, range.top) || along(left, box.scrollLeft, range.left)
  );
};
// The positions a box's scroll takes on each axis, as the browser clamps a write: from
// zero to the side where the box's content flows from, the negative one where that is
// the bottom or right edge (`scrollsBack`). Off zero, where the box stands says which;
// at zero on an axis whose side the style leaves open, both sides, so no move is lost.
/** @param {Element} box @returns {{top: [number, number], left: [number, number]}} */
export function scrollRange(box) {
  const { scrollTop: top, scrollLeft: left } = box;
  const down = Math.max(box.scrollHeight - box.clientHeight, 0);
  const across = Math.max(box.scrollWidth - box.clientWidth, 0);
  const back =
    (top === 0 && down) || (left === 0 && across)
      ? scrollsBack(box)
      : { top: false, left: false };
  /** @param {number} at @param {number} span @param {boolean | null} side @returns {[number, number]} */
  const reach = (at, span, side) =>
    at > 0 || (at === 0 && side === false)
      ? [0, span]
      : at < 0 || side
        ? [-span, 0]
        : [-span, span];
  return { top: reach(top, down, back.top), left: reach(left, across, back.left) };
}
// Whether each axis of a box scrolls on the negative side of zero, or null where its
// style leaves that open. A box scrolls from where its content's flow starts, so one
// whose flow starts at the bottom or right edge scrolls back from zero. Writing mode and
// direction place the inline and block starts, and a flex container's main and cross
// starts follow its direction and wrap. No API reports a box's scroll range (Firefox's
// own `scrollTopMin` aside), and a box standing at zero shows nothing of its side, so the
// side is read from the style that decides it; Chromium and Firefox agree on every
// combination of those (tests/browser/test_scroll_writes.py).
//
// The page scrolls from its principal flow, which no flex flow of the root's reverses:
// the root's writing mode and direction, or the body's where the page takes them from
// it. Which one applies turns on containment, content visibility, a hidden body or a
// frameset, and the engines differ on some of those, so where the root and the body
// agree that is the side, and where they don't it is open.
/** @param {Element} box @returns {{top: boolean | null, left: boolean | null}} */
function scrollsBack(box) {
  const page = box.ownerDocument;
  if (box !== page.scrollingElement) return flowsBack(getComputedStyle(box), true);
  const root = flowsBack(getComputedStyle(box), false);
  if (!page.body) return root;
  const body = flowsBack(getComputedStyle(page.body), false);
  return {
    top: root.top === body.top ? root.top : null,
    left: root.left === body.left ? root.left : null,
  };
}
// Whether each axis of a box with `style` starts its flow at the bottom or right edge,
// counting its flex flow where `flex` asks.
/** @param {CSSStyleDeclaration} style @param {boolean} flex */
function flowsBack(style, flex) {
  const { writingMode, direction, display, flexDirection, flexWrap } = style;
  const vertical = writingMode !== "horizontal-tb";
  // Whether the inline axis starts at its bottom or right end, and the block axis.
  let inline = (writingMode === "sideways-lr") !== (direction === "rtl");
  let block = writingMode === "vertical-rl" || writingMode === "sideways-rl";
  if (flex && display.endsWith("flex")) {
    const reversed = flexDirection.endsWith("-reverse");
    const wrapped = flexWrap === "wrap-reverse";
    if (flexDirection.startsWith("column"))
      [block, inline] = [block !== reversed, inline !== wrapped];
    else [inline, block] = [inline !== reversed, block !== wrapped];
  }
  return vertical ? { top: inline, left: block } : { top: block, left: inline };
}
/** @type {WeakSet<Document | ShadowRoot>} */
const hearing = new WeakSet();
/** @param {Document | ShadowRoot} root */
export function hearScrollsIn(root) {
  if (hearing.has(root)) return;
  hearing.add(root);
  /** @param {Event} event */
  const heard = ({ type, target }) => {
    const box =
      target === document
        ? root === document
          ? document.scrollingElement
          : null
        : isElement(target) && target.getRootNode() === root
          ? target
          : null;
    if (!box) return;
    if (type === "scroll") announceScroll(box);
    else if (!awaitsReader(box)) endSequence(box);
  };
  root.addEventListener("scroll", heard, SCROLL);
  root.addEventListener("scrollend", heard, SCROLL);
}
hearScrollsIn(document);
/** @param {(box: Element | null) => void} listener */
export function watchScrolls(listener) {
  scrollListeners.add(listener);
  return () => scrollListeners.delete(listener);
}

// Each box's scroll sequence, from its first scroll until it ends: at its `scrollend`,
// or, since a scroll restoration that replaces what was scrolling ends without one,
// after a quiet spell of SETTLE_MS and two rendering updates with no scroll in the box.
// The spell needs both: Firefox's main thread hears its smooth scroll's frames late,
// and a busy page delays the updates that carry a scroll's events past any clock.
// WebKit ends a keyboard scroll on each of its frames (notes/browser-support.md), so
// there one keypress makes several sequences. A script that moves a
// box a frame at a time, as the runtime's glide does (scrolling.js, `glideTo`), gets a
// `scrollend` for each frame, so it holds the box (`holdScroll`), and the sequence ends
// once, after the hold is released. Every reader of a scroll's end hears it here, once
// per sequence (`watchScrollEnds`): what rides a scroll on an anchor is placed again, a
// reading place recorded and who chose the position decided once the scroll settles,
// rather than on each frame, which would trail the scroll a frame behind and cost a
// frame's work. Readers hear an end in the order they subscribed, and scrolling.js
// subscribes as it loads, so who chose the position is decided before any later reader
// asks (version.js reads it).
const SETTLE_MS = 80;
/** @type {Set<(box: Element) => void>} */
const endListeners = new Set();
// Each box whose sequence runs, with how many of its scrolls have been heard, when the
// last one was, and where the box stood when the reader's input started it
// (`startReaderScroll`).
/** @typedef {{heard: number, at: number, reader?: {top: number, left: number, fromEnd: number}}} Sequence */
/** @type {Map<Element, Sequence>} */
const sequences = new Map();
/** @type {Map<Element, number>} */
const holds = new Map();
// Where a script last put each box (`setScroll`), until the box's sequence ends.
/** @type {WeakMap<Element, {top: number, left: number}>} */
const placed = new WeakMap();
// Where the page last heard each box stand: at its scroll events, Leaf's own writes and
// stops (`startReaderScroll`).
/** @type {WeakMap<Element, {top: number, left: number, fromEnd: number}>} */
const heardAt = new WeakMap();
/** @param {Element} box @returns {Sequence} */
function sequenceIn(box) {
  let sequence = sequences.get(box);
  if (!sequence) sequences.set(box, (sequence = { heard: 0, at: performance.now() }));
  return sequence;
}
/** @param {Element} box */
function inSequence(box) {
  const sequence = sequenceIn(box);
  const heard = ++sequence.heard;
  sequence.at = performance.now();
  const quiet = () => {
    if (sequences.get(box) !== sequence || sequence.heard !== heard) return;
    if (performance.now() - sequence.at < SETTLE_MS) nextFrame(quiet);
    else endSequence(box);
  };
  nextFrame(() => nextFrame(quiet));
}
/** @param {Element} box */
function endSequence(box) {
  if (!sequences.has(box) || holds.has(box)) return;
  sequences.delete(box);
  placed.delete(box);
  for (const listener of endListeners) listener(box);
}
// Hold `box`'s sequence open from now until the returned release, after which it ends
// as a glide's last frame ends it.
/** @param {Element} box @returns {() => void} */
export function holdScroll(box) {
  holds.set(box, (holds.get(box) ?? 0) + 1);
  sequenceIn(box);
  let held = true;
  return () => {
    if (!held) return;
    held = false;
    const left = (holds.get(box) ?? 1) - 1;
    if (left) {
      holds.set(box, left);
      return;
    }
    holds.delete(box);
    inSequence(box);
  };
}
// Start `box`'s sequence at the reader's input asking the browser to scroll it
// (scrolling.js, `aimScroll`), ahead of the scroll the browser applies later, so the box
// is the browser's to move from the input. A `scrollend` that arrives while the box
// still stands where the input found it, from its top or from its end, ends some other
// scroll, so it ends nothing of the reader's (`awaitsReader`): Firefox ends a write it
// applied before the input, and layout ends its own move, as a clamp when a log loses
// its oldest entries carries the box up with them. Where the input moves nothing, as a
// wheel at an edge doesn't, the sequence ends after the quiet spell.
//
// Where the input found the box is where the page last heard it stand (`heardAt`), not
// where it stands as the input's listener runs: Chromium can apply a wheel's scroll
// before it dispatches the wheel, and read from there the input's own `scrollend`
// would end nothing, leaving the box the browser's for the quiet spell after its
// scroll ended. A move the page has yet to hear of is the input's or layout's; a clamp
// keeps the box's end where the page last heard it, so its `scrollend` still ends
// nothing of the reader's.
// It returns where the input found the box.
/** @param {Element} box @returns {{top: number, left: number, fromEnd: number}} */
export function startReaderScroll(box) {
  placed.delete(box);
  const now = standing(box);
  const heard = heardAt.get(box);
  const found =
    heard && (heard.top !== now.top || heard.left !== now.left) ? heard : now;
  sequenceIn(box).reader = found;
  inSequence(box);
  return found;
}
/** @param {Element} box */
const standing = (box) => ({
  top: box.scrollTop,
  left: box.scrollLeft,
  fromEnd: fromEnd(box),
});
/** @param {Element} box */
const fromEnd = (box) => box.scrollHeight - box.clientHeight - box.scrollTop;
/** @param {Element} box */
const awaitsReader = (box) => {
  const at = sequences.get(box)?.reader;
  return Boolean(
    at &&
    at.left === box.scrollLeft &&
    (at.top === box.scrollTop || Math.abs(at.fromEnd - fromEnd(box)) < 1),
  );
};
// Whether a scroll sequence is under way anywhere in the page.
export const scrolling = () => sequences.size > 0;
// Whether the browser moves `box`, rather than a script: a sequence under way in it that
// no hold keeps open, and that has taken the box from where a script last put it, or
// that the reader's input has just asked of it (`startReaderScroll`). A script's last
// write keeps the sequence open while it settles (`inSequence`), and that settling is
// still the script's.
/** @param {Element} box */
export const browserScrolls = (box) => {
  if (!sequences.has(box) || holds.has(box)) return false;
  const at = placed.get(box);
  return !at || at.top !== box.scrollTop || at.left !== box.scrollLeft;
};
// Whether the reader's input has set `box` scrolling: a sequence it started
// (`startReaderScroll`), from the input, before the browser moves the box, until the
// sequence ends. A sequence layout starts, as a clamp does, is not the reader's.
/** @param {Element} box */
export const readerScrolls = (box) => Boolean(sequences.get(box)?.reader);
/** @param {(box: Element) => void} listener */
export function watchScrollEnds(listener) {
  endListeners.add(listener);
  return () => endListeners.delete(listener);
}
