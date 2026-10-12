/* Elements of one kind, held while they stand in the page, and the stages they stand in.

   Some of the runtime's paint belongs to an element for as long as it stands, whoever
   put it there: an external link's mark and note, and the bounded block that is a
   reading region. What produces those elements is open-ended (the served document, a
   revision patched in, a thread's message, any widget's render), so no list of
   producers can call each owner. `watchArrivals(selector, attributes, { arrive, leave })`
   watches for them instead:

   - `arrive(el)` runs for each match standing when the watch starts and each one added
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
   which decides one element at once rather than at the next mutation delivery.

   An element's connection lifetime is one such watch over every element:
   `watchOwner(owner, {connect, disconnect})` connects while the owner stands and
   disconnects once a batch shows it gone, so a move within one batch keeps it. The
   runtime's own subscriptions (data, projections, widget controllers) and clock paints
   (`clocked` and `readingPaint` in presence.js) hold it directly.
   Widgets hold it through `whileConnected`, for resources, and `frameFor`, for
   scheduled paints, which `widget-api.js` exports in its place.

   Standing means in `document.body`, or in a declared shadow stage whose host is
   connected. No observer crosses a shadow boundary on its own, so shadow-stage.js, the
   one door a stage is built through, hands each one it fills to `watchArrivalsIn`. No
   scroll crosses one either, so `watchScrolls` hears the document's and every stage's.
   This module is the stages' one registry (`liveStages`), held weakly: a stage outlives
   its widget only as garbage. A stage built while its host was detached arrives with the
   host. */
import { under } from "./shadow.js";
import { cancelRender, nextRender } from "./rendering.js";

const watches = new Set();
const stages = new WeakSet();
const stageRefs = new Set();
const owners = new WeakMap();
let offerOwner;

