import {
  layoutBox,
  pageDocument
} from "./bundle-passage-facts.js";
import {
  LAYOUT,
  PAGE_PAINT_ATTRIBUTE,
  landingBand,
  pagePresented,
  reportPageError,
  scrollsBy,
  setRuntimeRootAttribute,
  shadowRootsIn,
  shownRect,
  skipped,
  userScrollport,
  watchArrivals
} from "./bundle-page-paint.js";
import {
  LENT_REACH_STOP,
  TEXT_BOX,
  afterScript,
  deepFocus,
  keeps,
  nextFrame,
  nextRender,
  onCurrentLocation,
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
  applicationPresented
} from "./bundle-semantic-state.js";
import {
  J,
  Z
} from "./bundle-queued-work.js";

// runtime/presence.js
var clockSkew = 0;
var pulse = Z(0);
var serverNow = () => Date.now() + clockSkew;
var saidNow = () => new Date(serverNow()).toISOString();
var clockValue = (read) => J(() => {
  pulse.value;
  return read(serverNow());
}).value;
async function tickClock(reportError) {
  try {
    pulse.value += 1;
  } catch (error) {
    reportError(error, "clock paint failed");
  }
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
  if (behavior !== "instant" && !atScrollEnd(box)) startScroll(box);
  box.scrollTo({ top: box.scrollHeight, behavior });
};
var aims = /* @__PURE__ */ new WeakMap();
var moveScrollerBy = (box, top, behavior = "instant") => {
  const aim = box.scrollTop + top;
  if (Math.abs(top) >= 0.5) {
    if (behavior !== "instant" && reachable(box, top)) startScroll(box);
    box.scrollBy({ top, behavior });
  }
  if (behavior === "instant" && Math.abs(aim - box.scrollTop) < 1)
    aims.set(box, { aim, at: box.scrollTop });
  else aims.delete(box);
};
var aimedTop = (box) => {
  const kept2 = aims.get(box);
  return kept2?.at === box.scrollTop ? kept2.aim : box.scrollTop;
};
var reachable = (box, top) => Math.max(-box.scrollTop, Math.min(scrollLimit(box) - box.scrollTop, top));

