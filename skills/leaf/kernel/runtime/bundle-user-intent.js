import {
  aborted,
  commitWidgetDescriptors,
  dataBody,
  rememberAuthoredParents,
  stageAuthoredStates,
  stageWidgetDescriptors
} from "./bundle-widget-upgrade.js";
import {
  isCanonicalMediaUrl,
  readAttachedMedia,
  scopedMediaUrl,
  writeAttachedMedia
} from "./bundle-media.js";
import {
  flashDuration,
  motion,
  scrollBehavior
} from "./bundle-motion.js";
import {
  ADDRESSABLE,
  addressableWord,
  aimTargetAt,
  anchorBox,
  anchorForPassage,
  anchorForRange,
  anchorReading,
  anchorView,
  anchoringIsReady,
  chromeForeground,
  chromeRoot,
  cutFrames,
  datumAimTarget,
  datumLabel,
  followingItsEnd,
  headerLevels,
  localScrollBy,
  marks,
  nameAnchor,
  nameable,
  refreshAnchorView,
  resolveAnchor,
  scrollAxes,
  sectionLabel,
  sectionOf,
  targetElement,
  targetSegments,
  visualPartLabel
} from "./bundle-chrome.js";
import {
  initialOrigin,
  initialSource
} from "./bundle-initial-render.js";
import {
  ago,
  aimedTop,
  atScrollEnd,
  claimReachStop,
  containingReadingRegionFor,
  effectiveScroller,
  moveScrollerBy,
  pageReadingRegion,
  pageScroller,
  placeKept,
  reachScrollers,
  reachable,
  readingRegionFor,
  readingRegions,
  releaseReachStop,
  scrollLimit,
  scrollToEnd,
  scrollerFor,
  scrollersOf,
  shortAgo,
  shownRegionBounds,
  startScroll
} from "./bundle-presence.js";
import {
  setChildLists,
  setChildren
} from "./bundle-stylesheets.js";
import {
  COLLAPSE,
  alignText,
  closestAcross,
  elementById,
  fencePassageParts,
  inChrome,
  labelWords,
  pageBlocks,
  pageDocument,
  pageRange,
  pageText,
  pageWords,
  pointAt,
  quoteFrom,
  rangeOf,
  readingFrom,
  segmentBlock,
  segmentsIn,
  selectEnds,
  selectionBackward,
  spanIn,
  textUnits,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity
} from "./bundle-passage-facts.js";
import {
  PAGE_PAINT_ATTRIBUTE,
  PRESS,
  admitResponse,
  adoptRegistry,
  announce,
  announceScroll,
  bindings,
  checked,
  clampedRow,
  clippedContents,
  clippingAxes,
  commandScope,
  cycledRow,
  declarationFor,
  declareCommandReadiness,
  descriptionOf,
  el,
  elementDeclarations,
  elementsDeclaring,
  growthAfterIsSeen,
  growthIsSeen,
  headerInset,
  holdStatus,
  iconElement,
  iconTemplate,
  inUi,
  inWindowChrome,
  keys,
  landingBand,
  loadShadowRules,
  measure,
  nearestScrollBy,
  notice,
  offer,
  pagePresented,
  paintKeys,
  passErrorsAt,
  placeBox,
  placeHolder,
  plainPress,
  pointerAt,
  pressIsKeyboardActivation,
  projectCommandScope,
  raiseError,
  randomId,
  registry,
  repaint,
  reportPageError,
  revealLayer,
  sameLayer,
  seenRect,
  shownBox,
  shownRect,
  shownWindow,
  skipped,
  stuckBox,
  tagsDeclaring,
  titleOf,
  tokenEntry,
  touchPresses,
  union,
  userScrollport,
  visibleBand,
  watchArrivals,
  watchCommandScopes,
  watchOwner,
  whenNone
} from "./bundle-page-paint.js";
import {
  applicationState,
  attachApplicationPresentation,
  offlineInteractive,
  readApplication,
  readPart,
  runtime,
  runtimeModule,
  runtimeResource,
  whenApplicationPresented,
  whenDocumentPresented,
  whenWidgetsPresented
} from "./bundle-semantic-state.js";
import {
  CARET_KEYS,
  TEXT_FIELD,
  afterScript,
  atLayoutPrecision,
  cancelRender,
  caretAtKey,
  carriedFrom,
  deepFocus,
  drawn,
  focusDestination,
  focused,
  holdFocus,
  holdStanding,
  inputCount,
  keeps,
  keepsHidden,
  layoutPx,
  move,
  nextFrame,
  nextRender,
  onPress,
  onStanding,
  readCaret,
  recentPlaceInput,
  renderedOrder,
  renderedParent,
  renderedUnder,
  ringBox,
  selectsAll,
  sizeObserver,
  standingIn,
  standingNodes,
  standsOn,
  takesLetters,
  under,
  upFrom
} from "./bundle-frame-visibility.js";
import {
  M,
  PENDING,
  bindQueuedWork,
  editable,
  html,
  isElementName,
  isReaction,
  lastMovedAt,
  messageKey,
  moved,
  nothing,
  pendingForParent,
  render,
  repeat,
  sameAnchor,
  seatRoot,
  share,
  threadKey,
  threadNames,
  turns
} from "./bundle-queued-work.js";

// runtime/user-intent.js
var passed = /* @__PURE__ */ new WeakMap();
var passOn = (container, target) => passed.set(target, { container, intent: inputCount() });
var displaced = (source, at) => {
  if (!(source instanceof Node) || !at) return false;
  const via = passed.get(at);
  const carry2 = carriedFrom(at);
  return at.contains(source) || via?.intent === inputCount() && via.container.contains(source) || carry2?.inputs === inputCount() && (carry2.from === source || source.contains(carry2.from));
};
function retainUserIntent({
  source = focused(),
  available: available2 = () => true,
  fallback = null,
  since = inputCount()
} = {}) {
  const retained = since;
  let held = source instanceof Node ? new WeakRef(source) : null;
  const current = () => {
    const at = focused();
    const from = held?.deref();
    const withinSource = from === document.body ? at === document.body : from?.contains(at);
    return available2() && retained === inputCount() && (at === document.body || at === fallback || withinSource || displaced(from, at));
  };
  current.available = available2;
  current.handoff = (move2) => {
    if (!available2() || retained !== inputCount()) return false;
    const moved2 = current();
    if (moved2) move2();
    const at = focused();
    held = at ? new WeakRef(at) : null;
    return moved2 && current();
  };
  return current;
}
function restrictUserIntent(retained, available2) {
  const current = () => available2() && retained();
  current.available = () => available2() && retained.available();
  current.handoff = (move2) => available2() && retained.handoff(move2);
  return current;
}

// runtime/user-place.js
function focusedInView() {
  const node = focused();
  return node && !inWindowChrome(node) && seenRect(node, /* @__PURE__ */ new Map()) && !stuckBox(node) ? node : null;
}
function placeCandidates({ inherited, named, preferred, visible }) {
  const lead = inherited || named[0] || preferred || visible[0];
  const at = visible.indexOf(lead);
  const rest = at < 0 ? visible : [...visible.slice(at + 1), ...visible.slice(0, at + 1)];
  return [...new Set([inherited, ...named, preferred, lead, ...rest].filter(Boolean))];
}
function placeCorrection({
  was,
  now,
  scrollTop,
  limit,
  held,
  withinTask = false
}) {
  const reflowed = withinTask || limit < held.limit && held.scrollTop > limit && scrollTop === limit ? scrollTop - held.scrollTop : 0;
  return now - was - reflowed;
}
var heldScrollers = /* @__PURE__ */ new WeakMap();
var sharedMovement = (moved2, paid) => Math.sign(moved2) === Math.sign(paid) ? Math.sign(paid) * Math.min(Math.abs(moved2), Math.abs(paid)) : 0;
function placeKeeper(scroller, { items, identity, active = () => true, preferred = () => null }) {
  let current = null;
  const owner = {};
  const lease = {
    owner,
    snapshot: () => ({
      hold: current,
      references: current?.references.filter(live) ?? []
    }),
    sync: ({ hold, references }, paid) => {
      if (current !== hold) return;
      for (const reference of references)
        if (live(reference)) reference.contentTop += paid;
      hold.at = { scrollTop: scroller.scrollTop, limit: limit() };
    }
  };
  const limit = () => scrollLimit(scroller);
  const heldBox = (node) => {
    if (!node?.isConnected || !scroller.contains(node) || !node.matches(items) || !node.checkVisibility())
      return null;
    const box = node.getBoundingClientRect();
    return box.width && box.height ? box : null;
  };
  const rendered = (key) => !key ? null : [...scroller.querySelectorAll(items)].find(
    (node) => identity(node) === key && heldBox(node)
  );
  const live = (reference) => {
    if (heldBox(reference.node)) return reference.node;
    const replacement = rendered(reference.key);
    if (replacement) reference.node = replacement;
    return replacement ?? null;
  };
  let returning = 0;
  function claim() {
    if (current?.spans) {
      cancelRender(returning);
      returning = 0;
      scroller.style.setProperty("overflow-anchor", "none");
    } else if (!returning && scroller.style.getPropertyValue("overflow-anchor"))
      returning = nextRender(() => {
        returning = 0;
        if (!heldScrollers.has(scroller))
          scroller.style.removeProperty("overflow-anchor");
      });
  }
  function release2(hold) {
    if (current !== hold) return;
    current = null;
    if (heldScrollers.get(scroller)?.owner === owner) heldScrollers.delete(scroller);
    if (hold.spans) claim();
  }
  function correct(hold) {
    if (current !== hold || !active()) return false;
    const reference = hold.references.find(live);
    if (!reference) return false;
    const now = heldBox(reference.node).top + scroller.scrollTop;
    const was = reference.contentTop;
    const scrollWas = scroller.scrollTop;
    const delta = placeCorrection({
      was,
      now,
      scrollTop: scroller.scrollTop,
      limit: limit(),
      held: hold.at,
      withinTask: !hold.spans
    });
    if (delta) {
      moveScrollerBy(scroller, aimedTop(scroller) - scroller.scrollTop + delta);
      placeKept(scroller);
    }
    for (const candidate of hold.references) {
      const node = live(candidate);
      if (node) candidate.contentTop = heldBox(node).top + scroller.scrollTop;
    }
    hold.at = { scrollTop: scroller.scrollTop, limit: limit() };
    if (hold.borrowed) {
      hold.borrowed.lease.sync(
        hold.borrowed.reading,
        sharedMovement(now - was, scroller.scrollTop - scrollWas)
      );
      hold.borrowed.reading = hold.borrowed.lease.snapshot();
    }
    return true;
  }
  function take({ spans: spans2 = true } = {}) {
    const enclosing = heldScrollers.get(scroller);
    if (enclosing?.owner !== owner && enclosing && spans2) return null;
    const prior = current;
    if (prior) correct(prior);
    current = heldPlace(prior, spans2);
    if (current && enclosing?.owner !== owner && enclosing)
      current.borrowed = { lease: enclosing, reading: enclosing.snapshot() };
    else if (current) heldScrollers.set(scroller, lease);
    else if (enclosing?.owner === owner) heldScrollers.delete(scroller);
    if (spans2 || prior?.spans) claim();
    return current;
  }
  function heldPlace(prior, spans2) {
    if (!active()) return null;
    const band = visibleBand(scroller);
    if (!band) return null;
    const nodes = [...scroller.querySelectorAll(items)];
    const boxes = new Map(nodes.map((node) => [node, node.getBoundingClientRect()]));
    const tops = /* @__PURE__ */ new Map();
    const topFor = (node) => {
      if (!tops.has(node)) tops.set(node, band.top + headerInset(node, scroller));
      return tops.get(node);
    };
    const { x, y } = pointerAt();
    const over = x >= band.left && x <= band.right && y >= band.top && y <= band.bottom;
    const visible = nodes.filter((node) => {
      const box = boxes.get(node);
      return node.checkVisibility() && box.width && box.height && box.bottom > topFor(node) && box.top < band.bottom;
    }).sort((a, b) => boxes.get(a).top - boxes.get(b).top);
    const beginning = visible.filter((node) => boxes.get(node).top >= topFor(node));
    const shown = new Set(visible);
    const pointer = over ? document.elementFromPoint(x, y)?.closest?.(items) : null;
    const focus = focused()?.closest?.(items);
    const named = (recentPlaceInput() === "pointer" ? [pointer, focus] : [focus, pointer]).filter((node) => beginning.includes(node));
    const reading = preferred();
    const candidates = placeCandidates({
      inherited: prior?.references.find(
        (candidate) => live(candidate) && shown.has(candidate.node)
      )?.node,
      named,
      preferred: shown.has(reading) ? reading : null,
      visible: beginning
    });
    const references = [.../* @__PURE__ */ new Set([...candidates, ...visible])].filter((node) => scroller.contains(node)).map((node) => ({
      node,
      key: identity(node),
      contentTop: node.getBoundingClientRect().top + scroller.scrollTop
    }));
    if (!references.length) return null;
    return {
      named: named[0] ?? null,
      references,
      at: { scrollTop: scroller.scrollTop, limit: limit() },
      spans: spans2
    };
  }
  function follow2(hold, following) {
    if (!correct(hold) || !following()) release2(hold);
    else nextFrame(() => follow2(hold, following));
  }
  function finish(hold, following = () => false) {
    if (!hold) return;
    correct(hold);
    if (following()) nextFrame(() => follow2(hold, following));
    else release2(hold);
  }
  function around(mutate) {
    const held = take({ spans: false });
    try {
      return mutate();
    } finally {
      finish(held);
    }
  }
  return { take, finish, around };
}

// runtime/landing-scroll.js
var land = (box, by, behavior) => {
  const { scrollTop, scrollLeft } = box;
  if (behavior !== "instant") startScroll(box);
  box.scrollBy({ ...by, behavior });
  if (behavior === "instant" && (box.scrollTop !== scrollTop || box.scrollLeft !== scrollLeft))
    announceScroll(box);
};
function scrollMargin(where, side = "Top") {
  if (!(where instanceof Range))
    return Number.parseFloat(getComputedStyle(where)[`scrollMargin${side}`]) || 0;
  const edges = [
    where.startContainer.childNodes[where.startOffset],
    where.endContainer.childNodes[where.endOffset - 1]
  ].filter((edge) => edge instanceof Element);
  return edges.length ? Math.max(...edges.map((edge) => scrollMargin(edge, side))) : 0;
}
function shownFor(where) {
  const ring = ringBox(where);
  if (ring === where) return where;
  const box = placeBox(ring);
  const room = roomAround(ring, where);
  return box.height <= room.height && box.width <= room.width ? ring : where;
}
var destinationBox = (where) => placeBox(shownFor(where));
var holderOf = (where) => placeHolder(shownFor(where));
var readingTop = (holder, box) => visibleBand(box, holder)?.top ?? landingBand(box).top;
function topMargin(where, box, holder = holderOf(where)) {
  const band = landingBand(box);
  return Math.max(scrollMargin(where), readingTop(holder, box) - band.top);
}
var landingRoom = (where, until = where) => roomAround(shownFor(where), where, until);
function roomAround(shown, where, until = where) {
  const holder = placeHolder(shown);
  const regions = [...scrollersOf(holder)];
  let { width, height } = shownWindow();
  for (let box = shown instanceof Range ? holder : renderedParent(shown); box instanceof Element; box = renderedParent(box)) {
    const band = (until === where || renderedUnder(until, box)) && landingBand(box);
    if (band) {
      const axes = box === pageScroller ? { x: true, y: true } : clippingAxes(getComputedStyle(box));
      const at = regions.indexOf(box);
      const clearance = at === 0 ? topMargin(where, box, holder) + scrollMargin(until, "Bottom") : at > 0 ? Math.max(0, readingTop(regions[at - 1], box) - band.top) : 0;
      if (axes.x) width = Math.min(width, band.right - band.left);
      if (axes.y) height = Math.min(height, band.bottom - band.top - clearance);
    }
    if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
  }
  return { width, height };
}
function fitsWhole(where) {
  const box = destinationBox(where);
  const room = landingRoom(where);
  return box.height <= room.height && box.width <= room.width;
}
function seesWhole(where, box, out) {
  const seen = seenRect(shownFor(where), /* @__PURE__ */ new Map(), out);
  if (!seen) return false;
  const room = landingRoom(where);
  return (box.height > room.height || seen.top <= out.top && seen.bottom >= out.bottom) && (box.width > room.width || seen.left <= out.left && seen.right >= out.right);
}
function alreadyShown(where) {
  const box = destinationBox(where);
  return seesWhole(where, box, box);
}
function ringShown(where) {
  const box = destinationBox(where);
  const [top, right, bottom, left] = ["Top", "Right", "Bottom", "Left"].map(
    (side) => scrollMargin(where, side)
  );
  return seesWhole(
    where,
    box,
    new DOMRect(
      box.left - left,
      box.top - top,
      box.width + left + right,
      box.height + top + bottom
    )
  );
}
function placementBy(where, block, box, margin) {
  const rect = destinationBox(where);
  const band = landingBand(box);
  const room = band.bottom - band.top;
  const place2 = block === "start" ? margin : block === "end" ? room - rect.height - scrollMargin(where, "Bottom") : Math.max((room - rect.height) / 2, margin);
  const movement = block === "nearest" ? nearestScrollBy(
    rect.top - margin,
    rect.bottom + scrollMargin(where, "Bottom"),
    band.top,
    band.bottom
  ) : rect.top - band.top - place2;
  return movement;
}
function verticalTravel(box, movement) {
  const scale = scrollAxes(box).y.y;
  const local = scale === 0 ? 0 : reachable(box, movement / scale);
  return { local, moved: local * scale };
}
function scrollIntoReadingBand(where, holder, block, behavior) {
  const [box, ...around] = scrollersOf(holder);
  if (!box) return;
  const rect = destinationBox(where);
  const margin = topMargin(where, box);
  let { top, bottom } = rect;
  if (block === "start") {
    top -= margin;
  } else if (block === "end") {
    top = bottom - 1;
    bottom += scrollMargin(where, "Bottom");
  }
  let { local, moved: moved2 } = verticalTravel(box, placementBy(where, block, box, margin));
  if (Math.abs(moved2) >= 1) land(box, { top: local }, behavior);
  let inner = box;
  for (const outer of around) {
    top -= moved2;
    bottom -= moved2;
    const band = landingBand(outer);
    if (!band) return;
    band.top = Math.max(band.top, readingTop(inner, outer));
    if (block === "start") bottom = Math.min(bottom, top + band.bottom - band.top);
    ({ local, moved: moved2 } = verticalTravel(
      outer,
      nearestScrollBy(top, bottom, band.top, band.bottom)
    ));
    if (Math.abs(moved2) >= 1) land(outer, { top: local }, behavior);
    inner = outer;
  }
}
function scrollIntoView(where, { alignment = where, behavior = "auto", block = "start", within: within2 = null } = {}) {
  if (!where) return;
  const holder = holderOf(alignment);
  if (!holder) return;
  const targetScroller = within2 ? null : scrollersOf(holder).next().value;
  let inside = true;
  const start = holderOf(where);
  for (let box = start; box instanceof Element; box = renderedParent(box)) {
    if (box === targetScroller) inside = false;
    const band = landingBand(box);
    if (band) {
      const { left, right } = band;
      const destination = destinationBox(where);
      const byX = nearestScrollBy(
        destination.left - scrollMargin(where, "Left"),
        destination.right + scrollMargin(where, "Right"),
        left,
        right
      );
      const byY = inside ? placementBy(where, "nearest", box, topMargin(where, box, start)) : 0;
      if (byX || byY) land(box, localScrollBy(box, { x: byX, y: byY }), "instant");
    }
    if (box === within2 || box === pageScroller || getComputedStyle(box).position === "fixed")
      break;
  }
  if (targetScroller) scrollIntoReadingBand(alignment, holder, block, behavior);
}
onStanding((node, cause) => {
  if (cause !== "step" || !node) return;
  nextRender(() => {
    if (deepFocus() !== node) return;
    if (!ringShown(node)) scrollIntoView(node, { block: "nearest" });
    for (let box = node; box instanceof Element; box = renderedParent(box)) {
      if (!box.matches("[data-lf-obligation]")) continue;
      if (getComputedStyle(box).outlineStyle === "none") continue;
      if (!ringShown(box)) scrollIntoView(box, { block: "nearest" });
      break;
    }
  });
});

// runtime/reading-place.js
var FOCUSED_PLACE = /* @__PURE__ */ Symbol("live focused place");
var focusedPlace = (reading) => {
  const place2 = reading?.[FOCUSED_PLACE];
  const node = place2?.node.deref();
  return node?.isConnected && node === focused() && under(node, place2.body.deref()) && containingReadingRegionFor(node)?.id === place2.region && place2.intent() ? node : null;
};
var READ_BOX = /* @__PURE__ */ Symbol("box that read the offset");
var DRAWN_PLACE = /* @__PURE__ */ Symbol("live drawn place");
var drawnPlace = (reading) => {
  const place2 = reading?.[DRAWN_PLACE];
  const node = place2?.node.deref();
  if (!node?.isConnected || !drawsLandmark(node)) return null;
  const top = () => {
    const rect = shownBox(node);
    return rect.top + place2.through * rect.height;
  };
  return { node, top };
};
var DRAWING = "img, svg, canvas, video, picture, iframe, object, embed";
var draws = (element) => element.matches(DRAWING) || element.localName.includes("-");
var LANDMARK_CAP = 160;
var QUOTABLE = 24;
var HEADING = "h1, h2, h3, h4, h5, h6";
var textBlocks = (root = pageDocument()) => pageBlocks().filter((block) => under(block, root));
var drawsLandmark = (parent) => {
  if (!parent || skipped(parent) || getComputedStyle(parent).visibility !== "visible")
    return false;
  let box = parent;
  while (box && getComputedStyle(box).display === "contents") box = renderedParent(box);
  return Boolean(box?.checkVisibility({ opacityProperty: true }));
};
var blockWords = /* @__PURE__ */ new WeakMap();
var drawnInside = (block, segments, known) => {
  if (!known.has(block)) {
    const asked = /* @__PURE__ */ new Set();
    let inside = true;
    for (const { node } of segments) {
      for (let at = renderedParent(node); inside && at && at !== block; ) {
        if (asked.has(at)) break;
        asked.add(at);
        const style = getComputedStyle(at);
        inside = (style.position === "static" || style.position === "sticky") && style.transform === "none" && style.translate === "none";
        at = renderedParent(at);
      }
      if (!inside) break;
    }
    known.set(block, inside);
  }
  return known.get(block);
};
function* renderedBlocks(blocks, within2 = null) {
  const reading = pageText();
  if (!blockWords.has(reading)) {
    const words2 = /* @__PURE__ */ new Map();
    for (const segment of reading.segments) {
      if (!words2.has(segment.block)) words2.set(segment.block, []);
      words2.get(segment.block).push(segment);
    }
    blockWords.set(reading, words2);
  }
  const words = blockWords.get(reading);
  const inside = /* @__PURE__ */ new Map();
  const drawn3 = /* @__PURE__ */ new Map();
  const range = document.createRange();
  for (const block of blocks) {
    if (inChrome(block) || skipped(block)) continue;
    if (within2) {
      const own = block.getBoundingClientRect();
      if (own.height && (own.bottom <= within2.top || own.top >= within2.bottom) && drawnInside(block, words.get(block), inside))
        continue;
    }
    const boxes = [], runs = [];
    let run = null;
    for (const segment of words.get(block)) {
      const { node, start, end } = segment;
      const parent = renderedParent(node);
      if (!drawn3.has(parent)) drawn3.set(parent, drawsLandmark(parent));
      if (!drawn3.get(parent)) {
        run = null;
        continue;
      }
      range.setStart(node, start);
      range.setEnd(node, end);
      const rects = [...range.getClientRects()].filter(
        (rect2) => rect2.width && rect2.height
      );
      if (!rects.length) {
        run = null;
        continue;
      }
      if (!run) runs.push(run = { segments: [], boxes: [] });
      run.segments.push(segment);
      run.boxes.push(...rects);
      boxes.push(...rects);
    }
    const rect = union(boxes);
    if (rect)
      yield [block, new DOMRect(rect.left, rect.top, rect.width, rect.height), runs];
  }
}
function passageBlock(node) {
  const blocks = pageBlocks();
  for (let at = node; at; at = upFrom(at)) if (blocks.includes(at)) return at;
  return null;
}
function openingPassage(where) {
  if (where instanceof Range) return passageBlock(where.startContainer);
  if (!where) return null;
  const blocks = pageBlocks().filter((block) => under(block, where));
  return renderedBlocks(blocks).next().value?.[0] ?? null;
}
function readingBounds(region) {
  const shown = region ? shownRegionBounds(region) : shownWindow();
  if (!shown) return null;
  return region && effectiveScroller(region) === pageScroller ? shownWindow({ within: shown }) : shown;
}
function* blocksOnScreen(region = null, blocks = textBlocks(), band = null) {
  const bounds = readingBounds(region);
  if (!bounds) return;
  for (const [block, rect, runs] of renderedBlocks(blocks, band ?? bounds)) {
    if (region ? !under(block, region.body) : effectiveScroller(block) !== pageScroller)
      continue;
    const clips = /* @__PURE__ */ new Map();
    const onScreen2 = runs.filter(
      ({ boxes }) => boxes.some((box) => {
        const seen = clippedContents(box, block, clips);
        return seen && seen.bottom > bounds.top && seen.top < bounds.bottom;
      })
    );
    if (onScreen2.length) yield [block, rect, onScreen2.map(({ segments }) => segments)];
  }
}
var readingBlock = (region = null) => blocksOnScreen(region, textBlocks(region?.body)).next().value?.[0] ?? null;
function pageReading({ bodies }) {
  for (let region = pageReadingRegion(); region; region = readingRegionFor(region.host.parentElement)) {
    const block = readingBlock(region);
    if (block) return block;
    if (bodies && shownRegionBounds(region)) return region.body;
  }
  return readingBlock();
}
var pageReadingBlock = () => pageReading({ bodies: false });
var landingPlace = () => pageReading({ bodies: true });
function readerColumn(bounds, body) {
  if (recentPlaceInput() === "pointer") {
    const { x, y } = pointerAt();
    return x >= bounds.left && x <= bounds.right && y >= bounds.top && y <= bounds.bottom ? x : null;
  }
  const at = focusedInView();
  if (!at || !under(at, body)) return null;
  const rect = shownBox(at);
  return (rect.left + rect.right) / 2;
}
var spans = (block, rect, column) => {
  const own = block.getBoundingClientRect();
  const across = own.width ? own : rect;
  return column >= across.left && column <= across.right;
};
function lineAt(run, edge, range, whole) {
  const boxes = (node, start, end) => {
    range.setStart(node, start);
    range.setEnd(node, end);
    return [...range.getClientRects()].filter((rect) => rect.width && rect.height);
  };
  const reaches = (rect) => Boolean(rect) && (whole ? rect.bottom : (rect.top + rect.bottom) / 2) >= edge;
  for (const [at, segment] of run.entries()) {
    const { node, start, end } = segment;
    if (!reaches(boxes(node, start, end).at(-1))) continue;
    if (whole) return run;
    let low = start;
    let high = end - 1;
    while (low < high) {
      const middle = low + high >> 1;
      if (reaches(boxes(node, middle, end)[0])) high = middle;
      else low = middle + 1;
    }
    const unit = node.data.charCodeAt(low);
    if (unit >= 56320 && unit <= 57343 && low > start) low -= 1;
    return [{ ...segment, start: low }, ...run.slice(at + 1)];
  }
  return null;
}
function lineAnchor(segments) {
  const { text, units } = readingFrom(segments);
  if (!text) return null;
  const from = units[0].start;
  const to = units[Math.min(units.length, LANDMARK_CAP) - 1].end;
  const quoted = [];
  for (const segment of segments) {
    if (!quoted.length && segment.node !== from.node) continue;
    const start = quoted.length ? segment.start : from.offset;
    const end = segment.node === to.node ? to.offset : segment.end;
    if (end > start) quoted.push({ ...segment, start, end });
    if (segment.node === to.node) break;
  }
  const range = rangeOf(quoted);
  const anchor = anchorForPassage(quoted, range.commonAncestorContainer);
  return anchor.quote && !anchor.detached ? { anchor, range } : null;
}
function scrollsAlone(node, box) {
  let alone = null;
  for (let at = renderedParent(node); at?.nodeType === 1 && at !== box; at = renderedParent(at))
    if (at !== document.body && userScrollport(getComputedStyle(at).overflowY) && at.scrollHeight > at.clientHeight)
      alone = at;
  return alone;
}
function drawnAt(body, box, x, edge, blocks) {
  const holdsText = (element) => blocks.some((block) => under(block, element));
  for (const hit of document.elementsFromPoint(x, edge + 1)) {
    if (inChrome(hit) || inUi(hit)) continue;
    if (hit === body || !under(hit, body) || effectiveScroller(hit) !== box)
      return null;
    let found = scrollsAlone(hit, box);
    if (!found) {
      if (passageBlock(hit) || holdsText(hit)) return null;
      let drawing = draws(hit);
      found = hit;
      for (let up = upFrom(found); up && up !== body && !holdsText(up); up = upFrom(up)) {
        found = up;
        drawing ||= draws(up);
      }
      if (!drawing) return null;
    }
    const rect = shownBox(found);
    if (!(rect.height && rect.top <= edge + 1 && rect.bottom > edge)) return null;
    return { box: found, through: Math.max(0, (edge - rect.top) / rect.height) };
  }
  return null;
}
function capturePlace(region = null, blocks = textBlocks()) {
  const box = region ? effectiveScroller(region) : pageScroller;
  const boxTop = landingBand(box).top + aimedTop(box) - box.scrollTop;
  const landmarkTop = (top, block, blockTop = top) => block?.matches(HEADING) ? top + Math.max(0, -blockTop) : top;
  const view = {
    y: box.scrollTop,
    scroller: scrollerIdentity(box),
    width: box.clientWidth,
    revision: runtime.currentRevision,
    [READ_BOX]: new WeakRef(box)
  };
  const standing2 = focusedInView();
  const body = region?.body ?? pageDocument();
  const standingBody = readingRegionFor(standing2)?.body ?? body;
  const focusPlace = () => ({
    node: new WeakRef(standing2),
    body: new WeakRef(body),
    region: containingReadingRegionFor(standing2)?.id,
    intent: retainUserIntent({ source: standing2 })
  });
  const standsOn2 = recentPlaceInput() === "focus" && standing2 && under(standing2, body) && // Focus on the reading surface itself names its contents, not a landmark.
  !under(standingBody, standing2);
  if (region && followingItsEnd(box))
    return { ...view, ...standsOn2 && { [FOCUSED_PLACE]: focusPlace() }, end: true };
  const bounds = readingBounds(region);
  const column = bounds && readerColumn(bounds, body);
  let named = null;
  const range = document.createRange();
  const lineOf = (block, rect, runs) => {
    for (const run of runs) {
      if (quoteFrom(run).length < QUOTABLE) continue;
      const segments = lineAt(run, boxTop, range, block.matches(HEADING));
      if (!segments) continue;
      const landmark = lineAnchor(segments);
      if (!landmark) return null;
      const box2 = [...landmark.range.getClientRects()].find((r) => r.width && r.height);
      return { block, rect, landmark, bottom: box2?.bottom ?? -Infinity };
    }
    return null;
  };
  let sectioned = null;
  let line = null;
  for (const [block, rect, runs] of blocksOnScreen(region, blocks)) {
    if (stuckBox(block, box) || scrollsAlone(block, box)) continue;
    const section = closestAcross(block, ADDRESSABLE);
    sectioned ??= section && { block, rect, section };
    line = lineOf(block, rect, runs);
    if (line) break;
  }
  if (line && column !== null && !spans(line.block, line.rect, column)) {
    const row = { top: boxTop, bottom: line.bottom };
    for (const [block, rect, runs] of blocksOnScreen(region, blocks, row)) {
      if (block === line.block || stuckBox(block, box) || scrollsAlone(block, box) || !spans(block, rect, column))
        continue;
      const beside = lineOf(block, rect, runs);
      if (beside && beside.landmark.range.getBoundingClientRect().top < line.bottom) {
        line = beside;
        break;
      }
    }
  }
  if (sectioned) {
    const { block, rect, section } = sectioned;
    named = block;
    view.section = section.id;
    view.sectionTop = landmarkTop(
      shownBox(section).top - boxTop,
      block,
      rect.top - boxTop
    );
  }
  if (line) {
    const { block, rect, landmark } = line;
    named = block;
    const { section: id, quote, prefix, suffix } = landmark.anchor;
    Object.assign(view, { section: id, quote, prefix, suffix });
    const section = sectionOf(view);
    view.sectionTop = section && landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop);
    view.quoteTop = landmarkTop(
      landmark.range.getBoundingClientRect().top - boxTop,
      block
    );
  }
  if (bounds) {
    const across = shownBox(body);
    const left = Math.max(across.left, bounds.left);
    const right = Math.min(across.right, bounds.right);
    const x = column !== null && column >= left && column <= right ? column : (left + right) / 2;
    const drawn3 = drawnAt(body, box, x, boxTop, blocks);
    if (drawn3) {
      named = drawn3.box;
      view[DRAWN_PLACE] = { node: new WeakRef(drawn3.box), through: drawn3.through };
    }
  }
  if (standsOn2 && !(named && under(named, standing2)))
    view[FOCUSED_PLACE] = focusPlace();
  return view;
}
var drawnQuote = (view) => {
  const segments = targetSegments(view.quote && resolveAnchor(view));
  return segments.every(({ node }) => drawsLandmark(renderedParent(node))) ? segments : [];
};
function landmarkOf(view) {
  const live = focusedPlace(view);
  if (live) return { node: live, top: () => shownBox(live).top };
  const drawn3 = drawnPlace(view);
  if (drawn3) return drawn3;
  const segments = drawnQuote(view);
  if (segments.length)
    return {
      node: segments[0].node,
      top: () => rangeOf(segments).getBoundingClientRect().top
    };
  const section = view.section && targetElement(resolveAnchor({ section: view.section }));
  return section && drawsLandmark(section) ? { node: section, top: () => shownBox(section).top } : null;
}
var placeNode = (view) => landmarkOf(view)?.node ?? null;
function placeOffset(view, region = null) {
  const landmark = landmarkOf(view);
  const box = region ? effectiveScroller(region) : pageScroller;
  return landmark ? landmark.top() - landingBand(box).top : null;
}
var hasLandmark = (reading) => Boolean(
  focusedPlace(reading) || drawnPlace(reading) || reading?.end || reading?.quote || reading?.section
);
var sameScroller = (reading, scroller) => reading.scroller !== void 0 && reading.scroller === scrollerIdentity(scroller);
var rawOffsetFits = (reading, scroller) => sameScroller(reading, scroller) && reading.width === scroller.clientWidth && (reading.revision === runtime.currentRevision || inUi(scroller) && reading[READ_BOX]?.deref() !== scroller);
function scrollerIdentity(scroller) {
  if (scroller === pageScroller) return "$page";
  return readingRegions().find(({ body }) => body === scroller)?.id;
}
function restorePlace(view, region = null, currentIntent = retainUserIntent()) {
  if (!view || !currentIntent()) return;
  const box = region ? effectiveScroller(region) : pageScroller;
  const body = region?.body ?? pageDocument();
  const destination = focusedPlace(view);
  const standing2 = destination && under(destination, body) ? destination : null;
  if (!standing2 || !sameScroller(view, box)) {
    if (view.end) {
      scrollToEnd(box);
    } else {
      const boxTop = landingBand(box).top;
      const drawn3 = drawnPlace(view);
      const segments = drawn3 && under(drawn3.node, body) ? [] : drawnQuote(view);
      if (drawn3 && under(drawn3.node, body)) {
        moveScrollerBy(box, drawn3.top() - boxTop);
      } else if (segments.length) {
        moveScrollerBy(
          box,
          rangeOf(segments).getBoundingClientRect().top - boxTop - view.quoteTop
        );
      } else if (!standing2) {
        const found = targetElement(resolveAnchor({ section: view.section }));
        const section = found && drawsLandmark(found) ? found : null;
        if (section) {
          if (under(box, section))
            box.scrollTo({
              top: rawOffsetFits(view, box) ? view.y : 0,
              behavior: "instant"
            });
          else moveScrollerBy(box, shownBox(section).top - boxTop - view.sectionTop);
        } else if (rawOffsetFits(view, box))
          box.scrollTo({ top: view.y, behavior: "instant" });
      }
    }
  }
  if (standing2) scrollIntoReadingBand(standing2, standing2, "nearest", "instant");
  placeKept(box, ...standing2 ? scrollersOf(standing2) : []);
}