// Independent subscriptions share their element's connection lifetime. The arrival
// batch decides whether it actually left, so an in-document move retains them.
export function watchOwner(owner, lifecycle) {
  let connected = false;
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
  let subscriptions = owners.get(owner);
  if (!subscriptions) owners.set(owner, (subscriptions = new Set()));
  if (!offerOwner) {
    const notify = (element, method) => {
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
    };
    offerOwner = watchArrivals("*", [], {
      arrive: (element) => notify(element, "connect"),
      leave: (element) => notify(element, "disconnect"),
    });
  }
  // A synchronous connection can begin and end before the first arrival batch.
  // Offer the owner before setup so that batch still knows its resources must leave.
  if (owner.isConnected) offerOwner(owner);
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
  let held;
  return watchOwner(owner, {
    connect() {
      const controller = new AbortController();
      held = { controller, cleanup: null };
      // Hold the signal before setup: watchOwner also disconnects a failed start.
      held.cleanup = start(controller.signal);
    },
    disconnect() {
      const current = held;
      held = null;
      current.controller.abort();
      current.cleanup?.();
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

const stands = (el) => {
  const root = el.getRootNode();
  return root === document
    ? document.body.contains(el)
    : stages.has(root) && root.host.isConnected;
};

// Every match in what a record names, the stages inside it included.
function* matching(node, selector) {
  if (node?.nodeType !== Node.ELEMENT_NODE) return;
  if (node.matches(selector)) yield node;
  yield* node.querySelectorAll(selector);
  for (const stage of liveStages())
    if (under(stage.host, node)) yield* stage.querySelectorAll(selector);
}

export function watchArrivals(selector, attributes, { arrive, arriveBatch, leave }) {
  const arrived = new WeakSet();
  const offerMany = (elements) => {
    if (!arriveBatch) {
      for (const el of elements) offer(el);
      return;
    }
    const standing = [];
    for (const el of elements) {
      if (stands(el) && el.matches(selector)) {
        arrived.add(el);
        standing.push(el);
      } else if (arrived.delete(el)) leave(el);
    }
    if (standing.length) arriveBatch(standing);
  };
  const offer = (el) => {
    if (stands(el) && el.matches(selector)) {
      arrived.add(el);
      if (arriveBatch) arriveBatch([el]);
      else arrive(el);
    } else if (arrived.delete(el)) leave(el);
  };
  const beside = (node) =>
    node?.nodeType === Node.ELEMENT_NODE &&
    (arrived.has(node) || node.matches(selector))
      ? [node]
      : [];
  const observer = new MutationObserver((records) => {
    const offered = new Set();
    for (const record of records) {
      if (record.type === "attributes") {
        offered.add(record.target);
        continue;
      }
      for (const el of [
        ...beside(record.target),
        ...beside(record.previousSibling),
        ...beside(record.nextSibling),
      ])
        offered.add(el);
      for (const node of record.addedNodes)
        for (const el of matching(node, selector)) offered.add(el);
      for (const node of record.removedNodes)
        for (const el of matching(node, selector)) if (arrived.has(el)) offered.add(el);
    }
    offerMany(offered);
  });
  const watch = { selector, attributes, observer, offerMany };
  watches.add(watch);
  for (const root of [document.body, ...liveStages()]) enroll(watch, root);
  return offer;
}

function enroll({ selector, attributes, observer, offerMany }, root) {
  observer.observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: attributes,
  });
  offerMany(root.querySelectorAll(selector));
}

export function watchArrivalsIn(stage) {
  if (stages.has(stage)) return;
  stages.add(stage);
  stageRefs.add(new WeakRef(stage));
  for (const watch of watches) enroll(watch, stage);
  stage.addEventListener("scroll", heardIn(stage), SCROLL);
}

// Every scroll in the page, a stage's included: `scroll` is not composed, so a scroller
// inside a shadow stage reaches no listener outside it. Each stage hears its own
// scrollers for every listener, through one listener of its own that holds nothing but
// the stage, and only its own, since one slotted into it from the document reaches the
// document too.
const scrollListeners = new Set();
const SCROLL = { capture: true, passive: true };
const heardIn = (stage) => (event) => {
  if (event.target.getRootNode() !== stage) return;
  for (const listener of scrollListeners) listener(event);
};
export function watchScrolls(listener) {
  scrollListeners.add(listener);
  document.addEventListener("scroll", listener, SCROLL);
  return () => {
    scrollListeners.delete(listener);
    document.removeEventListener("scroll", listener, SCROLL);
  };
}

// Whether a scroll is in flight anywhere in the page, from its first frame until it
// settles, and each settle as it comes: a `scrollend` where the browser sends one, else
// a settle after the last scroll frame, since a scroll restoration that replaces what
// was scrolling ends without one. A scroll the runtime writes a frame at a time
// (navigation.js, `glideTo`) sends a `scrollend` for each frame, so it holds the flight
// until it lands (`scrollGlides`). What rides a scroll on an anchor is placed again once
// it settles rather than on its frames, where a placement would trail the scroll a
// frame behind.
const SETTLE_MS = 80;
const settleListeners = new Set();
let inFlight = false;
let gliding = false;
let settleTimer = 0;
let trackingScrolls = false;
function settle() {
  if (!inFlight || gliding) return;
  inFlight = false;
  clearTimeout(settleTimer);
  for (const listener of settleListeners) listener();
}
function trackScrolls() {
  if (trackingScrolls) return;
  trackingScrolls = true;
  watchScrolls(() => {
    inFlight = true;
    clearTimeout(settleTimer);
    settleTimer = setTimeout(settle, SETTLE_MS);
  });
  document.addEventListener("scrollend", settle, SCROLL);
}
export function scrollGlides(on) {
  trackScrolls();
  gliding = on;
  if (on) inFlight = true;
  // A glide stopped before it wrote sends nothing more to settle on.
  else if (inFlight) {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(settle, SETTLE_MS);
  }
}
export function scrolling() {
  trackScrolls();
  return inFlight;
}
export function watchScrollEnds(listener) {
  trackScrolls();
  settleListeners.add(listener);
  return () => settleListeners.delete(listener);
}