// runtime/reach.js
var SCROLL_SURFACE = ".scroll";
var seenClasses = /* @__PURE__ */ new WeakMap();
var watchingSurfaces = false;
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
var sideways = /* @__PURE__ */ new Map();
var downwards = /* @__PURE__ */ new Map();
var readingScrolled = (event) => paintReadingReach(event.currentTarget);
var sidewaysScrolled = (event) => paintSidewaysReach(event.currentTarget, true);
function reachReadingScroller(el, paintContinuation) {
  el.classList.toggle("scroll", true);
  downwards.set(el, paintContinuation);
  sweep(el);
  paintReach();
  watchReach(el);
  el.addEventListener("scroll", readingScrolled, { passive: true });
  paintReadingReach(el);
  return () => {
    downwards.delete(el);
    if (!watched(el)) unwatchReach(el);
    el.removeEventListener("scroll", readingScrolled);
    afterScript(() => {
      if (!downwards.has(el)) {
        keeps(el, PAGE_PAINT_ATTRIBUTE.moreBelow, null);
        paintContinuation?.(false);
      }
    });
  };
}
var readingPaints = /* @__PURE__ */ new Set();
var readingPaintQueued = false;
function paintReadingReach(el) {
  readingPaints.add(el);
  if (readingPaintQueued) return;
  readingPaintQueued = true;
  nextRender(paintReadingReachNow);
}
function paintReadingReachNow() {
  readingPaintQueued = false;
  const pending = [...readingPaints];
  readingPaints.clear();
  for (const el of pending) {
    if (!downwards.has(el) || unpainted(el)) continue;
    const style = getComputedStyle(el);
    const scrolling = userScrollport(style.overflowY);
    downwards.get(el)?.(scrolling && el.scrollTop > SCROLL_SLACK);
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
  if (watchingSurfaces) return;
  watchingSurfaces = true;
  watchArrivals(SCROLL_SURFACE, ["class"], {
    arriveBatch(surfaces) {
      for (const el of surfaces) {
        const classes = el.getAttribute("class");
        if (seenClasses.get(el) === classes) continue;
        seenClasses.set(el, classes);
        reread(el);
      }
    },
    leave: forgetSurface
  });
}
var wait = (el) => {
  waiting.add(el);
  reachSizes.observe(el);
};
function sweep(root) {
  const scopes = [root];
  for (const scope of scopes) scopes.push(...shadowRootsIn(scope));
  const surfaces = scopes.flatMap((scope) => [
    ...scope.nodeType === Node.ELEMENT_NODE && scope.matches(SCROLL_SURFACE) ? [scope] : [],
    ...scope.querySelectorAll(SCROLL_SURFACE)
  ]);
  const read = [];
  const containers = /* @__PURE__ */ new Set();
  for (const el of surfaces) {
    seenClasses.set(el, el.getAttribute("class"));
    if (skipped(el)) {
      wait(el);
      continue;
    }
    const style = getComputedStyle(el);
    read.push([
      el,
      {
        overflowX: style.overflowX,
        overflowY: style.overflowY,
        position: style.position,
        direction: style.direction
      }
    ]);
    for (let node = el; node?.nodeType === Node.ELEMENT_NODE; node = upFrom(node)) {
      if (containers.has(node)) break;
      containers.add(node);
    }
  }
  const queriesRead = [...containers].map((el) => [
    el,
    { containerType: getComputedStyle(el).containerType }
  ]);
  for (const [el, style] of queriesRead) noteQueries(el, style);
  for (const [el, style] of read) {
    const waited = waiting.delete(el);
    classify(el, style);
    if (waited) release(el);
  }
  asked.add(root);
}
function forgetSurface(el) {
  seenClasses.delete(el);
  if (mayScroll.has(el)) {
    const authored = mayScroll.get(el);
    mayScroll.delete(el);
    if (!claimedStops.has(el)) returnStop(el, authored);
  }
  if (sideways.delete(el)) el.removeEventListener("scroll", sidewaysScrolled);
  waiting.delete(el);
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrolls, null);
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, null);
  keeps(el, PAGE_PAINT_ATTRIBUTE.moreBefore, null);
  keeps(el, PAGE_PAINT_ATTRIBUTE.moreAfter, null);
  if (!watched(el)) unwatchReach(el);
}
function paintSlot(el, style) {
  const sticks = style.position === "sticky";
  const scrolls2 = scrollsBy(style) && !sticks && !el.matches(TEXT_BOX);
  const across = userScrollport(style.overflowX) && !userScrollport(style.overflowY);
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrolls, scrolls2 ? across ? "across" : "" : null);
}
function classify(el, style) {
  asked.add(el);
  paintSlot(el, style);
  if (!userScrollport(style.overflowX) && sideways.delete(el)) {
    el.removeEventListener("scroll", sidewaysScrolled);
    keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, null);
    keeps(el, PAGE_PAINT_ATTRIBUTE.moreBefore, null);
    keeps(el, PAGE_PAINT_ATTRIBUTE.moreAfter, null);
  }
  if (el.hasAttribute("hidden") || !userScrollport(style.overflowX) && !userScrollport(style.overflowY)) {
    if (!mayScroll.has(el)) return;
    const authored = mayScroll.get(el);
    mayScroll.delete(el);
    if (!claimedStops.has(el)) returnStop(el, authored);
    if (!watched(el)) unwatchReach(el);
    return;
  }
  if (userScrollport(style.overflowX) && !el.matches(TEXT_BOX)) {
    if (!sideways.has(el)) {
      watchReach(el);
      el.addEventListener("scroll", sidewaysScrolled, { passive: true });
    }
    sideways.set(el, style.direction);
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
function paintSidewaysReach(el, readStyle = false) {
  afterScript(() => {
    if (!sideways.has(el) || unpainted(el)) return;
    const direction = readStyle ? getComputedStyle(el).direction : sideways.get(el);
    if (readStyle) sideways.set(el, direction);
    const scrolling = el.scrollWidth > el.clientWidth + 1;
    const maximum = Math.max(0, el.scrollWidth - el.clientWidth);
    const raw = Math.abs(el.scrollLeft);
    const position = Math.min(maximum, Math.max(0, raw));
    keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, scrolling ? direction : null);
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
  if (sideways.delete(el)) el.removeEventListener("scroll", sidewaysScrolled);
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
  for (const el of sideways.keys()) paintSidewaysReach(el);
  for (const el of downwards.keys()) paintReadingReach(el);
}
var rereads = /* @__PURE__ */ new Set();
var rereadQueued = false;
function reread(root) {
  rereads.add(root);
  if (rereadQueued) return;
  rereadQueued = true;
  nextRender(() => {
    rereadQueued = false;
    const roots = [...rereads];
    rereads.clear();
    const due = new Set(roots);
    for (const root2 of roots) {
      if (!root2.isConnected) continue;
      let covered = false;
      for (let ancestor = upFrom(root2); ancestor; ancestor = upFrom(ancestor))
        if (due.has(ancestor)) {
          covered = true;
          break;
        }
      if (covered) continue;
      sweep(root2);
    }
    paintReach();
  });
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
      if (query.size !== null && query.size !== size) reread(target);
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
function registerReadingRegion({
  id,
  host,
  body,
  paintContinuation = void 0
}) {
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
  const stopReaching = reachReadingScroller(body, paintContinuation);
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
onCurrentLocation((node, cause) => {
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
var regionScrollBehavior = (regionOrNode) => {
  const region = asRegion(regionOrNode);
  return region && live(region) && scrolls(region.body) ? "bounded" : "flow";
};
function effectiveScroller(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region) return pageScroller;
  if (regionScrollBehavior(region) === "bounded") return region.body;
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
  regionScrollBehavior,
  effectiveScroller,
  scrollerFor,
  scrollersOf,
  scrollChainOf,
  shownRegionBounds,
  watchReadingRegionTransitions,
  preserveReadingRegions,
  regionsSettled
};
