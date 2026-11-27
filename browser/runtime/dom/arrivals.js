// Compiled from arrivals.ts by build/typescript.mjs; edit that file.
/* Elements of one kind, held while they stand in the page, and the stages they stand in.

   Some of the runtime's paint belongs to an element for as long as it stands, whoever
   put it there: an external link's mark, and the bounded block that is a reading
   region. What produces those elements is open-ended (the served document, a
   revision patched in, a thread's message, any widget's render), so no list of
   producers can call each owner. `watchArrivals(selector, attributes, { arrive, leave })`
   watches for them instead:

   - `arrive(el)` runs for each match present when the watch starts and each one added
     since, however deep in what was added, shadow stages included. It runs again when
     a watched attribute changes, and when the nodes beside the element change: its own
     children, or a sibling added or removed next to it. That is where an owner's paint
     stands, so a render that keeps the element and drops the paint hands the element
     back to be painted again. `arrive` is therefore idempotent, and cheap for an
     element whose paint still stands.
   - `leave(el)` runs once for an element that has arrived and no longer stands or
     matches. Mutation records describe intermediate moves: an element removed and added
     back in one batch has not left, so leaving is decided once the batch is read, from
     where the element stands then.

   `arriveBatch(elements)` may replace `arrive` where an owner must read all matching
   elements before writing any of them. Each initial stage and mutation delivery is
   one batch; an explicit offer is a batch of one. `watchArrivals` returns `offer(el)`,
   which decides one element at once rather than at the next mutation delivery. It
   first reads the mutations already made as a batch, so a decision made now never
   runs ahead of a departure made before it. Called with no element it only reads
   them, for an owner whose readers ask what stands now (readings/reading-regions.js).

   An element's connection lifetime is one such watch over the elements a subscription
   stands on, which can be any element: `watchOwner(owner, {connect, disconnect})`
   connects while the owner stands and
   disconnects once a batch shows it gone, so a move within one batch keeps it. A new
   owner connects through `offer`, and a batch decides its departures before its
   arrivals, so whatever left before an owner connects has released first: a revision
   evicts a replaced widget before its replacement connects, and a registration only
   one element may hold passes from one to the other. A connection also ends the
   batch, so an element removed before it and put back after it leaves and returns.
   The runtime's own subscriptions (data, projections, widget controllers) and the
   host of declared elements (host/element-integration.js) hold it directly.
   Widgets hold it through `whileConnected`, for resources, and `frameFor`, for
   scheduled paints, which `widget-api.js` exports in its place.

   Present means in the document, the page's body and the chrome after it alike, or in
   a declared shadow stage whose host is connected. No observer crosses a shadow boundary on its own, so shadow-stage.js, the
   one door a stage is built through, hands each one it fills to `watchArrivalsIn`. A
   record names only the outermost node it moved, and what that node holds is found by
   walking down from it, through open roots and stages; a closed root is entered only
   once it is a stage, as `adoptShadowStage` makes one, which `widget-api.js` doesn't
   export. So a stage inside a page script's or a package's own closed root is heard
   only by records of its own, and moving that root's host neither arrives nor leaves
   what the stage holds. No scroll or scroll end crosses a shadow boundary either, so this module hears the document's and
   every stage's, and those of any other tree a module enrolls (`hearScrollsIn`). A
   protocol event dispatched without the options that carry it to Leaf's listeners is
   lost the same way, in silence, so the document and each stage report one
   (`reportUnheardIn`). Its
   writes include the reading of the page with boxes scrolled elsewhere and put back in
   one task (`readScrolled`).

   A script's write of a box's scroll offset is heard as it is made, whichever script
   makes it: this module wraps the browser's own entry points for one, `scrollTo`,
   `scroll` and `scrollBy` on an element and on the window, the `scrollTop` and
   `scrollLeft` setters, and `scrollIntoView`, which writes the offsets of the boxes
   that scroll its target (`heardWrite`). The platform tells a page of a write only by a
   `scroll` event at the next rendering update, which for a write made in a frame
   callback or a resize delivery comes after that frame has painted, and the event says
   a box moved, never that a script moved it. Heard only there, a write is nobody's
   until that event and the browser's own motion from it to its `scrollend`
   (`browserScrolls`): a strip a script scrolled in a frame callback painted that frame
   without the mark on the edge its content had passed (reach.js), no scroll was under
   way and none was waiting to be drawn (`scrolling`, `scrollDrawn`), in Chromium 159
   and Firefox 159. A function of Leaf's own for the write (`setScroll`) closes that
   only for the code that imports it, which a page's script and another vendor's
   component never do. The wrap changes nothing a call does; it records the move the
   call made (`wrote`). Every other scroll is still heard by its events alone: a smooth
   write, which moves the box later, and a reveal made any other way, as a focus or a
   fragment makes one. So in a shadow tree nobody enrolled, whose events this
   module doesn't hear, a write's scroll ends after the quiet spell and a smooth one
   goes unheard.

   This module is the stages' one registry (`liveStages`), held weakly: a stage outlives
   its widget only as garbage. A stage built while its host was detached arrives with the
   host. */
