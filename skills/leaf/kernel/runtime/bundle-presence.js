import {
  layoutBox,
  pageDocument
} from "./bundle-passage-facts.js";
import {
  LAYOUT,
  PAGE_PAINT_ATTRIBUTE,
  announceScroll,
  landingBand,
  pagePresented,
  reportPageError,
  scrollsBy,
  setRuntimeRootAttribute,
  shadowRootsIn,
  shownRect,
  skipped,
  userScrollport,
  watchOwner,
  watchScrolls
} from "./bundle-page-paint.js";
import {
  applicationPresented
} from "./bundle-semantic-state.js";
import {
  LENT_REACH_STOP,
  TEXT_BOX,
  afterScript,
  deepFocus,
  keeps,
  nextFrame,
  nextRender,
  onStanding,
  pressing,
  renderedParent,
  renderedUnder,
  renderingState,
  sizeObserver,
  tabStops,
  under,
  upFrom,
  wearsLentStop
} from "./bundle-frame-visibility.js";
import {
  outsideReading
} from "./bundle-queued-work.js";

// runtime/presence.js
var clockSkew = 0;
var ticks = /* @__PURE__ */ new Set();
var onTick = (moved) => {
  ticks.add(moved);
  return () => ticks.delete(moved);
};
var serverNow = () => Date.now() + clockSkew;
var saidNow = () => new Date(serverNow()).toISOString();
var clockValue = (read) => outsideReading(() => read(serverNow()), onTick).read();
function readingPaint(owner, draw) {
  let painted = false;
  let key;
  let pending = null;
  const running = /* @__PURE__ */ new Set();
  let stopped = false;
  const stopLifetime = watchOwner(owner, {
    disconnect() {
      for (const mark of running) mark.cut = true;
      if (pending) painted = false;
      pending = null;
    }
  });
  const failed = (reason) => reportPageError(
    reason,
    `paint failed for ${owner.localName}${owner.id ? `#${owner.id}` : ""}`
  );
  let last = null;
  const render = (...args) => {
    last = args;
    pending = null;
    let result;
    try {
      result = draw(...args);
    } catch (error) {
      failed(error);
      const refused = Promise.reject(error);
      refused.catch(() => {
      });
      return refused;
    }
    if (typeof result?.then === "function") {
      const mark = pending = {};
      running.add(mark);
      const settled = (reason, rejected) => {
        running.delete(mark);
        mark.cut ||= !owner.isConnected;
        if (pending === mark) {
          pending = null;
          if (mark.cut) painted = false;
        }
        if (rejected && !mark.cut) failed(reason);
      };
      result.then(
        () => settled(),
        (reason) => settled(reason, true)
      );
    }
    return result;
  };
  const owes = (next) => !painted || key !== next;
  const paint = (next, ...args) => {
    if (stopped || !owes(next)) return void 0;
    painted = true;
    key = next;
    return render(...args);
  };
  paint.owes = owes;
  paint.forget = () => {
    painted = false;
  };
  paint.refresh = () => {
    if (stopped) return void 0;
    if (owner.isConnected) return last ? render(...last) : void 0;
    painted = false;
  };
  paint.stop = () => {
    stopped = true;
    stopLifetime();
  };
  return paint;
}
async function tickClock(reportError) {
  const round = {};
  const settled = await Promise.allSettled(
    [...ticks].map(async (moved) => moved(round))
  );
  for (const result of settled)
    if (result.status === "rejected") reportError(result.reason, "clock paint failed");
}
var observeServerNow = (now) => {
  if (now) clockSkew = Date.parse(now) - Date.now();
};
var JUST_NOW = "just now";
var age = (ts, compact) => clockValue((now) => {
  if (!ts) return "";
  const secs = Math.max(0, (now - new Date(ts).getTime()) / 1e3);
  if (secs < 45) return compact ? "now" : JUST_NOW;
  const [count, unit] = secs < 3600 ? [Math.round(secs / 60), "m"] : secs < 86400 ? [Math.round(secs / 3600), "h"] : [Math.round(secs / 86400), "d"];
  return `${count}${unit}${compact ? "" : " ago"}`;
});
var ago = (ts) => age(ts, false);
var shortAgo = (ts) => age(ts, true);
var workingGrace = null;
var observeWorkingGrace = (ms) => {
  workingGrace = ms;
};
var quietSince = (ts) => clockValue(
  (now) => workingGrace !== null && Boolean(ts) && now - new Date(ts).getTime() >= workingGrace
);
var activityTransitionAt = (state) => Math.min(
  ...[state?.activity, ...(state?.others ?? []).map((entry) => entry?.activity)].filter((activity) => activity?.next_transition_at).map((activity) => Date.parse(activity.next_transition_at))
);
var activityTransitionDue = (state) => serverNow() >= activityTransitionAt(state);