// runtime/obligations/model.js
var readObligations = readPart((root) => root.effective.obligations);
var obligationEntry = (obligation) => registry[obligation?.source.tag]?.["x-awaits"];
var answeredInWords = (obligation) => Boolean(obligationEntry(obligation)?.reply);
var approvalBlockingObligations = readPart((root) => {
  const { obligations, view } = root.effective;
  if (obligations.phase !== "ready" || !view) return null;
  const held = new Set(view.approval_blocking);
  return obligations.all.filter((obligation) => held.has(obligation.id));
});

// runtime/obligations/place.js
function obligationPlace(item, items = readObligations().all) {
  if (!item || item.source.kind !== "widget")
    return { source: null, context: null, node: null };
  const source = elementById(item.source.id);
  const context = elementById(item.prompt.target);
  const shared = items.some(
    (other) => other.id !== item.id && other.source.kind === "widget" && other.prompt.target === item.prompt.target
  );
  return { source, context, node: shared ? source : context };
}
function obligationsIn(region, items = readObligations().all) {
  return items.filter((item) => {
    if (item.source.kind !== "widget" || item.status === "withdrawn") return false;
    const source = elementById(item.source.id);
    return Boolean(source && under(source, region));
  });
}

// runtime/standing-target.js
var sides = /* @__PURE__ */ new Map();
function declareSide(bridge, { beside = false } = {}) {
  sides.set(bridge, beside);
  return () => sides.delete(bridge);
}
function obligationHolding(items, node) {
  if (!node) return null;
  const holds = (element) => element && under(node, element);
  let held = null;
  for (const item of items) {
    if (item.source.kind !== "widget") continue;
    const { source, node: stands } = obligationPlace(item, items);
    const at = holds(source) ? source : holds(stands) ? stands : null;
    if (at && (!held || under(at, held.at))) held = { item, at };
  }
  return held?.item ?? null;
}
var placeOf = (node) => placeFrom(node, /* @__PURE__ */ new Set(), true);
var arrivalOf = (node) => placeFrom(node, /* @__PURE__ */ new Set(), false);
function placeFrom(node, visited, countBeside) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at || at === document.body || visited.has(at)) return null;
  visited.add(at);
  if (obligationHolding(readObligations().all, at)) return at;
  for (const [side, beside] of sides) {
    const place2 = side(at);
    if (place2 && beside && !countBeside) return null;
    if (place2)
      return inChrome(place2) && !obligationHolding(readObligations().all, place2) ? placeFrom(place2, visited, countBeside) : place2;
  }
  return inChrome(at) ? null : at;
}
function standingOrigin() {
  for (const node of standingNodes()) {
    const place2 = placeOf(node);
    if (place2) {
      const tab = place2.closest('[role="tab"][aria-selected="true"]');
      const panel = tab?.ariaControlsElements?.[0];
      return panel ? { place: panel, kind: "enter" } : { place: place2, kind: "standing" };
    }
  }
  return null;
}
var walkOrigin = () => standingOrigin() ?? { place: pageReadingBlock(), kind: "standing" };
function stepFrom(list, { place: here, kind }, dir, placeOfItem) {
  if (!here) return cycledRow(list, null, dir);
  if (kind === "enter") {
    const inside = list.filter((item) => {
      const place2 = placeOfItem(item);
      return place2 && renderedUnder(place2, here);
    });
    if (inside.length) return cycledRow(inside, null, dir);
  }
  const reach = list.filter((item) => {
    const place2 = placeOfItem(item);
    if (!place2) return dir > 0;
    return renderedUnder(here, place2) || Math.sign(renderedOrder(here, place2)) === -dir;
  });
  const row = dir > 0 ? reach[0] : reach.at(-1);
  return row ? { row, wrapped: false } : { row: dir > 0 ? list[0] : list.at(-1), wrapped: true };
}
function heldObligation(node = focused()) {
  const item = obligationHolding(readObligations().all, placeOf(node));
  return obligationPlace(item).node;
}

// runtime/syntax-languages.js
var syntaxLanguages = {
  "bash": () => import("/vendor/syntax/bash.js"),
  "css": () => import("/vendor/syntax/css.js"),
  "diff": () => import("/vendor/syntax/diff.js"),
  "go": () => import("/vendor/syntax/go.js"),
  "html": () => import("/vendor/syntax/html.js"),
  "java": () => import("/vendor/syntax/java.js"),
  "javascript": () => import("/vendor/syntax/javascript.js"),
  "json": () => import("/vendor/syntax/json.js"),
  "markdown": () => import("/vendor/syntax/markdown.js"),
  "python": () => import("/vendor/syntax/python.js"),
  "rust": () => import("/vendor/syntax/rust.js"),
  "sql": () => import("/vendor/syntax/sql.js"),
  "toml": () => import("/vendor/syntax/toml.js"),
  "typescript": () => import("/vendor/syntax/typescript.js"),
  "yaml": () => import("/vendor/syntax/yaml.js")
};
var syntaxLanguageNames = { "shellscript": "bash", "bash": "bash", "sh": "bash", "shell": "bash", "zsh": "bash", "css": "css", "diff": "diff", "go": "go", "html": "html", "java": "java", "javascript": "javascript", "js": "javascript", "cjs": "javascript", "mjs": "javascript", "json": "json", "markdown": "markdown", "md": "markdown", "python": "python", "py": "python", "rust": "rust", "rs": "rust", "sql": "sql", "toml": "toml", "typescript": "typescript", "ts": "typescript", "cts": "typescript", "mts": "typescript", "yaml": "yaml", "yml": "yaml" };

// runtime/syntax.js
var registry2 = runtime.registry;
var tokenizerReady;
var tokenizer = () => tokenizerReady ??= import("/vendor/syntax.esm.js");
var languagesReady = /* @__PURE__ */ new Map();
function ensureSyntaxLanguage(lang) {
  if (!lang) return tokenizer();
  if (!languagesReady.has(lang)) {
    const load = syntaxLanguages[lang];
    if (!load)
      throw new Error(`no ${lang} grammar \u2014 rebuild syntax from registry.json`);
    languagesReady.set(
      lang,
      Promise.all([tokenizer(), load()]).then(async ([shared, grammar]) => {
        await shared.registerLanguage(lang, grammar.default);
        return shared;
      })
    );
  }
  return languagesReady.get(lang);
}
async function syntax(source, lang) {
  const shared = await ensureSyntaxLanguage(lang);
  const tokens3 = await shared.tokenize(source, lang);
  if (tokens3.map((t) => t.text).join("") !== source)
    throw new Error(`the ${lang} tokenizer did not return the source unchanged`);
  return tokens3;
}
var synNodes = (tokens3) => tokens3.map(({ text, style }) => {
  if (!Object.keys(style).length) return document.createTextNode(text);
  const span = document.createElement("span");
  span.dataset.lfSyn = "";
  for (const [property, value] of Object.entries(style))
    span.style.setProperty(property, value);
  span.textContent = text;
  return span;
});
function tokenLines(tokens3) {
  const lines = [[]];
  for (const { text, style } of tokens3) {
    const parts = text.split("\n");
    parts.forEach((part, i) => {
      if (i) lines.push([]);
      if (part) lines.at(-1).push({ text: part, style });
    });
  }
  return lines;
}
var langForPath = (path) => registry2.$languages.paths[path.split("/").pop().split(".").slice(1).pop()?.toLowerCase()];
var LANGUAGE_CLASS = /(?:^|\s)language-([\w+.#-]+)(?=\s|$)/;
var BLOCK = "pre > code[class]";
var languageOf = (code) => {
  const lang = code.className.match(LANGUAGE_CLASS)?.[1];
  return Object.hasOwn(syntaxLanguageNames, lang) ? syntaxLanguageNames[lang] : void 0;
};
var tokenizing = /* @__PURE__ */ new WeakSet();
async function highlightBlocks(root) {
  const blocks = [];
  const found = [...root.querySelectorAll(BLOCK)];
  if (root.matches?.(BLOCK)) found.unshift(root);
  for (const code of found) {
    const lang = languageOf(code);
    if (lang && code.dataset.lfSyntax !== lang && !tokenizing.has(code)) {
      tokenizing.add(code);
      blocks.push(code);
    }
  }
  if (!blocks.length) return;
  for (const code of blocks) {
    let lang = languageOf(code);
    try {
      let tokens3;
      while (lang) {
        const source = code.textContent;
        tokens3 = await syntax(source, lang);
        if (code.textContent === source && languageOf(code) === lang) break;
        lang = languageOf(code);
      }
      if (!lang) continue;
      if (tokens3.some(({ style }) => Object.keys(style).length))
        code.replaceChildren(...synNodes(tokens3));
      code.dataset.lfSyntax = lang;
    } catch (err) {
      reportPageError(err, `<pre><code class="language-${lang}"> failed to highlight`);
    } finally {
      tokenizing.delete(code);
    }
  }
}

// runtime/declared-words.js
var PAGE_PAINT_ATTRIBUTES = new Set(Object.values(PAGE_PAINT_ATTRIBUTE));
var isPagePaint = (name) => PAGE_PAINT_ATTRIBUTES.has(name) || Object.values(marks).some((mark) => mark.paint === name);
function quietWord(el2, word) {
  const title = el2.querySelector(":scope > strong");
  const seat = title ? title.nextSibling : el2.firstChild;
  const existing = el2.querySelector(":scope > .lf-quiet");
  if (existing) {
    if (existing === seat && existing.textContent === word) return;
    existing.remove();
  }
  if (!word) return;
  const span = Object.assign(document.createElement("span"), {
    className: "lf-ui lf-quiet",
    textContent: word
  });
  span.dataset.lfGen = "1";
  move(el2, span, title ? title.nextSibling : el2.firstChild);
}
var EXTERNAL_LINK_ATTRIBUTES = ["target", "rel", "aria-describedby"];
var externalLinkState = /* @__PURE__ */ new WeakMap();
var externalMarkSequence = 0;
function isExternalPageLink(link) {
  if (!(link instanceof HTMLAnchorElement)) return false;
  try {
    const href = link.getAttribute("href");
    const url = href === null ? null : new URL(href, document.baseURI);
    return ["http:", "https:"].includes(url?.protocol) && url.origin !== location.origin;
  } catch {
    return false;
  }
}
var linkAttributes = (link) => Object.fromEntries(
  EXTERNAL_LINK_ATTRIBUTES.map((name) => [name, link.getAttribute(name)])
);
var tokens = (value) => value?.split(/\s+/).filter(Boolean) ?? [];
function withToken(value, token, insensitive = false) {
  const values = tokens(value);
  const wanted = insensitive ? token.toLowerCase() : token;
  if (!values.some((value2) => (insensitive ? value2.toLowerCase() : value2) === wanted))
    values.push(token);
  return values.join(" ");
}
function withoutToken(value, token, insensitive = false) {
  if (value === null) return null;
  const unwanted = insensitive ? token.toLowerCase() : token;
  return tokens(value).filter((value2) => (insensitive ? value2.toLowerCase() : value2) !== unwanted).join(" ");
}
function writeLinkAttributes(link, values) {
  for (const [name, value] of Object.entries(values)) keeps(link, name, value);
}
function rememberExternalLinkChanges(link, state) {
  if (!state.painted) return;
  const current = linkAttributes(link);
  for (const name of EXTERNAL_LINK_ATTRIBUTES) {
    if (current[name] === state.painted[name]) continue;
    let value = current[name];
    if (name === "rel" && state.addedNoopener)
      value = withoutToken(value, "noopener", true);
    if (name === "aria-describedby") value = withoutToken(value, state.markId);
    state.baseline[name] = value;
  }
}
function clearExternalLink(link, state) {
  rememberExternalLinkChanges(link, state);
  writeLinkAttributes(link, state.baseline);
  link.querySelectorAll(':scope > .lf-external-mark[data-lf-gen="1"]').forEach((node) => node.remove());
  externalLinkState.delete(link);
}
function leaveExternalLink(link) {
  const state = externalLinkState.get(link);
  if (state) clearExternalLink(link, state);
}
function renderExternalLink(link) {
  if (!(link instanceof HTMLAnchorElement)) return;
  if (!isExternalPageLink(link)) {
    leaveExternalLink(link);
    return;
  }
  let state = externalLinkState.get(link);
  if (!state) {
    state = {
      baseline: linkAttributes(link),
      painted: null,
      markId: `lf-external-mark-${++externalMarkSequence}`,
      addedNoopener: false
    };
    externalLinkState.set(link, state);
  } else rememberExternalLinkChanges(link, state);
  let mark = link.querySelector(':scope > .lf-external-mark[data-lf-gen="1"]');
  if (!mark) {
    mark = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mark.setAttribute("class", "lf-ui lf-external-mark");
    mark.setAttribute("viewBox", "0 0 16 16");
    mark.dataset.lfGen = "1";
    mark.setAttribute("aria-hidden", "true");
    mark.setAttribute("aria-label", "opens in a new tab");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute(
      "d",
      "M6.5 3H4a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V9.5M9 3h4v4M13 3 7.5 8.5"
    );
    mark.append(line);
    link.append(mark);
  }
  keeps(mark, "id", state.markId);
  state.addedNoopener = !tokens(state.baseline.rel).some(
    (value) => value.toLowerCase() === "noopener"
  );
  writeLinkAttributes(link, {
    target: "_blank",
    rel: withToken(state.baseline.rel, "noopener", true),
    "aria-describedby": withToken(state.baseline["aria-describedby"], state.markId)
  });
  state.painted = linkAttributes(link);
}
function watchExternalLinks() {
  watchArrivals("a", ["href", ...EXTERNAL_LINK_ATTRIBUTES], {
    arrive: renderExternalLink,
    leave: leaveExternalLink
  });
}
function paintDeclaredWords(root) {
  renderSaid(root);
  renderQuiet(root);
  return highlightBlocks(root);
}
function* elementsIn(root, selector) {
  if (root.matches?.(selector)) yield root;
  yield* root.querySelectorAll(selector);
}
function markDeclared(root) {
  for (const [key, mark] of Object.entries(marks)) {
    const { paint: paint2, authored, message } = mark;
    if (!message) continue;
    const tags = tagsDeclaring((entry) => entry[key]);
    for (const tag of tags) {
      const declared = registry[tag][key];
      for (const el2 of elementsIn(root, tag))
        keeps(el2, paint2, declared === true || mark.presence ? "" : declared);
    }
    if (authored) {
      for (const el2 of elementsIn(root, `[${authored}]`))
        if (mark.authored_on !== "declared" || tags.includes(el2.localName))
          keeps(el2, paint2, el2.getAttribute(authored));
    }
  }
}
function writePrepaint(root) {
  for (const tag of tagsDeclaring((entry) => entry["x-prepaint"])) {
    const declared = registry[tag]["x-prepaint"];
    const markup = document.createElement("template");
    markup.innerHTML = declared.as ? registry[declared.as]["x-prepaint"] : declared;
    const written = (
      /** @type {HTMLElement} */
      markup.content.firstElementChild
    );
    written.toggleAttribute("data-lf-prepaint", true);
    written.dataset.lfGen = "1";
    for (const el2 of elementsIn(root, tag)) el2.prepend(written.cloneNode(true));
  }
}
function renderSaid(root) {
  for (const [tag, entry] of elementDeclarations()) {
    if (!entry["x-says"]) continue;
    for (const el2 of elementsIn(root, tag))
      for (const [attr, edge] of Object.entries(entry["x-says"])) {
        const text = el2.getAttribute(attr);
        const existing = el2.querySelector(`:scope > [data-lf-said="${attr}"]`);
        if (existing) {
          if (text === null) existing.remove();
          else if (existing.textContent !== text) existing.textContent = text;
          continue;
        }
        if (text === null) continue;
        const span = document.createElement("span");
        span.dataset.lfSaid = attr;
        span.dataset.lfGen = "1";
        span.textContent = text;
        const pastTrailingChrome = [...el2.childNodes].filter(
          (n) => !(n.nodeType === 1 && n.dataset.lfGen)
        );
        const beforeLeadingChrome = [...el2.childNodes].find(
          (n) => !(n.nodeType === 1 && n.dataset.lfSaid)
        );
        move(
          el2,
          span,
          (edge === "before" ? beforeLeadingChrome : pastTrailingChrome.at(-1)?.nextSibling) ?? null
        );
      }
  }
}
function quietFacts(el2) {
  const words = el2.hasAttribute(PAGE_PAINT_ATTRIBUTE.restated) ? ["rewritten since the decision"] : [];
  if (el2.hasAttribute(PAGE_PAINT_ATTRIBUTE.userOverride)) words.push("my change");
  if (el2.hasAttribute(PAGE_PAINT_ATTRIBUTE.reported)) words.push("reported state");
  return words.join(", ");
}
function renderQuiet(root, also = []) {
  const painting = [
    `[${PAGE_PAINT_ATTRIBUTE.restated}]`,
    `[${PAGE_PAINT_ATTRIBUTE.userOverride}]`,
    `[${PAGE_PAINT_ATTRIBUTE.reported}]`
  ].join(", ");
  const targets = new Set(elementsIn(root, painting));
  for (const el2 of also) if (el2 === root || root.contains(el2)) targets.add(el2);
  for (const el2 of targets) quietWord(el2, quietFacts(el2));
}

// runtime/copy-control.js
function copyControl(className, { label = "", success, error }) {
  const copy = offer("wa-copy-button", className);
  if (label) copy.copyLabel = label;
  copy.successLabel = success;
  copy.errorLabel = error;
  copy.tooltip = "none";
  copy.addEventListener("wa-copy", () => notice(success, { announce: false }));
  copy.addEventListener("wa-error", () => raiseError(error, { announce: false }));
  return copy;
}

// runtime/block-controls.js
var home = document.createElement("div");
home.className = "lf-block-controls";
var cuts = /* @__PURE__ */ new WeakMap();
var makeCut = () => {
  const frame = document.createElement("div");
  frame.className = "lf-block-control-cut";
  return frame;
};
var placed = /* @__PURE__ */ new Map();
var resized = 0;
addEventListener("resize", () => {
  resized ||= nextRender(() => {
    resized = 0;
    const read = [...placed].filter(([, block]) => !skipped(block)).map(([control, block]) => [control, block, headerLevels(block)]);
    for (const [control, block, levels] of read) standInChrome(control, block, levels);
  });
});
function standInChrome(control, block, levels) {
  const frames = cutFrames(levels, cuts.get(control) ?? [], makeCut);
  cuts.set(control, frames);
  placed.set(control, block);
  if (home.parentNode !== chromeRoot) move(chromeRoot, home, null);
  if (frames[0] && frames[0].parentNode !== home) move(home, frames[0], null);
  const frame = frames.at(-1) ?? home;
  if (control.parentNode !== frame) move(frame, control, null);
}
function anchorControl(control, block) {
  const place2 = () => control.classList.toggle(
    "lf-block-control-away",
    !anchorView(control, block, place2)
  );
  return {
    control,
    near: anchorView(control, block, place2),
    anchor: anchorReading(block)
  };
}
function aimControl({ control, near, anchor }) {
  control.classList.toggle("lf-block-control-away", !near);
  const name = nameAnchor(anchor);
  if (control.style.positionAnchor !== name) control.style.positionAnchor = name;
  return control;
}
function readInsets(block) {
  const box = block.getBoundingClientRect();
  const at = anchorBox(block);
  return { dx: box.left - at.left, dy: box.top - at.top };
}
function writeInsets(control, { dx, dy }) {
  for (
    const [property, length] of
    /** @type {[string, number][]} */
    [
      ["--lf-block-control-dx", dx],
      ["--lf-block-control-dy", dy]
    ]
  ) {
    const value = length ? layoutPx(length) : "";
    if (control.style.getPropertyValue(property) !== value)
      control.style.setProperty(property, value);
  }
}
function revealControl(control, block) {
  if (cuts.has(control)) standInChrome(control, block, headerLevels(block));
  writeInsets(control, readInsets(block));
  refreshAnchorView(control);
}
function tabFromBlock(control, block, signal) {
  control.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Tab") focusDestination(block, "step");
    },
    { signal }
  );
}
function releaseControl(control) {
  control.remove();
  cuts.get(control)?.[0]?.remove();
  cuts.delete(control);
  placed.delete(control);
}

// runtime/code-copy.js
var controls = /* @__PURE__ */ new WeakMap();
var wired = /* @__PURE__ */ new WeakMap();
var COPY_SCOPE = /* @__PURE__ */ Symbol("code copy");
var pressedPath = /* @__PURE__ */ new WeakSet();
addEventListener(
  "pointerdown",
  (event) => pressedPath = new WeakSet(event.composedPath()),
  {
    capture: true
  }
);
onStanding((node) => {
  for (let at = node; at; at = upFrom(at)) {
    const copy = controls.get(at);
    if (copy) return revealControl(copy, at);
  }
});
function prepareCodeBlock(pre, source, noun) {
  let copy = controls.get(pre);
  if (!copy) {
    copy = copyControl("lf-code-copy", {
      label: `Copy ${noun}`,
      success: `${noun[0].toUpperCase()}${noun.slice(1)} copied`,
      error: `Unable to copy ${noun}`
    });
    copy.addEventListener(
      "click",
      (event) => {
        if (event.detail && !pressedPath.has(copy)) {
          event.preventDefault();
          event.stopImmediatePropagation();
        } else copy.value = source();
      },
      { capture: true }
    );
    pre.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "touch" && copy.isConnected)
        focusDestination(pre, "move");
    });
    pre.addEventListener("pointerenter", () => revealControl(copy, pre));
    controls.set(pre, copy);
  }
  return anchorControl(copy, pre);
}
function declareCopy(pre, copy, noun) {
  projectCommandScope(
    pre,
    COPY_SCOPE,
    commandScope("On a code block", [
      {
        id: "code.copy",
        keys: ["Enter"],
        description: `Copy this block's ${noun} to the clipboard`,
        title: `copy ${noun}`,
        run: () => copy.shadowRoot.querySelector("button").click()
      }
    ])
  );
}
function copyBlock(block, source, noun) {
  const copy = aimControl(prepareCodeBlock(block, source, noun));
  declareCopy(block, copy, noun);
  return copy;
}
function watchCodeBlocks() {
  watchArrivals("pre:has(> code)", ["style"], {
    arriveBatch(blocks) {
      const prepared = blocks.filter((pre) => pre.getRootNode() === document).map(
        (pre) => (
          /** @type {[HTMLElement, ReturnType<typeof prepareCodeBlock>, any[]]} */
          [
            pre,
            prepareCodeBlock(
              pre,
              () => pre.querySelector(":scope > code").textContent,
              "code"
            ),
            headerLevels(pre)
          ]
        )
      );
      for (const [pre, pending, levels] of prepared) {
        const copy = aimControl(pending);
        standInChrome(copy, pre, levels);
        copy.tabIndex = -1;
        claimReachStop(pre);
        if (!wired.has(pre)) {
          const events = new AbortController();
          wired.set(pre, events);
          declareCopy(pre, copy, "code");
          const options = { signal: events.signal };
          tabFromBlock(copy, pre, events.signal);
          pre.addEventListener(
            "pointerenter",
            () => copy.classList.add("lf-code-copy-hover"),
            options
          );
          pre.addEventListener(
            "pointerleave",
            () => copy.classList.remove("lf-code-copy-hover"),
            options
          );
          pre.addEventListener(
            "focus",
            () => copy.classList.add("lf-code-copy-focused"),
            options
          );
          pre.addEventListener(
            "blur",
            () => copy.classList.remove("lf-code-copy-focused"),
            options
          );
        }
      }
    },
    leave(pre) {
      wired.get(pre)?.abort();
      wired.delete(pre);
      const copy = controls.get(pre);
      if (copy?.matches(".lf-code-copy-hover, .lf-code-copy-focused"))
        copy.classList.remove("lf-code-copy-hover", "lf-code-copy-focused");
      if (copy) releaseControl(copy);
      releaseReachStop(pre);
      projectCommandScope(pre, COPY_SCOPE, null);
    }
  });
}

// runtime/markdown.js
var escapeHtml = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
var escapedSource = (text) => escapeHtml(text);
var render2 = escapedSource;
var renderInline = escapedSource;
var tokenize = null;
var ready;
var renderMarkdown = (text) => render2(text);
function renderedWords(html2, imageAlt = false) {
  const parsed = document.createElement("template");
  parsed.innerHTML = html2;
  return fragmentWords(parsed.content, imageAlt);
}
function fragmentWords(fragment, imageAlt = false) {
  for (const br of fragment.querySelectorAll("br"))
    br.replaceWith(document.createTextNode("\n"));
  if (imageAlt)
    for (const image of fragment.querySelectorAll("img"))
      image.replaceWith(document.createTextNode(image.alt));
  return fragment.textContent;
}
var markdownWords = (text) => renderedWords(render2(text));
var renderInlineMarkdown = (text, breaks = true) => renderInline(text, breaks);
function inlineMarkdownFragment(text, breaks = true) {
  const parsed = document.createElement("template");
  parsed.innerHTML = renderInlineMarkdown(text, breaks);
  return parsed.content;
}
async function loadDeclaredMarkdown(scope) {
  if (!declarationFor(scope, "x-text-format") && !elementsDeclaring(scope, "x-text-format").length)
    return;
  let failure;
  if (!await loadMarkdown((error) => failure = error))
    throw new Error(
      `leaf: Markdown renderer failed to load: ${failure?.message ?? failure}`
    );
}
async function prepareDeclaredMarkdown(scope) {
  await loadDeclaredMarkdown(scope);
  formatDeclaredMarkdown(scope);
}
function formatDeclaredMarkdown(scope) {
  const elements = elementsDeclaring(scope, "x-text-format");
  if (declarationFor(scope, "x-text-format")) elements.unshift(scope);
  if (!elements.length) return;
  if (!tokenize)
    throw new Error("leaf: Markdown formatting requires its loaded renderer");
  for (const element of elements) {
    if (declarationFor(element, "x-text-format") === "markdown") {
      const pre = element.querySelector(":scope > pre");
      if (!pre) continue;
      const body = element.querySelector(":scope > .lf-markdown-body") ?? document.createElement("div");
      if (body.className !== "lf-markdown-body") body.className = "lf-markdown-body";
      paintMarkdown(body, dataBody(element));
      body.removeAttribute("data-lf-prepaint");
      body.removeAttribute("data-lf-gen");
      pre.replaceWith(body);
      continue;
    }
    for (const node of [...element.childNodes]) {
      if (node.nodeType !== Node.TEXT_NODE || !node.data.trim()) continue;
      const parsed = inlineMarkdownFragment(node.data, false);
      if (!parsed.firstElementChild && parsed.textContent === node.data) continue;
      const words = document.createElement("span");
      words.className = "lf-markdown-words";
      words.dataset.lfMarkdownWords = "";
      words.dataset.lfSourceWords = node.data;
      words.append(parsed);
      node.replaceWith(words);
    }
  }
}
function paintMarkdown(element, source) {
  if (element.dataset.lfSourceWords === source && !element.hasAttribute("data-lf-prepaint"))
    return;
  const markup = renderMarkdown(source);
  if (element.dataset.lfSourceWords !== source) element.dataset.lfSourceWords = source;
  if (element.innerHTML !== markup) element.innerHTML = markup;
}
var characters = new Intl.Segmenter(void 0, { granularity: "grapheme" });
function inlineSourcePositions(source, raw, at, limit) {
  const positions = [at];
  let sourceAt = at;
  let inlineAt = 0;
  for (const run of alignText(source.slice(at, limit), raw, characters, Infinity)) {
    if (run.kind === "delete") sourceAt += run.text.length;
    else {
      for (let i = 0; i < run.text.length; i++) {
        positions[inlineAt++] = sourceAt;
        if (run.kind === "same") sourceAt++;
      }
      positions[inlineAt] = sourceAt;
    }
  }
  return positions;
}
function placedMarkdownTokens(source) {
  const tokens3 = markdownTokens(source);
  if (!tokens3) return [];
  const starts = [0];
  for (let at = 0; at < source.length; at++) {
    if (source[at] === "\r" && source[at + 1] === "\n") at++;
    if (source[at] === "\r" || source[at] === "\n") starts.push(at + 1);
  }
  starts.push(source.length);
  const found = [];
  let inlineAt = 0;
  for (const [index, token] of tokens3.entries()) {
    const from = token.map ? starts[token.map[0]] : 0;
    const to = token.map ? starts[token.map[1]] : source.length;
    if (token.type !== "inline") {
      if (token.map && (token.nesting === 1 || token.type === "fence" || token.type === "code_block"))
        found.push({
          token,
          from,
          to,
          markers: token.meta?.markers?.map(([line, a, b]) => [
            starts[line] + a,
            starts[line] + b
          ]),
          // A heading's inline token owns its content lines, excluding Setext syntax.
          contentLines: token.type === "heading_open" ? tokens3[index + 1].map.map((at) => starts[at]) : void 0,
          words: token.nesting ? null : token.content
        });
      continue;
    }
    const positions = inlineSourcePositions(
      source,
      token.meta.sourceContent,
      Math.max(from, inlineAt),
      to
    );
    const stack = [];
    for (const child of token.children) {
      if (!child.meta?.source) continue;
      let [a, b] = child.meta.source;
      if (child.nesting === 1) {
        if (child.markup && child.markup !== "linkify" && child.markup !== "autolink")
          a = b - child.markup.length;
        const placed2 = {
          token: child,
          from: positions[a],
          to: positions[b],
          contentFrom: positions[b]
        };
        found.push(placed2);
        stack.push(placed2);
      } else if (child.nesting === -1) {
        const placed2 = stack.pop();
        if (!placed2) continue;
        if (child.markup && child.markup !== "linkify" && child.markup !== "autolink")
          b = a + child.markup.length;
        placed2.to = positions[b];
        placed2.contentTo = positions[a];
      } else if (child.type !== "html_inline") {
        found.push({
          token: child,
          from: positions[a],
          to: positions[b],
          words: child.type === "softbreak" || child.type === "hardbreak" ? "\n" : child.type === "image" ? safeUrl(child.attrGet("src")) ? "" : renderedWords(
            renderInlineMarkdown(source.slice(positions[a], positions[b]))
          ) : child.content,
          escapes: (child.meta.escapes ?? []).map((at) => positions[at])
        });
      }
    }
    inlineAt = positions.at(-1);
  }
  return found;
}
function markdownSourceOffset(body, node, offset) {
  if (!body.contains(node)) return null;
  const range = document.createRange();
  range.selectNodeContents(body);
  range.setEnd(node, offset);
  const aim = fragmentWords(range.cloneContents()).length;
  const source = body.dataset.lfSourceWords;
  const shown = fragmentWords(body.cloneNode(true));
  let shownAt = 0;
  let sourceEnd = 0;
  for (const placed2 of placedMarkdownTokens(source)) {
    const { token, from, to } = placed2;
    if (token.nesting) continue;
    const words = placed2.words;
    if (!words) continue;
    const start = shown.indexOf(words, shownAt);
    if (start < 0) continue;
    if (aim < start) return from;
    if (aim <= start + words.length) {
      let sourceAt = from;
      let tokenAt = start;
      for (const run of alignText(
        source.slice(from, to),
        words,
        characters,
        Infinity
      )) {
        if (run.kind === "delete") sourceAt += run.text.length;
        else {
          if (aim <= tokenAt + run.text.length)
            return sourceAt + (run.kind === "same" ? aim - tokenAt : 0);
          tokenAt += run.text.length;
          if (run.kind === "same") sourceAt += run.text.length;
        }
      }
      return to;
    }
    shownAt = start + words.length;
    sourceEnd = to;
  }
  return sourceEnd;
}
var markdownReady = () => render2 !== escapedSource;
var WEB_PROTOCOLS = /* @__PURE__ */ new Set(["http:", "https:", "mailto:"]);
function safeUrl(href) {
  if (href.startsWith("#")) return true;
  try {
    return WEB_PROTOCOLS.has(new URL(href, location.href).protocol);
  } catch {
    return false;
  }
}
var probe = document.createElement("template");
function renderedElement(markup, tag) {
  probe.innerHTML = markup;
  const element = probe.content.firstElementChild;
  return element?.localName === tag ? element : null;
}
var markdownTokens = (text) => tokenize?.(text) ?? null;
function sourcePositions(markdown) {
  const NativeState = markdown.inline.State;
  markdown.inline.State = class extends NativeState {
    pushPending() {
      const from = this.sourcePendingFrom ?? this.pos - this.pending.length;
      const to = from + this.pending.length;
      const token = super.pushPending();
      token.meta = { ...token.meta, source: [from, to] };
      this.sourcePendingFrom = null;
      return token;
    }
    push(...args) {
      const token = super.push(...args);
      token.meta = { ...token.meta, sourceAt: this.pos };
      return token;
    }
  };
  const nativeRules = markdown.inline.ruler.getRules.bind(markdown.inline.ruler);
  const wrapped = /* @__PURE__ */ new WeakMap();
  markdown.inline.ruler.getRules = (chain) => nativeRules(chain).map((rule) => {
    if (!wrapped.has(rule))
      wrapped.set(rule, (state, silent) => {
        const from = state.pos;
        const pendingFrom = from - state.pending.length;
        if (!silent && !state.pending) state.sourcePendingFrom = from;
        const count = state.tokens.length;
        const ok = rule(state, silent);
        if (!ok || silent) return ok;
        const emitted = state.tokens.slice(count).filter((token) => !token.meta?.source);
        let delimiterAt = from;
        for (const token of emitted) {
          let span = [from, state.pos];
          if (token.type === "text" && emitted.every((item) => item.type === "text")) {
            span = [delimiterAt, delimiterAt + token.content.length];
            delimiterAt = span[1];
          } else if (token.type === "link_open") {
            span = [from, token.meta.sourceAt];
          } else if (token.type === "link_close") {
            span = [token.meta.sourceAt, state.pos];
          }
          if (token.markup === "linkify" || emitted.some((item) => item.markup === "linkify") && token.type === "text") {
            const matched = markdown.linkify.match(state.src.slice(pendingFrom, state.pos)).at(-1);
            const start = pendingFrom + matched.index;
            span = token.type === "link_open" ? [start, start] : token.type === "link_close" ? [state.pos, state.pos] : [start, state.pos];
          } else if (emitted.some((item) => item.markup === "autolink")) {
            span = token.type === "link_open" ? [from, from + 1] : token.type === "link_close" ? [state.pos - 1, state.pos] : [from + 1, state.pos - 1];
          }
          token.meta = {
            ...token.meta,
            source: span,
            escapes: token.info === "escape" && token.content !== token.markup ? [span[0]] : []
          };
        }
        return ok;
      });
    return wrapped.get(rule);
  });
  const keepJoined = (before, after) => {
    const alive = new Set(after);
    let first = null;
    let escapes = [];
    for (const { token, source, escaped } of before) {
      escapes.push(...escaped);
      if (source && !first && (token.type !== "text" || token.content)) first = source;
      if (alive.has(token)) {
        if (source && first && token.type === "text")
          token.meta.source = [first[0], source[1]];
        if (token.meta) token.meta.escapes = escapes;
        first = null;
        escapes = [];
      }
    }
  };
  const snapshot = (tokens3) => tokens3.map((token) => ({
    token,
    source: token.meta?.source,
    escaped: token.meta?.escapes ?? []
  }));
  const secondRules = markdown.inline.ruler2.getRules.bind(markdown.inline.ruler2);
  markdown.inline.ruler2.getRules = (chain) => secondRules(chain).map((rule) => (state) => {
    const before = snapshot(state.tokens);
    rule(state);
    keepJoined(before, state.tokens);
  });
  markdown.core.ruler.after("inline", "source_content", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline")
        token.meta = { ...token.meta, sourceContent: token.content };
  });
  markdown.core.ruler.before("linkify", "source_before_linkify", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline") {
        token.meta ??= {};
        let inLink = 0;
        token.meta.beforeLinks = token.children.map((child) => {
          if (child.type === "link_open") inLink++;
          else if (child.type === "link_close") inLink--;
          let source = child.meta?.source;
          if (!inLink && source && child.type === "text" && child.content) {
            const raw = token.meta.sourceContent.slice(source[0], source[1]);
            const at = raw.indexOf(child.content);
            if (at < 0) throw new Error("leaf: Markdown text token lost its source");
            source = [source[0] + at, source[0] + at + child.content.length];
            child.meta.source = source;
          }
          return {
            token: child,
            content: child.content,
            source,
            links: !inLink && child.type === "text" ? markdown.linkify.match(child.content) ?? [] : []
          };
        });
      }
  });
  markdown.core.ruler.after("linkify", "source_after_linkify", (state) => {
    for (const inline of state.tokens)
      if (inline.type === "inline") {
        const before = inline.meta.beforeLinks;
        let at = 0;
        let textAt = 0;
        let link = null;
        for (const token of inline.children) {
          if (token.meta?.source || before[at]?.token === token) {
            while (at < before.length && before[at].token !== token) at++;
            at++;
            textAt = 0;
            link = null;
            continue;
          }
          if (textAt === before[at]?.content.length && token.type !== "link_close") {
            at++;
            textAt = 0;
          }
          const original = before[at];
          if (!original?.source) continue;
          let span;
          if (token.type === "link_open") {
            link = original.links.find(
              (match) => match.index >= textAt && markdown.normalizeLink(match.url) === token.attrGet("href")
            );
            if (!link) throw new Error("leaf: Markdown autolink lost its source");
            textAt = link.index;
            span = [textAt, textAt];
          } else if (token.type === "link_close") {
            textAt = link.lastIndex;
            span = [textAt, textAt];
            link = null;
          } else if (link) {
            span = [link.index, link.lastIndex];
            textAt = link.lastIndex;
          } else {
            const from = original.content.indexOf(token.content, textAt);
            if (from < 0)
              throw new Error("leaf: Markdown linkified text lost its source");
            textAt = from + token.content.length;
            span = [from, textAt];
          }
          token.meta = {
            ...token.meta,
            source: span.map((offset) => original.source[0] + offset)
          };
        }
        delete inline.meta.beforeLinks;
      }
  });
  markdown.core.ruler.before("text_join", "source_before_join", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline") token.meta.beforeJoin = snapshot(token.children);
  });
  markdown.core.ruler.after("text_join", "source_after_join", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline") {
        keepJoined(token.meta.beforeJoin, token.children);
        delete token.meta.beforeJoin;
      }
  });
}
function makeMarkdown(module, breaks) {
  const markdown = new module.MarkdownIt({ html: false, breaks, linkify: true }).use(
    module.taskLists,
    { enabled: false }
  );
  markdown.linkify.set({ fuzzyLink: true });
  markdown.renderer.rules.softbreak = (_tokens, _at, options) => options.breaks ? "<br>" : "\n";
  markdown.renderer.rules.hardbreak = () => "<br>";
  markdown.validateLink = () => true;
  const admitLinks = (tokens3) => {
    const links = [];
    for (const token of tokens3) {
      if (token.type === "link_open") {
        token.meta = { ...token.meta, linked: safeUrl(token.attrGet("href")) };
        links.push(token);
      } else if (token.type === "link_close") {
        token.meta = { ...token.meta, linked: links.pop().meta.linked };
      }
      if (token.children) admitLinks(token.children);
    }
  };
  markdown.core.ruler.push("safe_links", (state) => {
    for (const block of state.tokens)
      if (block.type === "inline") admitLinks(block.children);
  });
  markdown.renderer.rules.text_special = markdown.renderer.rules.text;
  markdown.renderer.rules.link_open = (tokens3, at, options, env, renderer) => {
    const token = tokens3[at];
    if (!token.meta.linked) return "";
    const href = token.attrGet("href");
    if (isCanonicalMediaUrl(href)) token.attrSet("href", scopedMediaUrl(href));
    return renderer.renderToken(tokens3, at, options);
  };
  markdown.renderer.rules.link_close = (tokens3, at, options, env, renderer) => tokens3[at].meta.linked ? renderer.renderToken(tokens3, at, options) : "";
  markdown.renderer.rules.image = (tokens3, at, options, env, renderer) => {
    const token = tokens3[at];
    const href = token.attrGet("src");
    const alt = renderedWords(
      renderer.renderInline(token.children, options, env),
      true
    );
    token.attrSet("alt", alt);
    if (!safeUrl(href)) return escapeHtml(alt);
    const markup = renderer.renderToken(tokens3, at, options);
    if (!isCanonicalMediaUrl(href)) return markup;
    const image = renderedElement(markup, "img");
    const source = scopedMediaUrl(href);
    image.setAttribute("src", source);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "lf-media-open lf-message-media";
    button.setAttribute("data-lf-offer", "button");
    button.setAttribute("data-lf-said", "");
    button.setAttribute("data-lf-media-url", source);
    button.setAttribute("aria-label", `View ${alt || "Image"}`);
    button.append(image);
    return button.outerHTML;
  };
  return markdown;
}
function loadMarkdown(onError = null) {
  const attempt = ready ??= import("/vendor/markdown-it.esm.js").then((module) => {
    const markdown = makeMarkdown(module, true);
    let singleLine;
    let positioned;
    render2 = (text) => markdown.render(text);
    renderInline = (text, breaks) => (breaks ? markdown : singleLine ??= makeMarkdown(module, false)).renderInline(
      text
    );
    tokenize = (text) => {
      if (!positioned) {
        positioned = makeMarkdown(module, true);
        sourcePositions(positioned);
      }
      return positioned.parse(text, {});
    };
  });
  return attempt.then(() => true).catch((error) => {
    if (ready === attempt) ready = void 0;
    onError?.(error);
    return false;
  });
}