import {
  composedParentNode,
  isElement,
  openRoot,
  renderedParent,
  shadowHost,
  treesUnder,
} from "../lib/shadow-tree.js";
import { cancelRender, nextFrame, nextRender } from "../lib/frame-pass.js";
import { scrollMoves } from "../lib/scroll-range.js";
import {
  COMMANDS,
  CONNECT,
  DEFER,
  HOLD,
  LAYOUT,
  PREVIEW,
  WALK,
} from "../lib/widget-events.js";
import { reportFailure } from "../lib/failure.js";

/** The elements a watch holds: whether `is` one, and every one `within` a tree. */

const watches = new Set();
const stageRefs = new Set();
// Each stage by its host, closed ones included, which no host answers through
// `shadowRoot`.
const hostStages = new WeakMap();
export const stageOf = (host) => hostStages.get(host) ?? null;
const owners = new WeakMap();
let offerOwner;

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
export function whileConnected(owner, start) {
  let disconnect = () => {};
  return watchOwner(owner, {
    connect() {
      const controller = new AbortController();
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

export const isStage = (root) => {
  const host = shadowHost(root);
  return host !== null && hostStages.get(host) === root;
};

const stands = (el) => {
  const root = el.getRootNode();
  return root === document || (isStage(root) && root.host.isConnected);
};

// An owner (`watchOwner`) can be any element, so finding the owners in what a mutation
// added visits every element there, and offers only the owners.
const ownerKind = {
  is: (el) => owners.has(el),
  *within(root) {
    for (const el of root.querySelectorAll("*")) if (owners.has(el)) yield el;
  },
};

// Every match in what a record names, the stages inside it included, found from the
// node down (`treesUnder`), so a record costs what it names rather than the stages the
// page holds. The walk passes through every tree this module can see, including open
// roots that are no stage, since a stage can stand inside one; only the node's own tree
// and the stages hold matches. A closed root is seen only once it is enrolled as a stage
// (`adoptShadowStage`, shadow-stage.js), so a stage behind one that isn't is heard only
// by records of its own.
function* matching(node, kind) {
  if (!isElement(node)) return;
  if (kind.is(node)) yield node;
  for (const tree of treesUnder(node, seenRoot))
    if (tree === node || isStage(tree)) yield* kind.within(tree);
}
// The tree a host holds that this module can see: its open root, or its closed stage.
const seenRoot = (host) => openRoot(host) ?? hostStages.get(host) ?? null;
// Whether none of `node`'s composed ancestors is among `nodes`.
const outermost = (node, nodes) => {
  for (let at = composedParentNode(node); at; at = composedParentNode(at))
    if (nodes.has(at)) return false;
  return true;
};

/** @param watcher Each arrival goes to `arriveBatch` where there is one, else to `arrive`. */
export const watchArrivals = (selector, attributes, watcher) =>
  watchKind(
    {
      is: (el) => el.matches(selector),
      within: (root) => root.querySelectorAll(selector),
    },
    attributes,
    watcher,
  );

function watchKind(kind, attributes, { arrive, arriveBatch, leave }) {
  const arrived = new WeakSet();
  // Every departure a batch shows is decided before any arrival in it.
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
  const offer = (el) => {
    if (stands(el) && kind.is(el)) {
      arrived.add(el);
      if (arriveBatch) arriveBatch([el]);
      else arrive(el);
    } else if (arrived.delete(el)) leave(el);
  };
  const beside = (node) =>
    isElement(node) && (arrived.has(node) || kind.is(node)) ? [node] : [];
  // A node a batch added inside another node it added is found by that node's walk, so
  // a script that appends nested elements one by one walks each once; removals likewise.
  const read = (records) => {
    const offered = new Set();
    const added = new Set(records.flatMap((record) => [...record.addedNodes]));
    const removed = new Set(records.flatMap((record) => [...record.removedNodes]));
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
        if (outermost(node, added))
          for (const el of matching(node, kind)) offered.add(el);
      for (const node of record.removedNodes)
        if (outermost(node, removed))
          for (const el of matching(node, kind)) if (arrived.has(el)) offered.add(el);
    }
    offerMany(offered);
  };
  const observer = new MutationObserver(read);
  const watch = { kind, attributes, observer, offerMany };
  watches.add(watch);
  for (const root of [document.documentElement, ...liveStages()]) enroll(watch, root);
  return (el) => {
    const made = observer.takeRecords();
    if (made.length) read(made);
    if (el) offer(el);
  };
}

function enroll({ kind, attributes, observer, offerMany }, root) {
  observer.observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: attributes,
  });
  offerMany(kind.within(root));
}

export function watchArrivalsIn(stage) {
  if (hostStages.get(stage.host) === stage) return;
  hostStages.set(stage.host, stage);
  stageRefs.add(new WeakRef(stage));
  for (const watch of watches) enroll(watch, stage);
  hearScrollsIn(stage);
  reportUnheardIn(stage);
}

// The events of the widget protocol that Leaf hears at the document or the window
// (lib/widget-events.js) reach it only as they bubble, and out of a shadow tree only
// where they are composed. One dispatched without those options tells Leaf nothing,
// and nothing else says so: a hold never begins, and a revision replaces the nodes
// under the user's hand. Each tree reports such an event as the failure of the element
// that dispatched it, which the page's errors then name: the document one that does
// not bubble, and a stage one that would not leave it. `lf-preview` Leaf hears as it
// starts down from the document, bubbling or not, so only a stage reports it.
//
// Only these trees are heard. An event that stays inside any other shadow root, one a
// page's script attached or an element opened without saying `lf-connect`, reaches
// neither Leaf nor this report.
const BUBBLED = [COMMANDS, CONNECT, DEFER, HOLD, LAYOUT, WALK];
function reportUnheardIn(root) {
  const staged = root !== document;
  const report = (event) => {
    const [origin] = event.composedPath();
    if (!isElement(origin) || (staged ? event.composed : event.bubbles)) return;
    reportFailure(
      origin,
      new Error(
        `\`${event.type}\` did not reach Leaf, which hears it as it bubbles to the document: dispatch it with { bubbles: true, composed: true }`,
      ),
    );
  };
  for (const type of staged ? [...BUBBLED, PREVIEW] : BUBBLED)
    root.addEventListener(type, report, { capture: true });
}
reportUnheardIn(document);

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
const scrollListeners = new Set();
const SCROLL = { capture: true, passive: true };
function announceScroll(box) {
  if (box) {
    heardAt.set(box, standing(box));
    inSequence(box);
  }
  for (const listener of scrollListeners) listener(box);
}
// Put a box at an offset at once, the runtime's own write, and publish the position that
// will paint. Native scroll events arrive too late for writes in an animation frame or
// resize delivery.
//
// A write that would leave the box where it stands writes nothing
// (lib/scroll-range.js, `scrollMoves`, says what such a write would do), so a writer may
// restate a position as often as it likes, as `keeps` lets one restate a DOM value.
// Stopping a scroll is a write of its own (`stopWhereItStands`).
export function setScroll(box, to) {
  const { scrollTop, scrollLeft } = box;
  if (!scrollMoves(box, to)) return;
  unheardWrite(box, { ...to, behavior: "instant" });
  placed.set(box, { top: box.scrollTop, left: box.scrollLeft });
  wrote(box, scrollTop, scrollLeft);
}
// Record a write that took `box` from `top` and `left` at once: the box is where a
// script put it (`placed`), unless the write `places` nothing, the position is announced
// before it paints, and readers of the whole scene wait for it to be drawn
// (`scrollDrawn`). A write that left the box where it stood records nothing: the
// browser moves the box later, as for a smooth write, or not at all.
function wrote(box, top, left, places = true) {
  if (box.scrollTop === top && box.scrollLeft === left) return;
  if (places) placed.set(box, { top: box.scrollTop, left: box.scrollLeft });
  drawLater();
  announceScroll(box);
}
// The browser's own scroll writes, heard (the header says why): each call is made as
// written, and a move it made at once is recorded as `setScroll` records its own. So a
// package or a page's script writes `box.scrollTo(…)`, and a component Leaf never saw
// is heard too.
//
// - The hearing changes nothing a call does. It makes a write that leaves the box where
//   it stands, which `setScroll` drops: dropping one takes predicting where each call's
//   arguments put the box, and a wrong prediction would lose a script's write. A writer
//   that may name the position its box holds asks first (lib/scroll-range.js,
//   `scrollMoves`). The caller gets what the browser's call returns, as Chromium
//   returns a promise of the scroll's end. Nor does a failure in what hears the write
//   reach the caller, whose call the browser would not have failed: it is reported once
//   the call has returned.
// - A write into a scroll the browser drives leaves the box the browser's
//   (`browserScrolls`), as it was while such a write went unheard. CodeMirror's measure
//   corrects its scroller's offset as the reader scrolls it; read as the script's, that
//   box would be one a hold on the reader's place could move back under their wheel
//   (readings/user-place.js, `holdUserPlace`).
// - The runtime's own writers record their own writes, each its own way, so theirs go
//   unheard (`unheardWrite`), and a write made inside another, as a DOM written in
//   script makes (`scrollTo` there sets `scrollTop`), is part of that one.
// - A call on something that is no element is the browser's to refuse.
// - Each document has entry points of its own: a live sample's page loads this module
//   and hears its own, and an element made in another document keeps that document's.
let writing = false;

/** @param page Whether the call scrolls the page, as the window's do. */
function hearsWrite(native, page = false) {
  return function heardWrite(...args) {
    const box = page ? document.scrollingElement : this;
    if (writing || !isElement(box)) return native.apply(this, args);
    const { scrollTop, scrollLeft } = box;
    const browser = browserScrolls(box);
    let result;
    writing = true;
    try {
      result = native.apply(this, args);
    } finally {
      writing = false;
    }
    heard(box, scrollTop, scrollLeft, !browser);
    return result;
  };
}
// Record a write the hearing made for a caller (`wrote`). What fails here is reported
// once that call has returned.
function heard(box, top, left, places) {
  try {
    wrote(box, top, left, places);
  } catch (error) {
    queueMicrotask(() => {
      throw error;
    });
  }
}
for (const method of ["scrollTo", "scroll", "scrollBy"]) {
  Element.prototype[method] = hearsWrite(Element.prototype[method]);
  window[method] = hearsWrite(window[method], true);
}
for (const offset of ["scrollTop", "scrollLeft"]) {
  const native = Object.getOwnPropertyDescriptor(Element.prototype, offset);
  if (native?.set)
    Object.defineProperty(Element.prototype, offset, {
      ...native,
      set: hearsWrite(native.set),
    });
}
// A reveal writes the offsets of the boxes that scroll its target, the page's among
// them. So the hearing notes where the target and each box it is drawn in stand, makes
// the call, and records each one the call moved. A target slotted into a closed shadow
// tree names no slot (`assignedSlot`), so the boxes of that tree go unread, and their
// moves are heard by their events. The call reveals in the documents around this one
// too, as in a live sample's host page, whose own runtime hears that scroll by its
// events.
function hearsReveal(native) {
  return function heardWrite(...args) {
    if (writing || !isElement(this)) return native.apply(this, args);
    const stood = [];
    for (let box = this; box; box = renderedParent(box))
      stood.push({
        box,
        top: box.scrollTop,
        left: box.scrollLeft,
        browser: browserScrolls(box),
      });
    let result;
    writing = true;
    try {
      result = native.apply(this, args);
    } finally {
      writing = false;
    }
    for (const { box, top, left, browser } of stood) heard(box, top, left, !browser);
    return result;
  };
}
{
  const reveals = Element.prototype;
  for (const method of ["scrollIntoView", "scrollIntoViewIfNeeded"]) {
    const native = reveals[method];
    // Firefox lacks scrollIntoViewIfNeeded.
    if (native) reveals[method] = hearsReveal(native);
  }
}
function unheardWrite(box, options) {
  writing = true;
  try {
    box.scrollTo(options);
  } finally {
    writing = false;
  }
}
// A script's scroll write is drawn by the rendering update after it, and a reading of the
// whole scene waits for that update (`scrollDrawn`): what flows in the box moves with the
// write, but a box CSS anchors to that content, as a thread card is (css-anchors.js),
// takes the write only as that update lays the page out (notes/browser-support.md, "A
// reveal of an anchored fixed box before the next frame in Chromium"), and Chromium can
// apply one last compositor scroll after a stop (`stopWhereItStands`). Read in between,
// the card a walk is bringing over its margin entry still stands where the walk left
// it, so the Go-to map `g` armed as the walk lands would name the entry the card covers,
// and read again at the scroll's end, which comes before that update, would name it
// again (readings/key-badges/hints.js). Two frame callbacks enclose the update. A reader waits for the
// writes made before it asks, not for later ones, so a log a stream keeps at its end
// holds no reading back for as long as it streams.
let undrawn = null;
function drawLater() {
  const write = (undrawn = Promise.withResolvers());
  nextFrame(() =>
    nextFrame(() => {
      write.resolve();
      if (undrawn === write) undrawn = null;
    }),
  );
}
// Null where every scroll a script wrote is drawn, else the promise of the latest.
export const scrollDrawn = () => undrawn?.promise ?? null;
// Stop the scroll the browser drives in a box, leaving the box where it stands, as a
// landing does before it places its destination (scrolling.js, `stopBrowserScroll`)
// and a glide before it takes over a wheel's motion (`glideTo`). It is the one scroll
// write meant to move nothing, which the write watch knows by this name
// (tests/write_watch.js, `EXPECTED_SCROLLS`). An instant write alone stops too little:
// no instant write, even one that moves the box, stops the smooth scroll a key such as
// PageDown sets off, in Chromium or Firefox, and Firefox doesn't stop any smooth scroll
// for a write of the position the page last saw (Chromium 158 and Firefox 159). So a
// `m` pressed as PageDown moved the page lost its landing to PageDown. A smooth write
// takes the box from whatever moves it, in both, and the instant one after ends that
// write's own motion where the box stands.
export function stopWhereItStands(box) {
  const at = { top: box.scrollTop, left: box.scrollLeft };
  unheardWrite(box, { ...at, behavior: "smooth" });
  unheardWrite(box, { ...at, behavior: "instant" });
  placed.set(box, at);
  heardAt.set(box, standing(box));
  drawLater();
}
// Read the page with each box in `at` scrolled to the offset it names: every box is
// written, `read` runs, and every box goes back where it stood before the task ends, so
// no frame draws it there. The browser lays a box's content out as a scroll write
// lands, sticky boxes, their holders' ends, transforms and nested scrollers included,
// so a read just after is exact (Chromium 159, Firefox 159), where a model of that
// layout needs a stuck box's own place, which Firefox can't read (geometry.js,
// `stuckShift`). A box Leaf anchors (css-anchors.js) takes a write only at the next
// frame (notes/browser-support.md, "A reveal of an anchored fixed box before the next
// frame in Chromium"), so past one its anchor's holder is what to read
// (readings/scroll-containers.js, `carrying`). `read` only reads: a write of its own would be
// undone.
//
// Each box costs a write and a write back, a few hundredths of a millisecond with the
// read, and one `scroll` and one `scrollend` at the next rendering update. A write also
// stops a smooth scroll a script set going in the box (Chromium and Firefox) and
// Firefox's rubber band of a flick into its edge, though not a key's, as PageDown's. So
// the only boxes written are those a glide of Leaf's is moving (scrolling.js,
// `whereGlidesLand`), which nothing else moves: their events fold into those of the
// glide's own writes, or read as a frame of the glide that moved nothing, and the
// glide holds the box's scroll sequence open (`holdScroll`), so they end nothing.
export function readScrolled(at, read) {
  const stood = [];
  try {
    for (const [box, top] of at) {
      if (!scrollMoves(box, { top })) continue;
      stood.push([box, box.scrollTop]);
      unheardWrite(box, { top, behavior: "instant" });
    }
    return read();
  } finally {
    for (const [box, top] of stood)
      if (box.scrollTop !== top) unheardWrite(box, { top, behavior: "instant" });
  }
}
const hearing = new WeakSet();
export function hearScrollsIn(root) {
  if (hearing.has(root)) return;
  hearing.add(root);
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
export function watchScrolls(listener) {
  scrollListeners.add(listener);
  return () => scrollListeners.delete(listener);
}

// Each box's scroll sequence, from its first scroll until it ends: at its `scrollend`,
// or, where none will come, after a quiet spell of SETTLE_MS and two rendering updates
// with no scroll in the box. Chromium, Firefox and WebKit send one for every move that
// lands, a script's, a clamp's and an anchoring adjustment's included, but none for an
// input that moves nothing, a box that leaves mid-scroll or Chromium's stop of a smooth
// scroll, nor for Playwright's wheel in Firefox and WebKit. The spell needs
// both: Firefox's main thread hears its smooth scroll's frames late, and a busy page
// delays the updates that carry a scroll's events past any clock. A Firefox starved of
// CPU can outlast both, applying a key's scroll well after the key and pausing
// longer than the spell between its frames, so there the spell can end the reader's
// scroll before or while it moves.
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
// asks (features/version.js reads it).
const SETTLE_MS = 80;
const endListeners = new Set();

// Each box whose sequence runs, with how many of its scrolls have been heard, when the
// last one was, and where the box stood when the reader's input started it
// (`startReaderScroll`).
const sequences = new Map();
const holds = new Map();
// Where a script last put each box (`setScroll`), until the box's sequence ends.
const placed = new WeakMap();
// Where the page last heard each box stand: at its scroll events, Leaf's own writes and
// stops (`startReaderScroll`).
const heardAt = new WeakMap();
function sequenceIn(box) {
  let sequence = sequences.get(box);
  if (!sequence) sequences.set(box, (sequence = { heard: 0, at: performance.now() }));
  return sequence;
}
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
function endSequence(box) {
  if (!sequences.has(box) || holds.has(box)) return;
  sequences.delete(box);
  placed.delete(box);
  for (const listener of endListeners) listener(box);
}
// Hold `box`'s sequence open from now until the returned release. A holder that has
// landed, its last write leaving the box where it stood, as a glide's last frames move
// it less than a pixel, owes the box no scroll event and no `scrollend`, so its release
// ends the sequence. Any other release ends it as a glide's last frame would: at the
// `scrollend` the last write owes, or after the quiet spell.
export function holdScroll(box) {
  holds.set(box, (holds.get(box) ?? 0) + 1);
  sequenceIn(box);
  let held = true;
  return (landed = false) => {
    if (!held) return;
    held = false;
    const left = (holds.get(box) ?? 1) - 1;
    if (left) {
      holds.set(box, left);
      return;
    }
    holds.delete(box);
    if (landed) endSequence(box);
    else inSequence(box);
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
const standing = (box) => ({
  top: box.scrollTop,
  left: box.scrollLeft,
  fromEnd: fromEnd(box),
});
const fromEnd = (box) => box.scrollHeight - box.clientHeight - box.scrollTop;
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
export const browserScrolls = (box) => {
  if (!sequences.has(box) || holds.has(box)) return false;
  const at = placed.get(box);
  return !at || at.top !== box.scrollTop || at.left !== box.scrollLeft;
};
// Whether the reader's input has set `box` scrolling: a sequence it started
// (`startReaderScroll`), from the input, before the browser moves the box, until the
// sequence ends. A sequence layout starts, as a clamp does, is not the reader's.
export const readerScrolls = (box) => Boolean(sequences.get(box)?.reader);
export function watchScrollEnds(listener) {
  endListeners.add(listener);
  return () => endListeners.delete(listener);
}