// runtime/presentation.js
var UPGRADE = "lf-upgraded";
function markPageUpgraded() {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.upgraded, "1");
  document.dispatchEvent(new Event(UPGRADE));
}
var { promise: presented, resolve: resolvePresented } = Promise.withResolvers();
function markPagePresented() {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.presented, "1");
  resolvePresented();
}
var arriving = /* @__PURE__ */ new Set();
var restarts = /* @__PURE__ */ new Set();
function deferredArrival(work) {
  arriving.add(work);
  const landed = () => arriving.delete(work);
  work.then(landed, landed);
  for (const restart of restarts) restart();
  restarts.clear();
  return work;
}
async function whenArrived() {
  while (arriving.size) await Promise.allSettled(arriving);
}
var whenArriving = () => arriving.size ? Promise.resolve() : new Promise((restart) => restarts.add(restart));
var afterPresentation = (work) => deferredArrival(presented.then(work));
var appliedState = null;
function markStateApplied(state) {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.reading, state.reading);
  appliedState = {
    reading: state.reading,
    taken: state.taken,
    lapses: activityTransitionAt(state)
  };
}
var stamp = (name) => document.body.getAttribute(PAGE_PAINT_ATTRIBUTE[name]);
var READINESS = [
  ["upgraded", () => stamp("upgraded") === "1"],
  ["log", () => stamp("applied") !== null],
  [
    "state",
    (held) => !held || appliedState?.taken >= held.taken || appliedState?.reading === held.reading && held.taken * 1e3 < appliedState.lapses
  ],
  ["presented", () => pagePresented() && applicationPresented()],
  ["arrived", () => arriving.size === 0],
  ["rendering", () => Object.values(renderingState()).every(Boolean)]
];
var READINESS_STAGES = new Set(READINESS.map(([stage]) => stage));
function pageReadiness(held = null, through = "rendering") {
  if (!READINESS_STAGES.has(through))
    throw new TypeError(`no readiness stage named ${through}`);
  for (const [stage, met] of READINESS) {
    if (!met(held)) return stage;
    if (stage === through) return null;
  }
}
var PRESENTATION = "lf-presentation";
var PAGE_INTERFACE = "lf-page-interface";
async function settlePageInterface() {
  const pending = [];
  const present = (promise) => {
    if (!promise?.then)
      throw new TypeError("Page interface presentation must be a promise");
    pending.push(promise);
    return promise;
  };
  document.dispatchEvent(new CustomEvent(PAGE_INTERFACE, { detail: { present } }));
  for (const result of await Promise.allSettled(pending)) {
    if (result.status === "rejected")
      reportPageError(result.reason, "Page interface failed");
  }
}