// runtime/video-controls.js
var PLAYER = PAGE_PAINT_ATTRIBUTE.player;
var SCOPE = /* @__PURE__ */ Symbol("recording");
var STEP_SECONDS = 5;
var players = /* @__PURE__ */ new Map();
var clock = (seconds) => {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};
var duration = (video) => Number.isFinite(video.duration) ? video.duration : 0;
function toggle(video) {
  if (!video.paused) return video.pause();
  video.play().catch((error) => {
    if (error.name !== "AbortError") throw error;
  });
}
function paintTime({ video, time }) {
  const at = String(video.currentTime);
  if (time.value !== at) time.value = at;
  keeps(
    time,
    "aria-valuetext",
    `${clock(video.currentTime)} of ${clock(duration(video))}`
  );
}
function paint(player) {
  const { video, bar, play, time } = player;
  const playing = !video.paused;
  bar.classList.toggle("lf-video-playing", playing);
  keeps(play, "aria-label", playing ? "Pause recording" : "Play recording");
  keeps(time, "max", String(duration(video)));
  keeps(time, "disabled", duration(video) ? null : "");
  paintTime(player);
}
function prepare(video) {
  const bar = offer("div", "lf-video-controls");
  const play = offer("button", "lf-video-play");
  play.tabIndex = -1;
  play.append(
    iconElement("play", "lf-video-icon"),
    iconElement("pause", "lf-video-icon")
  );
  const time = offer("input", "lf-video-time", void 0, "range");
  time.tabIndex = -1;
  time.min = "0";
  time.step = "any";
  keeps(time, "aria-label", "Recording position");
  bar.append(play, time);
  keeps(bar, "role", "group");
  keeps(bar, "aria-label", video.getAttribute("aria-label") || "Recording");
  const player = {
    video,
    bar,
    play,
    time,
    authoredTabindex: video.getAttribute("tabindex"),
    events: new AbortController(),
    /** @type {ReturnType<typeof commandScope> | null} */
    scope: null
  };
  const { signal } = player.events;
  const on = (target, type, listener) => target.addEventListener(type, listener, { signal });
  for (const type of ["play", "pause", "ended", "loadedmetadata", "durationchange"])
    on(video, type, () => paint(player));
  on(video, "seeked", () => paintTime(player));
  on(video, "timeupdate", () => paintTime(player));
  let frame = 0;
  const followFrames = () => {
    paintTime(player);
    frame = video.paused || signal.aborted ? 0 : video.requestVideoFrameCallback(followFrames);
  };
  on(video, "playing", () => {
    if (frame) video.cancelVideoFrameCallback(frame);
    frame = video.requestVideoFrameCallback(followFrames);
  });
  on(video, "click", (event) => {
    if (plainPress(event)) toggle(video);
  });
  on(time, "input", () => video.currentTime = Number(time.value));
  const show = (flag, force) => {
    if (force) revealControl(bar, video);
    bar.classList.toggle(flag, force);
  };
  on(video, "pointerenter", () => show("lf-video-hover", true));
  on(video, "pointerleave", () => show("lf-video-hover", false));
  on(video, "focus", () => show("lf-video-keyed", video.matches(":focus-visible")));
  on(video, "blur", () => show("lf-video-keyed", false));
  tabFromBlock(bar, video, signal);
  player.scope = commandScope("On a recording", [
    {
      id: "recording.play",
      keys: [" "],
      title: () => video.paused ? "play recording" : "pause recording",
      // The register runs the command when its control is pressed.
      control: play,
      run: () => {
        if (focused() === video) show("lf-video-keyed", true);
        toggle(video);
      }
    },
    {
      id: "recording.step",
      keys: ["ArrowLeft", "ArrowRight"],
      routes: [
        {
          id: "recording.back",
          binding: "ArrowLeft",
          title: `back ${STEP_SECONDS} seconds`
        },
        {
          id: "recording.forward",
          binding: "ArrowRight",
          title: `forward ${STEP_SECONDS} seconds`
        }
      ],
      title: `back / forward ${STEP_SECONDS} seconds`,
      repeat: true,
      run: (binding) => {
        show("lf-video-keyed", true);
        const step = binding === "ArrowLeft" ? -STEP_SECONDS : STEP_SECONDS;
        video.currentTime = Math.min(
          duration(video),
          Math.max(0, video.currentTime + step)
        );
      }
    }
  ]);
  players.set(video, player);
  return player;
}
function trade(player) {
  const { video, scope } = player;
  projectCommandScope(video, SCOPE, scope);
  keeps(video, PLAYER, "");
  keeps(video, "controls", null);
  if (player.authoredTabindex === null) keeps(video, "tabindex", "0");
  paint(player);
}
function giveBack(video) {
  const player = players.get(video);
  if (!player) return;
  players.delete(video);
  player.events.abort();
  releaseControl(player.bar);
  projectCommandScope(video, SCOPE, null);
  keeps(video, "tabindex", player.authoredTabindex);
  keeps(video, "controls", "");
  keeps(video, PLAYER, null);
}
function watchVideos() {
  const root = document.documentElement;
  const fallenBack = () => !root.hasAttribute("data-lf-interactive");
  new MutationObserver(() => {
    if (fallenBack()) for (const video of [...players.keys()]) giveBack(video);
  }).observe(root, { attributes: true, attributeFilter: ["data-lf-interactive"] });
  watchArrivals(`video[controls], video[${PLAYER}]`, [], {
    arriveBatch(videos) {
      if (fallenBack()) return;
      const read = videos.filter(nameable).map((video) => {
        const player = players.get(video) ?? prepare(video);
        return {
          player,
          reading: anchorControl(player.bar, video),
          levels: headerLevels(video),
          insets: readInsets(video)
        };
      });
      for (const { player, reading, levels, insets } of read) {
        aimControl(reading);
        writeInsets(player.bar, insets);
        standInChrome(player.bar, player.video, levels);
        trade(player);
      }
    },
    leave: giveBack
  });
}

// runtime/widget-imports.js
function registeredTags(scope, registry3) {
  const tags = /* @__PURE__ */ new Set([
    ...scope.localName ? [scope.localName] : [],
    ...[...scope.querySelectorAll("*")].map((element) => element.localName)
  ]);
  return [...tags].filter((tag) => isElementName(tag) && Object.hasOwn(registry3, tag));
}
function widgetImports(scope, registry3) {
  const initializers2 = [];
  const modules2 = [];
  const tags = registeredTags(scope, registry3);
  for (const tag of tags) {
    const entry = registry3[tag];
    if (entry?.["x-initial"]) initializers2.push({ tag, path: entry["x-initial"] });
    if (entry?.["x-upgrade"]) modules2.push(tag);
  }
  const shadow = tags.some(
    (tag) => registry3[tag]["x-shadow"] || Object.values(registry3[tag]["x-state"] ?? {}).some(
      (state) => state.creates && registry3[state.creates.child]["x-shadow"]
    )
  );
  return { initializers: initializers2, modules: modules2, shadow };
}

// runtime/widget-loader.js
var rememberedPassageRoots = /* @__PURE__ */ new WeakSet();
var within = (scope, selector) => [
  ...scope.matches?.(selector) ? [scope] : [],
  ...scope.querySelectorAll(selector)
];
function rememberPassageParts(scope = document, source = ["page", null]) {
  scope = initialSource(scope);
  for (const tag of tagsDeclaring(
    (entry) => entry["x-upgrade"] && !entry["x-verbatim"]
  ))
    for (const root of within(scope, tag)) {
      const live = initialOrigin(root);
      if (rememberedPassageRoots.has(live)) continue;
      rememberedPassageRoots.add(live);
      fencePassageParts(live, [...root.children].map(initialOrigin));
    }
  for (const [ownerIndex, root] of preservingOwners(scope).entries()) {
    const live = initialOrigin(root);
    if (rememberedPassageRoots.has(live)) continue;
    rememberedPassageRoots.add(live);
    identifyPreserving(root, [...source, ownerIndex]);
  }
}
var preservingOwners = (scope) => within(scope, "*").filter((root) => registry[root.localName]?.["x-verbatim"]);
function identifyPreserving(root, owner) {
  verbatimOwnerIdentity.set(initialOrigin(root), owner);
  let boundaryIndex = 0;
  const visit = (parent) => {
    for (const child of parent.children) {
      if (registry[child.localName]?.["x-upgrade"])
        verbatimBoundaryIdentity.set(initialOrigin(child), {
          owner,
          index: boundaryIndex++
        });
      else visit(child);
    }
  };
  visit(root);
}
function reindexPassageOwners(scope = document, source = ["page", null]) {
  for (const [ownerIndex, root] of preservingOwners(initialSource(scope)).entries())
    identifyPreserving(root, [...source, ownerIndex]);
}
var modules = /* @__PURE__ */ new Map();
var initializers = /* @__PURE__ */ new Map();
var registryUrl = () => runtimeResource("/registry.json");
var widgetUrl = (tag) => offlineInteractive ? runtimeModule(`/widgets/${tag}.js`) : runtimeResource(`/widgets/${tag}.js`);
async function loadWidgetDependencies(scope) {
  await Promise.all([
    loadDeclaredMarkdown(scope),
    ...widgetImports(scope, registry).shadow ? [loadShadowRules()] : []
  ]);
}
async function importWidgetModules(scope) {
  const required = widgetImports(scope, registry);
  await Promise.all(
    required.initializers.map(({ tag, path }) => {
      if (document.documentElement.lfInitial.has(tag)) return;
      if (!initializers.has(path))
        initializers.set(
          path,
          offlineInteractive ? import(runtimeModule(path)) : import(runtimeResource(path))
        );
      return initializers.get(path);
    })
  );
  await Promise.all(
    required.modules.map((tag) => {
      if (!modules.has(tag)) modules.set(tag, import(widgetUrl(tag)));
      return modules.get(tag);
    })
  );
}
async function preloadWidgets(scope) {
  await loadWidgetDependencies(scope);
  await importWidgetModules(scope);
}
async function importWidgets(scope) {
  await loadWidgetDependencies(scope);
  formatDeclaredMarkdown(scope);
  await importWidgetModules(scope);
}
async function installDocument(scope) {
  const presentation = attachApplicationPresentation("document:installation", scope);
  try {
    rememberPassageParts(scope);
    rememberAuthoredParents(scope);
    const descriptors = stageWidgetDescriptors(scope);
    const authored = stageAuthoredStates(scope, /* @__PURE__ */ new Map());
    const prior = readApplication().document;
    applicationState.captureDocument({
      ...prior,
      registry,
      authored: new Map([...prior.authored, ...authored]),
      descriptors: new Map([...prior.descriptors, ...descriptors.descriptors])
    });
    commitWidgetDescriptors(descriptors);
    watchExternalLinks();
    watchCodeBlocks();
    watchVideos();
    await importWidgets(scope);
    await settle(presentation, scope, [scope], whenApplicationPresented);
  } finally {
    presentation.disconnect();
  }
}
async function patchDocument(scope, patch) {
  const presentation = attachApplicationPresentation("document:patch", scope);
  try {
    const { roots, widgets, ...result } = patch();
    await settle(presentation, scope, roots, () => whenWidgetsPresented(widgets));
    return result;
  } finally {
    presentation.disconnect();
  }
}
async function settle(presentation, scope, arrived, presented) {
  const painted = Promise.all(arrived.map(paintDeclaredWords));
  const presenting = presentation.present(scope);
  presenting.resolve(painted);
  await presenting.ready;
  await presented();
  reachScrollers(scope);
}
async function upgradeWidgets({ buildReactionBar }) {
  const response = await fetch(registryUrl());
  if (!admitResponse(response)) return false;
  if (!response.ok)
    throw new Error(`leaf: registry failed to load (${response.status})`);
  adoptRegistry(await response.json());
  if (!sameLayer(registry.$layer.generation)) return false;
  revealLayer();
  buildReactionBar();
  await installDocument(document.body);
  return true;
}

// runtime/storage.js
var PAGE_SCOPE = document.documentElement.dataset.lfPageScope;
var { stored, tabStore: initialTabStore } = document.documentElement.lfStorage;
var tabStore = initialTabStore;
var views = (holder) => holder.ownerDocument.documentElement.lfViews;
var openingView = (holder, members) => views(holder).opening(holder, members);
var keepView = (holder, member) => views(holder).keep(holder, member);
var draftStore = stored(() => localStorage, "local", PAGE_SCOPE);
var userStore = document.documentElement.lfStorage.userStore;

// runtime/drafts.js
var DRAFT = "lf-draft:";
var PAGE_DRAFT = "general";
var whereDraft = (ctx) => draftStore.where(DRAFT + ctx);
var DRAFT_NEWS = "lf-drafts";
var draftCache = /* @__PURE__ */ new Map();
var tellDraft = (ctx, value, payload = void 0) => document.dispatchEvent(
  new CustomEvent(DRAFT_NEWS, { detail: { ctx, value, payload } })
);
var parseDraftRecord = (value) => {
  if (typeof value !== "string") return null;
  try {
    const record = JSON.parse(value);
    if (!record || typeof record !== "object" || typeof record.attempt !== "string" || !(record.base === null || typeof record.base === "string") || (record.settled === true ? Object.keys(record).some(
      (key) => !["attempt", "base", "settled"].includes(key)
    ) : typeof record.text !== "string" || record.payload !== void 0 && (!record.payload || typeof record.payload !== "object" || Array.isArray(record.payload)) || record.held !== void 0 && typeof record.held !== "string" || Object.keys(record).some(
      (key) => !["attempt", "text", "base", "payload", "held"].includes(key)
    )))
      return null;
    return record;
  } catch {
    return null;
  }
};
var storedDraft = (ctx) => {
  const read = draftStore.read(DRAFT + ctx);
  return read.available ? parseDraftRecord(read.value) : null;
};
var attemptAccepted = (attempt) => runtime.receipts.some((event) => event.attempt === attempt);
var writeDraftRecord = (ctx, record) => draftStore.set(DRAFT + ctx, JSON.stringify(record));
var rawDraftRecord = (ctx) => {
  if (draftCache.has(ctx)) return draftCache.get(ctx).record;
  const read = draftStore.read(DRAFT + ctx);
  const record = read.available ? parseDraftRecord(read.value) : null;
  if (record) draftCache.set(ctx, { record, durable: true });
  return record;
};
var sameDraftRecord = (left, right) => left === null && right === null || left !== null && right !== null && JSON.stringify(left) === JSON.stringify(right);
var projectDraftRecord = (ctx, record) => queueMicrotask(() => {
  const current = draftCache.get(ctx)?.record ?? null;
  if (!sameDraftRecord(current, record)) return;
  const active = current && !current.settled && !attemptAccepted(current.attempt);
  tellDraft(ctx, active ? current.text : null, active ? current.payload : void 0);
});
var sharedIsBaseOf = (branch, shared) => branch.base === null ? shared === null : shared?.attempt === branch.base;
var replyContext = (key) => `reply:${key}`;
var rewriteContext = (id) => `rewrite:${id}`;
var THREAD_DRAFT = /^(reply|rewrite):(.*)$/s;
function threadDraft(ctx) {
  const match = THREAD_DRAFT.exec(ctx);
  return match ? { part: match[1], name: match[2] } : null;
}
var isReply = (ctx) => threadDraft(ctx)?.part === "reply";
var refreshDraftRecord = (ctx) => {
  const cached = draftCache.get(ctx);
  const read = draftStore.read(DRAFT + ctx);
  if (!read.available) return cached?.record ?? null;
  const shared = parseDraftRecord(read.value);
  if (cached && !cached.durable) {
    if (sameDraftRecord(cached.record, shared)) {
      cached.durable = true;
      return cached.record;
    }
    if (sharedIsBaseOf(cached.record, shared)) {
      if (cached.record.settled) cached.durable = writeDraftRecord(ctx, cached.record);
      return cached.record;
    }
  }
  const changed2 = Boolean(cached && !sameDraftRecord(cached.record, shared));
  if (shared) draftCache.set(ctx, { record: shared, durable: true });
  else draftCache.delete(ctx);
  if (changed2) projectDraftRecord(ctx, shared);
  return shared;
};
var sentAttempts = /* @__PURE__ */ new Map();
var unsettledDraftRecord = (ctx) => {
  const record = rawDraftRecord(ctx);
  return record && !record.settled && !attemptAccepted(record.attempt) ? record : null;
};
var activeDraftRecord = (ctx) => {
  const record = unsettledDraftRecord(ctx);
  return sentAttempts.get(ctx) === record?.attempt ? null : record;
};
var draftHasContent = (ctx) => Boolean(unsettledDraftRecord(ctx)?.text);
var settleDraft = (ctx, attempt) => {
  const current = refreshDraftRecord(ctx);
  if (!current || current.settled || current.attempt !== attempt) return false;
  const currentDurable = draftCache.get(ctx)?.durable;
  const storedRecord = { attempt, base: attempt, settled: true };
  const durable = writeDraftRecord(ctx, storedRecord);
  const record = durable ? storedRecord : {
    attempt,
    base: currentDurable ? current.attempt : current.base,
    settled: true
  };
  draftCache.set(ctx, { record, durable });
  return true;
};
var saveDraft = (ctx, text, payload, held = carriedHeld(ctx)) => {
  const cached = draftCache.get(ctx);
  const previous = rawDraftRecord(ctx);
  const base = cached && !cached.durable && previous ? previous.base : previous?.attempt ?? null;
  const record = {
    text,
    attempt: randomId(),
    base,
    ...payload === void 0 ? {} : { payload },
    ...held ? { held } : {}
  };
  const durable = writeDraftRecord(ctx, record);
  draftCache.set(ctx, { record, durable });
  return durable;
};
var carriedHeld = (ctx) => {
  const previous = rawDraftRecord(ctx);
  return previous && !previous.settled && sentAttempts.get(ctx) !== previous.attempt ? previous.held : void 0;
};
var holdReply = (ctx, held) => {
  const current = activeDraftRecord(ctx);
  if (!current) return false;
  const { held: _, ...rest } = current;
  const record = held ? { ...rest, held } : rest;
  draftCache.set(ctx, { record, durable: writeDraftRecord(ctx, record) });
  return true;
};
var clearDraft = (ctx) => {
  const current = rawDraftRecord(ctx);
  if (!current || current.settled) {
    draftCache.delete(ctx);
    return false;
  }
  return settleDraft(ctx, current.attempt);
};
function transferDraft(from, to, text) {
  const source = activeDraftRecord(from);
  if (!source || from === to) return false;
  const editor = [...draftEditors].find((view) => view.ctx === from) ?? [...draftEditors].find((view) => view.ctx === to);
  const selection = writingPlace?.context === from ? writingPlace.selection : readCaret(editor && editorInput(editor));
  const held = [carriedHeld(to), carriedHeld(from)].filter(Boolean).join("\n\n") || null;
  const durable = isReply(to) ? saveDraft(to, held ? `${text}

${held}` : text, void 0, null) : saveDraft(to, text, void 0, held);
  keepWritingPlace({
    context: to,
    selection: selection ?? [0, 0],
    generation: randomId()
  });
  if (durable && settleDraft(from, source.attempt))
    projectDraftRecord(from, draftCache.get(from).record);
  tellDraft(to, activeDraftRecord(to)?.text ?? text);
  return true;
}
var loadDraft = (ctx) => activeDraftRecord(ctx)?.text ?? null;
var loadDraftPayload = (ctx) => activeDraftRecord(ctx)?.payload;
var draftContexts = () => /* @__PURE__ */ new Set([
  ...draftCache.keys(),
  ...draftStore.keys().filter((key) => key.startsWith(DRAFT)).map((key) => key.slice(DRAFT.length))
]);
function settleAcceptedDrafts() {
  for (const ctx of draftContexts()) {
    const record = refreshDraftRecord(ctx);
    if (record && !record.settled && attemptAccepted(record.attempt) && settleDraft(ctx, record.attempt))
      tellDraft(ctx, null);
  }
}
function claimDraft(ctx, owns) {
  const before = activeDraftRecord(ctx);
  const refreshed = refreshDraftRecord(ctx);
  const current = refreshed && !refreshed.settled && !attemptAccepted(refreshed.attempt) ? refreshed : null;
  if (!before || !current || current.attempt !== before.attempt || current.text !== before.text || !owns())
    return null;
  return current;
}
var standGesture = (ctx, current) => {
  sentAttempts.set(ctx, current.attempt);
  tellDraft(ctx, null);
  return (sent) => {
    if (sentAttempts.get(ctx) === current.attempt) sentAttempts.delete(ctx);
    if (sent) {
      if (settleDraft(ctx, current.attempt)) tellDraft(ctx, null);
      return;
    }
    if (activeDraftRecord(ctx)?.attempt !== current.attempt) return;
    tellDraft(ctx, current.text);
  };
};
async function sendDraft(ctx, owns, send) {
  const current = claimDraft(ctx, owns);
  if (!current) return null;
  const flight = send(current.attempt, current.payload);
  const answer = standGesture(ctx, current);
  const sent = await flight;
  answer(sent);
  return sent;
}
function sendMessage(ctx, owns, send) {
  const current = claimDraft(ctx, owns);
  if (!current) return null;
  const flight = send(current.attempt, current.payload);
  const answer = standGesture(ctx, current);
  if (!flight) {
    answer(null);
    return null;
  }
  if (!isReply(ctx)) {
    openedFrom.set(current.attempt, ctx);
    const under2 = replyContext(current.attempt);
    if (current.held && !activeDraftRecord(under2)) {
      saveDraft(under2, current.held);
      tellDraft(under2, current.held);
    }
  }
  const previousPlace = writingPlace;
  const sentPlace = previousPlace?.context === ctx ? {
    context: isReply(ctx) ? ctx : replyContext(current.attempt),
    selection: [0, 0],
    generation: previousPlace.generation
  } : null;
  if (sentPlace) keepWritingPlace(sentPlace);
  void Promise.resolve(flight).then((sent) => {
    answer(sent);
    if (sent) openedFrom.delete(current.attempt);
    if (!sent && sentPlace && writingPlace?.generation === sentPlace.generation && writingPlace.context === sentPlace.context)
      keepWritingPlace(previousPlace);
  });
  return { attempt: current.attempt, id: `${PENDING}${current.attempt}` };
}
var openedFrom = /* @__PURE__ */ new Map();
var draftEditors = /* @__PURE__ */ new Set();
var WRITING_PLACE = "lf-writing-place";
var isPlace = (place2) => typeof place2?.context === "string" && typeof place2.generation === "string" && Array.isArray(place2.selection) && place2.selection.slice(0, 2).every(Number.isInteger);
var [writingPlace, earlierPlaces] = (() => {
  try {
    const stored2 = JSON.parse(draftStore.get(WRITING_PLACE));
    if (!isPlace(stored2)) return [null, []];
    const { earlier = [], ...place2 } = stored2;
    return [place2, Array.isArray(earlier) ? earlier.filter(isPlace) : []];
  } catch {
    return [null, []];
  }
})();
var writingRoutes = /* @__PURE__ */ new Map();
var editorInput = (editor) => typeof editor.input === "function" ? editor.input() : editor.input;
var storeWritingPlace = () => draftStore.set(
  WRITING_PLACE,
  writingPlace && JSON.stringify({ ...writingPlace, earlier: earlierPlaces })
);
var keepWritingPlace = (place2) => {
  if (writingPlace && writingPlace.context !== place2.context)
    earlierPlaces = [
      ...earlierPlaces.filter(
        ({ context }) => context !== writingPlace.context && context !== place2.context
      ),
      writingPlace
    ].slice(-8);
  writingPlace = place2;
  storeWritingPlace();
};
function forgetWritingPlace(ctx) {
  earlierPlaces = earlierPlaces.filter(({ context }) => context !== ctx);
  if (writingPlace?.context !== ctx) return storeWritingPlace();
  writingPlace = null;
  while (earlierPlaces.length && !writingPlace) {
    const place2 = earlierPlaces.pop();
    if (draftHasContent(place2.context)) writingPlace = place2;
  }
  storeWritingPlace();
}
function keepRefusedWords(attempts) {
  const atEnd = (ctx) => {
    const end = (activeDraftRecord(ctx)?.text ?? "").length;
    return [end, end];
  };
  let held = 0;
  for (const attempt of attempts) {
    const from = openedFrom.get(attempt);
    openedFrom.delete(attempt);
    const under2 = replyContext(attempt);
    const box = activeDraftRecord(under2);
    if (from === void 0 || !box || !holdReply(from, box.text)) continue;
    const resumed = writingPlace?.context === under2;
    clearDraft(under2);
    if (resumed)
      keepWritingPlace({
        context: from,
        selection: atEnd(from),
        generation: randomId()
      });
    if (box.text) held += 1;
  }
  const returned = attempts.flatMap((attempt) => {
    const ctx = [...draftContexts()].find(
      (context) => activeDraftRecord(context)?.attempt === attempt
    );
    return ctx === void 0 ? [] : [ctx];
  });
  const shownIn = (ctx) => [...draftEditors].filter((view) => view.ctx === ctx).map((view) => editorInput(view)).find((input) => input?.isConnected && input.checkVisibility()) ?? null;
  const hidden = returned.filter((ctx) => !shownIn(ctx));
  const resumes = returned.find((ctx) => ctx === writingPlace?.context);
  if (resumes !== void 0)
    keepWritingPlace({ ...writingPlace, selection: atEnd(resumes) });
  for (const ctx of hidden.toReversed())
    if (writingPlace?.context !== ctx)
      keepWritingPlace({ context: ctx, selection: atEnd(ctx), generation: randomId() });
  const sentences = [
    hidden.length && "Draft kept \u2014 g i resumes writing",
    held && "Reply kept \u2014 it returns when its comment sends"
  ].filter(Boolean);
  return {
    said: sentences.length ? sentences.join(". ") : null,
    field: returned.map(shownIn).find(Boolean) ?? null
  };
}
var writingEditor = () => [...draftEditors].find((editor) => editorInput(editor) === focused());
var keepWritingCaret = () => {
  const editor = writingEditor();
  if (editor && editor.ctx === writingPlace?.context)
    keepWritingPlace({ ...writingPlace, selection: readCaret(editorInput(editor)) });
};
function rememberWriting(input) {
  const editor = [...draftEditors].find((view) => editorInput(view) === input);
  if (editor)
    keepWritingPlace({
      context: editor.ctx,
      selection: readCaret(input),
      generation: randomId()
    });
}
document.addEventListener("input", (event) => {
  const editor = [...draftEditors].find(
    (view) => event.composedPath().includes(editorInput(view))
  );
  if (editor) rememberWriting(editorInput(editor));
});
document.addEventListener("keyup", (event) => {
  if (CARET_KEYS.includes(event.key) || selectsAll(event)) keepWritingCaret();
});
document.addEventListener("pointerup", keepWritingCaret);
function registerWritingDestination(prefix, reveal) {
  writingRoutes.set(prefix, reveal);
  return () => writingRoutes.delete(prefix);
}
function moveToPage(ctx) {
  const words = loadDraft(ctx) ?? "";
  const text = [loadDraft(PAGE_DRAFT), words].filter(Boolean).join("\n\n");
  if (!transferDraft(ctx, PAGE_DRAFT, text)) return false;
  const shift = text.length - words.length;
  const [start, end, ...direction] = writingPlace.selection;
  keepWritingPlace({
    ...writingPlace,
    selection: [start + shift, end + shift, ...direction]
  });
  return true;
}
function createWritingResume({
  revealInThread,
  arriveEditor,
  holdsThreadDraft
}) {
  const holdsBox = (ctx) => threadDraft(ctx) ? holdsThreadDraft(ctx) : [...writingRoutes.keys()].some((prefix) => ctx.startsWith(prefix)) || [...draftEditors].some((view) => view.ctx === ctx);
  const resume = async () => {
    const place2 = writingPlace;
    if (!place2) return;
    const intent = retainUserIntent();
    let input;
    if (threadDraft(place2.context)) input = await revealInThread(place2.context, intent);
    else {
      const resolve = () => {
        const route = [...writingRoutes].find(
          ([prefix]) => place2.context.startsWith(prefix)
        );
        const editor = [...draftEditors].find(
          (view) => view.ctx === place2.context && view.resume
        );
        return route ? route[1](place2.context) : editor?.resume();
      };
      input = await arriveEditor(resolve, { intent, caret: place2.selection });
    }
    if (input === void 0 || !intent()) return;
    const matchesEditor = [...draftEditors].some(
      (view) => view.ctx === place2.context && editorInput(view) === input
    );
    if (matchesEditor && input?.isConnected && input.checkVisibility() && !input.readOnly && !input.disabled) {
      intent.handoff(() => {
        passErrorsAt(input);
        focusDestination(input, "move", { caret: place2.selection });
      });
      return;
    }
    if (runtime.showsActive && !holdsBox(place2.context) && moveToPage(place2.context)) {
      notice("Its box is gone, so its words moved to a comment on the page");
      return resume();
    }
    raiseError(
      `That writing place is unavailable${runtime.showsActive ? "" : " on this version"}`
    );
  };
  return {
    id: "writing.resume",
    keys: ["i"],
    description: "Resume writing",
    title: "Resume writing",
    touch: "Resume writing",
    menu: "keys",
    when: () => writingPlace !== null,
    run: resume
  };
}
function captureDraftEditing(input = focused()) {
  const editor = [...draftEditors].find((view) => editorInput(view) === input);
  if (!editor) return null;
  return {
    context: editor.ctx,
    mirrored: editor.mirrored,
    attempt: activeDraftRecord(editor.ctx)?.attempt,
    words: input.value,
    selection: readCaret(input),
    scroll: [input.scrollLeft, input.scrollTop]
  };
}
var draftEditingStands = (editing) => Boolean(editing) && activeDraftRecord(editing.context)?.attempt === editing.attempt;
function draftEditingDestination(editing, handoff) {
  const shown = (view) => Boolean(editorInput(view)?.checkVisibility({ visibilityProperty: true }));
  const placed2 = (view) => editorInput(view)?.isConnected;
  const roots = [...draftEditors].filter(
    (view) => view.ctx === editing.context && !view.mirrored && (placed2(view) || view.resume)
  );
  const editor = roots.find(shown) ?? roots.find(placed2) ?? roots[0];
  if (!editor) return null;
  const open2 = shown(editor) ? null : editor.resume?.()?.open;
  if (open2) handoff(open2);
  return shown(editor) ? editorInput(editor) : null;
}
function restoreDraftEditing(editing, input) {
  if (!draftEditingStands(editing)) return false;
  const editor = [...draftEditors].find((view) => editorInput(view) === input);
  if (!editor || editor.ctx !== editing.context || !input.isConnected || !input.checkVisibility() || input.value !== editing.words || focused() !== input)
    return false;
  focusDestination(input, "return", { caret: editing.selection });
  [input.scrollLeft, input.scrollTop] = editing.scroll;
  return true;
}
function watchDraft(ctx, callback, { input = null, mirrored = false, resume = null } = {}) {
  const editor = input && { ctx, input, mirrored, resume };
  if (editor) draftEditors.add(editor);
  const update2 = (ev) => ev.detail.ctx === ctx && callback(ev.detail.value, ev.detail.payload);
  document.addEventListener(DRAFT_NEWS, update2);
  return () => {
    document.removeEventListener(DRAFT_NEWS, update2);
    if (editor) draftEditors.delete(editor);
  };
}
function watchDrafts(prefix, callback) {
  const update2 = (ev) => ev.detail.ctx.startsWith(prefix) && callback(ev.detail.ctx);
  document.addEventListener(DRAFT_NEWS, update2);
  return () => document.removeEventListener(DRAFT_NEWS, update2);
}
addEventListener("storage", (ev) => {
  const prefix = whereDraft("").key;
  if (!ev.key?.startsWith(prefix)) return;
  const ctx = ev.key.slice(prefix.length);
  const incoming = parseDraftRecord(ev.newValue);
  const cached = draftCache.get(ctx);
  const current = cached?.record;
  if (current && !cached.durable) {
    if (sameDraftRecord(current, incoming)) cached.durable = true;
    else if (sharedIsBaseOf(current, incoming)) {
      cached.durable = writeDraftRecord(ctx, current);
      return;
    }
  }
  if (incoming) draftCache.set(ctx, { record: incoming, durable: true });
  else draftCache.delete(ctx);
  const active = incoming && !incoming.settled && !attemptAccepted(incoming.attempt);
  tellDraft(ctx, active ? incoming.text : null, active ? incoming.payload : void 0);
});
function mirrorDraft(ta, sync, ctx, {
  retained = false,
  mirrored = false,
  resume = null,
  onChange = () => {
  },
  blank = () => ""
} = {}) {
  const off = watchDraft(
    ctx,
    (value) => {
      if (!retained && !ta.isConnected) return off();
      sync.load(value ?? blank());
      onChange(value);
    },
    { input: ta, mirrored, resume }
  );
  return off;
}

// runtime/off-flow.js
var surfaces = /* @__PURE__ */ new Map();
function offFlowSurfaceOf(node) {
  for (const [surface, { floats }] of surfaces)
    if (floats() && under(node, surface)) return surface;
  return null;
}
var unseen = (node, surface) => {
  const box = node.getBoundingClientRect();
  const bounds = surface.getBoundingClientRect();
  const shown = shownWindow();
  return Math.max(box.top, bounds.top) < shown.top - 1 || Math.min(box.bottom, bounds.bottom) > shown.bottom + 1;
};
function follow(surface, node, behavior) {
  const { floats, away, bringBack } = surfaces.get(surface);
  if (floats() && (away() || unseen(node, surface))) bringBack(behavior);
}
function declareOffFlowSurface(surface, { floats = () => true, away = () => false, bringBack }) {
  surfaces.set(surface, { floats, away, bringBack });
  surface.addEventListener(
    "lf-before-edit",
    (event) => follow(surface, event.target, scrollBehavior()),
    { capture: true }
  );
}
onStanding((node, cause, left) => {
  if (!node || !left || cause === "return") return;
  for (const surface of surfaces.keys())
    if (under(node, surface) && under(left, surface))
      follow(surface, node, scrollBehavior());
});
function bringBackSurfaceOf(node, behavior = scrollBehavior()) {
  for (const surface of surfaces.keys())
    if (under(node, surface)) follow(surface, node, behavior);
}

// runtime/thread/selectors.js
var THREAD = ".lf-page-thread, [data-lf-thread-view]";
var drawnThreadId = (node) => node?.dataset.thread ?? null;
var SAYS_IN = `${THREAD}, .lf-thread-seat`;
var SAY_ROW = ".lf-thread-reply, .lf-say";
var SAY_BOX = SAY_ROW.split(", ").map((row) => `:scope > ${row} ${TEXT_FIELD}`).join(", ");

// runtime/thread/reply-landing.js
var replyRowOf = (held, control) => {
  const reply = control === held ? [...held.children].find((node) => node.matches(SAY_ROW)) : control.closest(SAY_ROW);
  return reply?.parentElement === held ? reply : null;
};
var replyPinned = (reply) => Boolean(reply) && stuckBox(reply) === reply;
var separateTranscript = (held) => {
  const transcript = held.querySelector(":scope > .lf-thread-transcript");
  return transcript && userScrollport(getComputedStyle(transcript).overflowY) ? transcript : null;
};
var landingTarget = (held, control) => {
  if (fitsWhole(held)) return { node: held };
  const reply = replyRowOf(held, control);
  if (replyPinned(reply))
    return control === held ? { node: null } : { node: held, block: "end" };
  if (reply && fitsWhole(reply)) return { node: reply };
  if (control === held && alreadyShown(held)) return { node: null };
  return { node: control };
};
var onScreen = (node) => seenRect(node, /* @__PURE__ */ new Map()) !== null;
var latestTurn = (transcript) => [...transcript.querySelectorAll(":scope > :is(.lf-msg, .lf-thread-checkpoint)")].at(
  -1
) ?? null;
function showLatestTurn(transcript) {
  scrollToEnd(transcript);
  const latest = latestTurn(transcript);
  if (!latest) return;
  const over = transcript.getBoundingClientRect().top + transcript.clientTop - latest.getBoundingClientRect().top;
  const headHeight = latest.firstElementChild?.getBoundingClientRect().height ?? 0;
  if (over > headHeight) moveScrollerBy(transcript, -over);
}
function landThread(held, control, behavior, block) {
  bringBackSurfaceOf(held, behavior);
  const transcript = separateTranscript(held);
  if (transcript && control !== held && replyRowOf(held, control)) {
    scrollToEnd(transcript, behavior);
    return;
  }
  if (transcript?.contains(control)) {
    scrollIntoView(control, { behavior, block });
    return;
  }
  const target = landingTarget(held, control);
  scrollIntoView(target.node, { behavior, block: target.block ?? block });
}
var landings = /* @__PURE__ */ new WeakMap();
function keepThreadLanding(held) {
  const landing = landings.get(held);
  if (!landing) return;
  if (!landing.mayLand()) {
    landings.delete(held);
    return;
  }
  landThread(held, landing.control, "instant", landing.block);
}
function scrollThreadIntoView(held, control, behavior = scrollBehavior(), block = "nearest") {
  const mayLand = retainUserIntent({
    available: () => held.isConnected && control.isConnected && under(control, held)
  });
  landings.set(held, { control, block, mayLand });
  landThread(held, control, behavior, block);
}
function sendLanding(input) {
  const held = input.closest(SAYS_IN);
  if (!held) return () => {
  };
  const reply = replyRowOf(held, input);
  const read = () => ({
    foot: standingAt(reply, "bottom"),
    within: reply.getBoundingClientRect().bottom - held.getBoundingClientRect().top
  });
  const stood = reply && !replyPinned(reply) && !separateTranscript(held) && alreadyShown(reply) ? read() : null;
  return (standing2 = held) => {
    const mayLand = retainUserIntent({
      source: standing2,
      available: () => held.isConnected
    });
    void whenDocumentPresented().then(() => {
      if (!mayLand() || !input.isConnected) return;
      if (stood === null || !held.contains(reply))
        return scrollThreadIntoView(held, input, "instant");
      returnTo(reply, "bottom", stood.foot + read().within - stood.within);
      revealWritingArea(held, input, reply);
      if (standingAt(reply, "bottom") < stood.foot)
        returnTo(reply, "bottom", stood.foot);
    }).catch(() => {
    });
  };
}
var rowHeights = /* @__PURE__ */ new WeakMap();
var transcriptPlaces = /* @__PURE__ */ new WeakMap();
var covered = (reply) => (reply.previousElementSibling?.getBoundingClientRect().bottom ?? -Infinity) - reply.getBoundingClientRect().top;
var revealWritingArea = (held, input, reply) => {
  bringBackSurfaceOf(held, "instant");
  const target = reply && fitsWhole(reply) ? reply : input;
  scrollIntoReadingBand(target, target, "nearest", "instant");
};
function revealEditor(message, caretLine) {
  const held = message.closest(SAYS_IN);
  if (!held) return;
  bringBackSurfaceOf(held, "instant");
  const target = fitsWhole(message) ? message : caretLine;
  scrollIntoReadingBand(target, target, "nearest", "instant");
  const reply = replyRowOf(held, held);
  if (!replyPinned(reply)) return;
  const margin = parseFloat(getComputedStyle(message).scrollMarginBlockEnd) || 0;
  const over = target.getBoundingClientRect().bottom + margin - reply.getBoundingClientRect().top;
  if (over > 0) moveScrollerBy(scrollerFor(reply), over);
}
function followBoxGrowth(input) {
  const held = input.closest(SAYS_IN);
  if (!held) return;
  const reply = replyRowOf(held, input);
  if (!reply) return;
  const transcript = separateTranscript(held);
  if (transcript) {
    const place2 = transcriptPlaces.get(input);
    if (place2?.transcript === transcript && place2.atTail && transcript.clientHeight < place2.height)
      scrollToEnd(transcript);
    transcriptPlaces.delete(input);
    if (!onScreen(reply)) revealWritingArea(held, input, reply);
    return;
  }
  if (!replyPinned(reply)) return revealWritingArea(held, input, reply);
  const height = reply.getBoundingClientRect().height;
  const grew = height - (rowHeights.get(input) ?? height);
  rowHeights.set(input, height);
  const by = Math.max(0, Math.min(grew, covered(reply)));
  if (by) scrollerFor(reply).scrollBy({ top: by, behavior: "instant" });
  if (!onScreen(reply)) revealWritingArea(held, input, reply);
}
function readBoxPlace(input) {
  const held = input.closest(SAYS_IN);
  const reply = held && replyRowOf(held, input);
  if (!reply) return;
  rowHeights.set(input, reply.getBoundingClientRect().height);
  const transcript = separateTranscript(held);
  if (transcript)
    transcriptPlaces.set(input, {
      transcript,
      height: transcript.clientHeight,
      atTail: atScrollEnd(transcript)
    });
}
var standingAt = (node, edge) => {
  let at = node.getBoundingClientRect()[edge];
  for (const box of scrollersOf(node)) at += box.scrollTop - aimedTop(box);
  return at;
};
function returnTo(node, edge, at) {
  for (const box of scrollersOf(node)) {
    const moved2 = standingAt(node, edge) - at;
    if (Math.abs(moved2) < 0.5) return;
    moveScrollerBy(box, moved2);
  }
}
function holdBox(control) {
  const held = control?.closest?.(SAYS_IN);
  if (!held || control !== focusedInView()) return () => {
  };
  const top = standingAt(control, "top");
  return () => {
    if (focused() !== control || !control.isConnected || !held.contains(control))
      return;
    returnTo(control, "top", top);
  };
}

// runtime/held-word.js
var HOLDS_WORD = "lf-holds-word";
var HOLDER = `.${HOLDS_WORD}`;
function holdToRead() {
  let hold = null;
  let released = null;
  const holderIn = (event) => event.composedPath().find((node) => node instanceof Element && node.matches(HOLDER));
  const read = (holder) => {
    if (hold.reading === holder) return;
    hold.reading?.removeAttribute("data-lf-held-word");
    hold.reading = holder;
    holder?.setAttribute("data-lf-held-word", "");
  };
  const under2 = (event) => {
    const holder = holderIn(event);
    return holder?.parentElement === hold.parent ? holder : null;
  };
  const end = (event, commit) => {
    if (hold?.pointerId !== event.pointerId) return;
    const holder = commit && plainPress(event) ? under2(event) : null;
    read(null);
    hold = null;
    if (!holder) return;
    released = holder;
    holder.dispatchEvent(
      new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        composed: true,
        detail: 1,
        clientX: event.clientX,
        clientY: event.clientY
      })
    );
  };
  document.addEventListener(
    "pointerdown",
    (event) => {
      released = null;
      if (hold) read(null);
      hold = null;
      if (!event.isPrimary || !plainPress(event)) return;
      const holder = holderIn(event);
      if (!holder || holder.matches(":disabled, [aria-disabled='true']")) return;
      const origin = (
        /** @type {Partial<Element>} */
        event.composedPath()[0]
      );
      if (origin.hasPointerCapture?.(event.pointerId))
        origin.releasePointerCapture(event.pointerId);
      hold = {
        pointerId: event.pointerId,
        parent: holder.parentElement,
        reading: null
      };
      read(holder);
    },
    { capture: true }
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      if (hold?.pointerId === event.pointerId) read(under2(event));
    },
    { capture: true }
  );
  document.addEventListener("pointerup", (event) => end(event, true), {
    capture: true
  });
  document.addEventListener("pointercancel", (event) => end(event, false), {
    capture: true
  });
  document.addEventListener(
    "click",
    (event) => {
      if (!released || !event.isTrusted || pressIsKeyboardActivation(event)) return;
      released = null;
      event.preventDefault();
      event.stopImmediatePropagation();
    },
    { capture: true }
  );
  document.addEventListener(
    "contextmenu",
    (event) => {
      if (hold) event.preventDefault();
    },
    { capture: true }
  );
}

// runtime/thread/message-edit.js
var OPEN_MESSAGE_EDIT = "lf-open-message-edit";
var open = /* @__PURE__ */ new Map();
var sending = /* @__PURE__ */ new Set();
function holdsMessageEdit(id, view) {
  const holder = open.get(id);
  if (!holder) return false;
  if (holder.view !== null && holder.view !== view) return false;
  holder.view = view;
  return true;
}
function releaseMessageEdit(id, view) {
  const holder = open.get(id);
  if (holder?.view === view) holder.view = null;
}
function openMessageEdit(id, view, thread) {
  for (const [other, holder] of [...open]) {
    if (other === id || holder.thread !== thread) continue;
    if (holder.view) holder.view.putEditAside();
    else if (!draftHasContent(rewriteContext(other))) open.delete(other);
  }
  const displaced2 = open.get(id)?.view;
  open.set(id, { view, thread });
  if (displaced2 && displaced2 !== view) displaced2.closeEdit();
}
var keptRewrite = (id) => !open.has(id) && !sending.has(id) && draftHasContent(rewriteContext(id));
var watchRewrite = (id, changed2) => watchDraft(rewriteContext(id), changed2);
function openMessageEditIn(thread, id) {
  const message = [...thread?.querySelectorAll(".lf-msg") ?? []].find(
    (node) => node.dataset.event === id
  );
  message?.dispatchEvent(new CustomEvent(OPEN_MESSAGE_EDIT));
  return message?.querySelector(`:scope > .lf-msg-body > .lf-msg-editor ${TEXT_FIELD}`) ?? null;
}
function threadRewrites({
  thread,
  views: views3,
  send,
  paint: paint2,
  box,
  home: home2,
  opening = () => {
  },
  landInThread,
  landSent
}) {
  const lastEditable = (before = null) => {
    const drawn3 = views3();
    const end = before === null ? drawn3.length : drawn3.findIndex(({ model }) => model?.id === before);
    const view = drawn3.slice(0, Math.max(end, 0)).findLast(
      ({ model }) => model?.author === "user" && model.body.kind !== "reaction" && model.body.text
    );
    return view?.model.editable ? view : null;
  };
  return {
    edit: {
      paint: paint2,
      send,
      // The rung above a rewrite is the thread's reply box, where ↑ came from, while it
      // is in view; a thread showing none, as a resolved one or a margin card not
      // replying, or one whose box is off screen, hands the user on as a sent reply
      // does, which moves nothing. A save in a resolved thread reopens it, so the box
      // its presentation draws then takes the caret, as Reopen's landing gives it
      // (#46, the user's decision, 2026-10-07).
      land: (message) => {
        const shown = () => {
          const input2 = box();
          return input2 && seenRect(input2, /* @__PURE__ */ new Map()) ? input2 : null;
        };
        const input = shown();
        if (input) return landInThread(input);
        landSent(home2(message));
        const mayLand = retainUserIntent();
        void whenDocumentPresented().then(() => {
          const drawn3 = shown();
          if (drawn3 && mayLand()) landInThread(drawn3);
        });
      },
      previous: (id) => lastEditable(id),
      // A rewrite of message `id` opens in `view`. It starts from the words as they
      // stand, so opening one is acting in the thread (`openMessageEdit`).
      opening: (id, view) => {
        opening(id);
        openMessageEdit(id, view, thread());
      },
      reveal: (message, caretLine) => revealEditor(message, caretLine)
    },
    editLast: {
      available: () => Boolean(lastEditable()),
      open: () => lastEditable()?.openEdit()
    }
  };
}
function closeMessageEdit(id, { discard }) {
  open.delete(id);
  if (!discard) return;
  const ctx = rewriteContext(id);
  clearDraft(ctx);
  tellDraft(ctx, null);
  forgetWritingPlace(ctx);
}
var MessageEditor = class {
  #stop;
  #putAside;
  #reveal;
  #settling = null;
  #follow;
  constructor(id, view, { wireInput, said: said2, base: currentBase, send, land: land2, paint: paint2, previous, reveal }) {
    const ctx = rewriteContext(id);
    let base = currentBase();
    const keptOver = loadDraftPayload(ctx)?.over;
    if (keptOver && keptOver !== base && !keptOver.startsWith(PENDING))
      raiseError(
        `This message changed since this edit began. It now says: \u201C${said2()}\u201D`
      );
    this.#reveal = reveal;
    this.node = offer("div", "lf-msg-editor lf-comment-box");
    this.input = offer(TEXT_FIELD);
    this.input.name = "edit";
    const actions = offer("span", "lf-msg-edit-actions");
    const save = offer("button", "lf-msg-control lf-msg-edit-save");
    const cancel = offer("button", "lf-msg-control lf-msg-edit-cancel");
    cancel.type = "button";
    cancel.title = "Cancel and discard changes";
    cancel.textContent = "Cancel";
    actions.append(cancel);
    this.foot = document.createElement("span");
    this.foot.className = "lf-msg-edit-foot";
    this.node.append(this.input, this.foot, actions);
    this.input.value = loadDraft(ctx) || said2();
    let opened = this.input.value;
    this.#follow = () => {
      if (base === currentBase() || draftHasContent(ctx) || this.input.value !== opened)
        return;
      base = currentBase();
      this.input.value = opened = said2();
    };
    const unchanged = () => {
      const words = this.input.value;
      return !words.trim() || words === said2();
    };
    const leave = (discard, { landing = true, says = null, painting = true } = {}) => {
      if (landing) land2();
      this.#stop();
      closeMessageEdit(id, { discard });
      if (painting) paint2();
      if (says) announce(says);
    };
    const close = () => leave(true, {
      says: unchanged() ? "Stopped editing" : "Edit discarded; the message is as it was"
    });
    const putAside = () => {
      if (!unchanged()) return;
      leave(true, { landing: false, painting: false });
      afterScript(paint2);
    };
    this.#putAside = putAside;
    const sync = wireInput(this.input, {
      hint: "Edit message",
      accessibleName: () => `Edit message: ${said2().slice(0, 60)}`,
      sends: "save",
      icon: null,
      sendBtn: save,
      submitIn: actions,
      save: (value) => {
        saveDraft(ctx, value, { over: base });
        tellDraft(ctx, value, { over: base });
      },
      send: async (_text, raw, owns) => {
        if (unchanged()) return leave(true, { says: "No change to save" });
        sending.add(id);
        const flight = sendDraft(ctx, owns, (attempt) => send(raw, { attempt, base }));
        leave(false, { painting: false });
        let sent = null;
        try {
          sent = await flight;
        } finally {
          sending.delete(id);
        }
        if (sent) forgetWritingPlace(ctx);
        paint2();
      },
      rows: [
        {
          id: "message.edit.previous",
          keys: ["ArrowUp"],
          description: "From the start of an unchanged box, edit my message before this one",
          title: "edit previous message",
          // A walk passes over words as they stand: words the user changed hold ↑ for
          // the caret, as a reply box holding words does, until Save or Escape. It
          // starts where the caret stood as the key went down, before the field's own ↑
          // took it to the start of a first line; a held ↑'s repeats run no row.
          when: () => {
            const [start, end] = caretAtKey(this.input) ?? [
              this.input.selectionStart,
              this.input.selectionEnd
            ];
            return start === 0 && end === 0 && unchanged() && Boolean(previous());
          },
          run: () => {
            const before = previous();
            putAside();
            before.openEdit();
          }
        }
      ]
    });
    keys(
      this.node,
      "Editing a message",
      [
        {
          id: "message.edit.close",
          keys: ["Escape"],
          description: "Stop editing, leaving the message as it was",
          title: "stop editing",
          run: () => close()
        }
      ],
      { escape: "inner" }
    );
    cancel.addEventListener("mousedown", (event) => event.preventDefault());
    cancel.addEventListener("click", () => close());
    this.#stop = mirrorDraft(this.input, sync, ctx, { retained: true, blank: said2 });
  }
  // Put the user on the words with the caret after them, where a rewrite usually starts,
  // and bring the editor into view, its last line, where the caret stands, at least. A
  // long one's lines take their height only as the field draws them, after this, so the
  // reveal follows the box's size until the user does anything. Every opening is the
  // user's own gesture, so the arrival is a move.
  enter() {
    const end = this.input.value.length;
    focusDestination(this.input, "move", { caret: [end, end] });
    this.#reveal(this.foot);
    this.#settling?.disconnect();
    const mayReveal = retainUserIntent();
    this.#settling = sizeObserver((entries, observer) => {
      if (!mayReveal() || !this.node.isConnected) return observer.disconnect();
      this.#reveal(this.foot);
    });
    this.#settling.observe(this.node);
  }
  // The message this rewrites stands as `said` and `base` now read it.
  follow() {
    this.#follow();
  }
  // Make way for another editor opening in the thread, without moving the user: close
  // this one where the user has changed nothing in it.
  putAside() {
    this.#putAside();
  }
  dispose() {
    this.#settling?.disconnect();
    this.#stop();
  }
};

// runtime/thread/workflow.js
var STAGE_LABELS = Object.freeze({
  sending: "Sending",
  sent: "Sent",
  queued: "Queued",
  picked_up: "Picked up",
  working: "Working",
  replying: "Replying",
  answered: "Answered"
});
var CONDITION_LABELS = Object.freeze({
  ended: "Turn ended",
  interrupted: "Interrupted",
  stale: "Update stale",
  failed: "Failed"
});
var WAITING_FOR_PICKUP = "Waiting for pickup";
var NOT_ANSWERED = "Not answered";
var workflowLabel = (workflow, { answered = false } = {}) => {
  if (!workflow) return "";
  if (workflow.condition)
    return workflow.condition.kind === "stale" && workflow.condition.operation === "delivery" ? WAITING_FOR_PICKUP : workflow.condition.kind === "failed" && workflow.condition.operation === "response" ? NOT_ANSWERED : CONDITION_LABELS[workflow.condition.kind] ?? "Failed";
  if (workflow.stage === "answered" && !answered) return "";
  return STAGE_LABELS[workflow.stage] ?? "";
};
var workflowTitle = (workflow) => {
  if (!workflow) return "";
  const label = workflowLabel(workflow, { answered: true });
  return [label, workflow.detail].filter(Boolean).join(" \xB7 ");
};
var progressFace = (workflow) => !workflow || workflow.condition ? null : workflow.stage === "picked_up" ? "picked_up" : ["working", "replying"].includes(workflow.stage) ? "working" : null;
var isWorkflowProgress = (workflow) => progressFace(workflow) !== null;
var workflowStep = (workflow) => progressFace(workflow) === "working" && workflow.detail || workflowLabel(workflow);
var isPageWidgetWorkflow = (workflow, revision) => workflow.subject.kind === "widget" && workflow.thread === null && workflow.revision <= revision;
var handedBack = (workflow) => workflow.stage === "answered" || workflow.stage === "sending" && workflow.condition?.kind === "failed";
var tier = (workflow) => (handedBack(workflow) ? 0 : 2) + Number(workflow.stage === "sending");
function strongestWorkflow(workflows) {
  let strongest = null;
  for (const candidate of workflows)
    if (strongest === null || tier(candidate) < tier(strongest)) strongest = candidate;
  return strongest;
}
var todoLabel = (running) => running ? "Working" : "To-do open";
function threadAttention(thread) {
  if (thread.resolved) return null;
  const workflow = thread.attention?.workflow ? thread.workflows.find(
    (candidate) => candidate.id === thread.attention.workflow
  ) ?? null : null;
  if (thread.attention?.kind === "needs_user") {
    const answering = thread.attention.reason === "widget";
    const nextMove = answering ? "answer" : workflow?.subject.kind === "thread" ? "resend" : "retry";
    const owed = new Set(
      (thread.obligations ?? []).filter((item) => item.source.kind === "update" && item.next_actor === "agent").map((item) => item.id)
    );
    const secondary = strongestWorkflow(
      thread.workflows.filter(
        (candidate) => owed.has(candidate.obligation) && candidate.id !== workflow?.id
      )
    );
    return Object.freeze({
      kind: "needs_user",
      label: `My turn to ${nextMove}`,
      workflow,
      secondary: [answering ? "" : workflowLabel(workflow), workflowLabel(secondary)].filter(Boolean).join(" \xB7 ")
    });
  }
  if (thread.attention?.kind === "waiting" && thread.attention.reason === "todo") {
    const [{ title, running }] = thread.todos;
    return Object.freeze({
      kind: "waiting",
      label: todoLabel(running),
      workflow: null,
      secondary: running?.text ?? title
    });
  }
  if (thread.attention?.kind === "waiting")
    return Object.freeze({
      kind: "waiting",
      label: workflowLabel(workflow) || (thread.attention.reason === "uncertain" ? "Uncertain" : "Waiting"),
      workflow,
      secondary: ""
    });
  return null;
}

// runtime/design-readings.js
var DESIGN_MODE_KEY = "lf-design-mode";
function designName(element) {
  const tag = element.tagName.toLowerCase();
  return `${tag.startsWith("lf-") ? tag : addressableWord(element)} \xB7 ${element.id}`;
}

// runtime/thread/reaction-strips.js
var ordinal = 0;
var ReactionStripView = class {
  #commands;
  #registration = null;
  #model = null;
  #paletteId = `lf-reactions-${++ordinal}`;
  constructor(commands2) {
    this.#commands = commands2;
    this.node = document.createElement("div");
    this.node.classList.add("lf-react-strip", "lf-react-surface");
    this.node.setAttribute("role", "group");
    this.node.setAttribute("aria-label", "React to this reply");
  }
  present(model) {
    this.#model = model;
    this.node.classList.toggle("lf-open", model.latest);
    render(
      html` <button
          type="button"
          class="lf-msg-control lf-react-trigger lf-ui"
          data-lf-gen="1"
          data-lf-offer="button"
          aria-expanded="false"
          aria-controls=${this.#paletteId}
          aria-label="Add reaction"
          title="Add reaction"
          @click=${() => this.#registration.toggle()}
        >
          ${iconTemplate("reaction", "lf-msg-control-icon")}
        </button>
        <span
          class="lf-react-palette"
          id=${this.#paletteId}
          popover="auto"
          role="group"
          @toggle=${(event) => {
        if (event.newState === "closed") this.#registration.close();
      }}
          aria-label="Reactions for this reply"
        >
          ${repeat(
        model.choices,
        (choice) => choice.name,
        (choice) => html` <button
                type="button"
                class="lf-outline-chip lf-react ${HOLDS_WORD} lf-ui"
                data-lf-gen="1"
                data-lf-offer="button"
                data-token=${choice.name}
                title=${choice.label}
                aria-label=${choice.label}
                aria-pressed=${String(Boolean(choice.inForce))}
                aria-busy=${String(Boolean(choice.inForce?.pending))}
                @click=${() => this.#press(choice.name)}
              >
                <span class="lf-react-glyph">${choice.glyph}</span>
              </button>`
      )}
        </span>`,
      this.node
    );
    this.#registration ??= this.#commands.registerSurface(this.node, {
      trigger: this.node.querySelector(".lf-react-trigger"),
      palette: this.node.querySelector(".lf-react-palette"),
      target: "the reply"
    });
    return this.node;
  }
  #press(name) {
    const model = this.#model;
    const sent = this.#commands.actions.setReaction(
      model.thread,
      model.message,
      name,
      !model.choices.find((choice) => choice.name === name).inForce
    );
    this.#registration.close();
    this.#commands.pressed();
    void sent;
  }
  retire() {
    this.#registration?.close();
  }
};