// runtime/scrolling.js
var pageScroller = document.scrollingElement;
var moving = /* @__PURE__ */ new WeakMap();
function stopScroll(boxes) {
  const stopped = [...boxes].filter((box) => moving.has(box)).map((box) => [box, moving.get(box)]);
  if (!stopped.length) return null;
  for (const [box] of stopped)
    box.scrollTo({
      left: box.scrollLeft,
      top: box.scrollTop,
      behavior: "instant"
    });
  return new Promise(
    (resolve) => nextFrame(
      () => nextFrame(() => {
        for (const [box, sequence] of stopped)
          if (moving.get(box) === sequence) moving.delete(box);
        resolve(void 0);
      })
    )
  );
}
var choices = 0;
var chosen = /* @__PURE__ */ new WeakMap();
var kept = /* @__PURE__ */ new WeakMap();
var scrollChoices = () => choices;
var chosenSince = (box, count) => (chosen.get(box) ?? 0) > count;
var chooseScroll = (box) => chosen.set(box, ++choices);
function startScroll(box) {
  moving.set(box, { glide: true });
  chooseScroll(box);
}
var eventScroller = (target) => target === document ? pageScroller : target;
document.addEventListener(
  "scroll",
  ({ target }) => {
    const box = eventScroller(target);
    if (moving.get(box)?.glide) return;
    const sequence = { glide: false };
    moving.set(box, sequence);
    nextFrame(
      () => nextFrame(() => {
        if (moving.get(box) === sequence) moving.delete(box);
      })
    );
  },
  {
    capture: true,
    passive: true
  }
);
function placeKept(...boxes) {
  for (const box of boxes) kept.set(box, box.scrollTop);
}
document.addEventListener(
  "scrollend",
  ({ target }) => {
    const box = eventScroller(target);
    moving.delete(box);
    if (kept.get(box) !== box.scrollTop) chooseScroll(box);
    kept.delete(box);
  },
  { capture: true, passive: true }
);
var scrollLimit = (box) => Math.max(0, box.scrollHeight - box.clientHeight);
var SCROLL_SLACK = 2;
var atScrollEnd = (box) => scrollLimit(box) - box.scrollTop <= SCROLL_SLACK;
var scrollToEnd = (box, behavior = "instant") => {
  const before = box.scrollTop;
  if (behavior !== "instant" && !atScrollEnd(box)) startScroll(box);
  box.scrollTo({ top: box.scrollHeight, behavior });
  if (behavior === "instant" && box.scrollTop !== before) announceScroll(box);
};
var aims = /* @__PURE__ */ new WeakMap();
var moveScrollerBy = (box, top, behavior = "instant") => {
  const before = box.scrollTop;
  const aim = box.scrollTop + top;
  if (Math.abs(top) >= 0.5) {
    if (behavior !== "instant" && reachable(box, top)) startScroll(box);
    box.scrollBy({ top, behavior });
  }
  if (behavior === "instant" && Math.abs(aim - box.scrollTop) < 1)
    aims.set(box, { aim, at: box.scrollTop });
  else aims.delete(box);
  if (behavior === "instant" && box.scrollTop !== before) announceScroll(box);
};
var aimedTop = (box) => {
  const kept2 = aims.get(box);
  return kept2?.at === box.scrollTop ? kept2.aim : box.scrollTop;
};
var reachable = (box, top) => Math.max(-box.scrollTop, Math.min(scrollLimit(box) - box.scrollTop, top));