// runtime/thread/messages.js
var loadMessageMarkdown = () => loadMarkdown((error) => reportPageError(error, `markdown renderer failed to load`));
var renderedProse = /* @__PURE__ */ new Map();
function proseReading(message) {
  const key = message.attempt ?? message.id;
  const edited = message.edited?.id ?? null;
  const text = message.text ?? "";
  const markdown = markdownReady();
  let reading = renderedProse.get(key);
  if (!reading || reading.id !== message.id || reading.edited !== edited || reading.text !== text || reading.markdown !== markdown) {
    const pasted = readAttachedMedia(text);
    const html2 = renderMarkdown(pasted.text);
    const mediaHtml = renderMarkdown(writeAttachedMedia("", pasted.paths));
    reading = Object.freeze({
      id: message.id,
      edited,
      text,
      markdown,
      html: html2,
      mediaHtml,
      plainText: renderedWords(html2 + mediaHtml)
    });
    renderedProse.set(key, reading);
  }
  return reading;
}
function messageText(message) {
  if (message.token) {
    const token = tokenEntry(message.token);
    return `${token?.glyph ?? ""} ${message.token}`.trim();
  }
  return message.suggestion ? message.text ?? "" : proseReading(message).plainText;
}
function threadName(thread) {
  if (thread.title != null) return thread.title;
  const { root } = thread;
  const words = labelWords(
    root.body.kind === "authored" ? root.body.text : messageText(root)
  );
  return words || (root.drawing ? "Drawing" : "");
}
var threadSummary = (thread) => ({
  topic: threadName(thread),
  latest: lastMovedAt(thread)
});
var authoredMessages = /* @__PURE__ */ new Map();
function prepareAuthoredMessage(message, thread) {
  const key = message.attempt ?? message.id;
  if (typeof thread !== "string" || !thread)
    throw new TypeError("an authored message needs its thread's id");
  if (!authoredMessages.has(key)) {
    const template = document.createElement("template");
    template.innerHTML = message.markup ?? "";
    rememberAuthoredParents(template.content);
    const descriptors = stageWidgetDescriptors(template.content, {
      kind: "thread",
      thread,
      message: message.id
    });
    const authored = stageAuthoredStates(template.content, /* @__PURE__ */ new Map());
    rememberPassageParts(template.content, ["event", message.id]);
    const text = template.content.textContent;
    writePrepaint(template.content);
    const nodes = Object.freeze([...template.content.childNodes]);
    authoredMessages.set(key, {
      message: message.id,
      body: {
        text,
        document: { thread, message: message.id }
      },
      authored,
      descriptors,
      nodes,
      root: template.content
    });
  }
  const prepared = authoredMessages.get(key);
  for (const descriptor of prepared.descriptors.descriptors.values())
    if (descriptor.document.thread !== thread || descriptor.document.message !== message.id)
      throw new TypeError("an authored message changed its frozen document identity");
  return prepared;
}
var authoredMessage = (message) => {
  const prepared = authoredMessages.get(message.attempt ?? message.id);
  if (!prepared)
    throw new Error("authored message presentation preceded semantic preparation");
  return prepared;
};
var FAILURE_LABEL = "Not answered";
function messageReading(message, { nativeAuthored = false, reactions, workflows, leaves = null }) {
  const workflow = strongestWorkflow(workflows);
  const token = isReaction(message) ? tokenEntry(message.token) : null;
  const kind = isReaction(message) ? "reaction" : message.suggestion ? "suggestion" : "prose";
  const prose = kind === "prose" ? proseReading(message) : null;
  return Object.freeze({
    key: messageKey(message),
    id: message.id,
    // A reply still streaming, which the answer it stands for completes in place.
    provisional: Boolean(message.provisional),
    // The agent's progress message (`ephemeral`): a step of work in hand, which the
    // thread shows as its run's face until an answer folds it (transcript.js).
    progress: Boolean(message.ephemeral),
    // What an answer leaves standing, while it stands: "Waiting on me" for the question the
    // user owes words to, "To-do open" for work it promised and has not ended
    // (thread-card.js).
    leaves,
    version: message.content_version,
    seq: moved(message).seq,
    unread: message.unread,
    attempt: message.attempt ?? null,
    author: message.author,
    by: message.author === "agent" ? message.agent : "Me",
    timestamp: message.ts,
    age: ago(message.ts),
    // What the message said before its last rewrite is the edited mark's to tell, since
    // answers above may have been about those words.
    edited: message.edited ? `Edited ${ago(message.edited.ts)}. Before, it said: \u201C${message.edited.was}\u201D` : null,
    editable: editable(message),
    failure: message.failure ?? null,
    pending: workflow?.stage === "sending",
    // What a rewrite of the message is written over (`base` on an edit): its current
    // content version.
    base: message.content_version,
    workflow,
    workflowLabel: workflowLabel(workflow),
    workflowTitle: workflowTitle(workflow),
    body: Object.freeze({
      kind,
      text: message.text ?? "",
      html: prose?.html ?? "",
      mediaHtml: prose?.mediaHtml ?? "",
      plainText: prose?.plainText ?? message.text ?? "",
      drawing: Boolean(message.drawing),
      token: message.token ?? null,
      glyph: token?.glyph ?? "",
      authored: message.body.kind === "authored"
    }),
    nativeAuthored,
    reactions
  });
}
var MessageView = class {
  #commands;
  #model = null;
  #reaction = null;
  #authored = null;
  #dressed = false;
  #arrivalMotion = null;
  #stopRead = null;
  #header = document.createElement("div");
  #editor = null;
  #kept = false;
  #stopKept = null;
  constructor(commands2) {
    this.#commands = commands2;
    this.node = document.createElement("div");
  }
  present(model, { arrived = false, headerControls = nothing } = {}) {
    const prior = this.#model;
    this.#model = model;
    if (!prior) {
      this.node.classList.add("lf-msg");
      this.node.dataset.message = model.key;
      this.#header.className = "lf-msg-head";
      this.node.classList.add("lf-ui");
      this.node.dataset.lfGen = "1";
      this.node.dataset.lfOffer = "";
      this.node.addEventListener("dblclick", (event) => {
        if (
          /** @type {Partial<Element>} */
          event.target.closest?.(
            ".lf-msg-editor, a[href]"
          )
        )
          return;
        if (!this.#model?.editable) return;
        window.getSelection()?.removeAllRanges();
        this.openEdit();
      });
      this.node.addEventListener(OPEN_MESSAGE_EDIT, () => this.openEdit());
    }
    const editing = model.editable && holdsMessageEdit(model.id, this);
    if (editing && !this.#editor)
      this.#editor = new MessageEditor(model.id, this, {
        wireInput: this.#commands.reply.wireInput,
        said: () => this.#model.body.text,
        base: () => this.#model.base,
        send: (text, options) => this.#commands.edit.send(this.#model.id, text, options),
        land: () => this.#commands.edit.land(this.node),
        paint: () => this.#commands.edit.paint(this.node),
        previous: () => this.#commands.edit.previous(this.#model.id),
        reveal: (caretLine) => this.#commands.edit.reveal(this.node, caretLine)
      });
    if (!editing && this.#editor) {
      this.#editor.dispose();
      this.#editor = null;
    }
    this.#editor?.follow();
    this.#kept = model.editable && !editing && keptRewrite(model.id);
    if (model.editable && !this.#stopKept)
      this.#stopKept = watchRewrite(model.id, () => {
        if (keptRewrite(this.#model.id) !== this.#kept)
          this.#commands.edit.paint(this.node);
      });
    keeps(this.#header, "data-lf-reflow", "text");
    if (prior && prior.author !== model.author)
      this.node.classList.toggle(prior.author, false);
    this.node.classList.toggle(model.author, true);
    keeps(this.node, "data-event", model.id);
    this.node.classList.toggle("lf-unread", Boolean(model.unread));
    keeps(this.node, "data-attempt", model.attempt || null);
    keeps(this.node, "aria-busy", model.pending ? "true" : null);
    keeps(this.node, "data-failure", model.failure || null);
    if (model.nativeAuthored && model.body.authored && !this.#authored)
      this.#authored = authoredMessage({
        id: model.id,
        attempt: model.attempt
      }).nodes;
    if (!model.reactions) this.#reaction?.retire();
    const strip = model.reactions ? (this.#reaction ??= new ReactionStripView(this.#commands.reaction)).present(
      model.reactions
    ) : nothing;
    const receipt = model.workflowLabel ? html`<span class="lf-msg-sending" title=${model.workflowTitle}
          >${model.workflowLabel}</span
        >` : nothing;
    render(
      html`
        <b>${model.by}</b
        ><span class="lf-msg-meta"
          ><time datetime=${model.timestamp}>${model.age}</time> ${receipt}
          ${model.leaves ? html`<span class="lf-msg-leaves">${model.leaves}</span>` : nothing}
          ${model.failure ? html`<span class="lf-msg-failure">${FAILURE_LABEL}</span>` : nothing}
          ${model.body.kind === "suggestion" ? html`<span class="lf-suggest-label">Suggestion</span>` : nothing}
          ${model.edited ? html`<span class="lf-edited" title=${model.edited}>edited</span>` : nothing}
          ${this.#kept ? html`<span
                  class="lf-msg-kept"
                  title="The rewrite is kept; open it to save or cancel"
                  >unsaved edit</span
                >` : nothing}
        </span>
        ${headerControls}
      `,
      this.#header
    );
    const rewrite = model.editable && !editing ? html`<button
            type="button"
            class="lf-msg-control lf-msg-edit lf-ui"
            tabindex="-1"
            data-lf-gen="1"
            data-lf-offer="button"
            aria-label="Edit message"
            title="Edit message"
            @click=${() => this.openEdit()}
          >
            ${iconTemplate("edit", "lf-msg-control-icon")}
          </button>` : nothing;
    render(
      html`
        ${this.#header}
        <div
          class=${`lf-msg-body${model.body.kind === "suggestion" ? " lf-suggest-body" : ""}`}
        >
          ${editing ? this.#editor.node : this.#body(model.body)}
          ${model.body.drawing ? html`<span class="lf-drawing-reference">Drawing comment</span>` : nothing}
          ${model.nativeAuthored && model.body.authored ? this.#authored : nothing}
        </div>
        ${model.body.authored && !model.nativeAuthored ? html`<button
                type="button"
                class="lf-btn lf-page-thread-open lf-ui"
                data-lf-gen="1"
                data-lf-offer="button"
                @click=${() => this.#commands.openThread(this.#model.id, { part: "message" })}
              >
                Open interactive reply
              </button>` : nothing}
        ${strip} ${rewrite}
      `,
      this.node
    );
    if (this.#authored && !this.#dressed) {
      markDeclared(this.node);
      renderSaid(this.node);
      renderQuiet(this.node);
      this.#dressed = true;
    }
    highlightBlocks(this.node);
    this.#stopRead = this.#commands.read.observeMessage(
      this.node.querySelector(":scope > .lf-msg-body"),
      model
    );
    if (!prior && (model.pending || arrived)) {
      this.#arrivalMotion = motion(
        this.node,
        [{ "--lf-msg-arrival": 1, offset: 0 }],
        flashDuration()
      );
    }
    return this.node;
  }
  // Open the user's own words for rewriting here, with the caret after them. False where
  // the message is not one they may rewrite.
  openEdit() {
    const model = this.#model;
    if (!model?.editable) return false;
    if (!this.#editor) {
      this.#commands.edit.opening(model.id, this);
      this.#commands.edit.paint(this.node);
    }
    this.#editor?.enter();
    return true;
  }
  // Draw the message as it stands, its rewrite having opened in another view.
  closeEdit() {
    this.#commands.edit.paint(this.node);
  }
  // Make way for another editor opening in the thread, closing this one where its
  // words are the message's own.
  putEditAside() {
    this.#editor?.putAside();
  }
  // The reading this view last drew.
  get model() {
    return this.#model;
  }
  // Whether this view draws an open rewrite.
  get editing() {
    return this.#editor !== null;
  }
  #body(body) {
    if (body.kind === "reaction")
      return html`<div class="lf-msg-text">
        <span class="lf-react-said">${`${body.glyph} ${body.token}`.trim()}</span>
      </div>`;
    if (body.kind === "suggestion")
      return html`<div class="lf-msg-text" .textContent=${body.text}></div>`;
    return html`<div class="lf-msg-text" .innerHTML=${body.html}></div>
      ${body.mediaHtml ? html`<div class="lf-msg-media" .innerHTML=${body.mediaHtml}></div>` : nothing}`;
  }
  commit() {
    if (!this.#model.reactions && this.#reaction) {
      this.#reaction.retire();
      this.#reaction = null;
    }
  }
  retire() {
    this.#arrivalMotion?.cancel();
    this.#reaction?.retire();
    if (this.#model) releaseMessageEdit(this.#model.id, this);
    this.#editor?.dispose();
    this.#editor = null;
    this.#stopKept?.();
    this.#stopKept = null;
    this.#stopRead?.();
  }
};
function messageHolding(id) {
  for (const { nodes, body } of authoredMessages.values())
    for (const node of nodes) {
      if (node.nodeType !== Node.ELEMENT_NODE) continue;
      const element = (
        /** @type {Element} */
        node
      );
      const kept = element.id === id ? element : element.querySelector(`[id="${CSS.escape(id)}"]`);
      if (kept) return { element: kept, ...body.document };
    }
  return null;
}
var addressableAt = (id) => elementById(id) ?? messageHolding(id)?.element ?? null;
function coordinateLabel(anchor, about) {
  if (about === "design") {
    const addressable2 = anchor?.section ? addressableAt(anchor.section) : null;
    const name = addressable2 ? designName(addressable2) : anchor?.section || "the page";
    return anchor?.quote ? `${name} \xB7 \u201C${anchor.quote}\u201D` : name;
  }
  const datum = datumLabel(anchor);
  if (datum) return anchor?.quote ? `${datum} \xB7 \u201C${anchor.quote}\u201D` : `\xA7 ${datum}`;
  if (anchor?.quote) return `\u201C${anchor.quote}\u201D`;
  if (!anchor?.section) return "";
  const addressable = addressableAt(anchor.section);
  if (anchor.visual) {
    const part = visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return `\xA7 ${addressable ? `${addressableWord(addressable)} \xB7 ${part}` : `${anchor.section} \xB7 ${part}`}`;
  }
  return `\xA7 ${addressable ? sectionLabel(addressable) : anchor.section}`;
}
function anchorLabel(anchor, about) {
  const label = coordinateLabel(anchor, about);
  return [about === "design" && "design", anchor?.part, label].filter(Boolean).join(" \xB7 ");
}

// runtime/keyboard/register.js
watchCommandScopes(() => [
  ...[...scopes.values()].flat(),
  { rows: [...commands.values()] }
]);
var ELEMENTS = /* @__PURE__ */ Symbol("the scopes of the focused element");
var PAGE = /* @__PURE__ */ Symbol("the page's own keys");
var RUNGS = /* @__PURE__ */ Symbol("Escape's fallback ladder");
var COMMAND_REFERENCE = "command.reference.open";
var GO_TO = "navigation.go-to.open";
var STACK = [
  "command reference",
  "page map",
  "go to",
  "response options",
  "reactions",
  "page search",
  "target picker",
  ELEMENTS,
  "region capture",
  // Among inner scopes the order is moot, since the modes and the Page Map stand it down
  // themselves.
  "standing",
  // A to-do on the user that the walk stands on, whose Done this scope carries.
  "todo",
  "versions",
  "composer",
  "text entry",
  "thread",
  "link",
  "disclosure",
  // The modes keep their own letters here and declare their Escape on the ladder,
  // because a mode is the stance the whole page is in and a surface opened while one
  // holds is opened inside it: a view the floating panel opens in Design mode comes off
  // first.
  "draw mode",
  "design mode",
  PAGE,
  // Outermost, so a page command still ranks ahead of the way out.
  RUNGS
];
var RUNG_LADDER = [
  "selection",
  // the selection, or the target a click captured
  "margin options",
  // the margin entry cluster the user unfolded
  "floating panel",
  // the menu or view the floating panel opened above its row
  "draw mode",
  // the drawing surface over the page
  "design mode",
  // the mode that comments on the layer
  "page"
  // whatever is left, in the chrome, and back onto the page
];
var PAGE_COMMANDS = [
  "comment.create",
  "writing.resume",
  "selection.restore",
  "target.picker.open",
  "reaction.open",
  "page.search.open",
  "page.search.repeat",
  "thread.walk",
  "queue.walk",
  "page.move",
  "scroll.move",
  "reading.align.top",
  "thread.unread.first",
  "navigation.panel.threads",
  "navigation.panel.queue",
  "navigation.panel.leaves",
  "navigation.page-map",
  "version.open",
  "history.undo",
  // Below the walks that reach one list at a time, because `g` opens a door to all of
  // them: a second way to somewhere the user can already get to.
  GO_TO,
  "draw.mode.enter",
  "capture.region.open",
  "design.mode.enter",
  "annotations.toggle",
  "panel.floating.fold",
  COMMAND_REFERENCE,
  // A real key the browser owns, and one gesture that is not a key at all.
  "browser.caret",
  "aim.comment"
];
var scopes = /* @__PURE__ */ new Map();
var commands = /* @__PURE__ */ new Map();
var rungs = /* @__PURE__ */ new Map();
var resolved = null;
var validated = false;
var place = (where, name) => {
  if (!where.includes(name))
    throw new Error(`leaf: ${String(name)} has no place in the page's keyboard`);
};
function pageScope(name, declaration) {
  place(STACK, name);
  if (declaration.ready !== void 0)
    declareCommandReadiness(declaration.rows, declaration.ready);
  const declarations = scopes.get(name) ?? [];
  declarations.push(declaration);
  scopes.set(name, declarations);
  resolved = null;
  validated = false;
  paintKeys();
  return () => {
    const remaining = scopes.get(name)?.filter((item) => item !== declaration) ?? [];
    if (remaining.length) scopes.set(name, remaining);
    else scopes.delete(name);
    resolved = null;
    validated = false;
    paintKeys();
  };
}
function pageCommand(row) {
  place(PAGE_COMMANDS, row.id);
  if (commands.has(row.id)) throw new Error(`leaf: ${row.id} is declared twice`);
  commands.set(row.id, row);
  resolved = null;
  validated = false;
  paintKeys();
  return row;
}
function pageRung(name, reading) {
  place(RUNG_LADDER, name);
  const readings = rungs.get(name) ?? [];
  readings.push(reading);
  rungs.set(name, readings);
  return () => {
    const remaining = rungs.get(name)?.filter((item) => item !== reading) ?? [];
    if (remaining.length) rungs.set(name, remaining);
    else rungs.delete(name);
  };
}
function rung() {
  const steps = [];
  for (const name of RUNG_LADDER) {
    for (const reading of rungs.get(name) ?? []) {
      const step = reading();
      if (step) steps.push({ ...step, name });
    }
  }
  const here = focused();
  let surface = null;
  for (const { root } of steps) {
    if (!root || root === document || !renderedUnder(here, root)) continue;
    if (!surface || renderedUnder(root, surface)) surface = root;
  }
  const holds = (step) => renderedUnder(step.root ?? document, surface);
  return (surface && steps.find(holds)) ?? steps[0] ?? null;
}
var BACK_OUT = {
  id: "navigation.back",
  keys: ["Escape"],
  title: () => rung() ? titleOf(rung()) : "Back",
  description: () => rung() ? descriptionOf(rung()) : void 0,
  when: () => Boolean(rung()),
  run: () => rung().out()
};
function assemble() {
  const rows = PAGE_COMMANDS.flatMap(
    (id) => commands.has(id) ? [commands.get(id)] : []
  );
  const unanswered = rows.filter((row) => row.touch === void 0).map((row) => row.id);
  if (unanswered.length)
    throw new Error(
      `leaf: ${unanswered.join(", ")} must declare \`touch\`: its words under a finger, or false where a finger reaches it directly`
    );
  const scopeRows = [...scopes.values()].flat().flatMap((scope) => scope.rows);
  const unreached = scopeRows.filter((row) => row.run && !row.exit && row.touch !== false).map((row) => row.id);
  if (unreached.length)
    throw new Error(
      `leaf: ${unreached.join(", ")} must be its stance's \`exit\` or declare \`touch: false\`: only a page command takes a finger's words`
    );
  return STACK.flatMap((name) => {
    if (name === PAGE) return { rows };
    if (name === RUNGS)
      return { root: () => rung()?.root ?? document, rows: [BACK_OUT] };
    if (typeof name !== "string") return name;
    return scopes.get(name) ?? [];
  });
}
function pageScopes() {
  if (offlineInteractive) return [ELEMENTS];
  resolved ??= assemble();
  if (!validated) {
    validated = true;
    for (const scope of resolved)
      if (typeof scope !== "symbol")
        checked(scope.rows, scope.title ?? "the page's own keys");
  }
  return resolved;
}
var namedScopes = () => STACK.flatMap((name) => typeof name === "string" ? scopes.get(name) ?? [] : []);
var exitOf = (scope) => scope.rows.find((row) => row.exit) ?? null;
function touchPresses2() {
  pageScopes();
  return PAGE_COMMANDS.flatMap(
    (id) => commands.has(id) ? touchPresses(commands.get(id)) : []
  );
}
function stances() {
  pageScopes();
  return namedScopes().flatMap((scope) => {
    const exit = exitOf(scope);
    return exit ? [{ scope, exit }] : [];
  });
}
var universalCommandReference = () => offlineInteractive ? void 0 : commands.get(COMMAND_REFERENCE);
var textEntryScope = () => scopes.get("text entry")?.[0];
var allButCommandReference = (binding) => !bindings(universalCommandReference()).includes(binding);
var pageDoor = (binding) => [COMMAND_REFERENCE, GO_TO].some(
  (id) => commands.has(id) && bindings(commands.get(id)).includes(binding)
);

// runtime/composing/capture.js
var selectionAnchor = (sel) => anchorForRange(pageRange(sel));
var drawn2 = (sel) => Boolean(sel?.rangeCount) && !pageRange(sel).collapsed;
var pageSelection = () => {
  const sel = getSelection();
  return drawn2(sel) && pageWords(sel.anchorNode) ? sel : null;
};
function createPassageSelection({ restore }) {
  let previous = null;
  return {
    remember(selection = pageSelection()) {
      if (!anchoringIsReady() || !selection || takesLetters(focused())) return;
      const anchor = selectionAnchor(selection);
      if (anchor.quote) previous = { anchor, backward: selectionBackward(selection) };
    },
    command: {
      id: "selection.restore",
      keys: ["v"],
      title: "Restore selection",
      description: "Restore the last selected passage",
      touch: "Restore selection",
      menu: "keys",
      when: () => previous !== null,
      run: async () => {
        const intent = retainUserIntent();
        const restored = await restore(previous.anchor, {
          backward: previous.backward,
          intent
        });
        if (!restored && intent())
          raiseError("That selected passage is unavailable on this version");
      }
    }
  };
}
var leftThePage = (sel = getSelection()) => drawn2(sel) && !pageWords(sel.focusNode);
var sameRun = (left, right) => Boolean(left && right) && segmentBlock(left.segment) === segmentBlock(right.segment) && left.segment.gen === right.segment.gen;
var sentenceUnits = new Intl.Segmenter(void 0, { granularity: "sentence" });
var edgeAt = (reading, i) => i >= 0 && i < reading.raw.length && pointAt(reading, i) === null;
function snapOut(reading, at, back) {
  const { raw, fences } = reading;
  const behind = fences.filter((f) => f <= at).at(-1) ?? 0;
  const ahead = fences.find((f) => f >= at) ?? raw.length;
  const joined = (i) => {
    if (!edgeAt(reading, i)) return true;
    let a = i - 1;
    while (edgeAt(reading, a)) a--;
    let b = i + 1;
    while (edgeAt(reading, b)) b++;
    return sameRun(pointAt(reading, a), pointAt(reading, b));
  };
  const inRun = (i) => !/\s/.test(raw[i]) && joined(i);
  let lo = at;
  while (lo > behind && inRun(lo - 1)) lo--;
  let hi = at;
  while (hi < ahead && inRun(hi)) hi++;
  let run = "";
  let boundary = 0;
  const from = [];
  for (let i = lo; i < hi; i++) {
    if (edgeAt(reading, i)) continue;
    if (i < at) boundary++;
    from.push(i);
    run += raw[i];
  }
  const word = textUnits.segment(run).containing(boundary);
  if (!word || word.index >= boundary || !word.isWordLike) return at;
  return back ? from[word.index] : from[word.index + word.segment.length - 1] + 1;
}
function snapSentence(reading, lo, hi) {
  const { raw, fences } = reading;
  const point = (i) => pointAt(reading, i);
  const first = point(lo);
  const last = point(hi - 1);
  if (!first || !last) return [lo, hi];
  if (closestAcross(first.node, "pre,code")) return [lo, hi];
  const belongs = (part) => sameRun(first, part);
  if (!belongs(last) || fences.some((f) => f > lo && f < hi)) return [lo, hi];
  for (let at = lo; at < hi; at++) {
    const part = point(at);
    if (part && !belongs(part)) return [lo, hi];
  }
  const behind = fences.filter((f) => f <= lo).at(-1) ?? 0;
  const ahead = fences.find((f) => f >= hi) ?? raw.length;
  const inScope = (at) => {
    const part = point(at);
    if (part) return belongs(part);
    let before = at - 1;
    while (before >= behind && edgeAt(reading, before)) before--;
    let after = at + 1;
    while (after < ahead && edgeAt(reading, after)) after++;
    return belongs(point(before)) && belongs(point(after));
  };
  let start = lo;
  while (start > behind && inScope(start - 1)) start--;
  let stop = hi;
  while (stop < ahead && inScope(stop)) stop++;
  let text = "";
  let selectedStart = 0;
  let selectedStop = 0;
  const from = [];
  let inWhitespace = false;
  for (let at = start; at < stop; at++) {
    if (edgeAt(reading, at)) continue;
    const character = raw[at].replace(COLLAPSE, " ");
    const whitespace = character === " ";
    if (whitespace && inWhitespace) continue;
    inWhitespace = whitespace;
    if (at < lo) selectedStart++;
    if (at < hi) selectedStop++;
    from.push(at);
    text += character;
  }
  const sentences = [...sentenceUnits.segment(text)];
  const atStart = sentences.find(
    (sentence) => sentence.index <= selectedStart && selectedStart < sentence.index + sentence.segment.length
  );
  const atStop = sentences.find(
    (sentence) => sentence.index < selectedStop && selectedStop <= sentence.index + sentence.segment.length
  );
  const edges = (sentence) => {
    if (!sentence) return null;
    const words = [...textUnits.segment(sentence.segment)].filter(
      (part) => part.isWordLike
    );
    if (!words.length) return null;
    const firstWord = words[0].index;
    const lastWord = words.at(-1).index + words.at(-1).segment.length;
    const leading = sentence.segment.slice(0, firstWord).match(/\p{P}+$/u)?.[0] ?? "";
    const trailing = sentence.segment.slice(lastWord).match(/^\p{P}+/u)?.[0] ?? "";
    return {
      contentStart: sentence.index + firstWord - leading.length,
      contentStop: sentence.index + lastWord + trailing.length,
      firstWord: sentence.index + firstWord,
      lastWord: sentence.index + lastWord
    };
  };
  let snappedStart = selectedStart;
  const startEdges = edges(atStart);
  if (startEdges && selectedStart >= startEdges.contentStart && selectedStart <= startEdges.firstWord)
    snappedStart = startEdges.contentStart;
  let snappedStop = selectedStop;
  const stopEdges = edges(atStop);
  if (stopEdges && selectedStop >= stopEdges.lastWord && selectedStop <= stopEdges.contentStop)
    snappedStop = stopEdges.contentStop;
  return [
    snappedStart === selectedStart ? lo : from[snappedStart],
    snappedStop === selectedStop ? hi : from[snappedStop - 1] + 1
  ];
}
function snapSelection() {
  if (!anchoringIsReady()) return;
  const sel = pageSelection();
  if (!sel) return;
  const range = pageRange(sel);
  const segments = segmentsIn(range);
  if (!segments.length) return;
  const reading = pageText();
  const [start, stop] = spanIn(reading, segments);
  let lo = snapOut(reading, start, true);
  let hi = snapOut(reading, stop, false);
  [lo, hi] = snapSentence(reading, lo, hi);
  if (lo === start && hi === stop) return;
  const first = pointAt(reading, lo);
  const last = pointAt(reading, hi - 1);
  const head = lo === start ? [range.startContainer, range.startOffset] : [first.node, first.offset];
  const tail = hi === stop ? [range.endContainer, range.endOffset] : [last.node, last.offset + 1];
  if (selectionBackward(sel, range)) selectEnds(tail, head);
  else selectEnds(head, tail);
}

// runtime/walk-position.js
var BOUNDARY_MS = 900;
var walking = null;
var boundaryTimer = 0;
function walkPositionLabel(noun, position, total, qualifier = "") {
  if (!noun && !qualifier) throw new Error("leaf: a walk position needs a noun");
  return [noun, `${position} of ${total}`, qualifier].filter(Boolean).join(" ");
}
function listWalkPosition(items, current, { identity = (item) => item, qualifier = "" } = {}) {
  if (!current) return null;
  const target = identity(current);
  const index = items.findIndex((item) => identity(item) === target);
  if (index < 0) return null;
  return { target, position: index + 1, total: items.length, qualifier };
}
function walkPosition() {
  if (!walking) return null;
  const position = walking.read();
  if (!position || position.target !== walking.target) {
    clearTimeout(boundaryTimer);
    boundaryTimer = 0;
    walking = null;
    return null;
  }
  return {
    boundary: walking.boundary,
    kind: walking.key,
    target: position.target,
    text: walkPositionLabel(
      walking.noun,
      position.position,
      position.total,
      position.qualifier
    )
  };
}
var STEPS = Object.freeze(["previous", "next", "first", "last"]);
var capital = (word) => word[0].toUpperCase() + word.slice(1);
function rowWalk({
  id,
  noun,
  plural,
  rows,
  position = () => listWalkPosition(rows(), focused()),
  steps = STEPS,
  landed,
  scroll = true
}) {
  const [up, down, home2, end] = steps;
  const route = (binding, step) => ({
    id: `${id}.${step}`,
    binding,
    title: `${capital(step)} ${noun.toLowerCase()}`
  });
  const land2 = (pick) => {
    const was = focused();
    const row = pick(rows());
    if (!row) return;
    focusDestination(row, "move");
    if (scroll) scrollIntoView(row, { block: "nearest" });
    beginWalk(id, noun, position);
    if (row !== was) landed?.(row);
  };
  return [
    {
      id: `${id}.walk`,
      keys: ["ArrowUp", "ArrowDown"],
      routes: [route("ArrowUp", up), route("ArrowDown", down)],
      title: `walk the ${plural}`,
      repeat: true,
      run: (binding) => land2(
        (list) => clampedRow(list, focused(), binding === "ArrowDown" ? 1 : -1, 0)
      )
    },
    {
      id: `${id}.edge`,
      keys: ["Home", "End"],
      routes: [route("Home", home2), route("End", end)],
      title: `${home2} / ${end}`,
      run: (binding) => land2((list) => binding === "Home" ? list[0] : list.at(-1))
    }
  ];
}
function beginWalk(key, noun, read, wrapped = false) {
  const position = read();
  if (!position) {
    clearTimeout(boundaryTimer);
    boundaryTimer = 0;
    walking = null;
    return null;
  }
  walkPositionLabel(noun, position.position, position.total, position.qualifier);
  const boundary = wrapped || walking?.key === key && walking.target === position.target;
  clearTimeout(boundaryTimer);
  const arrived = {
    boundary,
    key,
    noun,
    read,
    target: position.target
  };
  walking = arrived;
  holdStatus(BOUNDARY_MS);
  boundaryTimer = boundary ? setTimeout(() => {
    if (walking !== arrived) return;
    arrived.boundary = false;
    boundaryTimer = 0;
    repaint();
  }, BOUNDARY_MS) : 0;
  const shown = walkPosition();
  repaint();
  return shown?.text ?? null;
}

// runtime/thread/state.js
var threadState = readPart((root) => root.effective.thread);
var allThreads = () => threadState().all;
var readThreads = readPart((root) => root.effective.thread.collection);
var threadList = () => readThreads().threads;
var names = /* @__PURE__ */ new WeakMap();
function threadNamed(name) {
  const threads = allThreads();
  let index = names.get(threads);
  if (!index) names.set(threads, index = threadNames(threads));
  return index.get(name) ?? null;
}
var threadIdNamed = (name) => threadNamed(name)?.id ?? name;

// runtime/thread/replies.js
var REPLY_COMPOSITION = /* @__PURE__ */ Symbol("reply composition");
var compositions = /* @__PURE__ */ new Map();
var views2 = /* @__PURE__ */ new Map();
var available = (composition) => Boolean(composition) && views2.get(composition.context)?.has(composition) && composition.controls.input.isConnected;
function adopt(context, composition) {
  const session = compositions.get(context);
  if (session?.owner !== composition) session?.owner?.sync.cancelDictation();
  const caret = readCaret(session?.owner?.controls.input);
  if (session) session.owner = composition;
  else compositions.set(context, { owner: composition });
  if (caret) composition.controls.input.setSelectionRange(...caret);
  remember(composition);
}
function remember(composition) {
  const session = compositions.get(composition.context);
  if (session?.owner !== composition) return;
  const editing = captureDraftEditing(composition.controls.input);
  if (editing) session.editing = editing;
}
var compositionOf = (node) => closestAcross(node, SAY_ROW)?.[REPLY_COMPOSITION];
var replyDraftContext = (node) => compositionOf(node)?.context ?? null;
var replyThreadKey = (node) => compositionOf(node)?.key ?? null;
function holdReplyCompositions(threads, realize) {
  const current = new Map(
    threads.map((thread) => [replyContext(threadKey(thread)), thread])
  );
  const retained = [];
  const retired = [];
  for (const [context, session] of compositions) {
    if (!current.has(context)) {
      retired.push([context, session]);
      continue;
    }
    if (!session.owner || session.continuing) continue;
    const owner = session.owner;
    const editing = captureDraftEditing(owner.controls.input) ?? session.editing;
    if (!editing) continue;
    session.editing = editing;
    const intent = restrictUserIntent(
      retainUserIntent(),
      () => compositions.get(context) === session && session.owner === owner && draftEditingStands(editing)
    );
    retained.push({ context, session, owner, intent });
  }
  return async (restore) => {
    for (const [context, session] of retired)
      if (compositions.get(context) === session) endSession(context);
    const displaced2 = retained.filter(
      ({ session, owner, intent }) => !available(owner) && !session.continuing && intent()
    );
    for (const { session } of displaced2) session.continuing = true;
    try {
      await restore?.();
      for (const { context, owner, intent } of displaced2) {
        if (available(owner) || !intent()) continue;
        const destination = await realize(current.get(context).id, intent);
        if (!intent.available()) continue;
        const replacement = compositionOf(destination) ?? compositionOf(destination?.querySelector(SAY_ROW));
        if (replacement && replacement.controls.input.checkVisibility())
          adopt(context, carry(replacement, owner));
      }
    } finally {
      for (const { session } of displaced2) session.continuing = false;
    }
  };
}
var threadHoldsDraft = (key, ids) => draftHasContent(replyContext(key)) || ids.some((id) => draftHasContent(rewriteContext(id)));
var replyDraftsHold = (retains) => [...compositions].some(
  ([context, session]) => loadDraft(context) !== null && !retains(session.owner?.controls.input)
);
function endSession(context) {
  const session = compositions.get(context);
  compositions.delete(context);
  if (session?.owner && !session.owner.binding) session.owner.row.remove();
  return session;
}
function dismissContext(context) {
  const session = endSession(context);
  if (!session) return;
  session.owner?.sync.cancelDictation();
  session.owner?.changed();
}
var dismissReply = (key) => dismissContext(replyContext(key));
document.addEventListener(
  "click",
  (event) => {
    if (pressIsKeyboardActivation(event)) return;
    const within2 = replyDraftContext(event.composedPath()[0]);
    for (const context of compositions.keys())
      if (context !== within2) dismissContext(context);
  },
  true
);
var dismissReplyAt = (node) => {
  const context = replyDraftContext(node);
  if (context !== null) dismissContext(context);
};
function handOver(target, owner) {
  const redrawGiver = owner.binding?.give();
  target.binding.take(owner);
  redrawGiver?.();
  const session = compositions.get(owner.context);
  if (session) session.owner = owner;
  return owner;
}
function carry(target, owner) {
  if (target === owner || owner.retired || !target.binding || owner.binding && owner.row.checkVisibility())
    return target;
  const session = compositions.get(owner.context);
  if (session && session.owner !== owner && session.owner !== target) return target;
  return handOver(target, owner);
}
var park = null;
function parkRow(row) {
  if (!park) {
    park = el("div", "lf-reply-park");
    park.hidden = true;
  }
  if (!park.isConnected) move(chromeRoot, park, chromeForeground);
  move(park, row, null);
}
function releaseReplies(surface) {
  for (const { owner } of compositions.values()) {
    if (!owner?.binding || !surface.contains(owner.row)) continue;
    const shown = [...views2.get(owner.context)].find(
      (view) => view !== owner && view.controls.input.checkVisibility()
    );
    if (shown) handOver(shown, owner);
    else {
      const redrawGiver = owner.binding.give();
      parkRow(owner.row);
      redrawGiver();
    }
  }
}
function replyControlDestination(node) {
  const composition = compositionOf(node);
  if (!composition) return null;
  const part = Object.keys(composition.controls).find(
    (name) => composition.controls[name] === node
  );
  if (!part) return null;
  return (thread) => {
    const target = compositionOf(thread?.querySelector(SAY_ROW));
    return target ? carry(target, composition).controls[part] : null;
  };
}
function sendReply(draftCtx, key, text, owns, actions) {
  let flight = null;
  const sent = sendMessage(
    draftCtx,
    owns,
    (attempt) => flight = actions.reply(key, text, { attempt })
  );
  return sent && { flight };
}
function wireReply(key, row, input, send, wireInput, { hint, accessibleName, busy }) {
  row.classList.add("lf-comment-box");
  const draftCtx = replyContext(key);
  const composition = {
    context: draftCtx,
    key,
    row,
    controls: { input, send },
    binding: null,
    changed: () => composition.binding?.onChange()
  };
  row[REPLY_COMPOSITION] = composition;
  input.value = loadDraft(draftCtx) ?? "";
  const sync = wireInput(input, {
    hint,
    accessibleName,
    busy,
    sends: "send",
    sendBtn: send,
    // localStorage notifies other tabs but skips this document. Page, margin, and panel
    // reply boxes are views of one draft here, so they take the same bus directly.
    // Other draft kinds still have one view per document.
    save: (v) => {
      saveDraft(draftCtx, v);
      tellDraft(draftCtx, v);
      remember(composition);
    },
    // The new turn is drawn above the box; the landing shows it with the box the user
    // sent from, read before the send draws, around wherever the send left them
    // standing. A view whose box stays for the next turn lands the send itself (`sent`),
    // told whether the log takes it.
    send: (_text, raw, owns) => {
      const { actions, landSent, sent } = composition.binding;
      const land2 = sendLanding(input);
      const reply = sendReply(draftCtx, key, raw, owns, actions);
      if (!reply) return;
      if (sent) return sent(reply.flight);
      landSent(closestAcross(input, THREAD));
      land2(focused());
    },
    // ↑ from an empty box reaches back to the user's own last words in the thread, to
    // rewrite them where they stand (`message-edit.js`). A box holding words keeps the
    // key for its caret.
    rows: [
      {
        id: "message.edit.last",
        keys: ["ArrowUp"],
        description: "Edit my last message in the thread",
        title: "edit last message",
        when: () => !sync.value() && Boolean(composition.binding?.editLast?.available()),
        run: () => composition.binding?.editLast?.open()
      }
    ]
  });
  composition.sync = sync;
  sync();
  return composition;
}
function attach(composition, binding) {
  const { context, row, controls: controls2, sync } = composition;
  composition.binding = binding;
  let instances = views2.get(context);
  if (!instances) views2.set(context, instances = /* @__PURE__ */ new Set());
  instances.add(composition);
  const begin = () => {
    adopt(context, composition);
    composition.changed();
  };
  sync.load(loadDraft(context) ?? "");
  const stopMirror = mirrorDraft(controls2.input, sync, context, {
    retained: true,
    mirrored: true,
    onChange: (value) => {
      if (value === null && !draftHasContent(context)) dismissContext(context);
      remember(composition);
      composition.changed();
    }
  });
  row.addEventListener("focusin", begin);
  return ({ handingOn = false } = {}) => {
    if (!handingOn) sync.cancelDictation();
    stopMirror();
    row.removeEventListener("focusin", begin);
    instances.delete(composition);
    if (!instances.size) views2.delete(context);
    composition.binding = null;
  };
}
var replyCompositionHasDraft = (node) => {
  const ctx = replyDraftContext(node);
  return ctx ? loadDraft(ctx) !== null : null;
};
var replyIsEditing = (key) => compositions.has(replyContext(key));
var writingIn = (field, sending2) => Boolean(
  field?.checkVisibility() && (standingIn(field.closest(".lf-thread-reply")) || field.value !== "" || sending2)
);
var replyAvailable = (thread) => !thread.resolved || replyIsEditing(threadKey(thread));
async function restoreReplyEditing(editing, land2) {
  if (!editing?.mirrored || !draftEditingStands(editing)) return null;
  const context = editing.context;
  let session = compositions.get(context);
  if (!session) compositions.set(context, session = { owner: null });
  try {
    return await land2();
  } finally {
    if (compositions.get(context) === session && !available(session.owner))
      compositions.delete(context);
  }
}
function createReplyView(key, commands2, redraw, {
  onChange = () => {
  },
  editLast = null,
  hint = "Reply",
  accessibleName = "Reply",
  busy = () => false,
  sent = null
} = {}) {
  const fresh = () => {
    const row = offer("div", "lf-thread-reply");
    const input = offer(TEXT_FIELD);
    input.name = "reply";
    const send = offer("button", "lf-btn lf-thread-send", "Send");
    row.append(input, send);
    return wireReply(key, row, input, send, commands2.wireInput, {
      hint,
      accessibleName,
      busy
    });
  };
  let composition = fresh();
  const binding = { ...commands2, onChange, editLast, sent };
  let detach = attach(composition, binding);
  binding.give = () => {
    detach({ handingOn: true });
    composition = fresh();
    detach = attach(composition, binding);
    return redraw;
  };
  binding.take = (owner) => {
    if (standingIn(composition.row)) focused().blur();
    detach();
    composition.retired = true;
    composition = owner;
    detach = attach(composition, binding);
    redraw();
  };
  return {
    get node() {
      return composition.row;
    },
    get input() {
      return composition.controls.input;
    },
    cancelDictation: () => composition.sync.cancelDictation(),
    // A view drawing the thread takes its session's row where no view holds it: one
    // released to the park, or one whose view went. It does so once it stands in the
    // document, `shown`, so the move keeps the user in the row (dom-move.js).
    claim(shown) {
      const owner = compositions.get(composition.context)?.owner;
      if (owner && owner !== composition && !owner.binding && !owner.retired && shown())
        binding.take(owner);
    },
    dispose: () => detach()
  };
}

// runtime/thread/focus.js
function focusThread(thread, cause) {
  focusDestination(thread, cause);
}
var declaredParts = /* @__PURE__ */ new WeakMap();
var declareThreadParts = (thread, parts) => declaredParts.set(thread, parts);
var ownParts = {
  reply: (thread) => thread.querySelector(SAY_BOX),
  settlement: (thread) => [...thread.querySelectorAll(".lf-resolve, .lf-reopen")].find(
    (control) => control.closest(THREAD) === thread
  ) ?? null
};
function* drawingsOf(thread) {
  const id = drawnThreadId(thread);
  for (let at = thread; at === thread || at && id && drawnThreadId(at) === id; at = closestAcross(upFrom(at), THREAD))
    yield at;
}
function wholeThread(thread) {
  const outer = [...drawingsOf(thread)].at(-1);
  return declaredParts.get(outer)?.whole(outer) ?? outer;
}
function threadPart(thread, name) {
  for (const at of drawingsOf(thread)) {
    const part = (declaredParts.get(at) ?? ownParts)[name](at);
    if (part) return part;
  }
  return null;
}
var threadReplyInput = (thread) => {
  const input = thread && threadPart(thread, "reply");
  return input && shownBox(input).height ? input : null;
};
function threadFocusDestination(thread, { part = "reply" } = {}) {
  return (part === "thread" ? thread : null) ?? threadReplyInput(thread) ?? thread;
}
function focusedThreadTarget() {
  const active = focused();
  return active?.matches?.(THREAD) ? active : null;
}
var heldThread = () => closestAcross(focused(), THREAD);
var heldThreadId = () => drawnThreadId(heldThread());
var pressed = null;
var release = 0;
function releasePress() {
  if (!pressed || release) return;
  release = nextRender(() => {
    release = 0;
    pressed = null;
    repaint();
  });
}
onPress((start) => {
  if (start.button !== 0) return null;
  pressed = heldThreadId();
  return releasePress;
});
var standingThreadId = () => heldThreadId() ?? pressed;
var mayReplyTo = (id, intent) => restrictUserIntent(intent, () => {
  const thread = allThreads().find((candidate) => candidate.id === id);
  return Boolean(thread && replyAvailable(thread));
});
async function replyDestination(id, open2, intent, { destination = (thread) => threadPart(thread, "reply"), scroll = true } = {}) {
  const mayReply = mayReplyTo(id, intent);
  if (!mayReply()) return null;
  const shown = await open2(id, { part: "reply", scroll, intent: mayReply });
  const thread = shown instanceof Element ? closestAcross(shown, THREAD) : null;
  if (!thread || focused() !== shown || !mayReply()) return null;
  const control = destination(thread);
  if (!control) return null;
  if (control !== focused()) mayReply.handoff(() => focusDestination(control, "move"));
  return focused() === control && mayReply() ? control : null;
}
async function threadDestination(id, open2, may) {
  const at = focused();
  if (at && at !== document.body && drawn(at)) return null;
  const shown = await open2(id, { part: "thread", intent: may });
  return shown instanceof Element && focused() === shown && may() ? shown : null;
}
var carried = /* @__PURE__ */ new WeakSet();
var carrying = null;
var carryingThreadPlace = (node) => Boolean(node) && carrying?.node === node && (carrying.reply ? carrying.may() : carrying.intent() && allThreads().some((thread) => thread.id === carrying.id && !thread.resolved));
function holdThreadPlace(open2, { threadAt, seated }) {
  carrying = null;
  const held = holdStanding();
  const node = held?.node;
  if (!node || carried.has(node)) return null;
  const destination = replyControlDestination(node);
  const key = destination && replyThreadKey(node);
  const thread = !destination && closestAcross(node, ".lf-page-thread");
  const id = key ? allThreads().find((each) => threadKey(each) === key)?.id : thread ? drawnThreadId(thread) : threadAt(node);
  if (!id) return null;
  const intent = retainUserIntent({ source: node });
  const may = destination ? mayReplyTo(id, intent) : restrictUserIntent(
    intent,
    () => allThreads().some((each) => each.id === id && !each.resolved) && seated(id)
  );
  const carry2 = { node, id, intent, may, reply: Boolean(destination) };
  carrying = carry2;
  return async () => {
    try {
      return await held.restore(async () => {
        carried.add(node);
        const control = destination ? await replyDestination(id, open2, intent, { destination }) : await threadDestination(id, open2, may);
        if (control === node) carried.delete(node);
        return control;
      });
    } finally {
      if (carrying === carry2) carrying = null;
    }
  };
}

// runtime/reading-continuity.js
var generation = 0;
var interrupted = document.visibilityState === "hidden";
var readingIsContinuous = () => document.visibilityState !== "hidden" && !interrupted;
var readingReturn = () => interrupted ? generation : null;
var CONTINUITY = "lf-reading-continuity";
var changed = () => document.dispatchEvent(
  new CustomEvent(CONTINUITY, { detail: { continuous: readingIsContinuous() } })
);
function onReadingInterrupted(interrupted2) {
  const listener = () => {
    if (!readingIsContinuous()) interrupted2();
  };
  document.addEventListener(CONTINUITY, listener);
  return () => document.removeEventListener(CONTINUITY, listener);
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    generation += 1;
    interrupted = true;
  }
  changed();
});
function completeReadingReturn(returned) {
  if (returned === null || returned !== generation || document.visibilityState === "hidden" || !interrupted)
    return;
  interrupted = false;
  changed();
}