// runtime/reach.js
var overflows = (el) => !el.hasAttribute("hidden") && (el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight);
var holdsOwnStop = (el) => tabStops(el).length > 0;
var mayScroll = /* @__PURE__ */ new Map();
var claimedStops = /* @__PURE__ */ new WeakSet();
function lendStop(el) {
  keeps(el, LENT_REACH_STOP, "");
  keeps(el, "tabindex", 0);
}
function claimReachStop(el) {
  if (claimedStops.has(el)) return;
  const authored = mayScroll.has(el) ? mayScroll.get(el) : el.getAttribute("tabindex");
  if (authored !== null) return;
  claimedStops.add(el);
  lendStop(el);
}
function releaseReachStop(el) {
  if (!claimedStops.has(el)) return;
  claimedStops.delete(el);
  if (el.getAttribute("tabindex") !== "0") {
    keeps(el, LENT_REACH_STOP, null);
    return;
  }
  if (mayScroll.has(el) && overflows(el) && !holdsOwnStop(el)) lendStop(el);
  else returnStop(el, null);
}
function returnStop(el, authored) {
  keeps(el, LENT_REACH_STOP, null);
  if (el.getAttribute("tabindex") === "0")
    keeps(el, "tabindex", wearsLentStop(el) ? -1 : authored);
}
var sideways = /* @__PURE__ */ new Set();
var downwards = /* @__PURE__ */ new Set();
watchScrolls((box) => {
  if (downwards.has(box)) paintReadingReach(box);
  if (sideways.has(box)) paintSidewaysReach(box);
});
function reachReadingScroller(el) {
  downwards.add(el);
  watchReach(el);
  paintReadingReach(el);
  return () => {
    downwards.delete(el);
    if (!watched(el)) unwatchReach(el);
    afterScript(() => {
      if (!downwards.has(el)) keeps(el, PAGE_PAINT_ATTRIBUTE.moreBelow, null);
    });
  };
}
var readingPaints = /* @__PURE__ */ new Set();
function paintReadingReach(el) {
  readingPaints.add(el);
  afterScript(paintReadingReachNow);
}
function paintReadingReachNow() {
  const pending = [...readingPaints];
  readingPaints.clear();
  for (const el of pending) {
    if (!downwards.has(el) || unpainted(el)) continue;
    const style = getComputedStyle(el);
    const scrolling = userScrollport(style.overflowY);
    keeps(
      el,
      PAGE_PAINT_ATTRIBUTE.moreBelow,
      scrolling && !atScrollEnd(el) ? "" : null
    );
  }
}
var waiting = /* @__PURE__ */ new Set();
function reachScrollers(root) {
  sweep(root);
  paintReach();
}
var wait = (el) => {
  waiting.add(el);
  reachSizes.observe(el);
};
function sweep(root) {
  if (root.nodeType === Node.ELEMENT_NODE && skipped(root)) return wait(root);
  const trees = new Set(shadowRootsIn(root));
  const read = [];
  const walk = (scope) => {
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_ELEMENT, (el2) => {
      if (!skipped(el2)) return NodeFilter.FILTER_ACCEPT;
      wait(el2);
      return NodeFilter.FILTER_REJECT;
    });
    let el = scope.nodeType === Node.ELEMENT_NODE ? scope : walker.nextNode();
    for (; el; el = walker.nextNode()) {
      const style = getComputedStyle(el);
      const { overflowX, overflowY, position, containerType } = style;
      const top = position === "sticky" ? style.top : "auto";
      read.push([el, { overflowX, overflowY, position, top, containerType }]);
      if (trees.has(el.shadowRoot)) walk(el.shadowRoot);
    }
  };
  walk(root);
  for (const [el, style] of read) {
    const waited = waiting.delete(el);
    classify(el, style);
    if (waited) release(el);
  }
}
function paintSlot(el, style) {
  const sticks = style.position === "sticky";
  const scrolls2 = scrollsBy(style) && !sticks && !el.matches(TEXT_BOX);
  const across = userScrollport(style.overflowX) && !userScrollport(style.overflowY);
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrolls, scrolls2 ? across ? "across" : "" : null);
  el.toggleAttribute(PAGE_PAINT_ATTRIBUTE.sticks, sticks && style.top !== "auto");
}
function classify(el, style) {
  asked.add(el);
  noteQueries(el, style);
  paintSlot(el, style);
  if (el.hasAttribute("hidden") || !userScrollport(style.overflowX) && !userScrollport(style.overflowY)) {
    if (!mayScroll.has(el)) return;
    const authored = mayScroll.get(el);
    mayScroll.delete(el);
    if (!claimedStops.has(el)) returnStop(el, authored);
    if (!watched(el)) unwatchReach(el);
    return;
  }
  if (style.position === "static" && !el.matches(TEXT_BOX) && !el.hasAttribute(PAGE_PAINT_ATTRIBUTE.holds))
    el.setAttribute(PAGE_PAINT_ATTRIBUTE.holds, "1");
  if (userScrollport(style.overflowX) && !el.matches(TEXT_BOX) && !sideways.has(el)) {
    sideways.add(el);
    watchReach(el);
  }
  if (!mayScroll.has(el)) {
    if (el.tabIndex >= 0 && !claimedStops.has(el)) return;
    mayScroll.set(
      el,
      wearsLentStop(el) || claimedStops.has(el) ? null : el.getAttribute("tabindex")
    );
  }
  watchReach(el);
}
var childrenWatched = /* @__PURE__ */ new WeakSet();
var childLists = new MutationObserver((records) => {
  for (const { target, addedNodes, removedNodes } of records) {
    if (!childrenWatched.has(target)) continue;
    for (const node of removedNodes)
      if (node.nodeType === Node.ELEMENT_NODE) release(node);
    for (const node of addedNodes)
      if (node.nodeType === Node.ELEMENT_NODE)
        reachSizes.observe(
          /** @type {Element} */
          node
        );
  }
});
function watchReach(el) {
  reachSizes.observe(el);
  if (childrenWatched.has(el)) return;
  childrenWatched.add(el);
  for (const child of el.children) reachSizes.observe(child);
  childLists.observe(el, { childList: true });
}
function unwatchReach(el) {
  const heldChildren = childrenWatched.delete(el);
  release(el);
  if (heldChildren) for (const child of el.children) release(child);
}
function release(node) {
  if (!watched(node) && !childrenWatched.has(node.parentElement))
    reachSizes.unobserve(node);
}
var depth = (el) => {
  let levels = 0;
  for (let node = el; node; node = upFrom(node)) levels++;
  return levels;
};
var watched = (el) => mayScroll.has(el) || sideways.has(el) || downwards.has(el) || waiting.has(el);
var reachSizes = sizeObserver(() => paintReach());
function paintSidewaysReach(el) {
  afterScript(() => {
    if (!sideways.has(el) || unpainted(el)) return;
    const style = getComputedStyle(el);
    const scrolling = userScrollport(style.overflowX) && el.scrollWidth > el.clientWidth + 1;
    const maximum = Math.max(0, el.scrollWidth - el.clientWidth);
    const raw = Math.abs(el.scrollLeft);
    const position = Math.min(maximum, Math.max(0, raw));
    keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, scrolling ? style.direction : null);
    el.toggleAttribute(
      PAGE_PAINT_ATTRIBUTE.moreBefore,
      scrolling && position > SCROLL_SLACK
    );
    el.toggleAttribute(
      PAGE_PAINT_ATTRIBUTE.moreAfter,
      scrolling && position < maximum - SCROLL_SLACK
    );
  });
}
function gone(el) {
  if (el.isConnected) return false;
  mayScroll.delete(el);
  sideways.delete(el);
  downwards.delete(el);
  waiting.delete(el);
  if (queried.delete(el)) queries.unobserve(el);
  unwatchReach(el);
  return true;
}
var unpainted = (el) => gone(el) || skipped(el);
function paintReach() {
  afterScript(paintReachNow);
}
function paintReachNow() {
  for (const el of waiting) if (!unpainted(el)) sweep(el);
  const levels = new Map([...mayScroll.keys()].map((el) => [el, depth(el)]));
  for (const [el, authored] of [...mayScroll].sort(
    ([a], [b]) => levels.get(b) - levels.get(a)
  )) {
    if (unpainted(el)) continue;
    if (claimedStops.has(el)) continue;
    if (overflows(el) && !holdsOwnStop(el)) lendStop(el);
    else returnStop(el, authored);
  }
  for (const el of sideways) paintSidewaysReach(el);
  for (const el of downwards) paintReadingReach(el);
}
var STILL_MS = 100;
var PLAYING_MS = 1e3;
var rereads = /* @__PURE__ */ new Map();
var lastTick = -Infinity;
var tickFrame = 0;
var tickTimer = 0;
function reread(root, byContainer) {
  const now = performance.now();
  const asked2 = rereads.get(root) ?? { at: null, moved: null, movingSince: null };
  if (!byContainer) asked2.at = now;
  else {
    if (asked2.moved === null || now - asked2.moved >= STILL_MS) asked2.movingSince = now;
    asked2.moved = now;
  }
  rereads.set(root, asked2);
  waitToReread();
}
var playing = (asked2) => asked2.moved - asked2.movingSince > PLAYING_MS;
var counts = (asked2) => asked2.at !== null || asked2.moved !== null && !playing(asked2);
function waitToReread() {
  const pending = [...rereads.values()];
  if (pending.some(counts)) tickFrame ||= nextFrame(rereadFrame);
  else if (pending.length) tickTimer ||= setTimeout(rereadTimer, STILL_MS);
}
function rereadFrame() {
  tickFrame = 0;
  const since = lastTick;
  lastTick = performance.now();
  rereadDue(lastTick, since);
}
function rereadTimer() {
  tickTimer = 0;
  rereadDue(performance.now(), -Infinity);
}
function rereadDue(now, since) {
  const roots = [];
  for (const [root, asked2] of rereads) {
    let due = false;
    if (asked2.at !== null && asked2.at < since) {
      asked2.at = null;
      due = true;
    }
    const still = playing(asked2) ? now - asked2.moved >= STILL_MS : asked2.moved < since;
    if (asked2.moved !== null && still) {
      asked2.moved = null;
      due = true;
    }
    if (due) roots.push(root);
    if (asked2.at === null && asked2.moved === null) rereads.delete(root);
  }
  const outermost = roots.filter((el) => {
    for (let node = upFrom(el); node; node = upFrom(node))
      if (roots.includes(node)) return false;
    return !unpainted(el);
  });
  for (const root of outermost) sweep(root);
  if (outermost.length) paintReach();
  waitToReread();
}
var queried = /* @__PURE__ */ new Map();
var unobserved = /* @__PURE__ */ new Set();
function noteQueries(el, { containerType }) {
  const kinds = containerType.split(" ");
  const both = kinds.includes("size");
  if (!both && !kinds.includes("inline-size")) {
    if (queried.delete(el)) queries.unobserve(el);
    return;
  }
  if (queried.get(el)?.both === both) return;
  queried.set(el, { both, size: null });
  if (!unobserved.size) nextRender(observeQueried);
  unobserved.add(el);
}
function observeQueried() {
  for (const el of unobserved) if (queried.has(el)) queries.observe(el);
  unobserved.clear();
}
var queries = sizeObserver(
  (entries) => {
    for (const { target, contentBoxSize } of entries) {
      const query = queried.get(target);
      if (!query || gone(target)) continue;
      const [{ inlineSize, blockSize }] = contentBoxSize;
      const size = query.both ? `${inlineSize} ${blockSize}` : `${inlineSize}`;
      if (query.size !== null && query.size !== size) reread(target, true);
      query.size = size;
    }
  },
  { counted: false }
);
addEventListener("resize", () => reread(document.body));
var asked = /* @__PURE__ */ new WeakSet();
var reached = (el) => {
  for (let node = el; node; node = upFrom(node)) if (asked.has(node)) return true;
  return false;
};
document.addEventListener(LAYOUT, (event) => {
  const [changed] = (
    /** @type {Node[]} */
    event.composedPath()
  );
  if (changed?.nodeType === Node.ELEMENT_NODE && reached(changed)) reread(changed);
  paintReach();
});