// runtime/thread/held-news.js
var gesturedOn = (thread) => threadState().gestured.includes(thread.id);
var gestured = (key) => {
  const thread = allThreads().find((each) => threadKey(each) === key);
  return Boolean(thread) && gesturedOn(thread);
};
var tokens2 = (reactions) => new Set(reactions.choices.filter(({ inForce }) => inForce).map(({ name }) => name));
var symmetric = (a, b) => [...a, ...b].filter((name) => !a.has(name) || !b.has(name));
var fold = (summary, drawn3) => JSON.stringify([
  summary.id,
  summary.covers.filter((id) => drawn3.has(id)),
  Boolean(summary.protected?.length)
]);
var rewritten = (message) => message.base === message.id ? null : message.base;
function messageChange(prior, message) {
  if (!prior) return "joined";
  const reworded = JSON.stringify(prior.body) !== JSON.stringify(message.body);
  if (prior.provisional)
    return reworded ? "joined" : message.provisional ? null : "completed";
  if (!reworded) return null;
  return rewritten(prior) === rewritten(message) ? "grew" : "rewritten";
}
function difference(was, now, { progressOpen = false } = {}) {
  const drawn3 = new Map(was.messages.map((message) => [message.key, message]));
  const settled = Boolean(was.resolved) === Boolean(now.resolved) ? null : now.resolved ? "Resolved" : "Reopened";
  const news = {
    settled,
    working: was.working?.words === now.working?.words ? null : now.working?.live ? "Work in progress" : "Work changed",
    progress: 0,
    replies: 0,
    messages: 0,
    edits: 0,
    reactions: 0,
    appended: false
  };
  const changed2 = /* @__PURE__ */ new Set();
  const arrived = /* @__PURE__ */ new Set();
  const completed = /* @__PURE__ */ new Set();
  for (const message of now.messages) {
    const prior = drawn3.get(message.key);
    const change = messageChange(prior, message);
    if (!prior || prior.provisional) arrived.add(message.id);
    if (change === "completed") completed.add(message.id);
    if (change === "joined" && message.progress && !progressOpen && !now.resolved) {
      news.progress += 1;
      continue;
    }
    if (change === "joined") {
      if (message.author === "agent") news.replies += 1;
      else news.messages += 1;
      news.appended = true;
    } else if (change === "grew" || change === "rewritten") {
      news[change === "grew" ? "replies" : "edits"] += 1;
      changed2.add(message.key);
    } else if (settled) changed2.add(message.key);
    else if (message.reactions && prior.reactions) {
      const turned = symmetric(tokens2(prior.reactions), tokens2(message.reactions));
      news.reactions += turned.length;
      if (turned.length) changed2.add(message.key);
    }
  }
  const summaries = (reading) => {
    const ids = new Set(reading.messages.map(({ id }) => id));
    return new Map(reading.summaries.map((summary) => [fold(summary, ids), summary]));
  };
  const before = summaries(was);
  const after = summaries(now);
  const added = [...after].filter(([at]) => !before.has(at)).map(([, each]) => each);
  const gone = [...before].filter(([at]) => !after.has(at)).map(([, each]) => each);
  const told = (list) => list.filter(({ trigger }) => !arrived.has(trigger)).length;
  news.summaries = told(added) || told(gone);
  const folding = new Set([...added, ...gone].map(({ trigger }) => trigger));
  for (const id of completed)
    if (folding.has(id)) {
      news.replies += 1;
      news.appended = true;
    }
  const keys2 = new Map(
    [...was.messages, ...now.messages].map(({ id, key }) => [id, key])
  );
  const arrivals = new Set(
    now.messages.filter(({ id }) => arrived.has(id)).map(({ key }) => key)
  );
  const tail = was.messages.map(({ key }) => key).filter((key) => !arrivals.has(key));
  const covered2 = new Set(
    added.flatMap(({ covers }) => covers.map((id) => keys2.get(id))).filter(Boolean)
  );
  const footFold = covered2.size > 0 && !gone.length && added.every(({ trigger }) => arrived.has(trigger)) && tail.slice(-covered2.size).every((key) => covered2.has(key));
  const folds = {
    messages: [...added, ...gone].flatMap(
      ({ covers }) => covers.map((id) => keys2.get(id)).filter(Boolean)
    ),
    summaries: gone.map(({ id }) => id)
  };
  const counts = [
    "working",
    "progress",
    "replies",
    "messages",
    "edits",
    "reactions",
    "summaries"
  ];
  if (!settled && counts.every((count) => !news[count])) return null;
  const appendedAtEnd = news.appended && was.messages.every((message, index) => now.messages[index]?.key === message.key);
  const turn = was.messages.findLastIndex(
    (message) => message.author === "user" && !message.progress
  );
  const asked = new Set(was.messages.slice(0, turn + 1).map(({ key }) => key));
  const answers = turn >= 0 && was.messages.slice(turn + 1).every((message) => message.progress || message.provisional) && !settled && !news.messages && !news.edits && !news.reactions && !news.summaries && !folds.summaries.length && (!news.appended || appendedAtEnd) && ![...changed2, ...folds.messages].some((key) => asked.has(key));
  return { news, changed: changed2, folds, appendedAtEnd, footFold, answers };
}
function withheld(was, now) {
  const current = new Map(now.msgs.map((message) => [messageKey(message), message]));
  const msgs = was.msgs.flatMap((prior) => {
    const message = current.get(messageKey(prior));
    if (!message) return isReaction(prior) || prior.provisional ? [prior] : [];
    const { text, body, edited, content_version, provisional, reactions } = prior;
    return [
      Object.freeze({
        ...message,
        text,
        body,
        edited,
        content_version,
        provisional,
        reactions
      })
    ];
  });
  return Object.freeze({
    ...now,
    root: msgs.find((message) => messageKey(message) === messageKey(now.root)) ?? now.root,
    resolved: was.resolved,
    msgs: Object.freeze(msgs),
    summaries: was.summaries
  });
}
var counted = (count, one, many) => count && `${count} ${count === 1 ? one : many}`;
var newsParts = ({
  settled,
  working,
  progress = 0,
  replies = 0,
  messages = 0,
  edits,
  reactions,
  summaries,
  threads
}) => [
  settled,
  ![settled, progress, replies, messages, edits, reactions, summaries, threads].some(
    Boolean
  ) && working,
  counted(replies, "new reply", "new replies"),
  // A progress message is no reply, so it counts with the user's messages from
  // elsewhere; a reply arriving after it folds it, and says it.
  counted(messages + (replies ? 0 : progress), "new message", "new messages"),
  counted(edits, "message edited", "messages edited"),
  counted(reactions, "reaction changed", "reactions changed"),
  counted(summaries, "summary changed", "summaries changed"),
  counted(threads, "new thread", "new threads")
].filter(Boolean);
var said = (news) => {
  const parts = newsParts(news).map((part, index) => index ? ` \xB7 ${part}` : part);
  return { parts, label: parts.join("") };
};
function newsNotice(header = false) {
  const node = offer(
    "button",
    header ? "lf-thread-notice lf-thread-notice-news lf-thread-header-action lf-thread-news" : "lf-thread-notice lf-thread-notice-news lf-thread-news"
  );
  const words = document.createElement("span");
  node.append(words);
  let open2 = () => null;
  const show = () => {
    const standing2 = focused() === node;
    const landing = open2();
    if (standing2 && landing) focusThread(landing, "move");
  };
  keys(node, "On news waiting in a thread", [
    {
      id: "thread.news",
      keys: PRESS,
      description: "Show what is waiting",
      title: "show it",
      control: node,
      run: show
    }
  ]);
  return {
    node,
    set(news) {
      if (words.textContent !== news.label)
        words.replaceChildren(
          ...news.parts.map((part) => {
            const fact = document.createElement("span");
            fact.textContent = part;
            return fact;
          })
        );
      keeps(node, "title", news.label);
      node.classList.toggle("lf-reopen", news.reopened);
      open2 = news.open;
    }
  };
}
function seatNotice() {
  const notice2 = newsNotice();
  const node = offer("div", "lf-seat-news");
  node.append(notice2.node);
  return {
    node,
    set(news, box) {
      notice2.set(news);
      if (box?.isConnected)
        node.style.blockSize = layoutPx(box.getBoundingClientRect().height);
    }
  };
}
var holders = /* @__PURE__ */ new Set();
var showHeld = (id) => everySeat(id, (held, thread) => held.show(thread));
var showHeldThread = (id) => everySeat(id, (held, thread) => held.showThreads(thread));
function everySeat(id, show) {
  const thread = threadIdNamed(id);
  let shown = false;
  for (const held of holders) shown = show(held, thread) || shown;
  return shown;
}
var standing = null;
onStanding((node, cause) => {
  if (cause === "drop") return;
  const thread = node && closestAcross(node, THREAD);
  const id = drawnThreadId(thread);
  const arrived = id !== null && id !== standing && (cause === "move" || cause === "step");
  standing = id;
  if (arrived) showHeld(id);
});
var HeldNews = class {
  #seat;
  #view;
  #changed;
  // The reading last drawn, the one each reading is read against: every thread the seat
  // has taken in, by key, drawn or held; the threads it draws holding news; the threads
  // whose news the user asked to see, which the next reading draws as they stand; the
  // threads not drawn; and each thread's key by its id.
  #shown = null;
  #known = /* @__PURE__ */ new Set();
  #holds = /* @__PURE__ */ new Set();
  #released = /* @__PURE__ */ new Map();
  #threads = /* @__PURE__ */ new Set();
  #keys = /* @__PURE__ */ new Map();
  #stopWatching = null;
  // `view(key)` is the seat's ThreadView for a thread; `changed()` draws the seat again
  // from the reading it holds.
  constructor(seat, view, changed2) {
    this.#seat = seat;
    this.#view = view;
    this.#changed = () => {
      if (seat.isConnected) changed2();
    };
    holders.add(this);
  }
  // The reading to draw from `reading`, the seat's whole reading of its threads. The first
  // reading drawn from the read log is what the seat shows on arrival, so none of it is
  // news; one drawn before the log is read, or while the server is away, is no baseline
  // either. `row` says whether the seat draws a first-message row the user is not in, in
  // whose place a new thread's notice can stand.
  hold(reading, { row }) {
    const candidate = this.prepare(reading, { row });
    candidate.commit();
    return candidate.reading;
  }
  // Required presenters prepare before yielding to package layout. Only the
  // candidate actually painted becomes the baseline for the next comparison.
  prepare(reading, { row }) {
    const read = runtime.statePhase === "ready";
    if (!read || !readingIsContinuous()) this.#forget();
    const prior = read ? this.#shown : null;
    const keys2 = new Set(reading.threads.map(({ key }) => key));
    for (const key of this.#threads) if (!keys2.has(key)) this.#threads.delete(key);
    this.#keys = new Map(reading.threads.map(({ id, key }) => [id, key]));
    if (prior) this.#arrive(prior, reading, row);
    const shown = this.#draw(prior, reading);
    const released = new Map(this.#released);
    if (this.#holding())
      this.#stopWatching ??= whenNone([this.#seat], growthIsSeen, this.#all);
    else this.#stop();
    return {
      reading: shown,
      commit: () => {
        for (const [key, token] of released)
          if (this.#released.get(key) === token) this.#released.delete(key);
        this.#known = keys2;
        this.#shown = read ? shown : null;
      }
    };
  }
  // Which of the threads new to the seat it holds back.
  #arrive(prior, reading, row) {
    const arrived = reading.threads.filter(({ key }) => !this.#known.has(key));
    if (arrived.some(({ key }) => gestured(key))) this.#threads.clear();
    else if (arrived.length) {
      const last = prior.threads.at(-1)?.key;
      const after = last ? this.#view(last)?.node : this.#seat;
      const seen = readingIsContinuous() && Boolean(after) && growthAfterIsSeen(after);
      if (seen && (last || row)) for (const { key } of arrived) this.#threads.add(key);
      else this.#threads.clear();
    }
  }
  // Each thread as it stands, except one whose news would move what the reader reads,
  // which stands as it was drawn, its notice saying what waits.
  #draw(prior, reading) {
    this.#holds.clear();
    const drawn3 = new Map(prior?.threads.map((thread) => [thread.key, thread]));
    const threads = reading.threads.filter(({ key }) => !this.#threads.has(key)).map((thread) => {
      const was = drawn3.get(thread.key);
      const shown = thread.visible !== false && !thread.folding;
      const held = was && shown && !this.#released.has(thread.key) ? difference(was, thread, {
        progressOpen: this.#view(thread.key)?.progressOpen ?? false
      }) : null;
      if (!held || gestured(thread.key) || !this.#view(thread.key)?.newsMoves(held))
        return { ...thread, news: null };
      this.#holds.add(thread.key);
      const { news: news2 } = held;
      return {
        ...thread.reread(withheld(was.source, thread.source)),
        // Workflows and to-dos update in place, but the working message itself
        // keeps its drawn presence while its arrival or departure is held.
        working: news2.working ? was.working : thread.working,
        ...news2.settled === "Reopened" && { settlement: null },
        news: news2
      };
    });
    const waiting = this.#threads.size;
    const host = threads.at(-1);
    if (waiting && host) host.news = { ...host.news, threads: waiting };
    for (const thread of threads) {
      if (thread.news)
        thread.news = {
          ...said(thread.news),
          reopened: thread.news.settled === "Reopened",
          open: () => {
            const node = this.#view(thread.key)?.node ?? null;
            showHeld(thread.id);
            if (thread === host && waiting) this.#open(thread.key, true);
            return node;
          }
        };
    }
    const news = waiting && !host ? {
      ...said({ threads: waiting }),
      reopened: false,
      open: () => this.#open(null, true)
    } : null;
    return Object.freeze({ ...reading, threads: Object.freeze(threads), news });
  }
  // Shows what the seat holds of the thread `id`: its news, or, where the seat holds the
  // thread itself, every thread it holds, as the notice saying them would.
  show(id) {
    const key = this.#keys.get(id);
    const thread = this.#threads.has(key);
    if (!this.#holds.has(key) && !thread) return false;
    this.#open(key, thread);
    return true;
  }
  // Shows the new threads the seat holds, where it holds the thread `id` among them.
  showThreads(id) {
    if (!this.#threads.has(this.#keys.get(id))) return false;
    this.#open(null, true);
    return true;
  }
  // Shows what one notice holds: a thread's news, and the seat's new threads where that
  // notice also says them. Returns the thread a keyboard on the notice lands on.
  #open(key, threads) {
    const first = threads && [...this.#threads][0];
    let changed2 = false;
    if (key && this.#holds.has(key) && !this.#released.has(key)) {
      this.#released.set(key, /* @__PURE__ */ Symbol("release"));
      changed2 = !gestured(key);
    }
    if (threads && this.#threads.size) {
      this.#threads.clear();
      changed2 = true;
    }
    if (changed2) this.#changed();
    return this.#view(key ?? first)?.node ?? null;
  }
  // The next reading draws every thread as it stands, as when the user changes what
  // the surface shows, which moves its threads anyway.
  release() {
    this.#forget();
  }
  #all = () => {
    if (!this.#holding()) return;
    this.#forget();
    this.#changed();
  };
  // Every thread the seat holds shows on the next reading.
  #forget() {
    for (const thread of this.#shown?.threads ?? [])
      this.#released.set(thread.key, /* @__PURE__ */ Symbol("release"));
    this.#threads.clear();
  }
  #holding() {
    return Boolean(this.#threads.size || this.#holds.size);
  }
  // Whether the seat holds no news and owes no release, so a reading it has drawn would
  // draw the same again.
  get settled() {
    return !this.#holding() && !this.#released.size;
  }
  #stop() {
    this.#stopWatching?.();
    this.#stopWatching = null;
  }
  dispose() {
    this.#stop();
    holders.delete(this);
  }
};
var HeldReading = class {
  #region;
  #changed;
  #shown = null;
  #released = false;
  #watch = null;
  constructor(owner, region, changed2) {
    this.#region = region;
    this.#changed = changed2;
    watchOwner(owner, {
      connect: () => {
        if (this.#watch && !this.#watch.stop)
          this.#watch.stop = whenNone(this.#watch.nodes, growthIsSeen, this.show);
      },
      disconnect: () => {
        this.#watch?.stop?.();
        if (this.#watch) this.#watch.stop = null;
      }
    });
  }
  hold(reading) {
    if (runtime.statePhase !== "ready") {
      this.#shown = null;
      this.#stop();
      return reading;
    }
    const nodes = this.#region();
    if (this.#released || this.#shown === null || this.#shown === reading || !readingIsContinuous() || !nodes.some((node) => growthIsSeen(node))) {
      this.#released = false;
      this.#shown = reading;
      this.#stop();
    } else if (!this.#watch || this.#watch.nodes.length !== nodes.length || this.#watch.nodes.some((node, at) => node !== nodes[at])) {
      this.#stop();
      this.#watch = { nodes, stop: whenNone(nodes, growthIsSeen, this.show) };
    }
    return this.#shown;
  }
  // The next reading draws whatever it moves: the user asked, or nobody can see.
  // `release` leaves the drawing to the caller, which may release several readings
  // for one paint; `show` draws now.
  release() {
    this.#released = true;
  }
  show = () => {
    this.release();
    this.#changed();
  };
  #stop() {
    this.#watch?.stop?.();
    this.#watch = null;
  }
};
function heldGrowth(node, change) {
  if (!pagePresented() || !readingIsContinuous() || !growthIsSeen(node)) {
    change();
    return () => {
    };
  }
  let waiting = true;
  const stop = () => {
    if (!waiting) return;
    waiting = false;
    unwatch();
    uninterrupt();
  };
  const show = () => {
    stop();
    change();
  };
  const unwatch = whenNone([node], growthIsSeen, show);
  const uninterrupt = onReadingInterrupted(show);
  return stop;
}
var HeldArrivals = class {
  #changed;
  // The keys of the page's threads at the last reading, or null before a reading drawn
  // from the read log, which is what the page shows on arrival and so no baseline for
  // news; each held thread's id and datum, by key; and the watch on each holding datum's
  // node. A thread the widget is first handed because the user opened its datum, as a
  // collapsed file, is no news.
  #known = null;
  #held = /* @__PURE__ */ new Map();
  #watching = /* @__PURE__ */ new Map();
  // `changed()` hands the widget its threads again.
  constructor(changed2) {
    this.#changed = changed2;
  }
  // The keys to keep out of what the widget places. `threads` holds each thread record
  // the widget has an exact target for, with the `datum` it stands at and that datum's
  // `node`; `drawn` holds the datums where the widget drew a thread last, and `all` is
  // every thread record on the page.
  hold(threads, { drawn: drawn3, all }) {
    const read = runtime.statePhase === "ready";
    if (!read) this.#held.clear();
    else if (this.#known) this.#take(threads, drawn3);
    this.#known = read ? new Set(all.map(({ key }) => key)) : null;
    this.#watch(threads);
    return new Set(this.#held.keys());
  }
  #take(threads, drawn3) {
    if (!readingIsContinuous()) {
      this.#lapse(() => true);
      return;
    }
    const keys2 = new Set(threads.map(({ thread }) => thread.key));
    this.#release(({ key }) => !keys2.has(key));
    for (const { thread, datum } of threads) {
      const held = this.#held.get(thread.key);
      if (!held) continue;
      held.datum = datum;
      if (gesturedOn(thread)) this.#held.delete(thread.key);
      else if (drawn3.has(datum)) this.#lapse((each) => each === held);
    }
    const arrived = threads.filter(({ thread }) => !this.#known.has(thread.key));
    const started = new Set(
      arrived.filter(({ thread }) => gesturedOn(thread)).map(({ datum }) => datum)
    );
    for (const { thread, datum, node } of arrived) {
      if (started.has(datum)) this.#release((held) => held.datum === datum);
      else if (drawn3.has(datum) || !growthAfterIsSeen(node))
        this.#lapse((held) => held.datum === datum);
      else this.#held.set(thread.key, { key: thread.key, id: thread.id, datum });
    }
  }
  // Releases what `which` picks for a reason other than a gesture of the user's. A
  // thread the user stands in (`standingNodes`), by focus or by a selection of its
  // words, in the margin's card, stays there with them, since its
  // release would take the card, and the reply they may be writing, away; it shows
  // when they press its marker, or the next time its datum's growth goes unseen.
  #lapse(which) {
    const standing2 = new Set(
      standingNodes().map((node) => closestAcross(node, THREAD)?.dataset.thread)
    );
    return this.#release((held) => which(held) && !standing2.has(held.id));
  }
  // One watch for each datum holding a thread, on the node it stands at now.
  #watch(threads) {
    const nodes = new Map(threads.map(({ datum, node }) => [datum, node]));
    const holding = new Set([...this.#held.values()].map(({ datum }) => datum));
    for (const [datum, watch] of this.#watching)
      if (!holding.has(datum) || watch.node !== nodes.get(datum)) {
        watch.stop();
        this.#watching.delete(datum);
      }
    for (const datum of holding) {
      if (this.#watching.has(datum)) continue;
      const node = nodes.get(datum);
      const leave = () => {
        if (this.#lapse((held) => held.datum === datum)) this.#changed();
      };
      this.#watching.set(datum, { node, stop: whenNone([node], growthIsSeen, leave) });
    }
  }
  holds(id) {
    return [...this.#held.values()].some((held) => held.id === id);
  }
  // Shows the held threads `ids` names, and returns the ones it held, in `ids`' order.
  show(ids) {
    return ids.filter((id) => this.#release((held) => held.id === id));
  }
  #release(which) {
    const released = [...this.#held.values()].filter(which);
    for (const { key } of released) this.#held.delete(key);
    return released.length > 0;
  }
  dispose() {
    for (const watch of this.#watching.values()) watch.stop();
    this.#watching.clear();
  }
};

// runtime/thread/folding.js
var pendingSettlement = (entries, id) => pendingForParent(entries, id, ["resolve", "unresolve"]);
async function settleThread({
  parent,
  key,
  resolved: resolved2,
  prepareLanding,
  pendingEntries,
  actions,
  retainGesture
}) {
  if (pendingSettlement(pendingEntries(), parent())) return;
  const landing = prepareLanding?.();
  const attempt = randomId();
  const answer = resolved2 ? actions.reopen(key, { attempt }) : actions.resolve(key, { attempt });
  if (!answer) return;
  notice(resolved2 ? "Reopened the thread" : "Resolved the thread");
  if (landing) retainGesture(attempt, { reverse: landing.reverse });
  await landGesture({
    landing,
    answer,
    pending: () => Boolean(pendingSettlement(pendingEntries(), parent()))
  });
}
async function landGesture({ landing, answer, pending }) {
  const land2 = async (step) => {
    try {
      return Boolean(await step?.());
    } catch {
      return false;
    }
  };
  const startLanding = bindQueuedWork(
    () => pending() ? land2(landing?.optimistic) : false
  );
  const finishLanding = bindQueuedWork((accepted, landed) => {
    if (!accepted) return land2(landing?.reverse);
    if (!landed) return land2(landing?.optimistic);
  });
  const presentation = whenDocumentPresented();
  paintKeys();
  try {
    await presentation;
    const landed = await startLanding();
    const accepted = await answer;
    await finishLanding(accepted, landed);
  } finally {
    paintKeys();
  }
}

// runtime/thread/reply-continuity.js
var ReplyContinuity = class {
  #owner;
  #row = null;
  #departure = null;
  #space = 0;
  // Growth already deducted from passive space while a refused draft returns.
  #returningWriting = 0;
  // The writing areas a presentation changes, each with its height before it.
  #presenting = [];
  #writing = null;
  #sizes = sizeObserver((entries) => {
    const writing = this.#writing;
    if (!writing || !entries.some(
      ({ target, borderBoxSize }) => target === writing.input && atLayoutPrecision(borderBoxSize[0].inlineSize) !== writing.width
    ))
      return;
    if (!this.#visible()) return this.#releaseSpace();
    writing.width = atLayoutPrecision(
      parseFloat(getComputedStyle(writing.input).inlineSize)
    );
    this.#allocateWriting(writing.input, layoutPx(writing.input.naturalBlockSize));
  });
  gap = document.createElement("div");
  constructor(owner) {
    this.#owner = owner;
    owner.classList.add("lf-reply-continuity");
    this.gap.className = "lf-reply-space";
    this.gap.setAttribute("aria-hidden", "true");
    owner.addEventListener("toggle", () => {
      if (!this.#visible()) this.release();
    });
    owner.addEventListener(
      "input",
      (event) => {
        if (!this.#row?.contains(event.target)) return;
        const input = this.#row.querySelector(TEXT_FIELD);
        if (input.value) this.#allocateWriting(input, layoutPx(input.naturalBlockSize));
        else this.#releaseWriting();
      },
      { capture: true }
    );
  }
  #visible() {
    return this.#owner.isConnected && this.#row?.isConnected && growthIsSeen(this.#row);
  }
  // `writing` are the boxes the presentation opens, closes or changes the words of, as
  // rewrites do, whose own height changes the extent follows.
  before(writing = []) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    this.#presenting = [];
    if (!this.#visible()) return null;
    this.#presenting = writing.filter((node) => node.isConnected).map((node) => ({ node, height: node.getBoundingClientRect().height }));
    const extent = parseFloat(getComputedStyle(this.#owner).blockSize);
    const place2 = offFlowSurfaceOf(this.#owner) ? null : placeKeeper(scrollerFor(this.#owner), {
      items: ".lf-reply-continuity",
      identity: (node) => node.dataset.thread,
      preferred: () => this.#owner
    });
    return { extent, place: place2, held: place2?.take({ spans: false }) };
  }
  after(reading) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    const presenting = this.#presenting;
    this.#presenting = [];
    if (!this.#row?.isConnected) return this.release();
    if (!this.#visible()) {
      reading?.place?.finish(reading.held);
      return this.#releaseSpace();
    }
    this.#retainWriting();
    if (reading != null) {
      const { extent, place: place2, held } = reading;
      const body = getComputedStyle(this.#owner);
      const written = presenting.filter(({ node }) => node.isConnected).reduce(
        (sum, { node, height }) => sum + node.getBoundingClientRect().height - height,
        0
      );
      const input = this.#row.querySelector(TEXT_FIELD);
      const context = input && replyDraftContext(input);
      const returning = this.#writing?.input === input && context && draftHasContent(context) && !this.#owner.querySelector(".lf-msg.user[data-attempt]") ? Math.max(
        0,
        parseFloat(this.#writing.room) - input.getBoundingClientRect().height
      ) : 0;
      this.#keep(
        Math.max(
          0,
          this.#space + extent - parseFloat(body.blockSize) + written + this.#returningWriting - returning
        )
      );
      this.#returningWriting = returning;
      place2?.finish(held);
    }
    if (!this.#visible()) return this.#releaseSpace();
    this.#departure?.();
    this.#departure = whenNone([this.#row], growthIsSeen, () => {
      if (!this.#owner.isConnected) this.release();
      else this.#releaseSpace();
    });
  }
  #keep(space) {
    if (space === this.#space) return;
    this.#space = space;
    const value = layoutPx(space);
    if (this.gap.style.getPropertyValue("--lf-reply-space") !== value)
      this.gap.style.setProperty("--lf-reply-space", value);
  }
  #retainWriting() {
    const input = this.#row?.querySelector(TEXT_FIELD);
    if (!input?.value) {
      const context = input && replyDraftContext(input);
      if (context && draftHasContent(context) && this.#writing?.context === context) {
        if (this.#writing.input === input) return;
        const width = atLayoutPrecision(parseFloat(getComputedStyle(input).inlineSize));
        if (width === this.#writing.width)
          return this.#allocateWriting(input, this.#writing.room);
      }
      return this.#releaseWriting();
    }
    if (this.#writing?.input === input) return;
    this.#allocateWriting(input, getComputedStyle(input).blockSize);
  }
  #allocateWriting(input, room) {
    if (this.#writing?.input !== input) {
      this.#releaseWriting();
      this.#writing = {
        input,
        context: replyDraftContext(input),
        width: atLayoutPrecision(parseFloat(getComputedStyle(input).inlineSize)),
        room: null
      };
      this.#sizes.observe(input, { box: "border-box" });
    }
    if (this.#writing.room === room) return;
    this.#writing.room = room;
    input.style.setProperty("--lf-reply-writing-room", room);
  }
  #releaseWriting() {
    if (!this.#writing) return;
    this.#returningWriting = 0;
    const { input } = this.#writing;
    input.style.removeProperty("--lf-reply-writing-room");
    this.#sizes.unobserve(input);
    this.#writing = null;
  }
  #releaseSpace() {
    this.#departure?.();
    this.#departure = null;
    this.#space = 0;
    this.#returningWriting = 0;
    if (this.gap.style.getPropertyValue("--lf-reply-space"))
      this.gap.style.removeProperty("--lf-reply-space");
  }
  release() {
    this.#releaseSpace();
    this.#releaseWriting();
  }
};

// runtime/thread/summary-ranges.js
function summaryRanges(messages, summaries = []) {
  const index = new Map(messages.map((message, at) => [message.id, at]));
  const byStart = /* @__PURE__ */ new Map();
  const covered2 = /* @__PURE__ */ new Set();
  for (const summary of summaries) {
    const visible = summary.covers.filter((id) => index.has(id));
    if (!visible.length) continue;
    byStart.set(index.get(visible[0]), summary);
    for (const id of visible) covered2.add(id);
  }
  const ranges = [];
  for (let at = 0; at < messages.length; at += 1) {
    const summary = byStart.get(at);
    if (summary) {
      ranges.push(
        Object.freeze({
          kind: "summary",
          summary,
          messages: Object.freeze(
            summary.covers.filter((id) => index.has(id)).map((id) => messages[index.get(id)])
          )
        })
      );
      at += ranges.at(-1).messages.length - 1;
    } else if (!covered2.has(messages[at].id)) {
      ranges.push(
        Object.freeze({
          kind: "message",
          message: messages[at]
        })
      );
    }
  }
  return Object.freeze(ranges);
}
function withPendingProgress(ranges) {
  const gathered = [];
  for (const range of ranges) {
    const progress = range.kind === "message" && range.message.progress;
    const run = gathered.at(-1);
    if (progress && run?.summary?.pending) {
      run.summary.covers.push(range.message.id);
      run.messages.push(range.message);
    } else if (progress)
      gathered.push({
        kind: "summary",
        summary: {
          id: `progress:${range.message.id}`,
          covers: [range.message.id],
          pending: true
        },
        messages: [range.message]
      });
    else gathered.push(range);
  }
  return Object.freeze(
    gathered.map(
      (range) => range.summary?.pending ? Object.freeze({
        ...range,
        summary: Object.freeze({
          ...range.summary,
          covers: Object.freeze(range.summary.covers)
        }),
        messages: Object.freeze(range.messages)
      }) : range
    )
  );
}
function workingPlace(ranges, after) {
  const at = ranges.findIndex(
    (range) => range.kind === "message" ? range.message.key === after : range.messages.some((message) => message.key === after)
  );
  if (at < 0)
    throw new Error(`The working message follows ${after}, which no range holds`);
  return at;
}

// runtime/thread/transcript.js
function workingView(working, controls2 = nothing) {
  return html`<div class="lf-thread-working-head">
      ${working.who ? html`<b>${working.who}</b>` : nothing}
      ${working.timestamp || working.condition ? html`<span class="lf-msg-meta"
              >${working.timestamp ? html`<time datetime=${working.timestamp}>${working.age}</time>` : nothing}
              ${working.condition}</span
            >` : nothing}
      ${controls2}
    </div>
    <div class="lf-thread-working-words">${working.words}</div>`;
}
var stepOf = (message) => Object.freeze({
  who: message.by,
  timestamp: message.timestamp,
  age: message.age,
  words: message.body.plainText.trim().replace(/\.$/, ""),
  live: false,
  condition: null
});
var nextTranscriptId = 0;
var Transcript = class _Transcript {
  #commands;
  #messageCommands;
  #repaint;
  #home;
  #model = null;
  #messages = /* @__PURE__ */ new Map();
  // Each unfolded progress run's face, by the run's id, and the working message where
  // no run holds its words.
  #faces = /* @__PURE__ */ new Map();
  // The face each message stands behind as drawn, by the message's key: the last step
  // of its run, whose words the face shows.
  #facing = /* @__PURE__ */ new Map();
  #working = _Transcript.#face("working");
  #stopWorkingExposure = null;
  // Each pending progress range's covered message ids, as last drawn, so a fold that
  // takes the range over can take its disclosure state with it.
  #pendingCovers = /* @__PURE__ */ new Map();
  #pendingOpen = false;
  #checkpoints = /* @__PURE__ */ new Map();
  #expandedSummaries = /* @__PURE__ */ new Set();
  #id = ++nextTranscriptId;
  /**
   * @param {object} options
   * @param {any} options.commands The reader's commands; `read` observes the working
   *   message's words.
   * @param {any} options.messageCommands What each MessageView acts through.
   * @param {() => void} options.repaint Draws the reader around the transcript again,
   *   as a disclosure opens or closes.
   * @param {() => HTMLElement} options.home The drawing of the thread a disclosure
   *   press keeps in view.
   */
  constructor({ commands: commands2, messageCommands, repaint: repaint2, home: home2 }) {
    this.#commands = commands2;
    this.#messageCommands = messageCommands;
    this.#repaint = repaint2;
    this.#home = home2;
    this.node = document.createElement("div");
    this.node.className = "lf-thread-transcript";
    this.node.addEventListener("lf-reveal", (event) => {
      const message = event.detail?.target?.closest?.(".lf-msg[data-lf-summary]");
      const id = message?.dataset.lfSummary;
      if (!id || this.#expandedSummaries.has(id)) return;
      this.#expandedSummaries.add(id);
      this.#repaint();
    });
  }
  // Each message's view, in the thread's order: what its rewrites walk.
  get views() {
    return (this.#model?.messages ?? []).flatMap(
      ({ key }) => this.#messages.get(key) ?? []
    );
  }
  // The node a message stands in.
  messageNode(key) {
    return this.#messages.get(key)?.node ?? null;
  }
  // The checkpoint a summary stands in.
  summaryNode(id) {
    return this.#checkpoints.get(id)?.node ?? null;
  }
  // The last node the transcript shows. Progress behind its run's face and originals
  // behind a closed checkpoint stand in the transcript unrendered, so the last message
  // alone may have no box.
  get foot() {
    return [...this.node.children].findLast((node) => node.checkVisibility()) ?? null;
  }
  // Whether the progress behind the working message stood open when last drawn, opened by
  // the reader or by a search matching it, so each step that joins it shows: held news
  // counts those steps as news here (held-news.js).
  get progressOpen() {
    return this.#pendingOpen;
  }
  // Whether held news (held-news.js) would move what the reader sees of the
  // transcript: a message it changes, or the transcript's end it adds to, with growth
  // after it in sight, unless that end is `followed`, as by a reply pinned below it; or
  // a fold that comes or goes over what is in sight. The working message changes words
  // only at the run the newest step joins, the transcript's end; a run the work leaves
  // keeps its face's words where they stand.
  newsMoves({ news, changed: changed2, folds }, { followed = null } = {}) {
    return [
      ...[...changed2].flatMap((key) => [
        this.#facing.get(key),
        this.messageNode(key)
      ]),
      (news.appended || news.settled || news.working) && this.foot
    ].some((node) => node && node !== followed && growthAfterIsSeen(node)) || [
      ...folds.messages.map((key) => this.messageNode(key)),
      ...folds.summaries.map((id) => this.summaryNode(id))
    ].some((node) => node && growthIsSeen(node));
  }
  // Opens the fold holding a message, as a rewrite of it opens to be seen.
  expandAround(id) {
    const folded = this.#model?.summaries.find(({ covers }) => covers.includes(id));
    if (folded) this.#expandedSummaries.add(folded.id);
  }
  /**
   * Draws `model`, a thread's reading (thread-card.js, `threadReading`). `appends`
   * declares that it grows at its end inside the scroller holding it, as a margin
   * card's does (`data-lf-reflow`, tests/shift_watch.js). `notice` is a node the reader
   * stands at the head of the transcript's first message in sight, as a primary
   * reader's thread notice (primary-reader.js). Returns the disclosure that took over
   * the one the user stood on, where this draw replaced it, as the answer's head takes
   * progress over from the working message.
   * @returns {HTMLElement | null}
   */
  present(model, { arrived = false, appends = false, notice: notice2 = null } = {}) {
    const prior = this.#model;
    const standing2 = focused();
    const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
    if (prior && model.summaries.some(({ id }) => !priorSummaries.has(id))) {
      const heldMessage = prior.messages.find(
        ({ key }) => this.#messages.get(key)?.node.contains(standing2)
      )?.id;
      const clips = /* @__PURE__ */ new Map();
      const beingRead = new Set(
        prior.messages.filter(({ key }) => {
          const node = this.#messages.get(key)?.node;
          return node?.isConnected && seenRect(node, clips);
        }).map(({ id }) => id)
      );
      for (const summary of model.summaries) {
        if (priorSummaries.has(summary.id)) continue;
        if (summary.covers.includes(heldMessage) || summary.covers.some((id) => beingRead.has(id)))
          this.#expandedSummaries.add(summary.id);
      }
    }
    this.#model = model;
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) if (!wanted.has(key)) view.retire();
    const summarized = summaryRanges(model.messages, model.summaries);
    const describedRanges = model.resolved ? summarized : withPendingProgress(summarized);
    const summaries = new Set(
      describedRanges.flatMap((range) => range.summary ? [range.summary.id] : [])
    );
    const successors = /* @__PURE__ */ new Map();
    for (const [id, covers] of this.#pendingCovers)
      successors.set(
        id,
        describedRanges.filter(
          (range) => range.summary?.covers.some((covered2) => covers.includes(covered2))
        )
      );
    for (const id of [...this.#expandedSummaries])
      for (const range of successors.get(id) ?? [])
        this.#expandedSummaries.add(range.summary.id);
    for (const id of this.#expandedSummaries)
      if (!summaries.has(id)) this.#expandedSummaries.delete(id);
    this.#pendingCovers = new Map(
      describedRanges.filter((range) => range.summary?.pending).map((range) => [range.summary.id, range.summary.covers])
    );
    const standingToggle = this.node.querySelector(".lf-summary-expand:focus");
    const rangeState = describedRanges.map((range) => {
      if (range.kind === "message") return range;
      const forced = Boolean(range.summary.protected?.length);
      return {
        ...range,
        expanded: forced || this.#expandedSummaries.has(range.summary.id),
        forced,
        requiredText: "Messages kept open \xB7 current work"
      };
    });
    const pendingRanges = rangeState.filter((range) => range.summary?.pending);
    this.#pendingOpen = pendingRanges.some((range) => range.expanded);
    const progressByReply = /* @__PURE__ */ new Map();
    const streaming = model.messages.at(-1);
    const spoke = model.messages.findLastIndex(({ author }) => author === "user");
    const streamed = streaming?.provisional ? pendingRanges.filter(
      (range) => model.messages.indexOf(range.messages[0]) > spoke
    ) : [];
    if (streamed.length) progressByReply.set(streaming.id, streamed);
    for (const range of rangeState) {
      if (range.kind !== "summary" || !range.summary.trigger || range.forced) continue;
      const trigger = range.summary.trigger;
      if (!progressByReply.has(trigger)) progressByReply.set(trigger, []);
      progressByReply.get(trigger).push(range);
    }
    const lead = rangeState.find((range) => range.kind === "message")?.message ?? model.messages[0];
    for (const message of model.messages) {
      let view = this.#messages.get(message.key);
      if (!view)
        this.#messages.set(
          message.key,
          view = new MessageView(this.#messageCommands)
        );
      const toggle2 = progressByReply.has(message.id) ? this.#summaryToggle(progressByReply.get(message.id), true) : nothing;
      view.present(message, {
        arrived,
        headerControls: notice2 && message === lead ? html`${notice2}${toggle2}` : toggle2
      });
      keeps(
        view.node,
        "data-lf-append-tail",
        message.provisional && message === model.messages.at(-1) ? "" : null
      );
    }
    const placed2 = (key, summary) => {
      const node = this.#messages.get(key).node;
      keeps(node, "data-lf-summary", summary);
      return [node];
    };
    const checkpoints = /* @__PURE__ */ new Map();
    const faces = /* @__PURE__ */ new Map();
    const transcript = [];
    const transcriptLists = [[this.node, transcript]];
    const workingAt = model.working ? workingPlace(rangeState, model.working.after) : -1;
    let working = null;
    const facing = /* @__PURE__ */ new Map();
    const face = (node, reading, controls2) => {
      keeps(node, "data-lf-live", reading.live ? "" : null);
      render(workingView(reading, controls2), node);
      transcript.push(node);
      return node;
    };
    for (const [at, range] of rangeState.entries()) {
      if (range.kind === "message") transcript.push(...placed2(range.message.key, null));
      else {
        const id = range.summary.id;
        const checkpoint = this.#checkpoints.get(id) ?? this.#checkpoint(id);
        checkpoints.set(id, checkpoint);
        this.#paintCheckpoint(checkpoint, range);
        transcript.push(checkpoint.node);
        transcriptLists.push([
          checkpoint.originals,
          range.messages.flatMap((message) => placed2(message.key, id))
        ]);
      }
      const hosts = at === workingAt;
      if (range.summary?.pending && !streamed.includes(range)) {
        const id = range.summary.id;
        const node = this.#faces.get(id) ?? _Transcript.#face(id);
        faces.set(id, node);
        const kept = range.messages.length > 1 && model.messages.indexOf(range.messages[0]) < spoke;
        face(
          node,
          hosts ? model.working : stepOf(range.messages.at(-1)),
          kept ? this.#summaryToggle([range], true) : nothing
        );
        facing.set(range.messages.at(-1).key, node);
        if (hosts) working = node;
      } else if (hosts) working = face(this.#working, model.working);
    }
    this.#faces = faces;
    this.#facing = facing;
    for (const node of [...faces.values(), this.#working])
      keeps(node, "data-lf-append-tail", node === transcript.at(-1) ? "" : null);
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = model.working?.feedback ? this.#commands.read.observeFeedback(
      working.querySelector(".lf-thread-working-words"),
      {
        ...model.working.feedback,
        presentation_kind: "working_words",
        surface: model.surface
      }
    ) : null;
    this.#checkpoints = checkpoints;
    keeps(this.node, "data-lf-reflow", appends ? "append" : null);
    setChildLists(transcriptLists);
    if (!standingToggle || standingToggle.isConnected) return null;
    const toggleFor = (id) => this.node.querySelector(
      `.lf-summary-expand[data-summary-toggle="${CSS.escape(id)}"]`
    );
    const succeeded = standingToggle.dataset.summaryToggle;
    return [succeeded, ...(successors.get(succeeded) ?? []).map(({ summary }) => summary.id)].map(toggleFor).find(Boolean) ?? null;
  }
  // A progress run's face (`workingView`), retained while its run stands, and named
  // by it.
  static #face(id) {
    const node = document.createElement("div");
    node.className = "lf-thread-working";
    node.dataset.face = id;
    node.setAttribute("aria-live", "polite");
    return node;
  }
  // A summary's checkpoint: a retained section whose head the template draws, and
  // whose originals hold the retained messages the summary covers.
  #checkpoint(id) {
    const node = document.createElement("section");
    node.className = "lf-thread-checkpoint";
    node.dataset.summaryId = id;
    const originals = document.createElement("div");
    originals.id = `lf-summary-originals-${this.#id}-${id}`;
    originals.className = "lf-summary-originals";
    node.append(originals);
    return { node, originals };
  }
  #paintCheckpoint({ node, originals }, range) {
    const progress = Boolean(range.summary.trigger || range.summary.pending);
    keeps(node, "data-expanded", range.expanded);
    keepsHidden(node, progress && !range.expanded);
    keepsHidden(originals, !range.expanded);
    render(
      html`${progress ? nothing : html`<div class="lf-summary-checkpoint">
              <div class="lf-summary-header">
                <div class="lf-summary-label">${range.summary.label}</div>
                ${range.forced ? nothing : this.#summaryToggle([range])}
              </div>
              ${range.summary.text ? html`<div
                      class="lf-summary-text"
                      .innerHTML=${renderMarkdown(range.summary.text)}
                    ></div>` : nothing}
              ${range.forced ? html`<div class="lf-summary-required">${range.requiredText}</div>` : nothing}
            </div>`}
      ${progress && range.forced ? html`<div class="lf-summary-required">${range.requiredText}</div>` : nothing}`,
      node,
      { renderBefore: originals }
    );
  }
  #summaryToggle(ranges, progress = false) {
    const ids = ranges.map((range) => range.summary.id);
    const expanded = ranges.every((range) => range.expanded);
    const count = ranges.reduce((total, range) => total + range.messages.length, 0);
    const subject = `${count} ${progress ? "progress" : "earlier"} message${count === 1 ? "" : "s"}`;
    const label = `${expanded ? progress ? "Hide" : "Collapse" : "Show"} ${subject}`;
    return html`<button
      type="button"
      class="lf-thread-disclosure lf-summary-expand ${progress ? "lf-progress-expand" : ""}"
      data-lf-room=${progress ? `Show ${subject}` : nothing}
      data-summary-toggle=${ids[0]}
      aria-expanded=${String(expanded)}
      aria-controls=${ids.map((id) => `lf-summary-originals-${this.#id}-${id}`).join(" ")}
      @click=${() => this.#setSummaryExpanded(ids, !expanded)}
    >
      ${progress ? html`<span>${label}</span>` : label}
    </button>`;
  }
  #setSummaryExpanded(ids, expanded) {
    for (const id of ids) {
      if (expanded) this.#expandedSummaries.add(id);
      else this.#expandedSummaries.delete(id);
    }
    this.#repaint();
    const toggle2 = this.node.querySelector(
      `.lf-summary-expand[data-summary-toggle="${CSS.escape(ids[0])}"]`
    );
    if (toggle2) {
      focusDestination(toggle2, "return");
      scrollThreadIntoView(this.#home(), toggle2, "instant");
    }
  }
  commit() {
    const wanted = new Set(this.#model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) {
      if (wanted.has(key)) view.commit();
      else {
        view.retire();
        this.#messages.delete(key);
      }
    }
  }
  retire() {
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = null;
    for (const view of this.#messages.values()) view.retire();
  }
};

// runtime/thread/thread-card.js
function quoteReading(thread, anchors) {
  const placement = anchors.placedAt(thread.id);
  const rewritten2 = thread.rewritten_from;
  const quoted = rewritten2 ?? thread.detached_from ?? thread.anchor;
  const label = anchorLabel(quoted, thread.root.about);
  if (!label) return null;
  const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
  const found = !thread.detached_from && Boolean(placement);
  const outdated = anchored && placement?.status === "outdated";
  const changed2 = Boolean(rewritten2) || Boolean(quoted?.quote && placement?.datumElement && !placement.exact);
  return Object.freeze({
    label,
    words: quoted?.quote ?? null,
    anchored,
    found,
    outdated,
    changed: changed2,
    // A surviving element can still be a destination after its quoted words
    // have gone (rewritten text, replaced data or a virtual datum). Only a
    // resolved passage can supply the original quote's complete reading.
    localReading: Boolean(quoted?.quote) && placement?.kind !== "passage",
    title: !anchored ? null : found ? outdated ? "This comment refers to an earlier data revision" : changed2 ? "These words have changed since; jump to their current item" : quoted?.quote && placement.kind !== "passage" ? "Jump to the quoted item's current location" : "Jump to this passage" : thread.detached_from ? "This passage is no longer in the version shown" : "This passage can't be identified in the version shown"
  });
}
var STOPPED = /* @__PURE__ */ new Set(["ended", "stale", "interrupted"]);
function workingMessage(thread, attention, messages) {
  if (thread.resolved || messages.at(-1)?.provisional) return null;
  const covered2 = new Set(thread.summaries.flatMap(({ covers }) => covers));
  const pending = messages.filter(
    (message) => message.progress && !covered2.has(message.id)
  );
  const said2 = pending.at(-1)?.body.plainText ?? "";
  const saidAt = new Map(thread.msgs.map(({ id, seq }) => [id, seq ?? Infinity]));
  const workflows = thread.workflows ?? [];
  const running = workflows.find(
    (workflow) => !workflow.condition && ["working", "replying"].includes(workflow.stage)
  );
  const stopped = workflows.find(
    (workflow) => STOPPED.has(workflow.condition?.kind) && workflow.detail
  );
  const todo = thread.todos.find((open2) => open2.running);
  const [words, at, live, condition, agent] = running?.detail ? [running.detail, running.detail_seq, true, null, running.agent] : running ? [said2, saidAt.get(pending.at(-1)?.id), true, null, running.agent] : todo ? [todo.running.text, todo.running.seq, true, null, null] : stopped ? [
    stopped.detail,
    stopped.detail_seq,
    false,
    workflowLabel(stopped),
    stopped.agent
  ] : [said2, saidAt.get(pending.at(-1)?.id), false, null, null];
  if (!words || !pending.length && !live && !condition) return null;
  const agentMessage = messages.findLast((message) => message.author === "agent");
  const work = running?.detail ? running : !running && !todo ? stopped : null;
  const progress = !work && (running || !todo && !stopped) ? pending.at(-1) : null;
  const timestamp = work?.ts ?? progress?.timestamp ?? null;
  const feedback = work?.input ? {
    input_id: work.input,
    reply_id: null,
    reply_kind: "work"
  } : progress ? {
    reply_id: progress.id,
    attempt: progress.attempt,
    reply_kind: "progress"
  } : null;
  return Object.freeze({
    who: work?.agent || progress?.by || agent || agentMessage?.by || "Agent",
    after: messages.findLast((message) => saidAt.get(message.id) <= at).key,
    timestamp,
    age: timestamp ? ago(timestamp) : null,
    words: words.trim().replace(/\.$/, ""),
    feedback,
    live,
    condition
  });
}
function threadReading(thread, surface, commands2) {
  const resolved2 = Boolean(thread.resolved);
  const settling = Boolean(thread.settling);
  const kind = resolved2 ? "unresolve" : "resolve";
  const word = resolved2 ? "Reopen" : "Resolve";
  const label = resolved2 ? word : "Resolve thread";
  const attention = threadAttention(thread);
  const asking = new Set(
    thread.obligations.filter((item) => item.next_actor === "user" && answeredInWords(item)).map((item) => item.message)
  );
  const openTodos = new Set(thread.todos.map(({ id }) => id));
  const leaves = (message) => asking.has(message.id) ? "Waiting on me" : message.todo && openTodos.has(message.id) ? "To-do open" : null;
  const messages = turns(thread).map(
    (message) => messageReading(message, {
      nativeAuthored: Boolean(commands2.nativeAuthored),
      reactions: surface === "outlet" ? message.reactions : null,
      workflows: message.workflows,
      leaves: leaves(message)
    })
  );
  const summary = threadSummary(thread);
  return Object.freeze({
    key: threadKey(thread),
    summary,
    // How long ago the thread last moved, read here with the rest of the reading, so a
    // card whose reading did not change shows the same age and need not draw again.
    recency: summary.latest ? Object.freeze({ short: shortAgo(summary.latest), long: ago(summary.latest) }) : null,
    // A title comes from the agent's answer or beside it, so an untitled thread
    // waits for one only while the agent's work on it is under way. A turn that
    // ended, stalled or was never picked up sends none, and the thread reads its
    // opening words.
    titlePending: thread.title == null && thread.attention?.kind === "waiting" && thread.attention.reason === "workflow",
    unreadCount: thread.unread.length,
    id: thread.id,
    attempt: thread.root.attempt ?? null,
    surface,
    resolved: resolved2,
    attention,
    // A waiting thread's status is the stage of one message's workflow, which that
    // message already draws in its own header. The summary repeats it only for the
    // folded row, where no message shows; whose turn it is stays, since no message
    // says that.
    statusFolded: attention?.kind === "waiting" && attention.workflow !== null && messages.some((message) => message.workflow?.id === attention.workflow.id),
    // Where a resolved thread stands already says it is resolved: in a seat's Resolved
    // disclosure (inline.js). Who resolved it is said only where it was the agent.
    resolvedBy: thread.resolved?.author === "agent" ? `\u2713 Resolved by ${/** @type {{agent?: string}} */
    thread.resolved.agent}` : "",
    settlement: Object.freeze({
      kind,
      word,
      label,
      pending: settling
    }),
    reply: replyAvailable(thread),
    summaries: Object.freeze(thread.summaries),
    messages: Object.freeze(messages),
    working: workingMessage(thread, attention, messages),
    // The thread this reads, and the same reading of another state of it: the one a
    // seat holding news draws, the thread as it drew it (held-news.js).
    source: thread,
    reread: (held) => threadReading(held, surface, commands2)
  });
}
var ThreadView = class {
  #commands;
  #messageCommands;
  #rewrites;
  // The model this card shows. A signal, because its commands' liveness reads it, and
  // key and button reflection follow what they read (keyboard/scopes.js).
  #shown = M(null);
  get #model() {
    return this.#shown.value;
  }
  set #model(model) {
    this.#shown.value = model;
  }
  #transcript;
  #reply = null;
  #replyShown = false;
  #draftFrame = 0;
  #settlements = /* @__PURE__ */ new Map();
  #settlesAt = null;
  #actions = document.createElement("span");
  #marginControls = null;
  // What a thread in the page's flow holds back says so in its control row (held-news.js).
  #news = newsNotice();
  #continuity = null;
  #received = null;
  #headerSlot = null;
  #observedHeader = null;
  #sizes = sizeObserver(() => this.#retainHeaderSlot());
  constructor(commands2) {
    this.#commands = commands2;
    this.#rewrites = threadRewrites({
      thread: () => this.#model.key,
      views: () => this.#transcript.views,
      paint: () => this.repaint(),
      send: (id, text, options) => commands2.reply.actions.edit(this.#model.key, id, text, options),
      box: () => this.node.querySelector(SAY_BOX),
      home: () => this.node,
      // Opening a rewrite shows what the thread holds (held-news.js), and unfolds a
      // summary holding the message, since it opens to be seen.
      opening: (id) => {
        this.#showNews();
        this.#transcript.expandAround(id);
      },
      landInThread: commands2.reply.landInThread,
      landSent: commands2.reply.landSent
    });
    this.#messageCommands = {
      ...commands2,
      reaction: { ...commands2.reaction, pressed: () => this.#showNews() },
      edit: this.#rewrites.edit
    };
    this.node = document.createElement("div");
    this.#transcript = new Transcript({
      commands: commands2,
      messageCommands: this.#messageCommands,
      repaint: () => this.repaint(),
      home: () => this.node
    });
    this.#continuity = new ReplyContinuity(this.node);
    this.node.tabIndex = -1;
    this.node.classList.add("lf-page-thread", "lf-ui");
    this.node.dataset.lfRuntime = "";
    this.node.dataset.lfGen = "1";
    this.node.dataset.lfOffer = "";
    this.#actions.className = "lf-thread-meta-actions";
  }
  setMarginControls(controls2) {
    this.#marginControls = controls2;
  }
  get model() {
    return this.#model;
  }
  // Local disclosure and draft changes repaint the complete received descriptor,
  // never feed a held presentation back into the news owner's input.
  repaint() {
    this.#paint(this.#received);
  }
  // What holds the card folded away: the closed Resolved disclosure its seat gathers it
  // in (inline.js).
  get #fold() {
    const group = this.node.parentElement;
    return group?.matches(".lf-resolved-threads:not([open])") ? group : null;
  }
  // Where the seat's flow would grow if the card's settlement changed (inline.js), read
  // as the news comes: before the seat's next open thread, or before its Resolved
  // disclosure, for a resolved card that reopens; the disclosure, while it stands open,
  // for an open card that resolves into it. Null where nothing the seat draws grows.
  setSettlesAt(place2) {
    this.#settlesAt = place2;
  }
  // The last of the thread a reader can see, after which its news grows: the last
  // node its transcript shows (transcript.js, `foot`), and none while the thread is
  // folded. A card folded in its seat's Resolved disclosure draws nothing at all.
  get #foot() {
    return this.#fold ? null : this.#transcript.foot;
  }
  // What the thread draws after its messages that its settlement swaps: the reply box
  // while it stands open; none while the thread is folded, where it does not show. A
  // resolved card's Reopen stands where Resolve did, so settling grows nothing else.
  get #settlementRow() {
    if (this.#fold) return null;
    return this.node.querySelector(":scope > .lf-thread-reply");
  }
  // The node a message the thread draws stands in, after which a change to it grows;
  // none while the thread is folded, where no message shows.
  #messageNode(key) {
    return this.#fold ? null : this.#transcript.messageNode(key);
  }
  ownsMessage(id) {
    return this.#model?.id === id || this.#model?.messages.some((message) => message.id === id);
  }
  // The surface follows the whole thread; only this owner locates its message and
  // reply regions. Geometry readings carry no descendant nodes across that boundary.
  incomingTail(prior, next) {
    const known = new Set(prior.messages.map((message) => message.key));
    const incoming = next.messages.filter(
      (message) => message.author === "agent" && !known.has(message.key)
    );
    const latest = prior.messages.at(-1);
    const nextLatest = next.messages.at(-1);
    const grown = latest?.key === nextLatest?.key && nextLatest?.author === "agent" && latest.body.text !== nextLatest.body.text;
    if (!incoming.length && !grown) return null;
    const node = latest && this.#messageNode(latest.key);
    if (!node) return null;
    return {
      id: incoming.at(-1)?.id ?? nextLatest.id,
      tailStart: node.getBoundingClientRect().bottom,
      end: this.node.getBoundingClientRect().bottom,
      box: this.#reply?.node.getBoundingClientRect().top,
      pinned: replyPinned(this.#reply?.node)
    };
  }
  messageTail(id) {
    const message = this.#model.messages.find((message2) => message2.id === id);
    const node = message && this.#messageNode(message.key);
    return node ? {
      bottom: node.getBoundingClientRect().bottom,
      end: this.node.getBoundingClientRect().bottom
    } : null;
  }
  // HeldNews compares readings; this owner decides whether their changed regions
  // would move visible words. Existing-message changes and active compositions
  // retain the hold. A pinned reply can absorb growth at the thread's end, but cannot
  // absorb changes above it or settlement replacing the reply itself.
  newsMoves({ news, changed: changed2, folds, appendedAtEnd, footFold }) {
    const lands = news.settled ? this.#settlesAt?.() : null;
    if (lands && growthIsSeen(lands)) return true;
    if (this.#fold) return false;
    const pinned = replyPinned(this.#reply?.node);
    const foot = footFold && !folds.messages.some((key) => standsOn(this.#messageNode(key)));
    if (this.#model?.surface === "margin") {
      if (news.settled) return false;
      const last = this.#model.messages.at(-1);
      const list = this.#transcript.node;
      const follows = list.scrollHeight > list.clientHeight + 0.5 && atScrollEnd(list);
      const atEnd = (!news.appended || appendedAtEnd) && !news.summaries && [...changed2].every(
        (key) => key === last?.key && (last.provisional || follows)
      ) && (foot || !folds.messages.length && !folds.summaries.length);
      const writing = writingIn(
        this.#reply?.node.querySelector(TEXT_FIELD),
        last?.author === "user" && last.pending
      );
      const turn = news.appended || news.progress > 0 || footFold;
      return growthIsSeen(this.node) && (!atEnd || writing || this.#marginControls?.heldEdge(turn) === "foot");
    }
    const followed = pinned && !news.settled ? this.#foot : null;
    return this.#transcript.newsMoves({ news, changed: changed2, folds }, { followed }) || Boolean(news.settled && this.#settlementRow && growthIsSeen(this.#settlementRow));
  }
  // What a card draws from beyond its reading: whether a reply to it is being written
  // and whether it holds a draft.
  #outside(model) {
    return [
      replyIsEditing(model.key),
      threadHoldsDraft(
        model.key,
        model.messages.map(({ id }) => id)
      )
    ];
  }
  // Whether `model` is the reading this card last drew, outside inputs included, so a
  // pass that hands it over again need not draw it. The reading is rebuilt on every
  // pass, so it is compared by content; its `reread` is a fresh closure over the same
  // reading each time.
  shows(model) {
    const prior = this.#received;
    if (!prior || !this.#drawnWith) return false;
    if (this.#model?.news) return false;
    const { reread: _priorReread, ...was } = prior;
    const { reread: _reread, ...now } = model;
    const outside = this.#outside(model);
    return share(was, now) === was && outside.every((part, index) => part === this.#drawnWith[index]);
  }
  #drawnWith = null;
  present(model, options = {}) {
    return this.#paint(model, options, true);
  }
  // The caller knows whether this is a publication or a local repaint. Only a
  // publication allocates passive space; disclosures and editors stay intrinsic.
  #paint(model, _options = {}, published = false) {
    this.#received = model;
    this.#drawnWith = this.#outside(model);
    const prior = this.#model;
    if (model.news && !prior?.news) this.#retainHeaderSlot({ observe: false });
    const rewritten2 = this.#transcript.views.filter((view) => view.editing).map(({ node }) => node);
    const bodyPlace = published ? this.#continuity?.before(rewritten2) : null;
    const restoreFocus = holdFocus(this.node);
    this.#model = model;
    const reply = model.reply || replyIsEditing(model.key);
    this.#replyShown = reply;
    const marginControls = model.surface === "margin" ? this.#marginControls : null;
    const settlementPlace = marginControls ? "margin" : "head";
    const notice2 = this.#news;
    if (model.news) notice2.set(model.news);
    const news = model.news ? notice2.node : nothing;
    keeps(this.node, "data-thread", model.id);
    keeps(this.node, "data-resolved", model.resolved);
    keeps(this.node, "data-attempt", model.attempt || null);
    keeps(this.node, "role", "group");
    keeps(this.node, "aria-label", `Thread, ${model.summary.topic}`);
    const settlement = model.settlement ? this.#settlement(model, settlementPlace) : null;
    const actions = marginControls ? [
      model.news ? notice2.node : null,
      marginControls.nav,
      settlement,
      marginControls.close
    ].filter(Boolean) : [settlement].filter(Boolean);
    setChildren(this.#actions, actions);
    const threadActions = actions.length || model.news ? this.#actions : null;
    const handedOn = this.#transcript.present(model, {
      arrived: Boolean(prior),
      appends: model.surface === "margin"
    });
    if (reply && !this.#reply) this.#reply = this.#createReply(model);
    const body = html`
      ${this.#transcript.node}
      ${threadActions ? marginControls ? html`<div class="lf-margin-thread-controls">${threadActions}</div>` : html`<div class="lf-thread-controls" data-lf-reflow="text">
                ${news}${threadActions}
              </div>` : nothing}
    `;
    render(
      html`
        ${model.surface === "margin" ? body : html`<div class="lf-thread-content">${body}</div>`}
        ${reply ? this.#continuity?.gap ?? nothing : nothing}
        ${reply ? this.#reply.node : nothing}
      `,
      this.node
    );
    if (!marginControls && model.news)
      measure(this.node, () => this.#retainHeaderSlot());
    else this.#releaseHeaderSlot();
    this.#continuity?.after(bodyPlace);
    restoreFocus?.(
      handedOn ? () => (focusDestination(handedOn, "return"), true) : () => this.#commands.landInThread(this.node.querySelector(SAY_BOX) ?? this.node)
    );
    return this.node;
  }
  #releaseHeaderSlot() {
    if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
    this.#observedHeader = null;
    this.#releaseHeaderItems();
    this.#news.node.removeAttribute("data-lf-room");
  }
  #releaseHeaderItems() {
    for (const { node } of this.#headerSlot?.items ?? []) {
      node.classList.toggle("lf-held-header-item", false);
      node.style.removeProperty("--lf-held-header-width");
    }
    this.#headerSlot = null;
  }
  #retainHeaderSlot({ observe = true } = {}) {
    if (observe && !this.#model?.news) {
      this.#releaseHeaderSlot();
      return;
    }
    const content = this.node.querySelector(":scope > .lf-thread-content");
    const controls2 = content?.querySelector(":scope > .lf-thread-controls");
    const first = content?.querySelector(
      ":scope > .lf-thread-transcript > :nth-child(1 of .lf-msg, .lf-thread-checkpoint)"
    );
    const header = first?.querySelector(":scope > .lf-summary-checkpoint > .lf-summary-header") ?? first?.querySelector(":scope > .lf-msg-head");
    if (!controls2 || !header) {
      this.#releaseHeaderSlot();
      return;
    }
    const box = header.getBoundingClientRect();
    if (!box.width) return;
    const allocates = header.classList.contains("lf-msg-head");
    if (observe && this.#observedHeader !== header) {
      if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
      this.#sizes.observe(header);
      this.#observedHeader = header;
    }
    if (this.#headerSlot?.header !== header || this.#headerSlot.boxWidth !== box.width || !this.#model?.news) {
      const resizing = allocates && this.#headerSlot?.header === header;
      let reading = header;
      if (resizing) {
        reading = /** @type {HTMLElement} */
        header.cloneNode(true);
        Object.assign(reading.style, {
          position: "absolute",
          visibility: "hidden",
          inlineSize: layoutPx(box.width),
          margin: "0",
          anchorName: "none"
        });
        for (
          const node of
          /** @type {HTMLCollectionOf<HTMLElement>} */
          reading.children
        ) {
          node.classList.toggle("lf-held-header-item", false);
          node.style.removeProperty("--lf-held-header-width");
        }
        header.after(reading);
      } else this.#releaseHeaderItems();
      const widths = [...reading.children].map(
        (node) => node.getBoundingClientRect().width
      );
      if (resizing) reading.remove();
      const items = [
        .../** @type {HTMLCollectionOf<HTMLElement>} */
        header.children
      ].map((node, index) => ({
        node,
        width: widths[index]
      }));
      this.#headerSlot = { header, items, boxWidth: box.width, held: observe };
      for (const { node, width } of allocates ? items : []) {
        if (!observe && node.classList.contains("lf-msg-meta")) continue;
        node.classList.toggle("lf-held-header-item", true);
        node.style.setProperty("--lf-held-header-width", layoutPx(width));
      }
    }
    if (observe && !this.#headerSlot.held) {
      for (const item of allocates ? this.#headerSlot.items : []) {
        if (item.node.classList.contains("lf-msg-meta"))
          item.width = Math.max(item.width, item.node.getBoundingClientRect().width);
        item.node.classList.toggle("lf-held-header-item", true);
        item.node.style.setProperty("--lf-held-header-width", layoutPx(item.width));
      }
      this.#headerSlot.held = true;
    }
    const right = Math.max(
      box.left,
      ...this.#headerSlot.items.map(({ node }) => node.getBoundingClientRect().right)
    );
    controls2.style.setProperty("--lf-thread-news-start", layoutPx(right - box.left));
    if (this.#model.news) {
      if (!this.#news.node.hasAttribute("data-lf-room"))
        this.#news.node.dataset.lfRoom = this.#model.news.label;
      const line = controls2.getBoundingClientRect();
      const shown = shownRect(controls2, /* @__PURE__ */ new Map());
      if (shown)
        controls2.style.setProperty(
          "--lf-thread-news-visible-end",
          layoutPx(Math.max(0, shown.right - line.left))
        );
    } else this.#news.node.removeAttribute("data-lf-room");
  }
  // Whether the progress behind the working message stood open when last drawn
  // (transcript.js, `progressOpen`).
  get progressOpen() {
    return this.#transcript.progressOpen;
  }
  // A thread shows Reopen or the completed check in Resolve's place.
  #settlement(model, place2) {
    const state = model.settlement;
    const reopen = state.kind === "unresolve";
    const icon = place2 === "head" || place2 === "margin" && !model.resolved;
    const face = `${state.kind} ${place2}`;
    let button = this.#settlements.get(face);
    if (!button) {
      button = offer(
        "button",
        `lf-btn ${reopen ? "lf-reopen" : "lf-resolve"} ${icon ? "lf-icon-action" : "lf-thread-action"}`
      );
      button.type = "button";
      this.#settlements.set(face, button);
      const word = reopen ? "Reopen" : "Resolve";
      keys(button, `On a thread's ${word} button`, [
        {
          id: reopen ? "thread.reopen" : "thread.resolve",
          keys: PRESS,
          description: `${word} it`,
          title: word.toLowerCase(),
          control: button,
          when: () => !this.#model.settlement?.pending,
          run: this.#settle
        }
      ]);
    }
    keeps(button, "aria-busy", state.pending);
    if (icon) {
      const label = reopen && model.resolvedBy ? `${model.resolvedBy} \xB7 ${state.label}` : state.label;
      keeps(button, "aria-label", label);
      keeps(button, "title", label);
    }
    render(icon ? iconTemplate("check", "lf-action-icon") : state.label, button);
    return button;
  }
  // What the thread holds, shown by a press on one of its controls. Where showing it
  // takes the pressed control away, as a held settlement does Resolve, the press leaves
  // the user on the thread's title.
  #showNews() {
    if (!this.#model?.news) return;
    const restoreFocus = holdFocus(this.node);
    this.#model.news.open();
    restoreFocus?.(this.node);
  }
  // A press means what its control drew, and shows what the thread holds; where the
  // thread already stands as the press means, as one resolved elsewhere whose news
  // waits, it sends nothing (actions.js, `settle`).
  #settle = () => {
    const model = this.#model;
    this.#showNews();
    if (!model.resolved) dismissReply(model.key);
    void settleThread({
      parent: () => this.#model.id,
      key: model.key,
      resolved: model.resolved,
      prepareLanding: model.surface === "margin" ? model.resolved ? null : this.#marginControls?.prepareLanding : this.#prepareInlineLanding,
      ...this.#commands.settlement
    }).catch(() => {
    });
  };
  // A thread on the page moves as it settles: a resolved one into its seat's Resolved
  // disclosure, and a reopened one out of it, ahead of it (inline.js). Land where the
  // user went with it, the thread or the summary of the disclosure folding it, around
  // their focus, which a thread too tall to show leaves where it is.
  #prepareInlineLanding = () => {
    const mayLand = retainUserIntent({
      source: this.node,
      available: () => this.node.isConnected
    });
    const land2 = (may = mayLand) => {
      const place2 = this.#fold?.querySelector(":scope > summary") ?? this.node;
      if (!may() || !standingIn(place2)) return false;
      scrollThreadIntoView(place2, focused());
      return true;
    };
    return { optimistic: () => land2(), reverse: land2 };
  };
  #createReply(model) {
    const replyChanged = () => {
      if (!this.#reply) return;
      this.#draftFrame ||= nextRender(() => {
        this.#draftFrame = 0;
        if (!this.#reply) return;
        if (this.#model.resolved) this.repaint();
        if (this.#model.resolved) this.#commands.reply.changed();
      });
    };
    return createReplyView(model.key, this.#commands.reply, () => this.repaint(), {
      onChange: replyChanged,
      editLast: this.#rewrites.editLast
    });
  }
  commit() {
    this.#transcript.commit();
    if (!this.#replyShown && this.#reply) {
      this.#reply.dispose();
      this.#reply = null;
    }
  }
  // The reply being written in this thread, which no view holds, comes into this one
  // once it is `shown` (replies.js, `claim`).
  claimReply(shown) {
    this.#reply?.claim(shown);
  }
  retire() {
    this.#reply?.cancelDictation();
    this.#transcript.retire();
  }
  dispose() {
    this.#sizes.disconnect();
    this.#releaseHeaderSlot();
    this.#continuity?.release();
    this.retire();
    this.#reply?.dispose();
    this.#reply = null;
  }
};

// runtime/thread/inline.js
var seats = /* @__PURE__ */ new WeakMap();
var activeSeats = /* @__PURE__ */ new Set();
var EMPTY = Object.freeze({ threads: Object.freeze([]), response: false });
var activeBatch = null;
var ResolvedThreads = class {
  node = document.createElement("details");
  summary = document.createElement("summary");
  #threads = [];
  constructor() {
    this.node.className = "lf-resolved-threads lf-ui";
    this.node.dataset.lfRuntime = "";
    this.node.dataset.lfGen = "1";
    this.node.dataset.lfOffer = "";
    this.summary.className = "lf-resolved-summary";
    new MutationObserver(() => {
      if (this.node.open) for (const thread of this.#threads) thread.news?.open();
    }).observe(this.node, { attributeFilter: ["open"] });
  }
  // The summary says what its threads hold back in one notice of one line: the one
  // thread's news, or how many reopened or changed.
  present(threads, nodes) {
    this.#threads = threads;
    const held = threads.flatMap(({ news }) => news ? [news] : []);
    const notice2 = held.length > 1 ? `${held.length} ${held.every(({ reopened }) => reopened) ? "reopened" : "changed"}` : held[0]?.label ?? null;
    render(
      html`Resolved ·
      ${threads.length}${notice2 ? html` ·
              <span class="lf-thread-notice lf-thread-notice-news">${notice2}</span>` : ""}`,
      this.summary
    );
    setChildren(this.node, [this.summary, ...nodes]);
  }
};
var ThreadSeat = class {
  #views = /* @__PURE__ */ new Map();
  #resolved = null;
  #model = EMPTY;
  #shown = EMPTY;
  #committed = EMPTY;
  // A seat holds back news that would move what the reader reads, and says so in place
  // of its first-message row while it draws no thread (held-news.js). The margin's
  // floating card is a seat too, so it holds news as a seat in the page's flow does.
  #held = null;
  #notice = null;
  #commands = null;
  #response = () => null;
  #connected = false;
  #marginControls = null;
  constructor(node) {
    this.node = node;
  }
  configure(commands2, response, marginControls = null) {
    this.#commands ??= commands2;
    this.#response = response;
    this.#marginControls = marginControls;
  }
  present(model, batch = activeBatch) {
    if (batch && !batch.seats.has(this)) batch.seats.set(this, holdFocus(this.node));
    const restoreFocus = holdFocus(this.node);
    const standing2 = focused();
    const restoreBox = this.node.contains(standing2) ? holdBox(standing2) : () => {
    };
    const stoodIn = [...this.#views.values()].find(
      ({ node }) => standingIn(node)
    )?.node;
    const gathered = this.#resolved && standingIn(this.#resolved.summary) ? [...this.#resolved.node.children].slice(1) : [];
    this.#model = model;
    if (model.surface)
      this.#held ??= new HeldNews(
        this.node,
        (key) => this.#views.get(key),
        () => this.present(this.#model)
      );
    const prior = this.#shown;
    const box = model.surface === "page" ? this.#response() : null;
    const row = Boolean(box) && prior.response && !box.contains(standing2);
    const shown = this.#held ? this.#held.hold(model, { row }) : model;
    let foot = shown.response ? this.#response() : null;
    if (shown.news) {
      this.#notice ??= seatNotice();
      this.#notice.set(shown.news, box);
      foot = this.#notice.node;
    }
    this.#shown = shown;
    const added = shown.threads.filter(
      (thread) => !prior.threads.some(({ key }) => key === thread.key)
    );
    const wanted = new Set(shown.threads.map((thread) => thread.key));
    for (const [key, view] of this.#views)
      if (!wanted.has(key)) {
        releaseReplies(view.node);
        view.retire();
      }
    const nodes = [];
    const settled = [];
    for (const descriptor of shown.threads) {
      let view = this.#views.get(descriptor.key);
      if (!view)
        this.#views.set(descriptor.key, view = new ThreadView(this.#commands));
      view.setMarginControls(this.#marginControls);
      view.present(descriptor);
      if (descriptor.surface !== "margin" && descriptor.resolved && !descriptor.reply)
        settled.push(descriptor);
      else nodes.push(view.node);
    }
    if (!settled.length) this.#resolved = null;
    else {
      this.#resolved ??= new ResolvedThreads();
      this.#resolved.present(
        settled,
        settled.map(({ key }) => this.#views.get(key).node)
      );
      nodes.push(this.#resolved.node);
    }
    const fold2 = this.#resolved;
    const joins = () => fold2?.node.open ? fold2.node : null;
    let next = fold2?.node ?? null;
    for (const descriptor of shown.threads.toReversed()) {
      const view = this.#views.get(descriptor.key);
      if (!settled.includes(descriptor)) {
        view.setSettlesAt(joins);
        next = view.node;
      } else {
        const before = next;
        view.setSettlesAt(() => before);
      }
    }
    setChildren(this.node, foot ? [...nodes, foot] : nodes);
    this.claim();
    const own = added.filter(({ messages }) => messages[0]?.author === "user");
    const start = own.length === 1 ? own[0] : added.length === 1 ? added[0] : null;
    const started = start && this.#views.get(start.key).node;
    restoreFocus?.(
      started && (() => this.#commands?.reply.landSent(started)),
      ...gathered
    );
    const now = focused();
    if (fold2 && !fold2.node.open && fold2.node.contains(stoodIn ?? null) && (!now || now === document.body || standingIn(fold2.node) && now !== fold2.summary)) {
      focusDestination(fold2.summary, "return");
      passOn(fold2.node, fold2.summary);
    }
    restoreBox();
    if (!batch) this.commit();
  }
  // Each thread the seat shows takes the reply being written in it where no view holds
  // it (replies.js, `claim`), once the seat stands in the document, so the move keeps the
  // user in the editor. A seat drawn before it is placed, as the margin card's is, claims
  // once its owner places it (`claimSeatReplies`).
  claim() {
    const shown = () => this.node.isConnected;
    for (const { key } of this.#shown.threads) this.#views.get(key).claimReply(shown);
  }
  commit() {
    this.#committed = this.#model;
    const wanted = new Set(this.#shown.threads.map((thread) => thread.key));
    for (const [key, view] of this.#views) {
      if (wanted.has(key)) view.commit();
      else {
        view.dispose();
        this.#views.delete(key);
      }
    }
    this.#connected ||= this.node.isConnected;
  }
  retain(restoreFocus) {
    this.present(this.#committed);
    restoreFocus?.();
  }
  prune() {
    if (!this.#connected || this.node.isConnected) return false;
    this.#held?.dispose();
    for (const view of this.#views.values()) view.dispose();
    this.#views.clear();
    return true;
  }
};
function seatFor(host, commands2, response = () => null, marginControls = null) {
  let seat = seats.get(host);
  if (!seat) {
    seat = new ThreadSeat(host);
    seats.set(host, seat);
    activeSeats.add(seat);
  }
  seat.configure(commands2, response, marginControls);
  return seat;
}
function seatReading(threads, surface, commands2, response) {
  return Object.freeze({
    threads: Object.freeze(
      threads.map((thread) => threadReading(thread, surface, commands2))
    ),
    surface,
    response: Boolean(response)
  });
}
function renderThreadSurface(host, threads, commands2, response = null) {
  const editor = () => commands2.composition.outlet() === host ? commands2.composition.node() : null;
  seatFor(host, commands2, editor).present(
    seatReading(threads, "outlet", commands2, response)
  );
}
var claimSeatReplies = (host) => seats.get(host)?.claim();
function clearThreadSurface(host) {
  seats.get(host)?.present(EMPTY);
}
function mountFirstMessage(host, editor) {
  const seat = seatFor(host, null, () => editor);
  seat.present(Object.freeze({ threads: Object.freeze([]), response: true }));
  seat.commit();
}
function renderSeats(threads, commands2) {
  for (
    const host of
    /** @type {NodeListOf<HTMLElement>} */
    document.querySelectorAll(".lf-thread-seat[data-lf-thread-seat]")
  ) {
    const owner = elementById(host.dataset.lfThreadSeat);
    const owned = threads.filter((thread) => seatRoot(thread) === owner.id);
    const hold = registry[owner.localName]?.["x-thread-seat"]?.hold;
    const response = !owned.length || hold || loadDraft("say:" + owner.id) !== null;
    seatFor(host, commands2, () => host.lfFirstMessage).present(
      seatReading(owned, "page", commands2, response)
    );
  }
}
function renderMarginThread(host, thread, commands2, marginControls = null) {
  seatFor(host, commands2, () => null, marginControls).present(
    seatReading([thread], "margin", commands2, false)
  );
  return host.querySelector(":scope > .lf-page-thread");
}
function beginThreadSeats() {
  activeBatch = { seats: /* @__PURE__ */ new Map() };
  return activeBatch;
}
function commitThreadSeats(batch) {
  if (activeBatch !== batch) return;
  for (const seat of batch.seats.keys()) seat.commit();
  activeBatch = null;
  for (const seat of activeSeats)
    if (seat.prune()) {
      activeSeats.delete(seat);
      seats.delete(seat.node);
    }
}
function retainThreadSeats(batch) {
  if (activeBatch !== batch) return;
  for (const [seat, restoreFocus] of batch.seats) seat.retain(restoreFocus);
  activeBatch = null;
}

// runtime/thread/surfaces.js
var registrations = /* @__PURE__ */ new Map();
var claimedIds = /* @__PURE__ */ new Set();
var renderGeneration = 0;
function update(registration) {
  if (registration.reconcileQueued) return;
  registration.reconcileQueued = true;
  queueMicrotask(() => {
    registration.reconcileQueued = false;
    void registration.invalidate();
  });
}
function watchThreadSurfaces(commands2) {
  const tags = tagsDeclaring((entry) => entry["x-thread-surface"] === true);
  if (!tags.length) return;
  watchArrivals(tags.join(","), [], {
    arrive(owner) {
      if (registrations.has(owner)) return;
      if (!owner.matches(":defined")) return;
      register(
        owner,
        // A tag declaring `x-thread-surface` implements `threadOutlets`.
        (targets, context) => (
          /** @type {Element & {threadOutlets: (targets, context) => unknown}} */
          owner.threadOutlets(targets, context)
        ),
        commands2,
        "widget"
      );
    },
    leave(owner) {
      registrations.get(owner)?.handle.unregister();
    }
  });
}
var threadSurface = (owner) => Object.freeze({
  update() {
    const registration = registrations.get(owner);
    if (registration) update(registration);
  },
  open: (node) => registrations.get(owner)?.handle.open(node) ?? false
});
function placePageThreads(owner, render3, options) {
  if ([...registrations.values()].some((item) => item.kind === "page"))
    throw new Error("The document already has a page Thread presentation");
  return register(owner, render3, options, "page");
}
function register(owner, render3, { invalidate, composition, reveal }, kind) {
  if (!(owner instanceof Element))
    throw new TypeError("A Thread presentation needs an Element owner");
  if (registrations.has(owner))
    throw new Error(`Thread surface ${owner.localName} registered twice`);
  const registration = {
    render: render3,
    owner,
    kind,
    invalidate,
    composition,
    outlets: /* @__PURE__ */ new Set(),
    placements: null,
    // The datums where the widget drew a thread last, and the threads it holds out of
    // the seats it has not opened.
    drawn: /* @__PURE__ */ new Set(),
    held: kind === "widget" ? new HeldArrivals(() => update(registration)) : null,
    reconcileQueued: false,
    cancelRender: () => {
    }
  };
  registration.stopSide = declareSide((node) => {
    const outlet = [...registration.outlets].find((outlet2) => under(node, outlet2));
    if (!outlet) return null;
    const thread = closestAcross(node, ".lf-page-thread");
    if (thread && under(thread, outlet))
      return registration.placements?.placedAt(thread.dataset.thread)?.place ?? null;
    return outlet === composition.outlet() ? registration.placements?.pendingAt()?.place ?? null : null;
  });
  registrations.set(owner, registration);
  update(registration);
  let active = true;
  registration.handle = {
    read: readThreads,
    reveal(key) {
      if (!active) return false;
      const thread = readThreads().threads.find((item) => item.key === key);
      return thread ? reveal(thread.id) : false;
    },
    open(node) {
      if (!active) return false;
      const target = kind === "widget" ? datumAimTarget(node) : aimTargetAt(node);
      if (!target || kind === "widget" && (target.anchor.section !== owner.id || !under(target.element, owner)))
        throw new TypeError(
          kind === "widget" ? `Thread surface ${owner.localName} can open only its own projected datum` : "The page Thread presentation needs an addressable source target"
        );
      composition.open(target);
      return true;
    },
    update: () => update(registration),
    unregister() {
      if (!active) return;
      active = false;
      registrations.delete(owner);
      clearRegistration(registration);
      update(registration);
    }
  };
  return registration.handle;
}
function clearOutlets(outlets) {
  for (const outlet of outlets) {
    clearThreadSurface(outlet);
    delete outlet.dataset.lfThreadSurface;
  }
}
function reportFailure({ owner }, error) {
  reportPageError(error, `thread surface ${owner.localName}#${owner.id} failed`);
}
function releaseOutlets(node) {
  for (const { outlets, composition } of registrations.values()) {
    const outlet = composition.outlet();
    if (outlets.has(outlet) && under(outlet, node)) composition.restore();
  }
}
function clearRegistration(registration) {
  registration.cancelRender();
  registration.stopSide();
  registration.held?.dispose();
  registration.drawn = /* @__PURE__ */ new Set();
  if (registration.outlets.has(registration.composition.outlet()))
    registration.composition.restore();
  clearOutlets(registration.outlets);
  registration.outlets.clear();
}
function validateOutlets({ owner }, byOutlet) {
  for (const outlet of byOutlet.keys()) {
    if (!outlet.isConnected) byOutlet.delete(outlet);
    else if (!under(outlet, owner))
      throw new Error(
        `Thread surface ${owner.localName} returned an outlet outside its presentation owner`
      );
  }
}
function exactTarget({ owner, kind }, anchor, placement) {
  return placement?.status === "exact" && (kind === "page" ? placement.place instanceof Element : anchor?.datum && anchor.section === owner.id && placement.datumElement instanceof Element && under(placement.datumElement, owner));
}
function renderSurfaces(collection, placements, commands2) {
  const generation2 = ++renderGeneration;
  const current = () => generation2 === renderGeneration;
  for (const registration of registrations.values()) registration.cancelRender();
  const cancel = () => {
    if (!current()) return;
    ++renderGeneration;
    for (const registration of registrations.values()) registration.cancelRender();
  };
  const activeComposition = commands2.composition.active();
  let prepared = null;
  const completion = prepare2().then((plans) => {
    prepared = plans;
  });
  return { completion, cancel, commit };
  async function prepare2() {
    const plans = [];
    const ordered = [...registrations.values()].sort(
      (a, b) => Number(a.kind === "page") - Number(b.kind === "page")
    );
    for (const registration of ordered) {
      const { render: render3, owner } = registration;
      if (registrations.get(owner) !== registration) continue;
      if (!owner.isConnected) {
        registrations.delete(owner);
        clearRegistration(registration);
        continue;
      }
      registration.placements = placements;
      const byOutlet = /* @__PURE__ */ new Map();
      const abort = new AbortController();
      const cancelled = aborted(abort.signal);
      registration.cancelRender = () => abort.abort();
      let compositionOutlet = null;
      const committed = [];
      try {
        const byKey = new Map(collection.threads.map((thread) => [thread.key, thread]));
        const targets = /* @__PURE__ */ new Map();
        for (const thread of collection.threads) {
          if (registration.kind === "page" ? heldOut(thread.id) : thread.anchor?.section !== owner.id)
            continue;
          const placement2 = placements.placedAt(thread.id);
          if (exactTarget(registration, thread.anchor, placement2))
            targets.set(thread.key, { anchor: thread.anchor, placement: placement2 });
        }
        const held = registration.held?.hold(
          [...targets].map(([key, { anchor: anchor2, placement: placement2 }]) => ({
            thread: byKey.get(key),
            datum: anchor2.datum,
            node: placement2.datumElement
          })),
          { drawn: registration.drawn, all: collection.threads }
        );
        const anchor = activeComposition?.anchor;
        const placement = anchor && (registration.kind === "page" || anchor.datum && anchor.section === owner.id) ? placements.pendingAt() : null;
        const batch = [...targets].filter(([key]) => !held?.has(key)).map(([key, target]) => Object.freeze({ ...target, thread: byKey.get(key) }));
        if (exactTarget(registration, anchor, placement))
          batch.push(Object.freeze({ anchor, placement, thread: null }));
        const rendering = render3(Object.freeze(batch), {
          signal: abort.signal,
          collection,
          onCommit: (run) => committed.push(run)
        });
        const outlets = rendering?.then ? await Promise.race([rendering, cancelled]) : rendering;
        if (!current()) return null;
        if (registrations.get(owner) !== registration || !owner.isConnected) {
          clearRegistration(registration);
          continue;
        }
        if (abort.signal.aborted) continue;
        if (!Array.isArray(outlets) || outlets.length !== batch.length)
          throw new TypeError(
            "A Thread placement callback must return one outlet or null per target"
          );
        for (let index = 0; index < batch.length; index++) {
          const outlet = outlets[index];
          if (outlet === null) continue;
          if (!(outlet instanceof Element))
            throw new TypeError("A Thread outlet must be an Element or null");
          const threads = byOutlet.get(outlet) ?? [];
          const { thread } = batch[index];
          if (thread) threads.push(thread);
          else compositionOutlet = outlet;
          byOutlet.set(outlet, threads);
        }
        validateOutlets(registration, byOutlet);
        if (compositionOutlet && (!byOutlet.has(compositionOutlet) || !sameAnchor(commands2.composition.active()?.anchor, anchor)))
          compositionOutlet = null;
      } catch (error) {
        if (!current()) return null;
        if (abort.signal.aborted) continue;
        if (registration.kind === "page") throw error;
        plans.push({
          registration,
          byOutlet: /* @__PURE__ */ new Map(),
          compositionOutlet: null,
          committed: []
        });
        reportFailure(registration, error);
        continue;
      }
      plans.push({ registration, byOutlet, compositionOutlet, committed });
    }
    return current() ? plans : null;
  }
  function commit() {
    if (!current() || !prepared) return;
    const plans = prepared.filter(
      ({ registration }) => registrations.get(registration.owner) === registration && registration.owner.isConnected
    );
    const widgetClaims = /* @__PURE__ */ new Set();
    for (const plan of plans) {
      try {
        validateOutlets(plan.registration, plan.byOutlet);
        for (const [outlet, threads] of plan.byOutlet)
          plan.byOutlet.set(
            outlet,
            threads.filter(
              (thread) => exactTarget(
                plan.registration,
                thread.anchor,
                placements.placedAt(thread.id)
              ) && (plan.registration.kind === "widget" || !widgetClaims.has(thread.id) && !heldOut(thread.id))
            )
          );
        if (!plan.byOutlet.has(plan.compositionOutlet) || !exactTarget(
          plan.registration,
          activeComposition?.anchor,
          placements.pendingAt()
        ))
          plan.compositionOutlet = null;
      } catch (error) {
        if (plan.registration.kind === "page") throw error;
        reportFailure(plan.registration, error);
        plan.byOutlet.clear();
        plan.compositionOutlet = null;
      }
      if (plan.registration.kind === "widget") {
        for (const threads of plan.byOutlet.values())
          for (const thread of threads) widgetClaims.add(thread.id);
      }
    }
    const previousComposition = commands2.composition.outlet();
    let movedComposition = false;
    try {
      if (sameAnchor(activeComposition?.anchor, commands2.composition.active()?.anchor)) {
        movedComposition = true;
        const seated = plans.some(
          ({ compositionOutlet }) => compositionOutlet && commands2.composition.seat(compositionOutlet)
        );
        if (!seated) commands2.composition.restore();
      }
      const nextClaimed = /* @__PURE__ */ new Set();
      for (const { registration, byOutlet } of plans) {
        for (const outlet of registration.outlets)
          if (!byOutlet.has(outlet)) clearThreadSurface(outlet);
        for (const [outlet, threads] of byOutlet) {
          const response = outlet === commands2.composition.outlet() ? commands2.composition.node() : null;
          renderThreadSurface(outlet, threads, commands2, response);
          for (const thread of threads) nextClaimed.add(thread.id);
        }
      }
      for (const { registration, byOutlet } of plans) {
        for (const outlet of registration.outlets)
          if (!byOutlet.has(outlet)) delete outlet.dataset.lfThreadSurface;
        for (const outlet of byOutlet.keys())
          outlet.toggleAttribute("data-lf-thread-surface", true);
        registration.outlets = new Set(byOutlet.keys());
        registration.drawn = new Set(
          [...byOutlet.values()].flat().map((thread) => thread.anchor.datum)
        );
      }
      claimedIds = nextClaimed;
      prepared = null;
    } catch (error) {
      if (movedComposition) {
        if (!previousComposition?.isConnected || !commands2.composition.seat(previousComposition))
          commands2.composition.restore();
      }
      throw error;
    }
    for (const { registration, committed } of plans)
      for (const run of committed) {
        try {
          run();
        } catch (error) {
          reportFailure(registration, error);
        }
      }
  }
}
var claimed = (id) => claimedIds.has(id);
var heldOut = (id) => [...registrations.values()].some(({ held }) => held?.holds(id));
function revealHeld(ids) {
  for (const registration of registrations.values()) {
    const [id] = registration.held?.show(ids) ?? [];
    if (id) {
      const presented = (async () => {
        await registration.invalidate();
        await whenDocumentPresented();
      })();
      return { id, presented };
    }
  }
  return null;
}
function surfaceFocusTarget(id, { part = "reply" } = {}) {
  if (part === "message") return null;
  id = threadIdNamed(id);
  for (const registration of registrations.values()) {
    const thread = [...registration.outlets].map(
      (outlet) => outlet.querySelector(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`)
    ).find(Boolean);
    if (!thread) continue;
    return threadFocusDestination(thread, { part });
  }
  return null;
}

export {
  retainUserIntent,
  restrictUserIntent,
  focusedInView,
  placeKeeper,
  landingRoom,
  fitsWhole,
  alreadyShown,
  scrollIntoReadingBand,
  scrollIntoView,
  textBlocks,
  passageBlock,
  openingPassage,
  blocksOnScreen,
  readingBlock,
  pageReadingBlock,
  landingPlace,
  capturePlace,
  placeNode,
  placeOffset,
  hasLandmark,
  rawOffsetFits,
  restorePlace,
  readObligations,
  obligationEntry,
  answeredInWords,
  approvalBlockingObligations,
  obligationPlace,
  obligationsIn,
  declareSide,
  obligationHolding,
  placeOf,
  arrivalOf,
  standingOrigin,
  walkOrigin,
  stepFrom,
  heldObligation,
  ensureSyntaxLanguage,
  syntax,
  synNodes,
  tokenLines,
  langForPath,
  highlightBlocks,
  isPagePaint,
  quietWord,
  isExternalPageLink,
  renderQuiet,
  copyControl,
  copyBlock,
  renderMarkdown,
  markdownWords,
  inlineMarkdownFragment,
  prepareDeclaredMarkdown,
  formatDeclaredMarkdown,
  paintMarkdown,
  placedMarkdownTokens,
  markdownSourceOffset,
  markdownReady,
  loadMarkdown,
  rememberPassageParts,
  reindexPassageOwners,
  preloadWidgets,
  importWidgets,
  patchDocument,
  upgradeWidgets,
  PAGE_SCOPE,
  tabStore,
  openingView,
  keepView,
  draftStore,
  userStore,
  PAGE_DRAFT,
  whereDraft,
  tellDraft,
  storedDraft,
  replyContext,
  threadDraft,
  draftHasContent,
  saveDraft,
  clearDraft,
  transferDraft,
  loadDraft,
  draftContexts,
  settleAcceptedDrafts,
  sendDraft,
  sendMessage,
  keepRefusedWords,
  rememberWriting,
  registerWritingDestination,
  createWritingResume,
  captureDraftEditing,
  draftEditingStands,
  draftEditingDestination,
  restoreDraftEditing,
  watchDraft,
  watchDrafts,
  mirrorDraft,
  declareOffFlowSurface,
  bringBackSurfaceOf,
  THREAD,
  drawnThreadId,
  SAYS_IN,
  SAY_BOX,
  showLatestTurn,
  keepThreadLanding,
  scrollThreadIntoView,
  sendLanding,
  followBoxGrowth,
  readBoxPlace,
  openMessageEditIn,
  threadRewrites,
  workflowLabel,
  progressFace,
  isWorkflowProgress,
  workflowStep,
  isPageWidgetWorkflow,
  strongestWorkflow,
  todoLabel,
  threadAttention,
  DESIGN_MODE_KEY,
  designName,
  HOLDS_WORD,
  holdToRead,
  loadMessageMarkdown,
  messageText,
  threadName,
  threadSummary,
  prepareAuthoredMessage,
  messageReading,
  MessageView,
  messageHolding,
  anchorLabel,
  ELEMENTS,
  pageScope,
  pageCommand,
  pageRung,
  pageScopes,
  touchPresses2 as touchPresses,
  stances,
  universalCommandReference,
  textEntryScope,
  allButCommandReference,
  pageDoor,
  selectionAnchor,
  pageSelection,
  createPassageSelection,
  leftThePage,
  snapSelection,
  walkPositionLabel,
  listWalkPosition,
  walkPosition,
  rowWalk,
  beginWalk,
  threadState,
  allThreads,
  readThreads,
  threadList,
  threadNamed,
  threadIdNamed,
  replyDraftContext,
  holdReplyCompositions,
  replyDraftsHold,
  dismissReply,
  dismissReplyAt,
  releaseReplies,
  replyCompositionHasDraft,
  replyIsEditing,
  writingIn,
  replyAvailable,
  restoreReplyEditing,
  createReplyView,
  settleThread,
  focusThread,
  declareThreadParts,
  wholeThread,
  threadPart,
  threadReplyInput,
  threadFocusDestination,
  focusedThreadTarget,
  heldThread,
  heldThreadId,
  standingThreadId,
  replyDestination,
  carryingThreadPlace,
  holdThreadPlace,
  readingIsContinuous,
  readingReturn,
  onReadingInterrupted,
  completeReadingReturn,
  newsNotice,
  showHeld,
  showHeldThread,
  HeldNews,
  HeldReading,
  heldGrowth,
  Transcript,
  quoteReading,
  threadReading,
  ThreadView,
  claimSeatReplies,
  mountFirstMessage,
  renderSeats,
  renderMarginThread,
  beginThreadSeats,
  commitThreadSeats,
  retainThreadSeats,
  watchThreadSurfaces,
  threadSurface,
  placePageThreads,
  releaseOutlets,
  renderSurfaces,
  claimed,
  heldOut,
  revealHeld,
  surfaceFocusTarget
};