// runtime/reading-regions.js
var regions = /* @__PURE__ */ new Map();
var transitionWatchers = /* @__PURE__ */ new Set();
var depthOf = (node) => {
  let depth2 = 0;
  for (let current = node; current; current = renderedParent(current)) depth2 += 1;
  return depth2;
};
var live = (region) => region?.host?.isConnected && region.body?.isConnected;
var concealed = (region) => region.host.hidden || region.host.closest?.("[hidden], [aria-hidden='true']") !== null || region.body.matches("details:not([open])");
var hidden = (region) => !live(region) || concealed(region) || shownRect(region.host, /* @__PURE__ */ new Map()) === null;
var regionRecord = (region) => ({
  id: region.id,
  host: region.host,
  body: region.body,
  subject: region.subject
});
function compoundReadingRegionId(owner, localName) {
  if (!owner?.id || !/^[a-z][a-z0-9-]*$/.test(localName ?? ""))
    throw new Error("leaf: a compound reading region needs an owner id and local name");
  return `lf-region:${owner.id}:${localName}`;
}
function registerReadingRegion({ id, host, body }) {
  if (typeof id !== "string" || !id || !host || !body)
    throw new Error("leaf: a reading region needs id, host, and body");
  if (live(regions.get(id)))
    throw new Error(`leaf: reading region ${id} is already live`);
  const region = {
    id,
    host,
    body,
    subject: void 0,
    scroller: null,
    width: null,
    away: false
  };
  const stopReaching = reachReadingScroller(body);
  regions.set(id, region);
  sizes.observe(host);
  return () => {
    if (regions.get(id) === region) regions.delete(id);
    sizes.unobserve(host);
    stopReaching();
  };
}
var layoutRegions = /* @__PURE__ */ new Map();
var marked = (box) => box.checkVisibility() && getComputedStyle(box).getPropertyValue("--lf-reading-region").trim() === "layout";
function syncLayoutRegion() {
  const main = layoutBox();
  const bodies = main ? [...main.children].flatMap((child) => {
    if (marked(child)) return [[child, child.id]];
    const only = child.childElementCount === 1 ? child.firstElementChild : null;
    return only && marked(only) ? [[only, only.id || child.id]] : [];
  }) : [];
  let unnamed = 0;
  const ids = new Map(
    bodies.map(([body, name]) => [
      body,
      name ? `lf-region:layout#${name}` : `lf-region:layout@${unnamed++}`
    ])
  );
  for (const [body, region] of layoutRegions)
    if (ids.get(body) !== region.id) {
      region.stop();
      layoutRegions.delete(body);
    }
  for (const [body, id] of ids)
    if (!layoutRegions.has(body))
      layoutRegions.set(body, {
        id,
        stop: registerReadingRegion({ id, host: body, body })
      });
}
function showReadingSubject(id, subject, render) {
  const region = regions.get(id);
  if (!live(region) || region.subject === subject) {
    if (region) region.subject = subject;
    return render();
  }
  notify({ phase: "leaving", region: regionRecord(region) });
  region.subject = subject;
  const rendered = render();
  notify({ phase: "showing", region: regionRecord(region) });
  return rendered;
}
var readingRegion = (id) => {
  const region = regions.get(id);
  return live(region) ? regionRecord(region) : void 0;
};
var readingRegions = () => [...regions.values()].filter(live).map(regionRecord);
var unconcealedReadingRegions = () => [...regions.values()].filter((region) => live(region) && !concealed(region) && !skipped(region.body)).map(regionRecord);
var regionAt = (node) => {
  const region = [...regions.values()].filter((candidate) => live(candidate) && renderedUnder(node, candidate.host)).sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return region;
};
var readingRegionFor = (node) => {
  const region = regionAt(node);
  return region && regionRecord(region);
};
var recentRegionId = null;
var pageRegionId = null;
var readingInputReaders = /* @__PURE__ */ new Set();
var onReadingInput = (read) => readingInputReaders.add(read);
var readingInput = (node) => {
  for (const read of readingInputReaders) read(node);
};
var actedAt = (at, arriving2) => {
  const region = readingRegionFor(at);
  if (region) {
    recentRegionId = region.id;
    if (under(region.host, pageDocument())) pageRegionId = region.id;
  } else if ((at === document.body || under(at, pageDocument())) && !(arriving2 && at === document.body && pressing()))
    recentRegionId = pageRegionId = null;
};
for (const type of ["pointerdown", "wheel", "touchstart", "click"])
  addEventListener(
    type,
    (event) => {
      const at = event.composedPath()[0];
      if (type !== "click") actedAt(at, false);
      else if (event.isTrusted && /** @type {MouseEvent} */
      event.button === 0)
        readingInput(at);
    },
    { capture: true, passive: true }
  );
onStanding((node, cause) => {
  if (node) actedAt(node, true);
  if (node && cause === "step") readingInput(node);
});
var recentReadingRegion = () => readingRegion(recentRegionId);
var shown = (region) => region?.host.checkVisibility() ? region : void 0;
var pageReadingRegion = () => {
  const at = deepFocus();
  if (under(at, pageDocument())) return readingRegionFor(at);
  return shown(readingRegion(pageRegionId));
};
var userReadingRegion = () => {
  const at = deepFocus();
  const region = readingRegionFor(at);
  if (region || under(at, pageDocument())) return region;
  return shown(recentReadingRegion()) ?? pageReadingRegion();
};
var containingReadingRegionFor = (node) => {
  let region = regionAt(node);
  while (region) {
    if (renderedUnder(node, region.body)) return regionRecord(region);
    region = regionAt(renderedParent(region.host));
  }
  return void 0;
};
var asRegion = (regionOrNode) => typeof regionOrNode === "string" ? regions.get(regionOrNode) : regions.get(regionOrNode?.id) ?? regions.get(readingRegionFor(regionOrNode)?.id);
var scrolls = (box) => userScrollport(getComputedStyle(box).overflowY);
var readingPosture = (regionOrNode) => {
  const region = asRegion(regionOrNode);
  return region && live(region) && scrolls(region.body) ? "bounded" : "flow";
};
function effectiveScroller(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region) return pageScroller;
  if (readingPosture(region) === "bounded") return region.body;
  const containing = [...regions.values()].filter(
    (candidate) => candidate !== region && live(candidate) && renderedUnder(region.host, candidate.body)
  ).sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return containing ? effectiveScroller(containing) : pageScroller;
}
var scrollerFor = (el) => {
  const region = containingReadingRegionFor(el);
  return region ? effectiveScroller(region) : pageScroller;
};
function* scrollersOf(node) {
  for (let box = scrollerFor(node); ; box = scrollerFor(renderedParent(box))) {
    for (let at = node; at !== box; at = renderedParent(at))
      if (!at || getComputedStyle(at).position === "fixed") return;
    yield box;
    if (box === pageScroller) return;
    node = box;
  }
}
function* scrollChainOf(node) {
  let last = null;
  for (last of scrollersOf(node)) yield last;
  if (last !== pageScroller) yield pageScroller;
}
function shownRegionBounds(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region || hidden(region)) return null;
  return shownRect(region.body, /* @__PURE__ */ new Map());
}
function watchReadingRegionTransitions(listener) {
  transitionWatchers.add(listener);
  return () => transitionWatchers.delete(listener);
}
var notify = (detail) => {
  for (const listener of transitionWatchers) listener(detail);
};
var compositionTransitions = /* @__PURE__ */ new Map();
async function preserveReadingRegions(owner, change) {
  const transition = {
    owner,
    regions: readingRegions().filter((region) => under(region.host, owner))
  };
  notify({
    ...transition,
    phase: "before",
    retained: compositionTransitions.has(owner)
  });
  compositionTransitions.set(owner, transition);
  let completed = false;
  try {
    await change();
    completed = true;
  } finally {
    if (compositionTransitions.get(owner) === transition) {
      compositionTransitions.delete(owner);
      notify({
        ...transition,
        phase: "after",
        cancelled: !completed || !owner.isConnected
      });
    }
  }
}
var asSeen = (region, scroller, width) => region.scroller === scroller && region.width === width;
var viewportHeight = innerHeight;
var pageSeen = null;
var pageGeometry = () => ({
  width: pageScroller.clientWidth,
  band: landingBand(pageScroller)?.top ?? 0
});
var pageMoved = (now = pageGeometry()) => {
  if (pageSeen === null) return false;
  if (now.width !== pageSeen.width) return true;
  pageSeen = now;
  return false;
};
var regionsSettled = () => viewportHeight === innerHeight && !pageMoved() && [...regions.values()].every(
  (region) => !live(region) || !region.scroller || !shown(region) || asSeen(region, effectiveScroller(region), region.host.offsetWidth)
);
function measureRegions() {
  const viewportChanged = viewportHeight !== innerHeight;
  viewportHeight = innerHeight;
  const shifted = [];
  for (const region of regions.values()) {
    if (!live(region) || !shown(region)) continue;
    const scroller = effectiveScroller(region);
    const width = region.host.offsetWidth;
    const away = concealed(region);
    if (region.scroller && (viewportChanged || !asSeen(region, scroller, width)))
      shifted.push({
        region: regionRecord(region),
        from: region.scroller,
        to: scroller,
        returned: Boolean(region.away) && !away
      });
    region.scroller = scroller;
    region.width = width;
    region.away = away;
  }
  const now = pageGeometry();
  if (pageMoved(now)) shifted.push({ region: null, band: now.band - pageSeen.band });
  pageSeen = now;
  if (shifted.length) notify({ phase: "shift", shifted });
}
var sizes = sizeObserver(measureRegions);
sizes.observe(pageScroller);
addEventListener("resize", () => nextRender(measureRegions), { passive: true });

export {
  saidNow,
  clockValue,
  readingPaint,
  tickClock,
  observeServerNow,
  JUST_NOW,
  ago,
  shortAgo,
  observeWorkingGrace,
  quietSince,
  activityTransitionDue,
  UPGRADE,
  markPageUpgraded,
  markPagePresented,
  deferredArrival,
  whenArrived,
  whenArriving,
  afterPresentation,
  markStateApplied,
  pageReadiness,
  PRESENTATION,
  PAGE_INTERFACE,
  settlePageInterface,
  pageScroller,
  stopScroll,
  scrollChoices,
  chosenSince,
  startScroll,
  placeKept,
  scrollLimit,
  SCROLL_SLACK,
  atScrollEnd,
  scrollToEnd,
  moveScrollerBy,
  aimedTop,
  reachable,
  claimReachStop,
  releaseReachStop,
  reachScrollers,
  compoundReadingRegionId,
  registerReadingRegion,
  syncLayoutRegion,
  showReadingSubject,
  readingRegion,
  readingRegions,
  unconcealedReadingRegions,
  readingRegionFor,
  onReadingInput,
  recentReadingRegion,
  pageReadingRegion,
  userReadingRegion,
  containingReadingRegionFor,
  readingPosture,
  effectiveScroller,
  scrollerFor,
  scrollersOf,
  scrollChainOf,
  shownRegionBounds,
  watchReadingRegionTransitions,
  preserveReadingRegions,
  regionsSettled
};
